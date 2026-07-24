#!/usr/bin/env python3
"""Validate the one-use public checksum identity-resolution execution permit."""

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
    raise RuntimeError("execution permit checker requires `python3 -I -B -S`")

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_execution_permit_v1.py"
)
RUNNER_PATH = (
    "script/resolve_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_v1_once.py"
)
RUNNER_TESTS_PATH = (
    "script/test_resolve_p2p_nat_g2_pion_rung3_dependency_public_"
    "checksum_identity_v1_once.py"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_decision_v1.py"
)
EXPECTED_DECISION_CHECKER_RAW = (
    "47de3381f59aad75cec5639fff2eb5f1d3be2cd0bd06e3a47953430943fc4422"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "decision-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "decision-v1.md"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_decision_v1.py"
)
EXPECTED_DECISION_RAW = {
    DECISION_PATH: (
        "dfc141d996b213e5d172041341aa37bc43efac4f9e4d6c27aea415d8e69a840e"
    ),
    DECISION_READER_PATH: (
        "57c8df5364e577f85f88e4da0538ddd3b6a318ae62b71ea2a894983bedfd85f8"
    ),
    DECISION_CHECKER_PATH: EXPECTED_DECISION_CHECKER_RAW,
    DECISION_TESTS_PATH: (
        "ca59173e6c0fd3ec0692db12a63febd3b1f07f9d261fdb4484016ab512c8f9c4"
    ),
}
EXPECTED_DECISION_CONTENT = (
    "12eea2f9608f00c1953e41a9845669f396223fcaa561736aeb96b6ce2e37a0db"
)
EXPECTED_READER_RAW = (
    "8c421f586af85580571cf123a0917b4505d8ee5ee2f72eb0a7e0d398bb8d4493"
)
EXPECTED_RUNNER_NORMALIZED_SHA256 = (
    "1073e57d3b483cb9a6cb149d74513babaf7af654ea2241fe6389454a9381ef79"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 4 * 1024 * 1024

DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
CLAIM_PATH = (
    f"{DEPENDENCY_ROOT}/.wave-3-kr-pty-sumdb-identity-v1.claim"
)
STAGING_PREFIX = ".wave-3-kr-pty-sumdb-identity-v1-staging-"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-3-kr-pty-sumdb-identity-v1"
FINAL_EVIDENCE_PATH = f"{FINAL_ROOT}/evidence"
RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "receipt-v1.json"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "manifest-v1.json"
)
READBACK_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-manifest-v1.json"
)
TERMINAL_PATHS = (
    RECEIPT_PATH,
    FAILURE_PATH,
    MANIFEST_PATH,
    READBACK_PATH,
    READBACK_MANIFEST_PATH,
)


class PermitError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(value: bool, code: str) -> None:
    if not value:
        raise PermitError(code)


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
        ).encode()
        + b"\n"
    )


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
            parse_float=lambda _: (_ for _ in ()).throw(PermitError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(
                PermitError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    require("contentBinding" not in value, "E_CONTENT")
    value["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(value)),
    }
    return value


def verify_bound_bytes(
    raw: bytes,
    expected: Mapping[str, Any],
    mismatch_code: str,
) -> None:
    expected_value = dict(expected)
    expected_binding = expected_value.pop("contentBinding", None)
    require(
        type(expected_binding) is dict
        and expected_binding
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": sha256(canonical_bytes(expected_value)),
        },
        "E_CONTENT",
    )
    require(raw == canonical_bytes(expected), mismatch_code)
    actual = strict_json(raw)
    actual_binding = actual.pop("contentBinding", None)
    require(
        type(actual_binding) is dict
        and actual_binding
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": sha256(canonical_bytes(actual)),
        }
        and actual_binding == expected_binding,
        "E_CONTENT",
    )


def bootstrap_read(path: str, expected: str) -> bytes:
    current = ROOT
    for component in path.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_BOOTSTRAP",
        )
    fd = os.open(
        ROOT / path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
    )
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_BOOTSTRAP",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_BOOTSTRAP")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(fd, 1), "E_BOOTSTRAP")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        require(before == after and sha256(raw) == expected, "E_BOOTSTRAP")
        return raw
    finally:
        os.close(fd)


def load_module(name: str, path: str, expected: str) -> types.ModuleType:
    raw = bootstrap_read(path, expected)
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / path)
    module.__package__ = ""
    exec(compile(raw, path, "exec"), module.__dict__)
    return module


