#!/usr/bin/env python3
"""Exercise retained Runtime-chat state across same-DMG reinstall."""

from __future__ import annotations

import argparse
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import sys
from typing import Sequence
import zipfile

if __package__:
    from script import run_macos_clean_home_installed_state_recovery_smoke as clean
    from script import run_macos_local_dmg_uninstall_reinstall_smoke as same_dmg
else:
    import run_macos_clean_home_installed_state_recovery_smoke as clean
    import run_macos_local_dmg_uninstall_reinstall_smoke as same_dmg


base = same_dmg.base
dmg = same_dmg.dmg
engine = same_dmg.engine
installed = same_dmg.installed
recovery = same_dmg.recovery
uninstall = same_dmg.uninstall
upgrade = same_dmg.upgrade
LocalDMGSmokeError = same_dmg.LocalDMGSmokeError
ROOT = same_dmg.ROOT
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
    "state-recovery-v1"
)
LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "same-created-dmg-image-remount-only",
    "fixed-runtime-chat-legacy-canary-only",
    "legacy-fixture-removed-by-harness-before-reinstall-readback",
    "application-support-retained-no-automatic-data-cleanup",
    "post-archive-harness-not-build-input-member",
    "not-finder-system-applications-quarantine-or-gatekeeper-evidence",
    "not-signed-notarized-stapled-or-distribution-evidence",
    (
        "not-clean-machine-upgrade-rollback-device-provider-network-ui-"
        "accessibility-production-or-security-evidence"
    ),
)
LOWERCASE_HEX = frozenset("0123456789abcdef")


def current_release() -> recovery.ReleaseVersion:
    return same_dmg.current_release()


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return same_dmg.release_id_for(version)


def default_archive_dir() -> Path:
    return same_dmg.default_archive_dir()


def default_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-local-dmg-uninstall-reinstall-"
            "state-recovery-v1.json"
        )
    )


def _expected_canary_record() -> dict[str, object]:
    return {
        "eventID": recovery.CANARY_EVENT_ID,
        "eventJsonSha256": recovery.CANARY_EVENT_JSON_SHA256,
        "eventJsonSize": len(recovery.CANARY_EVENT_JSON),
        "legacyJsonlSha256": recovery.CANARY_LEGACY_SHA256,
        "legacyJsonlSize": len(recovery.CANARY_LEGACY_BYTES),
        "model": recovery.CANARY_MODEL,
        "requestID": recovery.CANARY_REQUEST_ID,
        "sessionID": recovery.CANARY_SESSION_ID,
    }


def _expected_sqlite_record() -> dict[str, object]:
    return {
        "eventJsonSha256": recovery.CANARY_EVENT_JSON_SHA256,
        "eventJsonSize": len(recovery.CANARY_EVENT_JSON),
        "integrityCheck": "ok",
        "totalEventCount": 1,
    }


def _validate_observation(
    value: dict[str, object],
    *,
    mode: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "mode",
        "sha256",
        "size",
        "status",
    }:
        raise LocalDMGSmokeError(
            "state-recovery observation shape is invalid"
        )
    sha256 = value["sha256"]
    size = value["size"]
    expected = recovery.expected_observation_line(mode)
    if (
        value["mode"] != mode
        or value["status"] != "passed"
        or type(sha256) is not str
        or sha256 != hashlib.sha256(expected).hexdigest()
        or type(size) is not int
        or size != len(expected)
    ):
        raise LocalDMGSmokeError(
            "state-recovery observation identity is invalid"
        )
    return dict(value)


