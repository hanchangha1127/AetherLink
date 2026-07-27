#!/usr/bin/env python3
"""Validate the one-use offline Wave9 acquisition readback permit."""

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
    raise RuntimeError("Wave9 readback checker requires `python3 -I -B -S`")

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
    raise RuntimeError("Wave9 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave9-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave9-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave9_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave9_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave9_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave9_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-9-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave9-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave9-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave9-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave9-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-9-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-9-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave9-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave9-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave9-failure-v1.json"
)
STAGING_PREFIX = ".wave-9-v1-staging-"
ATTEMPT_ID = "df64a4816a083806020580efe953b9a7"
EXPECTED_DECISION_CONTENT = (
    "340966e22b9759e2c1abd106e0cd9d9e9afa47b89ae3bb3929bfa6302dda18ae"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "14ac147494887a6019d8e5f66a1af2f8d9e27872a1b6560122e3bca2ff557a43"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "e3922164eda6657d447f1b75ff49268265338efe35440dad39a237d1ddf643bc"
)
EXPECTED_RESOURCES_CANONICAL = (
    "8758566447b9300880837d7316cf6fac319f50ec90549cb41aa36600ef2171f9"
)
EXPECTED_COMPACT_IDENTITY = (
    "db31bdd4d1ae0c97ba88094502f7c0dc5e0f554e72c5f68503d917005f762753"
)
EXPECTED_FULL_WITNESS = (
    "ee3657522619b1960c535fc3a9644441adb15cee473286bfd2871096fb719afe"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "527c2e6dc235d269c92e52915135c1b2beec113cb751198ca7142c5e63d79148"
)
EXPECTED_V7_CHECKER_NORMALIZED = (
    "cf4fd9d25efe04c2ecb3eea882bb24d6c40b02f2f258c4ab01d824d1373d1c02"
)
EXPECTED_V7_CONTENT = (
    "c71188f8d648a0f020a164002644f825e018f4c01b56d90e57011e05cc2e5202"
)
EXPECTED_V7_INPUT_SET = (
    "d389c84ae3b6d2d3d7dbb38d7003711972a75db3a558b9d6e0d79856249ef528"
)
EXPECTED_V7_GRAPH = (
    "c7889fbf06a01e08ba75150b85bb2cb2860ea71ce205cead432cf0a37e0d89b9"
)
EXPECTED_V7_FRONTIER = (
    "03058e3aea23aca0c6208dd0023361f90421d394272f212d80bf61d587baff4e"
)
EXPECTED_ACCEPTED_RESOURCE_HASH_SET = (
    "a325c4e436dbdb0c2e40cd212784e8f1533890a8f291cc2a4e1b43b9bf45f442"
)
EXPECTED_READER_RAW = (
    "324a505449c821ff8dfc73e22dc8e9bd127f560dfa37e4bb17081e8a06ab2144"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "1a946d03662e82d5c4cdd3abee461a9b45c9244047e6637c7c88149b25e40d11"
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
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave9-v1.json',
        '21ca43d44a67aec62b65a86fa44c43726eaa81fa277e07550f105e8c3b33bca8',
        22_532,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave9-v1.md',
        'b35305cbeac56522eb03a682d754d3d34b504fb7a143e9327a201b24113004c2',
        6_330,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave9_decision_v1.py',
        'e2bef912672b82e71e3f876fff1dd3aa91d3f97e2e0a29c82407b6e7ab4c218a',
        90_001,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave9_decision_v1.py',
        '0999212a310404b3d2bf5a762ed037ecc417ee2707e87ee90a990dd18f16c5ba',
        39_963,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_combined_fixed_point_v7.py',
        '7264d85e1948bc8f86e8238192663706e7bf7472153d37fe812bd118620e99c7',
        140_325,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_combined_fixed_point_v7.py',
        'bb992db8e2d649dd982255f21c2c719ee4d0437818eb0495c9a11fe81f5ea79f',
        74_359,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-execution-permit-v1.md',
        '814f5b64cc1707c5e838246887be3df1fb286b503d81f683833b0fd3902095cc',
        8_973,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-execution-permit-v1.json',
        '026c270af575655245042998cdfae15478ac1630d5f7545ed33f66822c9c2ff5',
        25_996,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave9_acquisition_v1.py',
        'cffa859723fb1688bea5cf7188885fe43443dd63c59d01c8805dfc61870b69a6',
        52_451,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave9_acquisition_v1.py',
        '7a4146a3b608cf38015e3f1071d744e7be487b5ea0ebcc53e38b4a0b453fdfad',
        37_109,
        "0644",
    ),
    frozen(
        'script/acquire_p2p_nat_g2_pion_rung3_dependency_wave9_v1_once.py',
        'b99f29546a050be951f9d07ced2a9c554b2c63b151a92dc6dca4dea241dcc87a',
        86_251,
        "0644",
    ),
    frozen(
        'script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave9_v1_once.py',
        '68911f5aab671b5a69df40ad972d4d6781152d707c899a963d7ed34b0e8ec10c',
        115_511,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py',
        '37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd',
        34_617,
        "0644",
    ),
    frozen(
        'script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py',
        'ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b',
        54_352,
        "0644",
    ),
]
ACQUISITION_CLAIM = frozen(
    ACQUISITION_CLAIM_PATH,
    "84957554fe937841165f38a2418613e4e740082bea4f55538b21324dfe6d45f4",
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
    "linkCount": 22,
    "exactFileCount": 20,
}
EVIDENCE_FILE = frozen(
    EVIDENCE_PATH,
    "566c1e5970d761839a6a75b953524dff7fcf1c00c68a114ab9f9af853587813b",
    8_263,
    "0600",
)


