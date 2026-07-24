#!/usr/bin/env python3
"""Verification-only audit of the G2 wave-one review byte readback.

The checker has no record mode and performs no writes.  It independently holds
and validates the original and two recovery decisions, preserved v1 and v2
failed-attempt chains, v3 permit, v3 review claim/result/manifest, all
permit-bound tools, and the three v3 readback publications.  It never opens an
archive, invokes the runner, executes source, starts a subprocess, or uses the
network.
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
            "dependency source-review readback verifier requires "
            "unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Mapping, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = f"{BASE}/bounded-dependency-source-review-wave1-decision-v1.json"
V1_RECOVERY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-recovery-decision-v1.json"
)
RECOVERY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-recovery-decision-v2.json"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v3.json"
)
REVIEW_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v3.claim"
)
RESULT_PATH = f"{BASE}/bounded-dependency-source-review-wave1-result-v3.json"
FAILURE_PATH = f"{BASE}/bounded-dependency-source-review-wave1-failure-v3.json"
REVIEW_MANIFEST_PATH = (
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
V1_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v1.json"
)
V1_REVIEW_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v1.claim"
)
V1_RESULT_PATH = f"{BASE}/bounded-dependency-source-review-wave1-result-v1.json"
V1_FAILURE_PATH = f"{BASE}/bounded-dependency-source-review-wave1-failure-v1.json"
V1_REVIEW_MANIFEST_PATH = (
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
V2_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v2.json"
)
V2_REVIEW_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v2.claim"
)
V2_RESULT_PATH = f"{BASE}/bounded-dependency-source-review-wave1-result-v2.json"
V2_FAILURE_PATH = f"{BASE}/bounded-dependency-source-review-wave1-failure-v2.json"
V2_REVIEW_MANIFEST_PATH = (
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
RECORD_TOOL_PATH = (
    "script/record_p2p_nat_g2_pion_dependency_source_review_wave1_readback_v1.py"
)
RECORD_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_readback_v1.py"
)
VERIFY_TOOL_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_source_review_wave1_readback_v1.py"
)
VERIFY_TESTS_PATH = (
    "script/test_check_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_readback_v1.py"
)

PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "execution-permit-v3"
)
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-decision-v1"
)
V1_RECOVERY_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "recovery-decision-v1"
)
V1_RECOVERY_DECISION_STATUS = (
    "dependency_source_review_wave1_v1_failure_read_back_v2_recovery_"
    "design_selected_execution_not_authorized"
)
RECOVERY_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "recovery-decision-v2"
)
RECOVERY_DECISION_STATUS = (
    "dependency_source_review_wave1_v2_failure_read_back_v3_recovery_"
    "design_selected_execution_not_authorized"
)
V1_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "execution-permit-v1"
)
V1_REVIEW_ID = "g2-pion-ice-v4.3.0-dependency-source-review-wave1-v1"
V2_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "execution-permit-v2"
)
V2_REVIEW_ID = "g2-pion-ice-v4.3.0-dependency-source-review-wave1-v2"
REVIEW_ID = "g2-pion-ice-v4.3.0-dependency-source-review-wave1-v3"
READBACK_ID = (
    "g2-pion-ice-v4.3.0-dependency-source-review-wave1-readback-v3"
)
READBACK_MANIFEST_ID = f"{READBACK_ID}-manifest"
V1_RECOVERY_DECISION_RAW_SHA256 = (
    "1140a718344017895557c304ef24658af325a98b9334606eeb38e85e3e603272"
)
V1_RECOVERY_DECISION_CONTENT_SHA256 = (
    "3d050549c9632dd2d2f57ed329b47cf4526db981e490015017dbda357c2275e3"
)
RECOVERY_DECISION_RAW_SHA256 = (
    "07b695c05dd5e26fff47ed97c7a41992325709c6ed2736543889971250543c28"
)
RECOVERY_DECISION_CONTENT_SHA256 = (
    "b2f2d102b4e5b9f5debed8b72b3f19098a2228e39d3a2e0b1ac980c57d6a4bd1"
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
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_SAFE_INTEGER = (1 << 63) - 1

TOOL_PATHS = {
    "decision_checker": (
        "script/check_p2p_nat_g2_pion_dependency_source_review_"
        "wave1_decision_v1.py"
    ),
    "decision_checker_tests": (
        "script/test_p2p_nat_g2_pion_dependency_source_review_"
        "wave1_decision_v1.py"
    ),
    "review_runner": (
        "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
    ),
    "review_runner_tests": (
        "script/test_run_p2p_nat_g2_pion_dependency_source_review_"
        "wave1_once.py"
    ),
    "permit_checker": (
        "script/check_p2p_nat_g2_pion_dependency_source_review_"
        "wave1_execution_permit_v1.py"
    ),
    "permit_checker_tests": (
        "script/test_p2p_nat_g2_pion_dependency_source_review_"
        "wave1_execution_permit_v1.py"
    ),
    "readback_recorder": RECORD_TOOL_PATH,
    "readback_recorder_tests": RECORD_TESTS_PATH,
    "readback_checker": VERIFY_TOOL_PATH,
    "readback_checker_tests": VERIFY_TESTS_PATH,
}

GRAPH_RECONSTRUCTION_FIELDS = (
    "selectedVersions",
    "nodes",
    "edges",
    "moduleNodes",
    "moduleEdges",
    "exactFrontier",
    "unmappedExternalImports",
    "unresolvedDeclaredExternalImports",
)

ROUTES = {
    "new_tuple_wave_required": {
        "resultStatus": "wave1_graph_discovery_complete_new_wave_required",
        "resultNextAction": (
            "run_separate_dependency_source_review_wave1_independent_readback"
        ),
        "postReadbackNextAction": (
            "prepare_separate_versioned_dependency_wave2_identity_and_"
            "acquisition_decision"
        ),
        "receiptStatus": (
            "dependency_source_review_wave1_readback_complete_"
            "new_tuple_wave_required_manifest_pending"
        ),
        "receiptResult": (
            "held_byte_and_graph_projection_readback_complete_"
            "new_tuple_wave_required"
        ),
        "receiptNextAction": (
            "prepare_separate_versioned_dependency_wave2_identity_and_"
            "acquisition_decision"
        ),
        "manifestStatus": (
            "dependency_source_review_wave1_readback_published_"
            "new_tuple_wave_required"
        ),
        "manifestResult": (
            "independent_readback_receipt_published_then_manifest_written_last_"
            "new_tuple_wave_required"
        ),
        "manifestNextAction": (
            "prepare_separate_versioned_dependency_wave2_identity_and_"
            "acquisition_decision"
        ),
    },
    "external_import_resolution_required": {
        "resultStatus": (
            "wave1_graph_discovery_complete_external_import_"
            "resolution_required"
        ),
        "resultNextAction": (
            "run_separate_dependency_source_review_wave1_independent_readback"
        ),
        "postReadbackNextAction": (
            "resolve_unmapped_and_declared_external_package_imports"
        ),
        "receiptStatus": (
            "dependency_source_review_wave1_readback_complete_external_"
            "import_resolution_required_manifest_pending"
        ),
        "receiptResult": (
            "held_byte_and_graph_projection_readback_complete_external_"
            "import_resolution_required"
        ),
        "receiptNextAction": "resolve_unmapped_and_declared_external_package_imports",
        "manifestStatus": (
            "dependency_source_review_wave1_readback_published_external_"
            "import_resolution_required"
        ),
        "manifestResult": (
            "independent_readback_receipt_published_then_manifest_written_last_"
            "external_import_resolution_required"
        ),
        "manifestNextAction": "resolve_unmapped_and_declared_external_package_imports",
    },
    "fixed_point_candidate": {
        "resultStatus": (
            "wave1_graph_discovery_complete_fixed_point_candidate_"
            "pending_independent_readback"
        ),
        "resultNextAction": (
            "run_separate_dependency_source_review_wave1_independent_readback"
        ),
        "postReadbackNextAction": (
            "prepare_dependency_source_review_wave1_fixed_point_"
            "closure_decision"
        ),
        "receiptStatus": (
            "dependency_source_review_wave1_readback_complete_"
            "fixed_point_candidate_manifest_pending"
        ),
        "receiptResult": (
            "held_byte_and_graph_projection_readback_complete_"
            "fixed_point_candidate"
        ),
        "receiptNextAction": (
            "prepare_dependency_source_review_wave1_fixed_point_"
            "closure_decision"
        ),
        "manifestStatus": (
            "dependency_source_review_wave1_readback_published_"
            "fixed_point_candidate"
        ),
        "manifestResult": (
            "independent_readback_receipt_published_then_manifest_written_last_"
            "fixed_point_candidate"
        ),
        "manifestNextAction": (
            "prepare_dependency_source_review_wave1_fixed_point_"
            "closure_decision"
        ),
    },
}


class VerificationError(RuntimeError):
    """A content-free, fail-closed verification error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def reject_float(_: str) -> Any:
    raise VerificationError("floating-point JSON value")


def reject_constant(_: str) -> Any:
    raise VerificationError("non-finite JSON value")


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "duplicate JSON key")
        result[key] = value
    return result


def validate_json_value(value: Any) -> None:
    if value is None or type(value) in {bool, str}:
        return
    if type(value) is int:
        require(
            -MAXIMUM_SAFE_INTEGER <= value <= MAXIMUM_SAFE_INTEGER,
            "JSON integer outside bound",
        )
        return
    if type(value) is list:
        for child in value:
            validate_json_value(child)
        return
    if type(value) is dict:
        for key, child in value.items():
            require(type(key) is str, "non-string JSON key")
            validate_json_value(child)
        return
    raise VerificationError("unsupported JSON type")


def strict_json(raw: bytes, label: str) -> dict[str, Any]:
    require(0 < len(raw) <= MAXIMUM_JSON_BYTES, f"{label}: byte bound")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=strict_object,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label}: strict JSON") from error
    validate_json_value(value)
    require(type(value) is dict, f"{label}: object required")
    return value


def require_exact_keys(
    value: Mapping[str, Any], keys: set[str], label: str
) -> None:
    require(set(value) == keys, f"{label}: exact keys")


def validate_content_binding(
    document: Mapping[str, Any],
    raw: bytes,
    scope: str,
    label: str,
    *,
    canonical_raw_required: bool = True,
) -> str:
    if canonical_raw_required:
        require(
            raw == canonical_json_bytes(document),
            f"{label}: canonical bytes",
        )
    binding = document.get("contentBinding")
    require(type(binding) is dict, f"{label}: content binding")
    require_exact_keys(
        binding,
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label} content binding",
    )
    without = dict(document)
    without.pop("contentBinding", None)
    expected = digest(without)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": scope,
            "sha256": expected,
        },
        f"{label}: content binding mismatch",
    )
    return expected


def content_bound(value: Mapping[str, Any], scope: str) -> dict[str, Any]:
    result = dict(value)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": digest(value),
    }
    return result


