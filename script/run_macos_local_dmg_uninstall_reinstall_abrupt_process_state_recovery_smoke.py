#!/usr/bin/env python3
"""Exercise persisted Build 24 state after an owned-child SIGKILL."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import math
import os
from pathlib import Path
import plistlib
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterator, Sequence
import zipfile

if __package__:
    from script import (
        run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke
        as state,
    )
else:
    import run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke as state


base = state.base
clean = state.clean
dmg = state.dmg
engine = state.engine
installed = state.installed
recovery = state.recovery
same_dmg = state.same_dmg
uninstall = state.uninstall
upgrade = state.upgrade
LocalDMGSmokeError = state.LocalDMGSmokeError
ROOT = state.ROOT
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
    "abrupt-process-state-recovery-v1"
)
REPEATABILITY_SCHEMA_VERSION = 1
REPEATABILITY_SCOPE = (
    "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
    "abrupt-process-state-recovery-repeatability-v1"
)
ABRUPT_LAUNCH_METHOD = "direct-installed-executable-owned-child"
GRACEFUL_LAUNCH_METHOD = "launchservices-open-exact-installed-app"
ABRUPT_PROCESS_DISPOSITION = (
    "exact-owned-child-pid-sigkill-reaped-and-appkit-absent"
)
SIGKILL_NUMBER = int(signal.SIGKILL)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "same-created-dmg-image-remount-only",
    "fixed-runtime-chat-legacy-canary-only",
    "post-persisted-sqlite-readback-observation-sigkill-only",
    "legacy-fixture-removed-by-harness-before-reinstall-readback",
    "no-in-flight-write-checkpoint-or-open-transaction-observed",
    (
        "not-write-durability-crash-consistency-power-loss-or-"
        "kernel-crash-evidence"
    ),
    "not-os-restart-ui-force-quit-arbitrary-history-or-soak-evidence",
    "application-support-retained-no-automatic-data-cleanup",
    "post-archive-harness-not-build-input-member",
    (
        "not-finder-system-applications-quarantine-gatekeeper-signing-"
        "notarization-or-stapling-evidence"
    ),
    (
        "not-upgrade-rollback-device-provider-network-ui-accessibility-"
        "production-or-security-evidence"
    ),
)


def current_release() -> recovery.ReleaseVersion:
    return state.current_release()


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return state.release_id_for(version)


def default_archive_dir() -> Path:
    return state.default_archive_dir()


def default_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-local-dmg-uninstall-reinstall-"
            "abrupt-process-state-recovery-v1.json"
        )
    )


def default_repeatability_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-local-dmg-uninstall-reinstall-"
            "abrupt-process-state-recovery-repeatability-v1.json"
        )
    )


def _expected_sqlite_evidence() -> recovery.SQLiteCanaryEvidence:
    return recovery.SQLiteCanaryEvidence(
        event_json_sha256=recovery.CANARY_EVENT_JSON_SHA256,
        event_json_size=len(recovery.CANARY_EVENT_JSON),
        integrity_check="ok",
        total_event_count=1,
    )


def _validate_sqlite(
    value: recovery.SQLiteCanaryEvidence,
) -> dict[str, object]:
    expected = _expected_sqlite_evidence()
    if (
        not isinstance(value, recovery.SQLiteCanaryEvidence)
        or type(value.event_json_size) is not int
        or type(value.total_event_count) is not int
        or value != expected
    ):
        raise LocalDMGSmokeError(
            "abrupt-process SQLite canary evidence is invalid"
        )
    return value.record()


def _validate_empty_log(value: dict[str, object]) -> dict[str, object]:
    expected = {
        "sha256": EMPTY_SHA256,
        "size": 0,
    }
    if (
        type(value) is not dict
        or not upgrade.exact_results_equal(value, expected)
    ):
        raise LocalDMGSmokeError(
            "abrupt-process stderr evidence must be exactly empty"
        )
    return expected


def _validate_graceful_run(
    value: dict[str, object],
    *,
    ordinal: int,
) -> dict[str, object]:
    required = {
        "activationPolicy",
        "executablePathMatched",
        "finishedLaunching",
        "minimumObservationSeconds",
        "newProcessIdentifierDetected",
        "observationDeadlineReached",
        "ordinal",
        "terminationAccepted",
    }
    if type(value) is not dict or set(value) != required:
        raise LocalDMGSmokeError(
            "abrupt-process graceful launch shape is invalid"
        )
    duration = value["minimumObservationSeconds"]
    if (
        type(value["activationPolicy"]) is not int
        or value["activationPolicy"] != 0
        or type(duration) not in (int, float)
        or not math.isfinite(duration)
        or not engine.MINIMUM_OBSERVATION_SECONDS <= duration <= 30.0
        or type(value["ordinal"]) is not int
        or value["ordinal"] != ordinal
        or any(
            value[key] is not True
            for key in (
                "executablePathMatched",
                "finishedLaunching",
                "newProcessIdentifierDetected",
                "observationDeadlineReached",
                "terminationAccepted",
            )
        )
    ):
        raise LocalDMGSmokeError(
            "abrupt-process graceful launch record is invalid"
        )
    return {
        **value,
        "launchMethod": GRACEFUL_LAUNCH_METHOD,
    }


def _validate_abrupt_run(
    value: dict[str, object],
) -> dict[str, object]:
    required = {
        "activationPolicy",
        "appKitProcessAbsentAfterReap",
        "exactExecutableIdentityMatchedImmediatelyBeforeSignal",
        "exitCode",
        "finishedLaunching",
        "launchMethod",
        "minimumObservationSeconds",
        "newProcessIdentifierDetected",
        "observationDeadlineReached",
        "ordinal",
        "ownedChildProcess",
        "persistenceProbePassedBeforeSignal",
        "processReaped",
        "signalName",
        "signalNumber",
    }
    if type(value) is not dict or set(value) != required:
        raise LocalDMGSmokeError(
            "abrupt-process owned-child launch shape is invalid"
        )
    duration = value["minimumObservationSeconds"]
    if (
        type(value["activationPolicy"]) is not int
        or value["activationPolicy"] != 0
        or type(value["exitCode"]) is not int
        or value["exitCode"] != -SIGKILL_NUMBER
        or value["launchMethod"] != ABRUPT_LAUNCH_METHOD
        or type(duration) not in (int, float)
        or not math.isfinite(duration)
        or not engine.MINIMUM_OBSERVATION_SECONDS <= duration <= 30.0
        or type(value["ordinal"]) is not int
        or value["ordinal"] != 2
        or type(value["signalNumber"]) is not int
        or value["signalNumber"] != SIGKILL_NUMBER
        or value["signalName"] != "SIGKILL"
        or any(
            value[key] is not True
            for key in (
                "appKitProcessAbsentAfterReap",
                "exactExecutableIdentityMatchedImmediatelyBeforeSignal",
                "finishedLaunching",
                "newProcessIdentifierDetected",
                "observationDeadlineReached",
                "ownedChildProcess",
                "persistenceProbePassedBeforeSignal",
                "processReaped",
            )
        )
    ):
        raise LocalDMGSmokeError(
            "abrupt-process owned-child launch record is invalid"
        )
    return dict(value)


def _cleanup_owned_child(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
) -> None:
    failures: list[BaseException] = []
    interruption: KeyboardInterrupt | SystemExit | None = None

    def record_failure(error: BaseException) -> None:
        nonlocal interruption
        failures.append(error)
        if (
            interruption is None
            and isinstance(error, (KeyboardInterrupt, SystemExit))
        ):
            interruption = error

    def return_or_interrupt() -> None:
        if interruption is not None:
            raise interruption

    for _attempt in range(2):
        try:
            if process.poll() is not None:
                return_or_interrupt()
                return
        except BaseException as error:
            record_failure(error)
        try:
            process.send_signal(signal.SIGKILL)
        except BaseException as error:
            record_failure(error)
        try:
            process.wait(timeout=timeout_seconds)
        except BaseException as error:
            record_failure(error)
        try:
            if process.poll() is not None:
                return_or_interrupt()
                return
        except BaseException as error:
            record_failure(error)
    if interruption is not None:
        raise interruption
    raise LocalDMGSmokeError(
        "owned abrupt-process child cleanup could not prove reap: "
        f"{[type(error).__name__ for error in failures]!r}"
    ) from (failures[-1] if failures else None)


@contextmanager
def isolated_abrupt_root(
    *,
    termination_timeout_seconds: float,
) -> Iterator[
    tuple[
        Path,
        list[subprocess.Popen[bytes]],
    ]
]:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix=(
                "aetherlink-macos-local-dmg-abrupt-process-recovery-v1-"
            )
        )
    ).resolve()
    owned_processes: list[subprocess.Popen[bytes]] = []
    body_error: BaseException | None = None
    try:
        try:
            yield temporary_root, owned_processes
        except BaseException as error:
            body_error = error
            raise
    finally:
        cleanup_errors: list[BaseException] = []
        for process in tuple(owned_processes):
            try:
                _cleanup_owned_child(
                    process,
                    timeout_seconds=termination_timeout_seconds,
                )
            except BaseException as error:
                cleanup_errors.append(error)
        try:
            upgrade.cleanup_exact_temporary_applications(
                temporary_root,
                termination_timeout_seconds=termination_timeout_seconds,
            )
        except BaseException as error:
            cleanup_errors.append(error)
        for name in ("mount-initial", "mount-reinstall"):
            try:
                same_dmg.recover_unmount(
                    dmg_path=temporary_root / "local-image.dmg",
                    mountpoint=temporary_root / name,
                )
            except BaseException as error:
                cleanup_errors.append(error)
        if cleanup_errors:
            diagnostic_error = LocalDMGSmokeError(
                "abrupt-process cleanup failed; diagnostic root retained "
                f"at {temporary_root}"
            )
            if isinstance(body_error, (KeyboardInterrupt, SystemExit)):
                raise body_error from diagnostic_error
            for error in cleanup_errors:
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise error
            raise diagnostic_error from cleanup_errors[0]
        try:
            shutil.rmtree(temporary_root)
        except BaseException as error:
            diagnostic_error = LocalDMGSmokeError(
                "abrupt-process root cleanup incomplete; diagnostic root "
                f"may remain at {temporary_root}"
            )
            if isinstance(body_error, (KeyboardInterrupt, SystemExit)):
                raise body_error from diagnostic_error
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise diagnostic_error from error


def run_owned_abrupt_readback_cycle(
    *,
    ordinal: int,
    app_path: Path,
    environment: dict[str, str],
    profile: str,
    stdout_path: Path,
    stderr_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
    persistence_probe: Callable[[], None],
    popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    readiness_waiter: Callable[..., engine.ApplicationStatus] = (
        engine.wait_for_application_readiness
    ),
    query: Callable[
        [int],
        engine.ApplicationStatus | None,
    ] = engine.query_application,
    gone_waiter: Callable[..., bool] = (
        installed.wait_until_application_gone
    ),
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    owned_processes: list[subprocess.Popen[bytes]] | None = None,
) -> tuple[int, dict[str, object], dict[str, object], dict[str, object]]:
    if ordinal != 2:
        raise LocalDMGSmokeError(
            "owned abrupt-process cycle must use ordinal 2"
        )
    executable = app_path / installed.EXECUTABLE_RELATIVE_PATH
    clean.prepare_captured_log(stdout_path)
    clean.prepare_captured_log(stderr_path)
    process: subprocess.Popen[bytes] | None = None
    signal_was_evidence = False
    status: engine.ApplicationStatus | None = None
    try:
        with (
            stdout_path.open("wb") as stdout_handle,
            stderr_path.open("wb") as stderr_handle,
        ):
            process = popen_factory(
                [
                    str(engine.SANDBOX_EXEC),
                    "-p",
                    profile,
                    str(executable),
                ],
                cwd=app_path.parent,
                env=environment,
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
            if owned_processes is not None:
                owned_processes.append(process)
            status = readiness_waiter(
                process,
                executable,
                timeout_seconds=readiness_timeout_seconds,
                query=query,
            )
            deadline = monotonic() + observation_seconds
            while monotonic() < deadline:
                exit_code = process.poll()
                if exit_code is not None:
                    raise LocalDMGSmokeError(
                        "owned abrupt-process child exited before signal"
                    )
                remaining = max(0.0, deadline - monotonic())
                sleeper(min(0.1, remaining))

            observation = recovery.verify_observation_log(
                stdout_path,
                recovery.SQLITE_READBACK_MODE,
            )
            stderr_evidence = clean.validate_captured_log(
                stderr_path,
                label="owned abrupt-process stderr",
            )
            _validate_empty_log(stderr_evidence)
            persistence_probe()

            if process.poll() is not None:
                raise LocalDMGSmokeError(
                    "owned abrupt-process child exited before identity check"
                )
            exact_status = installed.assert_query_identity(
                query(process.pid),
                executable,
            )
            if (
                not exact_status.finished_launching
                or exact_status.activation_policy != 0
            ):
                raise LocalDMGSmokeError(
                    "owned abrupt-process child lost ready identity"
                )
            process.send_signal(signal.SIGKILL)
            try:
                exit_code = process.wait(
                    timeout=termination_timeout_seconds
                )
            except subprocess.TimeoutExpired as error:
                raise LocalDMGSmokeError(
                    "owned abrupt-process child did not reap on time"
                ) from error
            if exit_code != -signal.SIGKILL:
                raise LocalDMGSmokeError(
                    "owned abrupt-process child exit did not prove SIGKILL"
                )
            if not gone_waiter(
                process.pid,
                timeout_seconds=termination_timeout_seconds,
                query=query,
            ):
                raise LocalDMGSmokeError(
                    "owned abrupt-process child remained in AppKit"
                )
            signal_was_evidence = True
            return (
                process.pid,
                {
                    "activationPolicy": status.activation_policy,
                    "appKitProcessAbsentAfterReap": True,
                    (
                        "exactExecutableIdentityMatchedImmediatelyBeforeSignal"
                    ): True,
                    "exitCode": exit_code,
                    "finishedLaunching": status.finished_launching,
                    "launchMethod": ABRUPT_LAUNCH_METHOD,
                    "minimumObservationSeconds": observation_seconds,
                    "newProcessIdentifierDetected": True,
                    "observationDeadlineReached": True,
                    "ordinal": ordinal,
                    "ownedChildProcess": True,
                    "persistenceProbePassedBeforeSignal": True,
                    "processReaped": True,
                    "signalName": "SIGKILL",
                    "signalNumber": SIGKILL_NUMBER,
                },
                observation,
                stderr_evidence,
            )
    finally:
        if process is not None and not signal_was_evidence:
            _cleanup_owned_child(
                process,
                timeout_seconds=termination_timeout_seconds,
            )
        if process is not None and owned_processes is not None:
            try:
                reaped = process.poll() is not None
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                reaped = False
            if reaped and process in owned_processes:
                owned_processes.remove(process)


def build_result(
    *,
    release: engine.ReleaseInputs,
    release_id: str,
    app_tree: installed.AppTreeEvidence,
    migration_run: dict[str, object],
    abrupt_run: dict[str, object],
    recovery_run: dict[str, object],
    migration_observation: dict[str, object],
    abrupt_observation: dict[str, object],
    recovery_observation: dict[str, object],
    migration_sqlite: recovery.SQLiteCanaryEvidence,
    abrupt_sqlite: recovery.SQLiteCanaryEvidence,
    post_abrupt_sqlite: recovery.SQLiteCanaryEvidence,
    recovery_sqlite: recovery.SQLiteCanaryEvidence,
    auxiliary_sqlite: Sequence[dict[str, object]],
    migration_stderr: dict[str, object],
    abrupt_stderr: dict[str, object],
    recovery_stderr: dict[str, object],
    runtime_identity_present: bool,
    snapshot_files: dict[str, dict[str, object]],
) -> dict[str, object]:
    if runtime_identity_present is not True:
        raise LocalDMGSmokeError(
            "abrupt-process runtime identity was not created"
        )
    sqlite_records = [
        _validate_sqlite(value)
        for value in (
            migration_sqlite,
            abrupt_sqlite,
            post_abrupt_sqlite,
            recovery_sqlite,
        )
    ]
    if any(record != sqlite_records[0] for record in sqlite_records[1:]):
        raise LocalDMGSmokeError(
            "abrupt-process SQLite canary changed across recovery"
        )
    validated_files = dmg.validated_snapshot_files(
        release=release,
        release_id=release_id,
        snapshot_files=snapshot_files,
    )
    tree_record = state._validate_app_tree(app_tree)
    if tree_record["digestAlgorithm"] != installed.TREE_DIGEST_ALGORITHM:
        raise LocalDMGSmokeError(
            "abrupt-process app tree digest algorithm is invalid"
        )
    migration_record = state._validate_observation(
        migration_observation,
        mode=recovery.MIGRATION_MODE,
    )
    abrupt_record = state._validate_observation(
        abrupt_observation,
        mode=recovery.SQLITE_READBACK_MODE,
    )
    recovery_record = state._validate_observation(
        recovery_observation,
        mode=recovery.SQLITE_READBACK_MODE,
    )
    auxiliary_records = state._validate_auxiliary_sqlite(auxiliary_sqlite)
    migration_log = _validate_empty_log(migration_stderr)
    abrupt_log = _validate_empty_log(abrupt_stderr)
    recovery_log = _validate_empty_log(recovery_stderr)
    validated_migration_run = _validate_graceful_run(
        migration_run,
        ordinal=1,
    )
    validated_abrupt_run = _validate_abrupt_run(abrupt_run)
    validated_recovery_run = _validate_graceful_run(
        recovery_run,
        ordinal=3,
    )
    return {
        "abruptTermination": {
            "appKitProcessAbsentAfterReap": True,
            "exactExecutableRevalidatedBeforeSignal": True,
            "exitCode": -SIGKILL_NUMBER,
            "gracefulTerminationRequested": False,
            "inFlightWriteCheckpointObserved": False,
            "launchMethod": ABRUPT_LAUNCH_METHOD,
            "migrationCommittedBeforeAbruptLaunch": True,
            "observationCompletedBeforeSignal": True,
            "persistenceProbePassedBeforeSignal": True,
            "processDisposition": ABRUPT_PROCESS_DISPOSITION,
            "processReaped": True,
            "signal": "SIGKILL",
            "signalNumber": SIGKILL_NUMBER,
        },
        "archiveReadback": {
            "currentSourceCompared": False,
            "mode": dmg.ARCHIVE_READBACK_MODE,
            "readbackAndExerciseSameSnapshot": True,
            "snapshotFiles": validated_files,
            "snapshotFilesUnchangedAfterExercise": True,
            "status": "passed",
        },
        "canary": state._expected_canary_record(),
        "image": {
            "ephemeral": True,
            "filesystem": base.DMG_FILESYSTEM,
            "format": base.DMG_FORMAT,
            "retained": False,
            "sameImageBytesUsedForBothInstalls": True,
            "verified": True,
        },
        "installation": {
            "adHocAppSealAndVersionVerified": True,
            "applicationsAliasPresent": True,
            "copyTool": "ditto",
            "exactReleaseTreeCopiedEachInstall": True,
            "installCount": 2,
            "origin": "same-ephemeral-local-dmg",
            "reinstallTreeMatchesInitial": True,
            "statePresentBeforeReinstall": True,
            "tree": tree_record,
        },
        "isolation": {
            "preexistingBundleApplicationsPreserved": True,
            "runtimeIdentityFileOverrideConfigured": True,
            "sandboxedOwnedChildConfigured": True,
            "temporaryCFUserHomeConfigured": True,
        },
        "launches": {
            "distinctProcessIdentifiers": True,
            "exactInstalledBundlePerCycle": True,
            "gracefulLaunchServicesCommandPolicy": clean.COMMAND_POLICY,
            "noExactTemporaryAppRemaining": True,
            "runs": [
                validated_migration_run,
                validated_abrupt_run,
                validated_recovery_run,
            ],
            "stderr": {
                "abruptReadback": abrupt_log,
                "migration": migration_log,
                "recoveryReadback": recovery_log,
            },
        },
        "limitations": list(LIMITATIONS),
        "mount": {
            "cycleCount": 2,
            "detachedBeforeEachLaunch": True,
            "exactFreshMountpointPerInstall": True,
            "nobrowse": True,
            "oneMountedEntityPerInstall": True,
            "readOnly": True,
            "unmountedAfterEachCopy": True,
        },
        "release": {
            "archiveSha256": release.archive_sha256,
            "manifestSha256": release.manifest_sha256,
            "releaseId": release_id,
        },
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "stateRecovery": {
            "applicationSupportPreservedAcrossRemovalAndReinstall": True,
            "auxiliarySQLite": auxiliary_records,
            "databaseCount": 1 + len(auxiliary_records),
            "legacyAbsentBeforeAbruptAndRecoveryReadback": True,
            "legacyFixturePreservedUnchanged": True,
            "legacyRemovedByHarnessBeforeReinstall": True,
            "migrationObservation": migration_record,
            "migrationSQLite": sqlite_records[0],
            "ownedAbruptReadbackObservation": abrupt_record,
            "ownedAbruptReadbackSQLite": sqlite_records[1],
            "postAbruptSQLite": sqlite_records[2],
            (
                "postAbruptStateBytesAndModesUnchangedAcrossRemovalReinstall"
            ): True,
            "recoveryReadbackObservation": recovery_record,
            "recoveryReadbackSQLite": sqlite_records[3],
            "runtimeIdentityFilePresent": True,
            "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination": (
                True
            ),
            "totalEventCount": 1,
        },
        "status": "passed",
        "uninstall": {
            "appAbsentAfterEachRemoval": True,
            "applicationSupportCleanupPerformed": False,
            "exactTemporaryAppPathOnly": True,
            "exactTemporaryAppStoppedBeforeEachRemoval": True,
            "removalCount": 2,
            "removalMethod": "python-shutil-rmtree",
        },
    }


def execute(
    *,
    archive_dir: Path,
    result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    readiness_timeout_seconds = engine.validated_duration(
        readiness_timeout_seconds,
        "readiness timeout",
        0.1,
        60.0,
    )
    observation_seconds = engine.validated_duration(
        observation_seconds,
        "observation window",
        engine.MINIMUM_OBSERVATION_SECONDS,
        30.0,
    )
    termination_timeout_seconds = engine.validated_duration(
        termination_timeout_seconds,
        "termination timeout",
        0.1,
        30.0,
    )
    same_dmg.require_result_outside_archive(result_path, archive_dir)

    version = current_release()
    release_id = release_id_for(version)
    preexisting_applications = installed.list_bundle_applications()

    with isolated_abrupt_root(
        termination_timeout_seconds=termination_timeout_seconds,
    ) as (temporary_root, owned_processes):
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
        extracted_app = engine.extract_packaged_app(
            release,
            temporary_root / "extracted-app",
        )
        recovery.verify_packaged_app(
            extracted_app,
            release,
            version=version,
        )
        release_tree = installed.app_tree_evidence(
            extracted_app,
            release,
        )

        staging_root = temporary_root / "dmg-staging"
        staged_app = base.stage_dmg_root(extracted_app, staging_root)
        recovery.verify_packaged_app(
            staged_app,
            release,
            version=version,
        )
        if installed.app_tree_evidence(staged_app, release) != release_tree:
            raise LocalDMGSmokeError(
                "staged abrupt-process app differs from release"
            )

        dmg_path = temporary_root / "local-image.dmg"
        base.run_bounded_command(
            base.create_dmg_command(staging_root, dmg_path)
        )
        base.run_bounded_command(base.verify_dmg_command(dmg_path))
        expected_image_identity = same_dmg.image_identity(dmg_path)

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        logs = temporary_root / "logs"
        initial_mountpoint = temporary_root / "mount-initial"
        reinstall_mountpoint = temporary_root / "mount-reinstall"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
            logs,
            initial_mountpoint,
            reinstall_mountpoint,
        ):
            path.mkdir(mode=0o700)
        installed_app = (
            isolated_home / "Applications" / installed.APP_RELATIVE_PATH
        )

        initial_tree = same_dmg.copy_same_image(
            dmg_path=dmg_path,
            mountpoint=initial_mountpoint,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            installed_app=installed_app,
            release=release,
            version=version,
            expected_tree=release_tree,
        )
        if initial_tree != release_tree:
            raise LocalDMGSmokeError(
                "initial abrupt-process install differs from release"
            )
        same_dmg.require_same_image(dmg_path, expected_image_identity)

        identity_file = isolated_state / "runtime-identity.json"
        application_support = (
            isolated_home / "Library/Application Support/AetherLink"
        )
        legacy_path = application_support / recovery.LEGACY_FILENAME
        database_path = application_support / recovery.DATABASE_FILENAME
        if (
            application_support.exists()
            or application_support.is_symlink()
            or identity_file.exists()
            or identity_file.is_symlink()
        ):
            raise LocalDMGSmokeError(
                "clean-HOME abrupt-process state existed before fixture"
            )
        recovery.write_legacy_fixture(legacy_path)

        migration_environment = clean.recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.MIGRATION_MODE,
        )
        migration_stdout = logs / "run-1-stdout.log"
        migration_stderr_path = logs / "run-1-stderr.log"
        migration_pid, migration_run = (
            clean.run_recovery_launch_services_cycle(
                ordinal=1,
                app_path=installed_app,
                environment=migration_environment,
                stdout_path=migration_stdout,
                stderr_path=migration_stderr_path,
                readiness_timeout_seconds=readiness_timeout_seconds,
                observation_seconds=observation_seconds,
                termination_timeout_seconds=termination_timeout_seconds,
            )
        )
        migration_stderr = clean.validate_captured_log(
            migration_stderr_path,
            label="migration stderr",
        )
        _validate_empty_log(migration_stderr)
        migration_observation = recovery.verify_observation_log(
            migration_stdout,
            recovery.MIGRATION_MODE,
        )
        migration_sqlite = recovery.sqlite_canary_evidence(database_path)
        _validate_sqlite(migration_sqlite)
        migration_auxiliary = clean.auxiliary_sqlite_evidence(
            application_support
        )
        state._validate_auxiliary_sqlite(migration_auxiliary)
        if installed.app_tree_evidence(installed_app, release) != initial_tree:
            raise LocalDMGSmokeError(
                "installed app changed during migration"
            )
        state_with_legacy = installed.state_file_records(
            application_support,
            identity_file,
        )

        uninstall.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=release,
            expected_tree=initial_tree,
        )
        state.require_recovery_state(
            label="during initial abrupt-process removal",
            application_support=application_support,
            identity_file=identity_file,
            expected_sqlite=migration_sqlite,
            expected_auxiliary=migration_auxiliary,
            expected_files=state_with_legacy,
            legacy_must_be_absent=False,
        )

        preserved_legacy = recovery.remove_legacy_before_readback(
            legacy_path,
            temporary_root / "preserved-legacy",
        )
        state.require_preserved_legacy(preserved_legacy)
        state_without_legacy = installed.state_file_records(
            application_support,
            identity_file,
        )
        expected_removed_path = (
            f"application-support/{recovery.LEGACY_FILENAME}"
        )
        if same_dmg.changed_state_paths(
            state_with_legacy,
            state_without_legacy,
        ) != [expected_removed_path]:
            raise LocalDMGSmokeError(
                "harness changed state beyond the legacy fixture"
            )

        same_dmg.require_same_image(dmg_path, expected_image_identity)
        reinstalled_tree = same_dmg.copy_same_image(
            dmg_path=dmg_path,
            mountpoint=reinstall_mountpoint,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            installed_app=installed_app,
            release=release,
            version=version,
            expected_tree=release_tree,
        )
        if reinstalled_tree != initial_tree:
            raise LocalDMGSmokeError(
                "same-image abrupt-process reinstall differs"
            )
        state.require_recovery_state(
            label="before owned abrupt-process readback",
            application_support=application_support,
            identity_file=identity_file,
            expected_sqlite=migration_sqlite,
            expected_auxiliary=migration_auxiliary,
            expected_files=state_without_legacy,
            legacy_must_be_absent=True,
        )

        readback_environment = clean.recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.SQLITE_READBACK_MODE,
        )
        sandbox_profile = engine.build_sandbox_profile(temporary_root)
        engine.preflight_sandbox(sandbox_profile, temporary_root)
        pre_signal_state: dict[str, installed.FileIdentity] | None = None
        pre_signal_sqlite: recovery.SQLiteCanaryEvidence | None = None

        def persistence_probe() -> None:
            nonlocal pre_signal_state, pre_signal_sqlite
            observed_sqlite = recovery.sqlite_canary_evidence(database_path)
            _validate_sqlite(observed_sqlite)
            if observed_sqlite != migration_sqlite:
                raise LocalDMGSmokeError(
                    "owned child observed a changed canary before signal"
                )
            observed_auxiliary = clean.auxiliary_sqlite_evidence(
                application_support
            )
            if observed_auxiliary != migration_auxiliary:
                raise LocalDMGSmokeError(
                    "auxiliary SQLite changed before abrupt signal"
                )
            first_state = installed.state_file_records(
                application_support,
                identity_file,
            )
            second_state = installed.state_file_records(
                application_support,
                identity_file,
            )
            if (
                first_state != state_without_legacy
                or second_state != first_state
                or installed.app_tree_evidence(
                    installed_app,
                    release,
                )
                != reinstalled_tree
            ):
                raise LocalDMGSmokeError(
                    "owned child state was not quiescent before signal"
                )
            pre_signal_state = second_state
            pre_signal_sqlite = observed_sqlite

        abrupt_stdout = logs / "run-2-stdout.log"
        abrupt_stderr_path = logs / "run-2-stderr.log"
        (
            abrupt_pid,
            abrupt_run,
            abrupt_observation,
            abrupt_stderr,
        ) = run_owned_abrupt_readback_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=readback_environment,
            profile=sandbox_profile,
            stdout_path=abrupt_stdout,
            stderr_path=abrupt_stderr_path,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
            persistence_probe=persistence_probe,
            owned_processes=owned_processes,
        )
        if pre_signal_state is None or pre_signal_sqlite is None:
            raise LocalDMGSmokeError(
                "owned child did not capture pre-signal persisted state"
            )
        post_abrupt_sqlite = recovery.sqlite_canary_evidence(database_path)
        post_abrupt_auxiliary = clean.auxiliary_sqlite_evidence(
            application_support
        )
        post_abrupt_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if (
            post_abrupt_sqlite != pre_signal_sqlite
            or post_abrupt_auxiliary != migration_auxiliary
            or post_abrupt_state != pre_signal_state
            or installed.app_tree_evidence(installed_app, release)
            != reinstalled_tree
        ):
            raise LocalDMGSmokeError(
                "persisted state changed immediately after abrupt signal"
            )

        recovery_stdout = logs / "run-3-stdout.log"
        recovery_stderr_path = logs / "run-3-stderr.log"
        recovery_pid, recovery_run = (
            clean.run_recovery_launch_services_cycle(
                ordinal=3,
                app_path=installed_app,
                environment=readback_environment,
                stdout_path=recovery_stdout,
                stderr_path=recovery_stderr_path,
                readiness_timeout_seconds=readiness_timeout_seconds,
                observation_seconds=observation_seconds,
                termination_timeout_seconds=termination_timeout_seconds,
            )
        )
        if len({migration_pid, abrupt_pid, recovery_pid}) != 3:
            raise LocalDMGSmokeError(
                "abrupt-process recovery did not use three distinct PIDs"
            )
        recovery_stderr = clean.validate_captured_log(
            recovery_stderr_path,
            label="recovery-readback stderr",
        )
        _validate_empty_log(recovery_stderr)
        recovery_observation = recovery.verify_observation_log(
            recovery_stdout,
            recovery.SQLITE_READBACK_MODE,
        )
        recovery_sqlite = recovery.sqlite_canary_evidence(database_path)
        recovery_auxiliary = clean.auxiliary_sqlite_evidence(
            application_support
        )
        recovery_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if (
            recovery_sqlite != migration_sqlite
            or recovery_auxiliary != migration_auxiliary
            or recovery_state != post_abrupt_state
            or installed.app_tree_evidence(installed_app, release)
            != reinstalled_tree
        ):
            raise LocalDMGSmokeError(
                "persisted state changed during recovery readback"
            )

        uninstall.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=release,
            expected_tree=reinstalled_tree,
        )
        state.require_recovery_state(
            label="after final abrupt-process removal",
            application_support=application_support,
            identity_file=identity_file,
            expected_sqlite=migration_sqlite,
            expected_auxiliary=migration_auxiliary,
            expected_files=recovery_state,
            legacy_must_be_absent=True,
        )
        state.require_preserved_legacy(preserved_legacy)
        same_dmg.require_same_image(dmg_path, expected_image_identity)
        upgrade.require_unchanged_archive_snapshot(
            snapshot_directory,
            snapshot_files,
        )
        installed.assert_preexisting_applications_preserved(
            preexisting_applications
        )
        result = build_result(
            release=release,
            release_id=release_id,
            app_tree=reinstalled_tree,
            migration_run=migration_run,
            abrupt_run=abrupt_run,
            recovery_run=recovery_run,
            migration_observation=migration_observation,
            abrupt_observation=abrupt_observation,
            recovery_observation=recovery_observation,
            migration_sqlite=migration_sqlite,
            abrupt_sqlite=pre_signal_sqlite,
            post_abrupt_sqlite=post_abrupt_sqlite,
            recovery_sqlite=recovery_sqlite,
            auxiliary_sqlite=migration_auxiliary,
            migration_stderr=migration_stderr,
            abrupt_stderr=abrupt_stderr,
            recovery_stderr=recovery_stderr,
            runtime_identity_present=identity_file.is_file(),
            snapshot_files=snapshot_files,
        )

    state.publish_result(result_path, result)
    return result


def execute_repeatability(
    *,
    archive_dir: Path,
    result_path: Path,
    repeatability_result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    upgrade.require_output_paths_outside_archives(
        (result_path, repeatability_result_path),
        (archive_dir,),
    )
    run_results: list[dict[str, object]] = []
    run_bytes: list[bytes] = []
    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-abrupt-recovery-repeatability-results-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        for ordinal in (1, 2):
            run_path = temporary_root / f"run-{ordinal}.json"
            result = execute(
                archive_dir=archive_dir,
                result_path=run_path,
                readiness_timeout_seconds=readiness_timeout_seconds,
                observation_seconds=observation_seconds,
                termination_timeout_seconds=termination_timeout_seconds,
            )
            payload = run_path.read_bytes()
            if payload != engine.canonical_json_bytes(result):
                raise LocalDMGSmokeError(
                    f"abrupt-process run {ordinal} result differs"
                )
            run_results.append(result)
            run_bytes.append(payload)
    if (
        run_bytes[0] != run_bytes[1]
        or not upgrade.exact_results_equal(
            run_results[0],
            run_results[1],
        )
    ):
        raise LocalDMGSmokeError(
            "two abrupt-process runs did not produce identical results"
        )

    version = current_release()
    release_id = release_id_for(version)
    identity = {
        "sha256": hashlib.sha256(run_bytes[0]).hexdigest(),
        "size": len(run_bytes[0]),
    }
    receipt = {
        "canonicalResult": {
            "fileName": result_path.name,
            **identity,
        },
        "limitations": [
            "same-host-two-recorded-runs-only",
            "not-arbitrary-repeatability-or-long-soak-evidence",
            (
                "not-in-flight-write-power-loss-kernel-crash-clean-machine-"
                "signed-distribution-device-network-or-production-evidence"
            ),
        ],
        "releaseId": release_id,
        "resultBytesEqual": True,
        "runCount": 2,
        "runs": [
            {
                "ordinal": ordinal,
                **identity,
                "status": "passed",
            }
            for ordinal in (1, 2)
        ],
        "schemaVersion": REPEATABILITY_SCHEMA_VERSION,
        "scope": REPEATABILITY_SCOPE,
        "status": "passed",
    }
    receipt_payload = engine.canonical_json_bytes(receipt)
    upgrade.require_publishable_result(
        result_path,
        run_bytes[0],
        label="canonical abrupt-process result",
    )
    upgrade.require_publishable_result(
        repeatability_result_path,
        receipt_payload,
        label="abrupt-process repeatability receipt",
    )
    upgrade.publish_result_pair(
        result_path,
        run_bytes[0],
        repeatability_result_path,
        receipt_payload,
    )
    return receipt


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=default_archive_dir(),
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=default_result_path(),
    )
    parser.add_argument(
        "--repeatability-result",
        type=Path,
        default=default_repeatability_result_path(),
    )
    parser.add_argument(
        "--single-run",
        action="store_true",
        help="run once without publishing a repeatability receipt",
    )
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "readiness timeout",
            0.1,
            60.0,
        ),
        default=20.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "observation window",
            engine.MINIMUM_OBSERVATION_SECONDS,
            30.0,
        ),
        default=engine.MINIMUM_OBSERVATION_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "termination timeout",
            0.1,
            30.0,
        ),
        default=10.0,
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.single_run:
            execute(
                archive_dir=arguments.archive_dir,
                result_path=arguments.result,
                readiness_timeout_seconds=arguments.readiness_timeout_seconds,
                observation_seconds=arguments.observation_seconds,
                termination_timeout_seconds=arguments.termination_timeout_seconds,
            )
            summary = "one persisted-state abrupt-process run completed"
        else:
            receipt = execute_repeatability(
                archive_dir=arguments.archive_dir,
                result_path=arguments.result,
                repeatability_result_path=arguments.repeatability_result,
                readiness_timeout_seconds=arguments.readiness_timeout_seconds,
                observation_seconds=arguments.observation_seconds,
                termination_timeout_seconds=arguments.termination_timeout_seconds,
            )
            summary = (
                f"{receipt['runCount']} complete runs produced "
                "byte-identical results"
            )
    except KeyboardInterrupt:
        print(
            "Local DMG abrupt-process state-recovery smoke interrupted.",
            file=sys.stderr,
        )
        return 130
    except (
        LocalDMGSmokeError,
        engine.LifecycleSmokeError,
        OSError,
        plistlib.InvalidFileException,
        sqlite3.Error,
        subprocess.SubprocessError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        print(
            f"Local DMG abrupt-process state-recovery smoke failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "Local DMG abrupt-process state-recovery smoke passed: "
        + summary
        + "."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
