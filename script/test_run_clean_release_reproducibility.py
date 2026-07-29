#!/usr/bin/env python3
"""Pure local regressions for the two-root clean-release runner."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import script.check_release_artifact_archive as readback_module
import script.package_release_artifacts as builder_module
import script.run_clean_release_reproducibility as runner


class CleanReleaseReproducibilityTests(unittest.TestCase):
    @staticmethod
    def identity(data: bytes = b"fixture\n") -> runner.FileIdentity:
        return runner.FileIdentity(
            device=1,
            inode=2,
            mode=0o644,
            uid=os.getuid(),
            gid=os.getgid(),
            size=len(data),
            mtime_ns=3,
            ctime_ns=4,
            sha256=hashlib.sha256(data).hexdigest(),
        )

    @classmethod
    def evidence(cls, root: Path) -> runner.ArchiveEvidence:
        identity = cls.identity()
        return runner.ArchiveEvidence(
            archive_directory=root,
            archive_path=root / "archive.zip",
            manifest_path=root / "manifest.json",
            checksum_path=root / "archive.zip.sha256",
            archive_identity=identity,
            manifest_identity=identity,
            checksum_identity=identity,
            zip_entry_count=2,
            payload_member_count=1,
            normalizations=(
                "android/mapping/configuration.txt:"
                "declared-extracted-file-root-markers",
            ),
            source_sha256="a" * 64,
            member_inventory=(),
        )

    def test_source_inventory_includes_runner_once_and_matches_readback(
        self,
    ) -> None:
        relative = "script/run_clean_release_reproducibility.py"
        self.assertEqual(
            builder_module.SOURCE_REQUIRED_FILES.count(relative),
            1,
        )
        self.assertEqual(
            builder_module.SOURCE_REQUIRED_FILES,
            readback_module.SOURCE_REQUIRED_FILES,
        )

    def test_swift_closure_diagnostic_uses_canonical_source_location(
        self,
    ) -> None:
        source = (
            runner.ROOT
            / "apps/macos/CompanionCore/Sources/"
            "RuntimeDocumentSourceManager.swift"
        ).read_text(encoding="utf-8")
        marker = (
            '#sourceLocation(file: "/aetherlink/source/apps/macos/'
            "CompanionCore/Sources/"
            'RuntimeDocumentSourceManager+Reproducibility.swift", line: 304)'
        )
        self.assertEqual(source.count(marker), 1)
        self.assertEqual(source.count("#sourceLocation()"), 1)
        self.assertLess(source.index(marker), source.index("NSFileCoordinator()"))

    def test_direct_cli_entrypoint_imports_project_package(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(runner.ROOT / "script/run_clean_release_reproducibility.py"),
                "--help",
            ],
            cwd=runner.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result)
        self.assertIn("--result", result.stdout)

    def test_default_result_path_is_release_id_qualified(self) -> None:
        current = mock.Mock(
            build_number=8,
            marketing_version="1.0.0",
        )
        with mock.patch.object(
            runner,
            "load_release_version_ledger",
            return_value=(current,),
        ):
            self.assertEqual(
                runner.default_result_path(),
                runner.RESULT_ROOT
                / "aetherlink-1.0.0+8-local-v1-two-root-v2.json",
            )

    def test_git_refs_capture_head_and_origin_independently(self) -> None:
        with mock.patch.object(
            runner,
            "run_bytes",
            side_effect=(b"a" * 40 + b"\n", b"b" * 40 + b"\n"),
        ):
            refs = runner.capture_git_refs(Path("/fixture"))
        self.assertEqual(refs.head, "a" * 40)
        self.assertEqual(refs.origin_main, "b" * 40)

    def test_canonical_result_and_swift_policy_are_exact(self) -> None:
        result = runner.empty_result()
        encoded = runner.canonical_json_bytes(result)
        self.assertEqual(result["schemaVersion"], 2)
        self.assertIsNone(result["scratch"]["sourceRoots"])
        self.assertIsNone(result["publication"])
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertEqual(
            encoded,
            json.dumps(
                result,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
            + b"\n",
        )
        arguments = result["toolchainPolicy"]["swiftArguments"]
        self.assertEqual(arguments.count("--jobs"), 1)
        self.assertEqual(arguments.count("-fdisable-module-hash"), 1)
        self.assertEqual(arguments.count("-working-directory"), 1)
        self.assertEqual(arguments.count(str(runner.SWIFT_SCRATCH)), 2)
        self.assertEqual(
            arguments.count(
                "-fdebug-compilation-dir=/aetherlink/source"
            ),
            1,
        )
        self.assertEqual(
            arguments.count("-fbuild-session-timestamp=0"),
            1,
        )
        self.assertEqual(arguments.count("-fno-pch-timestamp"), 1)

    def test_source_roots_require_exact_unequal_length_evidence(self) -> None:
        roots = tuple(
            Path("/private/tmp") / name / "project"
            for name in runner.SOURCE_ROOT_NAMES
        )
        evidence = runner.source_root_length_evidence(roots)
        expected_lengths = {
            label: len(os.fsencode(str(root)))
            for label, root in zip(("build-a", "build-b"), roots)
        }
        self.assertEqual(
            evidence,
            {
                "policy": runner.SOURCE_ROOT_POLICY,
                "sourceRootByteLengths": expected_lengths,
                "sourceRootLengthsDiffer": True,
            },
        )
        self.assertNotEqual(
            expected_lengths["build-a"],
            expected_lengths["build-b"],
        )

        invalid_evidence = (
            {
                "policy": runner.SOURCE_ROOT_POLICY,
                "sourceRootByteLengths": {
                    "build-a": expected_lengths["build-a"],
                },
                "sourceRootLengthsDiffer": True,
            },
            {
                "policy": runner.SOURCE_ROOT_POLICY,
                "sourceRootByteLengths": {
                    "build-a": True,
                    "build-b": expected_lengths["build-b"],
                },
                "sourceRootLengthsDiffer": True,
            },
            {
                "policy": runner.SOURCE_ROOT_POLICY,
                "sourceRootByteLengths": {
                    "build-a": expected_lengths["build-a"] + 1,
                    "build-b": expected_lengths["build-b"],
                },
                "sourceRootLengthsDiffer": True,
            },
            {
                "policy": runner.SOURCE_ROOT_POLICY,
                "sourceRootByteLengths": expected_lengths,
                "sourceRootLengthsDiffer": False,
            },
        )
        for mutated in invalid_evidence:
            with self.subTest(mutated=mutated), self.assertRaises(
                runner.ReproducibilityError
            ):
                runner.validate_source_root_length_evidence(mutated, roots)

        equal_length_roots = (
            Path("/private/tmp/root-a/project"),
            Path("/private/tmp/root-b/project"),
        )
        with self.assertRaisesRegex(
            runner.ReproducibilityError,
            "different UTF-8 byte lengths",
        ):
            runner.source_root_length_evidence(equal_length_roots)

    def test_overlay_capture_uses_one_byte_snapshot_and_tracks_deletion(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tracked.txt").write_bytes(b"tracked\n")
            (root / "untracked.txt").write_bytes(b"untracked\n")
            outputs = (
                b"",
                b"deleted.txt\0tracked.txt\0",
                b"untracked.txt\0",
            )
            with mock.patch.object(
                runner,
                "run_bytes",
                side_effect=outputs,
            ):
                overlay = runner.capture_source_overlay(root)

            self.assertEqual(
                [record.path for record in overlay.records],
                ["tracked.txt", "untracked.txt"],
            )
            self.assertEqual(
                overlay.tracked_deletions,
                ("deleted.txt",),
            )
            self.assertRegex(overlay.sha256, r"^[0-9a-f]{64}$")

    def test_overlay_capture_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text("target\n", encoding="utf-8")
            (root / "linked").symlink_to(target)
            with (
                mock.patch.object(
                    runner,
                    "run_bytes",
                    side_effect=(b"", b"linked\0", b""),
                ),
                self.assertRaisesRegex(
                    runner.ReproducibilityError,
                    "not a regular file",
                ),
            ):
                runner.capture_source_overlay(root)

    def test_materialize_clone_writes_only_captured_overlay(self) -> None:
        overlay = runner.SourceOverlay(
            records=(
                runner.OverlayRecord("script/run.sh", b"#!/bin/sh\n", 0o755),
                runner.OverlayRecord("README.md", b"readme\n", 0o644),
            ),
            tracked_deletions=("deleted.txt",),
            sha256="0" * 64,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "lane/project"

            def fake_clone(*args: object, **kwargs: object) -> None:
                command = args[0]
                if "clone" in command:
                    destination.mkdir(parents=True)
                    (destination / ".git").mkdir()

            git_refs = runner.GitRefs("a" * 40, "b" * 40)
            with (
                mock.patch.object(
                    runner,
                    "run_checked",
                    side_effect=fake_clone,
                ) as checked,
                mock.patch.object(
                    runner,
                    "run_bytes",
                    side_effect=(b"a" * 40 + b"\n", b"b" * 40 + b"\n"),
                ),
            ):
                runner.materialize_clone(
                    destination,
                    overlay,
                    git_refs,
                    root=root,
                )

            self.assertEqual(
                (destination / "README.md").read_bytes(),
                b"readme\n",
            )
            self.assertTrue(
                (destination / "script/run.sh").stat().st_mode & 0o111
            )
            self.assertFalse((destination / "deleted.txt").exists())
            update_command = checked.call_args_list[1].args[0]
            self.assertEqual(
                update_command,
                [
                    "git",
                    "update-ref",
                    "refs/remotes/origin/main",
                    "b" * 40,
                ],
            )

    def test_fixed_lock_and_owned_scratch_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            scratch = base / "scratch"
            lock = work_root / ".lock"
            lease = work_root / ".lease.json"
            patches = (
                mock.patch.object(runner, "WORK_ROOT", work_root),
                mock.patch.object(runner, "SWIFT_SCRATCH", scratch),
                mock.patch.object(runner, "LOCK_PATH", lock),
                mock.patch.object(runner, "SWIFT_LEASE_PATH", lease),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with runner.acquire_run_lock():
                    with self.assertRaisesRegex(
                        runner.ReproducibilityError,
                        "another reproducibility runner",
                    ):
                        with runner.acquire_run_lock():
                            pass
                    runner.create_swift_lease("run-id")
                    scratch.mkdir(mode=0o700)
                    (scratch / "owned").write_bytes(b"owned\n")
                    runner.cleanup_swift_scratch(
                        "run-id",
                        remove_lease=True,
                    )
                    self.assertFalse(os.path.lexists(scratch))
                    self.assertFalse(os.path.lexists(lease))

    def test_protected_build3_detects_byte_and_inode_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / runner.PROTECTED_RELEASE_RELATIVE
            directory.mkdir(parents=True)
            archive_id = directory.name
            files = (
                f"{archive_id}.zip",
                f"{archive_id}.manifest.json",
                f"{archive_id}.zip.sha256",
            )
            for name in files:
                (directory / name).write_bytes(name.encode("ascii"))
            before = runner.capture_protected_archive(root)
            target = directory / files[0]
            target.write_bytes(b"changed\n")
            after_bytes = runner.capture_protected_archive(root)
            self.assertNotEqual(before, after_bytes)
            replacement = directory / ".replacement"
            replacement.write_bytes(b"changed\n")
            os.replace(replacement, target)
            after_inode = runner.capture_protected_archive(root)
            self.assertNotEqual(after_bytes, after_inode)

    def test_tree_digest_detects_non_root_byte_difference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "cache.bin").write_bytes(b"same")
            (second / "cache.bin").write_bytes(b"same")
            self.assertEqual(
                runner.tree_digest(first),
                runner.tree_digest(second),
            )
            (second / "cache.bin").write_bytes(b"different")
            self.assertNotEqual(
                runner.tree_digest(first),
                runner.tree_digest(second),
            )

    def test_gradle_cache_pair_is_cloned_from_one_seed_and_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            live_seed = root / "live-gradle"
            run_root = root / "run"
            live_seed.mkdir()
            run_root.mkdir()
            (live_seed / "caches").mkdir()
            (live_seed / "caches/module.bin").write_bytes(b"module")

            cache_a, cache_b, file_count, digest = (
                runner.prepare_gradle_caches(
                    run_root,
                    {"GRADLE_USER_HOME": str(live_seed)},
                )
            )

            self.assertEqual(file_count, 1)
            self.assertEqual(
                (file_count, digest),
                runner.tree_digest(cache_a),
            )
            self.assertEqual(
                runner.tree_digest(cache_a),
                runner.tree_digest(cache_b),
            )
            (cache_a / "caches/module.bin").write_bytes(b"changed")
            self.assertNotEqual(
                runner.tree_digest(cache_a),
                runner.tree_digest(cache_b),
            )
            self.assertEqual(
                (cache_b / "caches/module.bin").read_bytes(),
                b"module",
            )

    def test_archive_comparison_checks_sidecars_and_member_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence: list[runner.ArchiveEvidence] = []
            release_id = "aetherlink-1.0.0+4-local-v1"
            manifest = {
                "archive": {
                    "memberCountExcludingManifest": 1,
                    "normalizations": [
                        "android/mapping/configuration.txt:"
                        "declared-extracted-file-root-markers"
                    ],
                },
                "source": {"snapshotSha256": "a" * 64},
            }
            manifest_bytes = json.dumps(manifest).encode("ascii")
            for lane in ("a", "b"):
                clone = root / lane
                directory = clone / "dist/releases" / release_id
                directory.mkdir(parents=True)
                archive_path = directory / f"{release_id}.zip"
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("manifest.json", manifest_bytes)
                    archive.writestr("payload.bin", b"payload")
                (directory / f"{release_id}.manifest.json").write_bytes(
                    manifest_bytes
                )
                (directory / f"{release_id}.zip.sha256").write_text(
                    hashlib.sha256(archive_path.read_bytes()).hexdigest()
                    + f"  {archive_path.name}\n",
                    encoding="ascii",
                )
                evidence.append(runner.capture_archive(clone, release_id))

            comparison = runner.compare_archives(*evidence)
            self.assertTrue(comparison["archiveBytesEqual"])
            self.assertTrue(comparison["memberBytesEqual"])
            self.assertEqual(comparison["memberDifferences"], [])
            self.assertEqual(
                len(evidence[0].result_record("build-a")["archive"]["members"]),
                2,
            )

            second_archive = evidence[1].archive_path
            with zipfile.ZipFile(second_archive, "w") as archive:
                archive.writestr("manifest.json", manifest_bytes)
                archive.writestr("payload.bin", b"changed")
            changed = runner.capture_archive(root / "b", release_id)
            comparison = runner.compare_archives(evidence[0], changed)
            self.assertIn("member-bytes", comparison["differences"])
            self.assertEqual(
                [record["path"] for record in comparison["memberDifferences"]],
                ["payload.bin"],
            )
            self.assertEqual(
                comparison["memberDifferences"][0]["diagnostic"],
                {
                    "firstDifferenceOffset": 0,
                    "sizeA": 7,
                    "sizeB": 7,
                },
            )

    def test_execute_never_builds_from_original_and_holds_lock_through_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            work_root.mkdir(mode=0o700)
            result_path = base / "result/result.json"
            evidence = self.evidence(base)
            source_snapshot = {
                "algorithm": "fixture-v1",
                "fileCount": 1,
                "files": [],
                "sha256": "a" * 64,
            }
            sentinel = ("b" * 64, {"fixture": self.identity()})
            events: list[str] = []

            @contextmanager
            def fake_lock() -> object:
                events.append("lock-enter")
                try:
                    yield
                finally:
                    events.append("lock-exit")

            def fake_cleanup(*args: object, **kwargs: object) -> None:
                events.append("scratch-cleanup")

            def fake_publish(*args: object, **kwargs: object) -> dict[str, object]:
                events.append("publish")
                return {
                    "alreadyMatched": False,
                    "archiveDirectory": "dist/releases/fixture",
                    "archiveSha256": "f" * 64,
                    "checksumSha256": "e" * 64,
                    "independentReadback": True,
                    "manifestSha256": "d" * 64,
                    "publishedBytesEqualLaneA": True,
                    "sourceLane": "build-a",
                    "sourceSnapshotUnchanged": True,
                }

            with (
                mock.patch.object(runner, "WORK_ROOT", work_root),
                mock.patch.object(
                    runner,
                    "capture_protected_archive",
                    side_effect=(sentinel, sentinel),
                ),
                mock.patch.object(runner, "acquire_run_lock", fake_lock),
                mock.patch.object(runner, "preflight_fixed_paths"),
                mock.patch.object(runner, "create_swift_lease"),
                mock.patch.object(
                    runner,
                    "capture_source_overlay",
                    return_value=runner.SourceOverlay(
                        records=(),
                        tracked_deletions=(),
                        sha256="c" * 64,
                    ),
                ),
                mock.patch.object(
                    runner,
                    "capture_git_refs",
                    return_value=runner.GitRefs("1" * 40, "2" * 40),
                ),
                mock.patch.object(
                    runner.archive_builder,
                    "source_snapshot",
                    return_value=source_snapshot,
                ),
                mock.patch.object(runner, "materialize_clone"),
                mock.patch.object(
                    runner,
                    "prepare_gradle_caches",
                    return_value=(base / "ga", base / "gb", 1, "d" * 64),
                ),
                mock.patch.object(
                    runner,
                    "resolve_android_sdk",
                    return_value=base / "sdk",
                ),
                mock.patch.object(
                    runner,
                    "run_lane",
                    side_effect=(evidence, evidence),
                ) as run_lane_mock,
                mock.patch.object(
                    runner,
                    "compare_archives",
                    return_value={
                        "archiveBytesEqual": True,
                        "differences": [],
                        "memberBytesEqual": True,
                        "memberDifferences": [],
                        "memberMetadataEqual": True,
                        "memberSetEqual": True,
                        "normalizations": [],
                    },
                ),
                mock.patch.object(
                    runner,
                    "cleanup_swift_scratch",
                    side_effect=fake_cleanup,
                ),
                mock.patch.object(
                    runner,
                    "publish_qualified_archive",
                    side_effect=fake_publish,
                ),
            ):
                exit_code, result = runner.execute(result_path)

            self.assertEqual(exit_code, 0, result)
            build_roots = [call.args[0] for call in run_lane_mock.call_args_list]
            self.assertEqual(len(build_roots), 2)
            self.assertTrue(all(work_root in path.parents for path in build_roots))
            self.assertTrue(all(path != runner.ROOT for path in build_roots))
            lengths = result["scratch"]["sourceRoots"][
                "sourceRootByteLengths"
            ]
            self.assertEqual(
                lengths,
                {
                    label: len(os.fsencode(str(root)))
                    for label, root in zip(
                        ("build-a", "build-b"),
                        build_roots,
                    )
                },
            )
            self.assertNotEqual(lengths["build-a"], lengths["build-b"])
            self.assertTrue(
                result["scratch"]["sourceRoots"]["sourceRootLengthsDiffer"]
            )
            self.assertTrue(result["publication"]["independentReadback"])
            self.assertLess(events.index("publish"), events.index("lock-exit"))
            self.assertLess(events.index("scratch-cleanup"), events.index("lock-exit"))
            self.assertTrue(result["protectedArchive"]["unchanged"])

    def test_protected_or_source_result_path_is_rejected_without_write(
        self,
    ) -> None:
        protected_result = (
            runner.ROOT
            / runner.PROTECTED_RELEASE_RELATIVE
            / "aetherlink-1.0.0+3-local-v1.manifest.json"
        ).resolve()
        source_result = (runner.ROOT / "release/version-ledger.tsv").resolve()
        for path in (protected_result, source_result):
            with self.subTest(path=path), self.assertRaisesRegex(
                runner.ReproducibilityError,
                "result path must be",
            ):
                runner.preflight_fixed_paths(path)

        sentinel = ("b" * 64, {"fixture": self.identity()})
        with (
            mock.patch.object(
                runner,
                "capture_protected_archive",
                side_effect=(sentinel, sentinel),
            ),
            mock.patch.object(runner, "acquire_run_lock"),
            mock.patch.object(
                runner,
                "preflight_fixed_paths",
                side_effect=runner.ReproducibilityError(
                    2,
                    "invocation",
                    "rejected result",
                ),
            ),
            mock.patch.object(runner, "write_result") as write_mock,
        ):
            exit_code, result = runner.execute(protected_result)
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["failure"]["phase"], "invocation")
        write_mock.assert_not_called()

    def test_result_write_failure_returns_controlled_internal_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            work_root.mkdir(mode=0o700)
            sentinel = ("b" * 64, {"fixture": self.identity()})

            @contextmanager
            def fake_lock() -> object:
                yield

            with (
                mock.patch.object(runner, "WORK_ROOT", work_root),
                mock.patch.object(
                    runner,
                    "capture_protected_archive",
                    side_effect=(sentinel, sentinel),
                ),
                mock.patch.object(runner, "acquire_run_lock", fake_lock),
                mock.patch.object(runner, "preflight_fixed_paths"),
                mock.patch.object(runner, "create_swift_lease"),
                mock.patch.object(runner, "cleanup_swift_scratch"),
                mock.patch.object(
                    runner,
                    "capture_git_refs",
                    side_effect=runner.ReproducibilityError(
                        4,
                        "source-capture",
                        "fixture failure",
                    ),
                ),
                mock.patch.object(
                    runner,
                    "write_result",
                    side_effect=OSError("read-only result target"),
                ),
            ):
                exit_code, result = runner.execute(base / "result.json")

            self.assertEqual(exit_code, 70)
            self.assertEqual(result["failure"]["phase"], "result-write")

    def test_keyboard_interrupt_returns_controlled_failure_and_cleans_up(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            work_root.mkdir(mode=0o700)
            sentinel = ("b" * 64, {"fixture": self.identity()})
            cleaned: list[str] = []

            @contextmanager
            def fake_lock() -> object:
                yield

            with (
                mock.patch.object(runner, "WORK_ROOT", work_root),
                mock.patch.object(
                    runner,
                    "capture_protected_archive",
                    side_effect=(sentinel, sentinel),
                ),
                mock.patch.object(runner, "acquire_run_lock", fake_lock),
                mock.patch.object(runner, "preflight_fixed_paths"),
                mock.patch.object(runner, "create_swift_lease"),
                mock.patch.object(
                    runner,
                    "capture_git_refs",
                    return_value=runner.GitRefs("1" * 40, "2" * 40),
                ),
                mock.patch.object(
                    runner,
                    "capture_source_overlay",
                    side_effect=KeyboardInterrupt,
                ),
                mock.patch.object(
                    runner,
                    "cleanup_swift_scratch",
                    side_effect=lambda *args, **kwargs: cleaned.append(
                        "scratch"
                    ),
                ),
            ):
                exit_code, result = runner.execute(base / "result.json")

            self.assertEqual(exit_code, 130)
            self.assertEqual(result["failure"]["phase"], "interrupted")
            self.assertEqual(cleaned, ["scratch"])
            self.assertEqual(
                json.loads((base / "result.json").read_text(encoding="ascii")),
                result,
            )

    def test_sentinel_change_overrides_a_passing_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            work_root.mkdir(mode=0o700)
            evidence = self.evidence(base)
            source_snapshot = {
                "algorithm": "fixture-v1",
                "fileCount": 1,
                "files": [],
                "sha256": "a" * 64,
            }
            before = ("b" * 64, {"fixture": self.identity(b"before")})
            after = ("c" * 64, {"fixture": self.identity(b"after")})
            with (
                mock.patch.object(runner, "WORK_ROOT", work_root),
                mock.patch.object(
                    runner,
                    "capture_protected_archive",
                    side_effect=(before, after),
                ),
                mock.patch.object(runner, "acquire_run_lock"),
                mock.patch.object(runner, "preflight_fixed_paths"),
                mock.patch.object(runner, "create_swift_lease"),
                mock.patch.object(
                    runner,
                    "capture_source_overlay",
                    return_value=runner.SourceOverlay((), (), "d" * 64),
                ),
                mock.patch.object(
                    runner,
                    "capture_git_refs",
                    return_value=runner.GitRefs("1" * 40, "2" * 40),
                ),
                mock.patch.object(
                    runner.archive_builder,
                    "source_snapshot",
                    return_value=source_snapshot,
                ),
                mock.patch.object(runner, "materialize_clone"),
                mock.patch.object(
                    runner,
                    "prepare_gradle_caches",
                    return_value=(base / "ga", base / "gb", 1, "e" * 64),
                ),
                mock.patch.object(
                    runner,
                    "resolve_android_sdk",
                    return_value=base / "sdk",
                ),
                mock.patch.object(
                    runner,
                    "run_lane",
                    side_effect=(evidence, evidence),
                ),
                mock.patch.object(
                    runner,
                    "compare_archives",
                    return_value={
                        "archiveBytesEqual": True,
                        "differences": [],
                        "memberBytesEqual": True,
                        "memberMetadataEqual": True,
                        "memberSetEqual": True,
                        "normalizations": [],
                    },
                ),
                mock.patch.object(
                    runner,
                    "publish_qualified_archive",
                    return_value={
                        "alreadyMatched": False,
                        "archiveDirectory": "dist/releases/fixture",
                        "archiveSha256": "f" * 64,
                        "checksumSha256": "e" * 64,
                        "independentReadback": True,
                        "manifestSha256": "d" * 64,
                        "publishedBytesEqualLaneA": True,
                        "sourceLane": "build-a",
                        "sourceSnapshotUnchanged": True,
                    },
                ),
                mock.patch.object(runner, "cleanup_swift_scratch"),
            ):
                exit_code, result = runner.execute(base / "result.json")

            self.assertEqual(exit_code, 9)
            self.assertEqual(result["failure"]["phase"], "protected-archive")
            self.assertFalse(result["protectedArchive"]["unchanged"])


if __name__ == "__main__":
    unittest.main()
