#!/usr/bin/env python3
"""Tests for packaged post-observation abrupt-process state recovery."""

from __future__ import annotations

import copy
from contextlib import contextmanager, ExitStack
import hashlib
import io
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from script import (
    run_macos_local_dmg_uninstall_reinstall_abrupt_process_state_recovery_smoke
    as smoke,
)


class FakeProcess:
    def __init__(
        self,
        *,
        pid: int = 4_242,
        exit_code: int | None = None,
        wait_result: int = -signal.SIGKILL,
        signal_error: OSError | None = None,
        events: list[str] | None = None,
        poll_error_at: int | None = None,
        poll_error: BaseException | None = None,
    ) -> None:
        self.pid = pid
        self.returncode = exit_code
        self.wait_result = wait_result
        self.signal_error = signal_error
        self.events = events
        self.poll_error_at = poll_error_at
        self.poll_error = poll_error
        self.poll_count = 0
        self.signals: list[int] = []
        self.waits: list[float] = []

    def poll(self) -> int | None:
        self.poll_count += 1
        if (
            self.poll_error_at == self.poll_count
            and self.poll_error is not None
        ):
            error = self.poll_error
            self.poll_error = None
            raise error
        return self.returncode

    def send_signal(self, sent_signal: int) -> None:
        if self.events is not None:
            self.events.append("signal")
        self.signals.append(sent_signal)
        if self.signal_error is not None:
            error = self.signal_error
            self.signal_error = None
            raise error

    def wait(self, timeout: float) -> int:
        if self.events is not None:
            self.events.append("wait")
        self.waits.append(timeout)
        self.returncode = self.wait_result
        return self.wait_result


