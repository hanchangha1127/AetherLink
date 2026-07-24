#!/usr/bin/env python3
"""Validate and safely load the G2 Pion rung-three v3 permit toolchain.

Runtime authority is an acyclic, closed tracked-file graph.  This checker has
no archive or build path capability, follows no symlinks, writes nothing, and
does not read the v1/v2 claims or report names.  It privately compiles only
exact pinned review-tool bytes after validating their static capabilities.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG2 = f"{BASE}/rung-two"
RUNG3 = f"{BASE}/rung-three"

RECEIPT_PATH = f"{RUNG2}/source-acquisition-receipt-v1.json"
FAILURE_MANIFEST_PATH = f"{RUNG3}/evidence-manifest-v8.json"
FAILURE_PATH = f"{RUNG3}/offline-source-review-execution-failure-v2.json"
PROGRESS_PATH = f"{RUNG3}/offline-source-review-progress-v3.json"
SUPERSESSION_PATH = f"{RUNG3}/canonical-document-supersession-v3.json"
FAILURE_CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_failure_v2.py"
FAILURE_CHECKER_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_execution_failure_v2.py"

POLICY_PATH = f"{RUNG3}/review-execution-policy-v3.json"
PERMIT_PATH = f"{RUNG3}/offline-source-review-execution-permit-v3.json"
CORE_MANIFEST_PATH = f"{RUNG3}/execution-permit-core-manifest-v9.json"
BASE_VALIDATOR_PATH = "script/p2p_nat_g2_pion_offline_zip.py"
BASE_VALIDATOR_TEST_PATH = "script/test_p2p_nat_g2_pion_offline_zip.py"
OVERLAY_PATH = "script/p2p_nat_g2_pion_offline_zip_creator_policy_v2.py"
OVERLAY_TEST_PATH = "script/test_p2p_nat_g2_pion_offline_zip_creator_policy_v2.py"
AGGREGATOR_PATH = "script/p2p_nat_g2_pion_candidate_inventory_v3.py"
AGGREGATOR_TEST_PATH = "script/test_p2p_nat_g2_pion_candidate_inventory_v3.py"
RUNNER_PATH = "script/run_p2p_nat_g2_pion_rung3_offline_review_v3_once.py"
RUNNER_TEST_PATH = "script/test_run_p2p_nat_g2_pion_rung3_offline_review_v3_once.py"
CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_permit_v3.py"
CHECKER_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_execution_permit_v3.py"
CHECKER_MANIFEST_PATH = f"{RUNG3}/execution-permit-checker-manifest-v10.json"

EXPECTED_DATE = "2026-07-23"
EXPECTED_STATUS = "rung3_bounded_complete_count_inventory_v3_execution_authorized_not_consumed"
EXPECTED_RESULT = (
    "separate_single_use_bounded_complete_count_candidate_inventory_v3_"
    "authorized_not_executed"
)
EXPECTED_NEXT_ACTION = "execute_bound_rung3_complete_count_candidate_inventory_v3_once"
EXPECTED_SCOPE = (
    "separate_single_use_offline_archive_read_and_bounded_complete_count_"
    "candidate_inventory_only_not_full_rung3_semantic_review"
)

EXPECTED_RECEIPT_RAW = "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6"
EXPECTED_FAILURE_MANIFEST_RAW = "35b074e2213b5304c2e0df2cc2b4dee8cf19fb693f36366c6a436f96db46c781"
EXPECTED_FAILURE_MANIFEST_SEMANTIC = "ea3304b84c42a287b87545eab93afa3a1bb6eaa5b2a4c4b8f28e736892ce43c8"
EXPECTED_FAILURE_COLLECTION = "b206cc0e744484136f513276c4d965288945bb5dded3d29e982494cb4fab3b02"
EXPECTED_FAILURE_RAW = "c1c36b4f2a6aaeddacbfad56e19cb3c658569e7f561eef764c4d48652be2b66c"
EXPECTED_FAILURE_SEMANTIC = "375becf562bcaf628b61cbc23369135ef6e1849332df00a804655dd4c08074bd"
EXPECTED_PROGRESS_RAW = "2b4a3a5c89bf5f1d9821f1ed83e78f8953d775f8d49d385a1177acb572c6dd00"
EXPECTED_PROGRESS_SEMANTIC = "4b677f1e6a91db2c91109b8952851be7ae46650e0dbf75272f14e969c566bbb1"
EXPECTED_SUPERSESSION_RAW = "7a2bf9d692396d356db4b98318fa066f9ff0af000b8b75ebe2b12c568ebbc938"
EXPECTED_SUPERSESSION_SEMANTIC = "f82345cfbfb73933f54ff6879c428b7675f62b03cc03697cc77c93b3d4c555f0"
EXPECTED_FAILURE_CHECKER_RAW = "358c75b1685231f5134b3e74c14300fccd713e76afebebb9a941b2fe2cb7c7e1"
EXPECTED_FAILURE_CHECKER_TEST_RAW = "cffaa6ebaae901da123dc0c66b921d27cec0e4e0df94c1eae0e40b249f370106"
EXPECTED_V2_CLAIM_RAW_RECORDED_ONLY = "ff5a1ea309d1fd51b0ed46a35f6b711a829170d70c330135b40d214544b8de9d"

EXPECTED_POLICY_RAW = "80f7ea3ee34f25295881ce175438f150db46b8493788d7f806e809afd2821367"
EXPECTED_POLICY_SEMANTIC = "12baedf3c2535d4999dacf363c8edd0b90ef57de6f6455260a8024791531ba9a"
EXPECTED_PERMIT_RAW = "62652843477ca36dcdd3bf14d2aad42c33a694c8ffb7b4a51f7ce3ece5d476ae"
EXPECTED_PERMIT_SEMANTIC = "d763a8ed9f681b66c9d6d3551fc5038e360173fee453eb6dee2a7cff3a1d8fe8"
EXPECTED_PERMIT_CONTENT = "4e2f831d9c90c2f171a2461dccda940fdb02f0f043c9d13ebfbc308b22a703c5"
EXPECTED_CORE_RAW = "e9f96e3026ac09bbe4fcac23232fbe97c9017c93799acc50b608b559058ee0d5"
EXPECTED_CORE_SEMANTIC = "f6d68a64eb16e25e27cf1fc8795710eb9d84dfbaf69bd54d97d44cc3be5b9486"
EXPECTED_CORE_COLLECTION = "088f2e352bb8b71d921174366a0c61d94abdf2bdb7fe5b74089d40d0742befec"

EXPECTED_BASE_RAW = "9daef717b30337191ee9902110bdf4455babacb261acab9124d37de72fa8988b"
EXPECTED_BASE_TEST_RAW = "49b4b99ec194186848fc127c10caa140e96260e7530830acc7781bfcb6a8a035"
EXPECTED_OVERLAY_RAW = "52e593d919066e7657acf20e1027c9c4a7753b16746c7f20e2eb62557fb0a2fc"
EXPECTED_OVERLAY_TEST_RAW = "1cbb7886b1a4b8130af3926941728aecddf764d94fd546c18c12f54ef4159d9c"
EXPECTED_AGGREGATOR_RAW = "6789329eb49c6ffbbf5fbc534128bf6419004e93aeaa0fdfa6a4a5c3bc5101be"
EXPECTED_AGGREGATOR_TEST_RAW = "fff32c9ac87bfc70db39a2e08c15c6173cc0f5da2735dd7b62f8a1219bffec29"

MAX_TRACKED_FILE_BYTES = 8 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"^__PENDING_[A-Z0-9_]+__$")

FAILURE_ARTIFACT_PATHS = (
    FAILURE_PATH,
    PROGRESS_PATH,
    SUPERSESSION_PATH,
    FAILURE_CHECKER_PATH,
    FAILURE_CHECKER_TEST_PATH,
)
AUTHORITY_READ_ALLOWLIST = frozenset(
    {
        RECEIPT_PATH,
        FAILURE_MANIFEST_PATH,
        *FAILURE_ARTIFACT_PATHS,
        POLICY_PATH,
        PERMIT_PATH,
        CORE_MANIFEST_PATH,
        BASE_VALIDATOR_PATH,
        BASE_VALIDATOR_TEST_PATH,
        OVERLAY_PATH,
        OVERLAY_TEST_PATH,
        AGGREGATOR_PATH,
        AGGREGATOR_TEST_PATH,
    }
)
OBSERVATIONAL_READ_ALLOWLIST = frozenset(
    {
        CHECKER_MANIFEST_PATH,
        RUNNER_PATH,
        RUNNER_TEST_PATH,
        CHECKER_PATH,
        CHECKER_TEST_PATH,
    }
)


class CheckError(ValueError):
    """Closed v3 permit evidence or exact tool bytes failed validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict, f"{label}: object required")
    require(set(value) == expected, f"{label}: exact keys mismatch")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def semantic_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite number")
    elif type(value) is list:
        for index, item in enumerate(value):
            reject_nonfinite(item, f"{label}[{index}]")
    elif type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(item, f"{label}.{key}")


