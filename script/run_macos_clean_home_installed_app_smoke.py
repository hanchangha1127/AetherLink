#!/usr/bin/env python3
"""Exercise the current packaged macOS app as an isolated installed bundle."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable
from urllib.parse import quote
import zipfile

if __package__:
    from script import run_macos_packaged_app_state_recovery_smoke as recovery
else:
    import run_macos_packaged_app_state_recovery_smoke as recovery


engine = recovery.engine
ROOT = Path(__file__).resolve().parents[1]
DITTO = Path("/usr/bin/ditto")
OPEN = Path("/usr/bin/open")
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = "same-host-per-user-clean-home-launchservices-rehearsal-v1"
APP_MEMBER_PREFIX = engine.APP_MEMBER_PREFIX
APP_RELATIVE_PATH = engine.APP_RELATIVE_PATH
EXECUTABLE_RELATIVE_PATH = engine.EXECUTABLE_RELATIVE_PATH
EXPECTED_BUNDLE_ID = engine.EXPECTED_BUNDLE_ID
EXPECTED_SQLITE_FILES = engine.EXPECTED_ISOLATED_STATE_FILES
CHAT_DATABASE_FILENAME = "runtime-chat-events.sqlite"
TREE_DIGEST_ALGORITHM = (
    "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
)


LIST_BUNDLE_APPLICATIONS_JXA = r"""
ObjC.import("AppKit");
function run(argv) {
    const expectedBundleIdentifier = argv[0];
    const running = $.NSWorkspace.sharedWorkspace.runningApplications;
    const applications = [];
    const count = Number(running.count);
    for (let index = 0; index < count; index++) {
        const app = running.objectAtIndex(index);
        const bundleIdentifier = ObjC.unwrap(app.bundleIdentifier);
        if (bundleIdentifier !== expectedBundleIdentifier) {
            continue;
        }
        const executableURL = app.executableURL;
        if (executableURL.isNil()) {
            continue;
        }
        applications.push({
            activationPolicy: Number(app.activationPolicy),
            bundleIdentifier: bundleIdentifier,
            executablePath: ObjC.unwrap(executableURL.path),
            finishedLaunching: Boolean(app.finishedLaunching),
            pid: Number(app.processIdentifier)
        });
    }
    applications.sort((left, right) => left.pid - right.pid);
    return JSON.stringify({applications: applications});
}
"""


@dataclass(frozen=True)
class RunningApplication:
    activation_policy: int
    bundle_identifier: str
    executable_path: str
    finished_launching: bool
    pid: int


@dataclass(frozen=True)
class FileIdentity:
    mode: int
    sha256: str
    size: int


@dataclass(frozen=True)
class AppTreeEvidence:
    digest_algorithm: str
    file_count: int
    sha256: str
    total_bytes: int

    def record(self) -> dict[str, object]:
        return {
            "digestAlgorithm": self.digest_algorithm,
            "regularFileCount": self.file_count,
            "sha256": self.sha256,
            "totalRegularFileBytes": self.total_bytes,
        }


@dataclass(frozen=True)
class SQLiteStateEvidence:
    filename: str
    integrity_check: str
    total_event_count: int | None

    def record(self) -> dict[str, object]:
        result: dict[str, object] = {
            "filename": self.filename,
            "integrityCheck": self.integrity_check,
        }
        if self.total_event_count is not None:
            result["totalEventCount"] = self.total_event_count
        return result


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
            f"{version.build_number}-clean-home-install-v1.json"
        )
    )


def stable_regular_file_identity(path: Path) -> FileIdentity:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot open regular file {path}: {error}"
        ) from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise engine.LifecycleSmokeError(
                f"expected a regular file: {path}"
            )
        digest = hashlib.sha256()
        size = 0
        while True:
            payload = os.read(descriptor, 1024 * 1024)
            if not payload:
                break
            digest.update(payload)
            size += len(payload)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable_fields = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if stable_fields != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) or size != before.st_size:
        raise engine.LifecycleSmokeError(
            f"regular file changed while being read: {path}"
        )
    return FileIdentity(
        mode=stat.S_IMODE(before.st_mode),
        sha256=digest.hexdigest(),
        size=size,
    )


def app_file_records(
    app_path: Path,
) -> dict[str, FileIdentity]:
    if app_path.is_symlink() or not app_path.is_dir():
        raise engine.LifecycleSmokeError(
            f"installed app is not a real directory: {app_path}"
        )
    records: dict[str, FileIdentity] = {}
    for path in sorted(app_path.rglob("*")):
        if path.is_symlink():
            raise engine.LifecycleSmokeError(
                f"installed app contains a symbolic link: {path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise engine.LifecycleSmokeError(
                f"installed app contains a non-regular entry: {path}"
            )
        relative = path.relative_to(app_path).as_posix()
        member = APP_MEMBER_PREFIX + relative
        records[member] = stable_regular_file_identity(path)
    return records


def app_tree_evidence(
    app_path: Path,
    release: engine.ReleaseInputs,
) -> AppTreeEvidence:
    expected = {
        path: FileIdentity(mode=identity[2], sha256=identity[1], size=identity[0])
        for path, identity in engine.manifest_member_map(
            release.manifest
        ).items()
        if path.startswith(APP_MEMBER_PREFIX)
    }
    observed = app_file_records(app_path)
    if set(observed) != set(expected):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise engine.LifecycleSmokeError(
            "installed app regular-file set differs from the release "
            f"manifest; missing={missing!r}; extra={extra!r}"
        )
    for path, expected_identity in expected.items():
        if observed[path] != expected_identity:
            raise engine.LifecycleSmokeError(
                f"installed app identity differs for {path!r}"
            )

    digest = hashlib.sha256()
    total_bytes = 0
    for path in sorted(observed):
        identity = observed[path]
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{identity.mode:04o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(str(identity.size).encode("ascii"))
        digest.update(b"\0")
        digest.update(identity.sha256.encode("ascii"))
        digest.update(b"\n")
        total_bytes += identity.size
    return AppTreeEvidence(
        digest_algorithm=TREE_DIGEST_ALGORITHM,
        file_count=len(observed),
        sha256=digest.hexdigest(),
        total_bytes=total_bytes,
    )


def install_app_with_ditto(
    source: Path,
    destination: Path,
    *,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = (
        engine.run_checked
    ),
) -> None:
    if not DITTO.is_file() or not os.access(DITTO, os.X_OK):
        raise engine.LifecycleSmokeError("ditto is unavailable")
    if destination.exists() or destination.is_symlink():
        raise engine.LifecycleSmokeError(
            f"installation destination already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=False)
    command_runner([str(DITTO), str(source), str(destination)])
    if destination.is_symlink() or not destination.is_dir():
        raise engine.LifecycleSmokeError(
            "ditto did not create a real installed app directory"
        )


def isolated_launch_environment(
    base: dict[str, str],
    *,
    home: Path,
    temporary: Path,
    identity_file: Path,
) -> dict[str, str]:
    environment = {
        key: value
        for key, value in base.items()
        if not key.startswith("AETHERLINK_")
        and not key.startswith("DYLD_")
        and not key.startswith("LD_")
    }
    environment.update(
        {
            "AETHERLINK_RUNTIME_IDENTITY_FILE": str(identity_file),
            "CFFIXED_USER_HOME": str(home),
            "CFPREFERENCES_AVOID_DAEMON": "1",
            "HOME": str(home),
            "NSUnbufferedIO": "YES",
            "OS_ACTIVITY_MODE": "disable",
            "TMPDIR": str(temporary) + "/",
        }
    )
    return environment


def launch_services_command(
    app_path: Path,
    environment: dict[str, str],
) -> list[str]:
    app_text = str(app_path)
    if (
        not app_path.is_absolute()
        or app_path.suffix != ".app"
        or "\x00" in app_text
    ):
        raise engine.LifecycleSmokeError(
            "LaunchServices requires an absolute application-bundle path"
        )
    forwarded_keys = (
        "AETHERLINK_RUNTIME_IDENTITY_FILE",
        "CFFIXED_USER_HOME",
        "CFPREFERENCES_AVOID_DAEMON",
        "HOME",
        "NSUnbufferedIO",
        "OS_ACTIVITY_MODE",
        "TMPDIR",
    )
    command = [
        str(OPEN),
        "-n",
        "-F",
        "-g",
    ]
    for key in forwarded_keys:
        value = environment.get(key)
        if value is None or "\x00" in value:
            raise engine.LifecycleSmokeError(
                f"missing or invalid LaunchServices environment value {key}"
            )
        command.extend(("--env", f"{key}={value}"))
    command.append(app_text)
    return command


def parse_running_applications(payload: object) -> tuple[RunningApplication, ...]:
    if not isinstance(payload, dict):
        raise engine.LifecycleSmokeError(
            "LaunchServices application inventory must be an object"
        )
    rows = payload.get("applications")
    if not isinstance(rows, list):
        raise engine.LifecycleSmokeError(
            "LaunchServices application inventory must contain an array"
        )
    applications: list[RunningApplication] = []
    seen_pids: set[int] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise engine.LifecycleSmokeError(
                f"LaunchServices applications[{index}] must be an object"
            )
        activation_policy = row.get("activationPolicy")
        bundle_identifier = row.get("bundleIdentifier")
        executable_path = row.get("executablePath")
        finished_launching = row.get("finishedLaunching")
        pid = row.get("pid")
        if (
            type(activation_policy) is not int
            or not isinstance(bundle_identifier, str)
            or not isinstance(executable_path, str)
            or type(finished_launching) is not bool
            or type(pid) is not int
            or pid <= 0
        ):
            raise engine.LifecycleSmokeError(
                f"LaunchServices applications[{index}] has invalid fields"
            )
        if pid in seen_pids:
            raise engine.LifecycleSmokeError(
                f"LaunchServices application inventory repeats PID {pid}"
            )
        seen_pids.add(pid)
        applications.append(
            RunningApplication(
                activation_policy=activation_policy,
                bundle_identifier=bundle_identifier,
                executable_path=executable_path,
                finished_launching=finished_launching,
                pid=pid,
            )
        )
    return tuple(sorted(applications, key=lambda application: application.pid))


def list_bundle_applications() -> tuple[RunningApplication, ...]:
    payload = engine.run_jxa(
        LIST_BUNDLE_APPLICATIONS_JXA,
        [EXPECTED_BUNDLE_ID],
    )
    applications = parse_running_applications(payload)
    if any(
        application.bundle_identifier != EXPECTED_BUNDLE_ID
        for application in applications
    ):
        raise engine.LifecycleSmokeError(
            "LaunchServices inventory returned an unexpected bundle identifier"
        )
    return applications


def application_matches_executable(
    application: RunningApplication,
    executable: Path,
) -> bool:
    return (
        application.bundle_identifier == EXPECTED_BUNDLE_ID
        and Path(application.executable_path).resolve() == executable.resolve()
    )


def wait_for_new_application(
    *,
    executable: Path,
    preexisting_pids: set[int],
    timeout_seconds: float,
    lister: Callable[[], tuple[RunningApplication, ...]] = (
        list_bundle_applications
    ),
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> RunningApplication:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        matches = [
            application
            for application in lister()
            if application.pid not in preexisting_pids
            and application_matches_executable(application, executable)
        ]
        if len(matches) > 1:
            raise engine.LifecycleSmokeError(
                "LaunchServices created multiple new exact-path app instances"
            )
        if matches:
            application = matches[0]
            if application.finished_launching:
                if application.activation_policy != 0:
                    raise engine.LifecycleSmokeError(
                        "installed app did not enter regular activation policy"
                    )
                return application
        remaining = max(0.0, deadline - monotonic())
        sleeper(min(0.1, remaining))
    raise engine.LifecycleSmokeError(
        "LaunchServices exact-path app readiness timed out"
    )


def assert_query_identity(
    status: engine.ApplicationStatus | None,
    executable: Path,
) -> engine.ApplicationStatus:
    if status is None:
        raise engine.LifecycleSmokeError(
            "LaunchServices app disappeared before termination"
        )
    if (
        status.bundle_identifier != EXPECTED_BUNDLE_ID
        or Path(status.executable_path).resolve() != executable.resolve()
    ):
        raise engine.LifecycleSmokeError(
            "LaunchServices PID no longer matches the installed app"
        )
    return status


def wait_until_application_gone(
    pid: int,
    *,
    timeout_seconds: float,
    query: Callable[[int], engine.ApplicationStatus | None] = (
        engine.query_application
    ),
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if query(pid) is None:
            return True
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    return query(pid) is None


def terminate_exact_application(
    pid: int,
    executable: Path,
    *,
    timeout_seconds: float,
    query: Callable[[int], engine.ApplicationStatus | None] = (
        engine.query_application
    ),
    requester: Callable[..., bool] = engine.request_application_termination,
) -> bool:
    assert_query_identity(query(pid), executable)
    accepted = requester(pid, executable, force=False)
    if not accepted:
        raise engine.LifecycleSmokeError(
            "installed app rejected exact-PID graceful termination"
        )
    if not wait_until_application_gone(
        pid,
        timeout_seconds=timeout_seconds,
        query=query,
    ):
        raise engine.LifecycleSmokeError(
            "installed app did not terminate within the graceful deadline"
        )
    return True


def force_cleanup_exact_application(
    application: RunningApplication,
    executable: Path,
    *,
    timeout_seconds: float,
) -> None:
    status = engine.query_application(application.pid)
    if status is None:
        return
    assert_query_identity(status, executable)
    accepted = engine.request_application_termination(
        application.pid,
        executable,
        force=True,
    )
    if not accepted or not wait_until_application_gone(
        application.pid,
        timeout_seconds=timeout_seconds,
    ):
        raise engine.LifecycleSmokeError(
            "could not clean up the exact installed app instance"
        )


def run_launch_services_cycle(
    *,
    ordinal: int,
    app_path: Path,
    environment: dict[str, str],
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> tuple[int, dict[str, object]]:
    executable = app_path / EXECUTABLE_RELATIVE_PATH
    before = list_bundle_applications()
    preexisting_pids = {application.pid for application in before}
    if any(
        application_matches_executable(application, executable)
        for application in before
    ):
        raise engine.LifecycleSmokeError(
            "the isolated installed app path is already running"
        )
    if not OPEN.is_file() or not os.access(OPEN, os.X_OK):
        raise engine.LifecycleSmokeError("open is unavailable")

    launched: RunningApplication | None = None
    try:
        engine.run_checked(
            launch_services_command(app_path, environment),
            cwd=app_path.parent,
            environment=environment,
        )
        launched = wait_for_new_application(
            executable=executable,
            preexisting_pids=preexisting_pids,
            timeout_seconds=readiness_timeout_seconds,
        )
        observation_deadline = time.monotonic() + observation_seconds
        while time.monotonic() < observation_deadline:
            status = assert_query_identity(
                engine.query_application(launched.pid),
                executable,
            )
            if not status.finished_launching:
                raise engine.LifecycleSmokeError(
                    "installed app lost its finished-launching state"
                )
            time.sleep(
                min(
                    0.1,
                    max(0.0, observation_deadline - time.monotonic()),
                )
            )
        termination_accepted = terminate_exact_application(
            launched.pid,
            executable,
            timeout_seconds=termination_timeout_seconds,
        )
        return (
            launched.pid,
            {
                "activationPolicy": launched.activation_policy,
                "executablePathMatched": True,
                "finishedLaunching": launched.finished_launching,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": termination_accepted,
            },
        )
    finally:
        remaining = [
            application
            for application in list_bundle_applications()
            if application.pid not in preexisting_pids
            and application_matches_executable(application, executable)
        ]
        for application in remaining:
            force_cleanup_exact_application(
                application,
                executable,
                timeout_seconds=termination_timeout_seconds,
            )


def sqlite_state_evidence(
    application_support: Path,
) -> tuple[SQLiteStateEvidence, ...]:
    evidence: list[SQLiteStateEvidence] = []
    for filename in EXPECTED_SQLITE_FILES:
        database_path = application_support / filename
        if database_path.is_symlink() or not database_path.is_file():
            raise engine.LifecycleSmokeError(
                f"installed app did not initialize {filename}"
            )
        database_uri = (
            "file:"
            + quote(str(database_path.resolve()), safe="/")
            + "?mode=ro"
        )
        try:
            connection = sqlite3.connect(database_uri, uri=True, timeout=5)
            try:
                connection.execute("PRAGMA query_only = ON")
                integrity_rows = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchall()
                total_event_count: int | None = None
                if filename == CHAT_DATABASE_FILENAME:
                    row = connection.execute(
                        "SELECT COUNT(*) FROM runtime_chat_events"
                    ).fetchone()
                    if (
                        row is None
                        or len(row) != 1
                        or type(row[0]) is not int
                    ):
                        raise engine.LifecycleSmokeError(
                            "runtime-chat event count has an invalid shape"
                        )
                    total_event_count = row[0]
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise engine.LifecycleSmokeError(
                f"SQLite readback failed for {filename}: {error}"
            ) from error
        if integrity_rows != [("ok",)]:
            raise engine.LifecycleSmokeError(
                f"SQLite integrity_check failed for {filename}"
            )
        if (
            filename == CHAT_DATABASE_FILENAME
            and total_event_count != 0
        ):
            raise engine.LifecycleSmokeError(
                "clean-HOME runtime-chat database is not empty"
            )
        evidence.append(
            SQLiteStateEvidence(
                filename=filename,
                integrity_check="ok",
                total_event_count=total_event_count,
            )
        )
    return tuple(evidence)


def state_file_records(
    application_support: Path,
    identity_file: Path,
) -> dict[str, FileIdentity]:
    if application_support.is_symlink() or not application_support.is_dir():
        raise engine.LifecycleSmokeError(
            "isolated AetherLink Application Support directory is missing"
        )
    records: dict[str, FileIdentity] = {}
    for path in sorted(application_support.rglob("*")):
        if path.is_symlink():
            raise engine.LifecycleSmokeError(
                f"isolated runtime state contains a symbolic link: {path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise engine.LifecycleSmokeError(
                f"isolated runtime state contains a non-regular entry: {path}"
            )
        relative = path.relative_to(application_support).as_posix()
        records[f"application-support/{relative}"] = (
            stable_regular_file_identity(path)
        )
    if identity_file.exists() or identity_file.is_symlink():
        if identity_file.is_symlink() or not identity_file.is_file():
            raise engine.LifecycleSmokeError(
                "isolated runtime identity is not a regular file"
            )
        records["runtime-identity.json"] = stable_regular_file_identity(
            identity_file
        )
    return records


def assert_preexisting_applications_preserved(
    before: tuple[RunningApplication, ...],
) -> None:
    for application in before:
        status = engine.query_application(application.pid)
        if status is None:
            raise engine.LifecycleSmokeError(
                "a pre-existing AetherLink application exited during the smoke"
            )
        if (
            status.bundle_identifier != application.bundle_identifier
            or Path(status.executable_path).resolve()
            != Path(application.executable_path).resolve()
        ):
            raise engine.LifecycleSmokeError(
                "a pre-existing AetherLink application identity changed"
            )


def publish_result(path: Path, result: dict[str, object]) -> None:
    payload = engine.canonical_json_bytes(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_file() and not path.is_symlink() and path.read_bytes() == payload:
            return
        raise engine.LifecycleSmokeError(
            f"refusing to replace different clean-HOME result bytes: {path}"
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
                raise engine.LifecycleSmokeError(
                    "concurrent clean-HOME result publication differed"
                )
    finally:
        temporary_path.unlink(missing_ok=True)


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
    preexisting_applications = list_bundle_applications()

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-clean-home-install-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        extracted_app = engine.extract_packaged_app(
            release,
            temporary_root / "extracted-app",
        )
        recovery.verify_packaged_app(
            extracted_app,
            release,
            version=version,
        )
        extracted_tree = app_tree_evidence(extracted_app, release)

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        for path in (isolated_home, isolated_temporary, isolated_state):
            path.mkdir(mode=0o700)
        installed_app = isolated_home / "Applications" / APP_RELATIVE_PATH
        install_app_with_ditto(extracted_app, installed_app)
        app_metadata = recovery.verify_packaged_app(
            installed_app,
            release,
            version=version,
        )
        installed_tree = app_tree_evidence(installed_app, release)
        if installed_tree != extracted_tree:
            raise engine.LifecycleSmokeError(
                "installed app tree differs from the extracted release app"
            )

        identity_file = isolated_state / "runtime-identity.json"
        environment = isolated_launch_environment(
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
            raise engine.LifecycleSmokeError(
                "clean-HOME runtime state existed before the first launch"
            )

        first_pid, first_run = run_launch_services_cycle(
            ordinal=1,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        first_tree = app_tree_evidence(installed_app, release)
        first_sqlite = sqlite_state_evidence(application_support)
        first_state = state_file_records(
            application_support,
            identity_file,
        )

        second_pid, second_run = run_launch_services_cycle(
            ordinal=2,
            app_path=installed_app,
            environment=environment,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if second_pid == first_pid:
            raise engine.LifecycleSmokeError(
                "LaunchServices relaunch reused the prior process identifier"
            )
        second_tree = app_tree_evidence(installed_app, release)
        second_sqlite = sqlite_state_evidence(application_support)
        second_state = state_file_records(
            application_support,
            identity_file,
        )
        if (
            first_tree != installed_tree
            or second_tree != installed_tree
        ):
            raise engine.LifecycleSmokeError(
                "installed app bytes or modes changed during launch/relaunch"
            )
        if second_sqlite != first_sqlite:
            raise engine.LifecycleSmokeError(
                "SQLite empty-state evidence changed across relaunch"
            )
        if second_state != first_state:
            changed = sorted(
                set(first_state)
                ^ set(second_state)
                | {
                    path
                    for path in set(first_state) & set(second_state)
                    if first_state[path] != second_state[path]
                }
            )
            raise engine.LifecycleSmokeError(
                "isolated runtime state changed across relaunch: "
                f"{changed!r}"
            )

        assert_preexisting_applications_preserved(preexisting_applications)
        result = {
            "app": app_metadata,
            "installation": {
                "codesignVerified": True,
                "copyTool": "ditto",
                "installedRelativePath": "Applications/AetherLink.app",
                "regularFileTreeMatchesReleaseManifest": True,
                "tree": installed_tree.record(),
            },
            "isolation": {
                "cleanHomeConfigured": True,
                "preexistingBundleApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "launchServices": {
                "commandPolicy": (
                    "open-new-fresh-background-exact-app-path-v1"
                ),
                "distinctProcessIdentifiers": True,
                "runs": [first_run, second_run],
            },
            "limitations": [
                "same-host-per-user-rehearsal-only",
                "not-a-clean-machine-or-dmg-installation",
                "not-developer-id-notarization-or-signed-distribution",
                "not-physical-device-or-live-provider-evidence",
            ],
            "release": {
                "archiveSha256": release.archive_sha256,
                "manifestSha256": release.manifest_sha256,
                "releaseId": release_id,
            },
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "scope": RESULT_SCOPE,
            "state": {
                "expectedSQLiteFiles": list(EXPECTED_SQLITE_FILES),
                "regularFileBytesAndModesUnchangedAcrossRelaunch": True,
                "runtimeIdentityFilePresent": identity_file.is_file(),
                "sqlite": [
                    evidence.record() for evidence in first_sqlite
                ],
            },
            "status": "passed",
        }

    publish_result(result_path, result)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
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
        type=lambda value: engine.bounded_float(
            value,
            "readiness timeout",
            0.1,
            60,
        ),
        default=20.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "observation window",
            engine.MINIMUM_OBSERVATION_SECONDS,
            30,
        ),
        default=engine.MINIMUM_OBSERVATION_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "termination timeout",
            0.1,
            30,
        ),
        default=10.0,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = execute(
            archive_dir=arguments.archive_dir,
            result_path=arguments.result,
            readiness_timeout_seconds=arguments.readiness_timeout_seconds,
            observation_seconds=arguments.observation_seconds,
            termination_timeout_seconds=arguments.termination_timeout_seconds,
        )
    except KeyboardInterrupt:
        print(
            "macOS clean-HOME installed-app smoke interrupted.",
            file=sys.stderr,
        )
        return 130
    except (
        engine.LifecycleSmokeError,
        OSError,
        sqlite3.Error,
        zipfile.BadZipFile,
    ) as error:
        print(
            f"macOS clean-HOME installed-app smoke failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "macOS clean-HOME installed-app smoke passed: "
        f"{result['release']['releaseId']}; "
        "LaunchServices launch/relaunch and empty state preserved."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
