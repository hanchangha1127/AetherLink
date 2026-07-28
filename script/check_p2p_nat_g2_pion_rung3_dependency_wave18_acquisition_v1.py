#!/usr/bin/env python3
"""Validate the Wave18 one-use acquisition package without consuming it."""

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
            "Wave18 acquisition checker requires `python3 -I -B -S`"
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
    "decision-wave18-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave18-v1.md"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "execution-permit-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_decision_v1.py"
)
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition_v1.py"
)
SELF_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave18_v1_once.py"
)
RUNNER_TESTS_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave18_v1_once.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
WAVE4_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)
SELF_NORMALIZED_SHA256 = (
    "e9a227bcdf6f5cd23b4f243f2358d506950cf5721c0414dd1163d70e6df2d579"
)
EXPECTED_DECISION_RAW = (
    "c90d16a7c7194c7a6dbde2be9bd99f4101a3a8cd1722278209fe5df8bf6371fa"
)
EXPECTED_DECISION_CONTENT = (
    "c75e5751d3e7c67939251d56e212f95f85439d05684cd50a49701de3e099803d"
)
EXPECTED_DECISION_CHECKER_RAW = (
    "bad407e7e0c95dc843ccc7bd7b0aa578c10f70b0592c110eab52fba0c6a73b57"
)
EXPECTED_DECISION_CHECKER_NORMALIZED = (
    "0bdec01037fd269627cfbc3e6a0c968a5a16d2c946016ee552ca07727fc3379d"
)
EXPECTED_DECISION_READER_RAW = (
    "862ac89248970b9b4d59230e6b9f894b3fc49ed82f151608687e82cb8b1d1a2d"
)
EXPECTED_DECISION_TESTS_RAW = (
    "e6ae108af2326c97ac2db488451922640ddecefe576d8c7dedd0415a6e57904d"
)
V16_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v16.py"
V16_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v16.py"
V16_CHECKER_RAW = (
    "2e388d466c5346fa6f82b7fd23fa6dca24009acadacdd62f1fe2ba25b0a10879"
)
V16_CHECKER_NORMALIZED = (
    "7dd2c81a2032a374192f7c502afc65305d97f7c1e3699654e416b60bf64c6bd5"
)
V16_TESTS_RAW = (
    "15cf4d56a68b9f0cfd61554b24e781357066b27e63c90c871dfb0cde19c80889"
)
V16_CONTENT = (
    "90928eb85eded2938b25a0beec82c00ebcd69147bf92733bc65a528d26c00e03"
)
V16_INPUT_SET = (
    "15705de20633cdf4bf473c82a634136f481a2c131e7960a0a6cbdeccf10397a7"
)
V16_SOURCE_BINDINGS = (
    "401a3e85faacc150944d883495fca4b22e4cac1933c0308aedaec228a7c872ea"
)
V16_GRAPH = (
    "db7e36664afd819c72e9c9916bd7053782282954ed4f359c550b7972b74147a2"
)
V16_FRONTIER = (
    "fe15a3ea57682b276a6f11a2c2fd998d9120640fac40038fc9c1f100e50750b5"
)
DECISION_COMPACT_IDENTITY = (
    "53a711ff8b8771d698ac0df4448a6155eddc69179e1895d8619afd104f7623d7"
)
DECISION_FULL_WITNESS = (
    "c95159a8c9b5fbf06f54830a06c59c2f358b8ec5901c3a467fabd0ad64ef5419"
)
DECISION_REQUEST_SET = (
    "3c13b764b7267efe885528d9f7d4fe31d6b7bdac48839f95e60bb5bd45a7d836"
)
PERMIT_READER_RAW_SHA256 = (
    "abe114edafaf7f1ed7dd11af5179bf39d6577c95ac87bc64f86ed57b9402fe8c"
)
RESOURCE_CONTRACT_CANONICAL_SHA256 = (
    "86587f7dbea64ab85bdfd32287595007577de1ea3d0bb554c6471af81b4d8602"
)
DECISION_TO_PERMIT_PROJECTION_SHA256 = (
    "acb203748c6976b219949a73a89da48a381f6db4d33faa6f91fd5e9e6ab17304"
)
EXPECTED_WAVE4_CHECKER_RAW = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
EXPECTED_WAVE4_RUNNER_RAW = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)
EXPECTED_SELF_TESTS_RAW = (
    "589f27f6754e357207e90f1a275126acba4f7f1008821dd0f18df4f904ce7c4e"
)
EXPECTED_RUNNER_TESTS_RAW = (
    "f45a478e0ed4a36bebaf4f2360181c4287ab5bfa09113238fa6b9eaf534b4dad"
)

