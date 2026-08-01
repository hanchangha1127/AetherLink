#!/usr/bin/env python3
"""Observe a bounded current-historical-current macOS state readback cycle.

This is intentionally not a product rollback or N/N-1 qualification.  It
manually replaces local ad-hoc app trees under one temporary HOME and checks
only a fixed non-security Runtime-chat SQLite canary.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
from typing import Callable, Sequence
import zipfile

if __package__:
    from script import run_macos_isolated_upgrade_smoke as upgrade
    from script.check_release_version_ledger import ReleaseVersion
else:
    import run_macos_isolated_upgrade_smoke as upgrade
    from check_release_version_ledger import ReleaseVersion


engine = upgrade.engine
installed = upgrade.installed
installed_recovery = upgrade.installed_recovery
removal = upgrade.removal
recovery = upgrade.recovery

ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-isolated-current-historical-current-"
    "manual-replacement-readback-v1"
)
REPEATABILITY_SCHEMA_VERSION = 1
REPEATABILITY_SCOPE = (
    "same-host-per-user-isolated-current-historical-current-"
    "manual-replacement-readback-repeatability-v1"
)
CURRENT_READBACK_MODE = upgrade.CURRENT_READBACK_MODE
HISTORICAL_READBACK_MODE = upgrade.PREVIOUS_READBACK_MODE
REPLACEMENT_METHOD = upgrade.REPLACEMENT_METHOD
RESULT_MAXIMUM_BYTES = 4 * 1_024 * 1_024
EXPECTED_HISTORICAL_BUILD_NUMBER = 23
EXPECTED_CURRENT_BUILD_NUMBER = 24
EXPECTED_MARKETING_VERSION = "1.0.0"


def release_pair() -> tuple[ReleaseVersion, ReleaseVersion]:
    """Return only the exact Build 23/24 pair recorded for this observation."""
    historical, current = upgrade.release_pair()
    validate_release_pair(historical, current)
    return historical, current


def validate_release_pair(
    historical: ReleaseVersion,
    current: ReleaseVersion,
) -> None:
    upgrade.validate_release_pair(historical, current)
    exact_pair = (
        historical.build_number,
        historical.marketing_version,
        current.build_number,
        current.marketing_version,
    )
    if exact_pair != (
        EXPECTED_HISTORICAL_BUILD_NUMBER,
        EXPECTED_MARKETING_VERSION,
        EXPECTED_CURRENT_BUILD_NUMBER,
        EXPECTED_MARKETING_VERSION,
    ):
        raise engine.LifecycleSmokeError(
            "reverse-version observation requires the exact terminal "
            "Build 23/24 local ledger pair"
        )


def default_archive_dir(version: ReleaseVersion) -> Path:
    return upgrade.default_archive_dir(version)


def default_result_path() -> Path:
    historical, current = release_pair()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{current.build_number}-to-{historical.build_number}-to-"
            f"{current.build_number}-isolated-reverse-version-readback-v1.json"
        )
    )


def default_repeatability_result_path() -> Path:
    historical, current = release_pair()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{current.build_number}-to-{historical.build_number}-to-"
            f"{current.build_number}-isolated-reverse-version-readback-"
            "repeatability-v1.json"
        )
    )


def exact_results_equal(first: object, second: object) -> bool:
    return upgrade.exact_results_equal(first, second)


def require_physical_existing_parent(path: Path) -> Path:
    absolute_parent = Path(os.path.abspath(path.parent))
    try:
        resolved_parent = path.parent.resolve(strict=True)
        parent_status = path.parent.lstat()
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"result parent must already exist as a physical directory: "
            f"{path.parent}: {error}"
        ) from error
    if (
        resolved_parent != absolute_parent
        or stat.S_ISLNK(parent_status.st_mode)
        or not stat.S_ISDIR(parent_status.st_mode)
        or parent_status.st_uid != os.getuid()
    ):
        raise engine.LifecycleSmokeError(
            f"result parent must be an owned physical path without symlink "
            f"ancestors: {path.parent}"
        )
    return absolute_parent


def stable_regular_bytes(
    path: Path,
    *,
    maximum_bytes: int = RESULT_MAXIMUM_BYTES,
) -> bytes:
    """Read one single-link regular file without following replacements."""
    require_physical_existing_parent(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot open result path {path}: {error}"
        ) from error
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_size <= 0
            or before.st_size > maximum_bytes
        ):
            raise engine.LifecycleSmokeError(
                f"result path must be a bounded single-link regular file: {path}"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise engine.LifecycleSmokeError(
                    f"result path exceeded its byte limit: {path}"
                )
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_uid,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if identity != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_uid,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) or total != before.st_size:
        raise engine.LifecycleSmokeError(
            f"result path changed while being read: {path}"
        )
    try:
        final = path.lstat()
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"result path disappeared after read: {path}: {error}"
        ) from error
    if (
        stat.S_ISLNK(final.st_mode)
        or not stat.S_ISREG(final.st_mode)
        or final.st_nlink != 1
        or final.st_uid != os.getuid()
        or stat.S_IMODE(final.st_mode) != 0o600
        or (
            final.st_dev,
            final.st_ino,
            final.st_mode,
            final.st_uid,
            final.st_nlink,
            final.st_size,
            final.st_mtime_ns,
            final.st_ctime_ns,
        )
        != identity
    ):
        raise engine.LifecycleSmokeError(
            f"result path identity changed after read: {path}"
        )
    return b"".join(chunks)


def require_publishable_result(
    path: Path,
    payload: bytes,
    *,
    label: str,
) -> bool:
    """Return True for an identical existing result, False when absent."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot inspect {label} output {path}: {error}"
        ) from error
    if stable_regular_bytes(path) != payload:
        raise engine.LifecycleSmokeError(
            f"{label} output already exists with different bytes: {path}"
        )
    return True


