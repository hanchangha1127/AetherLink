#!/usr/bin/env python3
"""Validate immutable G2 Pion rung-three permit-v2 failure evidence.

The checker reads a closed set of tracked files plus the exact v2 one-use
claim.  In the build tree it checks only four fixed report names.  It cannot
enumerate build, open or stat the retained archive, reproduce the runner
failure, use the network, invoke Git, or use a device.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG3 = f"{BASE}/rung-three"

FAILURE_PATH = f"{RUNG3}/offline-source-review-execution-failure-v2.json"
PROGRESS_PATH = f"{RUNG3}/offline-source-review-progress-v3.json"
SUPERSESSION_PATH = f"{RUNG3}/canonical-document-supersession-v3.json"
MANIFEST_PATH = f"{RUNG3}/evidence-manifest-v8.json"
PERMIT_PATH = f"{RUNG3}/offline-source-review-execution-permit-v2.json"
CORE_MANIFEST_PATH = f"{RUNG3}/execution-permit-core-manifest-v6.json"
TOOL_MANIFEST_PATH = f"{RUNG3}/execution-permit-checker-manifest-v7.json"
PREVIOUS_PROGRESS_PATH = f"{RUNG3}/offline-source-review-progress-v2.json"
PREVIOUS_SUPERSESSION_PATH = f"{RUNG3}/canonical-document-supersession-v2.json"
RUNNER_PATH = "script/run_p2p_nat_g2_pion_rung3_offline_review_v2_once.py"
CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_failure_v2.py"
CHECKER_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_execution_failure_v2.py"

TRACKED_READ_ALLOWLIST = frozenset(
    {
        FAILURE_PATH,
        PROGRESS_PATH,
        SUPERSESSION_PATH,
        MANIFEST_PATH,
        PERMIT_PATH,
        CORE_MANIFEST_PATH,
        TOOL_MANIFEST_PATH,
        PREVIOUS_PROGRESS_PATH,
        PREVIOUS_SUPERSESSION_PATH,
        RUNNER_PATH,
        CHECKER_PATH,
        CHECKER_TEST_PATH,
    }
)

CLAIM_DIRECTORY_PARTS = (
    "build",
    "offline-source",
    "pion-ice-v4.3.0",
    "review-v2",
)
CLAIM_DIRECTORY = "/".join(CLAIM_DIRECTORY_PARTS)
CLAIM_NAME = ".g2-pion-ice-v4.3.0-rung3-offline-review-v2.claim"
CLAIM_PATH = f"{CLAIM_DIRECTORY}/{CLAIM_NAME}"
ABSENCE_NAMES = (
    "offline-source-review-result-v2.json",
    "offline-source-review-manifest-v2.json",
    ".offline-source-review-result-v2.json.tmp",
    ".offline-source-review-manifest-v2.json.tmp",
)

EXPECTED_DATE = "2026-07-23"
EXPECTED_STATUS = "rung3_bounded_static_inventory_permit_v2_consumed_failed_closed"
EXPECTED_RESULT = "candidate_inventory_hit_bound_exceeded_before_report_publication"
EXPECTED_NEXT_ACTION = (
    "preserve_v2_claim_and_review_inventory_bound_design_before_any_"
    "separate_versioned_permit"
)
EXPECTED_FAILURE_REASON = (
    "candidate inventory for 'disable_nonprofile_network_paths' exceeds its hit bound"
)

EXPECTED_PERMIT_RAW_SHA256 = (
    "7f125ecc7d6e6d0a597cb4cddecebf37eaad5e0a8f614d1019603b4e952f9a06"
)
EXPECTED_PERMIT_SEMANTIC_SHA256 = (
    "3164cbf4b25f75c9689ad47db50776ba4fbbe7c4b315dfa5bcfbbba01e5c0321"
)
EXPECTED_CORE_RAW_SHA256 = (
    "443c6d918b94329692f1ed57a989263ae38f939120752103c47e852c50f83e73"
)
EXPECTED_CORE_SEMANTIC_SHA256 = (
    "861c04832e845be2066632697f1a5b8eb3085157328351cde5fdc052c6c00240"
)
EXPECTED_CORE_COLLECTION_SHA256 = (
    "cf53cf2b33ab07ec539a97a4f8f43cc84e32848e9fbfb2ae8669250529312f41"
)
EXPECTED_TOOL_MANIFEST_RAW_SHA256 = (
    "35538ba8c5db14d881b9d1f2420637e21f4a9e2a4b376e4e0f1687e6c137d3aa"
)
EXPECTED_TOOL_MANIFEST_SEMANTIC_SHA256 = (
    "dee99588758c8d8c9f9e0efdbd2c63abfaac9df4bb9c7c1d0d4bbf31cb0c9b32"
)
EXPECTED_TOOL_MANIFEST_COLLECTION_SHA256 = (
    "96bd129c1020591b8f4b19e6b9037631ee2801615cd07ef7581ba813bd5828e8"
)
EXPECTED_PREVIOUS_PROGRESS_RAW_SHA256 = (
    "a58e491f19707c0d4fef4401aa27ff74fdcf473f71d79025e794e4ca538ddd65"
)
EXPECTED_PREVIOUS_PROGRESS_SEMANTIC_SHA256 = (
    "e73ee097dc42c6de26b4ae935bc78ee2304f15ce2bfcd78b6edd8c8961423b23"
)
EXPECTED_PREVIOUS_SUPERSESSION_RAW_SHA256 = (
    "d224fb87352447ff30bcf33e3498ae37fc68a2c9fd8380a167efb2f7552e7750"
)
EXPECTED_PREVIOUS_SUPERSESSION_SEMANTIC_SHA256 = (
    "2514334023680b5118c6fc354710ddb04337b2bd59c63424ae8500ed9fe65a87"
)
EXPECTED_RUNNER_RAW_SHA256 = (
    "938e44be1dc020e4f58175fe6d9190108ae70a38d307fc83ef093ce445f529e7"
)

EXPECTED_FAILURE_RAW_SHA256 = (
    "c1c36b4f2a6aaeddacbfad56e19cb3c658569e7f561eef764c4d48652be2b66c"
)
EXPECTED_FAILURE_SEMANTIC_SHA256 = (
    "375becf562bcaf628b61cbc23369135ef6e1849332df00a804655dd4c08074bd"
)
EXPECTED_PROGRESS_RAW_SHA256 = (
    "2b4a3a5c89bf5f1d9821f1ed83e78f8953d775f8d49d385a1177acb572c6dd00"
)
EXPECTED_PROGRESS_SEMANTIC_SHA256 = (
    "4b677f1e6a91db2c91109b8952851be7ae46650e0dbf75272f14e969c566bbb1"
)
EXPECTED_SUPERSESSION_RAW_SHA256 = (
    "7a2bf9d692396d356db4b98318fa066f9ff0af000b8b75ebe2b12c568ebbc938"
)
EXPECTED_SUPERSESSION_SEMANTIC_SHA256 = (
    "f82345cfbfb73933f54ff6879c428b7675f62b03cc03697cc77c93b3d4c555f0"
)
EXPECTED_CHECKER_TEST_RAW_SHA256 = (
    "cffaa6ebaae901da123dc0c66b921d27cec0e4e0df94c1eae0e40b249f370106"
)

EXPECTED_CLAIM_RAW_SHA256 = (
    "ff5a1ea309d1fd51b0ed46a35f6b711a829170d70c330135b40d214544b8de9d"
)
EXPECTED_CLAIM_BYTES = 446
EXPECTED_CLAIM = {
    "automaticRetryAllowed": False,
    "claimType": "aetherlink.g2-pion-rung3-offline-review-v2-one-use-claim",
    "externalIdentityProofRequired": False,
    "permitRawSha256": EXPECTED_PERMIT_RAW_SHA256,
    "repositoryOwnerAuthenticationRequired": False,
    "rule": (
        "claim_persists_after_successful_exclusive_creation_even_if_"
        "module_load_archive_read_inspection_or_publication_fails"
    ),
    "schemaVersion": "2.0",
    "userActionRequired": False,
}

PLACEHOLDER = re.compile(r"^__PENDING_[A-Z0-9_]+__$")
MAX_TRACKED_FILE_BYTES = 8 * 1024 * 1024


class CheckError(ValueError):
    """The immutable v2 failure evidence violated its closed contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(type(value) is type(expected), f"{label}: type mismatch")
    require(value == expected, f"{label}: mismatch")


