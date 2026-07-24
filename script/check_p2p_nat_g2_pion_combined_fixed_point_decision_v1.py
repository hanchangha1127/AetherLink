#!/usr/bin/env python3
"""Validate the preparation-only combined fixed-point decision.

Run with ``python3 -I -B -S``.  This checker is read-only: it validates the
canonical decision and reader, the exact predecessor/tool bytes, and all 69
retained source inputs.  It neither recomputes nor publishes a fixed-point
result and grants no execution authority.
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
            "combined fixed-point decision checker requires "
            "unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import types
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-decision-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-decision-v1.md"
)
CANDIDATE_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
)
CANDIDATE_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_v1.py"
)
CANDIDATE_CHECKER_SHA256 = (
    "b11047fd74e8ba4b41d66590975270921a5835bf444ad2e942af357d56764f15"
)
CANDIDATE_TESTS_SHA256 = (
    "ab072a1ea2101f7a24a0d8ea1d6093391ca5ffffe87090f272acacce02340304"
)
WAVE1_RUNNER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
WAVE1_RUNNER_SHA256 = (
    "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
)
CANDIDATE_SOURCE_PROJECTION_SHA256 = (
    "c744597d53e9bf50611f154421f661aec19f95a767dcbb9a80aa653fe83f2036"
)
DECISION_HELD_BINDING_SET_SHA256 = (
    "f2a27bb27da1ba86d454625fcfaee64d5d1dbf5e8d38fd5fc0f6bcacbabf362e"
)
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-fixed-point-preparation-decision-v1"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024

DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
FUTURE_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.combined-fixed-point-v1.claim"
FUTURE_RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-result-v1.json"
)
FUTURE_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-failure-v1.json"
)
FUTURE_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-manifest-v1.json"
)
FUTURE_READBACK_CLAIM_PATH = (
    f"{DEPENDENCY_ROOT}/.combined-fixed-point-readback-v1.claim"
)
FUTURE_READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v1.json"
)
FUTURE_READBACK_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-failure-v1.json"
)
FUTURE_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-manifest-v1.json"
)
FUTURE_STAGING_PREFIX = ".combined-fixed-point-v1-staging-"
FUTURE_PATHS = (
    FUTURE_CLAIM_PATH,
    FUTURE_RESULT_PATH,
    FUTURE_FAILURE_PATH,
    FUTURE_MANIFEST_PATH,
    FUTURE_READBACK_CLAIM_PATH,
    FUTURE_READBACK_RECEIPT_PATH,
    FUTURE_READBACK_FAILURE_PATH,
    FUTURE_READBACK_MANIFEST_PATH,
)

CANDIDATE_SOURCE_PROJECTION_FIELDS = (
    "kind",
    "module",
    "path",
    "rawSha256",
    "tupleId",
    "tupleOrder",
    "version",
    "wave",
)
DECISION_HELD_BINDING_FIELDS = (
    *CANDIDATE_SOURCE_PROJECTION_FIELDS,
    "byteSize",
    "mode",
    "linkCount",
)
CANDIDATE_SOURCE_PROJECTION_SORT = (
    "tupleOrder",
    "kind",
    "path",
)

READER_BYTES = b"""# Combined Wave1 + Wave2 fixed-point preparation decision v1

Status: **execution not authorized**.

This companion explains the canonical JSON decision. It freezes the exact
Wave1 and Wave2 predecessor chain, the 69 retained source-file identities, the
two target profiles, graph limits, fixed-point acceptance conditions, and a
future independent one-use publication namespace.

It directly binds the immutable Wave1 graph runner, the candidate checker and
tests, and the exact predecessor chain. The 69 decision rows project back to
the candidate checker's exact eight-field source projection and fixed digest;
the decision's extended held-binding digest is independently fixed. It does
not treat the verification-only checker output as durable evidence. The
current non-authoritative observation has 16 newly reachable tuples, so it
does not satisfy the fixed-point acceptance rule. No dependency source
review, semantic closure, candidate selection, library selection, rung-three
completion, release readiness, acquisition, network use, source execution,
filesystem extraction, subprocess, publication, or Git operation is
authorized.

