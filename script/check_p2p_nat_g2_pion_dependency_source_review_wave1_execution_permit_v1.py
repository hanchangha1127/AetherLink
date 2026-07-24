#!/usr/bin/env python3
"""Preflight the one-use G2 dependency source-review wave-one permit.

The checker is deliberately preparation-only.  It byte-binds the already
recorded decision, its predecessor chain, the root archive, all 38 retained
dependency resources, and the finalized runner/checker tools.  It does not
inspect archive members, execute reviewed source, write files, use the
network, or consume the permit.
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
            "execution-permit checker requires unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Callable, Mapping, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
V1_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v1.json"
)
V2_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v2.json"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v3.json"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-decision-v1.json"
)
DECISION_RAW_SHA256 = (
    "071883a40adec734d87362a5781033fd18f83299177e886a92a04a0c3944dff7"
)
DECISION_CONTENT_SHA256 = (
    "bbad9b7e38554c841b91b5273f90c2e4f2450ab64c42dfc5cc1ed1e07d15d547"
)
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-decision-v1"
)
V1_RECOVERY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-recovery-decision-v1.json"
)
V1_RECOVERY_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "recovery-decision-v1"
)
V1_RECOVERY_DECISION_RAW_SHA256 = (
    "1140a718344017895557c304ef24658af325a98b9334606eeb38e85e3e603272"
)
V1_RECOVERY_DECISION_CONTENT_SHA256 = (
    "3d050549c9632dd2d2f57ed329b47cf4526db981e490015017dbda357c2275e3"
)
RECOVERY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-recovery-decision-v2.json"
)
RECOVERY_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "recovery-decision-v2"
)
RECOVERY_DECISION_RAW_SHA256 = (
    "07b695c05dd5e26fff47ed97c7a41992325709c6ed2736543889971250543c28"
)
RECOVERY_DECISION_CONTENT_SHA256 = (
    "b2f2d102b4e5b9f5debed8b72b3f19098a2228e39d3a2e0b1ac980c57d6a4bd1"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_source_review_wave1_decision_v1.py"
)
DECISION_CHECKER_RAW_SHA256 = (
    "a33d812fc704d54d57381795b45e7eff62e2c699e3ef01ddf052f735d181cdf0"
)
DECISION_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_source_review_wave1_decision_v1.py"
)
DECISION_TEST_RAW_SHA256 = (
    "260610f0280c678518cac463f6f66a0749adc02023c2c19eff6fa658102dc1d9"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_execution_permit_v1.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_execution_permit_v1.py"
)
RUNNER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
RUNNER_TEST_PATH = (
    "script/test_run_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_once.py"
)
READBACK_RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_readback_v1.py"
)
READBACK_RECORDER_TEST_PATH = (
    "script/test_record_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_readback_v1.py"
)
READBACK_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_readback_v1.py"
)
READBACK_CHECKER_TEST_PATH = (
    "script/test_check_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_readback_v1.py"
)
RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v3.json"
)
DEPENDENCY_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v3/accepted"
)
ROOT_ARCHIVE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
ROOT_ARCHIVE_RAW_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
V1_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v1.claim"
)
V1_RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-result-v1.json"
)
V1_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-failure-v1.json"
)
V1_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-manifest-v1.json"
)
V1_READBACK_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-readback-v1.claim"
)
V1_READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-v1.json"
)
V1_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-manifest-v1.json"
)
V1_PERMIT_RAW_SHA256 = (
    "2f1f3e7a50ad7d84ff392638e91e33a62a2f0b386c7796851d65fcfc23d389ed"
)
V1_PERMIT_CONTENT_SHA256 = (
    "ea6b8cd29e1f784b2a152fe5d2fe3695b3ea5119dd8be5d2aa80994ab60a0732"
)
V1_CLAIM_RAW_SHA256 = (
    "34bde07fdc7fd9043514fb247ab85fe1166b76a02fd8b9fc56b5c72278f78519"
)
V1_CLAIM_CONTENT_SHA256 = (
    "43b9db4e10c367ca3aeaffabeed1a56f0557b314381b8ec42b1ae76207eb0228"
)
V1_FAILURE_RAW_SHA256 = (
    "00d0a305d21d60f4cd058107d7e39c0c85724a66baa359ae46da8b4ac0ab7031"
)
V1_FAILURE_CONTENT_SHA256 = (
    "be948d4430c0e3bd22648154792ddf622d6cf6ccc1eb260fad466bdbccc89536"
)
V1_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "execution-permit-v1"
)
V1_REVIEW_ID = "g2-pion-ice-v4.3.0-dependency-source-review-wave1-v1"

V2_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v2.claim"
)
V2_RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-result-v2.json"
)
V2_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-failure-v2.json"
)
V2_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-manifest-v2.json"
)
V2_READBACK_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-readback-v2.claim"
)
V2_READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-v2.json"
)
V2_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-manifest-v2.json"
)
V2_PERMIT_RAW_SHA256 = (
    "88d1a05f61e77305e6dd91827da8901a9cd44ad8f85b27291dbdfb49e22f04f8"
)
V2_PERMIT_CONTENT_SHA256 = (
    "8ae8ae53d03fef67d0d84a5c1261b090f2866f36cce8c5983e8c06d45f016613"
)
V2_CLAIM_RAW_SHA256 = (
    "9379ca75f17ce5701a82b7b8d9edf8bbd8f09722925cbb15570da8983208d250"
)
V2_CLAIM_CONTENT_SHA256 = (
    "f6f596534c5b4bdaba6631b1cedfd7dafc6a398881665c8d9e02946b7277f86e"
)
V2_FAILURE_RAW_SHA256 = (
    "3aa2f172c805cda66935be8b9d96167eef23d3ac1eeeea9259300f15eee9435b"
)
V2_FAILURE_CONTENT_SHA256 = (
    "c4ce7c1cf17ba952ffbb60377f02552d51f9b2a38df96b7bb23d7b943f35ae7f"
)
V2_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "execution-permit-v2"
)
V2_REVIEW_ID = "g2-pion-ice-v4.3.0-dependency-source-review-wave1-v2"

CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v3.claim"
)
STAGING_DIRECTORY_PREFIX = ".wave-1-review-v3-staging-"
RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-result-v3.json"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-failure-v3.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-manifest-v3.json"
)
READBACK_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-readback-v3.claim"
)
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-v3.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-manifest-v3.json"
)
PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "execution-permit-v3"
)
REVIEW_ID = "g2-pion-ice-v4.3.0-dependency-source-review-wave1-v3"
EXPECTED_STATUS = (
    "dependency_source_review_wave1_execution_authorized_not_consumed"
)
EXPECTED_RESULT = (
    "bounded_wp4_graph_frontier_review_wave1_v3_authorized_once_not_executed"
)
EXPECTED_NEXT_ACTION = "execute_bound_dependency_source_review_wave1_once"
ORDERED_SOURCE_SET_SHA256 = (
    "2b0176d6d2b800c9a2abd34bf06279403e6f008bd3475ff45970abf11e843246"
)

MAXIMUM_JSON_BYTES = 2_097_152
MAXIMUM_TOOL_BYTES = 4_194_304
MAXIMUM_PLAN_BYTES = 262_144
MAXIMUM_ROOT_ARCHIVE_BYTES = 16_777_216
MAXIMUM_RESOURCE_BYTES = 16_777_216
MAXIMUM_TOTAL_READ_BYTES = 268_435_456


@dataclass(frozen=True)
class FixedBinding:
    path: str
    raw_sha256: str
    maximum_bytes: int
    owner_only: bool = False


FIXED_BINDINGS = (
    FixedBinding(
        f"{BASE}/implementation-or-dependency-review-decision-v1.json",
        "6a14603c02c9aa9d9d78377b1c38a9f0d47391c0ac1ff8eea1769198ddc13ff8",
        MAXIMUM_JSON_BYTES,
    ),
    FixedBinding(
        f"{BASE}/implementation-or-dependency-review-decision-v1/"
        "implementation/staged-fixed-point-source-closure.md",
        "22d7cfbc2db9e34fab641167d227e650cb490dcfd9a402a4dff86e1f967234bc",
        MAXIMUM_PLAN_BYTES,
    ),
    FixedBinding(
        f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json",
        "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e",
        MAXIMUM_JSON_BYTES,
    ),
    FixedBinding(
        RECEIPT_PATH,
        "10d63291813d66c1d7c9edaf7108842113bccbc2a84f799ddafe3f02a820f3b3",
        MAXIMUM_JSON_BYTES,
        True,
    ),
    FixedBinding(
        f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v3.json",
        "9763dd83e46a57404bbd3d4c18ecf2f151bdf4e1c17ba3131e4b726b32a54e6b",
        MAXIMUM_JSON_BYTES,
        True,
    ),
    FixedBinding(
        f"{BASE}/bounded-dependency-source-acquisition-wave1-readback-v1.json",
        "63c7db8fce4a1c5c26dba84c22be9ea79afda95afb76506a10457e1ac9e910e0",
        MAXIMUM_JSON_BYTES,
        True,
    ),
    FixedBinding(
        f"{BASE}/bounded-dependency-source-acquisition-wave1-"
        "readback-manifest-v1.json",
        "a62e1cc1508a127fa1f5cb4a5009cf7ddeae87ef40172d1c7327c51f8cbc3b96",
        MAXIMUM_JSON_BYTES,
        True,
    ),
    FixedBinding(
        f"{BASE}/bounded-dependency-source-acquisition-wave1-"
        "readback-post-verification-decision-v3.json",
        "9ad7b632782131c9ac9c327fc40942dab08eb3e6b308f582dbee1650ba8f76ba",
        MAXIMUM_JSON_BYTES,
    ),
    FixedBinding(
        "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3_post_verify_v3.py",
        "27b7ebbac46cd0e4a08b1dd87feabe1e1cd90c79d0c3a0ee1d5b5366f4a0d895",
        MAXIMUM_TOOL_BYTES,
    ),
    FixedBinding(
        "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3_post_verify_v3.py",
        "5bdda8fae3229907b2c224a81a217a62c1899917fb3f64781add39101806a786",
        MAXIMUM_TOOL_BYTES,
    ),
)


class PermitError(RuntimeError):
    """A fail-closed permit validation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PermitError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def reject_float(_: str) -> Any:
    raise PermitError("floating-point JSON values are forbidden")


