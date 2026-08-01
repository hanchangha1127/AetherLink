#!/usr/bin/env python3
"""Mutation tests for Android headless lifecycle evidence readback."""

from __future__ import annotations

from contextlib import contextmanager
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script import check_android_headless_emulator_product_lifecycle as checker


class HeadlessLifecycleEvidenceCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary.name)
        self.root = temporary_root / "source"
        self.sdk_root = temporary_root / "sdk"
        self.java_home = temporary_root / "java-home"
        self.result_directory = temporary_root / (
            "android-headless-api36-1-20260801T000000Z-deadbeef"
        )
        self.result_directory.mkdir(parents=True)
        (self.result_directory / "ui").mkdir()

        self.apk_path = self.root / checker.DEBUG_APK_RELATIVE
        self.apk_path.parent.mkdir(parents=True)
        self.apk_path.write_bytes(b"fixture-debug-apk\n")

        for relative, payload in (
            (Path("platform-tools/adb"), b"fixture-adb\n"),
            (Path("emulator/emulator"), b"fixture-emulator\n"),
            (
                Path("emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"),
                b"fixture-qemu\n",
            ),
        ):
            path = self.sdk_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            path.chmod(0o755)
        java = self.java_home / "bin/java"
        java.parent.mkdir(parents=True)
        java.write_bytes(b"fixture-java\n")
        java.chmod(0o755)

        self.avd_name = "AetherLink_API_36_1_5554_0123abcd"
        self.host_emulators = [
            {
                "commandSha256": "5" * 64,
                "pid": 78792,
                "port": 5580,
                "processStartedAt": "Fri Jul 31 15:56:45 2026",
                "serial": "emulator-5580",
            }
        ]
        self.process_observation_pids = {
            "clean_install_and_first_launch": 1001,
            "force_stop_cold_launch_repetition:2": 1002,
            "force_stop_cold_launch_repetition:3": 1003,
            "platform_locale_en": 1102,
            "platform_locale_ko": 1103,
            "platform_locale_ja": 1104,
            "platform_locale_zh_cn": 1105,
            "platform_locale_fr": 1106,
            "in_app_korean_language": 1200,
            "in_app_follow_system_language": 1201,
            "camera_permission_denial_and_cold_launch:before": 1300,
            "camera_permission_denial_and_cold_launch:after": 1301,
        }
        self._write_evidence_fixture()
        self.source_snapshot = {
            "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
            "fileCount": 1,
            "files": [
                {
                    "mode": "0644",
                    "path": "fixture",
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
            "package": checker.SYSTEM_IMAGE_PACKAGE,
            "sha256": "4" * 64,
        }
        self.payload = self._valid_payload()
        self.result_path = self.result_directory / "result.json"
        self._write_result()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _process_observation_record(self, label: str) -> dict[str, object]:
        pid = self.process_observation_pids[label]
        start_ticks = 50_000 + pid
        cmdline = checker.PACKAGE_NAME.encode("ascii") + (b"\0" * 8)
        stat = (
            f"{pid} (tbridge.android) S "
            + " ".join(["0"] * 18)
            + f" {start_ticks} 0 0\n"
        )
        return {
            "command": ["pidof", checker.PACKAGE_NAME],
            "label": label,
            "procCmdlineBase64": base64.b64encode(cmdline).decode("ascii"),
            "procCmdlineCommand": ["cat", f"/proc/{pid}/cmdline"],
            "procStatAfterCommand": ["cat", f"/proc/{pid}/stat"],
            "procStatAfterStdout": stat,
            "procStatBeforeCommand": ["cat", f"/proc/{pid}/stat"],
            "procStatBeforeStdout": stat,
            "processStartTicks": start_ticks,
            "serial": "emulator-5554",
            "stdout": f"{pid}\n",
        }

    def _write_evidence_fixture(self) -> None:
        ui = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<hierarchy><node package="fixture" text="fixture" '
            b'bounds="[0,0][1,1]"/></hierarchy>'
        )
        for relative in checker.EVIDENCE_PATHS:
            path = self.result_directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative == "installed-base.apk":
                path.write_bytes(self.apk_path.read_bytes())
            elif relative == "avd-config.ini":
                path.write_bytes(checker.avd_config_bytes(self.avd_name))
            elif relative == "launch-argv.json":
                path.write_bytes(
                    checker.canonical_json_bytes(
                        [
                            str(self.sdk_root / "emulator/emulator"),
                            "-avd",
                            self.avd_name,
                            "-port",
                            "5554",
                            *checker.LAUNCH_FLAGS,
                        ]
                    )
                )
            elif relative == "pre-adb-devices.txt":
                path.write_text(
                    "List of devices attached\n"
                    "emulator-5580 device product:fixture model:fixture\n",
                    encoding="utf-8",
                )
            elif relative == "post-adb-devices.txt":
                path.write_text(
                    "List of devices attached\n"
                    "emulator-5580 device product:fixture model:fixture\n",
                    encoding="utf-8",
                )
            elif relative in (
                "pre-emulator-processes.json",
                "post-emulator-processes.json",
            ):
                path.write_bytes(checker.canonical_json_bytes(self.host_emulators))
            elif relative == "app-process-observations.json":
                path.write_bytes(
                    checker.canonical_json_bytes(
                        [
                            self._process_observation_record(label)
                            for label in checker.PROCESS_OBSERVATION_LABELS
                        ]
                    )
                )
            elif relative.startswith("app-networking-"):
                path.write_text(
                    checker.APP_NETWORKING_DENIED_STATE + "\n",
                    encoding="ascii",
                )
            elif relative.startswith("guest-airplane-mode-"):
                path.write_text("enabled\n", encoding="ascii")
            elif relative.startswith("camera-permission-"):
                expected = dict(checker.CAMERA_PERMISSION_EVIDENCE)[relative]
                state = "true" if expected else "false"
                path.write_text(
                    "Package [com.localagentbridge.android]\n"
                    f"    android.permission.CAMERA: granted={state}, "
                    "flags=[ USER_SET ]\n",
                    encoding="utf-8",
                )
            elif relative == "logcat.txt":
                path.write_text("benign AetherLink log line\n", encoding="utf-8")
            elif relative == "exit-info.txt":
                path.write_text(
                    "process=com.localagentbridge.android "
                    "reason=10 (USER REQUESTED)\n",
                    encoding="utf-8",
                )
            elif relative.startswith("network-state-"):
                path.write_text("no active network\n", encoding="utf-8")
            elif relative.startswith("ui/"):
                path.write_bytes(ui)
            else:
                path.write_text("fixture evidence\n", encoding="utf-8")

    def _valid_payload(self) -> dict[str, object]:
        installed = checker.file_record(
            self.result_directory / "installed-base.apk",
            relative="installed-base.apk",
        )
        built = checker.file_record(
            self.apk_path,
            relative=checker.DEBUG_APK_RELATIVE.as_posix(),
        )
        logcat = (self.result_directory / "logcat.txt").read_bytes()
        exit_info = (self.result_directory / "exit-info.txt").read_bytes()
        network_before = (self.result_directory / "network-state-before.txt").read_bytes()
        network_after = (self.result_directory / "network-state-after.txt").read_bytes()
        app_networking_after_deny = (
            self.result_directory / "app-networking-after-deny.txt"
        ).read_bytes()
        app_networking_after_lifecycle = (
            self.result_directory / "app-networking-after-lifecycle.txt"
        ).read_bytes()
        guest_airplane_before = (
            self.result_directory / "guest-airplane-mode-before.txt"
        ).read_bytes()
        guest_airplane_after = (
            self.result_directory / "guest-airplane-mode-after.txt"
        ).read_bytes()
        return {
            "artifact": {
                "built": built,
                "exactByteMatch": True,
                "installed": installed,
            },
            "build": {
                "command": list(checker.BUILD_COMMAND),
                "dependencyMode": "offline",
                "exitCode": 0,
            },
            "cleanup": {
                "ownedProcessExited": True,
                "ownedSerialAbsent": True,
                "postHostEmulators": copy.deepcopy(self.host_emulators),
                "postSerials": ["emulator-5580"],
                "preexistingHostEmulators": copy.deepcopy(self.host_emulators),
                "preexistingSerials": ["emulator-5580"],
                "preexistingSerialsPreserved": True,
                "temporaryAvdRemoved": True,
            },
            "contract": checker.CONTRACT,
            "device": {
                "abi": "arm64-v8a",
                "activity": checker.ACTIVITY_NAME,
                "apiLevel": 36,
                "appNetworkingDenied": True,
                "avdEphemeral": True,
                "guestAirplaneModeEnabled": True,
                "launchFlags": list(checker.LAUNCH_FLAGS),
                "model": "fixture-pixel",
                "package": checker.PACKAGE_NAME,
                "release": "16",
                "screenDensity": 420,
                "screenHeight": 2400,
                "screenWidth": 1080,
                "systemImagePackage": checker.SYSTEM_IMAGE_PACKAGE,
            },
            "evidence": checker.evidence_manifest(self.result_directory),
            "exitInfo": {
                "forbiddenMatches": [],
                "lineCount": len(exit_info.splitlines()),
                "sha256": hashlib.sha256(exit_info).hexdigest(),
            },
            "logcat": {
                "fatalOrAnrMatches": [],
                "lineCount": len(logcat.splitlines()),
                "sha256": hashlib.sha256(logcat).hexdigest(),
            },
            "networkIsolation": {
                "after": {
                    "lineCount": len(network_after.splitlines()),
                    "sha256": hashlib.sha256(network_after).hexdigest(),
                    "validatedInternetMatches": [],
                },
                "appNetworkingAfterDeny": {
                    "lineCount": len(app_networking_after_deny.splitlines()),
                    "sha256": hashlib.sha256(
                        app_networking_after_deny
                    ).hexdigest(),
                    "value": checker.APP_NETWORKING_DENIED_STATE,
                },
                "appNetworkingAfterLifecycle": {
                    "lineCount": len(app_networking_after_lifecycle.splitlines()),
                    "sha256": hashlib.sha256(
                        app_networking_after_lifecycle
                    ).hexdigest(),
                    "value": checker.APP_NETWORKING_DENIED_STATE,
                },
                "before": {
                    "lineCount": len(network_before.splitlines()),
                    "sha256": hashlib.sha256(network_before).hexdigest(),
                    "validatedInternetMatches": [],
                },
                "guestAirplaneModeAfter": {
                    "lineCount": len(guest_airplane_after.splitlines()),
                    "sha256": hashlib.sha256(guest_airplane_after).hexdigest(),
                    "value": "enabled",
                },
                "guestAirplaneModeBefore": {
                    "lineCount": len(guest_airplane_before.splitlines()),
                    "sha256": hashlib.sha256(guest_airplane_before).hexdigest(),
                    "value": "enabled",
                },
            },
            "nonClaims": list(checker.NON_CLAIMS),
            "run": {
                "durationSeconds": 10.0,
                "emulatorPort": 5554,
                "finishedAt": "2026-08-01T00:00:10.000Z",
                "hostArchitecture": "arm64",
                "hostPlatform": "darwin",
                "id": self.result_directory.name,
                "serial": "emulator-5554",
                "startedAt": "2026-08-01T00:00:00.000Z",
            },
            "scenarios": [
                {
                    "checks": {check: True for check in checks},
                    "evidence": checker.SCENARIO_EVIDENCE[name],
                    "name": name,
                    "observations": self._scenario_observations(name, index),
                    "status": "passed",
                }
                for index, (name, checks) in enumerate(checker.SCENARIO_CHECKS)
            ],
            "schemaVersion": checker.SCHEMA_VERSION,
            "source": copy.deepcopy(self.source_snapshot),
            "status": "passed",
            "toolchain": {
                "adb": checker.sdk_tool_identity(
                    self.sdk_root, Path("platform-tools/adb")
                ),
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
                    Path(
                        "emulator/qemu/darwin-aarch64/"
                        "qemu-system-aarch64-headless"
                    ),
                ),
                "systemImage": copy.deepcopy(self.system_image_snapshot),
            },
        }

    def _scenario_observations(
        self,
        name: str,
        index: int,
    ) -> dict[str, object]:
        if name == "clean_install_and_first_launch":
            return {
                "firstProcessId": self.process_observation_pids[name],
                "installedApkSha256": checker.file_record(
                    self.result_directory / "installed-base.apk",
                    relative="installed-base.apk",
                )["sha256"],
                "preexistingSerials": ["emulator-5580"],
                "serial": "emulator-5554",
            }
        if name == "force_stop_cold_launch_repetition":
            return {
                "processIds": [
                    self.process_observation_pids[
                        "clean_install_and_first_launch"
                    ],
                    self.process_observation_pids[
                        "force_stop_cold_launch_repetition:2"
                    ],
                    self.process_observation_pids[
                        "force_stop_cold_launch_repetition:3"
                    ],
                ],
                "rounds": 3,
            }
        for tag, title in checker.LOCALE_TITLES:
            if name == f"platform_locale_{tag.lower().replace('-', '_')}":
                return {
                    "fontScale": "2.0",
                    "localeTags": [tag],
                    "pairingTitle": title,
                    "processId": self.process_observation_pids[name],
                }
        if name == "in_app_korean_language":
            return {
                "localeTags": ["ko"],
                "pairingTitle": "AetherLink 페어링",
                "processId": self.process_observation_pids[name],
            }
        if name == "in_app_follow_system_language":
            return {
                "deviceLocale": "en-US",
                "localeTags": [],
                "pairingTitle": "Pair AetherLink",
                "processId": self.process_observation_pids[name],
            }
        if name == "camera_permission_denial_and_cold_launch":
            return {
                "cameraPermissionGranted": False,
                "manualRetryLabel": "Allow camera",
                "processIds": [
                    self.process_observation_pids[
                        "camera_permission_denial_and_cold_launch:before"
                    ],
                    self.process_observation_pids[
                        "camera_permission_denial_and_cold_launch:after"
                    ],
                ],
            }
        if name == "camera_permission_regrant":
            return {
                "cameraPermissionGranted": True,
                "scannerTitle": "Scan AetherLink QR",
            }
        if name == "camera_settings_recovery":
            return {
                "cameraPermissionGranted": False,
                "settingsPackage": "com.android.settings",
            }
        if name == "font_scale_200_core_reachability":
            return {
                "fontScale": "2.0",
                "reachableDestinations": ["New Chat", "Settings"],
                "screen": [1080, 2400, 420],
            }
        self.fail(f"missing observation fixture for {name}")
        return {}

    @contextmanager
    def _validation_scope(self):
        with (
            patch.object(
                checker,
                "source_snapshot",
                return_value=copy.deepcopy(self.source_snapshot),
            ),
            patch.object(
                checker,
                "system_image_snapshot",
                return_value=copy.deepcopy(self.system_image_snapshot),
            ),
            patch.object(checker, "ui_semantic_failures", return_value=[]),
        ):
            yield

    def _write_result(self, *, canonical: bool = True) -> None:
        raw = checker.canonical_json_bytes(self.payload)
        self.result_path.write_bytes(raw if canonical else raw + b" ")

    def _refresh_evidence(self) -> None:
        self.payload["evidence"] = checker.evidence_manifest(self.result_directory)

    def _failures(self) -> list[str]:
        self._write_result()
        with self._validation_scope():
            return checker.result_failures(
                self.result_path,
                root=self.root,
                sdk_root=self.sdk_root,
                java_home=self.java_home,
            )

    def test_valid_fixture_passes_independent_readback(self) -> None:
        self.assertEqual(self._failures(), [])

    def test_actionable_language_evidence_requires_full_viewport_containment(self) -> None:
        path = self.result_directory / "ui/in-app-korean-settings.xml"

        def write_row(bounds: str, *, checked: str = "false") -> None:
            path.write_text(
                '<hierarchy><node package="com.localagentbridge.android" '
                'scrollable="true" bounds="[53,276][1027,2295]">'
                '<node package="com.localagentbridge.android" clickable="true" '
                f'enabled="true" checkable="true" checked="{checked}" bounds="{bounds}">'
                '<node package="com.localagentbridge.android" text="한국어" '
                'enabled="true" bounds="[179,1805][985,1900]"/>'
                "</node></node></hierarchy>",
                encoding="utf-8",
            )

        write_row("[95,1794][985,1920]")
        self.assertEqual(
            checker.ui_actionable_token_failures(
                self.result_directory,
                relative="ui/in-app-korean-settings.xml",
                text="한국어",
                expected_checked="false",
            ),
            [],
        )
        write_row("[95,2253][985,2379]")
        self.assertTrue(
            checker.ui_actionable_token_failures(
                self.result_directory,
                relative="ui/in-app-korean-settings.xml",
                text="한국어",
                expected_checked="false",
            )
        )
        write_row("[95,1794][985,1920]", checked="true")
        self.assertTrue(
            checker.ui_actionable_token_failures(
                self.result_directory,
                relative="ui/in-app-korean-settings.xml",
                text="한국어",
                expected_checked="false",
            )
        )

        path.write_text(
            '<hierarchy><node package="com.localagentbridge.android" '
            'scrollable="true" bounds="[100,100][900,1900]">'
            '<node package="com.localagentbridge.android" scrollable="true" '
            'bounds="[0,0][1080,2400]">'
            '<node package="com.localagentbridge.android" clickable="true" '
            'enabled="true" checkable="true" checked="false" '
            'bounds="[50,50][250,150]">'
            '<node package="com.localagentbridge.android" text="한국어" '
            'enabled="true" bounds="[75,70][225,130]"/>'
            "</node></node></node></hierarchy>",
            encoding="utf-8",
        )
        self.assertTrue(
            checker.ui_actionable_token_failures(
                self.result_directory,
                relative="ui/in-app-korean-settings.xml",
                text="한국어",
                expected_checked="false",
            ),
            "an inner viewport must not hide clipping by an outer scrollable ancestor",
        )

    def test_noncanonical_and_exact_type_mutations_are_rejected(self) -> None:
        self._write_result(canonical=False)
        with self._validation_scope():
            failures = checker.result_failures(
                self.result_path,
                root=self.root,
                sdk_root=self.sdk_root,
                java_home=self.java_home,
            )
        self.assertTrue(any("canonical JSON" in failure for failure in failures))

        self.payload["schemaVersion"] = True
        self.assertTrue(any("schemaVersion" in failure for failure in self._failures()))

    def test_source_toolchain_and_scenario_mutations_are_rejected(self) -> None:
        mutations = {
            "source": lambda: self.payload["source"].__setitem__(  # type: ignore[union-attr]
                "sha256", "0" * 64
            ),
            "toolchain": lambda: self.payload["toolchain"]["adb"].__setitem__(  # type: ignore[index,union-attr]
                "sha256", "0" * 64
            ),
            "scenario": lambda: next(
                iter(self.payload["scenarios"][0]["checks"].values())  # type: ignore[index,union-attr]
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                original = copy.deepcopy(self.payload)
                if label == "scenario":
                    first = self.payload["scenarios"][0]["checks"]  # type: ignore[index]
                    first[next(iter(first))] = False
                else:
                    mutate()
                self.assertTrue(self._failures())
                self.payload = original

    def test_observation_contract_rejects_semantic_self_claim_mutations(self) -> None:
        mutations = {
            "duplicate_pids": (
                "force_stop_cold_launch_repetition",
                lambda value: value.__setitem__("processIds", [1001, 1001, 1001]),
                "three distinct raw process identities",
            ),
            "missing_locale": (
                "platform_locale_ko",
                lambda value: value.__setitem__("localeTags", []),
                "localeTags",
            ),
            "wrong_font": (
                "platform_locale_en",
                lambda value: value.__setitem__("fontScale", "1.0"),
                "fontScale",
            ),
            "permission_flip": (
                "camera_permission_denial_and_cold_launch",
                lambda value: value.__setitem__("cameraPermissionGranted", True),
                "cameraPermissionGranted",
            ),
            "screen_flip": (
                "font_scale_200_core_reachability",
                lambda value: value.__setitem__("screen", [720, 1280, 320]),
                "screen",
            ),
        }
        original = copy.deepcopy(self.payload)
        for label, (scenario_name, mutate, expected) in mutations.items():
            with self.subTest(label=label):
                self.payload = copy.deepcopy(original)
                scenario = next(
                    item
                    for item in self.payload["scenarios"]  # type: ignore[union-attr]
                    if item["name"] == scenario_name
                )
                mutate(scenario["observations"])
                self.assertTrue(
                    any(expected in failure for failure in self._failures())
                )
        self.payload = original

    def test_coherent_scenario_pid_mutation_is_rejected_by_raw_pidof_evidence(self) -> None:
        for scenario in self.payload["scenarios"]:  # type: ignore[union-attr]
            observations = scenario["observations"]
            if "firstProcessId" in observations:
                observations["firstProcessId"] += 5000
            if "processIds" in observations:
                observations["processIds"] = [
                    value + 5000 for value in observations["processIds"]
                ]
            if "processId" in observations:
                observations["processId"] += 5000
        self.assertTrue(
            any(
                "raw package pidof" in failure
                for failure in self._failures()
            )
        )
        path = self.result_directory / "app-process-observations.json"
        records = json.loads(path.read_bytes())
        for record in records:
            pid = int(record["stdout"].strip()) + 5000
            record["stdout"] = f"{pid}\n"
            record["procCmdlineCommand"] = ["cat", f"/proc/{pid}/cmdline"]
            record["procStatBeforeCommand"] = ["cat", f"/proc/{pid}/stat"]
            record["procStatAfterCommand"] = ["cat", f"/proc/{pid}/stat"]
        path.write_bytes(checker.canonical_json_bytes(records))
        self._refresh_evidence()
        self.assertTrue(
            any(
                "procStatBeforeStdout must bind the exact observed PID" in failure
                for failure in self._failures()
            )
        )

    def test_numeric_pid_reuse_with_distinct_start_ticks_is_accepted(self) -> None:
        path = self.result_directory / "app-process-observations.json"
        records = json.loads(path.read_bytes())
        reused_pid = 1001
        for index in range(3):
            record = records[index]
            start_ticks = 60001 + index
            stat = (
                f"{reused_pid} (tbridge.android) S "
                + " ".join(["0"] * 18)
                + f" {start_ticks} 0 0\n"
            )
            record.update(
                {
                    "procCmdlineCommand": ["cat", f"/proc/{reused_pid}/cmdline"],
                    "procStatAfterCommand": ["cat", f"/proc/{reused_pid}/stat"],
                    "procStatAfterStdout": stat,
                    "procStatBeforeCommand": ["cat", f"/proc/{reused_pid}/stat"],
                    "procStatBeforeStdout": stat,
                    "processStartTicks": start_ticks,
                    "stdout": f"{reused_pid}\n",
                }
            )
        path.write_bytes(checker.canonical_json_bytes(records))
        cold = next(
            scenario
            for scenario in self.payload["scenarios"]  # type: ignore[union-attr]
            if scenario["name"] == "force_stop_cold_launch_repetition"
        )
        cold["observations"]["processIds"] = [reused_pid] * 3
        self._refresh_evidence()
        self.assertEqual(self._failures(), [])

    def test_reused_numeric_pid_with_same_start_ticks_is_rejected(self) -> None:
        path = self.result_directory / "app-process-observations.json"
        records = json.loads(path.read_bytes())
        reused_pid = 1001
        reused_ticks = 60001
        stat = (
            f"{reused_pid} (tbridge.android) S "
            + " ".join(["0"] * 18)
            + f" {reused_ticks} 0 0\n"
        )
        for index in range(3):
            records[index].update(
                {
                    "procCmdlineCommand": ["cat", f"/proc/{reused_pid}/cmdline"],
                    "procStatAfterCommand": ["cat", f"/proc/{reused_pid}/stat"],
                    "procStatAfterStdout": stat,
                    "procStatBeforeCommand": ["cat", f"/proc/{reused_pid}/stat"],
                    "procStatBeforeStdout": stat,
                    "processStartTicks": reused_ticks,
                    "stdout": f"{reused_pid}\n",
                }
            )
        path.write_bytes(checker.canonical_json_bytes(records))
        cold = next(
            scenario
            for scenario in self.payload["scenarios"]  # type: ignore[union-attr]
            if scenario["name"] == "force_stop_cold_launch_repetition"
        )
        cold["observations"]["processIds"] = [reused_pid] * 3
        self._refresh_evidence()
        self.assertTrue(
            any(
                "three distinct raw process identities" in failure
                for failure in self._failures()
            )
        )

    def test_process_identity_change_across_stat_reads_is_rejected(self) -> None:
        path = self.result_directory / "app-process-observations.json"
        records = json.loads(path.read_bytes())
        record = records[0]
        pid = int(record["stdout"].strip())
        changed_ticks = int(record["processStartTicks"]) + 1
        record["procStatAfterStdout"] = (
            f"{pid} (tbridge.android) S "
            + " ".join(["0"] * 18)
            + f" {changed_ticks} 0 0\n"
        )
        path.write_bytes(checker.canonical_json_bytes(records))
        self._refresh_evidence()
        self.assertTrue(
            any("identity changed across the cmdline read" in failure for failure in self._failures())
        )

    def test_pidof_observation_rejects_out_of_range_pid(self) -> None:
        path = self.result_directory / "app-process-observations.json"
        records = json.loads(path.read_bytes())
        records[0]["stdout"] = "99999999999\n"
        path.write_bytes(checker.canonical_json_bytes(records))
        self._refresh_evidence()
        self.assertTrue(
            any(
                "bounded exact positive pidof PID" in failure
                for failure in self._failures()
            )
        )

    def test_camera_permission_raw_states_are_independently_parsed(self) -> None:
        path = self.result_directory / "camera-permission-after-grant.txt"
        path.write_text(
            "Package [com.localagentbridge.android]\n"
            "    android.permission.CAMERA: granted=false, flags=[ USER_SET ]\n",
            encoding="utf-8",
        )
        self._refresh_evidence()
        self.assertTrue(
            any(
                "camera-permission-after-grant.txt CAMERA state must be granted=true"
                in failure
                for failure in self._failures()
            )
        )

        path.write_text(
            "    android.permission.CAMERA: granted=true\n"
            "    android.permission.CAMERA: granted=true\n",
            encoding="utf-8",
        )
        self._refresh_evidence()
        self.assertTrue(
            any("exactly one CAMERA" in failure for failure in self._failures())
        )

    def test_network_line_counts_require_exact_integers(self) -> None:
        original = copy.deepcopy(self.payload)
        for key in (
            "before",
            "after",
            "appNetworkingAfterDeny",
            "appNetworkingAfterLifecycle",
            "guestAirplaneModeBefore",
            "guestAirplaneModeAfter",
        ):
            with self.subTest(key=key):
                self.payload = copy.deepcopy(original)
                self.payload["networkIsolation"][key]["lineCount"] = True  # type: ignore[index]
                self.assertTrue(
                    any(
                        "lineCount" in failure and "integer" in failure
                        for failure in self._failures()
                    )
                )
        self.payload = original

    def test_raw_package_networking_state_is_independently_parsed(self) -> None:
        path = self.result_directory / "app-networking-after-lifecycle.txt"
        raw = f"{checker.PACKAGE_NAME}:allow\n".encode("ascii")
        path.write_bytes(raw)
        self.payload["networkIsolation"]["appNetworkingAfterLifecycle"].update(  # type: ignore[index,union-attr]
            {
                "lineCount": len(raw.splitlines()),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "value": f"{checker.PACKAGE_NAME}:allow",
            }
        )
        self._refresh_evidence()
        self.assertTrue(
            any(
                "app-networking-after-lifecycle.txt must contain" in failure
                for failure in self._failures()
            )
        )

    def test_built_and_installed_apk_byte_mismatch_is_rejected(self) -> None:
        installed_path = self.result_directory / "installed-base.apk"
        installed_path.write_bytes(b"different-installed-apk\n")
        self.payload["artifact"]["installed"] = checker.file_record(  # type: ignore[index]
            installed_path,
            relative="installed-base.apk",
        )
        self._refresh_evidence()
        failures = self._failures()
        self.assertTrue(any("exactly equal" in failure for failure in failures))

    def test_raw_logcat_and_exit_info_are_not_trusted_to_empty_claims(self) -> None:
        logcat_path = self.result_directory / "logcat.txt"
        raw = (
            b"FATAL EXCEPTION: main\n"
            b"Process: com.localagentbridge.android, PID: 123\n"
        )
        logcat_path.write_bytes(raw)
        self.payload["logcat"].update(  # type: ignore[union-attr]
            {
                "lineCount": len(raw.splitlines()),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        self._refresh_evidence()
        self.assertTrue(
            any("FATAL/ANR" in failure for failure in self._failures())
        )

        self.setUp_exit_info_mutation()
        self.assertTrue(
            any("crash/ANR reason" in failure for failure in self._failures())
        )

    def setUp_exit_info_mutation(self) -> None:
        exit_path = self.result_directory / "exit-info.txt"
        raw = (
            b"process=com.localagentbridge.android "
            b"reason=5 (CRASH_NATIVE)\n"
        )
        exit_path.write_bytes(raw)
        self.payload["exitInfo"].update(  # type: ignore[union-attr]
            {
                "lineCount": len(raw.splitlines()),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        self._refresh_evidence()

    def test_raw_network_and_cleanup_snapshots_are_independently_parsed(self) -> None:
        network_path = self.result_directory / "network-state-after.txt"
        raw = (
            b"  NetworkAgentInfo{network{100} "
            b"Capabilities: NET_CAPABILITY_INTERNET&"
            b"NET_CAPABILITY_VALIDATED factorySerialNumber=1}\n"
        )
        network_path.write_bytes(raw)
        self.payload["networkIsolation"]["after"].update(  # type: ignore[index,union-attr]
            {
                "lineCount": len(raw.splitlines()),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "validatedInternetMatches": checker.validated_network_lines(
                    raw.decode("ascii")
                ),
            }
        )
        self._refresh_evidence()
        self.assertTrue(
            any("validated Internet" in failure for failure in self._failures())
        )

        post_path = self.result_directory / "post-adb-devices.txt"
        post_path.write_text("List of devices attached\n", encoding="utf-8")
        self.payload["cleanup"]["postSerials"] = []  # type: ignore[index]
        self._refresh_evidence()
        self.assertTrue(
            any("preserve every preexisting" in failure for failure in self._failures())
        )

    def test_same_serial_with_replaced_host_process_is_rejected(self) -> None:
        replacement = copy.deepcopy(self.host_emulators)
        replacement[0]["pid"] = 90000
        replacement[0]["processStartedAt"] = "Sat Aug  1 00:00:00 2026"
        (self.result_directory / "post-emulator-processes.json").write_bytes(
            checker.canonical_json_bytes(replacement)
        )
        self.payload["cleanup"]["postHostEmulators"] = replacement  # type: ignore[index]
        self._refresh_evidence()
        self.assertTrue(
            any(
                "same PID and start identity" in failure
                for failure in self._failures()
            )
        )

    def test_launch_avd_and_evidence_byte_mutations_are_rejected(self) -> None:
        launch_path = self.result_directory / "launch-argv.json"
        launch = json.loads(launch_path.read_bytes())
        launch.remove("-wifi-user-mode-options")
        launch.remove("restrict=on")
        launch_path.write_bytes(checker.canonical_json_bytes(launch))
        self._refresh_evidence()
        self.assertTrue(
            any("exact owned launch" in failure for failure in self._failures())
        )

        config_path = self.result_directory / "avd-config.ini"
        config_path.write_bytes(config_path.read_bytes() + b"hw.ramSize = 1\n")
        self._refresh_evidence()
        self.assertTrue(
            any("exact owned AVD config" in failure for failure in self._failures())
        )

        ui_path = self.result_directory / "ui/first-launch.xml"
        ui_path.write_bytes(ui_path.read_bytes() + b"\n")
        self.assertTrue(
            any("bind every retained evidence" in failure for failure in self._failures())
        )

    def test_ui_and_raw_parser_helpers_reject_unsafe_evidence(self) -> None:
        nodes = [
            {
                "bounds": "[0,0][1080,2400]",
                "package": checker.PACKAGE_NAME,
                "text": "Pair AetherLink",
            }
        ]
        self.assertEqual(
            checker.ui_token_failures(
                nodes,
                relative="ui/fixture.xml",
                package=checker.PACKAGE_NAME,
                text="Pair AetherLink",
            ),
            [],
        )
        nodes[0]["bounds"] = "[0,0][1081,2400]"
        self.assertTrue(
            checker.ui_token_failures(
                nodes,
                relative="ui/fixture.xml",
                package=checker.PACKAGE_NAME,
                text="Pair AetherLink",
            )
        )
        dtd = self.result_directory / "ui/first-launch.xml"
        dtd.write_bytes(b'<!DOCTYPE x [<!ENTITY y "z">]><hierarchy/>')
        _, failures = checker.ui_nodes(
            self.result_directory,
            "ui/first-launch.xml",
        )
        self.assertTrue(any("DTD" in failure for failure in failures))
        self.assertTrue(
            checker.app_exit_failure_lines("reason=6 (ANR)\n")
        )

    def test_network_parser_distinguishes_current_from_historical_validation(self) -> None:
        historical = (
            "  NetworkAgentInfo{network{100} INTERNET EVER_VALIDATED "
            "factorySerialNumber=1}\n"
        )
        self.assertEqual(checker.validated_network_lines(historical), [])
        multiline = (
            "  NetworkAgentInfo{network{100} INTERNET\n"
            "    Score(Policies : IS_VALIDATED) factorySerialNumber=1}\n"
        )
        self.assertEqual(len(checker.validated_network_lines(multiline)), 1)

    def test_source_snapshot_binds_future_debug_source_set(self) -> None:
        root = Path(self.temporary.name) / "source-set-fixture"
        source_root = root / "module/src"
        main = source_root / "main/Main.kt"
        main.parent.mkdir(parents=True)
        main.write_text("fun main() = Unit\n", encoding="utf-8")
        with (
            patch.object(checker, "SOURCE_REQUIRED_FILES", ()),
            patch.object(checker, "SOURCE_ROOTS", (Path("module/src"),)),
        ):
            before = checker.source_snapshot(root)
            debug = source_root / "debug/AndroidManifest.xml"
            debug.parent.mkdir(parents=True)
            debug.write_text("<manifest/>\n", encoding="utf-8")
            after = checker.source_snapshot(root)
        self.assertNotEqual(before["sha256"], after["sha256"])


if __name__ == "__main__":
    unittest.main()