Any future execution requires a separate exact permit. That permit must use
the reserved independent namespace, consume one claim before archive-member
inspection, prohibit retry after consumption or uncertainty, publish either a
result or failure, treat any post-publication failure as consumed terminal
uncertainty, write the manifest last, and require a separately claimed
independent readback. The readback namespace includes its own mutually
exclusive receipt or failure and a manifest written last. This decision is not
that permit.

Repository-owner authentication, external authentication, signatures, private
keys, tokens, passwords, and user action are not required by this bounded
preparation decision.
"""


class CheckError(RuntimeError):
    """A bounded checker failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CheckError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
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


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "E_JSON")
        result[key] = value
    return result


def reject_float(_: str) -> Any:
    raise CheckError("E_JSON")


def reject_constant(_: str) -> Any:
    raise CheckError("E_JSON")


def strict_json(raw: bytes) -> dict[str, Any]:
    require(len(raw) <= MAXIMUM_JSON_BYTES, "E_JSON")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=strict_object,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def safe_relative(value: Any) -> str:
    require(
        type(value) is str
        and value
        and not value.startswith("/")
        and "\\" not in value
        and "\x00" not in value,
        "E_PATH",
    )
    parts = value.split("/")
    require(
        all(part not in {"", ".", ".."} for part in parts)
        and PurePosixPath(value).as_posix() == value,
        "E_PATH",
    )
    return value


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


class HeldFile:
    def __init__(
        self,
        root_fd: int,
        relative: str,
        *,
        maximum_bytes: int,
        owner_only: bool,
        expected_sha256: str | None,
    ) -> None:
        self.relative = safe_relative(relative)
        self.maximum_bytes = maximum_bytes
        self.owner_only = owner_only
        self.expected_sha256 = expected_sha256
        self.fd = -1
        self.parent_fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
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
                self._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = self.relative.rsplit("/", 1)[-1]
            self.fd = os.open(
                self.name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=self.parent_fd,
            )
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial)
            first = self.read_pass()
            second = self.read_pass()
            require(first == second, "E_HELD_SET")
            if expected_sha256 is not None:
                require(sha256(first) == expected_sha256, "E_RAW_PIN")
            self.raw = first
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_HELD_SET",
        )

    def _validate_file(self, info: os.stat_result) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and 0 <= info.st_size <= self.maximum_bytes,
            "E_HELD_SET",
        )
        if self.owner_only:
            require(stat.S_IMODE(info.st_mode) == 0o600, "E_HELD_SET")
        else:
            require(stat.S_IMODE(info.st_mode) & 0o022 == 0, "E_HELD_SET")

    def read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_HELD_SET")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", "E_HELD_SET")
        after = os.fstat(self.fd)
        require(file_identity(before) == file_identity(after), "E_HELD_SET")
        return b"".join(chunks)

    def final_barrier(self) -> None:
        current = os.fstat(self.fd)
        named = os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
        require(
            file_identity(current) == file_identity(self.initial)
            and file_identity(named) == file_identity(self.initial),
            "E_HELD_SET",
        )
        for child, initial, parent, component in self.directories:
            current_dir = os.fstat(child)
            named_dir = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            require(
                directory_identity(current_dir) == directory_identity(initial)
                and directory_identity(named_dir) == directory_identity(initial),
                "E_HELD_SET",
            )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directories):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directories.clear()
        if self.parent_fd >= 0 and self.parent_fd not in seen:
            os.close(self.parent_fd)
        self.parent_fd = -1


