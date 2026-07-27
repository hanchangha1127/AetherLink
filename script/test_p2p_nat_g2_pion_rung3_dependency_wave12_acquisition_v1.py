#!/usr/bin/env python3
"""Tests for the Wave12 acquisition permit checker."""

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
    raise RuntimeError("Wave12 acquisition tests require `python3 -I -B -S`")

import ast
import copy
import http.client
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock


def _deny_test_network(*_args, **_kwargs):
    raise AssertionError(
        "offline Wave12 tests must never create network connections"
    )


http.client.HTTPSConnection = _deny_test_network
socket.create_connection = _deny_test_network


CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave12_acquisition_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave12_acquisition_permit_v1",
    CHECKER_PATH,
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

EXPECTED_WAVE12_IDENTITIES = (
    (
        "golang.org/x/crypto",
        "v0.41.0",
        False,
        "h1:pO5AFd7FA68rFak7rOAGVuygIISepHftHnr8dr6+sUc=",
        "h1:WKYxWedPGCTVVl5+WHSSrOBT0O8lx32+zxmHxijgXp4=",
    ),
    (
        "golang.org/x/term",
        "v0.34.0",
        False,
        "h1:5jC53AEywhIVebHgPVeg0mj8OD3VO9OzclacVrqpaAw=",
        "h1:O/2T7POpk0ZZ7MAzMeWFSg6S5IpWd/RXDlM9hgM3DR4=",
    ),
    (
        "golang.org/x/text",
        "v0.28.0",
        False,
        "h1:U8nCwOR8jO/marOQ0QbDiOngZVEBB7MAiitBuMjXiNU=",
        "h1:rhazDwis8INMIwQ4tpjLDzUhx6RlXqZNPEM0huQojng=",
    ),
    (
        "golang.org/x/tools",
        "v0.35.0",
        False,
        "h1:NKdj5HkL/73byiZSJjqJgKn3ep7KjFkBOkR/Hps3VPw=",
        "h1:mBffYraMEf7aa0sB+NuKnuCy8qI/9Bughn8dC2Gu5r0=",
    ),
)


