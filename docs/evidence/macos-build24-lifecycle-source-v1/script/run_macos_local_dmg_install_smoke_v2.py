#!/usr/bin/env python3
"""Qualify a snapshot-bound local DMG mount/copy/launch rehearsal."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import sys
import tempfile
from typing import Sequence

if __package__:
    from script import run_macos_isolated_upgrade_smoke as upgrade
    from script import run_macos_local_dmg_install_smoke as base
else:
    import run_macos_isolated_upgrade_smoke as upgrade
    import run_macos_local_dmg_install_smoke as base


engine = base.engine
installed = base.installed
recovery = base.recovery
LocalDMGSmokeError = base.LocalDMGSmokeError
ROOT = base.ROOT
RESULT_SCHEMA_VERSION = 2
RESULT_SCOPE = "same-host-per-user-ephemeral-local-dmg-install-v2"
ARCHIVE_READBACK_MODE = "archive-only-no-current-source"
LOWERCASE_HEX = frozenset("0123456789abcdef")


def current_release() -> recovery.ReleaseVersion:
    return base.current_release()


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return base.release_id_for(version)


def default_archive_dir() -> Path:
    return base.default_archive_dir()


def default_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-local-dmg-install-v2.json"
        )
    )


def require_result_outside_archive(
    result_path: Path,
    archive_dir: Path,
) -> None:
    result = result_path.resolve(strict=False)
    archive = archive_dir.resolve(strict=False)
    if result == archive or archive in result.parents:
        raise LocalDMGSmokeError(
            "local DMG result must remain outside the release archive"
        )


def validated_snapshot_files(
    *,
    release: engine.ReleaseInputs,
    release_id: str,
    snapshot_files: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    expected_names = {
        f"{release_id}.zip",
        f"{release_id}.manifest.json",
        f"{release_id}.zip.sha256",
    }
    if (
        type(snapshot_files) is not dict
        or set(snapshot_files) != expected_names
    ):
        raise LocalDMGSmokeError(
            "local DMG release snapshot inventory is invalid"
        )

    validated: dict[str, dict[str, object]] = {}
    for name in sorted(expected_names):
        record = snapshot_files[name]
        if type(record) is not dict or set(record) != {"sha256", "size"}:
            raise LocalDMGSmokeError(
                "local DMG release snapshot record is invalid"
            )
        sha256 = record["sha256"]
        size = record["size"]
        if (
            type(sha256) is not str
            or len(sha256) != 64
            or any(character not in LOWERCASE_HEX for character in sha256)
            or type(size) is not int
            or size <= 0
        ):
            raise LocalDMGSmokeError(
                "local DMG release snapshot identity is invalid"
            )
        validated[name] = {
            "sha256": sha256,
            "size": size,
        }

    if (
        validated[f"{release_id}.zip"]["sha256"]
        != release.archive_sha256
        or validated[f"{release_id}.manifest.json"]["sha256"]
        != release.manifest_sha256
    ):
        raise LocalDMGSmokeError(
            "local DMG release snapshot differs from loaded inputs"
        )
    return validated


def build_result(
    *,
    release: engine.ReleaseInputs,
    release_id: str,
    app_tree: installed.AppTreeEvidence,
    runs: Sequence[dict[str, object]],
    sqlite_evidence: Sequence[installed.SQLiteStateEvidence],
    runtime_identity_present: bool,
    snapshot_files: dict[str, dict[str, object]],
) -> dict[str, object]:
    if runtime_identity_present is not True:
        raise LocalDMGSmokeError(
            "local DMG runtime identity was not created"
        )
    validated_files = validated_snapshot_files(
        release=release,
        release_id=release_id,
        snapshot_files=snapshot_files,
    )
    result = base.build_result(
        release=release,
        release_id=release_id,
        app_tree=app_tree,
        runs=runs,
        sqlite_evidence=sqlite_evidence,
        runtime_identity_present=True,
    )
    result["archiveReadback"] = {
        "currentSourceCompared": False,
        "mode": ARCHIVE_READBACK_MODE,
        "readbackAndExerciseSameSnapshot": True,
        "snapshotFiles": validated_files,
        "snapshotFilesUnchangedAfterExercise": True,
        "status": "passed",
    }
    result["schemaVersion"] = RESULT_SCHEMA_VERSION
    result["scope"] = RESULT_SCOPE
    return result


def publish_result(path: Path, result: dict[str, object]) -> None:
    base.publish_result(path, result)


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
    require_result_outside_archive(result_path, archive_dir)

    version = current_release()
    release_id = release_id_for(version)
    preexisting_applications = installed.list_bundle_applications()

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-local-dmg-install-v2-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
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
        release_tree = installed.app_tree_evidence(extracted_app, release)

        staging_root = temporary_root / "dmg-staging"
        staged_app = base.stage_dmg_root(extracted_app, staging_root)
        recovery.verify_packaged_app(
            staged_app,
            release,
            version=version,
        )
        if installed.app_tree_evidence(staged_app, release) != release_tree:
            raise LocalDMGSmokeError(
                "staged local DMG app differs from release"
            )

        dmg_path = temporary_root / "local-image.dmg"
        base.run_bounded_command(
            base.create_dmg_command(staging_root, dmg_path)
        )
        base.run_bounded_command(base.verify_dmg_command(dmg_path))

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        mountpoint = temporary_root / "mount"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
            mountpoint,
        ):
            path.mkdir(mode=0o700)
        installed_app = (
            isolated_home / "Applications" / installed.APP_RELATIVE_PATH
        )
        copied_tree = base.attach_copy_detach(
            dmg_path=dmg_path,
            mountpoint=mountpoint,
            copier=lambda: base.copy_from_mounted_dmg(
                mountpoint=mountpoint,
                installed_app=installed_app,
                release=release,
                version=version,
                expected_tree=release_tree,
            ),
        )
        if copied_tree != release_tree:
            raise LocalDMGSmokeError("local DMG installed tree differs")

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
        if (
            application_support.exists()
            or application_support.is_symlink()
            or identity_file.exists()
            or identity_file.is_symlink()
        ):
            raise LocalDMGSmokeError(
                "clean-HOME state existed before launch"
            )

        first_pid, first_run = installed.run_launch_services_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        first_tree = installed.app_tree_evidence(installed_app, release)
        first_sqlite = installed.sqlite_state_evidence(application_support)
        first_state = installed.state_file_records(
            application_support,
            identity_file,
        )

        second_pid, second_run = installed.run_launch_services_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if first_pid == second_pid:
            raise LocalDMGSmokeError(
                "LaunchServices reused a process identifier"
            )
        second_tree = installed.app_tree_evidence(installed_app, release)
        second_sqlite = installed.sqlite_state_evidence(application_support)
        second_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if first_tree != release_tree or second_tree != release_tree:
            raise LocalDMGSmokeError(
                "installed app tree changed during launch"
            )
        if first_sqlite != second_sqlite or first_state != second_state:
            raise LocalDMGSmokeError(
                "installed state changed across relaunch"
            )

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
            app_tree=copied_tree,
            runs=(first_run, second_run),
            sqlite_evidence=first_sqlite,
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
    except (
        LocalDMGSmokeError,
        engine.LifecycleSmokeError,
        OSError,
        plistlib.InvalidFileException,
        ValueError,
    ):
        print("Local DMG install v2 smoke failed.", file=sys.stderr)
        return 1
    print("Local DMG install v2 smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