class HeldSet:
    def __init__(
        self,
        root: Path,
        bindings: Sequence[Mapping[str, Any]],
    ) -> None:
        self.root_path = root.absolute()
        self.root_fd = os.open(
            self.root_path,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
        )
        self.root_initial = os.fstat(self.root_fd)
        require(
            stat.S_ISDIR(self.root_initial.st_mode)
            and self.root_initial.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(self.root_initial.st_mode) & 0o022 == 0,
            "E_HELD_SET",
        )
        self.files: dict[str, HeldFile] = {}
        self.raw: dict[str, bytes] = {}
        try:
            seen: set[str] = set()
            for binding in bindings:
                path = safe_relative(binding.get("path"))
                require(path not in seen, "E_HELD_SET")
                seen.add(path)
                held = HeldFile(
                    self.root_fd,
                    path,
                    maximum_bytes=binding["maximumBytes"],
                    owner_only=binding["ownerOnly"],
                    expected_sha256=binding.get("rawSha256"),
                )
                self.files[path] = held
                self.raw[path] = held.raw
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        try:
            named_root = os.stat(self.root_path, follow_symlinks=False)
        except OSError as error:
            raise CheckError("E_HELD_SET") from error
        require(
            directory_identity(os.fstat(self.root_fd))
            == directory_identity(self.root_initial)
            and directory_identity(named_root)
            == directory_identity(self.root_initial),
            "E_HELD_SET",
        )
        for held in self.files.values():
            held.final_barrier()

    def close(self) -> None:
        for held in self.files.values():
            held.close()
        self.files.clear()
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def __enter__(self) -> "HeldSet":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class HeldDirectory:
    """Retain one no-follow output-parent chain and every named identity."""

    def __init__(self, root_fd: int, relative: str) -> None:
        self.relative = safe_relative(relative)
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.fd = -1
        current = os.dup(root_fd)
        try:
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
                HeldFile._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.fd = current
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        try:
            for child, initial, parent, component in self.directories:
                current = os.fstat(child)
                named = os.stat(
                    component,
                    dir_fd=parent,
                    follow_symlinks=False,
                )
                require(
                    directory_identity(current) == directory_identity(initial)
                    and directory_identity(named)
                    == directory_identity(initial),
                    "E_NAMESPACE_IDENTITY",
                )
        except OSError as error:
            raise CheckError("E_NAMESPACE_IDENTITY") from error

    def close(self) -> None:
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directories):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directories.clear()
        self.fd = -1


class HeldNamespace:
    """Hold the no-follow root and both future output parent directories."""

    def __init__(self, root: Path) -> None:
        self.root_path = root.absolute()
        self.root_fd = -1
        self.root_initial: os.stat_result | None = None
        self.parents: list[HeldDirectory] = []
        try:
            self.root_fd = os.open(
                self.root_path,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self.root_initial = os.fstat(self.root_fd)
            require(
                stat.S_ISDIR(self.root_initial.st_mode)
                and self.root_initial.st_uid in {0, os.geteuid()}
                and stat.S_IMODE(self.root_initial.st_mode) & 0o022 == 0,
                "E_NAMESPACE_IDENTITY",
            )
            self.parents = [
                HeldDirectory(self.root_fd, DEPENDENCY_ROOT),
                HeldDirectory(self.root_fd, BASE),
            ]
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        require(
            self.root_fd >= 0 and self.root_initial is not None,
            "E_NAMESPACE_IDENTITY",
        )
        try:
            named_root = os.stat(self.root_path, follow_symlinks=False)
        except OSError as error:
            raise CheckError("E_NAMESPACE_IDENTITY") from error
        require(
            directory_identity(os.fstat(self.root_fd))
            == directory_identity(self.root_initial)
            and directory_identity(named_root)
            == directory_identity(self.root_initial),
            "E_NAMESPACE_IDENTITY",
        )
        for parent in self.parents:
            parent.final_barrier()

    def close(self) -> None:
        for parent in reversed(self.parents):
            parent.close()
        self.parents.clear()
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def __enter__(self) -> "HeldNamespace":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def tool_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": CANDIDATE_CHECKER_PATH,
            "rawSha256": CANDIDATE_CHECKER_SHA256,
            "maximumBytes": MAXIMUM_TOOL_BYTES,
            "ownerOnly": False,
        },
        {
            "path": CANDIDATE_TESTS_PATH,
            "rawSha256": CANDIDATE_TESTS_SHA256,
            "maximumBytes": MAXIMUM_TOOL_BYTES,
            "ownerOnly": False,
        },
        {
            "path": WAVE1_RUNNER_PATH,
            "rawSha256": WAVE1_RUNNER_SHA256,
            "maximumBytes": MAXIMUM_TOOL_BYTES,
            "ownerOnly": False,
        },
    ]


