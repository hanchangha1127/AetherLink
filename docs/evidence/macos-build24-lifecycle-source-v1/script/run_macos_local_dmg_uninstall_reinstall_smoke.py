#!/usr/bin/env python3
"""Exercise uninstall and reinstall from one snapshot-bound local DMG."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Callable, Iterator, Sequence

if __package__:
    from script import run_macos_isolated_uninstall_reinstall_smoke as uninstall
    from script import run_macos_local_dmg_install_smoke_v2 as dmg
else:
    import run_macos_isolated_uninstall_reinstall_smoke as uninstall
    import run_macos_local_dmg_install_smoke_v2 as dmg


base = dmg.base
engine = dmg.engine
installed = dmg.installed
recovery = dmg.recovery
upgrade = dmg.upgrade
LocalDMGSmokeError = dmg.LocalDMGSmokeError
ROOT = dmg.ROOT
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-v1"
)
LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "same-created-dmg-image-remount-only",
    "application-support-retained-no-automatic-data-cleanup",
    "post-archive-harness-not-build-input-member",
    "not-finder-system-applications-quarantine-or-gatekeeper-evidence",
    "not-signed-notarized-stapled-or-distribution-evidence",
    (
        "not-clean-machine-upgrade-rollback-device-provider-network-ui-"
        "accessibility-production-or-security-evidence"
    ),
)


def current_release() -> recovery.ReleaseVersion:
    return dmg.current_release()


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return dmg.release_id_for(version)


def default_archive_dir() -> Path:
    return dmg.default_archive_dir()


def default_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-local-dmg-uninstall-reinstall-v1.json"
        )
    )


def require_result_outside_archive(
    result_path: Path,
    archive_dir: Path,
) -> None:
    dmg.require_result_outside_archive(result_path, archive_dir)


def image_identity(path: Path) -> installed.FileIdentity:
    if path.is_symlink() or not path.is_file():
        raise LocalDMGSmokeError("local DMG image must be a regular file")
    return installed.stable_regular_file_identity(path)


def require_same_image(
    path: Path,
    expected: installed.FileIdentity,
) -> None:
    if image_identity(path) != expected:
        raise LocalDMGSmokeError(
            "local DMG image changed before reinstall completed"
        )


def changed_state_paths(
    before: dict[str, installed.FileIdentity],
    after: dict[str, installed.FileIdentity],
) -> list[str]:
    return uninstall.changed_state_paths(before, after)


def require_unchanged_state(
    *,
    label: str,
    expected_sqlite: Sequence[installed.SQLiteStateEvidence],
    observed_sqlite: Sequence[installed.SQLiteStateEvidence],
    expected_files: dict[str, installed.FileIdentity],
    observed_files: dict[str, installed.FileIdentity],
) -> None:
    if (
        tuple(observed_sqlite) != tuple(expected_sqlite)
        or observed_files != expected_files
    ):
        raise LocalDMGSmokeError(
            f"isolated runtime state changed {label}: "
            f"{changed_state_paths(expected_files, observed_files)!r}"
        )


def copy_same_image(
    *,
    dmg_path: Path,
    mountpoint: Path,
    temporary_root: Path,
    isolated_home: Path,
    installed_app: Path,
    release: engine.ReleaseInputs,
    version: recovery.ReleaseVersion,
    expected_tree: installed.AppTreeEvidence,
) -> installed.AppTreeEvidence:
    return attach_copy_detach(
        dmg_path=dmg_path,
        mountpoint=mountpoint,
        copier=lambda: copy_from_mounted_dmg(
            mountpoint=mountpoint,
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            installed_app=installed_app,
            release=release,
            version=version,
            expected_tree=expected_tree,
        ),
    )


def copy_from_mounted_dmg(
    *,
    mountpoint: Path,
    temporary_root: Path,
    isolated_home: Path,
    installed_app: Path,
    release: engine.ReleaseInputs,
    version: recovery.ReleaseVersion,
    expected_tree: installed.AppTreeEvidence,
) -> installed.AppTreeEvidence:
    mounted_app = base.verify_mounted_layout(mountpoint)
    recovery.verify_packaged_app(
        mounted_app,
        release,
        version=version,
    )
    mounted_tree = installed.app_tree_evidence(mounted_app, release)
    if mounted_tree != expected_tree:
        raise LocalDMGSmokeError(
            "mounted local DMG app differs from release"
        )
    uninstall.install_exact_temporary_app(
        mounted_app,
        temporary_root=temporary_root,
        isolated_home=isolated_home,
        app_path=installed_app,
    )
    recovery.verify_packaged_app(
        installed_app,
        release,
        version=version,
    )
    copied_tree = installed.app_tree_evidence(installed_app, release)
    if copied_tree != mounted_tree:
        raise LocalDMGSmokeError(
            "installed local DMG app differs after copy"
        )
    return copied_tree


def mounted_image_device(
    payload: bytes,
    *,
    dmg_path: Path,
) -> str | None:
    root = base._load_plist(payload)
    images = root.get("images")
    if not isinstance(images, list) or len(images) > 128:
        raise LocalDMGSmokeError("local DMG info plist is invalid")
    matches: list[tuple[list[str], list[str]]] = []
    for image in images:
        if not isinstance(image, dict) or any(
            not isinstance(key, str) for key in image
        ):
            raise LocalDMGSmokeError("local DMG info image is invalid")
        if image.get("image-path") != str(dmg_path):
            continue
        rows = image.get("system-entities")
        if not isinstance(rows, list) or not rows or len(rows) > 32:
            raise LocalDMGSmokeError(
                "local DMG image entity list is invalid"
            )
        devices: list[str] = []
        mounted_devices: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or any(
                not isinstance(key, str) for key in row
            ):
                raise LocalDMGSmokeError(
                    "local DMG image entity is invalid"
                )
            device = row.get("dev-entry")
            if device is not None:
                base.detach_dmg_command(device)
                if device in devices:
                    raise LocalDMGSmokeError(
                        "local DMG image device is duplicated"
                    )
                devices.append(device)
            mount = row.get("mount-point")
            if mount is not None:
                if (
                    not isinstance(mount, str)
                    or "\x00" in mount
                    or device is None
                ):
                    raise LocalDMGSmokeError(
                        "local DMG mounted image entity is invalid"
                    )
                mounted_devices.append(device)
        if not devices:
            raise LocalDMGSmokeError(
                "local DMG image contains no device identity"
            )
        matches.append((devices, mounted_devices))
    if len(matches) > 1:
        raise LocalDMGSmokeError(
            "local DMG image is mounted more than once"
        )
    if not matches:
        return None
    devices, mounted_devices = matches[0]
    if len(mounted_devices) == 1:
        return mounted_devices[0]
    return devices[0]


def read_mounted_image_device(dmg_path: Path) -> str | None:
    info = base.run_bounded_command(base.info_dmg_command())
    return mounted_image_device(info.stdout, dmg_path=dmg_path)


def recover_unmount(
    *,
    dmg_path: Path,
    mountpoint: Path,
) -> None:
    device = read_mounted_image_device(dmg_path)
    if device is not None:
        base.run_bounded_command(base.detach_dmg_command(device))
    elif (
        os.path.ismount(mountpoint)
        or (mountpoint / installed.APP_RELATIVE_PATH).exists()
        or (mountpoint / installed.APP_RELATIVE_PATH).is_symlink()
        or (mountpoint / "Applications").exists()
        or (mountpoint / "Applications").is_symlink()
    ):
        base.run_bounded_command(
            base.detach_mountpoint_command(mountpoint)
        )
    base.wait_for_unmounted(mountpoint)
    if read_mounted_image_device(dmg_path) is not None:
        raise LocalDMGSmokeError(
            "local DMG image remained mounted after cleanup"
        )


def attach_copy_detach(
    *,
    dmg_path: Path,
    mountpoint: Path,
    copier: Callable[[], installed.AppTreeEvidence],
) -> installed.AppTreeEvidence:
    if read_mounted_image_device(dmg_path) is not None:
        raise LocalDMGSmokeError(
            "local DMG image was mounted before attach"
        )
    device: str | None = None
    result: installed.AppTreeEvidence | None = None
    primary_error: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    try:
        attached = base.run_bounded_command(
            base.attach_dmg_command(dmg_path, mountpoint)
        )
        device = base.parse_attach_plist(
            attached.stdout,
            expected_mountpoint=mountpoint,
        ).device
        result = copier()
    except BaseException as error:
        primary_error = error
    finally:
        if device is not None:
            try:
                base.run_bounded_command(
                    base.detach_dmg_command(device)
                )
            except BaseException as error:
                cleanup_errors.append(error)
        try:
            recover_unmount(
                dmg_path=dmg_path,
                mountpoint=mountpoint,
            )
        except BaseException as error:
            cleanup_errors.append(error)
    for cleanup_error in cleanup_errors:
        if isinstance(cleanup_error, (KeyboardInterrupt, SystemExit)):
            raise cleanup_error
    if cleanup_errors:
        raise LocalDMGSmokeError(
            "local DMG cleanup failed"
        ) from cleanup_errors[0]
    if primary_error is not None:
        raise primary_error
    if result is None:
        raise LocalDMGSmokeError(
            "local DMG copy did not produce evidence"
        )
    return result


@contextmanager
def isolated_dmg_root(
    *,
    termination_timeout_seconds: float,
) -> Iterator[Path]:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="aetherlink-macos-local-dmg-uninstall-reinstall-v1-"
        )
    ).resolve()
    try:
        yield temporary_root
    finally:
        cleanup_error: BaseException | None = None
        try:
            upgrade.cleanup_exact_temporary_applications(
                temporary_root,
                termination_timeout_seconds=termination_timeout_seconds,
            )
        except BaseException as error:
            cleanup_error = error
        for name in ("mount-initial", "mount-reinstall"):
            try:
                recover_unmount(
                    dmg_path=temporary_root / "local-image.dmg",
                    mountpoint=temporary_root / name,
                )
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
        if cleanup_error is not None:
            if isinstance(cleanup_error, (KeyboardInterrupt, SystemExit)):
                raise cleanup_error
            raise LocalDMGSmokeError(
                "local DMG cleanup failed; diagnostic root retained"
            ) from cleanup_error
        try:
            shutil.rmtree(temporary_root)
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise LocalDMGSmokeError(
                "local DMG cleanup incomplete; diagnostic root may remain"
            ) from error


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
    validated = dmg.build_result(
        release=release,
        release_id=release_id,
        app_tree=app_tree,
        runs=runs,
        sqlite_evidence=sqlite_evidence,
        runtime_identity_present=runtime_identity_present,
        snapshot_files=snapshot_files,
    )
    required_records = (
        "archiveReadback",
        "image",
        "installation",
        "isolation",
        "launchServices",
        "release",
        "state",
    )
    if any(type(validated[key]) is not dict for key in required_records):
        raise LocalDMGSmokeError("local DMG base result shape is invalid")
    installation = validated["installation"]
    state = validated["state"]
    return {
        "archiveReadback": validated["archiveReadback"],
        "image": {
            "ephemeral": True,
            "filesystem": "HFS+",
            "format": "UDZO",
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
            "tree": installation["tree"],
        },
        "isolation": validated["isolation"],
        "launchServices": {
            "distinctProcessIdentifiers": True,
            "exactInstalledBundlePerCycle": True,
            "noExactTemporaryAppRemaining": True,
            "runs": validated["launchServices"]["runs"],
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
        "release": validated["release"],
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "state": {
            "applicationSupportPreservedAcrossRemovalAndReinstall": True,
            "databaseCount": state["databaseCount"],
            "emptyRuntimeChatVerified": state["emptyRuntimeChatVerified"],
            "integrityChecks": state["integrityChecks"],
            "regularFileBytesAndModesUnchanged": True,
            "runtimeIdentityFilePresent": state[
                "runtimeIdentityFilePresent"
            ],
            "sqlite": state["sqlite"],
            "stableAcrossRemovalAndReinstall": True,
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
    dmg.publish_result(path, result)


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

    with isolated_dmg_root(
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
        expected_image_identity = image_identity(dmg_path)

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        initial_mountpoint = temporary_root / "mount-initial"
        reinstall_mountpoint = temporary_root / "mount-reinstall"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
            initial_mountpoint,
            reinstall_mountpoint,
        ):
            path.mkdir(mode=0o700)
        installed_app = (
            isolated_home / "Applications" / installed.APP_RELATIVE_PATH
        )

        initial_tree = copy_same_image(
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
                "initial local DMG install differs from release"
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
        if (
            application_support.exists()
            or application_support.is_symlink()
            or identity_file.exists()
            or identity_file.is_symlink()
        ):
            raise LocalDMGSmokeError(
                "clean-HOME state existed before initial launch"
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
        uninstall.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=release,
            expected_tree=initial_tree,
        )
        require_unchanged_state(
            label="during initial removal",
            expected_sqlite=initial_sqlite,
            observed_sqlite=installed.sqlite_state_evidence(
                application_support
            ),
            expected_files=initial_state,
            observed_files=installed.state_file_records(
                application_support,
                identity_file,
            ),
        )

        require_same_image(dmg_path, expected_image_identity)
        reinstalled_tree = copy_same_image(
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
                "same-image reinstall differs from initial app tree"
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
            raise LocalDMGSmokeError(
                "same-image reinstall reused the initial process identifier"
            )
        require_unchanged_state(
            label="after same-image reinstall",
            expected_sqlite=initial_sqlite,
            observed_sqlite=installed.sqlite_state_evidence(
                application_support
            ),
            expected_files=initial_state,
            observed_files=installed.state_file_records(
                application_support,
                identity_file,
            ),
        )

        uninstall.remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            release=release,
            expected_tree=reinstalled_tree,
        )
        require_unchanged_state(
            label="during final removal",
            expected_sqlite=initial_sqlite,
            observed_sqlite=installed.sqlite_state_evidence(
                application_support
            ),
            expected_files=initial_state,
            observed_files=installed.state_file_records(
                application_support,
                identity_file,
            ),
        )

        require_same_image(dmg_path, expected_image_identity)
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
            sqlite_evidence=initial_sqlite,
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
        sqlite3.Error,
        ValueError,
    ):
        print(
            "Local DMG uninstall/reinstall v1 smoke failed.",
            file=sys.stderr,
        )
        return 1
    print("Local DMG uninstall/reinstall v1 smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