DECISION = load_module(
    "sumdb_identity_permit_decision_root",
    DECISION_CHECKER_PATH,
    EXPECTED_DECISION_CHECKER_RAW,
)


def normalized_runner_bytes(raw: bytes) -> bytes:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PermitError("E_RUNNER") from error
    pattern = re.compile(
        r'EXPECTED_PERMIT_CHECKER_RAW = "[0-9a-f]{64}"'
    )
    require(len(pattern.findall(text)) == 1, "E_RUNNER")
    normalized = pattern.sub(
        'EXPECTED_PERMIT_CHECKER_RAW = "' + "0" * 64 + '"',
        text,
    )
    return normalized.encode("utf-8")


def validate_runner_semantics(
    runner_raw: bytes,
    checker_raw: bytes,
) -> None:
    require(
        sha256(normalized_runner_bytes(runner_raw))
        == EXPECTED_RUNNER_NORMALIZED_SHA256,
        "E_RUNNER",
    )
    try:
        source = runner_raw.decode("utf-8", errors="strict")
        tree = ast.parse(source, filename=RUNNER_PATH)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise PermitError("E_RUNNER") from error
    allowed_imports = {
        "__future__",
        "argparse",
        "base64",
        "binascii",
        "ctypes",
        "hashlib",
        "http.client",
        "json",
        "os",
        "pathlib",
        "re",
        "secrets",
        "signal",
        "ssl",
        "stat",
        "sys",
        "time",
        "types",
        "typing",
        "urllib.parse",
    }
    observed_imports: set[str] = set()
    function_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            observed_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            observed_imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_names.add(node.name)
    require(observed_imports <= allowed_imports, "E_RUNNER")
    required_functions = {
        "load_permit_checker",
        "verify_signed_note",
        "parse_lookup_response",
        "inclusion_exprs",
        "consistency_exprs",
        "split_stored_hash_index",
        "parse_tile_path",
        "derive_tile_plan",
        "verify_inclusion",
        "verify_consistency",
        "direct_fetch",
        "create_claim",
        "rename_exclusive",
        "preflight",
        "execute",
    }
    require(required_functions <= function_names, "E_RUNNER")
    for forbidden in (
        "proxy.golang.org",
        "/@v/",
        "subprocess",
        "socket.",
        "requests.",
        "urlopen",
        "ProxyHandler",
        "shutil.rmtree",
        "os.system",
        "shell=True",
    ):
        require(forbidden not in source, "E_RUNNER")
    for required in (
        "http.client.HTTPSConnection",
        "ssl.create_default_context",
        'connection.request(\n            "GET"',
        "body=None",
        "encode_chunked=False",
        '"range"',
        "os.O_EXCL",
        'getattr(os, "O_NOFOLLOW", 0)',
        "os.fsync",
        "renameatx_np",
        "signal.setitimer",
        "PERMIT.DECISION.valid_tile_path",
    ):
        require(required in source, "E_RUNNER")
    reverse_pin = re.findall(
        r'EXPECTED_PERMIT_CHECKER_RAW = "([0-9a-f]{64})"',
        source,
    )
    require(
        reverse_pin == [sha256(checker_raw)],
        "E_RUNNER",
    )


