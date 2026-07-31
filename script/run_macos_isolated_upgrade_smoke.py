#!/usr/bin/env python3
"""Exercise the latest two macOS release archives as an isolated upgrade."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
from typing import Callable, Iterator, Sequence
import zipfile

if __package__:
    from script import run_macos_clean_home_installed_app_smoke as installed
    from script import (
        run_macos_clean_home_installed_state_recovery_smoke
        as installed_recovery
    )
    from script import run_macos_isolated_uninstall_reinstall_smoke as removal
    from script import run_macos_packaged_app_state_recovery_smoke as recovery
    from script.check_release_version_ledger import (
        ReleaseVersion,
        load_release_version_ledger,
    )
else:
    import run_macos_clean_home_installed_app_smoke as installed
    import run_macos_clean_home_installed_state_recovery_smoke as installed_recovery
    import run_macos_isolated_uninstall_reinstall_smoke as removal
    import run_macos_packaged_app_state_recovery_smoke as recovery
    from check_release_version_ledger import (
        ReleaseVersion,
        load_release_version_ledger,
    )


engine = installed.engine
ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_VERSION = 2
RESULT_SCOPE = "same-host-per-user-isolated-build-to-build-upgrade-v2"
REPEATABILITY_SCHEMA_VERSION = 1
REPEATABILITY_SCOPE = (
    "same-host-per-user-isolated-build-to-build-upgrade-repeatability-v1"
)
PREVIOUS_READBACK_MODE = "historical"
CURRENT_READBACK_MODE = "archive-only-no-current-source"
REPLACEMENT_METHOD = "exact-path-remove-then-ditto"
ARCHIVE_MAXIMUM_BYTES = 512 * 1_024 * 1_024
MANIFEST_MAXIMUM_BYTES = 4 * 1_024 * 1_024
CHECKSUM_MAXIMUM_BYTES = 4 * 1_024


def release_pair() -> tuple[ReleaseVersion, ReleaseVersion]:
    entries = load_release_version_ledger()
    if len(entries) < 2:
        raise engine.LifecycleSmokeError(
            "release ledger must contain at least two entries for an upgrade"
        )
    previous, current = entries[-2:]
    validate_release_pair(previous, current)
    return previous, current


def validate_release_pair(
    previous: ReleaseVersion,
    current: ReleaseVersion,
) -> None:
    if (
        previous.build_number >= current.build_number
        or recovery.release_id_for(previous)
        == recovery.release_id_for(current)
    ):
        raise engine.LifecycleSmokeError(
            "upgrade releases must be distinct and strictly ordered"
        )


def default_archive_dir(version: ReleaseVersion) -> Path:
    return (
        ROOT
        / "dist/releases"
        / recovery.release_id_for(version)
    )


def default_result_path() -> Path:
    previous, current = release_pair()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{previous.build_number}-to-{current.build_number}-"
            "isolated-upgrade-v2.json"
        )
    )


def default_repeatability_result_path() -> Path:
    previous, current = release_pair()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{previous.build_number}-to-{current.build_number}-"
            "isolated-upgrade-repeatability-v1.json"
        )
    )


def verify_archive_readback(
    archive_dir: Path,
    *,
    historical: bool,
    runner: Callable[..., object] = engine.run_checked,
) -> None:
    mode = "--historical" if historical else "--no-current-source"
    runner(
        [
            sys.executable,
            "-B",
            str(engine.ARCHIVE_CHECKER),
            "--archive-dir",
            str(archive_dir.resolve()),
            mode,
        ],
        cwd=ROOT,
    )


def copy_stable_regular_file(
    source: Path,
    destination: Path,
    *,
    maximum_bytes: int,
) -> dict[str, object]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        source_descriptor = os.open(source, flags)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot open release input {source}: {error}"
        ) from error

    destination_descriptor: int | None = None
    try:
        before = os.fstat(source_descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > maximum_bytes
        ):
            raise engine.LifecycleSmokeError(
                f"release input has an invalid file type or size: {source}"
            )
        destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        destination_flags |= getattr(os, "O_CLOEXEC", 0)
        destination_flags |= getattr(os, "O_NOFOLLOW", 0)
        destination_descriptor = os.open(
            destination,
            destination_flags,
            0o600,
        )
        digest = hashlib.sha256()
        total = 0
        while True:
            payload = os.read(source_descriptor, 1024 * 1024)
            if not payload:
                break
            digest.update(payload)
            total += len(payload)
            if total > maximum_bytes:
                raise engine.LifecycleSmokeError(
                    f"release input exceeded its byte limit: {source}"
                )
            offset = 0
            while offset < len(payload):
                offset += os.write(
                    destination_descriptor,
                    payload[offset:],
                )
        os.fsync(destination_descriptor)
        after = os.fstat(source_descriptor)
        stable_fields = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if stable_fields != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or total != before.st_size:
            raise engine.LifecycleSmokeError(
                f"release input changed while being snapshotted: {source}"
            )
        destination_status = os.fstat(destination_descriptor)
        if (
            not stat.S_ISREG(destination_status.st_mode)
            or destination_status.st_size != total
        ):
            raise engine.LifecycleSmokeError(
                f"release snapshot differs in size: {destination}"
            )
        return {
            "sha256": digest.hexdigest(),
            "size": total,
        }
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if destination_descriptor is not None:
            os.close(destination_descriptor)
        os.close(source_descriptor)


def snapshot_archive_directory(
    archive_dir: Path,
    *,
    version: ReleaseVersion,
    destination_parent: Path,
) -> tuple[Path, dict[str, dict[str, object]]]:
    release_id = recovery.release_id_for(version)
    try:
        source_status = archive_dir.lstat()
        source_directory = archive_dir.resolve(strict=True)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot inspect release archive directory: {error}"
        ) from error
    if (
        stat.S_ISLNK(source_status.st_mode)
        or not stat.S_ISDIR(source_status.st_mode)
        or source_directory.name != release_id
    ):
        raise engine.LifecycleSmokeError(
            f"release archive directory must be a physical {release_id!r}"
        )

    expected_limits = {
        f"{release_id}.zip": ARCHIVE_MAXIMUM_BYTES,
        f"{release_id}.manifest.json": MANIFEST_MAXIMUM_BYTES,
        f"{release_id}.zip.sha256": CHECKSUM_MAXIMUM_BYTES,
    }
    try:
        actual_names = {
            path.name for path in source_directory.iterdir()
        }
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot enumerate release archive directory: {error}"
        ) from error
    if actual_names != set(expected_limits):
        raise engine.LifecycleSmokeError(
            "release archive sidecar set differs before snapshot: "
            f"{sorted(actual_names)!r}"
        )

    destination_parent.mkdir(mode=0o700, exist_ok=True)
    destination_parent_status = destination_parent.lstat()
    if (
        stat.S_ISLNK(destination_parent_status.st_mode)
        or not stat.S_ISDIR(destination_parent_status.st_mode)
    ):
        raise engine.LifecycleSmokeError(
            "release snapshot parent must be a physical directory"
        )
    snapshot_directory = destination_parent / release_id
    snapshot_directory.mkdir(mode=0o700)
    identities: dict[str, dict[str, object]] = {}
    for name in sorted(expected_limits):
        identities[name] = copy_stable_regular_file(
            source_directory / name,
            snapshot_directory / name,
            maximum_bytes=expected_limits[name],
        )
    return snapshot_directory, identities


def require_unchanged_archive_snapshot(
    snapshot_directory: Path,
    expected: dict[str, dict[str, object]],
) -> None:
    try:
        actual_names = {
            path.name for path in snapshot_directory.iterdir()
        }
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot enumerate release snapshot directory: {error}"
        ) from error
    if actual_names != set(expected):
        raise engine.LifecycleSmokeError(
            "release snapshot sidecar set changed after exercise: "
            f"{sorted(actual_names)!r}"
        )
    for name, expected_identity in expected.items():
        identity = installed.stable_regular_file_identity(
            snapshot_directory / name
        )
        actual_identity = {
            "sha256": identity.sha256,
            "size": identity.size,
        }
        if not exact_results_equal(actual_identity, expected_identity):
            raise engine.LifecycleSmokeError(
                "release snapshot bytes changed after exercise: "
                f"{name}"
            )


def cleanup_exact_temporary_applications(
    temporary_root: Path,
    *,
    termination_timeout_seconds: float,
    lister: Callable[
        [], tuple[installed.RunningApplication, ...]
    ]
    | None = None,
    query: Callable[[int], engine.ApplicationStatus | None] | None = None,
    requester: Callable[..., bool] | None = None,
) -> None:
    resolved_lister = lister or installed.list_bundle_applications
    resolved_query = query or engine.query_application
    resolved_requester = requester or engine.request_application_termination
    executable = (
        temporary_root
        / "home/Applications"
        / installed.APP_RELATIVE_PATH
        / installed.EXECUTABLE_RELATIVE_PATH
    )
    matching = [
        application
        for application in resolved_lister()
        if installed.application_matches_executable(
            application,
            executable,
        )
    ]
    for application in matching:
        status = resolved_query(application.pid)
        if status is None:
            continue
        installed.assert_query_identity(status, executable)
        accepted = resolved_requester(
            application.pid,
            executable,
            force=True,
        )
        if not accepted or not installed.wait_until_application_gone(
            application.pid,
            timeout_seconds=termination_timeout_seconds,
            query=resolved_query,
        ):
            raise engine.LifecycleSmokeError(
                "could not terminate the exact temporary upgrade app"
            )
    remaining = [
        application
        for application in resolved_lister()
        if installed.application_matches_executable(
            application,
            executable,
        )
    ]
    if remaining:
        raise engine.LifecycleSmokeError(
            "exact temporary upgrade app remained after cleanup"
        )


@contextmanager
def isolated_upgrade_root(
    *,
    termination_timeout_seconds: float,
    lister: Callable[
        [], tuple[installed.RunningApplication, ...]
    ]
    | None = None,
    query: Callable[[int], engine.ApplicationStatus | None] | None = None,
    requester: Callable[..., bool] | None = None,
) -> Iterator[Path]:
    temporary_root = Path(
        tempfile.mkdtemp(prefix="aetherlink-macos-isolated-upgrade-")
    ).resolve()
    try:
        yield temporary_root
    finally:
        try:
            cleanup_exact_temporary_applications(
                temporary_root,
                termination_timeout_seconds=termination_timeout_seconds,
                lister=lister,
                query=query,
                requester=requester,
            )
        except BaseException as error:
            raise engine.LifecycleSmokeError(
                "temporary upgrade app cleanup failed; retained diagnostic "
                f"root at {temporary_root}"
            ) from error
        shutil.rmtree(temporary_root)


def changed_state_paths(
    before: dict[str, installed.FileIdentity],
    after: dict[str, installed.FileIdentity],
) -> list[str]:
    return installed_recovery.changed_state_paths(before, after)


def require_unchanged_state(
    before: dict[str, installed.FileIdentity],
    after: dict[str, installed.FileIdentity],
    *,
    phase: str,
) -> None:
    if before != after:
        raise engine.LifecycleSmokeError(
            f"isolated state changed during {phase}: "
            f"{changed_state_paths(before, after)!r}"
        )


def require_output_paths_outside_archives(
    output_paths: Sequence[Path],
    archive_directories: Sequence[Path],
) -> None:
    resolved_outputs = [
        path.resolve(strict=False) for path in output_paths
    ]
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise engine.LifecycleSmokeError(
            "isolated upgrade output paths must be distinct"
        )
    resolved_archives = [
        path.resolve(strict=False) for path in archive_directories
    ]
    for output in resolved_outputs:
        if any(
            output == archive or archive in output.parents
            for archive in resolved_archives
        ):
            raise engine.LifecycleSmokeError(
                "isolated upgrade outputs must remain outside release "
                f"archive directories: {output}"
            )


def extract_and_verify_app(
    release: engine.ReleaseInputs,
    version: ReleaseVersion,
    destination: Path,
) -> tuple[Path, dict[str, object], installed.AppTreeEvidence]:
    app = engine.extract_packaged_app(release, destination)
    metadata = recovery.verify_packaged_app(
        app,
        release,
        version=version,
    )
    tree = installed.app_tree_evidence(app, release)
    return app, metadata, tree


def run_recovery_cycle(
    *,
    ordinal: int,
    app_path: Path,
    environment: dict[str, str],
    logs: Path,
    mode: str,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> tuple[
    int,
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    stdout_path = logs / f"run-{ordinal}-stdout.log"
    stderr_path = logs / f"run-{ordinal}-stderr.log"
    pid, run = installed_recovery.run_recovery_launch_services_cycle(
        ordinal=ordinal,
        app_path=app_path,
        environment=environment,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        readiness_timeout_seconds=readiness_timeout_seconds,
        observation_seconds=observation_seconds,
        termination_timeout_seconds=termination_timeout_seconds,
    )
    stderr_evidence = installed_recovery.validate_captured_log(
        stderr_path,
        label=f"run {ordinal} stderr",
    )
    try:
        observation = recovery.verify_observation_log(
            stdout_path,
            mode,
        )
    except engine.LifecycleSmokeError as error:
        raise engine.LifecycleSmokeError(
            f"{error}; run {ordinal} stderr={stderr_evidence!r}"
        ) from error
    return pid, run, observation, stderr_evidence


def execute(
    *,
    previous_archive_dir: Path,
    current_archive_dir: Path,
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
    require_output_paths_outside_archives(
        (result_path,),
        (previous_archive_dir, current_archive_dir),
    )

    previous_version, current_version = release_pair()
    previous_release_id = recovery.release_id_for(previous_version)
    current_release_id = recovery.release_id_for(current_version)
    preexisting_applications = installed.list_bundle_applications()

    with isolated_upgrade_root(
        termination_timeout_seconds=termination_timeout_seconds,
    ) as temporary_root:
        snapshot_parent = temporary_root / "archive-snapshots"
        (
            previous_archive_snapshot,
            previous_snapshot_identities,
        ) = snapshot_archive_directory(
            previous_archive_dir,
            version=previous_version,
            destination_parent=snapshot_parent,
        )
        (
            current_archive_snapshot,
            current_snapshot_identities,
        ) = snapshot_archive_directory(
            current_archive_dir,
            version=current_version,
            destination_parent=snapshot_parent,
        )
        verify_archive_readback(
            previous_archive_snapshot,
            historical=True,
        )
        verify_archive_readback(
            current_archive_snapshot,
            historical=False,
        )
        previous_release = recovery.load_release_inputs(
            previous_archive_snapshot,
            verify_readback=False,
            version=previous_version,
        )
        current_release = recovery.load_release_inputs(
            current_archive_snapshot,
            verify_readback=False,
            version=current_version,
        )
        (
            previous_extracted_app,
            previous_app_metadata,
            previous_extracted_tree,
        ) = extract_and_verify_app(
            previous_release,
            previous_version,
            temporary_root / "previous-extraction/app",
        )
        (
            current_extracted_app,
            current_app_metadata,
            current_extracted_tree,
        ) = extract_and_verify_app(
            current_release,
            current_version,
            temporary_root / "current-extraction/app",
        )
        if previous_extracted_tree == current_extracted_tree:
            raise engine.LifecycleSmokeError(
                "previous and current release app trees must differ"
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
        removal.install_exact_temporary_app(
            previous_extracted_app,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
        )
        recovery.verify_packaged_app(
            installed_app,
            previous_release,
            version=previous_version,
        )
        previous_installed_tree = installed.app_tree_evidence(
            installed_app,
            previous_release,
        )
        if previous_installed_tree != previous_extracted_tree:
            raise engine.LifecycleSmokeError(
                "installed previous app differs from its release tree"
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
                "isolated upgrade state existed before fixture creation"
            )
        recovery.write_legacy_fixture(legacy_path)

        migration_environment = (
            installed_recovery.recovery_launch_environment(
                os.environ,
                home=isolated_home,
                temporary=isolated_temporary,
                identity_file=identity_file,
                mode=recovery.MIGRATION_MODE,
            )
        )
        (
            previous_pid,
            previous_run,
            migration_observation,
            migration_stderr,
        ) = run_recovery_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=migration_environment,
            logs=logs,
            mode=recovery.MIGRATION_MODE,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        previous_sqlite = recovery.sqlite_canary_evidence(database_path)
        previous_auxiliary = (
            installed_recovery.auxiliary_sqlite_evidence(
                application_support
            )
        )
        previous_runtime_tree = installed.app_tree_evidence(
            installed_app,
            previous_release,
        )
        if previous_runtime_tree != previous_installed_tree:
            raise engine.LifecycleSmokeError(
                "previous app bytes or modes changed during migration"
            )

        preserved_legacy = recovery.remove_legacy_before_readback(
            legacy_path,
            temporary_root / "preserved-legacy",
        )
        previous_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        removal.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=previous_release,
            expected_tree=previous_installed_tree,
        )
        state_after_previous_removal = installed.state_file_records(
            application_support,
            identity_file,
        )
        require_unchanged_state(
            previous_state,
            state_after_previous_removal,
            phase="previous app removal",
        )

        removal.install_exact_temporary_app(
            current_extracted_app,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
        )
        recovery.verify_packaged_app(
            installed_app,
            current_release,
            version=current_version,
        )
        current_installed_tree = installed.app_tree_evidence(
            installed_app,
            current_release,
        )
        if current_installed_tree != current_extracted_tree:
            raise engine.LifecycleSmokeError(
                "installed current app differs from its release tree"
            )
        state_after_current_install = installed.state_file_records(
            application_support,
            identity_file,
        )
        require_unchanged_state(
            previous_state,
            state_after_current_install,
            phase="current app installation",
        )

        readback_environment = (
            installed_recovery.recovery_launch_environment(
                os.environ,
                home=isolated_home,
                temporary=isolated_temporary,
                identity_file=identity_file,
                mode=recovery.SQLITE_READBACK_MODE,
            )
        )
        (
            current_pid,
            current_run,
            current_observation,
            current_stderr,
        ) = run_recovery_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=readback_environment,
            logs=logs,
            mode=recovery.SQLITE_READBACK_MODE,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if current_pid == previous_pid:
            raise engine.LifecycleSmokeError(
                "upgraded app reused the previous release process identifier"
            )
        if legacy_path.exists() or legacy_path.is_symlink():
            raise engine.LifecycleSmokeError(
                "legacy fixture reappeared after upgrade"
            )
        current_sqlite = recovery.sqlite_canary_evidence(database_path)
        current_auxiliary = (
            installed_recovery.auxiliary_sqlite_evidence(
                application_support
            )
        )
        current_runtime_tree = installed.app_tree_evidence(
            installed_app,
            current_release,
        )
        current_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if previous_sqlite != current_sqlite:
            raise engine.LifecycleSmokeError(
                "runtime-chat canary changed across upgrade"
            )
        if previous_auxiliary != current_auxiliary:
            raise engine.LifecycleSmokeError(
                "auxiliary SQLite evidence changed across upgrade"
            )
        require_unchanged_state(
            previous_state,
            current_state,
            phase="current release first launch",
        )
        if current_runtime_tree != current_installed_tree:
            raise engine.LifecycleSmokeError(
                "current app bytes or modes changed during upgrade readback"
            )

        (
            relaunch_pid,
            relaunch_run,
            relaunch_observation,
            relaunch_stderr,
        ) = run_recovery_cycle(
            ordinal=3,
            app_path=installed_app,
            environment=readback_environment,
            logs=logs,
            mode=recovery.SQLITE_READBACK_MODE,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if len({previous_pid, current_pid, relaunch_pid}) != 3:
            raise engine.LifecycleSmokeError(
                "upgrade launches did not use three distinct processes"
            )
        relaunch_sqlite = recovery.sqlite_canary_evidence(database_path)
        relaunch_auxiliary = (
            installed_recovery.auxiliary_sqlite_evidence(
                application_support
            )
        )
        relaunch_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        relaunch_tree = installed.app_tree_evidence(
            installed_app,
            current_release,
        )
        if current_sqlite != relaunch_sqlite:
            raise engine.LifecycleSmokeError(
                "runtime-chat canary changed across current relaunch"
            )
        if current_auxiliary != relaunch_auxiliary:
            raise engine.LifecycleSmokeError(
                "auxiliary SQLite evidence changed across current relaunch"
            )
        require_unchanged_state(
            current_state,
            relaunch_state,
            phase="current release idempotence relaunch",
        )
        if relaunch_tree != current_installed_tree:
            raise engine.LifecycleSmokeError(
                "current app bytes or modes changed during relaunch"
            )

        removal.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=current_release,
            expected_tree=current_installed_tree,
        )
        final_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        require_unchanged_state(
            relaunch_state,
            final_state,
            phase="final app cleanup",
        )
        if (
            preserved_legacy.read_bytes() != recovery.CANARY_LEGACY_BYTES
            or recovery.sha256_file(preserved_legacy)
            != recovery.CANARY_LEGACY_SHA256
        ):
            raise engine.LifecycleSmokeError(
                "preserved legacy fixture changed during upgrade"
            )

        require_unchanged_archive_snapshot(
            previous_archive_snapshot,
            previous_snapshot_identities,
        )
        require_unchanged_archive_snapshot(
            current_archive_snapshot,
            current_snapshot_identities,
        )
        installed.assert_preexisting_applications_preserved(
            preexisting_applications
        )
        result = {
            "archiveReadback": {
                "current": {
                    "currentSourceCompared": False,
                    "mode": CURRENT_READBACK_MODE,
                    "readbackAndExerciseSameSnapshot": True,
                    "snapshotFiles": current_snapshot_identities,
                    "snapshotFilesUnchangedAfterExercise": True,
                    "status": "passed",
                },
                "previous": {
                    "currentSourceCompared": False,
                    "mode": PREVIOUS_READBACK_MODE,
                    "readbackAndExerciseSameSnapshot": True,
                    "snapshotFiles": previous_snapshot_identities,
                    "snapshotFilesUnchangedAfterExercise": True,
                    "status": "passed",
                },
            },
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
            "cleanup": {
                "appAbsentAfterFinalRemoval": True,
                "applicationSupportCleanupPerformed": False,
                "exactTemporaryAppPathOnly": True,
                "removalCount": 2,
            },
            "installation": {
                "copyTool": "ditto",
                "currentTree": current_installed_tree.record(),
                "installedRelativePath": "Applications/AetherLink.app",
                "previousTree": previous_installed_tree.record(),
                "replacementMethod": REPLACEMENT_METHOD,
                "stalePreviousBundleFilesAbsent": True,
                "treesDiffer": True,
            },
            "isolation": {
                "preexistingBundleApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "launchServices": {
                "commandPolicy": installed_recovery.COMMAND_POLICY,
                "distinctProcessIdentifiers": True,
                "runs": [previous_run, current_run, relaunch_run],
            },
            "limitations": [
                "same-host-per-user-temporary-home-only",
                "build-to-build-upgrade-not-rollback",
                "application-support-retained-no-automatic-data-cleanup",
                "post-archive-harness-not-build-input-member",
                "not-clean-machine-device-provider-network-ui-or-distribution-evidence",
                "not-production-release-qualification",
            ],
            "releases": {
                "from": {
                    "app": previous_app_metadata,
                    "archiveSha256": previous_release.archive_sha256,
                    "manifestSha256": previous_release.manifest_sha256,
                    "releaseId": previous_release_id,
                },
                "to": {
                    "app": current_app_metadata,
                    "archiveSha256": current_release.archive_sha256,
                    "manifestSha256": current_release.manifest_sha256,
                    "releaseId": current_release_id,
                },
            },
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "scope": RESULT_SCOPE,
            "stateUpgrade": {
                "applicationSupportPreservedAcrossUpgrade": True,
                "auxiliarySQLite": list(previous_auxiliary),
                "bytesAndModesUnchangedAcrossUpgrade": True,
                "currentRelaunchIdempotent": True,
                "expectedSQLiteFiles": list(
                    installed.EXPECTED_SQLITE_FILES
                ),
                "legacyAbsentAfterUpgrade": True,
                "legacyFixturePreservedUnchanged": True,
                "migrationObservation": migration_observation,
                "migrationSQLite": previous_sqlite.record(),
                "readbackObservation": current_observation,
                "readbackSQLite": current_sqlite.record(),
                "relaunchObservation": relaunch_observation,
                "relaunchSQLite": relaunch_sqlite.record(),
                "runtimeIdentityFilePresent": identity_file.is_file(),
                "stderr": {
                    "migration": migration_stderr,
                    "readback": current_stderr,
                    "relaunch": relaunch_stderr,
                },
            },
            "status": "passed",
        }

    installed.publish_result(result_path, result)
    return result


def require_publishable_result(
    path: Path,
    payload: bytes,
    *,
    label: str,
) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    if (
        path.is_symlink()
        or not path.is_file()
        or path.read_bytes() != payload
    ):
        raise engine.LifecycleSmokeError(
            f"{label} output already exists with different bytes: {path}"
        )


def prepare_result_payload(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.pair-",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def publish_result_pair(
    result_path: Path,
    result_payload: bytes,
    repeatability_result_path: Path,
    repeatability_payload: bytes,
    *,
    linker: Callable[[Path, Path], None] = os.link,
) -> None:
    targets = (
        (result_path, result_payload, "canonical result"),
        (
            repeatability_result_path,
            repeatability_payload,
            "repeatability receipt",
        ),
    )
    for path, payload, label in targets:
        require_publishable_result(path, payload, label=label)

    temporary_paths: dict[Path, Path] = {}
    created_links: list[tuple[Path, Path]] = []
    try:
        for path, payload, _label in targets:
            if not (path.exists() or path.is_symlink()):
                temporary_paths[path] = prepare_result_payload(
                    path,
                    payload,
                )
        for path, payload, label in targets:
            temporary_path = temporary_paths.get(path)
            if temporary_path is None:
                continue
            try:
                linker(temporary_path, path)
            except FileExistsError:
                require_publishable_result(path, payload, label=label)
            else:
                created_links.append((path, temporary_path))
    except BaseException as error:
        rollback_failures: list[str] = []
        for path, temporary_path in reversed(created_links):
            try:
                path_status = path.lstat()
                temporary_status = temporary_path.lstat()
                if (
                    stat.S_ISLNK(path_status.st_mode)
                    or not stat.S_ISREG(path_status.st_mode)
                    or (
                        path_status.st_dev,
                        path_status.st_ino,
                    )
                    != (
                        temporary_status.st_dev,
                        temporary_status.st_ino,
                    )
                ):
                    raise engine.LifecycleSmokeError(
                        "published path no longer matches its owned "
                        "temporary inode"
                    )
                path.unlink()
            except BaseException as rollback_error:
                rollback_failures.append(
                    f"{path}: {rollback_error}"
                )
        if rollback_failures:
            raise engine.LifecycleSmokeError(
                "repeatability publication failed and exact rollback "
                f"was incomplete: {rollback_failures!r}"
            ) from error
        raise
    finally:
        for temporary_path in temporary_paths.values():
            temporary_path.unlink(missing_ok=True)


def execute_repeatability(
    *,
    previous_archive_dir: Path,
    current_archive_dir: Path,
    result_path: Path,
    repeatability_result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    require_output_paths_outside_archives(
        (result_path, repeatability_result_path),
        (previous_archive_dir, current_archive_dir),
    )
    run_results: list[dict[str, object]] = []
    run_bytes: list[bytes] = []
    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-upgrade-repeatability-results-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        for ordinal in (1, 2):
            run_path = temporary_root / f"run-{ordinal}.json"
            result = execute(
                previous_archive_dir=previous_archive_dir,
                current_archive_dir=current_archive_dir,
                result_path=run_path,
                readiness_timeout_seconds=readiness_timeout_seconds,
                observation_seconds=observation_seconds,
                termination_timeout_seconds=termination_timeout_seconds,
            )
            payload = run_path.read_bytes()
            expected_payload = engine.canonical_json_bytes(result)
            if payload != expected_payload:
                raise engine.LifecycleSmokeError(
                    f"upgrade run {ordinal} result publication differs"
                )
            run_results.append(result)
            run_bytes.append(payload)

    if run_bytes[0] != run_bytes[1]:
        raise engine.LifecycleSmokeError(
            "two complete upgrade runs produced different result bytes"
        )
    if not exact_results_equal(run_results[0], run_results[1]):
        raise engine.LifecycleSmokeError(
            "two complete upgrade runs produced different result values"
        )

    canonical_result = run_results[0]
    canonical_identity = {
        "sha256": hashlib.sha256(run_bytes[0]).hexdigest(),
        "size": len(run_bytes[0]),
    }
    receipt = {
        "canonicalResult": {
            "fileName": result_path.name,
            **canonical_identity,
        },
        "limitations": [
            "same-host-repeatability-only",
            "two-recorded-runs-not-arbitrary-repeatability",
            "not-cross-host-clean-machine-or-signed-distribution-evidence",
            "not-rollback-device-provider-network-or-production-evidence",
        ],
        "releaseTransition": {
            "from": canonical_result["releases"]["from"]["releaseId"],
            "to": canonical_result["releases"]["to"]["releaseId"],
        },
        "resultBytesEqual": True,
        "runCount": 2,
        "runs": [
            {
                "ordinal": ordinal,
                **canonical_identity,
                "status": "passed",
            }
            for ordinal in (1, 2)
        ],
        "schemaVersion": REPEATABILITY_SCHEMA_VERSION,
        "scope": REPEATABILITY_SCOPE,
        "status": "passed",
    }
    receipt_payload = engine.canonical_json_bytes(receipt)
    require_publishable_result(
        result_path,
        run_bytes[0],
        label="canonical result",
    )
    require_publishable_result(
        repeatability_result_path,
        receipt_payload,
        label="repeatability receipt",
    )
    publish_result_pair(
        result_path,
        run_bytes[0],
        repeatability_result_path,
        receipt_payload,
    )
    return receipt


def exact_results_equal(
    first: object,
    second: object,
) -> bool:
    if type(first) is not type(second):
        return False
    if isinstance(first, dict):
        return (
            isinstance(second, dict)
            and set(first) == set(second)
            and all(
                exact_results_equal(first[key], second[key])
                for key in first
            )
        )
    if isinstance(first, list):
        return (
            isinstance(second, list)
            and len(first) == len(second)
            and all(
                exact_results_equal(first_value, second_value)
                for first_value, second_value in zip(first, second)
            )
        )
    return first == second


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    previous, current = release_pair()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-archive-dir",
        type=Path,
        default=default_archive_dir(previous),
    )
    parser.add_argument(
        "--to-archive-dir",
        type=Path,
        default=default_archive_dir(current),
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
        help="run one upgrade exercise without a repeatability receipt",
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


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.single_run:
            result = execute(
                previous_archive_dir=arguments.from_archive_dir,
                current_archive_dir=arguments.to_archive_dir,
                result_path=arguments.result,
                readiness_timeout_seconds=arguments.readiness_timeout_seconds,
                observation_seconds=arguments.observation_seconds,
                termination_timeout_seconds=arguments.termination_timeout_seconds,
            )
            summary = (
                f"{result['releases']['from']['releaseId']} -> "
                f"{result['releases']['to']['releaseId']}; "
                "one state-preserving upgrade run completed."
            )
        else:
            receipt = execute_repeatability(
                previous_archive_dir=arguments.from_archive_dir,
                current_archive_dir=arguments.to_archive_dir,
                result_path=arguments.result,
                repeatability_result_path=arguments.repeatability_result,
                readiness_timeout_seconds=arguments.readiness_timeout_seconds,
                observation_seconds=arguments.observation_seconds,
                termination_timeout_seconds=arguments.termination_timeout_seconds,
            )
            summary = (
                f"{receipt['releaseTransition']['from']} -> "
                f"{receipt['releaseTransition']['to']}; "
                "two complete runs produced byte-identical results."
            )
    except KeyboardInterrupt:
        print(
            "macOS isolated build-to-build upgrade smoke interrupted.",
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
            f"macOS isolated build-to-build upgrade smoke failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "macOS isolated build-to-build upgrade smoke passed: "
        + summary
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