def exact_int(value: Any, label: str) -> int:
    require(
        type(value) is int and 0 <= value <= MAXIMUM_SAFE_INTEGER,
        f"{label}: bounded integer",
    )
    return value


def safe_relative_path(value: Any) -> str:
    require(type(value) is str and bool(value), "unsafe path")
    require(
        value == unicodedata.normalize("NFC", value)
        and "\\" not in value
        and "\x00" not in value
        and not value.startswith("/")
        and len(value.encode("utf-8")) <= 1024,
        "unsafe path",
    )
    parts = PurePosixPath(value).parts
    require(
        bool(parts)
        and all(part not in {"", ".", ".."} for part in parts),
        "unsafe path",
    )
    return value


def identity(info: os.stat_result) -> tuple[int, ...]:
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


class HeldFile:
    def __init__(
        self,
        root_fd: int,
        relative: str,
        *,
        maximum_bytes: int,
        owner_only: bool,
    ) -> None:
        self.relative = safe_relative_path(relative)
        self.maximum_bytes = maximum_bytes
        self.owner_only = owner_only
        self.directory_fds: list[tuple[int, os.stat_result, int, str]] = []
        self.fd = -1
        self.parent_fd = -1
        current = os.dup(root_fd)
        try:
            for component in self.relative.split("/")[:-1]:
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
                require(
                    stat.S_ISDIR(info.st_mode)
                    and info.st_uid in {0, os.geteuid()}
                    and stat.S_IMODE(info.st_mode) & 0o022 == 0,
                    f"{relative}: unsafe ancestor",
                )
                self.directory_fds.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = relative.rsplit("/", 1)[-1]
            self.fd = os.open(
                self.name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=current,
            )
            self.initial = os.fstat(self.fd)
            self._validate(self.initial)
        except BaseException:
            self.close()
            raise

    def _validate(self, info: os.stat_result) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and 0 < info.st_size <= self.maximum_bytes,
            f"{self.relative}: unsafe identity",
        )
        if self.owner_only:
            require(
                stat.S_IMODE(info.st_mode) == 0o600,
                f"{self.relative}: owner-only mode",
            )
        else:
            require(
                stat.S_IMODE(info.st_mode) & 0o022 == 0,
                f"{self.relative}: writable input",
            )

    def read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), f"{self.relative}: short read")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", f"{self.relative}: grew")
        require(
            identity(before) == identity(os.fstat(self.fd)),
            f"{self.relative}: changed during read",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        named = os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
        require(
            identity(os.fstat(self.fd)) == identity(self.initial)
            and identity(named) == identity(self.initial),
            f"{self.relative}: final-name replacement",
        )
        for child, initial, parent, component in self.directory_fds:
            named_dir = os.stat(
                component, dir_fd=parent, follow_symlinks=False
            )
            require(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                and directory_identity(named_dir)
                == directory_identity(initial),
                f"{self.relative}: ancestor replacement",
            )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directory_fds):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directory_fds.clear()
        if self.parent_fd >= 0 and self.parent_fd not in seen:
            os.close(self.parent_fd)
        self.parent_fd = -1


def path_kind(root_fd: int, relative: str) -> str:
    relative = safe_relative_path(relative)
    current = os.dup(root_fd)
    opened: list[int] = []
    try:
        for component in relative.split("/")[:-1]:
            child = os.open(
                component,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=current,
            )
            opened.append(current)
            current = child
        name = relative.rsplit("/", 1)[-1]
        normalized = unicodedata.normalize("NFC", name).casefold()
        matches = [
            existing
            for existing in os.listdir(current)
            if unicodedata.normalize("NFC", existing).casefold() == normalized
        ]
        if not matches:
            return "absent"
        require(matches == [name], f"{relative}: casefold collision")
        info = os.stat(name, dir_fd=current, follow_symlinks=False)
        return "file" if stat.S_ISREG(info.st_mode) else "other"
    except FileNotFoundError:
        return "absent"
    finally:
        os.close(current)
        for fd in reversed(opened):
            os.close(fd)


def no_auth(value: Mapping[str, Any], label: str) -> None:
    for field in (
        "repositoryOwnerIdentityProofRequired",
        "externalAuthenticationRequired",
        "executionPermitAuthenticationRequired",
        "privateKeyRequired",
        "tokenRequired",
        "passwordRequired",
        "signatureRequired",
        "credentialsAllowed",
        "userActionRequired",
        "productEndpointAuthenticationEvaluatedByThisPermit",
        "productEndpointAuthenticationEvaluatedByThisReview",
        "productEndpointAuthenticationEvaluatedByThisReadback",
        "productEndpointAuthenticationUserInputRequiredForThisPermit",
        "productEndpointAuthenticationUserInputRequiredForThisReview",
        "productEndpointAuthenticationUserInputRequiredForThisReadback",
    ):
        if field in value:
            require(value[field] is False, f"{label}: {field}")
    for field in (
        "productEndpointAuthenticationIsSeparateRuntimeInvariant",
        "productEndpointAuthenticationRemainsSeparateRuntimeInvariant",
    ):
        if field in value:
            require(value[field] is True, f"{label}: {field}")


def expected_readback_contract() -> dict[str, Any]:
    return {
        "claimPath": READBACK_CLAIM_PATH,
        "receiptPath": READBACK_RECEIPT_PATH,
        "manifestPath": READBACK_MANIFEST_PATH,
        "recordToolPath": RECORD_TOOL_PATH,
        "recordTestsPath": RECORD_TESTS_PATH,
        "verificationOnlyToolPath": VERIFY_TOOL_PATH,
        "verificationOnlyTestsPath": VERIFY_TESTS_PATH,
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
    }


def validate_permit(
    permit: Mapping[str, Any], raw: bytes
) -> tuple[str, list[dict[str, str]]]:
    content_sha = validate_content_binding(
        permit, raw, "permit_without_contentBinding", "permit"
    )
    require(
        permit.get("documentType")
        == (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "execution-permit"
        )
        and permit.get("schemaVersion") == "1.0"
        and permit.get("permitId") == PERMIT_ID
        and permit.get("status")
        == "dependency_source_review_wave1_execution_authorized_not_consumed",
        "permit identity",
    )
    require(
        permit.get("independentReadbackContract")
        == expected_readback_contract(),
        "permit readback contract",
    )
    decision_binding = permit.get("decisionBinding")
    require(
        type(decision_binding) is dict
        and decision_binding.get("path") == DECISION_PATH
        and decision_binding.get("decisionId") == DECISION_ID,
        "permit decision binding",
    )
    recovery_binding = permit.get("recoveryDecisionBinding")
    require(
        type(recovery_binding) is dict
        and set(recovery_binding)
        == {
            "path",
            "rawSha256",
            "contentSha256",
            "decisionId",
            "requiredStatus",
        }
        and recovery_binding.get("path") == RECOVERY_DECISION_PATH
        and recovery_binding.get("decisionId") == RECOVERY_DECISION_ID
        and recovery_binding.get("requiredStatus") == RECOVERY_DECISION_STATUS,
        "permit recovery decision binding",
    )
    prior_recovery_binding = permit.get("priorRecoveryDecisionBinding")
    require(
        type(prior_recovery_binding) is dict
        and set(prior_recovery_binding)
        == {
            "path",
            "rawSha256",
            "contentSha256",
            "decisionId",
        }
        and prior_recovery_binding.get("path") == V1_RECOVERY_DECISION_PATH
        and prior_recovery_binding.get("decisionId")
        == V1_RECOVERY_DECISION_ID,
        "permit prior recovery decision binding",
    )
    one_use = permit.get("oneUseConsumption")
    result_contract = permit.get("resultContract")
    manifest_contract = permit.get("manifestContract")
    require(
        type(one_use) is dict
        and one_use.get("claimPath") == REVIEW_CLAIM_PATH
        and one_use.get("secondExecutionAllowed") is False
        and type(result_contract) is dict
        and result_contract.get("resultPath") == RESULT_PATH
        and result_contract.get("failurePath") == FAILURE_PATH
        and type(manifest_contract) is dict
        and manifest_contract.get("manifestPath") == REVIEW_MANIFEST_PATH
        and manifest_contract.get("independentReadbackRequired") is True,
        "permit review paths",
    )
    no_auth(permit.get("personalProjectBoundary", {}), "permit no-auth")
    authority = permit.get("authority")
    require(type(authority) is dict, "permit authority")
    for field in (
        "networkAuthorized",
        "socketAuthorized",
        "dnsAuthorized",
        "shellOrSubprocessAuthorized",
        "reviewedSourceLoadOrExecutionAuthorized",
        "sourceMaterializationAuthorized",
        "filesystemExtractionAuthorized",
        "gitWriteAuthorized",
    ):
        require(authority.get(field) is False, f"permit authority {field}")
    tools = permit.get("toolBindings")
    require(type(tools) is list, "permit tools")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in tools:
        require(type(row) is dict, "permit tool row")
        require_exact_keys(row, {"role", "path", "rawSha256"}, "permit tool row")
        role = row.get("role")
        path = row.get("path")
        raw_sha = row.get("rawSha256")
        require(
            type(role) is str
            and role in TOOL_PATHS
            and role not in seen
            and path == TOOL_PATHS[role]
            and type(raw_sha) is str
            and len(raw_sha) == 64,
            "permit tool identity",
        )
        seen.add(role)
        result.append({"role": role, "path": path, "rawSha256": raw_sha})
    require(seen == set(TOOL_PATHS), "permit exact tool set")
    result.sort(key=lambda row: (row["role"], row["path"]))
    return content_sha, result


def rows(
    graph: Mapping[str, Any], field: str, keys: set[str]
) -> list[dict[str, Any]]:
    value = graph.get(field)
    require(
        type(value) is list and all(type(row) is dict for row in value),
        f"graph {field}",
    )
    result = [dict(row) for row in value]
    for row in result:
        require_exact_keys(row, keys, f"graph {field} row")
    return result


def sorted_unique(
    value: list[dict[str, Any]], fields: tuple[str, ...], label: str
) -> None:
    keys = [tuple(row[field] for field in fields) for row in value]
    require(keys == sorted(keys) and len(keys) == len(set(keys)), label)


