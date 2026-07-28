#!/usr/bin/env python3
"""Validate the non-authorizing Combined V18 fixed-point closure decision.

Run with ``python3 -I -B -S``. This checker reads and hashes the canonical
decision, its reader, and the exact Combined V18 checker/tests. It does not
reconstruct the graph, inspect archives, write files, use the network, or grant
execution authority.
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
            "closure-review checker requires unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "closure-review-decision-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "closure-review-decision-v1.md"
)
V18_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v18.py"
V18_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v18.py"
CLOSURE_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "closure_review_decision_v1.py"
)
CLOSURE_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "closure_review_decision_v1.py"
)
PATCH_DECISION_PATH = (
    f"{BASE}/patch-and-dependency-closure-decision-v1.json"
)
SEMANTIC_CLASSIFICATIONS_PATH = (
    f"{BASE}/semantic-source-review-classifications-v1.json"
)
SEMANTIC_RESULT_PATH = f"{BASE}/semantic-source-review-result-v1.json"

DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-v18-"
    "fixed-point-closure-review-decision-v1"
)
READER_SHA256 = (
    "115668753e3b468858456e38f4572ec26784950d5cf41b1d75ae41318f00fe78"
)
V18_CHECKER_RAW_SHA256 = (
    "35c35e98bfc0ea4b49f29b76d732a54f8f0f80dbbe20812266f35143c92da564"
)
V18_CHECKER_NORMALIZED_SHA256 = (
    "b53fa66b34a8379216d64892502bb352220397c598cbe0b84911ca641b9e40aa"
)
V18_TESTS_RAW_SHA256 = (
    "44a62fc3771a027987320dee3c690f350a62d1eb16911fd925f56a22f09c74eb"
)
V18_CANDIDATE_CONTENT_SHA256 = (
    "9dce50013314ec8934ad52ac57cb0de92e982c2334303fc77289f01bc9c285fb"
)
V18_GRAPH_SHA256 = (
    "a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba"
)
V18_FRONTIER_SHA256 = (
    "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570"
)
V18_INPUT_SET_SHA256 = (
    "321c50408978ff6b8795c17b51b53cd1dabf8f124e4a691c42cb2eb4fd961ded"
)
V18_SOURCE_BINDINGS_SHA256 = (
    "622a644a86e6ffe4596a3186034fbf141d964f34b5f3044f1b175db716d099f7"
)
V18_EXACT_INPUT_INVENTORY_SHA256 = (
    "a349cd67bd0f3355146b7008c5fcf595f79801bc1d7f8ab6d85f69178e565cda"
)
V18_WAVE19_READBACK_BINDINGS_SHA256 = (
    "4164d8845fa32c1179aa923da9b58a8c76b1d0cbcaf0bf6088538c6c3d4c1474"
)
PATCH_DECISION_RAW_SHA256 = (
    "5ab3bfe60c617c58b88ae0885f2bdb6fba0c315c0478d6eacf526cdd935903ec"
)
SEMANTIC_CLASSIFICATIONS_RAW_SHA256 = (
    "e76e8c9fa0a78c8c5c4beae1ebfd4c4f8144b411689a3a8bd5f8804ebf61c8c9"
)
SEMANTIC_RESULT_RAW_SHA256 = (
    "a01b3518f1354d438542ae77c06aa92d8f0936d516b4070d19c5bf27791e8a98"
)
SELF_NORMALIZED_SHA256 = (
    "ba52ee4e9ed4fb58fd7b74a55b0702bfe88ea367a98005f1c09a786001098362"
)
CLOSURE_TESTS_RAW_SHA256 = (
    "2ed1acdf9bbdf89c1ca3cce797f3bbc42baf1652d2f131e1be80f3c55d11bd64"
)

MAXIMUM_FILE_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 2 * 1024 * 1024


class CheckError(RuntimeError):
    """A deterministic validation failure."""

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
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(type(key) is str and key not in value, "E_JSON")
        value[key] = item
    return value


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


def safe_relative(value: str) -> str:
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


def read_stable_regular_file(
    root: Path,
    relative: str,
    maximum_bytes: int = MAXIMUM_FILE_BYTES,
) -> bytes:
    relative = safe_relative(relative)
    path = root / relative
    try:
        before = os.lstat(path)
    except OSError as error:
        raise CheckError("E_FILE") from error
    require(
        stat.S_ISREG(before.st_mode)
        and before.st_nlink == 1
        and 0 <= before.st_size <= maximum_bytes,
        "E_FILE",
    )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        require(
            file_identity(opened) == file_identity(before)
            and stat.S_ISREG(opened.st_mode)
            and opened.st_nlink == 1,
            "E_FILE",
        )
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            require(bool(chunk), "E_FILE")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(descriptor, 1) == b"", "E_FILE")
        after_descriptor = os.fstat(descriptor)
        require(
            file_identity(after_descriptor) == file_identity(opened),
            "E_FILE",
        )
    except OSError as error:
        raise CheckError("E_FILE") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        after_path = os.lstat(path)
    except OSError as error:
        raise CheckError("E_FILE") from error
    require(file_identity(after_path) == file_identity(before), "E_FILE")
    raw = b"".join(chunks)
    require(len(raw) == before.st_size, "E_FILE")
    return raw


def normalized_v18_checker_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    require(start >= 0, "E_V18_NORMALIZED")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    require(
        payload_end - payload_start == 64
        and raw.find(marker, payload_start) < 0,
        "E_V18_NORMALIZED",
    )
    return raw[:payload_start] + (b"0" * 64) + raw[payload_end:]


def normalized_self_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    require(start >= 0, "E_SELF_NORMALIZED")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    require(
        payload_end - payload_start == 64
        and raw.find(marker, payload_start) < 0,
        "E_SELF_NORMALIZED",
    )
    return raw[:payload_start] + (b"0" * 64) + raw[payload_end:]


def content_bound(body: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(body)
    value["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "canonical_json_without_contentBinding",
        "sha256": sha256(canonical_bytes(body)),
    }
    return value


def expected_decision() -> dict[str, Any]:
    body = {
        "schemaVersion": "1.0",
        "documentType": (
            "aetherlink.g2-pion-combined-v18-"
            "fixed-point-closure-review-decision"
        ),
        "decisionId": DECISION_ID,
        "status": (
            "dependency_graph_fixed_point_accepted_"
            "source_and_semantic_closure_open"
        ),
        "scope": (
            "read_only_review_of_exact_combined_v18_"
            "dependency_graph_fixed_point_evidence_only"
        ),
        "decision": "accept_combined_v18_dependency_graph_fixed_point_only",
        "evidenceBindings": {
            "patchAndDependencyClosureDecision": {
                "path": PATCH_DECISION_PATH,
                "rawSha256": PATCH_DECISION_RAW_SHA256,
            },
            "semanticSourceReviewClassifications": {
                "path": SEMANTIC_CLASSIFICATIONS_PATH,
                "rawSha256": SEMANTIC_CLASSIFICATIONS_RAW_SHA256,
            },
            "semanticSourceReviewResult": {
                "path": SEMANTIC_RESULT_PATH,
                "rawSha256": SEMANTIC_RESULT_RAW_SHA256,
            },
            "reader": {
                "path": READER_PATH,
                "rawSha256": READER_SHA256,
            },
            "combinedV18Checker": {
                "path": V18_CHECKER_PATH,
                "rawSha256": V18_CHECKER_RAW_SHA256,
                "normalizedSelfSha256": V18_CHECKER_NORMALIZED_SHA256,
            },
            "combinedV18Tests": {
                "path": V18_TESTS_PATH,
                "rawSha256": V18_TESTS_RAW_SHA256,
            },
            "closureReviewChecker": {
                "path": CLOSURE_CHECKER_PATH,
                "normalizedSelfSha256": SELF_NORMALIZED_SHA256,
            },
            "closureReviewTests": {
                "path": CLOSURE_TESTS_PATH,
                "rawSha256": CLOSURE_TESTS_RAW_SHA256,
            },
            "inputSetSha256": V18_INPUT_SET_SHA256,
            "sourceBindingsSha256": V18_SOURCE_BINDINGS_SHA256,
            "exactInputInventorySha256":
                V18_EXACT_INPUT_INVENTORY_SHA256,
            "wave19ReadbackBindingsSha256":
                V18_WAVE19_READBACK_BINDINGS_SHA256,
            "candidateContentSha256": V18_CANDIDATE_CONTENT_SHA256,
            "graphSha256": V18_GRAPH_SHA256,
            "frontierSha256": V18_FRONTIER_SHA256,
        },
        "fixedPointReview": {
            "candidateSchemaVersion": "18.0",
            "candidateStatus":
                "combined_graph_discovery_complete_fixed_point_candidate",
            "algorithm": "go1.24_mvs_profile_union_fixed_point_v1",
            "profiles": [
                "android_api_26_through_36_arm64_v8a",
                "macos_14_or_newer_arm64",
            ],
            "acceptedScope":
                "exact_retained_wave1_through_wave19_graph_discovery_only",
            "heldSourceInputCount": 369,
            "exactInputInventoryCount": 379,
            "resourceCount": 368,
            "moduleVersionTupleCount": 184,
            "modCount": 184,
            "zipCount": 184,
            "archiveCount": 185,
            "archiveEntryCount": 72_304,
            "sourceRawByteCount": 356_092_640,
            "exactInventoryRawByteCount": 356_152_035,
            "archiveUncompressedByteCount": 1_359_347_284,
            "exactFrontier": [],
            "newTupleCount": 0,
            "unmappedExternalImportCount": 0,
            "unresolvedDeclaredExternalImportCount": 0,
            "fixedPointReached": True,
            "canonicalGraphEqualityVerified": True,
            "candidateArtifactPersistedByThisDecision": False,
            "route": "fixed_point_candidate",
            "directFullInputReconstructionCount": 2,
            "fullSourceReconstructionCount": 34,
            "archiveOpenCount": 4_792,
            "independentGraphAlgorithmCount": 68,
            "operationCounters": {
                "archiveExtractionCount": 0,
                "dependencySourceLoadCount": 0,
                "dependencySourceExecutionCount": 0,
                "dependencySourceCompileCount": 0,
                "subprocessCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
            },
        },
        "testEvidence": {
            "postSealDryLatentFastBoundary": {
                "passed": 18,
                "total": 18,
            },
            "genuineFullClass": {
                "passed": 23,
                "total": 24,
                "soleError": (
                    "test_13_legacy_wave9_compatibility_"
                    "remains_exact_and_bounded"
                ),
                "failureCause":
                    "pre_correction_stale_chain_index_test_oracle",
                "candidateReproduced": True,
                "cleanPostFixFullClassRerunClaimed": False,
            },
            "correctedIsolatedTest13": {
                "passed": 1,
                "total": 1,
            },
        },
        "findingDisposition": {
            "canonicalFindingCount": 19,
            "patchRequiredCount": 7,
            "unresolvedCount": 12,
            "closedByThisDecisionCount": 0,
            "allCanonicalFindingsRemainOpen": True,
            "allFindingIdsBoundByExactPredecessors": True,
        },
        "closure": {
            "dependencyFixedPointReached": True,
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
        "authority": {
            "decisionRecorded": True,
            "acquisitionAuthorityGranted": False,
            "filesystemExtractionAuthorized": False,
            "sourceLoadAuthorized": False,
            "sourceExecutionAuthorized": False,
            "compilerAuthorized": False,
            "subprocessAuthorized": False,
            "socketAuthorized": False,
            "networkAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "publicationAuthorized": False,
            "fileWriteAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "approvalRequired": False,
            "userActionRequired": False,
        },
        "nonClaims": {
            "fixedPointIsDependencySourceReview": False,
            "fixedPointIsDependencyClosure": False,
            "fixedPointIsSemanticClosure": False,
            "fixedPointClosesAnyCanonicalFinding": False,
            "fixedPointIsLicenseOrSecurityAcceptance": False,
            "fixedPointSelectsCandidateOrLibrary": False,
            "fixedPointCompletesRungThreeOrV1": False,
            "reviewDecisionAuthorizesExecutionOrNetwork": False,
            "testEvidenceIsCleanPostFixFullClassRerun": False,
            "retainedSnapshotProvesContinuousCurrentPathIdentity": False,
            "personalProjectRequiresOwnerAuthentication": False,
            "productEndpointAuthenticationSatisfied": False,
        },
        "result": (
            "exact_v18_empty_frontier_fixed_point_acknowledged_"
            "all_19_semantic_findings_remain_open"
        ),
        "nextAction": (
            "prepare_separate_fixed_point_snapshot_"
            "dependency_source_and_license_review_decision"
        ),
    }
    return content_bound(body)


def validate_decision_bytes(
    raw: bytes,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = strict_json(raw)
    require(raw == canonical_bytes(parsed), "E_CANONICAL_DECISION")
    require(parsed == expected, "E_DECISION")
    without_binding = dict(parsed)
    binding = without_binding.pop("contentBinding", None)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": "canonical_json_without_contentBinding",
            "sha256": sha256(canonical_bytes(without_binding)),
        },
        "E_CONTENT_BINDING",
    )
    return parsed


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    expected = expected_decision()
    decision_raw = read_stable_regular_file(root, DECISION_PATH)
    decision = validate_decision_bytes(decision_raw, expected)

    reader_raw = read_stable_regular_file(root, READER_PATH)
    require(sha256(reader_raw) == READER_SHA256, "E_READER")

    checker_raw = read_stable_regular_file(root, V18_CHECKER_PATH)
    require(sha256(checker_raw) == V18_CHECKER_RAW_SHA256, "E_V18_CHECKER")
    require(
        sha256(normalized_v18_checker_bytes(checker_raw))
        == V18_CHECKER_NORMALIZED_SHA256,
        "E_V18_NORMALIZED",
    )

    tests_raw = read_stable_regular_file(root, V18_TESTS_PATH)
    require(sha256(tests_raw) == V18_TESTS_RAW_SHA256, "E_V18_TESTS")

    self_raw = read_stable_regular_file(root, CLOSURE_CHECKER_PATH)
    require(
        sha256(normalized_self_bytes(self_raw)) == SELF_NORMALIZED_SHA256,
        "E_SELF_NORMALIZED",
    )
    closure_tests_raw = read_stable_regular_file(root, CLOSURE_TESTS_PATH)
    require(
        sha256(closure_tests_raw) == CLOSURE_TESTS_RAW_SHA256,
        "E_CLOSURE_TESTS",
    )

    predecessor_bindings = (
        (PATCH_DECISION_PATH, PATCH_DECISION_RAW_SHA256),
        (
            SEMANTIC_CLASSIFICATIONS_PATH,
            SEMANTIC_CLASSIFICATIONS_RAW_SHA256,
        ),
        (SEMANTIC_RESULT_PATH, SEMANTIC_RESULT_RAW_SHA256),
    )
    for path, expected_sha256 in predecessor_bindings:
        require(
            sha256(read_stable_regular_file(root, path))
            == expected_sha256,
            "E_PREDECESSOR",
        )

    closure = decision["closure"]
    authority = decision["authority"]
    return {
        "schemaVersion": "1.0",
        "documentType": (
            "aetherlink.g2-pion-combined-v18-"
            "fixed-point-closure-review-check-result"
        ),
        "status": "validated_non_authorizing_fixed_point_only_decision",
        "validationPassed": True,
        "onDiskExactEqualityVerified": True,
        "decisionId": decision["decisionId"],
        "dependencyFixedPointReached":
            closure["dependencyFixedPointReached"],
        "dependencySourceReviewed": closure["dependencySourceReviewed"],
        "dependencyClosureComplete": closure["dependencyClosureComplete"],
        "semanticClosureComplete": closure["semanticClosureComplete"],
        "openCanonicalFindingCount":
            decision["findingDisposition"]["canonicalFindingCount"],
        "externalAuthenticationRequired":
            authority["externalAuthenticationRequired"],
        "userActionRequired": authority["userActionRequired"],
        "gitWriteAuthorized": authority["gitWriteAuthorized"],
        "nextAction": decision["nextAction"],
    }


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CheckError("E_ARGUMENT")


def parse_arguments(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-expected",
        action="store_true",
        help="print the exact canonical decision bytes",
    )
    return parser.parse_args(argv)


def emit(raw: bytes) -> None:
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = parse_arguments(argv)
        if arguments.print_expected:
            emit(canonical_bytes(expected_decision()))
            return 0
        emit(canonical_bytes(check_repository(ROOT)))
        return 0
    except CheckError:
        emit(
            canonical_bytes(
                {
                    "schemaVersion": "1.0",
                    "documentType": (
                        "aetherlink.g2-pion-combined-v18-"
                        "fixed-point-closure-review-check-error"
                    ),
                    "status": "verification_failed",
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
