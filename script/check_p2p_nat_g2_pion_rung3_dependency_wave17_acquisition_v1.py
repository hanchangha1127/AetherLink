#!/usr/bin/env python3
"""Validate the Wave17 one-use acquisition package without consuming it."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "Wave17 acquisition checker requires `python3 -I -B -S`"
        )


import argparse
import ast
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types
from typing import Any, Mapping, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.md"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "execution-permit-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave17_decision_v1.py"
)
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py"
)
SELF_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py"
)
RUNNER_TESTS_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
WAVE4_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)
SELF_NORMALIZED_SHA256 = (
    "6e653ff394c5e6f7d1dae9048ec34daecb9b7420121d19db01e772009acef959"
)
EXPECTED_DECISION_RAW = (
    "659e9ce6f079701cab68e337d2746959741ef4868ffff6392fcdbf26ae692f93"
)
EXPECTED_DECISION_CONTENT = (
    "867a2ba1a7da54b5466951b1caea9b09eb355d2325a58fa552037047d3fad7df"
)
EXPECTED_DECISION_CHECKER_RAW = (
    "564a8f0c3a6dbf9331fe8e02d121efe8c4e91fcd6c5e7415607e0c0b6d9fb256"
)
EXPECTED_DECISION_CHECKER_NORMALIZED = (
    "226cb948492708f50e695c9d5e849c4f0acff11143625f473372c1bb59cec269"
)
EXPECTED_DECISION_READER_RAW = (
    "3af49874bd518628971566d6067331c75e2f4fbcf7ac36bafee914938873ef51"
)
EXPECTED_DECISION_TESTS_RAW = (
    "5af9a8ed93b2424e4251cbe3b47de3281c498fc93e707975311dbddff41065a6"
)
V15_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v15.py"
V15_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v15.py"
V15_CHECKER_RAW = (
    "e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5"
)
V15_CHECKER_NORMALIZED = (
    "63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7"
)
V15_TESTS_RAW = (
    "65d7f435cef11da2cccae7e31a3c410d7a3038f6bc3261552753801a0de431b1"
)
V15_CONTENT = (
    "4666c802e40734bb1b5b91489eb24aa782cb346710caec9605be4e0e005553ee"
)
V15_INPUT_SET = (
    "4b12b7ca7f0a8b1556c692522e8832af033f9d2a1f00fbeb7469623a00541f1e"
)
V15_SOURCE_BINDINGS = (
    "86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd"
)
V15_GRAPH = (
    "ffe9f910669401198b88752663055ca2e6622d19e171f2d20a2b303d06c989d7"
)
V15_FRONTIER = (
    "ce1be1152aabf580a211f038d80aeaf9249418117b7d12ff26ffc909f1e4d593"
)
DECISION_COMPACT_IDENTITY = (
    "813ac6030c903b716fb5f68852468a53ebb0bcfe60c7c11582d2f2ffb18041ca"
)
DECISION_FULL_WITNESS = (
    "ee3f4b0e1072a8bc0e1eb6e53b83fe8d749fdfd8c13bec54c60774dc3755dc54"
)
DECISION_REQUEST_SET = (
    "acf64af2352fb4d82325f3e5bd2a3e913b8ef95db553fa0015bc71a239f3fb35"
)
PERMIT_READER_RAW_SHA256 = (
    "95ff70bdd0fdb5f2b7bdfdbeb8960774aa1b5ef48c67e6d62031c3d4cf485655"
)
RESOURCE_CONTRACT_CANONICAL_SHA256 = (
    "4920d020b6a4df4adc890a8eb2a0290e1343938483e396cc7e21447728f14686"
)
EXPECTED_WAVE4_CHECKER_RAW = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
EXPECTED_WAVE4_RUNNER_RAW = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)
EXPECTED_SELF_TESTS_RAW = (
    "46e4508695dba47cfdb899a5f1ca5a4f9d2c1cb8e3e288babf0036daf632827c"
)
EXPECTED_RUNNER_TESTS_RAW = (
    "edaaf7e0c557ab9648b6caf651276cdf406da338eca03fb7ee77ecaefa7e283e"
)

PROXY_HOST = "proxy.golang.org"
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
NAMESPACE_ANCHOR_PATH = f"{DEPENDENCY_ROOT}/.wave-16-v1.claim"
NAMESPACE_ANCHOR_RAW_SHA256 = (
    "df97f5d9bf8c56f3bbf08635b8332bbc18b25babd0e5f35742fee3657555f4b8"
)
CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-17-v1.claim"
STAGING_PREFIX = ".wave-17-v1-staging-"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-17-v1"
FINAL_ACCEPTED = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-receipt-v1.json"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-manifest-v1.json"
)
READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "readback-manifest-v1.json"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-17-v1-readback.claim"
READBACK_TEMP_PREFIX = ".wave-17-readback-v1-"
MAX_MOD_BYTES = 1 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_AGGREGATE_MOD_BYTES = 1 * 1024 * 1024
MAX_AGGREGATE_ZIP_BYTES = 16 * 1024 * 1024
MAX_AGGREGATE_BYTES = 17 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
MAX_ZIP_FILES = 20_000
MAX_ZIP_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ZIP_FILE_BYTES = 128 * 1024 * 1024
MAX_ZIP_NAME_BYTES = 1_024
MAX_ALL_ZIP_FILES = 20_000
MAX_ALL_ZIP_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
PER_REQUEST_DEADLINE_MS = 30_000
WHOLE_ATTEMPT_DEADLINE_MS = 600_000
INTERPRETER_PATH = (
    "/Applications/Xcode.app/Contents/Developer/usr/bin/python3"
)
EXACT_RUNNER_ARGV = ["--execute"]
EXACT_PREFLIGHT_ARGV = ["--preflight"]
EXACT_INVOCATION_COMMAND = [
    INTERPRETER_PATH,
    "-I",
    "-B",
    "-S",
    RUNNER_PATH,
    *EXACT_RUNNER_ARGV,
]
KERNEL_EXECUTABLE_PATH = (
    "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/"
    "Python3.framework/Versions/3.9/Resources/Python.app/Contents/"
    "MacOS/Python"
)
EXACT_KERNEL_ARGV = [
    KERNEL_EXECUTABLE_PATH,
    "-I",
    "-B",
    "-S",
    RUNNER_PATH,
    *EXACT_RUNNER_ARGV,
]


class CheckError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise CheckError("E_ARGUMENT")


def require(value: Any, code: str) -> None:
    if not value:
        raise CheckError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def normalize_marker(raw: bytes, name: bytes) -> bytes:
    marker = re.compile(
        rb"(" + name + rb' = \(\n    ")[0-9a-f]{64}("\n\))'
    )
    normalized, count = marker.subn(
        rb"\g<1>" + b"0" * 64 + rb"\g<2>",
        raw,
    )
    require(count == 1, "E_NORMALIZATION")
    return normalized


def normalized_self_bytes(raw: bytes) -> bytes:
    return normalize_marker(raw, b"SELF_NORMALIZED_SHA256")


def normalized_decision_checker_bytes(raw: bytes) -> bytes:
    return normalize_marker(raw, b"SELF_NORMALIZED_SHA256")


def normalized_runner_bytes(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    pattern = re.compile(r'EXPECTED_CHECKER_RAW = "[0-9a-f]{64}"')
    require(len(pattern.findall(text)) == 1, "E_RUNNER")
    return pattern.sub(
        'EXPECTED_CHECKER_RAW = "' + "0" * 64 + '"',
        text,
    ).encode("utf-8")


def validate_runner(raw: bytes, checker_raw: bytes) -> None:
    source = raw.decode("utf-8", errors="strict")
    ast.parse(source)
    reverse = re.findall(
        r'EXPECTED_CHECKER_RAW = "([0-9a-f]{64})"',
        source,
    )
    require(reverse == [sha256(checker_raw)], "E_RUNNER")
    for token in (
        "validate_production_invocation",
        "ImmutablePhaseLedger",
        "ProcessStateGuard",
        "ExecutionNamespace",
        "AuthorityFiles",
        "WHOLE_ATTEMPT_DEADLINE_MS",
        "signal.pthread_sigmask",
        "O_EXCL",
        "O_NOFOLLOW",
        "unknown_after_dispatch",
        "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
        "readback",
    ):
        require(token in source, "E_RUNNER")
    for token in (
        "shell=True",
        "shutil.rmtree",
        "\"Authorization\"",
        "\"Proxy-Authorization\"",
        "\"Cookie\"",
    ):
        require(token not in source, "E_RUNNER")


class HeldFile:
    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str | None,
        maximum_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        require(
            relative_path
            and not relative_path.startswith("/")
            and ".." not in Path(relative_path).parts,
            "E_PATH",
        )
        self.path = root / relative_path
        self.fd = -1
        self.initial: os.stat_result | None = None
        self.raw = b""
        flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            self.fd = os.open(self.path, flags)
            self.initial = os.fstat(self.fd)
            require(
                stat.S_ISREG(self.initial.st_mode)
                and self.initial.st_nlink == 1
                and self.initial.st_uid in {0, os.geteuid()}
                and stat.S_IMODE(self.initial.st_mode) & 0o022 == 0
                and 0 < self.initial.st_size <= maximum_bytes,
                "E_FILE_IDENTITY",
            )
            first = self._read()
            second = self._read()
            require(first == second, "E_STABLE_READ")
            if expected_sha256 is not None:
                require(sha256(first) == expected_sha256, "E_FILE_IDENTITY")
            self.raw = first
            self.barrier()
        except BaseException:
            self.close()
            raise

    def _read(self) -> bytes:
        require(self.fd >= 0 and self.initial is not None, "E_FILE_IDENTITY")
        os.lseek(self.fd, 0, os.SEEK_SET)
        remaining = self.initial.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_STABLE_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", "E_STABLE_READ")
        return b"".join(chunks)

    def barrier(self) -> None:
        require(self.fd >= 0 and self.initial is not None, "E_FILE_IDENTITY")
        current = os.fstat(self.fd)
        named = os.stat(self.path, follow_symlinks=False)
        fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        require(
            tuple(getattr(current, field) for field in fields)
            == tuple(getattr(named, field) for field in fields)
            == tuple(getattr(self.initial, field) for field in fields),
            "E_FILE_IDENTITY",
        )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> "HeldFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _directory_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _validate_directory(info: os.stat_result) -> None:
    require(
        stat.S_ISDIR(info.st_mode)
        and info.st_uid in {0, os.geteuid()}
        and stat.S_IMODE(info.st_mode) & 0o022 == 0,
        "E_DIRECTORY_IDENTITY",
    )


def _open_held_directory(
    owner: list[int],
    path: str | os.PathLike[str],
    *,
    dir_fd: int | None = None,
) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        if dir_fd is None:
            fd = os.open(path, flags)
        else:
            fd = os.open(path, flags, dir_fd=dir_fd)
        owner.append(fd)
        return fd
    except OSError as error:
        raise CheckError("E_DIRECTORY_IDENTITY") from error


class _HeldNamespace:
    def __init__(
        self,
        root: Path,
        relative_directory: str,
        error_code: str,
    ) -> None:
        self.root_path = root
        self.error_code = error_code
        self.owned: list[int] = []
        self.directories: list[
            tuple[int, os.stat_result, int, str]
        ] = []
        self.root_fd = -1
        self.directory_fd = -1
        try:
            self.root_fd = _open_held_directory(self.owned, root)
            self.root_initial = os.fstat(self.root_fd)
            _validate_directory(self.root_initial)
            current = self.root_fd
            for component in relative_directory.split("/"):
                child = _open_held_directory(
                    self.owned,
                    component,
                    dir_fd=current,
                )
                initial = os.fstat(child)
                _validate_directory(initial)
                self.directories.append(
                    (child, initial, current, component)
                )
                current = child
            self.directory_fd = current
        except BaseException:
            self.close()
            raise

    def _names(self) -> list[str]:
        try:
            raw_names = os.listdir(self.directory_fd)
        except OSError as error:
            raise CheckError(self.error_code) from error
        names = [_portable_name(name) for name in raw_names]
        require(
            len(set(names)) == len(raw_names),
            self.error_code,
        )
        return names

    def barrier(self) -> None:
        try:
            named_root = os.stat(
                self.root_path,
                follow_symlinks=False,
            )
            require(
                _directory_identity(os.fstat(self.root_fd))
                == _directory_identity(self.root_initial)
                == _directory_identity(named_root),
                "E_ROOT_IDENTITY",
            )
            for child, initial, parent, component in self.directories:
                named = os.stat(
                    component,
                    dir_fd=parent,
                    follow_symlinks=False,
                )
                require(
                    _directory_identity(os.fstat(child))
                    == _directory_identity(initial)
                    == _directory_identity(named),
                    self.error_code,
                )
        except OSError as error:
            raise CheckError(self.error_code) from error
        self.observe_absent()

    def observe_absent(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        first_error: OSError | None = None
        for fd in reversed(self.owned):
            try:
                os.close(fd)
            except OSError as error:
                if first_error is None:
                    first_error = error
        self.owned.clear()
        self.directories.clear()
        self.root_fd = -1
        self.directory_fd = -1
        if first_error is not None:
            raise CheckError(self.error_code) from first_error

    def __enter__(self) -> "_HeldNamespace":
        self.barrier()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class HeldReservedNamespace(_HeldNamespace):
    """Hold the dependency namespace and prove all Wave17 names absent."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, DEPENDENCY_ROOT, "E_NAMESPACE")

    def observe_absent(self) -> None:
        names = self._names()
        forbidden = {
            _portable_name(Path(CLAIM_PATH).name),
            _portable_name(Path(FINAL_ROOT).name),
            _portable_name(Path(READBACK_CLAIM_PATH).name),
        }
        staging = _portable_name(STAGING_PREFIX)
        readback_temp = _portable_name(READBACK_TEMP_PREFIX)
        require(
            not forbidden.intersection(names)
            and not any(name.startswith(staging) for name in names)
            and not any(
                name.startswith(readback_temp) for name in names
            ),
            "E_NAMESPACE",
        )