def load_candidate_checker(held: HeldSet) -> types.ModuleType:
    raw = held.raw[CANDIDATE_CHECKER_PATH]
    require(
        sha256(held.raw[WAVE1_RUNNER_PATH]) == WAVE1_RUNNER_SHA256,
        "E_RAW_PIN",
    )
    module = types.ModuleType("aetherlink_combined_fixed_point_candidate_v1")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / CANDIDATE_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_candidate_v1",
            "__package__": None,
        }
    )
    try:
        code = compile(
            raw,
            CANDIDATE_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CheckError("E_TOOL_LOAD") from error
    for name in (
        "PinnedRunnerFile",
        "load_pinned_runner",
        "control_bindings",
        "parse_control_documents",
        "validate_terminal_documents",
        "source_bindings",
        "graph_limits",
        "source_projection",
    ):
        require(callable(getattr(module, name, None)), "E_TOOL_API")
    require(
        module.RUNNER_PATH == WAVE1_RUNNER_PATH
        and module.RUNNER_SHA256 == WAVE1_RUNNER_SHA256,
        "E_TOOL_API",
    )
    return module


def source_hold_bindings(
    source_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "path": row["path"],
            "rawSha256": row["rawSha256"],
            "maximumBytes": row["maximumBytes"],
            "ownerOnly": True,
        }
        for row in source_rows
    ]


def predecessor_chain(
    candidate: types.ModuleType,
) -> list[dict[str, str]]:
    roles = {
        candidate.WAVE1_PERMIT_PATH: "wave1_review_permit",
        candidate.WAVE1_RESULT_PATH: "wave1_review_result",
        candidate.WAVE1_MANIFEST_PATH: "wave1_review_manifest",
        candidate.WAVE1_READBACK_PATH: "wave1_review_readback",
        candidate.WAVE1_READBACK_MANIFEST_PATH: (
            "wave1_review_readback_manifest"
        ),
        candidate.WAVE2_RECEIPT_PATH: "wave2_acquisition_receipt",
        candidate.WAVE2_MANIFEST_PATH: "wave2_acquisition_manifest",
        candidate.WAVE2_READBACK_PATH: "wave2_acquisition_readback",
        candidate.WAVE2_READBACK_MANIFEST_PATH: (
            "wave2_acquisition_readback_manifest"
        ),
    }
    result = [
        {
            "role": roles[path],
            "path": path,
            "rawSha256": digest,
        }
        for path, digest in candidate.CONTROL_SHA256.items()
    ]
    result.extend(
        [
            {
                "role": "combined_candidate_checker",
                "path": CANDIDATE_CHECKER_PATH,
                "rawSha256": CANDIDATE_CHECKER_SHA256,
            },
            {
                "role": "combined_candidate_checker_tests",
                "path": CANDIDATE_TESTS_PATH,
                "rawSha256": CANDIDATE_TESTS_SHA256,
            },
            {
                "role": "immutable_wave1_graph_runner",
                "path": WAVE1_RUNNER_PATH,
                "rawSha256": WAVE1_RUNNER_SHA256,
            },
        ]
    )
    return result


