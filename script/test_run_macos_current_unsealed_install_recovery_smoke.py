#!/usr/bin/env python3
"""Tests for current-source unsealed macOS install/recovery evidence."""

from __future__ import annotations

import copy
import hashlib
import math
import os
from pathlib import Path
import signal
import struct
import tempfile
import unittest
from unittest.mock import patch

from script import run_macos_current_unsealed_install_recovery_smoke as smoke


class CurrentUnsealedInstallRecoveryTests(unittest.TestCase):
    MACHO_FIXTURE_SIGNATURE_OFFSET = 4_112

    def signed_macho_fixture(self) -> tuple[bytes, str]:
        signature_offset = self.MACHO_FIXTURE_SIGNATURE_OFFSET
        identifier = smoke.CODE_DIRECTORY_IDENTIFIER
        hash_offset = smoke.CODE_DIRECTORY_HEADER_SIZE + len(identifier)
        code_directory_size = (
            hash_offset + 2 * smoke.CODE_DIRECTORY_SHA256_HASH_SIZE
        )
        superblob_size = 20 + code_directory_size
        signature_size = superblob_size + 1
        mach_header = struct.pack(
            "<IiiIIIII",
            smoke.MACHO_64_MAGIC,
            smoke.MACHO_CPU_TYPE_ARM64,
            0,
            smoke.MACHO_FILE_TYPE_EXECUTE,
            1,
            16,
            0x200085,
            0,
        )
        code_signature_command = struct.pack(
            "<IIII",
            smoke.MACHO_LOAD_COMMAND_CODE_SIGNATURE,
            16,
            signature_offset,
            signature_size,
        )
        code_bytes = (mach_header + code_signature_command).ljust(
            signature_offset, b"\x00"
        )
        page_size = 1 << smoke.CODE_DIRECTORY_PAGE_SIZE_EXPONENT
        page_hashes = b"".join(
            hashlib.sha256(code_bytes[offset : offset + page_size]).digest()
            for offset in range(0, signature_offset, page_size)
        )
        code_directory = (
            struct.pack(
                ">9I4BI",
                smoke.CODE_SIGNATURE_CODE_DIRECTORY_MAGIC,
                code_directory_size,
                smoke.CODE_DIRECTORY_VERSION_EXEC_SEGMENT,
                smoke.CODE_DIRECTORY_FLAGS_LINKER_ADHOC,
                hash_offset,
                smoke.CODE_DIRECTORY_HEADER_SIZE,
                0,
                2,
                signature_offset,
                smoke.CODE_DIRECTORY_SHA256_HASH_SIZE,
                smoke.CODE_DIRECTORY_SHA256_HASH_TYPE,
                0,
                smoke.CODE_DIRECTORY_PAGE_SIZE_EXPONENT,
                0,
            )
            + struct.pack(
                ">IIIQQQQ",
                0,
                0,
                0,
                0,
                0,
                signature_offset,
                1,
            )
            + identifier
            + page_hashes
        )
        self.assertEqual(len(code_directory), code_directory_size)
        signature = (
            struct.pack(
                ">III",
                smoke.CODE_SIGNATURE_SUPERBLOB_MAGIC,
                superblob_size,
                1,
            )
            + struct.pack(
                ">II",
                smoke.CODE_SIGNATURE_PRIMARY_CODE_DIRECTORY_SLOT,
                20,
            )
            + code_directory
            + b"\x00"
        )
        self.assertEqual(len(signature), signature_size)
        return (
            code_bytes + signature,
            hashlib.sha256(code_directory).digest()[:20].hex(),
        )

    def identity(self, marker: str, *, files: int = 1) -> dict[str, object]:
        return {
            "fileCount": files,
            "sha256": hashlib.sha256(marker.encode()).hexdigest(),
            "size": len(marker),
        }

    def run_record(self, ordinal: int) -> dict[str, object]:
        return {
            "activationPolicy": 0,
            "appKitBundleIdentifierPolicy": (
                smoke.APPKIT_BUNDLE_IDENTIFIER_POLICY
            ),
            "appKitExecutablePathMatched": True,
            "exitCode": 0,
            "finishedLaunching": True,
            "minimumObservationSeconds": 5.0,
            "observationDeadlineReached": True,
            "ordinal": ordinal,
            "ownedChildProcessCaptured": True,
            "terminationAccepted": True,
        }

    def abrupt_run_record(self) -> dict[str, object]:
        return {
            "activationPolicy": 0,
            "appKitBundleIdentifierPolicy": (
                smoke.APPKIT_BUNDLE_IDENTIFIER_POLICY
            ),
            "appKitExecutablePathMatched": True,
            "appKitProcessAbsentAfterReap": True,
            "capturedLogsRevalidatedAfterReap": True,
            "exactExecutableIdentityMatchedImmediatelyBeforeSignal": True,
            "exitCode": -smoke.SIGKILL_NUMBER,
            "finishedLaunching": True,
            "installedExecutableDescriptorHeldAcrossSignal": True,
            "launchMethod": smoke.ABRUPT_LAUNCH_METHOD,
            "minimumObservationSeconds": 5.0,
            "observationDeadlineReached": True,
            "ordinal": 2,
            "ownedChildProcessCaptured": True,
            "pathIdentityStableAcrossSignal": True,
            "persistenceProbePassedBeforeSignal": True,
            "processReaped": True,
            "runningExecutableCodeIdentityMatchedHeldBytes": True,
            "signalName": "SIGKILL",
            "signalNumber": smoke.SIGKILL_NUMBER,
        }

    def exercise_failing_abrupt_cycle(
        self,
        *,
        running_code_identities: tuple[str, ...],
        late_stderr: bytes = b"",
    ) -> None:
        class Process:
            pid = 4343

            def __init__(self) -> None:
                self.returncode: int | None = None
                self.stderr: object | None = None

            def poll(self) -> int | None:
                return self.returncode

            def send_signal(self, _sent_signal: int) -> None:
                return None

            def wait(self, timeout: float) -> int:
                del timeout
                if late_stderr and self.returncode is None:
                    assert self.stderr is not None
                    self.stderr.write(late_stderr)
                    self.stderr.flush()
                self.returncode = -signal.SIGKILL
                return self.returncode

        process = Process()
        code_identities = iter(running_code_identities)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "AetherLink.app"
            executable = app / smoke.installed.EXECUTABLE_RELATIVE_PATH
            executable.parent.mkdir(parents=True)
            executable_payload = b"fixture-executable"
            executable.write_bytes(executable_payload)
            executable.chmod(0o755)
            logs = root / "logs"
            logs.mkdir()

            def popen_factory(*args: object, **kwargs: object) -> Process:
                del args
                stdout = kwargs["stdout"]
                stdout.write(
                    smoke.recovery.expected_observation_line(
                        smoke.recovery.SQLITE_READBACK_MODE
                    )
                )
                stdout.flush()
                process.stderr = kwargs["stderr"]
                return process

            smoke.run_owned_abrupt_recovery_cycle(
                ordinal=2,
                app_path=app,
                profile="fixture-profile",
                environment={},
                log_directory=logs,
                readiness_timeout_seconds=1,
                observation_seconds=5,
                termination_timeout_seconds=1,
                persistence_probe=lambda: None,
                expected_executable_bytes=executable_payload,
                popen_factory=popen_factory,
                readiness_waiter=lambda *args, **kwargs: (
                    smoke.DirectOwnedApplicationStatus(
                        activation_policy=0,
                        bundle_identifier_state="expected",
                        executable_path=str(executable),
                        finished_launching=True,
                    )
                ),
                status_reader=lambda _pid, _executable: (
                    smoke.DirectOwnedApplicationStatus(
                        activation_policy=0,
                        bundle_identifier_state="expected",
                        executable_path=str(executable),
                        finished_launching=True,
                    )
                ),
                absence_waiter=lambda *args, **kwargs: True,
                held_code_identity_reader=lambda _payload: "a" * 40,
                running_code_identity_reader=lambda _pid: next(code_identities),
                monotonic=iter((0.0, 5.0)).__next__,
                sleeper=lambda _seconds: None,
            )

    def result_fixture(self) -> dict[str, object]:
        app_identity = self.identity("app", files=9)
        dsym_identity = self.identity("dsym", files=3)
        receipt_identity = {
            "sha256": hashlib.sha256(b"receipt").hexdigest(),
            "size": 7,
        }
        empty = {"sha256": hashlib.sha256(b"").hexdigest(), "size": 0}
        migration_bytes = smoke.recovery.expected_observation_line(
            smoke.recovery.MIGRATION_MODE
        )
        readback_bytes = smoke.recovery.expected_observation_line(
            smoke.recovery.SQLITE_READBACK_MODE
        )
        sqlite = {
            "eventJsonSha256": smoke.recovery.CANARY_EVENT_JSON_SHA256,
            "eventJsonSize": len(smoke.recovery.CANARY_EVENT_JSON),
            "integrityCheck": "ok",
            "totalEventCount": 1,
        }
        return {
            "abruptTermination": {
                "appKitProcessAbsentAfterReap": True,
                "capturedLogsRevalidatedAfterReap": True,
                "exactExecutableRevalidatedBeforeSignal": True,
                "exitCode": -smoke.SIGKILL_NUMBER,
                "gracefulTerminationRequested": False,
                "inFlightWriteCheckpointObserved": False,
                "installedExecutableDescriptorHeldAcrossSignal": True,
                "launchMethod": smoke.ABRUPT_LAUNCH_METHOD,
                "migrationCommittedBeforeAbruptLaunch": True,
                "observationCompletedBeforeSignal": True,
                "pathIdentityStableAcrossSignal": True,
                "persistenceProbePassedBeforeSignal": True,
                "processDisposition": smoke.ABRUPT_PROCESS_DISPOSITION,
                "processReaped": True,
                "runningExecutableCodeIdentityMatchedHeldBytes": True,
                "signal": "SIGKILL",
                "signalNumber": smoke.SIGKILL_NUMBER,
                "signalTargetPolicy": smoke.SIGNAL_TARGET_POLICY,
            },
            "app": {
                "architecture": "arm64",
                "buildNumber": 24,
                "bundleIdentifier": "dev.aetherlink.companion",
                "marketingVersion": "1.0.0",
                "minimumSystemVersion": "14.0",
                "uuid": "00000000-0000-0000-0000-000000000001",
            },
            "canary": {
                "eventID": smoke.recovery.CANARY_EVENT_ID,
                "eventJsonSha256": smoke.recovery.CANARY_EVENT_JSON_SHA256,
                "eventJsonSize": len(smoke.recovery.CANARY_EVENT_JSON),
                "legacyJsonlSha256": smoke.recovery.CANARY_LEGACY_SHA256,
                "legacyJsonlSize": len(smoke.recovery.CANARY_LEGACY_BYTES),
                "model": smoke.recovery.CANARY_MODEL,
                "requestID": smoke.recovery.CANARY_REQUEST_ID,
                "sessionID": smoke.recovery.CANARY_SESSION_ID,
            },
            "cleanup": {
                "applicationSupportCleanupPerformed": False,
                "exactTemporaryAppPathOnly": True,
                "installedAppAbsentAfterFinalRemoval": True,
                "stateBytesAndModesUnchangedAfterAppRemoval": True,
                "temporaryRootRemoved": True,
            },
            "generation": {
                "app": app_identity,
                "currentSourceBound": True,
                "dSYM": dsym_identity,
                "independentReadbackStableAcrossExercise": True,
                "liveOutputMatchesPrivateSnapshotBeforeAndAfterExercise": True,
                "outerBundleSeal": "absent",
                "outputContract": smoke.reader.MACOS_UNSEALED_OUTPUT_CONTRACT,
                "outputRelativePath": "dist/unsealed-package-only",
                "source": {
                    "algorithm": (
                        "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
                    ),
                    "fileCount": 10,
                    "sha256": "c" * 64,
                },
                "sourceReceipt": receipt_identity,
            },
            "installation": {
                "codesignVerified": False,
                "copyTool": "ditto",
                "installedAppMatchesPrivateSnapshot": True,
                "installedRelativePath": "Applications/AetherLink.app",
                "outerBundleSeal": "absent",
                "tree": app_identity,
            },
            "isolation": {
                "afInetBindDeniedByPreflight": True,
                "cleanHomeConfigured": True,
                "nonTemporaryWriteDeniedByPreflight": True,
                "preexistingAetherLinkApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "sandboxProfile": (
                    "allow-default-deny-network-and-non-temp-writes-v1"
                ),
                "sandboxed": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "lifecycle": {
                "commandPolicy": smoke.COMMAND_POLICY,
                "distinctProcessIdentifiers": True,
                "runs": [
                    self.run_record(1),
                    self.abrupt_run_record(),
                    self.run_record(3),
                ],
            },
            "limitations": list(smoke.LIMITATIONS),
            "qualification": dict(smoke.QUALIFICATION),
            "schemaVersion": smoke.RESULT_SCHEMA_VERSION,
            "scope": smoke.RESULT_SCOPE,
            "stateRecovery": {
                "auxiliarySQLite": [
                    {"filename": filename, "integrityCheck": "ok"}
                    for filename in smoke.clean_recovery.AUXILIARY_SQLITE_FILES
                ],
                (
                    "installedStateBytesAndModesUnchangedAcrossAbruptTermination"
                    "AndRelaunch"
                ): True,
                "legacyAbsentBeforeAbruptAndRecoveryReadback": True,
                "legacyFixturePreservedUnchanged": True,
                "migrationObservation": {
                    "mode": smoke.recovery.MIGRATION_MODE,
                    "sha256": hashlib.sha256(migration_bytes).hexdigest(),
                    "size": len(migration_bytes),
                    "status": "passed",
                },
                "migrationSQLite": dict(sqlite),
                "ownedAbruptReadbackObservation": {
                    "mode": smoke.recovery.SQLITE_READBACK_MODE,
                    "sha256": hashlib.sha256(readback_bytes).hexdigest(),
                    "size": len(readback_bytes),
                    "status": "passed",
                },
                "ownedAbruptReadbackSQLite": dict(sqlite),
                "postAbruptSQLite": dict(sqlite),
                "recoveryReadbackObservation": {
                    "mode": smoke.recovery.SQLITE_READBACK_MODE,
                    "sha256": hashlib.sha256(readback_bytes).hexdigest(),
                    "size": len(readback_bytes),
                    "status": "passed",
                },
                "recoveryReadbackSQLite": dict(sqlite),
                "runtimeIdentityFilePresent": False,
                (
                    "sqliteCanaryUnchangedAcrossAbruptTerminationAndRelaunch"
                ): True,
                (
                    "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination"
                ): True,
                "stderr": {
                    "abruptReadback": empty,
                    "migration": empty,
                    "recoveryReadback": empty,
                },
            },
            "status": "passed",
        }

    def create_generation(self, root: Path, marker: bytes = b"one") -> None:
        app = root / "AetherLink.app"
        for relative in smoke.reader.MACOS_UNSEALED_APP_FILES:
            path = app / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode() + b":" + marker)
            path.chmod(0o755 if relative == "Contents/MacOS/AetherLink" else 0o644)
        dsym = root / "AetherLink.dSYM"
        for relative in smoke.reader.MACOS_UNSEALED_DSYM_FILES:
            path = dsym / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode() + b":" + marker)
            path.chmod(0o644)
        receipt = root / smoke.reader.MACOS_UNSEALED_SOURCE_RECEIPT_NAME
        receipt.write_bytes(b'{"fixture":true}\n')
        receipt.chmod(0o644)

    def test_default_cli_paths_are_fixed(self) -> None:
        arguments = smoke.parse_args([])
        self.assertFalse(hasattr(arguments, "output_root"))
        self.assertEqual(arguments.result, smoke.ROOT / smoke.RESULT_RELATIVE_PATH)
        self.assertEqual(
            arguments.repeatability_result,
            smoke.ROOT / smoke.REPEATABILITY_RESULT_RELATIVE_PATH,
        )
        self.assertFalse(hasattr(arguments, "single_run"))

    def test_cli_overrides_paths_and_bounded_durations(self) -> None:
        arguments = smoke.parse_args(
            [
                "--result", "result.json",
                "--repeatability-result", "repeat.json",
                "--readiness-timeout-seconds", "3",
                "--observation-seconds", "5",
                "--termination-timeout-seconds", "4",
            ]
        )
        self.assertEqual(arguments.result, Path("result.json"))
        self.assertEqual(arguments.repeatability_result, Path("repeat.json"))
        self.assertEqual(arguments.readiness_timeout_seconds, 3.0)
        self.assertEqual(arguments.observation_seconds, 5.0)
        self.assertEqual(arguments.termination_timeout_seconds, 4.0)

    def test_result_schema_accepts_canonical_fixture(self) -> None:
        result = self.result_fixture()
        self.assertIs(smoke.validate_result_document(result), result)

    def test_result_schema_rejects_bool_as_integer(self) -> None:
        result = self.result_fixture()
        result["schemaVersion"] = True
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "exact integer"
        ):
            smoke.validate_result_document(result)

    def test_result_schema_rejects_integer_as_boolean(self) -> None:
        result = self.result_fixture()
        result["cleanup"]["temporaryRootRemoved"] = 1
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "exact boolean"
        ):
            smoke.validate_result_document(result)

    def test_result_schema_rejects_boolean_sigkill_exit_alias(self) -> None:
        result = self.result_fixture()
        result["abruptTermination"]["exitCode"] = True
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "exact integer"
        ):
            smoke.validate_result_document(result)

    def test_result_schema_rejects_qualification_zero_alias(self) -> None:
        result = self.result_fixture()
        result["qualification"]["canonicalG6ExitClaimed"] = 0
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "exact boolean"
        ):
            smoke.validate_result_document(result)

    def test_result_schema_rejects_canary_size_boolean_alias(self) -> None:
        result = self.result_fixture()
        result["canary"]["eventJsonSize"] = True
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "canary.eventJsonSize"
        ):
            smoke.validate_result_document(result)

    def test_result_schema_rejects_sqlite_count_boolean_alias(self) -> None:
        result = self.result_fixture()
        result["stateRecovery"]["migrationSQLite"]["totalEventCount"] = True
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "migrationSQLite"
        ):
            smoke.validate_result_document(result)

    def test_result_schema_rejects_nonfinite_observation_duration(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                result = self.result_fixture()
                result["lifecycle"]["runs"][0][
                    "minimumObservationSeconds"
                ] = value
                with self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError, "finite and bounded"
                ):
                    smoke.validate_result_document(result)

    def test_result_schema_rejects_nonempty_stderr(self) -> None:
        result = self.result_fixture()
        result["stateRecovery"]["stderr"]["migration"] = {
            "sha256": hashlib.sha256(b"warning\n").hexdigest(),
            "size": len(b"warning\n"),
        }
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "must be exactly empty"
        ):
            smoke.validate_result_document(result)

    def test_result_schema_rejects_raw_pid(self) -> None:
        result = self.result_fixture()
        result["stateRecovery"]["pid"] = 59809
        with self.assertRaises(smoke.engine.LifecycleSmokeError):
            smoke.validate_result_document(result)

    def test_read_generation_binds_exact_bytes_modes_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "generation"
            root.mkdir()
            self.create_generation(root)
            first = smoke.read_generation(root)
            second = smoke.read_generation(root)
            smoke.require_same_generation(first, second, label="fixture")
            executable = root / "AetherLink.app/Contents/MacOS/AetherLink"
            executable.write_bytes(executable.read_bytes() + b"drift")
            executable.chmod(0o755)
            changed = smoke.read_generation(root)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError, "exact bytes"
            ):
                smoke.require_same_generation(first, changed, label="fixture")

    def test_read_generation_rejects_symlink_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            physical = parent / "physical"
            physical.mkdir()
            self.create_generation(physical)
            linked = parent / "linked"
            linked.symlink_to(physical, target_is_directory=True)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError, "physical directory"
            ):
                smoke.read_generation(linked)

    def test_readback_must_match_snapshot_identity(self) -> None:
        generation = smoke.GenerationRead(
            app_files={"app": b"a"},
            app_modes={"app": 0o755},
            app_identity=self.identity("app"),
            dsym_files={"dsym": b"d"},
            dsym_modes={"dsym": 0o644},
            dsym_identity=self.identity("dsym"),
            receipt_bytes=b"receipt",
            receipt_mode=0o644,
        )
        public = generation.public_identity()
        readback = {
            "app": public["app"],
            "dSYM": public["dSYM"],
            "sourceReceipt": public["sourceReceipt"],
            "outerBundleSeal": "absent",
        }
        smoke.verify_readback_matches_generation(readback, generation)
        readback["app"] = self.identity("other")
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "independent readback"
        ):
            smoke.verify_readback_matches_generation(readback, generation)

    def test_result_paths_must_be_distinct_and_outside_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            same = root / "same.json"
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError, "must differ"
            ):
                smoke.require_output_paths_outside_generation(output, same, same)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError, "outside"
            ):
                smoke.require_output_paths_outside_generation(
                    output, output / "result.json", root / "receipt.json"
                )

    def test_existing_recovery_and_sandbox_helpers_are_reused(self) -> None:
        self.assertIs(
            smoke.recovery_launch_environment,
            smoke.clean_recovery.recovery_launch_environment,
        )
        self.assertIs(
            smoke.validate_captured_log,
            smoke.clean_recovery.validate_captured_log,
        )
        self.assertIs(
            smoke.auxiliary_sqlite_evidence,
            smoke.clean_recovery.auxiliary_sqlite_evidence,
        )
        self.assertIs(smoke.sandbox_profile, smoke.lifecycle.build_sandbox_profile)
        self.assertIs(smoke.sandbox_preflight, smoke.lifecycle.preflight_sandbox)

    def test_owned_cycle_captures_pid_without_retaining_it_in_record(self) -> None:
        class Process:
            pid = 4242

        def fake_lifecycle(**kwargs: object) -> smoke.lifecycle.LifecycleRunResult:
            kwargs["popen_factory"](["fixture"])
            return smoke.lifecycle.LifecycleRunResult(
                activation_policy=0,
                exit_code=0,
                finished_launching=True,
                minimum_observation_seconds=5.0,
                ordinal=1,
                observation_deadline_reached=True,
                termination_accepted=True,
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "AetherLink.app"
            executable = app / smoke.installed.EXECUTABLE_RELATIVE_PATH
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fixture")
            logs = root / "logs"
            logs.mkdir()
            with patch.object(smoke.lifecycle, "run_one_lifecycle", fake_lifecycle):
                pid, record = smoke.run_owned_recovery_cycle(
                    ordinal=1,
                    app_path=app,
                    profile="fixture-profile",
                    environment={},
                    log_directory=logs,
                    readiness_timeout_seconds=1,
                    observation_seconds=5,
                    termination_timeout_seconds=1,
                    popen_factory=lambda *args, **kwargs: Process(),
                )
        self.assertEqual(pid, 4242)
        self.assertTrue(record["ownedChildProcessCaptured"])
        self.assertNotIn("pid", record)

    def test_direct_owned_readiness_accepts_unavailable_bundle_id(self) -> None:
        class Process:
            pid = 4242

            def poll(self) -> None:
                return None

        executable = Path("/tmp/AetherLink.app/Contents/MacOS/AetherLink")
        status = smoke.wait_for_direct_owned_readiness(
            Process(),
            executable,
            timeout_seconds=1,
            query_payload=lambda _pid: {
                "activationPolicy": 0,
                "executablePath": str(executable),
                "finishedLaunching": True,
                "found": True,
            },
        )
        self.assertEqual(status.bundle_identifier_state, "unavailable")
        self.assertEqual(status.executable_path, str(executable))

    def test_direct_owned_readiness_rejects_wrong_bundle_id(self) -> None:
        class Process:
            pid = 4242

            def poll(self) -> None:
                return None

        executable = Path("/tmp/AetherLink.app/Contents/MacOS/AetherLink")
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "bundle identifier differs"
        ):
            smoke.wait_for_direct_owned_readiness(
                Process(),
                executable,
                timeout_seconds=1,
                query_payload=lambda _pid: {
                    "activationPolicy": 0,
                    "bundleIdentifier": "dev.aetherlink.wrong",
                    "executablePath": str(executable),
                    "finishedLaunching": True,
                    "found": True,
                },
            )

    def test_direct_owned_termination_accepts_unavailable_bundle_id(self) -> None:
        accepted = smoke.request_direct_owned_termination(
            4242,
            Path("/tmp/AetherLink.app/Contents/MacOS/AetherLink"),
            force=False,
            probe=lambda _pid, _executable, _force: {
                "accepted": True,
                "bundleIdentifierState": "unavailable",
                "found": True,
                "identityMatched": True,
            },
        )
        self.assertTrue(accepted)

    def test_direct_owned_termination_rejects_identity_mismatch(self) -> None:
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "identity did not match"
        ):
            smoke.request_direct_owned_termination(
                4242,
                Path("/tmp/AetherLink.app/Contents/MacOS/AetherLink"),
                force=False,
                probe=lambda _pid, _executable, _force: {
                    "accepted": False,
                    "bundleIdentifierState": "mismatch",
                    "found": True,
                    "identityMatched": False,
                },
            )

    def test_direct_owned_termination_rejects_contradictory_bundle_state(
        self,
    ) -> None:
        for state in ("absent", "mismatch"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    "identity did not match",
                ):
                    smoke.request_direct_owned_termination(
                        4242,
                        Path(
                            "/tmp/AetherLink.app/Contents/MacOS/AetherLink"
                        ),
                        force=False,
                        probe=lambda _pid, _executable, _force, state=state: {
                            "accepted": True,
                            "bundleIdentifierState": state,
                            "found": True,
                            "identityMatched": True,
                        },
                    )

    def test_held_executable_descriptor_rejects_hardlink_and_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "AetherLink"
            payload = b"current-unsealed-executable"
            executable.write_bytes(payload)
            executable.chmod(0o755)
            hardlink = root / "AetherLink-hardlink"
            os.link(executable, hardlink)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError, "private generation"
            ):
                smoke.open_held_installed_executable(
                    executable,
                    expected_bytes=payload,
                )
            hardlink.unlink()
            descriptor, identity = smoke.open_held_installed_executable(
                executable,
                expected_bytes=payload,
            )
            try:
                replacement = root / "replacement"
                replacement.write_bytes(payload)
                replacement.chmod(0o755)
                executable.unlink()
                replacement.rename(executable)
                with self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError, "identity changed"
                ):
                    smoke.require_held_installed_executable(
                        descriptor,
                        executable,
                        expected=identity,
                        expected_bytes=payload,
                    )
            finally:
                os.close(descriptor)

    def test_codesign_cdhash_parser_requires_one_exact_sha256_cdhash(self) -> None:
        expected = "a" * 40
        payload = (
            b"Executable=/private/tmp/AetherLink\n"
            b"CandidateCDHash sha256=" + expected.encode() + b"\n"
            b"CDHash=" + expected.encode() + b"\n"
        )
        self.assertEqual(
            smoke.parse_codesign_cdhash(payload, label="fixture"), expected
        )
        for invalid in (
            b"CDHash=" + b"a" * 39 + b"\n",
            b"CDHash=" + b"a" * 40 + b"\nCDHash=" + b"b" * 40 + b"\n",
            b"CDHash=" + b"A" * 40 + b"\n",
            b"CDHash=" + b"a" * 40 + b"\x00\n",
        ):
            with self.subTest(payload=invalid):
                with self.assertRaises(smoke.engine.LifecycleSmokeError):
                    smoke.parse_codesign_cdhash(invalid, label="fixture")

    def test_held_executable_cdhash_is_parsed_from_exact_macho_bytes(self) -> None:
        payload, expected = self.signed_macho_fixture()
        self.assertEqual(expected, "6dfd2839eb80d363966f34396baa897a29eff619")
        with (
            patch.object(
                smoke,
                "codesign_cdhash_for_target",
                side_effect=AssertionError("external codesign must not be called"),
            ),
            patch.object(
                smoke.subprocess,
                "run",
                side_effect=AssertionError("subprocess must not be called"),
            ),
            patch.object(
                smoke.tempfile,
                "TemporaryDirectory",
                side_effect=AssertionError("temporary files must not be used"),
            ),
        ):
            self.assertEqual(
                smoke.codesign_cdhash_for_executable_bytes(payload), expected
            )

    def test_held_executable_cdhash_rejects_malformed_or_unbound_bytes(
        self,
    ) -> None:
        payload, _ = self.signed_macho_fixture()
        signature_offset = self.MACHO_FIXTURE_SIGNATURE_OFFSET
        code_directory_offset = signature_offset + 20

        def changed(offset: int, replacement: bytes) -> bytes:
            result = bytearray(payload)
            result[offset : offset + len(replacement)] = replacement
            return bytes(result)

        mutations = {
            "wrong Mach-O magic": changed(0, b"BAD!"),
            "zero load-command count": changed(16, struct.pack("<I", 0)),
            "duplicate code signature command": (
                changed(16, struct.pack("<II", 2, 32))[:48]
                + struct.pack(
                    "<IIII",
                    smoke.MACHO_LOAD_COMMAND_CODE_SIGNATURE,
                    16,
                    signature_offset,
                    len(payload) - signature_offset,
                )
                + payload[64:]
            ),
            "alternate CodeDirectory slot": changed(
                signature_offset + 12, struct.pack(">I", 1)
            ),
            "two SuperBlob entries": changed(
                signature_offset + 8, struct.pack(">I", 2)
            ),
            "wrong CodeDirectory version": changed(
                code_directory_offset + 8, struct.pack(">I", 0x20300)
            ),
            "wrong CodeDirectory hash type": changed(
                code_directory_offset + 37, b"\x01"
            ),
            "changed first held code page": changed(100, b"\x01"),
            "changed partial held code page": changed(4_096, b"\x01"),
            "changed second stored page hash": changed(
                code_directory_offset
                + smoke.CODE_DIRECTORY_HEADER_SIZE
                + len(smoke.CODE_DIRECTORY_IDENTIFIER)
                + smoke.CODE_DIRECTORY_SHA256_HASH_SIZE,
                b"\x01",
            ),
            "wrong code-slot count": changed(
                code_directory_offset + 28, struct.pack(">I", 1)
            ),
            "code limit differs from signature offset": changed(
                code_directory_offset + 32,
                struct.pack(">I", signature_offset - 1),
            ),
            "changed identifier": changed(
                code_directory_offset + smoke.CODE_DIRECTORY_HEADER_SIZE,
                b"B",
            ),
            "nonzero signature padding": changed(len(payload) - 1, b"\x01"),
            "oversized CodeDirectory": changed(
                code_directory_offset + 4, struct.pack(">I", len(payload))
            ),
        }
        for label, invalid in mutations.items():
            with self.subTest(label=label):
                with self.assertRaises(smoke.engine.LifecycleSmokeError):
                    smoke.codesign_cdhash_for_executable_bytes(invalid)
        for invalid in (bytearray(payload), b"", b"not-a-macho"):
            with self.subTest(type=type(invalid).__name__):
                with self.assertRaises(smoke.engine.LifecycleSmokeError):
                    smoke.codesign_cdhash_for_executable_bytes(invalid)

    def test_abrupt_cycle_rejects_running_code_identity_mismatch(self) -> None:
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError,
            "running executable code identity differs from held bytes",
        ):
            self.exercise_failing_abrupt_cycle(
                running_code_identities=("b" * 40,)
            )

    def test_abrupt_cycle_rejects_late_log_write_before_reap(self) -> None:
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError,
            "logs changed before reap completed",
        ):
            self.exercise_failing_abrupt_cycle(
                running_code_identities=("a" * 40, "a" * 40),
                late_stderr=b"late-stderr-after-pre-signal-validation",
            )

    def test_owned_abrupt_cycle_proves_exact_sigkill_and_reap(self) -> None:
        class Process:
            pid = 4242

            def __init__(self) -> None:
                self.returncode: int | None = None
                self.signals: list[int] = []

            def poll(self) -> int | None:
                return self.returncode

            def send_signal(self, sent_signal: int) -> None:
                self.signals.append(sent_signal)

            def wait(self, timeout: float) -> int:
                self.returncode = -signal.SIGKILL
                return self.returncode

        process = Process()
        running_code_identity_pids: list[int] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "AetherLink.app"
            executable = app / smoke.installed.EXECUTABLE_RELATIVE_PATH
            executable.parent.mkdir(parents=True)
            executable_payload = b"fixture-executable"
            executable.write_bytes(executable_payload)
            executable.chmod(0o755)
            logs = root / "logs"
            logs.mkdir()

            def popen_factory(*args: object, **kwargs: object) -> Process:
                stdout = kwargs["stdout"]
                stdout.write(
                    smoke.recovery.expected_observation_line(
                        smoke.recovery.SQLITE_READBACK_MODE
                    )
                )
                stdout.flush()
                return process

            probe_calls: list[str] = []
            pid, record, observation, stderr = (
                smoke.run_owned_abrupt_recovery_cycle(
                    ordinal=2,
                    app_path=app,
                    profile="fixture-profile",
                    environment={},
                    log_directory=logs,
                    readiness_timeout_seconds=1,
                    observation_seconds=5,
                    termination_timeout_seconds=1,
                    persistence_probe=lambda: probe_calls.append("probe"),
                    expected_executable_bytes=executable_payload,
                    popen_factory=popen_factory,
                    readiness_waiter=lambda *args, **kwargs: (
                        smoke.DirectOwnedApplicationStatus(
                            activation_policy=0,
                            bundle_identifier_state="expected",
                            executable_path=str(executable),
                            finished_launching=True,
                        )
                    ),
                    status_reader=lambda _pid, _executable: (
                        smoke.DirectOwnedApplicationStatus(
                            activation_policy=0,
                            bundle_identifier_state="expected",
                            executable_path=str(executable),
                            finished_launching=True,
                        )
                    ),
                    absence_waiter=lambda *args, **kwargs: True,
                    held_code_identity_reader=lambda _payload: "a" * 40,
                    running_code_identity_reader=lambda pid: (
                        running_code_identity_pids.append(pid) or "a" * 40
                    ),
                    monotonic=iter((0.0, 5.0)).__next__,
                    sleeper=lambda _seconds: None,
                )
            )
        self.assertEqual(pid, 4242)
        self.assertEqual(process.signals, [signal.SIGKILL])
        self.assertEqual(running_code_identity_pids, [4242, 4242])
        self.assertEqual(probe_calls, ["probe"])
        self.assertEqual(record["exitCode"], -signal.SIGKILL)
        self.assertTrue(record["installedExecutableDescriptorHeldAcrossSignal"])
        self.assertTrue(record["capturedLogsRevalidatedAfterReap"])
        self.assertTrue(
            record["runningExecutableCodeIdentityMatchedHeldBytes"]
        )
        self.assertEqual(observation["mode"], smoke.recovery.SQLITE_READBACK_MODE)
        self.assertEqual(stderr, {"sha256": smoke.EMPTY_SHA256, "size": 0})

    def test_repeatability_rejects_different_observation_bytes(self) -> None:
        first = self.result_fixture()
        second = copy.deepcopy(first)
        second["app"]["buildNumber"] = 25
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    smoke, "execute_observation", side_effect=[first, second]
                ),
                patch.object(smoke.publication, "publish_result_pair") as publish,
            ):
                with self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError, "different results"
                ):
                    smoke.execute_repeatability(
                        output_root=smoke.default_output_root(),
                        result_path=root / "result.json",
                        repeatability_result_path=root / "repeat.json",
                        readiness_timeout_seconds=1,
                        observation_seconds=5,
                        termination_timeout_seconds=1,
                    )
        publish.assert_not_called()

    def test_repeatability_delegates_atomic_pair_publication(self) -> None:
        result = self.result_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / "result.json"
            receipt_path = root / "repeat.json"
            with (
                patch.object(
                    smoke,
                    "execute_observation",
                    side_effect=[copy.deepcopy(result), copy.deepcopy(result)],
                ),
                patch.object(smoke.publication, "publish_result_pair") as publish,
            ):
                receipt = smoke.execute_repeatability(
                    output_root=smoke.default_output_root(),
                    result_path=result_path,
                    repeatability_result_path=receipt_path,
                    readiness_timeout_seconds=1,
                    observation_seconds=5,
                    termination_timeout_seconds=1,
                )
        self.assertEqual(receipt["runCount"], 2)
        self.assertTrue(receipt["resultBytesEqual"])
        publish.assert_called_once()
        arguments = publish.call_args.args
        self.assertEqual(arguments[0], result_path)
        self.assertEqual(arguments[1], smoke.engine.canonical_json_bytes(result))
        self.assertEqual(arguments[2], receipt_path)
        self.assertEqual(
            arguments[3], smoke.engine.canonical_json_bytes(receipt)
        )

    def test_repeatability_rejects_noncanonical_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError, "canonical"
            ):
                smoke.execute_repeatability(
                    output_root=root / "output",
                    result_path=root / "result.json",
                    repeatability_result_path=root / "repeat.json",
                    readiness_timeout_seconds=1,
                    observation_seconds=5,
                    termination_timeout_seconds=1,
                )

    def test_repeatability_receipt_rejects_bool_run_count(self) -> None:
        result = self.result_fixture()
        payload = smoke.engine.canonical_json_bytes(result)
        identity = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }
        receipt = {
            "canonicalResult": {"fileName": "result.json", **identity},
            "limitations": list(smoke.LIMITATIONS),
            "qualification": dict(smoke.QUALIFICATION),
            "resultBytesEqual": True,
            "runCount": True,
            "runs": [
                {"ordinal": ordinal, **identity, "status": "passed"}
                for ordinal in (1, 2)
            ],
            "schemaVersion": smoke.REPEATABILITY_SCHEMA_VERSION,
            "scope": smoke.REPEATABILITY_SCOPE,
            "status": "passed",
        }
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "exact integer"
        ):
            smoke.validate_repeatability_receipt(receipt)

    def test_repeatability_receipt_rejects_qualification_zero_alias(self) -> None:
        result = self.result_fixture()
        payload = smoke.engine.canonical_json_bytes(result)
        identity = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }
        receipt = {
            "canonicalResult": {"fileName": "result.json", **identity},
            "limitations": list(smoke.LIMITATIONS),
            "qualification": dict(smoke.QUALIFICATION),
            "resultBytesEqual": True,
            "runCount": 2,
            "runs": [
                {"ordinal": ordinal, **identity, "status": "passed"}
                for ordinal in (1, 2)
            ],
            "schemaVersion": smoke.REPEATABILITY_SCHEMA_VERSION,
            "scope": smoke.REPEATABILITY_SCOPE,
            "status": "passed",
        }
        receipt["qualification"]["canonicalG7ExitClaimed"] = 0
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError, "exact boolean"
        ):
            smoke.validate_repeatability_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
