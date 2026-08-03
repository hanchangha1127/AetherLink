#!/usr/bin/env python3
"""Read back the bounded API 36.1 headless-emulator lifecycle evidence."""

from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat as stat_module
import sys
from typing import Iterable
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-android-headless-emulator-product-lifecycle-v1"
SCHEMA_VERSION = 1
PACKAGE_NAME = "com.localagentbridge.android"
ACTIVITY_NAME = f"{PACKAGE_NAME}/.MainActivity"
APP_NETWORKING_DENIED_STATE = f"{PACKAGE_NAME}:deny"
SYSTEM_IMAGE_PACKAGE = (
    "system-images;android-36.1;google_apis_playstore;arm64-v8a"
)
SYSTEM_IMAGE_RELATIVE = Path(
    "system-images/android-36.1/google_apis_playstore/arm64-v8a"
)
DEBUG_APK_RELATIVE = Path(
    "apps/android/app/build/outputs/apk/debug/app-debug.apk"
)
ANDROID_STUDIO_JAVA_HOME = Path(
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
)

SOURCE_REQUIRED_FILES = (
    Path("gradlew"),
    Path("build.gradle.kts"),
    Path("settings.gradle.kts"),
    Path("gradle.properties"),
    Path("buildscript-gradle.lockfile"),
    Path("settings-gradle.lockfile"),
    Path("gradle/libs.versions.toml"),
    Path("gradle/gradle-daemon-jvm.properties"),
    Path("gradle/wrapper/gradle-wrapper.jar"),
    Path("gradle/wrapper/gradle-wrapper.properties"),
    Path("apps/android/app/build.gradle.kts"),
    Path("apps/android/app/gradle.lockfile"),
    Path("apps/android/core/pairing/build.gradle.kts"),
    Path("apps/android/core/pairing/gradle.lockfile"),
    Path("apps/android/core/protocol/build.gradle.kts"),
    Path("apps/android/core/protocol/gradle.lockfile"),
    Path("apps/android/core/transport/build.gradle.kts"),
    Path("apps/android/core/transport/gradle.lockfile"),
    Path("script/run_android_headless_emulator_product_lifecycle.py"),
    Path("script/check_android_headless_emulator_product_lifecycle.py"),
)
SOURCE_ROOTS = (
    Path("apps/android/app/src"),
    Path("apps/android/core/pairing/src"),
    Path("apps/android/core/protocol/src"),
    Path("apps/android/core/transport/src"),
)
SYSTEM_IMAGE_BINDING_FILES = (
    Path("advancedFeatures.ini"),
    Path("build.prop"),
    Path("encryptionkey.img"),
    Path("kernel_cmdline.txt"),
    Path("package.xml"),
    Path("source.properties"),
    Path("VerifiedBootParams.textproto"),
    Path("kernel-ranchu"),
    Path("ramdisk.img"),
    Path("system.img"),
    Path("vendor.img"),
)
SYSTEM_IMAGE_ROOTS = (Path("data"),)

LAUNCH_FLAGS = (
    "-no-window",
    "-no-audio",
    "-no-boot-anim",
    "-no-snapshot",
    "-wipe-data",
    "-gpu",
    "swiftshader_indirect",
    "-wifi-user-mode-options",
    "restrict=on",
    "-network-user-mode-options",
    "restrict=on",
    "-no-metrics",
)
BUILD_COMMAND = (
    "./gradlew",
    "--offline",
    "--no-daemon",
    "--console=plain",
    "--rerun-tasks",
    "-Pkotlin.incremental=false",
    ":app:assembleDebug",
)

LOCALE_TITLES = (
    ("en", "Pair AetherLink"),
    ("ko", "AetherLink 페어링"),
    ("ja", "AetherLink をペアリング"),
    ("zh-CN", "配对 AetherLink"),
    ("fr", "Jumeler AetherLink"),
)

PROCESS_OBSERVATION_LABELS = (
    "clean_install_and_first_launch",
    "force_stop_cold_launch_repetition:2",
    "force_stop_cold_launch_repetition:3",
    *tuple(
        f"platform_locale_{tag.lower().replace('-', '_')}"
        for tag, _ in LOCALE_TITLES
    ),
    "in_app_korean_language",
    "in_app_follow_system_language",
    "camera_permission_denial_and_cold_launch:before",
    "camera_permission_denial_and_cold_launch:after",
)

CAMERA_PERMISSION_EVIDENCE = (
    ("camera-permission-after-denial.txt", False),
    ("camera-permission-after-denial-cold-launch.txt", False),
    ("camera-permission-after-grant.txt", True),
    ("camera-permission-after-fixed-revoke.txt", False),
)

SCENARIO_CHECKS = (
    (
        "clean_install_and_first_launch",
        (
            "offlineDebugBuildPassed",
            "debugApkInstalled",
            "installedBaseApkExactByteMatch",
            "guestAirplaneModeEnabled",
            "appNetworkingDenied",
            "processStarted",
            "activityResumed",
            "pairingUiVisible",
        ),
    ),
    (
        "force_stop_cold_launch_repetition",
        (
            "threeDistinctProcessesObserved",
            "activityResumedEveryRound",
            "pairingUiVisibleEveryRound",
        ),
    ),
    *tuple(
        (
            f"platform_locale_{tag.lower().replace('-', '_')}",
            (
                "platformLocaleExact",
                "localizedPairingTitleVisible",
                "forceStopColdLaunchPassed",
                "fontScale200Percent",
            ),
        )
        for tag, _ in LOCALE_TITLES
    ),
    (
        "in_app_korean_language",
        (
            "languageControlReachable",
            "platformLocaleExact",
            "localizedPairingTitleVisible",
            "forceStopColdLaunchPassed",
        ),
    ),
    (
        "in_app_follow_system_language",
        (
            "followSystemControlReachable",
            "platformLocaleListEmpty",
            "englishDeviceLocaleVisible",
            "forceStopColdLaunchPassed",
        ),
    ),
    (
        "camera_permission_denial_and_cold_launch",
        (
            "systemPermissionDialogVisible",
            "denialActionSelected",
            "cameraPermissionDenied",
            "denialPersistedAcrossColdLaunch",
            "manualRetryVisibleWithoutDuplicateDialog",
        ),
    ),
    (
        "camera_permission_regrant",
        (
            "cameraPermissionGranted",
            "scannerSurfaceVisible",
            "scannerCloseActionVisible",
        ),
    ),
    (
        "camera_settings_recovery",
        (
            "cameraPermissionRevokedAndFixed",
            "settingsRecoveryVisible",
            "openAppSettingsActionVisible",
            "systemAppInfoOpened",
        ),
    ),
    (
        "font_scale_200_core_reachability",
        (
            "fontScaleExact",
            "pairingTitleVisible",
            "scanActionVisible",
            "navigationMenuReachable",
            "newChatActionVisible",
            "settingsDestinationVisible",
            "languageOptionsVisible",
        ),
    ),
)

SCENARIO_EVIDENCE = {
    "clean_install_and_first_launch": [
        "app-networking-after-deny.txt",
        "app-process-observations.json",
        "gradle-build.log",
        "guest-airplane-mode-before.txt",
        "installed-base.apk",
        "ui/first-launch.xml",
    ],
    "force_stop_cold_launch_repetition": [
        "app-process-observations.json",
        "ui/first-launch.xml",
        "ui/cold-launch-2.xml",
        "ui/cold-launch-3.xml",
    ],
    **{
        f"platform_locale_{tag.lower().replace('-', '_')}": [
            "app-process-observations.json",
            f"ui/locale-{tag}.xml",
        ]
        for tag, _ in LOCALE_TITLES
    },
    "in_app_korean_language": [
        "app-process-observations.json",
        "ui/in-app-korean-drawer.xml",
        "ui/in-app-korean-settings.xml",
        "ui/in-app-korean.xml",
        "ui/in-app-korean-relaunch.xml",
    ],
    "in_app_follow_system_language": [
        "app-process-observations.json",
        "ui/in-app-follow-system-drawer.xml",
        "ui/in-app-follow-system-settings.xml",
        "ui/in-app-follow-system.xml",
        "ui/in-app-follow-system-relaunch.xml",
    ],
    "camera_permission_denial_and_cold_launch": [
        "app-process-observations.json",
        "camera-permission-after-denial.txt",
        "camera-permission-after-denial-cold-launch.txt",
        "ui/camera-permission-dialog.xml",
        "ui/camera-denied.xml",
        "ui/camera-denied-relaunch.xml",
    ],
    "camera_permission_regrant": [
        "camera-permission-after-grant.txt",
        "ui/camera-granted.xml",
    ],
    "camera_settings_recovery": [
        "camera-permission-after-fixed-revoke.txt",
        "ui/camera-settings-recovery.xml",
        "ui/app-info.xml",
    ],
    "font_scale_200_core_reachability": [
        "ui/first-launch.xml",
        "ui/font-scale-settings.xml",
        "ui/font-scale-drawer.xml",
    ],
}

