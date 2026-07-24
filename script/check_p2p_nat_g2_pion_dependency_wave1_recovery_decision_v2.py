#!/usr/bin/env python3
"""Validate the consumed v2 dependency-wave failure and v3 recovery design."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
SOURCE_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
RECOVERY_V1_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.json"
)
PERMIT_V2_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v2.json"
)
RECOVERY_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json"
)
RECOVERY_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.md"
)
CLAIM_V1_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v1.claim"
)
FAILURE_V1_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v1.json"
)
CLAIM_V2_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v2.claim"
)
FAILURE_V2_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v2.json"
)
RUNNER_V2_PATH = "script/acquire_p2p_nat_g2_pion_dependency_wave1_v2_once.py"
RUNNER_TEST_V2_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_dependency_wave1_v2_once.py"
)
PERMIT_CHECKER_V2_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v2.py"
)
PERMIT_TEST_V2_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_execution_permit_v2.py"
)

DEPENDENCY_PARENT = "build/offline-source/pion-ice-v4.3.0/dependencies"
V1_ACCEPTED_PATH = f"{DEPENDENCY_PARENT}/wave-1/accepted"
V2_ACCEPTED_PATH = f"{DEPENDENCY_PARENT}/wave-1-v2/accepted"
V3_WAVE_PATH = f"{DEPENDENCY_PARENT}/wave-1-v3"
V3_CLAIM_PATH = f"{DEPENDENCY_PARENT}/.wave-1-v3.claim"
V3_SUCCESS_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v3.json"
)
V3_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v3.json"
)
V3_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v3.json"
)
V1_SUCCESS_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v1.json"
)
V1_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v1.json"
)
V2_SUCCESS_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v2.json"
)
V2_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v2.json"
)

EXPECTED_RAW_SHA256 = {
    SOURCE_DECISION_PATH: (
        "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
    ),
    RECOVERY_V1_PATH: (
        "313e548e8d538ccc582f4d1c74618823d31b45915b4a5124378bc0d8b98315c2"
    ),
    PERMIT_V2_PATH: (
        "80867396723efcc3a1f0d3c3beca94b3634883058224382231ddcbb141328e1c"
    ),
    RUNNER_V2_PATH: (
        "9dcbd6e70e6a7904b468042ee116f04f014a4299f30ea32c41c4f850af53b823"
    ),
    RUNNER_TEST_V2_PATH: (
        "103586cafd5a92dc8851d36a13a759747e1eb6089425a47ef3cbbf4a0dce90e9"
    ),
    PERMIT_CHECKER_V2_PATH: (
        "35ac6152731f16e84c5ac3e4f6ddfdc04c109b51c01967ef63cc53557f1c2139"
    ),
    PERMIT_TEST_V2_PATH: (
        "8dbd52d521f6f1693b7c110106724579e0ffdecd4a4f6ddd2d303541aad5deb9"
    ),
    CLAIM_V1_PATH: (
        "560bbb6028588b91a2d7f35ae826cdcc68940566656a279b2dbe7b9352e161d5"
    ),
    FAILURE_V1_PATH: (
        "cdf4d75aeddb2accc4720c2ef8a606b22e333eac9aea2196a010f9383dc877fa"
    ),
    CLAIM_V2_PATH: (
        "d9902cec698026035f9d4e8937114e09d990e868a272ce7d1ec19679a1b2ef77"
    ),
    FAILURE_V2_PATH: (
        "e04e7224ef6288e964f36087170c2ce888f398bb967475d144508ceda0ef44dc"
    ),
    RECOVERY_PATH: (
        "c03ca34315226ad8a59d8857448657c3be2565b22c0583085eb93c6c65ad72fd"
    ),
    RECOVERY_READER_PATH: (
        "7681084a2bac8d8c07ef803c1b6db7cd2e82fdfc6c4588076d277f89d12daf6d"
    ),
}

EXPECTED_SOURCE_CONTENT_SHA256 = (
    "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201"
)
EXPECTED_RECOVERY_V1_CONTENT_SHA256 = (
    "8cdcccbea4318d41f44da78000f3e4161251a5ad9542543c2962d4767ed1e968"
)
EXPECTED_PERMIT_V2_CONTENT_SHA256 = (
    "44fe9460f2c4fc746b0b8d9389874644371640f23409178a0d00b0667ab93bd1"
)
EXPECTED_RECOVERY_CONTENT_SHA256 = (
    "5a41d5bcf7dccb25bb5e558d892620748ea72e12e9f90244242ffdb44e092a93"
)
EXPECTED_TUPLE_ID = "wave1-011-466356e1ed29"
EXPECTED_MODULE = "github.com/davecgh/go-spew"
EXPECTED_VERSION = "v1.1.1"
MAXIMUM_FILE_BYTES = 4 * 1024 * 1024


class CheckError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(code, message)


def require_isolated_interpreter() -> None:
    require(sys.flags.isolated == 1, "E_RUNTIME", "isolated interpreter required")
    require(sys.dont_write_bytecode, "E_RUNTIME", "bytecode writes must be disabled")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def strict_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CheckError("E_JSON", f"{label} is not UTF-8") from error

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            require(key not in result, "E_JSON", f"{label} duplicate key {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise CheckError("E_JSON", f"{label} non-finite number {value}")

    try:
        value = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, TypeError) as error:
        raise CheckError("E_JSON", f"{label} parse failure") from error
    require(isinstance(value, dict), "E_JSON", f"{label} must be an object")
    return value


def exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    require(isinstance(value, dict), "E_SCHEMA", f"{label} must be an object")
    actual = set(value)
    require(
        actual == expected,
        "E_SCHEMA",
        f"{label} keys differ: missing={sorted(expected - actual)} "
        f"unexpected={sorted(actual - expected)}",
    )
    return value


def typed_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            typed_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            typed_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def validate_relative_path(relative: str) -> tuple[str, ...]:
    path = PurePosixPath(relative)
    parts = path.parts
    require(
        bool(parts)
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in parts),
        "E_FILESYSTEM",
        f"unsafe path {relative}",
    )
    return parts


def directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def file_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def descriptor_state(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


class Snapshot:
    def __init__(self, path: str, fd: int, raw: bytes, state: tuple[int, ...]) -> None:
        self.path = path
        self.fd = fd
        self.raw = raw
        self.state = state


class SafeReader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root_fd = os.open(root, directory_flags())
        root_info = os.fstat(self.root_fd)
        require(stat.S_ISDIR(root_info.st_mode), "E_FILESYSTEM", "root type")
        require(root_info.st_uid == os.getuid(), "E_FILESYSTEM", "root owner")
        require(
            stat.S_IMODE(root_info.st_mode) & 0o022 == 0,
            "E_FILESYSTEM",
            "root permissions",
        )
        self.root_state = descriptor_state(root_info)
        self.snapshots: list[Snapshot] = []

    def _open_parent(self, relative: str) -> tuple[int, str]:
        parts = validate_relative_path(relative)
        current = os.dup(self.root_fd)
        try:
            for part in parts[:-1]:
                child = os.open(part, directory_flags(), dir_fd=current)
                info = os.fstat(child)
                require(stat.S_ISDIR(info.st_mode), "E_FILESYSTEM", "ancestor type")
                require(info.st_uid == os.getuid(), "E_FILESYSTEM", "ancestor owner")
                require(
                    stat.S_IMODE(info.st_mode) & 0o022 == 0,
                    "E_FILESYSTEM",
                    "ancestor permissions",
                )
                os.close(current)
                current = child
            return current, parts[-1]
        except Exception:
            os.close(current)
            raise

    def read(self, relative: str, maximum_bytes: int = MAXIMUM_FILE_BYTES) -> bytes:
        parent, name = self._open_parent(relative)
        try:
            fd = os.open(name, file_flags(), dir_fd=parent)
        except OSError as error:
            os.close(parent)
            raise CheckError("E_FILESYSTEM", f"cannot open {relative}") from error
        os.close(parent)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode), "E_FILESYSTEM", f"{relative} type")
            require(before.st_uid == os.getuid(), "E_FILESYSTEM", f"{relative} owner")
            require(before.st_nlink == 1, "E_FILESYSTEM", f"{relative} link count")
            require(
                stat.S_IMODE(before.st_mode) & 0o022 == 0,
                "E_FILESYSTEM",
                f"{relative} permissions",
            )
            require(before.st_size <= maximum_bytes, "E_FILESYSTEM", f"{relative} size")
            chunks: list[bytes] = []
            total = 0
            while total <= maximum_bytes:
                chunk = os.read(fd, min(64 * 1024, maximum_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(fd)
            require(
                len(raw) <= maximum_bytes
                and len(raw) == before.st_size
                and descriptor_state(before) == descriptor_state(after),
                "E_TOCTOU",
                f"{relative} changed during read",
            )
            self.snapshots.append(
                Snapshot(relative, fd, raw, descriptor_state(after))
            )
            return raw
        except Exception:
            os.close(fd)
            raise

    def snapshot(self, relative: str) -> Snapshot:
        for snapshot in self.snapshots:
            if snapshot.path == relative:
                return snapshot
        raise CheckError("E_INTERNAL", f"missing snapshot {relative}")

    def exists(self, relative: str) -> bool:
        parent, name = self._open_parent(relative)
        try:
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return False
            return True
        finally:
            os.close(parent)

    def list_directory(self, relative: str) -> list[str]:
        parts = validate_relative_path(relative)
        current = os.dup(self.root_fd)
        try:
            for part in parts:
                child = os.open(part, directory_flags(), dir_fd=current)
                info = os.fstat(child)
                require(stat.S_ISDIR(info.st_mode), "E_FILESYSTEM", "directory type")
                require(info.st_uid == os.getuid(), "E_FILESYSTEM", "directory owner")
                require(
                    stat.S_IMODE(info.st_mode) & 0o022 == 0,
                    "E_FILESYSTEM",
                    "directory permissions",
                )
                os.close(current)
                current = child
            return sorted(os.listdir(current))
        except OSError as error:
            raise CheckError("E_FILESYSTEM", f"cannot list {relative}") from error
        finally:
            os.close(current)

    def verify(self) -> None:
        for snapshot in self.snapshots:
            info = os.fstat(snapshot.fd)
            require(
                descriptor_state(info) == snapshot.state,
                "E_TOCTOU",
                f"{snapshot.path} descriptor changed",
            )
            os.lseek(snapshot.fd, 0, os.SEEK_SET)
            chunks: list[bytes] = []
            total = 0
            while total <= len(snapshot.raw):
                chunk = os.read(
                    snapshot.fd,
                    min(64 * 1024, len(snapshot.raw) + 1 - total),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            require(
                b"".join(chunks) == snapshot.raw,
                "E_TOCTOU",
                f"{snapshot.path} bytes changed",
            )
            parent, name = self._open_parent(snapshot.path)
            try:
                named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            finally:
                os.close(parent)
            require(
                (named.st_dev, named.st_ino) == (info.st_dev, info.st_ino),
                "E_TOCTOU",
                f"{snapshot.path} name changed",
            )
        current_root = os.fstat(self.root_fd)
        named_root = os.stat(self.root, follow_symlinks=False)
        require(
            descriptor_state(current_root) == self.root_state
            and (current_root.st_dev, current_root.st_ino)
            == (named_root.st_dev, named_root.st_ino),
            "E_TOCTOU",
            "repository root changed",
        )

    def close(self) -> None:
        for snapshot in self.snapshots:
            try:
                os.close(snapshot.fd)
            except OSError:
                pass
        self.snapshots.clear()
        os.close(self.root_fd)


def validate_content_binding(
    document: Mapping[str, Any],
    expected_scope: str,
    expected_digest: str,
    label: str,
) -> None:
    binding = exact_keys(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    require(
        typed_equal(
            binding,
            {
                "algorithm": "sha256",
                "canonicalization": (
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf"
                ),
                "scope": expected_scope,
                "sha256": expected_digest,
            },
        ),
        "E_BINDING",
        f"{label} binding fields",
    )
    payload = dict(document)
    payload.pop("contentBinding")
    require(
        sha256_bytes(canonical_json_bytes(payload)) == expected_digest,
        "E_BINDING",
        f"{label} binding digest",
    )


def validate_claim_v2(claim: Mapping[str, Any]) -> None:
    require(
        typed_equal(
            claim,
            {
                "claimType": (
                    "aetherlink.g2-pion-dependency-wave1-v2-one-use-claim"
                ),
                "createdAt": "2026-07-23T19:49:16Z",
                "permitContentSha256": EXPECTED_PERMIT_V2_CONTENT_SHA256,
                "permitId": (
                    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-"
                    "execution-permit-v2"
                ),
                "recoveryContentSha256": EXPECTED_RECOVERY_V1_CONTENT_SHA256,
                "rule": (
                    "v2_claim_persists_after_any_network_attempt_and_blocks_retry"
                ),
                "schemaVersion": "2.0",
                "v1ArtifactReuseAllowed": False,
            },
        ),
        "E_CLAIM",
        "v2 claim schema or values",
    )


def validate_failure_v2(failure: Mapping[str, Any]) -> None:
    require(
        typed_equal(
            failure,
            {
                "acceptedArtifactCount": 0,
                "automaticRetryAllowed": False,
                "claimRawSha256": EXPECTED_RAW_SHA256[CLAIM_V2_PATH],
                "claimRetained": True,
                "documentType": (
                    "aetherlink.g2-pion-dependency-wave1-v2-acquisition-failure"
                ),
                "externalAuthenticationRequired": False,
                "failedTupleId": EXPECTED_TUPLE_ID,
                "failedTupleOrder": 11,
                "failureCode": "E_GO_MOD_MISSING",
                "finalSetPublished": False,
                "legacyCompletedRequestCountForbidden": True,
                "networkRequestAttemptCount": 11,
                "nextAction": (
                    "prepare_new_versioned_wave1_v2_recovery_decision"
                ),
                "permitContentSha256": EXPECTED_PERMIT_V2_CONTENT_SHA256,
                "permitId": (
                    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-"
                    "execution-permit-v2"
                ),
                "phase": "zip",
                "recoveryContentSha256": EXPECTED_RECOVERY_V1_CONTENT_SHA256,
                "repositoryOwnerIdentityProofRequired": False,
                "responseBodyCompletedCount": 11,
                "result": "no_dependency_source_set_accepted",
                "safeNumericObservations": {
                    "entryCompressedBytes": 7119,
                    "entryOrdinal": 18,
                    "entryUncompressedBytes": 57466,
                },
                "schemaVersion": "2.0",
                "status": "wave1_v2_acquisition_failed_permit_consumed",
                "userActionRequired": False,
                "validatedAndStagedTupleCount": 10,
            },
        ),
        "E_FAILURE",
        "v2 failure schema or values",
    )


def validate_recovery(
    recovery: Mapping[str, Any],
    source: Mapping[str, Any],
) -> None:
    exact_keys(
        recovery,
        {
            "documentType",
            "schemaVersion",
            "decisionId",
            "recordedDate",
            "status",
            "result",
            "nextAction",
            "predecessorBindings",
            "terminalFailureBindings",
            "failureInterpretation",
            "rootCause",
            "selectedV3Policy",
            "v1AndV2PreservationContract",
            "v3NamespaceContract",
            "independentReadbackContract",
            "authority",
            "personalProjectBoundary",
            "closure",
            "nonClaims",
            "contentBinding",
        },
        "recovery",
    )
    require(
        recovery.get("documentType")
        == "aetherlink.g2-pion-dependency-wave1-recovery-decision"
        and recovery.get("schemaVersion") == "2.0"
        and recovery.get("decisionId")
        == "g2-pion-ice-v4.3.0-rung3-dependency-wave1-recovery-decision-v2"
        and recovery.get("recordedDate") == "2026-07-24",
        "E_RECOVERY",
        "recovery identity",
    )
    require(
        recovery.get("status")
        == (
            "wave1_v2_failure_read_back_recovery_v3_design_selected_"
            "execution_not_authorized"
        )
        and recovery.get("result")
        == (
            "v2_conflated_zip_and_mod_resources_tuple11_after_eleven_responses_"
            "no_final_set_v3_zip_plus_mod_policy_selected"
        )
        and recovery.get("nextAction")
        == "prepare_separate_v3_runner_checker_tests_and_execution_permit",
        "E_RECOVERY",
        "recovery disposition",
    )

    predecessors = exact_keys(
        recovery.get("predecessorBindings"),
        {
            "sourceIdentityDecision",
            "recoveryDecisionV1",
            "executionPermitV2",
            "runnerV2",
            "runnerTestsV2",
            "permitCheckerV2",
            "permitCheckerTestsV2",
        },
        "predecessors",
    )
    expected_predecessors = {
        "sourceIdentityDecision": {
            "path": SOURCE_DECISION_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[SOURCE_DECISION_PATH],
            "contentSha256": EXPECTED_SOURCE_CONTENT_SHA256,
        },
        "recoveryDecisionV1": {
            "path": RECOVERY_V1_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[RECOVERY_V1_PATH],
            "contentSha256": EXPECTED_RECOVERY_V1_CONTENT_SHA256,
        },
        "executionPermitV2": {
            "path": PERMIT_V2_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[PERMIT_V2_PATH],
            "contentSha256": EXPECTED_PERMIT_V2_CONTENT_SHA256,
        },
        "runnerV2": {
            "path": RUNNER_V2_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[RUNNER_V2_PATH],
        },
        "runnerTestsV2": {
            "path": RUNNER_TEST_V2_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[RUNNER_TEST_V2_PATH],
            "testCount": 28,
        },
        "permitCheckerV2": {
            "path": PERMIT_CHECKER_V2_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[PERMIT_CHECKER_V2_PATH],
        },
        "permitCheckerTestsV2": {
            "path": PERMIT_TEST_V2_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[PERMIT_TEST_V2_PATH],
            "testCount": 20,
        },
    }
    require(
        typed_equal(predecessors, expected_predecessors),
        "E_PREDECESSOR",
        "predecessor bindings",
    )

    terminal = exact_keys(
        recovery.get("terminalFailureBindings"),
        {"claimV2", "failureReceiptV2"},
        "terminal bindings",
    )
    require(
        typed_equal(
            terminal,
            {
                "claimV2": {
                    "path": CLAIM_V2_PATH,
                    "rawSha256": EXPECTED_RAW_SHA256[CLAIM_V2_PATH],
                    "byteSize": 482,
                    "mode": "0600",
                    "linkCount": 1,
                    "retained": True,
                    "automaticRetryAllowed": False,
                },
                "failureReceiptV2": {
                    "path": FAILURE_V2_PATH,
                    "rawSha256": EXPECTED_RAW_SHA256[FAILURE_V2_PATH],
                    "byteSize": 1174,
                    "mode": "0600",
                    "linkCount": 1,
                    "status": "wave1_v2_acquisition_failed_permit_consumed",
                    "result": "no_dependency_source_set_accepted",
                    "failureCode": "E_GO_MOD_MISSING",
                    "phase": "zip",
                    "failedTupleId": EXPECTED_TUPLE_ID,
                    "failedTupleOrder": 11,
                    "networkRequestAttemptCount": 11,
                    "responseBodyCompletedCount": 11,
                    "validatedAndStagedTupleCount": 10,
                    "acceptedArtifactCount": 0,
                    "finalSetPublished": False,
                    "automaticRetryAllowed": False,
                },
            },
        ),
        "E_TERMINAL",
        "terminal bindings",
    )

    interpretation = recovery.get("failureInterpretation")
    require(
        typed_equal(
            interpretation,
            {
                "failedTupleId": EXPECTED_TUPLE_ID,
                "failedTupleOrder": 11,
                "failedModule": EXPECTED_MODULE,
                "failedVersion": EXPECTED_VERSION,
                "expectedModuleZipH1": (
                    "h1:vj9j/u1bqnvCEfJOwUhtlOARqs3+rkHYY13jYWTU97c="
                ),
                "expectedGoModH1": (
                    "h1:J7Y8YcW2NihsgmVo/mv3lAwl/skON4iLHjSsI+c5H38="
                ),
                "networkRequestAttemptCount": 11,
                "responseBodyCompletedCount": 11,
                "validatedAndStagedTupleCount": 10,
                "safeNumericObservations": {
                    "entryOrdinal": 18,
                    "entryUncompressedBytes": 57466,
                    "entryCompressedBytes": 7119,
                },
                "stagingRetained": False,
                "acceptedFinalSetRetained": False,
                "v2PreflightTerminalState": (
                    "consumed_failed_recovery_required"
                ),
                "terminalStateSchemaValid": True,
                "observedOneUseArtifactCount": 2,
            },
        ),
        "E_INTERPRETATION",
        "failure interpretation",
    )

    root_cause = recovery.get("rootCause")
    require(
        typed_equal(
            root_cause,
            {
                "classification": "go_proxy_zip_and_mod_resources_conflated",
                "v2RequiredEmbeddedRootGoMod": True,
                "goProxyZipMayLegitimatelyOmitRootGoMod": True,
                "goProxyModEndpointSuppliesCanonicalModResource": True,
                "moduleZipH1AndGoModH1AreDistinctIdentities": True,
                "v2ModuleZipH1MismatchObserved": False,
                "v2GoModH1MismatchObserved": False,
                "authenticationRelated": False,
                "credentialRelated": False,
                "ownerProofRelated": False,
            },
        ),
        "E_ROOT_CAUSE",
        "root cause",
    )

    policy = exact_keys(
        recovery.get("selectedV3Policy"),
        {
            "selectionStatus",
            "resourceModel",
            "fullFreshTupleCountRequired",
            "resourceCountPerTuple",
            "maximumRequestCount",
            "expectedSuccessRequestCount",
            "sequentialOrderRequired",
            "resourceOrderPerTuple",
            "requestOrdinalRule",
            "zipResource",
            "modResource",
            "absoluteLimits",
            "requestPolicy",
            "requiredCounterSchema",
            "failureContract",
            "successContract",
            "forbiddenOperations",
        },
        "selectedV3Policy",
    )
    require(
        policy.get("selectionStatus")
        == "selected_for_v3_implementation_not_execution"
        and policy.get("resourceModel")
        == "fresh_exact_mod_then_zip_pair_for_each_tuple"
        and policy.get("fullFreshTupleCountRequired") == 19
        and policy.get("resourceCountPerTuple") == 2
        and policy.get("maximumRequestCount") == 38
        and policy.get("expectedSuccessRequestCount") == 38
        and policy.get("sequentialOrderRequired") is True
        and policy.get("resourceOrderPerTuple") == ["mod", "zip"]
        and typed_equal(
            policy.get("requestOrdinalRule"),
            {
                "mod": "two_times_tuple_order_minus_one",
                "zip": "two_times_tuple_order",
            },
        ),
        "E_POLICY",
        "v3 resource model",
    )
    require(
        typed_equal(
            policy.get("zipResource"),
            {
                "urlSource": "source_identity_decision_wave_tuple_url",
                "requiredSuffix": ".zip",
                "allowedContentTypes": [
                    "application/zip",
                    "application/octet-stream",
                ],
                "moduleZipH1MatchRequired": True,
                "embeddedRootGoModRequired": False,
                "embeddedRootGoModMustMatchExternalModWhenPresent": True,
                "zipStructureAndPrefixValidationRequired": True,
                "compressionRatioPolicy": "non_gating_bounded_telemetry",
            },
        )
        and typed_equal(
            policy.get("modResource"),
            {
                "urlDerivation": (
                    "replace_exact_terminal_dot_zip_with_dot_mod"
                ),
                "requiredSuffix": ".mod",
                "allowedContentTypes": [
                    "text/plain",
                    "application/octet-stream",
                ],
                "goModH1MatchRequired": True,
                "goModH1Algorithm": (
                    "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod"
                ),
                "canonicalFileName": "go.mod",
                "sourceBytes": "exact_mod_response_body",
                "utf8Required": True,
                "nulByteForbidden": True,
                "exactModuleDirectiveRequired": True,
            },
        ),
        "E_POLICY",
        "resource validation",
    )
    require(
        typed_equal(
            policy.get("absoluteLimits"),
            {
                "maximumZipResponseBytesPerTuple": 16777216,
                "maximumAggregateZipResponseBytes": 134217728,
                "maximumModResponseBytesPerTuple": 1048576,
                "maximumAggregateModResponseBytes": 8388608,
                "maximumAggregateResponseBytes": 142606336,
                "maximumRetainedBytes": 142606336,
                "maximumEntriesPerArchive": 16384,
                "maximumAggregateEntries": 131072,
                "maximumCentralDirectoryBytesPerArchive": 8388608,
                "maximumSingleFileBytes": 16777216,
                "maximumUncompressedBytesPerArchive": 268435456,
                "maximumAggregateUncompressedBytes": 1073741824,
                "maximumPathBytes": 1024,
                "maximumPathComponents": 64,
                "maximumComponentBytes": 255,
                "maximumJsonReceiptOrFailureBytes": 2097152,
                "perRequestDeadlineMilliseconds": 30000,
                "wholeWaveDeadlineMilliseconds": 600000,
            },
        ),
        "E_LIMITS",
        "absolute limits",
    )
    require(
        typed_equal(
            policy.get("requestPolicy"),
            {
                "scheme": "https",
                "allowedHost": "proxy.golang.org",
                "successStatusCode": 200,
                "tlsCertificateValidationRequired": True,
                "tlsHostnameValidationRequired": True,
                "ambientProxyAllowed": False,
                "redirectsAllowed": False,
                "credentialsAllowed": False,
                "authenticationChallengeAllowed": False,
                "urlQueryAllowed": False,
                "urlFragmentAllowed": False,
                "automaticRetryAllowed": False,
                "alternateMirrorAllowed": False,
            },
        ),
        "E_REQUEST_POLICY",
        "request policy",
    )
    require(
        typed_equal(
            policy.get("requiredCounterSchema"),
            {
                "networkRequestAttemptCount": True,
                "responseBodyCompletedCount": True,
                "validatedAndStagedResourceCount": True,
                "validatedModResourceCount": True,
                "validatedZipResourceCount": True,
                "validatedAndStagedTupleCount": True,
                "successValues": {
                    "networkRequestAttemptCount": 38,
                    "responseBodyCompletedCount": 38,
                    "validatedAndStagedResourceCount": 38,
                    "validatedModResourceCount": 19,
                    "validatedZipResourceCount": 19,
                    "validatedAndStagedTupleCount": 19,
                    "acceptedArtifactCount": 38,
                },
                "legacyCompletedRequestCountForbidden": True,
            },
        ),
        "E_COUNTERS",
        "counter schema",
    )
    require(
        typed_equal(
            policy.get("failureContract"),
            {
                "firstMismatchStopsWave": True,
                "claimAndFailureReceiptRetained": True,
                "partialStagingRemoved": True,
                "partialAcceptedSetAllowed": False,
                "finalSetPublished": False,
                "automaticRetryAllowed": False,
                "newRecoveryDecisionRequired": True,
                "failureTupleAndResourceKindRequired": True,
                "responseBodiesOrCredentialsRecorded": False,
            },
        )
        and typed_equal(
            policy.get("successContract"),
            {
                "retainedZipCount": 19,
                "retainedModCount": 19,
                "retainedResourceCount": 38,
                "acquisitionNamespaceRegularFileCount": 41,
                "orderedRowsContainSeparateZipAndModByteSizeAndSha256": True,
                "orderedRowsContainModuleZipH1AndGoModH1": True,
                "stableNoFollowIndependentReopenRequiredBeforePublication": True,
                "allResourcesReparsedAndRehashedBeforePublication": True,
                "successReceiptWrittenBeforeManifest": True,
                "manifestWrittenLast": True,
                "postPublishRetryForbidden": True,
            },
        ),
        "E_ATOMICITY",
        "failure or success contract",
    )
    require(
        typed_equal(
            policy.get("forbiddenOperations"),
            {
                "packageManager": True,
                "goCommand": True,
                "gitCommand": True,
                "shellOrSubprocess": True,
                "compiler": True,
                "sourceExtraction": True,
                "sourceLoadOrExecution": True,
                "runtimeOrProductNetwork": True,
                "device": True,
                "deployment": True,
            },
        ),
        "E_SCOPE",
        "forbidden operations",
    )

    require(
        typed_equal(
            recovery.get("v1AndV2PreservationContract"),
            {
                "v1ClaimDeletionAllowed": False,
                "v1FailureReceiptDeletionAllowed": False,
                "v1PermitReuseAllowed": False,
                "v1RunnerExecuteAllowed": False,
                "v2ClaimDeletionAllowed": False,
                "v2FailureReceiptDeletionAllowed": False,
                "v2PermitReuseAllowed": False,
                "v2RunnerExecuteAllowed": False,
                "v1OrV2AutomaticRetryAllowed": False,
                "v1OrV2StagingResumeAllowed": False,
            },
        ),
        "E_PRESERVATION",
        "v1 and v2 preservation",
    )
    require(
        typed_equal(
            recovery.get("v3NamespaceContract"),
            {
                "claimPath": V3_CLAIM_PATH,
                "stagingParentPath": DEPENDENCY_PARENT,
                "stagingNamePrefix": ".wave-1-v3-staging-",
                "finalDirectoryPath": f"{V3_WAVE_PATH}/accepted",
                "successReceiptPath": V3_SUCCESS_PATH,
                "failureReceiptPath": V3_FAILURE_PATH,
                "manifestPath": V3_MANIFEST_PATH,
                "zipOutputNamePattern": (
                    "{order:03d}-{tuple_sha256_prefix20}.zip"
                ),
                "modOutputNamePattern": (
                    "{order:03d}-{tuple_sha256_prefix20}.mod"
                ),
                "fullFreshTupleCountRequired": 19,
                "resumeFromV1OrV2StagingAllowed": False,
            },
        ),
        "E_NAMESPACE",
        "v3 namespace",
    )
    require(
        typed_equal(
            recovery.get("independentReadbackContract"),
            {
                "requiredAfterAcquisitionSuccess": True,
                "runnerSelfCheckQualifiesAsIndependentReadback": False,
                "checkerPath": (
                    "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
                ),
                "checkerTestsPath": (
                    "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
                ),
                "receiptPath": (
                    f"{BASE}/bounded-dependency-source-acquisition-"
                    "wave1-readback-v1.json"
                ),
                "manifestPath": (
                    f"{BASE}/bounded-dependency-source-acquisition-"
                    "wave1-readback-manifest-v1.json"
                ),
                "exactRetainedResourceCount": 38,
                "recomputeRawSha256": True,
                "recomputeModuleZipH1": True,
                "recomputeGoModH1": True,
                "recheckEmbeddedModParityWhenPresent": True,
                "recheckExactInventoryModeLinkCountAndStableIdentity": True,
                "regularFileCountMeaning": (
                    "exact_reserved_regular_file_path_set_not_recursive_"
                    "directory_count"
                ),
                "acquisitionSuccessRegularFileCount": 41,
                "postReadbackRegularFileCount": 43,
                "networkAllowed": False,
                "sourceExtractionAllowed": False,
                "sourceLoadOrExecutionAllowed": False,
                "receiptAndManifestWritesOnly": True,
                "manifestWrittenLast": True,
            },
        ),
        "E_READBACK",
        "independent readback contract",
    )
    require(
        typed_equal(
            recovery.get("authority"),
            {
                "recoveryDesignRecorded": True,
                "v3RunnerImplementationAuthorized": True,
                "v3CheckerAndTestsAuthorized": True,
                "v3ExecutionPermitPreparationAuthorized": True,
                "networkAuthorized": False,
                "dependencySourceAcquisitionAuthorized": False,
                "sourceExtractionAuthorized": False,
                "packageManagerAuthorized": False,
                "shellOrSubprocessAuthorized": False,
                "compilerAuthorized": False,
                "sourceLoadOrExecutionAuthorized": False,
                "runtimeOrProductNetworkAuthorized": False,
                "deviceAuthorized": False,
                "deploymentAuthorized": False,
                "gitWriteAuthorized": False,
            },
        ),
        "E_AUTHORITY",
        "authority",
    )
    require(
        typed_equal(
            recovery.get("personalProjectBoundary"),
            {
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "privateKeyRequired": False,
                "tokenRequired": False,
                "passwordRequired": False,
                "signatureRequired": False,
                "userActionRequired": False,
                "productEndpointAuthenticationChanged": False,
            },
        ),
        "E_AUTH_BOUNDARY",
        "personal project boundary",
    )
    require(
        typed_equal(
            recovery.get("closure"),
            {
                "openFindingCount": 19,
                "findingsClosedByRecoveryDecision": 0,
                "waveAcquired": False,
                "graphFixedPointReached": False,
                "dependencySourceReviewed": False,
                "dependencyClosureComplete": False,
                "semanticClosureComplete": False,
                "rungThreeComplete": False,
                "candidateSelected": False,
                "librarySelected": False,
            },
        ),
        "E_CLOSURE",
        "closure",
    )

    wave = source.get("wave")
    require(isinstance(wave, dict), "E_SOURCE", "source wave")
    tuples = wave.get("tuples")
    require(isinstance(tuples, list) and len(tuples) == 19, "E_SOURCE", "tuples")
    failed_tuple = tuples[10]
    require(
        isinstance(failed_tuple, dict)
        and failed_tuple.get("order") == 11
        and failed_tuple.get("tupleId") == EXPECTED_TUPLE_ID
        and failed_tuple.get("module") == EXPECTED_MODULE
        and failed_tuple.get("version") == EXPECTED_VERSION
        and failed_tuple.get("moduleZipH1")
        == "h1:vj9j/u1bqnvCEfJOwUhtlOARqs3+rkHYY13jYWTU97c="
        and failed_tuple.get("goModH1")
        == "h1:J7Y8YcW2NihsgmVo/mv3lAwl/skON4iLHjSsI+c5H38="
        and str(failed_tuple.get("url", "")).endswith("/v1.1.1.zip"),
        "E_SOURCE",
        "failed source tuple",
    )

    validate_content_binding(
        recovery,
        "decision_without_contentBinding",
        EXPECTED_RECOVERY_CONTENT_SHA256,
        "recovery",
    )


def validate_terminal_namespace(reader: SafeReader) -> None:
    for path in (
        V1_SUCCESS_PATH,
        V1_MANIFEST_PATH,
        V1_ACCEPTED_PATH,
        V2_SUCCESS_PATH,
        V2_MANIFEST_PATH,
        V2_ACCEPTED_PATH,
        V3_CLAIM_PATH,
        V3_SUCCESS_PATH,
        V3_FAILURE_PATH,
        V3_MANIFEST_PATH,
        V3_WAVE_PATH,
    ):
        require(not reader.exists(path), "E_NAMESPACE", f"unexpected artifact {path}")
    siblings = reader.list_directory(DEPENDENCY_PARENT)
    require(
        not any(
            name.startswith(prefix)
            for name in siblings
            for prefix in (
                ".wave-1-v1-staging-",
                ".wave-1-v2-staging-",
                ".wave-1-v3-staging-",
            )
        ),
        "E_NAMESPACE",
        "staging artifact retained",
    )


def validate_repository(
    root: Path = ROOT,
    *,
    before_final_barrier: Callable[[], None] | None = None,
) -> dict[str, Any]:
    reader = SafeReader(root)
    try:
        raw = {
            path: reader.read(path)
            for path in EXPECTED_RAW_SHA256
        }
        for path, expected in EXPECTED_RAW_SHA256.items():
            require(
                sha256_bytes(raw[path]) == expected,
                "E_RAW_BINDING",
                f"raw binding {path}",
            )
        for path, expected_size in (
            (CLAIM_V1_PATH, 445),
            (FAILURE_V1_PATH, 858),
            (CLAIM_V2_PATH, 482),
            (FAILURE_V2_PATH, 1174),
        ):
            snapshot = reader.snapshot(path)
            mode = stat.S_IMODE(snapshot.state[2])
            require(
                len(snapshot.raw) == expected_size
                and mode == 0o600
                and snapshot.state[4] == 1,
                "E_TERMINAL",
                f"terminal metadata {path}",
            )

        source = strict_json(raw[SOURCE_DECISION_PATH], "source decision")
        recovery_v1 = strict_json(raw[RECOVERY_V1_PATH], "recovery v1")
        permit_v2 = strict_json(raw[PERMIT_V2_PATH], "permit v2")
        claim_v2 = strict_json(raw[CLAIM_V2_PATH], "claim v2")
        failure_v2 = strict_json(raw[FAILURE_V2_PATH], "failure v2")
        recovery = strict_json(raw[RECOVERY_PATH], "recovery v2")

        validate_content_binding(
            source,
            "decision_without_contentBinding",
            EXPECTED_SOURCE_CONTENT_SHA256,
            "source decision",
        )
        validate_content_binding(
            recovery_v1,
            "decision_without_contentBinding",
            EXPECTED_RECOVERY_V1_CONTENT_SHA256,
            "recovery v1",
        )
        validate_content_binding(
            permit_v2,
            "permit_without_contentBinding",
            EXPECTED_PERMIT_V2_CONTENT_SHA256,
            "permit v2",
        )
        validate_claim_v2(claim_v2)
        validate_failure_v2(failure_v2)
        validate_recovery(recovery, source)
        validate_terminal_namespace(reader)

        if before_final_barrier is not None:
            before_final_barrier()
        reader.verify()
        validate_terminal_namespace(reader)
        return {
            "decisionId": recovery["decisionId"],
            "status": recovery["status"],
            "failedTupleId": EXPECTED_TUPLE_ID,
            "networkRequestAttemptCount": 11,
            "responseBodyCompletedCount": 11,
            "validatedAndStagedTupleCount": 10,
            "v3MaximumRequestCount": 38,
            "v3ExpectedRetainedResourceCount": 38,
            "v3ExecutionAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        reader.close()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate dependency wave-one v2 recovery decision"
    )
    parser.parse_args(argv)
    return argparse.Namespace()


def main(argv: Sequence[str] | None = None) -> int:
    parse_args(sys.argv[1:] if argv is None else argv)
    require_isolated_interpreter()
    try:
        validate_repository()
    except CheckError as error:
        print(f"[{error.code}] {error}", file=sys.stderr)
        return 1
    except Exception:
        print("[E_INTERNAL] recovery validation failed", file=sys.stderr)
        return 1
    print(
        "G2 Pion dependency wave-one recovery decision v2 passed: v2 consumed "
        "after eleven ZIP responses, no final set; v3 exact 19 mod-plus-zip "
        "pairs selected for implementation only; no authentication required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