def held_bindings(
    paths: Sequence[str],
    expected: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    expected = expected or {}
    result = []
    for path in paths:
        binding = {
            "path": path,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES
                if path.startswith("docs/")
                else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        if path in expected:
            binding["rawSha256"] = expected[path]
        result.append(binding)
    return result


class DecisionAdapter:
    def __init__(
        self,
        wave3: Any,
        checkpoint: Any,
        package: Any,
    ) -> None:
        self.wave3 = wave3
        self.checkpoint = checkpoint
        self.package = package

    def final_barrier(self) -> None:
        self.wave3.final_barrier()
        self.checkpoint.final_barrier()
        self.package.final_barrier()


class PermitContext:
    def __init__(self, root: Path, *, include_permit: bool) -> None:
        self.root = root
        self.wave3 = None
        self.checkpoint = None
        self.decision_package = None
        self.package = None
        try:
            self.wave3 = DECISION.WAVE3.DecisionContext(
                root,
                include_decision=True,
            )
            held_type = self.wave3.lineage.authority.decision_checker.HeldSet
            self.checkpoint = held_type(
                root,
                DECISION.checkpoint_bindings(),
            )
            self.decision_package = held_type(
                root,
                held_bindings(
                    tuple(EXPECTED_DECISION_RAW),
                    EXPECTED_DECISION_RAW,
                ),
            )
            package_paths = [
                READER_PATH,
                THIS_CHECKER_PATH,
                THIS_TESTS_PATH,
                RUNNER_PATH,
                RUNNER_TESTS_PATH,
            ]
            if include_permit:
                package_paths.append(PERMIT_PATH)
            self.package = held_type(root, held_bindings(package_paths))
            DECISION.RUNG2.validate_repository()
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def decision_adapter(self) -> DecisionAdapter:
        return DecisionAdapter(
            self.wave3,
            self.checkpoint,
            self.decision_package,
        )

    def final_barrier(self) -> None:
        require(
            self.wave3 is not None
            and self.checkpoint is not None
            and self.decision_package is not None
            and self.package is not None,
            "E_CONTEXT",
        )
        self.wave3.final_barrier()
        self.checkpoint.final_barrier()
        self.decision_package.final_barrier()
        self.package.final_barrier()
        recovery = DECISION.WAVE3.PERMIT.DECISION.V2.RECOVERY
        namespace = self.wave3.lineage.namespace
        for path in (CLAIM_PATH, FINAL_ROOT, *TERMINAL_PATHS):
            require(
                recovery.absent_from_held_namespace(namespace, path),
                "E_NAMESPACE",
            )
        require(
            not any(
                name.startswith(STAGING_PREFIX)
                for name in recovery.held_dependency_names(namespace)
            ),
            "E_NAMESPACE",
        )
        self.decision_package.final_barrier()
        self.checkpoint.final_barrier()
        self.wave3.final_barrier()

    def close(self) -> None:
        for held in (
            self.package,
            self.decision_package,
            self.checkpoint,
            self.wave3,
        ):
            if held is not None:
                try:
                    held.close()
                except BaseException:
                    pass


def expected_payload(context: PermitContext) -> dict[str, Any]:
    context.final_barrier()
    adapter = context.decision_adapter()
    decision_expected = DECISION.content_bound(
        DECISION.expected_payload(adapter)
    )
    decision_raw = context.decision_package.raw[DECISION_PATH]
    DECISION.verify_decision_bytes(decision_raw, decision_expected)
    require(
        sha256(decision_raw) == EXPECTED_DECISION_RAW[DECISION_PATH]
        and decision_expected["contentBinding"]["sha256"]
        == EXPECTED_DECISION_CONTENT,
        "E_DECISION",
    )
    package_raw = context.package.raw
    require(
        sha256(package_raw[READER_PATH]) == EXPECTED_READER_RAW,
        "E_READER",
    )
    validate_runner_semantics(
        package_raw[RUNNER_PATH],
        package_raw[THIS_CHECKER_PATH],
    )
    tools = [
        {"path": path, "rawSha256": sha256(package_raw[path])}
        for path in (
            THIS_CHECKER_PATH,
            THIS_TESTS_PATH,
            RUNNER_PATH,
            RUNNER_TESTS_PATH,
        )
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-public-checksum-identity-resolution-"
            "execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-kr-pty-v1.1.1-public-checksum-"
            "identity-resolution-execution-permit-v1"
        ),
        "recordedDate": "2026-07-24",
        "status": "authorized_not_consumed",
        "decisionBinding": {
            "files": [
                {"path": path, "rawSha256": digest}
                for path, digest in EXPECTED_DECISION_RAW.items()
            ],
            "decisionContentSha256": EXPECTED_DECISION_CONTENT,
            "requiredStatus": (
                "strict_deterministic_adaptive_sumdb_fsm_selected_"
                "execution_not_authorized"
            ),
            "requiredNextAction": (
                "prepare_separate_one_use_sumdb_identity_resolution_"
                "permit_checker_runner_and_tests"
            ),
        },
        "target": {
            "module": DECISION.TARGET_MODULE,
            "version": DECISION.TARGET_VERSION,
            "heldGoModH1": DECISION.TARGET_MOD_H1,
            "moduleZipH1": None,
            "unknownValueHardcoded": False,
        },
        "trustedCheckpoint": {
            "files": [
                {"path": path, "rawSha256": digest}
                for path, digest in DECISION.EXPECTED_RUNG2_RAW.items()
            ],
            "existingValidatorReverified": True,
            "verifierKey": DECISION.SUMDB_VERIFIER_KEY,
            "oldTreeSize": DECISION.OLD_TREE_SIZE,
            "oldRootHashBase64": DECISION.OLD_ROOT_HASH_BASE64,
            "oldSignatureBase64": DECISION.OLD_SIGNATURE_BASE64,
            "oldSignedTreeTextSha256": (
                DECISION.OLD_SIGNED_TREE_TEXT_SHA256
            ),
        },
        "oneUseConsumption": {
            "initialState": "authorized_not_consumed",
            "claimPath": CLAIM_PATH,
            "claimCreatedExclusivelyBeforeNetwork": True,
            "claimFsyncedBeforeNetwork": True,
            "claimContainsRandomAttemptId": True,
            "claimPersistsAfterAnyNetworkAttempt": True,
            "claimUncertaintyConsumesPermit": True,
            "preclaimFailureConsumesPermit": False,
            "secondExecutionAllowed": False,
            "automaticRetryAllowed": False,
            "partialResumeAllowed": False,
            "backfillAllowed": False,
            "stagingParentPath": DEPENDENCY_ROOT,
            "stagingNamePrefix": STAGING_PREFIX,
            "finalDirectoryPath": FINAL_EVIDENCE_PATH,
            "existingClaimStagingFinalOrTerminalRule": (
                "fail_closed_before_network"
            ),
        },
        "requestContract": {
            "mode": "strict_deterministic_adaptive_sumdb_lookup_then_tiles",
            "lookup": {
                "requestOrdinal": 1,
                "method": "GET",
                "url": DECISION.LOOKUP_URL,
                "host": DECISION.LOOKUP_HOST,
                "path": DECISION.LOOKUP_PATH,
                "acceptedStatusCode": 200,
                "maximumResponseBodyBytes": (
                    DECISION.MAXIMUM_LOOKUP_RESPONSE_BYTES
                ),
            },
            "tiles": {
                "method": "GET",
                "allowedHost": DECISION.LOOKUP_HOST,
                "allowedPathRegex": DECISION.TILE_PATH_REGEX,
                "tileHeight": DECISION.TILE_HEIGHT,
                "fullTileWidthHashes": DECISION.FULL_TILE_WIDTH,
                "hashBytes": 32,
                "maximumResponseBodyBytes": (
                    DECISION.MAXIMUM_TILE_RESPONSE_BYTES
                ),
                "exactResponseBytes": "32_times_tile_width",
                "onlyUniqueProofRequiredPaths": True,
                "deriveOnlyAfterSignedHeadVerification": True,
                "canonicalRequestOrder": (
                    "level_then_index_then_width_after_lookup"
                ),
                "requestBodyAllowed": False,
                "rangeHeaderAllowed": False,
            },
            "directHttpsOnly": True,
            "port": 443,
            "tlsCertificateValidationRequired": True,
            "tlsHostnameValidationRequired": True,
            "identityContentEncodingRequired": True,
            "acceptedStatusCode": 200,
            "ambientProxyAllowed": False,
            "redirectAllowed": False,
            "alternateMirrorAllowed": False,
            "authenticationChallengeHandlingAllowed": False,
            "authorizationHeaderAllowed": False,
            "proxyAuthorizationHeaderAllowed": False,
            "cookieAllowed": False,
            "clientCertificateAllowed": False,
            "credentialsAllowed": False,
            "queryAllowed": False,
            "fragmentAllowed": False,
            "retryAllowed": False,
            "latestEndpointAllowed": False,
            "secondLookupAllowed": False,
            "dataTileAllowed": False,
            "moduleProxyAllowed": False,
            "moduleOrZipRequestAllowed": False,
            "requestBodyAllowed": False,
            "rangeHeaderAllowed": False,
        },
        "strictVerificationContract": {
            "lookupRecordTargetLineCount": 2,
            "lineOrder": ["module_zip_h1", "go_mod_h1"],
            "goModH1MustEqualHeldEvidence": True,
            "moduleZipH1PrefixRequired": "h1:",
            "moduleZipH1CanonicalBase64DecodedBytes": 32,
            "emptyUnrelatedDuplicateExtraRecordAllowed": False,
            "carriageReturnNulOrTrailingRecordAllowed": False,
            "extraRecordRejectionClass": "GO-2026-4984",
            "pinnedKeySignedTreeRequiredBeforeTiles": True,
            "recordNumberMustBeWithinSignedTree": True,
            "maximumSignedTreeSize": 2**62,
            "recordLeafHashAlgorithm": "RFC6962_SHA256_0x00_prefix",
            "recordInclusionRequired": True,
            "rollbackRule": "new_tree_size_less_than_old_fails_consumed",
            "equalTreeRule": (
                "equal_size_requires_exact_old_root_and_empty_consistency_proof"
            ),
            "growthRule": "valid_old_to_new_rfc6962_consistency_required",
            "unusedDuplicateOrConflictingProofHashAllowed": False,
            "keyRotationAllowed": False,
            "trustOnFirstUseAllowed": False,
        },
        "authorityBindingContract": {
            "stableNoFollowReadBeforeClaim": True,
            "permitRawAndContentSha256Required": True,
            "checkerRawSha256Required": True,
            "runnerRawSha256Required": True,
            "sameBindingRequiredInClaimEvidenceReceiptFailureAndManifest": True,
            "runnerReversePinsCheckerRawSha256": True,
            "checkerPinsNormalizedRunnerSha256": (
                EXPECTED_RUNNER_NORMALIZED_SHA256
            ),
        },
        "absoluteResourceLimits": {
            "maximumTotalRequestCount": DECISION.MAXIMUM_REQUEST_COUNT,
            "maximumLookupRequestCount": 1,
            "maximumDerivedTileRequestCount": (
                DECISION.MAXIMUM_REQUEST_COUNT - 1
            ),
            "maximumAggregateResponseBodyBytes": (
                DECISION.MAXIMUM_AGGREGATE_RESPONSE_BYTES
            ),
            "maximumLookupResponseBodyBytes": (
                DECISION.MAXIMUM_LOOKUP_RESPONSE_BYTES
            ),
            "maximumTileResponseBodyBytes": (
                DECISION.MAXIMUM_TILE_RESPONSE_BYTES
            ),
            "maximumHeaderBytesPerResponse": DECISION.MAXIMUM_HEADER_BYTES,
            "maximumEvidenceJsonBytes": 1_048_576,
            "maximumReceiptFailureOrManifestBytes": 1_048_576,
            "perRequestDeadlineMilliseconds": (
                DECISION.PER_REQUEST_DEADLINE_MS
            ),
            "wholeAttemptDeadlineMilliseconds": (
                DECISION.WHOLE_ATTEMPT_DEADLINE_MS
            ),
            "wholeAttemptSignalTimerRequired": True,
            "deadlineChecksBeforeAndAfterNetworkProofAndPublication": True,
        },
        "filesystemWriteAuthority": {
            "claimWriteAuthorized": True,
            "ownerOnlyStagingWriteAuthorized": True,
            "metadataEvidenceWriteAuthorized": True,
            "successReceiptWriteAuthorized": True,
            "failureReceiptWriteAuthorized": True,
            "manifestWriteAuthorized": True,
            "failedStagingCleanupAuthorized": False,
            "failedStagingRetainedForForensics": True,
            "atomicNoReplaceFinalPublicationRequired": True,
            "newDirectoryMode": "0700",
            "newFileMode": "0600",
            "otherRepositoryWritesAuthorized": False,
            "sourceAcceptedDirectoryWriteAuthorized": False,
            "sourceWriteAuthorized": False,
            "sourceExtractionAuthorized": False,
        },
        "terminalContract": {
            "successReceiptPath": RECEIPT_PATH,
            "failureReceiptPath": FAILURE_PATH,
            "manifestPath": MANIFEST_PATH,
            "readbackReceiptPath": READBACK_PATH,
            "readbackManifestPath": READBACK_MANIFEST_PATH,
            "successAndFailureMutuallyExclusive": True,
            "manifestWrittenLast": True,
            "failureBeforeSuccessManifestOnly": True,
            "boundedFailureReasonCodesOnly": True,
            "rawResponseHeadersBodiesOrErrorsInTerminalJsonAllowed": False,
            "runnerMayClaimIndependentReadback": False,
            "independentReadbackRequired": True,
            "proofHashListsOrCanonicalAggregateRequired": True,
            "successStatus": (
                "identity_resolved_pending_independent_readback"
            ),
            "failureStatus": (
                "identity_resolution_failed_permit_consumed"
            ),
        },
        "networkAuthority": {
            "sumDbIdentityResolutionDnsAuthorized": True,
            "sumDbIdentityResolutionTcpAuthorized": True,
            "sumDbIdentityResolutionTlsAuthorized": True,
            "sumDbIdentityResolutionHttpsAuthorized": True,
            "authorizedHost": DECISION.LOOKUP_HOST,
            "authorizedPort": 443,
            "authorizedMaximumRequestCount": DECISION.MAXIMUM_REQUEST_COUNT,
            "productNetworkAuthorized": False,
            "relayOrP2PNetworkAuthorized": False,
            "runtimeNetworkAuthorized": False,
            "runtimeSocketAuthorized": False,
            "sourceAcquisitionNetworkAuthorized": False,
        },
        "executionBoundary": {
            "sumDbLookupAndDerivedHashTilesAuthorized": True,
            "metadataOnly": True,
            "sourceAcquisitionAuthorized": False,
            "moduleProxyAuthorized": False,
            "moduleOrZipAcquisitionAuthorized": False,
            "archiveExtractionAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "compileAuthorized": False,
            "goCommandAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "productRuntimeNetworkAuthorized": False,
            "externalAuthenticationRequired": False,
            "repositoryOwnerIdentityProofRequired": False,
            "accountLoginRequired": False,
            "credentialRequired": False,
            "clientCertificateRequired": False,
            "privateKeyRequired": False,
            "userSignatureRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "counterContract": {
            "initialValues": {
                "networkRequestAttemptCount": 0,
                "lookupResponseCompletedCount": 0,
                "signedHeadVerifiedCount": 0,
                "derivedUniqueTileCount": 0,
                "tileResponseCompletedCount": 0,
                "recordInclusionVerifiedCount": 0,
                "treeConsistencyVerifiedCount": 0,
                "metadataPublicationCount": 0,
                "subprocessCount": 0,
            },
            "successRules": {
                "networkRequestAttemptCount": (
                    "1_plus_exact_derived_unique_tile_count"
                ),
                "lookupResponseCompletedCount": 1,
                "signedHeadVerifiedCount": 1,
                "tileResponseCompletedCount": (
                    "exact_derived_unique_tile_count"
                ),
                "recordInclusionVerifiedCount": 1,
                "treeConsistencyVerifiedCount": 1,
                "metadataPublicationCount": 1,
            },
            "safeNumericObservationsOnly": True,
        },
        "interpreterIsolationContract": {
            "isolatedInterpreterRequired": True,
            "sitePackagesAllowed": False,
            "environmentOverridesAllowed": False,
            "bytecodeWritesAllowed": False,
            "processUmask": "077",
            "permitCheckerCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                THIS_CHECKER_PATH,
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
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW,
        },
        "toolBindings": tools,
        "nonClaims": [
            "the unresolved ZIP H1 is not present in this permit package",
            "a signed tree head alone is not record inclusion proof",
            "metadata identity resolution is not source acquisition",
            "success does not establish dependency closure review or release",
        ],
        "result": (
            "exact_auth_free_one_use_sumdb_lookup_and_derived_tiles_"
            "authorized_not_consumed"
        ),
        "nextAction": "execute_bound_sumdb_identity_resolution_once",
    }


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    context = PermitContext(ROOT, include_permit=verify_disk)
    try:
        expected = content_bound(expected_payload(context))
        if verify_disk:
            verify_bound_bytes(
                context.package.raw[PERMIT_PATH],
                expected,
                "E_PERMIT",
            )
        context.final_barrier()
        return expected, {
            "documentType": (
                "aetherlink.public-checksum-identity-resolution-"
                "execution-permit-check"
            ),
            "schemaVersion": "1.0",
            "status": "authorized_not_consumed",
            "validationPassed": True,
            "networkAuthorized": True,
            "authorizedHost": DECISION.LOOKUP_HOST,
            "maximumRequestCount": DECISION.MAXIMUM_REQUEST_COUNT,
            "claimExists": False,
            "sourceAcquisitionAuthorized": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise PermitError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        parser.add_argument("--preflight", action="store_true")
        parser.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        require(
            not (args.preflight and args.print_expected),
            "E_ARGUMENT",
        )
        expected, summary = evaluate(not args.print_expected)
        sys.stdout.buffer.write(
            canonical_bytes(expected if args.print_expected else summary)
        )
        return 0
    except PermitError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.public-checksum-identity-resolution-"
                        "execution-permit-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "networkAuthorized": False,
                    "fileWriteAuthorized": False,
                    "sourceAcquisitionAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.public-checksum-identity-resolution-"
                        "execution-permit-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "networkAuthorized": False,
                    "fileWriteAuthorized": False,
                    "sourceAcquisitionAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