PROXY_HOST = "proxy.golang.org"
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
NAMESPACE_ANCHOR_PATH = f"{DEPENDENCY_ROOT}/.wave-17-v1.claim"
NAMESPACE_ANCHOR_RAW_SHA256 = (
    "3090e729d99c46c4b4d1e4242d6f25c08e2345062dfb6c15e1e87d3edf632fad"
)
CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-18-v1.claim"
STAGING_PREFIX = ".wave-18-v1-staging-"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-18-v1"
FINAL_ACCEPTED = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-receipt-v1.json"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-manifest-v1.json"
)
READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "readback-manifest-v1.json"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-18-v1-readback.claim"
READBACK_TEMP_PREFIX = ".wave-18-readback-v1-"
MAX_MOD_BYTES = 1 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_AGGREGATE_MOD_BYTES = 3 * 1024 * 1024
MAX_AGGREGATE_ZIP_BYTES = 48 * 1024 * 1024
MAX_AGGREGATE_BYTES = 51 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
MAX_ZIP_FILES = 20_000
MAX_ZIP_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ZIP_FILE_BYTES = 128 * 1024 * 1024
MAX_ZIP_NAME_BYTES = 1_024
MAX_ALL_ZIP_FILES = 60_000
MAX_ALL_ZIP_UNCOMPRESSED_BYTES = 384 * 1024 * 1024
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


