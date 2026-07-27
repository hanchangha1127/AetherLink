#!/usr/bin/env python3
"""Tests for the Wave8 acquisition permit checker."""

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
    raise RuntimeError("Wave8 acquisition tests require `python3 -I -B -S`")

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave8_acquisition_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave8_acquisition_permit_v1",
    CHECKER_PATH,
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

EXPECTED_WAVE8_IDENTITIES = (
    (
        "github.com/davecgh/go-spew",
        "v1.1.0",
        "h1:J7Y8YcW2NihsgmVo/mv3lAwl/skON4iLHjSsI+c5H38=",
        "h1:ZDRjVQ15GmhC3fiQ8ni8+OwkZQO4DARzQgrnXU1Liz8=",
    ),
    (
        "github.com/stretchr/objx",
        "v0.1.0",
        "h1:HFkY916IF+rwdDfMAkV7OtwuqBVzrE8GR6GFx+wExME=",
        "h1:4G4v2dO3VZwixGIRoQ5Lfboy6nUhCyYzaqnIAPPhYs4=",
    ),
    (
        "golang.org/x/crypto",
        "v0.43.0",
        "h1:BFbav4mRNlXJL4wNeejLpWxB7wMbc79PdRGhWKncxR0=",
        "h1:dduJYIi3A3KOfdGOHX8AVZ/jGiyPa3IbBozJ5kNuE04=",
    ),
    (
        "golang.org/x/mod",
        "v0.6.0-dev.0.20220419223038-86c51ed26bb4",
        "h1:jJ57K6gSWd91VN4djpZkiMVwK6gcyfeH4XE8wZrZaV4=",
        "h1:6zppjxzCulZykYSLyVDYbneBfbaBIQPYMevg0bEwv2s=",
    ),
    (
        "golang.org/x/net",
        "v0.0.0-20220722155237-a158d28d115b",
        "h1:XRhObCWvk6IyKnWLug+ECip1KBveYUHfp+8e9klMJ9c=",
        "h1:PxfKdU9lEEDYjdIzOtC4qFWgkU2rGHdKlKowJSMN9h0=",
    ),
    (
        "golang.org/x/sync",
        "v0.0.0-20220722155255-886fb9371eb4",
        "h1:RxMgew5VJxzue5/jJTE5uejpjVlOe/izrB70Jof72aM=",
        "h1:uVc8UZUe6tr40fFVnUP5Oj+veunVezqYl9z7DYw9xzw=",
    ),
    (
        "golang.org/x/sys",
        "v0.0.0-20220722155257-8c9f86f7a55f",
        "h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=",
        "h1:v4INt8xihDGvnrfjMDVXGxw9wrfxYyCjk0KbXjhR55s=",
    ),
    (
        "golang.org/x/term",
        "v0.36.0",
        "h1:Qu394IJq6V6dCBRgwqshf3mPF85AqzYEzofzRdZkWss=",
        "h1:zMPR+aF8gfksFprF/Nc/rd1wRS1EI6nDBGyWAvDzx2Q=",
    ),
    (
        "golang.org/x/term",
        "v0.5.0",
        "h1:jMB1sMXY+tzblOD4FWmEbocvup2/aLOaQEp7JmGp78k=",
        "h1:n2a8QNdAb0sZNpU9R1ALUXBbY+w51fCQDN+7EdxNBsY=",
    ),
    (
        "golang.org/x/text",
        "v0.3.7",
        "h1:u+2+/6zg+i71rQMx5EYifcz6MCKuco9NR6JIITiCfzQ=",
        "h1:olpwvP2KacW1ZWvsR7uQhoyTYvKAupfQrRGBFM352Gk=",
    ),
    (
        "golang.org/x/text",
        "v0.30.0",
        "h1:yDdHFIX9t+tORqspjENWgzaCVXgk0yYnYuSZ8UzzBVM=",
        "h1:yznKA/E9zq54KzlzBEAWn1NXSQ8DIp/NYMy88xJjl4k=",
    ),
    (
        "golang.org/x/text",
        "v0.7.0",
        "h1:mrYo+phRRbMaCq/xk9113O4dZlRixOauAjOtrjsXDZ8=",
        "h1:4BRB4x83lYWy72KwLD/qYDuTu7q9PjSagHvijDw7cLo=",
    ),
    (
        "golang.org/x/tools",
        "v0.37.0",
        "h1:MBN5QPQtLMHVdvsbtarmTNukZDdgwdwlO5qGacAzF0w=",
        "h1:DVSRzp7FwePZW356yEAChSdNcQo6Nsp+fex1SUW09lE=",
    ),
    (
        "gopkg.in/yaml.v3",
        "v3.0.0-20200313102051-9f266ea9e77c",
        "h1:K4uyk7z7BCEPqu6E+C64Yfv1cQ7kz7rIZviUmN+EgEM=",
        "h1:dUUwHk2QECo/6vqA44rthZ8ie2QXMNeKRTHCNY2nXvo=",
    ),
)


