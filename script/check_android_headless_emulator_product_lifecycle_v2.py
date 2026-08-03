#!/usr/bin/env python3
"""Independently read back the API 36.1 lifecycle v2 successor evidence."""

from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat as stat_module
import sys
from typing import Iterable, Mapping
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script import check_android_headless_emulator_product_lifecycle as v1


CONTRACT = "aetherlink-android-headless-emulator-product-lifecycle-v2"
SCHEMA_VERSION = 2
RUN_ID_RE = re.compile(
    r"android-headless-api36-1-v2-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z"
)
PROCESS_OBSERVATION_LABELS = (
    "before_doze",
    "after_doze",
    "before_kill",
    "after_kill",
    "before_reboot",
    "after_reboot",
    "future_data_first_launch",
    "future_data_second_launch",
    "legacy_migration_first_launch",
    "legacy_migration_second_launch",
)
BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
PACKAGE_NAME = v1.PACKAGE_NAME
PERMISSION_CONTROLLER_PACKAGES = (
    "com.android.permissioncontroller",
    "com.google.android.permissioncontroller",
)
PREFERENCES_RELATIVE = "shared_prefs/aetherlink_pairing_qr_camera_permission.xml"
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
LEGACY_RUNTIME_LOCAL_STORE_SEED = (
    b'<?xml version="1.0" encoding="utf-8" standalone="yes" ?>\n'
    b"<map>\n"
    b'    <string name="runtime_data">'
    b"{&quot;appTheme&quot;:&quot;dark&quot;,&quot;composerDraft&quot;:"
    b"&quot;legacy-v0&quot;,&quot;trustedRuntimeAutoReconnectEnabled&quot;:false}"
    b"</string>\n"
    b"</map>\n"
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

SCENARIO_CHECKS = (
    (
        "background_doze_recovery",
        (
            "mainActivityBackgrounded",
            "deepIdleForced",
            "deepIdleUnforced",
            "sameProcessIdentityPreserved",
            "activityResumedAfterDoze",
            "pairingUiRecovered",
            "durableCameraRequestStatePreserved",
        ),
    ),
    (
        "background_process_kill_recovery",
        (
            "mainActivityBackgrounded",
            "sameUidSigkillSucceeded",
            "packageProcessAbsent",
            "newProcessIdentityObserved",
            "pairingUiRecovered",
            "durableCameraRequestStatePreserved",
        ),
    ),
    (
        "full_emulator_reboot_durable_state_recovery",
        (
            "adbTransportDisconnectedAndReconnected",
            "kernelBootIdChanged",
            "ownedQemuIdentityPreserved",
            "bootCompleted",
            "installedApkExactByteMatch",
            "cameraRequestStatePreserved",
            "cameraPermissionDenialPreserved",
            "followSystemLocalePreserved",
            "fontScalePreserved",
            "networkIsolationReapplied",
            "pairingUiRecovered",
            "settingsRecoveryVisible",
        ),
    ),
    (
        "future_local_data_update_required_cold_launch_preservation",
        (
            "futureVersionSeededExactly",
            "firstColdLaunchUpdateRequiredVisible",
            "firstColdLaunchPairingUiVisible",
            "firstColdLaunchSavedDataPreserved",
            "secondColdLaunchUpdateRequiredVisible",
            "secondColdLaunchPairingUiVisible",
            "secondColdLaunchSavedDataPreserved",
            "distinctColdLaunchProcessIdentityObserved",
        ),
    ),
    (
        "legacy_versionless_local_data_migration_cold_launch_stability",
        (
            "legacyVersionlessSeededExactly",
            "firstColdLaunchMigrationCompleted",
            "firstColdLaunchSettingsPreserved",
            "firstColdLaunchUpdateRequiredAbsent",
            "firstColdLaunchPairingUiVisible",
            "secondColdLaunchMigratedBytesStable",
            "secondColdLaunchSettingsPreserved",
            "secondColdLaunchUpdateRequiredAbsent",
            "secondColdLaunchPairingUiVisible",
            "distinctColdLaunchProcessIdentityObserved",
        ),
    ),
)

SCENARIO_EVIDENCE = {
    "background_doze_recovery": [
        "activity-after-doze.txt",
        "activity-background-before-doze.txt",
        "app-process-observations.json",
        "camera-request-state-after-doze.xml",
        "camera-request-state-before.xml",
        "deviceidle-force-idle.txt",
        "deviceidle-state-forced.txt",
        "deviceidle-state-unforced.txt",
        "deviceidle-unforce.txt",
        "ui/background-after-doze.xml",
        "ui/background-before-doze.xml",
    ],
    "background_process_kill_recovery": [
        "activity-background-before-kill.txt",
        "process-kill-receipt.json",
        "app-process-observations.json",
        "camera-request-state-after-kill.xml",
        "camera-request-state-before.xml",
        "pidof-absence-receipt.json",
        "ui/after-process-kill.xml",
    ],
    "full_emulator_reboot_durable_state_recovery": [
        "adb-reboot-receipt.json",
        "app-locales-after-reboot.txt",
        "app-locales-before.txt",
        "app-networking-after-reboot.txt",
        "app-process-observations.json",
        "boot-completed-after-reboot.txt",
        "boot-id-after.txt",
        "boot-id-before.txt",
        "camera-permission-after-reboot.txt",
        "camera-permission-before.txt",
        "camera-request-state-after-reboot.xml",
        "camera-request-state-before.xml",
        "font-scale-after-reboot.txt",
        "font-scale-before.txt",
        "guest-airplane-after-reboot.txt",
        "installed-base-after-reboot.apk",
        "installed-base-before.apk",
        "network-state-after-reboot.txt",
        "owned-emulator-after-reboot.json",
        "owned-emulator-before-reboot.json",
        "package-path-after-reboot.txt",
        "package-path-before.txt",
        "reboot-transport-observations.json",
        "ui/follow-system-after-reboot-drawer.xml",
        "ui/follow-system-after-reboot.xml",
        "ui/follow-system-before-reboot-drawer.xml",
        "ui/follow-system-before-reboot.xml",
        "ui/after-reboot-camera-settings-recovery.xml",
        "ui/after-reboot.xml",
    ],
    "future_local_data_update_required_cold_launch_preservation": [
        "app-process-observations.json",
        "runtime-local-store-after-future-version-first-launch.xml",
        "runtime-local-store-after-future-version-second-launch.xml",
        "runtime-local-store-future-version-seed.xml",
        "ui/future-data-first-launch.xml",
        "ui/future-data-second-launch.xml",
    ],
    "legacy_versionless_local_data_migration_cold_launch_stability": [
        "app-process-observations.json",
        "runtime-local-store-after-legacy-migration-first-launch.xml",
        "runtime-local-store-after-legacy-migration-second-launch.xml",
        "runtime-local-store-legacy-versionless-seed.xml",
        "ui/legacy-migration-first-launch.xml",
        "ui/legacy-migration-second-launch.xml",
    ],
}

EVIDENCE_PATHS = (
    "activity-after-doze.txt",
    "activity-background-before-doze.txt",
    "activity-background-before-kill.txt",
    "adb-reboot-receipt.json",
    "app-locales-after-reboot.txt",
    "app-locales-before.txt",
    "app-networking-after-reboot.txt",
    "app-networking-before.txt",
    "app-process-observations.json",
    "avd-config.ini",
    "boot-completed-after-reboot.txt",
    "boot-id-after.txt",
    "boot-id-before.txt",
    "camera-permission-after-reboot.txt",
    "camera-permission-before.txt",
    "camera-request-state-after-doze.xml",
    "camera-request-state-after-kill.xml",
    "camera-request-state-after-reboot.xml",
    "camera-request-state-before.xml",
    "deviceidle-force-idle.txt",
    "deviceidle-state-forced.txt",
    "deviceidle-state-unforced.txt",
    "deviceidle-unforce.txt",
    "emulator.log",
    "exit-info-after-reboot.txt",
    "exit-info-before-reboot.txt",
    "font-scale-after-reboot.txt",
    "font-scale-before.txt",
    "gradle-build.log",
    "guest-airplane-after-reboot.txt",
    "guest-airplane-before.txt",
    "installed-base-after-reboot.apk",
    "installed-base-before.apk",
    "launch-argv.json",
    "logcat-after-reboot.txt",
    "logcat-before-reboot.txt",
    "network-state-after-reboot.txt",
    "network-state-before.txt",
    "owned-emulator-after-reboot.json",
    "owned-emulator-before-reboot.json",
    "package-path-after-reboot.txt",
    "package-path-before.txt",
    "pidof-absence-receipt.json",
    "process-kill-receipt.json",
    "post-adb-devices.txt",
    "post-emulator-processes.json",
    "pre-adb-devices.txt",
    "pre-emulator-processes.json",
    "reboot-transport-observations.json",
    "runtime-local-store-after-future-version-first-launch.xml",
    "runtime-local-store-after-future-version-second-launch.xml",
    "runtime-local-store-future-version-seed.xml",
    "runtime-local-store-after-legacy-migration-first-launch.xml",
    "runtime-local-store-after-legacy-migration-second-launch.xml",
    "runtime-local-store-legacy-versionless-seed.xml",
    "ui/after-process-kill.xml",
    "ui/after-reboot-camera-settings-recovery.xml",
    "ui/after-reboot.xml",
    "ui/background-after-doze.xml",
    "ui/background-before-doze.xml",
    "ui/follow-system-after-reboot-drawer.xml",
    "ui/follow-system-after-reboot.xml",
    "ui/follow-system-before-reboot-drawer.xml",
    "ui/follow-system-before-reboot.xml",
    "ui/future-data-first-launch.xml",
    "ui/future-data-second-launch.xml",
    "ui/legacy-migration-first-launch.xml",
    "ui/legacy-migration-second-launch.xml",
    "ui/setup-camera-denied.xml",
    "ui/setup-camera-permission-dialog.xml",
    "ui/setup-camera-settings-recovery.xml",
    "ui/setup-first-launch.xml",
)

NON_CLAIMS = tuple(
    claim
    for claim in v1.NON_CLAIMS
    if claim not in {"background-or-doze", "device-reboot"}
)
SOURCE_SUCCESSOR_FILES = (
    Path("script/run_android_headless_emulator_product_lifecycle_v2.py"),
    Path("script/check_android_headless_emulator_product_lifecycle_v2.py"),
    Path(".github/workflows/product-nightly.yml"),
    Path("script/check_product_nightly_ci.py"),
    Path("script/test_check_product_nightly_ci.py"),
    Path("script/check_no_device_quality.sh"),
    Path("script/test_run_android_headless_emulator_product_lifecycle.py"),
    Path("script/test_check_android_headless_emulator_product_lifecycle.py"),
    Path("script/test_run_android_headless_emulator_product_lifecycle_v2.py"),
    Path("script/test_check_android_headless_emulator_product_lifecycle_v2.py"),
)
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_EVIDENCE_FILE_BYTES = 256 * 1024 * 1024
MAX_EVIDENCE_TOTAL_BYTES = 512 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024


EvidenceError = v1.EvidenceError
canonical_json_bytes = v1.canonical_json_bytes
file_record = v1.file_record
exact_keys = v1.exact_keys
valid_sha256 = v1.valid_sha256
default_java_home = v1.default_java_home
sdk_tool_identity = v1.sdk_tool_identity
java_tool_identity = v1.java_tool_identity
system_image_snapshot = v1.system_image_snapshot
avd_config_bytes = v1.avd_config_bytes


def _ancestor_identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_uid,
        status.st_gid,
    )