def typed_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (
            set(actual) == set(expected)
            and all(
                typed_equal(actual[key], expected[key])
                for key in expected
            )
        )
    if type(expected) is list:
        return (
            len(actual) == len(expected)
            and all(
                typed_equal(left, right)
                for left, right in zip(actual, expected)
            )
        )
    if type(expected) is tuple:
        return (
            len(actual) == len(expected)
            and all(
                typed_equal(left, right)
                for left, right in zip(actual, expected)
            )
        )
    return bool(actual == expected)


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
    """Hold the dependency namespace and prove all Wave18 names absent."""

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
    """Pin every byte that grants or implements one Wave18 attempt."""

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
        rows = (
            list(self.permit["decisionBinding"]["files"])
            + list(self.permit["toolBindings"])
            + list(self.permit["primitiveBindings"])
        )
        predecessor = self.permit["predecessorBindings"][
            "combinedFixedPointV16"
        ]
        anchor = predecessor["wave17NamespaceAnchor"]
        specs = [
            (row["path"], row["rawSha256"])
            for row in rows
        ] + [
            (
                self.permit["readerDocumentBinding"]["path"],
                self.permit["readerDocumentBinding"]["rawSha256"],
            ),
            (PERMIT_PATH, sha256(canonical_bytes(self.permit))),
            (
                predecessor["checkerPath"],
                predecessor["checkerRawSha256"],
            ),
            (
                predecessor["testsPath"],
                predecessor["testsRawSha256"],
            ),
            (anchor["path"], anchor["rawSha256"]),
        ]
        require(
            all(
                type(path) is str
                and type(digest) is str
                and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                for path, digest in specs
            )
            and len({path for path, _ in specs}) == len(specs),
            "E_AUTHORITY_PATH",
        )
        try:
            self.held = [
                self.stack.enter_context(
                    HeldFile(self.root, path, digest)
                )
                for path, digest in sorted(specs)
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
    module = types.ModuleType("aetherlink_wave18_decision_checker_pinned")
    module.__dict__.update(
        {
            "__file__": str(ROOT / DECISION_CHECKER_PATH),
            "__name__": "aetherlink_wave18_decision_checker_pinned",
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


EXPECTED_TUPLES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "golang.org/x/mod",
        "v0.24.0",
        "bb2025870bcef7a0c287192f498f0138c441987a31a5c93bbe69ac05c5d349e7",
        "h1:IXM97Txy2VM4PJ3gI61r1YEk/gAj6zAHN3AdZt6S9Ww=",
        "h1:ZfthKaKaT4NrhGVZHO1/WDTwGES4De8KtWO0SIbNJMU=",
    ),
    (
        "golang.org/x/net",
        "v0.40.0",
        "3c84a9eecca520aed886113ab5bf71b0c60c4f09df0144e66e385dae973eda2b",
        "h1:y0hY0exeL2Pku80/zKK7tpntoX23cqL3Oa6njdgRtds=",
        "h1:79Xs7wF06Gbdcg4kdCCIQArK11Z1hr5POQ6+fIYHNuY=",
    ),
    (
        "golang.org/x/sync",
        "v0.14.0",
        "4615480e24f0c4184e4c21ec74e129cb39fbe55c729ca6c997146da3a3924000",
        "h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=",
        "h1:woo0S4Yywslg6hp4eUFjTVOyKt0RookbpAHG4c1HmhQ=",
    ),
)
SOURCE_REQUEST_KEYS = {
    "acceptedFileName",
    "acquisitionAuthorized",
    "authenticationRequired",
    "expectedH1",
    "host",
    "maximumResponseBytes",
    "method",
    "module",
    "networkAuthorized",
    "requestOrdinal",
    "resourceKind",
    "selectedByGraphAlgorithm",
    "tupleOrder",
    "url",
    "version",
}


def expected_identity_rows() -> list[dict[str, Any]]:
    return [
        {
            "acquisitionAuthorized": False,
            "acquisitionReady": True,
            "goModH1": mod_h1,
            "goModH1WitnessCount": 1,
            "identityConflict": False,
            "identityPairComplete": True,
            "module": module,
            "moduleZipH1": zip_h1,
            "moduleZipH1WitnessCount": 1,
            "parentDeclarationComplete": True,
            "parentDeclarationCount": 1,
            "selectedByGraphAlgorithm": False,
            "tupleOrder": tuple_order,
            "version": version,
        }
        for tuple_order, (
            module,
            version,
            _,
            mod_h1,
            zip_h1,
        ) in enumerate(EXPECTED_TUPLES, 1)
    ]


def resource_contract(
    decision: Mapping[str, Any],
) -> list[dict[str, Any]]:
    require(type(decision) is dict, "E_DECISION_PROJECTION")
    preparation = decision.get("sourceAcquisitionPreparation")
    require(type(preparation) is dict, "E_DECISION_PROJECTION")
    source = preparation.get("requestSet")
    require(
        type(preparation.get("requestCount")) is int
        and preparation["requestCount"] == 6
        and preparation.get("requestOrder")
        == "tuple_order_ascending_mod_then_zip"
        and preparation.get("proxyHost") == PROXY_HOST
        and preparation.get("acquisitionReady") is True
        and type(preparation.get("acquisitionReady")) is bool
        and preparation.get("acquisitionAuthorizedByThisDecision") is False
        and type(
            preparation.get("acquisitionAuthorizedByThisDecision")
        )
        is bool
        and preparation.get("claimPath") == CLAIM_PATH
        and preparation.get("stagingDirectoryPrefix") == STAGING_PREFIX
        and preparation.get("acceptedDirectoryPath") == FINAL_ACCEPTED
        and preparation.get("namespaceReservationClaimed") is False
        and type(preparation.get("namespaceReservationClaimed")) is bool
        and preparation.get("permitOrRunnerCreated") is False
        and type(preparation.get("permitOrRunnerCreated")) is bool
        and preparation.get("separateOneUseExecutionPermitRequired")
        is True
        and type(
            preparation.get("separateOneUseExecutionPermitRequired")
        )
        is bool
        and preparation.get("requestSetCanonicalSha256")
        == DECISION_REQUEST_SET
        and type(source) is list
        and len(source) == 6
        and sha256(canonical_bytes(source)[:-1]) == DECISION_REQUEST_SET,
        "E_DECISION_PROJECTION",
    )
    resources: list[dict[str, Any]] = []
    projection: list[dict[str, Any]] = []
    for index, item in enumerate(source):
        tuple_order = index // 2 + 1
        request_ordinal = index + 1
        kind = "mod" if index % 2 == 0 else "zip"
        module, version, digest, mod_h1, zip_h1 = EXPECTED_TUPLES[
            tuple_order - 1
        ]
        maximum = MAX_MOD_BYTES if kind == "mod" else MAX_ZIP_BYTES
        expected_h1 = mod_h1 if kind == "mod" else zip_h1
        path = f"/{module}/@v/{version}.{kind}"
        url = f"https://{PROXY_HOST}{path}"
        accepted = f"{tuple_order:03d}-{digest[:20]}.{kind}"
        require(
            type(item) is dict
            and set(item) == SOURCE_REQUEST_KEYS
            and type(item.get("requestOrdinal")) is int
            and item["requestOrdinal"] == request_ordinal
            and type(item.get("tupleOrder")) is int
            and item["tupleOrder"] == tuple_order
            and type(item.get("maximumResponseBytes")) is int
            and item["maximumResponseBytes"] == maximum
            and type(item.get("acquisitionAuthorized")) is bool
            and item["acquisitionAuthorized"] is False
            and type(item.get("networkAuthorized")) is bool
            and item["networkAuthorized"] is False
            and type(item.get("authenticationRequired")) is bool
            and item["authenticationRequired"] is False
            and type(item.get("selectedByGraphAlgorithm")) is bool
            and item["selectedByGraphAlgorithm"] is False
            and all(
                type(item.get(key)) is str
                for key in (
                    "acceptedFileName",
                    "expectedH1",
                    "host",
                    "method",
                    "module",
                    "resourceKind",
                    "url",
                    "version",
                )
            )
            and item["acceptedFileName"] == accepted
            and item["expectedH1"] == expected_h1
            and item["host"] == PROXY_HOST
            and item["method"] == "GET"
            and item["module"] == module
            and item["resourceKind"] == kind
            and item["url"] == url
            and item["version"] == version
            and sha256(f"{module}\n{version}\n".encode("utf-8"))
            == digest,
            "E_DECISION_PROJECTION",
        )
        resource = {
            "acceptedFileName": accepted,
            "expectedH1": expected_h1,
            "host": PROXY_HOST,
            "kind": kind,
            "maximumResponseBodyBytes": maximum,
            "method": "GET",
            "module": module,
            "path": path,
            "port": 443,
            "requestOrdinal": request_ordinal,
            "selectedByGraphAlgorithm": False,
            "tupleDigestSha256": digest,
            "tupleId": f"wave18-{tuple_order:03d}-{digest[:12]}",
            "tupleOrder": tuple_order,
            "url": url,
            "version": version,
        }
        resources.append(resource)
        projection.append(
            {
                "decisionRequest": item,
                "permitResource": resource,
            }
        )
    require(
        sha256(canonical_bytes(resources))
        == RESOURCE_CONTRACT_CANONICAL_SHA256
        and sha256(canonical_bytes(projection))
        == DECISION_TO_PERMIT_PROJECTION_SHA256,
        "E_DECISION_PROJECTION",
    )
    return resources


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
        "wave18PublicProxy6GetAcquisitionAuthorizedOnce": True,
    }