def require_exact_keys(
    value: Any, expected: set[str], label: str
) -> Mapping[str, Any]:
    require(type(value) is dict, f"{label}: object required")
    require(set(value) == expected, f"{label}: exact keys mismatch")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def semantic_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite number")
    elif type(value) is list:
        for index, item in enumerate(value):
            reject_nonfinite(item, f"{label}[{index}]")
    elif type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(item, f"{label}.{key}")


def strict_json(data: bytes, label: str) -> Any:
    require(data.endswith(b"\n"), f"{label}: final LF required")
    require(b"\r" not in data, f"{label}: CR forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise CheckError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise CheckError(f"{label}: non-finite constant {value}")

    try:
        parsed = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid JSON: {error}") from error
    reject_nonfinite(parsed, label)
    return parsed


def unresolved_placeholders(value: Any, label: str = "$") -> list[str]:
    result: list[str] = []
    if type(value) is str and PLACEHOLDER.fullmatch(value):
        result.append(label)
    elif type(value) is list:
        for index, item in enumerate(value):
            result.extend(unresolved_placeholders(item, f"{label}[{index}]"))
    elif type(value) is dict:
        for key, item in value.items():
            result.extend(unresolved_placeholders(item, f"{label}.{key}"))
    return result


def validate_relative_tracked_path(path: str) -> tuple[str, ...]:
    require(type(path) is str, "tracked path must be string")
    require(path in TRACKED_READ_ALLOWLIST, f"unlisted tracked read: {path}")
    require("\\" not in path and "\x00" not in path, f"unsafe tracked path: {path}")
    pure = PurePosixPath(path)
    require(not pure.is_absolute(), f"absolute tracked path forbidden: {path}")
    require(
        pure.parts and all(part not in ("", ".", "..") for part in pure.parts),
        f"unsafe tracked path: {path}",
    )
    require(pure.parts[0] != "build", f"generic build read forbidden: {path}")
    return pure.parts


def stable_metadata(identity: os.stat_result) -> tuple[int, ...]:
    return (
        identity.st_dev,
        identity.st_ino,
        identity.st_size,
        identity.st_mode,
        identity.st_nlink,
        identity.st_uid,
        identity.st_mtime_ns,
        identity.st_ctime_ns,
    )


def named_identity(identity: os.stat_result) -> tuple[int, ...]:
    return (
        identity.st_dev,
        identity.st_ino,
        identity.st_size,
        identity.st_mode,
        identity.st_nlink,
        identity.st_uid,
    )


class SafeTrackedReader:
    """Component-wise nofollow reader for the closed tracked evidence set."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.cache: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        parts = validate_relative_tracked_path(path)
        if path in self.cache:
            return self.cache[path]
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        require(nofollow != 0 and directory != 0, "nofollow opens required")
        close_on_exec = getattr(os, "O_CLOEXEC", 0)
        directory_flags = os.O_RDONLY | directory | nofollow | close_on_exec
        file_flags = os.O_RDONLY | nofollow | close_on_exec
        opened_dirs: list[int] = []
        try:
            root_fd = os.open(os.fspath(self.root), directory_flags)
        except OSError as error:
            raise CheckError(f"tracked root: safe open failed: {error}") from error
        parent_fd = root_fd
        try:
            root_identity = os.fstat(root_fd)
            require(stat.S_ISDIR(root_identity.st_mode), "tracked root: directory required")
            require(root_identity.st_uid == os.geteuid(), "tracked root: owner mismatch")
            for part in parts[:-1]:
                try:
                    named = os.stat(part, dir_fd=parent_fd, follow_symlinks=False)
                    next_fd = os.open(part, directory_flags, dir_fd=parent_fd)
                except OSError as error:
                    raise CheckError(f"{path}: safe directory open failed") from error
                opened_dirs.append(next_fd)
                opened = os.fstat(next_fd)
                require(stat.S_ISDIR(opened.st_mode), f"{path}: directory required")
                require(opened.st_uid == os.geteuid(), f"{path}: directory owner mismatch")
                require(
                    stat.S_IMODE(opened.st_mode) & 0o022 == 0,
                    f"{path}: writable directory component forbidden",
                )
                require(
                    named_identity(named) == named_identity(opened),
                    f"{path}: directory named inode mismatch",
                )
                parent_fd = next_fd
            try:
                named_before = os.stat(
                    parts[-1], dir_fd=parent_fd, follow_symlinks=False
                )
                file_fd = os.open(parts[-1], file_flags, dir_fd=parent_fd)
            except OSError as error:
                raise CheckError(f"{path}: safe file open failed") from error
            try:
                before = os.fstat(file_fd)
                require(stat.S_ISREG(before.st_mode), f"{path}: regular file required")
                require(before.st_uid == os.geteuid(), f"{path}: owner mismatch")
                require(before.st_nlink == 1, f"{path}: single link required")
                require(
                    0 <= before.st_size <= MAX_TRACKED_FILE_BYTES,
                    f"{path}: size out of bounds",
                )
                require(
                    named_identity(named_before) == named_identity(before),
                    f"{path}: named inode mismatch",
                )
                remaining = before.st_size
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(file_fd, min(65536, remaining))
                    require(bool(chunk), f"{path}: unexpected EOF")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(file_fd, 1) == b"", f"{path}: grew during read")
                after = os.fstat(file_fd)
                require(
                    stable_metadata(before) == stable_metadata(after),
                    f"{path}: changed during read",
                )
                named_after = os.stat(
                    parts[-1], dir_fd=parent_fd, follow_symlinks=False
                )
                require(
                    named_identity(after) == named_identity(named_after),
                    f"{path}: named inode changed",
                )
                data = b"".join(chunks)
            finally:
                os.close(file_fd)
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)
            os.close(root_fd)
        self.cache[path] = data
        return data

    def json(self, path: str) -> Any:
        return strict_json(self.read(path), path)


def require_safe_directory(identity: os.stat_result, label: str) -> None:
    require(stat.S_ISDIR(identity.st_mode), f"{label}: directory required")
    require(identity.st_uid == os.geteuid(), f"{label}: owner mismatch")
    require(
        stat.S_IMODE(identity.st_mode) & 0o022 == 0,
        f"{label}: group/world writable directory forbidden",
    )


class SafeClaimObservationReader:
    """Read the exact v2 claim and lstat only four fixed report names."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _require_absent(directory_fd: int, name: str) -> None:
        require(name in ABSENCE_NAMES, f"unlisted absence name: {name}")
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as error:
            if error.errno == errno.ENOENT:
                return
            raise CheckError(f"{CLAIM_DIRECTORY}/{name}: absence check failed") from error
        raise CheckError(f"{CLAIM_DIRECTORY}/{name}: expected absent")

    def inspect(self) -> dict[str, Any]:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        require(nofollow != 0 and directory != 0, "nofollow opens required")
        close_on_exec = getattr(os, "O_CLOEXEC", 0)
        directory_flags = os.O_RDONLY | directory | nofollow | close_on_exec
        file_flags = os.O_RDONLY | nofollow | close_on_exec
        opened_dirs: list[int] = []
        try:
            root_fd = os.open(os.fspath(self.root), directory_flags)
        except OSError as error:
            raise CheckError(f"runtime root: safe open failed: {error}") from error
        parent_fd = root_fd
        review_parent_fd = -1
        review_fd = -1
        review_named_before: os.stat_result | None = None
        try:
            require_safe_directory(os.fstat(root_fd), "runtime root")
            for index, part in enumerate(CLAIM_DIRECTORY_PARTS):
                try:
                    named = os.stat(part, dir_fd=parent_fd, follow_symlinks=False)
                    next_fd = os.open(part, directory_flags, dir_fd=parent_fd)
                except OSError as error:
                    raise CheckError(
                        f"{CLAIM_DIRECTORY}: safe directory open failed"
                    ) from error
                opened = os.fstat(next_fd)
                require_safe_directory(opened, f"{part} directory")
                require(
                    named_identity(named) == named_identity(opened),
                    f"{CLAIM_DIRECTORY}: directory named inode mismatch",
                )
                opened_dirs.append(next_fd)
                if index == len(CLAIM_DIRECTORY_PARTS) - 1:
                    review_parent_fd = parent_fd
                    review_fd = next_fd
                    review_named_before = named
                parent_fd = next_fd
            require(
                review_fd >= 0 and review_named_before is not None,
                "review directory missing",
            )
            review_before = os.fstat(review_fd)
            require(
                stat.S_IMODE(review_before.st_mode) == 0o700,
                "review directory mode must be 0700",
            )
            for name in ABSENCE_NAMES:
                self._require_absent(review_fd, name)
            try:
                claim_named_before = os.stat(
                    CLAIM_NAME, dir_fd=review_fd, follow_symlinks=False
                )
                claim_fd = os.open(CLAIM_NAME, file_flags, dir_fd=review_fd)
            except OSError as error:
                raise CheckError(f"{CLAIM_PATH}: safe claim open failed") from error
            try:
                before = os.fstat(claim_fd)
                require(stat.S_ISREG(before.st_mode), f"{CLAIM_PATH}: regular required")
                require(before.st_uid == os.geteuid(), f"{CLAIM_PATH}: owner mismatch")
                require(before.st_nlink == 1, f"{CLAIM_PATH}: single link required")
                require(
                    stat.S_IMODE(before.st_mode) == 0o600,
                    f"{CLAIM_PATH}: mode must be 0600",
                )
                require(
                    before.st_size == EXPECTED_CLAIM_BYTES,
                    f"{CLAIM_PATH}: size mismatch",
                )
                require(
                    named_identity(claim_named_before) == named_identity(before),
                    f"{CLAIM_PATH}: named inode mismatch",
                )
                remaining = before.st_size
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(claim_fd, min(65536, remaining))
                    require(bool(chunk), f"{CLAIM_PATH}: unexpected EOF")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(claim_fd, 1) == b"", f"{CLAIM_PATH}: grew during read")
                after = os.fstat(claim_fd)
                require(
                    stable_metadata(before) == stable_metadata(after),
                    f"{CLAIM_PATH}: changed during read",
                )
                claim_named_after = os.stat(
                    CLAIM_NAME, dir_fd=review_fd, follow_symlinks=False
                )
                require(
                    named_identity(after) == named_identity(claim_named_after),
                    f"{CLAIM_PATH}: named inode changed",
                )
                claim_raw = b"".join(chunks)
            finally:
                os.close(claim_fd)
            require(
                sha256_bytes(claim_raw) == EXPECTED_CLAIM_RAW_SHA256,
                f"{CLAIM_PATH}: raw digest mismatch",
            )
            claim = strict_json(claim_raw, CLAIM_PATH)
            require_exact(claim, EXPECTED_CLAIM, "claim")
            require(
                claim_raw == canonical_json_bytes(EXPECTED_CLAIM),
                f"{CLAIM_PATH}: canonical bytes mismatch",
            )
            for name in ABSENCE_NAMES:
                self._require_absent(review_fd, name)
            review_after = os.fstat(review_fd)
            require(
                stable_metadata(review_before) == stable_metadata(review_after),
                "review directory changed during observation",
            )
            review_named_after = os.stat(
                CLAIM_DIRECTORY_PARTS[-1],
                dir_fd=review_parent_fd,
                follow_symlinks=False,
            )
            require(
                named_identity(review_named_before)
                == named_identity(review_named_after)
                == named_identity(review_after),
                "review directory named inode changed",
            )
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)
            os.close(root_fd)
        return {
            "claimPath": CLAIM_PATH,
            "claimRawSha256": EXPECTED_CLAIM_RAW_SHA256,
            "claimBytes": EXPECTED_CLAIM_BYTES,
            "claimMode": "0600",
            "claimLinkCount": 1,
            "checkedAbsenceNames": list(ABSENCE_NAMES),
        }