class HeldTerminalNamespace(_HeldNamespace):
    """Hold the documentation namespace and prove terminal names absent."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, BASE, "E_TERMINAL_NAMESPACE")

    def observe_absent(self) -> None:
        names = self._names()
        forbidden = {
            _portable_name(Path(path).name)
            for path in (
                RECEIPT_PATH,
                FAILURE_PATH,
                MANIFEST_PATH,
                READBACK_PATH,
                READBACK_MANIFEST_PATH,
            )
        }
        require(
            not forbidden.intersection(names),
            "E_TERMINAL_NAMESPACE",
        )


class AuthorityFiles:
    """Pin every byte that grants or implements one Wave17 attempt."""

    def __init__(
        self,
        root: Path,
        permit: Mapping[str, Any],
    ) -> None:
        self.root = root
        self.permit = permit
        self.stack = ExitStack()
        self.held: list[HeldFile] = []

    def __enter__(self) -> "AuthorityFiles":
        expected: dict[str, str] = {}
        rows = (
            list(self.permit["decisionBinding"]["files"])
            + list(self.permit["toolBindings"])
            + list(self.permit["primitiveBindings"])
        )
        for row in rows:
            expected[row["path"]] = row["rawSha256"]
        expected[PERMIT_READER_PATH] = self.permit[
            "readerDocumentBinding"
        ]["rawSha256"]
        expected[PERMIT_PATH] = sha256(canonical_bytes(self.permit))
        predecessor = self.permit["predecessorBindings"][
            "combinedFixedPointV15"
        ]
        expected[predecessor["checkerPath"]] = predecessor[
            "checkerRawSha256"
        ]
        expected[predecessor["testsPath"]] = predecessor[
            "testsRawSha256"
        ]
        anchor = predecessor["wave16NamespaceAnchor"]
        expected[anchor["path"]] = anchor["rawSha256"]
        try:
            self.held = [
                self.stack.enter_context(
                    HeldFile(self.root, path, digest)
                )
                for path, digest in sorted(expected.items())
            ]
            self.barrier()
            return self
        except BaseException:
            self.stack.close()
            raise

    def barrier(self) -> None:
        for held in self.held:
            held.barrier()

    def __exit__(self, *_: object) -> None:
        self.stack.close()


def strict_json(raw: bytes) -> dict[str, Any]:
    def reject_float(_: str) -> float:
        raise ValueError("float")

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            parse_float=reject_float,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise CheckError("E_JSON") from error
    require(type(value) is dict and canonical_bytes(value) == raw, "E_JSON")
    return value


def load_decision_checker(raw: bytes) -> types.ModuleType:
    require(
        sha256(raw) == EXPECTED_DECISION_CHECKER_RAW,
        "E_DECISION_CHECKER",
    )
    module = types.ModuleType("aetherlink_wave17_decision_checker_pinned")
    module.__dict__.update(
        {
            "__file__": str(ROOT / DECISION_CHECKER_PATH),
            "__name__": "aetherlink_wave17_decision_checker_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            raw,
            DECISION_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CheckError("E_DECISION_CHECKER") from error
    return module


def resource_contract() -> list[dict[str, Any]]:
    common = {
        "host": PROXY_HOST,
        "method": "GET",
        "module": "golang.org/x/tools",
        "port": 443,
        "selectedByGraphAlgorithm": False,
        "tupleDigestSha256":
            "8bd04ea612cec978713135c7452cb52e20350f82cd8b2a17691e3c431b43973c",
        "tupleId": "wave17-001-8bd04ea612ce",
        "tupleOrder": 1,
        "version": "v0.33.0",
    }
    return [
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.mod",
            "expectedH1":
                "h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI=",
            "kind": "mod",
            "maximumResponseBodyBytes": MAX_MOD_BYTES,
            "path": "/golang.org/x/tools/@v/v0.33.0.mod",
            "requestOrdinal": 1,
            "url":
                "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.mod",
        },
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.zip",
            "expectedH1":
                "h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc=",
            "kind": "zip",
            "maximumResponseBodyBytes": MAX_ZIP_BYTES,
            "path": "/golang.org/x/tools/@v/v0.33.0.zip",
            "requestOrdinal": 2,
            "url":
                "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.zip",
        },
    ]


def authority() -> dict[str, Any]:
    return {
        "accountRequired": False,
        "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized": False,
        "authenticationRequired": False,
        "clientCertificateRequired": False,
        "compileAuthorized": False,
        "cookieRequired": False,
        "deploymentAuthorized": False,
        "deviceAuthorized": False,
        "dnsTcpTlsHttpsToExactProxyAuthorized": True,
        "externalAuthenticationRequired": False,
        "gitOperationAuthorized": False,
        "gpgRequired": False,
        "ownerProofRequired": False,
        "ownerRequired": False,
        "packageManagerAuthorized": False,
        "passwordRequired": False,
        "privateKeyRequired": False,
        "productRuntimeNetworkAuthorized": False,
        "publicationAuthorized": False,
        "repositoryOwnerIdentityProofRequired": False,
        "signatureRequired": False,
        "sourceExtractionAuthorized": False,
        "sourceLoadOrExecutionAuthorized": False,
        "sshRequired": False,
        "subprocessAuthorized": False,
        "tokenRequired": False,
        "userActionRequired": False,
        "wave17PublicProxy2GetAcquisitionAuthorizedOnce": True,
    }


def permit_payload(
    *,
    checker_raw_sha256: str,
    runner_raw_sha256: str,
    runner_normalized_sha256: str,
) -> dict[str, Any]:
    require(
        type(checker_raw_sha256) is str
        and type(runner_raw_sha256) is str
        and type(runner_normalized_sha256) is str
        and re.fullmatch(r"[0-9a-f]{64}", checker_raw_sha256)
        is not None
        and re.fullmatch(r"[0-9a-f]{64}", runner_raw_sha256) is not None
        and re.fullmatch(r"[0-9a-f]{64}", runner_normalized_sha256)
        is not None,
        "E_RUNNER_BINDING",
    )
    resources = resource_contract()
    require(
        sha256(canonical_bytes(resources))
        == RESOURCE_CONTRACT_CANONICAL_SHA256,
        "E_RESOURCE_CONTRACT",
    )
    return {
        "absoluteResourceLimits": {
            "maximumAggregateResponseBodyBytes": MAX_AGGREGATE_BYTES,
            "maximumHeaderBytesPerResponse": MAX_HEADER_BYTES,
            "maximumModResponseBodyBytes": MAX_MOD_BYTES,
            "maximumRequestCount": 2,
            "maximumAggregateModResponseBodyBytes":
                MAX_AGGREGATE_MOD_BYTES,
            "maximumAggregateZipResponseBodyBytes":
                MAX_AGGREGATE_ZIP_BYTES,
            "maximumZipEntryBytes": MAX_ZIP_FILE_BYTES,
            "maximumZipEntryCount": MAX_ZIP_FILES,
            "maximumZipResponseBodyBytes": MAX_ZIP_BYTES,
            "maximumZipUncompressedBytes": MAX_ZIP_UNCOMPRESSED_BYTES,
            "perRequestDeadlineMilliseconds": PER_REQUEST_DEADLINE_MS,
            "callerBlockedSigalrmRejectedBeforePreflight": True,
            "originalSignalMaskRestoredExactlyOrUncertaintyReported": True,
            "pendingInstalledSigalrmSynchronouslyConsumedBeforePriorHandlerRestoration":
                True,
            "pendingSigalrmDrainFailureContainedWithoutPriorAlarmStateRestoration":
                True,
            "perRequestDeadlinePassedToPinnedFetchPrimitive": True,
            "preexistingRealTimerRestoredWithElapsedAdjustment": True,
            "priorHandlerRestoredBeforePriorTimerArmed": True,
            "processSetupAndRestorationUseGuardedSignalState": True,
            "processStateRestorationStepsAreIndependentBestEffort": True,
            "sigalrmUnblockedDuringFetchValidationWriteAndFsync": True,
            "wholeAttemptDeadlineMilliseconds": WHOLE_ATTEMPT_DEADLINE_MS,
            "wholeAttemptSigalrmDeadlineRequired": True,
        },
        "authority": authority(),
        "decisionBinding": {
            "contentSha256": EXPECTED_DECISION_CONTENT,
            "files": [
                {
                    "path": DECISION_PATH,
                    "rawSha256": EXPECTED_DECISION_RAW,
                },
                {
                    "path": DECISION_READER_PATH,
                    "rawSha256": EXPECTED_DECISION_READER_RAW,
                },
                {
                    "path": DECISION_CHECKER_PATH,
                    "rawSha256": EXPECTED_DECISION_CHECKER_RAW,
                },
                {
                    "path": DECISION_TESTS_PATH,
                    "rawSha256": EXPECTED_DECISION_TESTS_RAW,
                },
            ],
            "path": DECISION_PATH,
            "rawSha256": EXPECTED_DECISION_RAW,
            "requiredStatus": (
                "wave17_exact_1_frontier_identity_classified_1_complete_"
                "0_blocked_acquisition_ready_not_authorized"
            ),
        },
        "documentType":
            "aetherlink.wave17-source-acquisition-execution-permit",
        "executionReady": True,
        "structurePreparationOnly": False,
        "filesystemAuthority": {
            "acquisitionArtifactPublicationAuthorized": True,
            "atomicNoReplacePublicationRequired": True,
            "claimWriteAuthorized": True,
            "manifestWrittenLast": True,
            "newDirectoryMode": "0700",
            "newFileMode": "0600",
            "otherRepositoryWritesAuthorized": False,
            "ownerOnlyStagingWriteAuthorized": True,
            "receiptFailureAndManifestWriteAuthorized": True,
            "sourceExtractionAuthorized": False,
            "verifiedModAndZipWriteAuthorized": True,
        },
        "identityBinding": {
            "blockedTupleCount": 0,
            "compactIdentitySha256": DECISION_COMPACT_IDENTITY,
            "completeTupleCount": 1,
            "fullWitnessSha256": DECISION_FULL_WITNESS,
            "requestSetCanonicalSha256": DECISION_REQUEST_SET,
        },
        "invocationContract": {
            "additionalArgumentsAllowed": False,
            "abbreviatedArgumentsAllowed": False,
            "canonicalDirectCommand": EXACT_INVOCATION_COMMAND,
            "canonicalDirectCommandExclusive": False,
            "cwd": "repository_root",
            "duplicateArgumentsAllowed": False,
            "exactArgv": EXACT_RUNNER_ARGV,
            "exactKernelArgv": EXACT_KERNEL_ARGV,
            "executionEntryPointRevalidatesInvocationShape": True,
            "externalLauncherReceiptRequired": False,
            "interpreterAbsolutePath": INTERPRETER_PATH,
            "invocationChecksAuthenticateOrigin": False,
            "invocationOriginAttestationProvided": False,
            "kernelArgvPurpose":
                "accidental_misconfiguration_guard_only",
            "kernelArgvRevalidatedBeforePreflight": True,
            "kernelArgvSource": "macos_sysctl_kern_procargs2",
            "kernelExecutableAbsolutePath": KERNEL_EXECUTABLE_PATH,
            "localSameUserProcessTrusted": True,
            "pythonInvocationStatePurpose":
                "accidental_misconfiguration_guard_only",
            "runnerPath": RUNNER_PATH,
            "sameProcessWrapperWithinTrustBoundary": True,
            "testSeamMayDispatchExecution": False,
        },
        "nextAction": "execute_bound_wave17_source_acquisition_once",
        "nonClaims": [
            (
                "no account owner proof password private key signature token "
                "cookie client certificate or user authentication is required"
            ),
            (
                "checking or preflighting this package does not create the "
                "claim use network or write acquisition artifacts"
            ),
            (
                "the permit does not authorize source extraction loading "
                "execution compilation package-manager Git device deployment "
                "or product runtime networking"
            ),
            (
                "the permit does not establish dependency fixed point "
                "semantic closure selection rung-three completion or release"
            ),
        ],
        "oneUseContract": {
            "baseExceptionAfterExclusiveCreateFailsClosedAsClaimStateUncertain":
                True,
            "claimCreationAttemptRecordedBeforeExclusiveCreate": True,
            "claimCreationMayHaveConsumedDefaultsTrueUntilDefinitiveNotCreated":
                True,
            "claimCreationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "claimCreatedOExcl0600AndFsyncedBeforeDnsOrNetwork": True,
            "claimPath": CLAIM_PATH,
            "claimAbsentAtPermitPublication": True,
            "claimPersistsAfterSuccessFailureTimeoutOrUncertainty": True,
            "evidencePath": EVIDENCE_PATH,
            "existingClaimState": "already_consumed",
            "failurePath": FAILURE_PATH,
            "failureRetainsStaging": True,
            "fileExistsObservedBeforeUnmaskPreservesKnownConsumed": True,
            "fileExistsObservedOverridesUnmaskAcquisitionError": True,
            "finalAcceptedPath": FINAL_ACCEPTED,
            "finalRootPath": FINAL_ROOT,
            "heldRootRelativeComponentTraversalRequired": True,
            "intermediateDirectoryIdentityHeldThroughExecution": True,
            "knownConsumedSurvivesNamespaceOrAuthorityTeardownError": True,
            "knownExistingClaimPreservesAlreadyConsumedClassification": True,
            "localFdOwnershipTransferAndCloseCleanupDefersOnlySigalrmAndSigint":
                True,
            "networkValidationWriteAndFsyncOutsideLocalSignalDeferral": True,
            "closeCleanupCompletesBeforePriorSignalMaskRestoration": True,
            "postCreatePreAssignmentInterruptionTreatedAsConsumedPossible":
                True,
            "preAssignmentInterruptionClosesUnboundHeldEntry": True,
            "restoreFailureAfterKnownConsumedIsConsumedUncertain": True,
            "retryResumeBackfillOverwriteOrCleanupAllowed": False,
            "secondExecutionAllowed": False,
            "stagingPrefix": STAGING_PREFIX,
        },
        "permitId":
            "g2-pion-rung3-wave17-2-resource-source-acquisition-"
            "execution-permit-v1",
        "predecessorBindings": {
            "combinedFixedPointV15": {
                "checkerNormalizedSha256": V15_CHECKER_NORMALIZED,
                "checkerPath": V15_CHECKER_PATH,
                "checkerRawSha256": V15_CHECKER_RAW,
                "combinedInputSetSha256": V15_INPUT_SET,
                "contentSha256": V15_CONTENT,
                "frontierSha256": V15_FRONTIER,
                "graphSha256": V15_GRAPH,
                "sourceBindingsSha256": V15_SOURCE_BINDINGS,
                "testsPath": V15_TESTS_PATH,
                "testsRawSha256": V15_TESTS_RAW,
                "totalFullSourceReconstructionCount": 28,
                "totalGraphArchiveOpenCount": 3696,
                "wave16NamespaceAnchor": {
                    "path": NAMESPACE_ANCHOR_PATH,
                    "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
                },
            }
        },
        "readerDocumentBinding": {
            "path": PERMIT_READER_PATH,
            "rawSha256": PERMIT_READER_RAW_SHA256,
        },
        "recordedDate": "2026-07-27",
        "requestContract": {
            "acceptedStatusCode": 200,
            "alternateHostAllowed": False,
            "ambientProxyAllowed": False,
            "authenticationAllowed": False,
            "authorizationHeaderAllowed": False,
            "clientCertificateAllowed": False,
            "contentEncoding": "identity",
            "cookieAllowed": False,
            "directHttpsOnly": True,
            "host": PROXY_HOST,
            "method": "GET",
            "order": "tuple_order_ascending_mod_then_zip",
            "port": 443,
            "proxyAuthorizationHeaderAllowed": False,
            "queryOrFragmentAllowed": False,
            "rangeHeaderAllowed": False,
            "redirectAllowed": False,
            "requestBodyAllowed": False,
            "requestCount": 2,
            "resourcesCanonicalSha256":
                RESOURCE_CONTRACT_CANONICAL_SHA256,
            "sourceRequestSetCanonicalSha256": DECISION_REQUEST_SET,
            "tupleCount": 1,
            "resources": resources,
            "retryAllowed": False,
            "retryResumeOrBackfillAllowed": False,
            "tlsCertificateAndHostnameValidationRequired": True,
            "identityContentEncodingRequired": True,
        },
        "runnerBinding": {
            "normalizedSha256": runner_normalized_sha256,
            "path": RUNNER_PATH,
            "rawSha256": runner_raw_sha256,
        },
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "toolBindings": [
            {
                "normalizedSha256": SELF_NORMALIZED_SHA256,
                "path": SELF_PATH,
                "rawSha256": checker_raw_sha256,
                "role": "wave17_acquisition_checker",
            },
            {
                "path": SELF_TESTS_PATH,
                "rawSha256": EXPECTED_SELF_TESTS_RAW,
                "role": "wave17_acquisition_checker_tests",
            },
            {
                "normalizedSha256": runner_normalized_sha256,
                "path": RUNNER_PATH,
                "rawSha256": runner_raw_sha256,
                "role": "wave17_one_use_runner",
            },
            {
                "path": RUNNER_TESTS_PATH,
                "rawSha256": EXPECTED_RUNNER_TESTS_RAW,
                "role": "wave17_one_use_runner_tests",
            },
        ],
        "primitiveBindings": [
            {
                "path": WAVE4_CHECKER_PATH,
                "rawSha256": EXPECTED_WAVE4_CHECKER_RAW,
                "use": "constants_and_validation_contract_only",
            },
            {
                "path": WAVE4_RUNNER_PATH,
                "rawSha256": EXPECTED_WAVE4_RUNNER_RAW,
                "use": (
                    "h1_go_mod_zip_and_direct_https_"
                    "validation_primitives_only"
                ),
            },
        ],
        "runnerNormalizedSha256": runner_normalized_sha256,
        "terminalContract": {
            "failureOperationCountsAreCommittedLowerBounds": True,
            "failurePath": FAILURE_PATH,
            "failurePublicationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "failurePublishesFailureOnly": True,
            "inFlightOrdinalPhaseAndAdditionalCompletionUncertainRecorded":
                True,
            "independentReadbackRequired": True,
            "manifestPath": MANIFEST_PATH,
            "manifestWrittenLast": True,
            "postPublicationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "processStateRestorationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "readbackManifestPath": READBACK_MANIFEST_PATH,
            "readbackPath": READBACK_PATH,
            "receiptPath": RECEIPT_PATH,
            "successAndFailureMutuallyExclusive": True,
            "successRequiresNoActiveOperationAndExact2CommittedCounts": True,
            "terminalTeardownUncertaintyFailureCode":
                "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
            "terminalTeardownUncertaintyState":
                "consumed_terminal_state_uncertain",
            "zeroCommittedResponsesWithActiveFetchState":
                "unknown_after_dispatch",
        },
        "verificationContract": {
            "goModH1Algorithm":
                "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod",
            "moduleZipH1Algorithm":
                "golang.org/x/mod/sumdb/dirhash.HashZip(Hash1)_v1",
            "rawSha256RecordedSeparately": True,
            "sourceExtractionAllowed": False,
            "zipExactModuleVersionPrefixRequired": True,
            "zipSafetyShapeCrcAndModParityRequired": True,
        },
        "zipLimits": {
            "encryptedSymlinkDirectoryDuplicateOrUnsafeEntriesAllowed":
                False,
            "maximumEntryCountAcrossAllZips": MAX_ALL_ZIP_FILES,
            "maximumEntryCountPerZip": MAX_ZIP_FILES,
            "maximumEntryNameBytes": MAX_ZIP_NAME_BYTES,
            "maximumSingleEntryBytes": MAX_ZIP_FILE_BYTES,
            "maximumUncompressedBytesAcrossAllZips":
                MAX_ALL_ZIP_UNCOMPRESSED_BYTES,
            "maximumUncompressedBytesPerZip":
                MAX_ZIP_UNCOMPRESSED_BYTES,
        },
        "verificationOnly": False,
        "result":
            "exact_2_resource_one_use_wave17_acquisition_authorized_not_consumed",
    }


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization":
            "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def evaluate(
    verify_disk: bool,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    require_isolated_interpreter()
    with ExitStack() as stack:
        reserved = stack.enter_context(HeldReservedNamespace(root))
        terminal = stack.enter_context(HeldTerminalNamespace(root))
        self_held = stack.enter_context(HeldFile(root, SELF_PATH, None))
        self_tests_held = stack.enter_context(
            HeldFile(root, SELF_TESTS_PATH, EXPECTED_SELF_TESTS_RAW)
        )
        require(
            sha256(normalized_self_bytes(self_held.raw))
            == SELF_NORMALIZED_SHA256,
            "E_SELF",
        )
        decision_held = stack.enter_context(
            HeldFile(root, DECISION_PATH, EXPECTED_DECISION_RAW)
        )
        stack.enter_context(
            HeldFile(
                root,
                DECISION_READER_PATH,
                EXPECTED_DECISION_READER_RAW,
            )
        )
        decision_checker_held = stack.enter_context(
            HeldFile(
                root,
                DECISION_CHECKER_PATH,
                EXPECTED_DECISION_CHECKER_RAW,
            )
        )
        require(
            sha256(
                normalized_decision_checker_bytes(
                    decision_checker_held.raw
                )
            )
            == EXPECTED_DECISION_CHECKER_NORMALIZED,
            "E_DECISION_CHECKER",
        )
        stack.enter_context(
            HeldFile(
                root,
                DECISION_TESTS_PATH,
                EXPECTED_DECISION_TESTS_RAW,
            )
        )
        stack.enter_context(
            HeldFile(
                root,
                NAMESPACE_ANCHOR_PATH,
                NAMESPACE_ANCHOR_RAW_SHA256,
            )
        )
        permit_reader_held = stack.enter_context(
            HeldFile(root, PERMIT_READER_PATH, PERMIT_READER_RAW_SHA256)
        )
        wave4_checker_held = stack.enter_context(
            HeldFile(
                root,
                WAVE4_CHECKER_PATH,
                EXPECTED_WAVE4_CHECKER_RAW,
            )
        )
        wave4_runner_held = stack.enter_context(
            HeldFile(
                root,
                WAVE4_RUNNER_PATH,
                EXPECTED_WAVE4_RUNNER_RAW,
            )
        )
        runner_held = stack.enter_context(HeldFile(root, RUNNER_PATH, None))
        runner_tests_held = stack.enter_context(
            HeldFile(root, RUNNER_TESTS_PATH, EXPECTED_RUNNER_TESTS_RAW)
        )
        validate_runner(runner_held.raw, self_held.raw)
        runner_normalized = sha256(
            normalized_runner_bytes(runner_held.raw)
        )
        decision_checker = load_decision_checker(
            decision_checker_held.raw
        )
        live_decision = decision_checker.run_check(root)
        identity = live_decision.get("identityResolution")
        preparation = live_decision.get("sourceAcquisitionPreparation")
        closure = live_decision.get("closure")
        predecessor = live_decision.get("predecessorBindings", {}).get(
            "combinedFixedPointV15"
        )
        require(
            canonical_bytes(live_decision) == decision_held.raw
            and live_decision["contentBinding"]["sha256"]
            == EXPECTED_DECISION_CONTENT,
            "E_DECISION",
        )
        require(
            live_decision.get("authority")
            == {
                "acquisitionAuthorityGranted": False,
                "authenticationRequired": False,
                "compileAuthorized": False,
                "decisionAuthorityGranted": False,
                "dependencySourceExecutionAuthorized": False,
                "deploymentAuthorized": False,
                "deviceInteractionRequired": False,
                "dnsAuthorized": False,
                "executionAuthorityGranted": False,
                "externalAuthenticationRequired": False,
                "fileWriteAuthorized": False,
                "filesystemExtractionAuthorized": False,
                "gitWriteAuthorized": False,
                "networkAuthorized": False,
                "ownerProofRequired": False,
                "packageManagerAuthorized": False,
                "passwordRequired": False,
                "privateKeyRequired": False,
                "productRuntimeNetworkAuthorized": False,
                "publicationAuthorityGranted": False,
                "repositoryOwnerIdentityProofRequired": False,
                "signatureRequired": False,
                "socketAuthorized": False,
                "sourceExtractionAuthorized": False,
                "sourceLoadOrExecutionAuthorized": False,
                "subprocessAuthorized": False,
                "tokenRequired": False,
                "userActionRequired": False,
            }
            and type(identity) is dict
            and identity.get("tupleCount") == 1
            and not isinstance(identity.get("tupleCount"), bool)
            and identity.get("blockedTupleCount") == 0
            and not isinstance(identity.get("blockedTupleCount"), bool)
            and identity.get("conflictingIdentityCount") == 0
            and not isinstance(identity.get("conflictingIdentityCount"), bool)
            and identity.get("compactIdentitySha256")
            == DECISION_COMPACT_IDENTITY
            and identity.get("fullWitnessSha256")
            == DECISION_FULL_WITNESS
            and type(identity.get("tuples")) is list
            and len(identity["tuples"]) == 1
            and identity["tuples"][0]
            == {
                "acquisitionAuthorized": False,
                "acquisitionReady": True,
                "goModH1":
                    "h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI=",
                "goModH1WitnessCount": 1,
                "identityConflict": False,
                "identityPairComplete": True,
                "module": "golang.org/x/tools",
                "moduleZipH1":
                    "h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc=",
                "moduleZipH1WitnessCount": 1,
                "parentDeclarationComplete": True,
                "parentDeclarationCount": 1,
                "selectedByGraphAlgorithm": False,
                "tupleOrder": 1,
                "version": "v0.33.0",
            }
            and type(preparation) is dict
            and preparation.get("acquisitionReady") is True
            and preparation.get("acquisitionAuthorizedByThisDecision")
            is False
            and preparation.get("namespaceCleanAtDecisionCheck") is True
            and preparation.get("namespaceReservationClaimed") is False
            and preparation.get("permitOrRunnerCreated") is False
            and preparation.get("requestCount") == 2
            and not isinstance(preparation.get("requestCount"), bool)
            and preparation.get("requestSetCanonicalSha256")
            == DECISION_REQUEST_SET
            and preparation.get("requestSet")
            == decision_checker.expected_request_set()
            and closure
            == {
                "candidateSelected": False,
                "dependencyClosureComplete": False,
                "dependencyFixedPointReached": False,
                "librarySelected": False,
                "releaseReady": False,
                "rungThreeComplete": False,
                "semanticClosureComplete": False,
                "wave17AcquisitionComplete": False,
                "wave17AcquisitionReady": True,
                "wave17IdentityResolved": True,
            }
            and live_decision.get("status")
            == (
                "wave17_exact_1_frontier_identity_classified_1_complete_"
                "0_blocked_acquisition_ready_not_authorized"
            )
            and live_decision.get("result")
            == (
                "exact_1_version_vertex_0_selected_1_nonselected_"
                "1_complete_h1_pair_acquisition_ready_not_authorized"
            )
            and type(predecessor) is dict
            and predecessor.get("wave16NamespaceAnchor")
            == {
                "path": NAMESPACE_ANCHOR_PATH,
                "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
            },
            "E_DECISION_SEMANTICS",
        )
        permit = content_bound(
            permit_payload(
                checker_raw_sha256=sha256(self_held.raw),
                runner_raw_sha256=sha256(runner_held.raw),
                runner_normalized_sha256=runner_normalized,
            )
        )
        if verify_disk:
            permit_held = stack.enter_context(
                HeldFile(root, PERMIT_PATH, None)
            )
            require(
                permit_held.raw == canonical_bytes(permit)
                and strict_json(permit_held.raw) == permit,
                "E_PERMIT",
            )
        reserved.barrier()
        terminal.barrier()
        for held in (
            self_held,
            self_tests_held,
            decision_held,
            decision_checker_held,
            permit_reader_held,
            wave4_checker_held,
            wave4_runner_held,
            runner_held,
            runner_tests_held,
        ):
            held.barrier()
    summary = {
        "claimExists": False,
        "documentType":
            "aetherlink.wave17-source-acquisition-package-check",
        "executionReady": True,
        "externalAuthenticationRequired": False,
        "fileWriteCount": 0,
        "networkUsed": False,
        "permitConsumed": False,
        "productRuntimeNetworkUsed": False,
        "requestCount": 2,
        "runnerInvoked": False,
        "schemaVersion": "1.0",
        "sourceAcquired": False,
        "status": "authorized_not_consumed",
        "subprocessCount": 0,
        "tupleCount": 1,
        "userActionRequired": False,
        "validationPassed": True,
    }
    return {"decision": live_decision, "permit": permit}, summary


def error_document(code: str) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.wave17-source-acquisition-package-error",
        "externalAuthenticationRequired": False,
        "failureCode": code,
        "fileWriteAuthorized": False,
        "networkAuthorized": False,
        "permitConsumed": False,
        "productRuntimeNetworkAuthorized": False,
        "runnerInvoked": False,
        "schemaVersion": "1.0",
        "status": "failed_closed",
        "subprocessAuthorized": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False, allow_abbrev=False)
        parser.add_argument("--print-permit", action="store_true")
        args = parser.parse_args(argv)
        values, summary = evaluate(not args.print_permit)
        sys.stdout.buffer.write(
            canonical_bytes(values["permit"] if args.print_permit else summary)
        )
        return 0
    except CheckError as error:
        sys.stdout.buffer.write(canonical_bytes(error_document(error.code)))
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(error_document("E_INTERNAL"))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
