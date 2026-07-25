#!/usr/bin/env python3
"""Validate the offline Wave6 source-identity and acquisition-ready decision.

Run only with ``python3 -I -B -S``.  The checker replays the externally
pinned combined graph candidate, holds every already-acquired source byte by
descriptor, and derives the exact Wave6 parent declarations and module/go.mod
H1 pairs twice.  It performs no network, subprocess, authentication, archive
extraction, dependency-source execution, or filesystem write.
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
            "Wave6 decision checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
import base64
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
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
    "decision-wave6-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave6-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave6_decision_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave6_decision_v1.py"
)
WAVE6_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave6_candidate_v1.py"
)
WAVE6_CHECKER_RAW_SHA256 = (
    "6a34f78fc5fc89df2c0ac21c127099b4654b63f3688b0066df8b904618d8e352"
)
WAVE6_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave6_candidate_v1.py"
)
WAVE6_TESTS_RAW_SHA256 = (
    "49a15a5702b4a0de1499fb9ed57fee60c5e6ceb7aeb78f4fb461ad28ca61d6db"
)
WAVE6_CANDIDATE_CONTENT_SHA256 = (
    "1f8cb71fb454d36e339e286e5ef5631eb1e94cc2202adb72872057e40e3f0858"
)
COMBINED_V4_CONTENT_SHA256 = (
    "c223cb039aa7e819e78cd1b27c360076c50197b0cd11a21dd447fcdcb01d23a6"
)
COMBINED_V4_CHECKER_NORMALIZED_SHA256 = (
    "bbd67ceacb71af6b4228fd3ce524b120dd836a2a9e01f552f09ffcd80e479785"
)
COMBINED_SOURCE_BINDINGS_SHA256 = (
    "c8d5515eb4514216b43dd1192e86d33f849ae6e6085046a6e28a024386623acc"
)
COMBINED_INPUT_SET_SHA256 = (
    "b7eca5385fd0cf811d0eb7e8a00fe467bf64f8c10fa1ab998521f00510b0b8b2"
)
COMBINED_GRAPH_SHA256 = (
    "284ca32d914519393d1e29c43827dbcb06d57b63a4d78cb87d7cc0de6696e448"
)
COMBINED_FRONTIER_SHA256 = (
    "a966326a38b3050ac6ad7387405d359488b049d86982cde27946008dd258a6ce"
)
COMPACT_IDENTITY_SHA256 = (
    "f93cb8006e2c391934ffa820b2d03b3ba99075481b1437c3fe27e068242e35fe"
)
FULL_WITNESS_SHA256 = (
    "d3ea9f3c934911e7d5a7624cdba27ef71be222a6764f65a9b41664fa1e96937e"
)
EXPECTED_READER_RAW_SHA256 = (
    "4b97356305cf7817d39dfc1feb21e57c9afc1a887d6676c0bbcaa6259326ca57"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-wave6-identity-acquisition-decision-check-v1"
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-"
    "identity-and-acquisition-decision-wave6-v1"
)
MAXIMUM_CODE_BYTES = 4 * 1024 * 1024
MAXIMUM_DECISION_BYTES = 8 * 1024 * 1024
MAXIMUM_SOURCE_BYTES = 16 * 1024 * 1024
MAXIMUM_GO_METADATA_BYTES = 1024 * 1024
MAXIMUM_ARCHIVE_ENTRIES = 100_000
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
WAVE6_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-6-v1.claim"
WAVE6_STAGING_PREFIX = ".wave-6-v1-staging-"
WAVE6_FINAL_NAME = "wave-6-v1"
WAVE6_ACCEPTED_PATH = f"{DEPENDENCY_ROOT}/wave-6-v1/accepted"
EXPECTED_DECISION_AUTHORITY = {
    "decisionAuthorityGranted": False,
    "executionAuthorityGranted": False,
    "acquisitionAuthorityGranted": False,
    "networkAuthorized": False,
    "dnsAuthorized": False,
    "socketAuthorized": False,
    "subprocessAuthorized": False,
    "dependencySourceExecutionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "compileAuthorized": False,
    "fileWriteAuthorized": False,
    "gitWriteAuthorized": False,
    "publicationAuthorityGranted": False,
    "repositoryOwnerIdentityProofRequired": False,
    "externalAuthenticationRequired": False,
    "authenticationRequired": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "signatureRequired": False,
    "tokenRequired": False,
    "userActionRequired": False,
}
EXPECTED_NON_CLAIMS = (
    "this decision is not a network or source-acquisition execution permit",
    "held H1 pairs establish deterministic acquisition inputs, not source "
    "authorship or repository ownership",
    "selectedByGraphAlgorithm false does not remove a version-specific "
    "graph vertex",
    "no Wave6 source byte was downloaded, extracted, loaded, executed, "
    "reviewed, or compiled",
    "identity readiness is not dependency fixed point, semantic closure, "
    "candidate selection, library selection, rung-three completion, or "
    "release readiness",
    "no account, owner, SSH, GPG, password, private key, signature, token, "
    "or user authentication is required",
)
EXPECTED_IDENTITY_H1 = [
    ("github.com/stretchr/objx", "v0.4.0", "h1:YvHI0jy2hoMjB+UWwv71VJQ9isScKT/TqJzVSSt89Yw=", "h1:M2gUjqZET1qApGOWNSnZ49BAIMX4F/1plDv3+l31EJ4="),
    ("golang.org/x/crypto", "v0.23.0", "h1:CKFgDieR+mRhux2Lsu27y0fO304Db0wZe70UKqHu0v8=", "h1:dIJU/v2J8Mdglj/8rJ6UUOM3Zc9zLZxVZwwxMooUSAI="),
    ("golang.org/x/crypto", "v0.44.0", "h1:013i+Nw79BMiQiMsOPcVCB5ZIJbYkerPrGnOa00tvmc=", "h1:A97SsFvM3AIwEEmTBiaxPPTYpDC47w720rdiiUvgoAU="),
    ("golang.org/x/mod", "v0.12.0", "h1:iBbtSCu2XBx23ZKBPSOrRkjjQPZFPuis4dIYUhu/chs=", "h1:rmsUpXtvNzj340zd98LZ4KntptpfRHwpFOHG188oHXc="),
    ("golang.org/x/mod", "v0.15.0", "h1:hTbmBsO62+eylJbnUtE2MGJUyE7QWk4xUqPFrRgJ+7c=", "h1:SernR4v+D55NyBH2QiEQrlBAnj1ECL6AGrA5+dPaMY8="),
    ("golang.org/x/mod", "v0.8.0", "h1:iBbtSCu2XBx23ZKBPSOrRkjjQPZFPuis4dIYUhu/chs=", "h1:LUYupSeNrTNCGzR/hVBk2NHZO4hXcVaW1k4Qx7rjPx8="),
    ("golang.org/x/net", "v0.10.0", "h1:0qNGK6F8kojg2nk9dLZ2mShWaEBan6FAoqfSigmmuDg=", "h1:X2//UzNDwYmtCLn7To6G58Wr6f5ahEAQgKNzv9Y951M="),
    ("golang.org/x/net", "v0.15.0", "h1:idbUs1IY1+zTqbi8yxTbhexhEEk5ur9LInksu6HrEpk=", "h1:ugBLEUaxABaB5AJqW9enI0ACdci2RUd4eP51NTBvuJ8="),
    ("golang.org/x/sync", "v0.3.0", "h1:FU7BRWz2tNW+3quACPkgCx/L+uEAv1htQ0V83Z9Rj+Y=", "h1:ftCYgMx6zT/asHUrPw8BLLscYtGznsLAnjq5RH9P66E="),
    ("golang.org/x/sync", "v0.6.0", "h1:Czt+wKu1gCyEFDUtn0jG5QVvpJ6rzVqr5aXyt9drQfk=", "h1:5BMeUDZ7vkXGfEr1x9B4bRcTH4lpkTkpdh0T/J+qjbQ="),
    ("golang.org/x/sys", "v0.12.0", "h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=", "h1:CM0HF96J0hcLAwsHPJZjfdNzs0gftsLfgKt57wWHJ0o="),
    ("golang.org/x/sys", "v0.5.0", "h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=", "h1:MUK/U/4lj1t1oPg0HfuXDN/Z1wv31ZJ/YcPiGccS4DU="),
    ("golang.org/x/term", "v0.20.0", "h1:8UkIAJTvZgivsXaD6/pH6U9ecQzZ45awqEOzuCvwpFY=", "h1:VnkxpohqXaOBYJtBmEppKUG6mXpi+4O6purfc2+sMhw="),
    ("golang.org/x/term", "v0.37.0", "h1:5pB4lxRNYYVZuTLmy8oR2BH8dflOR+IbTYFD8fi3254=", "h1:8EGAD0qCmHYZg6J17DvsMy9/wJ7/D/4pV/wfnld5lTU="),
    ("golang.org/x/text", "v0.15.0", "h1:18ZOQIKpY8NJVqYksKHtTdi31H5itFRjB5/qKTNYzSU=", "h1:h1V/4gjBv8v9cjcR6+AR5+/cIYK5N/WAgiv4xlsEtAk="),
    ("golang.org/x/text", "v0.31.0", "h1:tKRAlv61yKIjGGHX/4tP1LTbc13YSec1pxVEWXzfoeM=", "h1:aC8ghyu4JhP8VojJ2lEHBnochRno1sgL6nEi9WGFGMM="),
    ("golang.org/x/tools", "v0.38.0", "h1:yEsQ/d/YK8cjh0L6rZlY8tgtlKiBNTL14pGDJPJpYQs=", "h1:Hx2Xv8hISq8Lm16jvBZ2VQf+RLmbd7wVUsALibYI/IQ="),
    ("golang.org/x/tools", "v0.6.0", "h1:Xwgl3UAJ/d3gWutnCtw505GrjyAbvKui8lOU390QaIU=", "h1:BOw41kyTf3PuCW1pVQf8+Cyg8pMlkYB1oo9iJ6D/lKM="),
]


class DecisionFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise DecisionFailure("E_ARGUMENT")


def require(condition: bool, code: str) -> None:
    if not condition:
        raise DecisionFailure(code)


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


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(
                DecisionFailure("E_JSON")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                DecisionFailure("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionFailure("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def validate_materialized_decision(
    raw: bytes,
    expected: Mapping[str, Any],
    package_raw: Mapping[str, bytes],
) -> dict[str, Any]:
    actual = strict_json(raw)
    validate_semantic_decision(actual, package_raw)
    require(
        raw == canonical_json_bytes(actual)
        and actual == expected,
        "E_DECISION",
    )
    return actual


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    require("contentBinding" not in result, "E_CONTENT")
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "decision_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(result)),
    }
    return result


def expected_tool_bindings(
    package_raw: Mapping[str, bytes],
) -> list[dict[str, str]]:
    checker_raw = package_raw.get(THIS_CHECKER_PATH)
    tests_raw = package_raw.get(THIS_TESTS_PATH)
    require(
        type(checker_raw) is bytes and type(tests_raw) is bytes,
        "E_DECISION_BINDINGS",
    )
    return [
        {
            "role": "wave6_identity_decision_checker",
            "path": THIS_CHECKER_PATH,
            "rawSha256": sha256_bytes(checker_raw),
        },
        {
            "role": "wave6_identity_decision_tests",
            "path": THIS_TESTS_PATH,
            "rawSha256": sha256_bytes(tests_raw),
        },
    ]


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


class PinnedFile:
    """Hold one exact, immutable-by-name file beneath the workspace root."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        *,
        expected_sha256: str | None = None,
        maximum_bytes: int = MAXIMUM_CODE_BYTES,
    ) -> None:
        self.root_path = root
        self.relative_path = relative_path
        self.root_fd = -1
        self.parent_fd = -1
        self.fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.raw = b""
        try:
            parts = relative_path.split("/")
            require(
                bool(parts)
                and all(part not in {"", ".", ".."} for part in parts),
                "E_FILE_IDENTITY",
            )
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self.root_initial = os.fstat(self.root_fd)
            self._validate_directory(self.root_initial)
            current = os.dup(self.root_fd)
            for component in parts[:-1]:
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    dir_fd=current,
                )
                info = os.fstat(child)
                self._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = parts[-1]
            self.fd = os.open(
                self.name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=self.parent_fd,
            )
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial, maximum_bytes)
            first = self._read_pass(maximum_bytes)
            second = self._read_pass(maximum_bytes)
            require(first == second, "E_FILE_IDENTITY")
            if expected_sha256 is not None:
                require(
                    sha256_bytes(first) == expected_sha256,
                    "E_FILE_IDENTITY",
                )
            self.raw = first
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_FILE_IDENTITY",
        )

    @staticmethod
    def _validate_file(
        info: os.stat_result,
        maximum_bytes: int,
    ) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= maximum_bytes,
            "E_FILE_IDENTITY",
        )

    def _read_pass(self, maximum_bytes: int) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before, maximum_bytes)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_FILE_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", "E_FILE_IDENTITY")
        after = os.fstat(self.fd)
        require(
            file_identity(before) == file_identity(after),
            "E_FILE_IDENTITY",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root_path, follow_symlinks=False)
            current = os.fstat(self.fd)
            named = os.stat(
                self.name,
                dir_fd=self.parent_fd,
                follow_symlinks=False,
            )
        except OSError as error:
            raise DecisionFailure("E_FILE_IDENTITY") from error
        require(
            directory_identity(held_root)
            == directory_identity(self.root_initial)
            == directory_identity(named_root),
            "E_ROOT_IDENTITY",
        )
        require(
            file_identity(current)
            == file_identity(self.initial)
            == file_identity(named),
            "E_FILE_IDENTITY",
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
                "E_FILE_IDENTITY",
            )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directories):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directories.clear()
        if self.parent_fd >= 0 and self.parent_fd not in seen:
            os.close(self.parent_fd)
        self.parent_fd = -1
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def __enter__(self) -> "PinnedFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class HeldNamespace:
    """Hold the dependency directory and prove the Wave6 namespace absent."""

    def __init__(self, root: Path) -> None:
        self.root_path = root
        self.root_fd = -1
        self.namespace_fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        try:
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self.root_initial = os.fstat(self.root_fd)
            PinnedFile._validate_directory(self.root_initial)
            current = os.dup(self.root_fd)
            for component in DEPENDENCY_ROOT.split("/"):
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    dir_fd=current,
                )
                info = os.fstat(child)
                PinnedFile._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.namespace_fd = current
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _portable(value: str) -> str:
        return unicodedata.normalize("NFC", value).casefold()

    def observe_absent(self) -> None:
        try:
            names = os.listdir(self.namespace_fd)
        except OSError as error:
            raise DecisionFailure("E_NAMESPACE") from error
        claim = self._portable(Path(WAVE6_CLAIM_PATH).name)
        final = self._portable(WAVE6_FINAL_NAME)
        staging = self._portable(WAVE6_STAGING_PREFIX)
        portable_names = [self._portable(name) for name in names]
        require(
            claim not in portable_names
            and final not in portable_names
            and not any(name.startswith(staging) for name in portable_names),
            "E_NAMESPACE",
        )

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root_path, follow_symlinks=False)
        except OSError as error:
            raise DecisionFailure("E_NAMESPACE") from error
        require(
            directory_identity(held_root)
            == directory_identity(self.root_initial)
            == directory_identity(named_root),
            "E_ROOT_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            try:
                held = os.fstat(child)
                named = os.stat(
                    component,
                    dir_fd=parent,
                    follow_symlinks=False,
                )
            except OSError as error:
                raise DecisionFailure("E_NAMESPACE") from error
            require(
                directory_identity(held)
                == directory_identity(initial)
                == directory_identity(named),
                "E_NAMESPACE",
            )
        self.observe_absent()

    def close(self) -> None:
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directories):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directories.clear()
        self.namespace_fd = -1
        if self.root_fd >= 0 and self.root_fd not in seen:
            os.close(self.root_fd)
        self.root_fd = -1

    def __enter__(self) -> "HeldNamespace":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def identity_barrier(root: Path, held: Sequence[Any]) -> None:
    try:
        named_before = os.stat(root, follow_symlinks=False)
        require(stat.S_ISDIR(named_before.st_mode), "E_ROOT_IDENTITY")
        expected = directory_identity(named_before)
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
            directory_identity(os.stat(root, follow_symlinks=False))
            == expected,
            "E_ROOT_IDENTITY",
        )
    except OSError as error:
        raise DecisionFailure("E_ROOT_IDENTITY") from error


