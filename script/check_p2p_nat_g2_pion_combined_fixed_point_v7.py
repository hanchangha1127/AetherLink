#!/usr/bin/env python3
"""Recompute the exact 257-input Wave1..Wave8 graph without publishing.

Run only with ``python3 -I -B -S``. The checker pins the immutable v6
combined checker, all Wave8 decision/acquisition/readback controls, and the
root archive plus 128 mod and 128 zip inputs. Every source input is opened
no-follow, held by descriptor, read twice, and used for two full graph
reconstructions. Fixed-point and frontier results are derived only from those
reconstructions. No dependency source is extracted, loaded, executed, or
compiled. The exact trusted pinned normal reconstruction path invokes zero
network, subprocess, authentication, device, Git, or file-write operations.
The provider proxy is defense-in-depth; it is not an OS syscall sandbox.
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
            "combined fixed-point v7 checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
from collections import defaultdict
import errno
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
SELF_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v7.py"
SELF_NORMALIZED_SHA256 = (
    "cf4fd9d25efe04c2ecb3eea882bb24d6c40b02f2f258c4ab01d824d1373d1c02"
)
V6_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v6.py"
V6_CHECKER_RAW_SHA256 = (
    "eee3d6bd5ec0857bc4832895f4c2d463b608ffc0a59436ebc2cde507cd9750e4"
)
V6_CHECKER_NORMALIZED_SHA256 = (
    "3f2a9866a185d157ab4fca021b52bc55aecac914fd5a08003e2f2f34e9522eef"
)
V6_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v6.py"
V6_TESTS_RAW_SHA256 = (
    "4ce508661695fd63c0e1c578a99cbfa9f369943283186958bf26b998839c7837"
)
V5_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v5.py"
V5_CHECKER_RAW_SHA256 = (
    "b63047c6867175655cf95710767dd930783dae5d99883dfb731aedeb59459e92"
)
V5_CHECKER_NORMALIZED_SHA256 = (
    "63587ee84ebe68aeb579c1bf85478e3c818ceaeaa8770e499d36b05ee41fe1aa"
)
V4_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v4.py"
V4_CHECKER_RAW_SHA256 = (
    "2576f7d2e0f0c8dffd2f4956254af3f62b39fdabb25b793242315f50b1373a52"
)
V1_PROVIDER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
V1_PROVIDER_RAW_SHA256 = (
    "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
)
TRANSITIVE_CHECKER_PATHS = {
    f"script/check_p2p_nat_g2_pion_combined_fixed_point_v{version}.py"
    for version in range(1, 7)
}
CHECKER_ID = (
    "g2-pion-ice-v4.3.0-combined-wave1-wave2-wave3-wave4-wave5-wave6-"
    "wave7-wave8-check-v7"
)
CODE_MAXIMUM_BYTES = 4 * 1024 * 1024
JSON_MAXIMUM_BYTES = 8 * 1024 * 1024
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)

WAVE8_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave8-v1.json"
)
WAVE8_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-"
    "execution-permit-v1.json"
)
WAVE8_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-receipt-v1.json"
)
WAVE8_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-manifest-v1.json"
)
WAVE8_READBACK_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-"
    "readback-execution-permit-v1.json"
)
WAVE8_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-readback-v1.json"
)
WAVE8_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-"
    "readback-manifest-v1.json"
)
WAVE8_ACCEPTED_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-8-v1/accepted"
)
WAVE8_ACQUISITION_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-8-v1.claim"
)
WAVE8_EVIDENCE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-8-v1/evidence.json"
)
WAVE8_READBACK_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-8-v1-readback.claim"
)
WAVE8_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave8-failure-v1.json"
)
WAVE8_STAGING_PREFIX = ".wave-8-v1-staging-"
WAVE8_READBACK_TEMP_PREFIXES = (
    ".bounded-dependency-source-acquisition-wave8-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave8-readback-"
        "manifest-v1.json.tmp-"
    ),
)

WAVE8_CONTROL_SHA256 = {
    WAVE8_DECISION_PATH:
        "45236a2ea42a4a3af59e60d27ed2f09cd5d191e34a6db992a9d81cb49316297e",
    WAVE8_PERMIT_PATH:
        "8595241898ebc14d563f5b03c3a4b46afdd995207bc1597d86c861e5c37bcb4c",
    WAVE8_RECEIPT_PATH:
        "77ca07dadeddd5578b08c1aab7b746b50f6d2e4f0ee83d0a73baa3cc4cb6ec68",
    WAVE8_MANIFEST_PATH:
        "5c440c55c3534c0d8b537fbbc0843b4e053f5e0c7397a568638dd043619abebe",
    WAVE8_READBACK_PERMIT_PATH:
        "36e44e0304a32026f645ce579493206537f57b9456684b3aa497b0298190851c",
    WAVE8_READBACK_PATH:
        "b61738fe4ffae1b4aec7ee7fd8f7a186962cbbebf8911afd7d1fd0e94f0a5fce",
    WAVE8_READBACK_MANIFEST_PATH:
        "79f844b647915661b0b36fd5fa333591327ad934d6589c0fc98c912e7660d62f",
}
WAVE8_CONTROL_METADATA = {
    WAVE8_DECISION_PATH: (27_639, 0o644),
    WAVE8_PERMIT_PATH: (30_422, 0o644),
    WAVE8_RECEIPT_PATH: (1_671, 0o600),
    WAVE8_MANIFEST_PATH: (463, 0o600),
    WAVE8_READBACK_PERMIT_PATH: (22_505, 0o644),
    WAVE8_READBACK_PATH: (15_104, 0o600),
    WAVE8_READBACK_MANIFEST_PATH: (2_296, 0o600),
}
WAVE8_CONTENT_SHA256 = {
    WAVE8_DECISION_PATH:
        "1e1d62f03fe3137a88aa9413be8310bf7260f65a4825a09baab9a848ce6969da",
    WAVE8_PERMIT_PATH:
        "527a4558d069b31f92256926ea90e05c8353a33f65128b131d1c960614df925b",
    WAVE8_READBACK_PERMIT_PATH:
        "f72ddfce42814469d3f7903a1a59a769d4ac22e910db093addf80be5494fd39e",
    WAVE8_READBACK_PATH:
        "78f7929982d34c4b6ace1779eb8ce85a8dc8fc54a03209e8509ddede61e74b16",
    WAVE8_READBACK_MANIFEST_PATH:
        "7218de236796568e5e56d92f813ad852d093ab6a5e7cef8681658ca011c58443",
}
WAVE8_REQUEST_SET_SHA256 = (
    "b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc"
)
WAVE8_PERMIT_RESOURCES_SHA256 = (
    "ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136"
)
WAVE8_RESOURCE_SET_SHA256 = (
    "7642f0b4dea8fee8eb92f573a3a4d948aa46a8736be70857097ce3b83af2eb38"
)
WAVE8_FROZEN_FILE_SET_SHA256 = (
    "ebf86b268714148fefacb338080f89a5c3381009474c2e932a00101e0f2ed5da"
)
WAVE8_ATTEMPT_ID = "6d8ea4473126c853b439c56a895f9c28"
WAVE8_READBACK_ATTEMPT_ID = "8618087527c005b5d19c8f902ec33557"
WAVE8_COMPACT_IDENTITY_SHA256 = (
    "c6aa1a974ad09f11927c103c7f2b63df0835d09b41d0dac9f6349d46d377a388"
)
WAVE8_FULL_WITNESS_SHA256 = (
    "044dc1dd0675d781d174825dbe8e419d7ff0fe6029b590e2d16c5edeed5f08ae"
)
WAVE8_HELD_SOURCE_BINDINGS_SHA256 = (
    "8358b58ad8925633d78c6c1c6160d6d52567c39a2d4c940d01a05cfc87419343"
)
WAVE8_ACQUISITION_CLAIM_RAW_SHA256 = (
    "772ac8daf78e313281245d6474dfee38bfe10b32b5e74953ef7bb45fed6a9265"
)
WAVE8_ACQUISITION_EVIDENCE_RAW_SHA256 = (
    "7431c37bacb8c630b24f4793aa0351e8ec4280080b32a52af41999dafa20cfbb"
)
WAVE8_ACQUISITION_CHECKER_RAW_SHA256 = (
    "78132ce62e3ba4b74fb404983d55b003119106eba34c3cba6b6fbc7622a0ca20"
)
WAVE8_ACQUISITION_RUNNER_RAW_SHA256 = (
    "cc11c0fa3b552afc05436c4a7568617796eeb6daa2fbc630aba8fd3e9603a7c9"
)
WAVE8_READBACK_CLAIM_RAW_SHA256 = (
    "aa696de4edaa8aad7e8a256dd0900680b42e3c0b6d2f877623461f6fe2bf5f6a"
)
WAVE8_READBACK_CLAIM_CONTENT_SHA256 = (
    "145991b0eee0ac7c1634c7133f26461aa42ca15abfef6df54a388e080634407a"
)
WAVE8_READBACK_CHECKER_RAW_SHA256 = (
    "f1073471aecc3d4003e6e85fdbdc5add92064ee9576d9b285e97fde66b59f4a9"
)
WAVE8_READBACK_RECORDER_RAW_SHA256 = (
    "7d02d81a64dc34c132f66194cd3893177eb57c2e51e3932ee1b7f526b1e32e42"
)
WAVE8_RETAINED_BARRIERS = [
    "complete_snapshot_and_claim_immediately_before_receipt",
    "complete_snapshot_claim_and_receipt_after_receipt",
    (
        "complete_snapshot_claim_and_receipt_immediately_before_"
        "manifest_publication"
    ),
]
V6_CANDIDATE_CONTENT_SHA256 = (
    "b33ef7a10de32dc99cea1dbbbcab1dac3a549eb466ef80b0229d2a0381ab9052"
)
V6_INPUT_SET_SHA256 = (
    "f7ad0b43d571da61edd4941f8e504d54d014b01f3395aeca8d0d10b9b3c22349"
)
V6_GRAPH_SHA256 = (
    "3648bdf037e316e69e155615edd5748c2bb653238579216ddd8b8dce4beb9f09"
)
V6_FRONTIER_SHA256 = (
    "d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92"
)
V6_AUTHORITY = {
    "decisionAuthorityGranted": False,
    "executionAuthorityGranted": False,
    "acquisitionAuthorityGranted": False,
    "publicationAuthorityGranted": False,
    "networkAuthorized": False,
    "sourceExecutionAuthorized": False,
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
    "osSyscallSandboxProvided": False,
}

WAVE8_ACQUISITION_AUTHORITY = {
    "accountRequired": False,
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
    "ownerRequired": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "productRuntimeNetworkAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "sshRequired": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
    "wave8PublicProxy28GetAcquisitionAuthorizedOnce": True,
}
WAVE8_READBACK_AUTHORITY = {
    "authenticationRequired": False,
    "compileAuthorized": False,
    "credentialRequired": False,
    "deploymentAuthorized": False,
    "deviceAuthorized": False,
    "dnsAuthorized": False,
    "externalAuthenticationRequired": False,
    "failedTemporaryCleanupAuthorized": True,
    "frozenInputWritesAuthorized": False,
    "gitOperationAuthorized": False,
    "networkAuthorized": False,
    "offlineReadbackAuthorizedOnce": True,
    "otherRepositoryWritesAuthorized": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "proxyAuthorized": False,
    "readbackClaimWriteAuthorized": True,
    "readbackManifestWriteAuthorized": True,
    "readbackReceiptWriteAuthorized": True,
    "repositoryOwnerIdentityProofRequired": False,
    "sameDirectoryTemporaryPublicationAuthorized": True,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceAcquisitionAuthorized": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}
WAVE8_READBACK_AUTHORITY_BINDING = {
    "checker": {
        "path": (
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave8_"
            "readback_execution_permit_v1.py"
        ),
        "rawSha256": WAVE8_READBACK_CHECKER_RAW_SHA256,
    },
    "permit": {
        "contentSha256": WAVE8_CONTENT_SHA256[WAVE8_READBACK_PERMIT_PATH],
        "path": WAVE8_READBACK_PERMIT_PATH,
        "rawSha256": WAVE8_CONTROL_SHA256[WAVE8_READBACK_PERMIT_PATH],
    },
    "recorder": {
        "path": (
            "script/record_p2p_nat_g2_pion_rung3_dependency_wave8_"
            "readback_v1_once.py"
        ),
        "rawSha256": WAVE8_READBACK_RECORDER_RAW_SHA256,
    },
}


class CombinedCheckFailure(RuntimeError):
    """A content-free, fail-closed checker error."""


class CliUsageFailure(RuntimeError):
    """A content-free command-line error."""


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise CliUsageFailure("E_ARGUMENT")


def check(condition: bool, code: str) -> None:
    if not condition:
        raise CombinedCheckFailure(code)


def exact_keys(value: Any, keys: Sequence[str]) -> bool:
    return type(value) is dict and set(value) == set(keys)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wave8_digest_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def normalized_self_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    check(start >= 0, "E_SELF_IDENTITY")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    check(
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
    """Retry once when a close failure leaves constructor-owned state."""

    for _ in range(2):
        try:
            resource.close()
        except BaseException:
            continue
        break


class PinnedCodeFile:
    """Open and retain one exact no-follow Python tool input."""

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
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.raw = b""
        try:
            parts = relative_path.split("/")
            check(
                parts
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
                self.directories.append((child, info, current, component))
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
            check(
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
        check(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_TOOL_IDENTITY",
        )

    @staticmethod
    def _validate_file(info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= CODE_MAXIMUM_BYTES,
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
            check(bool(chunk), "E_TOOL_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_TOOL_IDENTITY")
        check(
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
        check(
            file_identity(current)
            == file_identity(named)
            == file_identity(self.initial),
            "E_TOOL_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            check(
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

        previous_owned = list(self.owned_fds)
        for owned_fd in reversed(previous_owned):
            close_once(owned_fd)
        self.owned_fds = [
            owned_fd
            for owned_fd in previous_owned
            if owned_fd in remaining
        ]
        self.directories.clear()
        self.fd = self.fd if self.fd in remaining else -1
        self.parent_fd = (
            self.parent_fd if self.parent_fd in remaining else -1
        )
        self.root_fd = self.root_fd if self.root_fd in remaining else -1
        if errors:
            raise errors[0]

    def __enter__(self) -> "PinnedCodeFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def safe_relative_path(value: Any) -> str:
    check(
        type(value) is str
        and bool(value)
        and not value.startswith("/")
        and "\x00" not in value
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/")),
        "E_HELD_SET",
    )
    return value


class SafeHeldFile:
    """Retain one provider input with immediate descriptor ownership."""

    def __init__(
        self,
        root_fd: int,
        relative: str,
        *,
        maximum_bytes: int,
        owner_only: bool,
    ) -> None:
        self.relative = safe_relative_path(relative)
        check(
            type(maximum_bytes) is int
            and maximum_bytes >= 1
            and type(owner_only) is bool,
            "E_HELD_SET",
        )
        self.maximum_bytes = maximum_bytes
        self.owner_only = owner_only
        self.directory_fds: list[
            tuple[int, os.stat_result, int, str]
        ] = []
        self.owned_fds: list[int] = []
        self.fd = -1
        self.parent_fd = -1
        try:
            current = self._own(os.dup(root_fd))
            for component in self.relative.split("/")[:-1]:
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
                self.directory_fds.append(
                    (child, info, current, component)
                )
                current = child
            self.parent_fd = current
            self.name = self.relative.rsplit("/", 1)[-1]
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
        except BaseException:
            retry_constructor_cleanup(self)
            raise

    def _own(self, fd: int) -> int:
        self.owned_fds.append(fd)
        return fd

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        check(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_HELD_SET",
        )

    def _validate_file(self, info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and 0 <= info.st_size <= self.maximum_bytes,
            "E_HELD_SET",
        )
        mode = stat.S_IMODE(info.st_mode)
        check(
            mode == 0o600 if self.owner_only else mode & 0o022 == 0,
            "E_HELD_SET",
        )

    def read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_HELD_SET")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_HELD_SET")
        check(
            file_identity(os.fstat(self.fd)) == file_identity(before),
            "E_HELD_SET",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        check(
            file_identity(os.fstat(self.fd))
            == file_identity(self.initial)
            == file_identity(
                os.stat(
                    self.name,
                    dir_fd=self.parent_fd,
                    follow_symlinks=False,
                )
            ),
            "E_HELD_SET",
        )
        for child, initial, parent, component in self.directory_fds:
            check(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                == directory_identity(
                    os.stat(
                        component,
                        dir_fd=parent,
                        follow_symlinks=False,
                    )
                ),
                "E_HELD_SET",
            )

    def close(self) -> None:
        errors: list[OSError] = []
        remaining: set[int] = set()
        for fd in reversed(self.owned_fds):
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
        self.owned_fds = [
            fd for fd in self.owned_fds if fd in remaining
        ]
        self.directory_fds.clear()
        self.fd = self.fd if self.fd in remaining else -1
        self.parent_fd = (
            self.parent_fd if self.parent_fd in remaining else -1
        )
        if errors:
            raise errors[0]


class SafeHeldInputSet:
    """Provider-compatible held set using only safe held files."""

    def __init__(
        self,
        root: Path,
        bindings: Sequence[Mapping[str, Any]],
    ) -> None:
        self.root = root
        self.root_fd = -1
        self.files: dict[str, SafeHeldFile] = {}
        self.raw: dict[str, bytes] = {}
        try:
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            SafeHeldFile._validate_directory(os.fstat(self.root_fd))
            paths: set[str] = set()
            for binding in bindings:
                path = safe_relative_path(binding.get("path"))
                check(path not in paths, "E_INPUT_INVENTORY")
                paths.add(path)
                expected = binding.get("rawSha256")
                maximum = binding.get("maximumBytes")
                owner_only = binding.get("ownerOnly")
                check(
                    type(expected) is str
                    and len(expected) == 64
                    and all(
                        character in "0123456789abcdef"
                        for character in expected
                    )
                    and type(maximum) is int
                    and maximum >= 1
                    and type(owner_only) is bool,
                    "E_INPUT_INVENTORY",
                )
                held = SafeHeldFile(
                    self.root_fd,
                    path,
                    maximum_bytes=maximum,
                    owner_only=owner_only,
                )
                self.files[path] = held
                first = held.read_pass()
                second = held.read_pass()
                check(
                    first == second and sha256_bytes(first) == expected,
                    "E_PREDECESSOR_IDENTITY",
                )
                self.raw[path] = first
            self.final_barrier()
        except BaseException:
            retry_constructor_cleanup(self)
            raise

    def final_barrier(self) -> None:
        for held in self.files.values():
            held.final_barrier()

    def close(self) -> None:
        errors: list[OSError] = []
        retained: dict[str, SafeHeldFile] = {}
        for path, held in list(self.files.items()):
            try:
                held.close()
            except OSError as error:
                errors.append(error)
                if held.owned_fds:
                    retained[path] = held
        self.files = retained
        if self.root_fd >= 0:
            root_fd = self.root_fd
            try:
                os.close(root_fd)
            except OSError as error:
                errors.append(error)
                try:
                    os.fstat(root_fd)
                except OSError as probe_error:
                    if probe_error.errno == errno.EBADF:
                        self.root_fd = -1
                else:
                    pass
            else:
                self.root_fd = -1
        if errors:
            raise errors[0]

    def __enter__(self) -> "SafeHeldInputSet":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class SafePinnedRunnerFile(PinnedCodeFile):
    """Provider pin adapter with the v1 constructor signature."""

    def __init__(self, root: Path) -> None:
        super().__init__(
            root,
            V1_PROVIDER_PATH,
            V1_PROVIDER_RAW_SHA256,
        )


class ReadOnlyOSProxy:
    """Expose provider filesystem reads while rejecting every write surface."""

    __slots__ = ()

    _READ_ATTRIBUTES = {
        "O_CLOEXEC",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_NONBLOCK",
        "O_RDONLY",
        "SEEK_SET",
        "close",
        "dup",
        "fstat",
        "geteuid",
        "listdir",
        "lseek",
        "lstat",
        "read",
        "stat",
        "stat_result",
    }
    _MUTATION_ATTRIBUTES = {
        "O_APPEND",
        "O_CREAT",
        "O_EXCL",
        "O_RDWR",
        "O_TMPFILE",
        "O_TRUNC",
        "O_WRONLY",
        "fchmod",
        "fsync",
        "link",
        "mkdir",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "symlink",
        "truncate",
        "unlink",
        "write",
    }

    @staticmethod
    def open(
        path: Any,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        write_mask = 0
        for name in (
            "O_APPEND",
            "O_CREAT",
            "O_EXCL",
            "O_RDWR",
            "O_TMPFILE",
            "O_TRUNC",
            "O_WRONLY",
        ):
            write_mask |= getattr(os, name, 0)
        check(
            type(flags) is int and flags & write_mask == 0,
            "E_TRANSITIVE_WRITE",
        )
        if dir_fd is None:
            return os.open(path, flags, mode)
        return os.open(path, flags, mode, dir_fd=dir_fd)

    def __getattr__(self, name: str) -> Any:
        if name in self._MUTATION_ATTRIBUTES:
            raise CombinedCheckFailure("E_TRANSITIVE_WRITE")
        if name in self._READ_ATTRIBUTES:
            return getattr(os, name)
        raise AttributeError(name)

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_TRANSITIVE_WRITE")


class ReadOnlyZipArchive:
    """Minimal read-only ZipFile view used by graph reconstruction."""

    def __init__(
        self,
        file: Any,
        mode: str = "r",
        *,
        allowZip64: bool = True,
    ) -> None:
        check(mode == "r", "E_TRANSITIVE_WRITE")
        self._archive = zipfile.ZipFile(
            file,
            mode="r",
            allowZip64=allowZip64,
        )

    def infolist(self) -> list[zipfile.ZipInfo]:
        return self._archive.infolist()

    def read(
        self,
        name: str | zipfile.ZipInfo,
        pwd: bytes | None = None,
    ) -> bytes:
        return self._archive.read(name, pwd=pwd)

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> "ReadOnlyZipArchive":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class ReadOnlyZipFacade:
    __slots__ = ("ZipFile",)
    BadZipFile = zipfile.BadZipFile
    ZIP_DEFLATED = zipfile.ZIP_DEFLATED
    ZIP_STORED = zipfile.ZIP_STORED

    def __init__(self) -> None:
        object.__setattr__(
            self,
            "ZipFile",
            ReadOnlyProviderCallable(ReadOnlyZipArchive),
        )

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_PROVIDER_FACADE")


class ReadOnlyIOFacade:
    __slots__ = ()
    BytesIO = io.BytesIO


class SafeReviewFailure(RuntimeError):
    """Provider-compatible error without provider-module globals."""

    def __init__(
        self,
        code: str,
        phase: str,
        *,
        tuple_id: str | None = None,
        tuple_order: int | None = None,
        resource_kind: str | None = None,
        observations: Mapping[str, int] | None = None,
    ) -> None:
        safe_code = code if type(code) is str else "E_INTERNAL"
        safe_phase = phase if type(phase) is str else "runner"
        super().__init__(safe_code)
        self.code = safe_code
        self.phase = safe_phase
        self.tuple_id = tuple_id if type(tuple_id) is str else None
        self.tuple_order = (
            tuple_order if type(tuple_order) is int else None
        )
        self.resource_kind = (
            resource_kind if type(resource_kind) is str else None
        )
        self.observations = dict(
            sorted(
                (key, value)
                for key, value in (observations or {}).items()
                if type(key) is str
                and type(value) is int
                and 0 <= value <= (1 << 53) - 1
            )
        )


class ReadOnlyProviderCallable:
    """Callable wrapper that does not expose raw provider globals."""

    __slots__ = ("__target",)

    def __init__(self, target: Any) -> None:
        object.__setattr__(
            self,
            "_ReadOnlyProviderCallable__target",
            target,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        target = object.__getattribute__(
            self,
            "_ReadOnlyProviderCallable__target",
        )
        return target(*args, **kwargs)

    def __getattribute__(self, name: str) -> Any:
        if name in {
            "__closure__",
            "__code__",
            "__defaults__",
            "__globals__",
            "__kwdefaults__",
            "_ReadOnlyProviderCallable__target",
            "_target",
        }:
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_PROVIDER_FACADE")


class ReadOnlyProviderFacade:
    """Immutable allow-list facade over pinned provider functions."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        object.__setattr__(
            self,
            "_values",
            types.MappingProxyType(dict(values)),
        )

    def __getattr__(self, name: str) -> Any:
        values = object.__getattribute__(self, "_values")
        try:
            return values[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __getattribute__(self, name: str) -> Any:
        if name == "_values":
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_PROVIDER_FACADE")

    def __dir__(self) -> list[str]:
        values = object.__getattribute__(self, "_values")
        return sorted(values)


PROVIDER_API = (
    "DEFAULT_MAXIMUM_AGGREGATE_ENTRIES",
    "DEFAULT_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES",
    "DEFAULT_MAXIMUM_ARCHIVE_BYTES",
    "DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE",
    "DEFAULT_MAXIMUM_ENTRY_BYTES",
    "DEFAULT_MAXIMUM_GRAPH_EDGES",
    "DEFAULT_MAXIMUM_GRAPH_NODES",
    "GRAPH_ALGORITHM",
    "ReviewFailure",
    "_eocd_exact",
    "build_graph",
    "canonical_json_bytes",
    "content_bound",
    "exact_int",
    "extract_build_expression",
    "go_proxy_escape",
    "has_zip64_extra",
    "inspect_zip_bytes",
    "is_license_path",
    "parse_go_imports",
    "parse_go_mod",
    "profile_rows",
    "require",
    "safe_archive_name",
    "source_class",
    "special_classes",
    "strict_json",
)


def load_provider_facade(held: SafePinnedRunnerFile) -> ReadOnlyProviderFacade:
    check(
        type(held) is SafePinnedRunnerFile
        and sha256_bytes(held.raw) == V1_PROVIDER_RAW_SHA256,
        "E_PROVIDER_IDENTITY",
    )
    module = types.ModuleType("aetherlink_read_only_graph_provider_v1")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V1_PROVIDER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_read_only_graph_provider_v1",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V1_PROVIDER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_PROVIDER_LOAD") from error
    check(
        all(hasattr(module, name) for name in PROVIDER_API),
        "E_PROVIDER_API",
    )
    os_proxy = ReadOnlyOSProxy()
    io_facade = ReadOnlyIOFacade()
    zip_facade = ReadOnlyZipFacade()
    module.os = os_proxy
    module.io = io_facade
    module.zipfile = zip_facade
    module.ReviewFailure = SafeReviewFailure
    module.HeldFile = SafeHeldFile
    module.HeldInputSet = SafeHeldInputSet
    values: dict[str, Any] = {}
    for name in PROVIDER_API:
        value = getattr(module, name)
        values[name] = (
            ReadOnlyProviderCallable(value)
            if callable(value) and name != "ReviewFailure"
            else value
        )
    values.update(
        {
            "HeldInputSet": ReadOnlyProviderCallable(SafeHeldInputSet),
            "io": io_facade,
            "zipfile": zip_facade,
        }
    )
    return ReadOnlyProviderFacade(values)