def validate_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        graph,
        {
            "algorithm",
            "versionSpecificVertexTraversal",
            "nodes",
            "edges",
            "moduleNodes",
            "moduleEdges",
            "selectedVersions",
            "exactFrontier",
            "newlyReachableTuples",
            "unmappedExternalImports",
            "unresolvedDeclaredExternalImports",
            "nodeSetSha256",
            "edgeSetSha256",
            "moduleNodeSetSha256",
            "moduleEdgeSetSha256",
            "moduleGraphAndFrontierSha256",
            "reconstructionProjectionSha256",
            "unmappedExternalImportSetSha256",
            "unresolvedDeclaredExternalImportSetSha256",
            "graphSha256",
            "graphNodeCount",
            "graphEdgeCount",
            "moduleNodeCount",
            "moduleEdgeCount",
            "newTupleCount",
            "unmappedExternalImportCount",
            "unresolvedDeclaredExternalImportCount",
            "fixedPointReached",
            "independentReproductionPassed",
            "reconstructionCount",
            "reconstructions",
        },
        "graph schema",
    )
    require(
        graph.get("algorithm") == "go1.24_mvs_profile_union_fixed_point_v1"
        and graph.get("versionSpecificVertexTraversal") is True,
        "graph algorithm",
    )
    selected = rows(graph, "selectedVersions", {"module", "version"})
    nodes = rows(graph, "nodes", {"profileId", "module", "package"})
    edges = rows(
        graph,
        "edges",
        {
            "profileId",
            "fromPackage",
            "importPath",
            "targetModule",
            "targetVersion",
            "edgeClass",
        },
    )
    module_nodes = rows(
        graph,
        "moduleNodes",
        {
            "module",
            "version",
            "isRoot",
            "sourceAvailable",
            "frontier",
            "selectedForModule",
        },
    )
    module_edges = rows(
        graph,
        "moduleEdges",
        {
            "fromModule",
            "fromVersion",
            "requiredModule",
            "requestedVersion",
            "selectedVersion",
            "targetSourceAvailable",
        },
    )
    frontier = rows(
        graph,
        "exactFrontier",
        {
            "module",
            "version",
            "selectedByGraphAlgorithm",
            "requiresSeparateWaveDecision",
            "acquisitionAuthorized",
        },
    )
    newly = rows(
        graph,
        "newlyReachableTuples",
        {
            "module",
            "version",
            "selectedByGraphAlgorithm",
            "requiresSeparateWaveDecision",
            "acquisitionAuthorized",
        },
    )
    unmapped = rows(
        graph,
        "unmappedExternalImports",
        {"profileId", "fromPackage", "importPath"},
    )
    declared = rows(
        graph,
        "unresolvedDeclaredExternalImports",
        {
            "profileId",
            "fromPackage",
            "importPath",
            "targetModule",
            "targetVersion",
        },
    )
    sorted_unique(selected, ("module", "version"), "selected order")
    sorted_unique(nodes, ("profileId", "module", "package"), "node order")
    sorted_unique(
        edges, ("profileId", "fromPackage", "importPath"), "edge order"
    )
    sorted_unique(module_nodes, ("module", "version"), "module node order")
    sorted_unique(
        module_edges,
        ("fromModule", "fromVersion", "requiredModule", "requestedVersion"),
        "module edge order",
    )
    sorted_unique(frontier, ("module", "version"), "frontier order")
    sorted_unique(
        unmapped, ("profileId", "fromPackage", "importPath"), "unmapped order"
    )
    sorted_unique(
        declared,
        (
            "profileId",
            "fromPackage",
            "importPath",
            "targetModule",
            "targetVersion",
        ),
        "declared order",
    )
    for row in module_nodes:
        require(
            all(
                type(row[field]) is bool
                for field in (
                    "isRoot",
                    "sourceAvailable",
                    "frontier",
                    "selectedForModule",
                )
            )
            and row["frontier"] is (not row["sourceAvailable"]),
            "module node booleans",
        )
    expected_selected = [
        {"module": row["module"], "version": row["version"]}
        for row in module_nodes
        if row["selectedForModule"]
    ]
    require(selected == expected_selected, "selected projection")
    selected_map = {row["module"]: row["version"] for row in selected}
    require(
        len(selected_map) == len(selected)
        and set(selected_map) == {row["module"] for row in module_nodes},
        "selected module coverage",
    )
    available = {
        (row["module"], row["version"])
        for row in module_nodes
        if row["sourceAvailable"]
    }
    for row in module_edges:
        require(
            row["selectedVersion"] == selected_map.get(row["requiredModule"])
            and type(row["targetSourceAvailable"]) is bool
            and row["targetSourceAvailable"]
            is (
                (row["requiredModule"], row["requestedVersion"]) in available
            ),
            "module edge projection",
        )
    expected_frontier = [
        {
            "module": row["module"],
            "version": row["version"],
            "selectedByGraphAlgorithm": row["selectedForModule"],
            "requiresSeparateWaveDecision": True,
            "acquisitionAuthorized": False,
        }
        for row in module_nodes
        if row["frontier"]
    ]
    require(frontier == newly == expected_frontier, "frontier projection")
    expected_unmapped = [
        {
            "profileId": row["profileId"],
            "fromPackage": row["fromPackage"],
            "importPath": row["importPath"],
        }
        for row in edges
        if row["edgeClass"] == "unmapped_external"
    ]
    expected_declared = [
        {
            "profileId": row["profileId"],
            "fromPackage": row["fromPackage"],
            "importPath": row["importPath"],
            "targetModule": row["targetModule"],
            "targetVersion": row["targetVersion"],
        }
        for row in edges
        if row["edgeClass"] == "declared_external"
    ]
    require(
        unmapped == expected_unmapped and declared == expected_declared,
        "external projection",
    )
    counts = {
        "graphNodeCount": len(nodes),
        "graphEdgeCount": len(edges),
        "moduleNodeCount": len(module_nodes),
        "moduleEdgeCount": len(module_edges),
        "newTupleCount": len(frontier),
        "unmappedExternalImportCount": len(unmapped),
        "unresolvedDeclaredExternalImportCount": len(declared),
    }
    for field, expected in counts.items():
        require(exact_int(graph.get(field), field) == expected, field)
    fixed = not frontier and not unmapped and not declared
    require(
        type(graph.get("fixedPointReached")) is bool
        and graph.get("fixedPointReached") is fixed,
        "fixed-point derivation",
    )
    projection = {
        field: graph[field] for field in GRAPH_RECONSTRUCTION_FIELDS
    }
    projection_sha = digest(projection)
    module_sha = digest(
        {
            "selectedVersions": selected,
            "moduleNodes": module_nodes,
            "moduleEdges": module_edges,
            "exactFrontier": frontier,
        }
    )
    expected_digests = {
        "nodeSetSha256": digest(nodes),
        "edgeSetSha256": digest(edges),
        "moduleNodeSetSha256": digest(module_nodes),
        "moduleEdgeSetSha256": digest(module_edges),
        "moduleGraphAndFrontierSha256": module_sha,
        "reconstructionProjectionSha256": projection_sha,
        "unmappedExternalImportSetSha256": digest(unmapped),
        "unresolvedDeclaredExternalImportSetSha256": digest(declared),
        "graphSha256": projection_sha,
    }
    for field, expected in expected_digests.items():
        require(graph.get(field) == expected, f"graph digest {field}")
    reconstructions = graph.get("reconstructions")
    require(
        graph.get("independentReproductionPassed") is True
        and graph.get("reconstructionCount") == 2
        and type(reconstructions) is list
        and len(reconstructions) == 2,
        "reconstruction count",
    )
    algorithms = (
        "version_vertex_breadth_first_search",
        "version_vertex_monotone_full_set_scan",
    )
    for index, row in enumerate(reconstructions):
        require(
            row
            == {
                "algorithm": algorithms[index],
                "nodeSetSha256": digest(nodes),
                "edgeSetSha256": digest(edges),
                "moduleGraphAndFrontierSha256": module_sha,
                "reconstructionSha256": projection_sha,
            },
            "reconstruction equality",
        )
    route = (
        "new_tuple_wave_required"
        if frontier
        else (
            "external_import_resolution_required"
            if unmapped or declared
            else "fixed_point_candidate"
        )
    )
    return {
        "route": route,
        **counts,
        "selectedVersionCount": len(selected),
        "fixedPointCandidate": fixed,
        "graphSha256": projection_sha,
        "moduleGraphAndFrontierSha256": module_sha,
        "reconstructionProjectionSha256": projection_sha,
        "reconstructionAlgorithms": list(algorithms),
    }


def validate_decision(raw: bytes) -> tuple[dict[str, Any], str]:
    value = strict_json(raw, "decision")
    content_sha = validate_content_binding(
        value,
        raw,
        "decision_without_contentBinding",
        "decision",
        canonical_raw_required=False,
    )
    require(
        value.get("documentType")
        == "aetherlink.g2-pion-bounded-dependency-source-review-wave1-decision"
        and value.get("schemaVersion") == "1.0"
        and value.get("decisionId") == DECISION_ID
        and value.get("status")
        == (
            "dependency_source_review_wave1_decision_recorded_"
            "execution_not_authorized"
        ),
        "decision identity",
    )
    no_auth(value.get("nonClaims", {}), "decision no-auth")
    return value, content_sha


def validate_v1_recovery_decision(
    raw: bytes,
) -> tuple[dict[str, Any], str]:
    require(
        sha256_bytes(raw) == V1_RECOVERY_DECISION_RAW_SHA256,
        "historical v1 recovery decision raw SHA-256",
    )
    decision = strict_json(raw, "historical v1 recovery decision")
    content_sha = validate_content_binding(
        decision,
        raw,
        "decision_without_contentBinding",
        "historical v1 recovery decision",
    )
    require(
        content_sha == V1_RECOVERY_DECISION_CONTENT_SHA256,
        "historical v1 recovery decision content SHA-256",
    )
    require_exact_keys(
        decision,
        {
            "authority",
            "closure",
            "contentBinding",
            "decisionBinding",
            "decisionId",
            "documentType",
            "failedAttemptBindings",
            "failedAttemptNamespaceContract",
            "failureCrossBindingContract",
            "nextAction",
            "nonClaims",
            "personalProjectBoundary",
            "recordedDate",
            "result",
            "rootCause",
            "schemaVersion",
            "selectedV2Correction",
            "status",
            "v1PreservationContract",
            "v2NamespaceContract",
        },
        "historical v1 recovery decision",
    )
    require(
        decision.get("documentType")
        == (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "recovery-decision"
        )
        and decision.get("schemaVersion") == "1.0"
        and decision.get("decisionId") == V1_RECOVERY_DECISION_ID
        and decision.get("status") == V1_RECOVERY_DECISION_STATUS
        and decision.get("nextAction")
        == "prepare_separate_dependency_source_review_wave1_execution_permit_v2",
        "historical v1 recovery decision identity",
    )
    no_auth(
        decision.get("personalProjectBoundary", {}),
        "historical v1 recovery decision no-auth",
    )
    authority = decision.get("authority")
    require(type(authority) is dict, "historical v1 recovery authority")
    for field in (
        "archiveMemberInspectionAuthorized",
        "deploymentAuthorized",
        "deviceAuthorized",
        "externalAuthenticationRequired",
        "gitWriteAuthorized",
        "networkAuthorized",
        "repositoryOwnerIdentityProofRequired",
        "reviewExecutionAuthorized",
        "shellOrSubprocessAuthorized",
        "sourceExecutionAuthorized",
        "sourceModificationAuthorized",
        "userActionRequired",
    ):
        require(
            authority.get(field) is False,
            f"historical v1 recovery authority {field}",
        )
    return decision, content_sha


