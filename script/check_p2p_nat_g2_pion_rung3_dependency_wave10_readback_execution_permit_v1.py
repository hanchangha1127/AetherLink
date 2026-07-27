#!/usr/bin/env python3
"""Validate the one-use offline Wave10 acquisition readback permit."""

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
    raise RuntimeError("Wave10 readback checker requires `python3 -I -B -S`")

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
    raise RuntimeError("Wave10 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave10-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave10-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave10_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave10_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave10_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave10_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-10-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave10-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave10-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave10-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave10-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-10-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-10-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave10-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave10-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave10-failure-v1.json"
)
STAGING_PREFIX = ".wave-10-v1-staging-"
ATTEMPT_ID = "ffe70ee4562fcfc9e0fd6c9c4e136bd9"
EXPECTED_DECISION_CONTENT = (
    "d0bfdd7247584e116656ca4efd560e893814241e0b17be96ba0cb55151b9150e"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "33edc56dcb497f9fb94d54ef1d0c07f3ff18fe04cdbaca1ff0bffd81169eabfa"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "cf6a97651565b55bb714a713e66e6a452f7132973ce21ced254bd0d728d12a89"
)
EXPECTED_RESOURCES_CANONICAL = (
    "efa3845dcfaf05bfa989f8cf08275cebe59b29fd1268481171c51e602805fcc1"
)
EXPECTED_COMPACT_IDENTITY = (
    "ae82fa0383b6492de66add1ceaffefffff51dcbe1c3ad856399ce03152067bb0"
)
EXPECTED_FULL_WITNESS = (
    "89a1e5a1b16c01fcbfac6720f5ad9477416eb43d2c9c3a7121f60ad030cfe715"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "a5ae07cb68ea3f0e080094b8168aa36c67715ed44824220dd4c7a94cd0f9192b"
)
EXPECTED_V8_CHECKER_NORMALIZED = (
    "cfd83cdd00b6daee857cbff915ec48fd78390bbf06098ccab963a54e8748ba4b"
)
EXPECTED_V8_CONTENT = (
    "f9f683d3afbe65a77626577428c0f9ce94219e39529d0c5811b49172c51e3b37"
)
EXPECTED_V8_INPUT_SET = (
    "030743c3959a6e7466385e9f89255fcb03d65576676a1e5cd7e5e2929e9f6339"
)
EXPECTED_V8_GRAPH = (
    "721d045a10cdf015e865a84db7026115ac63462217dbb5349504fed9f1bae7b7"
)
EXPECTED_V8_FRONTIER = (
    "780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82"
)
EXPECTED_ACCEPTED_RESOURCE_HASH_SET = (
    "7902729395587c118ba4203d98dae29a6b0c1c33b0e71021032b8d91d6681e31"
)
EXPECTED_FROZEN_FILES_CANONICAL = (
    "f54e525a8d782891bc0cd452d9e3a9acf9a5881bbb138caacfc78167d72acb93"
)
EXPECTED_READER_RAW = (
    "c2da54eeba369acef1a755bca756c4cb5aae99f5fad69a561209633f66e24a6a"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "a1f0532b9180d64c320a66101523c432b74bfc0f31bde4d5a8c73f490efc9eae"
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
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave10-v1.json',
        'd1c23056487d88b92f1f2fd105d219abd029079590b379f7a671317b4158b6eb',
        24_723,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave10-v1.md',
        '700a0ae5d4067806cfbad2f8efd6439f272c1d02e5311da7e60d153cf2d85caa',
        6_710,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave10_decision_v1.py',
        'e7c3aabac84dd14f33b77b777730eb95bcd4160b6886645698ccad9060defebc',
        100_030,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave10_decision_v1.py',
        '9336e06a6fde88ad382a0cd54176d3cf3807c3a51c215769659c4fb7e199b9a4',
        47_345,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_combined_fixed_point_v8.py',
        '798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32',
        151_514,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_combined_fixed_point_v8.py',
        '347a1e0083d2daedb40deba5fca491b63ee3137b5a7c18a56886be694ded16a0',
        88_283,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave10-execution-permit-v1.md',
        '25b5a7cee6b0c9b4ddd633d39ed000b03a85a795b74770ecf0b28e08c4884074',
        9_806,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave10-execution-permit-v1.json',
        '841d30e43ce839662baab07d0f47f39cfe9c52d2b4d3757e2066a128452a6c93',
        27_327,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave10_acquisition_v1.py',
        'fe39b88609bbca78461bf7db416cb311143371d68ebab176703bbc2c7a81eaec',
        53_590,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave10_acquisition_v1.py',
        'fe4d7372b82f9fd4e50529ab4a17076ed3787ec2f663512476b846de6f6e0c3c',
        38_239,
        "0644",
    ),
    frozen(
        'script/acquire_p2p_nat_g2_pion_rung3_dependency_wave10_v1_once.py',
        '5395afdaff0d928e786d3e7fb50cea46bf83dd78e57865196813ca1d080546b3',
        87_407,
        "0644",
    ),
    frozen(
        'script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave10_v1_once.py',
        '5aa7f30a6debda432577227e86f0b933b7d668732141d78d3cf9c0a150bad747',
        116_213,
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
    "5260f5d7e7473013871573717848a3e8eae868a47ab2bfe538340d681ec4a6de",
    417,
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
    "linkCount": 24,
    "exactFileCount": 22,
}
EVIDENCE_FILE = frozen(
    EVIDENCE_PATH,
    "0b3700d12d11d334e91c95dfd561d43aa8827294ab9caee0b21258ded48cf9de",
    9_031,
    "0600",
)


