#!/usr/bin/env python3
"""Tests for the temporary-HOME macOS uninstall/reinstall smoke runner."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_isolated_uninstall_reinstall_smoke as smoke


class IsolatedUninstallReinstallSmokeTests(unittest.TestCase):
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
        placeholder = app_path.parent / "placeholder"
        return smoke.engine.ReleaseInputs(
            archive_dir=placeholder,
            archive_path=placeholder,
            manifest_path=placeholder,
            checksum_path=placeholder,
            archive_sha256="a" * 64,
            manifest_sha256="b" * 64,
            manifest={"members": members},
        )

    def create_sqlite_state(self, application_support: Path) -> None:
        application_support.mkdir(parents=True)
        for filename in smoke.installed.EXPECTED_SQLITE_FILES:
            database_path = application_support / filename
            connection = sqlite3.connect(database_path)
            try:
                if filename == smoke.installed.CHAT_DATABASE_FILENAME:
                    connection.execute(
                        "CREATE TABLE runtime_chat_events(id INTEGER)"
                    )
                else:
                    connection.execute("CREATE TABLE state(id INTEGER)")
                connection.commit()
            finally:
                connection.close()

    def test_archive_readback_is_explicitly_archive_only(self) -> None:
        calls: list[tuple[list[str], Path | None]] = []

        def runner(
            command: list[str],
            *,
            cwd: Path | None = None,
        ) -> object:
            calls.append((command, cwd))
            return object()

        archive = Path("/tmp/aetherlink-release")
        smoke.verify_archive_only_readback(archive, runner=runner)

        self.assertEqual(len(calls), 1)
        command, cwd = calls[0]
        self.assertEqual(cwd, smoke.ROOT)
        self.assertIn("--no-current-source", command)
        self.assertEqual(
            command[command.index("--archive-dir") + 1],
            str(archive.resolve()),
        )

    def test_exact_temporary_app_removal_preserves_sibling_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            isolated_home = temporary_root / "home"
            applications = isolated_home / "Applications"
            applications.mkdir(parents=True)
            app_path = applications / smoke.installed.APP_RELATIVE_PATH
            self.create_app(app_path)
            release = self.release_for_app(app_path)
            tree = smoke.installed.app_tree_evidence(app_path, release)
            state = isolated_home / "Library/Application Support/AetherLink"
            state.mkdir(parents=True)
            state_file = state / "state.bin"
            state_file.write_bytes(b"preserve")
            before = hashlib.sha256(state_file.read_bytes()).hexdigest()

            smoke.remove_exact_installed_app(
                temporary_root=temporary_root,
                isolated_home=isolated_home,
                app_path=app_path,
                release=release,
                expected_tree=tree,
                lister=lambda: (),
            )

            self.assertFalse(app_path.exists())
            self.assertEqual(
                hashlib.sha256(state_file.read_bytes()).hexdigest(),
                before,
            )

    def test_removal_rejects_wrong_path_symlink_and_running_instance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            isolated_home = temporary_root / "home"
            applications = isolated_home / "Applications"
            applications.mkdir(parents=True)
            app_path = applications / smoke.installed.APP_RELATIVE_PATH
            self.create_app(app_path)
            release = self.release_for_app(app_path)
            tree = smoke.installed.app_tree_evidence(app_path, release)

            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.remove_exact_installed_app(
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
                smoke.remove_exact_installed_app(
                    temporary_root=temporary_root,
                    isolated_home=isolated_home,
                    app_path=app_path,
                    release=release,
                    expected_tree=tree,
                    lister=lambda: (running,),
                )

            linked_home = temporary_root / "linked-home"
            linked_home.symlink_to(isolated_home, target_is_directory=True)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.validate_uninstall_target(
                    temporary_root=temporary_root,
                    isolated_home=linked_home,
                    app_path=(
                        linked_home
                        / "Applications"
                        / smoke.installed.APP_RELATIVE_PATH
                    ),
                )

    def test_execute_models_remove_reinstall_remove_without_state_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            template = root / "template/AetherLink.app"
            self.create_app(template)
            release = self.release_for_app(template)
            result_path = root / "result.json"
            pids: list[int] = []

            def extract(
                _release: smoke.engine.ReleaseInputs,
                destination: Path,
            ) -> Path:
                extracted = destination / smoke.installed.APP_RELATIVE_PATH
                extracted.parent.mkdir(parents=True)
                shutil.copytree(template, extracted)
                return extracted

            def install(
                source: Path,
                *,
                temporary_root: Path,
                isolated_home: Path,
                app_path: Path,
            ) -> None:
                del temporary_root, isolated_home
                app_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, app_path)

            def launch(
                *,
                ordinal: int,
                app_path: Path,
                environment: dict[str, str],
                readiness_timeout_seconds: float,
                observation_seconds: float,
                termination_timeout_seconds: float,
            ) -> tuple[int, dict[str, object]]:
                del (
                    app_path,
                    readiness_timeout_seconds,
                    observation_seconds,
                    termination_timeout_seconds,
                )
                application_support = (
                    Path(environment["HOME"])
                    / "Library/Application Support/AetherLink"
                )
                if not application_support.exists():
                    self.create_sqlite_state(application_support)
                pid = 100 + ordinal
                pids.append(pid)
                return (
                    pid,
                    {
                        "activationPolicy": 0,
                        "executablePathMatched": True,
                        "finishedLaunching": True,
                        "newProcessIdentifierDetected": True,
                        "observationDeadlineReached": True,
                        "ordinal": ordinal,
                        "terminationAccepted": True,
                    },
                )

            metadata = {
                "bundleIdentifier": smoke.installed.EXPECTED_BUNDLE_ID,
                "buildNumber": smoke.current_release().build_number,
                "executableSha256": "c" * 64,
                "marketingVersion": (
                    smoke.current_release().marketing_version
                ),
                "uuid": "fixture-uuid",
            }
            with (
                patch.object(
                    smoke,
                    "verify_archive_only_readback",
                ),
                patch.object(
                    smoke.recovery,
                    "load_release_inputs",
                    return_value=release,
                ),
                patch.object(
                    smoke.engine,
                    "extract_packaged_app",
                    side_effect=extract,
                ),
                patch.object(
                    smoke.recovery,
                    "verify_packaged_app",
                    return_value=metadata,
                ),
                patch.object(
                    smoke,
                    "install_exact_temporary_app",
                    side_effect=install,
                ),
                patch.object(
                    smoke.installed,
                    "run_launch_services_cycle",
                    side_effect=launch,
                ),
                patch.object(
                    smoke.installed,
                    "list_bundle_applications",
                    return_value=(),
                ),
                patch.object(
                    smoke.installed,
                    "assert_preexisting_applications_preserved",
                ),
            ):
                result = smoke.execute(
                    archive_dir=root / "archive",
                    result_path=result_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=(
                        smoke.engine.MINIMUM_OBSERVATION_SECONDS
                    ),
                    termination_timeout_seconds=1.0,
                )

            self.assertEqual(pids, [101, 102])
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["uninstall"]["removalCount"], 2)
            self.assertFalse(
                result["uninstall"]["applicationSupportCleanupPerformed"]
            )
            self.assertEqual(
                result["archiveReadback"]["mode"],
                smoke.ARCHIVE_READBACK_MODE,
            )
            self.assertEqual(
                result_path.read_bytes(),
                smoke.engine.canonical_json_bytes(result),
            )

    def test_default_result_tracks_current_and_future_release(self) -> None:
        current = smoke.current_release()
        future = smoke.recovery.ReleaseVersion(
            current.build_number + 5,
            "2.4.6",
            (2, 4, 6),
        )
        with patch.object(smoke, "current_release", return_value=future):
            self.assertEqual(
                smoke.default_result_path().name,
                (
                    "macos-packaged-app-build-"
                    f"{future.build_number}-"
                    "isolated-uninstall-reinstall-v1.json"
                ),
            )


if __name__ == "__main__":
    unittest.main()
