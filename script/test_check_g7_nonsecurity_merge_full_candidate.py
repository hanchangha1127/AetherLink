#!/usr/bin/env python3
"""Portable tests for the local non-security G7 candidate checker."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from script import check_g7_nonsecurity_merge_full_candidate as checker


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class CandidateFixture:
    def __init__(self, temporary: str) -> None:
        self.root = Path(temporary)
        subprocess.run(
            ("git", "init", "-q", str(self.root)),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._write(Path(".gitignore"), b".build/\napps/android/app/build/\ndist/\n")
        self._write(Path("source.txt"), b"current product source\n")
        self._write(Path("README.md"), b"excluded readme\n")
        self._write(Path("docs/excluded.md"), b"excluded docs\n")
        for relative in checker.EXPECTED_IMPLEMENTATION_PATHS:
            self._write(relative, f"fixture {relative.as_posix()}\n".encode("ascii"))
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "add",
                ".gitignore",
                "source.txt",
                "README.md",
                "docs/excluded.md",
                *(path.as_posix() for path in checker.EXPECTED_IMPLEMENTATION_PATHS),
            ),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for relative in checker.EXPECTED_ARTIFACT_PATHS:
            if relative == checker.ANDROID_LINT_XML_PATH:
                data = b'<?xml version="1.0" encoding="UTF-8"?>\n<issues format="6" />\n'
            else:
                data = f"artifact {relative.as_posix()}\n".encode("ascii")
            executable = relative in {
                Path("dist/unsealed-package-only/AetherLink.app/Contents/MacOS/AetherLink")
            }
            self._write(relative, data, mode=0o755 if executable else 0o644)

    def _write(self, relative: Path, data: bytes, *, mode: int = 0o644) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)

    def document(self, *, requested_pid: bool = True) -> dict[str, object]:
        command_records = []
        for command_id in checker.EXPECTED_COMMAND_IDS:
            argv = checker.CRITICAL_COMMAND_ARGV.get(
                command_id,
                ("fixture-command", command_id),
            )
            command_records.append(
                {
                    "argv": list(argv),
                    "cwd": ".",
                    "elapsedMilliseconds": 1,
                    "exitCode": 0,
                    "id": command_id,
                    "stderr": {"sha256": EMPTY_SHA256, "size": 0},
                    "stdout": {"sha256": EMPTY_SHA256, "size": 0},
                    "timeoutSeconds": 60,
                }
            )
        if requested_pid:
            pid = {
                "after": "59809|2026-07-19T14:46:40+09:00|dist/AetherLink.app",
                "before": "59809|2026-07-19T14:46:40+09:00|dist/AetherLink.app",
                "pid": 59809,
                "preservedDuringRun": True,
                "requested": True,
            }
        else:
            pid = {
                "after": "",
                "before": "",
                "pid": 0,
                "preservedDuringRun": False,
                "requested": False,
            }
        return {
            "artifacts": [
                checker.file_record(
                    self.root,
                    relative,
                    maximum_bytes=checker.ARTIFACT_MAX_BYTES,
                )
                for relative in checker.EXPECTED_ARTIFACT_PATHS
            ],
            "commands": command_records,
            "contract": checker.CONTRACT,
            "coverage": dict(checker.EXPECTED_COVERAGE),
            "implementation": [
                checker.file_record(
                    self.root,
                    relative,
                    maximum_bytes=checker.ARTIFACT_MAX_BYTES,
                )
                for relative in checker.EXPECTED_IMPLEMENTATION_PATHS
            ],
            "limitations": dict(checker.EXPECTED_LIMITATIONS),
            "pidPreservation": pid,
            "result": "passed",
            "schemaVersion": checker.SCHEMA_VERSION,
            "source": checker.source_snapshot(self.root),
        }

    def write_result(self, document: object, *, canonical: bool = True) -> Path:
        path = self.root / checker.RESULT_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        if canonical:
            data = checker.canonical_json_bytes(document)
        else:
            data = json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        path.write_bytes(data)
        path.chmod(0o600)
        return path


class G7NonsecurityMergeFullCandidateCheckerTests(unittest.TestCase):
    def with_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], CandidateFixture]:
        temporary = tempfile.TemporaryDirectory()
        return temporary, CandidateFixture(temporary.name)

    def assert_rejected(self, fixture: CandidateFixture, document: object) -> None:
        with self.assertRaises(checker.CandidateError):
            checker.validate_document(document, root=fixture.root, run_readbacks=False)

    def test_baseline_and_unrequested_pid_seam_pass(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            checker.validate_document(
                fixture.document(), root=fixture.root, run_readbacks=False
            )
            checker.validate_document(
                fixture.document(requested_pid=False),
                root=fixture.root,
                run_readbacks=False,
            )

    def test_duplicate_json_key_is_rejected(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            raw = checker.canonical_json_bytes(document)
            needle = b'"result":"passed"'
            self.assertIn(needle, raw)
            duplicated = raw.replace(
                needle,
                b'"result":"passed","result":"passed"',
                1,
            )
            path = fixture.root / checker.RESULT_RELATIVE_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(duplicated)
            path.chmod(0o600)
            with self.assertRaises(checker.CandidateError):
                checker.load_result(path, root=fixture.root)

    def test_boolean_count_is_rejected(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            coverage = document["coverage"]
            self.assertIsInstance(coverage, dict)
            coverage["swiftFocusedTests"] = True
            self.assert_rejected(fixture, document)

    def test_source_drift_is_rejected_but_excluded_docs_do_not_bind(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            (fixture.root / "source.txt").write_bytes(b"drifted source\n")
            self.assert_rejected(fixture, document)

            repaired = fixture.document()
            (fixture.root / "README.md").write_bytes(b"changed excluded readme\n")
            (fixture.root / "docs/excluded.md").write_bytes(b"changed excluded docs\n")
            checker.validate_document(repaired, root=fixture.root, run_readbacks=False)

    def test_artifact_symlink_and_byte_drift_are_rejected(self) -> None:
        for mutation in ("symlink", "bytes"):
            with self.subTest(mutation=mutation):
                temporary, fixture = self.with_fixture()
                with temporary:
                    document = fixture.document()
                    relative = checker.EXPECTED_ARTIFACT_PATHS[0]
                    path = fixture.root / relative
                    if mutation == "symlink":
                        path.unlink()
                        target = fixture.root / "source.txt"
                        path.symlink_to(target)
                    else:
                        path.write_bytes(b"mutated artifact\n")
                    self.assert_rejected(fixture, document)

    def test_unknown_top_level_key_is_rejected(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            document["unexpected"] = False
            self.assert_rejected(fixture, document)

    def test_lint_issue_is_rejected_even_when_artifact_record_is_current(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            lint_path = fixture.root / checker.ANDROID_LINT_XML_PATH
            lint_path.write_bytes(
                b'<issues format="6"><issue id="FixtureIssue" severity="Warning" /></issues>\n'
            )
            artifact_index = checker.EXPECTED_ARTIFACT_PATHS.index(
                checker.ANDROID_LINT_XML_PATH
            )
            artifacts = document["artifacts"]
            self.assertIsInstance(artifacts, list)
            artifacts[artifact_index] = checker.file_record(
                fixture.root,
                checker.ANDROID_LINT_XML_PATH,
                maximum_bytes=checker.ARTIFACT_MAX_BYTES,
            )
            self.assert_rejected(fixture, document)

    def test_true_qualification_claim_is_rejected(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            limitations = document["limitations"]
            self.assertIsInstance(limitations, dict)
            limitations["canonicalMergeFullClaimed"] = True
            self.assert_rejected(fixture, document)

    def test_pid_identity_mismatch_and_boolean_pid_are_rejected(self) -> None:
        for key, value in (("after", "different identity"), ("pid", True)):
            with self.subTest(key=key):
                temporary, fixture = self.with_fixture()
                with temporary:
                    document = fixture.document()
                    pid = document["pidPreservation"]
                    self.assertIsInstance(pid, dict)
                    pid[key] = value
                    self.assert_rejected(fixture, document)

    def test_noncanonical_json_is_rejected(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            path = fixture.write_result(fixture.document(), canonical=False)
            with self.assertRaises(checker.CandidateError):
                checker.load_result(path, root=fixture.root)

    def test_result_mode_and_trailing_lf_are_closed(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            path = fixture.write_result(document)
            path.chmod(0o644)
            with self.assertRaises(checker.CandidateError):
                checker.load_result(path, root=fixture.root)
            path.write_bytes(checker.canonical_json_bytes(document).rstrip(b"\n"))
            path.chmod(0o600)
            with self.assertRaises(checker.CandidateError):
                checker.load_result(path, root=fixture.root)

    def test_artifact_order_and_command_id_sequence_are_closed(self) -> None:
        temporary, fixture = self.with_fixture()
        with temporary:
            document = fixture.document()
            artifacts = document["artifacts"]
            self.assertIsInstance(artifacts, list)
            artifacts[0], artifacts[1] = artifacts[1], artifacts[0]
            self.assert_rejected(fixture, document)

            document = fixture.document()
            commands = document["commands"]
            self.assertIsInstance(commands, list)
            first = commands[0]
            self.assertIsInstance(first, dict)
            first["id"] = "different"
            self.assert_rejected(fixture, document)


if __name__ == "__main__":
    unittest.main()
