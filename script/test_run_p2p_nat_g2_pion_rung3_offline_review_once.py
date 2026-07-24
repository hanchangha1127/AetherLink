#!/usr/bin/env python3
"""Synthetic-only tests for the one-use G2 Pion rung-three review runner.

The retained production archive is never opened by this suite.  Every execution
test redirects the runner to an owner-controlled temporary root containing a
small synthetic ZIP, while preflight tests replace repository authority reads
with a closed in-memory fixture.
"""

from __future__ import annotations

import ast
import builtins
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "script/run_p2p_nat_g2_pion_rung3_offline_review_once.py"
PURE_MODULE_PATH = ROOT / "script/p2p_nat_g2_pion_offline_zip.py"


def load_source_without_importlib(
    path: Path,
    *,
    name: str,
    compile_name: str,
) -> ModuleType:
    module = ModuleType(name)
    module.__file__ = str(path)
    raw = path.read_bytes()
    code = compile(
        raw,
        compile_name,
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    )
    exec(code, module.__dict__, module.__dict__)
    return module


RUNNER = load_source_without_importlib(
    RUNNER_PATH,
    name="g2_pion_rung3_review_runner",
    compile_name="script/run_p2p_nat_g2_pion_rung3_offline_review_once.py",
)
OFFLINE_ZIP = load_source_without_importlib(
    PURE_MODULE_PATH,
    name="g2_pion_offline_zip_runner_test",
    compile_name="script/p2p_nat_g2_pion_offline_zip.py",
)


SOURCE_BODY_SENTINEL = "SYNTHETIC_SOURCE_BODY_MUST_NOT_APPEAR_IN_REPORT_7f40db"
SYNTHETIC_SOURCE = f"""package ice

// {SOURCE_BODY_SENTINEL}
func boundedReviewCandidates() {{
    Dial()
    Debugf("synthetic-password-marker")
    OnConnectionStateChange()
    SetDeadline()
    _ = udp
    _ = Resolver{{}}
    _ = nonce
}}
""".encode()

SYNTHETIC_ENTRIES = (
    (
        "go.mod",
        b"module github.com/pion/ice/v4\n"
        b"go 1.23\n"
        b"require example.invalid/dependency v1.2.3\n",
    ),
    (
        "go.sum",
        b"example.invalid/dependency v1.2.3 h1:c3ludGhldGlj\n",
    ),
    ("review_candidates.go", SYNTHETIC_SOURCE),
    ("LICENSE", b"synthetic license inventory fixture\n"),
)


def authority_fixture() -> dict[str, object]:
    return {
        "permit": {
            "permitId": "g2-pion-rung3-offline-review-execution-permit-v1",
        },
        "permitRawSha256": "a" * 64,
        "permitSemanticSha256": "b" * 64,
    }


def make_synthetic_zip(
    entries: tuple[tuple[str, bytes], ...] = SYNTHETIC_ENTRIES,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for relative_path, content in entries:
                info = zipfile.ZipInfo(
                    RUNNER.MODULE_PREFIX + relative_path,
                    date_time=(2026, 7, 23, 0, 0, 0),
                )
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
    return output.getvalue()


def altered_stat(metadata: os.stat_result, **changes: int) -> SimpleNamespace:
    values = {
        name: getattr(metadata, name)
        for name in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
    }
    values.update(changes)
    return SimpleNamespace(**values)


def strings_in(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        output: list[str] = []
        for key, item in value.items():
            output.extend(strings_in(key))
            output.extend(strings_in(item))
        return output
    if isinstance(value, list):
        output = []
        for item in value:
            output.extend(strings_in(item))
        return output
    return []


@contextmanager
def synthetic_execution_environment(
    temporary_root: str,
    *,
    raw_archive: bytes | None = None,
):
    """Redirect every mutable/readable execution path to one temporary root."""

    root = Path(temporary_root)
    archive = make_synthetic_zip() if raw_archive is None else raw_archive
    archive_relative = "build/synthetic-pion-v4.3.0.zip"
    archive_path = root / archive_relative
    archive_path.parent.mkdir(mode=0o700)
    archive_path.write_bytes(archive)
    archive_path.chmod(0o600)
    total_uncompressed = sum(len(content) for _, content in SYNTHETIC_ENTRIES)
    checker = ModuleType("synthetic_execution_permit_checker")
    checker.validate_repository = mock.Mock(return_value=authority_fixture())
    checker.load_validated_pure_module = mock.Mock(return_value=OFFLINE_ZIP)
    receipt_mock = mock.Mock(return_value=archive_relative)

    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(RUNNER, "ROOT", root))
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "OUTPUT_PARENT",
                RUNNER.PurePosixPath("build/synthetic-review-v1"),
            )
        )
        stack.enter_context(
            mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_BYTES", len(archive))
        )
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "EXPECTED_ARCHIVE_SHA256",
                hashlib.sha256(archive).hexdigest(),
            )
        )
        stack.enter_context(
            mock.patch.object(RUNNER, "EXPECTED_ENTRY_COUNT", len(SYNTHETIC_ENTRIES))
        )
        stack.enter_context(
            mock.patch.object(RUNNER, "EXPECTED_FILE_COUNT", len(SYNTHETIC_ENTRIES))
        )
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "EXPECTED_TOTAL_UNCOMPRESSED_BYTES",
                total_uncompressed,
            )
        )
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "load_checker_trust_root",
                return_value=checker,
            )
        )
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "read_pinned_receipt_archive_path",
                receipt_mock,
            )
        )
        yield {
            "root": root,
            "archive": archive_path,
            "output": root / "build/synthetic-review-v1",
            "raw": archive,
            "checker": checker,
            "receiptMock": receipt_mock,
        }