def permit_payload(
    *,
    decision: Mapping[str, Any],
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
    resources = resource_contract(decision)
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
            "maximumRequestCount": 6,
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
                "wave18_exact_3_frontier_identity_classified_3_complete_"
                "0_blocked_acquisition_ready_not_authorized"
            ),
            "typedProjectionCanonicalSha256":
                DECISION_TO_PERMIT_PROJECTION_SHA256,
        },
        "documentType":
            "aetherlink.wave18-source-acquisition-execution-permit",
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
            "completeTupleCount": 3,
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
        "nextAction": "execute_bound_wave18_source_acquisition_once",
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
            "g2-pion-rung3-wave18-6-resource-source-acquisition-"
            "execution-permit-v1",
        "predecessorBindings": {
            "combinedFixedPointV16": {
                "checkerNormalizedSha256": V16_CHECKER_NORMALIZED,
                "checkerPath": V16_CHECKER_PATH,
                "checkerRawSha256": V16_CHECKER_RAW,
                "combinedInputSetSha256": V16_INPUT_SET,
                "contentSha256": V16_CONTENT,
                "frontierSha256": V16_FRONTIER,
                "graphSha256": V16_GRAPH,
                "sourceBindingsSha256": V16_SOURCE_BINDINGS,
                "testsPath": V16_TESTS_PATH,
                "testsRawSha256": V16_TESTS_RAW,
                "totalFullSourceReconstructionCount": 30,
                "totalGraphArchiveOpenCount": 4056,
                "wave17NamespaceAnchor": {
                    "path": NAMESPACE_ANCHOR_PATH,
                    "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
                },
            }
        },
        "readerDocumentBinding": {
            "path": PERMIT_READER_PATH,
            "rawSha256": PERMIT_READER_RAW_SHA256,
        },
        "recordedDate": "2026-07-28",
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
            "requestCount": 6,
            "decisionToPermitTypedProjectionCanonicalSha256":
                DECISION_TO_PERMIT_PROJECTION_SHA256,
            "resourcesCanonicalSha256":
                RESOURCE_CONTRACT_CANONICAL_SHA256,
            "sourceRequestSetCanonicalSha256": DECISION_REQUEST_SET,
            "tupleCount": 3,
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
                "role": "wave18_acquisition_checker",
            },
            {
                "path": SELF_TESTS_PATH,
                "rawSha256": EXPECTED_SELF_TESTS_RAW,
                "role": "wave18_acquisition_checker_tests",
            },
            {
                "normalizedSha256": runner_normalized_sha256,
                "path": RUNNER_PATH,
                "rawSha256": runner_raw_sha256,
                "role": "wave18_one_use_runner",
            },
            {
                "path": RUNNER_TESTS_PATH,
                "rawSha256": EXPECTED_RUNNER_TESTS_RAW,
                "role": "wave18_one_use_runner_tests",
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
            "successRequiresNoActiveOperationAndExact6CommittedCounts": True,
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
            "exact_6_resource_one_use_wave18_acquisition_authorized_not_consumed",
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
            "combinedFixedPointV16"
        )
        require(
            canonical_bytes(live_decision) == decision_held.raw
            and live_decision["contentBinding"]["sha256"]
            == EXPECTED_DECISION_CONTENT,
            "E_DECISION",
        )
        require(
            typed_equal(
                live_decision.get("authority"),
                {
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
                },
            )
            and type(identity) is dict
            and all(
                type(identity.get(key)) is int
                for key in (
                    "blockedTupleCount",
                    "completeIdentityPairCount",
                    "conflictingIdentityCount",
                    "goModH1WitnessCount",
                    "graphSelectedTupleCount",
                    "moduleZipH1WitnessCount",
                    "parentDeclarationCount",
                    "tupleCount",
                    "versionSpecificNonSelectedTupleCount",
                )
            )
            and identity.get("tupleCount") == 3
            and identity.get("completeIdentityPairCount") == 3
            and identity.get("blockedTupleCount") == 0
            and identity.get("conflictingIdentityCount") == 0
            and identity.get("goModH1WitnessCount") == 3
            and identity.get("graphSelectedTupleCount") == 0
            and identity.get("moduleZipH1WitnessCount") == 3
            and identity.get("parentDeclarationCount") == 3
            and identity.get("versionSpecificNonSelectedTupleCount") == 3
            and identity.get("compactIdentitySha256")
            == DECISION_COMPACT_IDENTITY
            and identity.get("fullWitnessSha256")
            == DECISION_FULL_WITNESS
            and type(identity.get("tuples")) is list
            and typed_equal(identity["tuples"], expected_identity_rows())
            and type(preparation) is dict
            and preparation.get("acquisitionReady") is True
            and type(preparation.get("acquisitionReady")) is bool
            and preparation.get("acquisitionAuthorizedByThisDecision")
            is False
            and type(
                preparation.get("acquisitionAuthorizedByThisDecision")
            )
            is bool
            and preparation.get("namespaceCleanAtDecisionCheck") is True
            and type(preparation.get("namespaceCleanAtDecisionCheck")) is bool
            and preparation.get("namespaceReservationClaimed") is False
            and type(preparation.get("namespaceReservationClaimed")) is bool
            and preparation.get("permitOrRunnerCreated") is False
            and type(preparation.get("permitOrRunnerCreated")) is bool
            and type(preparation.get("requestCount")) is int
            and preparation.get("requestCount") == 6
            and preparation.get("requestSetCanonicalSha256")
            == DECISION_REQUEST_SET
            and typed_equal(
                preparation.get("requestSet"),
                decision_checker.expected_request_set(),
            )
            and typed_equal(
                closure,
                {
                    "candidateSelected": False,
                    "dependencyClosureComplete": False,
                    "dependencyFixedPointReached": False,
                    "librarySelected": False,
                    "releaseReady": False,
                    "rungThreeComplete": False,
                    "semanticClosureComplete": False,
                    "wave18AcquisitionComplete": False,
                    "wave18AcquisitionReady": True,
                    "wave18IdentityResolved": True,
                },
            )
            and live_decision.get("status")
            == (
                "wave18_exact_3_frontier_identity_classified_3_complete_"
                "0_blocked_acquisition_ready_not_authorized"
            )
            and live_decision.get("result")
            == (
                "exact_3_version_vertices_0_selected_3_nonselected_"
                "3_complete_h1_pairs_acquisition_ready_not_authorized"
            )
            and typed_equal(
                predecessor,
                {
                    "checkerNormalizedSha256": V16_CHECKER_NORMALIZED,
                    "checkerPath": V16_CHECKER_PATH,
                    "checkerRawSha256": V16_CHECKER_RAW,
                    "combinedInputSetSha256": V16_INPUT_SET,
                    "contentSha256": V16_CONTENT,
                    "fixedPointReached": False,
                    "frontierSha256": V16_FRONTIER,
                    "frontierTupleCount": 3,
                    "graphSha256": V16_GRAPH,
                    "sourceBindingCount": 359,
                    "sourceBindingsSha256": V16_SOURCE_BINDINGS,
                    "testsPath": V16_TESTS_PATH,
                    "testsRawSha256": V16_TESTS_RAW,
                    "totalFullSourceReconstructionCount": 30,
                    "totalGraphArchiveOpenCount": 4056,
                    "wave17NamespaceAnchor": {
                        "path": NAMESPACE_ANCHOR_PATH,
                        "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
                    },
                },
            ),
            "E_DECISION_SEMANTICS",
        )
        permit = content_bound(
            permit_payload(
                decision=live_decision,
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
            "aetherlink.wave18-source-acquisition-package-check",
        "executionReady": True,
        "externalAuthenticationRequired": False,
        "fileWriteCount": 0,
        "networkUsed": False,
        "permitConsumed": False,
        "productRuntimeNetworkUsed": False,
        "requestCount": 6,
        "runnerInvoked": False,
        "schemaVersion": "1.0",
        "sourceAcquired": False,
        "status": "authorized_not_consumed",
        "subprocessCount": 0,
        "tupleCount": 3,
        "userActionRequired": False,
        "validationPassed": True,
    }
    return {"decision": live_decision, "permit": permit}, summary


def error_document(code: str) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.wave18-source-acquisition-package-error",
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
