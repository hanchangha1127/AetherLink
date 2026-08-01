#!/usr/bin/env python3
"""Tests for the bounded macOS reverse-version readback observation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_isolated_reverse_version_readback_smoke as smoke


class ReverseVersionReadbackSmokeTests(unittest.TestCase):
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

    def receipt_fixture_result(
        self,
        marker: object = "stable",
    ) -> dict[str, object]:
        return {
            "fixture": marker,
            "qualification": {
                "nMinusOneQualificationClaimed": False,
                "productRollbackQualificationClaimed": False,
                "securityEvidenceProduced": False,
                "securityQualificationClaimed": False,
            },
            "releaseSequence": [
                {
                    "ordinal": 1,
                    "releaseId": "aetherlink-1.0.0+24-local-v1",
                    "role": "current-fixture-initialization",
                },
                {
                    "ordinal": 2,
                    "releaseId": "aetherlink-1.0.0+23-local-v1",
                    "role": "historical-readback",
                },
                {
                    "ordinal": 3,
                    "releaseId": "aetherlink-1.0.0+24-local-v1",
                    "role": "current-readback",
                },
            ],
            "schemaVersion": smoke.RESULT_SCHEMA_VERSION,
            "scope": smoke.RESULT_SCOPE,
            "status": "passed",
        }

    def run_modeled_execute(
        self,
        root: Path,
        *,
        mutate_state_ordinal: int | None = None,
        drift_sqlite_ordinal: int | None = None,
        reappear_legacy_ordinal: int | None = None,
        duplicate_pid: bool = False,
    ) -> tuple[dict[str, object], dict[str, object]]:
        historical_template = root / "historical/AetherLink.app"
        current_template = root / "current/AetherLink.app"
        self.create_app(historical_template, b"historical")
        self.create_app(current_template, b"current")
        historical_release = self.release_for_app(
            historical_template,
            archive_sha256="a" * 64,
            manifest_sha256="b" * 64,
        )
        current_release = self.release_for_app(
            current_template,
            archive_sha256="c" * 64,
            manifest_sha256="d" * 64,
        )
        historical_version = smoke.ReleaseVersion(
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
        snapshots: dict[int, Path] = {}
        readback_calls: list[tuple[Path, bool]] = []
        installed_builds: list[int] = []
        removed_builds: list[int] = []
        modes: list[str] = []
        pids: list[int] = []
        sqlite_calls = 0

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
                payload = f"snapshot-{version.build_number}-{name}".encode()
                (snapshot / name).write_bytes(payload)
                identities[name] = {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            snapshots[version.build_number] = snapshot
            return snapshot, identities

        def verify_readback(
            archive_dir: Path,
            *,
            historical: bool,
        ) -> None:
            readback_calls.append((archive_dir, historical))

        def load_release(
            archive_dir: Path,
            *,
            verify_readback: bool,
            version: smoke.ReleaseVersion,
        ) -> smoke.engine.ReleaseInputs:
            self.assertFalse(verify_readback)
            self.assertEqual(archive_dir, snapshots[version.build_number])
            return (
                historical_release
                if version == historical_version
                else current_release
            )

        def extract(
            release: smoke.engine.ReleaseInputs,
            destination: Path,
        ) -> Path:
            template = (
                historical_template
                if release is historical_release
                else current_template
            )
            extracted = destination.parent / smoke.installed.APP_RELATIVE_PATH
            shutil.copytree(template, extracted)
            return extracted

        def verify_app(
            _app: Path,
            release: smoke.engine.ReleaseInputs,
            *,
            version: smoke.ReleaseVersion,
        ) -> dict[str, object]:
            return {
                "bundleIdentifier": smoke.installed.EXPECTED_BUNDLE_ID,
                "buildNumber": version.build_number,
                "executableSha256": (
                    "e" * 64 if release is historical_release else "f" * 64
                ),
                "marketingVersion": version.marketing_version,
                "uuid": (
                    "fixture-historical-uuid"
                    if release is historical_release
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
            build = 23 if "historical-extraction" in str(source) else 24
            installed_builds.append(build)
            app_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, app_path)

        actual_remove = smoke.removal.remove_exact_installed_app

        def remove(**arguments: object) -> None:
            release = arguments["release"]
            removed_builds.append(
                23 if release is historical_release else 24
            )
            actual_remove(**arguments)

        def run_cycle(
            *,
            ordinal: int,
            app_path: Path,
            environment: dict[str, str],
            logs: Path,
            mode: str,
            readiness_timeout_seconds: float,
            observation_seconds: float,
            termination_timeout_seconds: float,
        ) -> tuple[int, dict[str, object], dict[str, object], dict[str, object]]:
            del (
                app_path,
                logs,
                readiness_timeout_seconds,
                observation_seconds,
                termination_timeout_seconds,
            )
            modes.append(mode)
            application_support = (
                Path(environment["HOME"])
                / "Library/Application Support/AetherLink"
            )
            application_support.mkdir(parents=True, exist_ok=True)
            state_file = application_support / "state.bin"
            if not state_file.exists():
                state_file.write_bytes(b"stable-reverse-version-state")
            identity_file = Path(
                environment["AETHERLINK_RUNTIME_IDENTITY_FILE"]
            )
            identity_file.write_bytes(b"stable-runtime-identity")
            if mutate_state_ordinal == ordinal:
                state_file.write_bytes(f"mutated-{ordinal}".encode())
            if reappear_legacy_ordinal == ordinal:
                legacy = application_support / smoke.recovery.LEGACY_FILENAME
                legacy.write_bytes(smoke.recovery.CANARY_LEGACY_BYTES)
            pid = 101 if duplicate_pid else 100 + ordinal
            pids.append(pid)
            return (
                pid,
                {
                    "activationPolicy": 0,
                    "executablePathMatched": True,
                    "finishedLaunching": True,
                    "minimumObservationSeconds": (
                        smoke.engine.MINIMUM_OBSERVATION_SECONDS
                    ),
                    "newProcessIdentifierDetected": True,
                    "observationDeadlineReached": True,
                    "ordinal": ordinal,
                    "terminationAccepted": True,
                },
                {
                    "mode": mode,
                    "sha256": "1" * 64,
                    "size": 1,
                    "status": "passed",
                },
                {
                    "sha256": hashlib.sha256(b"").hexdigest(),
                    "size": 0,
                },
            )

        stable_canary = smoke.recovery.SQLiteCanaryEvidence(
            event_json_sha256=smoke.recovery.CANARY_EVENT_JSON_SHA256,
            event_json_size=len(smoke.recovery.CANARY_EVENT_JSON),
            integrity_check="ok",
            total_event_count=1,
        )
        drifted_canary = smoke.recovery.SQLiteCanaryEvidence(
            event_json_sha256="9" * 64,
            event_json_size=len(smoke.recovery.CANARY_EVENT_JSON),
            integrity_check="ok",
            total_event_count=1,
        )

        def sqlite_evidence(_path: Path) -> smoke.recovery.SQLiteCanaryEvidence:
            nonlocal sqlite_calls
            sqlite_calls += 1
            if drift_sqlite_ordinal == sqlite_calls:
                return drifted_canary
            return stable_canary

        auxiliary = tuple(
            {"filename": filename, "integrityCheck": "ok"}
            for filename in smoke.installed_recovery.AUXILIARY_SQLITE_FILES
        )

        with (
            patch.object(
                smoke,
                "release_pair",
                return_value=(historical_version, current_version),
            ),
            patch.object(
                smoke.upgrade,
                "snapshot_archive_directory",
                side_effect=snapshot_archive,
            ),
            patch.object(
                smoke.upgrade,
                "verify_archive_readback",
                side_effect=verify_readback,
            ),
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
                smoke.removal,
                "remove_exact_installed_app",
                side_effect=remove,
            ),
            patch.object(
                smoke.upgrade,
                "run_recovery_cycle",
                side_effect=run_cycle,
            ),
            patch.object(
                smoke.recovery,
                "sqlite_canary_evidence",
                side_effect=sqlite_evidence,
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
                historical_archive_dir=root / "historical-archive",
                current_archive_dir=root / "current-archive",
                result_path=result_path,
                readiness_timeout_seconds=1.0,
                observation_seconds=smoke.engine.MINIMUM_OBSERVATION_SECONDS,
                termination_timeout_seconds=1.0,
            )

        diagnostics: dict[str, object] = {
            "installedBuilds": installed_builds,
            "modes": modes,
            "pids": pids,
            "readbackCalls": readback_calls,
            "removedBuilds": removed_builds,
            "resultPath": result_path,
            "snapshots": snapshots,
        }
        return result, diagnostics

    def test_execute_models_current_historical_current_readback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result, diagnostics = self.run_modeled_execute(root)

            self.assertEqual(diagnostics["installedBuilds"], [24, 23, 24])
            self.assertEqual(diagnostics["removedBuilds"], [24, 23, 24])
            self.assertEqual(
                diagnostics["modes"],
                [
                    smoke.recovery.MIGRATION_MODE,
                    smoke.recovery.SQLITE_READBACK_MODE,
                    smoke.recovery.SQLITE_READBACK_MODE,
                ],
            )
            self.assertEqual(diagnostics["pids"], [101, 102, 103])
            snapshots = diagnostics["snapshots"]
            self.assertEqual(
                diagnostics["readbackCalls"],
                [(snapshots[23], True), (snapshots[24], False)],
            )
            self.assertEqual(
                [entry["releaseId"] for entry in result["releaseSequence"]],
                [
                    "aetherlink-1.0.0+24-local-v1",
                    "aetherlink-1.0.0+23-local-v1",
                    "aetherlink-1.0.0+24-local-v1",
                ],
            )
            qualification = result["qualification"]
            self.assertIs(
                qualification["productionPredecessorClaimed"],
                False,
            )
            self.assertIs(
                qualification["nMinusOneQualificationClaimed"],
                False,
            )
            self.assertIs(
                qualification["productRollbackQualificationClaimed"],
                False,
            )
            self.assertIs(
                qualification["securityEvidenceProduced"],
                False,
            )
            self.assertIs(
                qualification["securityQualificationClaimed"],
                False,
            )
            self.assertIs(qualification["securityStateInspected"], False)
            self.assertIs(
                qualification["supportedUpgradeOrRollbackClaimed"],
                False,
            )
            result_path = diagnostics["resultPath"]
            self.assertEqual(
                smoke.stable_regular_bytes(result_path),
                smoke.engine.canonical_json_bytes(result),
            )

    def test_execute_rejects_state_drift_without_publication(self) -> None:
        for ordinal in (2, 3):
            with self.subTest(ordinal=ordinal), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                with self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    "isolated state changed",
                ):
                    self.run_modeled_execute(
                        root,
                        mutate_state_ordinal=ordinal,
                    )
                self.assertFalse((root / "result.json").exists())

    def test_execute_rejects_canary_drift_without_publication(self) -> None:
        for ordinal in (2, 3):
            with self.subTest(ordinal=ordinal), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                expected = (
                    "historical readback"
                    if ordinal == 2
                    else "current app restoration"
                )
                with self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    expected,
                ):
                    self.run_modeled_execute(
                        root,
                        drift_sqlite_ordinal=ordinal,
                    )
                self.assertFalse((root / "result.json").exists())

    def test_execute_rejects_reappearing_legacy_or_duplicate_pid(self) -> None:
        cases = (
            ({"reappear_legacy_ordinal": 2}, "isolated state changed"),
            ({"duplicate_pid": True}, "three distinct processes"),
        )
        for arguments, message in cases:
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                with self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    message,
                ):
                    self.run_modeled_execute(root, **arguments)
                self.assertFalse((root / "result.json").exists())

    def test_pair_publication_is_create_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result = root / "result.json"
            receipt = root / "receipt.json"
            result_payload = b'{"status":"passed"}\n'
            receipt_payload = b'{"runCount":2}\n'
            smoke.publish_result_pair(
                result,
                result_payload,
                receipt,
                receipt_payload,
            )
            self.assertEqual(smoke.stable_regular_bytes(result), result_payload)
            self.assertEqual(
                smoke.stable_regular_bytes(receipt),
                receipt_payload,
            )
            smoke.publish_result_pair(
                result,
                result_payload,
                receipt,
                receipt_payload,
            )
            self.assertEqual(list(root.glob(".*.pair-*")), [])

    def test_publication_preflight_rejects_unsafe_existing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            payload = b'{"status":"passed"}\n'
            different = root / "different.json"
            different.write_bytes(b"different")
            different.chmod(0o600)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "different bytes",
            ):
                smoke.publish_result_files(
                    ((different, payload, "fixture"),)
                )

            target = root / "target.json"
            target.write_bytes(payload)
            target.chmod(0o600)
            symlink = root / "symlink.json"
            symlink.symlink_to(target)
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.publish_result_files(((symlink, payload, "fixture"),))

            directory = root / "directory.json"
            directory.mkdir()
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.publish_result_files(((directory, payload, "fixture"),))

            hardlink = root / "hardlink.json"
            os.link(target, hardlink)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "single-link regular file",
            ):
                smoke.publish_result_files(((target, payload, "fixture"),))

            unsafe_mode = root / "unsafe-mode.json"
            unsafe_mode.write_bytes(payload)
            unsafe_mode.chmod(0o666)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "single-link regular file",
            ):
                smoke.publish_result_files(
                    ((unsafe_mode, payload, "fixture"),)
                )

    def test_publication_rejects_symlink_ancestor_or_missing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            real = root / "real"
            real.mkdir()
            alias = root / "alias"
            alias.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "without symlink ancestors",
            ):
                smoke.publish_result_files(
                    ((alias / "result.json", b"result\n", "fixture"),)
                )
            self.assertFalse((real / "result.json").exists())

            missing = root / "missing" / "result.json"
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "must already exist",
            ):
                smoke.publish_result_files(
                    ((missing, b"result\n", "fixture"),)
                )
            self.assertFalse(missing.parent.exists())

    def test_second_link_failure_removes_only_owned_first_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result = root / "result.json"
            receipt = root / "receipt.json"
            link_count = 0

            def fail_second(source: Path, target: Path) -> None:
                nonlocal link_count
                link_count += 1
                if link_count == 2:
                    raise OSError("fixture second-link failure")
                os.link(source, target)

            with self.assertRaisesRegex(OSError, "second-link failure"):
                smoke.publish_result_pair(
                    result,
                    b"result\n",
                    receipt,
                    b"receipt\n",
                    linker=fail_second,
                )
            self.assertFalse(result.exists())
            self.assertFalse(receipt.exists())
            self.assertEqual(list(root.glob(".*.pair-*")), [])

    def test_post_link_interrupt_uses_prelink_intent_for_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result = root / "result.json"

            def link_then_interrupt(source: Path, target: Path) -> None:
                os.link(source, target)
                raise KeyboardInterrupt("fixture post-link interrupt")

            with self.assertRaisesRegex(
                KeyboardInterrupt,
                "post-link interrupt",
            ):
                smoke.publish_result_files(
                    ((result, b"result\n", "fixture"),),
                    linker=link_then_interrupt,
                )
            self.assertFalse(result.exists())
            self.assertEqual(list(root.glob(".*.pair-*")), [])

    def test_cleanup_continues_after_one_owned_unlink_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            first = root / "first.json"
            second = root / "second.json"
            sync_calls = 0
            unlink_calls: list[Path] = []

            def fail_first_sync(_path: Path) -> None:
                nonlocal sync_calls
                sync_calls += 1
                if sync_calls == 1:
                    raise OSError("fixture post-link sync failure")

            def fail_second_unlink(path: Path) -> None:
                unlink_calls.append(path)
                if path == second:
                    raise OSError("fixture unlink failure")
                path.unlink()

            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "cleanup was incomplete",
            ):
                smoke.publish_result_files(
                    (
                        (first, b"first\n", "first"),
                        (second, b"second\n", "second"),
                    ),
                    rollback_unlinker=fail_second_unlink,
                    directory_sync=fail_first_sync,
                )
            self.assertEqual(unlink_calls, [second, first])
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())
            second.unlink()

    def test_temporary_unlink_failure_rolls_back_and_retries_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result = root / "result.json"
            unlink_calls = 0

            def fail_once(path: Path) -> None:
                nonlocal unlink_calls
                unlink_calls += 1
                if unlink_calls == 1:
                    raise OSError("fixture temporary unlink failure")
                path.unlink()

            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "temporary result payload cleanup failed",
            ):
                smoke.publish_result_files(
                    ((result, b"result\n", "fixture"),),
                    temporary_unlinker=fail_once,
                )
            self.assertFalse(result.exists())
            self.assertEqual(list(root.glob(".*.pair-*")), [])

    def test_repeatability_publishes_only_identical_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            fixture = self.receipt_fixture_result()

            def execute(**arguments: object) -> dict[str, object]:
                run_path = arguments["result_path"]
                assert isinstance(run_path, Path)
                smoke.publish_single_result(run_path, fixture)
                return fixture

            with patch.object(smoke, "execute", side_effect=execute):
                receipt = smoke.execute_repeatability(
                    historical_archive_dir=root / "historical",
                    current_archive_dir=root / "current",
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=smoke.engine.MINIMUM_OBSERVATION_SECONDS,
                    termination_timeout_seconds=1.0,
                )
            self.assertEqual(receipt["runCount"], 2)
            self.assertIs(
                receipt["qualification"][
                    "productRollbackQualificationClaimed"
                ],
                False,
            )
            self.assertEqual(
                smoke.stable_regular_bytes(result_path),
                smoke.engine.canonical_json_bytes(fixture),
            )
            self.assertEqual(
                smoke.stable_regular_bytes(receipt_path),
                smoke.engine.canonical_json_bytes(receipt),
            )

    def test_repeatability_mismatch_publishes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            ordinal = 0

            def execute(**arguments: object) -> dict[str, object]:
                nonlocal ordinal
                ordinal += 1
                result = self.receipt_fixture_result(ordinal)
                run_path = arguments["result_path"]
                assert isinstance(run_path, Path)
                smoke.publish_single_result(run_path, result)
                return result

            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            with (
                patch.object(smoke, "execute", side_effect=execute),
                self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    "different bytes",
                ),
            ):
                smoke.execute_repeatability(
                    historical_archive_dir=root / "historical",
                    current_archive_dir=root / "current",
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1.0,
                    observation_seconds=smoke.engine.MINIMUM_OBSERVATION_SECONDS,
                    termination_timeout_seconds=1.0,
                )
            self.assertFalse(result_path.exists())
            self.assertFalse(receipt_path.exists())

    def test_exact_comparison_and_default_paths(self) -> None:
        self.assertFalse(smoke.exact_results_equal(True, 1))
        self.assertEqual(
            smoke.default_result_path().name,
            (
                "macos-packaged-app-build-24-to-23-to-24-"
                "isolated-reverse-version-readback-v1.json"
            ),
        )
        self.assertEqual(
            smoke.default_repeatability_result_path().name,
            (
                "macos-packaged-app-build-24-to-23-to-24-"
                "isolated-reverse-version-readback-repeatability-v1.json"
            ),
        )
        historical = smoke.ReleaseVersion(41, "2.4.5", (2, 4, 5))
        current = smoke.ReleaseVersion(42, "2.4.6", (2, 4, 6))
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError,
            "exact terminal Build 23/24",
        ):
            smoke.validate_release_pair(historical, current)


if __name__ == "__main__":
    unittest.main()
