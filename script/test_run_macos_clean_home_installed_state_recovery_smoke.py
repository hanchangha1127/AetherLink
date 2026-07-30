#!/usr/bin/env python3
"""Tests for installed clean-HOME state-recovery qualification."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_clean_home_installed_state_recovery_smoke as smoke


class CleanHomeInstalledStateRecoverySmokeTests(unittest.TestCase):
    def environment(
        self,
        root: Path,
        *,
        mode: str = smoke.recovery.MIGRATION_MODE,
    ) -> dict[str, str]:
        return smoke.recovery_launch_environment(
            {
                "AETHERLINK_UNRELATED": "remove",
                "DYLD_INSERT_LIBRARIES": "remove",
                "LD_PRELOAD": "remove",
                "PATH": "/usr/bin",
            },
            home=root / "home",
            temporary=root / "tmp",
            identity_file=root / "state/runtime-identity.json",
            mode=mode,
        )

    def running_application(
        self,
        *,
        pid: int,
        executable_path: str,
    ) -> smoke.installed.RunningApplication:
        return smoke.installed.RunningApplication(
            activation_policy=0,
            bundle_identifier=smoke.installed.EXPECTED_BUNDLE_ID,
            executable_path=executable_path,
            finished_launching=True,
            pid=pid,
        )

    def application_status(
        self,
        executable: Path,
    ) -> smoke.engine.ApplicationStatus:
        return smoke.engine.ApplicationStatus(
            activation_policy=0,
            bundle_identifier=smoke.installed.EXPECTED_BUNDLE_ID,
            executable_path=str(executable),
            finished_launching=True,
        )

    def create_sqlite_database(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE state(id INTEGER)")
            connection.commit()
        finally:
            connection.close()

    def create_canary_database(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                """
                CREATE TABLE runtime_chat_events(
                    event_id TEXT,
                    timestamp TEXT,
                    kind TEXT,
                    request_id TEXT,
                    session_id TEXT,
                    owner_device_id TEXT,
                    model TEXT,
                    event_json TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO runtime_chat_events(
                    event_id,
                    timestamp,
                    kind,
                    request_id,
                    session_id,
                    owner_device_id,
                    model,
                    event_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    smoke.recovery.CANARY_EVENT_ID,
                    smoke.recovery.CANARY_TIMESTAMP,
                    "request",
                    smoke.recovery.CANARY_REQUEST_ID,
                    smoke.recovery.CANARY_SESSION_ID,
                    None,
                    smoke.recovery.CANARY_MODEL,
                    smoke.recovery.CANARY_EVENT_JSON.decode("ascii"),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def test_recovery_environment_is_closed_and_mode_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            environment = self.environment(root)
            self.assertNotIn("AETHERLINK_UNRELATED", environment)
            self.assertNotIn("DYLD_INSERT_LIBRARIES", environment)
            self.assertNotIn("LD_PRELOAD", environment)
            self.assertEqual(environment["PATH"], "/usr/bin")
            self.assertEqual(
                environment[smoke.recovery.QA_MODE_ENVIRONMENT_KEY],
                smoke.recovery.MIGRATION_MODE,
            )
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                self.environment(root, mode="unknown")

    def test_recovery_launch_command_captures_separate_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            app_path = root / "Applications/AetherLink.app"
            environment = self.environment(root)
            environment["AETHERLINK_UNRELATED"] = "not-forwarded"
            stdout_path = root / "logs/stdout.log"
            stderr_path = root / "logs/stderr.log"
            command = smoke.recovery_launch_services_command(
                app_path,
                environment,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )

            self.assertEqual(
                command[:4],
                [str(smoke.installed.OPEN), "-n", "-F", "-g"],
            )
            self.assertEqual(command[-1], str(app_path))
            self.assertEqual(command.count("--stdout"), 1)
            self.assertEqual(command.count("--stderr"), 1)
            self.assertEqual(command.count("--env"), 8)
            self.assertIn(
                (
                    f"{smoke.recovery.QA_MODE_ENVIRONMENT_KEY}="
                    f"{smoke.recovery.MIGRATION_MODE}"
                ),
                command,
            )
            self.assertFalse(
                any(
                    "AETHERLINK_UNRELATED" in argument
                    for argument in command
                )
            )

            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.recovery_launch_services_command(
                    app_path,
                    environment,
                    stdout_path=stdout_path,
                    stderr_path=stdout_path,
                )
            invalid = dict(environment)
            invalid.pop(smoke.recovery.QA_MODE_ENVIRONMENT_KEY)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.recovery_launch_services_command(
                    app_path,
                    invalid,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )

    def test_prepare_and_validate_captured_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            log = root / "run.log"
            smoke.prepare_captured_log(log)
            self.assertEqual(
                stat.S_IMODE(log.stat().st_mode),
                0o600,
            )
            evidence = smoke.validate_captured_log(
                log,
                label="test log",
            )
            self.assertEqual(evidence["size"], 0)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.prepare_captured_log(log)

            oversized = root / "oversized.log"
            oversized.write_bytes(
                b"x" * (smoke.MAXIMUM_CAPTURED_LOG_BYTES + 1)
            )
            oversized.chmod(0o600)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.validate_captured_log(
                    oversized,
                    label="oversized log",
                )

    def test_auxiliary_sqlite_evidence_requires_both_databases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            application_support = Path(temporary_name)
            for filename in smoke.AUXILIARY_SQLITE_FILES:
                self.create_sqlite_database(
                    application_support / filename
                )
            evidence = smoke.auxiliary_sqlite_evidence(
                application_support
            )
            self.assertEqual(
                tuple(row["filename"] for row in evidence),
                smoke.AUXILIARY_SQLITE_FILES,
            )
            self.assertTrue(
                all(row["integrityCheck"] == "ok" for row in evidence)
            )

            (application_support / smoke.AUXILIARY_SQLITE_FILES[0]).unlink()
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.auxiliary_sqlite_evidence(application_support)

    def test_fixed_canary_and_observation_helpers_accept_exact_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            legacy = (
                root
                / "Library/Application Support/AetherLink"
                / smoke.recovery.LEGACY_FILENAME
            )
            smoke.recovery.write_legacy_fixture(legacy)
            self.assertEqual(
                legacy.read_bytes(),
                smoke.recovery.CANARY_LEGACY_BYTES,
            )
            self.assertEqual(
                stat.S_IMODE(legacy.stat().st_mode),
                0o600,
            )

            observation = root / "observation.log"
            observation.write_bytes(
                smoke.recovery.expected_observation_line(
                    smoke.recovery.MIGRATION_MODE
                )
            )
            observed = smoke.recovery.verify_observation_log(
                observation,
                smoke.recovery.MIGRATION_MODE,
            )
            self.assertEqual(observed["status"], "passed")

            database = root / "runtime-chat-events.sqlite"
            self.create_canary_database(database)
            canary = smoke.recovery.sqlite_canary_evidence(database)
            self.assertEqual(canary.total_event_count, 1)
            self.assertEqual(
                canary.event_json_sha256,
                smoke.recovery.CANARY_EVENT_JSON_SHA256,
            )

    def test_canary_readback_rejects_an_extra_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            database = Path(temporary_name) / "runtime-chat-events.sqlite"
            self.create_canary_database(database)
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    """
                    INSERT INTO runtime_chat_events(
                        event_id,
                        timestamp,
                        kind,
                        request_id,
                        session_id,
                        owner_device_id,
                        model,
                        event_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "extra",
                        smoke.recovery.CANARY_TIMESTAMP,
                        "request",
                        "extra-request",
                        "extra-session",
                        None,
                        smoke.recovery.CANARY_MODEL,
                        "{}",
                    ),
                )
                connection.commit()
            finally:
                connection.close()
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.recovery.sqlite_canary_evidence(database)

    def test_changed_state_paths_reports_add_remove_and_identity_drift(
        self,
    ) -> None:
        first_identity = smoke.installed.FileIdentity(
            mode=0o600,
            sha256="a" * 64,
            size=1,
        )
        second_identity = smoke.installed.FileIdentity(
            mode=0o600,
            sha256="b" * 64,
            size=1,
        )
        self.assertEqual(
            smoke.changed_state_paths(
                {
                    "changed": first_identity,
                    "removed": first_identity,
                },
                {
                    "changed": second_identity,
                    "added": first_identity,
                },
            ),
            ["added", "changed", "removed"],
        )

    def test_launch_cycle_binds_and_terminates_only_new_exact_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            app_path = root / "Applications/AetherLink.app"
            executable = (
                app_path
                / smoke.installed.EXECUTABLE_RELATIVE_PATH
            )
            logs = root / "logs"
            logs.mkdir()
            environment = self.environment(root)
            preexisting = self.running_application(
                pid=10,
                executable_path="/tmp/other/AetherLink",
            )
            launched = self.running_application(
                pid=20,
                executable_path=str(executable),
            )
            inventories = iter(
                (
                    (preexisting,),
                    (preexisting, launched),
                    (preexisting,),
                )
            )
            statuses = iter(
                (
                    self.application_status(executable),
                    None,
                )
            )
            times = iter((0.0, 0.1, 0.2, 5.3))
            requests: list[tuple[int, Path, bool]] = []
            commands: list[list[str]] = []

            pid, record = smoke.run_recovery_launch_services_cycle(
                ordinal=1,
                app_path=app_path,
                environment=environment,
                stdout_path=logs / "stdout.log",
                stderr_path=logs / "stderr.log",
                readiness_timeout_seconds=1.0,
                observation_seconds=5.0,
                termination_timeout_seconds=1.0,
                command_runner=lambda command, **_kwargs: (
                    commands.append(command)
                    or subprocess.CompletedProcess(command, 0, "", "")
                ),
                lister=lambda: next(inventories),
                query=lambda _pid: next(statuses),
                requester=lambda request_pid, path, *, force: (
                    requests.append((request_pid, path, force)) or True
                ),
                monotonic=lambda: next(times),
                sleeper=lambda _seconds: None,
            )

            self.assertEqual(pid, 20)
            self.assertEqual(record["ordinal"], 1)
            self.assertEqual(
                requests,
                [(20, executable, False)],
            )
            self.assertEqual(commands[0][-1], str(app_path))

    def test_launch_cycle_cleans_new_exact_path_after_command_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            app_path = root / "Applications/AetherLink.app"
            executable = (
                app_path
                / smoke.installed.EXECUTABLE_RELATIVE_PATH
            )
            logs = root / "logs"
            logs.mkdir()
            environment = self.environment(root)
            launched = self.running_application(
                pid=30,
                executable_path=str(executable),
            )
            inventories = iter(((), (launched,)))
            statuses = iter(
                (
                    self.application_status(executable),
                    None,
                )
            )
            requests: list[tuple[int, Path, bool]] = []

            def fail_command(
                _command: list[str],
                **_kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                raise smoke.engine.LifecycleSmokeError("synthetic failure")

            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.run_recovery_launch_services_cycle(
                    ordinal=1,
                    app_path=app_path,
                    environment=environment,
                    stdout_path=logs / "stdout.log",
                    stderr_path=logs / "stderr.log",
                    readiness_timeout_seconds=1.0,
                    observation_seconds=5.0,
                    termination_timeout_seconds=1.0,
                    command_runner=fail_command,
                    lister=lambda: next(inventories),
                    query=lambda _pid: next(statuses),
                    requester=lambda request_pid, path, *, force: (
                        requests.append((request_pid, path, force))
                        or True
                    ),
                )
            self.assertEqual(requests, [(30, executable, True)])

    def test_result_publication_is_idempotent_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result_path = Path(temporary_name) / "result.json"
            result = {"schemaVersion": 1, "status": "passed"}
            smoke.installed.publish_result(result_path, result)
            first = result_path.read_bytes()
            smoke.installed.publish_result(result_path, result)
            self.assertEqual(result_path.read_bytes(), first)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.installed.publish_result(
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
                            "clean-home-state-recovery-v1.json"
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