def reject_constant(_: str) -> Any:
    raise PermitError("non-finite JSON values are forbidden")


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "duplicate JSON key")
        result[key] = value
    return result


def validate_json_values(value: Any, label: str) -> None:
    if value is None or type(value) in {bool, str}:
        return
    if type(value) is int:
        require(-(2**63) <= value <= 2**63 - 1, f"{label}: integer range")
        return
    if type(value) is list:
        for item in value:
            validate_json_values(item, label)
        return
    if type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, f"{label}: object key type")
            validate_json_values(item, label)
        return
    if type(value) is float:
        require(math.isfinite(value), f"{label}: finite number")
    raise PermitError(f"{label}: unsupported JSON value")


def strict_json(raw: bytes, label: str) -> Any:
    require(len(raw) <= MAXIMUM_JSON_BYTES, f"{label}: byte limit")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=strict_object,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError(f"{label}: invalid JSON") from error
    validate_json_values(value, label)
    return value


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


def typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            typed_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            typed_equal(a, b) for a, b in zip(left, right)
        )
    return bool(left == right)


def validate_content_binding(
    document: Mapping[str, Any],
    scope: str,
    label: str,
) -> None:
    binding = document.get("contentBinding")
    require(
        type(binding) is dict
        and set(binding)
        == {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}: content binding schema",
    )
    require(
        binding["algorithm"] == "sha256"
        and binding["canonicalization"]
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding["scope"] == scope
        and type(binding["sha256"]) is str
        and len(binding["sha256"]) == 64,
        f"{label}: content binding fields",
    )
    unsigned = dict(document)
    unsigned.pop("contentBinding")
    require(
        sha256_bytes(canonical_json_bytes(unsigned)) == binding["sha256"],
        f"{label}: content binding mismatch",
    )


def path_components(relative: str) -> tuple[str, ...]:
    require(
        type(relative) is str
        and relative
        and not relative.startswith("/")
        and "\x00" not in relative,
        "invalid repository-relative path",
    )
    components = tuple(relative.split("/"))
    require(
        all(
            component not in {"", ".", ".."}
            and len(component.encode("utf-8")) <= 255
            for component in components
        )
        and len(components) <= 64
        and len(relative.encode("utf-8")) <= 1024,
        "unsafe repository-relative path",
    )
    return components


def descriptor_state(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
    )


def directory_state(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
    )


