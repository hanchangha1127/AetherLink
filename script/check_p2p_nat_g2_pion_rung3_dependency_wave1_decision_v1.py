#!/usr/bin/env python3
"""Validate the G2 Pion dependency wave-one preparation decision.

This checker is intentionally read-only. It validates a preparation-only source
identity and request contract. It performs no network I/O, source acquisition,
archive extraction, package-manager invocation, compilation, or execution.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Callable
import zipfile


ROOT = Path(__file__).resolve().parents[1]

BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1"
)
RUNG_TWO = f"{BASE}/rung-two"
RUNG_THREE = f"{BASE}/rung-three"
DECISION_PATH = (
    f"{RUNG_THREE}/"
    "bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
READER_PATH = (
    f"{RUNG_THREE}/"
    "bounded-dependency-source-identity-and-acquisition-decision-v1.md"
)
PREDECESSOR_PATH = (
    f"{RUNG_THREE}/implementation-or-dependency-review-decision-v1.json"
)
PREDECESSOR_CHECKER_PATH = (
    "script/"
    "check_p2p_nat_g2_pion_rung3_implementation_dependency_review_decision_v1.py"
)
PREDECESSOR_TESTS_PATH = (
    "script/"
    "test_p2p_nat_g2_pion_rung3_implementation_dependency_review_decision_v1.py"
)
PLAN_PATH = (
    f"{RUNG_THREE}/implementation-or-dependency-review-decision-v1/"
    "implementation/staged-fixed-point-source-closure.md"
)
PROFILE_PATH = f"{BASE}/restricted-fork-profile.json"
PROVENANCE_PATH = f"{RUNG_TWO}/provenance-observation-v1.json"
RUNG_TWO_DECISION_PATH = f"{RUNG_TWO}/source-acquisition-decision-v1.json"
RUNG_TWO_RECEIPT_PATH = f"{RUNG_TWO}/source-acquisition-receipt-v1.json"
OFFLINE_RESULT_PATH = f"{RUNG_THREE}/offline-source-review-result-v3.json"
CLASSIFICATIONS_PATH = (
    f"{RUNG_THREE}/semantic-source-review-classifications-v1.json"
)
SEMANTIC_RESULT_PATH = f"{RUNG_THREE}/semantic-source-review-result-v1.json"
SEMANTIC_MANIFEST_PATH = f"{RUNG_THREE}/semantic-source-review-manifest-v1.json"
PATCH_DECISION_PATH = (
    f"{RUNG_THREE}/patch-and-dependency-closure-decision-v1.json"
)
SOURCE_ARCHIVE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
SOURCE_MODULE_PREFIX = "github.com/pion/ice/v4@v4.3.0/"
WAVE_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v1.claim"
)
WAVE_STAGING_PARENT_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies"
)
WAVE_STAGING_NAME_PREFIX = ".wave-1-v1-staging-"
WAVE_FINAL_DIRECTORY_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1/accepted"
)
WAVE_SUCCESS_RECEIPT_PATH = (
    f"{RUNG_THREE}/"
    "bounded-dependency-source-acquisition-wave1-receipt-v1.json"
)
WAVE_FAILURE_RECEIPT_PATH = (
    f"{RUNG_THREE}/"
    "bounded-dependency-source-acquisition-wave1-failure-v1.json"
)
WAVE_MANIFEST_PATH = (
    f"{RUNG_THREE}/"
    "bounded-dependency-source-acquisition-wave1-manifest-v1.json"
)

EXPECTED_RAW = {
    PREDECESSOR_PATH: (
        "6a14603c02c9aa9d9d78377b1c38a9f0d47391c0ac1ff8eea1769198ddc13ff8"
    ),
    PREDECESSOR_CHECKER_PATH: (
        "ee96b53eac90dd65d53ac9b7484a65b07d1749cc585559764e3aa9f42251b1f9"
    ),
    PREDECESSOR_TESTS_PATH: (
        "558d53ab0f29c57815e6fa0f14e1743f942865a05e424a4bc8227be126187a5a"
    ),
    PLAN_PATH: (
        "22d7cfbc2db9e34fab641167d227e650cb490dcfd9a402a4dff86e1f967234bc"
    ),
    PROFILE_PATH: (
        "10e9436ae9b8f24c4447d12f8087b4f121810841ae33526e08fcc3d862d60a0f"
    ),
    PROVENANCE_PATH: (
        "6b0b55023849480c0a7ea05449b98cc2e27d9fd1d704c794aace9e04d0afe4f0"
    ),
    RUNG_TWO_DECISION_PATH: (
        "8a7ec91354b27ffc4cdf8dcce2f6baa93a10dfadfd7c896266ce42b1ae854c10"
    ),
    RUNG_TWO_RECEIPT_PATH: (
        "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6"
    ),
    OFFLINE_RESULT_PATH: (
        "ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933"
    ),
    CLASSIFICATIONS_PATH: (
        "e76e8c9fa0a78c8c5c4beae1ebfd4c4f8144b411689a3a8bd5f8804ebf61c8c9"
    ),
    SEMANTIC_RESULT_PATH: (
        "a01b3518f1354d438542ae77c06aa92d8f0936d516b4070d19c5bf27791e8a98"
    ),
    SEMANTIC_MANIFEST_PATH: (
        "300da97505b4715576d665846b23dd8363b36d416ed5d24ed4a7d4e77f098e6f"
    ),
    PATCH_DECISION_PATH: (
        "5ab3bfe60c617c58b88ae0885f2bdb6fba0c315c0478d6eacf526cdd935903ec"
    ),
    SOURCE_ARCHIVE_PATH: (
        "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
    ),
    READER_PATH: (
        "aed39c3614f0237656f43aafabf45f125939cfb888ab9a5b76c4bcb8f26ce850"
    ),
}

EXPECTED_CONTENT = {
    PREDECESSOR_PATH: (
        "359e8e51ba3568f7f66bec4222149ef8b28162f35f4868f3d4a78ae4f4b5c7a6"
    ),
    OFFLINE_RESULT_PATH: (
        "ceffb7b9856a5eca635f0f797d341796776a7221a124c97b85c65fc936b02d48"
    ),
    CLASSIFICATIONS_PATH: (
        "d7feed1bdd5a7a8ee0eead002c598157c01dafe2d429b7c1c012978d39a38886"
    ),
    SEMANTIC_RESULT_PATH: (
        "9a7eeae26ca7538b33f805f35ade421c528dd52745fd6c737fedb7c70acf6e97"
    ),
    SEMANTIC_MANIFEST_PATH: (
        "3812c15c57b93b7d35dde44b4cdb3d4abff4f696b517fb6e7e216dab0b45671e"
    ),
    PATCH_DECISION_PATH: (
        "b0bc1feb01546e3bcd261794f21b51d526de1b3d84fabc36d459699319a773ef"
    ),
}

EXPECTED_TOP_LEVEL_KEYS = {
    "documentType",
    "schemaVersion",
    "decisionId",
    "recordedDate",
    "status",
    "predecessorBinding",
    "evidenceBindings",
    "sourceSnapshot",
    "productionProfiles",
    "rootSeed",
    "sourceIdentityPolicy",
    "wave",
    "plannedAcquisitionContract",
    "resourceLimits",
    "filesystemContract",
    "receiptContract",
    "sequence",
    "authority",
    "execution",
    "closure",
    "nonClaims",
    "readerDocumentBinding",
    "result",
    "nextAction",
    "contentBinding",
}

EXPECTED_PREDECESSOR_BINDING = {
    "decisionPath": PREDECESSOR_PATH,
    "decisionRawSha256": EXPECTED_RAW[PREDECESSOR_PATH],
    "decisionContentSha256": EXPECTED_CONTENT[PREDECESSOR_PATH],
    "decisionCheckerPath": PREDECESSOR_CHECKER_PATH,
    "decisionCheckerRawSha256": EXPECTED_RAW[PREDECESSOR_CHECKER_PATH],
    "decisionCheckerTestsPath": PREDECESSOR_TESTS_PATH,
    "decisionCheckerTestsRawSha256": EXPECTED_RAW[PREDECESSOR_TESTS_PATH],
    "implementationPlanPath": PLAN_PATH,
    "implementationPlanRawSha256": EXPECTED_RAW[PLAN_PATH],
    "requiredStatus": "dependency_review_selected_acquisition_not_authorized",
    "requiredResult": (
        "staged_fixed_point_dependency_review_selected_all_19_findings_remain_open"
    ),
    "requiredNextAction": (
        "prepare_separate_versioned_bounded_dependency_source_identity_and_"
        "acquisition_decision"
    ),
}

EXPECTED_EVIDENCE_BINDINGS = {
    "restrictedForkProfile": {
        "path": PROFILE_PATH,
        "rawSha256": EXPECTED_RAW[PROFILE_PATH],
        "semanticSha256": (
            "9c929d186eedb10cc890d5540597724d6df1d719f174ed1965c79e4d50324be6"
        ),
    },
    "rungTwoProvenanceObservation": {
        "path": PROVENANCE_PATH,
        "rawSha256": EXPECTED_RAW[PROVENANCE_PATH],
    },
    "rungTwoSourceAcquisitionDecision": {
        "path": RUNG_TWO_DECISION_PATH,
        "rawSha256": EXPECTED_RAW[RUNG_TWO_DECISION_PATH],
    },
    "rungTwoSourceAcquisitionReceipt": {
        "path": RUNG_TWO_RECEIPT_PATH,
        "rawSha256": EXPECTED_RAW[RUNG_TWO_RECEIPT_PATH],
    },
    "offlineReviewResult": {
        "path": OFFLINE_RESULT_PATH,
        "rawSha256": EXPECTED_RAW[OFFLINE_RESULT_PATH],
        "contentSha256": EXPECTED_CONTENT[OFFLINE_RESULT_PATH],
    },
    "semanticClassifications": {
        "path": CLASSIFICATIONS_PATH,
        "rawSha256": EXPECTED_RAW[CLASSIFICATIONS_PATH],
        "contentSha256": EXPECTED_CONTENT[CLASSIFICATIONS_PATH],
    },
    "semanticResult": {
        "path": SEMANTIC_RESULT_PATH,
        "rawSha256": EXPECTED_RAW[SEMANTIC_RESULT_PATH],
        "contentSha256": EXPECTED_CONTENT[SEMANTIC_RESULT_PATH],
    },
    "semanticManifest": {
        "path": SEMANTIC_MANIFEST_PATH,
        "rawSha256": EXPECTED_RAW[SEMANTIC_MANIFEST_PATH],
        "contentSha256": EXPECTED_CONTENT[SEMANTIC_MANIFEST_PATH],
    },
    "patchDependencyDecision": {
        "path": PATCH_DECISION_PATH,
        "rawSha256": EXPECTED_RAW[PATCH_DECISION_PATH],
        "contentSha256": EXPECTED_CONTENT[PATCH_DECISION_PATH],
        "portfolioArtifactCount": 19,
        "portfolioByteSize": 186716,
        "portfolioBundleSha256": (
            "020fa0b627a85844d557323b5106e4179637fe3f14c578fec50e6a3e34e68f56"
        ),
    },
}

EXPECTED_SOURCE_SNAPSHOT = {
    "module": "github.com/pion/ice/v4",
    "version": "v4.3.0",
    "upstreamCommit": "1e8716372f2bb52e45bf2a7172e4fb1004251c46",
    "archivePath": SOURCE_ARCHIVE_PATH,
    "archiveRawSha256": EXPECTED_RAW[SOURCE_ARCHIVE_PATH],
    "archiveByteSize": 293023,
    "archiveEntryCount": 129,
    "archiveTotalUncompressedBytes": 1131286,
    "modulePrefix": SOURCE_MODULE_PREFIX,
    "sourceTreeSha256": (
        "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
    ),
    "goModRawSha256": (
        "5044428710b5a718aad517eed5c08e1933378efa3d9b4245853cfb312560aca4"
    ),
    "goSumRawSha256": (
        "b47d7d5f3bb8c8b85b3283585f97ea6bd0a8b97427b49068b9f5685ddd953887"
    ),
    "checkerVerification": (
        "stable_no_follow_descriptor_raw_zip_embedded_go_mod_go_sum_and_"
        "source_tree_recompute"
    ),
    "goVersion": "1.24.0",
    "rootRequirementCount": 19,
    "rootDirectRequirementCount": 10,
    "rootIndirectRequirementCount": 9,
    "goSumRecordCount": 44,
    "goSumModuleVersionTupleCount": 23,
    "goSumSourceHashCount": 21,
    "goSumGoModHashCount": 23,
    "checksumOnlyContextTupleCount": 4,
}

EXPECTED_PROFILES = {
    "goVersion": "1.24.0",
    "compilerConstraint": "gc",
    "graphProfileMode": "union_of_exact_android_and_macos_v1_profiles",
    "profiles": [
        {
            "profileId": "android_api_26_through_36_arm64_v8a",
            "goos": "android",
            "goarch": "arm64",
            "cgoEnabled": True,
            "minimumPlatformVersion": 26,
            "maximumPlatformVersion": 36,
            "explicitBuildTags": [],
            "implicitConstraintTags": [
                "android",
                "arm64",
                "unix",
                "cgo",
                "gc",
                "go1.24",
            ],
        },
        {
            "profileId": "macos_14_or_newer_arm64",
            "goos": "darwin",
            "goarch": "arm64",
            "cgoEnabled": True,
            "minimumPlatformVersion": 14,
            "maximumPlatformVersion": None,
            "explicitBuildTags": [],
            "implicitConstraintTags": [
                "darwin",
                "arm64",
                "unix",
                "cgo",
                "gc",
                "go1.24",
            ],
        },
    ],
    "excludedFromProductionReachability": [
        "test_files",
        "external_test_packages",
        "examples",
        "commands",
        "tools",
        "benchmarks",
        "fuzz_entry_points",
    ],
    "alwaysClassifySeparately": [
        "generated_source",
        "assembly",
        "cgo",
        "native_source",
        "vendored_source",
        "build_scripts",
    ],
    "rootDirectiveCounts": {
        "replace": 0,
        "exclude": 0,
        "retract": 0,
        "toolchain": 0,
        "vendor": 0,
        "workspace": 0,
    },
    "graphAlgorithm": {
        "name": "go1.24_mvs_profile_union_fixed_point_v1",
        "moduleMetadataParsing": (
            "strict_go1_24_module_require_replace_exclude_retract_toolchain_"
            "semantics"
        ),
        "packageSelection": (
            "all_non_test_packages_transitively_imported_from_the_root_module_"
            "under_either_frozen_profile"
        ),
        "moduleSelection": (
            "longest_canonical_module_path_prefix_then_minimum_version_selection"
        ),
        "profileCombination": "ordered_node_and_edge_union",
        "standardLibraryTreatment": (
            "excluded_from_module_nodes_but_import_edges_recorded"
        ),
        "unknownDirectiveRule": "fail_closed",
        "newTupleRule": "require_new_versioned_bounded_wave_decision",
        "fixedPointRule": (
            "zero_new_selected_tuples_and_two_independent_equal_node_edge_and_"
            "graph_digests"
        ),
    },
}

EXPECTED_IDENTITY_POLICY = {
    "retrievalService": "public_go_module_proxy",
    "retrievalHost": "proxy.golang.org",
    "identityKind": "go_module_zip_h1_and_embedded_go_mod_h1",
    "rootTrustChain": (
        "locally_verified_pion_sumdb_inclusion_to_exact_pion_zip_to_exact_"
        "embedded_root_go_sum_to_dependency_h1"
    ),
    "rootPionSumdbSignatureVerified": True,
    "rootPionSumdbInclusionProofVerified": True,
    "dependencyDirectSumdbInclusionProofVerified": False,
    "dependencyRepositoryOwnerAttestationClaimed": False,
    "dependencyRepositoryCommitIdentityClaimed": False,
    "proxyOriginAloneIsAcceptance": False,
    "goSumIsCompleteGraphEvidence": False,
    "goSumIsLicenseReceipt": False,
    "rawSha256Predeclared": False,
    "rawSha256RecordedAfterAcceptance": True,
    "rawSha256TrustRole": (
        "post_acquisition_reproducible_byte_identity_not_independent_upstream_"
        "authentication"
    ),
    "moduleZipH1MatchRequired": True,
    "embeddedGoModH1MatchRequired": True,
    "zipStructureAndPrefixValidationRequired": True,
}

EXPECTED_RESOURCE_LIMITS = {
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
    "maximumCompressionRatio": 200,
    "maximumPathBytes": 1024,
    "maximumPathComponents": 64,
    "maximumComponentBytes": 255,
    "maximumGraphNodes": 512,
    "maximumGraphEdges": 4096,
    "maximumJsonReceiptOrFailureBytes": 2097152,
}

EXPECTED_PLANNED_CONTRACT = {
    "status": "prepared_not_authorized",
    "mode": "single_exact_19_archive_wave",
    "atomicPermitClaimRequired": True,
    "existingClaimStagingOutputOrReceiptRule": "fail_closed_before_network_io",
    "sourceAcquisitionAllowed": False,
    "sourceAcquisitionNetworkIoAllowed": False,
    "maximumRequestCount": 19,
    "expectedSuccessRequestCount": 19,
    "scheme": "https",
    "allowedHost": "proxy.golang.org",
    "allowedContentTypes": ["application/zip", "application/octet-stream"],
    "successStatusCode": 200,
    "tlsCertificateValidationRequired": True,
    "tlsHostnameValidationRequired": True,
    "ambientProxyAllowed": False,
    "redirectsAllowed": False,
    "credentialsAllowed": False,
    "authenticationChallengeAllowed": False,
    "urlQueryAllowed": False,
    "urlFragmentAllowed": False,
    "automaticRetryAllowed": False,
    "alternateMirrorAllowed": False,
    "wrapperFallbackAllowed": False,
    "packageManagerAllowed": False,
    "goCommandAllowed": False,
    "gitCommandAllowed": False,
    "shellAllowed": False,
    "subprocessAllowed": False,
    "compilerAllowed": False,
    "sourceExtractionAllowed": False,
    "sourceLoadingAllowed": False,
    "sourceExecutionAllowed": False,
    "claimPath": WAVE_CLAIM_PATH,
    "stagingParentPath": WAVE_STAGING_PARENT_PATH,
    "stagingNamePrefix": WAVE_STAGING_NAME_PREFIX,
    "finalDirectoryPath": WAVE_FINAL_DIRECTORY_PATH,
    "successReceiptPath": WAVE_SUCCESS_RECEIPT_PATH,
    "failureReceiptPath": WAVE_FAILURE_RECEIPT_PATH,
    "manifestPath": WAVE_MANIFEST_PATH,
    "firstMismatchRule": (
        "stop_consume_permit_publish_bounded_failure_retain_no_accepted_final_"
        "set_require_new_decision"
    ),
}

EXPECTED_FILESYSTEM_CONTRACT = {
    "ownerOnlyDirectoriesRequired": True,
    "ownerOnlyFilesRequired": True,
    "regularFilesOnly": True,
    "singleLinkRequired": True,
    "noFollowTraversalRequired": True,
    "directoryFdRelativeOperationsRequired": True,
    "exclusiveCreateRequired": True,
    "existingFinalOutputForbidden": True,
    "unexpectedSiblingForbidden": True,
    "stableAncestorIdentityRequired": True,
    "stableOpenedFileIdentityRequired": True,
    "atomicNoReplaceFinalDirectoryPublicationRequired": True,
    "manifestWrittenLast": True,
    "partialAcceptedSetAllowed": False,
    "absolutePathsRecorded": False,
}

EXPECTED_RECEIPT_CONTRACT = {
    "successAndFailureAreMutuallyExclusive": True,
    "successRequiresExactRequestCount": 19,
    "successRequiresExactAcceptedArtifactCount": 19,
    "successRequiresDecisionAndPredecessorBindings": True,
    "successRequiresOrderedRequestAndArtifactRows": True,
    "successRequiresRawByteSizeAndSha256": True,
    "successRequiresModuleZipAndGoModH1": True,
    "moduleZipH1Algorithm": (
        "golang.org/x/mod/sumdb/dirhash.HashZip(Hash1)_v1"
    ),
    "moduleZipH1Canonicalization": {
        "validatedEntrySet": (
            "all_exactly_once_non_directory_regular_central_directory_entries"
        ),
        "directoryEntryRule": "reject_before_hash",
        "duplicateNameRule": "reject_before_hash",
        "nameEncoding": "exact_valid_utf8_zip_entry_name",
        "nameNewlineRule": "reject_before_hash",
        "sortOrder": "ascending_utf8_bytes_equivalent_to_go_string_order",
        "fileDigest": "lowercase_hex_sha256_exact_uncompressed_content",
        "rowEncoding": (
            "file_digest_two_ascii_spaces_full_zip_entry_name_lf"
        ),
        "aggregateDigest": "sha256_concatenated_rows",
        "resultEncoding": (
            "h1_colon_rfc4648_standard_base64_with_padding"
        ),
    },
    "goModH1Algorithm": (
        "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod"
    ),
    "goModH1Canonicalization": {
        "fileName": "go.mod",
        "fileDigest": "lowercase_hex_sha256_exact_response_bytes",
        "rowEncoding": "file_digest_two_ascii_spaces_go.mod_lf",
        "aggregateDigest": "sha256_single_row",
        "resultEncoding": (
            "h1_colon_rfc4648_standard_base64_with_padding"
        ),
    },
    "successRequiresArchiveStructureAndPrefix": True,
    "successRequiresModeAndLinkCount": True,
    "successRequiresOrderedSourceSetDigest": True,
    "orderedSourceSetDigestAlgorithm": "sha256",
    "orderedSourceSetDigestCanonicalization": {
        "schema": "aetherlink.g2-pion-dependency-source-set-digest.v1",
        "documentShape": "object_with_schema_and_sources_array_only",
        "sourceOrder": "exact_wave_order_1_through_19",
        "sourceKeys": "exact_orderedSourceSetDigestFields",
        "json": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "digestScope": "entire_canonical_document_without_digest_field",
    },
    "orderedSourceSetDigestFields": [
        "order",
        "tupleId",
        "module",
        "version",
        "url",
        "outputPath",
        "rawByteSize",
        "rawSha256",
        "moduleZipH1",
        "goModH1",
        "entryCount",
        "uncompressedByteCount",
        "modulePrefix",
        "mode",
        "linkCount",
    ],
    "successRequiresManifestLastIndependentReadback": True,
    "failureUsesBoundedReasonCodesOnly": True,
    "failureMayRecordFailedTupleId": True,
    "failureMayRecordSafeNumericObservations": True,
    "failureRecordsCredentialsCookiesAuthorizationHeaders": False,
    "failureRecordsRawCertificatesOrResponseBodies": False,
    "failureRecordsAbsoluteFilesystemPaths": False,
    "automaticRetryAfterFailure": False,
}

EXPECTED_SEQUENCE = [
    {
        "order": 1,
        "stepId": "bind_patch_dependency_portfolio",
        "prepared": True,
        "executed": True,
    },
    {
        "order": 2,
        "stepId": "select_dependency_review_lane",
        "prepared": True,
        "executed": True,
    },
    {
        "order": 3,
        "stepId": "prepare_staged_fixed_point_review_plan",
        "prepared": True,
        "executed": True,
    },
    {
        "order": 4,
        "stepId": "prepare_bounded_dependency_source_identity_and_acquisition_decision",
        "prepared": True,
        "executed": True,
    },
    {
        "order": 5,
        "stepId": "acquire_immutable_bounded_waves",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 6,
        "stepId": "expand_exact_graph_to_fixed_point",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 7,
        "stepId": "two_pass_source_license_security_review",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 8,
        "stepId": "publish_sbom_manifest_and_independent_readback",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 9,
        "stepId": "prepare_separate_root_implementation_selection_decision",
        "prepared": False,
        "executed": False,
    },
]

EXPECTED_AUTHORITY = {
    "sourceModificationAuthorized": False,
    "sourceExtractionAuthorized": False,
    "dependencyAcquisitionAuthorized": False,
    "sourceAcquisitionHttpsAuthorized": False,
    "sourceAcquisitionDnsAndTlsAuthorized": False,
    "packageManagerAuthorized": False,
    "compilerAuthorized": False,
    "sourceLoadAuthorized": False,
    "sourceExecutionAuthorized": False,
    "runtimeSocketAuthorized": False,
    "runtimeNetworkAuthorized": False,
    "productNetworkAuthorized": False,
    "deviceAuthorized": False,
    "deploymentAuthorized": False,
    "gitWriteAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "externalAuthenticationRequired": False,
    "userActionRequired": False,
}

EXPECTED_EXECUTION = {
    "decisionRecorded": True,
    "acquisitionExecuted": False,
    "permitConsumed": False,
    "requestCount": 0,
    "acceptedArtifactCount": 0,
    "successReceiptCreated": False,
    "failureReceiptCreated": False,
    "manifestCreated": False,
    "dependencySourceReviewed": False,
    "graphExpanded": False,
    "sourceCompiled": False,
    "sourceLoaded": False,
    "sourceExecuted": False,
    "runtimeNetworkUsed": False,
    "deviceUsed": False,
    "deploymentPerformed": False,
    "gitOperationPerformed": False,
}

EXPECTED_CLOSURE = {
    "findingsClosedByDecision": 0,
    "openFindingCount": 19,
    "rootPatchComplete": False,
    "dependencySourceReviewed": False,
    "dependencyClosureComplete": False,
    "semanticClosureComplete": False,
    "rungThreeComplete": False,
    "candidateSelected": False,
    "librarySelected": False,
}

EXPECTED_NONCLAIMS = {
    "rootSeedIsCompleteGraphEvidence": False,
    "selectedWaveIsProductionReachabilityProof": False,
    "goSumIsDirectDependencyRepositoryAttestation": False,
    "proxyOriginIsSufficientAcceptance": False,
    "rawSha256IsIndependentUpstreamAuthentication": False,
    "sourceIdentityDecisionIsAcquisitionAuthority": False,
    "sourceIdentityDecisionIsDependencyReview": False,
    "sourceIdentityDecisionIsDependencyClosure": False,
    "dependencyReviewSelectsLibrary": False,
    "productEndpointAuthenticationSatisfied": False,
}

EXPECTED_READER_BINDING = {
    "path": READER_PATH,
    "byteSize": 14017,
    "rawSha256": EXPECTED_RAW[READER_PATH],
}

EXPECTED_STATUS = (
    "wave1_source_identity_and_request_contract_prepared_acquisition_not_authorized"
)
EXPECTED_RESULT = (
    "exact_19_root_requirement_source_identities_and_bounded_wave1_request_"
    "contract_prepared"
)
EXPECTED_NEXT_ACTION = (
    "prepare_separate_versioned_wave1_execution_permit_after_checker_runner_"
    "and_tests"
)
EXPECTED_PREFIX_SIBLINGS = (
    (
        "bounded-dependency-source-identity-and-acquisition-decision-v1.json",
        "file",
    ),
    (
        "bounded-dependency-source-identity-and-acquisition-decision-v1.md",
        "file",
    ),
)


class CheckError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def require_isolated_interpreter() -> None:
    require(
        bool(
            sys.flags.isolated
            and sys.flags.no_site
            and sys.flags.ignore_environment
        ),
        "E_RUNTIME",
        "run with python3 -I -B -S",
    )


def fail(code: str, message: str) -> None:
    raise CheckError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def strict_equal(actual: Any, expected: Any, code: str, path: str) -> None:
    require(type(actual) is type(expected), code, f"{path}: exact type drift")
    if isinstance(expected, dict):
        require(set(actual) == set(expected), code, f"{path}: exact key set drift")
        for key in expected:
            strict_equal(actual[key], expected[key], code, f"{path}.{key}")
    elif isinstance(expected, list):
        require(len(actual) == len(expected), code, f"{path}: list length drift")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            strict_equal(actual_item, expected_item, code, f"{path}[{index}]")
    else:
        require(actual == expected, code, f"{path}: exact value drift")


def reject_constant(value: str) -> None:
    fail("E_JSON", f"non-finite JSON number is forbidden: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("E_JSON", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
        require(not text.startswith("\ufeff"), "E_JSON", f"{label}: BOM forbidden")
        value = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("E_JSON", f"{label}: invalid strict UTF-8 JSON: {exc}")
    require(type(value) is dict, "E_JSON", f"{label}: top-level object required")
    require(text.endswith("\n"), "E_JSON", f"{label}: final LF required")
    return value


def validate_relative_path(relative: str) -> tuple[str, ...]:
    path = PurePosixPath(relative)
    require(not path.is_absolute(), "E_FILESYSTEM", f"absolute path: {relative}")
    require(
        bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts),
        "E_FILESYSTEM",
        f"unsafe path: {relative}",
    )
    return path.parts


def file_state(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


class DirectoryLink:
    def __init__(
        self,
        parent_fd: int,
        name: str,
        child_fd: int,
        state: tuple[int, int, int, int, int, int, int],
    ) -> None:
        self.parent_fd = parent_fd
        self.name = name
        self.child_fd = child_fd
        self.state = state


class Snapshot:
    def __init__(
        self,
        relative: str,
        root_fd: int,
        root_state: tuple[int, int, int, int, int, int, int],
        directory_links: list[DirectoryLink],
        parent_fd: int,
        filename: str,
        file_fd: int,
        state: tuple[int, int, int, int, int, int, int],
        data: bytes,
    ) -> None:
        self.relative = relative
        self.root_fd = root_fd
        self.root_state = root_state
        self.directory_links = directory_links
        self.parent_fd = parent_fd
        self.filename = filename
        self.file_fd = file_fd
        self.state = state
        self.data = data


class AbsenceSnapshot:
    def __init__(
        self,
        relative: str,
        root_fd: int,
        root_state: tuple[int, int, int, int, int, int, int],
        directory_links: list[DirectoryLink],
        parent_fd: int,
        missing_name: str,
    ) -> None:
        self.relative = relative
        self.root_fd = root_fd
        self.root_state = root_state
        self.directory_links = directory_links
        self.parent_fd = parent_fd
        self.missing_name = missing_name


def open_flags(*, directory: bool) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if directory and hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    return flags


def secure_read(relative: str, maximum_bytes: int) -> Snapshot:
    parts = validate_relative_path(relative)
    root_info = ROOT.lstat()
    require(
        stat.S_ISDIR(root_info.st_mode) and not stat.S_ISLNK(root_info.st_mode),
        "E_FILESYSTEM",
        "repository root must be a real directory",
    )
    root_fd = os.open(ROOT, open_flags(directory=True))
    directory_links: list[DirectoryLink] = []
    file_fd = -1
    try:
        root_opened = os.fstat(root_fd)
        require(
            file_state(root_opened) == file_state(root_info),
            "E_FILESYSTEM",
            "repository root identity changed",
        )
        current_fd = root_fd
        for part in parts[:-1]:
            before = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            require(
                stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode),
                "E_FILESYSTEM",
                f"real directory ancestor required: {relative}",
            )
            child_fd = os.open(part, open_flags(directory=True), dir_fd=current_fd)
            opened = os.fstat(child_fd)
            require(
                file_state(opened) == file_state(before),
                "E_FILESYSTEM",
                f"directory identity changed: {relative}",
            )
            directory_links.append(
                DirectoryLink(current_fd, part, child_fd, file_state(before))
            )
            current_fd = child_fd

        filename = parts[-1]
        before_file = os.stat(filename, dir_fd=current_fd, follow_symlinks=False)
        require(
            stat.S_ISREG(before_file.st_mode)
            and not stat.S_ISLNK(before_file.st_mode),
            "E_FILESYSTEM",
            f"regular file required: {relative}",
        )
        require(
            before_file.st_nlink == 1,
            "E_FILESYSTEM",
            f"single-link file required: {relative}",
        )
        file_fd = os.open(filename, open_flags(directory=False), dir_fd=current_fd)
        opened_file = os.fstat(file_fd)
        require(
            file_state(opened_file) == file_state(before_file),
            "E_FILESYSTEM",
            f"file identity changed before read: {relative}",
        )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            require(
                total <= maximum_bytes,
                "E_FILESYSTEM",
                f"file exceeds read bound: {relative}",
            )
        require(
            file_state(os.fstat(file_fd)) == file_state(before_file),
            "E_FILESYSTEM",
            f"file changed during read: {relative}",
        )
        return Snapshot(
            relative,
            root_fd,
            file_state(root_info),
            directory_links,
            current_fd,
            filename,
            file_fd,
            file_state(before_file),
            b"".join(chunks),
        )
    except Exception:
        if file_fd >= 0:
            os.close(file_fd)
        for link in reversed(directory_links):
            os.close(link.child_fd)
        os.close(root_fd)
        raise


def secure_absence(relative: str) -> AbsenceSnapshot:
    parts = validate_relative_path(relative)
    root_info = ROOT.lstat()
    require(
        stat.S_ISDIR(root_info.st_mode) and not stat.S_ISLNK(root_info.st_mode),
        "E_FILESYSTEM",
        "repository root must be a real directory",
    )
    root_fd = os.open(ROOT, open_flags(directory=True))
    directory_links: list[DirectoryLink] = []
    try:
        root_opened = os.fstat(root_fd)
        require(
            file_state(root_opened) == file_state(root_info),
            "E_FILESYSTEM",
            "repository root identity changed",
        )
        current_fd = root_fd
        for index, part in enumerate(parts):
            try:
                before = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            except FileNotFoundError:
                return AbsenceSnapshot(
                    relative,
                    root_fd,
                    file_state(root_info),
                    directory_links,
                    current_fd,
                    part,
                )
            require(
                index < len(parts) - 1,
                "E_PREPARATION_STATE",
                f"premature execution artifact exists: {relative}",
            )
            require(
                stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode),
                "E_FILESYSTEM",
                f"real directory ancestor required: {relative}",
            )
            child_fd = os.open(part, open_flags(directory=True), dir_fd=current_fd)
            opened = os.fstat(child_fd)
            require(
                file_state(opened) == file_state(before),
                "E_FILESYSTEM",
                f"directory identity changed: {relative}",
            )
            directory_links.append(
                DirectoryLink(current_fd, part, child_fd, file_state(before))
            )
            current_fd = child_fd
    except Exception:
        for link in reversed(directory_links):
            os.close(link.child_fd)
        os.close(root_fd)
        raise
    fail("E_INTERNAL", f"absence traversal did not terminate: {relative}")


def verify_snapshot(snapshot: Snapshot) -> None:
    require(
        file_state(ROOT.lstat()) == snapshot.root_state,
        "E_TOCTOU",
        f"repository root changed: {snapshot.relative}",
    )
    require(
        file_state(os.fstat(snapshot.root_fd)) == snapshot.root_state,
        "E_TOCTOU",
        f"opened repository root changed: {snapshot.relative}",
    )
    for link in snapshot.directory_links:
        linked = os.stat(link.name, dir_fd=link.parent_fd, follow_symlinks=False)
        require(
            file_state(linked) == link.state
            and file_state(os.fstat(link.child_fd)) == link.state,
            "E_TOCTOU",
            f"ancestor changed: {snapshot.relative}",
        )
    linked_file = os.stat(
        snapshot.filename,
        dir_fd=snapshot.parent_fd,
        follow_symlinks=False,
    )
    require(
        file_state(linked_file) == snapshot.state
        and file_state(os.fstat(snapshot.file_fd)) == snapshot.state,
        "E_TOCTOU",
        f"file path changed after read: {snapshot.relative}",
    )
    os.lseek(snapshot.file_fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(snapshot.file_fd, 65_536)
        if not chunk:
            break
        chunks.append(chunk)
    require(
        b"".join(chunks) == snapshot.data,
        "E_TOCTOU",
        f"file bytes changed after read: {snapshot.relative}",
    )


def verify_absence_snapshot(snapshot: AbsenceSnapshot) -> None:
    require(
        file_state(ROOT.lstat()) == snapshot.root_state,
        "E_TOCTOU",
        f"repository root changed: {snapshot.relative}",
    )
    require(
        file_state(os.fstat(snapshot.root_fd)) == snapshot.root_state,
        "E_TOCTOU",
        f"opened repository root changed: {snapshot.relative}",
    )
    for link in snapshot.directory_links:
        linked = os.stat(link.name, dir_fd=link.parent_fd, follow_symlinks=False)
        require(
            file_state(linked) == link.state
            and file_state(os.fstat(link.child_fd)) == link.state,
            "E_TOCTOU",
            f"ancestor changed: {snapshot.relative}",
        )
    try:
        os.stat(
            snapshot.missing_name,
            dir_fd=snapshot.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    fail(
        "E_TOCTOU",
        f"premature execution artifact appeared: {snapshot.relative}",
    )


def close_snapshots(
    snapshots: list[Snapshot | AbsenceSnapshot],
) -> None:
    for snapshot in snapshots:
        if isinstance(snapshot, Snapshot):
            try:
                os.close(snapshot.file_fd)
            except OSError:
                pass
        for link in reversed(snapshot.directory_links):
            try:
                os.close(link.child_fd)
            except OSError:
                pass
        try:
            os.close(snapshot.root_fd)
        except OSError:
            pass


def inventory_prefixed_siblings(
    relative: str,
    prefix: str,
) -> tuple[
    tuple[int, int, int, int, int, int, int],
    tuple[tuple[str, str], ...],
]:
    base = ROOT.joinpath(*validate_relative_path(relative))
    before = base.lstat()
    require(
        stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode),
        "E_INVENTORY",
        f"real sibling directory required: {relative}",
    )
    directory_fd = os.open(base, open_flags(directory=True))
    try:
        opened = os.fstat(directory_fd)
        require(
            file_state(opened) == file_state(before),
            "E_INVENTORY",
            f"sibling directory identity changed: {relative}",
        )
        found: list[tuple[str, str]] = []
        with os.scandir(directory_fd) as scanner:
            for entry in scanner:
                if not entry.name.startswith(prefix):
                    continue
                info = entry.stat(follow_symlinks=False)
                require(
                    not entry.is_symlink(),
                    "E_INVENTORY",
                    f"prefixed sibling symlink forbidden: {relative}/{entry.name}",
                )
                if stat.S_ISDIR(info.st_mode):
                    kind = "directory"
                elif stat.S_ISREG(info.st_mode):
                    require(
                        info.st_nlink == 1,
                        "E_INVENTORY",
                        f"single-link prefixed sibling required: "
                        f"{relative}/{entry.name}",
                    )
                    kind = "file"
                else:
                    fail(
                        "E_INVENTORY",
                        f"special prefixed sibling forbidden: "
                        f"{relative}/{entry.name}",
                    )
                found.append((entry.name, kind))
        require(
            file_state(os.fstat(directory_fd)) == file_state(before),
            "E_INVENTORY",
            f"sibling directory changed during inventory: {relative}",
        )
        return file_state(before), tuple(sorted(found))
    finally:
        os.close(directory_fd)


def verify_no_prefixed_siblings(relative: str, prefix: str) -> None:
    base = ROOT.joinpath(*validate_relative_path(relative))
    try:
        before = base.lstat()
    except FileNotFoundError:
        return
    require(
        stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode),
        "E_PREPARATION_STATE",
        f"real staging parent required when present: {relative}",
    )
    directory_fd = os.open(base, open_flags(directory=True))
    try:
        require(
            file_state(os.fstat(directory_fd)) == file_state(before),
            "E_PREPARATION_STATE",
            f"staging parent identity changed: {relative}",
        )
        with os.scandir(directory_fd) as scanner:
            for entry in scanner:
                require(
                    not entry.name.startswith(prefix),
                    "E_PREPARATION_STATE",
                    f"premature staging artifact exists: {relative}/{entry.name}",
                )
        require(
            file_state(os.fstat(directory_fd)) == file_state(before),
            "E_PREPARATION_STATE",
            f"staging parent changed during inventory: {relative}",
        )
    finally:
        os.close(directory_fd)


def verify_content_binding(
    document: dict[str, Any],
    label: str,
    expected_scope: str,
    expected_digest: str | None = None,
) -> None:
    binding = document.get("contentBinding")
    require(type(binding) is dict, "E_BINDING", f"{label}: binding missing")
    strict_equal(
        set(binding),
        {"algorithm", "canonicalization", "scope", "sha256"},
        "E_BINDING",
        f"{label}.contentBinding.keys",
    )
    strict_equal(binding["algorithm"], "sha256", "E_BINDING", f"{label}.algorithm")
    strict_equal(
        binding["canonicalization"],
        "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "E_BINDING",
        f"{label}.canonicalization",
    )
    strict_equal(binding["scope"], expected_scope, "E_BINDING", f"{label}.scope")
    payload = dict(document)
    payload.pop("contentBinding")
    computed = sha256(canonical_bytes(payload))
    strict_equal(binding["sha256"], computed, "E_BINDING", f"{label}.sha256")
    if expected_digest is not None:
        strict_equal(
            computed,
            expected_digest,
            "E_BINDING",
            f"{label}.expectedContentSha256",
        )


def verify_source_archive(data: bytes) -> None:
    strict_equal(
        len(data),
        EXPECTED_SOURCE_SNAPSHOT["archiveByteSize"],
        "E_SOURCE_SNAPSHOT",
        "sourceArchive.byteSize",
    )
    strict_equal(
        sha256(data),
        EXPECTED_SOURCE_SNAPSHOT["archiveRawSha256"],
        "E_SOURCE_SNAPSHOT",
        "sourceArchive.rawSha256",
    )
    bodies: dict[str, bytes] = {}
    tree_rows: list[bytes] = []
    total_uncompressed = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data), mode="r") as archive:
            infos = archive.infolist()
            strict_equal(
                len(infos),
                EXPECTED_SOURCE_SNAPSHOT["archiveEntryCount"],
                "E_SOURCE_SNAPSHOT",
                "sourceArchive.entryCount",
            )
            names: set[str] = set()
            for info in infos:
                name = info.filename
                require(
                    type(name) is str
                    and name.startswith(SOURCE_MODULE_PREFIX)
                    and len(name) > len(SOURCE_MODULE_PREFIX)
                    and "\x00" not in name
                    and "\n" not in name
                    and "\r" not in name
                    and "\\" not in name,
                    "E_SOURCE_SNAPSHOT",
                    "source archive entry name or prefix drift",
                )
                require(
                    name not in names,
                    "E_SOURCE_SNAPSHOT",
                    "duplicate source archive entry",
                )
                names.add(name)
                require(
                    not info.is_dir()
                    and not name.endswith("/")
                    and info.compress_type
                    in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    and not (info.flag_bits & 0x1),
                    "E_SOURCE_SNAPSHOT",
                    "regular unencrypted source archive entry required",
                )
                body = archive.read(info)
                require(
                    len(body) == info.file_size,
                    "E_SOURCE_SNAPSHOT",
                    "source archive entry size drift",
                )
                relative = name[len(SOURCE_MODULE_PREFIX) :]
                bodies[relative] = body
                total_uncompressed += len(body)
                tree_rows.append(
                    (
                        f"{relative}\0{len(body)}\0{sha256(body)}\n"
                    ).encode("utf-8")
                )
    except (
        zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
        UnicodeError,
        OSError,
    ) as exc:
        fail("E_SOURCE_SNAPSHOT", f"retained source ZIP is invalid: {exc}")

    strict_equal(
        total_uncompressed,
        EXPECTED_SOURCE_SNAPSHOT["archiveTotalUncompressedBytes"],
        "E_SOURCE_SNAPSHOT",
        "sourceArchive.totalUncompressedBytes",
    )
    strict_equal(
        sha256(b"".join(sorted(tree_rows))),
        EXPECTED_SOURCE_SNAPSHOT["sourceTreeSha256"],
        "E_SOURCE_SNAPSHOT",
        "sourceArchive.sourceTreeSha256",
    )
    require(
        set(("go.mod", "go.sum")).issubset(bodies),
        "E_SOURCE_SNAPSHOT",
        "embedded root go.mod and go.sum required",
    )
    strict_equal(
        sha256(bodies["go.mod"]),
        EXPECTED_SOURCE_SNAPSHOT["goModRawSha256"],
        "E_SOURCE_SNAPSHOT",
        "sourceArchive.goModRawSha256",
    )
    strict_equal(
        sha256(bodies["go.sum"]),
        EXPECTED_SOURCE_SNAPSHOT["goSumRawSha256"],
        "E_SOURCE_SNAPSHOT",
        "sourceArchive.goSumRawSha256",
    )


def build_expected_wave(
    requirements: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checksum_map: dict[tuple[str, str], str] = {}
    for record in records:
        require(
            type(record) is dict
            and set(record) == {"module", "version", "h1"},
            "E_SEED",
            "go.sum record schema drift",
        )
        key = (record["module"], record["version"])
        require(key not in checksum_map, "E_SEED", f"duplicate checksum: {key}")
        checksum_map[key] = record["h1"]

    result: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements, 1):
        require(
            type(requirement) is dict
            and set(requirement) == {"module", "version", "direct"},
            "E_SEED",
            "root requirement schema drift",
        )
        module = requirement["module"]
        version = requirement["version"]
        require(
            type(module) is str
            and type(version) is str
            and type(requirement["direct"]) is bool,
            "E_SEED",
            "root requirement exact type drift",
        )
        require(
            module == module.lower() and version == version.lower(),
            "E_SEED",
            "wave-one module and version must already be canonical lower-case",
        )
        tuple_digest = sha256(f"{module}\n{version}\n".encode("utf-8"))
        module_h1 = checksum_map.get((module, version))
        go_mod_h1 = checksum_map.get((module, f"{version}/go.mod"))
        require(
            type(module_h1) is str and type(go_mod_h1) is str,
            "E_SEED",
            f"both source and go.mod h1 required: {module}@{version}",
        )
        result.append(
            {
                "order": index,
                "tupleId": f"wave1-{index:03d}-{tuple_digest[:12]}",
                "tupleSha256": tuple_digest,
                "module": module,
                "version": version,
                "rootRequirementClass": (
                    "direct" if requirement["direct"] else "indirect"
                ),
                "selected": True,
                "selectionReason": (
                    "exact_root_go_mod_requirement_conservative_first_wave_seed"
                ),
                "moduleZipH1": module_h1,
                "goModH1": go_mod_h1,
                "sourceIdentityTrustRole": (
                    "root_pion_sumdb_verified_archive_embedded_go_sum_checksum_"
                    "identity_not_direct_upstream_repository_attestation"
                ),
                "url": f"https://proxy.golang.org/{module}/@v/{version}.zip",
                "scheme": "https",
                "host": "proxy.golang.org",
                "path": f"/{module}/@v/{version}.zip",
                "outputPath": (
                    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1/"
                    f"accepted/{index:03d}-{tuple_digest[:20]}.zip"
                ),
            }
        )
    return result


def verify_reader(data: bytes) -> None:
    require(len(data) == 14017, "E_READER", "reader byte size drift")
    require(sha256(data) == EXPECTED_RAW[READER_PATH], "E_READER", "reader hash drift")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("E_READER", f"reader is not UTF-8: {exc}")
    normalized = " ".join(text.split())
    required = (
        "source acquisition and public-proxy network I/O remain unauthorized",
        "separate versioned one-use execution permit",
        "Neither repository-owner identity proof, external authentication, nor user",
        "all 19 canonical findings remain open",
        "production-reachability",
        "direct attestation by each dependency's repository owner",
        "reads all 129 in-memory entries without filesystem extraction",
        "wave claim, staging prefix, accepted directory, success receipt, failure receipt, and manifest are absent",
        "golang.org/x/mod/sumdb/dirhash.HashZip(Hash1)",
        "aetherlink.g2-pion-dependency-source-set-digest.v1",
    )
    for phrase in required:
        require(
            phrase in normalized,
            "E_READER",
            f"reader phrase missing: {phrase}",
        )
    forbidden = (
        "acquisition is complete",
        "dependency closure is complete",
        "candidate is selected",
        "library is selected",
        "externalauthenticationrequired=true",
        "useractionrequired=true",
        "requires external authentication",
        "requires user action",
        "must authenticate",
    )
    lowered = normalized.lower()
    for phrase in forbidden:
        require(phrase not in lowered, "E_READER", f"reader overclaim: {phrase}")
    table_rows = sum(
        1
        for line in text.splitlines()
        if line.startswith("| ") and line.split("|", 2)[1].strip().isdigit()
    )
    require(table_rows == 19, "E_READER", "reader tuple table count drift")


def verify_decision(
    decision: dict[str, Any],
    documents: dict[str, dict[str, Any]],
) -> None:
    strict_equal(
        set(decision),
        EXPECTED_TOP_LEVEL_KEYS,
        "E_SCHEMA",
        "decision.topLevelKeys",
    )
    strict_equal(
        decision["documentType"],
        "aetherlink.g2-pion-rung3-bounded-dependency-source-identity-and-"
        "acquisition-decision",
        "E_SCHEMA",
        "decision.documentType",
    )
    strict_equal(decision["schemaVersion"], "1.0", "E_SCHEMA", "schemaVersion")
    strict_equal(
        decision["decisionId"],
        "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-identity-and-"
        "acquisition-decision-v1",
        "E_SCHEMA",
        "decisionId",
    )
    strict_equal(decision["recordedDate"], "2026-07-24", "E_SCHEMA", "recordedDate")
    strict_equal(decision["status"], EXPECTED_STATUS, "E_STATE", "status")
    strict_equal(
        decision["predecessorBinding"],
        EXPECTED_PREDECESSOR_BINDING,
        "E_LINEAGE",
        "predecessorBinding",
    )
    strict_equal(
        decision["evidenceBindings"],
        EXPECTED_EVIDENCE_BINDINGS,
        "E_LINEAGE",
        "evidenceBindings",
    )
    strict_equal(
        decision["sourceSnapshot"],
        EXPECTED_SOURCE_SNAPSHOT,
        "E_SOURCE",
        "sourceSnapshot",
    )
    strict_equal(
        decision["productionProfiles"],
        EXPECTED_PROFILES,
        "E_PROFILE",
        "productionProfiles",
    )

    predecessor = documents[PREDECESSOR_PATH]
    strict_equal(
        predecessor["status"],
        EXPECTED_PREDECESSOR_BINDING["requiredStatus"],
        "E_LINEAGE",
        "predecessor.status",
    )
    strict_equal(
        predecessor["result"],
        EXPECTED_PREDECESSOR_BINDING["requiredResult"],
        "E_LINEAGE",
        "predecessor.result",
    )
    strict_equal(
        predecessor["nextAction"],
        EXPECTED_PREDECESSOR_BINDING["requiredNextAction"],
        "E_LINEAGE",
        "predecessor.nextAction",
    )

    patch = documents[PATCH_DECISION_PATH]
    offline = documents[OFFLINE_RESULT_PATH]
    dependency_seed = patch.get("dependencySeed")
    require(type(dependency_seed) is dict, "E_SEED", "dependency seed missing")
    requirements = dependency_seed.get("requirements")
    context = dependency_seed.get("checksumOnlyContextTuples")
    require(type(requirements) is list, "E_SEED", "requirements list missing")
    require(type(context) is list, "E_SEED", "context tuple list missing")
    require(len(requirements) == 19, "E_SEED", "root requirement count drift")
    require(len(context) == 4, "E_SEED", "context tuple count drift")

    expected_root_seed = {
        "selectionPolicy": (
            "all_exact_root_go_mod_requirements_conservative_first_wave_seed"
        ),
        "selectedTupleCount": 19,
        "selectedDirectTupleCount": 10,
        "selectedIndirectTupleCount": 9,
        "allRootRequirementsSelectedForIntake": True,
        "selectionIsProductionReachabilityClaim": False,
        "requirements": requirements,
        "checksumOnlyContextTuples": context,
    }
    strict_equal(
        decision["rootSeed"],
        expected_root_seed,
        "E_SEED",
        "rootSeed",
    )

    metadata = offline.get("dependencyMetadata")
    require(type(metadata) is dict, "E_SEED", "offline dependency metadata missing")
    go_sum = metadata.get("goSum")
    require(type(go_sum) is dict, "E_SEED", "offline go.sum metadata missing")
    strict_equal(go_sum.get("recordCount"), 44, "E_SEED", "goSum.recordCount")
    records = go_sum.get("records")
    require(type(records) is list, "E_SEED", "go.sum records missing")
    expected_tuples = build_expected_wave(requirements, records)
    expected_wave = {
        "waveId": "g2-pion-ice-v4.3.0-dependency-source-wave1-v1",
        "order": 1,
        "selectedTupleCount": 19,
        "maximumRequestCount": 19,
        "expectedSuccessRequestCount": 19,
        "sequentialOrderRequired": True,
        "automaticRetryAllowed": False,
        "tuples": expected_tuples,
    }
    strict_equal(decision["wave"], expected_wave, "E_WAVE", "wave")
    require(
        len({row["tupleSha256"] for row in expected_tuples}) == 19,
        "E_WAVE",
        "tuple identities must be unique",
    )
    require(
        len({row["url"] for row in expected_tuples}) == 19,
        "E_WAVE",
        "request URLs must be unique",
    )
    require(
        len({row["outputPath"] for row in expected_tuples}) == 19,
        "E_WAVE",
        "output paths must be unique",
    )

    strict_equal(
        decision["sourceIdentityPolicy"],
        EXPECTED_IDENTITY_POLICY,
        "E_IDENTITY",
        "sourceIdentityPolicy",
    )
    strict_equal(
        decision["plannedAcquisitionContract"],
        EXPECTED_PLANNED_CONTRACT,
        "E_AUTHORITY",
        "plannedAcquisitionContract",
    )
    strict_equal(
        decision["resourceLimits"],
        EXPECTED_RESOURCE_LIMITS,
        "E_BOUNDS",
        "resourceLimits",
    )
    for key, value in decision["resourceLimits"].items():
        require(
            type(value) is int and value > 0,
            "E_BOUNDS",
            f"positive exact integer required: resourceLimits.{key}",
        )
    strict_equal(
        decision["filesystemContract"],
        EXPECTED_FILESYSTEM_CONTRACT,
        "E_FILESYSTEM_CONTRACT",
        "filesystemContract",
    )
    strict_equal(
        decision["receiptContract"],
        EXPECTED_RECEIPT_CONTRACT,
        "E_RECEIPT",
        "receiptContract",
    )
    strict_equal(decision["sequence"], EXPECTED_SEQUENCE, "E_SEQUENCE", "sequence")
    strict_equal(
        decision["authority"], EXPECTED_AUTHORITY, "E_AUTHORITY", "authority"
    )
    strict_equal(
        decision["execution"], EXPECTED_EXECUTION, "E_EXECUTION", "execution"
    )
    strict_equal(decision["closure"], EXPECTED_CLOSURE, "E_CLOSURE", "closure")
    strict_equal(
        decision["nonClaims"], EXPECTED_NONCLAIMS, "E_NONCLAIM", "nonClaims"
    )
    strict_equal(
        decision["readerDocumentBinding"],
        EXPECTED_READER_BINDING,
        "E_READER",
        "readerDocumentBinding",
    )
    strict_equal(decision["result"], EXPECTED_RESULT, "E_STATE", "result")
    strict_equal(decision["nextAction"], EXPECTED_NEXT_ACTION, "E_STATE", "nextAction")
    verify_content_binding(
        decision,
        DECISION_PATH,
        "decision_without_contentBinding",
    )


def check(
    root: Path,
    before_final_barrier: Callable[[list[Snapshot]], None] | None = None,
) -> None:
    global ROOT
    ROOT = root
    snapshots: list[Snapshot] = []
    absence_snapshots: list[AbsenceSnapshot] = []
    required_paths = (
        DECISION_PATH,
        READER_PATH,
        PREDECESSOR_PATH,
        PREDECESSOR_CHECKER_PATH,
        PREDECESSOR_TESTS_PATH,
        PLAN_PATH,
        PROFILE_PATH,
        PROVENANCE_PATH,
        RUNG_TWO_DECISION_PATH,
        RUNG_TWO_RECEIPT_PATH,
        OFFLINE_RESULT_PATH,
        CLASSIFICATIONS_PATH,
        SEMANTIC_RESULT_PATH,
        SEMANTIC_MANIFEST_PATH,
        PATCH_DECISION_PATH,
        SOURCE_ARCHIVE_PATH,
    )
    required_absent_paths = (
        WAVE_CLAIM_PATH,
        WAVE_FINAL_DIRECTORY_PATH,
        WAVE_SUCCESS_RECEIPT_PATH,
        WAVE_FAILURE_RECEIPT_PATH,
        WAVE_MANIFEST_PATH,
    )
    sibling_before = inventory_prefixed_siblings(
        RUNG_THREE,
        "bounded-dependency-source-identity-and-acquisition-decision-v1",
    )
    require(
        sibling_before[1] == EXPECTED_PREFIX_SIBLINGS,
        "E_INVENTORY",
        "decision prefixed sibling set drift",
    )
    try:
        for relative in required_absent_paths:
            try:
                absence_snapshots.append(secure_absence(relative))
            except OSError as exc:
                fail(
                    "E_FILESYSTEM",
                    f"could not verify preparation-state absence {relative}: {exc}",
                )
        verify_no_prefixed_siblings(
            WAVE_STAGING_PARENT_PATH,
            WAVE_STAGING_NAME_PREFIX,
        )
        for relative in required_paths:
            try:
                snapshots.append(secure_read(relative, 8 * 1024 * 1024))
            except OSError as exc:
                fail(
                    "E_FILESYSTEM",
                    f"could not read required file {relative}: {exc}",
                )
        raw = {snapshot.relative: snapshot.data for snapshot in snapshots}
        for path, expected in EXPECTED_RAW.items():
            strict_equal(sha256(raw[path]), expected, "E_LINEAGE", f"rawSha256:{path}")

        documents: dict[str, dict[str, Any]] = {}
        json_paths = (
            DECISION_PATH,
            PREDECESSOR_PATH,
            PROFILE_PATH,
            PROVENANCE_PATH,
            RUNG_TWO_DECISION_PATH,
            RUNG_TWO_RECEIPT_PATH,
            OFFLINE_RESULT_PATH,
            CLASSIFICATIONS_PATH,
            SEMANTIC_RESULT_PATH,
            SEMANTIC_MANIFEST_PATH,
            PATCH_DECISION_PATH,
        )
        for path in json_paths:
            documents[path] = parse_json(raw[path], path)

        binding_scopes = {
            PREDECESSOR_PATH: "decision_without_contentBinding",
            OFFLINE_RESULT_PATH: "result_without_contentBinding",
            CLASSIFICATIONS_PATH: "classifications_without_contentBinding",
            SEMANTIC_RESULT_PATH: "result_without_contentBinding",
            SEMANTIC_MANIFEST_PATH: "manifest_without_contentBinding",
            PATCH_DECISION_PATH: "decision_without_contentBinding",
        }
        for path, expected in EXPECTED_CONTENT.items():
            verify_content_binding(
                documents[path],
                path,
                binding_scopes[path],
                expected,
            )

        profile = documents[PROFILE_PATH]
        strict_equal(
            profile.get("upstreamBaseline", {}).get("goDirective"),
            "1.24.0",
            "E_PROFILE",
            "restrictedProfile.upstreamBaseline.goDirective",
        )
        strict_equal(
            profile.get("buildAndSupplyChain", {}).get("futureCompileOnlyTargets"),
            [
                "android_api_26_through_36_arm64_v8a",
                "macos_14_or_newer_arm64",
            ],
            "E_PROFILE",
            "restrictedProfile.futureCompileOnlyTargets",
        )

        provenance = documents[PROVENANCE_PATH]
        strict_equal(
            provenance.get("checksumDatabaseObservation", {}).get("name"),
            "sum.golang.org",
            "E_IDENTITY",
            "provenance.checksumDatabase.name",
        )
        strict_equal(
        provenance.get("checksumDatabaseObservation", {})
        .get("localVerification", {})
        .get("ed25519SignedTreeVerified"),
            True,
            "E_IDENTITY",
            "provenance.sumdbSignature",
        )
        strict_equal(
        provenance.get("checksumDatabaseObservation", {})
        .get("localVerification", {})
        .get("rfc6962InclusionProofVerified"),
            True,
            "E_IDENTITY",
            "provenance.sumdbInclusion",
        )

        verify_source_archive(raw[SOURCE_ARCHIVE_PATH])
        verify_reader(raw[READER_PATH])
        verify_decision(documents[DECISION_PATH], documents)

        if before_final_barrier is not None:
            before_final_barrier(snapshots)
        for snapshot in snapshots:
            verify_snapshot(snapshot)
        for snapshot in absence_snapshots:
            verify_absence_snapshot(snapshot)
        verify_no_prefixed_siblings(
            WAVE_STAGING_PARENT_PATH,
            WAVE_STAGING_NAME_PREFIX,
        )
        sibling_after = inventory_prefixed_siblings(
            RUNG_THREE,
            "bounded-dependency-source-identity-and-acquisition-decision-v1",
        )
        strict_equal(
            sibling_after,
            sibling_before,
            "E_TOCTOU",
            "decision prefixed sibling final barrier",
        )
    finally:
        close_snapshots([*snapshots, *absence_snapshots])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root used by mutation tests.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        require_isolated_interpreter()
        args = parse_args(sys.argv[1:] if argv is None else argv)
        check(args.root)
    except CheckError as exc:
        print(f"[{exc.code}] {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"[E_INTERNAL] {exc}", file=sys.stderr)
        return 1
    print(
        "G2 Pion dependency wave-one decision v1 passed: exact 19-tuple "
        "preparation bound; acquisition and network remain unauthorized."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
