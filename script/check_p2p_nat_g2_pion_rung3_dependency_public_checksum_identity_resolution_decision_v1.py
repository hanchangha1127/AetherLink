#!/usr/bin/env python3
"""Validate the decision-only public checksum identity-resolution design."""

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
    raise RuntimeError("identity decision checker requires `python3 -I -B -S`")

import argparse
import hashlib
import importlib.util
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
DECISION_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "decision-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "decision-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_decision_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_decision_v1.py"
)
WAVE3_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v1.py"
)
RUNG2_CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung2_acquisition_authority.py"

EXPECTED_WAVE3_RAW = {
    (
        f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
        "decision-wave3-v1.json"
    ): "c2a1e1d7c0e4936edb8eb20c92d62859c9ee047da4adf9f31a0a458363df732e",
    (
        f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
        "decision-wave3-v1.md"
    ): "9ed3ad459aa88c2ff559c8bfb96689dd5e3ca16be3cbe5a3e62d72c9aabb43fd",
    WAVE3_CHECKER_PATH: (
        "3f16e928847005bb6b1a328345738dd3f1cae7a372f3dc6c900d87e80e802cf4"
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v1.py"
    ): "7bab19d302cc488c1492f95cacbe7d60b710c72d9a32f004c9fb74f1eae91acd",
}
WAVE3_DECISION_PATH = next(iter(EXPECTED_WAVE3_RAW))
EXPECTED_WAVE3_CONTENT = (
    "e31e1bb96802082047e1a9c9d1c1cb43d8a8415f72294282d3b97c97b1cafc2a"
)

RUNG2_BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-two"
)
RUNG2_PROVENANCE_PATH = f"{RUNG2_BASE}/provenance-observation-v1.json"
RUNG2_DECISION_PATH = f"{RUNG2_BASE}/source-acquisition-decision-v1.json"
RUNG2_TESTS_PATH = "script/test_p2p_nat_g2_pion_rung2_acquisition_authority.py"
EXPECTED_RUNG2_RAW = {
    RUNG2_PROVENANCE_PATH: (
        "6b0b55023849480c0a7ea05449b98cc2e27d9fd1d704c794aace9e04d0afe4f0"
    ),
    RUNG2_DECISION_PATH: (
        "8a7ec91354b27ffc4cdf8dcce2f6baa93a10dfadfd7c896266ce42b1ae854c10"
    ),
    RUNG2_CHECKER_PATH: (
        "b0522ab4476822b9e2b0d3e3bef1e001d7371b4088c263af851d0fa067787ef4"
    ),
    RUNG2_TESTS_PATH: (
        "f501d73b1ac344944394e81f0a2829ac3edd8c547210a5b6eed72df0a3dc95e2"
    ),
}

EXPECTED_READER_RAW = (
    "57c8df5364e577f85f88e4da0538ddd3b6a318ae62b71ea2a894983bedfd85f8"
)
TARGET_MODULE = "github.com/kr/pty"
TARGET_VERSION = "v1.1.1"
TARGET_MOD_H1 = "h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ="
LOOKUP_HOST = "sum.golang.org"
LOOKUP_PATH = "/lookup/github.com/kr/pty@v1.1.1"
LOOKUP_URL = f"https://{LOOKUP_HOST}{LOOKUP_PATH}"
SUMDB_VERIFIER_KEY = (
    "sum.golang.org+033de0ae+"
    "Ac4zctda0e5eza+HJyk9SxEdh+s3Ux18htTTAD8OuAn8"
)
OLD_TREE_SIZE = 57_871_495
OLD_ROOT_HASH_BASE64 = "CXAe1gevwtmEqZ3aCCTvv6+nJY5F29T4UGHfB73rJTo="
OLD_SIGNATURE_BASE64 = (
    "Az3grl3EvFerct68O5eNpkq2v5oVwQN6i7f9wO42XflhUmA6BqeLeAxOBU8DSuxB3"
    "yTRtGL8ithf0vSqbu5PqDWnYAs="
)
OLD_SIGNED_TREE_TEXT_SHA256 = (
    "5192e92f2cbd4744e25a15c8617b86057400f8828d32b27e9efcf1b90bc65b45"
)
MAXIMUM_REQUEST_COUNT = 129
MAXIMUM_AGGREGATE_RESPONSE_BYTES = 4 * 1024 * 1024
MAXIMUM_LOOKUP_RESPONSE_BYTES = 64 * 1024
MAXIMUM_TILE_RESPONSE_BYTES = 8 * 1024
MAXIMUM_HEADER_BYTES = 16 * 1024
PER_REQUEST_DEADLINE_MS = 15_000
WHOLE_ATTEMPT_DEADLINE_MS = 120_000
TILE_HEIGHT = 8
FULL_TILE_WIDTH = 256
TILE_PATH_REGEX = (
    r"^/tile/8/(0|[1-9][0-9]*)/"
    r"(?:x[0-9]{3}/)*[0-9]{3}"
    r"(?:[.]p/(?:[1-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))?$"
)
TILE_PATH_PATTERN = re.compile(TILE_PATH_REGEX)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 4 * 1024 * 1024

DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
CLAIM_PATH = (
    f"{DEPENDENCY_ROOT}/.wave-3-kr-pty-sumdb-identity-v1.claim"
)
STAGING_PREFIX = ".wave-3-kr-pty-sumdb-identity-v1-staging-"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-3-kr-pty-sumdb-identity-v1"
FINAL_EVIDENCE_PATH = f"{FINAL_ROOT}/evidence"
FUTURE_DOCS = (
    (
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "execution-permit-v1.json"
    ),
    (
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "execution-permit-v1.md"
    ),
    (
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "receipt-v1.json"
    ),
    (
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "failure-v1.json"
    ),
    (
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "manifest-v1.json"
    ),
    (
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "readback-v1.json"
    ),
    (
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "readback-manifest-v1.json"
    ),
)


class DecisionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(value: bool, code: str) -> None:
    if not value:
        raise DecisionError(code)


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
            parse_float=lambda _: (_ for _ in ()).throw(DecisionError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(
                DecisionError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    require("contentBinding" not in value, "E_CONTENT")
    digest = sha256(canonical_bytes(value))
    value["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": digest,
    }
    return value


def verify_decision_bytes(raw: bytes, expected: Mapping[str, Any]) -> None:
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
    require(raw == canonical_bytes(expected), "E_DECISION")
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


WAVE3 = load_module(
    "identity_resolution_wave3_root",
    WAVE3_CHECKER_PATH,
    EXPECTED_WAVE3_RAW[WAVE3_CHECKER_PATH],
)
RUNG2 = load_module(
    "identity_resolution_rung2_root",
    RUNG2_CHECKER_PATH,
    EXPECTED_RUNG2_RAW[RUNG2_CHECKER_PATH],
)


def checkpoint_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": MAXIMUM_TOOL_BYTES,
            "ownerOnly": False,
        }
        for path, digest in EXPECTED_RUNG2_RAW.items()
    ]


