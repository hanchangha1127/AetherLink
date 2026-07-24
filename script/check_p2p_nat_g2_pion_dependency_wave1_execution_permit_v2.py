#!/usr/bin/env python3
"""Validate the separate G2 Pion dependency wave-one v2 execution permit."""

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
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
SOURCE_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
RECOVERY_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.json"
)
RECOVERY_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.md"
)
RECOVERY_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_recovery_decision_v1.py"
)
RECOVERY_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_recovery_decision_v1.py"
)
LEGACY_RUNNER_PATH = "script/acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
RUNNER_PATH = "script/acquire_p2p_nat_g2_pion_dependency_wave1_v2_once.py"
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_dependency_wave1_v2_once.py"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v2.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_execution_permit_v2.py"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v2.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v2.md"
)

EXPECTED_SOURCE_RAW_SHA256 = (
    "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
)
EXPECTED_SOURCE_CONTENT_SHA256 = (
    "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201"
)
EXPECTED_RECOVERY_RAW_SHA256 = (
    "313e548e8d538ccc582f4d1c74618823d31b45915b4a5124378bc0d8b98315c2"
)
EXPECTED_RECOVERY_CONTENT_SHA256 = (
    "8cdcccbea4318d41f44da78000f3e4161251a5ad9542543c2962d4767ed1e968"
)
EXPECTED_RECOVERY_READER_RAW_SHA256 = (
    "02fc75469af753bec9070b893b8755762b05262f1c4d1ced9da67645d1e127e9"
)
EXPECTED_RECOVERY_CHECKER_RAW_SHA256 = (
    "33ea25abeac607eb2a11a4039c293ba4949adec850217a319d96dd0bcf69bbe4"
)
EXPECTED_RECOVERY_TEST_RAW_SHA256 = (
    "e90551eeca4efdde87bcbc205d6550255375958908dac991e305716c8a5343e4"
)
EXPECTED_LEGACY_RUNNER_RAW_SHA256 = (
    "571985e002c6b819bfbe7153bb445beef27fdcad239a289b492005435c2a0356"
)

EXPECTED_DATE = "2026-07-24"
EXPECTED_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v2"
)
EXPECTED_STATUS = (
    "wave1_v2_dependency_source_acquisition_authorized_not_consumed"
)
EXPECTED_RESULT = (
    "exact_19_public_proxy_zip_requests_v2_authorized_once_not_executed"
)
EXPECTED_NEXT_ACTION = "execute_bound_dependency_source_wave1_v2_once"
EXPECTED_SCOPE = (
    "single_fresh_exact_19_zip_public_go_proxy_source_intake_v2_only"
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
V2_STAGING_PARENT = "build/offline-source/pion-ice-v4.3.0/dependencies"
V2_STAGING_PREFIX = ".wave-1-v2-staging-"
V2_FINAL_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v2/accepted"
)
V2_SUCCESS_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v2.json"
)
V2_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v2.json"
)
V2_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v2.json"
)

EXPECTED_TOOL_ROWS = (
    ("immutable_wave1_v1_runner_library", LEGACY_RUNNER_PATH),
    ("wave1_v1_terminal_recovery_checker", RECOVERY_CHECKER_PATH),
    ("wave1_v1_terminal_recovery_checker_tests", RECOVERY_TEST_PATH),
    ("bounded_dependency_wave1_v2_runner", RUNNER_PATH),
    ("bounded_dependency_wave1_v2_runner_offline_tests", RUNNER_TEST_PATH),
    ("strict_dependency_wave1_v2_execution_permit_checker", CHECKER_PATH),
    ("execution_permit_v2_checker_mutation_tests", CHECKER_TEST_PATH),
)