def strict_json(data: bytes, label: str) -> Any:
    require(data.endswith(b"\n") and not data.endswith(b"\n\n"), f"{label}: one final LF required")
    require(b"\r" not in data, f"{label}: CR forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        parsed = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CheckError(f"{label}: non-finite value {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid strict JSON: {error}") from error
    reject_nonfinite(parsed, label)
    return parsed


def unresolved_placeholders(value: Any, label: str = "$") -> list[str]:
    if type(value) is str:
        return [label] if PLACEHOLDER.fullmatch(value) else []
    if type(value) is list:
        return [
            item
            for index, child in enumerate(value)
            for item in unresolved_placeholders(child, f"{label}[{index}]")
        ]
    if type(value) is dict:
        return [
            item
            for key, child in value.items()
            for item in unresolved_placeholders(child, f"{label}.{key}")
        ]
    return []


def validate_relative_path(
    path: str,
    allowed_paths: frozenset[str] = AUTHORITY_READ_ALLOWLIST,
) -> tuple[str, ...]:
    require(type(path) is str and path in allowed_paths, f"unlisted read forbidden: {path}")
    require("\\" not in path and "\x00" not in path, f"unsafe path: {path}")
    pure = PurePosixPath(path)
    require(not pure.is_absolute(), f"absolute path forbidden: {path}")
    require(pure.parts and all(part not in ("", ".", "..") for part in pure.parts), f"unsafe path: {path}")
    require(pure.parts[0] != "build", f"build read forbidden: {path}")
    require(
        not path.lower().endswith((".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z")),
        f"archive read forbidden: {path}",
    )
    return pure.parts


class SafeTrackedReader:
    """Component-wise no-follow, stable, exact-allowlist reader."""

    def __init__(
        self,
        root: Path,
        allowed_paths: frozenset[str] = AUTHORITY_READ_ALLOWLIST,
    ) -> None:
        self.root = root
        self.allowed_paths = allowed_paths
        self.cache: dict[str, bytes] = {}
        self.read_paths: list[str] = []

    def read(self, path: str) -> bytes:
        parts = validate_relative_path(path, self.allowed_paths)
        if path in self.cache:
            return self.cache[path]
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        require(nofollow != 0 and directory != 0, "nofollow directory opens required")
        directory_flags = os.O_RDONLY | directory | nofollow | getattr(os, "O_CLOEXEC", 0)
        file_flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0)
        root_fd = os.open(os.fspath(self.root), directory_flags)
        parent_fd = root_fd
        opened_dirs: list[int] = []
        try:
            for component in parts[:-1]:
                next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
                opened_dirs.append(next_fd)
                parent_fd = next_fd
            file_fd = os.open(parts[-1], file_flags, dir_fd=parent_fd)
            try:
                before = os.fstat(file_fd)
                require(stat.S_ISREG(before.st_mode), f"{path}: regular file required")
                require(before.st_nlink == 1, f"{path}: single link required")
                require(0 <= before.st_size <= MAX_TRACKED_FILE_BYTES, f"{path}: size out of bounds")
                remaining = before.st_size
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(file_fd, min(65_536, remaining))
                    require(bool(chunk), f"{path}: unexpected EOF")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(file_fd, 1) == b"", f"{path}: grew during read")
                after = os.fstat(file_fd)
                stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
                require(
                    all(getattr(before, field) == getattr(after, field) for field in stable),
                    f"{path}: changed during read",
                )
                data = b"".join(chunks)
            finally:
                os.close(file_fd)
        except OSError as error:
            raise CheckError(f"{path}: safe read failed: {error}") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)
            os.close(root_fd)
        self.cache[path] = data
        self.read_paths.append(path)
        return data

    def json(self, path: str) -> Any:
        return strict_json(self.read(path), path)


