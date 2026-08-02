#!/usr/bin/env python3
"""Tests for production-append abrupt-recovery orchestration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest import mock

from script import (
    run_macos_runtime_chat_production_append_abrupt_recovery_smoke as smoke,
)


class FakeProcess:
    def __init__(self, *, pid: int = 72_001) -> None:
        self.pid = pid
        self.returncode: int | None = None
        self.stdout = None
        self.stderr = None
        self.killed = False
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-production-append", timeout)
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -signal.SIGKILL


class ProductionAppendAbruptRecoverySmokeTests(unittest.TestCase):
    def test_production_append_command_is_exact(self) -> None:
        self.assertEqual(
            smoke.production_append_command(
                Path("/tmp/helper"),
                Path("/tmp/database-root"),
            ),
            (
                "/tmp/helper",
                "production-append",
                "--database-root",
                "/tmp/database-root",
                "--writer",
                "writer-a",
            ),
        )
        with self.assertRaises(smoke.base.SmokeError):
            smoke.production_append_command(
                Path("relative-helper"),
                Path("/tmp/database-root"),
            )

    def test_checkpoint_requires_canonical_exact_types(self) -> None:
        expected = smoke.expected_checkpoint()
        payload = smoke.canonical_bytes(expected)
        self.assertEqual(smoke.validate_checkpoint(payload), expected)

        boolean_alias = dict(expected)
        boolean_alias["databaseCacheFlushed"] = 1
        with self.assertRaises(smoke.base.SmokeError):
            smoke.validate_checkpoint(smoke.canonical_bytes(boolean_alias))

        duplicate = payload[:-2] + b',"status":"duplicate"}\n'
        with self.assertRaises(smoke.base.SmokeError):
            smoke.validate_checkpoint(duplicate)

    def test_abrupt_process_kill_requires_exact_group_and_stable_bytes(self) -> None:
        process = FakeProcess()
        checkpoint = smoke.expected_checkpoint()
        checkpoint_bytes = smoke.canonical_bytes(checkpoint)
        journal = {
            "hotJournalHeaderObserved": True,
            "journalMode": "delete",
            "ownerOnlyMode": "0600",
            "pageRecordCountPositive": True,
            "pageSize": 4_096,
            "sectorSize": 512,
        }
        dirty = {
            "appendStateMutationRevision": 1,
            "appendStateValidatedRevision": 1,
            "eventAndFTSPresent": True,
            "eventCount": 1,
            "ftsEventCount": 1,
            "immutableReadIgnoredJournal": True,
            "searchProjectionVersion": 2,
        }
        killed: list[tuple[int, int]] = []

        def group_killer(pid: int, caught_signal: int) -> None:
            killed.append((pid, caught_signal))
            process.returncode = -signal.SIGKILL

        with tempfile.TemporaryDirectory() as temporary_name, mock.patch.object(
            smoke.base,
            "observe_hot_rollback_journal",
            return_value=journal,
        ), mock.patch.object(
            smoke,
            "_journal_bytes",
            return_value=b"stable-journal",
        ), mock.patch.object(
            smoke,
            "observe_dirty_database",
            return_value=dirty,
        ), mock.patch.object(
            smoke.base,
            "_read_owner_only_regular_file",
            return_value=checkpoint_bytes,
        ):
            result = smoke.run_abrupt_production_append(
                Path("/tmp/helper"),
                Path(temporary_name),
                popen_factory=lambda *_args, **_kwargs: process,
                checkpoint_waiter=lambda *_args: (
                    checkpoint,
                    checkpoint_bytes,
                ),
                group_killer=group_killer,
                group_identity_reader=lambda pid: pid,
                output_collector=lambda *_args: [(b"", b"")],
                monotonic=lambda: 1.0,
            )

        self.assertEqual(killed, [(process.pid, signal.SIGKILL)])
        self.assertEqual(result["terminationSignal"], "SIGKILL")
        self.assertTrue(result["writerProcessReaped"])
        self.assertTrue(result["journal"]["bytesStableAcrossSignal"])
        self.assertEqual(process.wait_calls, [2.0])

    def test_group_mismatch_never_calls_group_killer(self) -> None:
        process = FakeProcess()
        group_kills: list[tuple[int, int]] = []
        with tempfile.TemporaryDirectory() as temporary_name:
            with self.assertRaisesRegex(
                smoke.base.SmokeError,
                "exact process group",
            ):
                smoke.run_abrupt_production_append(
                    Path("/tmp/helper"),
                    Path(temporary_name),
                    popen_factory=lambda *_args, **_kwargs: process,
                    checkpoint_waiter=lambda *_args: (
                        smoke.expected_checkpoint(),
                        smoke.canonical_bytes(smoke.expected_checkpoint()),
                    ),
                    group_killer=lambda pid, caught_signal: group_kills.append(
                        (pid, caught_signal)
                    ),
                    group_identity_reader=lambda pid: pid + 1,
                )
        self.assertEqual(group_kills, [])
        self.assertTrue(process.killed)

    def test_exact_retry_rejects_boolean_count_alias(self) -> None:
        good = subprocess.CompletedProcess(
            args=("helper",),
            returncode=0,
            stdout=json.dumps({
                "eventCount": 48,
                "status": "passed",
                "writer": "writer-a",
            }),
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temporary_name, mock.patch.object(
            smoke.base,
            "write_start_gate",
        ):
            result = smoke.run_exact_retry(
                Path("/tmp/helper"),
                Path(temporary_name),
                command_runner=lambda *_args: good,
            )
            self.assertEqual(result["eventCount"], 48)

            bad = subprocess.CompletedProcess(
                args=("helper",),
                returncode=0,
                stdout=json.dumps({
                    "eventCount": True,
                    "status": "passed",
                    "writer": "writer-a",
                }),
                stderr="",
            )
            with self.assertRaises(smoke.base.SmokeError):
                smoke.run_exact_retry(
                    Path("/tmp/helper"),
                    Path(temporary_name),
                    command_runner=lambda *_args: bad,
                )

    def test_repeatability_compares_values_and_bytes(self) -> None:
        observed = {"schemaVersion": 1, "status": "passed"}
        result, receipt = smoke.qualify_repeatable(
            Path("/tmp/helper"),
            qualifier=lambda _helper: dict(observed),
        )
        payload = smoke.canonical_bytes(result)
        self.assertEqual(receipt["resultByteCount"], len(payload))
        self.assertEqual(
            receipt["runs"][0]["resultSha256"],
            receipt["runs"][1]["resultSha256"],
        )

        invocation = 0

        def drifting(_helper: Path) -> dict[str, object]:
            nonlocal invocation
            invocation += 1
            return {"invocation": invocation}

        with self.assertRaisesRegex(
            smoke.base.SmokeError,
            "not byte-repeatable",
        ):
            smoke.qualify_repeatable(
                Path("/tmp/helper"),
                qualifier=drifting,
            )

    def test_owner_only_publication_is_idempotent_and_fail_closed(self) -> None:
        value = {"schemaVersion": 1, "status": "passed"}
        with tempfile.TemporaryDirectory() as temporary_name:
            path = Path(temporary_name) / "result.json"
            smoke.publish_owner_only(path, value)
            smoke.publish_owner_only(path, value)
            status = path.lstat()
            self.assertEqual(stat_mode(status.st_mode), 0o600)
            self.assertEqual(path.read_bytes(), smoke.canonical_bytes(value))
            with self.assertRaises(smoke.base.SmokeError):
                smoke.publish_owner_only(
                    path,
                    {"schemaVersion": 2, "status": "passed"},
                )

    def test_source_inputs_bind_current_regular_files(self) -> None:
        records = smoke.source_inputs()
        self.assertEqual(
            [record["path"] for record in records],
            list(smoke.SOURCE_INPUT_PATHS),
        )
        for record in records:
            self.assertEqual(type(record["byteCount"]), int)
            self.assertEqual(len(record["sha256"]), 64)


def stat_mode(value: int) -> int:
    return value & 0o777


if __name__ == "__main__":
    unittest.main()