class AbruptProcessStateRecoverySmokeTests(unittest.TestCase):
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

    def app_tree(
        self,
        *,
        algorithm: str | None = None,
    ) -> smoke.installed.AppTreeEvidence:
        return smoke.installed.AppTreeEvidence(
            digest_algorithm=(
                smoke.installed.TREE_DIGEST_ALGORITHM
                if algorithm is None
                else algorithm
            ),
            file_count=10,
            sha256="d" * 64,
            total_bytes=123,
        )

    def sqlite(
        self,
        *,
        count: int = 1,
        size: int | None = None,
    ) -> smoke.recovery.SQLiteCanaryEvidence:
        return smoke.recovery.SQLiteCanaryEvidence(
            event_json_sha256=smoke.recovery.CANARY_EVENT_JSON_SHA256,
            event_json_size=(
                len(smoke.recovery.CANARY_EVENT_JSON)
                if size is None
                else size
            ),
            integrity_check="ok",
            total_event_count=count,
        )

    def observation(self, mode: str) -> dict[str, object]:
        payload = smoke.recovery.expected_observation_line(mode)
        return {
            "mode": mode,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "status": "passed",
        }

    def graceful_run(self, ordinal: int) -> dict[str, object]:
        return {
            "activationPolicy": 0,
            "executablePathMatched": True,
            "finishedLaunching": True,
            "minimumObservationSeconds": 5.0,
            "newProcessIdentifierDetected": True,
            "observationDeadlineReached": True,
            "ordinal": ordinal,
            "terminationAccepted": True,
        }

    def abrupt_run(self) -> dict[str, object]:
        return {
            "activationPolicy": 0,
            "appKitProcessAbsentAfterReap": True,
            "exactExecutableIdentityMatchedImmediatelyBeforeSignal": True,
            "exitCode": -signal.SIGKILL,
            "finishedLaunching": True,
            "launchMethod": smoke.ABRUPT_LAUNCH_METHOD,
            "minimumObservationSeconds": 5.0,
            "newProcessIdentifierDetected": True,
            "observationDeadlineReached": True,
            "ordinal": 2,
            "ownedChildProcess": True,
            "persistenceProbePassedBeforeSignal": True,
            "processReaped": True,
            "signalName": "SIGKILL",
            "signalNumber": smoke.SIGKILL_NUMBER,
        }

    def auxiliary(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "filename": filename,
                "integrityCheck": "ok",
            }
            for filename in smoke.clean.AUXILIARY_SQLITE_FILES
        )

    def empty_log(self) -> dict[str, object]:
        return {
            "sha256": smoke.EMPTY_SHA256,
            "size": 0,
        }

    def build_result(
        self,
        root: Path,
        **overrides: object,
    ) -> dict[str, object]:
        migration_sqlite = self.sqlite()
        arguments: dict[str, object] = {
            "release": self.release_inputs(root),
            "release_id": "build-987",
            "app_tree": self.app_tree(),
            "migration_run": self.graceful_run(1),
            "abrupt_run": self.abrupt_run(),
            "recovery_run": self.graceful_run(3),
            "migration_observation": self.observation(
                smoke.recovery.MIGRATION_MODE
            ),
            "abrupt_observation": self.observation(
                smoke.recovery.SQLITE_READBACK_MODE
            ),
            "recovery_observation": self.observation(
                smoke.recovery.SQLITE_READBACK_MODE
            ),
            "migration_sqlite": migration_sqlite,
            "abrupt_sqlite": migration_sqlite,
            "post_abrupt_sqlite": migration_sqlite,
            "recovery_sqlite": migration_sqlite,
            "auxiliary_sqlite": self.auxiliary(),
            "migration_stderr": self.empty_log(),
            "abrupt_stderr": self.empty_log(),
            "recovery_stderr": self.empty_log(),
            "runtime_identity_present": True,
            "snapshot_files": self.snapshot_files(),
        }
        arguments.update(overrides)
        return smoke.build_result(**arguments)  # type: ignore[arg-type]

    def test_result_is_closed_to_post_observation_owned_child_sigkill(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result = self.build_result(Path(temporary_name))

        self.assertEqual(
            set(result),
            {
                "abruptTermination",
                "archiveReadback",
                "canary",
                "image",
                "installation",
                "isolation",
                "launches",
                "limitations",
                "mount",
                "release",
                "schemaVersion",
                "scope",
                "stateRecovery",
                "status",
                "uninstall",
            },
        )
        self.assertEqual(result["scope"], smoke.RESULT_SCOPE)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            result["abruptTermination"]["processDisposition"],
            smoke.ABRUPT_PROCESS_DISPOSITION,
        )
        self.assertIs(
            result["abruptTermination"]["inFlightWriteCheckpointObserved"],
            False,
        )
        self.assertEqual(
            result["launches"]["runs"][1]["launchMethod"],
            smoke.ABRUPT_LAUNCH_METHOD,
        )
        self.assertEqual(
            result["launches"]["runs"][0]["launchMethod"],
            smoke.GRACEFUL_LAUNCH_METHOD,
        )
        self.assertIn(
            "no-in-flight-write-checkpoint-or-open-transaction-observed",
            result["limitations"],
        )
        rendered = repr(result).lower()
        for forbidden in (
            "hotjournal",
            "dirtydatabase",
            "crashduringwrite",
            "productionappendcrashpoint",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_result_rejects_type_identity_and_observation_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            invalid_count = self.sqlite(count=True)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    migration_sqlite=invalid_count,
                    abrupt_sqlite=invalid_count,
                    post_abrupt_sqlite=invalid_count,
                    recovery_sqlite=invalid_count,
                )

            invalid_size = self.sqlite(size=True)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    migration_sqlite=invalid_size,
                    abrupt_sqlite=invalid_size,
                    post_abrupt_sqlite=invalid_size,
                    recovery_sqlite=invalid_size,
                )

            wrong_observation = self.observation(
                smoke.recovery.SQLITE_READBACK_MODE
            )
            wrong_observation["size"] = (
                int(wrong_observation["size"]) + 1
            )
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    abrupt_observation=wrong_observation,
                )

            invalid_run = self.abrupt_run()
            invalid_run["exitCode"] = True
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(root, abrupt_run=invalid_run)

            invalid_run = self.graceful_run(1)
            invalid_run["minimumObservationSeconds"] = float("nan")
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(root, migration_run=invalid_run)

            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    app_tree=self.app_tree(algorithm="sha256-test"),
                )
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    abrupt_stderr={
                        "sha256": hashlib.sha256(b"x").hexdigest(),
                        "size": 1,
                    },
                )

    def owned_cycle(
        self,
        *,
        stdout_payload: bytes | None = None,
        stderr_payload: bytes = b"",
        wait_result: int = -signal.SIGKILL,
        gone: bool = True,
        signal_error: OSError | None = None,
        poll_error_at: int | None = None,
        poll_error: BaseException | None = None,
    ) -> tuple[
        FakeProcess,
        list[str],
        tuple[int, dict[str, object], dict[str, object], dict[str, object]],
    ]:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            app = root / "AetherLink.app"
            executable = app / smoke.installed.EXECUTABLE_RELATIVE_PATH
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"executable")
            stdout_path = root / "stdout.log"
            stderr_path = root / "stderr.log"
            events: list[str] = []
            process = FakeProcess(
                wait_result=wait_result,
                signal_error=signal_error,
                events=events,
                poll_error_at=poll_error_at,
                poll_error=poll_error,
            )
            owned_processes: list[FakeProcess] = []
            status = smoke.engine.ApplicationStatus(
                activation_policy=0,
                bundle_identifier=smoke.engine.EXPECTED_BUNDLE_ID,
                executable_path=str(executable),
                finished_launching=True,
            )

            def popen(
                command: list[str],
                **kwargs: object,
            ) -> FakeProcess:
                self.assertEqual(command[-1], str(executable))
                self.assertIs(kwargs["start_new_session"], True)
                events.append("popen")
                return process

            def readiness(
                _process: FakeProcess,
                expected: Path,
                **_kwargs: object,
            ) -> smoke.engine.ApplicationStatus:
                self.assertEqual(expected, executable)
                stdout_path.write_bytes(
                    (
                        smoke.recovery.expected_observation_line(
                            smoke.recovery.SQLITE_READBACK_MODE
                        )
                        if stdout_payload is None
                        else stdout_payload
                    )
                )
                stderr_path.write_bytes(stderr_payload)
                events.extend(("ready", "observation"))
                return status

            def query(pid: int) -> smoke.engine.ApplicationStatus:
                self.assertEqual(pid, process.pid)
                events.append("identity-query")
                return status

            def persistence_probe() -> None:
                events.append("probe")

            monotonic_values = iter((0.0, 5.0))
            result = smoke.run_owned_abrupt_readback_cycle(
                ordinal=2,
                app_path=app,
                environment={"fixture": "1"},
                profile="(version 1)",
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                readiness_timeout_seconds=1.0,
                observation_seconds=5.0,
                termination_timeout_seconds=2.0,
                persistence_probe=persistence_probe,
                popen_factory=popen,  # type: ignore[arg-type]
                readiness_waiter=readiness,  # type: ignore[arg-type]
                query=query,
                gone_waiter=lambda *_args, **_kwargs: gone,
                monotonic=lambda: next(monotonic_values),
                sleeper=lambda _seconds: None,
                owned_processes=owned_processes,  # type: ignore[arg-type]
            )
            self.assertEqual(owned_processes, [])
            events.append("returned")
            return process, events, result

    def execute_orchestration(
        self,
        *,
        fail_post_abrupt: bool = False,
        fail_root_cleanup: bool = False,
        abrupt_interrupt: BaseException | None = None,
    ) -> tuple[
        list[str],
        BaseException | None,
        dict[str, object] | None,
        bool,
    ]:
        events: list[str] = []
        error: BaseException | None = None
        result: dict[str, object] | None = None
        published = False
        version = smoke.recovery.ReleaseVersion(
            build_number=987,
            marketing_version="9.8.7",
            semantic_version=(9, 8, 7),
        )
        release_id = "aetherlink-9.8.7+987-local-v1"
        tree = self.app_tree()
        sqlite_evidence = self.sqlite()
        auxiliary = self.auxiliary()
        empty_log = self.empty_log()
        snapshot_files = self.snapshot_files(release_id)
        file_identity = smoke.installed.FileIdentity(
            mode=0o600,
            sha256="e" * 64,
            size=123,
        )
        preexisting = ("preexisting-user-application",)
        real_write_legacy = smoke.recovery.write_legacy_fixture
        real_remove_legacy = smoke.recovery.remove_legacy_before_readback

        with tempfile.TemporaryDirectory() as temporary_name:
            outer_root = Path(temporary_name)
            archive_dir = outer_root / "archive"
            archive_dir.mkdir()
            result_path = outer_root / "result.json"
            work_root = outer_root / "work"
            owned_registry: list[object] = []
            sqlite_calls = 0
            removal_calls = 0

            @contextmanager
            def isolated_root(
                *,
                termination_timeout_seconds: float,
            ):
                self.assertEqual(termination_timeout_seconds, 2.0)
                work_root.mkdir()
                events.append("root-enter")
                try:
                    yield work_root, owned_registry
                finally:
                    events.append("root-cleanup")
                    if fail_root_cleanup:
                        raise smoke.LocalDMGSmokeError(
                            "synthetic root cleanup failure"
                        )

            def snapshot_archive(
                _archive_dir: Path,
                *,
                version: smoke.recovery.ReleaseVersion,
                destination_parent: Path,
            ) -> tuple[Path, dict[str, dict[str, object]]]:
                self.assertEqual(version.build_number, 987)
                snapshot = destination_parent / "snapshot"
                snapshot.mkdir(parents=True)
                events.append("snapshot")
                return snapshot, snapshot_files

            def load_release(
                snapshot: Path,
                *,
                verify_readback: bool,
                version: smoke.recovery.ReleaseVersion,
            ) -> smoke.engine.ReleaseInputs:
                self.assertIs(verify_readback, False)
                self.assertEqual(version.build_number, 987)
                events.append("release-load")
                return self.release_inputs(snapshot, release_id)

            def create_app(path: Path) -> Path:
                executable = path / smoke.installed.EXECUTABLE_RELATIVE_PATH
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"fixture-executable")
                return path

            def extract_app(
                _release: smoke.engine.ReleaseInputs,
                destination: Path,
            ) -> Path:
                events.append("extract")
                return create_app(destination / smoke.installed.APP_RELATIVE_PATH)

            def stage_app(_source: Path, staging: Path) -> Path:
                events.append("stage")
                return create_app(staging / smoke.installed.APP_RELATIVE_PATH)

            def copy_image(**kwargs: object) -> smoke.installed.AppTreeEvidence:
                mountpoint = Path(kwargs["mountpoint"])
                installed_app = Path(kwargs["installed_app"])
                label = (
                    "install-initial"
                    if mountpoint.name == "mount-initial"
                    else "install-reinstall"
                )
                events.append(label)
                create_app(installed_app)
                return tree

            def write_legacy(path: Path) -> None:
                events.append("legacy-write")
                real_write_legacy(path)

            def launch_environment(
                _base_environment: object,
                *,
                home: Path,
                temporary: Path,
                identity_file: Path,
                mode: str,
            ) -> dict[str, str]:
                return {
                    "home": str(home),
                    "identity": str(identity_file),
                    "mode": mode,
                    "temporary": str(temporary),
                }

            def launch_services_cycle(
                *,
                ordinal: int,
                environment: dict[str, str],
                stdout_path: Path,
                stderr_path: Path,
                **_kwargs: object,
            ) -> tuple[int, dict[str, object]]:
                mode = environment["mode"]
                if ordinal == 1:
                    self.assertEqual(mode, smoke.recovery.MIGRATION_MODE)
                    events.append("migration-launch")
                    Path(environment["identity"]).write_bytes(b"identity")
                    pid = 101
                else:
                    self.assertEqual(ordinal, 3)
                    self.assertEqual(
                        mode,
                        smoke.recovery.SQLITE_READBACK_MODE,
                    )
                    events.append("recovery-launch")
                    pid = 303
                stdout_path.write_bytes(
                    smoke.recovery.expected_observation_line(mode)
                )
                stderr_path.write_bytes(b"")
                return pid, self.graceful_run(ordinal)

            def observation(
                path: Path,
                mode: str,
            ) -> dict[str, object]:
                events.append(f"observation:{path.name}")
                return self.observation(mode)

            def sqlite_readback(
                _database_path: Path,
            ) -> smoke.recovery.SQLiteCanaryEvidence:
                nonlocal sqlite_calls
                sqlite_calls += 1
                events.append(f"sqlite:{sqlite_calls}")
                if fail_post_abrupt and sqlite_calls == 3:
                    raise smoke.LocalDMGSmokeError(
                        "synthetic post-abrupt readback failure"
                    )
                return sqlite_evidence

            def state_records(
                application_support: Path,
                _identity_file: Path,
            ) -> dict[str, smoke.installed.FileIdentity]:
                records = {
                    "application-support/runtime-chat.sqlite3": (
                        file_identity
                    ),
                    "runtime-identity": file_identity,
                }
                legacy_path = (
                    application_support / smoke.recovery.LEGACY_FILENAME
                )
                if legacy_path.is_file():
                    records[
                        (
                            "application-support/"
                            f"{smoke.recovery.LEGACY_FILENAME}"
                        )
                    ] = file_identity
                events.append(
                    "state-with-legacy"
                    if legacy_path.is_file()
                    else "state-without-legacy"
                )
                return records

            def remove_app(**kwargs: object) -> None:
                nonlocal removal_calls
                removal_calls += 1
                events.append(
                    "initial-remove"
                    if removal_calls == 1
                    else "final-remove"
                )
                app_path = Path(kwargs["app_path"])
                if app_path.exists():
                    smoke.shutil.rmtree(app_path)

            def require_state(*, label: str, **_kwargs: object) -> None:
                events.append(f"state-check:{label}")

            def remove_legacy(
                legacy_path: Path,
                preserved_directory: Path,
            ) -> Path:
                events.append("legacy-move")
                return real_remove_legacy(
                    legacy_path,
                    preserved_directory,
                )

            def owned_cycle(**kwargs: object):
                self.assertIs(kwargs["owned_processes"], owned_registry)
                self.assertEqual(owned_registry, [])
                events.append("owned-observation")
                if abrupt_interrupt is not None:
                    raise abrupt_interrupt
                persistence_probe = kwargs["persistence_probe"]
                assert callable(persistence_probe)
                persistence_probe()
                events.append("owned-signal")
                return (
                    202,
                    self.abrupt_run(),
                    self.observation(
                        smoke.recovery.SQLITE_READBACK_MODE
                    ),
                    empty_log,
                )

            def publish(
                path: Path,
                published_result: dict[str, object],
            ) -> None:
                nonlocal published
                self.assertIn("root-cleanup", events)
                events.append("publish")
                path.write_bytes(
                    smoke.engine.canonical_json_bytes(published_result)
                )
                published = True

            patchers = (
                patch.object(smoke, "current_release", return_value=version),
                patch.object(smoke, "isolated_abrupt_root", isolated_root),
                patch.object(
                    smoke.installed,
                    "list_bundle_applications",
                    return_value=preexisting,
                ),
                patch.object(
                    smoke.upgrade,
                    "snapshot_archive_directory",
                    side_effect=snapshot_archive,
                ),
                patch.object(
                    smoke.upgrade,
                    "verify_archive_readback",
                    side_effect=lambda *_args, **_kwargs: events.append(
                        "archive-readback"
                    ),
                ),
                patch.object(
                    smoke.recovery,
                    "load_release_inputs",
                    side_effect=load_release,
                ),
                patch.object(
                    smoke.engine,
                    "extract_packaged_app",
                    side_effect=extract_app,
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
                    side_effect=stage_app,
                ),
                patch.object(
                    smoke.base,
                    "create_dmg_command",
                    return_value=("create-dmg",),
                ),
                patch.object(
                    smoke.base,
                    "verify_dmg_command",
                    return_value=("verify-dmg",),
                ),
                patch.object(smoke.base, "run_bounded_command"),
                patch.object(
                    smoke.same_dmg,
                    "image_identity",
                    return_value=file_identity,
                ),
                patch.object(smoke.same_dmg, "require_same_image"),
                patch.object(
                    smoke.same_dmg,
                    "copy_same_image",
                    side_effect=copy_image,
                ),
                patch.object(
                    smoke.recovery,
                    "write_legacy_fixture",
                    side_effect=write_legacy,
                ),
                patch.object(
                    smoke.clean,
                    "recovery_launch_environment",
                    side_effect=launch_environment,
                ),
                patch.object(
                    smoke.clean,
                    "run_recovery_launch_services_cycle",
                    side_effect=launch_services_cycle,
                ),
                patch.object(
                    smoke.clean,
                    "validate_captured_log",
                    return_value=empty_log,
                ),
                patch.object(
                    smoke.recovery,
                    "verify_observation_log",
                    side_effect=observation,
                ),
                patch.object(
                    smoke.recovery,
                    "sqlite_canary_evidence",
                    side_effect=sqlite_readback,
                ),
                patch.object(
                    smoke.clean,
                    "auxiliary_sqlite_evidence",
                    return_value=auxiliary,
                ),
                patch.object(
                    smoke.installed,
                    "state_file_records",
                    side_effect=state_records,
                ),
                patch.object(
                    smoke.uninstall,
                    "remove_exact_installed_app",
                    side_effect=remove_app,
                ),
                patch.object(
                    smoke.state,
                    "require_recovery_state",
                    side_effect=require_state,
                ),
                patch.object(
                    smoke.recovery,
                    "remove_legacy_before_readback",
                    side_effect=remove_legacy,
                ),
                patch.object(smoke.engine, "preflight_sandbox"),
                patch.object(
                    smoke,
                    "run_owned_abrupt_readback_cycle",
                    side_effect=owned_cycle,
                ),
                patch.object(
                    smoke.upgrade,
                    "require_unchanged_archive_snapshot",
                    side_effect=lambda *_args, **_kwargs: events.append(
                        "archive-unchanged"
                    ),
                ),
                patch.object(
                    smoke.installed,
                    "assert_preexisting_applications_preserved",
                    side_effect=lambda value: (
                        self.assertEqual(value, preexisting),
                        events.append("preexisting-preserved"),
                    ),
                ),
                patch.object(
                    smoke.state,
                    "publish_result",
                    side_effect=publish,
                ),
            )
            with ExitStack() as stack:
                for patcher in patchers:
                    stack.enter_context(patcher)
                try:
                    result = smoke.execute(
                        archive_dir=archive_dir,
                        result_path=result_path,
                        readiness_timeout_seconds=1.0,
                        observation_seconds=5.0,
                        termination_timeout_seconds=2.0,
                    )
                except BaseException as caught:
                    error = caught

            if published:
                self.assertTrue(result_path.is_file())

        return events, error, result, published

    def test_owned_child_proves_exact_sigkill_reap_after_observation(
        self,
    ) -> None:
        process, events, result = self.owned_cycle()
        pid, run, observation, stderr = result
        self.assertEqual(pid, process.pid)
        self.assertEqual(process.signals, [signal.SIGKILL])
        self.assertEqual(process.waits, [2.0])
        self.assertEqual(run["exitCode"], -signal.SIGKILL)
        self.assertIs(run["processReaped"], True)
        self.assertEqual(
            observation,
            self.observation(smoke.recovery.SQLITE_READBACK_MODE),
        )
        self.assertEqual(stderr, self.empty_log())
        self.assertLess(events.index("observation"), events.index("probe"))
        self.assertLess(events.index("probe"), events.index("identity-query"))
        self.assertLess(events.index("identity-query"), events.index("signal"))
        self.assertLess(events.index("signal"), events.index("wait"))
        self.assertEqual(events[-1], "returned")

    def test_owned_child_rejects_observation_log_and_stderr_drift(
        self,
    ) -> None:
        for label, stdout, stderr in (
            ("stdout", b"wrong\n", b""),
            ("stderr", None, b"unexpected"),
        ):
            with self.subTest(label=label):
                with self.assertRaises(
                    (
                        smoke.LocalDMGSmokeError,
                        smoke.engine.LifecycleSmokeError,
                    )
                ):
                    self.owned_cycle(
                        stdout_payload=stdout,
                        stderr_payload=stderr,
                    )

    def test_owned_child_rejects_wrong_exit_or_appkit_residue(
        self,
    ) -> None:
        with self.assertRaises(smoke.LocalDMGSmokeError):
            self.owned_cycle(wait_result=0)
        with self.assertRaises(smoke.LocalDMGSmokeError):
            self.owned_cycle(gone=False)

    def test_owned_child_signal_failure_cleans_up_without_pass_evidence(
        self,
    ) -> None:
        with self.assertRaises(OSError):
            self.owned_cycle(signal_error=OSError("synthetic signal failure"))

    def test_cleanup_owned_child_retries_signal_and_wait_then_reaps(
        self,
    ) -> None:
        class RetryProcess(FakeProcess):
            def wait(self, timeout: float) -> int:
                if self.events is not None:
                    self.events.append("wait")
                self.waits.append(timeout)
                if len(self.waits) == 1:
                    raise subprocess.TimeoutExpired("fixture", timeout)
                self.returncode = self.wait_result
                return self.wait_result

        events: list[str] = []
        process = RetryProcess(
            signal_error=OSError("synthetic first signal failure"),
            events=events,
        )
        smoke._cleanup_owned_child(process, timeout_seconds=2.0)

        self.assertEqual(process.signals, [signal.SIGKILL, signal.SIGKILL])
        self.assertEqual(process.waits, [2.0, 2.0])
        self.assertEqual(process.poll(), -signal.SIGKILL)
        self.assertEqual(events, ["signal", "wait", "signal", "wait"])

    def test_cleanup_owned_child_fails_closed_after_two_attempts(
        self,
    ) -> None:
        class StuckProcess(FakeProcess):
            def poll(self) -> None:
                return None

            def send_signal(self, sent_signal: int) -> None:
                self.signals.append(sent_signal)
                raise OSError("synthetic persistent signal failure")

            def wait(self, timeout: float) -> int:
                self.waits.append(timeout)
                raise subprocess.TimeoutExpired("fixture", timeout)

        process = StuckProcess()
        with self.assertRaisesRegex(
            smoke.LocalDMGSmokeError,
            "could not prove reap",
        ):
            smoke._cleanup_owned_child(process, timeout_seconds=2.0)

        self.assertEqual(process.signals, [signal.SIGKILL, signal.SIGKILL])
        self.assertEqual(process.waits, [2.0, 2.0])

    def test_cleanup_owned_child_reaps_then_rethrows_interrupts(
        self,
    ) -> None:
        class InterruptingProcess(FakeProcess):
            def __init__(
                self,
                *,
                stage: str,
                interruption: BaseException,
            ) -> None:
                super().__init__()
                self.stage = stage
                self.interruption = interruption
                self.injected = False

            def maybe_interrupt(self, stage: str) -> None:
                if self.stage == stage and not self.injected:
                    self.injected = True
                    raise self.interruption

            def poll(self) -> int | None:
                self.maybe_interrupt("poll")
                return super().poll()

            def send_signal(self, sent_signal: int) -> None:
                self.maybe_interrupt("signal")
                super().send_signal(sent_signal)

            def wait(self, timeout: float) -> int:
                self.maybe_interrupt("wait")
                return super().wait(timeout)

        for stage in ("poll", "signal", "wait"):
            for exception_type in (KeyboardInterrupt, SystemExit):
                with self.subTest(
                    stage=stage,
                    exception_type=exception_type.__name__,
                ):
                    interruption = (
                        KeyboardInterrupt()
                        if exception_type is KeyboardInterrupt
                        else SystemExit(17)
                    )
                    process = InterruptingProcess(
                        stage=stage,
                        interruption=interruption,
                    )
                    with self.assertRaises(exception_type):
                        smoke._cleanup_owned_child(
                            process,
                            timeout_seconds=2.0,
                        )
                    self.assertEqual(
                        process.returncode,
                        -signal.SIGKILL,
                    )
                    self.assertGreaterEqual(len(process.signals), 1)
                    self.assertGreaterEqual(len(process.waits), 1)

    def test_registry_removal_poll_rethrows_interrupts(
        self,
    ) -> None:
        for interruption in (KeyboardInterrupt(), SystemExit(17)):
            with self.subTest(type=type(interruption).__name__):
                with self.assertRaises(type(interruption)):
                    self.owned_cycle(
                        poll_error_at=2,
                        poll_error=interruption,
                    )

    def test_isolated_root_cleans_owned_child_before_app_mounts_and_root(
        self,
    ) -> None:
        events: list[str] = []
        removed_root: Path | None = None

        def cleanup_child(
            _process: FakeProcess,
            *,
            timeout_seconds: float,
        ) -> None:
            self.assertEqual(timeout_seconds, 2.0)
            events.append("child")

        def cleanup_apps(
            _root: Path,
            *,
            termination_timeout_seconds: float,
        ) -> None:
            self.assertEqual(termination_timeout_seconds, 2.0)
            events.append("apps")

        def recover_unmount(*, dmg_path: Path, mountpoint: Path) -> None:
            self.assertEqual(dmg_path.name, "local-image.dmg")
            events.append(f"unmount:{mountpoint.name}")

        def remove_root(path: Path) -> None:
            nonlocal removed_root
            removed_root = path
            events.append("root")

        with (
            patch.object(smoke, "_cleanup_owned_child", cleanup_child),
            patch.object(
                smoke.upgrade,
                "cleanup_exact_temporary_applications",
                cleanup_apps,
            ),
            patch.object(
                smoke.same_dmg,
                "recover_unmount",
                recover_unmount,
            ),
            patch.object(smoke.shutil, "rmtree", remove_root),
        ):
            with smoke.isolated_abrupt_root(
                termination_timeout_seconds=2.0,
            ) as (temporary_root, owned_processes):
                events.append("body")
                owned_processes.append(FakeProcess())  # type: ignore[arg-type]

        self.assertEqual(
            events,
            [
                "body",
                "child",
                "apps",
                "unmount:mount-initial",
                "unmount:mount-reinstall",
                "root",
            ],
        )
        self.assertEqual(removed_root, temporary_root)
        smoke.shutil.rmtree(temporary_root)

    def test_isolated_root_retains_diagnostics_when_child_cleanup_fails(
        self,
    ) -> None:
        retained_root: Path | None = None
        with (
            patch.object(
                smoke,
                "_cleanup_owned_child",
                side_effect=smoke.LocalDMGSmokeError("synthetic stuck child"),
            ),
            patch.object(
                smoke.upgrade,
                "cleanup_exact_temporary_applications",
            ),
            patch.object(smoke.same_dmg, "recover_unmount"),
            self.assertRaisesRegex(
                smoke.LocalDMGSmokeError,
                "diagnostic root retained",
            ),
        ):
            with smoke.isolated_abrupt_root(
                termination_timeout_seconds=2.0,
            ) as (temporary_root, owned_processes):
                retained_root = temporary_root
                owned_processes.append(FakeProcess())  # type: ignore[arg-type]

        self.assertIsNotNone(retained_root)
        assert retained_root is not None
        self.assertTrue(retained_root.is_dir())
        smoke.shutil.rmtree(retained_root)

    def test_isolated_root_preserves_body_interrupt_when_cleanup_fails(
        self,
    ) -> None:
        for interruption in (KeyboardInterrupt(), SystemExit(17)):
            retained_root: Path | None = None
            with self.subTest(type=type(interruption).__name__):
                with (
                    patch.object(
                        smoke.upgrade,
                        "cleanup_exact_temporary_applications",
                        side_effect=OSError("synthetic app cleanup failure"),
                    ),
                    patch.object(smoke.same_dmg, "recover_unmount"),
                    self.assertRaises(type(interruption)) as caught,
                ):
                    with smoke.isolated_abrupt_root(
                        termination_timeout_seconds=2.0,
                    ) as (temporary_root, _owned_processes):
                        retained_root = temporary_root
                        raise interruption

                self.assertIsInstance(
                    caught.exception.__cause__,
                    smoke.LocalDMGSmokeError,
                )
                assert caught.exception.__cause__ is not None
                self.assertIn(
                    "diagnostic root retained",
                    str(caught.exception.__cause__),
                )
                self.assertIsNotNone(retained_root)
                assert retained_root is not None
                self.assertTrue(retained_root.is_dir())
                smoke.shutil.rmtree(retained_root)

    def test_execute_orders_recovery_cleanup_and_publication(
        self,
    ) -> None:
        events, error, result, published = self.execute_orchestration()

        self.assertIsNone(error)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "passed")
        self.assertIs(published, True)
        for earlier, later in (
            ("migration-launch", "initial-remove"),
            ("initial-remove", "legacy-move"),
            ("legacy-move", "install-reinstall"),
            ("owned-observation", "sqlite:2"),
            ("sqlite:2", "owned-signal"),
            ("owned-signal", "sqlite:3"),
            ("sqlite:3", "recovery-launch"),
            ("recovery-launch", "final-remove"),
            ("final-remove", "preexisting-preserved"),
            ("preexisting-preserved", "root-cleanup"),
            ("root-cleanup", "publish"),
        ):
            self.assertLess(
                events.index(earlier),
                events.index(later),
                f"{earlier} must occur before {later}: {events!r}",
            )

    def test_execute_failure_after_signal_or_during_cleanup_never_publishes(
        self,
    ) -> None:
        for label, arguments, expected_message in (
            (
                "post-abrupt readback",
                {"fail_post_abrupt": True},
                "post-abrupt readback failure",
            ),
            (
                "root cleanup",
                {"fail_root_cleanup": True},
                "root cleanup failure",
            ),
        ):
            with self.subTest(label=label):
                events, error, result, published = (
                    self.execute_orchestration(**arguments)
                )
                self.assertIsInstance(error, smoke.LocalDMGSmokeError)
                assert error is not None
                self.assertIn(expected_message, str(error))
                self.assertIsNone(result)
                self.assertIs(published, False)
                self.assertIn("root-cleanup", events)
                self.assertNotIn("publish", events)

    def test_execute_interrupts_cleanup_root_and_block_publication(
        self,
    ) -> None:
        for interruption in (KeyboardInterrupt(), SystemExit(17)):
            with self.subTest(type=type(interruption).__name__):
                events, error, result, published = (
                    self.execute_orchestration(
                        abrupt_interrupt=interruption,
                    )
                )
                self.assertIsInstance(error, type(interruption))
                self.assertIsNone(result)
                self.assertIs(published, False)
                self.assertIn("owned-observation", events)
                self.assertIn("root-cleanup", events)
                self.assertNotIn("publish", events)

    def test_repeatability_publishes_exact_result_and_receipt_pair(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            archive = root / "archive"
            calls: list[Path] = []

            def execute(**kwargs: object) -> dict[str, object]:
                path = Path(kwargs["result_path"])
                result = {
                    "schemaVersion": 1,
                    "scope": smoke.RESULT_SCOPE,
                    "status": "passed",
                }
                path.write_bytes(smoke.engine.canonical_json_bytes(result))
                calls.append(path)
                return result

            version = smoke.recovery.ReleaseVersion(
                build_number=987,
                marketing_version="9.8.7",
                semantic_version=(9, 8, 7),
            )
            with (
                patch.object(smoke, "execute", side_effect=execute),
                patch.object(
                    smoke,
                    "current_release",
                    return_value=version,
                ),
            ):
                receipt = smoke.execute_repeatability(
                    archive_dir=archive,
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=5.0,
                    termination_timeout_seconds=1.0,
                )

            self.assertEqual(len(calls), 2)
            self.assertEqual(receipt["runCount"], 2)
            self.assertIs(receipt["resultBytesEqual"], True)
            self.assertEqual(
                receipt["releaseId"],
                "aetherlink-9.8.7+987-local-v1",
            )
            self.assertEqual(
                result_path.read_bytes(),
                smoke.engine.canonical_json_bytes(
                    {
                        "schemaVersion": 1,
                        "scope": smoke.RESULT_SCOPE,
                        "status": "passed",
                    }
                ),
            )
            self.assertEqual(
                receipt_path.read_bytes(),
                smoke.engine.canonical_json_bytes(receipt),
            )

    def test_repeatability_mismatch_publishes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            counter = 0

            def execute(**kwargs: object) -> dict[str, object]:
                nonlocal counter
                counter += 1
                result = {
                    "ordinal": counter,
                    "status": "passed",
                }
                Path(kwargs["result_path"]).write_bytes(
                    smoke.engine.canonical_json_bytes(result)
                )
                return result

            with (
                patch.object(smoke, "execute", side_effect=execute),
                self.assertRaises(smoke.LocalDMGSmokeError),
            ):
                smoke.execute_repeatability(
                    archive_dir=root / "archive",
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=5.0,
                    termination_timeout_seconds=1.0,
                )
            self.assertFalse(result_path.exists())
            self.assertFalse(receipt_path.exists())

    def test_defaults_and_interrupt_exit_track_current_release(self) -> None:
        version = smoke.recovery.ReleaseVersion(
            build_number=987,
            marketing_version="9.8.7",
            semantic_version=(9, 8, 7),
        )
        with patch.object(smoke, "current_release", return_value=version):
            self.assertEqual(
                smoke.default_result_path().name,
                (
                    "macos-packaged-app-build-987-local-dmg-uninstall-"
                    "reinstall-abrupt-process-state-recovery-v1.json"
                ),
            )
            self.assertEqual(
                smoke.default_repeatability_result_path().name,
                (
                    "macos-packaged-app-build-987-local-dmg-uninstall-"
                    "reinstall-abrupt-process-state-recovery-"
                    "repeatability-v1.json"
                ),
            )

        with (
            patch.object(smoke, "execute_repeatability", side_effect=KeyboardInterrupt),
            patch.object(smoke.sys, "stderr", new=io.StringIO()),
        ):
            self.assertEqual(smoke.main([]), 130)


if __name__ == "__main__":
    unittest.main()
