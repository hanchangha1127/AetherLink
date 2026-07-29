from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import plistlib
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from script import run_macos_packaged_app_state_recovery_smoke as smoke


class MacOSPackagedAppStateRecoverySmokeTests(unittest.TestCase):
    def test_canary_fixture_bytes_and_hashes_are_exact(self) -> None:
        self.assertEqual(len(smoke.CANARY_LEGACY_BYTES), 345)
        self.assertTrue(smoke.CANARY_LEGACY_BYTES.endswith(b"\n"))
        self.assertEqual(
            hashlib.sha256(smoke.CANARY_LEGACY_BYTES).hexdigest(),
            smoke.CANARY_LEGACY_SHA256,
        )
        self.assertEqual(len(smoke.CANARY_EVENT_JSON), 344)
        self.assertEqual(
            hashlib.sha256(smoke.CANARY_EVENT_JSON).hexdigest(),
            smoke.CANARY_EVENT_JSON_SHA256,
        )
        self.assertEqual(
            json.loads(smoke.CANARY_EVENT_JSON),
            {
                "id": smoke.CANARY_EVENT_ID,
                "kind": "request",
                "messages": [
                    {
                        "content": (
                            "Benign packaged state recovery canary v1."
                        ),
                        "role": "user",
                    }
                ],
                "model": smoke.CANARY_MODEL,
                "request_id": smoke.CANARY_REQUEST_ID,
                "session_id": smoke.CANARY_SESSION_ID,
                "timestamp": smoke.CANARY_TIMESTAMP,
            },
        )

    def test_release_id_uses_exact_typed_ledger_values(self) -> None:
        version = smoke.ReleaseVersion(12, "1.0.0", (1, 0, 0))
        self.assertEqual(
            smoke.release_id_for(version),
            "aetherlink-1.0.0+12-local-v1",
        )

    def test_state_recovery_environment_closes_inherited_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = smoke.state_recovery_environment(
                {
                    "AETHERLINK_UNRELATED": "remove",
                    smoke.QA_MODE_ENVIRONMENT_KEY: "wrong",
                    "DYLD_INSERT_LIBRARIES": "remove",
                    "PATH": "/usr/bin",
                },
                home=root / "home",
                temporary=root / "tmp",
                identity_file=root / "identity.json",
                mode=smoke.MIGRATION_MODE,
            )

        self.assertEqual(
            environment[smoke.QA_MODE_ENVIRONMENT_KEY],
            smoke.MIGRATION_MODE,
        )
        self.assertEqual(
            environment["AETHERLINK_RUNTIME_IDENTITY_FILE"],
            str(root / "identity.json"),
        )
        self.assertNotIn("AETHERLINK_UNRELATED", environment)
        self.assertNotIn("DYLD_INSERT_LIBRARIES", environment)
        self.assertEqual(environment["PATH"], "/usr/bin")

    def test_state_recovery_environment_rejects_unknown_mode(self) -> None:
        with self.assertRaisesRegex(
            smoke.engine.LifecycleSmokeError,
            "unsupported packaged-state recovery mode",
        ):
            smoke.state_recovery_environment(
                {},
                home=Path("/tmp/home"),
                temporary=Path("/tmp/tmp"),
                identity_file=Path("/tmp/identity"),
                mode="unknown",
            )

    def test_verify_marker_accepts_only_exact_canonical_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "marker.json"
            expected = smoke.expected_marker(smoke.MIGRATION_MODE)
            payload = smoke.engine.canonical_json_bytes(expected)
            path.write_bytes(payload)

            record = smoke.verify_marker(path, smoke.MIGRATION_MODE)

            self.assertEqual(record["status"], "passed")
            self.assertEqual(record["size"], len(payload))
            self.assertEqual(
                record["sha256"],
                hashlib.sha256(payload).hexdigest(),
            )

            path.write_bytes(
                json.dumps(expected, indent=2, sort_keys=True).encode("ascii")
                + b"\n"
            )
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "not canonical",
            ):
                smoke.verify_marker(path, smoke.MIGRATION_MODE)

            failed = smoke.expected_marker(smoke.MIGRATION_MODE)
            failed["status"] = "failed"
            path.write_bytes(smoke.engine.canonical_json_bytes(failed))
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "differs",
            ):
                smoke.verify_marker(path, smoke.MIGRATION_MODE)

    def test_verify_marker_rejects_duplicate_json_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "marker.json"
            path.write_bytes(b'{"status":"passed","status":"passed"}\n')

            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "invalid JSON",
            ):
                smoke.verify_marker(path, smoke.MIGRATION_MODE)

    def test_write_and_remove_legacy_fixture_preserve_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy_path = root / "home/AetherLink" / smoke.LEGACY_FILENAME
            smoke.write_legacy_fixture(legacy_path)

            self.assertEqual(
                legacy_path.read_bytes(),
                smoke.CANARY_LEGACY_BYTES,
            )
            self.assertEqual(
                stat.S_IMODE(legacy_path.stat().st_mode),
                0o600,
            )
            self.assertEqual(
                stat.S_IMODE(legacy_path.parent.stat().st_mode),
                0o700,
            )

            preserved = smoke.remove_legacy_before_readback(
                legacy_path,
                root / "preserved",
            )
            self.assertFalse(legacy_path.exists())
            self.assertEqual(
                preserved.read_bytes(),
                smoke.CANARY_LEGACY_BYTES,
            )

    def test_write_legacy_fixture_refuses_existing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "existing" / smoke.LEGACY_FILENAME
            path.parent.mkdir()
            with self.assertRaises(FileExistsError):
                smoke.write_legacy_fixture(path)

    def test_sqlite_canary_evidence_accepts_exact_single_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / smoke.DATABASE_FILENAME
            self.write_sqlite_fixture(database)

            evidence = smoke.sqlite_canary_evidence(database)

        self.assertEqual(
            evidence,
            smoke.SQLiteCanaryEvidence(
                event_json_sha256=smoke.CANARY_EVENT_JSON_SHA256,
                event_json_size=344,
                integrity_check="ok",
                total_event_count=1,
            ),
        )

    def test_sqlite_canary_evidence_rejects_extra_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / smoke.DATABASE_FILENAME
            self.write_sqlite_fixture(database)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    INSERT INTO runtime_chat_events(
                        event_id,
                        timestamp,
                        kind,
                        request_id,
                        session_id,
                        owner_device_id,
                        model,
                        event_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "extra",
                        smoke.CANARY_TIMESTAMP,
                        "request",
                        "extra-request",
                        "extra-session",
                        None,
                        "extra-model",
                        "{}",
                    ),
                )

            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "exactly one event",
            ):
                smoke.sqlite_canary_evidence(database)

    def test_load_release_inputs_accepts_exact_fixture_and_rejects_bool_build(
        self,
    ) -> None:
        version = smoke.ReleaseVersion(12, "1.0.0", (1, 0, 0))
        with tempfile.TemporaryDirectory() as temporary:
            archive_dir = self.write_release_fixture(
                Path(temporary),
                version,
            )
            loaded = smoke.load_release_inputs(
                archive_dir,
                verify_readback=False,
                version=version,
            )
            self.assertEqual(
                loaded.archive_sha256,
                smoke.sha256_file(loaded.archive_path),
            )

            manifest_path = (
                archive_dir
                / f"{smoke.release_id_for(version)}.manifest.json"
            )
            manifest = json.loads(manifest_path.read_text())
            manifest["release"]["buildNumber"] = True
            manifest_path.write_bytes(
                smoke.engine.canonical_json_bytes(manifest)
            )
            with self.assertRaisesRegex(
                smoke.engine.LifecycleSmokeError,
                "unexpected release metadata",
            ):
                smoke.load_release_inputs(
                    archive_dir,
                    verify_readback=False,
                    version=version,
                )

    def test_verify_packaged_app_binds_plist_and_manifest_executable(
        self,
    ) -> None:
        version = smoke.ReleaseVersion(12, "1.0.0", (1, 0, 0))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "AetherLink.app"
            info = app / smoke.engine.INFO_PLIST_RELATIVE_PATH
            executable = app / smoke.engine.EXECUTABLE_RELATIVE_PATH
            info.parent.mkdir(parents=True)
            executable.parent.mkdir(parents=True)
            info.write_bytes(
                plistlib.dumps(
                    {
                        "CFBundleIdentifier": (
                            smoke.engine.EXPECTED_BUNDLE_ID
                        ),
                        "CFBundleShortVersionString": (
                            version.marketing_version
                        ),
                        "CFBundleVersion": str(version.build_number),
                    }
                )
            )
            executable.write_bytes(b"binary")
            executable.chmod(0o755)
            member = (
                smoke.engine.APP_MEMBER_PREFIX
                + smoke.engine.EXECUTABLE_RELATIVE_PATH.as_posix()
            )
            release = smoke.engine.ReleaseInputs(
                archive_dir=root,
                archive_path=root / "archive.zip",
                manifest_path=root / "manifest.json",
                checksum_path=root / "checksum",
                archive_sha256="0" * 64,
                manifest_sha256="1" * 64,
                manifest={
                    "members": [
                        {
                            "mode": "0755",
                            "path": member,
                            "sha256": hashlib.sha256(b"binary").hexdigest(),
                            "size": 6,
                        }
                    ],
                    "platforms": {"macos": {"uuid": "TEST-UUID"}},
                },
            )

            with patch.object(smoke.engine, "run_checked"):
                metadata = smoke.verify_packaged_app(
                    app,
                    release,
                    version=version,
                )

        self.assertEqual(metadata["buildNumber"], 12)
        self.assertEqual(
            metadata["executableSha256"],
            hashlib.sha256(b"binary").hexdigest(),
        )

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

    def write_sqlite_fixture(self, path: Path) -> None:
        with sqlite3.connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE runtime_chat_events(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    owner_device_id TEXT,
                    model TEXT NOT NULL,
                    event_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO runtime_chat_events(
                    event_id,
                    timestamp,
                    kind,
                    request_id,
                    session_id,
                    owner_device_id,
                    model,
                    event_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    smoke.CANARY_EVENT_ID,
                    smoke.CANARY_TIMESTAMP,
                    "request",
                    smoke.CANARY_REQUEST_ID,
                    smoke.CANARY_SESSION_ID,
                    None,
                    smoke.CANARY_MODEL,
                    smoke.CANARY_EVENT_JSON.decode("ascii"),
                ),
            )

    def write_release_fixture(
        self,
        root: Path,
        version: smoke.ReleaseVersion,
    ) -> Path:
        release_id = smoke.release_id_for(version)
        archive_dir = root / release_id
        archive_dir.mkdir()
        archive_path = archive_dir / f"{release_id}.zip"
        manifest_path = archive_dir / f"{release_id}.manifest.json"
        checksum_path = archive_dir / f"{release_id}.zip.sha256"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("fixture", b"fixture")
        manifest_path.write_bytes(
            smoke.engine.canonical_json_bytes(
                {
                    "release": {
                        "buildNumber": version.build_number,
                        "marketingVersion": version.marketing_version,
                        "releaseId": release_id,
                    }
                }
            )
        )
        checksum_path.write_text(
            f"{smoke.sha256_file(archive_path)}  {archive_path.name}\n",
            encoding="ascii",
        )
        return archive_dir


if __name__ == "__main__":
    unittest.main()
