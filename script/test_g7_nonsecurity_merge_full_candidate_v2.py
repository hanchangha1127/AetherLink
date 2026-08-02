#!/usr/bin/env python3
"""Contract tests for the integrated non-security G7 candidate V2."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from script import check_g7_nonsecurity_merge_full_candidate_v2 as checker
from script import run_g7_nonsecurity_merge_full_candidate_v2 as runner


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def command_record(gate: runner.base.Gate) -> dict[str, object]:
    return {
        "argv": list(gate.argv),
        "cwd": ".",
        "elapsedMilliseconds": 1,
        "exitCode": 0,
        "id": gate.identifier,
        "stderr": {"sha256": EMPTY_SHA256, "size": 0},
        "stdout": {"sha256": EMPTY_SHA256, "size": 0},
        "timeoutSeconds": gate.timeout_seconds,
    }


def source_fixture(*, sha256: str = "1" * 64) -> dict[str, object]:
    return {
        "algorithm": checker.base.SOURCE_ALGORITHM,
        "fileCount": 1,
        "sha256": sha256,
        "size": 1,
    }


def valid_document() -> dict[str, object]:
    v1_record = dict(checker.EXPECTED_V1_CANDIDATE_RECORD)
    return {
        "artifacts": [],
        "commands": [command_record(gate) for gate in runner.ALL_GATES],
        "contract": checker.CONTRACT,
        "coverage": dict(checker.EXPECTED_COVERAGE),
        "implementation": [],
        "limitations": dict(checker.EXPECTED_LIMITATIONS),
        "pidPreservation": {
            "after": "",
            "before": "",
            "pid": 0,
            "preservedDuringRun": False,
            "requested": False,
        },
        "result": "passed",
        "schemaVersion": checker.SCHEMA_VERSION,
        "source": source_fixture(),
        "v1ArtifactPreservation": {
            "after": v1_record,
            "before": v1_record,
            "preservedDuringRun": True,
        },
    }


class G7NonsecurityMergeFullCandidateV2Tests(unittest.TestCase):
    def validate_with_fixture(
        self,
        document: dict[str, object],
        *,
        run_readbacks: bool = False,
    ) -> tuple[mock.Mock, mock.Mock]:
        with (
            mock.patch.object(
                checker.base,
                "source_snapshot",
                return_value=document["source"],
            ),
            mock.patch.object(
                checker.base,
                "validate_file_records",
            ) as file_records,
            mock.patch.object(checker.base, "validate_android_lint"),
            mock.patch.object(
                checker.base,
                "file_record",
                return_value=checker.EXPECTED_V1_CANDIDATE_RECORD,
            ),
            mock.patch.object(checker.base, "run_child_readbacks") as base_readbacks,
            mock.patch.object(checker, "run_addon_readback") as addon_readback,
        ):
            checker.validate_document(
                document,
                root=checker.ROOT,
                run_readbacks=run_readbacks,
            )
        return file_records, mock.Mock(
            base_calls=base_readbacks.call_count,
            addon_calls=addon_readback.call_count,
        )

    def test_static_contract_is_exact_67_plus_4(self) -> None:
        runner.validate_static_contract()
        checker.validate_static_contract()
        self.assertEqual(len(runner.ALL_GATES), 71)
        self.assertEqual(runner.ALL_GATES[:67], runner.base.ALL_GATES)
        self.assertEqual(
            runner.EXPECTED_COMMAND_IDS[:67],
            runner.base.EXPECTED_COMMAND_IDS,
        )
        expected_tail = (
            "g7-reviewed-nonsecurity-swift-addon-v2-prepare",
            "g7-reviewed-nonsecurity-swift-addon-v2-run",
            "g7-reviewed-nonsecurity-swift-addon-v2-write-binding",
            "g7-reviewed-nonsecurity-swift-addon-v2-results",
        )
        self.assertEqual(runner.EXPECTED_COMMAND_IDS[67:], expected_tail)
        self.assertEqual(checker.EXPECTED_COMMAND_IDS, runner.EXPECTED_COMMAND_IDS)
        for gate, (identifier, argv, timeout) in zip(
            runner.ADDITIONAL_GATES,
            checker.ADDITIONAL_COMMAND_SPECS,
        ):
            self.assertEqual((gate.identifier, gate.argv, gate.timeout_seconds), (identifier, argv, timeout))

    def test_paths_and_generation_boundaries_are_exact(self) -> None:
        self.assertEqual(len(runner.ARTIFACT_PATHS), 32)
        self.assertEqual(len(set(runner.ARTIFACT_PATHS)), 32)
        self.assertEqual(runner.ARTIFACT_PATHS, checker.EXPECTED_ARTIFACT_PATHS)
        self.assertEqual(len(runner.IMPLEMENTATION_PATHS), 11)
        self.assertEqual(len(set(runner.IMPLEMENTATION_PATHS)), 11)
        self.assertEqual(
            runner.IMPLEMENTATION_PATHS,
            checker.EXPECTED_IMPLEMENTATION_PATHS,
        )
        self.assertEqual(
            tuple(path.as_posix() for path in runner.ARTIFACT_PATHS),
            tuple(sorted(path.as_posix() for path in runner.ARTIFACT_PATHS)),
        )
        self.assertNotEqual(runner.RESULT_RELATIVE_PATH, runner.base.RESULT_RELATIVE_PATH)
        self.assertIn(runner.V1_CANDIDATE_RELATIVE_PATH, runner.ARTIFACT_PATHS)
        for path in runner.ADDON_ARTIFACT_PATHS:
            self.assertIn(path, runner.ARTIFACT_PATHS)

    def test_producer_rejects_every_noncanonical_result_path_before_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = (
                runner.V1_CANDIDATE_RELATIVE_PATH,
                runner.ARTIFACT_PATHS[0],
                runner.IMPLEMENTATION_PATHS[0],
                root / ".." / "outside-candidate.json",
                Path(".build/alternate-candidate.json"),
            )
            with (
                mock.patch.object(runner.base, "source_snapshot") as source_snapshot,
                mock.patch.object(
                    runner.base,
                    "run_gate_with_managed_release_scratch",
                ) as gate_runner,
            ):
                for result_path in cases:
                    with self.subTest(result_path=result_path):
                        with self.assertRaisesRegex(
                            runner.CandidateError,
                            "exact canonical V2 result path",
                        ):
                            runner.produce_candidate(
                                root=root,
                                result_path=result_path,
                                preserve_pid=None,
                            )
            source_snapshot.assert_not_called()
            gate_runner.assert_not_called()

    def test_payload_closes_v2_coverage_limitations_and_v1_preservation(self) -> None:
        document = valid_document()
        payload = runner.candidate_payload(
            source=document["source"],
            commands=document["commands"],
            artifacts=document["artifacts"],
            implementation=document["implementation"],
            pid_preservation=document["pidPreservation"],
            v1_artifact_preservation=document["v1ArtifactPreservation"],
        )
        self.assertEqual(payload, document)
        self.assertEqual(payload["coverage"]["swiftDistinctNonsecurityTests"], 1023)
        self.assertEqual(payload["coverage"]["swiftReviewedAddonTests"], 626)
        self.assertTrue(all(value is False for value in payload["limitations"].values()))

    def test_checker_accepts_exact_document_and_requests_exact_file_sets(self) -> None:
        document = valid_document()
        file_records, readbacks = self.validate_with_fixture(document)
        self.assertEqual(file_records.call_count, 3)
        self.assertEqual(
            file_records.call_args_list[0].kwargs["expected_paths"],
            checker.EXPECTED_ARTIFACT_PATHS,
        )
        self.assertEqual(
            file_records.call_args_list[1].kwargs["expected_paths"],
            checker.EXPECTED_IMPLEMENTATION_PATHS,
        )
        self.assertEqual(
            file_records.call_args_list[2].kwargs["expected_paths"],
            checker.EXPECTED_ARTIFACT_PATHS,
        )
        self.assertEqual(readbacks.base_calls, 0)
        self.assertEqual(readbacks.addon_calls, 0)

    def test_each_tail_id_argv_and_timeout_mutation_is_rejected(self) -> None:
        for index in range(67, 71):
            for field in ("id", "argv", "timeoutSeconds"):
                with self.subTest(index=index, field=field):
                    document = valid_document()
                    command = document["commands"][index]
                    if field == "id":
                        command[field] = "mutated-id"
                    elif field == "argv":
                        command[field] = [*command[field], "--mutated"]
                    else:
                        command[field] += 1
                    with self.assertRaises(checker.CandidateError):
                        self.validate_with_fixture(document)

    def test_stale_contract_boolean_counts_pid_and_schema_are_rejected(self) -> None:
        mutations = (
            ("contract", lambda document: document.__setitem__("contract", runner.base.CONTRACT)),
            (
                "coverage-bool",
                lambda document: document["coverage"].__setitem__(
                    "swiftReviewedAddonTests",
                    True,
                ),
            ),
            (
                "pid-bool",
                lambda document: document["pidPreservation"].__setitem__(
                    "pid",
                    True,
                ),
            ),
            ("schema-bool", lambda document: document.__setitem__("schemaVersion", True)),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                document = valid_document()
                mutate(document)
                with self.assertRaises(checker.CandidateError):
                    self.validate_with_fixture(document)

    def test_v1_preservation_mutations_are_rejected(self) -> None:
        for location in ("before", "after", "preservedDuringRun"):
            with self.subTest(location=location):
                document = valid_document()
                preservation = document["v1ArtifactPreservation"]
                if location == "preservedDuringRun":
                    preservation[location] = False
                else:
                    preservation[location] = dict(preservation[location])
                    preservation[location]["size"] += 1
                with self.assertRaises(checker.CandidateError):
                    self.validate_with_fixture(document)

    def test_readback_order_is_base_then_addon(self) -> None:
        document = valid_document()
        manager = mock.Mock()
        with (
            mock.patch.object(
                checker.base,
                "source_snapshot",
                return_value=document["source"],
            ),
            mock.patch.object(checker.base, "validate_file_records"),
            mock.patch.object(checker.base, "validate_android_lint"),
            mock.patch.object(
                checker.base,
                "file_record",
                return_value=checker.EXPECTED_V1_CANDIDATE_RECORD,
            ),
            mock.patch.object(checker.base, "run_child_readbacks") as base_readbacks,
            mock.patch.object(checker, "run_addon_readback") as addon_readback,
        ):
            manager.attach_mock(base_readbacks, "base")
            manager.attach_mock(addon_readback, "addon")
            checker.validate_document(
                document,
                root=checker.ROOT,
                run_readbacks=True,
            )
        self.assertEqual(manager.mock_calls, [mock.call.base(checker.ROOT), mock.call.addon(checker.ROOT)])

    def test_addon_readback_uses_exact_bounded_command(self) -> None:
        process = mock.Mock(returncode=0)
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                checker.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
            mock.patch.object(
                checker.base,
                "bounded_child_output",
                return_value=(b"passed\n", b""),
            ) as bounded_output,
        ):
            root = Path(temporary)
            checker.run_addon_readback(root)
        popen.assert_called_once()
        positional, keywords = popen.call_args
        self.assertEqual(positional, (checker.ADDON_READBACK_COMMAND,))
        self.assertEqual(keywords["cwd"], root)
        self.assertEqual(keywords["stdout"], checker.subprocess.PIPE)
        self.assertEqual(keywords["stderr"], checker.subprocess.PIPE)
        self.assertTrue(keywords["start_new_session"])
        self.assertEqual(keywords["env"]["LC_ALL"], "C")
        self.assertEqual(keywords["env"]["LANG"], "C")
        self.assertEqual(keywords["env"]["PYTHONPATH"], str(root))
        bounded_output.assert_called_once_with(
            process,
            command=checker.ADDON_READBACK_COMMAND,
            timeout_seconds=checker.base.READBACK_TIMEOUT_SECONDS,
            maximum_bytes=checker.base.READBACK_STREAM_MAX_BYTES,
        )

    def test_addon_readback_rejects_nonzero_exit(self) -> None:
        process = mock.Mock(returncode=7)
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                checker.subprocess,
                "Popen",
                return_value=process,
            ),
            mock.patch.object(
                checker.base,
                "bounded_child_output",
                return_value=(b"", b"readback-detail"),
            ),
        ):
            with self.assertRaisesRegex(
                checker.CandidateError,
                "add-on readback failed: readback-detail",
            ):
                checker.run_addon_readback(Path(temporary))

    def test_producer_success_wraps_all_71_gates_source_pid_and_v1_bytes(self) -> None:
        source = source_fixture()
        events: list[str] = []

        def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
            events.append(f"file:{relative.as_posix()}")
            if relative == runner.V1_CANDIDATE_RELATIVE_PATH:
                return dict(runner.EXPECTED_V1_CANDIDATE_RECORD)
            return {
                "mode": 0o600,
                "path": relative.as_posix(),
                "sha256": "2" * 64,
                "size": 1,
            }

        def run_gate(gate: runner.base.Gate, **_kwargs: object):
            events.append(f"gate:{gate.identifier}")
            stdout = b""
            if gate.identifier in {"macos-release-source-before", "macos-release-source-after"}:
                stdout = b"a" * 64 + b"\n"
            return command_record(gate), stdout, b""

        def source_snapshot(**_kwargs: object) -> dict[str, object]:
            events.append("source")
            return dict(source)

        def process_identity(pid: int) -> str:
            events.append(f"pid:{pid}")
            return "stable-pid"

        def atomic_publish(*_args: object, **_kwargs: object) -> None:
            events.append("atomic")

        with (
            mock.patch.object(runner.base, "ensure_directory"),
            mock.patch.object(runner.base, "source_snapshot", side_effect=source_snapshot),
            mock.patch.object(runner.base, "stable_file_record", side_effect=stable_record),
            mock.patch.object(runner.base, "process_identity", side_effect=process_identity),
            mock.patch.object(
                runner.base,
                "run_gate_with_managed_release_scratch",
                side_effect=run_gate,
            ) as gate_runner,
            mock.patch.object(runner.base, "validate_zero_lint_issues"),
            mock.patch.object(
                runner.base,
                "atomic_write",
                side_effect=atomic_publish,
            ) as atomic_write,
        ):
            payload = runner.produce_candidate(
                result_path=runner.ROOT / runner.RESULT_RELATIVE_PATH,
                preserve_pid=59809,
            )
        self.assertEqual(gate_runner.call_count, 71)
        self.assertEqual(len(payload["commands"]), 71)
        self.assertTrue(payload["pidPreservation"]["preservedDuringRun"])
        self.assertTrue(payload["v1ArtifactPreservation"]["preservedDuringRun"])
        self.assertEqual(events.count("source"), 2)
        self.assertEqual(events.count("pid:59809"), 2)
        self.assertEqual(
            sum(event == f"file:{runner.V1_CANDIDATE_RELATIVE_PATH}" for event in events),
            3,
        )
        self.assertEqual(atomic_write.call_count, 1)
        gate_events = [event for event in events if event.startswith("gate:")]
        self.assertEqual(
            gate_events,
            [f"gate:{gate.identifier}" for gate in runner.ALL_GATES],
        )
        source_indices = [
            index for index, event in enumerate(events) if event == "source"
        ]
        pid_indices = [
            index for index, event in enumerate(events) if event == "pid:59809"
        ]
        v1_event = f"file:{runner.V1_CANDIDATE_RELATIVE_PATH}"
        v1_indices = [
            index for index, event in enumerate(events) if event == v1_event
        ]
        first_gate = events.index(gate_events[0])
        last_gate = len(events) - 1 - events[::-1].index(gate_events[-1])
        self.assertLess(source_indices[0], first_gate)
        self.assertLess(pid_indices[0], first_gate)
        self.assertLess(v1_indices[0], first_gate)
        self.assertLess(last_gate, v1_indices[-1])
        self.assertLess(v1_indices[-1], source_indices[-1])
        self.assertLess(source_indices[-1], pid_indices[-1])
        self.assertEqual(events[-1], "atomic")

    def test_producer_source_drift_rejects_publication(self) -> None:
        before = source_fixture(sha256="1" * 64)
        after = source_fixture(sha256="2" * 64)

        def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
            if relative == runner.V1_CANDIDATE_RELATIVE_PATH:
                return dict(runner.EXPECTED_V1_CANDIDATE_RECORD)
            return {
                "mode": 0o600,
                "path": relative.as_posix(),
                "sha256": "3" * 64,
                "size": 1,
            }

        with (
            mock.patch.object(runner.base, "ensure_directory"),
            mock.patch.object(
                runner.base,
                "source_snapshot",
                side_effect=(before, after),
            ),
            mock.patch.object(runner.base, "stable_file_record", side_effect=stable_record),
            mock.patch.object(
                runner.base,
                "run_gate_with_managed_release_scratch",
                side_effect=lambda gate, **_kwargs: (
                    command_record(gate),
                    b"a" * 64 + b"\n"
                    if gate.identifier in {
                        "macos-release-source-before",
                        "macos-release-source-after",
                    }
                    else b"",
                    b"",
                ),
            ),
            mock.patch.object(runner.base, "validate_zero_lint_issues"),
            mock.patch.object(runner.base, "atomic_write") as atomic_write,
        ):
            with self.assertRaisesRegex(runner.CandidateError, "source changed"):
                runner.produce_candidate(
                    result_path=runner.ROOT / runner.RESULT_RELATIVE_PATH,
                    preserve_pid=None,
                )
        atomic_write.assert_not_called()

    def test_v1_and_pid_drift_after_all_gates_preserve_existing_v2(self) -> None:
        for drift_kind, expected_error in (
            ("v1", "V1 antecedent candidate changed"),
            ("pid", "preserved PID 59809 changed"),
        ):
            with self.subTest(drift_kind=drift_kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result_path = root / runner.RESULT_RELATIVE_PATH
                result_path.parent.mkdir(parents=True)
                result_path.write_bytes(b"existing-v2-parent\n")
                result_path.chmod(0o600)
                v1_calls = 0

                def stable_record(
                    relative: Path,
                    **_kwargs: object,
                ) -> dict[str, object]:
                    nonlocal v1_calls
                    if relative == runner.V1_CANDIDATE_RELATIVE_PATH:
                        v1_calls += 1
                        record = dict(runner.EXPECTED_V1_CANDIDATE_RECORD)
                        if drift_kind == "v1" and v1_calls == 3:
                            record["sha256"] = "9" * 64
                        return record
                    return {
                        "mode": 0o600,
                        "path": relative.as_posix(),
                        "sha256": "3" * 64,
                        "size": 1,
                    }

                def run_gate(gate: runner.base.Gate, **_kwargs: object):
                    stdout = b""
                    if gate.identifier in {
                        "macos-release-source-before",
                        "macos-release-source-after",
                    }:
                        stdout = b"a" * 64 + b"\n"
                    return command_record(gate), stdout, b""

                process_identities = (
                    ["pid-before", "pid-after"]
                    if drift_kind == "pid"
                    else ["pid-stable", "pid-stable"]
                )
                with (
                    mock.patch.object(runner.base, "ensure_directory"),
                    mock.patch.object(
                        runner.base,
                        "source_snapshot",
                        return_value=source_fixture(),
                    ),
                    mock.patch.object(
                        runner.base,
                        "stable_file_record",
                        side_effect=stable_record,
                    ),
                    mock.patch.object(
                        runner.base,
                        "process_identity",
                        side_effect=process_identities,
                    ),
                    mock.patch.object(
                        runner.base,
                        "run_gate_with_managed_release_scratch",
                        side_effect=run_gate,
                    ) as gate_runner,
                    mock.patch.object(runner.base, "validate_zero_lint_issues"),
                    mock.patch.object(runner.base, "atomic_write") as atomic_write,
                ):
                    with self.assertRaisesRegex(runner.CandidateError, expected_error):
                        runner.produce_candidate(
                            root=root,
                            result_path=result_path,
                            preserve_pid=59809,
                        )
                self.assertEqual(gate_runner.call_count, 71)
                self.assertEqual(v1_calls, 3)
                atomic_write.assert_not_called()
                self.assertEqual(result_path.read_bytes(), b"existing-v2-parent\n")
                self.assertEqual(result_path.stat().st_mode & 0o777, 0o600)

    def test_addon_failure_preserves_existing_v1_and_v2_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            v1_path = root / runner.V1_CANDIDATE_RELATIVE_PATH
            v1_path.parent.mkdir(parents=True)
            live_v1 = runner.ROOT / runner.V1_CANDIDATE_RELATIVE_PATH
            v1_data = live_v1.read_bytes()
            v1_path.write_bytes(v1_data)
            v1_path.chmod(0o600)
            v2_path = root / runner.RESULT_RELATIVE_PATH
            v2_path.parent.mkdir(parents=True)
            v2_path.write_bytes(b"existing-v2-parent\n")
            v2_path.chmod(0o600)

            def fail_on_addon(gate: runner.base.Gate, **_kwargs: object):
                if gate.identifier == "g7-reviewed-nonsecurity-swift-addon-v2-run":
                    raise runner.CandidateError("injected add-on failure")
                stdout = b""
                if gate.identifier in {
                    "macos-release-source-before",
                    "macos-release-source-after",
                }:
                    stdout = b"a" * 64 + b"\n"
                return command_record(gate), stdout, b""

            with (
                mock.patch.object(
                    runner.base,
                    "source_snapshot",
                    return_value=source_fixture(),
                ),
                mock.patch.object(
                    runner.base,
                    "run_gate_with_managed_release_scratch",
                    side_effect=fail_on_addon,
                ) as gate_runner,
                mock.patch.object(runner.base, "validate_zero_lint_issues"),
            ):
                with self.assertRaisesRegex(runner.CandidateError, "injected"):
                    runner.produce_candidate(
                        root=root,
                        result_path=v2_path,
                        preserve_pid=None,
                    )
            self.assertEqual(gate_runner.call_count, 69)
            self.assertEqual(v1_path.read_bytes(), v1_data)
            self.assertEqual(v1_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(v2_path.read_bytes(), b"existing-v2-parent\n")
            self.assertEqual(v2_path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
