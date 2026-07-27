#!/usr/bin/env python3
"""Tests for the Wave15 acquisition permit checker."""

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
    raise RuntimeError("Wave15 acquisition tests require `python3 -I -B -S`")

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
        "offline Wave15 tests must never create network connections"
    )


http.client.HTTPSConnection = _deny_test_network
socket.create_connection = _deny_test_network


CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave15_acquisition_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave15_acquisition_permit_v1",
    CHECKER_PATH,
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

EXPECTED_WAVE15_IDENTITIES = (
    (
        "golang.org/x/mod",
        "v0.25.0",
        False,
        "h1:IXM97Txy2VM4PJ3gI61r1YEk/gAj6zAHN3AdZt6S9Ww=",
        "h1:n7a+ZbQKQA/Ysbyb0/6IbB1H/X41mKgbhfv7AfG/44w=",
    ),
    (
        "golang.org/x/net",
        "v0.41.0",
        False,
        "h1:B/K4NNqkfmg07DQYrbwvSluqCJOOXwUjeb/5lOisjbA=",
        "h1:vBTly1HeNPEn3wtREYfy4GZ/NECgw2Cnl+nK6Nz3uvw=",
    ),
    (
        "golang.org/x/sync",
        "v0.15.0",
        False,
        "h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=",
        "h1:KWH3jNZsfyT6xfAfKiz6MRNmd46ByHDYaZ7KSkCtdW8=",
    ),
    (
        "golang.org/x/sys",
        "v0.33.0",
        False,
        "h1:BJP2sWEmIv4KK5OTEluFJCKSidICx8ciO85XgH3Ak8k=",
        "h1:q3i8TbbEz+JRD9ywIRlyRAQbM0qF7hu24q3teo2hbuw=",
    ),
    (
        "golang.org/x/telemetry",
        "v0.0.0-20240521205824-bda55230c457",
        False,
        "h1:pRgIJT+bRLFKnoM1ldnzKoxTIn14Yxz928LQRYYgIN0=",
        "h1:zf5N6UOrA487eEFacMePxjXAJctxKmyjKUsjA11Uzuk=",
    ),
)

EXPECTED_WAVE15_RESOURCE_NAMES = (
    (
        "wave15-001-5aede784ca07",
        "001-5aede784ca073b95cc80.mod",
        "001-5aede784ca073b95cc80.zip",
    ),
    (
        "wave15-002-2a401d22df12",
        "002-2a401d22df127014c8ff.mod",
        "002-2a401d22df127014c8ff.zip",
    ),
    (
        "wave15-003-a5add74f06b2",
        "003-a5add74f06b2f0c08dac.mod",
        "003-a5add74f06b2f0c08dac.zip",
    ),
    (
        "wave15-004-5e519f9381da",
        "004-5e519f9381da4b6cb760.mod",
        "004-5e519f9381da4b6cb760.zip",
    ),
    (
        "wave15-005-e5b8406e7a0c",
        "005-e5b8406e7a0cdff66df0.mod",
        "005-e5b8406e7a0cdff66df0.zip",
    ),
)


def _normalized_v13_self_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    if start < 0 or raw.find(marker, start + len(marker)) >= 0:
        raise AssertionError("V13 checker self marker is not unique")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    if payload_end - payload_start != 64:
        raise AssertionError("V13 checker self marker is malformed")
    return raw[:payload_start] + (b"0" * 64) + raw[payload_end:]