def verify_pinned_json(
    reader: SafeTrackedReader,
    path: str,
    raw_digest: str,
    semantic_digest: str,
) -> Any:
    raw = reader.read(path)
    document = strict_json(raw, path)
    require(sha256_bytes(raw) == raw_digest, f"{path}: raw digest mismatch")
    require(
        semantic_sha256(document) == semantic_digest,
        f"{path}: semantic digest mismatch",
    )
    return document


def validate_content_binding(document: Mapping[str, Any], scope: str, label: str) -> None:
    binding = require_exact_keys(
        document["contentBinding"],
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    require_exact(
        {key: binding[key] for key in ("algorithm", "canonicalization", "scope")},
        {
            "algorithm": "sha256",
            "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": scope,
        },
        f"{label}.contentBinding contract",
    )
    core = {key: value for key, value in document.items() if key != "contentBinding"}
    require(
        binding["sha256"] == sha256_bytes(canonical_json_bytes(core)),
        f"{label}: content binding mismatch",
    )


EXPECTED_PERMIT_BINDING = {
    "path": PERMIT_PATH,
    "permitId": "g2-pion-ice-v4.3.0-offline-source-review-execution-permit-v2",
    "rawSha256": EXPECTED_PERMIT_RAW_SHA256,
    "semanticSha256": EXPECTED_PERMIT_SEMANTIC_SHA256,
    "consumed": True,
}
EXPECTED_CORE_BINDING = {
    "path": CORE_MANIFEST_PATH,
    "rawSha256": EXPECTED_CORE_RAW_SHA256,
    "semanticSha256": EXPECTED_CORE_SEMANTIC_SHA256,
    "collectionSha256": EXPECTED_CORE_COLLECTION_SHA256,
}
EXPECTED_TOOL_BINDING = {
    "path": TOOL_MANIFEST_PATH,
    "rawSha256": EXPECTED_TOOL_MANIFEST_RAW_SHA256,
    "semanticSha256": EXPECTED_TOOL_MANIFEST_SEMANTIC_SHA256,
    "collectionSha256": EXPECTED_TOOL_MANIFEST_COLLECTION_SHA256,
}
EXPECTED_PERSONAL_BOUNDARY = {
    "technicalSafetyGatesRemainRequired": True,
    "repositoryOwnerAuthenticationRequired": False,
    "externalIdentityProofRequired": False,
    "executionPermitAuthenticationRequired": False,
    "userActionRequired": False,
    "productEndpointAuthenticationChangedByThisEvidence": False,
}
EXPECTED_REMAINING_VERIFICATION = [
    {"id": "g2-r3-egress-path-coverage", "status": "required_check_not_executed"},
    {"id": "g2-r3-ingress-path-coverage", "status": "required_check_not_executed"},
    {
        "id": "g2-r3-address-and-resolution-adversarial",
        "status": "required_check_not_executed",
    },
    {
        "id": "g2-r3-turn-tls-service-identity",
        "status": "required_check_not_executed",
    },
    {"id": "g2-r3-secure-session-promotion", "status": "required_check_not_executed"},
    {"id": "g2-r3-resource-and-event-bounds", "status": "required_check_not_executed"},
    {"id": "g2-r3-secret-free-diagnostics", "status": "required_check_not_executed"},
    {"id": "g2-r3-deadline-shutdown", "status": "required_check_not_executed"},
]


def validate_failure(document: Any) -> None:
    failure = require_exact_keys(
        document,
        {
            "documentType",
            "schemaVersion",
            "failureId",
            "recordedDate",
            "status",
            "result",
            "nextAction",
            "contentBinding",
            "permitBinding",
            "authorityManifestBindings",
            "runnerBinding",
            "claimEvidence",
            "reportAbsenceEvidence",
            "interactiveRunnerObservation",
            "independentlyRecheckedState",
            "executionBoundary",
            "checkerObservationBoundary",
            "personalProjectBoundary",
        },
        "failure",
    )
    require_exact(
        {key: failure[key] for key in (
            "documentType", "schemaVersion", "failureId", "recordedDate",
            "status", "result", "nextAction",
        )},
        {
            "documentType": "aetherlink.g2-pion-rung3-offline-source-review-execution-failure",
            "schemaVersion": "2.0",
            "failureId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-failure-v2",
            "recordedDate": EXPECTED_DATE,
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
        },
        "failure identity",
    )
    validate_content_binding(failure, "failure_without_contentBinding", "failure")
    require_exact(failure["permitBinding"], EXPECTED_PERMIT_BINDING, "failure permit")
    require_exact(
        failure["authorityManifestBindings"],
        {
            "core": EXPECTED_CORE_BINDING,
            "observationalToolchain": {
                **EXPECTED_TOOL_BINDING,
                "executionAuthority": False,
            },
        },
        "failure authority manifests",
    )
    require_exact(
        failure["runnerBinding"],
        {
            "path": RUNNER_PATH,
            "rawSha256": EXPECTED_RUNNER_RAW_SHA256,
            "invokedBytesAreLocalTrustRoot": True,
            "runnerSelfAuthenticationClaimed": False,
        },
        "failure runner binding",
    )
    require_exact(
        failure["claimEvidence"],
        {
            "path": CLAIM_PATH,
            "rawSha256": EXPECTED_CLAIM_RAW_SHA256,
            "bytes": EXPECTED_CLAIM_BYTES,
            "mode": "0600",
            "linkCount": 1,
            "claimType": EXPECTED_CLAIM["claimType"],
            "schemaVersion": "2.0",
            "permitRawSha256": EXPECTED_PERMIT_RAW_SHA256,
            "retained": True,
            "automaticRetryAllowed": False,
        },
        "failure claim evidence",
    )
    require_exact(
        failure["reportAbsenceEvidence"],
        {
            "directory": CLAIM_DIRECTORY,
            "checkedNames": list(ABSENCE_NAMES),
            "allAbsent": True,
            "directoryEnumerated": False,
        },
        "failure report absence",
    )
    require_exact(
        failure["interactiveRunnerObservation"],
        {
            "evidenceClass": "current_session_process_result_not_independent_runtime_receipt",
            "processExitCode": 1,
            "runnerReportedStatus": "failed_closed",
            "reason": EXPECTED_FAILURE_REASON,
            "automaticRetryAllowed": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "archiveOperationCountersPresentInFailurePayload": False,
            "sourceObservationCountersPresentInFailurePayload": False,
            "reportPublicationCountersPresentInFailurePayload": False,
        },
        "failure interactive observation",
    )
    require_exact(
        failure["independentlyRecheckedState"],
        {
            "evidenceClass": "claim_identity_and_exact_report_name_absence_only",
            "claimIdentityVerified": True,
            "claimRetainedVerified": True,
            "exactFourReportNameAbsenceVerified": True,
            "runnerFailureReasonIndependentlyReproduced": False,
            "candidateInventoryHitBoundIndependentlyReproduced": False,
            "archiveOpenCountIndependentlyProven": False,
            "archiveReadPassCountIndependentlyProven": False,
            "archiveEntryEnumerationCountIndependentlyProven": False,
            "sourceObservationCountIndependentlyProven": False,
        },
        "failure independent recheck",
    )
    require_exact(
        failure["executionBoundary"],
        {
            "completed": False,
            "permitConsumed": True,
            "claimRetained": True,
            "automaticRetryAllowed": False,
            "boundedCandidateLocationInventoryCompleted": False,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "sourceMaterialized": False,
            "sourceExecuted": False,
            "sourcePatched": False,
            "dependencyInstalled": False,
            "reviewedSourceCompiled": False,
            "completionManifestPublished": False,
            "networkUsed": False,
            "socketCreated": False,
            "gitOperationPerformed": False,
            "deviceOperationPerformed": False,
            "productionDeploymentAuthorized": False,
        },
        "failure execution boundary",
    )
    require_exact(
        failure["checkerObservationBoundary"],
        {
            "exactClaimReadAllowed": True,
            "exactFourReportNameAbsenceChecksAllowed": True,
            "buildDirectoryEnumerationAllowed": False,
            "archiveOpenByCheckerAllowed": False,
            "archiveReadByCheckerAllowed": False,
            "archiveStatByCheckerAllowed": False,
            "failureReproductionByCheckerAllowed": False,
        },
        "failure checker boundary",
    )
    require_exact(
        failure["personalProjectBoundary"],
        EXPECTED_PERSONAL_BOUNDARY,
        "failure personal boundary",
    )


def validate_progress(document: Any) -> None:
    progress = require_exact_keys(
        document,
        {
            "documentType",
            "schemaVersion",
            "progressId",
            "recordedDate",
            "status",
            "result",
            "nextAction",
            "contentBinding",
            "failureBinding",
            "permitBinding",
            "previousProgressBinding",
            "interactiveRunnerObservationSummary",
            "independentlyRecheckedState",
            "remainingVerification",
            "executionBoundary",
            "forwardOnlyBindings",
            "personalProjectBoundary",
        },
        "progress",
    )
    require_exact(
        {key: progress[key] for key in (
            "documentType", "schemaVersion", "progressId", "recordedDate",
            "status", "result", "nextAction",
        )},
        {
            "documentType": "aetherlink.g2-pion-rung3-offline-source-review-progress",
            "schemaVersion": "2.0",
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v3",
            "recordedDate": EXPECTED_DATE,
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
        },
        "progress identity",
    )
    validate_content_binding(progress, "progress_without_contentBinding", "progress")
    require_exact(
        progress["failureBinding"],
        {
            "path": FAILURE_PATH,
            "failureId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-failure-v2",
            "rawSha256": EXPECTED_FAILURE_RAW_SHA256,
            "semanticSha256": EXPECTED_FAILURE_SEMANTIC_SHA256,
            "requiredStatus": EXPECTED_STATUS,
        },
        "progress failure binding",
    )
    require_exact(progress["permitBinding"], EXPECTED_PERMIT_BINDING, "progress permit")
    require_exact(
        progress["previousProgressBinding"],
        {
            "path": PREVIOUS_PROGRESS_PATH,
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v2",
            "rawSha256": EXPECTED_PREVIOUS_PROGRESS_RAW_SHA256,
            "semanticSha256": EXPECTED_PREVIOUS_PROGRESS_SEMANTIC_SHA256,
            "recordedStatus": "rung3_bounded_static_inventory_permit_v1_consumed_failed_closed",
        },
        "progress predecessor",
    )
    require_exact(
        progress["interactiveRunnerObservationSummary"],
        {
            "evidenceClass": "current_session_process_result_not_independent_runtime_receipt",
            "permitVersion": 2,
            "permitConsumed": True,
            "claimRetained": True,
            "processExitCode": 1,
            "runnerReportedStatus": "failed_closed",
            "reason": EXPECTED_FAILURE_REASON,
            "completed": False,
            "completionManifestPublished": False,
            "automaticRetryAllowed": False,
        },
        "progress interactive observation",
    )
    require_exact(
        progress["independentlyRecheckedState"],
        {
            "evidenceClass": "claim_identity_and_exact_report_name_absence_only",
            "claimIdentityVerified": True,
            "claimRetainedVerified": True,
            "exactFourReportNameAbsenceVerified": True,
            "archiveOpenAndReadCountersIndependentlyProven": False,
            "sourceObservationCountIndependentlyProven": False,
            "failureReasonAndHitBoundIndependentlyReproduced": False,
        },
        "progress independent recheck",
    )
    require_exact(
        progress["remainingVerification"],
        EXPECTED_REMAINING_VERIFICATION,
        "progress remaining verification",
    )
    require_exact(
        progress["executionBoundary"],
        {
            "boundedCandidateLocationInventoryCompleted": False,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "sourceMaterialized": False,
            "sourcePatched": False,
            "sourceExecuted": False,
            "dependencyInstalled": False,
            "reviewedSourceCompiled": False,
            "networkUsed": False,
            "socketCreated": False,
            "gitOperationPerformed": False,
            "deviceOperationPerformed": False,
            "productionDeploymentAuthorized": False,
        },
        "progress execution boundary",
    )
    require_exact(
        progress["forwardOnlyBindings"],
        {
            "canonicalSupersession": {
                "path": SUPERSESSION_PATH,
                "supersessionId": "g2-pion-rung3-canonical-document-supersession-v3",
                "binding": "forward_identity_only_no_sha256",
            },
            "manifest": {
                "path": MANIFEST_PATH,
                "manifestId": "g2-pion-ice-v4.3.0-rung3-execution-failure-evidence-manifest-v8",
                "binding": "forward_identity_only_no_sha256",
            },
        },
        "progress forward bindings",
    )
    require_exact(
        progress["personalProjectBoundary"],
        EXPECTED_PERSONAL_BOUNDARY,
        "progress personal boundary",
    )


def validate_supersession(document: Any) -> None:
    supersession = require_exact_keys(
        document,
        {
            "documentType",
            "schemaVersion",
            "supersessionId",
            "recordedDate",
            "status",
            "result",
            "nextAction",
            "contentBinding",
            "reason",
            "predecessorSupersessionBinding",
            "predecessorManifestBinding",
            "failureBinding",
            "progressBinding",
            "supersededState",
            "currentState",
            "semanticGuard",
            "executionBoundary",
            "forwardOnlyManifestBinding",
        },
        "supersession",
    )
    require_exact(
        {key: supersession[key] for key in (
            "documentType", "schemaVersion", "supersessionId", "recordedDate",
            "status", "result", "nextAction", "reason",
        )},
        {
            "documentType": "aetherlink.g2-canonical-document-supersession",
            "schemaVersion": "2.0",
            "supersessionId": "g2-pion-rung3-canonical-document-supersession-v3",
            "recordedDate": EXPECTED_DATE,
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
            "reason": (
                "consumed_failed_closed_permit_v2_state_supersedes_v2_preexecution_"
                "authorized_not_consumed_state_without_rewriting_historical_evidence"
            ),
        },
        "supersession identity",
    )
    validate_content_binding(
        supersession, "supersession_without_contentBinding", "supersession"
    )
    require_exact(
        supersession["predecessorSupersessionBinding"],
        {
            "path": PREVIOUS_SUPERSESSION_PATH,
            "supersessionId": "g2-pion-rung3-canonical-document-supersession-v2",
            "rawSha256": EXPECTED_PREVIOUS_SUPERSESSION_RAW_SHA256,
            "semanticSha256": EXPECTED_PREVIOUS_SUPERSESSION_SEMANTIC_SHA256,
        },
        "supersession predecessor",
    )
    require_exact(
        supersession["predecessorManifestBinding"],
        EXPECTED_TOOL_BINDING,
        "supersession predecessor manifest",
    )
    require_exact(
        supersession["failureBinding"],
        {
            "path": FAILURE_PATH,
            "failureId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-failure-v2",
            "rawSha256": EXPECTED_FAILURE_RAW_SHA256,
            "semanticSha256": EXPECTED_FAILURE_SEMANTIC_SHA256,
        },
        "supersession failure",
    )
    require_exact(
        supersession["progressBinding"],
        {
            "path": PROGRESS_PATH,
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v3",
            "rawSha256": EXPECTED_PROGRESS_RAW_SHA256,
            "semanticSha256": EXPECTED_PROGRESS_SEMANTIC_SHA256,
        },
        "supersession progress",
    )
    require_exact(
        supersession["supersededState"],
        {
            "status": "rung3_bounded_static_inventory_v2_execution_authorized_not_consumed",
            "result": (
                "separate_single_use_bounded_static_candidate_location_inventory_"
                "v2_authorized_not_executed"
            ),
            "nextAction": "execute_bound_rung3_static_candidate_location_inventory_v2_once",
            "permitPath": PERMIT_PATH,
            "permitRawSha256": EXPECTED_PERMIT_RAW_SHA256,
        },
        "supersession superseded state",
    )
    require_exact(
        supersession["currentState"],
        {
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
            "permitVersionTwoConsumed": True,
            "automaticRetryAllowed": False,
            "rungThreeComplete": False,
        },
        "supersession current state",
    )
    require_exact(
        supersession["semanticGuard"],
        {
            "historicalEvidenceRewritten": False,
            "failureReinterpretedAsSuccess": False,
            "claimMustRemainPresent": True,
            "allRuntimeReportAndTemporaryNamesMustRemainAbsent": True,
            "interactiveFailureReason": EXPECTED_FAILURE_REASON,
            "interactiveFailureReasonIndependentlyReproduced": False,
            "requiredCurrentStatus": EXPECTED_STATUS,
            "requiredCurrentResult": EXPECTED_RESULT,
            "requiredCurrentNextAction": EXPECTED_NEXT_ACTION,
        },
        "supersession semantic guard",
    )
    require_exact(
        supersession["executionBoundary"],
        {
            "permitVersionTwoConsumed": True,
            "permitVersionTwoReusable": False,
            "boundedCandidateLocationInventoryCompleted": False,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "dependencyClosureComplete": False,
            "reviewedSourceCompileAuthorized": False,
            "runtimeNetworkAuthorized": False,
            "productionDeploymentAuthorized": False,
            "repositoryOwnerAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "executionPermitAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "supersession execution boundary",
    )
    require_exact(
        supersession["forwardOnlyManifestBinding"],
        {
            "path": MANIFEST_PATH,
            "manifestId": "g2-pion-ice-v4.3.0-rung3-execution-failure-evidence-manifest-v8",
            "binding": "forward_identity_only_no_sha256",
        },
        "supersession forward manifest",
    )


EXPECTED_ARTIFACT_IDENTITIES = (
    (
        "G2R3E038",
        FAILURE_PATH,
        "immutable_consumed_permit_v2_failed_closed_execution_record",
    ),
    (
        "G2R3E039",
        PROGRESS_PATH,
        "current_v2_failed_closed_rung3_progress",
    ),
    (
        "G2R3E040",
        SUPERSESSION_PATH,
        "canonical_v2_failed_closed_state_supersession",
    ),
    (
        "G2R3E041",
        CHECKER_PATH,
        "strict_v2_claim_only_no_archive_failure_evidence_checker",
    ),
    (
        "G2R3E042",
        CHECKER_TEST_PATH,
        "v2_failure_evidence_schema_runtime_and_mutation_tests",
    ),
)


def collection_sha256(artifacts: Sequence[Mapping[str, Any]]) -> str:
    payload = b"".join(
        (
            f"{artifact['evidenceId']}\t{artifact['sha256']}\t"
            f"{artifact['path']}\n"
        ).encode("utf-8")
        for artifact in artifacts
    )
    return sha256_bytes(payload)


def validate_manifest(document: Any, reader: SafeTrackedReader) -> None:
    manifest = require_exact_keys(
        document,
        {
            "documentType",
            "schemaVersion",
            "manifestId",
            "recordedDate",
            "status",
            "result",
            "nextAction",
            "artifactScope",
            "predecessorManifestBinding",
            "artifactCount",
            "orderingRule",
            "collectionDigestAlgorithm",
            "collectionSha256",
            "artifacts",
            "failureBoundary",
            "observationBoundary",
            "trustBoundary",
        },
        "manifest",
    )
    require_exact(
        {key: manifest[key] for key in (
            "documentType", "schemaVersion", "manifestId", "recordedDate",
            "status", "result", "nextAction", "artifactScope", "artifactCount",
            "orderingRule", "collectionDigestAlgorithm",
        )},
        {
            "documentType": "aetherlink.g2-pion-rung3-execution-failure-evidence-manifest",
            "schemaVersion": "2.0",
            "manifestId": "g2-pion-ice-v4.3.0-rung3-execution-failure-evidence-manifest-v8",
            "recordedDate": EXPECTED_DATE,
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
            "artifactScope": "immutable_v2_failed_closed_execution_evidence_with_claim_only_runtime_read",
            "artifactCount": 5,
            "orderingRule": "ascending_evidence_id",
            "collectionDigestAlgorithm": (
                "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_"
                "path_newline"
            ),
        },
        "manifest identity",
    )
    require_exact(
        manifest["predecessorManifestBinding"],
        EXPECTED_TOOL_BINDING,
        "manifest predecessor",
    )
    artifacts = manifest["artifacts"]
    require(type(artifacts) is list and len(artifacts) == 5, "manifest artifacts")
    for artifact, expected in zip(artifacts, EXPECTED_ARTIFACT_IDENTITIES):
        require_exact_keys(
            artifact, {"evidenceId", "path", "sha256", "role"}, "manifest artifact"
        )
        require_exact(
            (artifact["evidenceId"], artifact["path"], artifact["role"]),
            expected,
            "manifest artifact identity",
        )
        require(
            artifact["sha256"] == sha256_bytes(reader.read(artifact["path"])),
            f"{artifact['path']}: manifest digest mismatch",
        )
    require(
        [row["evidenceId"] for row in artifacts]
        == sorted(row["evidenceId"] for row in artifacts),
        "manifest artifact order",
    )
    require(
        manifest["collectionSha256"] == collection_sha256(artifacts),
        "manifest collection digest mismatch",
    )
    require_exact(
        manifest["failureBoundary"],
        {
            "permitVersionTwoConsumed": True,
            "automaticRetryAllowed": False,
            "completed": False,
            "completionManifestPublished": False,
            "boundedCandidateLocationInventoryCompleted": False,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "manifest failure boundary",
    )
    require_exact(
        manifest["observationBoundary"],
        {
            "interactiveFailureReasonIsIndependentReceipt": False,
            "independentRecheckScope": (
                "claim_identity_and_exact_four_report_name_absence_only"
            ),
            "failureReasonIndependentlyReproduced": False,
            "archiveOpenOrReadCountersIndependentlyProven": False,
            "sourceObservationCountersIndependentlyProven": False,
        },
        "manifest observation boundary",
    )
    require_exact(
        manifest["trustBoundary"],
        {
            "invokedCheckerBytesAreLocalTrustRoot": True,
            "checkerSelfAuthenticationClaimed": False,
            "exactClaimReadAllowed": True,
            "exactFourReportNameAbsenceChecksAllowed": True,
            "buildDirectoryEnumerationAllowed": False,
            "archiveOpenByCheckerAllowed": False,
            "archiveReadByCheckerAllowed": False,
            "archiveStatByCheckerAllowed": False,
            "networkAllowed": False,
            "gitAllowed": False,
            "deviceAllowed": False,
            "repositoryOwnerAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "executionPermitAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "manifest trust boundary",
    )


def validate_repository(root: Path) -> dict[str, Any]:
    reader = SafeTrackedReader(root)
    failure = verify_pinned_json(
        reader, FAILURE_PATH, EXPECTED_FAILURE_RAW_SHA256, EXPECTED_FAILURE_SEMANTIC_SHA256
    )
    progress = verify_pinned_json(
        reader, PROGRESS_PATH, EXPECTED_PROGRESS_RAW_SHA256, EXPECTED_PROGRESS_SEMANTIC_SHA256
    )
    supersession = verify_pinned_json(
        reader,
        SUPERSESSION_PATH,
        EXPECTED_SUPERSESSION_RAW_SHA256,
        EXPECTED_SUPERSESSION_SEMANTIC_SHA256,
    )
    verify_pinned_json(
        reader, PERMIT_PATH, EXPECTED_PERMIT_RAW_SHA256, EXPECTED_PERMIT_SEMANTIC_SHA256
    )
    verify_pinned_json(
        reader, CORE_MANIFEST_PATH, EXPECTED_CORE_RAW_SHA256, EXPECTED_CORE_SEMANTIC_SHA256
    )
    verify_pinned_json(
        reader,
        TOOL_MANIFEST_PATH,
        EXPECTED_TOOL_MANIFEST_RAW_SHA256,
        EXPECTED_TOOL_MANIFEST_SEMANTIC_SHA256,
    )
    verify_pinned_json(
        reader,
        PREVIOUS_PROGRESS_PATH,
        EXPECTED_PREVIOUS_PROGRESS_RAW_SHA256,
        EXPECTED_PREVIOUS_PROGRESS_SEMANTIC_SHA256,
    )
    verify_pinned_json(
        reader,
        PREVIOUS_SUPERSESSION_PATH,
        EXPECTED_PREVIOUS_SUPERSESSION_RAW_SHA256,
        EXPECTED_PREVIOUS_SUPERSESSION_SEMANTIC_SHA256,
    )
    require(
        sha256_bytes(reader.read(RUNNER_PATH)) == EXPECTED_RUNNER_RAW_SHA256,
        "runner raw digest mismatch",
    )
    require(
        sha256_bytes(reader.read(CHECKER_TEST_PATH))
        == EXPECTED_CHECKER_TEST_RAW_SHA256,
        "checker test raw digest mismatch",
    )
    manifest = reader.json(MANIFEST_PATH)
    for label, document in (
        ("failure", failure),
        ("progress", progress),
        ("supersession", supersession),
        ("manifest", manifest),
    ):
        require(not unresolved_placeholders(document), f"{label}: unresolved placeholder")
    validate_failure(failure)
    validate_progress(progress)
    validate_supersession(supersession)
    validate_manifest(manifest, reader)
    observed = SafeClaimObservationReader(root).inspect()
    require_exact(
        {
            "path": observed["claimPath"],
            "rawSha256": observed["claimRawSha256"],
            "bytes": observed["claimBytes"],
            "mode": observed["claimMode"],
            "linkCount": observed["claimLinkCount"],
        },
        {
            key: failure["claimEvidence"][key]
            for key in ("path", "rawSha256", "bytes", "mode", "linkCount")
        },
        "runtime claim cross-check",
    )
    require_exact(
        observed["checkedAbsenceNames"],
        failure["reportAbsenceEvidence"]["checkedNames"],
        "runtime absence cross-check",
    )
    return {
        "status": "validated",
        "failureId": failure["failureId"],
        "progressId": progress["progressId"],
        "supersessionId": supersession["supersessionId"],
        "manifestId": manifest["manifestId"],
        "claimRawSha256": observed["claimRawSha256"],
        "exactFourReportNamesAbsent": True,
        "archiveOpenCount": 0,
        "archiveReadPassCount": 0,
        "archiveStatCount": 0,
        "buildDirectoryEnumerationCount": 0,
        "failureReasonIndependentlyReproduced": False,
        "networkOperationCount": 0,
        "gitOperationCount": 0,
        "deviceOperationCount": 0,
        "repositoryOwnerAuthenticationRequired": False,
        "externalIdentityProofRequired": False,
        "executionPermitAuthenticationRequired": False,
        "userActionRequired": False,
    }


def require_isolated_interpreter() -> None:
    require(sys.flags.isolated == 1, "python -I required")
    require(sys.flags.dont_write_bytecode == 1, "python -B required")
    require(sys.flags.no_site == 1, "python -S required")


def main(argv: Sequence[str] | None = None) -> int:
    require_isolated_interpreter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        result = validate_repository(ROOT)
    except CheckError as error:
        print(f"G2 Pion rung-three v2 failure evidence check failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
