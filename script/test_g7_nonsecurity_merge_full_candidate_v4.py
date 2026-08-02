#!/usr/bin/env python3
"""Contract tests for the composed non-security G7 candidate V4."""

from __future__ import annotations

import ast
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from script import check_g7_nonsecurity_merge_full_candidate_v4 as checker
from script import run_g7_nonsecurity_merge_full_candidate_v4 as runner


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
FIXTURE_V4_RESULT_RECORD = {
    "mode": 0o600,
    "path": checker.addon_v4.RESULT_PATH.relative_to(checker.ROOT).as_posix(),
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
        "fileCount": 1_014,
        "sha256": sha256,
        "size": 1,
    }


def valid_document() -> dict[str, object]:
    v3_record = dict(checker.EXPECTED_V3_CANDIDATE_RECORD)
    v4_record = dict(FIXTURE_V4_RESULT_RECORD)
    return {
        "artifacts": [],
        "commands": [command_record(gate) for gate in runner.ALL_GATES],
        "contract": checker.CONTRACT,
        "coverage": dict(checker.EXPECTED_COVERAGE),
        "evidenceComposition": checker.expected_composition(
            v3_candidate=v3_record,
            v4_addon_result=v4_record,
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
        "v3ArtifactPreservation": {
            "after": v3_record,
            "before": v3_record,
            "preservedDuringRun": True,
        },
    }


def valid_addon_document() -> dict[str, object]:
    artifact_paths = {
        "antecedentCandidate": checker.V3_CANDIDATE_RELATIVE_PATH,
        "binding": checker.ADDON_OUTPUT_PARENT / "binding.json",
        "console": checker.ADDON_OUTPUT_PARENT / "console.log",
        "executionContract": checker.ADDON_OUTPUT_PARENT / "execution-contract.json",
        "reviewedIdentityManifest": checker.addon_v4.REVIEWED_IDENTITY_RELATIVE_PATH,
        "runMarker": checker.ADDON_OUTPUT_PARENT / "run-marker.json",
        "testList": checker.addon_v4.TEST_LIST_PATH.relative_to(checker.ROOT),
    }
    artifacts = {
        label: {
            "bytes": 1,
            "mode": 0o644 if label == "reviewedIdentityManifest" else 0o600,
            "path": path.as_posix(),
            "sha256": "8" * 64,
        }
        for label, path in artifact_paths.items()
    }
    return {
        "artifacts": artifacts,
        "contract": "aetherlink-g7-reviewed-nonsecurity-swift-addon-v4",
        "limitations": {
            "canonicalG7ExitClaimed": False,
            "canonicalMergeFullClaimed": False,
            "completeSwiftSuiteClaimed": False,
            "deviceOrNetworkClaimed": False,
            "hostedCiClaimed": False,
            "securityAuthenticationOrSecureChannelSuitesExecuted": False,
            "signedArtifactsClaimed": False,
            "v1Claimed": False,
        },
        "partition": {
            "antecedentDistinct": {
                "manifestSha256": "aaa5bfb601c28f89e52ab8d1d8da95c81b876eb4d5ea2cc0d1afb8f2ccd2bf18",
                "tests": 1_120,
            },
            "discovered": {
                "manifestSha256": "0a550e58480f4733abc264d0ec572e9511492a43dae6ea2dd5459c03548f4e65",
                "tests": 2_173,
            },
            "distinctAfterAddon": {
                "manifestSha256": "533de55b52fcda0f8af1871585e11fa846fdec6055c868791981ad5388711e67",
                "tests": 1_173,
            },
            "excludedByScope": {
                "manifestSha256": "c67806715d2ebbbc48395eaec9308d2c62946dd4c82ae1438aec157b05ebb488",
                "tests": 913,
            },
            "excludedExternal": {
                "manifestSha256": "0a641f6aa0d29985b3ac2f942cd8e78267c95d65c362cf0a03ee3ace1fb1585a",
                "tests": 87,
            },
            "newExecuted": {
                "manifestSha256": "0f625c53d1045b750b8a925c969df6d3a902b9d4bd5ed65c3fb283d518f1ca4e",
                "tests": 53,
            },
            "remaining": {
                "manifestSha256": "21353f330c03455a4cb66b55bc80846809c3505a1edfa77ea0695188fa908ee8",
                "tests": 1_000,
            },
            "reviewedInput": {
                "manifestSha256": "bc896a061126bb1958ac7c50ea6558ad174bb82418a7d2687cf99e2489d1e697",
                "tests": 1_053,
            },
        },
        "result": "passed",
        "schemaVersion": 1,
        "scope": {
            "classifiedReviewedInputTests": 1_053,
            "selectedByClass": {
                "AccessibilityAnnouncementTests": 1,
                "AetherLinkLocalizationTests": 39,
                "AetherLinkRenderSmokeTests": 11,
                "LocalRuntimeMessageRouterTests": 1,
                "PairingRouteNoticeTests": 1,
            },
            "selectedByModule": {
                "CompanionCoreTests.": 1,
                "LocalAgentBridgeTests.": 52,
            },
            "securityAuthenticationOrSecureChannelSuitesExecuted": False,
            "unclassifiedTests": 0,
        },
    }


class G7NonsecurityMergeFullCandidateV4Tests(unittest.TestCase):
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
                    dict(checker.EXPECTED_V3_CANDIDATE_RECORD),
                    dict(FIXTURE_V4_RESULT_RECORD),
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

    def test_independent_addon_result_schema_accepts_exact_document(self) -> None:
        document = valid_addon_document()
        by_path = {
            Path(record["path"]): dict(record)
            for record in document["artifacts"].values()
        }
        with mock.patch.object(
            checker,
            "_current_addon_artifact_record",
            side_effect=lambda relative, **_kwargs: by_path[relative],
        ):
            checker.validate_v4_addon_result_document(document)

    def test_independent_addon_result_schema_rejects_boolean_and_shape_drift(self) -> None:
        mutations = (
            lambda value: value["partition"]["newExecuted"].__setitem__("tests", True),
            lambda value: value["scope"]["selectedByClass"].__setitem__(
                "AetherLinkLocalizationTests", True
            ),
            lambda value: value["artifacts"]["binding"].__setitem__("bytes", True),
            lambda value: value.__setitem__("unexpected", False),
        )
        for mutate in mutations:
            document = valid_addon_document()
            by_path = {
                Path(record["path"]): dict(record)
                for record in document["artifacts"].values()
            }
            mutate(document)
            with self.subTest(mutation=mutate), mock.patch.object(
                checker,
                "_current_addon_artifact_record",
                side_effect=lambda relative, **_kwargs: by_path[relative],
            ):
                with self.assertRaises(checker.CandidateError):
                    checker.validate_v4_addon_result_document(document)

    def test_static_contract_is_exact_immutable_75_plus_new_4(self) -> None:
        runner.validate_static_contract()
        checker.validate_static_contract()
        self.assertEqual(len(runner.base.EXPECTED_COMMAND_IDS), 4)
        self.assertEqual(runner.base.COMPOSED_COMMAND_EVIDENCE_COUNT, 75)
        self.assertEqual(len(runner.ALL_GATES), 4)
        self.assertEqual(
            runner.EXPECTED_COMMAND_IDS,
            (
                "g7-reviewed-nonsecurity-swift-addon-v4-prepare",
                "g7-reviewed-nonsecurity-swift-addon-v4-run",
                "g7-reviewed-nonsecurity-swift-addon-v4-write-binding",
                "g7-reviewed-nonsecurity-swift-addon-v4-results",
            ),
        )
        self.assertEqual(checker.EXPECTED_COMMAND_IDS, runner.EXPECTED_COMMAND_IDS)
        self.assertEqual(runner.COMPOSED_COMMAND_EVIDENCE_COUNT, 79)
        for gate, (identifier, argv, timeout) in zip(
            runner.ADDITIONAL_GATES,
            checker.ADDITIONAL_COMMAND_SPECS,
        ):
            self.assertEqual(
                (gate.identifier, gate.argv, gate.timeout_seconds),
                (identifier, argv, timeout),
            )

    def test_checker_source_does_not_import_v4_candidate_runner(self) -> None:
        tree = ast.parse(
            Path(checker.__file__).read_text(encoding="utf-8"),
            filename=checker.__file__,
        )
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)
                imported.extend(
                    f"{node.module}.{alias.name}" for alias in node.names
                )
        self.assertFalse(
            any(
                "run_g7_nonsecurity_merge_full_candidate_v4" in name
                for name in imported
            ),
            imported,
        )

    def test_antecedent_mode_fails_when_selector_contract_drifts(self) -> None:
        with mock.patch.object(
            checker.addon_v4,
            "contract_inputs",
            return_value=(None, ["injected selector drift"]),
        ):
            self.assertEqual(checker.main(["--antecedents"]), 1)

    def test_candidate_loader_rejects_mode_symlink_and_hardlink(self) -> None:
        payload = checker.candidate_base.canonical_json_bytes({})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / checker.RESULT_RELATIVE_PATH
            canonical.parent.mkdir(parents=True)

            canonical.write_bytes(payload)
            canonical.chmod(0o644)
            with self.assertRaises(checker.CandidateError):
                checker.load_result(canonical, root=root)
            canonical.unlink()

            target = canonical.parent / "target.json"
            target.write_bytes(payload)
            target.chmod(0o600)
            canonical.symlink_to(target)
            with self.assertRaises(checker.CandidateError):
                checker.load_result(canonical, root=root)
            canonical.unlink()

            canonical.write_bytes(payload)
            canonical.chmod(0o600)
            hardlink = canonical.parent / "hardlink.json"
            os.link(canonical, hardlink)
            with self.assertRaises(checker.CandidateError):
                checker.load_result(canonical, root=root)

    def test_static_contract_rejects_same_count_addon_path_drift(self) -> None:
        substituted_binding = (
            runner.ROOT
            / runner.ADDON_OUTPUT_PARENT
            / "same-count-substituted-binding.json"
        )
        with mock.patch.object(
            runner.addon_v4,
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

        substituted_root = runner.ROOT / ".build/substituted-v4-output"
        with mock.patch.object(runner.addon_v4, "OUTPUT_ROOT", substituted_root):
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
        self.assertEqual(len(runner.ARTIFACT_PATHS), 46)
        self.assertEqual(runner.ARTIFACT_PATHS, checker.EXPECTED_ARTIFACT_PATHS)
        self.assertEqual(len(runner.IMPLEMENTATION_PATHS), 23)
        self.assertEqual(
            runner.IMPLEMENTATION_PATHS,
            checker.EXPECTED_IMPLEMENTATION_PATHS,
        )
        self.assertEqual(len(runner.addon_v4.ADDON_RELATIVE_PATHS), 3)
        self.assertEqual(
            len(runner.addon_v4.ANTECEDENT_PROJECTION_RELATIVE_PATHS),
            6,
        )
        self.assertEqual(
            set(runner.addon_v4.ANTECEDENT_PROJECTION_RELATIVE_PATHS),
            set(runner.V4_IMPLEMENTATION_PATHS),
        )
        for path in runner.V4_ADDON_ARTIFACT_PATHS:
            self.assertIn(path, runner.ARTIFACT_PATHS)
        self.assertNotIn(runner.RESULT_RELATIVE_PATH, runner.ARTIFACT_PATHS)

    def test_current_v3_antecedent_passes_before_v4_run(self) -> None:
        self.assertEqual(checker.addon_v4.candidate_antecedent_failures(), [])
        v3_record = checker.candidate_base.file_record(
            checker.ROOT,
            checker.V3_CANDIDATE_RELATIVE_PATH,
            maximum_bytes=checker.RESULT_MAX_BYTES,
        )
        self.assertEqual(v3_record, checker.EXPECTED_V3_CANDIDATE_RECORD)

    def test_producer_rejects_every_noncanonical_result_path_before_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = (
                runner.V3_CANDIDATE_RELATIVE_PATH,
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
                            "exact canonical V4 result path",
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
            v3_artifact_preservation=document["v3ArtifactPreservation"],
            composition=document["evidenceComposition"],
        )
        self.assertEqual(payload, document)
        self.assertEqual(len(payload["commands"]), 4)
        self.assertEqual(payload["evidenceComposition"]["antecedent"]["commands"], 75)
        self.assertEqual(payload["evidenceComposition"]["successor"]["commands"], 4)
        self.assertEqual(payload["evidenceComposition"]["composedCommandEvidence"], 79)
        self.assertFalse(payload["evidenceComposition"]["runtimeProductSourceChanged"])
        self.assertEqual(payload["coverage"]["swiftDistinctNonsecurityTests"], 1_173)
        self.assertEqual(payload["coverage"]["swiftNotExecutedTests"], 1_000)
        self.assertEqual(payload["coverage"]["swiftReviewedAddonTests"], 776)
        self.assertEqual(payload["coverage"]["swiftReviewedMethodTests"], 465)
        self.assertEqual(
            payload["coverage"]["swiftRunnerReviewedBeforeExclusion"],
            861,
        )
        self.assertTrue(all(value is False for value in payload["limitations"].values()))

    def test_checker_accepts_exact_document_and_requests_exact_file_sets(self) -> None:
        document = valid_document()
        file_records, addon_readback = self.validate_with_fixture(document)
        self.assertEqual(file_records.call_count, 4)
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
        self.assertEqual(
            file_records.call_args_list[3].kwargs["expected_paths"],
            checker.EXPECTED_IMPLEMENTATION_PATHS,
        )
        addon_readback.assert_not_called()

    def test_checker_complete_readback_rechecks_artifacts_and_addon(self) -> None:
        document = valid_document()
        file_records, addon_readback = self.validate_with_fixture(
            document,
            run_readbacks=True,
        )
        self.assertEqual(file_records.call_count, 4)
        self.assertEqual(
            file_records.call_args_list[-1].kwargs["expected_paths"],
            checker.EXPECTED_IMPLEMENTATION_PATHS,
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
            lambda value: value["evidenceComposition"].__setitem__("composedCommandEvidence", 80),
            lambda value: value["evidenceComposition"].__setitem__("runtimeProductSourceChanged", True),
            lambda value: value["evidenceComposition"].__setitem__("runtimeProductSourceChanged", 0),
            lambda value: value["evidenceComposition"]["successor"].__setitem__("swiftNewTests", 54),
            lambda value: value["evidenceComposition"]["evidenceOnlySourceDelta"].pop(),
            lambda value: value["v3ArtifactPreservation"].__setitem__("preservedDuringRun", False),
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
                checker.main([".build/copied-v4-candidate.json"]),
                1,
            )
            self.assertEqual(
                checker.main(["--antecedents", ".build/copied-v4-candidate.json"]),
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

    def test_producer_success_wraps_four_gates_source_pid_and_v3_bytes(self) -> None:
        source = source_fixture()
        events: list[str] = []

        def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
            events.append(f"file:{relative.as_posix()}")
            if relative == runner.V3_CANDIDATE_RELATIVE_PATH:
                return dict(runner.EXPECTED_V3_CANDIDATE_RECORD)
            if relative == runner.addon_v4.RESULT_PATH.relative_to(runner.ROOT):
                return dict(FIXTURE_V4_RESULT_RECORD)
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
                runner.addon_v4,
                "candidate_antecedent_failures",
                return_value=[],
            ) as antecedent_readback,
            mock.patch.object(
                runner,
                "current_v4_addon_failures",
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
        self.assertTrue(payload["v3ArtifactPreservation"]["preservedDuringRun"])
        self.assertEqual(events.count("source"), 2)
        self.assertEqual(events.count("pid:59809"), 2)
        self.assertEqual(antecedent_readback.call_count, 1)
        self.assertEqual(addon_postflight.call_count, 1)
        self.assertEqual(
            sum(event == f"file:{runner.V3_CANDIDATE_RELATIVE_PATH}" for event in events),
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
            if relative == runner.V3_CANDIDATE_RELATIVE_PATH:
                return dict(runner.EXPECTED_V3_CANDIDATE_RECORD)
            if relative == runner.addon_v4.RESULT_PATH.relative_to(runner.ROOT):
                return dict(FIXTURE_V4_RESULT_RECORD)
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
            mock.patch.object(runner.addon_v4, "candidate_antecedent_failures", return_value=[]),
            mock.patch.object(runner, "current_v4_addon_failures", return_value=[]),
            mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
        ):
            with self.assertRaisesRegex(runner.CandidateError, "source changed"):
                runner.produce_candidate(
                    result_path=runner.ROOT / runner.RESULT_RELATIVE_PATH,
                    preserve_pid=None,
                )
        atomic_write.assert_not_called()

    def test_v3_dependent_artifact_drift_preserves_existing_v4_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / runner.RESULT_RELATIVE_PATH
            result_path.parent.mkdir(parents=True)
            result_path.write_bytes(b"existing-v4-candidate\n")
            result_path.chmod(0o600)

            def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
                if relative == runner.V3_CANDIDATE_RELATIVE_PATH:
                    return dict(runner.EXPECTED_V3_CANDIDATE_RECORD)
                if relative == runner.addon_v4.RESULT_PATH.relative_to(runner.ROOT):
                    return dict(FIXTURE_V4_RESULT_RECORD)
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
                    runner.addon_v4,
                    "candidate_antecedent_failures",
                    return_value=[],
                ) as antecedent_readback,
                mock.patch.object(
                    runner,
                    "current_v4_addon_failures",
                    return_value=["V3 artifact bytes differ"],
                ) as addon_postflight,
                mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
            ):
                with self.assertRaisesRegex(
                    runner.CandidateError,
                    "V3/V4 antecedent evidence changed",
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
            self.assertEqual(result_path.read_bytes(), b"existing-v4-candidate\n")

    def test_v4_nonresult_artifact_drift_preserves_existing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / runner.RESULT_RELATIVE_PATH
            result_path.parent.mkdir(parents=True)
            result_path.write_bytes(b"existing-v4-candidate\n")
            result_path.chmod(0o600)
            binding_path = runner.ADDON_OUTPUT_PARENT / "binding.json"
            binding_reads = 0

            def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
                nonlocal binding_reads
                if relative == runner.V3_CANDIDATE_RELATIVE_PATH:
                    return dict(runner.EXPECTED_V3_CANDIDATE_RECORD)
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
                    runner.addon_v4,
                    "candidate_antecedent_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    runner,
                    "current_v4_addon_failures",
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
            self.assertEqual(result_path.read_bytes(), b"existing-v4-candidate\n")

    def test_v3_or_pid_drift_preserves_existing_v4_candidate(self) -> None:
        for drift_kind, expected_error in (
            ("v3", "V3 antecedent candidate changed"),
            ("pid", "preserved PID 59809 changed"),
        ):
            with self.subTest(drift_kind=drift_kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result_path = root / runner.RESULT_RELATIVE_PATH
                result_path.parent.mkdir(parents=True)
                result_path.write_bytes(b"existing-v4-candidate\n")
                result_path.chmod(0o600)
                v3_calls = 0

                def stable_record(relative: Path, **_kwargs: object) -> dict[str, object]:
                    nonlocal v3_calls
                    if relative == runner.V3_CANDIDATE_RELATIVE_PATH:
                        v3_calls += 1
                        record = dict(runner.EXPECTED_V3_CANDIDATE_RECORD)
                        if drift_kind == "v3" and v3_calls == 3:
                            record["sha256"] = "9" * 64
                        return record
                    if relative == runner.addon_v4.RESULT_PATH.relative_to(runner.ROOT):
                        return dict(FIXTURE_V4_RESULT_RECORD)
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
                    mock.patch.object(runner.addon_v4, "candidate_antecedent_failures", return_value=[]),
                    mock.patch.object(runner, "current_v4_addon_failures", return_value=[]),
                    mock.patch.object(runner.runtime, "atomic_write") as atomic_write,
                ):
                    with self.assertRaisesRegex(runner.CandidateError, expected_error):
                        runner.produce_candidate(
                            root=root,
                            result_path=result_path,
                            preserve_pid=59809,
                        )
                self.assertEqual(gate_runner.call_count, 4)
                self.assertEqual(v3_calls, 3 if drift_kind == "v3" else 4)
                atomic_write.assert_not_called()
                self.assertEqual(result_path.read_bytes(), b"existing-v4-candidate\n")

    def test_addon_failure_preserves_existing_v4_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / runner.RESULT_RELATIVE_PATH
            result_path.parent.mkdir(parents=True)
            result_path.write_bytes(b"existing-v4-candidate\n")
            result_path.chmod(0o600)

            def fail_on_run(gate: runner.runtime.Gate, **_kwargs: object):
                if gate.identifier == "g7-reviewed-nonsecurity-swift-addon-v4-run":
                    raise runner.CandidateError("injected V4 add-on failure")
                return command_record(gate), b"", b""

            with (
                mock.patch.object(runner, "ensure_private_output_directory"),
                mock.patch.object(runner.runtime, "source_snapshot", return_value=source_fixture()),
                mock.patch.object(
                    runner.runtime,
                    "stable_file_record",
                    return_value=dict(runner.EXPECTED_V3_CANDIDATE_RECORD),
                ),
                mock.patch.object(
                    runner.runtime,
                    "run_gate_with_managed_release_scratch",
                    side_effect=fail_on_run,
                ) as gate_runner,
                mock.patch.object(runner.addon_v4, "candidate_antecedent_failures", return_value=[]),
            ):
                with self.assertRaisesRegex(runner.CandidateError, "injected"):
                    runner.produce_candidate(
                        root=root,
                        result_path=result_path,
                        preserve_pid=None,
                    )
            self.assertEqual(gate_runner.call_count, 2)
            self.assertEqual(result_path.read_bytes(), b"existing-v4-candidate\n")


if __name__ == "__main__":
    unittest.main()
