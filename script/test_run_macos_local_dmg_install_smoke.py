#!/usr/bin/env python3
"""Unit tests for the credential-free local DMG install rehearsal."""

from __future__ import annotations

from contextlib import nullcontext
import io
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_local_dmg_install_smoke as smoke


def attach_plist(mountpoint: Path, device: str = "/dev/disk9s1") -> bytes:
    return plistlib.dumps(
        {
            "system-entities": [
                {"dev-entry": "/dev/disk9"},
                {
                    "dev-entry": device,
                    "mount-point": str(mountpoint),
                },
            ]
        }
    )


def info_plist(mountpoint: Path, device: str = "/dev/disk9s1") -> bytes:
    return plistlib.dumps(
        {
            "images": [
                {
                    "system-entities": [
                        {"dev-entry": "/dev/disk9"},
                        {
                            "dev-entry": device,
                            "mount-point": str(mountpoint),
                        },
                    ]
                }
            ]
        }
    )


def launch_record(ordinal: int) -> dict[str, object]:
    return {
        "activationPolicy": 0,
        "executablePathMatched": True,
        "finishedLaunching": True,
        "newProcessIdentifierDetected": True,
        "observationDeadlineReached": True,
        "ordinal": ordinal,
        "processIdentifier": 100 + ordinal,
        "terminationAccepted": True,
    }


def sqlite_evidence() -> tuple[smoke.installed.SQLiteStateEvidence, ...]:
    return tuple(
        smoke.installed.SQLiteStateEvidence(
            filename=filename,
            integrity_check="ok",
            total_event_count=(
                0
                if filename == smoke.installed.CHAT_DATABASE_FILENAME
                else None
            ),
        )
        for filename in smoke.installed.EXPECTED_SQLITE_FILES
    )


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        timeout: bool = False,
        complete_on_communicate: bool = True,
    ) -> None:
        self.pid = 4567
        self.returncode: int | None = (
            None if timeout or not complete_on_communicate else returncode
        )
        self.stdout = None
        self.stderr = None
        self._stdout = stdout
        self._stderr = stderr
        self._timeout = timeout
        self._complete_on_communicate = complete_on_communicate
        self.killed = False
        self.waited = False

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        if self._timeout and not self.killed:
            raise subprocess.TimeoutExpired("test command", timeout)
        if self._complete_on_communicate:
            self.returncode = 0 if self.returncode is None else self.returncode
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        if self.returncode is None:
            self.returncode = -9
        return self.returncode