def prepare_result_payload(
    path: Path,
    payload: bytes,
) -> tuple[Path, tuple[int, int]]:
    require_physical_existing_parent(path)

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
        status = temporary_path.lstat()
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_nlink != 1
            or status.st_uid != os.getuid()
            or stat.S_IMODE(status.st_mode) != 0o600
            or status.st_size != len(payload)
        ):
            raise engine.LifecycleSmokeError(
                "prepared result payload has an invalid identity"
            )
        return temporary_path, (status.st_dev, status.st_ino)
    except BaseException as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except BaseException as cleanup_error:
            raise engine.LifecycleSmokeError(
                "result payload preparation failed and temporary cleanup "
                f"was incomplete: {temporary_path}: {cleanup_error}"
            ) from error
        raise


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot open result directory {path}: {error}"
        ) from error
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISDIR(status.st_mode):
            raise engine.LifecycleSmokeError(
                f"result parent is not a directory: {path}"
            )
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_result_files(
    targets: Sequence[tuple[Path, bytes, str]],
    *,
    linker: Callable[[Path, Path], None] = os.link,
    rollback_unlinker: Callable[[Path], None] | None = None,
    temporary_unlinker: Callable[[Path], None] | None = None,
    directory_sync: Callable[[Path], None] = fsync_directory,
) -> None:
    """Create result links as one rollback-capable create-only transaction."""
    if not targets:
        raise engine.LifecycleSmokeError("result publication requires a target")
    absolute_paths = [Path(os.path.abspath(path)) for path, _payload, _label in targets]
    if len(set(absolute_paths)) != len(absolute_paths):
        raise engine.LifecycleSmokeError(
            "result publication targets must be distinct"
        )

    existing: dict[Path, bool] = {}
    for path, payload, label in targets:
        existing[path] = require_publishable_result(path, payload, label=label)

    prepared: dict[Path, tuple[Path, tuple[int, int]]] = {}
    intents: list[tuple[Path, tuple[int, int]]] = []
    touched_parents: set[Path] = set()
    parents = sorted({path.parent for path, _payload, _label in targets}, key=str)
    unlink_owned = rollback_unlinker or (lambda path: path.unlink())
    unlink_temporary = temporary_unlinker or (lambda path: path.unlink())

    def cleanup_temporaries() -> list[str]:
        failures: list[str] = []
        for temporary_path, _inode in prepared.values():
            try:
                try:
                    temporary_path.lstat()
                except FileNotFoundError:
                    continue
                unlink_temporary(temporary_path)
            except BaseException as cleanup_error:
                failures.append(f"{temporary_path}: {cleanup_error}")
        return failures

    try:
        for path, payload, _label in targets:
            if not existing[path]:
                prepared[path] = prepare_result_payload(path, payload)
                touched_parents.add(path.parent)

        for path, payload, label in targets:
            if existing[path]:
                continue
            temporary_path, inode = prepared[path]
            intent = (path, inode)
            # Record ownership before linking so an interrupt immediately after
            # os.link still has enough information for exact cleanup.
            intents.append(intent)
            try:
                linker(temporary_path, path)
            except FileExistsError:
                intents.remove(intent)
                require_publishable_result(path, payload, label=label)
            else:
                status = path.lstat()
                if (
                    stat.S_ISLNK(status.st_mode)
                    or not stat.S_ISREG(status.st_mode)
                    or status.st_uid != os.getuid()
                    or stat.S_IMODE(status.st_mode) != 0o600
                    or (status.st_dev, status.st_ino) != inode
                ):
                    raise engine.LifecycleSmokeError(
                        f"published {label} does not match its prepared inode"
                    )

        for parent in parents:
            directory_sync(parent)
        temporary_cleanup_failures = cleanup_temporaries()
        if temporary_cleanup_failures:
            raise engine.LifecycleSmokeError(
                "temporary result payload cleanup failed: "
                f"{temporary_cleanup_failures!r}"
            )
        for parent in parents:
            directory_sync(parent)
        for path, payload, label in targets:
            if stable_regular_bytes(path) != payload:
                raise engine.LifecycleSmokeError(
                    f"published {label} failed final byte readback"
                )
        intents.clear()
    except BaseException as error:
        cleanup_failures: list[str] = []
        for path, inode in reversed(intents):
            try:
                try:
                    status = path.lstat()
                except FileNotFoundError:
                    continue
                if (
                    stat.S_ISLNK(status.st_mode)
                    or not stat.S_ISREG(status.st_mode)
                    or (status.st_dev, status.st_ino) != inode
                ):
                    raise engine.LifecycleSmokeError(
                        "publication target no longer matches its owned inode"
                    )
                unlink_owned(path)
            except BaseException as cleanup_error:
                cleanup_failures.append(f"{path}: {cleanup_error}")
        cleanup_failures.extend(cleanup_temporaries())
        for parent in sorted(touched_parents, key=str):
            try:
                directory_sync(parent)
            except BaseException as cleanup_error:
                cleanup_failures.append(f"{parent}: {cleanup_error}")
        if cleanup_failures:
            raise engine.LifecycleSmokeError(
                "result publication failed and exact cleanup was incomplete: "
                f"{cleanup_failures!r}"
            ) from error
        raise