def _directory_identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        *_ancestor_identity(status),
        status.st_nlink,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _file_identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_uid,
        status.st_gid,
        status.st_nlink,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


@dataclass(frozen=True)
class CapturedEvidenceFile:
    data: bytes
    identity: tuple[int, ...]
    mode: str

    def record(self, relative: str) -> dict[str, object]:
        return {
            "mode": self.mode,
            "path": relative,
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "size": len(self.data),
        }


class EvidenceSnapshot:
    """Hold and capture one closed physical evidence graph."""

    def __init__(self, result_path: Path, *, result_required: bool = True) -> None:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise EvidenceError("evidence snapshot requires O_NOFOLLOW and O_DIRECTORY")
        absolute = Path(os.path.abspath(os.fspath(result_path)))
        if absolute.name != "result.json":
            raise EvidenceError("result path basename must equal result.json")
        self.result_path = absolute
        self.result_directory = absolute.parent
        self.result_required = result_required
        self.ancestor_fds: list[int] = []
        self.ancestor_names: list[str] = []
        self.ancestor_identities: list[tuple[int, ...]] = []
        self.directory_fds: dict[str, int] = {}
        self.directory_identities: dict[str, tuple[int, ...]] = {}
        self.directory_inventories: dict[str, frozenset[str]] = {}
        self.file_fds: dict[str, int] = {}
        self.file_identities: dict[str, tuple[int, ...]] = {}
        self.files: dict[str, CapturedEvidenceFile] = {}
        self._closed = False
        try:
            self._open_graph()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _flags(*, directory: bool) -> int:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
        return flags | os.O_DIRECTORY if directory else flags

    @staticmethod
    def _expected_inventories(
        *, result_required: bool, result_present: bool
    ) -> dict[str, frozenset[str]]:
        top_files = {
            relative for relative in EVIDENCE_PATHS if "/" not in relative
        }
        if result_required or result_present:
            top_files.add("result.json")
        ui_files = {
            relative.removeprefix("ui/")
            for relative in EVIDENCE_PATHS
            if relative.startswith("ui/")
        }
        return {
            "": frozenset(top_files | {"ui"}),
            "ui": frozenset(ui_files),
        }

    def _open_graph(self) -> None:
        directory_flags = self._flags(directory=True)
        file_flags = self._flags(directory=False)
        root_fd = os.open(os.sep, directory_flags)
        self.ancestor_fds.append(root_fd)
        self.ancestor_names.append(os.sep)
        self.ancestor_identities.append(_ancestor_identity(os.fstat(root_fd)))
        parent_fd = root_fd
        for part in self.result_directory.parts[1:]:
            try:
                descriptor = os.open(part, directory_flags, dir_fd=parent_fd)
            except OSError as error:
                raise EvidenceError(
                    f"cannot open evidence ancestor without following links: {part}: {error}"
                ) from error
            status = os.fstat(descriptor)
            if not stat_module.S_ISDIR(status.st_mode):
                os.close(descriptor)
                raise EvidenceError(f"evidence ancestor is not a directory: {part}")
            self.ancestor_fds.append(descriptor)
            self.ancestor_names.append(part)
            self.ancestor_identities.append(_ancestor_identity(status))
            parent_fd = descriptor

        result_fd = self.ancestor_fds[-1]
        result_status = os.fstat(result_fd)
        if result_status.st_uid != os.getuid():
            raise EvidenceError("evidence result directory must be owned by the current user")
        self.directory_fds[""] = result_fd
        self.directory_identities[""] = _directory_identity(result_status)
        result_inventory = frozenset(os.listdir(result_fd))
        result_present = "result.json" in result_inventory
        if self.result_required and not result_present:
            raise EvidenceError("closed evidence tree is missing result.json")
        expected_inventories = self._expected_inventories(
            result_required=self.result_required,
            result_present=result_present,
        )
        if result_inventory != expected_inventories[""]:
            raise EvidenceError(
                "evidence file set must be closed; "
                f"expected={sorted(expected_inventories[''])!r}, "
                f"found={sorted(result_inventory)!r}"
            )
        self.directory_inventories[""] = result_inventory

        try:
            ui_fd = os.open("ui", directory_flags, dir_fd=result_fd)
        except OSError as error:
            raise EvidenceError(
                f"cannot open evidence directory without following links: ui: {error}"
            ) from error
        ui_status = os.fstat(ui_fd)
        if (
            not stat_module.S_ISDIR(ui_status.st_mode)
            or ui_status.st_uid != os.getuid()
        ):
            os.close(ui_fd)
            raise EvidenceError("evidence ui directory identity differs")
        self.directory_fds["ui"] = ui_fd
        self.directory_identities["ui"] = _directory_identity(ui_status)
        ui_inventory = frozenset(os.listdir(ui_fd))
        if ui_inventory != expected_inventories["ui"]:
            raise EvidenceError(
                "evidence ui file set must be closed; "
                f"expected={sorted(expected_inventories['ui'])!r}, "
                f"found={sorted(ui_inventory)!r}"
            )
        self.directory_inventories["ui"] = ui_inventory

        relatives = list(EVIDENCE_PATHS)
        if self.result_required:
            relatives.append("result.json")
        for relative in sorted(relatives, key=lambda value: value.encode("ascii")):
            directory, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
            try:
                descriptor = os.open(
                    name, file_flags, dir_fd=self.directory_fds[directory]
                )
            except OSError as error:
                raise EvidenceError(
                    "cannot open evidence file without following links: "
                    f"{relative}: {error}"
                ) from error
            status = os.fstat(descriptor)
            if (
                not stat_module.S_ISREG(status.st_mode)
                or status.st_uid != os.getuid()
                or status.st_nlink != 1
                or status.st_size > MAX_EVIDENCE_FILE_BYTES
            ):
                os.close(descriptor)
                raise EvidenceError(f"evidence file identity differs: {relative}")
            self.file_fds[relative] = descriptor
            self.file_identities[relative] = _file_identity(status)
        self._verify_held_graph()

    def _verify_held_graph(self) -> None:
        for index, expected in enumerate(self.ancestor_identities):
            descriptor = self.ancestor_fds[index]
            if _ancestor_identity(os.fstat(descriptor)) != expected:
                raise EvidenceError(
                    f"evidence ancestor changed: {self.ancestor_names[index]}"
                )
            if index:
                current = os.stat(
                    self.ancestor_names[index],
                    dir_fd=self.ancestor_fds[index - 1],
                    follow_symlinks=False,
                )
                if (
                    not stat_module.S_ISDIR(current.st_mode)
                    or _ancestor_identity(current) != expected
                ):
                    raise EvidenceError(
                        f"evidence ancestor path changed: {self.ancestor_names[index]}"
                    )
        for relative, expected in self.directory_identities.items():
            descriptor = self.directory_fds[relative]
            if _directory_identity(os.fstat(descriptor)) != expected:
                raise EvidenceError(f"evidence directory changed: {relative or '.'}")
            inventory = frozenset(os.listdir(descriptor))
            if inventory != self.directory_inventories[relative]:
                raise EvidenceError(
                    f"evidence directory inventory changed: {relative or '.'}"
                )
            if relative:
                current = os.stat(
                    relative,
                    dir_fd=self.directory_fds[""],
                    follow_symlinks=False,
                )
                if (
                    not stat_module.S_ISDIR(current.st_mode)
                    or _directory_identity(current) != expected
                ):
                    raise EvidenceError(f"evidence directory path changed: {relative}")
        for relative, expected in self.file_identities.items():
            directory, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
            current = os.stat(
                name,
                dir_fd=self.directory_fds[directory],
                follow_symlinks=False,
            )
            if (
                not stat_module.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or _file_identity(current) != expected
                or _file_identity(os.fstat(self.file_fds[relative])) != expected
            ):
                raise EvidenceError(f"evidence file graph changed: {relative}")

    def capture(self) -> Mapping[str, CapturedEvidenceFile]:
        total_capture = 0
        for relative, descriptor in self.file_fds.items():
            before = os.fstat(descriptor)
            expected = self.file_identities[relative]
            if _file_identity(before) != expected:
                raise EvidenceError(f"evidence file changed before capture: {relative}")
            os.lseek(descriptor, 0, os.SEEK_SET)
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > before.st_size:
                    raise EvidenceError(f"evidence file grew during capture: {relative}")
                chunks.append(chunk)
            after = os.fstat(descriptor)
            if _file_identity(after) != expected or total != before.st_size:
                raise EvidenceError(f"evidence file changed during capture: {relative}")
            total_capture += total
            if total_capture > MAX_EVIDENCE_TOTAL_BYTES:
                raise EvidenceError("evidence capture exceeds the total byte limit")
            self.files[relative] = CapturedEvidenceFile(
                b"".join(chunks),
                expected,
                v1.normalized_mode(before.st_mode),
            )
        self._verify_held_graph()
        return self.files

    def verify_unchanged(self) -> None:
        self._verify_held_graph()
        current = EvidenceSnapshot(
            self.result_path,
            result_required=self.result_required,
        )
        try:
            if (
                current.ancestor_identities != self.ancestor_identities
                or current.directory_identities != self.directory_identities
                or current.directory_inventories != self.directory_inventories
                or current.file_identities != self.file_identities
            ):
                raise EvidenceError("evidence graph changed during verification")
        finally:
            current.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for descriptor in self.file_fds.values():
            try:
                os.close(descriptor)
            except OSError:
                pass
        self.file_fds.clear()
        ui_fd = self.directory_fds.get("ui")
        if ui_fd is not None:
            try:
                os.close(ui_fd)
            except OSError:
                pass
        self.directory_fds.clear()
        for descriptor in reversed(self.ancestor_fds):
            try:
                os.close(descriptor)
            except OSError:
                pass
        self.ancestor_fds.clear()

    def __enter__(self) -> EvidenceSnapshot:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def collect_source_paths(root: Path = ROOT) -> tuple[Path, ...]:
    candidates = set(v1.collect_source_paths(root))
    for relative in SOURCE_SUCCESSOR_FILES:
        candidate = root / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise EvidenceError(f"required v2 source input is missing: {relative}")
        candidates.add(candidate)
    return tuple(
        sorted(candidates, key=lambda path: path.relative_to(root).as_posix().encode("ascii"))
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


def evidence_manifest_from_snapshot(
    evidence: Mapping[str, CapturedEvidenceFile],
) -> list[dict[str, object]]:
    try:
        return [evidence[relative].record(relative) for relative in EVIDENCE_PATHS]
    except KeyError as error:
        raise EvidenceError(f"captured evidence is missing {error.args[0]}") from error


def evidence_manifest(result_directory: Path) -> list[dict[str, object]]:
    """Safely build a fixture/producer-compatible manifest from one snapshot."""

    with EvidenceSnapshot(
        result_directory / "result.json", result_required=False
    ) as snapshot:
        evidence = snapshot.capture()
        manifest = evidence_manifest_from_snapshot(evidence)
        snapshot.verify_unchanged()
        return manifest


def duplicate_rejecting_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_canonical_json(
    raw: bytes,
    *,
    label: str,
    maximum: int = MAX_JSON_BYTES,
) -> object:
    if type(raw) is not bytes or not (1 <= len(raw) <= maximum):
        raise EvidenceError(f"{label} must be nonempty and at most {maximum} bytes")
    try:
        value = json.loads(raw, object_pairs_hook=duplicate_rejecting_object)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise EvidenceError(f"{label} cannot be decoded: {error}") from error
    if raw != canonical_json_bytes(value):
        raise EvidenceError(f"{label} must use canonical JSON bytes")
    return value


def parse_utc(value: object, *, label: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise EvidenceError(f"{label} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise EvidenceError(f"{label} is not ISO-8601: {error}") from error
    if parsed.tzinfo != timezone.utc:
        raise EvidenceError(f"{label} must use UTC")
    return parsed


def exact_file_bytes(
    evidence: Mapping[str, CapturedEvidenceFile], relative: str
) -> bytes:
    try:
        return evidence[relative].data
    except KeyError as error:
        raise EvidenceError(f"captured evidence is missing {relative}") from error


def process_observation_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
    *,
    expected_serial: object,
) -> tuple[dict[str, tuple[str, int, int]], list[str]]:
    failures: list[str] = []
    try:
        value = load_canonical_json(
            exact_file_bytes(evidence, "app-process-observations.json"),
            label="app-process-observations.json",
        )
    except EvidenceError as error:
        return {}, [str(error)]
    if type(value) is not list:
        return {}, ["app-process-observations.json must be an array"]
    if len(value) != len(PROCESS_OBSERVATION_LABELS):
        failures.append(
            f"app-process-observations.json must contain {len(PROCESS_OBSERVATION_LABELS)} records"
        )
    observed: dict[str, tuple[str, int, int]] = {}
    keys = (
        "bootId",
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
    )
    for index, record in enumerate(value):
        label = f"app-process-observations.json[{index}]"
        failures.extend(exact_keys(record, keys, label=label))
        if type(record) is not dict:
            continue
        expected_label = PROCESS_OBSERVATION_LABELS[index] if index < len(PROCESS_OBSERVATION_LABELS) else None
        actual_label = record.get("label")
        if actual_label != expected_label:
            failures.append(f"{label}.label must equal {expected_label!r}")
        boot_id = record.get("bootId")
        if type(boot_id) is not str or BOOT_ID_RE.fullmatch(boot_id) is None:
            failures.append(f"{label}.bootId must be a lowercase UUID")
        if record.get("command") != ["pidof", PACKAGE_NAME]:
            failures.append(f"{label}.command must be the exact package pidof")
        if record.get("serial") != expected_serial:
            failures.append(f"{label}.serial must equal the owned serial")
        stdout = record.get("stdout")
        if type(stdout) is not str or re.fullmatch(r"[1-9][0-9]{0,9}\n", stdout) is None:
            failures.append(f"{label}.stdout must be one exact PID line")
            continue
        pid = int(stdout.removesuffix("\n"))
        if pid > 2_147_483_647:
            failures.append(f"{label} PID exceeds the Android range")
            continue
        proc_path = f"/proc/{pid}"
        if record.get("procCmdlineCommand") != ["cat", f"{proc_path}/cmdline"]:
            failures.append(f"{label}.procCmdlineCommand must bind the PID")
        if record.get("procStatBeforeCommand") != ["cat", f"{proc_path}/stat"]:
            failures.append(f"{label}.procStatBeforeCommand must bind the PID")
        if record.get("procStatAfterCommand") != ["cat", f"{proc_path}/stat"]:
            failures.append(f"{label}.procStatAfterCommand must bind the PID")
        valid = True
        encoded = record.get("procCmdlineBase64")
        try:
            cmdline = base64.b64decode(encoded, validate=True) if type(encoded) is str else b""
        except (binascii.Error, ValueError):
            cmdline = b""
        package = PACKAGE_NAME.encode("ascii")
        if (
            not (1 <= len(cmdline) <= 4096)
            or not cmdline.startswith(package + b"\0")
            or cmdline.rstrip(b"\0") != package
        ):
            failures.append(f"{label}.procCmdlineBase64 must identify the exact package")
            valid = False

        def start_ticks(field: str) -> int | None:
            nonlocal valid
            raw = record.get(field)
            if type(raw) is not str or not (1 <= len(raw) <= 4096):
                failures.append(f"{label}.{field} must be bounded text")
                valid = False
                return None
            try:
                raw.encode("ascii")
            except UnicodeEncodeError:
                failures.append(f"{label}.{field} must be ASCII")
                valid = False
                return None
            match = re.fullmatch(rf"{pid} \(([^()\n]{{1,128}})\) ([^\n]+)\n", raw)
            if match is None:
                failures.append(f"{label}.{field} must bind the exact PID")
                valid = False
                return None
            fields = match.group(2).split()
            if len(fields) < 20 or re.fullmatch(r"[1-9][0-9]{0,19}", fields[19]) is None:
                failures.append(f"{label}.{field} must expose positive start ticks")
                valid = False
                return None
            ticks = int(fields[19])
            if ticks > 9_223_372_036_854_775_807:
                failures.append(f"{label}.{field} start ticks exceed int64")
                valid = False
                return None
            return ticks

        before = start_ticks("procStatBeforeStdout")
        after = start_ticks("procStatAfterStdout")
        claimed = record.get("processStartTicks")
        if (
            before is None
            or after is None
            or before != after
            or type(claimed) is not int
            or claimed != before
        ):
            failures.append(f"{label} must retain one exact process start identity")
            valid = False
        if type(actual_label) is str and actual_label in observed:
            failures.append(f"{label}.label must be unique")
        elif valid and type(actual_label) is str and type(boot_id) is str and type(claimed) is int:
            observed[actual_label] = (boot_id, pid, claimed)
    return observed, failures


def camera_state_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
) -> tuple[str | None, list[str]]:
    failures: list[str] = []
    preference_paths = (
        "camera-request-state-before.xml",
        "camera-request-state-after-doze.xml",
        "camera-request-state-after-kill.xml",
        "camera-request-state-after-reboot.xml",
    )
    raws: list[bytes] = []
    for relative in preference_paths:
        try:
            raw = exact_file_bytes(evidence, relative)
        except EvidenceError as error:
            failures.append(f"{relative} cannot be read: {error}")
            continue
        if not (1 <= len(raw) <= 64 * 1024):
            failures.append(f"{relative} must be nonempty and at most 64 KiB")
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            failures.append(f"{relative} is malformed XML: {error}")
            continue
        children = list(root)
        if (
            root.tag != "map"
            or len(children) != 1
            or children[0].tag != "string"
            or children[0].attrib != {"name": "request_state"}
            or children[0].text != "recorded"
            or list(children[0])
        ):
            failures.append(f"{relative} must contain only request_state=recorded")
        raws.append(raw)
    if len(raws) == len(preference_paths) and len(set(raws)) != 1:
        failures.append("camera request-state preference bytes must remain exact across every lifecycle")
    preference_sha = hashlib.sha256(raws[0]).hexdigest() if raws else None

    for relative in ("camera-permission-before.txt", "camera-permission-after-reboot.txt"):
        try:
            raw = exact_file_bytes(evidence, relative)
        except EvidenceError as error:
            failures.append(f"{relative} cannot be read: {error}")
            continue
        if not (1 <= len(raw) <= 4 * 1024 * 1024):
            failures.append(f"{relative} must be bounded")
            continue
        states = re.findall(
            rb"(?m)^[ \t]*android\.permission\.CAMERA: granted=(true|false)(?:,[^\r\n]*)?\r?$",
            raw,
        )
        if states != [b"false"]:
            failures.append(f"{relative} must contain exactly one CAMERA granted=false state")
    return preference_sha, failures


def future_runtime_local_data_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
) -> tuple[dict[str, object], list[str]]:
    failures: list[str] = []
    paths = (
        "runtime-local-store-future-version-seed.xml",
        "runtime-local-store-after-future-version-first-launch.xml",
        "runtime-local-store-after-future-version-second-launch.xml",
    )
    try:
        root = ET.fromstring(FUTURE_RUNTIME_LOCAL_STORE_SEED)
    except ET.ParseError as error:
        return {}, [f"future-version seed contract is malformed XML: {error}"]
    children = list(root)
    if (
        root.tag != "map"
        or len(children) != 1
        or children[0].tag != "string"
        or children[0].attrib != {"name": "runtime_data"}
        or children[0].text != '{"version":2}'
        or list(children[0])
    ):
        failures.append("future-version seed contract must contain only runtime_data version 2")
    for relative in paths:
        try:
            raw = exact_file_bytes(evidence, relative)
        except EvidenceError as error:
            failures.append(f"{relative} cannot be read: {error}")
            continue
        if raw != FUTURE_RUNTIME_LOCAL_STORE_SEED:
            failures.append(f"{relative} must preserve the exact future-version seed bytes")
    return {
        "sha256": hashlib.sha256(FUTURE_RUNTIME_LOCAL_STORE_SEED).hexdigest(),
        "size": len(FUTURE_RUNTIME_LOCAL_STORE_SEED),
        "version": 2,
    }, failures


