#!/usr/bin/env python3
"""Acquire the exact G2 Pion dependency wave-one MOD+ZIP set through v3 once.

The default mode is a read-only preflight.  ``--execute`` requires a separate
v3 permit, creates a fresh one-use namespace, and performs exactly one
sequential MOD-then-ZIP request pair for each of the 19 pinned tuples.  It
never invokes Go, Git, a shell, a package manager, a compiler, or source code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import closing
from pathlib import Path, PurePosixPath
import stat
import sys
import time
import types
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
RECOVERY_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-"
    "recovery-decision-v2.json"
)
RECOVERY_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_recovery_decision_v2.py"
)
SOURCE_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v3.json"
)
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v3.py"
)
LEGACY_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
)
V2_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave1_v2_once.py"
)
THIS_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave1_v3_once.py"
)

EXPECTED_RECOVERY_CHECKER_RAW_SHA256 = (
    "25e4f6f6f9d49424428bd9017afad688652467fa8a2c038233dacea1aed15cbc"
)
EXPECTED_RECOVERY_RAW_SHA256 = (
    "c03ca34315226ad8a59d8857448657c3be2565b22c0583085eb93c6c65ad72fd"
)
EXPECTED_RECOVERY_CONTENT_SHA256 = (
    "5a41d5bcf7dccb25bb5e558d892620748ea72e12e9f90244242ffdb44e092a93"
)
EXPECTED_SOURCE_DECISION_RAW_SHA256 = (
    "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
)
EXPECTED_SOURCE_DECISION_CONTENT_SHA256 = (
    "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201"
)
EXPECTED_LEGACY_RUNNER_RAW_SHA256 = (
    "571985e002c6b819bfbe7153bb445beef27fdcad239a289b492005435c2a0356"
)
EXPECTED_V2_RUNNER_RAW_SHA256 = (
    "9dcbd6e70e6a7904b468042ee116f04f014a4299f30ea32c41c4f850af53b823"
)
EXPECTED_PERMIT_CHECKER_RAW_SHA256 = (
    "da8df9cbab7bd739b9471a43a909150479f197f94c6377dd2bae2267c2e13cb9"
)

EXPECTED_PERMIT_STATUS = (
    "wave1_v3_dependency_source_acquisition_authorized_not_consumed"
)
EXPECTED_PERMIT_RESULT = (
    "exact_19_public_proxy_mod_then_zip_pairs_v3_authorized_once_not_executed"
)
EXPECTED_PERMIT_NEXT_ACTION = (
    "execute_bound_dependency_source_wave1_v3_once"
)
EXPECTED_RECOVERY_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-recovery-decision-v2"
)

DEPENDENCY_PARENT = PurePosixPath(
    "build/offline-source/pion-ice-v4.3.0/dependencies"
)
CLAIM_NAME = ".wave-1-v3.claim"
STAGING_PREFIX = ".wave-1-v3-staging-"
WAVE_PARENT_NAME = "wave-1-v3"
FINAL_DIRECTORY_NAME = "accepted"
FINAL_DIRECTORY_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v3/accepted"
)
SUCCESS_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v3.json"
)
FAILURE_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v3.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v3.json"
)

MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 2 * 1024 * 1024
MAXIMUM_MOD_BYTES = 1 * 1024 * 1024
MAXIMUM_AGGREGATE_MOD_BYTES = 8 * 1024 * 1024
MAXIMUM_ZIP_BYTES = 16 * 1024 * 1024
MAXIMUM_AGGREGATE_ZIP_BYTES = 128 * 1024 * 1024
MAXIMUM_AGGREGATE_RESPONSE_BYTES = 136 * 1024 * 1024
PER_REQUEST_DEADLINE_MILLISECONDS = 30_000
WHOLE_WAVE_DEADLINE_MILLISECONDS = 600_000
EXPECTED_TUPLE_COUNT = 19
EXPECTED_RESOURCE_COUNT = 38
EXPECTED_ACQUISITION_REGULAR_FILE_COUNT = 41
MAXIMUM_SAFE_INTEGER = (1 << 63) - 1
STREAM_CHUNK_BYTES = 64 * 1024

COUNTER_NAMES = (
    "networkRequestAttemptCount",
    "responseBodyCompletedCount",
    "validatedAndStagedResourceCount",
    "validatedModResourceCount",
    "validatedZipResourceCount",
    "validatedAndStagedTupleCount",
)
SAFE_OBSERVATION_NAMES = frozenset(
    {
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
)
RESOURCE_KINDS = frozenset({"mod", "zip"})
ALLOWED_FAILURE_PHASES = frozenset(
    {
        "preflight",
        "filesystem",
        "mod",
        "zip",
        "publication",
        "post_publish",
        "execution",
    }
)
ALLOWED_FAILURE_CODES = frozenset(
    {
        "E_ACCEPTED_COUNT",
        "E_AGGREGATE_ENTRY_COUNT",
        "E_AGGREGATE_MOD_TOO_LARGE",
        "E_AGGREGATE_RESPONSE_TOO_LARGE",
        "E_AGGREGATE_UNCOMPRESSED",
        "E_AGGREGATE_ZIP_TOO_LARGE",
        "E_CLAIM_EXISTS",
        "E_CLAIM_STATE",
        "E_CONTENT_ENCODING",
        "E_CONTENT_LENGTH",
        "E_CONTENT_LENGTH_MISMATCH",
        "E_CONTENT_TYPE",
        "E_COUNTER_INVARIANT",
        "E_DEADLINE_ENVIRONMENT",
        "E_EMPTY_RESPONSE",
        "E_FAILURE_STATE",
        "E_FILESYSTEM_CREATE",
        "E_FILESYSTEM_LINK",
        "E_FILESYSTEM_LIST",
        "E_FILESYSTEM_MODE",
        "E_FILESYSTEM_OWNER",
        "E_FILESYSTEM_ROOT",
        "E_FILESYSTEM_ROOT_IDENTITY",
        "E_FILESYSTEM_STAT",
        "E_FILESYSTEM_TYPE",
        "E_FILESYSTEM_WRITE",
        "E_FILE_TOO_LARGE",
        "E_FORBIDDEN_RESPONSE_HEADER",
        "E_GO_MOD_DUPLICATE",
        "E_GO_MOD_ENCODING",
        "E_GO_MOD_H1",
        "E_GO_MOD_MODULE",
        "E_GO_MOD_PARITY",
        "E_HTTP_STATUS",
        "E_INTERNAL",
        "E_INTERPRETER",
        "E_JSON_BINDING",
        "E_MOD_URL",
        "E_MODULE_H1",
        "E_MODULE_PREFIX",
        "E_ONE_USE_STATE_PRESENT",
        "E_OUTPUT_EXISTS",
        "E_OUTPUT_IDENTITY",
        "E_OUTPUT_INVENTORY",
        "E_OUTPUT_PUBLISH",
        "E_PATH",
        "E_PERMIT_IDENTITY",
        "E_PERMIT_STATE",
        "E_PERMIT_VALIDATION",
        "E_POST_PUBLISH_UNCERTAIN",
        "E_RECOVERY_IDENTITY",
        "E_RECOVERY_STATE",
        "E_REDIRECT",
        "E_RENAME_EXCL_UNAVAILABLE",
        "E_REQUEST_COUNT",
        "E_REQUEST_DEADLINE",
        "E_RESPONSE_TOO_LARGE",
        "E_SOURCE_IDENTITY",
        "E_STAGING_COLLISION",
        "E_STAGING_CREATE",
        "E_STAGING_EXISTS",
        "E_STAGING_STATE",
        "E_TOOL_IDENTITY",
        "E_TOOL_LOAD",
        "E_TOCTOU",
        "E_TRANSPORT",
        "E_WAVE_DEADLINE",
        "E_WAVE_TUPLES",
        "E_ZIP64",
        "E_ZIP_CASE_COLLISION",
        "E_ZIP_CENTRAL_DIRECTORY",
        "E_ZIP_COMMENT",
        "E_ZIP_COMPRESSED_SIZE",
        "E_ZIP_COMPRESSION",
        "E_ZIP_CREATOR_SYSTEM",
        "E_ZIP_DATA_DESCRIPTOR",
        "E_ZIP_DIRECTORY_ENTRY",
        "E_ZIP_DUPLICATE",
        "E_ZIP_ENCRYPTED",
        "E_ZIP_ENTRY_COUNT",
        "E_ZIP_EOCD",
        "E_ZIP_EXTRA",
        "E_ZIP_FILE_SIZE",
        "E_ZIP_FLAGS",
        "E_ZIP_FORMAT",
        "E_ZIP_LOCAL_HEADER",
        "E_ZIP_MULTIDISK",
        "E_ZIP_NAME_ENCODING",
        "E_ZIP_PATH",
        "E_ZIP_READ",
        "E_ZIP_SPECIAL_FILE",
        "E_ZIP_SPECIAL_MODE",
        "E_ZIP_TRAILING",
        "E_ZIP_UNCOMPRESSED",
    }
)


class RunnerFailure(RuntimeError):
    """A bounded v3 failure safe to serialize."""

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
        super().__init__(code)
        self.code = code
        self.phase = phase
        self.tuple_id = tuple_id
        self.tuple_order = tuple_order
        self.resource_kind = resource_kind
        self.observations = dict(observations or {})


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
        raise RunnerFailure(
            code,
            phase,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
            observations=observations,
        )


def require_isolated_interpreter() -> None:
    require(
        sys.flags.isolated == 1 and sys.dont_write_bytecode,
        "E_INTERPRETER",
        "preflight",
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


def safe_integer(value: Any) -> bool:
    return type(value) is int and 0 <= value <= MAXIMUM_SAFE_INTEGER


def bounded_observations(values: Mapping[str, Any]) -> dict[str, int]:
    return {
        key: value
        for key, value in values.items()
        if key in SAFE_OBSERVATION_NAMES and safe_integer(value)
    }


def read_stable_source(relative: str, maximum_bytes: int) -> bytes:
    path = ROOT / relative
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise RunnerFailure("E_TOOL_IDENTITY", "preflight") from error
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid()
            and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= maximum_bytes,
            "E_TOOL_IDENTITY",
            "preflight",
        )
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, min(STREAM_CHUNK_BYTES, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        require(
            len(raw) == before.st_size
            and (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "E_TOCTOU",
            "preflight",
        )
        return raw
    finally:
        os.close(fd)


def execute_fixed_module(name: str, relative: str, raw: bytes) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / relative),
            "__loader__": None,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(raw, relative, "exec", dont_inherit=True, optimize=0),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise RunnerFailure("E_TOOL_LOAD", "preflight") from error
    return module


def strict_json(legacy: types.ModuleType, raw: bytes, label: str) -> dict[str, Any]:
    try:
        document = legacy.strict_json(raw, label)
    except Exception as error:
        raise RunnerFailure("E_JSON_BINDING", "preflight") from error
    require(isinstance(document, dict), "E_JSON_BINDING", "preflight")
    return document


def configure_legacy(legacy: types.ModuleType) -> None:
    legacy.ROOT = ROOT
    legacy.CLAIM_NAME = CLAIM_NAME
    legacy.STAGING_PREFIX = STAGING_PREFIX
    legacy.DEPENDENCY_PARENT = DEPENDENCY_PARENT
    legacy.WAVE_PARENT_NAME = WAVE_PARENT_NAME
    legacy.FINAL_DIRECTORY_NAME = FINAL_DIRECTORY_NAME
    legacy.SUCCESS_RECEIPT_PATH = SUCCESS_RECEIPT_PATH
    legacy.FAILURE_RECEIPT_PATH = FAILURE_RECEIPT_PATH
    legacy.MANIFEST_PATH = MANIFEST_PATH


def v3_namespace_artifact_may_exist() -> bool:
    """Conservatively detect whether the clean-only recovery checker must defer."""
    exact_paths = (
        ROOT / str(DEPENDENCY_PARENT) / CLAIM_NAME,
        ROOT / FINAL_DIRECTORY_PATH,
        ROOT / SUCCESS_RECEIPT_PATH,
        ROOT / FAILURE_RECEIPT_PATH,
        ROOT / MANIFEST_PATH,
    )
    for path in exact_paths:
        try:
            os.lstat(path)
            return True
        except FileNotFoundError:
            pass
        except OSError:
            return True
    parent = ROOT / str(DEPENDENCY_PARENT)
    try:
        names = os.listdir(parent)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return any(name.startswith(STAGING_PREFIX) for name in names)


def validate_content_binding(
    document: Mapping[str, Any],
    *,
    scope: str,
    expected: str | None = None,
) -> str:
    binding = document.get("contentBinding")
    require(
        isinstance(binding, dict)
        and binding.get("algorithm") == "sha256"
        and binding.get("canonicalization")
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding.get("scope") == scope
        and isinstance(binding.get("sha256"), str),
        "E_JSON_BINDING",
        "preflight",
    )
    payload = dict(document)
    payload.pop("contentBinding", None)
    observed = sha256_bytes(canonical_json_bytes(payload))
    require(
        observed == binding["sha256"]
        and (expected is None or observed == expected),
        "E_JSON_BINDING",
        "preflight",
    )
    return observed


def validate_exact_tuples(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    wave = source.get("wave")
    require(isinstance(wave, dict), "E_WAVE_TUPLES", "preflight")
    tuples = wave.get("tuples")
    require(
        isinstance(tuples, list)
        and len(tuples) == EXPECTED_TUPLE_COUNT,
        "E_WAVE_TUPLES",
        "preflight",
    )
    result: list[dict[str, Any]] = []
    for order, value in enumerate(tuples, start=1):
        require(isinstance(value, dict), "E_WAVE_TUPLES", "preflight")
        item = dict(value)
        required = (
            "order",
            "tupleId",
            "tupleSha256",
            "module",
            "version",
            "moduleZipH1",
            "goModH1",
            "url",
        )
        require(
            all(isinstance(item.get(key), (str, int)) for key in required)
            and item["order"] == order
            and isinstance(item["tupleId"], str)
            and item["tupleId"].startswith(f"wave1-{order:03d}-")
            and isinstance(item["tupleSha256"], str)
            and len(item["tupleSha256"]) == 64
            and all(c in "0123456789abcdef" for c in item["tupleSha256"])
            and item["url"].endswith(".zip"),
            "E_WAVE_TUPLES",
            "preflight",
        )
        derive_mod_url(item)
        output_names(item)
        result.append(item)
    return result


def validate_permit(
    permit: Mapping[str, Any],
    *,
    recovery: Mapping[str, Any],
    runner_raw_sha256: str,
) -> None:
    content_sha256 = validate_content_binding(
        permit,
        scope="permit_without_contentBinding",
    )
    recovery_binding = permit.get("recoveryBinding")
    runner_binding = permit.get("runnerBinding")
    authority = permit.get("authority")
    require(
        permit.get("documentType")
        == "aetherlink.g2-pion-rung3-dependency-wave1-execution-permit"
        and permit.get("schemaVersion") == "3.0"
        and isinstance(permit.get("permitId"), str)
        and permit.get("status") == EXPECTED_PERMIT_STATUS
        and permit.get("result") == EXPECTED_PERMIT_RESULT
        and permit.get("nextAction") == EXPECTED_PERMIT_NEXT_ACTION
        and isinstance(recovery_binding, dict)
        and recovery_binding.get("path") == RECOVERY_PATH
        and recovery_binding.get("rawSha256") == EXPECTED_RECOVERY_RAW_SHA256
        and recovery_binding.get("contentSha256")
        == EXPECTED_RECOVERY_CONTENT_SHA256
        and isinstance(runner_binding, dict)
        and runner_binding.get("path") == THIS_RUNNER_PATH
        and runner_binding.get("rawSha256") == runner_raw_sha256
        and isinstance(authority, dict)
        and authority.get("networkAuthorized") is True
        and authority.get("dependencySourceAcquisitionAuthorized") is True
        and authority.get("maximumRequestCount") == EXPECTED_RESOURCE_COUNT
        and authority.get("automaticRetryAllowed") is False
        and authority.get("credentialsAllowed") is False
        and authority.get("authenticationRequired") is False
        and len(content_sha256) == 64
        and recovery.get("decisionId") == EXPECTED_RECOVERY_DECISION_ID,
        "E_PERMIT_STATE",
        "preflight",
    )


def load_validated_authority() -> dict[str, Any]:
    require_isolated_interpreter()
    checker_raw = read_stable_source(
        RECOVERY_CHECKER_PATH,
        MAXIMUM_TOOL_BYTES,
    )
    require(
        sha256_bytes(checker_raw) == EXPECTED_RECOVERY_CHECKER_RAW_SHA256,
        "E_RECOVERY_IDENTITY",
        "preflight",
    )
    checker = execute_fixed_module(
        "g2_dependency_wave1_v3_recovery_checker_trust_root",
        RECOVERY_CHECKER_PATH,
        checker_raw,
    )
    recovery_clean_check_deferred = v3_namespace_artifact_may_exist()
    if recovery_clean_check_deferred:
        checked = {
            "v3ExecutionAuthorized": False,
            "cleanNamespaceValidationDeferredToTerminalPreflight": True,
        }
    else:
        try:
            checked = checker.validate_repository(ROOT)
        except Exception as error:
            raise RunnerFailure("E_RECOVERY_STATE", "preflight") from error
        require(
            isinstance(checked, dict)
            and checked.get("v3ExecutionAuthorized") is False,
            "E_RECOVERY_STATE",
            "preflight",
        )

    legacy_raw = read_stable_source(LEGACY_RUNNER_PATH, MAXIMUM_TOOL_BYTES)
    v2_raw = read_stable_source(V2_RUNNER_PATH, MAXIMUM_TOOL_BYTES)
    require(
        sha256_bytes(legacy_raw) == EXPECTED_LEGACY_RUNNER_RAW_SHA256
        and sha256_bytes(v2_raw) == EXPECTED_V2_RUNNER_RAW_SHA256,
        "E_TOOL_IDENTITY",
        "preflight",
    )
    legacy = execute_fixed_module(
        "g2_dependency_wave1_v3_immutable_v1_primitives",
        LEGACY_RUNNER_PATH,
        legacy_raw,
    )
    v2 = execute_fixed_module(
        "g2_dependency_wave1_v3_immutable_v2_primitives",
        V2_RUNNER_PATH,
        v2_raw,
    )
    configure_legacy(legacy)

    recovery_raw = read_stable_source(RECOVERY_PATH, MAXIMUM_JSON_BYTES)
    source_raw = read_stable_source(SOURCE_DECISION_PATH, MAXIMUM_JSON_BYTES)
    require(
        sha256_bytes(recovery_raw) == EXPECTED_RECOVERY_RAW_SHA256,
        "E_RECOVERY_IDENTITY",
        "preflight",
    )
    require(
        sha256_bytes(source_raw) == EXPECTED_SOURCE_DECISION_RAW_SHA256,
        "E_SOURCE_IDENTITY",
        "preflight",
    )
    recovery = strict_json(legacy, recovery_raw, RECOVERY_PATH)
    source = strict_json(legacy, source_raw, SOURCE_DECISION_PATH)
    validate_content_binding(
        recovery,
        scope="decision_without_contentBinding",
        expected=EXPECTED_RECOVERY_CONTENT_SHA256,
    )
    tuples = validate_exact_tuples(source)

    try:
        permit_checker_raw = read_stable_source(
            PERMIT_CHECKER_PATH,
            MAXIMUM_TOOL_BYTES,
        )
    except RunnerFailure as error:
        raise RunnerFailure("E_PERMIT_IDENTITY", "preflight") from error
    require(
        len(EXPECTED_PERMIT_CHECKER_RAW_SHA256) == 64
        and all(
            character in "0123456789abcdef"
            for character in EXPECTED_PERMIT_CHECKER_RAW_SHA256
        )
        and sha256_bytes(permit_checker_raw)
        == EXPECTED_PERMIT_CHECKER_RAW_SHA256,
        "E_PERMIT_IDENTITY",
        "preflight",
    )
    permit_checker = execute_fixed_module(
        "g2_dependency_wave1_v3_permit_checker_trust_root",
        PERMIT_CHECKER_PATH,
        permit_checker_raw,
    )
    try:
        permit_authority = permit_checker.validate_repository(ROOT)
    except Exception as error:
        raise RunnerFailure("E_PERMIT_VALIDATION", "preflight") from error
    require(
        isinstance(permit_authority, dict)
        and isinstance(permit_authority.get("permit"), dict)
        and isinstance(permit_authority.get("sourceDecision"), dict)
        and isinstance(permit_authority.get("recoveryDecision"), dict)
        and isinstance(permit_authority.get("repositoryRootIdentity"), dict)
        and permit_authority.get("v3ExecutionAuthorized") is True,
        "E_PERMIT_VALIDATION",
        "preflight",
    )
    permit = permit_authority["permit"]
    permit_raw = read_stable_source(PERMIT_PATH, MAXIMUM_JSON_BYTES)
    require(
        strict_json(legacy, permit_raw, PERMIT_PATH) == permit,
        "E_PERMIT_VALIDATION",
        "preflight",
    )
    runner_raw_sha256 = sha256_bytes(
        read_stable_source(THIS_RUNNER_PATH, MAXIMUM_TOOL_BYTES)
    )
    validate_permit(
        permit,
        recovery=recovery,
        runner_raw_sha256=runner_raw_sha256,
    )
    checker_source = permit_authority["sourceDecision"]
    checker_recovery = permit_authority["recoveryDecision"]
    require(
        checker_source == source
        and checker_recovery == recovery
        and validate_exact_tuples(checker_source) == tuples,
        "E_PERMIT_VALIDATION",
        "preflight",
    )
    return {
        "legacy": legacy,
        "v2": v2,
        "recovery": recovery,
        "source": source,
        "tuples": tuples,
        "permit": permit,
        "permitRawSha256": sha256_bytes(permit_raw),
        "repositoryRootIdentity": permit_authority[
            "repositoryRootIdentity"
        ],
        "recoveryCleanCheckDeferred": recovery_clean_check_deferred,
    }


def derive_mod_url(item: Mapping[str, Any]) -> str:
    url = item.get("url")
    require(
        isinstance(url, str)
        and url.endswith(".zip")
        and url.count(".zip") >= 1,
        "E_MOD_URL",
        "mod",
        tuple_id=str(item.get("tupleId") or "") or None,
        tuple_order=(
            item.get("order") if safe_integer(item.get("order")) else None
        ),
        resource_kind="mod",
    )
    mod_url = url[:-4] + ".mod"
    parsed = urlsplit(mod_url)
    require(
        parsed.scheme == "https"
        and parsed.hostname == "proxy.golang.org"
        and parsed.port is None
        and parsed.username is None
        and parsed.password is None
        and parsed.query == ""
        and parsed.fragment == ""
        and parsed.path.endswith(".mod"),
        "E_MOD_URL",
        "mod",
        tuple_id=str(item.get("tupleId") or "") or None,
        tuple_order=(
            item.get("order") if safe_integer(item.get("order")) else None
        ),
        resource_kind="mod",
    )
    return mod_url


def output_names(item: Mapping[str, Any]) -> tuple[str, str]:
    order = item.get("order")
    tuple_sha256 = item.get("tupleSha256")
    require(
        safe_integer(order)
        and 1 <= order <= EXPECTED_TUPLE_COUNT
        and isinstance(tuple_sha256, str)
        and len(tuple_sha256) == 64
        and all(character in "0123456789abcdef" for character in tuple_sha256),
        "E_PATH",
        "preflight",
    )
    stem = f"{order:03d}-{tuple_sha256[:20]}"
    return f"{stem}.mod", f"{stem}.zip"


def validate_mod_bytes(
    payload: bytes,
    item: Mapping[str, Any],
    legacy: types.ModuleType | None = None,
) -> dict[str, Any]:
    tuple_id = str(item["tupleId"])
    tuple_order = int(item["order"])
    require(
        isinstance(payload, bytes)
        and 0 < len(payload) <= MAXIMUM_MOD_BYTES
        and b"\x00" not in payload,
        "E_GO_MOD_ENCODING",
        "mod",
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind="mod",
    )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RunnerFailure(
            "E_GO_MOD_ENCODING",
            "mod",
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind="mod",
        ) from error
    directives: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "module" or line.startswith("module "):
            value = line[len("module") :].strip()
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            directives.append(value)
    require(
        directives == [item["module"]],
        "E_GO_MOD_MODULE",
        "mod",
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind="mod",
    )
    if legacy is None:
        import base64

        file_digest = hashlib.sha256(payload).hexdigest()
        aggregate = hashlib.sha256()
        aggregate.update(file_digest.encode("ascii"))
        aggregate.update(b"  go.mod\n")
        go_mod_h1 = "h1:" + base64.b64encode(aggregate.digest()).decode("ascii")
    else:
        go_mod_h1 = legacy.single_go_mod_h1(payload)
    require(
        go_mod_h1 == item["goModH1"],
        "E_GO_MOD_H1",
        "mod",
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind="mod",
    )
    return {
        "goModH1": go_mod_h1,
        "module": directives[0],
        "rawByteSize": len(payload),
        "nulBytePresent": False,
        "utf8Valid": True,
    }


def convert_legacy_failure(
    legacy: types.ModuleType,
    error: Exception,
    *,
    tuple_id: str | None,
    tuple_order: int | None,
    resource_kind: str | None,
    phase: str,
) -> RunnerFailure:
    if isinstance(error, RunnerFailure):
        return RunnerFailure(
            (
                error.code
                if error.code in ALLOWED_FAILURE_CODES
                else "E_INTERNAL"
            ),
            (
                error.phase
                if error.phase in ALLOWED_FAILURE_PHASES
                else phase
            ),
            tuple_id=error.tuple_id or tuple_id,
            tuple_order=(
                error.tuple_order
                if error.tuple_order is not None
                else tuple_order
            ),
            resource_kind=error.resource_kind or resource_kind,
            observations=bounded_observations(error.observations),
        )
    if isinstance(error, legacy.AcquisitionFailure):
        code = str(getattr(error, "code", "E_INTERNAL"))
        observations = bounded_observations(
            getattr(error, "observations", {}) or {}
        )
        return RunnerFailure(
            code if code in ALLOWED_FAILURE_CODES else "E_INTERNAL",
            phase if phase in ALLOWED_FAILURE_PHASES else "execution",
            tuple_id=getattr(error, "tuple_id", None) or tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
            observations=observations,
        )
    return RunnerFailure(
        "E_INTERNAL",
        "execution",
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )


def inspect_module_zip_v3(
    legacy: types.ModuleType,
    fd: int,
    item: Mapping[str, Any],
    limits: Mapping[str, Any],
    *,
    aggregate_entries_before: int,
    aggregate_uncompressed_before: int,
    external_go_mod: bytes,
) -> dict[str, Any]:
    tuple_id = str(item["tupleId"])
    tuple_order = int(item["order"])
    try:
        info = legacy.validate_regular_descriptor(
            fd,
            tuple_id,
            owner_only=True,
        )
        os.lseek(fd, 0, os.SEEK_SET)
        expected_prefix = f"{item['module']}@{item['version']}/"
        rows: list[tuple[str, str]] = []
        names: set[str] = set()
        folded: set[str] = set()
        embedded_go_mod: bytes | None = None
        total_uncompressed = 0
        best_ordinal = 0
        best_uncompressed = 0
        best_compressed = 0
        with os.fdopen(os.dup(fd), "rb") as archive_file:
            with zipfile.ZipFile(archive_file, "r") as archive:
                infos = archive.infolist()
                require(
                    0 < len(infos) <= limits["maximumEntriesPerArchive"],
                    "E_ZIP_ENTRY_COUNT",
                    "zip",
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="zip",
                )
                require(
                    aggregate_entries_before + len(infos)
                    <= limits["maximumAggregateEntries"],
                    "E_AGGREGATE_ENTRY_COUNT",
                    "zip",
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="zip",
                )
                central_directory_offset = legacy.validate_eocd(
                    fd,
                    info.st_size,
                    len(infos),
                    limits["maximumCentralDirectoryBytesPerArchive"],
                )
                entries_by_offset = sorted(
                    infos,
                    key=lambda value: value.header_offset,
                )
                offsets = [entry.header_offset for entry in entries_by_offset]
                require(
                    len(set(offsets)) == len(offsets)
                    and all(
                        type(offset) is int
                        and 0 <= offset < central_directory_offset
                        for offset in offsets
                    ),
                    "E_ZIP_LOCAL_HEADER",
                    "zip",
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="zip",
                )
                next_offset = {
                    entry.header_offset: (
                        entries_by_offset[index + 1].header_offset
                        if index + 1 < len(entries_by_offset)
                        else central_directory_offset
                    )
                    for index, entry in enumerate(entries_by_offset)
                }
                for ordinal, entry in enumerate(infos, start=1):
                    name = entry.filename
                    legacy.validate_zip_name(
                        name,
                        expected_prefix=expected_prefix,
                        limits=limits,
                    )
                    require(
                        name not in names,
                        "E_ZIP_DUPLICATE",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    names.add(name)
                    folded_name = legacy.unicodedata.normalize(
                        "NFC",
                        name,
                    ).casefold()
                    require(
                        folded_name not in folded,
                        "E_ZIP_CASE_COLLISION",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    folded.add(folded_name)
                    require(
                        not entry.is_dir()
                        and entry.flag_bits & 0x1 == 0
                        and entry.flag_bits & ~legacy.ALLOWED_ZIP_FLAGS == 0,
                        (
                            "E_ZIP_DIRECTORY_ENTRY"
                            if entry.is_dir()
                            else "E_ZIP_FLAGS"
                        ),
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    if not (entry.flag_bits & 0x0800):
                        require(
                            name.isascii(),
                            "E_ZIP_NAME_ENCODING",
                            "zip",
                            tuple_id=tuple_id,
                            tuple_order=tuple_order,
                            resource_kind="zip",
                        )
                    require(
                        entry.compress_type in legacy.ALLOWED_COMPRESSION_METHODS,
                        "E_ZIP_COMPRESSION",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    require(
                        entry.create_system in {0, 3},
                        "E_ZIP_CREATOR_SYSTEM",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    legacy.parse_extra_fields(entry.extra)
                    legacy.validate_local_header(
                        fd,
                        entry,
                        next_offset=next_offset[entry.header_offset],
                    )
                    require(
                        not entry.comment,
                        "E_ZIP_COMMENT",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    require(
                        0 <= entry.file_size
                        <= limits["maximumSingleFileBytes"],
                        "E_ZIP_FILE_SIZE",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    if entry.file_size:
                        require(
                            entry.compress_size > 0,
                            "E_ZIP_COMPRESSED_SIZE",
                            "zip",
                            tuple_id=tuple_id,
                            tuple_order=tuple_order,
                            resource_kind="zip",
                        )
                        if (
                            best_ordinal == 0
                            or entry.file_size * best_compressed
                            > best_uncompressed * entry.compress_size
                        ):
                            best_ordinal = ordinal
                            best_uncompressed = entry.file_size
                            best_compressed = entry.compress_size
                    mode = (entry.external_attr >> 16) & 0xFFFF
                    if entry.create_system == 3 and mode:
                        require(
                            mode & legacy.UNIX_TYPE_MASK
                            in {0, legacy.UNIX_REGULAR},
                            "E_ZIP_SPECIAL_FILE",
                            "zip",
                            tuple_id=tuple_id,
                            tuple_order=tuple_order,
                            resource_kind="zip",
                        )
                        require(
                            mode & legacy.UNIX_SPECIAL_PERMISSION_BITS == 0,
                            "E_ZIP_SPECIAL_MODE",
                            "zip",
                            tuple_id=tuple_id,
                            tuple_order=tuple_order,
                            resource_kind="zip",
                        )
                    elif entry.create_system == 0:
                        require(
                            entry.external_attr & legacy.DOS_DIRECTORY == 0,
                            "E_ZIP_SPECIAL_FILE",
                            "zip",
                            tuple_id=tuple_id,
                            tuple_order=tuple_order,
                            resource_kind="zip",
                        )
                    digest = hashlib.sha256()
                    chunks: list[bytes] | None = (
                        []
                        if name == expected_prefix + "go.mod"
                        else None
                    )
                    observed = 0
                    with archive.open(entry, "r") as source:
                        while True:
                            chunk = source.read(
                                min(
                                    STREAM_CHUNK_BYTES,
                                    limits["maximumSingleFileBytes"]
                                    + 1
                                    - observed,
                                )
                            )
                            if not chunk:
                                break
                            observed += len(chunk)
                            require(
                                observed <= limits["maximumSingleFileBytes"],
                                "E_ZIP_FILE_SIZE",
                                "zip",
                                tuple_id=tuple_id,
                                tuple_order=tuple_order,
                                resource_kind="zip",
                            )
                            total_uncompressed += len(chunk)
                            require(
                                total_uncompressed
                                <= limits[
                                    "maximumUncompressedBytesPerArchive"
                                ],
                                "E_ZIP_UNCOMPRESSED",
                                "zip",
                                tuple_id=tuple_id,
                                tuple_order=tuple_order,
                                resource_kind="zip",
                            )
                            require(
                                aggregate_uncompressed_before
                                + total_uncompressed
                                <= limits["maximumAggregateUncompressedBytes"],
                                "E_AGGREGATE_UNCOMPRESSED",
                                "zip",
                                tuple_id=tuple_id,
                                tuple_order=tuple_order,
                                resource_kind="zip",
                            )
                            digest.update(chunk)
                            if chunks is not None:
                                chunks.append(chunk)
                    require(
                        observed == entry.file_size,
                        "E_ZIP_FILE_SIZE",
                        "zip",
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind="zip",
                    )
                    rows.append((name, digest.hexdigest()))
                    if chunks is not None:
                        require(
                            embedded_go_mod is None,
                            "E_GO_MOD_DUPLICATE",
                            "zip",
                            tuple_id=tuple_id,
                            tuple_order=tuple_order,
                            resource_kind="zip",
                        )
                        embedded_go_mod = b"".join(chunks)
        module_h1 = legacy.dirhash_h1(rows)
        require(
            module_h1 == item["moduleZipH1"],
            "E_MODULE_H1",
            "zip",
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind="zip",
        )
        require(
            embedded_go_mod is None or embedded_go_mod == external_go_mod,
            "E_GO_MOD_PARITY",
            "zip",
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind="zip",
        )
        return {
            "moduleZipH1": module_h1,
            "entryCount": len(rows),
            "uncompressedByteCount": total_uncompressed,
            "modulePrefix": expected_prefix,
            "embeddedGoModPresent": embedded_go_mod is not None,
            "embeddedGoModByteParity": True,
            "compressionTelemetry": {
                "policy": "non_gating_bounded_telemetry",
                "maximumRatioEntryOrdinal": best_ordinal,
                "maximumRatioEntryUncompressedBytes": best_uncompressed,
                "maximumRatioEntryCompressedBytes": best_compressed,
                "floatingPointRatioUsed": False,
                "entryNameOrBodyRecorded": False,
            },
        }
    except RunnerFailure:
        raise
    except Exception as error:
        converted = convert_legacy_failure(
            legacy,
            error,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind="zip",
            phase="zip",
        )
        if converted.code == "E_INTERNAL" and isinstance(
            error,
            (OSError, RuntimeError, zipfile.BadZipFile),
        ):
            converted = RunnerFailure(
                "E_ZIP_FORMAT",
                "zip",
                tuple_id=tuple_id,
                tuple_order=tuple_order,
                resource_kind="zip",
            )
        raise converted from None


def zero_counters() -> dict[str, int]:
    return {name: 0 for name in COUNTER_NAMES}


def validate_counters(
    counters: Mapping[str, int],
    maximum: int = EXPECTED_RESOURCE_COUNT,
) -> None:
    require(
        set(counters) == set(COUNTER_NAMES)
        and all(safe_integer(counters[name]) for name in COUNTER_NAMES),
        "E_COUNTER_INVARIANT",
        "execution",
    )
    attempt = counters["networkRequestAttemptCount"]
    response = counters["responseBodyCompletedCount"]
    resource = counters["validatedAndStagedResourceCount"]
    mod = counters["validatedModResourceCount"]
    zip_count = counters["validatedZipResourceCount"]
    tuples = counters["validatedAndStagedTupleCount"]
    require(
        0 <= tuples <= min(mod, zip_count)
        and tuples == zip_count
        and mod in {zip_count, zip_count + 1}
        and resource == mod + zip_count
        and resource <= response <= attempt <= maximum,
        "E_COUNTER_INVARIANT",
        "execution",
    )


class AttemptCountingOpener:
    def __init__(self, delegate: Any, counters: dict[str, int]) -> None:
        self.delegate = delegate
        self.counters = counters

    def open(self, request: Any, *, timeout: float) -> Any:
        self.counters["networkRequestAttemptCount"] += 1
        validate_counters(self.counters)
        return self.delegate.open(request, timeout=timeout)


def exact_header_values(headers: Any, name: str) -> list[str]:
    try:
        values = headers.get_all(name, [])
    except (AttributeError, TypeError):
        values = []
    return [str(value) for value in values]


def validate_response_headers_v3(
    response: Any,
    *,
    expected_url: str,
    resource_kind: str,
    maximum_bytes: int,
    tuple_id: str,
    tuple_order: int,
) -> int | None:
    require(
        getattr(response, "status", None) == 200,
        "E_HTTP_STATUS",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
        observations={
            "httpStatus": int(getattr(response, "status", 0) or 0)
        },
    )
    require(
        response.geturl() == expected_url,
        "E_REDIRECT",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )
    headers = response.headers
    for forbidden in (
        "Location",
        "WWW-Authenticate",
        "Proxy-Authenticate",
        "Set-Cookie",
    ):
        require(
            not exact_header_values(headers, forbidden),
            "E_FORBIDDEN_RESPONSE_HEADER",
            resource_kind,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
        )
    encodings = exact_header_values(headers, "Content-Encoding")
    require(
        len(encodings) <= 1
        and (not encodings or encodings[0].lower() == "identity"),
        "E_CONTENT_ENCODING",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )
    content_types = exact_header_values(headers, "Content-Type")
    allowed_types = (
        {"text/plain", "application/octet-stream"}
        if resource_kind == "mod"
        else {"application/zip", "application/octet-stream"}
    )
    media_type = (
        content_types[0].split(";", 1)[0].strip().lower()
        if len(content_types) == 1
        else ""
    )
    require(
        len(content_types) == 1 and media_type in allowed_types,
        "E_CONTENT_TYPE",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )
    lengths = exact_header_values(headers, "Content-Length")
    require(
        len(lengths) <= 1,
        "E_CONTENT_LENGTH",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )
    if not lengths:
        return None
    require(
        lengths[0].isdigit(),
        "E_CONTENT_LENGTH",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )
    length = int(lengths[0])
    require(
        0 < length <= maximum_bytes,
        "E_CONTENT_LENGTH",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )
    return length


def download_resource_once(
    legacy: types.ModuleType,
    opener: Any,
    item: Mapping[str, Any],
    output_fd: int,
    *,
    resource_kind: str,
    url: str,
    maximum_bytes: int,
    aggregate_kind_before: int,
    maximum_aggregate_kind_bytes: int,
    aggregate_total_before: int,
    per_request_timeout_seconds: float,
    wave_deadline: float,
) -> dict[str, Any]:
    tuple_id = str(item["tupleId"])
    tuple_order = int(item["order"])
    require(
        resource_kind in RESOURCE_KINDS,
        "E_INTERNAL",
        "execution",
    )
    accept = "text/plain" if resource_kind == "mod" else "application/zip"
    request = Request(
        url,
        method="GET",
        headers={
            "Accept": accept,
            "Accept-Encoding": "identity",
            "User-Agent": "AetherLink-G2-Dependency-Source-Intake/3",
        },
    )
    digest = hashlib.sha256()
    total = 0
    request_deadline = time.monotonic() + per_request_timeout_seconds
    try:
        with legacy.hard_wall_clock_request_deadline(
            request_deadline=request_deadline,
            wave_deadline=wave_deadline,
            tuple_id=tuple_id,
            phase=resource_kind,
        ):
            timeout = min(request_deadline, wave_deadline) - time.monotonic()
            require(
                timeout > 0,
                "E_REQUEST_DEADLINE",
                resource_kind,
                tuple_id=tuple_id,
                tuple_order=tuple_order,
                resource_kind=resource_kind,
            )
            with closing(opener.open(request, timeout=timeout)) as response:
                declared = validate_response_headers_v3(
                    response,
                    expected_url=url,
                    resource_kind=resource_kind,
                    maximum_bytes=maximum_bytes,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                )
                read_one = getattr(response, "read1", None)
                require(
                    callable(read_one),
                    "E_TRANSPORT",
                    resource_kind,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind=resource_kind,
                )
                while True:
                    now = time.monotonic()
                    require(
                        now < wave_deadline,
                        "E_WAVE_DEADLINE",
                        resource_kind,
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind=resource_kind,
                    )
                    require(
                        now < request_deadline,
                        "E_REQUEST_DEADLINE",
                        resource_kind,
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind=resource_kind,
                    )
                    legacy.set_response_io_timeout(
                        response,
                        min(wave_deadline, request_deadline) - now,
                    )
                    chunk = read_one(
                        min(STREAM_CHUNK_BYTES, maximum_bytes + 1 - total)
                    )
                    if not chunk:
                        break
                    total += len(chunk)
                    require(
                        total <= maximum_bytes,
                        "E_RESPONSE_TOO_LARGE",
                        resource_kind,
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind=resource_kind,
                        observations={"responseBytes": total},
                    )
                    require(
                        aggregate_kind_before + total
                        <= maximum_aggregate_kind_bytes,
                        (
                            "E_AGGREGATE_MOD_TOO_LARGE"
                            if resource_kind == "mod"
                            else "E_AGGREGATE_ZIP_TOO_LARGE"
                        ),
                        resource_kind,
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind=resource_kind,
                        observations={
                            (
                                "aggregateModBytes"
                                if resource_kind == "mod"
                                else "aggregateZipBytes"
                            ): aggregate_kind_before + total
                        },
                    )
                    require(
                        aggregate_total_before + total
                        <= MAXIMUM_AGGREGATE_RESPONSE_BYTES,
                        "E_AGGREGATE_RESPONSE_TOO_LARGE",
                        resource_kind,
                        tuple_id=tuple_id,
                        tuple_order=tuple_order,
                        resource_kind=resource_kind,
                        observations={
                            "aggregateResponseBytes": (
                                aggregate_total_before + total
                            )
                        },
                    )
                    legacy.write_all(output_fd, chunk)
                    digest.update(chunk)
                require(
                    declared is None or declared == total,
                    "E_CONTENT_LENGTH_MISMATCH",
                    resource_kind,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind=resource_kind,
                    observations={"responseBytes": total},
                )
    except RunnerFailure:
        raise
    except HTTPError as error:
        raise RunnerFailure(
            "E_HTTP_STATUS",
            resource_kind,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
            observations={"httpStatus": int(error.code)},
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise RunnerFailure(
            "E_TRANSPORT",
            resource_kind,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
        ) from error
    require(
        total > 0,
        "E_EMPTY_RESPONSE",
        resource_kind,
        tuple_id=tuple_id,
        tuple_order=tuple_order,
        resource_kind=resource_kind,
    )
    os.fsync(output_fd)
    legacy.validate_regular_descriptor(output_fd, tuple_id, owner_only=True)
    return {"rawByteSize": total, "rawSha256": digest.hexdigest()}


def read_exact_held_file(
    legacy: types.ModuleType,
    fd: int,
    expected_size: int,
    *,
    maximum_bytes: int,
) -> bytes:
    require(
        safe_integer(expected_size)
        and 0 < expected_size <= maximum_bytes,
        "E_OUTPUT_IDENTITY",
        "publication",
    )
    before = legacy.validate_regular_descriptor(
        fd,
        "held resource",
        owner_only=True,
    )
    require(before.st_size == expected_size, "E_OUTPUT_IDENTITY", "publication")
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while total <= expected_size:
        chunk = os.read(
            fd,
            min(STREAM_CHUNK_BYTES, expected_size + 1 - total),
        )
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    after = legacy.validate_regular_descriptor(
        fd,
        "held resource",
        owner_only=True,
    )
    require(
        total == expected_size
        and legacy.regular_file_content_state(before)
        == legacy.regular_file_content_state(after),
        "E_OUTPUT_IDENTITY",
        "publication",
    )
    return b"".join(chunks)


def validate_held_output_inventory_v3(
    legacy: types.ModuleType,
    directory_fd: int,
    held_outputs: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    items: Sequence[Mapping[str, Any]],
    limits: Mapping[str, Any],
) -> None:
    require(
        len(held_outputs) == EXPECTED_RESOURCE_COUNT
        and len(rows) == EXPECTED_TUPLE_COUNT
        and len(items) == EXPECTED_TUPLE_COUNT,
        "E_OUTPUT_INVENTORY",
        "publication",
    )
    names = [record.get("name") for record in held_outputs]
    require(
        len(set(names)) == EXPECTED_RESOURCE_COUNT
        and legacy.list_names(directory_fd) == sorted(names),
        "E_OUTPUT_INVENTORY",
        "publication",
    )
    by_name = {str(record["name"]): record for record in held_outputs}
    reopened: list[int] = []
    stable_states: list[tuple[int, str, tuple[int, ...]]] = []
    try:
        for name in sorted(names):
            record = by_name[str(name)]
            fd = os.open(
                str(name),
                legacy.file_open_flags(),
                dir_fd=directory_fd,
            )
            reopened.append(fd)
            legacy.named_entry_matches_open_file(
                directory_fd,
                str(name),
                fd,
                expected_link_count=1,
            )
            raw = read_exact_held_file(
                legacy,
                fd,
                int(record["rawByteSize"]),
                maximum_bytes=(
                    MAXIMUM_MOD_BYTES
                    if record["resourceKind"] == "mod"
                    else MAXIMUM_ZIP_BYTES
                ),
            )
            require(
                sha256_bytes(raw) == record["rawSha256"],
                "E_OUTPUT_IDENTITY",
                "publication",
            )
            stable_states.append(
                (
                    fd,
                    str(name),
                    legacy.regular_file_content_state(os.fstat(fd)),
                )
            )
        aggregate_entries = 0
        aggregate_uncompressed = 0
        for item, row in zip(items, rows):
            mod_record = by_name[row["modOutputFileName"]]
            zip_record = by_name[row["zipOutputFileName"]]
            mod_raw = read_exact_held_file(
                legacy,
                int(mod_record["fd"]),
                int(mod_record["rawByteSize"]),
                maximum_bytes=MAXIMUM_MOD_BYTES,
            )
            mod_validation = validate_mod_bytes(mod_raw, item, legacy)
            archive = inspect_module_zip_v3(
                legacy,
                int(zip_record["fd"]),
                item,
                limits,
                aggregate_entries_before=aggregate_entries,
                aggregate_uncompressed_before=aggregate_uncompressed,
                external_go_mod=mod_raw,
            )
            require(
                mod_validation["goModH1"] == row["goModH1"]
                and archive["moduleZipH1"] == row["moduleZipH1"]
                and archive["entryCount"] == row["entryCount"]
                and archive["uncompressedByteCount"]
                == row["uncompressedByteCount"]
                and archive["embeddedGoModPresent"]
                == row["embeddedGoModPresent"]
                and archive["embeddedGoModByteParity"] is True,
                "E_OUTPUT_IDENTITY",
                "publication",
            )
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
        for fd, name, expected_state in stable_states:
            require(
                legacy.regular_file_content_state(os.fstat(fd))
                == expected_state,
                "E_TOCTOU",
                "publication",
            )
            legacy.named_entry_matches_open_file(
                directory_fd,
                name,
                fd,
                expected_link_count=1,
            )
    finally:
        for fd in reopened:
            legacy.close_quietly(fd)


def create_claim_v3(
    legacy: types.ModuleType,
    parent_fd: int,
    permit: Mapping[str, Any],
) -> str:
    payload = canonical_json_bytes(
        {
            "claimType": (
                "aetherlink.g2-pion-dependency-wave1-v3-one-use-claim"
            ),
            "schemaVersion": "3.0",
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "recoveryDecisionId": EXPECTED_RECOVERY_DECISION_ID,
            "recoveryContentSha256": EXPECTED_RECOVERY_CONTENT_SHA256,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rule": (
                "v3_claim_persists_after_any_network_attempt_and_blocks_retry"
            ),
            "v1OrV2ArtifactReuseAllowed": False,
        }
    )
    return legacy.create_exclusive_file(
        parent_fd,
        CLAIM_NAME,
        payload,
        maximum_bytes=64 * 1024,
    )


def ordered_source_set_digest_v3(rows: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(list(rows)))


def safe_failure_document_v3(
    permit: Mapping[str, Any],
    failure: RunnerFailure,
    counters: Mapping[str, int],
    *,
    claim_sha256: str,
) -> dict[str, Any]:
    validate_counters(counters)
    require(
        failure.code in ALLOWED_FAILURE_CODES
        and failure.phase in ALLOWED_FAILURE_PHASES
        and failure.resource_kind in RESOURCE_KINDS
        and isinstance(failure.tuple_id, str)
        and bool(failure.tuple_id)
        and safe_integer(failure.tuple_order)
        and int(failure.tuple_order) > 0
        and len(claim_sha256) == 64,
        "E_FAILURE_STATE",
        "execution",
    )
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v3-acquisition-failure"
        ),
        "schemaVersion": "3.0",
        "status": "wave1_v3_acquisition_failed_permit_consumed",
        "result": "no_dependency_source_set_accepted",
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "recoveryDecisionId": EXPECTED_RECOVERY_DECISION_ID,
        "recoveryContentSha256": EXPECTED_RECOVERY_CONTENT_SHA256,
        "failureCode": failure.code,
        "phase": failure.phase,
        "failedTupleId": failure.tuple_id,
        "failedTupleOrder": failure.tuple_order,
        "failedResourceKind": failure.resource_kind,
        "safeNumericObservations": bounded_observations(failure.observations),
        **{name: counters[name] for name in COUNTER_NAMES},
        "acceptedArtifactCount": 0,
        "acceptedTupleCount": 0,
        "claimRetained": True,
        "claimRawSha256": claim_sha256,
        "finalSetPublished": False,
        "automaticRetryAllowed": False,
        "legacyCompletedRequestCountForbidden": True,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "prepare_new_versioned_wave1_v3_recovery_decision",
    }


def classify_preflight_state(state: Mapping[str, Any]) -> str:
    invalid = state["dependencyParentInvalid"] or state["waveParentInvalid"]
    clean = (
        not invalid
        and not state["claimPresent"]
        and state["stagingEntryCount"] == 0
        and not state["finalDirectoryPresent"]
        and not state["successReceiptPresent"]
        and not state["failureReceiptPresent"]
        and not state["manifestPresent"]
    )
    success = (
        not invalid
        and state["claimPresent"]
        and state["stagingEntryCount"] == 0
        and state["finalDirectoryPresent"]
        and state["successReceiptPresent"]
        and not state["failureReceiptPresent"]
        and state["manifestPresent"]
    )
    failure = (
        not invalid
        and state["claimPresent"]
        and state["stagingEntryCount"] == 0
        and not state["finalDirectoryPresent"]
        and not state["successReceiptPresent"]
        and state["failureReceiptPresent"]
        and not state["manifestPresent"]
    )
    if clean:
        return "clean"
    if success:
        return "success"
    if failure:
        return "failure"
    return "blocked"


def validate_terminal_state(
    legacy: types.ModuleType,
    permit: Mapping[str, Any],
    state: Mapping[str, Any],
    classification: str,
    items: Sequence[Mapping[str, Any]],
) -> None:
    if classification == "clean":
        return
    require(
        classification in {"success", "failure"},
        "E_ONE_USE_STATE_PRESENT",
        "preflight",
    )
    claim_raw = legacy.read_stable_regular_file(
        ROOT / str(DEPENDENCY_PARENT) / CLAIM_NAME,
        64 * 1024,
    )
    claim = strict_json(legacy, claim_raw, CLAIM_NAME)
    require(
        claim.get("claimType")
        == "aetherlink.g2-pion-dependency-wave1-v3-one-use-claim"
        and claim.get("schemaVersion") == "3.0"
        and claim.get("permitId") == permit["permitId"]
        and claim.get("permitContentSha256")
        == permit["contentBinding"]["sha256"]
        and claim.get("recoveryContentSha256")
        == EXPECTED_RECOVERY_CONTENT_SHA256
        and claim.get("v1OrV2ArtifactReuseAllowed") is False
        and len(sha256_bytes(claim_raw)) == 64,
        "E_CLAIM_STATE",
        "preflight",
    )
    artifact_path = (
        FAILURE_RECEIPT_PATH
        if classification == "failure"
        else SUCCESS_RECEIPT_PATH
    )
    artifact_raw = legacy.read_stable_regular_file(
        ROOT / artifact_path,
        MAXIMUM_JSON_BYTES,
    )
    artifact = strict_json(legacy, artifact_raw, artifact_path)
    claim_sha256 = sha256_bytes(claim_raw)
    require(
        artifact.get("schemaVersion") == "3.0"
        and artifact.get("permitId") == permit["permitId"]
        and artifact.get("permitContentSha256")
        == permit["contentBinding"]["sha256"]
        and artifact.get("claimRawSha256") == claim_sha256,
        "E_FAILURE_STATE" if classification == "failure" else "E_OUTPUT_IDENTITY",
        "preflight",
    )
    if classification == "failure":
        counters = {name: artifact.get(name) for name in COUNTER_NAMES}
        validate_counters(counters)
        require(
            artifact.get("acceptedArtifactCount") == 0
            and artifact.get("acceptedTupleCount") == 0
            and artifact.get("finalSetPublished") is False
            and artifact.get("automaticRetryAllowed") is False
            and artifact.get("failedResourceKind") in RESOURCE_KINDS,
            "E_FAILURE_STATE",
            "preflight",
        )
    else:
        require(
            [artifact.get(name) for name in COUNTER_NAMES]
            == [38, 38, 38, 19, 19, 19]
            and artifact.get("acceptedArtifactCount") == 38
            and artifact.get("acceptedTupleCount") == 19,
            "E_OUTPUT_INVENTORY",
            "preflight",
        )
        manifest_raw = legacy.read_stable_regular_file(
            ROOT / MANIFEST_PATH,
            MAXIMUM_JSON_BYTES,
        )
        manifest = strict_json(legacy, manifest_raw, MANIFEST_PATH)
        require(
            manifest.get("schemaVersion") == "3.0"
            and manifest.get("permitId") == permit["permitId"]
            and manifest.get("successReceiptPath") == SUCCESS_RECEIPT_PATH
            and manifest.get("successReceiptRawSha256")
            == sha256_bytes(artifact_raw)
            and manifest.get("finalDirectoryPath") == FINAL_DIRECTORY_PATH
            and manifest.get("manifestWrittenLast") is True
            and [manifest.get(name) for name in COUNTER_NAMES]
            == [38, 38, 38, 19, 19, 19]
            and manifest.get("acceptedArtifactCount") == 38
            and manifest.get("acceptedTupleCount") == 19,
            "E_OUTPUT_INVENTORY",
            "preflight",
        )
        final_fd = -1
        opened: list[int] = []
        try:
            final_fd = os.open(
                ROOT / FINAL_DIRECTORY_PATH,
                legacy.directory_open_flags(),
            )
            legacy.validate_directory_descriptor(
                final_fd,
                FINAL_DIRECTORY_NAME,
                owner_only=True,
            )
            expected_names = sorted(
                name
                for item in items
                for name in output_names(item)
            )
            require(
                legacy.list_names(final_fd) == expected_names,
                "E_OUTPUT_INVENTORY",
                "preflight",
            )
            for name in expected_names:
                fd = os.open(name, legacy.file_open_flags(), dir_fd=final_fd)
                opened.append(fd)
                legacy.validate_regular_descriptor(
                    fd,
                    name,
                    owner_only=True,
                )
        finally:
            for fd in opened:
                legacy.close_quietly(fd)
            legacy.close_quietly(final_fd)


def preflight() -> dict[str, Any]:
    authority = load_validated_authority()
    legacy = authority["legacy"]
    permit = authority["permit"]
    legacy.validate_hard_deadline_environment()
    root_fd = legacy.open_root_directory(authority["repositoryRootIdentity"])
    try:
        state = legacy.inspect_one_use_state(root_fd)
    finally:
        os.close(root_fd)
    classification = classify_preflight_state(state)
    validate_terminal_state(
        legacy,
        permit,
        state,
        classification,
        authority["tuples"],
    )
    if classification == "clean":
        status = "passed"
        consumption = "authorized_not_consumed"
        next_action = EXPECTED_PERMIT_NEXT_ACTION
    elif classification == "success":
        status = "consumed_success_pending_independent_readback"
        consumption = "consumed_success"
        next_action = "run_separate_wave1_v3_independent_readback"
    else:
        status = "consumed_failed_recovery_required"
        consumption = "consumed_failure"
        next_action = "prepare_new_versioned_wave1_v3_recovery_decision"
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v3-runner-preflight"
        ),
        "schemaVersion": "3.0",
        "status": status,
        "validationPassed": classification in {"clean", "success"},
        "terminalStateSchemaValid": classification in {"success", "failure"},
        "permitId": permit["permitId"],
        **zero_counters(),
        "fileWriteCount": 0,
        "networkOperationCount": 0,
        "observedOneUseArtifactCount": legacy.one_use_artifact_count(state),
        "permitConsumptionState": consumption,
        "oneUseState": state,
        "recoveryCleanNamespaceCheckDeferred": authority[
            "recoveryCleanCheckDeferred"
        ],
        "expectedAcquisitionRegularFileCount": (
            EXPECTED_ACQUISITION_REGULAR_FILE_COUNT
        ),
        "legacyCompletedRequestCountForbidden": True,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": next_action,
    }


def enforce_download_file_mode(
    output_fd: int,
    *,
    tuple_id: str,
    tuple_order: int,
    resource_kind: str,
) -> None:
    try:
        os.fchmod(output_fd, 0o600)
    except OSError as error:
        raise RunnerFailure(
            "E_FILESYSTEM_MODE",
            resource_kind,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
        ) from error


def _execute_once_with_umask() -> dict[str, Any]:
    authority = load_validated_authority()
    legacy = authority["legacy"]
    permit = authority["permit"]
    items = authority["tuples"]
    source_limits = authority["source"]["resourceLimits"]
    limits = dict(source_limits)
    limits.update(
        {
            "maximumEntriesPerArchive": 16_384,
            "maximumAggregateEntries": 131_072,
            "maximumCentralDirectoryBytesPerArchive": 8 * 1024 * 1024,
            "maximumSingleFileBytes": 16 * 1024 * 1024,
            "maximumUncompressedBytesPerArchive": 256 * 1024 * 1024,
            "maximumAggregateUncompressedBytes": 1024 * 1024 * 1024,
        }
    )
    counters = zero_counters()
    root_fd = parent_fd = wave_parent_fd = staging_fd = -1
    staging_name: str | None = None
    claim_sha256: str | None = None
    claim_attempted = False
    publication_attempted = False
    held_outputs: list[dict[str, Any]] = []
    active_tuple_id = str(items[0]["tupleId"])
    active_tuple_order = int(items[0]["order"])
    active_resource_kind = "mod"
    try:
        legacy.validate_hard_deadline_environment()
        root_fd = legacy.open_root_directory(
            authority["repositoryRootIdentity"]
        )
        require(
            classify_preflight_state(legacy.inspect_one_use_state(root_fd))
            == "clean",
            "E_ONE_USE_STATE_PRESENT",
            "preflight",
        )
        parent_parts = legacy.validate_relative_path(str(DEPENDENCY_PARENT))
        parent_fd = legacy.open_directory_chain(
            root_fd,
            parent_parts,
            create=True,
            owner_only_from=len(parent_parts) - 1,
        )
        require(
            classify_preflight_state(legacy.inspect_one_use_state(root_fd))
            == "clean",
            "E_ONE_USE_STATE_PRESENT",
            "preflight",
        )
        claim_attempted = True
        claim_sha256 = create_claim_v3(legacy, parent_fd, permit)
        wave_parent_fd = legacy.open_directory_chain(
            parent_fd,
            (WAVE_PARENT_NAME,),
            create=True,
            owner_only_from=0,
        )
        staging_name = legacy.create_staging_directory(parent_fd)
        staging_fd = os.open(
            staging_name,
            legacy.directory_open_flags(),
            dir_fd=parent_fd,
        )
        legacy.validate_directory_descriptor(
            staging_fd,
            staging_name,
            owner_only=True,
        )

        opener = AttemptCountingOpener(legacy.build_exact_opener(), counters)
        wave_deadline = (
            time.monotonic() + WHOLE_WAVE_DEADLINE_MILLISECONDS / 1000
        )
        per_request_timeout = PER_REQUEST_DEADLINE_MILLISECONDS / 1000
        aggregate_mod_bytes = 0
        aggregate_zip_bytes = 0
        aggregate_entries = 0
        aggregate_uncompressed = 0
        rows: list[dict[str, Any]] = []

        for item in items:
            tuple_id = str(item["tupleId"])
            tuple_order = int(item["order"])
            active_tuple_id = tuple_id
            active_tuple_order = tuple_order
            active_resource_kind = "mod"
            mod_name, zip_name = output_names(item)
            mod_url = derive_mod_url(item)

            mod_temp = f".{tuple_order:03d}.mod.download"
            try:
                mod_fd = os.open(
                    mod_temp,
                    legacy.create_download_file_flags(),
                    0o600,
                    dir_fd=staging_fd,
                )
            except OSError as error:
                raise RunnerFailure(
                    "E_FILESYSTEM_CREATE",
                    "mod",
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="mod",
                ) from error
            keep_mod_fd = False
            try:
                enforce_download_file_mode(
                    mod_fd,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="mod",
                )
                mod_download = download_resource_once(
                    legacy,
                    opener,
                    item,
                    mod_fd,
                    resource_kind="mod",
                    url=mod_url,
                    maximum_bytes=MAXIMUM_MOD_BYTES,
                    aggregate_kind_before=aggregate_mod_bytes,
                    maximum_aggregate_kind_bytes=MAXIMUM_AGGREGATE_MOD_BYTES,
                    aggregate_total_before=(
                        aggregate_mod_bytes + aggregate_zip_bytes
                    ),
                    per_request_timeout_seconds=per_request_timeout,
                    wave_deadline=wave_deadline,
                )
                counters["responseBodyCompletedCount"] += 1
                validate_counters(counters)
                mod_raw = read_exact_held_file(
                    legacy,
                    mod_fd,
                    mod_download["rawByteSize"],
                    maximum_bytes=MAXIMUM_MOD_BYTES,
                )
                mod_validation = validate_mod_bytes(mod_raw, item, legacy)
                legacy.link_temp_to_final(
                    staging_fd,
                    mod_temp,
                    mod_name,
                    mod_fd,
                )
                held_outputs.append(
                    {
                        "fd": mod_fd,
                        "name": mod_name,
                        "resourceKind": "mod",
                        **mod_download,
                    }
                )
                keep_mod_fd = True
                counters["validatedAndStagedResourceCount"] += 1
                counters["validatedModResourceCount"] += 1
                validate_counters(counters)
            except Exception as error:
                raise convert_legacy_failure(
                    legacy,
                    error,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="mod",
                    phase="mod",
                ) from None
            finally:
                if not keep_mod_fd:
                    legacy.close_quietly(mod_fd)

            zip_temp = f".{tuple_order:03d}.zip.download"
            active_resource_kind = "zip"
            try:
                zip_fd = os.open(
                    zip_temp,
                    legacy.create_download_file_flags(),
                    0o600,
                    dir_fd=staging_fd,
                )
            except OSError as error:
                raise RunnerFailure(
                    "E_FILESYSTEM_CREATE",
                    "zip",
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="zip",
                ) from error
            keep_zip_fd = False
            try:
                enforce_download_file_mode(
                    zip_fd,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="zip",
                )
                zip_download = download_resource_once(
                    legacy,
                    opener,
                    item,
                    zip_fd,
                    resource_kind="zip",
                    url=str(item["url"]),
                    maximum_bytes=MAXIMUM_ZIP_BYTES,
                    aggregate_kind_before=aggregate_zip_bytes,
                    maximum_aggregate_kind_bytes=MAXIMUM_AGGREGATE_ZIP_BYTES,
                    aggregate_total_before=(
                        aggregate_mod_bytes + aggregate_zip_bytes
                        + mod_download["rawByteSize"]
                    ),
                    per_request_timeout_seconds=per_request_timeout,
                    wave_deadline=wave_deadline,
                )
                counters["responseBodyCompletedCount"] += 1
                validate_counters(counters)
                archive = inspect_module_zip_v3(
                    legacy,
                    zip_fd,
                    item,
                    limits,
                    aggregate_entries_before=aggregate_entries,
                    aggregate_uncompressed_before=aggregate_uncompressed,
                    external_go_mod=mod_raw,
                )
                legacy.link_temp_to_final(
                    staging_fd,
                    zip_temp,
                    zip_name,
                    zip_fd,
                )
                held_outputs.append(
                    {
                        "fd": zip_fd,
                        "name": zip_name,
                        "resourceKind": "zip",
                        **zip_download,
                    }
                )
                keep_zip_fd = True
                counters["validatedAndStagedResourceCount"] += 1
                counters["validatedZipResourceCount"] += 1
                counters["validatedAndStagedTupleCount"] += 1
                validate_counters(counters)
            except Exception as error:
                raise convert_legacy_failure(
                    legacy,
                    error,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="zip",
                    phase="zip",
                ) from None
            finally:
                if not keep_zip_fd:
                    legacy.close_quietly(zip_fd)

            aggregate_mod_bytes += mod_download["rawByteSize"]
            aggregate_zip_bytes += zip_download["rawByteSize"]
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
            rows.append(
                {
                    "order": tuple_order,
                    "tupleId": tuple_id,
                    "module": item["module"],
                    "version": item["version"],
                    "zipUrl": item["url"],
                    "modUrl": mod_url,
                    "zipOutputFileName": zip_name,
                    "modOutputFileName": mod_name,
                    "zipRawByteSize": zip_download["rawByteSize"],
                    "zipRawSha256": zip_download["rawSha256"],
                    "modRawByteSize": mod_download["rawByteSize"],
                    "modRawSha256": mod_download["rawSha256"],
                    "moduleZipH1": archive["moduleZipH1"],
                    "goModH1": mod_validation["goModH1"],
                    "entryCount": archive["entryCount"],
                    "uncompressedByteCount": archive[
                        "uncompressedByteCount"
                    ],
                    "modulePrefix": archive["modulePrefix"],
                    "embeddedGoModPresent": archive[
                        "embeddedGoModPresent"
                    ],
                    "embeddedGoModByteParity": archive[
                        "embeddedGoModByteParity"
                    ],
                    "zipMode": "0600",
                    "zipLinkCount": 1,
                    "modMode": "0600",
                    "modLinkCount": 1,
                }
            )

        validate_counters(counters)
        require(
            [counters[name] for name in COUNTER_NAMES]
            == [38, 38, 38, 19, 19, 19]
            and len(rows) == 19
            and len(held_outputs) == 38,
            "E_REQUEST_COUNT",
            "execution",
        )
        source_set_sha256 = ordered_source_set_digest_v3(rows)
        with legacy.hard_wall_clock_request_deadline(
            request_deadline=wave_deadline,
            wave_deadline=wave_deadline,
            tuple_id=None,
            phase="publication",
        ):
            validate_held_output_inventory_v3(
                legacy,
                staging_fd,
                held_outputs,
                rows,
                items,
                limits,
            )
            os.fsync(staging_fd)
        require(
            time.monotonic() < wave_deadline,
            "E_WAVE_DEADLINE",
            "publication",
        )

        publication_attempted = True
        legacy.exclusive_rename_directory(
            parent_fd,
            staging_name,
            wave_parent_fd,
            FINAL_DIRECTORY_NAME,
        )
        published_fd = os.open(
            FINAL_DIRECTORY_NAME,
            legacy.directory_open_flags(),
            dir_fd=wave_parent_fd,
        )
        try:
            legacy.validate_directory_descriptor(
                published_fd,
                FINAL_DIRECTORY_NAME,
                owner_only=True,
            )
            validate_held_output_inventory_v3(
                legacy,
                published_fd,
                held_outputs,
                rows,
                items,
                limits,
            )
        finally:
            legacy.close_quietly(published_fd)
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        held_outputs.clear()
        legacy.close_quietly(staging_fd)
        staging_fd = -1
        os.fsync(parent_fd)
        os.fsync(wave_parent_fd)

        receipt = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v3-acquisition-receipt"
            ),
            "schemaVersion": "3.0",
            "status": "acquired_pending_independent_readback",
            "result": (
                "fresh_exact_19_dependency_zip_mod_pairs_acquired_and_"
                "hash_verified"
            ),
            "permitId": permit["permitId"],
            "permitRawSha256": authority["permitRawSha256"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "recoveryDecisionId": EXPECTED_RECOVERY_DECISION_ID,
            "recoveryRawSha256": EXPECTED_RECOVERY_RAW_SHA256,
            "recoveryContentSha256": EXPECTED_RECOVERY_CONTENT_SHA256,
            "decisionId": authority["source"]["decisionId"],
            "decisionRawSha256": EXPECTED_SOURCE_DECISION_RAW_SHA256,
            "decisionContentSha256": (
                EXPECTED_SOURCE_DECISION_CONTENT_SHA256
            ),
            "claimRawSha256": claim_sha256,
            **{name: counters[name] for name in COUNTER_NAMES},
            "acceptedArtifactCount": 38,
            "acceptedTupleCount": 19,
            "aggregateModRawByteSize": aggregate_mod_bytes,
            "aggregateZipRawByteSize": aggregate_zip_bytes,
            "aggregateRawByteSize": (
                aggregate_mod_bytes + aggregate_zip_bytes
            ),
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedByteCount": aggregate_uncompressed,
            "orderedSourceSetSha256": source_set_sha256,
            "sources": rows,
            "legacyCompletedRequestCountForbidden": True,
            "independentReadbackPassed": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v3_independent_readback",
        }
        receipt_sha256 = legacy.write_repo_relative_artifact(
            root_fd,
            SUCCESS_RECEIPT_PATH,
            canonical_json_bytes(receipt),
            MAXIMUM_JSON_BYTES,
        )
        manifest = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v3-acquisition-manifest"
            ),
            "schemaVersion": "3.0",
            "status": (
                "wave1_v3_acquisition_publication_complete_pending_"
                "independent_readback"
            ),
            "result": (
                "receipt_and_fresh_exact_19_zip_mod_pairs_published_"
                "manifest_written_last"
            ),
            "permitId": permit["permitId"],
            "permitRawSha256": authority["permitRawSha256"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "recoveryRawSha256": EXPECTED_RECOVERY_RAW_SHA256,
            "recoveryContentSha256": EXPECTED_RECOVERY_CONTENT_SHA256,
            "successReceiptPath": SUCCESS_RECEIPT_PATH,
            "successReceiptRawSha256": receipt_sha256,
            "finalDirectoryPath": FINAL_DIRECTORY_PATH,
            **{name: counters[name] for name in COUNTER_NAMES},
            "acceptedArtifactCount": 38,
            "acceptedTupleCount": 19,
            "orderedSourceSetSha256": source_set_sha256,
            "manifestWrittenLast": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v3_independent_readback",
        }
        manifest_sha256 = legacy.write_repo_relative_artifact(
            root_fd,
            MANIFEST_PATH,
            canonical_json_bytes(manifest),
            MAXIMUM_JSON_BYTES,
        )
        return {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v3-runner-result"
            ),
            "schemaVersion": "3.0",
            "status": "acquired_pending_independent_readback",
            **{name: counters[name] for name in COUNTER_NAMES},
            "acceptedArtifactCount": 38,
            "acceptedTupleCount": 19,
            "orderedSourceSetSha256": source_set_sha256,
            "successReceiptRawSha256": receipt_sha256,
            "manifestRawSha256": manifest_sha256,
            "legacyCompletedRequestCountForbidden": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v3_independent_readback",
        }
    except Exception as error:
        failure = convert_legacy_failure(
            legacy,
            error,
            tuple_id=active_tuple_id,
            tuple_order=active_tuple_order,
            resource_kind=active_resource_kind,
            phase="execution",
        )
        if publication_attempted:
            failure = RunnerFailure(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
                observations=counters,
            )
        if claim_attempted and claim_sha256 is None:
            try:
                claim_raw = legacy.read_stable_regular_file(
                    ROOT / str(DEPENDENCY_PARENT) / CLAIM_NAME,
                    64 * 1024,
                )
                claim_document = strict_json(legacy, claim_raw, CLAIM_NAME)
                require(
                    claim_document.get("claimType")
                    == (
                        "aetherlink.g2-pion-dependency-wave1-v3-"
                        "one-use-claim"
                    )
                    and claim_document.get("permitId") == permit["permitId"]
                    and claim_document.get("permitContentSha256")
                    == permit["contentBinding"]["sha256"],
                    "E_CLAIM_STATE",
                    "execution",
                )
                claim_sha256 = sha256_bytes(claim_raw)
            except Exception:
                claim_sha256 = None
        if staging_fd >= 0:
            legacy.close_quietly(staging_fd)
            staging_fd = -1
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        held_outputs.clear()
        if (
            staging_name is not None
            and not publication_attempted
            and parent_fd >= 0
        ):
            try:
                legacy.remove_staging(parent_fd, staging_name)
            except Exception:
                pass
        if (
            not publication_attempted
            and claim_sha256 is not None
            and failure.resource_kind in RESOURCE_KINDS
        ):
            try:
                failure_document = safe_failure_document_v3(
                    permit,
                    failure,
                    counters,
                    claim_sha256=claim_sha256,
                )
                legacy.write_repo_relative_artifact(
                    root_fd,
                    FAILURE_RECEIPT_PATH,
                    canonical_json_bytes(failure_document),
                    MAXIMUM_JSON_BYTES,
                )
            except Exception:
                pass
        raise failure from None
    finally:
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        legacy.close_quietly(staging_fd)
        legacy.close_quietly(wave_parent_fd)
        legacy.close_quietly(parent_fd)
        legacy.close_quietly(root_fd)


def execute_once() -> dict[str, Any]:
    previous_umask = os.umask(0o077)
    try:
        return _execute_once_with_umask()
    finally:
        os.umask(previous_umask)


def runner_error_document(failure: RunnerFailure) -> dict[str, Any]:
    uncertain = failure.code == "E_POST_PUBLISH_UNCERTAIN"
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v3-runner-error"
        ),
        "schemaVersion": "3.0",
        "status": "consumed_terminal_state_uncertain" if uncertain else "failed",
        "failureCode": failure.code,
        "phase": failure.phase,
        "failedTupleId": failure.tuple_id,
        "failedTupleOrder": failure.tuple_order,
        "failedResourceKind": failure.resource_kind,
        "safeNumericObservations": bounded_observations(
            failure.observations
        ),
        "permitConsumptionState": (
            "consumed_terminal_state_uncertain"
            if uncertain
            else "inspect_v3_one_use_state_before_any_new_authority"
        ),
        "automaticRetryAllowed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": (
            "inspect_v3_terminal_state_without_retry"
            if uncertain
            else "inspect_v3_one_use_state_without_automatic_retry"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = execute_once() if args.execute else preflight()
    except RunnerFailure as failure:
        print(
            json.dumps(
                runner_error_document(failure),
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "documentType": (
                        "aetherlink.g2-pion-dependency-wave1-v3-runner-error"
                    ),
                    "schemaVersion": "3.0",
                    "status": "failed",
                    "failureCode": "E_INTERNAL",
                    "phase": "runner",
                    "failedTupleId": None,
                    "failedTupleOrder": None,
                    "failedResourceKind": None,
                    "safeNumericObservations": {},
                    "automaticRetryAllowed": False,
                    "repositoryOwnerIdentityProofRequired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    if not args.execute and not result.get("validationPassed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
