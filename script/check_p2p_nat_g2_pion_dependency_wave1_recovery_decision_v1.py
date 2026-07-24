#!/usr/bin/env python3
"""Validate the consumed v1 dependency-wave failure and v2 recovery design."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
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
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json"
)
RECOVERY_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.json"
)
RECOVERY_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.md"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v1.json"
)
CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v1.claim"
)
V1_SUCCESS_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v1.json"
)
V1_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v1.json"
)
V1_WAVE_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1"
)
V1_STAGING_PARENT = "build/offline-source/pion-ice-v4.3.0/dependencies"
V1_STAGING_PREFIX = ".wave-1-v1-staging-"

RUNNER_PATH = "script/acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
RUNNER_TEST_PATH = "script/test_acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v1.py"
)
PERMIT_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_execution_permit_v1.py"
)

EXPECTED_RAW_SHA256 = {
    SOURCE_DECISION_PATH: (
        "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
    ),
    PERMIT_PATH: (
        "153e6ed84a8b8942d7420e9f5e184c03b105622b6a9b6d7f29e656e683058971"
    ),
    RUNNER_PATH: (
        "571985e002c6b819bfbe7153bb445beef27fdcad239a289b492005435c2a0356"
    ),
    RUNNER_TEST_PATH: (
        "a46a882af332c287c2c34ad257f49a3d157186b663382567ddc64291fc0ccf60"
    ),
    PERMIT_CHECKER_PATH: (
        "014eaf714c41753e328679f1cc4f2ff0fe644039dbc1156406ad547a9f22bbe5"
    ),
    PERMIT_TEST_PATH: (
        "088189df0fc4c77bb91f152b437381910de6f5a2862b4550a27cd00da0fd6423"
    ),
    CLAIM_PATH: (
        "560bbb6028588b91a2d7f35ae826cdcc68940566656a279b2dbe7b9352e161d5"
    ),
    FAILURE_PATH: (
        "cdf4d75aeddb2accc4720c2ef8a606b22e333eac9aea2196a010f9383dc877fa"
    ),
    RECOVERY_PATH: (
        "313e548e8d538ccc582f4d1c74618823d31b45915b4a5124378bc0d8b98315c2"
    ),
    RECOVERY_READER_PATH: (
        "02fc75469af753bec9070b893b8755762b05262f1c4d1ced9da67645d1e127e9"
    ),
}

EXPECTED_SOURCE_CONTENT_SHA256 = (
    "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201"
)
EXPECTED_PERMIT_CONTENT_SHA256 = (
    "99f6daf629a6d0424b3ee5aa4a8a774322c65fcde94f3f9ae76599bb1c7cc240"
)
EXPECTED_RECOVERY_CONTENT_SHA256 = (
    "8cdcccbea4318d41f44da78000f3e4161251a5ad9542543c2962d4767ed1e968"
)
EXPECTED_TUPLE_ID = "wave1-002-c4e8ffbb48de"
EXPECTED_MODULE = "github.com/pion/dtls/v3"
EXPECTED_VERSION = "v3.1.5"
MAXIMUM_FILE_BYTES = 4 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def exact_keys(
    value: Any,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
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

    def exists(self, relative: str) -> bool:
        try:
            parent, name = self._open_parent(relative)
        except CheckError:
            return False
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
        f"{label} content binding fields",
    )
    payload = dict(document)
    payload.pop("contentBinding")
    require(
        sha256_bytes(canonical_json_bytes(payload)) == expected_digest,
        "E_BINDING",
        f"{label} content binding digest",
    )


def validate_claim(claim: Mapping[str, Any]) -> None:
    exact_keys(
        claim,
        {
            "claimType",
            "schemaVersion",
            "permitId",
            "permitContentSha256",
            "decisionContentSha256",
            "createdAt",
            "rule",
        },
        "claim",
    )
    require(
        claim["claimType"]
        == "aetherlink.g2-pion-dependency-wave1-one-use-claim",
        "E_CLAIM",
        "claim type",
    )
    require(claim["schemaVersion"] == "1.0", "E_CLAIM", "claim schema")
    require(
        claim["permitId"]
        == "g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v1",
        "E_CLAIM",
        "claim permit",
    )
    require(
        claim["permitContentSha256"] == EXPECTED_PERMIT_CONTENT_SHA256,
        "E_CLAIM",
        "claim permit binding",
    )
    require(
        claim["decisionContentSha256"] == EXPECTED_SOURCE_CONTENT_SHA256,
        "E_CLAIM",
        "claim decision binding",
    )
    require(
        re.fullmatch(r"2026-07-23T18:26:45Z", claim["createdAt"]) is not None,
        "E_CLAIM",
        "claim timestamp",
    )
    require(
        claim["rule"] == "claim_persists_after_any_network_attempt_and_blocks_retry",
        "E_CLAIM",
        "claim rule",
    )


def validate_failure(failure: Mapping[str, Any]) -> None:
    exact_keys(
        failure,
        {
            "documentType",
            "schemaVersion",
            "status",
            "result",
            "permitId",
            "permitContentSha256",
            "failureCode",
            "phase",
            "failedTupleId",
            "safeNumericObservations",
            "attemptedRequestCount",
            "completedRequestCount",
            "acceptedArtifactCount",
            "claimRetained",
            "claimSha256",
            "finalSetPublished",
            "automaticRetryAllowed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
            "nextAction",
        },
        "failure",
    )
    expected = {
        "documentType": "aetherlink.g2-pion-dependency-wave1-acquisition-failure",
        "schemaVersion": "1.0",
        "status": "wave1_acquisition_failed_permit_consumed",
        "result": "no_dependency_source_set_accepted",
        "permitId": (
            "g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v1"
        ),
        "permitContentSha256": EXPECTED_PERMIT_CONTENT_SHA256,
        "failureCode": "E_ZIP_RATIO",
        "phase": "zip",
        "failedTupleId": None,
        "safeNumericObservations": {},
        "attemptedRequestCount": 2,
        "completedRequestCount": 1,
        "acceptedArtifactCount": 0,
        "claimRetained": True,
        "claimSha256": EXPECTED_RAW_SHA256[CLAIM_PATH],
        "finalSetPublished": False,
        "automaticRetryAllowed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "prepare_new_versioned_wave1_recovery_decision",
    }
    require(typed_equal(failure, expected), "E_FAILURE", "terminal failure fields")


def validate_recovery(
    recovery: Mapping[str, Any],
    source: Mapping[str, Any],
    permit: Mapping[str, Any],
) -> dict[str, Any]:
    require(
        recovery.get("documentType")
        == "aetherlink.g2-pion-dependency-wave1-recovery-decision",
        "E_RECOVERY",
        "recovery document type",
    )
    require(recovery.get("schemaVersion") == "1.0", "E_RECOVERY", "schema")
    require(
        recovery.get("decisionId")
        == "g2-pion-ice-v4.3.0-rung3-dependency-wave1-recovery-decision-v1",
        "E_RECOVERY",
        "decision id",
    )
    require(recovery.get("recordedDate") == "2026-07-24", "E_RECOVERY", "date")
    require(
        recovery.get("status")
        == (
            "wave1_v1_failure_read_back_recovery_v2_design_selected_"
            "execution_not_authorized"
        ),
        "E_RECOVERY",
        "status",
    )
    require(
        recovery.get("result")
        == (
            "v1_ratio_policy_rejected_tuple2_after_two_responses_no_final_set_"
            "v2_bounded_telemetry_policy_selected"
        ),
        "E_RECOVERY",
        "result",
    )
    require(
        recovery.get("nextAction")
        == "prepare_separate_v2_runner_checker_tests_and_execution_permit",
        "E_RECOVERY",
        "next action",
    )
    validate_content_binding(
        recovery,
        "decision_without_contentBinding",
        EXPECTED_RECOVERY_CONTENT_SHA256,
        "recovery",
    )

    bindings = recovery.get("predecessorBindings")
    require(isinstance(bindings, dict), "E_BINDING", "predecessor bindings")
    expected_binding_rows = {
        "sourceIdentityDecision": (
            SOURCE_DECISION_PATH,
            EXPECTED_RAW_SHA256[SOURCE_DECISION_PATH],
            EXPECTED_SOURCE_CONTENT_SHA256,
        ),
        "executionPermitV1": (
            PERMIT_PATH,
            EXPECTED_RAW_SHA256[PERMIT_PATH],
            EXPECTED_PERMIT_CONTENT_SHA256,
        ),
    }
    for key, (path, raw_digest, content_digest) in expected_binding_rows.items():
        require(
            typed_equal(
                bindings.get(key),
                {
                    "path": path,
                    "rawSha256": raw_digest,
                    "contentSha256": content_digest,
                },
            ),
            "E_BINDING",
            key,
        )
    for key, path in (
        ("runnerV1", RUNNER_PATH),
        ("runnerTestsV1", RUNNER_TEST_PATH),
        ("permitCheckerV1", PERMIT_CHECKER_PATH),
        ("permitCheckerTestsV1", PERMIT_TEST_PATH),
    ):
        require(
            typed_equal(
                bindings.get(key),
                {"path": path, "rawSha256": EXPECTED_RAW_SHA256[path]},
            ),
            "E_BINDING",
            key,
        )

    tuples = source.get("wave", {}).get("tuples")
    require(isinstance(tuples, list) and len(tuples) == 19, "E_DERIVATION", "tuples")
    second = tuples[1]
    require(
        second.get("order") == 2
        and second.get("tupleId") == EXPECTED_TUPLE_ID
        and second.get("module") == EXPECTED_MODULE
        and second.get("version") == EXPECTED_VERSION,
        "E_DERIVATION",
        "derived second tuple",
    )
    interpretation = recovery.get("failureInterpretation")
    expected_interpretation = {
        "derivedFailedTupleId": EXPECTED_TUPLE_ID,
        "derivedFailedModule": EXPECTED_MODULE,
        "derivedFailedVersion": EXPECTED_VERSION,
        "receiptFailedTupleId": None,
        "derivation": (
            "ordered_execution_attempted_2_completed_validated_1_and_failure_phase_zip"
        ),
        "networkRequestAttemptCount": 2,
        "responseBodyCompletedCount": 2,
        "validatedAndStagedTupleCount": 1,
        "failedEntryIdentityEstablished": False,
        "failedEntrySizeEstablished": False,
        "failedEntryCompressionRatioEstablished": False,
        "failedResponseRawSha256Established": False,
        "stagingRetained": False,
        "acceptedFinalSetRetained": False,
        "v1PreflightCanClassifyTerminalState": False,
        "v1PreflightFailureCodeAfterConsumption": "E_PERMIT_VALIDATION",
    }
    require(
        typed_equal(interpretation, expected_interpretation),
        "E_DERIVATION",
        "failure interpretation",
    )

    root_cause = recovery.get("rootCause")
    require(
        typed_equal(
            root_cause,
            {
                "classification": "uncalibrated_compatibility_gate",
                "v1CompressionRatioLimit": 200,
                "v1RatioCompatibilityTestPresent": False,
                "v1TupleContextPropagationPresentForRatioFailure": False,
                "v1CounterNameAccuratelyDescribesCompletedResponses": False,
                "authenticationRelated": False,
            },
        ),
        "E_POLICY",
        "root cause",
    )

    policy = recovery.get("selectedV2Policy")
    require(isinstance(policy, dict), "E_POLICY", "selected policy")
    require(
        policy.get("selectionStatus")
        == "selected_for_v2_implementation_not_execution"
        and policy.get("compressionRatioPolicy")
        == "non_gating_bounded_telemetry",
        "E_POLICY",
        "ratio policy",
    )
    source_limits = source.get("resourceLimits")
    expected_limits = {
        key: source_limits[key]
        for key in (
            "maximumResponseBytesPerArchive",
            "maximumAggregateResponseBytes",
            "maximumEntriesPerArchive",
            "maximumAggregateEntries",
            "maximumSingleFileBytes",
            "maximumUncompressedBytesPerArchive",
            "maximumAggregateUncompressedBytes",
            "perRequestDeadlineMilliseconds",
            "wholeWaveDeadlineMilliseconds",
        )
    }
    require(
        typed_equal(policy.get("absoluteLimitsRetained"), expected_limits),
        "E_POLICY",
        "absolute limits",
    )
    require(
        typed_equal(
            policy.get("requiredCompressionTelemetry"),
            {
                "recordPerArchiveMaximum": True,
                "recordEntryOrdinal": True,
                "recordUncompressedBytes": True,
                "recordCompressedBytes": True,
                "useExactIntegerNumeratorDenominator": True,
                "floatingPointRatioForbidden": True,
                "entryNameOrBodyPublicationRequired": False,
            },
        ),
        "E_POLICY",
        "telemetry",
    )
    require(
        typed_equal(
            policy.get("requiredCounterSchema"),
            {
                "networkRequestAttemptCount": True,
                "responseBodyCompletedCount": True,
                "validatedAndStagedTupleCount": True,
                "legacyCompletedRequestCountForbidden": True,
            },
        ),
        "E_POLICY",
        "counter schema",
    )
    require(
        typed_equal(
            recovery.get("v1PreservationContract"),
            {
                "v1ClaimDeletionAllowed": False,
                "v1FailureReceiptDeletionAllowed": False,
                "v1PermitReuseAllowed": False,
                "v1RunnerExecuteAllowed": False,
                "v1AutomaticRetryAllowed": False,
                "v1StagingResumeAllowed": False,
            },
        ),
        "E_PRESERVATION",
        "v1 preservation",
    )
    namespace = recovery.get("v2NamespaceContract")
    expected_namespace = {
        "claimPath": (
            "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v2.claim"
        ),
        "stagingParentPath": V1_STAGING_PARENT,
        "stagingNamePrefix": ".wave-1-v2-staging-",
        "finalDirectoryPath": (
            "build/offline-source/pion-ice-v4.3.0/dependencies/"
            "wave-1-v2/accepted"
        ),
        "successReceiptPath": (
            f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v2.json"
        ),
        "failureReceiptPath": (
            f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v2.json"
        ),
        "manifestPath": (
            f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v2.json"
        ),
        "fullFreshTupleCountRequired": 19,
        "resumeFromDeletedV1StagingAllowed": False,
    }
    require(
        typed_equal(namespace, expected_namespace),
        "E_NAMESPACE",
        "v2 namespace",
    )

    authority = recovery.get("authority")
    require(isinstance(authority, dict), "E_AUTHORITY", "authority")
    require(
        authority.get("recoveryDesignRecorded") is True
        and authority.get("v2RunnerImplementationAuthorized") is True
        and authority.get("v2CheckerAndTestsAuthorized") is True
        and authority.get("v2ExecutionPermitPreparationAuthorized") is True,
        "E_AUTHORITY",
        "preparation authority",
    )
    for key in (
        "networkAuthorized",
        "dependencySourceAcquisitionAuthorized",
        "sourceExtractionAuthorized",
        "packageManagerAuthorized",
        "shellOrSubprocessAuthorized",
        "compilerAuthorized",
        "sourceLoadOrExecutionAuthorized",
        "runtimeOrProductNetworkAuthorized",
        "deviceAuthorized",
        "deploymentAuthorized",
        "gitWriteAuthorized",
    ):
        require(authority.get(key) is False, "E_AUTHORITY", key)
    personal = recovery.get("personalProjectBoundary")
    require(isinstance(personal, dict), "E_AUTHORITY", "personal project")
    for key in (
        "repositoryOwnerIdentityProofRequired",
        "externalAuthenticationRequired",
        "privateKeyRequired",
        "tokenRequired",
        "passwordRequired",
        "signatureRequired",
        "userActionRequired",
        "productEndpointAuthenticationChanged",
    ):
        require(personal.get(key) is False, "E_AUTHORITY", key)

    closure = recovery.get("closure")
    require(
        isinstance(closure, dict)
        and closure.get("openFindingCount") == 19
        and closure.get("findingsClosedByRecoveryDecision") == 0,
        "E_CLOSURE",
        "closure counts",
    )
    for key in (
        "waveAcquired",
        "graphFixedPointReached",
        "dependencySourceReviewed",
        "dependencyClosureComplete",
        "semanticClosureComplete",
        "rungThreeComplete",
        "candidateSelected",
        "librarySelected",
    ):
        require(closure.get(key) is False, "E_CLOSURE", key)

    require(
        permit.get("status")
        == "wave1_dependency_source_acquisition_authorized_not_consumed"
        and permit.get("contentBinding", {}).get("sha256")
        == EXPECTED_PERMIT_CONTENT_SHA256,
        "E_BINDING",
        "historical permit",
    )
    return second


def validate_reader(raw: bytes) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CheckError("E_READER", "reader UTF-8") from error
    for token in (
        "authorize network access",
        "No user authentication is required",
        "github.com/pion/dtls/v3@v3.1.5",
        "completedRequestCount=1",
        "response-body count",
        "failedTupleId",
        "non-gating",
        "16 MiB per response",
        "1 GiB aggregate uncompressed bytes",
        "may not be deleted, reused, resumed",
        "19 tuples",
    ):
        require(token in text, "E_READER", f"reader missing {token}")


def validate_v1_terminal_namespace(reader: SafeReader) -> None:
    parent_names = reader.list_directory(V1_STAGING_PARENT)
    wave_names = reader.list_directory(V1_WAVE_DIRECTORY)
    require(
        not any(name.startswith(V1_STAGING_PREFIX) for name in parent_names),
        "E_TERMINAL_STATE",
        "v1 staging remains",
    )
    require(wave_names == [], "E_TERMINAL_STATE", "v1 wave directory not empty")
    require(
        not reader.exists(V1_SUCCESS_PATH)
        and not reader.exists(V1_MANIFEST_PATH),
        "E_TERMINAL_STATE",
        "v1 success artifact present",
    )


def validate_repository(
    root: Path = ROOT,
    before_final_barrier: Callable[[SafeReader], None] | None = None,
) -> dict[str, Any]:
    require_isolated_interpreter()
    reader = SafeReader(root)
    try:
        raw = {
            path: reader.read(path)
            for path in (
                SOURCE_DECISION_PATH,
                PERMIT_PATH,
                RUNNER_PATH,
                RUNNER_TEST_PATH,
                PERMIT_CHECKER_PATH,
                PERMIT_TEST_PATH,
                CLAIM_PATH,
                FAILURE_PATH,
                RECOVERY_PATH,
                RECOVERY_READER_PATH,
            )
        }
        for path, expected in EXPECTED_RAW_SHA256.items():
            require(
                sha256_bytes(raw[path]) == expected,
                "E_BINDING",
                f"{path} raw binding",
            )
        claim_snapshot = next(
            snapshot for snapshot in reader.snapshots if snapshot.path == CLAIM_PATH
        )
        failure_snapshot = next(
            snapshot for snapshot in reader.snapshots if snapshot.path == FAILURE_PATH
        )
        for snapshot, expected_size in (
            (claim_snapshot, 445),
            (failure_snapshot, 858),
        ):
            info = os.fstat(snapshot.fd)
            require(
                stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1
                and info.st_size == expected_size,
                "E_FILESYSTEM",
                f"{snapshot.path} protected artifact metadata",
            )

        source = strict_json(raw[SOURCE_DECISION_PATH], "source decision")
        permit = strict_json(raw[PERMIT_PATH], "permit")
        claim = strict_json(raw[CLAIM_PATH], "claim")
        failure = strict_json(raw[FAILURE_PATH], "failure")
        recovery = strict_json(raw[RECOVERY_PATH], "recovery")
        validate_content_binding(
            source,
            "decision_without_contentBinding",
            EXPECTED_SOURCE_CONTENT_SHA256,
            "source decision",
        )
        validate_content_binding(
            permit,
            "permit_without_contentBinding",
            EXPECTED_PERMIT_CONTENT_SHA256,
            "permit",
        )
        validate_claim(claim)
        validate_failure(failure)
        second = validate_recovery(recovery, source, permit)
        validate_reader(raw[RECOVERY_READER_PATH])

        validate_v1_terminal_namespace(reader)
        reader.verify()
        if before_final_barrier is not None:
            before_final_barrier(reader)
        reader.verify()
        validate_v1_terminal_namespace(reader)
        return {
            "decision": recovery,
            "sourceDecision": source,
            "historicalPermit": permit,
            "derivedFailedTuple": second,
            "status": recovery["status"],
            "failureCode": failure["failureCode"],
            "networkRequestAttemptCount": 2,
            "responseBodyCompletedCount": 2,
            "validatedAndStagedTupleCount": 1,
            "acceptedArtifactCount": 0,
            "v1PermitConsumed": True,
            "v1AutomaticRetryAllowed": False,
            "v2ExecutionAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "trackedAndTerminalFileReadCount": len(raw),
            "fileWriteCount": 0,
            "networkOperationCount": 0,
        }
    finally:
        reader.close()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root used only by mutation tests.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        result = validate_repository(args.root)
    except CheckError as error:
        print(f"[{error.code}] {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("[E_INTERNAL] recovery validation failed", file=sys.stderr)
        return 1
    print(
        "G2 Pion dependency wave-one recovery decision v1 passed: v1 consumed "
        "after two response bodies, no final set; v2 design preparation only, "
        "no user authentication required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