class Wave8AcquisitionPermitTests(unittest.TestCase):
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

    def test_exact_request_contract_and_no_authentication(self) -> None:
        self.assertEqual(len(self.rows), 28)
        self.assertEqual(
            [row["requestOrdinal"] for row in self.rows],
            list(range(1, 29)),
        )
        self.assertEqual(
            [row["kind"] for row in self.rows],
            ["mod", "zip"] * 14,
        )
        self.assertEqual(
            sum(row["selectedByGraphAlgorithm"] for row in self.rows[::2]),
            0,
        )
        self.assertEqual(
            self.permit["requestContract"][
                "sourceRequestSetCanonicalSha256"
            ],
            "b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc",
        )
        source_requests = self.decision[
            "sourceAcquisitionPreparation"
        ]["requestSet"]
        self.assertEqual(
            check.sha256(check.digest_bytes(source_requests)),
            "b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc",
        )
        self.assertNotEqual(
            check.sha256(check.canonical_bytes(source_requests)),
            "b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc",
        )
        self.assertEqual(
            self.permit["requestContract"]["resourcesCanonicalSha256"],
            "ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136",
        )
        self.assertEqual(
            self.permit["oneUseContract"]["existingClaimState"],
            "already_consumed",
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
                "wave8PublicProxy28GetAcquisitionAuthorizedOnce": True,
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
            "wave8PublicProxy28GetAcquisitionAuthorizedOnce",
            "dnsTcpTlsHttpsToExactProxyAuthorized",
        }
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
                    row["goModH1"],
                    row["moduleZipH1"],
                )
                for row in identity_rows
            ],
            list(EXPECTED_WAVE8_IDENTITIES),
        )
        for tuple_order, (identity, expected) in enumerate(
            zip(identity_rows, EXPECTED_WAVE8_IDENTITIES),
            1,
        ):
            mod, archive = self.rows[(tuple_order - 1) * 2:tuple_order * 2]
            module, version, mod_h1, zip_h1 = expected
            self.assertIs(identity["selectedByGraphAlgorithm"], False)
            self.assertIs(mod["selectedByGraphAlgorithm"], False)
            self.assertIs(archive["selectedByGraphAlgorithm"], False)
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
            ["mod", "zip"] * len(EXPECTED_WAVE8_IDENTITIES),
        )
        self.assertEqual(
            len({row["url"] for row in self.rows}),
            28,
        )
        self.assertEqual(
            len({row["acceptedFileName"] for row in self.rows}),
            28,
        )
        self.assertEqual(
            (self.rows[0]["tupleId"], self.rows[-1]["tupleId"]),
            (
                "wave8-001-dc8e752ef190",
                "wave8-014-0af8d5321b46",
            ),
        )

    def test_portfolio_caps_and_stale_wave_markers_are_pinned(self) -> None:
        limits = self.permit["absoluteResourceLimits"]
        self.assertEqual(limits["maximumRequestCount"], 28)
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
            "combinedFixedPointV6"
        ]
        self.assertEqual(
            (predecessor["checkerPath"], predecessor["testsPath"]),
            (check.V6_CHECKER_PATH, check.V6_TESTS_PATH),
        )
        for path in (
            check.THIS_CHECKER_PATH,
            check.THIS_TESTS_PATH,
            check.RUNNER_PATH,
            check.RUNNER_TESTS_PATH,
            check.PERMIT_READER_PATH,
        ):
            source = (check.ROOT / path).read_text(encoding="utf-8")
            self.assertNotIn("wave" + "7", source.casefold())
            self.assertNotIn("wave-" + "7", source.casefold())
            self.assertNotIn("3" + "0-resource", source)
            self.assertNotIn("requestCount\"] == " + "30", source)
            self.assertNotIn('"requestCount": ' + "30", source)
            self.assertNotIn('"tupleCount": ' + "15", source)
            self.assertNotIn(
                "8fbabe69" + "d049992e28c687852686ae0ad28adce690443d61e335c903b87d0f48",
                source,
            )
            self.assertNotIn(
                "87568c0a" + "02360bc7eb289d422bd9173f563134253f3828465654cb94ae9bdcfd",
                source,
            )

    def test_resource_schema_mutations_fail_closed(self) -> None:
        for mutation in (
            lambda row: row.__setitem__("requestOrdinal", 2),
            lambda row: row.__setitem__("requestOrdinal", True),
            lambda row: row.__setitem__("resourceKind", "zip"),
            lambda row: row.__setitem__("authenticationRequired", True),
            lambda row: row.__setitem__("networkAuthorized", True),
            lambda row: row.__setitem__("maximumResponseBytes", 3),
            lambda row: row.__setitem__("maximumResponseBytes", True),
            lambda row: row.__setitem__("url", row["url"] + "?x=1"),
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
        ):
            source = copy.deepcopy(
                self.decision["sourceAcquisitionPreparation"]["requestSet"]
            )
            mutation(source[0])
            with self.assertRaises(check.CheckError):
                check._normalize_request_rows(source)
        changed = copy.deepcopy(self.decision)
        changed["sourceAcquisitionPreparation"]["requestCount"] = False
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
            28,
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
        self.assertNotIn('"wave8' + 'Candidate"', source)
        self.assertIn("DECISION.validate_materialized_decision", source)
        self.assertEqual(len(check._decision_package_bindings()), 4)

    def test_reserved_namespace_rejects_all_wave8_names(self) -> None:
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
