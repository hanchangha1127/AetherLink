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

    def test_source_inventory_includes_runtime_chat_cross_process_qa_closure(
        self,
    ) -> None:
        runner_relative = (
            "script/run_macos_runtime_chat_cross_process_smoke.py"
        )
        test_relative = (
            "script/test_run_macos_runtime_chat_cross_process_smoke.py"
        )
        helper_root = (
            "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources"
        )
        self.assertEqual(
            builder_module.SOURCE_REQUIRED_FILES.count(runner_relative),
            1,
        )
        self.assertEqual(
            builder_module.SOURCE_REQUIRED_FILES.count(test_relative),
            1,
        )
        self.assertEqual(
            builder_module.SOURCE_ROOTS.count(helper_root),
            1,
        )
        self.assertEqual(
            builder_module.SOURCE_REQUIRED_FILES,
            readback_module.SOURCE_REQUIRED_FILES,
        )
        self.assertEqual(
            builder_module.SOURCE_ROOTS,
            readback_module.SOURCE_ROOTS,
        )

    def test_source_inventory_includes_local_dmg_runner_once(self) -> None:
        runner_relative = "script/run_macos_local_dmg_install_smoke.py"
        self.assertEqual(
            builder_module.SOURCE_REQUIRED_FILES.count(runner_relative),
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
        self.assertIn("--comparison-only", result.stdout)

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
                / "aetherlink-1.0.0+8-local-v1-two-root-v4.json",
            )
            self.assertEqual(
                runner.default_comparison_result_path(),
                runner.RESULT_ROOT
                / (
                    "aetherlink-1.0.0+8-local-v1"
                    "-two-root-v4-prepublication.json"
                ),
            )

    def test_result_mode_namespaces_are_current_release_qualified(self) -> None:
        current = mock.Mock(
            build_number=8,
            marketing_version="1.0.0",
        )
        publish_names = (
            "aetherlink-1.0.0+8-local-v1-two-root-v4.json",
            "aetherlink-1.0.0+8-local-v1-two-root-v4-confirmation.json",
            "aetherlink-1.0.0+8-local-v1-two-root-v4-attempt1-failed.json",
        )
        comparison_names = (
            "aetherlink-1.0.0+8-local-v1-two-root-v4-prepublication.json",
            (
                "aetherlink-1.0.0+8-local-v1-two-root-v4-"
                "prepublication-confirmation.json"
            ),
            (
                "aetherlink-1.0.0+8-local-v1-two-root-v4-"
                "prepublication-attempt1-interrupted.json"
            ),
        )
        rejected = (
            (publish_names[0], False),
            (comparison_names[0], True),
            ("aetherlink-1.0.0+7-local-v1-two-root-v4.json", True),
            ("result.json", True),
            (
                "aetherlink-1.0.0+8-local-v1-two-root-v4-"
                "prepublication-confirmation.json",
                True,
            ),
            (
                "aetherlink-1.0.0+8-local-v1-two-root-v4-"
                "prepublication-.json",
                False,
            ),
        )
        with mock.patch.object(
            runner,
            "load_release_version_ledger",
            return_value=(current,),
        ):
            for name in publish_names:
                with self.subTest(name=name, publish=True):
                    runner.validate_result_mode_path(
                        runner.RESULT_ROOT / name,
                        publish_qualified=True,
                    )
            for name in comparison_names:
                with self.subTest(name=name, publish=False):
                    runner.validate_result_mode_path(
                        runner.RESULT_ROOT / name,
                        publish_qualified=False,
                    )
            for name, publish_qualified in rejected:
                with self.subTest(
                    name=name,
                    publish=publish_qualified,
                ), self.assertRaisesRegex(
                    runner.ReproducibilityError,
                    "mode namespace",
                ):
                    runner.validate_result_mode_path(
                        runner.RESULT_ROOT / name,
                        publish_qualified=publish_qualified,
                    )

    def test_main_wires_comparison_mode_and_rejects_cross_mode_result(
        self,
    ) -> None:
        current = mock.Mock(
            build_number=8,
            marketing_version="1.0.0",
        )
        comparison_path = (
            runner.RESULT_ROOT
            / "aetherlink-1.0.0+8-local-v1-two-root-v4-prepublication.json"
        )
        canonical_path = (
            runner.RESULT_ROOT
            / "aetherlink-1.0.0+8-local-v1-two-root-v4.json"
        )
        passed = {
            "builds": [{"archive": {"sha256": "a" * 64}}],
            "comparison": {"memberBytesEqual": True},
        }
        with (
            mock.patch.object(
                runner,
                "load_release_version_ledger",
                return_value=(current,),
            ),
            mock.patch.object(
                sys,
                "argv",
                ["runner", "--comparison-only"],
            ),
            mock.patch.object(
                runner,
                "execute",
                return_value=(0, passed),
            ) as execute_mock,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(runner.main(), 0)
        execute_mock.assert_called_once_with(
            comparison_path.resolve(),
            publish_qualified=False,
        )

        for arguments in (
            [
                "runner",
                "--comparison-only",
                "--result",
                str(canonical_path),
            ],
            [
                "runner",
                "--result",
                str(comparison_path),
            ],
        ):
            with (
                mock.patch.object(
                    runner,
                    "load_release_version_ledger",
                    return_value=(current,),
                ),
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "execute") as rejected_execute,
                mock.patch("builtins.print"),
            ):
                self.assertEqual(runner.main(), 2)
            rejected_execute.assert_not_called()

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
        self.assertEqual(result["schemaVersion"], 4)
        self.assertEqual(
            runner.RESULT_PATH_VERSION,
            result["schemaVersion"],
        )
        self.assertEqual(
            result["executionMode"],
            runner.PUBLISH_QUALIFIED_MODE,
        )
        self.assertIsNone(result["releaseId"])
        self.assertIsNone(result["prepublicationBinding"])
        self.assertIsNone(result["scratch"]["sourceRoots"])
        self.assertEqual(
            result["protectedArchive"],
            {
                "afterIdentitySha256": None,
                "beforeIdentitySha256": None,
                "policy": runner.PROTECTED_RELEASE_POLICY,
                "relativePath": None,
                "unchanged": False,
            },
        )
        self.assertEqual(
            result["publication"],
            {
                "attempted": False,
                "independentReadback": False,
                "outcome": "not-reached",
                "policy": runner.PUBLISH_QUALIFIED_PUBLICATION_POLICY,
                "qualifiedArchivePublished": False,
            },
        )
        comparison_only = runner.empty_result(publish_qualified=False)
        self.assertEqual(
            comparison_only["executionMode"],
            runner.COMPARISON_ONLY_MODE,
        )
        self.assertEqual(
            comparison_only["publication"],
            {
                "attempted": False,
                "independentReadback": False,
                "outcome": "disabled-comparison-only",
                "policy": runner.COMPARISON_ONLY_PUBLICATION_POLICY,
                "qualifiedArchivePublished": False,
            },
        )
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
        self.assertEqual(arguments.count("-num-threads"), 1)
        self.assertEqual(
            arguments[arguments.index("-num-threads") + 2],
            "1",
        )
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

    def test_publish_binding_requires_exact_canonical_comparison_result(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+22-local-v1"
        protected_relative = Path(
            "dist/releases/aetherlink-1.0.0+21-local-v1"
        )
        protected_identity = "b" * 64
        source = {
            "overlaySha256": "c" * 64,
            "snapshotSha256": "d" * 64,
        }
        builds = [
            {
                "archive": {
                    "members": [
                        {"path": "payload.bin", "sha256": "e" * 64}
                    ],
                    "sha256": "f" * 64,
                },
                "lane": "build-a",
            },
            {
                "archive": {
                    "members": [
                        {"path": "payload.bin", "sha256": "e" * 64}
                    ],
                    "sha256": "f" * 64,
                },
                "lane": "build-b",
            },
        ]
        comparison = {
            "archiveBytesEqual": True,
            "differences": [],
            "memberBytesEqual": True,
        }
        result = runner.empty_result(publish_qualified=False)
        result.update(
            {
                "builds": builds,
                "comparison": comparison,
                "releaseId": release_id,
                "source": source,
                "status": "passed",
            }
        )
        result["protectedArchive"].update(
            {
                "afterIdentitySha256": protected_identity,
                "beforeIdentitySha256": protected_identity,
                "relativePath": protected_relative.as_posix(),
                "unchanged": True,
            }
        )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary) / "root"
            result_root = temporary_root / "dist/reproducibility"
            result_root.mkdir(parents=True)
            with (
                mock.patch.object(runner, "ROOT", temporary_root),
                mock.patch.object(runner, "RESULT_ROOT", result_root),
            ):
                path = runner.canonical_prepublication_result_path(release_id)
                path.write_bytes(runner.canonical_json_bytes(result))
                binding, bound_path, identity = (
                    runner.load_matching_prepublication_result(
                        release_id,
                        expected_source=source,
                        expected_builds=builds,
                        expected_comparison=comparison,
                        protected_release_relative=protected_relative,
                        protected_archive_identity_sha256=(
                            protected_identity
                        ),
                    )
                )

                self.assertEqual(bound_path, path)
                self.assertEqual(identity, runner.stable_file_identity(path))
                self.assertEqual(
                    binding,
                    {
                        "matched": True,
                        "path": path.relative_to(runner.ROOT).as_posix(),
                        "policy": runner.PREPUBLICATION_BINDING_POLICY,
                        "sha256": identity.sha256,
                        "size": identity.size,
                    },
                )

                mismatches = (
                    (
                        "source",
                        {"overlaySha256": "0" * 64},
                        builds,
                        comparison,
                        protected_identity,
                    ),
                    (
                        "archive-member",
                        source,
                        [
                            {
                                "archive": {
                                    "members": [
                                        {
                                            "path": "payload.bin",
                                            "sha256": "0" * 64,
                                        }
                                    ],
                                    "sha256": "f" * 64,
                                },
                                "lane": "build-a",
                            },
                            builds[1],
                        ],
                        comparison,
                        protected_identity,
                    ),
                    (
                        "comparison",
                        source,
                        builds,
                        {
                            **comparison,
                            "memberBytesEqual": False,
                        },
                        protected_identity,
                    ),
                    (
                        "previous-archive",
                        source,
                        builds,
                        comparison,
                        "0" * 64,
                    ),
                )
                for (
                    label,
                    expected_source,
                    expected_builds,
                    expected_comparison,
                    expected_protected_identity,
                ) in mismatches:
                    with self.subTest(label=label), self.assertRaises(
                        runner.ReproducibilityError
                    ) as caught:
                        runner.load_matching_prepublication_result(
                            release_id,
                            expected_source=expected_source,
                            expected_builds=expected_builds,
                            expected_comparison=expected_comparison,
                            protected_release_relative=protected_relative,
                            protected_archive_identity_sha256=(
                                expected_protected_identity
                            ),
                        )
                    self.assertEqual(
                        caught.exception.phase,
                        "prepublication-binding",
                    )

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

    def test_previous_release_archive_detects_byte_and_inode_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = Path(
                "dist/releases/aetherlink-1.0.0+7-local-v1"
            )
            directory = root / relative
            directory.mkdir(parents=True)
            archive_id = directory.name
            files = (
                f"{archive_id}.zip",
                f"{archive_id}.manifest.json",
                f"{archive_id}.zip.sha256",
            )
            for name in files:
                (directory / name).write_bytes(name.encode("ascii"))
            before = runner.capture_protected_archive(relative, root)
            target = directory / files[0]
            target.write_bytes(b"changed\n")
            after_bytes = runner.capture_protected_archive(relative, root)
            self.assertNotEqual(before, after_bytes)
            replacement = directory / ".replacement"
            replacement.write_bytes(b"changed\n")
            os.replace(replacement, target)
            after_inode = runner.capture_protected_archive(relative, root)
            self.assertNotEqual(after_bytes, after_inode)

    def test_previous_release_path_comes_from_penultimate_ledger_entry(
        self,
    ) -> None:
        previous = builder_module.ReleaseVersion(
            build_number=21,
            marketing_version="1.0.0",
            semantic_version=(1, 0, 0),
        )
        current = builder_module.ReleaseVersion(
            build_number=22,
            marketing_version="1.0.0",
            semantic_version=(1, 0, 0),
        )
        with mock.patch.object(
            runner,
            "load_release_version_ledger",
            return_value=(previous, current),
        ):
            self.assertEqual(
                runner.previous_release_relative(),
                Path("dist/releases/aetherlink-1.0.0+21-local-v1"),
            )

        with (
            mock.patch.object(
                runner,
                "load_release_version_ledger",
                return_value=(current,),
            ),
            self.assertRaises(runner.ReproducibilityError) as caught,
        ):
            runner.previous_release_relative()
        self.assertEqual(caught.exception.phase, "protected-archive")

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

    def test_publication_state_tracks_archive_mutation_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            release_id = "fixture-release"
            qualified_root = base / "qualified" / release_id
            qualified_root.mkdir(parents=True)
            archive_path = qualified_root / f"{release_id}.zip"
            manifest_path = qualified_root / f"{release_id}.manifest.json"
            checksum_path = qualified_root / f"{release_id}.zip.sha256"
            archive_path.write_bytes(b"fixture archive\n")
            manifest_path.write_bytes(b'{"fixture":true}\n')
            checksum_path.write_text(
                f"{hashlib.sha256(archive_path.read_bytes()).hexdigest()}  "
                f"{archive_path.name}\n",
                encoding="ascii",
            )
            evidence = runner.ArchiveEvidence(
                archive_directory=qualified_root,
                archive_path=archive_path,
                manifest_path=manifest_path,
                checksum_path=checksum_path,
                archive_identity=runner.stable_file_identity(archive_path),
                manifest_identity=runner.stable_file_identity(manifest_path),
                checksum_identity=runner.stable_file_identity(checksum_path),
                zip_entry_count=0,
                payload_member_count=0,
                normalizations=(),
                source_sha256="a" * 64,
                member_inventory=(),
            )
            source_snapshot = {
                "algorithm": "fixture-v1",
                "fileCount": 1,
                "files": [],
                "sha256": "a" * 64,
            }
            git_refs = runner.GitRefs("1" * 40, "2" * 40)
            protected_relative = Path(
                "dist/releases/aetherlink-1.0.0+7-local-v1"
            )
            sentinel = ("b" * 64, {"fixture": self.identity()})
            current = mock.Mock()
            real_publisher = builder_module.publish_archive_directory

            def invoke(
                *,
                output_name: str,
                after_publish: str | None = None,
                verify_side_effect: tuple[object, ...] = (None, None),
            ) -> tuple[
                dict[str, object],
                dict[str, object] | None,
                BaseException | None,
                Path,
            ]:
                output_root = base / output_name
                final_directory = output_root / release_id
                publication = runner.empty_result()["publication"]
                details: dict[str, object] | None = None
                caught: BaseException | None = None

                def publish_fixture(
                    *args: object,
                    **kwargs: object,
                ) -> tuple[Path, bool]:
                    published = real_publisher(*args, **kwargs)
                    if after_publish == "oserror":
                        raise OSError("fixture post-mutation cleanup failure")
                    if after_publish == "interrupt":
                        raise KeyboardInterrupt
                    return published

                with (
                    mock.patch.object(runner, "ROOT", base),
                    mock.patch.object(
                        runner,
                        "load_release_version_ledger",
                        return_value=(current,),
                    ),
                    mock.patch.object(
                        runner.archive_builder,
                        "release_id",
                        return_value=release_id,
                    ),
                    mock.patch.object(
                        runner,
                        "capture_git_refs",
                        return_value=git_refs,
                    ),
                    mock.patch.object(
                        runner.archive_builder,
                        "source_snapshot",
                        return_value=source_snapshot,
                    ),
                    mock.patch.object(
                        runner,
                        "capture_protected_archive",
                        return_value=sentinel,
                    ),
                    mock.patch.object(
                        runner.archive_reader,
                        "verify_release_archive",
                        side_effect=verify_side_effect,
                    ),
                    mock.patch.object(
                        runner.archive_builder,
                        "DEFAULT_OUTPUT_ROOT",
                        output_root,
                    ),
                    mock.patch.object(
                        runner.archive_builder,
                        "publish_archive_directory",
                        side_effect=publish_fixture,
                    ),
                    mock.patch.object(
                        runner,
                        "capture_archive",
                        return_value=evidence,
                    ),
                    mock.patch.object(
                        runner,
                        "compare_archives",
                        return_value={"differences": []},
                    ),
                ):
                    try:
                        details = runner.publish_qualified_archive(
                            evidence,
                            source_snapshot,
                            git_refs,
                            protected_relative,
                            sentinel,
                            publication=publication,
                        )
                    except BaseException as error:
                        caught = error
                return publication, details, caught, final_directory

            publication, details, caught, final_directory = invoke(
                output_name="precheck-failure",
                verify_side_effect=(
                    readback_module.ReleaseArchiveVerificationError(
                        "fixture candidate failure"
                    ),
                ),
            )
            self.assertIsInstance(caught, runner.ReproducibilityError)
            self.assertIsNone(details)
            self.assertFalse(final_directory.exists())
            self.assertEqual(
                (
                    publication["attempted"],
                    publication["outcome"],
                    publication["qualifiedArchivePublished"],
                ),
                (True, "failed-before-archive-mutation", False),
            )

            publication, details, caught, final_directory = invoke(
                output_name="successful",
            )
            self.assertIsNone(caught)
            self.assertIsNotNone(details)
            self.assertFalse(details["alreadyMatched"])
            self.assertTrue(final_directory.is_dir())
            self.assertEqual(
                {path.name for path in final_directory.iterdir()},
                {
                    archive_path.name,
                    manifest_path.name,
                    checksum_path.name,
                },
            )
            self.assertEqual(
                (
                    publication["attempted"],
                    publication["outcome"],
                    publication["qualifiedArchivePublished"],
                ),
                (True, "published-verified", True),
            )
            self.assertTrue(publication["independentReadback"])

            publication, details, caught, final_directory = invoke(
                output_name="successful",
            )
            self.assertIsNone(caught)
            self.assertIsNotNone(details)
            self.assertTrue(details["alreadyMatched"])
            self.assertTrue(final_directory.is_dir())
            self.assertEqual(
                (
                    publication["attempted"],
                    publication["outcome"],
                    publication["qualifiedArchivePublished"],
                ),
                (True, "matched-existing-verified", False),
            )

            publication, details, caught, final_directory = invoke(
                output_name="new-postcheck-failure",
                verify_side_effect=(
                    None,
                    readback_module.ReleaseArchiveVerificationError(
                        "fixture readback failure"
                    ),
                ),
            )
            self.assertIsInstance(caught, runner.ReproducibilityError)
            self.assertIsNone(details)
            self.assertTrue(final_directory.is_dir())
            self.assertEqual(
                (
                    publication["attempted"],
                    publication["outcome"],
                    publication["qualifiedArchivePublished"],
                ),
                (True, "published-postcheck-failed", True),
            )
            self.assertFalse(publication["independentReadback"])

            publication, details, caught, final_directory = invoke(
                output_name="successful",
                verify_side_effect=(
                    None,
                    readback_module.ReleaseArchiveVerificationError(
                        "fixture existing readback failure"
                    ),
                ),
            )
            self.assertIsInstance(caught, runner.ReproducibilityError)
            self.assertIsNone(details)
            self.assertTrue(final_directory.is_dir())
            self.assertEqual(
                (
                    publication["attempted"],
                    publication["outcome"],
                    publication["qualifiedArchivePublished"],
                ),
                (True, "matched-existing-postcheck-failed", False),
            )

            for after_publish, expected_error in (
                ("oserror", runner.ReproducibilityError),
                ("interrupt", KeyboardInterrupt),
            ):
                with self.subTest(after_publish=after_publish):
                    publication, details, caught, final_directory = invoke(
                        output_name=f"post-mutation-{after_publish}",
                        after_publish=after_publish,
                    )
                    self.assertIsInstance(caught, expected_error)
                    self.assertIsNone(details)
                    self.assertTrue(final_directory.is_dir())
                    self.assertEqual(
                        (
                            publication["attempted"],
                            publication["outcome"],
                            publication["qualifiedArchivePublished"],
                        ),
                        (
                            True,
                            "archive-publication-call-outcome-uncertain",
                            None,
                        ),
                    )
                    self.assertFalse(publication["independentReadback"])

    def test_execute_resolves_one_release_context_under_the_lock(
        self,
    ) -> None:
        result_path = Path(
            "/fixture/dist/reproducibility/"
            "aetherlink-1.0.0+22-local-v1-two-root-v4-prepublication.json"
        )
        release_context = runner.ReleaseContext(
            release_id="aetherlink-1.0.0+22-local-v1",
            previous_release_relative=Path(
                "dist/releases/aetherlink-1.0.0+21-local-v1"
            ),
        )
        events: list[str] = []

        @contextmanager
        def fake_lock() -> object:
            events.append("lock-enter")
            try:
                yield
            finally:
                events.append("lock-exit")

        with (
            mock.patch.object(runner, "acquire_run_lock", fake_lock),
            mock.patch.object(
                runner,
                "resolve_release_context",
                return_value=release_context,
            ) as context_mock,
            mock.patch.object(
                runner,
                "preflight_fixed_paths",
                side_effect=runner.ReproducibilityError(
                    2,
                    "invocation",
                    "fixture preflight failure",
                ),
            ) as preflight_mock,
            mock.patch.object(
                runner,
                "capture_protected_archive",
            ) as capture_mock,
            mock.patch.object(runner, "write_result") as write_mock,
        ):
            exit_code, result = runner.execute(
                result_path,
                publish_qualified=False,
            )

        self.assertEqual(exit_code, 2, result)
        self.assertEqual(result["failure"]["phase"], "invocation")
        self.assertEqual(events, ["lock-enter", "lock-exit"])
        context_mock.assert_called_once_with()
        preflight_mock.assert_called_once_with(
            result_path,
            publish_qualified=False,
            expected_release_id=release_context.release_id,
            protected_release_relative=(
                release_context.previous_release_relative
            ),
        )
        capture_mock.assert_not_called()
        write_mock.assert_not_called()

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
            prepublication_path = base / "prepublication.json"
            prepublication_path.write_bytes(b"fixture\n")
            prepublication_identity = runner.stable_file_identity(
                prepublication_path
            )
            prepublication_binding = {
                "matched": True,
                "path": "dist/reproducibility/fixture.json",
                "policy": runner.PREPUBLICATION_BINDING_POLICY,
                "sha256": prepublication_identity.sha256,
                "size": prepublication_identity.size,
            }
            events: list[str] = []
            fail_binding = [False]
            fail_publication = [False]
            mutate_prepublication = [False]

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
                if fail_publication[0]:
                    raise runner.ReproducibilityError(
                        8,
                        "publication",
                        "fixture publication failure",
                    )
                if mutate_prepublication[0]:
                    prepublication_path.write_bytes(b"changed\n")
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

            def fake_load_matching(
                *args: object,
                **kwargs: object,
            ) -> tuple[dict[str, object], Path, runner.FileIdentity]:
                if fail_binding[0]:
                    raise runner.ReproducibilityError(
                        8,
                        "prepublication-binding",
                        "fixture binding failure",
                    )
                return (
                    prepublication_binding,
                    prepublication_path,
                    prepublication_identity,
                )

            with (
                mock.patch.object(runner, "WORK_ROOT", work_root),
                mock.patch.object(
                    runner,
                    "capture_protected_archive",
                    side_effect=(sentinel,) * 10,
                ),
                mock.patch.object(runner, "acquire_run_lock", fake_lock),
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value=base.name,
                ),
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
                mock.patch.object(
                    runner,
                    "source_release_id",
                    return_value=base.name,
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
                    side_effect=(evidence,) * 10,
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
                    "load_matching_prepublication_result",
                    side_effect=fake_load_matching,
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
                ) as publish_mock,
            ):
                comparison_code, comparison_result = runner.execute(
                    base / "result/result-prepublication.json",
                    publish_qualified=False,
                )
                self.assertEqual(comparison_code, 0, comparison_result)
                self.assertEqual(
                    comparison_result["publication"],
                    {
                        "attempted": False,
                        "independentReadback": False,
                        "outcome": "disabled-comparison-only",
                        "policy": "comparison-only-no-publication",
                        "qualifiedArchivePublished": False,
                    },
                )
                publish_mock.assert_not_called()
                run_lane_mock.reset_mock()
                events.clear()
                fail_binding[0] = True
                binding_code, binding_result = runner.execute(
                    base / "result/result-binding-failed.json"
                )
                self.assertEqual(binding_code, 8, binding_result)
                self.assertEqual(
                    binding_result["failure"]["phase"],
                    "prepublication-binding",
                )
                self.assertEqual(
                    binding_result["publication"],
                    {
                        "attempted": False,
                        "independentReadback": False,
                        "outcome": "not-reached",
                        "policy": (
                            runner.PUBLISH_QUALIFIED_PUBLICATION_POLICY
                        ),
                        "qualifiedArchivePublished": False,
                    },
                )
                publish_mock.assert_not_called()
                run_lane_mock.reset_mock()
                events.clear()
                fail_binding[0] = False
                fail_publication[0] = True
                failed_code, failed_result = runner.execute(
                    base / "result/result-attempt1-failed.json"
                )
                self.assertEqual(failed_code, 8, failed_result)
                self.assertEqual(
                    failed_result["publication"],
                    {
                        "attempted": True,
                        "independentReadback": None,
                        "outcome": "publication-or-readback-incomplete",
                        "policy": (
                            runner.PUBLISH_QUALIFIED_PUBLICATION_POLICY
                        ),
                        "qualifiedArchivePublished": None,
                    },
                )
                self.assertEqual(
                    failed_result["failure"]["phase"],
                    "publication",
                )
                run_lane_mock.reset_mock()
                events.clear()
                fail_publication[0] = False
                exit_code, result = runner.execute(result_path)
                successful_build_roots = [
                    call.args[0]
                    for call in run_lane_mock.call_args_list
                ]
                successful_events = list(events)

                run_lane_mock.reset_mock()
                events.clear()
                mutate_prepublication[0] = True
                mutation_code, mutation_result = runner.execute(
                    base / "result/result-binding-mutated.json"
                )
                self.assertEqual(mutation_code, 8, mutation_result)
                self.assertEqual(
                    mutation_result["failure"]["phase"],
                    "prepublication-binding",
                )
                self.assertTrue(
                    mutation_result["publication"]["independentReadback"]
                )

            self.assertEqual(exit_code, 0, result)
            build_roots = successful_build_roots
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
            self.assertEqual(
                result["prepublicationBinding"],
                prepublication_binding,
            )
            self.assertTrue(result["publication"]["independentReadback"])
            self.assertLess(
                successful_events.index("publish"),
                successful_events.index("lock-exit"),
            )
            self.assertLess(
                successful_events.index("scratch-cleanup"),
                successful_events.index("lock-exit"),
            )
            self.assertTrue(result["protectedArchive"]["unchanged"])

    def test_protected_or_source_result_path_is_rejected_without_write(
        self,
    ) -> None:
        protected_relative = Path(
            "dist/releases/aetherlink-1.0.0+7-local-v1"
        )
        protected_result = (
            runner.ROOT
            / protected_relative
            / "aetherlink-1.0.0+7-local-v1.manifest.json"
        ).resolve()
        source_result = (runner.ROOT / "release/version-ledger.tsv").resolve()
        with mock.patch.object(
            runner,
            "previous_release_relative",
            return_value=protected_relative,
        ):
            for path in (protected_result, source_result):
                with self.subTest(path=path), self.assertRaisesRegex(
                    runner.ReproducibilityError,
                    "result basename|result path must be",
                ):
                    runner.preflight_fixed_paths(path)

        sentinel = ("b" * 64, {"fixture": self.identity()})
        with (
            mock.patch.object(
                runner,
                "previous_release_relative",
                return_value=protected_relative,
            ),
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

    def test_execute_rejects_cross_mode_result_without_build_or_write(
        self,
    ) -> None:
        sentinel = ("b" * 64, {"fixture": self.identity()})
        canonical_path = runner.default_result_path().resolve()
        with (
            mock.patch.object(
                runner,
                "capture_protected_archive",
                side_effect=(sentinel, sentinel),
            ),
            mock.patch.object(runner, "acquire_run_lock"),
            mock.patch.object(runner, "run_lane") as run_lane_mock,
            mock.patch.object(
                runner,
                "publish_qualified_archive",
            ) as publish_mock,
            mock.patch.object(runner, "write_result") as write_mock,
        ):
            exit_code, result = runner.execute(
                canonical_path,
                publish_qualified=False,
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["failure"]["phase"], "invocation")
        self.assertEqual(
            result["executionMode"],
            runner.COMPARISON_ONLY_MODE,
        )
        self.assertEqual(
            result["publication"]["outcome"],
            "disabled-comparison-only",
        )
        run_lane_mock.assert_not_called()
        publish_mock.assert_not_called()
        write_mock.assert_not_called()

    def test_release_id_change_after_path_validation_blocks_build_and_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            work_root.mkdir(mode=0o700)
            sentinel = ("b" * 64, {"fixture": self.identity()})
            source_snapshot = {
                "algorithm": "fixture-v1",
                "fileCount": 1,
                "files": [],
                "sha256": "a" * 64,
            }

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
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value="fixture-build20",
                ),
                mock.patch.object(runner, "create_swift_lease"),
                mock.patch.object(runner, "cleanup_swift_scratch"),
                mock.patch.object(
                    runner,
                    "capture_git_refs",
                    return_value=runner.GitRefs("1" * 40, "2" * 40),
                ),
                mock.patch.object(
                    runner,
                    "capture_source_overlay",
                    return_value=runner.SourceOverlay((), (), "c" * 64),
                ),
                mock.patch.object(
                    runner.archive_builder,
                    "source_snapshot",
                    return_value=source_snapshot,
                ),
                mock.patch.object(
                    runner,
                    "source_release_id",
                    return_value="fixture-build21",
                ),
                mock.patch.object(
                    runner,
                    "materialize_clone",
                ) as materialize_mock,
                mock.patch.object(runner, "run_lane") as run_lane_mock,
                mock.patch.object(
                    runner,
                    "publish_qualified_archive",
                ) as publish_mock,
                mock.patch.object(runner, "write_result") as write_mock,
            ):
                exit_code, result = runner.execute(base / "result.json")

            self.assertEqual(exit_code, 4)
            self.assertEqual(result["releaseId"], "fixture-build20")
            self.assertEqual(result["failure"]["phase"], "source-capture")
            materialize_mock.assert_not_called()
            run_lane_mock.assert_not_called()
            publish_mock.assert_not_called()
            write_mock.assert_not_called()

    def test_materialized_clone_release_id_mismatch_blocks_build_and_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            work_root.mkdir(mode=0o700)
            sentinel = ("b" * 64, {"fixture": self.identity()})
            source_snapshot = {
                "algorithm": "fixture-v1",
                "fileCount": 1,
                "files": [],
                "sha256": "a" * 64,
            }

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
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value="fixture-build20",
                ),
                mock.patch.object(runner, "create_swift_lease"),
                mock.patch.object(runner, "cleanup_swift_scratch"),
                mock.patch.object(
                    runner,
                    "capture_git_refs",
                    return_value=runner.GitRefs("1" * 40, "2" * 40),
                ),
                mock.patch.object(
                    runner,
                    "capture_source_overlay",
                    return_value=runner.SourceOverlay((), (), "c" * 64),
                ),
                mock.patch.object(
                    runner.archive_builder,
                    "source_snapshot",
                    return_value=source_snapshot,
                ),
                mock.patch.object(
                    runner,
                    "source_release_id",
                    side_effect=("fixture-build20", "fixture-build21"),
                ),
                mock.patch.object(
                    runner,
                    "materialize_clone",
                ) as materialize_mock,
                mock.patch.object(runner, "run_lane") as run_lane_mock,
                mock.patch.object(
                    runner,
                    "publish_qualified_archive",
                ) as publish_mock,
                mock.patch.object(runner, "write_result") as write_mock,
            ):
                exit_code, result = runner.execute(base / "result.json")

            self.assertEqual(exit_code, 4)
            self.assertEqual(result["releaseId"], "fixture-build20")
            self.assertEqual(
                result["failure"]["phase"],
                "source-materialization",
            )
            self.assertEqual(materialize_mock.call_count, 1)
            run_lane_mock.assert_not_called()
            publish_mock.assert_not_called()
            write_mock.assert_not_called()

    def test_lane_archive_release_id_mismatch_blocks_publication_and_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            work_root = base / "work"
            work_root.mkdir(mode=0o700)
            evidence = self.evidence(base / "fixture-build21")
            source_snapshot = {
                "algorithm": "fixture-v1",
                "fileCount": 1,
                "files": [],
                "sha256": "a" * 64,
            }
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
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value="fixture-build20",
                ),
                mock.patch.object(runner, "create_swift_lease"),
                mock.patch.object(runner, "cleanup_swift_scratch"),
                mock.patch.object(
                    runner,
                    "capture_git_refs",
                    return_value=runner.GitRefs("1" * 40, "2" * 40),
                ),
                mock.patch.object(
                    runner,
                    "capture_source_overlay",
                    return_value=runner.SourceOverlay((), (), "c" * 64),
                ),
                mock.patch.object(
                    runner.archive_builder,
                    "source_snapshot",
                    return_value=source_snapshot,
                ),
                mock.patch.object(
                    runner,
                    "source_release_id",
                    return_value="fixture-build20",
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
                ),
                mock.patch.object(
                    runner,
                    "compare_archives",
                ) as compare_mock,
                mock.patch.object(
                    runner,
                    "publish_qualified_archive",
                ) as publish_mock,
                mock.patch.object(runner, "write_result") as write_mock,
            ):
                exit_code, result = runner.execute(base / "result.json")

            self.assertEqual(exit_code, 8)
            self.assertEqual(result["releaseId"], "fixture-build20")
            self.assertEqual(result["failure"]["phase"], "archive-comparison")
            self.assertEqual(len(result["builds"]), 2)
            compare_mock.assert_not_called()
            publish_mock.assert_not_called()
            write_mock.assert_not_called()

    def test_run_lane_reads_release_id_from_materialized_clone(self) -> None:
        clone_root = Path("/fixture/lane/project")
        evidence = self.evidence(Path("/fixture/archive/clone-release"))
        with (
            mock.patch.object(runner, "run_checked"),
            mock.patch.object(
                runner,
                "source_release_id",
                return_value="clone-release",
            ) as release_id_mock,
            mock.patch.object(
                runner,
                "capture_archive",
                return_value=evidence,
            ) as capture_mock,
        ):
            result = runner.run_lane(
                clone_root,
                Path("/fixture/gradle"),
                Path("/fixture/android-sdk"),
                lane_id="build-a",
            )
        self.assertIs(result, evidence)
        release_id_mock.assert_called_once_with(
            clone_root,
            exit_code=6,
            phase="build-a-readback",
        )
        capture_mock.assert_called_once_with(clone_root, "clone-release")

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
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value="fixture-release",
                ),
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
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value="fixture-release",
                ),
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
                result_path = base / "result-prepublication.json"
                exit_code, result = runner.execute(
                    result_path,
                    publish_qualified=False,
                )

            self.assertEqual(exit_code, 130)
            self.assertEqual(result["failure"]["phase"], "interrupted")
            self.assertEqual(cleaned, ["scratch"])
            self.assertEqual(
                result["executionMode"],
                runner.COMPARISON_ONLY_MODE,
            )
            self.assertEqual(
                result["publication"],
                {
                    "attempted": False,
                    "independentReadback": False,
                    "outcome": "disabled-comparison-only",
                    "policy": runner.COMPARISON_ONLY_PUBLICATION_POLICY,
                    "qualifiedArchivePublished": False,
                },
            )
            self.assertEqual(
                json.loads(result_path.read_text(encoding="ascii")),
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
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value=base.name,
                ),
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
                mock.patch.object(
                    runner,
                    "source_release_id",
                    return_value=base.name,
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
