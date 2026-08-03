#!/usr/bin/env python3
"""Produce one local G7 non-security Merge-full candidate result.

This deliberately does not execute the repository-wide no-device gate or any
security/authentication/G2 qualification.  It composes the existing bounded
product gates and publishes the parent result only after every child result is
independently read back against one unchanged source snapshot.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from typing import Iterable, Iterator, Sequence
import uuid
import xml.etree.ElementTree as ET

if __package__:
    from script import check_product_ci as product_ci
    from script import package_release_artifacts as package_release
    from script import check_release_artifact_archive as archive
    from script import run_clean_release_reproducibility as release_repro
    from script import run_android_release_repeatability_current as android_repeatability
    from script import run_release_diagnostics_usability as diagnostics
else:
    import check_product_ci as product_ci
    import package_release_artifacts as package_release
    import check_release_artifact_archive as archive
    import run_clean_release_reproducibility as release_repro
    import run_android_release_repeatability_current as android_repeatability
    import run_release_diagnostics_usability as diagnostics


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-local-candidate-v1"
SCHEMA_VERSION = 1
SOURCE_ALGORITHM = "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json"
)
RESULT_MAX_BYTES = 1024 * 1024
COMMAND_OUTPUT_MAX_BYTES = 64 * 1024 * 1024
COMMAND_TERMINATION_GRACE_SECONDS = 5.0
FILE_MAX_BYTES = 1024 * 1024 * 1024
SOURCE_FILE_MAX_BYTES = 64 * 1024 * 1024
SOURCE_TOTAL_MAX_BYTES = 1024 * 1024 * 1024
ARTIFACT_MAX_BYTES = 768 * 1024 * 1024
IMPLEMENTATION_MAX_BYTES = 4 * 1024 * 1024
ANDROID_STUDIO_JAVA_HOME = Path(
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
)
DEFAULT_ANDROID_HOME = Path.home() / "Library/Android/sdk"
MACOS_RELEASE_SCRATCH_ENVIRONMENT = "AETHERLINK_REPRO_SWIFT_SCRATCH_PATH"
MACOS_RELEASE_SCRATCH_PATH = Path(
    "/private/tmp/aetherlink-g6-swift-scratch-v1"
)
MACOS_UNSEALED_PACKAGE_COMMAND = (
    "/usr/bin/env",
    f"{MACOS_RELEASE_SCRATCH_ENVIRONMENT}={MACOS_RELEASE_SCRATCH_PATH}",
    "./script/build_and_run.sh",
    "--unsealed-package-only",
)
MACOS_LIFECYCLE_RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/"
    "macos-current-unsealed-lifecycle-v5/result.json"
)
MACOS_LIFECYCLE_REPEATABILITY_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/"
    "macos-current-unsealed-lifecycle-v5/repeatability.json"
)
ANDROID_RELEASE_REPEATABILITY_RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/"
    "android-release-repeatability-v1/result.json"
)
MACOS_CURRENT_SOURCE_IDLE_PARENT_RELATIVE_PATH = Path(
    "dist/reproducibility/"
    "aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication-"
    "current-source-g7-idle-repeatability-seven.json"
)
MACOS_CURRENT_SOURCE_IDLE_RUN_A_RELATIVE_PATH = Path(
    "dist/lifecycle/"
    "macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-"
    "idle-resource-stability-v1-"
    "current-source-g7-idle-repeatability-seven.json"
)
MACOS_CURRENT_SOURCE_IDLE_RUN_B_RELATIVE_PATH = Path(
    "dist/lifecycle/"
    "macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-"
    "idle-resource-stability-repeat-v1-"
    "current-source-g7-idle-repeatability-seven.json"
)
MACOS_CURRENT_SOURCE_IDLE_RECEIPT_RELATIVE_PATH = Path(
    "dist/lifecycle/"
    "macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-"
    "idle-resource-stability-repeatability-v1-"
    "current-source-g7-idle-repeatability-seven.json"
)
MACOS_CURRENT_SOURCE_IDLE_REPEATABILITY_READBACK_COMMAND = (
    "python3",
    "-I",
    "-B",
    "-S",
    "script/check_macos_current_source_lane_a_idle_resource_repeatability.py",
    "--parent-result",
    MACOS_CURRENT_SOURCE_IDLE_PARENT_RELATIVE_PATH.as_posix(),
    "--run-a",
    MACOS_CURRENT_SOURCE_IDLE_RUN_A_RELATIVE_PATH.as_posix(),
    "--run-b",
    MACOS_CURRENT_SOURCE_IDLE_RUN_B_RELATIVE_PATH.as_posix(),
    "--receipt",
    MACOS_CURRENT_SOURCE_IDLE_RECEIPT_RELATIVE_PATH.as_posix(),
)

LIMITATIONS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "deviceOrNetworkClaimed": False,
    "hostedCiClaimed": False,
    "securityAuthenticationCryptographyExecuted": False,
    "signedArtifactsClaimed": False,
    "v1Claimed": False,
}

COVERAGE = {
    "androidCoreNonsecurityClasses": 2,
    "androidCoreNonsecurityProtocolTests": 96,
    "androidCoreNonsecurityTests": 112,
    "androidCoreNonsecurityTransportTests": 16,
    "androidFullAppClasses": 19,
    "androidFullAppTests": 1226,
    "androidLintIssues": 0,
    "documentIngestionAsanTests": 57,
    "documentIngestionMutationCases": 96,
    "documentIngestionMutationXctestTests": 2,
    "releaseComplianceTests": 22,
    "macosRecordedCurrentSourceIdleObservationRuns": 2,
    "macosRecordedCurrentSourceIdleRepeatabilityReceipts": 1,
    "macosRecordedCurrentSourceIdleResourceSamples": 240,
    "swiftCurrentDiscoveryTests": 2175,
    "swiftCurrentNoSocketTests": 1204,
    "swiftCurrentParentRemainingTests": 967,
    "swiftCurrentParentReviewedTests": 1208,
    "swiftCurrentParentSocketContributionTests": 4,
    "swiftDistinctNonsecurityTests": 397,
    "swiftExpandedNonsecurityTests": 247,
    "swiftFocusedTests": 222,
}

IMPLEMENTATION_PATHS = tuple(
    Path(value)
    for value in (
        "script/check_android_release_repeatability_current.py",
        "script/check_g7_nonsecurity_merge_full_candidate.py",
        "script/check_g7_nonsecurity_merge_full_current.py",
        "script/check_macos_current_source_lane_a_idle_resource_repeatability.py",
        "script/g7_reviewed_nonsecurity_swift_addon_identities_v5.txt",
        "script/g7_reviewed_nonsecurity_swift_addon_identities_v6.txt",
        "script/run_android_release_repeatability_current.py",
        "script/run_clean_release_reproducibility.py",
        "script/run_g7_nonsecurity_merge_full_candidate.py",
        "script/run_g7_nonsecurity_merge_full_current.py",
        "script/run_macos_current_source_lane_a_idle_resource_stability_smoke.py",
        "script/test_check_android_release_repeatability_current.py",
        "script/test_check_g7_nonsecurity_merge_full_candidate.py",
        "script/test_check_g7_nonsecurity_merge_full_current.py",
        "script/test_check_macos_current_source_lane_a_idle_resource_repeatability.py",
        "script/test_run_android_release_repeatability_current.py",
        "script/test_run_g7_nonsecurity_merge_full_candidate.py",
        "script/test_run_g7_nonsecurity_merge_full_current.py",
        "script/test_run_macos_current_source_lane_a_idle_resource_stability_smoke.py",
    )
)

ARTIFACT_PATHS = tuple(
    Path(value)
    for value in (
        ".build/aetherlink-document-ingestion-asan-binding-v1.json",
        ".build/aetherlink-document-ingestion-asan-console-v1.log",
        ".build/aetherlink-document-ingestion-asan-run-marker-v1.json",
        ".build/aetherlink-document-ingestion-mutation-binding-v1.json",
        ".build/aetherlink-document-ingestion-mutation-console-v1.log",
        ".build/aetherlink-document-ingestion-mutation-run-marker-v1.json",
        ANDROID_RELEASE_REPEATABILITY_RESULT_RELATIVE_PATH.as_posix(),
        MACOS_LIFECYCLE_REPEATABILITY_RELATIVE_PATH.as_posix(),
        MACOS_LIFECYCLE_RESULT_RELATIVE_PATH.as_posix(),
        (
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "binding.json"
        ),
        (
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "console.log"
        ),
        (
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "execution-contract.json"
        ),
        (
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "parent-result.json"
        ),
        (
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "result.json"
        ),
        (
            ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
            "run-marker.json"
        ),
        ".build/aetherlink-g7-nonsecurity-swift-binding-v1.json",
        ".build/aetherlink-g7-nonsecurity-swift-console-v1.log",
        ".build/aetherlink-g7-nonsecurity-swift-run-marker-v1.json",
        ".build/aetherlink-product-ci-swift-focused-binding-v1.json",
        ".build/aetherlink-product-ci-swift-focused-console-v1.log",
        ".build/aetherlink-product-ci-swift-focused-run-marker-v1.json",
        ".build/aetherlink-product-ci-swift-test-list-v1.txt",
        ".build/aetherlink-release-diagnostics-v1/android.json",
        ".build/aetherlink-release-diagnostics-v1/macos.json",
        "apps/android/app/build/aetherlink-full-test-run-marker-v1.json",
        "apps/android/app/build/outputs/apk/release/app-release-unsigned.apk",
        "apps/android/app/build/outputs/bundle/release/app-release.aab",
        "apps/android/app/build/outputs/mapping/release/mapping.txt",
        "apps/android/app/build/reports/lint-results-release.xml",
        (
            "apps/android/app/build/test-results/testDebugUnitTest/"
            "aetherlink-full-test-result-binding-v1.json"
        ),
        (
            "apps/android/core/protocol/build/"
            "aetherlink-core-nonsecurity-test-run-marker-v1.json"
        ),
        (
            "apps/android/core/protocol/build/test-results/"
            "testDebugUnitTest/"
            "aetherlink-core-nonsecurity-test-result-binding-v1.json"
        ),
        (
            "apps/android/core/transport/build/"
            "aetherlink-core-nonsecurity-test-run-marker-v1.json"
        ),
        (
            "apps/android/core/transport/build/test-results/"
            "testDebugUnitTest/"
            "aetherlink-core-nonsecurity-test-result-binding-v1.json"
        ),
        MACOS_CURRENT_SOURCE_IDLE_RUN_B_RELATIVE_PATH.as_posix(),
        MACOS_CURRENT_SOURCE_IDLE_RECEIPT_RELATIVE_PATH.as_posix(),
        MACOS_CURRENT_SOURCE_IDLE_RUN_A_RELATIVE_PATH.as_posix(),
        MACOS_CURRENT_SOURCE_IDLE_PARENT_RELATIVE_PATH.as_posix(),
        "dist/unsealed-package-only/AetherLink.app/Contents/MacOS/AetherLink",
        (
            "dist/unsealed-package-only/AetherLink.dSYM/Contents/Resources/"
            "DWARF/AetherLink"
        ),
        "dist/unsealed-package-only/source-receipt.json",
    )
)


class CandidateError(RuntimeError):
    """Raised when a child gate cannot form a successful candidate."""


@dataclass(frozen=True)
class Gate:
    identifier: str
    argv: tuple[str, ...]
    timeout_seconds: int
    stdout_path: Path | None = None


def python_gate(
    identifier: str,
    *arguments: str,
    timeout_seconds: int = 600,
) -> Gate:
    return Gate(identifier, ("python3", "-B", *arguments), timeout_seconds)


DOCUMENTATION_TESTS = tuple(product_ci.TRACKED_DOCUMENTATION_CONTRACT_TESTS)

STATIC_GATES = (
    python_gate("product-ci-contract", "script/check_product_ci.py"),
    python_gate(
        "product-ci-contract-self-test",
        "script/check_product_ci.py",
        "--self-test",
    ),
    python_gate("nightly-contract", "script/check_product_nightly_ci.py"),
    Gate(
        "nightly-contract-tests",
        (
            "python3",
            "-B",
            "script/check_product_nightly_ci.py",
            "--run-contract-tests",
        ),
        900,
    ),
    python_gate(
        "product-copy",
        "script/check_copy_hygiene.py",
        "--product-copy-only",
    ),
    python_gate("release-ledger", "script/check_release_version_ledger.py"),
    python_gate("app-icons", "script/check_app_icons.py"),
    python_gate("license", "script/check_license.py"),
    python_gate(
        "release-compliance-catalog",
        "script/generate_release_compliance.py",
        "check",
    ),
    python_gate(
        "release-compliance-tests",
        "script/check_product_ci.py",
        "--run-release-compliance-tests",
        timeout_seconds=900,
    ),
    python_gate(
        "tracked-document-contracts",
        "script/check_docs_hygiene.py",
        "--tracked-contracts-only",
        timeout_seconds=900,
    ),
    Gate(
        "tracked-document-contract-tests",
        ("python3", "-B", "-m", "unittest", *DOCUMENTATION_TESTS),
        900,
    ),
    Gate(
        "macos-package-contract-tests",
        ("python3", "-B", "script/test_build_and_run.py"),
        900,
    ),
    Gate(
        "macos-lifecycle-contract-tests",
        (
            "python3",
            "-B",
            "-m",
            "unittest",
            "script.test_run_macos_current_unsealed_install_recovery_smoke",
            (
                "script.test_check_macos_current_unsealed_install_recovery_"
                "evidence.CurrentUnsealedRecoveryEvidencePortableTests"
            ),
            "script.test_check_macos_current_unsealed_ci_lifecycle",
            (
                "script.test_run_macos_runtime_chat_production_append_"
                "abrupt_recovery_smoke"
            ),
            (
                "script.test_check_macos_runtime_chat_production_append_"
                "abrupt_recovery_evidence"
            ),
            (
                "script.test_run_macos_current_source_lane_a_"
                "idle_resource_stability_smoke"
            ),
            (
                "script.test_check_macos_current_source_lane_a_"
                "idle_resource_repeatability"
            ),
        ),
        1200,
    ),
    Gate(
        "release-diagnostics-contract-tests",
        (
            "python3",
            "-B",
            "-m",
            "unittest",
            "script.test_run_release_diagnostics_usability",
            "script.test_check_release_diagnostics_usability",
        ),
        900,
    ),
    Gate(
        "release-archive-contract-tests",
        ("python3", "-B", "script/test_release_artifact_archive.py"),
        1200,
    ),
    Gate(
        "android-release-repeatability-contract-tests",
        (
            "python3",
            "-B",
            "-m",
            "unittest",
            "script.test_run_android_release_repeatability_current",
            "script.test_check_android_release_repeatability_current",
        ),
        900,
    ),
    Gate(
        "g7-candidate-contract-tests",
        (
            "python3",
            "-B",
            "-m",
            "unittest",
            "script.test_run_g7_nonsecurity_merge_full_candidate",
            "script.test_check_g7_nonsecurity_merge_full_candidate",
        ),
        900,
    ),
    Gate(
        "g7-current-contract-tests",
        (
            "python3",
            "-B",
            "-m",
            "unittest",
            "script.test_run_g7_nonsecurity_merge_full_current",
            "script.test_check_g7_nonsecurity_merge_full_current",
        ),
        900,
    ),
)

SWIFT_GATES = (
    Gate(
        "macos-debug-compile",
        ("swift", "build", "--product", "AetherLink"),
        1200,
    ),
    Gate(
        "swift-test-list",
        ("swift", "test", "list"),
        1200,
        Path(".build/aetherlink-product-ci-swift-test-list-v1.txt"),
    ),
    python_gate(
        "swift-selection-readback",
        "script/check_product_ci.py",
        "--swift-test-selection",
    ),
    python_gate(
        "swift-focused-prepare",
        "script/check_product_ci.py",
        "--prepare-swift-focused-test-run",
    ),
    Gate(
        "swift-focused-run",
        (
            "python3",
            "-B",
            "script/check_product_ci.py",
            "--run-swift-focused-tests",
            "--swift-focused-filter",
            product_ci.SWIFT_FILTER,
        ),
        1500,
    ),
    python_gate(
        "swift-focused-bind",
        "script/check_product_ci.py",
        "--write-swift-focused-test-binding",
    ),
    python_gate(
        "swift-focused-readback",
        "script/check_product_ci.py",
        "--swift-focused-test-results",
    ),
    python_gate(
        "g7-nonsecurity-swift-prepare",
        "script/check_product_ci.py",
        "--prepare-g7-nonsecurity-swift-run",
    ),
    python_gate(
        "g7-nonsecurity-swift-run",
        "script/check_product_ci.py",
        "--run-g7-nonsecurity-swift-tests",
        timeout_seconds=1500,
    ),
    python_gate(
        "g7-nonsecurity-swift-bind",
        "script/check_product_ci.py",
        "--write-g7-nonsecurity-swift-binding",
    ),
    python_gate(
        "g7-nonsecurity-swift-readback",
        "script/check_product_ci.py",
        "--g7-nonsecurity-swift-results",
    ),
    python_gate(
        "g7-current-prepare",
        "script/run_g7_nonsecurity_merge_full_current.py",
        "--prepare",
    ),
    python_gate(
        "g7-current-run",
        "script/run_g7_nonsecurity_merge_full_current.py",
        "--run",
        timeout_seconds=2100,
    ),
    python_gate(
        "g7-current-bind",
        "script/run_g7_nonsecurity_merge_full_current.py",
        "--write-binding",
    ),
    python_gate(
        "g7-current-readback",
        "script/run_g7_nonsecurity_merge_full_current.py",
        "--results",
    ),
    Gate(
        "g7-current-independent-readback",
        (
            "python3",
            "-I",
            "-B",
            "-S",
            "script/check_g7_nonsecurity_merge_full_current.py",
            (
                ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
                "result.json"
            ),
        ),
        600,
    ),
    python_gate(
        "g7-current-parent-bind",
        "script/run_g7_nonsecurity_merge_full_current.py",
        "--write-parent",
    ),
    python_gate(
        "g7-current-parent-readback",
        "script/run_g7_nonsecurity_merge_full_current.py",
        "--parent-results",
    ),
    Gate(
        "g7-current-parent-independent-readback",
        (
            "python3",
            "-I",
            "-B",
            "-S",
            "script/check_g7_nonsecurity_merge_full_current.py",
            "--parent",
            (
                ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
                "parent-result.json"
            ),
        ),
        600,
    ),
    python_gate(
        "document-ingestion-asan-prepare",
        "script/check_product_ci.py",
        "--prepare-document-ingestion-asan-run",
    ),
    python_gate(
        "document-ingestion-asan-run",
        "script/check_product_ci.py",
        "--run-document-ingestion-asan-tests",
        timeout_seconds=900,
    ),
    python_gate(
        "document-ingestion-asan-bind",
        "script/check_product_ci.py",
        "--write-document-ingestion-asan-binding",
    ),
    python_gate(
        "document-ingestion-asan-readback",
        "script/check_product_ci.py",
        "--document-ingestion-asan-results",
    ),
    python_gate(
        "document-ingestion-mutation-prepare",
        "script/check_product_ci.py",
        "--prepare-document-ingestion-mutation-run",
    ),
    python_gate(
        "document-ingestion-mutation-run",
        "script/check_product_ci.py",
        "--run-document-ingestion-mutation-tests",
        timeout_seconds=600,
    ),
    python_gate(
        "document-ingestion-mutation-bind",
        "script/check_product_ci.py",
        "--write-document-ingestion-mutation-binding",
    ),
    python_gate(
        "document-ingestion-mutation-readback",
        "script/check_product_ci.py",
        "--document-ingestion-mutation-results",
    ),
)

ANDROID_FULL_COMMAND = (
    "./gradlew",
    "--offline",
    "--no-daemon",
    "--console=plain",
    "--rerun-tasks",
    "-Pkotlin.incremental=false",
    ":app:compileDebugKotlin",
    ":app:testDebugUnitTest",
    *tuple(
        argument
        for test_name in product_ci.ANDROID_MAIN_FULL_TESTS
        for argument in ("--tests", test_name)
    ),
)

ANDROID_RELEASE_REPEATABILITY_PRODUCE_COMMAND = (
    "python3",
    "-B",
    "script/run_android_release_repeatability_current.py",
    "--result",
    ANDROID_RELEASE_REPEATABILITY_RESULT_RELATIVE_PATH.as_posix(),
)
ANDROID_RELEASE_REPEATABILITY_READBACK_COMMAND = (
    "python3",
    "-B",
    "script/check_android_release_repeatability_current.py",
    ANDROID_RELEASE_REPEATABILITY_RESULT_RELATIVE_PATH.as_posix(),
)

ANDROID_GATES = (
    python_gate(
        "android-full-prepare",
        "script/check_product_ci.py",
        "--prepare-android-full-test-run",
    ),
    Gate("android-full-run", ANDROID_FULL_COMMAND, 2400),
    python_gate(
        "android-full-bind",
        "script/check_product_ci.py",
        "--write-android-full-test-binding",
    ),
    python_gate(
        "android-full-readback",
        "script/check_product_ci.py",
        "--android-full-test-results",
    ),
    python_gate(
        "android-camera-lifecycle-readback",
        "script/check_product_ci.py",
        "--android-camera-lifecycle-results",
    ),
    python_gate(
        "android-camera-controller-readback",
        "script/check_product_ci.py",
        "--android-camera-controller-host-results",
    ),
    python_gate(
        "android-font-scale-readback",
        "script/check_product_ci.py",
        "--android-font-scale-results",
    ),
    python_gate(
        "android-core-nonsecurity-prepare",
        "script/check_product_ci.py",
        "--prepare-android-core-nonsecurity-test-run",
    ),
    python_gate(
        "android-core-nonsecurity-run",
        "script/check_product_ci.py",
        "--run-android-core-nonsecurity-tests",
        timeout_seconds=2400,
    ),
    python_gate(
        "android-core-nonsecurity-bind",
        "script/check_product_ci.py",
        "--write-android-core-nonsecurity-test-binding",
    ),
    python_gate(
        "android-core-nonsecurity-readback",
        "script/check_product_ci.py",
        "--android-core-nonsecurity-test-results",
    ),
    Gate(
        "android-release-repeatability-produce",
        ANDROID_RELEASE_REPEATABILITY_PRODUCE_COMMAND,
        8400,
    ),
    Gate(
        "android-release-repeatability-readback",
        ANDROID_RELEASE_REPEATABILITY_READBACK_COMMAND,
        1800,
    ),
    python_gate(
        "android-release-readback",
        "script/check_release_artifact_archive.py",
        "--android-build-outputs",
        timeout_seconds=1200,
    ),
    Gate(
        "android-diagnostics-produce",
        (
            "python3",
            "-B",
            "script/run_release_diagnostics_usability.py",
            "--platform",
            "android",
            "--result",
            ".build/aetherlink-release-diagnostics-v1/android.json",
        ),
        300,
    ),
    Gate(
        "android-diagnostics-readback",
        (
            "python3",
            "-B",
            "script/check_release_diagnostics_usability.py",
            "--platform",
            "android",
            ".build/aetherlink-release-diagnostics-v1/android.json",
        ),
        300,
    ),
)

MACOS_GATES = (
    python_gate(
        "macos-release-source-before",
        "script/package_release_artifacts.py",
        "source-digest",
    ),
    Gate(
        "macos-unsealed-package-produce",
        MACOS_UNSEALED_PACKAGE_COMMAND,
        2400,
    ),
    python_gate(
        "macos-release-source-after",
        "script/package_release_artifacts.py",
        "source-digest",
    ),
    python_gate(
        "macos-release-readback",
        "script/check_release_artifact_archive.py",
        "--macos-build-outputs",
        timeout_seconds=1200,
    ),
    Gate(
        "macos-diagnostics-produce",
        (
            "python3",
            "-B",
            "script/run_release_diagnostics_usability.py",
            "--platform",
            "macos",
            "--result",
            ".build/aetherlink-release-diagnostics-v1/macos.json",
        ),
        300,
    ),
    Gate(
        "macos-diagnostics-readback",
        (
            "python3",
            "-B",
            "script/check_release_diagnostics_usability.py",
            "--platform",
            "macos",
            ".build/aetherlink-release-diagnostics-v1/macos.json",
        ),
        300,
    ),
    Gate(
        "macos-lifecycle-produce",
        (
            "python3",
            "-B",
            "script/run_macos_current_unsealed_install_recovery_smoke.py",
            "--result",
            MACOS_LIFECYCLE_RESULT_RELATIVE_PATH.as_posix(),
            "--repeatability-result",
            MACOS_LIFECYCLE_REPEATABILITY_RELATIVE_PATH.as_posix(),
        ),
        1200,
    ),
    Gate(
        "macos-lifecycle-readback",
        (
            "python3",
            "-B",
            "script/check_macos_current_unsealed_ci_lifecycle.py",
            "--result",
            MACOS_LIFECYCLE_RESULT_RELATIVE_PATH.as_posix(),
            "--repeatability-result",
            MACOS_LIFECYCLE_REPEATABILITY_RELATIVE_PATH.as_posix(),
        ),
        600,
    ),
    Gate(
        "macos-current-source-idle-repeatability-readback",
        MACOS_CURRENT_SOURCE_IDLE_REPEATABILITY_READBACK_COMMAND,
        300,
    ),
)

FINAL_READBACK_GATES = (
    python_gate(
        "final-swift-focused-readback",
        "script/check_product_ci.py",
        "--swift-focused-test-results",
    ),
    python_gate(
        "final-g7-nonsecurity-swift-readback",
        "script/check_product_ci.py",
        "--g7-nonsecurity-swift-results",
    ),
    python_gate(
        "final-document-ingestion-asan-readback",
        "script/check_product_ci.py",
        "--document-ingestion-asan-results",
    ),
    python_gate(
        "final-document-ingestion-mutation-readback",
        "script/check_product_ci.py",
        "--document-ingestion-mutation-results",
    ),
    python_gate(
        "final-android-full-readback",
        "script/check_product_ci.py",
        "--android-full-test-results",
    ),
    python_gate(
        "final-android-core-nonsecurity-readback",
        "script/check_product_ci.py",
        "--android-core-nonsecurity-test-results",
    ),
    Gate(
        "final-android-release-repeatability-readback",
        ANDROID_RELEASE_REPEATABILITY_READBACK_COMMAND,
        1800,
    ),
    python_gate(
        "final-android-release-readback",
        "script/check_release_artifact_archive.py",
        "--android-build-outputs",
        timeout_seconds=1200,
    ),
    python_gate(
        "final-macos-release-readback",
        "script/check_release_artifact_archive.py",
        "--macos-build-outputs",
        timeout_seconds=1200,
    ),
    Gate(
        "final-android-diagnostics-readback",
        (
            "python3",
            "-B",
            "script/check_release_diagnostics_usability.py",
            "--platform",
            "android",
            ".build/aetherlink-release-diagnostics-v1/android.json",
        ),
        300,
    ),
    Gate(
        "final-macos-diagnostics-readback",
        (
            "python3",
            "-B",
            "script/check_release_diagnostics_usability.py",
            "--platform",
            "macos",
            ".build/aetherlink-release-diagnostics-v1/macos.json",
        ),
        300,
    ),
    Gate(
        "final-macos-lifecycle-readback",
        (
            "python3",
            "-B",
            "script/check_macos_current_unsealed_ci_lifecycle.py",
            "--result",
            MACOS_LIFECYCLE_RESULT_RELATIVE_PATH.as_posix(),
            "--repeatability-result",
            MACOS_LIFECYCLE_REPEATABILITY_RELATIVE_PATH.as_posix(),
        ),
        600,
    ),
    Gate(
        "final-macos-current-source-idle-repeatability-readback",
        MACOS_CURRENT_SOURCE_IDLE_REPEATABILITY_READBACK_COMMAND,
        300,
    ),
    Gate(
        "final-g7-current-independent-readback",
        (
            "python3",
            "-I",
            "-B",
            "-S",
            "script/check_g7_nonsecurity_merge_full_current.py",
            (
                ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
                "result.json"
            ),
        ),
        600,
    ),
    Gate(
        "final-g7-current-parent-independent-readback",
        (
            "python3",
            "-I",
            "-B",
            "-S",
            "script/check_g7_nonsecurity_merge_full_current.py",
            "--parent",
            (
                ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
                "parent-result.json"
            ),
        ),
        600,
    ),
    python_gate(
        "final-release-compliance-catalog",
        "script/generate_release_compliance.py",
        "check",
    ),
    python_gate(
        "final-tracked-document-contracts",
        "script/check_docs_hygiene.py",
        "--tracked-contracts-only",
        timeout_seconds=900,
    ),
)

ALL_GATES = STATIC_GATES + SWIFT_GATES + ANDROID_GATES + MACOS_GATES + FINAL_READBACK_GATES
EXPECTED_COMMAND_IDS = tuple(gate.identifier for gate in ALL_GATES)
OUTPUT_PARENT_BY_PRODUCER_ID = {
    "android-release-repeatability-produce": (
        ANDROID_RELEASE_REPEATABILITY_RESULT_RELATIVE_PATH.parent
    ),
    "android-diagnostics-produce": Path(
        ".build/aetherlink-release-diagnostics-v1"
    ),
    "macos-diagnostics-produce": Path(
        ".build/aetherlink-release-diagnostics-v1"
    ),
    "macos-lifecycle-produce": Path(
        ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/"
        "macos-current-unsealed-lifecycle-v5"
    ),
}
CREATE_ONLY_OUTPUT_PARENT_BY_PRODUCER_ID = {
    "android-release-repeatability-produce": (
        ANDROID_RELEASE_REPEATABILITY_RESULT_RELATIVE_PATH.parent
    ),
    "macos-lifecycle-produce": MACOS_LIFECYCLE_RESULT_RELATIVE_PATH.parent,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise CandidateError(f"candidate JSON is not canonical: {error}") from error


def stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def validate_relative_path(path: Path) -> None:
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
        or "\\" in path.as_posix()
        or "\x00" in path.as_posix()
    ):
        raise CandidateError(f"path is not a canonical repository path: {path}")
    try:
        path.as_posix().encode("ascii")
    except UnicodeEncodeError as error:
        raise CandidateError(f"path is not ASCII: {path}") from error


def stable_file_record(
    relative: Path,
    *,
    root: Path = ROOT,
    maximum_bytes: int = FILE_MAX_BYTES,
) -> dict[str, object]:
    validate_relative_path(relative)
    path = root / relative
    try:
        path_before = path.lstat()
    except OSError as error:
        raise CandidateError(f"required file cannot be statted: {relative}: {error}") from error
    if (
        stat.S_ISLNK(path_before.st_mode)
        or not stat.S_ISREG(path_before.st_mode)
        or path_before.st_nlink != 1
        or path_before.st_size < 0
        or path_before.st_size > maximum_bytes
    ):
        raise CandidateError(
            f"required file is not bounded, regular, and single-link: {relative}"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    digest = hashlib.sha256()
    size = 0
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise CandidateError(f"required file cannot be opened: {relative}: {error}") from error
    try:
        before = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum_bytes + 1 - size))
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if size > maximum_bytes:
                raise CandidateError(f"required file exceeds byte limit: {relative}")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        path_after = path.lstat()
    except OSError as error:
        raise CandidateError(f"required file disappeared: {relative}: {error}") from error
    if (
        stat_identity(path_before) != stat_identity(before)
        or stat_identity(before) != stat_identity(after)
        or stat_identity(after) != stat_identity(path_after)
        or size != before.st_size
    ):
        raise CandidateError(f"required file changed while read: {relative}")
    return {
        "mode": stat.S_IMODE(before.st_mode),
        "path": relative.as_posix(),
        "sha256": digest.hexdigest(),
        "size": size,
    }


def git_source_paths(*, root: Path = ROOT) -> tuple[Path, ...]:
    try:
        result = subprocess.run(
            (
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ),
            cwd=root,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CandidateError(f"source path enumeration failed: {error}") from error
    if result.returncode != 0 or result.stderr:
        raise CandidateError("source path enumeration did not complete cleanly")
    try:
        values = result.stdout.decode("utf-8").split("\0")
    except UnicodeDecodeError as error:
        raise CandidateError("source path enumeration is not UTF-8") from error
    paths: list[Path] = []
    for value in values:
        if not value or value == "README.md" or value.startswith("docs/"):
            continue
        relative = Path(value)
        validate_relative_path(relative)
        paths.append(relative)
    if len(paths) != len(set(paths)) or not paths:
        raise CandidateError("source path enumeration is empty or contains duplicates")
    return tuple(sorted(paths, key=lambda item: item.as_posix().encode("ascii")))


def source_snapshot(
    *,
    root: Path = ROOT,
    paths: Iterable[Path] | None = None,
) -> dict[str, object]:
    selected = tuple(paths) if paths is not None else git_source_paths(root=root)
    selected = tuple(sorted(selected, key=lambda item: item.as_posix().encode("ascii")))
    if not selected or len(selected) != len(set(selected)):
        raise CandidateError("source snapshot paths are empty or duplicated")
    digest = hashlib.sha256()
    total_size = 0
    for relative in selected:
        record = stable_file_record(
            relative,
            root=root,
            maximum_bytes=SOURCE_FILE_MAX_BYTES,
        )
        digest.update(relative.as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(f"{record['mode']:o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
        total_size += int(record["size"])
        if total_size > SOURCE_TOTAL_MAX_BYTES:
            raise CandidateError("source snapshot exceeds its total byte limit")
    return {
        "algorithm": SOURCE_ALGORITHM,
        "fileCount": len(selected),
        "sha256": digest.hexdigest(),
        "size": total_size,
    }


def ensure_directory(
    path: Path,
    *,
    root: Path,
    mode: int = 0o700,
) -> None:
    root = Path(os.path.abspath(root))
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(root)
        root_value = root.lstat()
    except (OSError, ValueError) as error:
        raise CandidateError(f"cannot prepare repository output directory {path}: {error}") from error
    if stat.S_ISLNK(root_value.st_mode) or not stat.S_ISDIR(root_value.st_mode):
        raise CandidateError("repository root must be a physical directory")
    current = root
    for component in relative.parts:
        current /= component
        try:
            value = current.lstat()
        except FileNotFoundError:
            try:
                current.mkdir(mode=mode)
                value = current.lstat()
            except OSError as error:
                raise CandidateError(
                    f"cannot create output directory {current}: {error}"
                ) from error
        except OSError as error:
            raise CandidateError(
                f"cannot inspect output directory {current}: {error}"
            ) from error
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            raise CandidateError(f"output directory is not physical: {current}")
    try:
        os.chmod(path, mode)
    except OSError as error:
        raise CandidateError(f"cannot set output directory mode: {path}: {error}") from error


def recreate_create_only_output_directory(path: Path, *, root: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise CandidateError("create-only output directory must stay inside the repository") from error
    allowed = set(CREATE_ONLY_OUTPUT_PARENT_BY_PRODUCER_ID.values())
    if relative not in allowed:
        raise CandidateError(f"create-only output directory is not allowlisted: {relative}")

    try:
        root_value = root.lstat()
    except OSError as error:
        raise CandidateError(f"cannot inspect repository root: {error}") from error
    if stat.S_ISLNK(root_value.st_mode) or not stat.S_ISDIR(root_value.st_mode):
        raise CandidateError("repository root must be a physical directory")

    current = root
    for component in relative.parts[:-1]:
        current /= component
        try:
            value = current.lstat()
        except FileNotFoundError:
            ensure_directory(current, root=root)
            continue
        except OSError as error:
            raise CandidateError(f"cannot inspect output ancestor {current}: {error}") from error
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            raise CandidateError(f"output ancestor is not physical: {current}")

    try:
        value = path.lstat()
    except FileNotFoundError:
        value = None
    except OSError as error:
        raise CandidateError(f"cannot inspect create-only output directory {path}: {error}") from error
    if value is not None:
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            raise CandidateError(f"create-only output directory is not physical: {path}")
        try:
            shutil.rmtree(path)
        except OSError as error:
            raise CandidateError(f"cannot clear create-only output directory {path}: {error}") from error
    ensure_directory(path, root=root)


def validated_candidate_result_path(path: Path, *, root: Path = ROOT) -> Path:
    root = Path(os.path.abspath(root))
    candidate = path if path.is_absolute() else root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise CandidateError("candidate result must stay inside the repository") from error
    if relative != RESULT_RELATIVE_PATH:
        raise CandidateError(
            "candidate result must use the dedicated canonical .build path"
        )
    return candidate


@contextmanager
def acquire_candidate_workspace_lock(
    *,
    root: Path = ROOT,
) -> Iterator[int]:
    """Hold the shared Release workspace lock for the complete candidate."""

    try:
        with android_repeatability.acquire_release_workspace_lock(root=root) as descriptor:
            yield descriptor
    except android_repeatability.RepeatabilityError as error:
        raise CandidateError(f"Release workspace lock failed: {error}") from error


def atomic_write(
    path: Path,
    data: bytes,
    *,
    root: Path,
    mode: int = 0o600,
) -> None:
    ensure_directory(path.parent, root=root)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise CandidateError(f"output parent is not a physical directory: {path.parent}")
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    except OSError as error:
        raise CandidateError(f"cannot publish {path}: {error}") from error
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def command_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    environment["PYTHONPATH"] = "."
    if "JAVA_HOME" not in environment and ANDROID_STUDIO_JAVA_HOME.is_dir():
        environment["JAVA_HOME"] = str(ANDROID_STUDIO_JAVA_HOME)
    if "ANDROID_HOME" not in environment and DEFAULT_ANDROID_HOME.is_dir():
        environment["ANDROID_HOME"] = str(DEFAULT_ANDROID_HOME)
    if "ANDROID_SDK_ROOT" not in environment and "ANDROID_HOME" in environment:
        environment["ANDROID_SDK_ROOT"] = environment["ANDROID_HOME"]
    return environment


def output_identity(data: bytes) -> dict[str, object]:
    return {"sha256": sha256_bytes(data), "size": len(data)}


def process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_process_group_exit(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while True:
        leader_exited = process.poll() is not None
        group_exited = not process_group_exists(process.pid)
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


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    termination_errors: list[str] = []
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError as error:
        termination_errors.append(f"SIGTERM failed: {error}")
    if wait_for_process_group_exit(
        process,
        timeout_seconds=COMMAND_TERMINATION_GRACE_SECONDS,
    ):
        return

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError as error:
        termination_errors.append(f"SIGKILL failed: {error}")
    if wait_for_process_group_exit(
        process,
        timeout_seconds=COMMAND_TERMINATION_GRACE_SECONDS,
    ):
        return

    detail = "; ".join(termination_errors)
    if detail:
        detail = f" ({detail})"
    raise CandidateError(
        f"process group {process.pid} survived termination{detail}"
    )


def bounded_process_output(
    process: subprocess.Popen[bytes],
    *,
    identifier: str,
    timeout_seconds: float,
    maximum_bytes: int = COMMAND_OUTPUT_MAX_BYTES,
) -> tuple[bytes, bytes]:
    if process.stdout is None or process.stderr is None:
        terminate_process_group(process)
        raise CandidateError(f"{identifier} did not expose both output streams")
    if type(maximum_bytes) is not int or maximum_bytes < 0:
        terminate_process_group(process)
        raise CandidateError(f"{identifier} output byte limit is invalid")
    if not isinstance(timeout_seconds, (int, float)) or isinstance(
        timeout_seconds, bool
    ) or timeout_seconds <= 0:
        terminate_process_group(process)
        raise CandidateError(f"{identifier} deadline is invalid")

    stdout = bytearray()
    stderr = bytearray()
    buffers = {process.stdout.fileno(): stdout, process.stderr.fileno(): stderr}
    streams = (process.stdout, process.stderr)
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + float(timeout_seconds)

    def terminate_for_failure(message: str) -> None:
        try:
            terminate_process_group(process)
        except CandidateError as error:
            raise CandidateError(f"{message}; cleanup failed: {error}") from error
        raise CandidateError(message)

    try:
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)

        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                terminate_for_failure(f"{identifier} exceeded its deadline")
            events = selector.select(timeout=remaining)
            if not events:
                terminate_for_failure(f"{identifier} exceeded its deadline")
            for key, _ in events:
                try:
                    chunk = os.read(key.fd, 65_536)
                except BlockingIOError:
                    continue
                except OSError as error:
                    terminate_for_failure(
                        f"{identifier} output could not be read: {error}"
                    )
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if len(stdout) + len(stderr) + len(chunk) > maximum_bytes:
                    terminate_for_failure(
                        f"{identifier} output exceeded its byte limit"
                    )
                buffers[key.fd].extend(chunk)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            terminate_for_failure(f"{identifier} exceeded its deadline")
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            terminate_for_failure(f"{identifier} exceeded its deadline")
        if process.returncode is None or process_group_exists(process.pid):
            terminate_for_failure(
                f"{identifier} process group did not fully exit"
            )
    except CandidateError:
        raise
    except OSError as error:
        terminate_for_failure(
            f"{identifier} output could not be read: {error}"
        )
    finally:
        selector.close()
        for stream in streams:
            stream.close()
    return bytes(stdout), bytes(stderr)


def run_gate(
    gate: Gate,
    *,
    root: Path = ROOT,
    environment: dict[str, str] | None = None,
    pass_fds: Sequence[int] = (),
) -> tuple[dict[str, object], bytes, bytes]:
    print(f"[{gate.identifier}] starting", flush=True)
    started = time.monotonic_ns()
    try:
        process = subprocess.Popen(
            gate.argv,
            cwd=root,
            env=environment or command_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            pass_fds=tuple(pass_fds),
        )
    except OSError as error:
        raise CandidateError(f"{gate.identifier} could not start: {error}") from error
    stdout, stderr = bounded_process_output(
        process,
        identifier=gate.identifier,
        timeout_seconds=gate.timeout_seconds,
        maximum_bytes=COMMAND_OUTPUT_MAX_BYTES,
    )
    elapsed = max(1, (time.monotonic_ns() - started) // 1_000_000)
    if process.returncode != 0:
        tail = (stderr or stdout)[-8192:].decode("utf-8", errors="replace")
        raise CandidateError(
            f"{gate.identifier} exited {process.returncode}; bounded tail:\n{tail}"
        )
    if gate.stdout_path is not None:
        atomic_write(root / gate.stdout_path, stdout, root=root)
    record = {
        "argv": list(gate.argv),
        "cwd": ".",
        "elapsedMilliseconds": elapsed,
        "exitCode": 0,
        "id": gate.identifier,
        "stderr": output_identity(stderr),
        "stdout": output_identity(stdout),
        "timeoutSeconds": gate.timeout_seconds,
    }
    print(f"[{gate.identifier}] passed in {elapsed / 1000:.3f}s", flush=True)
    return record, stdout, stderr


def run_gate_with_managed_release_scratch(
    gate: Gate,
    *,
    root: Path = ROOT,
    environment: dict[str, str] | None = None,
    pass_fds: Sequence[int] = (),
) -> tuple[dict[str, object], bytes, bytes]:
    if gate.identifier != "macos-unsealed-package-produce":
        return run_gate(
            gate,
            root=root,
            environment=environment,
            pass_fds=pass_fds,
        )
    if gate.argv != MACOS_UNSEALED_PACKAGE_COMMAND:
        raise CandidateError("macOS package gate command differs from its contract")
    if release_repro.SWIFT_SCRATCH != MACOS_RELEASE_SCRATCH_PATH:
        raise CandidateError("fixed Swift Release scratch path differs from its owner")

    run_id = f"g7-{uuid.uuid4().hex}"
    lease_created = False
    try:
        with release_repro.acquire_run_lock():
            if os.path.lexists(MACOS_RELEASE_SCRATCH_PATH):
                raise CandidateError(
                    "fixed Swift Release scratch already exists: "
                    f"{MACOS_RELEASE_SCRATCH_PATH}"
                )
            if os.path.lexists(release_repro.SWIFT_LEASE_PATH):
                raise CandidateError(
                    "fixed Swift Release scratch lease already exists: "
                    f"{release_repro.SWIFT_LEASE_PATH}"
                )
            release_repro.create_swift_lease(run_id)
            lease_created = True
            try:
                return run_gate(
                    gate,
                    root=root,
                    environment=environment,
                    pass_fds=pass_fds,
                )
            finally:
                if lease_created:
                    release_repro.cleanup_swift_scratch(
                        run_id,
                        remove_lease=True,
                    )
    except release_repro.ReproducibilityError as error:
        raise CandidateError(
            f"fixed Swift Release scratch lifecycle failed: {error}"
        ) from error


def process_identity(pid: int) -> str:
    if type(pid) is not int or pid <= 0:
        raise CandidateError("preserved PID must be a positive integer")
    try:
        result = subprocess.run(
            ("ps", "-p", str(pid), "-o", "lstart=", "-o", "command="),
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CandidateError(f"cannot inspect preserved PID {pid}: {error}") from error
    if result.returncode != 0 or result.stderr or not result.stdout.strip():
        raise CandidateError(f"preserved PID {pid} is not alive")
    try:
        identity = result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise CandidateError("preserved PID identity is not UTF-8") from error
    if len(identity) > 8192:
        raise CandidateError("preserved PID identity exceeds its bound")
    return identity


def pid_record(pid: int | None, before: str, after: str) -> dict[str, object]:
    if pid is None:
        return {
            "after": "",
            "before": "",
            "pid": 0,
            "preservedDuringRun": False,
            "requested": False,
        }
    return {
        "after": after,
        "before": before,
        "pid": pid,
        "preservedDuringRun": before == after,
        "requested": True,
    }


def validate_zero_lint_issues(*, root: Path = ROOT) -> None:
    relative = Path("apps/android/app/build/reports/lint-results-release.xml")
    record = stable_file_record(relative, root=root, maximum_bytes=16 * 1024 * 1024)
    try:
        data = (root / relative).read_bytes()
        document = ET.fromstring(data)
    except (OSError, ET.ParseError) as error:
        raise CandidateError(f"Android Release lint result cannot be parsed: {error}") from error
    issues = document.findall("issue")
    if issues:
        summary = ", ".join(
            f"{item.get('id', '?')}:{item.get('severity', '?')}" for item in issues[:20]
        )
        raise CandidateError(f"Android Release lint retained issues: {summary}")
    if record["size"] <= 0:
        raise CandidateError("Android Release lint result is empty")


def validate_idle_current_release_source_binding(
    *,
    root: Path = ROOT,
    expected_source_sha256: str | None = None,
) -> dict[str, object]:
    before = stable_file_record(
        MACOS_CURRENT_SOURCE_IDLE_PARENT_RELATIVE_PATH,
        root=root,
        maximum_bytes=ARTIFACT_MAX_BYTES,
    )
    try:
        raw = (root / MACOS_CURRENT_SOURCE_IDLE_PARENT_RELATIVE_PATH).read_bytes()
        parent = json.loads(raw)
        current = package_release.source_snapshot(root)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        package_release.ReleaseArchiveError,
    ) as error:
        raise CandidateError(
            f"macOS idle current-source binding cannot be read: {error}"
        ) from error
    after = stable_file_record(
        MACOS_CURRENT_SOURCE_IDLE_PARENT_RELATIVE_PATH,
        root=root,
        maximum_bytes=ARTIFACT_MAX_BYTES,
    )
    if before != after:
        raise CandidateError("macOS idle parent changed during source binding")
    if type(parent) is not dict or type(parent.get("source")) is not dict:
        raise CandidateError("macOS idle parent source record is missing")
    recorded = parent["source"]
    summary = {
        "algorithm": current.get("algorithm"),
        "fileCount": current.get("fileCount"),
        "sha256": current.get("sha256"),
    }
    if any(
        recorded.get(key) != value
        for key, value in summary.items()
    ):
        raise CandidateError(
            "macOS idle parent source differs from current Release source bytes"
        )
    if (
        expected_source_sha256 is not None
        and summary["sha256"] != expected_source_sha256
    ):
        raise CandidateError(
            "macOS idle parent source differs from in-run Release source digest"
        )
    return summary


def candidate_payload(
    *,
    source: dict[str, object],
    commands: Sequence[dict[str, object]],
    artifacts: Sequence[dict[str, object]],
    implementation: Sequence[dict[str, object]],
    pid_preservation: dict[str, object],
) -> dict[str, object]:
    return {
        "artifacts": list(artifacts),
        "commands": list(commands),
        "contract": CONTRACT,
        "coverage": dict(COVERAGE),
        "implementation": list(implementation),
        "limitations": dict(LIMITATIONS),
        "pidPreservation": pid_preservation,
        "result": "passed",
        "schemaVersion": SCHEMA_VERSION,
        "source": source,
    }


def _produce_candidate_locked(
    *,
    root: Path = ROOT,
    result_path: Path,
    preserve_pid: int | None,
    workspace_lock_descriptor: int,
) -> dict[str, object]:
    ensure_directory(result_path.parent, root=root)

    source_before = source_snapshot(root=root)
    pid_before = process_identity(preserve_pid) if preserve_pid is not None else ""
    command_records: list[dict[str, object]] = []
    macos_source_before: str | None = None
    macos_source_after: str | None = None
    environment = command_environment()

    for gate in ALL_GATES:
        output_parent = OUTPUT_PARENT_BY_PRODUCER_ID.get(gate.identifier)
        create_only_output_parent = CREATE_ONLY_OUTPUT_PARENT_BY_PRODUCER_ID.get(
            gate.identifier
        )
        if create_only_output_parent is not None:
            if output_parent != create_only_output_parent:
                raise CandidateError(
                    f"create-only output mapping differs for {gate.identifier}"
                )
            recreate_create_only_output_directory(
                root / create_only_output_parent,
                root=root,
            )
        elif output_parent is not None:
            ensure_directory(root / output_parent, root=root)
        gate_environment = environment
        pass_fds: tuple[int, ...] = ()
        if gate.identifier == "android-release-repeatability-produce":
            gate_environment = environment.copy()
            try:
                android_repeatability.bind_inherited_release_workspace_lock(
                    gate_environment,
                    workspace_lock_descriptor,
                )
            except android_repeatability.RepeatabilityError as error:
                raise CandidateError(
                    f"cannot bind inherited Release workspace lock: {error}"
                ) from error
            pass_fds = (workspace_lock_descriptor,)
        record, stdout, _stderr = run_gate_with_managed_release_scratch(
            gate,
            root=root,
            environment=gate_environment,
            pass_fds=pass_fds,
        )
        command_records.append(record)
        if gate.identifier == "macos-release-source-before":
            macos_source_before = stdout.decode("ascii", errors="strict").strip()
        elif gate.identifier == "macos-release-source-after":
            macos_source_after = stdout.decode("ascii", errors="strict").strip()
            if (
                macos_source_before is None
                or macos_source_after != macos_source_before
                or len(macos_source_after) != 64
            ):
                raise CandidateError("macOS Release source changed during packaging")
        elif gate.identifier == "android-release-repeatability-produce":
            validate_zero_lint_issues(root=root)
        elif gate.identifier in {
            "macos-current-source-idle-repeatability-readback",
            "final-macos-current-source-idle-repeatability-readback",
        }:
            if macos_source_after is None:
                raise CandidateError(
                    "macOS idle readback ran before the Release source digest"
                )
            validate_idle_current_release_source_binding(
                root=root,
                expected_source_sha256=macos_source_after,
            )

    source_after = source_snapshot(root=root)
    if source_after != source_before:
        raise CandidateError("candidate source changed during execution")

    validate_zero_lint_issues(root=root)
    artifacts = tuple(
        stable_file_record(path, root=root, maximum_bytes=ARTIFACT_MAX_BYTES)
        for path in ARTIFACT_PATHS
    )
    implementation = tuple(
        stable_file_record(path, root=root, maximum_bytes=IMPLEMENTATION_MAX_BYTES)
        for path in IMPLEMENTATION_PATHS
    )
    source_final = source_snapshot(root=root)
    if source_final != source_before:
        raise CandidateError("candidate source changed during final evidence read")
    pid_after = process_identity(preserve_pid) if preserve_pid is not None else ""
    preservation = pid_record(preserve_pid, pid_before, pid_after)
    if preserve_pid is not None and not preservation["preservedDuringRun"]:
        raise CandidateError(f"preserved PID {preserve_pid} changed during execution")
    payload = candidate_payload(
        source=source_before,
        commands=command_records,
        artifacts=artifacts,
        implementation=implementation,
        pid_preservation=preservation,
    )
    encoded = canonical_json_bytes(payload)
    if len(encoded) > RESULT_MAX_BYTES:
        raise CandidateError("candidate result exceeds its byte limit")
    atomic_write(result_path, encoded, root=root)
    if stable_file_record(
        result_path.relative_to(root),
        root=root,
        maximum_bytes=RESULT_MAX_BYTES,
    )["mode"] != 0o600:
        raise CandidateError("published candidate result is not mode 0600")
    return payload


def produce_candidate(
    *,
    root: Path = ROOT,
    result_path: Path,
    preserve_pid: int | None,
) -> dict[str, object]:
    result_path = validated_candidate_result_path(result_path, root=root)
    with acquire_candidate_workspace_lock(root=root) as workspace_lock_descriptor:
        return _produce_candidate_locked(
            root=root,
            result_path=result_path,
            preserve_pid=preserve_pid,
            workspace_lock_descriptor=workspace_lock_descriptor,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result",
        type=Path,
        default=RESULT_RELATIVE_PATH,
        help="repository-local canonical result path",
    )
    parser.add_argument(
        "--preserve-pid",
        type=int,
        help="existing unrelated AetherLink PID that must survive the run",
    )
    arguments = parser.parse_args()
    try:
        payload = produce_candidate(
            result_path=arguments.result,
            preserve_pid=arguments.preserve_pid,
        )
    except CandidateError as error:
        print(f"G7 non-security Merge-full candidate failed: {error}", file=os.sys.stderr)
        return 1
    print(
        "G7 non-security Merge-full local candidate published: "
        f"{payload['coverage']['swiftCurrentParentReviewedTests']} Swift "
        "reviewed parent, "
        f"{payload['coverage']['androidFullAppTests']} Android app, "
        f"{payload['coverage']['androidCoreNonsecurityTests']} Android core, "
        f"{payload['coverage']['androidLintIssues']} Android lint issues."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