def read_fd(fd: int, size: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while offset < size:
        chunk = os.pread(fd, min(1_048_576, size - offset), offset)
        require(bool(chunk), "unexpected EOF")
        chunks.append(chunk)
        offset += len(chunk)
    require(os.pread(fd, 1, size) == b"", "file grew during held read")
    return b"".join(chunks)


@dataclass
class FileSnapshot:
    path: str
    fd: int
    state: tuple[int, ...]
    raw: bytes
    parent_components: tuple[str, ...]


class HeldReader:
    """Hold repository paths through repeated descriptor and name barriers."""

    def __init__(self, root: Path):
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
            | os.O_NONBLOCK
        )
        self.root_fd = os.open(root, flags)
        self._directories: dict[tuple[str, ...], int] = {(): self.root_fd}
        self._directory_states: dict[tuple[str, ...], tuple[int, ...]] = {}
        self._files: dict[str, FileSnapshot] = {}
        self._absent: set[str] = set()
        self._listings: dict[tuple[str, ...], tuple[str, ...]] = {}
        self._total_read_bytes = 0
        self._validate_directory((), self.root_fd)

    def _validate_directory(self, components: tuple[str, ...], fd: int) -> None:
        info = os.fstat(fd)
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "unsafe repository directory",
        )
        self._directory_states[components] = directory_state(info)

    def _directory(self, components: tuple[str, ...]) -> int:
        if components in self._directories:
            return self._directories[components]
        parent = self._directory(components[:-1])
        fd = os.open(
            components[-1],
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
            | os.O_NONBLOCK,
            dir_fd=parent,
        )
        self._directories[components] = fd
        self._validate_directory(components, fd)
        return fd

    def read(
        self,
        relative: str,
        *,
        maximum_bytes: int,
        owner_only: bool = False,
    ) -> bytes:
        if relative in self._files:
            return self._files[relative].raw
        components = path_components(relative)
        parent_components = components[:-1]
        parent = self._directory(parent_components)
        fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=parent,
        )
        try:
            before = os.fstat(fd)
            require(
                stat.S_ISREG(before.st_mode)
                and before.st_uid == os.getuid()
                and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) & 0o022 == 0
                and 0 <= before.st_size <= maximum_bytes,
                f"{relative}: safe bounded single-link regular file required",
            )
            if owner_only:
                require(
                    stat.S_IMODE(before.st_mode) & 0o077 == 0,
                    f"{relative}: owner-only mode required",
                )
            raw = read_fd(fd, before.st_size)
            require(raw == read_fd(fd, before.st_size), f"{relative}: unstable")
            after = os.fstat(fd)
            require(
                descriptor_state(before) == descriptor_state(after),
                f"{relative}: descriptor identity changed",
            )
            self._total_read_bytes += len(raw)
            require(
                self._total_read_bytes <= MAXIMUM_TOTAL_READ_BYTES,
                "aggregate held-read byte limit",
            )
            self._files[relative] = FileSnapshot(
                relative,
                fd,
                descriptor_state(before),
                raw,
                parent_components,
            )
            fd = -1
            return raw
        finally:
            if fd >= 0:
                os.close(fd)

    def path_kind(self, relative: str) -> str:
        components = path_components(relative)
        parent = self._directory(components[:-1])
        try:
            info = os.stat(
                components[-1],
                dir_fd=parent,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            self._absent.add(relative)
            return "absent"
        if stat.S_ISREG(info.st_mode):
            return "file"
        if stat.S_ISDIR(info.st_mode):
            return "directory"
        if stat.S_ISLNK(info.st_mode):
            return "symlink"
        return "other"

    def list_names(self, relative: str) -> tuple[str, ...]:
        components = path_components(relative)
        fd = self._directory(components)
        names = tuple(sorted(os.listdir(fd)))
        self._listings[components] = names
        return names

    def verify(self) -> None:
        for components, fd in self._directories.items():
            require(
                directory_state(os.fstat(fd))
                == self._directory_states[components],
                "ancestor identity changed",
            )
        for snapshot in self._files.values():
            require(
                descriptor_state(os.fstat(snapshot.fd)) == snapshot.state
                and read_fd(snapshot.fd, snapshot.state[2]) == snapshot.raw,
                f"{snapshot.path}: held descriptor changed",
            )
            parent = self._directories[snapshot.parent_components]
            components = path_components(snapshot.path)
            try:
                name_info = os.stat(
                    components[-1],
                    dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError as error:
                raise PermitError(
                    f"{snapshot.path}: final name identity changed"
                ) from error
            require(
                stat.S_ISREG(name_info.st_mode)
                and (name_info.st_dev, name_info.st_ino)
                == (snapshot.state[0], snapshot.state[1]),
                f"{snapshot.path}: final name identity changed",
            )
        for relative in self._absent:
            components = path_components(relative)
            parent = self._directories[components[:-1]]
            try:
                os.stat(
                    components[-1],
                    dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                continue
            raise PermitError(f"{relative}: absent-name collision appeared")
        for components, expected in self._listings.items():
            require(
                tuple(sorted(os.listdir(self._directories[components])))
                == expected,
                "directory listing changed",
            )

    def close(self) -> None:
        for snapshot in self._files.values():
            os.close(snapshot.fd)
        for components in sorted(
            self._directories,
            key=len,
            reverse=True,
        ):
            os.close(self._directories[components])
        self._files.clear()
        self._directories.clear()


def resource_bindings_from_receipt(
    receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    sources = receipt.get("sources")
    require(type(sources) is list and len(sources) == 19, "receipt sources")
    resources: list[dict[str, Any]] = []
    tuple_ids: set[str] = set()
    names: set[str] = set()
    for expected_order, row in enumerate(sources, start=1):
        require(
            type(row) is dict
            and type(row.get("tupleId")) is str
            and row.get("order") == expected_order
            and type(row.get("module")) is str
            and type(row.get("version")) is str,
            "receipt source row identity",
        )
        tuple_id = row["tupleId"]
        require(tuple_id not in tuple_ids, "duplicate tuple id")
        tuple_ids.add(tuple_id)
        for kind in ("mod", "zip"):
            file_name = row.get(f"{kind}OutputFileName")
            byte_size = row.get(f"{kind}RawByteSize")
            digest = row.get(f"{kind}RawSha256")
            require(
                type(file_name) is str
                and "/" not in file_name
                and file_name not in names
                and type(byte_size) is int
                and type(byte_size) is not bool
                and 0 <= byte_size <= MAXIMUM_RESOURCE_BYTES
                and type(digest) is str
                and len(digest) == 64,
                "receipt resource row",
            )
            names.add(file_name)
            resources.append(
                {
                    "order": len(resources) + 1,
                    "tupleOrder": expected_order,
                    "tupleId": tuple_id,
                    "module": row["module"],
                    "version": row["version"],
                    "kind": kind,
                    "path": f"{DEPENDENCY_DIRECTORY}/{file_name}",
                    "byteSize": byte_size,
                    "rawSha256": digest,
                }
            )
    require(len(resources) == 38, "resource binding count")
    require(
        receipt.get("acceptedTupleCount") == 19
        and receipt.get("acceptedArtifactCount") == 38
        and receipt.get("validatedZipResourceCount") == 19
        and receipt.get("validatedModResourceCount") == 19
        and receipt.get("aggregateRawByteSize") == 13_178_024
        and receipt.get("aggregateZipRawByteSize") == 13_174_173
        and receipt.get("aggregateModRawByteSize") == 3_851
        and receipt.get("aggregateEntryCount") == 2_907
        and receipt.get("aggregateUncompressedByteCount") == 31_851_201
        and receipt.get("orderedSourceSetSha256")
        == ORDERED_SOURCE_SET_SHA256,
        "receipt aggregate contract",
    )
    return resources


def tool_binding(role: str, path: str, raw: Mapping[str, bytes]) -> dict[str, str]:
    require(path in raw, f"missing tool bytes: {path}")
    return {"role": role, "path": path, "rawSha256": sha256_bytes(raw[path])}


def original_decision_binding() -> dict[str, str]:
    return {
        "path": DECISION_PATH,
        "rawSha256": DECISION_RAW_SHA256,
        "contentSha256": DECISION_CONTENT_SHA256,
        "decisionId": DECISION_ID,
        "requiredStatus": (
            "dependency_source_review_wave1_decision_recorded_"
            "execution_not_authorized"
        ),
    }


def v1_failed_attempt_bindings() -> dict[str, dict[str, Any]]:
    return {
        "permit": {
            "path": V1_PERMIT_PATH,
            "rawSha256": V1_PERMIT_RAW_SHA256,
            "contentSha256": V1_PERMIT_CONTENT_SHA256,
            "permitId": V1_PERMIT_ID,
        },
        "claim": {
            "path": V1_CLAIM_PATH,
            "rawSha256": V1_CLAIM_RAW_SHA256,
            "contentSha256": V1_CLAIM_CONTENT_SHA256,
            "permitId": V1_PERMIT_ID,
            "reviewId": V1_REVIEW_ID,
        },
        "failure": {
            "path": V1_FAILURE_PATH,
            "rawSha256": V1_FAILURE_RAW_SHA256,
            "contentSha256": V1_FAILURE_CONTENT_SHA256,
            "permitId": V1_PERMIT_ID,
            "reviewId": V1_REVIEW_ID,
            "requiredFailureCode": "E_HELD_SET",
            "requiredPhase": "held_set",
            "permitContentSha256": V1_PERMIT_CONTENT_SHA256,
            "claimRawSha256": V1_CLAIM_RAW_SHA256,
        },
    }


def v2_failed_attempt_bindings() -> dict[str, dict[str, Any]]:
    return {
        "permit": {
            "path": V2_PERMIT_PATH,
            "rawSha256": V2_PERMIT_RAW_SHA256,
            "contentSha256": V2_PERMIT_CONTENT_SHA256,
            "permitId": V2_PERMIT_ID,
        },
        "claim": {
            "path": V2_CLAIM_PATH,
            "rawSha256": V2_CLAIM_RAW_SHA256,
            "contentSha256": V2_CLAIM_CONTENT_SHA256,
            "permitId": V2_PERMIT_ID,
            "reviewId": V2_REVIEW_ID,
        },
        "failure": {
            "path": V2_FAILURE_PATH,
            "rawSha256": V2_FAILURE_RAW_SHA256,
            "contentSha256": V2_FAILURE_CONTENT_SHA256,
            "permitId": V2_PERMIT_ID,
            "reviewId": V2_REVIEW_ID,
            "requiredFailureCode": "E_ARCHIVE_STRUCTURE",
            "requiredPhase": "archive",
            "requiredFailedTupleId": "wave1-010-ec8b158caf64",
            "requiredFailedTupleOrder": None,
            "requiredFailedResourceKind": None,
            "permitContentSha256": V2_PERMIT_CONTENT_SHA256,
            "claimRawSha256": V2_CLAIM_RAW_SHA256,
        },
    }


def failed_attempt_bindings() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "v1": v1_failed_attempt_bindings(),
        "v2": v2_failed_attempt_bindings(),
    }


def v1_failed_attempt_namespace_contract() -> dict[str, Any]:
    return {
        "requiredAbsentPaths": [
            V1_RESULT_PATH,
            V1_MANIFEST_PATH,
            V1_READBACK_CLAIM_PATH,
            V1_READBACK_RECEIPT_PATH,
            V1_READBACK_MANIFEST_PATH,
        ],
        "v1ResultRequiredAbsent": True,
        "v1ManifestRequiredAbsent": True,
        "v1ReadbackClaimRequiredAbsent": True,
        "v1ReadbackReceiptRequiredAbsent": True,
        "v1ReadbackManifestRequiredAbsent": True,
    }


def v2_failed_attempt_namespace_contract() -> dict[str, Any]:
    return {
        "requiredAbsentPaths": [
            V2_RESULT_PATH,
            V2_MANIFEST_PATH,
            V2_READBACK_CLAIM_PATH,
            V2_READBACK_RECEIPT_PATH,
            V2_READBACK_MANIFEST_PATH,
        ],
        "v2ResultRequiredAbsent": True,
        "v2ManifestRequiredAbsent": True,
        "v2ReadbackClaimRequiredAbsent": True,
        "v2ReadbackReceiptRequiredAbsent": True,
        "v2ReadbackManifestRequiredAbsent": True,
    }


def failed_attempt_namespace_contracts() -> dict[str, dict[str, Any]]:
    return {
        "v1": v1_failed_attempt_namespace_contract(),
        "v2": v2_failed_attempt_namespace_contract(),
    }


def apfs_recovery_contract() -> dict[str, Any]:
    return {
        "directoryIdentityFields": [
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
        ],
        "directoryIdentityExcludesLinkCount": True,
        "directoryLinkCountIsNotStableIdentity": True,
        "componentWiseNoFollowHeldParentsRequired": True,
        "trustedHeldClaimParentRequired": True,
        "trustedHeldOutputParentRequired": True,
        "claimAndOutputsPublishedDirectlyThroughHeldParentDescriptors": True,
        "publicationUsesHeldParentFdAndBasenameOnly": True,
        "descendantRetraversalForPublicationAllowed": False,
        "publicationFlags": [
            "O_WRONLY",
            "O_CREAT",
            "O_EXCL",
            "O_NOFOLLOW",
            "O_CLOEXEC",
        ],
        "heldParentBarrierBeforeAndAfterEachPublicationRequired": True,
        "finalHeldParentIdentityBarrierRequired": True,
    }


def v1_preservation_contract() -> dict[str, bool]:
    return {
        "v1PermitReuseAllowed": False,
        "v1ClaimDeletionAllowed": False,
        "v1FailureDeletionAllowed": False,
        "v1RunnerRetryAllowed": False,
        "v1AutomaticRetryAllowed": False,
        "v1ResultBackfillAllowed": False,
        "v1ManifestBackfillAllowed": False,
        "v1ReadbackBackfillAllowed": False,
    }


def v2_namespace_contract() -> dict[str, Any]:
    return {
        "permitPath": V2_PERMIT_PATH,
        "permitId": V2_PERMIT_ID,
        "reviewId": V2_REVIEW_ID,
        "claimPath": V2_CLAIM_PATH,
        "stagingDirectoryPrefix": ".wave-1-review-v2-staging-",
        "resultPath": V2_RESULT_PATH,
        "failurePath": V2_FAILURE_PATH,
        "manifestPath": V2_MANIFEST_PATH,
        "readbackClaimPath": V2_READBACK_CLAIM_PATH,
        "readbackReceiptPath": V2_READBACK_RECEIPT_PATH,
        "readbackManifestPath": V2_READBACK_MANIFEST_PATH,
        "freshOneUseNamespaceRequired": True,
        "reuseOfV1ArtifactsAllowed": False,
    }


def v2_preservation_contract() -> dict[str, bool]:
    return {
        "v2PermitModificationAllowed": False,
        "v2PermitReuseAllowed": False,
        "v2ClaimModificationAllowed": False,
        "v2ClaimDeletionAllowed": False,
        "v2FailureModificationAllowed": False,
        "v2FailureDeletionAllowed": False,
        "v2RunnerRetryAllowed": False,
        "v2AutomaticRetryAllowed": False,
        "v2ResultBackfillAllowed": False,
        "v2ManifestBackfillAllowed": False,
        "v2ReadbackBackfillAllowed": False,
    }


def v3_namespace_contract() -> dict[str, Any]:
    return {
        "permitPath": PERMIT_PATH,
        "permitId": PERMIT_ID,
        "reviewId": REVIEW_ID,
        "claimPath": CLAIM_PATH,
        "stagingDirectoryPrefix": STAGING_DIRECTORY_PREFIX,
        "resultPath": RESULT_PATH,
        "failurePath": FAILURE_PATH,
        "manifestPath": MANIFEST_PATH,
        "readbackClaimPath": READBACK_CLAIM_PATH,
        "readbackReceiptPath": READBACK_RECEIPT_PATH,
        "readbackManifestPath": READBACK_MANIFEST_PATH,
        "freshOneUseNamespaceRequired": True,
        "reuseOfV1ArtifactsAllowed": False,
        "reuseOfV2ArtifactsAllowed": False,
    }


def selected_v3_correction() -> dict[str, Any]:
    return {
        "escapeAwareSingleQuotedRuneTokenRequired": True,
        "doubleQuoteRuneLiteralSupported": True,
        "escapedSingleQuoteRuneLiteralSupported": True,
        "runeTokenMaySatisfyImportStringRequirement": False,
        "unterminatedOrMultilineRuneRejected": True,
        "reviewFailureCaughtBeforeRuntimeError": True,
        "reviewFailureCodePreserved": True,
        "reviewFailurePhasePreserved": True,
        "reviewFailureTupleIdPreserved": True,
        "reviewFailureTupleOrderPreserved": True,
        "reviewFailureResourceKindPreserved": True,
        "missingActiveBindingContextAttachedWithoutChangingCodeOrPhase": True,
        "sourceInventorySkippingAllowed": False,
        "testdataSkippingAllowed": False,
        "zipSafetyChecksUnchanged": [
            "exact_eocd_and_archive_byte_bounds",
            "module_prefix_and_safe_normalized_paths",
            "duplicate_and_casefold_collision_rejection",
            "encrypted_entry_rejection",
            "stored_or_deflated_compression_only",
            "zip64_extra_rejection",
            "regular_or_zero_mode_only",
            "entry_and_aggregate_uncompressed_bounds",
            "descriptor_read_size_and_crc_validation",
        ],
    }


def permit_predecessor_bindings() -> list[dict[str, str]]:
    bindings = [
        {"path": item.path, "rawSha256": item.raw_sha256}
        for item in FIXED_BINDINGS
    ]
    bindings.extend(
        [
            {
                "path": V1_RECOVERY_DECISION_PATH,
                "rawSha256": V1_RECOVERY_DECISION_RAW_SHA256,
            },
            {
                "path": RECOVERY_DECISION_PATH,
                "rawSha256": RECOVERY_DECISION_RAW_SHA256,
            },
            {
                "path": V1_PERMIT_PATH,
                "rawSha256": V1_PERMIT_RAW_SHA256,
            },
            {
                "path": V1_CLAIM_PATH,
                "rawSha256": V1_CLAIM_RAW_SHA256,
            },
            {
                "path": V1_FAILURE_PATH,
                "rawSha256": V1_FAILURE_RAW_SHA256,
            },
            {
                "path": V2_PERMIT_PATH,
                "rawSha256": V2_PERMIT_RAW_SHA256,
            },
            {
                "path": V2_CLAIM_PATH,
                "rawSha256": V2_CLAIM_RAW_SHA256,
            },
            {
                "path": V2_FAILURE_PATH,
                "rawSha256": V2_FAILURE_RAW_SHA256,
            },
        ]
    )
    require(
        len(bindings) == 18
        and len({binding["path"] for binding in bindings}) == 18,
        "permit predecessor binding inventory",
    )
    return bindings


def build_expected_recovery_decision_v1() -> dict[str, Any]:
    unsigned: dict[str, Any] = {
        "documentType": (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "recovery-decision"
        ),
        "schemaVersion": "1.0",
        "decisionId": V1_RECOVERY_DECISION_ID,
        "recordedDate": "2026-07-24",
        "status": (
            "dependency_source_review_wave1_v1_failure_read_back_v2_"
            "recovery_design_selected_execution_not_authorized"
        ),
        "result": (
            "v1_held_set_failure_preserved_apfs_directory_identity_and_"
            "held_output_parent_publication_correction_selected"
        ),
        "nextAction": (
            "prepare_separate_dependency_source_review_wave1_"
            "execution_permit_v2"
        ),
        "decisionBinding": original_decision_binding(),
        "failedAttemptBindings": v1_failed_attempt_bindings(),
        "failureCrossBindingContract": {
            "failureCode": "E_HELD_SET",
            "phase": "held_set",
            "failurePermitIdEqualsV1PermitId": True,
            "failureReviewIdEqualsV1ClaimReviewId": True,
            "failurePermitContentSha256EqualsV1PermitContentSha256": True,
            "failureClaimRawSha256EqualsV1ClaimRawSha256": True,
            "partialResultPublished": False,
            "automaticRetryAllowed": False,
        },
        "failedAttemptNamespaceContract": (
            v1_failed_attempt_namespace_contract()
        ),
        "rootCause": {
            "classification": (
                "apfs_directory_link_count_treated_as_stable_identity"
            ),
            "v1FailureCode": "E_HELD_SET",
            "v1FailurePhase": "held_set",
            "directoryLinkCountMayChangeWhenSiblingEntryIsPublished": True,
            "separateOutputPublicationHardeningGapIdentified": True,
            "outputParentRetraversalCanBreakHeldNamespaceGuarantee": True,
            "authenticationRelated": False,
            "credentialRelated": False,
            "ownerProofRelated": False,
        },
        "selectedV2Correction": apfs_recovery_contract(),
        "v1PreservationContract": v1_preservation_contract(),
        "v2NamespaceContract": v2_namespace_contract(),
        "authority": {
            "recoveryDesignRecorded": True,
            "v2RunnerInPlaceModificationAuthorized": True,
            "v2CheckerAndTestsAuthorized": True,
            "v2ReadbackInPlaceModificationAuthorized": True,
            "v2ExecutionPermitPreparationAuthorized": True,
            "reviewExecutionAuthorized": False,
            "archiveMemberInspectionAuthorized": False,
            "sourceExecutionAuthorized": False,
            "shellOrSubprocessAuthorized": False,
            "networkAuthorized": False,
            "sourceModificationAuthorized": False,
            "gitWriteAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "personalProjectBoundary": {
            "projectOwnership": "personal_single_owner",
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "signatureRequired": False,
            "credentialsAllowed": False,
            "userActionRequired": False,
            "productEndpointAuthenticationChanged": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
        },
        "closure": {
            "openFindingCount": 19,
            "findingsClosedByRecoveryDecision": 0,
            "graphFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "nonClaims": {
            "recoveryDecisionIsExecutionPermit": False,
            "v1FailureIsSuccessEvidence": False,
            "v1PermitReusable": False,
            "v1ArtifactsMayBeDeleted": False,
            "apfsCorrectionIsReviewResultEvidence": False,
            "candidateOrLibrarySelected": False,
            "releaseReady": False,
        },
    }
    decision = dict(unsigned)
    decision["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(unsigned)),
    }
    return decision


def build_expected_recovery_decision() -> dict[str, Any]:
    unsigned: dict[str, Any] = {
        "documentType": (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "recovery-decision"
        ),
        "schemaVersion": "1.0",
        "decisionId": RECOVERY_DECISION_ID,
        "recordedDate": "2026-07-24",
        "status": (
            "dependency_source_review_wave1_v2_failure_read_back_v3_"
            "recovery_design_selected_execution_not_authorized"
        ),
        "result": (
            "v2_valid_go_module_zip_false_rejection_preserved_escape_aware_"
            "rune_and_review_failure_context_correction_selected"
        ),
        "nextAction": (
            "prepare_separate_dependency_source_review_wave1_"
            "execution_permit_v3"
        ),
        "decisionBinding": original_decision_binding(),
        "priorRecoveryDecisionBinding": {
            "path": V1_RECOVERY_DECISION_PATH,
            "rawSha256": V1_RECOVERY_DECISION_RAW_SHA256,
            "contentSha256": V1_RECOVERY_DECISION_CONTENT_SHA256,
            "decisionId": V1_RECOVERY_DECISION_ID,
        },
        "failedAttemptBindings": failed_attempt_bindings(),
        "failureCrossBindingContracts": {
            "v1": {
                "failureCode": "E_HELD_SET",
                "phase": "held_set",
                "failurePermitIdEqualsV1PermitId": True,
                "failureReviewIdEqualsV1ClaimReviewId": True,
                "failurePermitContentSha256EqualsV1PermitContentSha256": True,
                "failureClaimRawSha256EqualsV1ClaimRawSha256": True,
                "partialResultPublished": False,
                "automaticRetryAllowed": False,
            },
            "v2": {
                "recordedFailureCode": "E_ARCHIVE_STRUCTURE",
                "recordedPhase": "archive",
                "recordedFailedTupleId": "wave1-010-ec8b158caf64",
                "recordedFailedTupleOrder": None,
                "recordedFailedResourceKind": None,
                "failurePermitIdEqualsV2PermitId": True,
                "failureReviewIdEqualsV2ClaimReviewId": True,
                "failurePermitContentSha256EqualsV2PermitContentSha256": True,
                "failureClaimRawSha256EqualsV2ClaimRawSha256": True,
                "partialResultPublished": False,
                "automaticRetryAllowed": False,
            },
        },
        "failedAttemptNamespaceContracts": (
            failed_attempt_namespace_contracts()
        ),
        "rootCause": {
            "classification": (
                "valid_go_rune_literal_misparsed_then_review_failure_"
                "misclassified"
            ),
            "module": "golang.org/x/net",
            "version": "v0.49.0",
            "tupleId": "wave1-010-ec8b158caf64",
            "tupleOrder": 10,
            "resourceKind": "zip",
            "sourcePath": "html/charset/charset.go",
            "sourceLine": 232,
            "doubleQuoteRuneLiteralIsValidGo": True,
            "escapedSingleQuoteRuneLiteralIsValidGo": True,
            "underlyingFailureCode": "E_IMPORT_PARSE",
            "underlyingFailurePhase": "source_inventory",
            "reviewFailureIsRuntimeErrorSubclass": True,
            "broadRuntimeErrorCatchReclassifiedUnderlyingFailure": True,
            "recordedFailureCode": "E_ARCHIVE_STRUCTURE",
            "recordedFailurePhase": "archive",
            "zipStructurePredicateFailureObserved": False,
            "tupleZipEntryCount": 825,
            "tupleZipAllEntriesReadAndCrcValidated": True,
            "authenticationRelated": False,
            "credentialRelated": False,
            "ownerProofRelated": False,
        },
        "selectedV3Correction": selected_v3_correction(),
        "v1PreservationContract": v1_preservation_contract(),
        "v2PreservationContract": v2_preservation_contract(),
        "v3NamespaceContract": v3_namespace_contract(),
        "authority": {
            "recoveryDesignRecorded": True,
            "v3RunnerAndTestsModificationAuthorized": True,
            "v3CheckerAndTestsModificationAuthorized": True,
            "v3ReadbackModificationAuthorized": True,
            "v3ExecutionPermitPreparationAuthorized": True,
            "reviewExecutionAuthorized": False,
            "archiveMemberInspectionAuthorized": False,
            "sourceExecutionAuthorized": False,
            "shellOrSubprocessAuthorized": False,
            "networkAuthorized": False,
            "reviewedSourceModificationAuthorized": False,
            "gitWriteAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "signatureRequired": False,
            "credentialsAllowed": False,
            "userActionRequired": False,
        },
        "personalProjectBoundary": {
            "projectOwnership": "personal_single_owner",
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "signatureRequired": False,
            "credentialsAllowed": False,
            "userActionRequired": False,
            "productEndpointAuthenticationChanged": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
        },
        "closure": {
            "openFindingCount": 19,
            "findingsClosedByRecoveryDecision": 0,
            "graphFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "nonClaims": {
            "recoveryDecisionIsExecutionPermit": False,
            "v1OrV2FailureIsSuccessEvidence": False,
            "v1PermitReusable": False,
            "v2PermitReusable": False,
            "v1OrV2ArtifactsMayBeDeleted": False,
            "recordedArchiveStructureFailureProvesZipCorruption": False,
            "v3CorrectionIsReviewResultEvidence": False,
            "candidateOrLibrarySelected": False,
            "releaseReady": False,
        },
    }
    decision = dict(unsigned)
    decision["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(unsigned)),
    }
    return decision


def build_expected_permit(
    raw: Mapping[str, bytes],
    decision: Mapping[str, Any],
    recovery_decision: Mapping[str, Any],
    receipt: Mapping[str, Any],
    resources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the exact permit from already-held bytes without self-hash cycles."""

    require(
        decision.get("decisionId") == DECISION_ID
        and decision.get("contentBinding", {}).get("sha256")
        == DECISION_CONTENT_SHA256,
        "decision identity for permit",
    )
    require(
        recovery_decision.get("decisionId") == RECOVERY_DECISION_ID
        and recovery_decision.get("contentBinding", {}).get("sha256")
        == RECOVERY_DECISION_CONTENT_SHA256,
        "recovery decision identity for permit",
    )
    require(len(resources) == 38, "permit resource count")
    unsigned: dict[str, Any] = {
        "documentType": (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": PERMIT_ID,
        "recordedDate": "2026-07-24",
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "scope": (
            "single_use_offline_in_memory_wp4_graph_frontier_license_"
            "native_inventory_wave1_only"
        ),
        "decisionBinding": original_decision_binding(),
        "recoveryDecisionBinding": {
            "path": RECOVERY_DECISION_PATH,
            "rawSha256": RECOVERY_DECISION_RAW_SHA256,
            "contentSha256": RECOVERY_DECISION_CONTENT_SHA256,
            "decisionId": RECOVERY_DECISION_ID,
            "requiredStatus": recovery_decision["status"],
        },
        "priorRecoveryDecisionBinding": {
            "path": V1_RECOVERY_DECISION_PATH,
            "rawSha256": V1_RECOVERY_DECISION_RAW_SHA256,
            "contentSha256": V1_RECOVERY_DECISION_CONTENT_SHA256,
            "decisionId": V1_RECOVERY_DECISION_ID,
        },
        "failedAttemptBindings": failed_attempt_bindings(),
        "failedAttemptNamespaceContracts": (
            failed_attempt_namespace_contracts()
        ),
        "apfsRecoveryContract": apfs_recovery_contract(),
        "selectedV3Correction": selected_v3_correction(),
        "v1PreservationContract": v1_preservation_contract(),
        "v2PreservationContract": v2_preservation_contract(),
        "v3NamespaceContract": v3_namespace_contract(),
        "predecessorBindings": permit_predecessor_bindings(),
        "toolBindings": [
            tool_binding(
                "decision_checker",
                DECISION_CHECKER_PATH,
                raw,
            ),
            tool_binding(
                "decision_checker_tests",
                DECISION_TEST_PATH,
                raw,
            ),
            tool_binding("review_runner", RUNNER_PATH, raw),
            tool_binding("review_runner_tests", RUNNER_TEST_PATH, raw),
            tool_binding("permit_checker", CHECKER_PATH, raw),
            tool_binding("permit_checker_tests", CHECKER_TEST_PATH, raw),
            tool_binding(
                "readback_recorder",
                READBACK_RECORDER_PATH,
                raw,
            ),
            tool_binding(
                "readback_recorder_tests",
                READBACK_RECORDER_TEST_PATH,
                raw,
            ),
            tool_binding(
                "readback_checker",
                READBACK_CHECKER_PATH,
                raw,
            ),
            tool_binding(
                "readback_checker_tests",
                READBACK_CHECKER_TEST_PATH,
                raw,
            ),
        ],
        "inputBindings": {
            "rootArchive": {
                "path": ROOT_ARCHIVE_PATH,
                "byteSize": len(raw[ROOT_ARCHIVE_PATH]),
                "rawSha256": ROOT_ARCHIVE_RAW_SHA256,
            },
            "acquisitionReceipt": {
                "path": RECEIPT_PATH,
                "rawSha256": sha256_bytes(raw[RECEIPT_PATH]),
            },
            "dependencyDirectory": DEPENDENCY_DIRECTORY,
            "resourceCount": 38,
            "modCount": 19,
            "zipCount": 19,
            "aggregateRawByteSize": 13_178_024,
            "aggregateEntryCount": 2_907,
            "aggregateUncompressedByteCount": 31_851_201,
            "orderedSourceSetSha256": ORDERED_SOURCE_SET_SHA256,
            "resources": [dict(item) for item in resources],
        },
        "interpreterIsolationContract": {
            "checkerPreflightCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                CHECKER_PATH,
                "--preflight",
            ],
            "runnerPreflightCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RUNNER_PATH,
                "--preflight",
            ],
            "runnerExecuteCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RUNNER_PATH,
                "--execute",
            ],
            "isolatedInterpreterRequired": True,
            "sitePackagesAllowed": False,
            "bytecodeWritesAllowed": False,
            "environmentOverridesAllowed": False,
            "cliPathOrLimitOverridesAllowed": False,
            "processUmask": "077",
        },
        "oneUseConsumption": {
            "initialState": "authorized_not_consumed",
            "claimPath": CLAIM_PATH,
            "claimCreatedBeforeArchiveMemberOpenOrDecode": True,
            "claimCreationFlags": [
                "O_WRONLY",
                "O_CREAT",
                "O_EXCL",
                "O_NOFOLLOW",
                "O_CLOEXEC",
            ],
            "claimMode": "0600",
            "claimRetainedAfterSuccessFailureOrUncertainty": True,
            "preclaimFailureConsumesPermit": False,
            "postclaimFailureConsumesPermit": True,
            "postclaimUncertaintyConsumesPermit": True,
            "automaticRetryAllowed": False,
            "secondExecutionAllowed": False,
            "failureRequiresNewVersionedPermit": True,
        },
        "resultContract": {
            "resultPath": RESULT_PATH,
            "failurePath": FAILURE_PATH,
            "successAndFailureMutuallyExclusive": True,
            "maximumBytes": 8_388_608,
            "canonicalJsonRequired": True,
            "sourceBodiesAllowed": False,
            "absolutePathsAllowed": False,
            "atomicNoReplacePublicationRequired": True,
            "independentGraphReconstructionsRequired": 2,
            "newTupleFrontierIsObservationOnly": True,
        },
        "manifestContract": {
            "manifestPath": MANIFEST_PATH,
            "manifestWrittenLast": True,
            "resultOrFailureRawSha256Required": True,
            "manifestIsSoleCompletionMarker": True,
            "independentReadbackRequired": True,
            "runnerSelfCheckIsIndependentReadback": False,
        },
        "independentReadbackContract": {
            "claimPath": READBACK_CLAIM_PATH,
            "receiptPath": READBACK_RECEIPT_PATH,
            "manifestPath": READBACK_MANIFEST_PATH,
            "recordToolPath": READBACK_RECORDER_PATH,
            "recordTestsPath": READBACK_RECORDER_TEST_PATH,
            "verificationOnlyToolPath": READBACK_CHECKER_PATH,
            "verificationOnlyTestsPath": READBACK_CHECKER_TEST_PATH,
            "reviewSuccessRequired": True,
            "reviewFailureMustBeAbsent": True,
            "oneUseNoOverwriteRequired": True,
            "claimCreatedAfterHeldValidationBeforeOutputs": True,
            "receiptWrittenBeforeManifest": True,
            "manifestWrittenLast": True,
            "recordFileWriteCount": 3,
            "verificationOnlyFileWriteCount": 0,
            "runnerInvocationAllowed": False,
            "archiveOpenAllowed": False,
            "archiveMemberInspectionAllowed": False,
            "sourceExecutionAllowed": False,
            "networkAllowed": False,
            "automaticRetryAllowed": False,
            "postclaimFailureRequiresVersionedRecovery": True,
        },
        "collisionAndToctouContract": {
            "componentWiseNoFollowRequired": True,
            "ownerAndNonWritableAncestorsRequired": True,
            "regularSingleLinkInputsRequired": True,
            "ownerOnlyAcquiredInputsRequired": True,
            "twoStableDescriptorReadsRequired": True,
            "finalNameIdentityBarrierRequired": True,
            "ancestorIdentityBarrierRequired": True,
            "inputDescriptorsHeldThroughExecutionRequired": True,
            "claimAndOutputNamespaceInitiallyCleanRequired": True,
            "casefoldAndNfcOutputCollisionRejectionRequired": True,
            "stagingDirectoryPrefix": STAGING_DIRECTORY_PREFIX,
            "atomicNoReplaceWritesRequired": True,
            "manifestWrittenLast": True,
        },
        "personalProjectBoundary": {
            "projectOwnership": "personal_single_owner",
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "executionPermitAuthenticationRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "signatureRequired": False,
            "credentialsAllowed": False,
            "userActionRequired": False,
            "productEndpointAuthenticationEvaluatedByThisPermit": False,
            "productEndpointAuthenticationUserInputRequiredForThisPermit": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
        },
        "authority": {
            "permitRecorded": True,
            "boundedDependencySourceReviewWave1Authorized": True,
            "boundedInMemoryArchiveInspectionAuthorized": True,
            "boundedSourceTextStaticInspectionAuthorized": True,
            "verifiedPinnedPermitCheckerModuleLoadingAuthorized": True,
            "oneUseClaimWriteAuthorized": True,
            "boundedResultOrFailureWriteAuthorized": True,
            "manifestWriteAuthorized": True,
            "filesystemExtractionAuthorized": False,
            "sourceMaterializationAuthorized": False,
            "reviewedSourceLoadOrExecutionAuthorized": False,
            "generatorTestHookOrBuildScriptExecutionAuthorized": False,
            "packageManagerAuthorized": False,
            "goCommandAuthorized": False,
            "compilerAuthorized": False,
            "shellOrSubprocessAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "networkAuthorized": False,
            "sourceModificationAuthorized": False,
            "gitWriteAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "execution": {
            "permitRecorded": True,
            "permitConsumed": False,
            "claimCreated": False,
            "archiveMemberInspectionCount": 0,
            "sourceExecutionCount": 0,
            "subprocessCount": 0,
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "resultCreated": False,
            "failureCreated": False,
            "manifestCreated": False,
            "independentReadbackPassed": False,
        },
        "closure": {
            "openFindingCount": 19,
            "findingsClosedByPermit": 0,
            "graphFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "nonClaims": {
            "permitIsExecution": False,
            "oneWaveIsFixedPointEvidence": False,
            "staticReviewIsCompileRuntimeOrNetworkEvidence": False,
            "newTupleObservationSelectsDependency": False,
            "candidateOrLibrarySelected": False,
            "productEndpointAuthenticationEvaluatedByThisPermit": False,
            "productEndpointAuthenticationUserInputRequiredForThisPermit": False,
            "releaseReady": False,
        },
    }
    permit = dict(unsigned)
    permit["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(unsigned)),
    }
    return permit


def validate_decision(decision: Mapping[str, Any]) -> None:
    validate_content_binding(decision, "decision_without_contentBinding", "decision")
    require(
        decision.get("decisionId") == DECISION_ID
        and decision.get("status")
        == (
            "dependency_source_review_wave1_decision_recorded_"
            "execution_not_authorized"
        )
        and decision.get("nextAction")
        == (
            "prepare_separate_dependency_source_review_wave1_"
            "runner_tests_and_execution_permit"
        )
        and decision.get("contentBinding", {}).get("sha256")
        == DECISION_CONTENT_SHA256
        and decision.get("authority", {}).get("reviewExecutionAuthorized")
        is False
        and decision.get("authority", {}).get("networkAuthorized") is False
        and decision.get("authority", {}).get("externalAuthenticationRequired")
        is False
        and decision.get("authority", {}).get("userActionRequired") is False
        and decision.get("closure", {}).get("openFindingCount") == 19
        and decision.get("closure", {}).get("graphFixedPointReached") is False
        and decision.get("closure", {}).get("candidateSelected") is False
        and decision.get("closure", {}).get("librarySelected") is False,
        "decision state contract",
    )


def validate_recovery_decision(
    recovery_decision: Mapping[str, Any],
) -> None:
    validate_content_binding(
        recovery_decision,
        "decision_without_contentBinding",
        "recovery decision",
    )
    require(
        typed_equal(
            recovery_decision,
            build_expected_recovery_decision(),
        ),
        "recovery decision exact typed contract mismatch",
    )


def validate_recovery_decision_v1(
    recovery_decision: Mapping[str, Any],
) -> None:
    validate_content_binding(
        recovery_decision,
        "decision_without_contentBinding",
        "v1 recovery decision",
    )
    require(
        typed_equal(
            recovery_decision,
            build_expected_recovery_decision_v1(),
        ),
        "v1 recovery decision exact typed contract mismatch",
    )


def validate_v1_failed_attempt(
    raw: Mapping[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(
        sha256_bytes(raw[V1_PERMIT_PATH]) == V1_PERMIT_RAW_SHA256,
        "v1 permit raw SHA-256",
    )
    require(
        sha256_bytes(raw[V1_CLAIM_PATH]) == V1_CLAIM_RAW_SHA256,
        "v1 claim raw SHA-256",
    )
    require(
        sha256_bytes(raw[V1_FAILURE_PATH]) == V1_FAILURE_RAW_SHA256,
        "v1 failure raw SHA-256",
    )
    permit = strict_json(raw[V1_PERMIT_PATH], "v1 execution permit")
    claim = strict_json(raw[V1_CLAIM_PATH], "v1 review claim")
    failure = strict_json(raw[V1_FAILURE_PATH], "v1 review failure")
    require(type(permit) is dict, "v1 execution permit object")
    require(type(claim) is dict, "v1 review claim object")
    require(type(failure) is dict, "v1 review failure object")
    validate_content_binding(
        permit,
        "permit_without_contentBinding",
        "v1 execution permit",
    )
    validate_content_binding(
        claim,
        "claim_without_contentBinding",
        "v1 review claim",
    )
    validate_content_binding(
        failure,
        "failure_without_contentBinding",
        "v1 review failure",
    )
    require(
        permit.get("permitId") == V1_PERMIT_ID
        and permit.get("contentBinding", {}).get("sha256")
        == V1_PERMIT_CONTENT_SHA256
        and permit.get("execution", {}).get("permitConsumed") is False,
        "v1 permit historical identity",
    )
    require(
        claim.get("permitId") == V1_PERMIT_ID
        and claim.get("permitContentSha256") == V1_PERMIT_CONTENT_SHA256
        and claim.get("reviewId") == V1_REVIEW_ID
        and claim.get("contentBinding", {}).get("sha256")
        == V1_CLAIM_CONTENT_SHA256
        and claim.get("automaticRetryAllowed") is False,
        "v1 claim cross-binding",
    )
    require(
        failure.get("permitId") == V1_PERMIT_ID
        and failure.get("permitContentSha256") == V1_PERMIT_CONTENT_SHA256
        and failure.get("claimRawSha256") == V1_CLAIM_RAW_SHA256
        and failure.get("reviewId") == V1_REVIEW_ID
        and failure.get("failureCode") == "E_HELD_SET"
        and failure.get("phase") == "held_set"
        and failure.get("partialResultPublished") is False
        and failure.get("automaticRetryAllowed") is False
        and failure.get("contentBinding", {}).get("sha256")
        == V1_FAILURE_CONTENT_SHA256,
        "v1 failure cross-binding",
    )
    return permit, claim, failure


def validate_v2_failed_attempt(
    raw: Mapping[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(
        sha256_bytes(raw[V2_PERMIT_PATH]) == V2_PERMIT_RAW_SHA256,
        "v2 permit raw SHA-256",
    )
    require(
        sha256_bytes(raw[V2_CLAIM_PATH]) == V2_CLAIM_RAW_SHA256,
        "v2 claim raw SHA-256",
    )
    require(
        sha256_bytes(raw[V2_FAILURE_PATH]) == V2_FAILURE_RAW_SHA256,
        "v2 failure raw SHA-256",
    )
    permit = strict_json(raw[V2_PERMIT_PATH], "v2 execution permit")
    claim = strict_json(raw[V2_CLAIM_PATH], "v2 review claim")
    failure = strict_json(raw[V2_FAILURE_PATH], "v2 review failure")
    require(type(permit) is dict, "v2 execution permit object")
    require(type(claim) is dict, "v2 review claim object")
    require(type(failure) is dict, "v2 review failure object")
    validate_content_binding(
        permit,
        "permit_without_contentBinding",
        "v2 execution permit",
    )
    validate_content_binding(
        claim,
        "claim_without_contentBinding",
        "v2 review claim",
    )
    validate_content_binding(
        failure,
        "failure_without_contentBinding",
        "v2 review failure",
    )
    require(
        permit.get("permitId") == V2_PERMIT_ID
        and permit.get("contentBinding", {}).get("sha256")
        == V2_PERMIT_CONTENT_SHA256
        and permit.get("execution", {}).get("permitConsumed") is False,
        "v2 permit historical identity",
    )
    require(
        claim.get("permitId") == V2_PERMIT_ID
        and claim.get("permitContentSha256") == V2_PERMIT_CONTENT_SHA256
        and claim.get("reviewId") == V2_REVIEW_ID
        and claim.get("contentBinding", {}).get("sha256")
        == V2_CLAIM_CONTENT_SHA256
        and claim.get("automaticRetryAllowed") is False,
        "v2 claim cross-binding",
    )
    require(
        failure.get("permitId") == V2_PERMIT_ID
        and failure.get("permitContentSha256") == V2_PERMIT_CONTENT_SHA256
        and failure.get("claimRawSha256") == V2_CLAIM_RAW_SHA256
        and failure.get("reviewId") == V2_REVIEW_ID
        and failure.get("failureCode") == "E_ARCHIVE_STRUCTURE"
        and failure.get("phase") == "archive"
        and failure.get("failedTupleId") == "wave1-010-ec8b158caf64"
        and "failedTupleOrder" in failure
        and failure["failedTupleOrder"] is None
        and "failedResourceKind" in failure
        and failure["failedResourceKind"] is None
        and failure.get("partialResultPublished") is False
        and failure.get("automaticRetryAllowed") is False
        and failure.get("contentBinding", {}).get("sha256")
        == V2_FAILURE_CONTENT_SHA256,
        "v2 failure cross-binding",
    )
    return permit, claim, failure


def validate_failed_attempt(
    raw: Mapping[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Backward-compatible name for the frozen v1 failed attempt."""

    return validate_v1_failed_attempt(raw)


def validate_resource_bytes(
    raw: Mapping[str, bytes],
    resources: Sequence[Mapping[str, Any]],
) -> None:
    total = 0
    for item in resources:
        path = item["path"]
        payload = raw[path]
        require(
            len(payload) == item["byteSize"]
            and sha256_bytes(payload) == item["rawSha256"],
            f"{path}: retained resource binding",
        )
        total += len(payload)
    require(total == 13_178_024, "retained resource aggregate byte size")


def absent_path_state(
    reader: HeldReader,
    paths: Sequence[str],
) -> dict[str, Any]:
    kinds = {path: reader.path_kind(path) for path in paths}
    by_parent: dict[str, set[str]] = {}
    for path in paths:
        parent, basename = path.rsplit("/", 1)
        by_parent.setdefault(parent, set()).add(
            unicodedata.normalize("NFC", basename).casefold()
        )
    collisions: list[dict[str, str]] = []
    for parent, normalized_basenames in by_parent.items():
        for name in reader.list_names(parent):
            if (
                unicodedata.normalize("NFC", name).casefold()
                in normalized_basenames
            ):
                collisions.append({"parent": parent, "name": name})
    return {
        "allRequiredPathsAbsent": (
            all(kind == "absent" for kind in kinds.values())
            and not collisions
        ),
        "requiredPathKinds": kinds,
        "casefoldOrNfcCollisionEntries": collisions,
    }


def v1_failed_attempt_namespace_state(reader: HeldReader) -> dict[str, Any]:
    paths = (
        V1_RESULT_PATH,
        V1_MANIFEST_PATH,
        V1_READBACK_CLAIM_PATH,
        V1_READBACK_RECEIPT_PATH,
        V1_READBACK_MANIFEST_PATH,
    )
    state = absent_path_state(reader, paths)
    return {
        "v1FailedAttemptNamespaceContractSatisfied": state[
            "allRequiredPathsAbsent"
        ],
        "v1FailedAttemptRequiredPathKinds": state["requiredPathKinds"],
        "v1FailedAttemptCasefoldOrNfcCollisionEntries": state[
            "casefoldOrNfcCollisionEntries"
        ],
    }


def v2_failed_attempt_namespace_state(reader: HeldReader) -> dict[str, Any]:
    paths = (
        V2_RESULT_PATH,
        V2_MANIFEST_PATH,
        V2_READBACK_CLAIM_PATH,
        V2_READBACK_RECEIPT_PATH,
        V2_READBACK_MANIFEST_PATH,
    )
    state = absent_path_state(reader, paths)
    return {
        "v2FailedAttemptNamespaceContractSatisfied": state[
            "allRequiredPathsAbsent"
        ],
        "v2FailedAttemptRequiredPathKinds": state["requiredPathKinds"],
        "v2FailedAttemptCasefoldOrNfcCollisionEntries": state[
            "casefoldOrNfcCollisionEntries"
        ],
    }


def failed_attempt_namespace_state(reader: HeldReader) -> dict[str, Any]:
    """Backward-compatible v1 historical namespace view."""

    return v1_failed_attempt_namespace_state(reader)


def namespace_state(reader: HeldReader) -> dict[str, Any]:
    reserved = (
        CLAIM_PATH,
        RESULT_PATH,
        FAILURE_PATH,
        MANIFEST_PATH,
        READBACK_CLAIM_PATH,
        READBACK_RECEIPT_PATH,
        READBACK_MANIFEST_PATH,
    )
    absent_state = absent_path_state(reader, reserved)
    dependency_parent = CLAIM_PATH.rsplit("/", 1)[0]
    dependency_names = reader.list_names(dependency_parent)
    staging_names = [
        name
        for name in dependency_names
        if unicodedata.normalize("NFC", name)
        .casefold()
        .startswith(STAGING_DIRECTORY_PREFIX.casefold())
    ]
    clean = (
        absent_state["allRequiredPathsAbsent"]
        and not staging_names
    )
    return {
        "namespaceInitiallyClean": clean,
        "reservedPathKinds": absent_state["requiredPathKinds"],
        "casefoldOrNfcCollisionEntries": absent_state[
            "casefoldOrNfcCollisionEntries"
        ],
        "stagingCollisionNames": staging_names,
    }


def validate_repository(
    root: Path = ROOT,
    *,
    before_final_barrier: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Validate a present permit and clean one-use namespace without mutation."""

    require_isolated_interpreter()
    reader = HeldReader(root)
    try:
        raw: dict[str, bytes] = {}

        def held(
            path: str,
            maximum: int,
            owner_only: bool = False,
        ) -> bytes:
            payload = reader.read(
                path,
                maximum_bytes=maximum,
                owner_only=owner_only,
            )
            raw[path] = payload
            return payload

        permit_raw = held(PERMIT_PATH, MAXIMUM_JSON_BYTES)
        decision_raw = held(DECISION_PATH, MAXIMUM_JSON_BYTES)
        recovery_decision_raw = held(
            RECOVERY_DECISION_PATH,
            MAXIMUM_JSON_BYTES,
        )
        v1_recovery_decision_raw = held(
            V1_RECOVERY_DECISION_PATH,
            MAXIMUM_JSON_BYTES,
        )
        require(
            sha256_bytes(decision_raw) == DECISION_RAW_SHA256,
            "decision raw SHA-256",
        )
        require(
            sha256_bytes(recovery_decision_raw)
            == RECOVERY_DECISION_RAW_SHA256,
            "recovery decision raw SHA-256",
        )
        require(
            sha256_bytes(v1_recovery_decision_raw)
            == V1_RECOVERY_DECISION_RAW_SHA256,
            "v1 recovery decision raw SHA-256",
        )
        held(V1_PERMIT_PATH, MAXIMUM_JSON_BYTES)
        held(V1_CLAIM_PATH, MAXIMUM_JSON_BYTES, True)
        held(V1_FAILURE_PATH, MAXIMUM_JSON_BYTES, True)
        held(V2_PERMIT_PATH, MAXIMUM_JSON_BYTES)
        held(V2_CLAIM_PATH, MAXIMUM_JSON_BYTES, True)
        held(V2_FAILURE_PATH, MAXIMUM_JSON_BYTES, True)
        require(
            sha256_bytes(held(DECISION_CHECKER_PATH, MAXIMUM_TOOL_BYTES))
            == DECISION_CHECKER_RAW_SHA256,
            "decision checker raw SHA-256",
        )
        require(
            sha256_bytes(held(DECISION_TEST_PATH, MAXIMUM_TOOL_BYTES))
            == DECISION_TEST_RAW_SHA256,
            "decision tests raw SHA-256",
        )
        held(CHECKER_PATH, MAXIMUM_TOOL_BYTES)
        held(CHECKER_TEST_PATH, MAXIMUM_TOOL_BYTES)
        held(RUNNER_PATH, MAXIMUM_TOOL_BYTES)
        held(RUNNER_TEST_PATH, MAXIMUM_TOOL_BYTES)
        held(READBACK_RECORDER_PATH, MAXIMUM_TOOL_BYTES)
        held(READBACK_RECORDER_TEST_PATH, MAXIMUM_TOOL_BYTES)
        held(READBACK_CHECKER_PATH, MAXIMUM_TOOL_BYTES)
        held(READBACK_CHECKER_TEST_PATH, MAXIMUM_TOOL_BYTES)
        for item in FIXED_BINDINGS:
            require(
                sha256_bytes(
                    held(item.path, item.maximum_bytes, item.owner_only)
                )
                == item.raw_sha256,
                f"{item.path}: predecessor raw SHA-256",
            )
        require(
            sha256_bytes(
                held(
                    ROOT_ARCHIVE_PATH,
                    MAXIMUM_ROOT_ARCHIVE_BYTES,
                    True,
                )
            )
            == ROOT_ARCHIVE_RAW_SHA256,
            "root archive raw SHA-256",
        )

        decision = strict_json(decision_raw, "review decision")
        require(type(decision) is dict, "review decision object")
        validate_decision(decision)
        recovery_decision = strict_json(
            recovery_decision_raw,
            "recovery decision",
        )
        require(type(recovery_decision) is dict, "recovery decision object")
        validate_recovery_decision(recovery_decision)
        v1_recovery_decision = strict_json(
            v1_recovery_decision_raw,
            "v1 recovery decision",
        )
        require(
            type(v1_recovery_decision) is dict,
            "v1 recovery decision object",
        )
        validate_recovery_decision_v1(v1_recovery_decision)
        v1_permit, v1_claim, v1_failure = validate_v1_failed_attempt(raw)
        v2_permit, v2_claim, v2_failure = validate_v2_failed_attempt(raw)
        v1_failed_namespace = v1_failed_attempt_namespace_state(reader)
        require(
            v1_failed_namespace[
                "v1FailedAttemptNamespaceContractSatisfied"
            ],
            "v1 failed-attempt namespace contract",
        )
        v2_failed_namespace = v2_failed_attempt_namespace_state(reader)
        require(
            v2_failed_namespace[
                "v2FailedAttemptNamespaceContractSatisfied"
            ],
            "v2 failed-attempt namespace contract",
        )
        receipt = strict_json(raw[RECEIPT_PATH], "acquisition receipt")
        require(type(receipt) is dict, "acquisition receipt object")
        resources = resource_bindings_from_receipt(receipt)
        for item in resources:
            held(item["path"], MAXIMUM_RESOURCE_BYTES, True)
        validate_resource_bytes(raw, resources)

        permit = strict_json(permit_raw, "execution permit")
        require(type(permit) is dict, "execution permit object")
        validate_content_binding(
            permit,
            "permit_without_contentBinding",
            "execution permit",
        )
        expected = build_expected_permit(
            raw,
            decision,
            recovery_decision,
            receipt,
            resources,
        )
        require(
            typed_equal(permit, expected),
            "execution permit exact typed contract mismatch",
        )
        namespace = namespace_state(reader)
        require(namespace["namespaceInitiallyClean"], "one-use namespace collision")

        reader.verify()
        if before_final_barrier is not None:
            before_final_barrier()
        reader.verify()
        root_info = os.fstat(reader.root_fd)
        return {
            "documentType": (
                "aetherlink.g2-pion-dependency-source-review-wave1-"
                "execution-permit-preflight"
            ),
            "schemaVersion": "1.0",
            "status": EXPECTED_STATUS,
            "permit": permit,
            "decision": decision,
            "recoveryDecision": recovery_decision,
            "v1RecoveryDecision": v1_recovery_decision,
            "v1Permit": v1_permit,
            "v1Claim": v1_claim,
            "v1Failure": v1_failure,
            "v2Permit": v2_permit,
            "v2Claim": v2_claim,
            "v2Failure": v2_failure,
            "repositoryRootIdentity": {
                "device": root_info.st_dev,
                "inode": root_info.st_ino,
                "ownerUid": root_info.st_uid,
                "mode": stat.S_IMODE(root_info.st_mode),
            },
            "reviewExecutionAuthorized": True,
            "runnerRawSha256": sha256_bytes(raw[RUNNER_PATH]),
            "permitCheckerRawSha256": sha256_bytes(raw[CHECKER_PATH]),
            "namespaceInitiallyClean": True,
            "heldInputResourceCount": 38,
            "archiveMemberInspectionCount": 0,
            "sourceExecutionCount": 0,
            "subprocessCount": 0,
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            **v1_failed_namespace,
            **v2_failed_namespace,
            **namespace,
        }
    finally:
        reader.close()


def preflight_status(root: Path = ROOT) -> tuple[dict[str, Any], int]:
    """Return a fail-closed, non-mutating status for the fixed permit path."""

    probe = HeldReader(root)
    try:
        kind = probe.path_kind(PERMIT_PATH)
        probe.verify()
    except (PermitError, OSError) as error:
        probe.close()
        return (
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "execution-permit-preflight"
                ),
                "schemaVersion": "1.0",
                "status": "permit_probe_invalid_not_authorized",
                "validationPassed": False,
                "reviewExecutionAuthorized": False,
                "error": str(error),
                "archiveMemberInspectionCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            },
            1,
        )
    else:
        probe.close()
    if kind == "absent":
        return (
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "execution-permit-preflight"
                ),
                "schemaVersion": "1.0",
                "status": "permit_absent_not_authorized",
                "validationPassed": False,
                "reviewExecutionAuthorized": False,
                "archiveMemberInspectionCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            },
            1,
        )
    if kind != "file":
        return (
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "execution-permit-preflight"
                ),
                "schemaVersion": "1.0",
                "status": "permit_path_invalid_not_authorized",
                "validationPassed": False,
                "reviewExecutionAuthorized": False,
                "archiveMemberInspectionCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            },
            1,
        )
    try:
        result = validate_repository(root)
    except (PermitError, OSError) as error:
        return (
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "execution-permit-preflight"
                ),
                "schemaVersion": "1.0",
                "status": "permit_invalid_not_authorized",
                "validationPassed": False,
                "reviewExecutionAuthorized": False,
                "error": str(error),
                "archiveMemberInspectionCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            },
            1,
        )
    return (
        {
            key: value
            for key, value in result.items()
            if key
            not in {
                "permit",
                "decision",
                "recoveryDecision",
                "v1RecoveryDecision",
                "v1Permit",
                "v1Claim",
                "v1Failure",
                "v2Permit",
                "v2Claim",
                "v2Failure",
            }
        }
        | {"validationPassed": True},
        0,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.parse_args(argv)
    status_value, exit_code = preflight_status(ROOT)
    print(canonical_json_bytes(status_value).decode("utf-8"), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
