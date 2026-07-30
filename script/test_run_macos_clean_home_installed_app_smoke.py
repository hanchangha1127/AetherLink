#!/usr/bin/env python3
"""Tests for the isolated installed-app LaunchServices smoke runner."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_clean_home_installed_app_smoke as smoke


class CleanHomeInstalledAppSmokeTests(unittest.TestCase):
    def running_application(
        self,
        *,
        pid: int,
        executable_path: str,
        bundle_identifier: str = smoke.EXPECTED_BUNDLE_ID,
        finished_launching: bool = True,
        activation_policy: int = 0,
    ) -> smoke.RunningApplication:
        return smoke.RunningApplication(
            activation_policy=activation_policy,
            bundle_identifier=bundle_identifier,
            executable_path=executable_path,
            finished_launching=finished_launching,
            pid=pid,
        )

    def valid_inventory_row(self, pid: object = 41) -> dict[str, object]:
        return {
            "activationPolicy": 0,
            "bundleIdentifier": smoke.EXPECTED_BUNDLE_ID,
            "executablePath": "/tmp/AetherLink",
            "finishedLaunching": True,
            "pid": pid,
        }

    def release_for_app(self, app_path: Path) -> smoke.engine.ReleaseInputs:
        members: list[dict[str, object]] = []
        for member, identity in smoke.app_file_records(app_path).items():
            members.append(
                {
                    "mode": f"0{identity.mode:03o}",
                    "path": member,
                    "sha256": identity.sha256,
                    "size": identity.size,
                }
            )
        placeholder = app_path.parent / "placeholder"
        return smoke.engine.ReleaseInputs(
            archive_dir=placeholder,
            archive_path=placeholder,
            manifest_path=placeholder,
            checksum_path=placeholder,
            archive_sha256="0" * 64,
            manifest_sha256="1" * 64,
            manifest={"members": members},
        )

    def create_sqlite_state(
        self,
        application_support: Path,
        *,
        chat_event_count: int = 0,
    ) -> None:
        application_support.mkdir(parents=True)
        for filename in smoke.EXPECTED_SQLITE_FILES:
            database_path = application_support / filename
            connection = sqlite3.connect(database_path)
            try:
                if filename == smoke.CHAT_DATABASE_FILENAME:
                    connection.execute(
                        "CREATE TABLE runtime_chat_events(id INTEGER)"
                    )
                    connection.executemany(
                        "INSERT INTO runtime_chat_events(id) VALUES (?)",
                        [(index,) for index in range(chat_event_count)],
                    )
                else:
                    connection.execute("CREATE TABLE state(id INTEGER)")
                connection.commit()
            finally:
                connection.close()

    def test_parse_running_applications_rejects_bool_and_duplicate_pid(
        self,
    ) -> None:
        with self.assertRaises(smoke.engine.LifecycleSmokeError):
            smoke.parse_running_applications(
                {"applications": [self.valid_inventory_row(True)]}
            )
        with self.assertRaises(smoke.engine.LifecycleSmokeError):
            smoke.parse_running_applications(
                {
                    "applications": [
                        self.valid_inventory_row(42),
                        self.valid_inventory_row(42),
                    ]
                }
            )

    def test_wait_for_new_application_uses_exact_path_and_new_pid(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            executable = (
                Path(temporary_name)
                / "AetherLink.app/Contents/MacOS/AetherLink"
            )
            applications = (
                self.running_application(
                    pid=10,
                    executable_path=str(executable),
                ),
                self.running_application(
                    pid=11,
                    executable_path="/tmp/Other.app/Contents/MacOS/AetherLink",
                ),
                self.running_application(
                    pid=12,
                    executable_path=str(executable),
                    bundle_identifier="example.other",
                ),
                self.running_application(
                    pid=13,
                    executable_path=str(executable),
                ),
            )
            selected = smoke.wait_for_new_application(
                executable=executable,
                preexisting_pids={10},
                timeout_seconds=1.0,
                lister=lambda: applications,
            )
            self.assertEqual(selected.pid, 13)

            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.wait_for_new_application(
                    executable=executable,
                    preexisting_pids=set(),
                    timeout_seconds=1.0,
                    lister=lambda: (
                        applications[-1],
                        self.running_application(
                            pid=14,
                            executable_path=str(executable),
                        ),
                    ),
                )

    def test_isolated_environment_scrubs_project_and_loader_overrides(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            environment = smoke.isolated_launch_environment(
                {
                    "AETHERLINK_EXISTING": "remove",
                    "DYLD_INSERT_LIBRARIES": "remove",
                    "LD_PRELOAD": "remove",
                    "PATH": "/usr/bin",
                },
                home=root / "home",
                temporary=root / "tmp",
                identity_file=root / "state/identity.json",
            )
            self.assertNotIn("AETHERLINK_EXISTING", environment)
            self.assertNotIn("DYLD_INSERT_LIBRARIES", environment)
            self.assertNotIn("LD_PRELOAD", environment)
            self.assertEqual(environment["PATH"], "/usr/bin")
            self.assertEqual(environment["HOME"], str(root / "home"))
            self.assertEqual(
                environment["AETHERLINK_RUNTIME_IDENTITY_FILE"],
                str(root / "state/identity.json"),
            )

    def test_launch_services_command_is_fresh_background_exact_path(
        self,
    ) -> None:
        app_path = Path("/tmp/isolated/Applications/AetherLink.app")
        environment = {
            key: f"value-{index}"
            for index, key in enumerate(
                (
                    "AETHERLINK_RUNTIME_IDENTITY_FILE",
                    "CFFIXED_USER_HOME",
                    "CFPREFERENCES_AVOID_DAEMON",
                    "HOME",
                    "NSUnbufferedIO",
                    "OS_ACTIVITY_MODE",
                    "TMPDIR",
                )
            )
        }
        command = smoke.launch_services_command(app_path, environment)
        self.assertEqual(command[:4], [str(smoke.OPEN), "-n", "-F", "-g"])
        self.assertEqual(command[-1], str(app_path))
        self.assertNotIn("-a", command)
        self.assertNotIn("-b", command)
        self.assertNotIn("-W", command)
        self.assertEqual(command.count("--env"), 7)

        with self.assertRaises(smoke.engine.LifecycleSmokeError):
            smoke.launch_services_command(
                Path("AetherLink.app"),
                environment,
            )
        incomplete = dict(environment)
        incomplete.pop("HOME")
        with self.assertRaises(smoke.engine.LifecycleSmokeError):
            smoke.launch_services_command(app_path, incomplete)

    def test_app_tree_evidence_rejects_tree_and_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            app_path = Path(temporary_name) / "AetherLink.app"
            payload = app_path / "Contents/payload.bin"
            payload.parent.mkdir(parents=True)
            payload.write_bytes(b"canonical")
            payload.chmod(0o644)
            release = self.release_for_app(app_path)

            evidence = smoke.app_tree_evidence(app_path, release)
            self.assertEqual(evidence.file_count, 1)
            self.assertEqual(evidence.total_bytes, len(b"canonical"))

            extra = app_path / "Contents/extra.bin"
            extra.write_bytes(b"extra")
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.app_tree_evidence(app_path, release)
            extra.unlink()

            payload.chmod(0o600)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.app_tree_evidence(app_path, release)
            payload.chmod(0o644)

            payload.write_bytes(b"mutated")
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.app_tree_evidence(app_path, release)
            payload.write_bytes(b"canonical")

            link = app_path / "Contents/link"
            link.symlink_to(payload)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.app_tree_evidence(app_path, release)

    def test_sqlite_state_evidence_accepts_clean_initialized_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            application_support = Path(temporary_name) / "AetherLink"
            self.create_sqlite_state(application_support)
            evidence = smoke.sqlite_state_evidence(application_support)
            self.assertEqual(
                tuple(item.filename for item in evidence),
                smoke.EXPECTED_SQLITE_FILES,
            )
            self.assertEqual(
                next(
                    item.total_event_count
                    for item in evidence
                    if item.filename == smoke.CHAT_DATABASE_FILENAME
                ),
                0,
            )
            self.assertTrue(
                all(item.integrity_check == "ok" for item in evidence)
            )

    def test_sqlite_state_evidence_rejects_nonempty_chat_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            application_support = Path(temporary_name) / "AetherLink"
            self.create_sqlite_state(
                application_support,
                chat_event_count=1,
            )
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.sqlite_state_evidence(application_support)

    def test_state_file_records_expose_byte_or_mode_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            application_support = root / "AetherLink"
            application_support.mkdir()
            state_file = application_support / "state.bin"
            state_file.write_bytes(b"first")
            state_file.chmod(0o600)
            identity_file = root / "runtime-identity.json"
            identity_file.write_bytes(b"identity")
            identity_file.chmod(0o600)

            first = smoke.state_file_records(
                application_support,
                identity_file,
            )
            state_file.write_bytes(b"second")
            second = smoke.state_file_records(
                application_support,
                identity_file,
            )
            self.assertNotEqual(first, second)
            self.assertEqual(
                first["runtime-identity.json"].sha256,
                hashlib.sha256(b"identity").hexdigest(),
            )

    def test_termination_checks_identity_before_request(self) -> None:
        executable = Path(
            "/tmp/isolated/AetherLink.app/Contents/MacOS/AetherLink"
        )
        valid_status = smoke.engine.ApplicationStatus(
            activation_policy=0,
            bundle_identifier=smoke.EXPECTED_BUNDLE_ID,
            executable_path=str(executable),
            finished_launching=True,
        )
        statuses = iter((valid_status, None))
        requested: list[tuple[int, Path, bool]] = []

        self.assertTrue(
            smoke.terminate_exact_application(
                77,
                executable,
                timeout_seconds=1.0,
                query=lambda _pid: next(statuses),
                requester=lambda pid, path, *, force: (
                    requested.append((pid, path, force)) or True
                ),
            )
        )
        self.assertEqual(requested, [(77, executable, False)])

        requested.clear()
        mismatched_status = smoke.engine.ApplicationStatus(
            activation_policy=0,
            bundle_identifier=smoke.EXPECTED_BUNDLE_ID,
            executable_path="/tmp/other/AetherLink",
            finished_launching=True,
        )
        with self.assertRaises(smoke.engine.LifecycleSmokeError):
            smoke.terminate_exact_application(
                78,
                executable,
                timeout_seconds=1.0,
                query=lambda _pid: mismatched_status,
                requester=lambda pid, path, *, force: (
                    requested.append((pid, path, force)) or True
                ),
            )
        self.assertEqual(requested, [])

    def test_publish_result_is_idempotent_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result_path = Path(temporary_name) / "result.json"
            result = {"schemaVersion": 1, "status": "passed"}
            smoke.publish_result(result_path, result)
            first_bytes = result_path.read_bytes()
            smoke.publish_result(result_path, result)
            self.assertEqual(result_path.read_bytes(), first_bytes)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.publish_result(
                    result_path,
                    {"schemaVersion": 1, "status": "different"},
                )

    def test_default_result_tracks_current_and_future_release(self) -> None:
        current = smoke.current_release()
        future = smoke.recovery.ReleaseVersion(
            current.build_number + 7,
            "2.3.4",
            (2, 3, 4),
        )
        for release in (current, future):
            with self.subTest(build_number=release.build_number):
                with patch.object(
                    smoke,
                    "current_release",
                    return_value=release,
                ):
                    self.assertEqual(
                        smoke.default_result_path().name,
                        (
                            "macos-packaged-app-build-"
                            f"{release.build_number}-"
                            "clean-home-install-v1.json"
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
