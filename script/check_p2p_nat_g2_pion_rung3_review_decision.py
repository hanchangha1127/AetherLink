#!/usr/bin/env python3
"""Validate the preparation-only G2 Pion rung-three decision evidence.

The checker deliberately has no archive capability.  It opens only the closed
set of repository-relative, tracked evidence paths below, follows no symlinks,
never writes, and never invokes another program or a network API.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Iterable, Mapping, Sequence


BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG2 = f"{BASE}/rung-two"
RUNG3 = f"{BASE}/rung-three"

PROFILE = f"{BASE}/restricted-fork-profile.json"
RECEIPT = f"{RUNG2}/source-acquisition-receipt-v1.json"
RUNG2_PROGRESS = f"{RUNG2}/source-acquisition-progress-v2.json"
RUNG2_MANIFEST_V3 = f"{RUNG2}/evidence-manifest-v3.json"
RUNG2_SUPERSESSION_V2 = f"{RUNG2}/canonical-document-supersession-v2.json"
RUNG2_MANIFEST_V5 = f"{RUNG2}/evidence-manifest-v5.json"
DECISION = f"{RUNG3}/offline-source-review-decision-v1.json"
PROGRESS = f"{RUNG3}/offline-source-review-progress-v1.json"
POLICY = f"{RUNG3}/preparation-sandbox-policy-v1.json"
MANIFEST_V1 = f"{RUNG3}/evidence-manifest-v1.json"
SUPERSESSION = f"{RUNG3}/canonical-document-supersession-v1.json"
MANIFEST_V2 = f"{RUNG3}/evidence-manifest-v2.json"
PREPARER = "script/prepare_p2p_nat_g2_pion_rung3_review_decision.py"
PREPARER_TEST = "script/test_prepare_p2p_nat_g2_pion_rung3_review_decision.py"
CHECKER = "script/check_p2p_nat_g2_pion_rung3_review_decision.py"
CHECKER_TEST = "script/test_p2p_nat_g2_pion_rung3_review_decision.py"

CANONICAL_DOCS = (
    "docs/roadmap.md",
    "docs/handoff.md",
    "README.md",
    "shared/protocol/README.md",
    "docs/progress.md",
    "docs/qa-evidence.md",
)

TRACKED_READ_ALLOWLIST = frozenset(
    (
        PROFILE,
        RECEIPT,
        RUNG2_PROGRESS,
        RUNG2_MANIFEST_V3,
        RUNG2_SUPERSESSION_V2,
        RUNG2_MANIFEST_V5,
        DECISION,
        PROGRESS,
        POLICY,
        MANIFEST_V1,
        SUPERSESSION,
        MANIFEST_V2,
        PREPARER,
        PREPARER_TEST,
        CHECKER,
        CHECKER_TEST,
    )
    + CANONICAL_DOCS
)

V1_ARTIFACTS = (
    ("G2R3E001", DECISION, "metadata_only_offline_source_review_decision"),
    ("G2R3E002", POLICY, "preparation_only_archive_capability_absent_policy"),
    ("G2R3E003", PROGRESS, "zero_execution_progress_and_next_permit_boundary"),
    ("G2R3E004", PREPARER, "closed_constants_stdout_only_decision_preparer"),
    ("G2R3E005", PREPARER_TEST, "decision_preparer_isolation_and_schema_tests"),
    ("G2R3E006", CHECKER, "strict_tracked_preparation_evidence_checker"),
    ("G2R3E007", CHECKER_TEST, "checker_mutation_and_safe_read_tests"),
)
V2_ARTIFACTS = (
    ("G2R3E008", SUPERSESSION, "canonical_document_supersession_to_rung3_preparation"),
    ("G2R3E009", "docs/roadmap.md", "current_canonical_v1_delivery_roadmap"),
    ("G2R3E010", "docs/handoff.md", "current_canonical_session_handoff"),
    ("G2R3E011", "README.md", "current_root_project_status"),
    ("G2R3E012", "shared/protocol/README.md", "current_shared_protocol_status"),
    ("G2R3E013", "docs/progress.md", "current_progress_status"),
    ("G2R3E014", "docs/qa-evidence.md", "current_qa_checklist"),
)
V1_ROWS = tuple(path for _evidence_id, path, _role in V1_ARTIFACTS)
V2_ROWS = tuple(path for _evidence_id, path, _role in V2_ARTIFACTS)
EXPECTED_STATUS = "rung3_review_plan_recorded_execution_not_authorized"
EXPECTED_RESULT = "retained_archive_metadata_bound_preparation_only"
EXPECTED_NEXT = "prepare_separate_versioned_rung3_review_execution_permit"
EVIDENCE_BASIS = "static_contract_and_synthetic_tests_not_os_attestation"

EXPECTED_PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)
EXPECTED_VERIFICATION_IDS = (
    "g2-r3-egress-path-coverage",
    "g2-r3-ingress-path-coverage",
    "g2-r3-address-and-resolution-adversarial",
    "g2-r3-turn-tls-service-identity",
    "g2-r3-secure-session-promotion",
    "g2-r3-resource-and-event-bounds",
    "g2-r3-secret-free-diagnostics",
    "g2-r3-deadline-shutdown",
)
POLICY_ZERO_COUNTERS = (
    "archiveOpenCount",
    "archiveReadCount",
    "archiveEntryEnumerationCount",
    "materializationCount",
    "sourceObservationCount",
    "reviewFindingCount",
    "fileWriteCount",
    "subprocessCount",
    "networkOperationCount",
    "gitOperationCount",
    "compilerInvocationCount",
    "deviceOperationCount",
)
PROGRESS_ZERO_COUNTERS = (
    "archiveOpenCount",
    "archiveReadCount",
    "archiveEntryEnumerationCount",
    "materializationCount",
    "sourceObservationCount",
    "reviewFindingCount",
    "sourceFileWriteCount",
    "subprocessCount",
    "networkOperationCount",
    "gitOperationCount",
    "compilerInvocationCount",
    "deviceOperationCount",
)
FORBIDDEN_TRUE_SUFFIXES = (
    "authorized",
    "allowed",
    "performed",
    "used",
    "required",
    "created",
    "opened",
    "read",
    "written",
    "executed",
    "extracted",
    "materialized",
    "reviewed",
    "selected",
    "invoked",
)
POSITIVE_FALSE_EXCEPTIONS = frozenset(
    {
        "reviewPlanPreparationAllowed",
        "reviewPlanPreparationRecorded",
        "rungThreeReviewPlanPreparationRecorded",
        "technicalSafetyGatesRemainRequired",
        "repositoryOwnerAuthenticationIsNotATechnicalGate",
        "noAuthenticationOrUserActionRequested",
        "stdoutIsOnlyEmissionSurface",
        "separateVersionedPermitRequired",
        "exactArchiveIdentityMustBeRevalidatedFromOneNoFollowFileDescriptor",
        "ownerOnlyTemporaryAndReportStorageRequired",
        "exclusiveClaimAndAtomicNoReplacePublicationRequired",
        "deterministicBoundedJsonReportsOnly",
        "retained",
        "archiveRetained",
        "productEndpointAuthenticationRequired",
    }
)
FORBIDDEN_GENERATOR_IMPORTS = frozenset(
    {
        "asyncio", "ctypes", "fcntl", "glob", "http", "importlib", "mmap",
        "multiprocessing", "os", "pathlib", "random", "requests", "secrets",
        "shutil", "socket", "subprocess", "tempfile", "time", "urllib", "zipfile",
    }
)
FORBIDDEN_GENERATOR_CALLS = frozenset(
    {
        "__import__", "breakpoint", "compile", "eval", "exec", "input", "open",
        "popen", "read_bytes", "read_text", "run", "system", "urlopen",
        "write_bytes", "write_text",
    }
)
MAX_FILE_BYTES = 8 * 1024 * 1024

# These acyclic digests are the standalone checker's trust anchors.  Manifest
# v1/v2 raw bytes are intentionally excluded because v1 contains this checker
# and v2 binds v1; pinning either raw digest here would create a hash cycle.
PINNED_RAW_SHA256 = {
    PROFILE: "10e9436ae9b8f24c4447d12f8087b4f121810841ae33526e08fcc3d862d60a0f",
    RECEIPT: "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6",
    RUNG2_PROGRESS: "df1ad52bc6fff294b9bb54fd94a8eaacd76d9ff2b179be4a6752a867d229196f",
    RUNG2_MANIFEST_V3: "8ed1a2667153f77270531d7c373f5f61ed9eb9080bceab7c804c9b686259537e",
    RUNG2_SUPERSESSION_V2: "3a2b74ecde45b69204b9687904a4f88d731dfc532046e472ec22a4873765309a",
    RUNG2_MANIFEST_V5: "203e88cf73ad358fd6c73d8bb8d988efa966ffa67573d6e7dda9c03a2fe01f89",
    DECISION: "8e2c60b977ee139644c372581e066bfa720d4c5bf1c1809d34b142917abdfa16",
    PROGRESS: "651f8145ae91f7861b21565394db28b1608657c9bffd9a3e921aeafbff1fbabf",
    POLICY: "c615da9fb80d7af0162077503b55663cf428aaee434cef61a67807c234ea3558",
    PREPARER: "1a1641355182178c23526f568fa1e5fbe429745acc82ffcb59ccbe9f2bc9855b",
    PREPARER_TEST: "cc443da3f3d970b445b8578a911ba518336a7b971ce6b83977ea5375948fc408",
    CHECKER_TEST: "d69e4f1d9dfb47507626617f5e6242503b86722904cf2f6b4f509888b481ac0b",
    SUPERSESSION: "ec57f0712309ef459b19e8155ce4450bb4b2d81c32b04e4a97e242f6824735bd",
    "docs/roadmap.md": "a7a7bd364f273d15c1033b9b7d196fd59a5af8bad516a2f33df268b73f19ac67",
    "docs/handoff.md": "b98b3600745889092ddfb961bce4fe307128a509705527c462249a005b338477",
    "README.md": "557014e4ab9b53226f6fc5996d104ecbf3134ddbe4f0bf8db1b38b5d2ea6cd38",
    "shared/protocol/README.md": "53c602bd4f3c43b75a7c296cc9b90b73c2fc8e71ea1ac1efd9b136c2bb6acea8",
    "docs/progress.md": "6c6cdfa5612ee14178ac395ac732767bd8d3f5ca90fec01e7ca1b525a1df0c53",
    "docs/qa-evidence.md": "2eda0f4e7438b3fe8a38f8841847120f22b610aef32972dc2c043dc9fb6c1b44",
}
PINNED_SEMANTIC_SHA256 = {
    PROFILE: "9c929d186eedb10cc890d5540597724d6df1d719f174ed1965c79e4d50324be6",
    RECEIPT: "304a0b246050e446da9d25d9778c6cc05153c10d353d4b01963e2c566ab37880",
    RUNG2_PROGRESS: "d984cdbae6be447bf04e8f643687c8b2fd23e670c5826538b1b3f352ef470309",
    RUNG2_MANIFEST_V3: "61bfeb7f12bdbea38c73d7a1581f5ceada31bfc9b0ef64ee25e97f8c5c8d2221",
    RUNG2_SUPERSESSION_V2: "1c1245ceb52e0f2b90fcd89934b02fedaf3985466b4e4b53d9c1821d85921932",
    RUNG2_MANIFEST_V5: "fd738ae8de9909adf6d9dd915d4d861998c06bde97b10cb9e87c4cc9adea9d80",
    DECISION: "fe816c45fb080a619bfad426406618952adbc2fd909b6d02f90e4de172b4d5c5",
    PROGRESS: "e29a3745ec2a43bfdce0959d5b96baee679af2fb902dc6989436830cf59bd515",
    POLICY: "bf5de358234c03a5bfc96b66d4fd8b5f0464328f4733820899ce0f93219be64a",
    SUPERSESSION: "fb9204ae5800964de278988d6969c234762b2f750efe17014f4d53631ef946f9",
    "docs/roadmap.md": "c4c1bd03744480f9dec7b5a82044dfbaf18f364d65d90cde06f0a60c3076328e",
    "docs/handoff.md": "4eeba15b929d310e55441f99d53645c251cb1f8b7966fef09683f870863dc27d",
    "README.md": "a435a8bdb86fd8c2a12106bdae2f9f167cf6f034fae759baaf7713471d6b3c5b",
    "shared/protocol/README.md": "d701bde56308fba26ede86b080ac1c6e489de2a66ba81f1c43ebc8e2d8c64e06",
    "docs/progress.md": "41bd164aa03592344106e21fffc9cf41586815192a2b86b292db122c5410b1b6",
    "docs/qa-evidence.md": "85f60e8cda6ca4ab2a1785f729bc5c2c7f33f091290da7a63fc0e4e90835400a",
}
PINNED_COLLECTION_SHA256 = {
    RUNG2_MANIFEST_V3: "0e5e41990ed8b46dd40dba9808f29f40e007142ed0ae77408d4d8afa6f4142a0",
    RUNG2_MANIFEST_V5: "adb1fbce766b0750e186285024156abea290d80763eea142420192aa8261d0a8",
    MANIFEST_V2: "49b517e8f35b4db4537de193e0b68b3d6aa9dde173aa080edd8adb122af6567a",
}

DECISION_KEYS = frozenset(
    {
        "archiveBinding", "contentBinding", "decisionBoundary", "decisionId",
        "documentType", "forwardOnlyBindings", "futureExecutionPermitRequirements",
        "futureExecutionProhibitions", "nextAction", "personalProjectBoundary",
        "plannedStaticReview", "policyBinding", "predecessorBindings",
        "preparationScope", "recordedDate", "result", "schemaVersion", "status",
    }
)
PROGRESS_KEYS = frozenset(
    {
        "archiveState", "decisionBinding", "documentType", "evidenceBasis",
        "executionBoundary", "forwardOnlyBindings", "nextAction",
        "personalProjectBoundary", "plannedVerification", "policyBinding",
        "predecessorBindings", "preparationToolBinding", "progressId",
        "recordedDate", "result", "schemaVersion", "status",
        "zeroOperationCounters",
    }
)
SUPERSESSION_KEYS = frozenset(
    {
        "currentDocumentState", "documentType", "executionBoundary", "nextAction",
        "predecessorManifestBinding", "predecessorSupersessionBinding",
        "preparationDecisionBinding", "preparationProgressBinding",
        "previousDocumentState", "reason", "recordedDate", "result",
        "schemaVersion", "semanticGuard", "status", "supersessionId",
    }
)
MANIFEST_BASE_KEYS = frozenset(
    {
        "archiveMaterializedByRungThree", "archiveReadByRungThree",
        "archiveRetained", "artifactCount", "artifacts", "artifactScope",
        "candidateSelected", "collectionDigestAlgorithm", "collectionSha256",
        "compilerInvoked", "dependencyInstalled", "deviceOperationPerformed",
        "documentType", "evidenceBasis", "externalIdentityProofRequired",
        "gitOperationPerformed", "librarySelected", "manifestId", "networkUsed",
        "nextAction", "orderingRule", "predecessorManifestBinding",
        "productEndpointAuthenticationRequired", "recordedDate",
        "repositoryOwnerAuthenticationRequired", "result",
        "reviewExecutionAuthorized", "schemaVersion", "socketCreated",
        "sourceReviewPerformed", "status", "userActionRequired",
    }
)
MANIFEST_IDENTITY = {
    False: {
        "documentType": "aetherlink.g2-pion-rung3-preparation-evidence-manifest",
        "schemaVersion": "1.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung3-decision-evidence-manifest-v1",
        "recordedDate": "2026-07-23",
        "artifactScope": "rung3_preparation_delta_only_no_archive_or_source_artifacts",
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": (
            "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_"
            "repo_relative_path_newline"
        ),
    },
    True: {
        "documentType": (
            "aetherlink.g2-pion-rung3-canonical-document-sync-evidence-manifest"
        ),
        "schemaVersion": "1.0",
        "manifestId": (
            "g2-pion-ice-v4.3.0-rung3-canonical-document-sync-"
            "evidence-manifest-v2"
        ),
        "recordedDate": "2026-07-23",
        "artifactScope": "post_v1_canonical_document_sync_delta_only",
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": (
            "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_"
            "repo_relative_path_newline"
        ),
    },
}


class CheckError(ValueError):
    """The closed evidence set failed validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_type(value: Any, expected: type, label: str) -> None:
    require(type(value) is expected, f"{label} must be {expected.__name__}")


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