def publish_result_pair(
    result_path: Path,
    result_payload: bytes,
    repeatability_result_path: Path,
    repeatability_payload: bytes,
    **kwargs: object,
) -> None:
    publish_result_files(
        (
            (result_path, result_payload, "canonical result"),
            (
                repeatability_result_path,
                repeatability_payload,
                "repeatability receipt",
            ),
        ),
        **kwargs,
    )


def publish_single_result(path: Path, result: dict[str, object]) -> None:
    payload = engine.canonical_json_bytes(result)
    publish_result_files(((path, payload, "single-run result"),))


def _release_record(
    *,
    release: engine.ReleaseInputs,
    release_id: str,
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "app": metadata,
        "archiveSha256": release.archive_sha256,
        "manifestSha256": release.manifest_sha256,
        "releaseId": release_id,
    }


def execute(
    *,
    historical_archive_dir: Path,
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
    upgrade.require_output_paths_outside_archives(
        (result_path,),
        (historical_archive_dir, current_archive_dir),
    )

    historical_version, current_version = release_pair()
    validate_release_pair(historical_version, current_version)
    historical_release_id = recovery.release_id_for(historical_version)
    current_release_id = recovery.release_id_for(current_version)
    preexisting_applications = installed.list_bundle_applications()

    with upgrade.isolated_upgrade_root(
        termination_timeout_seconds=termination_timeout_seconds,
    ) as temporary_root:
        snapshot_parent = temporary_root / "archive-snapshots"
        historical_snapshot, historical_snapshot_identities = (
            upgrade.snapshot_archive_directory(
                historical_archive_dir,
                version=historical_version,
                destination_parent=snapshot_parent,
            )
        )
        current_snapshot, current_snapshot_identities = (
            upgrade.snapshot_archive_directory(
                current_archive_dir,
                version=current_version,
                destination_parent=snapshot_parent,
            )
        )
        upgrade.verify_archive_readback(historical_snapshot, historical=True)
        upgrade.verify_archive_readback(current_snapshot, historical=False)

        historical_release = recovery.load_release_inputs(
            historical_snapshot,
            verify_readback=False,
            version=historical_version,
        )
        current_release = recovery.load_release_inputs(
            current_snapshot,
            verify_readback=False,
            version=current_version,
        )
        (
            historical_extracted_app,
            historical_app_metadata,
            historical_extracted_tree,
        ) = upgrade.extract_and_verify_app(
            historical_release,
            historical_version,
            temporary_root / "historical-extraction/app",
        )
        (
            current_extracted_app,
            current_app_metadata,
            current_extracted_tree,
        ) = upgrade.extract_and_verify_app(
            current_release,
            current_version,
            temporary_root / "current-extraction/app",
        )
        if historical_extracted_tree == current_extracted_tree:
            raise engine.LifecycleSmokeError(
                "historical and current release app trees must differ"
            )

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        logs = temporary_root / "logs"
        for path in (isolated_home, isolated_temporary, isolated_state, logs):
            path.mkdir(mode=0o700)

        installed_app = isolated_home / "Applications" / installed.APP_RELATIVE_PATH
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
                "isolated reverse-version state existed before fixture creation"
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
        initial_current_tree = installed.app_tree_evidence(
            installed_app,
            current_release,
        )
        if initial_current_tree != current_extracted_tree:
            raise engine.LifecycleSmokeError(
                "initial current app differs from its release tree"
            )

        recovery.write_legacy_fixture(legacy_path)
        initialization_environment = installed_recovery.recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.MIGRATION_MODE,
        )
        (
            initial_pid,
            initial_run,
            initialization_observation,
            initialization_stderr,
        ) = upgrade.run_recovery_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=initialization_environment,
            logs=logs,
            mode=recovery.MIGRATION_MODE,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        initial_sqlite = recovery.sqlite_canary_evidence(database_path)
        initial_auxiliary = installed_recovery.auxiliary_sqlite_evidence(
            application_support
        )
        if installed.app_tree_evidence(installed_app, current_release) != initial_current_tree:
            raise engine.LifecycleSmokeError(
                "initial current app bytes or modes changed during fixture setup"
            )
        preserved_legacy = recovery.remove_legacy_before_readback(
            legacy_path,
            temporary_root / "preserved-legacy",
        )
        baseline_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        removal.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=current_release,
            expected_tree=initial_current_tree,
        )
        upgrade.require_unchanged_state(
            baseline_state,
            installed.state_file_records(application_support, identity_file),
            phase="initial current app removal",
        )

        removal.install_exact_temporary_app(
            historical_extracted_app,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
        )
        recovery.verify_packaged_app(
            installed_app,
            historical_release,
            version=historical_version,
        )
        historical_installed_tree = installed.app_tree_evidence(
            installed_app,
            historical_release,
        )
        if historical_installed_tree != historical_extracted_tree:
            raise engine.LifecycleSmokeError(
                "installed historical app differs from its release tree"
            )
        upgrade.require_unchanged_state(
            baseline_state,
            installed.state_file_records(application_support, identity_file),
            phase="historical app installation",
        )

        readback_environment = installed_recovery.recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.SQLITE_READBACK_MODE,
        )
        (
            historical_pid,
            historical_run,
            historical_observation,
            historical_stderr,
        ) = upgrade.run_recovery_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=readback_environment,
            logs=logs,
            mode=recovery.SQLITE_READBACK_MODE,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        historical_sqlite = recovery.sqlite_canary_evidence(database_path)
        historical_auxiliary = installed_recovery.auxiliary_sqlite_evidence(
            application_support
        )
        historical_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if initial_sqlite != historical_sqlite:
            raise engine.LifecycleSmokeError(
                "Runtime-chat canary changed during historical readback"
            )
        if initial_auxiliary != historical_auxiliary:
            raise engine.LifecycleSmokeError(
                "auxiliary SQLite evidence changed during historical readback"
            )
        upgrade.require_unchanged_state(
            baseline_state,
            historical_state,
            phase="historical release readback",
        )
        if installed.app_tree_evidence(installed_app, historical_release) != historical_installed_tree:
            raise engine.LifecycleSmokeError(
                "historical app bytes or modes changed during readback"
            )
        removal.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=historical_release,
            expected_tree=historical_installed_tree,
        )
        upgrade.require_unchanged_state(
            baseline_state,
            installed.state_file_records(application_support, identity_file),
            phase="historical app removal",
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
        restored_current_tree = installed.app_tree_evidence(
            installed_app,
            current_release,
        )
        if restored_current_tree != initial_current_tree:
            raise engine.LifecycleSmokeError(
                "restored current app differs from its initial exact tree"
            )
        upgrade.require_unchanged_state(
            baseline_state,
            installed.state_file_records(application_support, identity_file),
            phase="current app restoration",
        )
        (
            restored_pid,
            restored_run,
            restored_observation,
            restored_stderr,
        ) = upgrade.run_recovery_cycle(
            ordinal=3,
            app_path=installed_app,
            environment=readback_environment,
            logs=logs,
            mode=recovery.SQLITE_READBACK_MODE,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if len({initial_pid, historical_pid, restored_pid}) != 3:
            raise engine.LifecycleSmokeError(
                "reverse-version observation did not use three distinct processes"
            )
        restored_sqlite = recovery.sqlite_canary_evidence(database_path)
        restored_auxiliary = installed_recovery.auxiliary_sqlite_evidence(
            application_support
        )
        restored_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if initial_sqlite != restored_sqlite:
            raise engine.LifecycleSmokeError(
                "Runtime-chat canary changed after current app restoration"
            )
        if initial_auxiliary != restored_auxiliary:
            raise engine.LifecycleSmokeError(
                "auxiliary SQLite evidence changed after current app restoration"
            )
        upgrade.require_unchanged_state(
            baseline_state,
            restored_state,
            phase="restored current release readback",
        )
        if installed.app_tree_evidence(installed_app, current_release) != restored_current_tree:
            raise engine.LifecycleSmokeError(
                "restored current app bytes or modes changed during readback"
            )
        if legacy_path.exists() or legacy_path.is_symlink():
            raise engine.LifecycleSmokeError(
                "legacy fixture reappeared during reverse-version readback"
            )

        removal.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=current_release,
            expected_tree=restored_current_tree,
        )
        final_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        upgrade.require_unchanged_state(
            baseline_state,
            final_state,
            phase="final current app removal",
        )
        if (
            preserved_legacy.read_bytes() != recovery.CANARY_LEGACY_BYTES
            or recovery.sha256_file(preserved_legacy)
            != recovery.CANARY_LEGACY_SHA256
        ):
            raise engine.LifecycleSmokeError(
                "preserved fixture bytes changed during reverse-version readback"
            )

        upgrade.require_unchanged_archive_snapshot(
            historical_snapshot,
            historical_snapshot_identities,
        )
        upgrade.require_unchanged_archive_snapshot(
            current_snapshot,
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
                "historical": {
                    "currentSourceCompared": False,
                    "mode": HISTORICAL_READBACK_MODE,
                    "readbackAndExerciseSameSnapshot": True,
                    "snapshotFiles": historical_snapshot_identities,
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
                "removalCount": 3,
            },
            "installation": {
                "copyTool": "ditto",
                "historicalTree": historical_installed_tree.record(),
                "initialCurrentTree": initial_current_tree.record(),
                "installedRelativePath": "Applications/AetherLink.app",
                "replacementCount": 2,
                "replacementMethod": REPLACEMENT_METHOD,
                "restoredCurrentTree": restored_current_tree.record(),
                "staleBundleFilesAbsentAfterEveryReplacement": True,
                "treesDifferAcrossVersions": True,
            },
            "isolation": {
                "preexistingBundleApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "launchServices": {
                "allOwnedProcessesGoneAfterEachRun": True,
                "commandPolicy": installed_recovery.COMMAND_POLICY,
                "distinctProcessIdentifiers": True,
                "runs": [initial_run, historical_run, restored_run],
            },
            "limitations": [
                "same-host-per-user-temporary-home-only",
                "local-ad-hoc-manual-exact-path-replacement-only",
                "fixed-runtime-chat-canary-readback-only",
                "fixture-initialization-not-supported-state-migration",
                "historical-build-readback-not-declared-production-predecessor",
                "not-updater-dmg-finder-quarantine-or-gatekeeper-evidence",
                "not-signed-notarized-clean-machine-or-cross-host-evidence",
                "not-pairing-keyset-revocation-or-security-state-evidence",
                "not-arbitrary-n-n-minus-one-upgrade-or-product-rollback",
                "failure-is-bounded-observation-failure-not-product-rollback-failure",
                "not-device-provider-network-ui-or-production-release-qualification",
            ],
            "qualification": {
                "nMinusOneQualificationClaimed": False,
                "productRollbackQualificationClaimed": False,
                "productionPredecessorClaimed": False,
                "securityEvidenceProduced": False,
                "securityQualificationClaimed": False,
                "securityStateInspected": False,
                "supportedUpgradeOrRollbackClaimed": False,
            },
            "releaseSequence": [
                {
                    "ordinal": 1,
                    "releaseId": current_release_id,
                    "role": "current-fixture-initialization",
                },
                {
                    "ordinal": 2,
                    "releaseId": historical_release_id,
                    "role": "historical-readback",
                },
                {
                    "ordinal": 3,
                    "releaseId": current_release_id,
                    "role": "current-readback",
                },
            ],
            "releases": {
                "current": _release_record(
                    release=current_release,
                    release_id=current_release_id,
                    metadata=current_app_metadata,
                ),
                "historical": _release_record(
                    release=historical_release,
                    release_id=historical_release_id,
                    metadata=historical_app_metadata,
                ),
            },
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "scope": RESULT_SCOPE,
            "stateReadback": {
                "applicationSupportPreservedAcrossManualReplacement": True,
                "auxiliarySQLite": list(initial_auxiliary),
                "bytesAndModesUnchangedAcrossManualReplacement": True,
                "canaryExactlyOnceAtEveryStage": True,
                "expectedSQLiteFiles": list(installed.EXPECTED_SQLITE_FILES),
                "fixtureInitializationObservation": initialization_observation,
                "fixtureInitializationSQLite": initial_sqlite.record(),
                "historicalObservation": historical_observation,
                "historicalSQLite": historical_sqlite.record(),
                "legacyAbsentAfterFixtureInitialization": True,
                "legacyFixturePreservedUnchanged": True,
                "restoredCurrentObservation": restored_observation,
                "restoredCurrentSQLite": restored_sqlite.record(),
                "runtimeIdentityFilePresent": identity_file.is_file(),
                "stderr": {
                    "fixtureInitialization": initialization_stderr,
                    "historicalReadback": historical_stderr,
                    "restoredCurrentReadback": restored_stderr,
                },
            },
            "status": "passed",
        }

    publish_single_result(result_path, result)
    return result


def execute_repeatability(
    *,
    historical_archive_dir: Path,
    current_archive_dir: Path,
    result_path: Path,
    repeatability_result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    upgrade.require_output_paths_outside_archives(
        (result_path, repeatability_result_path),
        (historical_archive_dir, current_archive_dir),
    )
    run_results: list[dict[str, object]] = []
    run_bytes: list[bytes] = []
    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-reverse-version-readback-results-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        for ordinal in (1, 2):
            run_path = temporary_root / f"run-{ordinal}.json"
            result = execute(
                historical_archive_dir=historical_archive_dir,
                current_archive_dir=current_archive_dir,
                result_path=run_path,
                readiness_timeout_seconds=readiness_timeout_seconds,
                observation_seconds=observation_seconds,
                termination_timeout_seconds=termination_timeout_seconds,
            )
            payload = stable_regular_bytes(run_path)
            if payload != engine.canonical_json_bytes(result):
                raise engine.LifecycleSmokeError(
                    f"reverse-version run {ordinal} result publication differs"
                )
            run_results.append(result)
            run_bytes.append(payload)

    if run_bytes[0] != run_bytes[1]:
        raise engine.LifecycleSmokeError(
            "two complete reverse-version observations produced different bytes"
        )
    if not exact_results_equal(run_results[0], run_results[1]):
        raise engine.LifecycleSmokeError(
            "two complete reverse-version observations produced different values"
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
            "same-host-two-run-repeatability-only",
            "manual-local-ad-hoc-replacement-not-an-updater",
            "historical-build-is-not-a-declared-production-predecessor",
            "not-arbitrary-n-n-minus-one-or-product-rollback-evidence",
            "not-security-device-network-signed-distribution-or-production-evidence",
        ],
        "qualification": {
            "nMinusOneQualificationClaimed": False,
            "productRollbackQualificationClaimed": False,
            "securityEvidenceProduced": False,
            "securityQualificationClaimed": False,
        },
        "releaseSequence": [
            entry["releaseId"] for entry in canonical_result["releaseSequence"]
        ],
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
    publish_result_pair(
        result_path,
        run_bytes[0],
        repeatability_result_path,
        receipt_payload,
    )
    return receipt


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    historical, current = release_pair()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--historical-archive-dir",
        type=Path,
        default=default_archive_dir(historical),
    )
    parser.add_argument(
        "--current-archive-dir",
        type=Path,
        default=default_archive_dir(current),
    )
    parser.add_argument("--result", type=Path, default=default_result_path())
    parser.add_argument(
        "--repeatability-result",
        type=Path,
        default=default_repeatability_result_path(),
    )
    parser.add_argument(
        "--single-run",
        action="store_true",
        help="run one bounded observation without a repeatability receipt",
    )
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value, "readiness timeout", 0.1, 60
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
            value, "termination timeout", 0.1, 30
        ),
        default=10.0,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.single_run:
            result = execute(
                historical_archive_dir=arguments.historical_archive_dir,
                current_archive_dir=arguments.current_archive_dir,
                result_path=arguments.result,
                readiness_timeout_seconds=arguments.readiness_timeout_seconds,
                observation_seconds=arguments.observation_seconds,
                termination_timeout_seconds=arguments.termination_timeout_seconds,
            )
            summary = (
                " -> ".join(
                    entry["releaseId"] for entry in result["releaseSequence"]
                )
                + "; one bounded non-production readback observation completed."
            )
        else:
            receipt = execute_repeatability(
                historical_archive_dir=arguments.historical_archive_dir,
                current_archive_dir=arguments.current_archive_dir,
                result_path=arguments.result,
                repeatability_result_path=arguments.repeatability_result,
                readiness_timeout_seconds=arguments.readiness_timeout_seconds,
                observation_seconds=arguments.observation_seconds,
                termination_timeout_seconds=arguments.termination_timeout_seconds,
            )
            summary = (
                " -> ".join(receipt["releaseSequence"])
                + "; two byte-identical bounded observations completed."
            )
    except KeyboardInterrupt:
        print("macOS reverse-version readback observation interrupted.", file=sys.stderr)
        return 130
    except (
        engine.LifecycleSmokeError,
        OSError,
        sqlite3.Error,
        zipfile.BadZipFile,
    ) as error:
        print(
            f"macOS reverse-version readback observation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
