#!/usr/bin/env python3
"""Shared fail-closed primitives for the G2 Pion dependency wave-two tools.

This module performs no network or filesystem mutation by itself.  It securely
holds authority inputs and exact-loads the previously verified wave-one ZIP/H1
implementation so the wave-two runner and independent readback checker do not
duplicate that security-sensitive parser.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types
from typing import Any, Mapping, Sequence


BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave2-v1.json"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave2_decision_v1.py"
)
LEGACY_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
)
WAVE1_V3_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave1_v3_once.py"
)

EXPECTED_DECISION_RAW_SHA256 = (
    "e10a4b41f0dc9ab9bc13b07f6b9e238e146316a7a4846af5b22f3a57fe0cd1a1"
)
EXPECTED_DECISION_CONTENT_SHA256 = (
    "1368918d79f629e2a07ec324201963b9558434aebeca2ef38261ebf62d180bc5"
)
EXPECTED_DECISION_CHECKER_RAW_SHA256 = (
    "146b4d3d9b38c05c01303b0b81146c68388905d4010345c8bda3807a6881d062"
)
EXPECTED_LEGACY_RUNNER_RAW_SHA256 = (
    "571985e002c6b819bfbe7153bb445beef27fdcad239a289b492005435c2a0356"
)
EXPECTED_WAVE1_V3_RUNNER_RAW_SHA256 = (
    "0855f7d7c14f1121ce74b678d5540d91ebbe482c5de306be84ecc6ddc910b5f1"
)

DEPENDENCY_PARENT = PurePosixPath(
    "build/offline-source/pion-ice-v4.3.0/dependencies"
)
CLAIM_NAME = ".wave-2-v1.claim"
STAGING_PREFIX = ".wave-2-v1-staging-"
WAVE_PARENT_NAME = "wave-2-v1"
FINAL_DIRECTORY_NAME = "accepted"
FINAL_DIRECTORY_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v1/accepted"
)
SUCCESS_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-receipt-v1.json"
)
FAILURE_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-manifest-v1.json"
)
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-manifest-v1.json"
)

MAXIMUM_JSON_BYTES = 2 * 1024 * 1024
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_MOD_BYTES = 1 * 1024 * 1024
MAXIMUM_ZIP_BYTES = 16 * 1024 * 1024
MAXIMUM_AGGREGATE_RESPONSE_BYTES = 64 * 1024 * 1024
MAXIMUM_ENTRIES_PER_ARCHIVE = 20_000
MAXIMUM_UNCOMPRESSED_BYTES_PER_ARCHIVE = 128 * 1024 * 1024
MAXIMUM_COMPRESSION_RATIO = 200
MAXIMUM_AGGREGATE_ENTRIES = 300_000
MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAXIMUM_CENTRAL_DIRECTORY_BYTES = 8 * 1024 * 1024
MAXIMUM_SINGLE_FILE_BYTES = 128 * 1024 * 1024
EXPECTED_TUPLE_COUNT = 15
EXPECTED_RESOURCE_COUNT = 30
MAXIMUM_SAFE_INTEGER = (1 << 63) - 1

COUNTER_NAMES = (
    "networkRequestAttemptCount",
    "responseBodyCompletedCount",
    "validatedAndStagedResourceCount",
    "validatedModResourceCount",
    "validatedZipResourceCount",
    "validatedAndStagedTupleCount",
)


class Wave2Failure(RuntimeError):
    """A bounded failure that is safe to map into a receipt."""

    def __init__(
        self,
        code: str,
        phase: str,
        *,
        tuple_id: str | None = None,
        tuple_order: int | None = None,
        request_ordinal: int | None = None,
        resource_kind: str | None = None,
        observations: Mapping[str, int] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase
        self.tuple_id = tuple_id
        self.tuple_order = tuple_order
        self.request_ordinal = request_ordinal
        self.resource_kind = resource_kind
        self.observations = dict(observations or {})


def require(condition: bool, code: str, phase: str = "preflight") -> None:
    if not condition:
        raise Wave2Failure(code, phase)


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


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "E_JSON")
        result[key] = value
    return result


def reject_number(_: str) -> Any:
    raise Wave2Failure("E_JSON", "preflight")


def validate_json_value(value: Any) -> None:
    if value is None or type(value) in {bool, str}:
        return
    if type(value) is int:
        require(
            -MAXIMUM_SAFE_INTEGER <= value <= MAXIMUM_SAFE_INTEGER,
            "E_JSON",
        )
        return
    if type(value) is list:
        for item in value:
            validate_json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, "E_JSON")
            validate_json_value(item)
        return
    if type(value) is float:
        require(math.isfinite(value), "E_JSON")
    raise Wave2Failure("E_JSON", "preflight")


def strict_json(raw: bytes, label: str = "json") -> dict[str, Any]:
    del label
    require(len(raw) <= MAXIMUM_JSON_BYTES, "E_JSON")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=strict_object,
            parse_float=reject_number,
            parse_constant=reject_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Wave2Failure("E_JSON", "preflight") from error
    validate_json_value(value)
    require(type(value) is dict, "E_JSON")
    return value


def validate_content_binding(
    document: Mapping[str, Any],
    *,
    scope: str,
    expected: str | None = None,
) -> str:
    binding = document.get("contentBinding")
    require(
        type(binding) is dict
        and binding.get("algorithm") == "sha256"
        and binding.get("canonicalization")
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding.get("scope") == scope
        and type(binding.get("sha256")) is str,
        "E_CONTENT_BINDING",
    )
    payload = dict(document)
    payload.pop("contentBinding", None)
    observed = sha256_bytes(canonical_json_bytes(payload))
    require(
        observed == binding["sha256"]
        and (expected is None or observed == expected),
        "E_CONTENT_BINDING",
    )
    return observed


def safe_relative_path(value: Any) -> str:
    require(
        type(value) is str
        and value
        and not value.startswith("/")
        and "\x00" not in value
        and "\\" not in value,
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
    """Open one file through a retained no-follow directory-fd chain."""

    def __init__(
        self,
        root_fd: int,
        relative: str,
        *,
        maximum_bytes: int,
        expected_sha256: str | None = None,
        owner_only: bool = False,
    ) -> None:
        self.relative = safe_relative_path(relative)
        self.maximum_bytes = maximum_bytes
        self.expected_sha256 = expected_sha256
        self.owner_only = owner_only
        self.directory_fds: list[
            tuple[int, os.stat_result, int, str]
        ] = []
        self.fd = -1
        self.parent_fd = os.dup(root_fd)
        try:
            current = self.parent_fd
            for component in self.relative.split("/")[:-1]:
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=current,
                )
                info = os.fstat(child)
                require(
                    stat.S_ISDIR(info.st_mode)
                    and info.st_uid in {0, os.geteuid()}
                    and stat.S_IMODE(info.st_mode) & 0o022 == 0,
                    "E_TOOL_IDENTITY",
                )
                self.directory_fds.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = self.relative.split("/")[-1]
            self.fd = os.open(
                self.name,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=self.parent_fd,
            )
            self.initial = os.fstat(self.fd)
            self._validate_info(self.initial)
            self.raw = self._read_once()
            require(
                expected_sha256 is None
                or sha256_bytes(self.raw) == expected_sha256,
                "E_TOOL_IDENTITY",
            )
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def _validate_info(self, info: os.stat_result) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and 0 <= info.st_size <= self.maximum_bytes,
            "E_TOOL_IDENTITY",
        )
        if self.owner_only:
            require(
                stat.S_IMODE(info.st_mode) == 0o600,
                "E_TOOL_IDENTITY",
            )
        else:
            require(
                stat.S_IMODE(info.st_mode) & 0o022 == 0,
                "E_TOOL_IDENTITY",
            )

    def _read_once(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_info(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_TOCTOU")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", "E_TOCTOU")
        require(
            file_identity(before) == file_identity(os.fstat(self.fd)),
            "E_TOCTOU",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        current = os.fstat(self.fd)
        named = os.stat(
            self.name,
            dir_fd=self.parent_fd,
            follow_symlinks=False,
        )
        require(
            file_identity(current) == file_identity(self.initial)
            and file_identity(named) == file_identity(self.initial),
            "E_TOCTOU",
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
                and directory_identity(named_dir)
                == directory_identity(initial),
                "E_TOCTOU",
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
    """Retain exact authority bytes and every parent component until close."""

    def __init__(
        self,
        root: Path,
        bindings: Sequence[Mapping[str, Any]],
    ) -> None:
        self.root = root.resolve()
        self.root_fd = os.open(
            self.root,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        self.root_initial = os.fstat(self.root_fd)
        self.files: dict[str, HeldFile] = {}
        try:
            seen: set[str] = set()
            for binding in bindings:
                relative = safe_relative_path(binding["path"])
                require(relative not in seen, "E_INPUT_INVENTORY")
                seen.add(relative)
                held = HeldFile(
                    self.root_fd,
                    relative,
                    maximum_bytes=int(binding["maximumBytes"]),
                    expected_sha256=binding.get("rawSha256"),
                    owner_only=bool(binding.get("ownerOnly", False)),
                )
                self.files[relative] = held
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def raw(self, relative: str) -> bytes:
        return self.files[relative].raw

    def final_barrier(self) -> None:
        require(
            directory_identity(os.fstat(self.root_fd))
            == directory_identity(self.root_initial),
            "E_TOCTOU",
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

    def __enter__(self) -> "HeldInputSet":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def execute_fixed_module(
    name: str,
    relative: str,
    raw: bytes,
    root: Path,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(root / relative),
            "__loader__": None,
            "__package__": None,
        }
    )
    try:
        previous = sys.modules.get(name)
        sys.modules[name] = module
        exec(
            compile(raw, relative, "exec", dont_inherit=True, optimize=0),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise Wave2Failure("E_TOOL_LOAD", "preflight") from error
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


def decision_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": DECISION_PATH,
            "rawSha256": EXPECTED_DECISION_RAW_SHA256,
            "maximumBytes": MAXIMUM_JSON_BYTES,
        },
        {
            "path": DECISION_CHECKER_PATH,
            "rawSha256": EXPECTED_DECISION_CHECKER_RAW_SHA256,
            "maximumBytes": MAXIMUM_TOOL_BYTES,
        },
    ]


def primitive_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": LEGACY_RUNNER_PATH,
            "rawSha256": EXPECTED_LEGACY_RUNNER_RAW_SHA256,
            "maximumBytes": MAXIMUM_TOOL_BYTES,
        },
        {
            "path": WAVE1_V3_RUNNER_PATH,
            "rawSha256": EXPECTED_WAVE1_V3_RUNNER_RAW_SHA256,
            "maximumBytes": MAXIMUM_TOOL_BYTES,
        },
    ]


def load_decision(
    inputs: HeldInputSet,
    root: Path,
    *,
    require_empty_namespace: bool,
) -> dict[str, Any]:
    checker = execute_fixed_module(
        "g2_wave2_decision_checker_trust_root",
        DECISION_CHECKER_PATH,
        inputs.raw(DECISION_CHECKER_PATH),
        root,
    )
    try:
        checked = checker.check(
            root,
            require_namespace_preflight=require_empty_namespace,
        )
    except Exception as error:
        raise Wave2Failure("E_DECISION_STATE", "preflight") from error
    require(
        checked.get("tupleCount") == EXPECTED_TUPLE_COUNT
        and checked.get("resourceCount") == EXPECTED_RESOURCE_COUNT
        and checked.get("externalAuthenticationRequired") is False
        and checked.get("userActionRequired") is False
        and checked.get("acquisitionAuthorized") is False,
        "E_DECISION_STATE",
    )
    decision = strict_json(inputs.raw(DECISION_PATH), DECISION_PATH)
    validate_content_binding(
        decision,
        scope="decision_without_contentBinding",
        expected=EXPECTED_DECISION_CONTENT_SHA256,
    )
    return decision


def validate_h1(value: Any) -> str:
    require(
        type(value) is str and value.startswith("h1:"),
        "E_H1",
    )
    try:
        decoded = base64.b64decode(value[3:], validate=True)
    except Exception as error:
        raise Wave2Failure("E_H1", "preflight") from error
    require(
        len(decoded) == 32
        and base64.b64encode(decoded).decode("ascii") == value[3:],
        "E_H1",
    )
    return value


def adapt_tuples(decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    wave = decision.get("wave")
    require(type(wave) is dict, "E_WAVE_TUPLES")
    tuples = wave.get("tuples")
    require(
        type(tuples) is list
        and len(tuples) == EXPECTED_TUPLE_COUNT
        and wave.get("resourceCount") == EXPECTED_RESOURCE_COUNT,
        "E_WAVE_TUPLES",
    )
    result: list[dict[str, Any]] = []
    resource_ordinals: list[int] = []
    for order, source in enumerate(tuples, start=1):
        require(
            type(source) is dict
            and source.get("tupleOrder") == order
            and type(source.get("tupleId")) is str
            and source["tupleId"].startswith(f"wave2-{order:03d}-")
            and type(source.get("tupleDigestSha256")) is str
            and len(source["tupleDigestSha256"]) == 64
            and type(source.get("module")) is str
            and type(source.get("version")) is str
            and type(source.get("selectedByGraphAlgorithm")) is bool,
            "E_WAVE_TUPLES",
        )
        resources = source.get("resources")
        require(
            type(resources) is list
            and len(resources) == 2
            and [resource.get("kind") for resource in resources]
            == ["mod", "zip"]
            and [resource.get("order") for resource in resources]
            == [2 * order - 1, 2 * order],
            "E_WAVE_RESOURCES",
        )
        mod_resource, zip_resource = resources
        stem = f"{order:03d}-{source['tupleDigestSha256'][:20]}"
        require(
            mod_resource.get("outputPath")
            == f"{FINAL_DIRECTORY_PATH}/{stem}.mod"
            and zip_resource.get("outputPath")
            == f"{FINAL_DIRECTORY_PATH}/{stem}.zip"
            and mod_resource.get("checksumKind") == "go_mod_h1"
            and zip_resource.get("checksumKind") == "module_zip_h1"
            and type(mod_resource.get("url")) is str
            and mod_resource["url"].endswith(".mod")
            and type(zip_resource.get("url")) is str
            and zip_resource["url"].endswith(".zip"),
            "E_WAVE_RESOURCES",
        )
        item = {
            "order": order,
            "tupleId": source["tupleId"],
            "tupleSha256": source["tupleDigestSha256"],
            "module": source["module"],
            "version": source["version"],
            "selectedByGraphAlgorithm": source[
                "selectedByGraphAlgorithm"
            ],
            "modUrl": mod_resource["url"],
            "url": zip_resource["url"],
            "goModH1": validate_h1(mod_resource.get("expectedH1")),
            "moduleZipH1": validate_h1(zip_resource.get("expectedH1")),
            "modOutputFileName": f"{stem}.mod",
            "zipOutputFileName": f"{stem}.zip",
            "modRequestOrdinal": mod_resource["order"],
            "zipRequestOrdinal": zip_resource["order"],
        }
        result.append(item)
        resource_ordinals.extend(
            [item["modRequestOrdinal"], item["zipRequestOrdinal"]]
        )
    require(
        resource_ordinals == list(range(1, EXPECTED_RESOURCE_COUNT + 1)),
        "E_WAVE_RESOURCES",
    )
    return result


def configure_primitives(
    inputs: HeldInputSet,
    root: Path,
) -> tuple[types.ModuleType, types.ModuleType]:
    legacy = execute_fixed_module(
        "g2_wave2_immutable_wave1_v1_primitives",
        LEGACY_RUNNER_PATH,
        inputs.raw(LEGACY_RUNNER_PATH),
        root,
    )
    core = execute_fixed_module(
        "g2_wave2_immutable_wave1_v3_primitives",
        WAVE1_V3_RUNNER_PATH,
        inputs.raw(WAVE1_V3_RUNNER_PATH),
        root,
    )
    for module in (legacy, core):
        module.ROOT = root
    for module in (legacy, core):
        module.CLAIM_NAME = CLAIM_NAME
        module.STAGING_PREFIX = STAGING_PREFIX
        module.DEPENDENCY_PARENT = DEPENDENCY_PARENT
        module.WAVE_PARENT_NAME = WAVE_PARENT_NAME
        module.FINAL_DIRECTORY_NAME = FINAL_DIRECTORY_NAME
        module.SUCCESS_RECEIPT_PATH = SUCCESS_RECEIPT_PATH
        module.FAILURE_RECEIPT_PATH = FAILURE_RECEIPT_PATH
        module.MANIFEST_PATH = MANIFEST_PATH
    core.FINAL_DIRECTORY_PATH = FINAL_DIRECTORY_PATH
    core.MAXIMUM_MOD_BYTES = MAXIMUM_MOD_BYTES
    core.MAXIMUM_ZIP_BYTES = MAXIMUM_ZIP_BYTES
    core.MAXIMUM_AGGREGATE_MOD_BYTES = MAXIMUM_AGGREGATE_RESPONSE_BYTES
    core.MAXIMUM_AGGREGATE_ZIP_BYTES = MAXIMUM_AGGREGATE_RESPONSE_BYTES
    core.MAXIMUM_AGGREGATE_RESPONSE_BYTES = MAXIMUM_AGGREGATE_RESPONSE_BYTES
    core.EXPECTED_TUPLE_COUNT = EXPECTED_TUPLE_COUNT
    core.EXPECTED_RESOURCE_COUNT = EXPECTED_RESOURCE_COUNT
    core.EXPECTED_ACQUISITION_REGULAR_FILE_COUNT = 33
    original_inspect = core.inspect_module_zip_v3

    def inspect_with_ratio_gate(
        legacy_module: types.ModuleType,
        fd: int,
        item: Mapping[str, Any],
        limits: Mapping[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = original_inspect(
            legacy_module,
            fd,
            item,
            limits,
            **kwargs,
        )
        telemetry = result["compressionTelemetry"]
        uncompressed = telemetry["maximumRatioEntryUncompressedBytes"]
        compressed = telemetry["maximumRatioEntryCompressedBytes"]
        require(
            compression_ratio_allowed(uncompressed, compressed),
            "E_ZIP_COMPRESSION_RATIO",
            "zip",
        )
        result["compressionTelemetry"] = {
            **telemetry,
            "policy": "gating_integer_ratio_maximum_200",
            "maximumAllowedRatio": MAXIMUM_COMPRESSION_RATIO,
            "ratioLimitPassed": True,
        }
        return result

    core.inspect_module_zip_v3 = inspect_with_ratio_gate
    return legacy, core


def compression_ratio_allowed(
    uncompressed_bytes: int,
    compressed_bytes: int,
) -> bool:
    return (
        type(uncompressed_bytes) is int
        and type(compressed_bytes) is int
        and uncompressed_bytes >= 0
        and compressed_bytes >= 0
        and (
            (uncompressed_bytes == 0 and compressed_bytes == 0)
            or (
                compressed_bytes > 0
                and uncompressed_bytes
                <= compressed_bytes * MAXIMUM_COMPRESSION_RATIO
            )
        )
    )


def archive_limits() -> dict[str, int]:
    return {
        "maximumEntriesPerArchive": MAXIMUM_ENTRIES_PER_ARCHIVE,
        "maximumAggregateEntries": MAXIMUM_AGGREGATE_ENTRIES,
        "maximumCentralDirectoryBytesPerArchive": (
            MAXIMUM_CENTRAL_DIRECTORY_BYTES
        ),
        "maximumSingleFileBytes": MAXIMUM_SINGLE_FILE_BYTES,
        "maximumUncompressedBytesPerArchive": (
            MAXIMUM_UNCOMPRESSED_BYTES_PER_ARCHIVE
        ),
        "maximumAggregateUncompressedBytes": (
            MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
        ),
        "maximumPathBytes": 1024,
        "maximumPathComponents": 64,
        "maximumComponentBytes": 255,
    }


def output_names(item: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(item["modOutputFileName"]),
        str(item["zipOutputFileName"]),
    )


def zero_counters() -> dict[str, int]:
    return {name: 0 for name in COUNTER_NAMES}


def validate_counters(counters: Mapping[str, Any]) -> None:
    require(
        set(counters) == set(COUNTER_NAMES)
        and all(
            type(counters[name]) is int
            and 0 <= counters[name] <= EXPECTED_RESOURCE_COUNT
            for name in COUNTER_NAMES
        ),
        "E_COUNTER_INVARIANT",
        "execution",
    )
    attempt = counters["networkRequestAttemptCount"]
    response = counters["responseBodyCompletedCount"]
    resource = counters["validatedAndStagedResourceCount"]
    mod_count = counters["validatedModResourceCount"]
    zip_count = counters["validatedZipResourceCount"]
    tuple_count = counters["validatedAndStagedTupleCount"]
    require(
        0 <= tuple_count <= min(mod_count, zip_count)
        and tuple_count == zip_count
        and mod_count in {zip_count, zip_count + 1}
        and resource == mod_count + zip_count
        and resource <= response <= attempt <= EXPECTED_RESOURCE_COUNT,
        "E_COUNTER_INVARIANT",
        "execution",
    )


def success_counters(counters: Mapping[str, Any]) -> bool:
    return [counters.get(name) for name in COUNTER_NAMES] == [
        30,
        30,
        30,
        15,
        15,
        15,
    ]


def ordered_source_set_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(list(rows)))


def expected_resource_names(items: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(name for item in items for name in output_names(item))


def namespace_exact_paths(root: Path) -> dict[str, Path]:
    return {
        "claim": root / str(DEPENDENCY_PARENT) / CLAIM_NAME,
        "waveParent": root / str(DEPENDENCY_PARENT) / WAVE_PARENT_NAME,
        "final": root / FINAL_DIRECTORY_PATH,
        "success": root / SUCCESS_RECEIPT_PATH,
        "failure": root / FAILURE_RECEIPT_PATH,
        "manifest": root / MANIFEST_PATH,
        "readback": root / READBACK_RECEIPT_PATH,
        "readbackManifest": root / READBACK_MANIFEST_PATH,
    }


def require_clean_namespace(root: Path) -> None:
    for label, path in namespace_exact_paths(root).items():
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise Wave2Failure("E_NAMESPACE", "preflight") from error
        raise Wave2Failure(f"E_NAMESPACE_{label.upper()}", "preflight")
    parent = root / str(DEPENDENCY_PARENT)
    try:
        names = os.listdir(parent)
    except OSError as error:
        raise Wave2Failure("E_NAMESPACE", "preflight") from error
    require(
        not any(name.startswith(STAGING_PREFIX) for name in names),
        "E_NAMESPACE_STAGING",
    )


def bounded_observations(values: Mapping[str, Any]) -> dict[str, int]:
    allowed = {
        "httpStatus",
        "responseBytes",
        "aggregateModBytes",
        "aggregateZipBytes",
        "aggregateResponseBytes",
        "entryOrdinal",
        "entryUncompressedBytes",
        "entryCompressedBytes",
        *COUNTER_NAMES,
    }
    return {
        key: value
        for key, value in values.items()
        if key in allowed
        and type(value) is int
        and 0 <= value <= MAXIMUM_SAFE_INTEGER
    }


def map_core_failure(
    core: types.ModuleType,
    error: Exception,
    *,
    tuple_id: str | None = None,
    tuple_order: int | None = None,
    request_ordinal: int | None = None,
    resource_kind: str | None = None,
    phase: str = "execution",
) -> Wave2Failure:
    if isinstance(error, Wave2Failure):
        return Wave2Failure(
            error.code,
            error.phase,
            tuple_id=error.tuple_id or tuple_id,
            tuple_order=(
                error.tuple_order
                if error.tuple_order is not None
                else tuple_order
            ),
            request_ordinal=(
                error.request_ordinal
                if error.request_ordinal is not None
                else request_ordinal
            ),
            resource_kind=error.resource_kind or resource_kind,
            observations=bounded_observations(error.observations),
        )
    if isinstance(error, core.RunnerFailure):
        return Wave2Failure(
            str(error.code),
            str(error.phase),
            tuple_id=error.tuple_id or tuple_id,
            tuple_order=(
                error.tuple_order
                if error.tuple_order is not None
                else tuple_order
            ),
            request_ordinal=request_ordinal,
            resource_kind=error.resource_kind or resource_kind,
            observations=bounded_observations(error.observations),
        )
    return Wave2Failure(
        "E_INTERNAL",
        phase,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        request_ordinal=request_ordinal,
        resource_kind=resource_kind,
    )
