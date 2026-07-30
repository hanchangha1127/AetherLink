#!/usr/bin/env python3
"""Unit tests for Runtime-chat SQLite cross-process orchestration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest import mock

from script import run_macos_runtime_chat_cross_process_smoke as smoke


class FakeProcess:
    def __init__(
        self,
        stdout: str,
        *,
        stderr: str = "",
        returncode: int = 0,
        timeout: bool = False,
        pid: int = 999_999,
        kill_failure: bool = False,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode: int | None = returncode
        self.timeout = timeout
        self.pid = pid
        self.kill_failure = kill_failure
        self.killed = False
        self.communicate_calls: list[float | None] = []
        self.wait_calls: list[float | None] = []

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.communicate_calls.append(timeout)
        if self.timeout and not self.killed:
            raise subprocess.TimeoutExpired("fake-writer", timeout)
        return self.stdout, self.stderr

    def kill(self) -> None:
        if self.kill_failure:
            raise OSError("injected kill failure")
        self.killed = True
        self.returncode = -9

    def poll(self) -> int | None:
        return None if self.timeout and not self.killed else self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.timeout and not self.killed:
            raise subprocess.TimeoutExpired("fake-writer", timeout)
        assert self.returncode is not None
        return self.returncode


class RuntimeChatCrossProcessSmokeTests(unittest.TestCase):
    def writer_output(self, writer: str) -> str:
        return json.dumps({
            "eventCount": smoke.EVENT_COUNT_PER_WRITER,
            "status": "passed",
            "writer": writer,
        })

    def canonical_readback(
        self,
        counts: dict[str, int] | None = None,
    ) -> dict[str, object]:
        expected_counts = counts or {
            writer: smoke.EVENT_COUNT_PER_WRITER
            for writer in smoke.WRITERS
        }
        rows: list[dict[str, object]] = []
        sequence = 0
        for ordinal in range(smoke.EVENT_COUNT_PER_WRITER):
            for writer in smoke.WRITERS:
                if ordinal >= expected_counts[writer]:
                    continue
                sequence += 1
                rows.append({
                    "eventID": smoke.expected_ids(writer)[ordinal],
                    "kind": "request",
                    "ownerDeviceID": smoke.OWNER_BY_WRITER[writer],
                    "requestID": smoke.expected_requests(writer)[ordinal],
                    "sequence": sequence,
                    "sessionID": smoke.SHARED_SESSION_ID,
                })
        return {
            "hostWideSessionCount": sum(
                count > 0 for count in expected_counts.values()
            ),
            "missingOwnerSessionCount": 0,
            "ownerProjections": [
                {
                    "messageContents": smoke.expected_contents(
                        writer,
                        end=expected_counts[writer],
                    ),
                    "ownerDeviceID": smoke.OWNER_BY_WRITER[writer],
                    "sessions": (
                        [{
                            "messageCount": expected_counts[writer],
                            "sessionID": smoke.SHARED_SESSION_ID,
                        }]
                        if expected_counts[writer]
                        else []
                    ),
                }
                for writer in smoke.WRITERS
            ],
            "rows": rows,
            "status": "passed",
            "unownedSessionCount": 0,
        }

    def test_helper_commands_bind_exact_root_mode_and_writer(self) -> None:
        helper = Path("/tmp/qa-helper")
        root = Path("/tmp/exact-db-root")
        command = smoke.helper_command(
            helper,
            root,
            mode="write",
            writer="writer-a",
        )
        self.assertEqual(
            command,
            (
                "/tmp/qa-helper",
                "write",
                "--database-root",
                "/tmp/exact-db-root",
                "--writer",
                "writer-a",
            ),
        )
        self.assertEqual(
            smoke.helper_command(helper, root, mode="read"),
            (
                "/tmp/qa-helper",
                "read",
                "--database-root",
                "/tmp/exact-db-root",
            ),
        )
        self.assertEqual(
            smoke.helper_command(
                helper,
                root,
                mode="abrupt-prefix",
                writer=smoke.ABRUPT_WRITER,
            ),
            (
                "/tmp/qa-helper",
                "abrupt-prefix",
                "--database-root",
                "/tmp/exact-db-root",
                "--writer",
                smoke.ABRUPT_WRITER,
            ),
        )
        self.assertEqual(
            smoke.helper_command(
                helper,
                root,
                mode="resume",
                writer=smoke.ABRUPT_WRITER,
            )[1],
            "resume",
        )
        with self.assertRaises(smoke.SmokeError):
            smoke.helper_command(
                helper,
                root,
                mode="write",
                writer="writer-c",
            )
        with self.assertRaises(smoke.SmokeError):
            smoke.helper_command(
                helper,
                root,
                mode="abrupt-prefix",
                writer="writer-b",
            )

    def test_two_injected_commands_launch_before_gate_and_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            processes = [
                FakeProcess(self.writer_output("writer-a")),
                FakeProcess(self.writer_output("writer-b")),
            ]
            calls: list[tuple[str, object]] = []

            def factory(command: list[str], **kwargs: object) -> FakeProcess:
                calls.append(("launch", tuple(command)))
                self.assertEqual(kwargs["cwd"], smoke.ROOT)
                self.assertEqual(kwargs["env"], smoke.closed_environment(temporary=root))
                return processes[len(calls) - 1]

            def gate_writer(observed_root: Path) -> None:
                calls.append(("gate", observed_root))

            results = smoke.run_writer_commands(
                (("fake-a",), ("fake-b",)),
                database_root=root,
                popen_factory=factory,
                gate_writer=gate_writer,
                monotonic=lambda: 1.0,
            )

            self.assertEqual(
                calls,
                [
                    ("launch", ("fake-a",)),
                    ("launch", ("fake-b",)),
                    ("gate", root),
                ],
            )
            smoke.validate_writer_results(results)
            self.assertTrue(
                all(process.communicate_calls for process in processes)
            )

    def test_timeout_kills_and_drains_both_injected_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            first = FakeProcess("", timeout=True)
            second = FakeProcess(self.writer_output("writer-b"), timeout=True)
            launched = [first, second]

            index = 0

            def indexed_factory(
                _command: list[str],
                **_kwargs: object,
            ) -> FakeProcess:
                nonlocal index
                process = launched[index]
                index += 1
                return process

            with self.assertRaises(smoke.SmokeError):
                smoke.run_writer_commands(
                    (("fake-a",), ("fake-b",)),
                    database_root=root,
                    popen_factory=indexed_factory,
                    gate_writer=lambda _root: None,
                    monotonic=lambda: 1.0,
                    group_killer=lambda _pid, _signal: (
                        (_ for _ in ()).throw(ProcessLookupError())
                    ),
                )
            self.assertTrue(first.killed)
            self.assertTrue(second.killed)
            self.assertGreaterEqual(len(first.wait_calls), 1)
            self.assertGreaterEqual(len(second.wait_calls), 1)

    def test_oversize_real_writer_output_is_terminated_at_hard_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            commands = (
                (
                    sys.executable,
                    "-c",
                    "import os; os.write(1, b'x' * 40000); "
                    "os.write(2, b'y' * 40000)",
                ),
                (
                    sys.executable,
                    "-c",
                    "import time; time.sleep(10)",
                ),
            )
            with self.assertRaisesRegex(smoke.SmokeError, "hard limit"):
                smoke.run_writer_commands(
                    commands,
                    database_root=root,
                    timeout_seconds=5.0,
                    gate_writer=lambda _root: None,
                )

    def test_oversize_real_readback_output_is_terminated_at_hard_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            helper = root / "oversize-readback"
            helper.write_text(
                "#!/usr/bin/python3\n"
                "import os\n"
                f"os.write(1, b'x' * {smoke.MAXIMUM_HELPER_OUTPUT_BYTES + 1})\n",
                encoding="utf-8",
            )
            helper.chmod(0o700)
            with self.assertRaisesRegex(smoke.SmokeError, "hard limit"):
                smoke.run_readback(helper, root)

    def test_bounded_command_timeout_kills_process_group_and_reaps(self) -> None:
        process = FakeProcess("", timeout=True, pid=4_242)
        popen_keywords: dict[str, object] = {}
        killed_groups: list[tuple[int, int]] = []

        def popen_factory(
            _command: list[str],
            **kwargs: object,
        ) -> FakeProcess:
            popen_keywords.update(kwargs)
            return process

        def timeout_collector(
            _processes: object,
            timeout_seconds: float,
            _monotonic: object,
        ) -> list[tuple[str, str]]:
            raise subprocess.TimeoutExpired("injected-build", timeout_seconds)

        with self.assertRaisesRegex(smoke.SmokeError, "timed out"):
            smoke._run_bounded_subprocess(
                ("fake-swift", "build"),
                3.0,
                popen_factory=popen_factory,
                output_collector=timeout_collector,
                group_killer=lambda pid, caught_signal: killed_groups.append(
                    (pid, caught_signal)
                ),
            )
        self.assertIs(popen_keywords["start_new_session"], True)
        self.assertEqual(killed_groups, [(4_242, smoke.signal.SIGKILL)])
        self.assertTrue(process.killed)
        self.assertGreaterEqual(len(process.wait_calls), 2)

    def test_cleanup_continues_when_one_child_cleanup_action_fails(self) -> None:
        first = FakeProcess(
            "",
            timeout=True,
            pid=5_001,
            kill_failure=True,
        )
        second = FakeProcess("", timeout=True, pid=5_002)
        group_calls: list[int] = []

        def failing_group_killer(pid: int, _caught_signal: int) -> None:
            group_calls.append(pid)
            if pid == first.pid:
                raise OSError("injected group cleanup failure")

        smoke._terminate_and_reap(
            (first, second),
            group_killer=failing_group_killer,
        )
        self.assertEqual(group_calls, [5_001, 5_002])
        self.assertGreaterEqual(len(first.wait_calls), 2)
        self.assertGreaterEqual(len(second.wait_calls), 2)

    def test_temporary_filesystem_error_is_normalized(self) -> None:
        with mock.patch.object(
            smoke.tempfile,
            "TemporaryDirectory",
            side_effect=OSError("sensitive temporary path"),
        ):
            with self.assertRaisesRegex(
                smoke.SmokeError,
                "could not prepare the temporary database root",
            ):
                smoke.qualify(Path("/tmp/fake-helper"))

    def test_readback_accepts_exactly_once_interleaving(self) -> None:
        smoke.validate_readback(self.canonical_readback())

    def test_readback_rejects_duplicate_and_owner_bleed(self) -> None:
        duplicate = self.canonical_readback()
        rows = duplicate["rows"]
        assert isinstance(rows, list)
        rows[-1]["eventID"] = rows[0]["eventID"]
        with self.assertRaises(smoke.SmokeError):
            smoke.validate_readback(duplicate)

        bleed = self.canonical_readback()
        projections = bleed["ownerProjections"]
        assert isinstance(projections, list)
        projections[0]["messageContents"] = smoke.expected_contents("writer-b")
        with self.assertRaises(smoke.SmokeError):
            smoke.validate_readback(bleed)

    def test_abrupt_checkpoint_is_exact_typed_and_duplicate_closed(self) -> None:
        checkpoint = {
            "committedPrefixCount": smoke.ABRUPT_COMMITTED_PREFIX_COUNT,
            "databaseCacheFlushed": True,
            "inFlightEventID": smoke.ABRUPT_INFLIGHT_EVENT_ID,
            "insideTransactionEventCount": (
                smoke.ABRUPT_COMMITTED_PREFIX_COUNT + 1
            ),
            "insideTransactionFTSEventCount": (
                smoke.ABRUPT_COMMITTED_PREFIX_COUNT + 1
            ),
            "insideTransactionMutationRevision": (
                smoke.ABRUPT_COMMITTED_PREFIX_COUNT + 1
            ),
            "insideTransactionValidatedRevision": (
                smoke.ABRUPT_COMMITTED_PREFIX_COUNT
            ),
            "journalMode": "delete",
            "schemaVersion": 1,
            "status": "ready-for-abrupt-termination",
            "transactionOpen": True,
            "writer": smoke.ABRUPT_WRITER,
        }
        payload = (
            json.dumps(checkpoint, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("ascii")
        self.assertEqual(
            smoke.validate_abrupt_checkpoint(payload),
            checkpoint,
        )

        wrong_type = dict(checkpoint)
        wrong_type["schemaVersion"] = True
        with self.assertRaises(smoke.SmokeError):
            smoke.validate_abrupt_checkpoint(
                json.dumps(wrong_type).encode("ascii")
            )
        with self.assertRaises(smoke.SmokeError):
            smoke.validate_abrupt_checkpoint(
                b'{"schemaVersion":1,"schemaVersion":1}\n'
            )

    def test_hot_journal_requires_owner_only_magic_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            journal = root / f"{smoke.DATABASE_FILENAME}-journal"
            header = (
                smoke.SQLITE_ROLLBACK_JOURNAL_MAGIC
                + struct.pack(
                    ">IIIII",
                    1,
                    123,
                    1,
                    512,
                    4_096,
                )
            )
            journal.write_bytes(
                header
                + b"\0" * (512 - len(header))
                + b"\0" * (4_096 + 8)
            )
            journal.chmod(0o600)
            self.assertEqual(
                smoke.observe_hot_rollback_journal(root)[
                    "hotJournalHeaderObserved"
                ],
                True,
            )
            journal.write_bytes(
                smoke.SQLITE_ROLLBACK_JOURNAL_MAGIC + b"\0" * 504
            )
            with self.assertRaises(smoke.SmokeError):
                smoke.observe_hot_rollback_journal(root)

    def test_abrupt_prefix_kills_only_new_session_group_and_reaps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            helper = root / "helper"
            helper.write_bytes(b"fixture")
            helper.chmod(0o700)
            process = FakeProcess("", timeout=True, pid=8_080)
            keywords: dict[str, object] = {}
            killed: list[tuple[int, int]] = []
            order: list[str] = []
            expected_checkpoint = {"status": "fixture"}
            expected_journal = {"hotJournalHeaderObserved": True}
            expected_dirty = {"inFlightEventAndFTSPresent": True}

            def factory(
                _command: list[str],
                **kwargs: object,
            ) -> FakeProcess:
                keywords.update(kwargs)
                return process

            def kill_group(pid: int, caught_signal: int) -> None:
                killed.append((pid, caught_signal))
                order.append("kill")
                process.kill()

            def journal_observer(_root: Path) -> dict[str, object]:
                order.append("journal")
                return expected_journal

            def dirty_observer(_root: Path) -> dict[str, object]:
                order.append("dirty")
                return expected_dirty

            result = smoke.run_abrupt_prefix(
                helper,
                root,
                popen_factory=factory,
                checkpoint_waiter=lambda _process, _root: (
                    expected_checkpoint
                ),
                journal_observer=journal_observer,
                dirty_database_observer=dirty_observer,
                group_killer=kill_group,
                group_identity_reader=lambda pid: pid,
                monotonic=lambda: 1.0,
            )
            self.assertIs(keywords["start_new_session"], True)
            self.assertEqual(
                killed,
                [(process.pid, smoke.signal.SIGKILL)],
            )
            self.assertEqual(
                result["processGroup"],
                "new-session-exact-child-only",
            )
            self.assertIs(result["checkpoint"], expected_checkpoint)
            self.assertGreaterEqual(len(process.wait_calls), 1)
            self.assertEqual(
                order,
                ["kill", "journal", "dirty", "journal"],
            )
            self.assertTrue(
                result["writerProcessReapedBeforeJournalObservation"]
            )

    def test_abrupt_prefix_rejects_group_drift_without_group_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            helper = root / "helper"
            helper.write_bytes(b"fixture")
            helper.chmod(0o700)
            process = FakeProcess("", timeout=True, pid=8_081)
            group_signals: list[tuple[int, int]] = []

            with self.assertRaisesRegex(
                smoke.SmokeError,
                "does not own its exact process group",
            ):
                smoke.run_abrupt_prefix(
                    helper,
                    root,
                    popen_factory=lambda _command, **_kwargs: process,
                    checkpoint_waiter=lambda _process, _root: {
                        "status": "fixture"
                    },
                    journal_observer=lambda _root: {
                        "hotJournalHeaderObserved": True
                    },
                    dirty_database_observer=lambda _root: {
                        "inFlightEventAndFTSPresent": True
                    },
                    group_killer=lambda pid, caught_signal: (
                        group_signals.append((pid, caught_signal))
                    ),
                    group_identity_reader=lambda _pid: process.pid + 1,
                    monotonic=lambda: 1.0,
                )
            self.assertEqual(group_signals, [])
            self.assertTrue(process.killed)

    def test_abrupt_partial_and_final_readback_contracts(self) -> None:
        prefix_counts = {
            smoke.ABRUPT_WRITER: smoke.ABRUPT_COMMITTED_PREFIX_COUNT,
            "writer-b": 0,
        }
        prefix = self.canonical_readback(prefix_counts)
        smoke.validate_readback_counts(
            prefix,
            expected_counts=prefix_counts,
            require_contiguous_sequences=True,
        )
        rows = prefix["rows"]
        assert isinstance(rows, list)
        rows[-1]["sequence"] = rows[-2]["sequence"] + 2
        with self.assertRaises(smoke.SmokeError):
            smoke.validate_readback_counts(
                prefix,
                expected_counts=prefix_counts,
                require_contiguous_sequences=True,
            )

        final_counts = {
            smoke.ABRUPT_WRITER: smoke.EVENT_COUNT_PER_WRITER,
            "writer-b": 0,
        }
        smoke.validate_readback_counts(
            self.canonical_readback(final_counts),
            expected_counts=final_counts,
            require_contiguous_sequences=True,
        )

    def test_real_helper_abrupt_recovery_is_exact_and_repeatable(self) -> None:
        helper = smoke.build_helper()
        first = smoke.qualify_abrupt_recovery(helper)
        second = smoke.qualify_abrupt_recovery(helper)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "passed")
        self.assertEqual(
            first["recovered"]["eventCount"],
            smoke.ABRUPT_COMMITTED_PREFIX_COUNT,
        )
        self.assertEqual(
            first["final"]["eventCount"],
            smoke.EVENT_COUNT_PER_WRITER,
        )
        self.assertTrue(
            first["abruptTermination"]["journal"][
                "hotJournalHeaderObserved"
            ]
        )
        self.assertTrue(
            first["abruptTermination"]["dirtyDatabaseBeforeRecovery"][
                "inFlightEventAndFTSPresent"
            ]
        )

    def test_result_publication_is_immutable_and_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result_path = Path(temporary_name) / "result.json"
            result = {
                "schemaVersion": smoke.RESULT_SCHEMA_VERSION,
                "scope": smoke.ABRUPT_RESULT_SCOPE,
                "status": "passed",
            }
            smoke.publish_result(result_path, result)
            first = result_path.read_bytes()
            smoke.publish_result(result_path, result)
            self.assertEqual(result_path.read_bytes(), first)
            with self.assertRaises(smoke.SmokeError):
                smoke.publish_result(
                    result_path,
                    {**result, "status": "different"},
                )

    def test_build_uses_injected_bounded_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            binary_directory = Path(temporary_name)
            helper = binary_directory / smoke.HELPER_PRODUCT
            helper.write_bytes(b"fixture")
            calls: list[tuple[tuple[str, ...], float]] = []

            def command_runner(
                command: object,
                timeout_seconds: float,
            ) -> subprocess.CompletedProcess[str]:
                command_tuple = tuple(command)
                calls.append((command_tuple, timeout_seconds))
                stdout = ""
                if "--show-bin-path" in command_tuple:
                    stdout = str(binary_directory) + "\n"
                return subprocess.CompletedProcess(
                    command_tuple,
                    0,
                    stdout=stdout,
                    stderr="",
                )

            self.assertEqual(
                smoke.build_helper(command_runner=command_runner),
                helper,
            )
            self.assertEqual(len(calls), 2)
            self.assertTrue(
                all(timeout == smoke.BUILD_TIMEOUT_SECONDS for _, timeout in calls)
            )
            self.assertIn("--product", calls[0][0])
            self.assertIn("--show-bin-path", calls[1][0])

    def test_canonical_result_has_no_path_or_environment(self) -> None:
        result = {
            "status": "passed",
            "scope": smoke.RESULT_SCOPE,
            "schemaVersion": smoke.RESULT_SCHEMA_VERSION,
        }
        encoded = smoke.canonical_json(result)
        self.assertEqual(encoded, smoke.canonical_json(result))
        self.assertNotIn(str(smoke.ROOT), encoded)
        self.assertNotIn("HOME", encoded)


if __name__ == "__main__":
    unittest.main()
