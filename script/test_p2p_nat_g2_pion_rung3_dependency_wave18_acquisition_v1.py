#!/usr/bin/env python3
"""Focused offline tests for the Wave18 acquisition permit checker."""

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
    raise RuntimeError("Wave18 acquisition tests require `python3 -I -B -S`")

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
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave18_v1_once.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition_v1.py"
)
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave18_v1_once.py"
)
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "execution-permit-v1.md"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave18-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave18-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_decision_v1.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
WAVE4_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)

DECISION_RAW_SHA256 = (
    "c90d16a7c7194c7a6dbde2be9bd99f4101a3a8cd1722278209fe5df8bf6371fa"
)
DECISION_CONTENT_SHA256 = (
    "c75e5751d3e7c67939251d56e212f95f85439d05684cd50a49701de3e099803d"
)
DECISION_READER_RAW_SHA256 = (
    "862ac89248970b9b4d59230e6b9f894b3fc49ed82f151608687e82cb8b1d1a2d"
)
DECISION_CHECKER_RAW_SHA256 = (
    "bad407e7e0c95dc843ccc7bd7b0aa578c10f70b0592c110eab52fba0c6a73b57"
)
DECISION_TESTS_RAW_SHA256 = (
    "e6ae108af2326c97ac2db488451922640ddecefe576d8c7dedd0415a6e57904d"
)
WAVE4_CHECKER_RAW_SHA256 = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
WAVE4_RUNNER_RAW_SHA256 = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)
DECISION_REQUEST_SHA256 = (
    "3c13b764b7267efe885528d9f7d4fe31d6b7bdac48839f95e60bb5bd45a7d836"
)
RESOURCE_SHA256 = (
    "86587f7dbea64ab85bdfd32287595007577de1ea3d0bb554c6471af81b4d8602"
)
PROJECTION_SHA256 = (
    "acb203748c6976b219949a73a89da48a381f6db4d33faa6f91fd5e9e6ab17304"
)
CHECKER_CALL_COUNT = 403
CHECKER_CALL_SURFACE_SHA256 = (
    "964ce3495d8715fcbfbcbfc990ee80ff3a25a4b464c0ab019667f652c184c13a"
)
TUPLES = (
    (
        "golang.org/x/mod",
        "v0.24.0",
        "bb2025870bcef7a0c287192f498f0138c441987a31a5c93bbe69ac05c5d349e7",
        "h1:IXM97Txy2VM4PJ3gI61r1YEk/gAj6zAHN3AdZt6S9Ww=",
        "h1:ZfthKaKaT4NrhGVZHO1/WDTwGES4De8KtWO0SIbNJMU=",
    ),
    (
        "golang.org/x/net",
        "v0.40.0",
        "3c84a9eecca520aed886113ab5bf71b0c60c4f09df0144e66e385dae973eda2b",
        "h1:y0hY0exeL2Pku80/zKK7tpntoX23cqL3Oa6njdgRtds=",
        "h1:79Xs7wF06Gbdcg4kdCCIQArK11Z1hr5POQ6+fIYHNuY=",
    ),
    (
        "golang.org/x/sync",
        "v0.14.0",
        "4615480e24f0c4184e4c21ec74e129cb39fbe55c729ca6c997146da3a3924000",
        "h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=",
        "h1:woo0S4Yywslg6hp4eUFjTVOyKt0RookbpAHG4c1HmhQ=",
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
    "wave18PublicProxy6GetAcquisitionAuthorizedOnce": True,
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
    module = types.ModuleType("wave18_acquisition_checker_test_subject")
    module.__dict__.update(
        {
            "__file__": str(ROOT / CHECKER_PATH),
            "__name__": "wave18_acquisition_checker_test_subject",
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
        raise RuntimeError("Wave18 checker test permit schema")
    tool_bindings = permit.get("toolBindings")
    if type(tool_bindings) is not list:
        raise RuntimeError("Wave18 checker test tool bindings")
    checker_bindings = [
        row
        for row in tool_bindings
        if type(row) is dict and row.get("path") == CHECKER_PATH
    ]
    if len(checker_bindings) != 1:
        raise RuntimeError(
            "Wave18 checker test checker binding cardinality"
        )
    binding = checker_bindings[0]
    if (
        set(binding)
        != {"normalizedSha256", "path", "rawSha256", "role"}
        or binding["role"] != "wave18_acquisition_checker"
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
        raise RuntimeError("Wave18 checker test preload gate")
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
                        f"wave18-{tuple_order:03d}-{digest[:12]}",
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


class Wave18AcquisitionCheckerTests(unittest.TestCase):
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

    def test_03_exact_six_resource_typed_projection_and_hashes(self) -> None:
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
            ["mod", "zip", "mod", "zip", "mod", "zip"],
        )
        self.assertEqual(
            [row["maximumResponseBodyBytes"] for row in rows],
            [1_048_576, 16_777_216] * 3,
        )
        self.assertEqual(
            [row["requestOrdinal"] for row in rows],
            list(range(1, 7)),
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
                "wave18PublicProxy6GetAcquisitionAuthorizedOnce",
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
        self.assertEqual(limits["maximumRequestCount"], 6)
        self.assertEqual(limits["maximumModResponseBodyBytes"], 1_048_576)
        self.assertEqual(limits["maximumZipResponseBodyBytes"], 16_777_216)
        self.assertEqual(
            limits["maximumAggregateResponseBodyBytes"],
            53_477_376,
        )
        self.assertEqual(
            limits["maximumAggregateModResponseBodyBytes"],
            3_145_728,
        )
        self.assertEqual(
            limits["maximumAggregateZipResponseBodyBytes"],
            50_331_648,
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
                ".wave-18-v1.claim"
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
                "successRequiresNoActiveOperationAndExact6CommittedCounts"
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
                ".wave-18-v1-readback.claim"
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
            60_000,
        )
        self.assertEqual(zip_limits["maximumEntryNameBytes"], 1_024)
        self.assertEqual(
            zip_limits["maximumUncompressedBytesPerZip"],
            134_217_728,
        )
        self.assertEqual(
            zip_limits["maximumUncompressedBytesAcrossAllZips"],
            402_653_184,
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

    def test_11_reserved_namespace_rejects_all_wave18_names(self) -> None:
        reserved = object.__new__(CHECKER.HeldReservedNamespace)
        clean = [".wave-17-v1.claim", "wave-17-v1"]
        with mock.patch.object(reserved, "_names", return_value=clean):
            reserved.observe_absent()
        for name in (
            ".wave-18-v1.claim",
            "wave-18-v1",
            ".wave-18-v1-readback.claim",
            ".wave-18-v1-staging-test",
            ".wave-18-readback-v1-test",
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
        self.assertEqual(values["decision"]["identityResolution"]["tupleCount"], 3)
        self.assertIs(
            values["decision"]["identityResolution"]["tuples"][0][
                "selectedByGraphAlgorithm"
            ],
            False,
        )
        self.assertEqual(summary["requestCount"], 6)
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
                    "requestCount": 6,
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
                    value["sourceAcquisitionPreparation"]["requestSet"][5][
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