_ACCEPTED_ROWS = [
    ('001-facedebd32778d85a887.mod', 'cd6311612a2aa4d0d7e03c41b3aa1fbc2d5f895ab3f61089fab80bfe9f8f5485', 247),
    ('001-facedebd32778d85a887.zip', 'eb2426a7891915213cc5da1da7b6fc6e9e2cf253d518d8e169e038e287f414e3', 1_878_482),
    ('002-894e21817dfa8267f491.mod', 'dfcf96d66b86f2a3527cbfb7a194970713c51a8b50f7daa71f2b7ec6837d6236', 86),
    ('002-894e21817dfa8267f491.zip', '1033fb59927549a16c7000369f6d534b652fcd201746a7d6d8cfd521e1ad85e2', 172_650),
    ('003-ecbba0ad72103feaa687.mod', 'b64ec375b819035044e5091608f3ee4ad3ba7a7c2aa6e6e1ebe52b13675ab821', 157),
    ('003-ecbba0ad72103feaa687.zip', 'e45c82aff473f14b51b0e4b1ca25274364885af81ad3eb433c84c61aae7506cd', 1_908_772),
    ('004-dbc58fe6145c5f36e7e8.mod', 'b64ec375b819035044e5091608f3ee4ad3ba7a7c2aa6e6e1ebe52b13675ab821', 157),
    ('004-dbc58fe6145c5f36e7e8.zip', '995a48eebb670c919eb9fc9d9f60ee85a9f8ae39d606760108a31438e1300348', 1_924_001),
    ('005-8087122ceb13689637a2.mod', 'f033333096fe198f3151deed93f2deba74e50bbfe7739134045bc3b7ce4a5024', 33),
    ('005-8087122ceb13689637a2.zip', '734caf189549ea9b85dd93f58e87e3f3bceaec72229449f5879c3c067a2ad60e', 1_762_176),
    ('006-212cea191ca50d4f7463.mod', 'f411814d83a96e86781b1dee41c125b9504da5422dba37cc1d63b016ae39cfe2', 35),
    ('006-212cea191ca50d4f7463.zip', '894ee9a48e191265cd3d2200ddd81b8d75c554a0eabe9fc1a9afbab25a4b29c4', 1_996_987),
    ('007-344ca787dd0887ddf7ec.mod', 'a41d5e07d9e2dee47cb81a88376347afe33aee5e240f4eeb50767cd6516c6e80', 133),
    ('007-344ca787dd0887ddf7ec.zip', 'ae079c5f1321c91facaf2e5aaaa23eeed74228446654ce41c1494b29760a9b4e', 1_016_983),
    ('008-169dcfe92aa84babdbd0.mod', '740794e2914f5cc87e25656c5843222b2c65665821205f45632a0477c8d3f79b', 95),
    ('008-169dcfe92aa84babdbd0.zip', '3adf713afa49fe26580ffe4adb1f4fb2f4921c945301aa5a9fb6d34031fa30cd', 21_653),
    ('009-e293519f45e4cef8b85a.mod', 'a0e02f0678fe62dc3c4b4bc77fa912c9b70de10fa9f7cf2f7aad0337392b52af', 26),
    ('009-e293519f45e4cef8b85a.zip', '6673fe06662fcbee5f246f12af8ed860328bf08fd016fd490987cd76acb1b4fe', 2_687_668),
    ('010-608b3dd7a3ef29a6f8c1.mod', '88d479265f886f5e598d76c003d0f257b42dbf1b895d820a12b5ab0b3501aca1', 212),
    ('010-608b3dd7a3ef29a6f8c1.zip', '092e06323d7a55880ee4387905ebf35a021fffdf2b7f72d80fb3c36e48668651', 2_915_387),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "55a989da9058e57fb44432e29299a3e6025f78b90e1bd011d5eb8e2141aee33c",
    1_670,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "3acb2c48c4ba1dbc701896188f166026133e1860c4abfe58078e145574ba6514",
    463,
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
    require(raw == canonical_bytes(observed) and observed == expected, "E_PERMIT")
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
    try:
        source = recorder_raw.decode("utf-8", errors="strict")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise PermitError("E_RECORDER") from error
    imports: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
    forbidden = {
        "http",
        "socket",
        "ssl",
        "urllib",
        "requests",
        "subprocess",
        "importlib",
        "runpy",
    }
    require(not imports.intersection(forbidden), "E_RECORDER")
    require(
        not any(
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave9" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave9_acquisition"
            in name
            for name in imports
        ),
        "E_RECORDER",
    )
    require(
        {
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
        }
        <= functions,
        "E_RECORDER",
    )
    for token in (
        "http.client",
        "HTTPSConnection",
        "urlopen",
        "socket.",
        "subprocess",
        "os.system",
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
            "combinedFixedPointV7": {
                "checkerPath": (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_v7.py"
                ),
                "checkerRawSha256": (
                    "7264d85e1948bc8f86e8238192663706e7bf7472153d37fe812bd118620e99c7"
                ),
                "checkerNormalizedSha256": EXPECTED_V7_CHECKER_NORMALIZED,
                "testsPath": (
                    "script/test_p2p_nat_g2_pion_combined_fixed_point_v7.py"
                ),
                "testsRawSha256": (
                    "bb992db8e2d649dd982255f21c2c719ee4d0437818eb0495c9a11fe81f5ea79f"
                ),
                "contentSha256": EXPECTED_V7_CONTENT,
                "combinedInputSetSha256": EXPECTED_V7_INPUT_SET,
                "graphSha256": EXPECTED_V7_GRAPH,
                "frontierSha256": EXPECTED_V7_FRONTIER,
                "sourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
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
        "frozenFilesCanonicalSha256": sha256(canonical_bytes(frozen_canonical)),
        "aggregateModBytes": 1_181,
        "aggregateZipBytes": 16_284_759,
        "aggregateAcceptedBytes": 16_285_940,
        "aggregateZipEntryCount": 5_349,
        "aggregateZipUncompressedBytes": 54_936_288,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "acceptedResourceCount": 20,
        "selectedTupleCount": 0,
        "modCount": 10,
        "zipCount": 10,
    }


def expected_payload_from_package(raw: Mapping[str, bytes]) -> dict[str, Any]:
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
            "aetherlink.wave9-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave9-source-acquisition-readback-"
            "execution-permit-v1"
        ),
        "recordedDate": "2026-07-26",
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
            "exact20ResourceOrderAndAggregateRecomputed": True,
            "exact38FrozenFileSnapshotRequired": True,
            "acceptedResourceHashSetCanonicalSha256Recomputed": True,
            "requestResourcesCanonicalSha256Recomputed": True,
            "combinedFixedPointV7PredecessorBindingRecomputed": True,
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
            "publicationOrder": [
                "rename_no_replace",
                "parent_directory_fsync",
                "final_name_no_follow_reopen_and_source_inode_verification",
                "return",
            ],
        },
        "resourceLimits": {
            "maximumPackageFileBytes": MAXIMUM_PACKAGE_FILE_BYTES,
            "maximumAcceptedResourceCount": 20,
            "maximumModBytes": 1_048_576,
            "maximumZipBytes": 16_777_216,
            "maximumAggregateModBytes": 8_388_608,
            "maximumAggregateZipBytes": 134_217_728,
            "maximumAggregateAcceptedBytes": 134_217_728,
            "maximumZipEntriesPerZip": 20_000,
            "maximumZipEntriesAcrossAll": 300_000,
            "maximumZipEntryNameBytes": 1_024,
            "maximumZipEntryBytes": 134_217_728,
            "maximumZipUncompressedBytesPerZip": 134_217_728,
            "maximumZipUncompressedBytesAcrossAll": 1_073_741_824,
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
            "passwordRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
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
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW,
        },
        "toolBindings": tools,
        "recorderNormalizedSha256": EXPECTED_RECORDER_NORMALIZED_SHA256,
        "result": (
            "exact_offline_wave9_retained_snapshot_readback_"
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
        "documentType": "aetherlink.wave9-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 14,
        "acceptedResourceCount": 20,
        "selectedTupleCount": 0,
        "aggregateAcceptedBytes": 16_285_940,
        "aggregateZipEntryCount": 5_349,
        "aggregateZipUncompressedBytes": 54_936_288,
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
                    "documentType": "aetherlink.wave9-acquisition-readback-permit-error",
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
                    "documentType": "aetherlink.wave9-acquisition-readback-permit-error",
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
