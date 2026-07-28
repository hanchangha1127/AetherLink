#!/usr/bin/env python3
"""Validate the one-use offline Wave18 acquisition readback permit."""

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
    raise RuntimeError("Wave18 readback checker requires `python3 -I -B -S`")

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
    raise RuntimeError("Wave18 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave18_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave18_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-18-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave18-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave18-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-18-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-18-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave18-failure-v1.json"
)
STAGING_PREFIX = ".wave-18-v1-staging-"
ATTEMPT_ID = "4380f5bbcd3366154b05111381ccab18"
EXPECTED_DECISION_CONTENT = (
    "c75e5751d3e7c67939251d56e212f95f85439d05684cd50a49701de3e099803d"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "522be316d62538e52eead736c1a38ba786768ac6e2777af1b44b4065b3cc6a24"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "3c13b764b7267efe885528d9f7d4fe31d6b7bdac48839f95e60bb5bd45a7d836"
)
EXPECTED_RESOURCES_CANONICAL = (
    "86587f7dbea64ab85bdfd32287595007577de1ea3d0bb554c6471af81b4d8602"
)
EXPECTED_COMPACT_IDENTITY = (
    "53a711ff8b8771d698ac0df4448a6155eddc69179e1895d8619afd104f7623d7"
)
EXPECTED_FULL_WITNESS = (
    "c95159a8c9b5fbf06f54830a06c59c2f358b8ec5901c3a467fabd0ad64ef5419"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "401a3e85faacc150944d883495fca4b22e4cac1933c0308aedaec228a7c872ea"
)
EXPECTED_V16_CHECKER_NORMALIZED = (
    "7dd2c81a2032a374192f7c502afc65305d97f7c1e3699654e416b60bf64c6bd5"
)
EXPECTED_V16_CONTENT = (
    "90928eb85eded2938b25a0beec82c00ebcd69147bf92733bc65a528d26c00e03"
)
EXPECTED_V16_INPUT_SET = (
    "15705de20633cdf4bf473c82a634136f481a2c131e7960a0a6cbdeccf10397a7"
)
EXPECTED_V16_GRAPH = (
    "db7e36664afd819c72e9c9916bd7053782282954ed4f359c550b7972b74147a2"
)
EXPECTED_V16_FRONTIER = (
    "fe15a3ea57682b276a6f11a2c2fd998d9120640fac40038fc9c1f100e50750b5"
)
EXPECTED_ACCEPTED_RESOURCE_HASH_SET = (
    "757651958dc0538863d7654d59df95a4171cf44fccfa726da87fb0fdf5babc0f"
)
EXPECTED_FROZEN_FILES_CANONICAL = (
    "59595e842e331a333c74f688d57198546ca8aad7347976a20906afc8df6161f4"
)
PLACEHOLDER_SHA256 = "0" * 64
EXPECTED_READER_RAW = (
    "0b05aec34986a265080c3b34f60502bfe2e84436bdc49bfb7bb503f41bb612aa"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "dee88b1d2197d19d64bcd634c6d8ee1af6b4396f30f4f817ed5f41baf7cd4d40"
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
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave18-v1.json",
        "c90d16a7c7194c7a6dbde2be9bd99f4101a3a8cd1722278209fe5df8bf6371fa",
        11_584,
        "0644",
    ),
    frozen(
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave18-v1.md",
        "862ac89248970b9b4d59230e6b9f894b3fc49ed82f151608687e82cb8b1d1a2d",
        6_232,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_decision_v1.py",
        "bad407e7e0c95dc843ccc7bd7b0aa578c10f70b0592c110eab52fba0c6a73b57",
        34_220,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_decision_v1.py",
        "e6ae108af2326c97ac2db488451922640ddecefe576d8c7dedd0415a6e57904d",
        47_997,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v16.py",
        "2e388d466c5346fa6f82b7fd23fa6dca24009acadacdd62f1fe2ba25b0a10879",
        232_397,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_combined_fixed_point_v16.py",
        "15cf4d56a68b9f0cfd61554b24e781357066b27e63c90c871dfb0cde19c80889",
        141_409,
        "0644",
    ),
    frozen(
        "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-17-v1.claim",
        "3090e729d99c46c4b4d1e4242d6f25c08e2345062dfb6c15e1e87d3edf632fad",
        416,
        "0600",
    ),
    frozen(
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave18-execution-permit-v1.md",
        "abe114edafaf7f1ed7dd11af5179bf39d6577c95ac87bc64f86ed57b9402fe8c",
        4_160,
        "0644",
    ),
    frozen(
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave18-execution-permit-v1.json",
        "c8bca67d38117c3658da504780bb97e33b92367567121285129e90dde0db0fc1",
        18_591,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition_v1.py",
        "c454de5191c7a9de4bccaa4c8aa00f914e74e2c9bb4c4bf59164b827a0c6bfc5",
        60_069,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition_v1.py",
        "589f27f6754e357207e90f1a275126acba4f7f1008821dd0f18df4f904ce7c4e",
        43_349,
        "0644",
    ),
    frozen(
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave18_v1_once.py",
        "5d4d77663d61b9ff77f35ec6f0e55239637e18970e9d3e6ad7a104d308b9e3ca",
        95_707,
        "0644",
    ),
    frozen(
        "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave18_v1_once.py",
        "f45a478e0ed4a36bebaf4f2360181c4287ab5bfa09113238fa6b9eaf534b4dad",
        91_088,
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
    "08f5134ce03805e512c2dec0dee13251ce682d793d2b87f7f8e29f6d3426d362",
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
    "linkCount": 8,
    "exactFileCount": 6,
}
EVIDENCE_FILE = frozen(
    EVIDENCE_PATH,
    "954d26f4d95a500b1c993b6e4727f787416db866246a009754c8baa1cb7febed",
    2_605,
    "0600",
)


