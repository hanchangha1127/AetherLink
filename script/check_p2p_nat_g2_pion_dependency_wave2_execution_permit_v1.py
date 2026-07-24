#!/usr/bin/env python3
"""Validate the exact one-use G2 Pion dependency wave-two execution permit."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
COMMON_PATH = "script/p2p_nat_g2_pion_dependency_wave2_common_v1.py"
PERMIT_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave2-execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave2-execution-permit-v1.md"
)
DECISION_READER_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave2-v1.md"
)
DECISION_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave2_decision_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave2_v1_once.py"
)
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_dependency_wave2_v1_once.py"
)
READBACK_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave2_success_v1.py"
)
READBACK_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave2_success_v1.py"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave2_execution_permit_v1.py"
)
THIS_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave2_execution_permit_v1.py"
)

EXPECTED_COMMON_RAW_SHA256 = (
    "dc25ddd3a82789bddccbd6ec57a71edc389225e003d7a73e6d371a640937f8c1"
)
PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave2-execution-permit-v1"
)
STATUS = "wave2_v1_dependency_source_acquisition_authorized_not_consumed"
RESULT = (
    "exact_15_public_proxy_mod_then_zip_pairs_authorized_once_not_executed"
)
NEXT_ACTION = "execute_bound_dependency_source_wave2_v1_once"
SCOPE = (
    "single_fresh_exact_15_public_go_proxy_mod_then_zip_pair_"
    "source_intake_wave2_v1_only"
)


def bootstrap_read(relative: str, expected_sha256: str) -> bytes:
    path = ROOT / relative
    current = ROOT
    for component in relative.split("/")[:-1]:
        current /= component
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid not in {0, os.geteuid()}
            or stat.S_IMODE(before.st_mode) & 0o022
            or before.st_size > 4 * 1024 * 1024
        ):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                raise RuntimeError("E_BOOTSTRAP_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        if (
            os.read(fd, 1) != b""
            or hashlib.sha256(raw).hexdigest() != expected_sha256
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
        return raw
    finally:
        os.close(fd)


def execute_module(
    name: str,
    relative: str,
    raw: bytes,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__file__": str(ROOT / relative),
            "__cached__": None,
            "__loader__": None,
            "__package__": None,
        }
    )
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(
            compile(raw, relative, "exec", dont_inherit=True, optimize=0),
            module.__dict__,
            module.__dict__,
        )
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


COMMON = execute_module(
    "g2_wave2_permit_common_trust_root",
    COMMON_PATH,
    bootstrap_read(COMMON_PATH, EXPECTED_COMMON_RAW_SHA256),
)


TOOL_SPECS: tuple[tuple[str, str, int], ...] = (
    ("wave2_common_fail_closed_primitives", COMMON_PATH, COMMON.MAXIMUM_TOOL_BYTES),
    (
        "wave2_identity_decision_reader",
        DECISION_READER_PATH,
        COMMON.MAXIMUM_JSON_BYTES,
    ),
    (
        "wave2_identity_decision_checker",
        COMMON.DECISION_CHECKER_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    (
        "wave2_identity_decision_offline_regression_tests",
        DECISION_TEST_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    (
        "immutable_wave1_v1_filesystem_and_zip_primitives",
        COMMON.LEGACY_RUNNER_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    (
        "immutable_wave1_v3_mod_zip_validation_primitives",
        COMMON.WAVE1_V3_RUNNER_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    ("wave2_v1_runner", RUNNER_PATH, COMMON.MAXIMUM_TOOL_BYTES),
    (
        "wave2_v1_runner_offline_regression_tests",
        RUNNER_TEST_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    (
        "wave2_v1_independent_readback_checker",
        READBACK_CHECKER_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    (
        "wave2_v1_independent_readback_offline_regression_tests",
        READBACK_TEST_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    (
        "wave2_v1_execution_permit_reader_contract",
        PERMIT_READER_PATH,
        COMMON.MAXIMUM_JSON_BYTES,
    ),
    (
        "wave2_v1_execution_permit_checker",
        THIS_CHECKER_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
    (
        "wave2_v1_execution_permit_checker_offline_regression_tests",
        THIS_TEST_PATH,
        COMMON.MAXIMUM_TOOL_BYTES,
    ),
)


def preparation_bindings(
    *,
    include_permit: bool,
) -> list[dict[str, Any]]:
    bindings = [
        {
            "path": COMMON.DECISION_PATH,
            "rawSha256": COMMON.EXPECTED_DECISION_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
        },
    ]
    seen = {COMMON.DECISION_PATH}
    for _, path, maximum in TOOL_SPECS:
        if path in seen:
            continue
        seen.add(path)
        binding = {"path": path, "maximumBytes": maximum}
        if path == COMMON_PATH:
            binding["rawSha256"] = EXPECTED_COMMON_RAW_SHA256
        elif path == COMMON.DECISION_CHECKER_PATH:
            binding["rawSha256"] = (
                COMMON.EXPECTED_DECISION_CHECKER_RAW_SHA256
            )
        elif path == COMMON.LEGACY_RUNNER_PATH:
            binding["rawSha256"] = (
                COMMON.EXPECTED_LEGACY_RUNNER_RAW_SHA256
            )
        elif path == COMMON.WAVE1_V3_RUNNER_PATH:
            binding["rawSha256"] = (
                COMMON.EXPECTED_WAVE1_V3_RUNNER_RAW_SHA256
            )
        bindings.append(binding)
    if include_permit:
        bindings.append(
            {
                "path": PERMIT_PATH,
                "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
            }
        )
    return bindings


def repository_root_identity(root: Path) -> dict[str, int]:
    path_info = root.lstat()
    fd = os.open(
        root,
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        opened = os.fstat(fd)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or stat.S_ISLNK(path_info.st_mode)
            or opened.st_dev != path_info.st_dev
            or opened.st_ino != path_info.st_ino
            or opened.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) & 0o022
        ):
            raise COMMON.Wave2Failure(
                "E_REPOSITORY_ROOT",
                "preflight",
            )
        return {
            "device": opened.st_dev,
            "inode": opened.st_ino,
            "uid": opened.st_uid,
            "mode": stat.S_IMODE(opened.st_mode),
        }
    finally:
        os.close(fd)


def ordered_requests(
    decision: Mapping[str, Any],
) -> list[dict[str, Any]]:
    items = COMMON.adapt_tuples(decision)
    rows: list[dict[str, Any]] = []
    for item in items:
        for kind in ("mod", "zip"):
            is_mod = kind == "mod"
            rows.append(
                {
                    "requestOrdinal": item[
                        "modRequestOrdinal"
                        if is_mod
                        else "zipRequestOrdinal"
                    ],
                    "tupleOrder": item["order"],
                    "tupleId": item["tupleId"],
                    "module": item["module"],
                    "version": item["version"],
                    "selectedByGraphAlgorithm": item[
                        "selectedByGraphAlgorithm"
                    ],
                    "resourceKind": kind,
                    "method": "GET",
                    "url": item["modUrl"] if is_mod else item["url"],
                    "outputFileName": item[
                        "modOutputFileName"
                        if is_mod
                        else "zipOutputFileName"
                    ],
                    "expectedH1": item[
                        "goModH1" if is_mod else "moduleZipH1"
                    ],
                    "expectedH1Kind": (
                        "go_mod_h1" if is_mod else "module_zip_h1"
                    ),
                    "allowedContentTypes": (
                        ["text/plain", "application/octet-stream"]
                        if is_mod
                        else ["application/zip", "application/octet-stream"]
                    ),
                }
            )
    if [row["requestOrdinal"] for row in rows] != list(range(1, 31)):
        raise COMMON.Wave2Failure("E_REQUEST_CONTRACT", "preflight")
    return rows


def tool_bindings(inputs: Any) -> list[dict[str, str]]:
    return [
        {
            "role": role,
            "path": path,
            "rawSha256": COMMON.sha256_bytes(inputs.raw(path)),
        }
        for role, path, _ in TOOL_SPECS
    ]


def reserved_paths(decision: Mapping[str, Any]) -> dict[str, Any]:
    items = COMMON.adapt_tuples(decision)
    resources = [
        f"{COMMON.FINAL_DIRECTORY_PATH}/{name}"
        for name in COMMON.expected_resource_names(items)
    ]
    acquisition = [
        f"{COMMON.DEPENDENCY_PARENT.as_posix()}/{COMMON.CLAIM_NAME}",
        *resources,
        COMMON.SUCCESS_RECEIPT_PATH,
        COMMON.MANIFEST_PATH,
    ]
    post_readback = [
        *acquisition,
        COMMON.READBACK_RECEIPT_PATH,
        COMMON.READBACK_MANIFEST_PATH,
    ]
    return {
        "regularFileCountMeaning": (
            "exact_reserved_regular_file_path_set_not_recursive_directory_count"
        ),
        "acquisitionPublication": {
            "count": 33,
            "paths": acquisition,
        },
        "postReadbackPublication": {
            "count": 35,
            "paths": post_readback,
        },
        "failureReceiptPath": COMMON.FAILURE_RECEIPT_PATH,
        "successAndFailureMutuallyExclusive": True,
    }


def expected_permit(
    inputs: Any,
    decision: Mapping[str, Any],
    root_identity: Mapping[str, int],
) -> dict[str, Any]:
    requests = ordered_requests(decision)
    limits = decision["resourceLimits"]
    value: dict[str, Any] = {
        "documentType": (
            "aetherlink.g2-pion-rung3-dependency-wave2-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": PERMIT_ID,
        "recordedDate": "2026-07-24",
        "status": STATUS,
        "result": RESULT,
        "nextAction": NEXT_ACTION,
        "scope": SCOPE,
        "decisionBinding": {
            "path": COMMON.DECISION_PATH,
            "decisionId": decision["decisionId"],
            "rawSha256": COMMON.EXPECTED_DECISION_RAW_SHA256,
            "contentSha256": COMMON.EXPECTED_DECISION_CONTENT_SHA256,
            "requiredStatus": decision["status"],
            "orderedTupleSetSha256": decision["wave"][
                "orderedTupleSetSha256"
            ],
            "orderedResourceSetSha256": decision["wave"][
                "orderedResourceSetSha256"
            ],
        },
        "readerDocumentBinding": {
            "path": PERMIT_READER_PATH,
            "rawSha256": COMMON.sha256_bytes(
                inputs.raw(PERMIT_READER_PATH)
            ),
        },
        "toolBindings": tool_bindings(inputs),
        "requestContract": {
            "tupleCount": 15,
            "resourcesPerTuple": 2,
            "requestCount": 30,
            "method": "GET",
            "scheme": "https",
            "host": "proxy.golang.org",
            "port": 443,
            "tupleOrder": "exact_wave2_decision_order_1_through_15_sequential",
            "resourceOrderPerTuple": ["mod", "zip"],
            "requestOrdinalRule": {
                "mod": "two_times_tuple_order_minus_one",
                "zip": "two_times_tuple_order",
            },
            "orderedRequests": requests,
            "redirectAllowed": False,
            "retryAllowed": False,
            "rangeOrResumeAllowed": False,
            "queryAllowed": False,
            "fragmentAllowed": False,
            "alternateMirrorAllowed": False,
            "ambientProxyAllowed": False,
            "credentialsAllowed": False,
            "authorizationHeaderAllowed": False,
            "proxyAuthorizationHeaderAllowed": False,
            "cookieAllowed": False,
            "clientCertificateAllowed": False,
            "authenticationChallengeHandlingAllowed": False,
            "acceptedStatusCode": 200,
            "identityContentEncodingRequired": True,
        },
        "networkAuthority": {
            "boundedSourceIntakeDnsAuthorized": True,
            "boundedSourceIntakeTcpAuthorized": True,
            "boundedSourceIntakeTlsAuthorized": True,
            "boundedSourceIntakeHttpsAuthorized": True,
            "authorizedHost": "proxy.golang.org",
            "authorizedPort": 443,
            "authorizedRequestCount": 30,
            "tlsCertificateAndHostnameVerificationRequired": True,
            "runtimeSocketAuthorized": False,
            "runtimeNetworkAuthorized": False,
            "productNetworkAuthorized": False,
            "relayOrP2PNetworkAuthorized": False,
        },
        "filesystemWriteAuthority": {
            "newDirectoryMode": "0700",
            "newFileMode": "0600",
            "claimWriteAuthorized": True,
            "stagingWriteAuthorized": True,
            "acceptedModWriteAuthorized": True,
            "acceptedZipWriteAuthorized": True,
            "successReceiptWriteAuthorized": True,
            "failureReceiptWriteAuthorized": True,
            "manifestWriteAuthorized": True,
            "readbackReceiptAndManifestWritesAuthorizedOnlyByBoundChecker": True,
            "failedStagingCleanupAuthorized": True,
            "atomicNoReplaceFinalDirectoryPublicationRequired": True,
            "wave1ArtifactModificationAuthorized": False,
            "sourceModificationAuthorized": False,
            "sourceExtractionAuthorized": False,
            "otherRepositoryWritesAuthorized": False,
        },
        "oneUseConsumption": {
            "initialState": "authorized_not_consumed",
            "claimPath": (
                f"{COMMON.DEPENDENCY_PARENT.as_posix()}/"
                f"{COMMON.CLAIM_NAME}"
            ),
            "stagingParentPath": COMMON.DEPENDENCY_PARENT.as_posix(),
            "stagingNamePrefix": COMMON.STAGING_PREFIX,
            "waveParentPath": (
                f"{COMMON.DEPENDENCY_PARENT.as_posix()}/"
                f"{COMMON.WAVE_PARENT_NAME}"
            ),
            "finalDirectoryPath": COMMON.FINAL_DIRECTORY_PATH,
            "claimCreatedExclusivelyBeforeNetwork": True,
            "claimFsyncedBeforeNetwork": True,
            "claimContainsRandomAttemptId": True,
            "claimPersistsAfterAnyNetworkAttempt": True,
            "claimUncertaintyConsumesPermit": True,
            "automaticRetryAllowed": False,
            "secondExecutionAllowed": False,
            "preclaimFailureConsumesPermit": False,
            "wave1ArtifactReuseAllowed": False,
            "partialResumeAllowed": False,
        },
        "resourceValidationContract": {
            "mod": {
                "sourceBytes": "exact_mod_response_body",
                "maximumBytesPerResponse": limits[
                    "maximumSingleModBytes"
                ],
                "utf8Required": True,
                "nulByteForbidden": True,
                "exactSingleModuleDirectiveRequired": True,
                "goModH1Required": True,
                "goModH1Algorithm": (
                    "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod"
                ),
            },
            "zip": {
                "maximumBytesPerResponse": limits[
                    "maximumSingleZipBytes"
                ],
                "filesystemExtractionAllowed": False,
                "centralAndLocalHeaderConsistencyRequired": True,
                "crcRequired": True,
                "exactEofRequired": True,
                "zip64Allowed": False,
                "encryptionAllowed": False,
                "explicitDirectoryEntriesAllowed": False,
                "symlinkOrSpecialFileAllowed": False,
                "duplicateOrCasefoldCollisionAllowed": False,
                "validUtf8AndNfcPathsRequired": True,
                "allowedCompressionMethods": ["stored", "deflated"],
                "exactModulePrefixRequired": True,
                "moduleZipH1Required": True,
                "embeddedRootGoModRequired": False,
                "embeddedRootGoModMustMatchExternalModWhenPresent": True,
                "compressionRatioMaximum": limits[
                    "maximumCompressionRatio"
                ],
                "compressionRatioUsesIntegerArithmetic": True,
            },
            "streamedToOwnerOnlyTemporaryFiles": True,
            "openedDescriptorValidation": True,
            "allResourcesReopenedReparsedAndRehashedBeforePublication": True,
            "orderedSourceSetDigestRequired": True,
            "heldGoSumH1IsFreshChecksumDatabaseProof": False,
        },
        "absoluteResourceLimits": {
            "maximumTupleCount": 15,
            "maximumRequestCount": limits["maximumRequestCount"],
            "maximumModResponseBytesPerTuple": limits[
                "maximumSingleModBytes"
            ],
            "maximumZipResponseBytesPerTuple": limits[
                "maximumSingleZipBytes"
            ],
            "maximumAggregateResponseBytes": limits[
                "maximumAggregateResponseBytes"
            ],
            "maximumEntriesPerArchive": limits[
                "maximumZipEntryCountPerArchive"
            ],
            "maximumUncompressedBytesPerArchive": limits[
                "maximumZipUncompressedBytesPerArchive"
            ],
            "maximumCompressionRatio": limits[
                "maximumCompressionRatio"
            ],
            "maximumAggregateEntries": (
                COMMON.MAXIMUM_AGGREGATE_ENTRIES
            ),
            "maximumAggregateUncompressedBytes": (
                COMMON.MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
            ),
            "maximumCentralDirectoryBytesPerArchive": (
                COMMON.MAXIMUM_CENTRAL_DIRECTORY_BYTES
            ),
            "maximumSingleFileBytes": COMMON.MAXIMUM_SINGLE_FILE_BYTES,
            "maximumPathBytes": 1024,
            "maximumPathComponents": 64,
            "maximumComponentBytes": 255,
            "maximumJsonReceiptOrFailureBytes": (
                COMMON.MAXIMUM_JSON_BYTES
            ),
            "perRequestDeadlineMilliseconds": 30_000,
            "wholeWaveDeadlineMilliseconds": 600_000,
            "acquisitionSuccessRegularFileCount": 33,
            "postReadbackRegularFileCount": 35,
        },
        "counterContract": {
            "counterNames": list(COMMON.COUNTER_NAMES),
            "successValues": {
                "networkRequestAttemptCount": 30,
                "responseBodyCompletedCount": 30,
                "validatedAndStagedResourceCount": 30,
                "validatedModResourceCount": 15,
                "validatedZipResourceCount": 15,
                "validatedAndStagedTupleCount": 15,
                "acceptedArtifactCount": 30,
                "acceptedTupleCount": 15,
            },
            "failureRequestContextNullableBeforeRequest": True,
            "failureRequestContextRequiredAfterRequestAttempt": True,
            "safeNumericObservationsOnly": True,
        },
        "receiptFailureManifestContract": {
            "successReceiptPath": COMMON.SUCCESS_RECEIPT_PATH,
            "failureReceiptPath": COMMON.FAILURE_RECEIPT_PATH,
            "manifestPath": COMMON.MANIFEST_PATH,
            "successState": "acquired_pending_independent_readback",
            "failureState": "wave2_v1_acquisition_failed_permit_consumed",
            "postPublishUncertainState": "consumed_terminal_state_uncertain",
            "successAndFailureMutuallyExclusive": True,
            "acceptedArtifactCountOnSuccess": 30,
            "acceptedTupleCountOnSuccess": 15,
            "acceptedArtifactCountOnFailure": 0,
            "boundedFailureReasonCodesOnly": True,
            "rawErrorsBodiesHeadersCertificatesPathsOrEntryNamesRecorded": False,
            "manifestWrittenLast": True,
            "runnerMayClaimIndependentReadback": False,
            "independentReadbackRequired": True,
            "failureReceiptWriteFailureMustBeReported": True,
            "failureReceiptForbiddenAfterPublishAttempt": True,
        },
        "independentReadbackContract": {
            "requiredAfterAcquisitionSuccess": True,
            "runnerSelfCheckQualifiesAsIndependentReadback": False,
            "checkerPath": READBACK_CHECKER_PATH,
            "checkerTestsPath": READBACK_TEST_PATH,
            "receiptPath": COMMON.READBACK_RECEIPT_PATH,
            "manifestPath": COMMON.READBACK_MANIFEST_PATH,
            "exactRetainedResourceCount": 30,
            "minimumStableFullReadPassCount": 2,
            "recomputeRawSha256": True,
            "recomputeModuleZipH1": True,
            "recomputeGoModH1": True,
            "recheckArchiveStructureAndCompressionRatio": True,
            "recheckEmbeddedModParityWhenPresent": True,
            "recheckExactInventoryModeLinkCountAndStableIdentity": True,
            "networkAllowed": False,
            "sourceExtractionAllowed": False,
            "sourceLoadOrExecutionAllowed": False,
            "receiptAndManifestWritesOnly": True,
            "manifestWrittenLast": True,
            "fixedPointGraphRerunRequiredAfterReadback": True,
        },
        "execution": {
            "permitRecorded": True,
            "permitConsumed": False,
            "claimCreated": False,
            **COMMON.zero_counters(),
            "acceptedArtifactCount": 0,
            "acceptedTupleCount": 0,
            "networkUsed": False,
            "successReceiptCreated": False,
            "failureReceiptCreated": False,
            "manifestCreated": False,
            "independentReadbackPassed": False,
        },
        "personalProjectBoundary": {
            "projectOwnership": "personal_single_owner",
            "repositoryOwnerIdentityProofRequired": False,
            "accountLoginRequired": False,
            "externalAuthenticationRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "signatureRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationChanged": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
        },
        "interpreterIsolationContract": {
            "permitCheckerPreflightCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                THIS_CHECKER_PATH,
                "--preflight",
            ],
            "runnerPreflightCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RUNNER_PATH,
                "--preflight",
            ],
            "runnerExecuteCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RUNNER_PATH,
                "--execute",
            ],
            "readbackCheckCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                READBACK_CHECKER_PATH,
                "--check",
            ],
            "readbackRecordCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                READBACK_CHECKER_PATH,
                "--record",
            ],
            "isolatedInterpreterRequired": True,
            "sitePackagesAllowed": False,
            "bytecodeWritesAllowed": False,
            "pythonPathAllowed": False,
            "environmentOverridesAllowed": False,
            "processUmask": "077",
            "cliOverridesAllowed": False,
        },
        "repositoryRootIdentity": {
            "device": root_identity["device"],
            "inode": root_identity["inode"],
            "uid": root_identity["uid"],
            "mode": root_identity["mode"],
            "realDirectoryRequired": True,
            "groupOrOtherWritableAllowed": False,
            "stableIdentityBarrierRequired": True,
        },
        "reservedRegularFilePaths": reserved_paths(decision),
        "closure": {
            "openFindingCount": 19,
            "findingsClosedByPermit": 0,
            "waveAcquired": False,
            "graphFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "nonClaims": [
            "permit_is_not_execution_success_or_independent_readback_evidence",
            "wave1_claims_outputs_and_namespaces_are_not_reused_or_changed",
            "selected_false_version_specific_frontier_tuples_are_not_removed",
            "held_go_sum_h1_is_not_fresh_checksum_database_inclusion_proof",
            "module_zip_h1_go_mod_h1_and_raw_sha256_are_distinct_bindings",
            "fifteen_frontier_sources_are_not_dependency_fixed_point_evidence",
            "acquisition_is_not_source_license_security_or_semantic_review",
            "runner_self_checks_are_not_independent_readback",
            "readback_does_not_replace_combined_fixed_point_graph_rerun",
            "permit_does_not_select_a_candidate_library_or_product_endpoint",
            "no_repository_authentication_owner_proof_or_user_action_is_required",
        ],
    }
    value["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "permit_without_contentBinding",
        "sha256": COMMON.sha256_bytes(COMMON.canonical_json_bytes(value)),
    }
    return value


def validate_runner_reverse_pins(inputs: Any) -> None:
    checker_sha = COMMON.sha256_bytes(inputs.raw(THIS_CHECKER_PATH))

    def assigned_string(source: str, name: str) -> str:
        tree = ast.parse(source)
        values: list[str] = []
        for node in tree.body:
            target = None
            value = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                value = node.value
            if (
                isinstance(target, ast.Name)
                and target.id == name
                and isinstance(value, ast.Constant)
                and type(value.value) is str
            ):
                values.append(value.value)
        if len(values) != 1:
            raise COMMON.Wave2Failure(
                "E_REVERSE_BINDING",
                "preflight",
            )
        return values[0]

    for path in (RUNNER_PATH, READBACK_CHECKER_PATH):
        source = inputs.raw(path).decode("utf-8", errors="strict")
        if (
            assigned_string(
                source,
                "EXPECTED_PERMIT_CHECKER_RAW_SHA256",
            )
            != checker_sha
            or assigned_string(source, "EXPECTED_COMMON_RAW_SHA256")
            != EXPECTED_COMMON_RAW_SHA256
        ):
            raise COMMON.Wave2Failure(
                "E_REVERSE_BINDING",
                "preflight",
            )


def validate_permit_document(
    permit: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    if type(permit) is not dict or permit != expected:
        raise COMMON.Wave2Failure("E_PERMIT", "preflight")
    COMMON.validate_content_binding(
        permit,
        scope="permit_without_contentBinding",
    )


def validate_repository(
    root: Path,
    *,
    require_clean_namespace: bool = True,
) -> dict[str, Any]:
    global ROOT
    ROOT = root.resolve()
    if sys.flags.isolated != 1 or not sys.dont_write_bytecode:
        raise COMMON.Wave2Failure("E_INTERPRETER", "preflight")
    inputs = COMMON.HeldInputSet(
        ROOT,
        preparation_bindings(include_permit=True),
    )
    try:
        decision = COMMON.load_decision(
            inputs,
            ROOT,
            require_empty_namespace=require_clean_namespace,
        )
        identity = repository_root_identity(ROOT)
        expected = expected_permit(inputs, decision, identity)
        permit = COMMON.strict_json(inputs.raw(PERMIT_PATH), PERMIT_PATH)
        validate_permit_document(permit, expected)
        validate_runner_reverse_pins(inputs)
        if require_clean_namespace:
            COMMON.require_clean_namespace(ROOT)
        inputs.final_barrier()
        if require_clean_namespace:
            COMMON.require_clean_namespace(ROOT)
        return {
            "permit": permit,
            "decision": decision,
            "repositoryRootIdentity": identity,
            "executionAuthorized": True,
            "namespacePreflightChecked": require_clean_namespace,
            "requestCount": 30,
            "tupleCount": 15,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "networkUsed": False,
            "fileWriteCount": 0,
        }
    finally:
        inputs.close()


def print_expected(root: Path) -> dict[str, Any]:
    global ROOT
    ROOT = root.resolve()
    inputs = COMMON.HeldInputSet(
        ROOT,
        preparation_bindings(include_permit=False),
    )
    try:
        decision = COMMON.load_decision(
            inputs,
            ROOT,
            require_empty_namespace=True,
        )
        value = expected_permit(
            inputs,
            decision,
            repository_root_identity(ROOT),
        )
        inputs.final_barrier()
        COMMON.require_clean_namespace(ROOT)
        return value
    finally:
        inputs.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="validate the permit and require the clean namespace",
    )
    parser.add_argument(
        "--print-expected",
        action="store_true",
        help="print the expected permit without reading a permit file",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.print_expected:
            result = print_expected(args.root)
        else:
            checked = validate_repository(
                args.root,
                require_clean_namespace=True,
            )
            result = {
                key: checked[key]
                for key in (
                    "executionAuthorized",
                    "namespacePreflightChecked",
                    "requestCount",
                    "tupleCount",
                    "externalAuthenticationRequired",
                    "userActionRequired",
                    "networkUsed",
                    "fileWriteCount",
                )
            }
    except COMMON.Wave2Failure as failure:
        print(f"{failure.code}:{failure.phase}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