class Wave15AcquisitionPermitTests(unittest.TestCase):
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

    def test_exact_final_decision_and_v13_fixed_point_pins(self) -> None:
        expected_raw_pins = {
            check.DECISION_PATH:
                "73638ba5aaaad61d146e0b884e71de9609ccddf870cf81c2c01bb42c2bccee19",
            check.DECISION_READER_PATH:
                "227a8c54a9f16881caab3d66193d12e9d03770a0e7bc7de1abb486d8cd698318",
            check.DECISION_CHECKER_PATH:
                "e6d37beea87041149bc4e79e6e7c7a238c48ff48075c0eedfb250a24006bb3c3",
            check.DECISION_TESTS_PATH:
                "31e90bdc46760f48d1c04be1993de27442662b11c02701ecf5b4f7d6d5220bc3",
            check.V13_CHECKER_PATH:
                "0b0ea7d68ef5fc11b8c0defe56bf443c681a6952a27e2c9b6c41d9702241a80b",
            check.V13_TESTS_PATH:
                "dffb5e24cfd2ba4c561f5e8c6302c4502a75f917c1ac9d15216fd7f2ac045327",
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
        v13_checker_raw = (check.ROOT / check.V13_CHECKER_PATH).read_bytes()
        self.assertEqual(
            check.sha256(
                check.DECISION.normalized_self_bytes(decision_checker_raw)
            ),
            "598ca5a9bbbf00ebbbe44a8d7ea7c9707b6f0ba3c99d1a80c7f9fa5e72469a4d",
        )
        self.assertEqual(
            check.sha256(
                _normalized_v13_self_bytes(v13_checker_raw)
            ),
            "73a778e53bdc1d15ffd34109ff02297e85eb6a91b52d1577acefe9bc1383e674",
        )
        self.assertEqual(
            self.decision["contentBinding"]["sha256"],
            "1d574152a913b067508260828f355a596fa82f5e8657c560229951f13e01b6c0",
        )
        predecessor = self.permit["predecessorBindings"][
            "combinedFixedPointV13"
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
                "e1f711b558642ad2167da48f25184cd4c3235314c67f06a60cfd14ceecea1988",
                "285cfb3e8b4a73beffa551429058611a606b00ad447d75599c77fb18895a2f91",
                "fbd023d2ee5f372ef90d06d92e48c7dfa9828212e38bf942e1741aca322b9996",
                "a35d9bd389a6fb9e04052eb411e4c9701a76ff0fd699e1c2d2a113d86439dfd5",
                "1d143e954c48cb48172cf61975868c3c76852f152d100a04745b16b02fa5e911",
            ),
        )
        self.assertEqual(
            (
                predecessor["v12TestsBindingScope"],
                predecessor["v12TestsLiveHeld"],
                predecessor["wave14NamespaceAnchor"],
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
            (341, 171, 170, 1, 120),
        )
        counters = self.decision["operationCounters"]
        self.assertEqual(
            (
                counters["totalFullSourceReconstructionCount"],
                counters["totalV13GraphArchiveOpenCount"],
                counters["overallDecisionExecutionArchiveOpenCount"],
            ),
            (24, 2_986, 3_328),
        )
        self.assertEqual(
            (
                self.permit["identityBinding"]["compactIdentitySha256"],
                self.permit["identityBinding"]["fullWitnessSha256"],
                self.permit["identityBinding"]["heldSourceBindingsSha256"],
            ),
            (
                "b9fc13d747fc092cf312ffdf4c792c078f4c79c783b2426a00388ae2f98d915b",
                "92fc2c418b2cda6984f51d09a0c8f8e95633539ee1542c91a03cc679011e7ee7",
                "fbd023d2ee5f372ef90d06d92e48c7dfa9828212e38bf942e1741aca322b9996",
            ),
        )

    def test_exact_request_contract_and_no_authentication(self) -> None:
        self.assertEqual(len(self.rows), 10)
        self.assertEqual(
            [row["requestOrdinal"] for row in self.rows],
            list(range(1, 11)),
        )
        self.assertEqual(
            [row["kind"] for row in self.rows],
            ["mod", "zip"] * 5,
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
            "106a3f88983749e5272783fc7ce1293473a8dacf2e86ef7effc374707fec0d04",
        )
        source_requests = self.decision[
            "sourceAcquisitionPreparation"
        ]["requestSet"]
        self.assertEqual(
            check.sha256(check.digest_bytes(source_requests)),
            "106a3f88983749e5272783fc7ce1293473a8dacf2e86ef7effc374707fec0d04",
        )
        self.assertNotEqual(
            check.sha256(check.canonical_bytes(source_requests)),
            "106a3f88983749e5272783fc7ce1293473a8dacf2e86ef7effc374707fec0d04",
        )
        self.assertEqual(
            self.permit["requestContract"]["resourcesCanonicalSha256"],
            "2898a6d51c5c660f0c714524b862c5f715cb1d6971b57cfc737c666953068603",
        )
        self.assertEqual(
            self.permit["oneUseContract"]["existingClaimState"],
            "already_consumed",
        )

    def test_five_modules_remain_distinct_exact_tuples(self) -> None:
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
                ("golang.org/x/mod", "v0.25.0"),
                ("golang.org/x/net", "v0.41.0"),
                ("golang.org/x/sync", "v0.15.0"),
                ("golang.org/x/sys", "v0.33.0"),
                (
                    "golang.org/x/telemetry",
                    "v0.0.0-20240521205824-bda55230c457",
                ),
            },
        )
        self.assertEqual(len({module for module, _ in identities}), 5)
        self.assertEqual(len(set(identities.values())), 5)
        projected = self.rows[::2]
        self.assertEqual(len({row["tupleId"] for row in projected}), 5)
        self.assertEqual(
            len({(row["module"], row["version"]) for row in projected}),
            5,
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
                "wave15PublicProxy10GetAcquisitionAuthorizedOnce": True,
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
            "wave15PublicProxy10GetAcquisitionAuthorizedOnce",
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
            list(EXPECTED_WAVE15_IDENTITIES),
        )
        for tuple_order, (identity, expected, resource_names) in enumerate(
            zip(
                identity_rows,
                EXPECTED_WAVE15_IDENTITIES,
                EXPECTED_WAVE15_RESOURCE_NAMES,
            ),
            1,
        ):
            mod, archive = self.rows[(tuple_order - 1) * 2:tuple_order * 2]
            module, version, selected, mod_h1, zip_h1 = expected
            tuple_id, mod_name, zip_name = resource_names
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
                    mod["tupleId"],
                    archive["tupleId"],
                    mod["acceptedFileName"],
                    archive["acceptedFileName"],
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
                    tuple_id,
                    tuple_id,
                    mod_name,
                    zip_name,
                ),
            )
            self.assertEqual(mod["expectedH1"], identity["goModH1"])
            self.assertEqual(archive["expectedH1"], identity["moduleZipH1"])
        self.assertEqual(
            [row["kind"] for row in self.rows],
            ["mod", "zip"] * len(EXPECTED_WAVE15_IDENTITIES),
        )
        self.assertEqual(
            len({row["url"] for row in self.rows}),
            10,
        )
        self.assertEqual(
            len({row["acceptedFileName"] for row in self.rows}),
            10,
        )
        self.assertEqual(
            (self.rows[0]["tupleId"], self.rows[-1]["tupleId"]),
            (
                "wave15-001-5aede784ca07",
                "wave15-005-e5b8406e7a0c",
            ),
        )

    def test_portfolio_caps_and_stale_wave_markers_are_pinned(self) -> None:
        limits = self.permit["absoluteResourceLimits"]
        zip_limits = self.permit["zipLimits"]
        self.assertEqual(limits["maximumRequestCount"], 10)
        self.assertEqual(
            limits["maximumAggregateModResponseBodyBytes"],
            5 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateZipResponseBodyBytes"],
            80 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateResponseBodyBytes"],
            85 * 1024 * 1024,
        )
        self.assertEqual(
            zip_limits["maximumEntryCountAcrossAllZips"],
            100_000,
        )
        self.assertEqual(
            zip_limits["maximumUncompressedBytesAcrossAllZips"],
            640 * 1024 * 1024,
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
            "combinedFixedPointV13"
        ]
        self.assertEqual(
            (predecessor["checkerPath"], predecessor["testsPath"]),
            (check.V13_CHECKER_PATH, check.V13_TESTS_PATH),
        )
        stale_markers = (
            "EXPECTED_WAVE" + "14_IDENTITY",
            "EXPECTED_WAVE" + "14_IDENTITIES",
            "EXPECTED_WAVE" + "14_RESOURCE_CONTRACT_SHA256",
            "wave14PublicProxy" + "8GetAcquisitionAuthorizedOnce",
            "exact_" + "8_resource",
            "8-" + "resource",
            "all_" + "8_rows",
            "before_" + "8_fetches",
            '"requestCount": ' + "8",
            'requestCount"] == ' + "8",
            '"maximumRequestCount": ' + "8",
            'maximumRequestCount"] == ' + "8",
            "range(0, " + "8, 2)",
            "range(1, " + "9)",
            "MAX_AGGREGATE_MOD_BYTES = " + "4 * 1024 * 1024",
            "MAX_AGGREGATE_ZIP_BYTES = " + "64 * 1024 * 1024",
            "MAX_AGGREGATE_BYTES = " + "68 * 1024 * 1024",
            "MAX_ALL_ZIP_FILES = " + "80_000",
            "MAX_ALL_ZIP_UNCOMPRESSED_BYTES = "
            + "512 * 1024 * 1024",
            "golang.org/x/" + "crypto",
            "golang.org/x/" + "term",
            "golang.org/x/" + "text",
            "golang.org/x/" + "tools",
            "wave15-001-" + "6ade739bf483",
            "wave15-004-" + "b142b05fc3ea",
            "505587c9" + "0ec32b1dea879b1e034450de091874a2ff9db9993532f1b14d9dc3aa",
            "ba1741c1" + "81b834c42c2501232fc8d99e5dfae3e02fb1d927fdb56f3248d20b6e",
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
            for marker in stale_markers:
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker, source)

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

    def test_every_source_request_field_is_exactly_bound_on_all_10_rows(
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
            10,
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
        self.assertNotIn('"wave15' + 'Candidate"', source)
        self.assertIn("DECISION.validate_materialized_decision", source)
        self.assertEqual(len(check._decision_package_bindings()), 4)

    def test_reserved_namespace_rejects_all_wave15_names(self) -> None:
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
