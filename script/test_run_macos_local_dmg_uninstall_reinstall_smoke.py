#!/usr/bin/env python3
"""Tests for the snapshot-bound local-DMG uninstall/reinstall smoke."""

from __future__ import annotations

import copy
from contextlib import contextmanager, ExitStack
import io
from pathlib import Path
import plistlib
import shutil
import tempfile
from typing import Iterator
import unittest
from unittest.mock import patch

from script import run_macos_local_dmg_uninstall_reinstall_smoke as smoke
from script.test_run_macos_local_dmg_install_smoke import (
    launch_record,
    sqlite_evidence,
)


class LocalDMGUninstallReinstallSmokeTests(unittest.TestCase):
    def release_inputs(
        self,
        root: Path,
        release_id: str = "build-987",
    ) -> smoke.engine.ReleaseInputs:
        return smoke.engine.ReleaseInputs(
            archive_dir=root,
            archive_path=root / f"{release_id}.zip",
            manifest_path=root / f"{release_id}.manifest.json",
            checksum_path=root / f"{release_id}.zip.sha256",
            archive_sha256="a" * 64,
            manifest_sha256="b" * 64,
            manifest={},
        )

    def snapshot_files(
        self,
        release_id: str = "build-987",
    ) -> dict[str, dict[str, object]]:
        return {
            f"{release_id}.manifest.json": {
                "sha256": "b" * 64,
                "size": 200,
            },
            f"{release_id}.zip": {
                "sha256": "a" * 64,
                "size": 300,
            },
            f"{release_id}.zip.sha256": {
                "sha256": "c" * 64,
                "size": 100,
            },
        }

    def app_tree(self, sha256: str = "d" * 64) -> smoke.installed.AppTreeEvidence:
        return smoke.installed.AppTreeEvidence(
            digest_algorithm="sha256-test-v1",
            file_count=3,
            sha256=sha256,
            total_bytes=123,
        )

    def build_result(
        self,
        root: Path,
        *,
        runtime_identity_present: bool = True,
        snapshot_files: dict[str, dict[str, object]] | None = None,
    ) -> dict[str, object]:
        return smoke.build_result(
            release=self.release_inputs(root),
            release_id="build-987",
            app_tree=self.app_tree(),
            runs=(launch_record(1), launch_record(2)),
            sqlite_evidence=sqlite_evidence(),
            runtime_identity_present=runtime_identity_present,
            snapshot_files=(
                self.snapshot_files()
                if snapshot_files is None
                else snapshot_files
            ),
        )

    def create_app(self, app_path: Path) -> None:
        executable = app_path / smoke.installed.EXECUTABLE_RELATIVE_PATH
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture-executable")
        executable.chmod(0o755)
        resource = app_path / "Contents/Resources/fixture.txt"
        resource.parent.mkdir(parents=True)
        resource.write_bytes(b"fixture-resource")
        resource.chmod(0o644)

    def release_for_app(
        self,
        app_path: Path,
    ) -> smoke.engine.ReleaseInputs:
        members = [
            {
                "mode": f"0{identity.mode:03o}",
                "path": member,
                "sha256": identity.sha256,
                "size": identity.size,
            }
            for member, identity in smoke.installed.app_file_records(
                app_path
            ).items()
        ]
        release = self.release_inputs(app_path.parent)
        return smoke.engine.ReleaseInputs(
            archive_dir=release.archive_dir,
            archive_path=release.archive_path,
            manifest_path=release.manifest_path,
            checksum_path=release.checksum_path,
            archive_sha256=release.archive_sha256,
            manifest_sha256=release.manifest_sha256,
            manifest={"members": members},
        )

    def test_result_is_closed_to_same_image_uninstall_reinstall_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result = self.build_result(Path(temporary_name))

        self.assertEqual(
            set(result),
            {
                "archiveReadback",
                "image",
                "installation",
                "isolation",
                "launchServices",
                "limitations",
                "mount",
                "release",
                "schemaVersion",
                "scope",
                "state",
                "status",
                "uninstall",
            },
        )
        self.assertEqual(result["schemaVersion"], 1)
        self.assertEqual(result["scope"], smoke.RESULT_SCOPE)
        self.assertEqual(
            result["image"],
            {
                "ephemeral": True,
                "filesystem": "HFS+",
                "format": "UDZO",
                "retained": False,
                "sameImageBytesUsedForBothInstalls": True,
                "verified": True,
            },
        )
        self.assertEqual(result["installation"]["installCount"], 2)
        self.assertEqual(
            result["installation"]["origin"],
            "same-ephemeral-local-dmg",
        )
        self.assertEqual(
            result["mount"],
            {
                "cycleCount": 2,
                "detachedBeforeEachLaunch": True,
                "exactFreshMountpointPerInstall": True,
                "nobrowse": True,
                "oneMountedEntityPerInstall": True,
                "readOnly": True,
                "unmountedAfterEachCopy": True,
            },
        )
        self.assertEqual(result["uninstall"]["removalCount"], 2)
        self.assertIs(
            result["state"]["runtimeIdentityFilePresent"],
            True,
        )
        self.assertEqual(
            result["archiveReadback"]["snapshotFiles"],
            self.snapshot_files(),
        )

    def test_result_rejects_exact_type_and_snapshot_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            for value in (False, 0, 1, None):
                with self.subTest(runtime_identity=value):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        self.build_result(
                            root,
                            runtime_identity_present=value,  # type: ignore[arg-type]
                        )

            baseline = self.snapshot_files()
            mutations: list[dict[str, dict[str, object]]] = []
            missing = copy.deepcopy(baseline)
            missing.pop("build-987.zip.sha256")
            mutations.append(missing)
            boolean_size = copy.deepcopy(baseline)
            boolean_size["build-987.zip"]["size"] = True
            mutations.append(boolean_size)
            extra = copy.deepcopy(baseline)
            extra["extra"] = {"sha256": "e" * 64, "size": 1}
            mutations.append(extra)
            wrong_archive = copy.deepcopy(baseline)
            wrong_archive["build-987.zip"]["sha256"] = "e" * 64
            mutations.append(wrong_archive)
            for mutation in mutations:
                with self.subTest(snapshot=mutation):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        self.build_result(
                            root,
                            snapshot_files=mutation,
                        )

    def test_default_result_and_archive_boundary_track_release(self) -> None:
        version = smoke.recovery.ReleaseVersion(
            build_number=987,
            marketing_version="9.8.7",
            semantic_version=(9, 8, 7),
        )
        with patch.object(smoke, "current_release", return_value=version):
            self.assertEqual(
                smoke.default_result_path(),
                smoke.ROOT
                / "dist/lifecycle/"
                "macos-packaged-app-build-987-"
                "local-dmg-uninstall-reinstall-v1.json",
            )

        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            archive = root / "archive"
            archive.mkdir()
            for result in (archive, archive / "result.json"):
                with self.subTest(result=result):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.require_result_outside_archive(result, archive)
            smoke.require_result_outside_archive(
                root / "result.json",
                archive,
            )

    def test_image_identity_rejects_symlink_and_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            image = root / "image.dmg"
            image.write_bytes(b"first image")
            expected = smoke.image_identity(image)
            smoke.require_same_image(image, expected)

            image.write_bytes(b"changed image")
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.require_same_image(image, expected)

            image.unlink()
            target = root / "target.dmg"
            target.write_bytes(b"first image")
            image.symlink_to(target)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.image_identity(image)

    def test_unexpected_attach_mount_is_detached_by_image_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name).resolve()
            image = root / "image.dmg"
            image.write_bytes(b"fixture image")
            mountpoint = root / "expected-mount"
            mountpoint.mkdir()
            wrong_mount = root / "unexpected-mount"
            entities = [
                {"dev-entry": "/dev/disk42"},
                {
                    "dev-entry": "/dev/disk42s1",
                    "mount-point": str(wrong_mount),
                },
            ]
            empty_info = plistlib.dumps({"images": []})
            responses = iter(
                (
                    smoke.base.CommandResult(
                        stdout=empty_info,
                        stderr=b"",
                    ),
                    smoke.base.CommandResult(
                        stdout=plistlib.dumps(
                            {"system-entities": entities}
                        ),
                        stderr=b"",
                    ),
                    smoke.base.CommandResult(
                        stdout=plistlib.dumps(
                            {
                                "images": [
                                    {
                                        "image-path": str(image),
                                        "system-entities": entities,
                                    }
                                ]
                            }
                        ),
                        stderr=b"",
                    ),
                    smoke.base.CommandResult(stdout=b"", stderr=b""),
                    smoke.base.CommandResult(
                        stdout=empty_info,
                        stderr=b"",
                    ),
                )
            )
            commands: list[tuple[str, ...]] = []

            def command_runner(
                command: tuple[str, ...],
            ) -> smoke.base.CommandResult:
                commands.append(command)
                return next(responses)

            with (
                patch.object(
                    smoke.base,
                    "run_bounded_command",
                    side_effect=command_runner,
                ),
                self.assertRaises(smoke.LocalDMGSmokeError),
            ):
                smoke.attach_copy_detach(
                    dmg_path=image,
                    mountpoint=mountpoint,
                    copier=lambda: self.app_tree(),
                )

            self.assertIn(
                smoke.base.detach_dmg_command("/dev/disk42s1"),
                commands,
            )
            with self.assertRaises(StopIteration):
                next(responses)

    def test_recovery_does_not_swallow_keyboard_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name).resolve()
            image = root / "image.dmg"
            mountpoint = root / "mount"
            mountpoint.mkdir()
            with (
                patch.object(
                    smoke.base,
                    "run_bounded_command",
                    side_effect=KeyboardInterrupt,
                ),
                self.assertRaises(KeyboardInterrupt),
            ):
                smoke.recover_unmount(
                    dmg_path=image,
                    mountpoint=mountpoint,
                )

    def test_uninstall_primitive_rejects_wrong_path_running_and_tree_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            temporary_root = Path(temporary_name).resolve()
            isolated_home = temporary_root / "home"
            applications = isolated_home / "Applications"
            applications.mkdir(parents=True)
            app_path = applications / smoke.installed.APP_RELATIVE_PATH
            self.create_app(app_path)
            release = self.release_for_app(app_path)
            tree = smoke.installed.app_tree_evidence(app_path, release)

            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.uninstall.remove_exact_installed_app(
                    temporary_root=temporary_root,
                    isolated_home=isolated_home,
                    app_path=applications / "Other.app",
                    release=release,
                    expected_tree=tree,
                    lister=lambda: (),
                )

            running = smoke.installed.RunningApplication(
                activation_policy=0,
                bundle_identifier=smoke.installed.EXPECTED_BUNDLE_ID,
                executable_path=str(
                    app_path / smoke.installed.EXECUTABLE_RELATIVE_PATH
                ),
                finished_launching=True,
                pid=77,
            )
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.uninstall.remove_exact_installed_app(
                    temporary_root=temporary_root,
                    isolated_home=isolated_home,
                    app_path=app_path,
                    release=release,
                    expected_tree=tree,
                    lister=lambda: (running,),
                )

            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.uninstall.remove_exact_installed_app(
                    temporary_root=temporary_root,
                    isolated_home=isolated_home,
                    app_path=app_path,
                    release=release,
                    expected_tree=self.app_tree("e" * 64),
                    lister=lambda: (),
                )

            linked_home = temporary_root / "linked-home"
            linked_home.symlink_to(isolated_home, target_is_directory=True)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.uninstall.validate_uninstall_target(
                    temporary_root=temporary_root,
                    isolated_home=linked_home,
                    app_path=(
                        linked_home
                        / "Applications"
                        / smoke.installed.APP_RELATIVE_PATH
                    ),
                )

    def test_mounted_copy_reuses_physical_applications_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name).resolve()
            mountpoint = root / "mount"
            mounted_app = mountpoint / smoke.installed.APP_RELATIVE_PATH
            self.create_app(mounted_app)
            (mountpoint / "Applications").symlink_to("/Applications")
            release = self.release_for_app(mounted_app)
            tree = smoke.installed.app_tree_evidence(
                mounted_app,
                release,
            )

            temporary_root = root / "temporary"
            isolated_home = temporary_root / "home"
            (isolated_home / "Applications").mkdir(parents=True)
            installed_app = (
                isolated_home
                / "Applications"
                / smoke.installed.APP_RELATIVE_PATH
            )
            with patch.object(smoke.recovery, "verify_packaged_app"):
                copied = smoke.copy_from_mounted_dmg(
                    mountpoint=mountpoint,
                    temporary_root=temporary_root,
                    isolated_home=isolated_home,
                    installed_app=installed_app,
                    release=release,
                    version=smoke.recovery.ReleaseVersion(
                        build_number=987,
                        marketing_version="9.8.7",
                        semantic_version=(9, 8, 7),
                    ),
                    expected_tree=tree,
                )

            self.assertEqual(copied, tree)
            self.assertTrue(installed_app.is_dir())

    def test_state_comparison_rejects_sqlite_and_file_drift(self) -> None:
        sqlite = sqlite_evidence()
        state = {
            "runtime-identity.json": smoke.installed.FileIdentity(
                mode=0o600,
                sha256="a" * 64,
                size=10,
            )
        }
        smoke.require_unchanged_state(
            label="baseline",
            expected_sqlite=sqlite,
            observed_sqlite=sqlite,
            expected_files=state,
            observed_files=state,
        )
        with self.assertRaises(smoke.LocalDMGSmokeError):
            smoke.require_unchanged_state(
                label="SQLite drift",
                expected_sqlite=sqlite,
                observed_sqlite=sqlite[:2],
                expected_files=state,
                observed_files=state,
            )
        changed = dict(state)
        changed["runtime-identity.json"] = smoke.installed.FileIdentity(
            mode=0o600,
            sha256="b" * 64,
            size=10,
        )
        with self.assertRaises(smoke.LocalDMGSmokeError):
            smoke.require_unchanged_state(
                label="file drift",
                expected_sqlite=sqlite,
                observed_sqlite=sqlite,
                expected_files=state,
                observed_files=changed,
            )

    def exercise(
        self,
        *,
        failure: str | None = None,
        publish_result: bool = True,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name).resolve()
            archive_dir = root / "archive"
            archive_dir.mkdir()
            snapshot_dir = root / "snapshot/build-987"
            snapshot_dir.mkdir(parents=True)
            result_path = root / "result.json"
            version = smoke.recovery.ReleaseVersion(
                build_number=987,
                marketing_version="9.8.7",
                semantic_version=(9, 8, 7),
            )
            release = self.release_inputs(snapshot_dir)
            tree = self.app_tree()
            image_identity = smoke.installed.FileIdentity(
                mode=0o600,
                sha256="f" * 64,
                size=1000,
            )
            changed_image_identity = smoke.installed.FileIdentity(
                mode=0o600,
                sha256="0" * 64,
                size=1000,
            )
            state = {
                "runtime-identity.json": smoke.installed.FileIdentity(
                    mode=0o600,
                    sha256="1" * 64,
                    size=20,
                )
            }
            events: list[str] = []
            copy_mounts: list[Path] = []
            copy_images: list[Path] = []
            identity_paths: list[Path] = []

            @contextmanager
            def root_context(
                *,
                termination_timeout_seconds: float,
            ) -> Iterator[Path]:
                self.assertEqual(termination_timeout_seconds, 1.0)
                work = root / "work"
                work.mkdir()
                events.append("root-enter")
                try:
                    yield work
                finally:
                    events.append("root-cleanup")

            def snapshot(*_args: object, **_kwargs: object) -> object:
                events.append("snapshot")
                return snapshot_dir, self.snapshot_files()

            def readback(
                path: Path,
                *,
                historical: bool,
            ) -> None:
                self.assertEqual(path, snapshot_dir)
                self.assertIs(historical, False)
                events.append("readback")

            def load_release(
                path: Path,
                *,
                verify_readback: bool,
                version: object,
            ) -> smoke.engine.ReleaseInputs:
                self.assertEqual(path, snapshot_dir)
                self.assertIs(verify_readback, False)
                self.assertIs(version, version_value)
                events.append("load")
                return release

            def extract(
                _release: smoke.engine.ReleaseInputs,
                destination: Path,
            ) -> Path:
                destination.mkdir(parents=True)
                events.append("extract")
                return destination

            def stage(_source: Path, staging: Path) -> Path:
                staged = staging / smoke.installed.APP_RELATIVE_PATH
                staged.mkdir(parents=True)
                events.append("stage")
                return staged

            def command_runner(
                command: tuple[str, ...],
            ) -> smoke.base.CommandResult:
                operation = command[1]
                if operation == "create":
                    Path(command[-1]).write_bytes(b"fixture DMG")
                    events.append("create")
                elif operation == "verify":
                    events.append("verify")
                else:
                    self.fail(f"unexpected command: {command}")
                return smoke.base.CommandResult(stdout=b"", stderr=b"")

            image_calls = 0

            def identify(_path: Path) -> smoke.installed.FileIdentity:
                nonlocal image_calls
                image_calls += 1
                events.append(f"image-{image_calls}")
                if failure == "image-drift" and image_calls == 2:
                    return changed_image_identity
                return image_identity

            def copy_image(**keywords: object) -> smoke.installed.AppTreeEvidence:
                mountpoint = Path(keywords["mountpoint"])
                copy_mounts.append(mountpoint)
                copy_images.append(Path(keywords["dmg_path"]))
                self.assertEqual(
                    keywords["temporary_root"],
                    root / "work",
                )
                self.assertEqual(
                    keywords["isolated_home"],
                    root / "work/home",
                )
                events.append(f"copy-{len(copy_mounts)}")
                return tree

            def environment(
                _source: object,
                *,
                home: Path,
                temporary: Path,
                identity_file: Path,
            ) -> dict[str, str]:
                self.assertTrue(home.is_dir())
                self.assertTrue(temporary.is_dir())
                identity_paths.append(identity_file)
                return {"IDENTITY_FILE": str(identity_file)}

            def launch(**keywords: object) -> tuple[int, dict[str, object]]:
                ordinal = int(keywords["ordinal"])
                events.append(f"launch-{ordinal}")
                if ordinal == 1:
                    path = Path(keywords["environment"]["IDENTITY_FILE"])
                    path.write_bytes(b"identity")
                    self.assertEqual(identity_paths, [path])
                pid = 101 if ordinal == 1 else 102
                if failure == "pid-reuse" and ordinal == 2:
                    pid = 101
                return pid, launch_record(ordinal)

            def remove(**_keywords: object) -> None:
                events.append(
                    "remove-1"
                    if events.count("remove-1") == 0
                    else "remove-2"
                )

            def recheck(
                _directory: Path,
                _files: dict[str, dict[str, object]],
            ) -> None:
                events.append("snapshot-recheck")
                if failure == "snapshot-drift":
                    raise smoke.engine.LifecycleSmokeError(
                        "snapshot changed"
                    )

            def publish(
                _path: Path,
                _result: dict[str, object],
            ) -> None:
                events.append("publish")

            version_value = version
            patches = (
                patch.object(smoke, "current_release", return_value=version),
                patch.object(smoke, "release_id_for", return_value="build-987"),
                patch.object(smoke, "isolated_dmg_root", side_effect=root_context),
                patch.object(
                    smoke.upgrade,
                    "snapshot_archive_directory",
                    side_effect=snapshot,
                ),
                patch.object(
                    smoke.upgrade,
                    "verify_archive_readback",
                    side_effect=readback,
                ),
                patch.object(
                    smoke.recovery,
                    "load_release_inputs",
                    side_effect=load_release,
                ),
                patch.object(
                    smoke.installed,
                    "list_bundle_applications",
                    return_value=(),
                ),
                patch.object(
                    smoke.engine,
                    "extract_packaged_app",
                    side_effect=extract,
                ),
                patch.object(smoke.recovery, "verify_packaged_app"),
                patch.object(
                    smoke.installed,
                    "app_tree_evidence",
                    return_value=tree,
                ),
                patch.object(
                    smoke.base,
                    "stage_dmg_root",
                    side_effect=stage,
                ),
                patch.object(
                    smoke.base,
                    "run_bounded_command",
                    side_effect=command_runner,
                ),
                patch.object(smoke, "image_identity", side_effect=identify),
                patch.object(smoke, "copy_same_image", side_effect=copy_image),
                patch.object(
                    smoke.installed,
                    "isolated_launch_environment",
                    side_effect=environment,
                ),
                patch.object(
                    smoke.installed,
                    "run_launch_services_cycle",
                    side_effect=launch,
                ),
                patch.object(
                    smoke.installed,
                    "sqlite_state_evidence",
                    return_value=sqlite_evidence(),
                ),
                patch.object(
                    smoke.installed,
                    "state_file_records",
                    return_value=state,
                ),
                patch.object(
                    smoke.uninstall,
                    "remove_exact_installed_app",
                    side_effect=remove,
                ),
                patch.object(
                    smoke.upgrade,
                    "require_unchanged_archive_snapshot",
                    side_effect=recheck,
                ),
                patch.object(
                    smoke.installed,
                    "assert_preexisting_applications_preserved",
                    side_effect=lambda _apps: events.append("preserve"),
                ),
                patch.object(smoke, "publish_result", side_effect=publish),
            )
            with ExitStack() as stack:
                for context in patches:
                    stack.enter_context(context)
                if failure is None:
                    arguments = {
                        "archive_dir": archive_dir,
                        "readiness_timeout_seconds": 1.0,
                        "observation_seconds": (
                            smoke.engine.MINIMUM_OBSERVATION_SECONDS
                        ),
                        "termination_timeout_seconds": 1.0,
                    }
                    result = (
                        smoke.execute(
                            result_path=result_path,
                            **arguments,
                        )
                        if publish_result
                        else smoke.exercise(**arguments)
                    )
                    self.assertEqual(result["status"], "passed")
                else:
                    with self.assertRaises(
                        (
                            smoke.LocalDMGSmokeError,
                            smoke.engine.LifecycleSmokeError,
                        )
                    ):
                        smoke.execute(
                            archive_dir=archive_dir,
                            result_path=result_path,
                            readiness_timeout_seconds=1.0,
                            observation_seconds=(
                                smoke.engine.MINIMUM_OBSERVATION_SECONDS
                            ),
                            termination_timeout_seconds=1.0,
                        )
            if len(copy_mounts) == 2:
                self.assertNotEqual(copy_mounts[0], copy_mounts[1])
                self.assertEqual(copy_images[0], copy_images[1])
            return events

    def test_execute_uses_one_image_two_mounts_cleanup_then_publish(
        self,
    ) -> None:
        events = self.exercise()
        self.assertEqual(
            events,
            [
                "root-enter",
                "snapshot",
                "readback",
                "load",
                "extract",
                "stage",
                "create",
                "verify",
                "image-1",
                "copy-1",
                "launch-1",
                "remove-1",
                "image-2",
                "copy-2",
                "launch-2",
                "remove-2",
                "image-3",
                "snapshot-recheck",
                "preserve",
                "root-cleanup",
                "publish",
            ],
        )

    def test_exercise_cleans_root_without_publishing(self) -> None:
        events = self.exercise(publish_result=False)
        self.assertEqual(events[-1], "root-cleanup")
        self.assertNotIn("publish", events)

    def test_image_snapshot_and_pid_failures_block_publication(self) -> None:
        for failure in ("image-drift", "snapshot-drift", "pid-reuse"):
            with self.subTest(failure=failure):
                events = self.exercise(failure=failure)
                self.assertNotIn("publish", events)
                self.assertIn("root-cleanup", events)

    def test_cleanup_failure_retains_root_and_blocks_body_success(
        self,
    ) -> None:
        retained: Path | None = None
        with (
            patch.object(
                smoke.upgrade,
                "cleanup_exact_temporary_applications",
                side_effect=smoke.engine.LifecycleSmokeError(
                    "cleanup failed"
                ),
            ),
            patch.object(smoke, "recover_unmount"),
        ):
            with self.assertRaisesRegex(
                smoke.LocalDMGSmokeError,
                "diagnostic root retained",
            ):
                with smoke.isolated_dmg_root(
                    termination_timeout_seconds=1.0
                ) as temporary_root:
                    retained = temporary_root
        self.assertIsNotNone(retained)
        assert retained is not None
        self.assertTrue(retained.is_dir())
        shutil.rmtree(retained)

    def test_partial_directory_cleanup_does_not_claim_full_retention(
        self,
    ) -> None:
        retained: Path | None = None
        with (
            patch.object(
                smoke.upgrade,
                "cleanup_exact_temporary_applications",
            ),
            patch.object(smoke, "recover_unmount"),
            patch.object(
                smoke.shutil,
                "rmtree",
                side_effect=OSError("partial removal"),
            ),
            self.assertRaisesRegex(
                smoke.LocalDMGSmokeError,
                "diagnostic root may remain",
            ),
        ):
            with smoke.isolated_dmg_root(
                termination_timeout_seconds=1.0
            ) as temporary_root:
                retained = temporary_root
        self.assertIsNotNone(retained)
        assert retained is not None
        shutil.rmtree(retained)

    def test_publisher_is_idempotent_and_refuses_different_or_symlink(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            result_path = root / "result.json"
            result = {"schemaVersion": 1, "status": "passed"}
            smoke.publish_result(result_path, result)
            baseline = result_path.read_bytes()
            smoke.publish_result(result_path, result)
            self.assertEqual(result_path.read_bytes(), baseline)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.publish_result(
                    result_path,
                    {"schemaVersion": 2, "status": "passed"},
                )

            link = root / "link.json"
            link.symlink_to(result_path)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.publish_result(link, result)

    def test_main_failure_is_path_free(self) -> None:
        stderr = io.StringIO()
        with (
            patch.object(
                smoke,
                "execute",
                side_effect=smoke.LocalDMGSmokeError(
                    "failure at /private/sensitive/path"
                ),
            ),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(smoke.main([]), 1)
        self.assertEqual(
            stderr.getvalue(),
            "Local DMG uninstall/reinstall v1 smoke failed.\n",
        )
        self.assertNotIn("/private/sensitive", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
