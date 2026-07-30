#!/usr/bin/env python3
"""Qualify a credential-free local DMG mount/copy/launch rehearsal."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import plistlib
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Protocol, Sequence

if __package__:
    from script import run_macos_clean_home_installed_app_smoke as installed
    from script import run_macos_packaged_app_state_recovery_smoke as recovery
else:
    import run_macos_clean_home_installed_app_smoke as installed
    import run_macos_packaged_app_state_recovery_smoke as recovery


engine = installed.engine
ROOT = Path(__file__).resolve().parents[1]
HDIUTIL = Path("/usr/bin/hdiutil")
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = "same-host-per-user-ephemeral-local-dmg-install-v1"
VOLUME_NAME = "AetherLink Local QA"
DMG_FORMAT = "UDZO"
DMG_FILESYSTEM = "HFS+"
MAXIMUM_COMMAND_OUTPUT_BYTES = 65_536
COMMAND_TIMEOUT_SECONDS = 120.0
UNMOUNT_TIMEOUT_SECONDS = 15.0
APPLICATIONS_LINK_TARGET = "/Applications"
LIMITATIONS = (
    "not-finder-ui-or-drag-and-drop-evidence",
    "not-general-ui-or-accessibility-evidence",
    "not-developer-id-notarized-or-stapled-distribution",
    "not-gatekeeper-quarantine-or-download-evidence",
    "not-clean-machine-account-or-system-applications",
    "not-tcc-keychain-provider-network-or-device-evidence",
    "not-arbitrary-history-crash-power-loss-or-concurrent-writer-evidence",
    "not-backup-restore-or-device-transfer-evidence",
    "not-upgrade-n-or-n-minus-one-rollback-production-or-security-evidence",
)
DEVICE_PATTERN = re.compile(r"/dev/disk[1-9][0-9]*(?:s[1-9][0-9]*)*")


class LocalDMGSmokeError(RuntimeError):
    """A bounded, path-free local DMG QA failure."""


class _OutputOverflow(LocalDMGSmokeError):
    pass


class ProcessLike(Protocol):
    pid: int
    returncode: int | None
    stdout: Any
    stderr: Any

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]: ...

    def kill(self) -> None: ...

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


PopenFactory = Callable[..., ProcessLike]
GroupKiller = Callable[[int, int], None]


@dataclass(frozen=True)
class CommandResult:
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class MountedEntity:
    device: str


def current_release() -> recovery.ReleaseVersion:
    return recovery.current_release()


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return recovery.release_id_for(version)


def default_archive_dir() -> Path:
    return recovery.default_archive_dir()


def default_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-local-dmg-install-v1.json"
        )
    )


def closed_environment() -> dict[str, str]:
    return {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }


def _supports_streaming(process: ProcessLike) -> bool:
    return all(
        stream is not None and callable(getattr(stream, "fileno", None))
        for stream in (process.stdout, process.stderr)
    )


def _collect_output(
    process: ProcessLike,
    timeout_seconds: float,
    monotonic: Callable[[], float],
) -> tuple[bytes, bytes]:
    if not _supports_streaming(process):
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        if len(stdout) + len(stderr) > MAXIMUM_COMMAND_OUTPUT_BYTES:
            raise _OutputOverflow()
        return stdout, stderr

    selector = selectors.DefaultSelector()
    buffers = [bytearray(), bytearray()]
    total = 0
    try:
        selector.register(process.stdout, selectors.EVENT_READ, 0)
        selector.register(process.stderr, selectors.EVENT_READ, 1)
        deadline = monotonic() + timeout_seconds
        while selector.get_map():
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("local DMG command", timeout_seconds)
            for key, _events in selector.select(remaining):
                capacity = MAXIMUM_COMMAND_OUTPUT_BYTES - total
                chunk = os.read(key.fd, min(8_192, capacity + 1))
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                total += len(chunk)
                if total > MAXIMUM_COMMAND_OUTPUT_BYTES:
                    raise _OutputOverflow()
                buffers[key.data].extend(chunk)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("local DMG command", timeout_seconds)
        process.wait(timeout=remaining)
        return bytes(buffers[0]), bytes(buffers[1])
    finally:
        selector.close()


def _discard_stream(stream: Any) -> None:
    if stream is None:
        return
    try:
        stream.close()
    except Exception:
        pass


def _terminate_and_reap(
    process: ProcessLike,
    *,
    group_killer: GroupKiller = os.killpg,
) -> None:
    group_killed = False
    try:
        group_killer(process.pid, signal.SIGKILL)
        group_killed = True
    except Exception:
        pass
    try:
        running = process.poll() is None
    except Exception:
        running = True
    if running and not group_killed:
        try:
            process.kill()
        except Exception:
            pass
    _discard_stream(getattr(process, "stdout", None))
    _discard_stream(getattr(process, "stderr", None))
    try:
        process.wait(timeout=2.0)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=2.0)
        except Exception:
            pass


def run_bounded_command(
    command: Sequence[str],
    *,
    timeout_seconds: float = COMMAND_TIMEOUT_SECONDS,
    popen_factory: PopenFactory = subprocess.Popen,
    group_killer: GroupKiller = os.killpg,
    monotonic: Callable[[], float] = time.monotonic,
) -> CommandResult:
    if (
        not command
        or command[0] != str(HDIUTIL)
        or timeout_seconds <= 0
        or any(not isinstance(item, str) or "\x00" in item for item in command)
    ):
        raise LocalDMGSmokeError("local DMG command contract is invalid")
    if not HDIUTIL.is_file() or not os.access(HDIUTIL, os.X_OK):
        raise LocalDMGSmokeError("local DMG tool is unavailable")

    process: ProcessLike | None = None
    try:
        process = popen_factory(
            list(command),
            cwd=ROOT,
            env=closed_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            start_new_session=True,
        )
        stdout, stderr = _collect_output(process, timeout_seconds, monotonic)
    except (_OutputOverflow, subprocess.TimeoutExpired, OSError) as error:
        if process is not None:
            _terminate_and_reap(process, group_killer=group_killer)
        raise LocalDMGSmokeError("local DMG command did not complete safely") from error
    except BaseException:
        if process is not None:
            _terminate_and_reap(process, group_killer=group_killer)
        raise
    if process.returncode != 0:
        raise LocalDMGSmokeError("local DMG command failed")
    return CommandResult(stdout=stdout, stderr=stderr)


def _absolute_clean_path(path: Path, label: str) -> str:
    rendered = str(path)
    if not path.is_absolute() or "\x00" in rendered:
        raise LocalDMGSmokeError(f"{label} is invalid")
    return rendered


def create_dmg_command(staging_root: Path, dmg_path: Path) -> tuple[str, ...]:
    staging = _absolute_clean_path(staging_root, "staging root")
    image = _absolute_clean_path(dmg_path, "image destination")
    if (
        staging_root.is_symlink()
        or not staging_root.is_dir()
        or dmg_path.exists()
        or dmg_path.is_symlink()
        or not dmg_path.parent.is_dir()
        or dmg_path.parent.is_symlink()
    ):
        raise LocalDMGSmokeError("fresh local DMG inputs are invalid")
    return (
        str(HDIUTIL),
        "create",
        "-srcfolder",
        staging,
        "-volname",
        VOLUME_NAME,
        "-fs",
        DMG_FILESYSTEM,
        "-format",
        DMG_FORMAT,
        image,
    )


def verify_dmg_command(dmg_path: Path) -> tuple[str, ...]:
    image = _absolute_clean_path(dmg_path, "image")
    if dmg_path.is_symlink() or not dmg_path.is_file():
        raise LocalDMGSmokeError("created local DMG is missing")
    return (str(HDIUTIL), "verify", image)


def attach_dmg_command(
    dmg_path: Path,
    mountpoint: Path,
) -> tuple[str, ...]:
    image = _absolute_clean_path(dmg_path, "image")
    mount = _absolute_clean_path(mountpoint, "mount point")
    if (
        dmg_path.is_symlink()
        or not dmg_path.is_file()
        or mountpoint.is_symlink()
        or not mountpoint.is_dir()
        or any(mountpoint.iterdir())
    ):
        raise LocalDMGSmokeError("fresh local DMG mount inputs are invalid")
    return (
        str(HDIUTIL),
        "attach",
        "-readonly",
        "-nobrowse",
        "-noautoopen",
        "-mountpoint",
        mount,
        "-plist",
        image,
    )


def detach_dmg_command(device: str) -> tuple[str, ...]:
    if not isinstance(device, str) or DEVICE_PATTERN.fullmatch(device) is None:
        raise LocalDMGSmokeError("mounted device identity is invalid")
    return (str(HDIUTIL), "detach", device)


def detach_mountpoint_command(mountpoint: Path) -> tuple[str, ...]:
    mount = _absolute_clean_path(mountpoint, "mount point")
    if mountpoint.is_symlink() or not mountpoint.is_dir():
        raise LocalDMGSmokeError("mounted mount point is invalid")
    return (str(HDIUTIL), "detach", mount)


def info_dmg_command() -> tuple[str, ...]:
    return (str(HDIUTIL), "info", "-plist")


def _load_plist(payload: bytes) -> dict[str, object]:
    if not payload or len(payload) > MAXIMUM_COMMAND_OUTPUT_BYTES:
        raise LocalDMGSmokeError("local DMG plist output is invalid")
    try:
        value = plistlib.loads(payload)
    except plistlib.InvalidFileException as error:
        raise LocalDMGSmokeError("local DMG plist output is invalid") from error
    if not isinstance(value, dict):
        raise LocalDMGSmokeError("local DMG plist root is invalid")
    return value


def _mounted_entities(
    rows: object,
    *,
    expected_mountpoint: Path,
    reject_other_mounts: bool = False,
) -> list[MountedEntity]:
    if not isinstance(rows, list) or not rows or len(rows) > 32:
        raise LocalDMGSmokeError("local DMG entity list is invalid")
    expected = str(expected_mountpoint)
    matches: list[MountedEntity] = []
    seen_devices: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or any(
            not isinstance(key, str) for key in row
        ):
            raise LocalDMGSmokeError("local DMG entity is invalid")
        device = row.get("dev-entry")
        mount = row.get("mount-point")
        if device is not None:
            if (
                not isinstance(device, str)
                or DEVICE_PATTERN.fullmatch(device) is None
                or device in seen_devices
            ):
                raise LocalDMGSmokeError("local DMG device identity is invalid")
            seen_devices.add(device)
        if mount is None:
            continue
        if (
            not isinstance(mount, str)
            or "\x00" in mount
            or device is None
        ):
            raise LocalDMGSmokeError("local DMG mounted entity is invalid")
        if mount != expected:
            if reject_other_mounts:
                raise LocalDMGSmokeError(
                    "local DMG attach included another mounted entity"
                )
            continue
        matches.append(MountedEntity(device=device))
    return matches


def parse_attach_plist(
    payload: bytes,
    *,
    expected_mountpoint: Path,
) -> MountedEntity:
    root = _load_plist(payload)
    if set(root) != {"system-entities"}:
        raise LocalDMGSmokeError("local DMG attach plist fields are invalid")
    matches = _mounted_entities(
        root["system-entities"],
        expected_mountpoint=expected_mountpoint,
        reject_other_mounts=True,
    )
    if len(matches) != 1:
        raise LocalDMGSmokeError("local DMG attach result is ambiguous")
    return matches[0]


def parse_info_plist_device(
    payload: bytes,
    *,
    expected_mountpoint: Path,
) -> MountedEntity | None:
    root = _load_plist(payload)
    images = root.get("images")
    if not isinstance(images, list) or len(images) > 128:
        raise LocalDMGSmokeError("local DMG info plist is invalid")
    matches: list[MountedEntity] = []
    for image in images:
        if not isinstance(image, dict):
            raise LocalDMGSmokeError("local DMG info image is invalid")
        rows = image.get("system-entities")
        if rows is None:
            continue
        matches.extend(
            _mounted_entities(
                rows,
                expected_mountpoint=expected_mountpoint,
            )
        )
    if len(matches) > 1:
        raise LocalDMGSmokeError("local DMG mount recovery is ambiguous")
    return matches[0] if matches else None


def stage_dmg_root(
    source_app: Path,
    staging_root: Path,
    *,
    installer: Callable[[Path, Path], None] = installed.install_app_with_ditto,
) -> Path:
    if staging_root.exists() or staging_root.is_symlink():
        raise LocalDMGSmokeError("local DMG staging root is not fresh")
    staged_app = staging_root / installed.APP_RELATIVE_PATH
    installer(source_app, staged_app)
    if staging_root.is_symlink() or not staging_root.is_dir():
        raise LocalDMGSmokeError("local DMG staging root was not created safely")
    staging_root.chmod(0o700)
    applications_link = staging_root / "Applications"
    applications_link.symlink_to(APPLICATIONS_LINK_TARGET)
    if (
        not applications_link.is_symlink()
        or os.readlink(applications_link) != APPLICATIONS_LINK_TARGET
        or set(path.name for path in staging_root.iterdir())
        != {installed.APP_RELATIVE_PATH.name, "Applications"}
    ):
        raise LocalDMGSmokeError("local DMG staging layout is invalid")
    return staged_app


def verify_mounted_layout(mountpoint: Path) -> Path:
    mounted_app = mountpoint / installed.APP_RELATIVE_PATH
    applications_link = mountpoint / "Applications"
    if (
        mountpoint.is_symlink()
        or not mountpoint.is_dir()
        or mounted_app.is_symlink()
        or not mounted_app.is_dir()
        or not applications_link.is_symlink()
        or os.readlink(applications_link) != APPLICATIONS_LINK_TARGET
        or set(path.name for path in mountpoint.iterdir())
        != {installed.APP_RELATIVE_PATH.name, "Applications"}
    ):
        raise LocalDMGSmokeError("mounted local DMG layout is invalid")
    return mounted_app


def wait_for_unmounted(
    mountpoint: Path,
    *,
    timeout_seconds: float = UNMOUNT_TIMEOUT_SECONDS,
    mount_checker: Callable[[Path], bool] = os.path.ismount,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        mounted_payload_present = (
            (mountpoint / installed.APP_RELATIVE_PATH).exists()
            or (mountpoint / installed.APP_RELATIVE_PATH).is_symlink()
            or (mountpoint / "Applications").exists()
            or (mountpoint / "Applications").is_symlink()
        )
        if not mount_checker(mountpoint) and not mounted_payload_present:
            return
        sleeper(min(0.1, max(0.0, deadline - monotonic())))
    raise LocalDMGSmokeError("local DMG did not detach within the bound")


def copy_from_mounted_dmg(
    *,
    mountpoint: Path,
    installed_app: Path,
    release: engine.ReleaseInputs,
    version: recovery.ReleaseVersion,
    expected_tree: installed.AppTreeEvidence,
) -> installed.AppTreeEvidence:
    mounted_app = verify_mounted_layout(mountpoint)
    recovery.verify_packaged_app(mounted_app, release, version=version)
    mounted_tree = installed.app_tree_evidence(mounted_app, release)
    if mounted_tree != expected_tree:
        raise LocalDMGSmokeError("mounted local DMG app differs from release")
    installed.install_app_with_ditto(mounted_app, installed_app)
    recovery.verify_packaged_app(installed_app, release, version=version)
    copied_tree = installed.app_tree_evidence(installed_app, release)
    if copied_tree != mounted_tree:
        raise LocalDMGSmokeError("installed local DMG app differs after copy")
    return copied_tree


def attach_copy_detach(
    *,
    dmg_path: Path,
    mountpoint: Path,
    copier: Callable[[], installed.AppTreeEvidence],
    command_runner: Callable[[Sequence[str]], CommandResult] | None = None,
    unmount_waiter: Callable[[Path], None] | None = None,
) -> installed.AppTreeEvidence:
    if command_runner is None:
        command_runner = run_bounded_command
    if unmount_waiter is None:
        unmount_waiter = wait_for_unmounted
    device: str | None = None
    attach_attempted = False
    result: installed.AppTreeEvidence | None = None
    primary_error: BaseException | None = None
    try:
        attach_attempted = True
        attached = command_runner(attach_dmg_command(dmg_path, mountpoint))
        entity = parse_attach_plist(
            attached.stdout,
            expected_mountpoint=mountpoint,
        )
        device = entity.device
        result = copier()
    except BaseException as error:
        primary_error = error
    finally:
        cleanup_error: BaseException | None = None
        if device is None and attach_attempted:
            try:
                info = command_runner(info_dmg_command())
                recovered = parse_info_plist_device(
                    info.stdout,
                    expected_mountpoint=mountpoint,
                )
                device = recovered.device if recovered is not None else None
            except BaseException:
                pass
        if device is not None:
            try:
                command_runner(detach_dmg_command(device))
            except BaseException as error:
                cleanup_error = error
        elif attach_attempted:
            try:
                command_runner(detach_mountpoint_command(mountpoint))
            except BaseException as error:
                if primary_error is None:
                    cleanup_error = error
        try:
            unmount_waiter(mountpoint)
        except BaseException as error:
            cleanup_error = error
        if cleanup_error is not None:
            raise LocalDMGSmokeError("local DMG cleanup failed") from cleanup_error
    if primary_error is not None:
        raise primary_error
    if result is None:
        raise LocalDMGSmokeError("local DMG copy did not produce evidence")
    return result


def _safe_launch_record(
    record: dict[str, object],
    *,
    expected_ordinal: int,
) -> dict[str, object]:
    required = (
        "activationPolicy",
        "executablePathMatched",
        "finishedLaunching",
        "newProcessIdentifierDetected",
        "observationDeadlineReached",
        "ordinal",
        "terminationAccepted",
    )
    if any(key not in record for key in required):
        raise LocalDMGSmokeError("LaunchServices result is incomplete")
    if (
        type(record["activationPolicy"]) is not int
        or record["activationPolicy"] != 0
        or record["executablePathMatched"] is not True
        or record["finishedLaunching"] is not True
        or record["newProcessIdentifierDetected"] is not True
        or record["observationDeadlineReached"] is not True
        or record["ordinal"] != expected_ordinal
        or type(record["ordinal"]) is not int
        or record["terminationAccepted"] is not True
    ):
        raise LocalDMGSmokeError("LaunchServices result did not pass")
    emitted = tuple(
        key for key in required if key != "executablePathMatched"
    )
    return {key: record[key] for key in emitted}


def _validated_sqlite_records(
    evidence: Sequence[installed.SQLiteStateEvidence],
) -> list[dict[str, object]]:
    if tuple(item.filename for item in evidence) != tuple(
        installed.EXPECTED_SQLITE_FILES
    ):
        raise LocalDMGSmokeError("local DMG SQLite inventory is invalid")
    for item in evidence:
        if item.integrity_check != "ok":
            raise LocalDMGSmokeError("local DMG SQLite integrity did not pass")
        if item.filename == installed.CHAT_DATABASE_FILENAME:
            if (
                type(item.total_event_count) is not int
                or item.total_event_count != 0
            ):
                raise LocalDMGSmokeError(
                    "local DMG runtime-chat database is not empty"
                )
        elif item.total_event_count is not None:
            raise LocalDMGSmokeError(
                "local DMG non-chat database count is invalid"
            )
    return [item.record() for item in evidence]


def build_result(
    *,
    release: engine.ReleaseInputs,
    release_id: str,
    app_tree: installed.AppTreeEvidence,
    runs: Sequence[dict[str, object]],
    sqlite_evidence: Sequence[installed.SQLiteStateEvidence],
    runtime_identity_present: bool,
) -> dict[str, object]:
    if (
        len(runs) != 2
        or len(sqlite_evidence) != len(installed.EXPECTED_SQLITE_FILES)
        or type(runtime_identity_present) is not bool
    ):
        raise LocalDMGSmokeError("local DMG result inputs are incomplete")
    safe_runs = [
        _safe_launch_record(dict(run), expected_ordinal=ordinal)
        for ordinal, run in enumerate(runs, start=1)
    ]
    sqlite_records = _validated_sqlite_records(sqlite_evidence)
    return {
        "image": {
            "ephemeral": True,
            "filesystem": DMG_FILESYSTEM,
            "format": DMG_FORMAT,
            "retained": False,
            "verified": True,
        },
        "installation": {
            "adHocAppSealAndVersionVerified": True,
            "applicationsAliasPresent": True,
            "copyTool": "ditto",
            "exactReleaseTreeCopied": True,
            "tree": app_tree.record(),
        },
        "isolation": {
            "cleanHomeConfigured": True,
            "preexistingBundleApplicationsPreserved": True,
            "runtimeIdentityFileOverrideConfigured": True,
            "temporaryCFUserHomeConfigured": True,
        },
        "launchServices": {
            "distinctProcessIdentifiers": True,
            "exactInstalledBundlePerCycle": True,
            "runs": safe_runs,
        },
        "limitations": list(LIMITATIONS),
        "mount": {
            "detachedBeforeLaunch": True,
            "exactFreshMountpoint": True,
            "nobrowse": True,
            "oneMountedEntity": True,
            "readOnly": True,
            "unmountedVerified": True,
        },
        "release": {
            "archiveSha256": release.archive_sha256,
            "manifestSha256": release.manifest_sha256,
            "releaseId": release_id,
        },
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "state": {
            "databaseCount": len(sqlite_evidence),
            "emptyRuntimeChatVerified": True,
            "integrityChecks": "passed",
            "regularFileBytesAndModesUnchangedAcrossRelaunch": True,
            "runtimeIdentityFilePresent": runtime_identity_present,
            "sqlite": sqlite_records,
            "stableAcrossRelaunch": True,
        },
        "status": "passed",
    }


def publish_result(path: Path, result: dict[str, object]) -> None:
    payload = engine.canonical_json_bytes(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_file() and not path.is_symlink() and path.read_bytes() == payload:
            return
        raise LocalDMGSmokeError("refusing to replace different local DMG result")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.read_bytes() != payload
            ):
                raise LocalDMGSmokeError(
                    "concurrent local DMG result publication differed"
                )
    finally:
        temporary.unlink(missing_ok=True)


def execute(
    *,
    archive_dir: Path,
    result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    readiness_timeout_seconds = engine.validated_duration(
        readiness_timeout_seconds,
        "readiness timeout",
        0.1,
        60.0,
    )
    observation_seconds = engine.validated_duration(
        observation_seconds,
        "observation window",
        engine.MINIMUM_OBSERVATION_SECONDS,
        30.0,
    )
    termination_timeout_seconds = engine.validated_duration(
        termination_timeout_seconds,
        "termination timeout",
        0.1,
        30.0,
    )
    version = current_release()
    release_id = release_id_for(version)
    release = recovery.load_release_inputs(
        archive_dir,
        version=version,
    )
    preexisting_applications = installed.list_bundle_applications()

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-local-dmg-install-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        extracted_app = engine.extract_packaged_app(
            release,
            temporary_root / "extracted-app",
        )
        recovery.verify_packaged_app(extracted_app, release, version=version)
        release_tree = installed.app_tree_evidence(extracted_app, release)

        staging_root = temporary_root / "dmg-staging"
        staged_app = stage_dmg_root(extracted_app, staging_root)
        recovery.verify_packaged_app(staged_app, release, version=version)
        if installed.app_tree_evidence(staged_app, release) != release_tree:
            raise LocalDMGSmokeError("staged local DMG app differs from release")

        dmg_path = temporary_root / "local-image.dmg"
        run_bounded_command(create_dmg_command(staging_root, dmg_path))
        run_bounded_command(verify_dmg_command(dmg_path))

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        mountpoint = temporary_root / "mount"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
            mountpoint,
        ):
            path.mkdir(mode=0o700)
        installed_app = (
            isolated_home / "Applications" / installed.APP_RELATIVE_PATH
        )
        copied_tree = attach_copy_detach(
            dmg_path=dmg_path,
            mountpoint=mountpoint,
            copier=lambda: copy_from_mounted_dmg(
                mountpoint=mountpoint,
                installed_app=installed_app,
                release=release,
                version=version,
                expected_tree=release_tree,
            ),
        )
        if copied_tree != release_tree:
            raise LocalDMGSmokeError("local DMG installed tree differs")

        identity_file = isolated_state / "runtime-identity.json"
        environment = installed.isolated_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
        )
        application_support = (
            isolated_home / "Library/Application Support/AetherLink"
        )
        if (
            application_support.exists()
            or application_support.is_symlink()
            or identity_file.exists()
            or identity_file.is_symlink()
        ):
            raise LocalDMGSmokeError("clean-HOME state existed before launch")

        first_pid, first_run = installed.run_launch_services_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        first_tree = installed.app_tree_evidence(installed_app, release)
        first_sqlite = installed.sqlite_state_evidence(application_support)
        first_state = installed.state_file_records(
            application_support,
            identity_file,
        )

        second_pid, second_run = installed.run_launch_services_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if first_pid == second_pid:
            raise LocalDMGSmokeError("LaunchServices reused a process identifier")
        second_tree = installed.app_tree_evidence(installed_app, release)
        second_sqlite = installed.sqlite_state_evidence(application_support)
        second_state = installed.state_file_records(
            application_support,
            identity_file,
        )
        if first_tree != release_tree or second_tree != release_tree:
            raise LocalDMGSmokeError("installed app tree changed during launch")
        if first_sqlite != second_sqlite or first_state != second_state:
            raise LocalDMGSmokeError("installed state changed across relaunch")
        installed.assert_preexisting_applications_preserved(
            preexisting_applications
        )
        result = build_result(
            release=release,
            release_id=release_id,
            app_tree=copied_tree,
            runs=(first_run, second_run),
            sqlite_evidence=first_sqlite,
            runtime_identity_present=identity_file.is_file(),
        )

    publish_result(result_path, result)
    return result


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=default_archive_dir(),
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=default_result_path(),
    )
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=float,
        default=15.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=float,
        default=10.0,
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        execute(
            archive_dir=arguments.archive_dir,
            result_path=arguments.result,
            readiness_timeout_seconds=arguments.readiness_timeout_seconds,
            observation_seconds=arguments.observation_seconds,
            termination_timeout_seconds=arguments.termination_timeout_seconds,
        )
    except (
        LocalDMGSmokeError,
        engine.LifecycleSmokeError,
        OSError,
        plistlib.InvalidFileException,
        ValueError,
    ):
        print("Local DMG install smoke failed.", file=sys.stderr)
        return 1
    print("Local DMG install smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