def _validate_launch_runs(
    runs: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    if type(runs) not in (tuple, list) or len(runs) != 2:
        raise LocalDMGSmokeError(
            "state-recovery launch inventory is invalid"
        )
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
    validated: list[dict[str, object]] = []
    for expected_ordinal, run in enumerate(runs, start=1):
        if type(run) is not dict or set(run) != required:
            raise LocalDMGSmokeError(
                "state-recovery launch record shape is invalid"
            )
        observation_seconds = run["minimumObservationSeconds"]
        if (
            type(run["activationPolicy"]) is not int
            or run["activationPolicy"] != 0
            or type(observation_seconds) not in (int, float)
            or not math.isfinite(observation_seconds)
            or not (
                engine.MINIMUM_OBSERVATION_SECONDS
                <= observation_seconds
                <= 30.0
            )
            or type(run["ordinal"]) is not int
            or run["ordinal"] != expected_ordinal
            or any(
                run[key] is not True
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
                "state-recovery launch record is invalid"
            )
        validated.append(dict(run))
    return validated


def _validate_app_tree(
    app_tree: installed.AppTreeEvidence,
) -> dict[str, object]:
    if not isinstance(app_tree, installed.AppTreeEvidence):
        raise LocalDMGSmokeError("state-recovery app tree is invalid")
    record = app_tree.record()
    if (
        type(record["digestAlgorithm"]) is not str
        or not record["digestAlgorithm"]
        or type(record["regularFileCount"]) is not int
        or record["regularFileCount"] <= 0
        or type(record["sha256"]) is not str
        or len(record["sha256"]) != 64
        or any(
            character not in LOWERCASE_HEX
            for character in record["sha256"]
        )
        or type(record["totalRegularFileBytes"]) is not int
        or record["totalRegularFileBytes"] <= 0
    ):
        raise LocalDMGSmokeError(
            "state-recovery app tree identity is invalid"
        )
    return record


def _validate_auxiliary_sqlite(
    value: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    expected = [
        {
            "filename": filename,
            "integrityCheck": "ok",
        }
        for filename in clean.AUXILIARY_SQLITE_FILES
    ]
    if type(value) not in (tuple, list) or list(value) != expected:
        raise LocalDMGSmokeError(
            "state-recovery auxiliary SQLite evidence is invalid"
        )
    return expected


def require_recovery_state(
    *,
    label: str,
    application_support: Path,
    identity_file: Path,
    expected_sqlite: recovery.SQLiteCanaryEvidence,
    expected_auxiliary: Sequence[dict[str, object]],
    expected_files: dict[str, installed.FileIdentity],
    legacy_must_be_absent: bool,
) -> None:
    legacy_path = application_support / recovery.LEGACY_FILENAME
    observed_sqlite = recovery.sqlite_canary_evidence(
        application_support / recovery.DATABASE_FILENAME
    )
    observed_auxiliary = clean.auxiliary_sqlite_evidence(
        application_support
    )
    observed_files = installed.state_file_records(
        application_support,
        identity_file,
    )
    if (
        observed_sqlite != expected_sqlite
        or tuple(observed_auxiliary) != tuple(expected_auxiliary)
        or observed_files != expected_files
    ):
        raise LocalDMGSmokeError(
            f"isolated recovery state changed {label}: "
            f"{same_dmg.changed_state_paths(expected_files, observed_files)!r}"
        )
    if legacy_must_be_absent and (
        legacy_path.exists() or legacy_path.is_symlink()
    ):
        raise LocalDMGSmokeError(
            f"legacy fixture reappeared {label}"
        )


def require_preserved_legacy(path: Path) -> None:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.read_bytes() != recovery.CANARY_LEGACY_BYTES
        or recovery.sha256_file(path) != recovery.CANARY_LEGACY_SHA256
    ):
        raise LocalDMGSmokeError(
            "preserved legacy fixture changed during reinstall"
        )


def build_result(
    *,
    release: engine.ReleaseInputs,
    release_id: str,
    app_tree: installed.AppTreeEvidence,
    runs: Sequence[dict[str, object]],
    migration_observation: dict[str, object],
    sqlite_readback_observation: dict[str, object],
    migration_sqlite: recovery.SQLiteCanaryEvidence,
    sqlite_readback_sqlite: recovery.SQLiteCanaryEvidence,
    auxiliary_sqlite: Sequence[dict[str, object]],
    runtime_identity_present: bool,
    snapshot_files: dict[str, dict[str, object]],
) -> dict[str, object]:
    if runtime_identity_present is not True:
        raise LocalDMGSmokeError(
            "state-recovery runtime identity was not created"
        )
    expected_sqlite = _expected_sqlite_record()
    if (
        not isinstance(
            migration_sqlite,
            recovery.SQLiteCanaryEvidence,
        )
        or not isinstance(
            sqlite_readback_sqlite,
            recovery.SQLiteCanaryEvidence,
        )
        or type(migration_sqlite.event_json_size) is not int
        or type(migration_sqlite.total_event_count) is not int
        or type(sqlite_readback_sqlite.event_json_size) is not int
        or type(sqlite_readback_sqlite.total_event_count) is not int
        or migration_sqlite.record() != expected_sqlite
        or sqlite_readback_sqlite.record() != expected_sqlite
        or migration_sqlite != sqlite_readback_sqlite
    ):
        raise LocalDMGSmokeError(
            "state-recovery Runtime-chat canary evidence is invalid"
        )
    validated_files = dmg.validated_snapshot_files(
        release=release,
        release_id=release_id,
        snapshot_files=snapshot_files,
    )
    tree_record = _validate_app_tree(app_tree)
    validated_runs = _validate_launch_runs(runs)
    migration_record = _validate_observation(
        migration_observation,
        mode=recovery.MIGRATION_MODE,
    )
    readback_record = _validate_observation(
        sqlite_readback_observation,
        mode=recovery.SQLITE_READBACK_MODE,
    )
    auxiliary_records = _validate_auxiliary_sqlite(auxiliary_sqlite)
    return {
        "archiveReadback": {
            "currentSourceCompared": False,
            "mode": dmg.ARCHIVE_READBACK_MODE,
            "readbackAndExerciseSameSnapshot": True,
            "snapshotFiles": validated_files,
            "snapshotFilesUnchangedAfterExercise": True,
            "status": "passed",
        },
        "canary": _expected_canary_record(),
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
            "cleanHomeConfigured": True,
            "preexistingBundleApplicationsPreserved": True,
            "runtimeIdentityFileOverrideConfigured": True,
            "temporaryCFUserHomeConfigured": True,
        },
        "launchServices": {
            "commandPolicy": clean.COMMAND_POLICY,
            "distinctProcessIdentifiers": True,
            "exactInstalledBundlePerCycle": True,
            "noExactTemporaryAppRemaining": True,
            "runs": validated_runs,
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
            (
                "installedStateBytesAndModesUnchangedAcrossRemovalAndReinstall"
            ): True,
            "legacyAbsentBeforeReinstallReadback": True,
            "legacyFixturePreservedUnchanged": True,
            "legacyRemovedByHarnessBeforeReinstall": True,
            "migrationObservation": migration_record,
            "migrationSQLite": migration_sqlite.record(),
            "runtimeIdentityFilePresent": True,
            "sqliteCanaryUnchangedAcrossRemovalAndReinstall": True,
            "sqliteReadbackObservation": readback_record,
            "sqliteReadbackSQLite": sqlite_readback_sqlite.record(),
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


def publish_result(path: Path, result: dict[str, object]) -> None:
    same_dmg.publish_result(path, result)


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

    with same_dmg.isolated_dmg_root(
        termination_timeout_seconds=termination_timeout_seconds,
    ) as temporary_root:
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
                "staged local DMG recovery app differs from release"
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
                "initial local DMG recovery install differs from release"
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
                "clean-HOME recovery state existed before fixture creation"
            )
        recovery.write_legacy_fixture(legacy_path)

        migration_environment = clean.recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.MIGRATION_MODE,
        )
        first_stdout = logs / "run-1-stdout.log"
        first_stderr = logs / "run-1-stderr.log"
        first_pid, first_run = clean.run_recovery_launch_services_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=migration_environment,
            stdout_path=first_stdout,
            stderr_path=first_stderr,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        clean.validate_captured_log(
            first_stderr,
            label="migration stderr",
        )
        migration_observation = recovery.verify_observation_log(
            first_stdout,
            recovery.MIGRATION_MODE,
        )
        migration_sqlite = recovery.sqlite_canary_evidence(database_path)
        migration_auxiliary = clean.auxiliary_sqlite_evidence(
            application_support
        )
        migration_tree = installed.app_tree_evidence(
            installed_app,
            release,
        )
        if migration_tree != initial_tree:
            raise LocalDMGSmokeError(
                "installed app tree changed during migration"
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
        require_recovery_state(
            label="during initial removal",
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
        require_preserved_legacy(preserved_legacy)
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
                "harness legacy removal changed unexpected recovery state"
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
                "same-image recovery reinstall differs from initial app tree"
            )
        require_recovery_state(
            label="during same-image reinstall copy",
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
        second_stdout = logs / "run-2-stdout.log"
        second_stderr = logs / "run-2-stderr.log"
        second_pid, second_run = clean.run_recovery_launch_services_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=readback_environment,
            stdout_path=second_stdout,
            stderr_path=second_stderr,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if second_pid == first_pid:
            raise LocalDMGSmokeError(
                "same-image recovery reinstall reused the initial process"
            )
        clean.validate_captured_log(
            second_stderr,
            label="SQLite-readback stderr",
        )
        sqlite_readback_observation = recovery.verify_observation_log(
            second_stdout,
            recovery.SQLITE_READBACK_MODE,
        )
        sqlite_readback_sqlite = recovery.sqlite_canary_evidence(
            database_path
        )
        readback_auxiliary = clean.auxiliary_sqlite_evidence(
            application_support
        )
        if readback_auxiliary != migration_auxiliary:
            raise LocalDMGSmokeError(
                "auxiliary SQLite evidence changed after reinstall"
            )
        require_recovery_state(
            label="after same-image reinstall readback",
            application_support=application_support,
            identity_file=identity_file,
            expected_sqlite=migration_sqlite,
            expected_auxiliary=migration_auxiliary,
            expected_files=state_without_legacy,
            legacy_must_be_absent=True,
        )
        if sqlite_readback_sqlite != migration_sqlite:
            raise LocalDMGSmokeError(
                "Runtime-chat canary changed after same-image reinstall"
            )
        if (
            installed.app_tree_evidence(installed_app, release)
            != reinstalled_tree
        ):
            raise LocalDMGSmokeError(
                "reinstalled app tree changed during SQLite readback"
            )

        uninstall.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=release,
            expected_tree=reinstalled_tree,
        )
        require_recovery_state(
            label="during final removal",
            application_support=application_support,
            identity_file=identity_file,
            expected_sqlite=migration_sqlite,
            expected_auxiliary=migration_auxiliary,
            expected_files=state_without_legacy,
            legacy_must_be_absent=True,
        )
        require_preserved_legacy(preserved_legacy)

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
            app_tree=initial_tree,
            runs=(first_run, second_run),
            migration_observation=migration_observation,
            sqlite_readback_observation=sqlite_readback_observation,
            migration_sqlite=migration_sqlite,
            sqlite_readback_sqlite=sqlite_readback_sqlite,
            auxiliary_sqlite=migration_auxiliary,
            runtime_identity_present=identity_file.is_file(),
            snapshot_files=snapshot_files,
        )

    publish_result(result_path, result)
    return result


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
        "--readiness-timeout-seconds",
        type=float,
        default=15.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=float,
        default=10.0,
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        execute(
            archive_dir=arguments.archive_dir,
            result_path=arguments.result,
            readiness_timeout_seconds=arguments.readiness_timeout_seconds,
            observation_seconds=arguments.observation_seconds,
            termination_timeout_seconds=arguments.termination_timeout_seconds,
        )
    except KeyboardInterrupt:
        print(
            "Local DMG uninstall/reinstall state-recovery smoke interrupted.",
            file=sys.stderr,
        )
        return 130
    except (
        LocalDMGSmokeError,
        engine.LifecycleSmokeError,
        OSError,
        sqlite3.Error,
        ValueError,
        zipfile.BadZipFile,
    ):
        print(
            "Local DMG uninstall/reinstall state-recovery smoke failed.",
            file=sys.stderr,
        )
        return 1
    print(
        "Local DMG uninstall/reinstall state-recovery smoke passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
