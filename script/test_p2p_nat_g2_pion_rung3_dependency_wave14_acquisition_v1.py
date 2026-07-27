#!/usr/bin/env python3
"""Tests for the Wave14 acquisition permit checker."""

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
    raise RuntimeError("Wave14 acquisition tests require `python3 -I -B -S`")

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
        "offline Wave14 tests must never create network connections"
    )


http.client.HTTPSConnection = _deny_test_network
socket.create_connection = _deny_test_network


CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave14_acquisition_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave14_acquisition_permit_v1",
    CHECKER_PATH,
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

EXPECTED_WAVE14_IDENTITIES = (
    (
        "golang.org/x/crypto",
        "v0.40.0",
        False,
        "h1:Qr1vMER5WyS2dfPHAlsOj01wgLbsyWtFn/aY+5+ZdxY=",
        "h1:r4x+VvoG5Fm+eJcxMaY8CQM7Lb0l1lsmjGBQ6s8BfKM=",
    ),
    (
        "golang.org/x/term",
        "v0.33.0",
        False,
        "h1:s18+ql9tYWp1IfpV9DmCtQDDSRBUjKaw9M1eAv5UeF0=",
        "h1:NuFncQrRcaRvVmgRkvM3j/F00gWIAlcmlB8ACEKmGIg=",
    ),
    (
        "golang.org/x/text",
        "v0.27.0",
        False,
        "h1:1D28KMCvyooCX9hBiosv5Tz/+YLxj0j7XhWjpSUF7CU=",
        "h1:4fGWRpyh641NLlecmyl4LOe6yDdfaYNrGb2zdfo4JV4=",
    ),
    (
        "golang.org/x/tools",
        "v0.34.0",
        False,
        "h1:pAP9OwEaY1CAW3HOmg3hLZC5Z0CCmzjAF2UQMSqNARg=",
        "h1:qIpSLOxeCYGg9TrcJokLBG4KFA6d795g0xkBkiESGlo=",
    ),
)


def _normalized_v12_self_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    if start < 0 or raw.find(marker, start + len(marker)) >= 0:
        raise AssertionError("V12 checker self marker is not unique")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    if payload_end - payload_start != 64:
        raise AssertionError("V12 checker self marker is malformed")
    return raw[:payload_start] + (b"0" * 64) + raw[payload_end:]


