#!/usr/bin/env python3
"""Validate the read-only Wave7 identity and acquisition decision.

Run only with ``python3 -I -B -S``.  The checker executes the exact pinned
combined-v5 candidate, then scans the retained 199 inputs twice using only the
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
            "Wave7 decision checker requires unoptimized "
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
    "decision-wave7-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave7-v1.md"
)
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave7_decision_v1.py"
)
SELF_NORMALIZED_SHA256 = (
    "77088e798ff3fd81033249753f475765a90efb4a874419a946ecc2a020dc007b"
)
TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave7_decision_v1.py"
)
TESTS_RAW_SHA256 = (
    "93371c63c0b9cf435aef68adeb9a7a790f25d2bf4a07b3c665af30b79913c0e0"
)
READER_RAW_SHA256 = (
    "695567c2952971bd490f00e9ce78d81fb787f70b9fca1078351c5e4fb61fb521"
)
V5_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v5.py"
V5_CHECKER_RAW_SHA256 = (
    "b63047c6867175655cf95710767dd930783dae5d99883dfb731aedeb59459e92"
)
V5_CHECKER_NORMALIZED_SHA256 = (
    "63587ee84ebe68aeb579c1bf85478e3c818ceaeaa8770e499d36b05ee41fe1aa"
)
V5_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v5.py"
V5_TESTS_RAW_SHA256 = (
    "bbf0ec5506ad7ac974bd07bf9a26e4bd993bf289abbbbe3d54e8ff74dfaf3549"
)
V5_CANDIDATE_CONTENT_SHA256 = (
    "87ee231bf81a403e35379624ac4275ecacf36fee9d0d1e1c5699ca390afb1ebd"
)
V5_INPUT_SET_SHA256 = (
    "06acb9e5395898abb1827761436b8c4b5d983d87d242eaf20622e352d0180c63"
)
V5_SOURCE_BINDINGS_SHA256 = (
    "762e231d84ae860233f0cfa717a1c1e2b8a56ec9108eaa0bacaf7a30d361817c"
)
V5_GRAPH_SHA256 = (
    "4b424c41fbc8fa09c5bc9f91a880f14309cb409785991cfb872bb2475d94e8fe"
)
V5_FRONTIER_SHA256 = (
    "1c226bfc244970e071ad2bf09d6e356cd9d42e7b542cd0cf1582fc2fdc4d9b8a"
)
COMPACT_IDENTITY_SHA256 = (
    "3e84f0d10c361a6520ce0746bfed49b3591be4f06a7508d48d4be4f14bb02b71"
)
FULL_WITNESS_SHA256 = (
    "61f3d4a57a80b3146d1a2728822203b47832c2bb99fa092d5127d746d6ca7b72"
)
DECLARATION_WITNESS_SHA256 = (
    "a527c1831540e3b8d9bdab8aff1a6d7105ca03d46693ed8b14e967b3c9f4216d"
)
GO_MOD_H1_WITNESS_SHA256 = (
    "d375c1ab1654dc31226671b7d3388f9f76093fd3a8fc367dddc3ee71abcf770f"
)
MODULE_ZIP_H1_WITNESS_SHA256 = (
    "2deccdffb0ba6b5c22a74aa271973d2a4f53d60cc98e40c86e7173a2df587385"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-wave7-identity-acquisition-decision-check-v1"
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-identity-and-"
    "acquisition-decision-wave7-v1"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
WAVE7_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-7-v1.claim"
WAVE7_STAGING_PREFIX = ".wave-7-v1-staging-"
WAVE7_ACCEPTED_PATH = f"{DEPENDENCY_ROOT}/wave-7-v1/accepted"
MAXIMUM_CODE_BYTES = 4 * 1024 * 1024
MAXIMUM_DECISION_BYTES = 8 * 1024 * 1024
MAXIMUM_SOURCE_BYTES = 256 * 1024 * 1024
MAXIMUM_GO_METADATA_BYTES = 4 * 1024 * 1024
MAXIMUM_ARCHIVE_ENTRIES = 300_000

EXPECTED_IDENTITY = [
    ("github.com/stretchr/testify", "v1.7.1",
     "h1:6Fq8oRcR53rry900zMqJjRRixrwX3KX962/h/Wwjteg=",
     "h1:5TQK59W5E3v0r2duFAb7P95B6hEeOyEnHRa8MjYSMTY=", 1, 5, 1),
    ("golang.org/x/crypto", "v0.13.0",
     "h1:y6Z2r+Rw4iayiXXAIxJIDAJ1zMW4yaTpebo8fPOliYc=",
     "h1:mvySKfSWJ+UKUii46M40LOvyWfN0s2U+46/jDd0e6Ck=", 1, 2, 1),
    ("golang.org/x/mod", "v0.29.0",
     "h1:NyhrlYXJ2H4eJiRy/WDBO6HMqZQ6q9nk4JzS3NuCK+w=",
     "h1:HV8lRxZC4l2cr3Zq1LvtOsi/ThTgWnUk/y64QSs8GwA=", 2, 2, 2),
    ("golang.org/x/net", "v0.46.0",
     "h1:Q9BGdFy1y4nkUwiLvT5qtyhAnEHgnQ/zd8PfU6nc210=",
     "h1:giFlY12I07fugqwPuWJi68oOnpfqFnJIJzaIIm2JVV4=", 2, 2, 2),
    ("golang.org/x/net", "v0.6.0",
     "h1:2Tu9+aMcznHK/AK1HMvgo6xiTLG5rD5rZLDS+rp2Bjs=",
     "h1:L4ZwwTvKW9gr0ZMS1yrHD9GZhIuVjOBBnaKH+SPQK0Q=", 1, 4, 1),
    ("golang.org/x/sync", "v0.1.0",
     "h1:RxMgew5VJxzue5/jJTE5uejpjVlOe/izrB70Jof72aM=",
     "h1:wsuoTGHzEhffawBOhz5CYhcrV4IdKZbEyZjBMuTp12o=", 1, 4, 3),
    ("golang.org/x/sync", "v0.17.0",
     "h1:9KTHXmSnoGruLpwFjVSX0lNNA75CykiMECbovNTZqGI=",
     "h1:l60nONMj9l5drqw6jlhIELNv9I0A4OFgRsG9k2oT9Ug=", 1, 1, 1),
    ("golang.org/x/sys", "v0.37.0",
     "h1:OgkHotnGiDImocRcuBABYBEXf8A9a87e/uXjp9XT3ks=",
     "h1:fdNQudmxPjkdUTPnLn5mdQv7Zwvbvpaxqs831goi9kQ=", 1, 1, 1),
    ("golang.org/x/sys", "v0.8.0",
     "h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=",
     "h1:EBmGv8NaZBZTWvrbjNoL6HVt+IVy3QDQpJs7VRIw3tU=", 1, 3, 1),
    ("golang.org/x/telemetry", "v0.0.0-20251008203120-078029d740a8",
     "h1:Pi4ztBfryZoJEkyFTI5/Ocsu2jXyDr6iSdgJiYE/uwE=",
     "h1:LvzTn0GQhWuvKH/kVRS3R3bVAsdQWI7hvfLHGgh9+lU=", 1, 1, 1),
    ("golang.org/x/term", "v0.12.0",
     "h1:owVbMEjm3cBLCHdkQu9b1opXd4ETQWc3BhuQGKgXgvU=",
     "h1:/ZfYdc3zq+q02Rv9vGqTeSItdzZTSNDmfTi0mBAuidU=", 1, 2, 1),
    ("golang.org/x/term", "v0.8.0",
     "h1:xPskH00ivmX89bAKVGSKKtLOWNx2+17Eiy94tnKShWo=",
     "h1:n5xxQn2i3PC0yLAbjTpNT85q/Kgzcr2gIoX9OrJUols=", 1, 3, 1),
    ("golang.org/x/text", "v0.13.0",
     "h1:TvPlkZtksWOMsz7fbANvkp4WM8x/WCo/om8BMLbz+aE=",
     "h1:ablQoSUd0tRdKxZewP80B+BaqeKJuVhuRxj/dkrun3k=", 1, 2, 1),
    ("golang.org/x/text", "v0.9.0",
     "h1:e1OnstbJyHTd6l/uOt8jFFHp6TRDWZR/bV3emEE/zU8=",
     "h1:2sjJmO8cDvYveuX97RDLsxlyUxLl+GHoLxBiRdHllBE=", 1, 3, 1),
    ("golang.org/x/tools", "v0.1.12",
     "h1:hNGJHUnrk76NpqgfD5Aqm5Crs+Hm0VOH/i9J2+nxYbc=",
     "h1:VveCTK38A2rkS8ZqFY25HIDFscX5X9OoEhJd3quQmXU=", 2, 6, 2),
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
    "wave7_dependency_source_not_acquired",
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
    """Immediate-ownership bootstrap pin matching combined-v5 semantics."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str,
        normalizer: Any = None,
    ) -> None:
        self.root = root.absolute()
        self.relative_path = relative_path
        self.normalizer = normalizer
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
            self._validate_file(self.initial)
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
    def _validate_file(info: os.stat_result) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= MAXIMUM_CODE_BYTES,
            "E_TOOL_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
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