def collection_sha256(artifacts: Sequence[Mapping[str, Any]]) -> str:
    payload = "".join(
        f"{row['evidenceId']}\t{row['sha256']}\t{row['path']}\n"
        for row in artifacts
    ).encode("utf-8")
    return sha256_bytes(payload)


EXPECTED_FAILURE_ARTIFACTS = (
    ("G2R3E038", FAILURE_PATH, EXPECTED_FAILURE_RAW),
    ("G2R3E039", PROGRESS_PATH, EXPECTED_PROGRESS_RAW),
    ("G2R3E040", SUPERSESSION_PATH, EXPECTED_SUPERSESSION_RAW),
    ("G2R3E041", FAILURE_CHECKER_PATH, EXPECTED_FAILURE_CHECKER_RAW),
    ("G2R3E042", FAILURE_CHECKER_TEST_PATH, EXPECTED_FAILURE_CHECKER_TEST_RAW),
)
EXPECTED_CORE_ARTIFACTS = (
    ("G2R3E043", PERMIT_PATH, EXPECTED_PERMIT_RAW),
    ("G2R3E044", POLICY_PATH, EXPECTED_POLICY_RAW),
    ("G2R3E045", FAILURE_MANIFEST_PATH, EXPECTED_FAILURE_MANIFEST_RAW),
    ("G2R3E046", FAILURE_PATH, EXPECTED_FAILURE_RAW),
    ("G2R3E047", PROGRESS_PATH, EXPECTED_PROGRESS_RAW),
    ("G2R3E048", SUPERSESSION_PATH, EXPECTED_SUPERSESSION_RAW),
    ("G2R3E049", FAILURE_CHECKER_PATH, EXPECTED_FAILURE_CHECKER_RAW),
    ("G2R3E050", FAILURE_CHECKER_TEST_PATH, EXPECTED_FAILURE_CHECKER_TEST_RAW),
    ("G2R3E051", BASE_VALIDATOR_PATH, EXPECTED_BASE_RAW),
    ("G2R3E052", BASE_VALIDATOR_TEST_PATH, EXPECTED_BASE_TEST_RAW),
    ("G2R3E053", OVERLAY_PATH, EXPECTED_OVERLAY_RAW),
    ("G2R3E054", OVERLAY_TEST_PATH, EXPECTED_OVERLAY_TEST_RAW),
    ("G2R3E055", AGGREGATOR_PATH, EXPECTED_AGGREGATOR_RAW),
    ("G2R3E056", AGGREGATOR_TEST_PATH, EXPECTED_AGGREGATOR_TEST_RAW),
)


def verify_json_pin(
    reader: SafeTrackedReader,
    path: str,
    raw_sha256: str,
    semantic: str,
) -> Any:
    raw = reader.read(path)
    parsed = strict_json(raw, path)
    require(sha256_bytes(raw) == raw_sha256, f"{path}: raw digest mismatch")
    require(semantic_sha256(parsed) == semantic, f"{path}: semantic digest mismatch")
    return parsed


