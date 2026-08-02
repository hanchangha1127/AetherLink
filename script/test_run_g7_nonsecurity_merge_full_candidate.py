#!/usr/bin/env python3
"""Tests for the local G7 non-security Merge-full candidate producer."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

from script import run_g7_nonsecurity_merge_full_candidate as module


class G7NonsecurityMergeFullCandidateProducerTests(unittest.TestCase):
    def test_canonical_json_is_ascii_sorted_and_rejects_nan(self) -> None:
        self.assertEqual(
            module.canonical_json_bytes({"z": "한", "a": 1}),
            b'{"a":1,"z":"\\ud55c"}\n',
        )
        with self.assertRaises(module.CandidateError):
            module.canonical_json_bytes({"bad": float("nan")})

    def test_source_snapshot_binds_path_mode_size_and_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "a.txt"
            second = root / "nested/b.txt"
            second.parent.mkdir()
            first.write_bytes(b"one\n")
            second.write_bytes(b"two\n")
            os.chmod(first, 0o640)
            os.chmod(second, 0o600)
            paths = (Path("nested/b.txt"), Path("a.txt"))
            before = module.source_snapshot(root=root, paths=paths)
            self.assertEqual(before["algorithm"], module.SOURCE_ALGORITHM)
            self.assertEqual(before["fileCount"], 2)
            self.assertEqual(before["size"], 8)
            self.assertRegex(str(before["sha256"]), r"^[0-9a-f]{64}$")

            second.write_bytes(b"changed\n")
            after = module.source_snapshot(root=root, paths=paths)
            self.assertNotEqual(before, after)

    def test_stable_file_record_rejects_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.write_bytes(b"value")
            (root / "link").symlink_to(source)
            with self.assertRaises(module.CandidateError):
                module.stable_file_record(Path("link"), root=root)
            os.link(source, root / "hardlink")
            with self.assertRaises(module.CandidateError):
                module.stable_file_record(Path("source"), root=root)

    def test_run_gate_records_output_and_publishes_requested_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gate = module.Gate(
                "fixture",
                (
                    sys.executable,
                    "-c",
                    "import sys; print('ok'); print('note', file=sys.stderr)",
                ),
                10,
                Path("out/result.txt"),
            )
            record, stdout, stderr = module.run_gate(gate, root=root)
            self.assertEqual(record["exitCode"], 0)
            self.assertEqual(record["id"], "fixture")
            self.assertEqual(record["stdout"], module.output_identity(stdout))
            self.assertEqual(record["stderr"], module.output_identity(stderr))
            self.assertEqual((root / "out/result.txt").read_bytes(), b"ok\n")
            self.assertEqual(
                stat.S_IMODE((root / "out/result.txt").stat().st_mode),
                0o600,
            )

    def test_run_gate_rejects_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            gate = module.Gate(
                "failure",
                (sys.executable, "-c", "raise SystemExit(7)"),
                10,
            )
            with self.assertRaisesRegex(module.CandidateError, "exited 7"):
                module.run_gate(gate, root=Path(temporary))

    def test_package_gate_uses_managed_release_scratch_lifecycle(self) -> None:
        gate = module.Gate(
            "macos-unsealed-package-produce",
            module.MACOS_UNSEALED_PACKAGE_COMMAND,
            2400,
        )
        root = Path("/fixture/repository")
        environment = {"FIXTURE": "value"}
        events: list[str] = []

        @contextmanager
        def fake_lock():
            events.append("lock-enter")
            try:
                yield
            finally:
                events.append("lock-exit")

        def fake_create(run_id: str) -> None:
            self.assertEqual(run_id, "g7-" + "a" * 32)
            events.append("lease-create")

        def fake_cleanup(run_id: str, *, remove_lease: bool) -> None:
            self.assertEqual(run_id, "g7-" + "a" * 32)
            self.assertTrue(remove_lease)
            events.append("scratch-cleanup")

        def fake_run(observed_gate, **kwargs):
            self.assertIs(observed_gate, gate)
            self.assertEqual(
                observed_gate.argv,
                (
                    "/usr/bin/env",
                    "AETHERLINK_REPRO_SWIFT_SCRATCH_PATH="
                    "/private/tmp/aetherlink-g6-swift-scratch-v1",
                    "./script/build_and_run.sh",
                    "--unsealed-package-only",
                ),
            )
            self.assertEqual(kwargs, {"root": root, "environment": environment})
            events.append("gate-run")
            return ({"id": observed_gate.identifier}, b"ok\n", b"")

        fixed_uuid = mock.Mock(hex="a" * 32)
        with mock.patch.object(
            module.release_repro, "acquire_run_lock", side_effect=fake_lock
        ), mock.patch.object(
            module.release_repro, "create_swift_lease", side_effect=fake_create
        ), mock.patch.object(
            module.release_repro, "cleanup_swift_scratch", side_effect=fake_cleanup
        ), mock.patch.object(
            module.uuid, "uuid4", return_value=fixed_uuid
        ), mock.patch.object(
            module.os.path, "lexists", return_value=False
        ), mock.patch.object(
            module, "run_gate", side_effect=fake_run
        ):
            record, stdout, stderr = module.run_gate_with_managed_release_scratch(
                gate,
                root=root,
                environment=environment,
            )

        self.assertEqual(record, {"id": gate.identifier})
        self.assertEqual((stdout, stderr), (b"ok\n", b""))
        self.assertEqual(
            events,
            [
                "lock-enter",
                "lease-create",
                "gate-run",
                "scratch-cleanup",
                "lock-exit",
            ],
        )

    def test_unrelated_gate_does_not_acquire_or_leak_release_scratch(self) -> None:
        gate = module.Gate("unrelated", ("fixture", "--flag"), 10)
        environment = {"FIXTURE": "value"}
        expected = ({"id": gate.identifier}, b"ok\n", b"")
        with mock.patch.object(
            module.release_repro, "acquire_run_lock"
        ) as acquire, mock.patch.object(
            module.release_repro, "create_swift_lease"
        ) as create, mock.patch.object(
            module.release_repro, "cleanup_swift_scratch"
        ) as cleanup, mock.patch.object(
            module, "run_gate", return_value=expected
        ) as run:
            observed = module.run_gate_with_managed_release_scratch(
                gate,
                root=Path("/fixture/repository"),
                environment=environment,
            )

        self.assertEqual(observed, expected)
        acquire.assert_not_called()
        create.assert_not_called()
        cleanup.assert_not_called()
        run.assert_called_once_with(
            gate,
            root=Path("/fixture/repository"),
            environment=environment,
        )
        self.assertEqual(gate.argv, ("fixture", "--flag"))
        self.assertNotIn(module.MACOS_RELEASE_SCRATCH_ENVIRONMENT, environment)

    def test_existing_or_broken_link_scratch_fails_before_subprocess(self) -> None:
        gate = module.Gate(
            "macos-unsealed-package-produce",
            module.MACOS_UNSEALED_PACKAGE_COMMAND,
            2400,
        )
        for scratch_kind in ("directory", "broken-symlink"):
            with self.subTest(scratch_kind=scratch_kind), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                scratch = base / "swift-scratch"
                lease = base / "swift-lease.json"
                if scratch_kind == "directory":
                    scratch.mkdir()
                else:
                    scratch.symlink_to(base / "missing-target")

                with mock.patch.object(
                    module, "MACOS_RELEASE_SCRATCH_PATH", scratch
                ), mock.patch.object(
                    module.release_repro, "SWIFT_SCRATCH", scratch
                ), mock.patch.object(
                    module.release_repro, "SWIFT_LEASE_PATH", lease
                ), mock.patch.object(
                    module.release_repro, "acquire_run_lock", return_value=mock.MagicMock()
                ), mock.patch.object(
                    module.release_repro, "create_swift_lease"
                ) as create, mock.patch.object(
                    module.release_repro, "cleanup_swift_scratch"
                ) as cleanup, mock.patch.object(
                    module, "run_gate"
                ) as run:
                    with self.assertRaisesRegex(
                        module.CandidateError,
                        "fixed Swift Release scratch already exists",
                    ):
                        module.run_gate_with_managed_release_scratch(
                            gate,
                            root=base,
                            environment={},
                        )

                create.assert_not_called()
                cleanup.assert_not_called()
                run.assert_not_called()

    def test_package_gate_failure_still_cleans_managed_scratch(self) -> None:
        gate = module.Gate(
            "macos-unsealed-package-produce",
            module.MACOS_UNSEALED_PACKAGE_COMMAND,
            2400,
        )
        events: list[str] = []

        @contextmanager
        def fake_lock():
            events.append("lock-enter")
            try:
                yield
            finally:
                events.append("lock-exit")

        with mock.patch.object(
            module.release_repro, "acquire_run_lock", side_effect=fake_lock
        ), mock.patch.object(
            module.release_repro,
            "create_swift_lease",
            side_effect=lambda _run_id: events.append("lease-create"),
        ), mock.patch.object(
            module.release_repro,
            "cleanup_swift_scratch",
            side_effect=lambda _run_id, *, remove_lease: events.append(
                f"scratch-cleanup-{remove_lease}"
            ),
        ), mock.patch.object(
            module.os.path, "lexists", return_value=False
        ), mock.patch.object(
            module,
            "run_gate",
            side_effect=lambda *_args, **_kwargs: (
                events.append("gate-run"),
                (_ for _ in ()).throw(module.CandidateError("fixture failure")),
            )[-1],
        ):
            with self.assertRaisesRegex(module.CandidateError, "fixture failure"):
                module.run_gate_with_managed_release_scratch(gate)

        self.assertEqual(
            events,
            [
                "lock-enter",
                "lease-create",
                "gate-run",
                "scratch-cleanup-True",
                "lock-exit",
            ],
        )

    def test_lint_result_requires_zero_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lint = root / "apps/android/app/build/reports/lint-results-release.xml"
            lint.parent.mkdir(parents=True)
            lint.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n<issues/>\n')
            module.validate_zero_lint_issues(root=root)
            lint.write_bytes(
                b'<?xml version="1.0" encoding="UTF-8"?>\n'
                b'<issues><issue id="UseKtx" severity="Warning"/></issues>\n'
            )
            with self.assertRaisesRegex(module.CandidateError, "UseKtx:Warning"):
                module.validate_zero_lint_issues(root=root)

    def test_pid_record_is_closed_for_requested_and_unrequested_modes(self) -> None:
        self.assertEqual(
            module.pid_record(None, "", ""),
            {
                "after": "",
                "before": "",
                "pid": 0,
                "preservedDuringRun": False,
                "requested": False,
            },
        )
        self.assertEqual(
            module.pid_record(9, "same", "same"),
            {
                "after": "same",
                "before": "same",
                "pid": 9,
                "preservedDuringRun": True,
                "requested": True,
            },
        )

    def test_parent_is_published_last_and_old_parent_survives_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lint_relative = Path(
                "apps/android/app/build/reports/lint-results-release.xml"
            )
            lint = root / lint_relative
            lint.parent.mkdir(parents=True)
            lint.write_bytes(b"<issues/>\n")
            implementation_relative = Path("script/fixture.py")
            implementation = root / implementation_relative
            implementation.parent.mkdir(parents=True)
            implementation.write_bytes(b"# fixture\n")
            result = root / module.RESULT_RELATIVE_PATH
            result.parent.mkdir(parents=True)
            result.write_bytes(b"old-parent\n")

            gates = (
                module.Gate("macos-release-source-before", ("fixture",), 1),
                module.Gate("android-release-build", ("fixture",), 1),
                module.Gate("macos-release-source-after", ("fixture",), 1),
            )
            digest = "a" * 64

            def fake_run_gate(gate, **_kwargs):
                stdout = (digest + "\n").encode("ascii") if "source" in gate.identifier else b"ok\n"
                return (
                    {
                        "argv": list(gate.argv),
                        "cwd": ".",
                        "elapsedMilliseconds": 1,
                        "exitCode": 0,
                        "id": gate.identifier,
                        "stderr": module.output_identity(b""),
                        "stdout": module.output_identity(stdout),
                        "timeoutSeconds": gate.timeout_seconds,
                    },
                    stdout,
                    b"",
                )

            snapshot = {
                "algorithm": module.SOURCE_ALGORITHM,
                "fileCount": 1,
                "sha256": "b" * 64,
                "size": 10,
            }
            with mock.patch.object(module, "ALL_GATES", gates), mock.patch.object(
                module, "ARTIFACT_PATHS", (lint_relative,)
            ), mock.patch.object(
                module, "IMPLEMENTATION_PATHS", (implementation_relative,)
            ), mock.patch.object(
                module, "source_snapshot", return_value=snapshot
            ), mock.patch.object(
                module, "run_gate", side_effect=fake_run_gate
            ), mock.patch.object(
                module, "process_identity", return_value="same identity"
            ):
                payload = module.produce_candidate(
                    root=root,
                    result_path=result,
                    preserve_pid=9,
                )
            self.assertEqual(payload["result"], "passed")
            raw = result.read_bytes()
            self.assertEqual(raw, module.canonical_json_bytes(json.loads(raw)))
            self.assertEqual(stat.S_IMODE(result.stat().st_mode), 0o600)

            result.write_bytes(b"known-good-parent\n")
            snapshots = iter((snapshot, {**snapshot, "sha256": "c" * 64}))
            with mock.patch.object(module, "ALL_GATES", gates), mock.patch.object(
                module, "ARTIFACT_PATHS", (lint_relative,)
            ), mock.patch.object(
                module, "IMPLEMENTATION_PATHS", (implementation_relative,)
            ), mock.patch.object(
                module, "source_snapshot", side_effect=snapshots
            ), mock.patch.object(
                module, "run_gate", side_effect=fake_run_gate
            ), mock.patch.object(
                module, "process_identity", return_value="same identity"
            ):
                with self.assertRaisesRegex(module.CandidateError, "source changed"):
                    module.produce_candidate(
                        root=root,
                        result_path=result,
                        preserve_pid=9,
                    )
            self.assertEqual(result.read_bytes(), b"known-good-parent\n")

    def test_producer_output_parents_are_recreated_immediately_at_mode_0700(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lint_relative = Path(
                "apps/android/app/build/reports/lint-results-release.xml"
            )
            lint = root / lint_relative
            lint.parent.mkdir(parents=True)
            lint.write_bytes(b"<issues/>\n")
            implementation_relative = Path("script/fixture.py")
            implementation = root / implementation_relative
            implementation.parent.mkdir(parents=True)
            implementation.write_bytes(b"# fixture\n")
            result = root / module.RESULT_RELATIVE_PATH
            gates = tuple(
                module.Gate(identifier, ("fixture",), 1)
                for identifier in (
                    "android-diagnostics-produce",
                    "macos-diagnostics-produce",
                    "macos-lifecycle-produce",
                )
            )
            for relative in set(module.OUTPUT_PARENT_BY_PRODUCER_ID.values()):
                path = root / relative
                path.mkdir(parents=True)
                os.chmod(path, 0o755)

            observations: list[tuple[str, int]] = []

            def fake_run_managed(gate, **_kwargs):
                parent = root / module.OUTPUT_PARENT_BY_PRODUCER_ID[gate.identifier]
                self.assertTrue(parent.is_dir())
                self.assertFalse(parent.is_symlink())
                observations.append(
                    (gate.identifier, stat.S_IMODE(parent.stat().st_mode))
                )
                parent.rmdir()
                return (
                    {
                        "argv": list(gate.argv),
                        "cwd": ".",
                        "elapsedMilliseconds": 1,
                        "exitCode": 0,
                        "id": gate.identifier,
                        "stderr": module.output_identity(b""),
                        "stdout": module.output_identity(b"ok\n"),
                        "timeoutSeconds": gate.timeout_seconds,
                    },
                    b"ok\n",
                    b"",
                )

            snapshot = {
                "algorithm": module.SOURCE_ALGORITHM,
                "fileCount": 1,
                "sha256": "b" * 64,
                "size": 10,
            }
            with mock.patch.object(module, "ALL_GATES", gates), mock.patch.object(
                module, "ARTIFACT_PATHS", (lint_relative,)
            ), mock.patch.object(
                module, "IMPLEMENTATION_PATHS", (implementation_relative,)
            ), mock.patch.object(
                module, "source_snapshot", return_value=snapshot
            ), mock.patch.object(
                module,
                "run_gate_with_managed_release_scratch",
                side_effect=fake_run_managed,
            ), mock.patch.object(
                module, "process_identity", return_value="same identity"
            ):
                payload = module.produce_candidate(
                    root=root,
                    result_path=result,
                    preserve_pid=9,
                )

            self.assertEqual(payload["result"], "passed")
            self.assertEqual(
                observations,
                [(gate.identifier, 0o700) for gate in gates],
            )


if __name__ == "__main__":
    unittest.main()
