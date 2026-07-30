#!/usr/bin/env python3
"""Validate the bounded G7 non-security product CI subset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/product-quality.yml"
CANONICAL_WORKFLOW_SHA256 = (
    "7f24adee31748522469daee3c4be17fd2d474dde3b9edcae79e95f3cc362571d"
)
CANONICAL_PARSED_WORKFLOW_SHA256 = (
    "843b003fb1fb16c60003ff920db4a95ec23e24b96dc1eee2e453717bbc529384"
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
    "AggregatingLlmBackendResidencyTests|RuntimeModelIdleUnloadPolicyTests|"
    "RuntimeChatContextCompactionPlannerTests|"
    "RuntimeSemanticChatSessionSearchTests|RuntimeSemanticMemorySearchTests|"
    "LocalPeerServerTests/"
    "testLocalPeerServerReportsListenerStartAndExplicitStop|"
    "LocalPeerServerTests/"
    "testLocalPeerServerOccupiedPortFailsThenSameInstanceRetries|"
    "LocalPeerServerTests/"
    "testPeerAdmissionCannotCrossListenerStopGenerationBoundary|"
    "MacRuntimeConnectionManagerTests/"
    "testStartLocalDefersAdvertisementUntilListenerIsReady|"
    "MacRuntimeConnectionManagerTests/"
    "testConcreteLocalListenerDefersAdvertisementAndRetriesAfterOccupiedPort|"
    "MacRuntimeConnectionManagerTests/"
    "testLateLocalFailureStopsOwnershipAndReportsStatus|"
    "MacRuntimeConnectionManagerTests/"
    "testSupersededLocalStatusCallbackCannotStopReplacement|"
    "MacRuntimeConnectionManagerTests/"
    "testStoppedLocalStatusCallbackIsIgnoredAfterExplicitStop|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelUserInterfaceStartCanRetryAfterListenerFailure|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelLateListenerFailureAllowsSamePortRetryAndIgnoresStaleCallback|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelUserInterfaceStartIsIdempotentDuringRouteAllocation|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelDebugUserInterfaceDoesNotGenerateQRCodeWhenRuntimeListenerFails|"
    "LocalRuntimeMessageRouterTests/"
    "testCompanionAppModelReportsFailedTransportWithoutAdvertising|"
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
    f"          --tests {ANDROID_TESTS[0]}\n"
    f"          --tests {ANDROID_TESTS[1]}\n"
    f"          --tests {ANDROID_TESTS[2]}\n"
    f"          --tests {ANDROID_TESTS[3]}\n"
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
        "Compile Android and run focused product units",
        ANDROID_TEST_STEP_BODY,
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
        "missing Android session-boundary regression": (
            workflow.replace(
                f"          --tests {ANDROID_TESTS[-1]}\n",
                "",
                1,
            ),
            "exact allowlist",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="also prove representative contract mutations are rejected",
    )
    args = parser.parse_args()

    try:
        workflow = WORKFLOW_PATH.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as error:
        print(f"Product CI contract failed: {error}", file=sys.stderr)
        return 1

    failures = workflow_failures(workflow)
    if args.self_test and not failures:
        failures.extend(self_test(workflow))

    if failures:
        for failure in failures:
            print(f"Product CI contract failed: {failure}", file=sys.stderr)
        return 1

    suffix = " and self-test" if args.self_test else ""
    print(f"Product CI contract{suffix} passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
