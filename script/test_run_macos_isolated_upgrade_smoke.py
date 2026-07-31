#!/usr/bin/env python3
"""Tests for the isolated latest-two-build macOS upgrade smoke runner."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_isolated_upgrade_smoke as smoke


class IsolatedUpgradeSmokeTests(unittest.TestCase):
    def create_app(self, app_path: Path, marker: bytes) -> None:
        executable = app_path / smoke.installed.EXECUTABLE_RELATIVE_PATH
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture-executable-" + marker)
        executable.chmod(0o755)
        resource = app_path / "Contents/Resources/fixture.txt"
        resource.parent.mkdir(parents=True)
        resource.write_bytes(b"fixture-resource-" + marker)
        resource.chmod(0o644)

    def release_for_app(
        self,
        app_path: Path,
        *,
        archive_sha256: str,
        manifest_sha256: str,
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
            archive_sha256=archive_sha256,
            manifest_sha256=manifest_sha256,
            manifest={"members": members},
        )

    def repeatability_fixture_result(
        self,
        marker: object = "stable",
    ) -> dict[str, object]:
        return {
            "fixture": marker,
            "releases": {
                "from": {
                    "releaseId": "aetherlink-1.0.0+23-local-v1",
                },
                "to": {
                    "releaseId": "aetherlink-1.0.0+24-local-v1",
                },
            },
            "schemaVersion": smoke.RESULT_SCHEMA_VERSION,
            "scope": smoke.RESULT_SCOPE,
            "status": "passed",
        }

    def test_archive_readback_modes_are_explicit_and_source_free(
        self,
    ) -> None:
        calls: list[tuple[list[str], Path | None]] = []

        def runner(
            command: list[str],
            *,
            cwd: Path | None = None,
        ) -> object:
            calls.append((command, cwd))
            return object()

        previous = Path("/tmp/aetherlink-previous")
        current = Path("/tmp/aetherlink-current")
        smoke.verify_archive_readback(
            previous,
            historical=True,
            runner=runner,
        )
        smoke.verify_archive_readback(
            current,
            historical=False,
            runner=runner,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], smoke.ROOT)
        self.assertEqual(calls[1][1], smoke.ROOT)
        self.assertIn("--historical", calls[0][0])
        self.assertNotIn("--no-current-source", calls[0][0])
        self.assertIn("--no-current-source", calls[1][0])
        self.assertNotIn("--historical", calls[1][0])

    def test_archive_snapshot_is_stable_and_rechecked_after_use(
        self,
    ) -> None:
        version = smoke.ReleaseVersion(23, "1.0.0", (1, 0, 0))
        release_id = smoke.recovery.release_id_for(version)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            archive = root / "source" / release_id
            archive.mkdir(parents=True)
            source_payloads = {
                f"{release_id}.manifest.json": b"fixture-manifest",
                f"{release_id}.zip": b"fixture-zip",
                f"{release_id}.zip.sha256": b"fixture-checksum\n",
            }
            for name, payload in source_payloads.items():
                (archive / name).write_bytes(payload)

            snapshot, identities = smoke.snapshot_archive_directory(
                archive,
                version=version,
                destination_parent=root / "snapshots",
            )
            snapshot_payloads = {
                name: (snapshot / name).read_bytes()
                for name in source_payloads
            }
            for name in source_payloads:
                (archive / name).write_bytes(b"changed-source")

            self.assertEqual(snapshot_payloads, source_payloads)
            for name, payload in source_payloads.items():
                self.assertEqual(
                    identities[name],
                    {
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                    },
                )
            smoke.require_unchanged_archive_snapshot(
                snapshot,
                identities,
            )
            first_name = sorted(source_payloads)[0]
            (snapshot / first_name).write_bytes(b"changed-snapshot")
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "changed after exercise",
            ):
                smoke.require_unchanged_archive_snapshot(
                    snapshot,
                    identities,
                )

    def test_cleanup_failure_retains_diagnostic_root(self) -> None:
        captured_root: Path | None = None

        def applications() -> tuple[
            smoke.installed.RunningApplication,
            ...,
        ]:
            if captured_root is None:
                return ()
            executable = (
                captured_root
                / "home/Applications"
                / smoke.installed.APP_RELATIVE_PATH
                / smoke.installed.EXECUTABLE_RELATIVE_PATH
            )
            return (
                smoke.installed.RunningApplication(
                    activation_policy=0,
                    bundle_identifier=(
                        smoke.installed.EXPECTED_BUNDLE_ID
                    ),
                    executable_path=str(executable),
                    finished_launching=True,
                    pid=4242,
                ),
            )

        def query(
            _pid: int,
        ) -> smoke.engine.ApplicationStatus | None:
            assert captured_root is not None
            executable = (
                captured_root
                / "home/Applications"
                / smoke.installed.APP_RELATIVE_PATH
                / smoke.installed.EXECUTABLE_RELATIVE_PATH
            )
            return smoke.engine.ApplicationStatus(
                activation_policy=0,
                bundle_identifier=smoke.installed.EXPECTED_BUNDLE_ID,
                executable_path=str(executable),
                finished_launching=True,
            )

        try:
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "retained diagnostic root",
            ):
                with smoke.isolated_upgrade_root(
                    termination_timeout_seconds=0.1,
                    lister=applications,
                    query=query,
                    requester=lambda *_args, **_kwargs: False,
                ) as root:
                    captured_root = root
                    executable = (
                        root
                        / "home/Applications"
                        / smoke.installed.APP_RELATIVE_PATH
                        / smoke.installed.EXECUTABLE_RELATIVE_PATH
                    )
                    executable.parent.mkdir(parents=True)
                    executable.write_bytes(b"fixture")
            self.assertIsNotNone(captured_root)
            assert captured_root is not None
            self.assertTrue(captured_root.is_dir())
        finally:
            if captured_root is not None:
                shutil.rmtree(captured_root, ignore_errors=True)

    def test_release_pair_requires_strict_build_order(self) -> None:
        previous = smoke.ReleaseVersion(23, "1.0.0", (1, 0, 0))
        current = smoke.ReleaseVersion(24, "1.0.0", (1, 0, 0))
        smoke.validate_release_pair(previous, current)

        for invalid in (
            (current, previous),
            (current, current),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(
                    smoke.engine.LifecycleSmokeError
                ):
                    smoke.validate_release_pair(*invalid)

    def test_state_comparison_reports_exact_changed_paths(self) -> None:
        identity = smoke.installed.FileIdentity(
            mode=0o600,
            sha256="a" * 64,
            size=4,
        )
        changed = smoke.installed.FileIdentity(
            mode=0o600,
            sha256="b" * 64,
            size=4,
        )
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError,
            "application-support/state.sqlite",
        ):
            smoke.require_unchanged_state(
                {"application-support/state.sqlite": identity},
                {"application-support/state.sqlite": changed},
                phase="fixture phase",
            )

    def test_execute_models_upgrade_canary_and_idempotent_relaunch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            previous_template = root / "previous/AetherLink.app"
            current_template = root / "current/AetherLink.app"
            self.create_app(previous_template, b"previous")
            self.create_app(current_template, b"current")
            previous_release = self.release_for_app(
                previous_template,
                archive_sha256="a" * 64,
                manifest_sha256="b" * 64,
            )
            current_release = self.release_for_app(
                current_template,
                archive_sha256="c" * 64,
                manifest_sha256="d" * 64,
            )
            previous_version = smoke.ReleaseVersion(
                23,
                "1.0.0",
                (1, 0, 0),
            )
            current_version = smoke.ReleaseVersion(
                24,
                "1.0.0",
                (1, 0, 0),
            )
            result_path = root / "result.json"
            pids: list[int] = []
            snapshots: dict[int, Path] = {}

            def snapshot_archive(
                _archive_dir: Path,
                *,
                version: smoke.ReleaseVersion,
                destination_parent: Path,
            ) -> tuple[Path, dict[str, dict[str, object]]]:
                release_id = smoke.recovery.release_id_for(version)
                snapshot = destination_parent / release_id
                snapshot.mkdir(parents=True)
                identities: dict[str, dict[str, object]] = {}
                for name in (
                    f"{release_id}.manifest.json",
                    f"{release_id}.zip",
                    f"{release_id}.zip.sha256",
                ):
                    payload = (
                        f"snapshot-{version.build_number}-{name}".encode()
                    )
                    (snapshot / name).write_bytes(payload)
                    identities[name] = {
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                    }
                snapshots[version.build_number] = snapshot
                return snapshot, identities

            def load_release(
                archive_dir: Path,
                *,
                verify_readback: bool,
                version: smoke.ReleaseVersion,
            ) -> smoke.engine.ReleaseInputs:
                self.assertFalse(verify_readback)
                if version == previous_version:
                    self.assertEqual(archive_dir, snapshots[23])
                    return previous_release
                self.assertEqual(version, current_version)
                self.assertEqual(archive_dir, snapshots[24])
                return current_release

            def extract(
                release: smoke.engine.ReleaseInputs,
                destination: Path,
            ) -> Path:
                template = (
                    previous_template
                    if release is previous_release
                    else current_template
                )
                extracted = (
                    destination.parent / smoke.installed.APP_RELATIVE_PATH
                )
                shutil.copytree(template, extracted)
                return extracted

            def verify_app(
                _app: Path,
                release: smoke.engine.ReleaseInputs,
                *,
                version: smoke.ReleaseVersion,
            ) -> dict[str, object]:
                return {
                    "bundleIdentifier": (
                        smoke.installed.EXPECTED_BUNDLE_ID
                    ),
                    "buildNumber": version.build_number,
                    "executableSha256": (
                        "e" * 64
                        if release is previous_release
                        else "f" * 64
                    ),
                    "marketingVersion": version.marketing_version,
                    "uuid": (
                        "fixture-previous-uuid"
                        if release is previous_release
                        else "fixture-current-uuid"
                    ),
                }

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

            def run_cycle(
                *,
                ordinal: int,
                app_path: Path,
                environment: dict[str, str],
                stdout_path: Path,
                stderr_path: Path,
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
                application_support.mkdir(parents=True, exist_ok=True)
                state_file = application_support / "state.bin"
                if not state_file.exists():
                    state_file.write_bytes(b"stable-upgrade-state")
                identity_file = Path(
                    environment["AETHERLINK_RUNTIME_IDENTITY_FILE"]
                )
                identity_file.write_bytes(b"stable-runtime-identity")
                stdout_path.write_bytes(b"fixture-observation\n")
                stderr_path.write_bytes(b"")
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

            canary = smoke.recovery.SQLiteCanaryEvidence(
                event_json_sha256=smoke.recovery.CANARY_EVENT_JSON_SHA256,
                event_json_size=len(smoke.recovery.CANARY_EVENT_JSON),
                integrity_check="ok",
                total_event_count=1,
            )
            auxiliary = tuple(
                {
                    "filename": filename,
                    "integrityCheck": "ok",
                }
                for filename in smoke.installed_recovery.AUXILIARY_SQLITE_FILES
            )

            with (
                patch.object(
                    smoke,
                    "release_pair",
                    return_value=(previous_version, current_version),
                ),
                patch.object(
                    smoke,
                    "snapshot_archive_directory",
                    side_effect=snapshot_archive,
                ),
                patch.object(
                    smoke,
                    "verify_archive_readback",
                ) as verify_readback,
                patch.object(
                    smoke.recovery,
                    "load_release_inputs",
                    side_effect=load_release,
                ),
                patch.object(
                    smoke.engine,
                    "extract_packaged_app",
                    side_effect=extract,
                ),
                patch.object(
                    smoke.recovery,
                    "verify_packaged_app",
                    side_effect=verify_app,
                ),
                patch.object(
                    smoke.removal,
                    "install_exact_temporary_app",
                    side_effect=install,
                ),
                patch.object(
                    smoke.installed_recovery,
                    "run_recovery_launch_services_cycle",
                    side_effect=run_cycle,
                ),
                patch.object(
                    smoke.installed_recovery,
                    "validate_captured_log",
                    return_value={
                        "sha256": hashlib.sha256(b"").hexdigest(),
                        "size": 0,
                    },
                ),
                patch.object(
                    smoke.recovery,
                    "verify_observation_log",
                    side_effect=lambda _path, mode: {
                        "mode": mode,
                        "sha256": "1" * 64,
                        "size": 1,
                        "status": "passed",
                    },
                ),
                patch.object(
                    smoke.recovery,
                    "sqlite_canary_evidence",
                    return_value=canary,
                ),
                patch.object(
                    smoke.installed_recovery,
                    "auxiliary_sqlite_evidence",
                    return_value=auxiliary,
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
                    previous_archive_dir=root / "previous-archive",
                    current_archive_dir=root / "current-archive",
                    result_path=result_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=(
                        smoke.engine.MINIMUM_OBSERVATION_SECONDS
                    ),
                    termination_timeout_seconds=1.0,
                )

            self.assertEqual(pids, [101, 102, 103])
            self.assertEqual(
                verify_readback.call_args_list[0].args,
                (snapshots[23],),
            )
            self.assertEqual(
                verify_readback.call_args_list[0].kwargs,
                {"historical": True},
            )
            self.assertEqual(
                verify_readback.call_args_list[1].args,
                (snapshots[24],),
            )
            self.assertEqual(
                verify_readback.call_args_list[1].kwargs,
                {"historical": False},
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(
                result["releases"]["from"]["releaseId"],
                "aetherlink-1.0.0+23-local-v1",
            )
            self.assertEqual(
                result["releases"]["to"]["releaseId"],
                "aetherlink-1.0.0+24-local-v1",
            )
            self.assertTrue(
                result["stateUpgrade"]["currentRelaunchIdempotent"]
            )
            self.assertTrue(
                result["installation"]["stalePreviousBundleFilesAbsent"]
            )
            self.assertTrue(
                result["archiveReadback"]["previous"][
                    "snapshotFilesUnchangedAfterExercise"
                ]
            )
            self.assertTrue(
                result["archiveReadback"]["current"][
                    "snapshotFilesUnchangedAfterExercise"
                ]
            )
            self.assertEqual(
                result_path.read_bytes(),
                smoke.engine.canonical_json_bytes(result),
            )

    def test_repeatability_publishes_two_identical_run_receipts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            calls: list[Path] = []
            fixture = self.repeatability_fixture_result()

            def execute(**arguments: object) -> dict[str, object]:
                run_path = arguments["result_path"]
                assert isinstance(run_path, Path)
                calls.append(run_path)
                smoke.installed.publish_result(run_path, fixture)
                return fixture

            with patch.object(smoke, "execute", side_effect=execute):
                receipt = smoke.execute_repeatability(
                    previous_archive_dir=root / "previous",
                    current_archive_dir=root / "current",
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=(
                        smoke.engine.MINIMUM_OBSERVATION_SECONDS
                    ),
                    termination_timeout_seconds=1.0,
                )

            self.assertEqual(len(calls), 2)
            self.assertEqual(receipt["runCount"], 2)
            self.assertTrue(receipt["resultBytesEqual"])
            self.assertEqual(
                [run["ordinal"] for run in receipt["runs"]],
                [1, 2],
            )
            self.assertEqual(
                result_path.read_bytes(),
                smoke.engine.canonical_json_bytes(fixture),
            )
            self.assertEqual(
                receipt_path.read_bytes(),
                smoke.engine.canonical_json_bytes(receipt),
            )

    def test_repeatability_mismatch_publishes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            ordinal = 0

            def execute(**arguments: object) -> dict[str, object]:
                nonlocal ordinal
                ordinal += 1
                result = self.repeatability_fixture_result(ordinal)
                run_path = arguments["result_path"]
                assert isinstance(run_path, Path)
                smoke.installed.publish_result(run_path, result)
                return result

            with (
                patch.object(smoke, "execute", side_effect=execute),
                self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    "different result bytes",
                ),
            ):
                smoke.execute_repeatability(
                    previous_archive_dir=root / "previous",
                    current_archive_dir=root / "current",
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=(
                        smoke.engine.MINIMUM_OBSERVATION_SECONDS
                    ),
                    termination_timeout_seconds=1.0,
                )

            self.assertFalse(result_path.exists())
            self.assertFalse(receipt_path.exists())

    def test_repeatability_preflight_prevents_partial_publication(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            receipt_path.write_bytes(b"different-receipt")
            fixture = self.repeatability_fixture_result()

            def execute(**arguments: object) -> dict[str, object]:
                run_path = arguments["result_path"]
                assert isinstance(run_path, Path)
                smoke.installed.publish_result(run_path, fixture)
                return fixture

            with (
                patch.object(smoke, "execute", side_effect=execute),
                self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    "repeatability receipt output already exists",
                ),
            ):
                smoke.execute_repeatability(
                    previous_archive_dir=root / "previous",
                    current_archive_dir=root / "current",
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=(
                        smoke.engine.MINIMUM_OBSERVATION_SECONDS
                    ),
                    termination_timeout_seconds=1.0,
                )

            self.assertFalse(result_path.exists())
            self.assertEqual(
                receipt_path.read_bytes(),
                b"different-receipt",
            )

    def test_result_pair_rolls_back_only_its_first_new_link(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            result_payload = b'{"status":"passed"}\n'
            receipt_payload = b'{"runCount":2}\n'
            link_count = 0

            def fail_second_link(source: Path, target: Path) -> None:
                nonlocal link_count
                link_count += 1
                if link_count == 2:
                    raise OSError("fixture second-link failure")
                os.link(source, target)

            with self.assertRaisesRegex(
                OSError,
                "fixture second-link failure",
            ):
                smoke.publish_result_pair(
                    result_path,
                    result_payload,
                    receipt_path,
                    receipt_payload,
                    linker=fail_second_link,
                )
            self.assertFalse(result_path.exists())
            self.assertFalse(receipt_path.exists())
            self.assertEqual(
                list(root.glob(".*.pair-*")),
                [],
            )

            result_path.write_bytes(result_payload)

            def fail_only_link(_source: Path, _target: Path) -> None:
                raise OSError("fixture receipt-link failure")

            with self.assertRaisesRegex(
                OSError,
                "fixture receipt-link failure",
            ):
                smoke.publish_result_pair(
                    result_path,
                    result_payload,
                    receipt_path,
                    receipt_payload,
                    linker=fail_only_link,
                )
            self.assertEqual(result_path.read_bytes(), result_payload)
            self.assertFalse(receipt_path.exists())
            self.assertEqual(
                list(root.glob(".*.pair-*")),
                [],
            )

    def test_exact_result_comparison_rejects_bool_integer_aliases(
        self,
    ) -> None:
        self.assertFalse(smoke.exact_results_equal(True, 1))
        self.assertFalse(
            smoke.exact_results_equal(
                {"count": 1},
                {"count": True},
            )
        )

    def test_output_paths_must_be_distinct_and_outside_archives(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            archive = root / "archive"
            archive.mkdir()
            shared = root / "shared.json"
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "must be distinct",
            ):
                smoke.require_output_paths_outside_archives(
                    (shared, shared),
                    (archive,),
                )
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "outside release archive",
            ):
                smoke.require_output_paths_outside_archives(
                    (archive / "result.json",),
                    (archive,),
                )

    def test_default_result_tracks_latest_two_ledger_entries(self) -> None:
        previous = smoke.ReleaseVersion(41, "2.4.5", (2, 4, 5))
        current = smoke.ReleaseVersion(42, "2.4.6", (2, 4, 6))
        with patch.object(
            smoke,
            "release_pair",
            return_value=(previous, current),
        ):
            self.assertEqual(
                smoke.default_result_path().name,
                (
                    "macos-packaged-app-build-41-to-42-"
                    "isolated-upgrade-v2.json"
                ),
            )
            self.assertEqual(
                smoke.default_repeatability_result_path().name,
                (
                    "macos-packaged-app-build-41-to-42-"
                    "isolated-upgrade-repeatability-v1.json"
                ),
            )


if __name__ == "__main__":
    unittest.main()
