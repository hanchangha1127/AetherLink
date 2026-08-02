#!/usr/bin/env python3
"""Run and verify an additive reviewed non-security Swift XCTest lane.

The existing 67-command G7 local candidate remains immutable.  This sibling
gate proves an exact source delta, partitions the current 2,173-test discovery
artifact, and executes only the 626 newly reviewed local product/data tests.
The method-level portion is pinned by a checked-in 315-identity manifest rather
than broadening three mixed test suites.
It deliberately makes no canonical Merge-full, G7-exit, RC, GA, or V1 claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Iterable

if __package__:
    from script import check_g7_nonsecurity_merge_full_candidate as antecedent
    from script import check_product_ci as product_ci
    from script import run_g7_nonsecurity_merge_full_candidate as antecedent_runner
else:
    import check_g7_nonsecurity_merge_full_candidate as antecedent
    import check_product_ci as product_ci
    import run_g7_nonsecurity_merge_full_candidate as antecedent_runner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-g7-reviewed-nonsecurity-swift-addon-v2"
SCHEMA_VERSION = 1

TEST_LIST_PATH = ROOT / ".build/aetherlink-product-ci-swift-test-list-v1.txt"
TEST_LIST_BYTES = 244_956
TEST_LIST_SHA256 = (
    "1ae03648063c27081e3686fa619f79ca9627c91404ce76abab1da5df64ef5fa5"
)

ANTECEDENT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json"
)
ANTECEDENT_PATH = ROOT / ANTECEDENT_RELATIVE_PATH
ANTECEDENT_BYTES = 41_459
ANTECEDENT_SHA256 = (
    "d48ac61a355ecb381100941881a72945144acc16926c27671c3c7ebde4020301"
)
ANTECEDENT_SOURCE = {
    "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
    "fileCount": 996,
    "sha256": (
        "aab42214fb8744a25c673fc0412e7a4c84095e93b66158b99ddce0e50b2d2213"
    ),
    "size": 67_452_727,
}

REVIEWED_METHOD_RELATIVE_PATH = Path(
    "script/g7_reviewed_nonsecurity_swift_addon_identities_v2.txt"
)
REVIEWED_METHOD_PATH = ROOT / REVIEWED_METHOD_RELATIVE_PATH
REVIEWED_METHOD_BYTES = 36_403
REVIEWED_METHOD_RAW_SHA256 = (
    "2472f29799d6957ed9ba1a846d4e1cb099638338a08714c7b715303a0b11231e"
)
REVIEWED_METHOD_TEST_COUNT = 315
REVIEWED_METHOD_TEST_MANIFEST_SHA256 = (
    "95c160839a13e0f6a2219436400ddfc301cafbdab9bfaabfa10388b0d7d511aa"
)
ROUTER_REVIEWED_METHOD_TEST_COUNT = 246
ROUTER_REVIEWED_METHOD_TEST_MANIFEST_SHA256 = (
    "096ff1a30b6eb28aa390ae52db07916406c9bcc58377fe3988bef6e697ad5914"
)
UI_REVIEWED_METHOD_TEST_COUNT = 69
UI_REVIEWED_METHOD_TEST_MANIFEST_SHA256 = (
    "c89ff2f2fd7810cd9d3f0cda361be62920b595f9f97901752903110e2ee7d72c"
)
ROUTER_REVIEWED_PREFIX = (
    "CompanionCoreTests.LocalRuntimeMessageRouterTests/"
)
UI_REVIEWED_SUITE_COUNTS = {
    "LocalAgentBridgeTests.AccessibilityAnnouncementTests/": 6,
    "LocalAgentBridgeTests.AetherLinkLocalizationTests/": 59,
    "LocalAgentBridgeTests.AetherLinkRenderSmokeTests/": 4,
}

ADDON_RELATIVE_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate_v2.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon.py"),
    REVIEWED_METHOD_RELATIVE_PATH,
    Path("script/run_g7_nonsecurity_merge_full_candidate_v2.py"),
    Path("script/test_check_g7_reviewed_nonsecurity_swift_addon.py"),
    Path("script/test_g7_nonsecurity_merge_full_candidate_v2.py"),
)

OUTPUT_ROOT = ROOT / ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2"
RUN_MARKER_PATH = OUTPUT_ROOT / "run-marker.json"
CONSOLE_PATH = OUTPUT_ROOT / "console.log"
BINDING_PATH = OUTPUT_ROOT / "binding.json"
RESULT_PATH = OUTPUT_ROOT / "result.json"
EXECUTION_CONTRACT_PATH = OUTPUT_ROOT / "execution-contract.json"

DISCOVERED_TEST_COUNT = 2_173
DISCOVERED_TEST_MANIFEST_SHA256 = (
    "0a550e58480f4733abc264d0ec572e9511492a43dae6ea2dd5459c03548f4e65"
)
BASE_REVIEWED_TEST_COUNT = 643
BASE_REVIEWED_TEST_MANIFEST_SHA256 = (
    "94ddfced937a57c81b084d65c9a846251555b436aa59f437c8fa6514edeb5e84"
)
REVIEWED_TEST_COUNT = 958
REVIEWED_TEST_MANIFEST_SHA256 = (
    "18b9241ee9196d8094fe70027d2c3439468fee30810f57ed0eb5cc1e43f63f8f"
)
ANTECEDENT_TEST_COUNT = 397
ANTECEDENT_TEST_MANIFEST_SHA256 = (
    "5b9043e65ba90b73620bc1939d0bb2e48a7f26acd379bccd18891d3fb7aae5ee"
)
COMPANION_REVIEWED_TEST_COUNT = 396
COMPANION_REVIEWED_TEST_MANIFEST_SHA256 = (
    "3efb520cd1be6b056f7264d9a72cc52dee37ae7c557b6b4683be55bb38a2b70f"
)
RUNNER_REVIEWED_TEST_COUNT = 711
RUNNER_REVIEWED_TEST_MANIFEST_SHA256 = (
    "825b00218107a638659bf03c27c40439f69ba986a08b9255ae3c10176e137c7c"
)
ANTECEDENT_OVERLAP_COUNT = 85
ANTECEDENT_OVERLAP_MANIFEST_SHA256 = (
    "7bc53be41cc8a7e478b04d99581e6a1017a97f5f11ffb2fc298d8d3631962b42"
)
BASE_NEW_TEST_COUNT = 311
BASE_NEW_TEST_MANIFEST_SHA256 = (
    "80605a31914a3d4d1ba66b4747721f4644a7ddb2b65829acc6730e3d1d65c388"
)
NEW_TEST_COUNT = 626
NEW_TEST_MANIFEST_SHA256 = (
    "5a1ea997a06466671e6b6eb4095d462cddb185cc54331389173a9cb5b84ee642"
)
DISTINCT_AFTER_ADDON_TEST_COUNT = 1_023
DISTINCT_AFTER_ADDON_MANIFEST_SHA256 = (
    "589d6a32bbdb7f24511c27d66f362a856ef1977eb524f8c0862d3752598c7282"
)
NOT_EXECUTED_TEST_COUNT = 1_150
NOT_EXECUTED_TEST_MANIFEST_SHA256 = (
    "aed047c9af8e4b06aad02064d034ffb70d0ab9dbef131acee6f346909b38ee48"
)

REVIEWED_SUITES = (
    "CompanionCoreTests.AggregatingLlmBackendResidencyTests",
    "CompanionCoreTests.RuntimeChatCompactionCalibrationReportTests",
    "CompanionCoreTests.RuntimeChatCompactionSourceFingerprintTests",
    "CompanionCoreTests.RuntimeChatContextCompactionPlannerTests",
    "CompanionCoreTests.RuntimeDocumentCitationGovernanceTests",
    "CompanionCoreTests.RuntimeDocumentIndexStoreTests",
    "CompanionCoreTests.RuntimeDocumentSourceGovernanceTests",
    "CompanionCoreTests.RuntimeLongInactivityMemorySummarizationPolicyTests",
    "CompanionCoreTests.RuntimeMemoryExactDuplicateSuggestionsTests",
    "CompanionCoreTests.RuntimeMemorySemanticCalibrationTests",
    "CompanionCoreTests.RuntimeMemorySemanticDuplicateSuggestionsTests",
    "CompanionCoreTests.RuntimeMemorySemanticEmbeddingCacheTests",
    "CompanionCoreTests.RuntimeMemoryStoreGeneratedDraftTests",
    "CompanionCoreTests.RuntimeMemoryStoreSummaryDecisionTests",
    "CompanionCoreTests.RuntimeModelIdleUnloadPolicyTests",
    "CompanionCoreTests.RuntimePromptSkillRegistryTests",
    "CompanionCoreTests.RuntimeResearchNotebookStoreTests",
    "CompanionCoreTests.RuntimeSemanticChatSessionSearchTests",
    "CompanionCoreTests.RuntimeSemanticMemorySearchTests",
    "CompanionCoreTests.SQLiteRuntimeChatCompactionSummaryCacheTests",
    "CompanionCoreTests.SQLiteRuntimeChatEventStoreTests",
    "CompanionCoreTests.SQLiteRuntimeDocumentIndexStoreTests",
    "CompanionCoreTests.SQLiteRuntimeDocumentSemanticEmbeddingCacheTests",
    "CompanionCoreTests.SQLiteRuntimeResearchNotebookStoreTests",
    "DocumentIngestionTests.DocumentChunkerTests",
    "DocumentIngestionTests.DocumentIngestionGenerationalMutationTests",
    "DocumentIngestionTests.DocumentIngestionSanitizerCorpusTests",
    "DocumentIngestionTests.DocumentIngestorTests",
    "DocumentIngestionTests.DocumentTextExtractorTests",
    "LMStudioBackendTests.LMStudioBackendHealthTimeoutTests",
    "LMStudioBackendTests.LMStudioBackendTests",
    "LocalAgentBridgeTests.AppLifecycleTests",
    "LocalAgentBridgeTests.PackagedStateRecoveryProbeTests",
    "LocalAgentBridgeTests.StatusQuickActionsDisclosureTests",
    "OllamaBackendTests.OllamaBackendHealthTimeoutTests",
    "OllamaBackendTests.OllamaBackendTests",
    "OllamaBackendTests.OllamaEmbeddingMultilingualFullMatrixV3Tests",
    "OllamaBackendTests.OllamaEmbeddingMultilingualSemanticQualityTests",
    "OllamaBackendTests.OllamaEmbeddingSemanticQualityTests",
)
COMPANION_REVIEWED_SUITES = tuple(
    suite for suite in REVIEWED_SUITES if suite.startswith("CompanionCoreTests.")
)


def suite_filter(suites: tuple[str, ...]) -> str:
    return (
        r"^(?!.*\/testLive)(?:"
        + "|".join(re.escape(suite) for suite in suites)
        + r")\/[A-Za-z0-9_]+$"
    )


REVIEWED_FILTER = suite_filter(REVIEWED_SUITES)
COMPANION_REVIEWED_FILTER = suite_filter(COMPANION_REVIEWED_SUITES)

RESULT_MAX_BYTES = 2 * 1024 * 1024
COMMAND_AND_ENVIRONMENT_MAX_BYTES = 64 * 1024
RUN_TIMEOUT_SECONDS = 20 * 60

EXACT_SOURCE_FILES = tuple(
    dict.fromkeys(
        product_ci.SWIFT_FOCUSED_RESULT_EXACT_FILES
        + tuple(ROOT / path for path in ADDON_RELATIVE_PATHS)
        + (ANTECEDENT_PATH, EXECUTION_CONTRACT_PATH)
    )
)

LIMITATIONS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "deviceOrNetworkClaimed": False,
    "hostedCiClaimed": False,
    "securityAuthenticationOrSecureChannelSuitesExecuted": False,
    "signedArtifactsClaimed": False,
    "v1Claimed": False,
}


@dataclass(frozen=True)
class Partition:
    discovered: tuple[str, ...]
    base_reviewed: tuple[str, ...]
    method_reviewed: tuple[str, ...]
    reviewed: tuple[str, ...]
    antecedent: tuple[str, ...]
    companion_reviewed: tuple[str, ...]
    runner_reviewed: tuple[str, ...]
    overlap: tuple[str, ...]
    base_new: tuple[str, ...]
    new: tuple[str, ...]
    distinct_after_addon: tuple[str, ...]
    not_executed: tuple[str, ...]


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


def manifest_sha256(identities: Iterable[str]) -> str:
    payload = json.dumps(
        sorted(identities),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def exact_set_failures(
    label: str,
    identities: tuple[str, ...],
    expected_count: int,
    expected_manifest_sha256: str,
) -> list[str]:
    failures: list[str] = []
    if type(expected_count) is not int or expected_count < 0:
        failures.append(f"{label} expected count must be an exact integer")
    elif len(identities) != expected_count:
        failures.append(
            f"{label} count must be {expected_count}, found {len(identities)}"
        )
    if re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is None:
        failures.append(f"{label} expected manifest must be SHA-256")
    elif manifest_sha256(identities) != expected_manifest_sha256:
        failures.append(f"{label} manifest SHA-256 differs")
    return failures


def load_reviewed_method_tests() -> tuple[tuple[str, ...] | None, list[str]]:
    try:
        before = REVIEWED_METHOD_PATH.lstat()
        data = REVIEWED_METHOD_PATH.read_bytes()
        after = REVIEWED_METHOD_PATH.lstat()
    except OSError as error:
        return None, [f"reviewed method manifest cannot be read: {error}"]
    failures: list[str] = []
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        failures.append("reviewed method manifest must be one stable regular file")
    if len(data) != REVIEWED_METHOD_BYTES:
        failures.append("reviewed method manifest byte count differs")
    if hashlib.sha256(data).hexdigest() != REVIEWED_METHOD_RAW_SHA256:
        failures.append("reviewed method manifest raw SHA-256 differs")
    if not data.endswith(b"\n") or b"\r" in data:
        failures.append("reviewed method manifest must use canonical LF lines")
    try:
        text = data.decode("ascii")
    except UnicodeError as error:
        return None, failures + [f"reviewed method manifest is not ASCII: {error}"]
    identities = tuple(text.splitlines())
    if tuple(sorted(identities)) != identities:
        failures.append("reviewed method manifest identities must be sorted")
    if len(set(identities)) != len(identities):
        failures.append("reviewed method manifest identities must be unique")
    if any(
        identity != identity.strip()
        or re.fullmatch(r"[^\s/]+\/[^\s/]+", identity) is None
        for identity in identities
    ):
        failures.append("reviewed method manifest identities must be canonical")
    failures.extend(
        exact_set_failures(
            "reviewed method Swift",
            identities,
            REVIEWED_METHOD_TEST_COUNT,
            REVIEWED_METHOD_TEST_MANIFEST_SHA256,
        )
    )
    router = tuple(
        identity
        for identity in identities
        if identity.startswith(ROUTER_REVIEWED_PREFIX)
    )
    router_set = set(router)
    ui = tuple(identity for identity in identities if identity not in router_set)
    failures.extend(
        exact_set_failures(
            "reviewed Router method Swift",
            router,
            ROUTER_REVIEWED_METHOD_TEST_COUNT,
            ROUTER_REVIEWED_METHOD_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "reviewed UI method Swift",
            ui,
            UI_REVIEWED_METHOD_TEST_COUNT,
            UI_REVIEWED_METHOD_TEST_MANIFEST_SHA256,
        )
    )
    for prefix, expected_count in UI_REVIEWED_SUITE_COUNTS.items():
        observed_count = sum(identity.startswith(prefix) for identity in ui)
        if observed_count != expected_count:
            failures.append(f"reviewed UI method count differs: {prefix}")
    if any(
        not any(identity.startswith(prefix) for prefix in UI_REVIEWED_SUITE_COUNTS)
        for identity in ui
    ):
        failures.append("reviewed UI methods must stay in the three exact suites")
    return (None if failures else identities), failures


def load_discovered_tests() -> tuple[tuple[str, ...] | None, list[str]]:
    try:
        value = TEST_LIST_PATH.lstat()
        data = TEST_LIST_PATH.read_bytes()
        after = TEST_LIST_PATH.lstat()
    except OSError as error:
        return None, [f"Swift discovery artifact cannot be read: {error}"]
    failures: list[str] = []
    if (
        stat.S_ISLNK(value.st_mode)
        or not stat.S_ISREG(value.st_mode)
        or value.st_dev != after.st_dev
        or value.st_ino != after.st_ino
        or value.st_size != after.st_size
        or value.st_mtime_ns != after.st_mtime_ns
    ):
        failures.append("Swift discovery artifact must be one stable regular file")
    if len(data) != TEST_LIST_BYTES:
        failures.append("Swift discovery artifact byte count differs")
    if hashlib.sha256(data).hexdigest() != TEST_LIST_SHA256:
        failures.append("Swift discovery artifact raw SHA-256 differs")
    if not data.endswith(b"\n") or b"\r" in data:
        failures.append("Swift discovery artifact must use canonical LF lines")
    try:
        text = data.decode("utf-8")
    except UnicodeError as error:
        return None, failures + [f"Swift discovery artifact is not UTF-8: {error}"]
    identities = tuple(text.splitlines())
    failures.extend(partition_shape_failures(identities)[1])
    return (None if failures else identities), failures


def partition_shape_failures(
    identities: tuple[str, ...],
    *,
    reviewed_methods: tuple[str, ...] | None = None,
) -> tuple[Partition | None, list[str]]:
    failures: list[str] = []
    if reviewed_methods is None:
        reviewed_methods, method_failures = load_reviewed_method_tests()
        failures.extend(method_failures)
    if reviewed_methods is None:
        return None, failures
    if not identities:
        return None, failures + ["Swift discovery identity set must not be empty"]
    if len(set(identities)) != len(identities):
        failures.append("Swift discovery identities must not contain duplicates")
    if any(
        identity != identity.strip()
        or re.fullmatch(r"[^\s/]+\/[^\s/]+", identity) is None
        for identity in identities
    ):
        failures.append("Swift discovery identities must be canonical specifiers")
    discovered_set = set(identities)

    focused = {
        identity
        for identity in identities
        if re.search(product_ci.SWIFT_FILTER, identity)
    }
    expanded = {
        identity
        for identity in identities
        if re.search(product_ci.G7_NONSECURITY_SWIFT_FILTER, identity)
        and identity not in product_ci.G7_NONSECURITY_SWIFT_LIVE_TESTS
    }
    antecedent_set = focused | expanded
    base_reviewed_set = {
        identity for identity in identities if re.fullmatch(REVIEWED_FILTER, identity)
    }
    method_set = set(reviewed_methods)
    reviewed_set = base_reviewed_set | method_set
    companion_set = {
        identity
        for identity in identities
        if re.fullmatch(COMPANION_REVIEWED_FILTER, identity)
    }
    runner_set = companion_set | method_set
    overlap_set = runner_set & antecedent_set
    base_new_set = companion_set - antecedent_set
    new_set = runner_set - antecedent_set
    distinct_set = antecedent_set | new_set
    not_executed_set = discovered_set - distinct_set

    def ordered(values: set[str]) -> tuple[str, ...]:
        return tuple(sorted(values))

    partition = Partition(
        discovered=ordered(discovered_set),
        base_reviewed=ordered(base_reviewed_set),
        method_reviewed=ordered(method_set),
        reviewed=ordered(reviewed_set),
        antecedent=ordered(antecedent_set),
        companion_reviewed=ordered(companion_set),
        runner_reviewed=ordered(runner_set),
        overlap=ordered(overlap_set),
        base_new=ordered(base_new_set),
        new=ordered(new_set),
        distinct_after_addon=ordered(distinct_set),
        not_executed=ordered(not_executed_set),
    )

    if tuple(sorted(REVIEWED_SUITES)) != REVIEWED_SUITES:
        failures.append("reviewed suite allowlist must be sorted")
    if len(REVIEWED_SUITES) != 39 or len(set(REVIEWED_SUITES)) != 39:
        failures.append("reviewed suite allowlist must contain exactly 39 suites")
    if len(COMPANION_REVIEWED_SUITES) != 24:
        failures.append("CompanionCore reviewed allowlist must contain 24 suites")
    failures.extend(
        exact_set_failures(
            "discovered Swift",
            partition.discovered,
            DISCOVERED_TEST_COUNT,
            DISCOVERED_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "base reviewed Swift",
            partition.base_reviewed,
            BASE_REVIEWED_TEST_COUNT,
            BASE_REVIEWED_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "antecedent Swift",
            partition.antecedent,
            ANTECEDENT_TEST_COUNT,
            ANTECEDENT_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "CompanionCore reviewed Swift",
            partition.companion_reviewed,
            COMPANION_REVIEWED_TEST_COUNT,
            COMPANION_REVIEWED_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "method reviewed Swift",
            partition.method_reviewed,
            REVIEWED_METHOD_TEST_COUNT,
            REVIEWED_METHOD_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "reviewed Swift",
            partition.reviewed,
            REVIEWED_TEST_COUNT,
            REVIEWED_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "runner reviewed Swift",
            partition.runner_reviewed,
            RUNNER_REVIEWED_TEST_COUNT,
            RUNNER_REVIEWED_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "antecedent overlap Swift",
            partition.overlap,
            ANTECEDENT_OVERLAP_COUNT,
            ANTECEDENT_OVERLAP_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "base new Swift",
            partition.base_new,
            BASE_NEW_TEST_COUNT,
            BASE_NEW_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "new Swift",
            partition.new,
            NEW_TEST_COUNT,
            NEW_TEST_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "distinct post-add-on Swift",
            partition.distinct_after_addon,
            DISTINCT_AFTER_ADDON_TEST_COUNT,
            DISTINCT_AFTER_ADDON_MANIFEST_SHA256,
        )
    )
    failures.extend(
        exact_set_failures(
            "not-executed Swift",
            partition.not_executed,
            NOT_EXECUTED_TEST_COUNT,
            NOT_EXECUTED_TEST_MANIFEST_SHA256,
        )
    )

    if not method_set <= discovered_set:
        failures.append("reviewed method manifest contains undiscovered tests")
    if method_set & antecedent_set:
        failures.append("reviewed method manifest must be additive to antecedent")
    if method_set & companion_set:
        failures.append("method manifest must not duplicate suite-reviewed tests")
    if runner_set != companion_set | method_set:
        failures.append("runner reviewed union differs")
    if new_set != base_new_set | method_set:
        failures.append("new Swift union differs from suite and method review")
    if not expanded <= base_reviewed_set:
        failures.append("reviewed allowlist must contain the existing expanded lane")
    if reviewed_set - antecedent_set != new_set:
        failures.append("reviewed-minus-antecedent partition differs from new tests")
    if overlap_set & new_set:
        failures.append("antecedent overlap and new Swift sets must be disjoint")
    if antecedent_set & not_executed_set or new_set & not_executed_set:
        failures.append("executed and not-executed Swift sets must be disjoint")
    if distinct_set | not_executed_set != discovered_set:
        failures.append("Swift discovery partition must be complete")
    if (
        ANTECEDENT_TEST_COUNT
        + NEW_TEST_COUNT
        + NOT_EXECUTED_TEST_COUNT
        != DISCOVERED_TEST_COUNT
    ):
        failures.append("Swift partition count arithmetic differs")
    if set(product_ci.G7_NONSECURITY_SWIFT_LIVE_TESTS) & reviewed_set:
        failures.append("reviewed allowlist must exclude every live-provider test")
    target_counts = {
        "CompanionCoreTests.": 642,
        "DocumentIngestionTests.": 59,
        "LMStudioBackendTests.": 71,
        "LocalAgentBridgeTests.": 91,
        "OllamaBackendTests.": 95,
    }
    for prefix, expected in target_counts.items():
        observed = sum(identity.startswith(prefix) for identity in reviewed_set)
        if observed != expected:
            failures.append(f"reviewed target count differs: {prefix}")
    return (None if failures else partition), failures


def _candidate_antecedent_failures_for_delta(
    allowed_delta_paths: tuple[Path, ...],
) -> list[str]:
    failures: list[str] = []
    try:
        data, mode = antecedent.read_stable_regular_file(
            ROOT,
            ANTECEDENT_RELATIVE_PATH,
            maximum_bytes=antecedent.RESULT_MAX_BYTES,
        )
    except antecedent.CandidateError as error:
        return [f"antecedent candidate cannot be read: {error}"]
    if mode != 0o600:
        failures.append("antecedent candidate mode must be 0600")
    if len(data) != ANTECEDENT_BYTES:
        failures.append("antecedent candidate byte count differs")
    if hashlib.sha256(data).hexdigest() != ANTECEDENT_SHA256:
        failures.append("antecedent candidate SHA-256 differs")
    try:
        document = json.loads(
            data,
            object_pairs_hook=antecedent.reject_duplicate_keys,
        )
    except (UnicodeError, json.JSONDecodeError, antecedent.DuplicateKeyError) as error:
        failures.append(f"antecedent candidate JSON cannot be decoded: {error}")
        document = None
    if type(document) is not dict or canonical_json_bytes(document) != data:
        failures.append("antecedent candidate must remain canonical JSON")
    else:
        if document.get("contract") != antecedent.CONTRACT:
            failures.append("antecedent candidate contract differs")
        if document.get("schemaVersion") != antecedent.SCHEMA_VERSION:
            failures.append("antecedent candidate schema version differs")
        if document.get("result") != "passed":
            failures.append("antecedent candidate result must remain passed")
        if document.get("source") != ANTECEDENT_SOURCE:
            failures.append("antecedent candidate recorded source differs")
        coverage = document.get("coverage")
        if type(coverage) is not dict or any(
            coverage.get(key) != expected
            for key, expected in {
                "swiftDistinctNonsecurityTests": ANTECEDENT_TEST_COUNT,
                "swiftExpandedNonsecurityTests": 247,
                "swiftFocusedTests": 222,
            }.items()
        ):
            failures.append("antecedent candidate Swift coverage differs")
        limitations = document.get("limitations")
        if type(limitations) is not dict or any(
            limitations.get(key) is not False
            for key in (
                "canonicalG7ExitClaimed",
                "canonicalMergeFullClaimed",
                "completeSwiftSuiteClaimed",
                "securityAuthenticationCryptographyExecuted",
                "v1Claimed",
            )
        ):
            failures.append("antecedent candidate limitations differ")

    if len(set(allowed_delta_paths)) != len(allowed_delta_paths):
        failures.append("allowed source delta paths must not contain duplicates")
        return failures
    try:
        current_paths = antecedent_runner.git_source_paths(root=ROOT)
    except antecedent_runner.CandidateError as error:
        failures.append(f"current source paths cannot be enumerated: {error}")
        return failures
    current_set = set(current_paths)
    delta_set = set(allowed_delta_paths)
    missing = tuple(sorted(delta_set - current_set, key=lambda path: path.as_posix()))
    if missing:
        failures.append(
            "allowed source delta paths are missing: "
            + ", ".join(path.as_posix() for path in missing)
        )
        return failures
    projected_paths = tuple(path for path in current_paths if path not in delta_set)
    try:
        projected = antecedent_runner.source_snapshot(
            root=ROOT,
            paths=projected_paths,
        )
    except antecedent_runner.CandidateError as error:
        failures.append(f"antecedent source projection failed: {error}")
    else:
        if projected != ANTECEDENT_SOURCE:
            failures.append(
                "current source minus the exact add-on paths must equal the "
                "antecedent source snapshot"
            )
    return failures


def candidate_antecedent_failures() -> list[str]:
    return _candidate_antecedent_failures_for_delta(ADDON_RELATIVE_PATHS)


def exact_skip_filter(identities: tuple[str, ...]) -> str:
    return "^(?:" + "|".join(re.escape(identity) for identity in identities) + ")$"


def runner_include_filter(partition: Partition) -> str:
    return (
        "(?:"
        + COMPANION_REVIEWED_FILTER
        + "|"
        + exact_skip_filter(partition.method_reviewed)
        + ")"
    )


def command_environment_footprint(
    command: tuple[str, ...],
    environment: dict[str, str],
) -> int:
    return sum(len(os.fsencode(value)) + 1 for value in command) + sum(
        len(os.fsencode(key)) + len(os.fsencode(value)) + 2
        for key, value in environment.items()
    )


def execution_contract_payload(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> dict[str, object]:
    return {
        "command": list(command),
        "commandAndEnvironmentBytes": command_environment_footprint(
            command,
            environment,
        ),
        "commandAndEnvironmentMaximumBytes": COMMAND_AND_ENVIRONMENT_MAX_BYTES,
        "contract": "aetherlink-g7-reviewed-nonsecurity-swift-execution-v2",
        "environment": environment,
        "filterExcluded": len(partition.overlap),
        "networkDenyProbePassed": True,
        "networkDenyProfile": product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
        "runtimeExpected": {
            "errors": 0,
            "failures": 0,
            "skipped": 0,
            "testcaseManifestSha256": NEW_TEST_MANIFEST_SHA256,
            "tests": NEW_TEST_COUNT,
        },
        "selection": {
            "baseNewManifestSha256": BASE_NEW_TEST_MANIFEST_SHA256,
            "baseNewTests": BASE_NEW_TEST_COUNT,
            "methodManifestSha256": REVIEWED_METHOD_TEST_MANIFEST_SHA256,
            "methodManifestTests": REVIEWED_METHOD_TEST_COUNT,
            "runnerManifestSha256": RUNNER_REVIEWED_TEST_MANIFEST_SHA256,
            "runnerTestsBeforeExclusion": RUNNER_REVIEWED_TEST_COUNT,
        },
        "schemaVersion": 1,
    }


def execution_contract_failures(
    partition: Partition,
    command: tuple[str, ...],
    *,
    expected_environment: dict[str, str] | None = None,
) -> list[str]:
    try:
        data, mode = antecedent.read_stable_regular_file(
            ROOT,
            EXECUTION_CONTRACT_PATH.relative_to(ROOT),
            maximum_bytes=COMMAND_AND_ENVIRONMENT_MAX_BYTES,
        )
    except antecedent.CandidateError as error:
        return [f"execution contract cannot be read: {error}"]
    failures: list[str] = []
    if mode != 0o600:
        failures.append("execution contract mode must be 0600")
    try:
        document = json.loads(data, object_pairs_hook=antecedent.reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, antecedent.DuplicateKeyError) as error:
        return failures + [f"execution contract JSON cannot be decoded: {error}"]
    if type(document) is not dict or data != canonical_json_bytes(document):
        failures.append("execution contract must be canonical JSON")
        return failures
    recorded_environment = document.get("environment")
    if type(recorded_environment) is not dict or any(
        type(key) is not str or type(value) is not str
        for key, value in (
            recorded_environment.items()
            if type(recorded_environment) is dict
            else ()
        )
    ):
        failures.append("execution contract environment must be a string mapping")
        recorded_environment = {}
    normalized_environment, environment_failures = (
        product_ci.g7_nonsecurity_swift_environment(recorded_environment)
    )
    failures.extend(
        "execution contract environment: " + failure
        for failure in environment_failures
    )
    if normalized_environment != recorded_environment:
        failures.append("execution contract environment is not the exact allowlist")
    if (
        expected_environment is not None
        and recorded_environment != expected_environment
    ):
        failures.append("execution contract environment differs from this run")
    expected = execution_contract_payload(
        partition,
        command,
        recorded_environment,
    )
    if data != canonical_json_bytes(expected):
        failures.append("execution contract command/profile/selection differs")
    return failures


def write_execution_contract(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> list[str]:
    failures = product_ci.write_canonical_json_payload(
        EXECUTION_CONTRACT_PATH,
        execution_contract_payload(partition, command, environment),
        label="G7 reviewed non-security Swift execution contract",
    )
    if not failures:
        failures.extend(
            execution_contract_failures(
                partition,
                command,
                expected_environment=environment,
            )
        )
    return failures


def runner_command(
    partition: Partition,
) -> tuple[tuple[str, ...] | None, list[str]]:
    failures: list[str] = []
    include_filter = runner_include_filter(partition)
    skip_filter = exact_skip_filter(partition.overlap)
    command = (
        "/usr/bin/sandbox-exec",
        "-p",
        product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
        "/usr/bin/swift",
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
        include_filter,
        "--skip",
        skip_filter,
    )
    try:
        included_by_command = {
            identity
            for identity in partition.discovered
            if re.search(command[8], identity)
        }
        excluded_by_command = {
            identity
            for identity in included_by_command
            if re.fullmatch(command[10], identity)
        }
    except re.error as error:
        failures.append(f"runner include/skip regex is invalid: {error}")
        included_by_command = set()
        excluded_by_command = set()
    selected_by_command = included_by_command - excluded_by_command
    if included_by_command != set(partition.runner_reviewed):
        failures.append("runner include filter differs from reviewed runner set")
    if excluded_by_command != set(partition.overlap):
        failures.append("runner skip filter differs from antecedent overlap")
    if selected_by_command != set(partition.new):
        failures.append("runner filter/skip selection differs from new test set")
    if any(re.fullmatch(skip_filter, identity) is None for identity in partition.overlap):
        failures.append("runner skip filter omits an antecedent overlap identity")
    return (None if failures else command), failures


def runner_contract(
    partition: Partition,
) -> tuple[tuple[str, ...] | None, dict[str, str] | None, list[str]]:
    command, failures = runner_command(partition)
    failures.extend(candidate_antecedent_failures())
    environment, environment_failures = product_ci.g7_nonsecurity_swift_environment()
    failures.extend(environment_failures)
    failures.extend(product_ci.g7_nonsecurity_swift_network_sandbox_self_test())
    if command is None:
        return None, None, failures
    for executable in (Path(command[0]), Path(command[3])):
        try:
            value = executable.lstat()
        except OSError as error:
            failures.append(f"runner executable cannot be inspected: {executable}: {error}")
            continue
        if (
            stat.S_ISLNK(value.st_mode)
            or not stat.S_ISREG(value.st_mode)
            or not os.access(executable, os.X_OK)
        ):
            failures.append(f"runner executable must be physical: {executable}")
    if environment is not None:
        footprint = command_environment_footprint(command, environment)
        if footprint > COMMAND_AND_ENVIRONMENT_MAX_BYTES:
            failures.append("runner argv/environment footprint exceeds fixed bound")
    if failures or environment is None:
        return None, None, failures
    return command, environment, []


def contract_inputs() -> tuple[Partition | None, list[str]]:
    identities, failures = load_discovered_tests()
    if identities is None:
        return None, failures
    partition, partition_failures = partition_shape_failures(identities)
    failures.extend(partition_failures)
    failures.extend(candidate_antecedent_failures())
    if partition is None or failures:
        return None, failures
    return partition, []


def generic_arguments(partition: Partition) -> dict[str, object]:
    return {
        "binding_path": BINDING_PATH,
        "marker_path": RUN_MARKER_PATH,
        "log_path": CONSOLE_PATH,
        "test_list_path": TEST_LIST_PATH,
        "filter_pattern": runner_include_filter(partition),
        "expected_count": NEW_TEST_COUNT,
        "expected_manifest_sha256": NEW_TEST_MANIFEST_SHA256,
        "excluded_tests": partition.overlap,
        "exact_files": EXACT_SOURCE_FILES,
    }


def run_addon_tests(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> tuple[int, list[str]]:
    include_filter = runner_include_filter(partition)
    marker_failures = product_ci.swift_focused_test_run_marker_failures(
        marker_path=RUN_MARKER_PATH,
        log_path=CONSOLE_PATH,
        test_list_path=TEST_LIST_PATH,
        filter_pattern=include_filter,
        expected_count=NEW_TEST_COUNT,
        expected_manifest_sha256=NEW_TEST_MANIFEST_SHA256,
        excluded_tests=partition.overlap,
        exact_files=EXACT_SOURCE_FILES,
        require_log=False,
    )
    if marker_failures:
        return 1, marker_failures
    _, expected_tests, selection_failures = (
        product_ci.swift_focused_test_list_snapshot(
            test_list_path=TEST_LIST_PATH,
            filter_pattern=include_filter,
            expected_count=NEW_TEST_COUNT,
            expected_manifest_sha256=NEW_TEST_MANIFEST_SHA256,
            excluded_tests=partition.overlap,
        )
    )
    if expected_tests is None:
        return 1, selection_failures

    def validate_log_context(candidate_log_path: Path) -> list[str]:
        return product_ci.swift_focused_test_run_marker_failures(
            marker_path=RUN_MARKER_PATH,
            log_path=candidate_log_path,
            test_list_path=TEST_LIST_PATH,
            filter_pattern=include_filter,
            expected_count=NEW_TEST_COUNT,
            expected_manifest_sha256=NEW_TEST_MANIFEST_SHA256,
            excluded_tests=partition.overlap,
            exact_files=EXACT_SOURCE_FILES,
        )

    return product_ci.run_and_publish_swift_focused_log(
        command=command,
        cwd=ROOT,
        log_path=CONSOLE_PATH,
        expected_tests=expected_tests,
        log_context_failures=validate_log_context,
        timeout_seconds=RUN_TIMEOUT_SECONDS,
        environment=environment,
    )


def stable_record(path: Path, *, maximum_bytes: int) -> dict[str, object]:
    relative = path.relative_to(ROOT)
    data, mode = antecedent.read_stable_regular_file(
        ROOT,
        relative,
        maximum_bytes=maximum_bytes,
    )
    return {
        "bytes": len(data),
        "mode": mode,
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def result_payload(partition: Partition) -> tuple[dict[str, object] | None, list[str]]:
    try:
        artifacts = {
            "antecedent": stable_record(ANTECEDENT_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "binding": stable_record(BINDING_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "console": stable_record(
                CONSOLE_PATH,
                maximum_bytes=product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
            ),
            "executionContract": stable_record(
                EXECUTION_CONTRACT_PATH,
                maximum_bytes=COMMAND_AND_ENVIRONMENT_MAX_BYTES,
            ),
            "reviewedMethodManifest": stable_record(
                REVIEWED_METHOD_PATH,
                maximum_bytes=RESULT_MAX_BYTES,
            ),
            "runMarker": stable_record(RUN_MARKER_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "testList": stable_record(TEST_LIST_PATH, maximum_bytes=RESULT_MAX_BYTES),
        }
    except (ValueError, antecedent.CandidateError) as error:
        return None, [f"add-on result artifact cannot be read: {error}"]
    return (
        {
            "artifacts": artifacts,
            "contract": CONTRACT,
            "limitations": LIMITATIONS,
            "partition": {
                "antecedent": {
                    "manifestSha256": ANTECEDENT_TEST_MANIFEST_SHA256,
                    "tests": ANTECEDENT_TEST_COUNT,
                },
                "discovered": {
                    "manifestSha256": DISCOVERED_TEST_MANIFEST_SHA256,
                    "tests": DISCOVERED_TEST_COUNT,
                },
                "distinctAfterAddon": {
                    "manifestSha256": DISTINCT_AFTER_ADDON_MANIFEST_SHA256,
                    "tests": DISTINCT_AFTER_ADDON_TEST_COUNT,
                },
                "newExecuted": {
                    "manifestSha256": NEW_TEST_MANIFEST_SHA256,
                    "tests": NEW_TEST_COUNT,
                },
                "newExecutedByReviewKind": {
                    "exactMethods": {
                        "manifestSha256": REVIEWED_METHOD_TEST_MANIFEST_SHA256,
                        "tests": REVIEWED_METHOD_TEST_COUNT,
                    },
                    "suiteReviewed": {
                        "manifestSha256": BASE_NEW_TEST_MANIFEST_SHA256,
                        "tests": BASE_NEW_TEST_COUNT,
                    },
                },
                "notExecuted": {
                    "manifestSha256": NOT_EXECUTED_TEST_MANIFEST_SHA256,
                    "tests": NOT_EXECUTED_TEST_COUNT,
                },
                "reviewedAllowlist": {
                    "manifestSha256": REVIEWED_TEST_MANIFEST_SHA256,
                    "tests": REVIEWED_TEST_COUNT,
                },
            },
            "result": "passed",
            "schemaVersion": SCHEMA_VERSION,
            "scope": {
                "contentHashUtilityTestsIncluded": True,
                "exactMethodReviewedRouterTests": (
                    ROUTER_REVIEWED_METHOD_TEST_COUNT
                ),
                "exactMethodReviewedUiAccessibilityLocalizationRenderTests": (
                    UI_REVIEWED_METHOD_TEST_COUNT
                ),
                "securityAuthenticationOrSecureChannelSuitesExecuted": False,
            },
        },
        [],
    )


def result_failures(partition: Partition) -> list[str]:
    failures = candidate_antecedent_failures()
    command, command_failures = runner_command(partition)
    failures.extend(command_failures)
    if command is not None:
        failures.extend(execution_contract_failures(partition, command))
    failures.extend(
        product_ci.swift_focused_test_binding_failures(
            **generic_arguments(partition)
        )
    )
    expected, payload_failures = result_payload(partition)
    failures.extend(payload_failures)
    if expected is None:
        return failures
    try:
        data, mode = antecedent.read_stable_regular_file(
            ROOT,
            RESULT_PATH.relative_to(ROOT),
            maximum_bytes=RESULT_MAX_BYTES,
        )
    except antecedent.CandidateError as error:
        failures.append(f"add-on result cannot be read: {error}")
        return failures
    if mode != 0o600:
        failures.append("add-on result mode must be 0600")
    try:
        observed = json.loads(data, object_pairs_hook=antecedent.reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, antecedent.DuplicateKeyError) as error:
        failures.append(f"add-on result JSON cannot be decoded: {error}")
        return failures
    if type(observed) is not dict or data != canonical_json_bytes(observed):
        failures.append("add-on result must be canonical JSON")
    if data != canonical_json_bytes(expected):
        failures.append("add-on result must exactly bind current evidence bytes")
    return failures


def write_result(partition: Partition) -> list[str]:
    failures = product_ci.swift_focused_test_binding_failures(
        **generic_arguments(partition)
    )
    failures.extend(candidate_antecedent_failures())
    command, command_failures = runner_command(partition)
    failures.extend(command_failures)
    if command is not None:
        failures.extend(execution_contract_failures(partition, command))
    payload, payload_failures = result_payload(partition)
    failures.extend(payload_failures)
    if payload is None or failures:
        return failures
    failures.extend(
        product_ci.write_canonical_json_payload(
            RESULT_PATH,
            payload,
            label="G7 reviewed non-security Swift add-on result",
        )
    )
    if not failures:
        failures.extend(result_failures(partition))
    return failures


def self_test() -> list[str]:
    partition, failures = contract_inputs()
    if partition is None:
        return failures
    command, environment, runner_failures = runner_contract(partition)
    failures.extend(runner_failures)
    if command is None or environment is None:
        return failures
    if command[0:4] != (
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1)(allow default)(deny network*)",
        "/usr/bin/swift",
    ):
        failures.append("runner sandbox prefix differs")
    if command[4:9] != (
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
        runner_include_filter(partition),
    ):
        failures.append("runner serial include contract differs")
    if command[9] != "--skip":
        failures.append("runner exact skip option differs")
    replacement = "CompanionCoreTests.RuntimeDocumentIndexStoreTests/testSyntheticDrift"
    mutated = list(partition.discovered)
    mutated[mutated.index(partition.new[0])] = replacement
    _, mutation_failures = partition_shape_failures(tuple(mutated))
    if not any("manifest SHA-256 differs" in failure for failure in mutation_failures):
        failures.append("same-count new Swift identity substitution was not rejected")
    _, duplicate_failures = partition_shape_failures(
        partition.discovered + (partition.discovered[0],)
    )
    if not any("duplicates" in failure for failure in duplicate_failures):
        failures.append("duplicate Swift discovery identity was not rejected")
    missing_delta_failures = _candidate_antecedent_failures_for_delta(
        ADDON_RELATIVE_PATHS[:1]
    )
    if not missing_delta_failures:
        failures.append("incomplete add-on source delta was not rejected")
    return failures


def print_failures(prefix: str, failures: list[str]) -> int:
    for failure in failures:
        print(f"{prefix}: {failure}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--write-binding", action="store_true")
    mode.add_argument("--results", action="store_true")
    args = parser.parse_args()

    partition, failures = contract_inputs()
    if partition is None:
        return print_failures("G7 reviewed Swift add-on preflight failed", failures)

    if args.self_test:
        failures = self_test()
        if failures:
            return print_failures("G7 reviewed Swift add-on self-test failed", failures)
        print("G7 reviewed non-security Swift add-on contract self-test passed.")
        return 0

    common = generic_arguments(partition)
    if args.prepare:
        command, environment, runner_failures = runner_contract(partition)
        failures.extend(runner_failures)
        if command is not None and environment is not None and not failures:
            failures.extend(write_execution_contract(partition, command, environment))
        if not failures:
            failures.extend(
                product_ci.write_swift_focused_test_run_marker(
                    marker_path=RUN_MARKER_PATH,
                    test_list_path=TEST_LIST_PATH,
                    filter_pattern=runner_include_filter(partition),
                    expected_count=NEW_TEST_COUNT,
                    expected_manifest_sha256=NEW_TEST_MANIFEST_SHA256,
                    excluded_tests=partition.overlap,
                    exact_files=EXACT_SOURCE_FILES,
                )
            )
        if failures:
            return print_failures("G7 reviewed Swift add-on preparation failed", failures)
        print(f"G7 reviewed Swift add-on marker passed: {NEW_TEST_COUNT} new tests.")
        return 0

    if args.run:
        command, environment, runner_failures = runner_contract(partition)
        failures.extend(runner_failures)
        if command is None or environment is None:
            return print_failures("G7 reviewed Swift add-on runner failed", failures)
        failures.extend(
            execution_contract_failures(
                partition,
                command,
                expected_environment=environment,
            )
        )
        if failures:
            return print_failures("G7 reviewed Swift add-on runner failed", failures)
        status, run_failures = run_addon_tests(
            partition,
            command,
            environment,
        )
        failures.extend(run_failures)
        if status != 0 or failures:
            return print_failures("G7 reviewed Swift add-on runner failed", failures)
        print(
            f"G7 reviewed Swift add-on run passed: {NEW_TEST_COUNT}/"
            f"{NEW_TEST_COUNT}; filterExcluded={ANTECEDENT_OVERLAP_COUNT}; "
            "runtimeSkipped=0; failures=0; network-deny probe passed and "
            "profile applied."
        )
        return 0

    if args.write_binding:
        command, command_failures = runner_command(partition)
        failures.extend(command_failures)
        if command is not None:
            failures.extend(execution_contract_failures(partition, command))
        failures.extend(
            product_ci.write_swift_focused_test_binding(**common)
        )
        if not failures:
            failures.extend(write_result(partition))
        if failures:
            return print_failures("G7 reviewed Swift add-on binding failed", failures)
        print(
            f"G7 reviewed Swift add-on binding passed: {NEW_TEST_COUNT}/"
            f"{NEW_TEST_COUNT}; distinct local Swift evidence "
            f"{DISTINCT_AFTER_ADDON_TEST_COUNT}."
        )
        return 0

    failures.extend(result_failures(partition))
    if failures:
        return print_failures("G7 reviewed Swift add-on readback failed", failures)
    print(
        f"G7 reviewed Swift add-on readback passed: {NEW_TEST_COUNT}/"
        f"{NEW_TEST_COUNT}; distinct local Swift evidence "
        f"{DISTINCT_AFTER_ADDON_TEST_COUNT}; canonical G7 remains unclaimed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