HARDENED_CHECKER_PATHS: set[str] = set()
PROVIDER_FACADE_LOAD_COUNT = 0


def harden_checker_module(module: types.ModuleType) -> types.ModuleType:
    """Recursively replace every transitive pin and provider loader."""

    if module.__dict__.get("_v7_safe_hardened") is True:
        return module
    module.__dict__["_v7_safe_hardened"] = True
    module_path = str(module.__dict__.get("__file__", ""))
    HARDENED_CHECKER_PATHS.add(module_path)
    if "PinnedCodeFile" in module.__dict__:
        module.PinnedCodeFile = PinnedCodeFile
    for name, value in list(module.__dict__.items()):
        if not (
            name.startswith("load_v")
            and name.endswith("_checker")
            and callable(value)
        ):
            continue

        def recursive_loader(
            held: PinnedCodeFile,
            *,
            _loader: Any = value,
        ) -> types.ModuleType:
            child = _loader(held)
            check(type(child) is types.ModuleType, "E_CHECKER_HARDENING")
            return harden_checker_module(child)

        recursive_loader.__name__ = name
        module.__dict__[name] = recursive_loader
    if "load_pinned_runner" in module.__dict__:
        module.PinnedRunnerFile = SafePinnedRunnerFile

        def safe_provider_loader(
            held: SafePinnedRunnerFile,
        ) -> ReadOnlyProviderFacade:
            global PROVIDER_FACADE_LOAD_COUNT
            PROVIDER_FACADE_LOAD_COUNT += 1
            return load_provider_facade(held)

        module.load_pinned_runner = safe_provider_loader
    return module


