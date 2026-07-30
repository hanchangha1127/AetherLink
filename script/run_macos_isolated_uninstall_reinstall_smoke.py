#!/usr/bin/env python3
"""Exercise exact-path macOS uninstall and same-build reinstall in a temporary HOME."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
from typing import Callable, Sequence
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
RESULT_SCOPE = "same-host-per-user-isolated-uninstall-reinstall-v1"
ARCHIVE_READBACK_MODE = "archive-only-no-current-source"


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
            f"{version.build_number}-isolated-uninstall-reinstall-v1.json"
        )
    )


def verify_archive_only_readback(
    archive_dir: Path,
    *,
    runner: Callable[..., object] = engine.run_checked,
) -> None:
    runner(
        [
            sys.executable,
            "-B",
            str(engine.ARCHIVE_CHECKER),
            "--archive-dir",
            str(archive_dir.resolve()),
            "--no-current-source",
        ],
        cwd=ROOT,
    )


def _physical_directory(path: Path, *, label: str) -> None:
    if not path.is_absolute():
        raise engine.LifecycleSmokeError(f"{label} must be absolute")
    try:
        status = path.lstat()
        physical = path.resolve(strict=True)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot inspect {label}: {error}"
        ) from error
    if (
        stat.S_ISLNK(status.st_mode)
        or not stat.S_ISDIR(status.st_mode)
        or physical != path
    ):
        raise engine.LifecycleSmokeError(
            f"{label} must be a physical directory"
        )


def validate_uninstall_target(
    *,
    temporary_root: Path,
    isolated_home: Path,
    app_path: Path,
) -> None:
    _physical_directory(temporary_root, label="temporary root")
    _physical_directory(isolated_home, label="isolated HOME")
    applications = isolated_home / "Applications"
    _physical_directory(applications, label="isolated Applications")
    expected_home = temporary_root / "home"
    expected_app = applications / installed.APP_RELATIVE_PATH
    if isolated_home != expected_home or app_path != expected_app:
        raise engine.LifecycleSmokeError(
            "uninstall target must be the exact temporary HOME app path"
        )
    if app_path.is_symlink() or not app_path.is_dir():
        raise engine.LifecycleSmokeError(
            "uninstall target must be a real installed app directory"
        )


def install_exact_temporary_app(
    source: Path,
    *,
    temporary_root: Path,
    isolated_home: Path,
    app_path: Path,
    command_runner: Callable[..., object] = engine.run_checked,
) -> None:
    _physical_directory(temporary_root, label="temporary root")
    _physical_directory(isolated_home, label="isolated HOME")
    applications = isolated_home / "Applications"
    expected_app = applications / installed.APP_RELATIVE_PATH
    if (
        isolated_home != temporary_root / "home"
        or app_path != expected_app
    ):
        raise engine.LifecycleSmokeError(
            "install target must be the exact temporary HOME app path"
        )
    if source.is_symlink() or not source.is_dir():
        raise engine.LifecycleSmokeError(
            "install source must be a real app directory"
        )
    if applications.exists() or applications.is_symlink():
        _physical_directory(
            applications,
            label="isolated Applications",
        )
    else:
        applications.mkdir(mode=0o700)
        _physical_directory(
            applications,
            label="isolated Applications",
        )
    if app_path.exists() or app_path.is_symlink():
        raise engine.LifecycleSmokeError(
            "install destination already exists"
        )
    if (
        not installed.DITTO.is_file()
        or not os.access(installed.DITTO, os.X_OK)
    ):
        raise engine.LifecycleSmokeError("ditto is unavailable")
    command_runner(
        [str(installed.DITTO), str(source), str(app_path)]
    )
    if app_path.is_symlink() or not app_path.is_dir():
        raise engine.LifecycleSmokeError(
            "ditto did not create the exact temporary app directory"
        )


def assert_exact_app_not_running(
    app_path: Path,
    *,
    lister: Callable[
        [], tuple[installed.RunningApplication, ...]
    ]
    | None = None,
) -> None:
    resolved_lister = lister or installed.list_bundle_applications
    executable = app_path / installed.EXECUTABLE_RELATIVE_PATH
    running = [
        application
        for application in resolved_lister()
        if installed.application_matches_executable(
            application,
            executable,
        )
    ]
    if running:
        raise engine.LifecycleSmokeError(
            "exact temporary app is still running before uninstall"
        )


def remove_exact_installed_app(
    *,
    temporary_root: Path,
    isolated_home: Path,
    app_path: Path,
    release: engine.ReleaseInputs,
    expected_tree: installed.AppTreeEvidence,
    lister: Callable[
        [], tuple[installed.RunningApplication, ...]
    ]
    | None = None,
    remover: Callable[[Path], None] = shutil.rmtree,
) -> None:
    validate_uninstall_target(
        temporary_root=temporary_root,
        isolated_home=isolated_home,
        app_path=app_path,
    )
    observed_tree = installed.app_tree_evidence(app_path, release)
    if observed_tree != expected_tree:
        raise engine.LifecycleSmokeError(
            "uninstall target differs from the installed release tree"
        )
    assert_exact_app_not_running(app_path, lister=lister)
    remover(app_path)
    if app_path.exists() or app_path.is_symlink():
        raise engine.LifecycleSmokeError(
            "exact temporary app remained after uninstall"
        )
    _physical_directory(temporary_root, label="temporary root")
    _physical_directory(isolated_home, label="isolated HOME")
    _physical_directory(
        isolated_home / "Applications",
        label="isolated Applications",
    )


def changed_state_paths(
    before: dict[str, installed.FileIdentity],
    after: dict[str, installed.FileIdentity],
) -> list[str]:
    return sorted(
        set(before)
        ^ set(after)
        | {
            path
            for path in set(before) & set(after)
            if before[path] != after[path]
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
    verify_archive_only_readback(archive_dir)
    release = recovery.load_release_inputs(
        archive_dir,
        verify_readback=False,
        version=version,
    )
    preexisting_applications = installed.list_bundle_applications()

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-uninstall-reinstall-"
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
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
        ):
            path.mkdir(mode=0o700)
        installed_app = (
            isolated_home / "Applications" / installed.APP_RELATIVE_PATH
        )
        install_exact_temporary_app(
            extracted_app,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
        )
        app_metadata = recovery.verify_packaged_app(
            installed_app,
            release,
            version=version,
        )
        initial_tree = installed.app_tree_evidence(
            installed_app,
            release,
        )
        if initial_tree != extracted_tree:
            raise engine.LifecycleSmokeError(
                "initial installed app differs from the release tree"
            )

        identity_file = isolated_state / "runtime-identity.json"
        environment = installed.isolated_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
        )
        application_support = (
            isolated_home / "Library/Application Support/AetherLink"
        )
        if application_support.exists() or application_support.is_symlink():
            raise engine.LifecycleSmokeError(
                "isolated runtime state existed before initial launch"
            )

        first_pid, first_run = installed.run_launch_services_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        initial_sqlite = installed.sqlite_state_evidence(
            application_support
        )
        initial_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=release,
            expected_tree=initial_tree,
        )
        after_first_uninstall_sqlite = installed.sqlite_state_evidence(
            application_support
        )
        after_first_uninstall_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if (
            after_first_uninstall_sqlite != initial_sqlite
            or after_first_uninstall_state != initial_state
        ):
            raise engine.LifecycleSmokeError(
                "isolated runtime state changed during app removal: "
                f"{changed_state_paths(initial_state, after_first_uninstall_state)!r}"
            )

        install_exact_temporary_app(
            extracted_app,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
        )
        recovery.verify_packaged_app(
            installed_app,
            release,
            version=version,
        )
        reinstalled_tree = installed.app_tree_evidence(
            installed_app,
            release,
        )
        if reinstalled_tree != initial_tree:
            raise engine.LifecycleSmokeError(
                "same-build reinstall differs from the initial app tree"
            )
        second_pid, second_run = installed.run_launch_services_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if second_pid == first_pid:
            raise engine.LifecycleSmokeError(
                "same-build reinstall reused the initial process identifier"
            )
        reinstalled_sqlite = installed.sqlite_state_evidence(
            application_support
        )
        reinstalled_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if reinstalled_sqlite != initial_sqlite or reinstalled_state != initial_state:
            raise engine.LifecycleSmokeError(
                "isolated state changed after same-build reinstall: "
                f"{changed_state_paths(initial_state, reinstalled_state)!r}"
            )

        remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=release,
            expected_tree=reinstalled_tree,
        )
        final_sqlite = installed.sqlite_state_evidence(application_support)
        final_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if final_sqlite != initial_sqlite or final_state != initial_state:
            raise engine.LifecycleSmokeError(
                "isolated state changed during final app removal: "
                f"{changed_state_paths(initial_state, final_state)!r}"
            )

        installed.assert_preexisting_applications_preserved(
            preexisting_applications
        )
        result = {
            "app": app_metadata,
            "archiveReadback": {
                "currentSourceCompared": False,
                "mode": ARCHIVE_READBACK_MODE,
                "status": "passed",
            },
            "installation": {
                "copyTool": "ditto",
                "initialTree": initial_tree.record(),
                "installedRelativePath": "Applications/AetherLink.app",
                "reinstallTreeMatchesInitial": True,
            },
            "isolation": {
                "preexistingBundleApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "launchServices": {
                "distinctProcessIdentifiers": True,
                "runs": [first_run, second_run],
            },
            "limitations": [
                "same-host-per-user-temporary-home-only",
                "same-build-reinstall-not-upgrade-or-rollback",
                "application-support-retained-no-automatic-data-cleanup",
                "post-archive-harness-not-build-input-member",
                "not-device-provider-network-or-ui-evidence",
            ],
            "release": {
                "archiveSha256": release.archive_sha256,
                "manifestSha256": release.manifest_sha256,
                "releaseId": release_id,
            },
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "scope": RESULT_SCOPE,
            "state": {
                "applicationSupportPreservedAcrossRemovalAndReinstall": True,
                "expectedSQLiteFiles": list(installed.EXPECTED_SQLITE_FILES),
                "runtimeIdentityFilePresent": identity_file.is_file(),
                "sqlite": [
                    evidence.record() for evidence in initial_sqlite
                ],
            },
            "status": "passed",
            "uninstall": {
                "appAbsentAfterEachRemoval": True,
                "applicationSupportCleanupPerformed": False,
                "exactTemporaryAppPathOnly": True,
                "removalCount": 2,
                "removalMethod": "python-shutil-rmtree",
            },
        }

    installed.publish_result(result_path, result)
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
        result = execute(
            archive_dir=arguments.archive_dir,
            result_path=arguments.result,
            readiness_timeout_seconds=arguments.readiness_timeout_seconds,
            observation_seconds=arguments.observation_seconds,
            termination_timeout_seconds=arguments.termination_timeout_seconds,
        )
    except KeyboardInterrupt:
        print(
            "macOS isolated uninstall/reinstall smoke interrupted.",
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
            f"macOS isolated uninstall/reinstall smoke failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "macOS isolated uninstall/reinstall smoke passed: "
        f"{result['release']['releaseId']}; "
        "app removal and same-build reinstall preserved isolated state."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
