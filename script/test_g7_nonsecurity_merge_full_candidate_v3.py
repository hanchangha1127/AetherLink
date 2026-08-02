#!/usr/bin/env python3
"""Contract tests for the composed non-security G7 candidate V3."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from script import check_g7_nonsecurity_merge_full_candidate_v3 as checker
from script import run_g7_nonsecurity_merge_full_candidate_v3 as runner


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
FIXTURE_V3_RESULT_RECORD = {
    "mode": 0o600,
    "path": checker.addon_v3.RESULT_PATH.relative_to(checker.ROOT).as_posix(),
    "sha256": "7" * 64,
    "size": 3_000,
}


def command_record(gate: runner.runtime.Gate) -> dict[str, object]:
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
        "algorithm": checker.candidate_base.SOURCE_ALGORITHM,
        "fileCount": 1,
        "sha256": sha256,
        "size": 1,
    }


def valid_document() -> dict[str, object]:
    v2_record = dict(checker.EXPECTED_V2_CANDIDATE_RECORD)
    v3_record = dict(FIXTURE_V3_RESULT_RECORD)
    return {
        "artifacts": [],
        "commands": [command_record(gate) for gate in runner.ALL_GATES],
        "contract": checker.CONTRACT,
        "coverage": dict(checker.EXPECTED_COVERAGE),
        "evidenceComposition": checker.expected_composition(
            v2_candidate=v2_record,
            v3_addon_result=v3_record,
        ),
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
        "v2ArtifactPreservation": {
            "after": v2_record,
            "before": v2_record,
            "preservedDuringRun": True,
        },
    }


class G7NonsecurityMergeFullCandidateV3Tests(unittest.TestCase):
    def validate_with_fixture(
        self,
        document: dict[str, object],
        *,
        run_readbacks: bool = False,
    ) -> tuple[mock.Mock, mock.Mock]:
        with (
            mock.patch.object(
                checker.candidate_base,
                "source_snapshot",
                return_value=document["source"],
            ),
            mock.patch.object(
                checker.candidate_base,
                "validate_file_records",
            ) as file_records,
            mock.patch.object(checker.candidate_base, "validate_android_lint"),
            mock.patch.object(
                checker,
                "current_antecedent_records",
                return_value=(
                    dict(checker.EXPECTED_V2_CANDIDATE_RECORD),
                    dict(FIXTURE_V3_RESULT_RECORD),
                ),
            ),
            mock.patch.object(checker, "run_addon_readback") as addon_readback,
        ):
            checker.validate_document(
                document,
                root=checker.ROOT,
                run_readbacks=run_readbacks,
            )
        return file_records, addon_readback

    def test_static_contract_is_exact_immutable_71_plus_new_4(self) -> None:
        runner.validate_static_contract()
        checker.validate_static_contract()
        self.assertEqual(len(runner.base.EXPECTED_COMMAND_IDS), 71)
        self.assertEqual(len(runner.ALL_GATES), 4)
        self.assertEqual(
            runner.EXPECTED_COMMAND_IDS,
            (
                "g7-reviewed-nonsecurity-swift-addon-v3-prepare",
                "g7-reviewed-nonsecurity-swift-addon-v3-run",
                "g7-reviewed-nonsecurity-swift-addon-v3-write-binding",
                "g7-reviewed-nonsecurity-swift-addon-v3-results",
            ),
        )
        self.assertEqual(checker.EXPECTED_COMMAND_IDS, runner.EXPECTED_COMMAND_IDS)
        self.assertEqual(runner.COMPOSED_COMMAND_EVIDENCE_COUNT, 75)
        for gate, (identifier, argv, timeout) in zip(
            runner.ADDITIONAL_GATES,
            checker.ADDITIONAL_COMMAND_SPECS,
        ):
            self.assertEqual(
                (gate.identifier, gate.argv, gate.timeout_seconds),
                (identifier, argv, timeout),
            )

    def test_static_contract_rejects_same_count_addon_path_drift(self) -> None:
        substituted_binding = (
            runner.ROOT
            / runner.ADDON_OUTPUT_PARENT
            / "same-count-substituted-binding.json"
        )
        with mock.patch.object(
            runner.addon_v3,
            "BINDING_PATH",
            substituted_binding,
        ):
            with self.assertRaisesRegex(
                runner.CandidateError,
                "artifact path contract differs",
            ):
                runner.validate_static_contract()
            with self.assertRaisesRegex(
                checker.CandidateError,
                "artifact path contract differs",
            ):
                checker.validate_static_contract()
            self.assertEqual(checker.main(["--antecedents"]), 1)

        substituted_root = runner.ROOT / ".build/substituted-v3-output"
        with mock.patch.object(runner.addon_v3, "OUTPUT_ROOT", substituted_root):
            with self.assertRaisesRegex(
                runner.CandidateError,
                "output root contract differs",
            ):
                runner.validate_static_contract()
            with self.assertRaisesRegex(
                checker.CandidateError,
                "output root contract differs",
            ):
                checker.validate_static_contract()

    def test_paths_and_projection_boundaries_are_exact(self) -> None:
        self.assertEqual(len(runner.ARTIFACT_PATHS), 39)
        self.assertEqual(runner.ARTIFACT_PATHS, checker.EXPECTED_ARTIFACT_PATHS)
        self.assertEqual(len(runner.IMPLEMENTATION_PATHS), 17)
        self.assertEqual(
            runner.IMPLEMENTATION_PATHS,
            checker.EXPECTED_IMPLEMENTATION_PATHS,
        )
        self.assertEqual(len(runner.addon_v3.ADDON_RELATIVE_PATHS), 3)
        self.assertEqual(
            len(runner.addon_v3.ANTECEDENT_PROJECTION_RELATIVE_PATHS),
            6,
        )
        self.assertEqual(
            set(runner.addon_v3.ANTECEDENT_PROJECTION_RELATIVE_PATHS),
            set(runner.V3_IMPLEMENTATION_PATHS),
        )
        for path in runner.V3_ADDON_ARTIFACT_PATHS:
            self.assertIn(path, runner.ARTIFACT_PATHS)
        self.assertNotIn(runner.RESULT_RELATIVE_PATH, runner.ARTIFACT_PATHS)

    def test_current_antecedents_pass_after_v3_regeneration(self) -> None:
        v2_record, v3_record = checker.current_antecedent_records()
        self.assertEqual(v2_record, checker.EXPECTED_V2_CANDIDATE_RECORD)
        self.assertEqual(
            v3_record["path"],
            checker.addon_v3.RESULT_PATH.relative_to(checker.ROOT).as_posix(),
        )
        self.assertEqual(v3_record["mode"], 0o600)

    def test_producer_rejects_every_noncanonical_result_path_before_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = (
                runner.V2_CANDIDATE_RELATIVE_PATH,
                runner.ARTIFACT_PATHS[0],
                runner.IMPLEMENTATION_PATHS[0],
                root / ".." / "outside-candidate.json",
                Path(".build/alternate-candidate.json"),
            )
            with (
                mock.patch.object(runner.runtime, "source_snapshot") as source_snapshot,
                mock.patch.object(
                    runner.runtime,
                    "run_gate_with_managed_release_scratch",
                ) as gate_runner,
            ):
                for result_path in cases:
                    with self.subTest(result_path=result_path):
                        with self.assertRaisesRegex(
                            runner.CandidateError,
                            "exact canonical V3 result path",
                        ):
                            runner.produce_candidate(
                                root=root,
                                result_path=result_path,
                                preserve_pid=None,
                            )
            source_snapshot.assert_not_called()
            gate_runner.assert_not_called()

    def test_producer_rejects_symlinked_build_ancestor_before_external_write(self) -> None:
        with (
            tempfile.TemporaryDirectory() as repository,
            tempfile.TemporaryDirectory() as external,
        ):
            root = Path(repository)
            external_root = Path(external)
            (root / ".build").symlink_to(external_root, target_is_directory=True)
            result_path = root / runner.RESULT_RELATIVE_PATH
            with (
                mock.patch.object(runner.runtime, "source_snapshot") as source_snapshot,
                mock.patch.object(
                    runner.runtime,
                    "run_gate_with_managed_release_scratch",
                ) as gate_runner,
            ):
                with self.assertRaisesRegex(
                    runner.CandidateError,
                    "directory chain must be physical",
                ):
                    runner.produce_candidate(
                        root=root,
                        result_path=result_path,
                        preserve_pid=None,
                    )
            source_snapshot.assert_not_called()
            gate_runner.assert_not_called()
            self.assertEqual(tuple(external_root.iterdir()), ())

    def test_payload_records_truthful_new_commands_and_composed_evidence(self) -> None:
        document = valid_document()
        payload = runner.candidate_payload(
            source=document["source"],
            commands=document["commands"],
            artifacts=document["artifacts"],
            implementation=document["implementation"],
            pid_preservation=document["pidPreservation"],
            v2_artifact_preservation=document["v2ArtifactPreservation"],
            composition=document["evidenceComposition"],
        )
        self.assertEqual(payload, document)
        self.assertEqual(len(payload["commands"]), 4)
        self.assertEqual(payload["evidenceComposition"]["antecedent"]["commands"], 71)
        self.assertEqual(payload["evidenceComposition"]["successor"]["commands"], 4)
        self.assertEqual(payload["evidenceComposition"]["composedCommandEvidence"], 75)
        self.assertFalse(payload["evidenceComposition"]["runtimeProductSourceChanged"])
        self.assertEqual(payload["coverage"]["swiftDistinctNonsecurityTests"], 1_120)
        self.assertEqual(payload["coverage"]["swiftNotExecutedTests"], 1_053)
        self.assertTrue(all(value is False for value in payload["limitations"].values()))

    def test_checker_accepts_exact_document_and_requests_exact_file_sets(self) -> None:
        document = valid_document()
        file_records, addon_readback = self.validate_with_fixture(document)
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
        addon_readback.assert_not_called()

    def test_checker_complete_readback_rechecks_artifacts_and_addon(self) -> None:
        document = valid_document()
        file_records, addon_readback = self.validate_with_fixture(
            document,
            run_readbacks=True,
        )
        self.assertEqual(file_records.call_count, 3)
        self.assertEqual(
            file_records.call_args_list[-1].kwargs["expected_paths"],
            checker.EXPECTED_ARTIFACT_PATHS,
        )
        addon_readback.assert_called_once_with(checker.ROOT)

    def test_boolean_coverage_count_is_rejected(self) -> None:
        document = valid_document()
        document["coverage"]["swiftDistinctNonsecurityTests"] = True
        with self.assertRaisesRegex(
            checker.CandidateError,
            "coverage.swiftDistinctNonsecurityTests must be an exact integer",
        ):
            self.validate_with_fixture(document)

    def test_command_mutations_are_rejected(self) -> None:
        mutations = (
            ("copied-antecedent", lambda value: value["commands"].insert(0, value["commands"][0])),
            ("exit", lambda value: value["commands"][0].__setitem__("exitCode", 1)),
            ("timeout-bool", lambda value: value["commands"][0].__setitem__("timeoutSeconds", True)),
            ("argv", lambda value: value["commands"][1]["argv"].append("--broad")),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                document = valid_document()
                mutate(document)
                with self.assertRaises(checker.CandidateError):
                    self.validate_with_fixture(document)

    def test_composition_and_preservation_mutations_are_rejected(self) -> None:
        mutations = (
            lambda value: value["evidenceComposition"].__setitem__("composedCommandEvidence", 76),
            lambda value: value["evidenceComposition"].__setitem__("runtimeProductSourceChanged", True),
            lambda value: value["evidenceComposition"].__setitem__("runtimeProductSourceChanged", 0),
            lambda value: value["evidenceComposition"]["successor"].__setitem__("swiftNewTests", 98),
            lambda value: value["evidenceComposition"]["evidenceOnlySourceDelta"].pop(),
            lambda value: value["v2ArtifactPreservation"].__setitem__("preservedDuringRun", False),
        )
        for mutate in mutations:
            document = valid_document()
            mutate(document)
            with self.assertRaises(checker.CandidateError):
                self.validate_with_fixture(document)

    def test_unrequested_pid_boolean_integer_aliases_are_rejected(self) -> None:
        mutations = (
            lambda value: value["pidPreservation"].__setitem__("pid", False),
            lambda value: value["pidPreservation"].__setitem__("preservedDuringRun", 0),
        )
        for mutate in mutations:
            document = valid_document()
            mutate(document)
            with self.assertRaises(checker.CandidateError):
                self.validate_with_fixture(document)

    def test_checker_cli_rejects_noncanonical_or_ignored_result_paths(self) -> None:
        with mock.patch.object(checker, "load_result") as load_result:
            self.assertEqual(
                checker.main([".build/copied-v3-candidate.json"]),
                1,
            )
            self.assertEqual(
                checker.main(["--antecedents", ".build/copied-v3-candidate.json"]),
                1,
            )
        load_result.assert_not_called()

    def test_unknown_top_level_key_is_rejected(self) -> None:
        document = valid_document()
        document["unexpected"] = True
        with self.assertRaisesRegex(checker.CandidateError, "keys differ"):
            self.validate_with_fixture(document)

    def test_addon_readback_uses_bounded_child_contract(self) -> None:
        process = mock.Mock()
        process.returncode = 0
        with (
            mock.patch.object(checker.subprocess, "Popen", return_value=process) as popen,
            mock.patch.object(
                checker.candidate_base,
                "bounded_child_output",
                return_value=(b"", b""),
            ) as bounded,
        ):
            checker.run_addon_readback(checker.ROOT)
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], checker.ADDON_READBACK_COMMAND)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(
            bounded.call_args.kwargs["command"],
            checker.ADDON_READBACK_COMMAND,
        )

    def test_producer_success_wraps_four_gates_source_pid_and_v2_bytes(self) -> None:
        source = source_fixture()
        events: list[str] = []

        def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
            events.append(f"file:{relative.as_posix()}")
            if relative == runner.V2_CANDIDATE_RELATIVE_PATH:
                return dict(runner.EXPECTED_V2_CANDIDATE_RECORD)
            if relative == runner.addon_v3.RESULT_PATH.relative_to(runner.ROOT):
                return dict(FIXTURE_V3_RESULT_RECORD)
            return {
                "mode": 0o600,
                "path": relative.as_posix(),
                "sha256": "2" * 64,
                "size": 1,
            }

        def run_gate(gate: runner.runtime.Gate, **_kwargs: object):
            events.append(f"gate:{gate.identifier}")
            return command_record(gate), b"", b""

        def source_snapshot(**_kwargs: object) -> dict[str, object]:
            events.append("source")
            return dict(source)

        def process_identity(pid: int) -> str:
            events.append(f"pid:{pid}")
            return "stable-pid"

        with (
            mock.patch.object(runner, "ensure_private_output_directory"),
            mock.patch.object(runner.runtime, "source_snapshot", side_effect=source_snapshot),
            mock.patch.object(runner.runtime, "stable_file_record", side_effect=stable_record),
            mock.patch.object(runner.runtime, "process_identity", side_effect=process_identity),
            mock.patch.object(
                runner.runtime,
                "run_gate_with_managed_release_scratch",
                side_effect=run_gate,
            ) as gate_runner,
            mock.patch.object(runner.runtime, "validate_zero_lint_issues"),
            mock.patch.object(
                runner.addon_v3,
                "candidate_antecedent_failures",
                return_value=[],
            ) as antecedent_readback,
            mock.patch.object(
                runner,
                "current_v3_addon_failures",
                return_value=[],
            ) as addon_postflight,
            mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
        ):
            payload = runner.produce_candidate(
                result_path=runner.ROOT / runner.RESULT_RELATIVE_PATH,
                preserve_pid=59809,
            )
        self.assertEqual(gate_runner.call_count, 4)
        self.assertEqual(len(payload["commands"]), 4)
        self.assertTrue(payload["pidPreservation"]["preservedDuringRun"])
        self.assertTrue(payload["v2ArtifactPreservation"]["preservedDuringRun"])
        self.assertEqual(events.count("source"), 2)
        self.assertEqual(events.count("pid:59809"), 2)
        self.assertEqual(antecedent_readback.call_count, 1)
        self.assertEqual(addon_postflight.call_count, 1)
        self.assertEqual(
            sum(event == f"file:{runner.V2_CANDIDATE_RELATIVE_PATH}" for event in events),
            4,
        )
        self.assertEqual(atomic_write.call_count, 1)
        gate_events = [event for event in events if event.startswith("gate:")]
        self.assertEqual(
            gate_events,
            [f"gate:{gate.identifier}" for gate in runner.ALL_GATES],
        )

    def test_producer_source_drift_rejects_publication(self) -> None:
        before = source_fixture(sha256="1" * 64)
        after = source_fixture(sha256="2" * 64)

        def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
            if relative == runner.V2_CANDIDATE_RELATIVE_PATH:
                return dict(runner.EXPECTED_V2_CANDIDATE_RECORD)
            if relative == runner.addon_v3.RESULT_PATH.relative_to(runner.ROOT):
                return dict(FIXTURE_V3_RESULT_RECORD)
            return {
                "mode": 0o600,
                "path": relative.as_posix(),
                "sha256": "3" * 64,
                "size": 1,
            }

        with (
            mock.patch.object(runner, "ensure_private_output_directory"),
            mock.patch.object(
                runner.runtime,
                "source_snapshot",
                side_effect=(before, after),
            ),
            mock.patch.object(runner.runtime, "stable_file_record", side_effect=stable_record),
            mock.patch.object(
                runner.runtime,
                "run_gate_with_managed_release_scratch",
                side_effect=lambda gate, **_kwargs: (command_record(gate), b"", b""),
            ),
            mock.patch.object(runner.runtime, "validate_zero_lint_issues"),
            mock.patch.object(runner.addon_v3, "candidate_antecedent_failures", return_value=[]),
            mock.patch.object(runner, "current_v3_addon_failures", return_value=[]),
            mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
        ):
            with self.assertRaisesRegex(runner.CandidateError, "source changed"):
                runner.produce_candidate(
                    result_path=runner.ROOT / runner.RESULT_RELATIVE_PATH,
                    preserve_pid=None,
                )
        atomic_write.assert_not_called()

    def test_v2_dependent_artifact_drift_preserves_existing_v3_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / runner.RESULT_RELATIVE_PATH
            result_path.parent.mkdir(parents=True)
            result_path.write_bytes(b"existing-v3-candidate\n")
            result_path.chmod(0o600)

            def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
                if relative == runner.V2_CANDIDATE_RELATIVE_PATH:
                    return dict(runner.EXPECTED_V2_CANDIDATE_RECORD)
                if relative == runner.addon_v3.RESULT_PATH.relative_to(runner.ROOT):
                    return dict(FIXTURE_V3_RESULT_RECORD)
                return {
                    "mode": 0o600,
                    "path": relative.as_posix(),
                    "sha256": "3" * 64,
                    "size": 1,
                }

            with (
                mock.patch.object(runner, "ensure_private_output_directory"),
                mock.patch.object(
                    runner.runtime,
                    "source_snapshot",
                    return_value=source_fixture(),
                ),
                mock.patch.object(
                    runner.runtime,
                    "stable_file_record",
                    side_effect=stable_record,
                ),
                mock.patch.object(
                    runner.runtime,
                    "run_gate_with_managed_release_scratch",
                    side_effect=lambda gate, **_kwargs: (command_record(gate), b"", b""),
                ) as gate_runner,
                mock.patch.object(runner.runtime, "validate_zero_lint_issues"),
                mock.patch.object(
                    runner.addon_v3,
                    "candidate_antecedent_failures",
                    return_value=[],
                ) as antecedent_readback,
                mock.patch.object(
                    runner,
                    "current_v3_addon_failures",
                    return_value=["V2 artifact bytes differ"],
                ) as addon_postflight,
                mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
            ):
                with self.assertRaisesRegex(
                    runner.CandidateError,
                    "V2/V3 antecedent evidence changed",
                ):
                    runner.produce_candidate(
                        root=root,
                        result_path=result_path,
                        preserve_pid=None,
                    )
            self.assertEqual(gate_runner.call_count, 4)
            self.assertEqual(antecedent_readback.call_count, 1)
            self.assertEqual(addon_postflight.call_count, 1)
            atomic_write.assert_not_called()
            self.assertEqual(result_path.read_bytes(), b"existing-v3-candidate\n")

    def test_v3_nonresult_artifact_drift_preserves_existing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / runner.RESULT_RELATIVE_PATH
            result_path.parent.mkdir(parents=True)
            result_path.write_bytes(b"existing-v3-candidate\n")
            result_path.chmod(0o600)
            binding_path = runner.ADDON_OUTPUT_PARENT / "binding.json"
            binding_reads = 0

            def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
                nonlocal binding_reads
                if relative == runner.V2_CANDIDATE_RELATIVE_PATH:
                    return dict(runner.EXPECTED_V2_CANDIDATE_RECORD)
                if relative == binding_path:
                    binding_reads += 1
                    return {
                        "mode": 0o600,
                        "path": relative.as_posix(),
                        "sha256": ("4" if binding_reads == 1 else "5") * 64,
                        "size": 1,
                    }
                return {
                    "mode": 0o600,
                    "path": relative.as_posix(),
                    "sha256": "3" * 64,
                    "size": 1,
                }

            with (
                mock.patch.object(runner, "ensure_private_output_directory"),
                mock.patch.object(
                    runner.runtime,
                    "source_snapshot",
                    return_value=source_fixture(),
                ),
                mock.patch.object(
                    runner.runtime,
                    "stable_file_record",
                    side_effect=stable_record,
                ),
                mock.patch.object(
                    runner.runtime,
                    "run_gate_with_managed_release_scratch",
                    side_effect=lambda gate, **_kwargs: (command_record(gate), b"", b""),
                ),
                mock.patch.object(runner.runtime, "validate_zero_lint_issues"),
                mock.patch.object(
                    runner.addon_v3,
                    "candidate_antecedent_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    runner,
                    "current_v3_addon_failures",
                    return_value=[],
                ),
                mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
            ):
                with self.assertRaisesRegex(
                    runner.CandidateError,
                    "artifact bytes changed during postflight",
                ):
                    runner.produce_candidate(
                        root=root,
                        result_path=result_path,
                        preserve_pid=None,
                    )
            self.assertEqual(binding_reads, 2)
            atomic_write.assert_not_called()
            self.assertEqual(result_path.read_bytes(), b"existing-v3-candidate\n")

    def test_v2_or_pid_drift_preserves_existing_v3_candidate(self) -> None:
        for drift_kind, expected_error in (
            ("v2", "V2 antecedent candidate changed"),
            ("pid", "preserved PID 59809 changed"),
        ):
            with self.subTest(drift_kind=drift_kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result_path = root / runner.RESULT_RELATIVE_PATH
                result_path.parent.mkdir(parents=True)
                result_path.write_bytes(b"existing-v3-candidate\n")
                result_path.chmod(0o600)
                v2_calls = 0

                def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
                    nonlocal v2_calls
                    if relative == runner.V2_CANDIDATE_RELATIVE_PATH:
                        v2_calls += 1
                        record = dict(runner.EXPECTED_V2_CANDIDATE_RECORD)
                        if drift_kind == "v2" and v2_calls == 3:
                            record["sha256"] = "9" * 64
                        return record
                    if relative == runner.addon_v3.RESULT_PATH.relative_to(runner.ROOT):
                        return dict(FIXTURE_V3_RESULT_RECORD)
                    return {
                        "mode": 0o600,
                        "path": relative.as_posix(),
                        "sha256": "3" * 64,
                        "size": 1,
                    }

                identities = (
                    ["pid-before", "pid-after"]
                    if drift_kind == "pid"
                    else ["pid-stable", "pid-stable"]
                )
                with (
                    mock.patch.object(runner, "ensure_private_output_directory"),
                    mock.patch.object(runner.runtime, "source_snapshot", return_value=source_fixture()),
                    mock.patch.object(runner.runtime, "stable_file_record", side_effect=stable_record),
                    mock.patch.object(runner.runtime, "process_identity", side_effect=identities),
                    mock.patch.object(
                        runner.runtime,
                        "run_gate_with_managed_release_scratch",
                        side_effect=lambda gate, **_kwargs: (command_record(gate), b"", b""),
                    ) as gate_runner,
                    mock.patch.object(runner.runtime, "validate_zero_lint_issues"),
                    mock.patch.object(runner.addon_v3, "candidate_antecedent_failures", return_value=[]),
                    mock.patch.object(runner, "current_v3_addon_failures", return_value=[]),
                    mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
                ):
                    with self.assertRaisesRegex(runner.CandidateError, expected_error):
                        runner.produce_candidate(
                            root=root,
                            result_path=result_path,
                            preserve_pid=59809,
                        )
                self.assertEqual(gate_runner.call_count, 4)
                self.assertEqual(v2_calls, 3 if drift_kind == "v2" else 4)
                atomic_write.assert_not_called()
                self.assertEqual(result_path.read_bytes(), b"existing-v3-candidate\n")

    def test_addon_failure_preserves_existing_v3_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / runner.RESULT_RELATIVE_PATH
            result_path.parent.mkdir(parents=True)
            result_path.write_bytes(b"existing-v3-candidate\n")
            result_path.chmod(0o600)

            def fail_on_run(gate: runner.runtime.Gate, **_kwargs: object):
                if gate.identifier == "g7-reviewed-nonsecurity-swift-addon-v3-run":
                    raise runner.CandidateError("injected V3 add-on failure")
                return command_record(gate), b"", b""

            with (
                mock.patch.object(runner, "ensure_private_output_directory"),
                mock.patch.object(runner.runtime, "source_snapshot", return_value=source_fixture()),
                mock.patch.object(
                    runner.runtime,
                    "stable_file_record",
                    return_value=dict(runner.EXPECTED_V2_CANDIDATE_RECORD),
                ),
                mock.patch.object(
                    runner.runtime,
                    "run_gate_with_managed_release_scratch",
                    side_effect=fail_on_run,
                ) as gate_runner,
                mock.patch.object(runner.addon_v3, "candidate_antecedent_failures", return_value=[]),
            ):
                with self.assertRaisesRegex(runner.CandidateError, "injected"):
                    runner.produce_candidate(
                        root=root,
                        result_path=result_path,
                        preserve_pid=None,
                    )
            self.assertEqual(gate_runner.call_count, 2)
            self.assertEqual(result_path.read_bytes(), b"existing-v3-candidate\n")


if __name__ == "__main__":
    unittest.main()
