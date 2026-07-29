from __future__ import annotations

from contextlib import redirect_stderr
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from script import run_macos_packaged_app_build10_lifecycle_smoke as smoke


class Build10MacOSPackagedAppLifecycleSmokeTests(unittest.TestCase):
    def release_fixture(
        self,
        root: Path,
    ) -> tuple[smoke.LifecycleContract, smoke.engine.ReleaseInputs]:
        executable = b"binary"
        executable_sha256 = hashlib.sha256(executable).hexdigest()
        contract = replace(
            smoke.BUILD_10_CONTRACT,
            executable_size=len(executable),
            executable_sha256=executable_sha256,
            macos_uuid="TEST-UUID",
        )
        archive_dir = root / contract.release_id
        archive_dir.mkdir()
        archive_path = archive_dir / f"{contract.release_id}.zip"
        manifest_path = archive_dir / f"{contract.release_id}.manifest.json"
        checksum_path = archive_dir / f"{contract.release_id}.zip.sha256"
        executable_member = (
            smoke.engine.APP_MEMBER_PREFIX
            + smoke.engine.EXECUTABLE_RELATIVE_PATH.as_posix()
        )
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(executable_member, executable)
        manifest = {
            "members": [
                {
                    "mode": "0755",
                    "path": executable_member,
                    "sha256": executable_sha256,
                    "size": len(executable),
                }
            ],
            "platforms": {"macos": {"uuid": contract.macos_uuid}},
            "release": {
                "buildNumber": contract.build_number,
                "marketingVersion": contract.marketing_version,
                "releaseId": contract.release_id,
            },
        }
        manifest_bytes = smoke.engine.canonical_json_bytes(manifest)
        manifest_path.write_bytes(manifest_bytes)
        archive_sha256 = smoke.sha256_file(archive_path)
        checksum_path.write_text(
            f"{archive_sha256}  {archive_path.name}\n",
            encoding="ascii",
        )
        contract = replace(
            contract,
            archive_sha256=archive_sha256,
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        )
        return (
            contract,
            smoke.engine.ReleaseInputs(
                archive_dir=archive_dir,
                archive_path=archive_path,
                manifest_path=manifest_path,
                checksum_path=checksum_path,
                archive_sha256=archive_sha256,
                manifest_sha256=contract.manifest_sha256,
                manifest=manifest,
            ),
        )

    def test_build10_contract_is_frozen_and_exact(self) -> None:
        contract = smoke.BUILD_10_CONTRACT

        self.assertEqual(contract.release_id, "aetherlink-1.0.0+10-local-v1")
        self.assertEqual(contract.build_number, 10)
        self.assertEqual(
            contract.archive_sha256,
            "12a4fcccceac74248a0835765876bd9184c845696c83cbf3a6b1fe7613000cc0",
        )
        self.assertEqual(
            contract.manifest_sha256,
            "fcda01d30c61be8182fc294ee76d2583b98ec78fee8b0e6c2ec2f9208ea31741",
        )
        self.assertEqual(
            contract.executable_sha256,
            "75f20fad8d5ce20ecdaa07bcdd526b20cb88f46b50dd1639f11f739858ad6ef4",
        )
        self.assertEqual(
            contract.macos_uuid,
            "415765ED-429A-36D9-BC1A-BAC6DDF18B45",
        )
        with self.assertRaises(FrozenInstanceError):
            contract.build_number = 11  # type: ignore[misc]

    def test_preserved_build9_runner_test_and_result_are_exact(self) -> None:
        self.assertEqual(smoke.preserved_build9_evidence_failures(), [])

    def test_preserved_build9_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "changed"
            changed.write_bytes(b"changed")
            with patch.object(
                smoke,
                "PRESERVED_BUILD9_IDENTITIES",
                ((changed, "0" * 64),),
            ):
                failures = smoke.preserved_build9_evidence_failures()

        self.assertEqual(len(failures), 1)
        self.assertIn("drifted", failures[0])

    def test_build10_readback_uses_current_lane(self) -> None:
        with patch.object(smoke.engine, "run_checked") as run_checked:
            smoke.verify_archive_readback(Path("/tmp/build-10"))

        command = run_checked.call_args.args[0]
        self.assertNotIn("--historical", command)
        self.assertNotIn("--no-current-source", command)
        self.assertEqual(command[-1], "/tmp/build-10")
        self.assertEqual(run_checked.call_args.kwargs["cwd"], smoke.ROOT)

    def test_load_release_inputs_accepts_exact_typed_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract, fixture = self.release_fixture(Path(temporary))

            loaded = smoke.load_release_inputs(
                fixture.archive_dir,
                verify_readback=False,
                contract=contract,
            )

        self.assertEqual(loaded.archive_sha256, contract.archive_sha256)
        self.assertEqual(loaded.manifest_sha256, contract.manifest_sha256)

    def test_load_release_inputs_rejects_wrong_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wrong = Path(temporary) / "wrong"
            wrong.mkdir()
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "expected release directory",
            ):
                smoke.load_release_inputs(wrong, verify_readback=False)

    def test_load_release_inputs_rejects_boolean_build_number(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract, fixture = self.release_fixture(Path(temporary))
            fixture.manifest["release"]["buildNumber"] = True
            manifest_bytes = smoke.engine.canonical_json_bytes(fixture.manifest)
            fixture.manifest_path.write_bytes(manifest_bytes)
            contract = replace(
                contract,
                manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            )

            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "unexpected release metadata",
            ):
                smoke.load_release_inputs(
                    fixture.archive_dir,
                    verify_readback=False,
                    contract=contract,
                )

    def test_load_release_inputs_rejects_wrong_archive_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract, fixture = self.release_fixture(Path(temporary))
            contract = replace(contract, archive_sha256="0" * 64)

            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "qualified Build 10 identity",
            ):
                smoke.load_release_inputs(
                    fixture.archive_dir,
                    verify_readback=False,
                    contract=contract,
                )

    def test_load_release_inputs_rejects_malformed_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract, fixture = self.release_fixture(Path(temporary))
            fixture.checksum_path.write_text("malformed\n", encoding="ascii")

            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "checksum sidecar is malformed",
            ):
                smoke.load_release_inputs(
                    fixture.archive_dir,
                    verify_readback=False,
                    contract=contract,
                )

    def test_verify_packaged_app_binds_plist_executable_and_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, release = self.release_fixture(root)
            app = root / "AetherLink.app"
            info_plist = app / smoke.engine.INFO_PLIST_RELATIVE_PATH
            executable = app / smoke.engine.EXECUTABLE_RELATIVE_PATH
            info_plist.parent.mkdir(parents=True)
            executable.parent.mkdir(parents=True)
            info_plist.write_bytes(
                plistlib.dumps(
                    {
                        "CFBundleIdentifier": contract.bundle_identifier,
                        "CFBundleShortVersionString": (
                            contract.marketing_version
                        ),
                        "CFBundleVersion": str(contract.build_number),
                    }
                )
            )
            executable.write_bytes(b"binary")
            executable.chmod(0o755)

            def checked(command: list[str], **_: object) -> object:
                stdout = ""
                if "-extract" in command:
                    key = command[command.index("-extract") + 1]
                    stdout = (
                        contract.marketing_version
                        if key == "CFBundleShortVersionString"
                        else str(contract.build_number)
                    )
                return subprocess.CompletedProcess(command, 0, stdout, "")

            with patch.object(
                smoke.engine,
                "run_checked",
                side_effect=checked,
            ):
                metadata = smoke.verify_packaged_app(
                    app,
                    release,
                    contract=contract,
                )

        self.assertEqual(metadata["buildNumber"], contract.build_number)
        self.assertEqual(
            metadata["executableSha256"],
            contract.executable_sha256,
        )
        self.assertEqual(metadata["uuid"], contract.macos_uuid)

    def test_publish_result_is_immutable_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            result = {"schemaVersion": 1, "status": "passed"}

            smoke.publish_result(path, result)
            first = path.read_bytes()
            smoke.publish_result(path, result)

            self.assertEqual(path.read_bytes(), first)
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "refusing to replace different",
            ):
                smoke.publish_result(
                    path,
                    {"schemaVersion": 1, "status": "failed"},
                )

    def test_execute_publishes_exact_build10_two_run_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / "result.json"
            release = Mock(
                archive_sha256=smoke.BUILD_10_CONTRACT.archive_sha256,
                manifest_sha256=smoke.BUILD_10_CONTRACT.manifest_sha256,
            )

            def fake_run(**kwargs: object) -> smoke.engine.LifecycleRunResult:
                environment = kwargs["environment"]
                assert isinstance(environment, dict)
                application_support = (
                    Path(environment["HOME"])
                    / "Library/Application Support/AetherLink"
                )
                application_support.mkdir(parents=True, exist_ok=True)
                for name in smoke.engine.EXPECTED_ISOLATED_STATE_FILES:
                    (application_support / name).write_bytes(b"fixture")
                ordinal = int(kwargs["ordinal"])
                return smoke.engine.LifecycleRunResult(
                    activation_policy=0,
                    exit_code=0,
                    finished_launching=True,
                    minimum_observation_seconds=5.0,
                    observation_deadline_reached=True,
                    ordinal=ordinal,
                    termination_accepted=True,
                )

            with (
                patch.object(smoke, "verify_preserved_build9_evidence"),
                patch.object(
                    smoke,
                    "load_release_inputs",
                    return_value=release,
                ),
                patch.object(
                    smoke.engine,
                    "extract_packaged_app",
                    side_effect=lambda release, destination: (
                        destination.parent / "AetherLink.app"
                    ),
                ),
                patch.object(
                    smoke,
                    "verify_packaged_app",
                    return_value={
                        "bundleIdentifier": (
                            smoke.BUILD_10_CONTRACT.bundle_identifier
                        ),
                        "buildNumber": 10,
                        "executableSha256": (
                            smoke.BUILD_10_CONTRACT.executable_sha256
                        ),
                        "marketingVersion": "1.0.0",
                        "uuid": smoke.BUILD_10_CONTRACT.macos_uuid,
                    },
                ),
                patch.object(smoke.engine, "preflight_sandbox"),
                patch.object(
                    smoke.engine,
                    "run_one_lifecycle",
                    side_effect=fake_run,
                ),
            ):
                result = smoke.execute(
                    archive_dir=root / "release",
                    result_path=result_path,
                    readiness_timeout_seconds=15,
                    observation_seconds=5,
                    termination_timeout_seconds=10,
                )

        self.assertEqual(
            result["release"]["releaseId"],
            "aetherlink-1.0.0+10-local-v1",
        )
        self.assertEqual(result["app"]["buildNumber"], 10)
        self.assertEqual([run["ordinal"] for run in result["runs"]], [1, 2])
        self.assertEqual(smoke.engine.EXPECTED_BUILD_NUMBER, 9)

    def test_execute_does_not_publish_partial_second_run_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / "result.json"

            def fake_run(**kwargs: object) -> smoke.engine.LifecycleRunResult:
                ordinal = int(kwargs["ordinal"])
                if ordinal == 2:
                    raise smoke.engine.LifecycleSmokeError(
                        "second launch failed"
                    )
                environment = kwargs["environment"]
                assert isinstance(environment, dict)
                application_support = (
                    Path(environment["HOME"])
                    / "Library/Application Support/AetherLink"
                )
                application_support.mkdir(parents=True, exist_ok=True)
                for name in smoke.engine.EXPECTED_ISOLATED_STATE_FILES:
                    (application_support / name).write_bytes(b"fixture")
                return smoke.engine.LifecycleRunResult(
                    activation_policy=0,
                    exit_code=0,
                    finished_launching=True,
                    minimum_observation_seconds=5.0,
                    observation_deadline_reached=True,
                    ordinal=ordinal,
                    termination_accepted=True,
                )

            with (
                patch.object(smoke, "verify_preserved_build9_evidence"),
                patch.object(smoke, "load_release_inputs", return_value=Mock()),
                patch.object(
                    smoke.engine,
                    "extract_packaged_app",
                    side_effect=lambda release, destination: (
                        destination.parent / "AetherLink.app"
                    ),
                ),
                patch.object(smoke, "verify_packaged_app", return_value={}),
                patch.object(smoke.engine, "preflight_sandbox"),
                patch.object(
                    smoke.engine,
                    "run_one_lifecycle",
                    side_effect=fake_run,
                ),
                self.assertRaisesRegex(
                    smoke.engine.LifecycleSmokeError,
                    "second launch failed",
                ),
            ):
                smoke.execute(
                    archive_dir=root / "release",
                    result_path=result_path,
                    readiness_timeout_seconds=15,
                    observation_seconds=5,
                    termination_timeout_seconds=10,
                )

            self.assertFalse(result_path.exists())

    def test_cli_keeps_release_identity_out_of_arguments(self) -> None:
        args = smoke.parse_args([])
        self.assertEqual(args.archive_dir, smoke.DEFAULT_ARCHIVE_DIR)
        self.assertEqual(args.result, smoke.DEFAULT_RESULT)

        with (
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            smoke.parse_args(["--release-id", "mutable"])


if __name__ == "__main__":
    unittest.main()
