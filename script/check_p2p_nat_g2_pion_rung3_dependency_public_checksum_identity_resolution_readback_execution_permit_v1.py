#!/usr/bin/env python3
"""Validate the one-use offline SumDB identity readback execution permit."""

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
    raise RuntimeError("readback permit checker requires `python3 -I -B -S`")

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_readback_v1_once.py"
)
READBACK_CLAIM_PATH = (
    f"{DEPENDENCY_ROOT}/.wave-3-kr-pty-sumdb-identity-readback-v1.claim"
)
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-manifest-v1.json"
)
ATTEMPT_ID = "02e6be7ab4a6ebb6d8beba2142c81406"
EXPECTED_READER_RAW = (
    "474018e98b351ae0dea7431cae0957296fca9c182d3233f37b4d794b1e9b7c77"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "cb9be4f79d0984438d0489a4c5f8dd081d7338abfb5f9a7e3699fac075dcd394"
)
MAXIMUM_FILE_BYTES = 4 * 1024 * 1024
TARGET_MODULE = "github.com/kr/pty"
TARGET_VERSION = "v1.1.1"
TARGET_MOD_H1 = "h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ="
TARGET_ZIP_H1 = "h1:VkoXIwSboBpnk99O/KFauAEILuNHv5DVFKZMBN/gUgw="
SUMDB_VERIFIER_KEY = (
    "sum.golang.org+033de0ae+"
    "Ac4zctda0e5eza+HJyk9SxEdh+s3Ux18htTTAD8OuAn8"
)
OLD_TREE_SIZE = 57_871_495
OLD_ROOT_HASH_BASE64 = "CXAe1gevwtmEqZ3aCCTvv6+nJY5F29T4UGHfB73rJTo="


def frozen(
    path: str,
    digest: str,
    size: int,
    mode: str,
    owner_uid: int = 501,
    link_count: int = 1,
) -> dict[str, Any]:
    return {
        "path": path,
        "rawSha256": digest,
        "bytes": size,
        "mode": mode,
        "ownerUid": owner_uid,
        "linkCount": link_count,
    }


