from __future__ import annotations

import ast
import copy
from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from script import run_macos_build24_idle_resource_stability_smoke as runner


def sample_records(
    *,
    resident_values: list[int] | None = None,
    descriptor_values: list[int] | None = None,
    thread_values: list[int] | None = None,
    lateness_milliseconds: int = 0,
) -> list[dict[str, object]]:
    resident = resident_values or [100 * 1024 * 1024] * runner.SAMPLE_COUNT
    descriptors = descriptor_values or [20] * runner.SAMPLE_COUNT
    threads = thread_values or [8] * runner.SAMPLE_COUNT
    if not (
        len(resident)
        == len(descriptors)
        == len(threads)
        == runner.SAMPLE_COUNT
    ):
        raise AssertionError("fixture sample lengths differ")
    return [
        runner.ResourceSample(
            open_file_descriptor_count=descriptors[index],
            resident_bytes=resident[index],
            thread_count=threads[index],
        ).record(
            ordinal=index + 1,
            target_elapsed_milliseconds=(
                (index + 1) * runner.SAMPLE_INTERVAL_MILLISECONDS
            ),
            observed_lateness_milliseconds=lateness_milliseconds,
        )
        for index in range(runner.SAMPLE_COUNT)
    ]


def valid_run() -> dict[str, object]:
    samples = sample_records()
    return {
        "activationPolicy": 0,
        "appKitProcessAbsentAfterReap": True,
        "exitCode": 0,
        "finishedLaunching": True,
        "gracefulTerminationAccepted": True,
        "maximumObservedLatenessMilliseconds": 0,
        "ownedChildProcess": True,
        "processIdentifierRetained": False,
        "processReaped": True,
        "samples": samples,
        "summary": runner.measurement_summary(samples),
    }


def ready_status(executable: Path) -> runner.engine.ApplicationStatus:
    return runner.engine.ApplicationStatus(
        activation_policy=0,
        bundle_identifier=runner.engine.EXPECTED_BUNDLE_ID,
        executable_path=str(executable),
        finished_launching=True,
    )


class FakeClock:
    def __init__(self) -> None:
        self.value = 0
        self.extra_per_sample = 0

    def monotonic_ns(self) -> int:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += int(round(seconds * 1_000_000_000))

    def advance(self, nanoseconds: int) -> None:
        self.value += nanoseconds


