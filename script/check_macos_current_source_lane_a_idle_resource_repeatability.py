#!/usr/bin/env python3
"""Independently read back two current-source Lane-A idle observations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Sequence


SCHEMA_VERSION = 1
PARENT_SCHEMA_VERSION = 4
SINGLE_SCOPE = (
    "same-host-per-user-current-source-lane-a-idle-resource-stability-v1"
)
REPEATABILITY_SCOPE = (
    "same-host-per-user-current-source-lane-a-idle-resource-repeatability-v1"
)
SOURCE_ALGORITHM = "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
APP_TREE_ALGORITHM = (
    "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
)
READBACK_MODE = (
    "archive-only-with-materialized-source-snapshot-no-signature-check"
)
WARMUP_MILLISECONDS = 60_000
OBSERVATION_MILLISECONDS = 600_000
INTERVAL_MILLISECONDS = 5_000
SAMPLE_COUNT = 120
LATENESS_LIMIT_MILLISECONDS = 1_000
WINDOW_SAMPLE_COUNT = 12
FINAL_FD_DELTA_LIMIT = 2
PEAK_FD_DELTA_LIMIT = 8
FINAL_THREAD_DELTA_LIMIT = 2
PEAK_THREAD_DELTA_LIMIT = 8
FINAL_RSS_DELTA_LIMIT_BYTES = 32 * 1024 * 1024
PEAK_RSS_DELTA_LIMIT_BYTES = 128 * 1024 * 1024
MAXIMUM_FILE_BYTES = 4 * 1024 * 1024
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
LABEL_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SINGLE_LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "single-direct-owned-child-idle-observation-only",
    "sixty-second-warmup-and-ten-minute-observation-only",
    "network-denied-and-writes-confined-to-temporary-root",
    "libproc-resource-samples-are-point-in-time-nonatomic-observations",
    "local-regression-budgets-not-performance-sla-or-capacity-evidence",
    "single-recorded-run-not-repeatability-or-long-soak-evidence",
    "archive-only-exercise-current-source-binding-requires-suite-parent",
    "no-signing-or-signature-verification-performed",
    (
        "not-install-upgrade-uninstall-reinstall-recovery-crash-or-"
        "rollback-evidence"
    ),
    (
        "not-load-provider-device-ui-accessibility-production-or-"
        "security-evidence"
    ),
)
REPEATABILITY_LIMITATIONS = (
    "same-host-two-recorded-idle-observations-only",
    "two-sequential-runner-processes-with-independent-temporary-root-lifecycles",
    "measurement-values-and-result-bytes-not-required-to-match",
    "each-observation-sixty-second-warmup-and-ten-minute-window-only",
    "local-regression-budgets-not-performance-sla-or-capacity-evidence",
    "archive-only-exercise-current-source-binding-requires-suite-parent",
    "no-signing-or-signature-verification-performed",
    (
        "not-arbitrary-repeatability-long-soak-weekly-resilience-or-"
        "production-evidence"
    ),
    (
        "not-cross-host-install-upgrade-rollback-device-provider-network-ui-"
        "accessibility-or-security-evidence"
    ),
)


class IdleRepeatabilityCheckError(RuntimeError):
    """Raised when independent evidence readback fails closed."""


@dataclass(frozen=True)
class HeldFile:
    path: Path
    descriptor: int
    initial_stat: os.stat_result


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def open_held_file(path: Path) -> HeldFile:
    path = path.absolute()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise IdleRepeatabilityCheckError(
            f"cannot open evidence without following links: {path}: {error}"
        ) from error
    try:
        status = os.fstat(descriptor)
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_uid != os.getuid()
            or status.st_nlink != 1
            or stat.S_IMODE(status.st_mode) != 0o600
            or status.st_size <= 0
            or status.st_size > MAXIMUM_FILE_BYTES
        ):
            raise IdleRepeatabilityCheckError(
                f"evidence must be an owner-only single-link regular file: {path}"
            )
        return HeldFile(path=path, descriptor=descriptor, initial_stat=status)
    except BaseException:
        os.close(descriptor)
        raise


def read_held_file(held: HeldFile) -> bytes:
    os.lseek(held.descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(held.descriptor, 64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAXIMUM_FILE_BYTES:
            raise IdleRepeatabilityCheckError(
                f"evidence exceeds the byte limit: {held.path}"
            )
        chunks.append(chunk)
    raw = b"".join(chunks)
    if len(raw) != held.initial_stat.st_size:
        raise IdleRepeatabilityCheckError(
            f"evidence size changed during held read: {held.path}"
        )
    return raw


def require_held_file_unchanged(held: HeldFile) -> None:
    try:
        descriptor_status = os.fstat(held.descriptor)
        path_status = os.lstat(held.path)
    except OSError as error:
        raise IdleRepeatabilityCheckError(
            f"cannot complete evidence identity readback: {held.path}: {error}"
        ) from error
    if (
        stat_identity(descriptor_status) != stat_identity(held.initial_stat)
        or stat_identity(path_status) != stat_identity(held.initial_stat)
    ):
        raise IdleRepeatabilityCheckError(
            f"evidence identity changed around validation: {held.path}"
        )


def parse_canonical_json(raw: bytes, label: str) -> dict[str, object]:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise IdleRepeatabilityCheckError(
                    f"{label} contains a duplicate JSON key: {key}"
                )
            result[key] = value
        return result

    try:
        text = raw.decode("ascii")
        parsed = json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                IdleRepeatabilityCheckError(
                    f"{label} contains a non-finite number: {value}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IdleRepeatabilityCheckError(
            f"{label} is not canonical ASCII JSON: {error}"
        ) from error
    if type(parsed) is not dict or raw != canonical_json_bytes(parsed):
        raise IdleRepeatabilityCheckError(
            f"{label} bytes are not canonical ASCII JSON"
        )
    return parsed


def closed_object(
    value: object,
    expected_keys: set[str],
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected_keys:
        raise IdleRepeatabilityCheckError(f"{label} has a different schema")
    return value


def exact_int(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise IdleRepeatabilityCheckError(
            f"{label} must be an exact integer >= {minimum}"
        )
    return value


def exact_bool(value: object, expected: bool, label: str) -> None:
    if type(value) is not bool or value is not expected:
        raise IdleRepeatabilityCheckError(
            f"{label} must be exactly {expected}"
        )


def exact_sha256(value: object, label: str) -> str:
    if type(value) is not str or SHA256_PATTERN.fullmatch(value) is None:
        raise IdleRepeatabilityCheckError(
            f"{label} must be a lowercase SHA-256"
        )
    return value


def positive_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise IdleRepeatabilityCheckError(f"{label} must be a nonempty string")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as error:
        raise IdleRepeatabilityCheckError(
            f"{label} must contain ASCII only"
        ) from error
    return value


def reject_absolute_strings(value: object, label: str) -> None:
    if type(value) is dict:
        for key, child in value.items():
            reject_absolute_strings(child, f"{label}.{key}")
    elif type(value) is list:
        for index, child in enumerate(value):
            reject_absolute_strings(child, f"{label}[{index}]")
    elif type(value) is str and value.startswith("/"):
        raise IdleRepeatabilityCheckError(
            f"{label} retains an absolute path"
        )


def metric_summary(
    values: list[int],
    *,
    final_delta_limit: int,
    peak_delta_limit: int,
) -> dict[str, object]:
    if len(values) != SAMPLE_COUNT or any(
        type(value) is not int or value <= 0 for value in values
    ):
        raise IdleRepeatabilityCheckError(
            "resource metric must contain 120 positive exact integers"
        )
    baseline_values = sorted(values[:WINDOW_SAMPLE_COUNT])
    final_values = sorted(values[-WINDOW_SAMPLE_COUNT:])
    baseline = baseline_values[len(baseline_values) // 2]
    final = final_values[len(final_values) // 2]
    maximum = max(values)
    final_delta = final - baseline
    peak_delta = maximum - baseline
    passed = (
        final_delta <= final_delta_limit
        and peak_delta <= peak_delta_limit
    )
    if not passed:
        raise IdleRepeatabilityCheckError(
            "resource samples exceed their fixed regression budget"
        )
    return {
        "baselineUpperMedian": baseline,
        "finalDelta": final_delta,
        "finalDeltaLimit": final_delta_limit,
        "finalUpperMedian": final,
        "maximum": maximum,
        "passed": True,
        "peakDelta": peak_delta,
        "peakDeltaLimit": peak_delta_limit,
    }


def measurement_summary(samples: object) -> dict[str, object]:
    if type(samples) is not list or len(samples) != SAMPLE_COUNT:
        raise IdleRepeatabilityCheckError(
            "idle observation must contain exactly 120 samples"
        )
    sample_keys = {
        "observedLatenessMilliseconds",
        "openFileDescriptorCount",
        "ordinal",
        "residentBytes",
        "targetElapsedMilliseconds",
        "threadCount",
    }
    for ordinal, sample_value in enumerate(samples, start=1):
        sample = closed_object(
            sample_value,
            sample_keys,
            f"idle sample {ordinal}",
        )
        if exact_int(sample["ordinal"], "sample ordinal", minimum=1) != ordinal:
            raise IdleRepeatabilityCheckError("sample ordinal differs")
        target = exact_int(
            sample["targetElapsedMilliseconds"],
            "sample target elapsed",
        )
        if target != ordinal * INTERVAL_MILLISECONDS:
            raise IdleRepeatabilityCheckError("sample schedule differs")
        lateness = exact_int(
            sample["observedLatenessMilliseconds"],
            "sample lateness",
        )
        if lateness > LATENESS_LIMIT_MILLISECONDS:
            raise IdleRepeatabilityCheckError("sample lateness exceeds limit")
        for key in (
            "openFileDescriptorCount",
            "residentBytes",
            "threadCount",
        ):
            exact_int(sample[key], f"sample {key}", minimum=1)
    return {
        "openFileDescriptors": metric_summary(
            [sample["openFileDescriptorCount"] for sample in samples],
            final_delta_limit=FINAL_FD_DELTA_LIMIT,
            peak_delta_limit=PEAK_FD_DELTA_LIMIT,
        ),
        "residentBytes": metric_summary(
            [sample["residentBytes"] for sample in samples],
            final_delta_limit=FINAL_RSS_DELTA_LIMIT_BYTES,
            peak_delta_limit=PEAK_RSS_DELTA_LIMIT_BYTES,
        ),
        "threads": metric_summary(
            [sample["threadCount"] for sample in samples],
            final_delta_limit=FINAL_THREAD_DELTA_LIMIT,
            peak_delta_limit=PEAK_THREAD_DELTA_LIMIT,
        ),
    }


def validate_identity_record(value: object, label: str) -> dict[str, object]:
    record = closed_object(value, {"sha256", "size"}, label)
    exact_sha256(record["sha256"], f"{label} SHA-256")
    exact_int(record["size"], f"{label} size", minimum=1)
    return record


def validate_single_result(
    result: dict[str, object],
    label: str,
) -> dict[str, object]:
    closed_object(
        result,
        {
            "archiveReadback",
            "artifact",
            "cleanup",
            "environment",
            "isolation",
            "limitations",
            "measurement",
            "process",
            "release",
            "repeatability",
            "schemaVersion",
            "scope",
            "sourceSnapshot",
            "status",
        },
        label,
    )
    if (
        exact_int(result["schemaVersion"], f"{label} schema", minimum=1)
        != SCHEMA_VERSION
        or result["scope"] != SINGLE_SCOPE
        or result["status"] != "passed"
        or result["limitations"] != list(SINGLE_LIMITATIONS)
    ):
        raise IdleRepeatabilityCheckError(
            f"{label} identity, status, or limitations differ"
        )
    reject_absolute_strings(result, label)

    source = closed_object(
        result["sourceSnapshot"],
        {"algorithm", "fileCount", "sha256"},
        f"{label} source",
    )
    if source["algorithm"] != SOURCE_ALGORITHM:
        raise IdleRepeatabilityCheckError(f"{label} source algorithm differs")
    exact_int(source["fileCount"], f"{label} source count", minimum=1)
    exact_sha256(source["sha256"], f"{label} source SHA-256")

    release = closed_object(
        result["release"],
        {"archiveSha256", "manifestSha256", "releaseId"},
        f"{label} release",
    )
    release_id = positive_string(release["releaseId"], f"{label} release ID")
    exact_sha256(release["archiveSha256"], f"{label} archive SHA-256")
    exact_sha256(release["manifestSha256"], f"{label} manifest SHA-256")

    artifact = closed_object(result["artifact"], {"appTree"}, f"{label} artifact")
    app_tree = closed_object(
        artifact["appTree"],
        {
            "digestAlgorithm",
            "regularFileCount",
            "sha256",
            "totalRegularFileBytes",
        },
        f"{label} app tree",
    )
    if app_tree["digestAlgorithm"] != APP_TREE_ALGORITHM:
        raise IdleRepeatabilityCheckError(f"{label} app-tree algorithm differs")
    exact_int(app_tree["regularFileCount"], f"{label} app files", minimum=1)
    exact_sha256(app_tree["sha256"], f"{label} app-tree SHA-256")
    exact_int(
        app_tree["totalRegularFileBytes"],
        f"{label} app-tree bytes",
        minimum=1,
    )

    readback = closed_object(
        result["archiveReadback"],
        {
            "currentSourceCompared",
            "mode",
            "readbackAndExerciseSameSnapshot",
            "signatureVerificationPerformed",
            "snapshotFiles",
            "snapshotFilesUnchangedAfterExercise",
            "status",
        },
        f"{label} archive readback",
    )
    exact_bool(readback["currentSourceCompared"], False, "current source compared")
    exact_bool(
        readback["readbackAndExerciseSameSnapshot"],
        True,
        "same archive snapshot",
    )
    exact_bool(
        readback["signatureVerificationPerformed"],
        False,
        "signature verification",
    )
    exact_bool(
        readback["snapshotFilesUnchangedAfterExercise"],
        True,
        "snapshot unchanged",
    )
    if readback["mode"] != READBACK_MODE or readback["status"] != "passed":
        raise IdleRepeatabilityCheckError(f"{label} archive readback differs")
    snapshot_names = {
        f"{release_id}.manifest.json",
        f"{release_id}.zip",
        f"{release_id}.zip.sha256",
    }
    snapshot = closed_object(
        readback["snapshotFiles"],
        snapshot_names,
        f"{label} snapshot files",
    )
    for name in snapshot_names:
        validate_identity_record(snapshot[name], f"{label} snapshot {name}")
    if (
        snapshot[f"{release_id}.zip"]["sha256"]
        != release["archiveSha256"]
        or snapshot[f"{release_id}.manifest.json"]["sha256"]
        != release["manifestSha256"]
    ):
        raise IdleRepeatabilityCheckError(f"{label} release binding differs")

    cleanup = closed_object(
        result["cleanup"],
        {
            "ownedChildOnly",
            "preexistingApplicationsPreserved",
            "temporaryRootRemovedBeforePublication",
        },
        f"{label} cleanup",
    )
    for key in cleanup:
        exact_bool(cleanup[key], True, f"{label} cleanup {key}")

    environment = closed_object(
        result["environment"],
        {"architecture", "logicalCpuCount", "macOSVersion", "pageSizeBytes"},
        f"{label} environment",
    )
    positive_string(environment["architecture"], f"{label} architecture")
    positive_string(environment["macOSVersion"], f"{label} macOS version")
    exact_int(environment["logicalCpuCount"], f"{label} CPUs", minimum=1)
    exact_int(environment["pageSizeBytes"], f"{label} page size", minimum=1)

    isolation = closed_object(
        result["isolation"],
        {
            "afInetBindDeniedByPreflight",
            "networkDenied",
            "nonTemporaryWriteDeniedByPreflight",
            "profile",
            "sandboxed",
            "standardStreams",
            "temporaryCFUserHomeConfigured",
        },
        f"{label} isolation",
    )
    for key in (
        "afInetBindDeniedByPreflight",
        "networkDenied",
        "nonTemporaryWriteDeniedByPreflight",
        "sandboxed",
        "temporaryCFUserHomeConfigured",
    ):
        exact_bool(isolation[key], True, f"{label} isolation {key}")
    if (
        isolation["profile"]
        != "allow-default-deny-network-and-non-temp-writes-v1"
        or isolation["standardStreams"] != "devnull"
    ):
        raise IdleRepeatabilityCheckError(f"{label} isolation policy differs")

    process = closed_object(
        result["process"],
        {
            "launchMethod",
            "preexistingApplicationCount",
            "preexistingApplicationsUsedAsTerminationTargets",
            "rawProcessIdentifierRetained",
        },
        f"{label} process",
    )
    if process["launchMethod"] != "sandbox-exec-direct-owned-child-v1":
        raise IdleRepeatabilityCheckError(f"{label} launch method differs")
    exact_int(process["preexistingApplicationCount"], "preexisting app count")
    exact_bool(
        process["preexistingApplicationsUsedAsTerminationTargets"],
        False,
        "preexisting termination target",
    )
    exact_bool(
        process["rawProcessIdentifierRetained"],
        False,
        "raw process identifier retained",
    )

    repeatability = closed_object(
        result["repeatability"],
        {"performed", "reason"},
        f"{label} single-run repeatability",
    )
    exact_bool(repeatability["performed"], False, "single repeatability")
    if repeatability["reason"] != "single-live-resource-observation-v1":
        raise IdleRepeatabilityCheckError(f"{label} single-run claim differs")

    measurement = closed_object(
        result["measurement"],
        {
            "api",
            "baselineWindowSampleCount",
            "finalWindowSampleCount",
            "intervalMilliseconds",
            "observationMilliseconds",
            "run",
            "sampleCount",
            "sampleLatenessLimitMilliseconds",
            "status",
            "warmupMilliseconds",
        },
        f"{label} measurement",
    )
    expected_measurement = {
        "api": "macos-libproc-proc-pidinfo-v1",
        "baselineWindowSampleCount": WINDOW_SAMPLE_COUNT,
        "finalWindowSampleCount": WINDOW_SAMPLE_COUNT,
        "intervalMilliseconds": INTERVAL_MILLISECONDS,
        "observationMilliseconds": OBSERVATION_MILLISECONDS,
        "sampleCount": SAMPLE_COUNT,
        "sampleLatenessLimitMilliseconds": LATENESS_LIMIT_MILLISECONDS,
        "status": "passed",
        "warmupMilliseconds": WARMUP_MILLISECONDS,
    }
    for key, expected in expected_measurement.items():
        value = measurement[key]
        if type(expected) is int:
            if type(value) is not int or value != expected:
                raise IdleRepeatabilityCheckError(
                    f"{label} measurement {key} differs"
                )
        elif value != expected:
            raise IdleRepeatabilityCheckError(
                f"{label} measurement {key} differs"
            )

    run = closed_object(
        measurement["run"],
        {
            "activationPolicy",
            "appKitProcessAbsentAfterReap",
            "exitCode",
            "finishedLaunching",
            "gracefulTerminationAccepted",
            "maximumObservedLatenessMilliseconds",
            "ownedChildProcess",
            "processIdentifierRetained",
            "processReaped",
            "samples",
            "summary",
        },
        f"{label} run",
    )
    if (
        exact_int(run["activationPolicy"], "activation policy") != 0
        or exact_int(run["exitCode"], "exit code") != 0
    ):
        raise IdleRepeatabilityCheckError(f"{label} process outcome differs")
    for key in (
        "appKitProcessAbsentAfterReap",
        "finishedLaunching",
        "gracefulTerminationAccepted",
        "ownedChildProcess",
        "processReaped",
    ):
        exact_bool(run[key], True, f"{label} run {key}")
    exact_bool(
        run["processIdentifierRetained"],
        False,
        f"{label} process identifier retained",
    )
    expected_summary = measurement_summary(run["samples"])
    if canonical_json_bytes(run["summary"]) != canonical_json_bytes(
        expected_summary
    ):
        raise IdleRepeatabilityCheckError(f"{label} sample summary differs")
    maximum_lateness = max(
        sample["observedLatenessMilliseconds"] for sample in run["samples"]
    )
    if (
        exact_int(
            run["maximumObservedLatenessMilliseconds"],
            f"{label} maximum lateness",
        )
        != maximum_lateness
    ):
        raise IdleRepeatabilityCheckError(f"{label} maximum lateness differs")
    return result


def invariant_projection(result: dict[str, object]) -> dict[str, object]:
    measurement = result["measurement"]
    process = result["process"]
    return {
        "archiveReadback": result["archiveReadback"],
        "artifact": result["artifact"],
        "cleanup": result["cleanup"],
        "environment": result["environment"],
        "isolation": result["isolation"],
        "limitations": result["limitations"],
        "measurement": {
            key: measurement[key]
            for key in (
                "api",
                "baselineWindowSampleCount",
                "finalWindowSampleCount",
                "intervalMilliseconds",
                "observationMilliseconds",
                "sampleCount",
                "sampleLatenessLimitMilliseconds",
                "status",
                "warmupMilliseconds",
            )
        },
        "process": {
            key: process[key]
            for key in (
                "launchMethod",
                "preexistingApplicationsUsedAsTerminationTargets",
                "rawProcessIdentifierRetained",
            )
        },
        "release": result["release"],
        "repeatability": result["repeatability"],
        "schemaVersion": result["schemaVersion"],
        "scope": result["scope"],
        "sourceSnapshot": result["sourceSnapshot"],
        "status": result["status"],
    }


def validate_parent(
    parent: dict[str, object],
    run_a: dict[str, object],
    run_b: dict[str, object],
) -> None:
    closed_object(
        parent,
        {
            "builds",
            "comparison",
            "executionMode",
            "failure",
            "gradleCache",
            "prepublicationBinding",
            "protectedArchive",
            "publication",
            "releaseId",
            "schemaVersion",
            "scratch",
            "source",
            "status",
            "toolchainPolicy",
        },
        "reproducibility parent",
    )
    release_id = run_a["release"]["releaseId"]
    if (
        exact_int(parent["schemaVersion"], "parent schema", minimum=1)
        != PARENT_SCHEMA_VERSION
        or parent["executionMode"] != "comparison-only"
        or parent["releaseId"] != release_id
        or parent["status"] != "passed"
        or parent["failure"] is not None
        or parent["prepublicationBinding"] is not None
    ):
        raise IdleRepeatabilityCheckError("reproducibility parent did not pass")
    publication = closed_object(
        parent["publication"],
        {
            "attempted",
            "independentReadback",
            "outcome",
            "policy",
            "qualifiedArchivePublished",
        },
        "parent publication",
    )
    for key in (
        "attempted",
        "independentReadback",
        "qualifiedArchivePublished",
    ):
        exact_bool(publication[key], False, f"parent publication {key}")
    if (
        publication["outcome"] != "disabled-comparison-only"
        or publication["policy"] != "comparison-only-no-publication"
    ):
        raise IdleRepeatabilityCheckError("parent publication policy differs")
    protected = closed_object(
        parent["protectedArchive"],
        {
            "afterIdentitySha256",
            "beforeIdentitySha256",
            "policy",
            "relativePath",
            "unchanged",
        },
        "parent protected archive",
    )
    exact_bool(protected["unchanged"], True, "protected archive unchanged")
    if (
        exact_sha256(protected["beforeIdentitySha256"], "protected before")
        != exact_sha256(protected["afterIdentitySha256"], "protected after")
    ):
        raise IdleRepeatabilityCheckError("protected archive identity differs")

    source = closed_object(
        parent["source"],
        {"algorithm", "fileCount", "overlaySha256", "sha256"},
        "parent source",
    )
    if source["algorithm"] != SOURCE_ALGORITHM:
        raise IdleRepeatabilityCheckError("parent source algorithm differs")
    exact_int(source["fileCount"], "parent source count", minimum=1)
    exact_sha256(source["overlaySha256"], "parent overlay SHA-256")
    exact_sha256(source["sha256"], "parent source SHA-256")
    for result in (run_a, run_b):
        if canonical_json_bytes(result["sourceSnapshot"]) != canonical_json_bytes(
            {
                "algorithm": source["algorithm"],
                "fileCount": source["fileCount"],
                "sha256": source["sha256"],
            }
        ):
            raise IdleRepeatabilityCheckError("parent source binding differs")

    builds = parent["builds"]
    if type(builds) is not list or len(builds) != 2:
        raise IdleRepeatabilityCheckError("parent must contain two builds")
    archives: list[dict[str, object]] = []
    for index, value in enumerate(builds):
        build = closed_object(
            value,
            {"archive", "commandExitCode", "id", "status"},
            f"parent build {index + 1}",
        )
        if (
            build["id"] != ("build-a" if index == 0 else "build-b")
            or build["status"] != "passed"
            or exact_int(build["commandExitCode"], "build exit code") != 0
        ):
            raise IdleRepeatabilityCheckError("parent build outcome differs")
        archive = closed_object(
            build["archive"],
            {
                "checksumSha256",
                "manifestSha256",
                "members",
                "payloadMemberCount",
                "sha256",
                "size",
                "sourceSha256",
                "zipEntryCount",
            },
            f"parent build {index + 1} archive",
        )
        for key in (
            "checksumSha256",
            "manifestSha256",
            "sha256",
            "sourceSha256",
        ):
            exact_sha256(archive[key], f"parent archive {key}")
        exact_int(archive["size"], "parent archive size", minimum=1)
        payload_count = exact_int(
            archive["payloadMemberCount"],
            "parent payload member count",
            minimum=1,
        )
        zip_count = exact_int(
            archive["zipEntryCount"],
            "parent ZIP entry count",
            minimum=1,
        )
        if (
            type(archive["members"]) is not list
            or len(archive["members"]) != zip_count
            or payload_count >= zip_count
        ):
            raise IdleRepeatabilityCheckError("parent archive inventory differs")
        archives.append(archive)
    if canonical_json_bytes(archives[0]) != canonical_json_bytes(archives[1]):
        raise IdleRepeatabilityCheckError("parent build archives differ")

    comparison = closed_object(
        parent["comparison"],
        {
            "archiveBytesEqual",
            "differences",
            "memberBytesEqual",
            "memberDifferences",
            "memberMetadataEqual",
            "memberSetEqual",
            "normalizations",
        },
        "parent comparison",
    )
    for key in (
        "archiveBytesEqual",
        "memberBytesEqual",
        "memberMetadataEqual",
        "memberSetEqual",
    ):
        exact_bool(comparison[key], True, f"parent comparison {key}")
    if (
        comparison["differences"] != []
        or comparison["memberDifferences"] != []
        or type(comparison["normalizations"]) is not list
    ):
        raise IdleRepeatabilityCheckError("parent comparison details differ")

    archive = archives[0]
    for result in (run_a, run_b):
        release = result["release"]
        snapshot = result["archiveReadback"]["snapshotFiles"]
        if (
            release["archiveSha256"] != archive["sha256"]
            or release["manifestSha256"] != archive["manifestSha256"]
            or result["sourceSnapshot"]["sha256"] != archive["sourceSha256"]
            or snapshot[f"{release_id}.zip"]["sha256"] != archive["sha256"]
            or snapshot[f"{release_id}.zip"]["size"] != archive["size"]
            or snapshot[f"{release_id}.zip.sha256"]["sha256"]
            != archive["checksumSha256"]
        ):
            raise IdleRepeatabilityCheckError(
                "idle result differs from parent build A archive"
            )


def validate_file_names(
    parent_path: Path,
    run_a_path: Path,
    run_b_path: Path,
    receipt_path: Path,
    release_id: str,
) -> None:
    prefix = f"macos-{release_id}-two-root-lane-a-"
    run_a_prefix = prefix + "idle-resource-stability-v1-"
    if (
        not run_a_path.name.startswith(run_a_prefix)
        or not run_a_path.name.endswith(".json")
    ):
        raise IdleRepeatabilityCheckError("run A filename differs")
    label = run_a_path.name[len(run_a_prefix) : -len(".json")]
    if LABEL_PATTERN.fullmatch(label) is None:
        raise IdleRepeatabilityCheckError("evidence label is invalid")
    expected = {
        run_b_path.name: (
            prefix + "idle-resource-stability-repeat-v1-" + label + ".json"
        ),
        receipt_path.name: (
            prefix
            + "idle-resource-stability-repeatability-v1-"
            + label
            + ".json"
        ),
    }
    for observed, required in expected.items():
        if observed != required:
            raise IdleRepeatabilityCheckError("evidence filenames differ")
    if len({parent_path, run_a_path, run_b_path, receipt_path}) != 4:
        raise IdleRepeatabilityCheckError("evidence paths must be distinct")


def validate_receipt(
    receipt: dict[str, object],
    receipt_raw: bytes,
    run_a: dict[str, object],
    run_a_raw: bytes,
    run_a_path: Path,
    run_b: dict[str, object],
    run_b_raw: bytes,
    run_b_path: Path,
) -> None:
    closed_object(
        receipt,
        {
            "allRunsPassed",
            "artifact",
            "environment",
            "independentTemporaryRootLifecycles",
            "limitations",
            "rawProcessIdentifiersRetained",
            "rawTemporaryPathsRetained",
            "release",
            "resultBytesEqual",
            "resultBytesEqualRequired",
            "runCount",
            "runs",
            "schemaVersion",
            "scope",
            "sharedInvariant",
            "sharedInvariantEqual",
            "sourceSnapshot",
            "status",
        },
        "idle repeatability receipt",
    )
    reject_absolute_strings(receipt, "idle repeatability receipt")
    if (
        exact_int(receipt["schemaVersion"], "receipt schema", minimum=1)
        != SCHEMA_VERSION
        or receipt["scope"] != REPEATABILITY_SCOPE
        or receipt["status"] != "passed"
        or receipt["limitations"] != list(REPEATABILITY_LIMITATIONS)
        or exact_int(receipt["runCount"], "receipt run count", minimum=1) != 2
    ):
        raise IdleRepeatabilityCheckError("repeatability receipt identity differs")
    for key in (
        "allRunsPassed",
        "independentTemporaryRootLifecycles",
        "sharedInvariantEqual",
    ):
        exact_bool(receipt[key], True, f"receipt {key}")
    for key in (
        "rawProcessIdentifiersRetained",
        "rawTemporaryPathsRetained",
        "resultBytesEqualRequired",
    ):
        exact_bool(receipt[key], False, f"receipt {key}")
    exact_bool(
        receipt["resultBytesEqual"],
        run_a_raw == run_b_raw,
        "receipt result byte equality",
    )

    projection_a = invariant_projection(run_a)
    projection_b = invariant_projection(run_b)
    projection_raw = canonical_json_bytes(projection_a)
    if projection_raw != canonical_json_bytes(projection_b):
        raise IdleRepeatabilityCheckError("idle invariant projections differ")
    invariant = closed_object(
        receipt["sharedInvariant"],
        {"algorithm", "sha256", "size"},
        "receipt shared invariant",
    )
    if (
        invariant["algorithm"] != "sha256(canonical-ascii-json)-v1"
        or exact_sha256(invariant["sha256"], "shared invariant SHA-256")
        != sha256(projection_raw)
        or exact_int(invariant["size"], "shared invariant size", minimum=1)
        != len(projection_raw)
    ):
        raise IdleRepeatabilityCheckError("shared invariant identity differs")
    for key in ("artifact", "environment", "release", "sourceSnapshot"):
        if canonical_json_bytes(receipt[key]) != canonical_json_bytes(
            projection_a[key]
        ):
            raise IdleRepeatabilityCheckError(f"receipt {key} differs")

    runs = receipt["runs"]
    if type(runs) is not list or len(runs) != 2:
        raise IdleRepeatabilityCheckError("receipt must bind exactly two runs")
    for ordinal, (value, path, raw) in enumerate(
        zip(runs, (run_a_path, run_b_path), (run_a_raw, run_b_raw)),
        start=1,
    ):
        record = closed_object(
            value,
            {"fileName", "ordinal", "sha256", "size", "status"},
            f"receipt run {ordinal}",
        )
        if (
            record["fileName"] != path.name
            or exact_int(record["ordinal"], "receipt ordinal", minimum=1)
            != ordinal
            or exact_sha256(record["sha256"], "receipt run SHA-256")
            != sha256(raw)
            or exact_int(record["size"], "receipt run size", minimum=1)
            != len(raw)
            or record["status"] != "passed"
        ):
            raise IdleRepeatabilityCheckError(
                f"receipt run {ordinal} identity differs"
            )
    if sha256(receipt_raw) == sha256(run_a_raw) or sha256(receipt_raw) == sha256(
        run_b_raw
    ):
        raise IdleRepeatabilityCheckError("receipt is not a distinct payload")


def check(
    *,
    parent_path: Path,
    run_a_path: Path,
    run_b_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    held_files: list[HeldFile] = []
    try:
        for path in (parent_path, run_a_path, run_b_path, receipt_path):
            held_files.append(open_held_file(path))
        parent_raw, run_a_raw, run_b_raw, receipt_raw = [
            read_held_file(held) for held in held_files
        ]
        parent = parse_canonical_json(parent_raw, "reproducibility parent")
        run_a = parse_canonical_json(run_a_raw, "idle observation A")
        run_b = parse_canonical_json(run_b_raw, "idle observation B")
        receipt = parse_canonical_json(receipt_raw, "idle repeatability receipt")
        validate_single_result(run_a, "idle observation A")
        validate_single_result(run_b, "idle observation B")
        release_id = run_a["release"]["releaseId"]
        if run_b["release"]["releaseId"] != release_id:
            raise IdleRepeatabilityCheckError("idle release IDs differ")
        validate_file_names(
            held_files[0].path,
            held_files[1].path,
            held_files[2].path,
            held_files[3].path,
            release_id,
        )
        validate_parent(parent, run_a, run_b)
        validate_receipt(
            receipt,
            receipt_raw,
            run_a,
            run_a_raw,
            held_files[1].path,
            run_b,
            run_b_raw,
            held_files[2].path,
        )
        for held in held_files:
            require_held_file_unchanged(held)
        return {
            "parent": {
                "fileName": held_files[0].path.name,
                "sha256": sha256(parent_raw),
                "size": len(parent_raw),
            },
            "receipt": {
                "fileName": held_files[3].path.name,
                "sha256": sha256(receipt_raw),
                "size": len(receipt_raw),
            },
            "releaseId": release_id,
            "runCount": 2,
            "runs": [
                {
                    "fileName": path.name,
                    "sha256": sha256(raw),
                    "size": len(raw),
                }
                for path, raw in (
                    (held_files[1].path, run_a_raw),
                    (held_files[2].path, run_b_raw),
                )
            ],
            "schemaVersion": SCHEMA_VERSION,
            "scope": REPEATABILITY_SCOPE,
            "status": "passed",
        }
    finally:
        for held in reversed(held_files):
            try:
                os.close(held.descriptor)
            except OSError:
                pass


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-result", type=Path, required=True)
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    try:
        result = check(
            parent_path=arguments.parent_result,
            run_a_path=arguments.run_a,
            run_b_path=arguments.run_b,
            receipt_path=arguments.receipt,
        )
    except IdleRepeatabilityCheckError as error:
        print(f"Idle repeatability readback failed: {error}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