def validate_failure_evidence(reader: SafeTrackedReader) -> dict[str, Any]:
    manifest = verify_json_pin(
        reader,
        FAILURE_MANIFEST_PATH,
        EXPECTED_FAILURE_MANIFEST_RAW,
        EXPECTED_FAILURE_MANIFEST_SEMANTIC,
    )
    artifacts = manifest.get("artifacts")
    require(type(artifacts) is list and len(artifacts) == 5, "failure manifest artifacts")
    require(manifest.get("artifactCount") == 5, "failure manifest artifact count")
    require(manifest.get("collectionSha256") == EXPECTED_FAILURE_COLLECTION, "failure manifest collection pin")
    for row, expected in zip(artifacts, EXPECTED_FAILURE_ARTIFACTS):
        require(type(row) is dict, "failure artifact object")
        require((row.get("evidenceId"), row.get("path"), row.get("sha256")) == expected, "failure artifact identity")
        require(sha256_bytes(reader.read(expected[1])) == expected[2], "failure artifact actual digest")
    require(collection_sha256(artifacts) == EXPECTED_FAILURE_COLLECTION, "failure collection digest")
    failure = verify_json_pin(reader, FAILURE_PATH, EXPECTED_FAILURE_RAW, EXPECTED_FAILURE_SEMANTIC)
    verify_json_pin(reader, PROGRESS_PATH, EXPECTED_PROGRESS_RAW, EXPECTED_PROGRESS_SEMANTIC)
    verify_json_pin(reader, SUPERSESSION_PATH, EXPECTED_SUPERSESSION_RAW, EXPECTED_SUPERSESSION_SEMANTIC)
    require(failure["claimEvidence"]["rawSha256"] == EXPECTED_V2_CLAIM_RAW_RECORDED_ONLY, "recorded v2 claim digest")
    require(failure["claimEvidence"]["retained"] is True, "v2 claim retained")
    require(failure["claimEvidence"]["automaticRetryAllowed"] is False, "v2 retry forbidden")
    require(failure["executionBoundary"]["permitConsumed"] is True, "v2 permit consumed")
    require(manifest["failureBoundary"]["permitVersionTwoConsumed"] is True, "manifest v2 consumed")
    require(manifest["failureBoundary"]["automaticRetryAllowed"] is False, "manifest v2 retry forbidden")
    require(manifest["trustBoundary"]["buildDirectoryEnumerationAllowed"] is False, "failure build enumeration boundary")
    return manifest


EXPECTED_TOOL_BINDINGS = {
    "baseValidator": {"path": BASE_VALIDATOR_PATH, "rawSha256": EXPECTED_BASE_RAW},
    "baseValidatorTest": {"path": BASE_VALIDATOR_TEST_PATH, "rawSha256": EXPECTED_BASE_TEST_RAW},
    "creatorPolicyOverlay": {"path": OVERLAY_PATH, "rawSha256": EXPECTED_OVERLAY_RAW},
    "creatorPolicyOverlayTest": {"path": OVERLAY_TEST_PATH, "rawSha256": EXPECTED_OVERLAY_TEST_RAW},
    "candidateAggregator": {"path": AGGREGATOR_PATH, "rawSha256": EXPECTED_AGGREGATOR_RAW},
    "candidateAggregatorTest": {"path": AGGREGATOR_TEST_PATH, "rawSha256": EXPECTED_AGGREGATOR_TEST_RAW},
}