class G2PionRung3OfflineReviewRunnerTests(unittest.TestCase):
    def test_00_nonisolated_source_stops_after_builtin_sys_import(self) -> None:
        source = RUNNER_PATH.read_bytes()
        fake_flags = SimpleNamespace(
            isolated=0,
            dont_write_bytecode=0,
            ignore_environment=0,
            no_user_site=0,
            optimize=0,
        )
        original_import = builtins.__import__
        observed_imports: list[str] = []

        def import_probe(
            name: str,
            globals_value: object = None,
            locals_value: object = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            observed_imports.append(name)
            if name not in {"__future__", "sys"}:
                raise AssertionError(f"non-builtin import reached before isolation guard: {name}")
            return original_import(
                name,
                globals_value,
                locals_value,
                fromlist,
                level,
            )

        namespace = {
            "__file__": "script/run_p2p_nat_g2_pion_rung3_offline_review_once.py",
            "__name__": "nonisolated_runner_probe",
        }
        with (
            mock.patch.object(sys, "flags", fake_flags),
            mock.patch.object(builtins, "__import__", import_probe),
        ):
            with self.assertRaisesRegex(RuntimeError, "python3 -I -B"):
                exec(
                    compile(
                        source,
                        "script/run_p2p_nat_g2_pion_rung3_offline_review_once.py",
                        "exec",
                        flags=0,
                        dont_inherit=True,
                        optimize=0,
                    ),
                    namespace,
                    namespace,
                )
        self.assertEqual(observed_imports, ["__future__", "sys"])

    def test_00b_checker_bootstrap_is_stable_nofollow_and_pyc_free(self) -> None:
        checker_source = b"""
def validate_repository(root):
    return {"root": str(root)}

def load_validated_pure_module(root):
    return {"root": str(root)}
"""
        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            script = root / "script"
            script.mkdir(mode=0o700)
            checker = script / "check_p2p_nat_g2_pion_rung3_execution_permit.py"
            checker.write_bytes(checker_source)
            checker.chmod(0o600)
            with (
                mock.patch.object(RUNNER, "ROOT", root),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("checker source path was reopened"),
                ) as path_read_mock,
                mock.patch.object(
                    builtins,
                    "open",
                    side_effect=AssertionError("builtin open is forbidden"),
                ) as builtin_open_mock,
            ):
                first = RUNNER.load_checker_trust_root()
                second = RUNNER.load_checker_trust_root()
            self.assertIsInstance(first, ModuleType)
            self.assertIsInstance(second, ModuleType)
            self.assertIsNot(first, second)
            self.assertEqual(first.__file__, RUNNER.CHECKER_SOURCE_PATH)
            self.assertEqual(
                first.validate_repository(root),
                {"root": str(root)},
            )
            self.assertTrue(sys.dont_write_bytecode)
            self.assertEqual(list(root.rglob("__pycache__")), [])
            path_read_mock.assert_not_called()
            builtin_open_mock.assert_not_called()

        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = root / "checker-target.py"
            target.write_bytes(checker_source)
            target.chmod(0o600)
            (script / "check_p2p_nat_g2_pion_rung3_execution_permit.py").symlink_to(
                target
            )
            with mock.patch.object(RUNNER, "ROOT", root):
                with self.assertRaises(RUNNER.ReviewError):
                    RUNNER.load_checker_trust_root()

        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            script = root / "script"
            script.mkdir(mode=0o700)
            checker = script / "check_p2p_nat_g2_pion_rung3_execution_permit.py"
            checker.write_bytes(checker_source)
            checker.chmod(0o600)
            with (
                mock.patch.object(RUNNER, "ROOT", root),
                mock.patch.object(sys, "path", [*sys.path, str(root)]),
            ):
                with self.assertRaisesRegex(
                    RUNNER.ReviewError,
                    "search path",
                ):
                    RUNNER.load_checker_trust_root()

    def test_00c_checker_bootstrap_rejects_metadata_and_toctou_drift(self) -> None:
        checker_source = (
            b"def validate_repository(root): return {}\n"
            b"def load_validated_pure_module(root): return None\n"
        )
        for failure in ("mode", "link", "owner", "size", "toctou"):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as temporary_root:
                    root = Path(temporary_root)
                    script = root / "script"
                    script.mkdir(mode=0o700)
                    checker = (
                        script
                        / "check_p2p_nat_g2_pion_rung3_execution_permit.py"
                    )
                    checker.write_bytes(checker_source)
                    checker.chmod(0o600)
                    if failure == "mode":
                        checker.chmod(0o620)
                    elif failure == "link":
                        os.link(checker, script / "checker-hardlink.py")

                    patches: list[object] = [
                        mock.patch.object(RUNNER, "ROOT", root)
                    ]
                    if failure == "size":
                        patches.append(
                            mock.patch.object(
                                RUNNER,
                                "MAXIMUM_TRUST_ROOT_SOURCE_BYTES",
                                len(checker_source) - 1,
                            )
                        )
                    elif failure in {"owner", "toctou"}:
                        real_fstat = os.fstat
                        regular_count = 0

                        def drifted_fstat(
                            fd: int,
                        ) -> os.stat_result | SimpleNamespace:
                            nonlocal regular_count
                            metadata = real_fstat(fd)
                            if not stat.S_ISREG(metadata.st_mode):
                                return metadata
                            regular_count += 1
                            if failure == "owner":
                                return altered_stat(
                                    metadata,
                                    st_uid=metadata.st_uid + 1,
                                )
                            if regular_count == 2:
                                return altered_stat(
                                    metadata,
                                    st_ctime_ns=metadata.st_ctime_ns + 1,
                                )
                            return metadata

                        patches.append(
                            mock.patch.object(
                                RUNNER.os,
                                "fstat",
                                drifted_fstat,
                            )
                        )
                    with ExitStack() as stack:
                        for patch in patches:
                            stack.enter_context(patch)  # type: ignore[arg-type]
                        with self.assertRaises(RUNNER.ReviewError):
                            RUNNER.load_checker_trust_root()

    def test_01_default_preflight_has_zero_archive_and_write_capability(self) -> None:
        standard_output = io.StringIO()
        standard_error = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary_root:
            with (
                mock.patch.object(
                    RUNNER,
                    "validate_authority",
                    return_value=authority_fixture(),
                ),
                mock.patch.object(
                    RUNNER,
                    "execute_permit",
                    side_effect=AssertionError("default mode must not execute"),
                ) as execute_mock,
                mock.patch.object(
                    RUNNER,
                    "open_relative_regular_file",
                    side_effect=AssertionError("preflight must not open an archive"),
                ) as archive_open_mock,
                mock.patch.object(
                    RUNNER,
                    "create_claim",
                    side_effect=AssertionError("preflight must not create a claim"),
                ) as claim_mock,
                redirect_stdout(standard_output),
                redirect_stderr(standard_error),
            ):
                self.assertEqual(RUNNER.main([]), 0)
            self.assertEqual(list(Path(temporary_root).iterdir()), [])
        result = json.loads(standard_output.getvalue())
        self.assertEqual(
            result["status"],
            "permit_validated_consumption_state_not_inspected",
        )
        self.assertEqual(result["permitConsumptionState"], "not_inspected")
        self.assertEqual(result["archiveOpenCount"], 0)
        self.assertEqual(result["archiveReadPassCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertEqual(result["reviewedSourceCompilerInvocationCount"], 0)
        self.assertEqual(
            result["verifiedAuxiliaryToolModulePythonCompileCount"],
            1,
        )
        self.assertNotIn("compilerInvocationCount", result)
        self.assertFalse(result["reviewPerformed"])
        self.assertFalse(result["userActionRequired"])
        self.assertEqual(standard_error.getvalue(), "")
        execute_mock.assert_not_called()
        archive_open_mock.assert_not_called()
        claim_mock.assert_not_called()

    def test_02_unknown_or_conflicting_cli_flags_are_rejected_before_work(self) -> None:
        for arguments in (
            ["--unknown"],
            ["--check-permit", "--execute-permit"],
            ["--execute-permit=true"],
            ["synthetic.zip"],
        ):
            with self.subTest(arguments=arguments):
                with (
                    mock.patch.object(RUNNER, "check_permit") as check_mock,
                    mock.patch.object(RUNNER, "execute_permit") as execute_mock,
                    redirect_stdout(io.StringIO()),
                    redirect_stderr(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit) as raised:
                        RUNNER.main(arguments)
                self.assertEqual(raised.exception.code, 2)
                check_mock.assert_not_called()
                execute_mock.assert_not_called()

    def test_03_claim_is_owner_only_durable_and_replay_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_fd = os.open(
                temporary_directory,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                payload, digest = RUNNER.create_claim(directory_fd, "c" * 64)
                claim = json.loads(payload)
                claim_path = Path(temporary_directory) / RUNNER.CLAIM_NAME
                metadata = claim_path.stat()
                self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
                self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
                self.assertEqual(metadata.st_nlink, 1)
                self.assertFalse(claim["automaticRetryAllowed"])
                self.assertFalse(claim["externalIdentityProofRequired"])
                self.assertFalse(claim["repositoryOwnerAuthenticationRequired"])
                self.assertFalse(claim["userActionRequired"])
                with self.assertRaisesRegex(
                    RUNNER.ReviewError,
                    "already exists",
                ):
                    RUNNER.create_claim(directory_fd, "c" * 64)
                self.assertEqual(claim_path.read_bytes(), payload)
            finally:
                os.close(directory_fd)

    def test_03b_claim_loser_and_initialization_failures_never_unlink_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_fd = os.open(
                temporary_directory,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                with (
                    mock.patch.object(RUNNER, "name_exists", return_value=False),
                    mock.patch.object(
                        RUNNER.os,
                        "open",
                        side_effect=FileExistsError("synthetic race loser"),
                    ),
                    mock.patch.object(RUNNER.os, "unlink") as unlink_mock,
                ):
                    with self.assertRaisesRegex(
                        RUNNER.ReviewError,
                        "already consumed",
                    ):
                        RUNNER.create_claim(directory_fd, "d" * 64)
                unlink_mock.assert_not_called()
            finally:
                os.close(directory_fd)

        for failure in ("malformed", "fsync"):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    directory_fd = os.open(
                        temporary_directory,
                        os.O_RDONLY
                        | os.O_DIRECTORY
                        | getattr(os, "O_CLOEXEC", 0),
                    )
                    try:
                        if failure == "malformed":
                            failure_patch = mock.patch.object(
                                RUNNER,
                                "write_all",
                                side_effect=OSError("forced short initialization"),
                            )
                        else:
                            failure_patch = mock.patch.object(
                                RUNNER.os,
                                "fsync",
                                side_effect=OSError("forced durability uncertainty"),
                            )
                        with failure_patch:
                            with self.assertRaises(OSError):
                                RUNNER.create_claim(directory_fd, "e" * 64)
                        claim_path = Path(temporary_directory) / RUNNER.CLAIM_NAME
                        self.assertTrue(claim_path.exists())
                        with self.assertRaisesRegex(
                            RUNNER.ReviewError,
                            "already exists",
                        ):
                            RUNNER.create_claim(directory_fd, "e" * 64)
                    finally:
                        os.close(directory_fd)

    def test_04_safe_archive_open_rejects_symlinks_mode_links_owner_and_size(self) -> None:
        self.assertTrue(
            RUNNER.file_open_flags() & getattr(os, "O_NOFOLLOW", 0),
            "the platform and runner must provide O_NOFOLLOW",
        )

        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            build = root / "build"
            build.mkdir(mode=0o700)
            target = root / "target.zip"
            target.write_bytes(b"safe")
            target.chmod(0o600)
            (build / "archive.zip").symlink_to(target)
            with mock.patch.object(RUNNER, "ROOT", root):
                with self.assertRaises(RUNNER.ReviewError):
                    RUNNER.open_relative_regular_file(
                        "build/archive.zip",
                        maximum_bytes=8,
                    )

        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            actual = root / "actual"
            actual.mkdir(mode=0o700)
            archive = actual / "archive.zip"
            archive.write_bytes(b"safe")
            archive.chmod(0o600)
            (root / "build").symlink_to(actual)
            with mock.patch.object(RUNNER, "ROOT", root):
                with self.assertRaises(RUNNER.ReviewError):
                    RUNNER.open_relative_regular_file(
                        "build/archive.zip",
                        maximum_bytes=8,
                    )

        for failure in ("mode", "link", "owner", "size"):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as temporary_root:
                    root = Path(temporary_root)
                    build = root / "build"
                    build.mkdir(mode=0o700)
                    archive = build / "archive.zip"
                    archive.write_bytes(b"safe")
                    archive.chmod(0o600)
                    maximum_bytes = 8
                    if failure == "mode":
                        archive.chmod(0o644)
                    elif failure == "link":
                        os.link(archive, build / "second-link.zip")
                    elif failure == "size":
                        maximum_bytes = 3

                    patches: list[object] = [mock.patch.object(RUNNER, "ROOT", root)]
                    if failure == "owner":
                        real_fstat = os.fstat

                        def owner_drift(fd: int) -> os.stat_result | SimpleNamespace:
                            metadata = real_fstat(fd)
                            if stat.S_ISREG(metadata.st_mode):
                                return altered_stat(
                                    metadata,
                                    st_uid=metadata.st_uid + 1,
                                )
                            return metadata

                        patches.append(mock.patch.object(RUNNER.os, "fstat", owner_drift))
                    with ExitStack() as stack:
                        for patch in patches:
                            stack.enter_context(patch)  # type: ignore[arg-type]
                        with self.assertRaises(RUNNER.ReviewError):
                            RUNNER.open_relative_regular_file(
                                "build/archive.zip",
                                maximum_bytes=maximum_bytes,
                            )

    def test_05_stable_read_checks_hash_metadata_and_named_inode(self) -> None:
        raw = b"synthetic stable archive bytes"
        digest = hashlib.sha256(raw).hexdigest()

        def open_fixture(
            temporary_root: str,
        ) -> tuple[Path, int, int, str]:
            root = Path(temporary_root)
            build = root / "build"
            build.mkdir(mode=0o700)
            archive = build / "archive.zip"
            archive.write_bytes(raw)
            archive.chmod(0o600)
            root_patch = mock.patch.object(RUNNER, "ROOT", root)
            root_patch.start()
            self.addCleanup(root_patch.stop)
            file_fd, parent_fd, name = RUNNER.open_relative_regular_file(
                "build/archive.zip",
                maximum_bytes=len(raw),
            )
            return archive, file_fd, parent_fd, name

        with tempfile.TemporaryDirectory() as temporary_root:
            archive, file_fd, parent_fd, name = open_fixture(temporary_root)
            try:
                with (
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_BYTES", len(raw)),
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_SHA256", digest),
                ):
                    observed, metadata = RUNNER.read_one_stable_archive_fd(
                        file_fd,
                        parent_fd,
                        name,
                    )
                self.assertEqual(observed, raw)
                self.assertEqual(metadata.st_ino, archive.stat().st_ino)
            finally:
                os.close(file_fd)
                os.close(parent_fd)

        with tempfile.TemporaryDirectory() as temporary_root:
            _, file_fd, parent_fd, name = open_fixture(temporary_root)
            try:
                with (
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_BYTES", len(raw)),
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_SHA256", "0" * 64),
                ):
                    with self.assertRaisesRegex(RUNNER.ReviewError, "SHA-256"):
                        RUNNER.read_one_stable_archive_fd(file_fd, parent_fd, name)
            finally:
                os.close(file_fd)
                os.close(parent_fd)

        with tempfile.TemporaryDirectory() as temporary_root:
            _, file_fd, parent_fd, name = open_fixture(temporary_root)
            real_fstat = os.fstat
            file_fstat_count = 0

            def metadata_drift(fd: int) -> os.stat_result | SimpleNamespace:
                nonlocal file_fstat_count
                metadata = real_fstat(fd)
                if fd == file_fd:
                    file_fstat_count += 1
                    if file_fstat_count == 2:
                        return altered_stat(
                            metadata,
                            st_mtime_ns=metadata.st_mtime_ns + 1,
                        )
                return metadata

            try:
                with (
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_BYTES", len(raw)),
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_SHA256", digest),
                    mock.patch.object(RUNNER.os, "fstat", metadata_drift),
                ):
                    with self.assertRaisesRegex(
                        RUNNER.ReviewError,
                        "metadata changed",
                    ):
                        RUNNER.read_one_stable_archive_fd(file_fd, parent_fd, name)
            finally:
                os.close(file_fd)
                os.close(parent_fd)

        with tempfile.TemporaryDirectory() as temporary_root:
            archive, file_fd, parent_fd, name = open_fixture(temporary_root)
            replacement = archive.with_name("replacement.zip")
            replacement.write_bytes(raw)
            replacement.chmod(0o600)
            os.replace(replacement, archive)
            try:
                with (
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_BYTES", len(raw)),
                    mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_SHA256", digest),
                ):
                    with self.assertRaisesRegex(
                        RUNNER.ReviewError,
                        "no longer names",
                    ):
                        RUNNER.read_one_stable_archive_fd(file_fd, parent_fd, name)
            finally:
                os.close(file_fd)
                os.close(parent_fd)

    def test_06_report_publication_is_owner_only_atomic_and_no_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_fd = os.open(
                temporary_directory,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                payload = b'{"synthetic":true}\n'
                temporary_fd = RUNNER.create_temporary_report(
                    directory_fd,
                    "first.tmp",
                    payload,
                )
                os.close(temporary_fd)
                RUNNER.publish_no_replace(directory_fd, "first.tmp", "result.json")
                final_path = Path(temporary_directory) / "result.json"
                self.assertEqual(final_path.read_bytes(), payload)
                self.assertEqual(stat.S_IMODE(final_path.stat().st_mode), 0o600)
                self.assertEqual(final_path.stat().st_nlink, 1)
                self.assertFalse((Path(temporary_directory) / "first.tmp").exists())

                second_payload = b'{"synthetic":false}\n'
                temporary_fd = RUNNER.create_temporary_report(
                    directory_fd,
                    "second.tmp",
                    second_payload,
                )
                os.close(temporary_fd)
                with self.assertRaisesRegex(RUNNER.ReviewError, "already exists"):
                    RUNNER.publish_no_replace(
                        directory_fd,
                        "second.tmp",
                        "result.json",
                    )
                self.assertEqual(final_path.read_bytes(), payload)
                self.assertEqual(
                    (Path(temporary_directory) / "second.tmp").read_bytes(),
                    second_payload,
                )

                fault_fd = RUNNER.create_temporary_report(
                    directory_fd,
                    "fault.tmp",
                    b'{"partial":true}\n',
                )
                os.close(fault_fd)
                real_stat = os.stat

                def fail_post_link_stat(
                    path: object,
                    *args: object,
                    **kwargs: object,
                ) -> os.stat_result:
                    if path == "fault.json":
                        raise OSError("forced post-link validation failure")
                    return real_stat(path, *args, **kwargs)

                with mock.patch.object(RUNNER.os, "stat", fail_post_link_stat):
                    with self.assertRaisesRegex(
                        RUNNER.PublishedReportStateError,
                        "publication completion is uncertain",
                    ):
                        RUNNER.publish_no_replace(
                            directory_fd,
                            "fault.tmp",
                            "fault.json",
                        )
                self.assertTrue((Path(temporary_directory) / "fault.json").is_file())
                self.assertFalse((Path(temporary_directory) / "fault.tmp").exists())
            finally:
                os.close(directory_fd)

    def test_07_documents_are_deterministic_bounded_and_body_free(self) -> None:
        raw_archive = make_synthetic_zip()
        inspection = OFFLINE_ZIP.inspect_module_zip(
            raw_archive,
            module_prefix=RUNNER.MODULE_PREFIX,
        )
        reversed_inspection = dict(inspection)
        reversed_inspection["entries"] = tuple(reversed(inspection["entries"]))
        total_uncompressed = sum(len(content) for _, content in SYNTHETIC_ENTRIES)
        archive_metadata = SimpleNamespace(st_size=len(raw_archive))

        with (
            mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_BYTES", len(raw_archive)),
            mock.patch.object(
                RUNNER,
                "EXPECTED_ARCHIVE_SHA256",
                hashlib.sha256(raw_archive).hexdigest(),
            ),
            mock.patch.object(
                RUNNER,
                "EXPECTED_ENTRY_COUNT",
                len(SYNTHETIC_ENTRIES),
            ),
            mock.patch.object(
                RUNNER,
                "EXPECTED_FILE_COUNT",
                len(SYNTHETIC_ENTRIES),
            ),
            mock.patch.object(
                RUNNER,
                "EXPECTED_TOTAL_UNCOMPRESSED_BYTES",
                total_uncompressed,
            ),
        ):
            first = RUNNER.build_review_documents(
                authority=authority_fixture(),
                claim_sha256="c" * 64,
                archive_metadata=archive_metadata,
                inspection=inspection,
            )
            second = RUNNER.build_review_documents(
                authority=authority_fixture(),
                claim_sha256="c" * 64,
                archive_metadata=archive_metadata,
                inspection=reversed_inspection,
            )

        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])
        result = json.loads(first[0])
        manifest = json.loads(first[1])
        serialized = first[0].decode()
        self.assertEqual(
            result["status"],
            "rung3_candidate_inventory_recorded_awaiting_completion_manifest",
        )
        self.assertEqual(result["nextAction"], "publish_bound_completion_manifest")
        self.assertFalse(result["publicationCompletion"]["complete"])
        self.assertTrue(
            result["publicationCompletion"]["completionManifestRequired"]
        )
        self.assertEqual(
            result["operationCounters"][
                "reportPublicationCountBeforeResultPublication"
            ],
            0,
        )
        self.assertEqual(
            result["operationCounters"][
                "requiredReportPublicationCountForCompletion"
            ],
            2,
        )
        self.assertEqual(
            manifest["status"],
            (
                "rung3_candidate_location_inventory_committed_"
                "semantic_review_not_performed"
            ),
        )
        self.assertEqual(
            manifest["nextAction"],
            "prepare_separate_versioned_rung3_semantic_source_review_decision",
        )
        self.assertTrue(manifest["publication"]["soleCompletionMarker"])
        self.assertTrue(
            manifest["publication"]["boundResultPublicationComplete"]
        )
        self.assertFalse(manifest["publication"]["rungThreeComplete"])
        self.assertEqual(
            manifest["resultBinding"]["rawSha256"],
            hashlib.sha256(first[0]).hexdigest(),
        )
        self.assertEqual(manifest["resultBinding"]["bytes"], len(first[0]))
        self.assertNotIn(SOURCE_BODY_SENTINEL, serialized)
        self.assertNotIn('Debugf("synthetic-password-marker")', serialized)
        self.assertNotIn(str(ROOT), serialized)
        self.assertLessEqual(len(first[0]), RUNNER.MAXIMUM_JSON_REPORT_BYTES)
        self.assertLessEqual(len(first[1]), RUNNER.MAXIMUM_JSON_REPORT_BYTES)
        self.assertFalse(result["evidenceBoundary"]["sourceBodiesRecorded"])
        self.assertFalse(result["evidenceBoundary"]["absoluteArchivePathRecorded"])
        self.assertFalse(result["archiveEvidence"]["pathCopiedIntoReport"])
        self.assertTrue(all(not value.startswith("/") for value in strings_in(result)))
        self.assertTrue(all(not value.startswith("/") for value in strings_in(manifest)))

        patch_units = [
            row["patchUnit"] for row in result["patchUnitCandidateInventory"]
        ]
        verification_ids = [
            row["id"] for row in result["profileVerificationUnits"]
        ]
        self.assertEqual(tuple(patch_units), RUNNER.PATCH_UNITS)
        self.assertEqual(tuple(verification_ids), RUNNER.VERIFICATION_IDS)
        self.assertEqual(len(set(patch_units)), 7)
        self.assertEqual(len(set(verification_ids)), 8)
        self.assertTrue(
            all(row["hitCount"] > 0 for row in result["patchUnitCandidateInventory"])
        )
        self.assertEqual(
            {
                row["id"]: tuple(row["relatedPatchUnits"])
                for row in result["profileVerificationUnits"]
            },
            dict(RUNNER.VERIFICATION_CROSSWALK),
        )
        for row in result["profileVerificationUnits"]:
            self.assertEqual(
                set(row),
                {"id", "relatedPatchUnits", "status", "meaning"},
            )
            self.assertEqual(
                row["status"],
                (
                    "candidate_location_crosswalk_recorded_"
                    "required_check_not_executed"
                ),
            )
            self.assertEqual(
                row["meaning"],
                (
                    "candidate_location_crosswalk_only_not_semantic_review_"
                    "or_required_check_evidence"
                ),
            )

        for counter in (
            "materializationCount",
            "sourceWriteCount",
            "sourceExecuteCount",
            "subprocessCount",
            "shellCount",
            "dnsCount",
            "networkOperationCount",
            "socketCreateCount",
            "gitOperationCount",
            "packageManagerInvocationCount",
            "reviewedSourceCompilerInvocationCount",
            "deviceOperationCount",
        ):
            self.assertEqual(result["operationCounters"][counter], 0, counter)
        for boundary in (
            "archiveExtracted",
            "sourceMaterialized",
            "sourcePatched",
            "sourceExecuted",
            "dependencyInstalled",
            "reviewedSourceCompiled",
            "reviewedSourceCodeLoaded",
            "subprocessInvoked",
            "shellInvoked",
            "dnsUsed",
            "networkUsed",
            "socketCreated",
            "gitOperationPerformed",
            "deviceExecutionPerformed",
            "productionDeploymentAuthorized",
        ):
            self.assertFalse(result["executionBoundary"][boundary], boundary)
        self.assertTrue(
            result["executionBoundary"]["verifiedPinnedReviewToolModulesLoaded"]
        )
        self.assertTrue(
            result["executionBoundary"][
                "verifiedPinnedReviewToolModulesCompiledInMemory"
            ]
        )
        self.assertEqual(
            result["operationCounters"][
                "verifiedAuxiliaryToolModulePythonCompileCount"
            ],
            2,
        )
        self.assertFalse(
            result["evidenceBoundary"][
                "reviewedSourceCompileOrRuntimeEvidencePresent"
            ]
        )
        self.assertNotIn(
            "compilerInvocationCount",
            result["operationCounters"],
        )
        self.assertNotIn("compilerInvoked", result["executionBoundary"])
        self.assertNotIn(
            "compileOrRuntimeEvidencePresent",
            result["evidenceBoundary"],
        )
        self.assertTrue(
            result["executionBoundary"][
                "boundedCandidateLocationInventoryPerformed"
            ]
        )
        self.assertFalse(
            result["executionBoundary"]["semanticSourceReviewPerformed"]
        )
        self.assertFalse(result["executionBoundary"]["rungThreeComplete"])

    def test_08_synthetic_execute_publishes_two_reports_and_blocks_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                events: list[str] = []
                checker = environment["checker"]
                receipt_mock = environment["receiptMock"]
                checker.validate_repository.side_effect = (
                    lambda root: events.append("validate") or authority_fixture()
                )
                checker.load_validated_pure_module.side_effect = (
                    lambda root: events.append("pure-tool") or OFFLINE_ZIP
                )
                receipt_mock.side_effect = (
                    lambda permit: events.append("receipt")
                    or "build/synthetic-pion-v4.3.0.zip"
                )
                create_claim = RUNNER.create_claim

                def ordered_claim(directory_fd: int, permit_sha256: str):
                    events.append("claim")
                    return create_claim(directory_fd, permit_sha256)

                with mock.patch.object(
                    RUNNER,
                    "create_claim",
                    side_effect=ordered_claim,
                ):
                    run_result = RUNNER.execute_permit()
                self.assertEqual(
                    events[:4],
                    ["validate", "claim", "pure-tool", "receipt"],
                )
                output = environment["output"]
                claim_path = output / RUNNER.CLAIM_NAME
                result_path = output / RUNNER.RESULT_NAME
                manifest_path = output / RUNNER.MANIFEST_NAME
                self.assertTrue(claim_path.is_file())
                self.assertTrue(result_path.is_file())
                self.assertTrue(manifest_path.is_file())
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
                for path in (claim_path, result_path, manifest_path):
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                    self.assertEqual(path.stat().st_nlink, 1)
                self.assertEqual(run_result["archiveOpenCount"], 1)
                self.assertEqual(run_result["archiveReadPassCount"], 1)
                self.assertEqual(run_result["archiveEntryEnumerationCount"], 1)
                self.assertEqual(run_result["reportPublicationCount"], 2)
                self.assertEqual(run_result["sourceMaterializationCount"], 0)
                self.assertEqual(run_result["subprocessCount"], 0)
                self.assertEqual(run_result["networkOperationCount"], 0)
                self.assertEqual(run_result["socketCreateCount"], 0)
                self.assertEqual(
                    run_result["reviewedSourceCompilerInvocationCount"],
                    0,
                )
                self.assertEqual(
                    run_result[
                        "verifiedAuxiliaryToolModulePythonCompileCount"
                    ],
                    2,
                )
                self.assertNotIn("compilerInvocationCount", run_result)
                self.assertEqual(run_result["gitOperationCount"], 0)
                self.assertEqual(run_result["deviceOperationCount"], 0)
                self.assertEqual(
                    run_result["status"],
                    (
                        "rung3_candidate_location_inventory_committed_"
                        "semantic_review_not_performed"
                    ),
                )
                self.assertEqual(
                    run_result["nextAction"],
                    (
                        "prepare_separate_versioned_rung3_"
                        "semantic_source_review_decision"
                    ),
                )
                self.assertTrue(
                    run_result["boundedCandidateLocationInventoryPerformed"]
                )
                self.assertFalse(run_result["semanticSourceReviewPerformed"])
                self.assertFalse(run_result["rungThreeComplete"])

                result_payload = result_path.read_text(encoding="utf-8")
                self.assertNotIn(SOURCE_BODY_SENTINEL, result_payload)
                self.assertNotIn(str(environment["root"]), result_payload)
                persisted_result = json.loads(result_payload)
                persisted_manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
                self.assertEqual(
                    persisted_result["status"],
                    (
                        "rung3_candidate_inventory_recorded_"
                        "awaiting_completion_manifest"
                    ),
                )
                self.assertEqual(
                    persisted_result["operationCounters"][
                        "reportPublicationCountBeforeResultPublication"
                    ],
                    0,
                )
                self.assertEqual(
                    persisted_result["operationCounters"][
                        "requiredReportPublicationCountForCompletion"
                    ],
                    2,
                )
                self.assertEqual(
                    persisted_manifest["resultBinding"]["rawSha256"],
                    hashlib.sha256(result_path.read_bytes()).hexdigest(),
                )
                with mock.patch.object(
                    RUNNER,
                    "open_relative_regular_file",
                    wraps=RUNNER.open_relative_regular_file,
                ) as archive_open_mock:
                    with self.assertRaises(RUNNER.ReviewError):
                        RUNNER.execute_permit()
                archive_open_mock.assert_not_called()
                self.assertTrue(claim_path.is_file())
                self.assertEqual(
                    checker.load_validated_pure_module.call_count,
                    1,
                )
                self.assertEqual(receipt_mock.call_count, 1)

    def test_09_failure_after_archive_open_retains_claim_and_blocks_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                failing_zip_module = SimpleNamespace(
                    inspect_module_zip=mock.Mock(
                        side_effect=RuntimeError("forced synthetic review failure")
                    )
                )
                environment[
                    "checker"
                ].load_validated_pure_module.return_value = failing_zip_module
                with self.assertRaisesRegex(
                    RUNNER.ReviewError,
                    "offline ZIP validation failed",
                ):
                    RUNNER.execute_permit()
                output = environment["output"]
                claim_path = output / RUNNER.CLAIM_NAME
                self.assertTrue(claim_path.is_file())
                self.assertFalse((output / RUNNER.RESULT_NAME).exists())
                self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
                self.assertFalse((output / RUNNER.TEMP_RESULT_NAME).exists())
                self.assertFalse((output / RUNNER.TEMP_MANIFEST_NAME).exists())

                with mock.patch.object(
                    RUNNER,
                    "open_relative_regular_file",
                    wraps=RUNNER.open_relative_regular_file,
                ) as archive_open_mock:
                    with self.assertRaisesRegex(RUNNER.ReviewError, "already exists"):
                        RUNNER.execute_permit()
                archive_open_mock.assert_not_called()
                self.assertTrue(claim_path.is_file())

    def test_09b_result_without_manifest_is_explicitly_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                real_publish = RUNNER.publish_no_replace

                def stop_before_manifest(
                    directory_fd: int,
                    temporary_name: str,
                    final_name: str,
                ) -> None:
                    if final_name == RUNNER.MANIFEST_NAME:
                        raise RUNNER.ReviewError(
                            "forced completion manifest pre-link failure"
                        )
                    real_publish(directory_fd, temporary_name, final_name)

                with mock.patch.object(
                    RUNNER,
                    "publish_no_replace",
                    side_effect=stop_before_manifest,
                ):
                    with self.assertRaisesRegex(
                        RUNNER.PublishedReportStateError,
                        "partially published",
                    ):
                        RUNNER.execute_permit()
                output = environment["output"]
                result_path = output / RUNNER.RESULT_NAME
                manifest_path = output / RUNNER.MANIFEST_NAME
                self.assertTrue(result_path.is_file())
                self.assertFalse(manifest_path.exists())
                result = json.loads(result_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    result["status"],
                    (
                        "rung3_candidate_inventory_recorded_"
                        "awaiting_completion_manifest"
                    ),
                )
                self.assertEqual(
                    result["nextAction"],
                    "publish_bound_completion_manifest",
                )
                self.assertFalse(result["publicationCompletion"]["complete"])
                self.assertEqual(
                    result["operationCounters"][
                        "reportPublicationCountBeforeResultPublication"
                    ],
                    0,
                )
                self.assertEqual(
                    result["operationCounters"][
                        "requiredReportPublicationCountForCompletion"
                    ],
                    2,
                )

    def test_10_runner_has_no_process_network_git_device_or_extraction_api(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(RUNNER_PATH))
        forbidden_modules = {
            "asyncio",
            "ftplib",
            "http",
            "httpx",
            "importlib",
            "requests",
            "socket",
            "ssl",
            "subprocess",
            "telnetlib",
            "urllib",
        }
        imported_roots: set[str] = set()
        forbidden_calls: list[str] = []
        forbidden_terminals = {
            "check_call",
            "check_output",
            "connect",
            "create_connection",
            "eval",
            "extract",
            "extractall",
            "fork",
            "popen",
            "run",
            "socket",
            "system",
            "urlopen",
        }
        controlled_load_calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    terminal = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    terminal = node.func.attr
                else:
                    terminal = ""
                if terminal in {"compile", "exec"}:
                    controlled_load_calls.append(terminal)
                if terminal in forbidden_terminals:
                    forbidden_calls.append(
                        f"{terminal}@{getattr(node, 'lineno', '?')}"
                    )
        self.assertEqual(imported_roots & forbidden_modules, set())
        self.assertEqual(forbidden_calls, [])
        self.assertEqual(sorted(controlled_load_calls), ["compile", "exec"])
        self.assertNotIn("SourceFileLoader", source)
        self.assertNotIn("spec_from_file_location", source)
        self.assertIn("sys.dont_write_bytecode = True", source)
        self.assertNotIn("adb ", source.casefold())
        self.assertNotIn("git ", source.casefold())

        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        claim_function = functions["create_claim"]
        claim_calls = {
            node.func.attr
            for node in ast.walk(claim_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }
        self.assertNotIn("unlink", claim_calls)

        non_future_imports = [
            node
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and not (
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
            )
        ]
        self.assertIsInstance(non_future_imports[0], ast.Import)
        self.assertEqual(non_future_imports[0].names[0].name, "sys")
        argparse_import = next(
            node
            for node in non_future_imports
            if isinstance(node, ast.Import)
            and any(alias.name == "argparse" for alias in node.names)
        )
        module_guard = next(
            node
            for node in tree.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "require_isolated_interpreter"
        )
        self.assertLess(module_guard.lineno, argparse_import.lineno)


if __name__ == "__main__":
    unittest.main(verbosity=2)
