#!/usr/bin/env python3
"""Run the API 36.1 background, process-kill, and reboot lifecycle successor."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script import check_android_headless_emulator_product_lifecycle as base_contract
from script import check_android_headless_emulator_product_lifecycle_v2 as contract
from script import run_android_headless_emulator_product_lifecycle as base


PACKAGE_NAME = base.PACKAGE_NAME
CAMERA_PERMISSION = base.CAMERA_PERMISSION
PREFERENCES_RELATIVE = (
    "shared_prefs/aetherlink_pairing_qr_camera_permission.xml"
)
FUTURE_RUNTIME_LOCAL_STORE_RELATIVE = "shared_prefs/runtime_local_store.xml"
FUTURE_RUNTIME_LOCAL_STORE_SEED = (
    b'<?xml version="1.0" encoding="utf-8" standalone="yes" ?>\n'
    b"<map>\n"
    b'    <string name="runtime_data">{&quot;version&quot;:2}</string>\n'
    b"</map>\n"
)
FUTURE_DATA_UPDATE_REQUIRED_TEXT = (
    "This version of AetherLink can’t safely open the saved app data. "
    "Update AetherLink before changing settings."
)
FUTURE_RUNTIME_LOCAL_STORE_WRITE_RECEIPT = "aetherlink-future-seed-ok\n"
FUTURE_RUNTIME_LOCAL_STORE_WRITE_SCRIPT = (
    "set -eu; umask 077; mkdir -p shared_prefs; "
    "rm -f shared_prefs/runtime_local_store.xml.bak "
    "shared_prefs/.runtime_local_store.xml.aetherlink-v2; "
    "cat > shared_prefs/.runtime_local_store.xml.aetherlink-v2; "
    "chmod 600 shared_prefs/.runtime_local_store.xml.aetherlink-v2; "
    "mv shared_prefs/.runtime_local_store.xml.aetherlink-v2 "
    "shared_prefs/runtime_local_store.xml; "
    "printf 'aetherlink-future-seed-ok\\n'"
)
LEGACY_RUNTIME_LOCAL_STORE_SEED = (
    b'<?xml version="1.0" encoding="utf-8" standalone="yes" ?>\n'
    b"<map>\n"
    b'    <string name="runtime_data">'
    b"{&quot;appTheme&quot;:&quot;dark&quot;,&quot;composerDraft&quot;:"
    b"&quot;legacy-v0&quot;,&quot;trustedRuntimeAutoReconnectEnabled&quot;:false}"
    b"</string>\n"
    b"</map>\n"
)
LEGACY_RUNTIME_LOCAL_STORE_WRITE_RECEIPT = "aetherlink-legacy-seed-ok\n"
LEGACY_RUNTIME_LOCAL_STORE_WRITE_SCRIPT = (
    "set -eu; umask 077; mkdir -p shared_prefs; "
    "rm -f shared_prefs/runtime_local_store.xml.bak "
    "shared_prefs/.runtime_local_store.xml.aetherlink-legacy; "
    "cat > shared_prefs/.runtime_local_store.xml.aetherlink-legacy; "
    "chmod 600 shared_prefs/.runtime_local_store.xml.aetherlink-legacy; "
    "mv shared_prefs/.runtime_local_store.xml.aetherlink-legacy "
    "shared_prefs/runtime_local_store.xml; "
    "printf 'aetherlink-legacy-seed-ok\\n'"
)
COMMAND_TIMEOUT_SECONDS = base.COMMAND_TIMEOUT_SECONDS
LIFECYCLE_TIMEOUT_SECONDS = 240
MAX_RAW_COMMAND_BYTES = 4 * 1024 * 1024
BOOT_ID_RE = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    rb"[89ab][0-9a-f]{3}-[0-9a-f]{12}\n\Z"
)
DEVICEIDLE_UNFORCE_RECEIPT_RE = re.compile(
    rb"Light state: ([A-Z_]+), deep state: ([A-Z_]+)\n"
    rb"mForceModeManagerQuickDozeRequest: false\n"
    rb"mForceModeManagerOffBodyState: false\n\Z"
)
DEVICEIDLE_LIGHT_STATES = frozenset(
    {
        "ACTIVE",
        "INACTIVE",
        "PRE_IDLE",
        "IDLE",
        "WAITING_FOR_NETWORK",
        "IDLE_MAINTENANCE",
        "OVERRIDE",
    }
)
DEVICEIDLE_DEEP_STATES = frozenset(
    {
        "ACTIVE",
        "INACTIVE",
        "IDLE_PENDING",
        "SENSING",
        "LOCATING",
        "IDLE",
        "IDLE_MAINTENANCE",
        "QUICK_DOZE_DELAY",
    }
)


RunnerError = base.RunnerError
Commands = base.Commands


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def write_canonical_json(path: Path, value: object) -> None:
    path.write_bytes(base_contract.canonical_json_bytes(value))


def prepublication_payload_failures(
    payload: object,
    *,
    output_directory: Path,
    root: Path,
    sdk_root: Path,
    java_home: Path,
) -> list[str]:
    result_path = output_directory / "result.json"
    with contract.EvidenceSnapshot(
        result_path,
        result_required=False,
    ) as snapshot:
        evidence = snapshot.capture()
        failures = contract.payload_failures(
            payload,
            result_directory=output_directory,
            evidence=evidence,
            root=root,
            sdk_root=sdk_root,
            java_home=java_home,
        )
        snapshot.verify_unchanged()
        return failures


def completed_receipt(
    commands: Commands,
    command: list[str],
    result: subprocess.CompletedProcess[bytes],
) -> dict[str, object]:
    if not isinstance(result.stdout, bytes) or not isinstance(result.stderr, bytes):
        raise RunnerError("raw command receipt requires byte stdout and stderr")
    if len(result.stdout) + len(result.stderr) > MAX_RAW_COMMAND_BYTES:
        raise RunnerError("raw command receipt exceeds the 4 MiB bound")
    if commands.serial is None:
        raise RunnerError("raw command receipt requires the owned emulator serial")
    try:
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RunnerError(f"raw command receipt is not UTF-8: {error}") from error
    return {
        "command": command,
        "exitCode": result.returncode,
        "serial": commands.serial,
        "stderr": stderr,
        "stdout": stdout,
    }


def read_boot_id(commands: Commands, path: Path | None = None) -> str:
    result = commands.adb(
        "exec-out",
        "cat",
        "/proc/sys/kernel/random/boot_id",
        text=False,
        timeout=30,
    )
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    if result.returncode != 0 or result.stderr or BOOT_ID_RE.fullmatch(result.stdout) is None:
        raise RunnerError(
            "boot_id must be one exact lowercase RFC 4122 UUID line; "
            f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
    if path is not None:
        path.write_bytes(result.stdout)
    return result.stdout.decode("ascii").removesuffix("\n")


def parse_process_stat(raw: bytes, *, pid: int, phase: str) -> tuple[str, int]:
    try:
        value = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise RunnerError(f"process stat {phase} is not ASCII: {error}") from error
    if not (1 <= len(value) <= 4096):
        raise RunnerError(f"process stat {phase} is not bounded")
    match = re.fullmatch(rf"{pid} \(([^()\n]{{1,128}})\) ([^\n]+)\n", value)
    if match is None:
        raise RunnerError(f"process stat {phase} does not bind PID {pid}")
    fields = match.group(2).split()
    if len(fields) < 20 or re.fullmatch(r"[1-9][0-9]{0,19}", fields[19]) is None:
        raise RunnerError(f"process stat {phase} has no positive start ticks")
    start_ticks = int(fields[19])
    if start_ticks > 9_223_372_036_854_775_807:
        raise RunnerError(f"process stat {phase} start ticks exceed int64")
    return value, start_ticks


def capture_process_identity(
    commands: Commands,
    *,
    label: str,
    boot_id: str,
) -> dict[str, object]:
    pidof = commands.adb("shell", "pidof", PACKAGE_NAME, check=False, text=False)
    assert isinstance(pidof.stdout, bytes)
    assert isinstance(pidof.stderr, bytes)
    if (
        pidof.returncode != 0
        or pidof.stderr
        or re.fullmatch(rb"[1-9][0-9]{0,9}\n", pidof.stdout) is None
    ):
        raise RunnerError(
            "pidof must return one exact package PID with empty stderr; "
            f"exit={pidof.returncode}, stdout={pidof.stdout!r}, stderr={pidof.stderr!r}"
        )
    pid = int(pidof.stdout.removesuffix(b"\n"))
    if pid > 2_147_483_647:
        raise RunnerError("package PID exceeds the Android PID range")
    proc_path = f"/proc/{pid}"
    stat_before = commands.adb("exec-out", "cat", f"{proc_path}/stat", text=False)
    cmdline = commands.adb("exec-out", "cat", f"{proc_path}/cmdline", text=False)
    stat_after = commands.adb("exec-out", "cat", f"{proc_path}/stat", text=False)
    assert isinstance(stat_before.stdout, bytes)
    assert isinstance(cmdline.stdout, bytes)
    assert isinstance(stat_after.stdout, bytes)
    package = PACKAGE_NAME.encode("ascii")
    if (
        cmdline.returncode != 0
        or cmdline.stderr
        or not (1 <= len(cmdline.stdout) <= 4096)
        or not cmdline.stdout.startswith(package + b"\0")
        or cmdline.stdout.rstrip(b"\0") != package
    ):
        raise RunnerError(f"/proc/{pid}/cmdline does not identify the exact package")
    before_text, before_ticks = parse_process_stat(
        stat_before.stdout,
        pid=pid,
        phase="before",
    )
    after_text, after_ticks = parse_process_stat(
        stat_after.stdout,
        pid=pid,
        phase="after",
    )
    if (
        stat_before.returncode != 0
        or stat_before.stderr
        or stat_after.returncode != 0
        or stat_after.stderr
        or before_ticks != after_ticks
    ):
        raise RunnerError(f"package process identity changed during /proc read for PID {pid}")
    if commands.serial is None:
        raise RunnerError("process identity requires the owned emulator serial")
    return {
        "bootId": boot_id,
        "command": ["pidof", PACKAGE_NAME],
        "label": label,
        "procCmdlineBase64": base64.b64encode(cmdline.stdout).decode("ascii"),
        "procCmdlineCommand": ["cat", f"{proc_path}/cmdline"],
        "procStatAfterCommand": ["cat", f"{proc_path}/stat"],
        "procStatAfterStdout": after_text,
        "procStatBeforeCommand": ["cat", f"{proc_path}/stat"],
        "procStatBeforeStdout": before_text,
        "processStartTicks": before_ticks,
        "serial": commands.serial,
        "stdout": pidof.stdout.decode("ascii"),
    }


def process_identity_key(record: dict[str, object]) -> tuple[object, object, object]:
    return (record["bootId"], process_pid(record), record["processStartTicks"])


def process_pid(record: dict[str, object]) -> int:
    stdout = record.get("stdout")
    if type(stdout) is not str or re.fullmatch(r"[1-9][0-9]{0,9}\n", stdout) is None:
        raise RunnerError("retained process identity has no exact pidof stdout")
    return int(stdout.removesuffix("\n"))


def _read_runtime_local_data(
    commands: Commands,
    *,
    timeout: float = 30,
) -> bytes:
    result = commands.adb(
        "exec-out",
        "run-as",
        PACKAGE_NAME,
        "cat",
        FUTURE_RUNTIME_LOCAL_STORE_RELATIVE,
        check=False,
        text=False,
        timeout=timeout,
    )
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    if (
        result.returncode != 0
        or result.stderr
        or not (1 <= len(result.stdout) <= 1024 * 1024)
    ):
        raise RunnerError(
            "runtime local data readback must be one bounded file; "
            f"exit={result.returncode}, stdout={result.stdout!r}, "
            f"stderr={result.stderr!r}"
        )
    return result.stdout


def _read_future_runtime_local_data(commands: Commands) -> bytes:
    raw = _read_runtime_local_data(commands)
    if raw != FUTURE_RUNTIME_LOCAL_STORE_SEED:
        raise RunnerError(
            "future-version runtime local data readback must match the exact seed"
        )
    return raw


def _seed_runtime_local_data(
    commands: Commands,
    *,
    seed: bytes,
    write_receipt: str,
    write_script: str,
    label: str,
) -> bytes:
    if commands.serial is None:
        raise RunnerError(f"{label} seed requires the owned emulator serial")
    remote_command = shlex.join(
        [
            "run-as",
            PACKAGE_NAME,
            "sh",
            "-c",
            write_script,
        ]
    )
    command = [
        str(commands.adb_path),
        "-s",
        commands.serial,
        "shell",
        "-T",
        remote_command,
    ]
    result = commands.run(
        command,
        check=False,
        timeout=30,
        input_text=seed.decode("ascii"),
    )
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)
    if (
        result.returncode != 0
        or result.stdout != write_receipt
        or result.stderr
    ):
        raise RunnerError(
            f"{label} runtime local data seed failed; "
            f"exit={result.returncode}, stdout={result.stdout!r}, "
            f"stderr={result.stderr!r}"
        )
    raw = _read_runtime_local_data(commands)
    if raw != seed:
        raise RunnerError(f"{label} runtime local data seed readback differs")
    return raw


def seed_future_runtime_local_data(commands: Commands) -> bytes:
    return _seed_runtime_local_data(
        commands,
        seed=FUTURE_RUNTIME_LOCAL_STORE_SEED,
        write_receipt=FUTURE_RUNTIME_LOCAL_STORE_WRITE_RECEIPT,
        write_script=FUTURE_RUNTIME_LOCAL_STORE_WRITE_SCRIPT,
        label="future-version",
    )


def capture_future_runtime_local_data(
    commands: Commands,
    output_directory: Path,
    relative: str,
) -> bytes:
    if relative not in {
        "runtime-local-store-after-future-version-first-launch.xml",
        "runtime-local-store-after-future-version-second-launch.xml",
    }:
        raise RunnerError(f"unexpected future-version local-data evidence path: {relative!r}")
    raw = _read_future_runtime_local_data(commands)
    (output_directory / relative).write_bytes(raw)
    return raw


def _runtime_local_store_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise RunnerError(f"{label} is malformed XML: {error}") from error
    children = list(root)
    if (
        root.tag != "map"
        or root.attrib
        or len(children) != 1
        or children[0].tag != "string"
        or children[0].attrib != {"name": "runtime_data"}
        or type(children[0].text) is not str
        or list(children[0])
    ):
        raise RunnerError(f"{label} must contain only one runtime_data string")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise RunnerError(f"{label} contains duplicate JSON key {key!r}")
            value[key] = item
        return value

    try:
        value = json.loads(children[0].text, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RunnerError(f"{label} runtime_data is malformed JSON: {error}") from error
    if type(value) is not dict:
        raise RunnerError(f"{label} runtime_data must be a JSON object")
    return value


def legacy_migrated_runtime_local_data_facts(raw: bytes) -> dict[str, object]:
    if raw == LEGACY_RUNTIME_LOCAL_STORE_SEED:
        raise RunnerError("legacy versionless local data has not migrated")
    value = _runtime_local_store_json(raw, label="migrated legacy local data")
    expected = {
        "appLanguageSource": "system",
        "appLanguageTag": "en",
        "appTheme": "dark",
        "composerDraft": "legacy-v0",
        "trustedRuntimeAutoReconnectEnabled": False,
    }
    for key, expected_value in expected.items():
        if type(value.get(key)) is not type(expected_value) or value.get(key) != expected_value:
            raise RunnerError(
                f"migrated legacy local data must preserve {key}={expected_value!r}"
            )
    for key, expected_value in (
        ("version", 1),
        ("androidAppLanguagePlatformMigrationVersion", 1),
    ):
        if type(value.get(key)) is not int or value.get(key) != expected_value:
            raise RunnerError(
                f"migrated legacy local data must contain integer {key}={expected_value}"
            )
    return {
        "appTheme": value["appTheme"],
        "composerDraft": value["composerDraft"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "trustedRuntimeAutoReconnectEnabled": value[
            "trustedRuntimeAutoReconnectEnabled"
        ],
        "version": value["version"],
    }


def seed_legacy_runtime_local_data(commands: Commands) -> bytes:
    return _seed_runtime_local_data(
        commands,
        seed=LEGACY_RUNTIME_LOCAL_STORE_SEED,
        write_receipt=LEGACY_RUNTIME_LOCAL_STORE_WRITE_RECEIPT,
        write_script=LEGACY_RUNTIME_LOCAL_STORE_WRITE_SCRIPT,
        label="legacy-versionless",
    )


def wait_for_legacy_runtime_local_data_migration(
    commands: Commands,
    output_directory: Path,
    relative: str,
) -> tuple[bytes, dict[str, object]]:
    if relative != "runtime-local-store-after-legacy-migration-first-launch.xml":
        raise RunnerError(f"unexpected legacy-migration evidence path: {relative!r}")
    deadline = time.monotonic() + 30
    last_error: RunnerError | None = None
    while True:
        try:
            timeout = base.remaining_timeout(
                deadline,
                maximum=5,
                description="legacy local-data migration",
            )
            raw = _read_runtime_local_data(commands, timeout=timeout)
            facts = legacy_migrated_runtime_local_data_facts(raw)
        except RunnerError as error:
            last_error = error
        else:
            (output_directory / relative).write_bytes(raw)
            return raw, facts
        if time.monotonic() >= deadline:
            raise RunnerError(
                f"legacy local-data migration did not converge: {last_error}"
            )
        time.sleep(0.25)


def capture_legacy_migrated_runtime_local_data(
    commands: Commands,
    output_directory: Path,
    relative: str,
) -> tuple[bytes, dict[str, object]]:
    if relative != "runtime-local-store-after-legacy-migration-second-launch.xml":
        raise RunnerError(f"unexpected legacy-migration evidence path: {relative!r}")
    raw = _read_runtime_local_data(commands)
    facts = legacy_migrated_runtime_local_data_facts(raw)
    (output_directory / relative).write_bytes(raw)
    return raw, facts


def capture_camera_preferences(commands: Commands, path: Path) -> bytes:
    result = commands.adb(
        "exec-out",
        "run-as",
        PACKAGE_NAME,
        "cat",
        PREFERENCES_RELATIVE,
        text=False,
        timeout=30,
    )
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    raw = result.stdout
    if result.returncode != 0 or result.stderr or not (1 <= len(raw) <= 64 * 1024):
        raise RunnerError(
            "camera request-state preferences could not be captured exactly; "
            f"exit={result.returncode}, stderr={result.stderr!r}"
        )
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise RunnerError(f"camera request-state preferences are malformed: {error}") from error
    children = list(root)
    if (
        root.tag != "map"
        or len(children) != 1
        or children[0].tag != "string"
        or children[0].attrib != {"name": "request_state"}
        or children[0].text != "recorded"
        or list(children[0])
    ):
        raise RunnerError("camera request-state preferences must contain only recorded state")
    path.write_bytes(raw)
    return raw


def capture_raw_adb(
    commands: Commands,
    path: Path,
    *arguments: str,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
) -> bytes:
    result = commands.adb(*arguments, text=False, timeout=timeout)
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    if result.returncode != 0 or result.stderr or not (1 <= len(result.stdout) <= MAX_RAW_COMMAND_BYTES):
        raise RunnerError(
            f"raw adb capture failed for {arguments!r}; exit={result.returncode}, "
            f"stderr={result.stderr!r}"
        )
    path.write_bytes(result.stdout)
    return result.stdout


def capture_activity(commands: Commands, path: Path, *, app_resumed: bool) -> bytes:
    raw = capture_raw_adb(
        commands,
        path,
        "shell",
        "dumpsys",
        "activity",
        "activities",
        timeout=60,
    )
    resumed = base.main_activity_is_resumed(raw.decode("utf-8", "replace"))
    if resumed is not app_resumed:
        state = "resumed" if app_resumed else "background"
        raise RunnerError(f"MainActivity did not reach required {state} state")
    return raw


def capture_ui(
    commands: Commands,
    result_directory: Path,
    relative: str | None,
    *,
    deadline: float | None = None,
) -> ET.Element:
    if relative is not None and (
        relative not in contract.EVIDENCE_PATHS or not relative.startswith("ui/")
    ):
        raise RunnerError(f"unexpected v2 UI evidence path: {relative}")
    local_path = result_directory / relative if relative is not None else None
    if local_path is not None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
    stem = Path(relative).stem if relative is not None else "ephemeral-v2"
    remote = f"/sdcard/aetherlink-v2-{stem}-{secrets.token_hex(8)}.xml"
    last_error: Exception | None = None
    try:
        for _ in range(10):
            remove_timeout = (
                base.remaining_timeout(
                    deadline,
                    maximum=10,
                    description=f"v2 UI capture {relative}",
                )
                if deadline is not None
                else 10
            )
            commands.adb(
                "shell",
                "rm",
                "-f",
                remote,
                check=False,
                timeout=remove_timeout,
            )
            dump_timeout = (
                base.remaining_timeout(
                    deadline,
                    maximum=20,
                    description=f"v2 UI capture {relative}",
                )
                if deadline is not None
                else 20
            )
            dumped = commands.adb(
                "shell",
                "uiautomator",
                "dump",
                remote,
                check=False,
                timeout=dump_timeout,
            )
            if dumped.returncode == 0:
                read_timeout = (
                    base.remaining_timeout(
                        deadline,
                        maximum=20,
                        description=f"v2 UI capture {relative}",
                    )
                    if deadline is not None
                    else 20
                )
                result = commands.adb(
                    "exec-out",
                    "cat",
                    remote,
                    check=False,
                    text=False,
                    timeout=read_timeout,
                )
                assert isinstance(result.stdout, bytes)
                try:
                    parsed = ET.fromstring(result.stdout)
                except ET.ParseError as error:
                    last_error = error
                else:
                    if deadline is not None:
                        base.remaining_timeout(
                            deadline,
                            maximum=1,
                            description=f"v2 UI capture {relative}",
                        )
                    if local_path is not None:
                        local_path.write_bytes(result.stdout)
                    return parsed
            sleep_seconds = 1.0
            if deadline is not None:
                sleep_seconds = min(
                    sleep_seconds,
                    base.remaining_timeout(
                        deadline,
                        maximum=1,
                        description=f"v2 UI capture {relative}",
                    ),
                )
            time.sleep(sleep_seconds)
    finally:
        cleanup_timeout = 10.0
        if deadline is not None:
            cleanup_timeout = min(10.0, max(0.0, deadline - time.monotonic()))
        if cleanup_timeout > 0:
            commands.adb(
                "shell",
                "rm",
                "-f",
                remote,
                check=False,
                timeout=cleanup_timeout,
            )
    raise RunnerError(f"could not capture v2 UI {relative}: {last_error}")


def wait_for_ui(
    commands: Commands,
    result_directory: Path,
    relative: str,
    predicate: Callable[[ET.Element], bool],
) -> ET.Element:
    deadline = time.monotonic() + base.UI_TIMEOUT_SECONDS
    while True:
        latest = capture_ui(
            commands,
            result_directory,
            relative,
            deadline=deadline,
        )
        base.remaining_timeout(
            deadline,
            maximum=1,
            description=f"v2 UI wait {relative}",
        )
        if predicate(latest):
            return latest
        time.sleep(
            min(
                0.25,
                base.remaining_timeout(
                    deadline,
                    maximum=0.25,
                    description=f"v2 UI wait {relative}",
                ),
            )
        )


def wait_for_ui_with_upward_swipes(
    commands: Commands,
    result_directory: Path,
    relative: str,
    predicate: Callable[[ET.Element], bool],
    *,
    anchor_predicate: Callable[[ET.Element], bool],
    maximum_swipes: int = 4,
) -> ET.Element:
    deadline = time.monotonic() + base.UI_TIMEOUT_SECONDS
    swipes = 0
    anchor_observed = False
    while True:
        root = capture_ui(
            commands,
            result_directory,
            relative,
            deadline=deadline,
        )
        base.remaining_timeout(
            deadline,
            maximum=1,
            description=f"v2 scrolling UI wait {relative}",
        )
        if not anchor_predicate(root):
            if anchor_observed:
                raise RunnerError(f"{relative} lost the expected screen anchor")
            time.sleep(
                min(
                    0.25,
                    base.remaining_timeout(
                        deadline,
                        maximum=0.25,
                        description=f"v2 screen anchor wait {relative}",
                    ),
                )
            )
            continue
        anchor_observed = True
        if predicate(root):
            return root
        if swipes >= maximum_swipes:
            raise RunnerError(
                f"{relative} did not expose the required content after scrolling"
            )
        commands.shell(
            "input",
            "swipe",
            "540",
            "2050",
            "540",
            "1700",
            "350",
            timeout=base.remaining_timeout(
                deadline,
                maximum=10,
                description=f"v2 scroll action {relative}",
            ),
        )
        swipes += 1
        time.sleep(
            min(
                0.5,
                base.remaining_timeout(
                    deadline,
                    maximum=0.5,
                    description=f"v2 scrolling UI wait {relative}",
                ),
            )
        )


def capture_follow_system_settings(
    commands: Commands,
    result_directory: Path,
    *,
    top_root: ET.Element,
    phase: str,
) -> ET.Element:
    if phase not in {"before-reboot", "after-reboot"}:
        raise RunnerError(f"unexpected Follow-system evidence phase: {phase!r}")
    base.tap_bounds(
        commands,
        base.clickable_bounds_for(
            top_root,
            content_description="Open navigation menu",
        ),
    )
    drawer_relative = f"ui/follow-system-{phase}-drawer.xml"
    drawer = wait_for_ui(
        commands,
        result_directory,
        drawer_relative,
        lambda root: base.has_node(
            root,
            text="Settings",
            package=base.APP_PACKAGE_PREFIX,
        ),
    )
    try:
        settings_bounds = base.clickable_bounds_for(drawer, text="Settings")
    except RunnerError:
        if not base.has_selected_ancestor(drawer, text="Settings"):
            raise
        commands.shell("input", "tap", "1030", "1200")
        base.wait_for_main_activity(commands)
    else:
        base.tap_bounds(commands, settings_bounds)
    settings_relative = f"ui/follow-system-{phase}.xml"
    return wait_for_ui_with_upward_swipes(
        commands,
        result_directory,
        settings_relative,
        lambda root: base.has_fully_visible_checked_node(
            root,
            text="Follow system language",
            package=base.APP_PACKAGE_PREFIX,
        ),
        anchor_predicate=lambda root: base.has_node(
            root,
            text="Pair AetherLink",
            package=base.APP_PACKAGE_PREFIX,
        ),
        maximum_swipes=12,
    )


def wait_for_background(commands: Commands, path: Path) -> bytes:
    deadline = time.monotonic() + 30
    last = b""
    while True:
        timeout = base.remaining_timeout(
            deadline,
            maximum=10,
            description="MainActivity background transition",
        )
        result = commands.adb(
            "shell",
            "dumpsys",
            "activity",
            "activities",
            text=False,
            timeout=timeout,
        )
        assert isinstance(result.stdout, bytes)
        assert isinstance(result.stderr, bytes)
        if result.returncode == 0 and not result.stderr and result.stdout:
            last = result.stdout
            if not base.main_activity_is_resumed(last.decode("utf-8", "replace")):
                path.write_bytes(last)
                return last
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunnerError("MainActivity did not enter the background before deadline")
        time.sleep(min(0.25, remaining))


def start_main_activity(commands: Commands) -> None:
    output = commands.shell(
        "am",
        "start",
        "-W",
        "-n",
        base_contract.ACTIVITY_NAME,
        timeout=60,
    )
    if "Status: ok" not in output or (
        f"Activity: {PACKAGE_NAME}/.MainActivity" not in output
        and f"Activity: {base_contract.ACTIVITY_NAME}" not in output
    ):
        raise RunnerError(f"am start -W did not prove MainActivity: {output!r}")
    base.wait_for_main_activity(commands)


def force_stop_package(commands: Commands) -> None:
    commands.shell("am", "force-stop", PACKAGE_NAME)
    deadline = time.monotonic() + 20
    while True:
        result = commands.adb("shell", "pidof", PACKAGE_NAME, check=False, text=False, timeout=5)
        assert isinstance(result.stdout, bytes)
        assert isinstance(result.stderr, bytes)
        if result.returncode == 1 and not result.stdout and not result.stderr:
            break
        if time.monotonic() >= deadline:
            raise RunnerError("force-stop did not remove the package process exactly")
        time.sleep(0.25)


def force_stop_and_start(commands: Commands) -> None:
    force_stop_package(commands)
    start_main_activity(commands)


def capture_exact_shell_line(
    commands: Commands,
    path: Path,
    *arguments: str,
    expected: bytes,
) -> bytes:
    result = commands.adb("shell", *arguments, text=False)
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    if result.returncode != 0 or result.stderr or result.stdout != expected:
        raise RunnerError(
            f"exact shell line failed for {arguments!r}; exit={result.returncode}, "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
    path.write_bytes(result.stdout)
    return result.stdout


def capture_package_path(commands: Commands, path: Path) -> tuple[bytes, str]:
    raw = capture_raw_adb(commands, path, "shell", "pm", "path", PACKAGE_NAME)
    if re.fullmatch(rb"package:(/[^\r\n]{1,4096}/base\.apk)\n", raw) is None:
        raise RunnerError(f"package path is not one exact installed base APK: {raw!r}")
    return raw, raw.decode("utf-8").removeprefix("package:").removesuffix("\n")


def pull_installed_apk(commands: Commands, device_path: str, output_path: Path) -> None:
    result = commands.adb("pull", device_path, str(output_path), text=False, timeout=180)
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    if result.returncode != 0 or not output_path.is_file():
        raise RunnerError(
            f"installed base APK pull failed; exit={result.returncode}, stderr={result.stderr!r}"
        )


def deep_idle_state(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RunnerError(f"deviceidle state is not UTF-8: {error}") from error
    matches = re.findall(
        r"(?m)^\s*mState=([A-Z_]+)(?:\s+mLightState=[A-Z_]+)?\s*$",
        text,
    )
    if len(matches) != 1:
        raise RunnerError(f"deviceidle state must expose one deep mState, found {matches!r}")
    return matches[0]


def deviceidle_unforce_receipt_states(raw: bytes) -> tuple[str, str]:
    match = DEVICEIDLE_UNFORCE_RECEIPT_RE.fullmatch(raw)
    if match is None:
        raise RunnerError(
            "deviceidle unforce receipt must be one exact state line followed by "
            "two false force-mode flags"
        )
    light_state = match.group(1).decode("ascii")
    deep_state = match.group(2).decode("ascii")
    if (
        light_state not in DEVICEIDLE_LIGHT_STATES
        or deep_state not in DEVICEIDLE_DEEP_STATES
    ):
        raise RunnerError(
            "deviceidle unforce receipt exposed an unknown light/deep state: "
            f"{light_state}/{deep_state}"
        )
    return light_state, deep_state


def enter_deep_idle(commands: Commands, output_directory: Path) -> None:
    commands.shell("dumpsys", "battery", "unplug")
    commands.shell("input", "keyevent", "KEYCODE_SLEEP")
    force = capture_raw_adb(
        commands,
        output_directory / "deviceidle-force-idle.txt",
        "shell",
        "dumpsys",
        "deviceidle",
        "force-idle",
        timeout=60,
    )
    if b"forced" not in force.lower() or b"idle" not in force.lower():
        raise RunnerError("deviceidle force-idle did not report a forced idle transition")
    state = capture_raw_adb(
        commands,
        output_directory / "deviceidle-state-forced.txt",
        "shell",
        "dumpsys",
        "deviceidle",
        timeout=60,
    )
    if deep_idle_state(state) != "IDLE":
        raise RunnerError("deviceidle did not reach deep IDLE")


def leave_deep_idle(commands: Commands, output_directory: Path) -> None:
    unforce = capture_raw_adb(
        commands,
        output_directory / "deviceidle-unforce.txt",
        "shell",
        "dumpsys",
        "deviceidle",
        "unforce",
        timeout=60,
    )
    deviceidle_unforce_receipt_states(unforce)
    commands.shell("dumpsys", "battery", "reset")
    commands.shell("input", "keyevent", "KEYCODE_WAKEUP", check=False)
    commands.shell("wm", "dismiss-keyguard", check=False)
    commands.shell("input", "keyevent", "82", check=False)
    state = capture_raw_adb(
        commands,
        output_directory / "deviceidle-state-unforced.txt",
        "shell",
        "dumpsys",
        "deviceidle",
        timeout=60,
    )
    if deep_idle_state(state) == "IDLE":
        raise RunnerError("deviceidle remained in deep IDLE after unforce")


def kill_background_process(
    commands: Commands,
    output_directory: Path,
    *,
    pid: int,
) -> None:
    if not (1 <= pid <= 2_147_483_647):
        raise RunnerError("target process PID must be inside the Android PID range")
    command = ["run-as", PACKAGE_NAME, "kill", "-9", str(pid)]
    result = commands.adb("shell", *command, check=False, text=False, timeout=30)
    assert isinstance(result, subprocess.CompletedProcess)
    receipt = completed_receipt(commands, command, result)
    write_canonical_json(output_directory / "process-kill-receipt.json", receipt)
    if result.returncode != 0 or result.stdout or result.stderr:
        raise RunnerError(f"same-UID SIGKILL must succeed silently, found {receipt!r}")


def wait_for_exact_pidof_absence(commands: Commands, output_directory: Path) -> None:
    deadline = time.monotonic() + 30
    command = ["pidof", PACKAGE_NAME]
    while True:
        timeout = base.remaining_timeout(
            deadline,
            maximum=5,
            description="post-SIGKILL pidof absence",
        )
        result = commands.adb(
            "shell",
            *command,
            check=False,
            text=False,
            timeout=timeout,
        )
        assert isinstance(result, subprocess.CompletedProcess)
        if result.returncode == 1 and not result.stdout and not result.stderr:
            write_canonical_json(
                output_directory / "pidof-absence-receipt.json",
                completed_receipt(commands, command, result),
            )
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunnerError("same-UID SIGKILL did not produce exact package pidof absence")
        time.sleep(min(0.25, remaining))


def owned_host_record(commands: Commands, *, serial: str, process_pid: int) -> dict[str, object]:
    records = base.host_emulator_inventory(commands)
    matches = [record for record in records if record.get("serial") == serial]
    if len(matches) != 1 or matches[0].get("pid") != process_pid:
        raise RunnerError("owned host emulator inventory does not bind the launched QEMU PID")
    return matches[0]


def wait_for_guest_reboot(
    commands: Commands,
    process: subprocess.Popen[bytes],
    output_directory: Path,
) -> None:
    if commands.serial is None:
        raise RunnerError("guest reboot requires the owned emulator serial")
    started_ns = time.monotonic_ns()
    observations: list[dict[str, object]] = []

    def observation(
        *,
        phase: str,
        command: list[str],
        result: subprocess.CompletedProcess[bytes],
        observed_state: str,
    ) -> dict[str, object]:
        if not isinstance(result.stdout, bytes) or not isinstance(result.stderr, bytes):
            raise RunnerError("reboot transport observations require byte streams")
        try:
            stdout = result.stdout.decode("utf-8")
            stderr = result.stderr.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RunnerError(f"reboot transport observation is not UTF-8: {error}") from error
        elapsed = (time.monotonic_ns() - started_ns) // 1_000_000
        if observations and elapsed <= observations[-1]["elapsedMilliseconds"]:
            raise RunnerError("reboot transition timestamps did not advance by a millisecond")
        return {
            "command": command,
            "elapsedMilliseconds": elapsed,
            "exitCode": result.returncode,
            "observedState": observed_state,
            "phase": phase,
            "serial": commands.serial,
            "stderr": stderr,
            "stdout": stdout,
        }

    before = commands.adb("get-state", check=False, text=False, timeout=10)
    assert isinstance(before, subprocess.CompletedProcess)
    if before.returncode != 0 or before.stdout != b"device\n" or before.stderr:
        raise RunnerError("owned emulator was not an exact device before reboot")
    observations.append(
        observation(
            phase="before_reboot",
            command=["get-state"],
            result=before,
            observed_state="device",
        )
    )

    command = ["reboot"]
    reboot = commands.adb(*command, check=False, text=False, timeout=30)
    assert isinstance(reboot, subprocess.CompletedProcess)
    write_canonical_json(
        output_directory / "adb-reboot-receipt.json",
        completed_receipt(commands, command, reboot),
    )
    if reboot.returncode != 0 or reboot.stdout or reboot.stderr:
        raise RunnerError("adb reboot must succeed with empty stdout and stderr")

    deadline = time.monotonic() + LIFECYCLE_TIMEOUT_SECONDS
    disconnected: subprocess.CompletedProcess[bytes] | None = None
    while True:
        if process.poll() is not None:
            raise RunnerError("owned QEMU process exited during guest reboot")
        timeout = base.remaining_timeout(
            deadline,
            maximum=10,
            description="guest reboot transport transition",
        )
        state = commands.adb("get-state", check=False, text=False, timeout=timeout)
        assert isinstance(state, subprocess.CompletedProcess)
        if not (
            state.returncode == 0
            and state.stdout == b"device\n"
            and not state.stderr
        ):
            disconnected = state
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunnerError("guest reboot did not disconnect before deadline")
        time.sleep(min(0.5, remaining))
    assert disconnected is not None
    observations.append(
        observation(
            phase="disconnected",
            command=["get-state"],
            result=disconnected,
            observed_state="absent",
        )
    )

    reconnected: subprocess.CompletedProcess[bytes] | None = None
    while True:
        if process.poll() is not None:
            raise RunnerError("owned QEMU process exited before guest reconnect")
        timeout = base.remaining_timeout(
            deadline,
            maximum=10,
            description="guest reboot reconnect",
        )
        state = commands.adb("get-state", check=False, text=False, timeout=timeout)
        assert isinstance(state, subprocess.CompletedProcess)
        if state.returncode == 0 and state.stdout == b"device\n" and not state.stderr:
            reconnected = state
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunnerError("guest reboot did not reconnect before deadline")
        time.sleep(min(0.5, remaining))
    assert reconnected is not None
    observations.append(
        observation(
            phase="reconnected",
            command=["get-state"],
            result=reconnected,
            observed_state="device",
        )
    )

    while True:
        timeout = base.remaining_timeout(
            deadline,
            maximum=10,
            description="post-reboot boot completion",
        )
        completed = commands.adb(
            "exec-out",
            "getprop",
            "sys.boot_completed",
            check=False,
            text=False,
            timeout=timeout,
        )
        assert isinstance(completed.stdout, bytes)
        assert isinstance(completed.stderr, bytes)
        if completed.returncode == 0 and completed.stdout == b"1\n" and not completed.stderr:
            (output_directory / "boot-completed-after-reboot.txt").write_bytes(
                completed.stdout
            )
            observations.append(
                observation(
                    phase="boot_completed",
                    command=["getprop", "sys.boot_completed"],
                    result=completed,
                    observed_state="1",
                )
            )
            write_canonical_json(
                output_directory / "reboot-transport-observations.json",
                observations,
            )
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunnerError("guest reboot did not complete before deadline")
        time.sleep(min(0.5, remaining))


def permission_dialog_has_app_prompt(root: ET.Element) -> bool:
    return any(
        node.attrib.get("package") in base.PERMISSION_CONTROLLER_PACKAGES
        and "AetherLink" in node.attrib.get("text", "")
        for node in root.iter("node")
    )


def permission_dialog_denial_bounds(
    root: ET.Element,
) -> tuple[int, int, int, int]:
    criteria = (
        {"resource_id_suffix": "permission_deny_button"},
        {"text": "Don’t allow"},
        {"text": "Don't allow"},
    )
    for package in base.PERMISSION_CONTROLLER_PACKAGES:
        for token in criteria:
            try:
                return base.fully_visible_clickable_bounds_for(
                    root,
                    package=package,
                    **token,
                )
            except RunnerError:
                continue
    raise RunnerError(
        "permission dialog did not expose one fully visible enabled denial action"
    )


def permission_dialog_denial_bounds_or_none(
    root: ET.Element,
) -> tuple[int, int, int, int] | None:
    try:
        return permission_dialog_denial_bounds(root)
    except RunnerError:
        return None


def camera_permission_dialog_denial(commands: Commands, output_directory: Path) -> None:
    entry = capture_ui(commands, output_directory, None)
    base.tap_bounds(commands, base.clickable_bounds_for(entry, text="Scan QR"))
    dialog = wait_for_ui(
        commands,
        output_directory,
        "ui/setup-camera-permission-dialog.xml",
        lambda root: permission_dialog_has_app_prompt(root)
        and permission_dialog_denial_bounds_or_none(root) is not None,
    )
    base.tap_bounds(commands, permission_dialog_denial_bounds(dialog))
    wait_for_ui(
        commands,
        output_directory,
        "ui/setup-camera-denied.xml",
        lambda root: base.has_node(
            root,
            text="Camera access is needed",
            package=base.APP_PACKAGE_PREFIX,
        ),
    )


def assert_settings_recovery_ui(
    commands: Commands,
    output_directory: Path,
    relative: str,
) -> None:
    entry = capture_ui(commands, output_directory, None)
    base.tap_bounds(commands, base.clickable_bounds_for(entry, text="Scan QR"))
    observed = wait_for_ui(
        commands,
        output_directory,
        relative,
        lambda root: (
            base.has_node(
                root,
                text="Camera permission is blocked",
                package=base.APP_PACKAGE_PREFIX,
            )
            and base.has_node(
                root,
                text="Open app settings",
                package=base.APP_PACKAGE_PREFIX,
            )
        ),
    )
    if any(
        node.attrib.get("package") in base.PERMISSION_CONTROLLER_PACKAGES
        for node in observed.iter()
    ):
        raise RunnerError("recorded camera state relaunched a system permission dialog")


def scenario(
    name: str,
    *,
    observations: dict[str, object],
) -> dict[str, object]:
    checks = dict(contract.SCENARIO_CHECKS).get(name)
    if checks is None:
        raise RunnerError(f"unknown v2 scenario {name!r}")
    return {
        "checks": {check: True for check in checks},
        "evidence": list(contract.SCENARIO_EVIDENCE[name]),
        "name": name,
        "observations": observations,
        "status": "passed",
    }


def assert_ui_pairing(
    commands: Commands,
    output_directory: Path,
    relative: str,
) -> ET.Element:
    return wait_for_ui(
        commands,
        output_directory,
        relative,
        lambda root: base.has_node(
            root,
            text="Pair AetherLink",
            package=base.APP_PACKAGE_PREFIX,
        ),
    )


def assert_future_data_update_required_ui(
    commands: Commands,
    output_directory: Path,
    relative: str,
) -> ET.Element:
    return wait_for_ui(
        commands,
        output_directory,
        relative,
        lambda root: (
            base.has_node(
                root,
                text="Pair AetherLink",
                package=base.APP_PACKAGE_PREFIX,
            )
            and base.has_node(
                root,
                text=FUTURE_DATA_UPDATE_REQUIRED_TEXT,
                package=base.APP_PACKAGE_PREFIX,
            )
        ),
    )


def assert_legacy_migration_ui(
    commands: Commands,
    output_directory: Path,
    relative: str,
) -> ET.Element:
    root = wait_for_ui(
        commands,
        output_directory,
        relative,
        lambda observed: base.has_node(
            observed,
            text="Pair AetherLink",
            package=base.APP_PACKAGE_PREFIX,
        ),
    )
    if base.has_node(
        root,
        text=FUTURE_DATA_UPDATE_REQUIRED_TEXT,
        package=base.APP_PACKAGE_PREFIX,
    ):
        raise RunnerError("legacy migration unexpectedly exposed update-required UI")
    return root


def capture_logcat_and_exit_info(
    commands: Commands,
    output_directory: Path,
    *,
    phase: str,
) -> tuple[bytes, bytes]:
    logcat = commands.adb("logcat", "-d", "-v", "threadtime", text=False)
    assert isinstance(logcat.stdout, bytes)
    assert isinstance(logcat.stderr, bytes)
    if logcat.returncode != 0 or logcat.stderr or not logcat.stdout:
        raise RunnerError(f"{phase} logcat capture failed")
    logcat_bytes = logcat.stdout
    (output_directory / f"logcat-{phase}.txt").write_bytes(logcat_bytes)
    if base.find_forbidden_logcat_lines(logcat_bytes.decode("utf-8", "replace")):
        raise RunnerError(f"AetherLink FATAL/ANR found in {phase} logcat")

    exit_info = commands.adb(
        "shell",
        "dumpsys",
        "activity",
        "exit-info",
        PACKAGE_NAME,
        text=False,
    )
    assert isinstance(exit_info.stdout, bytes)
    assert isinstance(exit_info.stderr, bytes)
    if exit_info.returncode != 0 or exit_info.stderr or not exit_info.stdout:
        raise RunnerError(f"{phase} exit-info capture failed")
    exit_info_bytes = exit_info.stdout
    (output_directory / f"exit-info-{phase}.txt").write_bytes(exit_info_bytes)
    if base.find_forbidden_exit_lines(exit_info_bytes.decode("utf-8", "replace")):
        raise RunnerError(f"AetherLink crash/ANR exit reason found in {phase} exit-info")
    return logcat_bytes, exit_info_bytes


def run_lane(
    *,
    sdk_root: Path,
    output_directory: Path,
    java_home: Path | None = None,
) -> Path:
    java_home = (java_home or base_contract.default_java_home()).resolve()
    base.ensure_host_and_sdk(sdk_root, java_home)
    run_id = output_directory.name
    if contract.RUN_ID_RE.fullmatch(run_id) is None:
        raise RunnerError("output directory basename must be the exact v2 run id")
    if output_directory.exists():
        raise RunnerError(f"output directory must not already exist: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=False)
    (output_directory / "ui").mkdir()

    started = utc_now()
    commands = Commands(sdk_root=sdk_root, java_home=java_home)
    source_before = contract.source_snapshot(ROOT)
    toolchain = {
        "adb": base_contract.sdk_tool_identity(sdk_root, Path("platform-tools/adb")),
        "adbVersion": base.command_version(commands, [str(commands.adb_path), "version"]),
        "emulator": base_contract.sdk_tool_identity(sdk_root, Path("emulator/emulator")),
        "emulatorVersion": base.command_version(
            commands,
            [str(commands.emulator_path), "-version"],
        ),
        "java": base_contract.java_tool_identity(java_home),
        "javaHome": str(java_home),
        "javaVersion": base.command_version(
            commands,
            [str(java_home / "bin/java"), "-version"],
        ),
        "qemuHeadless": base_contract.sdk_tool_identity(
            sdk_root,
            Path("emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"),
        ),
        "systemImage": base_contract.system_image_snapshot(sdk_root),
    }
    base.run_offline_debug_build(commands, output_directory / "gradle-build.log")

    port_lock: int | None = None
    temporary_root: Path | None = None
    process: subprocess.Popen[bytes] | None = None
    emulator_log = None
    preexisting_serials: tuple[str, ...] = ()
    preexisting_host_emulators: list[dict[str, object]] = []
    process_observations: list[dict[str, object]] = []
    scenarios: list[dict[str, object]] = []
    serial = ""
    port = 0
    model = ""
    width = height = density = 0
    doze_forced = False
    body_failed = False
    logcat_before_reboot_bytes = b""
    logcat_after_reboot_bytes = b""
    exit_info_before_reboot_bytes = b""
    exit_info_after_reboot_bytes = b""
    network_before = b""
    network_after = b""
    app_networking_before = b""
    app_networking_after = b""
    airplane_before = b""
    airplane_after = b""
    app_locales_before = b""
    built_record: dict[str, object] = {}
    installed_before_record: dict[str, object] = {}
    installed_after_record: dict[str, object] = {}
    boot_id_before = ""
    boot_id_after = ""
    preferences_before = b""
    try:
        preexisting_host_emulators = base.host_emulator_inventory(commands)
        write_canonical_json(
            output_directory / "pre-emulator-processes.json",
            preexisting_host_emulators,
        )
        port, port_lock, preexisting_serials, pre_adb = base.acquire_emulator_port(
            commands.adb_path,
            commands.environment,
            reserved_ports={int(record["port"]) for record in preexisting_host_emulators},
        )
        (output_directory / "pre-adb-devices.txt").write_text(pre_adb, encoding="utf-8")
        serial = f"emulator-{port}"
        commands.serial = serial
        temporary_root = Path(tempfile.mkdtemp(prefix=f"aetherlink-api36-1-v2-{port}-"))
        avd_name = f"AetherLink_API_36_1_{port}_{secrets.token_hex(4)}"
        avd_home = base.create_ephemeral_avd(
            temporary_root,
            sdk_root=sdk_root,
            avd_name=avd_name,
        )
        shutil.copyfile(
            avd_home / f"{avd_name}.avd/config.ini",
            output_directory / "avd-config.ini",
        )
        launch_environment = commands.environment.copy()
        launch_environment["ANDROID_AVD_HOME"] = str(avd_home)
        launch_command = base.emulator_launch_command(
            commands.emulator_path,
            avd_name=avd_name,
            port=port,
        )
        write_canonical_json(output_directory / "launch-argv.json", launch_command)
        emulator_log = (output_directory / "emulator.log").open("wb")
        process = subprocess.Popen(
            launch_command,
            cwd=ROOT,
            env=launch_environment,
            stdout=emulator_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        base.wait_for_boot(commands, process)
        base.verify_owned_emulator_identity(
            commands,
            process,
            expected_avd_name=avd_name,
        )
        base.configure_booted_device(commands)
        model, width, height, density = base.assert_screen_contract(commands)
        commands.shell("cmd", "locale", "set-device-locale", "en-US")
        if not commands.shell("cmd", "locale", "get-device-locale").startswith("en"):
            raise RunnerError("device locale did not converge to English")
        commands.shell("cmd", "connectivity", "airplane-mode", "enable")
        commands.shell("svc", "wifi", "disable")
        commands.shell("svc", "data", "disable")
        commands.shell("settings", "put", "system", "font_scale", "2.0")

        apk_path = ROOT / base_contract.DEBUG_APK_RELATIVE
        install = commands.adb("install", "-r", "-t", str(apk_path), timeout=180)
        assert isinstance(install.stdout, str)
        if "Success" not in install.stdout:
            raise RunnerError("Debug APK installation did not report Success")
        commands.shell("cmd", "connectivity", "set-chain3-enabled", "true")
        commands.shell(
            "cmd",
            "connectivity",
            "set-package-networking-enabled",
            "false",
            PACKAGE_NAME,
        )
        airplane_before = capture_exact_shell_line(
            commands,
            output_directory / "guest-airplane-before.txt",
            "cmd",
            "connectivity",
            "airplane-mode",
            expected=b"enabled\n",
        )
        app_networking_before = capture_exact_shell_line(
            commands,
            output_directory / "app-networking-before.txt",
            "cmd",
            "connectivity",
            "get-package-networking-enabled",
            PACKAGE_NAME,
            expected=(base_contract.APP_NETWORKING_DENIED_STATE + "\n").encode("ascii"),
        )
        network_before, _ = base.capture_network_state(
            commands,
            output_directory / "network-state-before.txt",
        )
        capture_exact_shell_line(
            commands,
            output_directory / "font-scale-before.txt",
            "settings",
            "get",
            "system",
            "font_scale",
            expected=b"2.0\n",
        )

        package_path_before_raw, package_path_before = capture_package_path(
            commands,
            output_directory / "package-path-before.txt",
        )
        pull_installed_apk(
            commands,
            package_path_before,
            output_directory / "installed-base-before.apk",
        )
        built_record = base_contract.file_record(
            apk_path,
            relative=base_contract.DEBUG_APK_RELATIVE.as_posix(),
        )
        installed_before_record = base_contract.file_record(
            output_directory / "installed-base-before.apk",
            relative="installed-base-before.apk",
        )
        if (built_record["sha256"], built_record["size"]) != (
            installed_before_record["sha256"],
            installed_before_record["size"],
        ):
            raise RunnerError("installed base APK differs from the built Debug APK")

        commands.shell("pm", "clear", PACKAGE_NAME)
        base.set_app_locales(commands, [])
        app_locales_before = capture_raw_adb(
            commands,
            output_directory / "app-locales-before.txt",
            "shell",
            "cmd",
            "locale",
            "get-app-locales",
            PACKAGE_NAME,
        )
        expected_app_locales = (
            f"Locales for {PACKAGE_NAME} for user 0 are []\n".encode("ascii")
        )
        if app_locales_before != expected_app_locales:
            raise RunnerError(
                "initial app locale evidence was not the exact package-bound empty "
                "Follow-system line"
            )
        commands.shell("pm", "revoke", PACKAGE_NAME, CAMERA_PERMISSION, check=False)
        commands.shell(
            "pm",
            "clear-permission-flags",
            PACKAGE_NAME,
            CAMERA_PERMISSION,
            "user-set",
            "user-fixed",
            check=False,
        )
        force_stop_and_start(commands)
        first_launch = assert_ui_pairing(
            commands,
            output_directory,
            "ui/setup-first-launch.xml",
        )
        capture_follow_system_settings(
            commands,
            output_directory,
            top_root=first_launch,
            phase="before-reboot",
        )
        force_stop_and_start(commands)
        camera_permission_dialog_denial(commands, output_directory)
        commands.shell(
            "pm",
            "set-permission-flags",
            PACKAGE_NAME,
            CAMERA_PERMISSION,
            "user-set",
            "user-fixed",
        )
        base.capture_camera_permission_state(
            commands,
            output_directory / "camera-permission-before.txt",
            expected_granted=False,
        )
        preferences_before = capture_camera_preferences(
            commands,
            output_directory / "camera-request-state-before.xml",
        )
        force_stop_and_start(commands)
        assert_settings_recovery_ui(
            commands,
            output_directory,
            "ui/setup-camera-settings-recovery.xml",
        )

        # Background -> deep Doze -> foreground recovery.
        force_stop_and_start(commands)
        assert_ui_pairing(commands, output_directory, "ui/background-before-doze.xml")
        boot_id_before = read_boot_id(commands, output_directory / "boot-id-before.txt")
        doze_before = capture_process_identity(
            commands,
            label="before_doze",
            boot_id=boot_id_before,
        )
        process_observations.append(doze_before)
        commands.shell("input", "keyevent", "KEYCODE_HOME")
        wait_for_background(
            commands,
            output_directory / "activity-background-before-doze.txt",
        )
        enter_deep_idle(commands, output_directory)
        doze_forced = True
        doze_during = capture_process_identity(
            commands,
            label="during_doze_unretained",
            boot_id=boot_id_before,
        )
        leave_deep_idle(commands, output_directory)
        doze_forced = False
        start_main_activity(commands)
        capture_activity(
            commands,
            output_directory / "activity-after-doze.txt",
            app_resumed=True,
        )
        assert_ui_pairing(commands, output_directory, "ui/background-after-doze.xml")
        doze_after = capture_process_identity(
            commands,
            label="after_doze",
            boot_id=boot_id_before,
        )
        process_observations.append(doze_after)
        doze_identities = [
            process_identity_key(record)
            for record in (doze_before, doze_during, doze_after)
        ]
        if len(set(doze_identities)) != 1:
            raise RunnerError("background/Doze recovery did not preserve one process identity")
        preferences_after_doze = capture_camera_preferences(
            commands,
            output_directory / "camera-request-state-after-doze.xml",
        )
        if preferences_after_doze != preferences_before:
            raise RunnerError("camera request state changed across background/Doze")
        scenarios.append(
            scenario(
                "background_doze_recovery",
                observations={
                    "bootId": boot_id_before,
                    "cameraRequestStateSha256": hashlib.sha256(preferences_before).hexdigest(),
                    "processIds": [process_pid(doze_before), process_pid(doze_after)],
                },
            )
        )

        # Background -> exact same-UID injected app-process SIGKILL -> cold recovery.
        kill_before = capture_process_identity(
            commands,
            label="before_kill",
            boot_id=boot_id_before,
        )
        process_observations.append(kill_before)
        commands.shell("input", "keyevent", "KEYCODE_HOME")
        wait_for_background(
            commands,
            output_directory / "activity-background-before-kill.txt",
        )
        kill_background_process(
            commands,
            output_directory,
            pid=process_pid(kill_before),
        )
        wait_for_exact_pidof_absence(commands, output_directory)
        preferences_after_kill = capture_camera_preferences(
            commands,
            output_directory / "camera-request-state-after-kill.xml",
        )
        if preferences_after_kill != preferences_before:
            raise RunnerError("camera request state changed across injected process kill")
        start_main_activity(commands)
        assert_ui_pairing(commands, output_directory, "ui/after-process-kill.xml")
        kill_after = capture_process_identity(
            commands,
            label="after_kill",
            boot_id=boot_id_before,
        )
        process_observations.append(kill_after)
        if process_identity_key(kill_before) == process_identity_key(kill_after):
            raise RunnerError("OS process kill recovery reused the killed process identity")
        scenarios.append(
            scenario(
                "background_process_kill_recovery",
                observations={
                    "bootId": boot_id_before,
                    "cameraRequestStateSha256": hashlib.sha256(preferences_before).hexdigest(),
                    "processIds": [process_pid(kill_before), process_pid(kill_after)],
                },
            )
        )

        # Full guest OS reboot inside the same owned QEMU process/ephemeral AVD.
        if process is None:
            raise RunnerError("owned QEMU process is unavailable before reboot")
        if read_boot_id(commands) != boot_id_before:
            raise RunnerError("kernel boot_id changed unexpectedly before the reboot scenario")
        reboot_before = capture_process_identity(
            commands,
            label="before_reboot",
            boot_id=boot_id_before,
        )
        process_observations.append(reboot_before)
        owned_before = owned_host_record(
            commands,
            serial=serial,
            process_pid=process.pid,
        )
        write_canonical_json(
            output_directory / "owned-emulator-before-reboot.json",
            owned_before,
        )
        (
            logcat_before_reboot_bytes,
            exit_info_before_reboot_bytes,
        ) = capture_logcat_and_exit_info(
            commands,
            output_directory,
            phase="before-reboot",
        )
        wait_for_guest_reboot(commands, process, output_directory)
        boot_id_after = read_boot_id(commands, output_directory / "boot-id-after.txt")
        if boot_id_after == boot_id_before:
            raise RunnerError("guest reboot did not change the kernel boot_id")
        base.verify_owned_emulator_identity(commands, process, expected_avd_name=avd_name)
        owned_after = owned_host_record(
            commands,
            serial=serial,
            process_pid=process.pid,
        )
        write_canonical_json(
            output_directory / "owned-emulator-after-reboot.json",
            owned_after,
        )
        if owned_after != owned_before:
            raise RunnerError("guest reboot replaced the owned QEMU host process identity")
        base.configure_booted_device(commands)
        commands.shell("cmd", "connectivity", "airplane-mode", "enable")
        commands.shell("svc", "wifi", "disable")
        commands.shell("svc", "data", "disable")
        commands.shell("cmd", "connectivity", "set-chain3-enabled", "true")
        commands.shell(
            "cmd",
            "connectivity",
            "set-package-networking-enabled",
            "false",
            PACKAGE_NAME,
        )
        airplane_after = capture_exact_shell_line(
            commands,
            output_directory / "guest-airplane-after-reboot.txt",
            "cmd",
            "connectivity",
            "airplane-mode",
            expected=b"enabled\n",
        )
        app_networking_after = capture_exact_shell_line(
            commands,
            output_directory / "app-networking-after-reboot.txt",
            "cmd",
            "connectivity",
            "get-package-networking-enabled",
            PACKAGE_NAME,
            expected=(base_contract.APP_NETWORKING_DENIED_STATE + "\n").encode("ascii"),
        )
        network_after, _ = base.capture_network_state(
            commands,
            output_directory / "network-state-after-reboot.txt",
        )
        capture_exact_shell_line(
            commands,
            output_directory / "font-scale-after-reboot.txt",
            "settings",
            "get",
            "system",
            "font_scale",
            expected=b"2.0\n",
        )
        app_locales_after = capture_raw_adb(
            commands,
            output_directory / "app-locales-after-reboot.txt",
            "shell",
            "cmd",
            "locale",
            "get-app-locales",
            PACKAGE_NAME,
        )
        if app_locales_after != app_locales_before:
            raise RunnerError("raw Follow-system app locale state changed across guest reboot")
        if app_locales_after != expected_app_locales:
            raise RunnerError(
                "post-reboot app locale evidence was not the exact package-bound "
                "empty Follow-system line"
            )
        if base.get_app_locales(commands) != []:
            raise RunnerError("Follow-system app locale did not survive guest reboot")
        package_path_after_raw, package_path_after = capture_package_path(
            commands,
            output_directory / "package-path-after-reboot.txt",
        )
        if package_path_after_raw != package_path_before_raw:
            raise RunnerError("installed package path changed across guest reboot")
        pull_installed_apk(
            commands,
            package_path_after,
            output_directory / "installed-base-after-reboot.apk",
        )
        installed_after_record = base_contract.file_record(
            output_directory / "installed-base-after-reboot.apk",
            relative="installed-base-after-reboot.apk",
        )
        if (
            installed_after_record["sha256"],
            installed_after_record["size"],
        ) != (
            built_record["sha256"],
            built_record["size"],
        ):
            raise RunnerError("installed APK bytes changed across guest reboot")
        preferences_after_reboot = capture_camera_preferences(
            commands,
            output_directory / "camera-request-state-after-reboot.xml",
        )
        if preferences_after_reboot != preferences_before:
            raise RunnerError("camera request state changed across guest reboot")
        base.capture_camera_permission_state(
            commands,
            output_directory / "camera-permission-after-reboot.txt",
            expected_granted=False,
        )
        start_main_activity(commands)
        after_reboot_ui = assert_ui_pairing(
            commands,
            output_directory,
            "ui/after-reboot.xml",
        )
        reboot_after = capture_process_identity(
            commands,
            label="after_reboot",
            boot_id=boot_id_after,
        )
        process_observations.append(reboot_after)
        capture_follow_system_settings(
            commands,
            output_directory,
            top_root=after_reboot_ui,
            phase="after-reboot",
        )
        force_stop_and_start(commands)
        assert_settings_recovery_ui(
            commands,
            output_directory,
            "ui/after-reboot-camera-settings-recovery.xml",
        )
        scenarios.append(
            scenario(
                "full_emulator_reboot_durable_state_recovery",
                observations={
                    "bootIds": [boot_id_before, boot_id_after],
                    "cameraPermissionGranted": False,
                    "cameraRequestStateSha256": hashlib.sha256(preferences_before).hexdigest(),
                    "fontScale": "2.0",
                    "installedApkSha256": installed_after_record["sha256"],
                    "localeTags": [],
                    "processIdAfterReboot": process_pid(reboot_after),
                },
            )
        )

        # A future-version local-data record must fail closed without rewriting
        # its bytes across two independently started app processes.
        force_stop_package(commands)
        future_seed = seed_future_runtime_local_data(commands)
        (output_directory / "runtime-local-store-future-version-seed.xml").write_bytes(
            future_seed
        )
        start_main_activity(commands)
        assert_future_data_update_required_ui(
            commands,
            output_directory,
            "ui/future-data-first-launch.xml",
        )
        future_first = capture_process_identity(
            commands,
            label="future_data_first_launch",
            boot_id=boot_id_after,
        )
        process_observations.append(future_first)
        future_after_first = capture_future_runtime_local_data(
            commands,
            output_directory,
            "runtime-local-store-after-future-version-first-launch.xml",
        )
        if future_after_first != future_seed:
            raise RunnerError("first future-data cold launch rewrote saved data")

        force_stop_package(commands)
        start_main_activity(commands)
        assert_future_data_update_required_ui(
            commands,
            output_directory,
            "ui/future-data-second-launch.xml",
        )
        future_second = capture_process_identity(
            commands,
            label="future_data_second_launch",
            boot_id=boot_id_after,
        )
        process_observations.append(future_second)
        future_after_second = capture_future_runtime_local_data(
            commands,
            output_directory,
            "runtime-local-store-after-future-version-second-launch.xml",
        )
        if future_after_second != future_seed:
            raise RunnerError("second future-data cold launch rewrote saved data")
        if process_identity_key(future_first) == process_identity_key(future_second):
            raise RunnerError("future-data cold launches reused one process identity")
        scenarios.append(
            scenario(
                "future_local_data_update_required_cold_launch_preservation",
                observations={
                    "coldLaunchCount": 2,
                    "localDataVersion": 2,
                    "processIds": [process_pid(future_first), process_pid(future_second)],
                    "savedDataSha256": hashlib.sha256(future_seed).hexdigest(),
                    "savedDataSize": len(future_seed),
                    "updateRequiredText": FUTURE_DATA_UPDATE_REQUIRED_TEXT,
                },
            )
        )

        # A versionless legacy record must migrate through the production
        # Activity/ViewModel/store path, preserve its values, and then remain
        # byte-stable across a second independently started app process.
        force_stop_package(commands)
        legacy_seed = seed_legacy_runtime_local_data(commands)
        (
            output_directory / "runtime-local-store-legacy-versionless-seed.xml"
        ).write_bytes(legacy_seed)
        start_main_activity(commands)
        legacy_after_first, legacy_first_facts = (
            wait_for_legacy_runtime_local_data_migration(
                commands,
                output_directory,
                "runtime-local-store-after-legacy-migration-first-launch.xml",
            )
        )
        assert_legacy_migration_ui(
            commands,
            output_directory,
            "ui/legacy-migration-first-launch.xml",
        )
        legacy_first = capture_process_identity(
            commands,
            label="legacy_migration_first_launch",
            boot_id=boot_id_after,
        )
        process_observations.append(legacy_first)

        force_stop_package(commands)
        start_main_activity(commands)
        assert_legacy_migration_ui(
            commands,
            output_directory,
            "ui/legacy-migration-second-launch.xml",
        )
        legacy_second = capture_process_identity(
            commands,
            label="legacy_migration_second_launch",
            boot_id=boot_id_after,
        )
        process_observations.append(legacy_second)
        legacy_after_second, legacy_second_facts = (
            capture_legacy_migrated_runtime_local_data(
                commands,
                output_directory,
                "runtime-local-store-after-legacy-migration-second-launch.xml",
            )
        )
        if legacy_after_second != legacy_after_first:
            raise RunnerError("second legacy-data cold launch changed migrated bytes")
        if legacy_second_facts != legacy_first_facts:
            raise RunnerError("second legacy-data cold launch changed migrated facts")
        if process_identity_key(legacy_first) == process_identity_key(legacy_second):
            raise RunnerError("legacy-data cold launches reused one process identity")
        scenarios.append(
            scenario(
                "legacy_versionless_local_data_migration_cold_launch_stability",
                observations={
                    "coldLaunchCount": 2,
                    "migratedDataSha256": legacy_first_facts["sha256"],
                    "migratedDataSize": legacy_first_facts["size"],
                    "migratedVersion": legacy_first_facts["version"],
                    "preservedAppTheme": legacy_first_facts["appTheme"],
                    "preservedComposerDraft": legacy_first_facts["composerDraft"],
                    "preservedTrustedRuntimeAutoReconnectEnabled": (
                        legacy_first_facts["trustedRuntimeAutoReconnectEnabled"]
                    ),
                    "processIds": [
                        process_pid(legacy_first),
                        process_pid(legacy_second),
                    ],
                    "sourceFormat": "versionless",
                },
            )
        )

        write_canonical_json(
            output_directory / "app-process-observations.json",
            process_observations,
        )
        (
            logcat_after_reboot_bytes,
            exit_info_after_reboot_bytes,
        ) = capture_logcat_and_exit_info(
            commands,
            output_directory,
            phase="after-reboot",
        )
    except BaseException:
        body_failed = True
        raise
    finally:
        doze_cleanup_error: RunnerError | None = None
        if doze_forced and commands.serial is not None:
            try:
                commands.shell(
                    "dumpsys",
                    "deviceidle",
                    "unforce",
                    check=False,
                    timeout=30,
                )
                commands.shell(
                    "dumpsys",
                    "battery",
                    "reset",
                    check=False,
                    timeout=30,
                )
            except RunnerError as error:
                doze_cleanup_error = error
        cleanup_completed = False
        try:
            base.cleanup_owned_emulator(process, temporary_root=temporary_root)
            cleanup_completed = True
        finally:
            if emulator_log is not None:
                emulator_log.close()
            if body_failed and cleanup_completed:
                base.release_emulator_port_lock(port_lock)
                port_lock = None
        if doze_cleanup_error is not None and not body_failed:
            base.release_emulator_port_lock(port_lock)
            port_lock = None
            raise RunnerError(
                f"forced Doze cleanup failed before emulator teardown: {doze_cleanup_error}"
            )

    try:
        post_adb, post_serials = base.wait_for_post_cleanup_devices(
            commands,
            owned_serial=serial,
            preexisting_serials=preexisting_serials,
        )
        (output_directory / "post-adb-devices.txt").write_text(post_adb, encoding="utf-8")
        post_host_emulators = base.host_emulator_inventory(commands)
        write_canonical_json(
            output_directory / "post-emulator-processes.json",
            post_host_emulators,
        )
    finally:
        base.release_emulator_port_lock(port_lock)
        port_lock = None

    process_exited = process is not None and process.poll() is not None
    temporary_removed = temporary_root is not None and not temporary_root.exists()
    owned_serial_absent = serial not in post_serials
    pre_by_serial = {record["serial"]: record for record in preexisting_host_emulators}
    post_by_serial = {record["serial"]: record for record in post_host_emulators}
    preexisting_preserved = (
        set(preexisting_serials).issubset(post_serials)
        and all(post_by_serial.get(key) == value for key, value in pre_by_serial.items())
    )
    if not (
        process_exited
        and temporary_removed
        and owned_serial_absent
        and serial not in post_by_serial
        and preexisting_preserved
    ):
        raise RunnerError("v2 cleanup did not preserve the exact emulator ownership boundary")

    source_after = contract.source_snapshot(ROOT)
    if source_after != source_before:
        raise RunnerError("Android v2 source bytes changed during the lifecycle run")
    if len(scenarios) != len(contract.SCENARIO_CHECKS):
        raise RunnerError("v2 scenario contract is incomplete")
    if [record.get("label") for record in process_observations] != list(
        contract.PROCESS_OBSERVATION_LABELS
    ):
        raise RunnerError("v2 process observation contract is incomplete")

    evidence = contract.evidence_manifest(output_directory)
    finished = utc_now()
    payload: dict[str, object] = {
        "artifact": {
            "built": built_record,
            "exactByteMatch": True,
            "installedAfterReboot": installed_after_record,
            "installedBefore": installed_before_record,
        },
        "build": {
            "command": list(base_contract.BUILD_COMMAND),
            "dependencyMode": "offline",
            "exitCode": 0,
        },
        "cleanup": {
            "ownedProcessExited": process_exited,
            "ownedSerialAbsent": owned_serial_absent,
            "postHostEmulators": post_host_emulators,
            "postSerials": post_serials,
            "preexistingHostEmulators": preexisting_host_emulators,
            "preexistingSerials": list(preexisting_serials),
            "preexistingSerialsPreserved": preexisting_preserved,
        },
        "contract": contract.CONTRACT,
        "device": {
            "abi": "arm64-v8a",
            "activity": base_contract.ACTIVITY_NAME,
            "apiLevel": 36,
            "appNetworkingDenied": True,
            "avdEphemeral": True,
            "guestAirplaneModeEnabled": True,
            "launchFlags": list(base_contract.LAUNCH_FLAGS),
            "model": model,
            "package": PACKAGE_NAME,
            "release": "16",
            "screenDensity": density,
            "screenHeight": height,
            "screenWidth": width,
            "systemImagePackage": base_contract.SYSTEM_IMAGE_PACKAGE,
        },
        "evidence": evidence,
        "exitInfo": {
            "afterReboot": {
                "forbiddenMatches": [],
                "lineCount": len(exit_info_after_reboot_bytes.splitlines()),
                "sha256": hashlib.sha256(exit_info_after_reboot_bytes).hexdigest(),
            },
            "beforeReboot": {
                "forbiddenMatches": [],
                "lineCount": len(exit_info_before_reboot_bytes.splitlines()),
                "sha256": hashlib.sha256(exit_info_before_reboot_bytes).hexdigest(),
            },
        },
        "logcat": {
            "afterReboot": {
                "fatalOrAnrMatches": [],
                "lineCount": len(logcat_after_reboot_bytes.splitlines()),
                "sha256": hashlib.sha256(logcat_after_reboot_bytes).hexdigest(),
            },
            "beforeReboot": {
                "fatalOrAnrMatches": [],
                "lineCount": len(logcat_before_reboot_bytes.splitlines()),
                "sha256": hashlib.sha256(logcat_before_reboot_bytes).hexdigest(),
            },
        },
        "networkIsolation": {
            "afterReboot": {
                "lineCount": len(network_after.splitlines()),
                "sha256": hashlib.sha256(network_after).hexdigest(),
                "validatedInternetMatches": [],
            },
            "appNetworkingAfterReboot": {
                "lineCount": len(app_networking_after.splitlines()),
                "sha256": hashlib.sha256(app_networking_after).hexdigest(),
                "value": base_contract.APP_NETWORKING_DENIED_STATE,
            },
            "appNetworkingBefore": {
                "lineCount": len(app_networking_before.splitlines()),
                "sha256": hashlib.sha256(app_networking_before).hexdigest(),
                "value": base_contract.APP_NETWORKING_DENIED_STATE,
            },
            "before": {
                "lineCount": len(network_before.splitlines()),
                "sha256": hashlib.sha256(network_before).hexdigest(),
                "validatedInternetMatches": [],
            },
            "guestAirplaneModeAfterReboot": {
                "lineCount": len(airplane_after.splitlines()),
                "sha256": hashlib.sha256(airplane_after).hexdigest(),
                "value": "enabled",
            },
            "guestAirplaneModeBefore": {
                "lineCount": len(airplane_before.splitlines()),
                "sha256": hashlib.sha256(airplane_before).hexdigest(),
                "value": "enabled",
            },
        },
        "nonClaims": list(contract.NON_CLAIMS),
        "run": {
            "durationSeconds": round((finished - started).total_seconds(), 3),
            "emulatorPort": port,
            "finishedAt": utc_text(finished),
            "hostArchitecture": "arm64",
            "hostPlatform": "darwin",
            "id": run_id,
            "serial": serial,
            "startedAt": utc_text(started),
        },
        "scenarios": scenarios,
        "schemaVersion": contract.SCHEMA_VERSION,
        "source": source_before,
        "status": "passed",
        "toolchain": toolchain,
    }
    failures = prepublication_payload_failures(
        payload,
        output_directory=output_directory,
        root=ROOT,
        sdk_root=sdk_root,
        java_home=java_home,
    )
    if failures:
        raise RunnerError("v2 result failed before write: " + "; ".join(failures))
    result_path = output_directory / "result.json"
    base.write_canonical_result(result_path, payload)
    failures = contract.result_failures(
        result_path,
        root=ROOT,
        sdk_root=sdk_root,
        java_home=java_home,
    )
    if failures:
        raise RunnerError("written v2 result failed readback: " + "; ".join(failures))
    return result_path


def default_sdk_root() -> Path:
    return base.default_sdk_root()


def default_run_id() -> str:
    return (
        "android-headless-api36-1-v2-"
        + utc_now().strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + secrets.token_hex(4)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path, default=default_sdk_root())
    parser.add_argument("--java-home", type=Path, default=base_contract.default_java_home())
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    output_directory = (
        args.output_directory.expanduser().resolve()
        if args.output_directory is not None
        else (ROOT / "build/qa" / default_run_id()).resolve()
    )
    try:
        result = run_lane(
            sdk_root=args.sdk_root.expanduser().resolve(),
            output_directory=output_directory,
            java_home=args.java_home.expanduser().resolve(),
        )
    except RunnerError as error:
        print(f"android headless lifecycle v2 failed: {error}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