def validate_policy(policy: Any) -> None:
    require(policy["documentType"] == "aetherlink.g2-pion-rung3-offline-source-review-execution-policy", "policy type")
    require(policy["schemaVersion"] == "3.0", "policy schema")
    require(policy["policyId"] == "g2-pion-ice-v4.3.0-offline-source-review-execution-policy-v3", "policy id")
    require((policy["recordedDate"], policy["status"], policy["scope"]) == (EXPECTED_DATE, "bounded_static_candidate_inventory_v3_policy_recorded_execution_not_started", EXPECTED_SCOPE), "policy identity")
    predecessor = policy["predecessorFailureBoundary"]
    require(
        predecessor == {
            "permitV1Consumed": True,
            "permitV2Consumed": True,
            "permitV1RetryAllowed": False,
            "permitV2RetryAllowed": False,
            "permitV1ClaimRetained": True,
            "permitV2ClaimRetained": True,
            "predecessorMutationAllowed": False,
            "v3UsesDistinctOutputDirectoryAndNames": True,
        },
        "policy predecessor boundary",
    )
    aggregation = policy["candidateAggregationContract"]
    require(aggregation["completeTotalsRequired"] is True, "complete totals required")
    require(aggregation["completeObservationDigestRequiredPerPatchUnit"] is True, "complete digest required")
    require(aggregation["completeObservationEncodingVersion"] == 1, "digest encoding")
    require(aggregation["representativeLimitPerRule"] == 8, "per-rule cap")
    require(aggregation["representativeRankEncodingVersion"] == 1, "rank encoding")
    require(aggregation["nonzeroRuleRetainsAtLeastOneRepresentative"] is True, "nonzero representative")
    require(aggregation["sourceBodyInOutputAllowed"] is False, "source body output")
    require(aggregation["logicalLineDigestInOutputAllowed"] is False, "line digest output")
    paths = policy["runtimePaths"]
    require(
        paths == {
            "runner": RUNNER_PATH,
            "runnerTest": RUNNER_TEST_PATH,
            "baseValidator": BASE_VALIDATOR_PATH,
            "baseValidatorTest": BASE_VALIDATOR_TEST_PATH,
            "creatorPolicyOverlay": OVERLAY_PATH,
            "creatorPolicyOverlayTest": OVERLAY_TEST_PATH,
            "candidateAggregator": AGGREGATOR_PATH,
            "candidateAggregatorTest": AGGREGATOR_TEST_PATH,
            "permitChecker": CHECKER_PATH,
            "permitCheckerTest": CHECKER_TEST_PATH,
        },
        "policy runtime paths",
    )
    isolation = policy["interpreterIsolationContract"]
    require(isolation["preflightCommand"] == ["python3", "-I", "-B", "-S", RUNNER_PATH, "--check-permit"], "preflight command")
    require(isolation["executionCommand"] == ["python3", "-I", "-B", "-S", RUNNER_PATH, "--execute-permit"], "execution command")
    require(isolation["requiredSysFlags"] == {"isolated": 1, "dont_write_bytecode": 1, "ignore_environment": 1, "no_user_site": 1, "no_site": 1, "optimize": 0}, "isolation flags")
    require(isolation["projectToolBytecodeReadAllowed"] is False and isolation["projectToolBytecodeWriteAllowed"] is False, "project pyc boundary")
    require(policy["archiveOpenContract"]["maximumArchiveOpenCount"] == 1, "archive open count")
    require(policy["archiveOpenContract"]["maximumArchiveReadPassCount"] == 1, "archive read count")
    require(policy["consumptionContract"]["maximumExecutionAttempts"] == 1, "single execution")
    require(policy["consumptionContract"]["automaticRetryAllowed"] is False, "automatic retry")
    output = policy["outputContract"]
    require(output["directory"] == "build/offline-source/pion-ice-v4.3.0/review-v3", "v3 output directory")
    require(output["claimFileName"] == ".g2-pion-ice-v4.3.0-rung3-offline-review-v3.claim", "v3 claim")
    require(output["resultFileName"] == "offline-source-review-result-v3.json", "v3 result")
    require(output["manifestFileName"] == "offline-source-review-manifest-v3.json", "v3 manifest")
    boundary = policy["capabilityBoundary"]
    for key in (
        "archiveExtractionAllowed", "sourceFileMaterializationAllowed", "sourceExecutionAllowed",
        "sourcePatchWriteAllowed", "dependencyInstallationAllowed", "packageManagerAllowed",
        "reviewedSourceCompilerInvocationAllowed", "reviewedSourceCodeLoadingAllowed",
        "childSubprocessAllowed", "shellAllowed", "dnsAllowed", "socketCreationAllowed",
        "networkIoAllowed", "gitOperationAllowed", "deviceOperationAllowed",
        "productionDeploymentAllowed",
    ):
        require(boundary[key] is False, f"policy forbidden capability {key}")
    personal = policy["personalProjectBoundary"]
    require(personal["repositoryOwnerAuthenticationRequired"] is False, "owner auth")
    require(personal["externalIdentityProofRequired"] is False, "external identity")
    require(personal["executionPermitAuthenticationRequired"] is False, "execution auth")
    require(personal["userActionRequired"] is False, "user action")
    require(personal["productEndpointAuthenticationRequired"] is True, "endpoint boundary")