def validate_recovery_decision(raw: bytes) -> tuple[dict[str, Any], str]:
    require(
        sha256_bytes(raw) == RECOVERY_DECISION_RAW_SHA256,
        "recovery decision raw SHA-256",
    )
    decision = strict_json(raw, "recovery decision")
    content_sha = validate_content_binding(
        decision,
        raw,
        "decision_without_contentBinding",
        "recovery decision",
    )
    require(
        content_sha == RECOVERY_DECISION_CONTENT_SHA256,
        "recovery decision content SHA-256",
    )
    require_exact_keys(
        decision,
        {
            "authority",
            "closure",
            "contentBinding",
            "decisionBinding",
            "decisionId",
            "documentType",
            "failedAttemptBindings",
            "failedAttemptNamespaceContracts",
            "failureCrossBindingContracts",
            "nextAction",
            "nonClaims",
            "personalProjectBoundary",
            "priorRecoveryDecisionBinding",
            "recordedDate",
            "result",
            "rootCause",
            "schemaVersion",
            "selectedV3Correction",
            "status",
            "v1PreservationContract",
            "v2PreservationContract",
            "v3NamespaceContract",
        },
        "recovery decision",
    )
    require(
        decision.get("documentType")
        == (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "recovery-decision"
        )
        and decision.get("schemaVersion") == "1.0"
        and decision.get("decisionId") == RECOVERY_DECISION_ID
        and decision.get("status") == RECOVERY_DECISION_STATUS
        and decision.get("nextAction")
        == "prepare_separate_dependency_source_review_wave1_execution_permit_v3",
        "recovery decision identity",
    )
    no_auth(
        decision.get("personalProjectBoundary", {}),
        "recovery decision no-auth",
    )
    authority = decision.get("authority")
    require(type(authority) is dict, "recovery decision authority")
    for field in (
        "archiveMemberInspectionAuthorized",
        "credentialsAllowed",
        "deploymentAuthorized",
        "deviceAuthorized",
        "externalAuthenticationRequired",
        "gitWriteAuthorized",
        "networkAuthorized",
        "passwordRequired",
        "privateKeyRequired",
        "repositoryOwnerIdentityProofRequired",
        "reviewExecutionAuthorized",
        "reviewedSourceModificationAuthorized",
        "shellOrSubprocessAuthorized",
        "signatureRequired",
        "sourceExecutionAuthorized",
        "tokenRequired",
        "userActionRequired",
    ):
        require(authority.get(field) is False, f"recovery authority {field}")
    return decision, content_sha


def validate_v1_permit(raw: bytes) -> tuple[dict[str, Any], str]:
    permit = strict_json(raw, "historical v1 permit")
    content_sha = validate_content_binding(
        permit,
        raw,
        "permit_without_contentBinding",
        "historical v1 permit",
    )
    require(
        permit.get("documentType")
        == (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "execution-permit"
        )
        and permit.get("schemaVersion") == "1.0"
        and permit.get("permitId") == V1_PERMIT_ID
        and permit.get("status")
        == "dependency_source_review_wave1_execution_authorized_not_consumed",
        "historical v1 permit identity",
    )
    no_auth(
        permit.get("personalProjectBoundary", {}),
        "historical v1 permit no-auth",
    )
    return permit, content_sha


def validate_v1_claim(
    claim: Mapping[str, Any],
    raw: bytes,
    permit_content_sha: str,
) -> str:
    content_sha = validate_content_binding(
        claim,
        raw,
        "claim_without_contentBinding",
        "historical v1 claim",
    )
    require_exact_keys(
        claim,
        {
            "automaticRetryAllowed",
            "contentBinding",
            "documentType",
            "externalAuthenticationRequired",
            "permitContentSha256",
            "permitId",
            "productEndpointAuthenticationEvaluatedByThisReview",
            "productEndpointAuthenticationIsSeparateRuntimeInvariant",
            "productEndpointAuthenticationRemainsSeparateRuntimeInvariant",
            "productEndpointAuthenticationUserInputRequiredForThisReview",
            "repositoryOwnerIdentityProofRequired",
            "reviewId",
            "schemaVersion",
            "userActionRequired",
        },
        "historical v1 claim",
    )
    require(
        claim.get("documentType")
        == "aetherlink.g2-pion-dependency-source-review-wave1-one-use-claim"
        and claim.get("schemaVersion") == "1.0"
        and claim.get("permitId") == V1_PERMIT_ID
        and claim.get("permitContentSha256") == permit_content_sha
        and claim.get("reviewId") == V1_REVIEW_ID
        and claim.get("automaticRetryAllowed") is False,
        "historical v1 claim identity",
    )
    no_auth(claim, "historical v1 claim no-auth")
    return content_sha


def validate_v1_failure(
    failure: Mapping[str, Any],
    raw: bytes,
    permit_content_sha: str,
    claim_raw_sha: str,
) -> str:
    content_sha = validate_content_binding(
        failure,
        raw,
        "failure_without_contentBinding",
        "historical v1 failure",
    )
    require_exact_keys(
        failure,
        {
            "automaticRetryAllowed",
            "claimRawSha256",
            "contentBinding",
            "documentType",
            "externalAuthenticationRequired",
            "failedResourceKind",
            "failedTupleId",
            "failedTupleOrder",
            "failureCode",
            "nextAction",
            "partialResultPublished",
            "permitContentSha256",
            "permitId",
            "phase",
            "productEndpointAuthenticationEvaluatedByThisReview",
            "productEndpointAuthenticationIsSeparateRuntimeInvariant",
            "productEndpointAuthenticationUserInputRequiredForThisReview",
            "repositoryOwnerIdentityProofRequired",
            "reviewId",
            "safeNumericObservations",
            "schemaVersion",
            "status",
            "userActionRequired",
        },
        "historical v1 failure",
    )
    require(
        failure.get("documentType")
        == "aetherlink.g2-pion-dependency-source-review-wave1-failure"
        and failure.get("schemaVersion") == "1.0"
        and failure.get("status")
        == "dependency_source_review_wave1_failed_closed"
        and failure.get("permitId") == V1_PERMIT_ID
        and failure.get("permitContentSha256") == permit_content_sha
        and failure.get("reviewId") == V1_REVIEW_ID
        and failure.get("claimRawSha256") == claim_raw_sha
        and failure.get("failureCode") == "E_HELD_SET"
        and failure.get("phase") == "held_set"
        and failure.get("failedTupleId") is None
        and failure.get("failedTupleOrder") is None
        and failure.get("failedResourceKind") is None
        and failure.get("safeNumericObservations") == {}
        and failure.get("partialResultPublished") is False
        and failure.get("automaticRetryAllowed") is False
        and failure.get("nextAction")
        == "prepare_new_versioned_dependency_source_review_wave1_recovery_decision",
        "historical v1 failure identity",
    )
    no_auth(failure, "historical v1 failure no-auth")
    return content_sha


def validate_v2_permit(raw: bytes) -> tuple[dict[str, Any], str]:
    require(
        sha256_bytes(raw) == V2_PERMIT_RAW_SHA256,
        "historical v2 permit raw SHA-256",
    )
    permit = strict_json(raw, "historical v2 permit")
    content_sha = validate_content_binding(
        permit,
        raw,
        "permit_without_contentBinding",
        "historical v2 permit",
    )
    require(
        content_sha == V2_PERMIT_CONTENT_SHA256,
        "historical v2 permit content SHA-256",
    )
    require(
        permit.get("documentType")
        == (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "execution-permit"
        )
        and permit.get("schemaVersion") == "1.0"
        and permit.get("permitId") == V2_PERMIT_ID
        and permit.get("status")
        == "dependency_source_review_wave1_execution_authorized_not_consumed",
        "historical v2 permit identity",
    )
    no_auth(
        permit.get("personalProjectBoundary", {}),
        "historical v2 permit no-auth",
    )
    return permit, content_sha


def validate_v2_claim(
    claim: Mapping[str, Any],
    raw: bytes,
    permit_content_sha: str,
) -> str:
    require(
        sha256_bytes(raw) == V2_CLAIM_RAW_SHA256,
        "historical v2 claim raw SHA-256",
    )
    content_sha = validate_content_binding(
        claim,
        raw,
        "claim_without_contentBinding",
        "historical v2 claim",
    )
    require(
        content_sha == V2_CLAIM_CONTENT_SHA256,
        "historical v2 claim content SHA-256",
    )
    require_exact_keys(
        claim,
        {
            "automaticRetryAllowed",
            "contentBinding",
            "documentType",
            "externalAuthenticationRequired",
            "permitContentSha256",
            "permitId",
            "productEndpointAuthenticationEvaluatedByThisReview",
            "productEndpointAuthenticationIsSeparateRuntimeInvariant",
            "productEndpointAuthenticationRemainsSeparateRuntimeInvariant",
            "productEndpointAuthenticationUserInputRequiredForThisReview",
            "repositoryOwnerIdentityProofRequired",
            "reviewId",
            "schemaVersion",
            "userActionRequired",
        },
        "historical v2 claim",
    )
    require(
        claim.get("documentType")
        == "aetherlink.g2-pion-dependency-source-review-wave1-one-use-claim"
        and claim.get("schemaVersion") == "1.0"
        and claim.get("permitId") == V2_PERMIT_ID
        and claim.get("permitContentSha256") == permit_content_sha
        and claim.get("reviewId") == V2_REVIEW_ID
        and claim.get("automaticRetryAllowed") is False,
        "historical v2 claim identity",
    )
    no_auth(claim, "historical v2 claim no-auth")
    return content_sha


def validate_v2_failure(
    failure: Mapping[str, Any],
    raw: bytes,
    permit_content_sha: str,
    claim_raw_sha: str,
) -> str:
    require(
        sha256_bytes(raw) == V2_FAILURE_RAW_SHA256,
        "historical v2 failure raw SHA-256",
    )
    content_sha = validate_content_binding(
        failure,
        raw,
        "failure_without_contentBinding",
        "historical v2 failure",
    )
    require(
        content_sha == V2_FAILURE_CONTENT_SHA256,
        "historical v2 failure content SHA-256",
    )
    require_exact_keys(
        failure,
        {
            "automaticRetryAllowed",
            "claimRawSha256",
            "contentBinding",
            "documentType",
            "externalAuthenticationRequired",
            "failedResourceKind",
            "failedTupleId",
            "failedTupleOrder",
            "failureCode",
            "nextAction",
            "partialResultPublished",
            "permitContentSha256",
            "permitId",
            "phase",
            "productEndpointAuthenticationEvaluatedByThisReview",
            "productEndpointAuthenticationIsSeparateRuntimeInvariant",
            "productEndpointAuthenticationUserInputRequiredForThisReview",
            "repositoryOwnerIdentityProofRequired",
            "reviewId",
            "safeNumericObservations",
            "schemaVersion",
            "status",
            "userActionRequired",
        },
        "historical v2 failure",
    )
    require(
        failure.get("documentType")
        == "aetherlink.g2-pion-dependency-source-review-wave1-failure"
        and failure.get("schemaVersion") == "1.0"
        and failure.get("status")
        == "dependency_source_review_wave1_failed_closed"
        and failure.get("permitId") == V2_PERMIT_ID
        and failure.get("permitContentSha256") == permit_content_sha
        and failure.get("reviewId") == V2_REVIEW_ID
        and failure.get("claimRawSha256") == claim_raw_sha
        and failure.get("failureCode") == "E_ARCHIVE_STRUCTURE"
        and failure.get("phase") == "archive"
        and failure.get("failedTupleId") == "wave1-010-ec8b158caf64"
        and failure.get("failedTupleOrder") is None
        and failure.get("failedResourceKind") is None
        and failure.get("safeNumericObservations") == {}
        and failure.get("partialResultPublished") is False
        and failure.get("automaticRetryAllowed") is False
        and failure.get("nextAction")
        == "prepare_new_versioned_dependency_source_review_wave1_recovery_decision",
        "historical v2 failure identity",
    )
    no_auth(failure, "historical v2 failure no-auth")
    return content_sha