EXECUTION_AUTHORITY = [
    frozen(
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "execution-permit-v1.json",
        "6d0669afbc24509609360952c3010726d71492832df69dabb1fccf0aaf1f2197",
        13_134,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_execution_permit_v1.py",
        "14b628e788dcd216e9102596f95681dfe1fbb6e97e6b6170ece19fee6499ab6c",
        34_410,
        "0644",
    ),
    frozen(
        "script/resolve_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_v1_once.py",
        "c2771f68a8d73076e3175b9791f7b03a988c2b0e4f289bad7a352c110debe25d",
        50_459,
        "0644",
    ),
]
EXECUTION_CLAIM = frozen(
    f"{DEPENDENCY_ROOT}/.wave-3-kr-pty-sumdb-identity-v1.claim",
    "f38054ca652a53d56e30766fc869728a14b42ac5dd8e20943f391a96a374d288",
    1_098,
    "0600",
)
EVIDENCE_DIRECTORY_PATH = (
    f"{DEPENDENCY_ROOT}/wave-3-kr-pty-sumdb-identity-v1/evidence"
)
EVIDENCE_DIRECTORY = {
    "path": EVIDENCE_DIRECTORY_PATH,
    "mode": "0700",
    "ownerUid": 501,
    "linkCount": 13,
}
EVIDENCE_FILES = [
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/evidence.json",
        "043e1f13a9c7c13624f3de622adff99965ddeee7ef41b539b41d1068cfd7f204",
        7_615,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/lookup.response",
        "a091017a6258e8994466556d69cdfe0d2f2255dbe04adfd706f582806204cd34",
        346,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-001-433f370775408752.bin",
        "a683cc7097dd2305c76c2876650c12041496b8fe82aad2000ee9a3e40d2485e2",
        8_192,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-002-a942e5993ab9ac53.bin",
        "3b186038695f392b628e89576b24c7d4c081ffd421b22343e68755ae0f64ac3a",
        8_192,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-003-11e688bd3f4b0938.bin",
        "231e112efd062aabddbc853b6c7df64770a4004b576743203a83ffafb451b74d",
        3_584,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-004-784dcfa494c65600.bin",
        "91c70bde50c7f65306f9ec9680e94e6eb64be27682e4ab1575a19d1d8ddf175b",
        8_192,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-005-46424d628236beba.bin",
        "eb451cb9245be0e322e5406fefe779df43746579228d93a2386c90bd173933f0",
        8_192,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-006-27561b7ea9397973.bin",
        "f1c008dfc4bb3302a4fd02ba16b27a4b47b7a151b33a339231364d9425239702",
        5_408,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-007-39dff99d869ebfa2.bin",
        "e31db8423668ce64d4153f4edea5cbb473825e7ba7aae501130c9c1f83948333",
        8_192,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-008-17efcc63092f321b.bin",
        "a4d3e65a383cf02ef96b63e850890a093e8e451b8011103ad9b662319eed4074",
        3_712,
        "0600",
    ),
    frozen(
        f"{EVIDENCE_DIRECTORY_PATH}/tile-009-63afe683110cb0e6.bin",
        "0572a23f83541b9701b37b8862c189ca3a9c83e08f183cde38ccdf894f43a375",
        96,
        "0600",
    ),
]
EXECUTION_RECEIPT = frozen(
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "receipt-v1.json",
    "f51c1caa62bb22bafda09d856bb7c1e9b3f0d4ee527f83dd0dcebe9ee6a18b36",
    1_806,
    "0600",
)
EXECUTION_MANIFEST = frozen(
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "manifest-v1.json",
    "e45d49d459cd7542e2544d9d9607a5f040f8af95c24a999780ed08d64ee1577b",
    1_547,
    "0600",
)
ALL_FROZEN_FILES = [
    *EXECUTION_AUTHORITY,
    EXECUTION_CLAIM,
    *EVIDENCE_FILES,
    EXECUTION_RECEIPT,
    EXECUTION_MANIFEST,
]


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
            parse_float=lambda _: (_ for _ in ()).throw(
                PermitError("E_JSON")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                PermitError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    require("contentBinding" not in payload, "E_CONTENT")
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def verify_bound_bytes(raw: bytes, expected: Mapping[str, Any]) -> None:
    observed = strict_json(raw)
    require(raw == canonical_bytes(observed), "E_CANONICAL")
    binding = observed.get("contentBinding")
    require(type(binding) is dict, "E_CONTENT")
    unbound = dict(observed)
    del unbound["contentBinding"]
    require(
        binding
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": sha256(canonical_bytes(unbound)),
        }
        and observed == expected,
        "E_CONTENT",
    )


class HeldFile:
    def __init__(
        self,
        path: Path,
        expected: Mapping[str, Any] | None = None,
    ) -> None:
        self.path = path
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        self.fd = os.open(path, flags)
        self.before = os.fstat(self.fd)
        require(stat.S_ISREG(self.before.st_mode), "E_SHAPE")
        require(self.before.st_nlink == 1, "E_SHAPE")
        require(0 < self.before.st_size <= MAXIMUM_FILE_BYTES, "E_SIZE")
        chunks: list[bytes] = []
        remaining = self.before.st_size
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(self.fd, 1), "E_READ")
        self.raw = b"".join(chunks)
        self.check()
        if expected is not None:
            self.verify_expected(expected)

    def check(self) -> None:
        require(os.fstat(self.fd) == self.before, "E_CHANGED")

    def verify_expected(self, expected: Mapping[str, Any]) -> None:
        require(
            str(self.path.relative_to(ROOT)) == expected["path"]
            and sha256(self.raw) == expected["rawSha256"]
            and len(self.raw) == expected["bytes"]
            and f"{stat.S_IMODE(self.before.st_mode):04o}" == expected["mode"]
            and self.before.st_uid == expected["ownerUid"]
            and self.before.st_nlink == expected["linkCount"],
            "E_FROZEN",
        )

    def close(self) -> None:
        os.close(self.fd)