class CommandContractTests(unittest.TestCase):
    def test_hdiutil_commands_are_exact_and_do_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            staging = root / "stage"
            staging.mkdir()
            image = root / "fresh.dmg"
            mountpoint = root / "mount"
            mountpoint.mkdir()

            self.assertEqual(
                smoke.create_dmg_command(staging, image),
                (
                    "/usr/bin/hdiutil",
                    "create",
                    "-srcfolder",
                    str(staging),
                    "-volname",
                    smoke.VOLUME_NAME,
                    "-fs",
                    "HFS+",
                    "-format",
                    "UDZO",
                    str(image),
                ),
            )
            image.write_bytes(b"test image")
            self.assertEqual(
                smoke.verify_dmg_command(image),
                ("/usr/bin/hdiutil", "verify", str(image)),
            )
            self.assertEqual(
                smoke.attach_dmg_command(image, mountpoint),
                (
                    "/usr/bin/hdiutil",
                    "attach",
                    "-readonly",
                    "-nobrowse",
                    "-noautoopen",
                    "-mountpoint",
                    str(mountpoint),
                    "-plist",
                    str(image),
                ),
            )
            self.assertEqual(
                smoke.detach_dmg_command("/dev/disk9s1"),
                ("/usr/bin/hdiutil", "detach", "/dev/disk9s1"),
            )
            self.assertEqual(
                smoke.detach_mountpoint_command(mountpoint),
                ("/usr/bin/hdiutil", "detach", str(mountpoint)),
            )
            self.assertEqual(
                smoke.info_dmg_command(),
                ("/usr/bin/hdiutil", "info", "-plist"),
            )
            self.assertNotIn("-ov", smoke.create_dmg_command(staging, root / "new.dmg"))

            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.create_dmg_command(staging, image)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.detach_dmg_command("/tmp/device")

    def test_attach_requires_a_fresh_empty_mountpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            image = root / "image.dmg"
            image.write_bytes(b"test")
            mountpoint = root / "mount"
            mountpoint.mkdir()
            (mountpoint / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.attach_dmg_command(image, mountpoint)

    def test_commands_reject_unsafe_paths_and_device_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            staging = root / "stage"
            staging.mkdir()
            image = root / "image.dmg"
            mountpoint = root / "mount"
            mountpoint.mkdir()

            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.create_dmg_command(Path("relative"), image)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.create_dmg_command(staging, Path("relative.dmg"))
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.verify_dmg_command(image)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.attach_dmg_command(image, mountpoint)

            image.write_bytes(b"test")
            staging_link = root / "stage-link"
            staging_link.symlink_to(staging, target_is_directory=True)
            image_link = root / "image-link.dmg"
            image_link.symlink_to(image)
            mount_link = root / "mount-link"
            mount_link.symlink_to(mountpoint, target_is_directory=True)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.create_dmg_command(staging_link, root / "fresh.dmg")
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.verify_dmg_command(image_link)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.attach_dmg_command(image_link, mountpoint)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.attach_dmg_command(image, mount_link)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.detach_mountpoint_command(mount_link)

            for device in (
                "/dev/disk0",
                "/dev/disk01",
                "/dev/disk1s0",
                "/dev/disk1suffix",
                "/dev/disk",
                "/dev/rdisk1",
            ):
                with self.subTest(device=device):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.detach_dmg_command(device)


class PlistParsingTests(unittest.TestCase):
    def test_attach_plist_accepts_one_exact_mounted_entity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            mountpoint = Path(temporary_name) / "mount"
            entity = smoke.parse_attach_plist(
                attach_plist(mountpoint),
                expected_mountpoint=mountpoint,
            )
            self.assertEqual(entity.device, "/dev/disk9s1")

    def test_attach_plist_rejects_noncanonical_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            mountpoint = Path(temporary_name) / "mount"
            malformed_payloads = (
                b"",
                b"not a plist",
                plistlib.dumps([]),
                plistlib.dumps(
                    {"system-entities": [], "unexpected": True}
                ),
                plistlib.dumps(
                    {
                        "system-entities": [
                            {
                                "dev-entry": "/dev/disk9s1",
                                "mount-point": str(mountpoint / "other"),
                            }
                        ]
                    }
                ),
                plistlib.dumps(
                    {
                        "system-entities": [
                            {
                                "dev-entry": "/dev/not-a-disk",
                                "mount-point": str(mountpoint),
                            }
                        ]
                    }
                ),
                plistlib.dumps(
                    {
                        "system-entities": [
                            {
                                "dev-entry": "/dev/disk9s1",
                                "mount-point": str(mountpoint),
                            },
                            {
                                "dev-entry": "/dev/disk10s1",
                                "mount-point": str(mountpoint),
                            },
                        ]
                    }
                ),
                plistlib.dumps(
                    {
                        "system-entities": [
                            {"dev-entry": "/dev/disk9"},
                            {
                                "dev-entry": "/dev/disk9s1",
                                "mount-point": str(mountpoint),
                            },
                            {
                                "dev-entry": "/dev/disk10s1",
                                "mount-point": str(mountpoint / "other"),
                            },
                        ]
                    }
                ),
            )
            for payload in malformed_payloads:
                with self.subTest(payload=payload[:40]):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.parse_attach_plist(
                            payload,
                            expected_mountpoint=mountpoint,
                        )

            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.parse_attach_plist(
                    b"x" * (smoke.MAXIMUM_COMMAND_OUTPUT_BYTES + 1),
                    expected_mountpoint=mountpoint,
                )

    def test_info_plist_requires_zero_or_one_exact_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            mountpoint = Path(temporary_name) / "mount"
            self.assertEqual(
                smoke.parse_info_plist_device(
                    info_plist(mountpoint),
                    expected_mountpoint=mountpoint,
                ),
                smoke.MountedEntity(device="/dev/disk9s1"),
            )
            self.assertIsNone(
                smoke.parse_info_plist_device(
                    plistlib.dumps({"images": []}),
                    expected_mountpoint=mountpoint,
                )
            )
            ambiguous = plistlib.dumps(
                {
                    "images": [
                        {
                            "system-entities": [
                                {
                                    "dev-entry": "/dev/disk9s1",
                                    "mount-point": str(mountpoint),
                                }
                            ]
                        },
                        {
                            "system-entities": [
                                {
                                    "dev-entry": "/dev/disk10s1",
                                    "mount-point": str(mountpoint),
                                }
                            ]
                        },
                    ]
                }
            )
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.parse_info_plist_device(
                    ambiguous,
                    expected_mountpoint=mountpoint,
                )


class StagingTests(unittest.TestCase):
    def test_default_ditto_stager_creates_its_own_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            source = root / "source.app"
            source.mkdir()
            (source / "marker").write_text("release", encoding="utf-8")
            staging = root / "stage"

            staged_app = smoke.stage_dmg_root(source, staging)

            self.assertTrue(staged_app.is_dir())
            self.assertEqual(
                (staged_app / "marker").read_text(encoding="utf-8"),
                "release",
            )
            self.assertEqual(staging.stat().st_mode & 0o777, 0o700)

    def test_stage_contains_only_app_and_absolute_applications_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            source = root / "source.app"
            source.mkdir()
            (source / "marker").write_text("release", encoding="utf-8")
            staging = root / "stage"

            staged_app = smoke.stage_dmg_root(
                source,
                staging,
                installer=lambda source_app, destination: shutil.copytree(
                    source_app, destination
                ),
            )

            self.assertEqual(staged_app.name, smoke.installed.APP_RELATIVE_PATH.name)
            self.assertEqual(
                {entry.name for entry in staging.iterdir()},
                {smoke.installed.APP_RELATIVE_PATH.name, "Applications"},
            )
            self.assertTrue((staging / "Applications").is_symlink())
            self.assertEqual(
                os.readlink(staging / "Applications"),
                "/Applications",
            )
            self.assertEqual(
                (staged_app / "marker").read_text(encoding="utf-8"),
                "release",
            )
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.stage_dmg_root(source, staging, installer=lambda _a, _b: None)


class MountedLayoutTests(unittest.TestCase):
    @staticmethod
    def create_layout(root: Path) -> Path:
        mountpoint = root / "mount"
        mountpoint.mkdir()
        (mountpoint / smoke.installed.APP_RELATIVE_PATH).mkdir()
        (mountpoint / "Applications").symlink_to("/Applications")
        return mountpoint

    def test_mounted_layout_requires_exact_real_app_and_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            mountpoint = self.create_layout(root)
            self.assertEqual(
                smoke.verify_mounted_layout(mountpoint),
                mountpoint / smoke.installed.APP_RELATIVE_PATH,
            )

        invalid_cases = ("wrong-alias", "extra-entry", "symlinked-app")
        for case in invalid_cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as temporary_name:
                    root = Path(temporary_name)
                    mountpoint = self.create_layout(root)
                    if case == "wrong-alias":
                        (mountpoint / "Applications").unlink()
                        (mountpoint / "Applications").symlink_to("/tmp")
                    elif case == "extra-entry":
                        (mountpoint / "unexpected").write_text(
                            "x",
                            encoding="utf-8",
                        )
                    else:
                        app = mountpoint / smoke.installed.APP_RELATIVE_PATH
                        app.rmdir()
                        target = root / "target.app"
                        target.mkdir()
                        app.symlink_to(target, target_is_directory=True)
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.verify_mounted_layout(mountpoint)

        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            real_mount = self.create_layout(root)
            mount_link = root / "mount-link"
            mount_link.symlink_to(real_mount, target_is_directory=True)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.verify_mounted_layout(mount_link)

    def test_copy_requires_release_and_destination_tree_identity(self) -> None:
        version = smoke.recovery.ReleaseVersion(
            build_number=987,
            marketing_version="9.8.7",
            semantic_version=(9, 8, 7),
        )
        expected = smoke.installed.AppTreeEvidence(
            "sha256-test",
            1,
            "a" * 64,
            1,
        )
        other = smoke.installed.AppTreeEvidence(
            "sha256-test",
            1,
            "b" * 64,
            1,
        )
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            mountpoint = self.create_layout(root)
            destination = (
                root / "home/Applications" / smoke.installed.APP_RELATIVE_PATH
            )
            release = smoke.engine.ReleaseInputs(
                archive_dir=root,
                archive_path=root / "release.zip",
                manifest_path=root / "manifest.json",
                checksum_path=root / "checksums.txt",
                archive_sha256="c" * 64,
                manifest_sha256="d" * 64,
                manifest={},
            )

            with (
                patch.object(smoke.recovery, "verify_packaged_app"),
                patch.object(
                    smoke.installed,
                    "app_tree_evidence",
                    side_effect=(expected, expected),
                ),
                patch.object(
                    smoke.installed,
                    "install_app_with_ditto",
                    side_effect=lambda source, target: shutil.copytree(
                        source,
                        target,
                    ),
                ),
            ):
                self.assertEqual(
                    smoke.copy_from_mounted_dmg(
                        mountpoint=mountpoint,
                        installed_app=destination,
                        release=release,
                        version=version,
                        expected_tree=expected,
                    ),
                    expected,
                )

        for trees in ((other,), (expected, other)):
            with self.subTest(trees=trees):
                with tempfile.TemporaryDirectory() as temporary_name:
                    root = Path(temporary_name)
                    mountpoint = self.create_layout(root)
                    destination = (
                        root
                        / "home/Applications"
                        / smoke.installed.APP_RELATIVE_PATH
                    )
                    release = smoke.engine.ReleaseInputs(
                        archive_dir=root,
                        archive_path=root / "release.zip",
                        manifest_path=root / "manifest.json",
                        checksum_path=root / "checksums.txt",
                        archive_sha256="c" * 64,
                        manifest_sha256="d" * 64,
                        manifest={},
                    )
                    with (
                        patch.object(smoke.recovery, "verify_packaged_app"),
                        patch.object(
                            smoke.installed,
                            "app_tree_evidence",
                            side_effect=trees,
                        ),
                        patch.object(
                            smoke.installed,
                            "install_app_with_ditto",
                            side_effect=lambda source, target: shutil.copytree(
                                source,
                                target,
                            ),
                        ),
                    ):
                        with self.assertRaises(smoke.LocalDMGSmokeError):
                            smoke.copy_from_mounted_dmg(
                                mountpoint=mountpoint,
                                installed_app=destination,
                                release=release,
                                version=version,
                                expected_tree=expected,
                            )

    def test_wait_for_unmounted_checks_mount_and_payload_until_clear(self) -> None:
        class Clock:
            def __init__(self) -> None:
                self.now = 0.0

            def monotonic(self) -> float:
                return self.now

            def sleep(self, duration: float) -> None:
                self.now += duration

        with tempfile.TemporaryDirectory() as temporary_name:
            mountpoint = Path(temporary_name) / "mount"
            mountpoint.mkdir()
            clock = Clock()
            smoke.wait_for_unmounted(
                mountpoint,
                timeout_seconds=1.0,
                mount_checker=lambda _path: clock.now < 0.2,
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )
            self.assertGreaterEqual(clock.now, 0.2)

            (mountpoint / "Applications").symlink_to("/Applications")
            clock = Clock()
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.wait_for_unmounted(
                    mountpoint,
                    timeout_seconds=0.2,
                    mount_checker=lambda _path: False,
                    monotonic=clock.monotonic,
                    sleeper=clock.sleep,
                )
            self.assertTrue((mountpoint / "Applications").is_symlink())

            (mountpoint / "Applications").unlink()
            broken_app = mountpoint / smoke.installed.APP_RELATIVE_PATH
            broken_app.symlink_to(
                mountpoint / "missing.app",
                target_is_directory=True,
            )
            clock = Clock()
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.wait_for_unmounted(
                    mountpoint,
                    timeout_seconds=0.2,
                    mount_checker=lambda _path: False,
                    monotonic=clock.monotonic,
                    sleeper=clock.sleep,
                )
            self.assertTrue(broken_app.is_symlink())


class BoundedProcessTests(unittest.TestCase):
    def test_group_kill_is_attempted_before_poll_can_reap_leader(self) -> None:
        class ExitedProcess(FakeProcess):
            def __init__(self, events: list[str]) -> None:
                super().__init__(
                    stdout=b"x"
                    * (smoke.MAXIMUM_COMMAND_OUTPUT_BYTES + 1),
                    returncode=0,
                )
                self.events = events

            def poll(self) -> int | None:
                self.events.append("poll")
                return super().poll()

        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            events: list[str] = []
            process = ExitedProcess(events)

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaises(smoke.LocalDMGSmokeError):
                    smoke.run_bounded_command(
                        (str(tool), "info", "-plist"),
                        popen_factory=lambda *_args, **_kwargs: process,
                        group_killer=lambda _pid, _sig: events.append(
                            "killpg"
                        ),
                    )

            self.assertEqual(events[:2], ["killpg", "poll"])
            self.assertTrue(process.waited)

    def test_streaming_output_overflow_kills_group_closes_and_reaps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            process_holder: dict[str, subprocess.Popen[bytes]] = {}
            group_signals: list[tuple[int, int]] = []

            def popen_factory(
                _command: list[str],
                **keywords: object,
            ) -> subprocess.Popen[bytes]:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import os,time\n"
                            "chunk=b'x'*8192\n"
                            "for _ in range(9): os.write(1,chunk)\n"
                            "time.sleep(5)\n"
                        ),
                    ],
                    **keywords,
                )
                process_holder["process"] = process
                return process

            def kill_group(pid: int, sig: int) -> None:
                group_signals.append((pid, sig))
                os.killpg(pid, sig)

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaisesRegex(
                    smoke.LocalDMGSmokeError,
                    r"^local DMG command did not complete safely$",
                ):
                    smoke.run_bounded_command(
                        (str(tool), "info", "-plist"),
                        popen_factory=popen_factory,
                        group_killer=kill_group,
                    )

            process = process_holder["process"]
            self.assertEqual(
                group_signals,
                [(process.pid, smoke.signal.SIGKILL)],
            )
            self.assertIsNotNone(process.returncode)
            self.assertTrue(process.stdout is not None and process.stdout.closed)
            self.assertTrue(process.stderr is not None and process.stderr.closed)

    def test_streaming_timeout_kills_group_closes_and_reaps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            process_holder: dict[str, subprocess.Popen[bytes]] = {}
            group_signals: list[tuple[int, int]] = []

            def popen_factory(
                _command: list[str],
                **keywords: object,
            ) -> subprocess.Popen[bytes]:
                process = subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    **keywords,
                )
                process_holder["process"] = process
                return process

            def kill_group(pid: int, sig: int) -> None:
                group_signals.append((pid, sig))
                os.killpg(pid, sig)

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaises(smoke.LocalDMGSmokeError):
                    smoke.run_bounded_command(
                        (str(tool), "info", "-plist"),
                        timeout_seconds=0.05,
                        popen_factory=popen_factory,
                        group_killer=kill_group,
                    )

            process = process_holder["process"]
            self.assertEqual(
                group_signals,
                [(process.pid, smoke.signal.SIGKILL)],
            )
            self.assertIsNotNone(process.returncode)
            self.assertTrue(process.stdout is not None and process.stdout.closed)
            self.assertTrue(process.stderr is not None and process.stderr.closed)

    def test_timeout_kills_group_after_leader_exits_with_live_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            process_holder: dict[str, subprocess.Popen[bytes]] = {}
            group_signals: list[tuple[int, int]] = []

            def popen_factory(
                _command: list[str],
                **keywords: object,
            ) -> subprocess.Popen[bytes]:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import subprocess,sys\n"
                            "subprocess.Popen([sys.executable,'-c',"
                            "'import time; time.sleep(5)'])\n"
                        ),
                    ],
                    **keywords,
                )
                process_holder["process"] = process
                return process

            def kill_group(pid: int, sig: int) -> None:
                group_signals.append((pid, sig))
                os.killpg(pid, sig)

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaises(smoke.LocalDMGSmokeError):
                    smoke.run_bounded_command(
                        (str(tool), "info", "-plist"),
                        timeout_seconds=0.1,
                        popen_factory=popen_factory,
                        group_killer=kill_group,
                    )

            process = process_holder["process"]
            self.assertEqual(process.returncode, 0)
            self.assertEqual(
                group_signals,
                [(process.pid, smoke.signal.SIGKILL)],
            )
            self.assertTrue(process.stdout is not None and process.stdout.closed)
            self.assertTrue(process.stderr is not None and process.stderr.closed)

    def test_output_overflow_kills_group_and_reaps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            process = FakeProcess(
                stdout=b"x" * (smoke.MAXIMUM_COMMAND_OUTPUT_BYTES + 1),
                complete_on_communicate=False,
            )
            group_signals: list[tuple[int, int]] = []
            popen_keywords: dict[str, object] = {}

            def popen_factory(
                _command: list[str], **keywords: object
            ) -> FakeProcess:
                popen_keywords.update(keywords)
                return process

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaisesRegex(
                    smoke.LocalDMGSmokeError,
                    r"^local DMG command did not complete safely$",
                ):
                    smoke.run_bounded_command(
                        (str(tool), "info", "-plist"),
                        popen_factory=popen_factory,
                        group_killer=lambda pid, sig: group_signals.append(
                            (pid, sig)
                        ),
                    )

            self.assertEqual(
                group_signals,
                [(process.pid, smoke.signal.SIGKILL)],
            )
            self.assertTrue(process.waited)
            self.assertTrue(popen_keywords["start_new_session"])
            self.assertFalse(popen_keywords["text"])

    def test_timeout_kills_group_and_reaps_without_path_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            process = FakeProcess(timeout=True)
            group_signals: list[tuple[int, int]] = []

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaises(smoke.LocalDMGSmokeError) as raised:
                    smoke.run_bounded_command(
                        (str(tool), "verify", "/private/secret/image.dmg"),
                        timeout_seconds=0.01,
                        popen_factory=lambda *_args, **_kwargs: process,
                        group_killer=lambda pid, sig: group_signals.append(
                            (pid, sig)
                        ),
                    )

            self.assertNotIn("/private/secret", str(raised.exception))
            self.assertEqual(
                group_signals,
                [(process.pid, smoke.signal.SIGKILL)],
            )
            self.assertTrue(process.waited)

    def test_group_kill_failure_falls_back_to_process_kill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            process = FakeProcess(timeout=True)

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaises(smoke.LocalDMGSmokeError):
                    smoke.run_bounded_command(
                        (str(tool), "info", "-plist"),
                        timeout_seconds=0.01,
                        popen_factory=lambda *_args, **_kwargs: process,
                        group_killer=lambda _pid, _sig: (_ for _ in ()).throw(
                            OSError("group unavailable")
                        ),
                    )

            self.assertTrue(process.killed)
            self.assertTrue(process.waited)

    def test_keyboard_interrupt_kills_group_and_reaps(self) -> None:
        class InterruptProcess(FakeProcess):
            def communicate(
                self,
                timeout: float | None = None,
            ) -> tuple[bytes, bytes]:
                raise KeyboardInterrupt()

        with tempfile.TemporaryDirectory() as temporary_name:
            tool = Path(temporary_name) / "hdiutil"
            tool.write_bytes(b"#!/bin/sh\n")
            tool.chmod(0o700)
            process = InterruptProcess(complete_on_communicate=False)
            group_signals: list[tuple[int, int]] = []

            with patch.object(smoke, "HDIUTIL", tool):
                with self.assertRaises(KeyboardInterrupt):
                    smoke.run_bounded_command(
                        (str(tool), "info", "-plist"),
                        popen_factory=lambda *_args, **_kwargs: process,
                        group_killer=lambda pid, sig: group_signals.append(
                            (pid, sig)
                        ),
                    )

            self.assertEqual(
                group_signals,
                [(process.pid, smoke.signal.SIGKILL)],
            )
            self.assertTrue(process.waited)