def runtime_local_store_json_failures(
    raw: bytes,
    *,
    label: str,
) -> tuple[dict[str, object], list[str]]:
    failures: list[str] = []
    if not (1 <= len(raw) <= 1024 * 1024):
        return {}, [f"{label} must be nonempty and at most 1 MiB"]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        return {}, [f"{label} is malformed XML: {error}"]
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
        return {}, [f"{label} must contain only one runtime_data string"]
    try:
        value = json.loads(
            children[0].text,
            object_pairs_hook=duplicate_rejecting_object,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, EvidenceError) as error:
        return {}, [f"{label} runtime_data cannot be decoded: {error}"]
    if type(value) is not dict:
        failures.append(f"{label} runtime_data must be a JSON object")
        return {}, failures
    return value, failures


def legacy_runtime_local_data_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
) -> tuple[dict[str, object], list[str]]:
    failures: list[str] = []
    seed_path = "runtime-local-store-legacy-versionless-seed.xml"
    try:
        seed = exact_file_bytes(evidence, seed_path)
    except EvidenceError as error:
        return {}, [f"{seed_path} cannot be read: {error}"]
    if seed != LEGACY_RUNTIME_LOCAL_STORE_SEED:
        failures.append(f"{seed_path} must equal the exact versionless seed bytes")
    seed_value, seed_failures = runtime_local_store_json_failures(
        seed,
        label=seed_path,
    )
    failures.extend(seed_failures)
    expected_seed_value = {
        "appTheme": "dark",
        "composerDraft": "legacy-v0",
        "trustedRuntimeAutoReconnectEnabled": False,
    }
    if seed_value != expected_seed_value or "version" in seed_value:
        failures.append(
            f"{seed_path} must contain exactly the versionless legacy fixture"
        )

    migrated_paths = (
        "runtime-local-store-after-legacy-migration-first-launch.xml",
        "runtime-local-store-after-legacy-migration-second-launch.xml",
    )
    migrated_raw: list[bytes] = []
    migrated_values: list[dict[str, object]] = []
    for relative in migrated_paths:
        try:
            raw = exact_file_bytes(evidence, relative)
        except EvidenceError as error:
            failures.append(f"{relative} cannot be read: {error}")
            continue
        value, value_failures = runtime_local_store_json_failures(
            raw,
            label=relative,
        )
        failures.extend(value_failures)
        migrated_raw.append(raw)
        migrated_values.append(value)
        expected = {
            "appLanguageSource": "system",
            "appLanguageTag": "en",
            "appTheme": "dark",
            "composerDraft": "legacy-v0",
            "trustedRuntimeAutoReconnectEnabled": False,
        }
        for key, expected_value in expected.items():
            if type(value.get(key)) is not type(expected_value) or value.get(key) != expected_value:
                failures.append(
                    f"{relative} must preserve {key}={expected_value!r}"
                )
        for key, expected_value in (
            ("version", 1),
            ("androidAppLanguagePlatformMigrationVersion", 1),
        ):
            if type(value.get(key)) is not int or value.get(key) != expected_value:
                failures.append(
                    f"{relative} must contain integer {key}={expected_value}"
                )
    if len(migrated_raw) == len(migrated_paths):
        if migrated_raw[0] == LEGACY_RUNTIME_LOCAL_STORE_SEED:
            failures.append("first legacy cold launch must rewrite the versionless seed")
        if migrated_raw[0] != migrated_raw[1]:
            failures.append("migrated legacy bytes must remain exact across cold launches")
    first_raw = migrated_raw[0] if migrated_raw else b""
    first_value = migrated_values[0] if migrated_values else {}
    return {
        "appTheme": first_value.get("appTheme"),
        "composerDraft": first_value.get("composerDraft"),
        "sha256": hashlib.sha256(first_raw).hexdigest() if first_raw else None,
        "size": len(first_raw) if first_raw else None,
        "trustedRuntimeAutoReconnectEnabled": first_value.get(
            "trustedRuntimeAutoReconnectEnabled"
        ),
        "version": first_value.get("version"),
    }, failures


