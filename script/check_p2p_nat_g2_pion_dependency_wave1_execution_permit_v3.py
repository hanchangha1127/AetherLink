#!/usr/bin/env python3
"""Validate the separate G2 Pion dependency wave-one v3 execution permit.

The checker is read-only.  It binds the immutable source and recovery
decisions, both consumed terminal attempts, the v3 runner and tests, the
independent readback checker and tests, the exact reader-contract bytes, and
this checker and its mutation tests.  The permit is deliberately loaded from
the repository and validated by its canonical content binding; this source
never embeds a permit raw hash or its own raw hash, avoiding a checker/permit
hash cycle.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import types
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
SOURCE_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
RECOVERY_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json"
)
RECOVERY_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_recovery_decision_v2.py"
)
RECOVERY_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_recovery_decision_v2.py"
)
RUNNER_PATH = "script/acquire_p2p_nat_g2_pion_dependency_wave1_v3_once.py"
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_dependency_wave1_v3_once.py"
)
READBACK_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
)
READBACK_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v3.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_execution_permit_v3.py"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v3.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v3.md"
)

V1_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v1.claim"
)
V1_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v1.json"
)
V2_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v2.claim"
)
V2_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v2.json"
)
DEPENDENCY_PARENT = "build/offline-source/pion-ice-v4.3.0/dependencies"
V3_CLAIM_PATH = f"{DEPENDENCY_PARENT}/.wave-1-v3.claim"
V3_STAGING_PREFIX = ".wave-1-v3-staging-"
V3_FINAL_DIRECTORY = f"{DEPENDENCY_PARENT}/wave-1-v3/accepted"
V3_SUCCESS_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v3.json"
)
V3_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v3.json"
)
V3_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v3.json"
)
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json"
)

EXPECTED_DATE = "2026-07-24"
EXPECTED_SOURCE_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-identity-and-"
    "acquisition-decision-v1"
)
EXPECTED_RECOVERY_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-recovery-decision-v2"
)
EXPECTED_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v3"
)
EXPECTED_STATUS = (
    "wave1_v3_dependency_source_acquisition_authorized_not_consumed"
)
EXPECTED_RESULT = (
    "exact_19_public_proxy_mod_then_zip_pairs_v3_authorized_once_not_executed"
)
EXPECTED_NEXT_ACTION = "execute_bound_dependency_source_wave1_v3_once"
EXPECTED_SCOPE = (
    "single_fresh_exact_19_public_go_proxy_mod_then_zip_pair_source_intake_v3_only"
)

EXPECTED_FIXED_RAW_SHA256 = {
    SOURCE_DECISION_PATH: (
        "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
    ),
    RECOVERY_PATH: (
        "c03ca34315226ad8a59d8857448657c3be2565b22c0583085eb93c6c65ad72fd"
    ),
    RECOVERY_CHECKER_PATH: (
        "25e4f6f6f9d49424428bd9017afad688652467fa8a2c038233dacea1aed15cbc"
    ),
    RECOVERY_TEST_PATH: (
        "48e6d457e84ab3731f8bfed83f0f7775505b97cfd503821485fe7982e86c6da1"
    ),
    PERMIT_READER_PATH: (
        "3dacb2da9085833e874e0e90966bbacddd8a370483ff81ce5434891f234bf327"
    ),
    READBACK_CHECKER_PATH: (
        "f3015f91fac37bc6b139b68e7b663780c00b7b208cfecfeff67208f8b57586b6"
    ),
    READBACK_TEST_PATH: (
        "0c990d98bd7bdb9f62c35a5fbb5a18f0cf4082661e84f5dddfb3aa72dc4c6163"
    ),
    V1_CLAIM_PATH: (
        "560bbb6028588b91a2d7f35ae826cdcc68940566656a279b2dbe7b9352e161d5"
    ),
    V1_FAILURE_PATH: (
        "cdf4d75aeddb2accc4720c2ef8a606b22e333eac9aea2196a010f9383dc877fa"
    ),
    V2_CLAIM_PATH: (
        "d9902cec698026035f9d4e8937114e09d990e868a272ce7d1ec19679a1b2ef77"
    ),
    V2_FAILURE_PATH: (
        "e04e7224ef6288e964f36087170c2ce888f398bb967475d144508ceda0ef44dc"
    ),
}
EXPECTED_SOURCE_CONTENT_SHA256 = (
    "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201"
)
EXPECTED_RECOVERY_CONTENT_SHA256 = (
    "5a41d5bcf7dccb25bb5e558d892620748ea72e12e9f90244242ffdb44e092a93"
)

TOOL_ROWS = (
    ("wave1_v3_recovery_decision_checker", RECOVERY_CHECKER_PATH),
    ("wave1_v3_recovery_decision_checker_mutation_tests", RECOVERY_TEST_PATH),
    ("wave1_v3_execution_permit_reader_contract", PERMIT_READER_PATH),
    ("bounded_dependency_wave1_v3_runner", RUNNER_PATH),
    ("bounded_dependency_wave1_v3_runner_offline_tests", RUNNER_TEST_PATH),
    ("independent_dependency_wave1_v3_readback_checker", READBACK_CHECKER_PATH),
    (
        "independent_dependency_wave1_v3_readback_checker_mutation_tests",
        READBACK_TEST_PATH,
    ),
    ("strict_dependency_wave1_v3_execution_permit_checker", CHECKER_PATH),
    ("execution_permit_v3_checker_mutation_tests", CHECKER_TEST_PATH),
)
EXPECTED_TEST_COUNTS = {
    RECOVERY_TEST_PATH: 39,
    RUNNER_TEST_PATH: 45,
    READBACK_TEST_PATH: 34,
    CHECKER_TEST_PATH: 39,
}

ABSOLUTE_RESOURCE_LIMITS = {
    "maximumSelectedModules": 19,
    "maximumRequestCount": 38,
    "maximumZipResponseBytesPerTuple": 16_777_216,
    "maximumAggregateZipResponseBytes": 134_217_728,
    "maximumModResponseBytesPerTuple": 1_048_576,
    "maximumAggregateModResponseBytes": 8_388_608,
    "maximumAggregateResponseBytes": 142_606_336,
    "maximumRetainedBytes": 142_606_336,
    "maximumEntriesPerArchive": 16_384,
    "maximumAggregateEntries": 131_072,
    "maximumCentralDirectoryBytesPerArchive": 8_388_608,
    "maximumSingleFileBytes": 16_777_216,
    "maximumUncompressedBytesPerArchive": 268_435_456,
    "maximumAggregateUncompressedBytes": 1_073_741_824,
    "maximumPathBytes": 1_024,
    "maximumPathComponents": 64,
    "maximumComponentBytes": 255,
    "maximumJsonReceiptOrFailureBytes": 2_097_152,
    "perRequestDeadlineMilliseconds": 30_000,
    "wholeWaveDeadlineMilliseconds": 600_000,
    "acquisitionSuccessRegularFileCount": 41,
    "postReadbackRegularFileCount": 43,
}

COUNTER_NAMES = (
    "networkRequestAttemptCount",
    "responseBodyCompletedCount",
    "validatedAndStagedResourceCount",
    "validatedModResourceCount",
    "validatedZipResourceCount",
    "validatedAndStagedTupleCount",
)
SUCCESS_COUNTERS = {
    "networkRequestAttemptCount": 38,
    "responseBodyCompletedCount": 38,
    "validatedAndStagedResourceCount": 38,
    "validatedModResourceCount": 19,
    "validatedZipResourceCount": 19,
    "validatedAndStagedTupleCount": 19,
    "acceptedArtifactCount": 38,
}

PERMIT_TOP_LEVEL_KEYS = {
    "documentType",
    "schemaVersion",
    "permitId",
    "recordedDate",
    "status",
    "result",
    "nextAction",
    "scope",
    "personalProjectBoundary",
    "sourceDecisionBinding",
    "recoveryBinding",
    "terminalEvidenceBindings",
    "runnerBinding",
    "toolBindings",
    "interpreterIsolationContract",
    "oneUseConsumption",
    "requestContract",
    "networkAuthority",
    "resourceValidationContract",
    "filesystemWriteAuthority",
    "absoluteResourceLimits",
    "counterContract",
    "receiptFailureManifestContract",
    "reservedRegularFilePaths",
    "independentReadbackContract",
    "authority",
    "execution",
    "closure",
    "nonClaims",
    "contentBinding",
}

EXPECTED_NONCLAIMS = [
    "permit_is_not_execution_success_or_independent_readback_evidence",
    "v1_and_v2_claims_and_failures_remain_terminal_and_are_not_reused",
    "v3_does_not_resume_or_recover_any_v1_or_v2_staging_or_response",
    "separate_mod_validation_does_not_remove_zip_structure_validation",
    "module_zip_h1_go_mod_h1_and_raw_sha256_are_distinct_bindings",
    "nineteen_root_sources_are_not_dependency_fixed_point_evidence",
    "acquisition_is_not_source_license_security_or_semantic_review",
    "runner_self_checks_are_not_independent_readback",
    "permit_does_not_select_a_candidate_library_or_product_endpoint",
]

MAXIMUM_FILE_BYTES = 4 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
H1 = re.compile(r"^h1:[A-Za-z0-9+/]{43}=$")


class CheckError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(code, message)


def require_isolated_interpreter() -> None:
    flags = sys.flags
    require(
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0,
        "E_RUNTIME",
        "run with unoptimized python3 -I -B -S",
    )


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
    require(type(value) is dict, "E_JSON", f"{label} must be an object")
    return value


def typed_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            typed_equal(actual[key], expected[key]) for key in expected
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            typed_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict, "E_SCHEMA", f"{label} must be an object")
    require(set(value) == expected, "E_SCHEMA", f"{label} keys differ")
    return value


def validate_relative_path(relative: str) -> tuple[str, ...]:
    require(type(relative) is str, "E_PATH", "path must be a string")
    path = PurePosixPath(relative)
    parts = path.parts
    require(
        bool(parts)
        and not path.is_absolute()
        and "\\" not in relative
        and "\x00" not in relative
        and relative == "/".join(parts)
        and all(part not in {"", ".", ".."} for part in parts),
        "E_PATH",
        "unsafe repository-relative path",
    )
    return parts


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


def directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def file_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


class Snapshot:
    def __init__(
        self,
        path: str,
        fd: int,
        raw: bytes,
        state: tuple[int, ...],
    ) -> None:
        self.path = path
        self.fd = fd
        self.raw = raw
        self.state = state


class SafeReader:
    """Hold no-follow file descriptors through two byte/identity barriers."""

    def __init__(self, root: Path) -> None:
        try:
            self.root_fd = os.open(root, directory_flags())
        except OSError as error:
            raise CheckError("E_FILESYSTEM", "cannot open repository root") from error
        self.root = root
        info = os.fstat(self.root_fd)
        require(stat.S_ISDIR(info.st_mode), "E_FILESYSTEM", "root type")
        require(info.st_uid == os.getuid(), "E_FILESYSTEM", "root owner")
        require(
            stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_FILESYSTEM",
            "root writable by non-owner",
        )
        self.root_state = descriptor_state(info)
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
                    "ancestor writable by non-owner",
                )
                os.close(current)
                current = child
            return current, parts[-1]
        except FileNotFoundError as error:
            os.close(current)
            raise CheckError("E_MISSING", f"missing {relative}") from error
        except OSError as error:
            os.close(current)
            raise CheckError("E_FILESYSTEM", f"unsafe ancestor {relative}") from error
        except Exception:
            os.close(current)
            raise

    def read(
        self,
        relative: str,
        maximum_bytes: int = MAXIMUM_FILE_BYTES,
    ) -> bytes:
        parent, name = self._open_parent(relative)
        try:
            try:
                fd = os.open(name, file_flags(), dir_fd=parent)
            except FileNotFoundError as error:
                raise CheckError("E_MISSING", f"missing {relative}") from error
            except OSError as error:
                raise CheckError("E_FILESYSTEM", f"cannot open {relative}") from error
        finally:
            os.close(parent)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode), "E_FILESYSTEM", f"{relative} type")
            require(before.st_uid == os.getuid(), "E_FILESYSTEM", f"{relative} owner")
            require(before.st_nlink == 1, "E_FILESYSTEM", f"{relative} link count")
            require(
                stat.S_IMODE(before.st_mode) & 0o022 == 0,
                "E_FILESYSTEM",
                f"{relative} writable by non-owner",
            )
            require(
                0 < before.st_size <= maximum_bytes,
                "E_FILESYSTEM",
                f"{relative} size",
            )
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
                len(raw) == before.st_size
                and len(raw) <= maximum_bytes
                and descriptor_state(before) == descriptor_state(after),
                "E_TOCTOU",
                f"{relative} changed during first pass",
            )
            self.snapshots.append(
                Snapshot(relative, fd, raw, descriptor_state(after))
            )
            return raw
        except Exception:
            os.close(fd)
            raise

    def snapshot(self, relative: str) -> Snapshot:
        matches = [item for item in self.snapshots if item.path == relative]
        require(len(matches) == 1, "E_INTERNAL", f"snapshot {relative}")
        return matches[0]

    def path_kind(self, relative: str) -> str:
        try:
            parent, name = self._open_parent(relative)
        except CheckError as error:
            if error.code == "E_MISSING":
                return "absent"
            raise
        try:
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return "absent"
        finally:
            os.close(parent)
        if stat.S_ISREG(info.st_mode):
            return "file"
        if stat.S_ISDIR(info.st_mode):
            return "directory"
        return "other"

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
                    "directory writable by non-owner",
                )
                os.close(current)
                current = child
            return sorted(os.listdir(current))
        except FileNotFoundError:
            return []
        except OSError as error:
            raise CheckError(
                "E_FILESYSTEM",
                f"cannot list directory {relative}",
            ) from error
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
            remaining = len(snapshot.raw) + 1
            while remaining > 0:
                chunk = os.read(snapshot.fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
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
                stat.S_ISREG(named.st_mode)
                and named.st_uid == os.getuid()
                and named.st_nlink == 1
                and (named.st_dev, named.st_ino) == (info.st_dev, info.st_ino),
                "E_TOCTOU",
                f"{snapshot.path} final name identity",
            )
        current = os.fstat(self.root_fd)
        named = os.stat(self.root, follow_symlinks=False)
        require(
            descriptor_state(current) == self.root_state
            and stat.S_ISDIR(named.st_mode)
            and (current.st_dev, current.st_ino) == (named.st_dev, named.st_ino),
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
    label: str,
    expected_digest: str | None = None,
) -> str:
    binding = exact_keys(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    digest = binding.get("sha256")
    require(
        typed_equal(
            binding,
            {
                "algorithm": "sha256",
                "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
                "scope": expected_scope,
                "sha256": digest,
            },
        )
        and type(digest) is str
        and HEX_SHA256.fullmatch(digest) is not None,
        "E_BINDING",
        f"{label} content binding contract",
    )
    unsigned = dict(document)
    unsigned.pop("contentBinding")
    observed = sha256_bytes(canonical_json_bytes(unsigned))
    require(
        observed == digest and (expected_digest is None or digest == expected_digest),
        "E_BINDING",
        f"{label} content binding mismatch",
    )
    return digest


def validate_source(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    require(
        source.get("documentType")
        == (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-identity-"
            "and-acquisition-decision"
        )
        and source.get("schemaVersion") == "1.0"
        and source.get("decisionId") == EXPECTED_SOURCE_ID,
        "E_SOURCE",
        "source decision identity",
    )
    validate_content_binding(
        source,
        "decision_without_contentBinding",
        "source decision",
        EXPECTED_SOURCE_CONTENT_SHA256,
    )
    wave = exact_keys(
        source.get("wave"),
        {
            "waveId",
            "order",
            "selectedTupleCount",
            "maximumRequestCount",
            "expectedSuccessRequestCount",
            "sequentialOrderRequired",
            "automaticRetryAllowed",
            "tuples",
        },
        "source wave",
    )
    require(
        wave.get("waveId") == "g2-pion-ice-v4.3.0-dependency-source-wave1-v1"
        and wave.get("order") == 1
        and wave.get("selectedTupleCount") == 19
        and wave.get("maximumRequestCount") == 19
        and wave.get("expectedSuccessRequestCount") == 19
        and wave.get("sequentialOrderRequired") is True
        and wave.get("automaticRetryAllowed") is False,
        "E_SOURCE",
        "source wave contract",
    )
    values = wave.get("tuples")
    require(type(values) is list and len(values) == 19, "E_SOURCE", "exact tuples")
    tuple_keys = {
        "order",
        "tupleId",
        "tupleSha256",
        "module",
        "version",
        "rootRequirementClass",
        "selected",
        "selectionReason",
        "moduleZipH1",
        "goModH1",
        "sourceIdentityTrustRole",
        "url",
        "scheme",
        "host",
        "path",
        "outputPath",
    }
    result: list[dict[str, Any]] = []
    for order, value in enumerate(values, 1):
        item = exact_keys(value, tuple_keys, f"tuple {order}")
        module = item.get("module")
        version = item.get("version")
        require(
            type(module) is str
            and module
            and module == module.lower()
            and type(version) is str
            and version
            and version == version.lower(),
            "E_SOURCE",
            f"tuple {order} module/version",
        )
        tuple_digest = sha256_bytes(f"{module}\n{version}\n".encode("utf-8"))
        expected_url = f"https://proxy.golang.org/{module}/@v/{version}.zip"
        require(
            item.get("order") == order
            and item.get("tupleSha256") == tuple_digest
            and item.get("tupleId") == f"wave1-{order:03d}-{tuple_digest[:12]}"
            and item.get("selected") is True
            and item.get("rootRequirementClass") in {"direct", "indirect"}
            and item.get("url") == expected_url
            and item.get("scheme") == "https"
            and item.get("host") == "proxy.golang.org"
            and item.get("path") == f"/{module}/@v/{version}.zip"
            and item.get("outputPath")
            == (
                f"{DEPENDENCY_PARENT}/wave-1/accepted/"
                f"{order:03d}-{tuple_digest[:20]}.zip"
            )
            and type(item.get("moduleZipH1")) is str
            and H1.fullmatch(item["moduleZipH1"]) is not None
            and type(item.get("goModH1")) is str
            and H1.fullmatch(item["goModH1"]) is not None,
            "E_SOURCE",
            f"tuple {order} binding",
        )
        result.append(dict(item))
    require(
        len({item["tupleSha256"] for item in result}) == 19
        and len({item["url"] for item in result}) == 19,
        "E_SOURCE",
        "tuple uniqueness",
    )
    return result


def output_file_name(item: Mapping[str, Any], kind: str) -> str:
    require(kind in {"mod", "zip"}, "E_INTERNAL", "resource kind")
    return f"{item['order']:03d}-{item['tupleSha256'][:20]}.{kind}"


def expected_ordered_requests(
    tuples: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in tuples:
        for kind in ("mod", "zip"):
            is_mod = kind == "mod"
            rows.append(
                {
                    "requestOrdinal": 2 * item["order"] - (1 if is_mod else 0),
                    "tupleOrder": item["order"],
                    "tupleId": item["tupleId"],
                    "resourceKind": kind,
                    "method": "GET",
                    "url": item["url"][:-4] + ".mod" if is_mod else item["url"],
                    "outputFileName": output_file_name(item, kind),
                    "expectedH1": item["goModH1"] if is_mod else item["moduleZipH1"],
                    "expectedH1Kind": "go_mod_h1" if is_mod else "module_zip_h1",
                    "allowedContentTypes": (
                        ["text/plain", "application/octet-stream"]
                        if is_mod
                        else ["application/zip", "application/octet-stream"]
                    ),
                }
            )
    require(
        len(rows) == 38
        and [row["requestOrdinal"] for row in rows] == list(range(1, 39)),
        "E_INTERNAL",
        "request-plan construction",
    )
    return rows


def expected_reserved_paths(
    tuples: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    resources = [
        f"{V3_FINAL_DIRECTORY}/{output_file_name(item, kind)}"
        for item in tuples
        for kind in ("mod", "zip")
    ]
    acquisition = [
        V3_CLAIM_PATH,
        *resources,
        V3_SUCCESS_PATH,
        V3_MANIFEST_PATH,
    ]
    post_readback = [
        *acquisition,
        READBACK_RECEIPT_PATH,
        READBACK_MANIFEST_PATH,
    ]
    require(
        len(acquisition) == len(set(acquisition)) == 41
        and len(post_readback) == len(set(post_readback)) == 43,
        "E_INTERNAL",
        "reserved-path construction",
    )
    return acquisition, post_readback


def expected_tool_bindings(raw: Mapping[str, bytes]) -> list[dict[str, str]]:
    return [
        {"role": role, "path": path, "rawSha256": sha256_bytes(raw[path])}
        for role, path in TOOL_ROWS
    ]


def terminal_binding(
    path: str,
    *,
    byte_size: int,
    status_value: str | None = None,
    failure_code: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path,
        "rawSha256": EXPECTED_FIXED_RAW_SHA256[path],
        "byteSize": byte_size,
        "mode": "0600",
        "linkCount": 1,
        "retained": True,
        "automaticRetryAllowed": False,
    }
    if status_value is not None:
        result.update(
            {
                "status": status_value,
                "result": "no_dependency_source_set_accepted",
                "failureCode": failure_code,
                "acceptedArtifactCount": 0,
                "finalSetPublished": False,
            }
        )
    return result


def build_expected_permit(
    source: Mapping[str, Any],
    recovery: Mapping[str, Any],
    raw: Mapping[str, bytes],
) -> dict[str, Any]:
    """Build the exact permit document expected from already-held repository bytes."""

    tuples = validate_source(source)
    requests = expected_ordered_requests(tuples)
    acquisition_paths, post_readback_paths = expected_reserved_paths(tuples)
    unsigned: dict[str, Any] = {
        "documentType": (
            "aetherlink.g2-pion-rung3-dependency-wave1-execution-permit"
        ),
        "schemaVersion": "3.0",
        "permitId": EXPECTED_PERMIT_ID,
        "recordedDate": EXPECTED_DATE,
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "scope": EXPECTED_SCOPE,
        "personalProjectBoundary": {
            "projectOwnership": "personal_single_owner",
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "signatureRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationChanged": False,
        },
        "sourceDecisionBinding": {
            "path": SOURCE_DECISION_PATH,
            "rawSha256": EXPECTED_FIXED_RAW_SHA256[SOURCE_DECISION_PATH],
            "contentSha256": EXPECTED_SOURCE_CONTENT_SHA256,
            "decisionId": EXPECTED_SOURCE_ID,
            "requiredTupleCount": 19,
            "freshFullSetRequired": True,
        },
        "recoveryBinding": {
            "path": RECOVERY_PATH,
            "rawSha256": EXPECTED_FIXED_RAW_SHA256[RECOVERY_PATH],
            "contentSha256": EXPECTED_RECOVERY_CONTENT_SHA256,
            "decisionId": EXPECTED_RECOVERY_ID,
            "requiredStatus": (
                "wave1_v2_failure_read_back_recovery_v3_design_selected_"
                "execution_not_authorized"
            ),
            "v1AndV2TerminalPreservationRequired": True,
        },
        "terminalEvidenceBindings": {
            "v1Claim": terminal_binding(V1_CLAIM_PATH, byte_size=445),
            "v1FailureReceipt": terminal_binding(
                V1_FAILURE_PATH,
                byte_size=858,
                status_value="wave1_acquisition_failed_permit_consumed",
                failure_code="E_ZIP_RATIO",
            ),
            "v2Claim": terminal_binding(V2_CLAIM_PATH, byte_size=482),
            "v2FailureReceipt": terminal_binding(
                V2_FAILURE_PATH,
                byte_size=1174,
                status_value="wave1_v2_acquisition_failed_permit_consumed",
                failure_code="E_GO_MOD_MISSING",
            ),
        },
        "runnerBinding": {
            "path": RUNNER_PATH,
            "rawSha256": sha256_bytes(raw[RUNNER_PATH]),
        },
        "toolBindings": expected_tool_bindings(raw),
        "interpreterIsolationContract": {
            "permitCheckerPreflightCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                CHECKER_PATH,
                "--preflight",
            ],
            "runnerPreflightCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RUNNER_PATH,
                "--preflight",
            ],
            "runnerExecuteCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RUNNER_PATH,
                "--execute",
            ],
            "isolatedInterpreterRequired": True,
            "sitePackagesAllowed": False,
            "bytecodeWritesAllowed": False,
            "pythonPathAllowed": False,
            "environmentOverridesAllowed": False,
            "processUmask": "077",
            "cliOverridesAllowed": False,
        },
        "oneUseConsumption": {
            "initialState": "authorized_not_consumed",
            "claimPath": V3_CLAIM_PATH,
            "stagingParentPath": DEPENDENCY_PARENT,
            "stagingNamePrefix": V3_STAGING_PREFIX,
            "finalDirectoryPath": V3_FINAL_DIRECTORY,
            "claimPersistsAfterAnyNetworkAttempt": True,
            "claimUncertaintyConsumesPermit": True,
            "automaticRetryAllowed": False,
            "secondExecutionAllowed": False,
            "preclaimFailureConsumesPermit": False,
            "v1OrV2ArtifactReuseAllowed": False,
            "resumeFromV1OrV2StagingAllowed": False,
        },
        "requestContract": {
            "tupleCount": 19,
            "resourcesPerTuple": 2,
            "requestCount": 38,
            "method": "GET",
            "scheme": "https",
            "host": "proxy.golang.org",
            "port": 443,
            "tupleOrder": "exact_source_decision_order_1_through_19_sequential",
            "resourceOrderPerTuple": ["mod", "zip"],
            "requestOrdinalRule": {
                "mod": "two_times_tuple_order_minus_one",
                "zip": "two_times_tuple_order",
            },
            "orderedRequests": requests,
            "redirectsAllowed": False,
            "automaticRetriesAllowed": False,
            "rangeOrResumeAllowed": False,
            "alternateMirrorAllowed": False,
            "authenticationHeadersAllowed": False,
            "authenticationChallengeAllowed": False,
            "cookiesAllowed": False,
            "clientCertificatesAllowed": False,
            "ambientProxyAllowed": False,
            "urlQueryAllowed": False,
            "urlFragmentAllowed": False,
            "contentEncoding": "identity",
            "successStatusCode": 200,
        },
        "networkAuthority": {
            "boundedSourceIntakeDnsAuthorized": True,
            "boundedSourceIntakeTcpAuthorized": True,
            "boundedSourceIntakeTlsAuthorized": True,
            "boundedSourceIntakeHttpsAuthorized": True,
            "authorizedHost": "proxy.golang.org",
            "authorizedRequestCount": 38,
            "runtimeSocketAuthorized": False,
            "runtimeNetworkAuthorized": False,
            "productNetworkAuthorized": False,
            "relayOrP2PNetworkAuthorized": False,
        },
        "resourceValidationContract": {
            "mod": {
                "sourceBytes": "exact_mod_response_body",
                "maximumBytesPerResponse": 1_048_576,
                "maximumAggregateBytes": 8_388_608,
                "utf8Required": True,
                "nulByteForbidden": True,
                "exactModuleDirectiveRequired": True,
                "goModH1Required": True,
                "goModH1Algorithm": (
                    "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod"
                ),
            },
            "zip": {
                "filesystemExtractionAllowed": False,
                "centralAndLocalHeaderConsistencyRequired": True,
                "crcRequired": True,
                "exactEofRequired": True,
                "zip64Allowed": False,
                "encryptionAllowed": False,
                "explicitDirectoryEntriesAllowed": False,
                "symlinkOrSpecialFileAllowed": False,
                "duplicateOrCasefoldCollisionAllowed": False,
                "validUtf8AndNfcPathsRequired": True,
                "allowedCompressionMethods": ["stored", "deflated"],
                "exactModulePrefixRequired": True,
                "moduleZipH1Required": True,
                "embeddedRootGoModRequired": False,
                "embeddedRootGoModMustMatchExternalModWhenPresent": True,
                "compressionRatioRejectionAllowed": False,
                "compressionRatioTelemetryRequired": True,
            },
            "streamedToOwnerOnlyTemporaryFiles": True,
            "openedDescriptorValidation": True,
            "allResourcesReopenedReparsedAndRehashedBeforePublication": True,
            "orderedSourceSetDigestRequired": True,
        },
        "filesystemWriteAuthority": {
            "newDirectoryMode": "0700",
            "newFileMode": "0600",
            "claimWriteAuthorized": True,
            "stagingWriteAuthorized": True,
            "acceptedModWriteAuthorized": True,
            "acceptedZipWriteAuthorized": True,
            "successReceiptWriteAuthorized": True,
            "failureReceiptWriteAuthorized": True,
            "manifestWriteAuthorized": True,
            "failedStagingCleanupAuthorized": True,
            "atomicNoReplaceFinalDirectoryPublicationRequired": True,
            "v1OrV2ArtifactModificationAuthorized": False,
            "sourceModificationAuthorized": False,
            "sourceExtractionAuthorized": False,
            "otherRepositoryWritesAuthorized": False,
        },
        "absoluteResourceLimits": ABSOLUTE_RESOURCE_LIMITS,
        "counterContract": {
            "counterNames": list(COUNTER_NAMES),
            "successValues": SUCCESS_COUNTERS,
            "legacyCompletedRequestCountForbidden": True,
            "failureTupleAndResourceKindRequired": True,
        },
        "receiptFailureManifestContract": {
            "successReceiptPath": V3_SUCCESS_PATH,
            "failureReceiptPath": V3_FAILURE_PATH,
            "manifestPath": V3_MANIFEST_PATH,
            "successState": "acquired_pending_independent_readback",
            "failureState": "wave1_v3_acquisition_failed_permit_consumed",
            "postPublishUncertainState": "consumed_terminal_state_uncertain",
            "successAndFailureMutuallyExclusive": True,
            "acceptedArtifactCountOnSuccess": 38,
            "acceptedTupleCountOnSuccess": 19,
            "acceptedArtifactCountOnFailure": 0,
            "boundedFailureReasonCodesOnly": True,
            "rawErrorsBodiesHeadersCertificatesPathsOrEntryNamesRecorded": False,
            "manifestWrittenLast": True,
            "runnerMayClaimIndependentReadback": False,
            "independentReadbackRequired": True,
        },
        "reservedRegularFilePaths": {
            "regularFileCountMeaning": (
                "exact_reserved_regular_file_path_set_not_recursive_directory_count"
            ),
            "acquisitionPublication": {
                "count": 41,
                "paths": acquisition_paths,
            },
            "postReadbackPublication": {
                "count": 43,
                "paths": post_readback_paths,
            },
            "failureReceiptPath": V3_FAILURE_PATH,
            "successAndFailureMutuallyExclusive": True,
        },
        "independentReadbackContract": {
            "requiredAfterAcquisitionSuccess": True,
            "runnerSelfCheckQualifiesAsIndependentReadback": False,
            "checkerPath": READBACK_CHECKER_PATH,
            "checkerTestsPath": READBACK_TEST_PATH,
            "receiptPath": READBACK_RECEIPT_PATH,
            "manifestPath": READBACK_MANIFEST_PATH,
            "exactRetainedResourceCount": 38,
            "recomputeRawSha256": True,
            "recomputeModuleZipH1": True,
            "recomputeGoModH1": True,
            "recheckEmbeddedModParityWhenPresent": True,
            "recheckExactInventoryModeLinkCountAndStableIdentity": True,
            "regularFileCountMeaning": (
                "exact_reserved_regular_file_path_set_not_recursive_directory_count"
            ),
            "acquisitionSuccessRegularFileCount": 41,
            "postReadbackRegularFileCount": 43,
            "networkAllowed": False,
            "sourceExtractionAllowed": False,
            "sourceLoadOrExecutionAllowed": False,
            "receiptAndManifestWritesOnly": True,
            "manifestWrittenLast": True,
        },
        "authority": {
            "permitRecorded": True,
            "exactWave1V3AcquisitionAuthorized": True,
            "networkAuthorized": True,
            "dependencySourceAcquisitionAuthorized": True,
            "maximumRequestCount": 38,
            "automaticRetryAllowed": False,
            "credentialsAllowed": False,
            "authenticationRequired": False,
            "boundedExecutionArtifactWritesAuthorized": True,
            "packageManagerAuthorized": False,
            "goCommandAuthorized": False,
            "gitCommandAuthorized": False,
            "shellOrSubprocessAuthorized": False,
            "compilerAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "runtimeOrProductNetworkAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "execution": {
            "permitRecorded": True,
            "permitConsumed": False,
            "claimCreated": False,
            **{name: 0 for name in COUNTER_NAMES},
            "acceptedArtifactCount": 0,
            "acceptedTupleCount": 0,
            "networkUsed": False,
            "successReceiptCreated": False,
            "failureReceiptCreated": False,
            "manifestCreated": False,
            "independentReadbackPassed": False,
        },
        "closure": {
            "openFindingCount": 19,
            "findingsClosedByPermit": 0,
            "waveAcquired": False,
            "graphFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "nonClaims": EXPECTED_NONCLAIMS,
    }
    document = dict(unsigned)
    document["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(unsigned)),
    }
    return document


def literal_assignment(tree: ast.Module, name: str) -> Any:
    matches: list[Any] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            try:
                matches.append(ast.literal_eval(node.value))
            except (ValueError, TypeError):
                matches.append(None)
    require(len(matches) == 1, "E_TOOL", f"runner constant {name}")
    return matches[0]


def test_count(raw: bytes, label: str) -> int:
    try:
        text = raw.decode("utf-8")
        ast.parse(text, filename=label)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise CheckError("E_TOOL", f"{label} syntax or encoding") from error
    return len(re.findall(r"(?m)^    def test_[A-Za-z0-9_]+\(", text))


def validate_tool_sources(raw: Mapping[str, bytes]) -> dict[str, int]:
    for path, expected in EXPECTED_FIXED_RAW_SHA256.items():
        require(
            sha256_bytes(raw[path]) == expected,
            "E_RAW_BINDING",
            f"fixed raw binding {path}",
        )
    counts = {
        path: test_count(raw[path], path) for path in EXPECTED_TEST_COUNTS
    }
    for path, expected in EXPECTED_TEST_COUNTS.items():
        require(counts[path] == expected, "E_TOOL", f"test count {path}")

    try:
        runner_tree = ast.parse(raw[RUNNER_PATH], filename=RUNNER_PATH)
        ast.parse(raw[CHECKER_PATH], filename=CHECKER_PATH)
        ast.parse(raw[READBACK_CHECKER_PATH], filename=READBACK_CHECKER_PATH)
        ast.parse(raw[RECOVERY_CHECKER_PATH], filename=RECOVERY_CHECKER_PATH)
    except SyntaxError as error:
        raise CheckError("E_TOOL", "bound tool syntax") from error

    checker_digest = sha256_bytes(raw[CHECKER_PATH])
    require(
        literal_assignment(runner_tree, "PERMIT_CHECKER_PATH") == CHECKER_PATH,
        "E_TOOL",
        "runner checker path pin",
    )
    require(
        literal_assignment(
            runner_tree,
            "EXPECTED_PERMIT_CHECKER_RAW_SHA256",
        )
        == checker_digest,
        "E_TOOL",
        "runner checker raw SHA pin",
    )
    runner_source = raw[RUNNER_PATH].decode("utf-8")
    for token in (
        "def validate_mod_bytes(",
        "def inspect_module_zip_v3(",
        "def validate_held_output_inventory_v3(",
        "def validate_terminal_state(",
        "def preflight(",
        "def execute_once(",
        '"consumed_terminal_state_uncertain"',
        'mode.add_argument("--execute", action="store_true")',
        '"externalAuthenticationRequired": False',
    ):
        require(token in runner_source, "E_TOOL", f"runner missing {token}")
    forbidden_imports = {"subprocess", "socket", "requests", "httpx", "aiohttp"}
    for node in ast.walk(runner_tree):
        if isinstance(node, ast.Import):
            names = {alias.name.split(".", 1)[0] for alias in node.names}
            require(
                not names.intersection(forbidden_imports),
                "E_TOOL",
                "runner forbidden import",
            )
        elif isinstance(node, ast.ImportFrom):
            require(
                (node.module or "").split(".", 1)[0] not in forbidden_imports,
                "E_TOOL",
                "runner forbidden import",
            )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(
                node.func.attr
                not in {"system", "popen", "spawn", "execv", "execve", "fork"},
                "E_TOOL",
                "runner process call",
            )
    return counts


def load_recovery_module(raw: bytes, root: Path) -> types.ModuleType:
    module = types.ModuleType("g2_wave1_v3_pinned_recovery_checker")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(root / RECOVERY_CHECKER_PATH),
            "__loader__": None,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(
                raw,
                RECOVERY_CHECKER_PATH,
                "exec",
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise CheckError("E_RECOVERY", "cannot load recovery checker") from error
    return module


def validate_terminal_files(
    reader: SafeReader,
    raw: Mapping[str, bytes],
) -> None:
    for path, size in (
        (V1_CLAIM_PATH, 445),
        (V1_FAILURE_PATH, 858),
        (V2_CLAIM_PATH, 482),
        (V2_FAILURE_PATH, 1174),
    ):
        snapshot = reader.snapshot(path)
        require(
            len(raw[path]) == size
            and stat.S_IMODE(snapshot.state[2]) == 0o600
            and snapshot.state[3] == os.getuid()
            and snapshot.state[4] == 1,
            "E_TERMINAL",
            f"terminal metadata {path}",
        )
    failure_v1 = strict_json(raw[V1_FAILURE_PATH], "v1 failure")
    failure_v2 = strict_json(raw[V2_FAILURE_PATH], "v2 failure")
    require(
        failure_v1.get("status") == "wave1_acquisition_failed_permit_consumed"
        and failure_v1.get("result") == "no_dependency_source_set_accepted"
        and failure_v1.get("failureCode") == "E_ZIP_RATIO"
        and failure_v1.get("automaticRetryAllowed") is False
        and failure_v1.get("finalSetPublished") is False
        and failure_v1.get("acceptedArtifactCount") == 0,
        "E_TERMINAL",
        "v1 terminal failure",
    )
    require(
        failure_v2.get("status")
        == "wave1_v2_acquisition_failed_permit_consumed"
        and failure_v2.get("result") == "no_dependency_source_set_accepted"
        and failure_v2.get("failureCode") == "E_GO_MOD_MISSING"
        and failure_v2.get("networkRequestAttemptCount") == 11
        and failure_v2.get("responseBodyCompletedCount") == 11
        and failure_v2.get("validatedAndStagedTupleCount") == 10
        and failure_v2.get("automaticRetryAllowed") is False
        and failure_v2.get("finalSetPublished") is False
        and failure_v2.get("acceptedArtifactCount") == 0,
        "E_TERMINAL",
        "v2 terminal failure",
    )


def validate_recovery_and_source(
    module: types.ModuleType,
    raw: Mapping[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = strict_json(raw[SOURCE_DECISION_PATH], "source decision")
    recovery = strict_json(raw[RECOVERY_PATH], "recovery decision v2")
    tuples = validate_source(source)
    require(len(tuples) == 19, "E_SOURCE", "source tuple count")
    validate_content_binding(
        recovery,
        "decision_without_contentBinding",
        "recovery decision v2",
        EXPECTED_RECOVERY_CONTENT_SHA256,
    )
    try:
        module.validate_claim_v2(
            module.strict_json(raw[V2_CLAIM_PATH], "v2 claim")
        )
        module.validate_failure_v2(
            module.strict_json(raw[V2_FAILURE_PATH], "v2 failure")
        )
        module.validate_recovery(recovery, source)
    except Exception as error:
        raise CheckError("E_RECOVERY", "recovery decision validation") from error
    require(
        recovery.get("decisionId") == EXPECTED_RECOVERY_ID
        and recovery.get("status")
        == (
            "wave1_v2_failure_read_back_recovery_v3_design_selected_"
            "execution_not_authorized"
        )
        and recovery.get("authority", {}).get("networkAuthorized") is False
        and recovery.get("authority", {}).get(
            "dependencySourceAcquisitionAuthorized"
        )
        is False,
        "E_RECOVERY",
        "recovery disposition",
    )
    return source, recovery


def validate_permit(
    permit: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    exact_keys(permit, PERMIT_TOP_LEVEL_KEYS, "permit")
    validate_content_binding(permit, "permit_without_contentBinding", "permit")
    section_codes = {
        "personalProjectBoundary": "E_AUTHORITY",
        "sourceDecisionBinding": "E_SOURCE",
        "recoveryBinding": "E_RECOVERY",
        "terminalEvidenceBindings": "E_TERMINAL",
        "runnerBinding": "E_TOOL",
        "toolBindings": "E_TOOL",
        "interpreterIsolationContract": "E_RUNTIME",
        "oneUseConsumption": "E_ONE_USE",
        "requestContract": "E_REQUEST",
        "networkAuthority": "E_AUTHORITY",
        "resourceValidationContract": "E_RESOURCE",
        "filesystemWriteAuthority": "E_FILESYSTEM",
        "absoluteResourceLimits": "E_LIMIT",
        "counterContract": "E_COUNTER",
        "receiptFailureManifestContract": "E_RECEIPT",
        "reservedRegularFilePaths": "E_RESERVED_PATH",
        "independentReadbackContract": "E_READBACK",
        "authority": "E_AUTHORITY",
        "execution": "E_EXECUTION",
        "closure": "E_CLOSURE",
        "nonClaims": "E_NONCLAIM",
    }
    for key in (
        "documentType",
        "schemaVersion",
        "permitId",
        "recordedDate",
        "status",
        "result",
        "nextAction",
        "scope",
    ):
        require(
            typed_equal(permit.get(key), expected[key]),
            "E_STATE",
            f"permit.{key}",
        )
    for key, code in section_codes.items():
        require(
            typed_equal(permit.get(key), expected[key]),
            code,
            f"permit.{key}",
        )
    require(
        typed_equal(permit.get("contentBinding"), expected["contentBinding"]),
        "E_BINDING",
        "permit expected content binding",
    )


def inspect_v3_namespace(reader: SafeReader) -> dict[str, Any]:
    kinds = {
        path: reader.path_kind(path)
        for path in (
            V3_CLAIM_PATH,
            V3_FINAL_DIRECTORY,
            V3_SUCCESS_PATH,
            V3_FAILURE_PATH,
            V3_MANIFEST_PATH,
            READBACK_RECEIPT_PATH,
            READBACK_MANIFEST_PATH,
        )
    }
    siblings = reader.list_directory(DEPENDENCY_PARENT)
    staging_count = sum(name.startswith(V3_STAGING_PREFIX) for name in siblings)
    clean = all(kind == "absent" for kind in kinds.values()) and staging_count == 0
    return {
        "namespaceInitiallyClean": clean,
        "v3ArtifactKinds": kinds,
        "v3StagingEntryCount": staging_count,
    }


def validate_repository(
    root: Path = ROOT,
    *,
    before_final_barrier: Callable[[], None] | None = None,
) -> dict[str, Any]:
    require_isolated_interpreter()
    reader = SafeReader(root)
    try:
        paths = tuple(dict.fromkeys(
            (
                PERMIT_PATH,
                *EXPECTED_FIXED_RAW_SHA256,
                *(path for _, path in TOOL_ROWS),
            )
        ))
        raw = {path: reader.read(path) for path in paths}
        counts = validate_tool_sources(raw)
        validate_terminal_files(reader, raw)
        recovery_module = load_recovery_module(raw[RECOVERY_CHECKER_PATH], root)
        source, recovery = validate_recovery_and_source(recovery_module, raw)
        permit = strict_json(raw[PERMIT_PATH], "v3 permit")
        expected = build_expected_permit(source, recovery, raw)
        validate_permit(permit, expected)
        namespace = inspect_v3_namespace(reader)

        reader.verify()
        if before_final_barrier is not None:
            before_final_barrier()
        reader.verify()
        root_info = os.fstat(reader.root_fd)
        return {
            "permit": permit,
            "sourceDecision": source,
            "recoveryDecision": recovery,
            "repositoryRootIdentity": {
                "device": root_info.st_dev,
                "inode": root_info.st_ino,
                "ownerUid": root_info.st_uid,
                "mode": stat.S_IMODE(root_info.st_mode),
            },
            "permitRawSha256": sha256_bytes(raw[PERMIT_PATH]),
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "runnerRawSha256": sha256_bytes(raw[RUNNER_PATH]),
            "checkerRawSha256": sha256_bytes(raw[CHECKER_PATH]),
            "testCounts": counts,
            "v1PermitConsumed": True,
            "v2PermitConsumed": True,
            "v3PermitRecorded": True,
            "v3ExecutionAuthorized": True,
            **namespace,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "fileWriteCount": 0,
            "networkOperationCount": 0,
        }
    finally:
        reader.close()


def preflight_status(root: Path = ROOT) -> tuple[dict[str, Any], int]:
    probe = SafeReader(root)
    try:
        permit_kind = probe.path_kind(PERMIT_PATH)
        probe.verify()
    finally:
        probe.close()
    if permit_kind == "absent":
        return (
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-wave1-v3-permit-preflight"
                ),
                "schemaVersion": "3.0",
                "status": "permit_absent_not_authorized",
                "validationPassed": False,
                "v3ExecutionAuthorized": False,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "nextAction": "record_separate_content_bound_v3_execution_permit",
            },
            1,
        )
    if permit_kind != "file":
        return (
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-wave1-v3-permit-preflight"
                ),
                "schemaVersion": "3.0",
                "status": "permit_invalid_not_authorized",
                "validationPassed": False,
                "v3ExecutionAuthorized": False,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "nextAction": "replace_no_files_and_review_invalid_permit_path",
            },
            1,
        )
    try:
        result = validate_repository(root)
    except CheckError as error:
        return (
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-wave1-v3-permit-preflight"
                ),
                "schemaVersion": "3.0",
                "status": "permit_invalid_not_authorized",
                "validationPassed": False,
                "v3ExecutionAuthorized": False,
                "failureCode": error.code,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "nextAction": "review_v3_permit_without_execution",
            },
            1,
        )
    return (
        {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v3-permit-preflight"
            ),
            "schemaVersion": "3.0",
            "status": EXPECTED_STATUS,
            "validationPassed": True,
            "v3ExecutionAuthorized": True,
            "namespaceInitiallyClean": result["namespaceInitiallyClean"],
            "permitId": EXPECTED_PERMIT_ID,
            "permitRawSha256": result["permitRawSha256"],
            "permitContentSha256": result["permitContentSha256"],
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": EXPECTED_NEXT_ACTION,
        },
        0,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    require_isolated_interpreter()
    try:
        status, exit_code = preflight_status(args.root)
    except CheckError as error:
        status = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v3-permit-preflight"
            ),
            "schemaVersion": "3.0",
            "status": "permit_invalid_not_authorized",
            "validationPassed": False,
            "v3ExecutionAuthorized": False,
            "failureCode": error.code,
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        exit_code = 1
    except Exception:
        status = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v3-permit-preflight"
            ),
            "schemaVersion": "3.0",
            "status": "permit_invalid_not_authorized",
            "validationPassed": False,
            "v3ExecutionAuthorized": False,
            "failureCode": "E_INTERNAL",
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        exit_code = 1
    print(json.dumps(status, ensure_ascii=True, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