class DetachFinallyTests(unittest.TestCase):
    def test_copy_baseexception_detaches_exact_device_before_unmount_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            image = root / "image.dmg"
            image.write_bytes(b"test")
            mountpoint = root / "mount"
            mountpoint.mkdir()
            events: list[str] = []

            def command_runner(
                command: tuple[str, ...],
            ) -> smoke.CommandResult:
                if command[1] == "attach":
                    events.append("attach")
                    return smoke.CommandResult(
                        stdout=attach_plist(mountpoint),
                        stderr=b"",
                    )
                if command[1] == "detach":
                    events.append(f"detach:{command[-1]}")
                    return smoke.CommandResult(stdout=b"", stderr=b"")
                self.fail(f"unexpected command: {command}")

            def copier() -> smoke.installed.AppTreeEvidence:
                events.append("copy")
                raise KeyboardInterrupt()

            with self.assertRaises(KeyboardInterrupt):
                smoke.attach_copy_detach(
                    dmg_path=image,
                    mountpoint=mountpoint,
                    copier=copier,
                    command_runner=command_runner,
                    unmount_waiter=lambda _mount: events.append("unmounted"),
                )
            self.assertEqual(
                events,
                ["attach", "copy", "detach:/dev/disk9s1", "unmounted"],
            )

    def test_parse_failure_recovers_exact_device_and_detaches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            image = root / "image.dmg"
            image.write_bytes(b"test")
            mountpoint = root / "mount"
            mountpoint.mkdir()
            events: list[str] = []

            def command_runner(
                command: tuple[str, ...],
            ) -> smoke.CommandResult:
                operation = command[1]
                if operation == "attach":
                    events.append("attach")
                    return smoke.CommandResult(stdout=b"invalid", stderr=b"")
                if operation == "info":
                    events.append("info")
                    return smoke.CommandResult(
                        stdout=info_plist(mountpoint),
                        stderr=b"",
                    )
                if operation == "detach":
                    events.append(f"detach:{command[-1]}")
                    return smoke.CommandResult(stdout=b"", stderr=b"")
                self.fail(f"unexpected command: {command}")

            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.attach_copy_detach(
                    dmg_path=image,
                    mountpoint=mountpoint,
                    copier=lambda: self.fail("copy must not run"),
                    command_runner=command_runner,
                    unmount_waiter=lambda _mount: events.append("unmounted"),
                )
            self.assertEqual(
                events,
                ["attach", "info", "detach:/dev/disk9s1", "unmounted"],
            )

    def test_info_failure_falls_back_to_exact_mountpoint_detach(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            image = root / "image.dmg"
            image.write_bytes(b"test")
            mountpoint = root / "mount"
            mountpoint.mkdir()
            events: list[str] = []

            def command_runner(
                command: tuple[str, ...],
            ) -> smoke.CommandResult:
                operation = command[1]
                if operation == "attach":
                    events.append("attach")
                    return smoke.CommandResult(stdout=b"invalid", stderr=b"")
                if operation == "info":
                    events.append("info-failed")
                    raise smoke.LocalDMGSmokeError("info failed")
                if operation == "detach":
                    events.append(f"detach:{command[-1]}")
                    return smoke.CommandResult(stdout=b"", stderr=b"")
                self.fail(f"unexpected command: {command}")

            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.attach_copy_detach(
                    dmg_path=image,
                    mountpoint=mountpoint,
                    copier=lambda: self.fail("copy must not run"),
                    command_runner=command_runner,
                    unmount_waiter=lambda _mount: events.append("unmounted"),
                )
            self.assertEqual(
                events,
                [
                    "attach",
                    "info-failed",
                    f"detach:{mountpoint}",
                    "unmounted",
                ],
            )

    def test_detach_failure_prevents_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            image = root / "image.dmg"
            image.write_bytes(b"test")
            mountpoint = root / "mount"
            mountpoint.mkdir()
            tree = smoke.installed.AppTreeEvidence("sha256-test", 1, "a" * 64, 1)

            def command_runner(
                command: tuple[str, ...],
            ) -> smoke.CommandResult:
                if command[1] == "attach":
                    return smoke.CommandResult(
                        stdout=attach_plist(mountpoint),
                        stderr=b"",
                    )
                raise RuntimeError("detach failed")

            with self.assertRaisesRegex(
                smoke.LocalDMGSmokeError,
                r"^local DMG cleanup failed$",
            ):
                smoke.attach_copy_detach(
                    dmg_path=image,
                    mountpoint=mountpoint,
                    copier=lambda: tree,
                    command_runner=command_runner,
                    unmount_waiter=lambda _mount: None,
                )


class ExecuteOrchestrationTests(unittest.TestCase):
    def exercise(self, *, detach_failure: bool) -> tuple[list[str], bool]:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            archive_dir = root / "archive"
            archive_dir.mkdir()
            result_path = root / "result.json"
            version = smoke.recovery.ReleaseVersion(
                build_number=987,
                marketing_version="9.8.7",
                semantic_version=(9, 8, 7),
            )
            release = smoke.engine.ReleaseInputs(
                archive_dir=archive_dir,
                archive_path=archive_dir / "release.zip",
                manifest_path=archive_dir / "manifest.json",
                checksum_path=archive_dir / "checksums.txt",
                archive_sha256="a" * 64,
                manifest_sha256="b" * 64,
                manifest={},
            )
            tree = smoke.installed.AppTreeEvidence(
                "sha256-test",
                1,
                "c" * 64,
                1,
            )
            events: list[str] = []

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
            ) -> smoke.CommandResult:
                operation = command[1]
                if operation == "create":
                    events.append("create")
                    Path(command[-1]).write_bytes(b"fixture DMG")
                    return smoke.CommandResult(stdout=b"", stderr=b"")
                if operation == "verify":
                    events.append("verify")
                    return smoke.CommandResult(stdout=b"", stderr=b"")
                if operation == "attach":
                    events.append("attach")
                    mountpoint = Path(command[command.index("-mountpoint") + 1])
                    return smoke.CommandResult(
                        stdout=attach_plist(mountpoint),
                        stderr=b"",
                    )
                if operation == "detach":
                    events.append("detach")
                    if detach_failure:
                        raise smoke.LocalDMGSmokeError("detach failed")
                    return smoke.CommandResult(stdout=b"", stderr=b"")
                self.fail(f"unexpected command: {command}")

            def copy_from_dmg(**_keywords: object) -> smoke.installed.AppTreeEvidence:
                events.append("copy")
                return tree

            def launch_cycle(**keywords: object) -> tuple[int, dict[str, object]]:
                ordinal = int(keywords["ordinal"])
                events.append(f"launch{ordinal}")
                return 100 + ordinal, launch_record(ordinal)

            def publish(_path: Path, _result: dict[str, object]) -> None:
                events.append("publish")

            with (
                patch.object(smoke, "current_release", return_value=version),
                patch.object(smoke, "release_id_for", return_value="build-987"),
                patch.object(
                    smoke.recovery,
                    "load_release_inputs",
                    return_value=release,
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
                patch.object(smoke, "stage_dmg_root", side_effect=stage),
                patch.object(
                    smoke,
                    "run_bounded_command",
                    side_effect=command_runner,
                ),
                patch.object(
                    smoke,
                    "copy_from_mounted_dmg",
                    side_effect=copy_from_dmg,
                ),
                patch.object(
                    smoke,
                    "wait_for_unmounted",
                    side_effect=lambda _mount: events.append("unmount"),
                ),
                patch.object(
                    smoke.installed,
                    "isolated_launch_environment",
                    return_value={},
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
                    smoke.installed,
                    "assert_preexisting_applications_preserved",
                ),
                patch.object(smoke, "publish_result", side_effect=publish),
            ):
                if detach_failure:
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.execute(
                            archive_dir=archive_dir,
                            result_path=result_path,
                            readiness_timeout_seconds=1.0,
                            observation_seconds=(
                                smoke.engine.MINIMUM_OBSERVATION_SECONDS
                            ),
                            termination_timeout_seconds=1.0,
                        )
                    return events, result_path.exists()
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

    def test_execute_orders_detach_before_both_launches_and_publication(self) -> None:
        events, published_on_disk = self.exercise(detach_failure=False)
        self.assertEqual(
            events,
            [
                "create",
                "verify",
                "attach",
                "copy",
                "detach",
                "unmount",
                "launch1",
                "launch2",
                "publish",
            ],
        )
        self.assertFalse(published_on_disk)

    def test_detach_failure_prevents_launch_and_publication(self) -> None:
        events, published_on_disk = self.exercise(detach_failure=True)
        self.assertEqual(
            events,
            ["create", "verify", "attach", "copy", "detach", "unmount"],
        )
        self.assertFalse(published_on_disk)


class ResultBoundaryTests(unittest.TestCase):
    def release_inputs(self, root: Path) -> smoke.engine.ReleaseInputs:
        return smoke.engine.ReleaseInputs(
            archive_dir=root,
            archive_path=root / "release.zip",
            manifest_path=root / "manifest.json",
            checksum_path=root / "checksums.txt",
            archive_sha256="a" * 64,
            manifest_sha256="b" * 64,
            manifest={},
        )

    def test_default_result_path_tracks_current_build(self) -> None:
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
                "macos-packaged-app-build-987-local-dmg-install-v1.json",
            )

    def test_publish_is_idempotent_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result_path = Path(temporary_name) / "nested" / "result.json"
            result = {"schemaVersion": 1, "status": "passed"}
            smoke.publish_result(result_path, result)
            first_bytes = result_path.read_bytes()
            smoke.publish_result(result_path, result)
            self.assertEqual(result_path.read_bytes(), first_bytes)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.publish_result(result_path, {"status": "different"})
            self.assertEqual(result_path.read_bytes(), first_bytes)

    def test_publish_rejects_symlink_and_handles_concurrent_writers(self) -> None:
        result = {"schemaVersion": 1, "status": "passed"}
        expected = smoke.engine.canonical_json_bytes(result)
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            target = root / "target.json"
            target.write_bytes(b"preserve")
            result_path = root / "result.json"
            result_path.symlink_to(target)
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.publish_result(result_path, result)
            self.assertEqual(target.read_bytes(), b"preserve")

        for concurrent_payload, should_pass in (
            (expected, True),
            (b"different\n", False),
        ):
            with self.subTest(should_pass=should_pass):
                with tempfile.TemporaryDirectory() as temporary_name:
                    result_path = Path(temporary_name) / "result.json"

                    def concurrent_link(source: Path, target: Path) -> None:
                        Path(target).write_bytes(concurrent_payload)
                        raise FileExistsError()

                    context = (
                        self.assertRaises(smoke.LocalDMGSmokeError)
                        if not should_pass
                        else nullcontext()
                    )
                    with patch.object(smoke.os, "link", side_effect=concurrent_link):
                        with context:
                            smoke.publish_result(result_path, result)
                    self.assertEqual(
                        result_path.read_bytes(),
                        concurrent_payload,
                    )

    def test_result_is_path_device_pid_and_dmg_identity_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            runs = (launch_record(1), launch_record(2))
            result = smoke.build_result(
                release=self.release_inputs(root),
                release_id="build-987",
                app_tree=smoke.installed.AppTreeEvidence(
                    digest_algorithm="sha256-test-v1",
                    file_count=3,
                    sha256="c" * 64,
                    total_bytes=123,
                ),
                runs=runs,
                sqlite_evidence=sqlite_evidence(),
                runtime_identity_present=True,
            )

            def visit(value: object) -> None:
                if isinstance(value, dict):
                    for key, child in value.items():
                        lowered = key.lower()
                        self.assertNotIn("path", lowered)
                        self.assertNotIn("device", lowered)
                        self.assertNotIn("pid", lowered)
                        self.assertNotIn("dmgsha", lowered)
                        self.assertNotIn("dmgsize", lowered)
                        visit(child)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)
                elif isinstance(value, str):
                    self.assertNotIn("/dev/", value)
                    self.assertNotIn(str(root), value)

            visit(result)
            self.assertEqual(
                set(result["image"]),
                {"ephemeral", "filesystem", "format", "retained", "verified"},
            )
            self.assertEqual(result["image"]["format"], "UDZO")
            self.assertEqual(result["image"]["filesystem"], "HFS+")
            self.assertTrue(result["image"]["ephemeral"])
            self.assertTrue(result["mount"]["readOnly"])
            self.assertTrue(result["mount"]["detachedBeforeLaunch"])
            self.assertEqual(
                result["limitations"],
                [
                    "not-finder-ui-or-drag-and-drop-evidence",
                    "not-general-ui-or-accessibility-evidence",
                    "not-developer-id-notarized-or-stapled-distribution",
                    "not-gatekeeper-quarantine-or-download-evidence",
                    "not-clean-machine-account-or-system-applications",
                    "not-tcc-keychain-provider-network-or-device-evidence",
                    (
                        "not-arbitrary-history-crash-power-loss-or-"
                        "concurrent-writer-evidence"
                    ),
                    "not-backup-restore-or-device-transfer-evidence",
                    (
                        "not-upgrade-n-or-n-minus-one-rollback-production-"
                        "or-security-evidence"
                    ),
                ],
            )
            self.assertNotIn(
                "executablePathMatched",
                result["launchServices"]["runs"][0],
            )
            self.assertNotIn(
                "processIdentifier",
                result["launchServices"]["runs"][0],
            )

    def test_result_rejects_unproven_launch_and_sqlite_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            release = self.release_inputs(root)
            tree = smoke.installed.AppTreeEvidence(
                digest_algorithm="sha256-test-v1",
                file_count=3,
                sha256="c" * 64,
                total_bytes=123,
            )

            invalid_runs = [launch_record(1), launch_record(2)]
            invalid_runs[1]["terminationAccepted"] = False
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.build_result(
                    release=release,
                    release_id="build-987",
                    app_tree=tree,
                    runs=invalid_runs,
                    sqlite_evidence=sqlite_evidence(),
                    runtime_identity_present=True,
                )

            invalid_policy_runs = [launch_record(1), launch_record(2)]
            invalid_policy_runs[0]["activationPolicy"] = 1
            with self.assertRaises(smoke.LocalDMGSmokeError):
                smoke.build_result(
                    release=release,
                    release_id="build-987",
                    app_tree=tree,
                    runs=invalid_policy_runs,
                    sqlite_evidence=sqlite_evidence(),
                    runtime_identity_present=True,
                )

            valid_sqlite = list(sqlite_evidence())
            chat_index = next(
                index
                for index, item in enumerate(valid_sqlite)
                if item.filename == smoke.installed.CHAT_DATABASE_FILENAME
            )
            non_chat_index = next(
                index
                for index, item in enumerate(valid_sqlite)
                if item.filename != smoke.installed.CHAT_DATABASE_FILENAME
            )
            invalid_sets = []
            for chat_count in (True, 1):
                candidate = list(valid_sqlite)
                chat = candidate[chat_index]
                candidate[chat_index] = smoke.installed.SQLiteStateEvidence(
                    filename=chat.filename,
                    integrity_check="ok",
                    total_event_count=chat_count,
                )
                invalid_sets.append(candidate)
            candidate = list(valid_sqlite)
            non_chat = candidate[non_chat_index]
            candidate[non_chat_index] = smoke.installed.SQLiteStateEvidence(
                filename=non_chat.filename,
                integrity_check="ok",
                total_event_count=0,
            )
            invalid_sets.append(candidate)
            candidate = list(valid_sqlite)
            first = candidate[0]
            candidate[0] = smoke.installed.SQLiteStateEvidence(
                filename=first.filename,
                integrity_check="failed",
                total_event_count=first.total_event_count,
            )
            invalid_sets.append(candidate)
            invalid_sets.append(list(reversed(valid_sqlite)))

            for evidence in invalid_sets:
                with self.subTest(evidence=evidence):
                    with self.assertRaises(smoke.LocalDMGSmokeError):
                        smoke.build_result(
                            release=release,
                            release_id="build-987",
                            app_tree=tree,
                            runs=(launch_record(1), launch_record(2)),
                            sqlite_evidence=evidence,
                            runtime_identity_present=True,
                        )

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
        self.assertEqual(stderr.getvalue(), "Local DMG install smoke failed.\n")
        self.assertNotIn("/private/sensitive", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
