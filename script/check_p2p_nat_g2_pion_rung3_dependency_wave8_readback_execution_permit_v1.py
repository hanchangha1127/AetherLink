#!/usr/bin/env python3
"""Validate the one-use offline Wave8 acquisition readback permit."""

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
    raise RuntimeError("Wave8 readback checker requires `python3 -I -B -S`")

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
    raise RuntimeError("Wave8 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave8_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave8_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave8_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave8_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-8-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave8-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave8-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-8-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-8-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-failure-v1.json"
)
STAGING_PREFIX = ".wave-8-v1-staging-"
ATTEMPT_ID = "6d8ea4473126c853b439c56a895f9c28"
EXPECTED_DECISION_CONTENT = (
    "1e1d62f03fe3137a88aa9413be8310bf7260f65a4825a09baab9a848ce6969da"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "527a4558d069b31f92256926ea90e05c8353a33f65128b131d1c960614df925b"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc"
)
EXPECTED_RESOURCES_CANONICAL = (
    "ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136"
)
EXPECTED_COMPACT_IDENTITY = (
    "c6aa1a974ad09f11927c103c7f2b63df0835d09b41d0dac9f6349d46d377a388"
)
EXPECTED_FULL_WITNESS = (
    "044dc1dd0675d781d174825dbe8e419d7ff0fe6029b590e2d16c5edeed5f08ae"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "8358b58ad8925633d78c6c1c6160d6d52567c39a2d4c940d01a05cfc87419343"
)
EXPECTED_V6_CHECKER_NORMALIZED = (
    "3f2a9866a185d157ab4fca021b52bc55aecac914fd5a08003e2f2f34e9522eef"
)
EXPECTED_V6_CONTENT = (
    "b33ef7a10de32dc99cea1dbbbcab1dac3a549eb466ef80b0229d2a0381ab9052"
)
EXPECTED_V6_INPUT_SET = (
    "f7ad0b43d571da61edd4941f8e504d54d014b01f3395aeca8d0d10b9b3c22349"
)
EXPECTED_V6_GRAPH = (
    "3648bdf037e316e69e155615edd5748c2bb653238579216ddd8b8dce4beb9f09"
)
EXPECTED_V6_FRONTIER = (
    "d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92"
)
EXPECTED_ACCEPTED_RESOURCE_HASH_SET = (
    "7642f0b4dea8fee8eb92f573a3a4d948aa46a8736be70857097ce3b83af2eb38"
)
EXPECTED_READER_RAW = (
    "8e832c5a461fcaf49b4993627f0d2aff85cb1441db84d496b40f511aac6410e3"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "c61b10ee185c79c60ed8027d596c5f025e523d97b37121cb3a16ecce4ebeacc9"
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
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.json',
        '45236a2ea42a4a3af59e60d27ed2f09cd5d191e34a6db992a9d81cb49316297e',
        27_639,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.md',
        'bb9cdcf45e85d4cd05a98d5049eb338ebf0feb1cf89abb17b2e64ab9bac18362',
        6_147,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave8_decision_v1.py',
        '01d04089f8add1840ff23542c2b44419107e5902d33c87c1d4e0460f551d4af1',
        81_960,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave8_decision_v1.py',
        '040c9217711f826f16aaaa27964682587759fd46d53f53bf8e92cad3c75bc393',
        33_553,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_combined_fixed_point_v6.py',
        'eee3d6bd5ec0857bc4832895f4c2d463b608ffc0a59436ebc2cde507cd9750e4',
        127_806,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_combined_fixed_point_v6.py',
        '4ce508661695fd63c0e1c578a99cbfa9f369943283186958bf26b998839c7837',
        59_391,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-execution-permit-v1.md',
        '20bf8742a011557813cbcfcd0f2a862f053939ea1a3acab35df3a31c89435ea4',
        8_973,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-execution-permit-v1.json',
        '8595241898ebc14d563f5b03c3a4b46afdd995207bc1597d86c861e5c37bcb4c',
        30_422,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave8_acquisition_v1.py',
        '78132ce62e3ba4b74fb404983d55b003119106eba34c3cba6b6fbc7622a0ca20',
        52_451,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave8_acquisition_v1.py',
        'ab6553167b05bf1c1fad12b3df03a530f8422381f088241255a33ef784d3f62f',
        35_605,
        "0644",
    ),
    frozen(
        'script/acquire_p2p_nat_g2_pion_rung3_dependency_wave8_v1_once.py',
        'cc11c0fa3b552afc05436c4a7568617796eeb6daa2fbc630aba8fd3e9603a7c9',
        86_251,
        "0644",
    ),
    frozen(
        'script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave8_v1_once.py',
        '898900e15930c9d28cca28f7f91db8e8ef5549bc24d2d589e01693d03b825028',
        115_246,
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
    "772ac8daf78e313281245d6474dfee38bfe10b32b5e74953ef7bb45fed6a9265",
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
    "linkCount": 30,
    "exactFileCount": 28,
}
EVIDENCE_FILE = frozen(
    EVIDENCE_PATH,
    "7431c37bacb8c630b24f4793aa0351e8ec4280080b32a52af41999dafa20cfbb",
    11_258,
    "0600",
)


