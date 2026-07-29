#!/usr/bin/env python3
"""Run an isolated launch, terminate, and relaunch smoke on a packaged macOS app."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RELEASE_ID = "aetherlink-1.0.0+9-local-v1"
EXPECTED_MARKETING_VERSION = "1.0.0"
EXPECTED_BUILD_NUMBER = 9
EXPECTED_BUNDLE_ID = "dev.aetherlink.companion"
EXPECTED_ARCHIVE_SHA256 = (
    "e2cbd350bf031d04b6e29054ceb387bbe453e60244b47919c54f6d3c13ba7e1a"
)
EXPECTED_MANIFEST_SHA256 = (
    "56380c239f916ba9d400cc73824ebbda111f61e0baa4d0dc66e8d14e044d05a5"
)
DEFAULT_ARCHIVE_DIR = ROOT / "dist/releases" / EXPECTED_RELEASE_ID
DEFAULT_RESULT = (
    ROOT
    / "dist/lifecycle"
    / "macos-packaged-app-build-9-lifecycle-v1.json"
)
ARCHIVE_CHECKER = ROOT / "script/check_release_artifact_archive.py"
SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
OSASCRIPT = Path("/usr/bin/osascript")
PLUTIL = Path("/usr/bin/plutil")
CODESIGN = Path("/usr/bin/codesign")
APP_MEMBER_PREFIX = "macos/AetherLink.app/"
APP_RELATIVE_PATH = Path("AetherLink.app")
EXECUTABLE_RELATIVE_PATH = Path("Contents/MacOS/AetherLink")
INFO_PLIST_RELATIVE_PATH = Path("Contents/Info.plist")
EXPECTED_ISOLATED_STATE_FILES = (
    "runtime-chat-events.sqlite",
    "runtime-document-index.sqlite",
    "runtime-model-pull-approvals.sqlite",
)
RESULT_SCHEMA_VERSION = 1
MINIMUM_OBSERVATION_SECONDS = 5.0


class LifecycleSmokeError(RuntimeError):
    """Raised when the packaged-app lifecycle contract is not satisfied."""


class DuplicateJSONKeyError(ValueError):
    """Raised when strict JSON parsing sees a duplicate key."""


@dataclass(frozen=True)
class ReleaseInputs:
    archive_dir: Path
    archive_path: Path
    manifest_path: Path
    checksum_path: Path
    archive_sha256: str
    manifest_sha256: str
    manifest: dict[str, object]


@dataclass(frozen=True)
class ApplicationStatus:
    activation_policy: int
    bundle_identifier: str
    executable_path: str
    finished_launching: bool


@dataclass(frozen=True)
class LifecycleRunResult:
    activation_policy: int
    exit_code: int
    finished_launching: bool
    minimum_observation_seconds: float
    ordinal: int
    observation_deadline_reached: bool
    termination_accepted: bool


STATUS_JXA = r"""
ObjC.import("AppKit");
function run(argv) {
    const pid = Number(argv[0]);
    if (!Number.isInteger(pid) || pid <= 0) {
        throw new Error("invalid pid");
    }
    const app = $.NSRunningApplication.runningApplicationWithProcessIdentifier(pid);
    if (app.isNil()) {
        return JSON.stringify({found: false});
    }
    return JSON.stringify({
        activationPolicy: Number(app.activationPolicy),
        bundleIdentifier: ObjC.unwrap(app.bundleIdentifier),
        executablePath: ObjC.unwrap(app.executableURL.path),
        finishedLaunching: Boolean(app.finishedLaunching),
        found: true
    });
}
"""


TERMINATE_JXA = r"""
ObjC.import("AppKit");
function run(argv) {
    const pid = Number(argv[0]);
    const force = argv[1] === "force";
    const expectedExecutablePath = argv[2];
    const expectedBundleIdentifier = argv[3];
    if (!Number.isInteger(pid) || pid <= 0) {
        throw new Error("invalid pid");
    }
    const app = $.NSRunningApplication.runningApplicationWithProcessIdentifier(pid);
    if (app.isNil()) {
        return JSON.stringify({
            accepted: false,
            found: false,
            identityMatched: false
        });
    }
    const executablePath = ObjC.unwrap(app.executableURL.path);
    const bundleIdentifier = ObjC.unwrap(app.bundleIdentifier);
    const identityMatched = (
        executablePath === expectedExecutablePath
        && bundleIdentifier === expectedBundleIdentifier
    );
    if (!identityMatched) {
        return JSON.stringify({
            accepted: false,
            found: true,
            identityMatched: false
        });
    }
    const accepted = force ? Boolean(app.forceTerminate) : Boolean(app.terminate);
    return JSON.stringify({
        accepted: accepted,
        found: true,
        identityMatched: true
    });
}
"""


SANDBOX_PREFLIGHT_SCRIPT = r"""
from pathlib import Path
import socket
import sys

