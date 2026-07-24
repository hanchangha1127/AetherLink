#!/usr/bin/env python3
"""Offline validation for the consumed G2 Pion rung-two acquisition receipt."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
RUNG_TWO_ROOT = (
    ROOT
    / "docs/security-hardening/production-p2p-nat-v1"
    / "g2-pion-restricted-fork-v1/rung-two"
)
BASE_CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung2_acquisition_authority.py"
RUNNER_PATH = ROOT / "script/acquire_p2p_nat_g2_pion_source_once.py"
RUNNER_TEST_PATH = ROOT / "script/test_acquire_p2p_nat_g2_pion_source_once.py"
RECEIPT_PATH = RUNG_TWO_ROOT / "source-acquisition-receipt-v1.json"
PROGRESS_PATH = RUNG_TWO_ROOT / "source-acquisition-progress-v2.json"
MANIFEST_PATH = RUNG_TWO_ROOT / "evidence-manifest-v3.json"
CANONICAL_SYNC_MANIFEST_PATH = RUNG_TWO_ROOT / "evidence-manifest-v4.json"
CANONICAL_SEMANTIC_SYNC_MANIFEST_PATH = RUNG_TWO_ROOT / "evidence-manifest-v5.json"
CLAIM_PATH = (
    ROOT
    / "build/offline-source/pion-ice-v4.3.0/original"
    / ".g2-pion-ice-v4.3.0-source-acquisition-v1.claim"
)
ARCHIVE_PATH = (
    ROOT
    / "build/offline-source/pion-ice-v4.3.0/original"
    / "github.com-pion-ice-v4@v4.3.0.zip"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_module("g2_pion_rung2_base_authority", BASE_CHECKER_PATH)
RUNNER = load_module("g2_pion_rung2_receipt_runner", RUNNER_PATH)
ReceiptValidationError = BASE.RungTwoValidationError

EXPECTED_RAW_SHA256 = {
    RUNNER_PATH: "a63c5d8905ee3b91537b84993116334b3e237d84a66a342febdcccbef9603e71",
    RUNNER_TEST_PATH: "f5b7804f4d596fc4696ca874e52477190470a19f0d3a70992ef071697b757cee",
    RECEIPT_PATH: "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6",
    PROGRESS_PATH: "df1ad52bc6fff294b9bb54fd94a8eaacd76d9ff2b179be4a6752a867d229196f",
    MANIFEST_PATH: "8ed1a2667153f77270531d7c373f5f61ed9eb9080bceab7c804c9b686259537e",
    CANONICAL_SYNC_MANIFEST_PATH: "eb2352de7623706095b6208edcc58b9550e1a1501ed2482739f89525c74da022",
    CANONICAL_SEMANTIC_SYNC_MANIFEST_PATH: "203e88cf73ad358fd6c73d8bb8d988efa966ffa67573d6e7dda9c03a2fe01f89",
    CLAIM_PATH: "49c221d8b31a7a87d85e04bbea3dc949b3f2afcc74a32c97d271698dd787562f",
    ARCHIVE_PATH: BASE.RAW_ARCHIVE_SHA256,
}
EXPECTED_SEMANTIC_SHA256 = {
    RECEIPT_PATH: "304a0b246050e446da9d25d9778c6cc05153c10d353d4b01963e2c566ab37880",
    PROGRESS_PATH: "d984cdbae6be447bf04e8f643687c8b2fd23e670c5826538b1b3f352ef470309",
    MANIFEST_PATH: "61bfeb7f12bdbea38c73d7a1581f5ceada31bfc9b0ef64ee25e97f8c5c8d2221",
    CANONICAL_SYNC_MANIFEST_PATH: "718a95c578267943a5011ba8bbb50e732abfa6de84d7f5de9bff87b9a8b11bad",
    CANONICAL_SEMANTIC_SYNC_MANIFEST_PATH: "fd738ae8de9909adf6d9dd915d4d861998c06bde97b10cb9e87c4cc9adea9d80",
}
RECEIPT_SHA256 = EXPECTED_RAW_SHA256[RECEIPT_PATH]
PROGRESS_SHA256 = EXPECTED_RAW_SHA256[PROGRESS_PATH]
MANIFEST_COLLECTION_SHA256 = (
    "0e5e41990ed8b46dd40dba9808f29f40e007142ed0ae77408d4d8afa6f4142a0"
)
SOURCE_URL = BASE.SOURCE_URL
OUTPUT_PATH = BASE.OUTPUT_PATH
CLAIM_REPO_PATH = CLAIM_PATH.relative_to(ROOT).as_posix()

RECEIPT_KEYS = {
    "documentType", "schemaVersion", "receiptId", "recordedDate", "status",
    "evidenceClass", "result", "nextAction", "authorityBinding",
    "predecessorProgressBinding", "predecessorManifestBinding", "runnerBinding",
    "claim", "request", "verification", "archive", "executionBoundary",
    "crossFileHashBindings",
}
PROGRESS_KEYS = {
    "documentType", "schemaVersion", "progressId", "recordedDate", "status",
    "result", "nextAction", "supersedes", "decisionBinding", "provenanceBinding",
    "receiptBinding", "acquisitionSummary", "executionBoundary",
    "crossFileHashBindings",
}
MANIFEST_KEYS = {
    "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
    "result", "nextAction", "predecessorManifestBinding", "artifactScope",
    "orderingRule", "collectionDigestAlgorithm", "artifactCount", "artifacts",
    "collectionSha256", "sourceAcquisitionExecuted", "requestCount",
    "permitConsumed", "claimRetained", "archiveRetained", "archiveExtracted",
    "sourceReviewPerformed", "candidateSelected", "librarySelected",
    "externalIdentityProofRequired", "userActionRequired",
    "repositoryOwnerAuthenticationRequired",
    "rungThreeOfflineReviewDecisionPreparationAllowed",
    "rungThreeOfflineReviewExecutionAllowed",
}
CANONICAL_SYNC_MANIFEST_KEYS = {
    "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
    "result", "nextAction", "predecessorManifestBinding", "artifactScope",
    "orderingRule", "collectionDigestAlgorithm", "artifactCount", "artifacts",
    "collectionSha256", "sourceAcquisitionExecuted", "requestCount",
    "permitConsumed", "archiveRetained", "archiveExtracted",
    "sourceReviewPerformed", "candidateSelected", "librarySelected",
    "externalIdentityProofRequired", "userActionRequired",
    "repositoryOwnerAuthenticationRequired",
    "rungThreeOfflineReviewDecisionPreparationAllowed",
    "rungThreeOfflineReviewExecutionAllowed",
}


def require_exact_map(
    actual: Any,
    expected: Mapping[str, Any],
    path: str,
) -> dict[str, Any]:
    value = BASE.require_exact_keys(actual, set(expected), path)
    for key, expected_value in expected.items():
        BASE.require_equal(value[key], expected_value, f"{path}.{key}")
    return value


def validate_receipt_document(document: dict[str, Any], *, semantic: bool = True) -> None:
    BASE.require_exact_keys(document, RECEIPT_KEYS, "receipt")
    if semantic:
        BASE.require_semantic_hash(
            document, EXPECTED_SEMANTIC_SHA256[RECEIPT_PATH], "receipt"
        )
    require_exact_map(
        {key: document[key] for key in (
            "documentType", "schemaVersion", "receiptId", "recordedDate", "status",
            "evidenceClass", "result", "nextAction",
        )},
        {
            "documentType": "aetherlink.g2-rung2-source-acquisition-receipt",
            "schemaVersion": "1.0",
            "receiptId": "g2-pion-ice-v4.3.0-source-acquisition-receipt-v1",
            "recordedDate": "2026-07-23",
            "status": "acquisition_succeeded_archive_retained_not_extracted",
            "evidenceClass": "local_bounded_acquisition_receipt_not_external_attestation",
            "result": "exact_archive_acquired_verified_and_retained",
            "nextAction": "record_progress_v2_and_manifest_v3_then_prepare_rung3_offline_review_decision",
        },
        "receipt.identity",
    )
    require_exact_map(
        document["authorityBinding"],
        {
            "decisionPath": BASE.DECISION_PATH.relative_to(ROOT).as_posix(),
            "decisionSha256": BASE.EXPECTED_RAW_SHA256[BASE.DECISION_PATH],
            "provenancePath": BASE.PROVENANCE_PATH.relative_to(ROOT).as_posix(),
            "provenanceSha256": BASE.EXPECTED_RAW_SHA256[BASE.PROVENANCE_PATH],
            "maximumRequestCount": 1,
            "automaticRetryAllowed": False,
        },
        "receipt.authorityBinding",
    )
    require_exact_map(
        document["predecessorProgressBinding"],
        {
            "path": BASE.PROGRESS_PATH.relative_to(ROOT).as_posix(),
            "progressId": "g2-pion-ice-v4.3.0-source-acquisition-progress-v1",
            "sha256": BASE.EXPECTED_RAW_SHA256[BASE.PROGRESS_PATH],
            "requiredStatus": "authorized_not_consumed",
        },
        "receipt.predecessorProgressBinding",
    )
    require_exact_map(
        document["predecessorManifestBinding"],
        {
            "path": BASE.EVIDENCE_MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "sha256": BASE.EXPECTED_RAW_SHA256[BASE.EVIDENCE_MANIFEST_PATH],
            "collectionSha256": BASE.RUNG_TWO_COLLECTION_SHA256,
        },
        "receipt.predecessorManifestBinding",
    )
    require_exact_map(
        document["runnerBinding"],
        {
            "path": RUNNER_PATH.relative_to(ROOT).as_posix(),
            "sha256": EXPECTED_RAW_SHA256[RUNNER_PATH],
            "testPath": RUNNER_TEST_PATH.relative_to(ROOT).as_posix(),
            "testSha256": EXPECTED_RAW_SHA256[RUNNER_TEST_PATH],
            "offlineTestCount": 16,
            "offlineTestsPassed": True,
            "preExecutionIndependentSolAuditCount": 2,
            "preExecutionP0P2BlockerCount": 0,
        },
        "receipt.runnerBinding",
    )
    require_exact_map(
        document["claim"],
        {
            "path": CLAIM_REPO_PATH,
            "createdAt": "2026-07-22T23:01:11.013Z",
            "bytes": 280,
            "mode": "0600",
            "linkCount": 1,
            "ownerUidMatchesCurrentUser": True,
            "sha256": EXPECTED_RAW_SHA256[CLAIM_PATH],
            "retained": True,
            "blocksAutomaticRetry": True,
        },
        "receipt.claim",
    )
    request = require_exact_map(
        document["request"],
        {
            "requestCount": 1,
            "method": "GET",
            "url": SOURCE_URL,
            "finalUrl": SOURCE_URL,
            "startedAt": "2026-07-22T23:01:11.016Z",
            "completedAt": "2026-07-22T23:01:11.411Z",
            "elapsedMilliseconds": 395,
            "totalElapsedMilliseconds": 407,
            "httpStatus": 200,
            "redirectCount": 0,
            "ambientProxyUsed": False,
            "credentialsUsed": False,
            "observedContentLengthBytes": 293023,
            "receivedBytes": 293023,
            "observedEtag": f'"{BASE.RAW_ARCHIVE_SHA256}"',
        },
        "receipt.request",
    )
    BASE.require_exact_source_url(request["url"], "receipt.request.url")
    verification = require_exact_map(
        document["verification"],
        {
            "rawSha256": BASE.RAW_ARCHIVE_SHA256,
            "rawSha256Matches": True,
            "rawSha256TrustRole": "decision_pinned_reproducibility_check_not_independent_upstream_authentication",
            "moduleH1": BASE.MODULE_H1,
            "moduleH1Matches": True,
            "goModH1": BASE.GO_MOD_H1,
            "goModH1Matches": True,
            "sumdbSignatureVerifiedByBoundPreflight": True,
            "sumdbInclusionProofVerifiedByBoundPreflight": True,
            "zipStructureAndCrcVerified": True,
            "independentRetainedByteReadbackPassed": True,
            "allRequiredChecksPassed": True,
        },
        "receipt.verification",
    )
    BASE.require_hex(verification["rawSha256"], 64, "receipt.verification.rawSha256")
    require_exact_map(
        document["archive"],
        {
            "path": OUTPUT_PATH,
            "bytes": 293023,
            "mode": "0600",
            "linkCount": 1,
            "ownerUidMatchesCurrentUser": True,
            "entryCount": 129,
            "fileCount": 129,
            "moduleHashEntryCount": 129,
            "centralDirectoryBytes": 12345,
            "totalUncompressedBytes": 1131286,
            "goModBytes": 794,
            "retained": True,
            "filesystemExtracted": False,
            "sourceReviewPerformed": False,
            "publishedWithoutReplacement": True,
            "directoryFsyncCompleted": True,
            "ignoredBuildArtifact": True,
        },
        "receipt.archive",
    )
    boundary = BASE.require_exact_keys(
        document["executionBoundary"],
        {
            "permitConsumed", "additionalSourceAcquisitionAllowed",
            "automaticRetryAllowed", "candidateSelected", "librarySelected",
            "archiveExtracted", "sourceExecuted", "dependencyInstallationAllowed",
            "compilerInvocationAllowed", "codeLoadingAllowed", "socketCreationAllowed",
            "runtimeNetworkIoAllowed", "deviceExecutionAllowed",
            "productionDeploymentAllowed", "gitOperationAllowed",
            "externalIdentityProofRequired", "userActionRequired",
            "repositoryOwnerAuthenticationRequired", "productEndpointAuthenticationRequired",
            "rungThreeOfflineReviewDecisionPreparationAllowed",
            "rungThreeOfflineReviewExecutionAllowed",
        },
        "receipt.executionBoundary",
    )
    true_keys = {
        "permitConsumed", "productEndpointAuthenticationRequired",
        "rungThreeOfflineReviewDecisionPreparationAllowed",
    }
    for key in boundary:
        BASE.require_equal(boundary[key], key in true_keys, f"receipt.executionBoundary.{key}")
    require_exact_map(
        document["crossFileHashBindings"],
        {
            "progressPath": PROGRESS_PATH.relative_to(ROOT).as_posix(),
            "progressId": "g2-pion-ice-v4.3.0-source-acquisition-progress-v2",
            "manifestPath": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "status": "forward_identity_only_no_cyclic_hash_claim",
        },
        "receipt.crossFileHashBindings",
    )


def validate_progress_document(document: dict[str, Any], *, semantic: bool = True) -> None:
    BASE.require_exact_keys(document, PROGRESS_KEYS, "progressV2")
    if semantic:
        BASE.require_semantic_hash(
            document, EXPECTED_SEMANTIC_SHA256[PROGRESS_PATH], "progressV2"
        )
    identity = {
        "documentType": "aetherlink.g2-rung2-source-acquisition-progress",
        "schemaVersion": "1.0",
        "progressId": "g2-pion-ice-v4.3.0-source-acquisition-progress-v2",
        "recordedDate": "2026-07-23",
        "status": "acquisition_complete_archive_retained_not_extracted",
        "result": "exact_archive_acquired_verified_rung3_decision_preparation_only",
        "nextAction": "prepare_versioned_rung3_offline_source_review_decision",
    }
    require_exact_map(
        {key: document[key] for key in identity}, identity, "progressV2.identity"
    )
    require_exact_map(
        document["supersedes"],
        {
            "path": BASE.PROGRESS_PATH.relative_to(ROOT).as_posix(),
            "progressId": "g2-pion-ice-v4.3.0-source-acquisition-progress-v1",
            "sha256": BASE.EXPECTED_RAW_SHA256[BASE.PROGRESS_PATH],
            "status": "authorized_not_consumed",
        },
        "progressV2.supersedes",
    )
    require_exact_map(
        document["decisionBinding"],
        {
            "path": BASE.DECISION_PATH.relative_to(ROOT).as_posix(),
            "sha256": BASE.EXPECTED_RAW_SHA256[BASE.DECISION_PATH],
            "status": "bound_and_consumed",
        },
        "progressV2.decisionBinding",
    )
    require_exact_map(
        document["provenanceBinding"],
        {
            "path": BASE.PROVENANCE_PATH.relative_to(ROOT).as_posix(),
            "sha256": BASE.EXPECTED_RAW_SHA256[BASE.PROVENANCE_PATH],
            "status": "bound",
        },
        "progressV2.provenanceBinding",
    )
    require_exact_map(
        document["receiptBinding"],
        {
            "path": RECEIPT_PATH.relative_to(ROOT).as_posix(),
            "receiptId": "g2-pion-ice-v4.3.0-source-acquisition-receipt-v1",
            "sha256": RECEIPT_SHA256,
            "requiredStatus": "acquisition_succeeded_archive_retained_not_extracted",
        },
        "progressV2.receiptBinding",
    )
    require_exact_map(
        document["acquisitionSummary"],
        {
            "maximumRequestCount": 1,
            "requestCount": 1,
            "permitConsumed": True,
            "claimRetained": True,
            "archiveRetained": True,
            "archiveBytes": 293023,
            "archiveRawSha256": BASE.RAW_ARCHIVE_SHA256,
            "archiveExtracted": False,
            "fileCount": 129,
            "moduleH1": BASE.MODULE_H1,
            "goModH1": BASE.GO_MOD_H1,
            "allRequiredChecksPassed": True,
        },
        "progressV2.acquisitionSummary",
    )
    boundary = BASE.require_exact_keys(
        document["executionBoundary"],
        {
            "additionalSourceAcquisitionAllowed", "automaticRetryAllowed",
            "candidateSelected", "librarySelected", "sourceReviewPerformed",
            "archiveExtractionAllowed", "sourceExecutionAllowed",
            "dependencyInstallationAllowed", "compilerInvocationAllowed",
            "codeLoadingAllowed", "productRuntimeSocketCreationAllowed",
            "runtimeNetworkIoAllowed", "deviceExecutionAllowed",
            "productionDeploymentAllowed", "gitOperationAllowed",
            "externalIdentityProofRequired", "userActionRequired",
            "repositoryOwnerAuthenticationRequired", "productEndpointAuthenticationRequired",
            "rungThreeOfflineReviewDecisionPreparationAllowed",
            "rungThreeOfflineReviewExecutionAllowed",
        },
        "progressV2.executionBoundary",
    )
    true_keys = {
        "productEndpointAuthenticationRequired",
        "rungThreeOfflineReviewDecisionPreparationAllowed",
    }
    for key in boundary:
        BASE.require_equal(boundary[key], key in true_keys, f"progressV2.executionBoundary.{key}")
    require_exact_map(
        document["crossFileHashBindings"],
        {
            "manifestPath": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "manifestId": "g2-pion-ice-v4.3.0-rung2-acquisition-evidence-manifest-v3",
            "prospectiveRungThreeDecisionPath": "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-decision-v1.json",
            "prospectiveRungThreeDecisionId": "g2-pion-ice-v4.3.0-offline-source-review-decision-v1",
            "status": "forward_identity_only_no_cyclic_hash_claim",
        },
        "progressV2.crossFileHashBindings",
    )


EXPECTED_MANIFEST_ROWS = (
    (
        "G2R2E007",
        RUNNER_PATH.relative_to(ROOT).as_posix(),
        EXPECTED_RAW_SHA256[RUNNER_PATH],
        "exact_one_use_fail_closed_acquisition_runner",
    ),
    (
        "G2R2E008",
        CLAIM_REPO_PATH,
        EXPECTED_RAW_SHA256[CLAIM_PATH],
        "retained_one_use_permit_consumption_claim",
    ),
    (
        "G2R2E009",
        OUTPUT_PATH,
        EXPECTED_RAW_SHA256[ARCHIVE_PATH],
        "retained_verified_upstream_module_archive_not_extracted",
    ),
    (
        "G2R2E010",
        RECEIPT_PATH.relative_to(ROOT).as_posix(),
        EXPECTED_RAW_SHA256[RECEIPT_PATH],
        "bounded_acquisition_and_independent_byte_readback_receipt",
    ),
    (
        "G2R2E011",
        PROGRESS_PATH.relative_to(ROOT).as_posix(),
        EXPECTED_RAW_SHA256[PROGRESS_PATH],
        "consumed_permit_current_progress_and_rung_three_preparation_boundary",
    ),
)


def validate_manifest_document(document: dict[str, Any], *, semantic: bool = True) -> None:
    BASE.require_exact_keys(document, MANIFEST_KEYS, "manifestV3")
    if semantic:
        BASE.require_semantic_hash(
            document, EXPECTED_SEMANTIC_SHA256[MANIFEST_PATH], "manifestV3"
        )
    identity = {
        "documentType": "aetherlink.g2-pion-rung2-source-acquisition-evidence-manifest",
        "schemaVersion": "1.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung2-acquisition-evidence-manifest-v3",
        "recordedDate": "2026-07-23",
        "status": "rung2_acquisition_evidence_complete_rung3_decision_not_recorded",
        "result": "exact_archive_acquired_verified_and_retained",
        "nextAction": "prepare_versioned_rung3_offline_source_review_decision",
        "artifactScope": "post_v2_delta_only",
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_path_newline",
        "artifactCount": 5,
        "collectionSha256": MANIFEST_COLLECTION_SHA256,
        "sourceAcquisitionExecuted": True,
        "requestCount": 1,
        "permitConsumed": True,
        "claimRetained": True,
        "archiveRetained": True,
        "archiveExtracted": False,
        "sourceReviewPerformed": False,
        "candidateSelected": False,
        "librarySelected": False,
        "externalIdentityProofRequired": False,
        "userActionRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "rungThreeOfflineReviewDecisionPreparationAllowed": True,
        "rungThreeOfflineReviewExecutionAllowed": False,
    }
    require_exact_map(
        {key: document[key] for key in identity}, identity, "manifestV3.identity"
    )
    require_exact_map(
        document["predecessorManifestBinding"],
        {
            "path": BASE.EVIDENCE_MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "sha256": BASE.EXPECTED_RAW_SHA256[BASE.EVIDENCE_MANIFEST_PATH],
            "collectionSha256": BASE.RUNG_TWO_COLLECTION_SHA256,
        },
        "manifestV3.predecessorManifestBinding",
    )
    artifacts = BASE.require_list(document["artifacts"], "manifestV3.artifacts")
    if len(artifacts) != len(EXPECTED_MANIFEST_ROWS):
        BASE.fail("manifestV3 must contain exactly five delta artifacts")
    digest_rows: list[tuple[str, str, str]] = []
    for index, (artifact, expected) in enumerate(zip(artifacts, EXPECTED_MANIFEST_ROWS)):
        evidence_id, path, sha256_value, role = expected
        require_exact_map(
            artifact,
            {
                "evidenceId": evidence_id,
                "path": path,
                "sha256": sha256_value,
                "role": role,
            },
            f"manifestV3.artifacts[{index}]",
        )
        BASE.require_safe_repo_relative_path(path, f"manifestV3.artifacts[{index}].path")
        BASE.require_hex(sha256_value, 64, f"manifestV3.artifacts[{index}].sha256")
        digest_rows.append((evidence_id, path, sha256_value))
    if BASE.manifest_collection_digest(digest_rows) != MANIFEST_COLLECTION_SHA256:
        BASE.fail("manifestV3 collection digest does not match its exact delta rows")


CANONICAL_SYNC_COLLECTION_SHA256 = (
    "a2f2ab09307a5b1408d65699b3746782f8e6de6ece8e98891241dc350bc4cae3"
)
EXPECTED_CANONICAL_SYNC_ROWS = (
    (
        "G2R2E012",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/canonical-document-supersession-v1.json",
        "51b1eb43a6b57441ddcb307d37db86420cea9932ea89e316c50730215bf4d816",
        "historical_git_snapshot_to_living_canonical_document_supersession",
    ),
    (
        "G2R2E013", "docs/roadmap.md",
        "b4a78169161f9a72788cc5c4dc7e55fe53ac720ec65095e9fe4562ce5c47d45d",
        "synchronized_current_canonical_v1_delivery_roadmap",
    ),
    (
        "G2R2E014", "docs/handoff.md",
        "e4b659e737402e359ec3e99d1a7b871176cdb1ea53ec986da5f9884089858987",
        "synchronized_current_canonical_session_handoff",
    ),
    (
        "G2R2E015", "README.md",
        "0c760bc7409629e70e9ddc170f295640c15738ad41ce76d6cb4c85a23194d0ae",
        "synchronized_root_project_status",
    ),
    (
        "G2R2E016", "shared/protocol/README.md",
        "319771b5614e71125809202c5625ade90416e19f29ca2dd5da7237bed8df24a0",
        "synchronized_shared_protocol_status",
    ),
    (
        "G2R2E017", "docs/progress.md",
        "d4f6885a898ad4468348999bed169837530663e87d94bd1b413aec21b1730cb1",
        "synchronized_current_progress_status",
    ),
    (
        "G2R2E018", "docs/qa-evidence.md",
        "f2458587f32fa3d93862dd84501544046bc4859291225fbf4eda8a07200a8880",
        "synchronized_current_qa_checklist",
    ),
)


def validate_canonical_sync_manifest_document(
    document: dict[str, Any], *, semantic: bool = True,
    verify_superseded_artifact_files: bool = False,
) -> None:
    BASE.require_exact_keys(
        document, CANONICAL_SYNC_MANIFEST_KEYS, "canonicalSyncManifestV4"
    )
    if semantic:
        BASE.require_semantic_hash(
            document,
            EXPECTED_SEMANTIC_SHA256[CANONICAL_SYNC_MANIFEST_PATH],
            "canonicalSyncManifestV4",
        )
    identity = {
        "documentType": "aetherlink.g2-pion-rung2-canonical-document-sync-evidence-manifest",
        "schemaVersion": "1.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung2-canonical-document-sync-evidence-manifest-v4",
        "recordedDate": "2026-07-23",
        "status": "rung2_acquisition_complete_canonical_docs_synchronized",
        "result": "historical_rung1_bytes_preserved_and_living_docs_advanced_to_receipt_state",
        "nextAction": "prepare_versioned_rung3_offline_source_review_decision",
        "artifactScope": "post_v3_canonical_document_sync_delta_only",
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_path_newline",
        "artifactCount": 7,
        "collectionSha256": CANONICAL_SYNC_COLLECTION_SHA256,
        "sourceAcquisitionExecuted": True,
        "requestCount": 1,
        "permitConsumed": True,
        "archiveRetained": True,
        "archiveExtracted": False,
        "sourceReviewPerformed": False,
        "candidateSelected": False,
        "librarySelected": False,
        "externalIdentityProofRequired": False,
        "userActionRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "rungThreeOfflineReviewDecisionPreparationAllowed": True,
        "rungThreeOfflineReviewExecutionAllowed": False,
    }
    require_exact_map(
        {key: document[key] for key in identity},
        identity,
        "canonicalSyncManifestV4.identity",
    )
    require_exact_map(
        document["predecessorManifestBinding"],
        {
            "path": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "sha256": EXPECTED_RAW_SHA256[MANIFEST_PATH],
            "collectionSha256": MANIFEST_COLLECTION_SHA256,
        },
        "canonicalSyncManifestV4.predecessorManifestBinding",
    )
    artifacts = BASE.require_list(
        document["artifacts"], "canonicalSyncManifestV4.artifacts"
    )
    if len(artifacts) != len(EXPECTED_CANONICAL_SYNC_ROWS):
        BASE.fail("canonicalSyncManifestV4 must contain exactly seven delta artifacts")
    digest_rows: list[tuple[str, str, str]] = []
    for index, (artifact, expected) in enumerate(
        zip(artifacts, EXPECTED_CANONICAL_SYNC_ROWS)
    ):
        evidence_id, path, sha256_value, role = expected
        require_exact_map(
            artifact,
            {
                "evidenceId": evidence_id,
                "path": path,
                "sha256": sha256_value,
                "role": role,
            },
            f"canonicalSyncManifestV4.artifacts[{index}]",
        )
        BASE.require_safe_repo_relative_path(
            path, f"canonicalSyncManifestV4.artifacts[{index}].path"
        )
        if verify_superseded_artifact_files:
            BASE.verify_file_shape_and_hash(ROOT / path, sha256_value)
        digest_rows.append((evidence_id, path, sha256_value))
    if BASE.manifest_collection_digest(digest_rows) != CANONICAL_SYNC_COLLECTION_SHA256:
        BASE.fail("canonicalSyncManifestV4 collection digest does not match its rows")


CANONICAL_SEMANTIC_SYNC_COLLECTION_SHA256 = (
    "adb1fbce766b0750e186285024156abea290d80763eea142420192aa8261d0a8"
)
EXPECTED_CANONICAL_SEMANTIC_SYNC_ROWS = (
    (
        "G2R2E019",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/canonical-document-supersession-v2.json",
        "3a2b74ecde45b69204b9687904a4f88d731dfc532046e472ec22a4873765309a",
        "semantic_current_step_canonical_document_supersession",
    ),
    (
        "G2R2E020", "docs/roadmap.md",
        "067fe008fb7be9c73883cf50bd9f9d44764025fb8197e18fbe46d79bf1ef110e",
        "semantically_unambiguous_current_canonical_v1_delivery_roadmap",
    ),
    (
        "G2R2E021", "docs/progress.md",
        "10d878b77bdfee4ebd0d0a104bdb3aa7ae80bfaf2130b293852b4fb04c50c1c4",
        "semantically_unambiguous_current_progress_status",
    ),
    (
        "G2R2E022", "docs/qa-evidence.md",
        "fe7b7535c3aa4d27b1e079d3be4fcfa5a13f1dba32c9a528b739a082fa348832",
        "semantically_unambiguous_current_qa_checklist",
    ),
    (
        "G2R2E023", "docs/handoff.md",
        "8117a2eea69f9fc2241145fec833700da1076f3e387b3b8a8a09ab725c207ae8",
        "semantically_unambiguous_current_session_handoff",
    ),
    (
        "G2R2E024", "README.md",
        "aca5762ff01056401e8e6824d96a548c589493a9dd28d7d4c07524913b41fdfc",
        "semantically_unambiguous_current_root_project_status",
    ),
    (
        "G2R2E025", "shared/protocol/README.md",
        "50e6337bf9685a3b3e064f954a7bb25dc129a19cf79a7ec536d990c60c73df40",
        "semantically_unambiguous_current_shared_protocol_status",
    ),
)


def validate_canonical_semantic_sync_manifest_document(
    document: dict[str, Any], *, semantic: bool = True,
    verify_superseded_artifact_files: bool = False,
) -> None:
    label = "canonicalSyncManifestV5"
    BASE.require_exact_keys(document, CANONICAL_SYNC_MANIFEST_KEYS, label)
    if semantic:
        BASE.require_semantic_hash(
            document,
            EXPECTED_SEMANTIC_SHA256[CANONICAL_SEMANTIC_SYNC_MANIFEST_PATH],
            label,
        )
    identity = {
        "documentType": "aetherlink.g2-pion-rung2-canonical-document-sync-evidence-manifest",
        "schemaVersion": "1.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung2-canonical-document-sync-evidence-manifest-v5",
        "recordedDate": "2026-07-23",
        "status": "rung2_acquisition_complete_canonical_docs_semantically_unambiguous",
        "result": "historical_current_wording_scoped_to_at_that_checkpoint_and_current_next_action_fixed_to_rung3_preparation",
        "nextAction": "prepare_versioned_rung3_offline_source_review_decision",
        "artifactScope": "post_v4_canonical_semantic_correction_delta_only",
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_path_newline",
        "artifactCount": 7,
        "collectionSha256": CANONICAL_SEMANTIC_SYNC_COLLECTION_SHA256,
        "sourceAcquisitionExecuted": True,
        "requestCount": 1,
        "permitConsumed": True,
        "archiveRetained": True,
        "archiveExtracted": False,
        "sourceReviewPerformed": False,
        "candidateSelected": False,
        "librarySelected": False,
        "externalIdentityProofRequired": False,
        "userActionRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "rungThreeOfflineReviewDecisionPreparationAllowed": True,
        "rungThreeOfflineReviewExecutionAllowed": False,
    }
    require_exact_map(
        {key: document[key] for key in identity}, identity, f"{label}.identity"
    )
    require_exact_map(
        document["predecessorManifestBinding"],
        {
            "path": CANONICAL_SYNC_MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "sha256": EXPECTED_RAW_SHA256[CANONICAL_SYNC_MANIFEST_PATH],
            "collectionSha256": CANONICAL_SYNC_COLLECTION_SHA256,
        },
        f"{label}.predecessorManifestBinding",
    )
    artifacts = BASE.require_list(document["artifacts"], f"{label}.artifacts")
    if len(artifacts) != len(EXPECTED_CANONICAL_SEMANTIC_SYNC_ROWS):
        BASE.fail(f"{label} must contain exactly seven delta artifacts")
    digest_rows: list[tuple[str, str, str]] = []
    for index, (artifact, expected) in enumerate(
        zip(artifacts, EXPECTED_CANONICAL_SEMANTIC_SYNC_ROWS)
    ):
        evidence_id, path, sha256_value, role = expected
        require_exact_map(
            artifact,
            {
                "evidenceId": evidence_id,
                "path": path,
                "sha256": sha256_value,
                "role": role,
            },
            f"{label}.artifacts[{index}]",
        )
        BASE.require_safe_repo_relative_path(path, f"{label}.artifacts[{index}].path")
        if verify_superseded_artifact_files:
            BASE.verify_file_shape_and_hash(ROOT / path, sha256_value)
        digest_rows.append((evidence_id, path, sha256_value))
    if BASE.manifest_collection_digest(digest_rows) != CANONICAL_SEMANTIC_SYNC_COLLECTION_SHA256:
        BASE.fail(f"{label} collection digest does not match its rows")


def verify_retained_files() -> None:
    for path, expected_hash in EXPECTED_RAW_SHA256.items():
        BASE.verify_file_shape_and_hash(path, expected_hash)

    for path, expected_size in ((CLAIM_PATH, 280), (ARCHIVE_PATH, 293023)):
        descriptor = BASE.secure_repo_file_descriptor(path)
        try:
            metadata = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size != expected_size
        ):
            BASE.fail(
                f"{path.relative_to(ROOT)} must remain owner-only 0600, single-link, "
                f"and exactly {expected_size} bytes"
            )

    claim = BASE.parse_json(BASE.secure_read_bytes(CLAIM_PATH).decode("utf-8"))
    require_exact_map(
        claim,
        {
            "claimType": "aetherlink.g2-pion-source-acquisition-one-use-claim",
            "createdAt": "2026-07-22T23:01:11.013Z",
            "decisionSha256": BASE.EXPECTED_RAW_SHA256[BASE.DECISION_PATH],
            "rule": "claim_persists_after_any_network_attempt_and_blocks_retry",
            "schemaVersion": "1.0",
        },
        "retainedClaim",
    )
    archive_evidence = RUNNER.inspect_module_zip(BASE.secure_read_bytes(ARCHIVE_PATH))
    expected_archive_evidence = {
        "entryCount": 129,
        "fileCount": 129,
        "moduleHashEntryCount": 129,
        "centralDirectoryBytes": 12345,
        "totalUncompressedBytes": 1131286,
        "moduleH1": BASE.MODULE_H1,
        "goModH1": BASE.GO_MOD_H1,
        "goModBytes": 794,
        "archiveExtracted": False,
    }
    require_exact_map(archive_evidence, expected_archive_evidence, "retainedArchive")


def validate_repository() -> None:
    BASE.validate_repository()
    verify_retained_files()
    receipt = BASE.load_json(RECEIPT_PATH)
    progress = BASE.load_json(PROGRESS_PATH)
    manifest = BASE.load_json(MANIFEST_PATH)
    canonical_sync_manifest = BASE.load_json(CANONICAL_SYNC_MANIFEST_PATH)
    canonical_semantic_sync_manifest = BASE.load_json(
        CANONICAL_SEMANTIC_SYNC_MANIFEST_PATH
    )
    for path, document in (
        (RECEIPT_PATH, receipt),
        (PROGRESS_PATH, progress),
        (MANIFEST_PATH, manifest),
        (CANONICAL_SYNC_MANIFEST_PATH, canonical_sync_manifest),
        (CANONICAL_SEMANTIC_SYNC_MANIFEST_PATH, canonical_semantic_sync_manifest),
    ):
        BASE.verify_pretty_json_bytes(path, document)
    validate_receipt_document(receipt)
    validate_progress_document(progress)
    validate_manifest_document(manifest)
    validate_canonical_sync_manifest_document(canonical_sync_manifest)
    validate_canonical_semantic_sync_manifest_document(
        canonical_semantic_sync_manifest,
        verify_superseded_artifact_files=False,
    )
    if progress["receiptBinding"]["sha256"] != BASE.raw_sha256(RECEIPT_PATH):
        BASE.fail("progressV2 receipt byte binding drifted")
    if receipt["archive"]["path"] != manifest["artifacts"][2]["path"]:
        BASE.fail("receipt/manifest retained archive path drifted")
    if receipt["verification"]["rawSha256"] != manifest["artifacts"][2]["sha256"]:
        BASE.fail("receipt/manifest retained archive hash drifted")
    if progress["acquisitionSummary"]["archiveRawSha256"] != BASE.RAW_ARCHIVE_SHA256:
        BASE.fail("progressV2 retained archive hash drifted")


def print_hashes() -> None:
    for path in EXPECTED_RAW_SHA256:
        print(f"{path.relative_to(ROOT).as_posix()}\t{BASE.raw_sha256(path)}")
        if path.suffix == ".json":
            print(
                f"{path.relative_to(ROOT).as_posix()}#semantic\t"
                f"{BASE.semantic_sha256(BASE.load_json(path))}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-hashes", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.print_hashes:
            print_hashes()
            return 0
        validate_repository()
    except (ReceiptValidationError, RUNNER.AcquisitionError) as error:
        print(f"G2 Pion rung-two receipt validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "G2 Pion historical rung-two acquisition receipt passed: exactly one request "
        "was consumed; retained bytes, claim, raw SHA-256, module h1, and go.mod h1 "
        "match; archive remains unextracted; historical canonical-document manifests "
        "are verified while the current successor is checked by the rung-three "
        "validator; no user or owner authentication required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
