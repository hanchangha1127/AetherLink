#!/usr/bin/env python3
"""Acquire the exact G2 Pion dependency wave-one ZIP set through v2 once.

The default mode is a read-only state preflight. ``--execute`` uses the
separate v2 permit and namespace. The immutable v1 runner is loaded only after
its raw SHA-256 is verified and supplies the already-tested bounded HTTPS, ZIP,
filesystem, and deadline primitives.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time
import types
from typing import Any, Mapping, Sequence
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v2.py"
)
EXPECTED_CHECKER_RAW_SHA256 = "35ac6152731f16e84c5ac3e4f6ddfdc04c109b51c01967ef63cc53557f1c2139"
LEGACY_RUNNER_PATH = "script/acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
EXPECTED_LEGACY_RUNNER_RAW_SHA256 = "571985e002c6b819bfbe7153bb445beef27fdcad239a289b492005435c2a0356"
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024

EXPECTED_PERMIT_STATUS = (
    "wave1_v2_dependency_source_acquisition_authorized_not_consumed"
)
EXPECTED_PERMIT_RESULT = (
    "exact_19_public_proxy_zip_requests_v2_authorized_once_not_executed"
)
EXPECTED_PERMIT_NEXT_ACTION = "execute_bound_dependency_source_wave1_v2_once"

DEPENDENCY_PARENT = PurePosixPath(
    "build/offline-source/pion-ice-v4.3.0/dependencies"
)
CLAIM_NAME = ".wave-1-v2.claim"
STAGING_PREFIX = ".wave-1-v2-staging-"
WAVE_PARENT_NAME = "wave-1-v2"
FINAL_DIRECTORY_NAME = "accepted"
FINAL_DIRECTORY_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v2/accepted"
)
SUCCESS_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v2.json"
)
FAILURE_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v2.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v2.json"
)
HISTORICAL_V1_COMPARISON_RATIO = 200
MAXIMUM_SAFE_INTEGER = (1 << 63) - 1
COUNTER_NAMES = (
    "networkRequestAttemptCount",
    "responseBodyCompletedCount",
    "validatedAndStagedTupleCount",
)
SAFE_OBSERVATION_NAMES = frozenset(
    {
        "httpStatus",
        "responseBytes",
        "aggregateBytes",
        "entryOrdinal",
        "entryUncompressedBytes",
        "entryCompressedBytes",
        *COUNTER_NAMES,
    }
)
ALLOWED_FAILURE_CODES = frozenset(
    {
        "E_ACCEPTED_COUNT",
        "E_AGGREGATE_ENTRY_COUNT",
        "E_AGGREGATE_RESPONSE_TOO_LARGE",
        "E_AGGREGATE_UNCOMPRESSED",
        "E_CHECKER_IDENTITY",
        "E_CLAIM_EXISTS",
        "E_CONTENT_ENCODING",
        "E_CONTENT_LENGTH",
        "E_CONTENT_LENGTH_MISMATCH",
        "E_CONTENT_TYPE",
        "E_COUNTER_INVARIANT",
        "E_DEADLINE_ENVIRONMENT",
        "E_EMPTY_RESPONSE",
        "E_FILESYSTEM_CREATE",
        "E_FILESYSTEM_LINK",
        "E_FILESYSTEM_LIST",
        "E_FILESYSTEM_MODE",
        "E_FILESYSTEM_OWNER",
        "E_FILESYSTEM_ROOT",
        "E_FILESYSTEM_ROOT_IDENTITY",
        "E_FILESYSTEM_STAT",
        "E_FILESYSTEM_TYPE",
        "E_FILESYSTEM_WRITE",
        "E_FILE_TOO_LARGE",
        "E_FORBIDDEN_RESPONSE_HEADER",
        "E_GO_MOD_DUPLICATE",
        "E_GO_MOD_ENCODING",
        "E_GO_MOD_H1",
        "E_GO_MOD_MISSING",
        "E_GO_MOD_MODULE",
        "E_HTTP_STATUS",
        "E_INTERNAL",
        "E_MODULE_H1",
        "E_MODULE_PREFIX",
        "E_OUTPUT_EXISTS",
        "E_OUTPUT_IDENTITY",
        "E_OUTPUT_INVENTORY",
        "E_OUTPUT_PUBLISH",
        "E_PATH",
        "E_RECEIPT_TOO_LARGE",
        "E_REDIRECT",
        "E_RENAME_EXCL_UNAVAILABLE",
        "E_REQUEST_COUNT",
        "E_REQUEST_DEADLINE",
        "E_RESPONSE_TOO_LARGE",
        "E_STAGING_COLLISION",
        "E_STAGING_CREATE",
        "E_STAGING_EXISTS",
        "E_STAGING_STATE",
        "E_TOCTOU",
        "E_TRANSPORT",
        "E_WAVE_DEADLINE",
        "E_WAVE_TUPLES",
        "E_ZIP64",
        "E_ZIP_CASE_COLLISION",
        "E_ZIP_CENTRAL_DIRECTORY",
        "E_ZIP_COMMENT",
        "E_ZIP_COMPRESSED_SIZE",
        "E_ZIP_COMPRESSION",
        "E_ZIP_CREATOR_SYSTEM",
        "E_ZIP_DATA_DESCRIPTOR",
        "E_ZIP_DIRECTORY_ENTRY",
        "E_ZIP_DUPLICATE",
        "E_ZIP_ENCRYPTED",
        "E_ZIP_ENTRY_COUNT",
        "E_ZIP_EOCD",
        "E_ZIP_EXTRA",
        "E_ZIP_FILE_SIZE",
        "E_ZIP_FLAGS",
        "E_ZIP_FORMAT",
        "E_ZIP_LOCAL_HEADER",
        "E_ZIP_MULTIDISK",
        "E_ZIP_NAME_ENCODING",
        "E_ZIP_PATH",
        "E_ZIP_RATIO",
        "E_ZIP_READ",
        "E_ZIP_RESULT",
        "E_ZIP_SPECIAL_FILE",
        "E_ZIP_SPECIAL_MODE",
        "E_ZIP_TELEMETRY",
        "E_ZIP_TRAILING",
        "E_ZIP_UNCOMPRESSED",
    }
)
ALLOWED_FAILURE_PHASES = frozenset(
    {"download", "execution", "filesystem", "preflight", "publication", "zip"}
)
TUPLE_REQUIRED_FAILURE_PHASES = frozenset({"download", "zip"})
TUPLE_FORBIDDEN_FAILURE_PHASES = frozenset({"preflight", "publication"})
FAILURE_DOCUMENT_KEYS = frozenset(
    {
        "documentType",
        "schemaVersion",
        "status",
        "result",
        "permitId",
        "permitContentSha256",
        "recoveryContentSha256",
        "failureCode",
        "phase",
        "failedTupleId",
        "failedTupleOrder",
        "safeNumericObservations",
        *COUNTER_NAMES,
        "acceptedArtifactCount",
        "claimRetained",
        "claimRawSha256",
        "finalSetPublished",
        "automaticRetryAllowed",
        "legacyCompletedRequestCountForbidden",
        "repositoryOwnerIdentityProofRequired",
        "externalAuthenticationRequired",
        "userActionRequired",
        "nextAction",
    }
)
SUCCESS_RECEIPT_KEYS = frozenset(
    {
        "documentType",
        "schemaVersion",
        "status",
        "result",
        "permitId",
        "permitContentSha256",
        "recoveryContentSha256",
        "decisionId",
        "decisionContentSha256",
        "claimRawSha256",
        *COUNTER_NAMES,
        "acceptedArtifactCount",
        "aggregateRawByteSize",
        "aggregateEntryCount",
        "aggregateUncompressedByteCount",
        "archiveCountExceedingHistoricalV1Ratio",
        "orderedSourceSetSha256",
        "sources",
        "compressionRatioPolicy",
        "legacyCompletedRequestCountForbidden",
        "independentReadbackPassed",
        "dependencySourceReviewed",
        "dependencyClosureComplete",
        "candidateSelected",
        "librarySelected",
        "repositoryOwnerIdentityProofRequired",
        "externalAuthenticationRequired",
        "userActionRequired",
        "nextAction",
    }
)
SUCCESS_SOURCE_KEYS = frozenset(
    {
        "order",
        "tupleId",
        "module",
        "version",
        "url",
        "outputFileName",
        "rawByteSize",
        "rawSha256",
        "moduleZipH1",
        "goModH1",
        "entryCount",
        "uncompressedByteCount",
        "modulePrefix",
        "compressionTelemetry",
        "mode",
        "linkCount",
    }
)
COMPRESSION_TELEMETRY_KEYS = frozenset(
    {
        "policy",
        "historicalV1ComparisonRatio",
        "maximumRatioEntryOrdinal",
        "maximumRatioEntryUncompressedBytes",
        "maximumRatioEntryCompressedBytes",
        "maximumRatioExceededHistoricalV1Limit",
        "floatingPointRatioUsed",
        "entryNameOrBodyRecorded",
    }
)
SUCCESS_MANIFEST_KEYS = frozenset(
    {
        "documentType",
        "schemaVersion",
        "status",
        "result",
        "permitId",
        "permitContentSha256",
        "successReceiptPath",
        "successReceiptRawSha256",
        "finalDirectoryPath",
        *COUNTER_NAMES,
        "acceptedArtifactCount",
        "orderedSourceSetSha256",
        "manifestWrittenLast",
        "independentReadbackPassed",
        "repositoryOwnerIdentityProofRequired",
        "externalAuthenticationRequired",
        "userActionRequired",
        "nextAction",
    }
)


class RunnerFailure(RuntimeError):
    """A bounded v2 failure safe to serialize."""

    def __init__(
        self,
        code: str,
        phase: str,
        *,
        tuple_id: str | None = None,
        tuple_order: int | None = None,
        observations: Mapping[str, int] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase
        self.tuple_id = tuple_id
        self.tuple_order = tuple_order
        self.observations = dict(observations or {})


def require(
    condition: bool,
    code: str,
    phase: str,
    *,
    tuple_id: str | None = None,
    tuple_order: int | None = None,
    observations: Mapping[str, int] | None = None,
) -> None:
    if not condition:
        raise RunnerFailure(
            code,
            phase,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            observations=observations,
        )


def require_isolated_interpreter() -> None:
    require(sys.flags.isolated == 1, "E_INTERPRETER", "preflight")
    require(sys.dont_write_bytecode, "E_INTERPRETER", "preflight")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def read_stable_source(relative: str, maximum_bytes: int) -> bytes:
    path = ROOT / relative
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise RunnerFailure("E_TOOL_IDENTITY", "preflight") from error
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid()
            and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and before.st_size <= maximum_bytes,
            "E_TOOL_IDENTITY",
            "preflight",
        )
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        require(
            len(raw) == before.st_size
            and (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "E_TOOL_IDENTITY",
            "preflight",
        )
        return raw
    finally:
        os.close(fd)


def execute_fixed_module(
    name: str,
    relative: str,
    raw: bytes,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / relative),
            "__loader__": None,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(
                raw,
                relative,
                "exec",
                flags=0,
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise RunnerFailure("E_TOOL_LOAD", "preflight") from error
    return module


def configure_legacy(legacy: types.ModuleType) -> None:
    legacy.ROOT = ROOT
    legacy.CLAIM_NAME = CLAIM_NAME
    legacy.STAGING_PREFIX = STAGING_PREFIX
    legacy.DEPENDENCY_PARENT = DEPENDENCY_PARENT
    legacy.WAVE_PARENT_NAME = WAVE_PARENT_NAME
    legacy.FINAL_DIRECTORY_NAME = FINAL_DIRECTORY_NAME
    legacy.SUCCESS_RECEIPT_PATH = SUCCESS_RECEIPT_PATH
    legacy.FAILURE_RECEIPT_PATH = FAILURE_RECEIPT_PATH
    legacy.MANIFEST_PATH = MANIFEST_PATH


def load_validated_authority() -> tuple[types.ModuleType, dict[str, Any], types.ModuleType]:
    require_isolated_interpreter()
    checker_raw = read_stable_source(CHECKER_PATH, MAXIMUM_TOOL_BYTES)
    require(
        sha256_bytes(checker_raw) == EXPECTED_CHECKER_RAW_SHA256,
        "E_CHECKER_IDENTITY",
        "preflight",
    )
    checker = execute_fixed_module(
        "g2_dependency_wave1_v2_permit_checker_trust_root",
        CHECKER_PATH,
        checker_raw,
    )
    try:
        authority = checker.validate_repository(ROOT)
    except Exception as error:
        raise RunnerFailure("E_PERMIT_VALIDATION", "preflight") from error
    require(isinstance(authority, dict), "E_PERMIT_VALIDATION", "preflight")
    permit = authority.get("permit")
    require(isinstance(permit, dict), "E_PERMIT_VALIDATION", "preflight")
    require(
        permit.get("status") == EXPECTED_PERMIT_STATUS
        and permit.get("result") == EXPECTED_PERMIT_RESULT
        and permit.get("nextAction") == EXPECTED_PERMIT_NEXT_ACTION,
        "E_PERMIT_STATE",
        "preflight",
    )

    legacy_raw = read_stable_source(LEGACY_RUNNER_PATH, MAXIMUM_TOOL_BYTES)
    require(
        sha256_bytes(legacy_raw) == EXPECTED_LEGACY_RUNNER_RAW_SHA256,
        "E_LEGACY_IDENTITY",
        "preflight",
    )
    legacy = execute_fixed_module(
        "g2_dependency_wave1_v1_immutable_primitives",
        LEGACY_RUNNER_PATH,
        legacy_raw,
    )
    configure_legacy(legacy)
    return checker, authority, legacy


def safe_integer(value: Any) -> bool:
    return type(value) is int and 0 <= value <= MAXIMUM_SAFE_INTEGER


def bounded_observations(values: Mapping[str, Any]) -> dict[str, int]:
    return {
        key: value
        for key, value in values.items()
        if key in SAFE_OBSERVATION_NAMES and safe_integer(value)
    }


def convert_legacy_failure(
    legacy: types.ModuleType,
    error: Exception,
    *,
    tuple_id: str | None = None,
    tuple_order: int | None = None,
    extra_observations: Mapping[str, int] | None = None,
) -> RunnerFailure:
    if isinstance(error, RunnerFailure):
        return RunnerFailure(
            error.code if error.code in ALLOWED_FAILURE_CODES else "E_INTERNAL",
            (
                error.phase
                if error.phase in ALLOWED_FAILURE_PHASES
                else "execution"
            ),
            tuple_id=error.tuple_id or tuple_id,
            tuple_order=(
                error.tuple_order
                if error.tuple_order is not None
                else tuple_order
            ),
            observations=bounded_observations(error.observations),
        )
    if isinstance(error, legacy.AcquisitionFailure):
        observations = dict(getattr(error, "observations", {}) or {})
        observations.update(extra_observations or {})
        code = str(error.code)
        phase = str(error.phase)
        return RunnerFailure(
            code if code in ALLOWED_FAILURE_CODES else "E_INTERNAL",
            phase if phase in ALLOWED_FAILURE_PHASES else "execution",
            tuple_id=getattr(error, "tuple_id", None) or tuple_id,
            tuple_order=tuple_order,
            observations=bounded_observations(observations),
        )
    return RunnerFailure(
        "E_INTERNAL",
        "execution",
        tuple_id=tuple_id,
        tuple_order=tuple_order,
    )


def collect_compression_telemetry(
    legacy: types.ModuleType,
    fd: int,
    item: Mapping[str, Any],
) -> dict[str, Any]:
    tuple_id = str(item["tupleId"])
    tuple_order = int(item["order"])
    legacy.validate_regular_descriptor(fd, tuple_id, owner_only=True)
    os.lseek(fd, 0, os.SEEK_SET)
    best_ordinal = 0
    best_uncompressed = 0
    best_compressed = 0
    try:
        with os.fdopen(os.dup(fd), "rb") as archive_file:
            with zipfile.ZipFile(archive_file, "r") as archive:
                for ordinal, entry in enumerate(archive.infolist(), start=1):
                    uncompressed = entry.file_size
                    compressed = entry.compress_size
                    require(
                        safe_integer(ordinal)
                        and safe_integer(uncompressed)
                        and safe_integer(compressed),
                        "E_ZIP_TELEMETRY",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                    )
                    if uncompressed == 0:
                        continue
                    require(
                        compressed > 0,
                        "E_ZIP_COMPRESSED_SIZE",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        observations={
                            "entryOrdinal": ordinal,
                            "entryUncompressedBytes": uncompressed,
                            "entryCompressedBytes": compressed,
                        },
                    )
                    if (
                        best_ordinal == 0
                        or uncompressed * best_compressed
                        > best_uncompressed * compressed
                    ):
                        best_ordinal = ordinal
                        best_uncompressed = uncompressed
                        best_compressed = compressed
    except RunnerFailure:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise RunnerFailure(
            "E_ZIP_FORMAT",
            "zip",
            tuple_id=tuple_id,
            tuple_order=tuple_order,
        ) from error
    return {
        "policy": "non_gating_bounded_telemetry",
        "historicalV1ComparisonRatio": HISTORICAL_V1_COMPARISON_RATIO,
        "maximumRatioEntryOrdinal": best_ordinal,
        "maximumRatioEntryUncompressedBytes": best_uncompressed,
        "maximumRatioEntryCompressedBytes": best_compressed,
        "maximumRatioExceededHistoricalV1Limit": (
            best_ordinal > 0
            and best_uncompressed
            > best_compressed * HISTORICAL_V1_COMPARISON_RATIO
        ),
        "floatingPointRatioUsed": False,
        "entryNameOrBodyRecorded": False,
    }


def inspect_module_zip_v2(
    legacy: types.ModuleType,
    fd: int,
    item: Mapping[str, Any],
    limits: Mapping[str, Any],
    *,
    aggregate_entries_before: int,
    aggregate_uncompressed_before: int,
) -> dict[str, Any]:
    tuple_id = str(item["tupleId"])
    tuple_order = int(item["order"])
    telemetry = collect_compression_telemetry(legacy, fd, item)
    effective_limits = dict(limits)
    effective_limits["maximumCompressionRatio"] = max(
        1,
        int(limits["maximumSingleFileBytes"]),
    )
    try:
        result = legacy.inspect_module_zip(
            fd,
            item,
            effective_limits,
            aggregate_entries_before=aggregate_entries_before,
            aggregate_uncompressed_before=aggregate_uncompressed_before,
        )
    except Exception as error:
        observations: dict[str, int] = {}
        if telemetry["maximumRatioEntryOrdinal"] > 0:
            observations = {
                "entryOrdinal": telemetry["maximumRatioEntryOrdinal"],
                "entryUncompressedBytes": telemetry[
                    "maximumRatioEntryUncompressedBytes"
                ],
                "entryCompressedBytes": telemetry[
                    "maximumRatioEntryCompressedBytes"
                ],
            }
        raise convert_legacy_failure(
            legacy,
            error,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            extra_observations=observations,
        ) from None
    require(isinstance(result, dict), "E_ZIP_RESULT", "zip")
    result = dict(result)
    result["compressionTelemetry"] = telemetry
    return result


def validate_counters(
    counters: Mapping[str, int],
    maximum: int = 19,
) -> None:
    attempted = counters["networkRequestAttemptCount"]
    response = counters["responseBodyCompletedCount"]
    staged = counters["validatedAndStagedTupleCount"]
    require(
        all(safe_integer(value) for value in (attempted, response, staged))
        and 0 <= staged <= response <= attempted <= maximum,
        "E_COUNTER_INVARIANT",
        "execution",
    )


def enforce_download_file_mode(
    output_fd: int,
    tuple_id: str,
    tuple_order: int,
) -> None:
    try:
        os.fchmod(output_fd, 0o600)
    except OSError as error:
        raise RunnerFailure(
            "E_FILESYSTEM_MODE",
            "filesystem",
            tuple_id=tuple_id,
            tuple_order=tuple_order,
        ) from error


class AttemptCountingOpener:
    def __init__(self, delegate: Any, counters: dict[str, int]) -> None:
        self.delegate = delegate
        self.counters = counters

    def open(self, request: Any, *, timeout: float) -> Any:
        self.counters["networkRequestAttemptCount"] += 1
        validate_counters(self.counters)
        return self.delegate.open(request, timeout=timeout)


def create_claim_v2(
    legacy: types.ModuleType,
    parent_fd: int,
    permit: Mapping[str, Any],
) -> str:
    payload = canonical_json_bytes(
        {
            "claimType": "aetherlink.g2-pion-dependency-wave1-v2-one-use-claim",
            "schemaVersion": "2.0",
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "recoveryContentSha256": permit["recoveryBinding"]["contentSha256"],
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rule": (
                "v2_claim_persists_after_any_network_attempt_and_blocks_retry"
            ),
            "v1ArtifactReuseAllowed": False,
        }
    )
    return legacy.create_exclusive_file(
        parent_fd,
        CLAIM_NAME,
        payload,
        maximum_bytes=64 * 1024,
    )


def ordered_source_set_digest_v2(rows: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "schema": "aetherlink.g2-pion-dependency-source-set-digest.v2",
                "sources": list(rows),
            }
        )
    )


def safe_failure_document_v2(
    permit: Mapping[str, Any],
    failure: RunnerFailure,
    counters: Mapping[str, int],
    *,
    claim_sha256: str | None,
    final_set_published: bool,
) -> dict[str, Any]:
    validate_counters(counters)
    tuple_context_complete = (
        failure.tuple_id is None and failure.tuple_order is None
    ) or (
        isinstance(failure.tuple_id, str)
        and bool(failure.tuple_id)
        and safe_integer(failure.tuple_order)
        and failure.tuple_order > 0
    )
    require(
        failure.code in ALLOWED_FAILURE_CODES
        and failure.phase in ALLOWED_FAILURE_PHASES
        and tuple_context_complete
        and (
            failure.phase not in TUPLE_REQUIRED_FAILURE_PHASES
            or failure.tuple_id is not None
        )
        and isinstance(claim_sha256, str)
        and len(claim_sha256) == 64
        and all(character in "0123456789abcdef" for character in claim_sha256)
        and final_set_published is False,
        "E_FAILURE_STATE",
        "execution",
    )
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v2-acquisition-failure"
        ),
        "schemaVersion": "2.0",
        "status": "wave1_v2_acquisition_failed_permit_consumed",
        "result": "no_dependency_source_set_accepted",
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "recoveryContentSha256": permit["recoveryBinding"]["contentSha256"],
        "failureCode": failure.code,
        "phase": failure.phase,
        "failedTupleId": failure.tuple_id,
        "failedTupleOrder": failure.tuple_order,
        "safeNumericObservations": bounded_observations(failure.observations),
        "networkRequestAttemptCount": counters["networkRequestAttemptCount"],
        "responseBodyCompletedCount": counters["responseBodyCompletedCount"],
        "validatedAndStagedTupleCount": counters[
            "validatedAndStagedTupleCount"
        ],
        "acceptedArtifactCount": 0,
        "claimRetained": claim_sha256 is not None,
        "claimRawSha256": claim_sha256,
        "finalSetPublished": final_set_published,
        "automaticRetryAllowed": False,
        "legacyCompletedRequestCountForbidden": True,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "prepare_new_versioned_wave1_v2_recovery_decision",
    }


def classify_preflight_state(state: Mapping[str, Any]) -> str:
    invalid = state["dependencyParentInvalid"] or state["waveParentInvalid"]
    clean = (
        not invalid
        and not state["claimPresent"]
        and state["stagingEntryCount"] == 0
        and not state["finalDirectoryPresent"]
        and not state["successReceiptPresent"]
        and not state["failureReceiptPresent"]
        and not state["manifestPresent"]
    )
    success = (
        not invalid
        and state["claimPresent"]
        and state["stagingEntryCount"] == 0
        and state["finalDirectoryPresent"]
        and state["successReceiptPresent"]
        and not state["failureReceiptPresent"]
        and state["manifestPresent"]
    )
    failure = (
        not invalid
        and state["claimPresent"]
        and state["stagingEntryCount"] == 0
        and not state["finalDirectoryPresent"]
        and not state["successReceiptPresent"]
        and state["failureReceiptPresent"]
        and not state["manifestPresent"]
    )
    if clean:
        return "clean"
    if success:
        return "success"
    if failure:
        return "failure"
    return "blocked"


def preflight_validation_passed(classification: str) -> bool:
    return classification in {"clean", "success"}


def read_runtime_json(
    legacy: types.ModuleType,
    relative: str,
    maximum_bytes: int,
) -> tuple[dict[str, Any], bytes]:
    raw = legacy.read_stable_regular_file(ROOT / relative, maximum_bytes)
    document = legacy.strict_json(raw, relative)
    require(isinstance(document, dict), "E_RUNTIME_ARTIFACT", "preflight")
    return document, raw


def validate_claim_document(
    claim: Mapping[str, Any],
    permit: Mapping[str, Any],
) -> None:
    require(
        set(claim)
        == {
            "claimType",
            "schemaVersion",
            "permitId",
            "permitContentSha256",
            "recoveryContentSha256",
            "createdAt",
            "rule",
            "v1ArtifactReuseAllowed",
        }
        and claim["claimType"]
        == "aetherlink.g2-pion-dependency-wave1-v2-one-use-claim"
        and claim["schemaVersion"] == "2.0"
        and claim["permitId"] == permit["permitId"]
        and claim["permitContentSha256"] == permit["contentBinding"]["sha256"]
        and claim["recoveryContentSha256"]
        == permit["recoveryBinding"]["contentSha256"]
        and claim["rule"]
        == "v2_claim_persists_after_any_network_attempt_and_blocks_retry"
        and claim["v1ArtifactReuseAllowed"] is False,
        "E_CLAIM_STATE",
        "preflight",
    )


def validate_failure_document(
    failure: Mapping[str, Any],
    permit: Mapping[str, Any],
    claim_sha256: str,
    decision: Mapping[str, Any],
) -> None:
    require(
        isinstance(failure, dict) and set(failure) == FAILURE_DOCUMENT_KEYS,
        "E_FAILURE_STATE",
        "preflight",
    )
    counters = {
        name: failure[name]
        for name in COUNTER_NAMES
    }
    validate_counters(counters)
    observations = failure["safeNumericObservations"]
    require(
        isinstance(observations, dict)
        and set(observations).issubset(SAFE_OBSERVATION_NAMES)
        and bounded_observations(observations) == observations,
        "E_FAILURE_STATE",
        "preflight",
    )
    tuple_id = failure["failedTupleId"]
    tuple_order = failure["failedTupleOrder"]
    tuple_rows = {
        item["order"]: item["tupleId"]
        for item in decision["wave"]["tuples"]
    }
    tuple_context_valid = (
        tuple_id is None
        and tuple_order is None
        and failure["phase"] not in TUPLE_REQUIRED_FAILURE_PHASES
    ) or (
        failure["phase"] not in TUPLE_FORBIDDEN_FAILURE_PHASES
        and type(tuple_order) is int
        and tuple_order in tuple_rows
        and type(tuple_id) is str
        and tuple_rows[tuple_order] == tuple_id
    )
    require(
        failure["documentType"]
        == "aetherlink.g2-pion-dependency-wave1-v2-acquisition-failure"
        and failure["schemaVersion"] == "2.0"
        and failure["status"]
        == "wave1_v2_acquisition_failed_permit_consumed"
        and failure["result"] == "no_dependency_source_set_accepted"
        and failure["permitId"] == permit["permitId"]
        and failure["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and failure["recoveryContentSha256"]
        == permit["recoveryBinding"]["contentSha256"]
        and isinstance(failure["failureCode"], str)
        and failure["failureCode"] in ALLOWED_FAILURE_CODES
        and isinstance(failure["phase"], str)
        and failure["phase"] in ALLOWED_FAILURE_PHASES
        and tuple_context_valid
        and all(
            name not in observations
            or observations[name] == counters[name]
            for name in COUNTER_NAMES
        )
        and failure["claimRetained"] is True
        and failure["claimRawSha256"] == claim_sha256
        and type(failure["acceptedArtifactCount"]) is int
        and failure["acceptedArtifactCount"] == 0
        and failure["finalSetPublished"] is False
        and failure["automaticRetryAllowed"] is False
        and failure["legacyCompletedRequestCountForbidden"] is True
        and failure["repositoryOwnerIdentityProofRequired"] is False
        and failure["externalAuthenticationRequired"] is False
        and failure["userActionRequired"] is False
        and failure["nextAction"]
        == "prepare_new_versioned_wave1_v2_recovery_decision"
        and ("completed" + "RequestCount") not in failure,
        "E_FAILURE_STATE",
        "preflight",
    )


def validate_compression_telemetry(
    telemetry: Any,
    *,
    entry_count: int,
) -> bool:
    if not isinstance(telemetry, dict) or set(telemetry) != COMPRESSION_TELEMETRY_KEYS:
        return False
    ordinal = telemetry["maximumRatioEntryOrdinal"]
    uncompressed = telemetry["maximumRatioEntryUncompressedBytes"]
    compressed = telemetry["maximumRatioEntryCompressedBytes"]
    if not all(safe_integer(value) for value in (ordinal, uncompressed, compressed)):
        return False
    if ordinal == 0:
        ratio_fields_valid = (
            uncompressed == 0
            and compressed == 0
            and telemetry["maximumRatioExceededHistoricalV1Limit"] is False
        )
    else:
        ratio_fields_valid = (
            1 <= ordinal <= entry_count
            and uncompressed > 0
            and compressed > 0
            and telemetry["maximumRatioExceededHistoricalV1Limit"]
            is (
                uncompressed
                > compressed * HISTORICAL_V1_COMPARISON_RATIO
            )
        )
    return (
        telemetry["policy"] == "non_gating_bounded_telemetry"
        and telemetry["historicalV1ComparisonRatio"]
        == HISTORICAL_V1_COMPARISON_RATIO
        and ratio_fields_valid
        and telemetry["floatingPointRatioUsed"] is False
        and telemetry["entryNameOrBodyRecorded"] is False
    )


def validate_success_sources(
    sources: Any,
    decision: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> tuple[int, int, int, int]:
    require(
        isinstance(sources, list) and len(sources) == 19,
        "E_SUCCESS_STATE",
        "preflight",
    )
    tuples = sorted(decision["wave"]["tuples"], key=lambda item: item["order"])
    require(len(tuples) == 19, "E_SUCCESS_STATE", "preflight")
    aggregate_bytes = 0
    aggregate_entries = 0
    aggregate_uncompressed = 0
    exceeded_count = 0
    for source, item in zip(sources, tuples):
        require(
            isinstance(source, dict) and set(source) == SUCCESS_SOURCE_KEYS,
            "E_SUCCESS_STATE",
            "preflight",
        )
        raw_size = source["rawByteSize"]
        entry_count = source["entryCount"]
        uncompressed = source["uncompressedByteCount"]
        expected_name = PurePosixPath(item["outputPath"]).name
        require(
            type(source["order"]) is int
            and source["order"] == item["order"]
            and source["tupleId"] == item["tupleId"]
            and source["module"] == item["module"]
            and source["version"] == item["version"]
            and source["url"] == item["url"]
            and source["outputFileName"] == expected_name
            and safe_integer(raw_size)
            and 0 < raw_size <= limits["maximumResponseBytesPerArchive"]
            and isinstance(source["rawSha256"], str)
            and len(source["rawSha256"]) == 64
            and all(
                character in "0123456789abcdef"
                for character in source["rawSha256"]
            )
            and source["moduleZipH1"] == item["moduleZipH1"]
            and source["goModH1"] == item["goModH1"]
            and safe_integer(entry_count)
            and 0 < entry_count <= limits["maximumEntriesPerArchive"]
            and safe_integer(uncompressed)
            and 0 < uncompressed <= limits["maximumUncompressedBytesPerArchive"]
            and source["modulePrefix"]
            == f"{item['module']}@{item['version']}/"
            and validate_compression_telemetry(
                source["compressionTelemetry"],
                entry_count=entry_count,
            )
            and source["mode"] == "0600"
            and type(source["linkCount"]) is int
            and source["linkCount"] == 1,
            "E_SUCCESS_STATE",
            "preflight",
        )
        aggregate_bytes += raw_size
        aggregate_entries += entry_count
        aggregate_uncompressed += uncompressed
        exceeded_count += int(
            source["compressionTelemetry"][
                "maximumRatioExceededHistoricalV1Limit"
            ]
        )
    require(
        aggregate_bytes <= limits["maximumAggregateResponseBytes"]
        and aggregate_bytes <= limits["maximumRetainedBytes"]
        and aggregate_entries <= limits["maximumAggregateEntries"]
        and aggregate_uncompressed
        <= limits["maximumAggregateUncompressedBytes"],
        "E_SUCCESS_STATE",
        "preflight",
    )
    return (
        aggregate_bytes,
        aggregate_entries,
        aggregate_uncompressed,
        exceeded_count,
    )


def validate_success_final_inventory(
    legacy: types.ModuleType,
    root_fd: int,
    sources: Sequence[Mapping[str, Any]],
    limits: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> None:
    parts = legacy.validate_relative_path(FINAL_DIRECTORY_PATH)
    final_fd = legacy.open_directory_chain(
        root_fd,
        parts,
        create=False,
        owner_only_from=len(parts) - 2,
    )
    try:
        expected_names = sorted(source["outputFileName"] for source in sources)
        require(
            len(set(expected_names)) == 19
            and legacy.list_names(final_fd) == expected_names,
            "E_OUTPUT_INVENTORY",
            "preflight",
        )
        tuples = sorted(
            decision["wave"]["tuples"],
            key=lambda item: item["order"],
        )
        require(len(tuples) == 19, "E_OUTPUT_INVENTORY", "preflight")
        aggregate_entries = 0
        aggregate_uncompressed = 0
        for source, item in zip(sources, tuples):
            name = source["outputFileName"]
            try:
                fd = os.open(name, legacy.file_open_flags(), dir_fd=final_fd)
            except OSError as error:
                raise RunnerFailure(
                    "E_OUTPUT_INVENTORY",
                    "preflight",
                ) from error
            try:
                before = legacy.validate_regular_descriptor(
                    fd,
                    source["tupleId"],
                    owner_only=True,
                )
                require(
                    before.st_size == source["rawByteSize"]
                    and before.st_size
                    <= limits["maximumResponseBytesPerArchive"],
                    "E_OUTPUT_IDENTITY",
                    "preflight",
                )
                try:
                    observed_archive = inspect_module_zip_v2(
                        legacy,
                        fd,
                        item,
                        limits,
                        aggregate_entries_before=aggregate_entries,
                        aggregate_uncompressed_before=aggregate_uncompressed,
                    )
                except Exception as error:
                    raise RunnerFailure(
                        "E_OUTPUT_IDENTITY",
                        "preflight",
                    ) from error
                require(
                    observed_archive
                    == {
                        "moduleZipH1": source["moduleZipH1"],
                        "goModH1": source["goModH1"],
                        "entryCount": source["entryCount"],
                        "uncompressedByteCount": source[
                            "uncompressedByteCount"
                        ],
                        "modulePrefix": source["modulePrefix"],
                        "compressionTelemetry": source[
                            "compressionTelemetry"
                        ],
                    },
                    "E_OUTPUT_IDENTITY",
                    "preflight",
                )
                aggregate_entries += observed_archive["entryCount"]
                aggregate_uncompressed += observed_archive[
                    "uncompressedByteCount"
                ]
                os.lseek(fd, 0, os.SEEK_SET)
                digest = hashlib.sha256()
                observed_size = 0
                while True:
                    chunk = os.read(
                        fd,
                        min(
                            64 * 1024,
                            before.st_size + 1 - observed_size,
                        ),
                    )
                    if not chunk:
                        break
                    observed_size += len(chunk)
                    require(
                        observed_size <= before.st_size,
                        "E_OUTPUT_IDENTITY",
                        "preflight",
                    )
                    digest.update(chunk)
                after = legacy.validate_regular_descriptor(
                    fd,
                    source["tupleId"],
                    owner_only=True,
                )
                require(
                    observed_size == before.st_size
                    and digest.hexdigest() == source["rawSha256"]
                    and (
                        before.st_dev,
                        before.st_ino,
                        before.st_size,
                        before.st_mtime_ns,
                        before.st_ctime_ns,
                    )
                    == (
                        after.st_dev,
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ),
                    "E_OUTPUT_IDENTITY",
                    "preflight",
                )
            finally:
                os.close(fd)
    finally:
        os.close(final_fd)


def validate_success_documents(
    legacy: types.ModuleType,
    root_fd: int,
    receipt: Mapping[str, Any],
    receipt_raw: bytes,
    manifest: Mapping[str, Any],
    permit: Mapping[str, Any],
    claim_sha256: str,
    decision: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> None:
    require(
        isinstance(receipt, dict) and set(receipt) == SUCCESS_RECEIPT_KEYS,
        "E_SUCCESS_STATE",
        "preflight",
    )
    counters = {
        name: receipt[name]
        for name in COUNTER_NAMES
    }
    validate_counters(counters)
    aggregates = validate_success_sources(receipt["sources"], decision, limits)
    require(
        list(counters.values()) == [19, 19, 19]
        and receipt["documentType"]
        == "aetherlink.g2-pion-dependency-wave1-v2-acquisition-receipt"
        and receipt["schemaVersion"] == "2.0"
        and receipt["status"] == "acquired_pending_independent_readback"
        and receipt["result"]
        == (
            "fresh_exact_19_dependency_module_zip_set_acquired_hash_"
            "verified_and_ratio_telemetry_recorded"
        )
        and receipt["permitId"] == permit["permitId"]
        and receipt["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and receipt["recoveryContentSha256"]
        == permit["recoveryBinding"]["contentSha256"]
        and receipt["decisionId"] == decision["decisionId"]
        and receipt["decisionContentSha256"]
        == decision["contentBinding"]["sha256"]
        and receipt["claimRawSha256"] == claim_sha256
        and type(receipt["acceptedArtifactCount"]) is int
        and receipt["acceptedArtifactCount"] == 19
        and all(
            safe_integer(receipt[name])
            for name in (
                "aggregateRawByteSize",
                "aggregateEntryCount",
                "aggregateUncompressedByteCount",
                "archiveCountExceedingHistoricalV1Ratio",
            )
        )
        and (
            receipt["aggregateRawByteSize"],
            receipt["aggregateEntryCount"],
            receipt["aggregateUncompressedByteCount"],
            receipt["archiveCountExceedingHistoricalV1Ratio"],
        )
        == aggregates
        and receipt["orderedSourceSetSha256"]
        == ordered_source_set_digest_v2(receipt["sources"])
        and receipt["compressionRatioPolicy"]
        == "non_gating_bounded_telemetry"
        and receipt["legacyCompletedRequestCountForbidden"] is True
        and receipt["independentReadbackPassed"] is False
        and receipt["dependencySourceReviewed"] is False
        and receipt["dependencyClosureComplete"] is False
        and receipt["candidateSelected"] is False
        and receipt["librarySelected"] is False
        and receipt["repositoryOwnerIdentityProofRequired"] is False
        and receipt["externalAuthenticationRequired"] is False
        and receipt["userActionRequired"] is False
        and receipt["nextAction"]
        == "run_separate_wave1_v2_independent_readback"
        and ("completed" + "RequestCount") not in receipt,
        "E_SUCCESS_STATE",
        "preflight",
    )
    require(
        isinstance(manifest, dict)
        and set(manifest) == SUCCESS_MANIFEST_KEYS
        and manifest["documentType"]
        == "aetherlink.g2-pion-dependency-wave1-v2-acquisition-manifest"
        and manifest["schemaVersion"] == "2.0"
        and manifest["status"]
        == "wave1_v2_acquisition_publication_complete_pending_independent_readback"
        and manifest["result"]
        == (
            "receipt_and_fresh_exact_19_zip_final_set_published_"
            "manifest_written_last"
        )
        and manifest["permitId"] == permit["permitId"]
        and manifest["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and manifest["successReceiptPath"] == SUCCESS_RECEIPT_PATH
        and manifest["successReceiptRawSha256"]
        == sha256_bytes(receipt_raw)
        and manifest["finalDirectoryPath"] == FINAL_DIRECTORY_PATH
        and [manifest[name] for name in COUNTER_NAMES] == [19, 19, 19]
        and type(manifest["acceptedArtifactCount"]) is int
        and manifest["acceptedArtifactCount"] == 19
        and manifest["orderedSourceSetSha256"]
        == receipt["orderedSourceSetSha256"]
        and manifest["manifestWrittenLast"] is True
        and manifest["independentReadbackPassed"] is False
        and manifest["repositoryOwnerIdentityProofRequired"] is False
        and manifest["externalAuthenticationRequired"] is False
        and manifest["userActionRequired"] is False
        and manifest["nextAction"]
        == "run_separate_wave1_v2_independent_readback",
        "E_SUCCESS_STATE",
        "preflight",
    )
    validate_success_final_inventory(
        legacy,
        root_fd,
        receipt["sources"],
        limits,
        decision,
    )


def preflight() -> dict[str, Any]:
    _, authority, legacy = load_validated_authority()
    permit = authority["permit"]
    decision = authority["decision"]
    state: dict[str, Any] = {
        "claimPresent": False,
        "stagingEntryCount": 0,
        "finalDirectoryPresent": False,
        "successReceiptPresent": False,
        "failureReceiptPresent": False,
        "manifestPresent": False,
        "dependencyParentInvalid": False,
        "waveParentInvalid": False,
    }
    validation_failure: str | None = None
    try:
        legacy.validate_hard_deadline_environment()
        root_fd = legacy.open_root_directory(authority["repositoryRootIdentity"])
        try:
            state = legacy.inspect_one_use_state(root_fd)
            classification = classify_preflight_state(state)
            if classification in {"success", "failure"}:
                claim, claim_raw = read_runtime_json(
                    legacy,
                    str(DEPENDENCY_PARENT / CLAIM_NAME),
                    64 * 1024,
                )
                validate_claim_document(claim, permit)
                claim_sha256 = sha256_bytes(claim_raw)
                if classification == "failure":
                    failure, _ = read_runtime_json(
                        legacy,
                        FAILURE_RECEIPT_PATH,
                        permit["absoluteResourceLimits"][
                            "maximumJsonReceiptOrFailureBytes"
                        ],
                    )
                    validate_failure_document(
                        failure,
                        permit,
                        claim_sha256,
                        decision,
                    )
                else:
                    receipt, receipt_raw = read_runtime_json(
                        legacy,
                        SUCCESS_RECEIPT_PATH,
                        permit["absoluteResourceLimits"][
                            "maximumJsonReceiptOrFailureBytes"
                        ],
                    )
                    manifest, _ = read_runtime_json(
                        legacy,
                        MANIFEST_PATH,
                        permit["absoluteResourceLimits"][
                            "maximumJsonReceiptOrFailureBytes"
                        ],
                    )
                    validate_success_documents(
                        legacy,
                        root_fd,
                        receipt,
                        receipt_raw,
                        manifest,
                        permit,
                        claim_sha256,
                        decision,
                        permit["absoluteResourceLimits"],
                    )
        finally:
            os.close(root_fd)
    except Exception as error:
        converted = convert_legacy_failure(legacy, error)
        classification = "blocked"
        validation_failure = converted.code
    if classification == "clean":
        status = "passed"
        consumption = "recovery_authorized_not_consumed"
        next_action = EXPECTED_PERMIT_NEXT_ACTION
    elif classification == "success":
        status = "consumed_pending_independent_readback"
        consumption = "recovery_acquired_pending_independent_readback"
        next_action = "run_separate_wave1_v2_independent_readback"
    elif classification == "failure":
        status = "consumed_failed_recovery_required"
        consumption = "recovery_failed_permit_consumed"
        next_action = "prepare_new_versioned_wave1_v2_recovery_decision"
    else:
        status = "blocked_recovery_state_present"
        consumption = "blocked_recovery_state_present"
        next_action = "inspect_v2_terminal_state_without_retry"
    observed_count = legacy.one_use_artifact_count(state)
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v2-runner-preflight"
        ),
        "schemaVersion": "2.0",
        "status": status,
        "validationPassed": preflight_validation_passed(classification),
        "terminalStateSchemaValid": classification in {"success", "failure"},
        "validationFailureCode": validation_failure,
        "permitId": permit["permitId"],
        "permitStatus": permit["status"],
        "networkRequestAttemptCount": 0,
        "responseBodyCompletedCount": 0,
        "validatedAndStagedTupleCount": 0,
        "fileWriteCount": 0,
        "networkOperationCount": 0,
        "observedOneUseArtifactCount": observed_count,
        "permitConsumptionState": consumption,
        "oneUseState": state,
        "legacyCompletedRequestCountForbidden": True,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": next_action,
    }


def _execute_once_with_umask() -> dict[str, Any]:
    checker, authority, legacy = load_validated_authority()
    permit = authority["permit"]
    decision = authority["decision"]
    limits = decision["resourceLimits"]
    counters = {
        "networkRequestAttemptCount": 0,
        "responseBodyCompletedCount": 0,
        "validatedAndStagedTupleCount": 0,
    }
    root_fd = -1
    parent_fd = -1
    wave_parent_fd = -1
    staging_fd = -1
    staging_name: str | None = None
    claim_sha256: str | None = None
    final_set_published = False
    success_receipt_published = False
    held_outputs: list[dict[str, Any]] = []
    try:
        legacy.validate_hard_deadline_environment()
        root_fd = legacy.open_root_directory(authority["repositoryRootIdentity"])
        require(
            classify_preflight_state(legacy.inspect_one_use_state(root_fd))
            == "clean",
            "E_ONE_USE_STATE_PRESENT",
            "preflight",
        )
        parent_parts = legacy.validate_relative_path(str(DEPENDENCY_PARENT))
        parent_fd = legacy.open_directory_chain(
            root_fd,
            parent_parts,
            create=True,
            owner_only_from=len(parent_parts) - 1,
        )
        wave_parent_fd = legacy.open_directory_chain(
            parent_fd,
            (WAVE_PARENT_NAME,),
            create=True,
            owner_only_from=0,
        )
        require(
            classify_preflight_state(legacy.inspect_one_use_state(root_fd))
            == "clean",
            "E_ONE_USE_STATE_PRESENT",
            "preflight",
        )
        claim_sha256 = create_claim_v2(legacy, parent_fd, permit)
        staging_name = legacy.create_staging_directory(parent_fd)
        staging_fd = os.open(
            staging_name,
            legacy.directory_open_flags(),
            dir_fd=parent_fd,
        )
        legacy.validate_directory_descriptor(
            staging_fd,
            staging_name,
            owner_only=True,
        )
        require(
            [
                name
                for name in legacy.list_names(parent_fd)
                if name.startswith(STAGING_PREFIX)
            ]
            == [staging_name],
            "E_STAGING_STATE",
            "filesystem",
        )

        opener = AttemptCountingOpener(legacy.build_exact_opener(), counters)
        wave_deadline = (
            time.monotonic() + limits["wholeWaveDeadlineMilliseconds"] / 1000
        )
        per_request_timeout = (
            limits["perRequestDeadlineMilliseconds"] / 1000
        )
        aggregate_bytes = 0
        aggregate_entries = 0
        aggregate_uncompressed = 0
        rows: list[dict[str, Any]] = []
        tuples = decision["wave"]["tuples"]
        require(len(tuples) == 19, "E_WAVE_TUPLES", "execution")
        for item in tuples:
            tuple_id = str(item["tupleId"])
            tuple_order = int(item["order"])
            temporary_name = f".{tuple_order:03d}.download"
            final_name = PurePosixPath(item["outputPath"]).name
            try:
                output_fd = os.open(
                    temporary_name,
                    legacy.create_download_file_flags(),
                    0o600,
                    dir_fd=staging_fd,
                )
            except OSError as error:
                raise RunnerFailure(
                    "E_FILESYSTEM_CREATE",
                    "download",
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                ) from error
            keep_output_fd = False
            try:
                enforce_download_file_mode(
                    output_fd,
                    tuple_id,
                    tuple_order,
                )
                download = legacy.download_exact_once(
                    opener,
                    item,
                    output_fd,
                    maximum_bytes=limits[
                        "maximumResponseBytesPerArchive"
                    ],
                    aggregate_before=aggregate_bytes,
                    maximum_aggregate_bytes=limits[
                        "maximumAggregateResponseBytes"
                    ],
                    per_request_timeout_seconds=per_request_timeout,
                    wave_deadline=wave_deadline,
                )
                counters["responseBodyCompletedCount"] += 1
                validate_counters(counters)
                with legacy.hard_wall_clock_request_deadline(
                    request_deadline=wave_deadline,
                    wave_deadline=wave_deadline,
                    tuple_id=tuple_id,
                    phase="zip",
                ):
                    archive = inspect_module_zip_v2(
                        legacy,
                        output_fd,
                        item,
                        limits,
                        aggregate_entries_before=aggregate_entries,
                        aggregate_uncompressed_before=aggregate_uncompressed,
                    )
                legacy.link_temp_to_final(
                    staging_fd,
                    temporary_name,
                    final_name,
                    output_fd,
                )
                held_outputs.append(
                    {
                        "fd": output_fd,
                        "name": final_name,
                        "rawByteSize": download["rawByteSize"],
                        "rawSha256": download["rawSha256"],
                    }
                )
                keep_output_fd = True
                counters["validatedAndStagedTupleCount"] += 1
                validate_counters(counters)
            except Exception as error:
                raise convert_legacy_failure(
                    legacy,
                    error,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                ) from None
            finally:
                if not keep_output_fd:
                    os.close(output_fd)
            aggregate_bytes += download["rawByteSize"]
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
            rows.append(
                {
                    "order": tuple_order,
                    "tupleId": tuple_id,
                    "module": item["module"],
                    "version": item["version"],
                    "url": item["url"],
                    "outputFileName": final_name,
                    "rawByteSize": download["rawByteSize"],
                    "rawSha256": download["rawSha256"],
                    "moduleZipH1": archive["moduleZipH1"],
                    "goModH1": archive["goModH1"],
                    "entryCount": archive["entryCount"],
                    "uncompressedByteCount": archive[
                        "uncompressedByteCount"
                    ],
                    "modulePrefix": archive["modulePrefix"],
                    "compressionTelemetry": archive[
                        "compressionTelemetry"
                    ],
                    "mode": "0600",
                    "linkCount": 1,
                }
            )

        validate_counters(counters)
        require(
            list(counters.values()) == [19, 19, 19] and len(rows) == 19,
            "E_REQUEST_COUNT",
            "execution",
        )
        source_set_sha256 = ordered_source_set_digest_v2(rows)
        checker.validate_repository(ROOT)
        with legacy.hard_wall_clock_request_deadline(
            request_deadline=wave_deadline,
            wave_deadline=wave_deadline,
            tuple_id=None,
            phase="publication",
        ):
            legacy.validate_held_output_inventory(staging_fd, held_outputs)
            os.fsync(staging_fd)
        require(
            time.monotonic() < wave_deadline,
            "E_WAVE_DEADLINE",
            "publication",
        )
        legacy.exclusive_rename_directory(
            parent_fd,
            staging_name,
            wave_parent_fd,
            FINAL_DIRECTORY_NAME,
        )
        final_set_published = True
        published_fd = os.open(
            FINAL_DIRECTORY_NAME,
            legacy.directory_open_flags(),
            dir_fd=wave_parent_fd,
        )
        try:
            legacy.validate_directory_descriptor(
                published_fd,
                FINAL_DIRECTORY_NAME,
                owner_only=True,
            )
            legacy.validate_held_output_inventory(published_fd, held_outputs)
        finally:
            os.close(published_fd)
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        held_outputs.clear()
        os.close(staging_fd)
        staging_fd = -1
        os.fsync(parent_fd)
        os.fsync(wave_parent_fd)

        exceeded_count = sum(
            row["compressionTelemetry"][
                "maximumRatioExceededHistoricalV1Limit"
            ]
            for row in rows
        )
        receipt = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v2-acquisition-receipt"
            ),
            "schemaVersion": "2.0",
            "status": "acquired_pending_independent_readback",
            "result": (
                "fresh_exact_19_dependency_module_zip_set_acquired_hash_"
                "verified_and_ratio_telemetry_recorded"
            ),
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "recoveryContentSha256": permit["recoveryBinding"]["contentSha256"],
            "decisionId": decision["decisionId"],
            "decisionContentSha256": decision["contentBinding"]["sha256"],
            "claimRawSha256": claim_sha256,
            "networkRequestAttemptCount": counters[
                "networkRequestAttemptCount"
            ],
            "responseBodyCompletedCount": counters[
                "responseBodyCompletedCount"
            ],
            "validatedAndStagedTupleCount": counters[
                "validatedAndStagedTupleCount"
            ],
            "acceptedArtifactCount": len(rows),
            "aggregateRawByteSize": aggregate_bytes,
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedByteCount": aggregate_uncompressed,
            "archiveCountExceedingHistoricalV1Ratio": exceeded_count,
            "orderedSourceSetSha256": source_set_sha256,
            "sources": rows,
            "compressionRatioPolicy": "non_gating_bounded_telemetry",
            "legacyCompletedRequestCountForbidden": True,
            "independentReadbackPassed": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v2_independent_readback",
        }
        receipt_raw = canonical_json_bytes(receipt)
        receipt_sha256 = legacy.write_repo_relative_artifact(
            root_fd,
            SUCCESS_RECEIPT_PATH,
            receipt_raw,
            limits["maximumJsonReceiptOrFailureBytes"],
        )
        success_receipt_published = True
        manifest = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v2-acquisition-manifest"
            ),
            "schemaVersion": "2.0",
            "status": (
                "wave1_v2_acquisition_publication_complete_pending_"
                "independent_readback"
            ),
            "result": (
                "receipt_and_fresh_exact_19_zip_final_set_published_"
                "manifest_written_last"
            ),
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "successReceiptPath": SUCCESS_RECEIPT_PATH,
            "successReceiptRawSha256": receipt_sha256,
            "finalDirectoryPath": FINAL_DIRECTORY_PATH,
            "networkRequestAttemptCount": 19,
            "responseBodyCompletedCount": 19,
            "validatedAndStagedTupleCount": 19,
            "acceptedArtifactCount": 19,
            "orderedSourceSetSha256": source_set_sha256,
            "manifestWrittenLast": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v2_independent_readback",
        }
        manifest_sha256 = legacy.write_repo_relative_artifact(
            root_fd,
            MANIFEST_PATH,
            canonical_json_bytes(manifest),
            limits["maximumJsonReceiptOrFailureBytes"],
        )
        return {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v2-runner-result"
            ),
            "schemaVersion": "2.0",
            "status": "acquired_pending_independent_readback",
            "networkRequestAttemptCount": 19,
            "responseBodyCompletedCount": 19,
            "validatedAndStagedTupleCount": 19,
            "acceptedArtifactCount": 19,
            "orderedSourceSetSha256": source_set_sha256,
            "successReceiptRawSha256": receipt_sha256,
            "manifestRawSha256": manifest_sha256,
            "legacyCompletedRequestCountForbidden": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v2_independent_readback",
        }
    except Exception as error:
        failure = convert_legacy_failure(legacy, error)
        if final_set_published:
            failure = RunnerFailure(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
                observations=counters,
            )
        if staging_fd >= 0:
            legacy.close_quietly(staging_fd)
            staging_fd = -1
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        held_outputs.clear()
        if (
            staging_name is not None
            and not final_set_published
            and parent_fd >= 0
        ):
            try:
                legacy.remove_staging(parent_fd, staging_name)
            except Exception:
                pass
        if (
            not final_set_published
            and claim_sha256 is not None
            and not success_receipt_published
        ):
            try:
                failure_document = safe_failure_document_v2(
                    permit,
                    failure,
                    counters,
                    claim_sha256=claim_sha256,
                    final_set_published=False,
                )
                legacy.write_repo_relative_artifact(
                    root_fd,
                    FAILURE_RECEIPT_PATH,
                    canonical_json_bytes(failure_document),
                    limits["maximumJsonReceiptOrFailureBytes"],
                )
            except Exception:
                pass
        raise failure from None
    finally:
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        legacy.close_quietly(staging_fd)
        legacy.close_quietly(wave_parent_fd)
        legacy.close_quietly(parent_fd)
        legacy.close_quietly(root_fd)


def execute_once() -> dict[str, Any]:
    previous_umask = os.umask(0o077)
    try:
        return _execute_once_with_umask()
    finally:
        os.umask(previous_umask)


def runner_error_document(failure: RunnerFailure) -> dict[str, Any]:
    post_publish_uncertain = failure.code == "E_POST_PUBLISH_UNCERTAIN"
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v2-runner-error"
        ),
        "schemaVersion": "2.0",
        "status": (
            "consumed_terminal_state_uncertain"
            if post_publish_uncertain
            else "failed"
        ),
        "failureCode": failure.code,
        "phase": failure.phase,
        "failedTupleId": failure.tuple_id,
        "failedTupleOrder": failure.tuple_order,
        "safeNumericObservations": bounded_observations(
            failure.observations
        ),
        "permitConsumptionState": (
            "consumed_terminal_state_uncertain"
            if post_publish_uncertain
            else "inspect_one_use_state_before_any_new_authority"
        ),
        "automaticRetryAllowed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": (
            "inspect_v2_terminal_state_without_retry"
            if post_publish_uncertain
            else "inspect_v2_one_use_state_without_automatic_retry"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = execute_once() if args.execute else preflight()
    except RunnerFailure as failure:
        safe = runner_error_document(failure)
        print(json.dumps(safe, ensure_ascii=True, sort_keys=True))
        return 1
    except Exception:
        safe = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v2-runner-error"
            ),
            "schemaVersion": "2.0",
            "status": "failed",
            "failureCode": "E_INTERNAL",
            "phase": "runner",
            "failedTupleId": None,
            "failedTupleOrder": None,
            "safeNumericObservations": {},
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        print(json.dumps(safe, ensure_ascii=True, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    if not args.execute and not result.get("validationPassed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
