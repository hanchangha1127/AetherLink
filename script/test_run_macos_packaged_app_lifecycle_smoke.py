from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import warnings
import zipfile

from script import run_macos_packaged_app_lifecycle_smoke as smoke


class FakeProcess:
    def __init__(self, *, pid: int = 4242, exit_code: int | None = None):
        self.pid = pid
        self.exit_code = exit_code
        self.signals: list[int] = []

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float | None = None) -> int:
        if self.exit_code is None:
            raise subprocess.TimeoutExpired("fake", timeout)
        return self.exit_code

    def send_signal(self, signal_number: int) -> None:
        self.signals.append(signal_number)
        self.exit_code = -signal_number


class MacOSPackagedAppLifecycleSmokeTests(unittest.TestCase):
    def release_fixture(
        self,
        root: Path,
        *,
        extra_members: list[tuple[zipfile.ZipInfo, bytes]] | None = None,
    ) -> smoke.ReleaseInputs:
        archive_dir = root / smoke.EXPECTED_RELEASE_ID
        archive_dir.mkdir()
        archive_path = archive_dir / f"{smoke.EXPECTED_RELEASE_ID}.zip"
        manifest_path = (
            archive_dir / f"{smoke.EXPECTED_RELEASE_ID}.manifest.json"
        )
        checksum_path = (
            archive_dir / f"{smoke.EXPECTED_RELEASE_ID}.zip.sha256"
        )
        app_members = {
            "macos/AetherLink.app/Contents/Info.plist": (
                b"plist",
                0o644,
            ),
            "macos/AetherLink.app/Contents/MacOS/AetherLink": (
                b"binary",
                0o755,
            ),
        }
        rows = []
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name, (payload, mode) in app_members.items():
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFREG | mode) << 16
                archive.writestr(info, payload)
                rows.append(
                    {
                        "mode": f"{mode:04o}",
                        "path": name,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                    }
                )
            for info, payload in extra_members or []:
                archive.writestr(info, payload)
        manifest = {
            "members": rows,
            "platforms": {"macos": {"uuid": "TEST-UUID"}},
            "release": {
                "buildNumber": smoke.EXPECTED_BUILD_NUMBER,
                "marketingVersion": smoke.EXPECTED_MARKETING_VERSION,
                "releaseId": smoke.EXPECTED_RELEASE_ID,
            },
        }
        manifest_bytes = smoke.canonical_json_bytes(manifest)
        manifest_path.write_bytes(manifest_bytes)
        archive_sha256 = smoke.sha256_file(archive_path)
        checksum_path.write_text(
            f"{archive_sha256}  {archive_path.name}\n",
            encoding="ascii",
        )
        return smoke.ReleaseInputs(
            archive_dir=archive_dir,
            archive_path=archive_path,
            manifest_path=manifest_path,
            checksum_path=checksum_path,
            archive_sha256=archive_sha256,
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            manifest=manifest,
        )

    def test_extract_packaged_app_preserves_exact_regular_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = self.release_fixture(root)

            app = smoke.extract_packaged_app(
                release,
                root / "extracting",
            )

            executable = app / smoke.EXECUTABLE_RELATIVE_PATH
            self.assertEqual(executable.read_bytes(), b"binary")
            self.assertEqual(
                stat.S_IMODE(executable.stat().st_mode),
                0o755,
            )

    def test_extract_rejects_zip_traversal_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info = zipfile.ZipInfo(
                "macos/AetherLink.app/Contents/../../escape"
            )
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            release = self.release_fixture(
                root,
                extra_members=[(info, b"escape")],
            )

            with self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "unsafe ZIP member path",
            ):
                smoke.extract_packaged_app(
                    release,
                    root / "extracting",
                )

    def test_extract_rejects_duplicate_zip_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = zipfile.ZipInfo(
                "macos/AetherLink.app/Contents/Info.plist"
            )
            duplicate.external_attr = (stat.S_IFREG | 0o644) << 16
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                release = self.release_fixture(
                    root,
                    extra_members=[(duplicate, b"duplicate")],
                )

            with self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "duplicate member",
            ):
                smoke.extract_packaged_app(
                    release,
                    root / "extracting",
                )

    def test_extract_rejects_non_octal_manifest_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = self.release_fixture(root)
            release.manifest["members"][0]["mode"] = "0999"

            with self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "invalid identity fields",
            ):
                smoke.extract_packaged_app(
                    release,
                    root / "extracting",
                )

    def test_extract_rejects_symlink_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = self.release_fixture(root)
            with zipfile.ZipFile(release.archive_path, "a") as archive:
                info = zipfile.ZipInfo(
                    "macos/AetherLink.app/Contents/Resources/link"
                )
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, b"/tmp/target")
            release.manifest["members"].append(
                {
                    "mode": "0777",
                    "path": info.filename,
                    "sha256": hashlib.sha256(b"/tmp/target").hexdigest(),
                    "size": len(b"/tmp/target"),
                }
            )

            with self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "not a regular file",
            ):
                smoke.extract_packaged_app(
                    release,
                    root / "extracting",
                )

    def test_load_release_inputs_rejects_wrong_release_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wrong = Path(temporary) / "wrong-release"
            wrong.mkdir()

            with self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "expected release directory",
            ):
                smoke.load_release_inputs(wrong, verify_readback=False)

    def test_load_release_inputs_pins_exact_build6_archive_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = self.release_fixture(Path(temporary))

            with (
                patch.object(
                    smoke,
                    "EXPECTED_MANIFEST_SHA256",
                    release.manifest_sha256,
                ),
                patch.object(smoke, "EXPECTED_ARCHIVE_SHA256", "0" * 64),
                self.assertRaisesRegex(
                    smoke.LifecycleSmokeError,
                    "qualified Build 6 identity",
                ),
            ):
                smoke.load_release_inputs(
                    release.archive_dir,
                    verify_readback=False,
                )

    def test_sandbox_profile_denies_network_and_non_temp_writes(self) -> None:
        root = Path("/private/tmp/aetherlink-lifecycle-fixture")

        profile = smoke.build_sandbox_profile(root)

        self.assertIn("(deny network*)", profile)
        self.assertIn("(deny file-write*)", profile)
        self.assertIn(
            '(allow file-write* (subpath "/private/tmp/aetherlink-lifecycle-fixture"))',
            profile,
        )

    def test_isolated_environment_strips_inherited_product_and_loader_values(
        self,
    ) -> None:
        base = {
            "AETHERLINK_RELAY_SECRET": "must-not-pass",
            "DYLD_INSERT_LIBRARIES": "/tmp/inject.dylib",
            "LANG": "en_US.UTF-8",
        }

        environment = smoke.isolated_environment(
            base,
            home=Path("/tmp/home"),
            temporary=Path("/tmp/temp"),
            identity_file=Path("/tmp/state/identity.json"),
        )

        self.assertNotIn("AETHERLINK_RELAY_SECRET", environment)
        self.assertNotIn("DYLD_INSERT_LIBRARIES", environment)
        self.assertEqual(environment["LANG"], "en_US.UTF-8")
        self.assertEqual(environment["HOME"], "/tmp/home")
        self.assertEqual(environment["CFFIXED_USER_HOME"], "/tmp/home")
        self.assertEqual(environment["CFPREFERENCES_AVOID_DAEMON"], "1")
        self.assertEqual(
            environment["AETHERLINK_RUNTIME_IDENTITY_FILE"],
            "/tmp/state/identity.json",
        )

    def test_preflight_refuses_unisolated_fallback(self) -> None:
        with patch.object(smoke, "SANDBOX_EXEC", Path("/missing/sandbox-exec")):
            with self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "refusing an unisolated lifecycle run",
            ):
                smoke.preflight_sandbox(
                    "(version 1)\n(allow default)",
                    Path("/tmp"),
                )

    def test_readiness_rejects_early_exit(self) -> None:
        process = FakeProcess(exit_code=9)

        with self.assertRaisesRegex(
            smoke.LifecycleSmokeError,
            "exited before readiness",
        ):
            smoke.wait_for_application_readiness(
                process,
                Path("/tmp/AetherLink"),
                timeout_seconds=1,
                query=lambda _: None,
            )

    def test_readiness_rejects_wrong_exact_executable(self) -> None:
        process = FakeProcess()
        status = smoke.ApplicationStatus(
            activation_policy=0,
            bundle_identifier=smoke.EXPECTED_BUNDLE_ID,
            executable_path="/tmp/other",
            finished_launching=True,
        )

        with self.assertRaisesRegex(
            smoke.LifecycleSmokeError,
            "does not match the extracted app",
        ):
            smoke.wait_for_application_readiness(
                process,
                Path("/tmp/AetherLink"),
                timeout_seconds=1,
                query=lambda _: status,
            )

    def test_readiness_timeout_is_bounded(self) -> None:
        process = FakeProcess()

        with self.assertRaisesRegex(
            smoke.LifecycleSmokeError,
            "readiness timed out",
        ):
            smoke.wait_for_application_readiness(
                process,
                Path("/tmp/AetherLink"),
                timeout_seconds=0.001,
                query=lambda _: None,
            )

    def test_termination_refuses_mismatched_app_identity(self) -> None:
        with (
            patch.object(
                smoke,
                "run_jxa",
                return_value={
                    "accepted": False,
                    "found": True,
                    "identityMatched": False,
                },
            ),
            self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "identity no longer matches",
            ),
        ):
            smoke.request_application_termination(
                4242,
                Path("/tmp/AetherLink"),
                force=False,
            )

    def test_exact_cleanup_escalates_only_owned_pid(self) -> None:
        process = FakeProcess()
        executable = Path("/tmp/AetherLink")
        requests: list[tuple[int, Path, bool]] = []

        def request(pid: int, path: Path, *, force: bool) -> bool:
            requests.append((pid, path, force))
            if force:
                process.exit_code = 0
            return True

        smoke.exact_process_cleanup(
            process,
            executable,
            timeout_seconds=0.01,
            request_termination=request,
        )

        self.assertEqual(
            requests,
            [
                (process.pid, executable, False),
                (process.pid, executable, True),
            ],
        )
        self.assertEqual(process.signals, [])

    def test_run_one_lifecycle_success_records_observation_deadline(
        self,
    ) -> None:
        process = FakeProcess()
        status = smoke.ApplicationStatus(
            activation_policy=0,
            bundle_identifier=smoke.EXPECTED_BUNDLE_ID,
            executable_path="/tmp/AetherLink",
            finished_launching=True,
        )

        def request(pid: int, path: Path, *, force: bool) -> bool:
            self.assertEqual(pid, process.pid)
            self.assertEqual(path, Path("/tmp/AetherLink"))
            self.assertFalse(force)
            process.exit_code = 0
            return True

        with tempfile.TemporaryDirectory() as temporary:
            result = smoke.run_one_lifecycle(
                ordinal=1,
                executable=Path("/tmp/AetherLink"),
                profile="profile",
                environment={},
                working_directory=Path(temporary),
                log_directory=Path(temporary),
                readiness_timeout_seconds=1,
                observation_seconds=0.001,
                termination_timeout_seconds=0.01,
                popen_factory=lambda *args, **kwargs: process,
                readiness_waiter=lambda *args, **kwargs: status,
                request_termination=request,
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.minimum_observation_seconds, 0.001)
        self.assertTrue(result.observation_deadline_reached)

    def test_run_one_lifecycle_rejects_termination_refusal(self) -> None:
        process = FakeProcess()
        status = smoke.ApplicationStatus(
            activation_policy=0,
            bundle_identifier=smoke.EXPECTED_BUNDLE_ID,
            executable_path="/tmp/AetherLink",
            finished_launching=True,
        )

        def request(pid: int, path: Path, *, force: bool) -> bool:
            if force:
                process.exit_code = 0
            return force

        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "rejected the exact-PID termination request",
            ),
        ):
            smoke.run_one_lifecycle(
                ordinal=1,
                executable=Path("/tmp/AetherLink"),
                profile="profile",
                environment={},
                working_directory=Path(temporary),
                log_directory=Path(temporary),
                readiness_timeout_seconds=1,
                observation_seconds=0.001,
                termination_timeout_seconds=0.001,
                popen_factory=lambda *args, **kwargs: process,
                readiness_waiter=lambda *args, **kwargs: status,
                request_termination=request,
            )

    def test_run_one_lifecycle_rejects_graceful_timeout(self) -> None:
        process = FakeProcess()
        status = smoke.ApplicationStatus(
            activation_policy=0,
            bundle_identifier=smoke.EXPECTED_BUNDLE_ID,
            executable_path="/tmp/AetherLink",
            finished_launching=True,
        )

        def request(pid: int, path: Path, *, force: bool) -> bool:
            if force:
                process.exit_code = 0
            return True

        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(
                smoke.LifecycleSmokeError,
                "graceful deadline",
            ),
        ):
            smoke.run_one_lifecycle(
                ordinal=1,
                executable=Path("/tmp/AetherLink"),
                profile="profile",
                environment={},
                working_directory=Path(temporary),
                log_directory=Path(temporary),
                readiness_timeout_seconds=1,
                observation_seconds=0.001,
                termination_timeout_seconds=0.001,
                popen_factory=lambda *args, **kwargs: process,
                readiness_waiter=lambda *args, **kwargs: status,
                request_termination=request,
            )

    def test_lifecycle_interrupt_still_cleans_exact_process(self) -> None:
        process = FakeProcess()
        cleanup = Mock()
        executable = Path("/tmp/AetherLink")

        def factory(*args: object, **kwargs: object) -> FakeProcess:
            return process

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(smoke, "exact_process_cleanup", cleanup),
            self.assertRaises(KeyboardInterrupt),
        ):
            root = Path(temporary)
            smoke.run_one_lifecycle(
                ordinal=1,
                executable=executable,
                profile="profile",
                environment={},
                working_directory=root,
                log_directory=root,
                readiness_timeout_seconds=1,
                observation_seconds=1,
                termination_timeout_seconds=1,
                popen_factory=factory,
                readiness_waiter=Mock(side_effect=KeyboardInterrupt),
            )

        cleanup.assert_called_once_with(
            process,
            executable,
            timeout_seconds=1,
            request_termination=smoke.request_application_termination,
        )

    def test_execute_runs_twice_and_writes_bounded_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / "result.json"
            ordinals: list[int] = []

            def fake_run(**kwargs: object) -> smoke.LifecycleRunResult:
                ordinal = int(kwargs["ordinal"])
                ordinals.append(ordinal)
                environment = kwargs["environment"]
                assert isinstance(environment, dict)
                application_support = (
                    Path(environment["HOME"])
                    / "Library/Application Support/AetherLink"
                )
                application_support.mkdir(parents=True, exist_ok=True)
                for name in smoke.EXPECTED_ISOLATED_STATE_FILES:
                    (application_support / name).write_bytes(b"fixture")
                return smoke.LifecycleRunResult(
                    activation_policy=0,
                    exit_code=0,
                    finished_launching=True,
                    minimum_observation_seconds=5.0,
                    observation_deadline_reached=True,
                    ordinal=ordinal,
                    termination_accepted=True,
                )

            with (
                patch.object(
                    smoke,
                    "load_release_inputs",
                    return_value=Mock(
                        archive_sha256=smoke.EXPECTED_ARCHIVE_SHA256,
                        manifest_sha256=smoke.EXPECTED_MANIFEST_SHA256,
                    ),
                ),
                patch.object(
                    smoke,
                    "extract_packaged_app",
                    side_effect=lambda release, destination: (
                        destination.parent / "AetherLink.app"
                    ),
                ),
                patch.object(
                    smoke,
                    "verify_packaged_app",
                    return_value={
                        "buildNumber": smoke.EXPECTED_BUILD_NUMBER,
                        "bundleIdentifier": smoke.EXPECTED_BUNDLE_ID,
                        "executableSha256": "a" * 64,
                        "marketingVersion": smoke.EXPECTED_MARKETING_VERSION,
                        "uuid": "TEST-UUID",
                    },
                ),
                patch.object(smoke, "preflight_sandbox"),
                patch.object(smoke, "run_one_lifecycle", side_effect=fake_run),
            ):
                result = smoke.execute(
                    archive_dir=root / "release",
                    result_path=result_path,
                    readiness_timeout_seconds=15,
                    observation_seconds=5,
                    termination_timeout_seconds=10,
                )

            self.assertEqual(ordinals, [1, 2])
            self.assertTrue(result_path.is_file())
            self.assertEqual(
                result["state"][
                    "expectedApplicationSupportFilesPresentAfterRuns"
                ],
                [True, True],
            )
            self.assertEqual(
                result["state"]["identityFilePresentAfterRuns"],
                [False, False],
            )
            self.assertEqual(
                [run["minimumObservationSeconds"] for run in result["runs"]],
                [5.0, 5.0],
            )

    def test_execute_does_not_publish_partial_second_run_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / "result.json"
            ordinals: list[int] = []

            def fake_run(**kwargs: object) -> smoke.LifecycleRunResult:
                ordinal = int(kwargs["ordinal"])
                ordinals.append(ordinal)
                if ordinal == 2:
                    raise smoke.LifecycleSmokeError("second launch failed")
                environment = kwargs["environment"]
                assert isinstance(environment, dict)
                application_support = (
                    Path(environment["HOME"])
                    / "Library/Application Support/AetherLink"
                )
                application_support.mkdir(parents=True, exist_ok=True)
                for name in smoke.EXPECTED_ISOLATED_STATE_FILES:
                    (application_support / name).write_bytes(b"fixture")
                return smoke.LifecycleRunResult(
                    activation_policy=0,
                    exit_code=0,
                    finished_launching=True,
                    minimum_observation_seconds=5.0,
                    observation_deadline_reached=True,
                    ordinal=ordinal,
                    termination_accepted=True,
                )

            with (
                patch.object(
                    smoke,
                    "load_release_inputs",
                    return_value=Mock(),
                ),
                patch.object(
                    smoke,
                    "extract_packaged_app",
                    side_effect=lambda release, destination: (
                        destination.parent / "AetherLink.app"
                    ),
                ),
                patch.object(smoke, "verify_packaged_app", return_value={}),
                patch.object(smoke, "preflight_sandbox"),
                patch.object(smoke, "run_one_lifecycle", side_effect=fake_run),
                self.assertRaisesRegex(
                    smoke.LifecycleSmokeError,
                    "second launch failed",
                ),
            ):
                smoke.execute(
                    archive_dir=root / "release",
                    result_path=result_path,
                    readiness_timeout_seconds=15,
                    observation_seconds=5,
                    termination_timeout_seconds=10,
                )

            self.assertEqual(ordinals, [1, 2])
            self.assertFalse(result_path.exists())

    def test_write_result_is_canonical_and_replaces_existing_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            path.write_text("old", encoding="utf-8")

            smoke.write_result(path, {"status": "passed", "schemaVersion": 1})

            self.assertEqual(
                path.read_bytes(),
                b'{"schemaVersion":1,"status":"passed"}\n',
            )

    def test_bounded_float_rejects_values_outside_qualification_range(
        self,
    ) -> None:
        with self.assertRaises(Exception):
            smoke.bounded_float("4.999", "observation", 5, 30)
        with self.assertRaises(Exception):
            smoke.bounded_float("31", "observation", 5, 30)
        self.assertEqual(
            smoke.bounded_float("5", "observation", 5, 30),
            5,
        )


if __name__ == "__main__":
    unittest.main()