class Wave12AcquisitionPermitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package, cls.summary = check.evaluate(True)
        cls.decision = cls.package["decision"]
        cls.permit = cls.package["permit"]
        cls.rows = check.normalized_resources(cls.decision)

    def test_materialized_package_is_exact_and_content_bound(self) -> None:
        raw = (check.ROOT / check.PERMIT_PATH).read_bytes()
        self.assertEqual(raw, check.canonical_bytes(self.permit))
        self.assertEqual(check.strict_json(raw), self.permit)
        without = dict(self.permit)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            check.sha256(check.canonical_bytes(without)),
        )
        actual = {
            path: check.sha256((check.ROOT / path).read_bytes())
            for path in (
                check.THIS_CHECKER_PATH,
                check.THIS_TESTS_PATH,
                check.RUNNER_PATH,
                check.RUNNER_TESTS_PATH,
            )
        }
        self.assertEqual(
            {
                row["path"]: row["rawSha256"]
                for row in self.permit["toolBindings"]
            },
            actual,
        )
        self.assertIs(self.summary["claimExists"], False)
        self.assertIs(self.summary["permitConsumed"], False)
        self.assertIs(self.summary["runnerInvoked"], False)
        self.assertIs(self.summary["networkUsed"], False)
        self.assertEqual(self.summary["fileWriteCount"], 0)
        self.assertIs(self.permit["structurePreparationOnly"], False)
        self.assertIs(self.permit["executionReady"], True)
        self.assertIs(self.summary["structurePreparationOnly"], False)
        self.assertIs(self.summary["executionReady"], True)

    def test_exact_final_decision_and_v10_fixed_point_pins(self) -> None:
        expected_raw_pins = {
            check.DECISION_PATH:
                "230d4329170a27fd27f8eef4c33337971441726837693526b732a4847a779c0a",
            check.DECISION_READER_PATH:
                "31036c0f25364c5f316c30a4541a6a649a13cdcc9952ec9df9cf2c94a1de5398",
            check.DECISION_CHECKER_PATH:
                "bb9d62377d676cc6de7678db6be8e64b6d65a088c4c508269fdd51f6f9ca9b53",
            check.DECISION_TESTS_PATH:
                "196fcdaf9a20a60d1b29b628492d1c3f0164805adc5df05678921437e7243def",
            check.V10_CHECKER_PATH:
                "11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985",
            check.V10_TESTS_PATH:
                "ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35",
        }
        self.assertEqual(
            {
                path: check.sha256((check.ROOT / path).read_bytes())
                for path in expected_raw_pins
            },
            expected_raw_pins,
        )
        decision_checker_raw = (
            check.ROOT / check.DECISION_CHECKER_PATH
        ).read_bytes()
        v10_checker_raw = (check.ROOT / check.V10_CHECKER_PATH).read_bytes()
        self.assertEqual(
            check.sha256(
                check.DECISION.normalized_self_bytes(decision_checker_raw)
            ),
            "b8702241e4455fb49d7bcae13857d6d3c2a4cad181390ecea8009d229e3d9051",
        )
        self.assertEqual(
            check.sha256(
                check.DECISION.normalized_self_bytes(v10_checker_raw)
            ),
            "ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751",
        )
        self.assertEqual(
            self.decision["contentBinding"]["sha256"],
            "9da32d6de84064039bce0438d75fb0ae7b5c9a22faff6b956c0e443f923a09a9",
        )
        predecessor = self.permit["predecessorBindings"][
            "combinedFixedPointV10"
        ]
        self.assertEqual(
            (
                predecessor["contentSha256"],
                predecessor["combinedInputSetSha256"],
                predecessor["sourceBindingsSha256"],
                predecessor["graphSha256"],
                predecessor["frontierSha256"],
            ),
            (
                "d7feddd3b291756c36359b013ea05aaa2f25cb83605daaeb493c0395ff9cc4f7",
                "f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be",
                "067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c",
                "77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4",
                "8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05",
            ),
        )
        self.assertEqual(
            (
                self.permit["identityBinding"]["compactIdentitySha256"],
                self.permit["identityBinding"]["fullWitnessSha256"],
                self.permit["identityBinding"]["heldSourceBindingsSha256"],
            ),
            (
                "23b6b188a88c5bdb87abe99325ec7a6d4580605ca69869f2614e36e134c07752",
                "2b13a602a2faf12ea2eb5f6d578a562033148ccded4035799756d969b96bdfa0",
                "067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c",
            ),
        )

    def test_exact_request_contract_and_no_authentication(self) -> None:
        self.assertEqual(len(self.rows), 8)
        self.assertEqual(
            [row["requestOrdinal"] for row in self.rows],
            list(range(1, 9)),
        )
        self.assertEqual(
            [row["kind"] for row in self.rows],
            ["mod", "zip"] * 4,
        )
        self.assertEqual(
            [
                row["requestOrdinal"]
                for row in self.rows
                if row["selectedByGraphAlgorithm"]
            ],
            [],
        )
        self.assertEqual(
            self.permit["requestContract"][
                "sourceRequestSetCanonicalSha256"
            ],
            "6531872e99da0c94746cbdb53fe9f5302ebc71bc82bfde1705b5e2300b2a2ee5",
        )
        source_requests = self.decision[
            "sourceAcquisitionPreparation"
        ]["requestSet"]
        self.assertEqual(
            check.sha256(check.digest_bytes(source_requests)),
            "6531872e99da0c94746cbdb53fe9f5302ebc71bc82bfde1705b5e2300b2a2ee5",
        )
        self.assertNotEqual(
            check.sha256(check.canonical_bytes(source_requests)),
            "6531872e99da0c94746cbdb53fe9f5302ebc71bc82bfde1705b5e2300b2a2ee5",
        )
        self.assertEqual(
            self.permit["requestContract"]["resourcesCanonicalSha256"],
            "c8ca9bc4559bea59a5a52fbceaaf068fe82ab9211fa0a888d3918aaa2dec55a2",
        )
        self.assertEqual(
            self.permit["oneUseContract"]["existingClaimState"],
            "already_consumed",
        )

    def test_four_modules_remain_distinct_exact_tuples(self) -> None:
        identities = {
            (row["module"], row["version"]): (
                row["goModH1"],
                row["moduleZipH1"],
            )
            for row in self.decision["identityResolution"]["tuples"]
        }
        self.assertEqual(
            set(identities),
            {
                ("golang.org/x/crypto", "v0.41.0"),
                ("golang.org/x/term", "v0.34.0"),
                ("golang.org/x/text", "v0.28.0"),
                ("golang.org/x/tools", "v0.35.0"),
            },
        )
        self.assertEqual(len({module for module, _ in identities}), 4)
        self.assertEqual(len(set(identities.values())), 4)
        projected = self.rows[::2]
        self.assertEqual(len({row["tupleId"] for row in projected}), 4)
        self.assertEqual(
            len({(row["module"], row["version"]) for row in projected}),
            4,
        )

    def test_exact_invocation_contract_and_mutations_fail_closed(self) -> None:
        expected = {
            "canonicalDirectCommand": [
                "/Applications/Xcode.app/Contents/Developer/usr/bin/python3",
                "-I",
                "-B",
                "-S",
                check.RUNNER_PATH,
                "--execute",
            ],
            "canonicalDirectCommandExclusive": False,
            "cwd": "repository_root",
            "interpreterAbsolutePath": (
                "/Applications/Xcode.app/Contents/Developer/usr/bin/python3"
            ),
            "runnerPath": check.RUNNER_PATH,
            "exactArgv": ["--execute"],
            "additionalArgumentsAllowed": False,
            "abbreviatedArgumentsAllowed": False,
            "duplicateArgumentsAllowed": False,
            "testSeamMayDispatchExecution": False,
            "executionEntryPointRevalidatesInvocationShape": True,
            "exactKernelArgv": [
                (
                    "/Applications/Xcode.app/Contents/Developer/Library/"
                    "Frameworks/Python3.framework/Versions/3.9/Resources/"
                    "Python.app/Contents/MacOS/Python"
                ),
                "-I",
                "-B",
                "-S",
                check.RUNNER_PATH,
                "--execute",
            ],
            "kernelExecutableAbsolutePath": (
                "/Applications/Xcode.app/Contents/Developer/Library/"
                "Frameworks/Python3.framework/Versions/3.9/Resources/"
                "Python.app/Contents/MacOS/Python"
            ),
            "kernelArgvSource": "macos_sysctl_kern_procargs2",
            "kernelArgvRevalidatedBeforePreflight": True,
            "pythonInvocationStatePurpose": (
                "accidental_misconfiguration_guard_only"
            ),
            "kernelArgvPurpose": (
                "accidental_misconfiguration_guard_only"
            ),
            "localSameUserProcessTrusted": True,
            "sameProcessWrapperWithinTrustBoundary": True,
            "invocationChecksAuthenticateOrigin": False,
            "invocationOriginAttestationProvided": False,
            "externalLauncherReceiptRequired": False,
        }
        self.assertEqual(self.permit["invocationContract"], expected)
        self.assertIn(
            (
                "the Python-state and kernel-argv checks guard accidental "
                "misconfiguration and do not authenticate invocation origin"
            ),
            self.permit["nonClaims"],
        )
        self.assertIn(
            (
                "no invocation-origin attestation or external launcher "
                "receipt is provided or required"
            ),
            self.permit["nonClaims"],
        )
        check.validate_invocation_contract(self.permit)
        mutations = (
            lambda value: value["invocationContract"][
                "canonicalDirectCommand"
            ]
            .__setitem__(0, "/usr/bin/python3"),
            lambda value: value["invocationContract"][
                "canonicalDirectCommand"
            ]
            .__setitem__(-1, "--exec"),
            lambda value: value["invocationContract"][
                "canonicalDirectCommand"
            ].append("--execute"),
            lambda value: value["invocationContract"][
                "canonicalDirectCommand"
            ].append("--extra"),
            lambda value: value["invocationContract"][
                "canonicalDirectCommand"
            ].pop(),
            lambda value: value["invocationContract"].__setitem__(
                "canonicalDirectCommandExclusive",
                True,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "cwd",
                ".",
            ),
            lambda value: value["invocationContract"].__setitem__(
                "exactArgv",
                ["--exec"],
            ),
            lambda value: value["invocationContract"].__setitem__(
                "additionalArgumentsAllowed",
                True,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "abbreviatedArgumentsAllowed",
                True,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "duplicateArgumentsAllowed",
                True,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "testSeamMayDispatchExecution",
                True,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "executionEntryPointRevalidatesInvocationShape",
                False,
            ),
            lambda value: value["invocationContract"]["exactKernelArgv"]
            .__setitem__(0, "/usr/bin/python3"),
            lambda value: value["invocationContract"]["exactKernelArgv"]
            .append("-c"),
            lambda value: value["invocationContract"].__setitem__(
                "kernelExecutableAbsolutePath",
                "/usr/bin/python3",
            ),
            lambda value: value["invocationContract"].__setitem__(
                "kernelArgvSource",
                "mutable_python_state",
            ),
            lambda value: value["invocationContract"].__setitem__(
                "kernelArgvRevalidatedBeforePreflight",
                False,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "pythonInvocationStatePurpose",
                "origin_authentication",
            ),
            lambda value: value["invocationContract"].__setitem__(
                "kernelArgvPurpose",
                "origin_authentication",
            ),
            lambda value: value["invocationContract"].__setitem__(
                "localSameUserProcessTrusted",
                False,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "sameProcessWrapperWithinTrustBoundary",
                False,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "invocationChecksAuthenticateOrigin",
                True,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "invocationOriginAttestationProvided",
                True,
            ),
            lambda value: value["invocationContract"].__setitem__(
                "externalLauncherReceiptRequired",
                True,
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.permit)
                mutation(changed)
                with self.assertRaises(check.CheckError) as caught:
                    check.validate_invocation_contract(changed)
                self.assertEqual(caught.exception.code, "E_INVOCATION")
        self.assertIs(
            self.permit["oneUseContract"][
                "claimAbsentAtPermitPublication"
            ],
            True,
        )
        self.assertEqual(
            self.permit["authority"],
            {
                "wave12PublicProxy8GetAcquisitionAuthorizedOnce": True,
                "dnsTcpTlsHttpsToExactProxyAuthorized": True,
                "sourceExtractionAuthorized": False,
                "sourceLoadOrExecutionAuthorized": False,
                "compileAuthorized": False,
                "packageManagerAuthorized": False,
                "subprocessAuthorized": False,
                "gitOperationAuthorized": False,
                "deviceAuthorized": False,
                "deploymentAuthorized": False,
                "productRuntimeNetworkAuthorized": False,
                "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized": False,
                "publicationAuthorized": False,
                "repositoryOwnerIdentityProofRequired": False,
                "accountRequired": False,
                "ownerRequired": False,
                "sshRequired": False,
                "gpgRequired": False,
                "externalAuthenticationRequired": False,
                "authenticationRequired": False,
                "passwordRequired": False,
                "privateKeyRequired": False,
                "signatureRequired": False,
                "tokenRequired": False,
                "cookieRequired": False,
                "clientCertificateRequired": False,
                "userActionRequired": False,
            },
        )
        true_authority = {
            "wave12PublicProxy8GetAcquisitionAuthorizedOnce",
            "dnsTcpTlsHttpsToExactProxyAuthorized",
        }
        self.assertNotIn("socketAuthorized", self.permit["authority"])
        for key, value in self.permit["authority"].items():
            self.assertIs(value, key in true_authority)
        self.assertFalse(
            self.permit["authority"]["externalAuthenticationRequired"]
        )
        self.assertFalse(
            self.permit["authority"]["repositoryOwnerIdentityProofRequired"]
        )
        self.assertFalse(self.permit["authority"]["passwordRequired"])
        self.assertFalse(self.permit["authority"]["privateKeyRequired"])
        self.assertFalse(self.permit["authority"]["signatureRequired"])
        self.assertFalse(self.permit["authority"]["tokenRequired"])
        self.assertFalse(self.permit["authority"]["userActionRequired"])
        self.assertFalse(
            self.permit["requestContract"]["authenticationAllowed"]
        )
        identity_rows = self.decision["identityResolution"]["tuples"]
        self.assertEqual(
            [
                (
                    row["module"],
                    row["version"],
                    row["selectedByGraphAlgorithm"],
                    row["goModH1"],
                    row["moduleZipH1"],
                )
                for row in identity_rows
            ],
            list(EXPECTED_WAVE12_IDENTITIES),
        )
        for tuple_order, (identity, expected) in enumerate(
            zip(identity_rows, EXPECTED_WAVE12_IDENTITIES),
            1,
        ):
            mod, archive = self.rows[(tuple_order - 1) * 2:tuple_order * 2]
            module, version, selected, mod_h1, zip_h1 = expected
            self.assertIs(identity["selectedByGraphAlgorithm"], selected)
            self.assertIs(mod["selectedByGraphAlgorithm"], selected)
            self.assertIs(archive["selectedByGraphAlgorithm"], selected)
            self.assertEqual(
                (
                    mod["requestOrdinal"],
                    archive["requestOrdinal"],
                    mod["tupleOrder"],
                    archive["tupleOrder"],
                    mod["module"],
                    archive["module"],
                    mod["version"],
                    archive["version"],
                    mod["kind"],
                    archive["kind"],
                    mod["expectedH1"],
                    archive["expectedH1"],
                ),
                (
                    tuple_order * 2 - 1,
                    tuple_order * 2,
                    tuple_order,
                    tuple_order,
                    module,
                    module,
                    version,
                    version,
                    "mod",
                    "zip",
                    mod_h1,
                    zip_h1,
                ),
            )
            self.assertEqual(mod["expectedH1"], identity["goModH1"])
            self.assertEqual(archive["expectedH1"], identity["moduleZipH1"])
        self.assertEqual(
            [row["kind"] for row in self.rows],
            ["mod", "zip"] * len(EXPECTED_WAVE12_IDENTITIES),
        )
        self.assertEqual(
            len({row["url"] for row in self.rows}),
            8,
        )
        self.assertEqual(
            len({row["acceptedFileName"] for row in self.rows}),
            8,
        )
        self.assertEqual(
            (self.rows[0]["tupleId"], self.rows[-1]["tupleId"]),
            (
                "wave12-001-799bf8d6fecb",
                "wave12-004-a1d2779b41be",
            ),
        )

    def test_portfolio_caps_and_stale_wave_markers_are_pinned(self) -> None:
        limits = self.permit["absoluteResourceLimits"]
        self.assertEqual(limits["maximumRequestCount"], 8)
        self.assertEqual(
            limits["maximumAggregateModResponseBodyBytes"],
            8 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateZipResponseBodyBytes"],
            128 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateResponseBodyBytes"],
            128 * 1024 * 1024,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "heldRootRelativeComponentTraversalRequired"
            ],
            True,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "intermediateDirectoryIdentityHeldThroughExecution"
            ],
            True,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "localFdOwnershipTransferAndCloseCleanupDefersOnlySigalrmAndSigint"
            ],
            True,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "closeCleanupCompletesBeforePriorSignalMaskRestoration"
            ],
            True,
        )
        for key in (
            "claimCreationAttemptRecordedBeforeExclusiveCreate",
            "claimCreationMayHaveConsumedDefaultsTrueUntilDefinitiveNotCreated",
            "baseExceptionAfterExclusiveCreateFailsClosedAsClaimStateUncertain",
            "postCreatePreAssignmentInterruptionTreatedAsConsumedPossible",
            "preAssignmentInterruptionClosesUnboundHeldEntry",
            "knownExistingClaimPreservesAlreadyConsumedClassification",
            "fileExistsObservedBeforeUnmaskPreservesKnownConsumed",
            "fileExistsObservedOverridesUnmaskAcquisitionError",
            "restoreFailureAfterKnownConsumedIsConsumedUncertain",
            "knownConsumedSurvivesNamespaceOrAuthorityTeardownError",
        ):
            self.assertIs(self.permit["oneUseContract"][key], True)
        self.assertIs(
            limits["callerBlockedSigalrmRejectedBeforePreflight"],
            True,
        )
        self.assertIs(
            limits["sigalrmUnblockedDuringFetchValidationWriteAndFsync"],
            True,
        )
        self.assertIs(
            limits[
                "originalSignalMaskRestoredExactlyOrUncertaintyReported"
            ],
            True,
        )
        self.assertIs(
            limits[
                "pendingInstalledSigalrmSynchronouslyConsumedBeforePriorHandlerRestoration"
            ],
            True,
        )
        self.assertIs(
            limits[
                "pendingSigalrmDrainFailureContainedWithoutPriorAlarmStateRestoration"
            ],
            True,
        )
        self.assertIs(
            limits["priorHandlerRestoredBeforePriorTimerArmed"],
            True,
        )
        self.assertIs(
            self.permit["terminalContract"][
                "failureOperationCountsAreCommittedLowerBounds"
            ],
            True,
        )
        self.assertEqual(
            self.permit["terminalContract"][
                "zeroCommittedResponsesWithActiveFetchState"
            ],
            "unknown_after_dispatch",
        )
        self.assertEqual(
            self.permit["terminalContract"][
                "terminalTeardownUncertaintyFailureCode"
            ],
            "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
        )
        self.assertEqual(
            self.permit["decisionBinding"]["files"],
            check._decision_package_bindings(),
        )
        self.assertEqual(
            [row["path"] for row in self.permit["decisionBinding"]["files"]],
            [
                check.DECISION_PATH,
                check.DECISION_READER_PATH,
                check.DECISION_CHECKER_PATH,
                check.DECISION_TESTS_PATH,
            ],
        )
        predecessor = self.permit["predecessorBindings"][
            "combinedFixedPointV10"
        ]
        self.assertEqual(
            (predecessor["checkerPath"], predecessor["testsPath"]),
            (check.V10_CHECKER_PATH, check.V10_TESTS_PATH),
        )
        for path in (
            check.THIS_CHECKER_PATH,
            check.THIS_TESTS_PATH,
            check.RUNNER_PATH,
            check.RUNNER_TESTS_PATH,
            check.PERMIT_READER_PATH,
            check.PERMIT_PATH,
        ):
            source = (check.ROOT / path).read_text(encoding="utf-8")
            self.assertNotIn("wave" + "11", source.casefold())
            self.assertNotIn("wave-" + "11", source.casefold())
            self.assertNotIn("1" + "8-resource", source)
            self.assertNotIn("requestCount\"] == " + "18", source)
            self.assertNotIn('"requestCount": ' + "18", source)
            self.assertNotIn('"tupleCount": ' + "9", source)
            self.assertNotIn(
                "bbde21b5" + "f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8",
                source,
            )
            self.assertNotIn(
                "9b317cf5" + "32f33691bb13b5f7dfa26e06cbc56cf10bb62e306afad73dd069df74",
                source,
            )

    def test_resource_schema_mutations_fail_closed(self) -> None:
        for mutation in (
            lambda row: row.__setitem__("requestOrdinal", 2),
            lambda row: row.__setitem__("requestOrdinal", True),
            lambda row: row.__setitem__("tupleOrder", True),
            lambda row: row.__setitem__("resourceKind", "zip"),
            lambda row: row.__setitem__("method", "POST"),
            lambda row: row.__setitem__("host", "example.invalid"),
            lambda row: row.__setitem__("acquisitionAuthorized", True),
            lambda row: row.__setitem__("authenticationRequired", True),
            lambda row: row.__setitem__("networkAuthorized", True),
            lambda row: row.__setitem__("maximumResponseBytes", 3),
            lambda row: row.__setitem__("maximumResponseBytes", True),
            lambda row: row.__setitem__("url", row["url"] + "?x=1"),
            lambda row: row.__setitem__(
                "expectedH1",
                "h1:" + ("A" * 44),
            ),
            lambda row: row.__setitem__("acceptedFileName", "wrong.mod"),
            lambda row: row.__setitem__(
                "selectedByGraphAlgorithm",
                "false",
            ),
            lambda row: row.__setitem__("selectedByGraphAlgorithm", 1),
            lambda row: row.__setitem__("module", "a//b"),
            lambda row: row.__setitem__("module", "a/../b"),
            lambda row: row.__setitem__("module", "a/-b"),
            lambda row: row.__setitem__("module", "Example.com/a"),
            lambda row: row.__setitem__("version", "v1.0.0-RC1"),
            lambda row: row.__setitem__("unexpected", False),
            lambda row: row.pop("host"),
        ):
            source = copy.deepcopy(
                self.decision["sourceAcquisitionPreparation"]["requestSet"]
            )
            mutation(source[0])
            with self.assertRaises(check.CheckError):
                check._normalize_request_rows(source)
        for mutation in (
            lambda rows: rows.pop(),
            lambda rows: rows.append(copy.deepcopy(rows[-1])),
            lambda rows: rows.reverse(),
        ):
            source = copy.deepcopy(
                self.decision["sourceAcquisitionPreparation"]["requestSet"]
            )
            mutation(source)
            with self.assertRaises(check.CheckError):
                check._normalize_request_rows(source)
        changed = copy.deepcopy(self.decision)
        changed["sourceAcquisitionPreparation"]["requestCount"] = False
        with self.assertRaises(check.CheckError):
            check.normalized_resources(changed)

    def test_every_source_request_field_is_exactly_bound_on_all_8_rows(
        self,
    ) -> None:
        original = self.decision[
            "sourceAcquisitionPreparation"
        ]["requestSet"]
        for index, original_row in enumerate(original):
            for key in original_row:
                with self.subTest(request_ordinal=index + 1, key=key):
                    changed = copy.deepcopy(self.decision)
                    changed[
                        "sourceAcquisitionPreparation"
                    ]["requestSet"][index][key] = None
                    with self.assertRaises(check.CheckError):
                        check.normalized_resources(changed)

    def test_lower_ascii_direct_proxy_identity_is_enforced(self) -> None:
        def rewritten_pair(module: str, version: str):
            source = copy.deepcopy(
                self.decision["sourceAcquisitionPreparation"]["requestSet"]
            )
            digest = check.sha256(f"{module}\n{version}\n".encode())
            for index, kind in enumerate(("mod", "zip")):
                source[index]["module"] = module
                source[index]["version"] = version
                source[index]["url"] = (
                    f"https://{check.PROXY_HOST}/{module}/@v/"
                    f"{version}.{kind}"
                )
                source[index]["acceptedFileName"] = (
                    f"001-{digest[:20]}.{kind}"
                )
            return source

        self.assertEqual(
            len(
                check._normalize_request_rows(
                    rewritten_pair(
                        "example.com/dependency",
                        "v1.0.0-rc1",
                    )
                )
            ),
            8,
        )
        for module, version in (
            ("Example.com/dependency", "v1.0.0-rc1"),
            ("example.com/dependency", "v1.0.0-RC1"),
        ):
            with self.subTest(module=module, version=version):
                with self.assertRaises(check.CheckError):
                    check._normalize_request_rows(
                        rewritten_pair(module, version)
                    )

    def test_runner_reverse_pin_and_normalized_hash_fail_closed(self) -> None:
        runner_raw = (check.ROOT / check.RUNNER_PATH).read_bytes()
        checker_raw = (check.ROOT / check.THIS_CHECKER_PATH).read_bytes()
        check.validate_runner(runner_raw, checker_raw)
        reverse_mutation = runner_raw.replace(
            check.sha256(checker_raw).encode(),
            b"0" * 64,
            1,
        )
        with self.assertRaises(check.CheckError):
            check.validate_runner(reverse_mutation, checker_raw)
        body_mutation = runner_raw.replace(
            b"consumed_active",
            b"consumed_altered",
            1,
        )
        with self.assertRaises(check.CheckError):
            check.validate_runner(body_mutation, checker_raw)

    def test_strict_json_rejects_duplicates_and_noncanonical_is_separate(self) -> None:
        with self.assertRaises(check.CheckError):
            check.strict_json(b'{"a":1,"a":2}\n')
        value = {"b": 1, "a": 2}
        raw = check.canonical_bytes(value)
        self.assertEqual(check.strict_json(raw), value)
        self.assertNotEqual(raw, b'{"b":1,"a":2}\n')

    def test_runner_ast_has_no_ambient_network_or_subprocess_client(self) -> None:
        raw = (check.ROOT / check.RUNNER_PATH).read_bytes()
        source = raw.decode("utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        self.assertTrue(
            {"subprocess", "requests", "socket", "urllib.request"}
            .isdisjoint(imports)
        )
        self.assertNotIn("Authorization", source)
        self.assertNotIn("Proxy-Authorization", source)
        self.assertNotIn("Cookie", source)
        self.assertNotIn("def _stable(", source)
        self.assertIn("signal.pthread_sigmask", source)
        self.assertIn("directory_steps", source)
        self.assertIn("ImmutablePhaseLedger", source)
        self.assertIn("ProcessStateGuard", source)
        self.assertNotIn("ResourceOperationBoundary", source)

    def test_checker_uses_materialized_fast_path_without_graph_rerun(
        self,
    ) -> None:
        source = (
            check.ROOT / check.THIS_CHECKER_PATH
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        self.assertTrue(
            {"socket", "subprocess", "urllib.request", "requests"}
            .isdisjoint(imports)
        )
        self.assertNotIn("DECISION" + ".evaluate", source)
        forbidden_name = "".join(("CAND", "IDATE_CHECKER_PATH"))
        self.assertNotIn(forbidden_name, source)
        self.assertNotIn('"wave12' + 'Candidate"', source)
        self.assertIn("DECISION.validate_materialized_decision", source)
        self.assertEqual(len(check._decision_package_bindings()), 4)

    def test_reserved_namespace_rejects_all_wave12_names(self) -> None:
        forbidden = (
            Path(check.CLAIM_PATH).name,
            Path(check.FINAL_ROOT).name,
            check.STAGING_PREFIX + "synthetic",
            Path(check.FINAL_ROOT).name.upper(),
        )
        for name in forbidden:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    namespace = root / check.DEPENDENCY_ROOT
                    namespace.mkdir(parents=True)
                    (namespace / name).write_bytes(b"occupied")
                    with self.assertRaises(check.CheckError):
                        check.HeldReservedNamespace(root)

    def test_terminal_namespace_rejects_broken_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / check.BASE
            base.mkdir(parents=True)
            os.symlink(
                "missing",
                base / Path(check.RECEIPT_PATH).name,
            )
            with self.assertRaises(check.CheckError):
                check.HeldTerminalNamespace(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / check.BASE
            base.mkdir(parents=True)
            (base / Path(check.RECEIPT_PATH).name.upper()).write_text(
                "casefold collision",
            )
            with self.assertRaises(check.CheckError):
                check.HeldTerminalNamespace(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / check.BASE).mkdir(parents=True)
            with mock.patch.object(
                check.os,
                "listdir",
                return_value=["\u00e9", "e\u0301"],
            ):
                with self.assertRaises(check.CheckError):
                    check.HeldTerminalNamespace(root)

    def test_terminal_namespace_partial_open_closes_owned_fds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / check.BASE).mkdir(parents=True)
            real_open = os.open
            real_close = os.close
            real_fstat = os.fstat
            opened: list[int] = []
            closed: list[int] = []
            fstat_calls = 0

            def tracked_open(*arguments, **keywords):
                fd = real_open(*arguments, **keywords)
                opened.append(fd)
                return fd

            def tracked_close(fd: int) -> None:
                closed.append(fd)
                real_close(fd)

            def failing_fstat(fd: int):
                nonlocal fstat_calls
                fstat_calls += 1
                if fstat_calls == 2:
                    raise OSError("synthetic terminal component failure")
                return real_fstat(fd)

            with mock.patch.object(
                check.os,
                "open",
                side_effect=tracked_open,
            ), mock.patch.object(
                check.os,
                "close",
                side_effect=tracked_close,
            ), mock.patch.object(
                check.os,
                "fstat",
                side_effect=failing_fstat,
            ):
                with self.assertRaises(OSError):
                    check.HeldTerminalNamespace(root)
            self.assertGreaterEqual(len(opened), 2)
            self.assertTrue(set(opened).issubset(set(closed)))
            for fd in opened:
                with self.assertRaises(OSError):
                    real_fstat(fd)

    def test_pinned_hardlink_and_terminal_root_rebind_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = "held/input.bin"
            target = root / relative
            target.parent.mkdir()
            target.write_bytes(b"held")
            os.link(target, target.with_name("alias.bin"))
            with self.assertRaises(check.DECISION.DecisionFailure):
                check.DECISION.BootstrapPinnedCodeFile(
                    root,
                    relative,
                    check.sha256(b"held"),
                )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "root"
            (root / check.BASE).mkdir(parents=True)
            held = check.HeldTerminalNamespace(root)
            displaced = base / "displaced"
            root.rename(displaced)
            (root / check.BASE).mkdir(parents=True)
            try:
                with self.assertRaises(check.CheckError):
                    held.final_barrier()
            finally:
                held.close()

    def test_content_binding_is_reproducible(self) -> None:
        payload = check.content_bound({"z": 1, "a": [2]})
        without = dict(payload)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            check.sha256(check.canonical_bytes(without)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
