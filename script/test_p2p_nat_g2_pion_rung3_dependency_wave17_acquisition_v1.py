#!/usr/bin/env python3
"""Focused offline tests for the Wave17 acquisition permit checker."""

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
    raise RuntimeError("Wave17 acquisition tests require `python3 -I -B -S`")

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
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py"
)
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py"
)
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "execution-permit-v1.md"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave17_decision_v1.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
WAVE4_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)

DECISION_RAW_SHA256 = (
    "659e9ce6f079701cab68e337d2746959741ef4868ffff6392fcdbf26ae692f93"
)
DECISION_CONTENT_SHA256 = (
    "867a2ba1a7da54b5466951b1caea9b09eb355d2325a58fa552037047d3fad7df"
)
DECISION_READER_RAW_SHA256 = (
    "3af49874bd518628971566d6067331c75e2f4fbcf7ac36bafee914938873ef51"
)
DECISION_CHECKER_RAW_SHA256 = (
    "564a8f0c3a6dbf9331fe8e02d121efe8c4e91fcd6c5e7415607e0c0b6d9fb256"
)
DECISION_TESTS_RAW_SHA256 = (
    "5af9a8ed93b2424e4251cbe3b47de3281c498fc93e707975311dbddff41065a6"
)
WAVE4_CHECKER_RAW_SHA256 = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
WAVE4_RUNNER_RAW_SHA256 = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)
DECISION_REQUEST_SHA256 = (
    "acf64af2352fb4d82325f3e5bd2a3e913b8ef95db553fa0015bc71a239f3fb35"
)
RESOURCE_SHA256 = (
    "4920d020b6a4df4adc890a8eb2a0290e1343938483e396cc7e21447728f14686"
)
TUPLE_DIGEST = (
    "8bd04ea612cec978713135c7452cb52e20350f82cd8b2a17691e3c431b43973c"
)
GO_MOD_H1 = "h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI="
ZIP_H1 = "h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc="


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
    "wave17PublicProxy2GetAcquisitionAuthorizedOnce": True,
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
    module = types.ModuleType("wave17_acquisition_checker_test_subject")
    module.__dict__.update(
        {
            "__file__": str(ROOT / CHECKER_PATH),
            "__name__": "wave17_acquisition_checker_test_subject",
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


def identity_rows() -> list[dict[str, object]]:
    common = {
        "host": "proxy.golang.org",
        "method": "GET",
        "module": "golang.org/x/tools",
        "port": 443,
        "selectedByGraphAlgorithm": False,
        "tupleDigestSha256": TUPLE_DIGEST,
        "tupleId": "wave17-001-8bd04ea612ce",
        "tupleOrder": 1,
        "version": "v0.33.0",
    }
    return [
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.mod",
            "expectedH1": GO_MOD_H1,
            "kind": "mod",
            "maximumResponseBodyBytes": 1_048_576,
            "path": "/golang.org/x/tools/@v/v0.33.0.mod",
            "requestOrdinal": 1,
            "url":
                "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.mod",
        },
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.zip",
            "expectedH1": ZIP_H1,
            "kind": "zip",
            "maximumResponseBodyBytes": 16_777_216,
            "path": "/golang.org/x/tools/@v/v0.33.0.zip",
            "requestOrdinal": 2,
            "url":
                "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.zip",
        },
    ]


CHECKER_RAW = (ROOT / CHECKER_PATH).read_bytes()
CHECKER_SOURCE = CHECKER_RAW.decode("utf-8")
CHECKER_TREE = ast.parse(CHECKER_SOURCE, filename=CHECKER_PATH)
CHECKER = load_module(CHECKER_RAW)
RUNNER_RAW = (ROOT / RUNNER_PATH).read_bytes()
PERMIT_RAW = (ROOT / PERMIT_PATH).read_bytes()
PERMIT = json.loads(PERMIT_RAW)


class Wave17AcquisitionCheckerTests(unittest.TestCase):
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

    def test_03_exact_two_resource_contract_and_distinct_hashes(self) -> None:
        rows = identity_rows()
        self.assertEqual(CHECKER.resource_contract(), rows)
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
            sha256(b"golang.org/x/tools\nv0.33.0\n"),
            TUPLE_DIGEST,
        )
        self.assertEqual(
            [row["kind"] for row in rows],
            ["mod", "zip"],
        )
        self.assertEqual(
            [row["maximumResponseBodyBytes"] for row in rows],
            [1_048_576, 16_777_216],
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
                "wave17PublicProxy2GetAcquisitionAuthorizedOnce",
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
        self.assertEqual(limits["maximumRequestCount"], 2)
        self.assertEqual(limits["maximumModResponseBodyBytes"], 1_048_576)
        self.assertEqual(limits["maximumZipResponseBodyBytes"], 16_777_216)
        self.assertEqual(
            limits["maximumAggregateResponseBodyBytes"],
            17_825_792,
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
                ".wave-17-v1.claim"
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
                "successRequiresNoActiveOperationAndExact2CommittedCounts"
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
                ".wave-17-v1-readback.claim"
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
        self.assertEqual(zip_limits["maximumEntryNameBytes"], 1_024)
        self.assertEqual(
            zip_limits["maximumUncompressedBytesPerZip"],
            134_217_728,
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

    def test_11_reserved_namespace_rejects_all_wave17_names(self) -> None:
        reserved = object.__new__(CHECKER.HeldReservedNamespace)
        clean = [".wave-16-v1.claim", "wave-16-v1"]
        with mock.patch.object(reserved, "_names", return_value=clean):
            reserved.observe_absent()
        for name in (
            ".wave-17-v1.claim",
            "wave-17-v1",
            ".wave-17-v1-readback.claim",
            ".wave-17-v1-staging-test",
            ".wave-17-readback-v1-test",
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
        self.assertEqual(values["decision"]["identityResolution"]["tupleCount"], 1)
        self.assertIs(
            values["decision"]["identityResolution"]["tuples"][0][
                "selectedByGraphAlgorithm"
            ],
            False,
        )
        self.assertEqual(summary["requestCount"], 2)
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
                    "requestCount": 2,
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


if __name__ == "__main__":
    unittest.main()
