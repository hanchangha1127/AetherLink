#!/usr/bin/env python3
"""Verify packaged macOS legacy migration and SQLite-only relaunch recovery."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import plistlib
import sqlite3
import stat
import sys
import tempfile
from urllib.parse import quote
import zipfile

if __package__:
    from script import run_macos_packaged_app_lifecycle_smoke as engine
    from script.check_release_version_ledger import (
        ReleaseVersion,
        load_release_version_ledger,
    )
else:
    import run_macos_packaged_app_lifecycle_smoke as engine
    from check_release_version_ledger import (
        ReleaseVersion,
        load_release_version_ledger,
    )


ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_VERSION = 1
QA_MODE_ENVIRONMENT_KEY = "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_MODE"
MIGRATION_MODE = "migration-read-v1"
SQLITE_READBACK_MODE = "sqlite-readback-v1"
MARKER_DIRECTORY_NAME = "qa-packaged-state-recovery-v1"
LEGACY_FILENAME = "runtime-chat-events.jsonl"
DATABASE_FILENAME = "runtime-chat-events.sqlite"
CANARY_EVENT_ID = "packaged-state-recovery-canary-event-v1"
CANARY_REQUEST_ID = "packaged-state-recovery-canary-request-v1"
CANARY_SESSION_ID = "packaged-state-recovery-canary-session-v1"
CANARY_MODEL = "qa:packaged-state-recovery-canary-v1"
CANARY_TIMESTAMP = "1970-01-01T00:00:01Z"
CANARY_TIMESTAMP_EPOCH_MILLISECONDS = 1_000
CANARY_LEGACY_BYTES = (
    b'{"id":"packaged-state-recovery-canary-event-v1","kind":"request",'
    b'"messages":[{"content":"Benign packaged state recovery canary v1.",'
    b'"role":"user"}],"model":"qa:packaged-state-recovery-canary-v1",'
    b'"request_id":"packaged-state-recovery-canary-request-v1",'
    b'"session_id":"packaged-state-recovery-canary-session-v1",'
    b'"timestamp":"1970-01-01T00:00:01Z"}\n'
)
CANARY_LEGACY_SHA256 = (
    "0e51fc924836465c4c0921eb3b3709b387f89787aabf2e100c7cff338f0aea2e"
)
CANARY_EVENT_JSON = CANARY_LEGACY_BYTES[:-1]
CANARY_EVENT_JSON_SHA256 = (
    "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
)


@dataclass(frozen=True)
class SQLiteCanaryEvidence:
    event_json_sha256: str
    event_json_size: int
    integrity_check: str
    total_event_count: int

    def record(self) -> dict[str, object]:
        return {
            "eventJsonSha256": self.event_json_sha256,
            "eventJsonSize": self.event_json_size,
            "integrityCheck": self.integrity_check,
            "totalEventCount": self.total_event_count,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_release() -> ReleaseVersion:
    return load_release_version_ledger()[-1]


def release_id_for(version: ReleaseVersion) -> str:
    return (
        f"aetherlink-{version.marketing_version}"
        f"+{version.build_number}-local-v1"
    )


def default_archive_dir() -> Path:
    return ROOT / "dist/releases" / release_id_for(current_release())


def default_result_path() -> Path:
    version = current_release()
    return (
        ROOT
        / "dist/lifecycle"
        / (
            "macos-packaged-app-build-"
            f"{version.build_number}-state-recovery-v1.json"
        )
    )


def load_release_inputs(
    archive_dir: Path,
    *,
    verify_readback: bool = True,
    version: ReleaseVersion | None = None,
) -> engine.ReleaseInputs:
    resolved_version = version or current_release()
    release_id = release_id_for(resolved_version)
    archive_dir = archive_dir.resolve()
    if not archive_dir.is_dir():
        raise engine.LifecycleSmokeError(
            f"release archive directory is missing: {archive_dir}"
        )
    if archive_dir.name != release_id:
        raise engine.LifecycleSmokeError(
            f"expected release directory {release_id!r}, "
            f"found {archive_dir.name!r}"
        )

    archive_path = archive_dir / f"{release_id}.zip"
    manifest_path = archive_dir / f"{release_id}.manifest.json"
    checksum_path = archive_dir / f"{release_id}.zip.sha256"
    for path in (archive_path, manifest_path, checksum_path):
        if not path.is_file():
            raise engine.LifecycleSmokeError(f"missing release input: {path}")

    if verify_readback:
        engine.verify_archive_readback(archive_dir)

    manifest_bytes = manifest_path.read_bytes()
    manifest = engine.strict_json_loads(manifest_bytes, str(manifest_path))
    if not isinstance(manifest, dict):
        raise engine.LifecycleSmokeError(
            "release manifest root must be an object"
        )
    release = manifest.get("release")
    if not isinstance(release, dict):
        raise engine.LifecycleSmokeError(
            "release manifest is missing release metadata"
        )
    expected_release = {
        "buildNumber": resolved_version.build_number,
        "marketingVersion": resolved_version.marketing_version,
        "releaseId": release_id,
    }
    actual_release = {key: release.get(key) for key in expected_release}
    if any(
        type(actual_release[key]) is not type(expected)
        or actual_release[key] != expected
        for key, expected in expected_release.items()
    ):
        raise engine.LifecycleSmokeError(
            f"unexpected release metadata: {actual_release!r}"
        )

    try:
        checksum_fields = checksum_path.read_text(encoding="ascii").split()
    except (OSError, UnicodeError) as error:
        raise engine.LifecycleSmokeError(
            f"release checksum sidecar is unreadable: {error}"
        ) from error
    if (
        len(checksum_fields) != 2
        or checksum_fields[1] != archive_path.name
        or len(checksum_fields[0]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in checksum_fields[0]
        )
    ):
        raise engine.LifecycleSmokeError(
            "release checksum sidecar is malformed"
        )
    archive_sha256 = checksum_fields[0]
    if sha256_file(archive_path) != archive_sha256:
        raise engine.LifecycleSmokeError(
            "release ZIP differs from its checksum sidecar"
        )

    return engine.ReleaseInputs(
        archive_dir=archive_dir,
        archive_path=archive_path,
        manifest_path=manifest_path,
        checksum_path=checksum_path,
        archive_sha256=archive_sha256,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        manifest=manifest,
    )


def verify_packaged_app(
    app_path: Path,
    release: engine.ReleaseInputs,
    *,
    version: ReleaseVersion | None = None,
) -> dict[str, object]:
    resolved_version = version or current_release()
    info_plist = app_path / engine.INFO_PLIST_RELATIVE_PATH
    executable = app_path / engine.EXECUTABLE_RELATIVE_PATH
    if not info_plist.is_file() or not executable.is_file():
        raise engine.LifecycleSmokeError(
            "extracted app is missing Info.plist or executable"
        )
    if not os.access(executable, os.X_OK):
        raise engine.LifecycleSmokeError(
            "extracted app executable is not executable"
        )

    try:
        plist = plistlib.loads(info_plist.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise engine.LifecycleSmokeError(
            f"invalid packaged Info.plist: {error}"
        ) from error
    expected_plist = {
        "CFBundleIdentifier": engine.EXPECTED_BUNDLE_ID,
        "CFBundleShortVersionString": resolved_version.marketing_version,
        "CFBundleVersion": str(resolved_version.build_number),
    }
    for key, expected in expected_plist.items():
        actual = plist.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise engine.LifecycleSmokeError(
                f"expected Info.plist {key}={expected!r}, found {actual!r}"
            )

    engine.run_checked(
        [
            str(engine.CODESIGN),
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app_path),
        ]
    )
    members = engine.manifest_member_map(release.manifest)
    executable_member = (
        engine.APP_MEMBER_PREFIX
        + engine.EXECUTABLE_RELATIVE_PATH.as_posix()
    )
    expected_executable = members.get(executable_member)
    if expected_executable is None:
        raise engine.LifecycleSmokeError(
            "manifest is missing the macOS executable"
        )
    actual_executable = (
        executable.stat().st_size,
        sha256_file(executable),
        stat.S_IMODE(executable.stat().st_mode),
    )
    if actual_executable != expected_executable:
        raise engine.LifecycleSmokeError(
            "extracted macOS executable differs from the release manifest"
        )
    platforms = release.manifest.get("platforms")
    macos = platforms.get("macos") if isinstance(platforms, dict) else None
    uuid = macos.get("uuid") if isinstance(macos, dict) else None
    if type(uuid) is not str or not uuid:
        raise engine.LifecycleSmokeError(
            "release manifest has no macOS UUID"
        )
    return {
        "bundleIdentifier": engine.EXPECTED_BUNDLE_ID,
        "buildNumber": resolved_version.build_number,
        "executableSha256": expected_executable[1],
        "marketingVersion": resolved_version.marketing_version,
        "uuid": uuid,
    }


def write_legacy_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=False, mode=0o700)
    path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        total = 0
        while total < len(CANARY_LEGACY_BYTES):
            total += os.write(descriptor, CANARY_LEGACY_BYTES[total:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    status = path.lstat()
    if (
        not stat.S_ISREG(status.st_mode)
        or stat.S_IMODE(status.st_mode) != 0o600
        or path.read_bytes() != CANARY_LEGACY_BYTES
        or sha256_file(path) != CANARY_LEGACY_SHA256
    ):
        raise engine.LifecycleSmokeError(
            "legacy runtime-chat canary fixture is not exact"
        )


def state_recovery_environment(
    base: dict[str, str],
    *,
    home: Path,
    temporary: Path,
    identity_file: Path,
    mode: str,
) -> dict[str, str]:
    if mode not in (MIGRATION_MODE, SQLITE_READBACK_MODE):
        raise engine.LifecycleSmokeError(
            f"unsupported packaged-state recovery mode: {mode!r}"
        )
    environment = engine.isolated_environment(
        base,
        home=home,
        temporary=temporary,
        identity_file=identity_file,
    )
    environment[QA_MODE_ENVIRONMENT_KEY] = mode
    return environment


def expected_marker(mode: str) -> dict[str, object]:
    if mode not in (MIGRATION_MODE, SQLITE_READBACK_MODE):
        raise engine.LifecycleSmokeError(
            f"unsupported packaged-state recovery mode: {mode!r}"
        )
    return {
        "canary": {
            "eventID": CANARY_EVENT_ID,
            "model": CANARY_MODEL,
            "requestID": CANARY_REQUEST_ID,
            "sessionID": CANARY_SESSION_ID,
            "timestampEpochMilliseconds": (
                CANARY_TIMESTAMP_EPOCH_MILLISECONDS
            ),
        },
        "mode": mode,
        "observation": {
            "lastActivityEpochMilliseconds": (
                CANARY_TIMESTAMP_EPOCH_MILLISECONDS
            ),
            "lastEvent": "request",
            "matchingSessionCount": 1,
            "messageCount": 1,
            "model": CANARY_MODEL,
            "status": "active",
        },
        "schemaVersion": 1,
        "status": "passed",
    }


def verify_marker(path: Path, mode: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise engine.LifecycleSmokeError(
            f"packaged-state recovery marker is missing: {path.name}"
        )
    payload = path.read_bytes()
    marker = engine.strict_json_loads(payload, str(path))
    expected = expected_marker(mode)
    if marker != expected:
        raise engine.LifecycleSmokeError(
            f"packaged-state recovery marker differs for {mode!r}"
        )
    if payload != engine.canonical_json_bytes(expected):
        raise engine.LifecycleSmokeError(
            f"packaged-state recovery marker is not canonical for {mode!r}"
        )
    return {
        "mode": mode,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "status": "passed",
    }


def sqlite_canary_evidence(database_path: Path) -> SQLiteCanaryEvidence:
    if database_path.is_symlink() or not database_path.is_file():
        raise engine.LifecycleSmokeError(
            "runtime-chat SQLite database is missing or not a regular file"
        )
    database_uri = (
        "file:" + quote(str(database_path.resolve()), safe="/") + "?mode=ro"
    )
    try:
        connection = sqlite3.connect(database_uri, uri=True, timeout=5)
        try:
            connection.execute("PRAGMA query_only = ON")
            integrity_rows = connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()
            count_row = connection.execute(
                "SELECT COUNT(*) FROM runtime_chat_events"
            ).fetchone()
            canary_rows = connection.execute(
                """
                SELECT event_id,
                       timestamp,
                       kind,
                       request_id,
                       session_id,
                       owner_device_id,
                       model,
                       event_json
                FROM runtime_chat_events
                WHERE event_id = ?
                """,
                (CANARY_EVENT_ID,),
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise engine.LifecycleSmokeError(
            f"runtime-chat SQLite readback failed: {error}"
        ) from error

    if integrity_rows != [("ok",)]:
        raise engine.LifecycleSmokeError(
            "runtime-chat SQLite integrity_check did not return exactly ok"
        )
    if (
        count_row is None
        or len(count_row) != 1
        or type(count_row[0]) is not int
        or count_row[0] != 1
    ):
        raise engine.LifecycleSmokeError(
            "runtime-chat SQLite must contain exactly one event"
        )
    expected_row = (
        CANARY_EVENT_ID,
        CANARY_TIMESTAMP,
        "request",
        CANARY_REQUEST_ID,
        CANARY_SESSION_ID,
        None,
        CANARY_MODEL,
        CANARY_EVENT_JSON.decode("ascii"),
    )
    if canary_rows != [expected_row]:
        raise engine.LifecycleSmokeError(
            "runtime-chat SQLite canary row differs from the fixed fixture"
        )
    event_json = canary_rows[0][7].encode("utf-8")
    digest = hashlib.sha256(event_json).hexdigest()
    if (
        event_json != CANARY_EVENT_JSON
        or len(event_json) != len(CANARY_EVENT_JSON)
        or digest != CANARY_EVENT_JSON_SHA256
    ):
        raise engine.LifecycleSmokeError(
            "runtime-chat SQLite event_json identity differs"
        )
    return SQLiteCanaryEvidence(
        event_json_sha256=digest,
        event_json_size=len(event_json),
        integrity_check="ok",
        total_event_count=count_row[0],
    )


def remove_legacy_before_readback(
    legacy_path: Path,
    preserved_directory: Path,
) -> Path:
    if (
        legacy_path.is_symlink()
        or not legacy_path.is_file()
        or legacy_path.read_bytes() != CANARY_LEGACY_BYTES
        or sha256_file(legacy_path) != CANARY_LEGACY_SHA256
    ):
        raise engine.LifecycleSmokeError(
            "legacy runtime-chat fixture drifted before SQLite-only readback"
        )
    preserved_directory.mkdir(
        parents=True,
        exist_ok=False,
        mode=0o700,
    )
    preserved_directory.chmod(0o700)
    preserved_path = preserved_directory / LEGACY_FILENAME
    legacy_path.replace(preserved_path)
    if legacy_path.exists() or legacy_path.is_symlink():
        raise engine.LifecycleSmokeError(
            "legacy runtime-chat fixture remains before SQLite-only readback"
        )
    if preserved_path.read_bytes() != CANARY_LEGACY_BYTES:
        raise engine.LifecycleSmokeError(
            "preserved legacy runtime-chat fixture differs"
        )
    return preserved_path


def publish_result(path: Path, result: dict[str, object]) -> None:
    payload = engine.canonical_json_bytes(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_file() and path.read_bytes() == payload:
            return
        raise engine.LifecycleSmokeError(
            f"refusing to replace different state-recovery result bytes: {path}"
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
            if not path.is_file() or path.read_bytes() != payload:
                raise engine.LifecycleSmokeError(
                    "concurrent state-recovery result publication differed"
                )
    finally:
        temporary_path.unlink(missing_ok=True)


def run_record(run: engine.LifecycleRunResult) -> dict[str, object]:
    return {
        "activationPolicy": run.activation_policy,
        "exitCode": run.exit_code,
        "finishedLaunching": run.finished_launching,
        "minimumObservationSeconds": run.minimum_observation_seconds,
        "observationDeadlineReached": run.observation_deadline_reached,
        "ordinal": run.ordinal,
        "terminationAccepted": run.termination_accepted,
    }


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
    release = load_release_inputs(archive_dir, version=version)

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-packaged-state-recovery-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        app_path = engine.extract_packaged_app(
            release,
            temporary_root / "extracted-app",
        )
        app_metadata = verify_packaged_app(
            app_path,
            release,
            version=version,
        )
        executable = app_path / engine.EXECUTABLE_RELATIVE_PATH

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
        application_support = (
            isolated_home / "Library/Application Support/AetherLink"
        )
        legacy_path = application_support / LEGACY_FILENAME
        database_path = application_support / DATABASE_FILENAME
        marker_directory = application_support / MARKER_DIRECTORY_NAME
        write_legacy_fixture(legacy_path)

        profile = engine.build_sandbox_profile(temporary_root)
        engine.preflight_sandbox(profile, temporary_root)
        migration_environment = state_recovery_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=MIGRATION_MODE,
        )
        first_run = engine.run_one_lifecycle(
            ordinal=1,
            executable=executable,
            profile=profile,
            environment=migration_environment,
            working_directory=temporary_root,
            log_directory=logs,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        first_marker = verify_marker(
            marker_directory / f"{MIGRATION_MODE}.json",
            MIGRATION_MODE,
        )
        first_sqlite = sqlite_canary_evidence(database_path)

        preserved_legacy = remove_legacy_before_readback(
            legacy_path,
            temporary_root / "preserved-legacy",
        )
        readback_environment = state_recovery_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=SQLITE_READBACK_MODE,
        )
        second_run = engine.run_one_lifecycle(
            ordinal=2,
            executable=executable,
            profile=profile,
            environment=readback_environment,
            working_directory=temporary_root,
            log_directory=logs,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if legacy_path.exists() or legacy_path.is_symlink():
            raise engine.LifecycleSmokeError(
                "legacy runtime-chat fixture reappeared during SQLite readback"
            )
        second_marker = verify_marker(
            marker_directory / f"{SQLITE_READBACK_MODE}.json",
            SQLITE_READBACK_MODE,
        )
        second_sqlite = sqlite_canary_evidence(database_path)
        if first_sqlite != second_sqlite:
            raise engine.LifecycleSmokeError(
                "runtime-chat SQLite canary changed across independent runs"
            )
        if (
            preserved_legacy.read_bytes() != CANARY_LEGACY_BYTES
            or sha256_file(preserved_legacy) != CANARY_LEGACY_SHA256
        ):
            raise engine.LifecycleSmokeError(
                "preserved legacy fixture changed during SQLite readback"
            )

        result = {
            "app": app_metadata,
            "canary": {
                "eventID": CANARY_EVENT_ID,
                "eventJsonSha256": CANARY_EVENT_JSON_SHA256,
                "eventJsonSize": len(CANARY_EVENT_JSON),
                "legacyJsonlSha256": CANARY_LEGACY_SHA256,
                "legacyJsonlSize": len(CANARY_LEGACY_BYTES),
                "model": CANARY_MODEL,
                "requestID": CANARY_REQUEST_ID,
                "sessionID": CANARY_SESSION_ID,
            },
            "isolation": {
                "profile": (
                    "allow-default-deny-network-and-non-temp-writes-v1"
                ),
                "sandboxed": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "release": {
                "archiveSha256": release.archive_sha256,
                "manifestSha256": release.manifest_sha256,
                "releaseId": release_id,
            },
            "runs": [run_record(first_run), run_record(second_run)],
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "stateRecovery": {
                "legacyAbsentBeforeSecondRun": True,
                "legacyFixturePreservedUnchanged": True,
                "migrationMarker": first_marker,
                "migrationSQLite": first_sqlite.record(),
                "sqliteCanaryUnchangedAcrossRuns": True,
                "sqliteReadbackMarker": second_marker,
                "sqliteReadbackSQLite": second_sqlite.record(),
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
        default=15.0,
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
        print(
            "macOS packaged-state recovery smoke interrupted.",
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
            f"macOS packaged-state recovery smoke failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "macOS packaged-state recovery smoke passed: "
        f"{result['release']['releaseId']}; "
        "migration-read=passed; sqlite-readback=passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