_ACCEPTED_ROWS = [
    (
        "001-bb2025870bcef7a0c287.mod",
        "1fb8ad2f7201cd79bf178578b35aaead1720cab2b8cfea35b99b25b60839f1ef",
        86,
    ),
    (
        "001-bb2025870bcef7a0c287.zip",
        "1a8ef77bb4d41c1a7d3fa5d0caf2fe599f14eac10f473629e31546f12759b89f",
        172_143,
    ),
    (
        "002-3c84a9eecca520aed886.mod",
        "3258ec9e17abe2bf1053d0b176d3d50367815237a7701eb373c38152bbd6b9a0",
        157,
    ),
    (
        "002-3c84a9eecca520aed886.zip",
        "388e4a624f48990057f1a2a2cc5f3e0f81e41b99dd2036247d98c931c59d44d4",
        1_910_283,
    ),
    (
        "003-4615480e24f0c4184e4c.mod",
        "720b98f1bf033d6b64a454ca8c29cdca6e9265ab7d70db3b834dff49560f1587",
        36,
    ),
    (
        "003-4615480e24f0c4184e4c.zip",
        "8b19a2aa2162ec8fa1cba4762eb06b089ef8d2dbddf4e64ef51334e722b83a7f",
        26_395,
    ),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "30c703bde55144665117bffcafa0f7fcd1b54c9885acd8fb028adda9339643ca",
    1_658,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "28230bf973cc4346772430080e87c1ac06d0482b9188e072cc75b72020332b7a",
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
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave18" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition"
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
        "check_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition",
        "acquire_p2p_nat_g2_pion_rung3_dependency_wave18",
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
        len(frozen_canonical) == 25
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
            "combinedFixedPointV16": {
                "checkerPath": (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_v16.py"
                ),
                "checkerRawSha256": (
                    "2e388d466c5346fa6f82b7fd23fa6dca24009acadacdd62f1fe2ba25b0a10879"
                ),
                "checkerNormalizedSha256": EXPECTED_V16_CHECKER_NORMALIZED,
                "testsPath": (
                    "script/test_p2p_nat_g2_pion_combined_fixed_point_v16.py"
                ),
                "testsRawSha256": (
                    "15cf4d56a68b9f0cfd61554b24e781357066b27e63c90c871dfb0cde19c80889"
                ),
                "contentSha256": EXPECTED_V16_CONTENT,
                "combinedInputSetSha256": EXPECTED_V16_INPUT_SET,
                "graphSha256": EXPECTED_V16_GRAPH,
                "frontierSha256": EXPECTED_V16_FRONTIER,
                "sourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
                "totalFullSourceReconstructionCount": 30,
                "totalGraphArchiveOpenCount": 4_056,
                "wave17NamespaceAnchor": {
                    "path": (
                        "build/offline-source/pion-ice-v4.3.0/"
                        "dependencies/.wave-17-v1.claim"
                    ),
                    "rawSha256": (
                        "3090e729d99c46c4b4d1e4242d6f25c"
                        "08e2345062dfb6c15e1e87d3edf632fad"
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
        "aggregateModBytes": 279,
        "aggregateZipBytes": 2_108_821,
        "aggregateAcceptedBytes": 2_109_100,
        "aggregateZipEntryCount": 971,
        "aggregateZipUncompressedBytes": 7_225_800,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "acceptedResourceCount": 6,
        "selectedTupleCount": 0,
        "selectedRequestOrdinals": [],
        "modCount": 3,
        "zipCount": 3,
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
            "aetherlink.wave18-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave18-source-acquisition-readback-"
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
            "exact6ResourceOrderAndAggregateRecomputed": True,
            "exact25FrozenFileSnapshotRequired": True,
            "acceptedResourceHashSetCanonicalSha256Recomputed": True,
            "requestResourcesCanonicalSha256Recomputed": True,
            "combinedFixedPointV16PredecessorBindingRecomputed": True,
            "v16TestsLiveHeld": True,
            "v15TestsLiveHeld": False,
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
            "maximumAcceptedResourceCount": 6,
            "maximumModBytes": 1_048_576,
            "maximumZipBytes": 16_777_216,
            "maximumAggregateModBytes": 3_145_728,
            "maximumAggregateZipBytes": 50_331_648,
            "maximumAggregateAcceptedBytes": 53_477_376,
            "maximumZipEntriesPerZip": 20_000,
            "maximumZipEntriesAcrossAll": 60_000,
            "maximumZipEntryNameBytes": 1_024,
            "maximumZipEntryBytes": 134_217_728,
            "maximumZipUncompressedBytesPerZip": 134_217_728,
            "maximumZipUncompressedBytesAcrossAll": 402_653_184,
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
            "exact_offline_wave18_retained_snapshot_readback_"
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
        "documentType": "aetherlink.wave18-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 15,
        "acceptedResourceCount": 6,
        "selectedTupleCount": 0,
        "selectedRequestOrdinals": [],
        "aggregateAcceptedBytes": 2_109_100,
        "aggregateZipEntryCount": 971,
        "aggregateZipUncompressedBytes": 7_225_800,
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
                    "documentType": "aetherlink.wave18-acquisition-readback-permit-error",
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
                    "documentType": "aetherlink.wave18-acquisition-readback-permit-error",
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