def load_v5_checker(
    held: BootstrapPinnedCodeFile,
) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_v5_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V5_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_v5_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V5_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise DecisionFailure("E_V5_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "SafeHeldInputSet",
        "generate_candidate",
        "load_v4_checker",
        "normalized_self_bytes",
    ):
        require(
            callable(getattr(module, name, None)),
            "E_V5_API",
        )
    require(
        module.SELF_PATH == V5_CHECKER_PATH
        and module.SELF_NORMALIZED_SHA256
        == V5_CHECKER_NORMALIZED_SHA256
        and sha256_bytes(held.raw) == V5_CHECKER_RAW_SHA256,
        "E_V5_API",
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
    require(len(wave_rows) == 15, "E_TARGETS")
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
    require(len(targets) == len(wave_rows) == 15, "E_TARGETS")
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
        len(rows) == 15
        and scan["archiveCount"] == 100
        and scan["externalModCount"] == 99
        and scan["embeddedRootGoModCount"] == 1
        and scan["goSumEntryCount"] == 70
        and sum(row["declarationCount"] for row in rows) == 18
        and sum(
            row["moduleZipH1WitnessCount"] for row in rows
        )
        == 20
        and sum(row["goModH1WitnessCount"] for row in rows)
        == 41
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
            mod_h1,
            zip_h1,
            declaration_count,
            mod_count,
            zip_count,
        ) = expected
        require(
            row["module"] == module
            and row["version"] == version
            and row["selectedByGraphAlgorithm"] is False
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
            "selectedByGraphAlgorithm": False,
            "requiresSeparateWaveDecision": True,
            "acquisitionAuthorized": False,
        }
        for (
            module,
            version,
            _,
            _,
            _,
            _,
            _,
        ) in EXPECTED_IDENTITY
    ]