class PermitContext:
    def __init__(self, include_permit: bool) -> None:
        self.held: list[HeldFile] = []
        self.raw: dict[str, bytes] = {}
        package_paths = [
            READER_PATH,
            THIS_CHECKER_PATH,
            THIS_TESTS_PATH,
            RECORDER_PATH,
            RECORDER_TESTS_PATH,
        ]
        if include_permit:
            package_paths.append(PERMIT_PATH)
        expected_map = {row["path"]: row for row in ALL_FROZEN_FILES}
        try:
            for path in [*package_paths, *expected_map]:
                item = HeldFile(ROOT / path, expected_map.get(path))
                self.held.append(item)
                self.raw[path] = item.raw
            self.evidence_fd = os.open(
                ROOT / EVIDENCE_DIRECTORY_PATH,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_CLOEXEC
                | getattr(os, "O_NOFOLLOW", 0),
            )
            info = os.fstat(self.evidence_fd)
            require(
                stat.S_ISDIR(info.st_mode)
                and f"{stat.S_IMODE(info.st_mode):04o}"
                == EVIDENCE_DIRECTORY["mode"]
                and info.st_uid == EVIDENCE_DIRECTORY["ownerUid"]
                and info.st_nlink == EVIDENCE_DIRECTORY["linkCount"],
                "E_INVENTORY",
            )
            expected_names = {
                Path(row["path"]).name for row in EVIDENCE_FILES
            }
            require(set(os.listdir(self.evidence_fd)) == expected_names, "E_INVENTORY")
            self.evidence_before = info
            for reserved in (
                READBACK_CLAIM_PATH,
                READBACK_RECEIPT_PATH,
                READBACK_MANIFEST_PATH,
            ):
                require(not (ROOT / reserved).exists(), "E_CONSUMED")
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        for item in self.held:
            item.check()
        require(
            os.fstat(self.evidence_fd) == self.evidence_before,
            "E_CHANGED",
        )
        expected_names = {Path(row["path"]).name for row in EVIDENCE_FILES}
        require(set(os.listdir(self.evidence_fd)) == expected_names, "E_INVENTORY")

    def close(self) -> None:
        for item in getattr(self, "held", ()):
            try:
                item.close()
            except BaseException:
                pass
        if hasattr(self, "evidence_fd"):
            try:
                os.close(self.evidence_fd)
            except BaseException:
                pass