EVIDENCE_PATHS = (
    "app-networking-after-deny.txt",
    "app-networking-after-lifecycle.txt",
    "app-process-observations.json",
    "camera-permission-after-denial.txt",
    "camera-permission-after-denial-cold-launch.txt",
    "camera-permission-after-grant.txt",
    "camera-permission-after-fixed-revoke.txt",
    "emulator.log",
    "gradle-build.log",
    "installed-base.apk",
    "logcat.txt",
    "exit-info.txt",
    "network-state-before.txt",
    "network-state-after.txt",
    "guest-airplane-mode-before.txt",
    "guest-airplane-mode-after.txt",
    "pre-adb-devices.txt",
    "post-adb-devices.txt",
    "pre-emulator-processes.json",
    "post-emulator-processes.json",
    "avd-config.ini",
    "launch-argv.json",
    "ui/first-launch.xml",
    "ui/cold-launch-2.xml",
    "ui/cold-launch-3.xml",
    "ui/locale-en.xml",
    "ui/locale-ko.xml",
    "ui/locale-ja.xml",
    "ui/locale-zh-CN.xml",
    "ui/locale-fr.xml",
    "ui/in-app-korean-drawer.xml",
    "ui/in-app-korean-settings.xml",
    "ui/in-app-korean.xml",
    "ui/in-app-korean-relaunch.xml",
    "ui/in-app-follow-system-drawer.xml",
    "ui/in-app-follow-system-settings.xml",
    "ui/in-app-follow-system.xml",
    "ui/in-app-follow-system-relaunch.xml",
    "ui/camera-permission-dialog.xml",
    "ui/camera-denied.xml",
    "ui/camera-denied-relaunch.xml",
    "ui/camera-granted.xml",
    "ui/camera-settings-recovery.xml",
    "ui/app-info.xml",
    "ui/font-scale-settings.xml",
    "ui/font-scale-drawer.xml",
)

NON_CLAIMS = (
    "physical-device",
    "optical-qr-recognition",
    "camera-preview-quality",
    "talkback-traversal",
    "oem-specific-ui",
    "api-26-30-33-os-matrix",
    "release-signing",
    "store-delivery",
    "production-network",
    "app-upgrade-or-rollback",
    "device-reboot",
    "background-or-doze",
    "os-process-kill",
    "runtime-pairing-or-reconnect",
    "live-provider",
    "reproducible-build",
    "g5-completion",
    "g6-completion",
    "g7-nightly-completion",
    "v1-production-release",
    "tamper-evident-or-signed-evidence",
)

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
RUN_ID_RE = re.compile(
    r"android-headless-api36-1-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z"
)
AVD_NAME_RE = re.compile(r"AetherLink_API_36_1_[0-9]{4}_[0-9a-f]{8}\Z")


class EvidenceError(ValueError):
    """Raised when evidence inputs cannot form the exact contract."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise EvidenceError(f"value is not canonical JSON: {error}") from error
    return encoded + b"\n"


def avd_config_bytes(avd_name: str) -> bytes:
    if type(avd_name) is not str or AVD_NAME_RE.fullmatch(avd_name) is None:
        raise EvidenceError("AVD name must use the reviewed API 36.1 owned-run format")
    return f"""AvdId = {avd_name}
