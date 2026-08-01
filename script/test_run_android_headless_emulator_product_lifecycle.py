#!/usr/bin/env python3
"""Unit tests for the owned Android headless lifecycle runner."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from script import run_android_headless_emulator_product_lifecycle as runner


def completed(
    command: list[str] | None = None,
    *,
    stdout: str | bytes = "",
    stderr: str | bytes = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
        command or [],
        returncode,
        stdout=stdout,
        stderr=stderr,
    )


class FakeProcess:
    def __init__(self, *, pid: int = 43210, stubborn: bool = False) -> None:
        self.pid = pid
        self.stubborn = stubborn
        self.returncode: int | None = None
        self.wait_calls: list[int | float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: int | float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.stubborn:
            raise subprocess.TimeoutExpired("fixture", timeout)
        self.returncode = 0
        return 0


class HeadlessLifecycleRunnerTests(unittest.TestCase):
    def test_commands_pin_java_home_and_path(self) -> None:
        commands = runner.Commands(
            sdk_root=Path("/fixture/sdk"),
            java_home=Path("/fixture/java"),
        )
        self.assertEqual(commands.environment["JAVA_HOME"], "/fixture/java")
        self.assertTrue(
            commands.environment["PATH"].startswith(
                "/fixture/java/bin" + os.pathsep
            )
        )

    def test_adb_snapshot_includes_every_transport_state(self) -> None:
        output = """List of devices attached