def validate_permit(permit: Any, raw: bytes, reader: SafeTrackedReader) -> None:
    require(sha256_bytes(raw) == EXPECTED_PERMIT_RAW, "permit raw pin")
    require(semantic_sha256(permit) == EXPECTED_PERMIT_SEMANTIC, "permit semantic pin")
    require(permit["documentType"] == "aetherlink.g2-pion-rung3-offline-source-review-execution-permit", "permit type")
    require(permit["schemaVersion"] == "3.0", "permit schema")
    require(permit["permitId"] == "g2-pion-ice-v4.3.0-offline-source-review-execution-permit-v3", "permit id")
    require((permit["recordedDate"], permit["status"], permit["result"], permit["nextAction"], permit["scope"]) == (EXPECTED_DATE, EXPECTED_STATUS, EXPECTED_RESULT, EXPECTED_NEXT_ACTION, EXPECTED_SCOPE), "permit identity")
    content = permit["contentBinding"]
    require(content == {"algorithm": "sha256", "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf", "scope": "permit_without_contentBinding", "sha256": EXPECTED_PERMIT_CONTENT}, "permit content binding")
    without = dict(permit)
    without.pop("contentBinding")
    require(sha256_bytes(canonical_json_bytes(without)) == EXPECTED_PERMIT_CONTENT, "permit content digest")
    require(permit["toolBindings"] == EXPECTED_TOOL_BINDINGS, "permit tool bindings")
    for binding in EXPECTED_TOOL_BINDINGS.values():
        require(sha256_bytes(reader.read(binding["path"])) == binding["rawSha256"], "tool actual digest")
    require(permit["policyBinding"] == {"path": POLICY_PATH, "rawSha256": EXPECTED_POLICY_RAW, "semanticSha256": EXPECTED_POLICY_SEMANTIC}, "policy binding")
    failure_bindings = permit["predecessorFailureBindings"]
    require(failure_bindings["failureEvidenceManifestV8"]["rawSha256"] == EXPECTED_FAILURE_MANIFEST_RAW, "failure manifest binding")
    require(failure_bindings["executionFailureV2"]["rawSha256"] == EXPECTED_FAILURE_RAW, "failure binding")
    require(failure_bindings["failureCheckerV2"]["rawSha256"] == EXPECTED_FAILURE_CHECKER_RAW, "failure checker binding")
    predecessor = permit["predecessorFailureBoundary"]
    require(predecessor["permitV1RetryAllowed"] is False and predecessor["permitV2RetryAllowed"] is False, "v1/v2 retry forbidden")
    require(predecessor["predecessorMutationAllowed"] is False, "predecessor mutation")
    require(predecessor["v2ClaimRawSha256RecordedOnlyNotReadByPreflight"] == EXPECTED_V2_CLAIM_RAW_RECORDED_ONLY, "recorded v2 claim")
    require(permit["singleUseConsumption"]["maximumExecutionAttempts"] == 1, "single use")
    require(permit["singleUseConsumption"]["automaticRetryAllowed"] is False, "v3 retry")
    require(permit["candidateAggregationContract"]["representativeLimitPerRule"] == 8, "permit cap")
    require(permit["candidateAggregationContract"]["completeTotalsRequired"] is True, "permit totals")
    require(permit["candidateAggregationContract"]["completeObservationDigestRequiredPerPatchUnit"] is True, "permit digest")
    isolation = permit["interpreterIsolationContract"]
    require(isolation["requiredSysFlags"]["no_site"] == 1, "permit no-site")
    require(isolation["projectToolBytecodeReadAllowed"] is False and isolation["projectToolBytecodeWriteAllowed"] is False, "permit pyc")
    capability = permit["capabilityBoundary"]
    require(capability["maximumArchiveOpenCount"] == 1 and capability["maximumArchiveReadPassCount"] == 1, "permit archive counts")
    for key in ("archiveExtractionAllowed", "sourceFileMaterializationAllowed", "sourceExecutionAllowed", "reviewedSourceCompilerInvocationAllowed", "childSubprocessAllowed", "shellAllowed", "dnsAllowed", "socketCreationAllowed", "networkIoAllowed", "gitOperationAllowed", "deviceOperationAllowed", "productionDeploymentAllowed"):
        require(capability[key] is False, f"permit forbidden capability {key}")
    personal = permit["personalProjectBoundary"]
    for key in ("repositoryOwnerAuthenticationRequired", "externalIdentityProofRequired", "executionPermitAuthenticationRequired", "userActionRequired"):
        require(personal[key] is False, f"permit personal boundary {key}")
    receipt_raw = reader.read(RECEIPT_PATH)
    require(sha256_bytes(receipt_raw) == EXPECTED_RECEIPT_RAW, "receipt raw pin")
    receipt = strict_json(receipt_raw, RECEIPT_PATH)
    archive = receipt["archive"]
    binding = permit["archiveIdentityBinding"]
    require(binding["receiptRawSha256"] == EXPECTED_RECEIPT_RAW, "receipt binding")
    require(binding["archivePathCopiedIntoPermit"] is False, "archive path copied")
    require(binding["rawSha256"] == "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c", "archive raw digest pin")
    for key in ("expectedBytes", "entryCount", "fileCount", "totalUncompressedBytes"):
        receipt_key = "bytes" if key == "expectedBytes" else key
        require(binding[key] == archive[receipt_key], f"archive identity {key}")


def validate_core(core: Any, raw: bytes, reader: SafeTrackedReader) -> None:
    require(sha256_bytes(raw) == EXPECTED_CORE_RAW, "core raw pin")
    require(semantic_sha256(core) == EXPECTED_CORE_SEMANTIC, "core semantic pin")
    require(core["manifestId"] == "g2-pion-ice-v4.3.0-rung3-execution-permit-core-evidence-manifest-v9", "core id")
    require((core["status"], core["result"], core["nextAction"]) == (EXPECTED_STATUS, EXPECTED_RESULT, EXPECTED_NEXT_ACTION), "core identity")
    require(core["artifactScope"] == "execution_authority_core_without_runner_checker_or_observational_manifest_cycle", "core scope")
    predecessor = core["predecessorManifestBinding"]
    require(predecessor == {"path": FAILURE_MANIFEST_PATH, "rawSha256": EXPECTED_FAILURE_MANIFEST_RAW, "semanticSha256": EXPECTED_FAILURE_MANIFEST_SEMANTIC, "collectionSha256": EXPECTED_FAILURE_COLLECTION}, "core predecessor")
    artifacts = core["artifacts"]
    require(type(artifacts) is list and len(artifacts) == 14 and core["artifactCount"] == 14, "core artifact count")
    for row, expected in zip(artifacts, EXPECTED_CORE_ARTIFACTS):
        require(type(row) is dict, "core artifact object")
        require((row.get("evidenceId"), row.get("path"), row.get("sha256")) == expected, "core artifact identity")
        require(sha256_bytes(reader.read(expected[1])) == expected[2], "core artifact actual digest")
    require(core["collectionSha256"] == EXPECTED_CORE_COLLECTION, "core collection pin")
    require(collection_sha256(artifacts) == EXPECTED_CORE_COLLECTION, "core collection digest")
    boundary = core["executionBoundary"]
    require(boundary["v1PermitRetryAllowed"] is False and boundary["v2PermitRetryAllowed"] is False, "core predecessor retries")
    require(boundary["preflightBuildReadAllowed"] is False and boundary["preflightArchiveReadAllowed"] is False, "core preflight access")
    for key in ("repositoryOwnerAuthenticationRequired", "externalIdentityProofRequired", "executionPermitAuthenticationRequired", "userActionRequired"):
        require(boundary[key] is False, f"core authentication boundary {key}")