class Wave14AcquisitionPermitTests(unittest.TestCase):
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

    def test_exact_final_decision_and_v12_fixed_point_pins(self) -> None:
        expected_raw_pins = {
            check.DECISION_PATH:
                "14d6debddca620af7f628198f7a7ae2d9291adc35a6fffbe13873d3fd75dc28f",
            check.DECISION_READER_PATH:
                "0d909c39aaf81a90c51803ad28839828e6b1df2060e7c347c34bdecda7587cce",
            check.DECISION_CHECKER_PATH:
                "eec92c7e557119b6eef79dd08069c0e99e0c75f9c7e1b42f5c00ff2d6696eee6",
            check.DECISION_TESTS_PATH:
                "155fed39113bb3a40e085efde1517409fba22a98e175094cee9edeefd7f380b3",
            check.V12_CHECKER_PATH:
                "cc693cb0126267962813a418a53ece371aec0172d24a75ea70cf6dbe89a1db45",
            check.V12_TESTS_PATH:
                "43dea4e06f07a304b620f33cf9aa647e39839dc5365705756fa10433e9bd60bd",
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
        v12_checker_raw = (check.ROOT / check.V12_CHECKER_PATH).read_bytes()
        self.assertEqual(
            check.sha256(
                check.DECISION.normalized_self_bytes(decision_checker_raw)
            ),
            "274cdb31412fcf56079f65a5ffd9c28a3267380846de12ff2910a8bd12885639",
        )
        self.assertEqual(
            check.sha256(
                _normalized_v12_self_bytes(v12_checker_raw)
            ),
            "cfcf095861bd753e3cfb7521e339e2bb5a3e59b5a75258ff5b8ee5cfc8ba43f2",
        )
        self.assertEqual(
            self.decision["contentBinding"]["sha256"],
            "cb4201b1d0e6fd4ae2275cf5a58ceedd0ca14e33cb6af4269e798f1115f37450",
        )
        predecessor = self.permit["predecessorBindings"][
            "combinedFixedPointV12"
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
                "176f5802b4bb56a6136f930a02ddd648774416945984af04bae4438de4e2bc17",
                "656dcf1c1e94b09649041fa6d99b0db1d3997914dc40eba5e7ca840b35b9760d",
                "bf043a07c5fa6d26f28de9954b8f676e583f625ccf28ca5a39d6fe23c6678592",
                "0ab3b47d6b4fc628a3bf83e648308591c84ddce8ad46ce8f8d6aca1797cf1e26",
                "a149da341952b398d71c9a9395cb18aac2c711bb8a8d72e1eb53ca710377df63",
            ),
        )
        self.assertEqual(
            (
                predecessor["v11TestsBindingScope"],
                predecessor["v11TestsLiveHeld"],
                predecessor["wave13NamespaceAnchor"],
            ),
            (
                "historical_metadata_only_not_live_held",
                False,
                {
                    "path": check.NAMESPACE_ANCHOR_PATH,
                    "rawSha256": check.NAMESPACE_ANCHOR_RAW_SHA256,
                },
            ),
        )
        held = self.decision["heldSourceInputSet"]
        self.assertEqual(
            (
                held["sourceBindingCount"],
                held["archiveCount"],
                held["externalModCount"],
                held["embeddedRootGoModCount"],
                held["goSumEntryCount"],
            ),
            (333, 167, 166, 1, 116),
        )
        counters = self.decision["operationCounters"]
        self.assertEqual(
            (
                counters["totalFullSourceReconstructionCount"],
                counters["totalV12GraphArchiveOpenCount"],
                counters["overallDecisionExecutionArchiveOpenCount"],
            ),
            (22, 2_644, 2_978),
        )
        self.assertEqual(
            (
                self.permit["identityBinding"]["compactIdentitySha256"],
                self.permit["identityBinding"]["fullWitnessSha256"],
                self.permit["identityBinding"]["heldSourceBindingsSha256"],
            ),
            (
                "a59b37276b85f5da5cbf2c39a560c7834582cf1f590e050d53e016ed80fb6185",
                "cf39e4c68e001b3d687df829e7d7903d4ebea69b11ee60f21d5385f9591fa542",
                "bf043a07c5fa6d26f28de9954b8f676e583f625ccf28ca5a39d6fe23c6678592",
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
            "505587c90ec32b1dea879b1e034450de091874a2ff9db9993532f1b14d9dc3aa",
        )
        source_requests = self.decision[
            "sourceAcquisitionPreparation"
        ]["requestSet"]
        self.assertEqual(
            check.sha256(check.digest_bytes(source_requests)),
            "505587c90ec32b1dea879b1e034450de091874a2ff9db9993532f1b14d9dc3aa",
        )
        self.assertNotEqual(
            check.sha256(check.canonical_bytes(source_requests)),
            "505587c90ec32b1dea879b1e034450de091874a2ff9db9993532f1b14d9dc3aa",
        )
        self.assertEqual(
            self.permit["requestContract"]["resourcesCanonicalSha256"],
            "ba1741c181b834c42c2501232fc8d99e5dfae3e02fb1d927fdb56f3248d20b6e",
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
                ("golang.org/x/crypto", "v0.40.0"),
                ("golang.org/x/term", "v0.33.0"),
                ("golang.org/x/text", "v0.27.0"),
                ("golang.org/x/tools", "v0.34.0"),
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
                "wave14PublicProxy8GetAcquisitionAuthorizedOnce": True,
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
            "wave14PublicProxy8GetAcquisitionAuthorizedOnce",
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
            list(EXPECTED_WAVE14_IDENTITIES),
        )
        for tuple_order, (identity, expected) in enumerate(
            zip(identity_rows, EXPECTED_WAVE14_IDENTITIES),
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
            ["mod", "zip"] * len(EXPECTED_WAVE14_IDENTITIES),
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
                "wave14-001-6ade739bf483",
                "wave14-004-b142b05fc3ea",
            ),
        )

    def test_portfolio_caps_and_stale_wave_markers_are_pinned(self) -> None:
        limits = self.permit["absoluteResourceLimits"]
        zip_limits = self.permit["zipLimits"]
        self.assertEqual(limits["maximumRequestCount"], 8)
        self.assertEqual(
            limits["maximumAggregateModResponseBodyBytes"],
            4 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateZipResponseBodyBytes"],
            64 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateResponseBodyBytes"],
            68 * 1024 * 1024,
        )
        self.assertEqual(
            zip_limits["maximumEntryCountAcrossAllZips"],
            80_000,
        )
        self.assertEqual(
            zip_limits["maximumUncompressedBytesAcrossAllZips"],
            512 * 1024 * 1024,
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
            "combinedFixedPointV12"
        ]
        self.assertEqual(
            (predecessor["checkerPath"], predecessor["testsPath"]),
            (check.V12_CHECKER_PATH, check.V12_TESTS_PATH),
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
            self.assertNotIn("wave" + "12", source.casefold())
            self.assertNotIn("wave-" + "12", source.casefold())
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
        self.assertNotIn('"wave14' + 'Candidate"', source)
        self.assertIn("DECISION.validate_materialized_decision", source)
        self.assertEqual(len(check._decision_package_bindings()), 4)

    def test_reserved_namespace_rejects_all_wave14_names(self) -> None:
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
