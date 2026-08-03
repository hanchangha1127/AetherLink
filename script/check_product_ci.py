#!/usr/bin/env python3
"""Validate the bounded G7 non-security product CI subset."""

from __future__ import annotations

import argparse
import hashlib
import io
import importlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable, Optional
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/product-quality.yml"
COPY_HYGIENE_PATH = ROOT / "script/check_copy_hygiene.py"
NO_DEVICE_QUALITY_PATH = ROOT / "script/check_no_device_quality.sh"
ANDROID_CAMERA_LIFECYCLE_TEST_PATH = ROOT / (
    "apps/android/app/src/test/java/com/localagentbridge/android/"
    "PairingQrCameraPermissionActivityRecreationTest.kt"
)
ANDROID_CAMERA_LIFECYCLE_CONFIG = (
    "@Config(sdk = [26, 30, 33, 36])"
)
ANDROID_APP_LANGUAGE_LIFECYCLE_TEST_PATH = ROOT / (
    "apps/android/app/src/test/java/com/localagentbridge/android/"
    "AndroidAppLanguagePlatformLifecycleTest.kt"
)
ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS = (
    '@Config(sdk = [32], qualifiers = "en")',
    '@Config(sdk = [33], qualifiers = "en")',
    '@Config(sdk = [36], qualifiers = "en")',
)
ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS = (
    "api32ColdLaunchAndRecreationPreserveStoredExplicitLanguage",
    "api33ExternalApplicationLocaleWinsAcrossColdLaunchAndRecreation",
    "api36ExplicitEnglishAndFollowSystemConvergeAcrossRecreation",
)
ANDROID_APP_LANGUAGE_LIFECYCLE_SOURCE_SHA256 = (
    "23bc579f5163890bffe24d1689cbbd2e3b97fe38934578a29d27c27763899f68"
)
ANDROID_CAMERA_CONTROLLER_HOST_TEST_PATH = ROOT / (
    "apps/android/app/src/test/java/com/localagentbridge/android/"
    "PairingQrCameraPermissionControllerHostApiMatrixTest.kt"
)
ANDROID_CAMERA_CONTROLLER_HOST_CONFIG = (
    "@Config(sdk = [26, 30, 33, 36])"
)
ANDROID_FONT_SCALE_TEST_PATH = ROOT / (
    "apps/android/app/src/test/java/com/localagentbridge/android/ui/"
    "AndroidCoreSurfaceFontScaleQualificationTest.kt"
)
ANDROID_FONT_SCALE_CONFIG = "@Config(sdk = [35])"
ANDROID_FONT_SCALE_LIST = (
    "val canonicalFontScales = listOf(1f, 1.5f, 2f)"
)
ANDROID_FONT_SCALE_LOCALES = (
    'val supportedLanguageTags = listOf("en", "ko", "ja", "zh-CN", "fr")'
)
ANDROID_FONT_SCALE_FULL_LOCALES = (
    'val fullCoverageLanguageTags = listOf("en", "ko")'
)
ANDROID_FONT_SCALE_METHODS = (
    "coreSurfacesRemainUsableAt100PercentFontScale",
    "coreSurfacesRemainUsableAt150PercentFontScale",
    "coreSurfacesRemainUsableAt200PercentFontScale",
)
CANONICAL_WORKFLOW_SHA256 = (
    "a88d5ba57e1ce6116889adfb76ac048fe90d4d9137ca65c798f4521eb62995fb"
)
CANONICAL_PARSED_WORKFLOW_SHA256 = (
    "48c4d21aa496b262d690800491778f638e6c3730bb6602e12fa632cb9fbad9fa"
)

REQUIRED_WORKFLOW_PREFIX = """name: Product quality (non-security subset)

"on":
  pull_request:
  push:
    branches:
      - main

permissions:
  contents: read

concurrency:
  group: >-
    product-quality-${{ github.workflow }}-${{
    github.event_name == 'pull_request' &&
    github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

defaults:
  run:
    shell: bash

jobs:
"""

JOB_IDS = (
    "macos-product-quality",
    "android-product-quality",
)

TOP_LEVEL_KEYS = (
    "name",
    "on",
    "permissions",
    "concurrency",
    "defaults",
    "jobs",
)

MAIN_RELEASE_CONDITION = (
    "${{ github.event_name == 'push' &&\n"
    "          github.ref == 'refs/heads/main' }}"
)
PULL_REQUEST_CONDITION = "${{ github.event_name == 'pull_request' }}"

SWIFT_FILTER = (
    "DocumentIngestorTests|DocumentTextExtractorTests|DocumentChunkerTests|"
    "DocumentIngestionSanitizerCorpusTests|"
    "AggregatingLlmBackendResidencyTests|ProviderHealthRecoveryTests|"
    "RuntimeModelIdleUnloadPolicyTests|"
    "RuntimeChatContextCompactionPlannerTests|"
    "RuntimeSemanticChatSessionSearchTests|RuntimeSemanticMemorySearchTests|"
    "AppLifecycleTests|"
    "LocalRuntimeMessageRouterTests/"
    "testApplicationTerminationRejectsNewRequestsAndDrainsRetiringTasks|"
    "LocalRuntimeMessageRouterTests/"
    "testApplicationTerminationDrainsRequestBlockedDuringRegistration|"
    "LocalRuntimeMessageRouterTests/"
    "testApplicationTerminationWaitsForChatTitleCancellationDispatch|"
    "LocalRuntimeMessageRouterTests/"
    "testApplicationTerminationWaitsForMemorySummaryCancellationDispatch|"
    "LocalRuntimeMessageRouterTests/"
    "testApplicationTerminationWaitsForDeferredSummaryPublicationAndPersistence|"
    "LocalRuntimeMessageRouterTests/"
    "testApplicationTerminationDrainsFailedDeferredSummaryPublicationWithoutPersistence|"
    "LocalRuntimeMessageRouterTests/"
    "testMemorySummaryDraftGeneratePublishesBeforeBlockingDurableCache|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelTerminationCancelsAndDrainsRuntimeChatRetentionMaintenance|"
    "OllamaBackendHealthTimeoutTests/"
    "testHealthCheckUsesFiveSecondsWhileCatalogRetainsSixtySeconds|"
    "LMStudioBackendHealthTimeoutTests/"
    "testHealthCheckUsesFiveSecondsWhileCatalogRetainsSixtySeconds|"
    "BonjourAdvertiserTests|"
    "LocalPeerServerTests/"
    "testLocalPeerServerReportsListenerStartAndExplicitStop|"
    "LocalPeerServerTests/"
    "testLocalPeerServerOccupiedPortFailsThenSameInstanceRetries|"
    "LocalPeerServerTests/"
    "testPeerAdmissionCannotCrossListenerStopGenerationBoundary|"
    "MacRuntimeConnectionManagerTests/"
    "testStartLocalDefersAdvertisementUntilListenerIsReady|"
    "MacRuntimeConnectionManagerTests/"
    "testStartLocalDefersReadyUntilAdvertisementIsPublished|"
    "MacRuntimeConnectionManagerTests/"
    "testAsyncListenerReadyForwardsImmediateAdvertisementFailure|"
    "MacRuntimeConnectionManagerTests/"
    "testAdvertisementFailureAllowsSamePortRetryAndIgnoresStaleSuccess|"
    "MacRuntimeConnectionManagerTests/"
    "testRefreshWhileAdvertisementPublishesUsesLatestMetadataOnly|"
    "MacRuntimeConnectionManagerTests/"
    "testUnexpectedAdvertisementStopClearsFalseReadyOwnership|"
    "MacRuntimeConnectionManagerTests/"
    "testConcreteLocalListenerDefersAdvertisementAndRetriesAfterOccupiedPort|"
    "MacRuntimeConnectionManagerTests/"
    "testUnexpectedLocalPortCannotRemainStartingOrAdvertising|"
    "MacRuntimeConnectionManagerTests/"
    "testLateLocalFailureStopsOwnershipAndReportsStatus|"
    "MacRuntimeConnectionManagerTests/"
    "testSupersededLocalStatusCallbackCannotStopReplacement|"
    "MacRuntimeConnectionManagerTests/"
    "testStoppedLocalStatusCallbackIsIgnoredAfterExplicitStop|"
    "MacRuntimeConnectionManagerTests/"
    "testStopAllStopsLocalAdvertiserBootstrapAndPairsExactlyOnce|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelSuspendsAndResumesActiveRuntimeOnceAtSamePort|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelSuspendsStartingRuntimeAndIgnoresPreSleepCallbacks|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelDoesNotResumeStoppedOrFailedRuntimeAfterSystemWake|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelStartsReplaceableTransportAndStopsIt|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelUserInterfaceStartCanRetryAfterListenerFailure|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelCanRetryAfterBonjourPublicationFailure|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelLateListenerFailureAllowsSamePortRetryAndIgnoresStaleCallback|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelPortReplacementShowsStartingUntilReady|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelUserInterfaceStartIsIdempotentDuringRouteAllocation|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelDebugUserInterfaceDoesNotGenerateQRCodeWhenRuntimeListenerFails|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelBeginLocalPairingWaitsForListenerReadiness|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelPairingWaitsForBonjourPublication|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelReportsFailedTransportWithoutAdvertising|"
    "PairingRouteNoticeTests/"
    "testRuntimeStartingUsesNeutralReadinessNotice|"
    "AetherLinkLocalizationTests/"
    "testStatusOverviewMapsEachFocusToOnePrimaryAction|"
    "AetherLinkLocalizationTests/"
    "testStatusOverviewRuntimeStartAndRetryActionsUseSelectedLanguage|"
    "AetherLinkLocalizationTests/"
    "testShortTransitionAnimationHonorsReducedMotion|"
    "AetherLinkLocalizationTests/"
    "testVisualAccessibilityOverridesCannotDisableSystemPreferences|"
    "AetherLinkLocalizationTests/"
    "testIncreasedContrastStatusPaletteAndSurfacesRemainLegible|"
    "AetherLinkLocalizationTests/"
    "testRuntimeHistorySelectionUsesNonColorMarkerAndReconcilesKeyboardList|"
    "AetherLinkLocalizationTests/"
    "testConnectionRecoveryExpansionTargetsFirstEditableField|"
    "AetherLinkLocalizationTests/"
    "testPairingDestinationFocusPlanSeparatesKeyboardAndVoiceOverTargets|"
    "AetherLinkLocalizationTests/"
    "testRuntimeTranscriptReasoningUsesFullOpacityAtIncreasedContrast|"
    "AccessibilityAnnouncementTests/"
    "testPairingQRExpiryAnnouncementFiresOnceWithoutCountdownSpam|"
    "AetherLinkRenderSmokeTests/"
    "testRuntimeOverviewPrimaryActionFitsCompactAccessibilityLayoutAcrossLanguages|"
    "AetherLinkRenderSmokeTests/"
    "testReducedMotionStatusAndActivePairingSurfacesRender|"
    "AetherLinkRenderSmokeTests/"
    "testIncreasedContrastAndColorIndependentHistorySurfacesRender"
)
SWIFT_TEST_LIST_PATH = (
    ROOT / ".build/aetherlink-product-ci-swift-test-list-v1.txt"
)
SWIFT_PRODUCT_TEST_COUNT = 222
SWIFT_PRODUCT_TEST_MANIFEST_SHA256 = (
    "b481e814d8e0f7a2385e50fb5d0f0f8d1602f08b608eb373bb8960ce53547815"
)
SWIFT_FOCUSED_TEST_RUN_MARKER_PATH = (
    ROOT / ".build/aetherlink-product-ci-swift-focused-run-marker-v1.json"
)
SWIFT_FOCUSED_TEST_LOG_PATH = (
    ROOT / ".build/aetherlink-product-ci-swift-focused-console-v1.log"
)
SWIFT_FOCUSED_TEST_BINDING_PATH = (
    ROOT / ".build/aetherlink-product-ci-swift-focused-binding-v1.json"
)
SWIFT_FOCUSED_TEST_RUN_MARKER_CONTRACT = (
    "swift-focused-xctest-run-source-v1"
)
SWIFT_FOCUSED_TEST_BINDING_CONTRACT = (
    "swift-focused-xctest-console-binding-v1"
)
SWIFT_FOCUSED_TEST_MAX_LOG_BYTES = 16 * 1024 * 1024
SWIFT_FOCUSED_TEST_RUN_TIMEOUT_SECONDS = 20 * 60
SWIFT_FOCUSED_TEST_TERMINATION_GRACE_SECONDS = 1.0
SWIFT_FOCUSED_TEST_FUTURE_MTIME_TOLERANCE_NS = 5_000_000_000
SWIFT_FOCUSED_PACKAGE_MAX_BYTES = 512 * 1024
SWIFT_FOCUSED_PACKAGE_DUMP_MAX_BYTES = 2 * 1024 * 1024
SWIFT_FOCUSED_PACKAGE_DUMP_TIMEOUT_SECONDS = 15
SWIFT_FOCUSED_PACKAGE_PATH = ROOT / "Package.swift"
SWIFT_FOCUSED_PACKAGE_DUMP_COMMAND = (
    "swift",
    "package",
    "dump-package",
)
SWIFT_FOCUSED_PACKAGE_TARGETS = (
    ("regular", "P2PNATContracts", "apps/macos/P2PNATContracts/Sources"),
    ("regular", "P2PNATConformance", "apps/macos/P2PNATConformance/Sources"),
    ("regular", "RelayServerCore", "apps/macos/RelayServerCore/Sources"),
    ("regular", "BridgeProtocol", "apps/macos/Protocol/Sources"),
    ("regular", "TrustedDevices", "apps/macos/TrustedDevices/Sources"),
    ("regular", "Pairing", "apps/macos/Pairing/Sources"),
    ("regular", "Transport", "apps/macos/Transport/Sources"),
    ("regular", "OllamaBackend", "apps/macos/OllamaBackend/Sources"),
    ("regular", "LMStudioBackend", "apps/macos/LMStudioBackend/Sources"),
    ("regular", "DocumentIngestion", "apps/macos/DocumentIngestion/Sources"),
    ("regular", "CompanionCore", "apps/macos/CompanionCore/Sources"),
    (
        "executable",
        "LocalAgentBridge",
        "apps/macos/LocalAgentBridgeApp/Sources",
    ),
    (
        "executable",
        "RuntimeDevServer",
        "apps/macos/RuntimeDevServer/Sources",
    ),
    ("executable", "AetherLinkRelay", "apps/macos/AetherLinkRelay/Sources"),
    (
        "executable",
        "RuntimeChatSQLiteCrossProcessQA",
        "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources",
    ),
    ("test", "P2PNATContractsTests", "apps/macos/P2PNATContracts/Tests"),
    (
        "test",
        "P2PNATConformanceTests",
        "apps/macos/P2PNATConformance/Tests",
    ),
    ("test", "RelayServerCoreTests", "apps/macos/RelayServerCore/Tests"),
    ("test", "BridgeProtocolTests", "apps/macos/Protocol/Tests"),
    ("test", "TrustedDevicesTests", "apps/macos/TrustedDevices/Tests"),
    ("test", "PairingTests", "apps/macos/Pairing/Tests"),
    ("test", "OllamaBackendTests", "apps/macos/OllamaBackend/Tests"),
    ("test", "TransportTests", "apps/macos/Transport/Tests"),
    ("test", "LMStudioBackendTests", "apps/macos/LMStudioBackend/Tests"),
    ("test", "CompanionCoreTests", "apps/macos/CompanionCore/Tests"),
    (
        "test",
        "LocalAgentBridgeTests",
        "apps/macos/LocalAgentBridgeApp/Tests",
    ),
    (
        "test",
        "DocumentIngestionTests",
        "apps/macos/DocumentIngestion/Tests",
    ),
)
SWIFT_FOCUSED_PACKAGE_SOURCE_PATHS = tuple(
    target_path
    for _, _, target_path in SWIFT_FOCUSED_PACKAGE_TARGETS
)
SWIFT_FOCUSED_RESULT_EXACT_FILES = (
    Path(__file__).resolve(),
    WORKFLOW_PATH,
    SWIFT_FOCUSED_PACKAGE_PATH,
)
SWIFT_FOCUSED_RESULT_SOURCE_ROOTS = tuple(
    ROOT / relative_path
    for relative_path in SWIFT_FOCUSED_PACKAGE_SOURCE_PATHS
)
SWIFT_FOCUSED_RUN_COMMAND = (
    "swift",
    "test",
    "--filter",
    SWIFT_FILTER,
)
G7_NONSECURITY_SWIFT_UI_FILTER = (
    r"^LocalAgentBridgeTests\."
    r"(?:AppLifecycleTests|PackagedStateRecoveryProbeTests|"
    r"StatusQuickActionsDisclosureTests)/[A-Za-z0-9_]+$"
)
G7_NONSECURITY_SWIFT_UI_TEST_COUNT = 22
G7_NONSECURITY_SWIFT_UI_TEST_MANIFEST_SHA256 = (
    "d28c2530a3b8c2b06b167d33dc157d7b17ec80ecebf193cfaf68c7fc8b6e4315"
)
G7_NONSECURITY_SWIFT_MODULE_FILTER = (
    r"^(?:DocumentIngestionTests\."
    r"(?:DocumentChunkerTests|DocumentIngestionGenerationalMutationTests|"
    r"DocumentIngestionSanitizerCorpusTests|DocumentIngestorTests|"
    r"DocumentTextExtractorTests)|LMStudioBackendTests\."
    r"(?:LMStudioBackendHealthTimeoutTests|LMStudioBackendTests)|"
    r"OllamaBackendTests\."
    r"(?:OllamaBackendHealthTimeoutTests|OllamaBackendTests|"
    r"OllamaEmbeddingSemanticQualityTests|"
    r"OllamaEmbeddingMultilingualFullMatrixV3Tests|"
    r"OllamaEmbeddingMultilingualSemanticQualityTests))/[A-Za-z0-9_]+$"
)
G7_NONSECURITY_SWIFT_MODULE_TEST_COUNT = 236
G7_NONSECURITY_SWIFT_MODULE_TEST_MANIFEST_SHA256 = (
    "e3f833161f53988006f1f7a63496573ad6feb16418ac0dddd363b294f59473ff"
)
G7_NONSECURITY_SWIFT_LIVE_TESTS = (
    (
        "LMStudioBackendTests.LMStudioBackendTests/"
        "testLiveLMStudioConfirmedUnload"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaConfirmedUnload"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaExactVersionEmptyCatalogCompatibility"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaExactVersionInstalledChatModelCompatibility"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaExactVersionInstalledEmbeddingModelCompatibility"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaExactVersionInstalledEmbeddingSemanticQuality"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaExactVersionInstalledEmbeddingSemanticRecovery"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaExactVersionInstalledVisionModelCompatibility"
    ),
    (
        "OllamaBackendTests.OllamaBackendTests/"
        "testLiveOllamaExactVersionProviderFaultInjection"
    ),
    (
        "OllamaBackendTests."
        "OllamaEmbeddingMultilingualFullMatrixV3Tests/"
        "testLiveOllamaExactVersionInstalledEmbeddingMultilingualFullMatrixObservationV3"
    ),
    (
        "OllamaBackendTests."
        "OllamaEmbeddingMultilingualSemanticQualityTests/"
        "testLiveOllamaExactVersionInstalledEmbeddingMultilingualSemanticQuality"
    ),
)
G7_NONSECURITY_SWIFT_LIVE_TEST_COUNT = 11
G7_NONSECURITY_SWIFT_LIVE_TEST_MANIFEST_SHA256 = (
    "46cdf7463d9e18aec2dabadc992dead68b60e4b26191b9905238bb54123c5d72"
)
G7_NONSECURITY_SWIFT_SAFE_MODULE_FILTER = (
    r"^(?!.*\/testLive)(?:DocumentIngestionTests\."
    r"(?:DocumentChunkerTests|DocumentIngestionGenerationalMutationTests|"
    r"DocumentIngestionSanitizerCorpusTests|DocumentIngestorTests|"
    r"DocumentTextExtractorTests)|LMStudioBackendTests\."
    r"(?:LMStudioBackendHealthTimeoutTests|LMStudioBackendTests)|"
    r"OllamaBackendTests\."
    r"(?:OllamaBackendHealthTimeoutTests|OllamaBackendTests|"
    r"OllamaEmbeddingSemanticQualityTests|"
    r"OllamaEmbeddingMultilingualFullMatrixV3Tests|"
    r"OllamaEmbeddingMultilingualSemanticQualityTests))/[A-Za-z0-9_]+$"
)
G7_NONSECURITY_SWIFT_SAFE_MODULE_TEST_COUNT = 225
G7_NONSECURITY_SWIFT_SAFE_MODULE_TEST_MANIFEST_SHA256 = (
    "3cf5fb6c09efd78dcf7fc688e2f1aca3d57fe831d33672d2a8f95faee17f76d5"
)
G7_NONSECURITY_SWIFT_FILTER = (
    r"^(?:LocalAgentBridgeTests\."
    r"(?:AppLifecycleTests|PackagedStateRecoveryProbeTests|"
    r"StatusQuickActionsDisclosureTests)|DocumentIngestionTests\."
    r"(?:DocumentChunkerTests|DocumentIngestionGenerationalMutationTests|"
    r"DocumentIngestionSanitizerCorpusTests|DocumentIngestorTests|"
    r"DocumentTextExtractorTests)|LMStudioBackendTests\."
    r"(?:LMStudioBackendHealthTimeoutTests|LMStudioBackendTests)|"
    r"OllamaBackendTests\."
    r"(?:OllamaBackendHealthTimeoutTests|OllamaBackendTests|"
    r"OllamaEmbeddingSemanticQualityTests|"
    r"OllamaEmbeddingMultilingualFullMatrixV3Tests|"
    r"OllamaEmbeddingMultilingualSemanticQualityTests))/[A-Za-z0-9_]+$"
)
G7_NONSECURITY_SWIFT_TEST_COUNT = 247
G7_NONSECURITY_SWIFT_TEST_MANIFEST_SHA256 = (
    "9ad12d0f8b909021046f6b00cdd989dc41010af85d02febd424a4fb6edaf861c"
)
G7_NONSECURITY_SWIFT_FOCUSED_OVERLAP_COUNT = 72
G7_NONSECURITY_SWIFT_DISTINCT_TEST_COUNT = 397
G7_NONSECURITY_SWIFT_SAFE_TARGET_COUNTS = {
    "DocumentIngestionTests.": 59,
    "LMStudioBackendTests.": 71,
    "OllamaBackendTests.": 95,
}
G7_NONSECURITY_SWIFT_SKIP_FILTER = (
    "^(?:"
    + "|".join(re.escape(identity) for identity in G7_NONSECURITY_SWIFT_LIVE_TESTS)
    + ")$"
)
G7_NONSECURITY_SWIFT_SANDBOX_PROFILE = (
    "(version 1)(allow default)(deny network*)"
)
G7_NONSECURITY_SWIFT_NETWORK_PROBE_SCRIPT = r"""
import errno
import socket

denied = {errno.EACCES, errno.EPERM}
cases = (
    (socket.AF_INET, ("127.0.0.1", 0), ("127.0.0.1", 9)),
    (socket.AF_INET6, ("::1", 0), ("::1", 9)),
)
for case_index, (family, bind_address, connect_address) in enumerate(cases):
    for operation_index, (operation, address) in enumerate(
        (("bind", bind_address), ("connect", connect_address))
    ):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as candidate:
                if operation == "bind":
                    candidate.bind(address)
                else:
                    candidate.settimeout(0.25)
                    candidate.connect(address)
        except OSError as error:
            if error.errno in denied:
                continue
            raise SystemExit(20 + case_index * 4 + operation_index)
        raise SystemExit(40 + case_index * 4 + operation_index)
"""
G7_NONSECURITY_SWIFT_NETWORK_PROBE_COMMAND = (
    "/usr/bin/sandbox-exec",
    "-p",
    G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
    "/usr/bin/python3",
    "-I",
    "-B",
    "-S",
    "-c",
    G7_NONSECURITY_SWIFT_NETWORK_PROBE_SCRIPT,
)
G7_NONSECURITY_SWIFT_RUN_COMMAND = (
    "/usr/bin/sandbox-exec",
    "-p",
    G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
    "/usr/bin/swift",
    "test",
    "--disable-sandbox",
    "--no-parallel",
    "--filter",
    G7_NONSECURITY_SWIFT_FILTER,
    "--skip",
    G7_NONSECURITY_SWIFT_SKIP_FILTER,
)
G7_NONSECURITY_SWIFT_RUN_MARKER_PATH = ROOT / (
    ".build/aetherlink-g7-nonsecurity-swift-run-marker-v1.json"
)
G7_NONSECURITY_SWIFT_LOG_PATH = ROOT / (
    ".build/aetherlink-g7-nonsecurity-swift-console-v1.log"
)
G7_NONSECURITY_SWIFT_BINDING_PATH = ROOT / (
    ".build/aetherlink-g7-nonsecurity-swift-binding-v1.json"
)
G7_NONSECURITY_SWIFT_ALLOWED_ENVIRONMENT_KEYS = (
    "DEVELOPER_DIR",
    "HOME",
    "PATH",
    "SDKROOT",
    "TMPDIR",
    "TOOLCHAINS",
)
DOCUMENT_INGESTION_ASAN_FILTER = (
    r"^DocumentIngestionTests\."
    r"(DocumentIngestionSanitizerCorpusTests|DocumentIngestorTests|"
    r"DocumentTextExtractorTests|DocumentChunkerTests)/"
)
DOCUMENT_INGESTION_ASAN_TEST_COUNT = 57
DOCUMENT_INGESTION_ASAN_TEST_MANIFEST_SHA256 = (
    "71b37b2f02a4b8ef65c9e82011259345c86015572480274f1417ed16f5d9b690"
)
DOCUMENT_INGESTION_ASAN_RUN_MARKER_PATH = ROOT / (
    ".build/aetherlink-document-ingestion-asan-run-marker-v1.json"
)
DOCUMENT_INGESTION_ASAN_LOG_PATH = ROOT / (
    ".build/aetherlink-document-ingestion-asan-console-v1.log"
)
DOCUMENT_INGESTION_ASAN_BINDING_PATH = ROOT / (
    ".build/aetherlink-document-ingestion-asan-binding-v1.json"
)
DOCUMENT_INGESTION_ASAN_SCRATCH_PATH = (
    ".build/aetherlink-document-ingestion-asan-v1"
)
DOCUMENT_INGESTION_ASAN_RUN_TIMEOUT_SECONDS = 12 * 60
DOCUMENT_INGESTION_ASAN_RUN_COMMAND = (
    "swift",
    "test",
    "--scratch-path",
    DOCUMENT_INGESTION_ASAN_SCRATCH_PATH,
    "--sanitize",
    "address",
    "--no-parallel",
    "--filter",
    DOCUMENT_INGESTION_ASAN_FILTER,
)
DOCUMENT_INGESTION_MUTATION_FILTER = (
    r"^DocumentIngestionTests\."
    r"DocumentIngestionGenerationalMutationTests/"
)
DOCUMENT_INGESTION_MUTATION_TEST_COUNT = 2
DOCUMENT_INGESTION_MUTATION_TEST_MANIFEST_SHA256 = (
    "268e426f7d7c69629188c444093f044efe1952628c2e4c20923c512aaf17f05b"
)
DOCUMENT_INGESTION_MUTATION_CASE_COUNT = 96
DOCUMENT_INGESTION_MUTATION_ROOT_SEED = "a37e2c915b04d8f6"
DOCUMENT_INGESTION_MUTATION_MARKER_MANIFEST_SHA256 = (
    "bd6e38cbac664aca4e7d4d912fddd1f853b93dfc5b862751921848d885d1e379"
)
DOCUMENT_INGESTION_MUTATION_FORMATS = (
    "txt",
    "xml",
    "html",
    "rtf",
    "pdf",
    "docx",
    "epub",
    "webarchive",
)
DOCUMENT_INGESTION_MUTATION_PRIMARY_OPERATORS = (
    "identity",
    "truncate",
    "delete_span",
    "insert_span",
    "overwrite_span",
    "flip_bit",
    "flip_high_bits",
    "duplicate_span",
    "splice_seed",
    "reverse_span",
    "pad_exact_4096",
    "pad_plus_one_4097",
)
DOCUMENT_INGESTION_MUTATION_RUN_MARKER_PATH = ROOT / (
    ".build/aetherlink-document-ingestion-mutation-run-marker-v1.json"
)
DOCUMENT_INGESTION_MUTATION_LOG_PATH = ROOT / (
    ".build/aetherlink-document-ingestion-mutation-console-v1.log"
)
DOCUMENT_INGESTION_MUTATION_BINDING_PATH = ROOT / (
    ".build/aetherlink-document-ingestion-mutation-binding-v1.json"
)
DOCUMENT_INGESTION_MUTATION_RUN_TIMEOUT_SECONDS = 5 * 60
DOCUMENT_INGESTION_MUTATION_RUN_COMMAND = (
    "swift",
    "test",
    "--scratch-path",
    DOCUMENT_INGESTION_ASAN_SCRATCH_PATH,
    "--sanitize",
    "address",
    "--no-parallel",
    "--filter",
    DOCUMENT_INGESTION_MUTATION_FILTER,
)
DOCUMENT_INGESTION_MUTATION_TEST_IDENTITY = (
    "DocumentIngestionTests.DocumentIngestionGenerationalMutationTests/"
    "testBoundedGenerationalMutationsHaveSafeOutcomes"
)
DOCUMENT_INGESTION_MUTATION_MARKER_PATTERN = re.compile(
    r"AETHERLINK_DOCUMENT_MUTATION_V1 "
    r"case=(?P<case>[0-9]{3}) total=(?P<total>[0-9]{3}) "
    r"generator=splitmix64-v1 root=(?P<root>[0-9a-f]{16}) "
    r"seed=(?P<seed>[0-9a-f]{16}) "
    r"format=(?P<format>[a-z]+) "
    r"operators=(?P<operators>[a-z0-9_]+(?:,[a-z0-9_]+){0,3}) "
    r"bytes=(?P<bytes>0|[1-9][0-9]{0,3}) "
    r"sha256=(?P<sha256>[0-9a-f]{64})"
)
DOCUMENT_INGESTION_MUTATION_SUMMARY_PATTERN = re.compile(
    r"AETHERLINK_DOCUMENT_MUTATION_SUMMARY_V1 "
    r"total=(?P<total>[0-9]{3}) "
    r"root=(?P<root>[0-9a-f]{16}) "
    r"manifest_sha256=(?P<manifest>[0-9a-f]{64})"
)

ANDROID_TESTS = (
    "com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest",
    "com.localagentbridge.android.ResearchNotebookDrawerTest",
    (
        "com.localagentbridge.android.runtime."
        "RuntimeAttachmentPromptResourceTest"
    ),
    (
        "com.localagentbridge.android.AppNavigationTest."
        "androidAppLocaleOverrideSyncDistinguishesExplicitEnglishFromFollowSystem"
    ),
    (
        "com.localagentbridge.android.runtime.RuntimeLocalStoreTest."
        "androidPlatformLanguageSnapshotUsesApi33OverrideAndPreservesLegacyExplicitChoice"
    ),
    (
        "com.localagentbridge.android.runtime.RuntimeClientViewModelTest."
        "viewModelReconcilesAuthoritativeAndroidAppLanguageSnapshotWithoutDuplicateSaves"
    ),
    (
        "com.localagentbridge.android."
        "AndroidAppLanguagePlatformLifecycleTest"
    ),
    (
        "com.localagentbridge.android.ui."
        "AndroidCoreSurfaceFontScaleQualificationTest"
    ),
    (
        "com.localagentbridge.android."
        "PairingQrScannerChromeNoDeviceComposeTest"
    ),
    (
        "com.localagentbridge.android."
        "PairingQrCameraPermissionControllerHostApiMatrixTest"
    ),
    (
        "com.localagentbridge.android."
        "PairingQrCameraPermissionActivityRecreationTest"
    ),
    (
        "com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest."
        "chatScreenSessionBoundaryResetsLatestWhileSameSessionUpdatesKeepPosition"
    ),
)

ANDROID_MAIN_FULL_TESTS = (
    "com.localagentbridge.android.AppNavigationTest",
    (
        "com.localagentbridge.android."
        "AndroidAppLanguagePlatformLifecycleTest"
    ),
    "com.localagentbridge.android.ResearchNotebookDrawerTest",
    "com.localagentbridge.android.PairingQrScanResultTest",
    "com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest",
    (
        "com.localagentbridge.android.ui."
        "AndroidCoreSurfaceFontScaleQualificationTest"
    ),
    (
        "com.localagentbridge.android."
        "PairingQrScannerChromeNoDeviceComposeTest"
    ),
    (
        "com.localagentbridge.android."
        "PairingQrCameraPermissionControllerHostApiMatrixTest"
    ),
    (
        "com.localagentbridge.android."
        "PairingQrCameraPermissionActivityRecreationTest"
    ),
    (
        "com.localagentbridge.android.ui."
        "ClientScreensNoDeviceComposeTest"
    ),
    "com.localagentbridge.android.AndroidBackupPolicyResourceTest",
    (
        "com.localagentbridge.android.runtime."
        "RuntimeClientViewModelRelayIntegrationTest"
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeClientViewModelProductionDeadlineTest"
    ),
    (
        "com.localagentbridge.android.runtime."
        "AndroidProductionRuntimeChannelComposerTest"
    ),
    (
        "com.localagentbridge.android.runtime."
        "AndroidProductionRuntimeActivationControllerTest"
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeLocalStoreTest"
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeClientViewModelTest"
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeClientChatSessionMutationFailureTest"
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeAttachmentPromptResourceTest"
    ),
)

ANDROID_CORE_NONSECURITY_PROTOCOL_CLASS_NAME = (
    "com.localagentbridge.android.core.protocol.ProtocolCodecTest"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_SOURCE_PATH = ROOT / (
    "apps/android/core/protocol/src/test/java/com/localagentbridge/android/"
    "core/protocol/ProtocolCodecTest.kt"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_METHODS = (
    "encodesAndDecodesLengthPrefixedFrame",
    "encodesAndReadsFrameBodySeparatelyFromLengthPrefix",
    "readsFragmentedFrameIntoExactDestinationAndRejectsTruncation",
    "errorPayloadDecodesNonRetryableChatContextWindowExceeded",
    "decodeRejectsMalformedRequiredEnvelopeFields",
    "decodeRejectsUnsupportedVersionAndBlankRequestId",
    "decodeAllowsMessageSpecificMetadataInsidePayloadObject",
    "helloPayloadEnforcesOptionalUniqueNonblankUtf8CapabilitiesAnd64EntryLimit",
    "protocolSchemaPins64CapabilitiesAndStrictResearchNotebookSyncBranches",
    "chatSendRequestRejectsInvalidBounds",
    "modelInfoPayloadCanCarryContextWindowMetadata",
    "modelInfoPayloadPreservesProviderAndEmbeddingMetadata",
    "modelsResultPayloadEnforcesExactCatalogRowLimitWithoutTruncation",
    "modelInfoPayloadUsesUnicodeCodePointLimitsForIdentityStrings",
    "modelInfoPayloadUsesUnicodeCodePointLimitForQualifiedId",
    "modelInfoPayloadUsesSharedCatalogBlankCodePointSet",
    "modelInfoPayloadEnforcesCapabilityCountAndUnicodeItemLimits",
    "modelInfoPayloadEnforcesExactSizeByteMaximum",
    "modelInfoPayloadEnforcesExactContextWindowMaximum",
    "modelInfoPayloadRejectsInvalidScalarMetadata",
    "modelInfoPayloadRejectsInvalidModifiedAtMetadata",
    "modelInfoPayloadRejectsInvalidNumericMetadata",
    "modelInfoPayloadDefaultsMissingCapabilitiesToEmptyList",
    "runtimeHealthBackendStatusAcceptsSchemaMinimalPayload",
    "runtimeHealthPayloadRejectsInvalidStatus",
    "runtimeHealthPayloadCanCarryModelResidencySnapshot",
    "runtimeHealthPayloadRejectsInvalidModelResidencyBounds",
    "chatHistorySessionPayloadsUseProtocolFieldNames",
    "chatSessionsAuthoritativeSyncPayloadsUseExactWireShapes",
    "chatSessionsListCursorRejectsInvalidAndMixedPayloads",
    "chatSessionsListPaginationResponseRejectsInvalidMetadata",
    "chatSessionsBulkLifecyclePayloadsRejectInvalidDomainsAndBounds",
    "chatSessionsSyncPayloadsRejectUnknownFieldsWithPermissiveJson",
    "chatSessionsListRequestRejectsInvalidBounds",
    "chatSessionsListResponseRejectsInvalidBounds",
    "indexDocumentsListPayloadUsesProtocolFieldNames",
    "indexDocumentsListRequestRejectsInvalidBounds",
    "indexDocumentsListResponseRejectsInvalidDocumentMetadataBounds",
    "indexDocumentsListResponseRejectsInvalidSummaryBounds",
    "retrievalAndSourceAnchorDocumentMetadataRejectsInvalidBounds",
    "retrievalQueryResponseRejectsTooManyResults",
    "retrievalQueryPayloadUsesProtocolFieldNames",
    "retrievalQueryRequestSerializesEmbeddingModelHintAndRejectsBlankHint",
    "retrievalQueryMatchKindDefaultsLexicalAndControlsMatchedTermsBounds",
    "retrievalQueryRequestRejectsInvalidBounds",
    "sourceAnchorResolvePayloadUsesProtocolFieldNames",
    "indexDocumentsListRejectsNonCanonicalContentFingerprints",
    "retrievalQueryResultRejectsNonCanonicalDocumentContentFingerprints",
    "sourceAnchorResolveResultRejectsNonCanonicalDocumentContentFingerprints",
    "sourceAnchorResolveRequestRejectsMissingRequiredField",
    "sourceAnchorResolveRequestRejectsNonCanonicalSourceAnchorIds",
    "sourceAnchorResolveResultRejectsMissingRequiredFields",
    "sourceAnchorResolveResultRejectsInvalidChunkSummaryValues",
    "sourceAnchorResolveResultRejectsNonCanonicalSourceAnchorIds",
    "retrievalQueryResultRejectsMissingSourceAnchorId",
    "retrievalQueryResultRejectsNonCanonicalSourceAnchorIds",
    "retrievalQueryResultRejectsInvalidCoordinatesAndRank",
    "retrievalQueryResultRejectsInvalidLexicalMetadata",
    "retrievalQueryResultRejectsMissingMatchedTerms",
    "researchNotebooksListRequestRequiresExplicitTypedBoundedFields",
    "researchNotebooksListCapableResponseRejectsBranchMixingAndInvalidSnapshotMetadata",
    "researchNotebooksAuthoritativeSyncFixtureGenerates201RowsAcross1001001Pages",
    "chatSourceAttributionsUseExactSafeWireShapeAndRemainOptional",
    "chatMessagesListRequestRejectsInvalidBounds",
    "chatSessionRenamePayloadUsesProtocolFieldNames",
    "chatTitleAndSessionMutationRequestsRejectInvalidBounds",
    "chatDeltaPayloadAcceptsCompatibilityAliases",
    "chatStreamResponsePayloadsRejectInvalidBounds",
    "modelPullAndChatCancelRequestsRejectInvalidBounds",
    "memoryPayloadsUseProtocolFieldNames",
    "memoryListRequestRejectsInvalidBounds",
    "memoryDuplicateSuggestionsPayloadUsesClosedCanonicalContract",
    "memoryDuplicateSuggestionsPayloadRejectsMalformedOrNoncanonicalGroups",
    "memoryDuplicateSuggestionsPayloadUsesUnsignedUtf8OrderingForBmpAndAstralIds",
    "memoryDuplicateSuggestionsPayloadRejectsJsonEscapedUnpairedSurrogateId",
    "memoryDuplicateSuggestionsPayloadUsesSharedAggregateUtf8IdBudget",
    "memoryDuplicateSuggestionsPayloadRejectsUnknownFields",
    "memorySemanticDuplicateSuggestionsPayloadUsesCanonicalWireContract",
    "memorySemanticDuplicateSuggestionsRequestRejectsBoundsAndInvalidTypes",
    "memorySemanticDuplicateSuggestionsResponseRejectsBoundsAndInvalidTypes",
    "memorySemanticDuplicateSuggestionsEnforcesPairShapeOrderAndDuplicates",
    "memorySemanticDuplicateSuggestionsUsesUnsignedUtf8AndAllowsIdsAcrossPairs",
    "memorySemanticDuplicateSuggestionsEnforcesAggregateUtf8IdBudget",
    "memorySemanticDuplicateClustersPayloadUsesCanonicalWireContract",
    "memorySemanticDuplicateClustersRequestRejectsBoundsUnknownFieldsAndInvalidTypes",
    "memorySemanticDuplicateClustersEnforcesShapeDisjointnessCountsAndOrder",
    "memorySemanticDuplicateClustersRejectsResponseTypesMetadataUnicodeAndIdBudget",
    "memoryCrudRequestsRejectInvalidBounds",
    "memorySummaryDraftsListPayloadUsesProtocolFieldNames",
    "memorySummaryDraftsListRequestRejectsInvalidBounds",
    "memorySummaryDraftGeneratePayloadRoundTripsExactWireShape",
    "memorySummaryDraftResponsePayloadsRejectInvalidBounds",
    "memorySummaryDraftApprovePayloadUsesProtocolFieldNamesAndAcceptsGeneratedSource",
    "memorySummaryDraftDecisionRequestsRejectInvalidBounds",
    "memorySummaryDraftDismissPayloadUsesProtocolFieldNames",
    "chatAndMemoryPayloadsRejectInvalidTimestampMetadata",
)
ANDROID_CORE_NONSECURITY_TRANSPORT_CLASS_NAME = (
    "com.localagentbridge.android.core.transport.RuntimeTransportClientTest"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_SOURCE_PATH = ROOT / (
    "apps/android/core/transport/src/test/java/com/localagentbridge/android/"
    "core/transport/RuntimeTransportClientTest.kt"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_METHODS = (
    "rawSendWritesOneCompleteLengthPrefixedBodyAndFlushes",
    "rawReceiveReturnsBodyBeforeJsonDecode",
    "rawConnectionRejectsProtocolApiAndClosesTheSocket",
    "invalidRawBodyLengthFailsClosedBeforeWriting",
    "rawSendBacklogOverflowFailsClosedAndReleasesBlockedSender",
    "cancellingBlockedRawSendClosesSocketAndReleasesWriterBoundedly",
    "oldRawHandleCannotSendReceiveOrCloseReplacementGeneration",
    "sendWritesOneCompleteProtocolFrame",
    "concurrentSendsRemainSerializedAsCompleteProtocolFrames",
    "partialFrameWriteFailureClosesCurrentSocketAndLeavesClientDisconnected",
    "flushFailureClosesCurrentSocketAndLeavesClientDisconnected",
    "queuedSendDoesNotCrossReconnectOnSameClientObject",
    "closeOwnsInFlightSocketAndStaleCompletionCannotPublish",
    "cancellationOwnsAndClosesInFlightSocketBoundedly",
    "laterConnectWinsWhenEarlierBarrierSocketCompletesStale",
    "cancellingBlockingReceiveClosesOnlyCapturedSocketAndCompletesBoundedly",
)
ANDROID_CORE_NONSECURITY_TRANSPORT_ADDON_SELECTIONS = (
    (
        "com.localagentbridge.android.core.transport.BonjourDiscoveryTest",
        ROOT / (
            "apps/android/core/transport/src/test/java/"
            "com/localagentbridge/android/core/transport/"
            "BonjourDiscoveryTest.kt"
        ),
        (
            "synchronousDiscoveryStartFailureReleasesLifecycleResourceExactlyOnce",
        ),
    ),
    (
        "com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest",
        ROOT / (
            "apps/android/core/transport/src/test/java/"
            "com/localagentbridge/android/core/transport/"
            "RuntimeConnectionManagerTest.kt"
        ),
        (
            "endpointHintRejectsInvalidEndpoint",
            "productionCompositionTimeoutUsesSaturatingAddition",
        ),
    ),
    (
        "com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest",
        ROOT / (
            "apps/android/core/transport/src/test/java/"
            "com/localagentbridge/android/core/transport/"
            "RuntimeRelayTcpClientTest.kt"
        ),
        (
            "relayFrameWriterEmitsExactPrefixThenBodyAtBoundarySizes",
            "relayFrameWriterRejectsEmptyAndOversizedBodiesBeforeWriting",
        ),
    ),
)
ANDROID_CORE_NONSECURITY_PROTOCOL_SELECTIONS = (
    (
        ANDROID_CORE_NONSECURITY_PROTOCOL_CLASS_NAME,
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_SOURCE_PATH,
        ANDROID_CORE_NONSECURITY_PROTOCOL_METHODS,
    ),
)
ANDROID_CORE_NONSECURITY_TRANSPORT_SELECTIONS = (
    (
        ANDROID_CORE_NONSECURITY_TRANSPORT_CLASS_NAME,
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_SOURCE_PATH,
        ANDROID_CORE_NONSECURITY_TRANSPORT_METHODS,
    ),
) + ANDROID_CORE_NONSECURITY_TRANSPORT_ADDON_SELECTIONS
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_COUNT = 96
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_COUNT = 21
ANDROID_CORE_NONSECURITY_TEST_COUNT = 117
ANDROID_CORE_NONSECURITY_PROTOCOL_TESTS = tuple(
    f"{class_name}.{method}"
    for class_name, _source_path, methods in (
        ANDROID_CORE_NONSECURITY_PROTOCOL_SELECTIONS
    )
    for method in methods
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TESTS = tuple(
    f"{class_name}.{method}"
    for class_name, _source_path, methods in (
        ANDROID_CORE_NONSECURITY_TRANSPORT_SELECTIONS
    )
    for method in methods
)
ANDROID_CORE_NONSECURITY_TESTS = (
    ANDROID_CORE_NONSECURITY_PROTOCOL_TESTS
    + ANDROID_CORE_NONSECURITY_TRANSPORT_TESTS
)
ANDROID_CORE_NONSECURITY_GRADLE_PREFIX = (
    "./gradlew",
    "--offline",
    "--no-daemon",
    "--console=plain",
    "--rerun-tasks",
    "-Pkotlin.incremental=false",
)
ANDROID_CORE_NONSECURITY_PROTOCOL_RUN_COMMAND = (
    ANDROID_CORE_NONSECURITY_GRADLE_PREFIX
    + (":core:protocol:testDebugUnitTest",)
    + tuple(
        argument
        for test in ANDROID_CORE_NONSECURITY_PROTOCOL_TESTS
        for argument in ("--tests", test)
    )
)
ANDROID_CORE_NONSECURITY_TRANSPORT_RUN_COMMAND = (
    ANDROID_CORE_NONSECURITY_GRADLE_PREFIX
    + (":core:transport:testDebugUnitTest",)
    + tuple(
        argument
        for test in ANDROID_CORE_NONSECURITY_TRANSPORT_TESTS
        for argument in ("--tests", test)
    )
)

ANDROID_TASKS = (
    ":app:compileDebugKotlin",
    ":app:compileDebugUnitTestKotlin",
    ":app:testDebugUnitTest",
    ":app:compileDebugKotlin",
    ":app:testDebugUnitTest",
    ":app:assembleRelease",
    ":app:bundleRelease",
    ":app:lintRelease",
)

ANDROID_CAMERA_LIFECYCLE_CLASS_NAME = (
    "com.localagentbridge.android."
    "PairingQrCameraPermissionActivityRecreationTest"
)
ANDROID_APP_LANGUAGE_LIFECYCLE_CLASS_NAME = (
    "com.localagentbridge.android."
    "AndroidAppLanguagePlatformLifecycleTest"
)
ANDROID_CAMERA_CONTROLLER_HOST_CLASS_NAME = (
    "com.localagentbridge.android."
    "PairingQrCameraPermissionControllerHostApiMatrixTest"
)
ANDROID_FONT_SCALE_CLASS_NAME = (
    "com.localagentbridge.android.ui."
    "AndroidCoreSurfaceFontScaleQualificationTest"
)
ANDROID_DRAWER_RUNTIME_SUMMARY_TEST_METHOD = (
    "navigationDrawerRuntimeSummaryStaysBoundedAtLargeFontAcrossSupportedLanguages"
)

ANDROID_PRODUCT_TEST_RESULTS = (
    (
        "com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest",
        4,
        (),
    ),
    (
        "com.localagentbridge.android.ResearchNotebookDrawerTest",
        1,
        (),
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeAttachmentPromptResourceTest",
        1,
        (),
    ),
    (
        "com.localagentbridge.android.AppNavigationTest",
        1,
        (
            "androidAppLocaleOverrideSyncDistinguishesExplicitEnglishFromFollowSystem",
        ),
    ),
    (
        "com.localagentbridge.android.runtime.RuntimeLocalStoreTest",
        1,
        (
            "androidPlatformLanguageSnapshotUsesApi33OverrideAndPreservesLegacyExplicitChoice",
        ),
    ),
    (
        "com.localagentbridge.android.runtime.RuntimeClientViewModelTest",
        1,
        (
            "viewModelReconcilesAuthoritativeAndroidAppLanguageSnapshotWithoutDuplicateSaves",
        ),
    ),
    (
        ANDROID_APP_LANGUAGE_LIFECYCLE_CLASS_NAME,
        3,
        ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS,
    ),
    (
        ANDROID_FONT_SCALE_CLASS_NAME,
        3,
        ANDROID_FONT_SCALE_METHODS,
    ),
    (
        "com.localagentbridge.android."
        "PairingQrScannerChromeNoDeviceComposeTest",
        13,
        (),
    ),
    (
        ANDROID_CAMERA_CONTROLLER_HOST_CLASS_NAME,
        4,
        (
            "controllerHostRunsDenialRegrantRevocationAndResumeLifecycle[26]",
            "controllerHostRunsDenialRegrantRevocationAndResumeLifecycle[30]",
            "controllerHostRunsDenialRegrantRevocationAndResumeLifecycle[33]",
            "controllerHostRunsDenialRegrantRevocationAndResumeLifecycle",
        ),
    ),
    (
        ANDROID_CAMERA_LIFECYCLE_CLASS_NAME,
        12,
        (
            "activityScenarioRecreateRestoresRecordedRequestWithoutRelaunch[26]",
            "activityScenarioRecreateRestoresRecordedRequestWithoutRelaunch[30]",
            "activityScenarioRecreateRestoresRecordedRequestWithoutRelaunch[33]",
            "activityScenarioRecreateRestoresRecordedRequestWithoutRelaunch",
            "coldActivityLaunchRecoversLaunchPendingWithoutAutomaticRelaunch[26]",
            "coldActivityLaunchRecoversLaunchPendingWithoutAutomaticRelaunch[30]",
            "coldActivityLaunchRecoversLaunchPendingWithoutAutomaticRelaunch[33]",
            "coldActivityLaunchRecoversLaunchPendingWithoutAutomaticRelaunch",
            "coldActivityLaunchRestoresRecordedRequestWithoutRelaunch[26]",
            "coldActivityLaunchRestoresRecordedRequestWithoutRelaunch[30]",
            "coldActivityLaunchRestoresRecordedRequestWithoutRelaunch[33]",
            "coldActivityLaunchRestoresRecordedRequestWithoutRelaunch",
        ),
    ),
    (
        "com.localagentbridge.android.ui."
        "ClientScreensNoDeviceComposeTest",
        1,
        (
            "chatScreenSessionBoundaryResetsLatestWhileSameSessionUpdatesKeepPosition",
        ),
    ),
)
ANDROID_PRODUCT_TEST_CASE_MANIFEST_SHA256 = (
    "b0dc7a73bddfead85c8f92be523442e5eaf5ae42740e1a99478cba6ace2909dd"
)

ANDROID_FULL_TEST_RESULTS = (
    (
        "com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest",
        4,
        (),
    ),
    (
        ANDROID_APP_LANGUAGE_LIFECYCLE_CLASS_NAME,
        3,
        (),
    ),
    (
        "com.localagentbridge.android.AndroidBackupPolicyResourceTest",
        6,
        (),
    ),
    (
        "com.localagentbridge.android.AppNavigationTest",
        168,
        (),
    ),
    (
        ANDROID_CAMERA_LIFECYCLE_CLASS_NAME,
        12,
        (),
    ),
    (
        ANDROID_CAMERA_CONTROLLER_HOST_CLASS_NAME,
        4,
        (),
    ),
    (
        "com.localagentbridge.android.PairingQrScanResultTest",
        8,
        (),
    ),
    (
        "com.localagentbridge.android."
        "PairingQrScannerChromeNoDeviceComposeTest",
        13,
        (),
    ),
    (
        "com.localagentbridge.android.ResearchNotebookDrawerTest",
        1,
        (),
    ),
    (
        "com.localagentbridge.android.runtime."
        "AndroidProductionRuntimeActivationControllerTest",
        12,
        (),
    ),
    (
        "com.localagentbridge.android.runtime."
        "AndroidProductionRuntimeChannelComposerTest",
        16,
        (),
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeAttachmentPromptResourceTest",
        1,
        (),
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeClientChatSessionMutationFailureTest",
        14,
        (),
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeClientViewModelProductionDeadlineTest",
        1,
        (),
    ),
    (
        "com.localagentbridge.android.runtime."
        "RuntimeClientViewModelRelayIntegrationTest",
        5,
        (),
    ),
    (
        "com.localagentbridge.android.runtime.RuntimeClientViewModelTest",
        643,
        (),
    ),
    (
        "com.localagentbridge.android.runtime.RuntimeLocalStoreTest",
        16,
        (),
    ),
    (
        ANDROID_FONT_SCALE_CLASS_NAME,
        3,
        (),
    ),
    (
        "com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest",
        296,
        (ANDROID_DRAWER_RUNTIME_SUMMARY_TEST_METHOD,),
    ),
)
ANDROID_FULL_TEST_CASE_MANIFEST_SHA256 = (
    "cc3ea9e2d72ca96e7f937b22a893d8cdaf38c409564ac8baecc5b947b8aa1b78"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RESULTS = (
    (
        ANDROID_CORE_NONSECURITY_PROTOCOL_CLASS_NAME,
        len(ANDROID_CORE_NONSECURITY_PROTOCOL_METHODS),
        ANDROID_CORE_NONSECURITY_PROTOCOL_METHODS,
    ),
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RESULTS = (
    (
        ANDROID_CORE_NONSECURITY_TRANSPORT_CLASS_NAME,
        len(ANDROID_CORE_NONSECURITY_TRANSPORT_METHODS),
        ANDROID_CORE_NONSECURITY_TRANSPORT_METHODS,
    ),
    *tuple(
        (class_name, len(methods), methods)
        for class_name, _source_path, methods in (
            ANDROID_CORE_NONSECURITY_TRANSPORT_ADDON_SELECTIONS
        )
    ),
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_CASE_MANIFEST_SHA256 = (
    "a2e7116511373f5cf62b95efa21162f7d52db4d12bd6d752e2ba84fc49e7ac73"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_CASE_MANIFEST_SHA256 = (
    "7d4f8fb415c719b8cf59978554e25a535a8cf774bef539392b377a74a73bb576"
)
ANDROID_RESULT_FUTURE_MTIME_TOLERANCE_NS = 5_000_000_000
ANDROID_FULL_TEST_RESULT_ROOT = (
    ROOT / "apps/android/app/build/test-results/testDebugUnitTest"
)
ANDROID_FULL_TEST_BINDING_PATH = (
    ANDROID_FULL_TEST_RESULT_ROOT
    / "aetherlink-full-test-result-binding-v1.json"
)
ANDROID_FULL_TEST_BINDING_CONTRACT = "android-full-app-junit-v1"
ANDROID_FULL_TEST_RUN_MARKER_PATH = (
    ROOT / "apps/android/app/build/aetherlink-full-test-run-marker-v1.json"
)
ANDROID_FULL_TEST_RUN_MARKER_CONTRACT = (
    "android-full-app-junit-run-source-v1"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RESULT_ROOT = (
    ROOT / "apps/android/core/protocol/build/test-results/testDebugUnitTest"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RESULT_ROOT = (
    ROOT / "apps/android/core/transport/build/test-results/testDebugUnitTest"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_BINDING_PATH = (
    ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RESULT_ROOT
    / "aetherlink-core-nonsecurity-test-result-binding-v1.json"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_BINDING_PATH = (
    ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RESULT_ROOT
    / "aetherlink-core-nonsecurity-test-result-binding-v1.json"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RUN_MARKER_PATH = (
    ROOT
    / "apps/android/core/protocol/build/"
    "aetherlink-core-nonsecurity-test-run-marker-v1.json"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RUN_MARKER_PATH = (
    ROOT
    / "apps/android/core/transport/build/"
    "aetherlink-core-nonsecurity-test-run-marker-v1.json"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_BINDING_CONTRACT = (
    "android-core-protocol-nonsecurity-junit-v1"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_BINDING_CONTRACT = (
    "android-core-transport-nonsecurity-junit-v1"
)
ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RUN_MARKER_CONTRACT = (
    "android-core-protocol-nonsecurity-junit-run-source-v1"
)
ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RUN_MARKER_CONTRACT = (
    "android-core-transport-nonsecurity-junit-run-source-v1"
)
ANDROID_CORE_NONSECURITY_RESULT_CONTRACTS = (
    (
        "protocol",
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RESULT_ROOT,
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_BINDING_PATH,
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RUN_MARKER_PATH,
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RESULTS,
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_CASE_MANIFEST_SHA256,
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_RUN_MARKER_CONTRACT,
        ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_BINDING_CONTRACT,
    ),
    (
        "transport",
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RESULT_ROOT,
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_BINDING_PATH,
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RUN_MARKER_PATH,
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RESULTS,
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_CASE_MANIFEST_SHA256,
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_RUN_MARKER_CONTRACT,
        ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_BINDING_CONTRACT,
    ),
)


def android_product_test_result_contract(
    class_name: str,
) -> tuple[str, int, tuple[str, ...]]:
    matches = tuple(
        contract
        for contract in ANDROID_PRODUCT_TEST_RESULTS
        if contract[0] == class_name
    )
    if len(matches) != 1:
        raise RuntimeError(
            "Android product test result contract must contain exactly one "
            f"entry for {class_name}, found {len(matches)}"
        )
    return matches[0]


ANDROID_CAMERA_LIFECYCLE_TEST_RESULTS = (
    android_product_test_result_contract(
        ANDROID_CAMERA_LIFECYCLE_CLASS_NAME
    ),
)

ANDROID_CAMERA_CONTROLLER_HOST_TEST_RESULTS = (
    android_product_test_result_contract(
        ANDROID_CAMERA_CONTROLLER_HOST_CLASS_NAME
    ),
)

ANDROID_FONT_SCALE_TEST_RESULTS = (
    android_product_test_result_contract(ANDROID_FONT_SCALE_CLASS_NAME),
)

ANDROID_RESULT_FRESHNESS_FILES = (
    Path(__file__).resolve(),
    WORKFLOW_PATH,
    NO_DEVICE_QUALITY_PATH,
    ROOT / "gradlew",
    ROOT / "build.gradle.kts",
    ROOT / "settings.gradle.kts",
    ROOT / "gradle.properties",
    ROOT / "buildscript-gradle.lockfile",
    ROOT / "settings-gradle.lockfile",
    ROOT / "gradle/libs.versions.toml",
    ROOT / "gradle/gradle-daemon-jvm.properties",
    ROOT / "gradle/wrapper/gradle-wrapper.jar",
    ROOT / "gradle/wrapper/gradle-wrapper.properties",
    ROOT / "apps/android/app/build.gradle.kts",
    ROOT / "apps/android/app/gradle.lockfile",
    ROOT / "apps/android/core/pairing/build.gradle.kts",
    ROOT / "apps/android/core/pairing/gradle.lockfile",
    ROOT / "apps/android/core/protocol/build.gradle.kts",
    ROOT / "apps/android/core/protocol/gradle.lockfile",
    ROOT / "apps/android/core/transport/build.gradle.kts",
    ROOT / "apps/android/core/transport/gradle.lockfile",
    ROOT / "packages/protocol-schema/protocol.schema.json",
    ROOT
    / "shared/protocol/fixtures/"
    "research-notebooks-authoritative-sync-smoke-v1.json",
)

ANDROID_RESULT_FRESHNESS_ROOTS = (
    ROOT / "apps/android/app/src/main",
    ROOT / "apps/android/app/src/test",
    ROOT / "apps/android/core/pairing/src/main",
    ROOT / "apps/android/core/protocol/src/main",
    ROOT / "apps/android/core/transport/src/main",
)

ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_FILES = (
    Path(__file__).resolve(),
    WORKFLOW_PATH,
    ROOT / "gradlew",
    ROOT / "build.gradle.kts",
    ROOT / "settings.gradle.kts",
    ROOT / "gradle.properties",
    ROOT / "buildscript-gradle.lockfile",
    ROOT / "settings-gradle.lockfile",
    ROOT / "gradle/libs.versions.toml",
    ROOT / "gradle/gradle-daemon-jvm.properties",
    ROOT / "gradle/wrapper/gradle-wrapper.jar",
    ROOT / "gradle/wrapper/gradle-wrapper.properties",
    ROOT / "apps/android/core/pairing/build.gradle.kts",
    ROOT / "apps/android/core/pairing/gradle.lockfile",
    ROOT / "apps/android/core/protocol/build.gradle.kts",
    ROOT / "apps/android/core/protocol/gradle.lockfile",
    ROOT / "apps/android/core/transport/build.gradle.kts",
    ROOT / "apps/android/core/transport/gradle.lockfile",
)
ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_ROOTS = (
    ROOT / "apps/android/core/pairing/src/main",
    ROOT / "apps/android/core/protocol/src/main",
    ROOT / "apps/android/core/protocol/src/test",
    ROOT / "apps/android/core/transport/src/main",
    ROOT / "apps/android/core/transport/src/test",
)

SWIFT_TEST_SELECTION_STEP_BODY = (
    "        run: |\n"
    "          swift test list > "
    ".build/aetherlink-product-ci-swift-test-list-v1.txt\n"
    "          python3 -B script/check_product_ci.py "
    "--swift-test-selection\n"
    "          python3 -B script/check_product_ci.py "
    "--prepare-swift-focused-test-run\n"
)

SWIFT_TEST_STEP_BODY = (
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --run-swift-focused-tests\n"
    "          --swift-focused-filter\n"
    f"          '{SWIFT_FILTER}'\n"
)

SWIFT_TEST_RESULT_STEP_BODY = (
    "        run: |\n"
    "          python3 -B script/check_product_ci.py "
    "--write-swift-focused-test-binding\n"
    "          python3 -B script/check_product_ci.py "
    "--swift-focused-test-results\n"
)

G7_CURRENT_RUN_CONTRACT_TEST_STEP_BODY = (
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B -m unittest\n"
    "          script.test_run_g7_nonsecurity_merge_full_current\n"
    "          script.test_check_g7_nonsecurity_merge_full_current\n"
)

G7_CURRENT_RUN_PREPARE_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/run_g7_nonsecurity_merge_full_current.py\n"
    "          --prepare\n"
)

G7_CURRENT_RUN_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/run_g7_nonsecurity_merge_full_current.py\n"
    "          --run\n"
)

G7_CURRENT_RUN_BIND_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          python3 -B script/run_g7_nonsecurity_merge_full_current.py "
    "--write-binding\n"
    "          python3 -B script/run_g7_nonsecurity_merge_full_current.py "
    "--results\n"
)

G7_CURRENT_RUN_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -I -B -S\n"
    "          script/check_g7_nonsecurity_merge_full_current.py\n"
    "          .build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
    "result.json\n"
)

G7_CURRENT_PARENT_BIND_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          python3 -B script/run_g7_nonsecurity_merge_full_current.py "
    "--write-parent\n"
    "          python3 -B script/run_g7_nonsecurity_merge_full_current.py "
    "--parent-results\n"
)

G7_CURRENT_PARENT_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -I -B -S\n"
    "          script/check_g7_nonsecurity_merge_full_current.py\n"
    "          --parent\n"
    "          .build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
    "parent-result.json\n"
)

DOCUMENT_INGESTION_ASAN_PREPARE_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --prepare-document-ingestion-asan-run\n"
)

DOCUMENT_INGESTION_ASAN_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --run-document-ingestion-asan-tests\n"
)

DOCUMENT_INGESTION_ASAN_RESULT_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          python3 -B script/check_product_ci.py "
    "--write-document-ingestion-asan-binding\n"
    "          python3 -B script/check_product_ci.py "
    "--document-ingestion-asan-results\n"
)

DOCUMENT_INGESTION_MUTATION_PREPARE_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --prepare-document-ingestion-mutation-run\n"
)

DOCUMENT_INGESTION_MUTATION_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --run-document-ingestion-mutation-tests\n"
)

DOCUMENT_INGESTION_MUTATION_RESULT_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          python3 -B script/check_product_ci.py "
    "--write-document-ingestion-mutation-binding\n"
    "          python3 -B script/check_product_ci.py "
    "--document-ingestion-mutation-results\n"
)

TRACKED_DOCUMENTATION_CONTRACT_TESTS = (
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_tracked_document_contract_mode_excludes_ignored_evidence_readback",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_tracked_document_contract_cli_is_explicit_and_bounded",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g7_nonsecurity_merge_full_local_candidate_block_is_exact_and_fail_closed",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g7_nonsecurity_merge_full_local_candidate_validator_is_wired_once",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g6_release_diagnostics_document_block_is_exact_and_fail_closed",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g6_release_diagnostics_validator_is_wired_once",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g7_document_ingestion_asan_block_is_exact_and_fail_closed",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g7_document_ingestion_asan_validator_is_wired_once",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g7_document_ingestion_mutation_block_is_exact_and_fail_closed",
    "script.test_documentation_handoff_guards."
    "DocumentationHandoffGuardTests."
    "test_current_g7_document_ingestion_mutation_validator_is_wired_once",
)

RELEASE_COMPLIANCE_TEST_IDS = (
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_bool_package_count_is_rejected",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_catalog_is_canonical_and_has_stable_identity",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_catalog_statistics_capture_unresolved_boundary",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_checked_in_catalog_exactly_covers_current_locks",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_coordinate_purl_mutation_is_rejected",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_dependency_input_universe_is_closed_in_both_implementations",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_generated_member_mutation_is_rejected",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_generator_rejects_claimed_repository_url_mismatch",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_independent_readback_reconstructs_every_generated_byte",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_license_mapping_mutation_is_rejected",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_lock_identity_mutation_is_rejected",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_noncanonical_or_duplicate_json_is_rejected",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_offline_render_is_deterministic",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_swift_external_dependency_is_rejected_independently",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_swift_resolution_file_is_rejected_independently",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_unexpected_or_missing_gradle_lock_is_rejected_independently",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_unknown_configuration_is_rejected_by_both_implementations",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_unreviewed_license_names_remain_noassertion",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_v1_historical_profileless_contract_is_frozen",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_v2_namespace_covers_every_generation_identity",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_v2_spdx_has_all_configuration_derived_roles",
    "script.test_release_compliance.ReleaseComplianceTests."
    "test_v2_summary_profile_and_schema_mutations_are_rejected",
)
RELEASE_COMPLIANCE_TEST_COUNT = len(RELEASE_COMPLIANCE_TEST_IDS)
RELEASE_COMPLIANCE_TEST_MANIFEST_SHA256 = (
    "788764544f8a9ad7282e3b902c2b7d16958304e78ba793e63c54f8e928f1347d"
)

RELEASE_COMPLIANCE_CONTRACT_STEP_BODY = (
    "        run: |\n"
    "          python3 -B script/generate_release_compliance.py check\n"
    "          PYTHONPATH=. python3 -B script/check_product_ci.py "
    "--run-release-compliance-tests\n"
)

TRACKED_DOCUMENTATION_CONTRACT_STEP_BODY = (
    "        run: |\n"
    "          python3 -B script/check_docs_hygiene.py "
    "--tracked-contracts-only\n"
    "          python3 -B -m unittest \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[0]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[1]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[2]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[3]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[4]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[5]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[6]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[7]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[8]} \\\n"
    f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[9]}\n"
)

MACOS_PACKAGE_CONTRACT_TEST_STEP_BODY = (
    "        run: PYTHONPATH=. python3 -B script/test_build_and_run.py\n"
)

MACOS_LIFECYCLE_CONTRACT_TEST_STEP_BODY = (
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B -m unittest\n"
    "          script.test_run_macos_current_unsealed_install_recovery_smoke\n"
    "          script.test_check_macos_current_unsealed_install_recovery_evidence."
    "CurrentUnsealedRecoveryEvidencePortableTests\n"
    "          script.test_check_macos_current_unsealed_ci_lifecycle\n"
    "          script.test_run_macos_runtime_chat_production_append_"
    "abrupt_recovery_smoke\n"
    "          script.test_check_macos_runtime_chat_production_append_"
    "abrupt_recovery_evidence\n"
    "          script.test_check_macos_current_source_lane_a_idle_"
    "resource_repeatability\n"
)

RELEASE_DIAGNOSTICS_CONTRACT_TEST_STEP_BODY = (
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B -m unittest\n"
    "          script.test_run_release_diagnostics_usability\n"
    "          script.test_check_release_diagnostics_usability\n"
)

PRODUCT_NIGHTLY_CONTRACT_STEP_BODY = (
    "        run: |\n"
    "          python3 -B script/check_product_nightly_ci.py\n"
    "          PYTHONPATH=. python3 -B script/check_product_nightly_ci.py "
    "--run-contract-tests\n"
)

MACOS_UNSEALED_RELEASE_BUILD_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          source_before=\"$(python3 -B "
    "script/package_release_artifacts.py source-digest)\"\n"
    "          ./script/build_and_run.sh --unsealed-package-only\n"
    "          source_after=\"$(python3 -B "
    "script/package_release_artifacts.py source-digest)\"\n"
    '          if [[ "$source_before" != "$source_after" ]]; then\n'
    '            echo "macOS Release build inputs changed during packaging" >&2\n'
    "            exit 2\n"
    "          fi\n"
)

MACOS_UNSEALED_RELEASE_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_release_artifact_archive.py\n"
    "          --macos-build-outputs\n"
)

MACOS_RELEASE_DIAGNOSTICS_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          install -d -m 700 .build/aetherlink-release-diagnostics-v1\n"
    "          python3 -B script/run_release_diagnostics_usability.py \\\n"
    "            --platform macos \\\n"
    "            --result .build/aetherlink-release-diagnostics-v1/macos.json\n"
)

MACOS_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B\n"
    "          script/check_release_diagnostics_usability.py\n"
    "          --platform macos\n"
    "          .build/aetherlink-release-diagnostics-v1/macos.json\n"
)

MACOS_CURRENT_UNSEALED_LIFECYCLE_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          install -d -m 700 "
    ".build/aetherlink-current-unsealed-lifecycle-v1\n"
    "          python3 -B "
    "script/run_macos_current_unsealed_install_recovery_smoke.py \\\n"
    "            --result "
    ".build/aetherlink-current-unsealed-lifecycle-v1/result.json \\\n"
    "            --repeatability-result "
    ".build/aetherlink-current-unsealed-lifecycle-v1/repeatability.json\n"
)

MACOS_CURRENT_UNSEALED_LIFECYCLE_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B\n"
    "          script/check_macos_current_unsealed_ci_lifecycle.py\n"
)

MACOS_PRODUCTION_APPEND_RECOVERY_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          install -d -m 700 "
    ".build/aetherlink-production-append-recovery-v1\n"
    "          python3 -B "
    "script/run_macos_runtime_chat_production_append_abrupt_recovery_smoke.py \\\n"
    "            --result "
    ".build/aetherlink-production-append-recovery-v1/result.json \\\n"
    "            --repeatability-receipt "
    ".build/aetherlink-production-append-recovery-v1/repeatability.json\n"
)

MACOS_PRODUCTION_APPEND_RECOVERY_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B\n"
    "          script/check_macos_runtime_chat_production_append_"
    "abrupt_recovery_evidence.py\n"
    "          --result "
    ".build/aetherlink-production-append-recovery-v1/result.json\n"
    "          --repeatability-receipt "
    ".build/aetherlink-production-append-recovery-v1/repeatability.json\n"
)

ANDROID_TEST_STEP_BODY = (
    "        run: >-\n"
    "          ./gradlew\n"
    "          --no-daemon\n"
    "          --console=plain\n"
    "          -Pkotlin.incremental=false\n"
    "          :app:compileDebugKotlin\n"
    "          :app:compileDebugUnitTestKotlin\n"
    "          :app:testDebugUnitTest\n"
    + "".join(f"          --tests {test}\n" for test in ANDROID_TESTS)
)

ANDROID_TEST_RESULT_STEP_BODY = (
    "        run: python3 -B script/check_product_ci.py "
    "--android-test-results\n"
)

ANDROID_MAIN_FULL_PREPARE_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --prepare-android-full-test-run\n"
)

ANDROID_MAIN_FULL_TEST_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          ./gradlew\n"
    "          --no-daemon\n"
    "          --console=plain\n"
    "          --rerun-tasks\n"
    "          -Pkotlin.incremental=false\n"
    "          :app:compileDebugKotlin\n"
    "          :app:testDebugUnitTest\n"
    + "".join(
        f"          --tests {test}\n"
        for test in ANDROID_MAIN_FULL_TESTS
    )
)

ANDROID_MAIN_FULL_RESULT_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          python3 -B script/check_product_ci.py "
    "--write-android-full-test-binding\n"
    "          python3 -B script/check_product_ci.py "
    "--android-full-test-results\n"
)

ANDROID_CORE_NONSECURITY_PREPARE_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --prepare-android-core-nonsecurity-test-run\n"
)

ANDROID_CORE_NONSECURITY_TEST_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B script/check_product_ci.py\n"
    "          --run-android-core-nonsecurity-tests\n"
)

ANDROID_CORE_NONSECURITY_RESULT_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          python3 -B script/check_product_ci.py "
    "--write-android-core-nonsecurity-test-binding\n"
    "          python3 -B script/check_product_ci.py "
    "--android-core-nonsecurity-test-results\n"
)

ANDROID_RELEASE_REPEATABILITY_CONTRACT_TEST_STEP_BODY = (
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B -m unittest\n"
    "          script.test_run_android_release_repeatability_current\n"
    "          script.test_check_android_release_repeatability_current\n"
)

ANDROID_RELEASE_STEP_BODY = (
    f"        if: {PULL_REQUEST_CONDITION}\n"
    "        run: >-\n"
    "          ./gradlew\n"
    "          --no-daemon\n"
    "          --console=plain\n"
    "          -PaetherlinkStrictReleaseDependencyLocks=true\n"
    "          -Pkotlin.incremental=false\n"
    "          :app:assembleRelease\n"
    "          :app:bundleRelease\n"
    "          :app:lintRelease\n"
)

ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          python3 -B "
    "script/run_android_release_repeatability_current.py\n"
)

ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B\n"
    "          script/check_android_release_repeatability_current.py\n"
    "          .build/aetherlink-android-release-repeatability-v1/"
    "result.json\n"
)

ANDROID_RELEASE_READBACK_STEP_BODY = (
    "        run: >-\n"
    "          python3 -B script/check_release_artifact_archive.py\n"
    "          --android-build-outputs\n"
)

ANDROID_RELEASE_DIAGNOSTICS_RUN_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: |\n"
    "          install -d -m 700 .build/aetherlink-release-diagnostics-v1\n"
    "          python3 -B script/run_release_diagnostics_usability.py \\\n"
    "            --platform android \\\n"
    "            --result .build/aetherlink-release-diagnostics-v1/android.json\n"
)

ANDROID_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          PYTHONPATH=. python3 -B\n"
    "          script/check_release_diagnostics_usability.py\n"
    "          --platform android\n"
    "          .build/aetherlink-release-diagnostics-v1/android.json\n"
)

MACOS_JOB_PREAMBLE = (
    "    name: macOS product quality subset\n"
    "    runs-on: macos-26\n"
    "    timeout-minutes: 120\n"
    "    env:\n"
    "      DEVELOPER_DIR: /Applications/Xcode_26.6.app/Contents/Developer\n"
)

ANDROID_JOB_PREAMBLE = (
    "    name: Android product quality subset\n"
    "    runs-on: ubuntu-24.04\n"
    "    timeout-minutes: 60\n"
)

MACOS_STEPS = (
    (
        "Check out source",
        "        uses: actions/checkout@v7\n"
        "        with:\n"
        "          fetch-depth: 0\n"
        "          persist-credentials: false\n",
    ),
    (
        "Report toolchain",
        "        run: |\n"
        "          xcodebuild -version\n"
        "          python3 --version\n"
        "          ruby --version\n"
        "          swift --version\n",
    ),
    (
        "Check changed bytes",
        "        env:\n"
        "          BASE_SHA: >-\n"
        "            ${{ github.event.pull_request.base.sha || github.event.before }}\n"
        "          HEAD_SHA: ${{ github.sha }}\n"
        "        run: |\n"
        '          if [[ -n "$BASE_SHA" && ! "$BASE_SHA" =~ ^0+$ ]]; then\n'
        '            git diff --check "$BASE_SHA" "$HEAD_SHA"\n'
        '          elif git rev-parse "$HEAD_SHA^" >/dev/null 2>&1; then\n'
        '            git diff --check "$HEAD_SHA^" "$HEAD_SHA"\n'
        "          else\n"
        '            git show --check --format= "$HEAD_SHA"\n'
        "          fi\n",
    ),
    (
        "Validate bounded CI contract",
        "        run: |\n"
        "          python3 -B script/check_product_ci.py\n"
        "          python3 -B script/check_product_ci.py --self-test\n",
    ),
    (
        "Validate product-nightly contract",
        PRODUCT_NIGHTLY_CONTRACT_STEP_BODY,
    ),
    (
        "Run product static checks",
        "        run: |\n"
        "          python3 -B script/check_copy_hygiene.py --product-copy-only\n"
        "          python3 -B script/check_release_version_ledger.py\n"
        "          python3 -B script/check_app_icons.py\n"
        "          python3 -B script/check_license.py\n",
    ),
    (
        "Run release compliance contracts",
        RELEASE_COMPLIANCE_CONTRACT_STEP_BODY,
    ),
    (
        "Run tracked documentation contracts",
        TRACKED_DOCUMENTATION_CONTRACT_STEP_BODY,
    ),
    (
        "Run macOS release package contract units",
        MACOS_PACKAGE_CONTRACT_TEST_STEP_BODY,
    ),
    (
        "Run macOS lifecycle contract units",
        MACOS_LIFECYCLE_CONTRACT_TEST_STEP_BODY,
    ),
    (
        "Run release diagnostics contract units",
        RELEASE_DIAGNOSTICS_CONTRACT_TEST_STEP_BODY,
    ),
    (
        "Compile macOS app",
        "        run: swift build --product AetherLink\n",
    ),
    (
        "Verify focused Swift test selection",
        SWIFT_TEST_SELECTION_STEP_BODY,
    ),
    (
        "Run G7 current-run contract units",
        G7_CURRENT_RUN_CONTRACT_TEST_STEP_BODY,
    ),
    ("Run focused product units", SWIFT_TEST_STEP_BODY),
    (
        "Bind and verify focused Swift test results",
        SWIFT_TEST_RESULT_STEP_BODY,
    ),
    (
        "Prepare G7 non-security current run on main",
        G7_CURRENT_RUN_PREPARE_STEP_BODY,
    ),
    (
        "Run G7 non-security current run on main",
        G7_CURRENT_RUN_RUN_STEP_BODY,
    ),
    (
        "Bind and verify G7 non-security current run on main",
        G7_CURRENT_RUN_BIND_STEP_BODY,
    ),
    (
        "Independently read back G7 non-security current run on main",
        G7_CURRENT_RUN_READBACK_STEP_BODY,
    ),
    (
        "Bind and verify G7 non-security current parent on main",
        G7_CURRENT_PARENT_BIND_STEP_BODY,
    ),
    (
        "Independently read back G7 non-security current parent on main",
        G7_CURRENT_PARENT_READBACK_STEP_BODY,
    ),
    (
        "Prepare DocumentIngestion ASan corpus on main",
        DOCUMENT_INGESTION_ASAN_PREPARE_STEP_BODY,
    ),
    (
        "Run DocumentIngestion ASan corpus on main",
        DOCUMENT_INGESTION_ASAN_RUN_STEP_BODY,
    ),
    (
        "Bind and verify DocumentIngestion ASan corpus on main",
        DOCUMENT_INGESTION_ASAN_RESULT_STEP_BODY,
    ),
    (
        "Prepare DocumentIngestion mutation corpus on main",
        DOCUMENT_INGESTION_MUTATION_PREPARE_STEP_BODY,
    ),
    (
        "Run DocumentIngestion mutation corpus on main",
        DOCUMENT_INGESTION_MUTATION_RUN_STEP_BODY,
    ),
    (
        "Bind and verify DocumentIngestion mutation corpus on main",
        DOCUMENT_INGESTION_MUTATION_RESULT_STEP_BODY,
    ),
    (
        "Build unsealed macOS Release package on main",
        MACOS_UNSEALED_RELEASE_BUILD_STEP_BODY,
    ),
    (
        "Read back unsealed macOS Release package on main",
        MACOS_UNSEALED_RELEASE_READBACK_STEP_BODY,
    ),
    (
        "Run macOS Release diagnostics on main",
        MACOS_RELEASE_DIAGNOSTICS_RUN_STEP_BODY,
    ),
    (
        "Read back macOS Release diagnostics on main",
        MACOS_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY,
    ),
    (
        "Run current unsealed lifecycle on main",
        MACOS_CURRENT_UNSEALED_LIFECYCLE_RUN_STEP_BODY,
    ),
    (
        "Read back current unsealed lifecycle on main",
        MACOS_CURRENT_UNSEALED_LIFECYCLE_READBACK_STEP_BODY,
    ),
    (
        "Run production append abrupt recovery on main",
        MACOS_PRODUCTION_APPEND_RECOVERY_RUN_STEP_BODY,
    ),
    (
        "Read back production append abrupt recovery on main",
        MACOS_PRODUCTION_APPEND_RECOVERY_READBACK_STEP_BODY,
    ),
)

ANDROID_STEPS = (
    (
        "Check out source",
        "        uses: actions/checkout@v7\n"
        "        with:\n"
        "          persist-credentials: false\n",
    ),
    (
        "Set up JDK 21",
        "        uses: actions/setup-java@v5\n"
        "        with:\n"
        "          distribution: temurin\n"
        '          java-version: "21"\n',
    ),
    (
        "Set up Gradle",
        "        uses: gradle/actions/setup-gradle@v6\n"
        "        with:\n"
        "          cache-provider: basic\n"
        "          cache-read-only: ${{ github.event_name == 'pull_request' }}\n",
    ),
    (
        "Verify Android toolchain",
        "        run: |\n"
        "          java -version\n"
        '          test -d "$ANDROID_HOME/platforms/android-36"\n'
        '          test -d "$ANDROID_HOME/build-tools/36.0.0"\n'
        '          test -d "$ANDROID_HOME/ndk/28.2.13676358"\n'
        "          ./gradlew --version\n",
    ),
    (
        "Run release archive contract units",
        "        run: PYTHONPATH=. python3 -B "
        "script/test_release_artifact_archive.py\n",
    ),
    (
        "Run Android Release repeatability contract units",
        ANDROID_RELEASE_REPEATABILITY_CONTRACT_TEST_STEP_BODY,
    ),
    (
        "Compile Android and run focused product units",
        ANDROID_TEST_STEP_BODY,
    ),
    (
        "Verify focused Android test results",
        ANDROID_TEST_RESULT_STEP_BODY,
    ),
    (
        "Prepare complete Android app units on main",
        ANDROID_MAIN_FULL_PREPARE_STEP_BODY,
    ),
    (
        "Run complete Android app units on main",
        ANDROID_MAIN_FULL_TEST_STEP_BODY,
    ),
    (
        "Bind and verify complete Android app units on main",
        ANDROID_MAIN_FULL_RESULT_STEP_BODY,
    ),
    (
        "Prepare Android core non-security units on main",
        ANDROID_CORE_NONSECURITY_PREPARE_STEP_BODY,
    ),
    (
        "Run Android core non-security units on main",
        ANDROID_CORE_NONSECURITY_TEST_STEP_BODY,
    ),
    (
        "Bind and verify Android core non-security units on main",
        ANDROID_CORE_NONSECURITY_RESULT_STEP_BODY,
    ),
    (
        "Compile and lint Android Release app on pull request",
        ANDROID_RELEASE_STEP_BODY,
    ),
    (
        "Run Android Release A/B repeatability on main",
        ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY,
    ),
    (
        "Read back Android Release A/B repeatability on main",
        ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY,
    ),
    (
        "Read back Android Release build outputs",
        ANDROID_RELEASE_READBACK_STEP_BODY,
    ),
    (
        "Run Android Release diagnostics on main",
        ANDROID_RELEASE_DIAGNOSTICS_RUN_STEP_BODY,
    ),
    (
        "Read back Android Release diagnostics on main",
        ANDROID_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY,
    ),
)

REQUIRED_TOP_LEVEL_FRAGMENTS = (
    "name: Product quality (non-security subset)\n",
    '"on":\n',
    "  pull_request:\n",
    "  push:\n",
    "    branches:\n      - main\n",
    "permissions:\n  contents: read\n",
    "product-quality-${{ github.workflow }}-${{",
    "github.event.pull_request.number || github.run_id }}",
    "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
)

FORBIDDEN_SCOPE_PATTERNS = {
    "privileged pull-request trigger": r"(?m)^\s*pull_request_target\s*:",
    "scheduled execution": r"(?m)^\s*schedule\s*:",
    "manual remote execution": r"(?m)^\s*workflow_dispatch\s*:",
    "repository secret reference": r"\bsecrets\.",
    "identity-token permission": r"(?m)^\s*id-token\s*:",
    "artifact publication": r"\bactions/upload-artifact@",
    "deployment environment": r"(?m)^\s*environment\s*:",
    "service container": r"(?m)^\s*services\s*:",
    "release publication": r"\bgh\s+release\b",
    "repository push": r"\bgit\s+push\b",
    "macOS signing": r"\bcodesign\b|\bnotarytool\b",
    "Android signing": r"\bjarsigner\b|\bapksigner\b",
    "mixed aggregate gate": r"\bcheck_no_device_quality(?:\.sh)?\b",
    "excluded checker": (
        r"\bcheck_(?:production_security|p2p_nat_security|"
        r"v1_g0_owner)[A-Za-z0-9_.-]*"
    ),
    "live provider smoke": r"\bruntime_authenticated_mock_smoke\b",
    "live backend test class": r"\b(?:OllamaBackendTests|LMStudioBackendTests)\b",
    "wildcard Android test selector": r"--tests\s+[\"']?\*[\"']?",
    "Android instrumentation task": r":\S*connected\S*AndroidTest\b",
    "Android install task": r":\S*install(?:Debug|Release)\b",
    "Android signing report": r":\S*signingReport\b",
    "explicit live-test enablement": (
        r"(?i)(?:OLLAMA|LM_STUDIO|LIVE_PROVIDER|RUN_LIVE)"
        r"[A-Z0-9_]*\s*:\s*[\"']?(?:1|true|yes)"
    ),
    "direct network command": r"(?m)^\s*(?:curl|wget|nc)\s+",
    "device command": r"(?:^|[\s/])adb(?:\s|$)|\bemulator\b",
    "cold-runner offline mode": r"--offline\b",
    "ignored failure": r"(?m)^\s*continue-on-error\s*:",
    "canonical tier overclaim": r"\bmain[- ]full\b",
}


def job_body(workflow: str, job_id: str) -> Optional[str]:
    pattern = re.compile(
        rf"(?ms)^  {re.escape(job_id)}:\n"
        rf"(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)"
    )
    match = pattern.search(workflow)
    return match.group("body") if match else None


def named_step_body(job: str, step_name: str) -> Optional[str]:
    pattern = re.compile(
        rf"(?ms)^      - name: {re.escape(step_name)}\n"
        rf"(?P<body>.*?)(?=^      - name:|\Z)"
    )
    match = pattern.search(job)
    return match.group("body") if match else None


def require_fragments(
    failures: list[str],
    *,
    label: str,
    text: str,
    fragments: tuple[str, ...],
) -> None:
    for fragment in fragments:
        if fragment not in text:
            failures.append(f"{label} is missing {fragment!r}")


def require_exact_job(
    failures: list[str],
    *,
    label: str,
    job: str,
    preamble: str,
    steps: tuple[tuple[str, str], ...],
) -> None:
    parts = job.split("    steps:\n", 1)
    if len(parts) != 2 or parts[0] != preamble:
        failures.append(f"{label} must match the exact job preamble")

    expected_names = tuple(name for name, _ in steps)
    actual_names = tuple(re.findall(r"(?m)^      - name: (.+)$", job))
    if actual_names != expected_names:
        failures.append(f"{label} steps must match the exact names and order")

    for step_name, expected_body in steps:
        actual_body = named_step_body(job, step_name)
        if (
            actual_body is None
            or actual_body.rstrip() != expected_body.rstrip()
        ):
            failures.append(
                f"{label} step {step_name!r} must match the exact body"
            )


def parsed_yaml_failures(workflow: str) -> list[str]:
    ruby = r"""
source = STDIN.read

def reject_duplicate_mapping_keys(node, path = "$")
  case node
  when Psych::Nodes::Mapping
    seen = {}
    node.children.each_slice(2) do |key, value|
      unless key.is_a?(Psych::Nodes::Scalar)
        raise "non-scalar mapping key at #{path}"
      end
      unless key.tag.nil?
        raise "explicitly tagged mapping key #{key.value.inspect} at #{path}"
      end
      if seen.key?(key.value)
        raise "duplicate mapping key #{key.value.inspect} at #{path}"
      end
      seen[key.value] = true
      reject_duplicate_mapping_keys(value, "#{path}.#{key.value}")
    end
  when Psych::Nodes::Sequence
    node.children.each_with_index do |child, index|
      reject_duplicate_mapping_keys(child, "#{path}[#{index}]")
    end
  when Psych::Nodes::Stream, Psych::Nodes::Document
    node.children.each { |child| reject_duplicate_mapping_keys(child, path) }
  end
end

begin
  syntax_tree = Psych.parse_stream(source)
  unless syntax_tree.children.length == 1
    raise "workflow must contain exactly one YAML document"
  end
  reject_duplicate_mapping_keys(syntax_tree)
  data = YAML.safe_load(
    source,
    permitted_classes: [],
    permitted_symbols: [],
    aliases: false
  )
  STDOUT.write(JSON.generate(data))
rescue StandardError => error
  warn error.message
  exit 2
end
"""
    try:
        result = subprocess.run(
            ["ruby", "-ryaml", "-rjson", "-e", ruby],
            input=workflow,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [f"workflow YAML parser failed: {error}"]

    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        return [f"workflow YAML is invalid{suffix}"]

    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        return [f"workflow YAML parser returned invalid JSON: {error}"]

    if not isinstance(parsed, dict):
        return ["parsed workflow must be a mapping"]
    failures: list[str] = []
    normalized = json.dumps(
        parsed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    parsed_sha256 = hashlib.sha256(normalized).hexdigest()
    if parsed_sha256 != CANONICAL_PARSED_WORKFLOW_SHA256:
        failures.append(
            "parsed workflow semantics differ from the exact contract: "
            f"expected {CANONICAL_PARSED_WORKFLOW_SHA256}, got {parsed_sha256}"
        )
    if tuple(parsed) != TOP_LEVEL_KEYS:
        failures.append("parsed workflow top-level keys must match exactly")

    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict):
        failures.append("parsed workflow jobs must be a mapping")
        return failures
    if tuple(jobs) != JOB_IDS:
        failures.append(
            "parsed workflow jobs must be exactly " + ", ".join(JOB_IDS)
        )

    expected_jobs = {
        "macos-product-quality": (
            ("name", "runs-on", "timeout-minutes", "env", "steps"),
            tuple(name for name, _ in MACOS_STEPS),
        ),
        "android-product-quality": (
            ("name", "runs-on", "timeout-minutes", "steps"),
            tuple(name for name, _ in ANDROID_STEPS),
        ),
    }
    for job_id, (expected_keys, expected_step_names) in expected_jobs.items():
        job = jobs.get(job_id)
        if not isinstance(job, dict):
            failures.append(f"parsed job {job_id!r} must be a mapping")
            continue
        if tuple(job) != expected_keys:
            failures.append(
                f"parsed job {job_id!r} keys must match exactly"
            )
        steps = job.get("steps")
        if not isinstance(steps, list):
            failures.append(f"parsed job {job_id!r} steps must be a list")
            continue
        if not all(isinstance(step, dict) for step in steps):
            failures.append(
                f"parsed job {job_id!r} steps must all be mappings"
            )
            continue
        step_names = tuple(step.get("name") for step in steps)
        if step_names != expected_step_names:
            failures.append(
                f"parsed job {job_id!r} steps must match exact names and order"
            )

    return failures


def release_compliance_test_case() -> type[unittest.TestCase]:
    root_entry = str(ROOT)
    added_root = root_entry not in sys.path
    if added_root:
        sys.path.insert(0, root_entry)
    try:
        module = importlib.import_module("script.test_release_compliance")
        candidate = getattr(module, "ReleaseComplianceTests", None)
        if not isinstance(candidate, type) or not issubclass(
            candidate, unittest.TestCase
        ):
            raise TypeError(
                "ReleaseComplianceTests must be a unittest.TestCase class"
            )
        return candidate
    finally:
        if added_root:
            sys.path.remove(root_entry)


def release_compliance_test_suite(
    test_case: type[unittest.TestCase],
) -> unittest.TestSuite:
    return unittest.TestSuite(
        test_case(identity.rsplit(".", 1)[-1])
        for identity in RELEASE_COMPLIANCE_TEST_IDS
    )


class ReleaseComplianceRecordingResult(unittest.TextTestResult):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.started_test_ids: list[str] = []

    def startTest(self, test: unittest.TestCase) -> None:
        self.started_test_ids.append(test.id())
        super().startTest(test)


def release_compliance_discovered_test_ids(
    test_case: type[unittest.TestCase],
) -> tuple[str, ...]:
    return tuple(
        f"{test_case.__module__}.{test_case.__qualname__}.{method_name}"
        for method_name in unittest.defaultTestLoader.getTestCaseNames(test_case)
    )


def release_compliance_test_manifest_failures() -> list[str]:
    manifest = ("\n".join(RELEASE_COMPLIANCE_TEST_IDS) + "\n").encode(
        "utf-8"
    )
    failures: list[str] = []
    if type(RELEASE_COMPLIANCE_TEST_COUNT) is not int:
        failures.append("release compliance test count must be an exact integer")
    if RELEASE_COMPLIANCE_TEST_COUNT != 22:
        failures.append("release compliance test manifest must contain 22 tests")
    if len(set(RELEASE_COMPLIANCE_TEST_IDS)) != RELEASE_COMPLIANCE_TEST_COUNT:
        failures.append("release compliance test manifest contains duplicates")
    actual_sha256 = hashlib.sha256(manifest).hexdigest()
    if actual_sha256 != RELEASE_COMPLIANCE_TEST_MANIFEST_SHA256:
        failures.append(
            "release compliance test manifest identity changed: expected "
            f"{RELEASE_COMPLIANCE_TEST_MANIFEST_SHA256}, got {actual_sha256}"
        )
    return failures


def release_compliance_test_selection_failures(
    actual_ids: Optional[tuple[str, ...]] = None,
) -> list[str]:
    failures = release_compliance_test_manifest_failures()
    if failures:
        return failures
    if actual_ids is None:
        try:
            actual_ids = release_compliance_discovered_test_ids(
                release_compliance_test_case()
            )
        except Exception as error:
            return [f"cannot load release compliance test suite: {error}"]

    if actual_ids == RELEASE_COMPLIANCE_TEST_IDS:
        return []

    missing = tuple(
        identity
        for identity in RELEASE_COMPLIANCE_TEST_IDS
        if identity not in actual_ids
    )
    unexpected = tuple(
        identity
        for identity in actual_ids
        if identity not in RELEASE_COMPLIANCE_TEST_IDS
    )
    failures = [
        "release compliance test identities must match the exact reviewed "
        f"{RELEASE_COMPLIANCE_TEST_COUNT}-test manifest"
    ]
    if missing:
        failures.append("missing release compliance tests: " + ", ".join(missing))
    if unexpected:
        failures.append(
            "unexpected release compliance tests: " + ", ".join(unexpected)
        )
    if not missing and not unexpected:
        failures.append(
            "release compliance test identities are duplicated or out of order"
        )
    return failures


def release_compliance_test_result_failures(
    result: unittest.TestResult,
) -> list[str]:
    failures: list[str] = []
    if (
        type(result.testsRun) is not int
        or result.testsRun != RELEASE_COMPLIANCE_TEST_COUNT
    ):
        failures.append(
            "release compliance runner executed "
            f"{result.testsRun}/{RELEASE_COMPLIANCE_TEST_COUNT} tests"
        )
    started_test_ids = getattr(result, "started_test_ids", None)
    if tuple(started_test_ids or ()) != RELEASE_COMPLIANCE_TEST_IDS:
        failures.append(
            "release compliance runner start identities must match the exact "
            "manifest order"
        )
    for label, records in (
        ("skips", result.skipped),
        ("failures", result.failures),
        ("errors", result.errors),
        ("expected failures", result.expectedFailures),
        ("unexpected successes", result.unexpectedSuccesses),
    ):
        if records:
            failures.append(
                f"release compliance runner recorded {len(records)} {label}"
            )
    if not result.wasSuccessful() and not failures:
        failures.append("release compliance runner was not successful")
    return failures


def run_release_compliance_tests() -> list[str]:
    try:
        test_case = release_compliance_test_case()
    except Exception as error:
        return [f"cannot load release compliance test suite: {error}"]

    failures = release_compliance_test_selection_failures(
        release_compliance_discovered_test_ids(test_case)
    )
    if failures:
        return failures

    suite = release_compliance_test_suite(test_case)
    output = io.StringIO()
    result = unittest.TextTestRunner(
        stream=output,
        verbosity=2,
        failfast=False,
        buffer=False,
        resultclass=ReleaseComplianceRecordingResult,
    ).run(suite)
    print(output.getvalue(), end="")
    return release_compliance_test_result_failures(result)


def release_compliance_test_runner_self_test() -> list[str]:
    failures = release_compliance_test_selection_failures()
    for label, identities in (
        ("omission", RELEASE_COMPLIANCE_TEST_IDS[:-1]),
        (
            "replacement",
            RELEASE_COMPLIANCE_TEST_IDS[:-1]
            + ("script.test_release_compliance.ReplacedTest.test_replaced",),
        ),
        (
            "duplication",
            RELEASE_COMPLIANCE_TEST_IDS + (RELEASE_COMPLIANCE_TEST_IDS[-1],),
        ),
        ("order", tuple(reversed(RELEASE_COMPLIANCE_TEST_IDS))),
    ):
        if not release_compliance_test_selection_failures(identities):
            failures.append(
                f"release compliance runner self-test accepted {label} mutation"
            )

    baseline = unittest.TestResult()
    baseline.testsRun = RELEASE_COMPLIANCE_TEST_COUNT
    baseline.started_test_ids = list(RELEASE_COMPLIANCE_TEST_IDS)
    if release_compliance_test_result_failures(baseline):
        failures.append("release compliance result self-test rejected baseline")

    for label, attribute, record in (
        ("skip", "skipped", (None, "fixture skip")),
        ("failure", "failures", (None, "fixture failure")),
        ("error", "errors", (None, "fixture error")),
        (
            "expected failure",
            "expectedFailures",
            (None, "fixture expected failure"),
        ),
        ("unexpected success", "unexpectedSuccesses", None),
    ):
        result = unittest.TestResult()
        result.testsRun = RELEASE_COMPLIANCE_TEST_COUNT
        result.started_test_ids = list(RELEASE_COMPLIANCE_TEST_IDS)
        getattr(result, attribute).append(record)
        if not release_compliance_test_result_failures(result):
            failures.append(
                "release compliance runner self-test accepted " + label
            )

    for label, tests_run in (
        ("short run", RELEASE_COMPLIANCE_TEST_COUNT - 1),
        ("long run", RELEASE_COMPLIANCE_TEST_COUNT + 1),
        ("boolean run count", True),
    ):
        result = unittest.TestResult()
        result.testsRun = tests_run
        result.started_test_ids = list(RELEASE_COMPLIANCE_TEST_IDS)
        if not release_compliance_test_result_failures(result):
            failures.append(
                f"release compliance runner self-test accepted {label}"
            )

    for label, started_ids in (
        ("started-test omission", RELEASE_COMPLIANCE_TEST_IDS[:-1]),
        (
            "started-test duplication",
            RELEASE_COMPLIANCE_TEST_IDS[:-1]
            + (RELEASE_COMPLIANCE_TEST_IDS[-2],),
        ),
        ("started-test order", tuple(reversed(RELEASE_COMPLIANCE_TEST_IDS))),
    ):
        result = unittest.TestResult()
        result.testsRun = RELEASE_COMPLIANCE_TEST_COUNT
        result.started_test_ids = list(started_ids)
        if not release_compliance_test_result_failures(result):
            failures.append(
                f"release compliance runner self-test accepted {label}"
            )
    return failures


def workflow_failures(
    workflow: str,
    *,
    check_canonical_bytes: bool = True,
) -> list[str]:
    failures: list[str] = []

    if check_canonical_bytes:
        actual_sha256 = hashlib.sha256(workflow.encode("utf-8")).hexdigest()
        if actual_sha256 != CANONICAL_WORKFLOW_SHA256:
            failures.append(
                "workflow bytes differ from the reviewed contract: "
                f"expected {CANONICAL_WORKFLOW_SHA256}, got {actual_sha256}"
            )
    if "\r" in workflow:
        failures.append("workflow must use LF line endings")
    if not workflow.endswith("\n"):
        failures.append("workflow must end with LF")
    failures.extend(parsed_yaml_failures(workflow))
    if not workflow.startswith(REQUIRED_WORKFLOW_PREFIX):
        failures.append(
            "workflow triggers, permissions, concurrency, and defaults "
            "must match the exact bounded header"
        )

    require_fragments(
        failures,
        label="workflow",
        text=workflow,
        fragments=REQUIRED_TOP_LEVEL_FRAGMENTS,
    )

    for label, pattern in FORBIDDEN_SCOPE_PATTERNS.items():
        if re.search(pattern, workflow, flags=re.IGNORECASE):
            failures.append(f"workflow contains out-of-scope {label}")

    try:
        jobs_section = workflow.split("jobs:\n", 1)[1]
    except IndexError:
        failures.append("workflow is missing the jobs mapping")
        return failures

    found_jobs = tuple(
        re.findall(r"(?m)^  ([a-z][a-z0-9-]*):\n", jobs_section)
    )
    if found_jobs != JOB_IDS:
        failures.append(
            "workflow jobs must be exactly " + ", ".join(JOB_IDS)
        )

    runner_labels = tuple(
        re.findall(r"(?m)^    runs-on:\s*([^\s#]+)\s*$", jobs_section)
    )
    expected_runners = ("macos-26", "ubuntu-24.04")
    if runner_labels != expected_runners:
        failures.append(
            "workflow runners must be exactly " + ", ".join(expected_runners)
        )
    if re.search(r"(?m)^    if\s*:", jobs_section):
        failures.append("workflow jobs must not have a job-level condition")

    action_uses = tuple(re.findall(
        r"(?m)^\s*uses:\s*([^\s#]+)\s*$",
        workflow,
    ))
    expected_actions = (
        "actions/checkout@v7",
        "actions/checkout@v7",
        "actions/setup-java@v5",
        "gradle/actions/setup-gradle@v6",
    )
    if action_uses != expected_actions:
        failures.append("workflow actions must match the exact approved sequence")

    macos = job_body(workflow, "macos-product-quality")
    android = job_body(workflow, "android-product-quality")
    if macos is None:
        failures.append("workflow is missing job 'macos-product-quality'")
    if android is None:
        failures.append("workflow is missing job 'android-product-quality'")
    if macos is None or android is None:
        return failures

    require_exact_job(
        failures,
        label="macos-product-quality",
        job=macos,
        preamble=MACOS_JOB_PREAMBLE,
        steps=MACOS_STEPS,
    )
    require_exact_job(
        failures,
        label="android-product-quality",
        job=android,
        preamble=ANDROID_JOB_PREAMBLE,
        steps=ANDROID_STEPS,
    )

    developer_dirs = tuple(
        re.findall(r"(?m)^      DEVELOPER_DIR:\s*([^\s#]+)\s*$", macos)
    )
    expected_developer_dirs = (
        "/Applications/Xcode_26.6.app/Contents/Developer",
    )
    if developer_dirs != expected_developer_dirs:
        failures.append("macOS must use the exact Xcode 26.6 developer directory")

    require_fragments(
        failures,
        label="macos-product-quality",
        text=macos,
        fragments=(
            "runs-on: macos-26",
            "timeout-minutes: 120",
            "DEVELOPER_DIR: /Applications/Xcode_26.6.app/Contents/Developer",
            "fetch-depth: 0",
            "xcodebuild -version",
            'git diff --check "$BASE_SHA" "$HEAD_SHA"',
            "python3 -B script/check_product_ci.py",
            "python3 -B script/check_product_ci.py --self-test",
            "python3 -B script/check_product_nightly_ci.py",
            "PYTHONPATH=. python3 -B script/check_product_nightly_ci.py "
            "--run-contract-tests",
            "python3 -B script/check_copy_hygiene.py --product-copy-only",
            "python3 -B script/check_release_version_ledger.py",
            "python3 -B script/check_app_icons.py",
            "python3 -B script/check_license.py",
            "python3 -B script/generate_release_compliance.py check",
            "PYTHONPATH=. python3 -B script/check_product_ci.py "
            "--run-release-compliance-tests",
            "python3 -B script/check_docs_hygiene.py "
            "--tracked-contracts-only",
            "python3 -B -m unittest",
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[0],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[1],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[2],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[3],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[4],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[5],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[6],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[7],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[8],
            TRACKED_DOCUMENTATION_CONTRACT_TESTS[9],
            "PYTHONPATH=. python3 -B script/test_build_and_run.py",
            "PYTHONPATH=. python3 -B -m unittest",
            "script.test_run_macos_current_unsealed_install_recovery_smoke",
            "script.test_check_macos_current_unsealed_install_recovery_evidence."
            "CurrentUnsealedRecoveryEvidencePortableTests",
            "script.test_check_macos_current_unsealed_ci_lifecycle",
            "script.test_run_macos_runtime_chat_production_append_"
            "abrupt_recovery_smoke",
            "script.test_check_macos_runtime_chat_production_append_"
            "abrupt_recovery_evidence",
            "script.test_check_macos_current_source_lane_a_idle_"
            "resource_repeatability",
            "script.test_run_g7_nonsecurity_merge_full_current",
            "script.test_check_g7_nonsecurity_merge_full_current",
            "run: swift build --product AetherLink",
            "swift test list > "
            ".build/aetherlink-product-ci-swift-test-list-v1.txt",
            "python3 -B script/check_product_ci.py --swift-test-selection",
            "--prepare-swift-focused-test-run",
            "--run-swift-focused-tests",
            f"'{SWIFT_FILTER}'",
            "--write-swift-focused-test-binding",
            "--swift-focused-test-results",
            "script/run_g7_nonsecurity_merge_full_current.py",
            "--prepare",
            "--run",
            "--write-binding",
            "script/check_g7_nonsecurity_merge_full_current.py",
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "result.json",
            "--write-parent",
            "--parent-results",
            "--parent",
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "parent-result.json",
            "--prepare-document-ingestion-asan-run",
            "--run-document-ingestion-asan-tests",
            "--write-document-ingestion-asan-binding",
            "--document-ingestion-asan-results",
            "--prepare-document-ingestion-mutation-run",
            "--run-document-ingestion-mutation-tests",
            "--write-document-ingestion-mutation-binding",
            "--document-ingestion-mutation-results",
            MAIN_RELEASE_CONDITION,
            "python3 -B script/package_release_artifacts.py source-digest",
            "./script/build_and_run.sh --unsealed-package-only",
            'if [[ "$source_before" != "$source_after" ]]; then',
            "python3 -B script/check_release_artifact_archive.py",
            "--macos-build-outputs",
            "install -d -m 700 "
            ".build/aetherlink-current-unsealed-lifecycle-v1",
            "python3 -B "
            "script/run_macos_current_unsealed_install_recovery_smoke.py",
            "--result "
            ".build/aetherlink-current-unsealed-lifecycle-v1/result.json",
            "--repeatability-result "
            ".build/aetherlink-current-unsealed-lifecycle-v1/repeatability.json",
            "script/check_macos_current_unsealed_ci_lifecycle.py",
            "install -d -m 700 "
            ".build/aetherlink-production-append-recovery-v1",
            "script/run_macos_runtime_chat_production_append_"
            "abrupt_recovery_smoke.py",
            "--result "
            ".build/aetherlink-production-append-recovery-v1/result.json",
            "--repeatability-receipt "
            ".build/aetherlink-production-append-recovery-v1/"
            "repeatability.json",
            "script/check_macos_runtime_chat_production_append_"
            "abrupt_recovery_evidence.py",
        ),
    )

    require_fragments(
        failures,
        label="android-product-quality",
        text=android,
        fragments=(
            "runs-on: ubuntu-24.04",
            "timeout-minutes: 60",
            'java-version: "21"',
            "cache-provider: basic",
            "cache-read-only: ${{ github.event_name == 'pull_request' }}",
            'test -d "$ANDROID_HOME/platforms/android-36"',
            'test -d "$ANDROID_HOME/build-tools/36.0.0"',
            ":app:compileDebugKotlin",
            ":app:compileDebugUnitTestKotlin",
            ":app:testDebugUnitTest",
            *tuple(f"--tests {test}" for test in ANDROID_TESTS),
            "python3 -B script/check_product_ci.py --android-test-results",
            "--prepare-android-full-test-run",
            "--rerun-tasks",
            *tuple(
                f"--tests {test}" for test in ANDROID_MAIN_FULL_TESTS
            ),
            "--write-android-full-test-binding",
            "--android-full-test-results",
            "--prepare-android-core-nonsecurity-test-run",
            "--run-android-core-nonsecurity-tests",
            "--write-android-core-nonsecurity-test-binding",
            "--android-core-nonsecurity-test-results",
            MAIN_RELEASE_CONDITION,
            "-PaetherlinkStrictReleaseDependencyLocks=true",
            ":app:assembleRelease",
            ":app:bundleRelease",
            ":app:lintRelease",
            "python3 -B script/check_release_artifact_archive.py",
            "--android-build-outputs",
            "script.test_run_android_release_repeatability_current",
            "script.test_check_android_release_repeatability_current",
            PULL_REQUEST_CONDITION,
            "script/run_android_release_repeatability_current.py",
            "script/check_android_release_repeatability_current.py",
            ".build/aetherlink-android-release-repeatability-v1/result.json",
        ),
    )

    if workflow.count("swift test") != 1:
        failures.append(
            "workflow must contain one direct Swift test-list command; the "
            "focused execution must use the bounded result runner"
        )
    for command in (
        "--prepare-swift-focused-test-run",
        "--run-swift-focused-tests",
        "--write-swift-focused-test-binding",
        "--swift-focused-test-results",
    ):
        if workflow.count(command) != 1:
            failures.append(
                f"workflow must invoke {command} exactly once"
            )
    current_run_commands = (
        "python3 -B script/run_g7_nonsecurity_merge_full_current.py\n"
        "          --prepare",
        "python3 -B script/run_g7_nonsecurity_merge_full_current.py\n"
        "          --run",
        "python3 -B script/run_g7_nonsecurity_merge_full_current.py "
        "--write-binding",
        "python3 -B script/run_g7_nonsecurity_merge_full_current.py --results",
        "python3 -I -B -S\n"
        "          script/check_g7_nonsecurity_merge_full_current.py\n"
        "          .build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
        "result.json",
    )
    for command in current_run_commands:
        if workflow.count(command) != 1:
            failures.append(
                "workflow must invoke each G7 current-run lifecycle command "
                "exactly once"
            )
    for command in (
        "--prepare-android-core-nonsecurity-test-run",
        "--run-android-core-nonsecurity-tests",
        "--write-android-core-nonsecurity-test-binding",
        "--android-core-nonsecurity-test-results",
    ):
        if workflow.count(command) != 1:
            failures.append(
                "workflow must invoke each Android core non-security "
                f"lifecycle command exactly once: {command}"
            )
    product_copy_command = (
        "python3 -B script/check_copy_hygiene.py --product-copy-only"
    )
    if workflow.count(product_copy_command) != 1:
        failures.append(
            "workflow must contain one exact non-security product copy command"
        )
    compliance_check_command = (
        "python3 -B script/generate_release_compliance.py check"
    )
    compliance_test_command = (
        "PYTHONPATH=. python3 -B script/check_product_ci.py "
        "--run-release-compliance-tests"
    )
    if (
        workflow.count(compliance_check_command) != 1
        or workflow.count(compliance_test_command) != 1
    ):
        failures.append(
            "workflow must contain one exact offline release compliance "
            "catalog check and one independent reconstruction test command"
        )
    if (
        named_step_body(macos, "Run release compliance contracts")
        != RELEASE_COMPLIANCE_CONTRACT_STEP_BODY
    ):
        failures.append(
            "release compliance contract step must match the exact offline "
            "check and independent reconstruction command body"
        )
    release_readback_command = (
        "python3 -B script/check_release_artifact_archive.py"
    )
    if (
        workflow.count(release_readback_command) != 2
        or workflow.count("--android-build-outputs") != 1
        or workflow.count("--macos-build-outputs") != 1
    ):
        failures.append(
            "workflow must contain one exact Android and one exact macOS "
            "Release readback command"
        )
    repeatability_commands = (
        "script.test_run_android_release_repeatability_current",
        "script.test_check_android_release_repeatability_current",
        "script/run_android_release_repeatability_current.py",
        "script/check_android_release_repeatability_current.py",
        ".build/aetherlink-android-release-repeatability-v1/result.json",
    )
    if any(workflow.count(command) != 1 for command in repeatability_commands):
        failures.append(
            "workflow must invoke each Android Release repeatability unit, "
            "producer, checker, and result path exactly once"
        )
    if workflow.count("./script/build_and_run.sh --unsealed-package-only") != 1:
        failures.append(
            "workflow must contain one exact unsealed macOS Release producer"
        )
    if workflow.count(
        "python3 -B script/package_release_artifacts.py source-digest"
    ) != 2:
        failures.append(
            "macOS unsealed Release producer must bind source before and "
            "after packaging"
        )
    if (
        named_step_body(
            macos,
            "Run macOS release package contract units",
        )
        != MACOS_PACKAGE_CONTRACT_TEST_STEP_BODY
    ):
        failures.append(
            "macOS release package contract-unit step must match the exact "
            "command body"
        )
    if (
        named_step_body(
            macos,
            "Run macOS lifecycle contract units",
        )
        != MACOS_LIFECYCLE_CONTRACT_TEST_STEP_BODY
    ):
        failures.append(
            "macOS lifecycle contract-unit step must match the exact command "
            "body"
        )
    if (
        named_step_body(
            macos,
            "Run G7 current-run contract units",
        )
        != G7_CURRENT_RUN_CONTRACT_TEST_STEP_BODY
    ):
        failures.append(
            "G7 current-run contract-unit step must match the exact producer/"
            "checker test body"
        )
    if (
        named_step_body(
            macos,
            "Run release diagnostics contract units",
        )
        != RELEASE_DIAGNOSTICS_CONTRACT_TEST_STEP_BODY
    ):
        failures.append(
            "release diagnostics contract-unit step must match the exact "
            "producer/checker test body"
        )
    if (
        named_step_body(
            macos,
            "Build unsealed macOS Release package on main",
        )
        != MACOS_UNSEALED_RELEASE_BUILD_STEP_BODY
    ):
        failures.append(
            "macOS unsealed Release producer step must match the exact "
            "main-only command body"
        )
    macos_unsealed_readback_body = named_step_body(
        macos,
        "Read back unsealed macOS Release package on main",
    )
    if (
        macos_unsealed_readback_body is None
        or macos_unsealed_readback_body.rstrip()
        != MACOS_UNSEALED_RELEASE_READBACK_STEP_BODY.rstrip()
    ):
        failures.append(
            "macOS unsealed Release readback step must match the exact "
            "main-only command body"
        )
    if (
        named_step_body(
            macos,
            "Run macOS Release diagnostics on main",
        )
        != MACOS_RELEASE_DIAGNOSTICS_RUN_STEP_BODY
    ):
        failures.append(
            "macOS Release diagnostics producer must match the exact "
            "main-only command body"
        )
    if (
        named_step_body(
            macos,
            "Read back macOS Release diagnostics on main",
        )
        != MACOS_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY
    ):
        failures.append(
            "macOS Release diagnostics checker must match the exact "
            "main-only command body"
        )
    if (
        named_step_body(
            macos,
            "Run current unsealed lifecycle on main",
        )
        != MACOS_CURRENT_UNSEALED_LIFECYCLE_RUN_STEP_BODY
    ):
        failures.append(
            "macOS current-unsealed lifecycle runner step must match the "
            "exact main-only command body"
        )
    current_unsealed_lifecycle_readback_body = named_step_body(
        macos,
        "Read back current unsealed lifecycle on main",
    )
    if (
        current_unsealed_lifecycle_readback_body is None
        or current_unsealed_lifecycle_readback_body.rstrip()
        != MACOS_CURRENT_UNSEALED_LIFECYCLE_READBACK_STEP_BODY.rstrip()
    ):
        failures.append(
            "macOS current-unsealed lifecycle readback step must match the "
            "exact main-only command body"
        )
    if (
        named_step_body(
            macos,
            "Run production append abrupt recovery on main",
        )
        != MACOS_PRODUCTION_APPEND_RECOVERY_RUN_STEP_BODY
    ):
        failures.append(
            "macOS production append recovery runner step must match the "
            "exact main-only command body"
        )
    production_append_recovery_readback_body = named_step_body(
        macos,
        "Read back production append abrupt recovery on main",
    )
    if (
        production_append_recovery_readback_body is None
        or production_append_recovery_readback_body.rstrip()
        != MACOS_PRODUCTION_APPEND_RECOVERY_READBACK_STEP_BODY.rstrip()
    ):
        failures.append(
            "macOS production append recovery readback step must match the "
            "exact main-only command body"
        )
    if (
        named_step_body(macos, "Verify focused Swift test selection")
        != SWIFT_TEST_SELECTION_STEP_BODY
    ):
        failures.append(
            "Swift focused test selection step must match the exact command "
            "body"
        )
    if (
        named_step_body(macos, "Run focused product units")
        != SWIFT_TEST_STEP_BODY
    ):
        failures.append("Swift focused test step must match the exact command body")
    if (
        named_step_body(
            macos,
            "Bind and verify focused Swift test results",
        )
        != SWIFT_TEST_RESULT_STEP_BODY
    ):
        failures.append(
            "Swift focused test result step must match the exact command body"
        )
    current_run_steps = (
        (
            "Prepare G7 non-security current run on main",
            G7_CURRENT_RUN_PREPARE_STEP_BODY,
        ),
        (
            "Run G7 non-security current run on main",
            G7_CURRENT_RUN_RUN_STEP_BODY,
        ),
        (
            "Bind and verify G7 non-security current run on main",
            G7_CURRENT_RUN_BIND_STEP_BODY,
        ),
        (
            "Independently read back G7 non-security current run on main",
            G7_CURRENT_RUN_READBACK_STEP_BODY,
        ),
        (
            "Bind and verify G7 non-security current parent on main",
            G7_CURRENT_PARENT_BIND_STEP_BODY,
        ),
        (
            "Independently read back G7 non-security current parent on main",
            G7_CURRENT_PARENT_READBACK_STEP_BODY,
        ),
    )
    for step_name, expected_body in current_run_steps:
        if named_step_body(macos, step_name) != expected_body:
            failures.append(
                f"{step_name} step must match the exact main-only command body"
            )
    asan_steps = (
        (
            "Prepare DocumentIngestion ASan corpus on main",
            DOCUMENT_INGESTION_ASAN_PREPARE_STEP_BODY,
        ),
        (
            "Run DocumentIngestion ASan corpus on main",
            DOCUMENT_INGESTION_ASAN_RUN_STEP_BODY,
        ),
        (
            "Bind and verify DocumentIngestion ASan corpus on main",
            DOCUMENT_INGESTION_ASAN_RESULT_STEP_BODY,
        ),
    )
    for step_name, expected_body in asan_steps:
        if named_step_body(macos, step_name) != expected_body:
            failures.append(
                f"{step_name} step must match the exact main-only command body"
            )
    mutation_steps = (
        (
            "Prepare DocumentIngestion mutation corpus on main",
            DOCUMENT_INGESTION_MUTATION_PREPARE_STEP_BODY,
        ),
        (
            "Run DocumentIngestion mutation corpus on main",
            DOCUMENT_INGESTION_MUTATION_RUN_STEP_BODY,
        ),
        (
            "Bind and verify DocumentIngestion mutation corpus on main",
            DOCUMENT_INGESTION_MUTATION_RESULT_STEP_BODY,
        ),
    )
    for step_name, expected_body in mutation_steps:
        if named_step_body(macos, step_name) != expected_body:
            failures.append(
                f"{step_name} step must match the exact main-only command body"
            )
    if SWIFT_FOCUSED_RUN_COMMAND != (
        "swift",
        "test",
        "--filter",
        SWIFT_FILTER,
    ):
        failures.append(
            "Swift focused result runner must use the exact serial product "
            "allowlist command"
        )
    if DOCUMENT_INGESTION_ASAN_RUN_COMMAND != (
        "swift",
        "test",
        "--scratch-path",
        ".build/aetherlink-document-ingestion-asan-v1",
        "--sanitize",
        "address",
        "--no-parallel",
        "--filter",
        DOCUMENT_INGESTION_ASAN_FILTER,
    ):
        failures.append(
            "DocumentIngestion ASan runner must use the exact isolated "
            "address-sanitizer corpus command"
        )
    if DOCUMENT_INGESTION_MUTATION_RUN_COMMAND != (
        "swift",
        "test",
        "--scratch-path",
        ".build/aetherlink-document-ingestion-asan-v1",
        "--sanitize",
        "address",
        "--no-parallel",
        "--filter",
        DOCUMENT_INGESTION_MUTATION_FILTER,
    ):
        failures.append(
            "DocumentIngestion mutation runner must reuse the exact isolated "
            "address-sanitizer scratch and selector"
        )
    if (
        SWIFT_FOCUSED_PACKAGE_SOURCE_PATHS
        != tuple(path for _, _, path in SWIFT_FOCUSED_PACKAGE_TARGETS)
        or SWIFT_FOCUSED_RESULT_SOURCE_ROOTS
        != tuple(ROOT / path for path in SWIFT_FOCUSED_PACKAGE_SOURCE_PATHS)
        or SWIFT_FOCUSED_PACKAGE_DUMP_COMMAND
        != ("swift", "package", "dump-package")
    ):
        failures.append(
            "Swift focused package roots must derive from the exact semantic "
            "target contract"
        )

    strict_flag = "-PaetherlinkStrictReleaseDependencyLocks=true"
    release_index = android.find(
        "      - name: Compile and lint Android Release app on pull request\n"
    )
    if release_index < 0:
        failures.append("Android Release pull-request step is missing")
    else:
        if strict_flag in android[:release_index]:
            failures.append(
                "Android debug compilation/tests must not use strict locks"
            )
        if strict_flag not in android[release_index:]:
            failures.append("Android Release compilation must use strict locks")

    android_tests = tuple(
        re.findall(r"(?m)^\s+--tests\s+([^\s#]+)\s*$", android)
    )
    if android_tests != ANDROID_TESTS + ANDROID_MAIN_FULL_TESTS:
        failures.append(
            "Android focused and complete app tests must use the exact "
            "allowlists; core non-security selectors stay inside "
            "the bounded runner"
        )

    if (
        named_step_body(
            android,
            "Run Android Release repeatability contract units",
        )
        != ANDROID_RELEASE_REPEATABILITY_CONTRACT_TEST_STEP_BODY
    ):
        failures.append(
            "Android Release repeatability contract units must match the "
            "exact command body"
        )
    if (
        named_step_body(
            android,
            "Compile Android and run focused product units",
        )
        != ANDROID_TEST_STEP_BODY
    ):
        failures.append(
            "Android focused test step must match the exact command body"
        )
    if (
        named_step_body(
            android,
            "Verify focused Android test results",
        )
        != ANDROID_TEST_RESULT_STEP_BODY
    ):
        failures.append(
            "Android focused test result step must match the exact command body"
        )
    if (
        named_step_body(
            android,
            "Prepare complete Android app units on main",
        )
        != ANDROID_MAIN_FULL_PREPARE_STEP_BODY
    ):
        failures.append(
            "Android complete test preparation step must match the exact "
            "main-only command body"
        )
    if (
        named_step_body(
            android,
            "Run complete Android app units on main",
        )
        != ANDROID_MAIN_FULL_TEST_STEP_BODY
    ):
        failures.append(
            "Android complete test step must match the exact main-only "
            "command body"
        )
    if (
        named_step_body(
            android,
            "Bind and verify complete Android app units on main",
        )
        != ANDROID_MAIN_FULL_RESULT_STEP_BODY
    ):
        failures.append(
            "Android complete result step must match the exact main-only "
            "command body"
        )
    core_nonsecurity_steps = (
        (
            "Prepare Android core non-security units on main",
            ANDROID_CORE_NONSECURITY_PREPARE_STEP_BODY,
        ),
        (
            "Run Android core non-security units on main",
            ANDROID_CORE_NONSECURITY_TEST_STEP_BODY,
        ),
        (
            "Bind and verify Android core non-security units on main",
            ANDROID_CORE_NONSECURITY_RESULT_STEP_BODY,
        ),
    )
    for step_name, expected_body in core_nonsecurity_steps:
        if named_step_body(android, step_name) != expected_body:
            failures.append(
                f"{step_name} step must match the exact main-only command body"
            )
    if (
        named_step_body(
            android,
            "Compile and lint Android Release app on pull request",
        )
        != ANDROID_RELEASE_STEP_BODY
    ):
        failures.append(
            "Android Release pull-request step must match the exact "
            "condition and command body"
        )
    if (
        named_step_body(
            android,
            "Run Android Release A/B repeatability on main",
        )
        != ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY
    ):
        failures.append(
            "Android Release repeatability producer must match the exact "
            "main-only command body"
        )
    if (
        named_step_body(
            android,
            "Read back Android Release A/B repeatability on main",
        )
        != ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY
    ):
        failures.append(
            "Android Release repeatability checker must match the exact "
            "main-only command body"
        )
    if (
        named_step_body(
            android,
            "Read back Android Release build outputs",
        )
        != ANDROID_RELEASE_READBACK_STEP_BODY
    ):
        failures.append(
            "Android Release readback step must match the exact "
            "command body"
        )
    if (
        named_step_body(
            android,
            "Run Android Release diagnostics on main",
        )
        != ANDROID_RELEASE_DIAGNOSTICS_RUN_STEP_BODY
    ):
        failures.append(
            "Android Release diagnostics producer must match the exact "
            "main-only command body"
        )
    if (
        named_step_body(
            android,
            "Read back Android Release diagnostics on main",
        )
        != ANDROID_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY
    ):
        failures.append(
            "Android Release diagnostics checker must match the exact "
            "main-only command body"
        )

    diagnostics_runner = "script/run_release_diagnostics_usability.py"
    diagnostics_checker = "script/check_release_diagnostics_usability.py"
    if workflow.count(diagnostics_runner) != 2:
        failures.append(
            "workflow must run exactly one macOS and one Android Release "
            "diagnostics producer"
        )
    if workflow.count(diagnostics_checker) != 2:
        failures.append(
            "workflow must run exactly one macOS and one Android Release "
            "diagnostics readback"
        )
    for platform in ("macos", "android"):
        if workflow.count(f"--platform {platform}") != 2:
            failures.append(
                f"workflow must bind the {platform} diagnostics platform "
                "once at production and once at readback"
            )

    android_tasks = tuple(
        re.findall(r"(?m)^\s+(:[A-Za-z0-9][A-Za-z0-9:_-]*)\s*$", android)
    )
    if android_tasks != ANDROID_TASKS:
        failures.append("Android Gradle tasks must match the exact product task list")
    if re.search(r"(?m)^\s+(?:build|check|test|assemble|lint)\s*$", android):
        failures.append("Android must not run a broad Gradle lifecycle task")
    if re.search(
        r"(?<!\S)(?:-x|--exclude-task|--dry-run)(?=\s|=|$)",
        android,
    ):
        failures.append("Android Gradle invocation must not skip or dry-run tasks")

    return failures


def self_test(workflow: str) -> list[str]:
    failures: list[str] = []

    byte_mutation = workflow + "# byte-pin self-test\n"
    byte_failures = workflow_failures(byte_mutation)
    if not any(
        "workflow bytes differ from the reviewed contract" in failure
        for failure in byte_failures
    ):
        failures.append("self-test did not exercise the workflow byte pin")

    mutations = {
        "parsed semantic fingerprint": (
            workflow.replace(
                "name: Product quality (non-security subset)\n",
                "name: Product quality subset renamed\n",
                1,
            ),
            "parsed workflow semantics differ from the exact contract",
        ),
        "narrowed pull-request events": (
            workflow.replace(
                "  pull_request:\n",
                "  pull_request:\n    types: [opened]\n",
                1,
            ),
            "exact bounded header",
        ),
        "expanded permission map": (
            workflow.replace(
                "permissions:\n  contents: read\n",
                "permissions:\n  contents: read\n  issues: write\n",
                1,
            ),
            "exact bounded header",
        ),
        "disabled macOS job": (
            workflow.replace(
                "    name: macOS product quality subset\n",
                "    name: macOS product quality subset\n    if: false\n",
                1,
            ),
            "job-level condition",
        ),
        "disabled macOS compile step": (
            workflow.replace(
                "      - name: Compile macOS app\n"
                "        run: swift build --product AetherLink\n",
                "      - name: Compile macOS app\n"
                "        if: false\n"
                "        run: swift build --product AetherLink\n",
                1,
            ),
            "step 'Compile macOS app' must match the exact body",
        ),
        "disabled changed-byte command": (
            workflow.replace(
                '            git diff --check "$BASE_SHA" "$HEAD_SHA"\n',
                '            true # git diff --check "$BASE_SHA" "$HEAD_SHA"\n',
                1,
            ),
            "step 'Check changed bytes' must match the exact body",
        ),
        "missing product-nightly contract step": (
            workflow.replace(
                "      - name: Validate product-nightly contract\n"
                f"{PRODUCT_NIGHTLY_CONTRACT_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "product-nightly exact test runner omission": (
            workflow.replace(
                "          PYTHONPATH=. python3 -B "
                "script/check_product_nightly_ci.py --run-contract-tests\n",
                "",
                1,
            ),
            "step 'Validate product-nightly contract' must match the exact body",
        ),
        "missing tracked documentation contract step": (
            workflow.replace(
                "      - name: Run tracked documentation contracts\n"
                + TRACKED_DOCUMENTATION_CONTRACT_STEP_BODY,
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing release compliance contract step": (
            workflow.replace(
                "      - name: Run release compliance contracts\n"
                f"{RELEASE_COMPLIANCE_CONTRACT_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "release compliance network refresh substitution": (
            workflow.replace(
                "python3 -B script/generate_release_compliance.py check",
                "python3 -B script/generate_release_compliance.py refresh",
                1,
            ),
            "one exact offline release compliance catalog check",
        ),
        "release compliance independent reconstruction omission": (
            workflow.replace(
                "          PYTHONPATH=. python3 -B script/check_product_ci.py "
                "--run-release-compliance-tests\n",
                "",
                1,
            ),
            "one exact offline release compliance catalog check",
        ),
        "release compliance unbound unittest substitution": (
            workflow.replace(
                "          PYTHONPATH=. python3 -B script/check_product_ci.py "
                "--run-release-compliance-tests\n",
                "          PYTHONPATH=. python3 -B -m unittest "
                "script.test_release_compliance\n",
                1,
            ),
            "one exact offline release compliance catalog check",
        ),
        "tracked documentation full-evidence substitution": (
            workflow.replace(
                "          python3 -B script/check_docs_hygiene.py "
                "--tracked-contracts-only\n",
                "          python3 -B script/check_docs_hygiene.py\n",
                1,
            ),
            "step 'Run tracked documentation contracts' must match the exact body",
        ),
        "tracked documentation mutation-test omission": (
            workflow.replace(
                f"            {TRACKED_DOCUMENTATION_CONTRACT_TESTS[9]}\n",
                "",
                1,
            ),
            "step 'Run tracked documentation contracts' must match the exact body",
        ),
        "missing macOS package contract units": (
            workflow.replace(
                "      - name: Run macOS release package contract units\n"
                f"{MACOS_PACKAGE_CONTRACT_TEST_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing macOS lifecycle contract units": (
            workflow.replace(
                "      - name: Run macOS lifecycle contract units\n"
                f"{MACOS_LIFECYCLE_CONTRACT_TEST_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing macOS idle repeatability checker units": (
            workflow.replace(
                "          script.test_check_macos_current_source_lane_a_"
                "idle_resource_repeatability\n",
                "",
                1,
            ),
            "macOS lifecycle contract-unit step must match the exact command "
            "body",
        ),
        "missing G7 current-run contract units": (
            workflow.replace(
                "      - name: Run G7 current-run contract units\n"
                f"{G7_CURRENT_RUN_CONTRACT_TEST_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing G7 current-run execution": (
            workflow.replace(
                "      - name: Run G7 non-security current run on main\n"
                f"{G7_CURRENT_RUN_RUN_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "G7 current-run independent checker bypass": (
            workflow.replace(
                "          python3 -I -B -S\n"
                "          script/check_g7_nonsecurity_merge_full_current.py\n",
                "          python3 -B "
                "script/run_g7_nonsecurity_merge_full_current.py --results\n",
                1,
            ),
            "Independently read back G7 non-security current run on main step "
            "must match the exact main-only command body",
        ),
        "missing G7 current parent binding": (
            workflow.replace(
                "      - name: Bind and verify G7 non-security current parent on main\n"
                f"{G7_CURRENT_PARENT_BIND_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "G7 current parent independent checker bypass": (
            workflow.replace(
                "          python3 -I -B -S\n"
                "          script/check_g7_nonsecurity_merge_full_current.py\n"
                "          --parent\n"
                "          .build/aetherlink-g7-nonsecurity-merge-full-"
                "current-run-v1/parent-result.json\n",
                "          python3 -B "
                "script/run_g7_nonsecurity_merge_full_current.py "
                "--parent-results\n",
                1,
            ),
            "Independently read back G7 non-security current parent on main "
            "step must match the exact main-only command body",
        ),
        "missing portable macOS lifecycle checker units": (
            workflow.replace(
                "          script.test_check_macos_current_unsealed_install_"
                "recovery_evidence.CurrentUnsealedRecoveryEvidencePortableTests\n",
                "",
                1,
            ),
            "step 'Run macOS lifecycle contract units' must match the exact body",
        ),
        "missing current-run macOS lifecycle checker units": (
            workflow.replace(
                "          script.test_check_macos_current_unsealed_ci_lifecycle\n",
                "",
                1,
            ),
            "step 'Run macOS lifecycle contract units' must match the exact body",
        ),
        "missing release diagnostics contract units": (
            workflow.replace(
                "      - name: Run release diagnostics contract units\n"
                f"{RELEASE_DIAGNOSTICS_CONTRACT_TEST_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing release diagnostics checker unit module": (
            workflow.replace(
                "          script.test_check_release_diagnostics_usability\n",
                "",
                1,
            ),
            "step 'Run release diagnostics contract units' must match the exact body",
        ),
        "missing macOS unsealed Release producer": (
            workflow.replace(
                "      - name: Build unsealed macOS Release package on main\n"
                f"{MACOS_UNSEALED_RELEASE_BUILD_STEP_BODY}",
                "",
                1,
            ),
            "one exact unsealed macOS Release producer",
        ),
        "missing macOS unsealed Release readback": (
            workflow.replace(
                "      - name: Read back unsealed macOS Release package on main\n"
                f"{MACOS_UNSEALED_RELEASE_READBACK_STEP_BODY}",
                "",
                1,
            ),
            "one exact Android and one exact macOS Release readback command",
        ),
        "missing macOS Release diagnostics producer": (
            workflow.replace(
                "      - name: Run macOS Release diagnostics on main\n"
                f"{MACOS_RELEASE_DIAGNOSTICS_RUN_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing macOS Release diagnostics readback": (
            workflow.replace(
                "      - name: Read back macOS Release diagnostics on main\n"
                f"{MACOS_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "macOS diagnostics platform substitution": (
            workflow.replace(
                "            --platform macos \\\n",
                "            --platform android \\\n",
                1,
            ),
            "producer must match the exact main-only command body",
        ),
        "missing current-unsealed lifecycle runner": (
            workflow.replace(
                "      - name: Run current unsealed lifecycle on main\n"
                f"{MACOS_CURRENT_UNSEALED_LIFECYCLE_RUN_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing current-unsealed lifecycle readback": (
            workflow.replace(
                "      - name: Read back current unsealed lifecycle on main\n"
                f"{MACOS_CURRENT_UNSEALED_LIFECYCLE_READBACK_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "signed package substituted for unsealed producer": (
            workflow.replace(
                "./script/build_and_run.sh --unsealed-package-only",
                "./script/build_and_run.sh --package-only",
                1,
            ),
            "one exact unsealed macOS Release producer",
        ),
        "wrong macOS Release readback mode": (
            workflow.replace(
                "          --macos-build-outputs\n",
                "          --historical\n",
                1,
            ),
            "one exact Android and one exact macOS Release readback command",
        ),
        "macOS unsealed producer condition removed": (
            workflow.replace(
                "      - name: Build unsealed macOS Release package on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Build unsealed macOS Release package on main\n",
                1,
            ),
            "producer step must match the exact main-only command body",
        ),
        "macOS unsealed readback condition removed": (
            workflow.replace(
                "      - name: Read back unsealed macOS Release package on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Read back unsealed macOS Release package on main\n",
                1,
            ),
            "readback step must match the exact main-only command body",
        ),
        "macOS unsealed build and readback reordered": (
            workflow.replace(
                "      - name: Build unsealed macOS Release package on main\n"
                f"{MACOS_UNSEALED_RELEASE_BUILD_STEP_BODY}"
                "      - name: Read back unsealed macOS Release package on main\n"
                f"{MACOS_UNSEALED_RELEASE_READBACK_STEP_BODY}",
                "      - name: Read back unsealed macOS Release package on main\n"
                f"{MACOS_UNSEALED_RELEASE_READBACK_STEP_BODY}"
                "      - name: Build unsealed macOS Release package on main\n"
                f"{MACOS_UNSEALED_RELEASE_BUILD_STEP_BODY}",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "current-unsealed lifecycle condition removed": (
            workflow.replace(
                "      - name: Run current unsealed lifecycle on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Run current unsealed lifecycle on main\n",
                1,
            ),
            "runner step must match the exact main-only command body",
        ),
        "current-unsealed lifecycle readback condition removed": (
            workflow.replace(
                "      - name: Read back current unsealed lifecycle on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Read back current unsealed lifecycle on main\n",
                1,
            ),
            "readback step must match the exact main-only command body",
        ),
        "macOS source drift comparison bypassed": (
            workflow.replace(
                '          if [[ "$source_before" != "$source_after" ]]; then\n',
                "          if false; then\n",
                1,
            ),
            "producer step must match the exact main-only command body",
        ),
        "changed runner with decoy": (
            workflow.replace(
                "    runs-on: macos-26\n",
                "    runs-on: macos-15\n    # runs-on: macos-26\n",
                1,
            ),
            "workflow runners must be exactly",
        ),
        "wrong Xcode directory": (
            workflow.replace(
                "Xcode_26.6.app",
                "Xcode_26.5.app",
                1,
            ),
            "exact Xcode 26.6 developer directory",
        ),
        "old checkout action": (
            workflow.replace(
                "actions/checkout@v7",
                "actions/checkout@v6",
                1,
            ),
            "exact approved sequence",
        ),
        "old setup-java action": (
            workflow.replace(
                "actions/setup-java@v5",
                "actions/setup-java@v4",
                1,
            ),
            "exact approved sequence",
        ),
        "unfiltered Swift suite": (
            workflow.replace(
                "      - name: Build unsealed macOS Release package on main\n",
                "      - run: swift test\n"
                "      - name: Build unsealed macOS Release package on main\n",
                1,
            ),
            "one direct Swift test-list command",
        ),
        "missing Swift test selection step": (
            workflow.replace(
                "      - name: Verify focused Swift test selection\n"
                f"{SWIFT_TEST_SELECTION_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "Swift test selection list bypass": (
            workflow.replace(
                "          swift test list > "
                ".build/aetherlink-product-ci-swift-test-list-v1.txt\n",
                "          printf '' > "
                ".build/aetherlink-product-ci-swift-test-list-v1.txt\n",
                1,
            ),
            "selection step must match the exact command body",
        ),
        "missing Swift test selection checker": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--swift-test-selection\n",
                "",
                1,
            ),
            "selection step must match the exact command body",
        ),
        "missing Swift focused source marker": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--prepare-swift-focused-test-run\n",
                "",
                1,
            ),
            "selection step must match the exact command body",
        ),
        "bypassed Swift focused result runner": (
            workflow.replace(
                "          --run-swift-focused-tests\n",
                "          --swift-test-selection\n",
                1,
            ),
            "focused test step must match the exact command body",
        ),
        "missing DocumentIngestion ASan preparation": (
            workflow.replace(
                "      - name: Prepare DocumentIngestion ASan corpus on main\n"
                f"{DOCUMENT_INGESTION_ASAN_PREPARE_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "bypassed DocumentIngestion ASan execution": (
            workflow.replace(
                "          --run-document-ingestion-asan-tests\n",
                "          --document-ingestion-asan-results\n",
                1,
            ),
            "step must match the exact main-only command body",
        ),
        "DocumentIngestion ASan main condition removed": (
            workflow.replace(
                "      - name: Run DocumentIngestion ASan corpus on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Run DocumentIngestion ASan corpus on main\n",
                1,
            ),
            "step must match the exact main-only command body",
        ),
        "missing DocumentIngestion ASan independent readback": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--document-ingestion-asan-results\n",
                "",
                1,
            ),
            "step must match the exact main-only command body",
        ),
        "missing DocumentIngestion mutation preparation": (
            workflow.replace(
                "      - name: Prepare DocumentIngestion mutation corpus on main\n"
                f"{DOCUMENT_INGESTION_MUTATION_PREPARE_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "bypassed DocumentIngestion mutation execution": (
            workflow.replace(
                "          --run-document-ingestion-mutation-tests\n",
                "          --document-ingestion-mutation-results\n",
                1,
            ),
            "step must match the exact main-only command body",
        ),
        "DocumentIngestion mutation main condition removed": (
            workflow.replace(
                "      - name: Run DocumentIngestion mutation corpus on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Run DocumentIngestion mutation corpus on main\n",
                1,
            ),
            "step must match the exact main-only command body",
        ),
        "missing DocumentIngestion mutation independent readback": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--document-ingestion-mutation-results\n",
                "",
                1,
            ),
            "step must match the exact main-only command body",
        ),
        "extra Swift filter": (
            workflow.replace(
                "          --swift-focused-filter\n",
                "          --swift-focused-filter ExtraProductTests\n"
                "          --swift-focused-filter\n",
                1,
            ),
            "exact command body",
        ),
        "missing AppKit termination lifecycle regressions": (
            workflow.replace(
                "AppLifecycleTests|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing active-request termination drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testApplicationTerminationRejectsNewRequestsAndDrainsRetiringTasks|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing request-registration termination drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testApplicationTerminationDrainsRequestBlockedDuringRegistration|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing chat-title cancellation drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testApplicationTerminationWaitsForChatTitleCancellationDispatch|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing memory-summary cancellation drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testApplicationTerminationWaitsForMemorySummaryCancellationDispatch|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing deferred publication success drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testApplicationTerminationWaitsForDeferredSummaryPublicationAndPersistence|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing deferred publication failure drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testApplicationTerminationDrainsFailedDeferredSummaryPublicationWithoutPersistence|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing queued persistence drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testMemorySummaryDraftGeneratePublishesBeforeBlockingDurableCache|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing retention maintenance drain regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelTerminationCancelsAndDrainsRuntimeChatRetentionMaintenance|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing provider health recovery regressions": (
            workflow.replace(
                "ProviderHealthRecoveryTests|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing Ollama health timeout regression": (
            workflow.replace(
                "OllamaBackendHealthTimeoutTests/"
                "testHealthCheckUsesFiveSecondsWhileCatalogRetainsSixtySeconds|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing LM Studio health timeout regression": (
            workflow.replace(
                "LMStudioBackendHealthTimeoutTests/"
                "testHealthCheckUsesFiveSecondsWhileCatalogRetainsSixtySeconds|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing active Runtime sleep-wake regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelSuspendsAndResumesActiveRuntimeOnceAtSamePort|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing starting Runtime sleep-wake generation regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelSuspendsStartingRuntimeAndIgnoresPreSleepCallbacks|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing stopped or failed Runtime wake regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelDoesNotResumeStoppedOrFailedRuntimeAfterSystemWake|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing Runtime model stop regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelStartsReplaceableTransportAndStopsIt|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing manager stop-all idempotency regression": (
            workflow.replace(
                "MacRuntimeConnectionManagerTests/"
                "testStopAllStopsLocalAdvertiserBootstrapAndPairsExactlyOnce|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing Runtime retry regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelUserInterfaceStartCanRetryAfterListenerFailure|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing late Runtime failure regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelLateListenerFailureAllowsSamePortRetryAndIgnoresStaleCallback|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing listener admission race regression": (
            workflow.replace(
                "LocalPeerServerTests/"
                "testPeerAdmissionCannotCrossListenerStopGenerationBoundary|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing occupied-port listener regression": (
            workflow.replace(
                "LocalPeerServerTests/"
                "testLocalPeerServerOccupiedPortFailsThenSameInstanceRetries|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing concrete occupied-port manager regression": (
            workflow.replace(
                "MacRuntimeConnectionManagerTests/"
                "testConcreteLocalListenerDefersAdvertisementAndRetriesAfterOccupiedPort|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing unexpected-port manager regression": (
            workflow.replace(
                "MacRuntimeConnectionManagerTests/"
                "testUnexpectedLocalPortCannotRemainStartingOrAdvertising|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing Runtime port-replacement regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelPortReplacementShowsStartingUntilReady|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing pairing listener-readiness regression": (
            workflow.replace(
                "LocalRuntimeMessageRouterTests/"
                "testCompanionAppModelBeginLocalPairingWaitsForListenerReadiness|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing pairing starting-notice regression": (
            workflow.replace(
                "PairingRouteNoticeTests/"
                "testRuntimeStartingUsesNeutralReadinessNotice|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing reduced-motion policy regression": (
            workflow.replace(
                "AetherLinkLocalizationTests/"
                "testShortTransitionAnimationHonorsReducedMotion|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing reduced-motion render regression": (
            workflow.replace(
                "|AetherLinkRenderSmokeTests/"
                "testReducedMotionStatusAndActivePairingSurfacesRender",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing visual-preference precedence regression": (
            workflow.replace(
                "AetherLinkLocalizationTests/"
                "testVisualAccessibilityOverridesCannotDisableSystemPreferences|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing increased-contrast palette regression": (
            workflow.replace(
                "AetherLinkLocalizationTests/"
                "testIncreasedContrastStatusPaletteAndSurfacesRemainLegible|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing color-independent history regression": (
            workflow.replace(
                "AetherLinkLocalizationTests/"
                "testRuntimeHistorySelectionUsesNonColorMarkerAndReconcilesKeyboardList|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing recovery focus regression": (
            workflow.replace(
                "AetherLinkLocalizationTests/"
                "testConnectionRecoveryExpansionTargetsFirstEditableField|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing pairing focus regression": (
            workflow.replace(
                "AetherLinkLocalizationTests/"
                "testPairingDestinationFocusPlanSeparatesKeyboardAndVoiceOverTargets|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing increased-contrast reasoning regression": (
            workflow.replace(
                "AetherLinkLocalizationTests/"
                "testRuntimeTranscriptReasoningUsesFullOpacityAtIncreasedContrast|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing QR expiry announcement regression": (
            workflow.replace(
                "AccessibilityAnnouncementTests/"
                "testPairingQRExpiryAnnouncementFiresOnceWithoutCountdownSpam|",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing increased-contrast render regression": (
            workflow.replace(
                "|AetherLinkRenderSmokeTests/"
                "testIncreasedContrastAndColorIndependentHistorySurfacesRender",
                "",
                1,
            ),
            "exact command body",
        ),
        "missing product copy command": (
            workflow.replace(
                "          python3 -B script/check_copy_hygiene.py --product-copy-only\n",
                "",
                1,
            ),
            "one exact non-security product copy command",
        ),
        "Swift skip option": (
            workflow.replace(
                "          --swift-focused-filter\n",
                "          --skip '.*'\n"
                "          --swift-focused-filter\n",
                1,
            ),
            "exact command body",
        ),
        "missing Swift focused binding writer": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--write-swift-focused-test-binding\n",
                "",
                1,
            ),
            "result step must match the exact command body",
        ),
        "missing Swift focused independent readback": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--swift-focused-test-results\n",
                "",
                1,
            ),
            "result step must match the exact command body",
        ),
        "reversed Swift focused binding and readback": (
            workflow.replace(
                (
                    "          python3 -B script/check_product_ci.py "
                    "--write-swift-focused-test-binding\n"
                    "          python3 -B script/check_product_ci.py "
                    "--swift-focused-test-results\n"
                ),
                (
                    "          python3 -B script/check_product_ci.py "
                    "--swift-focused-test-results\n"
                    "          python3 -B script/check_product_ci.py "
                    "--write-swift-focused-test-binding\n"
                ),
                1,
            ),
            "result step must match the exact command body",
        ),
        "missing Android complete preparation step": (
            workflow.replace(
                "      - name: Prepare complete Android app units on main\n"
                f"{ANDROID_MAIN_FULL_PREPARE_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing Android core non-security preparation step": (
            workflow.replace(
                "      - name: Prepare Android core non-security units on main\n"
                f"{ANDROID_CORE_NONSECURITY_PREPARE_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "Android core non-security runner bypass": (
            workflow.replace(
                "          --run-android-core-nonsecurity-tests\n",
                "          --android-core-nonsecurity-test-results\n",
                1,
            ),
            "Run Android core non-security units on main step must match the "
            "exact main-only command body",
        ),
        "missing Android core non-security independent readback": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--android-core-nonsecurity-test-results\n",
                "",
                1,
            ),
            "Bind and verify Android core non-security units on main step "
            "must match the exact main-only command body",
        ),
        "missing Android Release diagnostics producer": (
            workflow.replace(
                "      - name: Run Android Release diagnostics on main\n"
                f"{ANDROID_RELEASE_DIAGNOSTICS_RUN_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing Android Release diagnostics readback": (
            workflow.replace(
                "      - name: Read back Android Release diagnostics on main\n"
                f"{ANDROID_RELEASE_DIAGNOSTICS_READBACK_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "Android diagnostics condition removed": (
            workflow.replace(
                "      - name: Run Android Release diagnostics on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Run Android Release diagnostics on main\n",
                1,
            ),
            "producer must match the exact main-only command body",
        ),
        "missing Android complete rerun requirement": (
            workflow.replace(
                "          --rerun-tasks\n",
                "",
                1,
            ),
            "complete test step must match the exact main-only command body",
        ),
        "missing Android complete selector": (
            workflow.replace(
                f"          --tests {ANDROID_MAIN_FULL_TESTS[0]}\n",
                "",
                1,
            ),
            "exact allowlists",
        ),
        "missing Android complete binding writer": (
            workflow.replace(
                "          python3 -B script/check_product_ci.py "
                "--write-android-full-test-binding\n",
                "",
                1,
            ),
            "complete result step must match the exact main-only command body",
        ),
        "missing Android test selector": (
            workflow.replace(
                f"          --tests {ANDROID_TESTS[0]}\n",
                "",
                1,
            ),
            "exact allowlist",
        ),
        "missing Android font-scale qualification regression": (
            workflow.replace(
                f"          --tests {ANDROID_FONT_SCALE_CLASS_NAME}\n",
                "",
                1,
            ),
            "exact allowlist",
        ),
        "missing Android app-language platform lifecycle regression": (
            workflow.replace(
                f"          --tests {ANDROID_APP_LANGUAGE_LIFECYCLE_CLASS_NAME}\n",
                "",
                1,
            ),
            "exact allowlist",
        ),
        "missing Android session-boundary regression": (
            workflow.replace(
                f"          --tests {ANDROID_TESTS[-1]}\n",
                "",
                1,
            ),
            "exact allowlist",
        ),
        "missing Android camera permission controller regressions": (
            workflow.replace(
                f"          --tests {ANDROID_TESTS[-3]}\n",
                "",
                1,
            ),
            "exact allowlist",
        ),
        "missing Android Activity recreation regression": (
            workflow.replace(
                f"          --tests {ANDROID_TESTS[-2]}\n",
                "",
                1,
            ),
            "exact allowlist",
        ),
        "missing Android test result verification": (
            workflow.replace(
                "      - name: Verify focused Android test results\n"
                f"{ANDROID_TEST_RESULT_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "extra Android test selector": (
            workflow.replace(
                f"          --tests {ANDROID_TESTS[-1]}\n",
                f"          --tests {ANDROID_TESTS[-1]}\n"
                "          --tests com.localagentbridge.android.ExtraProductTest\n",
                1,
            ),
            "exact allowlist",
        ),
        "wildcard Android test selector": (
            workflow.replace(
                f"          --tests {ANDROID_TESTS[0]}\n",
                '          --tests "*"\n',
                1,
            ),
            "wildcard Android test selector",
        ),
        "broad Android lifecycle task": (
            workflow.replace(
                "          :app:compileDebugKotlin\n",
                "          test\n          :app:compileDebugKotlin\n",
                1,
            ),
            "broad Gradle lifecycle task",
        ),
        "same-line broad Android lifecycle task": (
            workflow.replace(
                "          ./gradlew\n",
                "          ./gradlew test\n",
                1,
            ),
            "exact command body",
        ),
        "extra unfiltered Android step": (
            workflow.replace(
                "      - name: Compile and lint Android Release app on pull request\n",
                "      - name: Run unfiltered Android units\n"
                "        run: ./gradlew :app:testDebugUnitTest\n"
                "      - name: Compile and lint Android Release app on pull request\n",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "anonymous unfiltered Android step": (
            workflow.replace(
                "    timeout-minutes: 60\n"
                "    steps:\n",
                "    timeout-minutes: 60\n"
                "    steps:\n"
                "      - run: ./gradlew :app:testDebugUnitTest\n",
                1,
            ),
            "parsed job 'android-product-quality' steps must match "
            "exact names and order",
        ),
        "quoted flow-style extra job": (
            workflow.replace(
                "jobs:\n",
                "jobs:\n"
                '  "_extra": {name: Extra product job, '
                "runs-on: ubuntu-24.04, "
                'steps: [{run: "./gradlew :app:testDebugUnitTest"}]}\n',
                1,
            ),
            "parsed workflow jobs must be exactly",
        ),
        "quoted flow-style duplicate job": (
            workflow.replace(
                "jobs:\n",
                "jobs:\n"
                '  "macos-product-quality": {name: Decoy, '
                "runs-on: macos-15, steps: []}\n",
                1,
            ),
            "duplicate mapping key",
        ),
        "tagged duplicate job": (
            workflow.replace(
                "jobs:\n",
                "jobs:\n"
                "  !!binary bWFjb3MtcHJvZHVjdC1xdWFsaXR5: "
                "{name: Decoy, runs-on: macos-15, steps: []}\n",
                1,
            ),
            "explicitly tagged mapping key",
        ),
        "second YAML document": (
            workflow
            + "---\n"
            + "name: Unrelated workflow document\n",
            "workflow must contain exactly one YAML document",
        ),
        "excluded Android test task": (
            workflow.replace(
                "          --no-daemon\n",
                "          -x :app:testDebugUnitTest\n"
                "          --no-daemon\n",
                1,
            ),
            "must not skip or dry-run tasks",
        ),
        "Android dry run": (
            workflow.replace(
                "          --no-daemon\n",
                "          --dry-run\n"
                "          --no-daemon\n",
                1,
            ),
            "must not skip or dry-run tasks",
        ),
        "strict debug locks": (
            workflow.replace(
                "          :app:compileDebugKotlin\n",
                "          -PaetherlinkStrictReleaseDependencyLocks=true\n"
                "          :app:compileDebugKotlin\n",
                1,
            ),
            "debug compilation/tests must not use strict locks",
        ),
        "Android instrumentation task": (
            workflow.replace(
                "          :app:compileDebugKotlin\n",
                "          :app:connectedDebugAndroidTest\n"
                "          :app:compileDebugKotlin\n",
                1,
            ),
            "Android instrumentation task",
        ),
        "Android install task": (
            workflow.replace(
                "          :app:compileDebugKotlin\n",
                "          :app:installDebug\n"
                "          :app:compileDebugKotlin\n",
                1,
            ),
            "Android install task",
        ),
        "Android signing report": (
            workflow.replace(
                "          :app:assembleRelease\n",
                "          :app:signingReport\n"
                "          :app:assembleRelease\n",
                1,
            ),
            "Android signing report",
        ),
        "missing Android bundle task": (
            workflow.replace(
                "          :app:bundleRelease\n",
                "",
                1,
            ),
            "Android Release pull-request step must match the exact",
        ),
        "duplicate Android bundle task": (
            workflow.replace(
                "          :app:bundleRelease\n",
                "          :app:bundleRelease\n"
                "          :app:bundleRelease\n",
                1,
            ),
            "Android Release pull-request step must match the exact",
        ),
        "reordered Android bundle task": (
            workflow.replace(
                "          :app:assembleRelease\n"
                "          :app:bundleRelease\n",
                "          :app:bundleRelease\n"
                "          :app:assembleRelease\n",
                1,
            ),
            "Android Release pull-request step must match the exact",
        ),
        "missing Android Release repeatability unit step": (
            workflow.replace(
                "      - name: Run Android Release repeatability contract units\n"
                f"{ANDROID_RELEASE_REPEATABILITY_CONTRACT_TEST_STEP_BODY}",
                "",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing Android Release repeatability producer": (
            workflow.replace(
                "      - name: Run Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY}",
                "",
                1,
            ),
            "invoke each Android Release repeatability",
        ),
        "missing Android Release repeatability checker": (
            workflow.replace(
                "      - name: Read back Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY}",
                "",
                1,
            ),
            "invoke each Android Release repeatability",
        ),
        "Android Release repeatability producer condition removed": (
            workflow.replace(
                "      - name: Run Android Release A/B repeatability on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Run Android Release A/B repeatability on main\n",
                1,
            ),
            "producer must match the exact main-only command body",
        ),
        "Android Release repeatability checker condition removed": (
            workflow.replace(
                "      - name: Read back Android Release A/B repeatability on main\n"
                "        if: >-\n"
                f"          {MAIN_RELEASE_CONDITION}\n",
                "      - name: Read back Android Release A/B repeatability on main\n",
                1,
            ),
            "checker must match the exact main-only command body",
        ),
        "Android Release pull-request condition removed": (
            workflow.replace(
                "      - name: Compile and lint Android Release app on pull request\n"
                f"        if: {PULL_REQUEST_CONDITION}\n",
                "      - name: Compile and lint Android Release app on pull request\n",
                1,
            ),
            "pull-request step must match the exact condition",
        ),
        "suppressed Android Release repeatability failure": (
            workflow.replace(
                "      - name: Run Android Release A/B repeatability on main\n",
                "      - name: Run Android Release A/B repeatability on main\n"
                "        continue-on-error: true\n",
                1,
            ),
            "ignored failure",
        ),
        "Android Release repeatability checker before producer": (
            workflow.replace(
                "      - name: Run Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY}"
                "      - name: Read back Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY}",
                "      - name: Read back Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY}"
                "      - name: Run Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY}",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "missing Android Release readback step": (
            workflow.replace(
                "      - name: Read back Android Release build outputs\n"
                f"{ANDROID_RELEASE_READBACK_STEP_BODY}",
                "",
                1,
            ),
            "one exact Android and one exact macOS Release readback command",
        ),
        "wrong Android Release readback mode": (
            workflow.replace(
                "          --android-build-outputs\n",
                "          --historical\n",
                1,
            ),
            "one exact Android and one exact macOS Release readback command",
        ),
        "Android Release readback before build": (
            workflow.replace(
                "      - name: Compile and lint Android Release app on pull request\n"
                f"{ANDROID_RELEASE_STEP_BODY}"
                "      - name: Run Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY}"
                "      - name: Read back Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY}"
                "      - name: Read back Android Release build outputs\n"
                f"{ANDROID_RELEASE_READBACK_STEP_BODY}",
                "      - name: Read back Android Release build outputs\n"
                f"{ANDROID_RELEASE_READBACK_STEP_BODY}"
                "      - name: Compile and lint Android Release app on pull request\n"
                f"{ANDROID_RELEASE_STEP_BODY}"
                "      - name: Run Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_RUN_STEP_BODY}"
                "      - name: Read back Android Release A/B repeatability on main\n"
                f"{ANDROID_RELEASE_REPEATABILITY_READBACK_STEP_BODY}",
                1,
            ),
            "steps must match the exact names and order",
        ),
        "suppressed Android Release readback failure": (
            workflow.replace(
                "      - name: Read back Android Release build outputs\n",
                "      - name: Read back Android Release build outputs\n"
                "        continue-on-error: true\n",
                1,
            ),
            "ignored failure",
        ),
        "live backend enablement": (
            workflow.replace(
                "    timeout-minutes: 120\n",
                "    timeout-minutes: 120\n"
                "    env:\n"
                '      OLLAMA_LIVE_TESTS: "1"\n',
                1,
            ),
            "explicit live-test enablement",
        ),
        "direct network command": (
            workflow.replace(
                "          python3 --version\n",
                "          curl https://example.invalid\n"
                "          python3 --version\n",
                1,
            ),
            "direct network command",
        ),
        "mixed aggregate gate": (
            workflow + "\n# ./script/check_no_device_quality.sh\n",
            "mixed aggregate gate",
        ),
        "cold-runner offline mode": (
            workflow.replace(
                "          --no-daemon\n",
                "          --offline\n          --no-daemon\n",
                1,
            ),
            "cold-runner offline mode",
        ),
        "ignored failure expression": (
            workflow.replace(
                "      - name: Compile macOS app\n",
                "      - name: Compile macOS app\n"
                "        continue-on-error: ${{ always() }}\n",
                1,
            ),
            "ignored failure",
        ),
        "wrong Java version": (
            workflow.replace(
                'java-version: "21"',
                'java-version: "17"',
                1,
            ),
            'java-version: "21"',
        ),
        "main tier overclaim": (
            workflow.replace(
                "Android product quality subset",
                "Android main-full",
                1,
            ),
            "canonical tier overclaim",
        ),
    }

    for label, (mutated, expected_failure) in mutations.items():
        if mutated == workflow:
            failures.append(f"self-test mutation did not apply: {label}")
            continue
        semantic_failures = workflow_failures(
            mutated,
            check_canonical_bytes=False,
        )
        if not any(
            expected_failure in failure for failure in semantic_failures
        ):
            failures.append(
                "self-test semantic mutation was not rejected as expected: "
                f"{label} ({expected_failure!r})"
            )

    return failures


def swift_test_selection_manifest_sha256(
    test_names: tuple[str, ...],
) -> str:
    payload = json.dumps(
        sorted(test_names),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def swift_selected_test_names(
    *,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    excluded_tests: tuple[str, ...] = (),
) -> tuple[tuple[str, ...] | None, bytes | None, list[str]]:
    try:
        test_list_bytes = test_list_path.read_bytes()
        test_list = test_list_bytes.decode("utf-8")
    except (OSError, UnicodeError) as error:
        return None, None, [
            f"{path_label(test_list_path)} cannot be read: {error}"
        ]

    failures: list[str] = []
    if b"\r" in test_list_bytes:
        failures.append("Swift test list must use LF line endings")
    if not test_list_bytes.endswith(b"\n"):
        failures.append("Swift test list must end with LF")

    test_names = tuple(test_list.splitlines())
    if not test_names:
        failures.append("Swift test list must not be empty")
        return None, test_list_bytes, failures
    malformed = tuple(
        test_name
        for test_name in test_names
        if (
            not test_name
            or test_name != test_name.strip()
            or re.fullmatch(r"[^\s/]+/[^\s/]+", test_name) is None
        )
    )
    if malformed:
        failures.append(
            "Swift test list must contain only canonical test specifiers"
        )
    if len(set(test_names)) != len(test_names):
        failures.append("Swift test list must not contain duplicate specifiers")

    if len(set(excluded_tests)) != len(excluded_tests):
        failures.append("Swift excluded tests must not contain duplicates")
    malformed_exclusions = tuple(
        test_name
        for test_name in excluded_tests
        if (
            not test_name
            or test_name != test_name.strip()
            or re.fullmatch(r"[^\s/]+/[^\s/]+", test_name) is None
        )
    )
    if malformed_exclusions:
        failures.append(
            "Swift excluded tests must contain only canonical specifiers"
        )

    try:
        included_tests = tuple(
            test_name
            for test_name in test_names
            if re.search(filter_pattern, test_name)
        )
    except re.error as error:
        failures.append(f"Swift product test filter is invalid: {error}")
        return None, test_list_bytes, failures
    included_set = set(included_tests)
    excluded_set = set(excluded_tests)
    missing_exclusions = tuple(
        sorted(excluded_set - set(test_names))
    )
    if missing_exclusions:
        failures.append(
            "Swift excluded tests must all exist in the discovered test list"
        )
    outside_filter = tuple(sorted(excluded_set - included_set))
    if outside_filter:
        failures.append(
            "Swift excluded tests must all match the include filter"
        )
    selected_tests = tuple(
        test_name
        for test_name in included_tests
        if test_name not in excluded_set
    )
    if failures:
        return None, test_list_bytes, failures
    return selected_tests, test_list_bytes, []


def swift_test_selection_failures(
    *,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
) -> list[str]:
    selected_tests, _, failures = swift_selected_test_names(
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        excluded_tests=excluded_tests,
    )
    if selected_tests is None:
        return failures
    if len(selected_tests) != expected_count:
        failures.append(
            "Swift product test selection must match exactly "
            f"{expected_count} tests, found {len(selected_tests)}"
        )
    actual_manifest_sha256 = swift_test_selection_manifest_sha256(
        selected_tests
    )
    if actual_manifest_sha256 != expected_manifest_sha256:
        failures.append(
            "Swift product test selection manifest SHA-256 must match the "
            "exact contract"
        )
    return failures


def g7_nonsecurity_swift_selection_failures(
    *,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
) -> list[str]:
    contracts = (
        (
            "focused",
            SWIFT_FILTER,
            SWIFT_PRODUCT_TEST_COUNT,
            SWIFT_PRODUCT_TEST_MANIFEST_SHA256,
            (),
        ),
        (
            "UI",
            G7_NONSECURITY_SWIFT_UI_FILTER,
            G7_NONSECURITY_SWIFT_UI_TEST_COUNT,
            G7_NONSECURITY_SWIFT_UI_TEST_MANIFEST_SHA256,
            (),
        ),
        (
            "module universe",
            G7_NONSECURITY_SWIFT_MODULE_FILTER,
            G7_NONSECURITY_SWIFT_MODULE_TEST_COUNT,
            G7_NONSECURITY_SWIFT_MODULE_TEST_MANIFEST_SHA256,
            (),
        ),
        (
            "safe module",
            G7_NONSECURITY_SWIFT_SAFE_MODULE_FILTER,
            G7_NONSECURITY_SWIFT_SAFE_MODULE_TEST_COUNT,
            G7_NONSECURITY_SWIFT_SAFE_MODULE_TEST_MANIFEST_SHA256,
            (),
        ),
        (
            "combined",
            G7_NONSECURITY_SWIFT_FILTER,
            G7_NONSECURITY_SWIFT_TEST_COUNT,
            G7_NONSECURITY_SWIFT_TEST_MANIFEST_SHA256,
            G7_NONSECURITY_SWIFT_LIVE_TESTS,
        ),
    )
    failures: list[str] = []
    observed: dict[str, set[str]] = {}
    for label, filter_pattern, count, manifest, excluded_tests in contracts:
        contract_failures = swift_test_selection_failures(
            test_list_path=test_list_path,
            filter_pattern=filter_pattern,
            expected_count=count,
            expected_manifest_sha256=manifest,
            excluded_tests=excluded_tests,
        )
        failures.extend(
            f"G7 non-security Swift {label}: {failure}"
            for failure in contract_failures
        )
        selected, _, selection_failures = swift_selected_test_names(
            test_list_path=test_list_path,
            filter_pattern=filter_pattern,
            excluded_tests=excluded_tests,
        )
        failures.extend(
            f"G7 non-security Swift {label}: {failure}"
            for failure in selection_failures
        )
        if selected is not None:
            observed[label] = set(selected)

    if len(G7_NONSECURITY_SWIFT_LIVE_TESTS) != (
        G7_NONSECURITY_SWIFT_LIVE_TEST_COUNT
    ):
        failures.append(
            "G7 non-security Swift live exclusion count differs"
        )
    if swift_test_selection_manifest_sha256(
        G7_NONSECURITY_SWIFT_LIVE_TESTS
    ) != G7_NONSECURITY_SWIFT_LIVE_TEST_MANIFEST_SHA256:
        failures.append(
            "G7 non-security Swift live exclusion manifest differs"
        )

    if set(contracts[index][0] for index in range(len(contracts))) <= set(
        observed
    ):
        focused_tests = observed["focused"]
        ui_tests = observed["UI"]
        module_tests = observed["module universe"]
        safe_tests = observed["safe module"]
        combined_tests = observed["combined"]
        live_tests = module_tests - safe_tests
        expected_live_tests = set(G7_NONSECURITY_SWIFT_LIVE_TESTS)
        if safe_tests & live_tests:
            failures.append(
                "G7 non-security Swift safe/live partitions overlap"
            )
        if safe_tests | live_tests != module_tests:
            failures.append(
                "G7 non-security Swift module partition is incomplete"
            )
        if live_tests != expected_live_tests:
            failures.append(
                "G7 non-security Swift live exclusion identities differ"
            )
        if len(live_tests) != G7_NONSECURITY_SWIFT_LIVE_TEST_COUNT:
            failures.append(
                "G7 non-security Swift live exclusion census differs"
            )
        elif swift_test_selection_manifest_sha256(
            tuple(live_tests)
        ) != G7_NONSECURITY_SWIFT_LIVE_TEST_MANIFEST_SHA256:
            failures.append(
                "G7 non-security Swift observed live manifest differs"
            )
        if ui_tests & safe_tests:
            failures.append(
                "G7 non-security Swift UI/safe partitions overlap"
            )
        if combined_tests != ui_tests | safe_tests:
            failures.append(
                "G7 non-security Swift combined partition differs"
            )
        if combined_tests & expected_live_tests:
            failures.append(
                "G7 non-security Swift combined selection includes live tests"
            )
        if len(focused_tests & combined_tests) != (
            G7_NONSECURITY_SWIFT_FOCUSED_OVERLAP_COUNT
        ):
            failures.append(
                "G7 non-security Swift focused overlap differs"
            )
        if len(focused_tests | combined_tests) != (
            G7_NONSECURITY_SWIFT_DISTINCT_TEST_COUNT
        ):
            failures.append(
                "G7 non-security Swift distinct identity count differs"
            )
        for prefix, expected_count in (
            G7_NONSECURITY_SWIFT_SAFE_TARGET_COUNTS.items()
        ):
            observed_count = sum(
                identity.startswith(prefix) for identity in safe_tests
            )
            if observed_count != expected_count:
                failures.append(
                    "G7 non-security Swift safe target breakdown differs: "
                    f"{prefix}"
                )
    return failures


def g7_nonsecurity_swift_environment(
    source_environment: dict[str, str] | None = None,
) -> tuple[dict[str, str] | None, list[str]]:
    source = os.environ if source_environment is None else source_environment
    if type(source) is not dict and source_environment is not None:
        return None, [
            "G7 non-security Swift parent environment must be a mapping"
        ]
    forbidden_keys = tuple(
        sorted(
            key
            for key in source
            if (
                key.upper().startswith("AETHERLINK_")
                or key.upper().startswith("OLLAMA_")
                or key.upper().startswith("LMSTUDIO_")
                or key.upper().startswith("LM_STUDIO_")
                or key.upper().endswith("_PROXY")
                or key.upper()
                in {"ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}
            )
        )
    )
    if forbidden_keys:
        return None, [
            "G7 non-security Swift parent environment contains forbidden "
            "live/provider/proxy keys: " + ", ".join(forbidden_keys)
        ]
    child: dict[str, str] = {}
    for key in G7_NONSECURITY_SWIFT_ALLOWED_ENVIRONMENT_KEYS:
        value = source.get(key)
        if value is not None:
            if type(value) is not str or "\x00" in value:
                return None, [
                    "G7 non-security Swift allowed environment value is "
                    f"invalid: {key}"
                ]
            child[key] = value
    child["LC_ALL"] = "C"
    child["LANG"] = "C"
    return child, []


def swift_test_selection_self_test() -> list[str]:
    failures: list[str] = []
    fixture_filter = r"FixtureSuite/"
    fixture_names = (
        "FixtureTests.FixtureSuite/testOne",
        "FixtureTests.FixtureSuite/testTwo",
        "FixtureTests.UnselectedSuite/testThree",
    )
    fixture_manifest = swift_test_selection_manifest_sha256(
        fixture_names[:2]
    )
    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-swift-selection-",
        ) as temporary:
            fixture_path = Path(temporary) / "tests.txt"

            def fixture_failures(text: str) -> list[str]:
                fixture_path.write_bytes(text.encode("utf-8"))
                return swift_test_selection_failures(
                    test_list_path=fixture_path,
                    filter_pattern=fixture_filter,
                    expected_count=2,
                    expected_manifest_sha256=fixture_manifest,
                )

            valid_text = "\n".join(fixture_names) + "\n"
            valid_failures = fixture_failures(valid_text)
            if valid_failures:
                failures.append(
                    "valid Swift selection fixture was rejected: "
                    + "; ".join(valid_failures)
                )

            missing_failures = fixture_failures(
                valid_text.replace(
                    "FixtureTests.FixtureSuite/testTwo\n",
                    "",
                    1,
                )
            )
            if not any(
                "must match exactly 2 tests" in failure
                for failure in missing_failures
            ):
                failures.append(
                    "missing Swift selected test was not rejected"
                )

            substitution_failures = fixture_failures(
                valid_text.replace("testTwo", "sameCountSubstitution", 1)
            )
            if not any(
                "selection manifest SHA-256 must match" in failure
                for failure in substitution_failures
            ):
                failures.append(
                    "same-count Swift selected test substitution was not "
                    "rejected"
                )

            duplicate_failures = fixture_failures(
                fixture_names[0] + "\n" + valid_text
            )
            if not any(
                "duplicate specifiers" in failure
                for failure in duplicate_failures
            ):
                failures.append("duplicate Swift test was not rejected")

            malformed_failures = fixture_failures(
                valid_text + "[0/1] Planning build\n"
            )
            if not any(
                "canonical test specifiers" in failure
                for failure in malformed_failures
            ):
                failures.append("malformed Swift test list was not rejected")

            missing_lf_failures = fixture_failures(
                valid_text.removesuffix("\n")
            )
            if not any(
                "must end with LF" in failure
                for failure in missing_lf_failures
            ):
                failures.append(
                    "Swift test list without final LF was not rejected"
                )

            excluded = (fixture_names[1],)
            excluded_manifest = swift_test_selection_manifest_sha256(
                fixture_names[:1]
            )

            def excluded_fixture_failures(
                excluded_tests: tuple[str, ...],
            ) -> list[str]:
                fixture_path.write_text(valid_text, encoding="utf-8")
                return swift_test_selection_failures(
                    test_list_path=fixture_path,
                    filter_pattern=fixture_filter,
                    expected_count=1,
                    expected_manifest_sha256=excluded_manifest,
                    excluded_tests=excluded_tests,
                )

            valid_excluded_failures = excluded_fixture_failures(excluded)
            if valid_excluded_failures:
                failures.append(
                    "valid Swift exact exclusion fixture was rejected: "
                    + "; ".join(valid_excluded_failures)
                )
            missing_exclusion_failures = excluded_fixture_failures(
                ("FixtureTests.FixtureSuite/testMissing",)
            )
            if not any(
                "must all exist" in failure
                for failure in missing_exclusion_failures
            ):
                failures.append(
                    "missing Swift exact exclusion was not rejected"
                )
            outside_filter_failures = excluded_fixture_failures(
                (fixture_names[2],)
            )
            if not any(
                "must all match the include filter" in failure
                for failure in outside_filter_failures
            ):
                failures.append(
                    "out-of-filter Swift exact exclusion was not rejected"
                )
            duplicate_exclusion_failures = excluded_fixture_failures(
                (fixture_names[1], fixture_names[1])
            )
            if not any(
                "excluded tests must not contain duplicates" in failure
                for failure in duplicate_exclusion_failures
            ):
                failures.append(
                    "duplicate Swift exact exclusion was not rejected"
                )
    except OSError as error:
        failures.append(f"Swift selection fixture failed: {error}")
    return failures


def g7_nonsecurity_swift_contract_self_test() -> list[str]:
    failures: list[str] = []
    expected_skip_filter = (
        "^(?:"
        + "|".join(
            re.escape(identity)
            for identity in G7_NONSECURITY_SWIFT_LIVE_TESTS
        )
        + ")$"
    )
    if G7_NONSECURITY_SWIFT_SKIP_FILTER != expected_skip_filter:
        failures.append("G7 non-security Swift exact skip filter differs")
    if len(G7_NONSECURITY_SWIFT_LIVE_TESTS) != 11:
        failures.append("G7 non-security Swift live identity census differs")
    if swift_test_selection_manifest_sha256(
        G7_NONSECURITY_SWIFT_LIVE_TESTS
    ) != G7_NONSECURITY_SWIFT_LIVE_TEST_MANIFEST_SHA256:
        failures.append("G7 non-security Swift live manifest differs")
    if sum(G7_NONSECURITY_SWIFT_SAFE_TARGET_COUNTS.values()) != (
        G7_NONSECURITY_SWIFT_SAFE_MODULE_TEST_COUNT
    ):
        failures.append("G7 non-security Swift safe target census differs")
    if (
        SWIFT_PRODUCT_TEST_COUNT
        + G7_NONSECURITY_SWIFT_TEST_COUNT
        - G7_NONSECURITY_SWIFT_FOCUSED_OVERLAP_COUNT
        != G7_NONSECURITY_SWIFT_DISTINCT_TEST_COUNT
    ):
        failures.append("G7 non-security Swift distinct count arithmetic differs")
    for identity in G7_NONSECURITY_SWIFT_LIVE_TESTS:
        if re.fullmatch(G7_NONSECURITY_SWIFT_SKIP_FILTER, identity) is None:
            failures.append(
                "G7 non-security Swift skip filter omitted a live identity"
            )
            break
        if re.search(G7_NONSECURITY_SWIFT_FILTER, identity) is None:
            failures.append(
                "G7 non-security Swift include filter omitted a live identity"
            )
            break
    safe_fixture = (
        "OllamaBackendTests.OllamaBackendTests/testInjectedCatalogResponse"
    )
    if re.fullmatch(G7_NONSECURITY_SWIFT_SKIP_FILTER, safe_fixture) is not None:
        failures.append(
            "G7 non-security Swift skip filter matched a safe identity"
        )
    expected_command = (
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1)(allow default)(deny network*)",
        "/usr/bin/swift",
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
        G7_NONSECURITY_SWIFT_FILTER,
        "--skip",
        G7_NONSECURITY_SWIFT_SKIP_FILTER,
    )
    if G7_NONSECURITY_SWIFT_RUN_COMMAND != expected_command:
        failures.append("G7 non-security Swift fixed command differs")

    expected_allowed_keys = (
        "DEVELOPER_DIR",
        "HOME",
        "PATH",
        "SDKROOT",
        "TMPDIR",
        "TOOLCHAINS",
    )
    if G7_NONSECURITY_SWIFT_ALLOWED_ENVIRONMENT_KEYS != expected_allowed_keys:
        failures.append(
            "G7 non-security Swift allowed environment keys differ"
        )
    valid_parent = {
        key: f"fixture-{key.lower()}"
        for key in expected_allowed_keys
    }
    valid_parent.update(
        {
            "LANG": "fixture-parent-lang",
            "LC_ALL": "fixture-parent-locale",
            "UNRELATED": "not-forwarded",
        }
    )
    child, environment_failures = g7_nonsecurity_swift_environment(
        valid_parent
    )
    if environment_failures or child is None:
        failures.append(
            "valid G7 non-security Swift environment fixture was rejected"
        )
    elif child != {
        **{
            key: f"fixture-{key.lower()}"
            for key in expected_allowed_keys
        },
        "LC_ALL": "C",
        "LANG": "C",
    }:
        failures.append(
            "G7 non-security Swift child environment is not exact"
        )
    for forbidden_key in (
        "AETHERLINK_LIVE_TEST",
        "aetherlink_live_test",
        "OLLAMA_HOST",
        "ollama_host",
        "LMSTUDIO_BASE_URL",
        "lmstudio_base_url",
        "LM_STUDIO_BASE_URL",
        "lm_studio_base_url",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
        "CUSTOM_PROXY",
        "custom_proxy",
    ):
        _, forbidden_failures = g7_nonsecurity_swift_environment(
            {**valid_parent, forbidden_key: "fixture"}
        )
        if not forbidden_failures:
            failures.append(
                "G7 non-security Swift forbidden environment key was not "
                f"rejected: {forbidden_key}"
            )
    return failures


def g7_nonsecurity_swift_network_sandbox_self_test() -> list[str]:
    environment, environment_failures = g7_nonsecurity_swift_environment(
        {
            "HOME": str(ROOT),
            "PATH": "/usr/bin:/bin",
            "TMPDIR": tempfile.gettempdir(),
        }
    )
    if environment_failures or environment is None:
        return [
            "G7 non-security Swift network probe environment was rejected: "
            + "; ".join(environment_failures)
        ]
    try:
        completed = subprocess.run(
            G7_NONSECURITY_SWIFT_NETWORK_PROBE_COMMAND,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [
            "G7 non-security Swift IPv4/IPv6 network-deny probe failed: "
            f"{error}"
        ]
    if completed.returncode != 0:
        return [
            "G7 non-security Swift IPv4/IPv6 network-deny probe exited "
            f"with status {completed.returncode}"
        ]
    return []


def android_testcase_manifest_sha256(
    testcases: list[tuple[str, str]],
) -> str:
    payload = json.dumps(
        sorted(testcases),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def android_core_nonsecurity_selection_failures() -> list[str]:
    failures: list[str] = []
    selections = (
        (
            "protocol",
            ANDROID_CORE_NONSECURITY_PROTOCOL_SELECTIONS,
            ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_COUNT,
            ANDROID_CORE_NONSECURITY_PROTOCOL_TEST_CASE_MANIFEST_SHA256,
            ANDROID_CORE_NONSECURITY_PROTOCOL_RUN_COMMAND,
            ":core:protocol:testDebugUnitTest",
        ),
        (
            "transport",
            ANDROID_CORE_NONSECURITY_TRANSPORT_SELECTIONS,
            ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_COUNT,
            ANDROID_CORE_NONSECURITY_TRANSPORT_TEST_CASE_MANIFEST_SHA256,
            ANDROID_CORE_NONSECURITY_TRANSPORT_RUN_COMMAND,
            ":core:transport:testDebugUnitTest",
        ),
    )
    observed_total = 0
    for (
        label,
        class_selections,
        expected_count,
        expected_manifest_sha256,
        command,
        gradle_task,
    ) in selections:
        selectors = tuple(
            f"{class_name}.{method}"
            for class_name, _source_path, methods in class_selections
            for method in methods
        )
        if (
            len(selectors) != expected_count
            or len(set(selectors)) != expected_count
        ):
            failures.append(
                f"Android core non-security {label} selectors must contain "
                f"exactly {expected_count} unique entries"
            )
        observed_total += len(selectors)
        for class_name, source_path, methods in class_selections:
            if not methods or len(methods) != len(set(methods)):
                failures.append(
                    f"Android core non-security {label} class methods must "
                    f"be nonempty and unique: {class_name}"
                )
                continue
            try:
                source = source_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                failures.append(
                    f"Android core non-security {label} source cannot be "
                    f"read for {class_name}: {error}"
                )
                continue
            declared_tests = set(
                re.findall(
                    r"(?m)^\s*@Test\s*\n\s*(?:suspend\s+)?"
                    r"fun\s+([A-Za-z0-9_]+)\s*\(",
                    source,
                )
            )
            missing = tuple(
                method for method in methods if method not in declared_tests
            )
            if missing:
                failures.append(
                    f"Android core non-security {label} selectors must name "
                    f"declared @Test methods in {class_name}: {missing!r}"
                )
        manifest_sha256 = android_testcase_manifest_sha256(
            [
                (class_name, method)
                for class_name, _source_path, methods in class_selections
                for method in methods
            ]
        )
        if manifest_sha256 != expected_manifest_sha256:
            failures.append(
                f"Android core non-security {label} testcase manifest "
                "must match its reviewed identity"
            )
        expected_command = (
            ANDROID_CORE_NONSECURITY_GRADLE_PREFIX
            + (gradle_task,)
            + tuple(
                argument
                for selector in selectors
                for argument in ("--tests", selector)
            )
        )
        if command != expected_command:
            failures.append(
                f"Android core non-security {label} runner command must "
                "match the exact offline method allowlist"
            )
    if (
        observed_total != ANDROID_CORE_NONSECURITY_TEST_COUNT
        or len(ANDROID_CORE_NONSECURITY_TESTS)
        != ANDROID_CORE_NONSECURITY_TEST_COUNT
        or len(set(ANDROID_CORE_NONSECURITY_TESTS))
        != ANDROID_CORE_NONSECURITY_TEST_COUNT
    ):
        failures.append(
            "Android core non-security combined allowlist must contain "
            f"exactly {ANDROID_CORE_NONSECURITY_TEST_COUNT} unique methods"
        )
    return failures


def terminate_android_core_nonsecurity_process(
    process: subprocess.Popen[bytes],
) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def run_android_core_nonsecurity_tests() -> list[str]:
    selection_failures = android_core_nonsecurity_selection_failures()
    if selection_failures:
        return selection_failures
    commands = (
        ("protocol", ANDROID_CORE_NONSECURITY_PROTOCOL_RUN_COMMAND),
        ("transport", ANDROID_CORE_NONSECURITY_TRANSPORT_RUN_COMMAND),
    )
    for label, command in commands:
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                status = process.wait(timeout=1200)
            except subprocess.TimeoutExpired:
                terminate_android_core_nonsecurity_process(process)
                return [
                    f"Android core non-security {label} runner timed out"
                ]
            except BaseException:
                terminate_android_core_nonsecurity_process(process)
                raise
        except OSError as error:
            return [
                f"Android core non-security {label} runner failed to start: "
                f"{error}"
            ]
        if status != 0:
            return [
                f"Android core non-security {label} runner exited with "
                f"status {status}"
            ]
    return []


def android_test_result_failures(
    expected_results: tuple[tuple[str, int, tuple[str, ...]], ...],
    *,
    result_root: Path | None = None,
    freshness_inputs: tuple[Path, ...] | None = None,
    allow_additional_methods: bool = False,
    require_exact_report_set: bool = False,
    expected_testcase_manifest_sha256: str | None = None,
) -> list[str]:
    failures: list[str] = []
    if result_root is None:
        result_root = ANDROID_FULL_TEST_RESULT_ROOT
    if freshness_inputs is None:
        freshness_inputs = android_result_freshness_inputs()
    expected_total = sum(count for _, count, _ in expected_results)
    observed_total = 0
    observed_testcases: list[tuple[str, str]] = []
    if require_exact_report_set:
        expected_report_names = tuple(
            sorted(
                f"TEST-{class_name}.xml"
                for class_name, _, _ in expected_results
            )
        )
        try:
            actual_report_names = tuple(
                sorted(
                    path.name
                    for path in result_root.iterdir()
                    if path.name.startswith("TEST-")
                    and path.name.endswith(".xml")
                )
            )
        except OSError as error:
            failures.append(
                f"{path_label(result_root)} report set cannot be read: "
                f"{error}"
            )
        else:
            if actual_report_names != expected_report_names:
                failures.append(
                    f"{path_label(result_root)} result report set must "
                    "match the exact result contract"
                )
    freshness_mtimes: list[tuple[str, int]] = []
    for input_path in freshness_inputs:
        try:
            input_mtime_ns = input_path.stat().st_mtime_ns
        except OSError as error:
            failures.append(
                "Android product result freshness input "
                f"{path_label(input_path)} cannot be read: {error}"
            )
            continue
        freshness_mtimes.append(
            (path_label(input_path), input_mtime_ns)
        )

    for class_name, expected_count, expected_methods in expected_results:
        report_path = result_root / f"TEST-{class_name}.xml"
        report_label = path_label(report_path)
        try:
            suite = ET.parse(report_path).getroot()
        except (OSError, ET.ParseError) as error:
            failures.append(
                f"{report_label} cannot be read: {error}"
            )
            continue

        try:
            report_mtime_ns = report_path.stat().st_mtime_ns
        except OSError as error:
            failures.append(
                f"{report_label} timestamp cannot be read: "
                f"{error}"
            )
        else:
            freshness_failure = android_result_staleness_failure(
                report_label=report_label,
                report_mtime_ns=report_mtime_ns,
                input_mtimes=tuple(freshness_mtimes),
            )
            if freshness_failure is not None:
                failures.append(freshness_failure)

        if suite.tag != "testsuite":
            failures.append(
                f"{report_label} root must be testsuite"
            )
            continue
        if suite.get("name") != class_name:
            failures.append(
                f"{report_label} suite name must be {class_name}"
            )

        counts: dict[str, int] = {}
        for attribute in ("tests", "skipped", "failures", "errors"):
            raw = suite.get(attribute)
            if raw is None or re.fullmatch(r"0|[1-9][0-9]*", raw) is None:
                failures.append(
                    f"{report_label} {attribute} must be "
                    "a canonical nonnegative integer"
                )
                continue
            counts[attribute] = int(raw)

        if counts.get("tests") != expected_count:
            failures.append(
                f"{report_label} must execute exactly "
                f"{expected_count} test(s)"
            )
        for attribute in ("skipped", "failures", "errors"):
            if counts.get(attribute) != 0:
                failures.append(
                    f"{report_label} {attribute} must be 0"
                )

        testcases = suite.findall("testcase")
        if len(testcases) != expected_count:
            failures.append(
                f"{report_label} must contain exactly "
                f"{expected_count} testcase element(s)"
            )
        actual_methods = tuple(
            testcase.get("name", "") for testcase in testcases
        )
        if any(not method for method in actual_methods):
            failures.append(
                f"{report_label} test method names must be nonempty"
            )
        if len(set(actual_methods)) != len(actual_methods):
            failures.append(
                f"{report_label} test method names must be unique"
            )
        if expected_methods:
            if allow_additional_methods:
                missing_methods = sorted(
                    set(expected_methods) - set(actual_methods)
                )
                if missing_methods:
                    failures.append(
                        f"{report_label} full-suite test methods must "
                        "include the required contract"
                    )
            elif sorted(actual_methods) != sorted(expected_methods):
                failures.append(
                    f"{report_label} selected test methods "
                    "must match the exact contract"
                )
        for testcase in testcases:
            testcase_class_name = testcase.get("classname")
            testcase_name = testcase.get("name", "")
            if testcase_class_name != class_name:
                failures.append(
                    f"{report_label} testcase classname "
                    f"must be {class_name}"
                )
            observed_testcases.append(
                (testcase_class_name or "", testcase_name)
            )
            if any(
                testcase.find(outcome) is not None
                for outcome in ("skipped", "failure", "error")
            ):
                failures.append(
                    f"{report_label} testcase outcomes "
                    "must contain no skipped, failure, or error element"
                )
        observed_total += counts.get("tests", 0)

    if observed_total != expected_total:
        failures.append(
            f"Android product result total must be {expected_total}, "
            f"found {observed_total}"
        )
    if expected_testcase_manifest_sha256 is not None:
        actual_manifest_sha256 = android_testcase_manifest_sha256(
            observed_testcases
        )
        if actual_manifest_sha256 != expected_testcase_manifest_sha256:
            failures.append(
                f"{path_label(result_root)} testcase manifest SHA-256 "
                "must match the exact result contract"
            )
    return failures


def path_label(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def android_result_freshness_inputs(
    *,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
) -> tuple[Path, ...]:
    inputs = list(exact_files)
    for source_root in source_roots:
        inputs.append(source_root)
        if source_root.is_dir():
            inputs.extend(
                sorted(
                    path
                    for path in source_root.rglob("*")
                    if path.is_file() or path.is_dir()
                )
            )
    return tuple(dict.fromkeys(inputs))


def android_result_staleness_failure(
    *,
    report_label: str,
    report_mtime_ns: int,
    input_mtimes: tuple[tuple[str, int], ...],
    current_time_ns: int | None = None,
) -> str | None:
    if not input_mtimes:
        return (
            f"{report_label} has no readable source freshness inputs; "
            "rerun cannot be validated"
        )
    newest_input_label, newest_input_mtime_ns = max(
        input_mtimes,
        key=lambda item: (item[1], item[0]),
    )
    if report_mtime_ns <= newest_input_mtime_ns:
        return (
            f"{report_label} is stale; rerun the exact Android product tests "
            f"after {newest_input_label}"
        )
    if current_time_ns is None:
        current_time_ns = time.time_ns()
    if (
        report_mtime_ns
        > current_time_ns + ANDROID_RESULT_FUTURE_MTIME_TOLERANCE_NS
    ):
        return (
            f"{report_label} timestamp is implausibly in the future; "
            "rerun with the current host clock"
        )
    return None


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def write_canonical_json_payload(
    path: Path,
    payload: object,
    *,
    label: str,
) -> list[str]:
    failures: list[str] = []
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(canonical_json_bytes(payload))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    except OSError as error:
        failures.append(
            f"{path_label(path)} cannot write {label}: {error}"
        )
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return failures


def android_result_source_snapshot(
    *,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
) -> tuple[dict[str, object] | None, list[str]]:
    failures: list[str] = []
    source_files: list[Path] = []
    for input_path in exact_files:
        if not input_path.is_file():
            failures.append(
                "Android result binding input must be a readable file: "
                f"{path_label(input_path)}"
            )
        else:
            source_files.append(input_path)
    for source_root in source_roots:
        if not source_root.is_dir():
            failures.append(
                "Android result binding source root must be a directory: "
                f"{path_label(source_root)}"
            )
            continue
        source_files.extend(
            sorted(
                path
                for path in source_root.rglob("*")
                if path.is_file()
            )
        )
    if failures:
        return None, failures

    entries: list[dict[str, object]] = []
    for source_path in sorted(
        dict.fromkeys(source_files),
        key=path_label,
    ):
        try:
            source_bytes = source_path.read_bytes()
            source_mode = source_path.stat().st_mode & 0o7777
        except OSError as error:
            failures.append(
                "Android result binding input cannot be read: "
                f"{path_label(source_path)}: {error}"
            )
            continue
        entries.append(
            {
                "bytes": len(source_bytes),
                "mode": source_mode,
                "path": path_label(source_path),
                "sha256": hashlib.sha256(source_bytes).hexdigest(),
            }
        )
    if failures:
        return None, failures
    manifest_bytes = canonical_json_bytes(entries)
    return (
        {
            "count": len(entries),
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        },
        [],
    )


def android_full_test_run_marker_payload(
    *,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
    expected_results: tuple[
        tuple[str, int, tuple[str, ...]], ...
    ] = ANDROID_FULL_TEST_RESULTS,
    testcase_manifest_sha256: str = (
        ANDROID_FULL_TEST_CASE_MANIFEST_SHA256
    ),
    marker_contract: str = ANDROID_FULL_TEST_RUN_MARKER_CONTRACT,
) -> tuple[dict[str, object] | None, list[str]]:
    source_snapshot, failures = android_result_source_snapshot(
        exact_files=exact_files,
        source_roots=source_roots,
    )
    if source_snapshot is None:
        return None, failures
    return (
        {
            "contract": marker_contract,
            "expectedReports": sorted(
                f"TEST-{class_name}.xml"
                for class_name, _, _ in expected_results
            ),
            "sourceInputs": source_snapshot,
            "testcaseManifestSha256": testcase_manifest_sha256,
            "tests": sum(count for _, count, _ in expected_results),
        },
        [],
    )


def android_full_test_run_marker_failures(
    *,
    result_root: Path = ANDROID_FULL_TEST_RESULT_ROOT,
    marker_path: Path = ANDROID_FULL_TEST_RUN_MARKER_PATH,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
    expected_results: tuple[
        tuple[str, int, tuple[str, ...]], ...
    ] = ANDROID_FULL_TEST_RESULTS,
    testcase_manifest_sha256: str = (
        ANDROID_FULL_TEST_CASE_MANIFEST_SHA256
    ),
    marker_contract: str = ANDROID_FULL_TEST_RUN_MARKER_CONTRACT,
    require_reports: bool = True,
) -> list[str]:
    expected_payload, failures = android_full_test_run_marker_payload(
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
        marker_contract=marker_contract,
    )
    if expected_payload is None:
        return failures
    try:
        marker_bytes = marker_path.read_bytes()
        json.loads(marker_bytes)
        marker_mtime_ns = marker_path.stat().st_mtime_ns
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        failures.append(
            f"{path_label(marker_path)} cannot be read: {error}"
        )
        return failures
    if marker_bytes != canonical_json_bytes(expected_payload):
        failures.append(
            f"{path_label(marker_path)} must exactly bind the Android "
            "source bytes from before the full-suite run"
        )
    if (
        marker_mtime_ns
        > time.time_ns() + ANDROID_RESULT_FUTURE_MTIME_TOLERANCE_NS
    ):
        failures.append(
            f"{path_label(marker_path)} timestamp is implausibly "
            "in the future"
        )
    if require_reports:
        for report_name in expected_payload["expectedReports"]:
            report_path = result_root / str(report_name)
            try:
                report_mtime_ns = report_path.stat().st_mtime_ns
            except OSError as error:
                failures.append(
                    f"{path_label(report_path)} timestamp cannot be "
                    f"read after the run marker: {error}"
                )
                continue
            if report_mtime_ns <= marker_mtime_ns:
                failures.append(
                    f"{path_label(report_path)} must be generated after "
                    "the Android full-suite source marker"
                )
    return failures


def write_android_full_test_run_marker(
    *,
    marker_path: Path = ANDROID_FULL_TEST_RUN_MARKER_PATH,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
    expected_results: tuple[
        tuple[str, int, tuple[str, ...]], ...
    ] = ANDROID_FULL_TEST_RESULTS,
    testcase_manifest_sha256: str = (
        ANDROID_FULL_TEST_CASE_MANIFEST_SHA256
    ),
    marker_contract: str = ANDROID_FULL_TEST_RUN_MARKER_CONTRACT,
) -> list[str]:
    payload, failures = android_full_test_run_marker_payload(
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
        marker_contract=marker_contract,
    )
    if payload is None:
        return failures
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{marker_path.name}.tmp-",
        dir=marker_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(canonical_json_bytes(payload))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, marker_path)
    except OSError as error:
        failures.append(
            f"{path_label(marker_path)} cannot be written: {error}"
        )
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    if not failures:
        failures.extend(
            android_full_test_run_marker_failures(
                marker_path=marker_path,
                exact_files=exact_files,
                source_roots=source_roots,
                expected_results=expected_results,
                testcase_manifest_sha256=testcase_manifest_sha256,
                marker_contract=marker_contract,
                require_reports=False,
            )
        )
    return failures


def android_full_test_report_snapshot(
    *,
    result_root: Path = ANDROID_FULL_TEST_RESULT_ROOT,
    expected_results: tuple[
        tuple[str, int, tuple[str, ...]], ...
    ] = ANDROID_FULL_TEST_RESULTS,
) -> tuple[list[dict[str, object]] | None, list[str]]:
    failures: list[str] = []
    reports: list[dict[str, object]] = []
    for class_name, _, _ in expected_results:
        report_path = result_root / f"TEST-{class_name}.xml"
        try:
            report_bytes = report_path.read_bytes()
        except OSError as error:
            failures.append(
                f"{path_label(report_path)} cannot be bound: {error}"
            )
            continue
        reports.append(
            {
                "bytes": len(report_bytes),
                "name": report_path.name,
                "sha256": hashlib.sha256(report_bytes).hexdigest(),
            }
        )
    if failures:
        return None, failures
    return sorted(reports, key=lambda report: str(report["name"])), []


def android_full_test_binding_payload(
    *,
    result_root: Path = ANDROID_FULL_TEST_RESULT_ROOT,
    marker_path: Path = ANDROID_FULL_TEST_RUN_MARKER_PATH,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
    expected_results: tuple[
        tuple[str, int, tuple[str, ...]], ...
    ] = ANDROID_FULL_TEST_RESULTS,
    testcase_manifest_sha256: str = (
        ANDROID_FULL_TEST_CASE_MANIFEST_SHA256
    ),
    binding_contract: str = ANDROID_FULL_TEST_BINDING_CONTRACT,
) -> tuple[dict[str, object] | None, list[str]]:
    source_snapshot, source_failures = android_result_source_snapshot(
        exact_files=exact_files,
        source_roots=source_roots,
    )
    report_snapshot, report_failures = android_full_test_report_snapshot(
        result_root=result_root,
        expected_results=expected_results,
    )
    try:
        marker_bytes = marker_path.read_bytes()
    except OSError as error:
        marker_snapshot = None
        marker_failures = [
            f"{path_label(marker_path)} cannot be bound: {error}"
        ]
    else:
        marker_snapshot = {
            "bytes": len(marker_bytes),
            "sha256": hashlib.sha256(marker_bytes).hexdigest(),
        }
        marker_failures = []
    failures = source_failures + report_failures + marker_failures
    if failures or source_snapshot is None or report_snapshot is None:
        return None, failures
    return (
        {
            "contract": binding_contract,
            "reports": report_snapshot,
            "runMarker": marker_snapshot,
            "sourceInputs": source_snapshot,
            "testcaseManifestSha256": testcase_manifest_sha256,
            "tests": sum(count for _, count, _ in expected_results),
        },
        [],
    )


def android_full_test_binding_failures(
    *,
    result_root: Path = ANDROID_FULL_TEST_RESULT_ROOT,
    binding_path: Path = ANDROID_FULL_TEST_BINDING_PATH,
    marker_path: Path = ANDROID_FULL_TEST_RUN_MARKER_PATH,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
    expected_results: tuple[
        tuple[str, int, tuple[str, ...]], ...
    ] = ANDROID_FULL_TEST_RESULTS,
    testcase_manifest_sha256: str = (
        ANDROID_FULL_TEST_CASE_MANIFEST_SHA256
    ),
    marker_contract: str = ANDROID_FULL_TEST_RUN_MARKER_CONTRACT,
    binding_contract: str = ANDROID_FULL_TEST_BINDING_CONTRACT,
) -> list[str]:
    marker_failures = android_full_test_run_marker_failures(
        result_root=result_root,
        marker_path=marker_path,
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
        marker_contract=marker_contract,
    )
    expected_payload, payload_failures = android_full_test_binding_payload(
        result_root=result_root,
        marker_path=marker_path,
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
        binding_contract=binding_contract,
    )
    failures = marker_failures + payload_failures
    if expected_payload is None:
        return failures
    try:
        binding_bytes = binding_path.read_bytes()
        json.loads(binding_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        failures.append(
            f"{path_label(binding_path)} cannot be read: {error}"
        )
        return failures
    expected_bytes = canonical_json_bytes(expected_payload)
    if binding_bytes != expected_bytes:
        failures.append(
            f"{path_label(binding_path)} must exactly bind the current "
            "Android full-suite source and report bytes"
        )

    try:
        binding_mtime_ns = binding_path.stat().st_mtime_ns
        report_mtimes = tuple(
            (
                result_root / str(report["name"])
            ).stat().st_mtime_ns
            for report in expected_payload["reports"]
        )
    except OSError as error:
        failures.append(
            "Android full-suite binding timestamp cannot be read: "
            f"{error}"
        )
    else:
        if report_mtimes and binding_mtime_ns <= max(report_mtimes):
            failures.append(
                f"{path_label(binding_path)} must postdate every bound "
                "Android full-suite report"
            )
        if (
            binding_mtime_ns
            > time.time_ns() + ANDROID_RESULT_FUTURE_MTIME_TOLERANCE_NS
        ):
            failures.append(
                f"{path_label(binding_path)} timestamp is implausibly "
                "in the future"
            )
    return failures


def write_android_full_test_binding(
    *,
    result_root: Path = ANDROID_FULL_TEST_RESULT_ROOT,
    binding_path: Path = ANDROID_FULL_TEST_BINDING_PATH,
    marker_path: Path = ANDROID_FULL_TEST_RUN_MARKER_PATH,
    exact_files: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_FILES,
    source_roots: tuple[Path, ...] = ANDROID_RESULT_FRESHNESS_ROOTS,
    expected_results: tuple[
        tuple[str, int, tuple[str, ...]], ...
    ] = ANDROID_FULL_TEST_RESULTS,
    testcase_manifest_sha256: str = (
        ANDROID_FULL_TEST_CASE_MANIFEST_SHA256
    ),
    marker_contract: str = ANDROID_FULL_TEST_RUN_MARKER_CONTRACT,
    binding_contract: str = ANDROID_FULL_TEST_BINDING_CONTRACT,
) -> list[str]:
    failures = android_full_test_run_marker_failures(
        result_root=result_root,
        marker_path=marker_path,
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
        marker_contract=marker_contract,
    )
    if failures:
        return failures
    payload, payload_failures = android_full_test_binding_payload(
        result_root=result_root,
        marker_path=marker_path,
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
        binding_contract=binding_contract,
    )
    failures.extend(payload_failures)
    if payload is None:
        return failures
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{binding_path.name}.tmp-",
        dir=binding_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(canonical_json_bytes(payload))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, binding_path)
    except OSError as error:
        failures.append(
            f"{path_label(binding_path)} cannot be written: {error}"
        )
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    if not failures:
        failures.extend(
            android_full_test_binding_failures(
                result_root=result_root,
                binding_path=binding_path,
                marker_path=marker_path,
                exact_files=exact_files,
                source_roots=source_roots,
                expected_results=expected_results,
                testcase_manifest_sha256=testcase_manifest_sha256,
                marker_contract=marker_contract,
                binding_contract=binding_contract,
            )
        )
    return failures


def prepare_android_core_nonsecurity_test_run() -> list[str]:
    failures = android_core_nonsecurity_selection_failures()
    if failures:
        return failures
    for (
        _label,
        _result_root,
        _binding_path,
        marker_path,
        expected_results,
        testcase_manifest_sha256,
        marker_contract,
        _binding_contract,
    ) in ANDROID_CORE_NONSECURITY_RESULT_CONTRACTS:
        failures.extend(
            write_android_full_test_run_marker(
                marker_path=marker_path,
                exact_files=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_FILES,
                source_roots=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_ROOTS,
                expected_results=expected_results,
                testcase_manifest_sha256=testcase_manifest_sha256,
                marker_contract=marker_contract,
            )
        )
    return failures


def android_core_nonsecurity_test_result_failures(
    *,
    require_bindings: bool,
) -> list[str]:
    failures: list[str] = []
    freshness_inputs = android_result_freshness_inputs(
        exact_files=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_FILES,
        source_roots=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_ROOTS,
    )
    for (
        label,
        result_root,
        binding_path,
        marker_path,
        expected_results,
        testcase_manifest_sha256,
        marker_contract,
        binding_contract,
    ) in ANDROID_CORE_NONSECURITY_RESULT_CONTRACTS:
        result_failures = android_test_result_failures(
            expected_results,
            result_root=result_root,
            freshness_inputs=freshness_inputs,
            allow_additional_methods=False,
            require_exact_report_set=True,
            expected_testcase_manifest_sha256=testcase_manifest_sha256,
        )
        failures.extend(
            f"Android core non-security {label}: {failure}"
            for failure in result_failures
        )
        if require_bindings and not result_failures:
            binding_failures = android_full_test_binding_failures(
                result_root=result_root,
                binding_path=binding_path,
                marker_path=marker_path,
                exact_files=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_FILES,
                source_roots=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_ROOTS,
                expected_results=expected_results,
                testcase_manifest_sha256=testcase_manifest_sha256,
                marker_contract=marker_contract,
                binding_contract=binding_contract,
            )
            failures.extend(
                f"Android core non-security {label}: {failure}"
                for failure in binding_failures
            )
    return failures


def write_android_core_nonsecurity_test_bindings() -> list[str]:
    failures = android_core_nonsecurity_test_result_failures(
        require_bindings=False,
    )
    if failures:
        return failures
    for (
        label,
        result_root,
        binding_path,
        marker_path,
        expected_results,
        testcase_manifest_sha256,
        marker_contract,
        binding_contract,
    ) in ANDROID_CORE_NONSECURITY_RESULT_CONTRACTS:
        binding_failures = write_android_full_test_binding(
            result_root=result_root,
            binding_path=binding_path,
            marker_path=marker_path,
            exact_files=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_FILES,
            source_roots=ANDROID_CORE_NONSECURITY_RESULT_FRESHNESS_ROOTS,
            expected_results=expected_results,
            testcase_manifest_sha256=testcase_manifest_sha256,
            marker_contract=marker_contract,
            binding_contract=binding_contract,
        )
        failures.extend(
            f"Android core non-security {label}: {failure}"
            for failure in binding_failures
        )
    return failures


def read_bounded_regular_bytes(
    path: Path,
    *,
    max_bytes: int,
    label: str,
) -> tuple[bytes | None, list[str]]:
    try:
        before = path.lstat()
    except OSError as error:
        return None, [f"{path_label(path)} cannot read {label}: {error}"]
    if not stat.S_ISREG(before.st_mode):
        return None, [f"{path_label(path)} {label} must be a regular file"]
    if before.st_size > max_bytes:
        return None, [
            f"{path_label(path)} {label} exceeds {max_bytes} bytes"
        ]

    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            return None, [
                f"{path_label(path)} {label} changed during descriptor open"
            ]
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                return None, [
                    f"{path_label(path)} {label} exceeds {max_bytes} bytes"
                ]
        after = os.fstat(descriptor)
        if (
            (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            )
        ):
            return None, [
                f"{path_label(path)} {label} changed during descriptor read"
            ]
        return b"".join(chunks), []
    except OSError as error:
        return None, [f"{path_label(path)} cannot read {label}: {error}"]
    finally:
        if descriptor is not None:
            os.close(descriptor)


def swift_focused_package_source_path_failures(
    *,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
) -> list[str]:
    package_bytes, failures = read_bounded_regular_bytes(
        package_path,
        max_bytes=SWIFT_FOCUSED_PACKAGE_MAX_BYTES,
        label="Swift package manifest",
    )
    if package_bytes is None:
        return failures
    try:
        package_bytes.decode("utf-8")
    except UnicodeError as error:
        return [
            f"{path_label(package_path)} Swift package manifest must be "
            f"UTF-8: {error}"
        ]
    if package_path.name != "Package.swift":
        failures.append("focused Swift package manifest must be named Package.swift")

    expected_source_paths = tuple(
        target_path for _, _, target_path in expected_targets
    )
    expected_names = tuple(target_name for _, target_name, _ in expected_targets)
    if len(set(expected_targets)) != len(expected_targets):
        failures.append("focused Swift package target contracts must be unique")
    if len(set(expected_names)) != len(expected_names):
        failures.append("focused Swift package target names must be unique")
    if len(set(expected_source_paths)) != len(expected_source_paths):
        failures.append("focused Swift package target paths must be unique")
    for target_type, target_name, relative_path in expected_targets:
        components = relative_path.split("/")
        if (
            target_type not in ("regular", "executable", "test")
            or not target_name
            or not relative_path
            or relative_path.startswith("/")
            or any(component in ("", ".", "..") for component in components)
            or components[-1] not in ("Sources", "Tests")
            or any(component in (".build", "build") for component in components)
        ):
            failures.append(
                "focused Swift source contract contains an invalid target "
                f"path: {relative_path!r}"
            )

    if observed_targets is None and not failures:
        try:
            completed = subprocess.run(
                SWIFT_FOCUSED_PACKAGE_DUMP_COMMAND,
                cwd=package_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=SWIFT_FOCUSED_PACKAGE_DUMP_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(
                f"focused Swift package semantic dump failed: {error}"
            )
        else:
            if completed.returncode != 0:
                stderr_text = completed.stderr[:512].decode(
                    "utf-8",
                    errors="replace",
                )
                failures.append(
                    "focused Swift package semantic dump exited with status "
                    f"{completed.returncode}: {stderr_text!r}"
                )
            elif len(completed.stdout) > SWIFT_FOCUSED_PACKAGE_DUMP_MAX_BYTES:
                failures.append(
                    "focused Swift package semantic dump exceeds the byte bound"
                )
            else:
                try:
                    dump_payload = json.loads(completed.stdout)
                except (UnicodeError, json.JSONDecodeError) as error:
                    failures.append(
                        "focused Swift package semantic dump must be JSON: "
                        f"{error}"
                    )
                else:
                    targets_value = (
                        dump_payload.get("targets")
                        if isinstance(dump_payload, dict)
                        else None
                    )
                    if not isinstance(targets_value, list):
                        failures.append(
                            "focused Swift package semantic dump must contain "
                            "a targets array"
                        )
                    else:
                        extracted_targets: list[tuple[str, str, str]] = []
                        for index, target_value in enumerate(targets_value):
                            if not isinstance(target_value, dict):
                                failures.append(
                                    "focused Swift package semantic target "
                                    f"{index} must be an object"
                                )
                                continue
                            target_type = target_value.get("type")
                            target_name = target_value.get("name")
                            target_path = target_value.get("path")
                            if not all(
                                isinstance(value, str) and bool(value)
                                for value in (
                                    target_type,
                                    target_name,
                                    target_path,
                                )
                            ):
                                failures.append(
                                    "focused Swift package semantic target "
                                    f"{index} must have nonempty string type, "
                                    "name, and path"
                                )
                                continue
                            extracted_targets.append(
                                (target_type, target_name, target_path)
                            )
                        if not failures:
                            observed_targets = tuple(extracted_targets)

    if observed_targets is not None and observed_targets != expected_targets:
        failures.append(
            "Swift package semantic targets must exactly match the focused "
            f"source contract; expected={expected_targets!r}; "
            f"found={observed_targets!r}"
        )

    expected_roots = tuple(
        package_path.parent / relative_path
        for relative_path in expected_source_paths
    )
    if source_roots != expected_roots:
        failures.append(
            "focused Swift source roots must be derived exactly from the "
            "Package.swift target path contract"
        )

    for source_root in source_roots:
        if not source_root.is_dir():
            continue
        for candidate in source_root.rglob("*"):
            try:
                relative_parts = candidate.relative_to(source_root).parts
            except ValueError:
                failures.append(
                    "focused Swift source traversal escaped its target root: "
                    f"{path_label(candidate)}"
                )
                continue
            if any(
                component in (".build", "build")
                for component in relative_parts
            ):
                failures.append(
                    "focused Swift target roots must not contain generated "
                    f"build paths: {path_label(candidate)}"
                )
                break
    return failures


def swift_focused_source_snapshot(
    *,
    exact_files: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_EXACT_FILES,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
) -> tuple[dict[str, object] | None, list[str]]:
    failures = swift_focused_package_source_path_failures(
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
        source_roots=source_roots,
    )
    if failures:
        return None, failures
    source_snapshot, source_failures = android_result_source_snapshot(
        exact_files=exact_files,
        source_roots=source_roots,
    )
    if source_failures:
        return None, source_failures
    return source_snapshot, []


def swift_focused_test_list_snapshot(
    *,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
) -> tuple[dict[str, object] | None, tuple[str, ...] | None, list[str]]:
    selected_tests, test_list_bytes, failures = swift_selected_test_names(
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        excluded_tests=excluded_tests,
    )
    if selected_tests is None or test_list_bytes is None:
        return None, None, failures
    if len(selected_tests) != expected_count:
        failures.append(
            "Swift product test selection must match exactly "
            f"{expected_count} tests, found {len(selected_tests)}"
        )
    manifest_sha256 = swift_test_selection_manifest_sha256(selected_tests)
    if manifest_sha256 != expected_manifest_sha256:
        failures.append(
            "Swift product test selection manifest SHA-256 must match the "
            "exact contract"
        )
    if failures:
        return None, None, failures
    snapshot: dict[str, object] = {
        "bytes": len(test_list_bytes),
        "sha256": hashlib.sha256(test_list_bytes).hexdigest(),
        "testcaseManifestSha256": manifest_sha256,
        "tests": len(selected_tests),
    }
    if excluded_tests:
        snapshot["excludedTestcaseManifestSha256"] = (
            swift_test_selection_manifest_sha256(excluded_tests)
        )
        snapshot["excludedTests"] = len(excluded_tests)
    return snapshot, selected_tests, []


def swift_focused_test_run_marker_payload(
    *,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
    exact_files: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_EXACT_FILES,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
) -> tuple[dict[str, object] | None, list[str]]:
    source_snapshot, source_failures = swift_focused_source_snapshot(
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
    )
    list_snapshot, _, list_failures = swift_focused_test_list_snapshot(
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
    )
    failures = source_failures + list_failures
    if failures or source_snapshot is None or list_snapshot is None:
        return None, failures
    return (
        {
            "contract": SWIFT_FOCUSED_TEST_RUN_MARKER_CONTRACT,
            "sourceInputs": source_snapshot,
            "testList": list_snapshot,
        },
        [],
    )


def swift_focused_test_run_marker_failures(
    *,
    marker_path: Path = SWIFT_FOCUSED_TEST_RUN_MARKER_PATH,
    log_path: Path = SWIFT_FOCUSED_TEST_LOG_PATH,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
    exact_files: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_EXACT_FILES,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
    require_log: bool = True,
) -> list[str]:
    expected_payload, failures = swift_focused_test_run_marker_payload(
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
    )
    if expected_payload is None:
        return failures
    try:
        marker_bytes = marker_path.read_bytes()
        json.loads(marker_bytes)
        marker_mtime_ns = marker_path.stat().st_mtime_ns
        test_list_mtime_ns = test_list_path.stat().st_mtime_ns
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        failures.append(
            f"{path_label(marker_path)} cannot be read: {error}"
        )
        return failures
    if marker_bytes != canonical_json_bytes(expected_payload):
        failures.append(
            f"{path_label(marker_path)} must exactly bind the focused Swift "
            "source and selected test-list bytes from before execution"
        )
    if marker_mtime_ns <= test_list_mtime_ns:
        failures.append(
            f"{path_label(marker_path)} must postdate the selected Swift "
            "test list"
        )
    if (
        marker_mtime_ns
        > time.time_ns() + SWIFT_FOCUSED_TEST_FUTURE_MTIME_TOLERANCE_NS
    ):
        failures.append(
            f"{path_label(marker_path)} timestamp is implausibly in the future"
        )
    if require_log:
        try:
            log_mtime_ns = log_path.stat().st_mtime_ns
        except OSError as error:
            failures.append(
                f"{path_label(log_path)} timestamp cannot be read after the "
                f"focused Swift source marker: {error}"
            )
        else:
            if log_mtime_ns <= marker_mtime_ns:
                failures.append(
                    f"{path_label(log_path)} must be generated after the "
                    "focused Swift source marker"
                )
    return failures


def write_swift_focused_test_run_marker(
    *,
    marker_path: Path = SWIFT_FOCUSED_TEST_RUN_MARKER_PATH,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
    exact_files: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_EXACT_FILES,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
) -> list[str]:
    payload, failures = swift_focused_test_run_marker_payload(
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
    )
    if payload is None:
        return failures
    failures.extend(
        write_canonical_json_payload(
            marker_path,
            payload,
            label="focused Swift source marker",
        )
    )
    if not failures:
        failures.extend(
            swift_focused_test_run_marker_failures(
                marker_path=marker_path,
                test_list_path=test_list_path,
                filter_pattern=filter_pattern,
                expected_count=expected_count,
                expected_manifest_sha256=expected_manifest_sha256,
                excluded_tests=excluded_tests,
                exact_files=exact_files,
                source_roots=source_roots,
                package_path=package_path,
                expected_targets=expected_targets,
                observed_targets=observed_targets,
                require_log=False,
            )
        )
    return failures


SWIFT_XCTEST_EVENT_PATTERN = re.compile(
    r"^Test Case '-\[([^\]\s]+) ([^\]\s]+)\]' "
    r"(started|passed|failed|skipped)(?: \([^\r\n]+\))?\.$"
)
SWIFT_XCTEST_SUMMARY_PATTERN = re.compile(
    r"^\s*Executed (\d+) tests?, with (\d+) failures? "
    r"\((\d+) unexpected\) in [0-9.]+ \([0-9.]+\) seconds$"
)


def swift_focused_console_snapshot(
    *,
    log_path: Path = SWIFT_FOCUSED_TEST_LOG_PATH,
    expected_tests: tuple[str, ...],
    max_bytes: int = SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
) -> tuple[dict[str, object] | None, list[str]]:
    log_bytes, failures = read_bounded_regular_bytes(
        log_path,
        max_bytes=max_bytes,
        label="focused Swift console log",
    )
    if log_bytes is None:
        return None, failures
    try:
        log_text = log_bytes.decode("utf-8")
    except UnicodeError as error:
        return None, [
            f"{path_label(log_path)} focused Swift console log must be "
            f"UTF-8: {error}"
        ]
    if not log_bytes.endswith(b"\n"):
        failures.append("focused Swift console log must end with LF")

    events_by_test: dict[str, list[tuple[int, str]]] = {}
    malformed_events: list[str] = []
    summaries: list[tuple[int, tuple[int, int, int]]] = []
    for line_number, line in enumerate(log_text.splitlines(), start=1):
        if line.startswith("Test Case '-["):
            match = SWIFT_XCTEST_EVENT_PATTERN.fullmatch(line)
            if match is None:
                malformed_events.append(f"line {line_number}")
                continue
            identity = f"{match.group(1)}/{match.group(2)}"
            events_by_test.setdefault(identity, []).append(
                (line_number, match.group(3))
            )
        summary = SWIFT_XCTEST_SUMMARY_PATTERN.fullmatch(line)
        if summary is not None:
            summaries.append(
                (
                    line_number,
                    tuple(int(value) for value in summary.groups()),
                )
            )
    if malformed_events:
        failures.append(
            "focused Swift console contains malformed XCTest events at "
            + ", ".join(malformed_events[:5])
        )

    expected_set = set(expected_tests)
    observed_set = set(events_by_test)
    if observed_set != expected_set:
        missing = sorted(expected_set - observed_set)
        unexpected = sorted(observed_set - expected_set)
        failures.append(
            "focused Swift console testcase identities must exactly match "
            f"the selected manifest; missing={missing[:3]!r}; "
            f"unexpected={unexpected[:3]!r}"
        )
    for identity in sorted(expected_set & observed_set):
        events = events_by_test[identity]
        event_names = tuple(event for _, event in events)
        if event_names != ("started", "passed"):
            failures.append(
                f"focused Swift testcase {identity} must contain exactly one "
                f"ordered started/passed pair; found {event_names!r}"
            )
    if any(
        summary[1] != 0 or summary[2] != 0
        for _line, summary in summaries
    ):
        failures.append(
            "focused Swift console must not contain a failing XCTest summary"
        )
    if not summaries:
        failures.append("focused Swift console must contain an XCTest summary")
    elif summaries[-1][1] != (len(expected_tests), 0, 0):
        failures.append(
            "focused Swift final XCTest summary must report exactly "
            f"{len(expected_tests)} tests and zero failures/unexpected; "
            f"found {summaries[-1][1]!r}"
        )
    elif events_by_test and summaries[-1][0] <= max(
        line_number
        for events in events_by_test.values()
        for line_number, _ in events
    ):
        failures.append(
            "focused Swift final XCTest summary must follow every testcase "
            "event"
        )
    if failures:
        return None, failures
    observed_tests = tuple(sorted(observed_set))
    manifest_sha256 = swift_test_selection_manifest_sha256(observed_tests)
    return (
        {
            "bytes": len(log_bytes),
            "errors": 0,
            "failures": 0,
            "sha256": hashlib.sha256(log_bytes).hexdigest(),
            "skipped": 0,
            "testcaseManifestSha256": manifest_sha256,
            "tests": len(observed_tests),
        },
        [],
    )


def document_ingestion_mutation_console_snapshot(
    log_path: Path,
    *,
    expected_case_count: int = DOCUMENT_INGESTION_MUTATION_CASE_COUNT,
    expected_root: str = DOCUMENT_INGESTION_MUTATION_ROOT_SEED,
    expected_manifest_sha256: str = (
        DOCUMENT_INGESTION_MUTATION_MARKER_MANIFEST_SHA256
    ),
    expected_formats: tuple[str, ...] = (
        DOCUMENT_INGESTION_MUTATION_FORMATS
    ),
    expected_primary_operators: tuple[str, ...] = (
        DOCUMENT_INGESTION_MUTATION_PRIMARY_OPERATORS
    ),
    expected_test_identity: str = (
        DOCUMENT_INGESTION_MUTATION_TEST_IDENTITY
    ),
    max_bytes: int = SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
) -> tuple[dict[str, object] | None, list[str]]:
    log_bytes, failures = read_bounded_regular_bytes(
        log_path,
        max_bytes=max_bytes,
        label="DocumentIngestion mutation console log",
    )
    if log_bytes is None:
        return None, failures
    try:
        log_text = log_bytes.decode("utf-8")
    except UnicodeError as error:
        return None, [
            "DocumentIngestion mutation console log must be UTF-8: "
            f"{error}"
        ]
    if not log_bytes.endswith(b"\n"):
        failures.append(
            "DocumentIngestion mutation console log must end with LF"
        )

    lines = log_text.splitlines()
    started_positions: list[int] = []
    passed_positions: list[int] = []
    marker_entries: list[tuple[int, str, re.Match[str]]] = []
    summary_entries: list[tuple[int, re.Match[str]]] = []
    for position, line in enumerate(lines):
        event = SWIFT_XCTEST_EVENT_PATTERN.fullmatch(line)
        if event is not None:
            identity = f"{event.group(1)}/{event.group(2)}"
            if identity == expected_test_identity:
                if event.group(3) == "started":
                    started_positions.append(position)
                elif event.group(3) == "passed":
                    passed_positions.append(position)
        if line.startswith("AETHERLINK_DOCUMENT_MUTATION_V1 "):
            match = DOCUMENT_INGESTION_MUTATION_MARKER_PATTERN.fullmatch(line)
            if match is None:
                failures.append(
                    "DocumentIngestion mutation console contains a malformed "
                    f"case marker at line {position + 1}"
                )
            else:
                marker_entries.append((position, line, match))
        if line.startswith("AETHERLINK_DOCUMENT_MUTATION_SUMMARY_V1 "):
            match = DOCUMENT_INGESTION_MUTATION_SUMMARY_PATTERN.fullmatch(line)
            if match is None:
                failures.append(
                    "DocumentIngestion mutation console contains a malformed "
                    f"summary at line {position + 1}"
                )
            else:
                summary_entries.append((position, match))

    if len(started_positions) != 1 or len(passed_positions) != 1:
        failures.append(
            "DocumentIngestion mutation case markers must be enclosed by one "
            "exact started/passed testcase pair"
        )
    if len(marker_entries) != expected_case_count:
        failures.append(
            "DocumentIngestion mutation console must contain exactly "
            f"{expected_case_count} complete case markers; found "
            f"{len(marker_entries)}"
        )
    if len(summary_entries) != 1:
        failures.append(
            "DocumentIngestion mutation console must contain exactly one "
            "complete summary"
        )

    expected_total = f"{expected_case_count:03d}"
    allowed_operators = set(expected_primary_operators)
    observed_seeds: set[str] = set()
    observed_format_counts = {format_name: 0 for format_name in expected_formats}
    marker_lines: list[str] = []
    for observed_index, (_, marker_line, match) in enumerate(marker_entries):
        marker_lines.append(marker_line)
        case_index = int(match.group("case"))
        if case_index != observed_index:
            failures.append(
                "DocumentIngestion mutation case markers must be ordered "
                f"000...{expected_case_count - 1:03d}"
            )
            break
        if match.group("total") != expected_total:
            failures.append(
                "DocumentIngestion mutation case marker total must match the "
                "exact corpus"
            )
        if match.group("root") != expected_root:
            failures.append(
                "DocumentIngestion mutation case marker root must match the "
                "fixed seed"
            )
        seed = match.group("seed")
        if seed in observed_seeds:
            failures.append(
                "DocumentIngestion mutation case seeds must be unique"
            )
        observed_seeds.add(seed)
        if not expected_formats:
            failures.append(
                "DocumentIngestion mutation expected format set is empty"
            )
            continue
        expected_format = expected_formats[case_index % len(expected_formats)]
        observed_format = match.group("format")
        if observed_format != expected_format:
            failures.append(
                "DocumentIngestion mutation format order must match the exact "
                "cross-product"
            )
        if observed_format in observed_format_counts:
            observed_format_counts[observed_format] += 1
        operators = tuple(match.group("operators").split(","))
        if not 1 <= len(operators) <= 4:
            failures.append(
                "DocumentIngestion mutation case must contain one through "
                "four operators"
            )
        if any(operator not in allowed_operators for operator in operators):
            failures.append(
                "DocumentIngestion mutation case contains an unknown operator"
            )
        if expected_formats:
            primary_index = case_index // len(expected_formats)
            if primary_index >= len(expected_primary_operators):
                failures.append(
                    "DocumentIngestion mutation primary operator index is "
                    "outside the exact cross-product"
                )
            elif operators[-1] != expected_primary_operators[primary_index]:
                failures.append(
                    "DocumentIngestion mutation primary operator order must "
                    "match the exact cross-product"
                )
            elif operators[-1] in ("pad_exact_4096", "pad_plus_one_4097"):
                if len(operators) != 1:
                    failures.append(
                        "DocumentIngestion limit cases must contain only their "
                        "primary operator"
                    )
        byte_count = int(match.group("bytes"))
        if byte_count > 4_097:
            failures.append(
                "DocumentIngestion mutation case exceeds the 4097-byte bound"
            )
        if operators[-1] == "pad_exact_4096" and byte_count != 4_096:
            failures.append(
                "DocumentIngestion exact-limit case must contain 4096 bytes"
            )
        if operators[-1] == "pad_plus_one_4097" and byte_count != 4_097:
            failures.append(
                "DocumentIngestion plus-one case must contain 4097 bytes"
            )

    expected_per_format = (
        len(expected_primary_operators) if expected_formats else 0
    )
    if any(
        count != expected_per_format
        for count in observed_format_counts.values()
    ):
        failures.append(
            "DocumentIngestion mutation format counts must cover the exact "
            "operator cross-product"
        )
    marker_manifest = ("\n".join(marker_lines) + "\n").encode("ascii")
    observed_manifest_sha256 = hashlib.sha256(marker_manifest).hexdigest()
    if observed_manifest_sha256 != expected_manifest_sha256:
        failures.append(
            "DocumentIngestion mutation marker manifest SHA-256 must match "
            "the exact corpus"
        )

    if len(summary_entries) == 1:
        summary_position, summary = summary_entries[0]
        if (
            summary.group("total") != expected_total
            or summary.group("root") != expected_root
            or summary.group("manifest") != expected_manifest_sha256
        ):
            failures.append(
                "DocumentIngestion mutation summary must bind the exact "
                "corpus manifest"
            )
        if marker_entries and summary_position <= marker_entries[-1][0]:
            failures.append(
                "DocumentIngestion mutation summary must follow every case "
                "marker"
            )
    if len(started_positions) == 1 and len(passed_positions) == 1:
        started_position = started_positions[0]
        passed_position = passed_positions[0]
        if started_position >= passed_position:
            failures.append(
                "DocumentIngestion mutation testcase events are reversed"
            )
        if marker_entries and (
            marker_entries[0][0] <= started_position
            or marker_entries[-1][0] >= passed_position
        ):
            failures.append(
                "DocumentIngestion mutation markers must occur inside the "
                "bounded testcase"
            )
        if summary_entries and not (
            started_position < summary_entries[0][0] < passed_position
        ):
            failures.append(
                "DocumentIngestion mutation summary must occur inside the "
                "bounded testcase"
            )
    if failures:
        return None, failures
    return (
        {
            "bytesMaximum": 4_097,
            "cases": expected_case_count,
            "formatCases": observed_format_counts,
            "generator": "splitmix64-v1",
            "markerManifestSha256": observed_manifest_sha256,
            "root": expected_root,
            "summaryCount": 1,
        },
        [],
    )


def last_document_ingestion_mutation_marker(log_path: Path) -> str | None:
    log_bytes, _ = read_bounded_regular_bytes(
        log_path,
        max_bytes=SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
        label="DocumentIngestion mutation failure console",
    )
    if log_bytes is None:
        return None
    for raw_line in reversed(log_bytes.splitlines()):
        try:
            line = raw_line.decode("ascii")
        except UnicodeError:
            continue
        if DOCUMENT_INGESTION_MUTATION_MARKER_PATTERN.fullmatch(line):
            return (
                "last observed DocumentIngestion mutation marker: " + line
            )
    return None


def run_and_publish_swift_focused_log(
    *,
    command: tuple[str, ...],
    cwd: Path,
    log_path: Path,
    expected_tests: tuple[str, ...],
    log_context_failures: Callable[[Path], list[str]],
    failure_context: Callable[[Path], str | None] | None = None,
    max_bytes: int = SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
    timeout_seconds: float = SWIFT_FOCUSED_TEST_RUN_TIMEOUT_SECONDS,
    termination_grace_seconds: float = (
        SWIFT_FOCUSED_TEST_TERMINATION_GRACE_SECONDS
    ),
    environment: dict[str, str] | None = None,
) -> tuple[int, list[str]]:
    if not command:
        return 1, ["focused Swift runner command must not be empty"]
    if max_bytes <= 0:
        return 1, ["focused Swift runner log bound must be positive"]
    if timeout_seconds <= 0:
        return 1, ["focused Swift runner timeout must be positive"]
    if (
        type(termination_grace_seconds) not in (int, float)
        or not 0 < termination_grace_seconds < float("inf")
    ):
        return 1, [
            "focused Swift runner termination grace must be a positive "
            "finite number"
        ]
    if environment is not None and (
        type(environment) is not dict
        or any(
            type(key) is not str
            or type(value) is not str
            or not key
            or "\x00" in key
            or "=" in key
            or "\x00" in value
            for key, value in environment.items()
        )
    ):
        return 1, ["focused Swift runner environment must be canonical text"]

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{log_path.name}.tmp-",
            dir=log_path.parent,
        )
    except OSError as error:
        return 1, [f"focused Swift runner failed: {error}"]
    temporary_path = Path(temporary_name)
    process: subprocess.Popen[bytes] | None = None
    status = 1
    failures: list[str] = []
    temporary_snapshot: dict[str, object] | None = None
    published_snapshot: dict[str, object] | None = None
    backup_path: Path | None = None
    previous_canonical_state: tuple[int, int, int, int] | None = None
    published = False
    interrupted_signal: int | None = None

    class SwiftRunnerSignal(BaseException):
        def __init__(self, signum: int) -> None:
            super().__init__(signum)
            self.signum = signum

    handled_signals = (signal.SIGTERM, signal.SIGINT)
    previous_signal_handlers: dict[int, object] = {}
    previous_signal_mask: set[signal.Signals] | None = None
    received_signal: int | None = None

    def receive_swift_runner_signal(signum: int, _frame: object) -> None:
        nonlocal received_signal
        if received_signal is not None:
            return
        received_signal = signum
        raise SwiftRunnerSignal(signum)

    def restore_signal_handlers() -> None:
        for handled_signal, previous_handler in reversed(
            tuple(previous_signal_handlers.items())
        ):
            try:
                signal.signal(handled_signal, previous_handler)
            except (OSError, ValueError) as error:
                failures.append(
                    "focused Swift runner signal-handler restoration failed "
                    f"for {handled_signal}: {error}"
                )
        previous_signal_handlers.clear()

    def restore_parent_signal_mask() -> None:
        nonlocal previous_signal_mask
        if previous_signal_mask is None:
            return
        mask = previous_signal_mask
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        except (AttributeError, OSError, ValueError) as error:
            failures.append(
                "focused Swift runner signal-mask restoration failed: "
                f"{error}"
            )
        else:
            previous_signal_mask = None

    def process_group_exists() -> bool:
        if process is None:
            return False
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def wait_for_process_group_exit(timeout: float) -> bool:
        if process is None:
            return True
        deadline = time.monotonic() + timeout
        while True:
            leader_exited = process.poll() is not None
            group_exited = not process_group_exists()
            if leader_exited and group_exited:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            if not leader_exited:
                try:
                    process.wait(timeout=min(0.05, remaining))
                except subprocess.TimeoutExpired:
                    pass
            else:
                time.sleep(min(0.01, remaining))

    def terminate_process_group(
        initial_signal: int = signal.SIGTERM,
    ) -> None:
        if process is None:
            return
        termination_errors: list[str] = []
        try:
            os.killpg(process.pid, initial_signal)
        except ProcessLookupError:
            pass
        except OSError as error:
            termination_errors.append(
                f"signal {initial_signal} failed: {error}"
            )
        if wait_for_process_group_exit(termination_grace_seconds):
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as error:
            termination_errors.append(f"SIGKILL failed: {error}")
        if wait_for_process_group_exit(termination_grace_seconds):
            return
        detail = "; ".join(termination_errors)
        if detail:
            detail = f": {detail}"
        failures.append(
            "focused Swift runner could not terminate and reap its complete "
            f"process group{detail}"
        )

    def restore_previous_canonical() -> None:
        nonlocal published
        try:
            if previous_canonical_state is None:
                try:
                    log_path.unlink()
                except FileNotFoundError:
                    pass
                try:
                    log_path.lstat()
                except FileNotFoundError:
                    pass
                else:
                    failures.append(
                        "focused Swift failed publication did not remove its "
                        "new canonical log"
                    )
            elif backup_path is None or not backup_path.exists():
                failures.append(
                    "focused Swift failed publication cannot restore the "
                    "previous canonical log"
                )
            else:
                os.replace(backup_path, log_path)
                restored = log_path.lstat()
                restored_state = (
                    restored.st_dev,
                    restored.st_ino,
                    restored.st_size,
                    restored.st_mtime_ns,
                )
                if restored_state != previous_canonical_state:
                    failures.append(
                        "focused Swift restored canonical log identity differs "
                        "from the pre-run log"
                    )
        except OSError as error:
            failures.append(
                f"focused Swift canonical log restoration failed: {error}"
            )
        published = False

    try:
        for handled_signal in handled_signals:
            previous_signal_handlers[handled_signal] = signal.getsignal(
                handled_signal
            )
            signal.signal(handled_signal, receive_swift_runner_signal)
        previous_signal_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            handled_signals,
        )
    except SwiftRunnerSignal as interruption:
        restore_signal_handlers()
        try:
            os.close(descriptor)
            temporary_path.unlink()
        except OSError:
            pass
        os.kill(os.getpid(), interruption.signum)
        raise SystemExit(128 + interruption.signum) from None
    except (AttributeError, OSError, ValueError) as error:
        failures.append(
            "focused Swift runner could not install cancellation handlers: "
            f"{error}"
        )
        restore_signal_handlers()
        restore_parent_signal_mask()
        try:
            os.close(descriptor)
        except OSError as close_error:
            failures.append(
                "focused Swift runner temporary log close failed: "
                f"{close_error}"
            )
        try:
            temporary_path.unlink()
        except OSError as unlink_error:
            failures.append(
                "focused Swift runner temporary log cleanup failed: "
                f"{unlink_error}"
            )
        return 1, failures

    try:
        with os.fdopen(descriptor, "wb") as output:
            child_signal_mask = previous_signal_mask

            def restore_child_signal_mask() -> None:
                if child_signal_mask is not None:
                    signal.pthread_sigmask(
                        signal.SIG_SETMASK,
                        child_signal_mask,
                    )

            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=environment,
                preexec_fn=restore_child_signal_mask,
            )
            restore_parent_signal_mask()
            if process.stdout is None:
                raise OSError("focused Swift runner stdout pipe was not created")
            total = 0
            deadline = time.monotonic() + timeout_seconds
            selector = selectors.DefaultSelector()
            try:
                selector.register(process.stdout, selectors.EVENT_READ)
                reached_eof = False
                while not reached_eof:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        terminate_process_group()
                        failures.append(
                            "focused Swift test command timed out after "
                            f"{timeout_seconds:g} seconds"
                        )
                        break
                    events = selector.select(timeout=remaining)
                    if not events:
                        terminate_process_group()
                        failures.append(
                            "focused Swift test command timed out after "
                            f"{timeout_seconds:g} seconds"
                        )
                        break
                    for key, _ in events:
                        chunk = os.read(key.fd, 65_536)
                        if not chunk:
                            reached_eof = True
                            break
                        remaining_capacity = max_bytes - total
                        if len(chunk) > remaining_capacity:
                            if remaining_capacity > 0:
                                output.write(chunk[:remaining_capacity])
                                total += remaining_capacity
                            terminate_process_group()
                            failures.append(
                                "focused Swift console exceeded the bounded "
                                "log size"
                            )
                            reached_eof = True
                            break
                        else:
                            output.write(chunk)
                            total += len(chunk)
            finally:
                selector.close()
            if not failures and process.poll() is None:
                remaining = max(0.001, deadline - time.monotonic())
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    terminate_process_group()
                    failures.append(
                        "focused Swift test command timed out after "
                        f"{timeout_seconds:g} seconds"
                    )
            if not failures and not wait_for_process_group_exit(1):
                terminate_process_group()
                failures.append(
                    "focused Swift test command left a descendant process "
                    "group after its leader exited"
                )
            process.stdout.close()
            if process.returncode is not None:
                status = process.returncode
            output.flush()
            os.fsync(output.fileno())

        if not failures and status != 0:
            failures.append(
                "focused Swift test command exited with status "
                f"{status}; canonical log was not replaced"
            )
        if not failures:
            temporary_snapshot, console_failures = (
                swift_focused_console_snapshot(
                    log_path=temporary_path,
                    expected_tests=expected_tests,
                    max_bytes=max_bytes,
                )
            )
            failures.extend(console_failures)
        if not failures:
            failures.extend(log_context_failures(temporary_path))
        if not failures:
            try:
                previous = log_path.lstat()
            except FileNotFoundError:
                previous_canonical_state = None
            else:
                if not stat.S_ISREG(previous.st_mode):
                    failures.append(
                        "focused Swift existing canonical log must be a regular "
                        "file"
                    )
                else:
                    previous_canonical_state = (
                        previous.st_dev,
                        previous.st_ino,
                        previous.st_size,
                        previous.st_mtime_ns,
                    )
                    backup_descriptor, backup_name = tempfile.mkstemp(
                        prefix=f".{log_path.name}.previous-",
                        dir=log_path.parent,
                    )
                    os.close(backup_descriptor)
                    backup_path = Path(backup_name)
                    backup_path.unlink()
                    os.link(
                        log_path,
                        backup_path,
                        follow_symlinks=False,
                    )
                    retained = backup_path.lstat()
                    current = log_path.lstat()
                    retained_state = (
                        retained.st_dev,
                        retained.st_ino,
                        retained.st_size,
                        retained.st_mtime_ns,
                    )
                    current_state = (
                        current.st_dev,
                        current.st_ino,
                        current.st_size,
                        current.st_mtime_ns,
                    )
                    if (
                        retained_state != previous_canonical_state
                        or current_state != previous_canonical_state
                    ):
                        failures.append(
                            "focused Swift existing canonical log changed while "
                            "being retained for publication"
                        )
        if not failures:
            published = True
            os.replace(temporary_path, log_path)
            published_snapshot, console_failures = (
                swift_focused_console_snapshot(
                    log_path=log_path,
                    expected_tests=expected_tests,
                    max_bytes=max_bytes,
                )
            )
            failures.extend(console_failures)
            failures.extend(log_context_failures(log_path))
            if (
                temporary_snapshot is not None
                and published_snapshot is not None
                and published_snapshot != temporary_snapshot
            ):
                failures.append(
                    "focused Swift canonical log readback must match the "
                    "validated temporary log bytes"
                )
        if published and failures:
            restore_previous_canonical()
        elif published and backup_path is not None:
            try:
                backup_path.unlink()
            except OSError as error:
                failures.append(
                    "focused Swift previous canonical log cleanup failed: "
                    f"{error}"
                )
                restore_previous_canonical()
    except SwiftRunnerSignal as interruption:
        terminate_process_group(interruption.signum)
        if published:
            restore_previous_canonical()
        interrupted_signal = interruption.signum
    except OSError as error:
        failures.append(f"focused Swift runner failed: {error}")
        terminate_process_group()
        if published:
            restore_previous_canonical()
    except BaseException:
        terminate_process_group()
        if published:
            restore_previous_canonical()
        raise
    finally:
        if (
            process is not None
            and process.stdout is not None
            and not process.stdout.closed
        ):
            process.stdout.close()
        if failures and failure_context is not None and temporary_path.exists():
            context = failure_context(temporary_path)
            if context is not None and context not in failures:
                failures.append(context)
        try:
            if temporary_path.exists():
                temporary_path.unlink()
            if backup_path is not None and backup_path.exists():
                backup_path.unlink()
        except OSError as error:
            failures.append(
                f"focused Swift runner temporary log cleanup failed: {error}"
            )
        restore_signal_handlers()
        restore_parent_signal_mask()
    if interrupted_signal is not None:
        os.kill(os.getpid(), interrupted_signal)
        raise SystemExit(128 + interrupted_signal)
    if failures:
        if status != 0 and status > 0:
            return status, failures
        return 1, failures
    return (0 if not failures else 1), failures


def run_swift_test_contract(
    *,
    command: tuple[str, ...],
    filter_pattern: str,
    expected_count: int,
    expected_manifest_sha256: str,
    marker_path: Path,
    log_path: Path,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    excluded_tests: tuple[str, ...] = (),
    timeout_seconds: float = SWIFT_FOCUSED_TEST_RUN_TIMEOUT_SECONDS,
    supplemental_log_failures: Callable[[Path], list[str]] | None = None,
    failure_context: Callable[[Path], str | None] | None = None,
    environment: dict[str, str] | None = None,
) -> tuple[int, list[str]]:
    marker_failures = swift_focused_test_run_marker_failures(
        marker_path=marker_path,
        log_path=log_path,
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
        require_log=False,
    )
    if marker_failures:
        return 1, marker_failures
    _, expected_tests, selection_failures = swift_focused_test_list_snapshot(
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
    )
    if expected_tests is None:
        return 1, selection_failures

    def validate_log_context(candidate_log_path: Path) -> list[str]:
        failures = swift_focused_test_run_marker_failures(
            marker_path=marker_path,
            log_path=candidate_log_path,
            test_list_path=test_list_path,
            filter_pattern=filter_pattern,
            expected_count=expected_count,
            expected_manifest_sha256=expected_manifest_sha256,
            excluded_tests=excluded_tests,
        )
        if supplemental_log_failures is not None:
            failures.extend(supplemental_log_failures(candidate_log_path))
        return failures

    return run_and_publish_swift_focused_log(
        command=command,
        cwd=ROOT,
        log_path=log_path,
        expected_tests=expected_tests,
        log_context_failures=validate_log_context,
        failure_context=failure_context,
        timeout_seconds=timeout_seconds,
        environment=environment,
    )


def run_swift_focused_tests(
    *,
    filter_pattern: str,
    marker_path: Path = SWIFT_FOCUSED_TEST_RUN_MARKER_PATH,
    log_path: Path = SWIFT_FOCUSED_TEST_LOG_PATH,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
) -> tuple[int, list[str]]:
    if filter_pattern != SWIFT_FILTER:
        return 1, ["focused Swift runner filter must match the exact contract"]
    return run_swift_test_contract(
        command=SWIFT_FOCUSED_RUN_COMMAND,
        filter_pattern=SWIFT_FILTER,
        expected_count=SWIFT_PRODUCT_TEST_COUNT,
        expected_manifest_sha256=SWIFT_PRODUCT_TEST_MANIFEST_SHA256,
        marker_path=marker_path,
        log_path=log_path,
        test_list_path=test_list_path,
    )


def run_g7_nonsecurity_swift_tests() -> tuple[int, list[str]]:
    failures = g7_nonsecurity_swift_selection_failures()
    environment, environment_failures = g7_nonsecurity_swift_environment()
    failures.extend(environment_failures)
    if failures or environment is None:
        return 1, failures
    for executable in (
        Path(G7_NONSECURITY_SWIFT_RUN_COMMAND[0]),
        Path(G7_NONSECURITY_SWIFT_RUN_COMMAND[3]),
    ):
        try:
            executable_status = executable.lstat()
        except OSError as error:
            failures.append(
                "G7 non-security Swift executable cannot be inspected: "
                f"{executable}: {error}"
            )
            continue
        if (
            stat.S_ISLNK(executable_status.st_mode)
            or not stat.S_ISREG(executable_status.st_mode)
            or not os.access(executable, os.X_OK)
        ):
            failures.append(
                "G7 non-security Swift executable must be a physical "
                f"executable file: {executable}"
            )
    if failures:
        return 1, failures
    return run_swift_test_contract(
        command=G7_NONSECURITY_SWIFT_RUN_COMMAND,
        filter_pattern=G7_NONSECURITY_SWIFT_FILTER,
        expected_count=G7_NONSECURITY_SWIFT_TEST_COUNT,
        expected_manifest_sha256=(
            G7_NONSECURITY_SWIFT_TEST_MANIFEST_SHA256
        ),
        marker_path=G7_NONSECURITY_SWIFT_RUN_MARKER_PATH,
        log_path=G7_NONSECURITY_SWIFT_LOG_PATH,
        excluded_tests=G7_NONSECURITY_SWIFT_LIVE_TESTS,
        environment=environment,
    )


def run_document_ingestion_asan_tests() -> tuple[int, list[str]]:
    return run_swift_test_contract(
        command=DOCUMENT_INGESTION_ASAN_RUN_COMMAND,
        filter_pattern=DOCUMENT_INGESTION_ASAN_FILTER,
        expected_count=DOCUMENT_INGESTION_ASAN_TEST_COUNT,
        expected_manifest_sha256=(
            DOCUMENT_INGESTION_ASAN_TEST_MANIFEST_SHA256
        ),
        marker_path=DOCUMENT_INGESTION_ASAN_RUN_MARKER_PATH,
        log_path=DOCUMENT_INGESTION_ASAN_LOG_PATH,
        timeout_seconds=DOCUMENT_INGESTION_ASAN_RUN_TIMEOUT_SECONDS,
    )


def run_document_ingestion_mutation_tests() -> tuple[int, list[str]]:
    def mutation_log_failures(log_path: Path) -> list[str]:
        _, failures = document_ingestion_mutation_console_snapshot(log_path)
        return failures

    return run_swift_test_contract(
        command=DOCUMENT_INGESTION_MUTATION_RUN_COMMAND,
        filter_pattern=DOCUMENT_INGESTION_MUTATION_FILTER,
        expected_count=DOCUMENT_INGESTION_MUTATION_TEST_COUNT,
        expected_manifest_sha256=(
            DOCUMENT_INGESTION_MUTATION_TEST_MANIFEST_SHA256
        ),
        marker_path=DOCUMENT_INGESTION_MUTATION_RUN_MARKER_PATH,
        log_path=DOCUMENT_INGESTION_MUTATION_LOG_PATH,
        timeout_seconds=DOCUMENT_INGESTION_MUTATION_RUN_TIMEOUT_SECONDS,
        supplemental_log_failures=mutation_log_failures,
        failure_context=last_document_ingestion_mutation_marker,
    )


def swift_focused_test_binding_payload(
    *,
    marker_path: Path = SWIFT_FOCUSED_TEST_RUN_MARKER_PATH,
    log_path: Path = SWIFT_FOCUSED_TEST_LOG_PATH,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
    exact_files: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_EXACT_FILES,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
    supplemental_console_key: str | None = None,
    supplemental_console_snapshot: (
        Callable[[Path], tuple[dict[str, object] | None, list[str]]] | None
    ) = None,
) -> tuple[dict[str, object] | None, list[str]]:
    source_snapshot, source_failures = swift_focused_source_snapshot(
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
    )
    list_snapshot, expected_tests, list_failures = (
        swift_focused_test_list_snapshot(
            test_list_path=test_list_path,
            filter_pattern=filter_pattern,
            expected_count=expected_count,
            expected_manifest_sha256=expected_manifest_sha256,
            excluded_tests=excluded_tests,
        )
    )
    if expected_tests is None:
        console_snapshot = None
        console_failures: list[str] = []
    else:
        console_snapshot, console_failures = swift_focused_console_snapshot(
            log_path=log_path,
            expected_tests=expected_tests,
        )
    supplemental_snapshot: dict[str, object] | None = None
    supplemental_failures: list[str] = []
    if (supplemental_console_key is None) != (
        supplemental_console_snapshot is None
    ):
        supplemental_failures.append(
            "focused Swift supplemental console key and parser must be "
            "configured together"
        )
    elif supplemental_console_snapshot is not None and expected_tests is not None:
        supplemental_snapshot, supplemental_failures = (
            supplemental_console_snapshot(log_path)
        )
    try:
        marker_bytes = marker_path.read_bytes()
    except OSError as error:
        marker_snapshot = None
        marker_failures = [
            f"{path_label(marker_path)} cannot be bound: {error}"
        ]
    else:
        marker_snapshot = {
            "bytes": len(marker_bytes),
            "sha256": hashlib.sha256(marker_bytes).hexdigest(),
        }
        marker_failures = []
    failures = (
        source_failures
        + list_failures
        + console_failures
        + supplemental_failures
        + marker_failures
    )
    if (
        failures
        or source_snapshot is None
        or list_snapshot is None
        or console_snapshot is None
        or marker_snapshot is None
        or (
            supplemental_console_snapshot is not None
            and supplemental_snapshot is None
        )
    ):
        return None, failures
    payload: dict[str, object] = {
        "contract": SWIFT_FOCUSED_TEST_BINDING_CONTRACT,
        "result": console_snapshot,
        "runMarker": marker_snapshot,
        "sourceInputs": source_snapshot,
        "testList": list_snapshot,
    }
    if supplemental_console_key is not None and supplemental_snapshot is not None:
        payload[supplemental_console_key] = supplemental_snapshot
    return payload, []


def swift_focused_test_binding_failures(
    *,
    binding_path: Path = SWIFT_FOCUSED_TEST_BINDING_PATH,
    marker_path: Path = SWIFT_FOCUSED_TEST_RUN_MARKER_PATH,
    log_path: Path = SWIFT_FOCUSED_TEST_LOG_PATH,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
    exact_files: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_EXACT_FILES,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
    supplemental_console_key: str | None = None,
    supplemental_console_snapshot: (
        Callable[[Path], tuple[dict[str, object] | None, list[str]]] | None
    ) = None,
) -> list[str]:
    failures = swift_focused_test_run_marker_failures(
        marker_path=marker_path,
        log_path=log_path,
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
    )
    expected_payload, payload_failures = swift_focused_test_binding_payload(
        marker_path=marker_path,
        log_path=log_path,
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
        supplemental_console_key=supplemental_console_key,
        supplemental_console_snapshot=supplemental_console_snapshot,
    )
    failures.extend(payload_failures)
    if expected_payload is None:
        return failures
    try:
        binding_bytes = binding_path.read_bytes()
        json.loads(binding_bytes)
        binding_mtime_ns = binding_path.stat().st_mtime_ns
        log_mtime_ns = log_path.stat().st_mtime_ns
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        failures.append(
            f"{path_label(binding_path)} cannot be read: {error}"
        )
        return failures
    if binding_bytes != canonical_json_bytes(expected_payload):
        failures.append(
            f"{path_label(binding_path)} must exactly bind the current "
            "focused Swift source, list, marker, and console bytes"
        )
    if binding_mtime_ns <= log_mtime_ns:
        failures.append(
            f"{path_label(binding_path)} must postdate the focused Swift log"
        )
    if (
        binding_mtime_ns
        > time.time_ns() + SWIFT_FOCUSED_TEST_FUTURE_MTIME_TOLERANCE_NS
    ):
        failures.append(
            f"{path_label(binding_path)} timestamp is implausibly in the future"
        )
    return failures


def write_swift_focused_test_binding(
    *,
    binding_path: Path = SWIFT_FOCUSED_TEST_BINDING_PATH,
    marker_path: Path = SWIFT_FOCUSED_TEST_RUN_MARKER_PATH,
    log_path: Path = SWIFT_FOCUSED_TEST_LOG_PATH,
    test_list_path: Path = SWIFT_TEST_LIST_PATH,
    filter_pattern: str = SWIFT_FILTER,
    expected_count: int = SWIFT_PRODUCT_TEST_COUNT,
    expected_manifest_sha256: str = (
        SWIFT_PRODUCT_TEST_MANIFEST_SHA256
    ),
    excluded_tests: tuple[str, ...] = (),
    exact_files: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_EXACT_FILES,
    source_roots: tuple[Path, ...] = SWIFT_FOCUSED_RESULT_SOURCE_ROOTS,
    package_path: Path = SWIFT_FOCUSED_PACKAGE_PATH,
    expected_targets: tuple[tuple[str, str, str], ...] = (
        SWIFT_FOCUSED_PACKAGE_TARGETS
    ),
    observed_targets: Optional[tuple[tuple[str, str, str], ...]] = None,
    supplemental_console_key: str | None = None,
    supplemental_console_snapshot: (
        Callable[[Path], tuple[dict[str, object] | None, list[str]]] | None
    ) = None,
) -> list[str]:
    failures = swift_focused_test_run_marker_failures(
        marker_path=marker_path,
        log_path=log_path,
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
    )
    if failures:
        return failures
    payload, payload_failures = swift_focused_test_binding_payload(
        marker_path=marker_path,
        log_path=log_path,
        test_list_path=test_list_path,
        filter_pattern=filter_pattern,
        expected_count=expected_count,
        expected_manifest_sha256=expected_manifest_sha256,
        excluded_tests=excluded_tests,
        exact_files=exact_files,
        source_roots=source_roots,
        package_path=package_path,
        expected_targets=expected_targets,
        observed_targets=observed_targets,
        supplemental_console_key=supplemental_console_key,
        supplemental_console_snapshot=supplemental_console_snapshot,
    )
    failures.extend(payload_failures)
    if payload is None:
        return failures
    failures.extend(
        write_canonical_json_payload(
            binding_path,
            payload,
            label="focused Swift result binding",
        )
    )
    if not failures:
        failures.extend(
            swift_focused_test_binding_failures(
                binding_path=binding_path,
                marker_path=marker_path,
                log_path=log_path,
                test_list_path=test_list_path,
                filter_pattern=filter_pattern,
                expected_count=expected_count,
                expected_manifest_sha256=expected_manifest_sha256,
                excluded_tests=excluded_tests,
                exact_files=exact_files,
                source_roots=source_roots,
                package_path=package_path,
                expected_targets=expected_targets,
                observed_targets=observed_targets,
                supplemental_console_key=supplemental_console_key,
                supplemental_console_snapshot=supplemental_console_snapshot,
            )
        )
    return failures


def swift_focused_result_self_test() -> list[str]:
    failures: list[str] = []
    fixture_filter = r"FixtureSuite/"
    fixture_tests = (
        "FixtureTests.FixtureSuite/testOne",
        "FixtureTests.FixtureSuite/testTwo",
    )
    fixture_manifest = swift_test_selection_manifest_sha256(fixture_tests)

    def console_text(
        *,
        tests: tuple[str, ...] = fixture_tests,
        final_count: int = 2,
    ) -> str:
        lines: list[str] = []
        for identity in tests:
            class_name, method_name = identity.split("/", 1)
            lines.extend(
                (
                    f"Test Case '-[{class_name} {method_name}]' started.",
                    (
                        f"Test Case '-[{class_name} {method_name}]' passed "
                        "(0.001 seconds)."
                    ),
                )
            )
        lines.append(
            f"\t Executed {final_count} tests, with 0 failures "
            "(0 unexpected) in 0.002 (0.002) seconds"
        )
        return "\n".join(lines) + "\n"

    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-swift-focused-result-",
        ) as temporary:
            root = Path(temporary)
            source_exact = root / "Package.swift"
            fixture_targets = (
                ("regular", "Fixture", "Component/Sources"),
            )
            source_root = root / fixture_targets[0][2]
            source_root.mkdir(parents=True)
            source_file = source_root / "Fixture.swift"
            fixture_package = """// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Fixture",
    targets: [
        .target(
            name: "Fixture",
            path: "Component/Sources"
        )
    ]
)
"""
            source_exact.write_text(fixture_package, encoding="utf-8")
            source_file.write_text("struct Fixture {}\n", encoding="utf-8")
            ambient_build_file = root / ".build/ambient.txt"
            ambient_component_build_file = root / "Component/build/ambient.txt"
            ambient_build_file.parent.mkdir()
            ambient_component_build_file.parent.mkdir()
            ambient_build_file.write_text("ambient\n", encoding="utf-8")
            ambient_component_build_file.write_text(
                "ambient\n",
                encoding="utf-8",
            )
            test_list_path = root / "tests.txt"
            marker_path = root / "marker.json"
            log_path = root / "result.log"
            binding_path = root / "binding.json"
            test_list_path.write_text(
                "\n".join(
                    fixture_tests
                    + ("FixtureTests.OtherSuite/testUnselected",)
                )
                + "\n",
                encoding="utf-8",
            )
            current_ns = time.time_ns()
            os.utime(
                test_list_path,
                ns=(current_ns - 4_000_000_000,) * 2,
            )

            package_contract_failures = (
                swift_focused_package_source_path_failures(
                    package_path=source_exact,
                    expected_targets=fixture_targets,
                    observed_targets=fixture_targets,
                    source_roots=(source_root,),
                )
            )
            if package_contract_failures:
                failures.append(
                    "valid focused Swift package-path fixture was rejected: "
                    + "; ".join(package_contract_failures)
                )
                return failures
            source_snapshot, source_snapshot_failures = (
                swift_focused_source_snapshot(
                    exact_files=(source_exact,),
                    source_roots=(source_root,),
                    package_path=source_exact,
                    expected_targets=fixture_targets,
                    observed_targets=fixture_targets,
                )
            )
            if source_snapshot_failures or source_snapshot is None:
                failures.append(
                    "valid focused Swift explicit-root snapshot was rejected: "
                    + "; ".join(source_snapshot_failures)
                )
                return failures
            if source_snapshot.get("count") != 2:
                failures.append(
                    "focused Swift explicit-root snapshot included ambient "
                    "sibling build outputs"
                )

            compact_test_root = root / "Component/Tests"
            compact_test_root.mkdir()
            (compact_test_root / "FixtureTests.swift").write_text(
                "// fixture test\n",
                encoding="utf-8",
            )
            extra_target_package = fixture_package.replace(
                "        )\n    ]",
                "        ), .testTarget("
                "name: \"FixtureTests\", dependencies: [\"Fixture\"], "
                "path: \"Component/Tests\")\n"
                "    ]",
                1,
            )
            source_exact.write_text(extra_target_package, encoding="utf-8")
            if not swift_focused_package_source_path_failures(
                package_path=source_exact,
                expected_targets=fixture_targets,
                source_roots=(source_root,),
            ):
                failures.append(
                    "focused Swift compact added target/path mutation was not "
                    "rejected"
                )
            source_exact.write_text(fixture_package, encoding="utf-8")

            implicit_test_root = root / "Tests/FixtureTests"
            implicit_test_root.mkdir(parents=True)
            (implicit_test_root / "FixtureTests.swift").write_text(
                "// implicit fixture test\n",
                encoding="utf-8",
            )
            no_path_target_package = fixture_package.replace(
                "        )\n    ]",
                "        ), .testTarget("
                "name: \"FixtureTests\", dependencies: [\"Fixture\"])\n"
                "    ]",
                1,
            )
            source_exact.write_text(no_path_target_package, encoding="utf-8")
            if not swift_focused_package_source_path_failures(
                package_path=source_exact,
                expected_targets=fixture_targets,
                source_roots=(source_root,),
            ):
                failures.append(
                    "focused Swift implicit-path target mutation was not rejected"
                )
            source_exact.write_text(fixture_package, encoding="utf-8")

            nested_build_file = source_root / "build/generated.swift"
            nested_build_file.parent.mkdir()
            nested_build_file.write_text("generated\n", encoding="utf-8")
            if not any(
                "must not contain generated build paths" in failure
                for failure in swift_focused_package_source_path_failures(
                    package_path=source_exact,
                    expected_targets=fixture_targets,
                    observed_targets=fixture_targets,
                    source_roots=(source_root,),
                )
            ):
                failures.append(
                    "focused Swift nested build-output mutation was not rejected"
                )
            nested_build_file.unlink()
            nested_build_file.parent.rmdir()

            marker_failures = write_swift_focused_test_run_marker(
                marker_path=marker_path,
                test_list_path=test_list_path,
                filter_pattern=fixture_filter,
                expected_count=2,
                expected_manifest_sha256=fixture_manifest,
                exact_files=(source_exact,),
                source_roots=(source_root,),
                package_path=source_exact,
                expected_targets=fixture_targets,
                observed_targets=fixture_targets,
            )
            if marker_failures:
                failures.append(
                    "valid focused Swift marker fixture was rejected: "
                    + "; ".join(marker_failures)
                )
                return failures
            os.utime(
                marker_path,
                ns=(current_ns - 3_000_000_000,) * 2,
            )
            valid_console = console_text()
            sentinel_bytes = b"prior canonical focused Swift log\n"
            log_path.write_bytes(sentinel_bytes)
            os.utime(
                log_path,
                ns=(current_ns - 2_000_000_000,) * 2,
            )

            def canonical_log_state() -> tuple[bytes, int, int]:
                log_stat = log_path.stat()
                return (
                    log_path.read_bytes(),
                    log_stat.st_ino,
                    log_stat.st_mtime_ns,
                )

            def fixture_log_context_failures(
                candidate_log_path: Path,
            ) -> list[str]:
                return swift_focused_test_run_marker_failures(
                    marker_path=marker_path,
                    log_path=candidate_log_path,
                    test_list_path=test_list_path,
                    filter_pattern=fixture_filter,
                    expected_count=2,
                    expected_manifest_sha256=fixture_manifest,
                    exact_files=(source_exact,),
                    source_roots=(source_root,),
                    package_path=source_exact,
                    expected_targets=fixture_targets,
                    observed_targets=fixture_targets,
                )

            def fixture_command(
                output_text: str,
                exit_status: int,
            ) -> tuple[str, ...]:
                return (
                    sys.executable,
                    "-c",
                    "import sys\n"
                    f"sys.stdout.write({output_text!r})\n"
                    "sys.stdout.flush()\n"
                    f"raise SystemExit({exit_status})\n",
                )

            def require_preserved_canonical(
                label: str,
                expected_state: tuple[bytes, int, int],
            ) -> None:
                if canonical_log_state() != expected_state:
                    failures.append(
                        f"focused Swift {label} runner replaced the canonical "
                        "log"
                    )

            sentinel_state = canonical_log_state()
            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=fixture_command(valid_console, 7),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=fixture_log_context_failures,
                )
            )
            if runner_status != 7 or not runner_failures:
                failures.append(
                    "focused Swift nonzero valid-console runner was not rejected"
                )
            require_preserved_canonical("nonzero", sentinel_state)

            invalid_console = valid_console.replace(
                "Test Case '-[FixtureTests.FixtureSuite testTwo]' "
                "passed (0.001 seconds).\n",
                "",
                1,
            )
            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=fixture_command(invalid_console, 0),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=fixture_log_context_failures,
                )
            )
            if runner_status != 1 or not runner_failures:
                failures.append(
                    "focused Swift zero-exit invalid-console runner was not "
                    "rejected"
                )
            require_preserved_canonical("invalid-console", sentinel_state)

            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=fixture_command(valid_console, 0),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=fixture_log_context_failures,
                    max_bytes=8,
                )
            )
            if runner_status != 1 or not runner_failures:
                failures.append(
                    "focused Swift oversized-console runner was not rejected"
                )
            require_preserved_canonical("oversized-console", sentinel_state)

            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=fixture_command(valid_console, 0),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=(
                        lambda _candidate: ["fixture pre-publication drift"]
                    ),
                )
            )
            if runner_status != 1 or not runner_failures:
                failures.append(
                    "focused Swift pre-publication drift was not rejected"
                )
            require_preserved_canonical("context-drift", sentinel_state)

            late_context_calls: list[tuple[Path, bytes, int]] = []

            def late_context_drift(candidate: Path) -> list[str]:
                candidate_stat = candidate.stat()
                late_context_calls.append(
                    (candidate, candidate.read_bytes(), candidate_stat.st_ino)
                )
                if len(late_context_calls) == 1:
                    return []
                return ["fixture post-publication drift"]

            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=fixture_command(valid_console, 0),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=late_context_drift,
                )
            )
            if (
                runner_status != 1
                or not runner_failures
                or len(late_context_calls) != 2
                or late_context_calls[0][0] == log_path
                or late_context_calls[1][0] != log_path
                or late_context_calls[0][1] != valid_console.encode("utf-8")
                or late_context_calls[1][1] != valid_console.encode("utf-8")
                or late_context_calls[0][2] != late_context_calls[1][2]
                or late_context_calls[1][2] == sentinel_state[1]
            ):
                failures.append(
                    "focused Swift post-publication drift phase was not "
                    "rejected and restored"
                )
            require_preserved_canonical("late-context-drift", sentinel_state)

            post_readback_calls: list[Path] = []

            def corrupt_after_temporary_validation(
                candidate: Path,
            ) -> list[str]:
                post_readback_calls.append(candidate)
                if len(post_readback_calls) == 1:
                    candidate.write_bytes(b"corrupted after validation\n")
                return []

            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=fixture_command(valid_console, 0),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=corrupt_after_temporary_validation,
                )
            )
            if (
                runner_status != 1
                or not runner_failures
                or len(post_readback_calls) != 2
                or post_readback_calls[0] == log_path
                or post_readback_calls[1] != log_path
            ):
                failures.append(
                    "focused Swift post-publication parser failure was not "
                    "rejected and restored"
                )
            require_preserved_canonical("post-readback-failure", sentinel_state)

            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=(str(root / "missing-executable"),),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=fixture_log_context_failures,
                )
            )
            if runner_status != 1 or not runner_failures:
                failures.append(
                    "focused Swift process-launch failure was not rejected"
                )
            require_preserved_canonical("process-launch-failure", sentinel_state)
            if tuple(root.glob(f".{log_path.name}.tmp-*")):
                failures.append(
                    "focused Swift failed runners retained temporary logs"
                )
            if tuple(root.glob(f".{log_path.name}.previous-*")):
                failures.append(
                    "focused Swift failed runners retained canonical backups"
                )

            runner_status, runner_failures = (
                run_and_publish_swift_focused_log(
                    command=fixture_command(valid_console, 0),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=fixture_tests,
                    log_context_failures=fixture_log_context_failures,
                )
            )
            if runner_status != 0 or runner_failures:
                failures.append(
                    "valid focused Swift runner fixture was rejected: "
                    + "; ".join(runner_failures)
                )
            elif log_path.read_bytes() != valid_console.encode("utf-8"):
                failures.append(
                    "valid focused Swift runner did not publish exact console "
                    "bytes"
                )

            _, valid_console_failures = swift_focused_console_snapshot(
                log_path=log_path,
                expected_tests=fixture_tests,
            )
            if valid_console_failures:
                failures.append(
                    "valid focused Swift console fixture was rejected: "
                    + "; ".join(valid_console_failures)
                )

            console_mutations = (
                (
                    "missing pass",
                    valid_console.replace(
                        "Test Case '-[FixtureTests.FixtureSuite testTwo]' "
                        "passed (0.001 seconds).\n",
                        "",
                        1,
                    ),
                ),
                (
                    "duplicate pass",
                    valid_console.replace(
                        "Test Case '-[FixtureTests.FixtureSuite testTwo]' "
                        "passed (0.001 seconds).\n",
                        "Test Case '-[FixtureTests.FixtureSuite testTwo]' "
                        "passed (0.001 seconds).\n"
                        "Test Case '-[FixtureTests.FixtureSuite testTwo]' "
                        "passed (0.001 seconds).\n",
                        1,
                    ),
                ),
                (
                    "same-count identity substitution",
                    valid_console.replace("testTwo", "testSubstitute"),
                ),
                (
                    "skipped testcase",
                    valid_console.replace(
                        "testTwo]' passed",
                        "testTwo]' skipped",
                        1,
                    ),
                ),
                (
                    "failed testcase",
                    valid_console.replace(
                        "testTwo]' passed",
                        "testTwo]' failed",
                        1,
                    ),
                ),
                (
                    "forged final summary",
                    valid_console.replace("Executed 2 tests", "Executed 1 test"),
                ),
                (
                    "earlier failing summary",
                    valid_console.replace(
                        valid_console.splitlines()[-1] + "\n",
                        "\t Executed 1 test, with 1 failure (1 unexpected) "
                        "in 0.001 (0.001) seconds\n"
                        + valid_console.splitlines()[-1]
                        + "\n",
                        1,
                    ),
                ),
                (
                    "summary before testcase events",
                    valid_console.splitlines()[-1]
                    + "\n"
                    + "\n".join(valid_console.splitlines()[:-1])
                    + "\n",
                ),
                ("missing final LF", valid_console.rstrip("\n")),
            )
            for label, mutated in console_mutations:
                log_path.write_text(mutated, encoding="utf-8")
                _, mutation_failures = swift_focused_console_snapshot(
                    log_path=log_path,
                    expected_tests=fixture_tests,
                )
                if not mutation_failures:
                    failures.append(
                        f"focused Swift console {label} mutation was not rejected"
                    )
            log_path.write_text(valid_console, encoding="utf-8")
            os.utime(
                log_path,
                ns=(current_ns - 2_000_000_000,) * 2,
            )

            binding_failures = write_swift_focused_test_binding(
                binding_path=binding_path,
                marker_path=marker_path,
                log_path=log_path,
                test_list_path=test_list_path,
                filter_pattern=fixture_filter,
                expected_count=2,
                expected_manifest_sha256=fixture_manifest,
                exact_files=(source_exact,),
                source_roots=(source_root,),
                package_path=source_exact,
                expected_targets=fixture_targets,
                observed_targets=fixture_targets,
            )
            if binding_failures:
                failures.append(
                    "valid focused Swift binding fixture was rejected: "
                    + "; ".join(binding_failures)
                )
                return failures

            original_source_mtime_ns = source_file.stat().st_mtime_ns
            source_file.write_text("struct ChangedFixture {}\n", encoding="utf-8")
            os.utime(
                source_file,
                ns=(original_source_mtime_ns,) * 2,
            )
            source_drift_failures = swift_focused_test_binding_failures(
                binding_path=binding_path,
                marker_path=marker_path,
                log_path=log_path,
                test_list_path=test_list_path,
                filter_pattern=fixture_filter,
                expected_count=2,
                expected_manifest_sha256=fixture_manifest,
                exact_files=(source_exact,),
                source_roots=(source_root,),
                package_path=source_exact,
                expected_targets=fixture_targets,
                observed_targets=fixture_targets,
            )
            if not any(
                "must exactly bind the focused Swift source" in failure
                for failure in source_drift_failures
            ):
                failures.append(
                    "mtime-preserved focused Swift source drift was not rejected"
                )
            source_file.write_text("struct Fixture {}\n", encoding="utf-8")
            os.utime(
                source_file,
                ns=(original_source_mtime_ns,) * 2,
            )

            original_log_bytes = log_path.read_bytes()
            original_log_mtime_ns = log_path.stat().st_mtime_ns
            log_path.write_bytes(original_log_bytes + b"post-run mutation\n")
            os.utime(log_path, ns=(original_log_mtime_ns,) * 2)
            log_drift_failures = swift_focused_test_binding_failures(
                binding_path=binding_path,
                marker_path=marker_path,
                log_path=log_path,
                test_list_path=test_list_path,
                filter_pattern=fixture_filter,
                expected_count=2,
                expected_manifest_sha256=fixture_manifest,
                exact_files=(source_exact,),
                source_roots=(source_root,),
                package_path=source_exact,
                expected_targets=fixture_targets,
                observed_targets=fixture_targets,
            )
            if not any(
                "must exactly bind the current focused Swift" in failure
                for failure in log_drift_failures
            ):
                failures.append("focused Swift log byte drift was not rejected")
            log_path.write_bytes(original_log_bytes)
            os.utime(log_path, ns=(original_log_mtime_ns,) * 2)

            marker_mtime_ns = marker_path.stat().st_mtime_ns
            os.utime(log_path, ns=(marker_mtime_ns,) * 2)
            stale_log_failures = swift_focused_test_binding_failures(
                binding_path=binding_path,
                marker_path=marker_path,
                log_path=log_path,
                test_list_path=test_list_path,
                filter_pattern=fixture_filter,
                expected_count=2,
                expected_manifest_sha256=fixture_manifest,
                exact_files=(source_exact,),
                source_roots=(source_root,),
                package_path=source_exact,
                expected_targets=fixture_targets,
                observed_targets=fixture_targets,
            )
            if not any(
                "must be generated after" in failure
                for failure in stale_log_failures
            ):
                failures.append("stale focused Swift log was not rejected")
            os.utime(log_path, ns=(original_log_mtime_ns,) * 2)

            os.utime(binding_path, ns=(original_log_mtime_ns,) * 2)
            stale_binding_failures = swift_focused_test_binding_failures(
                binding_path=binding_path,
                marker_path=marker_path,
                log_path=log_path,
                test_list_path=test_list_path,
                filter_pattern=fixture_filter,
                expected_count=2,
                expected_manifest_sha256=fixture_manifest,
                exact_files=(source_exact,),
                source_roots=(source_root,),
                package_path=source_exact,
                expected_targets=fixture_targets,
                observed_targets=fixture_targets,
            )
            if not any(
                "must postdate the focused Swift log" in failure
                for failure in stale_binding_failures
            ):
                failures.append("stale focused Swift binding was not rejected")
    except OSError as error:
        failures.append(f"focused Swift result fixture failed: {error}")
    return failures


def swift_runner_timeout_self_test() -> list[str]:
    descendant_pid: int | None = None
    lingering_pid: int | None = None
    original_handlers = tuple(
        signal.getsignal(signum)
        for signum in (signal.SIGTERM, signal.SIGINT)
    )
    original_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-swift-runner-timeout-",
        ) as temporary:
            root = Path(temporary)
            started_at = time.monotonic()
            status, observed_failures = run_and_publish_swift_focused_log(
                command=(
                    sys.executable,
                    "-B",
                    "-c",
                    "import time; time.sleep(60)",
                ),
                cwd=ROOT,
                log_path=root / "timeout.log",
                expected_tests=(),
                log_context_failures=lambda _: [],
                timeout_seconds=0.1,
                termination_grace_seconds=0.05,
            )
            elapsed = time.monotonic() - started_at

            descendant_pid_path = root / "descendant.pid"
            descendant_script = (
                "import os, signal, subprocess, sys, time\n"
                "child = subprocess.Popen((sys.executable, '-B', '-c', "
                "'import signal,time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "time.sleep(60)'))\n"
                "with open(sys.argv[1], 'w', encoding='ascii') as output:\n"
                "    output.write(str(child.pid))\n"
                "    output.flush()\n"
                "    os.fsync(output.fileno())\n"
                "time.sleep(60)\n"
            )
            descendant_started_at = time.monotonic()
            descendant_status, descendant_failures = (
                run_and_publish_swift_focused_log(
                    command=(
                        sys.executable,
                        "-B",
                        "-c",
                        descendant_script,
                        str(descendant_pid_path),
                    ),
                    cwd=ROOT,
                    log_path=root / "descendant-timeout.log",
                    expected_tests=(),
                    log_context_failures=lambda _: [],
                    timeout_seconds=0.25,
                    termination_grace_seconds=0.05,
                )
            )
            descendant_elapsed = time.monotonic() - descendant_started_at
            if descendant_pid_path.exists():
                descendant_pid = int(
                    descendant_pid_path.read_text(encoding="ascii")
                )

            lingering_pid_path = root / "lingering.pid"
            lingering_script = (
                "import os, signal, subprocess, sys\n"
                "child = subprocess.Popen((sys.executable, '-B', '-c', "
                "'import signal,time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "time.sleep(60)'), stdin=subprocess.DEVNULL, "
                "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "with open(sys.argv[1], 'w', encoding='ascii') as output:\n"
                "    output.write(str(child.pid))\n"
                "    output.flush()\n"
                "    os.fsync(output.fileno())\n"
            )
            lingering_started_at = time.monotonic()
            lingering_status, lingering_failures = (
                run_and_publish_swift_focused_log(
                    command=(
                        sys.executable,
                        "-B",
                        "-c",
                        lingering_script,
                        str(lingering_pid_path),
                    ),
                    cwd=ROOT,
                    log_path=root / "lingering-descendant.log",
                    expected_tests=(),
                    log_context_failures=lambda _: [],
                    timeout_seconds=5,
                    termination_grace_seconds=0.05,
                )
            )
            lingering_elapsed = time.monotonic() - lingering_started_at
            if lingering_pid_path.exists():
                lingering_pid = int(
                    lingering_pid_path.read_text(encoding="ascii")
                )
    except OSError as error:
        return [f"focused Swift timeout self-test failed: {error}"]

    failures: list[str] = []
    if status == 0:
        failures.append("focused Swift timeout self-test unexpectedly passed")
    if not any("timed out after" in failure for failure in observed_failures):
        failures.append("focused Swift timeout was not reported")
    if elapsed >= 5:
        failures.append(
            "focused Swift timeout did not terminate the process promptly"
        )
    if descendant_status == 0:
        failures.append(
            "focused Swift descendant timeout self-test unexpectedly passed"
        )
    if not any("timed out after" in failure for failure in descendant_failures):
        failures.append("focused Swift descendant timeout was not reported")
    if descendant_elapsed >= 7:
        failures.append(
            "focused Swift descendant timeout did not terminate promptly"
        )
    if descendant_pid is None:
        failures.append(
            "focused Swift descendant timeout did not publish its PID fixture"
        )
    else:
        descendant_alive = True
        deadline = time.monotonic() + 1
        while descendant_alive and time.monotonic() < deadline:
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                descendant_alive = False
            else:
                time.sleep(0.01)
        if descendant_alive:
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            failures.append(
                "focused Swift timeout retained a descendant process"
            )
    if lingering_status == 0:
        failures.append(
            "focused Swift lingering-descendant self-test unexpectedly passed"
        )
    if not any(
        "left a descendant process group" in failure
        for failure in lingering_failures
    ):
        failures.append(
            "focused Swift lingering descendant was not reported"
        )
    if lingering_elapsed >= 4:
        failures.append(
            "focused Swift lingering descendant was not terminated promptly"
        )
    if lingering_pid is None:
        failures.append(
            "focused Swift lingering-descendant fixture did not publish its PID"
        )
    else:
        lingering_alive = True
        deadline = time.monotonic() + 1
        while lingering_alive and time.monotonic() < deadline:
            try:
                os.kill(lingering_pid, 0)
            except ProcessLookupError:
                lingering_alive = False
            else:
                time.sleep(0.01)
        if lingering_alive:
            try:
                os.kill(lingering_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            failures.append(
                "focused Swift lingering-descendant cleanup retained the child"
            )
    current_handlers = tuple(
        signal.getsignal(signum)
        for signum in (signal.SIGTERM, signal.SIGINT)
    )
    current_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
    if current_handlers != original_handlers:
        failures.append(
            "focused Swift timeout paths did not restore signal handlers"
        )
    if current_mask != original_mask:
        failures.append(
            "focused Swift timeout paths did not restore the signal mask"
        )
    return failures


def swift_runner_signal_self_test() -> list[str]:
    failures: list[str] = []

    def read_pid(path: Path) -> int | None:
        try:
            value = int(path.read_text(encoding="ascii"))
        except (OSError, UnicodeError, ValueError):
            return None
        return value if value > 1 else None

    def process_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def kill_fixture_group(group_id: int | None) -> None:
        if group_id is None or group_id == os.getpgrp():
            return
        try:
            os.killpg(group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass

    inner_script = r"""
import os
import signal
import subprocess
import sys
import time

descendant_code = r'''
import os
import signal
import sys
import time

signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGINT, signal.SIG_IGN)
with open(sys.argv[1], "xb") as output:
    output.write(b"ready\n")
    output.flush()
    os.fsync(output.fileno())
time.sleep(0.5)
with open(sys.argv[2], "xb") as output:
    output.write(b"escaped\n")
    output.flush()
    os.fsync(output.fileno())
time.sleep(60)
'''

child = subprocess.Popen(
    (sys.executable, "-B", "-c", descendant_code, sys.argv[3], sys.argv[4])
)
for path, value in ((sys.argv[1], os.getpid()), (sys.argv[2], child.pid)):
    with open(path, "x", encoding="ascii") as output:
        output.write(str(value))
        output.flush()
        os.fsync(output.fileno())
time.sleep(60)
"""
    driver_script = r"""
import importlib.util
import os
import pathlib
import signal
import sys

module_path = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "aetherlink_check_product_ci_signal_fixture",
    module_path,
)
if spec is None or spec.loader is None:
    raise SystemExit(91)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
race_signal = int(sys.argv[9])
if race_signal:
    original_popen = module.subprocess.Popen

    def spawn_then_signal(*args, **kwargs):
        spawned = original_popen(*args, **kwargs)
        with open(sys.argv[10], "x", encoding="ascii") as output:
            output.write(str(spawned.pid))
            output.flush()
            os.fsync(output.fileno())
        os.kill(os.getpid(), race_signal)
        return spawned

    module.subprocess.Popen = spawn_then_signal
status, _ = module.run_and_publish_swift_focused_log(
    command=(
        sys.executable,
        "-B",
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
    ),
    cwd=pathlib.Path(sys.argv[7]),
    log_path=pathlib.Path(sys.argv[8]),
    expected_tests=(),
    log_context_failures=lambda _: [],
    timeout_seconds=30,
    termination_grace_seconds=0.05,
)
raise SystemExit(status)
"""

    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-swift-runner-signal-",
        ) as temporary:
            root = Path(temporary)
            inner_path = root / "inner.py"
            driver_path = root / "driver.py"
            inner_path.write_text(inner_script, encoding="utf-8")
            driver_path.write_text(driver_script, encoding="utf-8")

            for label, signum in (
                ("SIGTERM", signal.SIGTERM),
                ("SIGINT", signal.SIGINT),
            ):
                case_root = root / label.lower()
                case_root.mkdir()
                leader_pid_path = case_root / "leader.pid"
                descendant_pid_path = case_root / "descendant.pid"
                ready_path = case_root / "ready"
                escaped_path = case_root / "escaped"
                log_path = case_root / "result.log"
                sentinel_bytes = f"prior canonical {label} log\n".encode(
                    "ascii"
                )
                log_path.write_bytes(sentinel_bytes)
                driver: subprocess.Popen[bytes] | None = None
                leader_pid: int | None = None
                descendant_pid: int | None = None
                try:
                    driver = subprocess.Popen(
                        (
                            sys.executable,
                            "-B",
                            str(driver_path),
                            str(Path(__file__).resolve()),
                            str(inner_path),
                            str(leader_pid_path),
                            str(descendant_pid_path),
                            str(ready_path),
                            str(escaped_path),
                            str(case_root),
                            str(log_path),
                            "0",
                            str(case_root / "spawned.pid"),
                        ),
                        cwd=ROOT,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    ready_deadline = time.monotonic() + 5
                    while (
                        not ready_path.exists()
                        and driver.poll() is None
                        and time.monotonic() < ready_deadline
                    ):
                        time.sleep(0.01)
                    leader_pid = read_pid(leader_pid_path)
                    descendant_pid = read_pid(descendant_pid_path)
                    if not ready_path.exists():
                        failures.append(
                            f"focused Swift {label} fixture did not become ready"
                        )
                        continue
                    if leader_pid is None or descendant_pid is None:
                        failures.append(
                            f"focused Swift {label} fixture did not publish PIDs"
                        )
                        continue

                    os.killpg(driver.pid, signum)
                    try:
                        driver.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        failures.append(
                            f"focused Swift {label} cancellation did not exit"
                        )
                    else:
                        expected_status = -int(signum)
                        if driver.returncode != expected_status:
                            failures.append(
                                f"focused Swift {label} cancellation exited "
                                f"with status {driver.returncode}, expected "
                                f"{expected_status}"
                            )

                    observation_deadline = time.monotonic() + 0.7
                    while time.monotonic() < observation_deadline:
                        if escaped_path.exists():
                            break
                        time.sleep(0.01)
                    if escaped_path.exists():
                        failures.append(
                            f"focused Swift {label} cancellation retained a "
                            "sentinel-writing descendant"
                        )
                    if process_exists(descendant_pid):
                        failures.append(
                            f"focused Swift {label} cancellation retained a "
                            "descendant process"
                        )
                    if log_path.read_bytes() != sentinel_bytes:
                        failures.append(
                            f"focused Swift {label} cancellation replaced the "
                            "canonical log"
                        )
                    if tuple(case_root.glob(f".{log_path.name}.tmp-*")):
                        failures.append(
                            f"focused Swift {label} cancellation retained a "
                            "temporary log"
                        )
                    if tuple(case_root.glob(f".{log_path.name}.previous-*")):
                        failures.append(
                            f"focused Swift {label} cancellation retained a "
                            "canonical backup"
                        )
                finally:
                    if driver is not None and driver.poll() is None:
                        kill_fixture_group(driver.pid)
                        try:
                            driver.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass
                    kill_fixture_group(leader_pid)
                    if descendant_pid is not None and process_exists(
                        descendant_pid
                    ):
                        try:
                            os.kill(descendant_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

            race_root = root / "popen-race"
            race_root.mkdir()
            race_leader_pid_path = race_root / "leader.pid"
            race_descendant_pid_path = race_root / "descendant.pid"
            race_ready_path = race_root / "ready"
            race_escaped_path = race_root / "escaped"
            race_spawned_pid_path = race_root / "spawned.pid"
            race_log_path = race_root / "result.log"
            race_log_bytes = b"prior canonical Popen race log\n"
            race_log_path.write_bytes(race_log_bytes)
            race_driver: subprocess.Popen[bytes] | None = None
            race_spawned_pid: int | None = None
            try:
                race_driver = subprocess.Popen(
                    (
                        sys.executable,
                        "-B",
                        str(driver_path),
                        str(Path(__file__).resolve()),
                        str(inner_path),
                        str(race_leader_pid_path),
                        str(race_descendant_pid_path),
                        str(race_ready_path),
                        str(race_escaped_path),
                        str(race_root),
                        str(race_log_path),
                        str(int(signal.SIGTERM)),
                        str(race_spawned_pid_path),
                    ),
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                try:
                    race_driver.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    failures.append(
                        "focused Swift Popen-race cancellation did not exit"
                    )
                else:
                    if race_driver.returncode != -int(signal.SIGTERM):
                        failures.append(
                            "focused Swift Popen-race cancellation exited "
                            f"with status {race_driver.returncode}, expected "
                            f"{-int(signal.SIGTERM)}"
                        )
                race_spawned_pid = read_pid(race_spawned_pid_path)
                if race_spawned_pid is None:
                    failures.append(
                        "focused Swift Popen-race fixture did not publish its PID"
                    )
                else:
                    try:
                        os.killpg(race_spawned_pid, 0)
                    except ProcessLookupError:
                        pass
                    else:
                        failures.append(
                            "focused Swift Popen-race cancellation retained its "
                            "nested process group"
                        )
                time.sleep(0.6)
                if race_escaped_path.exists():
                    failures.append(
                        "focused Swift Popen-race cancellation retained a "
                        "sentinel-writing descendant"
                    )
                if race_log_path.read_bytes() != race_log_bytes:
                    failures.append(
                        "focused Swift Popen-race cancellation replaced the "
                        "canonical log"
                    )
                if tuple(race_root.glob(f".{race_log_path.name}.tmp-*")):
                    failures.append(
                        "focused Swift Popen-race cancellation retained a "
                        "temporary log"
                    )
            finally:
                if race_driver is not None and race_driver.poll() is None:
                    kill_fixture_group(race_driver.pid)
                    try:
                        race_driver.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
                kill_fixture_group(race_spawned_pid)
                kill_fixture_group(read_pid(race_leader_pid_path))
                race_descendant_pid = read_pid(race_descendant_pid_path)
                if race_descendant_pid is not None and process_exists(
                    race_descendant_pid
                ):
                    try:
                        os.kill(race_descendant_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

            keyboard_root = root / "keyboard-interrupt"
            keyboard_root.mkdir()
            keyboard_leader_pid_path = keyboard_root / "leader.pid"
            keyboard_descendant_pid_path = keyboard_root / "descendant.pid"
            keyboard_ready_path = keyboard_root / "ready"
            keyboard_escaped_path = keyboard_root / "escaped"
            keyboard_log_path = keyboard_root / "result.log"
            keyboard_log_bytes = b"prior canonical KeyboardInterrupt log\n"
            keyboard_log_path.write_bytes(keyboard_log_bytes)
            original_selector_factory = selectors.DefaultSelector
            original_handlers = tuple(
                signal.getsignal(signum)
                for signum in (signal.SIGTERM, signal.SIGINT)
            )
            original_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
            selector_ready = [False]

            class InterruptingSelector:
                def __init__(self) -> None:
                    self._inner = original_selector_factory()

                def register(self, *args, **kwargs):
                    return self._inner.register(*args, **kwargs)

                def select(self, timeout=None):
                    deadline = time.monotonic() + min(
                        5.0,
                        float(timeout) if timeout is not None else 5.0,
                    )
                    while time.monotonic() < deadline:
                        if keyboard_ready_path.exists():
                            selector_ready[0] = True
                            break
                        time.sleep(0.01)
                    raise KeyboardInterrupt

                def close(self) -> None:
                    self._inner.close()

            keyboard_interrupted = False
            keyboard_leader_pid: int | None = None
            keyboard_descendant_pid: int | None = None
            selectors.DefaultSelector = InterruptingSelector
            try:
                try:
                    run_and_publish_swift_focused_log(
                        command=(
                            sys.executable,
                            "-B",
                            str(inner_path),
                            str(keyboard_leader_pid_path),
                            str(keyboard_descendant_pid_path),
                            str(keyboard_ready_path),
                            str(keyboard_escaped_path),
                        ),
                        cwd=keyboard_root,
                        log_path=keyboard_log_path,
                        expected_tests=(),
                        log_context_failures=lambda _: [],
                        timeout_seconds=30,
                        termination_grace_seconds=0.05,
                    )
                except KeyboardInterrupt:
                    keyboard_interrupted = True
            finally:
                selectors.DefaultSelector = original_selector_factory
                keyboard_leader_pid = read_pid(keyboard_leader_pid_path)
                keyboard_descendant_pid = read_pid(
                    keyboard_descendant_pid_path
                )

            if not keyboard_interrupted:
                failures.append(
                    "focused Swift KeyboardInterrupt was not reraised"
                )
            if not selector_ready[0]:
                failures.append(
                    "focused Swift KeyboardInterrupt fixture did not become "
                    "ready before interruption"
                )
            time.sleep(0.6)
            if keyboard_escaped_path.exists():
                failures.append(
                    "focused Swift KeyboardInterrupt retained a "
                    "sentinel-writing descendant"
                )
            if keyboard_leader_pid is not None:
                try:
                    os.killpg(keyboard_leader_pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    failures.append(
                        "focused Swift KeyboardInterrupt retained its nested "
                        "process group"
                    )
            if (
                keyboard_descendant_pid is not None
                and process_exists(keyboard_descendant_pid)
            ):
                failures.append(
                    "focused Swift KeyboardInterrupt retained a descendant "
                    "process"
                )
            if keyboard_log_path.read_bytes() != keyboard_log_bytes:
                failures.append(
                    "focused Swift KeyboardInterrupt replaced the canonical log"
                )
            if tuple(
                keyboard_root.glob(f".{keyboard_log_path.name}.tmp-*")
            ):
                failures.append(
                    "focused Swift KeyboardInterrupt retained a temporary log"
                )
            current_handlers = tuple(
                signal.getsignal(signum)
                for signum in (signal.SIGTERM, signal.SIGINT)
            )
            current_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
            if current_handlers != original_handlers:
                failures.append(
                    "focused Swift KeyboardInterrupt did not restore signal "
                    "handlers"
                )
            if current_mask != original_mask:
                failures.append(
                    "focused Swift KeyboardInterrupt did not restore the signal "
                    "mask"
                )
            kill_fixture_group(keyboard_leader_pid)
            if (
                keyboard_descendant_pid is not None
                and process_exists(keyboard_descendant_pid)
            ):
                try:
                    os.kill(keyboard_descendant_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    except OSError as error:
        failures.append(f"focused Swift signal self-test failed: {error}")
    return failures


def document_ingestion_mutation_console_self_test() -> list[str]:
    root_seed = "0123456789abcdef"
    test_identity = "FixtureTests.MutationSuite/testCases"
    marker_lines = (
        "AETHERLINK_DOCUMENT_MUTATION_V1 case=000 total=002 "
        "generator=splitmix64-v1 root=0123456789abcdef "
        "seed=0000000000000001 format=txt operators=identity bytes=1 "
        "sha256=" + "a" * 64,
        "AETHERLINK_DOCUMENT_MUTATION_V1 case=001 total=002 "
        "generator=splitmix64-v1 root=0123456789abcdef "
        "seed=0000000000000002 format=txt operators=truncate bytes=0 "
        "sha256=" + "b" * 64,
    )
    manifest_sha256 = hashlib.sha256(
        ("\n".join(marker_lines) + "\n").encode("ascii")
    ).hexdigest()
    summary = (
        "AETHERLINK_DOCUMENT_MUTATION_SUMMARY_V1 total=002 "
        f"root={root_seed} manifest_sha256={manifest_sha256}"
    )
    started = "Test Case '-[FixtureTests.MutationSuite testCases]' started."
    passed = (
        "Test Case '-[FixtureTests.MutationSuite testCases]' passed "
        "(0.001 seconds)."
    )
    valid_console = "\n".join((started, *marker_lines, summary, passed)) + "\n"

    def validate(path: Path) -> list[str]:
        _, observed = document_ingestion_mutation_console_snapshot(
            path,
            expected_case_count=2,
            expected_root=root_seed,
            expected_manifest_sha256=manifest_sha256,
            expected_formats=("txt",),
            expected_primary_operators=("identity", "truncate"),
            expected_test_identity=test_identity,
        )
        return observed

    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-document-mutation-console-",
        ) as temporary:
            log_path = Path(temporary) / "mutation.log"
            log_path.write_text(valid_console, encoding="utf-8")
            snapshot, observed = document_ingestion_mutation_console_snapshot(
                log_path,
                expected_case_count=2,
                expected_root=root_seed,
                expected_manifest_sha256=manifest_sha256,
                expected_formats=("txt",),
                expected_primary_operators=("identity", "truncate"),
                expected_test_identity=test_identity,
            )
            if observed or snapshot is None or snapshot.get("cases") != 2:
                failures.append(
                    "valid DocumentIngestion mutation console fixture was "
                    "rejected"
                )

            mutations = (
                ("missing case", valid_console.replace(marker_lines[1] + "\n", "")),
                (
                    "duplicate case",
                    valid_console.replace(
                        marker_lines[1] + "\n",
                        marker_lines[1] + "\n" + marker_lines[1] + "\n",
                    ),
                ),
                (
                    "reordered cases",
                    valid_console.replace(
                        marker_lines[0] + "\n" + marker_lines[1],
                        marker_lines[1] + "\n" + marker_lines[0],
                    ),
                ),
                (
                    "root drift",
                    valid_console.replace(root_seed, "1123456789abcdef", 1),
                ),
                (
                    "unknown operator",
                    valid_console.replace("operators=identity", "operators=random"),
                ),
                (
                    "byte overflow",
                    valid_console.replace("bytes=1", "bytes=4098", 1),
                ),
                (
                    "summary before cases",
                    valid_console.replace(summary + "\n", "", 1).replace(
                        started + "\n",
                        started + "\n" + summary + "\n",
                        1,
                    ),
                ),
                (
                    "summary manifest drift",
                    valid_console.replace(manifest_sha256, "f" * 64, 1),
                ),
            )
            for label, mutated in mutations:
                log_path.write_text(mutated, encoding="utf-8")
                if not validate(log_path):
                    failures.append(
                        "DocumentIngestion mutation console mutation was not "
                        f"rejected: {label}"
                    )
    except OSError as error:
        failures.append(
            f"DocumentIngestion mutation console self-test failed: {error}"
        )
    return failures


def document_ingestion_mutation_failure_context_self_test() -> list[str]:
    marker_one = (
        "AETHERLINK_DOCUMENT_MUTATION_V1 case=000 total=002 "
        "generator=splitmix64-v1 root=0123456789abcdef "
        "seed=0000000000000001 format=txt operators=identity bytes=1 "
        "sha256=" + "a" * 64
    )
    marker_two = (
        "AETHERLINK_DOCUMENT_MUTATION_V1 case=001 total=002 "
        "generator=splitmix64-v1 root=0123456789abcdef "
        "seed=0000000000000002 format=txt operators=truncate bytes=0 "
        "sha256=" + "b" * 64
    )
    expected_context = (
        "last observed DocumentIngestion mutation marker: " + marker_two
    )
    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-document-mutation-failure-",
        ) as temporary:
            root = Path(temporary)
            log_path = root / "mutation.log"
            log_path.write_bytes(b"prior successful canonical log\n")

            def canonical_state() -> tuple[bytes, int]:
                state = log_path.stat()
                return log_path.read_bytes(), state.st_ino

            def command(
                output: str,
                *,
                exit_status: int = 1,
                sleep: bool = False,
            ) -> tuple[str, ...]:
                trailer = "import time; time.sleep(60)\n" if sleep else ""
                return (
                    sys.executable,
                    "-B",
                    "-c",
                    "import sys\n"
                    f"sys.stdout.write({output!r})\n"
                    "sys.stdout.flush()\n"
                    + trailer
                    + f"raise SystemExit({exit_status})\n",
                )

            def run_failure(
                label: str,
                output: str,
                *,
                timeout_seconds: float = 2,
                max_bytes: int = SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
                sleep: bool = False,
                expected_marker: bool = True,
            ) -> None:
                before = canonical_state()
                status, observed = run_and_publish_swift_focused_log(
                    command=command(output, sleep=sleep),
                    cwd=root,
                    log_path=log_path,
                    expected_tests=(),
                    log_context_failures=lambda _: [],
                    failure_context=last_document_ingestion_mutation_marker,
                    timeout_seconds=timeout_seconds,
                    max_bytes=max_bytes,
                )
                if status == 0:
                    failures.append(
                        f"DocumentIngestion mutation {label} fixture passed"
                    )
                if expected_marker and expected_context not in observed:
                    failures.append(
                        f"DocumentIngestion mutation {label} lost its last marker"
                    )
                if not expected_marker and any(
                    "last observed DocumentIngestion mutation marker" in item
                    for item in observed
                ):
                    failures.append(
                        f"DocumentIngestion mutation {label} accepted a malformed marker"
                    )
                if canonical_state() != before:
                    failures.append(
                        f"DocumentIngestion mutation {label} replaced the prior log"
                    )

            marker_output = marker_one + "\n" + marker_two + "\n"
            run_failure("nonzero", marker_output)
            run_failure(
                "timeout",
                marker_output,
                timeout_seconds=0.1,
                sleep=True,
            )
            run_failure(
                "oversized",
                marker_output + "x" * 1024,
                max_bytes=len(marker_output.encode("ascii")),
            )
            run_failure(
                "malformed",
                (marker_two + "\n").replace("case=001", "case=1", 1),
                expected_marker=False,
            )

            success_console = (
                "Test Suite 'Selected tests' started.\n"
                "\t Executed 0 tests, with 0 failures (0 unexpected) in "
                "0.000 (0.000) seconds\n"
            )
            status, observed = run_and_publish_swift_focused_log(
                command=command(success_console, exit_status=0),
                cwd=root,
                log_path=log_path,
                expected_tests=(),
                log_context_failures=lambda _: [],
                failure_context=last_document_ingestion_mutation_marker,
            )
            if status != 0 or observed:
                failures.append(
                    "DocumentIngestion mutation successful runner emitted "
                    "failure context"
                )
    except OSError as error:
        failures.append(
            f"DocumentIngestion mutation failure-context self-test failed: {error}"
        )
    return failures


def android_result_freshness_self_test() -> list[str]:
    failures: list[str] = []
    source_mtimes = (
        ("source-a", 100),
        ("source-b", 200),
    )
    if android_result_staleness_failure(
        report_label="fresh-report",
        report_mtime_ns=201,
        input_mtimes=source_mtimes,
    ) is not None:
        failures.append("fresh Android result timestamp was rejected")
    equal_source_failure = android_result_staleness_failure(
        report_label="equal-source-report",
        report_mtime_ns=200,
        input_mtimes=source_mtimes,
    )
    if equal_source_failure is None or "after source-b" not in equal_source_failure:
        failures.append(
            "source-equal Android result timestamp was not rejected"
        )
    stale_failure = android_result_staleness_failure(
        report_label="stale-report",
        report_mtime_ns=199,
        input_mtimes=source_mtimes,
    )
    if stale_failure is None or "after source-b" not in stale_failure:
        failures.append("stale Android result timestamp was not rejected")
    if android_result_staleness_failure(
        report_label="unbound-report",
        report_mtime_ns=200,
        input_mtimes=(),
    ) is None:
        failures.append("unbound Android result timestamp was not rejected")
    future_failure = android_result_staleness_failure(
        report_label="future-report",
        report_mtime_ns=(
            200 + ANDROID_RESULT_FUTURE_MTIME_TOLERANCE_NS + 1
        ),
        input_mtimes=source_mtimes,
        current_time_ns=200,
    )
    if future_failure is None or "implausibly in the future" not in future_failure:
        failures.append("future Android result timestamp was not rejected")

    enumerated_inputs = set(android_result_freshness_inputs())
    required_inputs = (
        Path(__file__).resolve(),
        WORKFLOW_PATH,
        NO_DEVICE_QUALITY_PATH,
        ROOT / "gradlew",
        ROOT / "build.gradle.kts",
        ROOT / "settings.gradle.kts",
        ROOT / "gradle.properties",
        ROOT / "buildscript-gradle.lockfile",
        ROOT / "settings-gradle.lockfile",
        ROOT / "gradle/libs.versions.toml",
        ROOT / "gradle/gradle-daemon-jvm.properties",
        ROOT / "gradle/wrapper/gradle-wrapper.jar",
        ROOT / "gradle/wrapper/gradle-wrapper.properties",
        ROOT / "apps/android/app/build.gradle.kts",
        ROOT / "apps/android/app/gradle.lockfile",
        ROOT / "apps/android/core/pairing/build.gradle.kts",
        ROOT / "apps/android/core/pairing/gradle.lockfile",
        ROOT / "apps/android/core/protocol/build.gradle.kts",
        ROOT / "apps/android/core/protocol/gradle.lockfile",
        ROOT / "apps/android/core/transport/build.gradle.kts",
        ROOT / "apps/android/core/transport/gradle.lockfile",
        ROOT / "apps/android/app/src/main",
        ROOT / "apps/android/app/src/test",
        ROOT / "apps/android/core/pairing/src/main",
        ROOT / "apps/android/core/protocol/src/main",
        ROOT / "apps/android/core/transport/src/main",
        ROOT
        / "apps/android/app/src/main/java/com/localagentbridge/android/"
        "MainActivity.kt",
        ROOT
        / "apps/android/app/src/test/java/com/localagentbridge/android/ui/"
        "ClientScreensNoDeviceComposeTest.kt",
        ANDROID_FONT_SCALE_TEST_PATH,
        ROOT
        / "apps/android/core/pairing/src/main/java/com/localagentbridge/"
        "android/core/pairing/DeviceIdentity.kt",
        ROOT
        / "apps/android/core/protocol/src/main/java/com/localagentbridge/"
        "android/core/protocol/ProtocolCodec.kt",
        ROOT
        / "apps/android/core/transport/src/main/java/com/localagentbridge/"
        "android/core/transport/BonjourDiscovery.kt",
    )
    for required_input in required_inputs:
        if required_input not in enumerated_inputs:
            failures.append(
                "Android result freshness input enumeration omitted "
                f"{path_label(required_input)}"
            )

    fixture_class = "example.CurrentSourceTest"
    fixture_contract = ((fixture_class, 1, ("passes",)),)
    fixture_xml = (
        f'<testsuite name="{fixture_class}" tests="1" skipped="0" '
        'failures="0" errors="0">'
        f'<testcase name="passes" classname="{fixture_class}"/>'
        "</testsuite>"
    )
    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-product-ci-freshness-",
        ) as temporary:
            temporary_root = Path(temporary)
            result_root = temporary_root / "results"
            result_root.mkdir()
            report_path = result_root / f"TEST-{fixture_class}.xml"
            report_path.write_text(fixture_xml, encoding="utf-8")
            readable_default_mtimes = tuple(
                input_path.stat().st_mtime_ns
                for input_path in enumerated_inputs
            )
            newest_default_mtime_ns = max(readable_default_mtimes)
            os.utime(
                report_path,
                ns=(
                    newest_default_mtime_ns + 1_000_000,
                    newest_default_mtime_ns + 1_000_000,
                ),
            )
            fresh_failures = android_test_result_failures(
                fixture_contract,
                result_root=result_root,
            )
            if fresh_failures:
                failures.append(
                    "fresh XML integration fixture was rejected: "
                    + "; ".join(fresh_failures)
                )
            os.utime(
                report_path,
                ns=(
                    max(0, newest_default_mtime_ns - 1),
                    max(0, newest_default_mtime_ns - 1),
                ),
            )
            stale_failures = android_test_result_failures(
                fixture_contract,
                result_root=result_root,
            )
            if not any("is stale" in failure for failure in stale_failures):
                failures.append(
                    "stale XML integration fixture was not rejected by the "
                    "actual Android result gate"
                )

            full_class = "example.FullSourceTest"
            full_contract = ((full_class, 2, ("required",)),)
            full_result_root = temporary_root / "full-results"
            full_result_root.mkdir()
            full_report_path = (
                full_result_root / f"TEST-{full_class}.xml"
            )
            full_report_path.write_text(
                (
                    f'<testsuite name="{full_class}" tests="2" skipped="0" '
                    'failures="0" errors="0">'
                    f'<testcase name="required" classname="{full_class}"/>'
                    f'<testcase name="additional" classname="{full_class}"/>'
                    "</testsuite>"
                ),
                encoding="utf-8",
            )
            os.utime(
                full_report_path,
                ns=(
                    newest_default_mtime_ns + 1_000_000,
                    newest_default_mtime_ns + 1_000_000,
                ),
            )
            full_testcase_manifest = android_testcase_manifest_sha256(
                [
                    (full_class, "required"),
                    (full_class, "additional"),
                ]
            )
            full_failures = android_test_result_failures(
                full_contract,
                result_root=full_result_root,
                allow_additional_methods=True,
                require_exact_report_set=True,
                expected_testcase_manifest_sha256=(
                    full_testcase_manifest
                ),
            )
            if full_failures:
                failures.append(
                    "full XML integration fixture was rejected: "
                    + "; ".join(full_failures)
                )
            strict_method_failures = android_test_result_failures(
                full_contract,
                result_root=full_result_root,
            )
            if not any(
                "selected test methods must match the exact contract"
                in failure
                for failure in strict_method_failures
            ):
                failures.append(
                    "full XML additional method was not rejected by the "
                    "focused exact-method gate"
                )
            missing_method_failures = android_test_result_failures(
                ((full_class, 2, ("missing",)),),
                result_root=full_result_root,
                allow_additional_methods=True,
                require_exact_report_set=True,
                expected_testcase_manifest_sha256=(
                    full_testcase_manifest
                ),
            )
            if not any(
                "full-suite test methods must include the required contract"
                in failure
                for failure in missing_method_failures
            ):
                failures.append(
                    "full XML missing required method was not rejected"
                )
            wrong_manifest_failures = android_test_result_failures(
                full_contract,
                result_root=full_result_root,
                allow_additional_methods=True,
                require_exact_report_set=True,
                expected_testcase_manifest_sha256=("0" * 64),
            )
            if not any(
                "testcase manifest SHA-256 must match"
                in failure
                for failure in wrong_manifest_failures
            ):
                failures.append(
                    "full XML testcase substitution was not rejected"
                )
            original_full_xml = full_report_path.read_text(
                encoding="utf-8"
            )
            full_report_path.write_text(
                original_full_xml.replace(
                    'name="additional"',
                    'name="sameCountSubstitution"',
                    1,
                ),
                encoding="utf-8",
            )
            same_count_substitution_failures = (
                android_test_result_failures(
                    full_contract,
                    result_root=full_result_root,
                    allow_additional_methods=True,
                    require_exact_report_set=True,
                    expected_testcase_manifest_sha256=(
                        full_testcase_manifest
                    ),
                )
            )
            if not any(
                "testcase manifest SHA-256 must match"
                in failure
                for failure in same_count_substitution_failures
            ):
                failures.append(
                    "same-count XML testcase substitution was not rejected"
                )
            full_report_path.write_text(
                original_full_xml,
                encoding="utf-8",
            )

            binding_exact_file = temporary_root / "binding-config.txt"
            binding_exact_file.write_text("config-v1\n", encoding="utf-8")
            binding_source_root = temporary_root / "binding-source"
            binding_nested_directory = (
                binding_source_root / "nested" / "deeper"
            )
            binding_nested_directory.mkdir(parents=True)
            binding_source_file = binding_nested_directory / "Source.kt"
            binding_source_file.write_text(
                "class SourceV1\n",
                encoding="utf-8",
            )
            enumerated_fixture_inputs = set(
                android_result_freshness_inputs(
                    exact_files=(binding_exact_file,),
                    source_roots=(binding_source_root,),
                )
            )
            if binding_nested_directory not in enumerated_fixture_inputs:
                failures.append(
                    "Android result freshness enumeration omitted a "
                    "nested source directory"
                )

            binding_marker_path = (
                temporary_root / "full-test-run-marker.json"
            )
            marker_payload, marker_payload_failures = (
                android_full_test_run_marker_payload(
                    exact_files=(binding_exact_file,),
                    source_roots=(binding_source_root,),
                    expected_results=full_contract,
                    testcase_manifest_sha256=(
                        full_testcase_manifest
                    ),
                )
            )
            if marker_payload_failures or marker_payload is None:
                failures.append(
                    "full XML source marker fixture could not be built: "
                    + "; ".join(marker_payload_failures)
                )
            else:
                binding_marker_path.write_bytes(
                    canonical_json_bytes(marker_payload)
                )
                full_report_mtime_ns = (
                    full_report_path.stat().st_mtime_ns
                )
                os.utime(
                    binding_marker_path,
                    ns=(
                        max(0, full_report_mtime_ns - 1_000_000),
                        max(0, full_report_mtime_ns - 1_000_000),
                    ),
                )
                marker_failures = android_full_test_run_marker_failures(
                    result_root=full_result_root,
                    marker_path=binding_marker_path,
                    exact_files=(binding_exact_file,),
                    source_roots=(binding_source_root,),
                    expected_results=full_contract,
                    testcase_manifest_sha256=(
                        full_testcase_manifest
                    ),
                )
                if marker_failures:
                    failures.append(
                        "fresh full XML source marker was rejected: "
                        + "; ".join(marker_failures)
                    )
                os.utime(
                    binding_marker_path,
                    ns=(full_report_mtime_ns, full_report_mtime_ns),
                )
                equal_marker_failures = (
                    android_full_test_run_marker_failures(
                        result_root=full_result_root,
                        marker_path=binding_marker_path,
                        exact_files=(binding_exact_file,),
                        source_roots=(binding_source_root,),
                        expected_results=full_contract,
                        testcase_manifest_sha256=(
                            full_testcase_manifest
                        ),
                    )
                )
                if not any(
                    "must be generated after" in failure
                    for failure in equal_marker_failures
                ):
                    failures.append(
                        "marker-equal Android full report timestamp was not "
                        "rejected"
                    )
                os.utime(
                    binding_marker_path,
                    ns=(
                        max(0, full_report_mtime_ns - 1_000_000),
                        max(0, full_report_mtime_ns - 1_000_000),
                    ),
                )

                prebinding_source_mtime_ns = (
                    binding_source_file.stat().st_mtime_ns
                )
                binding_source_file.write_text(
                    "class PrebindingDrift\n",
                    encoding="utf-8",
                )
                os.utime(
                    binding_source_file,
                    ns=(
                        prebinding_source_mtime_ns,
                        prebinding_source_mtime_ns,
                    ),
                )
                prebinding_drift_failures = (
                    android_full_test_run_marker_failures(
                        result_root=full_result_root,
                        marker_path=binding_marker_path,
                        exact_files=(binding_exact_file,),
                        source_roots=(binding_source_root,),
                        expected_results=full_contract,
                        testcase_manifest_sha256=(
                            full_testcase_manifest
                        ),
                    )
                )
                if not any(
                    "must exactly bind the Android source bytes from before"
                    in failure
                    for failure in prebinding_drift_failures
                ):
                    failures.append(
                        "pre-binding Android source byte drift was not "
                        "rejected"
                    )
                binding_source_file.write_text(
                    "class SourceV1\n",
                    encoding="utf-8",
                )
                os.utime(
                    binding_source_file,
                    ns=(
                        prebinding_source_mtime_ns,
                        prebinding_source_mtime_ns,
                    ),
                )

            binding_payload, binding_payload_failures = (
                android_full_test_binding_payload(
                    result_root=full_result_root,
                    marker_path=binding_marker_path,
                    exact_files=(binding_exact_file,),
                    source_roots=(binding_source_root,),
                    expected_results=full_contract,
                    testcase_manifest_sha256=(
                        full_testcase_manifest
                    ),
                )
            )
            if binding_payload_failures or binding_payload is None:
                failures.append(
                    "full XML binding fixture could not be built: "
                    + "; ".join(binding_payload_failures)
                )
            else:
                binding_path = (
                    full_result_root
                    / "aetherlink-full-test-result-binding-v1.json"
                )
                binding_path.write_bytes(
                    canonical_json_bytes(binding_payload)
                )
                os.utime(
                    binding_path,
                    ns=(
                        full_report_mtime_ns + 1_000_000,
                        full_report_mtime_ns + 1_000_000,
                    ),
                )
                binding_failures = android_full_test_binding_failures(
                    result_root=full_result_root,
                    binding_path=binding_path,
                    marker_path=binding_marker_path,
                    exact_files=(binding_exact_file,),
                    source_roots=(binding_source_root,),
                    expected_results=full_contract,
                    testcase_manifest_sha256=(
                        full_testcase_manifest
                    ),
                )
                if binding_failures:
                    failures.append(
                        "fresh full XML byte binding was rejected: "
                        + "; ".join(binding_failures)
                    )
                os.utime(
                    binding_path,
                    ns=(full_report_mtime_ns, full_report_mtime_ns),
                )
                equal_binding_failures = (
                    android_full_test_binding_failures(
                        result_root=full_result_root,
                        binding_path=binding_path,
                        marker_path=binding_marker_path,
                        exact_files=(binding_exact_file,),
                        source_roots=(binding_source_root,),
                        expected_results=full_contract,
                        testcase_manifest_sha256=(
                            full_testcase_manifest
                        ),
                    )
                )
                if not any(
                    "must postdate every bound" in failure
                    for failure in equal_binding_failures
                ):
                    failures.append(
                        "report-equal Android full binding timestamp was not "
                        "rejected"
                    )
                os.utime(
                    binding_path,
                    ns=(
                        full_report_mtime_ns + 1_000_000,
                        full_report_mtime_ns + 1_000_000,
                    ),
                )

                original_source_mtime_ns = (
                    binding_source_file.stat().st_mtime_ns
                )
                binding_source_file.write_text(
                    "class SourceV2\n",
                    encoding="utf-8",
                )
                os.utime(
                    binding_source_file,
                    ns=(
                        original_source_mtime_ns,
                        original_source_mtime_ns,
                    ),
                )
                content_drift_failures = (
                    android_full_test_binding_failures(
                        result_root=full_result_root,
                        binding_path=binding_path,
                        marker_path=binding_marker_path,
                        exact_files=(binding_exact_file,),
                        source_roots=(binding_source_root,),
                        expected_results=full_contract,
                        testcase_manifest_sha256=(
                            full_testcase_manifest
                        ),
                    )
                )
                if not any(
                    "must exactly bind the current Android full-suite"
                    in failure
                    for failure in content_drift_failures
                ):
                    failures.append(
                        "mtime-preserved Android source content drift "
                        "was not rejected"
                    )
                binding_source_file.write_text(
                    "class SourceV1\n",
                    encoding="utf-8",
                )
                os.utime(
                    binding_source_file,
                    ns=(
                        original_source_mtime_ns,
                        original_source_mtime_ns,
                    ),
                )
                renamed_source_file = (
                    binding_nested_directory / "RenamedSource.kt"
                )
                binding_source_file.rename(renamed_source_file)
                path_drift_failures = (
                    android_full_test_binding_failures(
                        result_root=full_result_root,
                        binding_path=binding_path,
                        marker_path=binding_marker_path,
                        exact_files=(binding_exact_file,),
                        source_roots=(binding_source_root,),
                        expected_results=full_contract,
                        testcase_manifest_sha256=(
                            full_testcase_manifest
                        ),
                    )
                )
                if not any(
                    "must exactly bind the current Android full-suite"
                    in failure
                    for failure in path_drift_failures
                ):
                    failures.append(
                        "Android source path drift was not rejected"
                    )
            extra_class = "example.ExtraSourceTest"
            extra_report_path = (
                full_result_root / f"TEST-{extra_class}.xml"
            )
            extra_report_path.write_text(
                (
                    f'<testsuite name="{extra_class}" tests="0" skipped="0" '
                    'failures="0" errors="0"></testsuite>'
                ),
                encoding="utf-8",
            )
            exact_set_failures = android_test_result_failures(
                full_contract,
                result_root=full_result_root,
                allow_additional_methods=True,
                require_exact_report_set=True,
            )
            if not any(
                "result report set must match the exact result contract"
                in failure
                for failure in exact_set_failures
            ):
                failures.append(
                    "full XML unexpected report was not rejected"
                )
    except OSError as error:
        failures.append(f"Android result freshness fixture failed: {error}")
    return failures


ANDROID_FULL_RESULT_GATE_BODY = (
    "run python3 -B script/check_product_ci.py "
    "--write-android-full-test-binding\n"
    "run python3 -B script/check_product_ci.py "
    "--android-full-test-results\n"
    "run python3 -B script/check_product_ci.py "
    "--android-camera-lifecycle-results\n"
)
ANDROID_FULL_RUN_PREPARE_COMMAND = (
    "run python3 -B script/check_product_ci.py "
    "--prepare-android-full-test-run\n"
)
ANDROID_FULL_RUNNER_SELECTORS = ANDROID_MAIN_FULL_TESTS


def no_device_full_result_gate_failures(
    runner_text: str | None = None,
) -> list[str]:
    relative = NO_DEVICE_QUALITY_PATH.relative_to(ROOT)
    if runner_text is None:
        try:
            runner_text = NO_DEVICE_QUALITY_PATH.read_text(
                encoding="utf-8",
            )
        except (OSError, UnicodeError) as error:
            return [
                f"{relative} cannot be read for Android full-result "
                f"gate validation: {error}"
            ]
    failures: list[str] = []
    if runner_text.count(ANDROID_FULL_RESULT_GATE_BODY) != 1:
        failures.append(
            f"{relative} must write, read back, and then project the "
            "Android full-result binding exactly once"
        )
    for command in (
        "--prepare-android-full-test-run",
        "--write-android-full-test-binding",
        "--android-full-test-results",
    ):
        if runner_text.count(command) != 1:
            failures.append(
                f"{relative} must invoke {command} exactly once"
            )
    full_app_selector = (
        "--tests com.localagentbridge.android.AppNavigationTest \\\n"
    )
    prepare_index = runner_text.find(
        ANDROID_FULL_RUN_PREPARE_COMMAND
    )
    selector_index = runner_text.find(full_app_selector)
    gate_index = runner_text.find(ANDROID_FULL_RESULT_GATE_BODY)
    if selector_index < 0 or gate_index <= selector_index:
        failures.append(
            f"{relative} must run the full-result binding only after "
            "the complete Android app class selector"
        )
    else:
        block_start = runner_text.rfind(
            "run ./gradlew --offline --no-daemon",
            0,
            selector_index,
        )
        block_end_marker = "-Pkotlin.incremental=false"
        block_end = runner_text.find(
            block_end_marker,
            selector_index,
        )
        if block_start < 0 or block_end < 0 or block_end >= gate_index:
            failures.append(
                f"{relative} cannot isolate the Android full-app "
                "Gradle selector block"
            )
        else:
            block_end += len(block_end_marker)
            selector_block = runner_text[block_start:block_end]
            if prepare_index < 0 or prepare_index >= block_start:
                failures.append(
                    f"{relative} must prepare the Android full-suite "
                    "source marker immediately before the Gradle run"
                )
            else:
                between_prepare_and_run = runner_text[
                    prepare_index
                    + len(ANDROID_FULL_RUN_PREPARE_COMMAND):
                    block_start
                ]
                if between_prepare_and_run.strip():
                    failures.append(
                        f"{relative} must not execute another action "
                        "between the source marker and Android full run"
                    )
            actual_selectors = tuple(
                re.findall(
                    r"(?m)^\s*--tests\s+([^\s\\]+)\s*\\$",
                    selector_block,
                )
            )
            if actual_selectors != ANDROID_FULL_RUNNER_SELECTORS:
                failures.append(
                    f"{relative} Android full-app selectors must match "
                    "the exact 19-suite contract"
                )
            if selector_block.count(":app:testDebugUnitTest") != 1:
                failures.append(
                    f"{relative} Android full-app selector must execute "
                    ":app:testDebugUnitTest exactly once"
                )
            if selector_block.count("--rerun-tasks") != 1:
                failures.append(
                    f"{relative} Android full-app selector must force "
                    "exactly one current-run test execution"
                )
            if runner_text[block_end:gate_index].strip():
                failures.append(
                    f"{relative} must write the Android full-result "
                    "binding immediately after the Gradle run"
                )
    return failures


def no_device_full_result_gate_self_test() -> list[str]:
    try:
        runner_text = NO_DEVICE_QUALITY_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [f"cannot load Android full-result runner self-test: {error}"]
    failures: list[str] = []
    mutations = (
        (
            "removed pre-run source marker",
            runner_text.replace(
                ANDROID_FULL_RUN_PREPARE_COMMAND,
                "",
                1,
            ),
        ),
        (
            "removed binding writer",
            runner_text.replace(
                (
                    "run python3 -B script/check_product_ci.py "
                    "--write-android-full-test-binding\n"
                ),
                "",
                1,
            ),
        ),
        (
            "reversed binding order",
            runner_text.replace(
                ANDROID_FULL_RESULT_GATE_BODY,
                (
                    "run python3 -B script/check_product_ci.py "
                    "--android-full-test-results\n"
                    "run python3 -B script/check_product_ci.py "
                    "--write-android-full-test-binding\n"
                    "run python3 -B script/check_product_ci.py "
                    "--android-camera-lifecycle-results\n"
                ),
                1,
            ),
        ),
        (
            "missing app-language lifecycle selector",
            runner_text.replace(
                (
                    "		  --tests com.localagentbridge.android."
                    "AndroidAppLanguagePlatformLifecycleTest \\\n"
                ),
                "",
                1,
            ),
        ),
        (
            "removed full-run rerun requirement",
            runner_text.replace(
                "	  --rerun-tasks \\\n",
                "",
                1,
            ),
        ),
    )
    for label, mutated in mutations:
        if mutated == runner_text:
            failures.append(
                f"Android full-result runner {label} mutation did not apply"
            )
        elif not no_device_full_result_gate_failures(mutated):
            failures.append(
                f"Android full-result runner {label} was not rejected"
            )
    return failures


def product_copy_font_scale_guard_failures(
    copy_hygiene_text: str | None = None,
) -> list[str]:
    relative = COPY_HYGIENE_PATH.relative_to(ROOT)
    if copy_hygiene_text is None:
        try:
            copy_hygiene_text = COPY_HYGIENE_PATH.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative} cannot be read for product-copy guard validation: "
                f"{error}"
            ]

    branch_start = copy_hygiene_text.find("    if arguments:")
    copy_check = copy_hygiene_text.find(
        "        if report_product_copy_failures():",
        branch_start,
    )
    font_scale_guard = copy_hygiene_text.find(
        "android_font_scale_qualification_guard_failures",
        copy_check,
    )
    success_return = copy_hygiene_text.find(
        "        return 0",
        copy_check,
    )
    if not (
        branch_start >= 0
        and copy_check > branch_start
        and font_scale_guard > copy_check
        and success_return > font_scale_guard
    ):
        return [
            f"{relative} --product-copy-only must run the Android font-scale "
            "qualification guard before its successful return"
        ]
    return []


def product_copy_font_scale_guard_self_test() -> list[str]:
    try:
        copy_hygiene_text = COPY_HYGIENE_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [f"cannot load product-copy guard self-test: {error}"]
    branch_start = copy_hygiene_text.find("    if arguments:")
    guard_start = copy_hygiene_text.find(
        "android_font_scale_qualification_guard_failures",
        branch_start,
    )
    if branch_start < 0 or guard_start < 0:
        return ["product-copy font-scale guard self-test mutation did not apply"]
    guard_name = "android_font_scale_qualification_guard_failures"
    mutated = (
        copy_hygiene_text[:guard_start]
        + "removed_font_scale_qualification_guard"
        + copy_hygiene_text[guard_start + len(guard_name):]
    )
    if not product_copy_font_scale_guard_failures(mutated):
        return ["product-copy font-scale guard mutation was not rejected"]
    return []


def kotlin_braced_body_span(
    source: str,
    opening_brace_index: int,
) -> tuple[int, int] | None:
    if (
        opening_brace_index < 0
        or opening_brace_index >= len(source)
        or source[opening_brace_index] != "{"
    ):
        return None
    depth = 0
    index = opening_brace_index
    state = "code"
    block_comment_depth = 0
    while index < len(source):
        if state == "code":
            if source.startswith("//", index):
                state = "line-comment"
                index += 2
                continue
            if source.startswith("/*", index):
                state = "block-comment"
                block_comment_depth = 1
                index += 2
                continue
            if source.startswith('"""', index):
                state = "raw-string"
                index += 3
                continue
            character = source[index]
            if character == '"':
                state = "string"
            elif character == "'":
                state = "character"
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return opening_brace_index + 1, index
            index += 1
            continue
        if state == "line-comment":
            if source[index] == "\n":
                state = "code"
            index += 1
            continue
        if state == "block-comment":
            if source.startswith("/*", index):
                block_comment_depth += 1
                index += 2
            elif source.startswith("*/", index):
                block_comment_depth -= 1
                index += 2
                if block_comment_depth == 0:
                    state = "code"
            else:
                index += 1
            continue
        if state == "raw-string":
            if source.startswith('"""', index):
                state = "code"
                index += 3
            else:
                index += 1
            continue
        if source[index] == "\\":
            index += 2
        elif (
            state == "string"
            and source[index] == '"'
        ) or (
            state == "character"
            and source[index] == "'"
        ):
            state = "code"
            index += 1
        else:
            index += 1
    return None


def kotlin_source_projection(
    source: str,
    *,
    retain_string_literals: bool,
) -> str:
    output = list(source)
    index = 0
    state = "code"
    block_comment_depth = 0

    def blank(position: int) -> None:
        if output[position] != "\n":
            output[position] = " "

    while index < len(source):
        if state == "code":
            if source.startswith("//", index):
                blank(index)
                blank(index + 1)
                state = "line-comment"
                index += 2
                continue
            if source.startswith("/*", index):
                blank(index)
                blank(index + 1)
                state = "block-comment"
                block_comment_depth = 1
                index += 2
                continue
            if source.startswith('"""', index):
                if not retain_string_literals:
                    blank(index)
                    blank(index + 1)
                    blank(index + 2)
                state = "raw-string"
                index += 3
                continue
            if source[index] == '"':
                if not retain_string_literals:
                    blank(index)
                state = "string"
            elif source[index] == "'":
                if not retain_string_literals:
                    blank(index)
                state = "character"
            index += 1
            continue
        if state == "line-comment":
            if source[index] == "\n":
                state = "code"
            else:
                blank(index)
            index += 1
            continue
        if state == "block-comment":
            blank(index)
            if source.startswith("/*", index):
                blank(index + 1)
                block_comment_depth += 1
                index += 2
            elif source.startswith("*/", index):
                blank(index + 1)
                block_comment_depth -= 1
                index += 2
                if block_comment_depth == 0:
                    state = "code"
            else:
                index += 1
            continue
        if state == "raw-string":
            if source.startswith('"""', index):
                if not retain_string_literals:
                    blank(index)
                    blank(index + 1)
                    blank(index + 2)
                state = "code"
                index += 3
            else:
                if not retain_string_literals:
                    blank(index)
                index += 1
            continue
        if not retain_string_literals:
            blank(index)
        if source[index] == "\\":
            if index + 1 < len(source) and not retain_string_literals:
                blank(index + 1)
            index += 2
        elif (
            state == "string"
            and source[index] == '"'
        ) or (
            state == "character"
            and source[index] == "'"
        ):
            state = "code"
            index += 1
        else:
            index += 1
    return "".join(output)


def kotlin_exact_code_occurrence_offsets(
    source: str,
    structural_source: str,
    exact: str,
) -> tuple[int, ...]:
    if (
        not exact
        or len(source) != len(structural_source)
    ):
        return ()
    structural_exact = kotlin_source_projection(
        exact,
        retain_string_literals=False,
    )
    offsets: list[int] = []
    search_start = 0
    while True:
        offset = source.find(exact, search_start)
        if offset < 0:
            break
        if (
            structural_source[offset:offset + len(exact)]
            == structural_exact
        ):
            offsets.append(offset)
        search_start = offset + 1
    return tuple(offsets)


def kotlin_snippet_brace_depths(
    structural_source: str,
    snippet: str,
) -> tuple[int, ...]:
    depths: list[int] = []
    depth = 0
    index = 0
    while index < len(structural_source):
        if structural_source.startswith(snippet, index):
            depths.append(depth)
        if structural_source[index] == "{":
            depth += 1
        elif structural_source[index] == "}":
            depth -= 1
            if depth < 0:
                return ()
        index += 1
    if depth != 0:
        return ()
    return tuple(depths)


def android_app_language_lifecycle_source_failures(
    test_text: str | None = None,
    *,
    enforce_source_digest: bool = True,
) -> list[str]:
    failures: list[str] = []
    relative = ANDROID_APP_LANGUAGE_LIFECYCLE_TEST_PATH.relative_to(ROOT)
    if test_text is None:
        try:
            test_text = ANDROID_APP_LANGUAGE_LIFECYCLE_TEST_PATH.read_text(
                encoding="utf-8",
            )
        except (OSError, UnicodeError) as error:
            return [
                f"{relative} cannot be read for app-language lifecycle validation: "
                f"{error}"
            ]

    if enforce_source_digest:
        source_sha256 = hashlib.sha256(test_text.encode("utf-8")).hexdigest()
        if source_sha256 != ANDROID_APP_LANGUAGE_LIFECYCLE_SOURCE_SHA256:
            failures.append(
                f"{relative} source SHA-256 must remain "
                f"{ANDROID_APP_LANGUAGE_LIFECYCLE_SOURCE_SHA256}, found "
                f"{source_sha256}"
            )

    structural_test_text = kotlin_source_projection(
        test_text,
        retain_string_literals=False,
    )
    if len(
        kotlin_exact_code_occurrence_offsets(
            test_text,
            structural_test_text,
            "@Config(sdk =",
        )
    ) != len(
        ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS
    ):
        failures.append(
            f"{relative} must contain exactly three API 32/33/36 method-level "
            "app-language lifecycle configurations"
        )
    method_contracts = (
        (
            ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[0],
            ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[0],
            (
                "closeInitialActivityAndResetState()",
                "runtimeStore().save(",
                "ActivityScenario.launch(MainActivity::class.java)",
                "awaitStoredLanguage(",
                "assertNull(androidAppLocaleOverrideLanguageTag(application))",
                "scenario.recreate()",
                "assertNotSame(firstActivity, recreatedActivity)",
            ),
            (
                'PersistedRuntimeData().withAppLanguageTag("fr-FR")',
                'awaitStoredLanguage("fr", APP_LANGUAGE_SOURCE_IN_APP)',
            ),
        ),
        (
            ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[1],
            ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[1],
            (
                "closeInitialActivityAndResetState()",
                "runtimeStore().save(",
                "ActivityScenario.launch(MainActivity::class.java)",
                "awaitStoredLanguage(",
                "assertPlatformLanguage(",
                "assertPlatformMigrationCompleted()",
                "migrationScenario.recreate()",
                "assertNotSame(firstActivity, recreatedActivity)",
                "LocaleList.getEmptyLocaleList()",
                "migratedColdScenario.recreate()",
                "localeManager().applicationLocales = LocaleList.forLanguageTags(",
                "externalOverrideScenario.recreate()",
            ),
            (
                'PersistedRuntimeData().withAppLanguageTag("fr-FR")',
                'awaitStoredLanguage("fr", APP_LANGUAGE_SOURCE_IN_APP)',
                'assertPlatformLanguage("fr")',
                'awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_SYSTEM)',
                'LocaleList.forLanguageTags("ko-KR")',
                'awaitStoredLanguage("ko", APP_LANGUAGE_SOURCE_IN_APP)',
            ),
        ),
        (
            ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[2],
            ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[2],
            (
                "closeInitialActivityAndResetState()",
                "runtimeStore().save(",
                "synchronizeAndroidAppLocaleOverride(",
                "ActivityScenario.launch(MainActivity::class.java)",
                "awaitStoredLanguage(",
                "assertPlatformLanguage(",
                "scenario.recreate()",
                "localeManager().applicationLocales.size()",
                "val coldScenario = ActivityScenario.launch(MainActivity::class.java)",
            ),
            (
                'selectedLanguageTag = "en-US"',
                "selectedLanguageTag = null",
                'awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_IN_APP)',
                'awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_SYSTEM)',
            ),
        ),
    )
    execution_depth_contracts = {
        ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[0]: (
            ("closeInitialActivityAndResetState()", (0,)),
            ("runtimeStore().save(", (0,)),
            ("ActivityScenario.launch(MainActivity::class.java)", (0,)),
            ("awaitStoredLanguage(", (1,)),
            ("assertNull(androidAppLocaleOverrideLanguageTag(application))", (1, 1)),
            ("scenario.recreate()", (1,)),
            ("assertNotSame(firstActivity, recreatedActivity)", (1,)),
        ),
        ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[1]: (
            ("closeInitialActivityAndResetState()", (0,)),
            ("runtimeStore().save(", (0,)),
            ("ActivityScenario.launch(MainActivity::class.java)", (0, 0, 0, 0)),
            ("awaitStoredLanguage(", (1, 1, 1, 1, 1)),
            ("assertPlatformLanguage(", (1, 1, 1, 1, 1)),
            ("assertPlatformMigrationCompleted()", (1, 1, 1, 1, 1, 1, 1)),
            ("migrationScenario.recreate()", (1,)),
            ("assertNotSame(firstActivity, recreatedActivity)", (1,)),
            ("LocaleList.getEmptyLocaleList()", (1,)),
            ("localeManager().applicationLocales.size()", (1, 1, 1)),
            ("migratedColdScenario.recreate()", (1,)),
            ("LocaleList.forLanguageTags(", (0,)),
            ("externalOverrideScenario.recreate()", (1,)),
            ("assertStoredLanguage(", (1, 1)),
        ),
        ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[2]: (
            ("closeInitialActivityAndResetState()", (0,)),
            ("runtimeStore().save(", (0,)),
            ("synchronizeAndroidAppLocaleOverride(", (0, 1)),
            ("assertPlatformLanguage(", (0, 1, 1)),
            ("ActivityScenario.launch(MainActivity::class.java)", (0, 0)),
            ("awaitStoredLanguage(", (1, 1, 1)),
            ("scenario.recreate()", (1, 1)),
            ("localeManager().applicationLocales.size()", (1, 1, 1)),
        ),
    }
    for config, method, structural_snippets, literal_snippets in method_contracts:
        header = (
            "    @Test\n"
            f"    {config}\n"
            f"    fun {method}() {{"
        )
        header_offsets = kotlin_exact_code_occurrence_offsets(
            test_text,
            structural_test_text,
            header,
        )
        if len(header_offsets) != 1:
            failures.append(
                f"{relative} must bind {config} directly to {method}"
            )
            continue
        opening_brace_index = header_offsets[0] + len(header) - 1
        body_span = kotlin_braced_body_span(
            structural_test_text,
            opening_brace_index,
        )
        if body_span is None:
            failures.append(
                f"{relative} cannot isolate the executable body for {method}"
            )
            continue
        body = test_text[body_span[0]:body_span[1]]
        uncommented_body = kotlin_source_projection(
            body,
            retain_string_literals=True,
        )
        structural_body = kotlin_source_projection(
            body,
            retain_string_literals=False,
        )
        for snippet in structural_snippets:
            if snippet not in structural_body:
                failures.append(
                    f"{relative} {method} must execute production structure: "
                    f"{snippet}"
                )
        for snippet in literal_snippets:
            if snippet not in uncommented_body:
                failures.append(
                    f"{relative} {method} must execute exact lifecycle case: "
                    f"{snippet}"
                )
        for snippet, expected_depths in execution_depth_contracts[method]:
            actual_depths = kotlin_snippet_brace_depths(
                structural_body,
                snippet,
            )
            if actual_depths != expected_depths:
                failures.append(
                    f"{relative} {method} must execute {snippet} at exact "
                    f"brace depths {expected_depths}, found {actual_depths}"
                )
        if re.search(r"\breturn(?:@[A-Za-z_][A-Za-z0-9_]*)?\b", structural_body):
            failures.append(
                f"{relative} {method} must not bypass its lifecycle assertions "
                "with an early return"
            )
        forbidden_control_flow = re.search(
            r"\b(?:if|when|for|while|do|catch|throw|break|continue|fun)\b",
            structural_body,
        )
        if forbidden_control_flow:
            failures.append(
                f"{relative} {method} must not conditionally bypass or shadow "
                "its fixed lifecycle sequence; found "
                f"{forbidden_control_flow.group(0)}"
            )
        forbidden_short_circuit = next(
            (
                operator
                for operator in ("?:", "?.", "&&", "||")
                if operator in structural_body
            ),
            None,
        )
        if forbidden_short_circuit is not None:
            failures.append(
                f"{relative} {method} must not short-circuit its fixed "
                "lifecycle sequence; found "
                f"{forbidden_short_circuit}"
            )
    return failures


def android_app_language_lifecycle_source_self_test() -> list[str]:
    try:
        test_text = ANDROID_APP_LANGUAGE_LIFECYCLE_TEST_PATH.read_text(
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as error:
        return [f"cannot load app-language lifecycle source self-test: {error}"]
    failures: list[str] = []
    digest_mutation = test_text.replace(
        "class AndroidAppLanguagePlatformLifecycleTest {",
        "class AndroidAppLanguagePlatformLifecycleTest { /* digest mutation */",
        1,
    )
    digest_failures = android_app_language_lifecycle_source_failures(
        digest_mutation,
    )
    if not any("source SHA-256" in failure for failure in digest_failures):
        failures.append(
            "app-language lifecycle source-digest mutation was not rejected"
        )

    changed_api = test_text.replace(
        ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[1],
        '@Config(sdk = [34], qualifiers = "en")',
        1,
    )
    if changed_api == test_text:
        failures.append(
            "app-language lifecycle API matrix self-test mutation did not apply"
        )
    elif not android_app_language_lifecycle_source_failures(
        changed_api,
        enforce_source_digest=False,
    ):
        failures.append(
            "app-language lifecycle API matrix mutation was not rejected"
        )

    placeholder = '@Config(sdk = [999], qualifiers = "en")'
    swapped_configs = (
        test_text
        .replace(ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[0], placeholder, 1)
        .replace(
            ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[2],
            ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[0],
            1,
        )
        .replace(placeholder, ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[2], 1)
    )
    if swapped_configs == test_text:
        failures.append(
            "app-language lifecycle annotation-swap mutation did not apply"
        )
    elif not android_app_language_lifecycle_source_failures(
        swapped_configs,
        enforce_source_digest=False,
    ):
        failures.append(
            "app-language lifecycle annotation swap was not rejected"
        )

    method_header = (
        "    @Test\n"
        f"    {ANDROID_APP_LANGUAGE_LIFECYCLE_CONFIGS[1]}\n"
        f"    fun {ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[1]}() {{"
    )
    method_start = test_text.find(method_header)
    opening_brace_index = method_start + len(method_header) - 1
    body_span = kotlin_braced_body_span(test_text, opening_brace_index)
    if body_span is None:
        failures.append(
            "app-language lifecycle commented-body mutation could not isolate "
            "the target method"
        )
    else:
        original_body = test_text[body_span[0]:body_span[1]]
        commented_body = "\n".join(
            f"// {line}" for line in original_body.splitlines()
        )
        commented_method = (
            test_text[:body_span[0]]
            + "\n"
            + commented_body
            + "\n    "
            + test_text[body_span[1]:]
        )
        if not android_app_language_lifecycle_source_failures(
            commented_method,
            enforce_source_digest=False,
        ):
            failures.append(
                "app-language lifecycle commented empty body was not rejected"
            )
        unreachable_wrappers = (
            (
                "constant-false branch",
                "\n        if (false) {\n",
                "\n        }\n    ",
            ),
            (
                "uninvoked local lambda",
                "\n        val neverInvoked = {\n",
                "\n        }\n    ",
            ),
            (
                "uninvoked local function",
                "\n        fun neverInvoked() {\n",
                "\n        }\n    ",
            ),
        )
        for label, prefix, suffix in unreachable_wrappers:
            wrapped_method = (
                test_text[:body_span[0]]
                + prefix
                + original_body
                + suffix
                + test_text[body_span[1]:]
            )
            if not android_app_language_lifecycle_source_failures(
                wrapped_method,
                enforce_source_digest=False,
            ):
                failures.append(
                    f"app-language lifecycle {label} was not rejected"
                )

        conditionally_disabled_body = re.sub(
            (
                r"(?m)^(\s*)"
                r"(awaitStoredLanguage|assertPlatformLanguage|"
                r"assertNotSame|assertStoredLanguage)\("
            ),
            r"\1if (false) \2(",
            original_body,
        )
        if conditionally_disabled_body == original_body:
            failures.append(
                "app-language lifecycle unbraced false-condition mutation "
                "did not apply"
            )
        else:
            conditionally_disabled_method = (
                test_text[:body_span[0]]
                + conditionally_disabled_body
                + test_text[body_span[1]:]
            )
            if not android_app_language_lifecycle_source_failures(
                conditionally_disabled_method,
                enforce_source_digest=False,
            ):
                failures.append(
                    "app-language lifecycle unbraced false-condition assertions "
                    "were not rejected"
                )

        method_end = body_span[1] + 1
        commented_expected_header = (
            test_text[:method_start]
            + "/*"
            + test_text[method_start:method_end]
            + "*/\n\n"
            + "    @Test\n"
            + "    @org.robolectric.annotation.Config("
            + 'sdk = [34], qualifiers = "en")\n'
            + f"    fun {ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[1]}() {{\n"
            + "    }"
            + test_text[method_end:]
        )
        if not android_app_language_lifecycle_source_failures(
            commented_expected_header,
            enforce_source_digest=False,
        ):
            failures.append(
                "app-language lifecycle block-commented fake header was not "
                "rejected"
            )

        raw_string_expected_header = (
            test_text[:method_start]
            + '    private val lifecycleDecoy = """\n'
            + test_text[method_start:method_end]
            + '\n    """\n\n'
            + "    @Test\n"
            + "    @org.robolectric.annotation.Config("
            + 'sdk = [34], qualifiers = "en")\n'
            + f"    fun {ANDROID_APP_LANGUAGE_LIFECYCLE_METHODS[1]}() {{\n"
            + "    }"
            + test_text[method_end:]
        )
        raw_string_failures = android_app_language_lifecycle_source_failures(
            raw_string_expected_header,
            enforce_source_digest=False,
        )
        if not (
            any(
                "must contain exactly three API 32/33/36" in failure
                for failure in raw_string_failures
            )
            and any(
                "must bind @Config(sdk = [33]" in failure
                for failure in raw_string_failures
            )
        ):
            failures.append(
                "app-language lifecycle raw-string fake header was not "
                "rejected by executable-code position"
            )

        elvis_disabled_body = re.sub(
            (
                r"(?m)^(\s*)"
                r"(awaitStoredLanguage|assertPlatformLanguage|"
                r"assertNotSame|assertStoredLanguage)\("
            ),
            r"\1Unit ?: \2(",
            original_body,
        )
        if elvis_disabled_body == original_body:
            failures.append(
                "app-language lifecycle Elvis short-circuit mutation did not "
                "apply"
            )
        else:
            elvis_disabled_method = (
                test_text[:body_span[0]]
                + elvis_disabled_body
                + test_text[body_span[1]:]
            )
            elvis_failures = android_app_language_lifecycle_source_failures(
                elvis_disabled_method,
                enforce_source_digest=False,
            )
            if not any(
                "must not short-circuit its fixed lifecycle sequence" in failure
                for failure in elvis_failures
            ):
                failures.append(
                    "app-language lifecycle Elvis-disabled assertions were not "
                    "rejected"
                )

        helper_no_op_mutation = test_text
        for helper_name in (
            "awaitStoredLanguage",
            "assertStoredLanguage",
            "assertPlatformLanguage",
        ):
            helper_start = helper_no_op_mutation.find(
                f"    private fun {helper_name}("
            )
            helper_opening = helper_no_op_mutation.find("{", helper_start)
            helper_span = kotlin_braced_body_span(
                helper_no_op_mutation,
                helper_opening,
            )
            if helper_start < 0 or helper_span is None:
                failures.append(
                    f"app-language lifecycle {helper_name} no-op mutation "
                    "could not isolate its helper"
                )
                helper_no_op_mutation = test_text
                break
            helper_no_op_mutation = (
                helper_no_op_mutation[:helper_span[0]]
                + "\n        Unit\n    "
                + helper_no_op_mutation[helper_span[1]:]
            )
        if helper_no_op_mutation != test_text:
            helper_failures = android_app_language_lifecycle_source_failures(
                helper_no_op_mutation,
            )
            if not any(
                "source SHA-256" in failure
                for failure in helper_failures
            ):
                failures.append(
                    "app-language lifecycle no-op helper mutation was not "
                    "rejected by source digest"
                )
    return failures


def android_camera_lifecycle_source_failures(
    test_text: str | None = None,
) -> list[str]:
    failures: list[str] = []
    relative = ANDROID_CAMERA_LIFECYCLE_TEST_PATH.relative_to(ROOT)
    if test_text is None:
        try:
            test_text = ANDROID_CAMERA_LIFECYCLE_TEST_PATH.read_text(
                encoding="utf-8",
            )
        except (OSError, UnicodeError) as error:
            return [
                f"{relative} cannot be read for API matrix validation: "
                f"{error}"
            ]

    if test_text.count(ANDROID_CAMERA_LIFECYCLE_CONFIG) != 1:
        failures.append(
            f"{relative} must contain one exact API 26/30/33/36 "
            "Robolectric lifecycle matrix"
        )
    if test_text.count("@Config(sdk =") != 1:
        failures.append(
            f"{relative} must contain exactly one class-level SDK matrix"
        )
    return failures


def android_camera_lifecycle_source_self_test() -> list[str]:
    try:
        test_text = ANDROID_CAMERA_LIFECYCLE_TEST_PATH.read_text(
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as error:
        return [f"cannot load camera lifecycle source self-test: {error}"]
    mutated = test_text.replace(
        ANDROID_CAMERA_LIFECYCLE_CONFIG,
        "@Config(sdk = [26, 30, 33, 35])",
        1,
    )
    if mutated == test_text:
        return ["camera lifecycle API matrix self-test mutation did not apply"]
    if not android_camera_lifecycle_source_failures(mutated):
        return ["camera lifecycle API matrix mutation was not rejected"]
    return []


def android_camera_controller_host_source_failures(
    test_text: str | None = None,
) -> list[str]:
    failures: list[str] = []
    relative = ANDROID_CAMERA_CONTROLLER_HOST_TEST_PATH.relative_to(ROOT)
    if test_text is None:
        try:
            test_text = ANDROID_CAMERA_CONTROLLER_HOST_TEST_PATH.read_text(
                encoding="utf-8",
            )
        except (OSError, UnicodeError) as error:
            return [
                f"{relative} cannot be read for API matrix validation: "
                f"{error}"
            ]

    if test_text.count(ANDROID_CAMERA_CONTROLLER_HOST_CONFIG) != 1:
        failures.append(
            f"{relative} must contain one exact API 26/30/33/36 "
            "Robolectric controller-host matrix"
        )
    if test_text.count("@Config(sdk =") != 1:
        failures.append(
            f"{relative} must contain exactly one class-level SDK matrix"
        )
    if (
        test_text.count(
            "controllerHostRunsDenialRegrantRevocationAndResumeLifecycle"
        )
        != 1
    ):
        failures.append(
            f"{relative} must contain one exact controller-host lifecycle test"
        )
    return failures


def android_camera_controller_host_source_self_test() -> list[str]:
    try:
        test_text = ANDROID_CAMERA_CONTROLLER_HOST_TEST_PATH.read_text(
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as error:
        return [
            f"cannot load camera controller-host source self-test: {error}"
        ]
    mutated = test_text.replace(
        ANDROID_CAMERA_CONTROLLER_HOST_CONFIG,
        "@Config(sdk = [26, 30, 33, 35])",
        1,
    )
    if mutated == test_text:
        return [
            "camera controller-host API matrix self-test mutation did not apply"
        ]
    if not android_camera_controller_host_source_failures(mutated):
        return [
            "camera controller-host API matrix mutation was not rejected"
        ]
    return []


def android_font_scale_source_failures(
    test_text: str | None = None,
) -> list[str]:
    failures: list[str] = []
    relative = ANDROID_FONT_SCALE_TEST_PATH.relative_to(ROOT)
    if test_text is None:
        try:
            test_text = ANDROID_FONT_SCALE_TEST_PATH.read_text(
                encoding="utf-8",
            )
        except (OSError, UnicodeError) as error:
            return [
                f"{relative} cannot be read for font-scale validation: "
                f"{error}"
            ]

    exact_snippets = (
        (
            ANDROID_FONT_SCALE_CONFIG,
            "one exact Robolectric SDK 35 configuration",
        ),
        (
            ANDROID_FONT_SCALE_LIST,
            "one exact 100/150/200 percent font-scale tuple",
        ),
        (
            ANDROID_FONT_SCALE_LOCALES,
            "one exact five-locale smoke tuple",
        ),
        (
            ANDROID_FONT_SCALE_FULL_LOCALES,
            "one exact English/Korean full-coverage tuple",
        ),
        (
            "require(fontScale in canonicalFontScales)",
            "one canonical font-scale membership check",
        ),
        (
            "Density(density = baseDensity.density, fontScale = fontScale)",
            "one explicit Compose font-scale density",
        ),
        (
            "LocalDensity provides scaledDensity",
            "one Compose LocalDensity provider",
        ),
        (
            "check(LocalDensity.current.fontScale == fontScale)",
            "one in-composition font-scale assertion",
        ),
    )
    for snippet, contract in exact_snippets:
        if test_text.count(snippet) != 1:
            failures.append(f"{relative} must contain {contract}")

    if test_text.count("@Config(sdk =") != 1:
        failures.append(
            f"{relative} must contain exactly one class-level SDK config"
        )

    method_scales = (
        (ANDROID_FONT_SCALE_METHODS[0], "1f"),
        (ANDROID_FONT_SCALE_METHODS[1], "1.5f"),
        (ANDROID_FONT_SCALE_METHODS[2], "2f"),
    )
    for method, scale in method_scales:
        if test_text.count(f"fun {method}()") != 1:
            failures.append(
                f"{relative} must contain one exact {method} result"
            )
        if (
            test_text.count(
                f"fun {method}() {{\n"
                f"        runCoreSurfaceQualification(fontScale = {scale})\n"
                "    }"
            )
            != 1
        ):
            failures.append(
                f"{relative} must bind {method} to exact scale {scale}"
            )

    required_surface_cases = (
        "ScannerActive",
        "ScannerInvalid",
        "ScannerPermission",
        "ScannerSettingsRecovery",
        "DrawerEmpty",
        "DrawerPopulated",
        "DrawerSearchNoResults",
        "ChatPopulated",
        "ChatStreaming",
        "SettingsPairing",
        "SettingsData",
    )
    for surface_case in required_surface_cases:
        if test_text.count(f"SurfaceCase.{surface_case}") < 1:
            failures.append(
                f"{relative} must retain representative {surface_case} "
                "font-scale coverage"
            )
    return failures


def android_font_scale_source_self_test() -> list[str]:
    try:
        test_text = ANDROID_FONT_SCALE_TEST_PATH.read_text(
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as error:
        return [f"cannot load font-scale source self-test: {error}"]

    failures: list[str] = []
    mutations = (
        (
            "SDK configuration",
            ANDROID_FONT_SCALE_CONFIG,
            "@Config(sdk = [34])",
        ),
        (
            "100 percent scale",
            ANDROID_FONT_SCALE_LIST,
            "val canonicalFontScales = listOf(1.1f, 1.5f, 2f)",
        ),
        (
            "200 percent scale",
            ANDROID_FONT_SCALE_LIST,
            "val canonicalFontScales = listOf(1f, 1.5f, 1.6f)",
        ),
        (
            "150 percent scale",
            ANDROID_FONT_SCALE_LIST,
            "val canonicalFontScales = listOf(1f, 1.45f, 2f)",
        ),
        (
            "five-locale tuple",
            ANDROID_FONT_SCALE_LOCALES,
            'val supportedLanguageTags = listOf("en", "ko", "ja", "fr")',
        ),
        (
            "English/Korean full-coverage tuple",
            ANDROID_FONT_SCALE_FULL_LOCALES,
            'val fullCoverageLanguageTags = listOf("en")',
        ),
        (
            "Compose LocalDensity provider",
            "LocalDensity provides scaledDensity",
            "LocalDensity provides baseDensity",
        ),
        (
            "in-composition font-scale assertion",
            "check(LocalDensity.current.fontScale == fontScale)",
            "check(LocalDensity.current.fontScale == 1f)",
        ),
    )
    for label, source, replacement in mutations:
        mutated = test_text.replace(source, replacement, 1)
        if mutated == test_text:
            failures.append(
                f"font-scale {label} self-test mutation did not apply"
            )
        elif not android_font_scale_source_failures(mutated):
            failures.append(
                f"font-scale {label} mutation was not rejected"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--self-test",
        action="store_true",
        help="also prove representative contract mutations are rejected",
    )
    mode.add_argument(
        "--run-release-compliance-tests",
        action="store_true",
        help=(
            "run the exact release compliance test manifest and require "
            "zero skips, failures, and errors"
        ),
    )
    mode.add_argument(
        "--swift-test-selection",
        action="store_true",
        help="validate the exact focused Swift test selection",
    )
    mode.add_argument(
        "--prepare-swift-focused-test-run",
        action="store_true",
        help="bind current Swift source and selected tests before execution",
    )
    mode.add_argument(
        "--run-swift-focused-tests",
        action="store_true",
        help="run the exact serial focused Swift tests and retain console bytes",
    )
    mode.add_argument(
        "--write-swift-focused-test-binding",
        action="store_true",
        help="bind focused Swift console bytes to source and selected tests",
    )
    mode.add_argument(
        "--swift-focused-test-results",
        action="store_true",
        help="independently read back the focused Swift test binding",
    )
    mode.add_argument(
        "--prepare-g7-nonsecurity-swift-run",
        action="store_true",
        help="bind the exact expanded non-security Swift lane before execution",
    )
    mode.add_argument(
        "--run-g7-nonsecurity-swift-tests",
        action="store_true",
        help="run the exact network-denied 247-test non-security Swift lane",
    )
    mode.add_argument(
        "--write-g7-nonsecurity-swift-binding",
        action="store_true",
        help="bind the expanded Swift console to source and selected tests",
    )
    mode.add_argument(
        "--g7-nonsecurity-swift-results",
        action="store_true",
        help="independently read back the expanded Swift test binding",
    )
    mode.add_argument(
        "--prepare-document-ingestion-asan-run",
        action="store_true",
        help="bind the exact DocumentIngestion ASan corpus before execution",
    )
    mode.add_argument(
        "--run-document-ingestion-asan-tests",
        action="store_true",
        help="run the exact bounded DocumentIngestion ASan corpus",
    )
    mode.add_argument(
        "--write-document-ingestion-asan-binding",
        action="store_true",
        help="bind the ASan console to its source and test manifest",
    )
    mode.add_argument(
        "--document-ingestion-asan-results",
        action="store_true",
        help="independently read back the DocumentIngestion ASan binding",
    )
    mode.add_argument(
        "--prepare-document-ingestion-mutation-run",
        action="store_true",
        help=(
            "bind the exact DocumentIngestion mutation corpus before "
            "execution"
        ),
    )
    mode.add_argument(
        "--run-document-ingestion-mutation-tests",
        action="store_true",
        help="run the exact bounded DocumentIngestion mutation corpus",
    )
    mode.add_argument(
        "--write-document-ingestion-mutation-binding",
        action="store_true",
        help="bind all mutation case markers to source and console bytes",
    )
    mode.add_argument(
        "--document-ingestion-mutation-results",
        action="store_true",
        help="independently read back the mutation corpus binding",
    )
    mode.add_argument(
        "--android-test-results",
        action="store_true",
        help="validate the exact focused Android product JUnit results",
    )
    mode.add_argument(
        "--android-full-test-results",
        action="store_true",
        help="validate the exact complete Android app JUnit results",
    )
    mode.add_argument(
        "--prepare-android-full-test-run",
        action="store_true",
        help="bind current Android source bytes before the complete app run",
    )
    mode.add_argument(
        "--write-android-full-test-binding",
        action="store_true",
        help=(
            "bind complete Android app JUnit reports to current source bytes"
        ),
    )
    mode.add_argument(
        "--prepare-android-core-nonsecurity-test-run",
        action="store_true",
        help=(
            "bind current Android core source before the exact non-security "
            "test run"
        ),
    )
    mode.add_argument(
        "--run-android-core-nonsecurity-tests",
        action="store_true",
        help=(
            "run the exact offline Android core non-security method allowlist"
        ),
    )
    mode.add_argument(
        "--write-android-core-nonsecurity-test-binding",
        action="store_true",
        help=(
            "bind exact Android core non-security JUnit reports to source"
        ),
    )
    mode.add_argument(
        "--android-core-nonsecurity-test-results",
        action="store_true",
        help=(
            "independently read back Android core non-security JUnit bindings"
        ),
    )
    mode.add_argument(
        "--android-camera-lifecycle-results",
        action="store_true",
        help="validate the production camera lifecycle JUnit results",
    )
    mode.add_argument(
        "--android-camera-controller-host-results",
        action="store_true",
        help="validate the camera controller-host API matrix JUnit results",
    )
    mode.add_argument(
        "--android-font-scale-results",
        action="store_true",
        help="validate the exact Android font-scale JUnit results",
    )
    parser.add_argument(
        "--swift-focused-filter",
        help="exact filter accepted only by --run-swift-focused-tests",
    )
    args = parser.parse_args()

    if (
        args.swift_focused_filter is not None
        and not args.run_swift_focused_tests
    ):
        parser.error(
            "--swift-focused-filter requires --run-swift-focused-tests"
        )

    if args.run_release_compliance_tests:
        failures = run_release_compliance_tests()
        if failures:
            for failure in failures:
                print(
                    f"Release compliance test runner failed: {failure}",
                    file=sys.stderr,
                )
            return 1
        print(
            "Release compliance tests passed: "
            f"{RELEASE_COMPLIANCE_TEST_COUNT}/"
            f"{RELEASE_COMPLIANCE_TEST_COUNT}; skipped=0; failures=0; "
            "errors=0."
        )
        return 0

    if args.swift_test_selection:
        failures = swift_test_selection_failures()
        if failures:
            for failure in failures:
                print(
                    f"Swift product test selection failed: {failure}",
                    file=sys.stderr,
                )
            return 1
        print(
            "Swift product test selection passed: "
            f"{SWIFT_PRODUCT_TEST_COUNT}/{SWIFT_PRODUCT_TEST_COUNT}."
        )
        return 0

    if args.prepare_swift_focused_test_run:
        failures = swift_test_selection_failures()
        if not failures:
            failures.extend(write_swift_focused_test_run_marker())
        if failures:
            for failure in failures:
                print(
                    f"Swift focused test run preparation failed: {failure}",
                    file=sys.stderr,
                )
            return 1
        print(
            "Swift focused source marker written and read back: "
            f"{SWIFT_PRODUCT_TEST_COUNT} expected tests."
        )
        return 0

    if args.run_swift_focused_tests:
        if args.swift_focused_filter is None:
            print(
                "Swift focused test runner failed: exact filter is required",
                file=sys.stderr,
            )
            return 1
        status, failures = run_swift_focused_tests(
            filter_pattern=args.swift_focused_filter,
        )
        if failures:
            for failure in failures:
                print(
                    f"Swift focused test runner failed: {failure}",
                    file=sys.stderr,
                )
        if status != 0:
            if not failures:
                print(
                    f"Swift focused test runner exited with status {status}.",
                    file=sys.stderr,
                )
            return status
        print(
            "Swift focused serial test run passed and retained: "
            f"{SWIFT_PRODUCT_TEST_COUNT}/{SWIFT_PRODUCT_TEST_COUNT}."
        )
        return 0

    if (
        args.write_swift_focused_test_binding
        or args.swift_focused_test_results
    ):
        failures = (
            write_swift_focused_test_binding()
            if args.write_swift_focused_test_binding
            else swift_focused_test_binding_failures()
        )
        if failures:
            for failure in failures:
                print(
                    f"Swift focused test results failed: {failure}",
                    file=sys.stderr,
                )
            return 1
        action = (
            "binding written and read back"
            if args.write_swift_focused_test_binding
            else "independent binding readback passed"
        )
        print(
            f"Swift focused test {action}: "
            f"{SWIFT_PRODUCT_TEST_COUNT}/{SWIFT_PRODUCT_TEST_COUNT}; "
            "skipped=0; failures=0; errors=0."
        )
        return 0

    if args.prepare_g7_nonsecurity_swift_run:
        failures = g7_nonsecurity_swift_selection_failures()
        _, environment_failures = g7_nonsecurity_swift_environment()
        failures.extend(environment_failures)
        if not failures:
            failures.extend(
                write_swift_focused_test_run_marker(
                    marker_path=G7_NONSECURITY_SWIFT_RUN_MARKER_PATH,
                    filter_pattern=G7_NONSECURITY_SWIFT_FILTER,
                    expected_count=G7_NONSECURITY_SWIFT_TEST_COUNT,
                    expected_manifest_sha256=(
                        G7_NONSECURITY_SWIFT_TEST_MANIFEST_SHA256
                    ),
                    excluded_tests=G7_NONSECURITY_SWIFT_LIVE_TESTS,
                )
            )
        if failures:
            for failure in failures:
                print(
                    "G7 non-security Swift preparation failed: " + failure,
                    file=sys.stderr,
                )
            return 1
        print(
            "G7 non-security Swift source marker written and read back: "
            f"{G7_NONSECURITY_SWIFT_TEST_COUNT} selected tests; "
            f"{G7_NONSECURITY_SWIFT_LIVE_TEST_COUNT} live tests excluded."
        )
        return 0

    if args.run_g7_nonsecurity_swift_tests:
        status, failures = run_g7_nonsecurity_swift_tests()
        if failures:
            for failure in failures:
                print(
                    "G7 non-security Swift runner failed: " + failure,
                    file=sys.stderr,
                )
        if status != 0:
            if not failures:
                print(
                    "G7 non-security Swift runner exited with status "
                    f"{status}.",
                    file=sys.stderr,
                )
            return status
        print(
            "G7 non-security Swift run passed and retained: "
            f"{G7_NONSECURITY_SWIFT_TEST_COUNT}/"
            f"{G7_NONSECURITY_SWIFT_TEST_COUNT}; skipped=0; failures=0; "
            "errors=0; network denied."
        )
        return 0

    if (
        args.write_g7_nonsecurity_swift_binding
        or args.g7_nonsecurity_swift_results
    ):
        common_arguments = {
            "binding_path": G7_NONSECURITY_SWIFT_BINDING_PATH,
            "marker_path": G7_NONSECURITY_SWIFT_RUN_MARKER_PATH,
            "log_path": G7_NONSECURITY_SWIFT_LOG_PATH,
            "filter_pattern": G7_NONSECURITY_SWIFT_FILTER,
            "expected_count": G7_NONSECURITY_SWIFT_TEST_COUNT,
            "expected_manifest_sha256": (
                G7_NONSECURITY_SWIFT_TEST_MANIFEST_SHA256
            ),
            "excluded_tests": G7_NONSECURITY_SWIFT_LIVE_TESTS,
        }
        failures = (
            write_swift_focused_test_binding(**common_arguments)
            if args.write_g7_nonsecurity_swift_binding
            else swift_focused_test_binding_failures(**common_arguments)
        )
        if failures:
            for failure in failures:
                print(
                    "G7 non-security Swift results failed: " + failure,
                    file=sys.stderr,
                )
            return 1
        action = (
            "binding written and read back"
            if args.write_g7_nonsecurity_swift_binding
            else "independent binding readback passed"
        )
        print(
            f"G7 non-security Swift {action}: "
            f"{G7_NONSECURITY_SWIFT_TEST_COUNT}/"
            f"{G7_NONSECURITY_SWIFT_TEST_COUNT}; skipped=0; failures=0; "
            "errors=0."
        )
        return 0

    if args.prepare_document_ingestion_asan_run:
        failures = swift_test_selection_failures(
            filter_pattern=DOCUMENT_INGESTION_ASAN_FILTER,
            expected_count=DOCUMENT_INGESTION_ASAN_TEST_COUNT,
            expected_manifest_sha256=(
                DOCUMENT_INGESTION_ASAN_TEST_MANIFEST_SHA256
            ),
        )
        if not failures:
            failures.extend(write_swift_focused_test_run_marker(
                marker_path=DOCUMENT_INGESTION_ASAN_RUN_MARKER_PATH,
                filter_pattern=DOCUMENT_INGESTION_ASAN_FILTER,
                expected_count=DOCUMENT_INGESTION_ASAN_TEST_COUNT,
                expected_manifest_sha256=(
                    DOCUMENT_INGESTION_ASAN_TEST_MANIFEST_SHA256
                ),
            ))
        if failures:
            for failure in failures:
                print(
                    "DocumentIngestion ASan preparation failed: " + failure,
                    file=sys.stderr,
                )
            return 1
        print(
            "DocumentIngestion ASan source marker written and read back: "
            f"{DOCUMENT_INGESTION_ASAN_TEST_COUNT} expected tests."
        )
        return 0

    if args.run_document_ingestion_asan_tests:
        status, failures = run_document_ingestion_asan_tests()
        if failures:
            for failure in failures:
                print(
                    "DocumentIngestion ASan runner failed: " + failure,
                    file=sys.stderr,
                )
        if status != 0:
            if not failures:
                print(
                    "DocumentIngestion ASan runner exited with status "
                    f"{status}.",
                    file=sys.stderr,
                )
            return status
        print(
            "DocumentIngestion ASan run passed and retained: "
            f"{DOCUMENT_INGESTION_ASAN_TEST_COUNT}/"
            f"{DOCUMENT_INGESTION_ASAN_TEST_COUNT}."
        )
        return 0

    if (
        args.write_document_ingestion_asan_binding
        or args.document_ingestion_asan_results
    ):
        common_arguments = {
            "binding_path": DOCUMENT_INGESTION_ASAN_BINDING_PATH,
            "marker_path": DOCUMENT_INGESTION_ASAN_RUN_MARKER_PATH,
            "log_path": DOCUMENT_INGESTION_ASAN_LOG_PATH,
            "filter_pattern": DOCUMENT_INGESTION_ASAN_FILTER,
            "expected_count": DOCUMENT_INGESTION_ASAN_TEST_COUNT,
            "expected_manifest_sha256": (
                DOCUMENT_INGESTION_ASAN_TEST_MANIFEST_SHA256
            ),
        }
        failures = (
            write_swift_focused_test_binding(**common_arguments)
            if args.write_document_ingestion_asan_binding
            else swift_focused_test_binding_failures(**common_arguments)
        )
        if failures:
            for failure in failures:
                print(
                    "DocumentIngestion ASan results failed: " + failure,
                    file=sys.stderr,
                )
            return 1
        action = (
            "binding written and read back"
            if args.write_document_ingestion_asan_binding
            else "independent binding readback passed"
        )
        print(
            f"DocumentIngestion ASan {action}: "
            f"{DOCUMENT_INGESTION_ASAN_TEST_COUNT}/"
            f"{DOCUMENT_INGESTION_ASAN_TEST_COUNT}; skipped=0; "
            "failures=0; errors=0."
        )
        return 0

    if args.prepare_document_ingestion_mutation_run:
        failures = swift_test_selection_failures(
            filter_pattern=DOCUMENT_INGESTION_MUTATION_FILTER,
            expected_count=DOCUMENT_INGESTION_MUTATION_TEST_COUNT,
            expected_manifest_sha256=(
                DOCUMENT_INGESTION_MUTATION_TEST_MANIFEST_SHA256
            ),
        )
        if not failures:
            failures.extend(write_swift_focused_test_run_marker(
                marker_path=DOCUMENT_INGESTION_MUTATION_RUN_MARKER_PATH,
                filter_pattern=DOCUMENT_INGESTION_MUTATION_FILTER,
                expected_count=DOCUMENT_INGESTION_MUTATION_TEST_COUNT,
                expected_manifest_sha256=(
                    DOCUMENT_INGESTION_MUTATION_TEST_MANIFEST_SHA256
                ),
            ))
        if failures:
            for failure in failures:
                print(
                    "DocumentIngestion mutation preparation failed: "
                    + failure,
                    file=sys.stderr,
                )
            return 1
        print(
            "DocumentIngestion mutation source marker written and read back: "
            f"{DOCUMENT_INGESTION_MUTATION_TEST_COUNT} XCTest identities and "
            f"{DOCUMENT_INGESTION_MUTATION_CASE_COUNT} cases expected."
        )
        return 0

    if args.run_document_ingestion_mutation_tests:
        status, failures = run_document_ingestion_mutation_tests()
        if failures:
            for failure in failures:
                print(
                    "DocumentIngestion mutation runner failed: " + failure,
                    file=sys.stderr,
                )
        if status != 0:
            if not failures:
                print(
                    "DocumentIngestion mutation runner exited with status "
                    f"{status}.",
                    file=sys.stderr,
                )
            return status
        print(
            "DocumentIngestion mutation run passed and retained: "
            f"{DOCUMENT_INGESTION_MUTATION_TEST_COUNT}/"
            f"{DOCUMENT_INGESTION_MUTATION_TEST_COUNT} XCTest identities; "
            f"{DOCUMENT_INGESTION_MUTATION_CASE_COUNT}/"
            f"{DOCUMENT_INGESTION_MUTATION_CASE_COUNT} cases."
        )
        return 0

    if (
        args.write_document_ingestion_mutation_binding
        or args.document_ingestion_mutation_results
    ):
        common_arguments = {
            "binding_path": DOCUMENT_INGESTION_MUTATION_BINDING_PATH,
            "marker_path": DOCUMENT_INGESTION_MUTATION_RUN_MARKER_PATH,
            "log_path": DOCUMENT_INGESTION_MUTATION_LOG_PATH,
            "filter_pattern": DOCUMENT_INGESTION_MUTATION_FILTER,
            "expected_count": DOCUMENT_INGESTION_MUTATION_TEST_COUNT,
            "expected_manifest_sha256": (
                DOCUMENT_INGESTION_MUTATION_TEST_MANIFEST_SHA256
            ),
            "supplemental_console_key": "mutationCorpus",
            "supplemental_console_snapshot": (
                document_ingestion_mutation_console_snapshot
            ),
        }
        failures = (
            write_swift_focused_test_binding(**common_arguments)
            if args.write_document_ingestion_mutation_binding
            else swift_focused_test_binding_failures(**common_arguments)
        )
        if failures:
            for failure in failures:
                print(
                    "DocumentIngestion mutation results failed: " + failure,
                    file=sys.stderr,
                )
            return 1
        action = (
            "binding written and read back"
            if args.write_document_ingestion_mutation_binding
            else "independent binding readback passed"
        )
        print(
            f"DocumentIngestion mutation {action}: "
            f"{DOCUMENT_INGESTION_MUTATION_TEST_COUNT}/"
            f"{DOCUMENT_INGESTION_MUTATION_TEST_COUNT} XCTest identities; "
            f"{DOCUMENT_INGESTION_MUTATION_CASE_COUNT}/"
            f"{DOCUMENT_INGESTION_MUTATION_CASE_COUNT} cases; skipped=0; "
            "failures=0; errors=0."
        )
        return 0

    if args.prepare_android_core_nonsecurity_test_run:
        failures = prepare_android_core_nonsecurity_test_run()
        if failures:
            for failure in failures:
                print(
                    "Android core non-security preparation failed: "
                    + failure,
                    file=sys.stderr,
                )
            return 1
        print(
            "Android core non-security source markers written and read back: "
            f"{len(ANDROID_CORE_NONSECURITY_TESTS)} expected tests."
        )
        return 0

    if args.run_android_core_nonsecurity_tests:
        failures = run_android_core_nonsecurity_tests()
        if failures:
            for failure in failures:
                print(
                    "Android core non-security runner failed: " + failure,
                    file=sys.stderr,
                )
            return 1
        print(
            "Android core non-security offline run passed and retained: "
            f"{ANDROID_CORE_NONSECURITY_TEST_COUNT}/"
            f"{ANDROID_CORE_NONSECURITY_TEST_COUNT}."
        )
        return 0

    if (
        args.write_android_core_nonsecurity_test_binding
        or args.android_core_nonsecurity_test_results
    ):
        failures = (
            write_android_core_nonsecurity_test_bindings()
            if args.write_android_core_nonsecurity_test_binding
            else android_core_nonsecurity_test_result_failures(
                require_bindings=True,
            )
        )
        if failures:
            for failure in failures:
                print(
                    "Android core non-security test results failed: "
                    + failure,
                    file=sys.stderr,
                )
            return 1
        action = (
            "bindings written and read back"
            if args.write_android_core_nonsecurity_test_binding
            else "independent binding readback passed"
        )
        print(
            f"Android core non-security test {action}: "
            f"{len(ANDROID_CORE_NONSECURITY_TESTS)}/"
            f"{len(ANDROID_CORE_NONSECURITY_TESTS)}; skipped=0; "
            "failures=0; errors=0."
        )
        return 0

    if args.prepare_android_full_test_run:
        failures = (
            no_device_full_result_gate_failures()
            + android_app_language_lifecycle_source_failures()
            + android_camera_lifecycle_source_failures()
            + android_camera_controller_host_source_failures()
            + android_font_scale_source_failures()
        )
        if not failures:
            failures.extend(write_android_full_test_run_marker())
        if failures:
            for failure in failures:
                print(
                    f"Android full test run preparation failed: {failure}",
                    file=sys.stderr,
                )
            return 1
        print(
            "Android full app source marker written and read back: "
            f"{sum(count for _, count, _ in ANDROID_FULL_TEST_RESULTS)} "
            "expected tests."
        )
        return 0

    if (
        args.android_test_results
        or args.android_full_test_results
        or args.write_android_full_test_binding
        or args.android_camera_lifecycle_results
        or args.android_camera_controller_host_results
        or args.android_font_scale_results
    ):
        if args.android_test_results:
            expected_results = ANDROID_PRODUCT_TEST_RESULTS
            result_label = "Android product"
            allow_additional_methods = False
            require_exact_report_set = True
        elif args.android_full_test_results:
            expected_results = ANDROID_FULL_TEST_RESULTS
            result_label = "Android full app"
            allow_additional_methods = True
            require_exact_report_set = True
        elif args.write_android_full_test_binding:
            expected_results = ANDROID_FULL_TEST_RESULTS
            result_label = "Android full app"
            allow_additional_methods = True
            require_exact_report_set = True
        elif args.android_camera_lifecycle_results:
            expected_results = ANDROID_CAMERA_LIFECYCLE_TEST_RESULTS
            result_label = "Android product"
            allow_additional_methods = False
            require_exact_report_set = False
        elif args.android_camera_controller_host_results:
            expected_results = ANDROID_CAMERA_CONTROLLER_HOST_TEST_RESULTS
            result_label = "Android product"
            allow_additional_methods = False
            require_exact_report_set = False
        else:
            expected_results = ANDROID_FONT_SCALE_TEST_RESULTS
            result_label = "Android product"
            allow_additional_methods = False
            require_exact_report_set = False
        failures = (
            android_test_result_failures(
                expected_results,
                allow_additional_methods=allow_additional_methods,
                require_exact_report_set=require_exact_report_set,
                expected_testcase_manifest_sha256=(
                    ANDROID_FULL_TEST_CASE_MANIFEST_SHA256
                    if (
                        args.android_full_test_results
                        or args.write_android_full_test_binding
                    )
                    else (
                        ANDROID_PRODUCT_TEST_CASE_MANIFEST_SHA256
                        if args.android_test_results
                        else None
                    )
                ),
            )
            + android_app_language_lifecycle_source_failures()
            + android_camera_lifecycle_source_failures()
            + android_camera_controller_host_source_failures()
            + android_font_scale_source_failures()
        )
        if not failures and args.write_android_full_test_binding:
            failures.extend(write_android_full_test_binding())
        elif not failures and args.android_full_test_results:
            failures.extend(android_full_test_binding_failures())
        if failures:
            for failure in failures:
                print(
                    f"Android product test results failed: {failure}",
                    file=sys.stderr,
                )
            return 1
        if args.write_android_full_test_binding:
            print(
                "Android full app test result binding written and read back: "
                f"{sum(count for _, count, _ in expected_results)}/"
                f"{sum(count for _, count, _ in expected_results)}."
            )
            return 0
        total = sum(count for _, count, _ in expected_results)
        print(
            f"{result_label} test results passed: "
            f"{total}/{total}; skipped=0; failures=0; errors=0."
        )
        return 0

    try:
        workflow = WORKFLOW_PATH.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as error:
        print(f"Product CI contract failed: {error}", file=sys.stderr)
        return 1

    failures = (
        workflow_failures(workflow)
        + no_device_full_result_gate_failures()
        + product_copy_font_scale_guard_failures()
        + android_app_language_lifecycle_source_failures()
        + android_camera_lifecycle_source_failures()
        + android_camera_controller_host_source_failures()
        + android_font_scale_source_failures()
        + android_core_nonsecurity_selection_failures()
    )
    if args.self_test and not failures:
        failures.extend(self_test(workflow))
        failures.extend(release_compliance_test_runner_self_test())
        failures.extend(android_app_language_lifecycle_source_self_test())
        failures.extend(android_camera_lifecycle_source_self_test())
        failures.extend(android_camera_controller_host_source_self_test())
        failures.extend(android_font_scale_source_self_test())
        failures.extend(swift_test_selection_self_test())
        failures.extend(g7_nonsecurity_swift_contract_self_test())
        failures.extend(g7_nonsecurity_swift_network_sandbox_self_test())
        failures.extend(swift_focused_result_self_test())
        failures.extend(swift_runner_timeout_self_test())
        failures.extend(swift_runner_signal_self_test())
        failures.extend(document_ingestion_mutation_console_self_test())
        failures.extend(
            document_ingestion_mutation_failure_context_self_test()
        )
        failures.extend(android_result_freshness_self_test())
        failures.extend(no_device_full_result_gate_self_test())
        failures.extend(product_copy_font_scale_guard_self_test())

    if failures:
        for failure in failures:
            print(f"Product CI contract failed: {failure}", file=sys.stderr)
        return 1

    suffix = " and self-test" if args.self_test else ""
    print(f"Product CI contract{suffix} passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
