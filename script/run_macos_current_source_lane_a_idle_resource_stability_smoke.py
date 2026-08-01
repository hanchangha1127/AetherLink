#!/usr/bin/env python3
"""Measure bounded idle resources for one current-source Lane-A archive."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Iterator, Sequence

if __package__:
    from script import package_release_artifacts as archive_builder
    from script import run_macos_build24_idle_resource_stability_smoke as idle
else:
    import package_release_artifacts as archive_builder
    import run_macos_build24_idle_resource_stability_smoke as idle


engine = idle.engine
installed = idle.installed
recovery = idle.recovery
upgrade = idle.upgrade
IdleResourceSmokeError = idle.IdleResourceSmokeError
ROOT = Path(__file__).resolve().parents[1]

RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-current-source-lane-a-idle-resource-stability-v1"
)
READINESS_TIMEOUT_SECONDS = idle.READINESS_TIMEOUT_SECONDS
TERMINATION_TIMEOUT_SECONDS = idle.TERMINATION_TIMEOUT_SECONDS
_HISTORICAL_MEASUREMENT_SUMMARY = idle.measurement_summary
_HISTORICAL_BUDGET_FAILURE = (
    "idle resource samples exceeded a predeclared regression budget"
)

LIMITATIONS = (
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


def diagnostic_measurement_summary(
    samples: Sequence[dict[str, object]],
) -> dict[str, object]:
    try:
        return _HISTORICAL_MEASUREMENT_SUMMARY(samples)
    except IdleResourceSmokeError as error:
        if str(error) != _HISTORICAL_BUDGET_FAILURE:
            raise
        metrics = {
            "openFileDescriptors": idle.metric_summary(
                [
                    sample["openFileDescriptorCount"]
                    for sample in samples
                ],
                final_delta_limit=idle.FINAL_FD_DELTA_LIMIT,
                peak_delta_limit=idle.PEAK_FD_DELTA_LIMIT,
            ),
            "residentBytes": idle.metric_summary(
                [sample["residentBytes"] for sample in samples],
                final_delta_limit=idle.FINAL_RSS_DELTA_LIMIT_BYTES,
                peak_delta_limit=idle.PEAK_RSS_DELTA_LIMIT_BYTES,
            ),
            "threads": idle.metric_summary(
                [sample["threadCount"] for sample in samples],
                final_delta_limit=idle.FINAL_THREAD_DELTA_LIMIT,
                peak_delta_limit=idle.PEAK_THREAD_DELTA_LIMIT,
            ),
        }
        failed = {
            name: summary
            for name, summary in metrics.items()
            if summary["passed"] is False
        }
        detail = engine.canonical_json_bytes(failed).decode("ascii").strip()
        raise IdleResourceSmokeError(
            f"{_HISTORICAL_BUDGET_FAILURE}; failed metrics: {detail}"
        ) from error


@contextmanager
def diagnostic_measurement_scope() -> Iterator[None]:
    original = idle.measurement_summary
    if original is not _HISTORICAL_MEASUREMENT_SUMMARY:
        raise IdleResourceSmokeError(
            "historical idle measurement hook changed before observation"
        )
    idle.measurement_summary = diagnostic_measurement_summary
    try:
        yield
    finally:
        idle.measurement_summary = original


def current_release() -> recovery.ReleaseVersion:
    return recovery.current_release()


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return recovery.release_id_for(version)


def default_archive_dir() -> Path:
    version = current_release()
    return ROOT / "dist/releases" / release_id_for(version)


def require_exact_nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise IdleResourceSmokeError(
            f"{label} must be an exact nonnegative integer"
        )
    return value


def validate_source_snapshot(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "algorithm",
        "fileCount",
        "sha256",
    }:
        raise IdleResourceSmokeError(
            "current-source snapshot has an invalid closed schema"
        )
    if (
        value["algorithm"]
        != "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
        or type(value["fileCount"]) is not int
        or value["fileCount"] <= 0
        or type(value["sha256"]) is not str
        or len(value["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in value["sha256"])
    ):
        raise IdleResourceSmokeError(
            "current-source snapshot identity is invalid"
        )
    return {
        "algorithm": value["algorithm"],
        "fileCount": value["fileCount"],
        "sha256": value["sha256"],
    }


def source_snapshot_summary(value: object) -> dict[str, object]:
    if type(value) is not dict or not {
        "algorithm",
        "fileCount",
        "sha256",
    }.issubset(value):
        raise IdleResourceSmokeError(
            "current-source full snapshot lacks its summary identity"
        )
    return validate_source_snapshot(
        {
            "algorithm": value["algorithm"],
            "fileCount": value["fileCount"],
            "sha256": value["sha256"],
        }
    )


def validate_snapshot_files(
    value: object,
    *,
    release: engine.ReleaseInputs,
    release_id: str,
) -> dict[str, dict[str, object]]:
    expected_names = {
        f"{release_id}.zip",
        f"{release_id}.manifest.json",
        f"{release_id}.zip.sha256",
    }
    if type(value) is not dict or set(value) != expected_names:
        raise IdleResourceSmokeError(
            "current-source archive snapshot has an invalid sidecar set"
        )
    validated: dict[str, dict[str, object]] = {}
    for name in sorted(expected_names):
        record = value[name]
        if (
            type(record) is not dict
            or set(record) != {"sha256", "size"}
            or type(record["sha256"]) is not str
            or len(record["sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in record["sha256"]
            )
            or type(record["size"]) is not int
            or record["size"] <= 0
        ):
            raise IdleResourceSmokeError(
                f"current-source archive snapshot identity is invalid: {name}"
            )
        validated[name] = {
            "sha256": record["sha256"],
            "size": record["size"],
        }

    archive_name = f"{release_id}.zip"
    manifest_name = f"{release_id}.manifest.json"
    checksum_name = f"{release_id}.zip.sha256"
    if (
        validated[archive_name]["sha256"] != release.archive_sha256
        or validated[manifest_name]["sha256"] != release.manifest_sha256
    ):
        raise IdleResourceSmokeError(
            "loaded current-source release differs from its archive snapshot"
        )
    checksum_payload = release.checksum_path.read_bytes()
    if (
        len(checksum_payload) != validated[checksum_name]["size"]
        or hashlib.sha256(checksum_payload).hexdigest()
        != validated[checksum_name]["sha256"]
    ):
        raise IdleResourceSmokeError(
            "loaded current-source checksum differs from its archive snapshot"
        )
    return validated


def validate_artifact(
    value: object,
    *,
    version: recovery.ReleaseVersion,
) -> dict[str, object]:
    required = {
        "appTree",
        "buildNumber",
        "bundleIdentifier",
        "executableMode",
        "executableSha256",
        "executableSize",
        "marketingVersion",
        "uuid",
    }
    if type(value) is not dict or set(value) != required:
        raise IdleResourceSmokeError(
            "current-source artifact has an invalid closed schema"
        )
    tree = value["appTree"]
    if type(tree) is not dict or set(tree) != {
        "digestAlgorithm",
        "regularFileCount",
        "sha256",
        "totalRegularFileBytes",
    }:
        raise IdleResourceSmokeError(
            "current-source app tree has an invalid closed schema"
        )
    if (
        tree["digestAlgorithm"]
        != "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
        or type(tree["regularFileCount"]) is not int
        or tree["regularFileCount"] <= 0
        or type(tree["totalRegularFileBytes"]) is not int
        or tree["totalRegularFileBytes"] <= 0
        or type(tree["sha256"]) is not str
        or len(tree["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in tree["sha256"])
        or type(value["buildNumber"]) is not int
        or value["buildNumber"] != version.build_number
        or value["bundleIdentifier"] != engine.EXPECTED_BUNDLE_ID
        or type(value["executableMode"]) is not int
        or value["executableMode"] != 0o755
        or type(value["executableSize"]) is not int
        or value["executableSize"] <= 0
        or type(value["executableSha256"]) is not str
        or len(value["executableSha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value["executableSha256"]
        )
        or value["marketingVersion"] != version.marketing_version
        or type(value["uuid"]) is not str
        or not value["uuid"]
    ):
        raise IdleResourceSmokeError(
            "current-source artifact identity is invalid"
        )
    return {"appTree": dict(tree)}


@contextmanager
def isolated_resource_root(
    *,
    termination_timeout_seconds: float,
    lister: Callable[
        [], tuple[installed.RunningApplication, ...]
    ] = installed.list_bundle_applications,
) -> Iterator[
    tuple[Path, list[tuple[subprocess.Popen[bytes], Path]]]
]:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="aetherlink-current-source-lane-a-idle-resource-v1-"
        )
    ).resolve()
    owned_processes: list[tuple[subprocess.Popen[bytes], Path]] = []
    body_error: BaseException | None = None
    try:
        try:
            yield temporary_root, owned_processes
        except BaseException as error:
            body_error = error
            raise
    finally:
        cleanup_errors: list[BaseException] = []
        for process, executable in tuple(owned_processes):
            try:
                idle.cleanup_owned_child(
                    process,
                    executable,
                    timeout_seconds=termination_timeout_seconds,
                )
            except BaseException as error:
                cleanup_errors.append(error)
        try:
            unexpected = [
                application
                for application in lister()
                if temporary_root
                in Path(application.executable_path).resolve().parents
            ]
            if unexpected:
                cleanup_errors.append(
                    IdleResourceSmokeError(
                        "an unowned current-source temporary-root app "
                        "process remains; it was not terminated"
                    )
                )
        except BaseException as error:
            cleanup_errors.append(error)
        if cleanup_errors:
            diagnostic = IdleResourceSmokeError(
                "current-source idle resource cleanup failed; diagnostic "
                f"root retained at {temporary_root}"
            )
            if isinstance(body_error, (KeyboardInterrupt, SystemExit)):
                raise body_error from diagnostic
            for error in cleanup_errors:
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise error
            raise diagnostic from cleanup_errors[0]
        try:
            shutil.rmtree(temporary_root)
        except BaseException as error:
            raise IdleResourceSmokeError(
                "current-source idle resource temporary root cleanup failed; "
                f"diagnostic root retained at {temporary_root}"
            ) from error


def validate_run(value: object) -> dict[str, object]:
    required = {
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
    }
    if type(value) is not dict or set(value) != required:
        raise IdleResourceSmokeError(
            "current-source idle resource run has an invalid closed schema"
        )
    if (
        type(value["activationPolicy"]) is not int
        or value["activationPolicy"] != 0
        or value["appKitProcessAbsentAfterReap"] is not True
        or type(value["exitCode"]) is not int
        or value["exitCode"] != 0
        or value["finishedLaunching"] is not True
        or value["gracefulTerminationAccepted"] is not True
        or type(value["maximumObservedLatenessMilliseconds"]) is not int
        or value["maximumObservedLatenessMilliseconds"] < 0
        or value["maximumObservedLatenessMilliseconds"]
        > idle.SAMPLE_LATENESS_LIMIT_MILLISECONDS
        or value["ownedChildProcess"] is not True
        or value["processIdentifierRetained"] is not False
        or value["processReaped"] is not True
    ):
        raise IdleResourceSmokeError(
            "current-source idle resource run did not finish its exact "
            "owned-child contract"
        )
    recomputed_summary = idle.measurement_summary(value["samples"])
    if not idle.exact_json_value_equal(
        recomputed_summary,
        value["summary"],
    ):
        raise IdleResourceSmokeError(
            "current-source idle resource summary differs from samples"
        )
    maximum_lateness = max(
        sample["observedLatenessMilliseconds"]
        for sample in value["samples"]
    )
    if value["maximumObservedLatenessMilliseconds"] != maximum_lateness:
        raise IdleResourceSmokeError(
            "current-source idle resource maximum lateness differs from samples"
        )
    return value


def build_result(
    *,
    version: recovery.ReleaseVersion,
    release: engine.ReleaseInputs,
    artifact: dict[str, object],
    snapshot_files: dict[str, dict[str, object]],
    source_snapshot: dict[str, object],
    run: dict[str, object],
    preexisting_application_count: int,
) -> dict[str, object]:
    require_exact_nonnegative_int(
        preexisting_application_count,
        "preexisting application count",
    )
    release_id = release_id_for(version)
    validated_snapshot = validate_snapshot_files(
        snapshot_files,
        release=release,
        release_id=release_id,
    )
    validated_source = validate_source_snapshot(source_snapshot)
    validated_run = validate_run(run)
    os_version = idle.platform.mac_ver()[0]
    architecture = idle.platform.machine()
    logical_cpu_count = os.cpu_count()
    page_size = os.sysconf("SC_PAGE_SIZE")
    if (
        not os_version
        or not architecture
        or type(logical_cpu_count) is not int
        or logical_cpu_count <= 0
        or type(page_size) is not int
        or page_size <= 0
    ):
        raise IdleResourceSmokeError(
            "cannot determine the current-source observation environment"
        )
    return {
        "archiveReadback": {
            "currentSourceCompared": False,
            "mode": (
                "archive-only-with-materialized-source-snapshot-"
                "no-signature-check"
            ),
            "readbackAndExerciseSameSnapshot": True,
            "signatureVerificationPerformed": False,
            "snapshotFiles": validated_snapshot,
            "snapshotFilesUnchangedAfterExercise": True,
            "status": "passed",
        },
        "artifact": validate_artifact(artifact, version=version),
        "cleanup": {
            "ownedChildOnly": True,
            "preexistingApplicationsPreserved": True,
            "temporaryRootRemovedBeforePublication": True,
        },
        "environment": {
            "architecture": architecture,
            "logicalCpuCount": logical_cpu_count,
            "macOSVersion": os_version,
            "pageSizeBytes": page_size,
        },
        "isolation": {
            "afInetBindDeniedByPreflight": True,
            "networkDenied": True,
            "nonTemporaryWriteDeniedByPreflight": True,
            "profile": "allow-default-deny-network-and-non-temp-writes-v1",
            "sandboxed": True,
            "standardStreams": "devnull",
            "temporaryCFUserHomeConfigured": True,
        },
        "limitations": list(LIMITATIONS),
        "measurement": {
            "api": "macos-libproc-proc-pidinfo-v1",
            "baselineWindowSampleCount": idle.BASELINE_WINDOW_SAMPLE_COUNT,
            "finalWindowSampleCount": idle.FINAL_WINDOW_SAMPLE_COUNT,
            "intervalMilliseconds": idle.SAMPLE_INTERVAL_MILLISECONDS,
            "observationMilliseconds": idle.OBSERVATION_MILLISECONDS,
            "run": validated_run,
            "sampleCount": idle.SAMPLE_COUNT,
            "sampleLatenessLimitMilliseconds": (
                idle.SAMPLE_LATENESS_LIMIT_MILLISECONDS
            ),
            "status": "passed",
            "warmupMilliseconds": idle.WARMUP_MILLISECONDS,
        },
        "process": {
            "launchMethod": "sandbox-exec-direct-owned-child-v1",
            "preexistingApplicationCount": preexisting_application_count,
            "preexistingApplicationsUsedAsTerminationTargets": False,
            "rawProcessIdentifierRetained": False,
        },
        "release": {
            "archiveSha256": release.archive_sha256,
            "manifestSha256": release.manifest_sha256,
            "releaseId": release_id,
        },
        "repeatability": {
            "performed": False,
            "reason": "single-live-resource-observation-v1",
        },
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "sourceSnapshot": validated_source,
        "status": "passed",
    }


def exercise(
    *,
    archive_dir: Path,
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
    termination_timeout_seconds: float = TERMINATION_TIMEOUT_SECONDS,
) -> dict[str, object]:
    readiness_timeout_seconds = engine.validated_duration(
        readiness_timeout_seconds,
        "readiness timeout",
        0.1,
        60.0,
    )
    termination_timeout_seconds = engine.validated_duration(
        termination_timeout_seconds,
        "termination timeout",
        0.1,
        30.0,
    )
    idle.validate_libproc_abi()
    version = current_release()
    full_source_snapshot = archive_builder.source_snapshot(ROOT)
    source_snapshot = source_snapshot_summary(full_source_snapshot)
    preexisting = installed.list_bundle_applications()
    temporary_root_path: Path | None = None

    with isolated_resource_root(
        termination_timeout_seconds=termination_timeout_seconds,
    ) as (temporary_root, owned_processes):
        temporary_root_path = temporary_root
        snapshot_directory, snapshot_files = (
            upgrade.snapshot_archive_directory(
                archive_dir,
                version=version,
                destination_parent=temporary_root / "archive-snapshot",
            )
        )
        upgrade.verify_archive_readback(
            snapshot_directory,
            historical=False,
        )
        release = recovery.load_release_inputs(
            snapshot_directory,
            verify_readback=False,
            version=version,
        )
        validate_snapshot_files(
            snapshot_files,
            release=release,
            release_id=release_id_for(version),
        )
        app_path = engine.extract_packaged_app(
            release,
            temporary_root / "extracted-app",
        )
        artifact = idle.verify_extracted_app(
            app_path,
            release,
            version=version,
        )
        executable = app_path / engine.EXECUTABLE_RELATIVE_PATH

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        for path in (isolated_home, isolated_temporary, isolated_state):
            path.mkdir(mode=0o700)
        identity_file = isolated_state / "runtime-identity.json"
        profile = engine.build_sandbox_profile(temporary_root)
        engine.preflight_sandbox(profile, temporary_root)
        environment = engine.isolated_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
        )
        with diagnostic_measurement_scope():
            run = idle.run_owned_idle_observation(
                executable=executable,
                profile=profile,
                environment=environment,
                working_directory=temporary_root,
                readiness_timeout_seconds=readiness_timeout_seconds,
                termination_timeout_seconds=termination_timeout_seconds,
                owned_processes=owned_processes,
            )
        if installed.app_tree_evidence(app_path, release).record() != artifact[
            "appTree"
        ]:
            raise IdleResourceSmokeError(
                "current-source app tree changed during idle observation"
            )
        upgrade.require_unchanged_archive_snapshot(
            snapshot_directory,
            snapshot_files,
        )
        final_full_source_snapshot = archive_builder.source_snapshot(ROOT)
        if final_full_source_snapshot != full_source_snapshot:
            raise IdleResourceSmokeError(
                "materialized current-source snapshot changed during idle "
                "observation"
            )
        installed.assert_preexisting_applications_preserved(preexisting)
        result = build_result(
            version=version,
            release=release,
            artifact=artifact,
            snapshot_files=snapshot_files,
            source_snapshot=source_snapshot,
            run=run,
            preexisting_application_count=len(preexisting),
        )

    if (
        temporary_root_path is None
        or temporary_root_path.exists()
        or temporary_root_path.is_symlink()
    ):
        raise IdleResourceSmokeError(
            "current-source idle temporary root was not removed"
        )
    return result


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=default_archive_dir(),
    )
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=float,
        default=READINESS_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=float,
        default=TERMINATION_TIMEOUT_SECONDS,
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = exercise(
            archive_dir=arguments.archive_dir,
            readiness_timeout_seconds=arguments.readiness_timeout_seconds,
            termination_timeout_seconds=arguments.termination_timeout_seconds,
        )
    except (
        IdleResourceSmokeError,
        OSError,
        plistlib.InvalidFileException,
        ValueError,
    ) as error:
        print(
            f"Current-source Lane-A idle resource stability failed: {error}",
            file=sys.stderr,
        )
        return 1
    sys.stdout.buffer.write(engine.canonical_json_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