def parse_source(raw: bytes, label: str) -> tuple[str, ast.Module]:
    try:
        source = raw.decode("utf-8", errors="strict")
        return source, ast.parse(source, filename=label)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise CheckError(f"{label}: invalid source: {error}") from error


def source_imports_calls(tree: ast.AST) -> tuple[set[str], list[tuple[str, ast.Call]]]:
    imports: set[str] = set()
    calls: list[tuple[str, ast.Call]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append((node.func.id, node))
            elif isinstance(node.func, ast.Attribute):
                calls.append((node.func.attr, node))
    return imports, calls


def enclosing_function(tree: ast.Module) -> dict[ast.AST, str | None]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    result: dict[ast.AST, str | None] = {}
    for node in ast.walk(tree):
        current = parents.get(node)
        name = None
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = current.name
                break
            current = parents.get(current)
        result[node] = name
    return result


def validate_review_sources(reader: SafeTrackedReader) -> None:
    base_raw = reader.read(BASE_VALIDATOR_PATH)
    _source, base_tree = parse_source(base_raw, BASE_VALIDATOR_PATH)
    base_imports, base_calls = source_imports_calls(base_tree)
    require(base_imports.isdisjoint({"os", "pathlib", "importlib", "ctypes", "http", "mmap", "requests", "shutil", "socket", "subprocess", "tempfile", "urllib"}), "base forbidden imports")
    require({name for name, _ in base_calls}.isdisjoint({"open", "eval", "exec", "compile", "input", "system", "popen", "urlopen"}), "base forbidden calls")

    overlay_raw = reader.read(OVERLAY_PATH)
    overlay_source, overlay_tree = parse_source(overlay_raw, OVERLAY_PATH)
    overlay_imports, overlay_calls = source_imports_calls(overlay_tree)
    require(overlay_imports == {"__future__", "builtins", "hashlib", "types"}, "overlay imports")
    scopes = enclosing_function(overlay_tree)
    for name in ("compile", "exec"):
        matches = [node for call_name, node in overlay_calls if call_name == name]
        require(len(matches) == 1 and scopes[matches[0]] == "_load_private_base_validator", f"overlay {name} boundary")
    require("def inspect_module_zip(\n    base_validator_source: bytes,\n    raw_archive: bytes," in overlay_source, "overlay API")

    aggregator_raw = reader.read(AGGREGATOR_PATH)
    aggregator_source, aggregator_tree = parse_source(aggregator_raw, AGGREGATOR_PATH)
    aggregator_imports, aggregator_calls = source_imports_calls(aggregator_tree)
    require(aggregator_imports == {"__future__", "hashlib", "re", "struct", "types", "typing", "unicodedata"}, "aggregator imports")
    require({name for name, _ in aggregator_calls}.isdisjoint({"open", "eval", "exec", "__import__", "input", "system", "popen", "urlopen"}), "aggregator forbidden calls")
    require("REPRESENTATIVE_LIMIT_PER_RULE = 8" in aggregator_source, "aggregator cap")
    require("completeObservationSha256" in aggregator_source and "totalHitCount" in aggregator_source, "aggregator totals/digest")
    require("def aggregate_candidate_inventory(" in aggregator_source, "aggregator API")


OVERLAY_IMPORT_ALLOWLIST = frozenset({"__future__", "builtins", "hashlib", "types"})
OVERLAY_BUILTIN_ALLOWLIST = frozenset(
    {
        "BaseException", "RuntimeError", "UnicodeDecodeError", "__build_class__",
        "bool", "bytes", "callable", "compile", "dict", "exec", "frozenset",
        "getattr", "int", "isinstance", "len", "set", "sorted", "str", "tuple", "type",
    }
)
AGGREGATOR_IMPORT_ALLOWLIST = frozenset(
    {"__future__", "hashlib", "re", "struct", "types", "typing", "unicodedata"}
)
AGGREGATOR_BUILTIN_ALLOWLIST = frozenset(
    {
        "AssertionError", "TypeError", "UnicodeDecodeError", "UnicodeEncodeError",
        "ValueError", "__build_class__", "any", "bool", "bytearray", "bytes",
        "dict", "enumerate", "getattr", "int", "isinstance", "iter", "len",
        "list", "memoryview", "object", "ord", "range", "set", "sorted", "str",
        "tuple", "type", "vars",
    }
)


def _validated_authority_reader(
    root: Path,
) -> tuple[SafeTrackedReader, dict[str, Any], str, str]:
    reader = SafeTrackedReader(root)
    policy_raw = reader.read(POLICY_PATH)
    policy = strict_json(policy_raw, POLICY_PATH)
    permit_raw = reader.read(PERMIT_PATH)
    permit = strict_json(permit_raw, PERMIT_PATH)
    core_raw = reader.read(CORE_MANIFEST_PATH)
    core = strict_json(core_raw, CORE_MANIFEST_PATH)
    placeholders = [
        item
        for index, document in enumerate((policy, permit, core))
        for item in unresolved_placeholders(document, f"document[{index}]")
    ]
    require(not placeholders, f"unresolved placeholders: {placeholders}")
    require(sha256_bytes(policy_raw) == EXPECTED_POLICY_RAW, "policy raw pin")
    require(semantic_sha256(policy) == EXPECTED_POLICY_SEMANTIC, "policy semantic pin")
    validate_failure_evidence(reader)
    validate_policy(policy)
    validate_permit(permit, permit_raw, reader)
    validate_core(core, core_raw, reader)
    validate_review_sources(reader)
    require(all(not path.startswith("build/") for path in reader.read_paths), "build read observed")
    require(all(not path.lower().endswith(".zip") for path in reader.read_paths), "archive read observed")
    return reader, permit, sha256_bytes(permit_raw), semantic_sha256(permit)


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    """Validate only the exact acyclic v3 execution-authority core."""

    reader, permit, permit_raw, permit_semantic = _validated_authority_reader(root)
    return {
        "permit": permit,
        "permitRawSha256": permit_raw,
        "permitSemanticSha256": permit_semantic,
        "archiveOpenCount": 0,
        "archiveReadPassCount": 0,
        "buildPathReadCount": 0,
        "outputPathReadCount": 0,
        "fileWriteCount": 0,
        "permitConsumptionState": "not_inspected",
        "authorityReadPaths": tuple(reader.read_paths),
    }


def _private_module(
    *,
    name: str,
    path: str,
    source: bytes,
    import_allowlist: frozenset[str],
    builtin_allowlist: frozenset[str],
) -> types.ModuleType:
    original_import = builtins.__import__

    def guarded_import(name, globals_value=None, locals_value=None, fromlist=(), level=0):
        require(level == 0, f"{path}: relative import forbidden: {name}")
        require(name in import_allowlist, f"{path}: import outside allowlist: {name}")
        return original_import(name, globals_value, locals_value, fromlist, level)

    safe_builtins = {item: getattr(builtins, item) for item in builtin_allowlist}
    safe_builtins["__import__"] = guarded_import
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__builtins__": safe_builtins,
            "__cached__": None,
            "__file__": path,
            "__loader__": None,
            "__package__": None,
        }
    )
    code = compile(source, path, "exec", flags=0, dont_inherit=True, optimize=0)
    exec(code, module.__dict__, module.__dict__)
    return module