def package_bindings(include_decision: bool) -> list[dict[str, Any]]:
    paths = [READER_PATH, THIS_CHECKER_PATH, THIS_TESTS_PATH]
    if include_decision:
        paths.append(DECISION_PATH)
    return [
        {
            "path": path,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES
                if path.startswith("docs/")
                else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        for path in paths
    ]


class DecisionContext:
    def __init__(self, root: Path, *, include_decision: bool) -> None:
        self.root = root
        self.wave3 = None
        self.checkpoint = None
        self.package = None
        try:
            self.wave3 = WAVE3.DecisionContext(root, include_decision=True)
            held_type = self.wave3.lineage.authority.decision_checker.HeldSet
            self.checkpoint = held_type(root, checkpoint_bindings())
            self.package = held_type(root, package_bindings(include_decision))
            RUNG2.validate_repository()
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        require(
            self.wave3 is not None
            and self.checkpoint is not None
            and self.package is not None,
            "E_CONTEXT",
        )
        self.wave3.final_barrier()
        self.checkpoint.final_barrier()
        self.package.final_barrier()
        recovery = WAVE3.PERMIT.DECISION.V2.RECOVERY
        namespace = self.wave3.lineage.namespace
        for path in (CLAIM_PATH, FINAL_ROOT, *FUTURE_DOCS):
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
        self.checkpoint.final_barrier()
        self.wave3.final_barrier()

    def close(self) -> None:
        for held in (self.package, self.checkpoint, self.wave3):
            if held is not None:
                try:
                    held.close()
                except BaseException:
                    pass


def valid_tile_path(path: str) -> bool:
    if type(path) is not str or TILE_PATH_PATTERN.fullmatch(path) is None:
        return False
    return (
        "/data/" not in path
        and "/lookup/" not in path
        and "/latest" not in path
        and "@" not in path
    )


def validate_checkpoint(context: DecisionContext) -> None:
    raw = context.checkpoint.raw
    for path, digest in EXPECTED_RUNG2_RAW.items():
        require(path in raw and sha256(raw[path]) == digest, "E_CHECKPOINT")
    provenance = strict_json(raw[RUNG2_PROVENANCE_PATH])
    checksum = provenance["checksumDatabaseObservation"]
    signed = checksum["signedTree"]
    local = checksum["localVerification"]
    require(
        checksum["verifierKey"] == SUMDB_VERIFIER_KEY
        and signed["treeSize"] == OLD_TREE_SIZE
        and signed["rootHashBase64"] == OLD_ROOT_HASH_BASE64
        and signed["signatureBase64"] == OLD_SIGNATURE_BASE64
        and signed["signedTreeTextSha256"]
        == OLD_SIGNED_TREE_TEXT_SHA256
        and checksum["status"]
        == "signed_tree_and_record_inclusion_locally_verified"
        and local["ed25519SignedTreeVerified"] is True
        and local["rfc6962InclusionProofVerified"] is True
        and local["recordHashRecomputed"] is True
        and local["verifierKeyHashRecomputed"] is True,
        "E_CHECKPOINT",
    )


def expected_payload(context: DecisionContext) -> dict[str, Any]:
    context.final_barrier()
    validate_checkpoint(context)
    wave3_raw = context.wave3.package.raw
    for path, digest in EXPECTED_WAVE3_RAW.items():
        require(path in wave3_raw and sha256(wave3_raw[path]) == digest, "E_WAVE3")
    wave3 = strict_json(wave3_raw[WAVE3_DECISION_PATH])
    gap = wave3["identityGap"]
    require(
        wave3["contentBinding"]["sha256"] == EXPECTED_WAVE3_CONTENT
        and wave3["wave"]["identityRecordCount"] == 31
        and wave3["wave"]["requiredIdentityRecordCount"] == 32
        and wave3["wave"]["acquisitionReady"] is False
        and gap["module"] == TARGET_MODULE
        and gap["version"] == TARGET_VERSION
        and gap["heldGoModH1"] == TARGET_MOD_H1
        and gap["missingIdentity"] == "module_zip_h1"
        and gap["missingValueMayBeGuessedOrInferred"] is False
        and gap["sumDbLookupPerformed"] is False,
        "E_GAP",
    )
    package_raw = context.package.raw
    require(
        sha256(package_raw[READER_PATH]) == EXPECTED_READER_RAW,
        "E_READER",
    )
    tool_bindings = [
        {"path": path, "rawSha256": sha256(package_raw[path])}
        for path in (THIS_CHECKER_PATH, THIS_TESTS_PATH)
    ]
    wave3_bindings = [
        {"path": path, "rawSha256": digest}
        for path, digest in EXPECTED_WAVE3_RAW.items()
    ]
    checkpoint_bindings_value = [
        {"path": path, "rawSha256": digest}
        for path, digest in EXPECTED_RUNG2_RAW.items()
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-bounded-dependency-public-checksum-"
            "identity-resolution-decision"
        ),
        "schemaVersion": "1.0",
        "decisionId": (
            "g2-pion-rung3-kr-pty-v1.1.1-public-checksum-"
            "identity-resolution-decision-v1"
        ),
        "recordedDate": "2026-07-24",
        "status": (
            "strict_deterministic_adaptive_sumdb_fsm_selected_"
            "execution_not_authorized"
        ),
        "wave3Binding": {
            "files": wave3_bindings,
            "decisionContentSha256": EXPECTED_WAVE3_CONTENT,
            "requiredStatus": (
                "wave3_exact_16_frontier_identity_classified_"
                "15_complete_1_blocked_acquisition_not_authorized"
            ),
            "identityRecordCount": 31,
            "requiredIdentityRecordCount": 32,
            "acquisitionReady": False,
        },
        "targetIdentityGap": {
            "module": TARGET_MODULE,
            "version": TARGET_VERSION,
            "heldGoModH1": TARGET_MOD_H1,
            "moduleZipH1": None,
            "missingIdentity": "module_zip_h1",
            "unknownValueHardcoded": False,
            "guessOrInferenceAllowed": False,
        },
        "trustedChecksumDatabaseCheckpoint": {
            "name": LOOKUP_HOST,
            "files": checkpoint_bindings_value,
            "existingValidatorReverified": True,
            "verifierKey": SUMDB_VERIFIER_KEY,
            "keyRotationAllowed": False,
            "trustOnFirstUseAllowed": False,
            "treeSize": OLD_TREE_SIZE,
            "rootHashBase64": OLD_ROOT_HASH_BASE64,
            "signatureBase64": OLD_SIGNATURE_BASE64,
            "signedTreeTextSha256": OLD_SIGNED_TREE_TEXT_SHA256,
            "signedTreeVerified": True,
            "recordInclusionVerified": True,
            "trustRole": (
                "old_signed_consistency_checkpoint_for_future_"
                "adaptive_identity_resolution"
            ),
        },
        "selectedFutureDesign": {
            "mode": "strict_deterministic_adaptive_one_use_sumdb_fsm",
            "designOnly": True,
            "executionPermitPrepared": False,
            "executionPermitGranted": False,
            "singleClaimCoversLookupAndDerivedTiles": True,
            "claimMustBeDurableBeforeNetwork": True,
            "claimPersistsAfterAnyNetworkAttempt": True,
            "automaticRetryAllowed": False,
            "resumeAllowed": False,
            "backfillAllowed": False,
            "alternateMirrorAllowed": False,
            "requestStateMachine": [
                "claimed_no_network",
                "lookup_attempted",
                "lookup_body_held",
                "signed_head_verified_before_tile_requests",
                "unique_proof_tiles_derived",
                "derived_tiles_attempted_once",
                "offline_proof_verification",
                "metadata_publication_or_bounded_failure",
            ],
        },
        "plannedLookupRequest": {
            "requestOrdinal": 1,
            "requestCount": 1,
            "method": "GET",
            "scheme": "https",
            "host": LOOKUP_HOST,
            "port": 443,
            "path": LOOKUP_PATH,
            "url": LOOKUP_URL,
            "acceptedStatusCode": 200,
            "tlsCertificateValidationRequired": True,
            "tlsHostnameValidationRequired": True,
            "identityContentEncodingRequired": True,
            "maximumResponseBodyBytes": MAXIMUM_LOOKUP_RESPONSE_BYTES,
            "maximumHeaderBytes": MAXIMUM_HEADER_BYTES,
            "redirectAllowed": False,
            "ambientProxyAllowed": False,
            "authenticationChallengeHandlingAllowed": False,
            "authorizationHeaderAllowed": False,
            "proxyAuthorizationHeaderAllowed": False,
            "cookieAllowed": False,
            "clientCertificateAllowed": False,
            "credentialsAllowed": False,
            "queryAllowed": False,
            "fragmentAllowed": False,
            "retryAllowed": False,
        },
        "strictLookupRecordContract": {
            "recordNumberRequired": True,
            "recordNumberMinimum": 0,
            "recordNumberMustBeLessThanSignedTreeSize": True,
            "exactTargetLineCount": 2,
            "moduleZipLineTemplate": (
                "github.com/kr/pty v1.1.1 "
                "<resolved-canonical-32-byte-module-zip-H1>"
            ),
            "goModLine": (
                "github.com/kr/pty v1.1.1/go.mod "
                + TARGET_MOD_H1
            ),
            "lineOrder": ["module_zip_h1", "go_mod_h1"],
            "leafTerminatesWithSingleLf": True,
            "carriageReturnAllowed": False,
            "nulAllowed": False,
            "emptyRecordAllowed": False,
            "unrelatedRecordAllowed": False,
            "duplicateRecordAllowed": False,
            "extraRecordAllowed": False,
            "trailingRecordBytesAllowed": False,
            "extraRecordRejectionClass": "GO-2026-4984",
            "moduleZipH1PrefixRequired": "h1:",
            "moduleZipH1CanonicalBase64DecodedBytes": 32,
            "goModH1MustEqualHeldEvidence": True,
            "leafHashAlgorithm": "RFC6962_SHA256_0x00_prefix",
        },
        "signedNoteAndTreeContract": {
            "verifierKey": SUMDB_VERIFIER_KEY,
            "verifierKeyHashRecomputed": True,
            "noteEd25519SignatureRequired": True,
            "signedTreeTextStrictlyParsed": True,
            "tileRequestsForbiddenBeforeSignatureVerification": True,
            "rollbackRule": "new_tree_size_less_than_57871495_fails_consumed",
            "equalSizeRule": (
                "new_tree_size_equal_57871495_requires_exact_old_root_"
                "and_zero_consistency_delta"
            ),
            "growthRule": (
                "new_tree_size_greater_than_57871495_requires_valid_"
                "old_to_new_rfc6962_consistency_proof"
            ),
            "equalSizeDifferentRootAllowed": False,
            "keyRotationAllowed": False,
            "trustOnFirstUseAllowed": False,
        },
        "adaptiveProofTileContract": {
            "derivationInput": [
                "strict_lookup_record_number",
                "pinned_key_verified_new_tree_size_and_root",
                "old_tree_size_57871495_and_root",
            ],
            "derivationAlgorithm": (
                "golang.org/x/mod/sumdb/tlog_tile_height_8_"
                "record_inclusion_union_old_to_new_consistency_v1"
            ),
            "tileHeight": TILE_HEIGHT,
            "fullTileWidthHashes": FULL_TILE_WIDTH,
            "hashBytes": 32,
            "allowedHost": LOOKUP_HOST,
            "allowedPathRegex": TILE_PATH_REGEX,
            "pathEncoding": (
                "tile_height_level_base1000_x_groups_three_digit_leaf_"
                "optional_partial_width_1_to_255"
            ),
            "onlyHashTilesAllowed": True,
            "dataTilesAllowed": False,
            "latestEndpointAllowed": False,
            "secondLookupAllowed": False,
            "sourceEndpointAllowed": False,
            "pathSetMustBeUnique": True,
            "pathSetMustBeMinimalForBothProofs": True,
            "requestOrder": (
                "lookup_first_then_unique_tiles_in_canonical_"
                "level_index_width_order"
            ),
            "tileResponseExactBytes": "32_times_tile_width",
            "maximumTileResponseBodyBytes": MAXIMUM_TILE_RESPONSE_BYTES,
            "maximumHeaderBytesPerResponse": MAXIMUM_HEADER_BYTES,
            "proofAcceptance": {
                "exactRecordLeafHashRecomputed": True,
                "recordInclusionAgainstSignedNewRootRequired": True,
                "oldToNewConsistencyRequiredOnGrowth": True,
                "equalTreeRequiresExactOldRootAndNoConsistencyDelta": True,
                "conflictingOrUnusedProofHashAllowed": False,
            },
        },
        "absoluteResourceLimits": {
            "maximumTotalRequestCount": MAXIMUM_REQUEST_COUNT,
            "maximumLookupRequestCount": 1,
            "maximumDerivedTileRequestCount": MAXIMUM_REQUEST_COUNT - 1,
            "maximumAggregateResponseBodyBytes": (
                MAXIMUM_AGGREGATE_RESPONSE_BYTES
            ),
            "maximumLookupResponseBodyBytes": MAXIMUM_LOOKUP_RESPONSE_BYTES,
            "maximumTileResponseBodyBytes": MAXIMUM_TILE_RESPONSE_BYTES,
            "maximumHeaderBytesPerResponse": MAXIMUM_HEADER_BYTES,
            "perRequestDeadlineMilliseconds": PER_REQUEST_DEADLINE_MS,
            "wholeAttemptDeadlineMilliseconds": WHOLE_ATTEMPT_DEADLINE_MS,
        },
        "metadataOnlyNamespaceReservation": {
            "dependencyParentPath": DEPENDENCY_ROOT,
            "claimPath": CLAIM_PATH,
            "stagingPrefix": STAGING_PREFIX,
            "finalEvidenceDirectoryPath": FINAL_EVIDENCE_PATH,
            "futureDocuments": list(FUTURE_DOCS),
            "allCurrentlyAbsent": True,
            "metadataOnly": True,
            "sourceAcceptedDirectory": False,
            "reservationIsWriteAuthority": False,
            "futurePublicationRule": (
                "fd_held_owner_only_fsync_atomic_no_replace_"
                "receipt_then_manifest_last"
            ),
            "futureIndependentReadbackRequired": True,
        },
        "authority": {
            "decisionRecorded": True,
            "decisionIsExecutionPermit": False,
            "permitPreparationAuthorized": False,
            "runnerPreparationAuthorized": False,
            "testPreparationAuthorized": False,
            "networkAuthorized": False,
            "dnsAuthorized": False,
            "tcpAuthorized": False,
            "tlsAuthorized": False,
            "httpsAuthorized": False,
            "sumDbLookupAuthorized": False,
            "tileRequestAuthorized": False,
            "filesystemMutationAuthorized": False,
            "metadataWriteAuthorized": False,
            "sourceAcquisitionAuthorized": False,
            "sourceProxyAuthorized": False,
            "moduleRequestAuthorized": False,
            "zipRequestAuthorized": False,
            "archiveExtractionAuthorized": False,
            "sourceLoadAuthorized": False,
            "sourceExecutionAuthorized": False,
            "compileAuthorized": False,
            "goCommandAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "externalAuthenticationRequired": False,
            "repositoryOwnerIdentityProofRequired": False,
            "accountLoginRequired": False,
            "credentialRequired": False,
            "clientCertificateRequired": False,
            "privateKeyRequired": False,
            "signatureByUserRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "operationCounters": {
            "existingRungTwoValidatorRunCount": 1,
            "networkOperationCount": 0,
            "sumDbLookupCount": 0,
            "tileRequestCount": 0,
            "fileWriteCount": 0,
            "sourceAcquisitionCount": 0,
            "archiveExtractionCount": 0,
            "sourceLoadCount": 0,
            "sourceExecutionCount": 0,
            "compileCount": 0,
            "goCommandCount": 0,
            "packageManagerInvocationCount": 0,
            "subprocessCount": 0,
            "gitOperationCount": 0,
            "deviceOperationCount": 0,
            "deploymentCount": 0,
            "authenticationCount": 0,
            "userActionCount": 0,
        },
        "closure": {
            "moduleZipH1Resolved": False,
            "identityPairComplete": False,
            "acquisitionReady": False,
            "sourceAcquired": False,
            "dependencyFixedPointReached": False,
            "dependencySourceClosureComplete": False,
            "dependencySourceReviewed": False,
            "candidateSelected": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "releaseReady": False,
        },
        "nonClaims": [
            "this decision is not a network or execution permit",
            "the unknown github.com/kr/pty v1.1.1 ZIP H1 is not hardcoded",
            "TLS is transport security and not checksum-log record proof",
            "a signed tree head alone is not record inclusion proof",
            "a future identity result is not source acquisition authority",
            "no proxy module ZIP or source request is allowed",
            "no dependency closure candidate library or release is established",
        ],
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW,
        },
        "toolBindings": tool_bindings,
        "result": (
            "auth_free_public_checksum_identity_resolution_fsm_"
            "designed_execution_not_authorized"
        ),
        "nextAction": (
            "prepare_separate_one_use_sumdb_identity_resolution_"
            "permit_checker_runner_and_tests"
        ),
    }


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    context = DecisionContext(ROOT, include_decision=verify_disk)
    try:
        expected = content_bound(expected_payload(context))
        if verify_disk:
            raw = context.package.raw[DECISION_PATH]
            verify_decision_bytes(raw, expected)
        context.final_barrier()
        return expected, {
            "documentType": (
                "aetherlink.public-checksum-identity-resolution-"
                "decision-check"
            ),
            "schemaVersion": "1.0",
            "status": "validated_decision_only_execution_not_authorized",
            "validationPassed": True,
            "target": f"{TARGET_MODULE}@{TARGET_VERSION}",
            "moduleZipH1Resolved": False,
            "maximumFutureRequestCount": MAXIMUM_REQUEST_COUNT,
            "networkAuthorized": False,
            "fileWriteCount": 0,
            "sourceAcquisitionAuthorized": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise DecisionError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        parser.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        expected, summary = evaluate(not args.print_expected)
        sys.stdout.buffer.write(
            canonical_bytes(expected if args.print_expected else summary)
        )
        return 0
    except DecisionError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.public-checksum-identity-resolution-"
                        "decision-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "networkAuthorized": False,
                    "fileWriteCount": 0,
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
                        "decision-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "networkAuthorized": False,
                    "fileWriteCount": 0,
                    "sourceAcquisitionAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
