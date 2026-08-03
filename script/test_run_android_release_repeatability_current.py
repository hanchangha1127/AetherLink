#!/usr/bin/env python3
"""Focused regressions for the Android Release A/B producer."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from script import run_android_release_repeatability_current as runner


class AndroidReleaseRepeatabilityRunnerTests(unittest.TestCase):
    @staticmethod
    def zip_fixture(*, reverse: bool, timestamp: tuple[int, int, int, int, int, int]) -> bytes:
        output = io.BytesIO()
        members = [("one", b"1"), ("two", b"2")]
        if reverse:
            members.reverse()
        with zipfile.ZipFile(output, "w") as value:
            for name, payload in members:
                info = zipfile.ZipInfo(name, timestamp)
                value.writestr(info, payload)
        return output.getvalue()

    def test_source_extras_bind_workflow_ci_runner_checker_and_tests(self) -> None:
        self.assertEqual(
            runner.SOURCE_EXTRAS,
            (
                Path(".github/workflows/product-quality.yml"),
                Path("script/check_product_ci.py"),
                Path("script/run_android_release_repeatability_current.py"),
                Path("script/check_android_release_repeatability_current.py"),
                Path("script/test_run_android_release_repeatability_current.py"),
                Path("script/test_check_android_release_repeatability_current.py"),
            ),
        )

    def test_private_snapshot_is_owner_only_and_round_trips_nested_bytes(self) -> None:
        payloads = {"a/b/c.bin": b"one", "top.bin": b"two"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "private"
            with runner.private_snapshot(
                payloads,
                parent=parent,
                root=root,
            ) as snapshot:
                self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(snapshot.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((snapshot / "a").stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((snapshot / "a/b").stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((snapshot / "a/b/c.bin").stat().st_mode), 0o600)
                self.assertEqual(
                    runner.read_private_snapshot(snapshot, tuple(payloads)),
                    payloads,
                )
            self.assertFalse(snapshot.exists())

    def test_atomic_result_is_mode_0600_and_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "nested/result.json"
            runner.publish_atomic_create_only(path, b"{}\n", root=root)
            self.assertEqual(path.read_bytes(), b"{}\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(path.stat().st_nlink, 1)
            with self.assertRaisesRegex(runner.RepeatabilityError, "already exists"):
                runner.publish_atomic_create_only(path, b"{}\n", root=root)

    def test_stable_file_rejects_symlink_hardlink_and_oversize(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_bytes(b"1234")
            (root / "link").symlink_to(target)
            with self.assertRaises(runner.RepeatabilityError):
                runner.stable_file(Path("link"), root=root, maximum_bytes=8)
            os.link(target, root / "hard")
            with self.assertRaises(runner.RepeatabilityError):
                runner.stable_file(Path("target"), root=root, maximum_bytes=8)
            (root / "single").write_bytes(b"1234")
            with self.assertRaises(runner.RepeatabilityError):
                runner.stable_file(Path("single"), root=root, maximum_bytes=3)

    def test_directory_inventory_rejects_symlink_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "file").write_bytes(b"x")
            (root / "link").symlink_to(root / "file")
            with self.assertRaises(runner.RepeatabilityError):
                runner.directory_names(root, "fixture", entries_are_directories=False)

    def test_five_normalized_comparison_identities_ignore_only_declared_variance(self) -> None:
        zip_a = self.zip_fixture(reverse=False, timestamp=(2020, 1, 1, 0, 0, 0))
        zip_b = self.zip_fixture(reverse=True, timestamp=(2022, 2, 2, 0, 0, 0))
        dm_path = runner.archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/0/app-release-unsigned.dm"
        prt_path = runner.archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "mapping.prt"
        self.assertNotEqual(zip_a, zip_b)
        self.assertEqual(runner.comparison_identity(dm_path, zip_a), runner.comparison_identity(dm_path, zip_b))
        self.assertEqual(runner.comparison_identity(prt_path, zip_a), runner.comparison_identity(prt_path, zip_b))
        resources_path = runner.archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "resources.txt"
        resources_a = b"pkg:type:1 reachable from first reason\n"
        resources_b = b"pkg:type:1 reachable from second reason\n"
        self.assertEqual(runner.comparison_identity(resources_path, resources_a), runner.comparison_identity(resources_path, resources_b))
        seeds_path = runner.archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "seeds.txt"
        self.assertEqual(runner.comparison_identity(seeds_path, b"b\na\n"), runner.comparison_identity(seeds_path, b"a\nb\n"))
        raw_path = Path("out.bin")
        self.assertNotEqual(runner.comparison_identity(raw_path, b"a"), runner.comparison_identity(raw_path, b"b"))

    def test_lint_xml_is_a_required_raw_ab_output(self) -> None:
        limits = runner.static_output_file_limits()
        self.assertEqual(
            limits[runner.LINT_XML_RELATIVE_PATH],
            runner.SMALL_LIMIT,
        )
        self.assertNotIn(
            runner.LINT_XML_RELATIVE_PATH.as_posix(),
            runner.NORMALIZED_COMPARISON_PATHS,
        )
        self.assertEqual(
            runner.comparison_identity(runner.LINT_XML_RELATIVE_PATH, b"<issues/>"),
            {
                "kind": runner.RAW_COMPARISON_KIND,
                "sha256": hashlib.sha256(b"<issues/>").hexdigest(),
            },
        )

    def test_differing_payload_paths_is_exact_and_ascii_sorted(self) -> None:
        self.assertEqual(
            runner.differing_payload_paths(
                {"same": b"x", "z": b"old", "missing": b"left"},
                {"same": b"x", "z": b"new", "added": b"right"},
            ),
            ("added", "missing", "z"),
        )

    def test_run_process_rejects_bool_limit_and_enforces_output_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(runner.RepeatabilityError, "exact integer"):
                runner.run_process((sys.executable, "-c", "pass"), root=root, timeout_seconds=1, maximum_output_bytes=True)
            with self.assertRaisesRegex(runner.RepeatabilityError, "byte limit"):
                runner.run_process((sys.executable, "-c", "print('x' * 10000)"), root=root, timeout_seconds=5, maximum_output_bytes=32)

    def test_run_process_absolute_deadline_terminates_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(runner, "terminate_process_group", wraps=runner.terminate_process_group) as terminate:
                with self.assertRaisesRegex(runner.RepeatabilityError, "absolute deadline"):
                    runner.run_process((sys.executable, "-c", "import time; time.sleep(5)"), root=Path(temporary), timeout_seconds=0.05, maximum_output_bytes=1024)
                terminate.assert_called_once()

    def test_result_path_must_use_dedicated_repository_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / ".build/evidence/result.json"
            self.assertEqual(
                runner.validated_result_path(
                    Path(".build/evidence/result.json"),
                    root=root,
                ),
                expected,
            )
            for invalid in (
                root / "result.json",
                root / ".build/result.json",
                root.parent / "outside/result.json",
                Path("../outside/result.json"),
            ):
                with self.subTest(path=str(invalid)):
                    with self.assertRaises(runner.RepeatabilityError):
                        runner.validated_result_path(invalid, root=root)

            outside = root / "outside"
            outside.mkdir()
            (root / ".build").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(
                runner.RepeatabilityError,
                "ancestors must be physical",
            ):
                runner.validated_result_path(
                    Path(".build/evidence/result.json"),
                    root=root,
                )

    def test_release_workspace_lock_rejects_overlap_and_accepts_inherited_fd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with runner.acquire_release_workspace_lock(root=root) as descriptor:
                with self.assertRaisesRegex(
                    runner.RepeatabilityError,
                    "already running",
                ):
                    with runner.acquire_release_workspace_lock(root=root):
                        self.fail("overlapping workspace lock unexpectedly succeeded")

                environment: dict[str, str] = {}
                runner.bind_inherited_release_workspace_lock(
                    environment,
                    descriptor,
                )
                with mock.patch.dict(os.environ, environment, clear=False):
                    with runner.acquire_release_workspace_lock(root=root) as inherited:
                        self.assertEqual(inherited, descriptor)

    def test_execute_runs_prepare_and_offline_workflow_for_a_and_b(self) -> None:
        source = {"algorithm": runner.SOURCE_ALGORITHM, "fileCount": 6, "sha256": "a" * 64, "size": 42}
        paths = sorted({"out", *runner.NORMALIZED_COMPARISON_PATHS})
        files = [
            {
                "comparison": {
                    "kind": "normalized-fixture-v1" if path in runner.NORMALIZED_COMPARISON_PATHS else runner.RAW_COMPARISON_KIND,
                    "sha256": hashlib.sha256(path.encode()).hexdigest(),
                },
                "mode": 0o644,
                "path": path,
                "sha256": hashlib.sha256(path.encode()).hexdigest(),
                "size": len(path),
            }
            for path in paths
        ]
        projection = {
            "dex": {"logicalSha256": "b" * 64, "memberCount": 1},
            "comparisonGraphSha256": "c" * 64,
            "fileCount": len(files),
            "files": files,
            "jni": {"intermediateAbis": ["arm64-v8a"], "logicalSha256": "d" * 64, "memberCount": 1, "mergedLogicalSha256": "e" * 64, "packagedAbis": ["arm64-v8a"], "strippedLogicalSha256": "f" * 64},
            "profiles": {"logicalSha256": "1" * 64, "memberCount": 2},
            "rawGraphSha256": "2" * 64,
        }
        process = {"exitCode": 0, "stderr": {"sha256": "0" * 64, "size": 0}, "stdout": {"sha256": "0" * 64, "size": 0}}
        payloads = {path: path.encode() for path in paths}
        readback = {"versionCode": 1}

        @contextmanager
        def snapshot(_payloads: object, *, parent: Path, root: Path):
            del _payloads, parent, root
            yield Path("/snapshot")

        calls: list[tuple[str, ...]] = []
        def run(argv: object, **_kwargs: object) -> dict[str, object]:
            calls.append(tuple(argv))
            return process

        with tempfile.TemporaryDirectory() as temporary, \
            mock.patch.object(runner, "source_snapshot", side_effect=[source, source, source]), \
            mock.patch.object(runner, "command_environment", return_value={}), \
            mock.patch.object(runner, "run_process", side_effect=run), \
            mock.patch.object(runner, "validate_live_outputs", side_effect=[readback, readback]), \
            mock.patch.object(runner, "capture_output_graph", side_effect=[(projection, payloads), (projection, payloads)]), \
            mock.patch.object(runner, "private_snapshot", side_effect=snapshot), \
            mock.patch.object(runner, "read_private_snapshot", return_value=payloads), \
            mock.patch.object(runner, "toolchain_identity", return_value={"host": "fixture"}), \
            mock.patch.object(runner, "publish_atomic_create_only") as publish:
            document = runner.execute(
                root=Path(temporary),
                result_path=Path(temporary) / ".build/evidence/result.json",
            )
        self.assertEqual(calls, [runner.PREPARE_COMMAND, runner.BUILD_COMMAND, runner.PREPARE_COMMAND, runner.BUILD_COMMAND])
        self.assertEqual(document["runs"]["a"], projection)
        self.assertEqual(document["runs"]["b"], projection)
        publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