def lifecycle_raw_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
) -> tuple[dict[str, object], list[str]]:
    failures: list[str] = []
    facts: dict[str, object] = {}
    try:
        before_raw = exact_file_bytes(evidence, "boot-id-before.txt")
        after_raw = exact_file_bytes(evidence, "boot-id-after.txt")
    except EvidenceError as error:
        failures.append(f"boot-id readback failed: {error}")
    else:
        for label, raw in (("before", before_raw), ("after", after_raw)):
            try:
                text = raw.decode("ascii")
            except UnicodeDecodeError:
                failures.append(f"boot-id-{label}.txt must be ASCII")
                continue
            value = text.removesuffix("\n") if text.endswith("\n") else ""
            if raw != (value + "\n").encode("ascii") or BOOT_ID_RE.fullmatch(value) is None:
                failures.append(f"boot-id-{label}.txt must be one lowercase UUID line")
            facts[f"bootId{label.title()}"] = value
        if before_raw == after_raw:
            failures.append("kernel boot_id must change across guest reboot")
    try:
        boot_completed = exact_file_bytes(evidence, "boot-completed-after-reboot.txt")
        if boot_completed != b"1\n":
            failures.append("boot-completed-after-reboot.txt must equal one exact 1 line")
    except EvidenceError as error:
        failures.append(str(error))

    try:
        forced = exact_file_bytes(evidence, "deviceidle-state-forced.txt").decode("utf-8")
        unforced = exact_file_bytes(evidence, "deviceidle-state-unforced.txt").decode("utf-8")
        force_receipt = exact_file_bytes(evidence, "deviceidle-force-idle.txt").lower()
        unforce_receipt = exact_file_bytes(evidence, "deviceidle-unforce.txt")
    except (EvidenceError, UnicodeDecodeError) as error:
        failures.append(f"deviceidle readback failed: {error}")
    else:
        state_pattern = (
            r"(?m)^\s*mState=([A-Z_]+)(?:\s+mLightState=[A-Z_]+)?\s*$"
        )
        forced_states = re.findall(state_pattern, forced)
        unforced_states = re.findall(state_pattern, unforced)
        if forced_states != ["IDLE"]:
            failures.append("forced deviceidle evidence must expose deep mState=IDLE")
        if len(unforced_states) != 1 or unforced_states[0] == "IDLE":
            failures.append("unforced deviceidle evidence must leave deep IDLE")
        if b"forced" not in force_receipt or b"idle" not in force_receipt:
            failures.append("deviceidle force receipt must report forced idle")
        unforce_match = DEVICEIDLE_UNFORCE_RECEIPT_RE.fullmatch(unforce_receipt)
        if unforce_match is None:
            failures.append(
                "deviceidle unforce receipt must be one exact state line followed "
                "by two false force-mode flags"
            )
        else:
            light_state = unforce_match.group(1).decode("ascii")
            deep_state = unforce_match.group(2).decode("ascii")
            if (
                light_state not in DEVICEIDLE_LIGHT_STATES
                or deep_state not in DEVICEIDLE_DEEP_STATES
            ):
                failures.append(
                    "deviceidle unforce receipt must expose recognized light/deep states"
                )

    component = f"{PACKAGE_NAME}/.MainActivity"
    for relative, expected_resumed in (
        ("activity-background-before-doze.txt", False),
        ("activity-after-doze.txt", True),
        ("activity-background-before-kill.txt", False),
    ):
        try:
            text = exact_file_bytes(evidence, relative).decode("utf-8")
        except (EvidenceError, UnicodeDecodeError) as error:
            failures.append(f"{relative} cannot be read: {error}")
            continue
        resumed = any(
            "topResumedActivity=" in line
            and re.search(rf"(?:^|\s){re.escape(component)}(?:\s|$|\}})", line)
            for line in text.splitlines()
        )
        if resumed is not expected_resumed:
            failures.append(f"{relative} resumed-state does not match its lifecycle phase")

    try:
        locales_before = exact_file_bytes(evidence, "app-locales-before.txt")
        locales_after = exact_file_bytes(evidence, "app-locales-after-reboot.txt")
    except EvidenceError as error:
        failures.append(f"app-locale readback failed: {error}")
    else:
        if locales_before != locales_after:
            failures.append("raw Follow-system app-locale bytes must survive reboot")
        expected_locales = (
            f"Locales for {PACKAGE_NAME} for user 0 are []\n".encode("ascii")
        )
        if locales_before != expected_locales or locales_after != expected_locales:
            failures.append(
                "app locale evidence must equal the exact package-bound empty "
                "Follow-system line"
            )

    for relative in ("font-scale-before.txt", "font-scale-after-reboot.txt"):
        try:
            raw = exact_file_bytes(evidence, relative)
        except EvidenceError as error:
            failures.append(str(error))
            continue
        if raw != b"2.0\n":
            failures.append(f"{relative} must equal one exact 2.0 line")

    try:
        package_before = exact_file_bytes(evidence, "package-path-before.txt")
        package_after = exact_file_bytes(evidence, "package-path-after-reboot.txt")
    except EvidenceError as error:
        failures.append(f"package-path readback failed: {error}")
    else:
        if package_before != package_after:
            failures.append("installed package path bytes must remain exact across reboot")
        if re.fullmatch(rb"package:/[^\r\n]{1,4096}/base\.apk\n", package_after) is None:
            failures.append("package path must be one exact installed base APK line")
    return facts, failures