def load_wave6_checker(held: PinnedFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_wave6_candidate_checker_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / WAVE6_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_wave6_candidate_checker_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            WAVE6_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise DecisionFailure("E_WAVE6_CHECKER_LOAD") from error
    for name in (
        "BootstrapPinnedCodeFile",
        "canonical_json_bytes",
        "content_bound",
        "load_v4_checker",
        "validate_v4_candidate",
        "wave6_rows",
    ):
        require(callable(getattr(module, name, None)), "E_WAVE6_CHECKER_API")
    require(
        module.CHECKER_ID
        == "g2-pion-ice-v4.3.0-wave6-frontier-candidate-check-v1"
        and module.V4_CANDIDATE_CONTENT_SHA256
        == COMBINED_V4_CONTENT_SHA256
        and module.V4_INPUT_SET_SHA256 == COMBINED_INPUT_SET_SHA256
        and module.V4_SOURCE_BINDINGS_SHA256
        == COMBINED_SOURCE_BINDINGS_SHA256
        and module.V4_CHECKER_NORMALIZED_SHA256
        == COMBINED_V4_CHECKER_NORMALIZED_SHA256
        and module.V4_GRAPH_SHA256 == COMBINED_GRAPH_SHA256
        and module.V4_FRONTIER_SHA256 == COMBINED_FRONTIER_SHA256
        and module.V4_PREDECESSOR_RECONSTRUCTION_COUNT == 4
        and module.V4_DIRECT_RECONSTRUCTION_COUNT == 2
        and module.V4_TOTAL_RECONSTRUCTION_COUNT == 6
        and module.V4_PREDECESSOR_ARCHIVE_OPEN_COUNT == 236
        and module.V4_DIRECT_ARCHIVE_OPEN_COUNT == 164
        and module.V4_TOTAL_ARCHIVE_OPEN_COUNT == 400,
        "E_WAVE6_CHECKER_API",
    )
    return module


def strict_text_lines(raw: bytes, code: str) -> list[str]:
    require(
        len(raw) <= MAXIMUM_GO_METADATA_BYTES
        and b"\x00" not in raw
        and b"\r" not in raw,
        code,
    )
    try:
        return raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise DecisionFailure(code) from error


def valid_h1(value: str) -> bool:
    if not value.startswith("h1:"):
        return False
    try:
        decoded = base64.b64decode(value[3:], validate=True)
    except (ValueError, base64.binascii.Error):
        return False
    return len(decoded) == 32


def capture_declarations(
    *,
    raw: bytes,
    runner: types.ModuleType,
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
    lines = strict_text_lines(raw, "E_GO_MOD")
    result = {key: [] for key in targets}
    block: str | None = None
    for line_number, text in enumerate(lines, 1):
        try:
            tokens = runner.tokenize_mod_line(text)
        except Exception as error:
            raise DecisionFailure("E_GO_MOD") from error
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
    lines = strict_text_lines(raw, "E_GO_SUM")
    zip_result = {key: [] for key in targets}
    mod_result = {key: [] for key in targets}
    entry_hash = sha256_bytes(raw)
    for line_number, text in enumerate(lines, 1):
        tokens = text.split()
        if not tokens:
            continue
        require(len(tokens) == 3 and valid_h1(tokens[2]), "E_GO_SUM")
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
    source: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> None:
    for pair, rows in source.items():
        destination[pair].extend(dict(row) for row in rows)


def validate_archive_names(infos: Sequence[zipfile.ZipInfo]) -> None:
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
        components = name[:-1].split("/") if name.endswith("/") else name.split("/")
        require(
            bool(components)
            and all(component not in {"", ".", ".."} for component in components),
            "E_ZIP",
        )
        normalized = unicodedata.normalize("NFC", name).casefold()
        require(name not in exact and normalized not in portable, "E_ZIP")
        exact.add(name)
        portable.add(normalized)
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        require(
            file_type in {0, stat.S_IFREG, stat.S_IFDIR}
            and not stat.S_ISLNK(mode),
            "E_ZIP",
        )


def scan_source_identity(
    *,
    source_bindings: Sequence[Mapping[str, Any]],
    source_raw: Mapping[str, bytes],
    wave_rows: Sequence[Mapping[str, Any]],
    runner: types.ModuleType,
) -> dict[str, Any]:
    targets = {
        (row["module"], row["version"]): row
        for row in wave_rows
    }
    require(len(targets) == len(wave_rows) == 18, "E_TARGETS")
    declarations = {key: [] for key in targets}
    zip_h1 = {key: [] for key in targets}
    mod_h1 = {key: [] for key in targets}
    archive_count = 0
    external_mod_count = 0
    embedded_root_go_mod_count = 0

    for binding in source_bindings:
        path = binding["path"]
        raw = source_raw[path]
        require(
            sha256_bytes(raw) == binding["rawSha256"],
            "E_SOURCE_BINDING",
        )
        if binding["kind"] == "mod":
            external_mod_count += 1
            found = capture_declarations(
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
            )
            merge_witnesses(declarations, found)
            continue
        require(binding["kind"] in {"zip", "root_zip"}, "E_SOURCE_BINDING")
        archive_count += 1
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                infos = archive.infolist()
                validate_archive_names(infos)
                if binding["kind"] == "root_zip":
                    expected_go_mod = (
                        f"{binding['module']}@{binding['version']}/go.mod"
                    )
                    matches = [
                        info for info in infos
                        if info.filename == expected_go_mod
                    ]
                    require(len(matches) == 1, "E_ROOT_GO_MOD")
                    info = matches[0]
                    require(
                        not info.is_dir()
                        and info.file_size <= MAXIMUM_GO_METADATA_BYTES,
                        "E_ROOT_GO_MOD",
                    )
                    embedded = archive.read(info)
                    embedded_root_go_mod_count += 1
                    found = capture_declarations(
                        raw=embedded,
                        runner=runner,
                        targets=targets,
                        holder_module=binding["module"],
                        holder_version=binding["version"],
                        holder_wave=binding["wave"],
                        container_kind="embedded_root_mod",
                        path=f"{path}!/{info.filename}",
                        container_raw_sha256=binding["rawSha256"],
                        entry_raw_sha256=sha256_bytes(embedded),
                    )
                    merge_witnesses(declarations, found)
                for info in infos:
                    if not info.filename.endswith("/go.sum"):
                        continue
                    require(
                        not info.is_dir()
                        and info.file_size <= MAXIMUM_GO_METADATA_BYTES,
                        "E_GO_SUM",
                    )
                    entry = archive.read(info)
                    found_zip, found_mod = parse_go_sum_entry(
                        raw=entry,
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
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
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
            "selectedByGraphAlgorithm": row["selectedByGraphAlgorithm"],
            "moduleZipH1": row["moduleZipH1Values"][0],
            "goModH1": row["goModH1Values"][0],
        }
        for row in rows
    ]
    return {
        "archiveCount": archive_count,
        "externalModCount": external_mod_count,
        "embeddedRootGoModCount": embedded_root_go_mod_count,
        "tuples": rows,
        "compactIdentity": compact,
        "compactIdentitySha256": sha256_bytes(digest_json_bytes(compact)),
        "fullWitnessSha256": sha256_bytes(digest_json_bytes(rows)),
    }


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
    for expected_order, wave_row in enumerate(wave_rows, 1):
        require(wave_row["tupleOrder"] == expected_order, "E_TARGETS")
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
        row = {
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
                len(zip_values) == 1 and len(mod_values) == 1,
        }
        result.append(row)
    return result


def require_closed_identity(scan: Mapping[str, Any]) -> None:
    rows = scan["tuples"]
    require(
        len(rows) == 18
        and scan["archiveCount"] == 82
        and scan["externalModCount"] == 81
        and scan["embeddedRootGoModCount"] == 1
        and sum(row["declarationCount"] for row in rows) == 18
        and sum(row["moduleZipH1WitnessCount"] for row in rows) == 18
        and sum(row["goModH1WitnessCount"] for row in rows) == 25
        and all(
            row["declarationComplete"]
            and row["identityPairComplete"]
            and not row["moduleZipH1Conflict"]
            and not row["goModH1Conflict"]
            for row in rows
        )
        and scan["compactIdentitySha256"] == COMPACT_IDENTITY_SHA256
        and scan["fullWitnessSha256"] == FULL_WITNESS_SHA256,
        "E_IDENTITY_CLOSURE",
    )


def request_set(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        tuple_digest = sha256_bytes(
            f"{row['module']}\n{row['version']}\n".encode("utf-8")
        )
        for kind, expected_h1, maximum_bytes in (
            ("mod", row["goModH1Values"][0], 1024 * 1024),
            ("zip", row["moduleZipH1Values"][0], 16 * 1024 * 1024),
        ):
            result.append(
                {
                    "requestOrdinal": len(result) + 1,
                    "tupleOrder": row["tupleOrder"],
                    "module": row["module"],
                    "version": row["version"],
                    "selectedByGraphAlgorithm":
                        row["selectedByGraphAlgorithm"],
                    "resourceKind": kind,
                    "method": "GET",
                    "host": "proxy.golang.org",
                    "url": (
                        f"https://proxy.golang.org/{row['module']}/"
                        f"@v/{row['version']}.{kind}"
                    ),
                    "expectedH1": expected_h1,
                    "maximumResponseBytes": maximum_bytes,
                    "acceptedFileName": (
                        f"{row['tupleOrder']:03d}-"
                        f"{tuple_digest[:20]}.{kind}"
                    ),
                    "authenticationRequired": False,
                    "networkAuthorized": False,
                    "acquisitionAuthorized": False,
                }
            )
    require(
        len(result) == 36
        and [row["requestOrdinal"] for row in result]
        == list(range(1, 37)),
        "E_REQUEST_SET",
    )
    return result


def validate_semantic_decision(
    document: Mapping[str, Any],
    package_raw: Mapping[str, bytes],
) -> Mapping[str, Any]:
    require(
        type(document) is dict
        and set(document)
        == {
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
        },
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
            "sha256": sha256_bytes(canonical_json_bytes(without)),
        },
        "E_DECISION_CONTENT",
    )
    require(
        document.get("documentType")
        == (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave6"
        )
        and document.get("schemaVersion") == "1.0"
        and document.get("checkerId") == CHECKER_ID
        and document.get("decisionId") == DECISION_ID
        and document.get("date") == "2026-07-25"
        and document.get("status")
        == (
            "wave6_exact_18_frontier_identity_classified_"
            "18_complete_0_blocked_acquisition_ready_not_authorized"
        )
        and document.get("result")
        == (
            "exact_18_version_vertices_0_selected_18_nonselected_"
            "18_complete_h1_pairs_acquisition_ready_not_authorized"
        )
        and document.get("verificationOnly") is True
        and document.get("recordModeExposed") is False,
        "E_DECISION_SCHEMA",
    )

    predecessors = document.get("predecessorBindings")
    wave6 = (
        predecessors.get("wave6Candidate")
        if type(predecessors) is dict else None
    )
    combined = (
        predecessors.get("combinedFixedPointV4")
        if type(predecessors) is dict else None
    )
    require(
        type(wave6) is dict
        and wave6
        == {
            "checkerPath": WAVE6_CHECKER_PATH,
            "checkerRawSha256": WAVE6_CHECKER_RAW_SHA256,
            "testsPath": WAVE6_TESTS_PATH,
            "testsRawSha256": WAVE6_TESTS_RAW_SHA256,
            "contentSha256": WAVE6_CANDIDATE_CONTENT_SHA256,
            "tupleCount": 18,
        }
        and type(combined) is dict
        and combined
        == {
            "contentSha256": COMBINED_V4_CONTENT_SHA256,
            "combinedInputSetSha256": COMBINED_INPUT_SET_SHA256,
            "sourceBindingsSha256": COMBINED_SOURCE_BINDINGS_SHA256,
            "graphSha256": COMBINED_GRAPH_SHA256,
            "frontierSha256": COMBINED_FRONTIER_SHA256,
            "fixedPointReached": False,
            "retainedSnapshotBoundary": {
                "completionAppliesToRetainedSnapshot": True,
                "currentPathIdentityGuaranteedThroughManifestPublication":
                    False,
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                    False,
            },
        },
        "E_DECISION_LINEAGE",
    )

    held = document.get("heldSourceInputSet")
    require(
        type(held) is dict
        and all(
            type(held.get(key)) is int
            for key in (
                "sourceBindingCount",
                "archiveCount",
                "externalModCount",
                "embeddedRootGoModCount",
            )
        )
        and held.get("sourceBindingCount") == 163
        and held.get("sourceBindingsSha256")
        == COMBINED_SOURCE_BINDINGS_SHA256
        and held.get("archiveCount") == 82
        and held.get("externalModCount") == 81
        and held.get("embeddedRootGoModCount") == 1
        and held.get("allInputsReadTwiceBeforeUse") is True
        and held.get("allInputsHeldThroughFinalBarrier") is True,
        "E_DECISION_LINEAGE",
    )

    identity = document.get("identityResolution")
    rows = identity.get("tuples") if type(identity) is dict else None
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
        type(identity) is dict
        and all(
            type(identity.get(key)) is int
            for key in identity_count_keys
        )
        and identity.get("tupleCount") == 18
        and identity.get("graphSelectedTupleCount") == 0
        and identity.get("versionSpecificNonSelectedTupleCount") == 18
        and identity.get("parentDeclarationCount") == 18
        and identity.get("moduleZipH1WitnessCount") == 18
        and identity.get("goModH1WitnessCount") == 25
        and identity.get("completeIdentityPairCount") == 18
        and identity.get("blockedTupleCount") == 0
        and identity.get("conflictingIdentityCount") == 0
        and identity.get("compactIdentitySha256")
        == COMPACT_IDENTITY_SHA256
        and identity.get("fullWitnessSha256") == FULL_WITNESS_SHA256
        and type(rows) is list
        and len(rows) == 18,
        "E_DECISION_IDENTITY",
    )
    for order, (row, expected) in enumerate(
        zip(rows, EXPECTED_IDENTITY_H1),
        1,
    ):
        module, version, mod_h1, zip_h1 = expected
        require(
            type(row) is dict
            and type(row.get("tupleOrder")) is int
            and row.get("tupleOrder") == order
            and row.get("module") == module
            and row.get("version") == version
            and row.get("selectedByGraphAlgorithm") is False
            and row.get("goModH1") == mod_h1
            and row.get("moduleZipH1") == zip_h1
            and row.get("parentDeclarationComplete") is True
            and row.get("identityPairComplete") is True
            and row.get("identityConflict") is False
            and row.get("acquisitionReady") is True
            and row.get("acquisitionAuthorized") is False,
            "E_DECISION_IDENTITY",
        )

    preparation = document.get("sourceAcquisitionPreparation")
    requests = (
        preparation.get("requestSet")
        if type(preparation) is dict else None
    )
    expected_requests: list[dict[str, Any]] = []
    for order, (module, version, mod_h1, zip_h1) in enumerate(
        EXPECTED_IDENTITY_H1,
        1,
    ):
        tuple_digest = sha256_bytes(
            f"{module}\n{version}\n".encode("utf-8")
        )
        for kind, h1, maximum in (
            ("mod", mod_h1, 1_048_576),
            ("zip", zip_h1, 16_777_216),
        ):
            expected_requests.append(
                {
                    "requestOrdinal": len(expected_requests) + 1,
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
                    "expectedH1": h1,
                    "maximumResponseBytes": maximum,
                    "acceptedFileName":
                        f"{order:03d}-{tuple_digest[:20]}.{kind}",
                    "authenticationRequired": False,
                    "networkAuthorized": False,
                    "acquisitionAuthorized": False,
                }
            )
    request_types_exact = (
        type(requests) is list
        and all(
            type(row) is dict
            and type(row.get("requestOrdinal")) is int
            and type(row.get("tupleOrder")) is int
            and type(row.get("maximumResponseBytes")) is int
            and row.get("selectedByGraphAlgorithm") is False
            and row.get("authenticationRequired") is False
            and row.get("networkAuthorized") is False
            and row.get("acquisitionAuthorized") is False
            for row in requests
        )
    )
    require(
        type(preparation) is dict
        and preparation.get("acquisitionReady") is True
        and preparation.get("acquisitionAuthorizedByThisDecision") is False
        and preparation.get("requestCount") == 36
        and preparation.get("requestOrder")
        == "tuple_order_ascending_mod_then_zip"
        and request_types_exact
        and requests == expected_requests
        and preparation.get("requestSetCanonicalSha256")
        == sha256_bytes(digest_json_bytes(expected_requests))
        and preparation.get("claimPath") == WAVE6_CLAIM_PATH
        and preparation.get("stagingDirectoryPrefix")
        == WAVE6_STAGING_PREFIX
        and preparation.get("acceptedDirectoryPath")
        == WAVE6_ACCEPTED_PATH,
        "E_DECISION_REQUEST",
    )

    counters = document.get("operationCounters")
    expected_counters = {
        "combinedV4CandidateInvocationCount": 1,
        "predecessorFullSourceReconstructionCount": 4,
        "directV4FullSourceReconstructionCount": 2,
        "totalFullSourceReconstructionCount": 6,
        "predecessorV3GraphArchiveOpenCount": 236,
        "currentV4GraphArchiveOpenCount": 164,
        "totalV4GraphArchiveOpenCount": 400,
        "identityWitnessScanCount": 2,
        "identityWitnessArchiveOpenCount": 164,
        "overallDecisionExecutionArchiveOpenCount": 564,
        "networkOperationCount": 0,
        "subprocessCount": 0,
        "authenticationOperationCount": 0,
        "dependencySourceExecutionCount": 0,
        "archiveExtractionCount": 0,
        "fileWriteCount": 0,
    }
    require(
        type(counters) is dict
        and set(counters) == set(expected_counters)
        and all(
            type(counters[key]) is int
            and counters[key] == expected_counters[key]
            for key in expected_counters
        ),
        "E_DECISION_COUNTERS",
    )
    expected_closure = {
        "wave6IdentityResolved": True,
        "wave6AcquisitionReady": True,
        "wave6AcquisitionComplete": False,
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
        type(closure) is dict
        and set(closure) == set(expected_closure)
        and all(
            closure[key] is expected_closure[key]
            for key in expected_closure
        ),
        "E_DECISION_CLOSURE",
    )
    authority = document.get("authority")
    require(
        type(authority) is dict
        and set(authority) == set(EXPECTED_DECISION_AUTHORITY)
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
            "rawSha256": EXPECTED_READER_RAW_SHA256,
        }
        and document.get("toolBindings")
        == expected_tool_bindings(package_raw)
        and document.get("nonClaims") == list(EXPECTED_NON_CLAIMS),
        "E_DECISION_BINDINGS",
    )
    require(
        document.get("nextAction")
        == (
            "prepare_separate_one_use_36_resource_wave6_source_"
            "acquisition_permit_checker_runner_and_tests"
        ),
        "E_DECISION_CLOSURE",
    )
    return document