ABSOLUTE_RESOURCE_LIMITS = {
    "maximumSelectedModules": 19,
    "maximumRequestCount": 19,
    "perRequestDeadlineMilliseconds": 30000,
    "wholeWaveDeadlineMilliseconds": 300000,
    "maximumResponseBytesPerArchive": 16777216,
    "maximumAggregateResponseBytes": 134217728,
    "maximumRetainedBytes": 134217728,
    "maximumEntriesPerArchive": 16384,
    "maximumAggregateEntries": 131072,
    "maximumCentralDirectoryBytesPerArchive": 8388608,
    "maximumSingleFileBytes": 16777216,
    "maximumUncompressedBytesPerArchive": 268435456,
    "maximumAggregateUncompressedBytes": 1073741824,
    "maximumPathBytes": 1024,
    "maximumPathComponents": 64,
    "maximumComponentBytes": 255,
    "maximumGraphNodes": 512,
    "maximumGraphEdges": 4096,
    "maximumJsonReceiptOrFailureBytes": 2097152,
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
    "recoveryBinding",
    "sourceDecisionBinding",
    "toolBindings",
    "interpreterIsolationContract",
    "oneUseConsumption",
    "requestContract",
    "networkAuthority",
    "archiveValidationContract",
    "filesystemWriteAuthority",
    "absoluteResourceLimits",
    "telemetryPolicy",
    "receiptFailureManifestContract",
    "authority",
    "execution",
    "closure",
    "nonClaims",
    "contentBinding",
}

EXPECTED_NONCLAIMS = [
    "permit_is_not_execution_or_success_evidence",
    "v1_claim_and_failure_remain_terminal_and_are_not_reused",
    "v2_does_not_resume_or_recover_deleted_v1_staging",
    "compression_ratio_telemetry_is_not_an_archive_authenticity_root",
    "non_gating_ratio_telemetry_does_not_remove_absolute_bounds",
    "module_h1_and_go_mod_h1_are_not_raw_zip_sha256",
    "nineteen_root_sources_are_not_dependency_fixed_point_evidence",
    "acquisition_is_not_source_license_security_or_semantic_review",
    "runner_self_checks_are_not_independent_readback",
    "permit_does_not_select_a_candidate_library_or_product_endpoint",
]

HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAXIMUM_FILE_BYTES = 4 * 1024 * 1024


class CheckError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise CheckError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


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


def exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    require(isinstance(value, dict), "E_SCHEMA", f"{label} must be an object")
    require(set(value) == expected, "E_SCHEMA", f"{label} keys differ")
    return value


def validate_relative_path(relative: str) -> tuple[str, ...]:
    require(isinstance(relative, str), "E_PATH", "path must be a string")
    path = PurePosixPath(relative)
    require(
        relative != ""
        and not path.is_absolute()
        and "\\" not in relative
        and "\x00" not in relative
        and all(part not in {"", ".", ".."} for part in path.parts),
        "E_PATH",
        "unsafe repository-relative path",
    )
    return path.parts


def file_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def read_fixed_file(
    root: Path,
    relative: str,
    *,
    maximum_bytes: int = MAXIMUM_FILE_BYTES,
) -> bytes:
    validate_relative_path(relative)
    path = root / relative
    try:
        fd = os.open(path, file_flags())
    except OSError as error:
        raise CheckError("E_FILESYSTEM", f"cannot open {relative}") from error
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
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, min(64 * 1024, remaining))
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
            f"{relative} changed during read",
        )
        return raw
    finally:
        os.close(fd)


def load_recovery_checker(root: Path) -> tuple[types.ModuleType, dict[str, Any]]:
    raw = read_fixed_file(root, RECOVERY_CHECKER_PATH)
    require(
        sha256_bytes(raw) == EXPECTED_RECOVERY_CHECKER_RAW_SHA256,
        "E_RECOVERY",
        "recovery checker raw binding",
    )
    module = types.ModuleType("g2_wave1_v1_recovery_checker_for_v2_permit")
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
                flags=0,
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
        result = module.validate_repository(root)
    except CheckError:
        raise
    except Exception as error:
        raise CheckError("E_RECOVERY", "terminal v1 recovery validation") from error
    require(isinstance(result, dict), "E_RECOVERY", "recovery result")
    require(
        result.get("v1PermitConsumed") is True
        and result.get("v1AutomaticRetryAllowed") is False
        and result.get("v2ExecutionAuthorized") is False,
        "E_RECOVERY",
        "terminal v1 recovery boundary",
    )
    return module, result