def command_receipt_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
    *,
    expected_serial: object,
    expected_kill_pid: int | None,
) -> list[str]:
    failures: list[str] = []
    specs = (
        (
            "process-kill-receipt.json",
            [
                "run-as",
                PACKAGE_NAME,
                "kill",
                "-9",
                str(expected_kill_pid),
            ],
            0,
        ),
        ("pidof-absence-receipt.json", ["pidof", PACKAGE_NAME], 1),
        ("adb-reboot-receipt.json", ["reboot"], 0),
    )
    for relative, command, exit_code in specs:
        try:
            value = load_canonical_json(
                exact_file_bytes(evidence, relative), label=relative
            )
        except EvidenceError as error:
            failures.append(str(error))
            continue
        failures.extend(
            exact_keys(
                value,
                ("command", "exitCode", "serial", "stderr", "stdout"),
                label=relative,
            )
        )
        if type(value) is not dict:
            continue
        if value.get("command") != command:
            failures.append(f"{relative}.command must equal {command!r}")
        if type(value.get("exitCode")) is not int or value.get("exitCode") != exit_code:
            failures.append(f"{relative}.exitCode must equal integer {exit_code}")
        if value.get("serial") != expected_serial:
            failures.append(f"{relative}.serial must equal the owned serial")
        if value.get("stdout") != "" or value.get("stderr") != "":
            failures.append(f"{relative} must retain empty stdout and stderr")

    try:
        transport = load_canonical_json(
            exact_file_bytes(evidence, "reboot-transport-observations.json"),
            label="reboot-transport-observations.json",
        )
    except EvidenceError as error:
        failures.append(str(error))
        return failures
    if type(transport) is not list or len(transport) != 4:
        failures.append("reboot transport observations must contain exactly four phases")
        return failures
    phases = ("before_reboot", "disconnected", "reconnected", "boot_completed")
    states = ("device", "absent", "device", "1")
    commands = (
        ["get-state"],
        ["get-state"],
        ["get-state"],
        ["getprop", "sys.boot_completed"],
    )
    previous_elapsed = -1
    for index, record in enumerate(transport):
        label = f"reboot-transport-observations.json[{index}]"
        failures.extend(
            exact_keys(
                record,
                (
                    "command",
                    "elapsedMilliseconds",
                    "exitCode",
                    "observedState",
                    "phase",
                    "serial",
                    "stderr",
                    "stdout",
                ),
                label=label,
            )
        )
        if type(record) is not dict:
            continue
        if record.get("phase") != phases[index] or record.get("observedState") != states[index]:
            failures.append(f"{label} phase/state must match the exact reboot order")
        if record.get("command") != commands[index]:
            failures.append(f"{label}.command must match its exact probe")
        if record.get("serial") != expected_serial:
            failures.append(f"{label}.serial must equal the owned serial")
        elapsed = record.get("elapsedMilliseconds")
        if type(elapsed) is not int or elapsed <= previous_elapsed:
            failures.append(f"{label}.elapsedMilliseconds must strictly increase")
        else:
            previous_elapsed = elapsed
        if type(record.get("exitCode")) is not int:
            failures.append(f"{label}.exitCode must be an integer")
        if type(record.get("stdout")) is not str or type(record.get("stderr")) is not str:
            failures.append(f"{label} streams must be strings")
        if index in (0, 2):
            if record.get("exitCode") != 0 or record.get("stdout") != "device\n" or record.get("stderr") != "":
                failures.append(f"{label} must be an exact connected device probe")
        elif index == 1:
            if record.get("exitCode") == 0 and record.get("stdout") == "device\n" and record.get("stderr") == "":
                failures.append(f"{label} must prove transport absence")
        else:
            if record.get("exitCode") != 0 or record.get("stdout") != "1\n" or record.get("stderr") != "":
                failures.append(f"{label} must prove exact boot completion")
    return failures


def owned_emulator_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
    *,
    expected_serial: object,
    expected_port: object,
) -> list[str]:
    failures: list[str] = []
    values: list[dict[str, object]] = []
    keys = ("commandSha256", "pid", "port", "processStartedAt", "serial")
    for relative in (
        "owned-emulator-before-reboot.json",
        "owned-emulator-after-reboot.json",
    ):
        try:
            value = load_canonical_json(
                exact_file_bytes(evidence, relative), label=relative
            )
        except EvidenceError as error:
            failures.append(str(error))
            continue
        failures.extend(exact_keys(value, keys, label=relative))
        if type(value) is not dict:
            continue
        if not valid_sha256(value.get("commandSha256")):
            failures.append(f"{relative}.commandSha256 must be SHA-256")
        pid = value.get("pid")
        port = value.get("port")
        if type(pid) is not int or pid <= 0:
            failures.append(f"{relative}.pid must be positive")
        if type(port) is not int or not (5554 <= port <= 5584) or port % 2:
            failures.append(f"{relative}.port must be an even emulator port")
        if type(port) is int and value.get("serial") != f"emulator-{port}":
            failures.append(f"{relative}.serial must derive from port")
        if value.get("serial") != expected_serial or value.get("port") != expected_port:
            failures.append(f"{relative} must bind the owned run serial and port")
        started = value.get("processStartedAt")
        if type(started) is not str or not started.strip() or "\n" in started:
            failures.append(f"{relative}.processStartedAt must be one nonempty line")
        values.append(value)
    if len(values) == 2 and values[0] != values[1]:
        failures.append("owned QEMU host identity must remain exact across guest reboot")
    return failures


def captured_ui_root(
    evidence: Mapping[str, CapturedEvidenceFile], relative: str
) -> tuple[ET.Element | None, list[str]]:
    try:
        raw = exact_file_bytes(evidence, relative)
    except EvidenceError as error:
        return None, [f"{relative} cannot be read: {error}"]
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return None, [f"{relative} must not contain a DTD or entity declaration"]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        return None, [f"{relative} is not valid UI XML: {error}"]
    if not any(True for _ in root.iter("node")):
        return None, [f"{relative} must contain UI nodes"]
    return root, []


def captured_ui_nodes(
    evidence: Mapping[str, CapturedEvidenceFile], relative: str
) -> tuple[list[dict[str, str]], list[str]]:
    root, failures = captured_ui_root(evidence, relative)
    if root is None:
        return [], failures
    return [dict(node.attrib) for node in root.iter("node")], []


def captured_fully_visible_bounds(
    node: ET.Element,
    parents: Mapping[ET.Element, ET.Element],
    *,
    require_scrollable_ancestor: bool,
) -> tuple[int, int, int, int] | None:
    bounds = v1.parsed_ui_bounds(node.attrib.get("bounds", ""))
    if bounds is None or not (
        0 <= bounds[0] < bounds[2] <= 1080
        and 0 <= bounds[1] < bounds[3] <= 2400
    ):
        return None
    scrollable_observed = False
    current = parents.get(node)
    while current is not None:
        if current.attrib.get("scrollable") == "true":
            scrollable_observed = True
            viewport = v1.parsed_ui_bounds(current.attrib.get("bounds", ""))
            if viewport is None or not (
                viewport[0] <= bounds[0]
                and viewport[1] <= bounds[1]
                and bounds[2] <= viewport[2]
                and bounds[3] <= viewport[3]
            ):
                return None
        current = parents.get(current)
    if require_scrollable_ancestor and not scrollable_observed:
        return None
    return bounds


def captured_checked_token_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
    *,
    relative: str,
    text: str,
) -> list[str]:
    root, failures = captured_ui_root(evidence, relative)
    if root is None:
        return failures
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter("node"):
        if node.attrib.get("package") != PACKAGE_NAME or node.attrib.get("text") != text:
            continue
        current: ET.Element | None = node
        while current is not None and current.attrib.get("checkable") != "true":
            current = parents.get(current)
        if current is None:
            continue
        if (
            current.attrib.get("package") == PACKAGE_NAME
            and current.attrib.get("enabled") == "true"
            and current.attrib.get("checked") == "true"
            and captured_fully_visible_bounds(
                current,
                parents,
                require_scrollable_ancestor=True,
            )
            is not None
        ):
            return []
    return [f"{relative} must expose fully visible enabled checked {text!r}"]


def captured_permission_denial_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
    *,
    relative: str,
) -> list[str]:
    root, failures = captured_ui_root(evidence, relative)
    if root is None:
        return failures
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter("node"):
        if node.attrib.get("package") not in PERMISSION_CONTROLLER_PACKAGES or not (
            node.attrib.get("resource-id", "").endswith("permission_deny_button")
            or node.attrib.get("text") in ("Don't allow", "Don’t allow")
        ):
            continue
        current: ET.Element | None = node
        while current is not None and current.attrib.get("clickable") != "true":
            current = parents.get(current)
        if current is None:
            continue
        if (
            current.attrib.get("package") in PERMISSION_CONTROLLER_PACKAGES
            and current.attrib.get("enabled") == "true"
            and captured_fully_visible_bounds(
                current,
                parents,
                require_scrollable_ancestor=False,
            )
            is not None
        ):
            return []
    return [
        f"{relative} must expose one fully visible enabled permission-controller denial action"
    ]


def ui_failures(evidence: Mapping[str, CapturedEvidenceFile]) -> list[str]:
    failures: list[str] = []
    pairing = (
        "ui/setup-first-launch.xml",
        "ui/background-before-doze.xml",
        "ui/background-after-doze.xml",
        "ui/after-process-kill.xml",
        "ui/after-reboot.xml",
        "ui/future-data-first-launch.xml",
        "ui/future-data-second-launch.xml",
        "ui/legacy-migration-first-launch.xml",
        "ui/legacy-migration-second-launch.xml",
    )
    for relative in pairing:
        nodes, node_failures = captured_ui_nodes(evidence, relative)
        failures.extend(node_failures)
        failures.extend(
            v1.ui_token_failures(
                nodes,
                relative=relative,
                package=PACKAGE_NAME,
                text="Pair AetherLink",
            )
        )
    for relative in (
        "ui/future-data-first-launch.xml",
        "ui/future-data-second-launch.xml",
    ):
        nodes, node_failures = captured_ui_nodes(evidence, relative)
        failures.extend(node_failures)
        failures.extend(
            v1.ui_token_failures(
                nodes,
                relative=relative,
                package=PACKAGE_NAME,
                text=FUTURE_DATA_UPDATE_REQUIRED_TEXT,
            )
        )
    for relative in (
        "ui/legacy-migration-first-launch.xml",
        "ui/legacy-migration-second-launch.xml",
    ):
        nodes, node_failures = captured_ui_nodes(evidence, relative)
        failures.extend(node_failures)
        if any(
            node.get("package") == PACKAGE_NAME
            and node.get("text") == FUTURE_DATA_UPDATE_REQUIRED_TEXT
            for node in nodes
        ):
            failures.append(f"{relative} must not expose update-required copy")
    for relative in (
        "ui/follow-system-before-reboot-drawer.xml",
        "ui/follow-system-after-reboot-drawer.xml",
    ):
        nodes, node_failures = captured_ui_nodes(evidence, relative)
        failures.extend(node_failures)
        failures.extend(
            v1.ui_token_failures(
                nodes,
                relative=relative,
                package=PACKAGE_NAME,
                text="Settings",
            )
        )
    for relative in (
        "ui/follow-system-before-reboot.xml",
        "ui/follow-system-after-reboot.xml",
    ):
        nodes, node_failures = captured_ui_nodes(evidence, relative)
        failures.extend(node_failures)
        failures.extend(
            v1.ui_token_failures(
                nodes,
                relative=relative,
                package=PACKAGE_NAME,
                text="Pair AetherLink",
            )
        )
        failures.extend(
            captured_checked_token_failures(
                evidence,
                relative=relative,
                text="Follow system language",
            )
        )
    for relative in (
        "ui/setup-camera-settings-recovery.xml",
        "ui/after-reboot-camera-settings-recovery.xml",
    ):
        nodes, node_failures = captured_ui_nodes(evidence, relative)
        failures.extend(node_failures)
        for text in ("Camera permission is blocked", "Open app settings"):
            failures.extend(
                v1.ui_token_failures(
                    nodes,
                    relative=relative,
                    package=PACKAGE_NAME,
                    text=text,
                )
            )
        if any(node.get("package") in PERMISSION_CONTROLLER_PACKAGES for node in nodes):
            failures.append(f"{relative} must not contain a permission-controller dialog")
    denied_nodes, denied_failures = captured_ui_nodes(
        evidence,
        "ui/setup-camera-denied.xml",
    )
    failures.extend(denied_failures)
    failures.extend(
        v1.ui_token_failures(
            denied_nodes,
            relative="ui/setup-camera-denied.xml",
            package=PACKAGE_NAME,
            text="Camera access is needed",
        )
    )
    dialog_nodes, dialog_failures = captured_ui_nodes(
        evidence,
        "ui/setup-camera-permission-dialog.xml",
    )
    failures.extend(dialog_failures)
    failures.extend(
        v1.ui_token_failures(
            dialog_nodes,
            relative="ui/setup-camera-permission-dialog.xml",
            package=PERMISSION_CONTROLLER_PACKAGES,
            text_contains="AetherLink",
        )
    )
    failures.extend(
        captured_permission_denial_failures(
            evidence,
            relative="ui/setup-camera-permission-dialog.xml",
        )
    )
    return failures


