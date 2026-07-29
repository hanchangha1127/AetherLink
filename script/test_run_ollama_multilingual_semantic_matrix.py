#!/usr/bin/env python3
"""Focused tests for the five-locale Ollama semantic runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script import run_ollama_multilingual_semantic_matrix as runner


class OllamaMultilingualSemanticMatrixTests(unittest.TestCase):
    def selected_model(
        self,
        root: Path,
    ) -> runner.base.SelectedLocalModel:
        manifest = root / "manifests" / "model"
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes(b"manifest")
        blobs: list[runner.base.SnapshotBlob] = []
        for index in range(4):
            source = root / "blobs" / f"blob-{index}"
            source.parent.mkdir(parents=True, exist_ok=True)
            content = f"blob-{index}".encode()
            source.write_bytes(content)
            blobs.append(
                runner.base.SnapshotBlob(
                    source_path=source,
                    relative_path=Path("blobs") / source.name,
                    size_bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                )
            )
        return runner.base.SelectedLocalModel(
            provider_model_id="private-embedding-model:latest",
            manifest_digest=hashlib.sha256(b"manifest").hexdigest(),
            reported_size_bytes=sum(blob.size_bytes for blob in blobs),
            manifest_source_path=manifest,
            manifest_relative_path=Path("manifests") / "model",
            manifest_size_bytes=len(b"manifest"),
            blobs=tuple(blobs),
            capabilities=("embedding",),
        )

    def task_set(self) -> dict[str, object]:
        return runner.base.strict_json_loads(
            runner.recorded_task_set_bytes(),
            label="multilingual semantic test task set",
        )

    def expected_failure_log(
        self,
        *,
        locale: str = "ko",
        ordinal: int = 2,
    ) -> str:
        suite, separator, method = runner.LIVE_TEST_FILTER.rpartition(".")
        self.assertTrue(separator)
        identifier = f"OllamaBackendTests.{suite} {method}"
        return "\n".join(
            (
                f"Test Case '-[{identifier}]' started.",
                (
                    "OllamaEmbeddingMultilingualSemanticQualityTests.swift:1: "
                    "error: test threw error "
                    '"positiveMarginFailed(locale: '
                    f'\\"{locale}\\", scenarioOrdinalWithinLocale: '
                    f'{ordinal})"'
                ),
                f"Test Case '-[{identifier}]' failed (0.001 seconds).",
            )
        )

    def test_recorded_sources_and_task_set_are_exact(self) -> None:
        runner.assert_bound_sources()
        data = runner.recorded_task_set_bytes()
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            runner.TASK_SET_SHA256,
        )
        value = self.task_set()
        runner.validate_task_set(value)
        self.assertEqual(value["locales"], list(runner.SUPPORTED_LOCALES))
        self.assertEqual(len(value["firstCall"]), 80)
        self.assertEqual(len(value["scenarios"]), 20)

    def test_task_set_rejects_shape_locale_and_unicode_mutations(
        self,
    ) -> None:
        value = self.task_set()

        def mutated() -> dict[str, object]:
            return json.loads(json.dumps(value, ensure_ascii=False))

        mutations: list[tuple[str, dict[str, object]]] = []

        boolean_threshold = mutated()
        boolean_threshold["minimumPositiveMarginBasisPoints"] = True
        mutations.append(("boolean threshold", boolean_threshold))

        unsupported_locale = mutated()
        unsupported_locale["locales"][-1] = "de"
        mutations.append(("unsupported locale", unsupported_locale))

        duplicate_input = mutated()
        duplicate_input["firstCall"][1]["id"] = (
            duplicate_input["firstCall"][0]["id"]
        )
        mutations.append(("duplicate input", duplicate_input))

        non_nfc = mutated()
        non_nfc["firstCall"][64]["text"] = "Cafe\u0301"
        mutations.append(("non-NFC text", non_nfc))

        format_character = mutated()
        format_character["firstCall"][16]["text"] = (
            "강아지\u200b가 달린다."
        )
        mutations.append(("format character", format_character))

        cross_locale = mutated()
        cross_locale["scenarios"][4]["queryId"] = "ja-puppy-query"
        mutations.append(("cross-locale role", cross_locale))

        locale_count = mutated()
        locale_count["firstCall"][16]["locale"] = "ja"
        mutations.append(("locale text count", locale_count))

        extra_key = mutated()
        extra_key["unexpected"] = True
        mutations.append(("extra key", extra_key))

        for label, mutation in mutations:
            with (
                self.subTest(label=label),
                self.assertRaises(runner.MatrixFailure),
            ):
                runner.validate_task_set(mutation)

    def test_recorded_fixture_is_closed_and_has_locale_results(
        self,
    ) -> None:
        fixture = runner.recorded_fixture()
        runner.validate_recorded_fixture(fixture)
        self.assertIs(fixture["qualityGatePassed"], False)
        self.assertEqual(
            fixture["resultStatus"],
            "observed-quality-failure",
        )
        self.assertEqual(fixture["semanticObservationCount"], 2)
        self.assertEqual(fixture["recoveryObservationCount"], 2)
        self.assertEqual(
            fixture["taskSet"]["locales"],
            list(runner.SUPPORTED_LOCALES),
        )
        self.assertEqual(fixture["thresholds"]["localeCount"], 5)
        self.assertEqual(fixture["thresholds"]["scenarioCount"], 20)
        self.assertEqual(fixture["thresholds"]["textsPerBatch"], 80)
        self.assertEqual(
            fixture["thresholds"]["embeddingCountPerVersion"],
            160,
        )
        for version in fixture["versions"]:
            self.assertIs(
                version["semantic"]["adapterTestPassed"],
                False,
            )
            self.assertIs(
                version["semantic"]["qualityGatePassed"],
                False,
            )
            self.assertIs(
                version["recovery"]["adapterTestPassed"],
                True,
            )
            self.assertIs(
                version["recovery"]["modelUnloadConfirmed"],
                True,
            )
            self.assertEqual(
                [
                    row["locale"]
                    for row in version["semantic"]["localeResults"]
                ],
                list(runner.SUPPORTED_LOCALES),
            )

        task_set = self.task_set()
        serialized = json.dumps(
            fixture,
            ensure_ascii=True,
            sort_keys=True,
        )
        for row in task_set["firstCall"]:
            self.assertNotIn(row["id"], serialized)
            self.assertNotIn(row["text"], serialized)
            escaped = json.dumps(
                row["text"],
                ensure_ascii=True,
            )[1:-1]
            self.assertNotIn(escaped, serialized)

    def test_recorded_fixture_rejects_type_identity_and_locale_drift(
        self,
    ) -> None:
        fixture = runner.recorded_fixture()
        mutations = (
            (
                ("semanticObservationCount",),
                True,
            ),
            (
                ("taskSet", "sha256"),
                "0" * 64,
            ),
            (
                ("taskSet", "locales", 0),
                "de",
            ),
            (
                ("thresholds", "embeddingCountPerVersion"),
                32,
            ),
            (
                (
                    "versions",
                    0,
                    "semantic",
                    "localeResults",
                    0,
                    "allMarginsPassed",
                ),
                False,
            ),
            (
                (
                    "sourceBindings",
                    "scorerAndLiveAssertionSha256",
                ),
                "0" * 64,
            ),
        )
        for path, replacement in mutations:
            with self.subTest(path=path):
                value = json.loads(json.dumps(fixture))
                target = value
                for component in path[:-1]:
                    target = target[component]
                target[path[-1]] = replacement
                with self.assertRaises(runner.MatrixFailure):
                    runner.validate_recorded_fixture(value)

        extra_key = json.loads(json.dumps(fixture))
        extra_key["unexpected"] = True
        with self.assertRaises(runner.MatrixFailure):
            runner.validate_recorded_fixture(extra_key)

    def test_input_nonretention_rejects_raw_and_escaped_text(
        self,
    ) -> None:
        task_set = self.task_set()
        source = Path("/private/source/models")
        selected = "private-embedding-model:latest"
        runner.assert_result_does_not_retain_inputs(
            runner.recorded_fixture(),
            selected_model_id=selected,
            source_models_directory=source,
            task_set=task_set,
        )
        korean_text = task_set["firstCall"][16]["text"]
        cases = (
            {"leak": korean_text},
            {
                "leak": json.dumps(
                    korean_text,
                    ensure_ascii=True,
                )[1:-1]
            },
            {"leak": task_set["firstCall"][16]["id"]},
            {"leak": selected},
            {"leak": str(source)},
        )
        for index, value in enumerate(cases):
            with (
                self.subTest(index=index),
                self.assertRaises(runner.MatrixFailure),
            ):
                runner.assert_result_does_not_retain_inputs(
                    value,
                    selected_model_id=selected,
                    source_models_directory=source,
                    task_set=task_set,
                )

    def test_source_binding_drift_is_rejected(self) -> None:
        for label, constant in (
            ("base compatibility runner", "BASE_RUNNER_SOURCE_SHA256"),
            (
                "multilingual scorer and live assertion",
                "SWIFT_SOURCE_SHA256",
            ),
            (
                "embedding recovery assertion",
                "RECOVERY_SOURCE_SHA256",
            ),
            (
                "multilingual semantic runner",
                "RECORDED_RUNNER_SOURCE_SHA256",
            ),
        ):
            with (
                self.subTest(label=label),
                patch.object(runner, constant, "0" * 64),
                self.assertRaises(runner.MatrixFailure),
            ):
                runner.assert_bound_sources()

    def test_expected_failure_log_is_exact_closed_and_nonretaining(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "swift-test.log"
            valid_log = self.expected_failure_log()
            log_path.write_text(valid_log, encoding="utf-8")
            result = runner.classify_expected_semantic_failure(log_path)
            self.assertIsNotNone(result)
            self.assertEqual(result["failureLocale"], "ko")
            self.assertEqual(
                result["failureScenarioOrdinalWithinLocale"],
                2,
            )
            self.assertIs(result["exactTestCaseExecuted"], True)

            task_set = self.task_set()
            task_id = task_set["scenarios"][5]["id"]
            mutations = {
                "missing started event": "\n".join(
                    valid_log.splitlines()[1:]
                ),
                "passed instead of failed": valid_log.replace(
                    "]' failed (",
                    "]' passed (",
                ),
                "multiple test events": (
                    valid_log
                    + "\n"
                    + valid_log.replace(
                        runner.LIVE_TEST_FILTER.rpartition(".")[2],
                        "testUnexpected",
                    )
                ),
                "other failure diagnostic": (
                    valid_log + "\ninvalidEmbeddingShape"
                ),
                "second error diagnostic": (
                    valid_log + "\nOther.swift:1: error: unrelated failure"
                ),
                "raw task id": valid_log + f"\n{task_id}",
                "multiple coordinates": (
                    valid_log
                    + '\npositiveMarginFailed(locale: "ko", '
                    "scenarioOrdinalWithinLocale: 2)"
                ),
                "unknown locale": self.expected_failure_log(locale="de"),
                "invalid ordinal": self.expected_failure_log(ordinal=5),
            }
            for label, mutation in mutations.items():
                with self.subTest(label=label):
                    log_path.write_text(mutation, encoding="utf-8")
                    self.assertIsNone(
                        runner.classify_expected_semantic_failure(
                            log_path
                        )
                    )

            log_path.write_bytes(
                b"x" * (runner.base.SWIFT_TEST_LOG_BYTE_LIMIT + 1)
            )
            self.assertIsNone(
                runner.classify_expected_semantic_failure(log_path)
            )

    def test_expected_semantic_failure_does_not_mask_cleanup_error(
        self,
    ) -> None:
        class FakeProcess:
            pid = 4242

            @staticmethod
            def poll() -> int:
                return 0

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_model(root / "source")
            candidate_root = root / "candidate"
            candidate_root.mkdir()
            task_set_path = candidate_root / "task-set.json"
            task_set_path.write_bytes(runner.recorded_task_set_bytes())
            initial_state = (("snapshot", 1, "0" * 64),)

            def fail_adapter(**kwargs: object) -> None:
                Path(kwargs["log_path"]).write_text(
                    self.expected_failure_log(),
                    encoding="utf-8",
                )
                raise runner.MatrixFailure("adapter failed")

            with (
                patch.object(
                    runner.base,
                    "start_live_fault_provider",
                    return_value=FakeProcess(),
                ),
                patch.object(
                    runner.base,
                    "run_fault_swift_test",
                    side_effect=fail_adapter,
                ),
                patch.object(
                    runner.base,
                    "stop_provider",
                    side_effect=runner.MatrixFailure("cleanup failed"),
                ),
                patch.object(
                    runner.base,
                    "process_group_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner.base,
                    "model_snapshot_state",
                    return_value=initial_state,
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "cleanup failed",
                ),
            ):
                runner.run_phase(
                    binary=root / "ollama",
                    extracted=root,
                    models_directory=root / "source",
                    candidate_root=candidate_root,
                    phase="semantic",
                    port=31343,
                    base_url="http://127.0.0.1:31343",
                    candidate=runner.base.EXACT_CANDIDATES[0],
                    selected=selected,
                    task_set_path=task_set_path,
                    initial_snapshot_state=initial_state,
                )

    def test_candidate_runs_semantic_then_fresh_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_model(root / "source")
            candidate_root = root / "candidate-root"
            candidate_root.mkdir()
            initial_state = tuple(
                (f"file-{index}", index, f"{index:064x}")
                for index in range(len(selected.blobs) + 1)
            )
            fixture_version = runner.recorded_fixture()["versions"][0]
            call_order: list[str] = []

            def extract_archive(
                command: list[str],
                **_kwargs: object,
            ) -> None:
                extracted = Path(command[-1])
                binary = extracted / "ollama"
                binary.write_bytes(b"binary")
                binary.chmod(0o755)

            def run_phase(**kwargs: object) -> dict[str, object]:
                phase = str(kwargs["phase"])
                call_order.append(phase)
                return json.loads(
                    json.dumps(fixture_version[phase])
                )

            with (
                patch.object(runner.base, "download_archive"),
                patch.object(
                    runner.base,
                    "run_checked",
                    side_effect=extract_archive,
                ),
                patch.object(
                    runner.base,
                    "create_model_snapshot",
                    return_value=initial_state,
                ),
                patch.object(
                    runner,
                    "create_task_set_copy",
                    return_value=candidate_root / "task-set.json",
                ),
                patch.object(
                    runner.base,
                    "reserve_unique_port",
                    return_value=31343,
                ),
                patch.object(
                    runner.base,
                    "endpoint_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner,
                    "run_phase",
                    side_effect=run_phase,
                ),
            ):
                result = runner.run_candidate(
                    runner.base.EXACT_CANDIDATES[0],
                    candidate_root,
                    selected=selected,
                )

            self.assertEqual(call_order, ["semantic", "recovery"])
            self.assertEqual(result, fixture_version)

    def test_cli_uses_the_selected_source_store(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.object(
                runner,
                "run_cli_matrix",
                return_value=runner.recorded_fixture(),
            ) as run_mock,
            patch("builtins.print"),
        ):
            source = Path(temporary_directory)
            self.assertEqual(
                runner.main(["--source-model-store", str(source)]),
                0,
            )
        run_mock.assert_called_once_with(source)


if __name__ == "__main__":
    unittest.main()