def validate_content_binding(document: Mapping[str, Any]) -> None:
    binding = exact_keys(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        "contentBinding",
    )
    require(
        typed_equal(
            binding,
            {
                "algorithm": "sha256",
                "canonicalization": (
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf"
                ),
                "scope": "permit_without_contentBinding",
                "sha256": binding["sha256"],
            },
        ),
        "E_BINDING",
        "content binding contract",
    )
    require(
        isinstance(binding["sha256"], str)
        and HEX_SHA256.fullmatch(binding["sha256"]) is not None,
        "E_BINDING",
        "content binding digest",
    )
    unsigned = dict(document)
    unsigned.pop("contentBinding", None)
    require(
        sha256_bytes(canonical_json_bytes(unsigned)) == binding["sha256"],
        "E_BINDING",
        "content binding mismatch",
    )


def expected_tool_bindings(raw: Mapping[str, bytes]) -> list[dict[str, str]]:
    return [
        {
            "role": role,
            "path": path,
            "rawSha256": sha256_bytes(raw[path]),
        }
        for role, path in EXPECTED_TOOL_ROWS
    ]


def validate_runner_source(
    runner_raw: bytes,
    runner_test_raw: bytes,
    checker_digest: str,
) -> None:
    try:
        tree = ast.parse(runner_raw, filename=RUNNER_PATH)
        ast.parse(runner_test_raw, filename=RUNNER_TEST_PATH)
    except SyntaxError as error:
        raise CheckError("E_TOOL", "v2 runner syntax") from error
    forbidden_imports = {
        "requests",
        "httpx",
        "aiohttp",
        "subprocess",
        "socket",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name.split(".", 1)[0] for alias in node.names}
            require(
                not names.intersection(forbidden_imports),
                "E_TOOL",
                "v2 runner forbidden import",
            )
        elif isinstance(node, ast.ImportFrom):
            require(
                (node.module or "").split(".", 1)[0] not in forbidden_imports,
                "E_TOOL",
                "v2 runner forbidden import",
            )
        elif isinstance(node, ast.Call):
            target = node.func
            require(
                not (
                    isinstance(target, ast.Attribute)
                    and target.attr
                    in {"system", "popen", "spawn", "execv", "execve", "fork"}
                ),
                "E_TOOL",
                "v2 runner process call",
            )
    source = runner_raw.decode("utf-8")
    required_tokens = (
        f'EXPECTED_CHECKER_RAW_SHA256 = "{checker_digest}"',
        f'EXPECTED_LEGACY_RUNNER_RAW_SHA256 = "{EXPECTED_LEGACY_RUNNER_RAW_SHA256}"',
        "def inspect_module_zip_v2(",
        "historicalV1ComparisonRatio",
        "maximumRatioEntryOrdinal",
        "networkRequestAttemptCount",
        "responseBodyCompletedCount",
        "validatedAndStagedTupleCount",
        "legacyCompletedRequestCountForbidden",
        "FAILURE_DOCUMENT_KEYS",
        "SUCCESS_RECEIPT_KEYS",
        "SUCCESS_MANIFEST_KEYS",
        "def safe_failure_document_v2(",
        "def validate_success_final_inventory(",
        "def preflight_validation_passed(",
        "def runner_error_document(",
        '"consumed_terminal_state_uncertain"',
        "def classify_preflight_state(",
        'mode.add_argument("--execute", action="store_true")',
        '"externalAuthenticationRequired": False',
    )
    for token in required_tokens:
        require(token in source, "E_TOOL", f"v2 runner missing {token}")
    require(
        '"completedRequestCount"' not in source,
        "E_TOOL",
        "legacy counter field present in v2 runner",
    )
    test_count = len(
        re.findall(
            r"(?m)^\s+def\s+test_",
            runner_test_raw.decode("utf-8"),
        )
    )
    require(test_count == 28, "E_TOOL", "v2 runner test count")


