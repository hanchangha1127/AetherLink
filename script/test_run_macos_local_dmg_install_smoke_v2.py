#!/usr/bin/env python3
"""Unit tests for the snapshot-bound local DMG install rehearsal."""

from __future__ import annotations

import copy
from contextlib import ExitStack
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_local_dmg_install_smoke_v2 as smoke
from script.test_run_macos_local_dmg_install_smoke import (
    attach_plist,
    launch_record,
    sqlite_evidence,
)


class ResultContractTests(unittest.TestCase):
    def release_inputs(
        self,
        root: Path,
        release_id: str,
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
        release_id: str,
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

    def build(
        self,
        root: Path,
        *,
        runtime_identity_present: bool = True,
        snapshot_files: dict[str, dict[str, object]] | None = None,
    ) -> dict[str, object]:
        release_id = "build-987"
        return smoke.build_result(
            release=self.release_inputs(root, release_id),
            release_id=release_id,
            app_tree=smoke.installed.AppTreeEvidence(
                digest_algorithm="sha256-test-v1",
                file_count=3,
                sha256="d" * 64,
                total_bytes=123,
            ),
            runs=(launch_record(1), launch_record(2)),
            sqlite_evidence=sqlite_evidence(),
            runtime_identity_present=runtime_identity_present,
            snapshot_files=(
                snapshot_files
                if snapshot_files is not None
                else self.snapshot_files(release_id)
            ),
        )

    def test_result_records_exact_same_snapshot_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result = self.build(Path(temporary_name))
        self.assertEqual(result["schemaVersion"], 2)
        self.assertEqual(result["scope"], smoke.RESULT_SCOPE)
        self.assertIs(
            result["state"]["runtimeIdentityFilePresent"],
            True,
        )
        self.assertEqual(
            result["archiveReadback"],
            {
                "currentSourceCompared": False,
                "mode": "archive-only-no-current-source",
                "readbackAndExerciseSameSnapshot": True,
                "snapshotFiles": self.snapshot_files("build-987"),
                "snapshotFilesUnchangedAfterExercise": True,
                "status": "passed",
            },
        )

    def test_result_requires_runtime_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            for value in (False, 0, 1, None):
                with self.subTest(value=value):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        self.build(
                            Path(temporary_name),
                            runtime_identity_present=value,  # type: ignore[arg-type]
                        )

    def test_result_rejects_closed_snapshot_contract_mutations(self) -> None:
        release_id = "build-987"
        baseline = self.snapshot_files(release_id)
        mutations: list[dict[str, dict[str, object]]] = []

        missing = copy.deepcopy(baseline)
        missing.pop(f"{release_id}.zip.sha256")
        mutations.append(missing)

        extra = copy.deepcopy(baseline)
        extra["extra"] = {"sha256": "e" * 64, "size": 1}
        mutations.append(extra)

        unknown_record_key = copy.deepcopy(baseline)
        unknown_record_key[f"{release_id}.zip"]["extra"] = True
        mutations.append(unknown_record_key)

        for invalid_size in (True, 0, -1):
            candidate = copy.deepcopy(baseline)
            candidate[f"{release_id}.zip"]["size"] = invalid_size
            mutations.append(candidate)

        for invalid_hash in ("A" * 64, "a" * 63, "g" * 64):
            candidate = copy.deepcopy(baseline)
            candidate[f"{release_id}.zip.sha256"]["sha256"] = invalid_hash
            mutations.append(candidate)

        archive_mismatch = copy.deepcopy(baseline)
        archive_mismatch[f"{release_id}.zip"]["sha256"] = "d" * 64
        mutations.append(archive_mismatch)

        manifest_mismatch = copy.deepcopy(baseline)
        manifest_mismatch[f"{release_id}.manifest.json"]["sha256"] = "d" * 64
        mutations.append(manifest_mismatch)

        with tempfile.TemporaryDirectory() as temporary_name:
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        self.build(
                            Path(temporary_name),
                            snapshot_files=mutation,
                        )

    def test_default_result_path_tracks_current_build_and_v2(self) -> None:
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
                "macos-packaged-app-build-987-local-dmg-install-v2.json",
            )

    def test_result_path_must_remain_outside_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            archive = Path(temporary_name) / "archive"
            archive.mkdir()
            for result in (archive, archive / "result.json"):
                with self.subTest(result=result):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.require_result_outside_archive(result, archive)
            smoke.require_result_outside_archive(
                Path(temporary_name) / "result.json",
                archive,
            )


