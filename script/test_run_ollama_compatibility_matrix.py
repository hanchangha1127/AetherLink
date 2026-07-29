#!/usr/bin/env python3
"""Focused tests for the bounded Ollama compatibility runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import ANY, patch

from script import run_ollama_compatibility_matrix as runner


class OllamaCompatibilityMatrixTests(unittest.TestCase):
    def write_model(
        self,
        store: Path,
        *,
        model_path: str,
        blob_contents: tuple[bytes, ...],
    ) -> tuple[str, int]:
        descriptors: list[dict[str, object]] = []
        for content in blob_contents:
            digest = hashlib.sha256(content).hexdigest()
            blob_path = store / "blobs" / f"sha256-{digest}"
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            descriptors.append(
                {
                    "digest": f"sha256:{digest}",
                    "size": len(content),
                }
            )

        manifest = {
            "config": descriptors[0],
            "layers": descriptors[1:],
            "schemaVersion": 2,
        }
        manifest_path = store / "manifests" / model_path
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return runner.file_sha256(manifest_path), sum(map(len, blob_contents))

    def selected_model(
        self,
        store: Path,
        *,
        model_name: str = "private-model:latest",
    ) -> runner.SelectedLocalModel:
        digest, size = self.write_model(
            store,
            model_path="registry.example/private/model/latest",
            blob_contents=(b"config", b"weights"),
        )
        with (
            patch.object(runner, "source_running_model_names", return_value=frozenset()),
            patch.object(
                runner,
                "source_catalog_rows",
                return_value=(
                    {
                        "digest": digest,
                        "name": model_name,
                        "size": size,
                    },
                ),
            ),
            patch.object(
                runner,
                "model_capabilities",
                return_value=("completion", "tools"),
            ),
        ):
            return runner.select_source_chat_model(store)

    def selected_embedding_model(
        self,
        store: Path,
        *,
        model_name: str = "private-embedding-model:latest",
    ) -> runner.SelectedLocalModel:
        digest, size = self.write_model(
            store,
            model_path="registry.example/private/embedding/latest",
            blob_contents=(b"embedding-config", b"embedding-weights"),
        )
        with (
            patch.object(
                runner,
                "source_running_model_names",
                return_value=frozenset(),
            ),
            patch.object(
                runner,
                "source_catalog_rows",
                return_value=(
                    {
                        "digest": digest,
                        "name": model_name,
                        "size": size,
                    },
                ),
            ),
            patch.object(
                runner,
                "model_capabilities",
                return_value=("embedding",),
            ),
        ):
            return runner.select_source_embedding_model(store)

    def selected_vision_model(
        self,
        store: Path,
        *,
        model_name: str = "private-vision-model:latest",
    ) -> runner.SelectedLocalModel:
        digest, size = self.write_model(
            store,
            model_path="registry.example/private/vision/latest",
            blob_contents=(b"vision-config", b"vision-weights"),
        )
        with (
            patch.object(
                runner,
                "source_running_model_names",
                return_value=frozenset(),
            ),
            patch.object(
                runner,
                "source_catalog_rows",
                return_value=(
                    {
                        "digest": digest,
                        "name": model_name,
                        "size": size,
                    },
                ),
            ),
            patch.object(
                runner,
                "model_capabilities",
                return_value=("completion", "vision"),
            ),
        ):
            return runner.select_source_vision_model(store)

    def profile_for_selected(
        self,
        selected: runner.SelectedLocalModel,
        *,
        temporary_prefix: str,
    ) -> runner.ModelBackedProfile:
        return replace(
            runner.CHAT_MODEL_BACKED_PROFILE,
            recorded_catalog_model_count=1,
            recorded_blob_count=len(selected.blobs),
            recorded_manifest_bytes=selected.manifest_size_bytes,
            recorded_model_artifact_bytes=selected.model_artifact_bytes,
            temporary_prefix=temporary_prefix,
        )

    def duration_versions(self) -> list[dict[str, object]]:
        phase = {
            "adapterMs": 2,
            "phaseTotalMs": 5,
            "providerReadyMs": 1,
            "stopMs": 1,
        }
        return [
            {
                "coldStart": dict(phase),
                "restart": dict(phase),
                "version": candidate["version"],
            }
            for candidate in runner.EXACT_CANDIDATES
        ]

    def run_injected_matrix_failure(
        self,
        store: Path,
        selected: runner.SelectedLocalModel,
        *,
        version_after: str = "0.32.4",
        catalog_after: tuple[dict[str, object], ...] | None = None,
        running_after: frozenset[str] | None = None,
        mutate_source: Callable[[], None] | None = None,
    ) -> tuple[runner.MatrixFailure, tuple[Path, ...], tuple[int, int, int]]:
        catalog_before = (
            {
                "digest": selected.manifest_digest,
                "name": selected.provider_model_id,
                "size": selected.model_artifact_bytes,
            },
        )
        running_before: frozenset[str] = frozenset()
        captured_roots: list[Path] = []
        profile = self.profile_for_selected(
            selected,
            temporary_prefix=(
                f"aetherlink-ollama-failure-test-{os.getpid()}-"
            ),
        )

        def fail_candidate(
            _candidate: dict[str, str],
            temporary_root: Path,
            **_kwargs: object,
        ) -> dict[str, object]:
            captured_roots.append(temporary_root)
            if mutate_source is not None:
                mutate_source()
            raise runner.MatrixFailure("injected candidate failure")

        def provider_version(_base_url: str) -> str:
            if not captured_roots:
                return "0.32.4"
            self.assertFalse(
                captured_roots[0].exists(),
                "post-failure source readback started before temp cleanup",
            )
            return version_after

        with (
            patch.object(
                runner,
                "source_provider_version",
                side_effect=provider_version,
            ) as version_mock,
            patch.object(
                runner,
                "source_catalog_rows",
                side_effect=(
                    catalog_before,
                    catalog_before if catalog_after is None else catalog_after,
                ),
            ) as catalog_mock,
            patch.object(
                runner,
                "source_running_model_names",
                side_effect=(
                    running_before,
                    running_before if running_after is None else running_after,
                ),
            ) as running_mock,
            patch.object(
                runner,
                "select_source_model",
                return_value=selected,
            ),
            patch.object(
                runner,
                "run_selected_model_backed_candidate",
                side_effect=fail_candidate,
            ),
            self.assertRaises(runner.MatrixFailure) as raised,
        ):
            runner.run_selected_model_backed_matrix(
                store,
                profile=profile,
            )

        return (
            raised.exception,
            tuple(captured_roots),
            (
                version_mock.call_count,
                catalog_mock.call_count,
                running_mock.call_count,
            ),
        )

    def test_strict_json_rejects_duplicate_keys(self) -> None:
        with self.assertRaises(runner.MatrixFailure):
            runner.strict_json_loads(
                b'{"models":[],"models":[]}',
                label="catalog",
            )

    def test_exact_integer_rejects_boolean_and_float(self) -> None:
        for value in (True, False, 1.0):
            with self.subTest(value=value):
                with self.assertRaises(runner.MatrixFailure):
                    runner.exact_int(value, label="count")
        self.assertEqual(runner.exact_int(1, label="count", minimum=1), 1)

    def test_ready_response_after_absolute_deadline_is_rejected(self) -> None:
        with (
            patch.object(
                runner.time,
                "monotonic_ns",
                side_effect=(19_750_000_000, 20_010_000_000),
            ),
            patch.object(
                runner,
                "fetch_version",
                return_value="0.32.5",
            ) as fetch_mock,
            self.assertRaisesRegex(
                runner.MatrixFailure,
                "provider became ready after the absolute deadline",
            ),
        ):
            runner.wait_until_ready(
                "http://127.0.0.1:31337",
                "0.32.5",
                deadline_ns=20_000_000_000,
            )

        self.assertEqual(fetch_mock.call_count, 1)
        self.assertAlmostEqual(
            fetch_mock.call_args.kwargs["timeout"],
            0.25,
        )

    def test_stop_endpoint_probe_shares_absolute_deadline(self) -> None:
        class FakeProcess:
            def __init__(self) -> None:
                self.wait_timeouts: list[float] = []

            def poll(self) -> None:
                return None

            def terminate(self) -> None:
                pass

            def wait(self, timeout: float) -> int:
                self.wait_timeouts.append(timeout)
                return 0

            def kill(self) -> None:
                raise AssertionError("graceful stop unexpectedly used kill")

        process = FakeProcess()
        with (
            patch.object(
                runner.time,
                "monotonic_ns",
                side_effect=(
                    0,
                    1_000_000_000,
                    9_750_000_000,
                    10_010_000_000,
                ),
            ),
            patch.object(
                runner,
                "endpoint_is_available",
                return_value=False,
            ) as endpoint_mock,
            self.assertRaisesRegex(
                runner.MatrixFailure,
                "provider stop exceeded the absolute deadline",
            ),
        ):
            runner.stop_provider(
                process,
                "http://127.0.0.1:31338",
            )

        self.assertEqual(process.wait_timeouts, [7.0])
        self.assertAlmostEqual(
            endpoint_mock.call_args.kwargs["timeout"],
            0.25,
        )

    def test_stop_force_kill_uses_only_remaining_sub_budget(self) -> None:
        class FakeProcess:
            def __init__(self) -> None:
                self.wait_timeouts: list[float] = []
                self.kill_count = 0

            def poll(self) -> None:
                return None

            def terminate(self) -> None:
                pass

            def wait(self, timeout: float) -> int:
                self.wait_timeouts.append(timeout)
                if len(self.wait_timeouts) == 1:
                    raise subprocess.TimeoutExpired("ollama", timeout)
                return 0

            def kill(self) -> None:
                self.kill_count += 1

        process = FakeProcess()
        with (
            patch.object(
                runner.time,
                "monotonic_ns",
                side_effect=(0, 0, 8_250_000_000, 8_500_000_000),
            ),
            patch.object(runner, "endpoint_is_available") as endpoint_mock,
            self.assertRaisesRegex(
                runner.MatrixFailure,
                "provider required forced termination",
            ),
        ):
            runner.stop_provider(
                process,
                "http://127.0.0.1:31339",
            )

        self.assertEqual(process.wait_timeouts, [8.0, 1.75])
        self.assertEqual(process.kill_count, 1)
        endpoint_mock.assert_not_called()

    def test_first_delta_marker_requires_exact_bounded_empty_file(self) -> None:
        class FakeProcess:
            def __init__(
                self,
                process_id: int,
                return_code: int | None = None,
            ) -> None:
                self.pid = process_id
                self.return_code = return_code

            def poll(self) -> int | None:
                return self.return_code

            def wait(self, timeout: float) -> int:
                self.return_code = -9
                return self.return_code

        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "first-provider-delta"
            provider = FakeProcess(424_240)
            adapter = FakeProcess(424_241)

            def create_marker(_seconds: float) -> None:
                marker.write_bytes(b"")

            with (
                patch.object(
                    runner.time,
                    "monotonic_ns",
                    return_value=0,
                ),
                patch.object(
                    runner.time,
                    "sleep",
                    side_effect=create_marker,
                ) as sleep_mock,
                patch.object(
                    runner,
                    "process_group_is_available",
                    return_value=True,
                ),
            ):
                runner.wait_for_first_delta_marker(
                    marker,
                    provider_process=provider,
                    adapter_process=adapter,
                    deadline_ns=1,
                )
            sleep_mock.assert_called_once()

            marker.write_bytes(b"not-empty")
            with self.assertRaisesRegex(
                runner.MatrixFailure,
                "exact empty-file shape",
            ):
                runner.wait_for_first_delta_marker(
                    marker,
                    provider_process=provider,
                    adapter_process=adapter,
                    deadline_ns=1,
                )

            marker.write_bytes(b"")
            provider.return_code = -9
            with (
                patch.object(
                    runner,
                    "process_group_is_available",
                    return_value=True,
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "provider exited before the runner injected",
                ),
            ):
                runner.wait_for_first_delta_marker(
                    marker,
                    provider_process=provider,
                    adapter_process=adapter,
                    deadline_ns=1,
                )

            marker.unlink()
            provider.return_code = None
            adapter.return_code = 1
            with self.assertRaisesRegex(
                runner.MatrixFailure,
                "adapter fault probe exited",
            ):
                runner.wait_for_first_delta_marker(
                    marker,
                    provider_process=provider,
                    adapter_process=adapter,
                    deadline_ns=1,
                )

            adapter.return_code = None
            with patch.object(
                runner.os,
                "killpg",
                side_effect=PermissionError(),
            ):
                self.assertTrue(
                    runner.process_group_is_available(provider.pid)
                )

            with (
                patch.object(
                    runner,
                    "process_group_is_available",
                    return_value=True,
                ),
                patch.object(
                    runner.os,
                    "killpg",
                    side_effect=ProcessLookupError(),
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "exited before the injected signal",
                ),
            ):
                runner.inject_process_group_sigkill(
                    provider,
                    label="provider",
                )

            class NaturalExitProcess(FakeProcess):
                def wait(self, timeout: float) -> int:
                    self.return_code = 0
                    return 0

            natural_exit = NaturalExitProcess(424_242)
            with (
                patch.object(
                    runner,
                    "process_group_is_available",
                    return_value=True,
                ),
                patch.object(runner.os, "killpg"),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "was not terminated by the injected signal",
                ),
            ):
                runner.inject_process_group_sigkill(
                    natural_exit,
                    label="provider",
                )

            injected_exit = FakeProcess(424_243)
            with (
                patch.object(
                    runner,
                    "process_group_is_available",
                    return_value=True,
                ),
                patch.object(runner.os, "killpg"),
                patch.object(
                    runner,
                    "wait_for_process_group_exit",
                ) as group_exit_mock,
            ):
                runner.inject_process_group_sigkill(
                    injected_exit,
                    label="provider",
                )
            group_exit_mock.assert_called_once()

            with (
                patch.object(
                    runner.time,
                    "monotonic_ns",
                    return_value=2,
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "first-delta marker was not observed",
                ),
            ):
                runner.wait_for_first_delta_marker(
                    marker,
                    provider_process=provider,
                    adapter_process=adapter,
                    deadline_ns=1,
                )

    def test_fault_swift_test_reaps_descendants_on_all_exit_paths(self) -> None:
        class FakeProcess:
            pid = 424_250

            def __init__(self, *, timeout: bool) -> None:
                self.timeout = timeout
                self.return_code: int | None = None

            def wait(self, timeout: float) -> int:
                if self.timeout:
                    raise subprocess.TimeoutExpired("swift", timeout)
                self.return_code = 0
                return 0

            def poll(self) -> int | None:
                return self.return_code

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for label, timeout, group_wait_error in (
                ("timeout", True, None),
                (
                    "descendant",
                    False,
                    runner.MatrixFailure(
                        "runner-owned process group remained after the deadline"
                    ),
                ),
            ):
                with self.subTest(label=label):
                    fake_process = FakeProcess(timeout=timeout)
                    with (
                        patch.object(
                            runner.subprocess,
                            "Popen",
                            return_value=fake_process,
                        ),
                        patch.object(
                            runner,
                            "wait_for_process_group_exit",
                            side_effect=group_wait_error,
                        ),
                        patch.object(
                            runner,
                            "process_group_is_available",
                            return_value=True,
                        ),
                        patch.object(
                            runner,
                            "kill_process_group_and_wait",
                        ) as kill_mock,
                        self.assertRaises(runner.MatrixFailure),
                    ):
                        runner.run_fault_swift_test(
                            environment={},
                            test_filter="test",
                            log_path=root / f"{label}.log",
                            label=f"{label} adapter",
                            timeout_seconds=1,
                        )
                    kill_mock.assert_called_once_with(
                        fake_process,
                        label=f"{label} adapter",
                    )

    def test_exact_swift_test_execution_requires_one_matching_pass(
        self,
    ) -> None:
        def event(
            suite: str,
            method: str,
            status: str,
        ) -> str:
            suffix = (
                "started."
                if status == "started"
                else "passed (0.001 seconds)."
            )
            return (
                "Test Case '-[OllamaBackendTests."
                f"{suite} {method}]' {suffix}"
            )

        expected_suite = "OllamaBackendTests"
        expected_method = "testExpected"
        test_filter = f"{expected_suite}.{expected_method}"
        valid_lines = (
            event(expected_suite, expected_method, "started"),
            event(expected_suite, expected_method, "passed"),
        )
        mutations = {
            "zero": ("warning: No matching test cases were run",),
            "wrong method": (
                event(expected_suite, "testOther", "started"),
                event(expected_suite, "testOther", "passed"),
            ),
            "multiple": (
                *valid_lines,
                event(expected_suite, "testOther", "started"),
                event(expected_suite, "testOther", "passed"),
            ),
            "not passed": (
                event(expected_suite, expected_method, "started"),
            ),
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "swift-test.log"
            log_path.write_text("\n".join(valid_lines), encoding="utf-8")
            runner.assert_exact_swift_test_execution(
                log_path=log_path,
                test_filter=test_filter,
                label="adapter",
            )

            for label, lines in mutations.items():
                with self.subTest(label=label):
                    log_path.write_text("\n".join(lines), encoding="utf-8")
                    with self.assertRaisesRegex(
                        runner.MatrixFailure,
                        "did not execute exactly one matching test case",
                    ):
                        runner.assert_exact_swift_test_execution(
                            log_path=log_path,
                            test_filter=test_filter,
                            label="adapter",
                        )

    def test_midstream_fault_requires_signal_and_adapter_group_readback(
        self,
    ) -> None:
        class FakeProcess:
            def __init__(self, process_id: int) -> None:
                self.pid = process_id
                self.return_code: int | None = None

            def poll(self) -> int | None:
                return self.return_code

            def wait(self, timeout: float) -> int:
                self.return_code = 0
                return 0

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            models_directory = root / "snapshot"
            models_directory.mkdir()
            selected = self.selected_model(root / "source")
            provider = FakeProcess(424_260)
            adapter = FakeProcess(424_261)

            with (
                patch.object(
                    runner.subprocess,
                    "Popen",
                    return_value=adapter,
                ),
                patch.object(
                    runner,
                    "wait_for_first_delta_marker",
                ),
                patch.object(
                    runner,
                    "inject_process_group_sigkill",
                ) as inject_mock,
                patch.object(
                    runner,
                    "wait_for_process_group_exit",
                ) as group_exit_mock,
                patch.object(
                    runner,
                    "process_group_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner,
                    "endpoint_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner,
                    "kill_process_group_and_wait",
                ) as cleanup_mock,
            ):
                runner.run_provider_exit_after_first_delta_fault(
                    provider_process=provider,
                    base_url="http://127.0.0.1:31343",
                    candidate=runner.EXACT_CANDIDATES[0],
                    models_directory=models_directory,
                    candidate_root=root,
                    selected=selected,
                )

            inject_mock.assert_called_once_with(
                provider,
                label="fault-injection provider",
            )
            self.assertEqual(
                group_exit_mock.call_args.args,
                (adapter.pid,),
            )
            cleanup_mock.assert_not_called()

    def test_duration_rounding_uses_exact_ceiling_milliseconds(self) -> None:
        cases = (
            (0, 0, 0),
            (0, 1, 1),
            (0, 1_000_000, 1),
            (0, 1_000_001, 2),
        )
        for start_ns, end_ns, expected_ms in cases:
            with self.subTest(start_ns=start_ns, end_ns=end_ns):
                self.assertEqual(
                    runner.elapsed_milliseconds_ceil(start_ns, end_ns),
                    expected_ms,
                )

    def test_duration_phase_accepts_exact_deadlines(self) -> None:
        result = runner.duration_phase_result(
            phase_started_ns=0,
            ready_finished_ns=runner.START_DEADLINE_NS,
            adapter_started_ns=runner.START_DEADLINE_NS,
            adapter_finished_ns=(
                runner.START_DEADLINE_NS
                + runner.COMMAND_DEADLINE_SECONDS
                * runner.NANOSECONDS_PER_SECOND
            ),
            stop_started_ns=(
                runner.START_DEADLINE_NS
                + runner.COMMAND_DEADLINE_SECONDS
                * runner.NANOSECONDS_PER_SECOND
            ),
            stop_finished_ns=(
                runner.START_DEADLINE_NS
                + runner.COMMAND_DEADLINE_SECONDS
                * runner.NANOSECONDS_PER_SECOND
                + runner.STOP_DEADLINE_NS
            ),
            phase_finished_ns=(
                runner.START_DEADLINE_NS
                + runner.COMMAND_DEADLINE_SECONDS
                * runner.NANOSECONDS_PER_SECOND
                + runner.STOP_DEADLINE_NS
                + 1
            ),
        )

        self.assertEqual(result["providerReadyMs"], 20_000)
        self.assertEqual(result["adapterMs"], 300_000)
        self.assertEqual(result["stopMs"], 10_000)
        self.assertEqual(result["phaseTotalMs"], 330_001)

    def test_duration_phase_rejects_each_deadline_plus_one_nanosecond(
        self,
    ) -> None:
        cases = (
            {
                "label": "provider ready",
                "ready_finished_ns": runner.START_DEADLINE_NS + 1,
                "adapter_finished_ns": runner.START_DEADLINE_NS + 1,
                "stop_started_ns": runner.START_DEADLINE_NS + 1,
                "stop_finished_ns": runner.START_DEADLINE_NS + 1,
                "phase_finished_ns": runner.START_DEADLINE_NS + 1,
            },
            {
                "label": "adapter",
                "ready_finished_ns": 0,
                "adapter_finished_ns": (
                    runner.COMMAND_DEADLINE_SECONDS
                    * runner.NANOSECONDS_PER_SECOND
                    + 1
                ),
                "stop_started_ns": (
                    runner.COMMAND_DEADLINE_SECONDS
                    * runner.NANOSECONDS_PER_SECOND
                    + 1
                ),
                "stop_finished_ns": (
                    runner.COMMAND_DEADLINE_SECONDS
                    * runner.NANOSECONDS_PER_SECOND
                    + 1
                ),
                "phase_finished_ns": (
                    runner.COMMAND_DEADLINE_SECONDS
                    * runner.NANOSECONDS_PER_SECOND
                    + 1
                ),
            },
            {
                "label": "stop",
                "ready_finished_ns": 0,
                "adapter_finished_ns": 0,
                "stop_started_ns": 0,
                "stop_finished_ns": runner.STOP_DEADLINE_NS + 1,
                "phase_finished_ns": runner.STOP_DEADLINE_NS + 1,
            },
        )
        for case in cases:
            with (
                self.subTest(label=case["label"]),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    f"{case['label']} duration exceeded the deadline",
                ),
            ):
                runner.duration_phase_result(
                    phase_started_ns=0,
                    ready_finished_ns=case["ready_finished_ns"],
                    adapter_started_ns=case["ready_finished_ns"],
                    adapter_finished_ns=case["adapter_finished_ns"],
                    stop_started_ns=case["stop_started_ns"],
                    stop_finished_ns=case["stop_finished_ns"],
                    phase_finished_ns=case["phase_finished_ns"],
                )

    def test_duration_evidence_rejects_type_and_shape_mutations(self) -> None:
        valid = runner.duration_evidence_result(self.duration_versions())

        def mutated(path: tuple[object, ...], replacement: object) -> object:
            value = json.loads(json.dumps(valid))
            target = value
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = replacement
            return value

        cases = (
            (
                "boolean",
                mutated(
                    ("versions", 0, "coldStart", "providerReadyMs"),
                    True,
                ),
            ),
            (
                "float",
                mutated(
                    ("versions", 0, "coldStart", "adapterMs"),
                    1.0,
                ),
            ),
            (
                "negative",
                mutated(
                    ("versions", 0, "coldStart", "stopMs"),
                    -1,
                ),
            ),
            (
                "wrong version order",
                mutated(("versions", 0, "version"), "0.32.4"),
            ),
        )
        for label, value in cases:
            with (
                self.subTest(label=label),
                self.assertRaises(runner.MatrixFailure),
            ):
                runner.validate_duration_evidence(value)

        extra_key = json.loads(json.dumps(valid))
        extra_key["versions"][0]["coldStart"]["unexpected"] = 0
        with self.assertRaises(runner.MatrixFailure):
            runner.validate_duration_evidence(extra_key)

        missing_key = json.loads(json.dumps(valid))
        del missing_key["versions"][0]["restart"]["phaseTotalMs"]
        with self.assertRaises(runner.MatrixFailure):
            runner.validate_duration_evidence(missing_key)

        impossible_total = json.loads(json.dumps(valid))
        impossible_total["versions"][0]["coldStart"] = {
            "adapterMs": 2,
            "phaseTotalMs": 3,
            "providerReadyMs": 2,
            "stopMs": 2,
        }
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "shorter than sequential components",
        ):
            runner.validate_duration_evidence(impossible_total)

        allowed_ceiling_discrepancy = json.loads(json.dumps(valid))
        allowed_ceiling_discrepancy["versions"][0]["coldStart"] = {
            "adapterMs": 1,
            "phaseTotalMs": 1,
            "providerReadyMs": 1,
            "stopMs": 1,
        }
        runner.validate_duration_evidence(allowed_ceiling_discrepancy)

    def test_duration_evidence_retains_no_provider_payload(self) -> None:
        serialized = json.dumps(
            runner.duration_evidence_result(self.duration_versions()),
            ensure_ascii=True,
            sort_keys=True,
        )
        for forbidden in (
            "private-model:latest",
            "/private/source/models",
            "http://127.0.0.1",
            "prompt",
            "images",
            "vectorValues",
            "providerOutput",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_recorded_live_fault_injection_fixture_is_closed(self) -> None:
        fixture = runner.recorded_live_fault_injection_fixture()

        runner.validate_recorded_live_fault_injection_fixture(fixture)
        self.assertEqual(fixture["faultObservationCount"], 6)
        self.assertEqual(fixture["faultsPerVersion"], 3)
        self.assertEqual(fixture["recoveryRunsPerVersion"], 3)
        self.assertEqual(
            fixture["canonicalFixtureSha256"],
            runner.recorded_selected_model_backed_fixture_sha256(
                runner.CHAT_MODEL_BACKED_PROFILE
            ),
        )
        self.assertEqual(
            [
                row["faultId"]
                for row in fixture["versions"][0]["faults"]
            ],
            list(runner.LIVE_FAULT_IDS),
        )

        serialized = json.dumps(fixture, ensure_ascii=True, sort_keys=True)
        for forbidden in (
            "private-model:latest",
            "/private/source/models",
            "http://127.0.0.1",
            "prompt",
            "images",
            "vectorValues",
            "providerOutput",
            "provider-exit-adapter.log",
        ):
            self.assertNotIn(forbidden, serialized)

        mutations = (
            (
                "boolean count",
                ("faultObservationCount",),
                True,
            ),
            (
                "canonical fixture",
                ("canonicalFixtureSha256",),
                "0" * 64,
            ),
            (
                "deadline",
                ("deadlinesMs", "postFaultTerminal"),
                15_001,
            ),
            (
                "archive identity",
                ("versions", 0, "archiveSha256"),
                "0" * 64,
            ),
            (
                "fault order",
                ("versions", 0, "faults", 0, "faultId"),
                runner.LIVE_FAULT_IDS[1],
            ),
            (
                "recovery",
                ("versions", 0, "faults", 0, "recoveryPassed"),
                False,
            ),
        )
        for label, path, replacement in mutations:
            with self.subTest(label=label):
                mutated = json.loads(json.dumps(fixture))
                target = mutated
                for component in path[:-1]:
                    target = target[component]
                target[path[-1]] = replacement
                with self.assertRaises(runner.MatrixFailure):
                    runner.validate_recorded_live_fault_injection_fixture(
                        mutated
                    )

        extra_key = json.loads(json.dumps(fixture))
        extra_key["unexpected"] = True
        with self.assertRaises(runner.MatrixFailure):
            runner.validate_recorded_live_fault_injection_fixture(extra_key)

    def test_embedding_semantic_quality_task_set_is_closed(self) -> None:
        data = runner.recorded_embedding_semantic_quality_task_set_bytes()
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            runner.EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256,
        )
        value = runner.strict_json_loads(
            data,
            label="embedding semantic-quality task set test",
        )
        runner.validate_embedding_semantic_quality_task_set(value)
        self.assertEqual(len(value["scenarios"]), 4)
        self.assertEqual(len(value["firstCall"]), 16)
        self.assertEqual(len(value["secondCallOrder"]), 16)

        mutations = []
        boolean_threshold = json.loads(json.dumps(value))
        boolean_threshold["minimumPositiveMarginBasisPoints"] = True
        mutations.append(boolean_threshold)
        duplicate_input = json.loads(json.dumps(value))
        duplicate_input["firstCall"][1]["id"] = (
            duplicate_input["firstCall"][0]["id"]
        )
        mutations.append(duplicate_input)
        duplicate_role = json.loads(json.dumps(value))
        duplicate_role["scenarios"][0]["positiveId"] = (
            duplicate_role["scenarios"][0]["queryId"]
        )
        mutations.append(duplicate_role)
        invalid_permutation = json.loads(json.dumps(value))
        invalid_permutation["secondCallOrder"] = [
            row["id"] for row in invalid_permutation["firstCall"]
        ]
        mutations.append(invalid_permutation)
        extra_key = json.loads(json.dumps(value))
        extra_key["unexpected"] = True
        mutations.append(extra_key)
        for mutation_index, mutated in enumerate(mutations):
            with self.subTest(mutation=mutation_index):
                with self.assertRaises(runner.MatrixFailure):
                    runner.validate_embedding_semantic_quality_task_set(
                        mutated
                    )

    def test_recorded_embedding_semantic_quality_fixture_is_closed(
        self,
    ) -> None:
        fixture = runner.recorded_embedding_semantic_quality_fixture()

        runner.validate_recorded_embedding_semantic_quality_fixture(
            fixture
        )
        self.assertEqual(fixture["semanticObservationCount"], 2)
        self.assertEqual(fixture["recoveryObservationCount"], 2)
        self.assertEqual(
            fixture["taskSet"]["sha256"],
            runner.EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256,
        )
        self.assertEqual(
            fixture["canonicalFixtureSha256"],
            runner.recorded_selected_model_backed_fixture_sha256(
                runner.EMBEDDING_MODEL_BACKED_PROFILE
            ),
        )
        self.assertEqual(
            fixture["swiftSources"],
            {
                "liveAssertionsSha256": (
                    runner
                    .EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_SHA256
                ),
                "semanticScorerSha256": (
                    runner.EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_SHA256
                ),
            },
        )
        self.assertEqual(
            [row["version"] for row in fixture["versions"]],
            [candidate["version"] for candidate in runner.EXACT_CANDIDATES],
        )

        serialized = json.dumps(fixture, ensure_ascii=True, sort_keys=True)
        task_set = runner.strict_json_loads(
            runner.recorded_embedding_semantic_quality_task_set_bytes(),
            label="embedding semantic-quality task set test",
        )
        for forbidden in (
            "/private/source/models",
            "http://127.0.0.1",
            "vectorValues",
            "providerOutput",
            "embedding-semantic-semantic-adapter.log",
            *(row["text"] for row in task_set["firstCall"]),
        ):
            self.assertNotIn(forbidden, serialized)

        mutations = (
            ("boolean count", ("semanticObservationCount",), True),
            (
                "task SHA",
                ("taskSet", "sha256"),
                "0" * 64,
            ),
            (
                "runner SHA",
                ("runnerSourceSha256",),
                "0" * 64,
            ),
            (
                "scorer source SHA",
                ("swiftSources", "semanticScorerSha256"),
                "0" * 64,
            ),
            (
                "live assertion source SHA",
                ("swiftSources", "liveAssertionsSha256"),
                "0" * 64,
            ),
            (
                "threshold",
                ("thresholds", "minimumPositiveMarginBasisPoints"),
                199,
            ),
            (
                "semantic flag",
                ("versions", 0, "semantic", "repeatabilityPassed"),
                False,
            ),
            (
                "exact test execution",
                ("versions", 0, "semantic", "exactTestCaseExecuted"),
                False,
            ),
            (
                "Swift source preservation",
                ("versions", 0, "recovery", "swiftSourcesUnchanged"),
                False,
            ),
            (
                "archive identity",
                ("versions", 0, "archiveSha256"),
                "0" * 64,
            ),
        )
        for label, path, replacement in mutations:
            with self.subTest(label=label):
                mutated = json.loads(json.dumps(fixture))
                target = mutated
                for component in path[:-1]:
                    target = target[component]
                target[path[-1]] = replacement
                with self.assertRaises(runner.MatrixFailure):
                    runner.validate_recorded_embedding_semantic_quality_fixture(
                        mutated
                    )

        extra_key = json.loads(json.dumps(fixture))
        extra_key["unexpected"] = True
        with self.assertRaises(runner.MatrixFailure):
            runner.validate_recorded_embedding_semantic_quality_fixture(
                extra_key
            )

    def test_embedding_semantic_quality_rejects_swift_source_drift(
        self,
    ) -> None:
        for label, expected_sha_name in (
            (
                "semantic scorer",
                "EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_SHA256",
            ),
            (
                "live assertion",
                "EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_SHA256",
            ),
        ):
            with (
                self.subTest(label=label),
                patch.object(runner, expected_sha_name, "0" * 64),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    f"{label} source bytes drifted",
                ),
            ):
                runner.assert_recorded_embedding_semantic_quality_swift_sources()

    def test_source_catalog_rejects_boolean_size(self) -> None:
        with patch.object(
            runner,
            "fetch_json",
            return_value={
                "models": [
                    {
                        "digest": "0" * 64,
                        "name": "model",
                        "size": True,
                    }
                ]
            },
        ):
            with self.assertRaises(runner.MatrixFailure):
                runner.source_catalog_rows(runner.SOURCE_OLLAMA_BASE_URL)

    def test_selection_prefers_smallest_unloaded_local_chat_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            embedding_digest, embedding_size = self.write_model(
                store,
                model_path="registry.example/private/embed/latest",
                blob_contents=(b"embedding-config", b"embedding-weights"),
            )
            running_digest, running_size = self.write_model(
                store,
                model_path="registry.example/private/running/latest",
                blob_contents=(b"running-config", b"running-weights"),
            )
            selected_digest, selected_size = self.write_model(
                store,
                model_path="registry.example/private/selected/latest",
                blob_contents=(b"selected-config", b"selected-weights"),
            )
            rows = (
                {
                    "digest": embedding_digest,
                    "name": "embedding",
                    "size": embedding_size,
                },
                {
                    "digest": running_digest,
                    "name": "running:latest",
                    "size": running_size,
                },
                {
                    "digest": selected_digest,
                    "name": "selected",
                    "size": selected_size,
                },
            )

            def capabilities(
                _base_url: str,
                model_name: str,
            ) -> tuple[str, ...]:
                return (
                    ("embedding",)
                    if model_name == "embedding"
                    else ("completion",)
                )

            with (
                patch.object(
                    runner,
                    "source_running_model_names",
                    return_value=frozenset({"running"}),
                ),
                patch.object(runner, "source_catalog_rows", return_value=rows),
                patch.object(
                    runner,
                    "model_capabilities",
                    side_effect=capabilities,
                ),
            ):
                selected = runner.select_source_chat_model(store)

            self.assertEqual(selected.provider_model_id, "selected")
            self.assertEqual(selected.manifest_digest, selected_digest)
            self.assertEqual(selected.model_artifact_bytes, selected_size)

    def test_embedding_selection_excludes_chat_and_picks_smallest_embedding(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            chat_digest, chat_size = self.write_model(
                store,
                model_path="registry.example/private/chat/latest",
                blob_contents=(b"c", b"h"),
            )
            larger_embedding_digest, larger_embedding_size = self.write_model(
                store,
                model_path="registry.example/private/embed-large/latest",
                blob_contents=(b"embedding-large-config", b"embedding-large-weights"),
            )
            selected_digest, selected_size = self.write_model(
                store,
                model_path="registry.example/private/embed-selected/latest",
                blob_contents=(b"embed-config", b"embed-weights"),
            )
            rows = (
                {
                    "digest": chat_digest,
                    "name": "smaller-chat",
                    "size": chat_size,
                },
                {
                    "digest": larger_embedding_digest,
                    "name": "larger-embedding",
                    "size": larger_embedding_size,
                },
                {
                    "digest": selected_digest,
                    "name": "selected-embedding",
                    "size": selected_size,
                },
            )

            def capabilities(
                _base_url: str,
                model_name: str,
            ) -> tuple[str, ...]:
                return (
                    ("completion",)
                    if model_name == "smaller-chat"
                    else ("embedding",)
                )

            with (
                patch.object(
                    runner,
                    "source_running_model_names",
                    return_value=frozenset(),
                ),
                patch.object(runner, "source_catalog_rows", return_value=rows),
                patch.object(
                    runner,
                    "model_capabilities",
                    side_effect=capabilities,
                ),
            ):
                selected = runner.select_source_embedding_model(store)

            self.assertEqual(selected.provider_model_id, "selected-embedding")
            self.assertEqual(selected.manifest_digest, selected_digest)
            self.assertEqual(selected.model_artifact_bytes, selected_size)

    def test_vision_selection_requires_vision_and_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            completion_digest, completion_size = self.write_model(
                store,
                model_path="registry.example/private/completion/latest",
                blob_contents=(b"c", b"m"),
            )
            vision_only_digest, vision_only_size = self.write_model(
                store,
                model_path="registry.example/private/vision-only/latest",
                blob_contents=(b"v", b"o"),
            )
            selected_digest, selected_size = self.write_model(
                store,
                model_path="registry.example/private/vision-chat/latest",
                blob_contents=(b"vision-config", b"vision-chat-weights"),
            )
            rows = (
                {
                    "digest": completion_digest,
                    "name": "completion-only",
                    "size": completion_size,
                },
                {
                    "digest": vision_only_digest,
                    "name": "vision-only",
                    "size": vision_only_size,
                },
                {
                    "digest": selected_digest,
                    "name": "selected-vision",
                    "size": selected_size,
                },
            )

            def capabilities(
                _base_url: str,
                model_name: str,
            ) -> tuple[str, ...]:
                if model_name == "completion-only":
                    return ("completion",)
                if model_name == "vision-only":
                    return ("vision",)
                return ("completion", "vision")

            with (
                patch.object(
                    runner,
                    "source_running_model_names",
                    return_value=frozenset(),
                ),
                patch.object(runner, "source_catalog_rows", return_value=rows),
                patch.object(
                    runner,
                    "model_capabilities",
                    side_effect=capabilities,
                ),
            ):
                selected = runner.select_source_vision_model(store)

            self.assertEqual(selected.provider_model_id, "selected-vision")
            self.assertEqual(selected.manifest_digest, selected_digest)
            self.assertEqual(selected.model_artifact_bytes, selected_size)

    def test_manifest_rejects_descriptor_size_type_confusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            blob_digest = hashlib.sha256(b"x").hexdigest()
            blob_path = store / "blobs" / f"sha256-{blob_digest}"
            blob_path.parent.mkdir(parents=True)
            blob_path.write_bytes(b"x")
            manifest_path = store / "manifest"
            manifest_path.write_text(
                json.dumps(
                    {
                        "config": {
                            "digest": f"sha256:{blob_digest}",
                            "size": True,
                        },
                        "layers": [],
                        "schemaVersion": 2,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(runner.MatrixFailure):
                runner.manifest_blobs(store, manifest_path)

    def test_manifest_rejects_same_size_blob_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory)
            self.write_model(
                store,
                model_path="registry.example/private/model/latest",
                blob_contents=(b"config", b"weights"),
            )
            manifest_path = (
                store
                / "manifests"
                / "registry.example/private/model/latest"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            blob_path = (
                store
                / "blobs"
                / manifest["config"]["digest"].replace(":", "-", 1)
            )
            metadata = blob_path.stat()
            blob_path.write_bytes(b"CONFIG")
            os.utime(
                blob_path,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns),
            )

            with self.assertRaises(runner.MatrixFailure):
                runner.manifest_blobs(store, manifest_path)

    @unittest.skipUnless(os.uname().sysname == "Darwin", "clonefile is macOS-only")
    def test_copy_on_write_snapshot_is_isolated_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = root / "source"
            selected = self.selected_model(store)
            destination = root / "snapshot"

            state = runner.create_model_snapshot(selected, destination)

            self.assertEqual(len(state), len(selected.blobs) + 1)
            cloned_blob = destination / selected.blobs[0].relative_path
            original_bytes = selected.blobs[0].source_path.read_bytes()
            metadata = cloned_blob.stat()
            replacement = bytes([original_bytes[0] ^ 0xFF]) + original_bytes[1:]
            cloned_blob.write_bytes(replacement)
            os.utime(
                cloned_blob,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns),
            )
            self.assertEqual(selected.blobs[0].source_path.read_bytes(), original_bytes)
            self.assertNotEqual(runner.model_snapshot_state(destination), state)

    def test_live_fault_candidate_runs_three_faults_and_recoveries_in_order(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_model(root / "source")
            temporary_root = root / "candidate-root"
            temporary_root.mkdir()
            call_order: list[tuple[str, str]] = []
            initial_state = tuple(
                (f"file-{index}", index, f"{index:064x}")
                for index in range(len(selected.blobs) + 1)
            )

            def extract_archive(
                command: list[str],
                **_kwargs: object,
            ) -> None:
                extracted = Path(command[-1])
                binary = extracted / "ollama"
                binary.write_bytes(b"binary")
                binary.chmod(0o755)

            def record_fault(**kwargs: object) -> None:
                call_order.append(("fault", str(kwargs["fault_id"])))

            def record_recovery(**kwargs: object) -> None:
                call_order.append(("recovery", str(kwargs["fault_id"])))

            with (
                patch.object(runner, "download_archive"),
                patch.object(
                    runner,
                    "run_checked",
                    side_effect=extract_archive,
                ),
                patch.object(
                    runner,
                    "create_model_snapshot",
                    return_value=initial_state,
                ),
                patch.object(runner, "reserve_unique_port", return_value=31341),
                patch.object(
                    runner,
                    "endpoint_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner,
                    "run_live_fault_scenario",
                    side_effect=record_fault,
                ),
                patch.object(
                    runner,
                    "run_live_fault_recovery",
                    side_effect=record_recovery,
                ),
            ):
                result = runner.run_live_fault_injection_candidate(
                    runner.EXACT_CANDIDATES[0],
                    temporary_root,
                    selected=selected,
                )

            self.assertEqual(
                call_order,
                [
                    entry
                    for fault_id in runner.LIVE_FAULT_IDS
                    for entry in (
                        ("fault", fault_id),
                        ("recovery", fault_id),
                    )
                ],
            )
            self.assertEqual(result["testRuns"], 6)
            self.assertEqual(result["recoveryRuns"], 3)
            self.assertEqual(
                [row["faultId"] for row in result["faults"]],
                list(runner.LIVE_FAULT_IDS),
            )

    def test_embedding_semantic_candidate_runs_semantic_then_fresh_recovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_embedding_model(root / "source")
            temporary_root = root / "candidate-root"
            temporary_root.mkdir()
            initial_state = tuple(
                (f"file-{index}", index, f"{index:064x}")
                for index in range(len(selected.blobs) + 1)
            )
            fixture_version = (
                runner.recorded_embedding_semantic_quality_fixture()[
                    "versions"
                ][0]
            )
            call_order: list[str] = []

            def extract_archive(
                command: list[str],
                **_kwargs: object,
            ) -> None:
                extracted = Path(command[-1])
                binary = extracted / "ollama"
                binary.write_bytes(b"binary")
                binary.chmod(0o755)

            def run_phase(**kwargs: object) -> dict[str, bool]:
                phase = str(kwargs["phase"])
                call_order.append(phase)
                return dict(fixture_version[phase])

            with (
                patch.object(runner, "download_archive"),
                patch.object(
                    runner,
                    "run_checked",
                    side_effect=extract_archive,
                ),
                patch.object(
                    runner,
                    "create_model_snapshot",
                    return_value=initial_state,
                ),
                patch.object(
                    runner,
                    "create_embedding_semantic_quality_task_set_copy",
                    return_value=temporary_root / "task-set.json",
                ),
                patch.object(runner, "reserve_unique_port", return_value=31342),
                patch.object(
                    runner,
                    "endpoint_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner,
                    "run_embedding_semantic_quality_phase",
                    side_effect=run_phase,
                ),
            ):
                result = runner.run_embedding_semantic_quality_candidate(
                    runner.EXACT_CANDIDATES[0],
                    temporary_root,
                    selected=selected,
                )

            self.assertEqual(call_order, ["semantic", "recovery"])
            self.assertEqual(result, fixture_version)

    def test_model_backed_phase_stops_provider_when_adapter_fails(self) -> None:
        class FakeProcess:
            def __init__(self) -> None:
                self.terminate_count = 0
                self.wait_timeouts: list[float] = []
                self.kill_count = 0

            def poll(self) -> None:
                return None

            def terminate(self) -> None:
                self.terminate_count += 1

            def wait(self, timeout: float) -> int:
                self.wait_timeouts.append(timeout)
                return 0

            def kill(self) -> None:
                self.kill_count += 1

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_model(root / "source")
            candidate_root = root / "candidate"
            candidate_root.mkdir()
            models_directory = root / "snapshot"
            models_directory.mkdir()
            fake_process = FakeProcess()
            initial_snapshot_state: tuple[tuple[str, int, str], ...] = ()

            with (
                patch.object(
                    runner.subprocess,
                    "Popen",
                    return_value=fake_process,
                ),
                patch.object(runner, "wait_until_ready"),
                patch.object(
                    runner,
                    "run_selected_model_backed_adapter_test",
                    side_effect=runner.MatrixFailure(
                        "injected adapter failure"
                    ),
                ),
                patch.object(
                    runner,
                    "endpoint_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner,
                    "model_snapshot_state",
                    return_value=initial_snapshot_state,
                ) as snapshot_state_mock,
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "injected adapter failure",
                ),
            ):
                runner.run_selected_model_backed_phase(
                    binary=root / "ollama",
                    extracted=root,
                    models_directory=models_directory,
                    candidate_root=candidate_root,
                    phase="failureProbe",
                    port=31337,
                    base_url="http://127.0.0.1:31337",
                    candidate=runner.EXACT_CANDIDATES[0],
                    selected=selected,
                    profile=runner.CHAT_MODEL_BACKED_PROFILE,
                    initial_snapshot_state=initial_snapshot_state,
                )

            self.assertEqual(fake_process.terminate_count, 1)
            self.assertEqual(len(fake_process.wait_timeouts), 1)
            self.assertGreater(fake_process.wait_timeouts[0], 0)
            self.assertLessEqual(
                fake_process.wait_timeouts[0],
                runner.STOP_DEADLINE_SECONDS,
            )
            self.assertEqual(fake_process.kill_count, 0)
            snapshot_state_mock.assert_called_once_with(models_directory)

    def test_duration_overrun_is_checked_after_stop_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_model(root / "source")
            candidate_root = root / "candidate"
            candidate_root.mkdir()
            models_directory = root / "snapshot"
            models_directory.mkdir()
            initial_snapshot_state: tuple[tuple[str, int, str], ...] = ()
            adapter_overrun_ns = (
                runner.COMMAND_DEADLINE_SECONDS
                * runner.NANOSECONDS_PER_SECOND
                + 1
            )
            duration_sink: dict[str, dict[str, int]] = {}

            with (
                patch.object(runner.subprocess, "Popen", return_value=object()),
                patch.object(runner, "wait_until_ready"),
                patch.object(
                    runner,
                    "run_selected_model_backed_adapter_test",
                ),
                patch.object(runner, "stop_provider") as stop_mock,
                patch.object(
                    runner,
                    "model_snapshot_state",
                    return_value=initial_snapshot_state,
                ) as snapshot_mock,
                patch.object(
                    runner,
                    "endpoint_is_available",
                    return_value=False,
                ),
                patch.object(
                    runner.time,
                    "monotonic_ns",
                    side_effect=(
                        0,
                        0,
                        0,
                        adapter_overrun_ns,
                        adapter_overrun_ns,
                        adapter_overrun_ns,
                        adapter_overrun_ns,
                    ),
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "adapter duration exceeded the deadline",
                ),
            ):
                runner.run_selected_model_backed_phase(
                    binary=root / "ollama",
                    extracted=root,
                    models_directory=models_directory,
                    candidate_root=candidate_root,
                    phase="durationProbe",
                    port=31340,
                    base_url="http://127.0.0.1:31340",
                    candidate=runner.EXACT_CANDIDATES[0],
                    selected=selected,
                    profile=runner.CHAT_MODEL_BACKED_PROFILE,
                    initial_snapshot_state=initial_snapshot_state,
                    duration_sink=duration_sink,
                )

            stop_mock.assert_called_once()
            snapshot_mock.assert_called_once_with(models_directory)
            self.assertEqual(duration_sink, {})

    def test_model_backed_phase_failure_priority_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_model(root / "source")
            candidate_root = root / "candidate"
            candidate_root.mkdir()
            models_directory = root / "snapshot"
            models_directory.mkdir()
            initial_snapshot_state: tuple[tuple[str, int, str], ...] = ()

            def capture_failure(
                *,
                popen_error: Exception | None = None,
                stop_error: Exception | None = None,
                snapshot_state: tuple[tuple[str, int, str], ...] = (),
                snapshot_error: Exception | None = None,
            ) -> tuple[Exception, int, int]:
                with (
                    patch.object(
                        runner.subprocess,
                        "Popen",
                        return_value=object(),
                        side_effect=popen_error,
                    ),
                    patch.object(runner, "wait_until_ready"),
                    patch.object(
                        runner,
                        "run_selected_model_backed_adapter_test",
                        side_effect=runner.MatrixFailure(
                            "injected adapter failure"
                        ),
                    ),
                    patch.object(
                        runner,
                        "stop_provider",
                        side_effect=stop_error,
                    ) as stop_mock,
                    patch.object(
                        runner,
                        "model_snapshot_state",
                        return_value=snapshot_state,
                        side_effect=snapshot_error,
                    ) as snapshot_mock,
                ):
                    try:
                        runner.run_selected_model_backed_phase(
                            binary=root / "ollama",
                            extracted=root,
                            models_directory=models_directory,
                            candidate_root=candidate_root,
                            phase="priorityProbe",
                            port=31338,
                            base_url="http://127.0.0.1:31338",
                            candidate=runner.EXACT_CANDIDATES[0],
                            selected=selected,
                            profile=runner.CHAT_MODEL_BACKED_PROFILE,
                            initial_snapshot_state=initial_snapshot_state,
                        )
                    except Exception as error:
                        return (
                            error,
                            stop_mock.call_count,
                            snapshot_mock.call_count,
                        )
                self.fail("injected phase failure unexpectedly passed")

            cases = (
                (
                    "popen_error",
                    {
                        "popen_error": OSError("injected Popen failure"),
                    },
                    OSError,
                    "injected Popen failure",
                    0,
                    1,
                ),
                (
                    "stop_over_adapter",
                    {
                        "stop_error": runner.MatrixFailure(
                            "injected stop failure"
                        ),
                    },
                    runner.MatrixFailure,
                    "injected stop failure",
                    1,
                    1,
                ),
                (
                    "snapshot_drift_over_stop",
                    {
                        "stop_error": runner.MatrixFailure(
                            "injected stop failure"
                        ),
                        "snapshot_state": (
                            ("changed", 1, "0" * 64),
                        ),
                    },
                    runner.MatrixFailure,
                    "isolated model snapshot bytes changed",
                    1,
                    1,
                ),
                (
                    "snapshot_read_over_stop",
                    {
                        "stop_error": runner.MatrixFailure(
                            "injected stop failure"
                        ),
                        "snapshot_error": OSError(
                            "injected snapshot read failure"
                        ),
                    },
                    OSError,
                    "injected snapshot read failure",
                    1,
                    1,
                ),
            )
            for (
                label,
                arguments,
                expected_type,
                expected_message,
                expected_stop_count,
                expected_snapshot_count,
            ) in cases:
                with self.subTest(label=label):
                    error, stop_count, snapshot_count = capture_failure(
                        **arguments
                    )
                    self.assertIsInstance(error, expected_type)
                    self.assertIn(expected_message, str(error))
                    self.assertEqual(stop_count, expected_stop_count)
                    self.assertEqual(
                        snapshot_count,
                        expected_snapshot_count,
                    )

    def test_sigstop_fault_accepts_only_forced_termination_result(
        self,
    ) -> None:
        class ReapedProcess:
            pid = 424_242

            def poll(self) -> int:
                return -9

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = self.selected_model(root / "source")
            models_directory = root / "snapshot"
            models_directory.mkdir()
            initial_state: tuple[tuple[str, int, str], ...] = ()

            def run_with_stop_error(error: Exception) -> None:
                with (
                    patch.object(
                        runner,
                        "start_live_fault_provider",
                        return_value=ReapedProcess(),
                    ),
                    patch.object(
                        runner,
                        "signal_provider_process",
                    ) as signal_mock,
                    patch.object(
                        runner,
                        "stop_provider",
                        side_effect=error,
                    ),
                    patch.object(
                        runner,
                        "ensure_fault_provider_stopped",
                    ),
                    patch.object(
                        runner,
                        "process_group_is_available",
                        return_value=False,
                    ),
                    patch.object(
                        runner,
                        "model_snapshot_state",
                        return_value=initial_state,
                    ),
                ):
                    runner.run_live_fault_scenario(
                        fault_id=runner.LIVE_FAULT_IDS[2],
                        binary=root / "ollama",
                        extracted=root,
                        models_directory=models_directory,
                        candidate_root=root,
                        port=31342,
                        base_url="http://127.0.0.1:31342",
                        candidate=runner.EXACT_CANDIDATES[0],
                        selected=selected,
                        initial_snapshot_state=initial_state,
                    )
                signal_mock.assert_called_once_with(
                    ANY,
                    runner.signal.SIGSTOP,
                    signal_process_group=True,
                )

            run_with_stop_error(
                runner.MatrixFailure("provider required forced termination")
            )
            with self.assertRaisesRegex(
                runner.MatrixFailure,
                "different stop failure",
            ):
                run_with_stop_error(
                    runner.MatrixFailure("different stop failure")
                )

    def test_failed_matrix_cleans_root_and_rechecks_observed_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "source"
            selected = self.selected_model(store)

            error, captured_roots, call_counts = (
                self.run_injected_matrix_failure(store, selected)
            )

            self.assertEqual(str(error), "injected candidate failure")
            self.assertEqual(len(captured_roots), 1)
            self.assertFalse(captured_roots[0].exists())
            self.assertEqual(call_counts, (2, 2, 2))

    def test_failed_live_fault_matrix_cleans_before_source_readback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "source"
            selected = self.selected_model(store)
            source_state = runner.expected_selected_source_state(selected)
            catalog = (
                {
                    "digest": selected.manifest_digest,
                    "name": selected.provider_model_id,
                    "size": selected.model_artifact_bytes,
                },
            )
            captured_roots: list[Path] = []
            profile = self.profile_for_selected(
                selected,
                temporary_prefix=(
                    f"aetherlink-ollama-live-fault-test-{os.getpid()}-"
                ),
            )

            def fail_candidate(
                _candidate: dict[str, str],
                temporary_root: Path,
                **_kwargs: object,
            ) -> dict[str, object]:
                captured_roots.append(temporary_root)
                raise runner.MatrixFailure("injected live fault failure")

            def source_version(_base_url: str) -> str:
                if captured_roots:
                    self.assertFalse(
                        captured_roots[0].exists(),
                        "source readback started before fault root cleanup",
                    )
                return profile.recorded_source_version

            with (
                patch.object(
                    runner,
                    "CHAT_MODEL_BACKED_PROFILE",
                    profile,
                ),
                patch.object(
                    runner,
                    "source_provider_version",
                    side_effect=source_version,
                ) as version_mock,
                patch.object(
                    runner,
                    "source_catalog_rows",
                    side_effect=(catalog, catalog),
                ) as catalog_mock,
                patch.object(
                    runner,
                    "source_running_model_names",
                    side_effect=(frozenset(), frozenset()),
                ) as running_mock,
                patch.object(
                    runner,
                    "select_source_model",
                    return_value=selected,
                ),
                patch.object(
                    runner,
                    "selected_source_state",
                    return_value=source_state,
                ),
                patch.object(
                    runner,
                    "run_live_fault_injection_candidate",
                    side_effect=fail_candidate,
                ),
                self.assertRaisesRegex(
                    runner.MatrixFailure,
                    "injected live fault failure",
                ),
            ):
                runner.run_live_fault_injection_matrix(store)

            self.assertEqual(len(captured_roots), 1)
            self.assertFalse(captured_roots[0].exists())
            self.assertEqual(version_mock.call_count, 2)
            self.assertEqual(catalog_mock.call_count, 2)
            self.assertEqual(running_mock.call_count, 2)

    def test_failed_matrix_rejects_provider_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "source"
            selected = self.selected_model(store)

            error, _, _ = self.run_injected_matrix_failure(
                store,
                selected,
                version_after="0.32.5",
            )

            self.assertIn("observed source provider version", str(error))

    def test_failed_matrix_rejects_catalog_identity_projection_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "source"
            selected = self.selected_model(store)
            changed_catalog = (
                {
                    "digest": selected.manifest_digest,
                    "name": selected.provider_model_id,
                    "size": selected.model_artifact_bytes + 1,
                },
            )

            error, _, _ = self.run_injected_matrix_failure(
                store,
                selected,
                catalog_after=changed_catalog,
            )

            self.assertIn(
                "catalog identity projection",
                str(error),
            )

    def test_failed_matrix_rejects_running_identity_set_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "source"
            selected = self.selected_model(store)

            error, _, _ = self.run_injected_matrix_failure(
                store,
                selected,
                running_after=frozenset({"newly-running-model"}),
            )

            self.assertIn("running identity set", str(error))

    def test_failed_matrix_rejects_selected_file_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "source"
            selected = self.selected_model(store)
            selected_blob = next(
                blob.source_path
                for blob in selected.blobs
                if blob.source_path.read_bytes() == b"config"
            )

            error, _, _ = self.run_injected_matrix_failure(
                store,
                selected,
                mutate_source=lambda: selected_blob.write_bytes(b"CONFIG"),
            )

            self.assertIn("selected file bytes changed", str(error))

    def test_model_backed_result_retains_no_model_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            selected = self.selected_model(Path(temporary_directory))
            result = runner.model_backed_result(
                source_version="0.32.4",
                catalog_model_count=4,
                selected=selected,
                versions=[],
            )
            serialized = json.dumps(result, sort_keys=True)

            self.assertNotIn(selected.provider_model_id, serialized)
            self.assertFalse(result["snapshot"]["modelNameRetained"])
            self.assertFalse(result["snapshot"]["modelDownloadAttempted"])

    def test_duration_opt_in_preserves_exact_canonical_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "source"
            selected = self.selected_model(store)
            profile = self.profile_for_selected(
                selected,
                temporary_prefix=(
                    f"aetherlink-ollama-duration-test-{os.getpid()}-"
                ),
            )
            catalog = (
                {
                    "digest": selected.manifest_digest,
                    "name": selected.provider_model_id,
                    "size": selected.model_artifact_bytes,
                },
            )
            fixture = runner.recorded_selected_model_backed_fixture(profile)
            fixture_versions = {
                row["version"]: row
                for row in fixture["versions"]
            }

            def successful_candidate(
                candidate: dict[str, str],
                _temporary_root: Path,
                **kwargs: object,
            ) -> dict[str, object]:
                duration_versions = kwargs.get("duration_versions")
                if isinstance(duration_versions, list):
                    duration_row = next(
                        row
                        for row in self.duration_versions()
                        if row["version"] == candidate["version"]
                    )
                    duration_versions.append(duration_row)
                return json.loads(
                    json.dumps(fixture_versions[candidate["version"]])
                )

            with (
                patch.object(
                    runner,
                    "source_provider_version",
                    return_value="0.32.4",
                ),
                patch.object(
                    runner,
                    "source_catalog_rows",
                    return_value=catalog,
                ),
                patch.object(
                    runner,
                    "source_running_model_names",
                    return_value=frozenset(),
                ),
                patch.object(
                    runner,
                    "select_source_model",
                    return_value=selected,
                ),
                patch.object(
                    runner,
                    "run_selected_model_backed_candidate",
                    side_effect=successful_candidate,
                ),
            ):
                stable_result = runner.run_selected_model_backed_matrix(
                    store,
                    profile=profile,
                )
                duration_result = runner.run_selected_model_backed_matrix(
                    store,
                    profile=profile,
                    include_duration_evidence=True,
                )

            stable_bytes = json.dumps(
                stable_result,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            fixture_bytes = json.dumps(
                fixture,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            self.assertEqual(stable_bytes, fixture_bytes)
            self.assertEqual(
                set(duration_result) - set(stable_result),
                {"durationEvidence"},
            )
            duration_projection = {
                key: value
                for key, value in duration_result.items()
                if key != "durationEvidence"
            }
            self.assertEqual(duration_projection, stable_result)
            runner.validate_duration_evidence(
                duration_result["durationEvidence"]
            )
            self.assertNotIn(
                selected.provider_model_id,
                json.dumps(duration_result, sort_keys=True),
            )

    def test_recorded_duration_observation_requires_three_stable_profiles(
        self,
    ) -> None:
        profiles = {
            "chat": runner.CHAT_MODEL_BACKED_PROFILE,
            "embedding": runner.EMBEDDING_MODEL_BACKED_PROFILE,
            "vision": runner.VISION_MODEL_BACKED_PROFILE,
        }
        results = {
            key: {
                **runner.recorded_selected_model_backed_fixture(profile),
                "durationEvidence": runner.duration_evidence_result(
                    self.duration_versions()
                ),
            }
            for key, profile in profiles.items()
        }

        fixture = runner.recorded_duration_observation_result(results)

        self.assertEqual(fixture["phaseObservationCount"], 12)
        self.assertEqual(set(fixture["profiles"]), set(profiles))
        runner.validate_recorded_duration_observation_fixture(fixture)

        drifted_fixture = json.loads(json.dumps(fixture))
        drifted_fixture["profiles"]["chat"]["canonicalFixtureSha256"] = "0" * 64
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "chat profile was invalid",
        ):
            runner.validate_recorded_duration_observation_fixture(
                drifted_fixture
            )

        drifted_results = json.loads(json.dumps(results))
        drifted_results["vision"]["fixtureId"] = "drifted"
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "vision canonical projection drifted",
        ):
            runner.recorded_duration_observation_result(drifted_results)

    def test_embedding_result_retains_no_model_name_or_vector_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            selected = self.selected_embedding_model(Path(temporary_directory))
            result = runner.embedding_model_backed_result(
                source_version="0.32.4",
                catalog_model_count=4,
                selected=selected,
                versions=[],
            )
            serialized = json.dumps(result, sort_keys=True)

            self.assertNotIn(selected.provider_model_id, serialized)
            self.assertNotIn('"embeddings":', serialized)
            self.assertNotIn('"vectorValues":', serialized)
            self.assertEqual(
                result["fixtureId"],
                runner.EMBEDDING_BACKED_RUNNER_ID,
            )
            self.assertFalse(result["snapshot"]["modelNameRetained"])
            self.assertFalse(result["snapshot"]["modelDownloadAttempted"])

    def test_vision_result_retains_no_model_name_input_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            selected = self.selected_vision_model(Path(temporary_directory))
            result = runner.vision_model_backed_result(
                source_version="0.32.4",
                catalog_model_count=4,
                selected=selected,
                versions=[],
            )
            serialized = json.dumps(result, sort_keys=True)

            self.assertNotIn(selected.provider_model_id, serialized)
            for forbidden_value in (
                (
                    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAK0lE"
                    "QVR42u3OIQEAAAwEoetfeovxBoGnq1tKQEBAQEBAQEBAQEBAQEB"
                    "gHXhUDfhqeP5ugAAAAABJRU5ErkJggg=="
                ),
                "Describe the dominant color in this image.",
                "Reply with exactly the single word OK.",
                (
                    "Write the integers from 1 through 10000, one per line, "
                    "without stopping early."
                ),
                "Reply with exactly the single word READY.",
            ):
                self.assertNotIn(forbidden_value, serialized)
            for forbidden_key in (
                "content",
                "dataBase64",
                "imageData",
                "images",
                "input",
                "message",
                "output",
                "prompt",
                "providerOutput",
                "response",
            ):
                self.assertNotIn(f'"{forbidden_key}":', serialized)
            self.assertEqual(
                result["fixtureId"],
                runner.VISION_BACKED_RUNNER_ID,
            )
            self.assertFalse(result["snapshot"]["modelNameRetained"])
            self.assertFalse(result["snapshot"]["modelDownloadAttempted"])

    def test_model_backed_cli_modes_are_mutually_exclusive(self) -> None:
        with (
            patch("sys.stderr", new=io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            runner.parse_arguments(
                [
                    "--model-backed",
                    "--embedding-backed",
                    "--vision-backed",
                ]
            )

    def test_duration_cli_requires_one_model_backed_mode(self) -> None:
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "--duration-evidence requires a model-backed mode",
        ):
            runner.main(["--duration-evidence"])

    def test_duration_cli_forwards_opt_in_for_all_three_profiles(self) -> None:
        cases = (
            ("--model-backed", runner.CHAT_MODEL_BACKED_PROFILE),
            ("--embedding-backed", runner.EMBEDDING_MODEL_BACKED_PROFILE),
            ("--vision-backed", runner.VISION_MODEL_BACKED_PROFILE),
        )
        for flag, expected_profile in cases:
            with (
                self.subTest(flag=flag),
                patch.object(
                    runner,
                    "run_cli_model_backed_matrix",
                    return_value={"ok": True},
                ) as matrix_mock,
                patch("builtins.print"),
            ):
                self.assertEqual(
                    runner.main([flag, "--duration-evidence"]),
                    0,
                )
                self.assertEqual(
                    matrix_mock.call_args.kwargs,
                    {
                        "profile": expected_profile,
                        "include_duration_evidence": True,
                    },
                )

    def test_live_fault_cli_is_separate_and_chat_only(self) -> None:
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "--live-fault-injection requires --model-backed",
        ):
            runner.main(["--live-fault-injection"])
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "--live-fault-injection requires --model-backed",
        ):
            runner.main(
                ["--embedding-backed", "--live-fault-injection"]
            )
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "cannot be combined with --duration-evidence",
        ):
            runner.main(
                [
                    "--model-backed",
                    "--duration-evidence",
                    "--live-fault-injection",
                ]
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            with (
                patch.object(
                    runner,
                    "run_cli_live_fault_injection_matrix",
                    return_value={"ok": True},
                ) as fault_mock,
                patch.object(
                    runner,
                    "run_cli_model_backed_matrix",
                ) as regular_mock,
                patch("builtins.print"),
            ):
                self.assertEqual(
                    runner.main(
                        [
                            "--model-backed",
                            "--live-fault-injection",
                            "--source-model-store",
                            str(source),
                        ]
                    ),
                    0,
                )
            fault_mock.assert_called_once_with(source)
            regular_mock.assert_not_called()

    def test_semantic_quality_cli_is_separate_and_embedding_only(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "--semantic-quality requires --embedding-backed",
        ):
            runner.main(["--semantic-quality"])
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "--semantic-quality requires --embedding-backed",
        ):
            runner.main(["--model-backed", "--semantic-quality"])
        with self.assertRaisesRegex(
            runner.MatrixFailure,
            "cannot be combined with --duration-evidence",
        ):
            runner.main(
                [
                    "--embedding-backed",
                    "--duration-evidence",
                    "--semantic-quality",
                ]
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            with (
                patch.object(
                    runner,
                    "run_cli_embedding_semantic_quality_matrix",
                    return_value={"ok": True},
                ) as semantic_mock,
                patch.object(
                    runner,
                    "run_cli_model_backed_matrix",
                ) as regular_mock,
                patch("builtins.print"),
            ):
                self.assertEqual(
                    runner.main(
                        [
                            "--embedding-backed",
                            "--semantic-quality",
                            "--source-model-store",
                            str(source),
                        ]
                    ),
                    0,
                )
            semantic_mock.assert_called_once_with(source)
            regular_mock.assert_not_called()

    def test_model_backed_cli_suppresses_local_io_failure_details(self) -> None:
        private_model_path = (
            "/private/source/models/manifests/registry/private-vision/latest"
        )
        with patch.object(
            runner,
            "run_selected_model_backed_matrix",
            side_effect=FileNotFoundError(private_model_path),
        ):
            with self.assertRaises(runner.MatrixFailure) as raised:
                runner.main(
                    [
                        "--vision-backed",
                        "--source-model-store",
                        "/private/source/models",
                    ]
                )

        diagnostic = str(raised.exception)
        self.assertEqual(
            diagnostic,
            (
                f"{runner.VISION_BACKED_RUNNER_ID} failed inside the "
                "non-retained local-model boundary"
            ),
        )
        self.assertNotIn(private_model_path, diagnostic)
        self.assertNotIn("private-vision", diagnostic)

    def test_failed_sensitive_command_suppresses_subprocess_output(self) -> None:
        selected_model_name = "private-model-name:latest"
        canonical_alias = runner.canonical_model_name(selected_model_name)
        json_escaped_name = json.dumps(
            selected_model_name,
            ensure_ascii=True,
        )
        unrelated_private_output = "private-provider-diagnostic"
        command_output = "|".join(
            (
                selected_model_name,
                canonical_alias,
                json_escaped_name,
                unrelated_private_output,
            )
        )
        with self.assertRaises(runner.MatrixFailure) as context:
            runner.run_checked(
                [
                    "/bin/sh",
                    "-c",
                    f"printf '%s' '{command_output}'; exit 7",
                ],
                cwd=runner.ROOT,
                environment=os.environ.copy(),
                label="redaction test",
                redactions=(selected_model_name,),
            )

        failure = str(context.exception)
        self.assertNotIn(selected_model_name, failure)
        self.assertNotIn(canonical_alias, failure)
        self.assertNotIn(json_escaped_name, failure)
        self.assertNotIn(unrelated_private_output, failure)
        self.assertIn(
            "[selected-model subprocess output suppressed]",
            failure,
        )


if __name__ == "__main__":
    unittest.main()