def normalized_recorder_bytes(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    pattern = (
        r'EXPECTED_READBACK_CHECKER_RAW = "[0-9a-f]{64}"'
    )
    require(len(re.findall(pattern, text)) == 1, "E_RECORDER")
    return re.sub(
        pattern,
        'EXPECTED_READBACK_CHECKER_RAW = "' + "0" * 64 + '"',
        text,
        count=1,
    ).encode()


def validate_recorder_semantics(recorder_raw: bytes, checker_raw: bytes) -> None:
    try:
        source = recorder_raw.decode("utf-8", errors="strict")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise PermitError("E_RECORDER") from error
    imports: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
    forbidden_imports = {
        "http",
        "socket",
        "ssl",
        "urllib",
        "requests",
        "subprocess",
    }
    require(not imports.intersection(forbidden_imports), "E_RECORDER")
    require(
        {
            "load_readback_checker",
            "verify_signed_tree_note",
            "parse_lookup_record",
            "derive_independent_plan",
            "verify_inclusion_path",
            "verify_consistency_path",
            "verify_snapshot",
            "create_readback_claim",
            "atomic_publish",
            "preflight",
            "execute",
        }
        <= functions,
        "E_RECORDER",
    )
    for forbidden in (
        "http.client",
        "HTTPSConnection",
        "urlopen",
        "socket.",
        "subprocess",
        "os.system",
        "proxy.golang.org",
        "sum.golang.org/lookup",
        "importlib",
        "identity_v1_once",
    ):
        require(forbidden not in source, "E_RECORDER")
    for required in (
        "os.O_EXCL",
        'getattr(os, "O_NOFOLLOW", 0)',
        "os.fsync",
        "renameatx_np",
        "verify_ed25519_signature",
        "derive_independent_plan",
    ):
        require(required in source, "E_RECORDER")
    pin = re.findall(
        r'EXPECTED_READBACK_CHECKER_RAW = "([0-9a-f]{64})"',
        source,
    )
    require(pin == [sha256(checker_raw)], "E_RECORDER")
    require(
        sha256(normalized_recorder_bytes(recorder_raw))
        == EXPECTED_RECORDER_NORMALIZED_SHA256,
        "E_RECORDER",
    )


def expected_payload_from_package(
    package_raw: Mapping[str, bytes],
) -> dict[str, Any]:
    """Build the permit without opening any frozen execution input."""
    require(sha256(package_raw[READER_PATH]) == EXPECTED_READER_RAW, "E_READER")
    validate_recorder_semantics(
        package_raw[RECORDER_PATH],
        package_raw[THIS_CHECKER_PATH],
    )
    tools = [
        {"path": path, "rawSha256": sha256(package_raw[path])}
        for path in (
            THIS_CHECKER_PATH,
            THIS_TESTS_PATH,
            RECORDER_PATH,
            RECORDER_TESTS_PATH,
        )
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-public-checksum-identity-resolution-"
            "readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-kr-pty-v1.1.1-public-checksum-"
            "identity-resolution-readback-execution-permit-v1"
        ),
        "recordedDate": "2026-07-24",
        "status": "authorized_not_consumed",
        "executionSnapshot": {
            "attemptId": ATTEMPT_ID,
            "executionAuthority": EXECUTION_AUTHORITY,
            "executionPermitContentSha256": (
                "41f2050c3e8a702da66adfdf5c890604756c7fa0e708d4b9fb062c8f5693a7fb"
            ),
            "executionClaim": EXECUTION_CLAIM,
            "evidenceDirectory": {
                **EVIDENCE_DIRECTORY,
                "exactFileCount": 11,
                "files": EVIDENCE_FILES,
            },
            "executionReceipt": EXECUTION_RECEIPT,
            "executionManifest": EXECUTION_MANIFEST,
        },
        "target": {
            "module": TARGET_MODULE,
            "version": TARGET_VERSION,
            "goModH1": TARGET_MOD_H1,
            "moduleZipH1": TARGET_ZIP_H1,
        },
        "trustedCheckpoint": {
            "verifierKey": SUMDB_VERIFIER_KEY,
            "oldTreeSize": OLD_TREE_SIZE,
            "oldRootHashBase64": OLD_ROOT_HASH_BASE64,
        },
        "verificationContract": {
            "allFrozenFilesReopenedNoFollowAndHeld": True,
            "exactPathSha256BytesModeOwnerAndLinkCountRequired": True,
            "exactEvidenceDirectoryInventoryRequired": True,
            "canonicalJsonAndContentBindingsRecomputed": True,
            "attemptIdMustMatchEveryExecutionArtifact": True,
            "executionAuthorityBindingMustMatchEveryExecutionArtifact": True,
            "strictTwoLineLookupRecordRequired": True,
            "pinnedSumDbSignedTreeVerificationRequired": True,
            "independentlyDerivedTilePlanRequired": True,
            "tilePathBodyLengthAndSha256Required": True,
            "rfc6962RecordInclusionRecomputed": True,
            "rfc6962OldToNewConsistencyRecomputed": True,
            "proofListsAndCanonicalAggregateRecomputed": True,
            "countersAndAggregateBytesRecomputed": True,
            "successFailureTerminalExclusivityRequired": True,
            "executionReceiptManifestLinkageRequired": True,
            "executionCheckerOrRunnerInvocationAllowed": False,
            "executionRunnerImportAllowed": False,
        },
        "oneUseConsumption": {
            "claimPath": READBACK_CLAIM_PATH,
            "initialState": "authorized_not_consumed",
            "claimCreatedExclusivelyBeforeFrozenInputReadback": True,
            "claimMode": "0600",
            "claimFsyncedBeforeFrozenInputReadback": True,
            "claimContainsRandomReadbackAttemptId": True,
            "claimPersistsAfterSuccessFailureOrUncertainty": True,
            "secondExecutionAllowed": False,
            "retryAllowed": False,
            "resumeAllowed": False,
            "replacementAllowed": False,
            "backfillAllowed": False,
        },
        "outputContract": {
            "receiptPath": READBACK_RECEIPT_PATH,
            "manifestPath": READBACK_MANIFEST_PATH,
            "receiptWrittenBeforeManifest": True,
            "manifestWrittenLast": True,
            "atomicNoReplaceRequired": True,
            "newFileMode": "0600",
            "successOutputBeforeAllVerificationAllowed": False,
            "failureOutputAuthorized": False,
        },
        "authorityBindingContract": {
            "permitRawAndContentSha256Required": True,
            "checkerRawSha256Required": True,
            "recorderRawSha256Required": True,
            "sameBindingRequiredInClaimReceiptAndManifest": True,
            "recorderReversePinsCheckerRawSha256": True,
            "checkerPinsNormalizedRecorderSha256": (
                EXPECTED_RECORDER_NORMALIZED_SHA256
            ),
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
            "recorderPreflightCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RECORDER_PATH,
                "--preflight",
            ],
            "recorderExecuteCommand": [
                "python3",
                "-I",
                "-B",
                "-S",
                RECORDER_PATH,
                "--execute",
            ],
        },
        "writeAuthority": {
            "readbackClaimWriteAuthorized": True,
            "readbackReceiptWriteAuthorized": True,
            "readbackManifestWriteAuthorized": True,
            "temporarySameDirectoryPublicationWriteAuthorized": True,
            "failedTemporaryPublicationCleanupAuthorized": True,
            "otherRepositoryWritesAuthorized": False,
            "frozenInputWritesAuthorized": False,
            "sourceWritesAuthorized": False,
        },
        "executionBoundary": {
            "offlineReadbackOnly": True,
            "networkAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "proxyAuthorized": False,
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
            "sourceAcquisitionAuthorized": False,
            "moduleOrZipAcquisitionAuthorized": False,
            "archiveExtractionAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "productRuntimeAuthorized": False,
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW,
        },
        "toolBindings": tools,
        "result": "exact_offline_readback_authorized_not_consumed",
        "nextAction": "execute_bound_offline_readback_once",
        "nonClaims": [
            "readback success is not source acquisition authority",
            "readback success is not dependency closure or release approval",
            "the consumed execution permit is not re-executed by readback",
        ],
    }