class FakeProcess:
    def __init__(
        self,
        *,
        pid: int = 444,
        exit_after_polls: int | None = None,
    ) -> None:
        self.pid = pid
        self.exit_after_polls = exit_after_polls
        self.poll_count = 0
        self.returncode: int | None = None
        self.killed = False

    def poll(self) -> int | None:
        self.poll_count += 1
        if (
            self.exit_after_polls is not None
            and self.poll_count >= self.exit_after_polls
            and self.returncode is None
        ):
            self.returncode = 7
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class Build24IdleResourceStabilitySmokeTests(unittest.TestCase):
    maxDiff = None

    def test_fixed_policy_and_cli_do_not_offer_a_shorter_observation(
        self,
    ) -> None:
        self.assertEqual(runner.WARMUP_MILLISECONDS, 60_000)
        self.assertEqual(runner.OBSERVATION_MILLISECONDS, 600_000)
        self.assertEqual(runner.SAMPLE_INTERVAL_MILLISECONDS, 5_000)
        self.assertEqual(runner.SAMPLE_COUNT, 120)
        self.assertEqual(runner.BASELINE_WINDOW_SAMPLE_COUNT, 12)
        self.assertEqual(runner.FINAL_WINDOW_SAMPLE_COUNT, 12)
        for arguments in (
            ["--observation-seconds", "1"],
            ["--sample-count", "1"],
        ):
            with (
                self.subTest(arguments=arguments),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                runner.parse_args(arguments)

    def test_terminal_release_and_default_paths_are_build24_bound(
        self,
    ) -> None:
        version = runner.current_release()
        self.assertEqual(version.build_number, 24)
        self.assertEqual(
            runner.default_archive_dir().name,
            "aetherlink-1.0.0+24-local-v1",
        )
        self.assertEqual(
            runner.default_result_path().name,
            (
                "macos-packaged-app-build-24-"
                "idle-resource-stability-v1.json"
            ),
        )

    def test_build24_snapshot_inventory_is_exact_and_closed(self) -> None:
        expected = copy.deepcopy(runner.EXPECTED_BUILD24_RELEASE_FILES)
        self.assertEqual(
            runner.validate_build24_snapshot_files(expected),
            expected,
        )
        mutations = []
        missing = copy.deepcopy(expected)
        missing.pop(next(iter(missing)))
        mutations.append(missing)
        extra = copy.deepcopy(expected)
        extra["unexpected"] = {"sha256": "0" * 64, "size": 1}
        mutations.append(extra)
        wrong_hash = copy.deepcopy(expected)
        wrong_hash[next(iter(wrong_hash))]["sha256"] = "0" * 64
        mutations.append(wrong_hash)
        wrong_size = copy.deepcopy(expected)
        wrong_size[next(iter(wrong_size))]["size"] += 1
        mutations.append(wrong_size)
        bool_size = copy.deepcopy(expected)
        bool_size[next(iter(bool_size))]["size"] = True
        mutations.append(bool_size)
        for ordinal, mutation in enumerate(mutations, start=1):
            with self.subTest(mutation=ordinal):
                with self.assertRaises(runner.IdleResourceSmokeError):
                    runner.validate_build24_snapshot_files(mutation)

    def test_resource_sample_record_has_a_closed_exact_integer_schema(
        self,
    ) -> None:
        record = runner.ResourceSample(
            open_file_descriptor_count=21,
            resident_bytes=123_456,
            thread_count=7,
        ).record(
            ordinal=3,
            target_elapsed_milliseconds=15_000,
            observed_lateness_milliseconds=4,
        )
        self.assertEqual(
            set(record),
            {
                "observedLatenessMilliseconds",
                "openFileDescriptorCount",
                "ordinal",
                "residentBytes",
                "targetElapsedMilliseconds",
                "threadCount",
            },
        )
        self.assertTrue(
            all(type(value) is int for value in record.values())
        )

    def test_upper_median_is_integer_and_rejects_bool_or_empty(
        self,
    ) -> None:
        self.assertEqual(runner.upper_median([9, 1, 7, 3]), 7)
        self.assertEqual(runner.upper_median([3]), 3)
        with self.assertRaises(runner.IdleResourceSmokeError):
            runner.upper_median([])
        with self.assertRaises(runner.IdleResourceSmokeError):
            runner.upper_median([1, True])

    def test_metric_summary_accepts_exact_limits_and_rejects_plus_one(
        self,
    ) -> None:
        cases = (
            (
                "descriptor",
                20,
                runner.FINAL_FD_DELTA_LIMIT,
                runner.PEAK_FD_DELTA_LIMIT,
            ),
            (
                "thread",
                8,
                runner.FINAL_THREAD_DELTA_LIMIT,
                runner.PEAK_THREAD_DELTA_LIMIT,
            ),
            (
                "resident",
                100 * 1024 * 1024,
                runner.FINAL_RSS_DELTA_LIMIT_BYTES,
                runner.PEAK_RSS_DELTA_LIMIT_BYTES,
            ),
        )
        for label, baseline, final_limit, peak_limit in cases:
            values = [baseline] * runner.SAMPLE_COUNT
            values[-runner.FINAL_WINDOW_SAMPLE_COUNT:] = [
                baseline + final_limit
            ] * runner.FINAL_WINDOW_SAMPLE_COUNT
            values[50] = baseline + peak_limit
            with self.subTest(label=label, boundary="pass"):
                summary = runner.metric_summary(
                    values,
                    final_delta_limit=final_limit,
                    peak_delta_limit=peak_limit,
                )
                self.assertIs(summary["passed"], True)
                self.assertEqual(summary["finalDelta"], final_limit)
                self.assertEqual(summary["peakDelta"], peak_limit)

            final_failure = list(values)
            final_failure[-runner.FINAL_WINDOW_SAMPLE_COUNT:] = [
                baseline + final_limit + 1
            ] * runner.FINAL_WINDOW_SAMPLE_COUNT
            with self.subTest(label=label, boundary="final-plus-one"):
                self.assertIs(
                    runner.metric_summary(
                        final_failure,
                        final_delta_limit=final_limit,
                        peak_delta_limit=peak_limit,
                    )["passed"],
                    False,
                )

            peak_failure = list(values)
            peak_failure[50] = baseline + peak_limit + 1
            with self.subTest(label=label, boundary="peak-plus-one"):
                self.assertIs(
                    runner.metric_summary(
                        peak_failure,
                        final_delta_limit=final_limit,
                        peak_delta_limit=peak_limit,
                    )["passed"],
                    False,
                )

    def test_metric_summary_allows_a_negative_final_delta(self) -> None:
        values = [100] * runner.SAMPLE_COUNT
        values[-runner.FINAL_WINDOW_SAMPLE_COUNT:] = [90] * (
            runner.FINAL_WINDOW_SAMPLE_COUNT
        )
        summary = runner.metric_summary(
            values,
            final_delta_limit=0,
            peak_delta_limit=0,
        )
        self.assertEqual(summary["finalDelta"], -10)
        self.assertIs(summary["passed"], True)

    def test_measurement_summary_recomputes_all_metrics(self) -> None:
        records = sample_records()
        summary = runner.measurement_summary(records)
        self.assertEqual(
            set(summary),
            {"openFileDescriptors", "residentBytes", "threads"},
        )
        self.assertTrue(
            all(value["passed"] is True for value in summary.values())
        )

    def test_measurement_summary_rejects_schedule_shape_and_type_drift(
        self,
    ) -> None:
        records = sample_records()
        mutations: list[list[dict[str, object]]] = []
        mutations.append(records[:-1])
        mutations.append(records + [copy.deepcopy(records[-1])])
        for key, value in (
            ("ordinal", 2),
            ("ordinal", True),
            ("targetElapsedMilliseconds", 4_999),
            (
                "observedLatenessMilliseconds",
                runner.SAMPLE_LATENESS_LIMIT_MILLISECONDS + 1,
            ),
            ("residentBytes", True),
            ("openFileDescriptorCount", 0),
            ("threadCount", -1),
        ):
            mutation = copy.deepcopy(records)
            mutation[0][key] = value
            mutations.append(mutation)
        extra_key = copy.deepcopy(records)
        extra_key[0]["unexpected"] = True
        mutations.append(extra_key)
        for ordinal, mutation in enumerate(mutations, start=1):
            with self.subTest(mutation=ordinal):
                with self.assertRaises(runner.IdleResourceSmokeError):
                    runner.measurement_summary(mutation)

    def test_measurement_summary_rejects_each_budget_overrun(
        self,
    ) -> None:
        mutations = []
        resident = [100 * 1024 * 1024] * runner.SAMPLE_COUNT
        resident[-runner.FINAL_WINDOW_SAMPLE_COUNT:] = [
            resident[0] + runner.FINAL_RSS_DELTA_LIMIT_BYTES + 1
        ] * runner.FINAL_WINDOW_SAMPLE_COUNT
        mutations.append(sample_records(resident_values=resident))

        descriptors = [20] * runner.SAMPLE_COUNT
        descriptors[50] = 20 + runner.PEAK_FD_DELTA_LIMIT + 1
        mutations.append(
            sample_records(descriptor_values=descriptors)
        )

        threads = [8] * runner.SAMPLE_COUNT
        threads[-runner.FINAL_WINDOW_SAMPLE_COUNT:] = [
            8 + runner.FINAL_THREAD_DELTA_LIMIT + 1
        ] * runner.FINAL_WINDOW_SAMPLE_COUNT
        mutations.append(sample_records(thread_values=threads))
        for ordinal, mutation in enumerate(mutations, start=1):
            with self.subTest(metric=ordinal):
                with self.assertRaises(runner.IdleResourceSmokeError):
                    runner.measurement_summary(mutation)

    @unittest.skipUnless(
        sys.platform == "darwin",  # type: ignore[name-defined]
        "macOS libproc ABI",
    )
    def test_real_libproc_abi_and_current_process_sample(self) -> None:
        runner.validate_libproc_abi()
        process_path = runner.read_process_path(os.getpid())
        sample = runner.collect_resource_sample(
            os.getpid(),
            process_path,
        )
        self.assertGreater(sample.resident_bytes, 0)
        self.assertGreater(sample.thread_count, 0)
        self.assertGreater(sample.open_file_descriptor_count, 0)

    def test_task_resource_reader_rejects_short_or_zero_fields(self) -> None:
        with mock.patch.object(
            runner,
            "call_proc_pidinfo",
            return_value=95,
        ):
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.read_task_resources(123)

        def zero_fields(
            pid: int,
            flavor: int,
            buffer: object,
            buffer_size: int,
        ) -> int:
            del pid, flavor, buffer, buffer_size
            return 96

        with mock.patch.object(
            runner,
            "call_proc_pidinfo",
            side_effect=zero_fields,
        ):
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.read_task_resources(123)

    def test_fd_reader_uses_actual_bytes_and_rejects_invalid_rows(
        self,
    ) -> None:
        def valid_rows(
            pid: int,
            flavor: int,
            buffer: object | None,
            buffer_size: int,
        ) -> int:
            del pid, flavor, buffer_size
            if buffer is None:
                return 512
            buffer[0].fd = 0  # type: ignore[index]
            buffer[1].fd = 3  # type: ignore[index]
            buffer[2].fd = 9  # type: ignore[index]
            return 3 * runner.ctypes.sizeof(runner.ProcFDInfo)

        with mock.patch.object(
            runner,
            "call_proc_pidinfo",
            side_effect=valid_rows,
        ):
            self.assertEqual(
                runner.read_open_file_descriptor_count(123),
                3,
            )

        def duplicate_rows(
            pid: int,
            flavor: int,
            buffer: object | None,
            buffer_size: int,
        ) -> int:
            del pid, flavor, buffer_size
            if buffer is None:
                return 16
            buffer[0].fd = 4  # type: ignore[index]
            buffer[1].fd = 4  # type: ignore[index]
            return 16

        with mock.patch.object(
            runner,
            "call_proc_pidinfo",
            side_effect=duplicate_rows,
        ):
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.read_open_file_descriptor_count(123)

        with mock.patch.object(
            runner,
            "call_proc_pidinfo",
            side_effect=(16, 7),
        ):
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.read_open_file_descriptor_count(123)

    def test_fd_reader_doubles_a_full_buffer_and_has_a_hard_ceiling(
        self,
    ) -> None:
        calls = 0

        def one_full_then_rows(
            pid: int,
            flavor: int,
            buffer: object | None,
            buffer_size: int,
        ) -> int:
            nonlocal calls
            del pid, flavor
            if buffer is None:
                return 16
            calls += 1
            if calls == 1:
                return buffer_size
            buffer[0].fd = 0  # type: ignore[index]
            return runner.ctypes.sizeof(runner.ProcFDInfo)

        with mock.patch.object(
            runner,
            "call_proc_pidinfo",
            side_effect=one_full_then_rows,
        ):
            self.assertEqual(
                runner.read_open_file_descriptor_count(123),
                1,
            )
        self.assertEqual(calls, 2)

        def always_full(
            pid: int,
            flavor: int,
            buffer: object | None,
            buffer_size: int,
        ) -> int:
            del pid, flavor
            return 16 if buffer is None else buffer_size

        with mock.patch.object(
            runner,
            "call_proc_pidinfo",
            side_effect=always_full,
        ):
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.read_open_file_descriptor_count(123)

    def test_collect_sample_rejects_libproc_path_drift(self) -> None:
        expected = Path("/tmp/expected/AetherLink")
        with mock.patch.object(
            runner,
            "read_process_path",
            return_value=Path("/tmp/replaced/AetherLink"),
        ):
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.collect_resource_sample(123, expected)

    def test_ready_identity_checks_appkit_and_libproc(self) -> None:
        executable = Path("/tmp/AetherLink.app/Contents/MacOS/AetherLink")
        process = FakeProcess()
        status = ready_status(executable)
        self.assertEqual(
            runner.validate_ready_identity(
                process,  # type: ignore[arg-type]
                executable,
                query=lambda pid: status,
                path_reader=lambda pid: executable.resolve(),
            ),
            status,
        )
        for label, query, path_reader in (
            (
                "missing",
                lambda pid: None,
                lambda pid: executable.resolve(),
            ),
            (
                "wrong-path",
                lambda pid: status,
                lambda pid: Path("/tmp/other"),
            ),
            (
                "not-ready",
                lambda pid: runner.engine.ApplicationStatus(
                    activation_policy=0,
                    bundle_identifier=runner.engine.EXPECTED_BUNDLE_ID,
                    executable_path=str(executable),
                    finished_launching=False,
                ),
                lambda pid: executable.resolve(),
            ),
        ):
            with self.subTest(label=label):
                with self.assertRaises(runner.IdleResourceSmokeError):
                    runner.validate_ready_identity(
                        process,  # type: ignore[arg-type]
                        executable,
                        query=query,
                        path_reader=path_reader,
                    )

    def run_fake_observation(
        self,
        *,
        process: FakeProcess | None = None,
        sample_delay_nanoseconds: int = 0,
    ) -> tuple[dict[str, object], FakeProcess, list[int]]:
        executable = Path("/tmp/AetherLink.app/Contents/MacOS/AetherLink")
        fake_process = process or FakeProcess()
        clock = FakeClock()
        termination_targets: list[int] = []

        def sampler(pid: int, expected: Path) -> runner.ResourceSample:
            self.assertEqual(pid, fake_process.pid)
            self.assertEqual(expected, executable)
            clock.advance(sample_delay_nanoseconds)
            return runner.ResourceSample(
                open_file_descriptor_count=20,
                resident_bytes=100 * 1024 * 1024,
                thread_count=8,
            )

        def request(
            pid: int,
            expected: Path,
            *,
            force: bool,
        ) -> bool:
            self.assertEqual(expected, executable)
            self.assertIs(force, False)
            termination_targets.append(pid)
            return True

        owned: list[tuple[subprocess.Popen[bytes], Path]] = []
        result = runner.run_owned_idle_observation(
            executable=executable,
            profile="sandbox",
            environment={},
            working_directory=Path("/tmp"),
            readiness_timeout_seconds=1.0,
            termination_timeout_seconds=1.0,
            owned_processes=owned,
            popen_factory=lambda *args, **kwargs: fake_process,  # type: ignore[arg-type]
            readiness_waiter=lambda *args, **kwargs: ready_status(executable),
            query=lambda pid: ready_status(executable),
            path_reader=lambda pid: executable.resolve(),
            sampler=sampler,
            request_termination=request,
            gone_waiter=lambda *args, **kwargs: True,
            monotonic_ns=clock.monotonic_ns,
            sleeper=clock.sleep,
        )
        self.assertEqual(owned, [])
        return result, fake_process, termination_targets

    def test_owned_observation_collects_120_samples_and_only_owns_its_pid(
        self,
    ) -> None:
        result, process, targets = self.run_fake_observation()
        self.assertEqual(len(result["samples"]), runner.SAMPLE_COUNT)
        self.assertEqual(
            result["samples"][-1]["targetElapsedMilliseconds"],
            runner.OBSERVATION_MILLISECONDS,
        )
        self.assertEqual(targets, [process.pid])
        self.assertNotIn(59809, targets)
        self.assertIs(result["processReaped"], True)
        self.assertIs(result["processIdentifierRetained"], False)

    def test_owned_observation_accepts_lateness_limit_and_rejects_plus_one(
        self,
    ) -> None:
        result, _, _ = self.run_fake_observation(
            sample_delay_nanoseconds=(
                runner.SAMPLE_LATENESS_LIMIT_MILLISECONDS * 1_000_000
            )
        )
        self.assertEqual(
            result["maximumObservedLatenessMilliseconds"],
            runner.SAMPLE_LATENESS_LIMIT_MILLISECONDS,
        )
        with self.assertRaises(runner.IdleResourceSmokeError):
            self.run_fake_observation(
                sample_delay_nanoseconds=(
                    (
                        runner.SAMPLE_LATENESS_LIMIT_MILLISECONDS
                        + 1
                    )
                    * 1_000_000
                )
            )

    def test_owned_observation_fails_closed_on_early_exit(self) -> None:
        process = FakeProcess(exit_after_polls=3)
        with self.assertRaises(runner.IdleResourceSmokeError):
            self.run_fake_observation(process=process)

    def test_cleanup_targets_only_the_owned_popen_pid(self) -> None:
        executable = Path("/tmp/owned/AetherLink")
        process = FakeProcess(pid=777)
        targets: list[int] = []

        def requester(
            pid: int,
            expected: Path,
            *,
            force: bool,
        ) -> bool:
            self.assertEqual(expected, executable)
            self.assertIs(force, False)
            targets.append(pid)
            return True

        runner.cleanup_owned_child(
            process,  # type: ignore[arg-type]
            executable,
            timeout_seconds=1.0,
            query=lambda pid: ready_status(executable),
            path_reader=lambda pid: executable.resolve(),
            request_termination=requester,
        )
        self.assertEqual(targets, [777])
        self.assertNotIn(59809, targets)
        self.assertFalse(process.killed)

    def test_isolated_root_ignores_preexisting_apps_outside_its_root(
        self,
    ) -> None:
        preexisting = runner.installed.RunningApplication(
            activation_policy=0,
            bundle_identifier=runner.engine.EXPECTED_BUNDLE_ID,
            executable_path=(
                "/Users/example/Desktop/project/dist/"
                "AetherLink.app/Contents/MacOS/AetherLink"
            ),
            finished_launching=True,
            pid=59809,
        )
        retained_path: Path | None = None
        with runner.isolated_resource_root(
            termination_timeout_seconds=1.0,
            lister=lambda: (preexisting,),
        ) as (temporary_root, owned):
            retained_path = temporary_root
            self.assertEqual(owned, [])
            (temporary_root / "probe").write_text(
                "temporary",
                encoding="utf-8",
            )
        self.assertIsNotNone(retained_path)
        self.assertFalse(retained_path.exists())  # type: ignore[union-attr]

    def test_isolated_root_never_terminates_an_unowned_temp_process(
        self,
    ) -> None:
        observed_root: Path | None = None

        def lister() -> tuple[runner.installed.RunningApplication, ...]:
            if observed_root is None:
                return ()
            return (
                runner.installed.RunningApplication(
                    activation_policy=0,
                    bundle_identifier=runner.engine.EXPECTED_BUNDLE_ID,
                    executable_path=str(
                        observed_root / "unknown/AetherLink"
                    ),
                    finished_launching=True,
                    pid=999,
                ),
            )

        try:
            with self.assertRaises(runner.IdleResourceSmokeError):
                with runner.isolated_resource_root(
                    termination_timeout_seconds=1.0,
                    lister=lister,
                ) as (temporary_root, owned):
                    observed_root = temporary_root
                    self.assertEqual(owned, [])
            self.assertIsNotNone(observed_root)
            self.assertTrue(observed_root.exists())  # type: ignore[union-attr]
        finally:
            if observed_root is not None and observed_root.is_dir():
                shutil.rmtree(observed_root)

    def test_build_result_recomputes_summary_and_rejects_bool_ints(
        self,
    ) -> None:
        version = runner.recovery.ReleaseVersion(
            build_number=24,
            marketing_version="1.0.0",
            semantic_version=(1, 0, 0),
        )
        release = runner.engine.ReleaseInputs(
            archive_dir=Path("/tmp/archive"),
            archive_path=Path("/tmp/archive/archive.zip"),
            manifest_path=Path("/tmp/archive/manifest.json"),
            checksum_path=Path("/tmp/archive/archive.zip.sha256"),
            archive_sha256=(
                runner.EXPECTED_BUILD24_RELEASE_FILES[
                    "aetherlink-1.0.0+24-local-v1.zip"
                ]["sha256"]
            ),
            manifest_sha256=(
                runner.EXPECTED_BUILD24_RELEASE_FILES[
                    "aetherlink-1.0.0+24-local-v1.manifest.json"
                ]["sha256"]
            ),
            manifest={},
        )
        run = valid_run()
        with (
            mock.patch.object(
                runner.platform,
                "mac_ver",
                return_value=("26.5.2", ("", "", ""), ""),
            ),
            mock.patch.object(
                runner.platform,
                "machine",
                return_value="arm64",
            ),
            mock.patch.object(runner.os, "cpu_count", return_value=10),
            mock.patch.object(runner.os, "sysconf", return_value=16_384),
        ):
            result = runner.build_result(
                version=version,
                release=release,
                artifact={"appTree": {}},
                snapshot_files=copy.deepcopy(
                    runner.EXPECTED_BUILD24_RELEASE_FILES
                ),
                run=run,
                preexisting_application_count=1,
            )
            self.assertEqual(result["status"], "passed")
            self.assertIs(result["repeatability"]["performed"], False)
            self.assertEqual(result["limitations"], list(runner.LIMITATIONS))

            for key, value in (
                ("activationPolicy", False),
                ("exitCode", False),
                ("maximumObservedLatenessMilliseconds", True),
                ("processReaped", 1),
            ):
                mutation = copy.deepcopy(run)
                mutation[key] = value
                with self.subTest(key=key):
                    with self.assertRaises(
                        runner.IdleResourceSmokeError
                    ):
                        runner.build_result(
                            version=version,
                            release=release,
                            artifact={"appTree": {}},
                            snapshot_files=copy.deepcopy(
                                runner.EXPECTED_BUILD24_RELEASE_FILES
                            ),
                            run=mutation,
                            preexisting_application_count=1,
                        )

            summary_mutation = copy.deepcopy(run)
            summary_mutation["summary"]["threads"]["maximum"] += 1
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.build_result(
                    version=version,
                    release=release,
                    artifact={"appTree": {}},
                    snapshot_files=copy.deepcopy(
                        runner.EXPECTED_BUILD24_RELEASE_FILES
                    ),
                    run=summary_mutation,
                    preexisting_application_count=1,
                )

            for metric, field, value in (
                ("threads", "finalDelta", False),
                ("threads", "peakDelta", False),
                ("threads", "passed", 1),
            ):
                summary_type_mutation = copy.deepcopy(run)
                summary_type_mutation["summary"][metric][field] = value
                with self.subTest(metric=metric, field=field):
                    with self.assertRaises(
                        runner.IdleResourceSmokeError
                    ):
                        runner.build_result(
                            version=version,
                            release=release,
                            artifact={"appTree": {}},
                            snapshot_files=copy.deepcopy(
                                runner.EXPECTED_BUILD24_RELEASE_FILES
                            ),
                            run=summary_type_mutation,
                            preexisting_application_count=1,
                        )

    def test_publish_result_is_create_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            result = {"schemaVersion": 1, "status": "passed"}
            runner.publish_result(path, result)
            first = path.read_bytes()
            runner.publish_result(path, result)
            self.assertEqual(path.read_bytes(), first)
            with self.assertRaises(runner.IdleResourceSmokeError):
                runner.publish_result(
                    path,
                    {"schemaVersion": 1, "status": "failed"},
                )

    def test_source_uses_no_broad_process_or_signing_command(self) -> None:
        source_path = (
            runner.ROOT
            / "script/run_macos_build24_idle_resource_stability_smoke.py"
        )
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)
        imported_names = {
            alias.name
            for node in ast.walk(module)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("psutil", imported_names)
        for token in (
            "killall",
            "pkill",
            "lsof",
            "codesign",
            "verify_archive_readback",
            "cleanup_exact_temporary_applications",
        ):
            self.assertNotIn(token, source)
        self.assertIn("process.kill()", source)
        self.assertIn("installed.assert_preexisting_applications_preserved", source)


if __name__ == "__main__":
    unittest.main()