_ACCEPTED_ROWS = [
    ('001-5d152fd915392fd2a5b5.mod', '68845acdeae2efec8dcf23dca9c759c0328cbaec288e2a2565d9eb7f70e00eb7', 192),
    ('001-5d152fd915392fd2a5b5.zip', 'dd13a44ed4e46d97aebf16b3bb654323f199c3bb37b9484e0104a5e537721c71', 2_230_527),
    ('002-ef7a0a4d5e9b983df87c.mod', 'e6efdaf78a29503f080cf6d2615e289cfb1d9e3ab7d570f53668eca2b4ab41da', 181),
    ('002-ef7a0a4d5e9b983df87c.zip', '8b437b88ece68e61336150fbdd2a4c0e8d80f143bcdc86ce4ef047c4c93f3caa', 1_421_786),
    ('003-82364176d91c7e0dfbf1.mod', 'fef5896d103a0bce5055fdb5e96e830944334792437865347718edceb633348a', 179),
    ('003-82364176d91c7e0dfbf1.zip', '17ae555c0bec70b583d84ec7a099db3fdc5b3b688cb2814f8c388d174e7ada15', 1_587_056),
    ('004-253ee61bed5449c9f94f.mod', '421f6139686d5891f3dc5a563d0995780d3279f65cad4d225cea52686794161c', 25),
    ('004-253ee61bed5449c9f94f.zip', 'dc105c2b4d6c7ab48e54946ce2f624e8d1f5d47270eff1e88fed06cc65f91fb4', 25_620),
    ('005-ce062f853b3e2f943440.mod', 'f033333096fe198f3151deed93f2deba74e50bbfe7739134045bc3b7ce4a5024', 33),
    ('005-ce062f853b3e2f943440.zip', '0d25c11d65a4ac84a6e2c3bd56a6afeb1da3923d2752a5aa59b7e99a94359fcb', 1_644_123),
    ('006-834e41a3e70906cfb6c2.mod', '4cbab14f7706771b271d995a1b3cc131fe5a246aadc7ee6d1ba6f0bd894781fa', 95),
    ('006-834e41a3e70906cfb6c2.zip', '475a86f11dd148b474ce405c5dbdd5f6bcae056c3e44e52445a45926dd69a552', 23_281),
    ('007-402a22726fd998461a52.mod', 'c210e4c5cb0c2f3a1fc3f64588acc627cbf8bbf8ce29e578a387e9ed8456c4fc', 70),
    ('007-402a22726fd998461a52.zip', 'ec4f6a729019902f333d2e6f40cd6160a63e1f7fa0d3f4c233e899d9aaec2db6', 21_166),
    ('008-3477722dbaf554a645bd.mod', 'b57bcc7ffdfddb1b8235f77262bf41422c75d72dda5a145543cc36bccac43ad3', 190),
    ('008-3477722dbaf554a645bd.zip', 'fb47744565fd36da42ab2ebd3ee4db0038dfed4f703c926a9e7327debab8af77', 9_234_225),
    ('009-c6eaa7316993afbcb5cb.mod', 'fbb7a88ed140515e790eca7a10ffd319c9786b11c6a6c7e59f80f7fb37bb4542', 97),
    ('009-c6eaa7316993afbcb5cb.zip', '8a896da346baf94ab4f24b0e396df0b79393c93aa05c50ef07cddd561a1ff8d7', 8_010_747),
    ('010-a2764930729cea661be3.mod', '53792e623827ef40be8f1af36dcf12790e82780b3d33b4b0944f56a3584bc429', 301),
    ('010-a2764930729cea661be3.zip', '85b486030e995cd5b4d56dea92f247b32bf4e0ae2fe6816b29d4514b5a43fec8', 3_553_586),
    ('011-4638677582e2455c59ce.mod', 'aa5e3ec9bb7b9f681609efac019d9de1a7ba7719248ff1eaa27e78882db3d7f5', 37),
    ('011-4638677582e2455c59ce.zip', 'c4e9f063cfed546c90f00a9657deac4f915a8994f8cbe6dbd3f18e79eb8302cf', 20_009),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "49f4aab3f71e52631aa48ac34ba7ee2a1ef3613814b06e87095ef75c3adaa1a1",
    1_673,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "3f1f178d3bd48b3b8d8792ae1be57716aacd7cba16f526afccfca3d4b998643c",
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
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave10" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave10_acquisition"
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
        "execute_success_recorded",
        "consumed_success_reporting_failed",
        "E_POST_SUCCESS_REPORTING",
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
    frozen_canonical_sha256 = sha256(canonical_bytes(frozen_canonical))
    require(
        len(frozen_canonical) == 40
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
            "combinedFixedPointV8": {
                "checkerPath": (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_v8.py"
                ),
                "checkerRawSha256": (
                    "798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32"
                ),
                "checkerNormalizedSha256": EXPECTED_V8_CHECKER_NORMALIZED,
                "testsPath": (
                    "script/test_p2p_nat_g2_pion_combined_fixed_point_v8.py"
                ),
                "testsRawSha256": (
                    "347a1e0083d2daedb40deba5fca491b63ee3137b5a7c18a56886be694ded16a0"
                ),
                "contentSha256": EXPECTED_V8_CONTENT,
                "combinedInputSetSha256": EXPECTED_V8_INPUT_SET,
                "graphSha256": EXPECTED_V8_GRAPH,
                "frontierSha256": EXPECTED_V8_FRONTIER,
                "sourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
                "v7TestsBindingScope":
                    "historical_metadata_only_not_live_held",
                "v7TestsLiveHeld": False,
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
        "aggregateModBytes": 1_400,
        "aggregateZipBytes": 27_772_126,
        "aggregateAcceptedBytes": 27_773_526,
        "aggregateZipEntryCount": 4_872,
        "aggregateZipUncompressedBytes": 108_563_141,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "acceptedResourceCount": 22,
        "selectedTupleCount": 1,
        "selectedRequestOrdinals": [21, 22],
        "modCount": 11,
        "zipCount": 11,
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
            "aetherlink.wave10-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave10-source-acquisition-readback-"
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
            "exact22ResourceOrderAndAggregateRecomputed": True,
            "exact40FrozenFileSnapshotRequired": True,
            "acceptedResourceHashSetCanonicalSha256Recomputed": True,
            "requestResourcesCanonicalSha256Recomputed": True,
            "combinedFixedPointV8PredecessorBindingRecomputed": True,
            "v8TestsLiveHeld": True,
            "v7TestsLiveHeld": False,
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
            "maximumAcceptedResourceCount": 22,
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
            "exact_offline_wave10_retained_snapshot_readback_"
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
        "documentType": "aetherlink.wave10-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 14,
        "acceptedResourceCount": 22,
        "selectedTupleCount": 1,
        "selectedRequestOrdinals": [21, 22],
        "aggregateAcceptedBytes": 27_773_526,
        "aggregateZipEntryCount": 4_872,
        "aggregateZipUncompressedBytes": 108_563_141,
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
                    "documentType": "aetherlink.wave10-acquisition-readback-permit-error",
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
                    "documentType": "aetherlink.wave10-acquisition-readback-permit-error",
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