def scenario_failures(
    payload: dict[str, object],
    *,
    observed_processes: dict[str, tuple[str, int, int]],
    preference_sha: str | None,
    lifecycle_facts: dict[str, object],
    future_data_facts: dict[str, object],
    legacy_data_facts: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    scenarios = payload.get("scenarios")
    if type(scenarios) is not list:
        return ["scenarios must be an array"]
    if [item.get("name") if type(item) is dict else None for item in scenarios] != [
        name for name, _ in SCENARIO_CHECKS
    ]:
        failures.append("scenarios must match the exact v2 names and order")
    by_name: dict[str, dict[str, object]] = {}
    for index, (name, checks) in enumerate(SCENARIO_CHECKS):
        if index >= len(scenarios) or type(scenarios[index]) is not dict:
            continue
        item = scenarios[index]
        by_name[name] = item
        failures.extend(
            exact_keys(
                item,
                ("checks", "evidence", "name", "observations", "status"),
                label=f"scenario {name}",
            )
        )
        if item.get("status") != "passed":
            failures.append(f"scenario {name} status must be passed")
        if item.get("evidence") != SCENARIO_EVIDENCE[name]:
            failures.append(f"scenario {name} evidence must match the exact tuple")
        observed_checks = item.get("checks")
        if (
            type(observed_checks) is not dict
            or set(observed_checks) != set(checks)
            or any(value is not True for value in observed_checks.values())
        ):
            failures.append(f"scenario {name} checks must be the exact all-true contract")

    def observations(name: str) -> dict[str, object]:
        item = by_name.get(name, {})
        value = item.get("observations")
        return value if type(value) is dict else {}

    before_doze = observed_processes.get("before_doze")
    after_doze = observed_processes.get("after_doze")
    background = observations("background_doze_recovery")
    failures.extend(
        exact_keys(
            background,
            ("bootId", "cameraRequestStateSha256", "processIds"),
            label="background_doze_recovery observations",
        )
    )
    if before_doze is None or after_doze is None or before_doze != after_doze:
        failures.append("Doze before/after must retain one raw process identity")
    else:
        if before_doze[0] != lifecycle_facts.get("bootIdBefore"):
            failures.append("Doze process identity must bind the raw pre-reboot boot ID")
        if background.get("bootId") != before_doze[0]:
            failures.append("Doze observation bootId must bind raw process evidence")
        if background.get("processIds") != [before_doze[1], after_doze[1]]:
            failures.append("Doze processIds must bind raw before/after PIDs")
    if background.get("cameraRequestStateSha256") != preference_sha:
        failures.append("Doze camera request-state SHA must bind retained preferences")

    before_kill = observed_processes.get("before_kill")
    after_kill = observed_processes.get("after_kill")
    killed = observations("background_process_kill_recovery")
    failures.extend(
        exact_keys(
            killed,
            ("bootId", "cameraRequestStateSha256", "processIds"),
            label="background_process_kill_recovery observations",
        )
    )
    if before_kill is None or after_kill is None or before_kill == after_kill:
        failures.append("process-kill before/after must use distinct raw identities")
    elif before_kill[0] != after_kill[0]:
        failures.append("process-kill recovery must remain in one kernel boot")
    else:
        if before_kill[0] != lifecycle_facts.get("bootIdBefore"):
            failures.append(
                "process-kill process identities must bind the raw pre-reboot boot ID"
            )
        if killed.get("bootId") != before_kill[0]:
            failures.append("process-kill bootId must bind raw process evidence")
        if killed.get("processIds") != [before_kill[1], after_kill[1]]:
            failures.append("process-kill processIds must bind raw evidence")
    if killed.get("cameraRequestStateSha256") != preference_sha:
        failures.append("process-kill camera request-state SHA must bind preferences")

    before_reboot = observed_processes.get("before_reboot")
    after_reboot = observed_processes.get("after_reboot")
    rebooted = observations("full_emulator_reboot_durable_state_recovery")
    reboot_keys = (
        "bootIds",
        "cameraPermissionGranted",
        "cameraRequestStateSha256",
        "fontScale",
        "installedApkSha256",
        "localeTags",
        "processIdAfterReboot",
    )
    failures.extend(
        exact_keys(
            rebooted,
            reboot_keys,
            label="full_emulator_reboot_durable_state_recovery observations",
        )
    )
    boot_ids = [lifecycle_facts.get("bootIdBefore"), lifecycle_facts.get("bootIdAfter")]
    if rebooted.get("bootIds") != boot_ids:
        failures.append("reboot bootIds must bind the two raw kernel boot IDs")
    if before_reboot is None or after_reboot is None:
        failures.append("reboot process observations are incomplete")
    else:
        if before_reboot[0] != boot_ids[0] or after_reboot[0] != boot_ids[1]:
            failures.append("reboot raw process identities must bind their kernel boot IDs")
        if rebooted.get("processIdAfterReboot") != after_reboot[1]:
            failures.append("post-reboot processId must bind raw process evidence")
    artifact = payload.get("artifact") if type(payload.get("artifact")) is dict else {}
    installed_after = artifact.get("installedAfterReboot") if type(artifact.get("installedAfterReboot")) is dict else {}
    expected_reboot = {
        "cameraPermissionGranted": False,
        "cameraRequestStateSha256": preference_sha,
        "fontScale": "2.0",
        "installedApkSha256": installed_after.get("sha256"),
        "localeTags": [],
    }
    for key, expected in expected_reboot.items():
        if rebooted.get(key) != expected:
            failures.append(f"reboot observations.{key} must equal {expected!r}")

    future = observations(
        "future_local_data_update_required_cold_launch_preservation"
    )
    future_keys = (
        "coldLaunchCount",
        "localDataVersion",
        "processIds",
        "savedDataSha256",
        "savedDataSize",
        "updateRequiredText",
    )
    failures.extend(
        exact_keys(
            future,
            future_keys,
            label=(
                "future_local_data_update_required_cold_launch_preservation "
                "observations"
            ),
        )
    )
    future_first = observed_processes.get("future_data_first_launch")
    future_second = observed_processes.get("future_data_second_launch")
    if future_first is None or future_second is None:
        failures.append("future-data cold-launch process observations are incomplete")
    else:
        if future_first == future_second:
            failures.append("future-data cold launches must use distinct raw identities")
        expected_boot_id = lifecycle_facts.get("bootIdAfter")
        if future_first[0] != expected_boot_id or future_second[0] != expected_boot_id:
            failures.append("future-data cold launches must bind the post-reboot boot ID")
        if future.get("processIds") != [future_first[1], future_second[1]]:
            failures.append("future-data processIds must bind raw process evidence")
    if type(future.get("coldLaunchCount")) is not int or future.get("coldLaunchCount") != 2:
        failures.append("future-data coldLaunchCount must equal integer 2")
    if (
        type(future.get("localDataVersion")) is not int
        or future.get("localDataVersion") != future_data_facts.get("version")
    ):
        failures.append("future-data localDataVersion must equal integer 2")
    if future.get("savedDataSha256") != future_data_facts.get("sha256"):
        failures.append("future-data savedDataSha256 must bind the exact seed bytes")
    if (
        type(future.get("savedDataSize")) is not int
        or future.get("savedDataSize") != future_data_facts.get("size")
    ):
        failures.append("future-data savedDataSize must bind the exact seed bytes")
    if future.get("updateRequiredText") != FUTURE_DATA_UPDATE_REQUIRED_TEXT:
        failures.append("future-data updateRequiredText must match the exact English copy")

    legacy = observations(
        "legacy_versionless_local_data_migration_cold_launch_stability"
    )
    legacy_keys = (
        "coldLaunchCount",
        "migratedDataSha256",
        "migratedDataSize",
        "migratedVersion",
        "preservedAppTheme",
        "preservedComposerDraft",
        "preservedTrustedRuntimeAutoReconnectEnabled",
        "processIds",
        "sourceFormat",
    )
    failures.extend(
        exact_keys(
            legacy,
            legacy_keys,
            label=(
                "legacy_versionless_local_data_migration_cold_launch_stability "
                "observations"
            ),
        )
    )
    legacy_first = observed_processes.get("legacy_migration_first_launch")
    legacy_second = observed_processes.get("legacy_migration_second_launch")
    if legacy_first is None or legacy_second is None:
        failures.append("legacy-migration cold-launch process observations are incomplete")
    else:
        if legacy_first == legacy_second:
            failures.append(
                "legacy-migration cold launches must use distinct raw identities"
            )
        expected_boot_id = lifecycle_facts.get("bootIdAfter")
        if legacy_first[0] != expected_boot_id or legacy_second[0] != expected_boot_id:
            failures.append(
                "legacy-migration cold launches must bind the post-reboot boot ID"
            )
        if legacy.get("processIds") != [legacy_first[1], legacy_second[1]]:
            failures.append(
                "legacy-migration processIds must bind raw process evidence"
            )
    if (
        type(legacy.get("coldLaunchCount")) is not int
        or legacy.get("coldLaunchCount") != 2
    ):
        failures.append("legacy-migration coldLaunchCount must equal integer 2")
    if (
        type(legacy.get("migratedVersion")) is not int
        or legacy.get("migratedVersion") != legacy_data_facts.get("version")
        or legacy.get("migratedVersion") != 1
    ):
        failures.append("legacy-migration migratedVersion must equal integer 1")
    if legacy.get("migratedDataSha256") != legacy_data_facts.get("sha256"):
        failures.append(
            "legacy-migration migratedDataSha256 must bind the migrated bytes"
        )
    if (
        type(legacy.get("migratedDataSize")) is not int
        or legacy.get("migratedDataSize") != legacy_data_facts.get("size")
    ):
        failures.append(
            "legacy-migration migratedDataSize must bind the migrated bytes"
        )
    if legacy.get("preservedAppTheme") != legacy_data_facts.get("appTheme"):
        failures.append("legacy-migration must preserve appTheme")
    if legacy.get("preservedComposerDraft") != legacy_data_facts.get("composerDraft"):
        failures.append("legacy-migration must preserve composerDraft")
    if (
        legacy.get("preservedTrustedRuntimeAutoReconnectEnabled") is not False
        or legacy.get("preservedTrustedRuntimeAutoReconnectEnabled")
        != legacy_data_facts.get("trustedRuntimeAutoReconnectEnabled")
    ):
        failures.append(
            "legacy-migration must preserve trustedRuntimeAutoReconnectEnabled=false"
        )
    if legacy.get("sourceFormat") != "versionless":
        failures.append("legacy-migration sourceFormat must equal versionless")
    return failures


def payload_failures(
    payload: object,
    *,
    result_directory: Path,
    evidence: Mapping[str, CapturedEvidenceFile],
    root: Path = ROOT,
    sdk_root: Path,
    java_home: Path | None = None,
) -> list[str]:
    java_home = (java_home or default_java_home()).resolve()
    top_keys = (
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
    )
    failures = exact_keys(payload, top_keys, label="result")
    if failures or type(payload) is not dict:
        return failures
    if payload.get("contract") != CONTRACT:
        failures.append(f"contract must equal {CONTRACT!r}")
    if type(payload.get("schemaVersion")) is not int or payload.get("schemaVersion") != SCHEMA_VERSION:
        failures.append(f"schemaVersion must equal integer {SCHEMA_VERSION}")
    if payload.get("status") != "passed":
        failures.append("status must equal passed")

    run = payload.get("run")
    run_keys = (
        "durationSeconds",
        "emulatorPort",
        "finishedAt",
        "hostArchitecture",
        "hostPlatform",
        "id",
        "serial",
        "startedAt",
    )
    failures.extend(exact_keys(run, run_keys, label="run"))
    if type(run) is dict:
        if type(run.get("id")) is not str or RUN_ID_RE.fullmatch(run["id"]) is None:
            failures.append("run.id must use the exact v2 run-id format")
        if run.get("id") != result_directory.name:
            failures.append("run.id must equal the result directory basename")
        port = run.get("emulatorPort")
        if type(port) is not int or not (5554 <= port <= 5584) or port % 2:
            failures.append("run.emulatorPort must be an even emulator port")
        if type(port) is int and run.get("serial") != f"emulator-{port}":
            failures.append("run.serial must derive from the emulator port")
        if run.get("hostPlatform") != "darwin" or run.get("hostArchitecture") != "arm64":
            failures.append("run host must be darwin/arm64")
        duration = run.get("durationSeconds")
        if type(duration) not in (int, float) or duration <= 0:
            failures.append("run.durationSeconds must be a positive exact number")
        try:
            started = parse_utc(run.get("startedAt"), label="run.startedAt")
            finished = parse_utc(run.get("finishedAt"), label="run.finishedAt")
            observed = (finished - started).total_seconds()
            if observed <= 0 or type(duration) not in (int, float) or abs(observed - duration) > 1:
                failures.append("run duration must match its timestamp interval")
        except EvidenceError as error:
            failures.append(str(error))

    try:
        expected_source = source_snapshot(root)
    except EvidenceError as error:
        failures.append(f"current source snapshot failed: {error}")
    else:
        if payload.get("source") != expected_source:
            failures.append("source must exactly match the current v2 source snapshot")

    build = payload.get("build")
    failures.extend(exact_keys(build, ("command", "dependencyMode", "exitCode"), label="build"))
    if type(build) is dict:
        if build.get("command") != list(v1.BUILD_COMMAND):
            failures.append("build.command must match the offline Debug build")
        if build.get("dependencyMode") != "offline":
            failures.append("build.dependencyMode must equal offline")
        if type(build.get("exitCode")) is not int or build.get("exitCode") != 0:
            failures.append("build.exitCode must equal integer zero")

    artifact = payload.get("artifact")
    artifact_keys = ("built", "exactByteMatch", "installedAfterReboot", "installedBefore")
    failures.extend(exact_keys(artifact, artifact_keys, label="artifact"))
    if type(artifact) is dict:
        try:
            expected_built = file_record(
                root / v1.DEBUG_APK_RELATIVE,
                relative=v1.DEBUG_APK_RELATIVE.as_posix(),
            )
            expected_before = evidence["installed-base-before.apk"].record(
                "installed-base-before.apk"
            )
            expected_after = evidence["installed-base-after-reboot.apk"].record(
                "installed-base-after-reboot.apk"
            )
        except (EvidenceError, KeyError) as error:
            failures.append(f"artifact readback failed: {error}")
        else:
            if artifact.get("built") != expected_built:
                failures.append("artifact.built must bind the current Debug APK")
            if artifact.get("installedBefore") != expected_before:
                failures.append("artifact.installedBefore must bind retained bytes")
            if artifact.get("installedAfterReboot") != expected_after:
                failures.append("artifact.installedAfterReboot must bind retained bytes")
            identities = {
                (record["size"], record["sha256"])
                for record in (expected_built, expected_before, expected_after)
            }
            if len(identities) != 1 or artifact.get("exactByteMatch") is not True:
                failures.append("built/before/after APK bytes must match exactly")

    device = payload.get("device")
    device_keys = (
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
    )
    failures.extend(exact_keys(device, device_keys, label="device"))
    if type(device) is dict:
        expected_device = {
            "abi": "arm64-v8a",
            "activity": v1.ACTIVITY_NAME,
            "apiLevel": 36,
            "appNetworkingDenied": True,
            "avdEphemeral": True,
            "guestAirplaneModeEnabled": True,
            "launchFlags": list(v1.LAUNCH_FLAGS),
            "package": PACKAGE_NAME,
            "release": "16",
            "screenDensity": 420,
            "screenHeight": 2400,
            "screenWidth": 1080,
            "systemImagePackage": v1.SYSTEM_IMAGE_PACKAGE,
        }
        for key, expected in expected_device.items():
            if device.get(key) != expected:
                failures.append(f"device.{key} must equal {expected!r}")
        if type(device.get("model")) is not str or not device["model"].strip():
            failures.append("device.model must be nonempty")

    toolchain = payload.get("toolchain")
    toolchain_keys = (
        "adb",
        "adbVersion",
        "emulator",
        "emulatorVersion",
        "java",
        "javaHome",
        "javaVersion",
        "qemuHeadless",
        "systemImage",
    )
    failures.extend(exact_keys(toolchain, toolchain_keys, label="toolchain"))
    if type(toolchain) is dict:
        try:
            expected_tools = {
                "adb": sdk_tool_identity(sdk_root, Path("platform-tools/adb")),
                "emulator": sdk_tool_identity(sdk_root, Path("emulator/emulator")),
                "java": java_tool_identity(java_home),
                "qemuHeadless": sdk_tool_identity(
                    sdk_root,
                    Path("emulator/qemu/darwin-aarch64/qemu-system-aarch64-headless"),
                ),
                "systemImage": system_image_snapshot(sdk_root),
            }
        except EvidenceError as error:
            failures.append(f"toolchain readback failed: {error}")
        else:
            for key, expected in expected_tools.items():
                if toolchain.get(key) != expected:
                    failures.append(f"toolchain.{key} must match current bytes")
        if toolchain.get("javaHome") != str(java_home):
            failures.append("toolchain.javaHome must equal the selected Java home")
        for key in ("adbVersion", "emulatorVersion", "javaVersion"):
            if type(toolchain.get(key)) is not str or not toolchain[key].strip():
                failures.append(f"toolchain.{key} must be nonempty")

    try:
        expected_evidence = evidence_manifest_from_snapshot(evidence)
    except EvidenceError as error:
        failures.append(f"evidence readback failed: {error}")
    else:
        if payload.get("evidence") != expected_evidence:
            failures.append("evidence must exactly bind every v2 evidence file")

    expected_serial = run.get("serial") if type(run) is dict else None
    observed_processes, process_failures = process_observation_failures(
        evidence,
        expected_serial=expected_serial,
    )
    failures.extend(process_failures)
    preference_sha, camera_failures = camera_state_failures(evidence)
    failures.extend(camera_failures)
    future_data_facts, future_data_failures = future_runtime_local_data_failures(
        evidence
    )
    failures.extend(future_data_failures)
    legacy_data_facts, legacy_data_failures = legacy_runtime_local_data_failures(
        evidence
    )
    failures.extend(legacy_data_failures)
    lifecycle_facts, raw_failures = lifecycle_raw_failures(evidence)
    failures.extend(raw_failures)
    before_kill_identity = observed_processes.get("before_kill")
    failures.extend(
        command_receipt_failures(
            evidence,
            expected_serial=expected_serial,
            expected_kill_pid=(
                before_kill_identity[1]
                if before_kill_identity is not None
                else None
            ),
        )
    )
    failures.extend(
        owned_emulator_failures(
            evidence,
            expected_serial=expected_serial,
            expected_port=run.get("emulatorPort") if type(run) is dict else None,
        )
    )
    failures.extend(ui_failures(evidence))
    failures.extend(
        scenario_failures(
            payload,
            observed_processes=observed_processes,
            preference_sha=preference_sha,
            lifecycle_facts=lifecycle_facts,
            future_data_facts=future_data_facts,
            legacy_data_facts=legacy_data_facts,
        )
    )

    failures.extend(network_failures(payload, evidence))
    failures.extend(log_and_exit_failures(payload, evidence))
    failures.extend(cleanup_failures(payload, evidence))
    failures.extend(avd_launch_failures(payload, evidence, sdk_root=sdk_root))

    if payload.get("nonClaims") != list(NON_CLAIMS):
        failures.append("nonClaims must match the exact v2 bounded list")
    return failures


def network_failures(
    payload: dict[str, object],
    evidence: Mapping[str, CapturedEvidenceFile],
) -> list[str]:
    failures: list[str] = []
    network = payload.get("networkIsolation")
    keys = (
        "afterReboot",
        "appNetworkingAfterReboot",
        "appNetworkingBefore",
        "before",
        "guestAirplaneModeAfterReboot",
        "guestAirplaneModeBefore",
    )
    failures.extend(exact_keys(network, keys, label="networkIsolation"))
    if type(network) is not dict:
        return failures
    for key, relative in (
        ("before", "network-state-before.txt"),
        ("afterReboot", "network-state-after-reboot.txt"),
    ):
        record = network.get(key)
        failures.extend(
            exact_keys(record, ("lineCount", "sha256", "validatedInternetMatches"), label=f"networkIsolation.{key}")
        )
        try:
            raw = exact_file_bytes(evidence, relative)
        except EvidenceError as error:
            failures.append(str(error))
            continue
        matches = v1.validated_network_lines(raw.decode("utf-8", "replace"))
        if matches:
            failures.append(f"{relative} contains a validated Internet network")
        if type(record) is dict:
            if type(record.get("lineCount")) is not int or record.get("lineCount") != len(raw.splitlines()):
                failures.append(f"networkIsolation.{key}.lineCount must bind raw bytes")
            if record.get("sha256") != hashlib.sha256(raw).hexdigest():
                failures.append(f"networkIsolation.{key}.sha256 must bind raw bytes")
            if record.get("validatedInternetMatches") != matches:
                failures.append(f"networkIsolation.{key} matches must be independently parsed")
    for key, relative, expected in (
        ("appNetworkingBefore", "app-networking-before.txt", v1.APP_NETWORKING_DENIED_STATE),
        ("appNetworkingAfterReboot", "app-networking-after-reboot.txt", v1.APP_NETWORKING_DENIED_STATE),
        ("guestAirplaneModeBefore", "guest-airplane-before.txt", "enabled"),
        ("guestAirplaneModeAfterReboot", "guest-airplane-after-reboot.txt", "enabled"),
    ):
        record = network.get(key)
        failures.extend(exact_keys(record, ("lineCount", "sha256", "value"), label=f"networkIsolation.{key}"))
        try:
            raw = exact_file_bytes(evidence, relative)
        except EvidenceError as error:
            failures.append(str(error))
            continue
        if raw != (expected + "\n").encode("ascii"):
            failures.append(f"{relative} must equal one exact {expected!r} line")
        if type(record) is dict:
            if type(record.get("lineCount")) is not int or record.get("lineCount") != 1:
                failures.append(f"networkIsolation.{key}.lineCount must equal integer one")
            if record.get("sha256") != hashlib.sha256(raw).hexdigest():
                failures.append(f"networkIsolation.{key}.sha256 must bind raw bytes")
            if record.get("value") != expected:
                failures.append(f"networkIsolation.{key}.value must equal {expected!r}")
    return failures


def log_and_exit_failures(
    payload: dict[str, object],
    evidence: Mapping[str, CapturedEvidenceFile],
) -> list[str]:
    failures: list[str] = []
    for top_key, phases, file_prefix, match_key, parser in (
        (
            "logcat",
            ("beforeReboot", "afterReboot"),
            "logcat",
            "fatalOrAnrMatches",
            v1.app_logcat_failure_lines,
        ),
        (
            "exitInfo",
            ("beforeReboot", "afterReboot"),
            "exit-info",
            "forbiddenMatches",
            v1.app_exit_failure_lines,
        ),
    ):
        value = payload.get(top_key)
        failures.extend(exact_keys(value, phases, label=top_key))
        if type(value) is not dict:
            continue
        for phase in phases:
            record = value.get(phase)
            failures.extend(exact_keys(record, (match_key, "lineCount", "sha256"), label=f"{top_key}.{phase}"))
            suffix = "before-reboot" if phase == "beforeReboot" else "after-reboot"
            try:
                raw = exact_file_bytes(evidence, f"{file_prefix}-{suffix}.txt")
            except EvidenceError as error:
                failures.append(str(error))
                continue
            direct = parser(raw.decode("utf-8", "replace"))
            if direct:
                failures.append(f"{file_prefix}-{suffix}.txt contains forbidden app failure evidence")
            if type(record) is dict:
                if record.get(match_key) != []:
                    failures.append(f"{top_key}.{phase}.{match_key} must be empty")
                if type(record.get("lineCount")) is not int or record.get("lineCount") != len(raw.splitlines()) or record["lineCount"] < 1:
                    failures.append(f"{top_key}.{phase}.lineCount must bind nonempty raw bytes")
                if record.get("sha256") != hashlib.sha256(raw).hexdigest():
                    failures.append(f"{top_key}.{phase}.sha256 must bind raw bytes")
    return failures


def cleanup_failures(
    payload: dict[str, object],
    evidence: Mapping[str, CapturedEvidenceFile],
) -> list[str]:
    failures: list[str] = []
    cleanup = payload.get("cleanup")
    keys = (
        "ownedProcessExited",
        "ownedSerialAbsent",
        "postHostEmulators",
        "postSerials",
        "preexistingHostEmulators",
        "preexistingSerials",
        "preexistingSerialsPreserved",
    )
    failures.extend(exact_keys(cleanup, keys, label="cleanup"))
    run = payload.get("run")
    if type(cleanup) is not dict or type(run) is not dict:
        return failures
    try:
        pre_devices = exact_file_bytes(evidence, "pre-adb-devices.txt").decode("utf-8")
        post_devices = exact_file_bytes(evidence, "post-adb-devices.txt").decode("utf-8")
        pre_host_raw = exact_file_bytes(evidence, "pre-emulator-processes.json")
        post_host_raw = exact_file_bytes(evidence, "post-emulator-processes.json")
    except (EvidenceError, UnicodeDecodeError) as error:
        failures.append(f"cleanup evidence readback failed: {error}")
        return failures
    pre_serials = v1.adb_serials_from_text(pre_devices)
    post_serials = v1.adb_serials_from_text(post_devices)
    pre_host, pre_failures = v1.host_emulator_inventory_failures(pre_host_raw, label="pre-emulator-processes.json")
    post_host, post_failures = v1.host_emulator_inventory_failures(post_host_raw, label="post-emulator-processes.json")
    failures.extend(pre_failures)
    failures.extend(post_failures)
    if cleanup.get("preexistingSerials") != pre_serials or cleanup.get("postSerials") != post_serials:
        failures.append("cleanup serial claims must bind raw adb inventories")
    if cleanup.get("preexistingHostEmulators") != pre_host or cleanup.get("postHostEmulators") != post_host:
        failures.append("cleanup host claims must bind raw host inventories")
    post_by_serial = {record.get("serial"): record for record in post_host}
    if not set(pre_serials).issubset(post_serials) or any(
        post_by_serial.get(record.get("serial")) != record for record in pre_host
    ):
        failures.append("cleanup must preserve every preexisting emulator identity")
    if run.get("serial") in post_serials or run.get("serial") in post_by_serial:
        failures.append("cleanup still contains the owned emulator")
    for key in (
        "ownedProcessExited",
        "ownedSerialAbsent",
        "preexistingSerialsPreserved",
    ):
        if cleanup.get(key) is not True:
            failures.append(f"cleanup.{key} must be true")
    return failures


def avd_launch_failures(
    payload: dict[str, object],
    evidence: Mapping[str, CapturedEvidenceFile],
    *,
    sdk_root: Path,
) -> list[str]:
    failures: list[str] = []
    run = payload.get("run")
    if type(run) is not dict:
        return failures
    try:
        config = exact_file_bytes(evidence, "avd-config.ini")
        launch = load_canonical_json(
            exact_file_bytes(evidence, "launch-argv.json"),
            label="launch-argv.json",
        )
    except EvidenceError as error:
        return [f"AVD launch readback failed: {error}"]
    if type(launch) is not list or any(type(item) is not str for item in launch) or len(launch) < 5:
        return ["launch-argv.json must be a complete string array"]
    avd_name = launch[2]
    try:
        expected_config = avd_config_bytes(avd_name)
    except EvidenceError as error:
        failures.append(str(error))
        return failures
    if config != expected_config:
        failures.append("avd-config.ini must match the exact ephemeral AVD")
    expected = [
        str(sdk_root / "emulator/emulator"),
        "-avd",
        avd_name,
        "-port",
        str(run.get("emulatorPort")),
        *v1.LAUNCH_FLAGS,
    ]
    if launch != expected:
        failures.append("launch-argv.json must match the exact owned launch")
    if v1.AVD_NAME_RE.fullmatch(avd_name) is None:
        failures.append("launch AVD name must use the reviewed API 36.1 format")
    return failures


def closed_evidence_failures(
    evidence: Mapping[str, CapturedEvidenceFile],
) -> list[str]:
    expected_files = set(EVIDENCE_PATHS) | {"result.json"}
    actual_files = set(evidence)
    if actual_files == expected_files:
        return []
    return [
        "evidence file set must be closed; "
        f"missing={sorted(expected_files - actual_files)!r}, "
        f"unexpected={sorted(actual_files - expected_files)!r}"
    ]


def captured_result_failures(
    snapshot: EvidenceSnapshot,
    evidence: Mapping[str, CapturedEvidenceFile],
    payload: object,
    *,
    root: Path = ROOT,
    sdk_root: Path,
    java_home: Path | None = None,
    verify_live_graph: bool = True,
) -> list[str]:
    """Validate one caller-held result/evidence generation.

    Keeping the snapshot open lets a downstream provenance or archive writer use
    the exact bytes that were semantically checked instead of reopening live
    paths after validation.
    """

    failures = payload_failures(
        payload,
        result_directory=snapshot.result_directory,
        evidence=evidence,
        root=root,
        sdk_root=sdk_root,
        java_home=java_home,
    )
    failures.extend(closed_evidence_failures(evidence))
    if verify_live_graph:
        try:
            snapshot.verify_unchanged()
        except (EvidenceError, OSError) as error:
            failures.append(f"final evidence graph verification failed: {error}")
    return failures


def result_failures(
    result_path: Path,
    *,
    root: Path = ROOT,
    sdk_root: Path,
    java_home: Path | None = None,
) -> list[str]:
    snapshot: EvidenceSnapshot | None = None
    try:
        snapshot = EvidenceSnapshot(result_path)
        evidence = snapshot.capture()
        payload = load_canonical_json(
            exact_file_bytes(evidence, "result.json"), label="result.json"
        )
    except (EvidenceError, OSError) as error:
        if snapshot is not None:
            snapshot.close()
        return [str(error)]
    try:
        return captured_result_failures(
            snapshot,
            evidence,
            payload,
            root=root,
            sdk_root=sdk_root,
            java_home=java_home,
        )
    finally:
        snapshot.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--sdk-root", type=Path, default=(Path.home() / "Library/Android/sdk"))
    parser.add_argument("--java-home", type=Path, default=default_java_home())
    args = parser.parse_args()
    result_path = Path(
        os.path.abspath(os.fspath(args.result.expanduser()))
    )
    failures = result_failures(
        result_path,
        sdk_root=args.sdk_root.expanduser().resolve(),
        java_home=args.java_home.expanduser().resolve(),
    )
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(
        f"Android headless lifecycle v2 readback passed: "
        f"{len(SCENARIO_CHECKS)}/{len(SCENARIO_CHECKS)} scenarios"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