PlayStore.enabled = true
abi.type = arm64-v8a
avd.ini.displayname = AetherLink API 36.1 Ephemeral
avd.ini.encoding = UTF-8
disk.dataPartition.size = 6442450944
fastboot.forceChosenSnapshotBoot = no
fastboot.forceColdBoot = yes
fastboot.forceFastBoot = no
hw.accelerometer = yes
hw.arc = false
hw.audioInput = no
hw.battery = yes
hw.camera.back = virtualscene
hw.camera.front = emulated
hw.cpu.arch = arm64
hw.cpu.ncore = 4
hw.dPad = no
hw.device.manufacturer = Google
hw.device.name = pixel_9
hw.gps = yes
hw.gpu.enabled = yes
hw.gpu.mode = auto
hw.initialOrientation = portrait
hw.keyboard = yes
hw.lcd.density = 420
hw.lcd.height = 2400
hw.lcd.width = 1080
hw.mainKeys = no
hw.ramSize = 4096
hw.sdCard = no
hw.sensors.light = yes
hw.sensors.orientation = yes
hw.sensors.proximity = yes
hw.trackBall = no
image.sysdir.1 = {SYSTEM_IMAGE_RELATIVE.as_posix()}/
runtime.network.latency = none
runtime.network.speed = full
showDeviceFrame = no
skin.dynamic = yes
skin.name = 1080x2400
skin.path = _no_skin
tag.display = Google Play
tag.id = google_apis_playstore
target = android-36.1
vm.heapSize = 512
""".encode("ascii")


def normalized_mode(mode: int) -> str:
    return "0755" if mode & 0o111 else "0644"


def validate_relative_path(value: str) -> None:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as error:
        raise EvidenceError(f"path must be ASCII: {value!r}") from error
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise EvidenceError(f"unsafe relative path: {value!r}")


def read_regular_file(path: Path) -> tuple[bytes, os.stat_result]:
    if path.is_symlink():
        raise EvidenceError(f"symlink is not allowed: {path}")
    try:
        stat_before = path.stat()
    except OSError as error:
        raise EvidenceError(f"cannot stat {path}: {error}") from error
    if not path.is_file():
        raise EvidenceError(f"regular file is required: {path}")
    try:
        data = path.read_bytes()
        stat_after = path.stat()
    except OSError as error:
        raise EvidenceError(f"cannot read {path}: {error}") from error
    stable_fields = (
        stat_before.st_dev,
        stat_before.st_ino,
        stat_before.st_mode,
        stat_before.st_size,
        stat_before.st_mtime_ns,
    )
    if stable_fields != (
        stat_after.st_dev,
        stat_after.st_ino,
        stat_after.st_mode,
        stat_after.st_size,
        stat_after.st_mtime_ns,
    ):
        raise EvidenceError(f"file changed while being read: {path}")
    return data, stat_after


def file_record(path: Path, *, relative: str) -> dict[str, object]:
    validate_relative_path(relative)
    if path.is_symlink():
        raise EvidenceError(f"symlink is not allowed: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise EvidenceError(f"cannot open {path}: {error}") from error
    digest = hashlib.sha256()
    size = 0
    try:
        stat_before = os.fstat(descriptor)
        if not stat_module.S_ISREG(stat_before.st_mode):
            raise EvidenceError(f"regular file is required: {path}")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
        stat_after = os.fstat(descriptor)
    except OSError as error:
        raise EvidenceError(f"cannot read {path}: {error}") from error
    finally:
        os.close(descriptor)
    if (
        stat_before.st_dev,
        stat_before.st_ino,
        stat_before.st_mode,
        stat_before.st_size,
        stat_before.st_mtime_ns,
    ) != (
        stat_after.st_dev,
        stat_after.st_ino,
        stat_after.st_mode,
        stat_after.st_size,
        stat_after.st_mtime_ns,
    ):
        raise EvidenceError(f"file changed while being hashed: {path}")
    if size != stat_after.st_size:
        raise EvidenceError(f"file size changed while being hashed: {path}")
    return {
        "mode": normalized_mode(stat_after.st_mode),
        "path": relative,
        "sha256": digest.hexdigest(),
        "size": size,
    }


def collect_source_paths(root: Path = ROOT) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for relative in SOURCE_REQUIRED_FILES:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise EvidenceError(f"required source input is missing: {relative}")
        candidates.add(path)
    for relative in SOURCE_ROOTS:
        source_root = root / relative
        if source_root.is_symlink() or not source_root.is_dir():
            raise EvidenceError(f"required source root is missing: {relative}")
        for candidate in source_root.rglob("*"):
            if candidate.is_symlink():
                raise EvidenceError(
                    "source root contains a symlink: "
                    f"{candidate.relative_to(root).as_posix()}"
                )
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise EvidenceError(
                    "source root contains a special file: "
                    f"{candidate.relative_to(root).as_posix()}"
                )
            candidates.add(candidate)
    return tuple(
        sorted(
            candidates,
            key=lambda item: item.relative_to(root).as_posix().encode("ascii"),
        )
    )


def source_snapshot(root: Path = ROOT) -> dict[str, object]:
    records = [
        file_record(path, relative=path.relative_to(root).as_posix())
        for path in collect_source_paths(root)
    ]
    digest = hashlib.sha256()
    for record in records:
        digest.update(
            (
                f"{record['path']}\0{record['mode']}\0{record['size']}\0"
                f"{record['sha256']}\n"
            ).encode("ascii")
        )
    return {
        "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        "fileCount": len(records),
        "files": records,
        "sha256": digest.hexdigest(),
    }


def system_image_snapshot(sdk_root: Path) -> dict[str, object]:
    image_root = sdk_root / SYSTEM_IMAGE_RELATIVE
    candidates = set(SYSTEM_IMAGE_BINDING_FILES)
    for relative_root in SYSTEM_IMAGE_ROOTS:
        source_root = image_root / relative_root
        if source_root.is_symlink() or not source_root.is_dir():
            raise EvidenceError(
                f"required system-image root is missing: {relative_root}"
            )
        for candidate in source_root.rglob("*"):
            if candidate.is_symlink():
                raise EvidenceError(
                    "system-image root contains a symlink: "
                    f"{candidate.relative_to(image_root).as_posix()}"
                )
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise EvidenceError(
                    "system-image root contains a special file: "
                    f"{candidate.relative_to(image_root).as_posix()}"
                )
            candidates.add(candidate.relative_to(image_root))
    records = [
        file_record(image_root / relative, relative=relative.as_posix())
        for relative in sorted(candidates, key=lambda item: item.as_posix().encode("ascii"))
    ]
    digest = hashlib.sha256()
    for record in records:
        digest.update(
            (
                f"{record['path']}\0{record['mode']}\0{record['size']}\0"
                f"{record['sha256']}\n"
            ).encode("ascii")
        )
    return {
        "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        "fileCount": len(records),
        "files": records,
        "package": SYSTEM_IMAGE_PACKAGE,
        "sha256": digest.hexdigest(),
    }


def sdk_tool_identity(sdk_root: Path, relative: Path) -> dict[str, object]:
    record = file_record(sdk_root / relative, relative=relative.as_posix())
    return record


def default_java_home() -> Path:
    configured = os.environ.get("JAVA_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return ANDROID_STUDIO_JAVA_HOME.resolve()


def java_tool_identity(java_home: Path) -> dict[str, object]:
    return file_record(java_home / "bin/java", relative="bin/java")


def evidence_manifest(result_directory: Path) -> list[dict[str, object]]:
    return [
        file_record(result_directory / relative, relative=relative)
        for relative in EVIDENCE_PATHS
    ]


def exact_keys(
    value: object,
    expected: Iterable[str],
    *,
    label: str,
) -> list[str]:
    if type(value) is not dict:
        return [f"{label} must be an object"]
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        return [
            f"{label} keys must be exactly {sorted(expected_set)!r}, "
            f"found {sorted(actual_set)!r}"
        ]
    return []


def valid_sha256(value: object) -> bool:
    return type(value) is str and SHA256_RE.fullmatch(value) is not None


def adb_serials_from_text(value: str) -> list[str]:
    serials: list[str] = []
    for line in value.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and not fields[0].startswith("*"):
            serials.append(fields[0])
    return sorted(set(serials))


def validated_network_lines(value: str) -> list[str]:
    internet = re.compile(
        r"(?<![A-Z0-9_])(?:NET_CAPABILITY_)?INTERNET(?![A-Z0-9_])"
    )
    validated = re.compile(
        r"(?<![A-Z0-9_])(?:NET_CAPABILITY_)?(?:VALIDATED|IS_VALIDATED)"
        r"(?![A-Z0-9_])"
    )
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in value.splitlines():
        if line.lstrip().startswith("NetworkAgentInfo{"):
            if current:
                blocks.append(current)
            current = [line]
            if "factorySerialNumber=" in line:
                blocks.append(current)
                current = None
            continue
        if current is not None:
            current.append(line)
            if "factorySerialNumber=" in line:
                blocks.append(current)
                current = None
    if current:
        blocks.append(current)
    matches: list[str] = []
    for block in blocks:
        joined = "\n".join(block)
        if internet.search(joined) and validated.search(joined):
            matches.append(block[0])
    return matches


def host_emulator_inventory_failures(
    raw: bytes,
    *,
    label: str,
) -> tuple[list[dict[str, object]], list[str]]:
    failures: list[str] = []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return [], [f"{label} cannot be decoded: {error}"]
    try:
        canonical = canonical_json_bytes(value)
    except EvidenceError as error:
        return [], [f"{label} is invalid: {error}"]
    if raw != canonical:
        failures.append(f"{label} must use canonical JSON bytes")
    if type(value) is not list:
        return [], failures + [f"{label} must be an array"]
    records: list[dict[str, object]] = []
    seen_serials: set[str] = set()
    for index, record in enumerate(value):
        failures.extend(
            exact_keys(
                record,
                ("commandSha256", "pid", "port", "processStartedAt", "serial"),
                label=f"{label}[{index}]",
            )
        )
        if type(record) is not dict:
            continue
        port = record.get("port")
        pid = record.get("pid")
        serial = record.get("serial")
        if type(port) is not int or not (5554 <= port <= 5584) or port % 2:
            failures.append(f"{label}[{index}].port must be an emulator console port")
        if type(pid) is not int or pid <= 0:
            failures.append(f"{label}[{index}].pid must be a positive integer")
        if type(port) is int and serial != f"emulator-{port}":
            failures.append(f"{label}[{index}].serial must derive from port")
        if type(serial) is not str or serial in seen_serials:
            failures.append(f"{label}[{index}].serial must be unique")
        else:
            seen_serials.add(serial)
        if not valid_sha256(record.get("commandSha256")):
            failures.append(f"{label}[{index}].commandSha256 must be SHA-256")
        started = record.get("processStartedAt")
        if type(started) is not str or not started.strip() or "\n" in started:
            failures.append(
                f"{label}[{index}].processStartedAt must be a nonempty line"
            )
        records.append(record)
    expected_order = sorted(
        records,
        key=lambda record: (
            record.get("port") if type(record.get("port")) is int else -1,
            record.get("pid") if type(record.get("pid")) is int else -1,
        ),
    )
    if records != expected_order:
        failures.append(f"{label} must be sorted by port and pid")
    return records, failures


def app_process_observation_failures(
    raw: bytes,
    *,
    expected_serial: object,
) -> tuple[dict[str, tuple[int, int]], list[str]]:
    label = "app-process-observations.json"
    failures: list[str] = []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return {}, [f"{label} cannot be decoded: {error}"]
    try:
        canonical = canonical_json_bytes(value)
    except EvidenceError as error:
        return {}, [f"{label} is invalid: {error}"]
    if raw != canonical:
        failures.append(f"{label} must use canonical JSON bytes")
    if type(value) is not list:
        return {}, failures + [f"{label} must be an array"]
    if len(value) != len(PROCESS_OBSERVATION_LABELS):
        failures.append(
            f"{label} must contain exactly {len(PROCESS_OBSERVATION_LABELS)} records"
        )

    observed: dict[str, tuple[int, int]] = {}
    for index, record in enumerate(value):
        record_label = f"{label}[{index}]"
        failures.extend(
            exact_keys(
                record,
                (
                    "command",
                    "label",
                    "procCmdlineBase64",
                    "procCmdlineCommand",
                    "procStatAfterCommand",
                    "procStatAfterStdout",
                    "procStatBeforeCommand",
                    "procStatBeforeStdout",
                    "processStartTicks",
                    "serial",
                    "stdout",
                ),
                label=record_label,
            )
        )
        if type(record) is not dict:
            continue
        expected_label = (
            PROCESS_OBSERVATION_LABELS[index]
            if index < len(PROCESS_OBSERVATION_LABELS)
            else None
        )
        actual_label = record.get("label")
        if actual_label != expected_label:
            failures.append(
                f"{record_label}.label must equal {expected_label!r}"
            )
        if record.get("command") != ["pidof", PACKAGE_NAME]:
            failures.append(
                f"{record_label}.command must be the exact package pidof command"
            )
        if (
            type(expected_serial) is not str
            or record.get("serial") != expected_serial
        ):
            failures.append(f"{record_label}.serial must equal the owned run serial")
        stdout = record.get("stdout")
        if (
            type(stdout) is not str
            or re.fullmatch(r"[1-9][0-9]{0,9}\n", stdout) is None
        ):
            failures.append(
                f"{record_label}.stdout must be one bounded exact positive pidof PID"
            )
            continue
        pid = int(stdout.removesuffix("\n"))
        if pid > 2_147_483_647:
            failures.append(f"{record_label}.stdout PID exceeds the Android PID range")
            continue
        proc_path = f"/proc/{pid}"
        if record.get("procCmdlineCommand") != ["cat", f"{proc_path}/cmdline"]:
            failures.append(
                f"{record_label}.procCmdlineCommand must bind the observed PID"
            )
        for phase in ("Before", "After"):
            if record.get(f"procStat{phase}Command") != [
                "cat",
                f"{proc_path}/stat",
            ]:
                failures.append(
                    f"{record_label}.procStat{phase}Command must bind the observed PID"
                )

        process_evidence_valid = True
        encoded_cmdline = record.get("procCmdlineBase64")
        if type(encoded_cmdline) is not str or len(encoded_cmdline) > 8192:
            failures.append(f"{record_label}.procCmdlineBase64 must be bounded Base64")
            process_evidence_valid = False
        else:
            try:
                cmdline = base64.b64decode(encoded_cmdline, validate=True)
            except (binascii.Error, ValueError) as error:
                failures.append(
                    f"{record_label}.procCmdlineBase64 cannot be decoded: {error}"
                )
                process_evidence_valid = False
            else:
                package_bytes = PACKAGE_NAME.encode("ascii")
                if (
                    not (1 <= len(cmdline) <= 4096)
                    or not cmdline.startswith(package_bytes + b"\0")
                    or cmdline.rstrip(b"\0") != package_bytes
                ):
                    failures.append(
                        f"{record_label}.procCmdlineBase64 must identify the exact package"
                    )
                    process_evidence_valid = False

        def parsed_stat_start_ticks(field: str) -> int | None:
            nonlocal process_evidence_valid
            stat_stdout = record.get(field)
            if type(stat_stdout) is not str or not (1 <= len(stat_stdout) <= 4096):
                failures.append(f"{record_label}.{field} must be bounded text")
                process_evidence_valid = False
                return None
            try:
                stat_stdout.encode("ascii")
            except UnicodeEncodeError:
                failures.append(f"{record_label}.{field} must be ASCII")
                process_evidence_valid = False
                return None
            stat_match = re.fullmatch(
                rf"{pid} \(([^()\n]{{1,128}})\) ([^\n]+)\n",
                stat_stdout,
            )
            if stat_match is None:
                failures.append(
                    f"{record_label}.{field} must bind the exact observed PID"
                )
                process_evidence_valid = False
                return None
            stat_fields = stat_match.group(2).split()
            if (
                len(stat_fields) < 20
                or re.fullmatch(r"[1-9][0-9]{0,19}", stat_fields[19]) is None
            ):
                failures.append(
                    f"{record_label}.{field} must expose positive start ticks"
                )
                process_evidence_valid = False
                return None
            start_ticks = int(stat_fields[19])
            if start_ticks > 9_223_372_036_854_775_807:
                failures.append(f"{record_label}.{field} start ticks exceed int64")
                process_evidence_valid = False
                return None
            return start_ticks

        before_start_ticks = parsed_stat_start_ticks("procStatBeforeStdout")
        after_start_ticks = parsed_stat_start_ticks("procStatAfterStdout")
        parsed_start_ticks = (
            before_start_ticks
            if before_start_ticks is not None
            and before_start_ticks == after_start_ticks
            else None
        )
        if (
            before_start_ticks is not None
            and after_start_ticks is not None
            and before_start_ticks != after_start_ticks
        ):
            failures.append(
                f"{record_label} process identity changed across the cmdline read"
            )
            process_evidence_valid = False
        claimed_start_ticks = record.get("processStartTicks")
        if (
            type(claimed_start_ticks) is not int
            or claimed_start_ticks <= 0
            or claimed_start_ticks != parsed_start_ticks
        ):
            failures.append(
                f"{record_label}.processStartTicks must match both raw proc stat reads"
            )
            process_evidence_valid = False

        if type(actual_label) is str and actual_label in observed:
            failures.append(f"{record_label}.label must be unique")
        elif (
            type(actual_label) is str
            and process_evidence_valid
            and type(claimed_start_ticks) is int
        ):
            observed[actual_label] = (pid, claimed_start_ticks)
    return observed, failures


def process_observation_binding_failures(
    scenarios: dict[object, dict[str, object]],
    observed: dict[str, tuple[int, int]],
) -> list[str]:
    failures: list[str] = []

    def scenario_observations(name: str) -> dict[str, object]:
        scenario = scenarios.get(name)
        if type(scenario) is not dict:
            return {}
        value = scenario.get("observations")
        return value if type(value) is dict else {}

    clean = scenario_observations("clean_install_and_first_launch")
    first_identity = observed.get("clean_install_and_first_launch")
    first_pid = first_identity[0] if first_identity is not None else None
    if first_pid is None or clean.get("firstProcessId") != first_pid:
        failures.append(
            "clean-install firstProcessId must match raw package pidof evidence"
        )

    cold = scenario_observations("force_stop_cold_launch_repetition")
    cold_identities = [
        observed.get("clean_install_and_first_launch"),
        observed.get("force_stop_cold_launch_repetition:2"),
        observed.get("force_stop_cold_launch_repetition:3"),
    ]
    expected_cold = [
        identity[0]
        for identity in cold_identities
        if identity is not None
    ]
    if (
        len(expected_cold) != 3
        or cold.get("processIds") != expected_cold
        or len({identity for identity in cold_identities if identity is not None}) != 3
    ):
        failures.append(
            "cold-launch processIds must match three distinct raw process identities"
        )

    for name in (
        *tuple(
            f"platform_locale_{tag.lower().replace('-', '_')}"
            for tag, _ in LOCALE_TITLES
        ),
        "in_app_korean_language",
        "in_app_follow_system_language",
    ):
        observations = scenario_observations(name)
        identity = observed.get(name)
        expected_pid = identity[0] if identity is not None else None
        if expected_pid is None or observations.get("processId") != expected_pid:
            failures.append(
                f"scenario {name} processId must match raw package pidof evidence"
            )
    camera = scenario_observations("camera_permission_denial_and_cold_launch")
    camera_identities = [
        observed.get("camera_permission_denial_and_cold_launch:before"),
        observed.get("camera_permission_denial_and_cold_launch:after"),
    ]
    expected_camera = [
        identity[0]
        for identity in camera_identities
        if identity is not None
    ]
    if (
        len(expected_camera) != 2
        or camera.get("processIds") != expected_camera
        or len({identity for identity in camera_identities if identity is not None}) != 2
    ):
        failures.append(
            "camera denial processIds must bind distinct before/after raw process identities"
        )
    return failures


def app_logcat_failure_lines(value: str) -> list[str]:
    lines = value.splitlines()
    failures: list[str] = []
    for index, line in enumerate(lines):
        if re.search(
            rf"ANR in {re.escape(PACKAGE_NAME)}|am_anr.*{re.escape(PACKAGE_NAME)}",
            line,
        ):
            failures.append(line)
        if "FATAL EXCEPTION:" in line:
            if PACKAGE_NAME in "\n".join(lines[index : index + 8]):
                failures.append(line)
        if re.search(rf"am_crash.*{re.escape(PACKAGE_NAME)}", line):
            failures.append(line)
    return failures


def app_exit_failure_lines(value: str) -> list[str]:
    return [
        line
        for line in value.splitlines()
        if (
            "REASON_CRASH" in line
            or "REASON_ANR" in line
            or re.search(r"\breason=(?:4|5|6)(?:\s|\()", line) is not None
        )
    ]


def camera_permission_evidence_failures(result_directory: Path) -> list[str]:
    failures: list[str] = []
    for relative, expected_granted in CAMERA_PERMISSION_EVIDENCE:
        try:
            raw, file_stat = read_regular_file(result_directory / relative)
        except EvidenceError as error:
            failures.append(f"{relative} cannot be read: {error}")
            continue
        if not (1 <= file_stat.st_size <= 4 * 1024 * 1024):
            failures.append(f"{relative} must be nonempty and at most 4 MiB")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            failures.append(f"{relative} must be UTF-8: {error}")
            continue
        states = re.findall(
            r"(?m)^[ \t]*android\.permission\.CAMERA: granted=(true|false)(?:,[^\r\n]*)?\r?$",
            text,
        )
        if len(states) != 1:
            failures.append(
                f"{relative} must contain exactly one CAMERA runtime permission state"
            )
            continue
        expected = "true" if expected_granted else "false"
        if states[0] != expected:
            failures.append(
                f"{relative} CAMERA state must be granted={expected}, "
                f"found granted={states[0]}"
            )
    return failures


def ui_nodes(
    result_directory: Path,
    relative: str,
) -> tuple[list[dict[str, str]], list[str]]:
    path = result_directory / relative
    try:
        raw, _ = read_regular_file(path)
    except EvidenceError as error:
        return [], [f"{relative} cannot be read: {error}"]
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return [], [f"{relative} must not contain a DTD or entity declaration"]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        return [], [f"{relative} is not valid UI XML: {error}"]
    nodes = [dict(node.attrib) for node in root.iter("node")]
    if not nodes:
        return [], [f"{relative} must contain UI nodes"]
    return nodes, []


def ui_token_failures(
    nodes: list[dict[str, str]],
    *,
    relative: str,
    package: str | tuple[str, ...],
    text: str | None = None,
    content_description: str | None = None,
    text_contains: str | None = None,
    resource_id_suffix: str | None = None,
) -> list[str]:
    packages = (package,) if type(package) is str else package
    matches: list[dict[str, str]] = []
    for node in nodes:
        if node.get("package") not in packages:
            continue
        if text is not None and node.get("text") != text:
            continue
        if content_description is not None and node.get("content-desc") != content_description:
            continue
        if text_contains is not None and text_contains not in node.get("text", ""):
            continue
        if resource_id_suffix is not None and not node.get("resource-id", "").endswith(
            resource_id_suffix
        ):
            continue
        matches.append(node)
    label = text or content_description or text_contains or resource_id_suffix or "package"
    if not matches:
        return [f"{relative} must contain {label!r} in package {packages!r}"]
    for node in matches:
        bounds = re.fullmatch(
            r"\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]",
            node.get("bounds", ""),
        )
        if bounds is None:
            continue
        left, top, right, bottom = (int(value) for value in bounds.groups())
        if 0 <= left < right <= 1080 and 0 <= top < bottom <= 2400:
            return []
    return [f"{relative} token {label!r} must have nonempty in-screen bounds"]


def parsed_ui_bounds(value: str) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(
        r"\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]",
        value,
    )
    if match is None:
        return None
    bounds = tuple(int(item) for item in match.groups())
    if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        return None
    return bounds  # type: ignore[return-value]


def fully_visible_ui_node_bounds(
    node: ET.Element,
    parents: dict[ET.Element, ET.Element],
) -> tuple[int, int, int, int] | None:
    bounds = parsed_ui_bounds(node.attrib.get("bounds", ""))
    if bounds is None or not (
        0 <= bounds[0] < bounds[2] <= 1080
        and 0 <= bounds[1] < bounds[3] <= 2400
    ):
        return None
    viewports: list[tuple[int, int, int, int]] = []
    current = parents.get(node)
    while current is not None:
        if current.attrib.get("scrollable") == "true":
            viewport = parsed_ui_bounds(current.attrib.get("bounds", ""))
            if viewport is None:
                return None
            viewports.append(viewport)
        current = parents.get(current)
    if not viewports or any(
        not (
            viewport[0] <= bounds[0]
            and viewport[1] <= bounds[1]
            and bounds[2] <= viewport[2]
            and bounds[3] <= viewport[3]
        )
        for viewport in viewports
    ):
        return None
    return bounds


def ui_actionable_token_failures(
    result_directory: Path,
    *,
    relative: str,
    text: str,
    expected_checked: str,
) -> list[str]:
    try:
        raw, _ = read_regular_file(result_directory / relative)
    except EvidenceError as error:
        return [f"{relative} actionable token cannot be read: {error}"]
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return [f"{relative} actionable token XML must not contain DTD/entities"]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        return [f"{relative} actionable token XML is invalid: {error}"]
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter("node"):
        if node.attrib.get("package") != PACKAGE_NAME or node.attrib.get("text") != text:
            continue
        current: ET.Element | None = node
        action: ET.Element | None = None
        while current is not None:
            if current.attrib.get("clickable") == "true":
                action = current
                break
            current = parents.get(current)
        if action is None:
            continue
        if (
            action.attrib.get("package") != PACKAGE_NAME
            or action.attrib.get("enabled") != "true"
            or action.attrib.get("checkable") != "true"
            or action.attrib.get("checked") != expected_checked
        ):
            continue
        if fully_visible_ui_node_bounds(action, parents) is None:
            continue
        return []
    return [
        f"{relative} must expose fully visible enabled unchecked actionable {text!r}"
    ]


def ui_checked_token_failures(
    result_directory: Path,
    *,
    relative: str,
    text: str,
) -> list[str]:
    try:
        raw, _ = read_regular_file(result_directory / relative)
    except EvidenceError as error:
        return [f"{relative} checked token cannot be read: {error}"]
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return [f"{relative} checked token XML must not contain DTD/entities"]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        return [f"{relative} checked token XML is invalid: {error}"]
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter("node"):
        if node.attrib.get("package") != PACKAGE_NAME or node.attrib.get("text") != text:
            continue
        current: ET.Element | None = node
        checked: ET.Element | None = None
        while current is not None:
            if current.attrib.get("checkable") == "true":
                checked = current
                break
            current = parents.get(current)
        if checked is None:
            continue
        if (
            checked.attrib.get("package") != PACKAGE_NAME
            or checked.attrib.get("enabled") != "true"
            or checked.attrib.get("checked") != "true"
            or fully_visible_ui_node_bounds(checked, parents) is None
        ):
            continue
        return []
    return [
        f"{relative} must expose fully visible enabled checked {text!r}"
    ]


def ui_semantic_failures(result_directory: Path) -> list[str]:
    failures: list[str] = []
    parsed: dict[str, list[dict[str, str]]] = {}
    for relative in (path for path in EVIDENCE_PATHS if path.startswith("ui/")):
        nodes, node_failures = ui_nodes(result_directory, relative)
        failures.extend(node_failures)
        parsed[relative] = nodes
    app = PACKAGE_NAME
    for relative in (
        "ui/first-launch.xml",
        "ui/cold-launch-2.xml",
        "ui/cold-launch-3.xml",
    ):
        failures.extend(
            ui_token_failures(parsed[relative], relative=relative, package=app, text="Pair AetherLink")
        )
    for tag, title in LOCALE_TITLES:
        relative = f"ui/locale-{tag}.xml"
        failures.extend(
            ui_token_failures(parsed[relative], relative=relative, package=app, text=title)
        )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-korean-drawer.xml"],
            relative="ui/in-app-korean-drawer.xml",
            package=app,
            text="Settings",
        )
    )
    failures.extend(
        ui_actionable_token_failures(
            result_directory,
            relative="ui/in-app-korean-settings.xml",
            text="한국어",
            expected_checked="false",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-korean-settings.xml"],
            relative="ui/in-app-korean-settings.xml",
            package=app,
            text="한국어",
        )
    )
    failures.extend(
        ui_actionable_token_failures(
            result_directory,
            relative="ui/in-app-follow-system-settings.xml",
            text="시스템 언어 따르기",
            expected_checked="false",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-korean.xml"],
            relative="ui/in-app-korean.xml",
            package=app,
            text="시스템 언어 따르기",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-korean-relaunch.xml"],
            relative="ui/in-app-korean-relaunch.xml",
            package=app,
            text="AetherLink 페어링",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-follow-system-drawer.xml"],
            relative="ui/in-app-follow-system-drawer.xml",
            package=app,
            text="설정",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-follow-system-settings.xml"],
            relative="ui/in-app-follow-system-settings.xml",
            package=app,
            text="시스템 언어 따르기",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-follow-system.xml"],
            relative="ui/in-app-follow-system.xml",
            package=app,
            text="Pair AetherLink",
        )
    )
    failures.extend(
        ui_checked_token_failures(
            result_directory,
            relative="ui/in-app-follow-system.xml",
            text="Follow system language",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/in-app-follow-system-relaunch.xml"],
            relative="ui/in-app-follow-system-relaunch.xml",
            package=app,
            text="Pair AetherLink",
        )
    )
    permission_packages = (
        "com.android.permissioncontroller",
        "com.google.android.permissioncontroller",
    )
    permission_nodes = parsed["ui/camera-permission-dialog.xml"]
    failures.extend(
        ui_token_failures(
            permission_nodes,
            relative="ui/camera-permission-dialog.xml",
            package=permission_packages,
            text_contains="AetherLink",
        )
    )
    if not any(
        node.get("package") in permission_packages
        and (
            node.get("resource-id", "").endswith("permission_deny_button")
            or node.get("text") in ("Don't allow", "Don’t allow")
        )
        for node in permission_nodes
    ):
        failures.append("ui/camera-permission-dialog.xml must expose the system denial action")
    for relative in ("ui/camera-denied.xml", "ui/camera-denied-relaunch.xml"):
        failures.extend(
            ui_token_failures(
                parsed[relative],
                relative=relative,
                package=app,
                text="Camera access is needed",
            )
        )
        failures.extend(
            ui_token_failures(
                parsed[relative],
                relative=relative,
                package=app,
                text="Allow camera",
            )
        )
        if any(node.get("package") in permission_packages for node in parsed[relative]):
            failures.append(f"{relative} must not contain a duplicate system permission dialog")
    failures.extend(
        ui_token_failures(
            parsed["ui/camera-granted.xml"],
            relative="ui/camera-granted.xml",
            package=app,
            text="Scan AetherLink QR",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed["ui/camera-granted.xml"],
            relative="ui/camera-granted.xml",
            package=app,
            content_description="Close QR scanner",
        )
    )
    recovery = "ui/camera-settings-recovery.xml"
    for token in ("Camera permission is blocked", "Open app settings"):
        failures.extend(
            ui_token_failures(parsed[recovery], relative=recovery, package=app, text=token)
        )
    failures.extend(
        ui_token_failures(
            parsed["ui/app-info.xml"],
            relative="ui/app-info.xml",
            package="com.android.settings",
            text_contains="AetherLink",
        )
    )
    settings = "ui/font-scale-settings.xml"
    for token in ("Follow system language", "한국어"):
        failures.extend(
            ui_token_failures(parsed[settings], relative=settings, package=app, text=token)
        )
    first_launch = "ui/first-launch.xml"
    failures.extend(
        ui_token_failures(
            parsed[first_launch],
            relative=first_launch,
            package=app,
            content_description="Open navigation menu",
        )
    )
    failures.extend(
        ui_token_failures(
            parsed[first_launch],
            relative=first_launch,
            package=app,
            text="Scan QR",
        )
    )
    drawer = "ui/font-scale-drawer.xml"
    for token in ("New Chat", "Settings"):
        failures.extend(
            ui_token_failures(parsed[drawer], relative=drawer, package=app, text=token)
        )
    return failures


def parse_utc_timestamp(value: object, *, label: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise EvidenceError(f"{label} must be a UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise EvidenceError(f"{label} is not ISO-8601: {error}") from error
    if parsed.tzinfo != timezone.utc:
        raise EvidenceError(f"{label} must use UTC")
    return parsed


def json_observation_value(value: object) -> bool:
    if value is None or type(value) in (str, bool, int, float):
        return type(value) is not float or (value == value and abs(value) != float("inf"))
    if type(value) is list:
        return all(json_observation_value(item) for item in value)
    return False


def exact_json_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is list:
        return len(left) == len(right) and all(  # type: ignore[arg-type]
            exact_json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)  # type: ignore[arg-type]
        )
    if type(left) is dict:
        return set(left) == set(right) and all(  # type: ignore[arg-type]
            exact_json_equal(left[key], right[key])  # type: ignore[index]
            for key in left
        )
    return left == right


def scenario_observation_failures(
    name: str,
    observations: object,
    *,
    payload: dict[str, object],
) -> list[str]:
    if type(observations) is not dict:
        return [f"scenario {name} observations must be an object"]
    run = payload.get("run") if type(payload.get("run")) is dict else {}
    artifact = (
        payload.get("artifact") if type(payload.get("artifact")) is dict else {}
    )
    cleanup = (
        payload.get("cleanup") if type(payload.get("cleanup")) is dict else {}
    )
    installed = (
        artifact.get("installed") if type(artifact.get("installed")) is dict else {}
    )
    expected: dict[str, object]
    pid_key: str | None = None
    process_id_count: int | None = None
    if name == "clean_install_and_first_launch":
        expected = {
            "firstProcessId": None,
            "installedApkSha256": installed.get("sha256"),
            "preexistingSerials": cleanup.get("preexistingSerials"),
            "serial": run.get("serial"),
        }
        pid_key = "firstProcessId"
    elif name == "force_stop_cold_launch_repetition":
        expected = {"processIds": None, "rounds": 3}
        process_id_count = 3
    elif name.startswith("platform_locale_"):
        locale = {
            f"platform_locale_{tag.lower().replace('-', '_')}": (tag, title)
            for tag, title in LOCALE_TITLES
        }.get(name)
        if locale is None:
            return [f"scenario {name} has no locale observation contract"]
        tag, title = locale
        expected = {
            "fontScale": "2.0",
            "localeTags": [tag],
            "pairingTitle": title,
            "processId": None,
        }
        pid_key = "processId"
    elif name == "in_app_korean_language":
        expected = {
            "localeTags": ["ko"],
            "pairingTitle": "AetherLink 페어링",
            "processId": None,
        }
        pid_key = "processId"
    elif name == "in_app_follow_system_language":
        expected = {
            "deviceLocale": "en-US",
            "localeTags": [],
            "pairingTitle": "Pair AetherLink",
            "processId": None,
        }
        pid_key = "processId"
    elif name == "camera_permission_denial_and_cold_launch":
        expected = {
            "cameraPermissionGranted": False,
            "manualRetryLabel": "Allow camera",
            "processIds": None,
        }
        process_id_count = 2
    elif name == "camera_permission_regrant":
        expected = {
            "cameraPermissionGranted": True,
            "scannerTitle": "Scan AetherLink QR",
        }
    elif name == "camera_settings_recovery":
        expected = {
            "cameraPermissionGranted": False,
            "settingsPackage": "com.android.settings",
        }
    elif name == "font_scale_200_core_reachability":
        expected = {
            "fontScale": "2.0",
            "reachableDestinations": ["New Chat", "Settings"],
            "screen": [1080, 2400, 420],
        }
    else:
        return [f"scenario {name} has no observation contract"]

    failures = exact_keys(
        observations,
        expected,
        label=f"scenario {name} observations",
    )
    if failures:
        return failures
    for key, expected_value in expected.items():
        if key == pid_key:
            value = observations[key]
            if type(value) is not int or not (1 <= value <= 2_147_483_647):
                failures.append(
                    f"scenario {name} observations.{key} must be a bounded positive PID"
                )
        elif process_id_count is not None and key == "processIds":
            value = observations[key]
            if (
                type(value) is not list
                or len(value) != process_id_count
                or any(
                    type(item) is not int or not (1 <= item <= 2_147_483_647)
                    for item in value
                )
            ):
                failures.append(
                    f"scenario {name} observations.processIds must be "
                    f"{process_id_count} bounded positive PIDs"
                )
        elif not exact_json_equal(observations[key], expected_value):
            failures.append(
                f"scenario {name} observations.{key} must equal {expected_value!r}"
            )
    return failures


def payload_failures(
    payload: object,
    *,
    result_directory: Path,
    root: Path = ROOT,
    sdk_root: Path,
    java_home: Path | None = None,
) -> list[str]:
    java_home = (java_home or default_java_home()).resolve()
    failures = exact_keys(
        payload,
        (
            "artifact",
            "build",
            "cleanup",
            "contract",
            "device",
            "evidence",
            "exitInfo",
            "logcat",
            "networkIsolation",
            "nonClaims",
            "run",
            "scenarios",
            "schemaVersion",
            "source",
            "status",
            "toolchain",
        ),
        label="result",
    )
    if failures:
        return failures
    assert isinstance(payload, dict)

    if payload["contract"] != CONTRACT:
        failures.append(f"contract must equal {CONTRACT!r}")
    if type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != SCHEMA_VERSION:
        failures.append(f"schemaVersion must equal integer {SCHEMA_VERSION}")
    if payload["status"] != "passed":
        failures.append("status must equal 'passed'")

    run = payload["run"]
    failures.extend(
        exact_keys(
            run,
            (
                "durationSeconds",
                "emulatorPort",
                "finishedAt",
                "hostArchitecture",
                "hostPlatform",
                "id",
                "serial",
                "startedAt",
            ),
            label="run",
        )
    )
    if type(run) is dict and not exact_keys(
        run,
        (
            "durationSeconds",
            "emulatorPort",
            "finishedAt",
            "hostArchitecture",
            "hostPlatform",
            "id",
            "serial",
            "startedAt",
        ),
        label="run",
    ):
        if type(run["id"]) is not str or RUN_ID_RE.fullmatch(run["id"]) is None:
            failures.append("run.id must use the exact versioned run-id format")
        if type(run["emulatorPort"]) is not int or not (5554 <= run["emulatorPort"] <= 5584) or run["emulatorPort"] % 2:
            failures.append("run.emulatorPort must be an unused even emulator port")
        if run["serial"] != f"emulator-{run['emulatorPort']}":
            failures.append("run.serial must derive from run.emulatorPort")
        if run["hostPlatform"] != "darwin" or run["hostArchitecture"] != "arm64":
            failures.append("run host must be the reviewed darwin/arm64 lane")
        if type(run["durationSeconds"]) not in (int, float) or type(run["durationSeconds"]) is bool or run["durationSeconds"] <= 0:
            failures.append("run.durationSeconds must be a positive number")
        try:
            started = parse_utc_timestamp(run["startedAt"], label="run.startedAt")
            finished = parse_utc_timestamp(run["finishedAt"], label="run.finishedAt")
            observed_duration = (finished - started).total_seconds()
            if observed_duration <= 0:
                failures.append("run.finishedAt must be after run.startedAt")
            elif abs(observed_duration - float(run["durationSeconds"])) > 1.0:
                failures.append("run.durationSeconds must match the timestamp interval")
        except EvidenceError as error:
            failures.append(str(error))

    try:
        expected_source = source_snapshot(root)
    except EvidenceError as error:
        failures.append(f"current source snapshot failed: {error}")
    else:
        if payload["source"] != expected_source:
            failures.append("source must exactly match the current Android source snapshot")

    build = payload["build"]
    failures.extend(
        exact_keys(
            build,
            ("command", "dependencyMode", "exitCode"),
            label="build",
        )
    )
    if type(build) is dict:
        if build.get("command") != list(BUILD_COMMAND):
            failures.append("build.command must match the exact offline Debug command")
        if build.get("dependencyMode") != "offline":
            failures.append("build.dependencyMode must equal 'offline'")
        if type(build.get("exitCode")) is not int or build.get("exitCode") != 0:
            failures.append("build.exitCode must equal integer zero")

    artifact = payload["artifact"]
    failures.extend(
        exact_keys(
            artifact,
            ("built", "exactByteMatch", "installed"),
            label="artifact",
        )
    )
    if type(artifact) is dict:
        try:
            expected_built = file_record(
                root / DEBUG_APK_RELATIVE,
                relative=DEBUG_APK_RELATIVE.as_posix(),
            )
            expected_installed = file_record(
                result_directory / "installed-base.apk",
                relative="installed-base.apk",
            )
        except EvidenceError as error:
            failures.append(f"artifact readback failed: {error}")
        else:
            if artifact.get("built") != expected_built:
                failures.append("artifact.built must match the current Debug APK")
            if artifact.get("installed") != expected_installed:
                failures.append("artifact.installed must match installed-base.apk")
            if expected_built["sha256"] != expected_installed["sha256"] or expected_built["size"] != expected_installed["size"]:
                failures.append("built and installed APK bytes must be exactly equal")
        if artifact.get("exactByteMatch") is not True:
            failures.append("artifact.exactByteMatch must be true")

    toolchain = payload["toolchain"]
    failures.extend(
        exact_keys(
            toolchain,
            (
                "adb",
                "adbVersion",
                "emulator",
                "emulatorVersion",
                "java",
                "javaHome",
                "javaVersion",
                "qemuHeadless",
                "systemImage",
            ),
            label="toolchain",
        )
    )
    if type(toolchain) is dict:
        try:
            expected_adb = sdk_tool_identity(sdk_root, Path("platform-tools/adb"))
            expected_emulator = sdk_tool_identity(sdk_root, Path("emulator/emulator"))
            expected_qemu = sdk_tool_identity(
                sdk_root,
                Path("emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"),
            )
            expected_image = system_image_snapshot(sdk_root)
            expected_java = java_tool_identity(java_home)
        except EvidenceError as error:
            failures.append(f"toolchain readback failed: {error}")
        else:
            if toolchain.get("adb") != expected_adb:
                failures.append("toolchain.adb must match the current adb bytes")
            if toolchain.get("emulator") != expected_emulator:
                failures.append("toolchain.emulator must match the current emulator bytes")
            if toolchain.get("qemuHeadless") != expected_qemu:
                failures.append("toolchain.qemuHeadless must match the current headless QEMU bytes")
            if toolchain.get("systemImage") != expected_image:
                failures.append("toolchain.systemImage must match the API 36.1 image bytes")
            if toolchain.get("java") != expected_java:
                failures.append("toolchain.java must match the current Java launcher bytes")
        if toolchain.get("javaHome") != str(java_home):
            failures.append("toolchain.javaHome must match the reviewed Java home")
        for key in ("adbVersion", "emulatorVersion", "javaVersion"):
            if type(toolchain.get(key)) is not str or not toolchain[key].strip():
                failures.append(f"toolchain.{key} must be a nonempty version string")

    device = payload["device"]
    failures.extend(
        exact_keys(
            device,
            (
                "abi",
                "activity",
                "apiLevel",
                "appNetworkingDenied",
                "avdEphemeral",
                "guestAirplaneModeEnabled",
                "launchFlags",
                "model",
                "package",
                "release",
                "screenDensity",
                "screenHeight",
                "screenWidth",
                "systemImagePackage",
            ),
            label="device",
        )
    )
    if type(device) is dict:
        exact_device_values = {
            "abi": "arm64-v8a",
            "activity": ACTIVITY_NAME,
            "apiLevel": 36,
            "appNetworkingDenied": True,
            "avdEphemeral": True,
            "guestAirplaneModeEnabled": True,
            "package": PACKAGE_NAME,
            "release": "16",
            "screenDensity": 420,
            "screenHeight": 2400,
            "screenWidth": 1080,
            "systemImagePackage": SYSTEM_IMAGE_PACKAGE,
        }
        for key, expected_value in exact_device_values.items():
            if device.get(key) != expected_value or type(device.get(key)) is not type(expected_value):
                failures.append(f"device.{key} must equal {expected_value!r}")
        if device.get("launchFlags") != list(LAUNCH_FLAGS):
            failures.append("device.launchFlags must match the exact headless cold-boot flags")
        if type(device.get("model")) is not str or not device["model"].strip():
            failures.append("device.model must be a nonempty string")

    try:
        avd_config_raw, _ = read_regular_file(result_directory / "avd-config.ini")
        launch_bytes, _ = read_regular_file(result_directory / "launch-argv.json")
    except EvidenceError as error:
        failures.append(f"AVD launch evidence readback failed: {error}")
    else:
        try:
            avd_config = avd_config_raw.decode("ascii")
        except UnicodeDecodeError:
            failures.append("avd-config.ini must be ASCII")
            avd_config = ""
        required_avd_lines = (
            "PlayStore.enabled = true",
            "abi.type = arm64-v8a",
            "fastboot.forceColdBoot = yes",
            "hw.cpu.arch = arm64",
            "hw.lcd.density = 420",
            "hw.lcd.height = 2400",
            "hw.lcd.width = 1080",
            f"image.sysdir.1 = {SYSTEM_IMAGE_RELATIVE.as_posix()}/",
            "target = android-36.1",
        )
        for line in required_avd_lines:
            if avd_config.splitlines().count(line) != 1:
                failures.append(f"avd-config.ini must contain one exact {line!r}")
        try:
            launch_argv = json.loads(launch_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            failures.append(f"launch-argv.json cannot be decoded: {error}")
        else:
            try:
                canonical_launch = canonical_json_bytes(launch_argv)
            except EvidenceError as error:
                failures.append(str(error))
            else:
                if launch_bytes != canonical_launch:
                    failures.append("launch-argv.json must use canonical JSON bytes")
            if type(launch_argv) is not list or any(type(item) is not str for item in launch_argv):
                failures.append("launch-argv.json must be a string array")
            elif type(run) is dict:
                if len(launch_argv) < 5:
                    failures.append("launch-argv.json is incomplete")
                else:
                    avd_name = launch_argv[2]
                    try:
                        expected_avd_config = avd_config_bytes(avd_name)
                    except EvidenceError as error:
                        failures.append(str(error))
                    else:
                        if avd_config_raw != expected_avd_config:
                            failures.append(
                                "avd-config.ini must match the exact owned AVD config"
                            )
                    expected = [
                        str(sdk_root / "emulator/emulator"),
                        "-avd",
                        avd_name,
                        "-port",
                        str(run.get("emulatorPort")),
                        *LAUNCH_FLAGS,
                    ]
                    if launch_argv != expected:
                        failures.append("launch-argv.json must match the exact owned launch")
                    expected_name = re.compile(
                        rf"AetherLink_API_36_1_{run.get('emulatorPort')}_[0-9a-f]{{8}}\Z"
                    )
                    if expected_name.fullmatch(avd_name) is None:
                        failures.append("launch-argv.json AVD name must bind the owned port")

    scenarios = payload["scenarios"]
    by_name: dict[object, dict[str, object]] = {}
    if type(scenarios) is not list:
        failures.append("scenarios must be an array")
    else:
        expected_names = [name for name, _ in SCENARIO_CHECKS]
        actual_names = [
            scenario.get("name") if type(scenario) is dict else None
            for scenario in scenarios
        ]
        if actual_names != expected_names:
            failures.append("scenarios must match the exact names and order")
        for index, (expected_name, expected_checks) in enumerate(SCENARIO_CHECKS):
            if index >= len(scenarios) or type(scenarios[index]) is not dict:
                continue
            scenario = scenarios[index]
            failures.extend(
                exact_keys(
                    scenario,
                    ("checks", "evidence", "name", "observations", "status"),
                    label=f"scenario {expected_name}",
                )
            )
            if scenario.get("status") != "passed":
                failures.append(f"scenario {expected_name} status must be 'passed'")
            checks = scenario.get("checks")
            if type(checks) is not dict or set(checks) != set(expected_checks):
                failures.append(f"scenario {expected_name} checks must match the exact contract")
            elif any(value is not True for value in checks.values()):
                failures.append(f"scenario {expected_name} checks must all be true")
            evidence = scenario.get("evidence")
            if evidence != SCENARIO_EVIDENCE[expected_name]:
                failures.append(
                    f"scenario {expected_name} evidence must match the exact retained tuple"
                )
            observations = scenario.get("observations")
            if type(observations) is not dict or not observations or any(
                type(key) is not str or not key or not json_observation_value(value)
                for key, value in observations.items()
            ):
                failures.append(f"scenario {expected_name} observations must be nonempty bounded JSON values")
            else:
                failures.extend(
                    scenario_observation_failures(
                        expected_name,
                        observations,
                        payload=payload,
                    )
                )
        by_name = {
            scenario.get("name"): scenario
            for scenario in scenarios
            if type(scenario) is dict and type(scenario.get("name")) is str
        }
        clean = by_name.get("clean_install_and_first_launch")
        cold = by_name.get("force_stop_cold_launch_repetition")
        if type(clean) is dict and type(cold) is dict:
            clean_observations = clean.get("observations")
            cold_observations = cold.get("observations")
            if (
                type(clean_observations) is dict
                and type(cold_observations) is dict
                and type(cold_observations.get("processIds")) is list
                and cold_observations["processIds"]
                and cold_observations["processIds"][0]
                != clean_observations.get("firstProcessId")
            ):
                failures.append(
                    "cold-launch processIds must begin with the clean firstProcessId"
                )

    try:
        process_observation_raw, _ = read_regular_file(
            result_directory / "app-process-observations.json"
        )
    except EvidenceError as error:
        failures.append(f"app process observation readback failed: {error}")
    else:
        observed_processes, process_failures = app_process_observation_failures(
            process_observation_raw,
            expected_serial=run.get("serial") if type(run) is dict else None,
        )
        failures.extend(process_failures)
        failures.extend(
            process_observation_binding_failures(by_name, observed_processes)
        )

    failures.extend(camera_permission_evidence_failures(result_directory))

    try:
        expected_evidence = evidence_manifest(result_directory)
    except EvidenceError as error:
        failures.append(f"retained evidence readback failed: {error}")
    else:
        if payload["evidence"] != expected_evidence:
            failures.append("evidence must exactly bind every retained evidence file")
    failures.extend(ui_semantic_failures(result_directory))

    logcat = payload["logcat"]
    failures.extend(
        exact_keys(
            logcat,
            ("fatalOrAnrMatches", "lineCount", "sha256"),
            label="logcat",
        )
    )
    if type(logcat) is dict:
        if logcat.get("fatalOrAnrMatches") != []:
            failures.append("logcat fatalOrAnrMatches must be empty")
        if type(logcat.get("lineCount")) is not int or logcat["lineCount"] < 1:
            failures.append("logcat.lineCount must be a positive integer")
        try:
            logcat_bytes, _ = read_regular_file(result_directory / "logcat.txt")
        except EvidenceError as error:
            failures.append(f"logcat readback failed: {error}")
        else:
            expected_logcat_sha = hashlib.sha256(logcat_bytes).hexdigest()
            if logcat.get("sha256") != expected_logcat_sha:
                failures.append("logcat.sha256 must bind logcat.txt")
            if logcat.get("lineCount") != len(logcat_bytes.splitlines()):
                failures.append("logcat.lineCount must match logcat.txt")
            direct_logcat_failures = app_logcat_failure_lines(
                logcat_bytes.decode("utf-8", "replace")
            )
            if direct_logcat_failures:
                failures.append(
                    "logcat.txt contains an AetherLink FATAL/ANR: "
                    + "; ".join(direct_logcat_failures)
                )

    exit_info = payload["exitInfo"]
    failures.extend(
        exact_keys(
            exit_info,
            ("forbiddenMatches", "lineCount", "sha256"),
            label="exitInfo",
        )
    )
    if type(exit_info) is dict:
        if exit_info.get("forbiddenMatches") != []:
            failures.append("exitInfo.forbiddenMatches must be empty")
        if type(exit_info.get("lineCount")) is not int or exit_info["lineCount"] < 1:
            failures.append("exitInfo.lineCount must be a positive integer")
        try:
            exit_bytes, _ = read_regular_file(result_directory / "exit-info.txt")
        except EvidenceError as error:
            failures.append(f"exit-info readback failed: {error}")
        else:
            expected_exit_sha = hashlib.sha256(exit_bytes).hexdigest()
            if exit_info.get("sha256") != expected_exit_sha:
                failures.append("exitInfo.sha256 must bind exit-info.txt")
            if exit_info.get("lineCount") != len(exit_bytes.splitlines()):
                failures.append("exitInfo.lineCount must match exit-info.txt")
            direct_exit_failures = app_exit_failure_lines(
                exit_bytes.decode("utf-8", "replace")
            )
            if direct_exit_failures:
                failures.append(
                    "exit-info.txt contains an AetherLink crash/ANR reason: "
                    + "; ".join(direct_exit_failures)
                )

    network = payload["networkIsolation"]
    failures.extend(
        exact_keys(
            network,
            (
                "after",
                "appNetworkingAfterDeny",
                "appNetworkingAfterLifecycle",
                "before",
                "guestAirplaneModeAfter",
                "guestAirplaneModeBefore",
            ),
            label="networkIsolation",
        )
    )
    if type(network) is dict:
        for phase in ("before", "after"):
            record = network.get(phase)
            failures.extend(
                exact_keys(
                    record,
                    ("lineCount", "sha256", "validatedInternetMatches"),
                    label=f"networkIsolation.{phase}",
                )
            )
            path = result_directory / f"network-state-{phase}.txt"
            try:
                raw, _ = read_regular_file(path)
            except EvidenceError as error:
                failures.append(f"network {phase} readback failed: {error}")
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                failures.append(f"network-state-{phase}.txt is not UTF-8: {error}")
                text = ""
            direct_matches = validated_network_lines(text)
            if type(record) is dict:
                if (
                    type(record.get("lineCount")) is not int
                    or record["lineCount"] < 1
                ):
                    failures.append(
                        f"networkIsolation.{phase}.lineCount must be a positive integer"
                    )
                elif record["lineCount"] != len(raw.splitlines()):
                    failures.append(f"networkIsolation.{phase}.lineCount must match")
                if record.get("sha256") != hashlib.sha256(raw).hexdigest():
                    failures.append(f"networkIsolation.{phase}.sha256 must match")
                if record.get("validatedInternetMatches") != direct_matches:
                    failures.append(
                        f"networkIsolation.{phase}.validatedInternetMatches must be direct"
                    )
            if direct_matches:
                failures.append(
                    f"network-state-{phase}.txt contains a validated Internet network"
                )

        control_states = (
            (
                "appNetworkingAfterDeny",
                "app-networking-after-deny.txt",
                APP_NETWORKING_DENIED_STATE,
            ),
            (
                "appNetworkingAfterLifecycle",
                "app-networking-after-lifecycle.txt",
                APP_NETWORKING_DENIED_STATE,
            ),
            (
                "guestAirplaneModeBefore",
                "guest-airplane-mode-before.txt",
                "enabled",
            ),
            (
                "guestAirplaneModeAfter",
                "guest-airplane-mode-after.txt",
                "enabled",
            ),
        )
        for key, relative, expected_value in control_states:
            record = network.get(key)
            failures.extend(
                exact_keys(
                    record,
                    ("lineCount", "sha256", "value"),
                    label=f"networkIsolation.{key}",
                )
            )
            try:
                raw, _ = read_regular_file(result_directory / relative)
            except EvidenceError as error:
                failures.append(f"{relative} readback failed: {error}")
                continue
            expected_raw = (expected_value + "\n").encode("ascii")
            if raw != expected_raw:
                failures.append(
                    f"{relative} must contain the one exact {expected_value!r} line"
                )
            if type(record) is dict:
                if type(record.get("lineCount")) is not int or record["lineCount"] != 1:
                    failures.append(
                        f"networkIsolation.{key}.lineCount must equal integer one"
                    )
                if record.get("sha256") != hashlib.sha256(raw).hexdigest():
                    failures.append(f"networkIsolation.{key}.sha256 must match")
                if record.get("value") != expected_value:
                    failures.append(
                        f"networkIsolation.{key}.value must equal {expected_value!r}"
                    )

    cleanup = payload["cleanup"]
    failures.extend(
        exact_keys(
            cleanup,
            (
                "ownedProcessExited",
                "ownedSerialAbsent",
                "postHostEmulators",
                "postSerials",
                "preexistingHostEmulators",
                "preexistingSerials",
                "preexistingSerialsPreserved",
                "temporaryAvdRemoved",
            ),
            label="cleanup",
        )
    )
    if type(cleanup) is dict and type(run) is dict:
        try:
            pre_bytes, _ = read_regular_file(result_directory / "pre-adb-devices.txt")
            post_bytes, _ = read_regular_file(result_directory / "post-adb-devices.txt")
        except EvidenceError as error:
            failures.append(f"adb cleanup snapshot readback failed: {error}")
        else:
            pre_serials = adb_serials_from_text(pre_bytes.decode("utf-8", "replace"))
            post_serials = adb_serials_from_text(post_bytes.decode("utf-8", "replace"))
            if cleanup.get("preexistingSerials") != pre_serials:
                failures.append("cleanup.preexistingSerials must match pre-adb-devices.txt")
            if cleanup.get("postSerials") != post_serials:
                failures.append("cleanup.postSerials must match post-adb-devices.txt")
            if not set(pre_serials).issubset(post_serials):
                failures.append("cleanup must preserve every preexisting adb serial")
            if run.get("serial") in post_serials:
                failures.append("cleanup post snapshot still contains the owned serial")
        try:
            pre_host_raw, _ = read_regular_file(
                result_directory / "pre-emulator-processes.json"
            )
            post_host_raw, _ = read_regular_file(
                result_directory / "post-emulator-processes.json"
            )
        except EvidenceError as error:
            failures.append(f"host emulator cleanup snapshot readback failed: {error}")
        else:
            pre_host, pre_host_failures = host_emulator_inventory_failures(
                pre_host_raw,
                label="pre-emulator-processes.json",
            )
            post_host, post_host_failures = host_emulator_inventory_failures(
                post_host_raw,
                label="post-emulator-processes.json",
            )
            failures.extend(pre_host_failures)
            failures.extend(post_host_failures)
            if cleanup.get("preexistingHostEmulators") != pre_host:
                failures.append(
                    "cleanup.preexistingHostEmulators must match the pre host inventory"
                )
            if cleanup.get("postHostEmulators") != post_host:
                failures.append(
                    "cleanup.postHostEmulators must match the post host inventory"
                )
            post_by_serial = {
                record.get("serial"): record
                for record in post_host
                if type(record.get("serial")) is str
            }
            for record in pre_host:
                if post_by_serial.get(record.get("serial")) != record:
                    failures.append(
                        "cleanup must preserve every preexisting host emulator "
                        "with the same PID and start identity"
                    )
                    break
            if any(record.get("serial") == run.get("serial") for record in post_host):
                failures.append(
                    "cleanup post host inventory still contains the owned emulator"
                )
        for key in (
            "ownedProcessExited",
            "ownedSerialAbsent",
            "preexistingSerialsPreserved",
            "temporaryAvdRemoved",
        ):
            if cleanup.get(key) is not True:
                failures.append(f"cleanup.{key} must be true")

    if payload["nonClaims"] != list(NON_CLAIMS):
        failures.append("nonClaims must match the exact bounded non-claim list")
    return failures


def result_failures(
    result_path: Path,
    *,
    root: Path = ROOT,
    sdk_root: Path,
    java_home: Path | None = None,
) -> list[str]:
    try:
        raw, _ = read_regular_file(result_path)
    except EvidenceError as error:
        return [str(error)]
    if len(raw) > 8 * 1024 * 1024:
        return ["result JSON exceeds the 8 MiB contract limit"]
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return [f"result JSON cannot be decoded: {error}"]
    try:
        expected_raw = canonical_json_bytes(payload)
    except EvidenceError as error:
        return [str(error)]
    failures: list[str] = []
    if raw != expected_raw:
        failures.append("result JSON must use exact canonical JSON bytes")
    failures.extend(
        payload_failures(
            payload,
            result_directory=result_path.parent,
            root=root,
            sdk_root=sdk_root,
            java_home=java_home,
        )
    )
    return failures


def default_sdk_root() -> Path:
    configured = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Library/Android/sdk").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path, help="canonical result JSON to read back")
    parser.add_argument("--sdk-root", type=Path, default=default_sdk_root())
    parser.add_argument("--java-home", type=Path, default=default_java_home())
    args = parser.parse_args()
    result_path = args.result.expanduser().resolve()
    sdk_root = args.sdk_root.expanduser().resolve()
    java_home = args.java_home.expanduser().resolve()
    failures = result_failures(
        result_path,
        sdk_root=sdk_root,
        java_home=java_home,
    )
    if failures:
        for failure in failures:
            print(f"Android headless lifecycle evidence failed: {failure}", file=sys.stderr)
        return 1
    raw = result_path.read_bytes()
    payload = json.loads(raw)
    print(
        "Android headless lifecycle evidence passed: "
        f"{len(payload['scenarios'])}/{len(SCENARIO_CHECKS)} scenarios; "
        f"source={payload['source']['sha256']}; "
        f"result={hashlib.sha256(raw).hexdigest()}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