def load_validated_review_modules(root: Path = ROOT) -> types.ModuleType:
    """Return a private two-call adapter retaining exact validated tool bytes."""

    reader, _permit, _permit_raw, _permit_semantic = _validated_authority_reader(root)
    base_source = reader.read(BASE_VALIDATOR_PATH)
    overlay_source = reader.read(OVERLAY_PATH)
    aggregator_source = reader.read(AGGREGATOR_PATH)
    require(sha256_bytes(base_source) == EXPECTED_BASE_RAW, "base drift before load")
    require(sha256_bytes(overlay_source) == EXPECTED_OVERLAY_RAW, "overlay drift before load")
    require(sha256_bytes(aggregator_source) == EXPECTED_AGGREGATOR_RAW, "aggregator drift before load")

    overlay = _private_module(
        name="g2_pion_creator_policy_v2_validated_private",
        path=OVERLAY_PATH,
        source=overlay_source,
        import_allowlist=OVERLAY_IMPORT_ALLOWLIST,
        builtin_allowlist=OVERLAY_BUILTIN_ALLOWLIST,
    )
    aggregator = _private_module(
        name="g2_pion_candidate_inventory_v3_validated_private",
        path=AGGREGATOR_PATH,
        source=aggregator_source,
        import_allowlist=AGGREGATOR_IMPORT_ALLOWLIST,
        builtin_allowlist=AGGREGATOR_BUILTIN_ALLOWLIST,
    )
    inspect = getattr(overlay, "inspect_module_zip", None)
    aggregate = getattr(aggregator, "aggregate_candidate_inventory", None)
    require(callable(inspect), "private inspect_module_zip missing")
    require(callable(aggregate), "private aggregate_candidate_inventory missing")

    def inspect_module_zip(raw_archive: bytes, *, module_prefix: str, limits=None):
        return inspect(
            base_source,
            raw_archive,
            module_prefix=module_prefix,
            limits=limits,
        )

    adapter = types.ModuleType("g2_pion_rung3_v3_validated_adapter")
    adapter.inspect_module_zip = inspect_module_zip
    adapter.aggregate_candidate_inventory = aggregate
    return adapter


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        result = validate_repository()
    except CheckError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "passed",
                "permitId": result["permit"]["permitId"],
                "permitRawSha256": result["permitRawSha256"],
                "permitSemanticSha256": result["permitSemanticSha256"],
                "archiveOpenCount": 0,
                "archiveReadPassCount": 0,
                "buildPathReadCount": 0,
                "outputPathReadCount": 0,
                "fileWriteCount": 0,
                "permitConsumptionState": "not_inspected",
                "reviewedSourceCompilerInvocationCount": 0,
                "repositoryOwnerAuthenticationRequired": False,
                "externalIdentityProofRequired": False,
                "executionPermitAuthenticationRequired": False,
                "userActionRequired": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