def decision_source_rows(
    candidate: types.ModuleType,
    source_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = candidate.source_projection(source_rows)
    result = [
        {
            **row,
            "byteSize": next(
                binding["maximumBytes"]
                for binding in source_rows
                if binding["path"] == row["path"]
            ),
            "mode": "0600",
            "linkCount": 1,
        }
        for row in rows
    ]
    require(
        all(set(row) == set(DECISION_HELD_BINDING_FIELDS) for row in result),
        "E_SOURCE_PROJECTION",
    )
    return result


def candidate_projection_from_decision_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    require(
        len(rows) == 69
        and all(set(row) == set(DECISION_HELD_BINDING_FIELDS) for row in rows),
        "E_SOURCE_PROJECTION",
    )
    projection = [
        {field: row[field] for field in CANDIDATE_SOURCE_PROJECTION_FIELDS}
        for row in rows
    ]
    require(
        projection
        == sorted(
            projection,
            key=lambda row: tuple(
                row[field] for field in CANDIDATE_SOURCE_PROJECTION_SORT
            ),
        ),
        "E_SOURCE_PROJECTION",
    )
    return projection


def expected_payload(
    candidate: types.ModuleType,
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    chain = predecessor_chain(candidate)
    sources = decision_source_rows(candidate, source_rows)
    candidate_projection = candidate_projection_from_decision_rows(sources)
    candidate_projection_sha256 = sha256(canonical_bytes(candidate_projection))
    decision_binding_set_sha256 = sha256(canonical_bytes(sources))
    require(
        candidate_projection
        == candidate.source_projection(source_rows)
        and candidate_projection_sha256
        == CANDIDATE_SOURCE_PROJECTION_SHA256
        and decision_binding_set_sha256
        == DECISION_HELD_BINDING_SET_SHA256,
        "E_SOURCE_PROJECTION",
    )
    profiles = runner.profile_rows(documents[candidate.WAVE1_PERMIT_PATH])
    limits = candidate.graph_limits(runner)
    namespaces = {
        "claimPath": FUTURE_CLAIM_PATH,
        "resultPath": FUTURE_RESULT_PATH,
        "failurePath": FUTURE_FAILURE_PATH,
        "manifestPath": FUTURE_MANIFEST_PATH,
        "readbackClaimPath": FUTURE_READBACK_CLAIM_PATH,
        "readbackReceiptPath": FUTURE_READBACK_RECEIPT_PATH,
        "readbackFailurePath": FUTURE_READBACK_FAILURE_PATH,
        "readbackManifestPath": FUTURE_READBACK_MANIFEST_PATH,
        "stagingDirectoryPrefix": FUTURE_STAGING_PREFIX,
    }
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-preparation-decision"
        ),
        "schemaVersion": "1.0",
        "decisionId": DECISION_ID,
        "status": (
            "combined_fixed_point_preparation_recorded_execution_not_authorized"
        ),
        "result": (
            "exact_inputs_acceptance_and_future_namespace_frozen_"
            "without_execution_authority"
        ),
        "scope": (
            "offline_preparation_contract_for_future_combined_dependency_"
            "fixed_point_evaluation_only"
        ),
        "recordedDate": "2026-07-24",
        "canonicalPredecessorChain": chain,
        "canonicalPredecessorChainSha256": sha256(canonical_bytes(chain)),
        "toolBindings": {
            "candidateChecker": {
                "path": CANDIDATE_CHECKER_PATH,
                "rawSha256": CANDIDATE_CHECKER_SHA256,
            },
            "candidateCheckerTests": {
                "path": CANDIDATE_TESTS_PATH,
                "rawSha256": CANDIDATE_TESTS_SHA256,
            },
            "immutableWave1GraphRunner": {
                "role": "immutable_wave1_graph_runner",
                "path": WAVE1_RUNNER_PATH,
                "rawSha256": WAVE1_RUNNER_SHA256,
            },
            "candidateCheckerMayBeLoadedOnlyAfterExactRawPin": True,
            "immutableWave1GraphRunnerHeldDirectly": True,
            "candidateCheckerOutputAcceptedAsEvidence": False,
        },
        "sourceInputSet": {
            "heldInputCount": 69,
            "rootArchiveCount": 1,
            "resourceCount": 68,
            "modCount": 34,
            "zipCount": 34,
            "wave1ResourceCount": 38,
            "wave2ResourceCount": 30,
            "bindings": sources,
            "inputSetSha256": decision_binding_set_sha256,
            "candidateSourceProjectionSha256": (
                candidate_projection_sha256
            ),
            "decisionHeldBindingSetSha256": decision_binding_set_sha256,
            "projectionContract": {
                "candidateFieldSet": list(CANDIDATE_SOURCE_PROJECTION_FIELDS),
                "decisionHeldBindingFieldSet": list(
                    DECISION_HELD_BINDING_FIELDS
                ),
                "sortKeys": list(CANDIDATE_SOURCE_PROJECTION_SORT),
                "canonicalization": (
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf"
                ),
                "decisionRowsProjectByDropping": [
                    "byteSize",
                    "mode",
                    "linkCount",
                ],
                "candidateFieldSetExact": True,
                "decisionHeldBindingFieldSetExact": True,
                "decisionRowsProjectBackToCandidateDigest": True,
            },
            "allInputsMustRemainOpenThroughFinalNamedIdentityBarrier": True,
            "filesystemExtractionAllowed": False,
            "sourceMaterializationAllowed": False,
            "sourceExecutionAllowed": False,
        },
        "profiles": profiles,
        "resourceLimits": limits,
        "candidateObservation": {
            "evidenceAccepted": False,
            "durableCandidateArtifactExists": False,
            "observationRecomputedByThisDecisionChecker": False,
            "producerRawSha256": CANDIDATE_CHECKER_SHA256,
            "observedStatus": (
                "combined_graph_discovery_complete_next_wave_required"
            ),
            "observedRoute": "next_wave_required",
            "observedGraphSha256": (
                "541fc40bcfe87640033db54948911972d"
                "ab9a6cab7e0b26d8021a89660be69d8"
            ),
            "observedNewTupleCount": 16,
            "observedUnmappedExternalImportCount": 0,
            "observedUnresolvedDeclaredExternalImportCount": 0,
            "observedFixedPointReached": False,
            "acceptanceSatisfied": False,
            "requiresFreshAuthorizedEvaluationBeforeAnyDurableClaim": True,
        },
        "fixedPointAcceptance": {
            "algorithm": "go1.24_mvs_profile_union_fixed_point_v1",
            "fullHeldInputReconstructionCountRequired": 2,
            "independentGraphAlgorithmCountRequired": 4,
            "canonicalGraphEqualityRequired": True,
            "exactFrontierCountRequired": 0,
            "unmappedExternalImportCountRequired": 0,
            "unresolvedDeclaredExternalImportCountRequired": 0,
            "fixedPointReachedRequired": True,
            "inputIdentityBarrierRequiredBeforeBetweenAndAfter": True,
            "independentReadbackRequired": True,
            "acceptanceCreatesSourceReviewClaim": False,
            "acceptanceCreatesSemanticClosureClaim": False,
            "acceptanceCreatesSelectionAuthority": False,
            "acceptanceCreatesReleaseAuthority": False,
        },
        "independentNamespace": {
            **namespaces,
            "allPathsRequiredAbsentBeforeFuturePermit": True,
            "namespaceSharedWithWave1OrWave2": False,
            "namespaceReservationIsExecutionAuthority": False,
        },
        "futureOneUseContract": {
            "futurePermitId": (
                "g2-pion-ice-v4.3.0-rung3-combined-fixed-point-"
                "execution-permit-v1"
            ),
            "futureEvaluationId": (
                "g2-pion-ice-v4.3.0-combined-fixed-point-evaluation-v1"
            ),
            "separateExactPermitRequired": True,
            "permitAuthorizedByThisDecision": False,
            "claimCreatedBeforeArchiveMemberOpenOrDecode": True,
            "secondExecutionAllowed": False,
            "automaticRetryAllowed": False,
            "postClaimFailureConsumesPermit": True,
            "postClaimUncertaintyConsumesPermit": True,
            "claimCreationUncertaintyConsumesPermit": True,
            "claimPersistsAfterAnyEvaluationAttempt": True,
            "preClaimFailureConsumesPermit": False,
            "resultOrFailureMutuallyExclusive": True,
            "failureForbiddenAfterResultPublishAttempt": True,
            "postPublishUncertainState": "consumed_terminal_state_uncertain",
            "manifestWrittenLast": True,
            "separateReadbackClaimRequired": True,
            "readbackPreClaimFailureConsumesPermit": False,
            "readbackClaimCreationUncertaintyConsumesPermit": True,
            "readbackPostClaimFailureConsumesPermit": True,
            "readbackPostClaimUncertaintyConsumesPermit": True,
            "readbackSecondExecutionAllowed": False,
            "readbackAutomaticRetryAllowed": False,
            "readbackReceiptOrFailureMutuallyExclusive": True,
            "readbackFailureForbiddenAfterReceiptPublishAttempt": True,
            "readbackPostPublishUncertainState": (
                "consumed_terminal_state_uncertain"
            ),
            "readbackReopensAll69Inputs": True,
            "readbackReexecutesGraphAlgorithms": True,
            "readbackManifestWrittenLast": True,
            "networkAllowed": False,
            "filesystemExtractionAllowed": False,
            "sourceExecutionAllowed": False,
            "subprocessAllowed": False,
            "gitWriteAllowed": False,
        },
        "authority": {
            "decisionRecorded": True,
            "executionAuthorized": False,
            "fixedPointEvaluationAuthorized": False,
            "oneUseClaimWriteAuthorized": False,
            "resultOrFailureWriteAuthorized": False,
            "manifestWriteAuthorized": False,
            "readbackAuthorized": False,
            "networkAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "sourceExecutionAuthorized": False,
            "packageManagerAuthorized": False,
            "compilerAuthorized": False,
            "subprocessAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "closure": {
            "dependencyFixedPointReached": False,
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
        "documentationBinding": {
            "path": READER_PATH,
            "rawSha256": sha256(READER_BYTES),
        },
        "nextAction": (
            "prepare_separate_combined_fixed_point_runner_checker_"
            "tests_and_one_use_execution_permit"
        ),
    }


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def validate_namespace_absent(
    root: Path,
    held_namespace: HeldNamespace | None = None,
) -> None:
    if held_namespace is not None:
        held_namespace.final_barrier()
    for relative in FUTURE_PATHS:
        path = root / safe_relative(relative)
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise CheckError("E_NAMESPACE") from error
        raise CheckError("E_NAMESPACE")
    parent = root / DEPENDENCY_ROOT
    try:
        names = os.listdir(parent)
    except OSError as error:
        raise CheckError("E_NAMESPACE") from error
    require(
        not any(name.startswith(FUTURE_STAGING_PREFIX) for name in names),
        "E_NAMESPACE",
    )
    if held_namespace is not None:
        held_namespace.final_barrier()


def decision_file_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": DECISION_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": False,
        },
        {
            "path": READER_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": False,
        },
    ]


