from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    from . import run_ollama_multilingual_semantic_matrix_v3 as runner
except ImportError:
    import run_ollama_multilingual_semantic_matrix_v3 as runner


class OllamaMultilingualSemanticFullMatrixV3Tests(unittest.TestCase):
    def passing_projection(self) -> dict[str, object]:
        return {
            "rankingFailures": [],
            "repeatabilityFailures": [],
            "schemaVersion": 1,
        }

    def failing_projection(self) -> dict[str, object]:
        return {
            "rankingFailures": [
                {
                    "failedBatches": [
                        {
                            "batchOrdinal": 1,
                            "comparisonFailureCount": 2,
                        },
                        {
                            "batchOrdinal": 2,
                            "comparisonFailureCount": 2,
                        },
                    ],
                    "locale": "ko",
                    "scenarioOrdinalWithinLocale": 2,
                }
            ],
            "repeatabilityFailures": [
                {
                    "inputOrdinalWithinLocale": 16,
                    "locale": "fr",
                }
            ],
            "schemaVersion": 1,
        }

    def swift_log(self, projection: dict[str, object]) -> str:
        suite = "OllamaBackendTests.OllamaEmbeddingMultilingualFullMatrixV3Tests"
        method = (
            "testLiveOllamaExactVersionInstalledEmbeddingMultilingual"
            "FullMatrixObservationV3"
        )
        marker = runner.DIAGNOSTIC_PREFIX + json.dumps(
            projection,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return "\n".join(
            (
                f"Test Case '-[{suite} {method}]' started.",
                marker,
                f"Test Case '-[{suite} {method}]' passed (0.100 seconds).",
                "",
            )
        )

    def selected_model(self) -> runner.base.SelectedLocalModel:
        profile = runner.base.EMBEDDING_MODEL_BACKED_PROFILE
        sizes = [profile.recorded_model_artifact_bytes, 0, 0, 0]
        blobs = tuple(
            runner.base.SnapshotBlob(
                source_path=Path(f"/source/{index}"),
                relative_path=Path(f"blobs/sha256-{index}"),
                size_bytes=size,
                sha256=f"{index}" * 64,
            )
            for index, size in enumerate(sizes)
        )
        return runner.base.SelectedLocalModel(
            provider_model_id="not-retained-model",
            manifest_digest="a" * 64,
            reported_size_bytes=profile.recorded_model_artifact_bytes,
            manifest_source_path=Path("/source/manifest"),
            manifest_relative_path=Path("manifests/example"),
            manifest_size_bytes=profile.recorded_manifest_bytes,
            blobs=blobs,
            capabilities=("embedding",),
        )

    def version_rows(
        self,
        projection: dict[str, object],
    ) -> list[dict[str, object]]:
        return [
            {
                "archiveSha256": candidate["archiveSha256"],
                "observation": deepcopy(projection),
                "recoveryPassed": True,
                "version": candidate["version"],
            }
            for candidate in runner.base.EXACT_CANDIDATES
        ]

    def test_projection_derives_pass_and_failure_counts(self) -> None:
        cases = (
            (self.passing_projection(), (True, 80, 80)),
            (self.failing_projection(), (False, 76, 79)),
        )
        for projection, expected in cases:
            with self.subTest(expected=expected):
                summary = runner.projection_summary(projection)
                self.assertEqual(
                    (
                        summary["qualityGatePassed"],
                        summary["rankingComparisonsPassed"],
                        summary["repeatabilityComparisonsPassed"],
                    ),
                    expected,
                )

    def test_projection_rejects_noncanonical_or_inexact_values(self) -> None:
        mutations = {
            "extra-key": lambda value: value.__setitem__("extra", 1),
            "bool-schema": lambda value: value.__setitem__(
                "schemaVersion", True
            ),
            "bool-batch": lambda value: value["rankingFailures"][0][
                "failedBatches"
            ][0].__setitem__("batchOrdinal", True),
            "float-count": lambda value: value["rankingFailures"][0][
                "failedBatches"
            ][0].__setitem__("comparisonFailureCount", 1.0),
            "reversed-batches": lambda value: value["rankingFailures"][0]
            .__setitem__(
                "failedBatches",
                list(
                    reversed(
                        value["rankingFailures"][0]["failedBatches"]
                    )
                ),
            ),
            "duplicate-ranking": lambda value: value[
                "rankingFailures"
            ].append(deepcopy(value["rankingFailures"][0])),
            "invalid-locale": lambda value: value["rankingFailures"][0]
            .__setitem__("locale", "de"),
            "duplicate-repeat": lambda value: value[
                "repeatabilityFailures"
            ].append(deepcopy(value["repeatabilityFailures"][0])),
            "invalid-input-ordinal": lambda value: value[
                "repeatabilityFailures"
            ][0].__setitem__("inputOrdinalWithinLocale", 17),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                projection = self.failing_projection()
                mutate(projection)
                with self.assertRaises(runner.MatrixFailure):
                    runner.validate_full_matrix_projection(projection)

    def test_parser_accepts_one_exact_passed_test_and_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory).resolve() / "adapter.log"
            projection = self.failing_projection()
            log_path.write_text(
                self.swift_log(projection),
                encoding="utf-8",
            )
            observed = runner.parse_full_matrix_observation(
                log_path,
                forbidden_tokens={"secret-input", "secret-model"},
            )
        self.assertEqual(observed, projection)

    def test_parser_rejects_marker_execution_and_retention_drift(self) -> None:
        mutations = {
            "missing-marker": lambda text: "\n".join(
                line
                for line in text.splitlines()
                if not line.startswith(runner.DIAGNOSTIC_PREFIX)
            ),
            "duplicate-marker": lambda text: (
                text
                + runner.DIAGNOSTIC_PREFIX
                + json.dumps(self.passing_projection())
                + "\n"
            ),
            "failed-test": lambda text: text.replace(
                "]' passed (", "]' failed ("
            ),
            "error-line": lambda text: text + "Source.swift:1: error: x\n",
            "retained-token": lambda text: text + "secret-input\n",
            "duplicate-json-key": lambda text: text.replace(
                '"schemaVersion":1',
                '"schemaVersion":1,"schemaVersion":1',
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                log_path = Path(directory).resolve() / "adapter.log"
                log_path.write_text(
                    mutate(self.swift_log(self.failing_projection())),
                    encoding="utf-8",
                )
                with self.assertRaises(runner.MatrixFailure):
                    runner.parse_full_matrix_observation(
                        log_path,
                        forbidden_tokens={"secret-input"},
                    )

    def test_cleanup_and_fallback_precede_adapter_error(self) -> None:
        class FakeProcess:
            pid = 4242

            @staticmethod
            def poll() -> None:
                return None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate_root = root / "candidate"
            candidate_root.mkdir()
            task_path = candidate_root / runner.v2.TASK_SET_COPY_NAME
            task_path.write_bytes(runner.v2.recorded_task_set_bytes())
            snapshot = (("snapshot", 1, "0" * 64),)
            fallback = Mock()
            with (
                patch.object(runner, "assert_bound_sources"),
                patch.object(
                    runner,
                    "semantic_adapter_environment",
                    return_value={},
                ),
                patch.object(
                    runner.base,
                    "start_live_fault_provider",
                    return_value=FakeProcess(),
                ),
                patch.object(
                    runner.base,
                    "run_fault_swift_test",
                    side_effect=runner.MatrixFailure("adapter failed"),
                ),
                patch.object(
                    runner.base,
                    "stop_provider",
                    side_effect=runner.MatrixFailure("cleanup failed"),
                ),
                patch.object(
                    runner.base,
                    "process_group_is_available",
                    return_value=True,
                ),
                patch.object(
                    runner.base,
                    "kill_process_group_and_wait",
                    side_effect=fallback,
                ),
                patch.object(
                    runner.base,
                    "model_snapshot_state",
                    return_value=snapshot,
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "cleanup failed",
                ),
            ):
                runner.run_phase_v3(
                    binary=root / "ollama",
                    extracted=root,
                    models_directory=root / "models",
                    candidate_root=candidate_root,
                    phase="semantic",
                    port=31343,
                    base_url="http://127.0.0.1:31343",
                    candidate=runner.base.EXACT_CANDIDATES[0],
                    selected=self.selected_model(),
                    task_set_path=task_path,
                    initial_snapshot_state=snapshot,
                )
            fallback.assert_called_once()

    def test_boundary_error_precedes_adapter_error(self) -> None:
        class FakeProcess:
            pid = 4242

            @staticmethod
            def poll() -> int:
                return 0

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            task_path = root / runner.v2.TASK_SET_COPY_NAME
            task_path.write_bytes(runner.v2.recorded_task_set_bytes())
            with (
                patch.object(runner, "assert_bound_sources"),
                patch.object(
                    runner,
                    "semantic_adapter_environment",
                    return_value={},
                ),
                patch.object(
                    runner.base,
                    "start_live_fault_provider",
                    return_value=FakeProcess(),
                ),
                patch.object(
                    runner.base,
                    "run_fault_swift_test",
                    side_effect=runner.MatrixFailure("adapter failed"),
                ),
                patch.object(runner.base, "stop_provider"),
                patch.object(runner.base, "ensure_fault_provider_stopped"),
                patch.object(
                    runner.base,
                    "model_snapshot_state",
                    return_value=(("changed", 2, "1" * 64),),
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "isolated snapshot changed",
                ),
            ):
                runner.run_phase_v3(
                    binary=root / "ollama",
                    extracted=root,
                    models_directory=root / "models",
                    candidate_root=root,
                    phase="semantic",
                    port=31343,
                    base_url="http://127.0.0.1:31343",
                    candidate=runner.base.EXACT_CANDIDATES[0],
                    selected=self.selected_model(),
                    task_set_path=task_path,
                    initial_snapshot_state=(("initial", 1, "0" * 64),),
                )

    def test_candidate_runs_semantic_then_fresh_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            selected = self.selected_model()
            snapshot = tuple(
                (f"file-{index}", index, f"{index:064x}")
                for index in range(len(selected.blobs) + 1)
            )
            call_order: list[str] = []

            def extract(command: list[str], **_kwargs: object) -> None:
                binary = Path(command[-1]) / "ollama"
                binary.write_bytes(b"binary")
                binary.chmod(0o755)

            def run_phase(**kwargs: object) -> dict[str, object] | None:
                phase = str(kwargs["phase"])
                call_order.append(phase)
                return (
                    deepcopy(self.failing_projection())
                    if phase == "semantic"
                    else None
                )

            with (
                patch.object(runner.base, "download_archive"),
                patch.object(runner.base, "run_checked", side_effect=extract),
                patch.object(
                    runner.base,
                    "create_model_snapshot",
                    return_value=snapshot,
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
                    "run_phase_v3",
                    side_effect=run_phase,
                ),
            ):
                result = runner.run_candidate_v3(
                    runner.base.EXACT_CANDIDATES[0],
                    root,
                    selected=selected,
                )

        self.assertEqual(call_order, ["semantic", "recovery"])
        self.assertFalse(
            runner.projection_summary(result["observation"])[
                "qualityGatePassed"
            ]
        )
        self.assertTrue(result["recoveryPassed"])

    def test_matrix_preserves_exact_candidate_order(self) -> None:
        selected = self.selected_model()
        candidate_order: list[str] = []
        profile = runner.base.EMBEDDING_MODEL_BACKED_PROFILE
        catalog = tuple(
            {"name": f"model-{index}"}
            for index in range(profile.recorded_catalog_model_count)
        )
        source_state = (("selected", 1, "0" * 64),)

        def run_candidate(
            candidate: dict[str, str],
            _root: Path,
            *,
            selected: runner.base.SelectedLocalModel,
        ) -> dict[str, object]:
            del selected
            candidate_order.append(candidate["version"])
            return {
                "archiveSha256": candidate["archiveSha256"],
                "observation": deepcopy(self.failing_projection()),
                "recoveryPassed": True,
                "version": candidate["version"],
            }

        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory).resolve()
            with (
                patch.object(runner, "assert_bound_sources"),
                patch.object(
                    runner.base,
                    "source_provider_version",
                    return_value=runner.SOURCE_PROVIDER_VERSION,
                ),
                patch.object(
                    runner.base,
                    "source_catalog_rows",
                    return_value=catalog,
                ),
                patch.object(
                    runner.base,
                    "source_running_model_names",
                    return_value=(),
                ),
                patch.object(
                    runner.base,
                    "select_source_model",
                    return_value=selected,
                ),
                patch.object(
                    runner.base,
                    "expected_selected_source_state",
                    return_value=source_state,
                ),
                patch.object(
                    runner.base,
                    "selected_source_state",
                    return_value=source_state,
                ),
                patch.object(
                    runner,
                    "run_candidate_v3",
                    side_effect=run_candidate,
                ),
            ):
                result = runner.run_matrix(source_root)

        expected = [
            candidate["version"]
            for candidate in runner.base.EXACT_CANDIDATES
        ]
        self.assertEqual(candidate_order, expected)
        self.assertEqual(
            [row["version"] for row in result["versions"]],
            expected,
        )
        self.assertFalse(result["qualityGatePassed"])

    def test_source_drift_precedes_candidate_error(self) -> None:
        selected = self.selected_model()
        profile = runner.base.EMBEDDING_MODEL_BACKED_PROFILE
        catalog_before = tuple(
            {"name": f"model-{index}"}
            for index in range(profile.recorded_catalog_model_count)
        )
        catalog_reads = [catalog_before, ({"name": "changed"},)]
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory).resolve()
            with (
                patch.object(runner, "assert_bound_sources"),
                patch.object(
                    runner.base,
                    "source_provider_version",
                    return_value=runner.SOURCE_PROVIDER_VERSION,
                ),
                patch.object(
                    runner.base,
                    "source_catalog_rows",
                    side_effect=catalog_reads,
                ),
                patch.object(
                    runner.base,
                    "source_running_model_names",
                    return_value=(),
                ),
                patch.object(
                    runner.base,
                    "select_source_model",
                    return_value=selected,
                ),
                patch.object(
                    runner.base,
                    "expected_selected_source_state",
                    return_value=(),
                ),
                patch.object(
                    runner.base,
                    "selected_source_state",
                    return_value=(),
                ),
                patch.object(
                    runner,
                    "run_candidate_v3",
                    side_effect=runner.MatrixFailure("candidate failed"),
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "source state changed",
                ),
            ):
                runner.run_matrix(source_root)

    def test_result_schema_derives_quality_and_binds_v2(self) -> None:
        for projection in (
            self.passing_projection(),
            self.failing_projection(),
        ):
            expected = not (
                projection["rankingFailures"]
                or projection["repeatabilityFailures"]
            )
            result = runner.result_for_observation(
                source_version=runner.SOURCE_PROVIDER_VERSION,
                versions=self.version_rows(projection),
            )
            runner.validate_result_v3(result)
            self.assertIs(result["qualityGatePassed"], expected)
            with self.assertRaises(runner.MatrixFailure):
                runner.v2.validate_recorded_fixture(result)

    def test_bound_sources_and_frozen_v2_task_remain_exact(self) -> None:
        runner.assert_bound_sources()
        self.assertEqual(
            runner.hashlib.sha256(
                runner.v2.recorded_task_set_bytes()
            ).hexdigest(),
            runner.v2.TASK_SET_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
