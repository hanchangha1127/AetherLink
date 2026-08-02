#!/usr/bin/env python3
"""Qualify SQLite recovery at a QA-forced production append writeback point."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Sequence
from urllib.parse import quote

try:
    import run_macos_runtime_chat_cross_process_smoke as base
except ModuleNotFoundError:
    from script import run_macos_runtime_chat_cross_process_smoke as base


RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "macos-runtime-chat-sqlite-production-append-abrupt-recovery-v1"
)
REPEATABILITY_SCOPE = RESULT_SCOPE + "-repeatability"
PRODUCTION_APPEND_MODE = "production-append"
PRODUCTION_APPEND_CHECKPOINT_FILENAME = (
    "production-append-checkpoint-v1.json"
)
PRODUCTION_APPEND_WRITER = "writer-a"
PRODUCTION_APPEND_EVENT_ID = "qa-writer-a-event-0000"
PRODUCTION_APPEND_REQUEST_ID = "qa-writer-a-request-0000"
PRODUCTION_APPEND_OWNER_ID = "qa-owner-a"
CHECKPOINT_TIMEOUT_SECONDS = 5.0
MAXIMUM_CHECKPOINT_BYTES = 4_096
MAXIMUM_JOURNAL_BYTES = 8 * 1_024 * 1_024
SOURCE_INPUT_PATHS = (
    "apps/macos/CompanionCore/Sources/SQLiteRuntimeChatEventStore.swift",
    (
        "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
        "RuntimeChatSQLiteCrossProcessQA.swift"
    ),
    "script/run_macos_runtime_chat_production_append_abrupt_recovery_smoke.py",
)


def production_append_command(
    helper: Path,
    database_root: Path,
) -> tuple[str, ...]:
    if (
        not helper.is_absolute()
        or not database_root.is_absolute()
        or "\x00" in str(helper)
        or "\x00" in str(database_root)
    ):
        raise base.SmokeError("production append helper paths must be absolute")
    return (
        str(helper),
        PRODUCTION_APPEND_MODE,
        "--database-root",
        str(database_root),
        "--writer",
        PRODUCTION_APPEND_WRITER,
    )


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise base.SmokeError("production append checkpoint repeats a JSON key")
        result[key] = value
    return result


def expected_checkpoint() -> dict[str, Any]:
    return {
        "databaseCacheFlushed": True,
        "eventID": PRODUCTION_APPEND_EVENT_ID,
        "ownerDeviceID": PRODUCTION_APPEND_OWNER_ID,
        "phase": "after-validated-state-and-cache-flush-before-commit",
        "requestID": PRODUCTION_APPEND_REQUEST_ID,
        "schemaVersion": 1,
        "status": "ready-for-abrupt-termination",
        "transactionOpen": True,
        "writePath": "SQLiteRuntimeChatEventStore.append",
        "writer": PRODUCTION_APPEND_WRITER,
    }


def validate_checkpoint(payload: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise base.SmokeError(
            "production append checkpoint is not canonical JSON"
        ) from error
    expected = expected_checkpoint()
    if (
        type(parsed) is not dict
        or parsed != expected
        or any(type(parsed.get(key)) is not type(value) for key, value in expected.items())
        or payload != (base.canonical_json(parsed) + "\n").encode("ascii")
    ):
        raise base.SmokeError(
            "production append checkpoint differs from the exact fixture"
        )
    return parsed


def wait_for_checkpoint(
    process: base.ProcessLike,
    database_root: Path,
    *,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any], bytes]:
    deadline = monotonic() + CHECKPOINT_TIMEOUT_SECONDS
    checkpoint_path = database_root / PRODUCTION_APPEND_CHECKPOINT_FILENAME
    while monotonic() < deadline:
        try:
            payload = base._read_owner_only_regular_file(
                checkpoint_path,
                maximum_bytes=MAXIMUM_CHECKPOINT_BYTES,
                label="production append checkpoint",
            )
            return validate_checkpoint(payload), payload
        except base.SmokeError:
            if checkpoint_path.exists() or checkpoint_path.is_symlink():
                raise
        if process.poll() is not None:
            raise base.SmokeError(
                "production append helper exited before its checkpoint"
            )
        sleep(0.005)
    raise base.SmokeError("production append checkpoint timed out")


def observe_dirty_database(database_root: Path) -> dict[str, Any]:
    database = database_root / base.DATABASE_FILENAME
    if not database.is_file() or database.is_symlink():
        raise base.SmokeError("production append dirty database is missing")
    uri = f"file:{quote(str(database))}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM runtime_chat_events"
            ).fetchone()
            fts_count = connection.execute(
                "SELECT COUNT(*) FROM runtime_chat_event_fts_v2"
            ).fetchone()
            append_state = connection.execute(
                """
                SELECT mutation_revision, validated_revision,
                       search_projection_version
                FROM runtime_chat_append_state
                WHERE singleton = 1
                """
            ).fetchall()
            event_identity = connection.execute(
                """
                SELECT event_id, request_id, owner_device_id
                FROM runtime_chat_events
                WHERE event_id = ?
                """,
                (PRODUCTION_APPEND_EVENT_ID,),
            ).fetchall()
            fts_event_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM runtime_chat_event_fts_v2
                WHERE event_id = ?
                """,
                (PRODUCTION_APPEND_EVENT_ID,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise base.SmokeError(
            "production append dirty database inspection failed"
        ) from error
    if (
        event_count != (1,)
        or fts_count != (1,)
        or append_state != [(1, 1, 2)]
        or event_identity
        != [(
            PRODUCTION_APPEND_EVENT_ID,
            PRODUCTION_APPEND_REQUEST_ID,
            PRODUCTION_APPEND_OWNER_ID,
        )]
        or fts_event_count != (1,)
    ):
        raise base.SmokeError(
            "production append dirty database differs from the exact fixture"
        )
    return {
        "appendStateMutationRevision": 1,
        "appendStateValidatedRevision": 1,
        "eventAndFTSPresent": True,
        "eventCount": 1,
        "ftsEventCount": 1,
        "immutableReadIgnoredJournal": True,
        "searchProjectionVersion": 2,
    }


def _journal_bytes(database_root: Path) -> bytes:
    return base._read_owner_only_regular_file(
        database_root / f"{base.DATABASE_FILENAME}-journal",
        maximum_bytes=MAXIMUM_JOURNAL_BYTES,
        label="production append SQLite rollback journal",
    )


def run_abrupt_production_append(
    helper: Path,
    database_root: Path,
    *,
    popen_factory: base.PopenFactory = subprocess.Popen,
    checkpoint_waiter: Callable[
        [base.ProcessLike, Path],
        tuple[dict[str, Any], bytes],
    ] = wait_for_checkpoint,
    group_killer: base.GroupKiller = os.killpg,
    group_identity_reader: base.GroupIdentityReader = os.getpgid,
    output_collector: base.OutputCollector = base._collect_process_outputs,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    process: base.ProcessLike | None = None
    group_identity_confirmed = False

    def cleanup_group_killer(pid: int, caught_signal: int) -> None:
        if not group_identity_confirmed:
            raise ProcessLookupError()
        group_killer(pid, caught_signal)

    try:
        process = popen_factory(
            list(production_append_command(helper, database_root)),
            cwd=base.ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=base.closed_environment(temporary=database_root),
            start_new_session=True,
        )
        checkpoint, checkpoint_bytes = checkpoint_waiter(
            process,
            database_root,
        )
        if process.poll() is not None:
            raise base.SmokeError(
                "production append helper exited before the termination signal"
            )
        if group_identity_reader(process.pid) != process.pid:
            raise base.SmokeError(
                "production append helper does not own its exact process group"
            )
        group_identity_confirmed = True

        journal_before = base.observe_hot_rollback_journal(database_root)
        journal_bytes_before = _journal_bytes(database_root)
        dirty_before = observe_dirty_database(database_root)
        checkpoint_path = database_root / PRODUCTION_APPEND_CHECKPOINT_FILENAME
        checkpoint_bytes_again = base._read_owner_only_regular_file(
            checkpoint_path,
            maximum_bytes=MAXIMUM_CHECKPOINT_BYTES,
            label="production append checkpoint",
        )
        if checkpoint_bytes_again != checkpoint_bytes:
            raise base.SmokeError(
                "production append checkpoint changed before termination"
            )
        if process.poll() is not None:
            raise base.SmokeError(
                "production append helper exited before exact termination"
            )

        group_killer(process.pid, signal.SIGKILL)
        stdout, stderr = output_collector(
            (process,),
            base.PROCESS_TIMEOUT_SECONDS,
            monotonic,
        )[0]
        process.wait(timeout=2.0)
        if process.returncode != -signal.SIGKILL or stdout or stderr:
            raise base.SmokeError(
                "production append helper termination result differs"
            )

        journal_bytes_after = _journal_bytes(database_root)
        journal_after = base.observe_hot_rollback_journal(database_root)
        dirty_after = observe_dirty_database(database_root)
        if (
            journal_bytes_after != journal_bytes_before
            or journal_after != journal_before
            or dirty_after != dirty_before
        ):
            raise base.SmokeError(
                "production append crash-point bytes changed across SIGKILL"
            )
    except base._OutputOverflow as error:
        if process is not None:
            base._terminate_and_reap(
                (process,),
                group_killer=cleanup_group_killer,
            )
        raise base.SmokeError(
            "production append helper output exceeded the hard limit"
        ) from error
    except (OSError, subprocess.TimeoutExpired) as error:
        if process is not None:
            base._terminate_and_reap(
                (process,),
                group_killer=cleanup_group_killer,
            )
        raise base.SmokeError(
            "production append helper could not be terminated and reaped"
        ) from error
    except Exception:
        if process is not None:
            base._terminate_and_reap(
                (process,),
                group_killer=cleanup_group_killer,
            )
        raise

    return {
        "checkpoint": checkpoint,
        "dirtyDatabaseBeforeRecovery": dirty_before,
        "journal": {
            **journal_before,
            "bytesStableAcrossSignal": True,
            "hotAfterWriterTermination": True,
            "populatedBeforeSignal": True,
        },
        "processGroup": "new-session-exact-child-only",
        "terminationSignal": "SIGKILL",
        "writerProcessReaped": True,
    }


def inspect_recovered_or_final_database(
    database: Path,
    *,
    expected_event_count: int,
) -> dict[str, Any]:
    if type(expected_event_count) is not int or expected_event_count not in {
        0,
        base.EVENT_COUNT_PER_WRITER,
    }:
        raise base.SmokeError("production append expected count is invalid")
    if not database.is_file() or database.is_symlink():
        raise base.SmokeError("production append SQLite database is missing")
    uri = f"file:{quote(str(database))}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchall()
            foreign_keys = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            event_count = connection.execute(
                "SELECT COUNT(*) FROM runtime_chat_events"
            ).fetchone()
            fts_count = connection.execute(
                "SELECT COUNT(*) FROM runtime_chat_event_fts_v2"
            ).fetchone()
            append_state = connection.execute(
                """
                SELECT mutation_revision, validated_revision,
                       search_projection_version
                FROM runtime_chat_append_state
                WHERE singleton = 1
                """
            ).fetchall()
            event_zero_count = connection.execute(
                """
                SELECT COUNT(*) FROM runtime_chat_events
                WHERE event_id = ?
                """,
                (PRODUCTION_APPEND_EVENT_ID,),
            ).fetchone()
            sequence = connection.execute(
                """
                SELECT sequence FROM runtime_chat_events
                ORDER BY sequence ASC
                """
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise base.SmokeError(
            "production append SQLite inspection failed"
        ) from error

    expected_state = (
        [(0, -1, 0)]
        if expected_event_count == 0
        else [(expected_event_count, expected_event_count, 2)]
    )
    expected_zero_count = 0 if expected_event_count == 0 else 1
    if (
        integrity != [("ok",)]
        or foreign_keys != []
        or event_count != (expected_event_count,)
        or fts_count != (expected_event_count,)
        or append_state != expected_state
        or event_zero_count != (expected_zero_count,)
        or sequence != [
            (value,)
            for value in range(1, expected_event_count + 1)
        ]
    ):
        raise base.SmokeError(
            "production append SQLite state differs from the exact fixture"
        )

    journal = database.with_name(f"{database.name}-journal")
    if journal.exists() or journal.is_symlink():
        residual = base._read_owner_only_regular_file(
            journal,
            maximum_bytes=MAXIMUM_JOURNAL_BYTES,
            label="recovered production append rollback journal",
        )
        if (
            len(residual) < len(base.SQLITE_ROLLBACK_JOURNAL_MAGIC)
            or residual[: len(base.SQLITE_ROLLBACK_JOURNAL_MAGIC)]
            != b"\0" * len(base.SQLITE_ROLLBACK_JOURNAL_MAGIC)
        ):
            raise base.SmokeError(
                "production append rollback journal remained hot"
            )
    return {
        "appendStateMutationRevision": expected_event_count,
        "appendStateValidatedRevision": (
            -1 if expected_event_count == 0 else expected_event_count
        ),
        "eventCount": expected_event_count,
        "eventZeroCount": expected_zero_count,
        "ftsEventCount": expected_event_count,
        "hotJournalCleared": True,
        "integrityCheck": "ok",
        "searchProjectionVersion": 0 if expected_event_count == 0 else 2,
        "sequencesContiguous": True,
    }


def run_exact_retry(
    helper: Path,
    database_root: Path,
    *,
    command_runner: base.CommandRunner = base.default_command_runner,
) -> dict[str, Any]:
    base.write_start_gate(database_root)
    completed = command_runner(
        base.helper_command(
            helper,
            database_root,
            mode="write",
            writer=PRODUCTION_APPEND_WRITER,
        ),
        base.PROCESS_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0 or completed.stderr:
        raise base.SmokeError("production append exact retry failed")
    result = base.parse_helper_json(
        completed.stdout,
        label="production append exact retry",
    )
    expected = {
        "eventCount": base.EVENT_COUNT_PER_WRITER,
        "status": "passed",
        "writer": PRODUCTION_APPEND_WRITER,
    }
    if (
        result != expected
        or any(type(result.get(key)) is not type(value) for key, value in expected.items())
    ):
        raise base.SmokeError(
            "production append exact retry result differs"
        )
    return result


def validate_permissions(database_root: Path) -> None:
    allowed = {
        base.DATABASE_FILENAME,
        base.DATABASE_FILENAME + "-journal",
        base.DATABASE_FILENAME + "-shm",
        base.DATABASE_FILENAME + "-wal",
        base.GATE_FILENAME,
        PRODUCTION_APPEND_CHECKPOINT_FILENAME,
    }
    try:
        root_status = database_root.lstat()
        if (
            not stat.S_ISDIR(root_status.st_mode)
            or stat.S_IMODE(root_status.st_mode) != 0o700
            or root_status.st_uid != os.getuid()
        ):
            raise base.SmokeError(
                "production append database root is not owner-only"
            )
        for child in database_root.iterdir():
            status = child.lstat()
            if (
                child.name not in allowed
                or not stat.S_ISREG(status.st_mode)
                or stat.S_IMODE(status.st_mode) != 0o600
                or status.st_uid != os.getuid()
                or status.st_nlink != 1
            ):
                raise base.SmokeError(
                    "production append database-root file is not owner-only"
                )
    except OSError as error:
        raise base.SmokeError(
            "could not inspect production append permissions"
        ) from error


def source_inputs() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for relative_path in SOURCE_INPUT_PATHS:
        path = base.ROOT / relative_path
        try:
            before = path.lstat()
            payload = path.read_bytes()
            after = path.lstat()
        except OSError as error:
            raise base.SmokeError(
                "production append source input could not be read"
            ) from error
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino, before.st_mode, before.st_size)
            != (after.st_dev, after.st_ino, after.st_mode, after.st_size)
            or len(payload) != before.st_size
        ):
            raise base.SmokeError(
                "production append source input identity is invalid"
            )
        result.append({
            "byteCount": len(payload),
            "path": relative_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    return result


def qualify_once(
    helper: Path,
    *,
    command_runner: base.CommandRunner = base.default_command_runner,
    popen_factory: base.PopenFactory = subprocess.Popen,
) -> dict[str, Any]:
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        temporary = tempfile.TemporaryDirectory(
            prefix="aetherlink-production-append-abrupt-recovery-"
        )
        database_root = Path(temporary.name)
        os.chmod(database_root, 0o700)
    except OSError as error:
        if temporary is not None:
            try:
                temporary.cleanup()
            except OSError:
                pass
        raise base.SmokeError(
            "could not prepare production append database root"
        ) from error

    failure: Exception | None = None
    try:
        abrupt = run_abrupt_production_append(
            helper,
            database_root,
            popen_factory=popen_factory,
        )
        recovered_readback = base.run_readback(
            helper,
            database_root,
            command_runner=command_runner,
        )
        base.validate_readback_counts(
            recovered_readback,
            expected_counts={
                PRODUCTION_APPEND_WRITER: 0,
                "writer-b": 0,
            },
            require_contiguous_sequences=True,
        )
        database = database_root / base.DATABASE_FILENAME
        recovered = inspect_recovered_or_final_database(
            database,
            expected_event_count=0,
        )
        retry = run_exact_retry(
            helper,
            database_root,
            command_runner=command_runner,
        )
        final_readback = base.run_readback(
            helper,
            database_root,
            command_runner=command_runner,
        )
        base.validate_readback_counts(
            final_readback,
            expected_counts={
                PRODUCTION_APPEND_WRITER: base.EVENT_COUNT_PER_WRITER,
                "writer-b": 0,
            },
            require_contiguous_sequences=True,
        )
        final = inspect_recovered_or_final_database(
            database,
            expected_event_count=base.EVENT_COUNT_PER_WRITER,
        )
        validate_permissions(database_root)
    except OSError as error:
        failure = base.SmokeError(
            "production append temporary filesystem operation failed"
        )
        failure.__cause__ = error
    except Exception as error:
        failure = error
    finally:
        try:
            temporary.cleanup()
        except OSError as error:
            if failure is None:
                failure = base.SmokeError(
                    "production append temporary database cleanup failed"
                )
                failure.__cause__ = error
    if failure is not None:
        raise failure
    try:
        cleanup_complete = not database_root.exists()
    except OSError as error:
        raise base.SmokeError(
            "could not verify production append database cleanup"
        ) from error
    if not cleanup_complete:
        raise base.SmokeError(
            "production append temporary database cleanup failed"
        )

    return {
        "abruptTermination": abrupt,
        "cleanup": "passed",
        "final": final,
        "finalReadbackProcess": "independent-production-store",
        "limitations": [
            "qa-forced-mid-transaction-database-cache-flush",
            "same-host-exact-child-process-termination-only",
            "not-natural-commit-timing-or-power-loss-evidence",
            "not-arbitrary-history-or-long-soak-evidence",
            "not-clean-machine-signed-distribution-or-device-evidence",
        ],
        "permissions": {
            "checkpointAndSQLiteFiles": "0600",
            "databaseRoot": "0700",
        },
        "recovered": recovered,
        "recoveryReadbackProcess": "independent-production-store",
        "retry": retry,
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "sourceInputs": source_inputs(),
        "status": "passed",
        "writePath": "SQLiteRuntimeChatEventStore.append",
    }


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return (base.canonical_json(value) + "\n").encode("ascii")


def qualify_repeatable(
    helper: Path,
    *,
    qualifier: Callable[[Path], dict[str, Any]] = qualify_once,
) -> tuple[dict[str, Any], dict[str, Any]]:
    first = qualifier(helper)
    second = qualifier(helper)
    first_bytes = canonical_bytes(first)
    second_bytes = canonical_bytes(second)
    if first != second or first_bytes != second_bytes:
        raise base.SmokeError(
            "production append recovery results are not byte-repeatable"
        )
    digest = hashlib.sha256(first_bytes).hexdigest()
    receipt = {
        "resultByteCount": len(first_bytes),
        "resultSha256": digest,
        "runs": [
            {
                "ordinal": ordinal,
                "resultByteCount": len(first_bytes),
                "resultSha256": digest,
            }
            for ordinal in (1, 2)
        ],
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": REPEATABILITY_SCOPE,
        "status": "passed",
    }
    return first, receipt


def publish_owner_only(path: Path, value: dict[str, Any]) -> None:
    payload = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        try:
            status = path.lstat()
            existing = path.read_bytes()
        except OSError as error:
            raise base.SmokeError(
                "production append result could not be inspected"
            ) from error
        if (
            not stat.S_ISREG(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o600
            or status.st_uid != os.getuid()
            or status.st_nlink != 1
            or existing != payload
        ):
            raise base.SmokeError(
                "refusing to replace different production append result bytes"
            )
        return
    temporary_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(temporary_path, flags, 0o600)
        written = 0
        while written < len(payload):
            count = os.write(descriptor, payload[written:])
            if count <= 0:
                raise OSError("short production append result write")
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
                raise base.SmokeError(
                    "concurrent production append result publication differed"
                )
    except OSError as error:
        raise base.SmokeError(
            "production append result publication failed"
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run repeated production-append SQLite abrupt-recovery qualification."
        )
    )
    parser.add_argument(
        "--helper",
        type=Path,
        help="Use an already-built QA helper executable.",
    )
    parser.add_argument(
        "--result",
        type=Path,
        help="Publish canonical owner-only result bytes.",
    )
    parser.add_argument(
        "--repeatability-receipt",
        type=Path,
        help="Publish the canonical two-run repeatability receipt.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        helper = arguments.helper
        if helper is None:
            helper = base.build_helper()
        elif not helper.is_absolute() or not helper.is_file() or helper.is_symlink():
            raise base.SmokeError("--helper must name an absolute regular file")
        if (arguments.result is None) != (arguments.repeatability_receipt is None):
            raise base.SmokeError(
                "result and repeatability receipt paths must be provided together"
            )
        result, receipt = qualify_repeatable(helper)
        if arguments.result is not None:
            publish_owner_only(
                Path(os.path.abspath(arguments.result)),
                result,
            )
            publish_owner_only(
                Path(os.path.abspath(arguments.repeatability_receipt)),
                receipt,
            )
        print(base.canonical_json({
            "repeatabilityReceipt": receipt,
            "result": result,
        }))
        return 0
    except base.SmokeError as error:
        print(
            f"Runtime-chat production append recovery smoke failed: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