def validate_decision_bytes(
    raw: bytes,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    actual = strict_json(raw)
    require(raw == canonical_bytes(actual), "E_CANONICAL_DECISION")
    require(actual == expected, "E_DECISION")
    binding = actual.get("contentBinding")
    require(
        type(binding) is dict
        and set(binding)
        == {
            "algorithm",
            "canonicalization",
            "scope",
            "sha256",
        }
        and binding["algorithm"] == "sha256"
        and binding["canonicalization"]
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding["scope"] == "decision_without_contentBinding"
        and binding["sha256"]
        == sha256(
            canonical_bytes(
                {
                    key: value
                    for key, value in actual.items()
                    if key != "contentBinding"
                }
            )
        ),
        "E_CONTENT_BINDING",
    )
    return actual


def validate_reader_bytes(raw: bytes) -> None:
    require(raw == READER_BYTES, "E_READER")


def evaluate(
    root: Path,
    *,
    verify_disk: bool,
    before_final_barrier: Callable[[], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with (
        HeldNamespace(root) as held_namespace,
        HeldSet(root, tool_bindings()) as held_tools,
    ):
        candidate = load_candidate_checker(held_tools)
        with candidate.PinnedRunnerFile(root) as held_runner:
            runner = candidate.load_pinned_runner(held_runner)
            with HeldSet(root, candidate.control_bindings()) as held_controls:
                documents = candidate.parse_control_documents(
                    runner,
                    held_controls,
                )
                candidate.validate_terminal_documents(runner, documents)
                sources = candidate.source_bindings(runner, documents)
                with HeldSet(
                    root,
                    source_hold_bindings(sources),
                ) as held_sources:
                    expected = content_bound(
                        expected_payload(
                            candidate,
                            runner,
                            documents,
                            sources,
                        )
                    )
                    held_tools.final_barrier()
                    held_runner.final_barrier()
                    held_controls.final_barrier()
                    held_sources.final_barrier()
                    validate_namespace_absent(root, held_namespace)
                    if verify_disk:
                        with HeldSet(
                            root,
                            decision_file_bindings(),
                        ) as held_decision:
                            raw = held_decision.raw[DECISION_PATH]
                            validate_decision_bytes(raw, expected)
                            validate_reader_bytes(held_decision.raw[READER_PATH])
                            if before_final_barrier is not None:
                                before_final_barrier()
                            held_tools.final_barrier()
                            held_runner.final_barrier()
                            held_controls.final_barrier()
                            held_sources.final_barrier()
                            held_decision.final_barrier()
                            validate_namespace_absent(
                                root,
                                held_namespace,
                            )
                    elif before_final_barrier is not None:
                        before_final_barrier()
                        held_tools.final_barrier()
                        held_runner.final_barrier()
                        held_controls.final_barrier()
                        held_sources.final_barrier()
                    validate_namespace_absent(root, held_namespace)
        summary = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-decision-check"
            ),
            "schemaVersion": "1.0",
            "decisionId": DECISION_ID,
            "status": "validated_execution_not_authorized",
            "validationPassed": True,
            "onDiskExactEqualityVerified": verify_disk,
            "heldSourceInputCount": 69,
            "candidateCheckerRawSha256": CANDIDATE_CHECKER_SHA256,
            "candidateTestsRawSha256": CANDIDATE_TESTS_SHA256,
            "immutableWave1GraphRunnerRawSha256": WAVE1_RUNNER_SHA256,
            "candidateOutputAcceptedAsEvidence": False,
            "fixedPointEvaluationAuthorized": False,
            "networkOperationCount": 0,
            "sourceExecutionCount": 0,
            "filesystemExtractionCount": 0,
            "subprocessCount": 0,
            "fileWriteCount": 0,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        }
        held_namespace.final_barrier()
        validate_namespace_absent(root, held_namespace)
        held_namespace.final_barrier()
        return expected, summary


def expected_decision(root: Path = ROOT) -> dict[str, Any]:
    expected, _ = evaluate(root, verify_disk=False)
    return expected


def check_repository(
    root: Path = ROOT,
    *,
    before_final_barrier: Callable[[], None] | None = None,
) -> dict[str, Any]:
    _, summary = evaluate(
        root,
        verify_disk=True,
        before_final_barrier=before_final_barrier,
    )
    return summary


def parse_arguments(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-expected",
        action="store_true",
        help="print the canonical expected decision without writing it",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        if args.print_expected:
            output = expected_decision(ROOT)
        else:
            output = check_repository(ROOT)
    except Exception:
        output = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "decision-check-error"
            ),
            "schemaVersion": "1.0",
            "status": "failed_closed",
            "networkOperationCount": 0,
            "sourceExecutionCount": 0,
            "fileWriteCount": 0,
        }
        sys.stdout.buffer.write(canonical_bytes(output))
        return 1
    sys.stdout.buffer.write(canonical_bytes(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
