#!/usr/bin/env python3
"""Tests for same-DMG uninstall/reinstall state-recovery qualification."""

from __future__ import annotations

import copy
from contextlib import contextmanager, ExitStack
import hashlib
import io
from pathlib import Path
import tempfile
from typing import Iterator
import unittest
from unittest.mock import patch

from script import (
    run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke as smoke,
)


class LocalDMGUninstallReinstallStateRecoverySmokeTests(
    unittest.TestCase
):
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
        sha256: str = "d" * 64,
    ) -> smoke.installed.AppTreeEvidence:
        return smoke.installed.AppTreeEvidence(
            digest_algorithm="sha256-test-v1",
            file_count=3,
            sha256=sha256,
            total_bytes=123,
        )

    def canary(
        self,
        *,
        count: int = 1,
    ) -> smoke.recovery.SQLiteCanaryEvidence:
        return smoke.recovery.SQLiteCanaryEvidence(
            event_json_sha256=smoke.recovery.CANARY_EVENT_JSON_SHA256,
            event_json_size=len(smoke.recovery.CANARY_EVENT_JSON),
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

    def launch_record(self, ordinal: int) -> dict[str, object]:
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

    def auxiliary(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "filename": filename,
                "integrityCheck": "ok",
            }
            for filename in smoke.clean.AUXILIARY_SQLITE_FILES
        )

    def build_result(
        self,
        root: Path,
        **overrides: object,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {
            "release": self.release_inputs(root),
            "release_id": "build-987",
            "app_tree": self.app_tree(),
            "runs": (
                self.launch_record(1),
                self.launch_record(2),
            ),
            "migration_observation": self.observation(
                smoke.recovery.MIGRATION_MODE
            ),
            "sqlite_readback_observation": self.observation(
                smoke.recovery.SQLITE_READBACK_MODE
            ),
            "migration_sqlite": self.canary(),
            "sqlite_readback_sqlite": self.canary(),
            "auxiliary_sqlite": self.auxiliary(),
            "runtime_identity_present": True,
            "snapshot_files": self.snapshot_files(),
        }
        arguments.update(overrides)
        return smoke.build_result(**arguments)  # type: ignore[arg-type]

    def test_result_is_closed_to_nonempty_same_dmg_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result = self.build_result(Path(temporary_name))

        self.assertEqual(
            set(result),
            {
                "archiveReadback",
                "canary",
                "image",
                "installation",
                "isolation",
                "launchServices",
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
        self.assertEqual(result["schemaVersion"], 1)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            result["archiveReadback"]["snapshotFiles"],
            self.snapshot_files(),
        )
        self.assertEqual(result["installation"]["installCount"], 2)
        self.assertIs(
            result["installation"]["statePresentBeforeReinstall"],
            True,
        )
        self.assertEqual(result["mount"]["cycleCount"], 2)
        self.assertEqual(result["uninstall"]["removalCount"], 2)
        recovery_result = result["stateRecovery"]
        self.assertEqual(recovery_result["databaseCount"], 3)
        self.assertEqual(recovery_result["totalEventCount"], 1)
        self.assertEqual(
            recovery_result["migrationSQLite"],
            recovery_result["sqliteReadbackSQLite"],
        )
        self.assertIs(
            recovery_result["legacyRemovedByHarnessBeforeReinstall"],
            True,
        )
        self.assertIn(
            "legacy-fixture-removed-by-harness-before-reinstall-readback",
            result["limitations"],
        )

    def test_result_rejects_boolean_counts_and_contract_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            for value in (False, 0, 1, None):
                with self.subTest(runtime_identity=value):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        self.build_result(
                            root,
                            runtime_identity_present=value,
                        )

            invalid_runs: list[object] = [
                (self.launch_record(1),),
                (
                    self.launch_record(2),
                    self.launch_record(1),
                ),
            ]
            boolean_ordinal = self.launch_record(1)
            boolean_ordinal["ordinal"] = True
            invalid_runs.append(
                (boolean_ordinal, self.launch_record(2))
            )
            boolean_observation = self.launch_record(1)
            boolean_observation["minimumObservationSeconds"] = True
            invalid_runs.append(
                (boolean_observation, self.launch_record(2))
            )
            for value in (
                float("nan"),
                float("inf"),
                float("-inf"),
                30.000_001,
            ):
                invalid_duration = self.launch_record(1)
                invalid_duration["minimumObservationSeconds"] = value
                invalid_runs.append(
                    (invalid_duration, self.launch_record(2))
                )
            for runs in invalid_runs:
                with self.subTest(runs=runs):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        self.build_result(root, runs=runs)

            wrong_observation = self.observation(
                smoke.recovery.MIGRATION_MODE
            )
            wrong_observation["size"] = True
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    migration_observation=wrong_observation,
                )
            wrong_observation = self.observation(
                smoke.recovery.MIGRATION_MODE
            )
            sha256 = str(wrong_observation["sha256"])
            wrong_observation["sha256"] = (
                ("0" if sha256[0] != "0" else "1") + sha256[1:]
            )
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    migration_observation=wrong_observation,
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
                    sqlite_readback_observation=wrong_observation,
                )

            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    sqlite_readback_sqlite=self.canary(count=2),
                )
            boolean_count = self.canary(count=True)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    migration_sqlite=boolean_count,
                    sqlite_readback_sqlite=boolean_count,
                )
            boolean_size = smoke.recovery.SQLiteCanaryEvidence(
                event_json_sha256=(
                    smoke.recovery.CANARY_EVENT_JSON_SHA256
                ),
                event_json_size=True,
                integrity_check="ok",
                total_event_count=1,
            )
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(
                    root,
                    migration_sqlite=boolean_size,
                    sqlite_readback_sqlite=boolean_size,
                )
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(root, auxiliary_sqlite=())

            snapshot = copy.deepcopy(self.snapshot_files())
            snapshot["build-987.zip"]["size"] = True
            with self.assertRaises(smoke.LocalDMGSmokeError):
                self.build_result(root, snapshot_files=snapshot)

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
                "macos-packaged-app-build-987-local-dmg-"
                "uninstall-reinstall-state-recovery-v1.json",
            )

        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            archive = root / "archive"
            archive.mkdir()
            for result in (archive, archive / "result.json"):
                with self.subTest(result=result):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.same_dmg.require_result_outside_archive(
                            result,
                            archive,
                        )
            smoke.same_dmg.require_result_outside_archive(
                root / "result.json",
                archive,
            )

    def test_recovery_state_comparison_rejects_each_drift(self) -> None:
        expected_sqlite = self.canary()
        expected_auxiliary = self.auxiliary()
        expected_files = {
            "runtime-identity.json": smoke.installed.FileIdentity(
                mode=0o600,
                sha256="1" * 64,
                size=20,
            )
        }
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            application_support = root / "Application Support/AetherLink"
            application_support.mkdir(parents=True)
            identity_file = root / "runtime-identity.json"
            legacy_path = (
                application_support / smoke.recovery.LEGACY_FILENAME
            )

            with (
                patch.object(
                    smoke.recovery,
                    "sqlite_canary_evidence",
                    return_value=expected_sqlite,
                ),
                patch.object(
                    smoke.clean,
                    "auxiliary_sqlite_evidence",
                    return_value=expected_auxiliary,
                ),
                patch.object(
                    smoke.installed,
                    "state_file_records",
                    return_value=expected_files,
                ),
            ):
                smoke.require_recovery_state(
                    label="baseline",
                    application_support=application_support,
                    identity_file=identity_file,
                    expected_sqlite=expected_sqlite,
                    expected_auxiliary=expected_auxiliary,
                    expected_files=expected_files,
                    legacy_must_be_absent=True,
                )
                legacy_path.write_bytes(b"reappeared")
                with self.assertRaises(smoke.LocalDMGSmokeError):
                    smoke.require_recovery_state(
                        label="legacy drift",
                        application_support=application_support,
                        identity_file=identity_file,
                        expected_sqlite=expected_sqlite,
                        expected_auxiliary=expected_auxiliary,
                        expected_files=expected_files,
                        legacy_must_be_absent=True,
                    )

            changed_files = {
                "runtime-identity.json": smoke.installed.FileIdentity(
                    mode=0o600,
                    sha256="2" * 64,
                    size=20,
                )
            }
            with (
                patch.object(
                    smoke.recovery,
                    "sqlite_canary_evidence",
                    return_value=expected_sqlite,
                ),
                patch.object(
                    smoke.clean,
                    "auxiliary_sqlite_evidence",
                    return_value=expected_auxiliary,
                ),
                patch.object(
                    smoke.installed,
                    "state_file_records",
                    return_value=changed_files,
                ),
                self.assertRaises(smoke.LocalDMGSmokeError),
            ):
                smoke.require_recovery_state(
                    label="file drift",
                    application_support=application_support,
                    identity_file=identity_file,
                    expected_sqlite=expected_sqlite,
                    expected_auxiliary=expected_auxiliary,
                    expected_files=expected_files,
                    legacy_must_be_absent=False,
                )

    def test_preserved_legacy_requires_exact_regular_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            legacy = root / smoke.recovery.LEGACY_FILENAME
            legacy.write_bytes(smoke.recovery.CANARY_LEGACY_BYTES)
            smoke.require_preserved_legacy(legacy)
            legacy.write_bytes(b"changed")
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.require_preserved_legacy(legacy)
            legacy.unlink()
            target = root / "target"
            target.write_bytes(smoke.recovery.CANARY_LEGACY_BYTES)
            legacy.symlink_to(target)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.require_preserved_legacy(legacy)

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
            canary = self.canary()
            auxiliary = self.auxiliary()
            state_with_legacy = {
                (
                    "application-support/"
                    f"{smoke.recovery.LEGACY_FILENAME}"
                ): smoke.installed.FileIdentity(
                    mode=0o600,
                    sha256=smoke.recovery.CANARY_LEGACY_SHA256,
                    size=len(smoke.recovery.CANARY_LEGACY_BYTES),
                ),
                "runtime-identity.json": smoke.installed.FileIdentity(
                    mode=0o600,
                    sha256="1" * 64,
                    size=20,
                ),
            }
            state_without_legacy = {
                "runtime-identity.json": state_with_legacy[
                    "runtime-identity.json"
                ]
            }
            events: list[str] = []
            copy_mounts: list[Path] = []
            copy_images: list[Path] = []
            state_records = iter(
                (state_with_legacy, state_without_legacy)
            )

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
                    if failure == "root-cleanup":
                        raise smoke.LocalDMGSmokeError(
                            "synthetic cleanup failure"
                        )

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
                self.assertEqual(version, version_value)
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

            def copy_image(
                **keywords: object,
            ) -> smoke.installed.AppTreeEvidence:
                copy_mounts.append(Path(keywords["mountpoint"]))
                copy_images.append(Path(keywords["dmg_path"]))
                events.append(f"copy-{len(copy_mounts)}")
                return tree

            def write_fixture(path: Path) -> None:
                events.append("fixture")
                path.parent.mkdir(parents=True)
                path.write_bytes(smoke.recovery.CANARY_LEGACY_BYTES)

            def launch(**keywords: object) -> tuple[int, dict[str, object]]:
                ordinal = int(keywords["ordinal"])
                events.append(f"launch-{ordinal}")
                if failure == "interrupt" and ordinal == 1:
                    raise KeyboardInterrupt
                if ordinal == 1:
                    identity = root / "work/state/runtime-identity.json"
                    identity.write_bytes(b"identity")
                pid = 101 if ordinal == 1 else 102
                if failure == "pid-reuse" and ordinal == 2:
                    pid = 101
                return pid, self.launch_record(ordinal)

            observation_calls = 0

            def observe(_path: Path, mode: str) -> dict[str, object]:
                nonlocal observation_calls
                observation_calls += 1
                events.append(f"observation-{observation_calls}")
                return self.observation(mode)

            sqlite_calls = 0

            def observe_sqlite(
                _path: Path,
            ) -> smoke.recovery.SQLiteCanaryEvidence:
                nonlocal sqlite_calls
                sqlite_calls += 1
                events.append(f"sqlite-{sqlite_calls}")
                return canary

            auxiliary_calls = 0

            def observe_auxiliary(
                _path: Path,
            ) -> tuple[dict[str, object], ...]:
                nonlocal auxiliary_calls
                auxiliary_calls += 1
                events.append(f"auxiliary-{auxiliary_calls}")
                return auxiliary

            removal_count = 0

            def remove(**_keywords: object) -> None:
                nonlocal removal_count
                removal_count += 1
                events.append(f"remove-{removal_count}")

            def compare_state(**_keywords: object) -> None:
                events.append("state-check")
                if failure == "state-drift":
                    raise smoke.LocalDMGSmokeError(
                        "synthetic state drift"
                    )

            def preserve_legacy(
                legacy: Path,
                destination: Path,
            ) -> Path:
                events.append("preserve-legacy")
                destination.mkdir()
                preserved = destination / legacy.name
                legacy.replace(preserved)
                return preserved

            image_checks = 0

            def check_image(
                _path: Path,
                _expected: smoke.installed.FileIdentity,
            ) -> None:
                nonlocal image_checks
                image_checks += 1
                events.append(f"image-check-{image_checks}")
                if failure == "image-drift" and image_checks == 2:
                    raise smoke.LocalDMGSmokeError(
                        "synthetic image drift"
                    )

            def recheck(
                _directory: Path,
                _files: dict[str, dict[str, object]],
            ) -> None:
                events.append("snapshot-recheck")
                if failure == "snapshot-drift":
                    raise smoke.engine.LifecycleSmokeError(
                        "synthetic snapshot drift"
                    )

            def publish(
                _path: Path,
                _result: dict[str, object],
            ) -> None:
                events.append("publish")

            version_value = version
            patches = (
                patch.object(smoke, "current_release", return_value=version),
                patch.object(
                    smoke,
                    "release_id_for",
                    return_value="build-987",
                ),
                patch.object(
                    smoke.same_dmg,
                    "isolated_dmg_root",
                    side_effect=root_context,
                ),
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
                patch.object(
                    smoke.same_dmg,
                    "image_identity",
                    return_value=smoke.installed.FileIdentity(
                        mode=0o600,
                        sha256="9" * 64,
                        size=100,
                    ),
                ),
                patch.object(
                    smoke.same_dmg,
                    "require_same_image",
                    side_effect=check_image,
                ),
                patch.object(
                    smoke.same_dmg,
                    "copy_same_image",
                    side_effect=copy_image,
                ),
                patch.object(
                    smoke.recovery,
                    "write_legacy_fixture",
                    side_effect=write_fixture,
                ),
                patch.object(
                    smoke.clean,
                    "recovery_launch_environment",
                    return_value={"QA": "1"},
                ),
                patch.object(
                    smoke.clean,
                    "run_recovery_launch_services_cycle",
                    side_effect=launch,
                ),
                patch.object(smoke.clean, "validate_captured_log"),
                patch.object(
                    smoke.recovery,
                    "verify_observation_log",
                    side_effect=observe,
                ),
                patch.object(
                    smoke.recovery,
                    "sqlite_canary_evidence",
                    side_effect=observe_sqlite,
                ),
                patch.object(
                    smoke.clean,
                    "auxiliary_sqlite_evidence",
                    side_effect=observe_auxiliary,
                ),
                patch.object(
                    smoke.installed,
                    "state_file_records",
                    side_effect=lambda *_args: next(state_records),
                ),
                patch.object(
                    smoke.uninstall,
                    "remove_exact_installed_app",
                    side_effect=remove,
                ),
                patch.object(
                    smoke,
                    "require_recovery_state",
                    side_effect=compare_state,
                ),
                patch.object(
                    smoke.recovery,
                    "remove_legacy_before_readback",
                    side_effect=preserve_legacy,
                ),
                patch.object(smoke, "require_preserved_legacy"),
                patch.object(
                    smoke.upgrade,
                    "require_unchanged_archive_snapshot",
                    side_effect=recheck,
                ),
                patch.object(
                    smoke.installed,
                    "assert_preexisting_applications_preserved",
                    side_effect=lambda _apps: events.append(
                        "preserve-apps"
                    ),
                ),
                patch.object(smoke, "publish_result", side_effect=publish),
            )
            with ExitStack() as stack:
                for context in patches:
                    stack.enter_context(context)
                expected_error: type[BaseException] | tuple[type[BaseException], ...]
                if failure == "interrupt":
                    expected_error = KeyboardInterrupt
                else:
                    expected_error = (
                        smoke.LocalDMGSmokeError,
                        smoke.engine.LifecycleSmokeError,
                    )
                if failure is None:
                    arguments = {
                        "archive_dir": archive_dir,
                        "readiness_timeout_seconds": 1.0,
                        "observation_seconds": 5.0,
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
                    with self.assertRaises(expected_error):
                        smoke.execute(
                            archive_dir=archive_dir,
                            result_path=result_path,
                            readiness_timeout_seconds=1.0,
                            observation_seconds=5.0,
                            termination_timeout_seconds=1.0,
                        )
            if len(copy_mounts) == 2:
                self.assertNotEqual(copy_mounts[0], copy_mounts[1])
                self.assertEqual(copy_images[0], copy_images[1])
            return events

    def test_execute_cleans_root_before_publishing(self) -> None:
        events = self.exercise()
        self.assertEqual(events.count("copy-1"), 1)
        self.assertEqual(events.count("copy-2"), 1)
        self.assertEqual(events.count("remove-1"), 1)
        self.assertEqual(events.count("remove-2"), 1)
        self.assertEqual(events.count("state-check"), 4)
        self.assertLess(events.index("root-cleanup"), events.index("publish"))
        self.assertLess(
            events.index("snapshot-recheck"),
            events.index("root-cleanup"),
        )

    def test_exercise_cleans_root_without_publishing(self) -> None:
        events = self.exercise(publish_result=False)
        self.assertEqual(events[-1], "root-cleanup")
        self.assertNotIn("publish", events)

    def test_failures_and_interrupt_block_publication(self) -> None:
        for failure in (
            "image-drift",
            "pid-reuse",
            "root-cleanup",
            "snapshot-drift",
            "state-drift",
            "interrupt",
        ):
            with self.subTest(failure=failure):
                events = self.exercise(failure=failure)
                self.assertIn("root-cleanup", events)
                self.assertNotIn("publish", events)

    def test_publisher_is_idempotent_and_refuses_different_bytes(self) -> None:
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

    def test_main_is_path_free_and_interrupt_is_distinct(self) -> None:
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
            (
                "Local DMG uninstall/reinstall state-recovery "
                "smoke failed.\n"
            ),
        )
        self.assertNotIn("/private/sensitive", stderr.getvalue())

        stderr = io.StringIO()
        with (
            patch.object(smoke, "execute", side_effect=KeyboardInterrupt),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(smoke.main([]), 130)
        self.assertEqual(
            stderr.getvalue(),
            (
                "Local DMG uninstall/reinstall state-recovery "
                "smoke interrupted.\n"
            ),
        )


if __name__ == "__main__":
    unittest.main()
