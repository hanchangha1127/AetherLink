#!/usr/bin/env python3
"""Validate the read-only Wave12 identity and acquisition decision.

Run only with ``python3 -I -B -S``.  The checker executes the exact pinned
combined-v10 candidate, then scans the retained 317 inputs twice using only the
root/external ``go.mod`` bytes and ZIP-contained ``go.sum`` bytes.  It does
not acquire, extract, load, execute, or compile dependency source.
"""

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
            "Wave12 decision checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
import base64
from contextlib import ExitStack
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import stat
import types
from typing import Any, Mapping, Sequence
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave12-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave12-v1.md"
)
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave12_decision_v1.py"
)
SELF_NORMALIZED_SHA256 = (
    "b8702241e4455fb49d7bcae13857d6d3c2a4cad181390ecea8009d229e3d9051"
)
TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave12_decision_v1.py"
)
TESTS_RAW_SHA256 = (
    "196fcdaf9a20a60d1b29b628492d1c3f0164805adc5df05678921437e7243def"
)
READER_RAW_SHA256 = (
    "31036c0f25364c5f316c30a4541a6a649a13cdcc9952ec9df9cf2c94a1de5398"
)
V10_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py"
V10_CHECKER_RAW_SHA256 = (
    "11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985"
)
V10_CHECKER_NORMALIZED_SHA256 = (
    "ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751"
)
V10_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v10.py"
V10_TESTS_RAW_SHA256 = (
    "ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35"
)
V10_CANDIDATE_CONTENT_SHA256 = (
    "d7feddd3b291756c36359b013ea05aaa2f25cb83605daaeb493c0395ff9cc4f7"
)
V10_INPUT_SET_SHA256 = (
    "f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be"
)
V10_SOURCE_BINDINGS_SHA256 = (
    "067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c"
)
V10_GRAPH_SHA256 = (
    "77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4"
)
V10_FRONTIER_SHA256 = (
    "8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05"
)
COMPACT_IDENTITY_SHA256 = (
    "23b6b188a88c5bdb87abe99325ec7a6d4580605ca69869f2614e36e134c07752"
)
FULL_WITNESS_SHA256 = (
    "2b13a602a2faf12ea2eb5f6d578a562033148ccded4035799756d969b96bdfa0"
)
DECLARATION_WITNESS_SHA256 = (
    "4270ecd062e70ffa00ebcbbcec9bc65ebadcb6c6810eeb80b05eb0ab8c14e9d2"
)
GO_MOD_H1_WITNESS_SHA256 = (
    "33ad9b08e9497df211aa43bbd74895a1bc6f0f56a1cda0fcb125aa7940b3fa0e"
)
MODULE_ZIP_H1_WITNESS_SHA256 = (
    "98a16f5f2393280c989afe77bb878676db5573d476c26fec3a59988790217e29"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-wave12-identity-acquisition-decision-check-v1"
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-identity-and-"
    "acquisition-decision-wave12-v1"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
NAMESPACE_ANCHOR_PATH = f"{DEPENDENCY_ROOT}/.wave-11-v1.claim"
NAMESPACE_ANCHOR_RAW_SHA256 = (
    "a41663bd827b8f07e0e04e887b21a7306c0ba286396e43d854ea3f2369a3e985"
)
WAVE12_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-12-v1.claim"
WAVE12_STAGING_PREFIX = ".wave-12-v1-staging-"
WAVE12_ACCEPTED_PATH = f"{DEPENDENCY_ROOT}/wave-12-v1/accepted"
MAXIMUM_CODE_BYTES = 4 * 1024 * 1024
MAXIMUM_DECISION_BYTES = 8 * 1024 * 1024
MAXIMUM_SOURCE_BYTES = 256 * 1024 * 1024
MAXIMUM_GO_METADATA_BYTES = 4 * 1024 * 1024
MAXIMUM_ARCHIVE_ENTRIES = 300_000
EXPECTED_FRONTIER_COUNT = 4
EXPECTED_GRAPH_SELECTED_TUPLE_COUNT = 0
EXPECTED_GO_SUM_ENTRY_COUNT = 109
EXPECTED_PARENT_DECLARATION_COUNT = 4
EXPECTED_GO_MOD_H1_WITNESS_COUNT = 4
EXPECTED_MODULE_ZIP_H1_WITNESS_COUNT = 4

# Filled only from the bounded retained-input discovery. Never hand-authored.
EXPECTED_IDENTITY: list[
    tuple[str, str, bool, str, str, int, int, int]
] = [
    (
        "golang.org/x/crypto",
        "v0.41.0",
        False,
        "h1:pO5AFd7FA68rFak7rOAGVuygIISepHftHnr8dr6+sUc=",
        "h1:WKYxWedPGCTVVl5+WHSSrOBT0O8lx32+zxmHxijgXp4=",
        1,
        1,
        1,
    ),
    (
        "golang.org/x/term",
        "v0.34.0",
        False,
        "h1:5jC53AEywhIVebHgPVeg0mj8OD3VO9OzclacVrqpaAw=",
        "h1:O/2T7POpk0ZZ7MAzMeWFSg6S5IpWd/RXDlM9hgM3DR4=",
        1,
        1,
        1,
    ),
    (
        "golang.org/x/text",
        "v0.28.0",
        False,
        "h1:U8nCwOR8jO/marOQ0QbDiOngZVEBB7MAiitBuMjXiNU=",
        "h1:rhazDwis8INMIwQ4tpjLDzUhx6RlXqZNPEM0huQojng=",
        1,
        1,
        1,
    ),
    (
        "golang.org/x/tools",
        "v0.35.0",
        False,
        "h1:NKdj5HkL/73byiZSJjqJgKn3ep7KjFkBOkR/Hps3VPw=",
        "h1:mBffYraMEf7aa0sB+NuKnuCy8qI/9Bughn8dC2Gu5r0=",
        1,
        1,
        1,
    ),
]

EXPECTED_DECISION_AUTHORITY = {
    "acquisitionAuthorityGranted": False,
    "authenticationRequired": False,
    "compileAuthorized": False,
    "decisionAuthorityGranted": False,
    "dependencySourceExecutionAuthorized": False,
    "dnsAuthorized": False,
    "executionAuthorityGranted": False,
    "externalAuthenticationRequired": False,
    "fileWriteAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "gitWriteAuthorized": False,
    "networkAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "publicationAuthorityGranted": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}
EXPECTED_NON_CLAIMS = (
    "retained_go_sum_h1_is_not_fresh_checksum_database_inclusion_proof",
    "wave12_dependency_source_not_acquired",
    "dependency_source_not_extracted_loaded_executed_or_compiled",
    "dependency_fixed_point_not_reached",
    "dependency_and_semantic_closure_not_complete",
    "candidate_and_library_not_selected",
    "release_not_ready",
    (
        "zero_writes_apply_only_to_the_trusted_pinned_normal_path_"
        "and_do_not_provide_an_os_syscall_sandbox"
    ),
)


class DecisionFailure(RuntimeError):
    """Content-free fail-closed error."""

    def __init__(self, code: str) -> None:
        safe = code if type(code) is str else "E_INTERNAL"
        super().__init__(safe)
        self.code = safe


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise DecisionFailure("E_USAGE")


def require(condition: bool, code: str) -> None:
    if not condition:
        raise DecisionFailure(code)


def exact_keys(value: Any, keys: Sequence[str]) -> bool:
    return type(value) is dict and set(value) == set(keys)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
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


def digest_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def strict_json(raw: bytes, code: str) -> dict[str, Any]:
    require(
        0 < len(raw) <= MAXIMUM_DECISION_BYTES
        and b"\x00" not in raw
        and b"\r" not in raw,
        code,
    )
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise DecisionFailure(code) from error
    require(
        type(value) is dict
        and raw == canonical_json_bytes(value),
        code,
    )
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization":
            "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(payload)),
    }
    return result


def normalized_self_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    require(start >= 0, "E_SELF_IDENTITY")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    require(
        payload_end - payload_start == 64
        and raw.find(marker, payload_start) < 0,
        "E_SELF_IDENTITY",
    )
    return raw[:payload_start] + (b"0" * 64) + raw[payload_end:]


def portable_name(value: str) -> str:
    require(type(value) is str, "E_WAVE12_NAMESPACE")
    return unicodedata.normalize("NFC", value).casefold()


def validate_wave12_namespace_absent(
    dependency_parent_fd: int,
    docs_parent_fd: int,
    script_parent_fd: int,
) -> None:
    try:
        dependency_names = os.listdir(dependency_parent_fd)
        docs_names = os.listdir(docs_parent_fd)
        script_names = os.listdir(script_parent_fd)
    except OSError as error:
        raise DecisionFailure("E_WAVE12_NAMESPACE") from error
    require(
        all(type(name) is str for name in dependency_names)
        and all(type(name) is str for name in docs_names)
        and all(type(name) is str for name in script_names),
        "E_WAVE12_NAMESPACE",
    )

    for name in dependency_names:
        normalized = portable_name(name)
        require(
            not normalized.startswith(".wave-12-v1")
            and not normalized.startswith("wave-12-v1"),
            "E_WAVE12_NAMESPACE",
        )

    allowed_docs = {
        DECISION_PATH.rsplit("/", 1)[-1],
        READER_PATH.rsplit("/", 1)[-1],
    }
    allowed_docs_by_portable = {
        portable_name(name): name for name in allowed_docs
    }
    for name in docs_names:
        normalized = portable_name(name)
        if normalized.startswith(
            "bounded-dependency-source-identity-and-acquisition-"
            "decision-wave12"
        ):
            require(
                allowed_docs_by_portable.get(normalized) == name,
                "E_WAVE12_NAMESPACE",
            )
        require(
            not normalized.startswith(
                "bounded-dependency-source-acquisition-wave12"
            ),
            "E_WAVE12_NAMESPACE",
        )

    allowed_tools = {SELF_PATH.rsplit("/", 1)[-1], TESTS_PATH.rsplit("/", 1)[-1]}
    allowed_tools_by_portable = {
        portable_name(name): name for name in allowed_tools
    }
    for name in script_names:
        normalized = portable_name(name)
        if "p2p_nat_g2_pion" in normalized and "wave12" in normalized:
            require(
                allowed_tools_by_portable.get(normalized) == name,
                "E_WAVE12_NAMESPACE",
            )


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def directory_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
    )


def retry_constructor_cleanup(resource: Any) -> None:
    for _ in range(2):
        try:
            resource.close()
        except BaseException:
            continue
        break


