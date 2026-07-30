#!/usr/bin/env python3
"""Exercise installed Build 14 legacy-to-SQLite recovery under a clean HOME."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable
from urllib.parse import quote
import zipfile

if __package__:
    from script import run_macos_clean_home_installed_app_smoke as installed
    from script import run_macos_packaged_app_state_recovery_smoke as recovery
else:
    import run_macos_clean_home_installed_app_smoke as installed
    import run_macos_packaged_app_state_recovery_smoke as recovery


engine = installed.engine
ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-clean-home-launchservices-state-recovery-v1"
)
COMMAND_POLICY = (
    "open-new-fresh-background-exact-app-path-captured-recovery-v1"
)
MAXIMUM_CAPTURED_LOG_BYTES = 65_536
FORWARDED_ENVIRONMENT_KEYS = (
    "AETHERLINK_RUNTIME_IDENTITY_FILE",
    "CFFIXED_USER_HOME",
    "CFPREFERENCES_AVOID_DAEMON",
    "HOME",
    "NSUnbufferedIO",
    "OS_ACTIVITY_MODE",
    "TMPDIR",
)
AUXILIARY_SQLITE_FILES = tuple(
    filename
    for filename in installed.EXPECTED_SQLITE_FILES
    if filename != recovery.DATABASE_FILENAME
)


def current_release() -> recovery.ReleaseVersion:
    return recovery.current_release()


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return recovery.release_id_for(version)


def default_archive_dir() -> Path:
    return recovery.default_archive_dir()


def default_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-clean-home-state-recovery-v1.json"
        )
    )


def recovery_launch_environment(
    base: dict[str, str],
    *,
    home: Path,
    temporary: Path,
    identity_file: Path,
    mode: str,
) -> dict[str, str]:
    if mode not in (
        recovery.MIGRATION_MODE,
        recovery.SQLITE_READBACK_MODE,
    ):
        raise engine.LifecycleSmokeError(
            f"unsupported installed state-recovery mode: {mode!r}"
        )
    environment = installed.isolated_launch_environment(
        base,
        home=home,
        temporary=temporary,
        identity_file=identity_file,
    )
    environment[recovery.QA_MODE_ENVIRONMENT_KEY] = mode
    return environment


def prepare_captured_log(path: Path) -> None:
    if not path.is_absolute() or "\x00" in str(path):
        raise engine.LifecycleSmokeError(
            "captured LaunchServices log path must be absolute"
        )
    if path.exists() or path.is_symlink():
        raise engine.LifecycleSmokeError(
            f"captured LaunchServices log already exists: {path}"
        )
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise engine.LifecycleSmokeError(
            "captured LaunchServices log parent is not a real directory"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    status = path.lstat()
    if (
        not stat.S_ISREG(status.st_mode)
        or stat.S_IMODE(status.st_mode) != 0o600
        or status.st_size != 0
    ):
        raise engine.LifecycleSmokeError(
            "captured LaunchServices log was not initialized exactly"
        )


def recovery_launch_services_command(
    app_path: Path,
    environment: dict[str, str],
    *,
    stdout_path: Path,
    stderr_path: Path,
) -> list[str]:
    app_text = str(app_path)
    stdout_text = str(stdout_path)
    stderr_text = str(stderr_path)
    mode = environment.get(recovery.QA_MODE_ENVIRONMENT_KEY)
    if (
        not app_path.is_absolute()
        or app_path.suffix != ".app"
        or "\x00" in app_text
    ):
        raise engine.LifecycleSmokeError(
            "LaunchServices requires an absolute application-bundle path"
        )
    if (
        mode
        not in (
            recovery.MIGRATION_MODE,
            recovery.SQLITE_READBACK_MODE,
        )
        or type(mode) is not str
    ):
        raise engine.LifecycleSmokeError(
            "LaunchServices recovery mode is missing or invalid"
        )
    if (
        not stdout_path.is_absolute()
        or not stderr_path.is_absolute()
        or stdout_path == stderr_path
        or "\x00" in stdout_text
        or "\x00" in stderr_text
    ):
        raise engine.LifecycleSmokeError(
            "LaunchServices capture paths must be distinct absolute paths"
        )

    command = [
        str(installed.OPEN),
        "-n",
        "-F",
        "-g",
        "--stdout",
        stdout_text,
        "--stderr",
        stderr_text,
    ]
    for key in FORWARDED_ENVIRONMENT_KEYS:
        value = environment.get(key)
        if value is None or "\x00" in value:
            raise engine.LifecycleSmokeError(
                f"missing or invalid LaunchServices environment value {key}"
            )
        command.extend(("--env", f"{key}={value}"))
    command.extend(
        (
            "--env",
            f"{recovery.QA_MODE_ENVIRONMENT_KEY}={mode}",
            app_text,
        )
    )
    return command


def validate_captured_log(
    path: Path,
    *,
    label: str,
) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise engine.LifecycleSmokeError(
            f"{label} is missing or not a regular file"
        )
    status = path.lstat()
    if stat.S_IMODE(status.st_mode) != 0o600:
        raise engine.LifecycleSmokeError(
            f"{label} mode differs from 0600"
        )
    payload = path.read_bytes()
    if len(payload) > MAXIMUM_CAPTURED_LOG_BYTES:
        raise engine.LifecycleSmokeError(
            f"{label} exceeded the captured-log limit"
        )
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }


def run_recovery_launch_services_cycle(
    *,
    ordinal: int,
    app_path: Path,
    environment: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
    command_runner: Callable[
        ...,
        subprocess.CompletedProcess[str],
    ] = engine.run_checked,
    lister: Callable[
        [],
        tuple[installed.RunningApplication, ...],
    ] = installed.list_bundle_applications,
    query: Callable[
        [int],
        engine.ApplicationStatus | None,
    ] = engine.query_application,
    requester: Callable[..., bool] = (
        engine.request_application_termination
    ),
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[int, dict[str, object]]:
    executable = app_path / installed.EXECUTABLE_RELATIVE_PATH
    before = lister()
    preexisting_pids = {application.pid for application in before}
    if any(
        installed.application_matches_executable(
            application,
            executable,
        )
        for application in before
    ):
        raise engine.LifecycleSmokeError(
            "the isolated installed recovery app path is already running"
        )
    if (
        not installed.OPEN.is_file()
        or not os.access(installed.OPEN, os.X_OK)
    ):
        raise engine.LifecycleSmokeError("open is unavailable")

    prepare_captured_log(stdout_path)
    prepare_captured_log(stderr_path)
    launched: installed.RunningApplication | None = None
    try:
        command_runner(
            recovery_launch_services_command(
                app_path,
                environment,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            ),
            cwd=app_path.parent,
            environment=environment,
        )
        launched = installed.wait_for_new_application(
            executable=executable,
            preexisting_pids=preexisting_pids,
            timeout_seconds=readiness_timeout_seconds,
            lister=lister,
            monotonic=monotonic,
            sleeper=sleeper,
        )
        observation_deadline = monotonic() + observation_seconds
        while monotonic() < observation_deadline:
            status = installed.assert_query_identity(
                query(launched.pid),
                executable,
            )
            if not status.finished_launching:
                raise engine.LifecycleSmokeError(
                    "installed recovery app lost finished-launching state"
                )
            remaining = max(0.0, observation_deadline - monotonic())
            sleeper(min(0.1, remaining))

        installed.assert_query_identity(
            query(launched.pid),
            executable,
        )
        termination_accepted = requester(
            launched.pid,
            executable,
            force=False,
        )
        if not termination_accepted:
            raise engine.LifecycleSmokeError(
                "installed recovery app rejected exact-PID termination"
            )
        if not installed.wait_until_application_gone(
            launched.pid,
            timeout_seconds=termination_timeout_seconds,
            query=query,
        ):
            raise engine.LifecycleSmokeError(
                "installed recovery app did not terminate on time"
            )
        return (
            launched.pid,
            {
                "activationPolicy": launched.activation_policy,
                "executablePathMatched": True,
                "finishedLaunching": launched.finished_launching,
                "minimumObservationSeconds": observation_seconds,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": True,
            },
        )
    finally:
        remaining_applications = [
            application
            for application in lister()
            if application.pid not in preexisting_pids
            and installed.application_matches_executable(
                application,
                executable,
            )
        ]
        for application in remaining_applications:
            status = query(application.pid)
            if status is None:
                continue
            installed.assert_query_identity(status, executable)
            accepted = requester(
                application.pid,
                executable,
                force=True,
            )
            if not accepted or not installed.wait_until_application_gone(
                application.pid,
                timeout_seconds=termination_timeout_seconds,
                query=query,
            ):
                raise engine.LifecycleSmokeError(
                    "could not clean up the exact installed recovery app"
                )


def auxiliary_sqlite_evidence(
    application_support: Path,
) -> tuple[dict[str, object], ...]:
    evidence: list[dict[str, object]] = []
    for filename in AUXILIARY_SQLITE_FILES:
        database_path = application_support / filename
        if database_path.is_symlink() or not database_path.is_file():
            raise engine.LifecycleSmokeError(
                f"installed recovery app did not initialize {filename}"
            )
        database_uri = (
            "file:"
            + quote(str(database_path.resolve()), safe="/")
            + "?mode=ro"
        )
        try:
            connection = sqlite3.connect(
                database_uri,
                uri=True,
                timeout=5,
            )
            try:
                connection.execute("PRAGMA query_only = ON")
                integrity_rows = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise engine.LifecycleSmokeError(
                f"SQLite readback failed for {filename}: {error}"
            ) from error
        if integrity_rows != [("ok",)]:
            raise engine.LifecycleSmokeError(
                f"SQLite integrity_check failed for {filename}"
            )
        evidence.append(
            {
                "filename": filename,
                "integrityCheck": "ok",
            }
        )
    return tuple(evidence)


def changed_state_paths(
    first: dict[str, installed.FileIdentity],
    second: dict[str, installed.FileIdentity],
) -> list[str]:
    return sorted(
        set(first)
        ^ set(second)
        | {
            path
            for path in set(first) & set(second)
            if first[path] != second[path]
        }
    )


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
    version = current_release()
    release_id = release_id_for(version)
    release = recovery.load_release_inputs(
        archive_dir,
        version=version,
    )
    preexisting_applications = installed.list_bundle_applications()

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-clean-home-state-recovery-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        extracted_app = engine.extract_packaged_app(
            release,
            temporary_root / "extracted-app",
        )
        recovery.verify_packaged_app(
            extracted_app,
            release,
            version=version,
        )
        extracted_tree = installed.app_tree_evidence(
            extracted_app,
            release,
        )

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        logs = temporary_root / "logs"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
            logs,
        ):
            path.mkdir(mode=0o700)
        installed_app = (
            isolated_home / "Applications" / installed.APP_RELATIVE_PATH
        )
        installed.install_app_with_ditto(extracted_app, installed_app)
        app_metadata = recovery.verify_packaged_app(
            installed_app,
            release,
            version=version,
        )
        installed_tree = installed.app_tree_evidence(
            installed_app,
            release,
        )
        if installed_tree != extracted_tree:
            raise engine.LifecycleSmokeError(
                "installed recovery app differs from the extracted app"
            )

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
            raise engine.LifecycleSmokeError(
                "clean-HOME recovery state existed before fixture creation"
            )
        recovery.write_legacy_fixture(legacy_path)

        migration_environment = recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.MIGRATION_MODE,
        )
        first_stdout = logs / "run-1-stdout.log"
        first_stderr = logs / "run-1-stderr.log"
        first_pid, first_run = run_recovery_launch_services_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=migration_environment,
            stdout_path=first_stdout,
            stderr_path=first_stderr,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        first_stderr_evidence = validate_captured_log(
            first_stderr,
            label="migration stderr",
        )
        try:
            first_observation = recovery.verify_observation_log(
                first_stdout,
                recovery.MIGRATION_MODE,
            )
        except engine.LifecycleSmokeError as error:
            raise engine.LifecycleSmokeError(
                f"{error}; migration stderr="
                f"{first_stderr_evidence!r}"
            ) from error
        first_sqlite = recovery.sqlite_canary_evidence(database_path)
        first_auxiliary = auxiliary_sqlite_evidence(
            application_support,
        )
        first_tree = installed.app_tree_evidence(
            installed_app,
            release,
        )

        preserved_legacy = recovery.remove_legacy_before_readback(
            legacy_path,
            temporary_root / "preserved-legacy",
        )
        first_state = installed.state_file_records(
            application_support,
            identity_file,
        )

        readback_environment = recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.SQLITE_READBACK_MODE,
        )
        second_stdout = logs / "run-2-stdout.log"
        second_stderr = logs / "run-2-stderr.log"
        second_pid, second_run = run_recovery_launch_services_cycle(
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
            raise engine.LifecycleSmokeError(
                "installed recovery relaunch reused the prior PID"
            )
        if legacy_path.exists() or legacy_path.is_symlink():
            raise engine.LifecycleSmokeError(
                "legacy fixture reappeared during SQLite-only readback"
            )
        second_stderr_evidence = validate_captured_log(
            second_stderr,
            label="SQLite-readback stderr",
        )
        try:
            second_observation = recovery.verify_observation_log(
                second_stdout,
                recovery.SQLITE_READBACK_MODE,
            )
        except engine.LifecycleSmokeError as error:
            raise engine.LifecycleSmokeError(
                f"{error}; SQLite-readback stderr="
                f"{second_stderr_evidence!r}"
            ) from error
        second_sqlite = recovery.sqlite_canary_evidence(database_path)
        second_auxiliary = auxiliary_sqlite_evidence(
            application_support,
        )
        second_tree = installed.app_tree_evidence(
            installed_app,
            release,
        )
        second_state = installed.state_file_records(
            application_support,
            identity_file,
        )

        if first_sqlite != second_sqlite:
            raise engine.LifecycleSmokeError(
                "installed runtime-chat canary changed across relaunch"
            )
        if first_auxiliary != second_auxiliary:
            raise engine.LifecycleSmokeError(
                "installed auxiliary SQLite evidence changed"
            )
        if first_state != second_state:
            raise engine.LifecycleSmokeError(
                "installed recovery state changed across relaunch: "
                f"{changed_state_paths(first_state, second_state)!r}"
            )
        if first_tree != installed_tree or second_tree != installed_tree:
            raise engine.LifecycleSmokeError(
                "installed app bytes or modes changed during recovery"
            )
        if (
            preserved_legacy.read_bytes()
            != recovery.CANARY_LEGACY_BYTES
            or recovery.sha256_file(preserved_legacy)
            != recovery.CANARY_LEGACY_SHA256
        ):
            raise engine.LifecycleSmokeError(
                "preserved legacy fixture changed during readback"
            )

        installed.assert_preexisting_applications_preserved(
            preexisting_applications
        )
        result = {
            "app": app_metadata,
            "canary": {
                "eventID": recovery.CANARY_EVENT_ID,
                "eventJsonSha256": recovery.CANARY_EVENT_JSON_SHA256,
                "eventJsonSize": len(recovery.CANARY_EVENT_JSON),
                "legacyJsonlSha256": recovery.CANARY_LEGACY_SHA256,
                "legacyJsonlSize": len(recovery.CANARY_LEGACY_BYTES),
                "model": recovery.CANARY_MODEL,
                "requestID": recovery.CANARY_REQUEST_ID,
                "sessionID": recovery.CANARY_SESSION_ID,
            },
            "installation": {
                "codesignVerified": True,
                "copyTool": "ditto",
                "installedRelativePath": "Applications/AetherLink.app",
                "regularFileTreeMatchesReleaseManifest": True,
                "tree": installed_tree.record(),
            },
            "isolation": {
                "cleanHomeConfigured": True,
                "preexistingBundleApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "launchServices": {
                "commandPolicy": COMMAND_POLICY,
                "distinctProcessIdentifiers": True,
                "runs": [first_run, second_run],
            },
            "limitations": [
                "same-host-per-user-rehearsal-only",
                "not-a-clean-machine-account-or-dmg-installation",
                "not-ui-accessibility-or-live-provider-evidence",
                "not-physical-device-or-signed-distribution-evidence",
            ],
            "release": {
                "archiveSha256": release.archive_sha256,
                "manifestSha256": release.manifest_sha256,
                "releaseId": release_id,
            },
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "scope": RESULT_SCOPE,
            "stateRecovery": {
                "auxiliarySQLite": list(first_auxiliary),
                "installedStateBytesAndModesUnchangedAcrossRelaunch": True,
                "legacyAbsentBeforeSecondRun": True,
                "legacyFixturePreservedUnchanged": True,
                "migrationObservation": first_observation,
                "migrationSQLite": first_sqlite.record(),
                "runtimeIdentityFilePresent": identity_file.is_file(),
                "sqliteCanaryUnchangedAcrossRuns": True,
                "sqliteReadbackObservation": second_observation,
                "sqliteReadbackSQLite": second_sqlite.record(),
            },
            "status": "passed",
        }

    installed.publish_result(result_path, result)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
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
        type=lambda value: engine.bounded_float(
            value,
            "readiness timeout",
            0.1,
            60,
        ),
        default=20.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "observation window",
            engine.MINIMUM_OBSERVATION_SECONDS,
            30,
        ),
        default=engine.MINIMUM_OBSERVATION_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "termination timeout",
            0.1,
            30,
        ),
        default=10.0,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = execute(
            archive_dir=arguments.archive_dir,
            result_path=arguments.result,
            readiness_timeout_seconds=arguments.readiness_timeout_seconds,
            observation_seconds=arguments.observation_seconds,
            termination_timeout_seconds=arguments.termination_timeout_seconds,
        )
    except KeyboardInterrupt:
        print(
            "macOS clean-HOME installed state-recovery smoke interrupted.",
            file=sys.stderr,
        )
        return 130
    except (
        engine.LifecycleSmokeError,
        OSError,
        sqlite3.Error,
        zipfile.BadZipFile,
    ) as error:
        print(
            "macOS clean-HOME installed state-recovery smoke failed: "
            f"{error}",
            file=sys.stderr,
        )
        return 1

    print(
        "macOS clean-HOME installed state-recovery smoke passed: "
        f"{result['release']['releaseId']}; "
        "legacy migration and SQLite-only relaunch preserved."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
