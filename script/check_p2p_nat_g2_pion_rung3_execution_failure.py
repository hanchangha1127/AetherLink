#!/usr/bin/env python3
"""Validate immutable G2 Pion rung-three permit-v1 failure evidence.

The checker reads a closed set of tracked evidence files plus the exact
one-use claim.  In the build tree it checks metadata absence for exactly four
report names.  It has no capability to enumerate the build directory, open the
source bundle, reproduce the runner, use the network, invoke Git, or use a
device.
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

FAILURE_PATH = f"{RUNG3}/offline-source-review-execution-failure-v1.json"
PROGRESS_PATH = f"{RUNG3}/offline-source-review-progress-v2.json"
SUPERSESSION_PATH = f"{RUNG3}/canonical-document-supersession-v2.json"
MANIFEST_PATH = f"{RUNG3}/evidence-manifest-v5.json"
PERMIT_PATH = f"{RUNG3}/offline-source-review-execution-permit-v1.json"
PREDECESSOR_MANIFEST_PATH = f"{RUNG3}/execution-permit-checker-manifest-v4.json"
PREVIOUS_PROGRESS_PATH = f"{RUNG3}/offline-source-review-progress-v1.json"
PREVIOUS_SUPERSESSION_PATH = f"{RUNG3}/canonical-document-supersession-v1.json"
CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_failure.py"
CHECKER_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_execution_failure.py"

TRACKED_READ_ALLOWLIST = frozenset(
    {
        FAILURE_PATH,
        PROGRESS_PATH,
        SUPERSESSION_PATH,
        MANIFEST_PATH,
        PERMIT_PATH,
        PREDECESSOR_MANIFEST_PATH,
        PREVIOUS_PROGRESS_PATH,
        PREVIOUS_SUPERSESSION_PATH,
        CHECKER_PATH,
        CHECKER_TEST_PATH,
    }
)

CLAIM_DIRECTORY_PARTS = (
    "build",
    "offline-source",
    "pion-ice-v4.3.0",
    "review-v1",
)
CLAIM_DIRECTORY = "/".join(CLAIM_DIRECTORY_PARTS)
CLAIM_NAME = ".g2-pion-ice-v4.3.0-rung3-offline-review-v1.claim"
CLAIM_PATH = f"{CLAIM_DIRECTORY}/{CLAIM_NAME}"
ABSENCE_NAMES = (
    "offline-source-review-result-v1.json",
    "offline-source-review-manifest-v1.json",
    ".offline-source-review-result-v1.json.tmp",
    ".offline-source-review-manifest-v1.json.tmp",
)

EXPECTED_DATE = "2026-07-23"
EXPECTED_STATUS = "rung3_bounded_static_inventory_permit_v1_consumed_failed_closed"
EXPECTED_RESULT = (
    "archive_rejected_before_source_decode_missing_auditable_unix_mode_metadata"
)
EXPECTED_NEXT_ACTION = (
    "prepare_separate_versioned_rung3_static_inventory_execution_permit_v2_"
    "with_exact_non_unix_creator_policy"
)
EXPECTED_FAILURE_CODE = "zip_entry_creator_mode_metadata_not_auditable"
EXPECTED_OBSERVED_ENTRY = "github.com/pion/ice/v4@v4.3.0/.github/.gitignore"

EXPECTED_PERMIT_RAW_SHA256 = (
    "13d1760477a07c32424f101fad98e85584c6a4335fb64e65992e099c750a756b"
)
EXPECTED_PERMIT_SEMANTIC_SHA256 = (
    "c28e798a1e953ffa291c9f9d7397ca377b3bc780b8a137325b0363951a083aac"
)
EXPECTED_PREDECESSOR_MANIFEST_RAW_SHA256 = (
    "437fc1faa7d0f406cc932be316897fc011f3428f408521f5578cdf476d4934e9"
)
EXPECTED_PREDECESSOR_MANIFEST_SEMANTIC_SHA256 = (
    "e95c34affc20acbf912c9a081e0f52fa0e631ad26add3063ea73ae64f07c6d47"
)
EXPECTED_PREDECESSOR_MANIFEST_COLLECTION_SHA256 = (
    "a19c61ca6a017159b62df238711e4de28903c670a1286b7e44b2f514f6c4741b"
)
EXPECTED_PREVIOUS_PROGRESS_RAW_SHA256 = (
    "651f8145ae91f7861b21565394db28b1608657c9bffd9a3e921aeafbff1fbabf"
)
EXPECTED_PREVIOUS_PROGRESS_SEMANTIC_SHA256 = (
    "e29a3745ec2a43bfdce0959d5b96baee679af2fb902dc6989436830cf59bd515"
)
EXPECTED_PREVIOUS_SUPERSESSION_RAW_SHA256 = (
    "ec57f0712309ef459b19e8155ce4450bb4b2d81c32b04e4a97e242f6824735bd"
)
EXPECTED_PREVIOUS_SUPERSESSION_SEMANTIC_SHA256 = (
    "fb9204ae5800964de278988d6969c234762b2f750efe17014f4d53631ef946f9"
)

EXPECTED_FAILURE_RAW_SHA256 = (
    "ec1883c9ca264e79120bf24a1624e661254beade219280122895ce05cbe1ec05"
)
EXPECTED_FAILURE_SEMANTIC_SHA256 = (
    "e13e2ceb158842a72cfe3b4ed76b9933225f7be169a46cda74c3ba76d682a7b3"
)
EXPECTED_PROGRESS_RAW_SHA256 = (
    "a58e491f19707c0d4fef4401aa27ff74fdcf473f71d79025e794e4ca538ddd65"
)
EXPECTED_PROGRESS_SEMANTIC_SHA256 = (
    "e73ee097dc42c6de26b4ae935bc78ee2304f15ce2bfcd78b6edd8c8961423b23"
)
EXPECTED_SUPERSESSION_RAW_SHA256 = (
    "d224fb87352447ff30bcf33e3498ae37fc68a2c9fd8380a167efb2f7552e7750"
)
EXPECTED_SUPERSESSION_SEMANTIC_SHA256 = (
    "2514334023680b5118c6fc354710ddb04337b2bd59c63424ae8500ed9fe65a87"
)
EXPECTED_CHECKER_TEST_RAW_SHA256 = (
    "fefa372f69b76300d985c8b96f048c89e17f985f2ade78dee7a362ff980ccf5a"
)

EXPECTED_CLAIM_RAW_SHA256 = (
    "955c0196c5ecea12e1249b8bbb5e8fe48b6f76510bba39e372d81f8e0904fafa"
)
EXPECTED_CLAIM_BYTES = 437
EXPECTED_CLAIM = {
    "automaticRetryAllowed": False,
    "claimType": "aetherlink.g2-pion-rung3-offline-review-one-use-claim",
    "externalIdentityProofRequired": False,
    "permitRawSha256": EXPECTED_PERMIT_RAW_SHA256,
    "repositoryOwnerAuthenticationRequired": False,
    "rule": (
        "claim_persists_after_successful_exclusive_creation_even_if_"
        "initialization_or_execution_fails_and_blocks_retry"
    ),
    "schemaVersion": "1.0",
    "userActionRequired": False,
}

PLACEHOLDER = re.compile(r"^__PENDING_[A-Z0-9_]+__$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_TRACKED_FILE_BYTES = 8 * 1024 * 1024


class CheckError(ValueError):
    """The immutable failure evidence did not satisfy its closed contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_exact_keys(
    value: Any, expected: set[str], label: str
) -> Mapping[str, Any]:
    require(type(value) is dict, f"{label} must be object")
    require(set(value) == expected, f"{label} exact keys mismatch")
    return value


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(type(value) is type(expected), f"{label} type mismatch")
    require(value == expected, f"{label} mismatch")


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