class BootstrapPinnedCodeFile:
    """Immediate-ownership bootstrap pin matching combined-v10 semantics."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str,
        normalizer: Any = None,
        maximum_bytes: int = MAXIMUM_CODE_BYTES,
    ) -> None:
        self.root = root.absolute()
        self.relative_path = relative_path
        self.normalizer = normalizer
        self.maximum_bytes = maximum_bytes
        self.root_fd = -1
        self.parent_fd = -1
        self.fd = -1
        self.owned_fds: list[int] = []
        self.directories: list[
            tuple[int, os.stat_result, int, str]
        ] = []
        self.raw = b""
        try:
            parts = relative_path.split("/")
            require(
                bool(parts)
                and all(part not in {"", ".", ".."} for part in parts),
                "E_TOOL_IDENTITY",
            )
            self.root_fd = self._own(
                os.open(
                    self.root,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                )
            )
            self._validate_directory(os.fstat(self.root_fd))
            current = self._own(os.dup(self.root_fd))
            for component in parts[:-1]:
                child = self._own(
                    os.open(
                        component,
                        os.O_RDONLY
                        | os.O_DIRECTORY
                        | os.O_NOFOLLOW
                        | os.O_NONBLOCK
                        | os.O_CLOEXEC,
                        dir_fd=current,
                    )
                )
                info = os.fstat(child)
                self._validate_directory(info)
                self.directories.append(
                    (child, info, current, component)
                )
                current = child
            self.parent_fd = current
            self.name = parts[-1]
            self.fd = self._own(
                os.open(
                    self.name,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    dir_fd=self.parent_fd,
                )
            )
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial, self.maximum_bytes)
            first = self._read_pass()
            second = self._read_pass()
            checked = first if normalizer is None else normalizer(first)
            require(
                first == second
                and sha256_bytes(checked) == expected_sha256,
                "E_TOOL_IDENTITY",
            )
            self.raw = first
            self.final_barrier()
        except BaseException:
            retry_constructor_cleanup(self)
            raise

    def _own(self, fd: int) -> int:
        self.owned_fds.append(fd)
        return fd

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_TOOL_IDENTITY",
        )

    @staticmethod
    def _validate_file(
        info: os.stat_result,
        maximum_bytes: int = MAXIMUM_CODE_BYTES,
    ) -> None:
        require(
            type(maximum_bytes) is int
            and 0 < maximum_bytes <= MAXIMUM_DECISION_BYTES
            and stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= maximum_bytes,
            "E_TOOL_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before, self.maximum_bytes)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_TOOL_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", "E_TOOL_IDENTITY")
        require(
            file_identity(os.fstat(self.fd)) == file_identity(before),
            "E_TOOL_IDENTITY",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        current = os.fstat(self.fd)
        named = os.stat(
            self.name,
            dir_fd=self.parent_fd,
            follow_symlinks=False,
        )
        require(
            file_identity(current)
            == file_identity(named)
            == file_identity(self.initial),
            "E_TOOL_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            require(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                == directory_identity(
                    os.stat(
                        component,
                        dir_fd=parent,
                        follow_symlinks=False,
                    )
                ),
                "E_TOOL_IDENTITY",
            )

    def close(self) -> None:
        errors: list[OSError] = []
        seen: set[int] = set()
        remaining: set[int] = set()

        def close_once(fd: int) -> None:
            if fd < 0 or fd in seen:
                return
            seen.add(fd)
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
                try:
                    os.fstat(fd)
                except OSError as probe_error:
                    if probe_error.errno != errno.EBADF:
                        remaining.add(fd)
                else:
                    remaining.add(fd)

        previous = list(self.owned_fds)
        for owned_fd in reversed(previous):
            close_once(owned_fd)
        self.owned_fds = [
            owned_fd for owned_fd in previous if owned_fd in remaining
        ]
        self.directories.clear()
        self.fd = self.fd if self.fd in remaining else -1
        self.parent_fd = (
            self.parent_fd if self.parent_fd in remaining else -1
        )
        self.root_fd = (
            self.root_fd if self.root_fd in remaining else -1
        )
        if errors:
            raise errors[0]

    def __enter__(self) -> "BootstrapPinnedCodeFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_v10_checker(
    held: BootstrapPinnedCodeFile,
) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_v10_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V10_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_v10_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V10_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise DecisionFailure("E_V10_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "SafeHeldInputSet",
        "generate_candidate",
        "harden_checker_module",
        "load_v9_checker",
        "normalized_self_bytes",
    ):
        require(
            callable(getattr(module, name, None)),
            "E_V10_API",
        )
    require(
        module.SELF_PATH == V10_CHECKER_PATH
        and module.SELF_NORMALIZED_SHA256
        == V10_CHECKER_NORMALIZED_SHA256
        and sha256_bytes(held.raw) == V10_CHECKER_RAW_SHA256,
        "E_V10_API",
    )
    return module


def identity_barrier(root: Path, held: Sequence[Any]) -> None:
    try:
        named = os.stat(root, follow_symlinks=False)
        require(stat.S_ISDIR(named.st_mode), "E_ROOT_IDENTITY")
        expected = directory_identity(named)
        for item in held:
            root_fd = getattr(item, "root_fd", -1)
            require(
                type(root_fd) is int
                and root_fd >= 0
                and directory_identity(os.fstat(root_fd)) == expected,
                "E_ROOT_IDENTITY",
            )
        for item in held:
            item.final_barrier()
        require(
            directory_identity(
                os.stat(root, follow_symlinks=False)
            )
            == expected,
            "E_ROOT_IDENTITY",
        )
    except OSError as error:
        raise DecisionFailure("E_ROOT_IDENTITY") from error


def strict_text_lines(raw: bytes, code: str) -> list[str]:
    require(
        len(raw) <= MAXIMUM_GO_METADATA_BYTES
        and b"\x00" not in raw
        and b"\r" not in raw,
        code,
    )
    try:
        return raw.decode(
            "utf-8",
            errors="strict",
        ).splitlines()
    except UnicodeDecodeError as error:
        raise DecisionFailure(code) from error


def valid_h1(value: str) -> bool:
    if type(value) is not str or not value.startswith("h1:"):
        return False
    try:
        decoded = base64.b64decode(value[3:], validate=True)
    except (ValueError, base64.binascii.Error):
        return False
    return len(decoded) == 32


def strip_go_mod_comment(line: str) -> str:
    quoted = False
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if not quoted and line[index:index + 2] == "//":
            return line[:index]
    return line


def tokenize_mod_line(line: str) -> list[str]:
    try:
        return shlex.split(
            strip_go_mod_comment(line),
            comments=False,
            posix=True,
        )
    except ValueError as error:
        raise DecisionFailure("E_GO_MOD") from error


def capture_declarations(
    *,
    raw: bytes,
    runner: Any,
    targets: Mapping[tuple[str, str], Mapping[str, Any]],
    holder_module: str,
    holder_version: str,
    holder_wave: str,
    container_kind: str,
    path: str,
    container_raw_sha256: str,
    entry_raw_sha256: str | None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    try:
        runner.parse_go_mod(raw, holder_module)
    except Exception as error:
        raise DecisionFailure("E_GO_MOD") from error
    result = {key: [] for key in targets}
    block: str | None = None
    for line_number, text in enumerate(
        strict_text_lines(raw, "E_GO_MOD"),
        1,
    ):
        tokens = tokenize_mod_line(text)
        if not tokens:
            continue
        pair: tuple[str, str] | None = None
        if block is not None:
            if tokens == [")"]:
                block = None
                continue
            if block == "require":
                require(len(tokens) == 2, "E_GO_MOD")
                pair = (tokens[0], tokens[1])
        elif len(tokens) == 2 and tokens[1] == "(":
            block = tokens[0]
        elif tokens[0] == "require":
            require(len(tokens) == 3, "E_GO_MOD")
            pair = (tokens[1], tokens[2])
        if pair in targets:
            result[pair].append(
                {
                    "containerKind": container_kind,
                    "holderModule": holder_module,
                    "holderVersion": holder_version,
                    "holderWave": holder_wave,
                    "path": path,
                    "line": line_number,
                    "text": text,
                    "containerRawSha256": container_raw_sha256,
                    "entryRawSha256": entry_raw_sha256,
                }
            )
    require(block is None, "E_GO_MOD")
    return result


def parse_go_sum_entry(
    *,
    raw: bytes,
    targets: Mapping[tuple[str, str], Mapping[str, Any]],
    holder_module: str,
    holder_version: str,
    holder_wave: str,
    archive_path: str,
    archive_raw_sha256: str,
    entry_path: str,
) -> tuple[
    dict[tuple[str, str], list[dict[str, Any]]],
    dict[tuple[str, str], list[dict[str, Any]]],
]:
    zip_result = {key: [] for key in targets}
    mod_result = {key: [] for key in targets}
    entry_hash = sha256_bytes(raw)
    for line_number, text in enumerate(
        strict_text_lines(raw, "E_GO_SUM"),
        1,
    ):
        tokens = text.split()
        if not tokens:
            continue
        require(
            len(tokens) == 3 and valid_h1(tokens[2]),
            "E_GO_SUM",
        )
        module, version_token, h1 = tokens
        if version_token.endswith("/go.mod"):
            version = version_token[:-7]
            bucket = mod_result
        else:
            version = version_token
            bucket = zip_result
        pair = (module, version)
        if pair in targets:
            bucket[pair].append(
                {
                    "holderModule": holder_module,
                    "holderVersion": holder_version,
                    "holderWave": holder_wave,
                    "archivePath": archive_path,
                    "archiveRawSha256": archive_raw_sha256,
                    "entryPath": entry_path,
                    "entryRawSha256": entry_hash,
                    "line": line_number,
                    "text": text,
                    "h1": h1,
                }
            )
    return zip_result, mod_result


def merge_witnesses(
    destination: dict[tuple[str, str], list[dict[str, Any]]],
    source: Mapping[
        tuple[str, str],
        Sequence[Mapping[str, Any]],
    ],
) -> None:
    for pair, rows in source.items():
        destination[pair].extend(dict(row) for row in rows)


def validate_archive_names(
    infos: Sequence[zipfile.ZipInfo],
) -> None:
    require(0 < len(infos) <= MAXIMUM_ARCHIVE_ENTRIES, "E_ZIP")
    exact: set[str] = set()
    portable: set[str] = set()
    for info in infos:
        name = info.filename
        require(
            type(name) is str
            and bool(name)
            and "\x00" not in name
            and "\\" not in name
            and not name.startswith("/")
            and not (info.flag_bits & 0x1),
            "E_ZIP",
        )
        components = (
            name[:-1].split("/")
            if name.endswith("/")
            else name.split("/")
        )
        require(
            bool(components)
            and all(
                component not in {"", ".", ".."}
                for component in components
            ),
            "E_ZIP",
        )
        normalized = unicodedata.normalize("NFC", name).casefold()
        require(
            name not in exact and normalized not in portable,
            "E_ZIP",
        )
        exact.add(name)
        portable.add(normalized)
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        require(
            file_type in {0, stat.S_IFREG, stat.S_IFDIR}
            and not stat.S_ISLNK(mode),
            "E_ZIP",
        )


def build_identity_rows(
    *,
    wave_rows: Sequence[Mapping[str, Any]],
    declarations: Mapping[
        tuple[str, str],
        Sequence[Mapping[str, Any]],
    ],
    module_zip_h1: Mapping[
        tuple[str, str],
        Sequence[Mapping[str, Any]],
    ],
    go_mod_h1: Mapping[
        tuple[str, str],
        Sequence[Mapping[str, Any]],
    ],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    require(
        len(wave_rows) == EXPECTED_FRONTIER_COUNT,
        "E_TARGETS",
    )
    for expected_order, wave_row in enumerate(wave_rows, 1):
        require(
            wave_row["tupleOrder"] == expected_order,
            "E_TARGETS",
        )
        pair = (wave_row["module"], wave_row["version"])
        declaration_rows = sorted(
            (dict(row) for row in declarations[pair]),
            key=lambda row: (
                row["path"],
                "",
                row["line"],
                row["text"],
            ),
        )
        zip_rows = sorted(
            (dict(row) for row in module_zip_h1[pair]),
            key=lambda row: (
                row["archivePath"],
                row["entryPath"],
                row["line"],
                row["text"],
            ),
        )
        mod_rows = sorted(
            (dict(row) for row in go_mod_h1[pair]),
            key=lambda row: (
                row["archivePath"],
                row["entryPath"],
                row["line"],
                row["text"],
            ),
        )
        zip_values = sorted({row["h1"] for row in zip_rows})
        mod_values = sorted({row["h1"] for row in mod_rows})
        result.append(
            {
                "module": pair[0],
                "version": pair[1],
                "selectedByGraphAlgorithm":
                    wave_row["selectedByGraphAlgorithm"],
                "declarations": declaration_rows,
                "moduleZipH1Witnesses": zip_rows,
                "goModH1Witnesses": mod_rows,
                "tupleOrder": expected_order,
                "declarationCount": len(declaration_rows),
                "moduleZipH1WitnessCount": len(zip_rows),
                "goModH1WitnessCount": len(mod_rows),
                "moduleZipH1Values": zip_values,
                "goModH1Values": mod_values,
                "declarationComplete": bool(declaration_rows),
                "moduleZipH1Complete": len(zip_values) == 1,
                "goModH1Complete": len(mod_values) == 1,
                "moduleZipH1Conflict": len(zip_values) > 1,
                "goModH1Conflict": len(mod_values) > 1,
                "identityPairComplete":
                    len(zip_values) == 1
                    and len(mod_values) == 1,
            }
        )
    return result


def scan_source_identity(
    *,
    source_bindings: Sequence[Mapping[str, Any]],
    source_raw: Mapping[str, bytes],
    wave_rows: Sequence[Mapping[str, Any]],
    runner: Any,
) -> dict[str, Any]:
    targets = {
        (row["module"], row["version"]): row
        for row in wave_rows
    }
    require(
        len(targets) == len(wave_rows) == EXPECTED_FRONTIER_COUNT,
        "E_TARGETS",
    )
    declarations = {key: [] for key in targets}
    zip_h1 = {key: [] for key in targets}
    mod_h1 = {key: [] for key in targets}
    archive_count = 0
    external_mod_count = 0
    embedded_root_go_mod_count = 0
    go_sum_entry_count = 0

    for binding in source_bindings:
        path = binding["path"]
        raw = source_raw[path]
        require(
            sha256_bytes(raw) == binding["rawSha256"],
            "E_SOURCE_BINDING",
        )
        if binding["kind"] == "mod":
            external_mod_count += 1
            merge_witnesses(
                declarations,
                capture_declarations(
                    raw=raw,
                    runner=runner,
                    targets=targets,
                    holder_module=binding["module"],
                    holder_version=binding["version"],
                    holder_wave=binding["wave"],
                    container_kind="external_mod",
                    path=path,
                    container_raw_sha256=binding["rawSha256"],
                    entry_raw_sha256=None,
                ),
            )
            continue
        require(
            binding["kind"] in {"zip", "root_zip"},
            "E_SOURCE_BINDING",
        )
        archive_count += 1
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                infos = archive.infolist()
                validate_archive_names(infos)
                if binding["kind"] == "root_zip":
                    expected_go_mod = (
                        f"{binding['module']}@"
                        f"{binding['version']}/go.mod"
                    )
                    matches = [
                        info
                        for info in infos
                        if info.filename == expected_go_mod
                    ]
                    require(len(matches) == 1, "E_ROOT_GO_MOD")
                    info = matches[0]
                    require(
                        not info.is_dir()
                        and info.file_size
                        <= MAXIMUM_GO_METADATA_BYTES,
                        "E_ROOT_GO_MOD",
                    )
                    embedded = archive.read(info)
                    embedded_root_go_mod_count += 1
                    merge_witnesses(
                        declarations,
                        capture_declarations(
                            raw=embedded,
                            runner=runner,
                            targets=targets,
                            holder_module=binding["module"],
                            holder_version=binding["version"],
                            holder_wave=binding["wave"],
                            container_kind="embedded_root_mod",
                            path=(
                                f"{path}!/{info.filename}"
                            ),
                            container_raw_sha256=
                                binding["rawSha256"],
                            entry_raw_sha256=
                                sha256_bytes(embedded),
                        ),
                    )
                for info in infos:
                    if not info.filename.endswith("/go.sum"):
                        continue
                    require(
                        not info.is_dir()
                        and info.file_size
                        <= MAXIMUM_GO_METADATA_BYTES,
                        "E_GO_SUM",
                    )
                    go_sum_entry_count += 1
                    found_zip, found_mod = parse_go_sum_entry(
                        raw=archive.read(info),
                        targets=targets,
                        holder_module=binding["module"],
                        holder_version=binding["version"],
                        holder_wave=binding["wave"],
                        archive_path=path,
                        archive_raw_sha256=binding["rawSha256"],
                        entry_path=info.filename,
                    )
                    merge_witnesses(zip_h1, found_zip)
                    merge_witnesses(mod_h1, found_mod)
        except (
            OSError,
            RuntimeError,
            zipfile.BadZipFile,
        ) as error:
            raise DecisionFailure("E_ZIP") from error

    rows = build_identity_rows(
        wave_rows=wave_rows,
        declarations=declarations,
        module_zip_h1=zip_h1,
        go_mod_h1=mod_h1,
    )
    compact = [
        {
            "tupleOrder": row["tupleOrder"],
            "module": row["module"],
            "version": row["version"],
            "selectedByGraphAlgorithm":
                row["selectedByGraphAlgorithm"],
            "moduleZipH1": (
                row["moduleZipH1Values"][0]
                if len(row["moduleZipH1Values"]) == 1
                else None
            ),
            "goModH1": (
                row["goModH1Values"][0]
                if len(row["goModH1Values"]) == 1
                else None
            ),
        }
        for row in rows
    ]
    flat_declarations = [
        witness
        for row in rows
        for witness in row["declarations"]
    ]
    flat_zip = [
        witness
        for row in rows
        for witness in row["moduleZipH1Witnesses"]
    ]
    flat_mod = [
        witness
        for row in rows
        for witness in row["goModH1Witnesses"]
    ]
    return {
        "archiveCount": archive_count,
        "externalModCount": external_mod_count,
        "embeddedRootGoModCount": embedded_root_go_mod_count,
        "goSumEntryCount": go_sum_entry_count,
        "tuples": rows,
        "compactIdentity": compact,
        "compactIdentitySha256":
            sha256_bytes(digest_json_bytes(compact)),
        "fullWitnessSha256":
            sha256_bytes(digest_json_bytes(rows)),
        "declarationWitnessSha256":
            sha256_bytes(digest_json_bytes(flat_declarations)),
        "moduleZipH1WitnessSha256":
            sha256_bytes(digest_json_bytes(flat_zip)),
        "goModH1WitnessSha256":
            sha256_bytes(digest_json_bytes(flat_mod)),
    }


def require_closed_identity(scan: Mapping[str, Any]) -> None:
    rows = scan["tuples"]
    require(
        len(rows) == EXPECTED_FRONTIER_COUNT
        and len(EXPECTED_IDENTITY) == EXPECTED_FRONTIER_COUNT
        and scan["archiveCount"] == 159
        and scan["externalModCount"] == 158
        and scan["embeddedRootGoModCount"] == 1
        and scan["goSumEntryCount"] == EXPECTED_GO_SUM_ENTRY_COUNT
        and sum(row["declarationCount"] for row in rows)
        == EXPECTED_PARENT_DECLARATION_COUNT
        and sum(
            row["moduleZipH1WitnessCount"] for row in rows
        )
        == EXPECTED_MODULE_ZIP_H1_WITNESS_COUNT
        and sum(row["goModH1WitnessCount"] for row in rows)
        == EXPECTED_GO_MOD_H1_WITNESS_COUNT
        and scan["compactIdentitySha256"]
        == COMPACT_IDENTITY_SHA256
        and scan["fullWitnessSha256"] == FULL_WITNESS_SHA256
        and scan["declarationWitnessSha256"]
        == DECLARATION_WITNESS_SHA256
        and scan["moduleZipH1WitnessSha256"]
        == MODULE_ZIP_H1_WITNESS_SHA256
        and scan["goModH1WitnessSha256"]
        == GO_MOD_H1_WITNESS_SHA256,
        "E_IDENTITY_CLOSURE",
    )
    for row, expected in zip(rows, EXPECTED_IDENTITY):
        (
            module,
            version,
            selected,
            mod_h1,
            zip_h1,
            declaration_count,
            mod_count,
            zip_count,
        ) = expected
        require(
            row["module"] == module
            and row["version"] == version
            and row["selectedByGraphAlgorithm"] is selected
            and row["declarationCount"] == declaration_count
            and row["goModH1WitnessCount"] == mod_count
            and row["moduleZipH1WitnessCount"] == zip_count
            and row["goModH1Values"] == [mod_h1]
            and row["moduleZipH1Values"] == [zip_h1]
            and row["declarationComplete"] is True
            and row["identityPairComplete"] is True
            and row["goModH1Conflict"] is False
            and row["moduleZipH1Conflict"] is False,
            "E_IDENTITY_CLOSURE",
        )


def expected_frontier() -> list[dict[str, Any]]:
    return [
        {
            "module": module,
            "version": version,
            "selectedByGraphAlgorithm": selected,
            "requiresSeparateWaveDecision": True,
            "acquisitionAuthorized": False,
        }
        for (
            module,
            version,
            selected,
            _,
            _,
            _,
            _,
            _,
        ) in EXPECTED_IDENTITY
    ]


def validate_wave9_duplicate_mod_boundary(
    source_bindings: Sequence[Mapping[str, Any]],
) -> None:
    rows = [
        row
        for row in source_bindings
        if row.get("kind") == "mod"
        and row.get("tupleOrder") in {131, 132}
    ]
    require(
        len(rows) == 2
        and [row.get("tupleOrder") for row in rows] == [131, 132]
        and all(row.get("wave") == "wave9" for row in rows)
        and rows[0].get("module") == rows[1].get("module")
        and rows[0].get("rawSha256") == rows[1].get("rawSha256")
        and rows[0].get("path") != rows[1].get("path")
        and rows[0].get("tupleId") != rows[1].get("tupleId")
        and rows[0].get("version") != rows[1].get("version"),
        "E_WAVE9_DUPLICATE_MOD",
    )


def validate_v10_candidate(
    candidate: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(type(candidate) is dict, "E_V10_CANDIDATE")
    binding = candidate.get("contentBinding")
    without = dict(candidate)
    without.pop("contentBinding", None)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "candidate_without_contentBinding",
            "sha256": V10_CANDIDATE_CONTENT_SHA256,
        }
        and sha256_bytes(canonical_json_bytes(without))
        == V10_CANDIDATE_CONTENT_SHA256
        and candidate.get("schemaVersion") == "10.0"
        and candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-"
            "wave4-wave5-wave6-wave7-wave8-wave9-wave10-wave11-"
            "fixed-point-candidate"
        )
        and candidate.get("verificationOnly") is True
        and candidate.get("recordModeExposed") is False
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and candidate.get("result")
        == (
            "combined_graph_recomputed_twice_from_exact_"
            "wave1_through_wave11_source_bytes"
        )
        and candidate.get("route") == "next_wave_required"
        and candidate.get("nextAction")
        == (
            "prepare_separate_versioned_dependency_wave_identity_and_"
            "acquisition_decision"
        ),
        "E_V10_CANDIDATE",
    )
    inputs = candidate.get("inputSet")
    source_bindings = (
        inputs.get("sourceBindings")
        if type(inputs) is dict
        else None
    )
    source_keys = {
        "kind",
        "module",
        "path",
        "rawSha256",
        "tupleId",
        "tupleOrder",
        "version",
        "wave",
    }
    require(
        type(inputs) is dict
        and inputs.get("heldSourceInputCount") == 317
        and inputs.get("rootArchiveCount") == 1
        and inputs.get("resourceCount") == 316
        and inputs.get("modCount") == 158
        and inputs.get("zipCount") == 158
        and inputs.get("wave1ResourceCount") == 38
        and inputs.get("wave2ResourceCount") == 30
        and inputs.get("wave3ResourceCount") == 32
        and inputs.get("wave4ResourceCount") == 32
        and inputs.get("wave5ResourceCount") == 30
        and inputs.get("wave6ResourceCount") == 36
        and inputs.get("wave7ResourceCount") == 30
        and inputs.get("wave8ResourceCount") == 28
        and inputs.get("wave9ResourceCount") == 20
        and inputs.get("wave10ResourceCount") == 22
        and inputs.get("wave11ResourceCount") == 18
        and inputs.get("uniqueModuleVersionTupleCount") == 158
        and inputs.get("aggregateRawByteSize") == 287_352_740
        and inputs.get("combinedInputSetSha256")
        == V10_INPUT_SET_SHA256
        and type(source_bindings) is list
        and len(source_bindings) == 317
        and all(
            type(row) is dict
            and set(row) == source_keys
            and row["kind"] in {"root_zip", "mod", "zip"}
            and type(row["module"]) is str
            and type(row["version"]) is str
            and type(row["path"]) is str
            and type(row["rawSha256"]) is str
            and len(row["rawSha256"]) == 64
            and all(
                character in "0123456789abcdef"
                for character in row["rawSha256"]
            )
            and type(row["tupleOrder"]) is int
            and row["tupleOrder"] >= 0
            and type(row["tupleId"]) is str
            and type(row["wave"]) is str
            for row in source_bindings
        )
        and len({row["path"] for row in source_bindings}) == 317
        and source_bindings
        == sorted(
            source_bindings,
            key=lambda row: (
                row["tupleOrder"],
                row["kind"],
                row["path"],
            ),
        )
        and sum(
            row["kind"] == "root_zip"
            for row in source_bindings
        )
        == 1
        and sum(row["kind"] == "mod" for row in source_bindings)
        == 158
        and sum(row["kind"] == "zip" for row in source_bindings)
        == 158
        and sorted(
            {
                row["tupleOrder"]
                for row in source_bindings
                if row["kind"] != "root_zip"
            }
        )
        == list(range(1, 159))
        and len(
            {
                (row["module"], row["version"])
                for row in source_bindings
                if row["kind"] != "root_zip"
            }
        )
        == 158
        and sha256_bytes(canonical_json_bytes(source_bindings))
        == V10_INPUT_SET_SHA256
        and sha256_bytes(digest_json_bytes(source_bindings))
        == V10_SOURCE_BINDINGS_SHA256,
        "E_SOURCE_BINDING",
    )
    validate_wave9_duplicate_mod_boundary(source_bindings)
    graph = candidate.get("graphDiscovery")
    derived = candidate.get("derivedResult")
    frontier = (
        graph.get("exactFrontier")
        if type(graph) is dict
        else None
    )
    require(
        type(graph) is dict
        and graph.get("graphSha256") == V10_GRAPH_SHA256
        and graph.get("fixedPointReached") is False
        and graph.get("newTupleCount") == EXPECTED_FRONTIER_COUNT
        and derived
        == {
            "fixedPointReached": False,
            "frontierTupleCount": EXPECTED_FRONTIER_COUNT,
            "frontierSha256": V10_FRONTIER_SHA256,
        }
        and type(frontier) is list
        and len(frontier) == EXPECTED_FRONTIER_COUNT
        and all(
            exact_keys(
                row,
                {
                    "acquisitionAuthorized",
                    "module",
                    "requiresSeparateWaveDecision",
                    "selectedByGraphAlgorithm",
                    "version",
                },
            )
            and type(row["module"]) is str
            and type(row["version"]) is str
            and type(row["selectedByGraphAlgorithm"]) is bool
            and row["requiresSeparateWaveDecision"] is True
            and row["acquisitionAuthorized"] is False
            for row in frontier
        )
        and len(
            {
                (row["module"], row["version"])
                for row in frontier
            }
        )
        == EXPECTED_FRONTIER_COUNT
        and frontier == expected_frontier()
        and sha256_bytes(canonical_json_bytes(frontier))
        == V10_FRONTIER_SHA256,
        "E_V10_GRAPH",
    )
    verification = candidate.get("checkerVerification")
    counters = candidate.get("operationCounters")
    authority = candidate.get("authority")
    tool_bindings = candidate.get("toolBindings")
    terminal_bindings = candidate.get("terminalEvidenceBindings")
    auxiliary_bindings = candidate.get("auxiliaryEvidenceBindings")
    legacy_policy = candidate.get("wave9LegacyBuildCompatibilityPolicy")
    predecessor_verification = candidate.get("predecessorVerification")
    require(
        type(verification) is dict
        and verification.get("directFullInputReconstructionCount")
        == 2
        and verification.get("inheritedFullInputReconstructionCount")
        == 16
        and verification.get("totalFullInputReconstructionCount")
        == 18
        and verification.get("underlyingIndependentGraphAlgorithmCount")
        == 36
        and verification.get("pinnedV9PredecessorExecuted") is True
        and verification.get("v9TestsBindingScope")
        == "historical_metadata_only_not_live_held"
        and verification.get("v9TestsLiveHeld") is False
        and type(predecessor_verification) is dict
        and predecessor_verification.get("v9TestsBindingScope")
        == "historical_metadata_only_not_live_held"
        and predecessor_verification.get("v9TestsLiveHeld") is False
        and verification.get("canonicalGraphEqualityVerified") is True
        and verification.get("barrierBeforeReconstructionCompleted")
        is True
        and verification.get("barrierBetweenReconstructionsCompleted")
        is True
        and verification.get("barrierAfterReconstructionCompleted")
        is True
        and verification.get("workspaceRootIdentityBoundAcrossAllInputs")
        is True
        and verification.get(
            "wave11HistoricalExact36FrozenSnapshotDescriptorSetBound"
        ) is True
        and verification.get(
            "wave11LiveTerminalControlMetadataVerified"
        ) is True
        and verification.get(
            "wave11LiveFinalAndAcceptedInventoriesVerified"
        ) is True
        and verification.get(
            "wave11FinalNamespaceReverifiedAfterReconstruction"
        ) is True
        and verification.get("wave11RetainedFdPreManifestBarrierCount")
        == 3
        and verification.get("wave11CompletionAppliesToRetainedSnapshot")
        is True
        and verification.get(
            "wave11CurrentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and verification.get(
            "wave11SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and verification.get("transitiveSafePinnedClassesVerified")
        is True
        and verification.get("readOnlyProviderFacadeVerified")
        is True
        and verification.get("providerFacadeVerificationScope")
        == "trusted_pinned_normal_reconstruction_path"
        and verification.get("hardenedCheckerModuleCount") == 9
        and verification.get("providerFacadeLoadCount") == 9
        and verification.get("wave9PinnedLegacyBuildCompatibilityCount")
        == 4
        and legacy_policy
        == {
            "configuredProfileInclusionEquivalent": True,
            "directReconstructionApplicationCount": 4,
            "expectedExpression":
                "((go1.8 && !go1.9)) && ((!windows))",
            "fallbackErrorCode": "E_BUILD_CONSTRAINT",
            "fallbackErrorPhase": "source_inventory",
            "go111TrailingWordOrSemanticsChecked": True,
            "normalizedSourceSha256":
                "a46760412870548bd5bf6cfb011129769545623276e3b0385f85deb3206045f2",
            "originalLineOccurrenceCount": 1,
            "originalProviderParserTriedFirst": True,
            "rawSourceSha256":
                "042948d42899becd3c158c680d9c491ca9a57629cc893edea31ef2aae2666443",
            "sourceBytesModified": False,
        }
        and type(counters) is dict
        and counters.get("directArchiveOpenCount") == 318
        and counters.get("inheritedArchiveOpenCount") == 1_666
        and counters.get("totalArchiveOpenCount") == 1_984
        and counters.get("archiveOpenCount") == 1_984
        and counters.get("heldSourceInputCount") == 317
        and counters.get("heldTerminalEvidenceCount") == 73
        and counters.get("heldAuxiliaryEvidenceCount") == 3
        and counters.get("heldToolInputCount") == 9
        and counters.get("transitiveDistinctToolPathCount") == 11
        and counters.get("stableReadPassesPerHeldInput") == 2
        and counters.get("directFullSourceReconstructionCount") == 2
        and counters.get("inheritedFullSourceReconstructionCount") == 16
        and counters.get("totalFullSourceReconstructionCount") == 18
        and counters.get("wave9PinnedLegacyBuildCompatibilityCount") == 4
        and counters.get("archiveExtractionCount") == 0
        and counters.get("dependencySourceLoadCount") == 0
        and counters.get("dependencySourceExecutionCount") == 0
        and counters.get("dependencySourceCompileCount") == 0
        and counters.get("networkOperationCount") == 0
        and counters.get("subprocessCount") == 0
        and counters.get("fileWriteCount") == 0
        and type(tool_bindings) is list
        and len(tool_bindings) == 9
        and type(terminal_bindings) is list
        and len(terminal_bindings) == 73
        and type(auxiliary_bindings) is list
        and len(auxiliary_bindings) == 3
        and type(authority) is dict
        and set(authority) == {
            "decisionAuthorityGranted",
            "executionAuthorityGranted",
            "acquisitionAuthorityGranted",
            "publicationAuthorityGranted",
            "networkAuthorized",
            "sourceExecutionAuthorized",
            "filesystemExtractionAuthorized",
            "subprocessAuthorized",
            "fileWriteAuthorized",
            "gitWriteAuthorized",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "passwordRequired",
            "privateKeyRequired",
            "signatureRequired",
            "tokenRequired",
            "userActionRequired",
            "osSyscallSandboxProvided",
        }
        and authority.get("osSyscallSandboxProvided") is False
        and all(value is False for value in authority.values()),
        "E_V10_VERIFICATION",
    )
    wave_rows = [
        {
            **dict(row),
            "tupleOrder": order,
        }
        for order, row in enumerate(frontier, 1)
    ]
    return wave_rows, [dict(row) for row in source_bindings]


def request_set(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    require(
        len(rows) == EXPECTED_FRONTIER_COUNT
        and [
            row.get("tupleOrder")
            for row in rows
            if type(row) is dict
        ]
        == list(range(1, EXPECTED_FRONTIER_COUNT + 1))
        and len(
            {
                (row.get("module"), row.get("version"))
                for row in rows
                if type(row) is dict
            }
        )
        == EXPECTED_FRONTIER_COUNT,
        "E_REQUEST_SET",
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        order = row["tupleOrder"]
        module = row["module"]
        version = row["version"]
        selected = row["selectedByGraphAlgorithm"]
        require(
            type(module) is str
            and type(version) is str
            and type(selected) is bool
            and module.isascii()
            and version.isascii()
            and module == module.lower()
            and version == version.lower()
            and all(
                character in
                "abcdefghijklmnopqrstuvwxyz0123456789./-_"
                for character in module
            )
            and all(
                character in
                "abcdefghijklmnopqrstuvwxyz0123456789.+-"
                for character in version
            )
            and all(
                component not in {"", ".", ".."}
                for component in module.split("/")
            )
            and version.startswith("v"),
            "E_REQUEST_SET",
        )
        tuple_digest = sha256_bytes(
            f"{module}\n{version}\n".encode("utf-8")
        )
        for kind, expected_h1, maximum in (
            ("mod", row["goModH1Values"][0], 1_048_576),
            ("zip", row["moduleZipH1Values"][0], 16_777_216),
        ):
            result.append(
                {
                    "requestOrdinal": len(result) + 1,
                    "tupleOrder": order,
                    "module": module,
                    "version": version,
                    "selectedByGraphAlgorithm": selected,
                    "resourceKind": kind,
                    "method": "GET",
                    "host": "proxy.golang.org",
                    "url": (
                        f"https://proxy.golang.org/{module}/"
                        f"@v/{version}.{kind}"
                    ),
                    "expectedH1": expected_h1,
                    "maximumResponseBytes": maximum,
                    "acceptedFileName": (
                        f"{order:03d}-{tuple_digest[:20]}.{kind}"
                    ),
                    "authenticationRequired": False,
                    "networkAuthorized": False,
                    "acquisitionAuthorized": False,
                }
            )
    require(
        len(result) == EXPECTED_FRONTIER_COUNT * 2
        and [row["requestOrdinal"] for row in result]
        == list(range(1, EXPECTED_FRONTIER_COUNT * 2 + 1))
        and [
            row["resourceKind"]
            for row in result
        ]
        == ["mod", "zip"] * EXPECTED_FRONTIER_COUNT,
        "E_REQUEST_SET",
    )
    return result


def expected_tool_bindings(
    package_raw: Mapping[str, bytes],
) -> list[dict[str, Any]]:
    require(
        sha256_bytes(
            normalized_self_bytes(package_raw[SELF_PATH])
        )
        == SELF_NORMALIZED_SHA256
        and sha256_bytes(package_raw[TESTS_PATH])
        == TESTS_RAW_SHA256
        and sha256_bytes(package_raw[V10_CHECKER_PATH])
        == V10_CHECKER_RAW_SHA256
        and sha256_bytes(
            package_raw[V10_TESTS_PATH]
        )
        == V10_TESTS_RAW_SHA256,
        "E_TOOL_IDENTITY",
    )
    return [
        {
            "role": "current_wave12_decision_checker",
            "path": SELF_PATH,
            "normalizedSha256": SELF_NORMALIZED_SHA256,
        },
        {
            "role": "current_wave12_decision_tests",
            "path": TESTS_PATH,
            "rawSha256": TESTS_RAW_SHA256,
        },
        {
            "role": "immutable_combined_v10_checker",
            "path": V10_CHECKER_PATH,
            "rawSha256": V10_CHECKER_RAW_SHA256,
            "normalizedSha256": V10_CHECKER_NORMALIZED_SHA256,
        },
        {
            "role": "immutable_combined_v10_tests",
            "path": V10_TESTS_PATH,
            "rawSha256": V10_TESTS_RAW_SHA256,
        },
    ]


def expected_payload(
    *,
    package_raw: Mapping[str, bytes],
    source_bindings: Sequence[Mapping[str, Any]],
    scan: Mapping[str, Any],
) -> dict[str, Any]:
    rows = scan["tuples"]
    require_closed_identity(scan)
    requests = request_set(rows)
    identity_rows = [
        {
            "tupleOrder": row["tupleOrder"],
            "module": row["module"],
            "version": row["version"],
            "selectedByGraphAlgorithm":
                row["selectedByGraphAlgorithm"],
            "goModH1": row["goModH1Values"][0],
            "moduleZipH1": row["moduleZipH1Values"][0],
            "parentDeclarationCount": row["declarationCount"],
            "moduleZipH1WitnessCount":
                row["moduleZipH1WitnessCount"],
            "goModH1WitnessCount":
                row["goModH1WitnessCount"],
            "parentDeclarationComplete":
                row["declarationComplete"],
            "identityPairComplete":
                row["identityPairComplete"],
            "identityConflict": (
                row["goModH1Conflict"]
                or row["moduleZipH1Conflict"]
            ),
            "acquisitionReady": row["identityPairComplete"],
            "acquisitionAuthorized": False,
        }
        for row in rows
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave12"
        ),
        "schemaVersion": "1.0",
        "checkerId": CHECKER_ID,
        "decisionId": DECISION_ID,
        "date": "2026-07-27",
        "status": (
            "wave12_exact_4_frontier_identity_classified_"
            "4_complete_0_blocked_acquisition_ready_not_authorized"
        ),
        "result": (
            f"exact_4_version_vertices_"
            f"{EXPECTED_GRAPH_SELECTED_TUPLE_COUNT}_selected_"
            f"{EXPECTED_FRONTIER_COUNT - EXPECTED_GRAPH_SELECTED_TUPLE_COUNT}"
            "_nonselected_4_complete_h1_pairs_"
            "acquisition_ready_not_authorized"
        ),
        "verificationOnly": True,
        "recordModeExposed": False,
        "predecessorBindings": {
            "combinedFixedPointV10": {
                "checkerPath": V10_CHECKER_PATH,
                "checkerRawSha256": V10_CHECKER_RAW_SHA256,
                "checkerNormalizedSha256":
                    V10_CHECKER_NORMALIZED_SHA256,
                "testsPath": V10_TESTS_PATH,
                "testsRawSha256": V10_TESTS_RAW_SHA256,
                "wave11NamespaceAnchor": {
                    "path": NAMESPACE_ANCHOR_PATH,
                    "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
                },
                "contentSha256": V10_CANDIDATE_CONTENT_SHA256,
                "combinedInputSetSha256": V10_INPUT_SET_SHA256,
                "sourceBindingsSha256":
                    V10_SOURCE_BINDINGS_SHA256,
                "graphSha256": V10_GRAPH_SHA256,
                "frontierSha256": V10_FRONTIER_SHA256,
                "fixedPointReached": False,
                "frontierTupleCount": EXPECTED_FRONTIER_COUNT,
                "totalFullSourceReconstructionCount": 18,
                "totalGraphArchiveOpenCount": 1984,
                "providerFacadeVerificationScope": (
                    "trusted_pinned_normal_reconstruction_path"
                ),
                "trustedPinnedNormalPathFileWriteCount": 0,
                "osSyscallSandboxProvided": False,
                "v9TestsBindingScope":
                    "historical_metadata_only_not_live_held",
                "v9TestsLiveHeld": False,
                "wave9LegacyBuildCompatibilityPolicy": {
                    "configuredProfileInclusionEquivalent": True,
                    "directReconstructionApplicationCount": 4,
                    "expectedExpression":
                        "((go1.8 && !go1.9)) && ((!windows))",
                    "fallbackErrorCode": "E_BUILD_CONSTRAINT",
                    "fallbackErrorPhase": "source_inventory",
                    "go111TrailingWordOrSemanticsChecked": True,
                    "normalizedSourceSha256":
                        "a46760412870548bd5bf6cfb011129769545623276e3b0385f85deb3206045f2",
                    "originalLineOccurrenceCount": 1,
                    "originalProviderParserTriedFirst": True,
                    "rawSourceSha256":
                        "042948d42899becd3c158c680d9c491ca9a57629cc893edea31ef2aae2666443",
                    "sourceBytesModified": False,
                },
                "wave9PinnedLegacyBuildCompatibilityCount": 4,
                "retainedSnapshotBoundary": {
                    "historicalExact36FrozenSnapshotDescriptorSetBound": True,
                    "liveTerminalControlMetadataVerifiedAtCombinedV10Barrier":
                        True,
                    "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV10Barrier":
                        True,
                    "finalNamespaceReverifiedAfterCombinedV10Reconstruction":
                        True,
                    "retainedFdPreManifestBarrierCount": 3,
                    "completionAppliesToRetainedSnapshot": True,
                    "currentPathIdentityGuaranteedThroughManifestPublication":
                        False,
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                        False,
                },
            }
        },
        "heldSourceInputSet": {
            "sourceBindingCount": len(source_bindings),
            "sourceBindingsSha256": V10_SOURCE_BINDINGS_SHA256,
            "archiveCount": scan["archiveCount"],
            "externalModCount": scan["externalModCount"],
            "embeddedRootGoModCount":
                scan["embeddedRootGoModCount"],
            "goSumEntryCount": scan["goSumEntryCount"],
            "allInputsReadTwiceBeforeUse": True,
            "allInputsHeldThroughFinalBarrier": True,
        },
        "identityResolution": {
            "tupleCount": len(rows),
            "graphSelectedTupleCount": sum(
                row["selectedByGraphAlgorithm"] for row in rows
            ),
            "versionSpecificNonSelectedTupleCount": sum(
                not row["selectedByGraphAlgorithm"] for row in rows
            ),
            "parentDeclarationCount": sum(
                row["declarationCount"] for row in rows
            ),
            "moduleZipH1WitnessCount": sum(
                row["moduleZipH1WitnessCount"] for row in rows
            ),
            "goModH1WitnessCount": sum(
                row["goModH1WitnessCount"] for row in rows
            ),
            "completeIdentityPairCount": sum(
                row["identityPairComplete"] for row in rows
            ),
            "blockedTupleCount": sum(
                not row["identityPairComplete"] for row in rows
            ),
            "conflictingIdentityCount": sum(
                row["goModH1Conflict"]
                or row["moduleZipH1Conflict"]
                for row in rows
            ),
            "compactIdentityCanonicalization":
                "utf8_unescaped_sorted_keys_compact_no_trailing_lf",
            "compactIdentitySha256": scan["compactIdentitySha256"],
            "fullWitnessCanonicalization":
                "utf8_unescaped_sorted_keys_compact_no_trailing_lf",
            "fullWitnessSha256": scan["fullWitnessSha256"],
            "fullWitnessMaterializedInDecision": False,
            "fullWitnessReproducibleByPinnedChecker": True,
            "tuples": identity_rows,
        },
        "sourceAcquisitionPreparation": {
            "acquisitionReady": True,
            "acquisitionAuthorizedByThisDecision": False,
            "separateOneUseExecutionPermitRequired": True,
            "requestCount": len(requests),
            "requestOrder": "tuple_order_ascending_mod_then_zip",
            "requestSet": requests,
            "requestSetCanonicalSha256":
                sha256_bytes(digest_json_bytes(requests)),
            "proxyHost": "proxy.golang.org",
            "modulePathEncoding":
                "current_wave12_lowercase_ascii_direct_proxy_path",
            "claimPath": WAVE12_CLAIM_PATH,
            "stagingDirectoryPrefix": WAVE12_STAGING_PREFIX,
            "acceptedDirectoryPath": WAVE12_ACCEPTED_PATH,
            "namespaceCleanAtDecisionCheck": True,
            "namespaceCheckIsPointInTimeOnly": True,
            "namespaceReservationClaimed": False,
            "oneUseNoOverwriteRequired": True,
            "atomicNoReplacePromotionRequired": True,
            "independentPostConsumptionReadbackRequired": True,
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": READER_RAW_SHA256,
        },
        "toolBindings": expected_tool_bindings(package_raw),
        "operationCounters": {
            "combinedV10CandidateInvocationCount": 1,
            "predecessorFullSourceReconstructionCount": 16,
            "directV10FullSourceReconstructionCount": 2,
            "totalFullSourceReconstructionCount": 18,
            "predecessorGraphArchiveOpenCount": 1666,
            "currentV10GraphArchiveOpenCount": 318,
            "totalV10GraphArchiveOpenCount": 1984,
            "identityWitnessScanCount": 2,
            "identityWitnessArchiveOpenCount": 318,
            "overallDecisionExecutionArchiveOpenCount": 2302,
            "descriptorIdentityBarrierCount": 7,
            "namespaceSnapshotCount": 2,
            "networkOperationCount": 0,
            "productRuntimeNetworkOperationCount": 0,
            "socketOperationCount": 0,
            "subprocessCount": 0,
            "authenticationOperationCount": 0,
            "dependencySourceLoadCount": 0,
            "dependencySourceExecutionCount": 0,
            "dependencySourceCompileCount": 0,
            "archiveExtractionCount": 0,
            "fileWriteCount": 0,
        },
        "closure": {
            "wave12IdentityResolved": True,
            "wave12AcquisitionReady": True,
            "wave12AcquisitionComplete": False,
            "dependencyFixedPointReached": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "releaseReady": False,
        },
        "authority": dict(EXPECTED_DECISION_AUTHORITY),
        "nonClaims": list(EXPECTED_NON_CLAIMS),
        "nextAction": (
            "prepare_separate_one_use_8_resource_wave12_source_"
            "acquisition_permit_checker_runner_and_tests"
        ),
    }


def validate_semantic_decision(
    document: Mapping[str, Any],
    package_raw: Mapping[str, bytes],
) -> Mapping[str, Any]:
    top_keys = {
        "authority",
        "checkerId",
        "closure",
        "contentBinding",
        "date",
        "decisionId",
        "documentType",
        "heldSourceInputSet",
        "identityResolution",
        "nextAction",
        "nonClaims",
        "operationCounters",
        "predecessorBindings",
        "readerDocumentBinding",
        "recordModeExposed",
        "result",
        "schemaVersion",
        "sourceAcquisitionPreparation",
        "status",
        "toolBindings",
        "verificationOnly",
    }
    require(
        type(document) is dict
        and set(document) == top_keys,
        "E_DECISION_SCHEMA",
    )
    binding = document.get("contentBinding")
    without = dict(document)
    without.pop("contentBinding", None)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "decision_without_contentBinding",
            "sha256":
                sha256_bytes(canonical_json_bytes(without)),
        },
        "E_DECISION_CONTENT",
    )
    require(
        document.get("documentType")
        == (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave12"
        )
        and document.get("schemaVersion") == "1.0"
        and document.get("checkerId") == CHECKER_ID
        and document.get("decisionId") == DECISION_ID
        and document.get("date") == "2026-07-27"
        and document.get("status")
        == (
            "wave12_exact_4_frontier_identity_classified_"
            "4_complete_0_blocked_acquisition_ready_not_authorized"
        )
        and document.get("result")
        == (
            f"exact_4_version_vertices_"
            f"{EXPECTED_GRAPH_SELECTED_TUPLE_COUNT}_selected_"
            f"{EXPECTED_FRONTIER_COUNT - EXPECTED_GRAPH_SELECTED_TUPLE_COUNT}"
            "_nonselected_4_complete_h1_pairs_"
            "acquisition_ready_not_authorized"
        )
        and document.get("verificationOnly") is True
        and document.get("recordModeExposed") is False,
        "E_DECISION_SCHEMA",
    )

    predecessors = document.get("predecessorBindings")
    combined = (
        predecessors.get("combinedFixedPointV10")
        if type(predecessors) is dict
        else None
    )
    retained = (
        combined.get("retainedSnapshotBoundary")
        if type(combined) is dict
        else None
    )
    combined_keys = {
        "checkerPath",
        "checkerRawSha256",
        "checkerNormalizedSha256",
        "testsPath",
        "testsRawSha256",
        "wave11NamespaceAnchor",
        "contentSha256",
        "combinedInputSetSha256",
        "sourceBindingsSha256",
        "graphSha256",
        "frontierSha256",
        "fixedPointReached",
        "frontierTupleCount",
        "totalFullSourceReconstructionCount",
        "totalGraphArchiveOpenCount",
        "providerFacadeVerificationScope",
        "trustedPinnedNormalPathFileWriteCount",
        "osSyscallSandboxProvided",
        "v9TestsBindingScope",
        "v9TestsLiveHeld",
        "wave9LegacyBuildCompatibilityPolicy",
        "wave9PinnedLegacyBuildCompatibilityCount",
        "retainedSnapshotBoundary",
    }
    retained_keys = {
        "historicalExact36FrozenSnapshotDescriptorSetBound",
        "liveTerminalControlMetadataVerifiedAtCombinedV10Barrier",
        "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV10Barrier",
        "finalNamespaceReverifiedAfterCombinedV10Reconstruction",
        "retainedFdPreManifestBarrierCount",
        "completionAppliesToRetainedSnapshot",
        "currentPathIdentityGuaranteedThroughManifestPublication",
        "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
    }
    require(
        exact_keys(predecessors, {"combinedFixedPointV10"})
        and exact_keys(combined, combined_keys)
        and exact_keys(retained, retained_keys)
        and combined
        == {
            "checkerPath": V10_CHECKER_PATH,
            "checkerRawSha256": V10_CHECKER_RAW_SHA256,
            "checkerNormalizedSha256":
                V10_CHECKER_NORMALIZED_SHA256,
            "testsPath": V10_TESTS_PATH,
            "testsRawSha256": V10_TESTS_RAW_SHA256,
            "wave11NamespaceAnchor": {
                "path": NAMESPACE_ANCHOR_PATH,
                "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
            },
            "contentSha256": V10_CANDIDATE_CONTENT_SHA256,
            "combinedInputSetSha256": V10_INPUT_SET_SHA256,
            "sourceBindingsSha256": V10_SOURCE_BINDINGS_SHA256,
            "graphSha256": V10_GRAPH_SHA256,
            "frontierSha256": V10_FRONTIER_SHA256,
            "fixedPointReached": False,
            "frontierTupleCount": EXPECTED_FRONTIER_COUNT,
            "totalFullSourceReconstructionCount": 18,
            "totalGraphArchiveOpenCount": 1984,
            "providerFacadeVerificationScope":
                "trusted_pinned_normal_reconstruction_path",
            "trustedPinnedNormalPathFileWriteCount": 0,
            "osSyscallSandboxProvided": False,
            "v9TestsBindingScope":
                "historical_metadata_only_not_live_held",
            "v9TestsLiveHeld": False,
            "wave9LegacyBuildCompatibilityPolicy": {
                "configuredProfileInclusionEquivalent": True,
                "directReconstructionApplicationCount": 4,
                "expectedExpression":
                    "((go1.8 && !go1.9)) && ((!windows))",
                "fallbackErrorCode": "E_BUILD_CONSTRAINT",
                "fallbackErrorPhase": "source_inventory",
                "go111TrailingWordOrSemanticsChecked": True,
                "normalizedSourceSha256":
                    "a46760412870548bd5bf6cfb011129769545623276e3b0385f85deb3206045f2",
                "originalLineOccurrenceCount": 1,
                "originalProviderParserTriedFirst": True,
                "rawSourceSha256":
                    "042948d42899becd3c158c680d9c491ca9a57629cc893edea31ef2aae2666443",
                "sourceBytesModified": False,
            },
            "wave9PinnedLegacyBuildCompatibilityCount": 4,
            "retainedSnapshotBoundary": {
                "historicalExact36FrozenSnapshotDescriptorSetBound": True,
                "liveTerminalControlMetadataVerifiedAtCombinedV10Barrier":
                    True,
                "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV10Barrier":
                    True,
                "finalNamespaceReverifiedAfterCombinedV10Reconstruction":
                    True,
                "retainedFdPreManifestBarrierCount": 3,
                "completionAppliesToRetainedSnapshot": True,
                "currentPathIdentityGuaranteedThroughManifestPublication":
                    False,
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                    False,
            },
        }
        and combined["fixedPointReached"] is False
        and combined["osSyscallSandboxProvided"] is False
        and combined["v9TestsLiveHeld"] is False
        and all(
            type(combined[key]) is int
            for key in (
                "frontierTupleCount",
                "totalFullSourceReconstructionCount",
                "totalGraphArchiveOpenCount",
                "trustedPinnedNormalPathFileWriteCount",
            )
        )
        and retained["completionAppliesToRetainedSnapshot"] is True
        and retained[
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ]
        is False
        and retained[
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ]
        is False,
        "E_DECISION_LINEAGE",
    )

    held = document.get("heldSourceInputSet")
    held_count_keys = (
        "sourceBindingCount",
        "archiveCount",
        "externalModCount",
        "embeddedRootGoModCount",
        "goSumEntryCount",
    )
    require(
        exact_keys(
            held,
            {
                *held_count_keys,
                "sourceBindingsSha256",
                "allInputsReadTwiceBeforeUse",
                "allInputsHeldThroughFinalBarrier",
            },
        )
        and all(type(held[key]) is int for key in held_count_keys)
        and held["sourceBindingCount"] == 317
        and held["sourceBindingsSha256"]
        == V10_SOURCE_BINDINGS_SHA256
        and held["archiveCount"] == 159
        and held["externalModCount"] == 158
        and held["embeddedRootGoModCount"] == 1
        and held["goSumEntryCount"] == EXPECTED_GO_SUM_ENTRY_COUNT
        and held["allInputsReadTwiceBeforeUse"] is True
        and held["allInputsHeldThroughFinalBarrier"] is True,
        "E_DECISION_LINEAGE",
    )

    identity = document.get("identityResolution")
    rows = (
        identity.get("tuples")
        if type(identity) is dict
        else None
    )
    identity_count_keys = (
        "tupleCount",
        "graphSelectedTupleCount",
        "versionSpecificNonSelectedTupleCount",
        "parentDeclarationCount",
        "moduleZipH1WitnessCount",
        "goModH1WitnessCount",
        "completeIdentityPairCount",
        "blockedTupleCount",
        "conflictingIdentityCount",
    )
    require(
        exact_keys(
            identity,
            {
                *identity_count_keys,
                "compactIdentityCanonicalization",
                "compactIdentitySha256",
                "fullWitnessCanonicalization",
                "fullWitnessSha256",
                "fullWitnessMaterializedInDecision",
                "fullWitnessReproducibleByPinnedChecker",
                "tuples",
            },
        )
        and all(
            type(identity[key]) is int
            for key in identity_count_keys
        )
        and identity["tupleCount"] == EXPECTED_FRONTIER_COUNT
        and identity["graphSelectedTupleCount"]
        == EXPECTED_GRAPH_SELECTED_TUPLE_COUNT
        and identity["versionSpecificNonSelectedTupleCount"]
        == (
            EXPECTED_FRONTIER_COUNT
            - EXPECTED_GRAPH_SELECTED_TUPLE_COUNT
        )
        and identity["parentDeclarationCount"]
        == EXPECTED_PARENT_DECLARATION_COUNT
        and identity["moduleZipH1WitnessCount"]
        == EXPECTED_MODULE_ZIP_H1_WITNESS_COUNT
        and identity["goModH1WitnessCount"]
        == EXPECTED_GO_MOD_H1_WITNESS_COUNT
        and identity["completeIdentityPairCount"]
        == EXPECTED_FRONTIER_COUNT
        and identity["blockedTupleCount"] == 0
        and identity["conflictingIdentityCount"] == 0
        and identity["compactIdentityCanonicalization"]
        == "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
        and identity["compactIdentitySha256"]
        == COMPACT_IDENTITY_SHA256
        and identity["fullWitnessCanonicalization"]
        == "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
        and identity["fullWitnessSha256"] == FULL_WITNESS_SHA256
        and identity["fullWitnessMaterializedInDecision"] is False
        and identity["fullWitnessReproducibleByPinnedChecker"] is True
        and type(rows) is list
        and len(rows) == EXPECTED_FRONTIER_COUNT,
        "E_DECISION_IDENTITY",
    )
    identity_row_keys = {
        "tupleOrder",
        "module",
        "version",
        "selectedByGraphAlgorithm",
        "goModH1",
        "moduleZipH1",
        "parentDeclarationCount",
        "moduleZipH1WitnessCount",
        "goModH1WitnessCount",
        "parentDeclarationComplete",
        "identityPairComplete",
        "identityConflict",
        "acquisitionReady",
        "acquisitionAuthorized",
    }
    for order, (row, expected) in enumerate(
        zip(rows, EXPECTED_IDENTITY),
        1,
    ):
        (
            module,
            version,
            selected,
            mod_h1,
            zip_h1,
            declaration_count,
            mod_count,
            zip_count,
        ) = expected
        require(
            exact_keys(row, identity_row_keys)
            and type(row["tupleOrder"]) is int
            and row["tupleOrder"] == order
            and row["module"] == module
            and row["version"] == version
            and row["selectedByGraphAlgorithm"] is selected
            and row["goModH1"] == mod_h1
            and row["moduleZipH1"] == zip_h1
            and type(row["parentDeclarationCount"]) is int
            and row["parentDeclarationCount"] == declaration_count
            and type(row["moduleZipH1WitnessCount"]) is int
            and row["moduleZipH1WitnessCount"] == zip_count
            and type(row["goModH1WitnessCount"]) is int
            and row["goModH1WitnessCount"] == mod_count
            and row["parentDeclarationComplete"] is True
            and row["identityPairComplete"] is True
            and row["identityConflict"] is False
            and row["acquisitionReady"] is True
            and row["acquisitionAuthorized"] is False,
            "E_DECISION_IDENTITY",
        )

    preparation = document.get("sourceAcquisitionPreparation")
    requests = (
        preparation.get("requestSet")
        if type(preparation) is dict
        else None
    )
    expected_request_rows = [
        {
            "tupleOrder": order,
            "module": expected[0],
            "version": expected[1],
            "selectedByGraphAlgorithm": expected[2],
            "goModH1Values": [expected[3]],
            "moduleZipH1Values": [expected[4]],
        }
        for order, expected in enumerate(EXPECTED_IDENTITY, 1)
    ]
    expected_requests = request_set(expected_request_rows)
    request_keys = {
        "requestOrdinal",
        "tupleOrder",
        "module",
        "version",
        "selectedByGraphAlgorithm",
        "resourceKind",
        "method",
        "host",
        "url",
        "expectedH1",
        "maximumResponseBytes",
        "acceptedFileName",
        "authenticationRequired",
        "networkAuthorized",
        "acquisitionAuthorized",
    }
    require(
        exact_keys(
            preparation,
            {
                "acquisitionReady",
                "acquisitionAuthorizedByThisDecision",
                "separateOneUseExecutionPermitRequired",
                "requestCount",
                "requestOrder",
                "requestSet",
                "requestSetCanonicalSha256",
                "proxyHost",
                "modulePathEncoding",
                "claimPath",
                "stagingDirectoryPrefix",
                "acceptedDirectoryPath",
                "namespaceCleanAtDecisionCheck",
                "namespaceCheckIsPointInTimeOnly",
                "namespaceReservationClaimed",
                "oneUseNoOverwriteRequired",
                "atomicNoReplacePromotionRequired",
                "independentPostConsumptionReadbackRequired",
            },
        )
        and preparation["acquisitionReady"] is True
        and preparation["acquisitionAuthorizedByThisDecision"] is False
        and preparation["separateOneUseExecutionPermitRequired"] is True
        and type(preparation["requestCount"]) is int
        and preparation["requestCount"] == EXPECTED_FRONTIER_COUNT * 2
        and preparation["requestOrder"]
        == "tuple_order_ascending_mod_then_zip"
        and type(requests) is list
        and len(requests) == EXPECTED_FRONTIER_COUNT * 2
        and all(
            exact_keys(row, request_keys)
            and type(row["requestOrdinal"]) is int
            and type(row["tupleOrder"]) is int
            and type(row["maximumResponseBytes"]) is int
            and type(row["selectedByGraphAlgorithm"]) is bool
            and row["authenticationRequired"] is False
            and row["networkAuthorized"] is False
            and row["acquisitionAuthorized"] is False
            for row in requests
        )
        and requests == expected_requests
        and preparation["requestSetCanonicalSha256"]
        == sha256_bytes(digest_json_bytes(expected_requests))
        and preparation["proxyHost"] == "proxy.golang.org"
        and preparation["modulePathEncoding"]
        == "current_wave12_lowercase_ascii_direct_proxy_path"
        and preparation["claimPath"] == WAVE12_CLAIM_PATH
        and preparation["stagingDirectoryPrefix"]
        == WAVE12_STAGING_PREFIX
        and preparation["acceptedDirectoryPath"]
        == WAVE12_ACCEPTED_PATH
        and preparation["namespaceCleanAtDecisionCheck"] is True
        and preparation["namespaceCheckIsPointInTimeOnly"] is True
        and preparation["namespaceReservationClaimed"] is False
        and preparation["oneUseNoOverwriteRequired"] is True
        and preparation["atomicNoReplacePromotionRequired"] is True
        and preparation[
            "independentPostConsumptionReadbackRequired"
        ]
        is True,
        "E_DECISION_REQUEST",
    )

    expected_counters = {
        "combinedV10CandidateInvocationCount": 1,
        "predecessorFullSourceReconstructionCount": 16,
        "directV10FullSourceReconstructionCount": 2,
        "totalFullSourceReconstructionCount": 18,
        "predecessorGraphArchiveOpenCount": 1666,
        "currentV10GraphArchiveOpenCount": 318,
        "totalV10GraphArchiveOpenCount": 1984,
        "identityWitnessScanCount": 2,
        "identityWitnessArchiveOpenCount": 318,
        "overallDecisionExecutionArchiveOpenCount": 2302,
        "descriptorIdentityBarrierCount": 7,
        "namespaceSnapshotCount": 2,
        "networkOperationCount": 0,
        "productRuntimeNetworkOperationCount": 0,
        "socketOperationCount": 0,
        "subprocessCount": 0,
        "authenticationOperationCount": 0,
        "dependencySourceLoadCount": 0,
        "dependencySourceExecutionCount": 0,
        "dependencySourceCompileCount": 0,
        "archiveExtractionCount": 0,
        "fileWriteCount": 0,
    }
    counters = document.get("operationCounters")
    require(
        exact_keys(counters, expected_counters)
        and all(
            type(counters[key]) is int
            and counters[key] == expected_counters[key]
            for key in expected_counters
        ),
        "E_DECISION_COUNTERS",
    )
    expected_closure = {
        "wave12IdentityResolved": True,
        "wave12AcquisitionReady": True,
        "wave12AcquisitionComplete": False,
        "dependencyFixedPointReached": False,
        "dependencyClosureComplete": False,
        "semanticClosureComplete": False,
        "candidateSelected": False,
        "librarySelected": False,
        "rungThreeComplete": False,
        "releaseReady": False,
    }
    closure = document.get("closure")
    require(
        exact_keys(closure, expected_closure)
        and all(
            closure[key] is expected_closure[key]
            for key in expected_closure
        ),
        "E_DECISION_CLOSURE",
    )
    authority = document.get("authority")
    require(
        exact_keys(authority, EXPECTED_DECISION_AUTHORITY)
        and all(
            authority[key] is False
            for key in EXPECTED_DECISION_AUTHORITY
        ),
        "E_DECISION_AUTHORITY",
    )
    require(
        document.get("readerDocumentBinding")
        == {
            "path": READER_PATH,
            "rawSha256": READER_RAW_SHA256,
        }
        and document.get("toolBindings")
        == expected_tool_bindings(package_raw)
        and document.get("nonClaims")
        == list(EXPECTED_NON_CLAIMS),
        "E_DECISION_BINDINGS",
    )
    require(
        document.get("nextAction")
        == (
            "prepare_separate_one_use_8_resource_wave12_source_"
            "acquisition_permit_checker_runner_and_tests"
        ),
        "E_DECISION_CLOSURE",
    )
    return document


def validate_materialized_decision(
    raw: bytes,
    expected: Mapping[str, Any],
    package_raw: Mapping[str, bytes],
) -> Mapping[str, Any]:
    parsed = strict_json(raw, "E_DECISION_JSON")
    require(
        raw == canonical_json_bytes(expected)
        and parsed == expected,
        "E_DECISION_BYTES",
    )
    return validate_semantic_decision(parsed, package_raw)


def validate_materialized_decision_path(
    root: Path,
    expected: Mapping[str, Any],
    package_raw: Mapping[str, bytes],
    held: Sequence[Any] = (),
) -> Mapping[str, Any]:
    expected_raw = canonical_json_bytes(expected)
    with BootstrapPinnedCodeFile(
        root,
        DECISION_PATH,
        sha256_bytes(expected_raw),
        maximum_bytes=MAXIMUM_DECISION_BYTES,
    ) as decision_held:
        active_held = [*held, decision_held]
        identity_barrier(root, active_held)
        validated = validate_materialized_decision(
            decision_held.raw,
            expected,
            package_raw,
        )
        identity_barrier(root, active_held)
        return validated


def evaluate(
    root: Path = ROOT,
    *,
    verify_disk: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    require_isolated_interpreter()
    with ExitStack() as stack:
        self_held = stack.enter_context(
            BootstrapPinnedCodeFile(
                root,
                SELF_PATH,
                SELF_NORMALIZED_SHA256,
                normalized_self_bytes,
            )
        )
        v10_held = stack.enter_context(
            BootstrapPinnedCodeFile(
                root,
                V10_CHECKER_PATH,
                V10_CHECKER_RAW_SHA256,
            )
        )
        v10 = load_v10_checker(v10_held)
        v10_tests_held = stack.enter_context(
            v10.PinnedCodeFile(
                root,
                V10_TESTS_PATH,
                V10_TESTS_RAW_SHA256,
            )
        )
        tests_held = stack.enter_context(
            v10.PinnedCodeFile(
                root,
                TESTS_PATH,
                TESTS_RAW_SHA256,
            )
        )
        reader_held = stack.enter_context(
            v10.PinnedCodeFile(
                root,
                READER_PATH,
                READER_RAW_SHA256,
            )
        )
        namespace_anchor_held = stack.enter_context(
            BootstrapPinnedCodeFile(
                root,
                NAMESPACE_ANCHOR_PATH,
                NAMESPACE_ANCHOR_RAW_SHA256,
            )
        )
        package_raw = {
            SELF_PATH: self_held.raw,
            TESTS_PATH: tests_held.raw,
            READER_PATH: reader_held.raw,
            V10_CHECKER_PATH: v10_held.raw,
            V10_TESTS_PATH: v10_tests_held.raw,
        }
        held: list[Any] = [
            self_held,
            v10_held,
            v10_tests_held,
            tests_held,
            reader_held,
            namespace_anchor_held,
        ]

        validate_wave12_namespace_absent(
            namespace_anchor_held.parent_fd,
            reader_held.parent_fd,
            self_held.parent_fd,
        )
        identity_barrier(root, held)
        candidate = v10.generate_candidate(root)
        identity_barrier(root, held)
        wave_rows, source_bindings = validate_v10_candidate(candidate)
        v10 = v10.harden_checker_module(v10)

        v9_held = stack.enter_context(
            v10.PinnedCodeFile(
                root,
                v10.V9_CHECKER_PATH,
                v10.V9_CHECKER_RAW_SHA256,
            )
        )
        v9 = v10.load_v9_checker(v9_held)
        v8_held = stack.enter_context(
            v9.PinnedCodeFile(
                root,
                v9.V8_CHECKER_PATH,
                v9.V8_CHECKER_RAW_SHA256,
            )
        )
        v8 = v9.load_v8_checker(v8_held)
        v7_held = stack.enter_context(
            v8.PinnedCodeFile(
                root,
                v8.V7_CHECKER_PATH,
                v8.V7_CHECKER_RAW_SHA256,
            )
        )
        v7 = v8.load_v7_checker(v7_held)
        v6_held = stack.enter_context(
            v7.PinnedCodeFile(
                root,
                v7.V6_CHECKER_PATH,
                v7.V6_CHECKER_RAW_SHA256,
            )
        )
        v6 = v7.load_v6_checker(v6_held)

        v5_held = stack.enter_context(
            v6.PinnedCodeFile(
                root,
                v6.V5_CHECKER_PATH,
                v6.V5_CHECKER_RAW_SHA256,
            )
        )
        v5 = v6.load_v5_checker(v5_held)
        v4_held = stack.enter_context(
            v5.PinnedCodeFile(
                root,
                v5.V4_CHECKER_PATH,
                v5.V4_CHECKER_RAW_SHA256,
            )
        )
        v4 = v5.load_v4_checker(v4_held)
        v1_held = stack.enter_context(
            v4.PinnedCodeFile(
                root,
                v4.V1_CHECKER_PATH,
                v4.V1_CHECKER_RAW_SHA256,
            )
        )
        v1 = v4.load_v1_checker(v1_held)
        provider_held = stack.enter_context(
            v1.PinnedRunnerFile(root)
        )
        runner = v1.load_pinned_runner(provider_held)
        require(
            type(runner) is v10.ReadOnlyProviderFacade
            and v9.PinnedCodeFile is v10.PinnedCodeFile
            and v8.PinnedCodeFile is v10.PinnedCodeFile
            and v7.PinnedCodeFile is v10.PinnedCodeFile
            and v6.PinnedCodeFile is v10.PinnedCodeFile
            and v5.PinnedCodeFile is v10.PinnedCodeFile
            and v4.PinnedCodeFile is v10.PinnedCodeFile
            and v1.PinnedRunnerFile is v10.SafePinnedRunnerFile,
            "E_SAFE_RUNTIME",
        )
        full_source_bindings = [
            {
                **dict(row),
                "maximumBytes": MAXIMUM_SOURCE_BYTES,
                "ownerOnly": False,
            }
            for row in source_bindings
        ]
        require(
            v1.source_projection(full_source_bindings)
            == source_bindings
            and len(full_source_bindings) == 317
            and all(
                type(row) is dict
                and set(source_bindings[index]).issubset(row)
                and type(row.get("maximumBytes")) is int
                and row["maximumBytes"] >= 1
                and type(row.get("ownerOnly")) is bool
                for index, row in enumerate(
                    sorted(
                        full_source_bindings,
                        key=lambda value: (
                            value["tupleOrder"],
                            value["kind"],
                            value["path"],
                        ),
                    )
                )
            ),
            "E_FULL_SOURCE_BINDING",
        )
        source_held = stack.enter_context(
            runner.HeldInputSet(
                root,
                full_source_bindings,
            )
        )
        held.extend(
            (
                v9_held,
                v8_held,
                v7_held,
                v6_held,
                v5_held,
                v4_held,
                v1_held,
                provider_held,
                source_held,
            )
        )
        identity_barrier(root, held)
        first_scan = scan_source_identity(
            source_bindings=source_bindings,
            source_raw=source_held.raw,
            wave_rows=wave_rows,
            runner=runner,
        )
        identity_barrier(root, held)
        second_scan = scan_source_identity(
            source_bindings=source_bindings,
            source_raw=source_held.raw,
            wave_rows=wave_rows,
            runner=runner,
        )
        require(
            digest_json_bytes(first_scan)
            == digest_json_bytes(second_scan),
            "E_REPRODUCTION",
        )
        require_closed_identity(first_scan)
        if not verify_disk:
            identity_barrier(root, held)

        expected = content_bound(
            expected_payload(
                package_raw=package_raw,
                source_bindings=source_bindings,
                scan=first_scan,
            )
        )
        validate_semantic_decision(expected, package_raw)
        if verify_disk:
            validate_materialized_decision_path(
                root,
                expected,
                package_raw,
                held,
            )
        else:
            identity_barrier(root, held)
        validate_wave12_namespace_absent(
            namespace_anchor_held.parent_fd,
            reader_held.parent_fd,
            self_held.parent_fd,
        )
        identity_barrier(root, held)

    return expected, {
        "documentType":
            "aetherlink.wave12-identity-acquisition-decision-check",
        "schemaVersion": "1.0",
        "status":
            "validated_4_of_4_acquisition_ready_not_authorized",
        "validationPassed": True,
        "tupleCount": EXPECTED_FRONTIER_COUNT,
        "parentDeclarationCount": EXPECTED_PARENT_DECLARATION_COUNT,
        "moduleZipH1WitnessCount":
            EXPECTED_MODULE_ZIP_H1_WITNESS_COUNT,
        "goModH1WitnessCount": EXPECTED_GO_MOD_H1_WITNESS_COUNT,
        "completeIdentityPairCount": EXPECTED_FRONTIER_COUNT,
        "blockedTupleCount": 0,
        "conflictingIdentityCount": 0,
        "acquisitionReady": True,
        "acquisitionAuthorized": False,
        "networkUsed": False,
        "productRuntimeNetworkUsed": False,
        "socketUsed": False,
        "fileWriteCount": 0,
        "sourceAcquired": False,
        "sourceExecutionUsed": False,
        "subprocessCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "osSyscallSandboxProvided": False,
    }


def error_document(code: str) -> dict[str, Any]:
    return {
        "documentType":
            "aetherlink.wave12-identity-acquisition-decision-error",
        "schemaVersion": "1.0",
        "status": "failed_closed",
        "failureCode": code,
        "acquisitionAuthorized": False,
        "networkUsed": False,
        "productRuntimeNetworkUsed": False,
        "socketUsed": False,
        "fileWriteCount": 0,
        "sourceAcquired": False,
        "sourceExecutionUsed": False,
        "subprocessCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "osSyscallSandboxProvided": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        parser.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        expected, summary = evaluate(
            ROOT,
            verify_disk=not args.print_expected,
        )
        sys.stdout.buffer.write(
            canonical_json_bytes(
                expected if args.print_expected else summary
            )
        )
        return 0
    except DecisionFailure as error:
        sys.stdout.buffer.write(
            canonical_json_bytes(error_document(error.code))
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_json_bytes(error_document("E_INTERNAL"))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
