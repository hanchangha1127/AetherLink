#!/usr/bin/env python3
"""Run the bounded API 36.1 headless Android product lifecycle lane."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import Callable
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script import check_android_headless_emulator_product_lifecycle as contract


BOOT_TIMEOUT_SECONDS = 240
UI_TIMEOUT_SECONDS = 30
COMMAND_TIMEOUT_SECONDS = 120
PACKAGE_NAME = contract.PACKAGE_NAME
CAMERA_PERMISSION = "android.permission.CAMERA"
APP_PACKAGE_PREFIX = PACKAGE_NAME
PERMISSION_CONTROLLER_PACKAGES = (
    "com.android.permissioncontroller",
    "com.google.android.permissioncontroller",
)
SETTINGS_PACKAGE = "com.android.settings"


class RunnerError(RuntimeError):
    """Raised when a lifecycle assertion cannot be proved."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def output_tail(value: str, lines: int = 40) -> str:
    return "\n".join(value.splitlines()[-lines:])


def remaining_timeout(
    deadline: float,
    *,
    maximum: float,
    description: str,
) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RunnerError(f"{description} exceeded its absolute deadline")
    return min(maximum, remaining)


class Commands:
    def __init__(
        self,
        *,
        sdk_root: Path,
        java_home: Path,
        serial: str | None = None,
    ) -> None:
        self.sdk_root = sdk_root
        self.java_home = java_home
        self.adb_path = sdk_root / "platform-tools/adb"
        self.emulator_path = sdk_root / "emulator/emulator"
        self.serial = serial
        self.environment = os.environ.copy()
        self.environment.update(
            {
                "ANDROID_HOME": str(sdk_root),
                "ANDROID_SDK_ROOT": str(sdk_root),
                "JAVA_HOME": str(java_home),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
        )
        self.environment["PATH"] = (
            str(java_home / "bin") + os.pathsep + self.environment.get("PATH", "")
        )

    def run(
        self,
        command: list[str],
        *,
        check: bool = True,
        timeout: float = COMMAND_TIMEOUT_SECONDS,
        text: bool = True,
        environment: dict[str, str] | None = None,
        cwd: Path = ROOT,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=environment or self.environment,
                input=input_text if text else None,
                capture_output=True,
                text=text,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RunnerError(f"command could not complete: {command!r}: {error}") from error
        if check and completed.returncode != 0:
            stdout = completed.stdout.decode("utf-8", "replace") if isinstance(completed.stdout, bytes) else completed.stdout
            stderr = completed.stderr.decode("utf-8", "replace") if isinstance(completed.stderr, bytes) else completed.stderr
            detail = output_tail((stdout or "") + "\n" + (stderr or ""))
            raise RunnerError(
                f"command failed with exit {completed.returncode}: {command!r}\n{detail}"
            )
        return completed

    def adb(
        self,
        *arguments: str,
        check: bool = True,
        timeout: float = COMMAND_TIMEOUT_SECONDS,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        if self.serial is None:
            raise RunnerError("an explicit owned emulator serial is required for adb")
        return self.run(
            [str(self.adb_path), "-s", self.serial, *arguments],
            check=check,
            timeout=timeout,
            text=text,
        )

    def shell(
        self,
        *arguments: str,
        check: bool = True,
        timeout: float = COMMAND_TIMEOUT_SECONDS,
    ) -> str:
        completed = self.adb(
            "shell",
            *arguments,
            check=check,
            timeout=timeout,
            text=True,
        )
        assert isinstance(completed.stdout, str)
        return completed.stdout.strip()


def ensure_host_and_sdk(sdk_root: Path, java_home: Path) -> None:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise RunnerError("the reviewed lane requires a darwin/arm64 host")
    required = (
        sdk_root / "platform-tools/adb",
        sdk_root / "emulator/emulator",
        sdk_root / contract.SYSTEM_IMAGE_RELATIVE,
        java_home / "bin/java",
        ROOT / "gradlew",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RunnerError("required local input is missing: " + ", ".join(missing))
    if not os.access(java_home / "bin/java", os.X_OK):
        raise RunnerError("the reviewed Java launcher is not executable")


def parse_adb_devices(output: str) -> tuple[str, ...]:
    serials: list[str] = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and not fields[0].startswith("*"):
            serials.append(fields[0])
    return tuple(sorted(set(serials)))


def host_emulator_inventory(commands: Commands) -> list[dict[str, object]]:
    qemu_path = (
        commands.sdk_root
        / "emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"
    )
    result = commands.run(
        ["/bin/ps", "-axo", "pid=,command="],
        timeout=30,
    )
    assert isinstance(result.stdout, str)
    records: list[dict[str, object]] = []
    seen_ports: set[int] = set()
    for line in result.stdout.splitlines():
        match = re.match(r"\s*([0-9]+)\s+(.+)\Z", line)
        if match is None:
            continue
        pid = int(match.group(1))
        command = match.group(2)
        if command != str(qemu_path) and not command.startswith(str(qemu_path) + " "):
            continue
        port_match = re.search(r"(?:^|\s)-port\s+([0-9]+)(?:\s|$)", command)
        if port_match is None:
            raise RunnerError(f"headless emulator PID {pid} has no explicit console port")
        port = int(port_match.group(1))
        if port < 5554 or port > 5584 or port % 2 or port in seen_ports:
            raise RunnerError(
                f"headless emulator PID {pid} has an unsafe or duplicate port {port}"
            )
        seen_ports.add(port)
        started = commands.run(
            ["/bin/ps", "-p", str(pid), "-o", "lstart="],
            timeout=30,
        )
        confirmation = commands.run(
            ["/bin/ps", "-p", str(pid), "-o", "pid=,command="],
            timeout=30,
        )
        assert isinstance(started.stdout, str)
        assert isinstance(confirmation.stdout, str)
        confirmation_match = re.match(
            r"\s*([0-9]+)\s+(.+)\s*\Z",
            confirmation.stdout,
        )
        if (
            confirmation_match is None
            or int(confirmation_match.group(1)) != pid
            or confirmation_match.group(2).rstrip() != command
            or not started.stdout.strip()
        ):
            raise RunnerError(f"headless emulator PID {pid} changed during inventory")
        records.append(
            {
                "commandSha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "pid": pid,
                "port": port,
                "processStartedAt": started.stdout.strip(),
                "serial": f"emulator-{port}",
            }
        )
    return sorted(records, key=lambda record: (record["port"], record["pid"]))


def port_is_bindable(port: int) -> bool:
    sockets: list[socket.socket] = []
    try:
        for candidate in (port, port + 1):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(listener)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            listener.bind(("127.0.0.1", candidate))
        return True
    except OSError:
        return False
    finally:
        for listener in sockets:
            listener.close()


def acquire_emulator_port(
    adb_path: Path,
    environment: dict[str, str],
    *,
    reserved_ports: set[int],
) -> tuple[int, int, tuple[str, ...], str]:
    try:
        devices = subprocess.run(
            [str(adb_path), "devices", "-l"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RunnerError(f"cannot snapshot connected adb serials: {error}") from error
    preexisting = parse_adb_devices(devices.stdout)
    for port in range(5554, 5585, 2):
        serial = f"emulator-{port}"
        if port in reserved_ports or serial in preexisting or not port_is_bindable(port):
            continue
        lock_path = Path(tempfile.gettempdir()) / f"aetherlink-emulator-port-{port}.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(descriptor)
            continue
        if port_is_bindable(port):
            return port, descriptor, preexisting, devices.stdout
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    raise RunnerError("no unused locked even emulator port is available in 5554..5584")


def create_ephemeral_avd(
    temporary_root: Path,
    *,
    sdk_root: Path,
    avd_name: str,
) -> Path:
    avd_home = temporary_root / "avd"
    avd_directory = avd_home / f"{avd_name}.avd"
    avd_directory.mkdir(parents=True)
    pointer = (
        "avd.ini.encoding=UTF-8\n"
        f"path={avd_directory}\n"
        "target=android-36.1\n"
    )
    (avd_home / f"{avd_name}.ini").write_text(pointer, encoding="ascii")
    (avd_directory / "config.ini").write_bytes(
        contract.avd_config_bytes(avd_name)
    )
    return avd_home


def emulator_launch_command(
    emulator_path: Path,
    *,
    avd_name: str,
    port: int,
) -> list[str]:
    if port < 5554 or port > 5584 or port % 2:
        raise RunnerError("emulator port must be even and inside 5554..5584")
    if contract.AVD_NAME_RE.fullmatch(avd_name) is None:
        raise RunnerError("AVD name must bind the reviewed API 36.1 owned-run format")
    return [
        str(emulator_path),
        "-avd",
        avd_name,
        "-port",
        str(port),
        *contract.LAUNCH_FLAGS,
    ]


def wait_until(
    description: str,
    predicate: Callable[[], bool],
    *,
    timeout: int,
    process: subprocess.Popen[bytes] | None = None,
) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RunnerError(
                f"emulator exited with {process.returncode} while waiting for {description}"
            )
        try:
            if predicate():
                return
        except (RunnerError, OSError, ET.ParseError) as error:
            last_error = error
        time.sleep(1)
    suffix = f": {last_error}" if last_error is not None else ""
    raise RunnerError(f"timed out waiting for {description}{suffix}")


def command_version(commands: Commands, command: list[str]) -> str:
    completed = commands.run(command, timeout=30)
    assert isinstance(completed.stdout, str)
    assert isinstance(completed.stderr, str)
    value = "\n".join(
        line.rstrip() for line in (completed.stdout + completed.stderr).splitlines()
    ).strip()
    if not value:
        raise RunnerError(f"version command returned no output: {command!r}")
    return value


def run_offline_debug_build(commands: Commands, log_path: Path) -> None:
    completed = commands.run(
        list(contract.BUILD_COMMAND),
        timeout=900,
        text=False,
        check=False,
    )
    assert isinstance(completed.stdout, bytes)
    assert isinstance(completed.stderr, bytes)
    output = completed.stdout + completed.stderr
    log_path.write_bytes(output)
    if completed.returncode != 0:
        raise RunnerError(
            "offline Debug build failed:\n" + output_tail(output.decode("utf-8", "replace"))
        )
    if not contract.DEBUG_APK_RELATIVE.is_absolute() and not (
        ROOT / contract.DEBUG_APK_RELATIVE
    ).is_file():
        raise RunnerError("offline Debug build did not produce the expected APK")


def wait_for_boot(commands: Commands, process: subprocess.Popen[bytes]) -> None:
    wait_until(
        "adb device",
        lambda: commands.adb("get-state", check=False, timeout=10).stdout.strip() == "device",
        timeout=BOOT_TIMEOUT_SECONDS,
        process=process,
    )
    wait_until(
        "Android boot completion",
        lambda: commands.shell("getprop", "sys.boot_completed", check=False) == "1",
        timeout=BOOT_TIMEOUT_SECONDS,
        process=process,
    )


def verify_owned_emulator_identity(
    commands: Commands,
    process: subprocess.Popen[bytes],
    *,
    expected_avd_name: str,
) -> None:
    if process.poll() is not None:
        raise RunnerError("owned emulator process exited before identity verification")
    result = commands.adb("emu", "avd", "name", timeout=30)
    assert isinstance(result.stdout, str)
    names = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and line.strip() != "OK"
    ]
    if names != [expected_avd_name]:
        raise RunnerError(
            "adb serial does not belong to the exact owned AVD: "
            f"expected {expected_avd_name!r}, found {names!r}"
        )


def configure_booted_device(commands: Commands) -> None:
    commands.shell("settings", "put", "global", "device_provisioned", "1")
    commands.shell("settings", "put", "secure", "user_setup_complete", "1")
    commands.shell("settings", "put", "global", "window_animation_scale", "0")
    commands.shell("settings", "put", "global", "transition_animation_scale", "0")
    commands.shell("settings", "put", "global", "animator_duration_scale", "0")
    commands.shell("wm", "dismiss-keyguard", check=False)
    commands.shell("input", "keyevent", "82", check=False)


def parse_bounds(value: str) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]", value)
    if match is None:
        return None
    bounds = tuple(int(item) for item in match.groups())
    if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        return None
    return bounds  # type: ignore[return-value]


def node_matches(
    node: ET.Element,
    *,
    text: str | None = None,
    content_description: str | None = None,
    package: str | None = None,
    resource_id_suffix: str | None = None,
) -> bool:
    if text is not None and node.attrib.get("text") != text:
        return False
    if content_description is not None and node.attrib.get("content-desc") != content_description:
        return False
    if package is not None and node.attrib.get("package") != package:
        return False
    if resource_id_suffix is not None and not node.attrib.get("resource-id", "").endswith(
        resource_id_suffix
    ):
        return False
    return True


def has_node(root: ET.Element, **criteria: str) -> bool:
    return any(node_matches(node, **criteria) for node in root.iter())


def has_selected_ancestor(root: ET.Element, **criteria: str) -> bool:
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter():
        if not node_matches(node, **criteria):
            continue
        current: ET.Element | None = node
        while current is not None:
            if current.attrib.get("selected") == "true":
                return True
            current = parents.get(current)
    return False


def clickable_bounds_for(root: ET.Element, **criteria: str) -> tuple[int, int, int, int]:
    parents = {child: parent for parent in root.iter() for child in parent}
    candidates: list[tuple[int, tuple[int, int, int, int]]] = []
    for node in root.iter():
        if not node_matches(node, **criteria):
            continue
        current: ET.Element | None = node
        depth = 0
        while current is not None:
            if current.attrib.get("clickable") == "true":
                bounds = parse_bounds(current.attrib.get("bounds", ""))
                if bounds is not None:
                    area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
                    candidates.append((area + depth, bounds))
                    break
            current = parents.get(current)
            depth += 1
    if not candidates:
        raise RunnerError(f"no clickable UI node matched {criteria!r}")
    return min(candidates, key=lambda item: item[0])[1]


def fully_visible_clickable_bounds_for(
    root: ET.Element,
    **criteria: str,
) -> tuple[int, int, int, int]:
    parents = {child: parent for parent in root.iter() for child in parent}
    candidates: list[tuple[int, tuple[int, int, int, int]]] = []
    for node in root.iter():
        if not node_matches(node, **criteria):
            continue
        current: ET.Element | None = node
        clickable: ET.Element | None = None
        depth = 0
        while current is not None:
            if (
                current.attrib.get("clickable") == "true"
                and current.attrib.get("enabled") == "true"
            ):
                clickable = current
                break
            current = parents.get(current)
            depth += 1
        if clickable is None:
            continue
        bounds = parse_bounds(clickable.attrib.get("bounds", ""))
        if bounds is None:
            continue
        viewports: list[tuple[int, int, int, int]] = []
        invalid_viewport = False
        current = parents.get(clickable)
        while current is not None:
            if current.attrib.get("scrollable") == "true":
                viewport = parse_bounds(current.attrib.get("bounds", ""))
                if viewport is None:
                    invalid_viewport = True
                    break
                viewports.append(viewport)
            current = parents.get(current)
        if invalid_viewport or not (
            0 <= bounds[0] < bounds[2] <= 1080
            and 0 <= bounds[1] < bounds[3] <= 2400
        ):
            continue
        if any(
            not (
                viewport[0] <= bounds[0]
                and viewport[1] <= bounds[1]
                and bounds[2] <= viewport[2]
                and bounds[3] <= viewport[3]
            )
            for viewport in viewports
        ):
            continue
        area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
        candidates.append((area + depth, bounds))
    if not candidates:
        raise RunnerError(f"no fully visible clickable UI node matched {criteria!r}")
    return min(candidates, key=lambda item: item[0])[1]


def has_fully_visible_clickable_node(root: ET.Element, **criteria: str) -> bool:
    try:
        fully_visible_clickable_bounds_for(root, **criteria)
    except RunnerError:
        return False
    return True


def visible_bounds_for(root: ET.Element, **criteria: str) -> tuple[int, int, int, int]:
    candidates: list[tuple[int, tuple[int, int, int, int]]] = []
    for node in root.iter():
        if not node_matches(node, **criteria) or node.attrib.get("enabled") != "true":
            continue
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if bounds is None:
            continue
        area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
        candidates.append((area, bounds))
    if not candidates:
        raise RunnerError(f"no visible enabled UI node matched {criteria!r}")
    return min(candidates, key=lambda item: item[0])[1]


def tap_bounds(commands: Commands, bounds: tuple[int, int, int, int]) -> None:
    x = (bounds[0] + bounds[2]) // 2
    y = (bounds[1] + bounds[3]) // 2
    commands.shell("input", "tap", str(x), str(y))


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
        raise RunnerError(f"unexpected UI evidence path: {relative}")
    local_path = result_directory / relative if relative is not None else None
    if local_path is not None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
    stem = Path(relative).stem if relative is not None else "ephemeral"
    remote = (
        f"/sdcard/aetherlink-{stem}-{secrets.token_hex(8)}.xml"
    )
    last_error: Exception | None = None
    try:
        for _ in range(10):
            rm_timeout = (
                remaining_timeout(
                    deadline,
                    maximum=10,
                    description=f"UI capture {relative}",
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
                timeout=rm_timeout,
            )
            dump_timeout = (
                remaining_timeout(
                    deadline,
                    maximum=20,
                    description=f"UI capture {relative}",
                )
                if deadline is not None
                else 20
            )
            completed = commands.adb(
                "shell",
                "uiautomator",
                "dump",
                remote,
                check=False,
                timeout=dump_timeout,
            )
            if completed.returncode == 0:
                cat_timeout = (
                    remaining_timeout(
                        deadline,
                        maximum=20,
                        description=f"UI capture {relative}",
                    )
                    if deadline is not None
                    else 20
                )
                raw_result = commands.adb(
                    "exec-out",
                    "cat",
                    remote,
                    check=False,
                    text=False,
                    timeout=cat_timeout,
                )
                assert isinstance(raw_result.stdout, bytes)
                raw = raw_result.stdout
                try:
                    parsed = ET.fromstring(raw)
                except ET.ParseError as error:
                    last_error = error
                else:
                    if deadline is not None:
                        remaining_timeout(
                            deadline,
                            maximum=1,
                            description=f"UI capture {relative}",
                        )
                    if local_path is not None:
                        local_path.write_bytes(raw)
                    return parsed
            if deadline is None:
                time.sleep(1)
            else:
                time.sleep(
                    min(
                        1,
                        remaining_timeout(
                            deadline,
                            maximum=1,
                            description=f"UI capture {relative}",
                        ),
                    )
                )
    finally:
        if deadline is None:
            commands.adb("shell", "rm", "-f", remote, check=False, timeout=10)
        else:
            cleanup_remaining = deadline - time.monotonic()
            if cleanup_remaining > 0:
                commands.adb(
                    "shell",
                    "rm",
                    "-f",
                    remote,
                    check=False,
                    timeout=min(10, cleanup_remaining),
                )
    raise RunnerError(f"could not capture {relative}: {last_error}")


def wait_for_ui(
    commands: Commands,
    result_directory: Path,
    relative: str,
    predicate: Callable[[ET.Element], bool],
) -> ET.Element:
    deadline = time.monotonic() + UI_TIMEOUT_SECONDS
    while True:
        latest = capture_ui(
            commands,
            result_directory,
            relative,
            deadline=deadline,
        )
        remaining_timeout(
            deadline,
            maximum=1,
            description=f"UI wait {relative}",
        )
        if predicate(latest):
            return latest
        time.sleep(
            min(
                0.25,
                remaining_timeout(
                    deadline,
                    maximum=0.25,
                    description=f"UI wait {relative}",
                ),
            )
        )


def wait_for_ui_with_upward_swipes(
    commands: Commands,
    result_directory: Path,
    relative: str,
    predicate: Callable[[ET.Element], bool],
    *,
    anchor_predicate: Callable[[ET.Element], bool] | None = None,
    maximum_swipes: int = 12,
) -> ET.Element:
    deadline = time.monotonic() + UI_TIMEOUT_SECONDS
    swipes = 0
    anchor_observed = anchor_predicate is None
    while True:
        root = capture_ui(
            commands,
            result_directory,
            relative,
            deadline=deadline,
        )
        remaining_timeout(
            deadline,
            maximum=1,
            description=f"scrolling UI wait {relative}",
        )
        if anchor_predicate is not None and not anchor_predicate(root):
            if anchor_observed:
                raise RunnerError(f"{relative} lost the expected screen anchor")
            time.sleep(
                min(
                    0.25,
                    remaining_timeout(
                        deadline,
                        maximum=0.25,
                        description=f"screen anchor wait {relative}",
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
            timeout=remaining_timeout(
                deadline,
                maximum=10,
                description=f"scroll action {relative}",
            ),
        )
        swipes += 1
        time.sleep(
            min(
                0.5,
                remaining_timeout(
                    deadline,
                    maximum=0.5,
                    description=f"scrolling UI wait {relative}",
                ),
            )
        )


def open_language_settings(
    commands: Commands,
    result_directory: Path,
    *,
    top_root: ET.Element,
    navigation_description: str,
    settings_label: str,
    drawer_relative: str,
    settings_relative: str,
    language_tokens: tuple[str, ...],
    actionable_tokens: tuple[str, ...] = (),
    settings_anchor_text: str,
) -> tuple[ET.Element, ET.Element]:
    tap_bounds(
        commands,
        clickable_bounds_for(
            top_root,
            content_description=navigation_description,
        ),
    )
    drawer = wait_for_ui(
        commands,
        result_directory,
        drawer_relative,
        lambda root: has_node(root, text=settings_label, package=APP_PACKAGE_PREFIX),
    )
    try:
        settings_bounds = clickable_bounds_for(drawer, text=settings_label)
    except RunnerError:
        if not has_selected_ancestor(drawer, text=settings_label):
            raise
        commands.shell("input", "tap", "1030", "1200")
        wait_for_main_activity(commands)
    else:
        tap_bounds(commands, settings_bounds)
    settings = wait_for_ui_with_upward_swipes(
        commands,
        result_directory,
        settings_relative,
        lambda root: all(
            has_node(root, text=token, package=APP_PACKAGE_PREFIX)
            for token in language_tokens
        )
        and all(
            has_fully_visible_clickable_node(
                root,
                text=token,
                package=APP_PACKAGE_PREFIX,
            )
            for token in actionable_tokens
        ),
        anchor_predicate=lambda root: has_node(
            root,
            text=settings_anchor_text,
            package=APP_PACKAGE_PREFIX,
        ),
    )
    return drawer, settings


def top_activity(commands: Commands) -> str:
    return commands.shell("dumpsys", "activity", "activities", timeout=30)


def main_activity_is_resumed(activity_dump: str) -> bool:
    component = f"{PACKAGE_NAME}/.MainActivity"
    return any(
        "topResumedActivity=" in line
        and re.search(rf"(?:^|\s){re.escape(component)}(?:\s|$|\}})", line)
        is not None
        for line in activity_dump.splitlines()
    )


def wait_for_main_activity(commands: Commands) -> None:
    wait_until(
        "AetherLink MainActivity resume",
        lambda: main_activity_is_resumed(top_activity(commands)),
        timeout=30,
    )


def process_id(
    commands: Commands,
    *,
    observation_label: str | None = None,
    observations: list[dict[str, object]] | None = None,
) -> int:
    result = commands.adb(
        "shell",
        "pidof",
        PACKAGE_NAME,
        check=False,
        text=False,
    )
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    if result.returncode != 0 or result.stderr:
        raise RunnerError(
            "AetherLink pidof must exit zero with empty stderr; "
            f"exit={result.returncode}, stderr={result.stderr!r}"
        )
    raw_output = result.stdout
    if re.fullmatch(rb"[1-9][0-9]{0,9}\n", raw_output) is None:
        raise RunnerError(
            f"expected one exact AetherLink pidof output line, found {raw_output!r}"
        )
    output = raw_output.decode("ascii")
    pid = int(output.removesuffix("\n"))
    if pid > 2_147_483_647:
        raise RunnerError(f"AetherLink PID exceeds the Android PID range: {pid}")
    proc_path = f"/proc/{pid}"
    stat_before_result = commands.adb(
        "exec-out",
        "cat",
        f"{proc_path}/stat",
        text=False,
    )
    cmdline_result = commands.adb(
        "exec-out",
        "cat",
        f"{proc_path}/cmdline",
        text=False,
    )
    stat_after_result = commands.adb(
        "exec-out",
        "cat",
        f"{proc_path}/stat",
        text=False,
    )
    assert isinstance(stat_before_result.stdout, bytes)
    assert isinstance(cmdline_result.stdout, bytes)
    assert isinstance(stat_after_result.stdout, bytes)
    stat_before_raw = stat_before_result.stdout
    cmdline_raw = cmdline_result.stdout
    stat_after_raw = stat_after_result.stdout
    package_bytes = PACKAGE_NAME.encode("ascii")
    if (
        not (1 <= len(cmdline_raw) <= 4096)
        or not cmdline_raw.startswith(package_bytes + b"\0")
        or cmdline_raw.rstrip(b"\0") != package_bytes
    ):
        raise RunnerError(
            f"AetherLink /proc/{pid}/cmdline did not identify the exact package"
        )
    def parse_stat(raw: bytes, phase: str) -> tuple[str, int]:
        try:
            stat_text = raw.decode("ascii")
        except UnicodeDecodeError as error:
            raise RunnerError(
                f"AetherLink /proc/{pid}/stat {phase} is not ASCII: {error}"
            ) from error
        if not (1 <= len(stat_text) <= 4096):
            raise RunnerError(
                f"AetherLink /proc/{pid}/stat {phase} is not bounded text"
            )
        stat_match = re.fullmatch(
            rf"{pid} \(([^()\n]{{1,128}})\) ([^\n]+)\n",
            stat_text,
        )
        if stat_match is None:
            raise RunnerError(
                f"AetherLink /proc/{pid}/stat {phase} did not bind the exact PID"
            )
        stat_fields = stat_match.group(2).split()
        if (
            len(stat_fields) < 20
            or re.fullmatch(r"[1-9][0-9]{0,19}", stat_fields[19]) is None
        ):
            raise RunnerError(
                f"AetherLink /proc/{pid}/stat {phase} has no bounded start ticks"
            )
        start_ticks = int(stat_fields[19])
        if start_ticks > 9_223_372_036_854_775_807:
            raise RunnerError(
                f"AetherLink /proc/{pid}/stat {phase} start ticks exceed int64"
            )
        return stat_text, start_ticks

    stat_before_text, stat_before_ticks = parse_stat(stat_before_raw, "before")
    stat_after_text, stat_after_ticks = parse_stat(stat_after_raw, "after")
    if stat_before_ticks != stat_after_ticks:
        raise RunnerError(
            f"AetherLink /proc/{pid} identity changed while reading cmdline"
        )
    process_start_ticks = stat_before_ticks
    if (observation_label is None) != (observations is None):
        raise RunnerError("process observation label and sink must be provided together")
    if observation_label is not None and observations is not None:
        index = len(observations)
        if (
            index >= len(contract.PROCESS_OBSERVATION_LABELS)
            or observation_label != contract.PROCESS_OBSERVATION_LABELS[index]
        ):
            raise RunnerError(
                f"unexpected process observation label at index {index}: "
                f"{observation_label!r}"
            )
        if commands.serial is None:
            raise RunnerError("process observation requires the owned emulator serial")
        observations.append(
            {
                "command": ["pidof", PACKAGE_NAME],
                "label": observation_label,
                "procCmdlineBase64": base64.b64encode(cmdline_raw).decode("ascii"),
                "procCmdlineCommand": ["cat", f"{proc_path}/cmdline"],
                "procStatAfterCommand": ["cat", f"{proc_path}/stat"],
                "procStatAfterStdout": stat_after_text,
                "procStatBeforeCommand": ["cat", f"{proc_path}/stat"],
                "procStatBeforeStdout": stat_before_text,
                "processStartTicks": process_start_ticks,
                "serial": commands.serial,
                "stdout": output,
            }
        )
    return pid


def force_stop_and_launch(
    commands: Commands,
    *,
    observation_label: str | None = None,
    observations: list[dict[str, object]] | None = None,
) -> int:
    commands.shell("am", "force-stop", PACKAGE_NAME)
    wait_until(
        "AetherLink process stop",
        lambda: not commands.shell("pidof", PACKAGE_NAME, check=False),
        timeout=20,
    )
    start_output = commands.shell(
        "am", "start", "-W", "-n", contract.ACTIVITY_NAME, timeout=60
    )
    if "Status: ok" not in start_output or (
        f"Activity: {PACKAGE_NAME}/.MainActivity" not in start_output
        and f"Activity: {contract.ACTIVITY_NAME}" not in start_output
    ):
        raise RunnerError(f"am start -W did not prove the exact activity: {start_output!r}")
    wait_for_main_activity(commands)
    return process_id(
        commands,
        observation_label=observation_label,
        observations=observations,
    )


def get_app_locales(
    commands: Commands,
    *,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
) -> list[str]:
    output = commands.shell(
        "cmd",
        "locale",
        "get-app-locales",
        PACKAGE_NAME,
        timeout=timeout,
    )
    match = re.search(r"\[([^\]]*)\]", output)
    if match is None:
        raise RunnerError(f"unexpected app-locale output: {output!r}")
    body = match.group(1).strip()
    return [] if not body else [item.strip() for item in body.split(",")]


def wait_for_app_locales(
    commands: Commands,
    expected: list[str],
    *,
    description: str,
    timeout: float = 20,
) -> list[str]:
    deadline = time.monotonic() + timeout
    last_observed: list[str] | None = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        remaining = min(COMMAND_TIMEOUT_SECONDS, remaining)
        last_observed = get_app_locales(commands, timeout=remaining)
        if time.monotonic() >= deadline:
            break
        if last_observed == expected:
            return last_observed
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.25, remaining))
    raise RunnerError(
        f"timed out waiting for {description}; expected {expected!r}, "
        f"last observed {last_observed!r}"
    )


def set_app_locales(commands: Commands, tags: list[str]) -> None:
    arguments = ["cmd", "locale", "set-app-locales", PACKAGE_NAME]
    if tags:
        arguments.extend(("--locales", ",".join(tags)))
    commands.shell(*arguments)
    observed = get_app_locales(commands)
    if observed != tags:
        raise RunnerError(f"app locales must be {tags!r}, found {observed!r}")


def capture_camera_permission_state(
    commands: Commands,
    path: Path,
    *,
    expected_granted: bool,
) -> bytes:
    result = commands.adb(
        "shell",
        "dumpsys",
        "package",
        PACKAGE_NAME,
        text=False,
        timeout=60,
    )
    assert isinstance(result.stdout, bytes)
    raw = result.stdout
    if not (1 <= len(raw) <= 4 * 1024 * 1024):
        raise RunnerError("CAMERA dumpsys package output must be nonempty and at most 4 MiB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RunnerError(f"CAMERA dumpsys package output is not UTF-8: {error}") from error
    matches = re.findall(
        r"(?m)^[ \t]*android\.permission\.CAMERA: granted=(true|false)(?:,[^\r\n]*)?\r?$",
        text,
    )
    if len(matches) != 1:
        raise RunnerError(
            "CAMERA permission state must appear exactly once in dumpsys package; "
            f"found {len(matches)}"
        )
    expected = "true" if expected_granted else "false"
    if matches[0] != expected:
        raise RunnerError(
            f"CAMERA permission must be granted={expected}, found granted={matches[0]}"
        )
    path.write_bytes(raw)
    return raw


def assert_screen_contract(commands: Commands) -> tuple[str, int, int, int]:
    model = commands.shell("getprop", "ro.product.model")
    api_level = commands.shell("getprop", "ro.build.version.sdk")
    release = commands.shell("getprop", "ro.build.version.release")
    abi = commands.shell("getprop", "ro.product.cpu.abi")
    if (api_level, release, abi) != ("36", "16", "arm64-v8a"):
        raise RunnerError(
            f"unexpected emulator platform: api={api_level}, release={release}, abi={abi}"
        )
    size = commands.shell("wm", "size")
    density = commands.shell("wm", "density")
    size_match = re.search(r"Physical size: ([0-9]+)x([0-9]+)", size)
    density_match = re.search(r"Physical density: ([0-9]+)", density)
    if size_match is None or density_match is None:
        raise RunnerError(f"cannot read screen contract: {size!r}, {density!r}")
    width, height = (int(value) for value in size_match.groups())
    density_value = int(density_match.group(1))
    if (width, height, density_value) != (1080, 2400, 420):
        raise RunnerError(
            f"screen contract must be 1080x2400@420, found {width}x{height}@{density_value}"
        )
    return model, width, height, density_value


def scenario(
    name: str,
    *,
    evidence: list[str],
    observations: dict[str, object],
) -> dict[str, object]:
    expected = dict(contract.SCENARIO_CHECKS).get(name)
    if expected is None:
        raise RunnerError(f"unknown scenario name: {name}")
    return {
        "checks": {check: True for check in expected},
        "evidence": evidence,
        "name": name,
        "observations": observations,
        "status": "passed",
    }


def find_forbidden_logcat_lines(text: str) -> list[str]:
    lines = text.splitlines()
    forbidden: list[str] = []
    for index, line in enumerate(lines):
        if re.search(rf"ANR in {re.escape(PACKAGE_NAME)}|am_anr.*{re.escape(PACKAGE_NAME)}", line):
            forbidden.append(line)
        if "FATAL EXCEPTION:" in line:
            window = "\n".join(lines[index : index + 8])
            if PACKAGE_NAME in window:
                forbidden.append(line)
        if re.search(rf"am_crash.*{re.escape(PACKAGE_NAME)}", line):
            forbidden.append(line)
    return forbidden


def find_forbidden_exit_lines(text: str) -> list[str]:
    return contract.app_exit_failure_lines(text)


def capture_network_state(
    commands: Commands,
    path: Path,
) -> tuple[bytes, list[str]]:
    result = commands.adb(
        "shell",
        "dumpsys",
        "connectivity",
        text=False,
        timeout=60,
    )
    assert isinstance(result.stdout, bytes)
    raw = result.stdout
    path.write_bytes(raw)
    matches = contract.validated_network_lines(raw.decode("utf-8", "replace"))
    if matches:
        raise RunnerError(
            "guest still exposes a validated Internet network: "
            + "; ".join(matches[:8])
        )
    return raw, matches


def capture_exact_shell_line(
    commands: Commands,
    path: Path,
    *arguments: str,
    expected: str,
    label: str,
) -> bytes:
    result = commands.adb("shell", *arguments, text=False)
    assert isinstance(result.stdout, bytes)
    raw = result.stdout
    path.write_bytes(raw)
    expected_raw = (expected + "\n").encode("ascii")
    if raw != expected_raw:
        found = raw.decode("utf-8", "backslashreplace")
        raise RunnerError(
            f"{label} must equal the one exact {expected!r} line, found {found!r}"
        )
    return raw


def write_canonical_result(path: Path, payload: dict[str, object]) -> None:
    raw = contract.canonical_json_bytes(payload)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def cleanup_owned_emulator(
    process: subprocess.Popen[bytes] | None,
    *,
    temporary_root: Path | None,
) -> None:
    failures: list[str] = []
    if process is not None:
        process_group: int | None = None
        if process.poll() is None:
            try:
                process_group = os.getpgid(process.pid)
            except ProcessLookupError:
                process.poll()
            except OSError as error:
                failures.append(f"owned emulator process-group lookup failed: {error}")
            if process_group is not None:
                if process_group != process.pid:
                    failures.append(
                        "owned emulator process is not the leader of its isolated group"
                    )
                else:
                    try:
                        os.killpg(process_group, signal.SIGTERM)
                    except ProcessLookupError:
                        process.poll()
                    except OSError as error:
                        failures.append(f"owned emulator SIGTERM failed: {error}")
        try:
            if process.poll() is None:
                process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            if process_group == process.pid:
                try:
                    os.killpg(process_group, signal.SIGKILL)
                    process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired) as error:
                    failures.append(f"owned emulator SIGKILL failed: {error}")
            else:
                failures.append("owned emulator remained alive without a safe process group")
        except OSError as error:
            failures.append(f"owned emulator wait failed: {error}")
        if process.poll() is None:
            failures.append("owned emulator process did not exit")
    process_exited = process is None or process.poll() is not None
    if process_exited:
        try:
            if temporary_root is not None and temporary_root.exists():
                shutil.rmtree(temporary_root)
        except OSError as error:
            failures.append(f"temporary AVD cleanup failed: {error}")
    if failures:
        raise RunnerError("; ".join(failures))


def release_emulator_port_lock(port_lock: int | None) -> None:
    if port_lock is None:
        return
    failures: list[str] = []
    try:
        fcntl.flock(port_lock, fcntl.LOCK_UN)
    except OSError as error:
        failures.append(f"emulator port unlock failed: {error}")
    finally:
        try:
            os.close(port_lock)
        except OSError as error:
            failures.append(f"emulator port descriptor close failed: {error}")
    if failures:
        raise RunnerError("; ".join(failures))


def wait_for_post_cleanup_devices(
    commands: Commands,
    *,
    owned_serial: str,
    preexisting_serials: tuple[str, ...],
    timeout: int = 30,
) -> tuple[str, list[str]]:
    deadline = time.monotonic() + timeout
    last_output = ""
    last_error: RunnerError | None = None
    while time.monotonic() < deadline:
        try:
            result = commands.run(
                [str(commands.adb_path), "devices", "-l"],
                check=False,
                timeout=10,
            )
        except RunnerError as error:
            last_error = error
        else:
            assert isinstance(result.stdout, str)
            last_output = result.stdout
            if result.returncode == 0:
                serials = list(parse_adb_devices(last_output))
                if (
                    owned_serial not in serials
                    and set(preexisting_serials).issubset(serials)
                ):
                    return last_output, serials
        time.sleep(1)
    suffix = f": {last_error}" if last_error is not None else ""
    raise RunnerError(
        "adb transports did not converge after owned emulator cleanup"
        f"; last devices={last_output!r}{suffix}"
    )


def run_lane(
    *,
    sdk_root: Path,
    output_directory: Path,
    java_home: Path | None = None,
) -> Path:
    java_home = (java_home or contract.default_java_home()).resolve()
    ensure_host_and_sdk(sdk_root, java_home)
    run_id = output_directory.name
    if contract.RUN_ID_RE.fullmatch(run_id) is None:
        raise RunnerError("output directory basename must be the exact versioned run id")
    if output_directory.exists():
        raise RunnerError(f"output directory must not already exist: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=False)
    (output_directory / "ui").mkdir()

    started = utc_now()

    commands = Commands(sdk_root=sdk_root, java_home=java_home)
    source_before = contract.source_snapshot(ROOT)
    toolchain = {
        "adb": contract.sdk_tool_identity(sdk_root, Path("platform-tools/adb")),
        "adbVersion": command_version(commands, [str(commands.adb_path), "version"]),
        "emulator": contract.sdk_tool_identity(sdk_root, Path("emulator/emulator")),
        "emulatorVersion": command_version(
            commands, [str(commands.emulator_path), "-version"]
        ),
        "java": contract.java_tool_identity(java_home),
        "javaHome": str(java_home),
        "javaVersion": command_version(
            commands, [str(java_home / "bin/java"), "-version"]
        ),
        "qemuHeadless": contract.sdk_tool_identity(
            sdk_root,
            Path("emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"),
        ),
        "systemImage": contract.system_image_snapshot(sdk_root),
    }
    run_offline_debug_build(commands, output_directory / "gradle-build.log")

    port_lock: int | None = None
    temporary_root: Path | None = None
    process: subprocess.Popen[bytes] | None = None
    emulator_log = None
    scenarios: list[dict[str, object]] = []
    process_observations: list[dict[str, object]] = []
    preexisting_serials: tuple[str, ...] = ()
    preexisting_host_emulators: list[dict[str, object]] = []
    model = ""
    width = height = density = 0
    port = 0
    serial = ""
    logcat_bytes = b""
    exit_info_bytes = b""
    network_before_bytes = b""
    network_after_bytes = b""
    app_networking_after_deny_bytes = b""
    app_networking_after_lifecycle_bytes = b""
    guest_airplane_mode_before_bytes = b""
    guest_airplane_mode_after_bytes = b""
    body_failed = False
    try:
        preexisting_host_emulators = host_emulator_inventory(commands)
        (output_directory / "pre-emulator-processes.json").write_bytes(
            contract.canonical_json_bytes(preexisting_host_emulators)
        )
        port, port_lock, preexisting_serials, pre_adb_devices = acquire_emulator_port(
            commands.adb_path,
            commands.environment,
            reserved_ports={
                int(record["port"]) for record in preexisting_host_emulators
            },
        )
        (output_directory / "pre-adb-devices.txt").write_text(
            pre_adb_devices,
            encoding="utf-8",
        )
        serial = f"emulator-{port}"
        if serial in preexisting_serials:
            raise RunnerError("owned serial collides with a preexisting adb serial")
        commands.serial = serial
        temporary_root = Path(
            tempfile.mkdtemp(prefix=f"aetherlink-api36-1-{port}-")
        )
        avd_name = f"AetherLink_API_36_1_{port}_{secrets.token_hex(4)}"
        avd_home = create_ephemeral_avd(
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
        launch_command = emulator_launch_command(
            commands.emulator_path,
            avd_name=avd_name,
            port=port,
        )
        (output_directory / "launch-argv.json").write_bytes(
            contract.canonical_json_bytes(launch_command)
        )
        emulator_log = (output_directory / "emulator.log").open("wb")
        process = subprocess.Popen(
            launch_command,
            cwd=ROOT,
            env=launch_environment,
            stdout=emulator_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        wait_for_boot(commands, process)
        verify_owned_emulator_identity(
            commands,
            process,
            expected_avd_name=avd_name,
        )
        configure_booted_device(commands)
        model, width, height, density = assert_screen_contract(commands)
        commands.shell("cmd", "locale", "set-device-locale", "en-US")
        device_locale = commands.shell("cmd", "locale", "get-device-locale")
        if not device_locale.startswith("en"):
            raise RunnerError(f"device locale must be English, found {device_locale!r}")
        commands.shell("cmd", "connectivity", "airplane-mode", "enable")
        commands.shell("svc", "wifi", "disable")
        commands.shell("svc", "data", "disable")
        guest_airplane_mode_before_bytes = capture_exact_shell_line(
            commands,
            output_directory / "guest-airplane-mode-before.txt",
            "cmd",
            "connectivity",
            "airplane-mode",
            expected="enabled",
            label="guest airplane mode before lifecycle",
        )
        commands.shell("settings", "put", "system", "font_scale", "2.0")
        if commands.shell("settings", "get", "system", "font_scale") != "2.0":
            raise RunnerError("font_scale did not converge to 2.0")

        apk_path = ROOT / contract.DEBUG_APK_RELATIVE
        install = commands.adb("install", "-r", "-t", str(apk_path), timeout=180)
        assert isinstance(install.stdout, str)
        if "Success" not in install.stdout:
            raise RunnerError(f"Debug APK installation did not report Success: {install.stdout!r}")
        commands.shell("cmd", "connectivity", "set-chain3-enabled", "true")
        commands.shell(
            "cmd",
            "connectivity",
            "set-package-networking-enabled",
            "false",
            PACKAGE_NAME,
        )
        app_networking_after_deny_bytes = capture_exact_shell_line(
            commands,
            output_directory / "app-networking-after-deny.txt",
            "cmd",
            "connectivity",
            "get-package-networking-enabled",
            PACKAGE_NAME,
            expected=contract.APP_NETWORKING_DENIED_STATE,
            label="package networking state after deny",
        )
        network_before_bytes, _ = capture_network_state(
            commands,
            output_directory / "network-state-before.txt",
        )

        package_path_output = commands.shell("pm", "path", PACKAGE_NAME)
        package_paths = [
            line.removeprefix("package:")
            for line in package_path_output.splitlines()
            if line.startswith("package:")
        ]
        if len(package_paths) != 1 or not package_paths[0].endswith("/base.apk"):
            raise RunnerError(f"expected one installed base APK, found {package_path_output!r}")
        pull = commands.adb(
            "pull",
            package_paths[0],
            str(output_directory / "installed-base.apk"),
            timeout=180,
        )
        if pull.returncode != 0:
            raise RunnerError("installed base APK could not be read back")
        built_record = contract.file_record(
            apk_path,
            relative=contract.DEBUG_APK_RELATIVE.as_posix(),
        )
        installed_record = contract.file_record(
            output_directory / "installed-base.apk",
            relative="installed-base.apk",
        )
        if (
            built_record["sha256"],
            built_record["size"],
        ) != (
            installed_record["sha256"],
            installed_record["size"],
        ):
            raise RunnerError("installed base APK bytes differ from the built Debug APK")

        commands.shell("pm", "clear", PACKAGE_NAME)
        set_app_locales(commands, [])
        commands.adb("logcat", "-c", check=False)
        first_pid = force_stop_and_launch(
            commands,
            observation_label="clean_install_and_first_launch",
            observations=process_observations,
        )
        first_ui = wait_for_ui(
            commands,
            output_directory,
            "ui/first-launch.xml",
            lambda root: has_node(root, text="Pair AetherLink", package=APP_PACKAGE_PREFIX),
        )
        scenarios.append(
            scenario(
                "clean_install_and_first_launch",
                evidence=list(
                    contract.SCENARIO_EVIDENCE["clean_install_and_first_launch"]
                ),
                observations={
                    "firstProcessId": first_pid,
                    "installedApkSha256": installed_record["sha256"],
                    "preexistingSerials": list(preexisting_serials),
                    "serial": serial,
                },
            )
        )

        cold_pids = [first_pid]
        for round_number, relative in enumerate(
            ("ui/cold-launch-2.xml", "ui/cold-launch-3.xml"),
            start=2,
        ):
            cold_pids.append(
                force_stop_and_launch(
                    commands,
                    observation_label=(
                        f"force_stop_cold_launch_repetition:{round_number}"
                    ),
                    observations=process_observations,
                )
            )
            wait_for_ui(
                commands,
                output_directory,
                relative,
                lambda root: has_node(root, text="Pair AetherLink", package=APP_PACKAGE_PREFIX),
            )
        cold_identities = {
            (record.get("stdout"), record.get("processStartTicks"))
            for record in process_observations[:3]
        }
        if len(cold_identities) != 3:
            raise RunnerError(
                "three cold launches must use distinct raw process identities: "
                f"{cold_identities!r}"
            )
        scenarios.append(
            scenario(
                "force_stop_cold_launch_repetition",
                evidence=list(
                    contract.SCENARIO_EVIDENCE[
                        "force_stop_cold_launch_repetition"
                    ]
                ),
                observations={"processIds": cold_pids, "rounds": 3},
            )
        )

        for tag, title in contract.LOCALE_TITLES:
            set_app_locales(commands, [tag])
            scenario_name = f"platform_locale_{tag.lower().replace('-', '_')}"
            pid = force_stop_and_launch(
                commands,
                observation_label=scenario_name,
                observations=process_observations,
            )
            relative = f"ui/locale-{tag}.xml"
            wait_for_ui(
                commands,
                output_directory,
                relative,
                lambda root, expected=title: has_node(
                    root, text=expected, package=APP_PACKAGE_PREFIX
                ),
            )
            scenarios.append(
                scenario(
                    scenario_name,
                    evidence=list(contract.SCENARIO_EVIDENCE[scenario_name]),
                    observations={
                        "fontScale": "2.0",
                        "localeTags": get_app_locales(commands),
                        "pairingTitle": title,
                        "processId": pid,
                    },
                )
            )

        set_app_locales(commands, ["en"])
        force_stop_and_launch(commands)
        english_ui = capture_ui(commands, output_directory, None)
        _, language_settings = open_language_settings(
            commands,
            output_directory,
            top_root=english_ui,
            navigation_description="Open navigation menu",
            settings_label="Settings",
            drawer_relative="ui/in-app-korean-drawer.xml",
            settings_relative="ui/in-app-korean-settings.xml",
            language_tokens=("한국어",),
            actionable_tokens=("한국어",),
            settings_anchor_text="Pair AetherLink",
        )
        tap_bounds(
            commands,
            fully_visible_clickable_bounds_for(
                language_settings,
                text="한국어",
                package=APP_PACKAGE_PREFIX,
            ),
        )
        wait_for_app_locales(
            commands,
            ["ko"],
            description="in-app Korean locale write",
        )
        wait_for_ui(
            commands,
            output_directory,
            "ui/in-app-korean.xml",
            lambda root: has_node(
                root,
                text="시스템 언어 따르기",
                package=APP_PACKAGE_PREFIX,
            ),
        )
        korean_pid = force_stop_and_launch(
            commands,
            observation_label="in_app_korean_language",
            observations=process_observations,
        )
        korean_relaunch = wait_for_ui(
            commands,
            output_directory,
            "ui/in-app-korean-relaunch.xml",
            lambda root: has_node(root, text="AetherLink 페어링", package=APP_PACKAGE_PREFIX),
        )
        scenarios.append(
            scenario(
                "in_app_korean_language",
                evidence=list(
                    contract.SCENARIO_EVIDENCE["in_app_korean_language"]
                ),
                observations={
                    "localeTags": get_app_locales(commands),
                    "pairingTitle": "AetherLink 페어링",
                    "processId": korean_pid,
                },
            )
        )

        _, follow_system_settings = open_language_settings(
            commands,
            output_directory,
            top_root=korean_relaunch,
            navigation_description="탐색 메뉴 열기",
            settings_label="설정",
            drawer_relative="ui/in-app-follow-system-drawer.xml",
            settings_relative="ui/in-app-follow-system-settings.xml",
            language_tokens=("시스템 언어 따르기",),
            actionable_tokens=("시스템 언어 따르기",),
            settings_anchor_text="AetherLink 페어링",
        )
        tap_bounds(
            commands,
            fully_visible_clickable_bounds_for(
                follow_system_settings,
                text="시스템 언어 따르기",
                package=APP_PACKAGE_PREFIX,
            ),
        )
        wait_for_app_locales(
            commands,
            [],
            description="in-app Follow system locale clear",
        )
        wait_for_ui(
            commands,
            output_directory,
            "ui/in-app-follow-system.xml",
            lambda root: has_node(
                root,
                text="Follow system language",
                package=APP_PACKAGE_PREFIX,
            ),
        )
        follow_pid = force_stop_and_launch(
            commands,
            observation_label="in_app_follow_system_language",
            observations=process_observations,
        )
        wait_for_ui(
            commands,
            output_directory,
            "ui/in-app-follow-system-relaunch.xml",
            lambda root: has_node(root, text="Pair AetherLink", package=APP_PACKAGE_PREFIX),
        )
        scenarios.append(
            scenario(
                "in_app_follow_system_language",
                evidence=list(
                    contract.SCENARIO_EVIDENCE[
                        "in_app_follow_system_language"
                    ]
                ),
                observations={
                    "deviceLocale": device_locale,
                    "localeTags": get_app_locales(commands),
                    "pairingTitle": "Pair AetherLink",
                    "processId": follow_pid,
                },
            )
        )

        commands.shell("pm", "clear", PACKAGE_NAME)
        set_app_locales(commands, [])
        commands.shell("pm", "revoke", PACKAGE_NAME, CAMERA_PERMISSION, check=False)
        commands.shell(
            "pm", "clear-permission-flags", PACKAGE_NAME, CAMERA_PERMISSION, "user-set", "user-fixed", check=False
        )
        camera_before_pid = force_stop_and_launch(
            commands,
            observation_label="camera_permission_denial_and_cold_launch:before",
            observations=process_observations,
        )
        camera_entry = capture_ui(commands, output_directory, None)
        tap_bounds(commands, clickable_bounds_for(camera_entry, text="Scan QR"))
        permission_dialog = wait_for_ui(
            commands,
            output_directory,
            "ui/camera-permission-dialog.xml",
            lambda root: any(
                node.attrib.get("package") in PERMISSION_CONTROLLER_PACKAGES
                for node in root.iter()
            ),
        )
        try:
            deny_bounds = clickable_bounds_for(
                permission_dialog,
                resource_id_suffix="permission_deny_button",
            )
        except RunnerError:
            try:
                deny_bounds = clickable_bounds_for(permission_dialog, text="Don’t allow")
            except RunnerError:
                deny_bounds = clickable_bounds_for(permission_dialog, text="Don't allow")
        tap_bounds(commands, deny_bounds)
        denied_ui = wait_for_ui(
            commands,
            output_directory,
            "ui/camera-denied.xml",
            lambda root: has_node(root, text="Camera access is needed", package=APP_PACKAGE_PREFIX),
        )
        capture_camera_permission_state(
            commands,
            output_directory / "camera-permission-after-denial.txt",
            expected_granted=False,
        )
        camera_after_pid = force_stop_and_launch(
            commands,
            observation_label="camera_permission_denial_and_cold_launch:after",
            observations=process_observations,
        )
        capture_camera_permission_state(
            commands,
            output_directory / "camera-permission-after-denial-cold-launch.txt",
            expected_granted=False,
        )
        denied_entry = capture_ui(commands, output_directory, None)
        tap_bounds(commands, clickable_bounds_for(denied_entry, text="Scan QR"))
        denied_relaunch = wait_for_ui(
            commands,
            output_directory,
            "ui/camera-denied-relaunch.xml",
            lambda root: has_node(root, text="Camera access is needed", package=APP_PACKAGE_PREFIX),
        )
        if any(
            node.attrib.get("package") in PERMISSION_CONTROLLER_PACKAGES
            for node in denied_relaunch.iter()
        ):
            raise RunnerError("denial cold launch issued a duplicate system permission dialog")
        camera_identities = {
            (record.get("stdout"), record.get("processStartTicks"))
            for record in process_observations[-2:]
        }
        if len(camera_identities) != 2:
            raise RunnerError(
                "camera denial cold launch must use a distinct raw process identity"
            )
        scenarios.append(
            scenario(
                "camera_permission_denial_and_cold_launch",
                evidence=list(
                    contract.SCENARIO_EVIDENCE[
                        "camera_permission_denial_and_cold_launch"
                    ]
                ),
                observations={
                    "cameraPermissionGranted": False,
                    "manualRetryLabel": "Allow camera",
                    "processIds": [camera_before_pid, camera_after_pid],
                },
            )
        )

        commands.shell("pm", "grant", PACKAGE_NAME, CAMERA_PERMISSION)
        capture_camera_permission_state(
            commands,
            output_directory / "camera-permission-after-grant.txt",
            expected_granted=True,
        )
        force_stop_and_launch(commands)
        granted_entry = capture_ui(commands, output_directory, None)
        tap_bounds(commands, clickable_bounds_for(granted_entry, text="Scan QR"))
        wait_for_ui(
            commands,
            output_directory,
            "ui/camera-granted.xml",
            lambda root: (
                has_node(root, text="Scan AetherLink QR", package=APP_PACKAGE_PREFIX)
                and has_node(
                    root,
                    content_description="Close QR scanner",
                    package=APP_PACKAGE_PREFIX,
                )
            ),
        )
        scenarios.append(
            scenario(
                "camera_permission_regrant",
                evidence=list(contract.SCENARIO_EVIDENCE["camera_permission_regrant"]),
                observations={"cameraPermissionGranted": True, "scannerTitle": "Scan AetherLink QR"},
            )
        )

        commands.shell("am", "force-stop", PACKAGE_NAME)
        commands.shell("pm", "revoke", PACKAGE_NAME, CAMERA_PERMISSION)
        commands.shell(
            "pm", "set-permission-flags", PACKAGE_NAME, CAMERA_PERMISSION, "user-set", "user-fixed"
        )
        force_stop_and_launch(commands)
        capture_camera_permission_state(
            commands,
            output_directory / "camera-permission-after-fixed-revoke.txt",
            expected_granted=False,
        )
        recovery_entry = capture_ui(commands, output_directory, None)
        tap_bounds(commands, clickable_bounds_for(recovery_entry, text="Scan QR"))
        recovery_ui = wait_for_ui(
            commands,
            output_directory,
            "ui/camera-settings-recovery.xml",
            lambda root: (
                has_node(root, text="Camera permission is blocked", package=APP_PACKAGE_PREFIX)
                and has_node(root, text="Open app settings", package=APP_PACKAGE_PREFIX)
            ),
        )
        tap_bounds(commands, clickable_bounds_for(recovery_ui, text="Open app settings"))
        wait_until(
            "Android app-info activity",
            lambda: SETTINGS_PACKAGE in top_activity(commands) and PACKAGE_NAME in top_activity(commands),
            timeout=30,
        )
        wait_for_ui(
            commands,
            output_directory,
            "ui/app-info.xml",
            lambda root: any(
                node.attrib.get("package") == SETTINGS_PACKAGE for node in root.iter()
            ),
        )
        scenarios.append(
            scenario(
                "camera_settings_recovery",
                evidence=list(contract.SCENARIO_EVIDENCE["camera_settings_recovery"]),
                observations={
                    "cameraPermissionGranted": False,
                    "settingsPackage": SETTINGS_PACKAGE,
                },
            )
        )

        force_stop_and_launch(commands)
        font_top = capture_ui(commands, output_directory, None)
        drawer, font_settings = open_language_settings(
            commands,
            output_directory,
            top_root=font_top,
            navigation_description="Open navigation menu",
            settings_label="Settings",
            drawer_relative="ui/font-scale-drawer.xml",
            settings_relative="ui/font-scale-settings.xml",
            language_tokens=("Follow system language", "한국어"),
            settings_anchor_text="Pair AetherLink",
        )
        if commands.shell("settings", "get", "system", "font_scale") != "2.0":
            raise RunnerError("font_scale changed during product lifecycle checks")
        for expected in ("New Chat", "Settings"):
            bounds = visible_bounds_for(drawer, text=expected)
            if bounds[2] > width or bounds[3] > height:
                raise RunnerError(f"{expected} drawer destination is outside the screen")
        scenarios.append(
            scenario(
                "font_scale_200_core_reachability",
                evidence=list(
                    contract.SCENARIO_EVIDENCE[
                        "font_scale_200_core_reachability"
                    ]
                ),
                observations={
                    "fontScale": "2.0",
                    "reachableDestinations": ["New Chat", "Settings"],
                    "screen": [width, height, density],
                },
            )
        )

        if [record.get("label") for record in process_observations] != list(
            contract.PROCESS_OBSERVATION_LABELS
        ):
            raise RunnerError("raw package process observations are incomplete")
        (output_directory / "app-process-observations.json").write_bytes(
            contract.canonical_json_bytes(process_observations)
        )
        app_networking_after_lifecycle_bytes = capture_exact_shell_line(
            commands,
            output_directory / "app-networking-after-lifecycle.txt",
            "cmd",
            "connectivity",
            "get-package-networking-enabled",
            PACKAGE_NAME,
            expected=contract.APP_NETWORKING_DENIED_STATE,
            label="package networking state after lifecycle",
        )
        guest_airplane_mode_after_bytes = capture_exact_shell_line(
            commands,
            output_directory / "guest-airplane-mode-after.txt",
            "cmd",
            "connectivity",
            "airplane-mode",
            expected="enabled",
            label="guest airplane mode after lifecycle",
        )
        network_after_bytes, _ = capture_network_state(
            commands,
            output_directory / "network-state-after.txt",
        )

        logcat_result = commands.adb("logcat", "-d", "-v", "threadtime", text=False)
        assert isinstance(logcat_result.stdout, bytes)
        logcat_bytes = logcat_result.stdout
        (output_directory / "logcat.txt").write_bytes(logcat_bytes)
        logcat_text = logcat_bytes.decode("utf-8", "replace")
        forbidden_logcat = find_forbidden_logcat_lines(logcat_text)
        if forbidden_logcat:
            raise RunnerError("AetherLink FATAL/ANR found in logcat: " + "; ".join(forbidden_logcat))

        exit_result = commands.adb(
            "shell", "dumpsys", "activity", "exit-info", PACKAGE_NAME, text=False
        )
        assert isinstance(exit_result.stdout, bytes)
        exit_info_bytes = exit_result.stdout
        (output_directory / "exit-info.txt").write_bytes(exit_info_bytes)
        forbidden_exit = find_forbidden_exit_lines(exit_info_bytes.decode("utf-8", "replace"))
        if forbidden_exit:
            raise RunnerError("AetherLink crash/ANR exit reason found: " + "; ".join(forbidden_exit))
    except BaseException:
        body_failed = True
        raise
    finally:
        cleanup_completed = False
        try:
            cleanup_owned_emulator(
                process,
                temporary_root=temporary_root,
            )
            cleanup_completed = True
        finally:
            if emulator_log is not None:
                emulator_log.close()
            if body_failed and cleanup_completed:
                release_emulator_port_lock(port_lock)
                port_lock = None

    try:
        post_adb_devices, post_serials = wait_for_post_cleanup_devices(
            commands,
            owned_serial=serial,
            preexisting_serials=preexisting_serials,
        )
        (output_directory / "post-adb-devices.txt").write_text(
            post_adb_devices,
            encoding="utf-8",
        )
        post_host_emulators = host_emulator_inventory(commands)
        (output_directory / "post-emulator-processes.json").write_bytes(
            contract.canonical_json_bytes(post_host_emulators)
        )
    finally:
        release_emulator_port_lock(port_lock)
        port_lock = None
    preexisting_list = list(preexisting_serials)
    process_exited = process is not None and process.poll() is not None
    temporary_removed = temporary_root is not None and not temporary_root.exists()
    owned_absent = serial not in post_serials
    preexisting_host_by_serial = {
        record["serial"]: record for record in preexisting_host_emulators
    }
    post_host_by_serial = {record["serial"]: record for record in post_host_emulators}
    host_emulators_preserved = all(
        post_host_by_serial.get(serial_key) == record
        for serial_key, record in preexisting_host_by_serial.items()
    )
    owned_host_absent = serial not in post_host_by_serial
    preexisting_preserved = (
        set(preexisting_list).issubset(post_serials)
        and host_emulators_preserved
    )
    if not (
        process_exited
        and temporary_removed
        and owned_absent
        and owned_host_absent
        and preexisting_preserved
    ):
        raise RunnerError(
            "owned emulator cleanup did not preserve the exact process/serial/AVD boundary"
        )

    source_after = contract.source_snapshot(ROOT)
    if source_after != source_before:
        raise RunnerError("Android source bytes changed during the emulator lifecycle run")
    if len(scenarios) != len(contract.SCENARIO_CHECKS):
        raise RunnerError(
            f"scenario contract is incomplete: {len(scenarios)}/{len(contract.SCENARIO_CHECKS)}"
        )
    built_record = contract.file_record(
        ROOT / contract.DEBUG_APK_RELATIVE,
        relative=contract.DEBUG_APK_RELATIVE.as_posix(),
    )
    installed_record = contract.file_record(
        output_directory / "installed-base.apk",
        relative="installed-base.apk",
    )
    evidence = contract.evidence_manifest(output_directory)
    finished = utc_now()
    payload: dict[str, object] = {
        "artifact": {
            "built": built_record,
            "exactByteMatch": True,
            "installed": installed_record,
        },
        "build": {
            "command": list(contract.BUILD_COMMAND),
            "dependencyMode": "offline",
            "exitCode": 0,
        },
        "cleanup": {
            "ownedProcessExited": process_exited,
            "ownedSerialAbsent": owned_absent,
            "postHostEmulators": post_host_emulators,
            "postSerials": post_serials,
            "preexistingHostEmulators": preexisting_host_emulators,
            "preexistingSerials": preexisting_list,
            "preexistingSerialsPreserved": preexisting_preserved,
            "temporaryAvdRemoved": temporary_removed,
        },
        "contract": contract.CONTRACT,
        "device": {
            "abi": "arm64-v8a",
            "activity": contract.ACTIVITY_NAME,
            "apiLevel": 36,
            "appNetworkingDenied": True,
            "avdEphemeral": True,
            "guestAirplaneModeEnabled": True,
            "launchFlags": list(contract.LAUNCH_FLAGS),
            "model": model,
            "package": PACKAGE_NAME,
            "release": "16",
            "screenDensity": density,
            "screenHeight": height,
            "screenWidth": width,
            "systemImagePackage": contract.SYSTEM_IMAGE_PACKAGE,
        },
        "evidence": evidence,
        "exitInfo": {
            "forbiddenMatches": [],
            "lineCount": len(exit_info_bytes.splitlines()),
            "sha256": hashlib.sha256(exit_info_bytes).hexdigest(),
        },
        "logcat": {
            "fatalOrAnrMatches": [],
            "lineCount": len(logcat_bytes.splitlines()),
            "sha256": hashlib.sha256(logcat_bytes).hexdigest(),
        },
        "networkIsolation": {
            "after": {
                "lineCount": len(network_after_bytes.splitlines()),
                "sha256": hashlib.sha256(network_after_bytes).hexdigest(),
                "validatedInternetMatches": [],
            },
            "appNetworkingAfterDeny": {
                "lineCount": len(app_networking_after_deny_bytes.splitlines()),
                "sha256": hashlib.sha256(
                    app_networking_after_deny_bytes
                ).hexdigest(),
                "value": contract.APP_NETWORKING_DENIED_STATE,
            },
            "appNetworkingAfterLifecycle": {
                "lineCount": len(
                    app_networking_after_lifecycle_bytes.splitlines()
                ),
                "sha256": hashlib.sha256(
                    app_networking_after_lifecycle_bytes
                ).hexdigest(),
                "value": contract.APP_NETWORKING_DENIED_STATE,
            },
            "before": {
                "lineCount": len(network_before_bytes.splitlines()),
                "sha256": hashlib.sha256(network_before_bytes).hexdigest(),
                "validatedInternetMatches": [],
            },
            "guestAirplaneModeAfter": {
                "lineCount": len(guest_airplane_mode_after_bytes.splitlines()),
                "sha256": hashlib.sha256(
                    guest_airplane_mode_after_bytes
                ).hexdigest(),
                "value": "enabled",
            },
            "guestAirplaneModeBefore": {
                "lineCount": len(guest_airplane_mode_before_bytes.splitlines()),
                "sha256": hashlib.sha256(
                    guest_airplane_mode_before_bytes
                ).hexdigest(),
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
    structural_failures = contract.payload_failures(
        payload,
        result_directory=output_directory,
        root=ROOT,
        sdk_root=sdk_root,
        java_home=java_home,
    )
    if structural_failures:
        raise RunnerError("result payload failed before write: " + "; ".join(structural_failures))
    result_path = output_directory / "result.json"
    write_canonical_result(result_path, payload)
    readback_failures = contract.result_failures(
        result_path,
        root=ROOT,
        sdk_root=sdk_root,
        java_home=java_home,
    )
    if readback_failures:
        raise RunnerError("written result failed readback: " + "; ".join(readback_failures))
    return result_path


def default_sdk_root() -> Path:
    configured = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Library/Android/sdk").resolve()


def default_run_id() -> str:
    return (
        "android-headless-api36-1-"
        + utc_now().strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + secrets.token_hex(4)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path, default=default_sdk_root())
    parser.add_argument("--java-home", type=Path, default=contract.default_java_home())
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="new evidence directory; basename must be the versioned run id",
    )
    args = parser.parse_args()
    sdk_root = args.sdk_root.expanduser().resolve()
    java_home = args.java_home.expanduser().resolve()
    output_directory = (
        args.output_directory.expanduser().resolve()
        if args.output_directory is not None
        else (ROOT / "build/qa" / default_run_id()).resolve()
    )
    try:
        result_path = run_lane(
            sdk_root=sdk_root,
            output_directory=output_directory,
            java_home=java_home,
        )
    except (RunnerError, contract.EvidenceError, OSError) as error:
        print(f"Android headless lifecycle runner failed: {error}", file=sys.stderr)
        print(f"Partial evidence directory: {output_directory}", file=sys.stderr)
        return 1
    result_bytes = result_path.read_bytes()
    print(
        "Android headless lifecycle runner passed: "
        f"{result_path}; sha256={hashlib.sha256(result_bytes).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