def semantic_sha256(path: str, data: bytes, parsed: Any | None = None) -> str:
    if path.endswith(".json"):
        require(parsed is not None, f"{path}: parsed JSON required for semantic hash")
        payload = json.dumps(
            parsed,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256_bytes(payload)
    text = data.decode("utf-8")
    normalized = " ".join(text.split()).lower()
    return sha256_bytes(normalized.encode("utf-8"))


def strict_json(data: bytes, path: str) -> Any:
    require(data.endswith(b"\n"), f"{path}: final LF required")
    require(b"\r" not in data, f"{path}: CR bytes forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise CheckError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise CheckError(f"{path}: non-finite JSON number {value!r}")

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{path}: invalid UTF-8 JSON: {error}") from error
    _reject_nonfinite(value, path)
    return value


def _reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite float")
    elif type(value) is list:
        for item in value:
            _reject_nonfinite(item, label)
    elif type(value) is dict:
        for key, item in value.items():
            require_type(key, str, f"{label} object key")
            _reject_nonfinite(item, label)


def validate_relative_path(path: str) -> tuple[str, ...]:
    require_type(path, str, "path")
    require(path in TRACKED_READ_ALLOWLIST, f"unlisted read forbidden: {path}")
    require("\\" not in path and "\x00" not in path, f"unsafe path: {path}")
    pure = PurePosixPath(path)
    require(not pure.is_absolute(), f"absolute path forbidden: {path}")
    parts = pure.parts
    require(parts and all(part not in ("", ".", "..") for part in parts), f"unsafe path: {path}")
    require(parts[0] != "build", f"build path forbidden: {path}")
    require(not path.lower().endswith((".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z")), f"archive path forbidden: {path}")
    return parts


class SafeTrackedReader:
    """Bounded regular-file reader using component-wise O_NOFOLLOW opens."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        parts = validate_relative_path(path)
        if path in self._cache:
            return self._cache[path]
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
        file_flags = os.O_RDONLY | nofollow
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
                info = os.fstat(file_fd)
                require(stat.S_ISREG(info.st_mode), f"{path}: regular file required")
                require(info.st_nlink == 1, f"{path}: exactly one hard link required")
                require(0 <= info.st_size <= MAX_FILE_BYTES, f"{path}: file size out of bounds")
                remaining = info.st_size
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(file_fd, min(remaining, 65536))
                    require(bool(chunk), f"{path}: unexpected EOF")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(file_fd, 1) == b"", f"{path}: file grew during read")
                after = os.fstat(file_fd)
                require(
                    (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                    f"{path}: file changed during read",
                )
                data = b"".join(chunks)
            finally:
                os.close(file_fd)
        except OSError as error:
            raise CheckError(f"{path}: safe read failed: {error}") from error
        finally:
            for fd in reversed(opened_dirs):
                os.close(fd)
            os.close(root_fd)
        self._cache[path] = data
        return data

    def json(self, path: str) -> Any:
        return strict_json(self.read(path), path)


def validate_pinned_identity(reader: SafeTrackedReader) -> None:
    """Reject coordinated drift in every acyclic predecessor/current anchor."""

    for path, expected in PINNED_RAW_SHA256.items():
        observed = sha256_bytes(reader.read(path))
        require(
            observed == expected,
            f"pinned raw SHA-256 mismatch for {path}: expected {expected}, got {observed}",
        )
    for path, expected in PINNED_SEMANTIC_SHA256.items():
        raw = reader.read(path)
        parsed = reader.json(path) if path.endswith(".json") else None
        observed = semantic_sha256(path, raw, parsed)
        require(
            observed == expected,
            f"pinned semantic SHA-256 mismatch for {path}: expected {expected}, got {observed}",
        )
    for path, expected in PINNED_COLLECTION_SHA256.items():
        document = reader.json(path)
        require_type(document, dict, f"pinned collection {path}")
        observed = document.get("collectionSha256")
        require(
            observed == expected,
            f"pinned collection SHA-256 mismatch for {path}: expected {expected}, got {observed}",
        )


def walk_objects(value: Any) -> Iterable[Mapping[str, Any]]:
    if type(value) is dict:
        yield value
        for nested in value.values():
            yield from walk_objects(nested)
    elif type(value) is list:
        for nested in value:
            yield from walk_objects(nested)


def find_binding(value: Any, path: str) -> Mapping[str, Any] | None:
    for item in walk_objects(value):
        if item.get("path") == path:
            return item
    return None


def verify_binding(reader: SafeTrackedReader, binding: Mapping[str, Any], label: str) -> None:
    path = binding.get("path")
    require_type(path, str, f"{label}.path")
    raw = reader.read(path)
    parsed = reader.json(path) if path.endswith(".json") else None
    raw_claim = binding.get("sha256", binding.get("rawSha256"))
    require_type(raw_claim, str, f"{label}.sha256")
    require(raw_claim == sha256_bytes(raw), f"{label}: raw SHA-256 mismatch for {path}")
    if "semanticSha256" in binding:
        require_type(binding["semanticSha256"], str, f"{label}.semanticSha256")
        require(
            binding["semanticSha256"] == semantic_sha256(path, raw, parsed),
            f"{label}: semantic SHA-256 mismatch for {path}",
        )
    if "collectionSha256" in binding:
        require_type(parsed, dict, f"{label} collection target")
        require(
            binding["collectionSha256"] == parsed.get("collectionSha256"),
            f"{label}: collection SHA-256 mismatch for {path}",
        )


def require_closed_state(document: Mapping[str, Any], label: str) -> None:
    for key, expected in (
        ("status", EXPECTED_STATUS),
        ("result", EXPECTED_RESULT),
        ("nextAction", EXPECTED_NEXT),
    ):
        require(document.get(key) == expected, f"{label}.{key} mismatch")


def require_zero_boundary(
    value: Any,
    label: str,
    *,
    required_counters: Sequence[str] = (),
) -> None:
    counters: dict[str, int] = {}
    for item in walk_objects(value):
        for key, nested in item.items():
            if key in required_counters:
                require(type(nested) is int and nested == 0, f"{label}.{key} must be integer zero")
                counters[key] = nested
            elif (
                type(nested) is int
                and nested != 0
                and key in {
                    *POLICY_ZERO_COUNTERS,
                    *PROGRESS_ZERO_COUNTERS,
                    "repositoryFilesRead",
                    "repositoryFilesWritten",
                    "archiveBytesRead",
                }
            ):
                raise CheckError(f"{label}.{key} must be zero at preparation boundary")
            if type(nested) is bool and nested and key not in POSITIVE_FALSE_EXCEPTIONS:
                lower = key.lower()
                if any(lower.endswith(suffix) for suffix in FORBIDDEN_TRUE_SUFFIXES):
                    raise CheckError(f"{label}.{key} must be false at preparation boundary")
    require(set(counters) == set(required_counters), f"{label}: exact zero counters missing")


def validate_policy(document: Any) -> None:
    require_type(document, dict, "policy")
    require(document.get("status") == "preparation_only_archive_capability_absent", "policy.status mismatch")
    require(document.get("evidenceBasis") == EVIDENCE_BASIS, "policy.evidenceBasis mismatch")
    generator = document.get("generatorPolicy")
    checker = document.get("checkerPolicy")
    denied = document.get("deniedPathRules")
    boundary = document.get("executionBoundary")
    require_type(generator, dict, "policy.generatorPolicy")
    require_type(checker, dict, "policy.checkerPolicy")
    require_type(denied, dict, "policy.deniedPathRules")
    require_type(boundary, dict, "policy.executionBoundary")
    require(generator.get("path") == PREPARER, "policy generator path mismatch")
    require(generator.get("allowedCliModes") == ["--check", "--emit-decision"], "policy generator CLI mismatch")
    require(generator.get("fileReadAllowlist") == [], "generator file reads must be empty")
    require(generator.get("fileWriteAllowlist") == [], "generator file writes must be empty")
    require(checker.get("path") == CHECKER, "policy checker path mismatch")
    require(set(checker.get("trackedReadAllowlist", [])) == set(TRACKED_READ_ALLOWLIST), "policy checker allowlist mismatch")
    require(checker.get("fileWriteAllowlist") == [], "checker file writes must be empty")
    for key in (
        "archiveReadAllowed", "sourceTreeReadAllowed", "buildDirectoryReadAllowed",
        "symlinkReadAllowed", "subprocessAllowed", "networkAllowed", "gitAllowed",
    ):
        require(checker.get(key) is False, f"policy checker {key} must be false")
    for key in ("absolutePathInputsAllowed", "parentTraversalAllowed", "backslashPathSeparatorsAllowed", "buildPrefixAllowed", "archiveSuffixesAllowed"):
        require(denied.get(key) is False, f"policy deniedPathRules.{key} must be false")
    require(document.get("zeroOperationCounters") == {key: 0 for key in POLICY_ZERO_COUNTERS}, "policy zero counters mismatch")
    require(boundary.get("reviewPlanPreparationAllowed") is True, "policy preparation must be allowed")
    for key, value in boundary.items():
        if key not in ("reviewPlanPreparationAllowed", "productEndpointAuthenticationRequired"):
            require(value is False, f"policy executionBoundary.{key} must be false")


def validate_generator_source(data: bytes) -> None:
    try:
        source = data.decode("utf-8")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise CheckError(f"generator source invalid: {error}") from error
    imports: set[str] = set()
    calls: set[str] = set()
    flags: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
                if node.func.attr == "add_argument":
                    flags.extend(
                        arg.value
                        for arg in node.args
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--")
                    )
    require(imports.isdisjoint(FORBIDDEN_GENERATOR_IMPORTS), f"generator forbidden imports: {sorted(imports & FORBIDDEN_GENERATOR_IMPORTS)}")
    require(calls.isdisjoint(FORBIDDEN_GENERATOR_CALLS), f"generator forbidden calls: {sorted(calls & FORBIDDEN_GENERATOR_CALLS)}")
    require(sorted(flags) == ["--check", "--emit-decision"], "generator must expose exactly two CLI flags")


def validate_decision(document: Any, raw: bytes, reader: SafeTrackedReader) -> None:
    require_type(document, dict, "decision")
    require(set(document) == set(DECISION_KEYS), "decision top-level schema mismatch")
    require_closed_state(document, "decision")
    require(b"build/" not in raw and b".zip" not in raw.lower(), "decision must not copy archive paths")
    content = document.get("contentBinding")
    require_type(content, dict, "decision.contentBinding")
    require(content.get("algorithm") == "sha256", "decision content algorithm mismatch")
    require(
        set(content) == {"algorithm", "canonicalization", "scope", "sha256"},
        "decision content binding schema mismatch",
    )
    require(content.get("scope") == "decision_without_contentBinding", "decision content scope mismatch")
    require(
        content.get("canonicalization")
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "decision canonicalization mismatch",
    )
    core = {key: value for key, value in document.items() if key != "contentBinding"}
    require(content.get("sha256") == sha256_bytes(canonical_json_bytes(core)), "decision content binding mismatch")
    planned = document.get("plannedStaticReview")
    require_type(planned, dict, "decision.plannedStaticReview")
    require(tuple(planned.get("patchUnits", ())) == EXPECTED_PATCH_UNITS, "decision patch units mismatch")
    units = planned.get("profileVerificationUnits")
    require_type(units, list, "decision profile verification units")
    require(
        units == [{"id": item, "status": "planned_not_performed"} for item in EXPECTED_VERIFICATION_IDS],
        "decision verification units mismatch",
    )
    require_zero_boundary(document, "decision")
    archive = document.get("archiveBinding")
    require_type(archive, dict, "decision.archiveBinding")
    for key, expected in (
        ("receiptPath", RECEIPT),
        ("archiveMetadataJsonPointer", "/archive"),
        ("archiveEvidenceId", "G2R2E009"),
        ("archivePathCopiedIntoDecision", False),
        ("expectedBytes", 293023),
        ("entryCount", 129),
        ("fileCount", 129),
        ("totalUncompressedBytes", 1131286),
        ("rawSha256", "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"),
        ("moduleH1", "h1:X8l4s9zV2HeTKX33nulWAFXAEo5KhIVzOsY62/3t/LM="),
        ("goModH1", "h1:obAyD+J+Hzs7QA7Y8YXHp5uIn6gb7z87pKedXZkrcFU="),
        ("modulePath", "github.com/pion/ice/v4"),
        ("version", "v4.3.0"),
        ("tag", "v4.3.0"),
        ("commitSha1", "1e8716372f2bb52e45bf2a7172e4fb1004251c46"),
        ("treeSha1", "df59c87a634cfea261582cd9932554663112a975"),
    ):
        require(type(archive.get(key)) is type(expected) and archive.get(key) == expected, f"decision archive metadata mismatch: {key}")
    for key in ("archiveReadByThisDecision", "archiveMaterializedByThisDecision", "sourceReviewedByThisDecision"):
        require(archive.get(key) is False, f"decision archive boundary mismatch: {key}")
    forward = document.get("forwardOnlyBindings")
    require_type(forward, dict, "decision.forwardOnlyBindings")
    require(not any("sha256" in key.lower() for item in walk_objects(forward) for key in item), "forward-only decision bindings must not carry hashes")
    required_parents = (
        PROFILE, RECEIPT, RUNG2_PROGRESS, RUNG2_MANIFEST_V3,
        RUNG2_SUPERSESSION_V2, RUNG2_MANIFEST_V5, POLICY,
    )
    for path in required_parents:
        binding = find_binding(document, path)
        require(binding is not None, f"decision missing predecessor binding: {path}")
        verify_binding(reader, binding, "decision predecessor")


def validate_progress(document: Any, reader: SafeTrackedReader) -> None:
    require_type(document, dict, "progress")
    require(set(document) == set(PROGRESS_KEYS), "progress top-level schema mismatch")
    require_closed_state(document, "progress")
    evidence_basis = document.get("evidenceBasis")
    require_type(evidence_basis, dict, "progress.evidenceBasis")
    require(evidence_basis.get("kind") == EVIDENCE_BASIS, "progress evidenceBasis.kind mismatch")
    require(evidence_basis.get("actualArchiveAccessEvidencePresent") is False, "progress must not claim archive access evidence")
    require(evidence_basis.get("operatingSystemSandboxAttestationPresent") is False, "progress must not claim OS attestation")
    counters = document.get("zeroOperationCounters")
    require_type(counters, dict, "progress.zeroOperationCounters")
    require(
        counters.get("counterScope")
        == "rung3_review_execution_not_documentation_artifact_creation_or_checker_reads",
        "progress counter scope mismatch",
    )
    require(
        set(counters) == {"counterScope", *PROGRESS_ZERO_COUNTERS},
        "progress zero counter schema mismatch",
    )
    require_zero_boundary(document, "progress", required_counters=PROGRESS_ZERO_COUNTERS)
    require(
        document.get("plannedVerification")
        == [{"id": item, "status": "planned_not_performed"} for item in EXPECTED_VERIFICATION_IDS],
        "progress planned verification mismatch",
    )
    archive = document.get("archiveState")
    require_type(archive, dict, "progress.archiveState")
    for key, expected in (
        ("receiptPath", RECEIPT),
        ("archiveMetadataJsonPointer", "/archive"),
        ("archiveEvidenceId", "G2R2E009"),
        ("archivePathCopiedIntoProgress", False),
        ("expectedBytes", 293023),
        ("rawSha256", "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"),
    ):
        require(type(archive.get(key)) is type(expected) and archive.get(key) == expected, f"progress archive metadata mismatch: {key}")
    for key in ("archiveOpenedByRungThree", "archiveReadByRungThree", "archiveMaterializedByRungThree", "sourceReviewedByRungThree"):
        require(archive.get(key) is False, f"progress archive boundary mismatch: {key}")
    tool = document.get("preparationToolBinding")
    require_type(tool, dict, "progress.preparationToolBinding")
    require(
        set(tool)
        == {"generatorPath", "generatorRawSha256", "testPath", "testRawSha256", "offlineTestCount", "offlineTestsPassed"},
        "progress preparation tool binding schema mismatch",
    )
    require(tool.get("generatorPath") == PREPARER and tool.get("testPath") == PREPARER_TEST, "progress preparation tool paths mismatch")
    require(tool.get("generatorRawSha256") == sha256_bytes(reader.read(PREPARER)), "progress generator hash mismatch")
    require(tool.get("testRawSha256") == sha256_bytes(reader.read(PREPARER_TEST)), "progress generator test hash mismatch")
    require(tool.get("offlineTestCount") == 15 and tool.get("offlineTestsPassed") is True, "progress generator test result mismatch")
    binding = find_binding(document, DECISION)
    require(binding is not None, "progress missing decision binding")
    require("semanticSha256" in binding, "progress decision semantic binding required")
    verify_binding(reader, binding, "progress decision")
    for path in (RUNG2_SUPERSESSION_V2, RUNG2_MANIFEST_V5):
        parent = find_binding(document, path)
        require(parent is not None, f"progress missing parent binding: {path}")
        verify_binding(reader, parent, "progress predecessor")


def collection_sha256(artifacts: Sequence[Mapping[str, Any]]) -> str:
    lines: list[str] = []
    for artifact in artifacts:
        evidence_id = artifact.get("evidenceId")
        digest = artifact.get("sha256")
        path = artifact.get("path")
        require_type(evidence_id, str, "artifact.evidenceId")
        require_type(digest, str, "artifact.sha256")
        require_type(path, str, "artifact.path")
        lines.append(f"{evidence_id}\t{digest}\t{path}\n")
    return sha256_bytes("".join(lines).encode("utf-8"))


def validate_manifest(
    document: Any,
    expected_artifacts: Sequence[tuple[str, str, str]],
    reader: SafeTrackedReader,
    predecessor: str,
) -> None:
    require_type(document, dict, "manifest")
    is_v2 = tuple(expected_artifacts) == V2_ARTIFACTS
    expected_keys = set(MANIFEST_BASE_KEYS)
    if is_v2:
        expected_keys.update({"semanticBindings", "preparationBindings"})
    require(set(document) == expected_keys, "manifest top-level schema mismatch")
    require_closed_state(document, "manifest")
    for key, expected in MANIFEST_IDENTITY[is_v2].items():
        require(
            type(document.get(key)) is type(expected) and document.get(key) == expected,
            f"manifest.{key} mismatch",
        )
    require(document.get("evidenceBasis") == EVIDENCE_BASIS, "manifest evidence basis mismatch")
    require(document.get("archiveRetained") is True, "manifest must preserve retained metadata state")
    require(document.get("productEndpointAuthenticationRequired") is True, "product endpoint authentication boundary missing")
    require_zero_boundary(document, "manifest")
    for key in (
        "archiveReadByRungThree", "archiveMaterializedByRungThree",
        "sourceReviewPerformed", "reviewExecutionAuthorized", "candidateSelected",
        "librarySelected", "dependencyInstalled", "compilerInvoked", "socketCreated",
        "networkUsed", "gitOperationPerformed", "deviceOperationPerformed",
        "externalIdentityProofRequired", "userActionRequired",
        "repositoryOwnerAuthenticationRequired",
    ):
        require(document.get(key) is False, f"manifest.{key} must be false")
    artifacts = document.get("artifacts")
    require_type(artifacts, list, "manifest.artifacts")
    require(document.get("artifactCount") == len(expected_artifacts), "manifest artifactCount mismatch")
    observed_rows = tuple(
        (item.get("evidenceId"), item.get("path"), item.get("role"))
        for item in artifacts
    )
    require(observed_rows == tuple(expected_artifacts), "manifest exact evidence ID/path/role rows mismatch")
    for artifact in artifacts:
        require(set(artifact) == {"evidenceId", "path", "sha256", "role"}, "manifest artifact schema mismatch")
        verify_binding(reader, artifact, "manifest artifact")
    require(document.get("collectionSha256") == collection_sha256(artifacts), "manifest collection mismatch")
    binding = document.get("predecessorManifestBinding")
    require_type(binding, dict, "manifest.predecessorManifestBinding")
    require(
        set(binding) == {"path", "sha256", "semanticSha256", "collectionSha256"},
        "manifest predecessor binding schema mismatch",
    )
    require(binding.get("path") == predecessor, f"manifest predecessor mismatch: {predecessor}")
    verify_binding(reader, binding, "manifest predecessor")
    require(document.get("sourceReviewPerformed") is False, "manifest source review must be false")
    require(document.get("reviewExecutionAuthorized") is False, "manifest review execution must be false")
    require(document.get("externalIdentityProofRequired") is False, "manifest external identity proof must be false")
    require(document.get("userActionRequired") is False, "manifest user action must be false")
    require(document.get("repositoryOwnerAuthenticationRequired") is False, "manifest owner authentication must be false")


def validate_supersession(document: Any, reader: SafeTrackedReader) -> None:
    require_type(document, dict, "supersession")
    require(set(document) == set(SUPERSESSION_KEYS), "supersession top-level schema mismatch")
    require_closed_state(document, "supersession")
    previous = document.get("previousDocumentState")
    current = document.get("currentDocumentState")
    guard = document.get("semanticGuard")
    boundary = document.get("executionBoundary")
    require_type(previous, dict, "supersession.previousDocumentState")
    require_type(current, dict, "supersession.currentDocumentState")
    require_type(guard, dict, "supersession.semanticGuard")
    require_type(boundary, dict, "supersession.executionBoundary")
    require_closed_state(current, "supersession.currentDocumentState")
    previous_docs = previous.get("documents")
    current_docs = current.get("documents")
    require_type(previous_docs, list, "supersession previous documents")
    require_type(current_docs, list, "supersession current documents")
    require(tuple(item.get("path") for item in previous_docs) == CANONICAL_DOCS, "supersession previous scope mismatch")
    require(tuple(item.get("path") for item in current_docs) == CANONICAL_DOCS, "supersession current scope mismatch")
    predecessor = reader.json(RUNG2_SUPERSESSION_V2)
    old_docs = predecessor.get("currentDocumentState", {}).get("documents")
    require_type(old_docs, list, "rung2 supersession current documents")
    old_hashes = {item.get("path"): item.get("sha256") for item in old_docs}
    for item in previous_docs:
        require(set(item) >= {"path", "sha256"}, "supersession previous document schema")
        require(item.get("sha256") == old_hashes.get(item.get("path")), "supersession previous hash mismatch")
    for item in current_docs:
        require(set(item) >= {"path", "sha256", "semanticSha256"}, "supersession current semantic binding required")
        verify_binding(reader, item, "supersession current document")
    require(tuple(guard.get("scope", ())) == CANONICAL_DOCS, "semantic guard scope mismatch")
    require(guard.get("historicalCheckpointToken") == "at_that_checkpoint", "historical checkpoint token mismatch")
    require(guard.get("requiredCurrentStatus") == EXPECTED_STATUS, "semantic guard status mismatch")
    require(guard.get("requiredCurrentResult") == EXPECTED_RESULT, "semantic guard result mismatch")
    require(guard.get("requiredCurrentNextAction") == EXPECTED_NEXT, "semantic guard next action mismatch")
    require(
        guard.get("historicalNextActionKey") == "recordedNextActionAtThatCheckpoint",
        "historical next-action key mismatch",
    )
    require(
        guard.get("historicalNextAction")
        == "prepare_versioned_rung3_offline_source_review_decision",
        "historical next-action value mismatch",
    )
    require(guard.get("historicalNextActionOccurrencePerDocument") == 1, "historical occurrence count contract mismatch")
    historical_assignment = (
        "recordednextactionatthatcheckpoint="
        "prepare_versioned_rung3_offline_source_review_decision"
    )
    for path in CANONICAL_DOCS:
        normalized = " ".join(reader.read(path).decode("utf-8").split()).lower()
        for token in (EXPECTED_STATUS, EXPECTED_RESULT, EXPECTED_NEXT):
            require(token.lower() in normalized, f"{path}: missing current semantic token {token}")
        require(normalized.count(historical_assignment) == 1, f"{path}: historical rung3 next action must occur exactly once")
        assignment_index = normalized.index(historical_assignment)
        nearby = normalized[max(0, assignment_index - 160):assignment_index]
        require("at_that_checkpoint" in nearby, f"{path}: historical rung3 next action is not checkpoint-scoped")
    for key, value in boundary.items():
        if key not in ("productEndpointAuthenticationRequired", "rungThreeReviewPlanPreparationRecorded"):
            require(value is False, f"supersession executionBoundary.{key} must be false")
    require(boundary.get("rungThreeReviewPlanPreparationRecorded") is True, "supersession must record plan preparation")
    for path in (RUNG2_SUPERSESSION_V2, RUNG2_MANIFEST_V5):
        binding = find_binding(document, path)
        require(binding is not None, f"supersession missing predecessor: {path}")
        verify_binding(reader, binding, "supersession predecessor")


def check_repository(
    root: Path,
    *,
    enforce_pinned_identity: bool = True,
) -> dict[str, Any]:
    reader = SafeTrackedReader(root)
    if enforce_pinned_identity:
        validate_pinned_identity(reader)
    policy = reader.json(POLICY)
    validate_policy(policy)
    validate_generator_source(reader.read(PREPARER))
    decision_raw = reader.read(DECISION)
    decision = strict_json(decision_raw, DECISION)
    validate_decision(decision, decision_raw, reader)
    progress = reader.json(PROGRESS)
    validate_progress(progress, reader)
    manifest_v1 = reader.json(MANIFEST_V1)
    validate_manifest(manifest_v1, V1_ARTIFACTS, reader, RUNG2_MANIFEST_V5)
    supersession = reader.json(SUPERSESSION)
    validate_supersession(supersession, reader)
    manifest_v2 = reader.json(MANIFEST_V2)
    validate_manifest(manifest_v2, V2_ARTIFACTS, reader, MANIFEST_V1)
    semantic_bindings = manifest_v2.get("semanticBindings")
    require_type(semantic_bindings, list, "manifest-v2.semanticBindings")
    require(tuple(item.get("path") for item in semantic_bindings) == CANONICAL_DOCS, "manifest-v2 semantic binding scope mismatch")
    for item in semantic_bindings:
        require(set(item) == {"path", "semanticSha256"}, "manifest-v2 semantic binding schema mismatch")
        raw = reader.read(item["path"])
        require(item["semanticSha256"] == semantic_sha256(item["path"], raw), "manifest-v2 semantic digest mismatch")
    preparation_bindings = manifest_v2.get("preparationBindings")
    require_type(preparation_bindings, dict, "manifest-v2.preparationBindings")
    require(
        set(preparation_bindings) == {"decision", "progress", "policy", "canonicalSupersession"},
        "manifest-v2 preparation binding schema mismatch",
    )
    for label, path in (
        ("decision", DECISION),
        ("progress", PROGRESS),
        ("policy", POLICY),
        ("canonicalSupersession", SUPERSESSION),
    ):
        binding = preparation_bindings.get(label)
        require_type(binding, dict, f"manifest-v2.preparationBindings.{label}")
        require(binding.get("path") == path, f"manifest-v2 preparation path mismatch: {label}")
        require(set(binding) == {"path", "sha256", "semanticSha256"}, f"manifest-v2 preparation binding schema mismatch: {label}")
        verify_binding(reader, binding, f"manifest-v2 preparation binding {label}")
    return {
        "status": "passed",
        "pinnedIdentityEnforced": enforce_pinned_identity,
        "checkedTrackedFiles": len(reader._cache),
        "archiveRead": False,
        "buildDirectoryRead": False,
        "sourceReviewPerformed": False,
        "reviewExecutionAuthorized": False,
        "repositoryOwnerAuthenticationRequired": False,
        "externalIdentityProofRequired": False,
        "productEndpointAuthenticationRequired": True,
        "userActionRequired": False,
        "nextAction": EXPECTED_NEXT,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        result = check_repository(Path(__file__).resolve().parents[1])
    except CheckError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