def validate_permit_reader(raw: bytes) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CheckError("E_READER", "permit reader encoding") from error
    for token in (
        "# G2 Pion dependency wave-one execution permit v2",
        EXPECTED_PERMIT_ID,
        EXPECTED_STATUS,
        EXPECTED_RESULT,
        EXPECTED_NEXT_ACTION,
        "No user authentication is required",
        "v1 claim and failure receipt remain immutable",
        "exactly 19 fresh sequential",
        "non-gating exact-integer telemetry",
        "16 MiB per response",
        "1 GiB aggregate uncompressed",
        "separate v2 claim",
        "independent readback",
    ):
        require(token in text, "E_READER", f"permit reader missing {token}")


def validate_permit(
    permit: Mapping[str, Any],
    recovery_result: Mapping[str, Any],
    raw: Mapping[str, bytes],
) -> None:
    exact_keys(permit, PERMIT_TOP_LEVEL_KEYS, "permit")
    expected_header = {
        "documentType": (
            "aetherlink.g2-pion-rung3-dependency-wave1-execution-permit"
        ),
        "schemaVersion": "2.0",
        "permitId": EXPECTED_PERMIT_ID,
        "recordedDate": EXPECTED_DATE,
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "scope": EXPECTED_SCOPE,
    }
    for key, value in expected_header.items():
        require(permit.get(key) == value, "E_STATE", f"permit.{key}")

    require(
        typed_equal(
            permit["personalProjectBoundary"],
            {
                "projectOwnership": "personal_single_owner",
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "privateKeyRequired": False,
                "tokenRequired": False,
                "passwordRequired": False,
                "signatureRequired": False,
                "userActionRequired": False,
                "productPairingAuthenticationUnaffected": True,
            },
        ),
        "E_AUTHORITY",
        "personal-project boundary",
    )
    require(
        typed_equal(
            permit["recoveryBinding"],
            {
                "path": RECOVERY_PATH,
                "rawSha256": EXPECTED_RECOVERY_RAW_SHA256,
                "contentSha256": EXPECTED_RECOVERY_CONTENT_SHA256,
                "requiredStatus": (
                    "wave1_v1_failure_read_back_recovery_v2_design_selected_"
                    "execution_not_authorized"
                ),
                "v1ClaimPath": V1_CLAIM_PATH,
                "v1ClaimRawSha256": (
                    "560bbb6028588b91a2d7f35ae826cdcc68940566656a279b2dbe7b9352e161d5"
                ),
                "v1FailurePath": V1_FAILURE_PATH,
                "v1FailureRawSha256": (
                    "cdf4d75aeddb2accc4720c2ef8a606b22e333eac9aea2196a010f9383dc877fa"
                ),
                "v1AutomaticRetryAllowed": False,
                "v1RunnerExecuteAllowed": False,
            },
        ),
        "E_RECOVERY",
        "recovery binding",
    )
    source = recovery_result.get("sourceDecision")
    require(isinstance(source, dict), "E_SOURCE", "source decision")
    require(
        typed_equal(
            permit["sourceDecisionBinding"],
            {
                "path": SOURCE_DECISION_PATH,
                "rawSha256": EXPECTED_SOURCE_RAW_SHA256,
                "contentSha256": EXPECTED_SOURCE_CONTENT_SHA256,
                "decisionId": source.get("decisionId"),
                "requiredTupleCount": 19,
                "freshFullSetRequired": True,
            },
        ),
        "E_SOURCE",
        "source decision binding",
    )

    require(
        typed_equal(permit["toolBindings"], expected_tool_bindings(raw)),
        "E_TOOL",
        "tool bindings",
    )
    require(
        typed_equal(
            permit["interpreterIsolationContract"],
            {
                "preflightCommand": [
                    "python3",
                    "-I",
                    "-B",
                    "-S",
                    RUNNER_PATH,
                    "--preflight",
                ],
                "executeCommand": [
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
        ),
        "E_RUNTIME",
        "interpreter isolation",
    )
    require(
        typed_equal(
            permit["oneUseConsumption"],
            {
                "initialState": "authorized_not_consumed",
                "claimPath": V2_CLAIM_PATH,
                "stagingParentPath": V2_STAGING_PARENT,
                "stagingNamePrefix": V2_STAGING_PREFIX,
                "finalDirectoryPath": V2_FINAL_DIRECTORY,
                "claimPersistsAfterAnyNetworkAttempt": True,
                "claimUncertaintyConsumesPermit": True,
                "automaticRetryAllowed": False,
                "secondExecutionAllowed": False,
                "preclaimFailureConsumesPermit": False,
                "v1ArtifactReuseAllowed": False,
            },
        ),
        "E_ONE_USE",
        "one-use contract",
    )
    require(
        typed_equal(
            permit["requestContract"],
            {
                "requestCount": 19,
                "method": "GET",
                "scheme": "https",
                "host": "proxy.golang.org",
                "port": 443,
                "tupleOrder": "exact_decision_wave_order_1_through_19_sequential",
                "responseBodyKind": "module_zip_only",
                "redirectsAllowed": False,
                "automaticRetriesAllowed": False,
                "rangeOrResumeAllowed": False,
                "alternateMirrorAllowed": False,
                "authenticationHeadersAllowed": False,
                "cookiesAllowed": False,
                "clientCertificatesAllowed": False,
                "ambientProxyAllowed": False,
                "contentEncoding": "identity",
                "successStatusCode": 200,
            },
        ),
        "E_REQUEST",
        "request contract",
    )
    require(
        typed_equal(
            permit["networkAuthority"],
            {
                "boundedSourceIntakeDnsAuthorized": True,
                "boundedSourceIntakeTcpAuthorized": True,
                "boundedSourceIntakeTlsAuthorized": True,
                "boundedSourceIntakeHttpsAuthorized": True,
                "authorizedHost": "proxy.golang.org",
                "authorizedRequestCount": 19,
                "runtimeSocketAuthorized": False,
                "runtimeNetworkAuthorized": False,
                "productNetworkAuthorized": False,
                "relayOrP2PNetworkAuthorized": False,
            },
        ),
        "E_AUTHORITY",
        "network authority",
    )
    require(
        typed_equal(
            permit["archiveValidationContract"],
            {
                "filesystemExtractionAllowed": False,
                "streamedToOwnerOnlyTemporaryFiles": True,
                "openedDescriptorValidation": True,
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
                "embeddedGoModH1Required": True,
                "orderedSourceSetDigestRequired": True,
                "compressionRatioRejectionAllowed": False,
                "compressionRatioTelemetryRequired": True,
            },
        ),
        "E_ARCHIVE",
        "archive validation contract",
    )
    require(
        typed_equal(
            permit["filesystemWriteAuthority"],
            {
                "newDirectoryMode": "0700",
                "newFileMode": "0600",
                "claimWriteAuthorized": True,
                "stagingWriteAuthorized": True,
                "acceptedZipWriteAuthorized": True,
                "successReceiptWriteAuthorized": True,
                "failureReceiptWriteAuthorized": True,
                "manifestWriteAuthorized": True,
                "failedStagingCleanupAuthorized": True,
                "atomicNoReplaceFinalDirectoryPublicationRequired": True,
                "v1ArtifactModificationAuthorized": False,
                "sourceModificationAuthorized": False,
                "sourceExtractionAuthorized": False,
                "otherRepositoryWritesAuthorized": False,
            },
        ),
        "E_FILESYSTEM",
        "filesystem authority",
    )
    require(
        typed_equal(permit["absoluteResourceLimits"], ABSOLUTE_RESOURCE_LIMITS),
        "E_LIMIT",
        "absolute limits",
    )
    source_limits = source.get("resourceLimits")
    require(isinstance(source_limits, dict), "E_SOURCE", "source resource limits")
    for key, value in ABSOLUTE_RESOURCE_LIMITS.items():
        require(source_limits.get(key) == value, "E_LIMIT", f"source limit {key}")
    require(
        source_limits.get("maximumCompressionRatio") == 200,
        "E_LIMIT",
        "historical ratio source value",
    )
    require(
        typed_equal(
            permit["telemetryPolicy"],
            {
                "compressionRatioPolicy": "non_gating_bounded_telemetry",
                "historicalV1ComparisonRatio": 200,
                "ratioComparisonUsesExactIntegerMultiplication": True,
                "floatingPointRatioAllowed": False,
                "recordPerArchiveMaximum": True,
                "recordMaximumEntryOrdinal": True,
                "recordMaximumEntryUncompressedBytes": True,
                "recordMaximumEntryCompressedBytes": True,
                "entryNameOrBodyRecorded": False,
                "legacyCompletedRequestCountForbidden": True,
                "counterNames": [
                    "networkRequestAttemptCount",
                    "responseBodyCompletedCount",
                    "validatedAndStagedTupleCount",
                ],
            },
        ),
        "E_TELEMETRY",
        "telemetry policy",
    )
    require(
        typed_equal(
            permit["receiptFailureManifestContract"],
            {
                "successReceiptPath": V2_SUCCESS_PATH,
                "failureReceiptPath": V2_FAILURE_PATH,
                "manifestPath": V2_MANIFEST_PATH,
                "successState": "acquired_pending_independent_readback",
                "failureState": "wave1_v2_acquisition_failed_permit_consumed",
                "postPublishUncertainState": "consumed_terminal_state_uncertain",
                "successAndFailureMutuallyExclusive": True,
                "acceptedArtifactCountOnSuccess": 19,
                "acceptedArtifactCountOnFailure": 0,
                "boundedFailureReasonCodesOnly": True,
                "rawErrorsBodiesHeadersCertificatesPathsOrEntryNamesRecorded": False,
                "manifestWrittenLast": True,
                "runnerMayClaimIndependentReadback": False,
                "independentReadbackRequired": True,
            },
        ),
        "E_RECEIPT",
        "receipt contract",
    )
    require(
        typed_equal(
            permit["authority"],
            {
                "permitRecorded": True,
                "exactWave1V2AcquisitionAuthorized": True,
                "boundedSourceIntakeNetworkAuthorized": True,
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
        ),
        "E_AUTHORITY",
        "authority",
    )
    require(
        typed_equal(
            permit["execution"],
            {
                "permitRecorded": True,
                "permitConsumed": False,
                "claimCreated": False,
                "networkRequestAttemptCount": 0,
                "responseBodyCompletedCount": 0,
                "validatedAndStagedTupleCount": 0,
                "acceptedArtifactCount": 0,
                "networkUsed": False,
                "successReceiptCreated": False,
                "failureReceiptCreated": False,
                "manifestCreated": False,
                "independentReadbackPassed": False,
            },
        ),
        "E_EXECUTION",
        "execution initial state",
    )
    require(
        typed_equal(
            permit["closure"],
            {
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
        ),
        "E_CLOSURE",
        "closure",
    )
    require(
        typed_equal(permit["nonClaims"], EXPECTED_NONCLAIMS),
        "E_NONCLAIM",
        "non-claims",
    )
    validate_content_binding(permit)


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    recovery_module, recovery_result = load_recovery_checker(root)
    reader = recovery_module.SafeReader(root)
    try:
        paths = tuple(path for _, path in EXPECTED_TOOL_ROWS) + (
            PERMIT_PATH,
            PERMIT_READER_PATH,
            RECOVERY_PATH,
            RECOVERY_READER_PATH,
            SOURCE_DECISION_PATH,
        )
        raw = {path: reader.read(path) for path in dict.fromkeys(paths)}
        require(
            sha256_bytes(raw[RECOVERY_PATH]) == EXPECTED_RECOVERY_RAW_SHA256,
            "E_RECOVERY",
            "recovery raw binding",
        )
        require(
            sha256_bytes(raw[RECOVERY_READER_PATH])
            == EXPECTED_RECOVERY_READER_RAW_SHA256,
            "E_RECOVERY",
            "recovery reader raw binding",
        )
        require(
            sha256_bytes(raw[RECOVERY_TEST_PATH])
            == EXPECTED_RECOVERY_TEST_RAW_SHA256,
            "E_RECOVERY",
            "recovery tests raw binding",
        )
        require(
            sha256_bytes(raw[LEGACY_RUNNER_PATH])
            == EXPECTED_LEGACY_RUNNER_RAW_SHA256,
            "E_TOOL",
            "legacy runner raw binding",
        )
        require(
            sha256_bytes(raw[SOURCE_DECISION_PATH])
            == EXPECTED_SOURCE_RAW_SHA256,
            "E_SOURCE",
            "source decision raw binding",
        )
        permit = recovery_module.strict_json(raw[PERMIT_PATH], "v2 permit")
        validate_permit(permit, recovery_result, raw)
        checker_digest = sha256_bytes(raw[CHECKER_PATH])
        validate_runner_source(
            raw[RUNNER_PATH],
            raw[RUNNER_TEST_PATH],
            checker_digest,
        )
        validate_permit_reader(raw[PERMIT_READER_PATH])
        checker_test_count = len(
            re.findall(
                r"(?m)^\s+def\s+test_",
                raw[CHECKER_TEST_PATH].decode("utf-8"),
            )
        )
        require(checker_test_count == 20, "E_TOOL", "v2 checker test count")
        reader.verify()
        reader.verify()
        root_info = os.fstat(reader.root_fd)
        repository_root_identity = {
            "device": root_info.st_dev,
            "inode": root_info.st_ino,
            "ownerUid": root_info.st_uid,
            "mode": stat.S_IMODE(root_info.st_mode),
        }
        source = recovery_result["sourceDecision"]
        execution_decision = json.loads(json.dumps(source))
        execution_decision["plannedAcquisitionContract"][
            "finalDirectoryPath"
        ] = V2_FINAL_DIRECTORY
        return {
            "permit": permit,
            "decision": execution_decision,
            "sourceDecision": source,
            "recoveryDecision": recovery_result["decision"],
            "repositoryRootIdentity": repository_root_identity,
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "permitRawSha256": sha256_bytes(raw[PERMIT_PATH]),
            "runnerRawSha256": sha256_bytes(raw[RUNNER_PATH]),
            "runnerTestCount": 28,
            "checkerTestCount": 20,
            "v1PermitConsumed": True,
            "v1AutomaticRetryAllowed": False,
            "v2ExecutionAuthorized": True,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "fileWriteCount": 0,
            "networkOperationCount": 0,
        }
    finally:
        reader.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_repository(args.root)
    except CheckError as error:
        print(f"[{error.code}] v2 execution permit validation failed", file=sys.stderr)
        return 1
    except Exception:
        print("[E_INTERNAL] v2 execution permit validation failed", file=sys.stderr)
        return 1
    print(
        "G2 Pion dependency wave-one execution permit v2 passed: exact 19 "
        "fresh public ZIP requests authorized once; ratio is non-gating "
        "integer telemetry; no user authentication required; "
        f"runner-tests={result['runnerTestCount']}; "
        f"checker-tests={result['checkerTestCount']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