def validate_source_bindings(
    candidate: Mapping[str, Any],
) -> list[dict[str, Any]]:
    input_set = candidate["inputSet"]
    bindings = input_set["sourceBindings"]
    require(
        type(bindings) is list
        and len(bindings) == 163
        and bindings[0]["kind"] == "root_zip"
        and sum(row["kind"] == "mod" for row in bindings) == 81
        and sum(row["kind"] == "zip" for row in bindings) == 81
        and len({row["path"] for row in bindings}) == 163
        and sha256_bytes(digest_json_bytes(bindings))
        == COMBINED_SOURCE_BINDINGS_SHA256
        and input_set["combinedInputSetSha256"]
        == COMBINED_INPUT_SET_SHA256,
        "E_SOURCE_BINDING",
    )
    for row in bindings:
        require(
            set(row)
            == {
                "kind",
                "module",
                "path",
                "rawSha256",
                "tupleId",
                "tupleOrder",
                "version",
                "wave",
            }
            and type(row["path"]) is str
            and len(row["rawSha256"]) == 64,
            "E_SOURCE_BINDING",
        )
    return [dict(row) for row in bindings]


def reconstruct_wave6_candidate(
    *,
    wave6: types.ModuleType,
    combined_candidate: Mapping[str, Any],
    wave_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild the exact pinned Wave6 candidate without a second graph run."""

    require(
        combined_candidate["contentBinding"]["sha256"]
        == COMBINED_V4_CONTENT_SHA256,
        "E_WAVE6_CANDIDATE_CONTENT",
    )
    body = {
        "documentType": (
            "aetherlink.g2-pion-rung3-wave6-frontier-"
            "identity-candidate"
        ),
        "schemaVersion": "1.0",
        "checkerId": wave6.CHECKER_ID,
        "status": (
            "exact_18_wave6_frontier_identity_candidates_"
            "prepared_without_authority"
        ),
        "result": (
            "externally_pinned_v4_frontier_projected_"
            "to_wave6_identity_candidates"
        ),
        "verificationOnly": True,
        "recordModeExposed": False,
        "producerPackageBindings": [
            {
                "role": "combined_fixed_point_v4_checker",
                "path": wave6.V4_CHECKER_PATH,
                "rawSha256": wave6.V4_CHECKER_RAW_SHA256,
                "normalizedSha256":
                    wave6.V4_CHECKER_NORMALIZED_SHA256,
            },
            {
                "role": "combined_fixed_point_v4_tests",
                "path": wave6.V4_TESTS_PATH,
                "rawSha256": wave6.V4_TESTS_RAW_SHA256,
            },
        ],
        "sourceCandidateBinding": {
            "contentSha256": wave6.V4_CANDIDATE_CONTENT_SHA256,
            "combinedInputSetSha256": wave6.V4_INPUT_SET_SHA256,
            "sourceBindingsSha256":
                wave6.V4_SOURCE_BINDINGS_SHA256,
            "graphSha256": wave6.V4_GRAPH_SHA256,
            "moduleGraphAndFrontierSha256":
                wave6.V4_MODULE_GRAPH_AND_FRONTIER_SHA256,
            "exactFrontierCanonicalSha256": wave6.V4_FRONTIER_SHA256,
            "route": "next_wave_required",
            "newTupleCount": 18,
            "fixedPointReached": False,
            "retainedSnapshotBoundary": {
                "completionAppliesToRetainedSnapshot": True,
                "currentPathIdentityGuaranteedThroughManifestPublication":
                    False,
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                    False,
            },
        },
        "wave": {
            "waveId": (
                "g2-pion-ice-v4.3.0-dependency-source-wave6-"
                "candidate-v1"
            ),
            "tupleCount": 18,
            "graphSelectedTupleCount": 0,
            "versionSpecificNonSelectedTupleCount": 18,
            "identityResolvedTupleCount": 0,
            "acquisitionReadyTupleCount": 0,
            "tuples": [dict(row) for row in wave_rows],
        },
        "nextAction": (
            "prepare_separate_wave6_identity_and_acquisition_"
            "decision"
        ),
        "operationCounters": {
            "v4CandidateInvocationCount": 1,
            "predecessorFullSourceReconstructionCount":
                wave6.V4_PREDECESSOR_RECONSTRUCTION_COUNT,
            "directV4FullSourceReconstructionCount":
                wave6.V4_DIRECT_RECONSTRUCTION_COUNT,
            "totalFullSourceReconstructionCount":
                wave6.V4_TOTAL_RECONSTRUCTION_COUNT,
            "predecessorArchiveOpenCount":
                wave6.V4_PREDECESSOR_ARCHIVE_OPEN_COUNT,
            "directV4ArchiveOpenCount":
                wave6.V4_DIRECT_ARCHIVE_OPEN_COUNT,
            "totalArchiveOpenCount":
                wave6.V4_TOTAL_ARCHIVE_OPEN_COUNT,
            "inheritedFullSourceReconstructionCount":
                wave6.V4_TOTAL_RECONSTRUCTION_COUNT,
            "inheritedArchiveOpenCount":
                wave6.V4_TOTAL_ARCHIVE_OPEN_COUNT,
            "networkOperationCount": 0,
            "subprocessCount": 0,
            "dependencySourceExecutionCount": 0,
            "archiveExtractionCount": 0,
            "fileWriteCount": 0,
        },
        "closure": {
            "dependencyFixedPointReached": False,
            "dependencyClosureComplete": False,
            "wave6IdentityResolved": False,
            "wave6AcquisitionReady": False,
            "semanticClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "releaseReady": False,
        },
        "authority": {
            "decisionAuthorityGranted": False,
            "executionAuthorityGranted": False,
            "identityResolutionAuthorityGranted": False,
            "acquisitionAuthorityGranted": False,
            "publicationAuthorityGranted": False,
            "networkAuthorized": False,
            "dependencySourceExecutionAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "subprocessAuthorized": False,
            "fileWriteAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "passwordRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
            "userActionRequired": False,
        },
        "nonClaims": {
            "frontierIdentityResolved": False,
            "sourceAcquisitionAuthorized": False,
            "dependencyClosureComplete": False,
            "fixedPointReached": False,
            "candidateOrLibrarySelected": False,
            "releaseReady": False,
        },
    }
    projected = wave6.content_bound(
        body,
        "wave6_candidate_without_contentBinding",
    )
    binding = projected.get("contentBinding")
    without = dict(projected)
    without.pop("contentBinding", None)
    require(
        type(binding) is dict
        and binding.get("sha256") == WAVE6_CANDIDATE_CONTENT_SHA256
        and sha256_bytes(wave6.canonical_json_bytes(without))
        == WAVE6_CANDIDATE_CONTENT_SHA256,
        "E_WAVE6_CANDIDATE_CONTENT",
    )
    return projected


def expected_payload(
    *,
    package_raw: Mapping[str, bytes],
    wave6_candidate: Mapping[str, Any],
    wave_rows: Sequence[Mapping[str, Any]],
    source_bindings: Sequence[Mapping[str, Any]],
    scan: Mapping[str, Any],
) -> dict[str, Any]:
    rows = scan["tuples"]
    requests = request_set(rows)
    blocked_count = sum(
        not (
            row["declarationComplete"]
            and row["identityPairComplete"]
        )
        for row in rows
    )
    conflict_count = sum(
        row["moduleZipH1Conflict"] or row["goModH1Conflict"]
        for row in rows
    )
    acquisition_ready = blocked_count == 0 and conflict_count == 0
    decision_rows = [
        {
            "tupleOrder": row["tupleOrder"],
            "module": row["module"],
            "version": row["version"],
            "selectedByGraphAlgorithm":
                row["selectedByGraphAlgorithm"],
            "parentDeclarationCount": row["declarationCount"],
            "moduleZipH1WitnessCount":
                row["moduleZipH1WitnessCount"],
            "goModH1WitnessCount": row["goModH1WitnessCount"],
            "moduleZipH1": row["moduleZipH1Values"][0],
            "goModH1": row["goModH1Values"][0],
            "parentDeclarationComplete":
                row["declarationComplete"],
            "identityPairComplete": row["identityPairComplete"],
            "identityConflict": (
                row["moduleZipH1Conflict"]
                or row["goModH1Conflict"]
            ),
            "acquisitionReady": True,
            "acquisitionAuthorized": False,
        }
        for row in rows
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave6"
        ),
        "schemaVersion": "1.0",
        "checkerId": CHECKER_ID,
        "decisionId": DECISION_ID,
        "date": "2026-07-25",
        "status": (
            f"wave6_exact_{len(rows)}_frontier_identity_classified_"
            f"{len(rows) - blocked_count}_complete_{blocked_count}_blocked_"
            + (
                "acquisition_ready_not_authorized"
                if acquisition_ready
                else "acquisition_blocked_not_authorized"
            )
        ),
        "result": (
            f"exact_{len(rows)}_version_vertices_"
            f"{sum(row['selectedByGraphAlgorithm'] for row in rows)}_selected_"
            f"{sum(not row['selectedByGraphAlgorithm'] for row in rows)}_"
            f"nonselected_{len(rows) - blocked_count}_complete_h1_pairs_"
            + (
                "acquisition_ready_not_authorized"
                if acquisition_ready
                else "acquisition_blocked_not_authorized"
            )
        ),
        "verificationOnly": True,
        "recordModeExposed": False,
        "predecessorBindings": {
            "wave6Candidate": {
                "checkerPath": WAVE6_CHECKER_PATH,
                "checkerRawSha256": WAVE6_CHECKER_RAW_SHA256,
                "testsPath": WAVE6_TESTS_PATH,
                "testsRawSha256": WAVE6_TESTS_RAW_SHA256,
                "contentSha256":
                    wave6_candidate["contentBinding"]["sha256"],
                "tupleCount": 18,
            },
            "combinedFixedPointV4": {
                "contentSha256": COMBINED_V4_CONTENT_SHA256,
                "combinedInputSetSha256": COMBINED_INPUT_SET_SHA256,
                "sourceBindingsSha256":
                    COMBINED_SOURCE_BINDINGS_SHA256,
                "graphSha256": COMBINED_GRAPH_SHA256,
                "frontierSha256": COMBINED_FRONTIER_SHA256,
                "fixedPointReached": False,
                "retainedSnapshotBoundary": {
                    "completionAppliesToRetainedSnapshot": True,
                    "currentPathIdentityGuaranteedThroughManifestPublication":
                        False,
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                        False,
                },
            },
        },
        "heldSourceInputSet": {
            "sourceBindingCount": len(source_bindings),
            "sourceBindingsSha256": sha256_bytes(
                digest_json_bytes(source_bindings)
            ),
            "archiveCount": scan["archiveCount"],
            "externalModCount": scan["externalModCount"],
            "embeddedRootGoModCount": scan["embeddedRootGoModCount"],
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
            "blockedTupleCount": blocked_count,
            "conflictingIdentityCount": conflict_count,
            "compactIdentityCanonicalization": (
                "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
            ),
            "compactIdentitySha256": scan["compactIdentitySha256"],
            "fullWitnessCanonicalization": (
                "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
            ),
            "fullWitnessSha256": scan["fullWitnessSha256"],
            "fullWitnessMaterializedInDecision": False,
            "fullWitnessReproducibleByPinnedChecker": True,
            "tuples": decision_rows,
        },
        "sourceAcquisitionPreparation": {
            "acquisitionReady": acquisition_ready,
            "acquisitionAuthorizedByThisDecision": False,
            "separateOneUseExecutionPermitRequired": True,
            "requestCount": len(requests),
            "requestOrder": "tuple_order_ascending_mod_then_zip",
            "requestSet": requests,
            "requestSetCanonicalSha256": sha256_bytes(
                digest_json_bytes(requests)
            ),
            "proxyHost": "proxy.golang.org",
            "modulePathEncoding": (
                "current_wave6_lowercase_ascii_direct_proxy_path"
            ),
            "claimPath": WAVE6_CLAIM_PATH,
            "stagingDirectoryPrefix": WAVE6_STAGING_PREFIX,
            "acceptedDirectoryPath": WAVE6_ACCEPTED_PATH,
            "oneUseNoOverwriteRequired": True,
            "atomicNoReplacePromotionRequired": True,
            "independentPostConsumptionReadbackRequired": True,
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW_SHA256,
        },
        "toolBindings": expected_tool_bindings(package_raw),
        "operationCounters": {
            "combinedV4CandidateInvocationCount": 1,
            "predecessorFullSourceReconstructionCount": 4,
            "directV4FullSourceReconstructionCount": 2,
            "totalFullSourceReconstructionCount": 6,
            "predecessorV3GraphArchiveOpenCount": 236,
            "currentV4GraphArchiveOpenCount": 164,
            "totalV4GraphArchiveOpenCount": 400,
            "identityWitnessScanCount": 2,
            "identityWitnessArchiveOpenCount": 164,
            "overallDecisionExecutionArchiveOpenCount": 564,
            "networkOperationCount": 0,
            "subprocessCount": 0,
            "authenticationOperationCount": 0,
            "dependencySourceExecutionCount": 0,
            "archiveExtractionCount": 0,
            "fileWriteCount": 0,
        },
        "closure": {
            "wave6IdentityResolved": acquisition_ready,
            "wave6AcquisitionReady": acquisition_ready,
            "wave6AcquisitionComplete": False,
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
            (
                "prepare_separate_one_use_36_resource_wave6_source_"
                "acquisition_permit_checker_runner_and_tests"
            )
            if acquisition_ready
            else "resolve_blocked_wave6_identity_gap_without_acquisition"
        ),
    }


def evaluate(
    root: Path = ROOT,
    *,
    verify_disk: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    require_isolated_interpreter()
    package_specs = [
        (THIS_CHECKER_PATH, None, MAXIMUM_CODE_BYTES),
        (THIS_TESTS_PATH, None, MAXIMUM_CODE_BYTES),
        (
            READER_PATH,
            EXPECTED_READER_RAW_SHA256,
            MAXIMUM_CODE_BYTES,
        ),
        (
            WAVE6_CHECKER_PATH,
            WAVE6_CHECKER_RAW_SHA256,
            MAXIMUM_CODE_BYTES,
        ),
        (
            WAVE6_TESTS_PATH,
            WAVE6_TESTS_RAW_SHA256,
            MAXIMUM_CODE_BYTES,
        ),
    ]
    if verify_disk:
        package_specs.append(
            (DECISION_PATH, None, MAXIMUM_DECISION_BYTES)
        )
    with ExitStack() as stack:
        namespace_held = stack.enter_context(HeldNamespace(root))
        package_held = {
            path: stack.enter_context(
                PinnedFile(
                    root,
                    path,
                    expected_sha256=expected,
                    maximum_bytes=maximum,
                )
            )
            for path, expected, maximum in package_specs
        }
        wave6 = load_wave6_checker(package_held[WAVE6_CHECKER_PATH])
        v4_held = stack.enter_context(
            wave6.BootstrapPinnedCodeFile(
                root,
                wave6.V4_CHECKER_PATH,
                wave6.V4_CHECKER_RAW_SHA256,
            )
        )
        v4 = wave6.load_v4_checker(v4_held)
        v4_tests_held = stack.enter_context(
            v4.PinnedCodeFile(
                root,
                wave6.V4_TESTS_PATH,
                wave6.V4_TESTS_RAW_SHA256,
            )
        )
        held: list[Any] = [
            namespace_held,
            *package_held.values(),
            v4_held,
            v4_tests_held,
        ]
        identity_barrier(root, held)
        candidate = v4.generate_candidate(root)
        identity_barrier(root, held)
        frontier = wave6.validate_v4_candidate(candidate)
        wave_rows = wave6.wave6_rows(frontier)
        wave6_candidate = reconstruct_wave6_candidate(
            wave6=wave6,
            combined_candidate=candidate,
            wave_rows=wave_rows,
        )
        source_bindings = validate_source_bindings(candidate)

        v1_held = stack.enter_context(
            v4.PinnedCodeFile(
                root,
                v4.V1_CHECKER_PATH,
                v4.V1_CHECKER_RAW_SHA256,
            )
        )
        v1 = v4.load_v1_checker(v1_held)
        provider_held = stack.enter_context(v1.PinnedRunnerFile(root))
        runner = v1.load_pinned_runner(provider_held)
        source_held = stack.enter_context(
            runner.HeldInputSet(
                root,
                [
                    {
                        "path": row["path"],
                        "rawSha256": row["rawSha256"],
                        "maximumBytes": MAXIMUM_SOURCE_BYTES,
                        "ownerOnly": False,
                    }
                    for row in source_bindings
                ],
            )
        )
        held.extend((v1_held, provider_held, source_held))
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
            digest_json_bytes(first_scan) == digest_json_bytes(second_scan),
            "E_REPRODUCTION",
        )
        require_closed_identity(first_scan)
        identity_barrier(root, held)
        package_raw = {
            path: item.raw for path, item in package_held.items()
        }
        expected = content_bound(
            expected_payload(
                package_raw=package_raw,
                wave6_candidate=wave6_candidate,
                wave_rows=wave_rows,
                source_bindings=source_bindings,
                scan=first_scan,
            )
        )
        if verify_disk:
            decision_raw = package_raw[DECISION_PATH]
            validate_materialized_decision(
                decision_raw,
                expected,
                package_raw,
            )
        identity_barrier(root, held)
    return expected, {
        "documentType": "aetherlink.wave6-identity-acquisition-decision-check",
        "schemaVersion": "1.0",
        "status": "validated_18_of_18_acquisition_ready_not_authorized",
        "validationPassed": True,
        "tupleCount": 18,
        "parentDeclarationCount": 18,
        "moduleZipH1WitnessCount": 18,
        "goModH1WitnessCount": 25,
        "completeIdentityPairCount": 18,
        "blockedTupleCount": 0,
        "acquisitionReady": True,
        "acquisitionAuthorized": False,
        "networkUsed": False,
        "fileWriteCount": 0,
        "sourceAcquired": False,
        "sourceExecutionUsed": False,
        "subprocessCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def error_document(code: str) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.wave6-identity-acquisition-decision-error",
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
            canonical_json_bytes(expected if args.print_expected else summary)
        )
        return 0
    except DecisionFailure as error:
        sys.stdout.buffer.write(canonical_json_bytes(error_document(error.code)))
        return 1
    except Exception:
        sys.stdout.buffer.write(canonical_json_bytes(error_document("E_INTERNAL")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
