#!/usr/bin/env python3
"""Mutation tests for the Android API 36.1 lifecycle v2 evidence checker."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from script import check_android_headless_emulator_product_lifecycle as v1
from script import check_android_headless_emulator_product_lifecycle_v2 as checker


class AndroidLifecycleV2CheckerTests(unittest.TestCase):
    def test_checker_script_entrypoint_imports_from_an_independent_process(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(Path(checker.__file__).resolve()), "--help"],
            cwd=Path(checker.__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Independently read back", completed.stdout)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary.name).resolve()
        self.root = temporary_root / "source"
        self.sdk_root = temporary_root / "sdk"
        self.java_home = temporary_root / "java-home"
        self.result_directory = temporary_root / (
            "android-headless-api36-1-v2-20260801T000000Z-deadbeef"
        )
        self.result_directory.mkdir(parents=True)
        (self.result_directory / "ui").mkdir()

        self.apk_path = self.root / v1.DEBUG_APK_RELATIVE
        self.apk_path.parent.mkdir(parents=True)
        self.apk_path.write_bytes(b"fixture-v2-debug-apk\n")
        for relative, raw in (
            (Path("platform-tools/adb"), b"fixture-adb\n"),
            (Path("emulator/emulator"), b"fixture-emulator\n"),
            (
                Path("emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"),
                b"fixture-qemu\n",
            ),
        ):
            path = self.sdk_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o755)
        java = self.java_home / "bin/java"
        java.parent.mkdir(parents=True)
        java.write_bytes(b"fixture-java\n")
        java.chmod(0o755)

        self.boot_before = "12345678-1234-4123-8123-123456789abc"
        self.boot_after = "abcdefab-cdef-4abc-9def-abcdefabcdef"
        self.serial = "emulator-5554"
        self.avd_name = "AetherLink_API_36_1_5554_0123abcd"
        self.owned_emulator = {
            "commandSha256": "5" * 64,
            "pid": 78792,
            "port": 5554,
            "processStartedAt": "Sat Aug  1 00:00:00 2026",
            "serial": self.serial,
        }
        self.preexisting_emulators = [
            {
                "commandSha256": "6" * 64,
                "pid": 70000,
                "port": 5580,
                "processStartedAt": "Fri Jul 31 23:00:00 2026",
                "serial": "emulator-5580",
            }
        ]
        self.processes = {
            "before_doze": (self.boot_before, 101, 50_101),
            "after_doze": (self.boot_before, 101, 50_101),
            "before_kill": (self.boot_before, 102, 50_102),
            "after_kill": (self.boot_before, 103, 50_103),
            "before_reboot": (self.boot_before, 103, 50_103),
            "after_reboot": (self.boot_after, 104, 50_104),
        }
        self.preference_bytes = (
            b'<?xml version="1.0" encoding="utf-8" standalone="yes" ?>\n'
            b'<map>\n    <string name="request_state">recorded</string>\n</map>\n'
        )
        self.source_snapshot = {
            "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
            "fileCount": 1,
            "files": [
                {
                    "mode": "0644",
                    "path": "fixture.kt",
                    "sha256": "1" * 64,
                    "size": 1,
                }
            ],
            "sha256": "2" * 64,
        }
        self.system_image_snapshot = {
            "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
            "fileCount": 1,
            "files": [
                {
                    "mode": "0644",
                    "path": "system.img",
                    "sha256": "3" * 64,
                    "size": 1,
                }
            ],
            "package": v1.SYSTEM_IMAGE_PACKAGE,
            "sha256": "4" * 64,
        }
        self._write_evidence_fixture()
        self.payload = self._valid_payload()
        self.result_path = self.result_directory / "result.json"
        self._write_result()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _json_bytes(value: object) -> bytes:
        return checker.canonical_json_bytes(value)

    def _process_record(self, label: str) -> dict[str, object]:
        boot_id, pid, ticks = self.processes[label]
        stat = (
            f"{pid} (tbridge.android) S "
            + " ".join(["0"] * 18)
            + f" {ticks} 0 0\n"
        )
        return {
            "bootId": boot_id,
            "command": ["pidof", checker.PACKAGE_NAME],
            "label": label,
            "procCmdlineBase64": base64.b64encode(
                checker.PACKAGE_NAME.encode("ascii") + b"\0"
            ).decode("ascii"),
            "procCmdlineCommand": ["cat", f"/proc/{pid}/cmdline"],
            "procStatAfterCommand": ["cat", f"/proc/{pid}/stat"],
            "procStatAfterStdout": stat,
            "procStatBeforeCommand": ["cat", f"/proc/{pid}/stat"],
            "procStatBeforeStdout": stat,
            "processStartTicks": ticks,
            "serial": self.serial,
            "stdout": f"{pid}\n",
        }

    def _receipt(self, command: list[str], exit_code: int) -> dict[str, object]:
        return {
            "command": command,
            "exitCode": exit_code,
            "serial": self.serial,
            "stderr": "",
            "stdout": "",
        }

    def _write_ui(self, relative: str, nodes: list[tuple[str, str]]) -> None:
        body = "".join(
            f'<node package="{package}" text="{text}" bounds="[10,10][900,100]"/>'
            for package, text in nodes
        )
        (self.result_directory / relative).write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><hierarchy>{body}</hierarchy>',
            encoding="utf-8",
        )

    def _write_evidence_fixture(self) -> None:
        for relative in checker.EVIDENCE_PATHS:
            path = self.result_directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture evidence\n")

        for relative in (
            "installed-base-before.apk",
            "installed-base-after-reboot.apk",
        ):
            (self.result_directory / relative).write_bytes(self.apk_path.read_bytes())
        (self.result_directory / "avd-config.ini").write_bytes(
            checker.avd_config_bytes(self.avd_name)
        )
        (self.result_directory / "launch-argv.json").write_bytes(
            self._json_bytes(
                [
                    str(self.sdk_root / "emulator/emulator"),
                    "-avd",
                    self.avd_name,
                    "-port",
                    "5554",
                    *v1.LAUNCH_FLAGS,
                ]
            )
        )

        for relative in (
            "camera-request-state-before.xml",
            "camera-request-state-after-doze.xml",
            "camera-request-state-after-kill.xml",
            "camera-request-state-after-reboot.xml",
        ):
            (self.result_directory / relative).write_bytes(self.preference_bytes)
        permission = (
            b"Package [com.localagentbridge.android]\n"
            b"    android.permission.CAMERA: granted=false, flags=[ USER_SET|USER_FIXED ]\n"
        )
        for relative in (
            "camera-permission-before.txt",
            "camera-permission-after-reboot.txt",
        ):
            (self.result_directory / relative).write_bytes(permission)

        (self.result_directory / "boot-id-before.txt").write_text(
            self.boot_before + "\n", encoding="ascii"
        )
        (self.result_directory / "boot-id-after.txt").write_text(
            self.boot_after + "\n", encoding="ascii"
        )
        (self.result_directory / "boot-completed-after-reboot.txt").write_bytes(b"1\n")
        (self.result_directory / "deviceidle-state-forced.txt").write_text(
            "DeviceIdleController state:\n  mState=IDLE\n", encoding="utf-8"
        )
        (self.result_directory / "deviceidle-state-unforced.txt").write_text(
            "DeviceIdleController state:\n  mState=ACTIVE\n", encoding="utf-8"
        )
        (self.result_directory / "deviceidle-force-idle.txt").write_text(
            "Now forced in to deep idle mode\n", encoding="utf-8"
        )
        (self.result_directory / "deviceidle-unforce.txt").write_text(
            "Light state: ACTIVE, deep state: ACTIVE\n", encoding="utf-8"
        )
        component = f"{checker.PACKAGE_NAME}/.MainActivity"
        (self.result_directory / "activity-background-before-doze.txt").write_text(
            "topResumedActivity=ActivityRecord{system/.Launcher}\n", encoding="utf-8"
        )
        (self.result_directory / "activity-background-before-kill.txt").write_text(
            "topResumedActivity=ActivityRecord{system/.Launcher}\n", encoding="utf-8"
        )
        (self.result_directory / "activity-after-doze.txt").write_text(
            f"topResumedActivity=ActivityRecord{{abc {component} t1}}\n", encoding="utf-8"
        )

        locale = b"Locales for com.localagentbridge.android: []\n"
        for relative in ("app-locales-before.txt", "app-locales-after-reboot.txt"):
            (self.result_directory / relative).write_bytes(locale)
        for relative in ("font-scale-before.txt", "font-scale-after-reboot.txt"):
            (self.result_directory / relative).write_bytes(b"2.0\n")
        package_path = b"package:/data/app/fixture/base.apk\n"
        for relative in ("package-path-before.txt", "package-path-after-reboot.txt"):
            (self.result_directory / relative).write_bytes(package_path)

        receipts = {
            "process-kill-receipt.json": self._receipt(
                [
                    "run-as",
                    checker.PACKAGE_NAME,
                    "kill",
                    "-9",
                    str(self.processes["before_kill"][1]),
                ],
                0,
            ),
            "pidof-absence-receipt.json": self._receipt(
                ["pidof", checker.PACKAGE_NAME], 1
            ),
            "adb-reboot-receipt.json": self._receipt(["reboot"], 0),
        }
        for relative, value in receipts.items():
            (self.result_directory / relative).write_bytes(self._json_bytes(value))
        transport = [
            {
                "command": ["get-state"],
                "elapsedMilliseconds": 1,
                "exitCode": 0,
                "observedState": "device",
                "phase": "before_reboot",
                "serial": self.serial,
                "stderr": "",
                "stdout": "device\n",
            },
            {
                "command": ["get-state"],
                "elapsedMilliseconds": 2,
                "exitCode": 1,
                "observedState": "absent",
                "phase": "disconnected",
                "serial": self.serial,
                "stderr": "error: device offline\n",
                "stdout": "",
            },
            {
                "command": ["get-state"],
                "elapsedMilliseconds": 3,
                "exitCode": 0,
                "observedState": "device",
                "phase": "reconnected",
                "serial": self.serial,
                "stderr": "",
                "stdout": "device\n",
            },
            {
                "command": ["getprop", "sys.boot_completed"],
                "elapsedMilliseconds": 4,
                "exitCode": 0,
                "observedState": "1",
                "phase": "boot_completed",
                "serial": self.serial,
                "stderr": "",
                "stdout": "1\n",
            },
        ]
        (self.result_directory / "reboot-transport-observations.json").write_bytes(
            self._json_bytes(transport)
        )
        for relative in (
            "owned-emulator-before-reboot.json",
            "owned-emulator-after-reboot.json",
        ):
            (self.result_directory / relative).write_bytes(
                self._json_bytes(self.owned_emulator)
            )
        (self.result_directory / "app-process-observations.json").write_bytes(
            self._json_bytes(
                [self._process_record(label) for label in checker.PROCESS_OBSERVATION_LABELS]
            )
        )

        for relative in ("network-state-before.txt", "network-state-after-reboot.txt"):
            (self.result_directory / relative).write_text(
                "No active network agents\n", encoding="utf-8"
            )
        for relative in ("app-networking-before.txt", "app-networking-after-reboot.txt"):
            (self.result_directory / relative).write_text(
                v1.APP_NETWORKING_DENIED_STATE + "\n", encoding="ascii"
            )
        for relative in ("guest-airplane-before.txt", "guest-airplane-after-reboot.txt"):
            (self.result_directory / relative).write_text("enabled\n", encoding="ascii")
        for relative in ("logcat-before-reboot.txt", "logcat-after-reboot.txt"):
            (self.result_directory / relative).write_text(
                "08-01 00:00:00.000 I/AetherLink: benign lifecycle event\n",
                encoding="utf-8",
            )
        for relative in ("exit-info-before-reboot.txt", "exit-info-after-reboot.txt"):
            (self.result_directory / relative).write_text(
                "process=com.localagentbridge.android reason=10 (USER REQUESTED)\n",
                encoding="utf-8",
            )

        devices = (
            "List of devices attached\n"
            "emulator-5580 device product:fixture model:fixture\n"
        )
        for relative in ("pre-adb-devices.txt", "post-adb-devices.txt"):
            (self.result_directory / relative).write_text(devices, encoding="utf-8")
        for relative in ("pre-emulator-processes.json", "post-emulator-processes.json"):
            (self.result_directory / relative).write_bytes(
                self._json_bytes(self.preexisting_emulators)
            )

        app = checker.PACKAGE_NAME
        for relative in (
            "ui/setup-first-launch.xml",
            "ui/background-before-doze.xml",
            "ui/background-after-doze.xml",
            "ui/after-process-kill.xml",
            "ui/after-reboot.xml",
        ):
            self._write_ui(relative, [(app, "Pair AetherLink")])
        for relative in (
            "ui/setup-camera-settings-recovery.xml",
            "ui/after-reboot-camera-settings-recovery.xml",
        ):
            self._write_ui(
                relative,
                [(app, "Camera permission is blocked"), (app, "Open app settings")],
            )
        self._write_ui("ui/setup-camera-denied.xml", [(app, "Camera access is needed")])
        self._write_ui(
            "ui/setup-camera-permission-dialog.xml",
            [("com.google.android.permissioncontroller", "Don’t allow")],
        )

    @staticmethod
    def _record(raw: bytes) -> dict[str, object]:
        return {
            "lineCount": len(raw.splitlines()),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _scenario(self, name: str, checks: tuple[str, ...]) -> dict[str, object]:
        preference_sha = hashlib.sha256(self.preference_bytes).hexdigest()
        if name == "background_doze_recovery":
            observations = {
                "bootId": self.boot_before,
                "cameraRequestStateSha256": preference_sha,
                "processIds": [101, 101],
            }
        elif name == "background_process_kill_recovery":
            observations = {
                "bootId": self.boot_before,
                "cameraRequestStateSha256": preference_sha,
                "processIds": [102, 103],
            }
        else:
            observations = {
                "bootIds": [self.boot_before, self.boot_after],
                "cameraPermissionGranted": False,
                "cameraRequestStateSha256": preference_sha,
                "fontScale": "2.0",
                "installedApkSha256": hashlib.sha256(self.apk_path.read_bytes()).hexdigest(),
                "localeTags": [],
                "processIdAfterReboot": 104,
            }
        return {
            "checks": {check: True for check in checks},
            "evidence": list(checker.SCENARIO_EVIDENCE[name]),
            "name": name,
            "observations": observations,
            "status": "passed",
        }

    def _phase_record(self, relative: str, match_key: str) -> dict[str, object]:
        raw = (self.result_directory / relative).read_bytes()
        record = self._record(raw)
        record[match_key] = []
        return record

    def _network_value_record(self, relative: str, value: str) -> dict[str, object]:
        raw = (self.result_directory / relative).read_bytes()
        record = self._record(raw)
        record["value"] = value
        return record

    def _valid_payload(self) -> dict[str, object]:
        built = checker.file_record(
            self.apk_path, relative=v1.DEBUG_APK_RELATIVE.as_posix()
        )
        before = checker.file_record(
            self.result_directory / "installed-base-before.apk",
            relative="installed-base-before.apk",
        )
        after = checker.file_record(
            self.result_directory / "installed-base-after-reboot.apk",
            relative="installed-base-after-reboot.apk",
        )
        network_before = self._record(
            (self.result_directory / "network-state-before.txt").read_bytes()
        )
        network_before["validatedInternetMatches"] = []
        network_after = self._record(
            (self.result_directory / "network-state-after-reboot.txt").read_bytes()
        )
        network_after["validatedInternetMatches"] = []
        return {
            "artifact": {
                "built": built,
                "exactByteMatch": True,
                "installedAfterReboot": after,
                "installedBefore": before,
            },
            "build": {
                "command": list(v1.BUILD_COMMAND),
                "dependencyMode": "offline",
                "exitCode": 0,
            },
            "cleanup": {
                "ownedProcessExited": True,
                "ownedSerialAbsent": True,
                "postHostEmulators": copy.deepcopy(self.preexisting_emulators),
                "postSerials": ["emulator-5580"],
                "preexistingHostEmulators": copy.deepcopy(self.preexisting_emulators),
                "preexistingSerials": ["emulator-5580"],
                "preexistingSerialsPreserved": True,
            },
            "contract": checker.CONTRACT,
            "device": {
                "abi": "arm64-v8a",
                "activity": v1.ACTIVITY_NAME,
                "apiLevel": 36,
                "appNetworkingDenied": True,
                "avdEphemeral": True,
                "guestAirplaneModeEnabled": True,
                "launchFlags": list(v1.LAUNCH_FLAGS),
                "model": "fixture-pixel",
                "package": checker.PACKAGE_NAME,
                "release": "16",
                "screenDensity": 420,
                "screenHeight": 2400,
                "screenWidth": 1080,
                "systemImagePackage": v1.SYSTEM_IMAGE_PACKAGE,
            },
            "evidence": checker.evidence_manifest(self.result_directory),
            "exitInfo": {
                "afterReboot": self._phase_record(
                    "exit-info-after-reboot.txt", "forbiddenMatches"
                ),
                "beforeReboot": self._phase_record(
                    "exit-info-before-reboot.txt", "forbiddenMatches"
                ),
            },
            "logcat": {
                "afterReboot": self._phase_record(
                    "logcat-after-reboot.txt", "fatalOrAnrMatches"
                ),
                "beforeReboot": self._phase_record(
                    "logcat-before-reboot.txt", "fatalOrAnrMatches"
                ),
            },
            "networkIsolation": {
                "afterReboot": network_after,
                "appNetworkingAfterReboot": self._network_value_record(
                    "app-networking-after-reboot.txt", v1.APP_NETWORKING_DENIED_STATE
                ),
                "appNetworkingBefore": self._network_value_record(
                    "app-networking-before.txt", v1.APP_NETWORKING_DENIED_STATE
                ),
                "before": network_before,
                "guestAirplaneModeAfterReboot": self._network_value_record(
                    "guest-airplane-after-reboot.txt", "enabled"
                ),
                "guestAirplaneModeBefore": self._network_value_record(
                    "guest-airplane-before.txt", "enabled"
                ),
            },
            "nonClaims": list(checker.NON_CLAIMS),
            "run": {
                "durationSeconds": 10.0,
                "emulatorPort": 5554,
                "finishedAt": "2026-08-01T00:00:10.000Z",
                "hostArchitecture": "arm64",
                "hostPlatform": "darwin",
                "id": self.result_directory.name,
                "serial": self.serial,
                "startedAt": "2026-08-01T00:00:00.000Z",
            },
            "scenarios": [
                self._scenario(name, checks) for name, checks in checker.SCENARIO_CHECKS
            ],
            "schemaVersion": checker.SCHEMA_VERSION,
            "source": copy.deepcopy(self.source_snapshot),
            "status": "passed",
            "toolchain": {
                "adb": checker.sdk_tool_identity(self.sdk_root, Path("platform-tools/adb")),
                "adbVersion": "Android Debug Bridge fixture",
                "emulator": checker.sdk_tool_identity(
                    self.sdk_root, Path("emulator/emulator")
                ),
                "emulatorVersion": "Android emulator fixture",
                "java": checker.java_tool_identity(self.java_home),
                "javaHome": str(self.java_home.resolve()),
                "javaVersion": "openjdk fixture",
                "qemuHeadless": checker.sdk_tool_identity(
                    self.sdk_root,
                    Path("emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"),
                ),
                "systemImage": copy.deepcopy(self.system_image_snapshot),
            },
        }

    def _write_result(self) -> None:
        self.result_path.write_bytes(self._json_bytes(self.payload))

    def _refresh_evidence(self) -> None:
        self.payload["evidence"] = checker.evidence_manifest(self.result_directory)

    def _failures(self, *, rewrite: bool = True) -> list[str]:
        if rewrite:
            self._write_result()
        with (
            patch.object(
                checker, "source_snapshot", return_value=copy.deepcopy(self.source_snapshot)
            ),
            patch.object(
                checker,
                "system_image_snapshot",
                return_value=copy.deepcopy(self.system_image_snapshot),
            ),
        ):
            return checker.result_failures(
                self.result_path,
                root=self.root,
                sdk_root=self.sdk_root,
                java_home=self.java_home,
            )

    def _mutate_json_file(self, relative: str, mutate) -> None:
        path = self.result_directory / relative
        value = json.loads(path.read_bytes())
        mutate(value)
        path.write_bytes(self._json_bytes(value))
        self._refresh_evidence()

    def assertRejected(self, failures: list[str], needle: str) -> None:  # noqa: N802
        self.assertTrue(failures, "mutation unexpectedly passed")
        self.assertTrue(
            any(needle in failure for failure in failures),
            f"expected {needle!r} in {failures!r}",
        )

    def test_valid_synthetic_evidence_passes_payload_and_result_readback(self) -> None:
        with (
            patch.object(
                checker, "source_snapshot", return_value=copy.deepcopy(self.source_snapshot)
            ),
            patch.object(
                checker,
                "system_image_snapshot",
                return_value=copy.deepcopy(self.system_image_snapshot),
            ),
            checker.EvidenceSnapshot(self.result_path) as snapshot,
        ):
            evidence = snapshot.capture()
            self.assertEqual(
                checker.payload_failures(
                    self.payload,
                    result_directory=self.result_directory,
                    evidence=evidence,
                    root=self.root,
                    sdk_root=self.sdk_root,
                    java_home=self.java_home,
                ),
                [],
            )
            snapshot.verify_unchanged()
        self.assertEqual(self._failures(), [])

    def test_duplicate_and_noncanonical_json_are_rejected(self) -> None:
        canonical = self._json_bytes(self.payload)
        with self.subTest("duplicate-key"):
            self.result_path.write_bytes(
                canonical.replace(
                    b'"status":"passed"',
                    b'"status":"passed","status":"passed"',
                    1,
                )
            )
            self.assertRejected(self._failures(rewrite=False), "duplicate JSON key")
        with self.subTest("noncanonical-bytes"):
            self.result_path.write_bytes(canonical + b" ")
            self.assertRejected(self._failures(rewrite=False), "canonical JSON bytes")

    def test_bool_as_integer_is_rejected(self) -> None:
        self.payload["schemaVersion"] = True
        self.assertRejected(self._failures(), "schemaVersion must equal integer")

    def test_preferences_byte_and_state_drift_are_rejected(self) -> None:
        path = self.result_directory / "camera-request-state-after-doze.xml"
        with self.subTest("byte-drift"):
            path.write_bytes(self.preference_bytes + b"\n")
            self._refresh_evidence()
            self.assertRejected(self._failures(), "preference bytes must remain exact")
        path.write_bytes(self.preference_bytes)
        with self.subTest("state-drift"):
            path.write_bytes(self.preference_bytes.replace(b"recorded", b"unrequested"))
            self._refresh_evidence()
            self.assertRejected(self._failures(), "request_state=recorded")

    def test_doze_mstate_mutation_is_rejected(self) -> None:
        (self.result_directory / "deviceidle-state-forced.txt").write_text(
            "DeviceIdleController state:\n  mState=ACTIVE\n", encoding="utf-8"
        )
        self._refresh_evidence()
        self.assertRejected(self._failures(), "deep mState=IDLE")

    def test_process_kill_and_pidof_receipt_mutations_are_rejected(self) -> None:
        with self.subTest("process-kill"):
            self._mutate_json_file(
                "process-kill-receipt.json",
                lambda value: value.__setitem__("exitCode", 1),
            )
            self.assertRejected(self._failures(), "exitCode must equal integer 0")
        (self.result_directory / "process-kill-receipt.json").write_bytes(
            self._json_bytes(
                self._receipt(
                    [
                        "run-as",
                        checker.PACKAGE_NAME,
                        "kill",
                        "-9",
                        str(self.processes["before_kill"][1]),
                    ],
                    0,
                )
            )
        )
        with self.subTest("pidof-absence"):
            self._mutate_json_file(
                "pidof-absence-receipt.json",
                lambda value: value.__setitem__("stdout", "103\n"),
            )
            self.assertRejected(self._failures(), "empty stdout and stderr")

    def test_process_raw_identity_mutation_is_rejected(self) -> None:
        def mutate(value: list[dict[str, object]]) -> None:
            value[1]["procStatAfterStdout"] = str(value[1]["procStatAfterStdout"]).replace(
                "50101", "60101"
            )

        self._mutate_json_file("app-process-observations.json", mutate)
        self.assertRejected(self._failures(), "one exact process start identity")

    def test_process_kill_boot_id_must_bind_raw_pre_reboot_boot_id(self) -> None:
        unrelated_boot_id = "fedcba98-7654-4321-8abc-0123456789ab"

        def mutate(value: list[dict[str, object]]) -> None:
            by_label = {record["label"]: record for record in value}
            by_label["before_kill"]["bootId"] = unrelated_boot_id
            by_label["after_kill"]["bootId"] = unrelated_boot_id

        self._mutate_json_file("app-process-observations.json", mutate)
        self.payload["scenarios"][1]["observations"]["bootId"] = unrelated_boot_id
        self.assertRejected(self._failures(), "process-kill")

    def test_doze_boot_id_must_bind_raw_pre_reboot_boot_id(self) -> None:
        unrelated_boot_id = "fedcba98-7654-4321-8abc-0123456789ab"

        def mutate(value: list[dict[str, object]]) -> None:
            by_label = {record["label"]: record for record in value}
            by_label["before_doze"]["bootId"] = unrelated_boot_id
            by_label["after_doze"]["bootId"] = unrelated_boot_id

        self._mutate_json_file("app-process-observations.json", mutate)
        self.payload["scenarios"][0]["observations"]["bootId"] = unrelated_boot_id
        self.assertRejected(self._failures(), "Doze process identity")

    def test_nonclaims_keep_spontaneous_os_process_kill_out_of_scope(self) -> None:
        self.assertIn("os-process-kill", checker.NON_CLAIMS)
        self.assertNotIn("background-or-doze", checker.NON_CLAIMS)
        self.assertNotIn("device-reboot", checker.NON_CLAIMS)

    def test_run_id_must_equal_result_directory_basename(self) -> None:
        self.payload["run"]["id"] = (
            "android-headless-api36-1-v2-20260801T000001Z-feedface"
        )
        self.assertRejected(self._failures(), "result directory")

    def test_boot_id_equality_is_rejected(self) -> None:
        (self.result_directory / "boot-id-after.txt").write_text(
            self.boot_before + "\n", encoding="ascii"
        )
        self._refresh_evidence()
        self.assertRejected(self._failures(), "kernel boot_id must change")

    def test_reboot_order_mutation_is_rejected(self) -> None:
        def mutate(value: list[dict[str, object]]) -> None:
            value[1]["phase"] = "reconnected"

        self._mutate_json_file("reboot-transport-observations.json", mutate)
        self.assertRejected(self._failures(), "exact reboot order")

    def test_owned_qemu_identity_drift_is_rejected(self) -> None:
        self._mutate_json_file(
            "owned-emulator-after-reboot.json",
            lambda value: value.__setitem__("pid", 78793),
        )
        self.assertRejected(self._failures(), "owned QEMU host identity")

    def test_installed_apk_mismatch_is_rejected(self) -> None:
        (self.result_directory / "installed-base-after-reboot.apk").write_bytes(
            b"replaced-after-reboot-apk\n"
        )
        self._refresh_evidence()
        self.assertRejected(self._failures(), "APK bytes must match exactly")

    def test_validated_network_line_is_rejected(self) -> None:
        (self.result_directory / "network-state-after-reboot.txt").write_text(
            "NetworkAgentInfo{network{42} INTERNET VALIDATED factorySerialNumber=1}\n",
            encoding="utf-8",
        )
        self._refresh_evidence()
        self.assertRejected(self._failures(), "validated Internet network")

    def test_ui_settings_recovery_mutation_is_rejected(self) -> None:
        self._write_ui(
            "ui/after-reboot-camera-settings-recovery.xml",
            [(checker.PACKAGE_NAME, "Camera permission is blocked")],
        )
        self._refresh_evidence()
        self.assertRejected(self._failures(), "Open app settings")

    def test_closed_evidence_rejects_an_extra_file(self) -> None:
        (self.result_directory / "unexpected.txt").write_text("not contracted\n")
        self.assertRejected(self._failures(), "evidence file set must be closed")

    def test_same_byte_path_replacement_after_capture_is_rejected(self) -> None:
        target = self.result_directory / "boot-id-before.txt"
        original_manifest = checker.evidence_manifest_from_snapshot
        replaced = False

        def replace_after_manifest(evidence):
            nonlocal replaced
            manifest = original_manifest(evidence)
            if not replaced:
                replacement = self.result_directory / "replacement.tmp"
                replacement.write_bytes(target.read_bytes())
                replacement.chmod(target.stat().st_mode & 0o777)
                os.replace(replacement, target)
                replaced = True
            return manifest

        with patch.object(
            checker,
            "evidence_manifest_from_snapshot",
            side_effect=replace_after_manifest,
        ):
            self.assertRejected(
                self._failures(), "final evidence graph verification failed"
            )

    def test_aba_path_replacement_and_restore_is_rejected(self) -> None:
        target = self.result_directory / "boot-id-before.txt"
        held = self.result_directory.parent / "boot-id-held.txt"
        replacement = self.result_directory.parent / "boot-id-replacement.txt"
        replacement.write_bytes(b"00000000-0000-4000-8000-000000000000\n")
        original_manifest = checker.evidence_manifest_from_snapshot
        replaced = False

        def replace_and_restore(evidence):
            nonlocal replaced
            manifest = original_manifest(evidence)
            if not replaced:
                target.rename(held)
                replacement.rename(target)
                target.unlink()
                held.rename(target)
                replaced = True
            return manifest

        with patch.object(
            checker,
            "evidence_manifest_from_snapshot",
            side_effect=replace_and_restore,
        ):
            self.assertRejected(
                self._failures(), "final evidence graph verification failed"
            )

    def test_evidence_file_symlink_is_rejected(self) -> None:
        target = self.result_directory / "boot-id-before.txt"
        physical = self.result_directory.parent / "boot-id-physical.txt"
        target.rename(physical)
        target.symlink_to(physical)
        self.assertRejected(
            self._failures(), "cannot open evidence file without following links"
        )

    def test_evidence_directory_symlink_is_rejected(self) -> None:
        physical = self.result_directory.parent / "ui-physical"
        (self.result_directory / "ui").rename(physical)
        (self.result_directory / "ui").symlink_to(physical, target_is_directory=True)
        self.assertRejected(
            self._failures(), "cannot open evidence directory without following links"
        )

    def test_evidence_hardlink_is_rejected(self) -> None:
        target = self.result_directory / "boot-id-before.txt"
        os.link(target, self.result_directory.parent / "boot-id-hardlink.txt")
        self.assertRejected(self._failures(), "evidence file identity differs")

    def test_result_directory_replacement_during_validation_is_rejected(self) -> None:
        original_manifest = checker.evidence_manifest_from_snapshot
        moved = self.result_directory.with_name(self.result_directory.name + "-held")
        replaced = False

        def replace_result_directory(evidence):
            nonlocal replaced
            manifest = original_manifest(evidence)
            if not replaced:
                self.result_directory.rename(moved)
                self.result_directory.symlink_to(moved, target_is_directory=True)
                replaced = True
            return manifest

        with patch.object(
            checker,
            "evidence_manifest_from_snapshot",
            side_effect=replace_result_directory,
        ):
            self.assertRejected(
                self._failures(), "final evidence graph verification failed"
            )

    def test_cleanup_rejects_unverifiable_temporary_avd_removal_claim(self) -> None:
        self.payload["cleanup"]["temporaryAvdRemoved"] = True
        self.assertRejected(self._failures(), "cleanup keys must be exactly")


if __name__ == "__main__":
    unittest.main()
