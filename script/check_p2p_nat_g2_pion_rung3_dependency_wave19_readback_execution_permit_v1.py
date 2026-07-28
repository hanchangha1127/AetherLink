#!/usr/bin/env python3
"""Validate the one-use offline Wave19 acquisition readback permit."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("Wave19 readback checker requires `python3 -I -B -S`")

import argparse
import ast
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
from typing import Any, Mapping, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", None)
if O_NOFOLLOW is None:
    raise RuntimeError("Wave19 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave19_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave19_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave19_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-19-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave19-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave19-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-19-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-19-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-failure-v1.json"
)
STAGING_PREFIX = ".wave-19-v1-staging-"
ATTEMPT_ID = "f10c20196d994afe3a8eba830eb42614"
EXPECTED_DECISION_CONTENT = (
    "39edf590a88d728a105c74ef0eeb1600c84159888d3b4edbbe4acba05e7a6f56"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "b84a1914f84bec8f02197042e2576ed74a85063f3d0c37c6515ab64638caf286"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "97f4d8c1775c01c27f83f19b66af6274e0ae77b1be328456c2685ba18552b6e7"
)
EXPECTED_RESOURCES_CANONICAL = (
    "e5effbf132773b38711521ab3da4fec70732867556024fe997a4f735027ce484"
)
EXPECTED_COMPACT_IDENTITY = (
    "a3f5a20989a886accb15c79d8c47202c38a84e8d42fe54e44da7b598bd44534b"
)
EXPECTED_FULL_WITNESS = (
    "6fd00b2ec910ef9dae4a3f03dc74105038f1ae855092366509c509e8394c5e7d"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "72c1253423412744380ed5c7f8b74f9d5b34daaefd05caf5b384d9bb55589490"
)
EXPECTED_V17_CHECKER_NORMALIZED = (
    "d2ebef7f9aad384b08a68c438320de882d640a859a7d35521853818afbcdd7ce"
)
EXPECTED_V17_CONTENT = (
    "1267edbe7f1a4f2554808376f67c6ba25a9217db0e6e2cc80a0822d780710f78"
)
EXPECTED_V17_INPUT_SET = (
    "79f2c8e28daf3f46c97d827cdc7416b77905eea49bc482911f8d234e0de3765f"
)
EXPECTED_V17_GRAPH = (
    "cc748b6a5285321d8e74abab1c881dbc5ffd4433865ba9c75e459152f459092e"
)
EXPECTED_V17_FRONTIER = (
    "4a7998ef0c1e5716640cccf9c5b349e92124bd787a2ca4090e3ba0920b68b006"
)
EXPECTED_ACCEPTED_RESOURCE_HASH_SET = (
    "a98db8197e88a28464082ef00a9700550652f46e3026993dd3adddcda50280d0"
)
EXPECTED_FROZEN_FILES_CANONICAL = (
    "a95ea05b73ce1b4c8f4781eb313f2a58071f288c7872a203bfd58bacc3ed68b1"
)
PLACEHOLDER_SHA256 = "0" * 64
EXPECTED_READER_RAW = (
    "c37e61846c174e8fb238e9e1e6639c7dae9d89fe00308176bab2f3d83618fb46"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "c469bd570613e1330e8f8c697a1d0c65061cb9e8307f4dc74f4153f34d443e32"
)
EXPECTED_RECORDER_AST_CALL_SURFACE_SHA256 = (
    "a758f79bea56fab79178ff611d80575fe31a97f0ac9848d42ea78c52541b0fa7"
)
MAXIMUM_PACKAGE_FILE_BYTES = 8 * 1024 * 1024


def frozen(
    path: str,
    digest: str,
    size: int,
    mode: str,
    owner_uid: int = 501,
    link_count: int = 1,
) -> dict[str, Any]:
    return {
        "path": path,
        "rawSha256": digest,
        "bytes": size,
        "mode": mode,
        "ownerUid": owner_uid,
        "linkCount": link_count,
    }


ACQUISITION_AUTHORITY = [
    frozen(
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave19-v1.json",
        "7486a8a4659459ce49128bcf05501abb065f2b64c542715eaebd3c1ca686a8cf",
        10_205,
        "0644",
    ),
    frozen(
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave19-v1.md",
        "3aefdd1e3a283e099ad4a3624103461eee821043ad4bf18a57a39c81b100d526",
        6_113,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_decision_v1.py",
        "cd6926a344b52fafd0265ec8bd1f08cbdf250826fa53e46e6c5a3e94049f0d92",
        33_784,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave19_decision_v1.py",
        "2bd972108f75739be378c20544eaa518425ad875156cf83065f27fb34d2a47d2",
        47_545,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v17.py",
        "32df9bd1bf9b4b6610a2a74038956eab7e51c506198c11f45fa5058968caacb8",
        239_088,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_combined_fixed_point_v17.py",
        "3403ec05b1f6a9561a74a44b001352230d0d68db72789403f6155785f01588f0",
        169_253,
        "0644",
    ),
    frozen(
        "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-18-v1.claim",
        "08f5134ce03805e512c2dec0dee13251ce682d793d2b87f7f8e29f6d3426d362",
        416,
        "0600",
    ),
    frozen(
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave19-execution-permit-v1.md",
        "5bca347cbe948bc82912464aca23b43e8d0323204ad33289ed8d42be3ddec977",
        3_866,
        "0644",
    ),
    frozen(
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave19-execution-permit-v1.json",
        "ea80d045fb13042f2c673dcd3363a46aaf4bc81ffbe65af53e9ecd65b1369a3e",
        17_488,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py",
        "9fc0b1eae88a029ae3f3c180acdfbb2f296736c8745cebc75248efe3aa2bc435",
        60_177,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py",
        "aeaee4516fae2630b1cf803f467a191dddfa12011f990201a854cd6def3adbbb",
        44_959,
        "0644",
    ),
    frozen(
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py",
        "c9c197b247cc8f9bdcc581ab3e56e87d0ba1de6d568a6826b7ad839dc64a96a3",
        95_532,
        "0644",
    ),
    frozen(
        "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py",
        "9c9514e23d5a9abe0d69a9ae3c8af210ebd477206b08a964b41c29c07d37d47f",
        93_146,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py",
        "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd",
        34_617,
        "0644",
    ),
    frozen(
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py",
        "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b",
        54_352,
        "0644",
    ),
]
ACQUISITION_CLAIM = frozen(
    ACQUISITION_CLAIM_PATH,
    "0454a51b04fd51c967221e7b1ca178b6d750cddec2ea4fc884ada61af6e2f6c1",
    416,
    "0600",
)
FINAL_DIRECTORY = {
    "path": FINAL_ROOT,
    "mode": "0700",
    "ownerUid": 501,
    "linkCount": 4,
    "exactEntries": ["accepted", "evidence.json"],
}
ACCEPTED_DIRECTORY = {
    "path": ACCEPTED_ROOT,
    "mode": "0700",
    "ownerUid": 501,
    "linkCount": 6,
    "exactFileCount": 4,
}
EVIDENCE_FILE = frozen(
    EVIDENCE_PATH,
    "9e108c036f7ba30b7dc0f9cbfe88390b783f2f8b0658b32a24020bed36060b4a",
    1_865,
    "0600",
)


_ACCEPTED_ROWS = [
    (
        "001-a26a2513c9f4c49c479c.mod",
        "e9c23d3613ad3c29e18552f90d02798b7295419dd47d4f667d5843d7dc1673b3",
        192,
    ),
    (
        "001-a26a2513c9f4c49c479c.zip",
        "02824dd62fa3241946a2ac14fdadbd393514d76cebbfbd8bddcddbfc80c7f94b",
        2_219_369,
    ),
    (
        "002-c6022d5be99f60f2428e.mod",
        "8133f6f3b232cb388b50d1c74be92f39198cbd62e3b0991c917cdbc1322bbe14",
        223,
    ),
    (
        "002-c6022d5be99f60f2428e.zip",
        "3f218b1dd9a690036d1226f46f142fc7ae3cc9cd4f28610b96bb8080b7e194c9",
        9_234_171,
    ),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "97e208dde0b41dfe400ed948ae8636d7e2e25bf644d4fda6beb057d97e9a746e",
    1_662,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "eed663ad8e0ce4e1a3300d3666ad879223a1aaa4b0adc107a6293123499d0de8",
    465,
    "0600",
)
ALL_FROZEN_FILES = [
    *ACQUISITION_AUTHORITY,
    ACQUISITION_CLAIM,
    EVIDENCE_FILE,
    *ACCEPTED_FILES,
    ACQUISITION_RECEIPT,
    ACQUISITION_MANIFEST,
]


class PermitError(RuntimeError):
    def __init__(self, code: str, state: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.state = state


def require(value: bool, code: str) -> None:
    if not value:
        raise PermitError(code)


def is_sealed() -> bool:
    return (
        EXPECTED_READER_RAW != PLACEHOLDER_SHA256
        and EXPECTED_RECORDER_NORMALIZED_SHA256 != PLACEHOLDER_SHA256
    )


def require_sealed() -> None:
    require(is_sealed(), "E_UNSEALED_STRUCTURE")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def has_portable_prefix(
    names: Sequence[str],
    prefixes: Sequence[str],
) -> bool:
    portable_prefixes = [portable_name(prefix) for prefix in prefixes]
    return any(
        portable_name(name).startswith(prefix)
        for name in names
        for prefix in portable_prefixes
    )


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def exact_json_equal(observed: Any, expected: Any) -> bool:
    if type(observed) is not type(expected):
        return False
    if type(expected) is dict:
        return (
            set(observed) == set(expected)
            and all(
                exact_json_equal(observed[key], expected[key])
                for key in expected
            )
        )
    if type(expected) is list:
        return (
            len(observed) == len(expected)
            and all(
                exact_json_equal(left, right)
                for left, right in zip(observed, expected)
            )
        )
    return observed == expected


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
            parse_float=lambda _: (_ for _ in ()).throw(PermitError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(PermitError("E_JSON")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    require("contentBinding" not in payload, "E_CONTENT")
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def verify_bound(raw: bytes, expected: Mapping[str, Any]) -> None:
    observed = strict_json(raw)
    require(
        raw == canonical_bytes(observed)
        and exact_json_equal(observed, expected),
        "E_PERMIT",
    )
    binding = observed["contentBinding"]
    unbound = dict(observed)
    del unbound["contentBinding"]
    require(
        binding
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": sha256(canonical_bytes(unbound)),
        },
        "E_CONTENT",
    )


def _safe_relative(path: str) -> list[str]:
    require(
        type(path) is str
        and path
        and not path.startswith("/")
        and all(part not in {"", ".", ".."} for part in path.split("/")),
        "E_PATH",
    )
    return path.split("/")


def _directory_anchor(info: os.stat_result) -> tuple[int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IMODE(info.st_mode),
        info.st_uid,
    )


def _open_to_owner(
    owner: list[int],
    opener: Any,
) -> int:
    """Defer SIGALRM/SIGINT only across open-to-owner transfer."""
    previous_mask = signal.pthread_sigmask(
        signal.SIG_BLOCK,
        {signal.SIGALRM, signal.SIGINT},
    )
    fd = -1
    transferred = False
    primary_error: BaseException | None = None
    try:
        try:
            fd = opener()
            owner.append(fd)
            transferred = True
        except BaseException as error:
            primary_error = error
        if fd >= 0 and not transferred:
            try:
                os.close(fd)
            except BaseException as error:
                if primary_error is None:
                    primary_error = error
            fd = -1
    except BaseException as error:
        primary_error = error
    restore_error: BaseException | None = None
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    except BaseException as error:
        restore_error = error
    if primary_error is not None:
        if restore_error is not None:
            raise primary_error from restore_error
        raise primary_error
    if restore_error is not None:
        raise restore_error
    return fd


def _remove_owned_fd(owner: list[int], fd: int) -> None:
    while fd in owner:
        owner.remove(fd)


def _attempt_close_owned_fd(
    owner: list[int],
    fd: int,
) -> BaseException | None:
    """Retry only a reported close failure in this single-threaded checker."""
    if fd not in owner:
        return None
    first_error: BaseException | None = None
    for _ in range(2):
        try:
            os.close(fd)
        except OSError as error:
            if error.errno == errno.EBADF:
                _remove_owned_fd(owner, fd)
                return None
            if first_error is None:
                first_error = error
        except BaseException as error:
            if first_error is None:
                first_error = error
        else:
            _remove_owned_fd(owner, fd)
            return None
        try:
            os.fstat(fd)
        except OSError as error:
            if error.errno == errno.EBADF:
                _remove_owned_fd(owner, fd)
                return None
            if first_error is None:
                first_error = error
        except BaseException as error:
            if first_error is None:
                first_error = error
        else:
            continue
    return first_error or OSError(
        errno.EIO,
        "file descriptor closure could not be verified",
    )


def _close_owned_fds(owner: list[int]) -> None:
    """Attempt every FD and retain ownership of any observably open FD."""
    errors: list[BaseException] = []
    previous_mask: set[signal.Signals] | None = None
    try:
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGINT},
        )
    except BaseException as error:
        errors.append(error)
    seen: set[int] = set()
    for fd in reversed(tuple(owner)):
        if fd < 0 or fd in seen:
            continue
        seen.add(fd)
        error = _attempt_close_owned_fd(owner, fd)
        if error is not None:
            errors.append(error)
    if previous_mask is not None:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        except BaseException as error:
            errors.append(error)
    if errors:
        raise errors[0]


class HeldTraversal:
    """Hold root-relative directory components and opened files until cleanup."""

    def __init__(self, root: Path) -> None:
        self.root = root.absolute()
        self.owned: list[int] = []
        self.directories: dict[str, tuple[int, os.stat_result, int, str]] = {}
        self.closed = False
        self.root_fd = -1
        self.root_initial: os.stat_result | None = None
        try:
            self.root_fd = _open_to_owner(
                self.owned,
                lambda: os.open(
                    self.root,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC
                    | O_NOFOLLOW,
                ),
            )
            self.root_initial = os.fstat(self.root_fd)
            self._validate_directory(self.root_initial)
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_PATH",
        )

    def directory(self, path: str) -> int:
        parts = _safe_relative(path)
        current = self.root_fd
        prefix: list[str] = []
        for component in parts:
            prefix.append(component)
            key = "/".join(prefix)
            existing = self.directories.get(key)
            if existing is not None:
                current = existing[0]
                continue
            parent = current
            child = _open_to_owner(
                self.owned,
                lambda component=component, parent=parent: os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC
                    | O_NOFOLLOW,
                    dir_fd=parent,
                ),
            )
            try:
                info = os.fstat(child)
                self._validate_directory(info)
                self.directories[key] = (child, info, parent, component)
                current = child
            except BaseException:
                # Ownership is already registered; close() performs the
                # signal-guarded all-FD cleanup even on validation failure.
                raise
        return current

    def file(self, path: str) -> int:
        parts = _safe_relative(path)
        parent = (
            self.directory("/".join(parts[:-1]))
            if len(parts) > 1
            else self.root_fd
        )
        return _open_to_owner(
            self.owned,
            lambda: os.open(
                parts[-1],
                os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | O_NOFOLLOW,
                dir_fd=parent,
            ),
        )

    def exists(self, path: str) -> bool:
        parts = _safe_relative(path)
        parent = (
            self.directory("/".join(parts[:-1]))
            if len(parts) > 1
            else self.root_fd
        )
        try:
            os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def barrier(self) -> None:
        current_root = os.stat(self.root, follow_symlinks=False)
        held_root = os.fstat(self.root_fd)
        require(
            _directory_anchor(current_root)
            == _directory_anchor(held_root)
            == _directory_anchor(self.root_initial),
            "E_PATH",
        )
        for fd, initial, parent, component in self.directories.values():
            held = os.fstat(fd)
            named = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            require(
                _directory_anchor(held)
                == _directory_anchor(named)
                == _directory_anchor(initial),
                "E_PATH",
            )

    def close(self) -> None:
        if self.closed:
            return
        _close_owned_fds(self.owned)
        self.directories.clear()
        self.root_fd = -1
        self.closed = True

    def __enter__(self) -> "HeldTraversal":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def stable_read(path: str) -> bytes:
    with HeldTraversal(ROOT) as traversal:
        fd = traversal.file(path)
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_PACKAGE_FILE_BYTES,
            "E_SHAPE",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(fd, 1), "E_READ")
        raw = b"".join(chunks)
        require(os.fstat(fd) == before, "E_CHANGED")
        traversal.barrier()
        return raw


def normalized_recorder(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    pattern = re.compile(r'EXPECTED_READBACK_CHECKER_RAW = "[0-9a-f]{64}"')
    require(len(pattern.findall(text)) == 1, "E_RECORDER")
    return pattern.sub(
        'EXPECTED_READBACK_CHECKER_RAW = "' + "0" * 64 + '"',
        text,
        count=1,
    ).encode()


def validate_recorder(recorder_raw: bytes, checker_raw: bytes) -> None:
    require_sealed()
    try:
        source = recorder_raw.decode("utf-8", errors="strict")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise PermitError("E_RECORDER") from error
    imports: list[str] = []
    function_counts: dict[str, int] = {}
    call_counts: dict[str, int] = {}

    def dotted_name(node: ast.AST) -> str | None:
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_counts[node.name] = function_counts.get(node.name, 0) + 1
        elif isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name is not None:
                call_counts[name] = call_counts.get(name, 0) + 1
    expected_imports = {
        "__future__",
        "sys",
        "argparse",
        "base64",
        "binascii",
        "ctypes",
        "errno",
        "hashlib",
        "io",
        "json",
        "os",
        "pathlib",
        "re",
        "secrets",
        "signal",
        "stat",
        "struct",
        "types",
        "typing",
        "unicodedata",
        "zipfile",
        "zlib",
    }
    require(
        len(imports) == len(expected_imports)
        and set(imports) == expected_imports,
        "E_RECORDER",
    )
    require(
        not any(
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave19" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition"
            in name
            for name in imports
        ),
        "E_RECORDER",
    )
    require(
        all(
            function_counts.get(name) == 1
            for name in {
            "load_readback_checker",
            "_open_to_owner",
            "_close_owned_fd",
            "_close_owned_fds",
            "create_readback_claim",
            "verify_snapshot",
            "validate_mod",
            "validate_zip",
            "atomic_publish",
            "preflight",
            "execute",
            "validate_argument_vector",
            }
        ),
        "E_RECORDER",
    )
    exact_sensitive_calls = {
        "compile": 1,
        "exec": 1,
        "load_readback_checker": 1,
        "PERMIT.package_preflight_for_recorder": 1,
        "create_readback_claim": 1,
        "verify_snapshot": 2,
        "validate_mod": 1,
        "validate_zip": 1,
        "atomic_publish": 2,
        "preflight": 2,
        "execute": 1,
        "validate_argument_vector": 1,
    }
    require(
        all(
            call_counts.get(name, 0) == count
            for name, count in exact_sensitive_calls.items()
        ),
        "E_RECORDER",
    )
    require(
        sha256(canonical_bytes(call_counts))
        == EXPECTED_RECORDER_AST_CALL_SURFACE_SHA256,
        "E_RECORDER",
    )
    forbidden_call_fragments = (
        "input",
        "getpass",
        "socket",
        "subprocess",
        "urlopen",
        "HTTPConnection",
        "HTTPSConnection",
        "create_connection",
        "check_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition",
        "acquire_p2p_nat_g2_pion_rung3_dependency_wave19",
    )
    require(
        not any(
            any(fragment in name for fragment in forbidden_call_fragments)
            for name in call_counts
        ),
        "E_RECORDER",
    )
    for token in (
        "http.client",
        "HTTPSConnection",
        "urlopen",
        "socket.",
        "subprocess",
        "os.system",
        "getpass",
        "input(",
    ):
        require(token not in source, "E_RECORDER")
    for token in (
        "os.O_EXCL",
        "O_NOFOLLOW",
        "os.fsync",
        "renameatx_np",
        "ZIP_CENTRAL_HEADER",
        "zlib.decompressobj",
        "MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP",
        "MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL",
        "signal.pthread_sigmask",
        "execute_success_recorded",
        "consumed_success_reporting_failed",
        "E_POST_SUCCESS_REPORTING",
        "allow_abbrev=False",
    ):
        require(token in source, "E_RECORDER")
    pin = re.findall(
        r'EXPECTED_READBACK_CHECKER_RAW = "([0-9a-f]{64})"',
        source,
    )
    require(pin == [sha256(checker_raw)], "E_RECORDER")
    require(
        sha256(normalized_recorder(recorder_raw))
        == EXPECTED_RECORDER_NORMALIZED_SHA256,
        "E_RECORDER",
    )


def package_raw(include_permit: bool) -> dict[str, bytes]:
    require_sealed()
    paths = [
        READER_PATH,
        THIS_CHECKER_PATH,
        THIS_TESTS_PATH,
        RECORDER_PATH,
        RECORDER_TESTS_PATH,
    ]
    if include_permit:
        paths.append(PERMIT_PATH)
    return {path: stable_read(path) for path in paths}


def frozen_snapshot_payload() -> dict[str, Any]:
    frozen_canonical = [
        *ACQUISITION_AUTHORITY,
        ACQUISITION_CLAIM,
        EVIDENCE_FILE,
        *ACCEPTED_FILES,
        ACQUISITION_RECEIPT,
        ACQUISITION_MANIFEST,
    ]
    frozen_canonical_sha256 = sha256(canonical_bytes(frozen_canonical))
    require(
        len(frozen_canonical) == 23
        and frozen_canonical_sha256 == EXPECTED_FROZEN_FILES_CANONICAL,
        "E_FROZEN_BINDING",
    )
    return {
        "attemptId": ATTEMPT_ID,
        "acquisitionAuthority": ACQUISITION_AUTHORITY,
        "acquisitionDecisionContentSha256": EXPECTED_DECISION_CONTENT,
        "acquisitionPermitContentSha256": EXPECTED_ACQUISITION_PERMIT_CONTENT,
        "identityBindings": {
            "sourceRequestSetCanonicalSha256": (
                EXPECTED_SOURCE_REQUEST_SET_CANONICAL
            ),
            "resourcesCanonicalSha256": EXPECTED_RESOURCES_CANONICAL,
            "compactIdentitySha256": EXPECTED_COMPACT_IDENTITY,
            "fullWitnessSha256": EXPECTED_FULL_WITNESS,
            "heldSourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
        },
        "predecessorBindings": {
            "combinedFixedPointV17": {
                "checkerPath": (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_v17.py"
                ),
                "checkerRawSha256": (
                    "32df9bd1bf9b4b6610a2a74038956eab7e51c506198c11f45fa5058968caacb8"
                ),
                "checkerNormalizedSha256": EXPECTED_V17_CHECKER_NORMALIZED,
                "testsPath": (
                    "script/test_p2p_nat_g2_pion_combined_fixed_point_v17.py"
                ),
                "testsRawSha256": (
                    "3403ec05b1f6a9561a74a44b001352230d0d68db72789403f6155785f01588f0"
                ),
                "contentSha256": EXPECTED_V17_CONTENT,
                "combinedInputSetSha256": EXPECTED_V17_INPUT_SET,
                "graphSha256": EXPECTED_V17_GRAPH,
                "frontierSha256": EXPECTED_V17_FRONTIER,
                "sourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
                "totalFullSourceReconstructionCount": 32,
                "totalGraphArchiveOpenCount": 4_422,
                "wave18NamespaceAnchor": {
                    "path": (
                        "build/offline-source/pion-ice-v4.3.0/"
                        "dependencies/.wave-18-v1.claim"
                    ),
                    "rawSha256": (
                        "08f5134ce03805e512c2dec0dee13251c"
                        "e682d793d2b87f7f8e29f6d3426d362"
                    ),
                },
            },
        },
        "acquisitionClaim": ACQUISITION_CLAIM,
        "finalDirectory": FINAL_DIRECTORY,
        "evidence": EVIDENCE_FILE,
        "acceptedDirectory": {
            **ACCEPTED_DIRECTORY,
            "files": ACCEPTED_FILES,
        },
        "acquisitionReceipt": ACQUISITION_RECEIPT,
        "acquisitionManifest": ACQUISITION_MANIFEST,
        "absenceContract": {
            "failurePath": ACQUISITION_FAILURE_PATH,
            "stagingParent": DEPENDENCY_ROOT,
            "stagingPrefix": STAGING_PREFIX,
            "portableNameComparison": "NFC_casefold",
            "failureAbsent": True,
            "stagingAbsent": True,
        },
        "frozenFileCount": len(frozen_canonical),
        "frozenFilesCanonicalSha256": frozen_canonical_sha256,
        "aggregateModBytes": 415,
        "aggregateZipBytes": 11_453_540,
        "aggregateAcceptedBytes": 11_453_955,
        "aggregateZipEntryCount": 931,
        "aggregateZipUncompressedBytes": 46_404_827,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "acceptedResourceCount": 4,
        "selectedTupleCount": 0,
        "selectedRequestOrdinals": [],
        "modCount": 2,
        "zipCount": 2,
    }


def expected_payload_from_package(raw: Mapping[str, bytes]) -> dict[str, Any]:
    require_sealed()
    require(sha256(raw[READER_PATH]) == EXPECTED_READER_RAW, "E_READER")
    validate_recorder(raw[RECORDER_PATH], raw[THIS_CHECKER_PATH])
    tools = [
        {"path": path, "rawSha256": sha256(raw[path])}
        for path in (
            THIS_CHECKER_PATH,
            THIS_TESTS_PATH,
            RECORDER_PATH,
            RECORDER_TESTS_PATH,
        )
    ]
    return {
        "documentType": (
            "aetherlink.wave19-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave19-source-acquisition-readback-"
            "execution-permit-v1"
        ),
        "recordedDate": "2026-07-28",
        "status": "authorized_not_consumed",
        "frozenAcquisitionSnapshot": frozen_snapshot_payload(),
        "verificationContract": {
            "claimDurableBeforeAnyFrozenAcquisitionInputOpen": True,
            "authorityFilesOpenedAndHeldFirst": True,
            "allFrozenFilesOpenedNoFollowAndHeld": True,
            "intermediateDirectoryComponentsOpenedNoFollowAndHeld": True,
            "openToOwnershipTransferDefersOnlySigalrmAndSigint": True,
            "cleanupClosesEveryOwnedFdBeforeSignalMaskRestore": True,
            "retainedProjectRootCurrentPathIdentityCheckedAtEachPreManifestBarrier": True,
            "eachPreManifestBarrierReopensEveryCurrentPathNoFollow": True,
            "currentPathDeviceAndInodeMustMatchHeldObjectAtEachPreManifestBarrier": True,
            "frozenSnapshotHeldFdBytesReverifiedImmediatelyBeforeManifestPublication": True,
            "readbackClaimCurrentPathIdentityReverifiedImmediatelyBeforeManifestPublication": True,
            "readbackReceiptCurrentPathIdentityReverifiedImmediatelyBeforeManifestPublication": True,
            "claimCreationFdHeldAtImmediatelyBeforeManifestBarrier": True,
            "currentPathIdentityGuaranteedThroughManifestPublication": False,
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
            "completionAppliesToRetainedSnapshot": True,
            "publishedOutputsReopenedAndVerifiedBeforePublishReturns": True,
            "pathSha256BytesModeOwnerAndLinkCountRequired": True,
            "exactFinalAndAcceptedDirectoryInventoriesRequired": True,
            "strictCanonicalTerminalAndEvidenceJsonRequired": True,
            "decisionAndPermitContentBindingsRecomputed": True,
            "attemptAndAuthorityBindingsRecomputed": True,
            "exact4ResourceOrderAndAggregateRecomputed": True,
            "exact23FrozenFileSnapshotRequired": True,
            "acceptedResourceHashSetCanonicalSha256Recomputed": True,
            "requestResourcesCanonicalSha256Recomputed": True,
            "combinedFixedPointV17PredecessorBindingRecomputed": True,
            "v17TestsLiveHeld": True,
            "v16TestsLiveHeld": False,
            "identityAndSourceRequestSetBindingsRecomputed": True,
            "goModH1RecomputedIndependently": True,
            "moduleZipH1RecomputedIndependently": True,
            "zipStructurePathCrcAndModParityRecomputed": True,
            "completeVerificationPassCount": 2,
            "retainedFdPreManifestBarrierCount": 3,
            "retainedFdPreManifestBarriers": [
                "complete_snapshot_and_claim_immediately_before_receipt",
                "complete_snapshot_claim_and_receipt_after_receipt",
                (
                    "complete_snapshot_claim_and_receipt_"
                    "immediately_before_manifest_publication"
                ),
            ],
            "allRequiredPreManifestBarriersCompleteImmediatelyBeforeManifestPublication": True,
            "requiredFallibleBarrierAfterManifest": False,
            "acquisitionCheckerOrRunnerImportAllowed": False,
            "acquisitionCheckerOrRunnerInvocationAllowed": False,
            "sourceExtractionAllowed": False,
            "executeSuccessRecordedBeforeStdoutReporting": True,
            "postSuccessReportingFailure": {
                "status": "consumed_success_reporting_failed",
                "failureCode": "E_POST_SUCCESS_REPORTING",
                "failurePhase": "reporting",
                "retryAllowed": False,
                "readbackPublicationComplete": True,
                "completionAppliesToRetainedSnapshot": True,
            },
        },
        "oneUseConsumption": {
            "claimPath": READBACK_CLAIM_PATH,
            "claimCreatedOExclNoFollow0600AndFsynced": True,
            "claimParentFsyncedBeforeFrozenInputOpen": True,
            "claimCreatedReadWriteAndCreationFdTransferredToHold": True,
            "claimPersistsAfterSuccessFailureOrUncertainty": True,
            "existingClaimState": "already_consumed",
            "claimDurabilityAmbiguityState": "consumed_terminal_state_uncertain",
            "secondExecutionAllowed": False,
            "retryAllowed": False,
            "resumeAllowed": False,
            "replacementAllowed": False,
            "backfillAllowed": False,
            "namespaceStates": {
                "claimOnly": "claim_only",
                "receiptOnly": "receipt_only",
                "complete": "complete",
                "inconsistent": "inconsistent",
                "staleTemporary": "stale_temporary_namespace",
            },
        },
        "outputContract": {
            "receiptPath": READBACK_RECEIPT_PATH,
            "manifestPath": READBACK_MANIFEST_PATH,
            "receiptWrittenBeforeManifest": True,
            "manifestWrittenLast": True,
            "atomicNoReplaceRequired": True,
            "fileMode": "0600",
            "fileAndParentFsyncRequired": True,
            "ordinaryFailurePublishesSuccess": False,
            "failureOutputAuthorized": False,
            "receiptOnlyGapState": "consumed_terminal_state_uncertain",
            "publicationDurabilityAmbiguityState": (
                "consumed_terminal_state_uncertain"
            ),
            "temporaryNamePrefixes": READBACK_TEMP_PREFIXES,
            "temporaryNameComparison": "NFC_casefold",
            "preflightRejectsAnyStaleTemporaryName": True,
            "manifestPublicationFollowsLastPreManifestBarrierWithoutFrozenInputRecheck": True,
            "fallibleFrozenClaimOrReceiptBarrierAfterManifest": False,
            "currentPathIdentityGuaranteedThroughManifestPublication": False,
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
            "completionAppliesToRetainedSnapshot": True,
            "executeSuccessRecordedBeforeStdoutReporting": True,
            "postSuccessReportingFailureStatus": (
                "consumed_success_reporting_failed"
            ),
            "publicationOrder": [
                "rename_no_replace",
                "parent_directory_fsync",
                "final_name_no_follow_reopen_and_source_inode_verification",
                "return",
            ],
        },
        "resourceLimits": {
            "maximumPackageFileBytes": MAXIMUM_PACKAGE_FILE_BYTES,
            "maximumAcceptedResourceCount": 4,
            "maximumModBytes": 1_048_576,
            "maximumZipBytes": 16_777_216,
            "maximumAggregateModBytes": 2_097_152,
            "maximumAggregateZipBytes": 33_554_432,
            "maximumAggregateAcceptedBytes": 35_651_584,
            "maximumZipEntriesPerZip": 20_000,
            "maximumZipEntriesAcrossAll": 40_000,
            "maximumZipEntryNameBytes": 1_024,
            "maximumZipEntryBytes": 134_217_728,
            "maximumZipUncompressedBytesPerZip": 134_217_728,
            "maximumZipUncompressedBytesAcrossAll": 268_435_456,
        },
        "authority": {
            "offlineReadbackAuthorizedOnce": True,
            "readbackClaimWriteAuthorized": True,
            "readbackReceiptWriteAuthorized": True,
            "readbackManifestWriteAuthorized": True,
            "sameDirectoryTemporaryPublicationAuthorized": True,
            "failedTemporaryCleanupAuthorized": True,
            "otherRepositoryWritesAuthorized": False,
            "frozenInputWritesAuthorized": False,
            "networkAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "proxyAuthorized": False,
            "authenticationRequired": False,
            "credentialRequired": False,
            "externalAuthenticationRequired": False,
            "repositoryOwnerIdentityProofRequired": False,
            "ownerProofRequired": False,
            "accountRequired": False,
            "ownerRequired": False,
            "sshRequired": False,
            "gpgRequired": False,
            "passwordRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
            "cookieRequired": False,
            "clientCertificateRequired": False,
            "sourceAcquisitionAuthorized": False,
            "sourceExtractionAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "userActionRequired": False,
        },
        "interpreterContract": {
            "command": [
                "python3",
                "-I",
                "-B",
                "-S",
                RECORDER_PATH,
                "--execute",
            ],
            "isolated": True,
            "sitePackagesAllowed": False,
            "environmentOverridesAllowed": False,
            "bytecodeWritesAllowed": False,
            "processUmask": "077",
            "productionExactArgv": ["--execute"],
            "readOnlyPreflightExactArgv": ["--preflight"],
            "additionalArgumentsAllowed": False,
            "duplicateArgumentsAllowed": False,
            "abbreviatedArgumentsAllowed": False,
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW,
        },
        "toolBindings": tools,
        "recorderNormalizedSha256": EXPECTED_RECORDER_NORMALIZED_SHA256,
        "result": (
            "exact_offline_wave19_retained_snapshot_readback_"
            "authorized_not_consumed"
        ),
        "nextAction": "execute_bound_offline_readback_once",
        "nonClaims": [
            "this permit does not authorize another source acquisition",
            "readback success is not source review or dependency closure",
            "readback success is not library selection release approval or V1 completion",
            (
                "the standalone live permit checker is a sequential diagnostic, "
                "not an atomic concurrent snapshot; execution safety relies on "
                "the recorder retained-FD and pre-manifest current-path barriers"
            ),
            (
                "same-UID rename or replacement after the last pre-manifest "
                "barrier is not prevented; completion applies to the retained "
                "snapshot, not continuous current-path identity"
            ),
        ],
    }


def expected_package(include_permit: bool) -> tuple[dict[str, Any], dict[str, bytes]]:
    raw = package_raw(include_permit)
    return content_bound(expected_payload_from_package(raw)), raw


def _audit_file(
    traversal: HeldTraversal,
    spec: Mapping[str, Any],
) -> None:
    fd = traversal.file(spec["path"])
    before = os.fstat(fd)
    require(
        stat.S_ISREG(before.st_mode)
        and before.st_size == spec["bytes"]
        and stat.S_IMODE(before.st_mode) == int(spec["mode"], 8)
        and before.st_uid == spec["ownerUid"]
        and before.st_nlink == spec["linkCount"],
        "E_FROZEN",
    )
    digest = hashlib.sha256()
    remaining = before.st_size
    while remaining:
        chunk = os.read(fd, min(65_536, remaining))
        require(bool(chunk), "E_READ")
        digest.update(chunk)
        remaining -= len(chunk)
    require(
        not os.read(fd, 1)
        and digest.hexdigest() == spec["rawSha256"]
        and os.fstat(fd) == before,
        "E_FROZEN",
    )


def _audit_directory(
    traversal: HeldTraversal,
    spec: Mapping[str, Any],
    expected: set[str],
) -> None:
    fd = traversal.directory(spec["path"])
    info = os.fstat(fd)
    require(
        stat.S_ISDIR(info.st_mode)
        and stat.S_IMODE(info.st_mode) == int(spec["mode"], 8)
        and info.st_uid == spec["ownerUid"]
        and info.st_nlink == spec["linkCount"]
        and set(os.listdir(fd)) == expected,
        "E_INVENTORY",
    )


def audit_frozen_snapshot() -> None:
    with HeldTraversal(ROOT) as traversal:
        for spec in ALL_FROZEN_FILES:
            _audit_file(traversal, spec)
        _audit_directory(
            traversal,
            FINAL_DIRECTORY,
            set(FINAL_DIRECTORY["exactEntries"]),
        )
        accepted_names = {Path(row["path"]).name for row in ACCEPTED_FILES}
        _audit_directory(
            traversal,
            ACCEPTED_DIRECTORY,
            accepted_names,
        )
        require(
            not traversal.exists(ACQUISITION_FAILURE_PATH),
            "E_TERMINAL",
        )
        dependency = traversal.directory(DEPENDENCY_ROOT)
        require(
            not has_portable_prefix(
                os.listdir(dependency),
                [STAGING_PREFIX],
            ),
            "E_TERMINAL",
        )
        traversal.barrier()


def readback_namespace_state(root: Path = ROOT) -> str:
    traversal = HeldTraversal(root)
    observed_state: str | None = None
    try:
        claim = traversal.exists(READBACK_CLAIM_PATH)
        receipt = traversal.exists(READBACK_RECEIPT_PATH)
        manifest = traversal.exists(READBACK_MANIFEST_PATH)
        names = os.listdir(traversal.directory(BASE))
        traversal.barrier()
        if has_portable_prefix(names, READBACK_TEMP_PREFIXES):
            observed_state = "stale_temporary_namespace"
        elif not claim and not receipt and not manifest:
            observed_state = "absent"
        elif claim and not receipt and not manifest:
            observed_state = "claim_only"
        elif claim and receipt and not manifest:
            observed_state = "receipt_only"
        elif claim and receipt and manifest:
            observed_state = "complete"
        else:
            observed_state = "inconsistent"
    finally:
        try:
            traversal.close()
        except BaseException as error:
            if observed_state is not None and observed_state != "absent":
                raise PermitError(
                    "E_CONSUMED",
                    observed_state,
                ) from error
            raise
    require(observed_state is not None, "E_NAMESPACE")
    return observed_state


def readback_namespace_absent(root: Path = ROOT) -> None:
    state = readback_namespace_state(root)
    if state != "absent":
        raise PermitError("E_CONSUMED", state)


def package_preflight_for_recorder() -> dict[str, Any]:
    """Validate only the readback package and reserved names, not frozen inputs."""
    expected, raw = expected_package(True)
    verify_bound(raw[PERMIT_PATH], expected)
    readback_namespace_absent()
    return {
        "permit": expected,
        "permitRawSha256": sha256(raw[PERMIT_PATH]),
        "permitContentSha256": expected["contentBinding"]["sha256"],
        "checkerRawSha256": sha256(raw[THIS_CHECKER_PATH]),
        "recorderRawSha256": sha256(raw[RECORDER_PATH]),
        "frozenAcquisitionInputOpened": False,
        "networkRequestAttemptCount": 0,
    }


def evaluate(verify_disk: bool, verify_frozen: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    expected, raw = expected_package(verify_disk)
    if verify_disk:
        verify_bound(raw[PERMIT_PATH], expected)
    readback_namespace_absent()
    if verify_frozen:
        audit_frozen_snapshot()
    return expected, {
        "documentType": "aetherlink.wave19-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 15,
        "acceptedResourceCount": 4,
        "selectedTupleCount": 0,
        "selectedRequestOrdinals": [],
        "aggregateAcceptedBytes": 11_453_955,
        "aggregateZipEntryCount": 931,
        "aggregateZipUncompressedBytes": 46_404_827,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "frozenSnapshotVerified": verify_frozen,
        "readbackClaimExists": False,
        "lastCurrentPathIdentityBarrierTiming":
            "immediately_before_manifest_publication",
        "currentPathIdentityGuaranteedThroughManifestPublication": False,
        "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
        "completionAppliesToRetainedSnapshot": True,
        "networkRequestAttemptCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise PermitError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--preflight", action="store_true")
        group.add_argument("--package-only", action="store_true")
        group.add_argument("--print-permit", action="store_true")
        args = parser.parse_args(argv)
        if args.package_only:
            result = package_preflight_for_recorder()
        else:
            permit, summary = evaluate(
                verify_disk=not args.print_permit,
                verify_frozen=not args.print_permit,
            )
            result = permit if args.print_permit else summary
        sys.stdout.buffer.write(canonical_bytes(result))
        return 0
    except PermitError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": "aetherlink.wave19-acquisition-readback-permit-error",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "networkAuthorized": False,
                    "fileWriteAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": "aetherlink.wave19-acquisition-readback-permit-error",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "networkAuthorized": False,
                    "fileWriteAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