def validate_v5_candidate(
    candidate: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(type(candidate) is dict, "E_V5_CANDIDATE")
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
            "sha256": V5_CANDIDATE_CONTENT_SHA256,
        }
        and sha256_bytes(canonical_json_bytes(without))
        == V5_CANDIDATE_CONTENT_SHA256
        and candidate.get("schemaVersion") == "5.0"
        and candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-"
            "wave4-wave5-wave6-fixed-point-candidate"
        )
        and candidate.get("verificationOnly") is True
        and candidate.get("recordModeExposed") is False
        and candidate.get("route") == "next_wave_required",
        "E_V5_CANDIDATE",
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
        and inputs.get("heldSourceInputCount") == 199
        and inputs.get("rootArchiveCount") == 1
        and inputs.get("modCount") == 99
        and inputs.get("zipCount") == 99
        and inputs.get("uniqueModuleVersionTupleCount") == 99
        and inputs.get("combinedInputSetSha256")
        == V5_INPUT_SET_SHA256
        and type(source_bindings) is list
        and len(source_bindings) == 199
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
        and len({row["path"] for row in source_bindings}) == 199
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
        == 99
        and sum(row["kind"] == "zip" for row in source_bindings)
        == 99
        and sorted(
            {
                row["tupleOrder"]
                for row in source_bindings
                if row["kind"] != "root_zip"
            }
        )
        == list(range(1, 100))
        and len(
            {
                (row["module"], row["version"])
                for row in source_bindings
                if row["kind"] != "root_zip"
            }
        )
        == 99
        and sha256_bytes(canonical_json_bytes(source_bindings))
        == V5_INPUT_SET_SHA256
        and sha256_bytes(digest_json_bytes(source_bindings))
        == V5_SOURCE_BINDINGS_SHA256,
        "E_SOURCE_BINDING",
    )
    graph = candidate.get("graphDiscovery")
    frontier = (
        graph.get("exactFrontier")
        if type(graph) is dict
        else None
    )
    require(
        type(graph) is dict
        and graph.get("graphSha256") == V5_GRAPH_SHA256
        and graph.get("fixedPointReached") is False
        and graph.get("newTupleCount") == 15
        and frontier == expected_frontier()
        and sha256_bytes(canonical_json_bytes(frontier))
        == V5_FRONTIER_SHA256,
        "E_V5_GRAPH",
    )
    verification = candidate.get("checkerVerification")
    counters = candidate.get("operationCounters")
    authority = candidate.get("authority")
    require(
        type(verification) is dict
        and verification.get("directFullInputReconstructionCount")
        == 2
        and verification.get("inheritedFullInputReconstructionCount")
        == 6
        and verification.get("totalFullInputReconstructionCount")
        == 8
        and verification.get("transitiveSafePinnedClassesVerified")
        is True
        and verification.get("readOnlyProviderFacadeVerified")
        is True
        and verification.get("providerFacadeVerificationScope")
        == "trusted_pinned_normal_reconstruction_path"
        and type(counters) is dict
        and counters.get("directArchiveOpenCount") == 200
        and counters.get("inheritedArchiveOpenCount") == 400
        and counters.get("totalArchiveOpenCount") == 600
        and counters.get("networkOperationCount") == 0
        and counters.get("subprocessCount") == 0
        and counters.get("fileWriteCount") == 0
        and type(authority) is dict
        and authority.get("osSyscallSandboxProvided") is False
        and all(value is False for value in authority.values()),
        "E_V5_VERIFICATION",
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
    require(len(rows) == 15, "E_REQUEST_SET")
    result: list[dict[str, Any]] = []
    for row in rows:
        order = row["tupleOrder"]
        module = row["module"]
        version = row["version"]
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
                    "selectedByGraphAlgorithm": False,
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
        len(result) == 30
        and [row["requestOrdinal"] for row in result]
        == list(range(1, 31))
        and [
            row["resourceKind"]
            for row in result
        ]
        == ["mod", "zip"] * 15,
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
        and sha256_bytes(package_raw[V5_CHECKER_PATH])
        == V5_CHECKER_RAW_SHA256
        and sha256_bytes(
            package_raw[V5_TESTS_PATH]
        )
        == V5_TESTS_RAW_SHA256,
        "E_TOOL_IDENTITY",
    )
    return [
        {
            "role": "current_wave7_decision_checker",
            "path": SELF_PATH,
            "normalizedSha256": SELF_NORMALIZED_SHA256,
        },
        {
            "role": "current_wave7_decision_tests",
            "path": TESTS_PATH,
            "rawSha256": TESTS_RAW_SHA256,
        },
        {
            "role": "immutable_combined_v5_checker",
            "path": V5_CHECKER_PATH,
            "rawSha256": V5_CHECKER_RAW_SHA256,
            "normalizedSha256": V5_CHECKER_NORMALIZED_SHA256,
        },
        {
            "role": "immutable_combined_v5_tests",
            "path": V5_TESTS_PATH,
            "rawSha256": V5_TESTS_RAW_SHA256,
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
            "identity-and-acquisition-decision-wave7"
        ),
        "schemaVersion": "1.0",
        "checkerId": CHECKER_ID,
        "decisionId": DECISION_ID,
        "date": "2026-07-26",
        "status": (
            "wave7_exact_15_frontier_identity_classified_"
            "15_complete_0_blocked_acquisition_ready_not_authorized"
        ),
        "result": (
            "exact_15_version_vertices_0_selected_15_nonselected_"
            "15_complete_h1_pairs_acquisition_ready_not_authorized"
        ),
        "verificationOnly": True,
        "recordModeExposed": False,
        "predecessorBindings": {
            "combinedFixedPointV5": {
                "checkerPath": V5_CHECKER_PATH,
                "checkerRawSha256": V5_CHECKER_RAW_SHA256,
                "checkerNormalizedSha256":
                    V5_CHECKER_NORMALIZED_SHA256,
                "testsPath": V5_TESTS_PATH,
                "testsRawSha256": V5_TESTS_RAW_SHA256,
                "contentSha256": V5_CANDIDATE_CONTENT_SHA256,
                "combinedInputSetSha256": V5_INPUT_SET_SHA256,
                "sourceBindingsSha256":
                    V5_SOURCE_BINDINGS_SHA256,
                "graphSha256": V5_GRAPH_SHA256,
                "frontierSha256": V5_FRONTIER_SHA256,
                "fixedPointReached": False,
                "frontierTupleCount": 15,
                "totalFullSourceReconstructionCount": 8,
                "totalGraphArchiveOpenCount": 600,
                "providerFacadeVerificationScope": (
                    "trusted_pinned_normal_reconstruction_path"
                ),
                "trustedPinnedNormalPathFileWriteCount": 0,
                "osSyscallSandboxProvided": False,
                "retainedSnapshotBoundary": {
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
            "sourceBindingsSha256": V5_SOURCE_BINDINGS_SHA256,
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
                "current_wave7_lowercase_ascii_direct_proxy_path",
            "claimPath": WAVE7_CLAIM_PATH,
            "stagingDirectoryPrefix": WAVE7_STAGING_PREFIX,
            "acceptedDirectoryPath": WAVE7_ACCEPTED_PATH,
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
            "combinedV5CandidateInvocationCount": 1,
            "predecessorFullSourceReconstructionCount": 6,
            "directV5FullSourceReconstructionCount": 2,
            "totalFullSourceReconstructionCount": 8,
            "predecessorGraphArchiveOpenCount": 400,
            "currentV5GraphArchiveOpenCount": 200,
            "totalV5GraphArchiveOpenCount": 600,
            "identityWitnessScanCount": 2,
            "identityWitnessArchiveOpenCount": 200,
            "overallDecisionExecutionArchiveOpenCount": 800,
            "descriptorIdentityBarrierCount": 6,
            "networkOperationCount": 0,
            "subprocessCount": 0,
            "authenticationOperationCount": 0,
            "dependencySourceExecutionCount": 0,
            "archiveExtractionCount": 0,
            "fileWriteCount": 0,
        },
        "closure": {
            "wave7IdentityResolved": True,
            "wave7AcquisitionReady": True,
            "wave7AcquisitionComplete": False,
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
            "prepare_separate_one_use_30_resource_wave7_source_"
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
            "identity-and-acquisition-decision-wave7"
        )
        and document.get("schemaVersion") == "1.0"
        and document.get("checkerId") == CHECKER_ID
        and document.get("decisionId") == DECISION_ID
        and document.get("date") == "2026-07-26"
        and document.get("status")
        == (
            "wave7_exact_15_frontier_identity_classified_"
            "15_complete_0_blocked_acquisition_ready_not_authorized"
        )
        and document.get("result")
        == (
            "exact_15_version_vertices_0_selected_15_nonselected_"
            "15_complete_h1_pairs_acquisition_ready_not_authorized"
        )
        and document.get("verificationOnly") is True
        and document.get("recordModeExposed") is False,
        "E_DECISION_SCHEMA",
    )

    predecessors = document.get("predecessorBindings")
    combined = (
        predecessors.get("combinedFixedPointV5")
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
        "retainedSnapshotBoundary",
    }
    retained_keys = {
        "completionAppliesToRetainedSnapshot",
        "currentPathIdentityGuaranteedThroughManifestPublication",
        "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
    }
    require(
        exact_keys(predecessors, {"combinedFixedPointV5"})
        and exact_keys(combined, combined_keys)
        and exact_keys(retained, retained_keys)
        and combined
        == {
            "checkerPath": V5_CHECKER_PATH,
            "checkerRawSha256": V5_CHECKER_RAW_SHA256,
            "checkerNormalizedSha256":
                V5_CHECKER_NORMALIZED_SHA256,
            "testsPath": V5_TESTS_PATH,
            "testsRawSha256": V5_TESTS_RAW_SHA256,
            "contentSha256": V5_CANDIDATE_CONTENT_SHA256,
            "combinedInputSetSha256": V5_INPUT_SET_SHA256,
            "sourceBindingsSha256": V5_SOURCE_BINDINGS_SHA256,
            "graphSha256": V5_GRAPH_SHA256,
            "frontierSha256": V5_FRONTIER_SHA256,
            "fixedPointReached": False,
            "frontierTupleCount": 15,
            "totalFullSourceReconstructionCount": 8,
            "totalGraphArchiveOpenCount": 600,
            "providerFacadeVerificationScope":
                "trusted_pinned_normal_reconstruction_path",
            "trustedPinnedNormalPathFileWriteCount": 0,
            "osSyscallSandboxProvided": False,
            "retainedSnapshotBoundary": {
                "completionAppliesToRetainedSnapshot": True,
                "currentPathIdentityGuaranteedThroughManifestPublication":
                    False,
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                    False,
            },
        }
        and combined["fixedPointReached"] is False
        and combined["osSyscallSandboxProvided"] is False
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
        and held["sourceBindingCount"] == 199
        and held["sourceBindingsSha256"]
        == V5_SOURCE_BINDINGS_SHA256
        and held["archiveCount"] == 100
        and held["externalModCount"] == 99
        and held["embeddedRootGoModCount"] == 1
        and held["goSumEntryCount"] == 70
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
        and identity["tupleCount"] == 15
        and identity["graphSelectedTupleCount"] == 0
        and identity["versionSpecificNonSelectedTupleCount"] == 15
        and identity["parentDeclarationCount"] == 18
        and identity["moduleZipH1WitnessCount"] == 20
        and identity["goModH1WitnessCount"] == 41
        and identity["completeIdentityPairCount"] == 15
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
        and len(rows) == 15,
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
            and row["selectedByGraphAlgorithm"] is False
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
            "goModH1Values": [expected[2]],
            "moduleZipH1Values": [expected[3]],
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
                "oneUseNoOverwriteRequired",
                "atomicNoReplacePromotionRequired",
                "independentPostConsumptionReadbackRequired",
            },
        )
        and preparation["acquisitionReady"] is True
        and preparation["acquisitionAuthorizedByThisDecision"] is False
        and preparation["separateOneUseExecutionPermitRequired"] is True
        and type(preparation["requestCount"]) is int
        and preparation["requestCount"] == 30
        and preparation["requestOrder"]
        == "tuple_order_ascending_mod_then_zip"
        and type(requests) is list
        and len(requests) == 30
        and all(
            exact_keys(row, request_keys)
            and type(row["requestOrdinal"]) is int
            and type(row["tupleOrder"]) is int
            and type(row["maximumResponseBytes"]) is int
            and row["selectedByGraphAlgorithm"] is False
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
        == "current_wave7_lowercase_ascii_direct_proxy_path"
        and preparation["claimPath"] == WAVE7_CLAIM_PATH
        and preparation["stagingDirectoryPrefix"]
        == WAVE7_STAGING_PREFIX
        and preparation["acceptedDirectoryPath"]
        == WAVE7_ACCEPTED_PATH
        and preparation["oneUseNoOverwriteRequired"] is True
        and preparation["atomicNoReplacePromotionRequired"] is True
        and preparation[
            "independentPostConsumptionReadbackRequired"
        ]
        is True,
        "E_DECISION_REQUEST",
    )

    expected_counters = {
        "combinedV5CandidateInvocationCount": 1,
        "predecessorFullSourceReconstructionCount": 6,
        "directV5FullSourceReconstructionCount": 2,
        "totalFullSourceReconstructionCount": 8,
        "predecessorGraphArchiveOpenCount": 400,
        "currentV5GraphArchiveOpenCount": 200,
        "totalV5GraphArchiveOpenCount": 600,
        "identityWitnessScanCount": 2,
        "identityWitnessArchiveOpenCount": 200,
        "overallDecisionExecutionArchiveOpenCount": 800,
        "descriptorIdentityBarrierCount": 6,
        "networkOperationCount": 0,
        "subprocessCount": 0,
        "authenticationOperationCount": 0,
        "dependencySourceExecutionCount": 0,
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
        "wave7IdentityResolved": True,
        "wave7AcquisitionReady": True,
        "wave7AcquisitionComplete": False,
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
            "prepare_separate_one_use_30_resource_wave7_source_"
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
        v5_held = stack.enter_context(
            BootstrapPinnedCodeFile(
                root,
                V5_CHECKER_PATH,
                V5_CHECKER_RAW_SHA256,
            )
        )
        v5 = load_v5_checker(v5_held)
        v5_tests_held = stack.enter_context(
            v5.PinnedCodeFile(
                root,
                V5_TESTS_PATH,
                V5_TESTS_RAW_SHA256,
            )
        )
        tests_held = stack.enter_context(
            v5.PinnedCodeFile(
                root,
                TESTS_PATH,
                TESTS_RAW_SHA256,
            )
        )
        reader_held = stack.enter_context(
            v5.PinnedCodeFile(
                root,
                READER_PATH,
                READER_RAW_SHA256,
            )
        )
        package_raw = {
            SELF_PATH: self_held.raw,
            TESTS_PATH: tests_held.raw,
            READER_PATH: reader_held.raw,
            V5_CHECKER_PATH: v5_held.raw,
            V5_TESTS_PATH: v5_tests_held.raw,
        }
        held: list[Any] = [
            self_held,
            v5_held,
            v5_tests_held,
            tests_held,
            reader_held,
        ]

        identity_barrier(root, held)
        candidate = v5.generate_candidate(root)
        identity_barrier(root, held)
        wave_rows, source_bindings = validate_v5_candidate(candidate)

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
            type(runner) is v5.ReadOnlyProviderFacade
            and v4.PinnedCodeFile is v5.PinnedCodeFile
            and v1.PinnedRunnerFile is v5.SafePinnedRunnerFile,
            "E_SAFE_RUNTIME",
        )
        controls = (
            v1.control_bindings()
            + v4.wave3_control_bindings()
            + v4.wave4_control_bindings()
            + v4.wave5_control_bindings()
            + v5.wave6_control_bindings()
        )
        control_held = stack.enter_context(
            runner.HeldInputSet(root, controls)
        )
        v1_documents = v1.parse_control_documents(
            runner,
            control_held,
        )
        v1.validate_terminal_documents(runner, v1_documents)
        wave3_documents = v4.parse_wave3_documents(
            runner,
            control_held,
        )
        wave4_documents = v4.parse_wave4_documents(
            runner,
            control_held,
        )
        wave5_documents = v4.parse_wave5_documents(
            runner,
            control_held,
        )
        wave6_documents = v5.parse_wave6_documents(
            runner,
            control_held,
        )
        full_source_bindings = v5.combined_source_bindings(
            v4,
            v1,
            runner,
            v1_documents,
            wave3_documents,
            wave4_documents,
            wave5_documents,
            wave6_documents,
        )
        require(
            v1.source_projection(full_source_bindings)
            == source_bindings
            and len(full_source_bindings) == 199
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
                v4_held,
                v1_held,
                provider_held,
                control_held,
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

    return expected, {
        "documentType":
            "aetherlink.wave7-identity-acquisition-decision-check",
        "schemaVersion": "1.0",
        "status":
            "validated_15_of_15_acquisition_ready_not_authorized",
        "validationPassed": True,
        "tupleCount": 15,
        "parentDeclarationCount": 18,
        "moduleZipH1WitnessCount": 20,
        "goModH1WitnessCount": 41,
        "completeIdentityPairCount": 15,
        "blockedTupleCount": 0,
        "conflictingIdentityCount": 0,
        "acquisitionReady": True,
        "acquisitionAuthorized": False,
        "networkUsed": False,
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
            "aetherlink.wave7-identity-acquisition-decision-error",
        "schemaVersion": "1.0",
        "status": "failed_closed",
        "failureCode": code,
        "acquisitionAuthorized": False,
        "networkUsed": False,
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