def expected_payload(context: PermitContext) -> dict[str, Any]:
    context.final_barrier()
    return expected_payload_from_package(context.raw)


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    context = PermitContext(include_permit=verify_disk)
    try:
        expected = content_bound(expected_payload(context))
        if verify_disk:
            verify_bound_bytes(context.raw[PERMIT_PATH], expected)
        context.final_barrier()
        return expected, {
            "documentType": (
                "aetherlink.sumdb-identity-resolution-readback-"
                "execution-permit-check"
            ),
            "schemaVersion": "1.0",
            "status": "authorized_not_consumed",
            "validationPassed": True,
            "attemptId": ATTEMPT_ID,
            "frozenEvidenceFileCount": 11,
            "networkAuthorized": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "sourceAcquisitionAuthorized": False,
            "claimExists": False,
        }
    finally:
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise PermitError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--preflight", action="store_true")
        mode.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        expected, summary = evaluate(not args.print_expected)
        output = expected if args.print_expected else summary
        sys.stdout.buffer.write(canonical_bytes(output))
        return 0
    except PermitError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-readback-"
                        "execution-permit-check-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "networkAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                    "sourceAcquisitionAuthorized": False,
                }
            )
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-readback-"
                        "execution-permit-check-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "networkAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                    "sourceAcquisitionAuthorized": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
