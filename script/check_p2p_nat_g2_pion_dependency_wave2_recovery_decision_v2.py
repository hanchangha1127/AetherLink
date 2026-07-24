#!/usr/bin/env python3
"""Validate the consumed Wave2 v2 failure and selected v3 recovery design."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
COMMON_PATH = "script/p2p_nat_g2_pion_dependency_wave2_common_v2.py"
V2_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-"
    "execution-permit-v2.json"
)
V2_PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-"
    "execution-permit-v2.md"
)
V2_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave2_v2_once.py"
)
V2_RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_dependency_wave2_v2_once.py"
)
V2_PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave2_execution_permit_v2.py"
)
V2_PERMIT_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave2_execution_permit_v2.py"
)
V2_READBACK_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave2_success_v2.py"
)
V2_READBACK_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave2_success_v2.py"
)
RECOVERY_V1_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-"
    "recovery-decision-v1.json"
)
RECOVERY_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-"
    "recovery-decision-v2.json"
)
RECOVERY_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-"
    "recovery-decision-v2.md"
)
V2_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-2-v2.claim"
)
V2_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-failure-v2.json"
)
V2_WAVE_PARENT_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v2"
)

EXPECTED_COMMON_RAW_SHA256 = (
    "a877fc159e8abee773e1517f559266d97655aafac653398b76c91c724bd94316"
)
EXPECTED_RECOVERY_RAW_SHA256 = (
    "ffe2d8eaae8809d60f7f31da7f8c1bd3a0a90cf0d533e7d88c63a9a30bf52336"
)
EXPECTED_RECOVERY_CONTENT_SHA256 = (
    "0e8c05ed9abf4c3c6ee624009565e54789be7b79d9722b931f5d96a34ce819b5"
)
EXPECTED_RECOVERY_READER_RAW_SHA256 = (
    "3d0a06339e7fc99ec1823392db3fdfbb752ec8c37c1c4219925258b41c6d478e"
)
EXPECTED_V2_PERMIT_RAW_SHA256 = (
    "5565ea080f2db3f59b64a0daec41c61adff851820bc981a684f7c1c0c374fa5d"
)
EXPECTED_V2_PERMIT_CONTENT_SHA256 = (
    "83c8e13dd03e4403102351736a82f37c054703deb3f45185d562cc528dfe6cb3"
)
EXPECTED_V2_CLAIM_RAW_SHA256 = (
    "0f2139813180b158428cb0c92ebdc2cd7035d4c0d5841058452f084db23c7d63"
)
EXPECTED_V2_FAILURE_RAW_SHA256 = (
    "602757ccea4ad7d4b7534355762d8c95fe246750860b6ca3c815d1084e55068b"
)
EXPECTED_V2_RUNNER_RAW_SHA256 = (
    "b73113a99c94d00cee428efd621c4b0e43afdeed6f85c4f279b8976b4f1313dd"
)
EXPECTED_V2_RUNNER_TEST_RAW_SHA256 = (
    "ea55d06de4fb4d7d81c707f8a984a11e9a8c2d3b763001c2f7778d394c09c11f"
)
EXPECTED_V2_PERMIT_CHECKER_RAW_SHA256 = (
    "8e4093d636308720f5fe216e8b22923b44b2b41e3e325b61d85c7ead55645147"
)
EXPECTED_V2_PERMIT_TEST_RAW_SHA256 = (
    "0024f17c8abee7d3e0b4f06b170223ee1500a561f1f007638899e59f2fd285a3"
)
EXPECTED_V2_READBACK_RAW_SHA256 = (
    "71df0bab0d85da5b6972d5668d939275d2cd833db4040bf4dce2d71910d00d0e"
)
EXPECTED_V2_READBACK_TEST_RAW_SHA256 = (
    "fe54d0b48b07ee5b5bbd4e71d1366d51720edcc7b0a6f447a1836bc0f7c4fe53"
)
EXPECTED_V2_PERMIT_READER_RAW_SHA256 = (
    "ef840350f192f9e0887e4f8f1284d1cc25cbdf7f43b6ff84326ffebc5f4ed357"
)
EXPECTED_RECOVERY_V1_RAW_SHA256 = (
    "97be9c7a3aa5e7ab58ea4eada5f5f5d6193a14cc0fb71208bafdf16ba4e7523f"
)
EXPECTED_STATUS = (
    "wave2_v2_compression_ratio_gate_failure_read_back_"
    "v3_recovery_selected_execution_not_authorized"
)
EXPECTED_RESULT = (
    "v2_consumed_after_four_responses_no_final_set_"
    "v3_non_gating_bounded_compression_telemetry_selected"
)
EXPECTED_NEXT_ACTION = (
    "prepare_separate_wave2_v3_runner_readback_tests_and_execution_permit"
)

V3_TERMINAL_PATHS: tuple[str, ...] = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-2-v3.claim",
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v3",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-receipt-v3.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-failure-v3.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-manifest-v3.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-v3.json",
    (
        f"{BASE}/bounded-dependency-source-acquisition-wave2-"
        "readback-manifest-v3.json"
    ),
)


def bootstrap_read(relative: str, expected_sha256: str) -> bytes:
    path = ROOT / relative
    current = ROOT
    for component in relative.split("/")[:-1]:
        current /= component
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
    fd = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
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
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
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
    "g2_wave2_recovery_v2_common_trust_root",
    COMMON_PATH,
    bootstrap_read(COMMON_PATH, EXPECTED_COMMON_RAW_SHA256),
)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise COMMON.Wave2Failure(code, "preflight")


def path_absent(root: Path, relative: str) -> bool:
    try:
        os.lstat(root / relative)
    except FileNotFoundError:
        return True
    except OSError as error:
        raise COMMON.Wave2Failure("E_NAMESPACE", "preflight") from error
    return False


def recovery_bindings() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "path": COMMON_PATH,
            "rawSha256": EXPECTED_COMMON_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        *COMMON.decision_bindings(),
        {
            "path": RECOVERY_V1_PATH,
            "rawSha256": EXPECTED_RECOVERY_V1_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
        },
        {
            "path": V2_PERMIT_PATH,
            "rawSha256": EXPECTED_V2_PERMIT_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
        },
        {
            "path": V2_PERMIT_READER_PATH,
            "rawSha256": EXPECTED_V2_PERMIT_READER_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
        },
        {
            "path": V2_RUNNER_PATH,
            "rawSha256": EXPECTED_V2_RUNNER_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": V2_RUNNER_TEST_PATH,
            "rawSha256": EXPECTED_V2_RUNNER_TEST_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": V2_PERMIT_CHECKER_PATH,
            "rawSha256": EXPECTED_V2_PERMIT_CHECKER_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": V2_PERMIT_TEST_PATH,
            "rawSha256": EXPECTED_V2_PERMIT_TEST_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": V2_READBACK_PATH,
            "rawSha256": EXPECTED_V2_READBACK_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": V2_READBACK_TEST_PATH,
            "rawSha256": EXPECTED_V2_READBACK_TEST_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": V2_CLAIM_PATH,
            "rawSha256": EXPECTED_V2_CLAIM_RAW_SHA256,
            "maximumBytes": 64 * 1024,
            "ownerOnly": True,
        },
        {
            "path": V2_FAILURE_PATH,
            "rawSha256": EXPECTED_V2_FAILURE_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": RECOVERY_PATH,
            "rawSha256": EXPECTED_RECOVERY_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
        },
        {
            "path": RECOVERY_READER_PATH,
            "rawSha256": EXPECTED_RECOVERY_READER_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
        },
    ]
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        if row["path"] not in seen:
            seen.add(row["path"])
            unique.append(row)
    return unique


def validate_recovery_document(document: Mapping[str, Any]) -> None:
    require(
        type(document) is dict
        and document.get("documentType")
        == "aetherlink.g2-pion-dependency-wave2-recovery-decision"
        and document.get("schemaVersion") == "2.0"
        and document.get("decisionId")
        == "g2-pion-ice-v4.3.0-rung3-dependency-wave2-recovery-decision-v2"
        and document.get("status") == EXPECTED_STATUS
        and document.get("result") == EXPECTED_RESULT
        and document.get("nextAction") == EXPECTED_NEXT_ACTION,
        "E_RECOVERY_STATE",
    )
    COMMON.validate_content_binding(
        document,
        scope="decision_without_contentBinding",
        expected=EXPECTED_RECOVERY_CONTENT_SHA256,
    )
    terminal = document.get("terminalFailureBindings")
    claim_binding = (
        terminal.get("claimV2") if type(terminal) is dict else None
    )
    failure_binding = (
        terminal.get("failureReceiptV2")
        if type(terminal) is dict
        else None
    )
    require(
        type(claim_binding) is dict
        and claim_binding.get("path") == V2_CLAIM_PATH
        and claim_binding.get("rawSha256")
        == EXPECTED_V2_CLAIM_RAW_SHA256
        and claim_binding.get("byteSize") == 755
        and claim_binding.get("mode") == "0600"
        and claim_binding.get("linkCount") == 1
        and claim_binding.get("retained") is True
        and claim_binding.get("automaticRetryAllowed") is False,
        "E_V2_CLAIM_BINDING",
    )
    require(
        type(failure_binding) is dict
        and failure_binding.get("path") == V2_FAILURE_PATH
        and failure_binding.get("rawSha256")
        == EXPECTED_V2_FAILURE_RAW_SHA256
        and failure_binding.get("byteSize") == 1408
        and failure_binding.get("mode") == "0600"
        and failure_binding.get("linkCount") == 1
        and failure_binding.get("status")
        == "wave2_v2_acquisition_failed_permit_consumed"
        and failure_binding.get("result")
        == "no_wave2_dependency_source_set_accepted"
        and failure_binding.get("failureCode")
        == "E_ZIP_COMPRESSION_RATIO"
        and failure_binding.get("phase") == "zip"
        and failure_binding.get("failedTupleId")
        == "wave2-002-fb2873f66a36"
        and failure_binding.get("failedTupleOrder") == 2
        and failure_binding.get("failedRequestOrdinal") == 4
        and failure_binding.get("failedResourceKind") == "zip"
        and [
            failure_binding.get(name)
            for name in COMMON.COUNTER_NAMES
        ]
        == [4, 4, 3, 2, 1, 1]
        and failure_binding.get("acceptedArtifactCount") == 0
        and failure_binding.get("acceptedTupleCount") == 0
        and failure_binding.get("finalSetPublished") is False
        and failure_binding.get("automaticRetryAllowed") is False,
        "E_V2_FAILURE_BINDING",
    )
    interpretation = document.get("failureInterpretation")
    require(
        type(interpretation) is dict
        and interpretation.get("safeNumericObservations") == {}
        and interpretation.get("actualCompressionRatioRecorded") is False
        and interpretation.get("v2PreflightTerminalState")
        == "consumed_failure_recovery_required"
        and interpretation.get("authenticationRelated") is False
        and interpretation.get("credentialRelated") is False
        and interpretation.get("ownerProofRelated") is False,
        "E_FAILURE_INTERPRETATION",
    )
    policy = document.get("selectedV3Policy")
    telemetry = (
        policy.get("compressionTelemetry")
        if type(policy) is dict
        else None
    )
    limits = policy.get("absoluteLimits") if type(policy) is dict else None
    require(
        type(policy) is dict
        and policy.get("fullFreshTupleCountRequired") == 15
        and policy.get("maximumRequestCount") == 30
        and policy.get("v2ResponseOrStagingReuseAllowed") is False
        and policy.get("v2PartialResumeAllowed") is False
        and type(telemetry) is dict
        and telemetry.get("policy") == "non_gating_bounded_telemetry"
        and telemetry.get("historicalV2ComparisonRatio") == 200
        and telemetry.get("exactIntegerComparisonRequired") is True
        and telemetry.get("divisionOrFloatingPointAllowed") is False
        and telemetry.get("maximumRatioExceededHistoricalV2LimitRequired")
        is True
        and telemetry.get("entryNameOrBodyRecorded") is False
        and telemetry.get("ratioUsedAsRejectionGate") is False,
        "E_V3_POLICY",
    )
    require(
        type(limits) is dict
        and limits
        == {
            "maximumAggregateEntries": 300000,
            "maximumAggregateResponseBytes": 67108864,
            "maximumAggregateUncompressedBytes": 1073741824,
            "maximumCentralDirectoryBytesPerArchive": 8388608,
            "maximumComponentBytes": 255,
            "maximumEntriesPerArchive": 20000,
            "maximumJsonReceiptOrFailureBytes": 2097152,
            "maximumModResponseBytesPerTuple": 1048576,
            "maximumPathBytes": 1024,
            "maximumPathComponents": 64,
            "maximumSingleFileBytes": 134217728,
            "maximumUncompressedBytesPerArchive": 134217728,
            "maximumZipResponseBytesPerTuple": 16777216,
            "perRequestDeadlineMilliseconds": 30000,
            "wholeWaveDeadlineMilliseconds": 600000,
        },
        "E_ABSOLUTE_LIMITS",
    )
    preservation = document.get("v1AndV2PreservationContract")
    require(
        type(preservation) is dict
        and preservation.get("v1RevocationSentinelRetained") is True
        and all(
            preservation.get(name) is False
            for name in (
                "v1RetryAllowed",
                "v2ClaimDeletionAllowed",
                "v2FailureReceiptDeletionAllowed",
                "v2PermitReuseAllowed",
                "v2RunnerExecuteAllowed",
                "v2AutomaticRetryAllowed",
                "v2StagingResumeAllowed",
            )
        ),
        "E_V2_PRESERVATION",
    )
    namespace = document.get("v3NamespaceContract")
    require(
        type(namespace) is dict
        and namespace.get("v3OrderedResourceSetSha256")
        == "a2476fb8d0e37a2e3411b02186ea25647c1e4b40fc1f8353d383304e906594ee"
        and namespace.get("sourceV2OrderedResourceSetSha256")
        == COMMON.EXPECTED_V2_ORDERED_RESOURCE_SET_SHA256
        and namespace.get("resumeFromV2StagingAllowed") is False,
        "E_V3_NAMESPACE_CONTRACT",
    )
    boundary = document.get("personalProjectBoundary")
    require(
        type(boundary) is dict
        and boundary.get("projectOwnership") == "personal_single_owner"
        and boundary.get("repositoryOwnerIdentityProofRequired") is False
        and boundary.get("externalAuthenticationRequired") is False
        and boundary.get("credentialsAllowed") is False
        and boundary.get("privateKeyRequired") is False
        and boundary.get("signatureRequired") is False
        and boundary.get("tokenRequired") is False
        and boundary.get("passwordRequired") is False
        and boundary.get("userActionRequired") is False,
        "E_PERSONAL_PROJECT_BOUNDARY",
    )


def validate_v2_terminal(
    inputs: Any,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    permit = COMMON.strict_json(inputs.raw(V2_PERMIT_PATH), V2_PERMIT_PATH)
    COMMON.validate_content_binding(
        permit,
        scope="permit_without_contentBinding",
        expected=EXPECTED_V2_PERMIT_CONTENT_SHA256,
    )
    claim = COMMON.strict_json(inputs.raw(V2_CLAIM_PATH), V2_CLAIM_PATH)
    failure = COMMON.strict_json(
        inputs.raw(V2_FAILURE_PATH),
        V2_FAILURE_PATH,
    )
    require(
        claim
        == {
            "attemptId": "ded0d0c11ee0ed5740be530abe7f1a8e",
            "automaticRetryAllowed": False,
            "claimType": (
                "aetherlink.g2-pion-dependency-wave2-v2-one-use-claim"
            ),
            "createdAt": "2026-07-24T08:07:31Z",
            "decisionContentSha256": COMMON.EXPECTED_DECISION_CONTENT_SHA256,
            "decisionId": (
                "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-"
                "identity-and-acquisition-decision-wave2-v1"
            ),
            "orderedResourceSetSha256": (
                COMMON.EXPECTED_V2_ORDERED_RESOURCE_SET_SHA256
            ),
            "permitContentSha256": EXPECTED_V2_PERMIT_CONTENT_SHA256,
            "permitId": (
                "g2-pion-ice-v4.3.0-rung3-dependency-wave2-"
                "execution-permit-v2"
            ),
            "rule": (
                "claim_persists_after_any_network_attempt_and_blocks_retry"
            ),
            "schemaVersion": "1.0",
            "userActionRequired": False,
        },
        "E_V2_CLAIM_STATE",
    )
    counters = {name: failure.get(name) for name in COMMON.COUNTER_NAMES}
    COMMON.validate_counters(counters)
    require(
        failure.get("documentType")
        == "aetherlink.g2-pion-dependency-wave2-v2-acquisition-failure"
        and failure.get("status")
        == "wave2_v2_acquisition_failed_permit_consumed"
        and failure.get("result")
        == "no_wave2_dependency_source_set_accepted"
        and failure.get("permitId") == claim["permitId"]
        and failure.get("permitContentSha256")
        == EXPECTED_V2_PERMIT_CONTENT_SHA256
        and failure.get("claimRawSha256")
        == EXPECTED_V2_CLAIM_RAW_SHA256
        and failure.get("failureCode") == "E_ZIP_COMPRESSION_RATIO"
        and failure.get("phase") == "zip"
        and failure.get("failedRequestOrdinal") == 4
        and failure.get("failedTupleId") == "wave2-002-fb2873f66a36"
        and failure.get("failedTupleOrder") == 2
        and failure.get("failedResourceKind") == "zip"
        and list(counters.values()) == [4, 4, 3, 2, 1, 1]
        and failure.get("safeNumericObservations") == {}
        and failure.get("acceptedArtifactCount") == 0
        and failure.get("acceptedTupleCount") == 0
        and failure.get("finalSetPublished") is False
        and failure.get("automaticRetryAllowed") is False
        and failure.get("externalAuthenticationRequired") is False
        and failure.get("userActionRequired") is False,
        "E_V2_FAILURE_STATE",
    )
    wave = root / V2_WAVE_PARENT_PATH
    info = wave.lstat()
    require(
        stat.S_ISDIR(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and info.st_uid == os.geteuid()
        and stat.S_IMODE(info.st_mode) == 0o700
        and os.listdir(wave) == [],
        "E_V2_NAMESPACE",
    )
    parent = root / str(COMMON.DEPENDENCY_PARENT)
    require(
        not any(
            name.startswith(COMMON.STAGING_PREFIX)
            for name in os.listdir(parent)
        ),
        "E_V2_NAMESPACE",
    )
    for relative in (
        COMMON.FINAL_DIRECTORY_PATH,
        COMMON.SUCCESS_RECEIPT_PATH,
        COMMON.MANIFEST_PATH,
        COMMON.READBACK_RECEIPT_PATH,
        COMMON.READBACK_MANIFEST_PATH,
    ):
        require(path_absent(root, relative), "E_V2_NAMESPACE")
    return claim, failure


def validate_repository(
    root: Path = ROOT,
    *,
    require_v3_clean: bool = True,
) -> dict[str, Any]:
    global ROOT
    ROOT = root.resolve()
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode, "E_INTERPRETER")
    inputs = COMMON.HeldInputSet(ROOT, recovery_bindings())
    try:
        document = COMMON.strict_json(
            inputs.raw(RECOVERY_PATH),
            RECOVERY_PATH,
        )
        validate_recovery_document(document)
        validate_v2_terminal(inputs, ROOT)
        sentinel = ROOT / COMMON.V1_REVOCATION_SENTINEL_PATH
        sentinel_info = sentinel.lstat()
        require(
            stat.S_ISREG(sentinel_info.st_mode)
            and stat.S_IMODE(sentinel_info.st_mode) == 0o600
            and sentinel_info.st_nlink == 1,
            "E_V1_REVOCATION",
        )
        if require_v3_clean:
            require(
                all(path_absent(ROOT, path) for path in V3_TERMINAL_PATHS),
                "E_V3_NAMESPACE",
            )
            parent = ROOT / str(COMMON.DEPENDENCY_PARENT)
            require(
                not any(
                    name.startswith(".wave-2-v3-staging-")
                    for name in os.listdir(parent)
                ),
                "E_V3_NAMESPACE",
            )
        v2_runner = COMMON.execute_fixed_module(
            "g2_wave2_recovery_v2_terminal_runner",
            V2_RUNNER_PATH,
            inputs.raw(V2_RUNNER_PATH),
            ROOT,
        )
        preflight = v2_runner.preflight()
        require(
            preflight.get("status")
            == "consumed_failure_recovery_required"
            and preflight.get("permitConsumptionState")
            == "consumed_failure"
            and preflight.get("oneUseState") == "failure"
            and preflight.get("validationPassed") is False
            and preflight.get("nextAction")
            == "prepare_new_versioned_wave2_recovery_decision"
            and preflight.get("networkOperationCount") == 0
            and preflight.get("fileWriteCount") == 0,
            "E_V2_TERMINAL_PREFLIGHT",
        )
        inputs.final_barrier()
        validate_v2_terminal(inputs, ROOT)
        return {
            "status": document["status"],
            "result": document["result"],
            "v2TerminalStateValid": True,
            "v2PermitConsumed": True,
            "v2ClaimRetained": True,
            "v2FailureReceiptRetained": True,
            "v2NetworkRequestAttemptCount": 4,
            "v2ResponseBodyCompletedCount": 4,
            "v2RetryAuthorized": False,
            "v2PartialResumeAuthorized": False,
            "v1RevocationSentinelRetained": True,
            "v3ExecutionAuthorized": False,
            "v3NamespaceCleanRequired": require_v3_clean,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "networkUsed": False,
            "fileWriteCount": 0,
            "nextAction": document["nextAction"],
        }
    finally:
        inputs.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--preflight", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_repository(args.root)
    except COMMON.Wave2Failure as failure:
        print(f"{failure.code}:{failure.phase}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