def load_v6_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v6_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V6_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v6_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V6_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V6_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v5_checker",
        "wave7_control_bindings",
        "parse_wave7_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V6_CHECKER_API")
    check(
        module.SELF_PATH == V6_CHECKER_PATH
        and sha256_bytes(held.raw) == V6_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V6_CHECKER_NORMALIZED_SHA256,
        "E_V6_CHECKER_API",
    )
    return module


def wave8_control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": WAVE8_CONTROL_METADATA[path][1] == 0o600,
            "kind": "terminal_evidence",
        }
        for path, digest in WAVE8_CONTROL_SHA256.items()
    ]


def parse_wave8_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in WAVE8_CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_WAVE8_JSON")
        result[path] = value
    return result


def wave8_auxiliary_evidence_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": WAVE8_ACQUISITION_CLAIM_PATH,
            "rawSha256": WAVE8_ACQUISITION_CLAIM_RAW_SHA256,
            "maximumBytes": 416,
            "ownerOnly": True,
            "kind": "consumed_acquisition_claim",
        },
        {
            "path": WAVE8_EVIDENCE_PATH,
            "rawSha256": WAVE8_ACQUISITION_EVIDENCE_RAW_SHA256,
            "maximumBytes": 11_258,
            "ownerOnly": True,
            "kind": "frozen_acquisition_evidence",
        },
        {
            "path": WAVE8_READBACK_CLAIM_PATH,
            "rawSha256": WAVE8_READBACK_CLAIM_RAW_SHA256,
            "maximumBytes": 1_251,
            "ownerOnly": True,
            "kind": "consumed_readback_claim",
        },
    ]


def portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def validate_wave8_completed_namespace(
    control_held: Any,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    acquisition_claim = control_held.files[WAVE8_ACQUISITION_CLAIM_PATH]
    readback_claim = control_held.files[WAVE8_READBACK_CLAIM_PATH]
    evidence = control_held.files[WAVE8_EVIDENCE_PATH]
    readback = control_held.files[WAVE8_READBACK_PATH]
    readback_manifest = control_held.files[WAVE8_READBACK_MANIFEST_PATH]
    for path, (expected_bytes, expected_mode) in WAVE8_CONTROL_METADATA.items():
        info = os.fstat(control_held.files[path].fd)
        check(
            info.st_uid == os.geteuid()
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == expected_mode
            and info.st_size == expected_bytes,
            "E_WAVE8_CONTROL_METADATA",
        )
    for held, expected_bytes in (
        (acquisition_claim, 416),
        (evidence, 11_258),
        (readback_claim, 1_251),
    ):
        info = os.fstat(held.fd)
        check(
            info.st_uid == os.geteuid()
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == expected_bytes,
            "E_WAVE8_AUXILIARY_METADATA",
        )

    dependency_names = os.listdir(acquisition_claim.parent_fd)
    base_names = os.listdir(readback.parent_fd)
    final_names = os.listdir(evidence.parent_fd)
    normalized_dependency_names = [
        portable_name(name) for name in dependency_names
    ]
    normalized_base_names = [portable_name(name) for name in base_names]
    normalized_final_names = [portable_name(name) for name in final_names]
    exact_dependency_names = {
        Path(WAVE8_ACQUISITION_CLAIM_PATH).name,
        Path(WAVE8_READBACK_CLAIM_PATH).name,
    }
    exact_base_names = {
        Path(path).name for path in WAVE8_CONTROL_SHA256
    }
    exact_final_names = {"accepted", "evidence.json"}
    check(
        all(
            normalized_dependency_names.count(portable_name(name)) == 1
            for name in exact_dependency_names
        )
        and all(
            normalized_base_names.count(portable_name(name)) == 1
            for name in exact_base_names
        )
        and not any(
            name.startswith(portable_name(WAVE8_STAGING_PREFIX))
            for name in normalized_dependency_names
        )
        and portable_name(Path(WAVE8_FAILURE_PATH).name)
        not in normalized_base_names
        and not any(
            name.startswith(portable_name(prefix))
            for name in normalized_base_names
            for prefix in WAVE8_READBACK_TEMP_PREFIXES
        )
        and len(final_names) == len(exact_final_names)
        and set(final_names) == exact_final_names
        and len(set(normalized_final_names)) == len(exact_final_names),
        "E_WAVE8_NAMESPACE",
    )
    check(
        readback.parent_fd == readback_manifest.parent_fd
        or directory_identity(os.fstat(readback.parent_fd))
        == directory_identity(os.fstat(readback_manifest.parent_fd)),
        "E_WAVE8_NAMESPACE",
    )
    final_info = os.fstat(evidence.parent_fd)
    check(
        final_info.st_uid == os.geteuid()
        and final_info.st_nlink == 4
        and stat.S_IMODE(final_info.st_mode) == 0o700,
        "E_WAVE8_NAMESPACE",
    )

    readback_permit = documents[WAVE8_READBACK_PERMIT_PATH]
    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    accepted = (
        snapshot.get("acceptedDirectory")
        if type(snapshot) is dict
        else None
    )
    accepted_files = (
        accepted.get("files") if type(accepted) is dict else None
    )
    check(
        type(accepted_files) is list and len(accepted_files) == 28,
        "E_WAVE8_NAMESPACE",
    )
    expected_accepted_names = {
        Path(row.get("path", "")).name
        for row in accepted_files
        if type(row) is dict and type(row.get("path")) is str
    }
    check(
        len(expected_accepted_names) == 28
        and all(
            Path(row["path"]).parent.as_posix() == WAVE8_ACCEPTED_DIRECTORY
            for row in accepted_files
        ),
        "E_WAVE8_NAMESPACE",
    )
    accepted_fd = -1
    try:
        accepted_fd = os.open(
            "accepted",
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
            dir_fd=evidence.parent_fd,
        )
        accepted_info = os.fstat(accepted_fd)
        accepted_names = os.listdir(accepted_fd)
        normalized_accepted_names = [
            portable_name(name) for name in accepted_names
        ]
        check(
            accepted_info.st_uid == os.geteuid()
            and accepted_info.st_nlink == 30
            and stat.S_IMODE(accepted_info.st_mode) == 0o700
            and len(accepted_names) == 28
            and set(accepted_names) == expected_accepted_names
            and len(set(normalized_accepted_names)) == 28,
            "E_WAVE8_NAMESPACE",
        )
    finally:
        if accepted_fd >= 0:
            os.close(accepted_fd)


def validate_wave8_consumed_claims(
    runner: types.ModuleType,
    acquisition_raw: bytes,
    readback_raw: bytes,
) -> None:
    acquisition_claim = runner.strict_json(
        acquisition_raw,
        WAVE8_ACQUISITION_CLAIM_PATH,
    )
    readback_claim = runner.strict_json(
        readback_raw,
        WAVE8_READBACK_CLAIM_PATH,
    )
    check(
        acquisition_raw == runner.canonical_json_bytes(acquisition_claim)
        and exact_keys(
            acquisition_claim,
            (
                "attemptId", "checkerRawSha256", "documentType",
                "externalAuthenticationRequired", "permitContentSha256",
                "requestCount", "schemaVersion", "status",
                "userActionRequired",
            ),
        )
        and acquisition_claim
        == {
            "attemptId": WAVE8_ATTEMPT_ID,
            "checkerRawSha256": WAVE8_ACQUISITION_CHECKER_RAW_SHA256,
            "documentType": "aetherlink.wave8-source-acquisition-claim",
            "externalAuthenticationRequired": False,
            "permitContentSha256": WAVE8_CONTENT_SHA256[WAVE8_PERMIT_PATH],
            "requestCount": 28,
            "schemaVersion": "1.0",
            "status": "consumed_active",
            "userActionRequired": False,
        },
        "E_WAVE8_ACQUISITION_CLAIM",
    )
    without = dict(readback_claim)
    without.pop("contentBinding", None)
    check(
        readback_raw == runner.canonical_json_bytes(readback_claim)
        and exact_keys(
            readback_claim,
            (
                "acquisitionAttemptId", "authorityBinding",
                "claimPersistsAfterSuccessFailureOrUncertainty",
                "contentBinding", "documentType",
                "externalAuthenticationRequired", "readbackAttemptId",
                "retryAllowed", "schemaVersion", "status",
                "userActionRequired",
            ),
        )
        and readback_claim.get("contentBinding")
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE8_READBACK_CLAIM_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == WAVE8_READBACK_CLAIM_CONTENT_SHA256
        and readback_claim.get("acquisitionAttemptId") == WAVE8_ATTEMPT_ID
        and readback_claim.get("readbackAttemptId")
        == WAVE8_READBACK_ATTEMPT_ID
        and readback_claim.get("authorityBinding")
        == WAVE8_READBACK_AUTHORITY_BINDING
        and readback_claim.get("documentType")
        == "aetherlink.wave8-acquisition-readback-one-use-claim"
        and readback_claim.get(
            "claimPersistsAfterSuccessFailureOrUncertainty"
        )
        is True
        and readback_claim.get("retryAllowed") is False
        and readback_claim.get("schemaVersion") == "1.0"
        and readback_claim.get("status") == "consumed_active"
        and readback_claim.get("externalAuthenticationRequired") is False
        and readback_claim.get("userActionRequired") is False,
        "E_WAVE8_READBACK_CLAIM",
    )


def validate_wave8_evidence(
    runner: types.ModuleType,
    raw: bytes,
    evidence_document: Mapping[str, Any],
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    check(type(evidence_document) is dict, "E_WAVE8_EVIDENCE")
    readback = documents[WAVE8_READBACK_PATH]
    verified = readback.get("verified")
    evidence_resources = evidence_document.get("resources")
    verified_resources = (
        verified.get("resources") if type(verified) is dict else None
    )
    check(
        exact_keys(
            evidence_document,
            (
                "aggregateModResponseBytes", "aggregateResponseBytes",
                "aggregateZipEntryCount", "aggregateZipResponseBytes",
                "aggregateZipUncompressedBytes", "attemptId",
                "documentType", "requestCount", "resources",
                "schemaVersion",
            ),
        )
        and raw == runner.canonical_json_bytes(evidence_document)
        and sha256_bytes(raw) == WAVE8_ACQUISITION_EVIDENCE_RAW_SHA256
        and evidence_document.get("documentType")
        == "aetherlink.wave8-source-acquisition-evidence"
        and evidence_document.get("schemaVersion") == "1.0"
        and evidence_document.get("attemptId") == WAVE8_ATTEMPT_ID
        and evidence_document.get("requestCount") == 28
        and evidence_document.get("aggregateResponseBytes") == 35_196_959
        and evidence_document.get("aggregateModResponseBytes") == 1_730
        and evidence_document.get("aggregateZipResponseBytes") == 35_195_229
        and evidence_document.get("aggregateZipEntryCount") == 4_907
        and evidence_document.get("aggregateZipUncompressedBytes")
        == 144_867_307
        and type(evidence_resources) is list
        and len(evidence_resources) == 28
        and type(verified_resources) is list
        and runner.canonical_json_bytes(evidence_resources)
        == runner.canonical_json_bytes(verified_resources),
        "E_WAVE8_EVIDENCE",
    )


def verify_wave8_content_bindings(
    v4: types.ModuleType,
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    v4.verify_modern_content_binding(
        runner,
        documents[WAVE8_DECISION_PATH],
        WAVE8_CONTENT_SHA256[WAVE8_DECISION_PATH],
        "decision_without_contentBinding",
    )
    v4.verify_modern_content_binding(
        runner,
        documents[WAVE8_PERMIT_PATH],
        WAVE8_CONTENT_SHA256[WAVE8_PERMIT_PATH],
        "permit_without_contentBinding",
    )
    for path in (
        WAVE8_READBACK_PERMIT_PATH,
        WAVE8_READBACK_PATH,
        WAVE8_READBACK_MANIFEST_PATH,
    ):
        v4.verify_content_binding(
            runner,
            documents[path],
            WAVE8_CONTENT_SHA256[path],
        )


def validate_v6_predecessor_candidate(
    runner: types.ModuleType,
    candidate: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    predecessor = decision.get("predecessorBindings", {}).get(
        "combinedFixedPointV6"
    )
    binding = candidate.get("contentBinding")
    without = dict(candidate)
    without.pop("contentBinding", None)
    inputs = candidate.get("inputSet")
    source_bindings = (
        inputs.get("sourceBindings") if type(inputs) is dict else None
    )
    graph = candidate.get("graphDiscovery")
    frontier = graph.get("exactFrontier") if type(graph) is dict else None
    retained_boundary = (
        predecessor.get("retainedSnapshotBoundary")
        if type(predecessor) is dict
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
    check(
        type(source_bindings) is list
        and len(source_bindings) == 229
        and all(
            type(row) is dict
            and set(row) == source_keys
            and row["kind"] in {"root_zip", "mod", "zip"}
            and type(row["module"]) is str
            and type(row["path"]) is str
            and type(row["rawSha256"]) is str
            and len(row["rawSha256"]) == 64
            and all(
                character in "0123456789abcdef"
                for character in row["rawSha256"]
            )
            and type(row["tupleId"]) is str
            and type(row["tupleOrder"]) is int
            and type(row["version"]) is str
            and type(row["wave"]) is str
            for row in source_bindings
        ),
        "E_V6_PREDECESSOR",
    )
    source_pairs: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in source_bindings:
        if row["kind"] != "root_zip":
            source_pairs[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        type(predecessor) is dict
        and predecessor.get("contentSha256")
        == V6_CANDIDATE_CONTENT_SHA256
        and predecessor.get("combinedInputSetSha256")
        == V6_INPUT_SET_SHA256
        and predecessor.get("sourceBindingsSha256")
        == WAVE8_HELD_SOURCE_BINDINGS_SHA256
        and predecessor.get("graphSha256") == V6_GRAPH_SHA256
        and predecessor.get("frontierSha256") == V6_FRONTIER_SHA256
        and predecessor.get("frontierTupleCount") == 14
        and predecessor.get("fixedPointReached") is False
        and predecessor.get("checkerPath") == V6_CHECKER_PATH
        and predecessor.get("checkerRawSha256") == V6_CHECKER_RAW_SHA256
        and predecessor.get("checkerNormalizedSha256")
        == V6_CHECKER_NORMALIZED_SHA256
        and predecessor.get("testsPath") == V6_TESTS_PATH
        and predecessor.get("testsRawSha256") == V6_TESTS_RAW_SHA256
        and predecessor.get("totalFullSourceReconstructionCount") == 10
        and predecessor.get("totalGraphArchiveOpenCount") == 830
        and predecessor.get("trustedPinnedNormalPathFileWriteCount") == 0
        and predecessor.get("osSyscallSandboxProvided") is False
        and predecessor.get("providerFacadeVerificationScope")
        == "trusted_pinned_normal_reconstruction_path"
        and retained_boundary
        == {
            "completionAppliesToRetainedSnapshot": True,
            "currentPathIdentityGuaranteedThroughManifestPublication": False,
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                False,
        }
        and type(binding) is dict
        and binding
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "candidate_without_contentBinding",
            "sha256": V6_CANDIDATE_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == V6_CANDIDATE_CONTENT_SHA256
        and candidate.get("schemaVersion") == "6.0"
        and candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
            "wave5-wave6-wave7-fixed-point-candidate"
        )
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and candidate.get("result")
        == (
            "combined_graph_recomputed_twice_from_exact_"
            "wave1_through_wave7_source_bytes"
        )
        and candidate.get("route") == "next_wave_required"
        and candidate.get("nextAction")
        == (
            "prepare_separate_versioned_dependency_wave_identity_and_"
            "acquisition_decision"
        )
        and candidate.get("derivedResult")
        == {
            "fixedPointReached": False,
            "frontierTupleCount": 14,
            "frontierSha256": V6_FRONTIER_SHA256,
        }
        and type(inputs) is dict
        and inputs.get("heldSourceInputCount") == 229
        and inputs.get("combinedInputSetSha256") == V6_INPUT_SET_SHA256
        and sha256_bytes(runner.canonical_json_bytes(source_bindings))
        == V6_INPUT_SET_SHA256
        and sha256_bytes(wave8_digest_bytes(source_bindings))
        == WAVE8_HELD_SOURCE_BINDINGS_SHA256
        and len({row["path"] for row in source_bindings}) == 229
        and sum(row["kind"] == "root_zip" for row in source_bindings) == 1
        and sum(row["kind"] == "mod" for row in source_bindings) == 114
        and sum(row["kind"] == "zip" for row in source_bindings) == 114
        and sum(row["wave"] == "wave1" for row in source_bindings) == 38
        and sum(row["wave"] == "wave2" for row in source_bindings) == 30
        and sum(row["wave"] == "wave3" for row in source_bindings) == 32
        and sum(row["wave"] == "wave4" for row in source_bindings) == 32
        and sum(row["wave"] == "wave5" for row in source_bindings) == 30
        and sum(row["wave"] == "wave6" for row in source_bindings) == 36
        and sum(row["wave"] == "wave7" for row in source_bindings) == 30
        and len(source_pairs) == 114
        and all(kinds == {"mod", "zip"} for kinds in source_pairs.values())
        and sorted(order for _, _, order in source_pairs)
        == list(range(1, 115))
        and type(graph) is dict
        and graph.get("fixedPointReached") is False
        and graph.get("newTupleCount") == 14
        and graph.get("graphSha256") == V6_GRAPH_SHA256
        and type(frontier) is list
        and len(frontier) == 14
        and sha256_bytes(runner.canonical_json_bytes(frontier))
        == V6_FRONTIER_SHA256
        and candidate.get("authority") == V6_AUTHORITY,
        "E_V6_PREDECESSOR",
    )
    return {
        "checkerExecutedFromPinnedBytes": True,
        "candidateContentSha256": binding["sha256"],
        "combinedInputSetSha256": inputs["combinedInputSetSha256"],
        "graphSha256": graph["graphSha256"],
        "frontierSha256": sha256_bytes(
            runner.canonical_json_bytes(frontier)
        ),
        "fixedPointReached": graph["fixedPointReached"],
        "frontierTupleCount": len(frontier),
        "wave7CompletionAppliesToRetainedSnapshot": True,
        "wave7CurrentPathIdentityGuaranteedThroughManifestPublication": False,
        "wave7SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
            False,
    }


def wave8_request_resources(
    v4: types.ModuleType,
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    decision = documents[WAVE8_DECISION_PATH]
    permit = documents[WAVE8_PERMIT_PATH]
    receipt = documents[WAVE8_RECEIPT_PATH]
    manifest = documents[WAVE8_MANIFEST_PATH]
    readback_permit = documents[WAVE8_READBACK_PERMIT_PATH]
    readback = documents[WAVE8_READBACK_PATH]
    readback_manifest = documents[WAVE8_READBACK_MANIFEST_PATH]
    verify_wave8_content_bindings(v4, runner, documents)

    resolution = decision.get("identityResolution")
    held_set = decision.get("heldSourceInputSet")
    preparation = decision.get("sourceAcquisitionPreparation")
    identity_tuples = (
        resolution.get("tuples") if type(resolution) is dict else None
    )
    source_requests = (
        preparation.get("requestSet") if type(preparation) is dict else None
    )
    check(
        exact_keys(
            decision,
            (
                "authority", "checkerId", "closure", "contentBinding",
                "date", "decisionId", "documentType",
                "heldSourceInputSet", "identityResolution", "nextAction",
                "nonClaims", "operationCounters", "predecessorBindings",
                "readerDocumentBinding", "recordModeExposed", "result",
                "schemaVersion", "sourceAcquisitionPreparation", "status",
                "toolBindings", "verificationOnly",
            ),
        )
        and exact_keys(
            resolution,
            (
                "blockedTupleCount", "compactIdentityCanonicalization",
                "compactIdentitySha256", "completeIdentityPairCount",
                "conflictingIdentityCount", "fullWitnessCanonicalization",
                "fullWitnessMaterializedInDecision",
                "fullWitnessReproducibleByPinnedChecker",
                "fullWitnessSha256", "goModH1WitnessCount",
                "graphSelectedTupleCount", "moduleZipH1WitnessCount",
                "parentDeclarationCount", "tupleCount", "tuples",
                "versionSpecificNonSelectedTupleCount",
            ),
        )
        and exact_keys(
            held_set,
            (
                "allInputsHeldThroughFinalBarrier",
                "allInputsReadTwiceBeforeUse", "archiveCount",
                "embeddedRootGoModCount", "externalModCount",
                "goSumEntryCount",
                "sourceBindingCount", "sourceBindingsSha256",
            ),
        )
        and exact_keys(
            preparation,
            (
                "acceptedDirectoryPath",
                "acquisitionAuthorizedByThisDecision",
                "acquisitionReady", "atomicNoReplacePromotionRequired",
                "claimPath", "independentPostConsumptionReadbackRequired",
                "modulePathEncoding", "oneUseNoOverwriteRequired",
                "proxyHost", "requestCount", "requestOrder", "requestSet",
                "requestSetCanonicalSha256",
                "separateOneUseExecutionPermitRequired",
                "stagingDirectoryPrefix",
            ),
        ),
        "E_WAVE8_DECISION",
    )
    check(
        decision.get("contentBinding")
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "decision_without_contentBinding",
            "sha256": WAVE8_CONTENT_SHA256[WAVE8_DECISION_PATH],
        }
        and decision.get("status")
        == (
            "wave8_exact_14_frontier_identity_classified_14_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and type(resolution) is dict
        and resolution.get("tupleCount") == 14
        and resolution.get("completeIdentityPairCount") == 14
        and resolution.get("blockedTupleCount") == 0
        and resolution.get("graphSelectedTupleCount") == 0
        and resolution.get("versionSpecificNonSelectedTupleCount") == 14
        and resolution.get("compactIdentitySha256")
        == WAVE8_COMPACT_IDENTITY_SHA256
        and resolution.get("fullWitnessSha256")
        == WAVE8_FULL_WITNESS_SHA256
        and type(held_set) is dict
        and held_set.get("sourceBindingCount") == 229
        and held_set.get("sourceBindingsSha256")
        == WAVE8_HELD_SOURCE_BINDINGS_SHA256
        and type(preparation) is dict
        and preparation.get("acquisitionReady") is True
        and preparation.get("acquisitionAuthorizedByThisDecision") is False
        and preparation.get("requestCount") == 28
        and preparation.get("requestOrder")
        == "tuple_order_ascending_mod_then_zip"
        and preparation.get("acceptedDirectoryPath")
        == WAVE8_ACCEPTED_DIRECTORY
        and preparation.get("requestSetCanonicalSha256")
        == WAVE8_REQUEST_SET_SHA256
        and type(identity_tuples) is list
        and len(identity_tuples) == 14
        and type(source_requests) is list
        and len(source_requests) == 28
        and sha256_bytes(wave8_digest_bytes(source_requests))
        == WAVE8_REQUEST_SET_SHA256,
        "E_WAVE8_DECISION",
    )

    contract = permit.get("requestContract")
    resources = contract.get("resources") if type(contract) is dict else None
    permit_decision_binding = permit.get("decisionBinding")
    permit_identity_binding = permit.get("identityBinding")
    permit_predecessor = permit.get("predecessorBindings", {}).get(
        "combinedFixedPointV6"
    )
    check(
        exact_keys(
            permit,
            (
                "absoluteResourceLimits", "authority", "contentBinding",
                "decisionBinding", "documentType", "filesystemAuthority",
                "identityBinding", "invocationContract", "nextAction",
                "nonClaims",
                "oneUseContract", "permitId", "predecessorBindings",
                "primitiveBindings",
                "readerDocumentBinding", "recordedDate", "requestContract",
                "result", "runnerNormalizedSha256", "schemaVersion",
                "status", "terminalContract", "toolBindings",
                "verificationContract", "zipLimits",
            ),
        )
        and exact_keys(
            permit_decision_binding,
            (
                "contentSha256", "files", "path", "rawSha256",
                "requiredStatus",
            ),
        )
        and exact_keys(
            permit_identity_binding,
            (
                "blockedTupleCount", "compactIdentitySha256",
                "completeTupleCount", "fullWitnessSha256",
                "heldSourceBindingsSha256",
            ),
        )
        and exact_keys(
            contract,
            (
                "acceptedStatusCode", "alternateHostAllowed",
                "ambientProxyAllowed", "authenticationAllowed",
                "authorizationHeaderAllowed", "clientCertificateAllowed",
                "cookieAllowed", "directHttpsOnly", "host",
                "identityContentEncodingRequired", "method", "order",
                "port", "proxyAuthorizationHeaderAllowed",
                "queryOrFragmentAllowed", "rangeHeaderAllowed",
                "redirectAllowed", "requestBodyAllowed", "requestCount",
                "resources", "resourcesCanonicalSha256",
                "retryResumeOrBackfillAllowed",
                "sourceRequestSetCanonicalSha256",
                "tlsCertificateAndHostnameValidationRequired",
                "tupleCount",
            ),
        ),
        "E_WAVE8_PERMIT",
    )
    check(
        permit.get("contentBinding")
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "permit_without_contentBinding",
            "sha256": WAVE8_CONTENT_SHA256[WAVE8_PERMIT_PATH],
        }
        and permit.get("status") == "authorized_not_consumed"
        and permit.get("authority") == WAVE8_ACQUISITION_AUTHORITY
        and permit.get("decisionBinding", {}).get("rawSha256")
        == WAVE8_CONTROL_SHA256[WAVE8_DECISION_PATH]
        and permit.get("decisionBinding", {}).get("contentSha256")
        == WAVE8_CONTENT_SHA256[WAVE8_DECISION_PATH]
        and permit.get("identityBinding", {}).get("compactIdentitySha256")
        == WAVE8_COMPACT_IDENTITY_SHA256
        and permit.get("identityBinding", {}).get("fullWitnessSha256")
        == WAVE8_FULL_WITNESS_SHA256
        and permit.get("identityBinding", {}).get(
            "heldSourceBindingsSha256"
        )
        == WAVE8_HELD_SOURCE_BINDINGS_SHA256
        and permit_predecessor
        == {
            "checkerNormalizedSha256": V6_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V6_CHECKER_PATH,
            "checkerRawSha256": V6_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V6_INPUT_SET_SHA256,
            "contentSha256": V6_CANDIDATE_CONTENT_SHA256,
            "frontierSha256": V6_FRONTIER_SHA256,
            "graphSha256": V6_GRAPH_SHA256,
            "sourceBindingsSha256": WAVE8_HELD_SOURCE_BINDINGS_SHA256,
            "testsPath": V6_TESTS_PATH,
            "testsRawSha256": V6_TESTS_RAW_SHA256,
        }
        and type(contract) is dict
        and contract.get("requestCount") == 28
        and contract.get("tupleCount") == 14
        and contract.get("order") == "tuple_order_ascending_mod_then_zip"
        and contract.get("sourceRequestSetCanonicalSha256")
        == WAVE8_REQUEST_SET_SHA256
        and contract.get("resourcesCanonicalSha256")
        == WAVE8_PERMIT_RESOURCES_SHA256
        and type(resources) is list
        and len(resources) == 28
        and sha256_bytes(runner.canonical_json_bytes(resources))
        == WAVE8_PERMIT_RESOURCES_SHA256,
        "E_WAVE8_PERMIT",
    )

    check(
        exact_keys(
            receipt,
            (
                "acceptedEvidenceRawSha256", "acceptedPath",
                "acceptedResourceCount",
                "acceptedResourceHashSetCanonicalSha256",
                "additionalCompletionUncertain",
                "aggregateModResponseBytes", "aggregateResponseBytes",
                "aggregateZipEntryCount", "aggregateZipResponseBytes",
                "aggregateZipUncompressedBytes", "attemptId",
                "checkerRawSha256", "claimRawSha256", "compiled",
                "currentOperationPhase", "currentResourceOrdinal",
                "decisionContentSha256", "dispatchBoundaryCount",
                "documentType", "externalAuthenticationRequired",
                "modCount", "operationCountSemantics",
                "permitContentSha256", "persistenceCommittedCount",
                "requestCount", "responseCommittedBytes",
                "responseCommittedCount", "runnerRawSha256",
                "schemaVersion", "sourceAcquired",
                "sourceAcquisitionState", "sourceExtracted",
                "sourceLoadedOrExecuted", "status", "userActionRequired",
                "validationCommittedCount", "zipCount",
            ),
        ),
        "E_WAVE8_RECEIPT",
    )
    check(
        receipt.get("status")
        == "consumed_success_pending_independent_readback"
        and receipt.get("attemptId") == WAVE8_ATTEMPT_ID
        and receipt.get("acceptedPath") == WAVE8_ACCEPTED_DIRECTORY
        and receipt.get("acceptedResourceCount") == 28
        and receipt.get("modCount") == 14
        and receipt.get("zipCount") == 14
        and receipt.get("aggregateResponseBytes") == 35_196_959
        and receipt.get("aggregateModResponseBytes") == 1_730
        and receipt.get("aggregateZipResponseBytes") == 35_195_229
        and receipt.get("aggregateZipEntryCount") == 4_907
        and receipt.get("aggregateZipUncompressedBytes") == 144_867_307
        and receipt.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE8_RESOURCE_SET_SHA256
        and receipt.get("claimRawSha256")
        == WAVE8_ACQUISITION_CLAIM_RAW_SHA256
        and receipt.get("acceptedEvidenceRawSha256")
        == WAVE8_ACQUISITION_EVIDENCE_RAW_SHA256
        and receipt.get("checkerRawSha256")
        == WAVE8_ACQUISITION_CHECKER_RAW_SHA256
        and receipt.get("runnerRawSha256")
        == WAVE8_ACQUISITION_RUNNER_RAW_SHA256
        and receipt.get("decisionContentSha256")
        == WAVE8_CONTENT_SHA256[WAVE8_DECISION_PATH]
        and receipt.get("permitContentSha256")
        == WAVE8_CONTENT_SHA256[WAVE8_PERMIT_PATH]
        and receipt.get("sourceAcquired") is True
        and receipt.get("sourceExtracted") is False
        and receipt.get("sourceLoadedOrExecuted") is False
        and receipt.get("compiled") is False
        and receipt.get("externalAuthenticationRequired") is False
        and receipt.get("userActionRequired") is False,
        "E_WAVE8_RECEIPT",
    )
    check(
        manifest
        == {
            "attemptId": WAVE8_ATTEMPT_ID,
            "documentType": "aetherlink.wave8-source-acquisition-manifest",
            "manifestWrittenLast": True,
            "receiptPath": WAVE8_RECEIPT_PATH,
            "receiptRawSha256": WAVE8_CONTROL_SHA256[WAVE8_RECEIPT_PATH],
            "schemaVersion": "1.0",
            "status": "consumed_success_pending_independent_readback",
        },
        "E_WAVE8_MANIFEST",
    )

    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    verification_contract = readback_permit.get("verificationContract")
    accepted = snapshot.get("acceptedDirectory") if type(snapshot) is dict else None
    accepted_files = accepted.get("files") if type(accepted) is dict else None
    acquisition_authority = (
        snapshot.get("acquisitionAuthority")
        if type(snapshot) is dict
        else None
    )
    acquisition_authority_by_path = {
        row.get("path"): row
        for row in (
            acquisition_authority
            if type(acquisition_authority) is list
            else []
        )
        if type(row) is dict
    }
    acquisition_claim = (
        snapshot.get("acquisitionClaim")
        if type(snapshot) is dict
        else None
    )
    evidence = snapshot.get("evidence") if type(snapshot) is dict else None
    acquisition_receipt = (
        snapshot.get("acquisitionReceipt")
        if type(snapshot) is dict
        else None
    )
    acquisition_manifest = (
        snapshot.get("acquisitionManifest")
        if type(snapshot) is dict
        else None
    )
    identity_bindings = (
        snapshot.get("identityBindings")
        if type(snapshot) is dict
        else None
    )
    snapshot_predecessor = (
        snapshot.get("predecessorBindings", {}).get("combinedFixedPointV6")
        if type(snapshot) is dict
        else None
    )
    final_directory = (
        snapshot.get("finalDirectory")
        if type(snapshot) is dict
        else None
    )
    absence_contract = (
        snapshot.get("absenceContract")
        if type(snapshot) is dict
        else None
    )
    check(
        exact_keys(
            readback_permit,
            (
                "authority", "contentBinding", "documentType",
                "frozenAcquisitionSnapshot", "interpreterContract",
                "nextAction", "nonClaims", "oneUseConsumption",
                "outputContract", "permitId", "readerDocumentBinding",
                "recordedDate", "recorderNormalizedSha256",
                "resourceLimits", "result", "schemaVersion", "status",
                "toolBindings", "verificationContract",
            ),
        )
        and exact_keys(
            snapshot,
            (
                "absenceContract", "acceptedDirectory",
                "acceptedResourceCount",
                "acceptedResourceHashSetCanonicalSha256",
                "acquisitionAuthority", "acquisitionClaim",
                "acquisitionDecisionContentSha256", "acquisitionManifest",
                "acquisitionPermitContentSha256", "acquisitionReceipt",
                "aggregateAcceptedBytes", "aggregateModBytes",
                "aggregateZipBytes", "aggregateZipEntryCount",
                "aggregateZipUncompressedBytes", "attemptId", "evidence",
                "finalDirectory", "frozenFileCount",
                "frozenFilesCanonicalSha256", "identityBindings",
                "modCount", "predecessorBindings",
                "selectedTupleCount", "zipCount",
            ),
        )
        and exact_keys(
            verification_contract,
            (
                "acceptedResourceHashSetCanonicalSha256Recomputed",
                "acquisitionCheckerOrRunnerImportAllowed",
                "acquisitionCheckerOrRunnerInvocationAllowed",
                "allFrozenFilesOpenedNoFollowAndHeld",
                (
                    "allRequiredPreManifestBarriersCompleteImmediatelyBefore"
                    "ManifestPublication"
                ),
                "attemptAndAuthorityBindingsRecomputed",
                "authorityFilesOpenedAndHeldFirst",
                (
                    "claimCreationFdHeldAtImmediatelyBeforeManifestBarrier"
                ),
                "claimDurableBeforeAnyFrozenAcquisitionInputOpen",
                "cleanupClosesEveryOwnedFdBeforeSignalMaskRestore",
                "combinedFixedPointV6PredecessorBindingRecomputed",
                "completeVerificationPassCount",
                "completionAppliesToRetainedSnapshot",
                (
                    "currentPathDeviceAndInodeMustMatchHeldObjectAtEachPre"
                    "ManifestBarrier"
                ),
                (
                    "currentPathIdentityGuaranteedThroughManifest"
                    "Publication"
                ),
                "decisionAndPermitContentBindingsRecomputed",
                "eachPreManifestBarrierReopensEveryCurrentPathNoFollow",
                "exact28ResourceOrderAndAggregateRecomputed",
                "exact46FrozenFileSnapshotRequired",
                "exactFinalAndAcceptedDirectoryInventoriesRequired",
                (
                    "frozenSnapshotHeldFdBytesReverifiedImmediatelyBefore"
                    "ManifestPublication"
                ),
                "goModH1RecomputedIndependently",
                "identityAndSourceRequestSetBindingsRecomputed",
                "intermediateDirectoryComponentsOpenedNoFollowAndHeld",
                "moduleZipH1RecomputedIndependently",
                "openToOwnershipTransferDefersOnlySigalrmAndSigint",
                "pathSha256BytesModeOwnerAndLinkCountRequired",
                "publishedOutputsReopenedAndVerifiedBeforePublishReturns",
                (
                    "readbackClaimCurrentPathIdentityReverifiedImmediately"
                    "BeforeManifestPublication"
                ),
                (
                    "readbackReceiptCurrentPathIdentityReverifiedImmediately"
                    "BeforeManifestPublication"
                ),
                "requestResourcesCanonicalSha256Recomputed",
                "requiredFallibleBarrierAfterManifest",
                "retainedFdPreManifestBarrierCount",
                "retainedFdPreManifestBarriers",
                (
                    "retainedProjectRootCurrentPathIdentityCheckedAtEachPre"
                    "ManifestBarrier"
                ),
                (
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrier"
                    "Prevented"
                ),
                "sourceExtractionAllowed",
                "strictCanonicalTerminalAndEvidenceJsonRequired",
                "zipStructurePathCrcAndModParityRecomputed",
            ),
        ),
        "E_WAVE8_READBACK_PERMIT",
    )
    check(
        readback_permit.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE8_CONTENT_SHA256[WAVE8_READBACK_PERMIT_PATH],
        }
        and readback_permit.get("status") == "authorized_not_consumed"
        and readback_permit.get("authority") == WAVE8_READBACK_AUTHORITY
        and type(verification_contract) is dict
        and verification_contract.get("completeVerificationPassCount") == 2
        and verification_contract.get("allFrozenFilesOpenedNoFollowAndHeld")
        is True
        and verification_contract.get("exact46FrozenFileSnapshotRequired")
        is True
        and verification_contract.get(
            "combinedFixedPointV6PredecessorBindingRecomputed"
        ) is True
        and verification_contract.get(
            "requestResourcesCanonicalSha256Recomputed"
        ) is True
        and verification_contract.get("retainedFdPreManifestBarrierCount")
        == 3
        and verification_contract.get("retainedFdPreManifestBarriers")
        == WAVE8_RETAINED_BARRIERS
        and verification_contract.get("completionAppliesToRetainedSnapshot")
        is True
        and verification_contract.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and verification_contract.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and type(snapshot) is dict
        and snapshot.get("attemptId") == WAVE8_ATTEMPT_ID
        and identity_bindings
        == {
            "compactIdentitySha256": WAVE8_COMPACT_IDENTITY_SHA256,
            "fullWitnessSha256": WAVE8_FULL_WITNESS_SHA256,
            "heldSourceBindingsSha256":
                WAVE8_HELD_SOURCE_BINDINGS_SHA256,
            "resourcesCanonicalSha256":
                WAVE8_PERMIT_RESOURCES_SHA256,
            "sourceRequestSetCanonicalSha256":
                WAVE8_REQUEST_SET_SHA256,
        }
        and snapshot_predecessor
        == {
            "checkerNormalizedSha256": V6_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V6_CHECKER_PATH,
            "checkerRawSha256": V6_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V6_INPUT_SET_SHA256,
            "contentSha256": V6_CANDIDATE_CONTENT_SHA256,
            "frontierSha256": V6_FRONTIER_SHA256,
            "graphSha256": V6_GRAPH_SHA256,
            "sourceBindingsSha256": WAVE8_HELD_SOURCE_BINDINGS_SHA256,
            "testsPath": V6_TESTS_PATH,
            "testsRawSha256": V6_TESTS_RAW_SHA256,
        }
        and snapshot.get("acquisitionDecisionContentSha256")
        == WAVE8_CONTENT_SHA256[WAVE8_DECISION_PATH]
        == decision.get("contentBinding", {}).get("sha256")
        == permit.get("decisionBinding", {}).get("contentSha256")
        == receipt.get("decisionContentSha256")
        and snapshot.get("acquisitionPermitContentSha256")
        == WAVE8_CONTENT_SHA256[WAVE8_PERMIT_PATH]
        == permit.get("contentBinding", {}).get("sha256")
        == receipt.get("permitContentSha256")
        and final_directory
        == {
            "exactEntries": ["accepted", "evidence.json"],
            "linkCount": 4,
            "mode": "0700",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-8-v1"
            ),
        }
        and absence_contract
        == {
            "failureAbsent": True,
            "failurePath": (
                f"{BASE}/bounded-dependency-source-acquisition-wave8-"
                "failure-v1.json"
            ),
            "portableNameComparison": "NFC_casefold",
            "stagingAbsent": True,
            "stagingParent": (
                "build/offline-source/pion-ice-v4.3.0/dependencies"
            ),
            "stagingPrefix": ".wave-8-v1-staging-",
        }
        and snapshot.get("frozenFileCount") == 46
        and snapshot.get("frozenFilesCanonicalSha256")
        == WAVE8_FROZEN_FILE_SET_SHA256
        and snapshot.get("acceptedResourceCount") == 28
        and snapshot.get("selectedTupleCount") == 0
        and snapshot.get("modCount") == 14
        and snapshot.get("zipCount") == 14
        and snapshot.get("aggregateAcceptedBytes") == 35_196_959
        and snapshot.get("aggregateModBytes") == 1_730
        and snapshot.get("aggregateZipBytes") == 35_195_229
        and snapshot.get("aggregateZipEntryCount") == 4_907
        and snapshot.get("aggregateZipUncompressedBytes") == 144_867_307
        and snapshot.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE8_RESOURCE_SET_SHA256
        and type(acquisition_authority) is list
        and len(acquisition_authority) == 14
        and len(acquisition_authority_by_path) == 14
        and acquisition_authority_by_path.get(
            (
                "script/check_p2p_nat_g2_pion_rung3_dependency_wave8_"
                "acquisition_v1.py"
            ),
            {},
        ).get("rawSha256")
        == WAVE8_ACQUISITION_CHECKER_RAW_SHA256
        and acquisition_authority_by_path.get(
            (
                "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave8_"
                "v1_once.py"
            ),
            {},
        ).get("rawSha256")
        == WAVE8_ACQUISITION_RUNNER_RAW_SHA256
        and acquisition_claim
        == {
            "bytes": 416,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-8-v1.claim"
            ),
            "rawSha256": WAVE8_ACQUISITION_CLAIM_RAW_SHA256,
        }
        and evidence
        == {
            "bytes": 11_258,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-8-v1/evidence.json"
            ),
            "rawSha256": WAVE8_ACQUISITION_EVIDENCE_RAW_SHA256,
        }
        and acquisition_receipt
        == {
            "bytes": 1_671,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE8_RECEIPT_PATH,
            "rawSha256": WAVE8_CONTROL_SHA256[WAVE8_RECEIPT_PATH],
        }
        and acquisition_manifest
        == {
            "bytes": 463,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE8_MANIFEST_PATH,
            "rawSha256": WAVE8_CONTROL_SHA256[WAVE8_MANIFEST_PATH],
        }
        and manifest.get("receiptPath") == acquisition_receipt["path"]
        and manifest.get("receiptRawSha256")
        == acquisition_receipt["rawSha256"]
        and type(accepted) is dict
        and accepted.get("path") == WAVE8_ACCEPTED_DIRECTORY
        and accepted.get("mode") == "0700"
        and accepted.get("ownerUid") == os.geteuid()
        and accepted.get("linkCount") == 30
        and accepted.get("exactFileCount") == 28
        and type(accepted_files) is list
        and len(accepted_files) == 28
        and sha256_bytes(
            runner.canonical_json_bytes(
                [
                    *acquisition_authority,
                    acquisition_claim,
                    evidence,
                    *accepted_files,
                    acquisition_receipt,
                    acquisition_manifest,
                ]
            )
        )
        == WAVE8_FROZEN_FILE_SET_SHA256,
        "E_WAVE8_READBACK_PERMIT",
    )

    verified = readback.get("verified")
    verified_resources = (
        verified.get("resources") if type(verified) is dict else None
    )
    check(
        set(readback)
        == {
            "acquisitionAttemptId",
            "allRequiredPreManifestBarriersCompleteAtReceipt",
            "allRequiredPreManifestBarriersRequired",
            "authorityBinding",
            "compiled",
            "completedRetainedFdPreManifestBarrierCountAtReceipt",
            "completionAppliesToRetainedSnapshot",
            "contentBinding",
            "currentPathIdentityGuaranteedThroughManifestPublication",
            "documentType",
            "externalAuthenticationRequired",
            "networkRequestAttemptCount",
            "offline",
            "readbackAttemptId",
            "readbackClaim",
            "remainingRetainedFdPreManifestBarrierCount",
            "requiredRetainedFdPreManifestBarrierCount",
            "retainedFdPreManifestBarriers",
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
            "schemaVersion",
            "sourceAcquisitionCount",
            "sourceExtracted",
            "sourceLoadedOrExecuted",
            "status",
            "userActionRequired",
            "verificationPassCount",
            "verified",
        }
        and type(verified) is dict
        and set(verified)
        == {
            "acceptedResourceCount",
            "acceptedResourceHashSetCanonicalSha256",
            "acquisitionAttemptId",
            "acquisitionClaimRawSha256",
            "acquisitionManifestRawSha256",
            "acquisitionReceiptRawSha256",
            "aggregateAcceptedBytes",
            "aggregateModBytes",
            "aggregateZipBytes",
            "aggregateZipEntryCount",
            "aggregateZipUncompressedBytes",
            "authorityFileCount",
            "combinedFixedPointV6ContentSha256",
            "compactIdentitySha256",
            "compiled",
            "decisionContentSha256",
            "evidenceRawSha256",
            "externalAuthenticationRequired",
            "failureAbsent",
            "fullWitnessSha256",
            "heldSourceBindingsSha256",
            "modCount",
            "permitContentSha256",
            "resources",
            "resourcesCanonicalSha256",
            "selectedTupleCount",
            "sourceExtracted",
            "sourceLoadedOrExecuted",
            "sourceRequestSetCanonicalSha256",
            "stagingAbsent",
            "status",
            "userActionRequired",
            "zipCount",
        },
        "E_WAVE8_READBACK",
    )
    check(
        readback.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE8_CONTENT_SHA256[WAVE8_READBACK_PATH],
        }
        and readback.get("status")
        == "wave8_acquisition_retained_snapshot_independently_read_back"
        and readback.get("acquisitionAttemptId") == WAVE8_ATTEMPT_ID
        and readback.get("readbackAttemptId") == WAVE8_READBACK_ATTEMPT_ID
        and readback.get("authorityBinding")
        == WAVE8_READBACK_AUTHORITY_BINDING
        and readback.get("verificationPassCount") == 2
        and readback.get("offline") is True
        and readback.get("networkRequestAttemptCount") == 0
        and readback.get("sourceAcquisitionCount") == 0
        and readback.get("sourceExtracted") is False
        and readback.get("sourceLoadedOrExecuted") is False
        and readback.get("compiled") is False
        and readback.get("externalAuthenticationRequired") is False
        and readback.get("userActionRequired") is False
        and readback.get("readbackClaim")
        == {
            "bytes": 1_251,
            "contentSha256": WAVE8_READBACK_CLAIM_CONTENT_SHA256,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-8-v1-readback.claim"
            ),
            "rawSha256": WAVE8_READBACK_CLAIM_RAW_SHA256,
        }
        and readback.get("allRequiredPreManifestBarriersRequired") is True
        and readback.get("allRequiredPreManifestBarriersCompleteAtReceipt")
        is False
        and readback.get("requiredRetainedFdPreManifestBarrierCount") == 3
        and readback.get(
            "completedRetainedFdPreManifestBarrierCountAtReceipt"
        ) == 1
        and readback.get("remainingRetainedFdPreManifestBarrierCount") == 2
        and readback.get("retainedFdPreManifestBarriers")
        == WAVE8_RETAINED_BARRIERS
        and readback.get("completionAppliesToRetainedSnapshot") is True
        and readback.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and readback.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and type(verified) is dict
        and verified.get("status")
        == "wave8_acquisition_retained_snapshot_independently_verified"
        and verified.get("acquisitionAttemptId")
        == snapshot.get("attemptId")
        == receipt.get("attemptId")
        == manifest.get("attemptId")
        and verified.get("authorityFileCount")
        == len(acquisition_authority)
        and verified.get("acceptedResourceCount") == 28
        == snapshot.get("acceptedResourceCount")
        == receipt.get("acceptedResourceCount")
        and verified.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE8_RESOURCE_SET_SHA256
        == snapshot.get("acceptedResourceHashSetCanonicalSha256")
        == receipt.get("acceptedResourceHashSetCanonicalSha256")
        and verified.get("selectedTupleCount") == 0
        == snapshot.get("selectedTupleCount")
        and verified.get("modCount")
        == snapshot.get("modCount")
        == receipt.get("modCount")
        == 14
        and verified.get("zipCount")
        == snapshot.get("zipCount")
        == receipt.get("zipCount")
        == 14
        and verified.get("aggregateAcceptedBytes")
        == snapshot.get("aggregateAcceptedBytes")
        == receipt.get("aggregateResponseBytes")
        == 35_196_959
        and verified.get("aggregateModBytes")
        == snapshot.get("aggregateModBytes")
        == receipt.get("aggregateModResponseBytes")
        == 1_730
        and verified.get("aggregateZipBytes")
        == snapshot.get("aggregateZipBytes")
        == receipt.get("aggregateZipResponseBytes")
        == 35_195_229
        and verified.get("aggregateZipEntryCount")
        == snapshot.get("aggregateZipEntryCount")
        == receipt.get("aggregateZipEntryCount")
        == 4_907
        and verified.get("aggregateZipUncompressedBytes")
        == snapshot.get("aggregateZipUncompressedBytes")
        == receipt.get("aggregateZipUncompressedBytes")
        == 144_867_307
        and verified.get("combinedFixedPointV6ContentSha256")
        == V6_CANDIDATE_CONTENT_SHA256
        and verified.get("resourcesCanonicalSha256")
        == identity_bindings["resourcesCanonicalSha256"]
        == contract.get("resourcesCanonicalSha256")
        == WAVE8_PERMIT_RESOURCES_SHA256
        and verified.get("decisionContentSha256")
        == snapshot.get("acquisitionDecisionContentSha256")
        == receipt.get("decisionContentSha256")
        == WAVE8_CONTENT_SHA256[WAVE8_DECISION_PATH]
        and verified.get("permitContentSha256")
        == snapshot.get("acquisitionPermitContentSha256")
        == receipt.get("permitContentSha256")
        == WAVE8_CONTENT_SHA256[WAVE8_PERMIT_PATH]
        and verified.get("sourceRequestSetCanonicalSha256")
        == identity_bindings["sourceRequestSetCanonicalSha256"]
        == contract.get("sourceRequestSetCanonicalSha256")
        == WAVE8_REQUEST_SET_SHA256
        and verified.get("compactIdentitySha256")
        == identity_bindings["compactIdentitySha256"]
        == resolution.get("compactIdentitySha256")
        == WAVE8_COMPACT_IDENTITY_SHA256
        and verified.get("fullWitnessSha256")
        == identity_bindings["fullWitnessSha256"]
        == resolution.get("fullWitnessSha256")
        == WAVE8_FULL_WITNESS_SHA256
        and verified.get("heldSourceBindingsSha256")
        == identity_bindings["heldSourceBindingsSha256"]
        == held_set.get("sourceBindingsSha256")
        == WAVE8_HELD_SOURCE_BINDINGS_SHA256
        and verified.get("acquisitionClaimRawSha256")
        == acquisition_claim["rawSha256"]
        == receipt.get("claimRawSha256")
        and verified.get("evidenceRawSha256")
        == evidence["rawSha256"]
        == receipt.get("acceptedEvidenceRawSha256")
        and verified.get("acquisitionReceiptRawSha256")
        == acquisition_receipt["rawSha256"]
        == manifest.get("receiptRawSha256")
        and verified.get("acquisitionManifestRawSha256")
        == acquisition_manifest["rawSha256"]
        and verified.get("failureAbsent")
        is absence_contract["failureAbsent"]
        is True
        and verified.get("stagingAbsent")
        is absence_contract["stagingAbsent"]
        is True
        and verified.get("sourceExtracted")
        is receipt.get("sourceExtracted")
        is readback.get("sourceExtracted")
        is False
        and verified.get("sourceLoadedOrExecuted")
        is receipt.get("sourceLoadedOrExecuted")
        is readback.get("sourceLoadedOrExecuted")
        is False
        and verified.get("compiled")
        is receipt.get("compiled")
        is readback.get("compiled")
        is False
        and verified.get("externalAuthenticationRequired")
        is receipt.get("externalAuthenticationRequired")
        is readback.get("externalAuthenticationRequired")
        is False
        and verified.get("userActionRequired")
        is receipt.get("userActionRequired")
        is readback.get("userActionRequired")
        is False
        and type(verified_resources) is list
        and len(verified_resources) == 28,
        "E_WAVE8_READBACK",
    )
    check(
        set(readback_manifest)
        == {
            "acquisitionAttemptId",
            "allRequiredPreManifestBarriersCompleted",
            "authorityBinding",
            "completedPreManifestCurrentPathIdentityBarrierCount",
            "completionAppliesToRetainedSnapshot",
            "contentBinding",
            "currentPathIdentityGuaranteedThroughManifestPublication",
            "documentType",
            "externalAuthenticationRequired",
            "lastCurrentPathIdentityBarrierTiming",
            "manifestWrittenLast",
            "networkRequestAttemptCount",
            "offline",
            "readbackAttemptId",
            "receipt",
            "retainedFdPreManifestBarriers",
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
            "schemaVersion",
            "sourceAcquisitionCount",
            "status",
            "userActionRequired",
        },
        "E_WAVE8_READBACK_MANIFEST",
    )
    check(
        readback_manifest.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE8_CONTENT_SHA256[
                WAVE8_READBACK_MANIFEST_PATH
            ],
        }
        and readback_manifest.get("status")
        == "wave8_acquisition_retained_snapshot_readback_publication_complete"
        and readback_manifest.get("acquisitionAttemptId") == WAVE8_ATTEMPT_ID
        and readback_manifest.get("readbackAttemptId")
        == WAVE8_READBACK_ATTEMPT_ID
        and readback_manifest.get("authorityBinding")
        == WAVE8_READBACK_AUTHORITY_BINDING
        and readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("allRequiredPreManifestBarriersCompleted")
        is True
        and readback_manifest.get(
            "completedPreManifestCurrentPathIdentityBarrierCount"
        ) == 3
        and readback_manifest.get("lastCurrentPathIdentityBarrierTiming")
        == "immediately_before_manifest_publication"
        and readback_manifest.get("retainedFdPreManifestBarriers")
        == WAVE8_RETAINED_BARRIERS
        and readback_manifest.get("completionAppliesToRetainedSnapshot")
        is True
        and readback_manifest.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and readback_manifest.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and readback_manifest.get("receipt")
        == {
            "bytes": 15_104,
            "contentSha256": WAVE8_CONTENT_SHA256[WAVE8_READBACK_PATH],
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE8_READBACK_PATH,
            "rawSha256": WAVE8_CONTROL_SHA256[WAVE8_READBACK_PATH],
        }
        and readback_manifest.get("offline") is True
        and readback_manifest.get("networkRequestAttemptCount") == 0
        and readback_manifest.get("sourceAcquisitionCount") == 0
        and readback_manifest.get("externalAuthenticationRequired") is False
        and readback_manifest.get("userActionRequired") is False,
        "E_WAVE8_READBACK_MANIFEST",
    )

    accepted_by_name = {
        Path(row["path"]).name: row
        for row in accepted_files
        if type(row) is dict and type(row.get("path")) is str
    }
    verified_by_name = {
        row.get("acceptedFileName"): row
        for row in verified_resources
        if type(row) is dict
    }
    identity_by_order = {
        row.get("tupleOrder"): row
        for row in identity_tuples
        if type(row) is dict
    }
    check(
        len(accepted_by_name) == 28
        and len(verified_by_name) == 28
        and len(identity_by_order) == 14,
        "E_WAVE8_RESOURCE",
    )
    result: list[dict[str, Any]] = []
    tuple_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    totals = {"all": 0, "mod": 0, "zip": 0, "entries": 0, "expanded": 0}
    accepted_hash_projection: list[dict[str, Any]] = []
    for index, value in enumerate(resources, start=1):
        source_value = source_requests[index - 1]
        expected_kind = "mod" if index % 2 else "zip"
        tuple_order = (index + 1) // 2
        identity_tuple = identity_by_order.get(tuple_order)
        digest = sha256_bytes(
            f"{value.get('module')}\n{value.get('version')}\n".encode()
        )
        check(
            type(value) is dict
            and value.get("requestOrdinal") == index
            and value.get("tupleOrder") == tuple_order
            and value.get("kind") == expected_kind
            and value.get("selectedByGraphAlgorithm") is False
            and value.get("tupleDigestSha256") == digest
            and value.get("tupleId")
            == f"wave8-{tuple_order:03}-{digest[:12]}"
            and value.get("acceptedFileName")
            == f"{tuple_order:03}-{digest[:20]}.{expected_kind}"
            and type(source_value) is dict
            and source_value.get("requestOrdinal") == index
            and source_value.get("tupleOrder") == tuple_order
            and source_value.get("resourceKind") == expected_kind
            and source_value.get("module") == value.get("module")
            and source_value.get("version") == value.get("version")
            and source_value.get("url") == value.get("url")
            and source_value.get("expectedH1") == value.get("expectedH1")
            and source_value.get("selectedByGraphAlgorithm") is False
            and type(identity_tuple) is dict
            and identity_tuple.get("module") == value.get("module")
            and identity_tuple.get("version") == value.get("version")
            and (
                identity_tuple.get("goModH1")
                if expected_kind == "mod"
                else identity_tuple.get("moduleZipH1")
            )
            == value.get("expectedH1")
            and identity_tuple.get("selectedByGraphAlgorithm") is False,
            "E_WAVE8_RESOURCE",
        )
        name = value["acceptedFileName"]
        accepted_row = accepted_by_name.get(name)
        verified_row = verified_by_name.get(name)
        check(
            type(accepted_row) is dict
            and set(accepted_row)
            == {
                "bytes",
                "linkCount",
                "mode",
                "ownerUid",
                "path",
                "rawSha256",
            }
            and accepted_row.get("path")
            == f"{WAVE8_ACCEPTED_DIRECTORY}/{name}"
            and accepted_row.get("mode") == "0600"
            and accepted_row.get("ownerUid") == os.geteuid()
            and accepted_row.get("linkCount") == 1
            and type(accepted_row.get("bytes")) is int
            and accepted_row["bytes"] > 0
            and type(verified_row) is dict
            and set(verified_row)
            == (
                {
                    "acceptedFileName",
                    "byteCount",
                    "entryCount",
                    "kind",
                    "rawSha256",
                    "requestOrdinal",
                    "rootGoModPresent",
                    "tupleId",
                    "uncompressedBytes",
                    "url",
                    "verifiedH1",
                }
                if expected_kind == "zip"
                else {
                    "acceptedFileName",
                    "byteCount",
                    "kind",
                    "rawSha256",
                    "requestOrdinal",
                    "tupleId",
                    "url",
                    "verifiedH1",
                }
            )
            and verified_row.get("acceptedFileName") == name
            and verified_row.get("requestOrdinal") == index
            and verified_row.get("tupleId") == value.get("tupleId")
            and verified_row.get("kind") == expected_kind
            and verified_row.get("url") == value.get("url")
            and verified_row.get("verifiedH1") == value.get("expectedH1")
            and verified_row.get("byteCount") == accepted_row["bytes"]
            and verified_row.get("rawSha256")
            == accepted_row.get("rawSha256"),
            "E_WAVE8_RESOURCE",
        )
        accepted_hash_projection.append(
            {
                "requestOrdinal": index,
                "acceptedFileName": name,
                "rawSha256": accepted_row["rawSha256"],
                "verifiedH1": verified_row["verifiedH1"],
            }
        )
        totals["all"] += accepted_row["bytes"]
        totals[expected_kind] += accepted_row["bytes"]
        if expected_kind == "zip":
            check(
                type(verified_row.get("entryCount")) is int
                and verified_row["entryCount"] > 0
                and verified_row.get("rootGoModPresent")
                is (tuple_order > 2)
                and type(verified_row.get("uncompressedBytes")) is int
                and verified_row["uncompressedBytes"] > 0,
                "E_WAVE8_RESOURCE",
            )
            totals["entries"] += verified_row.get("entryCount", -1)
            totals["expanded"] += verified_row.get("uncompressedBytes", -1)
        row = {
            "wave": "wave8",
            "path": accepted_row["path"],
            "rawSha256": accepted_row["rawSha256"],
            "maximumBytes": accepted_row["bytes"],
            "ownerOnly": True,
            "kind": expected_kind,
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 114 + tuple_order,
            "order": index,
        }
        if expected_kind == "zip":
            row["modulePrefix"] = (
                f"{runner.go_proxy_escape(value['module'])}@"
                f"{runner.go_proxy_escape(value['version'])}/"
            )
        tuple_rows[value["tupleId"]].append(row)
        result.append(row)
    check(
        len(tuple_rows) == 14
        and all(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len({(row["module"], row["version"]) for row in rows}) == 1
            for rows in tuple_rows.values()
        )
        and totals
        == {
            "all": 35_196_959,
            "mod": 1_730,
            "zip": 35_195_229,
            "entries": 4_907,
            "expanded": 144_867_307,
        }
        and sha256_bytes(
            runner.canonical_json_bytes(accepted_hash_projection)
        )
        == WAVE8_RESOURCE_SET_SHA256,
        "E_WAVE8_AGGREGATE",
    )
    return result


