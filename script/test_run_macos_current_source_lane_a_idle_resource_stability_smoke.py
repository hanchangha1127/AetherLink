from __future__ import annotations

import copy
from contextlib import contextmanager, redirect_stderr
import hashlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from script.check_release_version_ledger import ReleaseVersion
from script import (
    run_macos_current_source_lane_a_idle_resource_stability_smoke as runner,
)


def sample_records() -> list[dict[str, object]]:
    return [
        runner.idle.ResourceSample(
            open_file_descriptor_count=10,
            resident_bytes=100 * 1024 * 1024,
            thread_count=3,
        ).record(
            ordinal=index + 1,
            target_elapsed_milliseconds=(
                (index + 1) * runner.idle.SAMPLE_INTERVAL_MILLISECONDS
            ),
            observed_lateness_milliseconds=0,
        )
        for index in range(runner.idle.SAMPLE_COUNT)
    ]


def valid_run() -> dict[str, object]:
    samples = sample_records()
    return {
        "activationPolicy": 0,
        "appKitProcessAbsentAfterReap": True,
        "exitCode": 0,
        "finishedLaunching": True,
        "gracefulTerminationAccepted": True,
        "maximumObservedLatenessMilliseconds": 0,
        "ownedChildProcess": True,
        "processIdentifierRetained": False,
        "processReaped": True,
        "samples": samples,
        "summary": runner.idle.measurement_summary(samples),
    }


def valid_source_snapshot() -> dict[str, object]:
    return {
        "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        "fileCount": 266,
        "sha256": "1" * 64,
    }


def valid_artifact() -> dict[str, object]:
    return {
        "appTree": {
            "digestAlgorithm": (
                "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
            ),
            "regularFileCount": 10,
            "sha256": "2" * 64,
            "totalRegularFileBytes": 21_000_000,
        },
        "buildNumber": 24,
        "bundleIdentifier": runner.engine.EXPECTED_BUNDLE_ID,
        "executableMode": 0o755,
        "executableSha256": "3" * 64,
        "executableSize": 18_000_000,
        "marketingVersion": "1.0.0",
        "uuid": "00000000-0000-0000-0000-000000000000",
    }


class ReleaseFixture:
    def __init__(self, root: Path) -> None:
        self.version = ReleaseVersion(
            build_number=24,
            marketing_version="1.0.0",
            semantic_version=(1, 0, 0),
        )
        self.release_id = "aetherlink-1.0.0+24-local-v1"
        archive = root / f"{self.release_id}.zip"
        manifest = root / f"{self.release_id}.manifest.json"
        checksum = root / f"{self.release_id}.zip.sha256"
        archive.write_bytes(b"archive\n")
        manifest.write_bytes(b"{}\n")
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksum.write_text(
            f"{archive_sha}  {archive.name}\n",
            encoding="ascii",
        )
        self.release = runner.engine.ReleaseInputs(
            archive_dir=root,
            archive_path=archive,
            manifest_path=manifest,
            checksum_path=checksum,
            archive_sha256=archive_sha,
            manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            manifest={},
        )
        self.snapshot_files = {
            path.name: {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": len(path.read_bytes()),
            }
            for path in (archive, manifest, checksum)
        }


class BinaryStdout:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


class CurrentSourceLaneAIdleResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = ReleaseFixture(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def build(self, **overrides: object) -> dict[str, object]:
        arguments: dict[str, object] = {
            "version": self.fixture.version,
            "release": self.fixture.release,
            "artifact": valid_artifact(),
            "snapshot_files": self.fixture.snapshot_files,
            "source_snapshot": valid_source_snapshot(),
            "run": valid_run(),
            "preexisting_application_count": 1,
        }
        arguments.update(overrides)
        return runner.build_result(**arguments)  # type: ignore[arg-type]

    def test_build_result_closes_current_source_idle_contract(self) -> None:
        result = self.build()
        self.assertEqual(result["schemaVersion"], 1)
        self.assertEqual(result["scope"], runner.RESULT_SCOPE)
        self.assertEqual(result["sourceSnapshot"], valid_source_snapshot())
        self.assertEqual(
            result["artifact"],
            {"appTree": valid_artifact()["appTree"]},
        )
        self.assertEqual(
            result["archiveReadback"]["snapshotFiles"],
            self.fixture.snapshot_files,
        )
        self.assertEqual(
            result["measurement"]["sampleCount"],
            120,
        )

    def test_full_source_snapshot_is_projected_to_closed_summary(self) -> None:
        full = {
            **valid_source_snapshot(),
            "files": [{"path": "fixture", "sha256": "a" * 64}],
        }
        self.assertEqual(
            runner.source_snapshot_summary(full),
            valid_source_snapshot(),
        )

    def test_budget_failure_retains_metric_values_and_restores_hook(
        self,
    ) -> None:
        samples = sample_records()
        samples[60]["residentBytes"] = 300 * 1024 * 1024
        for sample in samples[-runner.idle.FINAL_WINDOW_SAMPLE_COUNT :]:
            sample["residentBytes"] = 164 * 1024 * 1024
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "failed metrics",
        ) as caught:
            runner.diagnostic_measurement_summary(samples)
        message = str(caught.exception)
        for fragment in (
            '"residentBytes"',
            '"finalDelta":67108864',
            '"finalDeltaLimit":33554432',
            '"peakDelta":209715200',
            '"peakDeltaLimit":134217728',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, message)

        original = runner.idle.measurement_summary
        with runner.diagnostic_measurement_scope():
            self.assertIs(
                runner.idle.measurement_summary,
                runner.diagnostic_measurement_summary,
            )
        self.assertIs(runner.idle.measurement_summary, original)

    def test_exercise_binds_equal_full_source_snapshots(self) -> None:
        full = {
            **valid_source_snapshot(),
            "files": [{"path": "fixture", "sha256": "a" * 64}],
        }
        changed = copy.deepcopy(full)
        changed["files"][0]["sha256"] = "b" * 64
        tree_evidence = mock.Mock()
        tree_evidence.record.return_value = valid_artifact()["appTree"]
        snapshot_roots: list[Path] = []

        @contextmanager
        def isolated(**_: object):
            temporary_root = Path(tempfile.mkdtemp())
            try:
                yield temporary_root, []
            finally:
                shutil.rmtree(temporary_root)

        def extracted(
            _release: object,
            destination: Path,
        ) -> Path:
            app_path = destination / "AetherLink.app"
            app_path.mkdir(parents=True)
            return app_path

        def snapshot_archive(
            _archive_dir: Path,
            *,
            version: ReleaseVersion,
            destination_parent: Path,
        ) -> tuple[Path, dict[str, dict[str, object]]]:
            self.assertEqual(version, self.fixture.version)
            snapshot_root = destination_parent / self.fixture.release_id
            snapshot_root.mkdir(parents=True)
            for source in (
                self.fixture.release.archive_path,
                self.fixture.release.manifest_path,
                self.fixture.release.checksum_path,
            ):
                (snapshot_root / source.name).write_bytes(source.read_bytes())
            snapshot_roots.append(snapshot_root)
            return snapshot_root, copy.deepcopy(self.fixture.snapshot_files)

        def load_release(snapshot_root: Path, **_: object) -> object:
            return runner.engine.ReleaseInputs(
                archive_dir=snapshot_root,
                archive_path=(
                    snapshot_root / self.fixture.release.archive_path.name
                ),
                manifest_path=(
                    snapshot_root / self.fixture.release.manifest_path.name
                ),
                checksum_path=(
                    snapshot_root / self.fixture.release.checksum_path.name
                ),
                archive_sha256=self.fixture.release.archive_sha256,
                manifest_sha256=self.fixture.release.manifest_sha256,
                manifest={},
            )

        with (
            mock.patch.object(runner.idle, "validate_libproc_abi"),
            mock.patch.object(
                runner.archive_builder,
                "source_snapshot",
                side_effect=[
                    full,
                    copy.deepcopy(full),
                    full,
                    changed,
                ],
            ) as source_reader,
            mock.patch.object(
                runner.installed,
                "list_bundle_applications",
                return_value=(),
            ),
            mock.patch.object(runner, "isolated_resource_root", isolated),
            mock.patch.object(
                runner.upgrade,
                "snapshot_archive_directory",
                side_effect=snapshot_archive,
            ),
            mock.patch.object(runner.upgrade, "verify_archive_readback"),
            mock.patch.object(
                runner.recovery,
                "load_release_inputs",
                side_effect=load_release,
            ),
            mock.patch.object(
                runner.engine,
                "extract_packaged_app",
                side_effect=extracted,
            ),
            mock.patch.object(
                runner.idle,
                "verify_extracted_app",
                return_value=valid_artifact(),
            ),
            mock.patch.object(
                runner.engine,
                "build_sandbox_profile",
                return_value="profile",
            ),
            mock.patch.object(runner.engine, "preflight_sandbox"),
            mock.patch.object(
                runner.engine,
                "isolated_environment",
                return_value={},
            ),
            mock.patch.object(
                runner.idle,
                "run_owned_idle_observation",
                return_value=valid_run(),
            ),
            mock.patch.object(
                runner.installed,
                "app_tree_evidence",
                return_value=tree_evidence,
            ),
            mock.patch.object(
                runner.upgrade,
                "require_unchanged_archive_snapshot",
            ),
            mock.patch.object(
                runner.installed,
                "assert_preexisting_applications_preserved",
            ),
        ):
            result = runner.exercise(archive_dir=self.root)
            with self.assertRaisesRegex(
                runner.IdleResourceSmokeError,
                "source snapshot changed",
            ):
                runner.exercise(archive_dir=self.root)
        self.assertEqual(source_reader.call_count, 4)
        self.assertEqual(result["sourceSnapshot"], valid_source_snapshot())
        self.assertEqual(len(snapshot_roots), 2)
        self.assertTrue(all(not path.exists() for path in snapshot_roots))

    def test_bool_source_file_count_is_rejected(self) -> None:
        source = valid_source_snapshot()
        source["fileCount"] = True
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "snapshot identity",
        ):
            self.build(source_snapshot=source)

    def test_bool_snapshot_size_is_rejected(self) -> None:
        snapshot = copy.deepcopy(self.fixture.snapshot_files)
        next(iter(snapshot.values()))["size"] = True
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "snapshot identity",
        ):
            self.build(snapshot_files=snapshot)

    def test_checksum_snapshot_drift_is_rejected(self) -> None:
        snapshot = copy.deepcopy(self.fixture.snapshot_files)
        snapshot[f"{self.fixture.release_id}.zip.sha256"]["sha256"] = "4" * 64
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "checksum differs",
        ):
            self.build(snapshot_files=snapshot)

    def test_artifact_tree_drift_is_rejected(self) -> None:
        artifact = valid_artifact()
        artifact["appTree"]["regularFileCount"] = False
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "artifact identity",
        ):
            self.build(artifact=artifact)

    def test_summary_drift_is_rejected(self) -> None:
        run = valid_run()
        run["summary"]["residentBytes"]["finalDelta"] = 1
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "summary differs",
        ):
            self.build(run=run)

    def test_maximum_lateness_must_match_samples(self) -> None:
        run = valid_run()
        run["maximumObservedLatenessMilliseconds"] = 1
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "maximum lateness differs",
        ):
            self.build(run=run)

    def test_bool_preexisting_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            runner.IdleResourceSmokeError,
            "exact nonnegative integer",
        ):
            self.build(preexisting_application_count=False)

    def test_isolated_root_removes_only_its_temporary_root(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        with runner.isolated_resource_root(
            termination_timeout_seconds=1.0,
            lister=lambda: (),
        ) as (temporary_root, owned_processes):
            self.assertEqual(owned_processes, [])
            (temporary_root / "marker").write_text("x", encoding="ascii")
        self.assertFalse(temporary_root.exists())
        self.assertTrue(outside.is_dir())

    def test_unowned_temporary_app_retains_diagnostic_root(self) -> None:
        captured: Path | None = None

        def lister() -> tuple[runner.installed.RunningApplication, ...]:
            assert captured is not None
            return (
                runner.installed.RunningApplication(
                    activation_policy=0,
                    bundle_identifier=runner.engine.EXPECTED_BUNDLE_ID,
                    executable_path=str(captured / "AetherLink"),
                    finished_launching=True,
                    pid=999_999,
                ),
            )

        try:
            with self.assertRaisesRegex(
                runner.IdleResourceSmokeError,
                "diagnostic root retained",
            ):
                with runner.isolated_resource_root(
                    termination_timeout_seconds=1.0,
                    lister=lister,
                ) as (temporary_root, _):
                    captured = temporary_root
            self.assertIsNotNone(captured)
            self.assertTrue(captured.is_dir())
        finally:
            if captured is not None:
                shutil.rmtree(captured, ignore_errors=True)

    def test_main_writes_only_canonical_result_bytes(self) -> None:
        output = BinaryStdout()
        result = {"schemaVersion": 1, "status": "passed"}
        with (
            mock.patch.object(runner, "exercise", return_value=result),
            mock.patch.object(runner.sys, "stdout", output),
        ):
            self.assertEqual(runner.main(["--archive-dir", str(self.root)]), 0)
        self.assertEqual(
            output.buffer.getvalue(),
            runner.engine.canonical_json_bytes(result),
        )

    def test_main_reports_failure_without_result_bytes(self) -> None:
        stderr = io.StringIO()
        output = BinaryStdout()
        with (
            mock.patch.object(
                runner,
                "exercise",
                side_effect=runner.IdleResourceSmokeError("fixture"),
            ),
            mock.patch.object(runner.sys, "stdout", output),
            redirect_stderr(stderr),
        ):
            self.assertEqual(runner.main(["--archive-dir", str(self.root)]), 1)
        self.assertEqual(output.buffer.getvalue(), b"")
        self.assertIn("fixture", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