_ACCEPTED_ROWS = [
    ('001-dc8e752ef19075b7388b.mod', 'bcb29393251237b79a17b6c19bf29134f43e8f438c3198988fcd461a1cdf05cc', 34),
    ('001-dc8e752ef19075b7388b.zip', '0b5a691aeb8b6af31bd2bb640973ea7e8bf1ed9bc5889da220bf44dc06d9692c', 60_546),
    ('002-1c26455186eb5974f621.mod', '1350354d52d2287a62336ecc0d56232d4c47699af9bba49c67c2b48254da98f1', 32),
    ('002-1c26455186eb5974f621.zip', '1fa10dab404ed7fc8ed2a033f8784187d5df3513ced3841ce39e46d37850eb1d', 34_637),
    ('003-c7c9a35f8c860a864978.mod', 'd83331446e98865733a1bd882774bd2f23d69dd3500adb5c7f79832b51cdd95b', 192),
    ('003-c7c9a35f8c860a864978.zip', '0b11e4f2ac759849fc2567213e22e7dcb2e1bfe9755aca46c95d8d253f3c610b', 2_233_740),
    ('004-dfd0d771992c603d8baf.mod', '42d19023ff8f2eae700bc5495f371ecd998a22d19ba985d0af5f69900b254083', 157),
    ('004-dfd0d771992c603d8baf.zip', '2b7471ed34a349f91055527c5328acd40e9aba006b644e51d40a8627efa76a92', 169_387),
    ('005-b82b19891343cee72e6e.mod', 'b315c52647d2da2f76e5cdb9d367e1d6727784236a9bffb612192b19b10a128d', 179),
    ('005-b82b19891343cee72e6e.zip', '1decf7a324a0916bc66304da1b68a834ce679379422de3a2855f3031f6dc39bd', 1_582_191),
    ('006-b5d7ef36e40ac9268364.mod', '421f6139686d5891f3dc5a563d0995780d3279f65cad4d225cea52686794161c', 25),
    ('006-b5d7ef36e40ac9268364.zip', '39d2431ae1db11be34b4012b719e7bcec1572006a122d44509da038a5b498ff1', 28_988),
    ('007-97961d641ce6b93567d4.mod', 'f033333096fe198f3151deed93f2deba74e50bbfe7739134045bc3b7ce4a5024', 33),
    ('007-97961d641ce6b93567d4.zip', 'f4480597a942160a2aaeb761d41ee67f610287785c263f1df253a3e157c98594', 1_797_601),
    ('008-f7c42ed58f08d25cb531.mod', 'dedbe562ba4411dfdcc7eb7800b47b63aac8e50b9b8c9ffd616a8d6d702ecb75', 70),
    ('008-f7c42ed58f08d25cb531.zip', 'b6773eb737a1269579913418c72aa4f3195e2a1f63c6f01080cc7435cbe55eac', 21_166),
    ('009-0d27a921d557535c6f56.mod', '0d6f58228aadc1a6528e6755da018516566e3ae5c5201f7ade1773f56fa8d934', 67),
    ('009-0d27a921d557535c6f56.zip', '7d89c49ab41306950128a0f4b7c67fb8e2d2f637ece8e024e6cf38d17a33193b', 19_924),
    ('010-83de369e32f7facb928e.mod', 'c45d669089427bc4635d07b185f9b9680332d1c48c75b3c49cb715b81a04a5b0', 97),
    ('010-83de369e32f7facb928e.zip', 'e1a9115e61a38da8bdc893d0ba83b65f89cc1114f152a98eb572c5ea6551e8d4', 8_610_883),
    ('011-f899684b9b53b7131824.mod', '10accc0a3b58e97c3000c3120983bbb41f2c4c4767c8ce098a879dee69c83315', 190),
    ('011-f899684b9b53b7131824.zip', '4953efaff3130e642c94ffb8624f668fb9ccfb780757a7e87f86a2434559d934', 9_236_258),
    ('012-072b7b335165c4e0666e.mod', '15929e76fce04aea4c92a354426bb43370684645a4ee03f2e75d0c2eb1466304', 258),
    ('012-072b7b335165c4e0666e.zip', '4d017493c58addadf3c753056b921b47ae386a4cfd10eab2d90ed1252c6ba0e4', 8_614_578),
    ('013-0a0892431fe29280a63b.mod', 'dbd04ecd296d4dab2706766adfcdd2d52c27345613d631682f8fa4371af54aef', 301),
    ('013-0a0892431fe29280a63b.zip', '429b25131b8564084cce722043b12dd8e3ff5231ac6cd63a405b4f3e6fd69204', 2_683_863),
    ('014-0af8d5321b4646203a63.mod', '21579860a20306fcf43b1bd234d1fba319499c77611b71c05f9bf3ba90dab939', 95),
    ('014-0af8d5321b4646203a63.zip', 'acf19ccb4fca983b234a39ef032faf9ab70e759680673bb3dff077e77fee20fe', 101_467),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "77ca07dadeddd5578b08c1aab7b746b50f6d2e4f0ee83d0a73baa3cc4cb6ec68",
    1_671,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "5c440c55c3534c0d8b537fbbc0843b4e053f5e0c7397a568638dd043619abebe",
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
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave8" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave8_acquisition"
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
            "combinedFixedPointV6": {
                "checkerPath": (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_v6.py"
                ),
                "checkerRawSha256": (
                    "eee3d6bd5ec0857bc4832895f4c2d463b608ffc0a59436ebc2cde507cd9750e4"
                ),
                "checkerNormalizedSha256": EXPECTED_V6_CHECKER_NORMALIZED,
                "testsPath": (
                    "script/test_p2p_nat_g2_pion_combined_fixed_point_v6.py"
                ),
                "testsRawSha256": (
                    "4ce508661695fd63c0e1c578a99cbfa9f369943283186958bf26b998839c7837"
                ),
                "contentSha256": EXPECTED_V6_CONTENT,
                "combinedInputSetSha256": EXPECTED_V6_INPUT_SET,
                "graphSha256": EXPECTED_V6_GRAPH,
                "frontierSha256": EXPECTED_V6_FRONTIER,
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
        "aggregateModBytes": 1_730,
        "aggregateZipBytes": 35_195_229,
        "aggregateAcceptedBytes": 35_196_959,
        "aggregateZipEntryCount": 4_907,
        "aggregateZipUncompressedBytes": 144_867_307,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "acceptedResourceCount": 28,
        "selectedTupleCount": 0,
        "modCount": 14,
        "zipCount": 14,
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
            "aetherlink.wave8-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave8-source-acquisition-readback-"
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
            "exact28ResourceOrderAndAggregateRecomputed": True,
            "exact46FrozenFileSnapshotRequired": True,
            "acceptedResourceHashSetCanonicalSha256Recomputed": True,
            "requestResourcesCanonicalSha256Recomputed": True,
            "combinedFixedPointV6PredecessorBindingRecomputed": True,
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
            "maximumAcceptedResourceCount": 28,
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
            "exact_offline_wave8_retained_snapshot_readback_"
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
        "documentType": "aetherlink.wave8-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 14,
        "acceptedResourceCount": 28,
        "selectedTupleCount": 0,
        "aggregateAcceptedBytes": 35_196_959,
        "aggregateZipEntryCount": 4_907,
        "aggregateZipUncompressedBytes": 144_867_307,
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
                    "documentType": "aetherlink.wave8-acquisition-readback-permit-error",
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
                    "documentType": "aetherlink.wave8-acquisition-readback-permit-error",
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
