#!/usr/bin/env python3
"""Measure bounded idle resources for the exact Build 24 packaged macOS app."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import math
import os
from pathlib import Path
import platform
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterator, Sequence

if __package__:
    from script import (
        run_macos_clean_home_installed_app_smoke as installed,
    )
    from script import (
        run_macos_isolated_upgrade_smoke as upgrade,
    )
    from script import (
        run_macos_local_dmg_install_smoke_v2 as dmg,
    )
else:
    import run_macos_clean_home_installed_app_smoke as installed
    import run_macos_isolated_upgrade_smoke as upgrade
    import run_macos_local_dmg_install_smoke_v2 as dmg


engine = dmg.engine
recovery = dmg.recovery
IdleResourceSmokeError = engine.LifecycleSmokeError
ROOT = Path(__file__).resolve().parents[1]

RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-build24-idle-resource-stability-v1"
)
EXPECTED_BUILD_NUMBER = 24
WARMUP_MILLISECONDS = 60_000
OBSERVATION_MILLISECONDS = 600_000
SAMPLE_INTERVAL_MILLISECONDS = 5_000
SAMPLE_COUNT = 120
SAMPLE_LATENESS_LIMIT_MILLISECONDS = 1_000
BASELINE_WINDOW_SAMPLE_COUNT = 12
FINAL_WINDOW_SAMPLE_COUNT = 12
WAIT_POLL_MILLISECONDS = 1_000
READINESS_TIMEOUT_SECONDS = 15.0
TERMINATION_TIMEOUT_SECONDS = 10.0

FINAL_FD_DELTA_LIMIT = 2
PEAK_FD_DELTA_LIMIT = 8
FINAL_THREAD_DELTA_LIMIT = 2
PEAK_THREAD_DELTA_LIMIT = 8
FINAL_RSS_DELTA_LIMIT_BYTES = 32 * 1024 * 1024
PEAK_RSS_DELTA_LIMIT_BYTES = 128 * 1024 * 1024

PROC_PIDLISTFDS = 1
PROC_PIDTASKINFO = 4
PROC_PIDPATHINFO_MAXSIZE = 4096
MAXIMUM_FD_BUFFER_BYTES = 1024 * 1024

LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "single-direct-owned-child-idle-observation-only",
    "sixty-second-warmup-and-ten-minute-observation-only",
    "network-denied-and-writes-confined-to-temporary-root",
    "libproc-resource-samples-are-point-in-time-nonatomic-observations",
    "local-regression-budgets-not-performance-sla-or-capacity-evidence",
    "single-recorded-run-not-repeatability-or-long-soak-evidence",
    "no-signing-or-signature-verification-performed",
    (
        "not-install-upgrade-uninstall-reinstall-recovery-crash-or-"
        "rollback-evidence"
    ),
    (
        "not-load-provider-device-ui-accessibility-production-or-"
        "security-evidence"
    ),
)

EXPECTED_BUILD24_RELEASE_FILES = {
    "aetherlink-1.0.0+24-local-v1.zip": {
        "sha256": (
            "104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c"
        ),
        "size": 166_345_274,
    },
    "aetherlink-1.0.0+24-local-v1.manifest.json": {
        "sha256": (
            "eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b"
        ),
        "size": 15_200,
    },
    "aetherlink-1.0.0+24-local-v1.zip.sha256": {
        "sha256": (
            "827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882"
        ),
        "size": 99,
    },
}


class ProcTaskInfo(ctypes.Structure):
    _fields_ = (
        ("virtual_size", ctypes.c_uint64),
        ("resident_size", ctypes.c_uint64),
        ("total_user", ctypes.c_uint64),
        ("total_system", ctypes.c_uint64),
        ("threads_user", ctypes.c_uint64),
        ("threads_system", ctypes.c_uint64),
        ("policy", ctypes.c_int32),
        ("faults", ctypes.c_int32),
        ("pageins", ctypes.c_int32),
        ("cow_faults", ctypes.c_int32),
        ("messages_sent", ctypes.c_int32),
        ("messages_received", ctypes.c_int32),
        ("syscalls_mach", ctypes.c_int32),
        ("syscalls_unix", ctypes.c_int32),
        ("csw", ctypes.c_int32),
        ("threadnum", ctypes.c_int32),
        ("numrunning", ctypes.c_int32),
        ("priority", ctypes.c_int32),
    )


class ProcFDInfo(ctypes.Structure):
    _fields_ = (
        ("fd", ctypes.c_int32),
        ("fdtype", ctypes.c_uint32),
    )


@dataclass(frozen=True)
class ResourceSample:
    open_file_descriptor_count: int
    resident_bytes: int
    thread_count: int

    def record(
        self,
        *,
        ordinal: int,
        target_elapsed_milliseconds: int,
        observed_lateness_milliseconds: int,
    ) -> dict[str, object]:
        return {
            "observedLatenessMilliseconds": (
                observed_lateness_milliseconds
            ),
            "openFileDescriptorCount": self.open_file_descriptor_count,
            "ordinal": ordinal,
            "residentBytes": self.resident_bytes,
            "targetElapsedMilliseconds": target_elapsed_milliseconds,
            "threadCount": self.thread_count,
        }


def current_release() -> recovery.ReleaseVersion:
    version = recovery.current_release()
    if (
        type(version.build_number) is not int
        or version.build_number != EXPECTED_BUILD_NUMBER
    ):
        raise IdleResourceSmokeError(
            "idle resource evidence requires terminal Build 24"
        )
    return version


def release_id_for(version: recovery.ReleaseVersion) -> str:
    return recovery.release_id_for(version)


def default_archive_dir() -> Path:
    version = current_release()
    return ROOT / "dist/releases" / release_id_for(version)


def default_result_path() -> Path:
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-24-"
            "idle-resource-stability-v1.json"
        )
    )


def require_exact_positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise IdleResourceSmokeError(
            f"{label} must be an exact positive integer"
        )
    return value


def validate_build24_snapshot_files(
    snapshot_files: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    if (
        type(snapshot_files) is not dict
        or set(snapshot_files) != set(EXPECTED_BUILD24_RELEASE_FILES)
    ):
        raise IdleResourceSmokeError(
            "Build 24 snapshot file inventory differs from the fixed contract"
        )
    validated: dict[str, dict[str, object]] = {}
    for name in sorted(EXPECTED_BUILD24_RELEASE_FILES):
        record = snapshot_files[name]
        expected = EXPECTED_BUILD24_RELEASE_FILES[name]
        if (
            type(record) is not dict
            or set(record) != {"sha256", "size"}
            or type(record["sha256"]) is not str
            or type(record["size"]) is not int
            or record != expected
        ):
            raise IdleResourceSmokeError(
                f"Build 24 snapshot identity differs for {name}"
            )
        validated[name] = dict(record)
    return validated


def validate_libproc_abi() -> None:
    if sys.platform != "darwin":
        raise IdleResourceSmokeError(
            "idle resource evidence requires macOS libproc"
        )
    if ctypes.sizeof(ProcTaskInfo) != 96:
        raise IdleResourceSmokeError(
            "unexpected macOS proc_taskinfo ABI size"
        )
    if ctypes.sizeof(ProcFDInfo) != 8:
        raise IdleResourceSmokeError(
            "unexpected macOS proc_fdinfo ABI size"
        )


@lru_cache(maxsize=1)
def libproc_functions() -> tuple[object, object, object]:
    validate_libproc_abi()
    try:
        library = ctypes.CDLL(
            "/usr/lib/libproc.dylib",
            use_errno=True,
        )
    except OSError as error:
        raise IdleResourceSmokeError(
            f"cannot load macOS libproc: {error}"
        ) from error

    pidinfo = library.proc_pidinfo
    pidinfo.argtypes = (
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_int,
    )
    pidinfo.restype = ctypes.c_int
    pidpath = library.proc_pidpath
    pidpath.argtypes = (
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    pidpath.restype = ctypes.c_int
    return library, pidinfo, pidpath


def call_proc_pidinfo(
    pid: int,
    flavor: int,
    buffer: object | None,
    buffer_size: int,
) -> int:
    _, pidinfo, _ = libproc_functions()
    ctypes.set_errno(0)
    result = pidinfo(pid, flavor, 0, buffer, buffer_size)  # type: ignore[operator]
    if result <= 0:
        error_number = ctypes.get_errno()
        raise IdleResourceSmokeError(
            "macOS proc_pidinfo failed "
            f"for flavor {flavor} with errno {error_number}"
        )
    return result


def read_process_path(pid: int) -> Path:
    require_exact_positive_int(pid, "process identifier")
    _, _, pidpath = libproc_functions()
    buffer = ctypes.create_string_buffer(PROC_PIDPATHINFO_MAXSIZE)
    ctypes.set_errno(0)
    returned = pidpath(  # type: ignore[operator]
        pid,
        buffer,
        PROC_PIDPATHINFO_MAXSIZE,
    )
    if returned <= 0 or returned >= PROC_PIDPATHINFO_MAXSIZE:
        error_number = ctypes.get_errno()
        raise IdleResourceSmokeError(
            "macOS proc_pidpath failed or truncated "
            f"with errno {error_number}"
        )
    payload = bytes(buffer.raw[:returned])
    if b"\0" in payload:
        payload = payload.split(b"\0", 1)[0]
    try:
        path_text = payload.decode("utf-8")
    except UnicodeError as error:
        raise IdleResourceSmokeError(
            "macOS proc_pidpath returned invalid UTF-8"
        ) from error
    if not path_text or "\x00" in path_text:
        raise IdleResourceSmokeError(
            "macOS proc_pidpath returned an invalid path"
        )
    return Path(path_text).resolve()


def read_task_resources(pid: int) -> tuple[int, int]:
    require_exact_positive_int(pid, "process identifier")
    task_info = ProcTaskInfo()
    returned = call_proc_pidinfo(
        pid,
        PROC_PIDTASKINFO,
        ctypes.byref(task_info),
        ctypes.sizeof(task_info),
    )
    if returned != ctypes.sizeof(task_info):
        raise IdleResourceSmokeError(
            "macOS proc_pidinfo returned short task information"
        )
    resident_bytes = require_exact_positive_int(
        task_info.resident_size,
        "resident byte count",
    )
    thread_count = require_exact_positive_int(
        task_info.threadnum,
        "thread count",
    )
    return resident_bytes, thread_count


def read_open_file_descriptor_count(pid: int) -> int:
    require_exact_positive_int(pid, "process identifier")
    entry_size = ctypes.sizeof(ProcFDInfo)
    capacity_hint = call_proc_pidinfo(
        pid,
        PROC_PIDLISTFDS,
        None,
        0,
    )
    buffer_size = max(capacity_hint + 16 * entry_size, 4096)
    while True:
        if buffer_size > MAXIMUM_FD_BUFFER_BYTES:
            raise IdleResourceSmokeError(
                "macOS open-file descriptor inventory exceeded 1 MiB"
            )
        entry_capacity = math.ceil(buffer_size / entry_size)
        entries = (ProcFDInfo * entry_capacity)()
        allocated_bytes = ctypes.sizeof(entries)
        returned = call_proc_pidinfo(
            pid,
            PROC_PIDLISTFDS,
            entries,
            allocated_bytes,
        )
        if returned == allocated_bytes:
            buffer_size = allocated_bytes * 2
            continue
        if (
            returned > allocated_bytes
            or returned % entry_size != 0
        ):
            raise IdleResourceSmokeError(
                "macOS open-file descriptor inventory is malformed"
            )
        count = returned // entry_size
        if count <= 0:
            raise IdleResourceSmokeError(
                "macOS open-file descriptor inventory is empty"
            )
        file_descriptors = [entries[index].fd for index in range(count)]
        if (
            any(type(value) is not int or value < 0 for value in file_descriptors)
            or len(file_descriptors) != len(set(file_descriptors))
        ):
            raise IdleResourceSmokeError(
                "macOS open-file descriptor inventory contains invalid "
                "or duplicate descriptors"
            )
        return count


def collect_resource_sample(
    pid: int,
    expected_executable: Path,
) -> ResourceSample:
    process_path = read_process_path(pid)
    if process_path != expected_executable.resolve():
        raise IdleResourceSmokeError(
            "libproc process path no longer matches the owned executable"
        )
    resident_bytes, thread_count = read_task_resources(pid)
    descriptor_count = read_open_file_descriptor_count(pid)
    return ResourceSample(
        open_file_descriptor_count=descriptor_count,
        resident_bytes=resident_bytes,
        thread_count=thread_count,
    )


def upper_median(values: Sequence[int]) -> int:
    if not values or any(type(value) is not int for value in values):
        raise IdleResourceSmokeError(
            "resource median requires exact integer samples"
        )
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def exact_json_value_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        left_mapping = left
        right_mapping = right
        if (
            any(type(key) is not str for key in left_mapping)
            or any(type(key) is not str for key in right_mapping)
            or set(left_mapping) != set(right_mapping)
        ):
            return False
        return all(
            exact_json_value_equal(
                left_mapping[key],
                right_mapping[key],
            )
            for key in left_mapping
        )
    if type(left) is list:
        left_items = left
        right_items = right
        return len(left_items) == len(right_items) and all(
            exact_json_value_equal(left_item, right_item)
            for left_item, right_item in zip(left_items, right_items)
        )
    return left == right


def metric_summary(
    values: Sequence[int],
    *,
    final_delta_limit: int,
    peak_delta_limit: int,
) -> dict[str, object]:
    if (
        len(values) != SAMPLE_COUNT
        or any(type(value) is not int or value <= 0 for value in values)
    ):
        raise IdleResourceSmokeError(
            "resource metric requires exactly 120 positive integer samples"
        )
    if (
        type(final_delta_limit) is not int
        or final_delta_limit < 0
        or type(peak_delta_limit) is not int
        or peak_delta_limit < final_delta_limit
    ):
        raise IdleResourceSmokeError(
            "resource metric limits are invalid"
        )
    baseline = upper_median(values[:BASELINE_WINDOW_SAMPLE_COUNT])
    final = upper_median(values[-FINAL_WINDOW_SAMPLE_COUNT:])
    maximum = max(values)
    final_delta = final - baseline
    peak_delta = maximum - baseline
    passed = (
        final_delta <= final_delta_limit
        and peak_delta <= peak_delta_limit
    )
    return {
        "baselineUpperMedian": baseline,
        "finalDelta": final_delta,
        "finalDeltaLimit": final_delta_limit,
        "finalUpperMedian": final,
        "maximum": maximum,
        "passed": passed,
        "peakDelta": peak_delta,
        "peakDeltaLimit": peak_delta_limit,
    }


def measurement_summary(
    samples: Sequence[dict[str, object]],
) -> dict[str, object]:
    if len(samples) != SAMPLE_COUNT:
        raise IdleResourceSmokeError(
            "measurement requires exactly 120 samples"
        )
    expected_keys = {
        "observedLatenessMilliseconds",
        "openFileDescriptorCount",
        "ordinal",
        "residentBytes",
        "targetElapsedMilliseconds",
        "threadCount",
    }
    for ordinal, sample in enumerate(samples, start=1):
        if type(sample) is not dict or set(sample) != expected_keys:
            raise IdleResourceSmokeError(
                "resource sample has an invalid closed schema"
            )
        if (
            type(sample["ordinal"]) is not int
            or sample["ordinal"] != ordinal
            or type(sample["targetElapsedMilliseconds"]) is not int
            or sample["targetElapsedMilliseconds"]
            != ordinal * SAMPLE_INTERVAL_MILLISECONDS
            or type(sample["observedLatenessMilliseconds"]) is not int
            or sample["observedLatenessMilliseconds"] < 0
            or sample["observedLatenessMilliseconds"]
            > SAMPLE_LATENESS_LIMIT_MILLISECONDS
        ):
            raise IdleResourceSmokeError(
                "resource sample schedule is invalid"
            )
        for key in (
            "openFileDescriptorCount",
            "residentBytes",
            "threadCount",
        ):
            if type(sample[key]) is not int or sample[key] <= 0:
                raise IdleResourceSmokeError(
                    f"resource sample {key} must be a positive integer"
                )

    resident = metric_summary(
        [sample["residentBytes"] for sample in samples],  # type: ignore[misc]
        final_delta_limit=FINAL_RSS_DELTA_LIMIT_BYTES,
        peak_delta_limit=PEAK_RSS_DELTA_LIMIT_BYTES,
    )
    descriptors = metric_summary(
        [
            sample["openFileDescriptorCount"]  # type: ignore[misc]
            for sample in samples
        ],
        final_delta_limit=FINAL_FD_DELTA_LIMIT,
        peak_delta_limit=PEAK_FD_DELTA_LIMIT,
    )
    threads = metric_summary(
        [sample["threadCount"] for sample in samples],  # type: ignore[misc]
        final_delta_limit=FINAL_THREAD_DELTA_LIMIT,
        peak_delta_limit=PEAK_THREAD_DELTA_LIMIT,
    )
    if not all(
        summary["passed"] is True
        for summary in (resident, descriptors, threads)
    ):
        raise IdleResourceSmokeError(
            "idle resource samples exceeded a predeclared regression budget"
        )
    return {
        "openFileDescriptors": descriptors,
        "residentBytes": resident,
        "threads": threads,
    }


def validate_ready_identity(
    process: subprocess.Popen[bytes],
    executable: Path,
    *,
    query: Callable[
        [int],
        engine.ApplicationStatus | None,
    ] = engine.query_application,
    path_reader: Callable[[int], Path] = read_process_path,
) -> engine.ApplicationStatus:
    if process.poll() is not None:
        raise IdleResourceSmokeError(
            "owned app exited during the idle observation"
        )
    status = installed.assert_query_identity(
        query(process.pid),
        executable,
    )
    if not status.finished_launching or status.activation_policy != 0:
        raise IdleResourceSmokeError(
            "owned app lost its finished regular AppKit identity"
        )
    if path_reader(process.pid) != executable.resolve():
        raise IdleResourceSmokeError(
            "owned app libproc executable identity changed"
        )
    return status


def wait_until_monotonic_target(
    *,
    process: subprocess.Popen[bytes],
    target_nanoseconds: int,
    monotonic_ns: Callable[[], int],
    sleeper: Callable[[float], None],
) -> None:
    previous = monotonic_ns()
    while previous < target_nanoseconds:
        if process.poll() is not None:
            raise IdleResourceSmokeError(
                "owned app exited before the next idle sample"
            )
        remaining = target_nanoseconds - previous
        sleep_nanoseconds = min(
            remaining,
            WAIT_POLL_MILLISECONDS * 1_000_000,
        )
        sleeper(sleep_nanoseconds / 1_000_000_000)
        current = monotonic_ns()
        if current < previous:
            raise IdleResourceSmokeError(
                "monotonic clock moved backwards"
            )
        previous = current


def cleanup_owned_child(
    process: subprocess.Popen[bytes],
    executable: Path,
    *,
    timeout_seconds: float,
    query: Callable[
        [int],
        engine.ApplicationStatus | None,
    ] = engine.query_application,
    path_reader: Callable[[int], Path] = read_process_path,
    request_termination: Callable[..., bool] = (
        engine.request_application_termination
    ),
) -> None:
    if process.poll() is not None:
        process.wait(timeout=timeout_seconds)
        return
    status = query(process.pid)
    if status is not None:
        installed.assert_query_identity(status, executable)
    if path_reader(process.pid) != executable.resolve():
        raise IdleResourceSmokeError(
            "refusing to clean an owned PID with changed executable identity"
        )
    accepted = False
    try:
        accepted = request_termination(
            process.pid,
            executable,
            force=False,
        )
    except IdleResourceSmokeError:
        accepted = False
    if accepted:
        try:
            process.wait(timeout=timeout_seconds)
            return
        except subprocess.TimeoutExpired:
            pass
    if process.poll() is not None:
        return
    if path_reader(process.pid) != executable.resolve():
        raise IdleResourceSmokeError(
            "refusing fallback cleanup after executable identity drift"
        )
    process.kill()
    process.wait(timeout=timeout_seconds)


@contextmanager
def isolated_resource_root(
    *,
    termination_timeout_seconds: float,
    lister: Callable[
        [],
        tuple[installed.RunningApplication, ...],
    ] = installed.list_bundle_applications,
) -> Iterator[
    tuple[
        Path,
        list[tuple[subprocess.Popen[bytes], Path]],
    ]
]:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="aetherlink-macos-build24-idle-resource-v1-"
        )
    ).resolve()
    owned_processes: list[tuple[subprocess.Popen[bytes], Path]] = []
    body_error: BaseException | None = None
    try:
        try:
            yield temporary_root, owned_processes
        except BaseException as error:
            body_error = error
            raise
    finally:
        cleanup_errors: list[BaseException] = []
        for process, executable in tuple(owned_processes):
            try:
                cleanup_owned_child(
                    process,
                    executable,
                    timeout_seconds=termination_timeout_seconds,
                )
            except BaseException as error:
                cleanup_errors.append(error)
        try:
            unexpected = [
                application
                for application in lister()
                if temporary_root
                in Path(application.executable_path).resolve().parents
            ]
            if unexpected:
                cleanup_errors.append(
                    IdleResourceSmokeError(
                        "an unowned temporary-root app process remains; "
                        "it was not terminated"
                    )
                )
        except BaseException as error:
            cleanup_errors.append(error)
        if cleanup_errors:
            diagnostic = IdleResourceSmokeError(
                "idle resource cleanup failed; diagnostic root retained "
                f"at {temporary_root}"
            )
            if isinstance(body_error, (KeyboardInterrupt, SystemExit)):
                raise body_error from diagnostic
            for error in cleanup_errors:
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise error
            raise diagnostic from cleanup_errors[0]
        try:
            shutil.rmtree(temporary_root)
        except BaseException as error:
            raise IdleResourceSmokeError(
                "idle resource temporary root cleanup failed; "
                f"diagnostic root retained at {temporary_root}"
            ) from error


def verify_extracted_app(
    app_path: Path,
    release: engine.ReleaseInputs,
    *,
    version: recovery.ReleaseVersion,
) -> dict[str, object]:
    info_plist = app_path / engine.INFO_PLIST_RELATIVE_PATH
    executable = app_path / engine.EXECUTABLE_RELATIVE_PATH
    if (
        info_plist.is_symlink()
        or executable.is_symlink()
        or not info_plist.is_file()
        or not executable.is_file()
        or not os.access(executable, os.X_OK)
    ):
        raise IdleResourceSmokeError(
            "extracted Build 24 app lacks physical executable metadata"
        )
    try:
        plist = plistlib.loads(info_plist.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise IdleResourceSmokeError(
            f"invalid extracted Build 24 Info.plist: {error}"
        ) from error
    expected_plist = {
        "CFBundleIdentifier": engine.EXPECTED_BUNDLE_ID,
        "CFBundleShortVersionString": version.marketing_version,
        "CFBundleVersion": str(version.build_number),
    }
    if any(
        type(plist.get(key)) is not type(expected)
        or plist.get(key) != expected
        for key, expected in expected_plist.items()
    ):
        raise IdleResourceSmokeError(
            "extracted Build 24 Info.plist identity is invalid"
        )

    app_tree = installed.app_tree_evidence(app_path, release)
    members = engine.manifest_member_map(release.manifest)
    executable_member = (
        engine.APP_MEMBER_PREFIX
        + engine.EXECUTABLE_RELATIVE_PATH.as_posix()
    )
    expected_executable = members.get(executable_member)
    if expected_executable is None:
        raise IdleResourceSmokeError(
            "release manifest lacks the Build 24 executable"
        )
    executable_status = executable.lstat()
    executable_identity = (
        executable_status.st_size,
        recovery.sha256_file(executable),
        stat.S_IMODE(executable_status.st_mode),
    )
    if executable_identity != expected_executable:
        raise IdleResourceSmokeError(
            "extracted Build 24 executable differs from the manifest"
        )
    platforms = release.manifest.get("platforms")
    macos = platforms.get("macos") if type(platforms) is dict else None
    uuid = macos.get("uuid") if type(macos) is dict else None
    if type(uuid) is not str or not uuid:
        raise IdleResourceSmokeError(
            "release manifest lacks the Build 24 macOS UUID"
        )
    return {
        "appTree": app_tree.record(),
        "buildNumber": version.build_number,
        "bundleIdentifier": engine.EXPECTED_BUNDLE_ID,
        "executableMode": expected_executable[2],
        "executableSha256": expected_executable[1],
        "executableSize": expected_executable[0],
        "marketingVersion": version.marketing_version,
        "uuid": uuid,
    }


def run_owned_idle_observation(
    *,
    executable: Path,
    profile: str,
    environment: dict[str, str],
    working_directory: Path,
    readiness_timeout_seconds: float,
    termination_timeout_seconds: float,
    owned_processes: list[tuple[subprocess.Popen[bytes], Path]],
    popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    readiness_waiter: Callable[..., engine.ApplicationStatus] = (
        engine.wait_for_application_readiness
    ),
    query: Callable[
        [int],
        engine.ApplicationStatus | None,
    ] = engine.query_application,
    path_reader: Callable[[int], Path] = read_process_path,
    sampler: Callable[[int, Path], ResourceSample] = (
        collect_resource_sample
    ),
    request_termination: Callable[..., bool] = (
        engine.request_application_termination
    ),
    gone_waiter: Callable[..., bool] = installed.wait_until_application_gone,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    process = popen_factory(
        [
            str(engine.SANDBOX_EXEC),
            "-p",
            profile,
            str(executable),
        ],
        cwd=working_directory,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    owned_processes.append((process, executable))
    completed_normally = False
    try:
        status = readiness_waiter(
            process,
            executable,
            timeout_seconds=readiness_timeout_seconds,
            query=query,
        )
        if not status.finished_launching or status.activation_policy != 0:
            raise IdleResourceSmokeError(
                "owned app did not reach regular AppKit readiness"
            )
        if path_reader(process.pid) != executable.resolve():
            raise IdleResourceSmokeError(
                "owned app initial libproc path is not the exact executable"
            )

        warmup_start = monotonic_ns()
        warmup_target = (
            warmup_start + WARMUP_MILLISECONDS * 1_000_000
        )
        wait_until_monotonic_target(
            process=process,
            target_nanoseconds=warmup_target,
            monotonic_ns=monotonic_ns,
            sleeper=sleeper,
        )
        validate_ready_identity(
            process,
            executable,
            query=query,
            path_reader=path_reader,
        )

        measurement_start = monotonic_ns()
        sample_records: list[dict[str, object]] = []
        maximum_lateness = 0
        for ordinal in range(1, SAMPLE_COUNT + 1):
            target_elapsed = ordinal * SAMPLE_INTERVAL_MILLISECONDS
            target_nanoseconds = (
                measurement_start + target_elapsed * 1_000_000
            )
            wait_until_monotonic_target(
                process=process,
                target_nanoseconds=target_nanoseconds,
                monotonic_ns=monotonic_ns,
                sleeper=sleeper,
            )
            validate_ready_identity(
                process,
                executable,
                query=query,
                path_reader=path_reader,
            )
            sample = sampler(process.pid, executable)
            if process.poll() is not None:
                raise IdleResourceSmokeError(
                    "owned app exited while collecting an idle sample"
                )
            observed_nanoseconds = monotonic_ns()
            if observed_nanoseconds < target_nanoseconds:
                raise IdleResourceSmokeError(
                    "idle sample was collected before its target"
                )
            lateness_nanoseconds = (
                observed_nanoseconds - target_nanoseconds
            )
            lateness_milliseconds = (
                lateness_nanoseconds + 999_999
            ) // 1_000_000
            if (
                lateness_milliseconds
                > SAMPLE_LATENESS_LIMIT_MILLISECONDS
            ):
                raise IdleResourceSmokeError(
                    "idle sample exceeded the lateness limit"
                )
            maximum_lateness = max(
                maximum_lateness,
                lateness_milliseconds,
            )
            sample_records.append(
                sample.record(
                    ordinal=ordinal,
                    target_elapsed_milliseconds=target_elapsed,
                    observed_lateness_milliseconds=lateness_milliseconds,
                )
            )

        summary = measurement_summary(sample_records)
        validate_ready_identity(
            process,
            executable,
            query=query,
            path_reader=path_reader,
        )
        accepted = request_termination(
            process.pid,
            executable,
            force=False,
        )
        if accepted is not True:
            raise IdleResourceSmokeError(
                "owned app rejected exact graceful termination"
            )
        try:
            exit_code = process.wait(
                timeout=termination_timeout_seconds
            )
        except subprocess.TimeoutExpired as error:
            raise IdleResourceSmokeError(
                "owned app did not terminate within the graceful deadline"
            ) from error
        if exit_code != 0:
            raise IdleResourceSmokeError(
                f"owned app exited with nonzero status {exit_code}"
            )
        if not gone_waiter(
            process.pid,
            timeout_seconds=termination_timeout_seconds,
            query=query,
        ):
            raise IdleResourceSmokeError(
                "owned app remained in AppKit after reap"
            )
        completed_normally = True
        return {
            "activationPolicy": status.activation_policy,
            "appKitProcessAbsentAfterReap": True,
            "exitCode": exit_code,
            "finishedLaunching": status.finished_launching,
            "gracefulTerminationAccepted": accepted,
            "maximumObservedLatenessMilliseconds": maximum_lateness,
            "ownedChildProcess": True,
            "processIdentifierRetained": False,
            "processReaped": True,
            "samples": sample_records,
            "summary": summary,
        }
    finally:
        if not completed_normally:
            cleanup_owned_child(
                process,
                executable,
                timeout_seconds=termination_timeout_seconds,
                query=query,
                path_reader=path_reader,
                request_termination=request_termination,
            )
        if process.poll() is not None:
            entry = (process, executable)
            if entry in owned_processes:
                owned_processes.remove(entry)


def build_result(
    *,
    version: recovery.ReleaseVersion,
    release: engine.ReleaseInputs,
    artifact: dict[str, object],
    snapshot_files: dict[str, dict[str, object]],
    run: dict[str, object],
    preexisting_application_count: int,
) -> dict[str, object]:
    if (
        type(preexisting_application_count) is not int
        or preexisting_application_count < 0
    ):
        raise IdleResourceSmokeError(
            "preexisting application count is invalid"
        )
    validated_snapshot = validate_build24_snapshot_files(snapshot_files)
    archive_name = f"{release_id_for(version)}.zip"
    manifest_name = f"{release_id_for(version)}.manifest.json"
    if (
        release.archive_sha256
        != validated_snapshot[archive_name]["sha256"]
        or release.manifest_sha256
        != validated_snapshot[manifest_name]["sha256"]
    ):
        raise IdleResourceSmokeError(
            "loaded Build 24 release differs from the fixed snapshot"
        )
    if type(run) is not dict or set(run) != {
        "activationPolicy",
        "appKitProcessAbsentAfterReap",
        "exitCode",
        "finishedLaunching",
        "gracefulTerminationAccepted",
        "maximumObservedLatenessMilliseconds",
        "ownedChildProcess",
        "processIdentifierRetained",
        "processReaped",
        "samples",
        "summary",
    }:
        raise IdleResourceSmokeError(
            "idle resource run has an invalid closed schema"
        )
    if (
        type(run["activationPolicy"]) is not int
        or run["activationPolicy"] != 0
        or run["appKitProcessAbsentAfterReap"] is not True
        or type(run["exitCode"]) is not int
        or run["exitCode"] != 0
        or run["finishedLaunching"] is not True
        or run["gracefulTerminationAccepted"] is not True
        or type(run["maximumObservedLatenessMilliseconds"]) is not int
        or run["maximumObservedLatenessMilliseconds"] < 0
        or run["maximumObservedLatenessMilliseconds"]
        > SAMPLE_LATENESS_LIMIT_MILLISECONDS
        or run["ownedChildProcess"] is not True
        or run["processIdentifierRetained"] is not False
        or run["processReaped"] is not True
    ):
        raise IdleResourceSmokeError(
            "idle resource run did not finish its exact owned-child contract"
        )
    recomputed_summary = measurement_summary(
        run["samples"]  # type: ignore[arg-type]
    )
    if not exact_json_value_equal(
        recomputed_summary,
        run["summary"],
    ):
        raise IdleResourceSmokeError(
            "idle resource summary differs from retained samples"
        )
    os_version = platform.mac_ver()[0]
    architecture = platform.machine()
    logical_cpu_count = os.cpu_count()
    page_size = os.sysconf("SC_PAGE_SIZE")
    if (
        not os_version
        or not architecture
        or type(logical_cpu_count) is not int
        or logical_cpu_count <= 0
        or type(page_size) is not int
        or page_size <= 0
    ):
        raise IdleResourceSmokeError(
            "cannot determine the bounded macOS observation environment"
        )
    return {
        "archiveReadback": {
            "currentSourceCompared": False,
            "mode": (
                "fixed-identity-snapshot-no-current-source-"
                "no-signature-check"
            ),
            "readbackAndExerciseSameSnapshot": True,
            "signatureVerificationPerformed": False,
            "snapshotFiles": validated_snapshot,
            "snapshotFilesUnchangedAfterExercise": True,
            "status": "passed",
        },
        "artifact": artifact,
        "cleanup": {
            "ownedChildOnly": True,
            "preexistingApplicationsPreserved": True,
            "temporaryRootRemovedBeforePublication": True,
        },
        "environment": {
            "architecture": architecture,
            "logicalCpuCount": logical_cpu_count,
            "macOSVersion": os_version,
            "pageSizeBytes": page_size,
        },
        "isolation": {
            "afInetBindDeniedByPreflight": True,
            "networkDenied": True,
            "nonTemporaryWriteDeniedByPreflight": True,
            "profile": "allow-default-deny-network-and-non-temp-writes-v1",
            "sandboxed": True,
            "standardStreams": "devnull",
            "temporaryCFUserHomeConfigured": True,
        },
        "limitations": list(LIMITATIONS),
        "measurement": {
            "api": "macos-libproc-proc-pidinfo-v1",
            "baselineWindowSampleCount": (
                BASELINE_WINDOW_SAMPLE_COUNT
            ),
            "finalWindowSampleCount": FINAL_WINDOW_SAMPLE_COUNT,
            "intervalMilliseconds": SAMPLE_INTERVAL_MILLISECONDS,
            "run": run,
            "sampleCount": SAMPLE_COUNT,
            "sampleLatenessLimitMilliseconds": (
                SAMPLE_LATENESS_LIMIT_MILLISECONDS
            ),
            "status": "passed",
            "warmupMilliseconds": WARMUP_MILLISECONDS,
            "observationMilliseconds": OBSERVATION_MILLISECONDS,
        },
        "process": {
            "launchMethod": "sandbox-exec-direct-owned-child-v1",
            "preexistingApplicationCount": preexisting_application_count,
            "preexistingApplicationsUsedAsTerminationTargets": False,
            "rawProcessIdentifierRetained": False,
        },
        "release": {
            "archiveSha256": release.archive_sha256,
            "manifestSha256": release.manifest_sha256,
            "releaseId": release_id_for(version),
        },
        "repeatability": {
            "performed": False,
            "reason": "single-live-resource-observation-v1",
        },
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "status": "passed",
    }


def publish_result(path: Path, result: dict[str, object]) -> None:
    payload = engine.canonical_json_bytes(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if (
            path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == payload
        ):
            return
        raise IdleResourceSmokeError(
            f"refusing to replace different idle resource result: {path}"
        )
    temporary_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary_path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.read_bytes() != payload
            ):
                raise IdleResourceSmokeError(
                    "concurrent idle resource result publication differed"
                )
    finally:
        temporary_path.unlink(missing_ok=True)


def execute(
    *,
    archive_dir: Path,
    result_path: Path,
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
    termination_timeout_seconds: float = TERMINATION_TIMEOUT_SECONDS,
) -> dict[str, object]:
    readiness_timeout_seconds = engine.validated_duration(
        readiness_timeout_seconds,
        "readiness timeout",
        0.1,
        60.0,
    )
    termination_timeout_seconds = engine.validated_duration(
        termination_timeout_seconds,
        "termination timeout",
        0.1,
        30.0,
    )
    dmg.require_result_outside_archive(result_path, archive_dir)
    validate_libproc_abi()
    version = current_release()
    preexisting = installed.list_bundle_applications()
    temporary_root_path: Path | None = None

    with isolated_resource_root(
        termination_timeout_seconds=termination_timeout_seconds,
    ) as (temporary_root, owned_processes):
        temporary_root_path = temporary_root
        snapshot_directory, snapshot_files = (
            upgrade.snapshot_archive_directory(
                archive_dir,
                version=version,
                destination_parent=temporary_root / "archive-snapshot",
            )
        )
        validate_build24_snapshot_files(snapshot_files)
        release = recovery.load_release_inputs(
            snapshot_directory,
            verify_readback=False,
            version=version,
        )
        app_path = engine.extract_packaged_app(
            release,
            temporary_root / "extracted-app",
        )
        artifact = verify_extracted_app(
            app_path,
            release,
            version=version,
        )
        executable = app_path / engine.EXECUTABLE_RELATIVE_PATH

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
        ):
            path.mkdir(mode=0o700)
        identity_file = isolated_state / "runtime-identity.json"
        profile = engine.build_sandbox_profile(temporary_root)
        engine.preflight_sandbox(profile, temporary_root)
        environment = engine.isolated_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
        )
        run = run_owned_idle_observation(
            executable=executable,
            profile=profile,
            environment=environment,
            working_directory=temporary_root,
            readiness_timeout_seconds=readiness_timeout_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
            owned_processes=owned_processes,
        )
        final_tree = installed.app_tree_evidence(app_path, release).record()
        if final_tree != artifact["appTree"]:
            raise IdleResourceSmokeError(
                "Build 24 app tree changed during idle observation"
            )
        upgrade.require_unchanged_archive_snapshot(
            snapshot_directory,
            snapshot_files,
        )
        installed.assert_preexisting_applications_preserved(preexisting)

    if (
        temporary_root_path is None
        or temporary_root_path.exists()
        or temporary_root_path.is_symlink()
    ):
        raise IdleResourceSmokeError(
            "idle resource temporary root was not removed before publication"
        )
    result = build_result(
        version=version,
        release=release,
        artifact=artifact,
        snapshot_files=snapshot_files,
        run=run,
        preexisting_application_count=len(preexisting),
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
        default=READINESS_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=float,
        default=TERMINATION_TIMEOUT_SECONDS,
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = execute(
            archive_dir=arguments.archive_dir,
            result_path=arguments.result,
            readiness_timeout_seconds=(
                arguments.readiness_timeout_seconds
            ),
            termination_timeout_seconds=(
                arguments.termination_timeout_seconds
            ),
        )
    except (
        IdleResourceSmokeError,
        OSError,
        plistlib.InvalidFileException,
        ValueError,
    ) as error:
        print(
            f"Build 24 idle resource stability failed: {error}",
            file=sys.stderr,
        )
        return 1
    payload = engine.canonical_json_bytes(result)
    print(
        "Build 24 idle resource stability passed: "
        f"{len(payload)} bytes, SHA-256 "
        f"{hashlib.sha256(payload).hexdigest()}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