emulator-5554 device product:a
emulator-5556 offline
emulator-5558 unauthorized
emulator-5560 recovery
emulator-5562 bootloader
* daemon started successfully
"""
        expected = (
            "emulator-5554",
            "emulator-5556",
            "emulator-5558",
            "emulator-5560",
            "emulator-5562",
        )
        self.assertEqual(runner.parse_adb_devices(output), expected)

    def test_host_inventory_binds_pid_start_time_port_and_command(self) -> None:
        sdk_root = Path("/fixture/sdk")
        qemu = (
            sdk_root
            / "emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"
        )
        command = f"{qemu} -avd Existing -port 5580 -no-window"
        commands = Mock()
        commands.sdk_root = sdk_root
        commands.run.side_effect = [
            completed(stdout=f"  7 /usr/bin/other\n78792 {command}\n"),
            completed(stdout="Fri Jul 31 15:56:45 2026    \n"),
            completed(stdout=f"78792 {command}\n"),
        ]
        records = runner.host_emulator_inventory(commands)
        self.assertEqual(
            records,
            [
                {
                    "commandSha256": runner.hashlib.sha256(
                        command.encode("utf-8")
                    ).hexdigest(),
                    "pid": 78792,
                    "port": 5580,
                    "processStartedAt": "Fri Jul 31 15:56:45 2026",
                    "serial": "emulator-5580",
                }
            ],
        )

    def test_port_selection_reserves_adb_and_host_owned_ports(self) -> None:
        devices = completed(
            stdout=(
                "List of devices attached\n"
                "emulator-5554 recovery product:fixture\n"
            )
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner.subprocess, "run", return_value=devices),
            patch.object(runner, "port_is_bindable", return_value=True),
            patch.object(runner.tempfile, "gettempdir", return_value=temporary),
        ):
            port, descriptor, serials, raw = runner.acquire_emulator_port(
                Path("/fixture/adb"),
                {},
                reserved_ports={5556},
            )
            self.assertEqual(port, 5558)
            self.assertEqual(serials, ("emulator-5554",))
            self.assertEqual(raw, devices.stdout)
            runner.release_emulator_port_lock(descriptor)

    def test_ephemeral_avd_and_launch_are_exact(self) -> None:
        avd_name = "AetherLink_API_36_1_5554_0123abcd"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            avd_home = runner.create_ephemeral_avd(
                root,
                sdk_root=Path("/fixture/sdk"),
                avd_name=avd_name,
            )
            self.assertEqual(
                (avd_home / f"{avd_name}.avd/config.ini").read_bytes(),
                runner.contract.avd_config_bytes(avd_name),
            )
            self.assertIn(
                f"path={avd_home / (avd_name + '.avd')}",
                (avd_home / f"{avd_name}.ini").read_text(encoding="ascii"),
            )
        command = runner.emulator_launch_command(
            Path("/fixture/emulator"),
            avd_name=avd_name,
            port=5554,
        )
        self.assertEqual(command[-len(runner.contract.LAUNCH_FLAGS) :], list(runner.contract.LAUNCH_FLAGS))
        self.assertIn("-wifi-user-mode-options", command)
        self.assertIn("-network-user-mode-options", command)
        for bad_port in (5553, 5555, 5586):
            with self.subTest(port=bad_port), self.assertRaises(runner.RunnerError):
                runner.emulator_launch_command(
                    Path("/fixture/emulator"),
                    avd_name=avd_name,
                    port=bad_port,
                )

    def test_identity_verification_is_read_only_and_fails_closed(self) -> None:
        commands = Mock()
        commands.adb.return_value = completed(stdout="Another_AVD\nOK\n")
        process = FakeProcess()
        with self.assertRaisesRegex(runner.RunnerError, "exact owned AVD"):
            runner.verify_owned_emulator_identity(
                commands,
                process,  # type: ignore[arg-type]
                expected_avd_name="AetherLink_API_36_1_5554_0123abcd",
            )
        commands.adb.assert_called_once_with("emu", "avd", "name", timeout=30)
        self.assertEqual(process.poll(), None)

    def test_main_activity_requires_exact_top_resumed_line(self) -> None:
        exact = (
            "topResumedActivity=ActivityRecord{a u0 "
            "com.localagentbridge.android/.MainActivity t1}\n"
        )
        self.assertTrue(runner.main_activity_is_resumed(exact))
        self.assertFalse(
            runner.main_activity_is_resumed(
                "topResumedActivity=ActivityRecord{settings}\n"
                "com.localagentbridge.android/.MainActivity\n"
            )
        )
        self.assertFalse(
            runner.main_activity_is_resumed(
                exact.replace(".MainActivity ", ".MainActivityEvil ")
            )
        )

    def test_process_id_retains_exact_owned_pidof_observation(self) -> None:
        commands = Mock()
        commands.serial = "emulator-5554"
        cmdline = runner.PACKAGE_NAME.encode("ascii") + (b"\0" * 8)
        start_ticks = 54321
        stat = (
            "43210 (tbridge.android) S "
            + " ".join(["0"] * 18)
            + f" {start_ticks} 0 0\n"
        ).encode("ascii")
        commands.adb.side_effect = [
            completed(stdout=b"43210\n", stderr=b""),
            completed(stdout=stat, stderr=b""),
            completed(stdout=cmdline, stderr=b""),
            completed(stdout=stat, stderr=b""),
        ]
        observations: list[dict[str, object]] = []
        observed = runner.process_id(
            commands,
            observation_label="clean_install_and_first_launch",
            observations=observations,
        )
        self.assertEqual(observed, 43210)
        self.assertEqual(
            observations,
            [
                {
                    "command": ["pidof", runner.PACKAGE_NAME],
                    "label": "clean_install_and_first_launch",
                    "procCmdlineBase64": runner.base64.b64encode(cmdline).decode(
                        "ascii"
                    ),
                    "procCmdlineCommand": ["cat", "/proc/43210/cmdline"],
                    "procStatAfterCommand": ["cat", "/proc/43210/stat"],
                    "procStatAfterStdout": stat.decode("ascii"),
                    "procStatBeforeCommand": ["cat", "/proc/43210/stat"],
                    "procStatBeforeStdout": stat.decode("ascii"),
                    "processStartTicks": start_ticks,
                    "serial": "emulator-5554",
                    "stdout": "43210\n",
                }
            ],
        )
        commands.adb.side_effect = None
        commands.adb.return_value = completed(
            stdout=b"43210 43211\n",
            stderr=b"",
        )
        with self.assertRaisesRegex(runner.RunnerError, "expected one"):
            runner.process_id(commands)

    def test_process_id_rejects_pidof_failure_and_identity_change(self) -> None:
        commands = Mock()
        commands.serial = "emulator-5554"
        for result in (
            completed(stdout=b"43210\n", stderr=b"", returncode=1),
            completed(stdout=b"43210\n", stderr=b"warning\n", returncode=0),
        ):
            with self.subTest(result=result), self.assertRaisesRegex(
                runner.RunnerError,
                "exit zero with empty stderr",
            ):
                commands.adb.side_effect = [result]
                runner.process_id(commands)

        cmdline = runner.PACKAGE_NAME.encode("ascii") + b"\0"

        def stat(start_ticks: int) -> bytes:
            return (
                "43210 (tbridge.android) S "
                + " ".join(["0"] * 18)
                + f" {start_ticks} 0 0\n"
            ).encode("ascii")

        commands.adb.side_effect = [
            completed(stdout=b"43210\n", stderr=b""),
            completed(stdout=stat(54321), stderr=b""),
            completed(stdout=cmdline, stderr=b""),
            completed(stdout=stat(54322), stderr=b""),
        ]
        with self.assertRaisesRegex(runner.RunnerError, "identity changed"):
            runner.process_id(commands)

    def test_exact_shell_line_capture_rejects_noncanonical_state_output(self) -> None:
        commands = Mock()
        expected = runner.contract.APP_NETWORKING_DENIED_STATE
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.txt"
            commands.adb.return_value = completed(
                stdout=(expected + "\n").encode("ascii"),
                stderr=b"",
            )
            self.assertEqual(
                runner.capture_exact_shell_line(
                    commands,
                    path,
                    "cmd",
                    "connectivity",
                    "get-package-networking-enabled",
                    runner.PACKAGE_NAME,
                    expected=expected,
                    label="package networking state",
                ),
                (expected + "\n").encode("ascii"),
            )
            self.assertEqual(path.read_bytes(), (expected + "\n").encode("ascii"))

            for raw in (
                b"false\n",
                (expected + "\nextra\n").encode("ascii"),
                expected.encode("ascii"),
                b"\xff\n",
            ):
                with self.subTest(raw=raw):
                    commands.adb.return_value = completed(stdout=raw, stderr=b"")
                    with self.assertRaisesRegex(runner.RunnerError, "one exact"):
                        runner.capture_exact_shell_line(
                            commands,
                            path,
                            "fixture",
                            expected=expected,
                            label="package networking state",
                        )

    def test_locale_wait_timeout_reports_last_observed_value(self) -> None:
        commands = Mock()
        with (
            patch.object(runner, "get_app_locales", return_value=["en"]),
            patch.object(
                runner.time,
                "monotonic",
                side_effect=[0, 0, 0.5, 0.5, 1.1],
            ),
            patch.object(runner.time, "sleep"),
            self.assertRaisesRegex(
                runner.RunnerError,
                r"expected \['ko'\], last observed \['en'\]",
            ),
        ):
            runner.wait_for_app_locales(
                commands,
                ["ko"],
                description="fixture locale",
                timeout=1,
            )

    def test_locale_wait_rejects_expected_value_returned_after_deadline(self) -> None:
        commands = Mock()
        with (
            patch.object(runner, "get_app_locales", return_value=["ko"]) as get_locales,
            patch.object(runner.time, "monotonic", side_effect=[0, 0, 1.1]),
            self.assertRaisesRegex(runner.RunnerError, "timed out waiting"),
        ):
            runner.wait_for_app_locales(
                commands,
                ["ko"],
                description="late locale",
                timeout=1,
            )
        get_locales.assert_called_once_with(commands, timeout=1)

    def test_ui_wait_rejects_target_returned_after_deadline(self) -> None:
        commands = Mock()
        target = ET.fromstring('<hierarchy><node text="ready"/></hierarchy>')
        predicate = Mock(return_value=True)
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner, "capture_ui", return_value=target),
            patch.object(runner.time, "monotonic", side_effect=[0, 31]),
            self.assertRaisesRegex(runner.RunnerError, "absolute deadline"),
        ):
            runner.wait_for_ui(
                commands,
                Path(temporary),
                "ui/first-launch.xml",
                predicate,
            )
        predicate.assert_not_called()

    def test_ui_capture_caps_every_adb_call_to_remaining_deadline(self) -> None:
        xml = b'<hierarchy><node text="ready"/></hierarchy>'
        calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

        class Commands:
            def adb(self, *arguments: str, **keywords: object):
                calls.append((arguments, keywords))
                if arguments[:2] == ("exec-out", "cat"):
                    return completed(stdout=xml, stderr=b"")
                return completed(stdout="", stderr="")

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner.time, "monotonic", return_value=5),
        ):
            runner.capture_ui(
                Commands(),  # type: ignore[arg-type]
                Path(temporary),
                "ui/first-launch.xml",
                deadline=8,
            )
        self.assertGreaterEqual(len(calls), 4)
        for _, keywords in calls:
            self.assertGreater(keywords["timeout"], 0)
            self.assertLessEqual(keywords["timeout"], 3)

    def test_scrolling_ui_wait_allows_initial_anchor_transition(self) -> None:
        commands = Mock()
        old_screen = ET.fromstring('<hierarchy><node text="old"/></hierarchy>')
        ready = ET.fromstring(
            '<hierarchy><node text="Settings"/><node text="한국어"/></hierarchy>'
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner, "capture_ui", side_effect=[old_screen, ready]),
            patch.object(runner.time, "monotonic", return_value=0),
            patch.object(runner.time, "sleep"),
        ):
            observed = runner.wait_for_ui_with_upward_swipes(
                commands,
                Path(temporary),
                "ui/in-app-korean-settings.xml",
                lambda root: runner.has_node(root, text="한국어"),
                anchor_predicate=lambda root: runner.has_node(root, text="Settings"),
            )
        self.assertIs(observed, ready)
        commands.shell.assert_not_called()

    def test_camera_permission_capture_retains_exact_raw_state(self) -> None:
        commands = Mock()
        raw = (
            b"Package [com.localagentbridge.android]\n"
            b"    android.permission.CAMERA: granted=false, flags=[ USER_SET ]\n"
        )
        commands.adb.return_value = completed(stdout=raw, stderr=b"")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "camera.txt"
            self.assertEqual(
                runner.capture_camera_permission_state(
                    commands,
                    path,
                    expected_granted=False,
                ),
                raw,
            )
            self.assertEqual(path.read_bytes(), raw)
            with self.assertRaisesRegex(runner.RunnerError, "granted=true"):
                runner.capture_camera_permission_state(
                    commands,
                    path,
                    expected_granted=True,
                )

            commands.adb.return_value = completed(stdout=raw + raw, stderr=b"")
            with self.assertRaisesRegex(runner.RunnerError, "exactly once"):
                runner.capture_camera_permission_state(
                    commands,
                    path,
                    expected_granted=False,
                )

    def test_clickable_ancestor_and_ui_capture_are_stale_safe(self) -> None:
        root = ET.fromstring(
            '<hierarchy><node clickable="true" bounds="[10,20][110,220]">'
            '<node text="Scan QR" package="com.localagentbridge.android" '
            'clickable="false" bounds="[20,30][100,100]"/>'
            "</node></hierarchy>"
        )
        self.assertEqual(
            runner.clickable_bounds_for(root, text="Scan QR"),
            (10, 20, 110, 220),
        )
        visible = ET.fromstring(
            '<hierarchy><node text="Chat" enabled="true" '
            'clickable="false" bounds="[5,6][50,60]"/></hierarchy>'
        )
        self.assertEqual(
            runner.visible_bounds_for(visible, text="Chat"),
            (5, 6, 50, 60),
        )
        selected = ET.fromstring(
            '<hierarchy><node selected="true"><node text="Settings"/>'
            "</node></hierarchy>"
        )
        self.assertTrue(runner.has_selected_ancestor(selected, text="Settings"))

        clipped = ET.fromstring(
            '<hierarchy><node scrollable="true" bounds="[0,0][100,100]">'
            '<node clickable="true" enabled="true" bounds="[0,80][100,120]">'
            '<node text="한국어" enabled="true" bounds="[10,80][90,100]"/>'
            "</node></node></hierarchy>"
        )
        self.assertFalse(
            runner.has_fully_visible_clickable_node(clipped, text="한국어")
        )
        with self.assertRaisesRegex(runner.RunnerError, "fully visible"):
            runner.fully_visible_clickable_bounds_for(clipped, text="한국어")
        fully_visible = ET.fromstring(
            '<hierarchy><node scrollable="true" bounds="[0,0][100,100]">'
            '<node clickable="true" enabled="true" bounds="[0,60][100,100]">'
            '<node text="한국어" enabled="true" bounds="[10,65][90,95]"/>'
            "</node></node></hierarchy>"
        )
        self.assertEqual(
            runner.fully_visible_clickable_bounds_for(
                fully_visible,
                text="한국어",
            ),
            (0, 60, 100, 100),
        )

        xml = b'<hierarchy><node text="Pair AetherLink"/></hierarchy>'
        calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

        class Commands:
            def adb(self, *arguments: str, **keywords: object):
                calls.append((arguments, keywords))
                if arguments[:2] == ("exec-out", "cat"):
                    return completed(stdout=xml, stderr=b"")
                return completed(stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temporary:
            result_directory = Path(temporary)
            parsed = runner.capture_ui(
                Commands(),  # type: ignore[arg-type]
                result_directory,
                "ui/first-launch.xml",
            )
            self.assertTrue(runner.has_node(parsed, text="Pair AetherLink"))
            self.assertEqual(
                (result_directory / "ui/first-launch.xml").read_bytes(),
                xml,
            )
        rm_calls = [arguments for arguments, _ in calls if arguments[:3] == ("shell", "rm", "-f")]
        self.assertEqual(len(rm_calls), 2)
        self.assertEqual(rm_calls[0][3], rm_calls[1][3])

    def test_ui_scroll_search_uses_incremental_swipes_without_overshoot(self) -> None:
        clipped = ET.fromstring('<hierarchy><node text="other"/></hierarchy>')
        ready = ET.fromstring('<hierarchy><node text="한국어"/></hierarchy>')
        commands = Mock()
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner, "capture_ui", side_effect=[clipped, ready]),
            patch.object(runner.time, "sleep"),
        ):
            observed = runner.wait_for_ui_with_upward_swipes(
                commands,
                Path(temporary),
                "ui/in-app-korean-settings.xml",
                lambda root: runner.has_node(root, text="한국어"),
            )
        self.assertIs(observed, ready)
        commands.shell.assert_called_once()
        swipe_arguments, swipe_keywords = commands.shell.call_args
        self.assertEqual(
            swipe_arguments,
            ("input", "swipe", "540", "2050", "540", "1700", "350"),
        )
        self.assertGreater(swipe_keywords["timeout"], 0)
        self.assertLessEqual(swipe_keywords["timeout"], 10)

        anchored_screen = ET.fromstring(
            '<hierarchy><node text="Pair AetherLink"/></hierarchy>'
        )
        wrong_screen = ET.fromstring(
            '<hierarchy><node text="Launcher"/></hierarchy>'
        )
        commands = Mock()
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(
                runner,
                "capture_ui",
                side_effect=[anchored_screen, wrong_screen],
            ),
            patch.object(runner.time, "sleep"),
            self.assertRaisesRegex(runner.RunnerError, "screen anchor"),
        ):
            runner.wait_for_ui_with_upward_swipes(
                commands,
                Path(temporary),
                "ui/in-app-korean-settings.xml",
                lambda root: runner.has_node(root, text="한국어"),
                anchor_predicate=lambda root: runner.has_node(
                    root,
                    text="Pair AetherLink",
                ),
            )
        commands.shell.assert_called_once()

    def test_cleanup_signals_only_owned_process_group_then_removes_avd(self) -> None:
        process = FakeProcess()
        with tempfile.TemporaryDirectory() as temporary:
            avd_root = Path(temporary) / "owned-avd"
            avd_root.mkdir()
            with (
                patch.object(runner.os, "getpgid", return_value=process.pid),
                patch.object(runner.os, "killpg") as killpg,
            ):
                runner.cleanup_owned_emulator(
                    process,  # type: ignore[arg-type]
                    temporary_root=avd_root,
                )
            killpg.assert_called_once_with(process.pid, signal.SIGTERM)
            self.assertFalse(avd_root.exists())

    def test_cleanup_retains_avd_when_owned_process_cannot_exit(self) -> None:
        process = FakeProcess(stubborn=True)
        with tempfile.TemporaryDirectory() as temporary:
            avd_root = Path(temporary) / "owned-avd"
            avd_root.mkdir()
            with (
                patch.object(runner.os, "getpgid", return_value=process.pid),
                patch.object(runner.os, "killpg") as killpg,
                self.assertRaisesRegex(runner.RunnerError, "did not exit"),
            ):
                runner.cleanup_owned_emulator(
                    process,  # type: ignore[arg-type]
                    temporary_root=avd_root,
                )
            self.assertEqual(
                killpg.call_args_list,
                [
                    unittest.mock.call(process.pid, signal.SIGTERM),
                    unittest.mock.call(process.pid, signal.SIGKILL),
                ],
            )
            self.assertTrue(avd_root.exists())

    def test_post_cleanup_waits_for_owned_transport_to_disappear(self) -> None:
        commands = Mock()
        commands.adb_path = Path("/fixture/adb")
        commands.run.side_effect = [
            completed(
                stdout=(
                    "List of devices attached\n"
                    "emulator-5554 offline\n"
                    "emulator-5580 device\n"
                )
            ),
            completed(
                stdout=(
                    "List of devices attached\n"
                    "emulator-5580 device\n"
                )
            ),
        ]
        with (
            patch.object(runner.time, "monotonic", side_effect=[0, 0, 1]),
            patch.object(runner.time, "sleep"),
        ):
            raw, serials = runner.wait_for_post_cleanup_devices(
                commands,
                owned_serial="emulator-5554",
                preexisting_serials=("emulator-5580",),
            )
        self.assertNotIn("emulator-5554", raw)
        self.assertEqual(serials, ["emulator-5580"])

    def test_port_lock_is_released_only_by_explicit_finalizer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "port.lock"
            first = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            second = os.open(path, os.O_RDWR)
            fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            runner.release_emulator_port_lock(first)
            fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(second, fcntl.LOCK_UN)
            os.close(second)

    def test_invalid_output_name_leaves_no_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "invalid"
            with (
                patch.object(runner, "ensure_host_and_sdk"),
                self.assertRaisesRegex(runner.RunnerError, "versioned run id"),
            ):
                runner.run_lane(
                    sdk_root=Path("/fixture/sdk"),
                    output_directory=output,
                )
            self.assertFalse(output.exists())

    def test_forbidden_exit_and_logcat_parsers_cover_real_formats(self) -> None:
        self.assertTrue(
            runner.find_forbidden_exit_lines(
                "process=com.localagentbridge.android reason=4 (CRASH)\n"
            )
        )
        self.assertTrue(
            runner.find_forbidden_logcat_lines(
                "FATAL EXCEPTION: main\n"
                "Process: com.localagentbridge.android, PID: 1\n"
            )
        )


if __name__ == "__main__":
    unittest.main()
