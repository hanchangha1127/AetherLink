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
import time
from typing import Callable
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

    @classmethod
    def lane_a_local_dmg_result(
        cls,
        release_id: str,
        evidence: runner.ArchiveEvidence,
    ) -> dict[str, object]:
        return {
            "archiveReadback": {
                "currentSourceCompared": False,
                "mode": runner.LANE_A_LOCAL_DMG_READBACK_MODE,
                "readbackAndExerciseSameSnapshot": True,
                "snapshotFiles": {
                    f"{release_id}.manifest.json": {
                        "sha256": evidence.manifest_identity.sha256,
                        "size": evidence.manifest_identity.size,
                    },
                    f"{release_id}.zip": {
                        "sha256": evidence.archive_identity.sha256,
                        "size": evidence.archive_identity.size,
                    },
                    f"{release_id}.zip.sha256": {
                        "sha256": evidence.checksum_identity.sha256,
                        "size": evidence.checksum_identity.size,
                    },
                },
                "snapshotFilesUnchangedAfterExercise": True,
                "status": "passed",
            },
            "image": {
                "ephemeral": True,
                "filesystem": "HFS+",
                "format": "UDZO",
                "retained": False,
                "verified": True,
            },
            "installation": {
                "adHocAppSealAndVersionVerified": True,
                "applicationsAliasPresent": True,
                "copyTool": "ditto",
                "exactReleaseTreeCopied": True,
                "tree": {
                    "digestAlgorithm": (
                        "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
                    ),
                    "regularFileCount": 1,
                    "sha256": "d" * 64,
                    "totalRegularFileBytes": 1,
                },
            },
            "isolation": {
                "cleanHomeConfigured": True,
                "preexistingBundleApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "launchServices": {
                "distinctProcessIdentifiers": True,
                "exactInstalledBundlePerCycle": True,
                "runs": [
                    {
                        "activationPolicy": 0,
                        "finishedLaunching": True,
                        "newProcessIdentifierDetected": True,
                        "observationDeadlineReached": True,
                        "ordinal": ordinal,
                        "terminationAccepted": True,
                    }
                    for ordinal in (1, 2)
                ],
            },
            "limitations": list(runner.LANE_A_LOCAL_DMG_LIMITATIONS),
            "mount": {
                "detachedBeforeLaunch": True,
                "exactFreshMountpoint": True,
                "nobrowse": True,
                "oneMountedEntity": True,
                "readOnly": True,
                "unmountedVerified": True,
            },
            "release": {
                "archiveSha256": evidence.archive_identity.sha256,
                "manifestSha256": evidence.manifest_identity.sha256,
                "releaseId": release_id,
            },
            "schemaVersion": 2,
            "scope": runner.LANE_A_LOCAL_DMG_SCOPE,
            "state": {
                "databaseCount": 3,
                "emptyRuntimeChatVerified": True,
                "integrityChecks": "passed",
                "regularFileBytesAndModesUnchangedAcrossRelaunch": True,
                "runtimeIdentityFilePresent": True,
                "sqlite": [
                    {
                        "filename": "runtime-chat-events.sqlite",
                        "integrityCheck": "ok",
                        "totalEventCount": 0,
                    },
                    {
                        "filename": "runtime-document-index.sqlite",
                        "integrityCheck": "ok",
                    },
                    {
                        "filename": "runtime-model-pull-approvals.sqlite",
                        "integrityCheck": "ok",
                    },
                ],
                "stableAcrossRelaunch": True,
            },
            "status": "passed",
        }

    @classmethod
    def lane_a_local_dmg_uninstall_reinstall_result(
        cls,
        release_id: str,
        evidence: runner.ArchiveEvidence,
    ) -> dict[str, object]:
        install = cls.lane_a_local_dmg_result(release_id, evidence)
        return {
            "archiveReadback": json.loads(
                json.dumps(install["archiveReadback"])
            ),
            "image": {
                "ephemeral": True,
                "filesystem": "HFS+",
                "format": "UDZO",
                "retained": False,
                "sameImageBytesUsedForBothInstalls": True,
                "verified": True,
            },
            "installation": {
                "adHocAppSealAndVersionVerified": True,
                "applicationsAliasPresent": True,
                "copyTool": "ditto",
                "exactReleaseTreeCopiedEachInstall": True,
                "installCount": 2,
                "origin": "same-ephemeral-local-dmg",
                "reinstallTreeMatchesInitial": True,
                "tree": json.loads(
                    json.dumps(install["installation"]["tree"])  # type: ignore[index]
                ),
            },
            "isolation": {
                "cleanHomeConfigured": True,
                "preexistingBundleApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "launchServices": {
                "distinctProcessIdentifiers": True,
                "exactInstalledBundlePerCycle": True,
                "noExactTemporaryAppRemaining": True,
                "runs": [
                    {
                        "activationPolicy": 0,
                        "finishedLaunching": True,
                        "newProcessIdentifierDetected": True,
                        "observationDeadlineReached": True,
                        "ordinal": ordinal,
                        "terminationAccepted": True,
                    }
                    for ordinal in (1, 2)
                ],
            },
            "limitations": list(
                runner.LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_LIMITATIONS
            ),
            "mount": {
                "cycleCount": 2,
                "detachedBeforeEachLaunch": True,
                "exactFreshMountpointPerInstall": True,
                "nobrowse": True,
                "oneMountedEntityPerInstall": True,
                "readOnly": True,
                "unmountedAfterEachCopy": True,
            },
            "release": json.loads(json.dumps(install["release"])),
            "schemaVersion": 1,
            "scope": runner.LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_SCOPE,
            "state": {
                "applicationSupportPreservedAcrossRemovalAndReinstall": True,
                "databaseCount": 3,
                "emptyRuntimeChatVerified": True,
                "integrityChecks": "passed",
                "regularFileBytesAndModesUnchanged": True,
                "runtimeIdentityFilePresent": True,
                "sqlite": json.loads(json.dumps(install["state"]["sqlite"])),  # type: ignore[index]
                "stableAcrossRemovalAndReinstall": True,
            },
            "status": "passed",
            "uninstall": {
                "appAbsentAfterEachRemoval": True,
                "applicationSupportCleanupPerformed": False,
                "exactTemporaryAppPathOnly": True,
                "exactTemporaryAppStoppedBeforeEachRemoval": True,
                "removalCount": 2,
                "removalMethod": "python-shutil-rmtree",
            },
        }

    @classmethod
    def lane_a_local_dmg_state_recovery_result(
        cls,
        release_id: str,
        evidence: runner.ArchiveEvidence,
    ) -> dict[str, object]:
        same_dmg = cls.lane_a_local_dmg_uninstall_reinstall_result(
            release_id,
            evidence,
        )
        tree = same_dmg["installation"]["tree"]  # type: ignore[index]
        canary_sqlite = {
            "eventJsonSha256": runner.LANE_A_LOCAL_DMG_CANARY[
                "eventJsonSha256"
            ],
            "eventJsonSize": runner.LANE_A_LOCAL_DMG_CANARY[
                "eventJsonSize"
            ],
            "integrityCheck": "ok",
            "totalEventCount": 1,
        }
        return {
            "archiveReadback": json.loads(
                json.dumps(same_dmg["archiveReadback"])
            ),
            "canary": dict(runner.LANE_A_LOCAL_DMG_CANARY),
            "image": json.loads(json.dumps(same_dmg["image"])),
            "installation": {
                **json.loads(json.dumps(same_dmg["installation"])),
                "statePresentBeforeReinstall": True,
                "tree": json.loads(json.dumps(tree)),
            },
            "isolation": json.loads(json.dumps(same_dmg["isolation"])),
            "launchServices": {
                "commandPolicy": (
                    "open-new-fresh-background-exact-app-path-"
                    "captured-recovery-v1"
                ),
                "distinctProcessIdentifiers": True,
                "exactInstalledBundlePerCycle": True,
                "noExactTemporaryAppRemaining": True,
                "runs": [
                    {
                        "activationPolicy": 0,
                        "executablePathMatched": True,
                        "finishedLaunching": True,
                        "minimumObservationSeconds": 5.0,
                        "newProcessIdentifierDetected": True,
                        "observationDeadlineReached": True,
                        "ordinal": ordinal,
                        "terminationAccepted": True,
                    }
                    for ordinal in (1, 2)
                ],
            },
            "limitations": list(
                runner.LANE_A_LOCAL_DMG_STATE_RECOVERY_LIMITATIONS
            ),
            "mount": json.loads(json.dumps(same_dmg["mount"])),
            "release": json.loads(json.dumps(same_dmg["release"])),
            "schemaVersion": 1,
            "scope": runner.LANE_A_LOCAL_DMG_STATE_RECOVERY_SCOPE,
            "stateRecovery": {
                "applicationSupportPreservedAcrossRemovalAndReinstall": True,
                "auxiliarySQLite": [
                    {
                        "filename": "runtime-document-index.sqlite",
                        "integrityCheck": "ok",
                    },
                    {
                        "filename": "runtime-model-pull-approvals.sqlite",
                        "integrityCheck": "ok",
                    },
                ],
                "databaseCount": 3,
                (
                    "installedStateBytesAndModesUnchangedAcrossRemovalAndReinstall"
                ): True,
                "legacyAbsentBeforeReinstallReadback": True,
                "legacyFixturePreservedUnchanged": True,
                "legacyRemovedByHarnessBeforeReinstall": True,
                "migrationObservation": dict(
                    runner.LANE_A_LOCAL_DMG_MIGRATION_OBSERVATION
                ),
                "migrationSQLite": dict(canary_sqlite),
                "runtimeIdentityFilePresent": True,
                "sqliteCanaryUnchangedAcrossRemovalAndReinstall": True,
                "sqliteReadbackObservation": dict(
                    runner.LANE_A_LOCAL_DMG_SQLITE_READBACK_OBSERVATION
                ),
                "sqliteReadbackSQLite": dict(canary_sqlite),
                "totalEventCount": 1,
            },
            "status": "passed",
            "uninstall": json.loads(json.dumps(same_dmg["uninstall"])),
        }

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

    def test_source_inventory_includes_local_dmg_runners_once(self) -> None:
        for runner_relative in (
            "script/run_macos_clean_home_installed_app_smoke.py",
            "script/run_macos_clean_home_installed_state_recovery_smoke.py",
            "script/run_macos_isolated_uninstall_reinstall_smoke.py",
            "script/run_macos_isolated_upgrade_smoke.py",
            "script/run_macos_local_dmg_install_smoke.py",
            "script/run_macos_local_dmg_install_smoke_v2.py",
            "script/run_macos_local_dmg_uninstall_reinstall_smoke.py",
            (
                "script/"
                "run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
            ),
            "script/run_macos_packaged_app_lifecycle_smoke.py",
            "script/run_macos_packaged_app_state_recovery_smoke.py",
        ):
            with self.subTest(runner=runner_relative):
                self.assertEqual(
                    builder_module.SOURCE_REQUIRED_FILES.count(
                        runner_relative
                    ),
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
        self.assertIn("--lane-a-local-dmg-result", result.stdout)

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

    def test_lane_a_local_dmg_result_path_is_release_qualified_and_owned(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+24-local-v1"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            lifecycle_root = base / "lifecycle"
            lifecycle_root.mkdir(mode=0o700)
            valid = lifecycle_root / (
                f"macos-{release_id}-two-root-lane-a-"
                "local-dmg-install-v2-current-source-g6.json"
            )
            with mock.patch.object(
                runner,
                "LIFECYCLE_RESULT_ROOT",
                lifecycle_root,
            ):
                self.assertEqual(
                    runner.validate_lane_a_local_dmg_result_path(
                        valid,
                        expected_release_id=release_id,
                    ),
                    valid,
                )
                invalid = (
                    lifecycle_root
                    / "macos-packaged-app-build-24-local-dmg-install-v2.json",
                    lifecycle_root
                    / (
                        "macos-aetherlink-1.0.0+23-local-v1-two-root-"
                        "lane-a-local-dmg-install-v2-current-source-g6.json"
                    ),
                    lifecycle_root / ".hidden.json",
                    lifecycle_root / "nested" / valid.name,
                    Path("relative.json"),
                )
                for path in invalid:
                    with self.subTest(path=path), self.assertRaises(
                        runner.ReproducibilityError
                    ):
                        runner.validate_lane_a_local_dmg_result_path(
                            path,
                            expected_release_id=release_id,
                        )

                target = lifecycle_root / "target.json"
                target.write_bytes(b"{}\n")
                valid.symlink_to(target)
                with self.assertRaises(runner.ReproducibilityError):
                    runner.validate_lane_a_local_dmg_result_path(
                        valid,
                        expected_release_id=release_id,
                    )
                valid.unlink()
                valid.write_bytes(b"{}\n")
                valid.chmod(0o666)
                with self.assertRaises(runner.ReproducibilityError):
                    runner.validate_lane_a_local_dmg_result_path(
                        valid,
                        expected_release_id=release_id,
                    )

    def test_lane_a_local_dmg_suite_label_derives_three_exact_paths(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+24-local-v1"
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle_root = Path(temporary).resolve() / "lifecycle"
            lifecycle_root.mkdir(mode=0o700)
            with mock.patch.object(
                runner,
                "LIFECYCLE_RESULT_ROOT",
                lifecycle_root,
            ):
                paths = runner.lane_a_local_dmg_suite_paths(
                    "current-source-g6-chain",
                    expected_release_id=release_id,
                )
                self.assertEqual(
                    [path.name for path in paths.ordered()],
                    [
                        (
                            f"macos-{release_id}-two-root-lane-a-"
                            "local-dmg-install-v2-"
                            "current-source-g6-chain.json"
                        ),
                        (
                            f"macos-{release_id}-two-root-lane-a-"
                            "local-dmg-uninstall-reinstall-v1-"
                            "current-source-g6-chain.json"
                        ),
                        (
                            f"macos-{release_id}-two-root-lane-a-"
                            "local-dmg-uninstall-reinstall-state-recovery-v1-"
                            "current-source-g6-chain.json"
                        ),
                    ],
                )
                self.assertEqual(len(set(paths.ordered())), 3)
                for invalid in (
                    "",
                    "Uppercase",
                    "two--hyphens",
                    "trailing-",
                    "a" * 81,
                    True,
                ):
                    with self.subTest(label=invalid), self.assertRaises(
                        runner.ReproducibilityError
                    ):
                        runner.lane_a_local_dmg_suite_paths(
                            invalid,
                            expected_release_id=release_id,
                        )

    def test_main_wires_lane_a_local_dmg_only_in_comparison_mode(
        self,
    ) -> None:
        current = mock.Mock(
            build_number=8,
            marketing_version="1.0.0",
        )
        release_id = "aetherlink-1.0.0+8-local-v1"
        comparison_path = runner.RESULT_ROOT / (
            f"{release_id}-two-root-v4-prepublication.json"
        )
        passed = {
            "builds": [{"archive": {"sha256": "a" * 64}}],
            "comparison": {"memberBytesEqual": True},
        }
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle_root = Path(temporary).resolve() / "lifecycle"
            lifecycle_root.mkdir(mode=0o700)
            lifecycle_path = lifecycle_root / (
                f"macos-{release_id}-two-root-lane-a-"
                "local-dmg-install-v2-current-source-g6.json"
            )
            with (
                mock.patch.object(
                    runner,
                    "load_release_version_ledger",
                    return_value=(current,),
                ),
                mock.patch.object(
                    runner,
                    "LIFECYCLE_RESULT_ROOT",
                    lifecycle_root,
                ),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "runner",
                        "--comparison-only",
                        "--lane-a-local-dmg-result",
                        str(lifecycle_path),
                    ],
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
                lane_a_local_dmg_result_path=lifecycle_path,
            )

            with (
                mock.patch.object(
                    runner,
                    "load_release_version_ledger",
                    return_value=(current,),
                ),
                mock.patch.object(
                    runner,
                    "LIFECYCLE_RESULT_ROOT",
                    lifecycle_root,
                ),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "runner",
                        "--lane-a-local-dmg-result",
                        str(lifecycle_path),
                    ],
                ),
                mock.patch.object(runner, "execute") as rejected_execute,
                mock.patch("builtins.print"),
            ):
                self.assertEqual(runner.main(), 2)
            rejected_execute.assert_not_called()

            target = lifecycle_root / (
                f"macos-{release_id}-two-root-lane-a-"
                "local-dmg-install-v2-alternate.json"
            )
            target.write_bytes(b"{}\n")
            lifecycle_path.symlink_to(target)
            with (
                mock.patch.object(
                    runner,
                    "load_release_version_ledger",
                    return_value=(current,),
                ),
                mock.patch.object(
                    runner,
                    "LIFECYCLE_RESULT_ROOT",
                    lifecycle_root,
                ),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "runner",
                        "--comparison-only",
                        "--lane-a-local-dmg-result",
                        str(lifecycle_path),
                    ],
                ),
                mock.patch.object(runner, "execute") as symlink_execute,
                mock.patch("builtins.print"),
            ):
                self.assertEqual(runner.main(), 2)
            symlink_execute.assert_not_called()

    def test_main_wires_complete_lane_a_local_dmg_suite_only_in_comparison(
        self,
    ) -> None:
        current = mock.Mock(
            build_number=8,
            marketing_version="1.0.0",
        )
        release_id = "aetherlink-1.0.0+8-local-v1"
        comparison_path = runner.RESULT_ROOT / (
            f"{release_id}-two-root-v4-prepublication.json"
        )
        passed = {
            "builds": [{"archive": {"sha256": "a" * 64}}],
            "comparison": {"memberBytesEqual": True},
        }
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle_root = Path(temporary).resolve() / "lifecycle"
            lifecycle_root.mkdir(mode=0o700)
            with (
                mock.patch.object(
                    runner,
                    "load_release_version_ledger",
                    return_value=(current,),
                ),
                mock.patch.object(
                    runner,
                    "LIFECYCLE_RESULT_ROOT",
                    lifecycle_root,
                ),
                mock.patch("builtins.print"),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "runner",
                        "--comparison-only",
                        "--lane-a-local-dmg-suite-label",
                        "current-source-g6-chain",
                    ],
                ),
                mock.patch.object(
                    runner,
                    "execute",
                    return_value=(0, passed),
                ) as execute_mock,
            ):
                self.assertEqual(runner.main(), 0)
            execute_mock.assert_called_once_with(
                comparison_path.resolve(),
                publish_qualified=False,
                lane_a_local_dmg_suite_label="current-source-g6-chain",
            )

            for arguments in (
                [
                    "runner",
                    "--lane-a-local-dmg-suite-label",
                    "current-source-g6-chain",
                ],
                [
                    "runner",
                    "--comparison-only",
                    "--lane-a-local-dmg-result",
                    str(
                        lifecycle_root
                        / (
                            f"macos-{release_id}-two-root-lane-a-"
                            "local-dmg-install-v2-install-only.json"
                        )
                    ),
                    "--lane-a-local-dmg-suite-label",
                    "current-source-g6-chain",
                ],
            ):
                with (
                    mock.patch.object(
                        runner,
                        "load_release_version_ledger",
                        return_value=(current,),
                    ),
                    mock.patch.object(
                        runner,
                        "LIFECYCLE_RESULT_ROOT",
                        lifecycle_root,
                    ),
                    mock.patch.object(sys, "argv", arguments),
                    mock.patch.object(
                        runner,
                        "execute",
                    ) as rejected_execute,
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

    def test_lane_a_local_dmg_result_readback_is_closed_and_exact(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+24-local-v1"
        evidence = self.evidence(Path("/fixture/archive"))
        baseline = self.lane_a_local_dmg_result(release_id, evidence)
        raw = runner.canonical_json_bytes(baseline)
        self.assertEqual(
            runner.validate_lane_a_local_dmg_result_bytes(
                raw,
                expected_release_id=release_id,
                evidence=evidence,
            ),
            baseline,
        )

        mutations: list[dict[str, object]] = []
        schema_bool = json.loads(json.dumps(baseline))
        schema_bool["schemaVersion"] = True
        mutations.append(schema_bool)
        archive_size_bool = json.loads(json.dumps(baseline))
        archive_size_bool["archiveReadback"]["snapshotFiles"][  # type: ignore[index]
            f"{release_id}.zip"
        ]["size"] = True
        mutations.append(archive_size_bool)
        release_hash = json.loads(json.dumps(baseline))
        release_hash["release"]["archiveSha256"] = "e" * 64
        mutations.append(release_hash)
        extra_key = json.loads(json.dumps(baseline))
        extra_key["unexpected"] = True
        mutations.append(extra_key)
        launch_ordinal_bool = json.loads(json.dumps(baseline))
        launch_ordinal_bool["launchServices"]["runs"][0]["ordinal"] = True
        mutations.append(launch_ordinal_bool)
        image_bool_aliases = json.loads(json.dumps(baseline))
        image_bool_aliases["image"].update(
            {
                "ephemeral": 1,
                "retained": 0,
                "verified": 1,
            }
        )
        mutations.append(image_bool_aliases)

        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                runner.ReproducibilityError,
                "lane-A local DMG",
            ):
                runner.validate_lane_a_local_dmg_result_bytes(
                    runner.canonical_json_bytes(mutation),
                    expected_release_id=release_id,
                    evidence=evidence,
                )

        with self.assertRaisesRegex(
            runner.ReproducibilityError,
            "canonical JSON",
        ):
            runner.validate_lane_a_local_dmg_result_bytes(
                json.dumps(baseline).encode("ascii"),
                expected_release_id=release_id,
                evidence=evidence,
            )
        duplicate = b'{"status":"passed",' + raw[1:]
        with self.assertRaisesRegex(
            runner.ReproducibilityError,
            "strict ASCII JSON",
        ):
            runner.validate_lane_a_local_dmg_result_bytes(
                duplicate,
                expected_release_id=release_id,
                evidence=evidence,
            )

    def test_lane_a_local_dmg_followup_results_are_closed_and_cross_bound(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+24-local-v1"
        evidence = self.evidence(Path("/fixture/archive"))
        install = self.lane_a_local_dmg_result(release_id, evidence)
        tree = install["installation"]["tree"]  # type: ignore[index]
        same_dmg = self.lane_a_local_dmg_uninstall_reinstall_result(
            release_id,
            evidence,
        )
        recovery = self.lane_a_local_dmg_state_recovery_result(
            release_id,
            evidence,
        )
        self.assertEqual(
            runner.validate_lane_a_local_dmg_uninstall_reinstall_result_bytes(
                runner.canonical_json_bytes(same_dmg),
                expected_release_id=release_id,
                evidence=evidence,
                expected_tree=tree,
            ),
            same_dmg,
        )
        self.assertEqual(
            runner.validate_lane_a_local_dmg_state_recovery_result_bytes(
                runner.canonical_json_bytes(recovery),
                expected_release_id=release_id,
                evidence=evidence,
                expected_tree=tree,
            ),
            recovery,
        )

        mutations: list[
            tuple[
                dict[str, object],
                Callable[[bytes], dict[str, object]],
            ]
        ] = []
        same_bool = json.loads(json.dumps(same_dmg))
        same_bool["installation"]["installCount"] = True
        mutations.append(
            (
                same_bool,
                lambda raw: (
                    runner.validate_lane_a_local_dmg_uninstall_reinstall_result_bytes(
                        raw,
                        expected_release_id=release_id,
                        evidence=evidence,
                        expected_tree=tree,
                    )
                ),
            )
        )
        same_tree = json.loads(json.dumps(same_dmg))
        same_tree["installation"]["tree"]["sha256"] = "e" * 64
        mutations.append(
            (
                same_tree,
                lambda raw: (
                    runner.validate_lane_a_local_dmg_uninstall_reinstall_result_bytes(
                        raw,
                        expected_release_id=release_id,
                        evidence=evidence,
                        expected_tree=tree,
                    )
                ),
            )
        )
        recovery_bool = json.loads(json.dumps(recovery))
        recovery_bool["stateRecovery"]["totalEventCount"] = True
        mutations.append(
            (
                recovery_bool,
                lambda raw: (
                    runner.validate_lane_a_local_dmg_state_recovery_result_bytes(
                        raw,
                        expected_release_id=release_id,
                        evidence=evidence,
                        expected_tree=tree,
                    )
                ),
            )
        )
        recovery_extra = json.loads(json.dumps(recovery))
        recovery_extra["unexpected"] = True
        mutations.append(
            (
                recovery_extra,
                lambda raw: (
                    runner.validate_lane_a_local_dmg_state_recovery_result_bytes(
                        raw,
                        expected_release_id=release_id,
                        evidence=evidence,
                        expected_tree=tree,
                    )
                ),
            )
        )
        for mutation, validator in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(
                runner.ReproducibilityError
            ):
                validator(runner.canonical_json_bytes(mutation))

        duplicate = (
            b'{"status":"passed",'
            + runner.canonical_json_bytes(recovery)[1:]
        )
        with self.assertRaisesRegex(
            runner.ReproducibilityError,
            "strict ASCII JSON",
        ):
            runner.validate_lane_a_local_dmg_state_recovery_result_bytes(
                duplicate,
                expected_release_id=release_id,
                evidence=evidence,
                expected_tree=tree,
            )

    def test_lane_a_local_dmg_result_publication_is_idempotent_only(
        self,
    ) -> None:
        class FailingFile:
            def __init__(self, descriptor: int, failure: str) -> None:
                self.descriptor = descriptor
                self.failure = failure

            def __enter__(self) -> "FailingFile":
                return self

            def __exit__(self, *args: object) -> None:
                os.close(self.descriptor)

            def write(self, payload: bytes) -> int:
                if self.failure == "write":
                    raise OSError("fixture write failure")
                return len(payload)

            def flush(self) -> None:
                if self.failure == "flush":
                    raise OSError("fixture flush failure")

            def fileno(self) -> int:
                return self.descriptor

        release_id = "aetherlink-1.0.0+24-local-v1"
        evidence = self.evidence(Path("/fixture/archive"))
        result = self.lane_a_local_dmg_result(release_id, evidence)
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle_root = Path(temporary).resolve() / "lifecycle"
            lifecycle_root.mkdir(mode=0o700)
            path = lifecycle_root / (
                f"macos-{release_id}-two-root-lane-a-"
                "local-dmg-install-v2-current-source-g6.json"
            )
            with mock.patch.object(
                runner,
                "LIFECYCLE_RESULT_ROOT",
                lifecycle_root,
            ):
                first = runner.publish_lane_a_local_dmg_result(
                    path,
                    result,
                    expected_release_id=release_id,
                )
                second = runner.publish_lane_a_local_dmg_result(
                    path,
                    result,
                    expected_release_id=release_id,
                )
                self.assertEqual(first, second)
                self.assertEqual(
                    path.read_bytes(),
                    runner.canonical_json_bytes(result),
                )
                path.write_bytes(b"changed\n")
                with self.assertRaisesRegex(
                    runner.ReproducibilityError,
                    "refusing to replace",
                ):
                    runner.publish_lane_a_local_dmg_result(
                        path,
                        result,
                        expected_release_id=release_id,
                    )
                self.assertEqual(path.read_bytes(), b"changed\n")

                creation_failure_path = lifecycle_root / (
                    f"macos-{release_id}-two-root-lane-a-"
                    "local-dmg-install-v2-creation-failure.json"
                )
                with (
                    mock.patch.object(
                        runner.tempfile,
                        "mkstemp",
                        side_effect=OSError("fixture failure"),
                    ),
                    self.assertRaises(
                        runner.ReproducibilityError
                    ) as caught,
                ):
                    runner.publish_lane_a_local_dmg_result(
                        creation_failure_path,
                        result,
                        expected_release_id=release_id,
                    )
                self.assertEqual(caught.exception.exit_code, 10)
                self.assertEqual(
                    caught.exception.phase,
                    runner.LANE_A_LOCAL_DMG_PHASE,
                )

                for failure in ("write", "flush"):
                    failure_path = lifecycle_root / (
                        f"macos-{release_id}-two-root-lane-a-"
                        f"local-dmg-install-v2-{failure}-failure.json"
                    )
                    with (
                        mock.patch.object(
                            runner.os,
                            "fdopen",
                            side_effect=lambda descriptor, mode, value=failure: (
                                FailingFile(descriptor, value)
                            ),
                        ),
                        self.assertRaises(
                            runner.ReproducibilityError
                        ) as caught,
                    ):
                        runner.publish_lane_a_local_dmg_result(
                            failure_path,
                            result,
                            expected_release_id=release_id,
                        )
                    self.assertEqual(caught.exception.exit_code, 10)
                    self.assertEqual(
                        caught.exception.phase,
                        runner.LANE_A_LOCAL_DMG_PHASE,
                    )
                    self.assertFalse(failure_path.exists())

                fsync_failure_path = lifecycle_root / (
                    f"macos-{release_id}-two-root-lane-a-"
                    "local-dmg-install-v2-fsync-failure.json"
                )
                with (
                    mock.patch.object(
                        runner.os,
                        "fsync",
                        side_effect=OSError("fixture fsync failure"),
                    ),
                    self.assertRaises(
                        runner.ReproducibilityError
                    ) as caught,
                ):
                    runner.publish_lane_a_local_dmg_result(
                        fsync_failure_path,
                        result,
                        expected_release_id=release_id,
                    )
                self.assertEqual(caught.exception.exit_code, 10)
                self.assertEqual(
                    caught.exception.phase,
                    runner.LANE_A_LOCAL_DMG_PHASE,
                )
                self.assertFalse(fsync_failure_path.exists())

                directory_failure_path = lifecycle_root / (
                    f"macos-{release_id}-two-root-lane-a-"
                    "local-dmg-install-v2-directory-failure.json"
                )
                runner.publish_lane_a_local_dmg_result(
                    directory_failure_path,
                    result,
                    expected_release_id=release_id,
                )
                with (
                    mock.patch.object(
                        runner.os,
                        "fsync",
                        side_effect=OSError("fixture directory failure"),
                    ),
                    self.assertRaises(
                        runner.ReproducibilityError
                    ) as caught,
                ):
                    runner.publish_lane_a_local_dmg_result(
                        directory_failure_path,
                        result,
                        expected_release_id=release_id,
                    )
                self.assertEqual(caught.exception.exit_code, 10)
                self.assertEqual(
                    caught.exception.phase,
                    runner.LANE_A_LOCAL_DMG_PHASE,
                )

    def test_lane_a_local_dmg_suite_preflights_all_then_publishes_exactly(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+24-local-v1"
        evidence = self.evidence(Path("/fixture/archive"))
        install = self.lane_a_local_dmg_result(release_id, evidence)
        same_dmg = self.lane_a_local_dmg_uninstall_reinstall_result(
            release_id,
            evidence,
        )
        recovery = self.lane_a_local_dmg_state_recovery_result(
            release_id,
            evidence,
        )
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle_root = Path(temporary).resolve() / "lifecycle"
            lifecycle_root.mkdir(mode=0o700)
            with mock.patch.object(
                runner,
                "LIFECYCLE_RESULT_ROOT",
                lifecycle_root,
            ):
                blocked_paths = runner.lane_a_local_dmg_suite_paths(
                    "blocked-suite",
                    expected_release_id=release_id,
                )
                blocked_paths.uninstall_reinstall.write_bytes(b"different\n")
                blocked_suite = runner.LaneALocalDMGSuiteEvidence(
                    paths=blocked_paths,
                    archive=evidence,
                    expected_release_id=release_id,
                    install=install,
                    uninstall_reinstall=same_dmg,
                    state_recovery=recovery,
                )
                with self.assertRaisesRegex(
                    runner.ReproducibilityError,
                    "refusing to replace",
                ):
                    runner.publish_lane_a_local_dmg_suite(blocked_suite)
                self.assertFalse(blocked_paths.install.exists())
                self.assertFalse(blocked_paths.state_recovery.exists())

                recoverable_paths = runner.lane_a_local_dmg_suite_paths(
                    "recoverable-suite",
                    expected_release_id=release_id,
                )
                recoverable_suite = runner.LaneALocalDMGSuiteEvidence(
                    paths=recoverable_paths,
                    archive=evidence,
                    expected_release_id=release_id,
                    install=install,
                    uninstall_reinstall=same_dmg,
                    state_recovery=recovery,
                )
                real_link = os.link
                link_calls = 0

                def fail_second_link(source: object, target: object) -> None:
                    nonlocal link_calls
                    link_calls += 1
                    if link_calls == 2:
                        raise OSError("fixture second-link failure")
                    real_link(source, target)

                with (
                    mock.patch.object(
                        runner.os,
                        "link",
                        side_effect=fail_second_link,
                    ),
                    self.assertRaisesRegex(
                        runner.ReproducibilityError,
                        "cannot publish",
                    ),
                ):
                    runner.publish_lane_a_local_dmg_suite(
                        recoverable_suite
                    )
                self.assertTrue(recoverable_paths.install.is_file())
                self.assertFalse(
                    recoverable_paths.uninstall_reinstall.exists()
                )
                self.assertFalse(recoverable_paths.state_recovery.exists())
                runner.publish_lane_a_local_dmg_suite(recoverable_suite)
                self.assertTrue(
                    all(path.is_file() for path in recoverable_paths.ordered())
                )

                paths = runner.lane_a_local_dmg_suite_paths(
                    "published-suite",
                    expected_release_id=release_id,
                )
                suite = runner.LaneALocalDMGSuiteEvidence(
                    paths=paths,
                    archive=evidence,
                    expected_release_id=release_id,
                    install=install,
                    uninstall_reinstall=same_dmg,
                    state_recovery=recovery,
                )
                runner.publish_lane_a_local_dmg_suite(suite)
                first = [path.read_bytes() for path in paths.ordered()]
                self.assertEqual(
                    first,
                    [
                        runner.canonical_json_bytes(install),
                        runner.canonical_json_bytes(same_dmg),
                        runner.canonical_json_bytes(recovery),
                    ],
                )
                runner.publish_lane_a_local_dmg_suite(suite)
                self.assertEqual(
                    [path.read_bytes() for path in paths.ordered()],
                    first,
                )

    def test_lane_a_local_dmg_exercises_clone_before_publication(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+24-local-v1"
        clone_root = Path("/fixture/clone")
        evidence = self.evidence(Path("/fixture/archive"))
        result_path = Path("/fixture/result.json")
        result = self.lane_a_local_dmg_result(release_id, evidence)
        raw = runner.canonical_json_bytes(result)
        identity = self.identity(raw)
        completed = mock.Mock(returncode=0, stdout=raw, stderr=b"")
        events: list[str] = []

        with (
            mock.patch.object(
                runner,
                "validate_lane_a_local_dmg_result_path",
                side_effect=lambda *args, **kwargs: events.append("path"),
            ),
            mock.patch.object(
                runner,
                "lane_archive_identities",
                side_effect=lambda *args, **kwargs: events.append("archive"),
            ) as archive_mock,
            mock.patch.object(
                runner,
                "stable_file_identity",
                side_effect=lambda *args, **kwargs: (
                    events.append("runner") or identity
                ),
            ),
            mock.patch.object(
                runner.subprocess,
                "run",
                side_effect=lambda *args, **kwargs: (
                    events.append("exercise") or completed
                ),
            ) as subprocess_mock,
            mock.patch.object(
                runner,
                "publish_lane_a_local_dmg_result",
                side_effect=lambda *args, **kwargs: (
                    events.append("publish") or identity
                ),
            ) as publish_mock,
            mock.patch.object(
                runner,
                "stable_lane_a_local_dmg_result_bytes",
                side_effect=lambda *args, **kwargs: (
                    events.append("readback") or (raw, identity)
                ),
            ),
        ):
            observed = runner.run_lane_a_local_dmg_install(
                clone_root=clone_root,
                evidence=evidence,
                expected_release_id=release_id,
                result_path=result_path,
            )

        self.assertEqual(observed, result)
        self.assertEqual(
            events,
            [
                "path",
                "archive",
                "runner",
                "exercise",
                "runner",
                "archive",
                "publish",
                "readback",
                "archive",
            ],
        )
        self.assertEqual(archive_mock.call_count, 3)
        command = subprocess_mock.call_args.args[0]
        self.assertEqual(subprocess_mock.call_args.kwargs["cwd"], clone_root)
        self.assertEqual(command[-1], str(evidence.archive_directory))
        self.assertNotIn(str(result_path), command)
        publish_mock.assert_called_once_with(
            result_path,
            result,
            expected_release_id=release_id,
        )

        invalid = json.loads(json.dumps(result))
        invalid["release"]["archiveSha256"] = "e" * 64
        invalid_raw = runner.canonical_json_bytes(invalid)
        completed.stdout = invalid_raw
        with (
            mock.patch.object(
                runner,
                "validate_lane_a_local_dmg_result_path",
            ),
            mock.patch.object(runner, "lane_archive_identities"),
            mock.patch.object(
                runner,
                "stable_file_identity",
                return_value=identity,
            ),
            mock.patch.object(
                runner.subprocess,
                "run",
                return_value=completed,
            ),
            mock.patch.object(
                runner,
                "publish_lane_a_local_dmg_result",
            ) as rejected_publish,
        ):
            with self.assertRaisesRegex(
                runner.ReproducibilityError,
                "differs from build A",
            ):
                runner.run_lane_a_local_dmg_install(
                    clone_root=clone_root,
                    evidence=evidence,
                    expected_release_id=release_id,
                    result_path=result_path,
                )
        rejected_publish.assert_not_called()

    def test_lane_a_lifecycle_command_enforces_output_and_time_bounds(
        self,
    ) -> None:
        environment = os.environ.copy()
        result = runner.run_bounded_lane_a_lifecycle_command(
            [
                sys.executable,
                "-B",
                "-c",
                (
                    "import os;"
                    "os.write(1,b'out');"
                    "os.write(2,b'err')"
                ),
            ],
            cwd=Path.cwd(),
            environment=environment,
            timeout_seconds=5.0,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"out")
        self.assertEqual(result.stderr, b"err")

        for descriptor, constant in (
            (1, "LANE_A_LIFECYCLE_MAX_STDOUT_BYTES"),
            (2, "LANE_A_LIFECYCLE_MAX_STDERR_BYTES"),
        ):
            with (
                self.subTest(descriptor=descriptor),
                mock.patch.object(runner, constant, 32),
                self.assertRaisesRegex(
                    runner.ReproducibilityError,
                    "hard byte limit",
                ),
            ):
                runner.run_bounded_lane_a_lifecycle_command(
                    [
                        sys.executable,
                        "-B",
                        "-c",
                        (
                            f"import os;os.write({descriptor},"
                            "b'x'*33)"
                        ),
                    ],
                    cwd=Path.cwd(),
                    environment=environment,
                    timeout_seconds=5.0,
                )

        with self.assertRaisesRegex(
            runner.ReproducibilityError,
            "timed out",
        ):
            runner.run_bounded_lane_a_lifecycle_command(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    "import time;time.sleep(5)",
                ],
                cwd=Path.cwd(),
                environment=environment,
                timeout_seconds=0.05,
            )

        with tempfile.TemporaryDirectory() as temporary:
            descendant_pid_path = Path(temporary) / "descendant.pid"
            descendant_program = (
                "import signal,time;"
                "signal.signal(signal.SIGINT,signal.SIG_IGN);"
                "time.sleep(30)"
            )
            parent_program = (
                "import pathlib,subprocess,sys,time;"
                "child=subprocess.Popen([sys.executable,'-B','-c',"
                "sys.argv[2]]);"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid));"
                "time.sleep(30)"
            )
            with (
                mock.patch.object(
                    runner,
                    "LANE_A_LIFECYCLE_INTERRUPT_TIMEOUT_SECONDS",
                    0.2,
                ),
                self.assertRaises(runner.ReproducibilityError),
            ):
                runner.run_bounded_lane_a_lifecycle_command(
                    [
                        sys.executable,
                        "-B",
                        "-c",
                        parent_program,
                        str(descendant_pid_path),
                        descendant_program,
                    ],
                    cwd=Path.cwd(),
                    environment=environment,
                    timeout_seconds=0.5,
                )
            self.assertTrue(descendant_pid_path.is_file())
            descendant_pid = int(
                descendant_pid_path.read_text(encoding="ascii")
            )
            deadline = time.monotonic() + 2.0
            descendant_alive = True
            while time.monotonic() < deadline:
                try:
                    os.kill(descendant_pid, 0)
                except ProcessLookupError:
                    descendant_alive = False
                    break
                time.sleep(0.02)
            if descendant_alive:
                try:
                    os.kill(descendant_pid, 9)
                except ProcessLookupError:
                    descendant_alive = False
            self.assertFalse(
                descendant_alive,
                "SIGINT-ignoring descendant survived bounded cleanup",
            )

    def test_lane_a_lifecycle_exercise_binds_runner_source_and_archive(
        self,
    ) -> None:
        evidence = self.evidence(Path("/fixture/archive"))
        payload = b'{"status":"passed"}\n'
        validated = {"status": "passed"}
        validator = mock.Mock(return_value=validated)
        completed = runner.LaneALifecycleProcessResult(
            returncode=0,
            stdout=payload,
            stderr=b"",
        )
        source_snapshot = {"sha256": "f" * 64}
        with (
            mock.patch.object(
                runner,
                "lane_archive_identities",
            ) as archive_mock,
            mock.patch.object(
                runner,
                "require_lane_a_clone_source_snapshot",
            ) as source_mock,
            mock.patch.object(
                runner,
                "stable_file_identity",
                side_effect=(self.identity(), self.identity()),
            ),
            mock.patch.object(
                runner,
                "run_bounded_lane_a_lifecycle_command",
                return_value=completed,
            ) as subprocess_mock,
        ):
            observed = runner.run_lane_a_lifecycle_exercise(
                clone_root=Path("/fixture/clone"),
                evidence=evidence,
                runner_relative=runner.LANE_A_LOCAL_DMG_RUNNER,
                module_name="run_macos_local_dmg_install_smoke_v2",
                expected_source_snapshot=source_snapshot,
                validator=validator,
            )
        self.assertIs(observed, validated)
        self.assertEqual(archive_mock.call_count, 2)
        self.assertEqual(source_mock.call_count, 2)
        validator.assert_called_once_with(payload)
        invocation = subprocess_mock.call_args.args[0]
        self.assertIn("run_macos_local_dmg_install_smoke_v2", invocation[3])

        with (
            mock.patch.object(runner, "lane_archive_identities"),
            mock.patch.object(
                runner,
                "require_lane_a_clone_source_snapshot",
            ),
            mock.patch.object(
                runner,
                "stable_file_identity",
                side_effect=(
                    self.identity(),
                    self.identity(b"changed\n"),
                ),
            ),
            mock.patch.object(
                runner,
                "run_bounded_lane_a_lifecycle_command",
                return_value=completed,
            ),
            self.assertRaisesRegex(
                runner.ReproducibilityError,
                "runner changed",
            ),
        ):
            runner.run_lane_a_lifecycle_exercise(
                clone_root=Path("/fixture/clone"),
                evidence=evidence,
                runner_relative=runner.LANE_A_LOCAL_DMG_RUNNER,
                module_name="run_macos_local_dmg_install_smoke_v2",
                expected_source_snapshot=source_snapshot,
                validator=validator,
            )

    def test_lane_a_lifecycle_failures_stop_before_validation(
        self,
    ) -> None:
        evidence = self.evidence(Path("/fixture/archive"))
        identity = self.identity()
        validator = mock.Mock()
        source_snapshot = {"sha256": "f" * 64}
        completed = runner.LaneALifecycleProcessResult(
            returncode=1,
            stdout=b"",
            stderr=b"fixture",
        )
        with (
            mock.patch.object(runner, "lane_archive_identities"),
            mock.patch.object(
                runner,
                "require_lane_a_clone_source_snapshot",
            ),
            mock.patch.object(
                runner,
                "stable_file_identity",
                side_effect=(identity, identity),
            ),
            mock.patch.object(
                runner,
                "run_bounded_lane_a_lifecycle_command",
                return_value=completed,
            ),
            self.assertRaisesRegex(
                runner.ReproducibilityError,
                "nonzero status",
            ),
        ):
            runner.run_lane_a_lifecycle_exercise(
                clone_root=Path("/fixture/clone"),
                evidence=evidence,
                runner_relative=runner.LANE_A_LOCAL_DMG_RUNNER,
                module_name="run_macos_local_dmg_install_smoke_v2",
                expected_source_snapshot=source_snapshot,
                validator=validator,
            )
        validator.assert_not_called()

        for failure_name, patches in (
            (
                "timeout",
                {
                    "bounded": runner.lane_a_local_dmg_error(
                        "lane-A lifecycle exercise timed out"
                    ),
                    "source": None,
                    "archive": None,
                },
            ),
            (
                "source",
                {
                    "bounded": None,
                    "source": runner.lane_a_local_dmg_error(
                        "materialized lane-A source snapshot changed"
                    ),
                    "archive": None,
                },
            ),
            (
                "archive",
                {
                    "bounded": None,
                    "source": None,
                    "archive": runner.lane_a_local_dmg_error(
                        "lane-A archive input changed"
                    ),
                },
            ),
        ):
            validator.reset_mock()
            archive_side_effect = (
                (None, patches["archive"])
                if failure_name == "archive"
                else None
            )
            source_side_effect = patches["source"]
            bounded_side_effect = patches["bounded"]
            with (
                self.subTest(failure=failure_name),
                mock.patch.object(
                    runner,
                    "lane_archive_identities",
                    side_effect=archive_side_effect,
                ),
                mock.patch.object(
                    runner,
                    "require_lane_a_clone_source_snapshot",
                    side_effect=source_side_effect,
                ),
                mock.patch.object(
                    runner,
                    "stable_file_identity",
                    side_effect=(identity, identity),
                ),
                mock.patch.object(
                    runner,
                    "run_bounded_lane_a_lifecycle_command",
                    side_effect=bounded_side_effect,
                    return_value=runner.LaneALifecycleProcessResult(
                        returncode=0,
                        stdout=b"{}\n",
                        stderr=b"",
                    ),
                ),
                self.assertRaises(runner.ReproducibilityError),
            ):
                runner.run_lane_a_lifecycle_exercise(
                    clone_root=Path("/fixture/clone"),
                    evidence=evidence,
                    runner_relative=runner.LANE_A_LOCAL_DMG_RUNNER,
                    module_name="run_macos_local_dmg_install_smoke_v2",
                    expected_source_snapshot=source_snapshot,
                    validator=validator,
                )
            validator.assert_not_called()

    def test_lane_a_local_dmg_suite_runs_install_same_dmg_then_recovery(
        self,
    ) -> None:
        release_id = "aetherlink-1.0.0+24-local-v1"
        evidence = self.evidence(Path("/fixture/archive"))
        install = self.lane_a_local_dmg_result(release_id, evidence)
        same_dmg = self.lane_a_local_dmg_uninstall_reinstall_result(
            release_id,
            evidence,
        )
        recovery = self.lane_a_local_dmg_state_recovery_result(
            release_id,
            evidence,
        )
        outputs = {
            runner.LANE_A_LOCAL_DMG_RUNNER: install,
            runner.LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER: same_dmg,
            runner.LANE_A_LOCAL_DMG_STATE_RECOVERY_RUNNER: recovery,
        }
        events: list[Path] = []

        def exercise(**keywords: object) -> dict[str, object]:
            relative = Path(keywords["runner_relative"])
            events.append(relative)
            output = outputs[relative]
            validator = keywords["validator"]
            return validator(runner.canonical_json_bytes(output))

        with tempfile.TemporaryDirectory() as temporary:
            lifecycle_root = Path(temporary).resolve() / "lifecycle"
            lifecycle_root.mkdir(mode=0o700)
            with (
                mock.patch.object(
                    runner,
                    "LIFECYCLE_RESULT_ROOT",
                    lifecycle_root,
                ),
                mock.patch.object(
                    runner,
                    "run_lane_a_lifecycle_exercise",
                    side_effect=exercise,
                ),
                mock.patch.object(runner, "lane_archive_identities"),
                mock.patch.object(
                    runner,
                    "require_lane_a_clone_source_snapshot",
                ),
            ):
                suite = runner.run_lane_a_local_dmg_suite(
                    clone_root=Path("/fixture/clone"),
                    evidence=evidence,
                    expected_release_id=release_id,
                    expected_source_snapshot={"sha256": "f" * 64},
                    label="ordered-suite",
                )
        self.assertEqual(
            events,
            [
                runner.LANE_A_LOCAL_DMG_RUNNER,
                runner.LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER,
                runner.LANE_A_LOCAL_DMG_STATE_RECOVERY_RUNNER,
            ],
        )
        self.assertEqual(suite.install, install)
        self.assertEqual(suite.uninstall_reinstall, same_dmg)
        self.assertEqual(suite.state_recovery, recovery)

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

            local_dmg_mock = mock.Mock(
                side_effect=lambda *args, **kwargs: events.append(
                    "lane-a-local-dmg"
                )
            )
            local_dmg_suite_mock = mock.Mock(
                side_effect=lambda *args, **kwargs: (
                    events.append("lane-a-local-dmg-suite")
                    or mock.sentinel.lane_a_local_dmg_suite
                )
            )
            local_dmg_suite_publish_mock = mock.Mock(
                side_effect=lambda *args, **kwargs: events.append(
                    "lane-a-local-dmg-suite-publish"
                )
            )
            with (
                mock.patch.object(runner, "WORK_ROOT", work_root),
                mock.patch.object(
                    runner,
                    "capture_protected_archive",
                    side_effect=(sentinel,) * 20,
                ),
                mock.patch.object(runner, "acquire_run_lock", fake_lock),
                mock.patch.object(
                    runner,
                    "preflight_fixed_paths",
                    return_value=base.name,
                ),
                mock.patch.object(
                    runner,
                    "validate_lane_a_local_dmg_result_path",
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
                    side_effect=(evidence,) * 20,
                ) as run_lane_mock,
                mock.patch.object(
                    runner,
                    "compare_archives",
                    side_effect=lambda *args, **kwargs: (
                        events.append("compare")
                        or {
                            "archiveBytesEqual": True,
                            "differences": [],
                            "memberBytesEqual": True,
                            "memberDifferences": [],
                            "memberMetadataEqual": True,
                            "memberSetEqual": True,
                            "normalizations": [],
                        }
                    ),
                ),
                mock.patch.multiple(
                    runner,
                    run_lane_a_local_dmg_install=local_dmg_mock,
                    run_lane_a_local_dmg_suite=local_dmg_suite_mock,
                    publish_lane_a_local_dmg_suite=(
                        local_dmg_suite_publish_mock
                    ),
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
                local_dmg_mock.assert_not_called()

                run_lane_mock.reset_mock()
                events.clear()
                lane_a_result_path = base / "lifecycle/lane-a.json"
                lane_code, lane_result = runner.execute(
                    base / "result/result-lane-a-prepublication.json",
                    publish_qualified=False,
                    lane_a_local_dmg_result_path=lane_a_result_path,
                )
                self.assertEqual(lane_code, 0, lane_result)
                self.assertEqual(lane_result["schemaVersion"], 4)
                self.assertEqual(
                    lane_result["publication"],
                    {
                        "attempted": False,
                        "independentReadback": False,
                        "outcome": "disabled-comparison-only",
                        "policy": "comparison-only-no-publication",
                        "qualifiedArchivePublished": False,
                    },
                )
                local_dmg_mock.assert_called_once()
                local_dmg_call = local_dmg_mock.call_args.kwargs
                self.assertEqual(
                    local_dmg_call["evidence"],
                    evidence,
                )
                self.assertEqual(
                    local_dmg_call["expected_release_id"],
                    base.name,
                )
                self.assertEqual(
                    local_dmg_call["result_path"],
                    lane_a_result_path,
                )
                self.assertIn(
                    local_dmg_call["clone_root"],
                    [
                        call.args[0]
                        for call in run_lane_mock.call_args_list
                    ],
                )
                self.assertEqual(
                    local_dmg_call["clone_root"],
                    run_lane_mock.call_args_list[0].args[0],
                )
                self.assertLess(
                    events.index("compare"),
                    events.index("lane-a-local-dmg"),
                )
                self.assertLess(
                    events.index("lane-a-local-dmg"),
                    events.index("lock-exit"),
                )
                local_dmg_mock.reset_mock()
                local_dmg_suite_mock.reset_mock()
                local_dmg_suite_publish_mock.reset_mock()
                run_lane_mock.reset_mock()
                events.clear()
                suite_code, suite_result = runner.execute(
                    base / "result/result-lane-a-suite-prepublication.json",
                    publish_qualified=False,
                    lane_a_local_dmg_suite_label="current-source-g6-chain",
                )
                self.assertEqual(suite_code, 0, suite_result)
                local_dmg_mock.assert_not_called()
                local_dmg_suite_mock.assert_called_once()
                local_dmg_suite_publish_mock.assert_called_once_with(
                    mock.sentinel.lane_a_local_dmg_suite
                )
                suite_call = local_dmg_suite_mock.call_args.kwargs
                self.assertEqual(
                    suite_call["label"],
                    "current-source-g6-chain",
                )
                self.assertEqual(suite_call["evidence"], evidence)
                self.assertLess(
                    events.index("compare"),
                    events.index("lane-a-local-dmg-suite"),
                )
                self.assertLess(
                    max(
                        index
                        for index, event in enumerate(events)
                        if event == "scratch-cleanup"
                    ),
                    events.index("lane-a-local-dmg-suite-publish"),
                )
                self.assertLess(
                    events.index("lane-a-local-dmg-suite-publish"),
                    events.index("lock-exit"),
                )
                local_dmg_suite_mock.reset_mock()
                local_dmg_suite_publish_mock.reset_mock()
                run_lane_mock.reset_mock()
                events.clear()
                local_dmg_suite_mock.side_effect = (
                    runner.ReproducibilityError(
                        10,
                        runner.LANE_A_LOCAL_DMG_PHASE,
                        "fixture lifecycle suite failure",
                    )
                )
                suite_failure_code, suite_failure_result = runner.execute(
                    base / "result/result-lane-a-suite-failed.json",
                    publish_qualified=False,
                    lane_a_local_dmg_suite_label=(
                        "current-source-g6-chain-failed"
                    ),
                )
                self.assertEqual(
                    suite_failure_code,
                    10,
                    suite_failure_result,
                )
                local_dmg_suite_publish_mock.assert_not_called()
                self.assertIn("scratch-cleanup", events)
                self.assertIn("lock-exit", events)
                local_dmg_suite_mock.side_effect = (
                    lambda *args, **kwargs: (
                        events.append("lane-a-local-dmg-suite")
                        or mock.sentinel.lane_a_local_dmg_suite
                    )
                )
                local_dmg_mock.reset_mock()
                run_lane_mock.reset_mock()
                events.clear()
                local_dmg_mock.side_effect = runner.ReproducibilityError(
                    10,
                    runner.LANE_A_LOCAL_DMG_PHASE,
                    "fixture local DMG failure",
                )
                lane_failure_code, lane_failure_result = runner.execute(
                    base / "result/result-lane-a-failed.json",
                    publish_qualified=False,
                    lane_a_local_dmg_result_path=lane_a_result_path,
                )
                self.assertEqual(lane_failure_code, 10, lane_failure_result)
                self.assertEqual(
                    lane_failure_result["failure"]["phase"],
                    runner.LANE_A_LOCAL_DMG_PHASE,
                )
                self.assertEqual(
                    lane_failure_result["publication"]["outcome"],
                    "disabled-comparison-only",
                )
                self.assertIn("scratch-cleanup", events)
                self.assertIn("lock-exit", events)
                publish_mock.assert_not_called()
                local_dmg_mock.side_effect = lambda *args, **kwargs: (
                    events.append("lane-a-local-dmg")
                )
                local_dmg_mock.reset_mock()
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

    def test_execute_rejects_lane_a_local_dmg_in_publish_mode_before_build(
        self,
    ) -> None:
        release_context = runner.ReleaseContext(
            release_id="aetherlink-1.0.0+24-local-v1",
            previous_release_relative=Path(
                "dist/releases/aetherlink-1.0.0+23-local-v1"
            ),
        )
        with (
            mock.patch.object(runner, "acquire_run_lock"),
            mock.patch.object(
                runner,
                "resolve_release_context",
                return_value=release_context,
            ),
            mock.patch.object(
                runner,
                "preflight_fixed_paths",
            ) as preflight_mock,
            mock.patch.object(runner, "run_lane") as run_lane_mock,
            mock.patch.object(
                runner,
                "publish_qualified_archive",
            ) as publish_mock,
            mock.patch.object(runner, "write_result") as write_mock,
        ):
            exit_code, result = runner.execute(
                Path("/fixture/result.json"),
                publish_qualified=True,
                lane_a_local_dmg_result_path=Path(
                    "/fixture/lane-a-local-dmg.json"
                ),
            )
        self.assertEqual(exit_code, 2, result)
        self.assertEqual(result["failure"]["phase"], "invocation")
        preflight_mock.assert_not_called()
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
