#!/usr/bin/env python3
"""Check current docs for stale product-boundary wording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import runpy
import sys

if __package__:
    from script.check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )
else:
    from check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )


ROOT = Path(__file__).resolve().parents[1]
PHYSICAL_QR_OBSERVATION_MANIFEST = (
    ROOT / "docs/evidence/physical-qr-pairing-20260719.json"
)
LOCAL_RELEASE_MARKETING_VERSION = "1.0.0"
LOCAL_RELEASE_BUILD_NUMBER = 11
LOCAL_RELEASE_ID = (
    f"aetherlink-{LOCAL_RELEASE_MARKETING_VERSION}"
    f"+{LOCAL_RELEASE_BUILD_NUMBER}-local-v1"
)
LOCAL_RELEASE_CURRENT_DOC = ROOT / "docs/releases/1.0.0-build-11-local-v1.md"
LOCAL_RELEASE_FIXTURE_BUILD_NUMBER = 3
LOCAL_RELEASE_FIXTURE_ID = (
    f"aetherlink-{LOCAL_RELEASE_MARKETING_VERSION}"
    f"+{LOCAL_RELEASE_FIXTURE_BUILD_NUMBER}-local-v1"
)
LOCAL_RELEASE_FIXTURE_DOC = (
    ROOT / "docs/releases/1.0.0-build-3-local-v1.md"
)
# Backward-compatible fixture handle for the focused fixture-mutation tests.
LOCAL_RELEASE_DOC = LOCAL_RELEASE_FIXTURE_DOC
LOCAL_RELEASE_ARCHIVE_DIR = ROOT / "dist/releases" / LOCAL_RELEASE_ID
LOCAL_RELEASE_REPRODUCIBILITY_RESULT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+11-local-v1-two-root-v2.json"
)
LOCAL_RELEASE_REPRODUCIBILITY_CONFIRMATION_RESULT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+11-local-v1-two-root-v2-confirmation.json"
)
MACOS_PACKAGED_LIFECYCLE_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-10-lifecycle-v1.json"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-9-lifecycle-v1.json"
)
MACOS_PACKAGED_LIFECYCLE_RUNNER = (
    ROOT / "script/run_macos_packaged_app_build10_lifecycle_smoke.py"
)
MACOS_PACKAGED_LIFECYCLE_TEST = (
    ROOT / "script/test_run_macos_packaged_app_build10_lifecycle_smoke.py"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RUNNER = (
    ROOT / "script/run_macos_packaged_app_lifecycle_smoke.py"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_TEST = (
    ROOT / "script/test_run_macos_packaged_app_lifecycle_smoke.py"
)
LOCAL_RELEASE_LEDGER = ROOT / "release/version-ledger.tsv"
LOCAL_RELEASE_G0_DECISION = ROOT / "docs/v1/g0/decision-v1.json"
LOCAL_RELEASE_EXPECTED_ZIP_SIZE = 165_378_312
LOCAL_RELEASE_EXPECTED_ZIP_SHA256 = (
    "08505eaefa7f7ef035ad9ff644f1f7e6efa95ef924acccd23d2478e47d92c148"
)
LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE = 12_062
LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256 = (
    "04b4e387e09c9cebc72d72871689472d379435ecdbc288a69e2df99040471812"
)
LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE = 99
LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256 = (
    "9c12f8d1e378527a6f72f7a65410accf5861c4f6c9040ba356c2ba87c4bc9277"
)
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE = 19_745
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256 = (
    "65bb96a93008a077b95608611416e4c41cb91e27cb70d61facd66104748512f4"
)
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_CONFIRMATION_SIZE = 19_744
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_CONFIRMATION_SHA256 = (
    "6da0148640ef5bb97d53369214103a90ea67c499cc2f2cf918591d19f2e87039"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE = 1_313
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256 = (
    "c0ea4dba08e74130f7aaa1e9855121d02459249ff5e6a0fc27cd1b01f46f0ded"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE = 1_311
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256 = (
    "aad796ee3c768e37953f18eeea0e6642107750c3a8c398df798a46e96aabab53"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256 = (
    "76c4e5aebf9824d25bba1c57923f6610b648b64876977f7bc7ddc63afae89c0f"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256 = (
    "069372314018138e4781eceaf60b158798eca99d3ed847d71a0282f63695935b"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256 = (
    "3d7ae7ac5b29236babb239769e7e76f6e51b2fc054accb7d53bd88509aa6ee12"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256 = (
    "4b01ac0161969077b027d44aad9f4f838caa1c14d1f807020ef5bca98d9de138"
)
LOCAL_RELEASE_EXPECTED_SOURCE_ROOT_BYTE_LENGTHS = {
    "build-a": 101,
    "build-b": 109,
}
LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT = 239
LOCAL_RELEASE_EXPECTED_SOURCE_SHA256 = (
    "da7dbf88cba5d5bc9f9d822e0f70fe7b21a9080add5e1b3718c60ef9dc341c84"
)
LOCAL_RELEASE_EXPECTED_SOURCE_HEAD = (
    "8955fb1c25ec483aaedad53793609311337605de"
)
LOCAL_RELEASE_EXPECTED_MEMBER_COUNT = 29
LOCAL_RELEASE_EXPECTED_MACOS_UUID = "415765ED-429A-36D9-BC1A-BAC6DDF18B45"
LOCAL_RELEASE_EXPECTED_MEMBERS = {
    "android/apk/app-release-unsigned.apk": (
        9_568_738,
        "3b1254c17e5891354b7f7062fc9852020a0b905b2c9198b6d1ebc83e7191246c",
    ),
    "android/bundle/app-release.aab": (
        10_660_783,
        "fdf3a8d1834b013bb9458ca2146f087f0bc55e8cf55f5ca7775771fcd7e18707",
    ),
    "android/mapping/mapping.txt": (
        71_726_855,
        "176c55122536220bf69bee28e7954b733ee2675fd6937adb4b034265042537e6",
    ),
    "android/mapping/resources.txt": (
        134_228,
        "c816b0f709eaa66526973bdda6fc0790afdebdfdecfe0a306cda82c742a686d5",
    ),
    "macos/AetherLink.app/Contents/MacOS/AetherLink": (
        18_248_464,
        "143fcd8c54be37e99ce9a3d916967b68bacaa0694c4bbf012c52e5c57b1175ad",
    ),
    "macos/AetherLink.dSYM/Contents/Resources/DWARF/AetherLink": (
        31_260_073,
        "7238ee762f94bbdf74d71579a0fa731eb69b89ba5cf2157ef99a4462c5915e95",
    ),
    "compliance/THIRD_PARTY_LICENSE_INVENTORY.txt": (
        109_725,
        "7bee5eee533db2b7c3ddc88c6e131287a0e641c92fa501bb8e680732da0e92c7",
    ),
    "compliance/release-compliance-metadata-v1.json": (
        94,
        "380bfb4b649035fc1ddbb1a8fa3e8da7bed97aa4910d22d557367332f87e0fdd",
    ),
    "compliance/sbom.spdx.json": (
        252_417,
        "2a940d601c80f4fe21d601b0b81b01f2fcdbc590813f2ec2db1a1fb60bf28f1d",
    ),
    "compliance/third-party-license-inventory-v1.json": (
        411_087,
        "1f97b74e794e5e2b3092cc31ce8c67f634a299989658feca597bc301b67dcda5",
    ),
    "source-files.json": (
        46_545,
        "24dd2812d554cef2dcd09a50dc8e1ed43dccac9891ed47350e6f09e0494bef92",
    ),
}
MACOS_PACKAGED_LIFECYCLE_BUILD_NUMBER = 10
MACOS_PACKAGED_LIFECYCLE_RELEASE_ID = "aetherlink-1.0.0+10-local-v1"
MACOS_PACKAGED_LIFECYCLE_MACOS_UUID = "415765ED-429A-36D9-BC1A-BAC6DDF18B45"
MACOS_PACKAGED_LIFECYCLE_ARCHIVE_SHA256 = (
    "12a4fcccceac74248a0835765876bd9184c845696c83cbf3a6b1fe7613000cc0"
)
MACOS_PACKAGED_LIFECYCLE_MANIFEST_SHA256 = (
    "fcda01d30c61be8182fc294ee76d2583b98ec78fee8b0e6c2ec2f9208ea31741"
)
MACOS_PACKAGED_LIFECYCLE_EXECUTABLE_SHA256 = (
    "75f20fad8d5ce20ecdaa07bcdd526b20cb88f46b50dd1639f11f739858ad6ef4"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT = {
    "app": {
        "buildNumber": MACOS_PACKAGED_LIFECYCLE_BUILD_NUMBER,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": MACOS_PACKAGED_LIFECYCLE_EXECUTABLE_SHA256,
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "uuid": MACOS_PACKAGED_LIFECYCLE_MACOS_UUID,
    },
    "isolation": {
        "afInetBindDeniedByPreflight": True,
        "nonTemporaryWriteDeniedByPreflight": True,
        "profile": "allow-default-deny-network-and-non-temp-writes-v1",
        "runtimeIdentity": (
            "temporary-file-override-with-memory-fallback-allowed"
        ),
        "sandboxed": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "release": {
        "archiveSha256": MACOS_PACKAGED_LIFECYCLE_ARCHIVE_SHA256,
        "manifestSha256": MACOS_PACKAGED_LIFECYCLE_MANIFEST_SHA256,
        "releaseId": MACOS_PACKAGED_LIFECYCLE_RELEASE_ID,
    },
    "runs": [
        {
            "activationPolicy": 0,
            "exitCode": 0,
            "finishedLaunching": True,
            "minimumObservationSeconds": 5.0,
            "observationDeadlineReached": True,
            "ordinal": ordinal,
            "terminationAccepted": True,
        }
        for ordinal in (1, 2)
    ],
    "schemaVersion": 1,
    "state": {
        "expectedApplicationSupportFilesPresentAfterRuns": [True, True],
        "identityFilePresentAfterRuns": [False, False],
        "identityFileUnchangedAcrossRuns": False,
        "runtimeIdentityFileOverrideConfigured": True,
    },
    "status": "passed",
}
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT = {
    **MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT,
    "app": {
        **MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT["app"],
        "buildNumber": 9,
        "executableSha256": (
            "66f4fde6f4ba578f9f6f2a6a4f5fed6f2e27b26e169a868c405fe676535e2c8c"
        ),
        "uuid": "0711F00D-B4B5-316C-A159-2E8BE3FE9FCB",
    },
    "release": {
        "archiveSha256": (
            "e2cbd350bf031d04b6e29054ceb387bbe453e60244b47919c54f6d3c13ba7e1a"
        ),
        "manifestSha256": (
            "56380c239f916ba9d400cc73824ebbda111f61e0baa4d0dc66e8d14e044d05a5"
        ),
        "releaseId": "aetherlink-1.0.0+9-local-v1",
    },
}
LOCAL_RELEASE_TRANSITION_FIXTURE_START = (
    "<!-- aetherlink-release-transition-fixture-v1:start -->"
)
LOCAL_RELEASE_TRANSITION_FIXTURE_END = (
    "<!-- aetherlink-release-transition-fixture-v1:end -->"
)
LOCAL_RELEASE_PROVIDER_FIXTURE_START = (
    "<!-- aetherlink-provider-compatibility-fixture-v1:start -->"
)
LOCAL_RELEASE_PROVIDER_FIXTURE_END = (
    "<!-- aetherlink-provider-compatibility-fixture-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START = (
    "<!-- aetherlink-ollama-exact-version-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END = (
    "<!-- aetherlink-ollama-exact-version-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_START = (
    "<!-- aetherlink-ollama-model-backed-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_END = (
    "<!-- aetherlink-ollama-model-backed-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_START = (
    "<!-- aetherlink-ollama-additional-chat-shape-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_END = (
    "<!-- aetherlink-ollama-additional-chat-shape-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_START = (
    "<!-- aetherlink-ollama-embedding-model-backed-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_END = (
    "<!-- aetherlink-ollama-embedding-model-backed-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_START = (
    "<!-- aetherlink-ollama-embedding-semantic-quality-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_END = (
    "<!-- aetherlink-ollama-embedding-semantic-quality-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_START = (
    "<!-- aetherlink-ollama-embedding-multilingual-semantic-quality-v2:"
    "start -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_END = (
    "<!-- aetherlink-ollama-embedding-multilingual-semantic-quality-v2:"
    "end -->"
)
LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_START = (
    "<!-- aetherlink-ollama-vision-model-backed-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_END = (
    "<!-- aetherlink-ollama-vision-model-backed-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_START = (
    "<!-- aetherlink-ollama-duration-observation-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_END = (
    "<!-- aetherlink-ollama-duration-observation-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_START = (
    "<!-- aetherlink-ollama-live-fault-injection-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_END = (
    "<!-- aetherlink-ollama-live-fault-injection-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER = (
    ROOT / "script/run_ollama_compatibility_matrix.py"
)
LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_RUNNER = (
    ROOT / "script/run_ollama_additional_chat_shape_matrix.py"
)
LOCAL_RELEASE_OLLAMA_MULTILINGUAL_SEMANTIC_RUNNER = (
    ROOT / "script/run_ollama_multilingual_semantic_matrix.py"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaEmbeddingSemanticQualityTests.swift"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_LIVE_ASSERTION_SOURCE = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaBackendTests.swift"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_SOURCE = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaEmbeddingMultilingualSemanticQualityTests.swift"
)
LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE = {
    "android": {
        "developmentBaseline": "0.1.0+1-debug",
        "inPlaceUpgradeSupported": False,
        "requiredAction": "clean-install-and-fresh-pair",
        "sourceApplicationId": "com.localagentbridge.android",
        "stateMigrationSupported": False,
    },
    "currentRelease": {
        "buildNumber": LOCAL_RELEASE_FIXTURE_BUILD_NUMBER,
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "releaseId": LOCAL_RELEASE_FIXTURE_ID,
    },
    "evidenceBoundary": "policy-fixture-only-no-install-or-state-migration-executed",
    "fixtureId": "aetherlink-first-production-lineage-transition-v1",
    "macos": {
        "developmentBaseline": "pre-production-local-ad-hoc",
        "inPlaceUpgradeSupported": False,
        "requiredAction": "clean-install-and-fresh-pair",
        "sourceBundleId": "dev.aetherlink.companion",
        "stateMigrationSupported": False,
    },
    "nMinusOne": {
        "compatibleReleaseId": None,
        "status": "unproven-no-prior-production-release",
        "upgradePathTested": False,
    },
    "productionPredecessor": None,
    "schemaVersion": 1,
}
LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE = {
    "evidenceBoundary": (
        "exact-version-isolated-ollama-empty-catalog-and-existing-chat-plus-"
        "embedding-plus-vision-model-cold-restart-plus-focused-default-tests-"
        "no-lm-studio-live-or-semantic-qualification"
    ),
    "fixtureId": "aetherlink-provider-compatibility-baseline-v1",
    "lmStudio": {
        "access": "runtime_host_only",
        "currentCandidate": {
            "build": 1,
            "qualified": False,
            "releaseDate": "2026-07-22",
            "schemaSmokeObserved": False,
            "version": "0.4.20",
        },
        "localObservation": {
            "channel": "beta",
            "cliCommit": "6041ae0",
            "fallbackModelsEndpoint": {
                "arrayField": "data",
                "httpStatus": 200,
                "objectField": "list",
                "path": "/v1/models",
            },
            "nativeModelsEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/v1/models",
            },
            "version": "0.4.17-beta+3",
        },
        "minimumSupportedVersion": None,
        "officialSource": "https://lmstudio.ai/changelog",
        "previousCandidate": {
            "build": 2,
            "qualified": False,
            "releaseDate": "2026-07-07",
            "schemaSmokeObserved": False,
            "version": "0.4.19",
        },
        "providerId": "lm_studio",
        "releasePolicy": (
            "exact_rc_current_stable_and_previous_verified_versions"
        ),
        "supportStatus": "unresolved-no-minimum-or-full-qualification",
    },
    "ollama": {
        "access": "runtime_host_only",
        "currentCandidate": {
            "darwinArchiveSha256": (
                "5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"
            ),
            "darwinArchiveUrl": (
                "https://github.com/ollama/ollama/releases/download/"
                "v0.32.5/ollama-darwin.tgz"
            ),
            "isolatedAdapterSmoke": {
                "coldStartPassed": True,
                "emptyCatalogPassed": True,
                "restartPassed": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "chatCompletionPassed": True,
                "coldStartPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedEmbeddingModelBackedSmoke": {
                "catalogPopulated": True,
                "coldStartPassed": True,
                "embeddingBatchPassed": True,
                "embeddingShapePassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedVisionModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "coldStartPassed": True,
                "imageAttachmentPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
                "textChatPassed": True,
            },
            "qualified": False,
            "releaseDate": "2026-07-27",
            "schemaSmokeObserved": True,
            "version": "0.32.5",
        },
        "localObservation": {
            "catalogEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/tags",
            },
            "channel": "stable",
            "runningEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/ps",
            },
            "version": "0.32.4",
            "versionEndpoint": {
                "httpStatus": 200,
                "path": "/api/version",
                "versionField": "version",
            },
        },
        "minimumSupportedVersion": None,
        "officialSource": "https://github.com/ollama/ollama/releases",
        "previousCandidate": {
            "darwinArchiveSha256": (
                "15383493225d5e7e7fda052dc103ab4d2835a22eabb41655f1d6302c6d1577bc"
            ),
            "darwinArchiveUrl": (
                "https://github.com/ollama/ollama/releases/download/"
                "v0.32.4/ollama-darwin.tgz"
            ),
            "isolatedAdapterSmoke": {
                "coldStartPassed": True,
                "emptyCatalogPassed": True,
                "restartPassed": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "chatCompletionPassed": True,
                "coldStartPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedEmbeddingModelBackedSmoke": {
                "catalogPopulated": True,
                "coldStartPassed": True,
                "embeddingBatchPassed": True,
                "embeddingShapePassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedVisionModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "coldStartPassed": True,
                "imageAttachmentPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
                "textChatPassed": True,
            },
            "qualified": False,
            "releaseDate": "2026-07-25",
            "schemaSmokeObserved": True,
            "version": "0.32.4",
        },
        "providerId": "ollama",
        "releasePolicy": (
            "exact_rc_current_stable_and_previous_verified_versions"
        ),
        "supportStatus": "unresolved-no-minimum-or-full-qualification",
    },
    "recordedDate": "2026-07-29",
    "schemaVersion": 1,
    "tests": {
        "isolatedOllamaExactVersion": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "isolatedOllamaModelBacked": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "isolatedOllamaEmbeddingModelBacked": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "isolatedOllamaVisionModelBacked": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "lmStudio": {
            "executed": 71,
            "failures": 0,
            "passed": 70,
            "skipped": 1,
        },
        "ollama": {
            "executed": 78,
            "failures": 0,
            "passed": 72,
            "skipped": 6,
        },
        "testKind": (
            "focused-default-plus-opt-in-isolated-exact-version-empty-and-"
            "chat-plus-embedding-plus-vision-model-backed"
        ),
    },
}


class DuplicateJSONKeyError(ValueError):
    pass


LIVE_FAULT_RUNNER_SOURCE_DIGEST_PATTERN = re.compile(
    r"(?m)^(RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256 = \(\n"
    r'    ")[0-9a-f]{64}("\n\))$'
)


def normalized_live_fault_runner_source_sha256(source: str) -> str:
    normalized, replacement_count = (
        LIVE_FAULT_RUNNER_SOURCE_DIGEST_PATTERN.subn(
            lambda match: (
                match.group(1)
                + ("0" * 64)
                + match.group(2)
            ),
            source,
        )
    )
    if replacement_count != 1:
        raise ValueError(
            "runner must contain exactly one canonical live-fault source "
            "SHA-256 declaration"
        )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def exact_json_values_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(
                exact_json_values_equal(actual[key], expected[key])
                for key in expected
            )
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                exact_json_values_equal(actual_value, expected_value)
                for actual_value, expected_value in zip(actual, expected)
            )
        )
    return actual == expected


@dataclass(frozen=True)
class DocsRule:
    name: str
    pattern: re.Pattern[str]
    guidance: str


@dataclass(frozen=True)
class DocsContract:
    name: str
    required_patterns: tuple[re.Pattern[str], ...]
    guidance: str


@dataclass(frozen=True)
class DocsFileContract:
    name: str
    target: str
    required_patterns: tuple[re.Pattern[str], ...]
    guidance: str


RULES = (
    DocsRule(
        "companion-runtime",
        re.compile(r"\bcompanion runtime\b", re.IGNORECASE),
        "Use AetherLink Runtime, trusted runtime, or runtime host.",
    ),
    DocsRule(
        "runtime-server-hybrid",
        re.compile(r"\bruntime/server\b", re.IGNORECASE),
        "Use runtime host, trusted runtime, or runtime target.",
    ),
    DocsRule(
        "server-targets",
        re.compile(r"\bserver targets?\b", re.IGNORECASE),
        "Use runtime targets unless describing an external infrastructure service.",
    ),
    DocsRule(
        "finished-e2e-transport-claim",
        re.compile(r"\bauthenticated end-to-end encrypted session\b", re.IGNORECASE),
        "Do not imply production transport encryption is complete.",
    ),
    DocsRule(
        "desktop-host-copy",
        re.compile(r"\b(this Mac|Mac alone|this computer|paired computer)\b", re.IGNORECASE),
        "Use runtime host wording so docs stay OS-neutral.",
    ),
    DocsRule(
        "runtime-companion-label",
        re.compile(r"\bAetherLink Runtime companion\b", re.IGNORECASE),
        "Use AetherLink Runtime.",
    ),
    DocsRule(
        "visible-app-language-system-option",
        re.compile(
            r"\b(?:language selector|app-language|app language|language support)\b.*"
            r"\bSystem/Device language\b",
            re.IGNORECASE,
        ),
        "Use the localized Follow system language setting name rather than the stale System/Device language label.",
    ),
    DocsRule(
        "stale-remote-route-diagnostics-title",
        re.compile(r"\bRemote Route Diagnostics\b", re.IGNORECASE),
        "Use Advanced Connection Setup or Connection Setup to match the current runtime UI.",
    ),
    DocsRule(
        "stale-route-host-copy",
        re.compile(r"\broute host(?:/port| and port)?\b", re.IGNORECASE),
        "Use connection address and port.",
    ),
)


HYGIENE_TARGETS = (
    "README.md",
    "apps/android/README.md",
    "apps/macos/README.md",
    "docs/architecture.md",
    "docs/connection-overlay.md",
    "docs/handoff.md",
    "docs/mvp-v0.1.md",
    "docs/protocol.md",
    "docs/qa-evidence.md",
    "docs/releases/1.0.0-build-1-local-v1.md",
    "docs/releases/1.0.0-build-2-local-v1.md",
    "docs/releases/1.0.0-build-3-local-v1.md",
    "docs/releases/1.0.0-build-4-local-v1.md",
    "docs/releases/1.0.0-build-5-local-v1.md",
    "docs/releases/1.0.0-build-6-local-v1.md",
    "docs/releases/1.0.0-build-7-local-v1.md",
    "docs/releases/1.0.0-build-8-local-v1.md",
    "docs/releases/1.0.0-build-9-local-v1.md",
    "docs/releases/1.0.0-build-10-local-v1.md",
    "docs/releases/1.0.0-build-11-local-v1.md",
    "docs/roadmap.md",
    "docs/security.md",
    "examples/README.md",
)

CONTRACT_TARGETS = tuple(
    target for target in HYGIENE_TARGETS if target != "docs/handoff.md"
)

CONTRACTS = (
    DocsContract(
        "runtime-mediated-backends",
        (
            re.compile(r"\bclient\b.*\b(?:must not|never)\b.*\b(?:call|connects?\s+directly\s+to)\b.*\bOllama\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bclient\b.*\b(?:must not|never)\b.*\b(?:call|connects?\s+directly\s+to)\b.*\bLM Studio\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bAetherLink Runtime\b|\bruntime host\b", re.IGNORECASE),
        ),
        "Docs must preserve the boundary that clients talk to AetherLink Runtime, never directly to Ollama or LM Studio.",
    ),
    DocsContract(
        "qr-overlay-route-model",
        (
            re.compile(r"\bQR-only\b|\bQR\b.*\b(?:pair|route|refresh)", re.IGNORECASE | re.DOTALL),
            re.compile(r"\broute\.refresh\b", re.IGNORECASE),
            re.compile(r"\bprivate overlay\b|\bremote P2P\b|\bNAT traversal\b", re.IGNORECASE),
            re.compile(r"\brelay_secret\b.*\brelay_expires_at\b.*\brelay_nonce\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must describe QR-first pairing/route refresh and remote overlay or relay material instead of fixed-IP reconnect.",
    ),
    DocsContract(
        "runtime-owned-chat-history",
        (
            re.compile(r"\bruntime-owned\b.*\bchat\b|\bchat\b.*\bruntime-owned\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bchat\.sessions\.list\b", re.IGNORECASE),
            re.compile(r"\bchat\.messages\.list\b", re.IGNORECASE),
            re.compile(r"\b(?:redact|redacted|omits?)\b.*\bmessage bodies\b|\bmessage bodies\b.*\b(?:redact|redacted|omits?)\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must keep runtime-owned chat history and client-cache redaction explicit.",
    ),
    DocsContract(
        "five-language-locale-handoff",
        (
            re.compile(r"\bEnglish, Korean, Japanese, Simplified Chinese, and French\b", re.IGNORECASE),
            re.compile(r"\bchat\.send\.locale\b|\blocale handoff\b|\bruntime request locale\b", re.IGNORECASE),
        ),
        "Docs must keep the five-language launch set and runtime locale handoff visible.",
    ),
    DocsContract(
        "runtime-mediated-memory-embedding",
        (
            re.compile(r"\bmemory\b.*\bruntime-(?:owned|mediated)|\bruntime-(?:owned|mediated)\b.*\bmemory\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bembedding models?\b.*\bseparate(?:ly)?\b|\bseparate\b.*\bembedding models?\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bselected embedding model\b|\bMemory indexing model\b", re.IGNORECASE),
        ),
        "Docs must keep memory runtime-mediated and embedding model selection separate from chat model selection.",
    ),
    DocsContract(
        "runtime-mediated-attachments",
        (
            re.compile(r"\battachments?\b.*\bruntime-(?:mediated|side)\b|\bruntime-(?:mediated|side)\b.*\battachments?\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bvision\b.*\bgating\b|\bgating\b.*\bvision\b|\bimage/vision gating\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bdocument ingestion\b|\bdocument attachments?\b", re.IGNORECASE),
        ),
        "Docs must distinguish current runtime-mediated attachment support from remaining physical QA and future ingestion hardening.",
    ),
    DocsContract(
        "future-tools-runtime-only",
        (
            re.compile(r"\bMCP\b.*\b(?:roadmap|future|not v0\.1)\b|\b(?:roadmap|future|not v0\.1)\b.*\bMCP\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bweb search\b.*\b(?:roadmap|future|not v0\.1)\b|\b(?:roadmap|future|not v0\.1)\b.*\bweb search\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\b(?:MCP|web search)\b.*\b(?:AetherLink Runtime|runtime host)\b|\b(?:AetherLink Runtime|runtime host)\b.*\b(?:MCP|web search)\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bclient\b.*\b(?:does not|must not|never)\b.*\b(?:MCP|web search)\b|\b(?:MCP|web search)\b.*\bclient\b.*\b(?:does not|must not|never)\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must keep MCP and web search as future runtime-side features, never v0.1 client capabilities.",
    ),
)

FILE_CONTRACTS = (
    DocsFileContract(
        "local-release-qualification-boundary",
        "docs/releases/1.0.0-build-11-local-v1.md",
        (
            re.compile(
                r"\bStatus:\s*local release-engineering candidate,\s*not a production release\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bAndroid Debug\b.*\b0\.1\.0\+1\b.*\bnon-migratable\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bN/N-1\b.*\bnot yet qualified\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bAndroid channel\b.*\brollback\b.*\bhigher\s+`versionCode`",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bcurrent\s+or\s+immediately\s+previous\b.*\bsigned DMG\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\b08505eaefa7f7ef035ad9ff644f1f7e6efa95ef924acccd23d2478e47d92c148\b"
            ),
            re.compile(
                r"\b04b4e387e09c9cebc72d72871689472d379435ecdbc288a69e2df99040471812\b"
            ),
            re.compile(
                r"\b9c12f8d1e378527a6f72f7a65410accf5861c4f6c9040ba356c2ba87c4bc9277\b"
            ),
            re.compile(
                r"\b65bb96a93008a077b95608611416e4c41cb91e27cb70d61facd66104748512f4\b"
            ),
            re.compile(
                r"\b101-\s+and\s+109-byte source roots\b",
                re.IGNORECASE,
            ),
        ),
        "The local release record must retain its exact artifact identity, non-production boundary, transition limits, and rollback posture.",
    ),
    DocsFileContract(
        "canonical-session-handoff",
        "docs/handoff.md",
        (
            re.compile(r"\bcanonical first document\b", re.IGNORECASE),
            re.compile(r"\bintentionally dirty\b.*\bworktree\b|\bworktree\b.*\bintentionally dirty\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bAndroid device state at handoff:\s*disconnected\b", re.IGNORECASE),
            re.compile(r"\bphysical\b.*\bcamera scan\b.*\bNo URI or deep-link injection\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bPairingQr\b.*\bBonjourDiscovery\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\blocal_diagnostic\b.*\brelease\b.*\bremote-required\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bCurrent Truth Versus Historical Evidence\b", re.IGNORECASE),
            re.compile(r"\bUI Callback Wiring Matrix\b", re.IGNORECASE),
            re.compile(r"\bPairingView\b.*\bmain\b.*\brequestPairingForUserInterface\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bPairing\b.*\bnested Connection Recovery\b.*\brequestRemotePairingForUserInterface\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bDebug And Release Evidence Matrix\b", re.IGNORECASE),
            re.compile(r"\bphysical-qr-pairing-20260719\.json\b", re.IGNORECASE),
            re.compile(r"\bprogress-v8\.json\b.*\bdecision-v6\.json\b.*\bhandoff-v9\.json\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bimplementationAuthorized=false\b.*\bruntimeNetworkIOAllowed=false\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bNot Yet Proven\b", re.IGNORECASE),
            re.compile(r"\bP2P/NAT\b.*\bPhase B\b.*\bproduction\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bGPT-5\.6 Sol\b", re.IGNORECASE),
            re.compile(r"\bHandoff Maintenance Rule\b", re.IGNORECASE),
        ),
        "docs/handoff.md must remain a current, bounded, and executable continuation contract rather than a stale narrative snapshot.",
    ),
    DocsFileContract(
        "roadmap-qr-history-supersession",
        "docs/roadmap.md",
        (
            re.compile(r"\bReading rule:.*\bHistorical Checkpoint\b.*\bcannot override\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bHistorical Checkpoint: macOS Pairing QR Recovery And Bounded Route Preparation \(Superseded\)", re.IGNORECASE),
            re.compile(r"\bProduct result at that checkpoint:", re.IGNORECASE),
            re.compile(r"\bHistorical Checkpoint: Cross-Platform Readiness UI Pass \(Superseded\)", re.IGNORECASE),
            re.compile(r"\blater physical debug result\b.*\bdoes not\b.*\bhistorical aggregate\b", re.IGNORECASE | re.DOTALL),
        ),
        "Historical QR and readiness checkpoints must remain explicitly superseded by the current handoff and roadmap sections.",
    ),
    DocsFileContract(
        "protocol-locale-contract",
        "docs/protocol.md",
        (
            re.compile(r"\bchat\.send\.locale\b", re.IGNORECASE),
            re.compile(r"\bEnglish, Korean, Japanese, Simplified Chinese, and French\b", re.IGNORECASE),
        ),
        "docs/protocol.md must directly define the runtime locale handoff and the five-language launch set.",
    ),
    DocsFileContract(
        "protocol-runtime-memory-client-boundary",
        "docs/protocol.md",
        (
            re.compile(r"\bCurrent clients\b.*\b(?:should not|do not)\b.*\bcached memory\b.*\bchat\.send\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bCompatibility clients?\b", re.IGNORECASE),
            re.compile(r"\bruntime-owned memory store\b|\bruntime-owned memory\b", re.IGNORECASE),
        ),
        "docs/protocol.md must distinguish current client behavior from stale compatibility memory stripping.",
    ),
    DocsFileContract(
        "readme-cross-platform-language-verification",
        "README.md",
        (
            re.compile(r"\bAndroid and macOS five-language app-language verification\b", re.IGNORECASE),
            re.compile(r"\bchat\.send\.locale\b", re.IGNORECASE),
        ),
        "README.md must keep cross-platform language verification and chat.send.locale handoff visible outside historical progress logs.",
    ),
    DocsFileContract(
        "readme-no-device-quality-caveats",
        "README.md",
        (
            re.compile(r"\bno-device gate\b", re.IGNORECASE),
            re.compile(r"\bdoes not require a connected phone\b", re.IGNORECASE),
            re.compile(r"\bphysical Android rendering\b", re.IGNORECASE),
            re.compile(r"\bTalkBack\b.*\bVoiceOver\b|\bVoiceOver\b.*\bTalkBack\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\boptical/camera QR\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat or cancel\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "README.md must keep no-device quality caveats explicit for physical rendering, screen-reader traversal, optical QR, live provider chat/cancel, and real different-network connectivity.",
    ),
    DocsFileContract(
        "qa-current-rule-no-device-quality-caveats",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bCurrent Rule\b", re.IGNORECASE),
            re.compile(r"\bNo-device evidence does not prove\b", re.IGNORECASE),
            re.compile(r"\bphysical Android rendering\b", re.IGNORECASE),
            re.compile(r"\bTalkBack\b.*\bVoiceOver\b|\bVoiceOver\b.*\bTalkBack\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\boptical/camera QR\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat/cancel\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md Current Rule must keep no-device quality caveats explicit before historical evidence entries.",
    ),
    DocsFileContract(
        "qa-owner-device-scoping-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Runtime Owner-Device History And Memory Scoping\b", re.IGNORECASE),
            re.compile(r"\bowner_device_id\b", re.IGNORECASE),
            re.compile(r"\btestAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeMemoryStoreScopesEntriesByOwnerDevice\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep the latest runtime history/memory owner-device scoping proof visible.",
    ),
    DocsFileContract(
        "qa-android-archived-chat-composer-cleanup",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Archived Chat Composer Cleanup\b", re.IGNORECASE),
            re.compile(r"\barchiveActiveChatClearsNoActiveDraftAndPendingAttachments\b", re.IGNORECASE),
            re.compile(r"\barchiveAllChatsClearsNoActiveDraftAndPendingAttachments\b", re.IGNORECASE),
            re.compile(r"\bsanitizedDropsArchivedSessionComposerDrafts\b", re.IGNORECASE),
            re.compile(r"\bAndroid transient attachment cleanup on chat lifecycle exits\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep archived chat composer cleanup proof visible.",
    ),
    DocsFileContract(
        "qa-android-runtime-transcript-loading-state",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Runtime Transcript Loading State\b", re.IGNORECASE),
            re.compile(r"\bchatComposerHintExplainsActiveTranscriptLoadingLockout\b", re.IGNORECASE),
            re.compile(r"\bopeningRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShowsLocalizedLoadingStateWhileRuntimeTranscriptLoads\b", re.IGNORECASE),
            re.compile(r"\bAndroid runtime transcript loading state\b", re.IGNORECASE),
            re.compile(r"\bAndroid runtime transcript lifecycle mutation lockout\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android runtime transcript loading proof visible.",
    ),
    DocsFileContract(
        "qa-macos-route-material-redaction",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Route Material Diagnostic Redaction\b", re.IGNORECASE),
            re.compile(r"\btestActivityTechnicalDetailsRedactRouteSecrets\b", re.IGNORECASE),
            re.compile(r"\btestRouteDiagnosticDisclosureRedactsSensitiveDetails\b", re.IGNORECASE),
            re.compile(r"\bmacOS route material diagnostic redaction\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep macOS route material diagnostic redaction proof visible.",
    ),
    DocsFileContract(
        "progress-macos-thinking-runtime-history-evidence",
        "docs/progress.md",
        (
            re.compile(r"\bmacOS Thinking Copy And Sidebar Header Accessibility\b", re.IGNORECASE),
            re.compile(r"\bRuntime History Inspector transcript reasoning\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep macOS Runtime History Thinking/reasoning evidence visible.",
    ),
    DocsFileContract(
        "qa-macos-thinking-runtime-history-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Thinking Copy And Sidebar Header Accessibility\b", re.IGNORECASE),
            re.compile(r"\bRuntime History Inspector transcript reasoning\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep macOS Runtime History Thinking/reasoning proof visible.",
    ),
    DocsFileContract(
        "progress-android-preference-system-detail-guard",
        "docs/progress.md",
        (
            re.compile(r"\bAndroid Appearance System Detail Polish\b", re.IGNORECASE),
            re.compile(r"\bR\.string\.appearance_system_detail\b", re.IGNORECASE),
            re.compile(r"\blanguage_follow_system_detail\b", re.IGNORECASE),
            re.compile(r"\bAndroid appearance system detail copy\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep Android Settings system appearance/language detail guard evidence visible.",
    ),
    DocsFileContract(
        "qa-android-preference-system-detail-guard",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Appearance System Detail Polish\b", re.IGNORECASE),
            re.compile(r"\bsettingsPreferenceRowsExposeSelectedStateToAccessibility\b", re.IGNORECASE),
            re.compile(r"\blanguage_follow_system_detail\b", re.IGNORECASE),
            re.compile(r"\bAndroid Settings Appearance\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android Settings system appearance/language detail proof visible.",
    ),
    DocsFileContract(
        "progress-android-static-thinking-state-evidence",
        "docs/progress.md",
        (
            re.compile(r"\bAndroid Static Thinking Accessibility\b", re.IGNORECASE),
            re.compile(r"\bassistant_reasoning_state_shown\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\bAndroid short reasoning static accessibility state\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep Android short Thinking static accessibility evidence visible.",
    ),
    DocsFileContract(
        "qa-android-static-thinking-state-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Static Thinking Accessibility\b", re.IGNORECASE),
            re.compile(r"\bassistant_reasoning_state_shown\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\bAndroid short reasoning static accessibility state\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android short Thinking static accessibility proof visible.",
    ),
    DocsFileContract(
        "connection-overlay-production-bootstrap-verifier",
        "docs/connection-overlay.md",
        (
            re.compile(r"\bscript/verify_pairing_qr\.swift\b", re.IGNORECASE),
            re.compile(r"--require-production-bootstrap\b", re.IGNORECASE),
            re.compile(r"\bruntime_public_key\b.*\broute_token\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"--require-relay-route\b", re.IGNORECASE),
            re.compile(r"--forbid-direct-endpoint\b", re.IGNORECASE),
        ),
        "docs/connection-overlay.md must document the QR verifier flags that prove production bootstrap fields, relay route material, and no direct endpoint fallback.",
    ),
    DocsFileContract(
        "protocol-product-qr-bootstrap-contract",
        "docs/protocol.md",
        (
            re.compile(r"\bNormal product client scans\b.*\bruntime_public_key\b.*\broute_token\b.*\bremote route material\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bIdentity-only QR\b.*\bcompatibility or diagnostic\b.*\bnormal product scan path\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bnormal product QR scans require\b.*\bruntime_public_key\b", re.IGNORECASE | re.DOTALL),
        ),
        "docs/protocol.md must state that normal product QR scans require runtime public key, route token, and remote route material while identity-only QR remains diagnostic/compatibility only.",
    ),
    DocsFileContract(
        "roadmap-no-device-live-proof-split",
        "docs/roadmap.md",
        (
            re.compile(r"\bContinue expanding smoke tests while separating no-device gate coverage from live proof gaps\b", re.IGNORECASE),
            re.compile(r"\bNamed no-device/default-gate coverage currently includes\b", re.IGNORECASE),
            re.compile(r"\bLive/physical proof that remains separate\b", re.IGNORECASE),
            re.compile(r"\bphysical Android QR scan\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat/cancel\b", re.IGNORECASE),
            re.compile(r"\bproduction relay allocation\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "docs/roadmap.md must separate named no-device/default-gate coverage from live physical or production proof gaps.",
    ),
)


PROGRESS_DOC = ROOT / "docs/progress.md"
QA_EVIDENCE_DOC = ROOT / "docs/qa-evidence.md"
QA_CURRENT_RELEASE_READBACK_MARKER = (
    "The Build 11 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs."
)
QA_STALE_RELEASE_READBACK_MARKERS = (
    "The current build 6 archive includes the terminal-less EOF fix and the "
    "settled provider-quality source snapshot.",
    "The current build 5 archive includes the terminal-less EOF fix and the "
    "settled provider-quality source snapshot.",
    "The current build 3 archive includes the terminal-less EOF fix and the "
    "settled provider-quality source snapshot.",
    "The existing local release archive predates the terminal-less EOF fix"
)
RELEASE_READBACK_COMMAND_DOCS = (
    PROGRESS_DOC,
    QA_EVIDENCE_DOC,
)


def target_files() -> list[Path]:
    return [path for path in (ROOT / target for target in HYGIENE_TARGETS) if path.is_file()]


def current_release_qa_evidence_failures(
    document_text: str | None = None,
) -> list[str]:
    if document_text is None:
        if not QA_EVIDENCE_DOC.is_file():
            return ["docs/qa-evidence.md: missing current QA evidence file."]
        document_text = QA_EVIDENCE_DOC.read_text(
            encoding="utf-8",
            errors="replace",
        )
    normalized_text = " ".join(document_text.split())
    failures: list[str] = []
    if QA_CURRENT_RELEASE_READBACK_MARKER not in normalized_text:
        failures.append(
            "docs/qa-evidence.md: Build 11 current-source readback marker is "
            "missing."
        )
    for stale_marker in QA_STALE_RELEASE_READBACK_MARKERS:
        if stale_marker in normalized_text:
            failures.append(
                "docs/qa-evidence.md: stale current-release EOF readback claim "
                "must not remain current."
            )
    return failures


def release_readback_command_mode_failures(
    document_text_by_path: dict[str, str] | None = None,
) -> list[str]:
    failures: list[str] = []
    release_pattern = re.compile(
        r"--archive-dir\s+dist/releases/"
        r"aetherlink-[0-9]+\.[0-9]+\.[0-9]+\+"
        r"(?P<build>[1-9][0-9]*)-local-v1"
    )
    historical_pattern = re.compile(
        r"(?<![\w-])--historical(?![\w-])"
    )

    for path in RELEASE_READBACK_COMMAND_DOCS:
        relative = str(path.relative_to(ROOT))
        if document_text_by_path is None:
            try:
                document_text = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError as error:
                failures.append(
                    f"{relative}: cannot inspect release readback commands: "
                    f"{error}"
                )
                continue
        else:
            document_text = document_text_by_path.get(relative, "")

        for line_number, line in enumerate(document_text.splitlines(), 1):
            if "check_release_artifact_archive.py" not in line:
                continue
            match = release_pattern.search(line)
            if match is None:
                failures.append(
                    f"{relative}:{line_number}: release readback command must "
                    "name a canonical versioned archive directory on the same "
                    "line."
                )
                continue

            build_number = int(match.group("build"))
            historical_mode = historical_pattern.search(line) is not None
            if build_number < LOCAL_RELEASE_BUILD_NUMBER and not historical_mode:
                failures.append(
                    f"{relative}:{line_number}: historical Build "
                    f"{build_number} release readback command requires "
                    "`--historical`."
                )
            elif (
                build_number == LOCAL_RELEASE_BUILD_NUMBER
                and historical_mode
            ):
                failures.append(
                    f"{relative}:{line_number}: current Build "
                    f"{build_number} release readback command must not use "
                    "`--historical`."
                )
            elif build_number > LOCAL_RELEASE_BUILD_NUMBER:
                failures.append(
                    f"{relative}:{line_number}: release readback command names "
                    f"future Build {build_number}; current Build is "
                    f"{LOCAL_RELEASE_BUILD_NUMBER}."
                )

    return failures


def contract_text() -> str:
    chunks: list[str] = []
    for target in CONTRACT_TARGETS:
        path = ROOT / target
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def file_contract_text(target: str) -> str:
    path = ROOT / target
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def embedded_json_fixture_body(
    document_text: str,
    *,
    start_marker: str,
    end_marker: str,
    fixture_label: str,
) -> tuple[str | None, list[str]]:
    pattern = re.compile(
        re.escape(start_marker)
        + r"\n```json\n(?P<body>.*?)\n```\n"
        + re.escape(end_marker),
        re.DOTALL,
    )
    matches = list(pattern.finditer(document_text))
    if (
        len(matches) != 1
        or document_text.count(start_marker) != 1
        or document_text.count(end_marker) != 1
    ):
        return (
            None,
            [
                "docs/releases/1.0.0-build-3-local-v1.md: expected exactly "
                f"one canonical {fixture_label} fixture block."
            ],
        )

    fixture_body = matches[0].group("body")

    try:
        json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, DuplicateJSONKeyError) as error:
        return (
            None,
            [
                "docs/releases/1.0.0-build-3-local-v1.md: invalid "
                f"{fixture_label} fixture JSON: {error}"
            ],
        )

    return fixture_body, []


def local_release_transition_fixture_failures(
    document_text: str,
) -> list[str]:
    failures: list[str] = []
    fixture_body, parse_failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_TRANSITION_FIXTURE_START,
        end_marker=LOCAL_RELEASE_TRANSITION_FIXTURE_END,
        fixture_label="release-transition",
    )
    if fixture_body is None:
        return parse_failures

    expected_body = json.dumps(
        LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: release-transition "
            "fixture must match the canonical first-lineage schema, exact "
            "values, JSON types, and key order."
        )

    try:
        ledger_bytes = LOCAL_RELEASE_LEDGER.read_bytes()
        ledger_entries = parse_release_version_ledger(ledger_bytes)
        fixture_entries = [
            entry
            for entry in ledger_entries
            if entry.build_number == LOCAL_RELEASE_FIXTURE_BUILD_NUMBER
            and entry.marketing_version == LOCAL_RELEASE_MARKETING_VERSION
        ]
        if len(fixture_entries) != 1:
            raise LedgerError(
                "expected exactly one build 3 fixture entry in the release ledger"
            )
        fixture_entry = fixture_entries[0]
        ledger_fixture = {
            "buildNumber": fixture_entry.build_number,
            "marketingVersion": fixture_entry.marketing_version,
            "releaseId": (
                f"aetherlink-{fixture_entry.marketing_version}"
                f"+{fixture_entry.build_number}-local-v1"
            ),
        }
    except (OSError, LedgerError) as error:
        failures.append(
            "release/version-ledger.tsv: cannot cross-check local release "
            f"transition fixture: {error}"
        )
    else:
        if json.dumps(
            ledger_fixture,
            sort_keys=True,
        ) != json.dumps(
            LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"],
            sort_keys=True,
        ):
            failures.append(
                "release/version-ledger.tsv: build 3 entry differs from the "
                "historical local release transition fixture."
            )

    try:
        g0 = json.loads(
            LOCAL_RELEASE_G0_DECISION.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        g0_projection = {
            "androidCurrentApplicationId": (
                g0["releasePolicy"]["android"]["currentApplicationId"]
            ),
            "androidDebugTransition": (
                g0["releasePolicy"]["android"]["currentDebugDataMigration"]
            ),
            "androidProductionApplicationId": (
                g0["releasePolicy"]["android"]["productionApplicationId"]
            ),
            "macosCurrentBundleId": (
                g0["releasePolicy"]["macos"]["currentBundleId"]
            ),
            "macosProductionBundleId": (
                g0["releasePolicy"]["macos"]["productionBundleId"]
            ),
            "marketingVersion": g0["productScope"]["releaseVersion"],
            "policyMarketingVersion": (
                g0["releasePolicy"]["versioning"]["marketingVersion"]
            ),
            "wireCompatibility": (
                g0["releasePolicy"]["compatibility"]["wireAndService"]
            ),
        }
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
        KeyError,
        TypeError,
    ) as error:
        failures.append(
            "docs/v1/g0/decision-v1.json: cannot cross-check local release "
            f"transition fixture: {error}"
        )
    else:
        expected_g0_projection = {
            "androidCurrentApplicationId": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["android"][
                    "sourceApplicationId"
                ]
            ),
            "androidDebugTransition": (
                "unsupported_clean_install_and_fresh_pair_required"
            ),
            "androidProductionApplicationId": None,
            "macosCurrentBundleId": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["macos"][
                    "sourceBundleId"
                ]
            ),
            "macosProductionBundleId": None,
            "marketingVersion": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"][
                    "marketingVersion"
                ]
            ),
            "policyMarketingVersion": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"][
                    "marketingVersion"
                ]
            ),
            "wireCompatibility": "n_and_n_minus_1",
        }
        if json.dumps(
            g0_projection,
            sort_keys=True,
        ) != json.dumps(
            expected_g0_projection,
            sort_keys=True,
        ):
            failures.append(
                "docs/v1/g0/decision-v1.json: non-security release version, "
                "identity, migration, or compatibility fields differ from "
                "the local transition fixture."
            )

    return failures


def local_release_provider_fixture_failures(
    document_text: str,
) -> list[str]:
    failures: list[str] = []
    fixture_body, parse_failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_PROVIDER_FIXTURE_START,
        end_marker=LOCAL_RELEASE_PROVIDER_FIXTURE_END,
        fixture_label="provider-compatibility",
    )
    if fixture_body is None:
        return parse_failures

    expected_body = json.dumps(
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "provider-compatibility fixture must match the canonical "
            "recorded-date schema, exact values, JSON types, and key order."
        )

    try:
        g0 = json.loads(
            LOCAL_RELEASE_G0_DECISION.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        providers = g0["productScope"]["providers"]
        if not isinstance(providers, list):
            raise TypeError("productScope.providers must be an array")
        g0_projection = sorted(
            (
                {
                    "access": provider["access"],
                    "minimumSupportedVersion": (
                        provider["minimumSupportedVersion"]
                    ),
                    "providerId": provider["id"],
                    "releasePolicy": provider["releasePolicy"],
                }
                for provider in providers
            ),
            key=lambda provider: provider["providerId"],
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
        KeyError,
        TypeError,
    ) as error:
        failures.append(
            "docs/v1/g0/decision-v1.json: cannot cross-check local "
            f"provider-compatibility fixture: {error}"
        )
    else:
        expected_projection = sorted(
            (
                {
                    "access": provider["access"],
                    "minimumSupportedVersion": (
                        provider["minimumSupportedVersion"]
                    ),
                    "providerId": provider["providerId"],
                    "releasePolicy": provider["releasePolicy"],
                }
                for provider in (
                    LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"],
                    LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["lmStudio"],
                )
            ),
            key=lambda provider: provider["providerId"],
        )
        if json.dumps(g0_projection, sort_keys=True) != json.dumps(
            expected_projection,
            sort_keys=True,
        ):
            failures.append(
                "docs/v1/g0/decision-v1.json: non-security provider IDs, "
                "runtime-host access, minimum versions, or release policies "
                "differ from the local provider-compatibility fixture."
            )

    return failures


def local_release_ollama_runner_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START,
        end_marker=LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END,
        fixture_label="ollama-exact-version-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: missing exact-version runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        runner_id = runner["RUNNER_ID"]
        recorded_date = runner["RECORDED_DATE"]
        evidence_boundary = runner["EVIDENCE_BOUNDARY"]
        candidates = runner["EXACT_CANDIDATES"]
        live_test_filter = runner["LIVE_TEST_FILTER"]
        default_port = runner["DEFAULT_OLLAMA_PORT"]
        if not isinstance(runner_id, str) or not runner_id:
            raise TypeError("RUNNER_ID must be a non-empty string")
        if not isinstance(recorded_date, str) or not recorded_date:
            raise TypeError("RECORDED_DATE must be a non-empty string")
        if not isinstance(evidence_boundary, str) or not evidence_boundary:
            raise TypeError("EVIDENCE_BOUNDARY must be a non-empty string")
        if type(candidates) is not tuple or len(candidates) != 2:
            raise TypeError("EXACT_CANDIDATES must contain exactly two rows")
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionEmptyCatalogCompatibility"
        ):
            raise ValueError("LIVE_TEST_FILTER differs from the canonical test")
        if type(default_port) is not int or default_port != 11_434:
            raise ValueError("DEFAULT_OLLAMA_PORT differs from 11434")

        versions: list[dict[str, object]] = []
        for candidate in candidates:
            if type(candidate) is not dict:
                raise TypeError("candidate rows must be objects")
            archive_sha256 = candidate["archiveSha256"]
            archive_url = candidate["archiveUrl"]
            version = candidate["version"]
            if not all(
                isinstance(value, str) and value
                for value in (archive_sha256, archive_url, version)
            ):
                raise TypeError("candidate strings must be non-empty")
            versions.append(
                {
                    "archiveSha256": archive_sha256,
                    "archiveUrl": archive_url,
                    "coldStart": {
                        "adapterTestPassed": True,
                        "endpointUnavailableAfterStop": True,
                    },
                    "restart": {
                        "adapterTestPassed": True,
                        "endpointUnavailableAfterStop": True,
                    },
                    "testRuns": 2,
                    "version": version,
                }
            )
        expected_fixture = {
            "evidenceBoundary": evidence_boundary,
            "fixtureId": runner_id,
            "recordedDate": recorded_date,
            "schemaVersion": 1,
            "versions": versions,
        }
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            f"cannot derive canonical runner fixture: {error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-exact-version-run fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        versions,
    ):
        if (
            provider_candidate["version"] != runner_candidate["version"]
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate["archiveSha256"]
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate["archiveUrl"]
            or provider_candidate["isolatedAdapterSmoke"]
            != {
                "coldStartPassed": runner_candidate["coldStart"][
                    "adapterTestPassed"
                ],
                "emptyCatalogPassed": True,
                "restartPassed": runner_candidate["restart"][
                    "adapterTestPassed"
                ],
                "stoppedEndpointUnavailable": (
                    runner_candidate["coldStart"][
                        "endpointUnavailableAfterStop"
                    ]
                    and runner_candidate["restart"][
                        "endpointUnavailableAfterStop"
                    ]
                ),
            }
        ):
            failures.append(
                "provider-compatibility fixture and exact-version runner "
                "fixture differ in Ollama version, archive identity, or "
                "isolated adapter result."
            )
            break

    return failures


def local_release_ollama_model_backed_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_START,
        end_marker=LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_END,
        fixture_label="ollama-model-backed-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: missing model-backed runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        live_test_filter = runner["MODEL_BACKED_LIVE_TEST_FILTER"]
        fixture_builder = runner["recorded_model_backed_fixture"]
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledChatModelCompatibility"
        ):
            raise ValueError(
                "MODEL_BACKED_LIVE_TEST_FILTER differs from the canonical test"
            )
        if not callable(fixture_builder):
            raise TypeError("recorded_model_backed_fixture must be callable")
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError("recorded model-backed fixture must be an object")
        if (
            expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get("modelNameRetained")
            is not False
            or expected_fixture.get("source", {}).get("modelNameRetained")
            is not False
        ):
            raise ValueError(
                "recorded model-backed fixture has an invalid evidence boundary"
            )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            f"cannot derive canonical model-backed fixture: {error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-model-backed-run fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    runner_versions = expected_fixture.get("versions")
    if type(runner_versions) is not list or len(runner_versions) != 2:
        failures.append(
            "model-backed runner fixture must contain exactly two versions."
        )
        return failures

    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        runner_versions,
    ):
        if type(runner_candidate) is not dict:
            failures.append(
                "model-backed runner version rows must be objects."
            )
            break
        cold_start = runner_candidate.get("coldStart")
        restart = runner_candidate.get("restart")
        if type(cold_start) is not dict or type(restart) is not dict:
            failures.append(
                "model-backed runner phases must be objects."
            )
            break
        expected_smoke = {
            "catalogPopulated": (
                cold_start.get("catalogPopulated") is True
                and restart.get("catalogPopulated") is True
            ),
            "chatCancellationPassed": (
                cold_start.get("chatCancellationConfirmed") is True
                and restart.get("chatCancellationConfirmed") is True
            ),
            "chatCompletionPassed": (
                cold_start.get("chatCompleted") is True
                and restart.get("chatCompleted") is True
            ),
            "coldStartPassed": (
                cold_start.get("adapterTestPassed") is True
            ),
            "installedStatePreserved": (
                cold_start.get("installedStatePreserved") is True
                and restart.get("installedStatePreserved") is True
            ),
            "modelUnloadPassed": (
                cold_start.get("modelUnloadConfirmed") is True
                and restart.get("modelUnloadConfirmed") is True
            ),
            "postCancellationRecoveryPassed": (
                cold_start.get("postCancellationRecoveryPassed") is True
                and restart.get("postCancellationRecoveryPassed") is True
            ),
            "restartPassed": restart.get("adapterTestPassed") is True,
            "snapshotUnchanged": (
                cold_start.get("snapshotUnchanged") is True
                and restart.get("snapshotUnchanged") is True
            ),
            "stoppedEndpointUnavailable": (
                cold_start.get("endpointUnavailableAfterStop") is True
                and restart.get("endpointUnavailableAfterStop") is True
            ),
        }
        if (
            provider_candidate["version"] != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
            or provider_candidate["isolatedModelBackedSmoke"]
            != expected_smoke
        ):
            failures.append(
                "provider-compatibility fixture and model-backed runner "
                "fixture differ in Ollama version, archive identity, or "
                "model-backed adapter result."
            )
            break

    return failures


def local_release_ollama_additional_chat_shape_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_END
        ),
        fixture_label="ollama-additional-chat-shape",
    )
    if fixture_body is None:
        return failures

    runner_path = LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_RUNNER
    if not runner_path.is_file():
        return failures + [
            "script/run_ollama_additional_chat_shape_matrix.py: "
            "missing additional chat-shape runner."
        ]

    try:
        runner = runpy.run_path(str(runner_path))
        fixture_builder = runner["recorded_fixture"]
        fixture_validator = runner["validate_recorded_fixture"]
        source_assertion = runner["assert_bound_sources"]
        profile = runner["PROFILE"]
        if not all(
            callable(value)
            for value in (
                fixture_builder,
                fixture_validator,
                source_assertion,
            )
        ):
            raise TypeError(
                "additional chat-shape fixture helpers must be callable"
            )
        if profile.live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledChatModelCompatibility"
        ):
            raise ValueError(
                "additional chat-shape live filter differs from the "
                "canonical chat assertion"
            )
        if profile.required_capabilities != frozenset({"completion"}):
            raise ValueError(
                "additional chat-shape profile must require completion"
            )
        source_assertion()
        expected_fixture = fixture_builder()
        fixture_validator(expected_fixture)
        if (
            type(expected_fixture) is not dict
            or expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("observationCount") != 4
            or expected_fixture.get("profile") != "chat"
            or expected_fixture.get("selection")
            != {
                "completionCandidateCount": 3,
                "selectionOrdinal": 2,
                "targetCapabilityCount": 3,
                "targetInitiallyUnloaded": True,
                "targetVisionCapable": False,
            }
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get(
                "modelNameRetained"
            )
            is not False
            or expected_fixture.get("source", {}).get(
                "modelNameRetained"
            )
            is not False
        ):
            raise ValueError(
                "recorded additional chat-shape fixture has an invalid "
                "evidence boundary"
            )
    except Exception as error:
        return failures + [
            "script/run_ollama_additional_chat_shape_matrix.py: "
            "cannot derive canonical additional chat-shape fixture: "
            f"{error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-additional-chat-shape fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    versions = expected_fixture.get("versions")
    if type(versions) is not list or len(versions) != 2:
        failures.append(
            "additional chat-shape runner fixture must contain exactly "
            "two versions."
        )
        return failures
    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        versions,
    ):
        if (
            type(runner_candidate) is not dict
            or provider_candidate["version"]
            != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
        ):
            failures.append(
                "provider-compatibility fixture and additional chat-shape "
                "fixture differ in Ollama version or archive identity."
            )
            break

    return failures


def local_release_ollama_embedding_model_backed_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_END
        ),
        fixture_label="ollama-embedding-model-backed-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing embedding-model-backed runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        live_test_filter = runner["EMBEDDING_BACKED_LIVE_TEST_FILTER"]
        fixture_builder = runner[
            "recorded_embedding_model_backed_fixture"
        ]
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledEmbeddingModelCompatibility"
        ):
            raise ValueError(
                "EMBEDDING_BACKED_LIVE_TEST_FILTER differs from the "
                "canonical test"
            )
        if not callable(fixture_builder):
            raise TypeError(
                "recorded_embedding_model_backed_fixture must be callable"
            )
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError(
                "recorded embedding-model-backed fixture must be an object"
            )
        if (
            expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get(
                "modelNameRetained"
            )
            is not False
            or expected_fixture.get("source", {}).get(
                "modelNameRetained"
            )
            is not False
        ):
            raise ValueError(
                "recorded embedding-model-backed fixture has an invalid "
                "evidence boundary"
            )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical embedding-model-backed fixture: "
            f"{error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-model-backed-run fixture must match the "
            "runner's canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    runner_versions = expected_fixture.get("versions")
    if type(runner_versions) is not list or len(runner_versions) != 2:
        failures.append(
            "embedding-model-backed runner fixture must contain exactly "
            "two versions."
        )
        return failures

    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        runner_versions,
    ):
        if type(runner_candidate) is not dict:
            failures.append(
                "embedding-model-backed runner version rows must be objects."
            )
            break
        cold_start = runner_candidate.get("coldStart")
        restart = runner_candidate.get("restart")
        if type(cold_start) is not dict or type(restart) is not dict:
            failures.append(
                "embedding-model-backed runner phases must be objects."
            )
            break
        expected_smoke = {
            "catalogPopulated": (
                cold_start.get("catalogPopulated") is True
                and restart.get("catalogPopulated") is True
            ),
            "coldStartPassed": (
                cold_start.get("adapterTestPassed") is True
            ),
            "embeddingBatchPassed": (
                cold_start.get("embeddingBatchCompleted") is True
                and restart.get("embeddingBatchCompleted") is True
            ),
            "embeddingShapePassed": (
                cold_start.get("embeddingShapeValidated") is True
                and restart.get("embeddingShapeValidated") is True
            ),
            "installedStatePreserved": (
                cold_start.get("installedStatePreserved") is True
                and restart.get("installedStatePreserved") is True
            ),
            "modelUnloadPassed": (
                cold_start.get("modelUnloadConfirmed") is True
                and restart.get("modelUnloadConfirmed") is True
            ),
            "restartPassed": restart.get("adapterTestPassed") is True,
            "snapshotUnchanged": (
                cold_start.get("snapshotUnchanged") is True
                and restart.get("snapshotUnchanged") is True
            ),
            "stoppedEndpointUnavailable": (
                cold_start.get("endpointUnavailableAfterStop") is True
                and restart.get("endpointUnavailableAfterStop") is True
            ),
        }
        if (
            provider_candidate["version"]
            != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
            or provider_candidate["isolatedEmbeddingModelBackedSmoke"]
            != expected_smoke
        ):
            failures.append(
                "provider-compatibility fixture and "
                "embedding-model-backed runner fixture differ in Ollama "
                "version, archive identity, or adapter result."
            )
            break

    return failures


def local_release_ollama_embedding_semantic_quality_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_END
        ),
        fixture_label="ollama-embedding-semantic-quality",
    )
    if fixture_body is None:
        return failures
    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing embedding semantic-quality runner."
        ]

    try:
        runner_source = LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
            encoding="utf-8"
        )
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        fixture_builder = runner[
            "recorded_embedding_semantic_quality_fixture"
        ]
        validator = runner[
            "validate_recorded_embedding_semantic_quality_fixture"
        ]
        task_set_validator = runner[
            "validate_embedding_semantic_quality_task_set"
        ]
        expected_runner_source_sha256 = runner[
            "RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256"
        ]
        expected_task_set_sha256 = runner[
            "EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256"
        ]
        expected_scorer_source_sha256 = runner[
            "EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_SHA256"
        ]
        expected_live_assertion_source_sha256 = runner[
            "EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_SHA256"
        ]
        semantic_filter = runner[
            "EMBEDDING_SEMANTIC_QUALITY_LIVE_TEST_FILTER"
        ]
        recovery_filter = runner[
            "EMBEDDING_SEMANTIC_QUALITY_RECOVERY_TEST_FILTER"
        ]
        if (
            not callable(fixture_builder)
            or not callable(validator)
            or not callable(task_set_validator)
        ):
            raise TypeError(
                "embedding semantic-quality builders and validators "
                "must be callable"
            )
        if semantic_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledEmbeddingSemanticQuality"
        ):
            raise ValueError(
                "embedding semantic-quality test filter drifted"
            )
        if recovery_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledEmbeddingSemanticRecovery"
        ):
            raise ValueError(
                "embedding semantic-quality recovery filter drifted"
            )
        for label, value in (
            ("runner source", expected_runner_source_sha256),
            ("task set", expected_task_set_sha256),
            ("semantic scorer source", expected_scorer_source_sha256),
            (
                "semantic live assertion source",
                expected_live_assertion_source_sha256,
            ),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in value
                )
            ):
                raise ValueError(f"{label} SHA-256 was invalid")
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError(
                "recorded embedding semantic-quality fixture must be "
                "an object"
            )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        task_set_path = (
            ROOT
            / "shared"
            / "evaluation"
            / "ollama-embedding-semantic-quality-v1.json"
        )
        task_set_data = task_set_path.read_bytes()
        task_set = json.loads(
            task_set_data,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        for label, source_path in (
            (
                "semantic scorer",
                LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE,
            ),
            (
                "semantic live assertion",
                LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_LIVE_ASSERTION_SOURCE,
            ),
        ):
            if source_path.is_symlink() or not source_path.is_file():
                raise OSError(f"{label} source was not a regular file")
        scorer_source_data = (
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE.read_bytes()
        )
        live_assertion_source_data = (
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_LIVE_ASSERTION_SOURCE
            .read_bytes()
        )
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical embedding semantic-quality fixture: "
            f"{error}"
        ]

    observed_runner_source_sha256 = (
        normalized_live_fault_runner_source_sha256(runner_source)
    )
    if observed_runner_source_sha256 != expected_runner_source_sha256:
        failures.append(
            "script/run_ollama_compatibility_matrix.py: embedding "
            "semantic-quality runner source differs from the recorded "
            "normalized SHA-256."
        )
    if hashlib.sha256(task_set_data).hexdigest() != (
        expected_task_set_sha256
    ):
        failures.append(
            "shared/evaluation/ollama-embedding-semantic-quality-v1.json: "
            "task-set bytes differ from the recorded SHA-256."
        )
    if hashlib.sha256(scorer_source_data).hexdigest() != (
        expected_scorer_source_sha256
    ):
        failures.append(
            "apps/macos/OllamaBackend/Tests/"
            "OllamaEmbeddingSemanticQualityTests.swift: semantic scorer "
            "source bytes differ from the recorded SHA-256."
        )
    if hashlib.sha256(live_assertion_source_data).hexdigest() != (
        expected_live_assertion_source_sha256
    ):
        failures.append(
            "apps/macos/OllamaBackend/Tests/OllamaBackendTests.swift: "
            "semantic live assertion source bytes differ from the recorded "
            "SHA-256."
        )
    try:
        task_set_validator(task_set)
    except Exception as error:
        failures.append(
            "shared/evaluation/ollama-embedding-semantic-quality-v1.json: "
            f"task-set schema is invalid: {error}"
        )

    try:
        validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-semantic-quality fixture violates the "
            f"runner schema: {error}"
        )
        return failures

    canonical_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-semantic-quality fixture must match the "
            "runner's canonical exact values, JSON types, and key order."
        )
    return failures


def local_release_ollama_embedding_multilingual_semantic_quality_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_END
        ),
        fixture_label=(
            "ollama-embedding-multilingual-semantic-quality"
        ),
    )
    if fixture_body is None:
        return failures
    runner_path = LOCAL_RELEASE_OLLAMA_MULTILINGUAL_SEMANTIC_RUNNER
    if not runner_path.is_file():
        return failures + [
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "missing multilingual semantic-quality runner."
        ]

    try:
        runner_source = runner_path.read_text(encoding="utf-8")
        runner = runpy.run_path(str(runner_path))
        fixture_builder = runner["recorded_fixture"]
        fixture_validator = runner["validate_recorded_fixture"]
        task_set_bytes_reader = runner["recorded_task_set_bytes"]
        task_set_validator = runner["validate_task_set"]
        normalized_source_sha256 = runner[
            "normalized_runner_source_sha256"
        ]
        expected_runner_source_sha256 = runner[
            "RECORDED_RUNNER_SOURCE_SHA256"
        ]
        expected_task_set_sha256 = runner["TASK_SET_SHA256"]
        expected_swift_source_sha256 = runner["SWIFT_SOURCE_SHA256"]
        expected_base_runner_source_sha256 = runner[
            "BASE_RUNNER_SOURCE_SHA256"
        ]
        expected_recovery_source_sha256 = runner[
            "RECOVERY_SOURCE_SHA256"
        ]
        task_set_path = runner["TASK_SET_PATH"]
        swift_source_path = runner["SWIFT_SOURCE_PATH"]
        base_runner_source_path = runner["BASE_RUNNER_SOURCE_PATH"]
        recovery_source_path = runner["RECOVERY_SOURCE_PATH"]
        live_filter = runner["LIVE_TEST_FILTER"]
        if (
            not callable(fixture_builder)
            or not callable(fixture_validator)
            or not callable(task_set_bytes_reader)
            or not callable(task_set_validator)
            or not callable(normalized_source_sha256)
        ):
            raise TypeError(
                "multilingual semantic builders and validators must be "
                "callable"
            )
        if live_filter != (
            "OllamaEmbeddingMultilingualSemanticQualityTests."
            "testLiveOllamaExactVersionInstalledEmbeddingMultilingual"
            "SemanticQuality"
        ):
            raise ValueError(
                "multilingual semantic live test filter drifted"
            )
        for label, value in (
            ("runner source", expected_runner_source_sha256),
            ("task set", expected_task_set_sha256),
            ("Swift source", expected_swift_source_sha256),
            ("base runner source", expected_base_runner_source_sha256),
            ("recovery source", expected_recovery_source_sha256),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in value
                )
            ):
                raise ValueError(f"{label} SHA-256 was invalid")
        # The V2 fixture is a historical observation bound to its recorded
        # product-source digests. The live runner still calls
        # assert_bound_sources() and refuses re-execution after product-source
        # drift; documentation validation must not relabel current bytes as the
        # bytes that produced the observation.
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError(
                "recorded multilingual semantic fixture must be an object"
            )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        task_set_data = task_set_bytes_reader()
        task_set = json.loads(
            task_set_data,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        for label, path in (
            ("task set", task_set_path),
            ("Swift source", swift_source_path),
            ("base runner source", base_runner_source_path),
            ("recovery source", recovery_source_path),
        ):
            if (
                not isinstance(path, Path)
                or path.is_symlink()
                or not path.is_file()
            ):
                raise OSError(f"{label} was not a regular file")
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "cannot derive canonical multilingual semantic fixture: "
            f"{error}"
        ]
    except Exception as error:
        return failures + [
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "multilingual semantic source validation failed: "
            f"{error}"
        ]

    if normalized_source_sha256(runner_source) != (
        expected_runner_source_sha256
    ):
        failures.append(
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "multilingual semantic runner source differs from the recorded "
            "normalized SHA-256."
        )
    for label, path, expected_sha256 in (
        (
            "task-set",
            task_set_path,
            expected_task_set_sha256,
        ),
        (
            "Swift scorer/live assertion",
            swift_source_path,
            expected_swift_source_sha256,
        ),
        (
            "base runner",
            base_runner_source_path,
            expected_base_runner_source_sha256,
        ),
        (
            "recovery assertion",
            recovery_source_path,
            expected_recovery_source_sha256,
        ),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            failures.append(
                f"{path.relative_to(ROOT)}: multilingual semantic "
                f"{label} bytes differ from the recorded SHA-256."
            )
    try:
        task_set_validator(task_set)
    except Exception as error:
        failures.append(
            "shared/evaluation/"
            "ollama-embedding-multilingual-semantic-quality-v2.json: "
            f"task-set schema is invalid: {error}"
        )
    try:
        fixture_validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-multilingual-semantic-quality fixture "
            f"violates the runner schema: {error}"
        )
        return failures

    canonical_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-multilingual-semantic-quality fixture must "
            "match the runner's canonical exact values, JSON types, and "
            "key order."
        )
    return failures


def local_release_ollama_vision_model_backed_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_START,
        end_marker=LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_END,
        fixture_label="ollama-vision-model-backed-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing vision-model-backed runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        live_test_filter = runner["VISION_BACKED_LIVE_TEST_FILTER"]
        fixture_builder = runner["recorded_vision_model_backed_fixture"]
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledVisionModelCompatibility"
        ):
            raise ValueError(
                "VISION_BACKED_LIVE_TEST_FILTER differs from the canonical test"
            )
        if not callable(fixture_builder):
            raise TypeError(
                "recorded_vision_model_backed_fixture must be callable"
            )
        expected_fixture = fixture_builder()
        if (
            type(expected_fixture) is not dict
            or expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get(
                "modelNameRetained"
            )
            is not False
            or expected_fixture.get("source", {}).get(
                "modelNameRetained"
            )
            is not False
        ):
            raise ValueError(
                "recorded vision-model-backed fixture has an invalid "
                "evidence boundary"
            )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical vision-model-backed fixture: "
            f"{error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-vision-model-backed-run fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    runner_versions = expected_fixture.get("versions")
    if type(runner_versions) is not list or len(runner_versions) != 2:
        failures.append(
            "vision-model-backed runner fixture must contain exactly two versions."
        )
        return failures

    phase_keys = {
        "catalogPopulated": "catalogPopulated",
        "chatCancellationPassed": "chatCancellationConfirmed",
        "imageAttachmentPassed": "imageAttachmentCompleted",
        "installedStatePreserved": "installedStatePreserved",
        "modelUnloadPassed": "modelUnloadConfirmed",
        "postCancellationRecoveryPassed": (
            "postCancellationRecoveryPassed"
        ),
        "snapshotUnchanged": "snapshotUnchanged",
        "stoppedEndpointUnavailable": "endpointUnavailableAfterStop",
        "textChatPassed": "textChatCompleted",
    }
    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        runner_versions,
    ):
        if type(runner_candidate) is not dict:
            failures.append(
                "vision-model-backed runner version rows must be objects."
            )
            break
        cold_start = runner_candidate.get("coldStart")
        restart = runner_candidate.get("restart")
        if type(cold_start) is not dict or type(restart) is not dict:
            failures.append(
                "vision-model-backed runner phases must be objects."
            )
            break
        expected_smoke = {
            output_key: (
                cold_start.get(phase_key) is True
                and restart.get(phase_key) is True
            )
            for output_key, phase_key in phase_keys.items()
        }
        expected_smoke.update(
            {
                "coldStartPassed": (
                    cold_start.get("adapterTestPassed") is True
                ),
                "restartPassed": (
                    restart.get("adapterTestPassed") is True
                ),
            }
        )
        if (
            provider_candidate["version"]
            != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
            or provider_candidate["isolatedVisionModelBackedSmoke"]
            != expected_smoke
        ):
            failures.append(
                "provider-compatibility fixture and vision-model-backed "
                "runner fixture differ in Ollama version, archive identity, "
                "or adapter result."
            )
            break

    return failures


def local_release_ollama_duration_observation_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_START
        ),
        end_marker=LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_END,
        fixture_label="ollama-duration-observation",
    )
    if fixture_body is None:
        return failures
    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing duration-observation runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        validator = runner[
            "validate_recorded_duration_observation_fixture"
        ]
        expected_sha256 = runner[
            "RECORDED_DURATION_OBSERVATION_SHA256"
        ]
        if not callable(validator):
            raise TypeError(
                "duration-observation validator must be callable"
            )
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_sha256
            )
        ):
            raise ValueError(
                "RECORDED_DURATION_OBSERVATION_SHA256 must be a SHA-256"
            )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical duration-observation fixture: "
            f"{error}"
        ]

    try:
        validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-duration-observation fixture violates the runner schema: "
            f"{error}"
        )
        return failures

    canonical_body = json.dumps(
        fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-duration-observation fixture must use canonical JSON "
            "types and key order."
        )
    observed_sha256 = hashlib.sha256(
        fixture_body.encode("utf-8")
    ).hexdigest()
    if observed_sha256 != expected_sha256:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-duration-observation fixture differs from the recorded "
            "runner SHA-256."
        )
    return failures


def local_release_ollama_live_fault_injection_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_END
        ),
        fixture_label="ollama-live-fault-injection",
    )
    if fixture_body is None:
        return failures
    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing live-fault-injection runner."
        ]

    try:
        runner_source = LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
            encoding="utf-8"
        )
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        validator = runner[
            "validate_recorded_live_fault_injection_fixture"
        ]
        expected_sha256 = runner[
            "RECORDED_LIVE_FAULT_INJECTION_SHA256"
        ]
        expected_runner_source_sha256 = runner[
            "RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256"
        ]
        if not callable(validator):
            raise TypeError(
                "live-fault-injection validator must be callable"
            )
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_sha256
            )
        ):
            raise ValueError(
                "RECORDED_LIVE_FAULT_INJECTION_SHA256 must be a SHA-256"
            )
        if (
            not isinstance(expected_runner_source_sha256, str)
            or len(expected_runner_source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_runner_source_sha256
            )
        ):
            raise ValueError(
                "RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256 "
                "must be a SHA-256"
            )
        observed_runner_source_sha256 = (
            normalized_live_fault_runner_source_sha256(runner_source)
        )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical live-fault-injection fixture: "
            f"{error}"
        ]

    if observed_runner_source_sha256 != expected_runner_source_sha256:
        failures.append(
            "script/run_ollama_compatibility_matrix.py: "
            "live-fault-injection runner source differs from the recorded "
            "normalized SHA-256."
        )

    try:
        validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-live-fault-injection fixture violates the runner schema: "
            f"{error}"
        )
        return failures

    canonical_body = json.dumps(
        fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-live-fault-injection fixture must use canonical JSON "
            "types and key order."
        )
    observed_sha256 = hashlib.sha256(
        fixture_body.encode("utf-8")
    ).hexdigest()
    if observed_sha256 != expected_sha256:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-live-fault-injection fixture differs from the recorded "
            "runner SHA-256."
        )
    return failures


def local_release_document_failures() -> list[str]:
    try:
        relative_doc = LOCAL_RELEASE_CURRENT_DOC.relative_to(ROOT)
    except ValueError:
        relative_doc = LOCAL_RELEASE_CURRENT_DOC
    if not LOCAL_RELEASE_CURRENT_DOC.is_file():
        return [f"{relative_doc}: missing local release qualification record."]

    try:
        document_text = LOCAL_RELEASE_CURRENT_DOC.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [f"{relative_doc}: unreadable local release qualification record: {error}"]

    failures: list[str] = []
    try:
        relative_fixture_doc = LOCAL_RELEASE_FIXTURE_DOC.relative_to(ROOT)
    except ValueError:
        relative_fixture_doc = LOCAL_RELEASE_FIXTURE_DOC
    try:
        fixture_document_text = LOCAL_RELEASE_FIXTURE_DOC.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError) as error:
        fixture_document_text = None
        failures.append(
            f"{relative_fixture_doc}: unreadable historical release fixture "
            f"record: {error}"
        )

    required_claims = (
        ("release ID", f"`{LOCAL_RELEASE_ID}`"),
        (
            "ZIP size",
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SIZE:,} bytes",
        ),
        ("ZIP SHA-256", f"`{LOCAL_RELEASE_EXPECTED_ZIP_SHA256}`"),
        (
            "manifest size",
            f"{LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE:,} bytes",
        ),
        (
            "manifest SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256}`",
        ),
        (
            "checksum sidecar size",
            f"{LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE:,} bytes",
        ),
        (
            "checksum sidecar SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256}`",
        ),
        (
            "reproducibility result path",
            (
                "`dist/reproducibility/"
                "aetherlink-1.0.0+11-local-v1-two-root-v2.json`"
            ),
        ),
        (
            "reproducibility result size",
            f"{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        ),
        (
            "reproducibility result SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256}`",
        ),
        (
            "reproducibility confirmation path",
            (
                "`dist/reproducibility/"
                "aetherlink-1.0.0+11-local-v1-two-root-v2-confirmation.json`"
            ),
        ),
        (
            "reproducibility confirmation size",
            (
                f"{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_CONFIRMATION_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "reproducibility confirmation SHA-256",
            (
                f"`{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_CONFIRMATION_SHA256}`"
            ),
        ),
        (
            "reproducibility confirmation publication match",
            "`alreadyMatched=true`",
        ),
        (
            "packaged-app lifecycle result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-10-lifecycle-v1.json`"
            ),
        ),
        (
            "packaged-app lifecycle result size",
            f"{MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE:,} bytes",
        ),
        (
            "packaged-app lifecycle result SHA-256",
            f"`{MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256}`",
        ),
        (
            "packaged-app lifecycle runner SHA-256",
            f"`{MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256}`",
        ),
        (
            "packaged-app lifecycle test SHA-256",
            f"`{MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256}`",
        ),
        (
            "historical packaged-app lifecycle runner SHA-256",
            (
                f"`{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "historical packaged-app lifecycle test SHA-256",
            f"`{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256}`",
        ),
        (
            "packaged-app minimum observation",
            "`minimumObservationSeconds=5.0`",
        ),
        (
            "packaged-app observation deadline",
            "`observationDeadlineReached=true`",
        ),
        (
            "packaged-app identity-file observation",
            "`identityFilePresentAfterRuns=[false, false]`",
        ),
        (
            "historical packaged-app lifecycle result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-9-lifecycle-v1.json`"
            ),
        ),
        (
            "historical packaged-app lifecycle result size",
            (
                f"{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "historical packaged-app lifecycle result SHA-256",
            (
                f"`{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "Build 10 lifecycle non-transfer boundary",
            (
                "Build 10 observations remain bound to Build 10 and are not "
                "reinterpreted as Build 11 evidence."
            ),
        ),
        (
            "unequal source-root byte lengths",
            "101- and 109-byte source roots",
        ),
        (
            "unequal source-root result",
            "`sourceRootLengthsDiffer=true`",
        ),
        (
            "independent publication readback",
            "`independentReadback=true`",
        ),
        (
            "published lane identity",
            "`publishedBytesEqualLaneA=true`",
        ),
        (
            "publication source freshness",
            "`sourceSnapshotUnchanged=true`",
        ),
        (
            "AAB structure validation",
            "`bundletool validate`",
        ),
        (
            "source inventory count",
            f"{LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT}-file source inventory",
        ),
        (
            "source inventory SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_SHA256}`",
        ),
        ("source HEAD", f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`"),
        ("dirty source boundary", "`dirty-content-snapshot`"),
        (
            "commit-only reconstruction boundary",
            "The Git commit alone cannot reconstruct these release bytes.",
        ),
        (
            "POM body retention boundary",
            "Original POM bodies are not archived.",
        ),
        (
            "license text retention boundary",
            "License/NOTICE texts are not archived.",
        ),
        (
            "offline evidence boundary",
            "The offline checker does not re-fetch or re-parse those originals.",
        ),
        (
            "compliance profile",
            "`aetherlink-release-compliance-v2`",
        ),
        ("compliance schema", "`schemaVersion=2`"),
        ("runtime relationship count", "202 runtime"),
        ("build dependency relationship count", "155 build dependency"),
        ("build tool relationship count", "335 build tool"),
        ("total relationship count", "692 exact role relationships"),
        (
            "payload member count",
            f"{LOCAL_RELEASE_EXPECTED_MEMBER_COUNT} payload members",
        ),
        ("macOS app/dSYM UUID", f"`{LOCAL_RELEASE_EXPECTED_MACOS_UUID}`"),
    )
    for member_path, (size, sha256) in LOCAL_RELEASE_EXPECTED_MEMBERS.items():
        required_claims += (
            (f"{member_path} size", f"{size:,} bytes"),
            (f"{member_path} SHA-256", f"`{sha256}`"),
        )

    for label, expected_text in required_claims:
        if expected_text not in document_text:
            failures.append(
                f"{relative_doc}: missing exact {label} claim {expected_text!r}."
            )

    if fixture_document_text is not None:
        failures.extend(
            local_release_transition_fixture_failures(fixture_document_text)
        )
        failures.extend(
            local_release_provider_fixture_failures(fixture_document_text)
        )
        failures.extend(
            local_release_ollama_runner_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_model_backed_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_additional_chat_shape_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_embedding_model_backed_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_embedding_semantic_quality_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_embedding_multilingual_semantic_quality_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_vision_model_backed_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_duration_observation_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_live_fault_injection_fixture_failures(
                fixture_document_text
            )
        )

    if not LOCAL_RELEASE_ARCHIVE_DIR.exists():
        return failures
    if not LOCAL_RELEASE_ARCHIVE_DIR.is_dir():
        failures.append(
            f"{LOCAL_RELEASE_ARCHIVE_DIR.relative_to(ROOT)}: local release archive path is not a directory."
        )
        return failures

    archive_path = LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip"
    manifest_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.manifest.json"
    )
    checksum_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip.sha256"
    )
    for path in (archive_path, manifest_path, checksum_path):
        if not path.is_file():
            failures.append(
                f"{path.relative_to(ROOT)}: missing local release readback input."
            )
    if failures and any(not path.is_file() for path in (archive_path, manifest_path, checksum_path)):
        return failures

    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(
            manifest_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
        checksum_fields = checksum_path.read_text(encoding="ascii").split()
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: unreadable local release identity: {error}"
        )
        return failures

    if not isinstance(manifest, dict):
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: manifest root must be a JSON object."
        )
        return failures

    def read_path(path: tuple[str, ...]) -> object:
        value: object = manifest
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    manifest_expectations = (
        (("schemaVersion",), 2),
        (("release", "releaseId"), LOCAL_RELEASE_ID),
        (
            ("archive", "memberCountExcludingManifest"),
            LOCAL_RELEASE_EXPECTED_MEMBER_COUNT,
        ),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (("source", "snapshotSha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
        (("source", "head"), LOCAL_RELEASE_EXPECTED_SOURCE_HEAD),
        (("source", "worktreeState"), "dirty-content-snapshot"),
        (("platforms", "android", "applicationId"), "com.localagentbridge.android"),
        (
            ("platforms", "android", "versionCode"),
            LOCAL_RELEASE_BUILD_NUMBER,
        ),
        (
            ("platforms", "android", "versionName"),
            LOCAL_RELEASE_MARKETING_VERSION,
        ),
        (("platforms", "android", "minSdk"), 26),
        (("platforms", "android", "targetSdk"), 36),
        (("platforms", "android", "abis"), ["arm64-v8a"]),
        (("platforms", "android", "signatureState"), "unsigned"),
        (
            ("platforms", "android", "bundleStructureValidation"),
            {
                "member": "android/bundle/app-release.aab",
                "moduleSet": ["base"],
                "status": "passed",
                "tool": "bundletool validate",
            },
        ),
        (("platforms", "macos", "bundleId"), "dev.aetherlink.companion"),
        (
            ("platforms", "macos", "marketingVersion"),
            LOCAL_RELEASE_MARKETING_VERSION,
        ),
        (
            ("platforms", "macos", "buildNumber"),
            LOCAL_RELEASE_BUILD_NUMBER,
        ),
        (("platforms", "macos", "minimumSystemVersion"), "14.0"),
        (("platforms", "macos", "architectures"), ["arm64"]),
        (("platforms", "macos", "signatureState"), "ad-hoc-local"),
        (("platforms", "macos", "uuid"), LOCAL_RELEASE_EXPECTED_MACOS_UUID),
        (
            ("platforms", "macos", "dSYM", "uuid"),
            LOCAL_RELEASE_EXPECTED_MACOS_UUID,
        ),
        (("compliance", "gradleLockedPackageCount"), 350),
        (("compliance", "swiftExternalDependencyCount"), 0),
        (("compliance", "artifactFilesAnalyzed"), False),
        (
            ("compliance", "licenseCompatibilityConclusionIncluded"),
            False,
        ),
        (("compliance", "licenseConcluded"), "NOASSERTION"),
        (("compliance", "networkRequiredForReleaseBuild"), False),
        (
            ("compliance", "profile"),
            "aetherlink-release-compliance-v2",
        ),
        (("compliance", "schemaVersion"), 2),
        (("compliance", "spdx", "format"), "SPDX-2.3"),
        (("compliance", "spdx", "packageCount"), 351),
        (("compliance", "spdx", "relationshipCount"), 692),
    )
    for path, expected in manifest_expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{manifest_path.relative_to(ROOT)}: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )

    member_rows = manifest.get("members")
    actual_members: dict[str, tuple[object, object]] = {}
    if not isinstance(member_rows, list):
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: members must be a JSON array."
        )
    else:
        for index, row in enumerate(member_rows):
            if not isinstance(row, dict):
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: members[{index}] must be an object."
                )
                continue
            path = row.get("path")
            if not isinstance(path, str):
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: members[{index}].path must be a string."
                )
                continue
            if path in actual_members:
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: duplicate member path {path!r}."
                )
                continue
            actual_members[path] = (row.get("size"), row.get("sha256"))

    for member_path, expected_identity in LOCAL_RELEASE_EXPECTED_MEMBERS.items():
        actual_identity = actual_members.get(member_path)
        if actual_identity != expected_identity:
            failures.append(
                f"{manifest_path.relative_to(ROOT)}: expected {member_path} "
                f"identity {expected_identity!r}, found {actual_identity!r}."
            )

    manifest_identity = (len(manifest_bytes), hashlib.sha256(manifest_bytes).hexdigest())
    expected_manifest_identity = (
        LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE,
        LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
    )
    if manifest_identity != expected_manifest_identity:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: expected manifest identity "
            f"{expected_manifest_identity!r}, found {manifest_identity!r}."
        )

    archive_size = archive_path.stat().st_size
    if archive_size != LOCAL_RELEASE_EXPECTED_ZIP_SIZE:
        failures.append(
            f"{archive_path.relative_to(ROOT)}: expected size "
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SIZE}, found {archive_size}."
        )
    if (
        len(checksum_fields) != 2
        or checksum_fields[0] != LOCAL_RELEASE_EXPECTED_ZIP_SHA256
        or checksum_fields[1] != archive_path.name
    ):
        failures.append(
            f"{checksum_path.relative_to(ROOT)}: checksum sidecar does not match "
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SHA256} and {archive_path.name}."
        )

    checksum_bytes = checksum_path.read_bytes()
    checksum_identity = (
        len(checksum_bytes),
        hashlib.sha256(checksum_bytes).hexdigest(),
    )
    expected_checksum_identity = (
        LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE,
        LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256,
    )
    if checksum_identity != expected_checksum_identity:
        failures.append(
            f"{checksum_path.relative_to(ROOT)}: expected checksum sidecar "
            f"identity {expected_checksum_identity!r}, found "
            f"{checksum_identity!r}."
        )

    result_relative = (
        "dist/reproducibility/"
        "aetherlink-1.0.0+11-local-v1-two-root-v2.json"
    )
    if not LOCAL_RELEASE_REPRODUCIBILITY_RESULT.is_file():
        failures.append(
            f"{result_relative}: missing current reproducibility result."
        )
        return failures

    try:
        result_bytes = LOCAL_RELEASE_REPRODUCIBILITY_RESULT.read_bytes()
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{result_relative}: unreadable current reproducibility result: "
            f"{error}"
        )
        return failures

    result_identity = (
        len(result_bytes),
        hashlib.sha256(result_bytes).hexdigest(),
    )
    expected_result_identity = (
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE,
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256,
    )
    if result_identity != expected_result_identity:
        failures.append(
            f"{result_relative}: expected identity "
            f"{expected_result_identity!r}, found {result_identity!r}."
        )

    if not isinstance(result, dict):
        failures.append(
            f"{result_relative}: result root must be a JSON object."
        )
        return failures

    def read_result_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    result_expectations = (
        (("schemaVersion",), 2),
        (("status",), "passed"),
        (
            ("scratch", "sourceRoots", "policy"),
            "distinct-unequal-utf8-byte-length-v1",
        ),
        (
            ("scratch", "sourceRoots", "sourceRootByteLengths"),
            LOCAL_RELEASE_EXPECTED_SOURCE_ROOT_BYTE_LENGTHS,
        ),
        (("scratch", "sourceRoots", "sourceRootLengthsDiffer"), True),
        (("comparison", "archiveBytesEqual"), True),
        (("comparison", "memberSetEqual"), True),
        (("comparison", "memberMetadataEqual"), True),
        (("comparison", "memberBytesEqual"), True),
        (("comparison", "differences"), []),
        (("comparison", "memberDifferences"), []),
        (
            ("publication", "archiveSha256"),
            LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
        ),
        (
            ("publication", "manifestSha256"),
            LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
        ),
        (
            ("publication", "checksumSha256"),
            LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256,
        ),
        (("publication", "independentReadback"), True),
        (("publication", "publishedBytesEqualLaneA"), True),
        (("publication", "sourceSnapshotUnchanged"), True),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (("source", "sha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
    )
    for path, expected in result_expectations:
        actual = read_result_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{result_relative}: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )

    failures.extend(
        current_release_reproducibility_confirmation_failures()
    )
    return failures


def current_release_reproducibility_confirmation_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    relative = (
        "dist/reproducibility/"
        "aetherlink-1.0.0+11-local-v1-two-root-v2-confirmation.json"
    )
    if result_bytes is None:
        if not LOCAL_RELEASE_REPRODUCIBILITY_CONFIRMATION_RESULT.is_file():
            return [f"{relative}: missing reproducibility confirmation result."]
        try:
            result_bytes = (
                LOCAL_RELEASE_REPRODUCIBILITY_CONFIRMATION_RESULT.read_bytes()
            )
        except OSError as error:
            return [
                f"{relative}: unreadable reproducibility confirmation "
                f"result: {error}"
            ]

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_CONFIRMATION_SIZE,
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_CONFIRMATION_SHA256,
    )
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected identity {expected_identity!r}, "
            f"found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{relative}: invalid reproducibility confirmation JSON: {error}"
        )
        return failures
    if not isinstance(result, dict):
        failures.append(
            f"{relative}: reproducibility confirmation root must be an object."
        )
        return failures

    def read_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    expectations = (
        (("schemaVersion",), 2),
        (("status",), "passed"),
        (
            ("scratch", "sourceRoots", "policy"),
            "distinct-unequal-utf8-byte-length-v1",
        ),
        (
            ("scratch", "sourceRoots", "sourceRootByteLengths"),
            LOCAL_RELEASE_EXPECTED_SOURCE_ROOT_BYTE_LENGTHS,
        ),
        (("scratch", "sourceRoots", "sourceRootLengthsDiffer"), True),
        (("comparison", "archiveBytesEqual"), True),
        (("comparison", "memberSetEqual"), True),
        (("comparison", "memberMetadataEqual"), True),
        (("comparison", "memberBytesEqual"), True),
        (("comparison", "differences"), []),
        (("comparison", "memberDifferences"), []),
        (("publication", "alreadyMatched"), True),
        (
            ("publication", "archiveDirectory"),
            f"dist/releases/{LOCAL_RELEASE_ID}",
        ),
        (
            ("publication", "archiveSha256"),
            LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
        ),
        (
            ("publication", "manifestSha256"),
            LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
        ),
        (
            ("publication", "checksumSha256"),
            LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256,
        ),
        (("publication", "independentReadback"), True),
        (("publication", "publishedBytesEqualLaneA"), True),
        (("publication", "sourceSnapshotUnchanged"), True),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (("source", "sha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )

    builds = result.get("builds")
    if not isinstance(builds, list) or len(builds) != 2:
        failures.append(
            f"{relative}: builds must contain exact build-a/build-b results."
        )
        return failures
    for index, expected_id in enumerate(("build-a", "build-b")):
        build = builds[index]
        if not isinstance(build, dict):
            failures.append(
                f"{relative}: builds[{index}] must be an object."
            )
            continue
        build_expectations = (
            ("id", expected_id),
            ("status", "passed"),
            ("commandExitCode", 0),
        )
        for key, expected in build_expectations:
            actual = build.get(key)
            if type(actual) is not type(expected) or actual != expected:
                failures.append(
                    f"{relative}: expected builds[{index}].{key}="
                    f"{expected!r}, found {actual!r}."
                )
        archive = build.get("archive")
        if not isinstance(archive, dict):
            failures.append(
                f"{relative}: builds[{index}].archive must be an object."
            )
            continue
        archive_expectations = (
            ("sha256", LOCAL_RELEASE_EXPECTED_ZIP_SHA256),
            ("manifestSha256", LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256),
            ("checksumSha256", LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256),
            ("sourceSha256", LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
            ("payloadMemberCount", LOCAL_RELEASE_EXPECTED_MEMBER_COUNT),
            ("zipEntryCount", LOCAL_RELEASE_EXPECTED_MEMBER_COUNT + 1),
        )
        for key, expected in archive_expectations:
            actual = archive.get(key)
            if type(actual) is not type(expected) or actual != expected:
                failures.append(
                    f"{relative}: expected builds[{index}].archive.{key}="
                    f"{expected!r}, found {actual!r}."
                )
    return failures


def macos_packaged_lifecycle_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_PACKAGED_LIFECYCLE_RUNNER,
            MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256,
        ),
        (
            MACOS_PACKAGED_LIFECYCLE_TEST,
            MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256,
        ),
        (
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RUNNER,
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256,
        ),
        (
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_TEST,
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256,
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(f"{relative}: missing lifecycle source.")
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(f"{relative}: unreadable lifecycle source: {error}")
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected SHA-256 {expected_sha256}, "
                f"found {actual_sha256}."
            )
    return failures


def packaged_lifecycle_evidence_failures(
    *,
    result_path: Path,
    relative: str,
    expected_size: int,
    expected_sha256: str,
    expected_result: dict[str, object],
    build_label: str,
    result_bytes: bytes | None = None,
) -> list[str]:
    if result_bytes is None:
        if not result_path.is_file():
            return [f"{relative}: missing packaged-app lifecycle result."]
        try:
            result_bytes = result_path.read_bytes()
        except OSError as error:
            return [
                f"{relative}: unreadable packaged-app lifecycle result: {error}"
            ]

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (expected_size, expected_sha256)
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected identity {expected_identity!r}, "
            f"found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{relative}: invalid packaged-app lifecycle JSON: {error}"
        )
        return failures

    if not exact_json_values_equal(
        result,
        expected_result,
    ):
        failures.append(
            f"{relative}: result does not match the exact closed "
            f"{build_label} lifecycle contract."
        )
    return failures


def macos_packaged_lifecycle_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_PACKAGED_LIFECYCLE_RESULT,
        relative=(
            "dist/lifecycle/macos-packaged-app-build-10-lifecycle-v1.json"
        ),
        expected_size=MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE,
        expected_sha256=MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256,
        expected_result=MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT,
        build_label="Build 10",
        result_bytes=result_bytes,
    )


def historical_macos_packaged_lifecycle_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RESULT,
        relative=(
            "dist/lifecycle/macos-packaged-app-build-9-lifecycle-v1.json"
        ),
        expected_size=(
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT
        ),
        build_label="Build 9",
        result_bytes=result_bytes,
    )


def latest_progress_entry() -> tuple[int, str]:
    if not PROGRESS_DOC.is_file():
        return (0, "")

    lines = PROGRESS_DOC.read_text(encoding="utf-8", errors="replace").splitlines()
    implemented_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "## Implemented So Far"),
        -1,
    )
    if implemented_index < 0:
        return (0, "")

    start_index = next(
        (
            index
            for index in range(implemented_index + 1, len(lines))
            if lines[index].startswith("### ")
        ),
        -1,
    )
    if start_index < 0:
        return (0, "")

    end_index = next(
        (
            index
            for index in range(start_index + 1, len(lines))
            if lines[index].startswith("### ")
        ),
        len(lines),
    )
    return (start_index + 1, "\n".join(lines[start_index:end_index]))


def latest_qa_evidence_entry() -> tuple[int, str]:
    if not QA_EVIDENCE_DOC.is_file():
        return (0, "")

    lines = QA_EVIDENCE_DOC.read_text(encoding="utf-8", errors="replace").splitlines()
    current_rule_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "## Current Rule"),
        -1,
    )
    if current_rule_index < 0:
        return (0, "")

    start_index = next(
        (
            index
            for index in range(current_rule_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        -1,
    )
    if start_index < 0:
        return (0, "")

    end_index = next(
        (
            index
            for index in range(start_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return (start_index + 1, "\n".join(lines[start_index:end_index]))


def latest_progress_evidence_failures() -> list[str]:
    failures: list[str] = []
    start_line, entry = latest_progress_entry()
    if not entry:
        return [
            "docs/progress.md: missing latest implemented progress entry under '## Implemented So Far'."
        ]

    required_patterns = (
        (
            re.compile(r"^### \d{4}-\d{2}-\d{2} .+", re.MULTILINE),
            "Latest progress entry must start with a dated implementation heading.",
        ),
        (
            re.compile(r"\bno-device\b", re.IGNORECASE),
            "Latest progress entry must state whether verification was no-device.",
        ),
        (
            re.compile(r"\bCaveat:", re.IGNORECASE),
            "Latest progress entry must include an explicit caveat.",
        ),
        (
            re.compile(r"\bphysical\b|\bcamera QR\b|\breal different-network\b", re.IGNORECASE),
            "Latest progress caveat must name physical or real-network coverage limits.",
        ),
        (
            re.compile(r"\bVerified after this change:", re.IGNORECASE),
            "Latest progress entry must list current verification commands.",
        ),
        (
            re.compile(r"`(?:swift|python3|JAVA_HOME=|git diff|bash)\b", re.IGNORECASE),
            "Latest progress entry must include concrete verification commands in backticks.",
        ),
    )

    for pattern, guidance in required_patterns:
        if not pattern.search(entry):
            failures.append(f"docs/progress.md:{start_line}: {guidance}")

    if "artifacts/" in entry and "device/runtime state" not in entry:
        failures.append(
            f"docs/progress.md:{start_line}: Progress entries that cite artifacts must explain the device/runtime state."
        )

    return failures


def latest_qa_evidence_failures() -> list[str]:
    failures: list[str] = []
    start_line, entry = latest_qa_evidence_entry()
    if not entry:
        return [
            "docs/qa-evidence.md: missing latest QA evidence entry after '## Current Rule'."
        ]

    required_patterns = (
        (
            re.compile(r"^## \d{4}-\d{2}-\d{2} .+", re.MULTILINE),
            "Latest QA evidence entry must start with a dated evidence heading.",
        ),
        (
            re.compile(r"\bproof-boundary\b|\bproof boundary\b", re.IGNORECASE),
            "Latest QA evidence entry must name the proof boundary.",
        ),
        (
            re.compile(r"\bno-device\b", re.IGNORECASE),
            "Latest QA evidence entry must state whether no-device evidence is involved.",
        ),
        (
            re.compile(r"\bphysical\b|\blive-provider\b|\blive provider\b", re.IGNORECASE),
            "Latest QA evidence entry must separate physical or live-provider proof from no-device evidence.",
        ),
        (
            re.compile(r"\bAgent state:.*\bGPT-5\.3-Codex-Spark was not used\b", re.IGNORECASE | re.DOTALL),
            "Latest QA evidence entry must record that GPT-5.3-Codex-Spark was not used.",
        ),
        (
            re.compile(r"\bCaveat:", re.IGNORECASE),
            "Latest QA evidence entry must include an explicit caveat.",
        ),
        (
            re.compile(r"\bVerification commands:", re.IGNORECASE),
            "Latest QA evidence entry must list verification commands.",
        ),
        (
            re.compile(r"`(?:swift|python3|JAVA_HOME=|git diff|bash|./script|script/)\b", re.IGNORECASE),
            "Latest QA evidence entry must include concrete verification commands in backticks.",
        ),
    )

    for pattern, guidance in required_patterns:
        if not pattern.search(entry):
            failures.append(f"docs/qa-evidence.md:{start_line}: {guidance}")

    if "artifacts/" in entry and "device/runtime state" not in entry:
        failures.append(
            f"docs/qa-evidence.md:{start_line}: QA entries that cite artifacts must explain the device/runtime state."
        )

    return failures


def syntax_only_no_device_gate_evidence_failures() -> list[str]:
    failures: list[str] = []
    syntax_command = "bash -n script/check_no_device_quality.sh"

    progress_start_line, progress_entry = latest_progress_entry()
    if syntax_command in progress_entry and "syntax only" not in progress_entry.lower():
        failures.append(
            f"docs/progress.md:{progress_start_line}: `{syntax_command}` is shell syntax validation only; "
            "label it as syntax only or record a real `bash script/check_no_device_quality.sh` run."
        )

    qa_path = ROOT / "docs/qa-evidence.md"
    if qa_path.exists():
        qa_lines = qa_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number, line in enumerate(qa_lines[:60], 1):
            if syntax_command in line and "syntax only" not in line.lower():
                failures.append(
                    f"docs/qa-evidence.md:{line_number}: `{syntax_command}` is shell syntax validation only; "
                    "label it as syntax only or record a real `bash script/check_no_device_quality.sh` run."
                )

    return failures


def historical_local_release_document_failures(
    *,
    ledger_bytes: bytes | None = None,
    document_text_by_build: dict[int, str] | None = None,
) -> list[str]:
    try:
        raw_ledger = (
            LOCAL_RELEASE_LEDGER.read_bytes()
            if ledger_bytes is None
            else ledger_bytes
        )
        entries = parse_release_version_ledger(raw_ledger)
    except (OSError, LedgerError) as error:
        return [
            "release/version-ledger.tsv: cannot validate historical release "
            f"document lineage: {error}"
        ]

    current = entries[-1]
    current_doc_relative = (
        "docs/releases/"
        f"{current.marketing_version}-build-{current.build_number}-local-v1.md"
    )
    failures: list[str] = []
    for entry in entries[:-1]:
        relative = (
            "docs/releases/"
            f"{entry.marketing_version}-build-{entry.build_number}-local-v1.md"
        )
        if document_text_by_build is None:
            path = ROOT / relative
            if not path.is_file():
                failures.append(
                    f"{relative}: missing historical local release record."
                )
                continue
            try:
                document_text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                failures.append(
                    f"{relative}: unreadable historical local release "
                    f"record: {error}"
                )
                continue
        else:
            document_text = document_text_by_build.get(entry.build_number)
            if document_text is None:
                failures.append(
                    f"{relative}: missing injected historical release record."
                )
                continue

        release_id = (
            f"aetherlink-{entry.marketing_version}"
            f"+{entry.build_number}-local-v1"
        )
        required_text = (
            (
                "current qualification record pointer",
                f"`{current_doc_relative}`",
            ),
        )
        for label, expected in required_text:
            if expected not in document_text:
                failures.append(
                    f"{relative}: missing exact {label} {expected!r}."
                )
        expected_status = (
            "superseded local release-engineering candidate, "
            "not a production release."
        )
        status_claims = re.findall(
            r"^Status:\s*(.+?)\s*$",
            document_text,
            re.MULTILINE,
        )
        if status_claims != [expected_status]:
            failures.append(
                f"{relative}: historical status must appear exactly once as "
                f"{expected_status!r}; found {status_claims!r}."
            )
        release_id_claims = re.findall(
            r"^Release ID:\s*`?([^`\s]+)`?\s*$",
            document_text,
            re.MULTILINE,
        )
        if release_id_claims != [release_id]:
            failures.append(
                f"{relative}: historical Release ID must appear exactly once "
                f"as {release_id!r}; found {release_id_claims!r}."
            )
        readback_targets = re.findall(
            r"--archive-dir\s+dist/releases/(aetherlink-[^\s`\\]+)",
            document_text,
        )
        is_fixture_record = (
            entry.build_number == LOCAL_RELEASE_FIXTURE_BUILD_NUMBER
            and entry.marketing_version == LOCAL_RELEASE_MARKETING_VERSION
        )
        if is_fixture_record:
            if readback_targets.count(release_id) != 1:
                failures.append(
                    f"{relative}: historical archive readback target must "
                    f"include exactly one {release_id!r}; found "
                    f"{readback_targets!r}."
                )
        elif readback_targets != [release_id]:
            failures.append(
                f"{relative}: historical archive readback target must appear "
                f"exactly once as {release_id!r}; found "
                f"{readback_targets!r}."
            )
        historical_mode_count = len(
            re.findall(
                r"(?<![\w-])--historical(?![\w-])",
                document_text,
            )
        )
        if not is_fixture_record and historical_mode_count != 1:
            failures.append(
                f"{relative}: historical readback mode must appear exactly "
                f"once; found {historical_mode_count}."
            )
        release_doc_mentions = re.findall(
            r"docs/releases/[0-9]+\.[0-9]+\.[0-9]+-build-"
            r"[1-9][0-9]*-local-v1\.md",
            document_text,
        )
        if is_fixture_record:
            release_doc_pointer_valid = (
                release_doc_mentions.count(current_doc_relative) == 1
            )
        else:
            release_doc_pointer_valid = (
                release_doc_mentions == [current_doc_relative]
            )
        if not release_doc_pointer_valid:
            failures.append(
                f"{relative}: current release document pointer must appear "
                f"exactly once as {current_doc_relative!r}; found "
                f"{release_doc_mentions!r}."
            )
        current_claim_builds = [
            int(value)
            for value in re.findall(
                r"\bBuild\s+([1-9][0-9]*)\b"
                r"(?:(?!\bBuild\s+[1-9][0-9]*\b).){0,180}?"
                r"\bcurrent\s+local\s+qualification\s+record\b",
                document_text,
                re.IGNORECASE | re.DOTALL,
            )
        ]
        if is_fixture_record:
            current_claim_valid = (
                current_claim_builds.count(current.build_number) == 1
            )
        else:
            current_claim_valid = (
                current_claim_builds == [current.build_number]
            )
        if not current_claim_valid:
            failures.append(
                f"{relative}: current qualification prose must name build "
                f"{current.build_number} exactly once; found "
                f"{current_claim_builds!r}."
            )
        contract_claim_builds = [
            int(value)
            for value in re.findall(
                r"\bcontract\s+now\s+lives\s+in\s+the\s+build\s+"
                r"([1-9][0-9]*)\s+record\b",
                document_text,
                re.IGNORECASE,
            )
        ]
        if is_fixture_record:
            contract_claim_valid = (
                contract_claim_builds.count(current.build_number) == 1
            )
        else:
            contract_claim_valid = (
                contract_claim_builds == [current.build_number]
            )
        if not contract_claim_valid:
            failures.append(
                f"{relative}: fuller contract must point to current build "
                f"{current.build_number} exactly once; found "
                f"{contract_claim_builds!r}."
            )

    return failures


def physical_qr_observation_manifest_failures() -> list[str]:
    if not PHYSICAL_QR_OBSERVATION_MANIFEST.is_file():
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: missing sanitized physical QR observation manifest."
        ]

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        raw_text = PHYSICAL_QR_OBSERVATION_MANIFEST.read_text(encoding="utf-8")
        document = json.loads(raw_text, object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateJSONKeyError) as error:
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: unreadable or invalid JSON: "
            f"{error}"
        ]

    if not isinstance(document, dict):
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: root must be a JSON object."
        ]

    failures: list[str] = []

    def read_path(path: tuple[str, ...]) -> object:
        value: object = document
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    allowed_keys_by_path = {
        (): {
            "documentType",
            "schemaVersion",
            "recordedDate",
            "source",
            "device",
            "topology",
            "qrObservation",
            "observedMilestones",
            "retention",
            "proofBoundary",
        },
        ("source",): {
            "repository",
            "branch",
            "headAtObservation",
            "worktreeDirty",
            "exactTreeDigestRetained",
            "laterSourceDelta",
        },
        ("device",): {
            "model",
            "operatingSystem",
            "apiLevel",
            "appBuildVariant",
            "deviceIdentifierRetained",
        },
        ("topology",): {
            "runtimeHost",
            "deviceAndRuntimeNetwork",
            "usbRouteUsedForOpticalClaim",
            "externalRelayUsed",
            "p2pNatTraversalUsed",
        },
        ("qrObservation",): {
            "captureSurface",
            "scanMethod",
            "uriInjectionUsed",
            "routeScope",
            "queryKeyCount",
            "listenerPortAtObservation",
            "endpointReusable",
            "payloadSha256",
            "fullPayloadRetained",
        },
        ("observedMilestones",): {
            "pairingQrSourceConnected",
            "pairingRequestSent",
            "pairingResultReceived",
            "helloSent",
            "authenticationChallengeReceived",
            "authenticationResponseCompleted",
            "runtimeHealthCompleted",
            "trustedDeviceReportedByMacos",
            "bonjourReconnectAfterForceStop",
            "storedTrustAuthenticationCompleted",
            "runtimeHealthAfterReconnect",
        },
        ("retention",): {
            "rawLogcatRetained",
            "screenCaptureRetainedInRepository",
            "completeQrVerifierOutputRetained",
            "apkDigestRetained",
            "sanitizedManifestRetained",
            "sensitiveMaterialIncluded",
        },
        ("proofBoundary",): {"proves", "doesNotProve"},
    }
    for path, allowed_keys in allowed_keys_by_path.items():
        value = read_path(path)
        if not isinstance(value, dict):
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: expected object at "
                f"{'.'.join(path) or '<root>'}."
            )
            continue
        actual_keys = set(value)
        if actual_keys != allowed_keys:
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: closed schema mismatch at "
                f"{'.'.join(path) or '<root>'}; missing={sorted(allowed_keys - actual_keys)}, "
                f"unexpected={sorted(actual_keys - allowed_keys)}."
            )

    forbidden_key_names = {
        "serial",
        "deviceserial",
        "fullpayload",
        "fullqrpayload",
        "fullqruri",
        "verifieroutput",
        "completeqrverifieroutput",
        "pairingcode",
        "pairingnonce",
        "nonce",
        "relaysecret",
        "allocationtoken",
        "routetoken",
        "privatekey",
        "identityprivatekey",
        "privateidentitymaterial",
        "devicecredential",
        "devicecredentials",
    }
    sensitive_string_patterns = (
        re.compile(r"\baetherlink\s*:\s*//\s*pair\b", re.IGNORECASE),
        re.compile(
            r"\b(?:pairing[\s_-]*(?:code|nonce)|nonce|secret|token|"
            r"relay[\s_-]*secret|allocation[\s_-]*token|route[\s_-]*token|"
            r"private[\s_-]*(?:key|identity))\b\s*[:=]",
            re.IGNORECASE,
        ),
    )

    def reject_sensitive_content(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
                if normalized_key in forbidden_key_names:
                    failures.append(
                        "docs/evidence/physical-qr-pairing-20260719.json: prohibited sensitive key "
                        f"{'.'.join(path + (key,))}."
                    )
                reject_sensitive_content(child, path + (key,))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                reject_sensitive_content(child, path + (str(index),))
        elif isinstance(value, str) and any(
            pattern.search(value) for pattern in sensitive_string_patterns
        ):
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: prohibited credential-like string value at "
                f"{'.'.join(path) or '<root>'}."
            )

    reject_sensitive_content(document)

    expected_values = (
        (("documentType",), "aetherlink.physical-qr-pairing-observation"),
        (("schemaVersion",), 1),
        (("recordedDate",), "2026-07-19"),
        (("source", "repository"), "/Users/hanchangha/Desktop/project"),
        (("source", "branch"), "main"),
        (("source", "headAtObservation"), "df19c53a"),
        (("source", "worktreeDirty"), True),
        (("source", "exactTreeDigestRetained"), False),
        (("source", "laterSourceDelta"), "macos_ui_and_launcher_only_without_android_retest"),
        (("device", "model"), "SM-S936N"),
        (("device", "operatingSystem"), "Android 16"),
        (("device", "apiLevel"), 36),
        (("device", "appBuildVariant"), "debug"),
        (("device", "deviceIdentifierRetained"), False),
        (("topology", "runtimeHost"), "macos_development_app"),
        (("topology", "deviceAndRuntimeNetwork"), "same_wifi_lan"),
        (("topology", "usbRouteUsedForOpticalClaim"), False),
        (("topology", "externalRelayUsed"), False),
        (("topology", "p2pNatTraversalUsed"), False),
        (("qrObservation", "captureSurface"), "actual_macos_window_screen"),
        (("qrObservation", "scanMethod"), "physical_android_camera"),
        (("qrObservation", "uriInjectionUsed"), False),
        (("qrObservation", "routeScope"), "local_diagnostic"),
        (("qrObservation", "queryKeyCount"), 11),
        (("qrObservation", "listenerPortAtObservation"), 43170),
        (("qrObservation", "endpointReusable"), False),
        (("qrObservation", "payloadSha256"), "efc77b1402ed6270b741e5ee69bb30a7527ad563876f58eee31e7587ef9544ef"),
        (("qrObservation", "fullPayloadRetained"), False),
        (("observedMilestones", "pairingQrSourceConnected"), True),
        (("observedMilestones", "pairingRequestSent"), True),
        (("observedMilestones", "pairingResultReceived"), True),
        (("observedMilestones", "helloSent"), True),
        (("observedMilestones", "authenticationChallengeReceived"), True),
        (("observedMilestones", "authenticationResponseCompleted"), True),
        (("observedMilestones", "runtimeHealthCompleted"), True),
        (("observedMilestones", "trustedDeviceReportedByMacos"), True),
        (("observedMilestones", "bonjourReconnectAfterForceStop"), True),
        (("observedMilestones", "storedTrustAuthenticationCompleted"), True),
        (("observedMilestones", "runtimeHealthAfterReconnect"), True),
        (("retention", "rawLogcatRetained"), False),
        (("retention", "screenCaptureRetainedInRepository"), False),
        (("retention", "completeQrVerifierOutputRetained"), False),
        (("retention", "apkDigestRetained"), False),
        (("retention", "sanitizedManifestRetained"), True),
        (("retention", "sensitiveMaterialIncluded"), False),
        (("proofBoundary", "proves"), [
            "one_same_wifi_debug_optical_pairing",
            "challenge_response_and_runtime_health",
            "one_stored_trust_bonjour_reconnect",
        ]),
        (("proofBoundary", "doesNotProve"), [
            "release_apk_camera_pairing",
            "expired_or_rotated_qr_recovery",
            "camera_permission_recovery",
            "talkback_or_voiceover",
            "different_network_pairing",
            "external_relay_operation",
            "p2p_nat_or_phase_b",
            "production_capacity_reliability_or_readiness",
        ]),
    )
    for path, expected in expected_values:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )

    payload_digest = read_path(("qrObservation", "payloadSha256"))
    if not isinstance(payload_digest, str) or re.fullmatch(r"[0-9a-f]{64}", payload_digest) is None:
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: qrObservation.payloadSha256 must be one lowercase SHA-256 digest."
        )

    if isinstance(payload_digest, str):
        for relative_path in ("docs/progress.md", "docs/qa-evidence.md"):
            path = ROOT / relative_path
            if payload_digest not in path.read_text(encoding="utf-8", errors="replace"):
                failures.append(
                    f"{relative_path}: physical QR payload digest must match the sanitized observation manifest."
                )

    nonclaims = read_path(("proofBoundary", "doesNotProve"))
    required_nonclaims = {
        "release_apk_camera_pairing",
        "different_network_pairing",
        "external_relay_operation",
        "p2p_nat_or_phase_b",
        "production_capacity_reliability_or_readiness",
    }
    if not isinstance(nonclaims, list) or not required_nonclaims.issubset(
        {value for value in nonclaims if isinstance(value, str)}
    ):
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: proofBoundary.doesNotProve must retain release, different-network, relay, P2P/Phase B, and production limits."
        )

    if re.search(r"\baetherlink\s*:\s*(?:\\?/){2}\s*pair\b", raw_text, re.IGNORECASE):
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: full credential-bearing QR URI must not be retained."
        )

    return failures


def main() -> int:
    failures: list[str] = []

    for path in target_files():
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for rule in RULES:
                if rule.pattern.search(line):
                    failures.append(f"{relative}:{line_number}: {rule.name}: {rule.guidance}")

    docs_text = contract_text()
    for contract in CONTRACTS:
        missing = [
            pattern.pattern
            for pattern in contract.required_patterns
            if not pattern.search(docs_text)
        ]
        if missing:
            failures.append(
                f"documentation-contract:{contract.name}: {contract.guidance} "
                f"Missing pattern(s): {', '.join(missing)}"
            )

    for contract in FILE_CONTRACTS:
        target_text = file_contract_text(contract.target)
        if not target_text:
            failures.append(
                f"documentation-file-contract:{contract.name}: Missing target file {contract.target}. "
                f"{contract.guidance}"
            )
            continue
        missing = [
            pattern.pattern
            for pattern in contract.required_patterns
            if not pattern.search(target_text)
        ]
        if missing:
            failures.append(
                f"documentation-file-contract:{contract.name}: {contract.guidance} "
                f"Missing pattern(s): {', '.join(missing)}"
            )

    failures.extend(latest_progress_evidence_failures())
    failures.extend(latest_qa_evidence_failures())
    failures.extend(current_release_qa_evidence_failures())
    failures.extend(release_readback_command_mode_failures())
    failures.extend(syntax_only_no_device_gate_evidence_failures())
    failures.extend(local_release_document_failures())
    failures.extend(macos_packaged_lifecycle_source_failures())
    failures.extend(macos_packaged_lifecycle_evidence_failures())
    failures.extend(
        historical_macos_packaged_lifecycle_evidence_failures()
    )
    failures.extend(historical_local_release_document_failures())
    failures.extend(physical_qr_observation_manifest_failures())

    if failures:
        print("Docs hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Docs hygiene OK across {len(target_files())} current documentation file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