def expected_v1_absent_paths() -> list[str]:
    return [
        V1_RESULT_PATH,
        V1_REVIEW_MANIFEST_PATH,
        V1_READBACK_CLAIM_PATH,
        V1_READBACK_RECEIPT_PATH,
        V1_READBACK_MANIFEST_PATH,
    ]


def expected_v2_absent_paths() -> list[str]:
    return [
        V2_RESULT_PATH,
        V2_REVIEW_MANIFEST_PATH,
        V2_READBACK_CLAIM_PATH,
        V2_READBACK_RECEIPT_PATH,
        V2_READBACK_MANIFEST_PATH,
    ]


def expected_original_decision_binding(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "path": DECISION_PATH,
        "rawSha256": sha256_bytes(raw[DECISION_PATH]),
        "contentSha256": content_shas[DECISION_PATH],
        "decisionId": DECISION_ID,
        "requiredStatus": (
            "dependency_source_review_wave1_decision_recorded_"
            "execution_not_authorized"
        ),
    }


def expected_recovery_decision_binding(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "path": RECOVERY_DECISION_PATH,
        "rawSha256": sha256_bytes(raw[RECOVERY_DECISION_PATH]),
        "contentSha256": content_shas[RECOVERY_DECISION_PATH],
        "decisionId": RECOVERY_DECISION_ID,
        "requiredStatus": RECOVERY_DECISION_STATUS,
    }


def expected_v1_recovery_decision_binding(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "path": V1_RECOVERY_DECISION_PATH,
        "rawSha256": sha256_bytes(raw[V1_RECOVERY_DECISION_PATH]),
        "contentSha256": content_shas[V1_RECOVERY_DECISION_PATH],
        "decisionId": V1_RECOVERY_DECISION_ID,
        "requiredStatus": V1_RECOVERY_DECISION_STATUS,
    }


