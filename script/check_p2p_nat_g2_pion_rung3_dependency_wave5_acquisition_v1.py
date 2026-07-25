#!/usr/bin/env python3
"""Validate the Wave5 identity decision and one-use acquisition permit."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("Wave5 acquisition checker requires `python3 -I -B -S`")

import argparse
import ast
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types
from typing import Any, Mapping, Sequence
import unicodedata
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave5-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave5-v1.md"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "execution-permit-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave5_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave5_decision_v1.py"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave5_acquisition_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave5_acquisition_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave5_v1_once.py"
)
RUNNER_TESTS_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave5_v1_once.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
WAVE4_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)

EXPECTED_DECISION_CHECKER_RAW = (
    "db5ef0a6477282c6a8d97d582b785f6dfbb9c9a10831456964e02981a46e8d2e"
)
EXPECTED_DECISION_TESTS_RAW = (
    "6e580c5d96f3ea5870f07ed94cdcbd6bb1736b523ee851faea3ecf8e2477e5e2"
)
EXPECTED_DECISION_RAW = (
    "fb2d6ec8e29f50e7d6198d452366cce98c4414e4d7a409634ad1daffe02d195e"
)
EXPECTED_DECISION_CONTENT = (
    "042360fe15b03240341e4f7e80aa59b630dbc6647ea3d05f4980881e09a6f912"
)
EXPECTED_DECISION_READER_RAW = (
    "ce974c3590a40db23a54cd450dbf7282fb1cd172fc416cfcb8aeabd3ab86956c"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "1197fd5d5e7f6bdaccb3b4538fd999bc4995fe34890cd8472f3df68fa00b0fae"
)
EXPECTED_COMPACT_IDENTITY = (
    "52567cdead3fcd8029f9c1676a7f83af86a5d0110c52851b47e55b2f09af8a7d"
)
EXPECTED_FULL_WITNESS = (
    "af51e067ccf3388561bfe0e2b38dae744792625cdc5f7a37b55208b41d4a5fb4"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "025e9a401eda9fac4687ed4c2cdbefd07a0b0489d31c1b43fe9744350579ff78"
)
EXPECTED_PERMIT_READER_RAW = (
    "1da05139619a7aa017d33aa2b082154de25cdc665246941db630433321833ebf"
)
EXPECTED_RUNNER_NORMALIZED_SHA256 = (
    "5340c5ac8bf24d941f4bfe1271bca013984209a946164c2b00da85896c4ba565"
)
EXPECTED_WAVE4_CHECKER_RAW = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
EXPECTED_WAVE4_RUNNER_RAW = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)

PROXY_HOST = "proxy.golang.org"
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-5-v1.claim"
STAGING_PREFIX = ".wave-5-v1-staging-"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-5-v1"
FINAL_ACCEPTED = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-receipt-v1.json"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-manifest-v1.json"
)
READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "readback-manifest-v1.json"
)

MAX_MOD_BYTES = 1 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_AGGREGATE_MOD_BYTES = 8 * 1024 * 1024
MAX_AGGREGATE_ZIP_BYTES = 128 * 1024 * 1024
MAX_AGGREGATE_BYTES = 128 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
PER_REQUEST_DEADLINE_MS = 30_000
WHOLE_ATTEMPT_DEADLINE_MS = 600_000
MAX_ZIP_FILES = 20_000
MAX_ZIP_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ZIP_FILE_BYTES = 128 * 1024 * 1024
MAX_ZIP_NAME_BYTES = 1_024
MAX_ALL_ZIP_FILES = 300_000
MAX_ALL_ZIP_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAXIMUM_PACKAGE_BYTES = 8 * 1024 * 1024


class CheckError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise CheckError("E_ARGUMENT")


def require(value: bool, code: str) -> None:
    if not value:
        raise CheckError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode() + b"\n"


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(CheckError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(CheckError("E_JSON")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    require("contentBinding" not in result, "E_CONTENT")
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256(canonical_bytes(result)),
    }
    return result


def _bootstrap_module(
    root: Path,
    path: str,
    expected_sha256: str,
    module_name: str,
) -> tuple[types.ModuleType, bytes]:
    target = root / path
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_PACKAGE_BYTES,
            "E_BOOTSTRAP",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_BOOTSTRAP")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_BOOTSTRAP")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        fields = (
            "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
            "st_size", "st_mtime_ns", "st_ctime_ns",
        )
        require(
            all(getattr(before, name) == getattr(after, name) for name in fields)
            and sha256(raw) == expected_sha256,
            "E_BOOTSTRAP",
        )
    finally:
        os.close(fd)
    module = types.ModuleType(module_name)
    module.__file__ = str(target)
    module.__package__ = ""
    exec(compile(raw, path, "exec"), module.__dict__)
    return module, raw


DECISION, DECISION_CHECKER_RAW = _bootstrap_module(
    ROOT,
    DECISION_CHECKER_PATH,
    EXPECTED_DECISION_CHECKER_RAW,
    "wave5_identity_decision_v1",
)


def _portable(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


class HeldTerminalNamespace:
    """Hold the documentation directory and prove terminal names absent."""

    def __init__(self, root: Path) -> None:
        self.root_path = root
        self.root_fd = -1
        self.directory_fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
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
            DECISION.PinnedFile._validate_directory(self.root_initial)
            current = os.dup(self.root_fd)
            for component in BASE.split("/"):
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
                DECISION.PinnedFile._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.directory_fd = current
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def observe_absent(self) -> None:
        forbidden = {
            _portable(Path(path).name)
            for path in (
                RECEIPT_PATH,
                FAILURE_PATH,
                MANIFEST_PATH,
                READBACK_PATH,
                READBACK_MANIFEST_PATH,
            )
        }
        try:
            raw_names = os.listdir(self.directory_fd)
            names = {_portable(name) for name in raw_names}
        except OSError as error:
            raise CheckError("E_TERMINAL_NAMESPACE") from error
        require(
            len(names) == len(raw_names) and not forbidden & names,
            "E_TERMINAL_NAMESPACE",
        )

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root_path, follow_symlinks=False)
            require(
                DECISION.directory_identity(held_root)
                == DECISION.directory_identity(self.root_initial)
                == DECISION.directory_identity(named_root),
                "E_ROOT_IDENTITY",
            )
            for child, initial, parent, component in self.directories:
                require(
                    DECISION.directory_identity(os.fstat(child))
                    == DECISION.directory_identity(initial)
                    == DECISION.directory_identity(
                        os.stat(
                            component,
                            dir_fd=parent,
                            follow_symlinks=False,
                        )
                    ),
                    "E_TERMINAL_NAMESPACE",
                )
        except OSError as error:
            raise CheckError("E_TERMINAL_NAMESPACE") from error
        self.observe_absent()

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
        if self.root_fd >= 0 and self.root_fd not in seen:
            os.close(self.root_fd)
        self.root_fd = -1
        self.directory_fd = -1

    def __enter__(self) -> "HeldTerminalNamespace":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _tuple_digest(module: str, version: str) -> str:
    return sha256(f"{module}\n{version}\n".encode("utf-8"))


def normalized_resources(decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    preparation = decision["sourceAcquisitionPreparation"]
    source = preparation["requestSet"]
    require(
        preparation["requestCount"] == 30
        and preparation["requestOrder"] == "tuple_order_ascending_mod_then_zip"
        and preparation["proxyHost"] == PROXY_HOST
        and preparation["acquisitionReady"] is True
        and preparation["acquisitionAuthorizedByThisDecision"] is False
        and preparation["claimPath"] == CLAIM_PATH
        and preparation["stagingDirectoryPrefix"] == STAGING_PREFIX
        and preparation["acceptedDirectoryPath"] == FINAL_ACCEPTED
        and type(source) is list
        and len(source) == 30
        and sha256(canonical_bytes(source)) == EXPECTED_SOURCE_REQUEST_SET_CANONICAL,
        "E_REQUEST_SET",
    )
    return _normalize_request_rows(source)


def _normalize_request_rows(
    source: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    require(type(source) is list and len(source) == 30, "E_REQUEST_SET")
    expected_keys = {
        "acceptedFileName",
        "acquisitionAuthorized",
        "authenticationRequired",
        "expectedH1",
        "host",
        "maximumResponseBytes",
        "method",
        "module",
        "networkAuthorized",
        "requestOrdinal",
        "resourceKind",
        "selectedByGraphAlgorithm",
        "tupleOrder",
        "url",
        "version",
    }
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(source):
        require(type(item) is dict and set(item) == expected_keys, "E_REQUEST_SET")
        ordinal = index + 1
        tuple_order = index // 2 + 1
        kind = "mod" if index % 2 == 0 else "zip"
        module = item["module"]
        version = item["version"]
        components = module.split("/") if type(module) is str else []
        require(
            type(module) is str
            and type(version) is str
            and module.isascii()
            and version.isascii()
            and re.fullmatch(r"[a-z0-9][a-z0-9./_-]*", module) is not None
            and all(
                component not in {"", ".", ".."}
                for component in components
            )
            and re.fullmatch(r"v[0-9][A-Za-z0-9.+_-]*", version) is not None,
            "E_REQUEST_IDENTITY",
        )
        digest = _tuple_digest(module, version)
        expected_path = f"/{module}/@v/{version}.{kind}"
        parsed = urlsplit(item["url"])
        maximum = MAX_MOD_BYTES if kind == "mod" else MAX_ZIP_BYTES
        require(
            item["requestOrdinal"] == ordinal
            and item["tupleOrder"] == tuple_order
            and item["resourceKind"] == kind
            and item["method"] == "GET"
            and item["host"] == PROXY_HOST
            and item["maximumResponseBytes"] == maximum
            and item["acceptedFileName"]
            == f"{tuple_order:03d}-{digest[:20]}.{kind}"
            and item["acquisitionAuthorized"] is False
            and item["networkAuthorized"] is False
            and item["authenticationRequired"] is False
            and type(item["selectedByGraphAlgorithm"]) is bool
            and parsed.scheme == "https"
            and parsed.hostname == PROXY_HOST
            and parsed.port is None
            and parsed.path == expected_path
            and not parsed.query
            and not parsed.fragment
            and item["url"] == f"https://{PROXY_HOST}{expected_path}"
            and re.fullmatch(r"h1:[A-Za-z0-9+/]{43}=", item["expectedH1"])
            is not None,
            "E_REQUEST_CONTRACT",
        )
        rows.append(
            {
                "requestOrdinal": ordinal,
                "tupleOrder": tuple_order,
                "tupleId": f"wave5-{tuple_order:03d}-{digest[:12]}",
                "tupleDigestSha256": digest,
                "selectedByGraphAlgorithm": item["selectedByGraphAlgorithm"],
                "module": module,
                "version": version,
                "kind": kind,
                "method": "GET",
                "host": PROXY_HOST,
                "port": 443,
                "path": expected_path,
                "url": item["url"],
                "expectedH1": item["expectedH1"],
                "maximumResponseBodyBytes": maximum,
                "acceptedFileName": item["acceptedFileName"],
            }
        )
    for index in range(0, 30, 2):
        first, second = rows[index:index + 2]
        require(
            first["tupleOrder"] == second["tupleOrder"]
            and first["tupleId"] == second["tupleId"]
            and first["module"] == second["module"]
            and first["version"] == second["version"]
            and first["selectedByGraphAlgorithm"]
            == second["selectedByGraphAlgorithm"],
            "E_REQUEST_PAIR",
        )
    require(
        sum(bool(row["selectedByGraphAlgorithm"]) for row in rows[::2]) == 0,
        "E_REQUEST_SELECTION",
    )
    return rows


def normalized_runner(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    pattern = re.compile(r'EXPECTED_CHECKER_RAW = "[0-9a-f]{64}"')
    require(len(pattern.findall(text)) == 1, "E_RUNNER")
    return pattern.sub(
        'EXPECTED_CHECKER_RAW = "' + "0" * 64 + '"',
        text,
    ).encode()


def validate_runner(runner_raw: bytes, checker_raw: bytes) -> None:
    require(
        sha256(normalized_runner(runner_raw))
        == EXPECTED_RUNNER_NORMALIZED_SHA256,
        "E_RUNNER",
    )
    source = runner_raw.decode("utf-8", errors="strict")
    tree = ast.parse(source)
    imports: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
    require(
        not {
            "subprocess",
            "requests",
            "urllib.request",
            "socket",
        } & imports
        and {
            "direct_fetch",
            "create_claim",
            "rename_exclusive",
            "preflight",
            "_attempt",
            "execute",
            "validate_execution_context",
        } <= functions,
        "E_RUNNER",
    )
    for token in (
        "signal.setitimer",
        "EXPECTED_WAVE4_RUNNER_RAW",
        "os.O_EXCL",
        "os.fsync",
        "os.pread",
        "renameatx_np",
        "dir_fd=",
        "HeldEntry",
        "ExecutionNamespace",
        "externalAuthenticationRequired",
        "retryAllowed",
    ):
        require(token in source, "E_RUNNER")
    for token in (
        "subprocess",
        "shell=True",
        "shutil.rmtree",
        "Authorization",
        "Proxy-Authorization",
        "Cookie",
    ):
        require(token not in source, "E_RUNNER")
    reverse = re.findall(r'EXPECTED_CHECKER_RAW = "([0-9a-f]{64})"', source)
    require(reverse == [sha256(checker_raw)], "E_RUNNER")


def _decision_package_bindings() -> list[dict[str, str]]:
    return [
        {"path": DECISION_PATH, "rawSha256": EXPECTED_DECISION_RAW},
        {
            "path": DECISION_READER_PATH,
            "rawSha256": EXPECTED_DECISION_READER_RAW,
        },
        {
            "path": DECISION_CHECKER_PATH,
            "rawSha256": EXPECTED_DECISION_CHECKER_RAW,
        },
        {
            "path": DECISION_TESTS_PATH,
            "rawSha256": EXPECTED_DECISION_TESTS_RAW,
        },
    ]


def permit_payload(
    decision: Mapping[str, Any],
    package_raw: Mapping[str, bytes],
) -> dict[str, Any]:
    resources = normalized_resources(decision)
    validate_runner(package_raw[RUNNER_PATH], package_raw[THIS_CHECKER_PATH])
    tool_paths = (
        THIS_CHECKER_PATH,
        THIS_TESTS_PATH,
        RUNNER_PATH,
        RUNNER_TESTS_PATH,
    )
    tool_bindings = [
        {"path": path, "rawSha256": sha256(package_raw[path])}
        for path in tool_paths
    ]
    primitive_bindings = [
        {
            "path": WAVE4_CHECKER_PATH,
            "rawSha256": EXPECTED_WAVE4_CHECKER_RAW,
            "use": "constants_and_validation_contract_only",
        },
        {
            "path": WAVE4_RUNNER_PATH,
            "rawSha256": EXPECTED_WAVE4_RUNNER_RAW,
            "use": (
                "h1_go_mod_zip_and_direct_https_"
                "validation_primitives_only"
            ),
        },
    ]
    return {
        "documentType": "aetherlink.wave5-source-acquisition-execution-permit",
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave5-30-resource-source-acquisition-"
            "execution-permit-v1"
        ),
        "recordedDate": "2026-07-25",
        "status": "authorized_not_consumed",
        "decisionBinding": {
            "path": DECISION_PATH,
            "rawSha256": EXPECTED_DECISION_RAW,
            "contentSha256": EXPECTED_DECISION_CONTENT,
            "requiredStatus": decision["status"],
            "files": _decision_package_bindings(),
        },
        "identityBinding": {
            "compactIdentitySha256": EXPECTED_COMPACT_IDENTITY,
            "fullWitnessSha256": EXPECTED_FULL_WITNESS,
            "heldSourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
            "completeTupleCount": 15,
            "blockedTupleCount": 0,
        },
        "requestContract": {
            "tupleCount": 15,
            "requestCount": 30,
            "order": "tuple_order_ascending_mod_then_zip",
            "method": "GET",
            "host": PROXY_HOST,
            "port": 443,
            "sourceRequestSetCanonicalSha256":
                EXPECTED_SOURCE_REQUEST_SET_CANONICAL,
            "resources": resources,
            "resourcesCanonicalSha256": sha256(canonical_bytes(resources)),
            "directHttpsOnly": True,
            "tlsCertificateAndHostnameValidationRequired": True,
            "identityContentEncodingRequired": True,
            "acceptedStatusCode": 200,
            "requestBodyAllowed": False,
            "redirectAllowed": False,
            "ambientProxyAllowed": False,
            "alternateHostAllowed": False,
            "authenticationAllowed": False,
            "authorizationHeaderAllowed": False,
            "proxyAuthorizationHeaderAllowed": False,
            "cookieAllowed": False,
            "clientCertificateAllowed": False,
            "rangeHeaderAllowed": False,
            "queryOrFragmentAllowed": False,
            "retryResumeOrBackfillAllowed": False,
        },
        "oneUseContract": {
            "claimPath": CLAIM_PATH,
            "claimCreatedOExcl0600AndFsyncedBeforeDnsOrNetwork": True,
            "claimPersistsAfterSuccessFailureTimeoutOrUncertainty": True,
            "existingClaimState": "already_consumed",
            "claimAbsentAtPermitPublication": True,
            "claimCreationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "secondExecutionAllowed": False,
            "stagingPrefix": STAGING_PREFIX,
            "finalRootPath": FINAL_ROOT,
            "finalAcceptedPath": FINAL_ACCEPTED,
            "evidencePath": EVIDENCE_PATH,
            "failureRetainsStaging": True,
            "retryResumeBackfillOverwriteOrCleanupAllowed": False,
        },
        "verificationContract": {
            "goModH1Algorithm":
                "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod",
            "moduleZipH1Algorithm":
                "golang.org/x/mod/sumdb/dirhash.HashZip(Hash1)_v1",
            "rawSha256RecordedSeparately": True,
            "zipExactModuleVersionPrefixRequired": True,
            "zipSafetyShapeCrcAndModParityRequired": True,
            "sourceExtractionAllowed": False,
        },
        "zipLimits": {
            "maximumEntryCountPerZip": MAX_ZIP_FILES,
            "maximumUncompressedBytesPerZip":
                MAX_ZIP_UNCOMPRESSED_BYTES,
            "maximumSingleEntryBytes": MAX_ZIP_FILE_BYTES,
            "maximumEntryNameBytes": MAX_ZIP_NAME_BYTES,
            "maximumEntryCountAcrossAllZips": MAX_ALL_ZIP_FILES,
            "maximumUncompressedBytesAcrossAllZips":
                MAX_ALL_ZIP_UNCOMPRESSED_BYTES,
            "encryptedSymlinkDirectoryDuplicateOrUnsafeEntriesAllowed": False,
        },
        "absoluteResourceLimits": {
            "maximumRequestCount": 30,
            "maximumModResponseBodyBytes": MAX_MOD_BYTES,
            "maximumZipResponseBodyBytes": MAX_ZIP_BYTES,
            "maximumAggregateModResponseBodyBytes":
                MAX_AGGREGATE_MOD_BYTES,
            "maximumAggregateZipResponseBodyBytes":
                MAX_AGGREGATE_ZIP_BYTES,
            "maximumAggregateResponseBodyBytes": MAX_AGGREGATE_BYTES,
            "maximumHeaderBytesPerResponse": MAX_HEADER_BYTES,
            "perRequestDeadlineMilliseconds": PER_REQUEST_DEADLINE_MS,
            "wholeAttemptDeadlineMilliseconds":
                WHOLE_ATTEMPT_DEADLINE_MS,
            "absoluteWallTimersRequired": True,
            "preexistingRealTimerRestoredWithElapsedAdjustment": True,
        },
        "filesystemAuthority": {
            "claimWriteAuthorized": True,
            "ownerOnlyStagingWriteAuthorized": True,
            "verifiedModAndZipWriteAuthorized": True,
            "receiptFailureAndManifestWriteAuthorized": True,
            "atomicNoReplacePublicationRequired": True,
            "manifestWrittenLast": True,
            "newFileMode": "0600",
            "newDirectoryMode": "0700",
            "sourceExtractionAuthorized": False,
            "otherRepositoryWritesAuthorized": False,
        },
        "authority": {
            "wave5SourceAcquisitionAuthorizedOnce": True,
            "dnsTcpTlsHttpsToExactProxyAuthorized": True,
            "sourceExtractionAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "productRuntimeNetworkAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "passwordRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
            "userActionRequired": False,
        },
        "terminalContract": {
            "receiptPath": RECEIPT_PATH,
            "failurePath": FAILURE_PATH,
            "manifestPath": MANIFEST_PATH,
            "readbackPath": READBACK_PATH,
            "readbackManifestPath": READBACK_MANIFEST_PATH,
            "successAndFailureMutuallyExclusive": True,
            "failurePublishesFailureOnly": True,
            "failurePublicationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "postPublicationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "manifestWrittenLast": True,
            "independentReadbackRequired": True,
        },
        "readerDocumentBinding": {
            "path": PERMIT_READER_PATH,
            "rawSha256": EXPECTED_PERMIT_READER_RAW,
        },
        "toolBindings": tool_bindings,
        "primitiveBindings": primitive_bindings,
        "runnerNormalizedSha256": EXPECTED_RUNNER_NORMALIZED_SHA256,
        "nonClaims": [
            "no account owner SSH GPG password private key signature token cookie client certificate or user authentication is required",
            "the permit does not authorize source extraction loading execution compilation package-manager use Git device deployment or product runtime networking",
            "the permit does not establish dependency fixed point semantic closure candidate selection library selection rung-three completion or release readiness",
        ],
        "result":
            "exact_30_resource_one_use_wave5_acquisition_authorized_not_consumed",
        "nextAction": "execute_bound_wave5_source_acquisition_once",
    }


def _package_specs(include_permit: bool) -> list[tuple[str, str | None]]:
    specs = [
        (DECISION_PATH, EXPECTED_DECISION_RAW),
        (DECISION_READER_PATH, EXPECTED_DECISION_READER_RAW),
        (DECISION_CHECKER_PATH, EXPECTED_DECISION_CHECKER_RAW),
        (DECISION_TESTS_PATH, EXPECTED_DECISION_TESTS_RAW),
        (PERMIT_READER_PATH, EXPECTED_PERMIT_READER_RAW),
        (THIS_CHECKER_PATH, None),
        (THIS_TESTS_PATH, None),
        (RUNNER_PATH, None),
        (RUNNER_TESTS_PATH, None),
        (WAVE4_CHECKER_PATH, EXPECTED_WAVE4_CHECKER_RAW),
        (WAVE4_RUNNER_PATH, EXPECTED_WAVE4_RUNNER_RAW),
    ]
    if include_permit:
        specs.append((PERMIT_PATH, None))
    return specs


class AuthorityFiles:
    """Pin every byte that grants or implements one Wave5 attempt."""

    def __init__(
        self,
        root: Path,
        permit: Mapping[str, Any],
    ) -> None:
        self.root = root
        self.permit = permit
        self.stack = ExitStack()
        self.held: list[Any] = []

    def __enter__(self) -> "AuthorityFiles":
        expected = {
            row["path"]: row["rawSha256"]
            for row in (
                list(self.permit["decisionBinding"]["files"])
                + list(self.permit["toolBindings"])
                + list(self.permit["primitiveBindings"])
            )
        }
        expected[PERMIT_READER_PATH] = self.permit[
            "readerDocumentBinding"
        ]["rawSha256"]
        expected[PERMIT_PATH] = sha256(canonical_bytes(self.permit))
        try:
            self.held = [
                self.stack.enter_context(
                    DECISION.PinnedFile(
                        self.root,
                        path,
                        expected_sha256=digest,
                        maximum_bytes=MAXIMUM_PACKAGE_BYTES,
                    )
                )
                for path, digest in sorted(expected.items())
            ]
            self.barrier()
            return self
        except BaseException:
            self.stack.close()
            raise

    def barrier(self) -> None:
        DECISION.identity_barrier(self.root, self.held)

    def __exit__(self, *_: object) -> None:
        self.stack.close()


def evaluate(
    verify_disk: bool,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_decision, decision_summary = DECISION.evaluate(
        root,
        verify_disk=True,
    )
    require(
        decision_summary["validationPassed"] is True
        and decision_summary["tupleCount"] == 15
        and decision_summary["completeIdentityPairCount"] == 15
        and decision_summary["blockedTupleCount"] == 0
        and decision_summary["acquisitionReady"] is True
        and decision_summary["acquisitionAuthorized"] is False
        and decision_summary["externalAuthenticationRequired"] is False
        and expected_decision["contentBinding"]["sha256"]
        == EXPECTED_DECISION_CONTENT,
        "E_DECISION",
    )
    with ExitStack() as stack:
        reserved = stack.enter_context(DECISION.HeldNamespace(root))
        terminal = stack.enter_context(HeldTerminalNamespace(root))
        pinned = {
            path: stack.enter_context(
                DECISION.PinnedFile(
                    root,
                    path,
                    expected_sha256=expected,
                    maximum_bytes=MAXIMUM_PACKAGE_BYTES,
                )
            )
            for path, expected in _package_specs(verify_disk)
        }
        held = [reserved, terminal, *pinned.values()]
        DECISION.identity_barrier(root, held)
        decision_raw = pinned[DECISION_PATH].raw
        require(
            sha256(decision_raw) == EXPECTED_DECISION_RAW
            and strict_json(decision_raw) == expected_decision,
            "E_DECISION",
        )
        package_raw = {path: item.raw for path, item in pinned.items()}
        permit = content_bound(permit_payload(expected_decision, package_raw))
        if verify_disk:
            permit_raw = pinned[PERMIT_PATH].raw
            require(
                permit_raw == canonical_bytes(permit)
                and strict_json(permit_raw) == permit,
                "E_PERMIT",
            )
        DECISION.identity_barrier(root, held)
    return {
        "decision": expected_decision,
        "permit": permit,
    }, {
        "documentType": "aetherlink.wave5-source-acquisition-package-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "tupleCount": 15,
        "requestCount": 30,
        "claimExists": False,
        "networkUsed": False,
        "fileWriteCount": 0,
        "sourceAcquired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def error_document(code: str) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.wave5-source-acquisition-package-error",
        "schemaVersion": "1.0",
        "status": "failed_closed",
        "failureCode": code,
        "networkAuthorized": False,
        "fileWriteAuthorized": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False)
        parser.add_argument("--print-permit", action="store_true")
        args = parser.parse_args(argv)
        values, summary = evaluate(not args.print_permit)
        sys.stdout.buffer.write(
            canonical_bytes(values["permit"] if args.print_permit else summary)
        )
        return 0
    except (CheckError, DECISION.DecisionFailure) as error:
        code = getattr(error, "code", "E_DECISION")
        sys.stdout.buffer.write(canonical_bytes(error_document(code)))
        return 1
    except Exception:
        sys.stdout.buffer.write(canonical_bytes(error_document("E_INTERNAL")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
