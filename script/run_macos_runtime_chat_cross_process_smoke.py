#!/usr/bin/env python3
"""Qualify two independent Runtime-chat SQLite writers against one database."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any, Protocol
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SWIFT = Path("/usr/bin/swift")
HELPER_PRODUCT = "RuntimeChatSQLiteCrossProcessQA"
DATABASE_FILENAME = "runtime-chat-events.sqlite"
GATE_FILENAME = "start-gate"
ABRUPT_CHECKPOINT_FILENAME = "abrupt-checkpoint-v1.json"
WRITERS = ("writer-a", "writer-b")
OWNER_BY_WRITER = {
    "writer-a": "qa-owner-a",
    "writer-b": "qa-owner-b",
}
EVENT_COUNT_PER_WRITER = 48
TOTAL_EVENT_COUNT = EVENT_COUNT_PER_WRITER * len(WRITERS)
ABRUPT_WRITER = "writer-a"
ABRUPT_COMMITTED_PREFIX_COUNT = 24
ABRUPT_INFLIGHT_EVENT_ID = "qa-writer-a-inflight-uncommitted-v1"
SHARED_SESSION_ID = "qa-shared-session"
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = "macos-runtime-chat-sqlite-cross-process-writers-v1"
ABRUPT_RESULT_SCOPE = (
    "macos-runtime-chat-sqlite-abrupt-process-recovery-v1"
)
BUILD_TIMEOUT_SECONDS = 240.0
PROCESS_TIMEOUT_SECONDS = 30.0
CHECKPOINT_TIMEOUT_SECONDS = 20.0
MAXIMUM_HELPER_OUTPUT_BYTES = 65_536
MAXIMUM_CHECKPOINT_BYTES = 4_096
SQLITE_ROLLBACK_JOURNAL_MAGIC = bytes.fromhex("d9d505f920a163d7")


class SmokeError(RuntimeError):
    """A bounded, user-safe qualification failure."""


class _OutputOverflow(SmokeError):
    """A child exceeded the hard combined stdout/stderr memory bound."""


class ProcessLike(Protocol):
    returncode: int | None
    pid: int
    stdout: Any
    stderr: Any

    def communicate(self, timeout: float | None = None) -> tuple[str, str]: ...

    def kill(self) -> None: ...

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


CommandRunner = Callable[
    [Sequence[str], float],
    subprocess.CompletedProcess[str],
]
PopenFactory = Callable[..., ProcessLike]
OutputCollector = Callable[
    [Sequence[ProcessLike], float, Callable[[], float]],
    list[tuple[str, str]],
]
GroupKiller = Callable[[int, int], None]
GroupIdentityReader = Callable[[int], int]


def _decode_output(payload: bytes | str) -> str:
    if isinstance(payload, str):
        return payload
    return payload.decode("utf-8", errors="replace")


def _combined_output_size(stdout: bytes | str, stderr: bytes | str) -> int:
    return len(
        stdout.encode("utf-8") if isinstance(stdout, str) else stdout
    ) + len(
        stderr.encode("utf-8") if isinstance(stderr, str) else stderr
    )


def _supports_streaming(process: ProcessLike) -> bool:
    return all(
        stream is not None and callable(getattr(stream, "fileno", None))
        for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None))
    )


def _collect_streaming_outputs(
    processes: Sequence[ProcessLike],
    timeout_seconds: float,
    monotonic: Callable[[], float],
) -> list[tuple[str, str]]:
    selector = selectors.DefaultSelector()
    buffers = [
        [bytearray(), bytearray()]
        for _process in processes
    ]
    combined_sizes = [0 for _process in processes]
    try:
        for process_index, process in enumerate(processes):
            selector.register(process.stdout, selectors.EVENT_READ, (process_index, 0))
            selector.register(process.stderr, selectors.EVENT_READ, (process_index, 1))
        deadline = monotonic() + timeout_seconds
        while selector.get_map():
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("bounded child process", timeout_seconds)
            for key, _events in selector.select(remaining):
                process_index, stream_index = key.data
                remaining_capacity = (
                    MAXIMUM_HELPER_OUTPUT_BYTES
                    - combined_sizes[process_index]
                )
                chunk = os.read(
                    key.fd,
                    min(8_192, remaining_capacity + 1),
                )
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                combined_sizes[process_index] += len(chunk)
                if combined_sizes[process_index] > MAXIMUM_HELPER_OUTPUT_BYTES:
                    raise _OutputOverflow("child output exceeded the hard memory bound")
                buffers[process_index][stream_index].extend(chunk)

        for process in processes:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("bounded child process", timeout_seconds)
            process.wait(timeout=remaining)
        return [
            (
                bytes(stdout).decode("utf-8", errors="replace"),
                bytes(stderr).decode("utf-8", errors="replace"),
            )
            for stdout, stderr in buffers
        ]
    finally:
        selector.close()


def _collect_process_outputs(
    processes: Sequence[ProcessLike],
    timeout_seconds: float,
    monotonic: Callable[[], float],
) -> list[tuple[str, str]]:
    if all(_supports_streaming(process) for process in processes):
        return _collect_streaming_outputs(processes, timeout_seconds, monotonic)

    # Injection-only compatibility for lightweight fake processes. Real
    # subprocesses always take the incremental selector path above.
    deadline = monotonic() + timeout_seconds
    outputs: list[tuple[str, str]] = []
    for process in processes:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("bounded child process", timeout_seconds)
        stdout, stderr = process.communicate(timeout=remaining)
        if _combined_output_size(stdout, stderr) > MAXIMUM_HELPER_OUTPUT_BYTES:
            raise _OutputOverflow("child output exceeded the hard memory bound")
        outputs.append((_decode_output(stdout), _decode_output(stderr)))
    return outputs


def _discard_and_close(stream: Any) -> None:
    if stream is None or not callable(getattr(stream, "fileno", None)):
        return
    try:
        descriptor = stream.fileno()
        os.set_blocking(descriptor, False)
        while os.read(descriptor, 8_192):
            pass
    except (BlockingIOError, OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _terminate_and_reap(
    processes: Sequence[ProcessLike],
    *,
    group_killer: GroupKiller = os.killpg,
) -> None:
    # Every phase visits every process even if an earlier cleanup action fails.
    for process in processes:
        try:
            running = process.poll() is None
        except Exception:
            running = True
        if not running:
            continue
        group_killed = False
        try:
            group_killer(process.pid, signal.SIGKILL)
            group_killed = True
        except Exception:
            pass
        if not group_killed:
            try:
                process.kill()
            except Exception:
                pass

    for process in processes:
        _discard_and_close(getattr(process, "stdout", None))
        _discard_and_close(getattr(process, "stderr", None))

    for process in processes:
        wait = getattr(process, "wait", None)
        if callable(wait):
            try:
                wait(timeout=2.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    wait(timeout=2.0)
                except Exception:
                    pass
            continue
        try:
            process.communicate(timeout=2.0)
        except Exception:
            pass


def _run_bounded_subprocess(
    command: Sequence[str],
    timeout_seconds: float,
    *,
    popen_factory: PopenFactory = subprocess.Popen,
    output_collector: OutputCollector = _collect_process_outputs,
    group_killer: GroupKiller = os.killpg,
    monotonic: Callable[[], float] = time.monotonic,
) -> subprocess.CompletedProcess[str]:
    process: ProcessLike | None = None
    try:
        process = popen_factory(
            list(command),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=closed_environment(),
            start_new_session=True,
        )
        stdout, stderr = output_collector(
            (process,),
            timeout_seconds,
            monotonic,
        )[0]
    except _OutputOverflow as error:
        if process is not None:
            _terminate_and_reap((process,), group_killer=group_killer)
        raise SmokeError("bounded helper command output exceeded the hard limit") from error
    except subprocess.TimeoutExpired as error:
        if process is not None:
            _terminate_and_reap((process,), group_killer=group_killer)
        raise SmokeError("bounded helper command timed out") from error
    except OSError as error:
        if process is not None:
            _terminate_and_reap((process,), group_killer=group_killer)
        raise SmokeError("bounded helper command failed") from error
    except Exception:
        if process is not None:
            _terminate_and_reap((process,), group_killer=group_killer)
        raise
    return subprocess.CompletedProcess(
        list(command),
        process.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def default_command_runner(
    command: Sequence[str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    return _run_bounded_subprocess(command, timeout_seconds)


def closed_environment(*, temporary: Path | None = None) -> dict[str, str]:
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }
    if temporary is not None:
        environment["TMPDIR"] = str(temporary)
    return environment


def build_helper(
    *,
    command_runner: CommandRunner = default_command_runner,
) -> Path:
    build = command_runner(
        (
            str(SWIFT),
            "build",
            "--package-path",
            str(ROOT),
            "--product",
            HELPER_PRODUCT,
        ),
        BUILD_TIMEOUT_SECONDS,
    )
    if build.returncode != 0:
        raise SmokeError("QA helper build failed")
    location = command_runner(
        (
            str(SWIFT),
            "build",
            "--package-path",
            str(ROOT),
            "--show-bin-path",
        ),
        BUILD_TIMEOUT_SECONDS,
    )
    if location.returncode != 0:
        raise SmokeError("QA helper location lookup failed")
    lines = location.stdout.splitlines()
    if len(lines) != 1:
        raise SmokeError("QA helper location output is not canonical")
    binary_directory = Path(lines[0])
    if not binary_directory.is_absolute():
        raise SmokeError("QA helper location is not absolute")
    helper = binary_directory / HELPER_PRODUCT
    if not helper.is_file() or helper.is_symlink():
        raise SmokeError("QA helper binary is missing")
    return helper


def helper_command(
    helper: Path,
    database_root: Path,
    *,
    mode: str,
    writer: str | None = None,
) -> tuple[str, ...]:
    if (
        not helper.is_absolute()
        or not database_root.is_absolute()
        or "\x00" in str(helper)
        or "\x00" in str(database_root)
    ):
        raise SmokeError("helper command paths must be absolute")
    if mode == "write" and writer in WRITERS:
        return (
            str(helper),
            "write",
            "--database-root",
            str(database_root),
            "--writer",
            writer,
        )
    if mode in {"abrupt-prefix", "resume"} and writer == ABRUPT_WRITER:
        return (
            str(helper),
            mode,
            "--database-root",
            str(database_root),
            "--writer",
            writer,
        )
    if mode == "read" and writer is None:
        return (
            str(helper),
            "read",
            "--database-root",
            str(database_root),
        )
    raise SmokeError("helper command mode is invalid")


def write_start_gate(database_root: Path) -> None:
    gate = database_root / GATE_FILENAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(gate, flags, 0o600)
    except OSError as error:
        raise SmokeError("could not create the writer start gate") from error
    try:
        os.write(descriptor, b"go\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        status = gate.lstat()
    except OSError as error:
        raise SmokeError("could not inspect the writer start gate") from error
    if (
        not stat.S_ISREG(status.st_mode)
        or stat.S_IMODE(status.st_mode) != 0o600
        or status.st_uid != os.getuid()
    ):
        raise SmokeError("writer start gate is not owner-only")


def run_writer_commands(
    commands: Sequence[Sequence[str]],
    *,
    database_root: Path,
    timeout_seconds: float = PROCESS_TIMEOUT_SECONDS,
    popen_factory: PopenFactory = subprocess.Popen,
    monotonic: Callable[[], float] = time.monotonic,
    gate_writer: Callable[[Path], None] = write_start_gate,
    output_collector: OutputCollector = _collect_process_outputs,
    group_killer: GroupKiller = os.killpg,
) -> tuple[dict[str, Any], ...]:
    if len(commands) != 2 or timeout_seconds <= 0:
        raise SmokeError("exactly two bounded writer commands are required")
    processes: list[ProcessLike] = []
    try:
        for command in commands:
            processes.append(
                popen_factory(
                    list(command),
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                    env=closed_environment(temporary=database_root),
                    start_new_session=True,
                )
            )
        gate_writer(database_root)
        outputs = output_collector(processes, timeout_seconds, monotonic)
    except _OutputOverflow as error:
        _terminate_and_reap(processes, group_killer=group_killer)
        raise SmokeError("writer helper output exceeded the hard limit") from error
    except (OSError, subprocess.TimeoutExpired) as error:
        _terminate_and_reap(processes, group_killer=group_killer)
        raise SmokeError("writer helpers did not finish within the bound") from error
    except Exception:
        _terminate_and_reap(processes, group_killer=group_killer)
        raise

    results: list[dict[str, Any]] = []
    for process, (stdout, stderr) in zip(processes, outputs):
        if process.returncode != 0 or stderr:
            raise SmokeError("a writer helper failed")
        results.append(parse_helper_json(stdout, label="writer"))
    return tuple(results)


def parse_helper_json(payload: str, *, label: str) -> dict[str, Any]:
    encoded = payload.encode("utf-8")
    if not encoded or len(encoded) > MAXIMUM_HELPER_OUTPUT_BYTES:
        raise SmokeError(f"{label} helper output size is invalid")
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as error:
        raise SmokeError(f"{label} helper output is not JSON") from error
    if type(decoded) is not dict:
        raise SmokeError(f"{label} helper output is not an object")
    return decoded


def _validated_ordinal_range(
    writer: str,
    start: int,
    end: int,
) -> range:
    if (
        writer not in WRITERS
        or type(start) is not int
        or type(end) is not int
        or start < 0
        or end < start
        or end > EVENT_COUNT_PER_WRITER
    ):
        raise SmokeError("expected event ordinal range is invalid")
    return range(start, end)


def expected_ids(
    writer: str,
    start: int = 0,
    end: int = EVENT_COUNT_PER_WRITER,
) -> list[str]:
    return [
        f"qa-{writer}-event-{ordinal:04d}"
        for ordinal in _validated_ordinal_range(writer, start, end)
    ]


def expected_requests(
    writer: str,
    start: int = 0,
    end: int = EVENT_COUNT_PER_WRITER,
) -> list[str]:
    return [
        f"qa-{writer}-request-{ordinal:04d}"
        for ordinal in _validated_ordinal_range(writer, start, end)
    ]


def expected_contents(
    writer: str,
    start: int = 0,
    end: int = EVENT_COUNT_PER_WRITER,
) -> list[str]:
    return [
        f"{writer}-message-{ordinal:04d}"
        for ordinal in _validated_ordinal_range(writer, start, end)
    ]


def validate_writer_results(results: Sequence[dict[str, Any]]) -> None:
    expected = {
        writer: {
            "eventCount": EVENT_COUNT_PER_WRITER,
            "status": "passed",
            "writer": writer,
        }
        for writer in WRITERS
    }
    observed: dict[str, dict[str, Any]] = {}
    for result in results:
        if set(result) != {"eventCount", "status", "writer"}:
            raise SmokeError("writer helper result fields are not canonical")
        writer = result.get("writer")
        if type(writer) is not str or writer in observed:
            raise SmokeError("writer helper identity is invalid")
        observed[writer] = result
    if observed != expected:
        raise SmokeError("writer helper results differ from the exact fixture")


def _read_owner_only_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise SmokeError(f"{label} could not be opened") from error
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > maximum_bytes
        ):
            raise SmokeError(f"{label} identity is invalid")
        payload = bytearray()
        while len(payload) <= maximum_bytes:
            chunk = os.read(
                descriptor,
                min(4_096, maximum_bytes + 1 - len(payload)),
            )
            if not chunk:
                break
            payload.extend(chunk)
        after = os.fstat(descriptor)
        if (
            len(payload) != before.st_size
            or len(payload) > maximum_bytes
            or (before.st_dev, before.st_ino, before.st_mode, before.st_size)
            != (after.st_dev, after.st_ino, after.st_mode, after.st_size)
        ):
            raise SmokeError(f"{label} changed while being read")
        return bytes(payload)
    finally:
        os.close(descriptor)


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SmokeError("abrupt checkpoint repeats a JSON key")
        result[key] = value
    return result


def validate_abrupt_checkpoint(payload: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SmokeError("abrupt checkpoint is not canonical JSON") from error
    expected = {
        "committedPrefixCount": ABRUPT_COMMITTED_PREFIX_COUNT,
        "databaseCacheFlushed": True,
        "inFlightEventID": ABRUPT_INFLIGHT_EVENT_ID,
        "insideTransactionEventCount": ABRUPT_COMMITTED_PREFIX_COUNT + 1,
        "insideTransactionFTSEventCount": ABRUPT_COMMITTED_PREFIX_COUNT + 1,
        "insideTransactionMutationRevision": ABRUPT_COMMITTED_PREFIX_COUNT + 1,
        "insideTransactionValidatedRevision": ABRUPT_COMMITTED_PREFIX_COUNT,
        "journalMode": "delete",
        "schemaVersion": 1,
        "status": "ready-for-abrupt-termination",
        "transactionOpen": True,
        "writer": ABRUPT_WRITER,
    }
    if (
        type(decoded) is not dict
        or decoded != expected
        or any(
            type(decoded[key]) is not type(value)
            for key, value in expected.items()
        )
    ):
        raise SmokeError("abrupt checkpoint differs from the exact fixture")
    return decoded


def wait_for_abrupt_checkpoint(
    process: ProcessLike,
    database_root: Path,
    *,
    timeout_seconds: float = CHECKPOINT_TIMEOUT_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise SmokeError("abrupt checkpoint timeout is invalid")
    checkpoint = database_root / ABRUPT_CHECKPOINT_FILENAME
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if checkpoint.exists() or checkpoint.is_symlink():
            return validate_abrupt_checkpoint(
                _read_owner_only_regular_file(
                    checkpoint,
                    maximum_bytes=MAXIMUM_CHECKPOINT_BYTES,
                    label="abrupt checkpoint",
                )
            )
        if process.poll() is not None:
            raise SmokeError(
                "abrupt helper exited before publishing its checkpoint"
            )
        sleeper(min(0.01, max(0.0, deadline - monotonic())))
    raise SmokeError("abrupt helper checkpoint timed out")


def observe_hot_rollback_journal(database_root: Path) -> dict[str, Any]:
    journal = database_root / f"{DATABASE_FILENAME}-journal"
    payload = _read_owner_only_regular_file(
        journal,
        maximum_bytes=8 * 1024 * 1024,
        label="SQLite rollback journal",
    )
    if len(payload) <= 512 or payload[:8] != SQLITE_ROLLBACK_JOURNAL_MAGIC:
        raise SmokeError("SQLite rollback journal is not hot")
    (
        page_record_count,
        _checksum_nonce,
        initial_database_page_count,
        sector_size,
        page_size,
    ) = struct.unpack(">IIIII", payload[8:28])
    if (
        page_record_count == 0
        or initial_database_page_count == 0
        or sector_size < 512
        or sector_size > 65_536
        or sector_size & (sector_size - 1)
        or page_size < 512
        or page_size > 65_536
        or page_size & (page_size - 1)
        or len(payload)
        < sector_size + page_record_count * (page_size + 8)
    ):
        raise SmokeError("SQLite rollback journal header is malformed")
    return {
        "journalMode": "delete",
        "hotJournalHeaderObserved": True,
        "ownerOnlyMode": "0600",
        "pageRecordCountPositive": True,
        "pageSize": page_size,
        "sectorSize": sector_size,
    }


def observe_unrecovered_dirty_database(
    database_root: Path,
) -> dict[str, Any]:
    database = database_root / DATABASE_FILENAME
    if not database.is_file() or database.is_symlink():
        raise SmokeError("unrecovered SQLite database is missing")
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
                SELECT mutation_revision, validated_revision
                FROM runtime_chat_append_state
                WHERE singleton = 1
                """
            ).fetchall()
            in_flight_event_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM runtime_chat_events
                WHERE event_id = ?
                """,
                (ABRUPT_INFLIGHT_EVENT_ID,),
            ).fetchone()
            in_flight_fts_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM runtime_chat_event_fts_v2
                WHERE event_id = ?
                """,
                (ABRUPT_INFLIGHT_EVENT_ID,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise SmokeError(
            "unrecovered dirty-database inspection failed"
        ) from error
    expected_dirty_count = ABRUPT_COMMITTED_PREFIX_COUNT + 1
    if (
        event_count != (expected_dirty_count,)
        or fts_count != (expected_dirty_count,)
        or append_state
        != [(
            expected_dirty_count,
            ABRUPT_COMMITTED_PREFIX_COUNT,
        )]
        or in_flight_event_count != (1,)
        or in_flight_fts_count != (1,)
    ):
        raise SmokeError(
            "unrecovered dirty database does not contain the exact fixture"
        )
    return {
        "appendStateMutationRevision": expected_dirty_count,
        "appendStateValidatedRevision": ABRUPT_COMMITTED_PREFIX_COUNT,
        "eventCount": expected_dirty_count,
        "ftsEventCount": expected_dirty_count,
        "immutableReadIgnoredJournal": True,
        "inFlightEventAndFTSPresent": True,
    }


def run_abrupt_prefix(
    helper: Path,
    database_root: Path,
    *,
    popen_factory: PopenFactory = subprocess.Popen,
    checkpoint_waiter: Callable[
        [ProcessLike, Path],
        dict[str, Any],
    ] = wait_for_abrupt_checkpoint,
    journal_observer: Callable[
        [Path],
        dict[str, Any],
    ] = observe_hot_rollback_journal,
    dirty_database_observer: Callable[
        [Path],
        dict[str, Any],
    ] = observe_unrecovered_dirty_database,
    output_collector: OutputCollector = _collect_process_outputs,
    group_killer: GroupKiller = os.killpg,
    group_identity_reader: GroupIdentityReader = os.getpgid,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    process: ProcessLike | None = None
    group_identity_confirmed = False

    def cleanup_group_killer(pid: int, caught_signal: int) -> None:
        if not group_identity_confirmed:
            raise ProcessLookupError()
        group_killer(pid, caught_signal)

    try:
        process = popen_factory(
            list(
                helper_command(
                    helper,
                    database_root,
                    mode="abrupt-prefix",
                    writer=ABRUPT_WRITER,
                )
            ),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=closed_environment(temporary=database_root),
            start_new_session=True,
        )
        checkpoint = checkpoint_waiter(process, database_root)
        if process.poll() is not None:
            raise SmokeError(
                "abrupt helper exited before the termination signal"
            )
        if group_identity_reader(process.pid) != process.pid:
            raise SmokeError(
                "abrupt helper does not own its exact process group"
            )
        group_identity_confirmed = True
        group_killer(process.pid, signal.SIGKILL)
        stdout, stderr = output_collector(
            (process,),
            PROCESS_TIMEOUT_SECONDS,
            monotonic,
        )[0]
        process.wait(timeout=2.0)
        if (
            process.returncode != -signal.SIGKILL
            or stdout
            or stderr
        ):
            raise SmokeError("abrupt helper termination result differs")
        journal = journal_observer(database_root)
        dirty_database = dirty_database_observer(database_root)
        if journal_observer(database_root) != journal:
            raise SmokeError(
                "SQLite hot journal changed during immutable inspection"
            )
    except _OutputOverflow as error:
        if process is not None:
            _terminate_and_reap(
                (process,),
                group_killer=cleanup_group_killer,
            )
        raise SmokeError("abrupt helper output exceeded the hard limit") from error
    except (OSError, subprocess.TimeoutExpired) as error:
        if process is not None:
            _terminate_and_reap(
                (process,),
                group_killer=cleanup_group_killer,
            )
        raise SmokeError(
            "abrupt helper could not be terminated and reaped exactly"
        ) from error
    except Exception:
        if process is not None:
            _terminate_and_reap(
                (process,),
                group_killer=cleanup_group_killer,
            )
        raise
    return {
        "checkpoint": checkpoint,
        "dirtyDatabaseBeforeRecovery": dirty_database,
        "journal": journal,
        "processGroup": "new-session-exact-child-only",
        "terminationSignal": "SIGKILL",
        "writerProcessReapedBeforeJournalObservation": True,
    }


def run_resume_writer(
    helper: Path,
    database_root: Path,
    *,
    command_runner: CommandRunner = default_command_runner,
) -> dict[str, Any]:
    completed = command_runner(
        helper_command(
            helper,
            database_root,
            mode="resume",
            writer=ABRUPT_WRITER,
        ),
        PROCESS_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0 or completed.stderr:
        raise SmokeError("resume writer helper failed")
    result = parse_helper_json(completed.stdout, label="resume writer")
    expected = {
        "endExclusive": EVENT_COUNT_PER_WRITER,
        "eventCount": (
            EVENT_COUNT_PER_WRITER - ABRUPT_COMMITTED_PREFIX_COUNT
        ),
        "startOrdinal": ABRUPT_COMMITTED_PREFIX_COUNT,
        "status": "passed",
        "writer": ABRUPT_WRITER,
    }
    if result != expected or any(
        type(result.get(key)) is not type(value)
        for key, value in expected.items()
    ):
        raise SmokeError("resume writer result differs from the exact fixture")
    return result


def run_readback(
    helper: Path,
    database_root: Path,
    *,
    command_runner: CommandRunner = default_command_runner,
) -> dict[str, Any]:
    completed = command_runner(
        helper_command(helper, database_root, mode="read"),
        PROCESS_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0 or completed.stderr:
        raise SmokeError("independent readback helper failed")
    return parse_helper_json(completed.stdout, label="readback")


def validate_readback_counts(
    readback: dict[str, Any],
    *,
    expected_counts: dict[str, int],
    require_contiguous_sequences: bool = False,
) -> None:
    if set(expected_counts) != set(WRITERS) or any(
        type(count) is not int
        or count < 0
        or count > EVENT_COUNT_PER_WRITER
        for count in expected_counts.values()
    ):
        raise SmokeError("readback expected counts are invalid")
    required_fields = {
        "hostWideSessionCount",
        "missingOwnerSessionCount",
        "ownerProjections",
        "rows",
        "status",
        "unownedSessionCount",
    }
    if set(readback) != required_fields or readback.get("status") != "passed":
        raise SmokeError("readback result fields are not canonical")
    if (
        type(readback["hostWideSessionCount"]) is not int
        or readback["hostWideSessionCount"]
        != sum(count > 0 for count in expected_counts.values())
        or type(readback["missingOwnerSessionCount"]) is not int
        or readback["missingOwnerSessionCount"] != 0
        or type(readback["unownedSessionCount"]) is not int
        or readback["unownedSessionCount"] != 0
    ):
        raise SmokeError("owner/session projection isolation failed")

    projections = readback["ownerProjections"]
    if type(projections) is not list or len(projections) != len(WRITERS):
        raise SmokeError("owner projections are incomplete")
    by_owner: dict[str, dict[str, Any]] = {}
    for projection in projections:
        if type(projection) is not dict or set(projection) != {
            "messageContents",
            "ownerDeviceID",
            "sessions",
        }:
            raise SmokeError("owner projection fields are invalid")
        owner = projection["ownerDeviceID"]
        if type(owner) is not str or owner in by_owner:
            raise SmokeError("owner projection identity is invalid")
        by_owner[owner] = projection
    for writer in WRITERS:
        owner = OWNER_BY_WRITER[writer]
        projection = by_owner.get(owner)
        if projection is None:
            raise SmokeError("owner projection is missing")
        expected_count = expected_counts[writer]
        expected_sessions = (
            [{
                "messageCount": expected_count,
                "sessionID": SHARED_SESSION_ID,
            }]
            if expected_count
            else []
        )
        if projection["sessions"] != expected_sessions:
            raise SmokeError("shared session projection is not owner-isolated")
        if projection["messageContents"] != expected_contents(
            writer,
            end=expected_count,
        ):
            raise SmokeError("owner message projection order differs")

    rows = readback["rows"]
    expected_total = sum(expected_counts.values())
    if type(rows) is not list or len(rows) != expected_total:
        raise SmokeError("readback event count differs")
    required_row_fields = {
        "eventID",
        "kind",
        "ownerDeviceID",
        "requestID",
        "sequence",
        "sessionID",
    }
    all_ids: list[str] = []
    previous_sequence = 0
    rows_by_writer: dict[str, list[dict[str, Any]]] = {
        writer: [] for writer in WRITERS
    }
    writer_by_owner = {
        owner: writer for writer, owner in OWNER_BY_WRITER.items()
    }
    for row in rows:
        if type(row) is not dict or set(row) != required_row_fields:
            raise SmokeError("readback event row fields are invalid")
        sequence = row["sequence"]
        if type(sequence) is not int or sequence <= previous_sequence:
            raise SmokeError("SQLite event sequence is not strictly ordered")
        if require_contiguous_sequences and sequence != previous_sequence + 1:
            raise SmokeError("SQLite event sequence is not contiguous")
        previous_sequence = sequence
        if row["kind"] != "request" or row["sessionID"] != SHARED_SESSION_ID:
            raise SmokeError("readback event shape differs")
        writer = writer_by_owner.get(row["ownerDeviceID"])
        if writer is None:
            raise SmokeError("readback event owner differs")
        rows_by_writer[writer].append(row)
        all_ids.append(row["eventID"])

    expected_all_ids = sorted(
        event_id
        for writer in WRITERS
        for event_id in expected_ids(
            writer,
            end=expected_counts[writer],
        )
    )
    if len(set(all_ids)) != expected_total or sorted(all_ids) != expected_all_ids:
        raise SmokeError("event sets are not disjoint and exactly once")
    for writer in WRITERS:
        expected_count = expected_counts[writer]
        if [row["eventID"] for row in rows_by_writer[writer]] != expected_ids(
            writer,
            end=expected_count,
        ):
            raise SmokeError("per-writer append ordering differs")
        if [row["requestID"] for row in rows_by_writer[writer]] != expected_requests(
            writer,
            end=expected_count,
        ):
            raise SmokeError("per-writer request ordering differs")


def validate_readback(readback: dict[str, Any]) -> None:
    validate_readback_counts(
        readback,
        expected_counts={
            writer: EVENT_COUNT_PER_WRITER
            for writer in WRITERS
        },
    )


def sqlite_integrity(
    database: Path,
    *,
    expected_event_count: int = TOTAL_EVENT_COUNT,
) -> None:
    if type(expected_event_count) is not int or expected_event_count < 0:
        raise SmokeError("expected SQLite event count is invalid")
    if not database.is_file() or database.is_symlink():
        raise SmokeError("SQLite database is missing")
    uri = f"file:{quote(str(database))}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchall()
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            count = connection.execute(
                "SELECT COUNT(*) FROM runtime_chat_events"
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise SmokeError("SQLite integrity inspection failed") from error
    if (
        integrity != [("ok",)]
        or foreign_keys != []
        or count != (expected_event_count,)
    ):
        raise SmokeError("SQLite integrity result differs")


def sqlite_abrupt_recovery_evidence(
    database: Path,
    *,
    expected_event_count: int,
) -> dict[str, Any]:
    if (
        type(expected_event_count) is not int
        or expected_event_count < 0
        or expected_event_count > EVENT_COUNT_PER_WRITER
        or not database.is_file()
        or database.is_symlink()
    ):
        raise SmokeError("abrupt-recovery SQLite input is invalid")
    uri = f"file:{quote(str(database))}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            connection.execute("PRAGMA query_only = ON")
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()
            foreign_keys = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            event_rows = connection.execute(
                """
                SELECT sequence, event_id
                FROM runtime_chat_events
                ORDER BY sequence ASC
                """
            ).fetchall()
            fts_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT event_id
                    FROM runtime_chat_event_fts_v2
                    ORDER BY event_id ASC
                    """
                ).fetchall()
            ]
            append_state = connection.execute(
                """
                SELECT mutation_revision, validated_revision
                FROM runtime_chat_append_state
                WHERE singleton = 1
                """
            ).fetchall()
            in_flight_event_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM runtime_chat_events
                WHERE event_id = ?
                """,
                (ABRUPT_INFLIGHT_EVENT_ID,),
            ).fetchone()
            in_flight_fts_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM runtime_chat_event_fts_v2
                WHERE event_id = ?
                """,
                (ABRUPT_INFLIGHT_EVENT_ID,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise SmokeError(
            "abrupt-recovery SQLite inspection failed"
        ) from error

    expected_event_ids = expected_ids(
        ABRUPT_WRITER,
        end=expected_event_count,
    )
    if (
        integrity != [("ok",)]
        or foreign_keys != []
        or event_rows
        != list(enumerate(expected_event_ids, start=1))
        or fts_ids != sorted(expected_event_ids)
        or append_state
        != [(expected_event_count, expected_event_count)]
        or in_flight_event_count != (0,)
        or in_flight_fts_count != (0,)
    ):
        raise SmokeError(
            "abrupt-recovery SQLite state differs from the exact fixture"
        )
    journal = database.with_name(f"{database.name}-journal")
    residual_journal_header_zeroed = False
    if journal.exists() or journal.is_symlink():
        residual = _read_owner_only_regular_file(
            journal,
            maximum_bytes=8 * 1024 * 1024,
            label="recovered SQLite rollback journal",
        )
        if (
            len(residual) < len(SQLITE_ROLLBACK_JOURNAL_MAGIC)
            or residual[: len(SQLITE_ROLLBACK_JOURNAL_MAGIC)]
            != b"\0" * len(SQLITE_ROLLBACK_JOURNAL_MAGIC)
        ):
            raise SmokeError(
                "SQLite rollback journal remained hot after recovery"
            )
        residual_journal_header_zeroed = True
    return {
        "appendStateRevision": expected_event_count,
        "eventCount": expected_event_count,
        "ftsEventCount": expected_event_count,
        "hotJournalCleared": True,
        "inFlightEventAndFTSAbsent": True,
        "integrityCheck": "ok",
        "residualJournalHeaderZeroed": residual_journal_header_zeroed,
        "sequencesContiguous": True,
    }


def validate_owner_only_permissions(database_root: Path) -> None:
    try:
        root_status = database_root.lstat()
        if (
            not stat.S_ISDIR(root_status.st_mode)
            or stat.S_IMODE(root_status.st_mode) != 0o700
            or root_status.st_uid != os.getuid()
        ):
            raise SmokeError("database root is not owner-only")
        allowed = {
            DATABASE_FILENAME,
            DATABASE_FILENAME + "-journal",
            DATABASE_FILENAME + "-shm",
            DATABASE_FILENAME + "-wal",
            ABRUPT_CHECKPOINT_FILENAME,
            GATE_FILENAME,
        }
        for child in database_root.iterdir():
            status = child.lstat()
            if (
                child.name not in allowed
                or not stat.S_ISREG(status.st_mode)
                or stat.S_IMODE(status.st_mode) != 0o600
                or status.st_uid != os.getuid()
                or status.st_nlink != 1
            ):
                raise SmokeError("database-root file is not owner-only")
    except OSError as error:
        raise SmokeError("could not inspect database-root permissions") from error


def qualify(
    helper: Path,
    *,
    command_runner: CommandRunner = default_command_runner,
    popen_factory: PopenFactory = subprocess.Popen,
) -> dict[str, Any]:
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        temporary = tempfile.TemporaryDirectory(
            prefix="aetherlink-runtime-chat-cross-process-"
        )
        database_root = Path(temporary.name)
        os.chmod(database_root, 0o700)
    except OSError as error:
        if temporary is not None:
            try:
                temporary.cleanup()
            except OSError:
                pass
        raise SmokeError("could not prepare the temporary database root") from error

    failure: Exception | None = None
    try:
        commands = [
            helper_command(
                helper,
                database_root,
                mode="write",
                writer=writer,
            )
            for writer in WRITERS
        ]
        writer_results = run_writer_commands(
            commands,
            database_root=database_root,
            popen_factory=popen_factory,
        )
        validate_writer_results(writer_results)
        readback = run_readback(
            helper,
            database_root,
            command_runner=command_runner,
        )
        validate_readback(readback)
        database = database_root / DATABASE_FILENAME
        sqlite_integrity(database)
        validate_owner_only_permissions(database_root)
    except OSError as error:
        failure = SmokeError("temporary filesystem operation failed")
        failure.__cause__ = error
    except Exception as error:
        failure = error
    finally:
        try:
            temporary.cleanup()
        except OSError as error:
            if failure is None:
                failure = SmokeError("temporary database cleanup failed")
                failure.__cause__ = error
    if failure is not None:
        raise failure
    try:
        cleanup_complete = not database_root.exists()
    except OSError as error:
        raise SmokeError("could not verify temporary database cleanup") from error
    if not cleanup_complete:
        raise SmokeError("temporary database cleanup failed")
    return {
        "cleanup": "passed",
        "eventCount": TOTAL_EVENT_COUNT,
        "eventSets": "disjoint-exactly-once",
        "eventsPerWriter": EVENT_COUNT_PER_WRITER,
        "ownerSessionIsolation": "passed",
        "perWriterAppendOrdering": "passed",
        "permissions": {
            "databaseRoot": "0700",
            "sqliteFiles": "0600",
        },
        "readbackProcess": "independent",
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "sqliteIntegrity": "ok",
        "status": "passed",
        "writerProcesses": len(WRITERS),
    }


def qualify_abrupt_recovery(
    helper: Path,
    *,
    command_runner: CommandRunner = default_command_runner,
    popen_factory: PopenFactory = subprocess.Popen,
) -> dict[str, Any]:
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        temporary = tempfile.TemporaryDirectory(
            prefix="aetherlink-runtime-chat-abrupt-recovery-"
        )
        database_root = Path(temporary.name)
        os.chmod(database_root, 0o700)
    except OSError as error:
        if temporary is not None:
            try:
                temporary.cleanup()
            except OSError:
                pass
        raise SmokeError(
            "could not prepare the abrupt-recovery database root"
        ) from error

    failure: Exception | None = None
    try:
        abrupt = run_abrupt_prefix(
            helper,
            database_root,
            popen_factory=popen_factory,
        )
        recovered_readback = run_readback(
            helper,
            database_root,
            command_runner=command_runner,
        )
        validate_readback_counts(
            recovered_readback,
            expected_counts={
                ABRUPT_WRITER: ABRUPT_COMMITTED_PREFIX_COUNT,
                "writer-b": 0,
            },
            require_contiguous_sequences=True,
        )
        database = database_root / DATABASE_FILENAME
        recovered = sqlite_abrupt_recovery_evidence(
            database,
            expected_event_count=ABRUPT_COMMITTED_PREFIX_COUNT,
        )
        resume = run_resume_writer(
            helper,
            database_root,
            command_runner=command_runner,
        )
        final_readback = run_readback(
            helper,
            database_root,
            command_runner=command_runner,
        )
        validate_readback_counts(
            final_readback,
            expected_counts={
                ABRUPT_WRITER: EVENT_COUNT_PER_WRITER,
                "writer-b": 0,
            },
            require_contiguous_sequences=True,
        )
        final = sqlite_abrupt_recovery_evidence(
            database,
            expected_event_count=EVENT_COUNT_PER_WRITER,
        )
        validate_owner_only_permissions(database_root)
    except OSError as error:
        failure = SmokeError("temporary filesystem operation failed")
        failure.__cause__ = error
    except Exception as error:
        failure = error
    finally:
        try:
            temporary.cleanup()
        except OSError as error:
            if failure is None:
                failure = SmokeError(
                    "temporary abrupt-recovery database cleanup failed"
                )
                failure.__cause__ = error
    if failure is not None:
        raise failure
    try:
        cleanup_complete = not database_root.exists()
    except OSError as error:
        raise SmokeError(
            "could not verify abrupt-recovery database cleanup"
        ) from error
    if not cleanup_complete:
        raise SmokeError("temporary abrupt-recovery database cleanup failed")
    return {
        "abruptTermination": abrupt,
        "cleanup": "passed",
        "committedPrefixCount": ABRUPT_COMMITTED_PREFIX_COUNT,
        "committedPrefixWritePath": (
            "production-SQLiteRuntimeChatEventStore"
        ),
        "final": final,
        "finalReadbackProcess": "independent",
        "inFlightEventID": ABRUPT_INFLIGHT_EVENT_ID,
        "inFlightTransactionWritePath": "qa-raw-sql-event-plus-fts-v1",
        "limitations": [
            "same-host-abrupt-child-process-termination-only",
            "not-production-append-crash-point",
            "not-power-loss-or-kernel-crash-evidence",
            "not-arbitrary-history-or-long-soak-evidence",
            "not-clean-machine-signed-distribution-or-device-evidence",
        ],
        "permissions": {
            "checkpointAndSQLiteFiles": "0600",
            "databaseRoot": "0700",
        },
        "recovered": recovered,
        "recoveryReadbackProcess": "independent",
        "resume": resume,
        "resumeWritePath": "production-SQLiteRuntimeChatEventStore",
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": ABRUPT_RESULT_SCOPE,
        "status": "passed",
    }


def canonical_json(result: dict[str, Any]) -> str:
    return json.dumps(
        result,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def publish_result(path: Path, result: dict[str, Any]) -> None:
    payload = (canonical_json(result) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if (
            path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == payload
        ):
            return
        raise SmokeError(
            "refusing to replace different cross-process result bytes"
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
                raise SmokeError(
                    "concurrent cross-process result publication differed"
                )
    finally:
        temporary_path.unlink(missing_ok=True)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the macOS Runtime-chat SQLite cross-process smoke."
    )
    parser.add_argument(
        "--helper",
        type=Path,
        help="Use an already-built QA helper executable.",
    )
    parser.add_argument(
        "--abrupt-recovery",
        action="store_true",
        help=(
            "Run the committed-prefix, abrupt child termination, recovery, "
            "and exact resume qualification."
        ),
    )
    parser.add_argument(
        "--result",
        type=Path,
        help="Publish canonical result bytes without replacing different bytes.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        helper = arguments.helper
        if helper is None:
            helper = build_helper()
        elif not helper.is_absolute() or not helper.is_file() or helper.is_symlink():
            raise SmokeError("--helper must name an absolute regular file")
        result = (
            qualify_abrupt_recovery(helper)
            if arguments.abrupt_recovery
            else qualify(helper)
        )
        if arguments.result is not None:
            publish_result(arguments.result.resolve(), result)
        print(canonical_json(result))
        return 0
    except SmokeError as error:
        print(f"Runtime-chat SQLite cross-process smoke failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