class SnapshotIntegrationTests(unittest.TestCase):
    def test_snapshot_isolated_from_source_and_rechecked_after_use(self) -> None:
        version = smoke.recovery.ReleaseVersion(
            build_number=987,
            marketing_version="9.8.7",
            semantic_version=(9, 8, 7),
        )
        release_id = smoke.recovery.release_id_for(version)
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            archive = root / release_id
            archive.mkdir()
            source_payloads = {
                f"{release_id}.zip": b"zip bytes",
                f"{release_id}.manifest.json": b"manifest bytes",
                f"{release_id}.zip.sha256": b"checksum bytes",
            }
            for name, payload in source_payloads.items():
                (archive / name).write_bytes(payload)

            snapshot, identities = smoke.upgrade.snapshot_archive_directory(
                archive,
                version=version,
                destination_parent=root / "snapshots",
            )
            for name in source_payloads:
                (archive / name).write_bytes(b"changed source")
            smoke.upgrade.require_unchanged_archive_snapshot(
                snapshot,
                identities,
            )

            (snapshot / f"{release_id}.zip").write_bytes(b"changed snapshot")
            with self.assertRaises(smoke.engine.LifecycleSmokeError):
                smoke.upgrade.require_unchanged_archive_snapshot(
                    snapshot,
                    identities,
                )