def combined_source_bindings(
    v6: types.ModuleType,
    v5: types.ModuleType,
    v4: types.ModuleType,
    v1: types.ModuleType,
    runner: types.ModuleType,
    v1_documents: Mapping[str, Mapping[str, Any]],
    wave3_documents: Mapping[str, Mapping[str, Any]],
    wave4_documents: Mapping[str, Mapping[str, Any]],
    wave5_documents: Mapping[str, Mapping[str, Any]],
    wave6_documents: Mapping[str, Mapping[str, Any]],
    wave7_documents: Mapping[str, Mapping[str, Any]],
    wave8_documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    bindings = v6.combined_source_bindings(
        v5,
        v4,
        v1,
        runner,
        v1_documents,
        wave3_documents,
        wave4_documents,
        wave5_documents,
        wave6_documents,
        wave7_documents,
    )
    bindings.extend(wave8_request_resources(v4, runner, wave8_documents))
    check(
        len(bindings) == 257
        and sum(row["kind"] == "root_zip" for row in bindings) == 1
        and sum(row["kind"] == "mod" for row in bindings) == 128
        and sum(row["kind"] == "zip" for row in bindings) == 128
        and sum(row["wave"] == "wave1" for row in bindings) == 38
        and sum(row["wave"] == "wave2" for row in bindings) == 30
        and sum(row["wave"] == "wave3" for row in bindings) == 32
        and sum(row["wave"] == "wave4" for row in bindings) == 32
        and sum(row["wave"] == "wave5" for row in bindings) == 30
        and sum(row["wave"] == "wave6" for row in bindings) == 36
        and sum(row["wave"] == "wave7" for row in bindings) == 30
        and sum(row["wave"] == "wave8" for row in bindings) == 28,
        "E_COMBINED_INPUT",
    )
    check(
        len({row["path"] for row in bindings}) == 257
        and len(
            {
                (row["module"], row["version"])
                for row in bindings
                if row["kind"] != "root_zip"
            }
        )
        == 128,
        "E_COMBINED_INPUT",
    )
    pair_kinds: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in bindings:
        if row["kind"] != "root_zip":
            pair_kinds[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        len(pair_kinds) == 128
        and all(kinds == {"mod", "zip"} for kinds in pair_kinds.values())
        and sorted(order for _, _, order in pair_kinds) == list(range(1, 129)),
        "E_COMBINED_INPUT",
    )
    return bindings


def derive_and_validate_graph_result(
    runner: types.ModuleType,
    graph: Mapping[str, Any],
    route: Mapping[str, Any],
) -> dict[str, Any]:
    frontier = graph.get("exactFrontier")
    new_tuple_count = graph.get("newTupleCount")
    unmapped_count = graph.get("unmappedExternalImportCount")
    unresolved_count = graph.get(
        "unresolvedDeclaredExternalImportCount"
    )
    fixed_point = graph.get("fixedPointReached")
    check(
        type(frontier) is list
        and type(new_tuple_count) is int
        and not isinstance(new_tuple_count, bool)
        and new_tuple_count >= 0
        and type(unmapped_count) is int
        and not isinstance(unmapped_count, bool)
        and unmapped_count >= 0
        and type(unresolved_count) is int
        and not isinstance(unresolved_count, bool)
        and unresolved_count >= 0
        and type(fixed_point) is bool
        and new_tuple_count == len(frontier),
        "E_DERIVED_RESULT",
    )
    logically_fixed = (
        len(frontier) == 0
        and unmapped_count == 0
        and unresolved_count == 0
    )
    if new_tuple_count > 0:
        expected_route = {
            "route": "next_wave_required",
            "status": "combined_graph_discovery_complete_next_wave_required",
            "nextAction": (
                "prepare_separate_versioned_dependency_wave_identity_and_"
                "acquisition_decision"
            ),
        }
    elif unmapped_count > 0 or unresolved_count > 0:
        expected_route = {
            "route": "external_import_resolution_required",
            "status": (
                "combined_graph_discovery_complete_external_import_"
                "resolution_required"
            ),
            "nextAction": (
                "prepare_separate_external_import_resolution_decision"
            ),
        }
    else:
        expected_route = {
            "route": "fixed_point_candidate",
            "status": (
                "combined_graph_discovery_complete_fixed_point_candidate"
            ),
            "nextAction": (
                "prepare_separate_combined_fixed_point_closure_review_"
                "decision"
            ),
        }
    check(
        fixed_point is logically_fixed
        and type(route) is dict
        and route == expected_route,
        "E_DERIVED_RESULT",
    )
    return {
        "fixedPointReached": fixed_point,
        "frontierTupleCount": len(frontier),
        "frontierSha256": sha256_bytes(
            runner.canonical_json_bytes(frontier)
        ),
    }


def generate_candidate(root: Path = ROOT) -> dict[str, Any]:
    global PROVIDER_FACADE_LOAD_COUNT
    require_isolated_interpreter()
    HARDENED_CHECKER_PATHS.clear()
    PROVIDER_FACADE_LOAD_COUNT = 0
    with (
        PinnedCodeFile(
            root,
            SELF_PATH,
            SELF_NORMALIZED_SHA256,
            normalized_self_bytes,
        ) as self_held,
        PinnedCodeFile(
            root,
            V6_CHECKER_PATH,
            V6_CHECKER_RAW_SHA256,
        ) as v6_held,
        PinnedCodeFile(
            root,
            V5_CHECKER_PATH,
            V5_CHECKER_RAW_SHA256,
        ) as v5_held,
        PinnedCodeFile(
            root,
            V4_CHECKER_PATH,
            V4_CHECKER_RAW_SHA256,
        ) as v4_held,
    ):
        v6 = load_v6_checker(v6_held)
        predecessor_candidate = v6.generate_candidate(root)
        v6 = harden_checker_module(v6)
        v5 = v6.load_v5_checker(v5_held)
        v4 = v5.load_v4_checker(v4_held)
        with v4.PinnedCodeFile(
            root,
            v4.V1_CHECKER_PATH,
            v4.V1_CHECKER_RAW_SHA256,
        ) as v1_held:
            v1 = v4.load_v1_checker(v1_held)
            with v1.PinnedRunnerFile(root) as provider_held:
                runner = v1.load_pinned_runner(provider_held)
                expected_direct_hardened_paths = {
                    str(root / path)
                    for path in (
                        V6_CHECKER_PATH,
                        V5_CHECKER_PATH,
                        V4_CHECKER_PATH,
                        v4.V1_CHECKER_PATH,
                    )
                }
                check(
                    v6.PinnedCodeFile is PinnedCodeFile
                    and v5.PinnedCodeFile is PinnedCodeFile
                    and v4.PinnedCodeFile is PinnedCodeFile
                    and v1.PinnedRunnerFile is SafePinnedRunnerFile
                    and type(runner) is ReadOnlyProviderFacade
                    and HARDENED_CHECKER_PATHS
                    == expected_direct_hardened_paths
                    and predecessor_candidate["checkerVerification"][
                        "hardenedCheckerModuleCount"
                    ] == 5
                    and predecessor_candidate["checkerVerification"][
                        "providerFacadeLoadCount"
                    ] == 5
                    and PROVIDER_FACADE_LOAD_COUNT == 1,
                    "E_CHECKER_HARDENING",
                )
                controls = (
                    v1.control_bindings()
                    + v4.wave3_control_bindings()
                    + v4.wave4_control_bindings()
                    + v4.wave5_control_bindings()
                    + v5.wave6_control_bindings()
                    + v6.wave7_control_bindings()
                    + wave8_control_bindings()
                )
                auxiliary_evidence = wave8_auxiliary_evidence_bindings()
                with runner.HeldInputSet(
                    root,
                    controls + auxiliary_evidence,
                ) as control_held:
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
                    wave7_documents = v6.parse_wave7_documents(
                        runner,
                        control_held,
                    )
                    wave8_documents = parse_wave8_documents(
                        runner,
                        control_held,
                    )
                    predecessor_verification = (
                        validate_v6_predecessor_candidate(
                            runner,
                            predecessor_candidate,
                            wave8_documents[WAVE8_DECISION_PATH],
                        )
                    )
                    bindings = combined_source_bindings(
                        v6,
                        v5,
                        v4,
                        v1,
                        runner,
                        v1_documents,
                        wave3_documents,
                        wave4_documents,
                        wave5_documents,
                        wave6_documents,
                        wave7_documents,
                        wave8_documents,
                    )
                    wave8_evidence_raw = control_held.raw[WAVE8_EVIDENCE_PATH]
                    wave8_evidence_document = runner.strict_json(
                        wave8_evidence_raw,
                        WAVE8_EVIDENCE_PATH,
                    )
                    validate_wave8_evidence(
                        runner,
                        wave8_evidence_raw,
                        wave8_evidence_document,
                        wave8_documents,
                    )
                    validate_wave8_consumed_claims(
                        runner,
                        control_held.raw[WAVE8_ACQUISITION_CLAIM_PATH],
                        control_held.raw[WAVE8_READBACK_CLAIM_PATH],
                    )
                    validate_wave8_completed_namespace(
                        control_held,
                        wave8_documents,
                    )
                    with runner.HeldInputSet(root, bindings) as source_held:
                        held_inputs = (
                            self_held,
                            v6_held,
                            v5_held,
                            v4_held,
                            v1_held,
                            provider_held,
                            control_held,
                            source_held,
                        )
                        v4.combined_identity_barrier(root, held_inputs)
                        limits = v1.graph_limits(runner)
                        first_graph, first_coverage = (
                            v4.reconstruct_graph_v3(
                                runner,
                                v1_documents[v1.WAVE1_PERMIT_PATH],
                                bindings,
                                source_held,
                                limits,
                            )
                        )
                        v4.combined_identity_barrier(root, held_inputs)
                        second_graph, second_coverage = (
                            v4.reconstruct_graph_v3(
                                runner,
                                v1_documents[v1.WAVE1_PERMIT_PATH],
                                bindings,
                                source_held,
                                limits,
                            )
                        )
                        check(
                            runner.canonical_json_bytes(first_graph)
                            == runner.canonical_json_bytes(second_graph)
                            and first_coverage == second_coverage,
                            "E_REPRODUCTION",
                        )
                        v4.combined_identity_barrier(root, held_inputs)
                        projection = v1.source_projection(bindings)
                        route = v1.route_for_graph(first_graph)
                        frontier = first_graph["exactFrontier"]
                        derived_result = derive_and_validate_graph_result(
                            runner,
                            first_graph,
                            route,
                        )
                        fixed_point = derived_result["fixedPointReached"]
                        inherited_reconstructions = predecessor_candidate[
                            "checkerVerification"
                        ]["totalFullInputReconstructionCount"]
                        inherited_source_reconstructions = (
                            predecessor_candidate["operationCounters"][
                                "totalFullSourceReconstructionCount"
                            ]
                        )
                        body = {
                            "documentType": (
                                "aetherlink.g2-pion-combined-wave1-wave2-"
                                "wave3-wave4-wave5-wave6-wave7-wave8-"
                                "fixed-point-candidate"
                            ),
                            "schemaVersion": "7.0",
                            "checkerId": CHECKER_ID,
                            "status": route["status"],
                            "result": (
                                "combined_graph_recomputed_twice_from_exact_"
                                "wave1_through_wave8_source_bytes"
                            ),
                            "verificationOnly": True,
                            "recordModeExposed": False,
                            "sourceInspectionPolicy": (
                                predecessor_candidate[
                                    "sourceInspectionPolicy"
                                ]
                            ),
                            "inputSet": {
                                "heldSourceInputCount": len(bindings),
                                "rootArchiveCount": 1,
                                "resourceCount": 256,
                                "modCount": 128,
                                "zipCount": 128,
                                "wave1ResourceCount": 38,
                                "wave2ResourceCount": 30,
                                "wave3ResourceCount": 32,
                                "wave4ResourceCount": 32,
                                "wave5ResourceCount": 30,
                                "wave6ResourceCount": 36,
                                "wave7ResourceCount": 30,
                                "wave8ResourceCount": 28,
                                "uniqueModuleVersionTupleCount": 128,
                                "aggregateRawByteSize": sum(
                                    row["maximumBytes"] for row in bindings
                                ),
                                "sourceBindings": projection,
                                "combinedInputSetSha256": sha256_bytes(
                                    runner.canonical_json_bytes(projection)
                                ),
                                "wave1OrderedSourceSetSha256": v1_documents[
                                    v1.WAVE1_PERMIT_PATH
                                ]["inputBindings"]["orderedSourceSetSha256"],
                                "wave2OrderedSourceSetSha256": v1_documents[
                                    v1.WAVE2_RECEIPT_PATH
                                ]["orderedSourceSetSha256"],
                                "wave3AcceptedResourceSetSha256":
                                    v4.WAVE3_RESOURCE_SET_SHA256,
                                "wave4AcceptedResourceSetSha256":
                                    v4.WAVE4_RESOURCE_SET_SHA256,
                                "wave5AcceptedResourceSetSha256":
                                    v4.WAVE5_RESOURCE_SET_SHA256,
                                "wave6AcceptedResourceSetSha256":
                                    v5.WAVE6_RESOURCE_SET_SHA256,
                                "wave7AcceptedResourceSetSha256":
                                    v6.WAVE7_RESOURCE_SET_SHA256,
                                "wave8AcceptedResourceSetSha256":
                                    WAVE8_RESOURCE_SET_SHA256,
                            },
                            "toolBindings": [
                                {
                                    "role": "current_v7_combined_checker",
                                    "path": SELF_PATH,
                                    "normalizedSha256":
                                        SELF_NORMALIZED_SHA256,
                                },
                                {
                                    "role": "immutable_v6_combined_checker",
                                    "path": V6_CHECKER_PATH,
                                    "rawSha256": V6_CHECKER_RAW_SHA256,
                                    "normalizedSha256":
                                        V6_CHECKER_NORMALIZED_SHA256,
                                },
                                {
                                    "role": "immutable_v5_combined_checker",
                                    "path": V5_CHECKER_PATH,
                                    "rawSha256": V5_CHECKER_RAW_SHA256,
                                    "normalizedSha256":
                                        V5_CHECKER_NORMALIZED_SHA256,
                                },
                                {
                                    "role": "immutable_v4_combined_checker",
                                    "path": V4_CHECKER_PATH,
                                    "rawSha256": V4_CHECKER_RAW_SHA256,
                                },
                                {
                                    "role": "immutable_v1_combined_checker",
                                    "path": v4.V1_CHECKER_PATH,
                                    "rawSha256":
                                        v4.V1_CHECKER_RAW_SHA256,
                                },
                                {
                                    "role": "immutable_wave1_graph_provider",
                                    "path": v4.V1_PROVIDER_PATH,
                                    "rawSha256":
                                        v4.V1_PROVIDER_RAW_SHA256,
                                },
                            ],
                            "terminalEvidenceBindings": [
                                {
                                    "path": row["path"],
                                    "rawSha256": row["rawSha256"],
                                }
                                for row in controls
                            ],
                            "auxiliaryEvidenceBindings": [
                                {
                                    "path": row["path"],
                                    "rawSha256": row["rawSha256"],
                                }
                                for row in auxiliary_evidence
                            ],
                            "predecessorVerification":
                                predecessor_verification,
                            "coverage": first_coverage,
                            "profiles": runner.profile_rows(
                                v1_documents[v1.WAVE1_PERMIT_PATH]
                            ),
                            "graphDiscovery": first_graph,
                            "derivedResult": derived_result,
                            "checkerVerification": {
                                "directFullInputReconstructionCount": 2,
                                "inheritedFullInputReconstructionCount":
                                    inherited_reconstructions,
                                "totalFullInputReconstructionCount":
                                    inherited_reconstructions + 2,
                                "underlyingIndependentGraphAlgorithmCount":
                                    predecessor_candidate[
                                        "checkerVerification"
                                    ][
                                        "underlyingIndependentGraphAlgorithmCount"
                                    ]
                                    + 4,
                                "pinnedV6PredecessorExecuted": True,
                                "canonicalGraphEqualityVerified": True,
                                "barrierBeforeReconstructionCompleted": True,
                                "barrierBetweenReconstructionsCompleted": True,
                                "barrierAfterReconstructionCompleted": True,
                                "workspaceRootIdentityBoundAcrossAllInputs":
                                    True,
                                "calculatedFixedPointCandidate": fixed_point,
                                "wave8HistoricalExact46FrozenSnapshotDescriptorSetBound":
                                    True,
                                "wave8LiveTerminalControlMetadataVerified":
                                    True,
                                "wave8LiveFinalAndAcceptedInventoriesVerified":
                                    True,
                                "wave8FinalNamespaceReverifiedAfterReconstruction":
                                    True,
                                "wave8RetainedFdPreManifestBarrierCount": 3,
                                "wave8CompletionAppliesToRetainedSnapshot":
                                    True,
                                "wave8CurrentPathIdentityGuaranteedThroughManifestPublication":
                                    False,
                                "wave8SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                                    False,
                                "transitiveSafePinnedClassesVerified":
                                    True,
                                "readOnlyProviderFacadeVerified": True,
                                "providerFacadeVerificationScope": (
                                    "trusted_pinned_normal_reconstruction_path"
                                ),
                                "hardenedCheckerModuleCount":
                                    predecessor_candidate[
                                        "checkerVerification"
                                    ]["hardenedCheckerModuleCount"] + 1,
                                "providerFacadeLoadCount":
                                    predecessor_candidate[
                                        "checkerVerification"
                                    ]["providerFacadeLoadCount"]
                                    + PROVIDER_FACADE_LOAD_COUNT,
                            },
                            "route": route["route"],
                            "nextAction": route["nextAction"],
                            "operationCounters": {
                                "heldSourceInputCount": len(bindings),
                                "heldTerminalEvidenceCount": len(controls),
                                "heldAuxiliaryEvidenceCount":
                                    len(auxiliary_evidence),
                                "heldToolInputCount": 6,
                                "transitiveDistinctToolPathCount": 8,
                                "stableReadPassesPerHeldInput": 2,
                                "directFullSourceReconstructionCount": 2,
                                "inheritedFullSourceReconstructionCount":
                                    inherited_source_reconstructions,
                                "totalFullSourceReconstructionCount":
                                    inherited_source_reconstructions + 2,
                                "directArchiveOpenCount":
                                    first_coverage["archiveCount"] * 2,
                                "inheritedArchiveOpenCount":
                                    predecessor_candidate[
                                        "operationCounters"
                                    ]["archiveOpenCount"],
                                "totalArchiveOpenCount": (
                                    predecessor_candidate[
                                        "operationCounters"
                                    ]["archiveOpenCount"]
                                    + first_coverage["archiveCount"] * 2
                                ),
                                "archiveOpenCount": (
                                    predecessor_candidate[
                                        "operationCounters"
                                    ]["archiveOpenCount"]
                                    + first_coverage["archiveCount"] * 2
                                ),
                                "archiveExtractionCount": 0,
                                "dependencySourceLoadCount": 0,
                                "dependencySourceExecutionCount": 0,
                                "dependencySourceCompileCount": 0,
                                "subprocessCount": 0,
                                "networkOperationCount": 0,
                                "fileWriteCount": 0,
                            },
                            "closure": {
                                "dependencyFixedPointReached": fixed_point,
                                "dependencySourceReviewed": False,
                                "dependencyClosureComplete": False,
                                "semanticClosureComplete": False,
                                "licenseCompatibilityReviewed": False,
                                "securityReviewComplete": False,
                                "rungThreeComplete": False,
                                "candidateSelected": False,
                                "librarySelected": False,
                                "releaseReady": False,
                            },
                            "authority": {
                                "decisionAuthorityGranted": False,
                                "executionAuthorityGranted": False,
                                "acquisitionAuthorityGranted": False,
                                "publicationAuthorityGranted": False,
                                "networkAuthorized": False,
                                "sourceExecutionAuthorized": False,
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
                                "osSyscallSandboxProvided": False,
                            },
                        }
                        candidate = runner.content_bound(
                            body,
                            "candidate_without_contentBinding",
                        )
                        v4.combined_identity_barrier(root, held_inputs)
                        validate_wave8_completed_namespace(
                            control_held,
                            wave8_documents,
                        )
                        return candidate


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def error_document_bytes() -> bytes:
    return (
        json.dumps(
            {
                "documentType": (
                    "aetherlink.g2-pion-combined-wave1-through-wave8-"
                    "fixed-point-check-error"
                ),
                "schemaVersion": "7.0",
                "status": "verification_failed",
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def emit_error_document() -> int:
    try:
        sys.stdout.buffer.write(error_document_bytes())
    except Exception:
        pass
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parse_arguments(argv)
        candidate = generate_candidate(ROOT)
        sys.stdout.buffer.write(
            json.dumps(
                candidate,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        return 0
    except (CombinedCheckFailure, CliUsageFailure, OSError, ValueError):
        return emit_error_document()
    except Exception:
        return emit_error_document()


if __name__ == "__main__":
    raise SystemExit(main())