inside = Path(sys.argv[1])
outside = Path(sys.argv[2])
inside.write_bytes(b"inside")
try:
    outside.write_bytes(b"outside")
except OSError:
    pass
else:
    outside.unlink(missing_ok=True)
    raise SystemExit("sandbox allowed a write outside the temporary root")

probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    probe.bind(("127.0.0.1", 0))
except OSError:
    pass
else:
    raise SystemExit("sandbox allowed an AF_INET bind")
finally:
    probe.close()
"""


def reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def strict_json_loads(payload: bytes, label: str) -> object:
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        raise LifecycleSmokeError(f"{label}: invalid JSON: {error}") from error


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_output(completed: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(
        part.strip()
        for part in (completed.stdout or "", completed.stderr or "")
        if part.strip()
    )
    return combined[-4_000:]


def run_checked(
    command: list[str],
    *,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise LifecycleSmokeError(
            f"command timed out after 60 seconds: {' '.join(command)}"
        ) from error
    if completed.returncode != 0:
        rendered = " ".join(command)
        detail = bounded_output(completed)
        raise LifecycleSmokeError(
            f"command failed ({completed.returncode}): {rendered}"
            + (f"\n{detail}" if detail else "")
        )
    return completed


def verify_archive_readback(archive_dir: Path) -> None:
    run_checked(
        [
            sys.executable,
            "-B",
            str(ARCHIVE_CHECKER),
            "--archive-dir",
            str(archive_dir),
        ],
        cwd=ROOT,
    )


def load_release_inputs(
    archive_dir: Path,
    *,
    verify_readback: bool = True,
) -> ReleaseInputs:
    archive_dir = archive_dir.resolve()
    if not archive_dir.is_dir():
        raise LifecycleSmokeError(
            f"release archive directory is missing: {archive_dir}"
        )
    if archive_dir.name != EXPECTED_RELEASE_ID:
        raise LifecycleSmokeError(
            f"expected release directory {EXPECTED_RELEASE_ID!r}, "
            f"found {archive_dir.name!r}"
        )

    archive_path = archive_dir / f"{EXPECTED_RELEASE_ID}.zip"
    manifest_path = archive_dir / f"{EXPECTED_RELEASE_ID}.manifest.json"
    checksum_path = archive_dir / f"{EXPECTED_RELEASE_ID}.zip.sha256"
    for path in (archive_path, manifest_path, checksum_path):
        if not path.is_file():
            raise LifecycleSmokeError(f"missing release input: {path}")

    if verify_readback:
        verify_archive_readback(archive_dir)

    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = sha256_bytes(manifest_bytes)
    if manifest_sha256 != EXPECTED_MANIFEST_SHA256:
        raise LifecycleSmokeError(
            "release manifest does not match the qualified Build 9 identity"
        )
    manifest = strict_json_loads(manifest_bytes, str(manifest_path))
    if not isinstance(manifest, dict):
        raise LifecycleSmokeError("release manifest root must be an object")

    release = manifest.get("release")
    if not isinstance(release, dict):
        raise LifecycleSmokeError("release manifest is missing release metadata")
    expected_release = {
        "buildNumber": EXPECTED_BUILD_NUMBER,
        "marketingVersion": EXPECTED_MARKETING_VERSION,
        "releaseId": EXPECTED_RELEASE_ID,
    }
    actual_release = {
        key: release.get(key)
        for key in expected_release
    }
    if any(
        type(actual_release[key]) is not type(expected)
        or actual_release[key] != expected
        for key, expected in expected_release.items()
    ):
        raise LifecycleSmokeError(
            f"unexpected release metadata: {actual_release!r}"
        )

    try:
        checksum_fields = checksum_path.read_text(encoding="ascii").split()
    except (OSError, UnicodeError) as error:
        raise LifecycleSmokeError(
            f"release checksum sidecar is unreadable: {error}"
        ) from error
    if (
        len(checksum_fields) != 2
        or checksum_fields[1] != archive_path.name
        or len(checksum_fields[0]) != 64
        or any(character not in "0123456789abcdef" for character in checksum_fields[0])
    ):
        raise LifecycleSmokeError("release checksum sidecar is malformed")
    archive_sha256 = checksum_fields[0]
    if sha256_file(archive_path) != archive_sha256:
        raise LifecycleSmokeError("release ZIP differs from its checksum sidecar")
    if archive_sha256 != EXPECTED_ARCHIVE_SHA256:
        raise LifecycleSmokeError(
            "release ZIP does not match the qualified Build 9 identity"
        )

    return ReleaseInputs(
        archive_dir=archive_dir,
        archive_path=archive_path,
        manifest_path=manifest_path,
        checksum_path=checksum_path,
        archive_sha256=archive_sha256,
        manifest_sha256=manifest_sha256,
        manifest=manifest,
    )


def manifest_member_map(
    manifest: dict[str, object],
) -> dict[str, tuple[int, str, int]]:
    rows = manifest.get("members")
    if not isinstance(rows, list):
        raise LifecycleSmokeError("release manifest members must be an array")
    members: dict[str, tuple[int, str, int]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise LifecycleSmokeError(
                f"release manifest members[{index}] must be an object"
            )
        path = row.get("path")
        size = row.get("size")
        digest = row.get("sha256")
        mode_text = row.get("mode")
        if (
            not isinstance(path, str)
            or type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(mode_text, str)
            or len(mode_text) != 4
            or mode_text[0] != "0"
            or any(character not in "01234567" for character in mode_text)
        ):
            raise LifecycleSmokeError(
                f"release manifest members[{index}] has invalid identity fields"
            )
        if path in members:
            raise LifecycleSmokeError(
                f"release manifest contains duplicate member {path!r}"
            )
        members[path] = (size, digest, int(mode_text, 8))
    return members


def validate_zip_member_name(name: str) -> PurePosixPath:
    if not name or "\x00" in name or "\\" in name:
        raise LifecycleSmokeError(f"unsafe ZIP member name {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise LifecycleSmokeError(f"unsafe ZIP member path {name!r}")
    return path


def extract_packaged_app(
    release: ReleaseInputs,
    destination: Path,
) -> Path:
    expected_members = {
        path: identity
        for path, identity in manifest_member_map(release.manifest).items()
        if path.startswith(APP_MEMBER_PREFIX)
    }
    if not expected_members:
        raise LifecycleSmokeError("release manifest contains no packaged macOS app")

    destination.mkdir(parents=True, exist_ok=False)
    observed_members: dict[str, tuple[int, str, int]] = {}
    seen_names: set[str] = set()
    with zipfile.ZipFile(release.archive_path, "r") as archive:
        for info in archive.infolist():
            validate_zip_member_name(info.filename)
            if info.filename in seen_names:
                raise LifecycleSmokeError(
                    f"release ZIP contains duplicate member {info.filename!r}"
                )
            seen_names.add(info.filename)
            if not info.filename.startswith(APP_MEMBER_PREFIX):
                continue
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_ISDIR(mode):
                raise LifecycleSmokeError(
                    f"packaged app contains unexpected directory entry "
                    f"{info.filename!r}"
                )
            if stat.S_ISLNK(mode) or (
                stat.S_IFMT(mode) not in (0, stat.S_IFREG)
            ):
                raise LifecycleSmokeError(
                    f"packaged app member is not a regular file: "
                    f"{info.filename!r}"
                )
            relative = PurePosixPath(
                info.filename.removeprefix(APP_MEMBER_PREFIX)
            )
            if not relative.parts:
                raise LifecycleSmokeError("packaged app member path is empty")
            payload = archive.read(info)
            identity = (len(payload), sha256_bytes(payload), mode & 0o7777)
            observed_members[info.filename] = identity
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            target.chmod(identity[2])

    if set(observed_members) != set(expected_members):
        missing = sorted(set(expected_members) - set(observed_members))
        extra = sorted(set(observed_members) - set(expected_members))
        raise LifecycleSmokeError(
            f"packaged app member set mismatch; missing={missing!r}; "
            f"extra={extra!r}"
        )
    for path, expected in expected_members.items():
        actual = observed_members[path]
        if actual != expected:
            raise LifecycleSmokeError(
                f"packaged app member identity mismatch for {path!r}: "
                f"expected {expected!r}, found {actual!r}"
            )

    app_path = destination.parent / APP_RELATIVE_PATH
    destination.rename(app_path)
    return app_path


def verify_packaged_app(
    app_path: Path,
    release: ReleaseInputs,
) -> dict[str, object]:
    info_plist = app_path / INFO_PLIST_RELATIVE_PATH
    executable = app_path / EXECUTABLE_RELATIVE_PATH
    if not info_plist.is_file() or not executable.is_file():
        raise LifecycleSmokeError("extracted app is missing Info.plist or executable")
    if not os.access(executable, os.X_OK):
        raise LifecycleSmokeError("extracted app executable is not executable")

    try:
        plist = plistlib.loads(info_plist.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise LifecycleSmokeError(f"invalid packaged Info.plist: {error}") from error
    expected_plist = {
        "CFBundleIdentifier": EXPECTED_BUNDLE_ID,
        "CFBundleShortVersionString": EXPECTED_MARKETING_VERSION,
        "CFBundleVersion": str(EXPECTED_BUILD_NUMBER),
    }
    for key, expected in expected_plist.items():
        actual = plist.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise LifecycleSmokeError(
                f"expected Info.plist {key}={expected!r}, found {actual!r}"
            )

    run_checked(
        [
            str(CODESIGN),
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app_path),
        ]
    )
    for key, expected in (
        ("CFBundleShortVersionString", EXPECTED_MARKETING_VERSION),
        ("CFBundleVersion", str(EXPECTED_BUILD_NUMBER)),
    ):
        completed = run_checked(
            [
                str(PLUTIL),
                "-extract",
                key,
                "raw",
                str(info_plist),
            ]
        )
        if completed.stdout.strip() != expected:
            raise LifecycleSmokeError(
                f"plutil expected {key}={expected!r}, "
                f"found {completed.stdout.strip()!r}"
            )

    members = manifest_member_map(release.manifest)
    executable_member = APP_MEMBER_PREFIX + EXECUTABLE_RELATIVE_PATH.as_posix()
    expected_executable = members.get(executable_member)
    if expected_executable is None:
        raise LifecycleSmokeError("manifest is missing the macOS executable")
    if (
        executable.stat().st_size,
        sha256_file(executable),
        stat.S_IMODE(executable.stat().st_mode),
    ) != expected_executable:
        raise LifecycleSmokeError(
            "extracted macOS executable differs from the release manifest"
        )

    platforms = release.manifest.get("platforms")
    macos = platforms.get("macos") if isinstance(platforms, dict) else None
    if not isinstance(macos, dict):
        raise LifecycleSmokeError("release manifest is missing macOS metadata")
    uuid = macos.get("uuid")
    if not isinstance(uuid, str) or not uuid:
        raise LifecycleSmokeError("release manifest has no macOS UUID")
    return {
        "bundleIdentifier": EXPECTED_BUNDLE_ID,
        "buildNumber": EXPECTED_BUILD_NUMBER,
        "executableSha256": expected_executable[1],
        "marketingVersion": EXPECTED_MARKETING_VERSION,
        "uuid": uuid,
    }


def sandbox_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_sandbox_profile(temporary_root: Path) -> str:
    canonical_root = temporary_root.resolve()
    return "\n".join(
        (
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            (
                "(allow file-write* (subpath "
                f"{sandbox_string(str(canonical_root))}))"
            ),
        )
    )


def isolated_environment(
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


def preflight_sandbox(profile: str, cwd: Path) -> None:
    if not SANDBOX_EXEC.is_file() or not os.access(SANDBOX_EXEC, os.X_OK):
        raise LifecycleSmokeError(
            "sandbox-exec is unavailable; refusing an unisolated lifecycle run"
        )
    inside_probe = cwd / ".sandbox-write-probe"
    outside_probe = (
        cwd.parent / f".aetherlink-sandbox-outside-probe-{os.getpid()}"
    )
    if inside_probe.exists() or outside_probe.exists():
        raise LifecycleSmokeError("sandbox preflight probe path already exists")
    try:
        run_checked(
            [
                str(SANDBOX_EXEC),
                "-p",
                profile,
                sys.executable,
                "-B",
                "-c",
                SANDBOX_PREFLIGHT_SCRIPT,
                str(inside_probe),
                str(outside_probe),
            ],
            cwd=cwd,
        )
        if not inside_probe.is_file():
            raise LifecycleSmokeError(
                "sandbox preflight did not permit the temporary-root write"
            )
        if outside_probe.exists():
            raise LifecycleSmokeError(
                "sandbox preflight wrote outside the temporary root"
            )
    finally:
        inside_probe.unlink(missing_ok=True)
        outside_probe.unlink(missing_ok=True)


def run_jxa(script: str, arguments: list[str]) -> dict[str, object]:
    if not OSASCRIPT.is_file() or not os.access(OSASCRIPT, os.X_OK):
        raise LifecycleSmokeError("osascript is unavailable")
    completed = run_checked(
        [
            str(OSASCRIPT),
            "-l",
            "JavaScript",
            "-e",
            script,
            *arguments,
        ]
    )
    payload = strict_json_loads(
        completed.stdout.strip().encode("utf-8"),
        "AppKit lifecycle probe",
    )
    if not isinstance(payload, dict):
        raise LifecycleSmokeError("AppKit lifecycle probe result must be an object")
    return payload


def query_application(pid: int) -> ApplicationStatus | None:
    payload = run_jxa(STATUS_JXA, [str(pid)])
    found = payload.get("found")
    if type(found) is not bool:
        raise LifecycleSmokeError("AppKit lifecycle probe has invalid found flag")
    if not found:
        return None
    activation_policy = payload.get("activationPolicy")
    bundle_identifier = payload.get("bundleIdentifier")
    executable_path = payload.get("executablePath")
    finished_launching = payload.get("finishedLaunching")
    if (
        type(activation_policy) is not int
        or not isinstance(bundle_identifier, str)
        or not isinstance(executable_path, str)
        or type(finished_launching) is not bool
    ):
        raise LifecycleSmokeError(
            "AppKit lifecycle probe has invalid status field types"
        )
    return ApplicationStatus(
        activation_policy=activation_policy,
        bundle_identifier=bundle_identifier,
        executable_path=executable_path,
        finished_launching=finished_launching,
    )


def request_application_termination(
    pid: int,
    executable: Path,
    *,
    force: bool,
) -> bool:
    payload = run_jxa(
        TERMINATE_JXA,
        [
            str(pid),
            "force" if force else "graceful",
            str(executable.resolve()),
            EXPECTED_BUNDLE_ID,
        ],
    )
    found = payload.get("found")
    accepted = payload.get("accepted")
    identity_matched = payload.get("identityMatched")
    if (
        type(found) is not bool
        or type(accepted) is not bool
        or type(identity_matched) is not bool
    ):
        raise LifecycleSmokeError(
            "AppKit termination probe has invalid result field types"
        )
    if found and not identity_matched:
        raise LifecycleSmokeError(
            "refusing to terminate a PID whose app identity no longer matches"
        )
    return found and accepted


def wait_for_application_readiness(
    process: subprocess.Popen[bytes],
    executable: Path,
    *,
    timeout_seconds: float,
    query: Callable[[int], ApplicationStatus | None] = query_application,
) -> ApplicationStatus:
    deadline = time.monotonic() + timeout_seconds
    expected_executable = executable.resolve()
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise LifecycleSmokeError(
                f"packaged app exited before readiness with code {exit_code}"
            )
        status = query(process.pid)
        if status is not None:
            if status.bundle_identifier != EXPECTED_BUNDLE_ID:
                raise LifecycleSmokeError(
                    "launched process has an unexpected bundle identifier"
                )
            if Path(status.executable_path).resolve() != expected_executable:
                raise LifecycleSmokeError(
                    "launched process executable does not match the extracted app"
                )
            if status.finished_launching:
                if status.activation_policy != 0:
                    raise LifecycleSmokeError(
                        "packaged app did not enter the regular activation policy"
                    )
                return status
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    raise LifecycleSmokeError("packaged app readiness timed out")


def exact_process_cleanup(
    process: subprocess.Popen[bytes],
    executable: Path,
    *,
    timeout_seconds: float,
    request_termination: Callable[..., bool] = request_application_termination,
) -> None:
    if process.poll() is not None:
        return
    try:
        request_termination(process.pid, executable, force=False)
    except LifecycleSmokeError:
        pass
    try:
        process.wait(timeout=timeout_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        request_termination(process.pid, executable, force=True)
    except LifecycleSmokeError:
        pass
    try:
        process.wait(timeout=timeout_seconds)
        return
    except subprocess.TimeoutExpired:
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=timeout_seconds)


def isolated_diagnostic_summary(
    temporary_root: Path,
    log_directory: Path,
) -> str:
    files = sorted(
        path.relative_to(temporary_root).as_posix()
        for path in temporary_root.rglob("*")
        if path.is_file()
    )
    log_tails: list[str] = []
    for log_path in sorted(log_directory.glob("*.log")):
        payload = log_path.read_bytes()[-2_000:]
        if payload:
            log_tails.append(
                f"{log_path.name}="
                f"{payload.decode('utf-8', errors='replace').strip()}"
            )
    return f"isolated files={files!r}; logs={log_tails!r}"


def run_one_lifecycle(
    *,
    ordinal: int,
    executable: Path,
    profile: str,
    environment: dict[str, str],
    working_directory: Path,
    log_directory: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
    popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    readiness_waiter: Callable[..., ApplicationStatus] = (
        wait_for_application_readiness
    ),
    request_termination: Callable[..., bool] = request_application_termination,
) -> LifecycleRunResult:
    stdout_path = log_directory / f"run-{ordinal}-stdout.log"
    stderr_path = log_directory / f"run-{ordinal}-stderr.log"
    with stdout_path.open("wb") as stdout_handle, stderr_path.open(
        "wb"
    ) as stderr_handle:
        process = popen_factory(
            [
                str(SANDBOX_EXEC),
                "-p",
                profile,
                str(executable),
            ],
            cwd=working_directory,
            env=environment,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
        try:
            status = readiness_waiter(
                process,
                executable,
                timeout_seconds=readiness_timeout_seconds,
            )
            observation_deadline = time.monotonic() + observation_seconds
            while time.monotonic() < observation_deadline:
                exit_code = process.poll()
                if exit_code is not None:
                    raise LifecycleSmokeError(
                        "packaged app exited during the observation window "
                        f"with code {exit_code}"
                    )
                remaining = max(
                    0.0,
                    observation_deadline - time.monotonic(),
                )
                time.sleep(min(0.1, remaining))

            termination_accepted = request_termination(
                process.pid,
                executable,
                force=False,
            )
            if not termination_accepted:
                raise LifecycleSmokeError(
                    "packaged app rejected the exact-PID termination request"
                )
            try:
                exit_code = process.wait(timeout=termination_timeout_seconds)
            except subprocess.TimeoutExpired as error:
                raise LifecycleSmokeError(
                    "packaged app did not terminate within the graceful deadline"
                ) from error
            if exit_code != 0:
                raise LifecycleSmokeError(
                    f"packaged app terminated with code {exit_code}"
                )
            return LifecycleRunResult(
                activation_policy=status.activation_policy,
                exit_code=exit_code,
                finished_launching=status.finished_launching,
                minimum_observation_seconds=observation_seconds,
                ordinal=ordinal,
                observation_deadline_reached=True,
                termination_accepted=termination_accepted,
            )
        finally:
            exact_process_cleanup(
                process,
                executable,
                timeout_seconds=termination_timeout_seconds,
                request_termination=request_termination,
            )


def write_result(path: Path, result: dict[str, object]) -> None:
    payload = canonical_json_bytes(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary_path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def execute(
    *,
    archive_dir: Path,
    result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    readiness_timeout_seconds = validated_duration(
        readiness_timeout_seconds,
        "readiness timeout",
        0.1,
        60.0,
    )
    observation_seconds = validated_duration(
        observation_seconds,
        "observation window",
        MINIMUM_OBSERVATION_SECONDS,
        30.0,
    )
    termination_timeout_seconds = validated_duration(
        termination_timeout_seconds,
        "termination timeout",
        0.1,
        30.0,
    )
    release = load_release_inputs(archive_dir)
    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-packaged-lifecycle-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        extracted_staging = temporary_root / "extracted-app"
        app_path = extract_packaged_app(release, extracted_staging)
        app_metadata = verify_packaged_app(app_path, release)
        executable = app_path / EXECUTABLE_RELATIVE_PATH

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        logs = temporary_root / "logs"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
            logs,
        ):
            path.mkdir(parents=True, exist_ok=False)
        identity_file = isolated_state / "runtime-identity.json"
        profile = build_sandbox_profile(temporary_root)
        preflight_sandbox(profile, temporary_root)
        environment = isolated_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
        )

        runs: list[LifecycleRunResult] = []
        identity_digests: list[str | None] = []
        application_support_files_present_after_runs: list[bool] = []
        for ordinal in (1, 2):
            runs.append(
                run_one_lifecycle(
                    ordinal=ordinal,
                    executable=executable,
                    profile=profile,
                    environment=environment,
                    working_directory=temporary_root,
                    log_directory=logs,
                    readiness_timeout_seconds=readiness_timeout_seconds,
                    observation_seconds=observation_seconds,
                    termination_timeout_seconds=termination_timeout_seconds,
                )
            )
            application_support = (
                isolated_home / "Library/Application Support/AetherLink"
            )
            missing_state_files = [
                name
                for name in EXPECTED_ISOLATED_STATE_FILES
                if not (application_support / name).is_file()
            ]
            if missing_state_files:
                raise LifecycleSmokeError(
                    "packaged app did not initialize isolated application "
                    f"support files {missing_state_files!r}; "
                    + isolated_diagnostic_summary(temporary_root, logs)
                )
            application_support_files_present_after_runs.append(True)
            if identity_file.is_file() and identity_file.stat().st_size > 0:
                identity_digests.append(sha256_file(identity_file))
                if (
                    len(identity_digests) == 2
                    and identity_digests[0] is not None
                    and identity_digests[1] != identity_digests[0]
                ):
                    raise LifecycleSmokeError(
                        "isolated runtime identity changed across relaunch"
                    )
            else:
                identity_digests.append(None)

        result = {
            "app": app_metadata,
            "isolation": {
                "afInetBindDeniedByPreflight": True,
                "nonTemporaryWriteDeniedByPreflight": True,
                "profile": "allow-default-deny-network-and-non-temp-writes-v1",
                "runtimeIdentity": (
                    "temporary-file-override-with-memory-fallback-allowed"
                ),
                "sandboxed": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "release": {
                "archiveSha256": release.archive_sha256,
                "manifestSha256": release.manifest_sha256,
                "releaseId": EXPECTED_RELEASE_ID,
            },
            "runs": [
                {
                    "activationPolicy": run.activation_policy,
                    "exitCode": run.exit_code,
                    "finishedLaunching": run.finished_launching,
                    "minimumObservationSeconds": (
                        run.minimum_observation_seconds
                    ),
                    "observationDeadlineReached": (
                        run.observation_deadline_reached
                    ),
                    "ordinal": run.ordinal,
                    "terminationAccepted": run.termination_accepted,
                }
                for run in runs
            ],
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "status": "passed",
            "state": {
                "expectedApplicationSupportFilesPresentAfterRuns": (
                    application_support_files_present_after_runs
                ),
                "identityFilePresentAfterRuns": [
                    digest is not None for digest in identity_digests
                ],
                "identityFileUnchangedAcrossRuns": (
                    len(identity_digests) == 2
                    and identity_digests[0] is not None
                    and identity_digests[1] == identity_digests[0]
                ),
                "runtimeIdentityFileOverrideConfigured": True,
            },
        }
    write_result(result_path, result)
    return result


def validated_duration(
    value: object,
    label: str,
    minimum: float,
    maximum: float,
) -> float:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise LifecycleSmokeError(
            f"{label} must be a finite number from {minimum} through {maximum}"
        )
    return float(value)


def bounded_float(
    value: str,
    label: str,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"{label} must be a number"
        ) from error
    try:
        return validated_duration(parsed, label, minimum, maximum)
    except LifecycleSmokeError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=DEFAULT_RESULT,
    )
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=lambda value: bounded_float(
            value,
            "readiness timeout",
            0.1,
            60,
        ),
        default=15.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=lambda value: bounded_float(
            value,
            "observation window",
            MINIMUM_OBSERVATION_SECONDS,
            30,
        ),
        default=MINIMUM_OBSERVATION_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=lambda value: bounded_float(
            value,
            "termination timeout",
            0.1,
            30,
        ),
        default=10.0,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = execute(
            archive_dir=args.archive_dir,
            result_path=args.result,
            readiness_timeout_seconds=args.readiness_timeout_seconds,
            observation_seconds=args.observation_seconds,
            termination_timeout_seconds=args.termination_timeout_seconds,
        )
    except KeyboardInterrupt:
        print("macOS packaged-app lifecycle smoke interrupted.", file=sys.stderr)
        return 130
    except (LifecycleSmokeError, OSError, zipfile.BadZipFile) as error:
        print(
            f"macOS packaged-app lifecycle smoke failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "macOS packaged-app lifecycle smoke passed: "
        f"{result['release']['releaseId']}; runs=2; "
        "network-bind=denied; temporary-user-home=configured."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