def semantic_sha256(parsed: Any) -> str:
    payload = json.dumps(
        parsed,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def strict_json(data: bytes, label: str) -> Any:
    require(data.endswith(b"\n"), f"{label}: final LF required")
    require(b"\r" not in data, f"{label}: CR forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise CheckError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise CheckError(f"{label}: non-finite JSON number {value}")

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


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite float")
    elif type(value) is list:
        for index, item in enumerate(value):
            reject_nonfinite(item, f"{label}[{index}]")
    elif type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(item, f"{label}.{key}")


def unresolved_placeholders(value: Any, label: str = "$") -> list[str]:
    found: list[str] = []
    if type(value) is str and PLACEHOLDER.fullmatch(value):
        found.append(label)
    elif type(value) is list:
        for index, item in enumerate(value):
            found.extend(unresolved_placeholders(item, f"{label}[{index}]"))
    elif type(value) is dict:
        for key, item in value.items():
            found.extend(unresolved_placeholders(item, f"{label}.{key}"))
    return found


def require_digest(value: Any, label: str) -> str:
    require(
        type(value) is str and HEX_SHA256.fullmatch(value) is not None,
        f"{label}: SHA-256 required",
    )
    return value


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
        require(nofollow != 0 and directory != 0, "nofollow directory opens required")
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
            root_stat = os.fstat(root_fd)
            require(stat.S_ISDIR(root_stat.st_mode), "tracked root must be directory")
            require(root_stat.st_uid == os.geteuid(), "tracked root owner mismatch")
            for part in parts[:-1]:
                try:
                    next_fd = os.open(part, directory_flags, dir_fd=parent_fd)
                except OSError as error:
                    raise CheckError(
                        f"{path}: safe directory open failed: {error}"
                    ) from error
                opened_dirs.append(next_fd)
                parent_fd = next_fd
                directory_stat = os.fstat(next_fd)
                require(
                    stat.S_ISDIR(directory_stat.st_mode),
                    f"{path}: directory component required",
                )
                require(
                    directory_stat.st_uid == os.geteuid(),
                    f"{path}: directory owner mismatch",
                )
                require(
                    stat.S_IMODE(directory_stat.st_mode) & 0o022 == 0,
                    f"{path}: writable directory component forbidden",
                )
            try:
                named_before = os.stat(
                    parts[-1], dir_fd=parent_fd, follow_symlinks=False
                )
                file_fd = os.open(parts[-1], file_flags, dir_fd=parent_fd)
            except OSError as error:
                raise CheckError(f"{path}: safe file open failed: {error}") from error
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
    """Read the exact claim and lstat only the four fixed report names."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _require_absent(directory_fd: int, name: str) -> None:
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
        require(nofollow != 0 and directory != 0, "nofollow directory opens required")
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
                    named_before = os.stat(
                        part, dir_fd=parent_fd, follow_symlinks=False
                    )
                    next_fd = os.open(part, directory_flags, dir_fd=parent_fd)
                except OSError as error:
                    raise CheckError(
                        f"{CLAIM_DIRECTORY}: safe directory open failed"
                    ) from error
                require(
                    named_identity(named_before)
                    == named_identity(os.fstat(next_fd)),
                    f"{CLAIM_DIRECTORY}: directory named inode mismatch",
                )
                require_safe_directory(
                    os.fstat(next_fd),
                    f"{CLAIM_DIRECTORY_PARTS[index]} directory",
                )
                opened_dirs.append(next_fd)
                if index == len(CLAIM_DIRECTORY_PARTS) - 1:
                    review_parent_fd = parent_fd
                    review_fd = next_fd
                    review_named_before = named_before
                parent_fd = next_fd
            require(review_fd >= 0 and review_named_before is not None, "review directory missing")
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
                claim_before = os.fstat(claim_fd)
                require(
                    stat.S_ISREG(claim_before.st_mode),
                    f"{CLAIM_PATH}: regular file required",
                )
                require(
                    claim_before.st_uid == os.geteuid(),
                    f"{CLAIM_PATH}: owner mismatch",
                )
                require(claim_before.st_nlink == 1, f"{CLAIM_PATH}: single link required")
                require(
                    stat.S_IMODE(claim_before.st_mode) == 0o600,
                    f"{CLAIM_PATH}: mode must be 0600",
                )
                require(
                    claim_before.st_size == EXPECTED_CLAIM_BYTES,
                    f"{CLAIM_PATH}: exact size mismatch",
                )
                require(
                    named_identity(claim_named_before) == named_identity(claim_before),
                    f"{CLAIM_PATH}: named inode mismatch",
                )
                remaining = EXPECTED_CLAIM_BYTES
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(claim_fd, min(65536, remaining))
                    require(bool(chunk), f"{CLAIM_PATH}: unexpected EOF")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(claim_fd, 1) == b"", f"{CLAIM_PATH}: grew during read")
                claim_after = os.fstat(claim_fd)
                require(
                    stable_metadata(claim_before) == stable_metadata(claim_after),
                    f"{CLAIM_PATH}: changed during read",
                )
                claim_named_after = os.stat(
                    CLAIM_NAME, dir_fd=review_fd, follow_symlinks=False
                )
                require(
                    named_identity(claim_after) == named_identity(claim_named_after),
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
    raw_sha256: str,
    semantic_digest: str,
) -> tuple[bytes, Any]:
    raw = reader.read(path)
    document = strict_json(raw, path)
    require(sha256_bytes(raw) == raw_sha256, f"{path}: raw digest mismatch")
    require(
        semantic_sha256(document) == semantic_digest,
        f"{path}: semantic digest mismatch",
    )
    return raw, document


def validate_content_binding(document: Mapping[str, Any], scope: str, label: str) -> None:
    binding = require_exact_keys(
        document["contentBinding"],
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    require_exact(
        {
            "algorithm": binding["algorithm"],
            "canonicalization": binding["canonicalization"],
            "scope": binding["scope"],
        },
        {
            "algorithm": "sha256",
            "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": scope,
        },
        f"{label}.contentBinding contract",
    )
    require_digest(binding["sha256"], f"{label}.contentBinding.sha256")
    core = {key: value for key, value in document.items() if key != "contentBinding"}
    require(
        binding["sha256"] == sha256_bytes(canonical_json_bytes(core)),
        f"{label}: content binding mismatch",
    )


EXPECTED_PERMIT_BINDING = {
    "path": PERMIT_PATH,
    "permitId": "g2-pion-ice-v4.3.0-offline-source-review-execution-permit-v1",
    "rawSha256": EXPECTED_PERMIT_RAW_SHA256,
    "semanticSha256": EXPECTED_PERMIT_SEMANTIC_SHA256,
    "consumed": True,
}
EXPECTED_PREDECESSOR_BINDING = {
    "path": PREDECESSOR_MANIFEST_PATH,
    "rawSha256": EXPECTED_PREDECESSOR_MANIFEST_RAW_SHA256,
    "semanticSha256": EXPECTED_PREDECESSOR_MANIFEST_SEMANTIC_SHA256,
    "collectionSha256": EXPECTED_PREDECESSOR_MANIFEST_COLLECTION_SHA256,
}
EXPECTED_PERSONAL_BOUNDARY = {
    "technicalSafetyGatesRemainRequired": True,
    "repositoryOwnerAuthenticationIsNotATechnicalGate": True,
    "repositoryOwnerAuthenticationRequired": False,
    "externalIdentityProofRequired": False,
    "userActionRequired": False,
}


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
            "predecessorManifestBinding",
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
        {
            key: failure[key]
            for key in (
                "documentType",
                "schemaVersion",
                "failureId",
                "recordedDate",
                "status",
                "result",
                "nextAction",
            )
        },
        {
            "documentType": (
                "aetherlink.g2-pion-rung3-offline-source-review-execution-failure"
            ),
            "schemaVersion": "1.0",
            "failureId": (
                "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-"
                "failure-v1"
            ),
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
        failure["predecessorManifestBinding"],
        EXPECTED_PREDECESSOR_BINDING,
        "failure predecessor",
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
            "schemaVersion": "1.0",
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
            "evidenceClass": (
                "current_session_process_result_not_independent_runtime_receipt"
            ),
            "code": EXPECTED_FAILURE_CODE,
            "observedArchiveEntryPath": EXPECTED_OBSERVED_ENTRY,
            "archiveRejectedBeforeSourceDecode": True,
            "sourceBytesDecoded": False,
            "candidateLocationInventoryStarted": False,
            "completionManifestPublished": False,
            "operationCounters": {
                "claimCreateCount": 1,
                "archiveOpenCount": 1,
                "archiveReadPassCount": 1,
                "centralDirectoryEnumerationAttemptCount": 1,
                "sourceObservationCount": 0,
                "reportPublicationCount": 0,
                "materializationCount": 0,
                "networkOperationCount": 0,
                "subprocessCount": 0,
                "socketCreateCount": 0,
                "gitOperationCount": 0,
                "deviceOperationCount": 0,
                "reviewedSourceCompilerInvocationCount": 0,
                "verifiedAuxiliaryToolModulePythonCompileCount": 2,
            },
        },
        "failure interactive runner observation",
    )
    require_exact(
        failure["independentlyRecheckedState"],
        {
            "evidenceClass": "claim_identity_and_exact_report_name_absence_only",
            "claimIdentityVerified": True,
            "claimRetainedVerified": True,
            "exactFourReportNameAbsenceVerified": True,
            "archiveOpenCountIndependentlyProven": False,
            "archiveReadPassCountIndependentlyProven": False,
            "centralDirectoryEnumerationAttemptCountIndependentlyProven": False,
            "failureCodeIndependentlyReproduced": False,
            "observedArchiveEntryPathIndependentlyReproduced": False,
        },
        "failure independently rechecked state",
    )
    require_exact(
        failure["executionBoundary"],
        {
            "completed": False,
            "permitConsumed": True,
            "claimRetained": True,
            "automaticRetryAllowed": False,
            "sourceDecoded": False,
            "sourceObserved": False,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "sourceMaterialized": False,
            "sourceExecuted": False,
            "sourcePatched": False,
            "dependencyInstalled": False,
            "reviewedSourceCompiled": False,
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
        },
        "failure checker observation boundary",
    )
    require_exact(
        failure["personalProjectBoundary"],
        {
            **EXPECTED_PERSONAL_BOUNDARY,
            "productEndpointAuthenticationRequired": True,
        },
        "failure personal project boundary",
    )


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
            "predecessorManifestBinding",
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
        {
            key: progress[key]
            for key in (
                "documentType",
                "schemaVersion",
                "progressId",
                "recordedDate",
                "status",
                "result",
                "nextAction",
            )
        },
        {
            "documentType": "aetherlink.g2-pion-rung3-offline-source-review-progress",
            "schemaVersion": "1.0",
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v2",
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
            "failureId": (
                "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-"
                "failure-v1"
            ),
            "rawSha256": EXPECTED_FAILURE_RAW_SHA256,
            "semanticSha256": EXPECTED_FAILURE_SEMANTIC_SHA256,
            "requiredStatus": EXPECTED_STATUS,
        },
        "progress failure binding",
    )
    require_exact(
        progress["permitBinding"],
        {
            "path": PERMIT_PATH,
            "rawSha256": EXPECTED_PERMIT_RAW_SHA256,
            "semanticSha256": EXPECTED_PERMIT_SEMANTIC_SHA256,
            "consumed": True,
        },
        "progress permit",
    )
    require_exact(
        progress["previousProgressBinding"],
        {
            "path": PREVIOUS_PROGRESS_PATH,
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v1",
            "rawSha256": EXPECTED_PREVIOUS_PROGRESS_RAW_SHA256,
            "semanticSha256": EXPECTED_PREVIOUS_PROGRESS_SEMANTIC_SHA256,
            "recordedStatus": "rung3_review_plan_recorded_execution_not_authorized",
        },
        "progress predecessor progress",
    )
    require_exact(
        progress["predecessorManifestBinding"],
        EXPECTED_PREDECESSOR_BINDING,
        "progress predecessor manifest",
    )
    require_exact(
        progress["interactiveRunnerObservationSummary"],
        {
            "evidenceClass": (
                "current_session_process_result_not_independent_runtime_receipt"
            ),
            "permitVersion": 1,
            "permitConsumed": True,
            "claimCreateCount": 1,
            "claimRetained": True,
            "archiveOpenCount": 1,
            "archiveReadPassCount": 1,
            "centralDirectoryEnumerationAttemptCount": 1,
            "completed": False,
            "sourceObservationCount": 0,
            "reportPublicationCount": 0,
            "archiveRejectedBeforeSourceDecode": True,
            "automaticRetryAllowed": False,
        },
        "progress interactive runner observation",
    )
    require_exact(
        progress["independentlyRecheckedState"],
        {
            "evidenceClass": "claim_identity_and_exact_report_name_absence_only",
            "claimIdentityVerified": True,
            "claimRetainedVerified": True,
            "exactFourReportNameAbsenceVerified": True,
            "archiveOpenAndReadCountersIndependentlyProven": False,
            "failureCodeAndEntryPathIndependentlyReproduced": False,
        },
        "progress independently rechecked state",
    )
    require_exact(
        progress["remainingVerification"],
        EXPECTED_REMAINING_VERIFICATION,
        "progress remaining verification",
    )
    require_exact(
        progress["executionBoundary"],
        {
            "boundedCandidateLocationInventoryPerformed": False,
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
                "supersessionId": "g2-pion-rung3-canonical-document-supersession-v2",
                "binding": "forward_identity_only_no_sha256",
            },
            "manifest": {
                "path": MANIFEST_PATH,
                "manifestId": (
                    "g2-pion-ice-v4.3.0-rung3-execution-failure-evidence-"
                    "manifest-v5"
                ),
                "binding": "forward_identity_only_no_sha256",
            },
        },
        "progress forward bindings",
    )
    require_exact(
        progress["personalProjectBoundary"],
        EXPECTED_PERSONAL_BOUNDARY,
        "progress personal project boundary",
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
        {
            key: supersession[key]
            for key in (
                "documentType",
                "schemaVersion",
                "supersessionId",
                "recordedDate",
                "status",
                "result",
                "nextAction",
                "reason",
            )
        },
        {
            "documentType": "aetherlink.g2-canonical-document-supersession",
            "schemaVersion": "1.0",
            "supersessionId": "g2-pion-rung3-canonical-document-supersession-v2",
            "recordedDate": EXPECTED_DATE,
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
            "reason": (
                "consumed_failed_closed_permit_v1_state_supersedes_"
                "preexecution_authorized_not_consumed_state_without_rewriting_"
                "historical_evidence"
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
            "supersessionId": "g2-pion-rung3-canonical-document-supersession-v1",
            "rawSha256": EXPECTED_PREVIOUS_SUPERSESSION_RAW_SHA256,
            "semanticSha256": EXPECTED_PREVIOUS_SUPERSESSION_SEMANTIC_SHA256,
        },
        "supersession predecessor supersession",
    )
    require_exact(
        supersession["predecessorManifestBinding"],
        EXPECTED_PREDECESSOR_BINDING,
        "supersession predecessor manifest",
    )
    require_exact(
        supersession["failureBinding"],
        {
            "path": FAILURE_PATH,
            "failureId": (
                "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-"
                "failure-v1"
            ),
            "rawSha256": EXPECTED_FAILURE_RAW_SHA256,
            "semanticSha256": EXPECTED_FAILURE_SEMANTIC_SHA256,
        },
        "supersession failure binding",
    )
    require_exact(
        supersession["progressBinding"],
        {
            "path": PROGRESS_PATH,
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v2",
            "rawSha256": EXPECTED_PROGRESS_RAW_SHA256,
            "semanticSha256": EXPECTED_PROGRESS_SEMANTIC_SHA256,
        },
        "supersession progress binding",
    )
    require_exact(
        supersession["supersededState"],
        {
            "status": "rung3_bounded_static_inventory_execution_authorized_not_consumed",
            "result": (
                "single_use_bounded_static_candidate_location_inventory_"
                "authorized_not_executed"
            ),
            "nextAction": "execute_bound_rung3_static_candidate_location_inventory_once",
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
            "permitVersionOneConsumed": True,
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
            "requiredFailureCode": EXPECTED_FAILURE_CODE,
            "requiredCurrentStatus": EXPECTED_STATUS,
            "requiredCurrentResult": EXPECTED_RESULT,
            "requiredCurrentNextAction": EXPECTED_NEXT_ACTION,
        },
        "supersession semantic guard",
    )
    require_exact(
        supersession["executionBoundary"],
        {
            "permitVersionOneConsumed": True,
            "permitVersionOneReusable": False,
            "boundedCandidateLocationInventoryPerformed": False,
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
            "userActionRequired": False,
        },
        "supersession execution boundary",
    )
    require_exact(
        supersession["forwardOnlyManifestBinding"],
        {
            "path": MANIFEST_PATH,
            "manifestId": (
                "g2-pion-ice-v4.3.0-rung3-execution-failure-evidence-manifest-v5"
            ),
            "binding": "forward_identity_only_no_sha256",
        },
        "supersession forward manifest",
    )


ARTIFACT_ROWS = (
    (
        "G2R3E023",
        FAILURE_PATH,
        "immutable_consumed_permit_v1_failed_closed_execution_record",
        EXPECTED_FAILURE_RAW_SHA256,
    ),
    (
        "G2R3E024",
        PROGRESS_PATH,
        "current_failed_closed_rung3_progress",
        EXPECTED_PROGRESS_RAW_SHA256,
    ),
    (
        "G2R3E025",
        SUPERSESSION_PATH,
        "canonical_failed_closed_state_supersession",
        EXPECTED_SUPERSESSION_RAW_SHA256,
    ),
    (
        "G2R3E026",
        CHECKER_PATH,
        "strict_claim_only_no_archive_failure_evidence_checker",
        None,
    ),
    (
        "G2R3E027",
        CHECKER_TEST_PATH,
        "failure_evidence_schema_runtime_and_mutation_tests",
        EXPECTED_CHECKER_TEST_RAW_SHA256,
    ),
)


def collection_sha256(artifacts: Sequence[Mapping[str, Any]]) -> str:
    payload = "".join(
        f"{item['evidenceId']}\t{item['sha256']}\t{item['path']}\n"
        for item in artifacts
    ).encode("utf-8")
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
            "trustBoundary",
        },
        "manifest",
    )
    require_exact(
        {
            key: manifest[key]
            for key in (
                "documentType",
                "schemaVersion",
                "manifestId",
                "recordedDate",
                "status",
                "result",
                "nextAction",
                "artifactScope",
                "artifactCount",
                "orderingRule",
                "collectionDigestAlgorithm",
            )
        },
        {
            "documentType": (
                "aetherlink.g2-pion-rung3-execution-failure-evidence-manifest"
            ),
            "schemaVersion": "1.0",
            "manifestId": (
                "g2-pion-ice-v4.3.0-rung3-execution-failure-evidence-manifest-v5"
            ),
            "recordedDate": EXPECTED_DATE,
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
            "artifactScope": (
                "immutable_failed_closed_execution_evidence_with_claim_only_"
                "runtime_read"
            ),
            "artifactCount": 5,
            "orderingRule": "ascending_evidence_id",
            "collectionDigestAlgorithm": (
                "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_"
                "repo_relative_path_newline"
            ),
        },
        "manifest identity",
    )
    require_exact(
        manifest["predecessorManifestBinding"],
        EXPECTED_PREDECESSOR_BINDING,
        "manifest predecessor",
    )
    require(type(manifest["artifacts"]) is list, "manifest artifacts must be list")
    require(len(manifest["artifacts"]) == len(ARTIFACT_ROWS), "manifest row count mismatch")
    for artifact, expected in zip(manifest["artifacts"], ARTIFACT_ROWS):
        row = require_exact_keys(
            artifact, {"evidenceId", "path", "sha256", "role"}, "manifest artifact"
        )
        evidence_id, path, role, pinned = expected
        require_exact(
            (row["evidenceId"], row["path"], row["role"]),
            (evidence_id, path, role),
            f"manifest {evidence_id} identity",
        )
        require_digest(row["sha256"], f"manifest {evidence_id} digest")
        actual = sha256_bytes(reader.read(path))
        require(row["sha256"] == actual, f"manifest {evidence_id} actual digest mismatch")
        if pinned is not None:
            require(row["sha256"] == pinned, f"manifest {evidence_id} pin mismatch")
    require_digest(manifest["collectionSha256"], "manifest collection digest")
    require(
        manifest["collectionSha256"] == collection_sha256(manifest["artifacts"]),
        "manifest collection digest mismatch",
    )
    require_exact(
        manifest["failureBoundary"],
        {
            "permitVersionOneConsumed": True,
            "automaticRetryAllowed": False,
            "completed": False,
            "archiveRejectedBeforeSourceDecode": True,
            "sourceObservationCount": 0,
            "reportPublicationCount": 0,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "manifest failure boundary",
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
        },
        "manifest trust boundary",
    )


def validate_predecessors(reader: SafeTrackedReader) -> None:
    _, permit = verify_pinned_json(
        reader,
        PERMIT_PATH,
        EXPECTED_PERMIT_RAW_SHA256,
        EXPECTED_PERMIT_SEMANTIC_SHA256,
    )
    require(
        type(permit) is dict
        and permit.get("permitId")
        == "g2-pion-ice-v4.3.0-offline-source-review-execution-permit-v1",
        "permit identity mismatch",
    )
    _, predecessor = verify_pinned_json(
        reader,
        PREDECESSOR_MANIFEST_PATH,
        EXPECTED_PREDECESSOR_MANIFEST_RAW_SHA256,
        EXPECTED_PREDECESSOR_MANIFEST_SEMANTIC_SHA256,
    )
    require(
        type(predecessor) is dict
        and predecessor.get("collectionSha256")
        == EXPECTED_PREDECESSOR_MANIFEST_COLLECTION_SHA256,
        "predecessor manifest collection mismatch",
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


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    require(
        HEX_SHA256.fullmatch(EXPECTED_CHECKER_TEST_RAW_SHA256) is not None,
        "checker test digest placeholder unresolved",
    )
    reader = SafeTrackedReader(root)
    failure_raw, failure = verify_pinned_json(
        reader,
        FAILURE_PATH,
        EXPECTED_FAILURE_RAW_SHA256,
        EXPECTED_FAILURE_SEMANTIC_SHA256,
    )
    progress_raw, progress = verify_pinned_json(
        reader,
        PROGRESS_PATH,
        EXPECTED_PROGRESS_RAW_SHA256,
        EXPECTED_PROGRESS_SEMANTIC_SHA256,
    )
    supersession_raw, supersession = verify_pinned_json(
        reader,
        SUPERSESSION_PATH,
        EXPECTED_SUPERSESSION_RAW_SHA256,
        EXPECTED_SUPERSESSION_SEMANTIC_SHA256,
    )
    manifest = reader.json(MANIFEST_PATH)
    unresolved: list[str] = []
    for label, document in (
        ("failure", failure),
        ("progress", progress),
        ("supersession", supersession),
        ("manifest", manifest),
    ):
        unresolved.extend(unresolved_placeholders(document, label))
    require(not unresolved, f"unresolved artifact placeholders: {', '.join(unresolved)}")
    validate_failure(failure)
    validate_progress(progress)
    validate_supersession(supersession)
    validate_predecessors(reader)
    validate_manifest(manifest, reader)
    runtime = SafeClaimObservationReader(root).inspect()
    return {
        "failureId": failure["failureId"],
        "status": failure["status"],
        "result": failure["result"],
        "nextAction": failure["nextAction"],
        "failureRawSha256": sha256_bytes(failure_raw),
        "progressRawSha256": sha256_bytes(progress_raw),
        "supersessionRawSha256": sha256_bytes(supersession_raw),
        **runtime,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        result = validate_repository()
    except CheckError as error:
        print(
            json.dumps(
                {"status": "failed", "error": str(error)},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": "passed",
                **result,
                "claimReadByChecker": True,
                "archiveOpenByChecker": False,
                "archiveReadByChecker": False,
                "archiveStatByChecker": False,
                "buildDirectoryEnumerated": False,
                "interactiveRunnerObservationIndependentlyReproduced": False,
                "completed": False,
                "repositoryOwnerAuthenticationRequired": False,
                "externalIdentityProofRequired": False,
                "userActionRequired": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
