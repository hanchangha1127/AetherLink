#!/usr/bin/env python3
"""Unit tests for the API 36.1 lifecycle v2 runner helpers."""

from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from script import run_android_headless_emulator_product_lifecycle_v2 as runner


def completed(
    *,
    stdout: bytes = b"",
    stderr: bytes = b"",
    returncode: int = 0,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class AndroidHeadlessLifecycleV2RunnerTests(unittest.TestCase):
    def test_prepublication_validation_uses_one_held_evidence_snapshot(
        self,
    ) -> None:
        snapshot = Mock()
        snapshot.__enter__ = Mock(return_value=snapshot)
        snapshot.__exit__ = Mock(return_value=None)
        captured = {"fixture": object()}
        snapshot.capture.return_value = captured
        payload = {"status": "fixture"}
        output = Path("/fixture/output")
        root = Path("/fixture/root")
        sdk_root = Path("/fixture/sdk")
        java_home = Path("/fixture/java")
        with (
            patch.object(
                runner.contract,
                "EvidenceSnapshot",
                return_value=snapshot,
            ) as snapshot_type,
            patch.object(
                runner.contract,
                "payload_failures",
                return_value=["fixture failure"],
            ) as validate,
        ):
            self.assertEqual(
                runner.prepublication_payload_failures(
                    payload,
                    output_directory=output,
                    root=root,
                    sdk_root=sdk_root,
                    java_home=java_home,
                ),
                ["fixture failure"],
            )
        snapshot_type.assert_called_once_with(
            output / "result.json",
            result_required=False,
        )
        snapshot.capture.assert_called_once_with()
        validate.assert_called_once_with(
            payload,
            result_directory=output,
            evidence=captured,
            root=root,
            sdk_root=sdk_root,
            java_home=java_home,
        )
        snapshot.verify_unchanged.assert_called_once_with()

    def test_no_device_gate_wires_v2_syntax_and_unit_contracts(self) -> None:
        gate = (runner.ROOT / "script/check_no_device_quality.sh").read_text(
            encoding="utf-8"
        )
        syntax_start = gate.index("run check_python_syntax \\\n")
        syntax_end = gate.index("\n\nrun bash -n script/*.sh", syntax_start)
        unit_start = gate.index("run python3 -m unittest \\\n")
        unit_end = gate.index("\nrun git diff --check", unit_start)

        runner_path = (
            "script/run_android_headless_emulator_product_lifecycle_v2.py"
        )
        runner_test_path = (
            "script/test_run_android_headless_emulator_product_lifecycle_v2.py"
        )
        checker_path = (
            "script/check_android_headless_emulator_product_lifecycle_v2.py"
        )
        checker_test_path = (
            "script/test_check_android_headless_emulator_product_lifecycle_v2.py"
        )
        for path in (
            runner_path,
            runner_test_path,
            checker_path,
            checker_test_path,
        ):
            line = f"  {path} \\\n"
            positions = [
                index
                for index in range(len(gate))
                if gate.startswith(line, index)
            ]
            self.assertEqual(
                sum(syntax_start <= index < syntax_end for index in positions),
                1,
                path,
            )

        self.assertEqual(gate.count(runner_path), 1)
        self.assertEqual(gate.count(checker_path), 1)
        for path in (runner_test_path, checker_test_path):
            self.assertEqual(gate.count(path), 2)
            line = f"  {path} \\\n"
            positions = [
                index
                for index in range(len(gate))
                if gate.startswith(line, index)
            ]
            self.assertEqual(
                sum(unit_start <= index < unit_end for index in positions),
                1,
                path,
            )

    def test_v2_ui_capture_accepts_only_closed_successor_paths(self) -> None:
        xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<hierarchy><node package="com.localagentbridge.android" '
            b'text="Pair AetherLink" bounds="[0,0][100,100]"/></hierarchy>'
        )

        class Commands:
            def adb(self, *arguments: str, **keywords: object):
                if arguments[:2] == ("exec-out", "cat"):
                    return completed(stdout=xml)
                return completed()

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            root = runner.capture_ui(
                Commands(),  # type: ignore[arg-type]
                output,
                "ui/setup-first-launch.xml",
            )
            self.assertEqual(root.find("node").attrib["text"], "Pair AetherLink")
            self.assertEqual(
                (output / "ui/setup-first-launch.xml").read_bytes(),
                xml,
            )
            with self.assertRaisesRegex(runner.RunnerError, "unexpected v2 UI"):
                runner.capture_ui(
                    Commands(),  # type: ignore[arg-type]
                    output,
                    "ui/not-in-contract.xml",
                )

        pair_only = runner.ET.fromstring(
            '<hierarchy><node package="com.localagentbridge.android" '
            'text="Pair AetherLink" bounds="[148,167][764,284]"/></hierarchy>'
        )
        clipped = runner.ET.fromstring(
            '<hierarchy><node package="com.localagentbridge.android" '
            'text="Pair AetherLink" bounds="[148,167][764,284]"/>'
            '<node package="com.localagentbridge.android" scrollable="true" '
            'bounds="[53,276][1027,2295]"><node '
            'package="com.localagentbridge.android" checkable="true" '
            'checked="true" enabled="true" bounds="[95,2250][985,2376]">'
            '<node package="com.localagentbridge.android" '
            'text="Follow system language" bounds="[179,2260][900,2360]"/>'
            "</node></node></hierarchy>"
        )
        ready = runner.ET.fromstring(
            '<hierarchy><node package="com.localagentbridge.android" '
            'text="Pair AetherLink" bounds="[148,167][764,284]"/>'
            '<node package="com.localagentbridge.android" scrollable="true" '
            'bounds="[53,276][1027,2295]"><node '
            'package="com.localagentbridge.android" checkable="true" '
            'checked="true" enabled="true" bounds="[95,1800][985,1926]">'
            '<node package="com.localagentbridge.android" '
            'text="Follow system language" bounds="[179,1810][900,1910]"/>'
            "</node></node></hierarchy>"
        )
        predicate = lambda root: runner.base.has_fully_visible_checked_node(
            root,
            text="Follow system language",
            package=runner.PACKAGE_NAME,
        )
        anchor = lambda root: runner.base.has_node(
            root,
            text="Pair AetherLink",
            package=runner.PACKAGE_NAME,
        )
        commands = Mock()
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner, "capture_ui", side_effect=[pair_only, clipped, ready]),
            patch.object(runner.time, "sleep"),
        ):
            observed = runner.wait_for_ui_with_upward_swipes(
                commands,
                Path(temporary),
                "ui/follow-system-before-reboot.xml",
                predicate,
                anchor_predicate=anchor,
            )
        self.assertIs(observed, ready)
        self.assertEqual(commands.shell.call_count, 2)

        wrong_screen = runner.ET.fromstring("<hierarchy><node text=\"Launcher\"/></hierarchy>")
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner, "capture_ui", side_effect=[pair_only, wrong_screen]),
            patch.object(runner.time, "sleep"),
            self.assertRaisesRegex(runner.RunnerError, "screen anchor"),
        ):
            runner.wait_for_ui_with_upward_swipes(
                Mock(),
                Path(temporary),
                "ui/follow-system-before-reboot.xml",
                predicate,
                anchor_predicate=anchor,
            )

        permission = runner.ET.fromstring(
            '<hierarchy><node package="com.google.android.permissioncontroller" '
            'text="Allow AetherLink to take pictures and record video?" '
            'bounds="[80,600][1000,760]"/><node '
            'package="com.google.android.permissioncontroller" clickable="true" '
            'enabled="true" bounds="[80,1800][1000,1950]"><node '
            'package="com.google.android.permissioncontroller" '
            'resource-id="com.android.permissioncontroller:id/permission_deny_button" '
            'text="Don’t allow" bounds="[100,1820][980,1930]"/>'
            "</node></hierarchy>"
        )
        self.assertTrue(runner.permission_dialog_has_app_prompt(permission))
        self.assertEqual(
            runner.permission_dialog_denial_bounds(permission),
            (80, 1800, 1000, 1950),
        )
        disabled = runner.ET.fromstring(
            runner.ET.tostring(permission, encoding="unicode").replace(
                'enabled="true"', 'enabled="false"', 1
            )
        )
        self.assertIsNone(runner.permission_dialog_denial_bounds_or_none(disabled))

    def test_future_saved_data_seed_and_readback_are_exact(self) -> None:
        commands = Mock()
        commands.adb_path = Path("/fixture/adb")
        commands.environment = {"LANG": "C.UTF-8"}
        commands.serial = "emulator-5554"
        commands.run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout=runner.FUTURE_RUNTIME_LOCAL_STORE_WRITE_RECEIPT,
            stderr="",
        )
        commands.adb.return_value = completed(
            stdout=runner.FUTURE_RUNTIME_LOCAL_STORE_SEED,
        )

        seeded = runner.seed_future_runtime_local_data(commands)

        self.assertEqual(seeded, runner.FUTURE_RUNTIME_LOCAL_STORE_SEED)
        write_command = commands.run.call_args.args[0]
        self.assertEqual(
            write_command[:5],
            [
                "/fixture/adb",
                "-s",
                "emulator-5554",
                "shell",
                "-T",
            ],
        )
        self.assertEqual(len(write_command), 6)
        remote_argv = shlex.split(write_command[5])
        self.assertEqual(
            remote_argv[:4],
            ["run-as", runner.PACKAGE_NAME, "sh", "-c"],
        )
        self.assertEqual(len(remote_argv), 5)
        fixed_script = remote_argv[4]
        self.assertIn("umask 077", fixed_script)
        self.assertIn(f"{runner.FUTURE_RUNTIME_LOCAL_STORE_RELATIVE}.bak", fixed_script)
        self.assertIn(".aetherlink-v2", fixed_script)
        self.assertIn("chmod 600", fixed_script)
        self.assertIn("mv", fixed_script)
        self.assertIn("aetherlink-future-seed-ok", fixed_script)
        self.assertEqual(
            commands.run.call_args.kwargs["input_text"],
            runner.FUTURE_RUNTIME_LOCAL_STORE_SEED.decode("ascii"),
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            captured = runner.capture_future_runtime_local_data(
                commands,
                output,
                "runtime-local-store-after-future-version-first-launch.xml",
            )
            self.assertEqual(captured, runner.FUTURE_RUNTIME_LOCAL_STORE_SEED)
            self.assertEqual(
                (
                    output
                    / "runtime-local-store-after-future-version-first-launch.xml"
                ).read_bytes(),
                runner.FUTURE_RUNTIME_LOCAL_STORE_SEED,
            )

            commands.adb.return_value = completed(
                stdout=runner.FUTURE_RUNTIME_LOCAL_STORE_SEED + b" ",
            )
            with self.assertRaises(runner.RunnerError):
                runner.capture_future_runtime_local_data(
                    commands,
                    output,
                    "runtime-local-store-after-future-version-second-launch.xml",
                )
            with self.assertRaises(runner.RunnerError):
                runner.capture_future_runtime_local_data(
                    commands,
                    output,
                    "runtime-local-store-not-in-contract.xml",
                )

        for label, result in (
            (
                "wrong-receipt",
                subprocess.CompletedProcess([], 0, stdout="wrong\n", stderr=""),
            ),
            (
                "stderr",
                subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=runner.FUTURE_RUNTIME_LOCAL_STORE_WRITE_RECEIPT,
                    stderr="unexpected\n",
                ),
            ),
            (
                "nonzero",
                subprocess.CompletedProcess([], 1, stdout="", stderr="failed\n"),
            ),
        ):
            with self.subTest(label=label):
                commands.run.return_value = result
                with self.assertRaises(runner.RunnerError):
                    runner.seed_future_runtime_local_data(commands)

    def test_legacy_versionless_saved_data_migration_and_readback_are_exact(
        self,
    ) -> None:
        migrated = (
            b'<?xml version="1.0" encoding="utf-8" standalone="yes" ?>\n'
            b'<map>\n    <string name="runtime_data">'
            b"{&quot;androidAppLanguagePlatformMigrationVersion&quot;:1,"
            b"&quot;appLanguageSource&quot;:&quot;system&quot;,"
            b"&quot;appLanguageTag&quot;:&quot;en&quot;,"
            b"&quot;appTheme&quot;:&quot;dark&quot;,"
            b"&quot;composerDraft&quot;:&quot;legacy-v0&quot;,"
            b"&quot;trustedRuntimeAutoReconnectEnabled&quot;:false,"
            b"&quot;version&quot;:1}</string>\n</map>\n"
        )
        commands = Mock()
        commands.adb_path = Path("/fixture/adb")
        commands.environment = {"LANG": "C.UTF-8"}
        commands.serial = "emulator-5554"
        commands.run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout=runner.LEGACY_RUNTIME_LOCAL_STORE_WRITE_RECEIPT,
            stderr="",
        )
        commands.adb.side_effect = [
            completed(stdout=runner.LEGACY_RUNTIME_LOCAL_STORE_SEED),
            completed(stdout=runner.LEGACY_RUNTIME_LOCAL_STORE_SEED),
            completed(stdout=migrated),
            completed(stdout=migrated),
        ]

        seeded = runner.seed_legacy_runtime_local_data(commands)
        self.assertEqual(seeded, runner.LEGACY_RUNTIME_LOCAL_STORE_SEED)
        write_command = commands.run.call_args.args[0]
        self.assertEqual(
            write_command[:5],
            [
                "/fixture/adb",
                "-s",
                "emulator-5554",
                "shell",
                "-T",
            ],
        )
        remote_argv = shlex.split(write_command[5])
        self.assertEqual(
            remote_argv[:4],
            ["run-as", runner.PACKAGE_NAME, "sh", "-c"],
        )
        self.assertIn(".aetherlink-legacy", remote_argv[4])
        self.assertIn("aetherlink-legacy-seed-ok", remote_argv[4])
        self.assertEqual(
            commands.run.call_args.kwargs["input_text"],
            runner.LEGACY_RUNTIME_LOCAL_STORE_SEED.decode("ascii"),
        )

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner.time, "sleep"),
        ):
            output = Path(temporary)
            first, first_facts = (
                runner.wait_for_legacy_runtime_local_data_migration(
                    commands,
                    output,
                    "runtime-local-store-after-legacy-migration-first-launch.xml",
                )
            )
            second, second_facts = (
                runner.capture_legacy_migrated_runtime_local_data(
                    commands,
                    output,
                    "runtime-local-store-after-legacy-migration-second-launch.xml",
                )
            )
            self.assertEqual(first, migrated)
            self.assertEqual(second, migrated)
            self.assertEqual(first_facts, second_facts)
            self.assertEqual(first_facts["version"], 1)
            self.assertEqual(first_facts["appTheme"], "dark")
            self.assertEqual(first_facts["composerDraft"], "legacy-v0")
            self.assertIs(
                first_facts["trustedRuntimeAutoReconnectEnabled"],
                False,
            )
            self.assertEqual(
                (
                    output
                    / "runtime-local-store-after-legacy-migration-first-launch.xml"
                ).read_bytes(),
                migrated,
            )
            self.assertEqual(
                (
                    output
                    / "runtime-local-store-after-legacy-migration-second-launch.xml"
                ).read_bytes(),
                migrated,
            )
            with self.assertRaisesRegex(
                runner.RunnerError,
                "unexpected legacy-migration",
            ):
                runner.capture_legacy_migrated_runtime_local_data(
                    commands,
                    output,
                    "runtime-local-store-not-in-contract.xml",
                )

        with self.assertRaisesRegex(runner.RunnerError, "has not migrated"):
            runner.legacy_migrated_runtime_local_data_facts(
                runner.LEGACY_RUNTIME_LOCAL_STORE_SEED
            )

    def test_boot_id_capture_requires_one_exact_uuid_line(self) -> None:
        commands = Mock()
        raw = b"123e4567-e89b-42d3-a456-426614174000\n"
        commands.adb.return_value = completed(stdout=raw)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "boot-id.txt"
            self.assertEqual(
                runner.read_boot_id(commands, path),
                "123e4567-e89b-42d3-a456-426614174000",
            )
            self.assertEqual(path.read_bytes(), raw)

            for invalid in (
                raw.rstrip(b"\n"),
                raw + b"extra\n",
                b"123E4567-e89b-42d3-a456-426614174000\n",
                b"not-a-uuid\n",
            ):
                with self.subTest(invalid=invalid):
                    commands.adb.return_value = completed(stdout=invalid)
                    with self.assertRaisesRegex(runner.RunnerError, "boot_id"):
                        runner.read_boot_id(commands)

    def test_camera_preferences_require_only_recorded_state(self) -> None:
        commands = Mock()
        valid = (
            b"<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n"
            b"<map>\n"
            b"    <string name=\"request_state\">recorded</string>\n"
            b"</map>\n"
        )
        commands.adb.return_value = completed(stdout=valid)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "preferences.xml"
            self.assertEqual(runner.capture_camera_preferences(commands, path), valid)
            self.assertEqual(path.read_bytes(), valid)

            for invalid in (
                b"<map/>",
                b'<map><string name="request_state">launch_pending</string></map>',
                b'<map><string name="request_state">recorded</string>'
                b'<boolean name="request_recorded" value="true"/></map>',
            ):
                with self.subTest(invalid=invalid):
                    commands.adb.return_value = completed(stdout=invalid)
                    with self.assertRaisesRegex(runner.RunnerError, "recorded state"):
                        runner.capture_camera_preferences(commands, path)

    def test_process_identity_binds_boot_pid_cmdline_and_start_ticks(self) -> None:
        commands = Mock()
        commands.serial = "emulator-5554"
        pid = 43210
        start_ticks = 987654
        stat = (
            f"{pid} (tbridge.android) S "
            + " ".join(["0"] * 18)
            + f" {start_ticks} 0 0\n"
        ).encode("ascii")
        cmdline = runner.PACKAGE_NAME.encode("ascii") + b"\0"
        commands.adb.side_effect = [
            completed(stdout=f"{pid}\n".encode("ascii")),
            completed(stdout=stat),
            completed(stdout=cmdline),
            completed(stdout=stat),
        ]
        record = runner.capture_process_identity(
            commands,
            label="before_doze",
            boot_id="123e4567-e89b-42d3-a456-426614174000",
        )
        self.assertEqual(runner.process_pid(record), pid)
        self.assertEqual(record["processStartTicks"], start_ticks)
        self.assertEqual(
            runner.process_identity_key(record),
            ("123e4567-e89b-42d3-a456-426614174000", pid, start_ticks),
        )
        self.assertEqual(record["command"], ["pidof", runner.PACKAGE_NAME])

    def test_process_identity_rejects_changed_start_ticks(self) -> None:
        commands = Mock()
        commands.serial = "emulator-5554"
        pid = 43210

        def stat(ticks: int) -> bytes:
            return (
                f"{pid} (tbridge.android) S "
                + " ".join(["0"] * 18)
                + f" {ticks} 0 0\n"
            ).encode("ascii")

        commands.adb.side_effect = [
            completed(stdout=b"43210\n"),
            completed(stdout=stat(10)),
            completed(stdout=runner.PACKAGE_NAME.encode("ascii") + b"\0"),
            completed(stdout=stat(11)),
        ]
        with self.assertRaisesRegex(runner.RunnerError, "identity changed"):
            runner.capture_process_identity(
                commands,
                label="before_doze",
                boot_id="123e4567-e89b-42d3-a456-426614174000",
            )

    def test_deep_idle_parser_requires_one_deep_state(self) -> None:
        self.assertEqual(
            runner.deep_idle_state(
                b"mLightState=ACTIVE\n  mState=IDLE mLightState=OVERRIDE\n"
            ),
            "IDLE",
        )
        with self.assertRaisesRegex(runner.RunnerError, "one deep mState"):
            runner.deep_idle_state(b"mState=IDLE\nmState=ACTIVE\n")

        for deep_state in (b"ACTIVE", b"IDLE"):
            receipt = (
                b"Light state: OVERRIDE, deep state: "
                + deep_state
                + b"\n"
                b"mForceModeManagerQuickDozeRequest: false\n"
                b"mForceModeManagerOffBodyState: false\n"
            )
            self.assertEqual(
                runner.deviceidle_unforce_receipt_states(receipt),
                ("OVERRIDE", deep_state.decode("ascii")),
            )
        for invalid in (
            b"Light state: ACTIVE, deep state: ACTIVE\n",
            receipt.replace(b"QuickDozeRequest: false", b"QuickDozeRequest: true"),
            receipt.replace(b"OVERRIDE", b"UNKNOWN"),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(runner.RunnerError, "unforce receipt"):
                    runner.deviceidle_unforce_receipt_states(invalid)

    def test_same_uid_sigkill_and_pidof_absence_receipts_are_exact(self) -> None:
        commands = Mock()
        commands.serial = "emulator-5554"
        commands.adb.side_effect = [
            completed(),
            completed(stdout=b"43210\n"),
            completed(returncode=1),
        ]
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner.time, "monotonic", return_value=0),
            patch.object(runner.time, "sleep"),
        ):
            output = Path(temporary)
            runner.kill_background_process(commands, output, pid=43210)
            runner.wait_for_exact_pidof_absence(commands, output)
            kill = json.loads((output / "process-kill-receipt.json").read_bytes())
            absent = json.loads((output / "pidof-absence-receipt.json").read_bytes())
        self.assertEqual(
            kill,
            {
                "command": [
                    "run-as",
                    runner.PACKAGE_NAME,
                    "kill",
                    "-9",
                    "43210",
                ],
                "exitCode": 0,
                "serial": "emulator-5554",
                "stderr": "",
                "stdout": "",
            },
        )
        self.assertEqual(absent["command"], ["pidof", runner.PACKAGE_NAME])
        self.assertEqual(absent["exitCode"], 1)
        self.assertEqual((absent["stdout"], absent["stderr"]), ("", ""))

    def test_guest_reboot_records_ordered_disconnect_reconnect_and_boot(self) -> None:
        commands = Mock()
        commands.serial = "emulator-5554"
        commands.adb.side_effect = [
            completed(stdout=b"device\n"),
            completed(),
            completed(stderr=b"error: device offline\n", returncode=1),
            completed(stdout=b"device\n"),
            completed(stdout=b"1\n"),
        ]
        process = Mock()
        process.poll.return_value = None
        monotonic_ns = [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000]
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(runner.time, "monotonic", return_value=0),
            patch.object(runner.time, "monotonic_ns", side_effect=monotonic_ns),
        ):
            output = Path(temporary)
            runner.wait_for_guest_reboot(commands, process, output)
            observations = json.loads(
                (output / "reboot-transport-observations.json").read_bytes()
            )
            reboot = json.loads((output / "adb-reboot-receipt.json").read_bytes())
            self.assertEqual(
                (output / "boot-completed-after-reboot.txt").read_bytes(),
                b"1\n",
            )
        self.assertEqual(
            [record["phase"] for record in observations],
            ["before_reboot", "disconnected", "reconnected", "boot_completed"],
        )
        self.assertEqual(
            [record["observedState"] for record in observations],
            ["device", "absent", "device", "1"],
        )
        self.assertEqual(reboot["command"], ["reboot"])

    def test_invalid_run_id_creates_no_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "invalid"
            with (
                patch.object(runner.base, "ensure_host_and_sdk"),
                self.assertRaisesRegex(runner.RunnerError, "exact v2 run id"),
            ):
                runner.run_lane(
                    sdk_root=Path("/fixture/sdk"),
                    java_home=Path("/fixture/java"),
                    output_directory=output,
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