def expected_prior_recovery_decision_binding(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    binding = expected_v1_recovery_decision_binding(raw, content_shas)
    binding.pop("requiredStatus")
    return binding


def expected_v1_failed_attempt_namespace_contract() -> dict[str, Any]:
    return {
        "requiredAbsentPaths": expected_v1_absent_paths(),
        "v1ManifestRequiredAbsent": True,
        "v1ReadbackClaimRequiredAbsent": True,
        "v1ReadbackManifestRequiredAbsent": True,
        "v1ReadbackReceiptRequiredAbsent": True,
        "v1ResultRequiredAbsent": True,
    }


def expected_v2_failed_attempt_namespace_contract() -> dict[str, Any]:
    return {
        "requiredAbsentPaths": expected_v2_absent_paths(),
        "v2ManifestRequiredAbsent": True,
        "v2ReadbackClaimRequiredAbsent": True,
        "v2ReadbackManifestRequiredAbsent": True,
        "v2ReadbackReceiptRequiredAbsent": True,
        "v2ResultRequiredAbsent": True,
    }


def expected_v2_namespace_contract() -> dict[str, Any]:
    return {
        "claimPath": V2_REVIEW_CLAIM_PATH,
        "failurePath": V2_FAILURE_PATH,
        "freshOneUseNamespaceRequired": True,
        "manifestPath": V2_REVIEW_MANIFEST_PATH,
        "permitId": V2_PERMIT_ID,
        "permitPath": V2_PERMIT_PATH,
        "readbackClaimPath": V2_READBACK_CLAIM_PATH,
        "readbackManifestPath": V2_READBACK_MANIFEST_PATH,
        "readbackReceiptPath": V2_READBACK_RECEIPT_PATH,
        "resultPath": V2_RESULT_PATH,
        "reuseOfV1ArtifactsAllowed": False,
        "reviewId": V2_REVIEW_ID,
        "stagingDirectoryPrefix": ".wave-1-review-v2-staging-",
    }


def expected_v3_namespace_contract() -> dict[str, Any]:
    return {
        "claimPath": REVIEW_CLAIM_PATH,
        "failurePath": FAILURE_PATH,
        "freshOneUseNamespaceRequired": True,
        "manifestPath": REVIEW_MANIFEST_PATH,
        "permitId": PERMIT_ID,
        "permitPath": PERMIT_PATH,
        "readbackClaimPath": READBACK_CLAIM_PATH,
        "readbackManifestPath": READBACK_MANIFEST_PATH,
        "readbackReceiptPath": READBACK_RECEIPT_PATH,
        "resultPath": RESULT_PATH,
        "reuseOfV1ArtifactsAllowed": False,
        "reuseOfV2ArtifactsAllowed": False,
        "reviewId": REVIEW_ID,
        "stagingDirectoryPrefix": ".wave-1-review-v3-staging-",
    }


def expected_v1_failed_attempt_bindings(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    claim_raw_sha = sha256_bytes(raw[V1_REVIEW_CLAIM_PATH])
    return {
        "permit": {
            "path": V1_PERMIT_PATH,
            "rawSha256": sha256_bytes(raw[V1_PERMIT_PATH]),
            "contentSha256": content_shas[V1_PERMIT_PATH],
            "permitId": V1_PERMIT_ID,
        },
        "claim": {
            "path": V1_REVIEW_CLAIM_PATH,
            "rawSha256": claim_raw_sha,
            "contentSha256": content_shas[V1_REVIEW_CLAIM_PATH],
            "permitId": V1_PERMIT_ID,
            "reviewId": V1_REVIEW_ID,
        },
        "failure": {
            "path": V1_FAILURE_PATH,
            "rawSha256": sha256_bytes(raw[V1_FAILURE_PATH]),
            "contentSha256": content_shas[V1_FAILURE_PATH],
            "permitId": V1_PERMIT_ID,
            "permitContentSha256": content_shas[V1_PERMIT_PATH],
            "reviewId": V1_REVIEW_ID,
            "claimRawSha256": claim_raw_sha,
            "requiredFailureCode": "E_HELD_SET",
            "requiredPhase": "held_set",
        },
    }


def expected_v2_failed_attempt_bindings(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    claim_raw_sha = sha256_bytes(raw[V2_REVIEW_CLAIM_PATH])
    return {
        "permit": {
            "path": V2_PERMIT_PATH,
            "rawSha256": sha256_bytes(raw[V2_PERMIT_PATH]),
            "contentSha256": content_shas[V2_PERMIT_PATH],
            "permitId": V2_PERMIT_ID,
        },
        "claim": {
            "path": V2_REVIEW_CLAIM_PATH,
            "rawSha256": claim_raw_sha,
            "contentSha256": content_shas[V2_REVIEW_CLAIM_PATH],
            "permitId": V2_PERMIT_ID,
            "reviewId": V2_REVIEW_ID,
        },
        "failure": {
            "path": V2_FAILURE_PATH,
            "rawSha256": sha256_bytes(raw[V2_FAILURE_PATH]),
            "contentSha256": content_shas[V2_FAILURE_PATH],
            "permitId": V2_PERMIT_ID,
            "permitContentSha256": content_shas[V2_PERMIT_PATH],
            "reviewId": V2_REVIEW_ID,
            "claimRawSha256": claim_raw_sha,
            "requiredFailureCode": "E_ARCHIVE_STRUCTURE",
            "requiredPhase": "archive",
            "requiredFailedTupleId": "wave1-010-ec8b158caf64",
            "requiredFailedTupleOrder": None,
            "requiredFailedResourceKind": None,
        },
    }


def expected_failed_attempt_bindings(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "v1": expected_v1_failed_attempt_bindings(raw, content_shas),
        "v2": expected_v2_failed_attempt_bindings(raw, content_shas),
    }


def expected_failed_attempt_namespace_contracts() -> dict[str, Any]:
    return {
        "v1": expected_v1_failed_attempt_namespace_contract(),
        "v2": expected_v2_failed_attempt_namespace_contract(),
    }


def expected_v1_preservation_contract() -> dict[str, bool]:
    return {
        "v1AutomaticRetryAllowed": False,
        "v1ClaimDeletionAllowed": False,
        "v1FailureDeletionAllowed": False,
        "v1ManifestBackfillAllowed": False,
        "v1PermitReuseAllowed": False,
        "v1ReadbackBackfillAllowed": False,
        "v1ResultBackfillAllowed": False,
        "v1RunnerRetryAllowed": False,
    }


def expected_v2_preservation_contract() -> dict[str, bool]:
    return {
        "v2AutomaticRetryAllowed": False,
        "v2ClaimDeletionAllowed": False,
        "v2ClaimModificationAllowed": False,
        "v2FailureDeletionAllowed": False,
        "v2FailureModificationAllowed": False,
        "v2ManifestBackfillAllowed": False,
        "v2PermitModificationAllowed": False,
        "v2PermitReuseAllowed": False,
        "v2ReadbackBackfillAllowed": False,
        "v2ResultBackfillAllowed": False,
        "v2RunnerRetryAllowed": False,
    }


def expected_selected_v3_correction() -> dict[str, Any]:
    return {
        "doubleQuoteRuneLiteralSupported": True,
        "escapeAwareSingleQuotedRuneTokenRequired": True,
        "escapedSingleQuoteRuneLiteralSupported": True,
        "missingActiveBindingContextAttachedWithoutChangingCodeOrPhase": True,
        "reviewFailureCaughtBeforeRuntimeError": True,
        "reviewFailureCodePreserved": True,
        "reviewFailurePhasePreserved": True,
        "reviewFailureResourceKindPreserved": True,
        "reviewFailureTupleIdPreserved": True,
        "reviewFailureTupleOrderPreserved": True,
        "runeTokenMaySatisfyImportStringRequirement": False,
        "sourceInventorySkippingAllowed": False,
        "testdataSkippingAllowed": False,
        "unterminatedOrMultilineRuneRejected": True,
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


def validate_v1_recovery_history(
    recovery: Mapping[str, Any],
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> None:
    require(
        recovery.get("decisionBinding")
        == expected_original_decision_binding(raw, content_shas),
        "recovery/original decision binding",
    )
    require(
        recovery.get("failedAttemptBindings")
        == expected_v1_failed_attempt_bindings(raw, content_shas),
        "recovery failed-attempt bindings",
    )
    require(
        recovery.get("failedAttemptNamespaceContract")
        == expected_v1_failed_attempt_namespace_contract(),
        "recovery failed-attempt namespace",
    )
    require(
        recovery.get("failureCrossBindingContract")
        == {
            "automaticRetryAllowed": False,
            "failureClaimRawSha256EqualsV1ClaimRawSha256": True,
            "failureCode": "E_HELD_SET",
            "failurePermitContentSha256EqualsV1PermitContentSha256": True,
            "failurePermitIdEqualsV1PermitId": True,
            "failureReviewIdEqualsV1ClaimReviewId": True,
            "partialResultPublished": False,
            "phase": "held_set",
        },
        "recovery failure cross-binding contract",
    )
    require(
        recovery.get("v1PreservationContract")
        == expected_v1_preservation_contract(),
        "recovery v1 preservation",
    )
    require(
        recovery.get("v2NamespaceContract")
        == expected_v2_namespace_contract(),
        "recovery v2 namespace",
    )
    require(
        recovery.get("selectedV2Correction")
        == {
            "claimAndOutputsPublishedDirectlyThroughHeldParentDescriptors": True,
            "componentWiseNoFollowHeldParentsRequired": True,
            "descendantRetraversalForPublicationAllowed": False,
            "directoryIdentityExcludesLinkCount": True,
            "directoryIdentityFields": [
                "st_dev",
                "st_ino",
                "st_mode",
                "st_uid",
                "st_gid",
            ],
            "directoryLinkCountIsNotStableIdentity": True,
            "finalHeldParentIdentityBarrierRequired": True,
            "heldParentBarrierBeforeAndAfterEachPublicationRequired": True,
            "publicationFlags": [
                "O_WRONLY",
                "O_CREAT",
                "O_EXCL",
                "O_NOFOLLOW",
                "O_CLOEXEC",
            ],
            "publicationUsesHeldParentFdAndBasenameOnly": True,
            "trustedHeldClaimParentRequired": True,
            "trustedHeldOutputParentRequired": True,
        },
        "recovery selected v2 correction",
    )


def validate_recovery_history(
    recovery: Mapping[str, Any],
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> None:
    require(
        recovery.get("decisionBinding")
        == expected_original_decision_binding(raw, content_shas),
        "recovery/original decision binding",
    )
    require(
        recovery.get("priorRecoveryDecisionBinding")
        == expected_prior_recovery_decision_binding(raw, content_shas),
        "recovery/prior recovery decision binding",
    )
    require(
        recovery.get("failedAttemptBindings")
        == expected_failed_attempt_bindings(raw, content_shas),
        "recovery failed-attempt bindings",
    )
    require(
        recovery.get("failedAttemptNamespaceContracts")
        == expected_failed_attempt_namespace_contracts(),
        "recovery failed-attempt namespace contracts",
    )
    require(
        recovery.get("failureCrossBindingContracts")
        == {
            "v1": {
                "automaticRetryAllowed": False,
                "failureClaimRawSha256EqualsV1ClaimRawSha256": True,
                "failureCode": "E_HELD_SET",
                "failurePermitContentSha256EqualsV1PermitContentSha256": True,
                "failurePermitIdEqualsV1PermitId": True,
                "failureReviewIdEqualsV1ClaimReviewId": True,
                "partialResultPublished": False,
                "phase": "held_set",
            },
            "v2": {
                "automaticRetryAllowed": False,
                "failureClaimRawSha256EqualsV2ClaimRawSha256": True,
                "failurePermitContentSha256EqualsV2PermitContentSha256": True,
                "failurePermitIdEqualsV2PermitId": True,
                "failureReviewIdEqualsV2ClaimReviewId": True,
                "partialResultPublished": False,
                "recordedFailedResourceKind": None,
                "recordedFailedTupleId": "wave1-010-ec8b158caf64",
                "recordedFailedTupleOrder": None,
                "recordedFailureCode": "E_ARCHIVE_STRUCTURE",
                "recordedPhase": "archive",
            },
        },
        "recovery failure cross-binding contracts",
    )
    require(
        recovery.get("selectedV3Correction")
        == expected_selected_v3_correction(),
        "recovery selected v3 correction",
    )
    require(
        recovery.get("v1PreservationContract")
        == expected_v1_preservation_contract(),
        "recovery v1 preservation",
    )
    require(
        recovery.get("v2PreservationContract")
        == expected_v2_preservation_contract(),
        "recovery v2 preservation",
    )
    require(
        recovery.get("v3NamespaceContract") == expected_v3_namespace_contract(),
        "recovery v3 namespace",
    )


def validate_review_claim(
    value: Mapping[str, Any], raw: bytes, permit_content_sha: str
) -> str:
    content_sha = validate_content_binding(
        value, raw, "claim_without_contentBinding", "review claim"
    )
    require_exact_keys(
        value,
        {
            "documentType",
            "schemaVersion",
            "permitId",
            "permitContentSha256",
            "reviewId",
            "automaticRetryAllowed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
            "productEndpointAuthenticationEvaluatedByThisReview",
            "productEndpointAuthenticationUserInputRequiredForThisReview",
            "productEndpointAuthenticationIsSeparateRuntimeInvariant",
            "productEndpointAuthenticationRemainsSeparateRuntimeInvariant",
            "contentBinding",
        },
        "review claim",
    )
    require(
        value.get("documentType")
        == "aetherlink.g2-pion-dependency-source-review-wave1-one-use-claim"
        and value.get("schemaVersion") == "1.0"
        and value.get("permitId") == PERMIT_ID
        and value.get("permitContentSha256") == permit_content_sha
        and value.get("reviewId") == REVIEW_ID
        and value.get("automaticRetryAllowed") is False,
        "review claim identity",
    )
    no_auth(value, "review claim no-auth")
    return content_sha


def validate_result(
    value: Mapping[str, Any],
    raw: bytes,
    permit: Mapping[str, Any],
    permit_content_sha: str,
) -> tuple[str, dict[str, Any]]:
    validate_content_binding(
        value, raw, "result_without_contentBinding", "result"
    )
    require_exact_keys(
        value,
        {
            "documentType",
            "schemaVersion",
            "reviewId",
            "status",
            "result",
            "decisionBinding",
            "permitBinding",
            "inputSet",
            "coverage",
            "moduleMetadata",
            "sourceSurface",
            "graphDiscovery",
            "licenseInventory",
            "specialSourceInventory",
            "operationCounters",
            "closure",
            "personalProjectBoundary",
            "nextAction",
            "postReadbackNextAction",
            "contentBinding",
        },
        "result schema",
    )
    require(
        value.get("documentType")
        == "aetherlink.g2-pion-dependency-source-review-wave1-result"
        and value.get("schemaVersion") == "1.0"
        and value.get("reviewId") == REVIEW_ID
        and value.get("decisionBinding") == permit.get("decisionBinding")
        and value.get("permitBinding")
        == {"permitId": PERMIT_ID, "contentSha256": permit_content_sha},
        "result identity",
    )
    graph = value.get("graphDiscovery")
    require(type(graph) is dict, "result graph")
    summary = validate_graph(graph)
    contract = ROUTES[summary["route"]]
    require(
        value.get("status") == contract["resultStatus"]
        and value.get("nextAction") == contract["resultNextAction"]
        and value.get("postReadbackNextAction")
        == contract["postReadbackNextAction"],
        "result routing",
    )
    counters = value.get("operationCounters")
    require(type(counters) is dict, "result counters")
    for field in (
        "archiveExtractionCount",
        "sourceExecutionCount",
        "subprocessCount",
        "networkOperationCount",
    ):
        require(counters.get(field) == 0, f"result counter {field}")
    require(counters.get("fileWriteCount") == 3, "result file write count")
    closure = value.get("closure")
    require(type(closure) is dict, "result closure")
    for field in (
        "dependencySourceReviewed",
        "graphFixedPointReached",
        "dependencyClosureComplete",
        "semanticClosureComplete",
        "rungThreeComplete",
        "candidateSelected",
        "librarySelected",
    ):
        require(closure.get(field) is False, f"result closure {field}")
    no_auth(value.get("personalProjectBoundary", {}), "result no-auth")
    return summary["route"], summary


def validate_review_manifest(
    value: Mapping[str, Any],
    raw: bytes,
    result: Mapping[str, Any],
    result_raw: bytes,
    permit_content_sha: str,
) -> str:
    content_sha = validate_content_binding(
        value, raw, "manifest_without_contentBinding", "review manifest"
    )
    require_exact_keys(
        value,
        {
            "documentType",
            "schemaVersion",
            "reviewId",
            "permitId",
            "permitContentSha256",
            "resultPath",
            "resultRawSha256",
            "resultContentSha256",
            "graphSha256",
            "resultStatus",
            "manifestWrittenLast",
            "independentReadbackPassed",
            "networkOperationCount",
            "sourceExecutionCount",
            "productEndpointAuthenticationEvaluatedByThisReview",
            "productEndpointAuthenticationUserInputRequiredForThisReview",
            "productEndpointAuthenticationIsSeparateRuntimeInvariant",
            "nextAction",
            "contentBinding",
        },
        "review manifest",
    )
    require(
        value.get("documentType")
        == "aetherlink.g2-pion-dependency-source-review-wave1-manifest"
        and value.get("schemaVersion") == "1.0"
        and value.get("reviewId") == REVIEW_ID
        and value.get("permitId") == PERMIT_ID
        and value.get("permitContentSha256") == permit_content_sha
        and value.get("resultPath") == RESULT_PATH
        and value.get("resultRawSha256") == sha256_bytes(result_raw)
        and value.get("resultContentSha256")
        == result["contentBinding"]["sha256"]
        and value.get("graphSha256") == result["graphDiscovery"]["graphSha256"]
        and value.get("resultStatus") == result["status"]
        and value.get("manifestWrittenLast") is True
        and value.get("independentReadbackPassed") is False
        and value.get("networkOperationCount") == 0
        and value.get("sourceExecutionCount") == 0
        and value.get("nextAction")
        == (
            "run_separate_dependency_source_review_wave1_"
            "independent_readback"
        ),
        "review manifest binding",
    )
    no_auth(value, "review manifest no-auth")
    return content_sha


def binding(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
    path: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path,
        "rawSha256": sha256_bytes(raw[path]),
        "contentSha256": content_shas[path],
    }
    if extra:
        result.update(extra)
    return result


def recovery_decision_binding(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    return expected_recovery_decision_binding(raw, content_shas)


def prior_recovery_decision_binding(
    raw: Mapping[str, bytes],
    content_shas: Mapping[str, str],
) -> dict[str, Any]:
    return expected_prior_recovery_decision_binding(raw, content_shas)


def historical_bindings(
    documents: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    value = documents[RECOVERY_DECISION_PATH].get("failedAttemptBindings")
    require(type(value) is dict, "held historical attempt bindings")
    return dict(value)


def historical_namespace_contracts(
    documents: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    value = documents[RECOVERY_DECISION_PATH].get(
        "failedAttemptNamespaceContracts"
    )
    require(type(value) is dict, "held historical namespace contracts")
    return dict(value)


def personal_boundary() -> dict[str, Any]:
    return {
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
        "productEndpointAuthenticationEvaluatedByThisReadback": False,
        "productEndpointAuthenticationUserInputRequiredForThisReadback": False,
        "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
    }


def operation_counters(held_count: int) -> dict[str, Any]:
    return {
        "heldInputCount": held_count - 3,
        "stableReadPassesPerInput": 2,
        "finalNameIdentityBarrierCompleted": True,
        "ancestorIdentityBarrierCompleted": True,
        "runnerInvocationCount": 0,
        "archiveOpenCount": 0,
        "archiveMemberInspectionCount": 0,
        "sourceExecutionCount": 0,
        "subprocessCount": 0,
        "networkOperationCount": 0,
        "fileWriteCount": 3,
    }


def graph_verification(
    route: str, summary: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "algorithm": "stored_eight_field_projection_byte_reconstruction_v1",
        "sourceGraphAlgorithm": "go1.24_mvs_profile_union_fixed_point_v1",
        "versionSpecificVertexTraversal": True,
        "route": route,
        "selectedVersionCount": summary["selectedVersionCount"],
        "graphNodeCount": summary["graphNodeCount"],
        "graphEdgeCount": summary["graphEdgeCount"],
        "moduleNodeCount": summary["moduleNodeCount"],
        "moduleEdgeCount": summary["moduleEdgeCount"],
        "newTupleCount": summary["newTupleCount"],
        "unmappedExternalImportCount": summary[
            "unmappedExternalImportCount"
        ],
        "unresolvedDeclaredExternalImportCount": summary[
            "unresolvedDeclaredExternalImportCount"
        ],
        "fixedPointCandidate": summary["fixedPointCandidate"],
        "graphSha256": summary["graphSha256"],
        "moduleGraphAndFrontierSha256": summary[
            "moduleGraphAndFrontierSha256"
        ],
        "reconstructionProjectionSha256": summary[
            "reconstructionProjectionSha256"
        ],
        "independentReconstructionCount": 2,
        "independentReconstructionAlgorithms": summary[
            "reconstructionAlgorithms"
        ],
        "storedProjectionEqualityVerified": True,
        "sourceGraphAlgorithmsReexecuted": False,
        "archiveMembersReopened": False,
    }


def non_claims(route: str) -> dict[str, Any]:
    return {
        "readbackReexecutesGraphAlgorithms": False,
        "readbackProvesSourceGraphCorrectness": False,
        "readbackProvesFixedPoint": False,
        "fixedPointCandidateOnly": route == "fixed_point_candidate",
        "candidateOrLibrarySelected": False,
        "dependencyClosureComplete": False,
        "semanticClosureComplete": False,
        "rungThreeComplete": False,
        "releaseReady": False,
    }


class VerificationInputs:
    def __init__(self, root: Path) -> None:
        self.root_fd = -1
        self.held: dict[str, HeldFile] = {}
        self.raw: dict[str, bytes] = {}
        self.documents: dict[str, dict[str, Any]] = {}
        self.required_absent_paths = (
            FAILURE_PATH,
            *expected_v1_absent_paths(),
            *expected_v2_absent_paths(),
        )
        try:
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            root_info = os.fstat(self.root_fd)
            require(
                stat.S_ISDIR(root_info.st_mode)
                and root_info.st_uid in {0, os.geteuid()}
                and stat.S_IMODE(root_info.st_mode) & 0o022 == 0,
                "unsafe repository root",
            )
            self._hold(PERMIT_PATH, MAXIMUM_JSON_BYTES, False)
            permit = strict_json(self.raw[PERMIT_PATH], "permit")
            permit_content_sha, tools = validate_permit(
                permit, self.raw[PERMIT_PATH]
            )
            self.documents[PERMIT_PATH] = permit
            self.permit_content_sha = permit_content_sha
            self.tool_bindings = tools
            for path, owner_only in (
                (DECISION_PATH, False),
                (V1_RECOVERY_DECISION_PATH, False),
                (RECOVERY_DECISION_PATH, False),
                (V1_PERMIT_PATH, False),
                (V1_REVIEW_CLAIM_PATH, True),
                (V1_FAILURE_PATH, True),
                (V2_PERMIT_PATH, False),
                (V2_REVIEW_CLAIM_PATH, True),
                (V2_FAILURE_PATH, True),
                (REVIEW_CLAIM_PATH, True),
                (RESULT_PATH, True),
                (REVIEW_MANIFEST_PATH, True),
                (READBACK_CLAIM_PATH, True),
                (READBACK_RECEIPT_PATH, True),
                (READBACK_MANIFEST_PATH, True),
            ):
                self._hold(path, MAXIMUM_JSON_BYTES, owner_only)
            for tool in tools:
                self._hold(tool["path"], MAXIMUM_TOOL_BYTES, False)
                require(
                    sha256_bytes(self.raw[tool["path"]])
                    == tool["rawSha256"],
                    "bound tool bytes",
                )
            decision, decision_content_sha = validate_decision(
                self.raw[DECISION_PATH]
            )
            v1_recovery, v1_recovery_content_sha = (
                validate_v1_recovery_decision(
                    self.raw[V1_RECOVERY_DECISION_PATH]
                )
            )
            recovery, recovery_content_sha = validate_recovery_decision(
                self.raw[RECOVERY_DECISION_PATH]
            )
            v1_permit, v1_permit_content_sha = validate_v1_permit(
                self.raw[V1_PERMIT_PATH]
            )
            v1_claim = strict_json(
                self.raw[V1_REVIEW_CLAIM_PATH],
                "historical v1 claim",
            )
            v1_claim_content_sha = validate_v1_claim(
                v1_claim,
                self.raw[V1_REVIEW_CLAIM_PATH],
                v1_permit_content_sha,
            )
            v1_failure = strict_json(
                self.raw[V1_FAILURE_PATH],
                "historical v1 failure",
            )
            v1_failure_content_sha = validate_v1_failure(
                v1_failure,
                self.raw[V1_FAILURE_PATH],
                v1_permit_content_sha,
                sha256_bytes(self.raw[V1_REVIEW_CLAIM_PATH]),
            )
            v2_permit, v2_permit_content_sha = validate_v2_permit(
                self.raw[V2_PERMIT_PATH]
            )
            v2_claim = strict_json(
                self.raw[V2_REVIEW_CLAIM_PATH],
                "historical v2 claim",
            )
            v2_claim_content_sha = validate_v2_claim(
                v2_claim,
                self.raw[V2_REVIEW_CLAIM_PATH],
                v2_permit_content_sha,
            )
            v2_failure = strict_json(
                self.raw[V2_FAILURE_PATH],
                "historical v2 failure",
            )
            v2_failure_content_sha = validate_v2_failure(
                v2_failure,
                self.raw[V2_FAILURE_PATH],
                v2_permit_content_sha,
                sha256_bytes(self.raw[V2_REVIEW_CLAIM_PATH]),
            )
            historical_content_shas = {
                DECISION_PATH: decision_content_sha,
                V1_RECOVERY_DECISION_PATH: v1_recovery_content_sha,
                RECOVERY_DECISION_PATH: recovery_content_sha,
                V1_PERMIT_PATH: v1_permit_content_sha,
                V1_REVIEW_CLAIM_PATH: v1_claim_content_sha,
                V1_FAILURE_PATH: v1_failure_content_sha,
                V2_PERMIT_PATH: v2_permit_content_sha,
                V2_REVIEW_CLAIM_PATH: v2_claim_content_sha,
                V2_FAILURE_PATH: v2_failure_content_sha,
            }
            require(
                permit.get("decisionBinding")
                == expected_original_decision_binding(
                    self.raw, historical_content_shas
                )
                and v1_permit.get("decisionBinding")
                == expected_original_decision_binding(
                    self.raw, historical_content_shas
                ),
                "permit/original decision exact binding",
            )
            require(
                v2_permit.get("decisionBinding")
                == expected_original_decision_binding(
                    self.raw, historical_content_shas
                ),
                "historical v2 permit/original decision exact binding",
            )
            require(
                permit.get("recoveryDecisionBinding")
                == expected_recovery_decision_binding(
                    self.raw, historical_content_shas
                )
                and permit.get("priorRecoveryDecisionBinding")
                == expected_prior_recovery_decision_binding(
                    self.raw, historical_content_shas
                ),
                "permit/recovery decision exact binding",
            )
            validate_v1_recovery_history(
                v1_recovery,
                self.raw,
                historical_content_shas,
            )
            require(
                v2_permit.get("recoveryDecisionBinding")
                == expected_v1_recovery_decision_binding(
                    self.raw, historical_content_shas
                )
                and v2_permit.get("failedAttemptBindings")
                == v1_recovery.get("failedAttemptBindings")
                and v2_permit.get("failedAttemptNamespaceContract")
                == v1_recovery.get("failedAttemptNamespaceContract")
                and v2_permit.get("apfsRecoveryContract")
                == v1_recovery.get("selectedV2Correction")
                and v2_permit.get("v1PreservationContract")
                == v1_recovery.get("v1PreservationContract")
                and v2_permit.get("v2NamespaceContract")
                == v1_recovery.get("v2NamespaceContract"),
                "historical v2 permit/v1 recovery contracts",
            )
            validate_recovery_history(
                recovery,
                self.raw,
                historical_content_shas,
            )
            require(
                permit.get("failedAttemptBindings")
                == recovery.get("failedAttemptBindings")
                and permit.get("failedAttemptNamespaceContracts")
                == recovery.get("failedAttemptNamespaceContracts")
                and permit.get("apfsRecoveryContract")
                == v1_recovery.get("selectedV2Correction")
                and permit.get("selectedV3Correction")
                == recovery.get("selectedV3Correction")
                and permit.get("v1PreservationContract")
                == recovery.get("v1PreservationContract")
                and permit.get("v2PreservationContract")
                == recovery.get("v2PreservationContract")
                and permit.get("v3NamespaceContract")
                == recovery.get("v3NamespaceContract"),
                "permit/recovery historical contracts",
            )
            review_claim = strict_json(
                self.raw[REVIEW_CLAIM_PATH], "review claim"
            )
            review_claim_content_sha = validate_review_claim(
                review_claim,
                self.raw[REVIEW_CLAIM_PATH],
                permit_content_sha,
            )
            result = strict_json(self.raw[RESULT_PATH], "result")
            route, summary = validate_result(
                result, self.raw[RESULT_PATH], permit, permit_content_sha
            )
            review_manifest = strict_json(
                self.raw[REVIEW_MANIFEST_PATH], "review manifest"
            )
            review_manifest_content_sha = validate_review_manifest(
                review_manifest,
                self.raw[REVIEW_MANIFEST_PATH],
                result,
                self.raw[RESULT_PATH],
                permit_content_sha,
            )
            self.documents.update(
                {
                    DECISION_PATH: decision,
                    V1_RECOVERY_DECISION_PATH: v1_recovery,
                    RECOVERY_DECISION_PATH: recovery,
                    V1_PERMIT_PATH: v1_permit,
                    V1_REVIEW_CLAIM_PATH: v1_claim,
                    V1_FAILURE_PATH: v1_failure,
                    V2_PERMIT_PATH: v2_permit,
                    V2_REVIEW_CLAIM_PATH: v2_claim,
                    V2_FAILURE_PATH: v2_failure,
                    REVIEW_CLAIM_PATH: review_claim,
                    RESULT_PATH: result,
                    REVIEW_MANIFEST_PATH: review_manifest,
                }
            )
            self.content_shas = {
                DECISION_PATH: decision_content_sha,
                V1_RECOVERY_DECISION_PATH: v1_recovery_content_sha,
                RECOVERY_DECISION_PATH: recovery_content_sha,
                V1_PERMIT_PATH: v1_permit_content_sha,
                V1_REVIEW_CLAIM_PATH: v1_claim_content_sha,
                V1_FAILURE_PATH: v1_failure_content_sha,
                V2_PERMIT_PATH: v2_permit_content_sha,
                V2_REVIEW_CLAIM_PATH: v2_claim_content_sha,
                V2_FAILURE_PATH: v2_failure_content_sha,
                PERMIT_PATH: permit_content_sha,
                REVIEW_CLAIM_PATH: review_claim_content_sha,
                RESULT_PATH: result["contentBinding"]["sha256"],
                REVIEW_MANIFEST_PATH: review_manifest_content_sha,
            }
            self.route = route
            self.summary = summary
            self._validate_readback_documents()
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def _hold(self, path: str, maximum: int, owner_only: bool) -> None:
        require(path not in self.held, "duplicate held input")
        held = HeldFile(
            self.root_fd,
            path,
            maximum_bytes=maximum,
            owner_only=owner_only,
        )
        self.held[path] = held
        first = held.read_pass()
        second = held.read_pass()
        require(first == second, f"{path}: unstable bytes")
        self.raw[path] = first

    def _validate_readback_documents(self) -> None:
        claim = strict_json(self.raw[READBACK_CLAIM_PATH], "readback claim")
        claim_content_sha = validate_content_binding(
            claim,
            self.raw[READBACK_CLAIM_PATH],
            "readback_claim_without_contentBinding",
            "readback claim",
        )
        expected_claim = content_bound(
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "independent-readback-one-use-claim"
                ),
                "schemaVersion": "1.0",
                "readbackId": READBACK_ID,
                "reviewId": REVIEW_ID,
                "permitId": PERMIT_ID,
                "permitContentSha256": self.permit_content_sha,
                "reviewClaimBinding": binding(
                    self.raw, self.content_shas, REVIEW_CLAIM_PATH
                ),
                "reviewResultBinding": binding(
                    self.raw,
                    self.content_shas,
                    RESULT_PATH,
                    {"status": self.documents[RESULT_PATH]["status"]},
                ),
                "reviewManifestBinding": binding(
                    self.raw,
                    self.content_shas,
                    REVIEW_MANIFEST_PATH,
                    {
                        "resultStatus": self.documents[
                            REVIEW_MANIFEST_PATH
                        ]["resultStatus"]
                    },
                ),
                "route": self.route,
                "automaticRetryAllowed": False,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "productEndpointAuthenticationEvaluatedByThisReadback": False,
                "productEndpointAuthenticationUserInputRequiredForThisReadback": (
                    False
                ),
                "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            },
            "readback_claim_without_contentBinding",
        )
        require(claim == expected_claim, "readback claim exact contract")
        route = ROUTES[self.route]
        receipt = strict_json(
            self.raw[READBACK_RECEIPT_PATH], "readback receipt"
        )
        receipt_content_sha = validate_content_binding(
            receipt,
            self.raw[READBACK_RECEIPT_PATH],
            "readback_receipt_without_contentBinding",
            "readback receipt",
        )
        expected_receipt = content_bound(
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "independent-readback-receipt"
                ),
                "schemaVersion": "1.0",
                "readbackId": READBACK_ID,
                "status": route["receiptStatus"],
                "result": route["receiptResult"],
                "decisionBinding": binding(
                    self.raw,
                    self.content_shas,
                    DECISION_PATH,
                    {"decisionId": DECISION_ID},
                ),
                "recoveryDecisionBinding": recovery_decision_binding(
                    self.raw, self.content_shas
                ),
                "priorRecoveryDecisionBinding": (
                    prior_recovery_decision_binding(
                        self.raw, self.content_shas
                    )
                ),
                "failedAttemptBindings": historical_bindings(
                    self.documents
                ),
                "failedAttemptNamespaceContracts": (
                    historical_namespace_contracts(self.documents)
                ),
                "executionPermitBinding": binding(
                    self.raw,
                    self.content_shas,
                    PERMIT_PATH,
                    {"permitId": PERMIT_ID},
                ),
                "reviewClaimBinding": binding(
                    self.raw, self.content_shas, REVIEW_CLAIM_PATH
                ),
                "reviewResultBinding": binding(
                    self.raw,
                    self.content_shas,
                    RESULT_PATH,
                    {"status": self.documents[RESULT_PATH]["status"]},
                ),
                "reviewManifestBinding": binding(
                    self.raw,
                    self.content_shas,
                    REVIEW_MANIFEST_PATH,
                    {
                        "resultStatus": self.documents[
                            REVIEW_MANIFEST_PATH
                        ]["resultStatus"]
                    },
                ),
                "readbackClaimBinding": {
                    "path": READBACK_CLAIM_PATH,
                    "rawSha256": sha256_bytes(
                        self.raw[READBACK_CLAIM_PATH]
                    ),
                    "contentSha256": claim_content_sha,
                },
                "toolBindings": self.tool_bindings,
                "graphVerification": graph_verification(
                    self.route, self.summary
                ),
                "operationCounters": operation_counters(len(self.held)),
                "personalProjectBoundary": personal_boundary(),
                "nonClaims": non_claims(self.route),
                "nextAction": route["receiptNextAction"],
            },
            "readback_receipt_without_contentBinding",
        )
        require(receipt == expected_receipt, "readback receipt exact contract")
        manifest = strict_json(
            self.raw[READBACK_MANIFEST_PATH], "readback manifest"
        )
        validate_content_binding(
            manifest,
            self.raw[READBACK_MANIFEST_PATH],
            "readback_manifest_without_contentBinding",
            "readback manifest",
        )
        expected_manifest = content_bound(
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "independent-readback-manifest"
                ),
                "schemaVersion": "1.0",
                "manifestId": READBACK_MANIFEST_ID,
                "status": route["manifestStatus"],
                "result": route["manifestResult"],
                "recoveryDecisionBinding": recovery_decision_binding(
                    self.raw, self.content_shas
                ),
                "priorRecoveryDecisionBinding": (
                    prior_recovery_decision_binding(
                        self.raw, self.content_shas
                    )
                ),
                "failedAttemptBindings": historical_bindings(
                    self.documents
                ),
                "failedAttemptNamespaceContracts": (
                    historical_namespace_contracts(self.documents)
                ),
                "readbackReceiptBinding": {
                    "path": READBACK_RECEIPT_PATH,
                    "rawSha256": sha256_bytes(
                        self.raw[READBACK_RECEIPT_PATH]
                    ),
                    "contentSha256": receipt_content_sha,
                },
                "readbackClaimBinding": {
                    "path": READBACK_CLAIM_PATH,
                    "rawSha256": sha256_bytes(
                        self.raw[READBACK_CLAIM_PATH]
                    ),
                    "contentSha256": claim_content_sha,
                },
                "reviewResultBinding": binding(
                    self.raw,
                    self.content_shas,
                    RESULT_PATH,
                    {"status": self.documents[RESULT_PATH]["status"]},
                ),
                "reviewManifestBinding": binding(
                    self.raw,
                    self.content_shas,
                    REVIEW_MANIFEST_PATH,
                    {
                        "resultStatus": self.documents[
                            REVIEW_MANIFEST_PATH
                        ]["resultStatus"]
                    },
                ),
                "route": self.route,
                "manifestWrittenLast": True,
                "independentReadbackPassed": True,
                "operationCounters": operation_counters(len(self.held)),
                "personalProjectBoundary": personal_boundary(),
                "nonClaims": non_claims(self.route),
                "nextAction": route["manifestNextAction"],
            },
            "readback_manifest_without_contentBinding",
        )
        require(manifest == expected_manifest, "readback manifest exact contract")
        no_auth(claim, "readback claim no-auth")
        no_auth(
            receipt.get("personalProjectBoundary", {}),
            "readback receipt no-auth",
        )
        no_auth(
            manifest.get("personalProjectBoundary", {}),
            "readback manifest no-auth",
        )

    def final_barrier(self) -> None:
        for held in self.held.values():
            held.final_barrier()
        for path in self.required_absent_paths:
            require(
                path_kind(self.root_fd, path) == "absent",
                f"{path}: required historical/current absence",
            )
        for held in self.held.values():
            held.final_barrier()

    def close(self) -> None:
        for held in reversed(list(self.held.values())):
            held.close()
        self.held.clear()
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def __enter__(self) -> "VerificationInputs":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def validate_state(root: Path = ROOT) -> dict[str, Any]:
    with VerificationInputs(root) as state:
        state.final_barrier()
        return {
            "documentType": (
                "aetherlink.g2-pion-dependency-source-review-wave1-"
                "independent-readback-verification-result"
            ),
            "schemaVersion": "1.0",
            "status": (
                "dependency_source_review_wave1_independent_readback_verified_"
                f"{state.route}"
            ),
            "validationPassed": True,
            "route": state.route,
            "graphSha256": state.summary["graphSha256"],
            "readbackReceiptRawSha256": sha256_bytes(
                state.raw[READBACK_RECEIPT_PATH]
            ),
            "readbackManifestRawSha256": sha256_bytes(
                state.raw[READBACK_MANIFEST_PATH]
            ),
            "heldInputCount": len(state.held),
            "verificationOnly": True,
            "recordModeExposed": False,
            "archiveOpenCount": 0,
            "archiveMemberInspectionCount": 0,
            "runnerInvocationCount": 0,
            "sourceExecutionCount": 0,
            "subprocessCount": 0,
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": ROUTES[state.route]["manifestNextAction"],
        }


def error_document(error: BaseException) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-source-review-wave1-"
            "independent-readback-verification-error"
        ),
        "schemaVersion": "1.0",
        "status": "failed_closed",
        "validationPassed": False,
        "error": str(error),
        "verificationOnly": True,
        "recordModeExposed": False,
        "archiveOpenCount": 0,
        "archiveMemberInspectionCount": 0,
        "runnerInvocationCount": 0,
        "sourceExecutionCount": 0,
        "subprocessCount": 0,
        "networkOperationCount": 0,
        "fileWriteCount": 0,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        result = validate_state(ROOT)
    except (VerificationError, OSError) as error:
        print(canonical_json_bytes(error_document(error)).decode("utf-8"), end="")
        return 1
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