class ExecuteOrchestrationTests(unittest.TestCase):
    def exercise(
        self,
        *,
        recheck_failure: bool,
    ) -> tuple[list[str], bool]:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            archive_dir = root / "archive"
            archive_dir.mkdir()
            snapshot_dir = root / "snapshot" / "build-987"
            snapshot_dir.mkdir(parents=True)
            result_path = root / "result.json"
            version = smoke.recovery.ReleaseVersion(
                build_number=987,
                marketing_version="9.8.7",
                semantic_version=(9, 8, 7),
            )
            snapshot_files = {
                "build-987.manifest.json": {
                    "sha256": "b" * 64,
                    "size": 200,
                },
                "build-987.zip": {
                    "sha256": "a" * 64,
                    "size": 300,
                },
                "build-987.zip.sha256": {
                    "sha256": "c" * 64,
                    "size": 100,
                },
            }
            release = smoke.engine.ReleaseInputs(
                archive_dir=snapshot_dir,
                archive_path=snapshot_dir / "build-987.zip",
                manifest_path=snapshot_dir / "build-987.manifest.json",
                checksum_path=snapshot_dir / "build-987.zip.sha256",
                archive_sha256="a" * 64,
                manifest_sha256="b" * 64,
                manifest={},
            )
            tree = smoke.installed.AppTreeEvidence(
                "sha256-test",
                1,
                "d" * 64,
                1,
            )
            events: list[str] = []
            identity_path: list[Path] = []

            def snapshot(*_args: object, **_kwargs: object) -> object:
                events.append("snapshot")
                return snapshot_dir, snapshot_files

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

            def verify_readback(
                path: Path,
                *,
                historical: bool,
            ) -> None:
                self.assertEqual(path, snapshot_dir)
                self.assertIs(historical, False)
                events.append("readback")

            def extract(
                _release: smoke.engine.ReleaseInputs,
                destination: Path,
            ) -> Path:
                destination.mkdir(parents=True)
                return destination

            def stage(_source: Path, staging: Path) -> Path:
                staging.mkdir()
                staged_app = staging / smoke.installed.APP_RELATIVE_PATH
                staged_app.mkdir()
                return staged_app

            def command_runner(
                command: tuple[str, ...],
            ) -> smoke.base.CommandResult:
                operation = command[1]
                if operation == "create":
                    events.append("create")
                    Path(command[-1]).write_bytes(b"fixture DMG")
                    return smoke.base.CommandResult(stdout=b"", stderr=b"")
                if operation == "verify":
                    events.append("verify")
                    return smoke.base.CommandResult(stdout=b"", stderr=b"")
                if operation == "attach":
                    events.append("attach")
                    mountpoint = Path(
                        command[command.index("-mountpoint") + 1]
                    )
                    return smoke.base.CommandResult(
                        stdout=attach_plist(mountpoint),
                        stderr=b"",
                    )
                if operation == "detach":
                    events.append("detach")
                    return smoke.base.CommandResult(stdout=b"", stderr=b"")
                self.fail(f"unexpected command: {command}")

            def copy_from_dmg(
                **_keywords: object,
            ) -> smoke.installed.AppTreeEvidence:
                events.append("copy")
                return tree

            def isolated_environment(
                _source: object,
                *,
                home: Path,
                temporary: Path,
                identity_file: Path,
            ) -> dict[str, str]:
                self.assertTrue(home.is_dir())
                self.assertTrue(temporary.is_dir())
                identity_path.append(identity_file)
                return {}

            def launch_cycle(
                **keywords: object,
            ) -> tuple[int, dict[str, object]]:
                ordinal = int(keywords["ordinal"])
                events.append(f"launch{ordinal}")
                if ordinal == 1:
                    identity_path[0].write_bytes(b"identity")
                return 100 + ordinal, launch_record(ordinal)

            def recheck(
                directory: Path,
                identities: dict[str, dict[str, object]],
            ) -> None:
                self.assertEqual(directory, snapshot_dir)
                self.assertIs(identities, snapshot_files)
                events.append("snapshot-recheck")
                if recheck_failure:
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
                patch.object(
                    smoke.upgrade,
                    "snapshot_archive_directory",
                    side_effect=snapshot,
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
                    smoke.base,
                    "copy_from_mounted_dmg",
                    side_effect=copy_from_dmg,
                ),
                patch.object(
                    smoke.base,
                    "wait_for_unmounted",
                    side_effect=lambda _mount: events.append("unmount"),
                ),
                patch.object(
                    smoke.installed,
                    "isolated_launch_environment",
                    side_effect=isolated_environment,
                ),
                patch.object(
                    smoke.installed,
                    "run_launch_services_cycle",
                    side_effect=launch_cycle,
                ),
                patch.object(
                    smoke.installed,
                    "sqlite_state_evidence",
                    return_value=sqlite_evidence(),
                ),
                patch.object(
                    smoke.installed,
                    "state_file_records",
                    return_value=(),
                ),
                patch.object(
                    smoke.upgrade,
                    "require_unchanged_archive_snapshot",
                    side_effect=recheck,
                ),
                patch.object(
                    smoke.installed,
                    "assert_preexisting_applications_preserved",
                ),
                patch.object(smoke, "publish_result", side_effect=publish),
            )
            with ExitStack() as stack:
                for context in patches:
                    stack.enter_context(context)
                if recheck_failure:
                    with self.assertRaises(smoke.engine.LifecycleSmokeError):
                        smoke.execute(
                            archive_dir=archive_dir,
                            result_path=result_path,
                            readiness_timeout_seconds=1.0,
                            observation_seconds=(
                                smoke.engine.MINIMUM_OBSERVATION_SECONDS
                            ),
                            termination_timeout_seconds=1.0,
                        )
                else:
                    result = smoke.execute(
                        archive_dir=archive_dir,
                        result_path=result_path,
                        readiness_timeout_seconds=1.0,
                        observation_seconds=(
                            smoke.engine.MINIMUM_OBSERVATION_SECONDS
                        ),
                        termination_timeout_seconds=1.0,
                    )
                    self.assertEqual(result["status"], "passed")
            return events, result_path.exists()

    def test_execute_uses_snapshot_and_rechecks_before_publication(self) -> None:
        events, published_on_disk = self.exercise(recheck_failure=False)
        self.assertEqual(
            events,
            [
                "snapshot",
                "readback",
                "load",
                "create",
                "verify",
                "attach",
                "copy",
                "detach",
                "unmount",
                "launch1",
                "launch2",
                "snapshot-recheck",
                "publish",
            ],
        )
        self.assertFalse(published_on_disk)

    def test_snapshot_recheck_failure_prevents_publication(self) -> None:
        events, published_on_disk = self.exercise(recheck_failure=True)
        self.assertEqual(events[-1], "snapshot-recheck")
        self.assertNotIn("publish", events)
        self.assertFalse(published_on_disk)


class MainBoundaryTests(unittest.TestCase):
    def test_main_prints_only_path_free_failure(self) -> None:
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
            "Local DMG install v2 smoke failed.\n",
        )
        self.assertNotIn("/private/sensitive", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
