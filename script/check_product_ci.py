#!/usr/bin/env python3
"""Validate the bounded G7 non-security product CI subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Optional
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
    "01f5790886f5fb47647369ad5a003cdd47e5f87bb5a9b2e1dd1e4a17fd4120d0"
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
    "56c2417d0294e7da5ff27a904036cae94668699ed83447b2214a72b2858714ef"
)
CANONICAL_PARSED_WORKFLOW_SHA256 = (
    "563cf577cc6bea780633a99bb73416cfbdafa416cde9d0125056baeef5307305"
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

SWIFT_FILTER = (
    "DocumentIngestorTests|DocumentTextExtractorTests|DocumentChunkerTests|"
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

ANDROID_TASKS = (
    ":app:compileDebugKotlin",
    ":app:compileDebugUnitTestKotlin",
    ":app:testDebugUnitTest",
    ":app:assembleRelease",
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
)

ANDROID_RESULT_FRESHNESS_ROOTS = (
    ROOT / "apps/android/app/src/main",
    ROOT / "apps/android/app/src/test",
    ROOT / "apps/android/core/pairing/src/main",
    ROOT / "apps/android/core/protocol/src/main",
    ROOT / "apps/android/core/transport/src/main",
)

SWIFT_TEST_STEP_BODY = (
    "        run: >-\n"
    "          swift test\n"
    "          --filter\n"
    f"          '{SWIFT_FILTER}'\n"
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

ANDROID_RELEASE_STEP_BODY = (
    "        if: >-\n"
    f"          {MAIN_RELEASE_CONDITION}\n"
    "        run: >-\n"
    "          ./gradlew\n"
    "          --no-daemon\n"
    "          --console=plain\n"
    "          -PaetherlinkStrictReleaseDependencyLocks=true\n"
    "          -Pkotlin.incremental=false\n"
    "          :app:assembleRelease\n"
    "          :app:lintRelease\n"
)

MACOS_JOB_PREAMBLE = (
    "    name: macOS product quality subset\n"
    "    runs-on: macos-26\n"
    "    timeout-minutes: 45\n"
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
        "Run product static checks",
        "        run: |\n"
        "          python3 -B script/check_copy_hygiene.py --product-copy-only\n"
        "          python3 -B script/check_release_version_ledger.py\n"
        "          python3 -B script/check_app_icons.py\n"
        "          python3 -B script/check_license.py\n",
    ),
    (
        "Compile macOS app",
        "        run: swift build --product AetherLink\n",
    ),
    ("Run focused product units", SWIFT_TEST_STEP_BODY),
    (
        "Compile macOS Release app on main",
        "        if: >-\n"
        f"          {MAIN_RELEASE_CONDITION}\n"
        "        run: swift build -c release --product AetherLink\n",
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
        "          ./gradlew --version\n",
    ),
    (
        "Run release archive contract units",
        "        run: PYTHONPATH=. python3 -B "
        "script/test_release_artifact_archive.py\n",
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
        "Compile and lint Android Release app on main",
        ANDROID_RELEASE_STEP_BODY,
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
    "Android bundle signing path": r":app:bundleRelease\b",
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
            "timeout-minutes: 45",
            "DEVELOPER_DIR: /Applications/Xcode_26.6.app/Contents/Developer",
            "fetch-depth: 0",
            "xcodebuild -version",
            'git diff --check "$BASE_SHA" "$HEAD_SHA"',
            "python3 -B script/check_product_ci.py",
            "python3 -B script/check_product_ci.py --self-test",
            "python3 -B script/check_copy_hygiene.py --product-copy-only",
            "python3 -B script/check_release_version_ledger.py",
            "python3 -B script/check_app_icons.py",
            "python3 -B script/check_license.py",
            "run: swift build --product AetherLink",
            f"'{SWIFT_FILTER}'",
            MAIN_RELEASE_CONDITION,
            "run: swift build -c release --product AetherLink",
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
            MAIN_RELEASE_CONDITION,
            "-PaetherlinkStrictReleaseDependencyLocks=true",
            ":app:assembleRelease",
            ":app:lintRelease",
        ),
    )

    if workflow.count("swift test") != 1:
        failures.append("workflow must contain one focused Swift test command")
    product_copy_command = (
        "python3 -B script/check_copy_hygiene.py --product-copy-only"
    )
    if workflow.count(product_copy_command) != 1:
        failures.append(
            "workflow must contain one exact non-security product copy command"
        )
    if f"'{SWIFT_FILTER}'" not in macos:
        failures.append("Swift tests must use the exact product allowlist")
    if (
        named_step_body(macos, "Run focused product units")
        != SWIFT_TEST_STEP_BODY
    ):
        failures.append("Swift focused test step must match the exact command body")
    if len(re.findall(r"(?<![\w-])--filter(?:\s|=)", macos)) != 1:
        failures.append("Swift tests must contain exactly one filter option")
    if re.search(r"(?<![\w-])--skip(?:\s|=)", macos):
        failures.append("Swift focused tests must not use a skip option")

    strict_flag = "-PaetherlinkStrictReleaseDependencyLocks=true"
    release_index = android.find(MAIN_RELEASE_CONDITION)
    if release_index < 0:
        failures.append("Android Release step must be main-push-only")
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
    if android_tests != ANDROID_TESTS:
        failures.append("Android product tests must use the exact allowlist")

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
            "Compile and lint Android Release app on main",
        )
        != ANDROID_RELEASE_STEP_BODY
    ):
        failures.append(
            "Android Release step must match the exact command body"
        )

    android_tasks = tuple(
        re.findall(r"(?m)^\s+(:[A-Za-z0-9][A-Za-z0-9:_-]*)\s*$", android)
    )
    if android_tasks != ANDROID_TASKS:
        failures.append("Android Gradle tasks must match the exact product task list")
    if re.search(r"(?m)^\s+(?:build|check|test|assemble|lint)\s*$", android):
        failures.append("Android must not run a broad Gradle lifecycle task")
    if re.search(
        r"(?<!\S)(?:-x|--exclude-task|--dry-run|-m)(?=\s|=|$)",
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
                "run: swift build -c release --product AetherLink",
                "run: swift test\n"
                "      - run: swift build -c release --product AetherLink",
                1,
            ),
            "one focused Swift test command",
        ),
        "extra Swift filter": (
            workflow.replace(
                "          --filter\n",
                "          --filter ExtraProductTests\n"
                "          --filter\n",
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
                "          --filter\n",
                "          --skip '.*'\n"
                "          --filter\n",
                1,
            ),
            "skip option",
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
                "      - name: Compile and lint Android Release app on main\n",
                "      - name: Run unfiltered Android units\n"
                "        run: ./gradlew :app:testDebugUnitTest\n"
                "      - name: Compile and lint Android Release app on main\n",
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
        "Android bundle path": (
            workflow.replace(
                "          :app:assembleRelease\n",
                "          :app:assembleRelease\n"
                "          :app:bundleRelease\n",
                1,
            ),
            "Android bundle signing path",
        ),
        "live backend enablement": (
            workflow.replace(
                "    timeout-minutes: 45\n",
                "    timeout-minutes: 45\n"
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


def android_testcase_manifest_sha256(
    testcases: list[tuple[str, str]],
) -> str:
    payload = json.dumps(
        sorted(testcases),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


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
                    "match the exact full-suite contract"
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
                "must match the exact full-suite contract"
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
) -> tuple[dict[str, object] | None, list[str]]:
    source_snapshot, failures = android_result_source_snapshot(
        exact_files=exact_files,
        source_roots=source_roots,
    )
    if source_snapshot is None:
        return None, failures
    return (
        {
            "contract": ANDROID_FULL_TEST_RUN_MARKER_CONTRACT,
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
    require_reports: bool = True,
) -> list[str]:
    expected_payload, failures = android_full_test_run_marker_payload(
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
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
) -> list[str]:
    payload, failures = android_full_test_run_marker_payload()
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
            "contract": ANDROID_FULL_TEST_BINDING_CONTRACT,
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
) -> list[str]:
    marker_failures = android_full_test_run_marker_failures(
        result_root=result_root,
        marker_path=marker_path,
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
    )
    expected_payload, payload_failures = android_full_test_binding_payload(
        result_root=result_root,
        marker_path=marker_path,
        exact_files=exact_files,
        source_roots=source_roots,
        expected_results=expected_results,
        testcase_manifest_sha256=testcase_manifest_sha256,
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
) -> list[str]:
    failures = android_full_test_run_marker_failures(
        result_root=result_root,
        marker_path=marker_path,
    )
    if failures:
        return failures
    payload, payload_failures = android_full_test_binding_payload(
        result_root=result_root,
        marker_path=marker_path,
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
            )
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
                "result report set must match the exact full-suite contract"
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
ANDROID_FULL_RUNNER_SELECTORS = (
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
                "localeManager().applicationLocales = LocaleList.forLanguageTags(",
                "ActivityScenario.launch(MainActivity::class.java)",
                "awaitStoredLanguage(",
                "assertPlatformLanguage(",
                "scenario.recreate()",
                "assertNotSame(firstActivity, recreatedActivity)",
                "val coldScenario = ActivityScenario.launch(MainActivity::class.java)",
            ),
            (
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
            (
                "localeManager().applicationLocales = LocaleList.forLanguageTags(",
                (0,),
            ),
            ("ActivityScenario.launch(MainActivity::class.java)", (0, 0)),
            ("awaitStoredLanguage(", (1, 1)),
            ("assertPlatformLanguage(", (1, 1, 1)),
            ("scenario.recreate()", (1,)),
            ("assertNotSame(firstActivity, recreatedActivity)", (1,)),
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
    args = parser.parse_args()

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
            require_exact_report_set = False
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
                    else None
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
    )
    if args.self_test and not failures:
        failures.extend(self_test(workflow))
        failures.extend(android_app_language_lifecycle_source_self_test())
        failures.extend(android_camera_lifecycle_source_self_test())
        failures.extend(android_camera_controller_host_source_self_test())
        failures.extend(android_font_scale_source_self_test())
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
