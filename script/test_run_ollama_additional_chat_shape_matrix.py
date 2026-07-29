#!/usr/bin/env python3
"""Focused tests for the additional installed Ollama chat-shape matrix."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from script import run_ollama_additional_chat_shape_matrix as runner


base = runner.base


class AdditionalChatShapeMatrixTests(unittest.TestCase):
    def candidates(self) -> tuple[runner.CatalogCandidate, ...]:
        return (
            runner.CatalogCandidate(
                capabilities=("completion", "thinking", "tools"),
                digest="1" * 64,
                name="first-private-shape:latest",
                reported_size_bytes=9_639_236_355,
            ),
            runner.CatalogCandidate(
                capabilities=runner.RECORDED_TARGET_CAPABILITIES,
                digest=runner.RECORDED_TARGET_MANIFEST_DIGEST,
                name="recorded-private-shape:latest",
                reported_size_bytes=runner.RECORDED_MODEL_ARTIFACT_BYTES,
            ),
            runner.CatalogCandidate(
                capabilities=("completion", "thinking", "tools", "vision"),
                digest="3" * 64,
                name="third-private-shape:latest",
                reported_size_bytes=21_909_210_142,
            ),
            runner.CatalogCandidate(
                capabilities=("embedding",),
                digest="4" * 64,
                name="private-embedding-shape:latest",
                reported_size_bytes=621_875_917,
            ),
        )

    def blobs(
        self,
        store: Path,
        *,
        count: int = runner.RECORDED_BLOB_COUNT,
        total_bytes: int = runner.RECORDED_MODEL_ARTIFACT_BYTES,
    ) -> tuple[base.SnapshotBlob, ...]:
        if count < 1 or total_bytes < count:
            raise AssertionError("invalid synthetic snapshot shape")
        sizes = (total_bytes - count + 1, *(1 for _ in range(count - 1)))
        return tuple(
            base.SnapshotBlob(
                source_path=store / "blobs" / f"sha256-{index:064x}",
                relative_path=Path("blobs") / f"sha256-{index:064x}",
                size_bytes=size,
                sha256=f"{index:064x}",
            )
            for index, size in enumerate(sizes, start=1)
        )

    def selected(
        self,
        store: Path,
        *,
        manifest_bytes: int = runner.RECORDED_MANIFEST_BYTES,
        blob_count: int = runner.RECORDED_BLOB_COUNT,
        artifact_bytes: int = runner.RECORDED_MODEL_ARTIFACT_BYTES,
    ) -> base.SelectedLocalModel:
        target = self.candidates()[1]
        manifest_path = store / "manifests" / "recorded"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_bytes(b"x" * manifest_bytes)
        return base.SelectedLocalModel(
            provider_model_id=target.name,
            manifest_digest=target.digest,
            reported_size_bytes=target.reported_size_bytes,
            manifest_source_path=manifest_path,
            manifest_relative_path=Path("manifests/recorded"),
            manifest_size_bytes=manifest_bytes,
            blobs=self.blobs(
                store,
                count=blob_count,
                total_bytes=artifact_bytes,
            ),
            capabilities=target.capabilities,
        )

    def select_with_snapshot(
        self,
        store: Path,
        *,
        manifest_bytes: int = runner.RECORDED_MANIFEST_BYTES,
        blob_count: int = runner.RECORDED_BLOB_COUNT,
        artifact_bytes: int = runner.RECORDED_MODEL_ARTIFACT_BYTES,
    ) -> base.SelectedLocalModel:
        selected = self.selected(
            store,
            manifest_bytes=manifest_bytes,
            blob_count=blob_count,
            artifact_bytes=artifact_bytes,
        )
        with (
            patch.object(
                base,
                "find_manifest_by_digest",
                return_value=(
                    selected.manifest_source_path,
                    selected.manifest_relative_path,
                ),
            ),
            patch.object(base, "manifest_blobs", return_value=selected.blobs),
        ):
            return runner.select_recorded_model(
                store,
                candidates=self.candidates(),
                running_names=frozenset(),
            )

    def matrix_patches(
        self,
        *,
        selected: base.SelectedLocalModel,
        candidate_side_effect: object,
        version_side_effect: object = None,
    ):
        catalog = tuple(
            {
                "digest": candidate.digest,
                "name": candidate.name,
                "size": candidate.reported_size_bytes,
            }
            for candidate in self.candidates()
        )
        state = (("manifest", runner.RECORDED_MANIFEST_BYTES, "a" * 64),)
        versions = (
            (runner.RECORDED_SOURCE_VERSION,) * 2
            if version_side_effect is None
            else version_side_effect
        )
        return (
            patch.object(runner, "assert_bound_sources"),
            patch.object(
                base,
                "source_provider_version",
                side_effect=versions,
            ),
            patch.object(
                base,
                "source_catalog_rows",
                side_effect=(catalog, catalog),
            ),
            patch.object(
                base,
                "source_running_model_names",
                side_effect=(frozenset(), frozenset()),
            ),
            patch.object(
                runner,
                "catalog_candidates",
                side_effect=(self.candidates(), self.candidates()),
            ),
            patch.object(
                runner,
                "select_recorded_model",
                return_value=selected,
            ),
            patch.object(
                base,
                "expected_selected_source_state",
                return_value=state,
            ),
            patch.object(
                base,
                "selected_source_state",
                return_value=state,
            ),
            patch.object(
                base,
                "run_selected_model_backed_candidate",
                side_effect=candidate_side_effect,
            ),
        )

    def test_bound_sources_and_recorded_fixture_are_exact(self) -> None:
        runner.assert_bound_sources()
        fixture = runner.recorded_fixture()
        runner.validate_recorded_fixture(fixture)
        self.assertEqual(fixture["observationCount"], 4)
        self.assertEqual(fixture["profile"], "chat")
        self.assertEqual(
            fixture["selection"],
            {
                "completionCandidateCount": 3,
                "selectionOrdinal": 2,
                "targetCapabilityCount": 3,
                "targetInitiallyUnloaded": True,
                "targetVisionCapable": False,
            },
        )
        self.assertEqual(
            fixture["sourceBindings"]["runnerSourceSha256"],
            runner.RECORDED_RUNNER_SOURCE_SHA256,
        )

    def test_catalog_projection_queries_all_rows_and_sorts_by_size(self) -> None:
        rows = (
            {"digest": "b", "name": "large", "size": 20},
            {"digest": "a", "name": "small", "size": 10},
        )
        with patch.object(
            base,
            "model_capabilities",
            side_effect=(("completion",), ("embedding",)),
        ) as capabilities:
            candidates = runner.catalog_candidates(
                rows,
                base_url="http://127.0.0.1:11434",
            )
        self.assertEqual(
            tuple(candidate.name for candidate in candidates),
            ("small", "large"),
        )
        self.assertEqual(capabilities.call_count, 2)
        self.assertEqual(
            runner.capability_projection(candidates),
            (
                ("a", 10, ("embedding",)),
                ("b", 20, ("completion",)),
            ),
        )
        chat_only = runner.CatalogCandidate(
            capabilities=("chat",),
            digest="c",
            name="chat-only",
            reported_size_bytes=30,
        )
        self.assertEqual(
            runner.completion_candidates((chat_only,)),
            (),
        )

    def test_selector_chooses_the_exact_second_completion_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            selected = self.select_with_snapshot(Path(temporary_directory))
        self.assertEqual(
            selected.provider_model_id,
            self.candidates()[1].name,
        )
        self.assertEqual(len(selected.blobs), runner.RECORDED_BLOB_COUNT)
        self.assertEqual(
            selected.model_artifact_bytes,
            runner.RECORDED_MODEL_ARTIFACT_BYTES,
        )

    def test_selector_rejects_running_target_without_fallback(self) -> None:
        target = self.candidates()[1]
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.object(base, "find_manifest_by_digest") as manifest_lookup,
            self.assertRaisesRegex(
                runner.MatrixFailure,
                "already running",
            ),
        ):
            runner.select_recorded_model(
                Path(temporary_directory),
                candidates=self.candidates(),
                running_names=frozenset(
                    {base.canonical_model_name(target.name)}
                ),
            )
        manifest_lookup.assert_not_called()

    def test_selector_rejects_candidate_count_and_identity_drift(self) -> None:
        candidates = self.candidates()
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            self.assertRaisesRegex(
                runner.MatrixFailure,
                "catalog count differs",
            ),
        ):
            runner.select_recorded_model(
                Path(temporary_directory),
                candidates=candidates[:2],
                running_names=frozenset(),
            )

        identity_mutations = (
            replace(
                candidates[1],
                digest="d" * 64,
            ),
            replace(
                candidates[1],
                reported_size_bytes=runner.RECORDED_MODEL_ARTIFACT_BYTES + 1,
            ),
            replace(
                candidates[1],
                capabilities=("completion", "thinking"),
            ),
            replace(
                candidates[1],
                capabilities=("completion", "thinking", "vision"),
            ),
            replace(
                candidates[1],
                capabilities=("audio", "completion", "tools"),
            ),
        )
        for mutation in identity_mutations:
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary_directory,
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "target identity drifted",
                ),
            ):
                runner.select_recorded_model(
                    Path(temporary_directory),
                    candidates=(
                        candidates[0],
                        mutation,
                        candidates[2],
                        candidates[3],
                    ),
                    running_names=frozenset(),
                )

    def test_selector_rejects_manifest_and_blob_shape_drift(self) -> None:
        mutations = (
            {
                "manifest_bytes": runner.RECORDED_MANIFEST_BYTES - 1,
            },
            {
                "blob_count": runner.RECORDED_BLOB_COUNT - 1,
            },
            {
                "artifact_bytes": (
                    runner.RECORDED_MODEL_ARTIFACT_BYTES - 1
                ),
            },
        )
        for mutation in mutations:
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary_directory,
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "snapshot differs",
                ),
            ):
                self.select_with_snapshot(
                    Path(temporary_directory),
                    **mutation,
                )

    def test_fixture_schema_and_nonretention_are_closed(self) -> None:
        fixture = runner.recorded_fixture()
        mutated = json.loads(json.dumps(fixture))
        mutated["unexpected"] = True
        with self.assertRaises(runner.MatrixFailure):
            runner.validate_recorded_fixture(mutated)

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            selected = self.selected(store)
            runner.assert_result_nonretention(
                fixture,
                selected=selected,
                source_models_directory=store,
            )
            leaked = {**fixture, "leak": selected.provider_model_id}
            with self.assertRaisesRegex(
                runner.MatrixFailure,
                "retained non-evidence",
            ):
                runner.assert_result_nonretention(
                    leaked,
                    selected=selected,
                    source_models_directory=store,
                )

    def test_matrix_uses_exact_candidates_and_dedicated_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            selected = self.selected(store)
            expected_versions = {
                row["version"]: row
                for row in runner.recorded_fixture()["versions"]
            }
            observed: list[tuple[str, str, bool]] = []

            def run_candidate(
                candidate: dict[str, str],
                temporary_root: Path,
                *,
                selected: base.SelectedLocalModel,
                profile: base.ModelBackedProfile,
            ) -> dict[str, object]:
                observed.append(
                    (
                        candidate["version"],
                        profile.runner_id,
                        temporary_root.exists(),
                    )
                )
                self.assertEqual(
                    selected.provider_model_id,
                    self.candidates()[1].name,
                )
                return expected_versions[candidate["version"]]

            patches = self.matrix_patches(
                selected=selected,
                candidate_side_effect=run_candidate,
            )
            with (
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[4],
                patches[5],
                patches[6],
                patches[7],
                patches[8],
            ):
                result = runner.run_matrix(store)

        runner.validate_recorded_fixture(result)
        self.assertEqual(
            observed,
            [
                (
                    candidate["version"],
                    runner.FIXTURE_ID,
                    True,
                )
                for candidate in base.EXACT_CANDIDATES
            ],
        )

    def test_source_drift_overrides_candidate_failure_after_cleanup(self) -> None:
        captured_roots: list[Path] = []

        def fail_candidate(
            _candidate: dict[str, str],
            temporary_root: Path,
            **_kwargs: object,
        ) -> dict[str, object]:
            captured_roots.append(temporary_root)
            raise runner.MatrixFailure("injected candidate failure")

        def provider_version(_base_url: str) -> str:
            if not captured_roots:
                return runner.RECORDED_SOURCE_VERSION
            self.assertFalse(
                captured_roots[0].exists(),
                "source readback started before temporary cleanup",
            )
            return "0.32.5"

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            selected = self.selected(store)
            patches = self.matrix_patches(
                selected=selected,
                candidate_side_effect=fail_candidate,
                version_side_effect=provider_version,
            )
            with (
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[4],
                patches[5],
                patches[6],
                patches[7],
                patches[8],
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "observed source provider",
                ),
            ):
                runner.run_matrix(store)

        self.assertEqual(len(captured_roots), 1)

    def test_cleanup_failure_blocks_post_run_source_readback(self) -> None:
        class CleanupFailure:
            def __init__(self, root: Path) -> None:
                self.root = root

            def __enter__(self) -> str:
                self.root.mkdir()
                return str(self.root)

            def __exit__(
                self,
                _exception_type: object,
                _exception: object,
                _traceback: object,
            ) -> bool:
                self.root.rmdir()
                self.root.symlink_to(
                    self.root.parent / "missing-cleanup-target",
                    target_is_directory=True,
                )
                raise OSError("injected cleanup failure")

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            selected = self.selected(store)
            expected_versions = {
                row["version"]: row
                for row in runner.recorded_fixture()["versions"]
            }

            def run_candidate(
                candidate: dict[str, str],
                _temporary_root: Path,
                **_kwargs: object,
            ) -> dict[str, object]:
                return expected_versions[candidate["version"]]

            patches = self.matrix_patches(
                selected=selected,
                candidate_side_effect=run_candidate,
            )
            leaked_root = store / "leaked-temporary-root"
            with (
                patches[0],
                patches[1] as version_read,
                patches[2] as catalog_read,
                patches[3] as running_read,
                patches[4],
                patches[5],
                patches[6],
                patches[7] as source_state_read,
                patches[8],
                patch.object(
                    runner.tempfile,
                    "TemporaryDirectory",
                    return_value=CleanupFailure(leaked_root),
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "temporary cleanup failed",
                ),
            ):
                runner.run_matrix(store)

            self.assertFalse(leaked_root.exists())
            self.assertTrue(os.path.lexists(leaked_root))
            self.assertEqual(version_read.call_count, 1)
            self.assertEqual(catalog_read.call_count, 1)
            self.assertEqual(running_read.call_count, 1)
            source_state_read.assert_not_called()

    def test_cli_failure_does_not_retain_inner_diagnostics(self) -> None:
        with (
            patch.object(
                runner,
                "run_matrix",
                side_effect=runner.MatrixFailure(
                    "private model and path diagnostic"
                ),
            ),
            self.assertRaises(runner.MatrixFailure) as raised,
        ):
            runner.run_cli_matrix(Path("/private/model/store"))
        message = str(raised.exception)
        self.assertIn(runner.FIXTURE_ID, message)
        self.assertNotIn("private model", message)
        self.assertNotIn("/private/model/store", message)

    def test_top_level_cli_failure_is_one_line_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_store = Path(temporary_directory) / "private-missing-store"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(runner.__file__).resolve()),
                    "--source-model-store",
                    str(missing_store),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertNotIn(str(missing_store), completed.stderr)
        self.assertEqual(len(completed.stderr.rstrip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
