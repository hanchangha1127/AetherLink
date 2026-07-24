#!/usr/bin/env python3
"""Review the bound G2 dependency source wave one exactly once.

The runner has two explicit modes. ``--preflight`` verifies the fixed permit,
its complete held input set, and the one-use publication namespace without
opening archive members or writing files. ``--execute`` performs one bounded
in-memory ZIP/MOD review and publishes a result followed by a manifest. It
never extracts source, invokes source, creates a socket, uses the network,
starts a subprocess, or modifies an acquired input.
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
            "dependency source-review runner requires unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
from collections import defaultdict, deque
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import types
from typing import Any, Iterable, Mapping, Sequence
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = f"{BASE}/bounded-dependency-source-review-wave1-decision-v1.json"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v3.json"
)
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_source_review_wave1_"
    "execution_permit_v1.py"
)
RUNNER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
RUNNER_TESTS_PATH = (
    "script/test_run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v3.claim"
)
RESULT_PATH = f"{BASE}/bounded-dependency-source-review-wave1-result-v3.json"
FAILURE_PATH = f"{BASE}/bounded-dependency-source-review-wave1-failure-v3.json"
MANIFEST_PATH = f"{BASE}/bounded-dependency-source-review-wave1-manifest-v3.json"
STAGING_DIRECTORY_PREFIX = ".wave-1-review-v3-staging-"

PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
    "execution-permit-v3"
)
EXPECTED_PERMIT_STATUS = (
    "dependency_source_review_wave1_execution_authorized_not_consumed"
)
EXPECTED_PERMIT_NEXT_ACTION = (
    "execute_bound_dependency_source_review_wave1_once"
)
REVIEW_ID = "g2-pion-ice-v4.3.0-dependency-source-review-wave1-v3"
GRAPH_ALGORITHM = "go1.24_mvs_profile_union_fixed_point_v1"
INDEPENDENT_READBACK_NEXT_ACTION = (
    "run_separate_dependency_source_review_wave1_independent_readback"
)
WAVE2_POST_READBACK_ACTION = (
    "prepare_separate_versioned_dependency_wave2_identity_and_"
    "acquisition_decision"
)
EXTERNAL_RESOLUTION_POST_READBACK_ACTION = (
    "resolve_unmapped_and_declared_external_package_imports"
)
FIXED_POINT_POST_READBACK_ACTION = (
    "prepare_dependency_source_review_wave1_fixed_point_closure_decision"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024
DEFAULT_MAXIMUM_ARCHIVE_BYTES = 16 * 1024 * 1024
DEFAULT_MAXIMUM_ENTRY_BYTES = 16 * 1024 * 1024
DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE = 16_384
DEFAULT_MAXIMUM_AGGREGATE_ENTRIES = 131_072
DEFAULT_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_073_741_824
DEFAULT_MAXIMUM_GRAPH_NODES = 512
DEFAULT_MAXIMUM_GRAPH_EDGES = 4_096
MAXIMUM_SAFE_INTEGER = (1 << 63) - 1

ALLOWED_FAILURE_CODES = frozenset(
    {
        "E_INTERPRETER_ISOLATION",
        "E_DECISION_IDENTITY",
        "E_TOOL_IDENTITY",
        "E_PERMIT_STATE",
        "E_PREDECESSOR_IDENTITY",
        "E_HELD_SET",
        "E_INPUT_INVENTORY",
        "E_ARCHIVE_STRUCTURE",
        "E_ARCHIVE_BOUND",
        "E_MODULE_METADATA",
        "E_MODULE_IDENTITY",
        "E_BUILD_CONSTRAINT",
        "E_IMPORT_PARSE",
        "E_GRAPH_SEMANTICS",
        "E_GRAPH_BOUND",
        "E_LICENSE_INVENTORY",
        "E_SPECIAL_SOURCE_CLASSIFICATION",
        "E_ONE_USE_STATE_PRESENT",
        "E_OUTPUT_COLLISION",
        "E_CLAIM_STATE",
        "E_PUBLICATION",
        "E_POST_PUBLISH_UNCERTAIN",
        "E_INTERNAL",
    }
)
ALLOWED_PHASES = frozenset(
    {
        "preflight",
        "held_set",
        "archive",
        "module_metadata",
        "source_inventory",
        "graph",
        "publication",
        "post_publish",
        "runner",
    }
)
SAFE_OBSERVATION_KEYS = frozenset(
    {
        "inputCount",
        "resourceCount",
        "archiveCount",
        "modCount",
        "entryCount",
        "sourceFileCount",
        "moduleCount",
        "graphNodeCount",
        "graphEdgeCount",
        "newTupleCount",
        "resultBytes",
        "manifestBytes",
        "fileWriteCount",
    }
)


class ReviewFailure(RuntimeError):
    """A content-free, fail-closed review error."""

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
        if code not in ALLOWED_FAILURE_CODES:
            code = "E_INTERNAL"
        if phase not in ALLOWED_PHASES:
            phase = "runner"
        super().__init__(code)
        self.code = code
        self.phase = phase
        self.tuple_id = tuple_id
        self.tuple_order = tuple_order
        self.resource_kind = resource_kind
        self.observations = bounded_observations(observations or {})


def require(
    condition: bool,
    code: str,
    phase: str,
    *,
    tuple_id: str | None = None,
    tuple_order: int | None = None,
    resource_kind: str | None = None,
    observations: Mapping[str, int] | None = None,
) -> None:
    if not condition:
        raise ReviewFailure(
            code,
            phase,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
            observations=observations,
        )


def bounded_observations(values: Mapping[str, int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, value in values.items():
        if (
            key in SAFE_OBSERVATION_KEYS
            and type(value) is int
            and 0 <= value <= MAXIMUM_SAFE_INTEGER
        ):
            result[key] = value
    return dict(sorted(result.items()))


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


def content_bound(value: Mapping[str, Any], scope: str) -> dict[str, Any]:
    result = dict(value)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": sha256_bytes(canonical_json_bytes(value)),
    }
    return result


def reject_float(_: str) -> Any:
    raise ReviewFailure("E_PERMIT_STATE", "preflight")


def reject_constant(_: str) -> Any:
    raise ReviewFailure("E_PERMIT_STATE", "preflight")


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(
            type(key) is str and key not in result,
            "E_PERMIT_STATE",
            "preflight",
        )
        result[key] = value
    return result


def validate_json_value(value: Any) -> None:
    if value is None or type(value) in {bool, str}:
        return
    if type(value) is int:
        require(
            -(1 << 63) <= value <= (1 << 63) - 1,
            "E_PERMIT_STATE",
            "preflight",
        )
        return
    if type(value) is list:
        for child in value:
            validate_json_value(child)
        return
    if type(value) is dict:
        for key, child in value.items():
            require(type(key) is str, "E_PERMIT_STATE", "preflight")
            validate_json_value(child)
        return
    if type(value) is float:
        require(math.isfinite(value), "E_PERMIT_STATE", "preflight")
    raise ReviewFailure("E_PERMIT_STATE", "preflight")


def strict_json(raw: bytes, label: str = "json") -> Any:
    del label
    require(len(raw) <= MAXIMUM_JSON_BYTES, "E_PERMIT_STATE", "preflight")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=strict_object,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReviewFailure("E_PERMIT_STATE", "preflight") from error
    validate_json_value(value)
    return value


def exact_bool(value: Any) -> bool:
    require(type(value) is bool, "E_PERMIT_STATE", "preflight")
    return value


def exact_int(value: Any, *, minimum: int = 0) -> int:
    require(
        type(value) is int and minimum <= value <= MAXIMUM_SAFE_INTEGER,
        "E_PERMIT_STATE",
        "preflight",
    )
    return value


def safe_relative_path(value: Any) -> str:
    require(
        type(value) is str
        and value
        and not value.startswith("/")
        and "\x00" not in value
        and "\\" not in value,
        "E_HELD_SET",
        "held_set",
    )
    parts = value.split("/")
    require(
        all(part not in {"", ".", ".."} for part in parts),
        "E_HELD_SET",
        "held_set",
    )
    require(
        PurePosixPath(value).as_posix() == value,
        "E_HELD_SET",
        "held_set",
    )
    return value


def go_proxy_escape(value: Any) -> str:
    require(type(value) is str and value, "E_MODULE_IDENTITY", "preflight")
    escaped: list[str] = []
    for character in value:
        if "A" <= character <= "Z":
            escaped.extend(("!", character.lower()))
        else:
            escaped.append(character)
    return "".join(escaped)


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
                    "E_HELD_SET",
                    "held_set",
                )
                self.directory_fds.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = self.relative.split("/")[-1]
            self.fd = os.open(
                self.name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=self.parent_fd,
            )
            self.initial = os.fstat(self.fd)
            self._validate_info(self.initial)
        except BaseException:
            self.close()
            raise

    def _validate_info(self, info: os.stat_result) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and 0 <= info.st_size <= self.maximum_bytes,
            "E_HELD_SET",
            "held_set",
        )
        if self.owner_only:
            require(
                stat.S_IMODE(info.st_mode) == 0o600,
                "E_HELD_SET",
                "held_set",
            )
        else:
            require(
                stat.S_IMODE(info.st_mode) & 0o022 == 0,
                "E_HELD_SET",
                "held_set",
            )

    def read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_info(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_HELD_SET", "held_set")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", "E_HELD_SET", "held_set")
        after = os.fstat(self.fd)
        require(identity(before) == identity(after), "E_HELD_SET", "held_set")
        return b"".join(chunks)

    def final_barrier(self) -> None:
        current = os.fstat(self.fd)
        named = os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
        require(
            identity(current) == identity(self.initial)
            and identity(named) == identity(self.initial),
            "E_HELD_SET",
            "held_set",
        )
        for child_fd, initial, parent_fd, component in self.directory_fds:
            current_dir = os.fstat(child_fd)
            named_dir = os.stat(
                component,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
            require(
                directory_identity(current_dir) == directory_identity(initial)
                and directory_identity(named_dir) == directory_identity(initial),
                "E_HELD_SET",
                "held_set",
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


class HeldInputSet:
    def __init__(
        self,
        root: Path,
        bindings: Sequence[Mapping[str, Any]],
    ) -> None:
        self.root = root
        self.root_fd = os.open(
            root,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
        )
        self.files: dict[str, HeldFile] = {}
        self.raw: dict[str, bytes] = {}
        try:
            paths: set[str] = set()
            for binding in bindings:
                path = safe_relative_path(binding.get("path"))
                require(path not in paths, "E_INPUT_INVENTORY", "held_set")
                paths.add(path)
                expected = binding.get("rawSha256")
                maximum = exact_int(binding.get("maximumBytes"), minimum=1)
                owner_only = exact_bool(binding.get("ownerOnly"))
                require(
                    type(expected) is str
                    and len(expected) == 64
                    and all(character in "0123456789abcdef" for character in expected),
                    "E_INPUT_INVENTORY",
                    "held_set",
                )
                held = HeldFile(
                    self.root_fd,
                    path,
                    maximum_bytes=maximum,
                    owner_only=owner_only,
                )
                self.files[path] = held
                first = held.read_pass()
                second = held.read_pass()
                require(
                    first == second and sha256_bytes(first) == expected,
                    "E_PREDECESSOR_IDENTITY",
                    "held_set",
                )
                self.raw[path] = first
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        for held in self.files.values():
            held.final_barrier()

    def close(self) -> None:
        for held in self.files.values():
            held.close()
        self.files.clear()
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def __enter__(self) -> "HeldInputSet":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def build_expected_permit(
    *,
    decision_binding: Mapping[str, Any],
    input_bindings: Sequence[Mapping[str, Any]],
    runner_raw_sha256: str,
    runner_tests_raw_sha256: str,
    one_use_paths: Mapping[str, str] | None = None,
    resource_limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    paths = dict(
        one_use_paths
        or {
            "claimPath": CLAIM_PATH,
            "resultPath": RESULT_PATH,
            "failurePath": FAILURE_PATH,
            "manifestPath": MANIFEST_PATH,
        }
    )
    limits = {
        "maximumArchiveBytes": DEFAULT_MAXIMUM_ARCHIVE_BYTES,
        "maximumSingleFileBytes": DEFAULT_MAXIMUM_ENTRY_BYTES,
        "maximumEntriesPerArchive": DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE,
        "maximumAggregateEntries": DEFAULT_MAXIMUM_AGGREGATE_ENTRIES,
        "maximumAggregateUncompressedBytes": (
            DEFAULT_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
        ),
        "maximumGraphNodes": DEFAULT_MAXIMUM_GRAPH_NODES,
        "maximumGraphEdges": DEFAULT_MAXIMUM_GRAPH_EDGES,
        "maximumResultOrFailureBytes": MAXIMUM_JSON_BYTES,
    }
    if resource_limits:
        limits.update(resource_limits)
    body = {
        "documentType": (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-"
            "execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": PERMIT_ID,
        "status": EXPECTED_PERMIT_STATUS,
        "result": (
            "fixed_hash_v3_intake_wp4_graph_frontier_review_authorized_"
            "once_not_executed"
        ),
        "scope": (
            "offline_exact_wave1_module_metadata_profile_graph_license_"
            "and_special_source_inventory_only"
        ),
        "decisionBinding": dict(decision_binding),
        "toolBindings": [
            {
                "role": "review_runner",
                "path": RUNNER_PATH,
                "rawSha256": runner_raw_sha256,
            },
            {
                "role": "review_runner_tests",
                "path": RUNNER_TESTS_PATH,
                "rawSha256": runner_tests_raw_sha256,
            },
        ],
        "inputBindings": {
            "rootArchive": {
                "path": next(
                    row["path"] for row in input_bindings
                    if row.get("kind") == "root_zip"
                ),
                "byteSize": next(
                    row.get("byteSize", row["maximumBytes"])
                    for row in input_bindings
                    if row.get("kind") == "root_zip"
                ),
                "rawSha256": next(
                    row["rawSha256"] for row in input_bindings
                    if row.get("kind") == "root_zip"
                ),
            },
            "resourceCount": sum(
                row.get("kind") in {"mod", "zip"} for row in input_bindings
            ),
            "modCount": sum(row.get("kind") == "mod" for row in input_bindings),
            "zipCount": sum(row.get("kind") == "zip" for row in input_bindings),
            "resources": [
                {
                    key: value
                    for key, value in row.items()
                    if key
                    in {
                        "path",
                        "rawSha256",
                        "module",
                        "version",
                        "kind",
                        "tupleId",
                        "tupleOrder",
                    }
                }
                | {"byteSize": row.get("byteSize", row["maximumBytes"])}
                for row in input_bindings
                if row.get("kind") in {"mod", "zip"}
            ],
        },
        "authority": {
            "permitRecorded": True,
            "boundedDependencySourceReviewWave1Authorized": True,
            "boundedInMemoryArchiveInspectionAuthorized": True,
            "boundedSourceTextStaticInspectionAuthorized": True,
            "verifiedPinnedPermitCheckerModuleLoadingAuthorized": True,
            "oneUseClaimWriteAuthorized": True,
            "boundedResultOrFailureWriteAuthorized": True,
            "manifestWriteAuthorized": True,
            "filesystemExtractionAuthorized": False,
            "sourceMaterializationAuthorized": False,
            "reviewedSourceLoadOrExecutionAuthorized": False,
            "generatorTestHookOrBuildScriptExecutionAuthorized": False,
            "sourceModificationAuthorized": False,
            "packageManagerAuthorized": False,
            "goCommandAuthorized": False,
            "compilerAuthorized": False,
            "shellOrSubprocessAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "networkAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "personalProjectBoundary": {
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationEvaluatedByThisReview": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
        },
        "resourceLimits": limits,
        "oneUseConsumption": {
            **paths,
            "initialState": "authorized_not_consumed",
            "claimCreatedBeforeArchiveMemberOpenOrDecode": True,
            "secondExecutionAllowed": False,
            "automaticRetryAllowed": False,
            "preclaimFailureConsumesPermit": False,
            "postclaimFailureConsumesPermit": True,
            "postclaimUncertaintyConsumesPermit": True,
        },
        "closure": {
            "openFindingCount": 19,
            "findingsClosedByPermit": 0,
            "dependencySourceReviewed": False,
            "graphFixedPointReached": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "nextAction": EXPECTED_PERMIT_NEXT_ACTION,
    }
    return content_bound(body, "permit_without_contentBinding")


def validate_permit(permit: Mapping[str, Any], root: Path) -> list[dict[str, Any]]:
    require(type(permit) is dict, "E_PERMIT_STATE", "preflight")
    require(
        permit.get("permitId") == PERMIT_ID
        and permit.get("status") == EXPECTED_PERMIT_STATUS
        and permit.get("nextAction") == EXPECTED_PERMIT_NEXT_ACTION,
        "E_PERMIT_STATE",
        "preflight",
    )
    authority = permit.get("authority")
    require(type(authority) is dict, "E_PERMIT_STATE", "preflight")
    expected_true = {
        "permitRecorded",
        "boundedDependencySourceReviewWave1Authorized",
        "boundedInMemoryArchiveInspectionAuthorized",
        "boundedSourceTextStaticInspectionAuthorized",
        "verifiedPinnedPermitCheckerModuleLoadingAuthorized",
        "oneUseClaimWriteAuthorized",
        "boundedResultOrFailureWriteAuthorized",
        "manifestWriteAuthorized",
    }
    expected_false = {
        "filesystemExtractionAuthorized",
        "sourceMaterializationAuthorized",
        "reviewedSourceLoadOrExecutionAuthorized",
        "generatorTestHookOrBuildScriptExecutionAuthorized",
        "sourceModificationAuthorized",
        "packageManagerAuthorized",
        "goCommandAuthorized",
        "compilerAuthorized",
        "shellOrSubprocessAuthorized",
        "dnsAuthorized",
        "socketAuthorized",
        "networkAuthorized",
        "deviceAuthorized",
        "deploymentAuthorized",
        "gitWriteAuthorized",
        "repositoryOwnerIdentityProofRequired",
        "externalAuthenticationRequired",
        "userActionRequired",
    }
    require(
        all(authority.get(name) is True for name in expected_true)
        and all(authority.get(name) is False for name in expected_false),
        "E_PERMIT_STATE",
        "preflight",
    )
    personal = permit.get("personalProjectBoundary")
    require(
        type(personal) is dict
        and all(
            personal.get(name) is False
            for name in {
                "repositoryOwnerIdentityProofRequired",
                "externalAuthenticationRequired",
                "signatureRequired",
                "privateKeyRequired",
                "tokenRequired",
                "passwordRequired",
                "userActionRequired",
            }
        ),
        "E_PERMIT_STATE",
        "preflight",
    )
    closure = permit.get("closure")
    require(
        type(closure) is dict
        and closure.get("openFindingCount") == 19
        and closure.get("findingsClosedByPermit") == 0
        and all(
            closure.get(name) is False
            for name in {
                "dependencySourceReviewed",
                "graphFixedPointReached",
                "dependencyClosureComplete",
                "semanticClosureComplete",
                "rungThreeComplete",
                "candidateSelected",
                "librarySelected",
            }
        ),
        "E_PERMIT_STATE",
        "preflight",
    )
    binding = permit.get("contentBinding")
    require(
        type(binding) is dict
        and binding.get("scope") == "permit_without_contentBinding",
        "E_PERMIT_STATE",
        "preflight",
    )
    without = dict(permit)
    without.pop("contentBinding", None)
    require(
        binding.get("sha256") == sha256_bytes(canonical_json_bytes(without)),
        "E_PERMIT_STATE",
        "preflight",
    )
    tools = permit.get("toolBindings")
    require(
        type(tools) is list,
        "E_TOOL_IDENTITY",
        "preflight",
    )
    by_role = {
        row.get("role"): row
        for row in tools
        if type(row) is dict and type(row.get("role")) is str
    }
    require(
        len(by_role) == len(tools)
        and by_role.get("review_runner", {}).get("path") == RUNNER_PATH
        and by_role.get("review_runner_tests", {}).get("path")
        == RUNNER_TESTS_PATH,
        "E_TOOL_IDENTITY",
        "preflight",
    )
    tool_inputs = [
        {
            "path": binding_row.get("path"),
            "rawSha256": binding_row.get("rawSha256"),
            "maximumBytes": MAXIMUM_TOOL_BYTES,
            "ownerOnly": False,
            "kind": "tool",
        }
        for binding_row in tools
    ]
    with HeldInputSet(root, tool_inputs):
        pass
    inputs = permit.get("inputBindings")
    require(
        type(inputs) is dict
        and type(inputs.get("rootArchive")) is dict
        and type(inputs.get("resources")) is list
        and bool(inputs["resources"]),
        "E_INPUT_INVENTORY",
        "preflight",
    )
    decision_binding = permit.get("decisionBinding")
    require(
        type(decision_binding) is dict,
        "E_INPUT_INVENTORY",
        "preflight",
    )
    result: list[dict[str, Any]] = [
        {
            "path": decision_binding.get("path"),
            "rawSha256": decision_binding.get("rawSha256"),
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": False,
            "kind": "decision",
        },
        *tool_inputs,
        *[
            {
                "path": row.get("path"),
                "rawSha256": row.get("rawSha256"),
                "maximumBytes": DEFAULT_MAXIMUM_ARCHIVE_BYTES,
                "ownerOnly": False,
                "kind": "permit_predecessor",
            }
            for row in permit.get("predecessorBindings", [])
            if type(row) is dict
        ],
        {
            "path": inputs["rootArchive"].get("path"),
            "rawSha256": inputs["rootArchive"].get("rawSha256"),
            "maximumBytes": inputs["rootArchive"].get("byteSize"),
            "ownerOnly": True,
            "kind": "root_zip",
            "module": "github.com/pion/ice/v4",
            "version": "v4.3.0",
            "modulePrefix": "github.com/pion/ice/v4@v4.3.0/",
            "tupleId": "root",
            "tupleOrder": 0,
        }
    ]
    seen: set[str] = set()
    for row in result:
        path = safe_relative_path(row.get("path"))
        require(path not in seen, "E_INPUT_INVENTORY", "preflight")
        seen.add(path)
    for value in inputs["resources"]:
        require(type(value) is dict, "E_INPUT_INVENTORY", "preflight")
        row = {
            **dict(value),
            "maximumBytes": value.get("byteSize"),
            "ownerOnly": True,
        }
        if row.get("kind") == "zip":
            row["modulePrefix"] = (
                f"{go_proxy_escape(row.get('module'))}@"
                f"{go_proxy_escape(row.get('version'))}/"
            )
        path = safe_relative_path(row.get("path"))
        require(path not in seen, "E_INPUT_INVENTORY", "preflight")
        seen.add(path)
        require(
            row.get("kind") in {"zip", "mod"},
            "E_INPUT_INVENTORY",
            "preflight",
        )
        result.append(row)
    require(
        inputs.get("resourceCount") == len(inputs["resources"])
        and inputs.get("modCount")
        == sum(row.get("kind") == "mod" for row in inputs["resources"])
        and inputs.get("zipCount")
        == sum(row.get("kind") == "zip" for row in inputs["resources"]),
        "E_INPUT_INVENTORY",
        "preflight",
    )
    return result


def load_permit_checker(root: Path = ROOT) -> types.ModuleType:
    root_fd = -1
    permit_held: HeldFile | None = None
    checker_held: HeldFile | None = None
    try:
        root_fd = os.open(
            root,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
        )
        permit_held = HeldFile(
            root_fd,
            PERMIT_PATH,
            maximum_bytes=MAXIMUM_JSON_BYTES,
            owner_only=False,
        )
        permit_first = permit_held.read_pass()
        permit_second = permit_held.read_pass()
        require(
            permit_first == permit_second,
            "E_TOOL_IDENTITY",
            "preflight",
        )
        permit = strict_json(permit_first, "execution permit")
        require(type(permit) is dict, "E_TOOL_IDENTITY", "preflight")
        tools = permit.get("toolBindings")
        matches = [
            row
            for row in tools if type(row) is dict
            and row.get("role") == "permit_checker"
            and row.get("path") == PERMIT_CHECKER_PATH
        ] if type(tools) is list else []
        require(len(matches) == 1, "E_TOOL_IDENTITY", "preflight")
        checker_held = HeldFile(
            root_fd,
            PERMIT_CHECKER_PATH,
            maximum_bytes=MAXIMUM_TOOL_BYTES,
            owner_only=False,
        )
        raw = checker_held.read_pass()
        require(
            raw == checker_held.read_pass()
            and sha256_bytes(raw) == matches[0].get("rawSha256"),
            "E_TOOL_IDENTITY",
            "preflight",
        )
        permit_held.final_barrier()
        checker_held.final_barrier()
    except (OSError, ReviewFailure) as error:
        raise ReviewFailure("E_TOOL_IDENTITY", "preflight") from error
    finally:
        if checker_held is not None:
            checker_held.close()
        if permit_held is not None:
            permit_held.close()
        if root_fd >= 0:
            os.close(root_fd)
    module = types.ModuleType("aetherlink_g2_dependency_review_permit_checker_v1")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(root / PERMIT_CHECKER_PATH),
            "__loader__": None,
            "__package__": None,
        }
    )
    sys.modules[module.__name__] = module
    try:
        exec(
            compile(
                raw,
                PERMIT_CHECKER_PATH,
                "exec",
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        sys.modules.pop(module.__name__, None)
        raise ReviewFailure("E_TOOL_IDENTITY", "preflight") from error
    require(
        callable(getattr(module, "validate_repository", None)),
        "E_TOOL_IDENTITY",
        "preflight",
    )
    return module


def load_validated_authority(root: Path = ROOT) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checker = load_permit_checker(root)
    try:
        checked = checker.validate_repository(root)
    except Exception as error:
        raise ReviewFailure("E_PERMIT_STATE", "preflight") from error
    require(
        type(checked) is dict
        and type(checked.get("permit")) is dict
        and checked.get("reviewExecutionAuthorized") is True,
        "E_PERMIT_STATE",
        "preflight",
    )
    permit = dict(checked["permit"])
    inputs = validate_permit(permit, root)
    return permit, inputs


def output_paths(permit: Mapping[str, Any]) -> dict[str, str]:
    one_use = permit.get("oneUseConsumption")
    result_contract = permit.get("resultContract")
    manifest_contract = permit.get("manifestContract")
    require(type(one_use) is dict, "E_PERMIT_STATE", "preflight")
    result_paths = result_contract if type(result_contract) is dict else one_use
    manifest_paths = (
        manifest_contract if type(manifest_contract) is dict else one_use
    )
    expected = {
        "claim": CLAIM_PATH,
        "result": RESULT_PATH,
        "failure": FAILURE_PATH,
        "manifest": MANIFEST_PATH,
    }
    names = {
        "claim": one_use.get("claimPath"),
        "result": result_paths.get("resultPath"),
        "failure": result_paths.get("failurePath"),
        "manifest": manifest_paths.get("manifestPath"),
    }
    require(names == expected, "E_PERMIT_STATE", "preflight")
    return {name: safe_relative_path(path) for name, path in names.items()}


def path_kind(root: Path, relative: str) -> str:
    path = root / safe_relative_path(relative)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return "absent"
    except OSError as error:
        raise ReviewFailure("E_ONE_USE_STATE_PRESENT", "preflight") from error
    if stat.S_ISREG(info.st_mode):
        return "regular"
    return "other"


def classify_one_use_state(root: Path, permit: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    paths = output_paths(permit)
    kinds = {name: path_kind(root, path) for name, path in paths.items()}
    if all(value == "absent" for value in kinds.values()):
        return "clean", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["result"] == "regular"
        and kinds["failure"] == "absent"
        and kinds["manifest"] == "regular"
    ):
        return "success", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["result"] == "absent"
        and kinds["failure"] == "regular"
        and kinds["manifest"] == "absent"
    ):
        return "failure", kinds
    return "blocked", kinds


def _eocd_exact(raw: bytes) -> bool:
    signature = b"PK\x05\x06"
    start = raw.rfind(signature, max(0, len(raw) - 65_557))
    if start < 0 or start + 22 > len(raw):
        return False
    comment_length = int.from_bytes(raw[start + 20 : start + 22], "little")
    return start + 22 + comment_length == len(raw)


def safe_archive_name(name: str, expected_prefix: str) -> str:
    require(
        type(name) is str
        and name
        and name.startswith(expected_prefix)
        and not name.endswith("/")
        and not name.startswith("/")
        and "\\" not in name
        and "\x00" not in name
        and "\n" not in name
        and "\r" not in name
        and unicodedata.normalize("NFC", name) == name,
        "E_ARCHIVE_STRUCTURE",
        "archive",
    )
    parts = name.split("/")
    require(
        all(part not in {"", ".", ".."} for part in parts),
        "E_ARCHIVE_STRUCTURE",
        "archive",
    )
    return name


def source_class(relative: str) -> str:
    lower = relative.casefold()
    parts = lower.split("/")
    name = parts[-1]
    if name.endswith("_test.go"):
        return "test"
    if any(part in {"example", "examples", "testdata"} for part in parts[:-1]):
        return "example"
    if any(part in {"cmd", "commands", "tool", "tools"} for part in parts[:-1]):
        return "tool"
    return "production"


def special_classes(relative: str, raw: bytes) -> list[str]:
    lower = relative.casefold()
    result: set[str] = set()
    suffix = PurePosixPath(lower).suffix
    if suffix in {".s", ".asm", ".syso"}:
        result.add("assembly")
    if suffix in {".c", ".cc", ".cpp", ".h", ".m", ".mm"}:
        result.add("native_source")
    if suffix in {".a", ".aar", ".so", ".dylib", ".dll", ".exe", ".wasm"}:
        result.add("binary_artifact")
    if lower.endswith((".sh", ".bat", ".ps1")) or PurePosixPath(lower).name in {
        "makefile",
        "dockerfile",
    }:
        result.add("build_script")
    if "/vendor/" in f"/{lower}/":
        result.add("vendored_source")
    if suffix == ".go":
        prefix = raw[:4096].decode("utf-8", errors="ignore").casefold()
        if "code generated" in prefix and "do not edit" in prefix:
            result.add("generated_source")
        if 'import "c"' in prefix or 'import c "c"' in prefix:
            result.add("cgo")
    return sorted(result)


def is_license_path(relative: str) -> bool:
    name = PurePosixPath(relative).name.casefold()
    return (
        name in {"license", "licence", "copying", "notice"}
        or name.startswith(("license.", "licence.", "copying.", "notice."))
    )


def has_zip64_extra(extra: bytes) -> bool:
    offset = 0
    while offset < len(extra):
        require(
            offset + 4 <= len(extra),
            "E_ARCHIVE_STRUCTURE",
            "archive",
        )
        field_id = int.from_bytes(extra[offset : offset + 2], "little")
        field_size = int.from_bytes(extra[offset + 2 : offset + 4], "little")
        offset += 4
        require(
            offset + field_size <= len(extra),
            "E_ARCHIVE_STRUCTURE",
            "archive",
        )
        if field_id == 0x0001:
            return True
        offset += field_size
    return False


def inspect_zip_bytes(
    raw: bytes,
    binding: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> dict[str, Any]:
    tuple_id = binding.get("tupleId")
    tuple_order = binding.get("tupleOrder")
    kind = binding.get("kind")
    maximum_archive = exact_int(
        limits.get("maximumArchiveBytes", DEFAULT_MAXIMUM_ARCHIVE_BYTES),
        minimum=1,
    )
    require(
        len(raw) <= maximum_archive and _eocd_exact(raw),
        "E_ARCHIVE_BOUND",
        "archive",
        tuple_id=tuple_id if type(tuple_id) is str else None,
        tuple_order=tuple_order if type(tuple_order) is int else None,
        resource_kind=kind if type(kind) is str else None,
    )
    expected_prefix = binding.get("modulePrefix")
    require(
        type(expected_prefix) is str and expected_prefix.endswith("/"),
        "E_MODULE_IDENTITY",
        "archive",
    )
    max_entries = exact_int(
        limits.get("maximumEntriesPerArchive", DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE),
        minimum=1,
    )
    max_file = exact_int(
        limits.get("maximumSingleFileBytes", DEFAULT_MAXIMUM_ENTRY_BYTES),
        minimum=1,
    )
    entries: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    licenses: list[dict[str, Any]] = []
    special: list[dict[str, Any]] = []
    names: set[str] = set()
    folded: set[str] = set()
    total_uncompressed = 0
    embedded_mod: bytes | None = None
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r", allowZip64=False) as archive:
            infos = archive.infolist()
            require(
                0 < len(infos) <= max_entries,
                "E_ARCHIVE_BOUND",
                "archive",
            )
            require(
                min(info.header_offset for info in infos) == 0,
                "E_ARCHIVE_STRUCTURE",
                "archive",
            )
            for info in infos:
                name = safe_archive_name(info.filename, expected_prefix)
                relative = name[len(expected_prefix) :]
                folded_name = name.casefold()
                require(
                    name not in names and folded_name not in folded,
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                names.add(name)
                folded.add(folded_name)
                require(
                    not (info.flag_bits & 0x1)
                    and info.compress_type
                    in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    and not has_zip64_extra(info.extra),
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                mode = (info.external_attr >> 16) & 0xFFFF
                require(
                    mode == 0 or stat.S_ISREG(mode),
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                require(
                    0 <= info.file_size <= max_file,
                    "E_ARCHIVE_BOUND",
                    "archive",
                )
                total_uncompressed += info.file_size
                payload = archive.read(info)
                require(
                    len(payload) == info.file_size,
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                digest = sha256_bytes(payload)
                row = {
                    "relativePath": relative,
                    "rawByteSize": len(payload),
                    "rawSha256": digest,
                }
                entries.append(row)
                if relative == "go.mod":
                    embedded_mod = payload
                if relative.endswith(".go"):
                    try:
                        text = payload.decode("utf-8", errors="strict")
                    except UnicodeDecodeError as error:
                        raise ReviewFailure(
                            "E_IMPORT_PARSE",
                            "source_inventory",
                            tuple_id=tuple_id if type(tuple_id) is str else None,
                        ) from error
                    sources.append(
                        {
                            **row,
                            "sourceClass": source_class(relative),
                            "buildExpression": extract_build_expression(text),
                            "imports": parse_go_imports(text),
                        }
                    )
                if is_license_path(relative):
                    licenses.append(row)
                classes = special_classes(relative, payload)
                if classes:
                    special.append({**row, "classes": classes})
    except ReviewFailure as error:
        raise ReviewFailure(
            error.code,
            error.phase,
            tuple_id=error.tuple_id if error.tuple_id is not None else (
                tuple_id if type(tuple_id) is str else None
            ),
            tuple_order=error.tuple_order if error.tuple_order is not None else (
                tuple_order if type(tuple_order) is int else None
            ),
            resource_kind=(
                error.resource_kind if error.resource_kind is not None else (
                    kind if type(kind) is str else None
                )
            ),
            observations=error.observations,
        ) from error
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ReviewFailure(
            "E_ARCHIVE_STRUCTURE",
            "archive",
            tuple_id=tuple_id if type(tuple_id) is str else None,
            tuple_order=tuple_order if type(tuple_order) is int else None,
            resource_kind=kind if type(kind) is str else None,
        ) from error
    return {
        "module": binding.get("module"),
        "version": binding.get("version"),
        "tupleId": tuple_id,
        "tupleOrder": tuple_order,
        "modulePrefix": expected_prefix,
        "entryCount": len(entries),
        "uncompressedByteCount": total_uncompressed,
        "entrySetSha256": sha256_bytes(canonical_json_bytes(entries)),
        "sources": sources,
        "licenses": licenses,
        "special": special,
        "embeddedGoMod": embedded_mod,
    }


def strip_go_mod_comment(line: str) -> str:
    quoted = False
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if not quoted and line[index : index + 2] == "//":
            return line[:index]
    return line


VERSION_RE = re.compile(
    r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
MODULE_RE = re.compile(r"^[A-Za-z0-9._~+/-]+$")


def valid_module(value: str) -> bool:
    return bool(MODULE_RE.fullmatch(value)) and ("/" in value or "." in value)


def valid_version(value: str) -> bool:
    return bool(VERSION_RE.fullmatch(value))


def tokenize_mod_line(line: str) -> list[str]:
    try:
        return shlex.split(strip_go_mod_comment(line), comments=False, posix=True)
    except ValueError as error:
        raise ReviewFailure("E_MODULE_METADATA", "module_metadata") from error


def parse_go_mod(raw: bytes, expected_module: str | None = None) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewFailure("E_MODULE_METADATA", "module_metadata") from error
    require("\x00" not in text, "E_MODULE_METADATA", "module_metadata")
    directives: dict[str, list[list[str]]] = defaultdict(list)
    block: str | None = None
    allowed = {"module", "go", "toolchain", "require", "replace", "exclude", "retract"}
    for raw_line in text.splitlines():
        tokens = tokenize_mod_line(raw_line)
        if not tokens:
            continue
        if block is not None:
            if tokens == [")"]:
                block = None
                continue
            directives[block].append(tokens)
            continue
        if len(tokens) == 2 and tokens[1] == "(":
            require(tokens[0] in allowed, "E_MODULE_METADATA", "module_metadata")
            block = tokens[0]
            continue
        directive = tokens[0]
        require(directive in allowed, "E_MODULE_METADATA", "module_metadata")
        directives[directive].append(tokens[1:])
    require(block is None, "E_MODULE_METADATA", "module_metadata")
    require(
        len(directives["module"]) == 1
        and len(directives["module"][0]) == 1,
        "E_MODULE_METADATA",
        "module_metadata",
    )
    module = directives["module"][0][0]
    require(valid_module(module), "E_MODULE_METADATA", "module_metadata")
    if expected_module is not None:
        require(module == expected_module, "E_MODULE_IDENTITY", "module_metadata")
    for name in ("go", "toolchain"):
        require(len(directives[name]) <= 1, "E_MODULE_METADATA", "module_metadata")
    requires: list[dict[str, Any]] = []
    for row in directives["require"]:
        require(
            len(row) == 2 and valid_module(row[0]) and valid_version(row[1]),
            "E_MODULE_METADATA",
            "module_metadata",
        )
        requires.append({"module": row[0], "version": row[1]})
    replaces: list[dict[str, Any]] = []
    for row in directives["replace"]:
        require(
            "=>" in row and row.count("=>") == 1,
            "E_MODULE_METADATA",
            "module_metadata",
        )
        split = row.index("=>")
        old, new = row[:split], row[split + 1 :]
        require(
            len(old) in {1, 2}
            and len(new) in {1, 2}
            and valid_module(old[0])
            and valid_module(new[0])
            and (len(old) == 1 or valid_version(old[1]))
            and (len(new) == 1 or valid_version(new[1])),
            "E_MODULE_METADATA",
            "module_metadata",
        )
        replaces.append({"old": old, "new": new})
    excludes: list[dict[str, str]] = []
    for row in directives["exclude"]:
        require(
            len(row) == 2 and valid_module(row[0]) and valid_version(row[1]),
            "E_MODULE_METADATA",
            "module_metadata",
        )
        excludes.append({"module": row[0], "version": row[1]})
    retracts = [" ".join(row) for row in directives["retract"]]
    result = {
        "module": module,
        "goVersion": (
            directives["go"][0][0]
            if directives["go"] and len(directives["go"][0]) == 1
            else None
        ),
        "toolchain": (
            directives["toolchain"][0][0]
            if directives["toolchain"]
            and len(directives["toolchain"][0]) == 1
            else None
        ),
        "requires": sorted(requires, key=lambda row: (row["module"], row["version"])),
        "replaces": sorted(replaces, key=canonical_json_bytes),
        "excludes": sorted(excludes, key=lambda row: (row["module"], row["version"])),
        "retracts": sorted(retracts),
    }
    result["semanticSha256"] = sha256_bytes(canonical_json_bytes(result))
    return result


BUILD_TOKEN = re.compile(r"\s*(\|\||&&|!|\(|\)|[A-Za-z0-9_.]+)")


def build_tokens(expression: str) -> list[str]:
    tokens: list[str] = []
    position = 0
    while position < len(expression):
        match = BUILD_TOKEN.match(expression, position)
        require(match is not None, "E_BUILD_CONSTRAINT", "source_inventory")
        tokens.append(match.group(1))
        position = match.end()
    return tokens


class BuildExpression:
    def __init__(self, tokens: Sequence[str], tags: set[str]) -> None:
        self.tokens = list(tokens)
        self.tags = tags
        self.index = 0

    def parse(self) -> bool:
        result = self.parse_or()
        require(
            self.index == len(self.tokens),
            "E_BUILD_CONSTRAINT",
            "source_inventory",
        )
        return result

    def parse_or(self) -> bool:
        value = self.parse_and()
        while self._take("||"):
            right = self.parse_and()
            value = value or right
        return value

    def parse_and(self) -> bool:
        value = self.parse_unary()
        while self._take("&&"):
            right = self.parse_unary()
            value = value and right
        return value

    def parse_unary(self) -> bool:
        if self._take("!"):
            return not self.parse_unary()
        if self._take("("):
            value = self.parse_or()
            require(self._take(")"), "E_BUILD_CONSTRAINT", "source_inventory")
            return value
        require(self.index < len(self.tokens), "E_BUILD_CONSTRAINT", "source_inventory")
        token = self.tokens[self.index]
        require(
            token not in {"||", "&&", ")", "("},
            "E_BUILD_CONSTRAINT",
            "source_inventory",
        )
        self.index += 1
        return token in self.tags

    def _take(self, token: str) -> bool:
        if self.index < len(self.tokens) and self.tokens[self.index] == token:
            self.index += 1
            return True
        return False


LEGACY_BUILD_TERM = re.compile(r"!?[A-Za-z0-9_.]+")
MODERN_BUILD_MARKER = "//go:build"
LEGACY_BUILD_MARKER = "// +build"


def legacy_build_expression(lines: Sequence[str]) -> str:
    line_expressions: list[str] = []
    for line in lines:
        options = line.split()
        require(bool(options), "E_BUILD_CONSTRAINT", "source_inventory")
        option_expressions: list[str] = []
        for option in options:
            terms = option.split(",")
            require(
                bool(terms)
                and all(
                    bool(term) and LEGACY_BUILD_TERM.fullmatch(term) is not None
                    for term in terms
                ),
                "E_BUILD_CONSTRAINT",
                "source_inventory",
            )
            option_expressions.append(
                "(" + " && ".join(terms) + ")"
            )
        line_expressions.append(
            "(" + " || ".join(option_expressions) + ")"
        )
    require(bool(line_expressions), "E_BUILD_CONSTRAINT", "source_inventory")
    expression = " && ".join(line_expressions)
    build_tokens(expression)
    return expression


def extract_build_expression(text: str) -> str | None:
    expressions: list[str] = []
    legacy_lines: list[str] = []
    in_block_comment = False
    saw_package = False
    legacy_blank_boundary = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_block_comment:
            for marker, destination in (
                (MODERN_BUILD_MARKER, expressions),
                (LEGACY_BUILD_MARKER, legacy_lines),
            ):
                if stripped == marker:
                    raise ReviewFailure(
                        "E_BUILD_CONSTRAINT",
                        "source_inventory",
                    )
                if stripped.startswith(marker):
                    suffix = stripped[len(marker) :]
                    if suffix and suffix[0].isspace():
                        expression = suffix.strip()
                        require(
                            bool(expression),
                            "E_BUILD_CONSTRAINT",
                            "source_inventory",
                        )
                        destination.append(expression)
                        if marker == LEGACY_BUILD_MARKER:
                            legacy_blank_boundary = False
        if (
            not in_block_comment
            and not stripped
            and legacy_lines
        ):
            legacy_blank_boundary = True
        cursor = 0
        while cursor < len(line):
            while cursor < len(line) and line[cursor].isspace():
                cursor += 1
            if cursor == len(line):
                break
            if in_block_comment:
                end = line.find("*/", cursor)
                if end < 0:
                    cursor = len(line)
                    continue
                in_block_comment = False
                cursor = end + 2
                continue
            if line.startswith("//", cursor):
                cursor = len(line)
                continue
            if line.startswith("/*", cursor):
                in_block_comment = True
                cursor += 2
                continue
            require(
                re.match(r"package(?:\s|$)", line[cursor:]) is not None,
                "E_BUILD_CONSTRAINT",
                "source_inventory",
            )
            saw_package = True
            break
        if saw_package:
            break
    require(
        not in_block_comment and saw_package,
        "E_BUILD_CONSTRAINT",
        "source_inventory",
    )
    require(len(expressions) <= 1, "E_BUILD_CONSTRAINT", "source_inventory")
    if legacy_lines and not legacy_blank_boundary:
        legacy_lines = []
    if expressions:
        require(bool(expressions[0]), "E_BUILD_CONSTRAINT", "source_inventory")
        build_tokens(expressions[0])
        return expressions[0]
    return legacy_build_expression(legacy_lines) if legacy_lines else None


def active_for_profile(expression: str | None, tags: Iterable[str]) -> bool:
    if expression is None:
        return True
    return BuildExpression(build_tokens(expression), set(tags)).parse()


def active_for_profile_monotone(
    expression: str | None,
    tags: Iterable[str],
) -> bool:
    if expression is None:
        return True
    tokens: list[str] = []
    position = 0
    while position < len(expression):
        match = BUILD_TOKEN.match(expression, position)
        require(match is not None, "E_BUILD_CONSTRAINT", "source_inventory")
        tokens.append(match.group(1))
        position = match.end()
    output: list[str] = []
    operators: list[str] = []
    precedence = {"!": 3, "&&": 2, "||": 1}
    expect_operand = True
    for token in tokens:
        if token not in {"!", "&&", "||", "(", ")"}:
            require(expect_operand, "E_BUILD_CONSTRAINT", "source_inventory")
            output.append(token)
            expect_operand = False
        elif token == "!":
            require(expect_operand, "E_BUILD_CONSTRAINT", "source_inventory")
            operators.append(token)
        elif token == "(":
            require(expect_operand, "E_BUILD_CONSTRAINT", "source_inventory")
            operators.append(token)
        elif token == ")":
            require(not expect_operand, "E_BUILD_CONSTRAINT", "source_inventory")
            while operators and operators[-1] != "(":
                output.append(operators.pop())
            require(
                bool(operators) and operators.pop() == "(",
                "E_BUILD_CONSTRAINT",
                "source_inventory",
            )
            expect_operand = False
        else:
            require(not expect_operand, "E_BUILD_CONSTRAINT", "source_inventory")
            while (
                operators
                and operators[-1] != "("
                and precedence[operators[-1]] >= precedence[token]
            ):
                output.append(operators.pop())
            operators.append(token)
            expect_operand = True
    require(tokens and not expect_operand, "E_BUILD_CONSTRAINT", "source_inventory")
    while operators:
        operator = operators.pop()
        require(operator != "(", "E_BUILD_CONSTRAINT", "source_inventory")
        output.append(operator)
    tag_set = set(tags)
    values: list[bool] = []
    for token in output:
        if token == "!":
            require(bool(values), "E_BUILD_CONSTRAINT", "source_inventory")
            values.append(not values.pop())
        elif token in {"&&", "||"}:
            require(len(values) >= 2, "E_BUILD_CONSTRAINT", "source_inventory")
            right = values.pop()
            left = values.pop()
            values.append(left and right if token == "&&" else left or right)
        else:
            values.append(token in tag_set)
    require(len(values) == 1, "E_BUILD_CONSTRAINT", "source_inventory")
    return values[0]


def scan_go_quoted_literal(text: str, start: int, quote: str) -> int:
    require(
        0 <= start < len(text)
        and text[start] == quote
        and quote in {'"', "'", "`"},
        "E_IMPORT_PARSE",
        "source_inventory",
    )
    index = start + 1
    escaped = False
    while index < len(text):
        current = text[index]
        if quote != "`" and current in "\r\n":
            raise ReviewFailure("E_IMPORT_PARSE", "source_inventory")
        if quote != "`" and escaped:
            escaped = False
        elif quote != "`" and current == "\\":
            escaped = True
        elif current == quote:
            return index + 1
        index += 1
    raise ReviewFailure("E_IMPORT_PARSE", "source_inventory")


def go_tokens(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end + 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            require(end >= 0, "E_IMPORT_PARSE", "source_inventory")
            index = end + 2
            continue
        if character in {'"', "'", "`"}:
            quote = character
            start = index
            index = scan_go_quoted_literal(text, start, quote)
            literal = text[start:index]
            if quote == "'":
                tokens.append(("rune", literal))
                continue
            try:
                value = (
                    bytes(literal[1:-1], "utf-8").decode("unicode_escape")
                    if quote == '"'
                    else literal[1:-1]
                )
            except UnicodeDecodeError as error:
                raise ReviewFailure("E_IMPORT_PARSE", "source_inventory") from error
            tokens.append(("string", value))
            continue
        if character.isalpha() or character == "_":
            start = index
            index += 1
            while index < len(text) and (
                text[index].isalnum() or text[index] == "_"
            ):
                index += 1
            tokens.append(("identifier", text[start:index]))
            continue
        tokens.append(("punctuation", character))
        index += 1
    return tokens


def parse_go_imports(text: str) -> list[str]:
    tokens = go_tokens(text)
    imports: list[str] = []
    index = 0
    while index < len(tokens):
        if tokens[index] != ("identifier", "import"):
            index += 1
            continue
        index += 1
        if index < len(tokens) and tokens[index] == ("punctuation", "("):
            index += 1
            while index < len(tokens) and tokens[index] != ("punctuation", ")"):
                if tokens[index][0] in {"identifier", "punctuation"}:
                    index += 1
                require(
                    index < len(tokens) and tokens[index][0] == "string",
                    "E_IMPORT_PARSE",
                    "source_inventory",
                )
                imports.append(tokens[index][1])
                index += 1
            require(
                index < len(tokens) and tokens[index] == ("punctuation", ")"),
                "E_IMPORT_PARSE",
                "source_inventory",
            )
            index += 1
        else:
            if index < len(tokens) and tokens[index][0] in {
                "identifier",
                "punctuation",
            }:
                index += 1
            require(
                index < len(tokens) and tokens[index][0] == "string",
                "E_IMPORT_PARSE",
                "source_inventory",
            )
            imports.append(tokens[index][1])
            index += 1
    require(
        all(
            value
            and not value.startswith("/")
            and "\\" not in value
            and "\x00" not in value
            and "\n" not in value
            for value in imports
        ),
        "E_IMPORT_PARSE",
        "source_inventory",
    )
    return sorted(set(imports))


def semver_key(version: str) -> tuple[Any, ...]:
    require(valid_version(version), "E_GRAPH_SEMANTICS", "graph")
    body = version[1:].split("+", 1)[0]
    main, separator, pre = body.partition("-")
    major, minor, patch = (int(value) for value in main.split("."))
    if not separator:
        return major, minor, patch, 1, ()
    identifiers: list[tuple[int, Any]] = []
    for value in pre.split("."):
        identifiers.append(
            (0, int(value)) if value.isdigit() else (1, value)
        )
    return major, minor, patch, 0, tuple(identifiers)


GO_1_24_RELEASE_TAGS = frozenset(
    f"go1.{minor}" for minor in range(1, 25)
)


def frozen_profile_tag_set(
    tags: Iterable[str],
    goos: str,
    goarch: str = "arm64",
) -> set[str]:
    require(goarch == "arm64", "E_GRAPH_SEMANTICS", "graph")
    result = set(tags)
    result.update(GO_1_24_RELEASE_TAGS)
    result.add("arm64.v8.0")
    if goos == "android":
        result.add("linux")
    return result


def profile_rows(permit: Mapping[str, Any]) -> list[dict[str, Any]]:
    decision = permit.get("decisionBinding")
    profiles = decision.get("profiles") if type(decision) is dict else None
    if type(profiles) is not list:
        profiles = [
            {
                "profileId": "android_api_26_through_36_arm64_v8a",
                "tags": ["android", "arm64", "unix", "cgo", "gc", "go1.24"],
            },
            {
                "profileId": "macos_14_or_newer_arm64",
                "tags": ["darwin", "arm64", "unix", "cgo", "gc", "go1.24"],
            },
        ]
    result: list[dict[str, Any]] = []
    for row in profiles:
        require(
            type(row) is dict
            and type(row.get("profileId")) is str
            and type(row.get("tags")) is list
            and all(type(value) is str for value in row["tags"]),
            "E_PERMIT_STATE",
            "preflight",
        )
        initial_tags = set(row["tags"])
        goos_values = sorted(initial_tags & {"android", "darwin"})
        goarch_values = sorted(initial_tags & {"arm64"})
        require(
            len(goos_values) == 1 and goarch_values == ["arm64"],
            "E_PERMIT_STATE",
            "preflight",
        )
        tags = sorted(
            frozen_profile_tag_set(
                initial_tags,
                goos_values[0],
                "arm64",
            )
        )
        result.append(
            {
                "profileId": row["profileId"],
                "goos": goos_values[0],
                "goarch": "arm64",
                "tags": tags,
            }
        )
    require(
        bool(result)
        and len({row["profileId"] for row in result}) == len(result),
        "E_PERMIT_STATE",
        "preflight",
    )
    return result


KNOWN_GOOS = frozenset(
    {
        "aix",
        "android",
        "darwin",
        "dragonfly",
        "freebsd",
        "illumos",
        "ios",
        "js",
        "linux",
        "netbsd",
        "openbsd",
        "plan9",
        "solaris",
        "wasip1",
        "windows",
    }
)
KNOWN_GOARCH = frozenset(
    {
        "386",
        "amd64",
        "arm",
        "arm64",
        "loong64",
        "mips",
        "mips64",
        "mips64le",
        "mipsle",
        "ppc64",
        "ppc64le",
        "riscv64",
        "s390x",
        "wasm",
    }
)


def normalized_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    tags = profile.get("tags")
    require(
        type(profile.get("profileId")) is str
        and type(tags) is list
        and all(type(value) is str for value in tags),
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    tag_set = set(tags)
    goos = profile.get("goos")
    goarch = profile.get("goarch")
    if goos is None:
        candidates = sorted(tag_set & {"android", "darwin"})
        require(len(candidates) == 1, "E_GRAPH_SEMANTICS", "graph")
        goos = candidates[0]
    if goarch is None:
        require("arm64" in tag_set, "E_GRAPH_SEMANTICS", "graph")
        goarch = "arm64"
    require(
        goos in {"android", "darwin"}
        and goarch == "arm64"
        and goos in tag_set
        and goarch in tag_set,
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    tag_set = frozen_profile_tag_set(tag_set, goos, goarch)
    return {
        "profileId": profile["profileId"],
        "goos": goos,
        "goarch": goarch,
        "tags": sorted(tag_set),
    }


def filename_active_for_profile(
    relative: str,
    goos: str,
    goarch: str,
) -> bool:
    path = PurePosixPath(relative)
    name = path.name
    require(name.endswith(".go"), "E_GRAPH_SEMANTICS", "graph")
    if any(part.startswith(("_", ".")) for part in path.parts):
        return False
    stem = name.split(".", 1)[0]
    parts = stem.split("_")
    if len(parts) >= 2 and parts[-1] in KNOWN_GOARCH:
        if parts[-1] != goarch:
            return False
        if len(parts) >= 3 and parts[-2] in KNOWN_GOOS:
            allowed_goos = {goos, "linux"} if goos == "android" else {goos}
            return parts[-2] in allowed_goos
        return True
    if len(parts) >= 2 and parts[-1] in KNOWN_GOOS:
        allowed_goos = {goos, "linux"} if goos == "android" else {goos}
        return parts[-1] in allowed_goos
    return True


def filename_active_for_profile_monotone(
    relative: str,
    goos: str,
    goarch: str,
) -> bool:
    components = relative.split("/")
    require(
        components
        and all(component not in {"", ".", ".."} for component in components)
        and components[-1].endswith(".go"),
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    for component in components:
        if component[0] in {"_", "."}:
            return False
    stem, _, _ = components[-1].partition(".")
    suffixes = stem.split("_")
    allowed_goos = {goos}
    if goos == "android":
        allowed_goos.add("linux")
    if suffixes[-1] in KNOWN_GOARCH:
        if suffixes[-1] != goarch:
            return False
        if len(suffixes) >= 3 and suffixes[-2] in KNOWN_GOOS:
            return suffixes[-2] in allowed_goos
        return True
    if len(suffixes) >= 2 and suffixes[-1] in KNOWN_GOOS:
        return suffixes[-1] in allowed_goos
    return True


def module_metadata_by_pair(
    metadata: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    by_pair: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in metadata:
        module = row.get("module")
        version = row.get("version")
        require(
            type(module) is str
            and type(version) is str
            and valid_version(version)
            and type(row.get("metadata")) is dict
            and row["metadata"].get("module") == module
            and (module, version) not in by_pair,
            "E_GRAPH_SEMANTICS",
            "graph",
        )
        by_pair[(module, version)] = row
    return by_pair


def root_module_pair(
    root_module: str,
    by_pair: Mapping[tuple[str, str], Mapping[str, Any]],
    archive_pairs: set[tuple[str, str]],
) -> tuple[str, str]:
    root_versions = sorted(
        version for module, version in by_pair if module == root_module
    )
    require(
        len(root_versions) == 1
        and (root_module, root_versions[0]) in archive_pairs,
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    return root_module, root_versions[0]


def finalize_module_version_graph(
    root_pair: tuple[str, str],
    vertices: set[tuple[str, str]],
    raw_edges: set[tuple[str, str, str, str]],
    by_pair: Mapping[tuple[str, str], Mapping[str, Any]],
    archive_pairs: set[tuple[str, str]],
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    selected: dict[str, str] = {}
    for module, version in sorted(vertices):
        current = selected.get(module)
        if current is None or semver_key(version) > semver_key(current):
            selected[module] = version
    nodes = [
        {
            "module": module,
            "version": version,
            "isRoot": (module, version) == root_pair,
            "sourceAvailable": (
                (module, version) in archive_pairs
                and (module, version) in by_pair
            ),
            "frontier": not (
                (module, version) in archive_pairs
                and (module, version) in by_pair
            ),
            "selectedForModule": selected[module] == version,
        }
        for module, version in sorted(vertices)
    ]
    edges = [
        {
            "fromModule": from_module,
            "fromVersion": from_version,
            "requiredModule": required_module,
            "requestedVersion": requested_version,
            "selectedVersion": selected[required_module],
            "targetSourceAvailable": (
                (required_module, requested_version) in archive_pairs
                and (required_module, requested_version) in by_pair
            ),
        }
        for (
            from_module,
            from_version,
            required_module,
            requested_version,
        ) in sorted(raw_edges)
    ]
    return selected, nodes, edges


def finalize_module_version_graph_monotone(
    root_pair: tuple[str, str],
    vertices: set[tuple[str, str]],
    raw_edges: set[tuple[str, str, str, str]],
    by_pair: Mapping[tuple[str, str], Mapping[str, Any]],
    archive_pairs: set[tuple[str, str]],
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    versions_by_module: dict[str, list[str]] = defaultdict(list)
    for module, version in vertices:
        versions_by_module[module].append(version)
    selected = {
        module: max(versions, key=semver_key)
        for module, versions in sorted(versions_by_module.items())
    }
    nodes: list[dict[str, Any]] = []
    for pair in sorted(vertices):
        available = pair in archive_pairs and pair in by_pair
        nodes.append(
            {
                "module": pair[0],
                "version": pair[1],
                "isRoot": pair == root_pair,
                "sourceAvailable": available,
                "frontier": not available,
                "selectedForModule": selected[pair[0]] == pair[1],
            }
        )
    edges: list[dict[str, Any]] = []
    for raw_edge in sorted(raw_edges):
        target_pair = (raw_edge[2], raw_edge[3])
        edges.append(
            {
                "fromModule": raw_edge[0],
                "fromVersion": raw_edge[1],
                "requiredModule": raw_edge[2],
                "requestedVersion": raw_edge[3],
                "selectedVersion": selected[raw_edge[2]],
                "targetSourceAvailable": (
                    target_pair in archive_pairs and target_pair in by_pair
                ),
            }
        )
    return selected, nodes, edges


def module_graph(
    root_module: str,
    metadata: Sequence[Mapping[str, Any]],
    archive_pairs: set[tuple[str, str]],
    maximum_nodes: int,
    maximum_edges: int,
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    by_pair = module_metadata_by_pair(metadata)
    root_pair = root_module_pair(root_module, by_pair, archive_pairs)
    queue = deque([root_pair])
    visited: set[tuple[str, str]] = set()
    raw_edges: set[tuple[str, str, str, str]] = set()
    while queue:
        pair = queue.popleft()
        if pair in visited:
            continue
        visited.add(pair)
        require(
            len(visited) <= maximum_nodes,
            "E_GRAPH_BOUND",
            "graph",
        )
        if pair not in archive_pairs or pair not in by_pair:
            continue
        for required in by_pair[pair]["metadata"]["requires"]:
            target_pair = (required["module"], required["version"])
            raw_edges.add((pair[0], pair[1], target_pair[0], target_pair[1]))
            require(
                len(raw_edges) <= maximum_edges,
                "E_GRAPH_BOUND",
                "graph",
            )
            queue.append(target_pair)
    return finalize_module_version_graph(
        root_pair,
        visited,
        raw_edges,
        by_pair,
        archive_pairs,
    )


def package_edge_bfs(
    profile_id: str,
    package: str,
    imported: str,
    packages: Mapping[str, Mapping[str, Any]],
    candidate_modules: Sequence[str],
    selected: Mapping[str, str],
) -> dict[str, Any]:
    if imported in packages:
        target_module = packages[imported]["module"]
        target_version = selected.get(target_module)
        edge_class = "internal_or_acquired"
    elif "." not in imported.split("/", 1)[0]:
        target_module = None
        target_version = None
        edge_class = "standard_library"
    else:
        target_module = next(
            (
                module
                for module in candidate_modules
                if imported == module or imported.startswith(module + "/")
            ),
            None,
        )
        target_version = (
            selected.get(target_module) if target_module is not None else None
        )
        edge_class = (
            "declared_external"
            if target_module is not None
            else "unmapped_external"
        )
    return {
        "profileId": profile_id,
        "fromPackage": package,
        "importPath": imported,
        "targetModule": target_module,
        "targetVersion": target_version,
        "edgeClass": edge_class,
    }


def package_edge_monotone(
    profile_id: str,
    package: str,
    imported: str,
    packages: Mapping[str, Mapping[str, Any]],
    candidate_modules: Sequence[str],
    selected: Mapping[str, str],
) -> dict[str, Any]:
    if imported in packages:
        target_module = packages[imported]["module"]
        target_version = selected.get(target_module)
        edge_class = "internal_or_acquired"
    elif "." not in imported.partition("/")[0]:
        target_module = None
        target_version = None
        edge_class = "standard_library"
    else:
        target_module = None
        for candidate in candidate_modules:
            if imported == candidate or imported.startswith(candidate + "/"):
                target_module = candidate
                break
        if target_module is None:
            target_version = None
            edge_class = "unmapped_external"
        else:
            target_version = selected.get(target_module)
            edge_class = "declared_external"
    return {
        "profileId": profile_id,
        "fromPackage": package,
        "importPath": imported,
        "targetModule": target_module,
        "targetVersion": target_version,
        "edgeClass": edge_class,
    }


def package_graph_bfs(
    profile_id: str,
    root_module: str,
    packages: Mapping[str, Mapping[str, Any]],
    candidate_modules: Sequence[str],
    selected: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    queue = deque([root_module])
    visited: set[str] = set()
    edges: list[dict[str, Any]] = []
    while queue:
        package = queue.popleft()
        if package in visited:
            continue
        visited.add(package)
        row = packages[package]
        for imported in sorted(row["imports"]):
            edge = package_edge_bfs(
                profile_id,
                package,
                imported,
                packages,
                candidate_modules,
                selected,
            )
            edges.append(edge)
            if imported in packages:
                queue.append(imported)
    nodes = [
        {
            "profileId": profile_id,
            "module": packages[package]["module"],
            "package": package,
        }
        for package in sorted(visited)
    ]
    return nodes, sorted(
        edges,
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
        ),
    )


def package_graph_fixed_point(
    profile_id: str,
    root_module: str,
    packages: Mapping[str, Mapping[str, Any]],
    candidate_modules: Sequence[str],
    selected: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reachable = {root_module}
    edges_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    while True:
        expanded = set(reachable)
        for package in sorted(reachable):
            row = packages[package]
            for imported in sorted(row["imports"]):
                edge = package_edge_monotone(
                    profile_id,
                    package,
                    imported,
                    packages,
                    candidate_modules,
                    selected,
                )
                edges_by_key[(profile_id, package, imported)] = edge
                if imported in packages:
                    expanded.add(imported)
        if expanded == reachable:
            break
        reachable = expanded
    nodes = [
        {
            "profileId": profile_id,
            "module": packages[package]["module"],
            "package": package,
        }
        for package in sorted(reachable)
    ]
    edges = [
        edges_by_key[key]
        for key in sorted(edges_by_key)
    ]
    return nodes, edges


def module_graph_monotone(
    root_module: str,
    metadata: Sequence[Mapping[str, Any]],
    archive_pairs: set[tuple[str, str]],
    maximum_nodes: int,
    maximum_edges: int,
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    by_pair = module_metadata_by_pair(metadata)
    root_pair = root_module_pair(root_module, by_pair, archive_pairs)
    vertices = {root_pair}
    raw_edges: set[tuple[str, str, str, str]] = set()
    while True:
        expanded_vertices = set(vertices)
        expanded_edges = set(raw_edges)
        for pair in sorted(vertices):
            if pair not in archive_pairs or pair not in by_pair:
                continue
            for required in by_pair[pair]["metadata"]["requires"]:
                target_pair = (required["module"], required["version"])
                expanded_vertices.add(target_pair)
                expanded_edges.add(
                    (pair[0], pair[1], target_pair[0], target_pair[1])
                )
        require(
            len(expanded_vertices) <= maximum_nodes
            and len(expanded_edges) <= maximum_edges,
            "E_GRAPH_BOUND",
            "graph",
        )
        if expanded_vertices == vertices and expanded_edges == raw_edges:
            break
        vertices = expanded_vertices
        raw_edges = expanded_edges
    selected, nodes, edges = finalize_module_version_graph_monotone(
        root_pair,
        vertices,
        raw_edges,
        by_pair,
        archive_pairs,
    )
    require(
        len(nodes) <= maximum_nodes and len(edges) <= maximum_edges,
        "E_GRAPH_BOUND",
        "graph",
    )
    return selected, nodes, edges


def profile_package_reconstruction_bfs(
    archives: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    root_module: str,
    selected: Mapping[str, str],
    module_nodes: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_modules = sorted(
        set(selected),
        key=lambda value: (-len(value), value),
    )
    available_selected_pairs = {
        (row["module"], row["version"])
        for row in module_nodes
        if row["sourceAvailable"] and row["selectedForModule"]
    }
    result_nodes: list[dict[str, Any]] = []
    result_edges: list[dict[str, Any]] = []
    for raw_profile in profiles:
        profile = normalized_profile(dict(raw_profile))
        packages: dict[str, dict[str, Any]] = {}
        for archive in archives:
            module = archive["module"]
            version = archive["version"]
            if (
                archive.get("kind") != "root_zip"
                and (
                    selected.get(module) != version
                    or (module, version) not in available_selected_pairs
                )
            ):
                continue
            for source in archive["sources"]:
                filename_active = filename_active_for_profile(
                    source["relativePath"],
                    profile["goos"],
                    profile["goarch"],
                )
                expression_active = active_for_profile(
                    source["buildExpression"],
                    set(profile["tags"]),
                )
                if (
                    source["sourceClass"] != "production"
                    or not filename_active
                    or not expression_active
                ):
                    continue
                directory = str(PurePosixPath(source["relativePath"]).parent)
                package = module if directory == "." else f"{module}/{directory}"
                row = packages.setdefault(
                    package,
                    {"module": module, "imports": set()},
                )
                row["imports"].update(source["imports"])
        require(
            root_module in packages
            and packages[root_module]["module"] == root_module,
            "E_GRAPH_SEMANTICS",
            "graph",
        )
        nodes, edges = package_graph_bfs(
            profile["profileId"],
            root_module,
            packages,
            candidate_modules,
            selected,
        )
        result_nodes.extend(nodes)
        result_edges.extend(edges)
    result_nodes.sort(
        key=lambda row: (row["profileId"], row["module"], row["package"])
    )
    result_edges.sort(
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
        )
    )
    return result_nodes, result_edges


def profile_package_reconstruction_monotone(
    archives: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    root_module: str,
    selected: Mapping[str, str],
    module_nodes: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_modules = sorted(
        selected.keys(),
        key=lambda value: (-len(value), value),
    )
    usable_pairs: set[tuple[str, str]] = set()
    for node in module_nodes:
        if node["sourceAvailable"] and node["selectedForModule"]:
            usable_pairs.add((node["module"], node["version"]))
    all_nodes: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    for raw_profile in profiles:
        profile = normalized_profile(dict(raw_profile))
        packages: dict[str, dict[str, Any]] = {}
        for archive in archives:
            module = archive["module"]
            version = archive["version"]
            use_archive = archive.get("kind") == "root_zip" or (
                selected.get(module) == version
                and (module, version) in usable_pairs
            )
            if not use_archive:
                continue
            for source in archive["sources"]:
                if source["sourceClass"] != "production":
                    continue
                if not filename_active_for_profile_monotone(
                    source["relativePath"],
                    profile["goos"],
                    profile["goarch"],
                ):
                    continue
                if not active_for_profile_monotone(
                    source["buildExpression"],
                    set(profile["tags"]),
                ):
                    continue
                parent = str(PurePosixPath(source["relativePath"]).parent)
                package = module if parent == "." else f"{module}/{parent}"
                if package not in packages:
                    packages[package] = {"module": module, "imports": set()}
                packages[package]["imports"].update(source["imports"])
        require(
            packages.get(root_module, {}).get("module") == root_module,
            "E_GRAPH_SEMANTICS",
            "graph",
        )
        nodes, edges = package_graph_fixed_point(
            profile["profileId"],
            root_module,
            packages,
            candidate_modules,
            selected,
        )
        all_nodes.extend(nodes)
        all_edges.extend(edges)
    all_nodes.sort(
        key=lambda row: (row["profileId"], row["module"], row["package"])
    )
    all_edges.sort(
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
        )
    )
    return all_nodes, all_edges


def exact_frontier(
    module_nodes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
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


def exact_frontier_monotone(
    module_nodes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    frontier: list[dict[str, Any]] = []
    for node in module_nodes:
        if not node["frontier"]:
            continue
        frontier.append(
            {
                "module": node["module"],
                "version": node["version"],
                "selectedByGraphAlgorithm": node["selectedForModule"],
                "requiresSeparateWaveDecision": True,
                "acquisitionAuthorized": False,
            }
        )
    frontier.sort(key=lambda row: (row["module"], row["version"]))
    return frontier


def package_closure_gaps(
    edges: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unmapped = [
        {
            "profileId": row["profileId"],
            "fromPackage": row["fromPackage"],
            "importPath": row["importPath"],
        }
        for row in edges
        if row["edgeClass"] == "unmapped_external"
    ]
    declared = [
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
    unmapped.sort(
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
        )
    )
    declared.sort(
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
            row["targetModule"],
            row["targetVersion"],
        )
    )
    return unmapped, declared


def package_closure_gaps_monotone(
    edges: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unmapped: list[dict[str, Any]] = []
    declared: list[dict[str, Any]] = []
    for edge in edges:
        common = {
            "profileId": edge["profileId"],
            "fromPackage": edge["fromPackage"],
            "importPath": edge["importPath"],
        }
        if edge["edgeClass"] == "unmapped_external":
            unmapped.append(common)
        elif edge["edgeClass"] == "declared_external":
            declared.append(
                {
                    **common,
                    "targetModule": edge["targetModule"],
                    "targetVersion": edge["targetVersion"],
                }
            )
    unmapped = sorted(
        unmapped,
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
        ),
    )
    declared = sorted(
        declared,
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
            row["targetModule"],
            row["targetVersion"],
        ),
    )
    return unmapped, declared


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


def graph_reconstruction_projection(
    graph: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    require(type(graph) is dict, "E_GRAPH_SEMANTICS", "graph")
    projection: dict[str, list[dict[str, Any]]] = {}
    for field in GRAPH_RECONSTRUCTION_FIELDS:
        rows = graph.get(field)
        require(
            type(rows) is list and all(type(row) is dict for row in rows),
            "E_GRAPH_SEMANTICS",
            "graph",
        )
        projection[field] = [dict(row) for row in rows]
    selected = projection["selectedVersions"]
    require(
        all(
            type(row.get("module")) is str
            and type(row.get("version")) is str
            and valid_version(row["version"])
            for row in selected
        ),
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    require(
        selected
        == sorted(
            selected,
            key=lambda row: (row["module"], row["version"]),
        )
        and len(
            {
                (row["module"], row["version"])
                for row in selected
            }
        )
        == len(selected),
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    return projection


def build_graph(
    archives: Sequence[Mapping[str, Any]],
    metadata: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    limits: Mapping[str, Any],
) -> dict[str, Any]:
    maximum_nodes = exact_int(
        limits.get("maximumGraphNodes", DEFAULT_MAXIMUM_GRAPH_NODES),
        minimum=1,
    )
    maximum_edges = exact_int(
        limits.get("maximumGraphEdges", DEFAULT_MAXIMUM_GRAPH_EDGES),
        minimum=1,
    )
    root_modules = [
        row["module"] for row in archives if row.get("kind") == "root_zip"
    ]
    require(len(root_modules) == 1, "E_GRAPH_SEMANTICS", "graph")
    root_module = root_modules[0]
    root_metadata = [
        row for row in metadata if row.get("module") == root_module
    ]
    require(
        len(root_metadata) == 1
        and root_metadata[0]["metadata"].get("replaces") in (None, [])
        and root_metadata[0]["metadata"].get("excludes") in (None, []),
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    archive_pairs = {
        (row["module"], row["version"])
        for row in archives
        if type(row.get("module")) is str and type(row.get("version")) is str
    }
    versions, module_nodes, module_edges = module_graph(
        root_module,
        metadata,
        archive_pairs,
        maximum_nodes,
        maximum_edges,
    )
    fixed_versions, fixed_module_nodes, fixed_module_edges = (
        module_graph_monotone(
            root_module,
            metadata,
            archive_pairs,
            maximum_nodes,
            maximum_edges,
        )
    )
    nodes, edges = profile_package_reconstruction_bfs(
        archives,
        profiles,
        root_module,
        versions,
        module_nodes,
    )
    fixed_nodes, fixed_edges = profile_package_reconstruction_monotone(
        archives,
        profiles,
        root_module,
        fixed_versions,
        fixed_module_nodes,
    )
    new_tuples = exact_frontier(module_nodes)
    fixed_new_tuples = exact_frontier_monotone(fixed_module_nodes)
    unmapped_imports, declared_imports = package_closure_gaps(edges)
    (
        fixed_unmapped_imports,
        fixed_declared_imports,
    ) = package_closure_gaps_monotone(fixed_edges)
    selected_version_rows = [
        {"module": module, "version": version}
        for module, version in sorted(versions.items())
    ]
    fixed_selected_version_rows = [
        {"module": module, "version": version}
        for module, version in sorted(fixed_versions.items())
    ]
    bfs_reconstruction = graph_reconstruction_projection({
        "selectedVersions": selected_version_rows,
        "nodes": nodes,
        "edges": edges,
        "moduleNodes": module_nodes,
        "moduleEdges": module_edges,
        "exactFrontier": new_tuples,
        "unmappedExternalImports": unmapped_imports,
        "unresolvedDeclaredExternalImports": declared_imports,
    })
    fixed_reconstruction = graph_reconstruction_projection({
        "selectedVersions": fixed_selected_version_rows,
        "nodes": fixed_nodes,
        "edges": fixed_edges,
        "moduleNodes": fixed_module_nodes,
        "moduleEdges": fixed_module_edges,
        "exactFrontier": fixed_new_tuples,
        "unmappedExternalImports": fixed_unmapped_imports,
        "unresolvedDeclaredExternalImports": fixed_declared_imports,
    })
    bfs_raw = canonical_json_bytes(bfs_reconstruction)
    fixed_raw = canonical_json_bytes(fixed_reconstruction)
    require(bfs_raw == fixed_raw, "E_GRAPH_SEMANTICS", "graph")
    require(
        len(nodes) <= maximum_nodes
        and len(edges) <= maximum_edges
        and len(module_nodes) <= maximum_nodes
        and len(module_edges) <= maximum_edges,
        "E_GRAPH_BOUND",
        "graph",
    )
    node_digest = sha256_bytes(canonical_json_bytes(nodes))
    edge_digest = sha256_bytes(canonical_json_bytes(edges))
    module_node_digest = sha256_bytes(canonical_json_bytes(module_nodes))
    module_edge_digest = sha256_bytes(canonical_json_bytes(module_edges))
    module_graph_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "selectedVersions": bfs_reconstruction["selectedVersions"],
                "moduleNodes": module_nodes,
                "moduleEdges": module_edges,
                "exactFrontier": new_tuples,
            }
        )
    )
    fixed_module_graph_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "selectedVersions": fixed_reconstruction["selectedVersions"],
                "moduleNodes": fixed_module_nodes,
                "moduleEdges": fixed_module_edges,
                "exactFrontier": fixed_new_tuples,
            }
        )
    )
    require(
        module_graph_digest == fixed_module_graph_digest,
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    reconstruction_digest = sha256_bytes(bfs_raw)
    return {
        "algorithm": GRAPH_ALGORITHM,
        "versionSpecificVertexTraversal": True,
        "nodes": nodes,
        "edges": edges,
        "moduleNodes": module_nodes,
        "moduleEdges": module_edges,
        "selectedVersions": selected_version_rows,
        "exactFrontier": new_tuples,
        "newlyReachableTuples": new_tuples,
        "unmappedExternalImports": unmapped_imports,
        "unresolvedDeclaredExternalImports": declared_imports,
        "nodeSetSha256": node_digest,
        "edgeSetSha256": edge_digest,
        "moduleNodeSetSha256": module_node_digest,
        "moduleEdgeSetSha256": module_edge_digest,
        "moduleGraphAndFrontierSha256": module_graph_digest,
        "reconstructionProjectionSha256": reconstruction_digest,
        "unmappedExternalImportSetSha256": sha256_bytes(
            canonical_json_bytes(unmapped_imports)
        ),
        "unresolvedDeclaredExternalImportSetSha256": sha256_bytes(
            canonical_json_bytes(declared_imports)
        ),
        "graphSha256": reconstruction_digest,
        "graphNodeCount": len(nodes),
        "graphEdgeCount": len(edges),
        "moduleNodeCount": len(module_nodes),
        "moduleEdgeCount": len(module_edges),
        "newTupleCount": len(new_tuples),
        "unmappedExternalImportCount": len(unmapped_imports),
        "unresolvedDeclaredExternalImportCount": len(declared_imports),
        "fixedPointReached": (
            not new_tuples
            and not unmapped_imports
            and not declared_imports
        ),
        "independentReproductionPassed": True,
        "reconstructionCount": 2,
        "reconstructions": [
            {
                "algorithm": "version_vertex_breadth_first_search",
                "nodeSetSha256": node_digest,
                "edgeSetSha256": edge_digest,
                "moduleGraphAndFrontierSha256": module_graph_digest,
                "reconstructionSha256": reconstruction_digest,
            },
            {
                "algorithm": "version_vertex_monotone_full_set_scan",
                "nodeSetSha256": sha256_bytes(canonical_json_bytes(fixed_nodes)),
                "edgeSetSha256": sha256_bytes(canonical_json_bytes(fixed_edges)),
                "moduleGraphAndFrontierSha256": fixed_module_graph_digest,
                "reconstructionSha256": sha256_bytes(fixed_raw),
            },
        ],
    }


def graph_result_routing(graph: Mapping[str, Any]) -> tuple[str, str]:
    require(
        graph.get("independentReproductionPassed") is True
        and graph.get("reconstructionCount") == 2,
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    new_tuple_count = exact_int(graph.get("newTupleCount"), minimum=0)
    if new_tuple_count > 0:
        return (
            "wave1_graph_discovery_complete_new_wave_required",
            WAVE2_POST_READBACK_ACTION,
        )
    unmapped_count = exact_int(
        graph.get("unmappedExternalImportCount"),
        minimum=0,
    )
    declared_count = exact_int(
        graph.get("unresolvedDeclaredExternalImportCount"),
        minimum=0,
    )
    if unmapped_count > 0 or declared_count > 0:
        return (
            (
                "wave1_graph_discovery_complete_external_import_"
                "resolution_required"
            ),
            EXTERNAL_RESOLUTION_POST_READBACK_ACTION,
        )
    require(
        graph.get("fixedPointReached") is True,
        "E_GRAPH_SEMANTICS",
        "graph",
    )
    return (
        (
            "wave1_graph_discovery_complete_fixed_point_candidate_"
            "pending_independent_readback"
        ),
        FIXED_POINT_POST_READBACK_ACTION,
    )


def review_held_inputs(
    permit: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    held: HeldInputSet,
) -> dict[str, Any]:
    limits = permit.get("resourceLimits")
    if type(limits) is not dict:
        limits = {
            "maximumArchiveBytes": DEFAULT_MAXIMUM_ARCHIVE_BYTES,
            "maximumSingleFileBytes": DEFAULT_MAXIMUM_ENTRY_BYTES,
            "maximumEntriesPerArchive": DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE,
            "maximumAggregateEntries": DEFAULT_MAXIMUM_AGGREGATE_ENTRIES,
            "maximumAggregateUncompressedBytes": (
                DEFAULT_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
            ),
            "maximumGraphNodes": DEFAULT_MAXIMUM_GRAPH_NODES,
            "maximumGraphEdges": DEFAULT_MAXIMUM_GRAPH_EDGES,
            "maximumResultOrFailureBytes": MAXIMUM_JSON_BYTES,
        }
    metadata_rows: list[dict[str, Any]] = []
    archive_rows: list[dict[str, Any]] = []
    binding_by_tuple: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    aggregate_entries = 0
    aggregate_uncompressed = 0
    for binding in bindings:
        kind = binding["kind"]
        if kind in {"mod", "zip"}:
            tuple_id = binding.get("tupleId")
            require(type(tuple_id) is str, "E_INPUT_INVENTORY", "held_set")
            binding_by_tuple[tuple_id][kind] = binding
        if kind == "mod":
            metadata = parse_go_mod(
                held.raw[binding["path"]],
                binding.get("module"),
            )
            metadata_rows.append(
                {
                    "tupleId": binding.get("tupleId"),
                    "tupleOrder": binding.get("tupleOrder"),
                    "module": binding.get("module"),
                    "version": binding.get("version"),
                    "metadata": metadata,
                    "externalModRawSha256": binding.get("rawSha256"),
                }
            )
        elif kind in {"zip", "root_zip"}:
            archive = inspect_zip_bytes(held.raw[binding["path"]], binding, limits)
            archive["kind"] = kind
            archive_rows.append(archive)
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
    require(
        aggregate_entries
        <= exact_int(
            limits.get("maximumAggregateEntries", DEFAULT_MAXIMUM_AGGREGATE_ENTRIES),
            minimum=1,
        )
        and aggregate_uncompressed
        <= exact_int(
            limits.get(
                "maximumAggregateUncompressedBytes",
                DEFAULT_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
            ),
            minimum=1,
        ),
        "E_ARCHIVE_BOUND",
        "archive",
    )
    root_archives = [row for row in archive_rows if row["kind"] == "root_zip"]
    require(len(root_archives) == 1, "E_INPUT_INVENTORY", "held_set")
    root_embedded = root_archives[0].pop("embeddedGoMod")
    require(root_embedded is not None, "E_MODULE_METADATA", "module_metadata")
    root_metadata = parse_go_mod(root_embedded, root_archives[0]["module"])
    metadata_rows.append(
        {
            "tupleId": "root",
            "tupleOrder": 0,
            "module": root_archives[0]["module"],
            "version": root_archives[0]["version"],
            "metadata": root_metadata,
            "externalModRawSha256": None,
        }
    )
    for tuple_id, pair in binding_by_tuple.items():
        require(
            set(pair) == {"mod", "zip"},
            "E_INPUT_INVENTORY",
            "held_set",
            tuple_id=tuple_id,
        )
        archive = next(row for row in archive_rows if row["tupleId"] == tuple_id)
        embedded = archive.pop("embeddedGoMod")
        if embedded is not None:
            require(
                embedded == held.raw[pair["mod"]["path"]],
                "E_MODULE_IDENTITY",
                "module_metadata",
                tuple_id=tuple_id,
            )
    profiles = profile_rows(permit)
    graph = build_graph(archive_rows, metadata_rows, profiles, limits)
    licenses = sorted(
        [
            {
                "module": archive["module"],
                "relativePath": row["relativePath"],
                "rawByteSize": row["rawByteSize"],
                "rawSha256": row["rawSha256"],
            }
            for archive in archive_rows
            for row in archive["licenses"]
        ],
        key=lambda row: (row["module"], row["relativePath"]),
    )
    special = sorted(
        [
            {
                "module": archive["module"],
                "relativePath": row["relativePath"],
                "rawByteSize": row["rawByteSize"],
                "rawSha256": row["rawSha256"],
                "classes": row["classes"],
            }
            for archive in archive_rows
            for row in archive["special"]
        ],
        key=lambda row: (row["module"], row["relativePath"]),
    )
    module_summary = [
        {
            "tupleId": row["tupleId"],
            "tupleOrder": row["tupleOrder"],
            "module": row["module"],
            "version": row["version"],
            "metadata": row["metadata"],
            "externalModRawSha256": row["externalModRawSha256"],
        }
        for row in sorted(metadata_rows, key=lambda value: value["tupleOrder"])
    ]
    coverage_rows = [
        {
            "module": row["module"],
            "version": row["version"],
            "kind": row["kind"],
            "entryCount": row["entryCount"],
            "uncompressedByteCount": row["uncompressedByteCount"],
            "entrySetSha256": row["entrySetSha256"],
            "goSourceFileCount": len(row["sources"]),
            "licenseCandidateCount": len(row["licenses"]),
            "specialSourceCount": len(row["special"]),
        }
        for row in sorted(
            archive_rows,
            key=lambda value: (
                0 if value["kind"] == "root_zip" else 1,
                value.get("tupleOrder") or 0,
            ),
        )
    ]
    status, post_readback_next_action = graph_result_routing(graph)
    result_text = (
        "exact_wave1_module_metadata_source_surface_and_new_tuple_"
        "candidates_recorded"
    )
    result = {
        "documentType": (
            "aetherlink.g2-pion-dependency-source-review-wave1-result"
        ),
        "schemaVersion": "1.0",
        "reviewId": REVIEW_ID,
        "status": status,
        "result": result_text,
        "decisionBinding": dict(permit["decisionBinding"]),
        "permitBinding": {
            "permitId": permit["permitId"],
            "contentSha256": permit["contentBinding"]["sha256"],
        },
        "inputSet": {
            "heldInputCount": len(bindings),
            "resourceCount": sum(
                binding["kind"] in {"mod", "zip"} for binding in bindings
            ),
            "archiveCount": len(archive_rows),
            "modCount": sum(binding["kind"] == "mod" for binding in bindings),
            "inputSetSha256": sha256_bytes(
                canonical_json_bytes(
                    [
                        {
                            "path": binding["path"],
                            "rawSha256": binding["rawSha256"],
                            "kind": binding["kind"],
                        }
                        for binding in bindings
                    ]
                )
            ),
        },
        "coverage": {
            "modules": coverage_rows,
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedBytes": aggregate_uncompressed,
            "omittedArchiveCount": 0,
            "filesystemExtractionCount": 0,
        },
        "moduleMetadata": {"modules": module_summary},
        "sourceSurface": {
            "profiles": profiles,
            "sourceFileCount": sum(len(row["sources"]) for row in archive_rows),
            "sourceSurfaceSha256": sha256_bytes(
                canonical_json_bytes(
                    [
                        {
                            "module": archive["module"],
                            "sources": archive["sources"],
                        }
                        for archive in archive_rows
                    ]
                )
            ),
        },
        "graphDiscovery": graph,
        "licenseInventory": {
            "entries": licenses,
            "licenseCandidateCount": len(licenses),
            "compatibilityReviewed": False,
        },
        "specialSourceInventory": {
            "entries": special,
            "specialSourceCount": len(special),
            "executed": False,
        },
        "operationCounters": {
            "archiveOpenCount": len(archive_rows),
            "archiveExtractionCount": 0,
            "sourceExecutionCount": 0,
            "subprocessCount": 0,
            "networkOperationCount": 0,
            "fileWriteCount": 3,
        },
        "closure": {
            "openFindingCount": 19,
            "findingsClosedByReview": 0,
            "dependencySourceReviewed": False,
            "graphFixedPointReached": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "personalProjectBoundary": {
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationEvaluatedByThisReview": False,
            "productEndpointAuthenticationUserInputRequiredForThisReview": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            "productEndpointAuthenticationRemainsSeparateRuntimeInvariant": True,
        },
        "nextAction": INDEPENDENT_READBACK_NEXT_ACTION,
        "postReadbackNextAction": post_readback_next_action,
    }
    return content_bound(result, "result_without_contentBinding")


class HeldOutputDirectory:
    def __init__(self, root: Path, relative: str) -> None:
        self.root = root
        self.relative = safe_relative_path(relative)
        self.root_fd = -1
        self.directory_fds: list[
            tuple[int, os.stat_result, int, str]
        ] = []
        try:
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self.root_initial = os.fstat(self.root_fd)
            self._validate_directory(self.root_initial)
            current = self.root_fd
            for component in self.relative.split("/"):
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
                self._validate_directory(info)
                self.directory_fds.append(
                    (child, info, current, component)
                )
                current = child
            self.fd = current
            self.barrier()
        except BaseException as error:
            self.close()
            if isinstance(error, ReviewFailure):
                raise
            raise ReviewFailure(
                "E_PUBLICATION",
                "publication",
            ) from error

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_PUBLICATION",
            "publication",
        )

    def barrier(
        self,
        code: str = "E_PUBLICATION",
        phase: str = "publication",
    ) -> None:
        try:
            current_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root, follow_symlinks=False)
            require(
                directory_identity(current_root)
                == directory_identity(self.root_initial)
                and directory_identity(named_root)
                == directory_identity(self.root_initial),
                code,
                phase,
            )
            for child_fd, initial, parent_fd, component in self.directory_fds:
                current = os.fstat(child_fd)
                named = os.stat(
                    component,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                require(
                    directory_identity(current) == directory_identity(initial)
                    and directory_identity(named)
                    == directory_identity(initial),
                    code,
                    phase,
                )
        except OSError as error:
            raise ReviewFailure(code, phase) from error

    def close(self) -> None:
        for child_fd, _, _, _ in reversed(self.directory_fds):
            os.close(child_fd)
        self.directory_fds.clear()
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1
        self.fd = -1

    def __enter__(self) -> "HeldOutputDirectory":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class PublishedFile:
    def __init__(
        self,
        fd: int,
        write_fd: int,
        parent: HeldOutputDirectory,
        name: str,
        raw_sha256: str,
        byte_size: int,
        identity_value: tuple[int, ...],
    ) -> None:
        self.fd = fd
        self.write_fd = write_fd
        self.parent = parent
        self.name = name
        self.raw_sha256 = raw_sha256
        self.byte_size = byte_size
        self.identity_value = identity_value

    def barrier(self) -> None:
        try:
            self.parent.barrier(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
            )
            current = os.fstat(self.fd)
            named = os.stat(
                self.name,
                dir_fd=self.parent.fd,
                follow_symlinks=False,
            )
            require(
                identity(current) == self.identity_value
                and identity(named) == self.identity_value,
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
            )
            self.parent.barrier(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
            )
        except OSError as error:
            raise ReviewFailure(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
            ) from error

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        if self.write_fd >= 0:
            os.close(self.write_fd)
            self.write_fd = -1


def write_exclusive(
    parent: HeldOutputDirectory,
    name: str,
    payload: bytes,
) -> PublishedFile:
    require(
        type(name) is str
        and name
        and "/" not in name
        and name not in {".", ".."},
        "E_PUBLICATION",
        "publication",
    )
    write_fd = -1
    read_fd = -1
    try:
        parent.barrier()
        normalized = unicodedata.normalize("NFC", name).casefold()
        require(
            all(
                unicodedata.normalize("NFC", existing).casefold() != normalized
                for existing in os.listdir(parent.fd)
            ),
            "E_OUTPUT_COLLISION",
            "publication",
        )
        write_fd = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o600,
            dir_fd=parent.fd,
        )
        os.fchmod(write_fd, 0o600)
        offset = 0
        while offset < len(payload):
            written = os.write(write_fd, payload[offset:])
            require(written > 0, "E_PUBLICATION", "publication")
            offset += written
        os.fsync(write_fd)
        written_info = os.fstat(write_fd)
        read_fd = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent.fd,
        )
        readback = bytearray()
        while len(readback) < len(payload):
            chunk = os.read(
                read_fd,
                min(65_536, len(payload) - len(readback)),
            )
            require(bool(chunk), "E_PUBLICATION", "publication")
            readback.extend(chunk)
        require(
            os.read(read_fd, 1) == b"" and bytes(readback) == payload,
            "E_PUBLICATION",
            "publication",
        )
        info = os.fstat(read_fd)
        named = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == len(payload)
            and identity(info) == identity(written_info)
            and identity(info) == identity(named),
            "E_PUBLICATION",
            "publication",
        )
        os.fsync(parent.fd)
        parent.barrier()
        published = PublishedFile(
            read_fd,
            write_fd,
            parent,
            name,
            sha256_bytes(bytes(readback)),
            len(readback),
            identity(info),
        )
        read_fd = -1
        write_fd = -1
        return published
    except FileExistsError as error:
        raise ReviewFailure("E_OUTPUT_COLLISION", "publication") from error
    except OSError as error:
        raise ReviewFailure("E_PUBLICATION", "publication") from error
    finally:
        if read_fd >= 0:
            os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)


def claim_document(permit: Mapping[str, Any]) -> dict[str, Any]:
    return content_bound(
        {
            "documentType": (
                "aetherlink.g2-pion-dependency-source-review-wave1-one-use-claim"
            ),
            "schemaVersion": "1.0",
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "reviewId": REVIEW_ID,
            "automaticRetryAllowed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationEvaluatedByThisReview": False,
            "productEndpointAuthenticationUserInputRequiredForThisReview": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            "productEndpointAuthenticationRemainsSeparateRuntimeInvariant": True,
        },
        "claim_without_contentBinding",
    )


def manifest_document(
    permit: Mapping[str, Any],
    result_raw: bytes,
) -> dict[str, Any]:
    result = strict_json(result_raw, "review result")
    return content_bound(
        {
            "documentType": (
                "aetherlink.g2-pion-dependency-source-review-wave1-manifest"
            ),
            "schemaVersion": "1.0",
            "reviewId": REVIEW_ID,
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "resultPath": RESULT_PATH,
            "resultRawSha256": sha256_bytes(result_raw),
            "resultContentSha256": result["contentBinding"]["sha256"],
            "graphSha256": result["graphDiscovery"]["graphSha256"],
            "resultStatus": result["status"],
            "manifestWrittenLast": True,
            "independentReadbackPassed": False,
            "networkOperationCount": 0,
            "sourceExecutionCount": 0,
            "productEndpointAuthenticationEvaluatedByThisReview": False,
            "productEndpointAuthenticationUserInputRequiredForThisReview": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            "nextAction": INDEPENDENT_READBACK_NEXT_ACTION,
        },
        "manifest_without_contentBinding",
    )


def durable_failure_document(
    permit: Mapping[str, Any],
    failure: ReviewFailure,
    claim_raw_sha256: str,
) -> dict[str, Any]:
    return content_bound(
        {
            "documentType": (
                "aetherlink.g2-pion-dependency-source-review-wave1-failure"
            ),
            "schemaVersion": "1.0",
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "reviewId": REVIEW_ID,
            "status": "dependency_source_review_wave1_failed_closed",
            "failureCode": failure.code,
            "phase": failure.phase,
            "failedTupleId": failure.tuple_id,
            "failedTupleOrder": failure.tuple_order,
            "failedResourceKind": failure.resource_kind,
            "safeNumericObservations": failure.observations,
            "claimRawSha256": claim_raw_sha256,
            "partialResultPublished": False,
            "automaticRetryAllowed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationEvaluatedByThisReview": False,
            "productEndpointAuthenticationUserInputRequiredForThisReview": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            "nextAction": (
                "prepare_new_versioned_dependency_source_review_wave1_"
                "recovery_decision"
            ),
        },
        "failure_without_contentBinding",
    )


def preflight_with_authority(
    root: Path,
    permit: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_permit(permit, root)
    with HeldInputSet(root, bindings) as held:
        held.final_barrier()
        classification, kinds = classify_one_use_state(root, permit)
        status = {
            "clean": "passed",
            "success": "consumed_success_pending_independent_readback",
            "failure": "consumed_failed_recovery_required",
            "blocked": "failed_closed",
        }[classification]
        return {
            "documentType": (
                "aetherlink.g2-pion-dependency-source-review-wave1-preflight"
            ),
            "schemaVersion": "1.0",
            "status": status,
            "validationPassed": classification in {"clean", "success"},
            "permitId": permit["permitId"],
            "permitConsumptionState": {
                "clean": "authorized_not_consumed",
                "success": "consumed_success",
                "failure": "consumed_failure",
                "blocked": "consumed_terminal_state_uncertain",
            }[classification],
            "oneUseState": kinds,
            "heldInputCount": len(bindings),
            "archiveInspectionCount": 0,
            "archiveExtractionCount": 0,
            "sourceExecutionCount": 0,
            "subprocessCount": 0,
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationEvaluatedByThisReview": False,
            "productEndpointAuthenticationUserInputRequiredForThisReview": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            "nextAction": (
                EXPECTED_PERMIT_NEXT_ACTION
                if classification == "clean"
                else (
                    INDEPENDENT_READBACK_NEXT_ACTION
                    if classification == "success"
                    else "prepare_new_versioned_dependency_source_review_wave1_recovery_decision"
                )
            ),
        }


def execute_with_authority(
    root: Path,
    permit: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_permit(permit, root)
    claim_parent, claim_name = CLAIM_PATH.rsplit("/", 1)
    result_parent, result_name = RESULT_PATH.rsplit("/", 1)
    failure_parent, failure_name = FAILURE_PATH.rsplit("/", 1)
    manifest_parent, manifest_name = MANIFEST_PATH.rsplit("/", 1)
    require(
        result_parent == failure_parent == manifest_parent,
        "E_PUBLICATION",
        "publication",
    )
    claim_written = False
    result_written = False
    claim_raw = b""
    claim_file: PublishedFile | None = None
    result_file: PublishedFile | None = None
    manifest_file: PublishedFile | None = None
    failure_file: PublishedFile | None = None
    with (
        HeldOutputDirectory(root, claim_parent) as claim_output,
        HeldOutputDirectory(root, result_parent) as document_output,
        HeldInputSet(root, bindings) as held,
    ):
        claim_output.barrier()
        document_output.barrier()
        classification, _ = classify_one_use_state(root, permit)
        require(
            classification == "clean",
            "E_ONE_USE_STATE_PRESENT",
            "preflight",
        )
        claim_output.barrier()
        document_output.barrier()
        held.final_barrier()
        claim_raw = canonical_json_bytes(claim_document(permit))
        try:
            claim_file = write_exclusive(
                claim_output,
                claim_name,
                claim_raw,
            )
            claim_written = True
            held.final_barrier()
            result = review_held_inputs(permit, bindings, held)
            result_raw = canonical_json_bytes(result)
            result_contract = permit.get("resultContract")
            configured_maximum = (
                result_contract.get("maximumBytes")
                if type(result_contract) is dict
                else None
            )
            if configured_maximum is None:
                limits = permit.get("resourceLimits")
                configured_maximum = (
                    limits.get("maximumResultOrFailureBytes")
                    if type(limits) is dict
                    else MAXIMUM_JSON_BYTES
                )
            maximum_result = exact_int(configured_maximum, minimum=1)
            require(
                len(result_raw) <= maximum_result,
                "E_GRAPH_BOUND",
                "publication",
                observations={"resultBytes": len(result_raw)},
            )
            held.final_barrier()
            result_file = write_exclusive(
                document_output,
                result_name,
                result_raw,
            )
            result_written = True
            manifest_raw = canonical_json_bytes(
                manifest_document(permit, result_raw)
            )
            require(
                len(manifest_raw) <= maximum_result,
                "E_GRAPH_BOUND",
                "publication",
                observations={"manifestBytes": len(manifest_raw)},
            )
            manifest_file = write_exclusive(
                document_output,
                manifest_name,
                manifest_raw,
            )
            held.final_barrier()
            claim_output.barrier(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
            )
            document_output.barrier(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
            )
            claim_file.barrier()
            result_file.barrier()
            manifest_file.barrier()
        except ReviewFailure as failure:
            if claim_written and not result_written:
                try:
                    failure_raw = canonical_json_bytes(
                        durable_failure_document(
                            permit,
                            failure,
                            sha256_bytes(claim_raw),
                        )
                    )
                    failure_file = write_exclusive(
                        document_output,
                        failure_name,
                        failure_raw,
                    )
                    held.final_barrier()
                    claim_output.barrier(
                        "E_POST_PUBLISH_UNCERTAIN",
                        "post_publish",
                    )
                    document_output.barrier(
                        "E_POST_PUBLISH_UNCERTAIN",
                        "post_publish",
                    )
                    claim_file.barrier()
                    failure_file.barrier()
                except ReviewFailure as nested:
                    raise ReviewFailure(
                        "E_POST_PUBLISH_UNCERTAIN",
                        "post_publish",
                    ) from nested
            elif claim_written:
                raise ReviewFailure(
                    "E_POST_PUBLISH_UNCERTAIN",
                    "post_publish",
                ) from failure
            raise
        finally:
            for published in (
                manifest_file,
                result_file,
                failure_file,
                claim_file,
            ):
                if published is not None:
                    published.close()
    require(
        result_file is not None and manifest_file is not None,
        "E_POST_PUBLISH_UNCERTAIN",
        "post_publish",
    )
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-source-review-wave1-runner-result"
        ),
        "schemaVersion": "1.0",
        "status": "review_publication_complete_pending_independent_readback",
        "validationPassed": True,
        "permitId": permit["permitId"],
        "reviewId": REVIEW_ID,
        "claimRawSha256": sha256_bytes(claim_raw),
        "resultRawSha256": result_file.raw_sha256,
        "manifestRawSha256": manifest_file.raw_sha256,
        "fileWriteCount": 3,
        "networkOperationCount": 0,
        "sourceExecutionCount": 0,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "productEndpointAuthenticationEvaluatedByThisReview": False,
        "productEndpointAuthenticationUserInputRequiredForThisReview": False,
        "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
        "productEndpointAuthenticationRemainsSeparateRuntimeInvariant": True,
        "nextAction": INDEPENDENT_READBACK_NEXT_ACTION,
    }


def runner_error_document(failure: ReviewFailure) -> dict[str, Any]:
    uncertain = failure.code == "E_POST_PUBLISH_UNCERTAIN"
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-source-review-wave1-runner-error"
        ),
        "schemaVersion": "1.0",
        "status": (
            "consumed_terminal_state_uncertain"
            if uncertain
            else "failed_preclaim_or_state_requires_inspection"
        ),
        "failureCode": failure.code,
        "phase": failure.phase,
        "failedTupleId": failure.tuple_id,
        "failedTupleOrder": failure.tuple_order,
        "failedResourceKind": failure.resource_kind,
        "safeNumericObservations": failure.observations,
        "automaticRetryAllowed": False,
        "networkOperationCount": 0,
        "sourceExecutionCount": 0,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "productEndpointAuthenticationEvaluatedByThisReview": False,
        "productEndpointAuthenticationUserInputRequiredForThisReview": False,
        "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
        "productEndpointAuthenticationRemainsSeparateRuntimeInvariant": True,
        "nextAction": (
            "inspect_dependency_source_review_wave1_terminal_state_without_retry"
            if uncertain
            else "inspect_dependency_source_review_wave1_state_without_automatic_retry"
        ),
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        permit, bindings = load_validated_authority(ROOT)
        result = (
            execute_with_authority(ROOT, permit, bindings)
            if args.execute
            else preflight_with_authority(ROOT, permit, bindings)
        )
    except ReviewFailure as failure:
        print(canonical_json_bytes(runner_error_document(failure)).decode(), end="")
        return 1
    except Exception:
        failure = ReviewFailure("E_INTERNAL", "runner")
        print(canonical_json_bytes(runner_error_document(failure)).decode(), end="")
        return 1
    print(canonical_json_bytes(result).decode(), end="")
    return 0 if result.get("validationPassed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
