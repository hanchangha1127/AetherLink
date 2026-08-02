#!/usr/bin/env python3
"""Run and verify the exact 53-test G7 local non-security Swift V4 add-on.

The passing Merge-full V3 candidate remains immutable antecedent evidence.  V4
selects only the reviewed deterministic UI/local projection tests from V3's
scope-excluded partition.  It makes no complete-suite, canonical G7, RC, GA,
device/network, signing, security, authentication, or V1 claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Iterable, Sequence

if __package__:
    from script import check_g7_nonsecurity_merge_full_candidate_v3 as candidate_v3
    from script import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    from script import g7_nonsecurity_swift_successor_engine as engine
else:
    import check_g7_nonsecurity_merge_full_candidate_v3 as candidate_v3
    import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    import g7_nonsecurity_swift_successor_engine as engine


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-g7-reviewed-nonsecurity-swift-addon-v4"
EXECUTION_CONTRACT = "aetherlink-g7-reviewed-nonsecurity-swift-execution-v4"
SCHEMA_VERSION = 1

product_ci = addon_v3.product_ci
candidate_base = addon_v3.candidate_base
source_runner = addon_v3.source_runner

TEST_LIST_PATH = addon_v3.TEST_LIST_PATH
DISCOVERED_TEST_COUNT = 2_173
DISCOVERED_TEST_MANIFEST_SHA256 = (
    "0a550e58480f4733abc264d0ec572e9511492a43dae6ea2dd5459c03548f4e65"
)

ANTECEDENT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v3/candidate.json"
)
ANTECEDENT_PATH = ROOT / ANTECEDENT_RELATIVE_PATH
ANTECEDENT_BYTES = 14_457
ANTECEDENT_SHA256 = (
    "b43b6ff584216466380a16a84dcf35cb9bc9129deda8d1d31c431610946f1575"
)
ANTECEDENT_SOURCE = {
    "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
    "fileCount": 1_008,
    "sha256": "7281eacaf6eec1876c81945f0e61302da243357663a75ce4bf6c1d36be1883e5",
    "size": 67_776_947,
}
ANTECEDENT_DISTINCT_TEST_COUNT = 1_120
ANTECEDENT_DISTINCT_TEST_MANIFEST_SHA256 = (
    "aaa5bfb601c28f89e52ab8d1d8da95c81b876eb4d5ea2cc0d1afb8f2ccd2bf18"
)
REVIEWED_INPUT_TEST_COUNT = 1_053
REVIEWED_INPUT_TEST_MANIFEST_SHA256 = (
    "bc896a061126bb1958ac7c50ea6558ad174bb82418a7d2687cf99e2489d1e697"
)

REVIEWED_IDENTITY_RELATIVE_PATH = Path(
    "docs/evidence/g7-reviewed-nonsecurity-swift-addon-identities-v4-proposal.txt"
)
REVIEWED_IDENTITY_PATH = ROOT / REVIEWED_IDENTITY_RELATIVE_PATH
REVIEWED_IDENTITY_BYTES = 6_324
REVIEWED_IDENTITY_RAW_SHA256 = (
    "1c63f6bf70e8bfeb4f966aaf7b0d8bb0b676ea36cef2afbdbd121335c663a598"
)
NEW_TEST_COUNT = 53
NEW_TEST_MANIFEST_SHA256 = (
    "0f625c53d1045b750b8a925c969df6d3a902b9d4bd5ed65c3fb283d518f1ca4e"
)
EXCLUDED_BY_SCOPE_TEST_COUNT = 913
EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256 = (
    "c67806715d2ebbbc48395eaec9308d2c62946dd4c82ae1438aec157b05ebb488"
)
EXCLUDED_EXTERNAL_TEST_COUNT = 87
EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256 = (
    "0a641f6aa0d29985b3ac2f942cd8e78267c95d65c362cf0a03ee3ace1fb1585a"
)
REMAINING_TEST_COUNT = 1_000
REMAINING_TEST_MANIFEST_SHA256 = (
    "21353f330c03455a4cb66b55bc80846809c3505a1edfa77ea0695188fa908ee8"
)
DISTINCT_AFTER_ADDON_TEST_COUNT = 1_173
DISTINCT_AFTER_ADDON_TEST_MANIFEST_SHA256 = (
    "533de55b52fcda0f8af1871585e11fa846fdec6055c868791981ad5388711e67"
)

SELECTED_MODULE_COUNTS = {
    "CompanionCoreTests.": 1,
    "LocalAgentBridgeTests.": 52,
}
SELECTED_CLASS_COUNTS = {
    "AccessibilityAnnouncementTests": 1,
    "AetherLinkLocalizationTests": 39,
    "AetherLinkRenderSmokeTests": 11,
    "LocalRuntimeMessageRouterTests": 1,
    "PairingRouteNoticeTests": 1,
}
SELECTED_CLASS_PREFIX_COUNTS = {
    "CompanionCoreTests.LocalRuntimeMessageRouterTests/": 1,
    "LocalAgentBridgeTests.AccessibilityAnnouncementTests/": 1,
    "LocalAgentBridgeTests.AetherLinkLocalizationTests/": 39,
    "LocalAgentBridgeTests.AetherLinkRenderSmokeTests/": 11,
    "LocalAgentBridgeTests.PairingRouteNoticeTests/": 1,
}

ADDON_RELATIVE_PATHS = (
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
    Path("script/g7_nonsecurity_swift_successor_engine.py"),
    Path("script/test_check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
)
CANDIDATE_INTEGRATION_RELATIVE_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate_v4.py"),
    Path("script/run_g7_nonsecurity_merge_full_candidate_v4.py"),
    Path("script/test_g7_nonsecurity_merge_full_candidate_v4.py"),
)
ANTECEDENT_PROJECTION_RELATIVE_PATHS = tuple(
    sorted(
        ADDON_RELATIVE_PATHS + CANDIDATE_INTEGRATION_RELATIVE_PATHS,
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

OUTPUT_ROOT = ROOT / ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v4"
RUN_MARKER_PATH = OUTPUT_ROOT / "run-marker.json"
CONSOLE_PATH = OUTPUT_ROOT / "console.log"
BINDING_PATH = OUTPUT_ROOT / "binding.json"
RESULT_PATH = OUTPUT_ROOT / "result.json"
EXECUTION_CONTRACT_PATH = OUTPUT_ROOT / "execution-contract.json"

RESULT_MAX_BYTES = 2 * 1024 * 1024
COMMAND_AND_ENVIRONMENT_MAX_BYTES = 64 * 1024
RUN_TIMEOUT_SECONDS = 20 * 60

EXACT_SOURCE_FILES = tuple(
    dict.fromkeys(
        product_ci.SWIFT_FOCUSED_RESULT_EXACT_FILES
        + tuple(ROOT / path for path in ADDON_RELATIVE_PATHS)
        + (REVIEWED_IDENTITY_PATH, ANTECEDENT_PATH, EXECUTION_CONTRACT_PATH)
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
    antecedent_distinct: tuple[str, ...]
    reviewed_input: tuple[str, ...]
    selected: tuple[str, ...]
    excluded_by_scope: tuple[str, ...]
    excluded_external: tuple[str, ...]
    remaining: tuple[str, ...]
    distinct_after_addon: tuple[str, ...]


def canonical_json_bytes(value: object) -> bytes:
    return addon_v3.canonical_json_bytes(value)


def manifest_sha256(identities: Iterable[str]) -> str:
    return addon_v3.manifest_sha256(identities)


def exact_set_failures(
    label: str,
    identities: tuple[str, ...],
    expected_count: int,
    expected_manifest_sha256: str,
) -> list[str]:
    return addon_v3.exact_set_failures(
        label,
        identities,
        expected_count,
        expected_manifest_sha256,
    )


def load_reviewed_tests() -> tuple[tuple[str, ...] | None, list[str]]:
    try:
        relative = REVIEWED_IDENTITY_PATH.relative_to(ROOT)
        data, mode = candidate_base.read_stable_regular_file(
            ROOT,
            relative,
            maximum_bytes=RESULT_MAX_BYTES,
        )
    except (ValueError, candidate_base.CandidateError) as error:
        return None, [f"reviewed identity manifest cannot be read: {error}"]
    failures: list[str] = []
    if mode != 0o644:
        failures.append("reviewed identity manifest mode must be 0644")
    if len(data) != REVIEWED_IDENTITY_BYTES:
        failures.append("reviewed identity manifest byte count differs")
    if hashlib.sha256(data).hexdigest() != REVIEWED_IDENTITY_RAW_SHA256:
        failures.append("reviewed identity manifest raw SHA-256 differs")
    if not data.endswith(b"\n") or b"\r" in data:
        failures.append("reviewed identity manifest must use canonical LF lines")
    try:
        text = data.decode("ascii")
    except UnicodeError as error:
        return None, failures + [f"reviewed identity manifest is not ASCII: {error}"]
    identities = tuple(text.splitlines())
    if tuple(sorted(identities)) != identities:
        failures.append("reviewed identity manifest identities must be sorted")
    if len(set(identities)) != len(identities):
        failures.append("reviewed identity manifest identities must be unique")
    if any(
        identity != identity.strip()
        or re.fullmatch(r"[^\s/]+\/[^\s/]+", identity) is None
        for identity in identities
    ):
        failures.append("reviewed identity manifest identities must be canonical")
    failures.extend(
        exact_set_failures(
            "new reviewed Swift",
            identities,
            NEW_TEST_COUNT,
            NEW_TEST_MANIFEST_SHA256,
        )
    )
    return (None if failures else identities), failures


def reconstruct_v3_partition(
    discovered: tuple[str, ...],
) -> tuple[addon_v3.Partition | None, list[str]]:
    v2_partition, failures = addon_v3.addon_v2.partition_shape_failures(discovered)
    if v2_partition is None:
        return None, failures
    v3_partition, v3_failures = addon_v3.partition_shape_failures(
        discovered,
        v2_partition,
    )
    failures.extend(v3_failures)
    return (None if failures else v3_partition), failures


def partition_shape_failures(
    discovered: tuple[str, ...],
    antecedent_partition: addon_v3.Partition,
    *,
    selected: tuple[str, ...] | None = None,
) -> tuple[Partition | None, list[str]]:
    failures: list[str] = []
    if selected is None:
        selected, selected_failures = load_reviewed_tests()
        failures.extend(selected_failures)
    if selected is None:
        return None, failures

    discovered_set = set(discovered)
    antecedent_set = set(antecedent_partition.distinct_after_addon)
    reviewed_input_set = set(antecedent_partition.remaining)
    prior_scope_set = set(antecedent_partition.excluded_by_scope)
    selected_set = set(selected)
    external_set = set(antecedent_partition.excluded_external)
    scope_set = prior_scope_set - selected_set
    remaining_set = scope_set | external_set
    distinct_set = antecedent_set | selected_set

    def ordered(values: set[str]) -> tuple[str, ...]:
        return tuple(sorted(values))

    partition = Partition(
        discovered=ordered(discovered_set),
        antecedent_distinct=ordered(antecedent_set),
        reviewed_input=ordered(reviewed_input_set),
        selected=ordered(selected_set),
        excluded_by_scope=ordered(scope_set),
        excluded_external=ordered(external_set),
        remaining=ordered(remaining_set),
        distinct_after_addon=ordered(distinct_set),
    )
    exact_contracts = (
        (
            "discovered Swift",
            partition.discovered,
            DISCOVERED_TEST_COUNT,
            DISCOVERED_TEST_MANIFEST_SHA256,
        ),
        (
            "antecedent distinct Swift",
            partition.antecedent_distinct,
            ANTECEDENT_DISTINCT_TEST_COUNT,
            ANTECEDENT_DISTINCT_TEST_MANIFEST_SHA256,
        ),
        (
            "reviewed input Swift",
            partition.reviewed_input,
            REVIEWED_INPUT_TEST_COUNT,
            REVIEWED_INPUT_TEST_MANIFEST_SHA256,
        ),
        ("new Swift", partition.selected, NEW_TEST_COUNT, NEW_TEST_MANIFEST_SHA256),
        (
            "scope-excluded Swift",
            partition.excluded_by_scope,
            EXCLUDED_BY_SCOPE_TEST_COUNT,
            EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256,
        ),
        (
            "external/socket excluded Swift",
            partition.excluded_external,
            EXCLUDED_EXTERNAL_TEST_COUNT,
            EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256,
        ),
        (
            "remaining Swift",
            partition.remaining,
            REMAINING_TEST_COUNT,
            REMAINING_TEST_MANIFEST_SHA256,
        ),
        (
            "distinct post-add-on Swift",
            partition.distinct_after_addon,
            DISTINCT_AFTER_ADDON_TEST_COUNT,
            DISTINCT_AFTER_ADDON_TEST_MANIFEST_SHA256,
        ),
    )
    for label, identities, count, digest in exact_contracts:
        failures.extend(exact_set_failures(label, identities, count, digest))

    if discovered != tuple(discovered) or len(discovered_set) != len(discovered):
        failures.append("Swift discovery identities must remain unique")
    if selected != tuple(sorted(selected)) or len(selected_set) != len(selected):
        failures.append("new reviewed Swift identities must remain sorted and unique")
    if antecedent_set & reviewed_input_set:
        failures.append("antecedent and reviewed-input sets must be disjoint")
    if antecedent_set | reviewed_input_set != discovered_set:
        failures.append("antecedent V3 partition must cover Swift discovery")
    if not selected_set <= prior_scope_set:
        failures.append("new reviewed tests must come only from V3 scope exclusions")
    if selected_set & external_set:
        failures.append("new reviewed tests must not include external/socket exclusions")
    if selected_set & antecedent_set:
        failures.append("new reviewed tests must be additive to V3")
    if selected_set & scope_set or selected_set & external_set:
        failures.append("new and excluded Swift sets must be disjoint")
    if scope_set & external_set:
        failures.append("scope and external exclusions must be disjoint")
    if selected_set | scope_set != prior_scope_set:
        failures.append("V3 scope exclusion classification must be complete")
    if selected_set | scope_set | external_set != reviewed_input_set:
        failures.append("reviewed input classification must be complete")
    if remaining_set != reviewed_input_set - selected_set:
        failures.append("remaining Swift set differs from reviewed input minus new")
    if distinct_set | remaining_set != discovered_set:
        failures.append("post-add-on Swift partition must cover discovery")
    if (
        ANTECEDENT_DISTINCT_TEST_COUNT + NEW_TEST_COUNT + REMAINING_TEST_COUNT
        != DISCOVERED_TEST_COUNT
    ):
        failures.append("post-add-on Swift count arithmetic differs")
    for prefix, expected in SELECTED_MODULE_COUNTS.items():
        if type(expected) is not int or expected < 0:
            failures.append(f"selected module count must be an exact integer: {prefix}")
            continue
        if sum(identity.startswith(prefix) for identity in selected_set) != expected:
            failures.append(f"selected module count differs: {prefix}")
    if any(
        not any(identity.startswith(prefix) for prefix in SELECTED_MODULE_COUNTS)
        for identity in selected_set
    ):
        failures.append("new reviewed tests must stay in the two reviewed modules")
    for prefix, expected in SELECTED_CLASS_PREFIX_COUNTS.items():
        if type(expected) is not int or expected < 0:
            failures.append(f"selected class count must be an exact integer: {prefix}")
            continue
        if sum(identity.startswith(prefix) for identity in selected_set) != expected:
            failures.append(f"selected class count differs: {prefix}")
    return (None if failures else partition), failures


def _validate_v3_candidate_document(document: object) -> list[str]:
    failures: list[str] = []
    if type(document) is not dict:
        return ["V3 antecedent candidate must be a JSON object"]
    expected_keys = {
        "artifacts",
        "commands",
        "contract",
        "coverage",
        "evidenceComposition",
        "implementation",
        "limitations",
        "pidPreservation",
        "result",
        "schemaVersion",
        "source",
        "v2ArtifactPreservation",
    }
    if set(document) != expected_keys:
        failures.append("V3 antecedent candidate top-level keys differ")
        return failures
    if document.get("contract") != candidate_v3.CONTRACT:
        failures.append("V3 antecedent candidate contract differs")
    if type(document.get("schemaVersion")) is not int or document.get(
        "schemaVersion"
    ) != candidate_v3.SCHEMA_VERSION:
        failures.append("V3 antecedent candidate schema version differs")
    if document.get("result") != "passed":
        failures.append("V3 antecedent candidate result must remain passed")
    source = document.get("source")
    if type(source) is not dict or set(source) != set(ANTECEDENT_SOURCE):
        failures.append("V3 antecedent candidate source shape differs")
    else:
        if type(source.get("fileCount")) is not int or type(source.get("size")) is not int:
            failures.append("V3 antecedent candidate source counts must be exact integers")
        if source != ANTECEDENT_SOURCE:
            failures.append("V3 antecedent candidate recorded source differs")
    coverage = document.get("coverage")
    if type(coverage) is not dict or set(coverage) != set(candidate_v3.EXPECTED_COVERAGE):
        failures.append("V3 antecedent candidate coverage shape differs")
    elif any(
        type(coverage.get(key)) is not int or coverage.get(key) != expected
        for key, expected in candidate_v3.EXPECTED_COVERAGE.items()
    ):
        failures.append("V3 antecedent candidate coverage differs")
    limitations = document.get("limitations")
    if type(limitations) is not dict or set(limitations) != set(
        candidate_v3.EXPECTED_LIMITATIONS
    ):
        failures.append("V3 antecedent candidate limitations shape differs")
    elif any(
        limitations.get(key) is not expected
        for key, expected in candidate_v3.EXPECTED_LIMITATIONS.items()
    ):
        failures.append("V3 antecedent candidate limitations differ")
    try:
        candidate_v3.validate_static_contract()
        candidate_v3.validate_commands(document.get("commands"))
        candidate_v3.validate_pid_preservation(document.get("pidPreservation"))
        candidate_base.validate_file_records(
            document.get("artifacts"),
            expected_paths=candidate_v3.EXPECTED_ARTIFACT_PATHS,
            label="V3 antecedent artifacts",
            root=ROOT,
        )
        candidate_base.validate_file_records(
            document.get("implementation"),
            expected_paths=candidate_v3.EXPECTED_IMPLEMENTATION_PATHS,
            label="V3 antecedent implementation",
            root=ROOT,
        )
        v2_record = candidate_base.file_record(
            ROOT,
            candidate_v3.V2_CANDIDATE_RELATIVE_PATH,
            maximum_bytes=RESULT_MAX_BYTES,
        )
        if v2_record != candidate_v3.EXPECTED_V2_CANDIDATE_RECORD:
            raise candidate_base.CandidateError(
                "V2 candidate bytes differ inside V3 antecedent"
            )
        v3_addon_record = candidate_base.file_record(
            ROOT,
            candidate_v3.V3_ADDON_RESULT_RELATIVE_PATH,
            maximum_bytes=RESULT_MAX_BYTES,
        )
        candidate_v3.validate_evidence_composition(
            document.get("evidenceComposition"),
            v2_candidate=v2_record,
            v3_addon_result=v3_addon_record,
        )
        preservation = candidate_base.exact_mapping(
            document.get("v2ArtifactPreservation"),
            {"after", "before", "preservedDuringRun"},
            "V3 antecedent v2ArtifactPreservation",
        )
        candidate_base.require_bool(
            preservation["preservedDuringRun"],
            True,
            "V3 antecedent v2ArtifactPreservation.preservedDuringRun",
        )
        if preservation["before"] != v2_record or preservation["after"] != v2_record:
            raise candidate_base.CandidateError(
                "V3 antecedent V2 preservation records differ"
            )
    except candidate_base.CandidateError as error:
        failures.append(f"V3 antecedent candidate evidence differs: {error}")
    return failures


def _candidate_antecedent_failures_for_delta(
    allowed_delta_paths: tuple[Path, ...],
) -> list[str]:
    failures: list[str] = []
    try:
        data, mode = candidate_base.read_stable_regular_file(
            ROOT,
            ANTECEDENT_RELATIVE_PATH,
            maximum_bytes=RESULT_MAX_BYTES,
        )
    except candidate_base.CandidateError as error:
        return [f"V3 antecedent candidate cannot be read: {error}"]
    if mode != 0o600:
        failures.append("V3 antecedent candidate mode must be 0600")
    if len(data) != ANTECEDENT_BYTES:
        failures.append("V3 antecedent candidate byte count differs")
    if hashlib.sha256(data).hexdigest() != ANTECEDENT_SHA256:
        failures.append("V3 antecedent candidate SHA-256 differs")
    try:
        document = json.loads(
            data,
            object_pairs_hook=candidate_base.reject_duplicate_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        candidate_base.DuplicateKeyError,
    ) as error:
        failures.append(f"V3 antecedent candidate JSON cannot be decoded: {error}")
        document = None
    if type(document) is not dict or canonical_json_bytes(document) != data:
        failures.append("V3 antecedent candidate must remain canonical JSON")
    else:
        failures.extend(_validate_v3_candidate_document(document))

    if len(set(allowed_delta_paths)) != len(allowed_delta_paths):
        failures.append("allowed V4 source delta paths must not contain duplicates")
        return failures
    if any(
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
        for path in allowed_delta_paths
    ):
        failures.append("allowed V4 source delta paths must be canonical repository paths")
        return failures
    try:
        current_paths = source_runner.git_source_paths(root=ROOT)
    except source_runner.CandidateError as error:
        failures.append(f"current source paths cannot be enumerated: {error}")
        return failures
    current_set = set(current_paths)
    delta_set = set(allowed_delta_paths)
    missing = tuple(sorted(delta_set - current_set, key=lambda path: path.as_posix()))
    if missing:
        failures.append(
            "allowed V4 source delta paths are missing: "
            + ", ".join(path.as_posix() for path in missing)
        )
        return failures
    for relative in allowed_delta_paths:
        try:
            _data, delta_mode = candidate_base.read_stable_regular_file(
                ROOT,
                relative,
                maximum_bytes=RESULT_MAX_BYTES,
            )
        except candidate_base.CandidateError as error:
            failures.append(f"V4 source delta cannot be inspected: {relative}: {error}")
            continue
        if delta_mode != 0o644:
            failures.append(f"V4 source delta mode must be 0644: {relative}")
    projected_paths = tuple(path for path in current_paths if path not in delta_set)
    try:
        projected = source_runner.source_snapshot(root=ROOT, paths=projected_paths)
    except source_runner.CandidateError as error:
        failures.append(f"V3 antecedent source projection failed: {error}")
    else:
        if projected != ANTECEDENT_SOURCE:
            failures.append(
                "current source minus the exact V4 source delta must equal the "
                "V3 antecedent source snapshot"
            )
    return failures


def candidate_antecedent_failures() -> list[str]:
    return _candidate_antecedent_failures_for_delta(
        ANTECEDENT_PROJECTION_RELATIVE_PATHS
    )


def contract_inputs() -> tuple[Partition | None, list[str]]:
    discovered, failures = addon_v3.addon_v2.load_discovered_tests()
    if discovered is None:
        return None, failures
    antecedent_partition, antecedent_failures = reconstruct_v3_partition(discovered)
    failures.extend(antecedent_failures)
    if antecedent_partition is None:
        return None, failures
    partition, partition_failures = partition_shape_failures(
        discovered,
        antecedent_partition,
    )
    failures.extend(partition_failures)
    failures.extend(candidate_antecedent_failures())
    if partition is None or failures:
        return None, failures
    return partition, []


def exact_filter(identities: tuple[str, ...]) -> str:
    return addon_v3.exact_filter(identities)


def _extra_self_test(partition: Partition) -> list[str]:
    failures: list[str] = []
    replacement = partition.excluded_by_scope[0]
    mutated = list(partition.selected)
    mutated[0] = replacement
    discovered, discovered_failures = addon_v3.addon_v2.load_discovered_tests()
    failures.extend(discovered_failures)
    if discovered is not None:
        antecedent, antecedent_failures = reconstruct_v3_partition(discovered)
        failures.extend(antecedent_failures)
        if antecedent is not None:
            observed, mutation_failures = partition_shape_failures(
                discovered,
                antecedent,
                selected=tuple(sorted(mutated)),
            )
            if observed is not None or not any(
                "manifest SHA-256 differs" in failure
                for failure in mutation_failures
            ):
                failures.append("same-count V4 identity substitution was not rejected")
    missing_delta_failures = _candidate_antecedent_failures_for_delta(
        ANTECEDENT_PROJECTION_RELATIVE_PATHS[:1]
    )
    if not missing_delta_failures:
        failures.append("incomplete V4 source delta was not rejected")
    return failures


CONFIG = engine.SuccessorConfig(
    root=ROOT,
    version_label="V4",
    contract=CONTRACT,
    execution_contract=EXECUTION_CONTRACT,
    schema_version=SCHEMA_VERSION,
    product_ci=product_ci,
    candidate_base=candidate_base,
    test_list_path=TEST_LIST_PATH,
    reviewed_identity_path=REVIEWED_IDENTITY_PATH,
    antecedent_path=ANTECEDENT_PATH,
    output_root=OUTPUT_ROOT,
    run_marker_path=RUN_MARKER_PATH,
    console_path=CONSOLE_PATH,
    binding_path=BINDING_PATH,
    result_path=RESULT_PATH,
    execution_contract_path=EXECUTION_CONTRACT_PATH,
    result_max_bytes=RESULT_MAX_BYTES,
    command_and_environment_max_bytes=COMMAND_AND_ENVIRONMENT_MAX_BYTES,
    run_timeout_seconds=RUN_TIMEOUT_SECONDS,
    exact_source_files=EXACT_SOURCE_FILES,
    limitations=LIMITATIONS,
    selected_module_counts=SELECTED_MODULE_COUNTS,
    selected_class_counts=SELECTED_CLASS_COUNTS,
    selected_class_prefix_counts=SELECTED_CLASS_PREFIX_COUNTS,
    discovered_test_count=DISCOVERED_TEST_COUNT,
    discovered_test_manifest_sha256=DISCOVERED_TEST_MANIFEST_SHA256,
    antecedent_distinct_test_count=ANTECEDENT_DISTINCT_TEST_COUNT,
    antecedent_distinct_test_manifest_sha256=(
        ANTECEDENT_DISTINCT_TEST_MANIFEST_SHA256
    ),
    reviewed_input_test_count=REVIEWED_INPUT_TEST_COUNT,
    reviewed_input_test_manifest_sha256=REVIEWED_INPUT_TEST_MANIFEST_SHA256,
    new_test_count=NEW_TEST_COUNT,
    new_test_manifest_sha256=NEW_TEST_MANIFEST_SHA256,
    excluded_by_scope_test_count=EXCLUDED_BY_SCOPE_TEST_COUNT,
    excluded_by_scope_test_manifest_sha256=EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256,
    excluded_external_test_count=EXCLUDED_EXTERNAL_TEST_COUNT,
    excluded_external_test_manifest_sha256=EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256,
    remaining_test_count=REMAINING_TEST_COUNT,
    remaining_test_manifest_sha256=REMAINING_TEST_MANIFEST_SHA256,
    distinct_after_addon_test_count=DISTINCT_AFTER_ADDON_TEST_COUNT,
    distinct_after_addon_test_manifest_sha256=(
        DISTINCT_AFTER_ADDON_TEST_MANIFEST_SHA256
    ),
    canonical_json_bytes=canonical_json_bytes,
    exact_filter=exact_filter,
    contract_inputs=contract_inputs,
    candidate_antecedent_failures=candidate_antecedent_failures,
    extra_self_test=_extra_self_test,
)


def physical_output_directory_failures(
    directory: Path,
    *,
    create: bool,
) -> list[str]:
    return engine.physical_output_directory_failures(CONFIG, directory, create=create)


def runner_command(
    partition: Partition,
) -> tuple[tuple[str, ...] | None, list[str]]:
    return engine.runner_command(CONFIG, partition)


def command_environment_footprint(
    command: tuple[str, ...],
    environment: dict[str, str],
) -> int:
    return engine.command_environment_footprint(CONFIG, command, environment)


def runner_contract(
    partition: Partition,
) -> tuple[tuple[str, ...] | None, dict[str, str] | None, list[str]]:
    return engine.runner_contract(CONFIG, partition)


def execution_contract_payload(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> dict[str, object]:
    return engine.execution_contract_payload(CONFIG, partition, command, environment)


def execution_contract_failures(
    partition: Partition,
    command: tuple[str, ...],
    *,
    expected_environment: dict[str, str] | None = None,
) -> list[str]:
    return engine.execution_contract_failures(
        CONFIG,
        partition,
        command,
        expected_environment=expected_environment,
    )


def write_execution_contract(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> list[str]:
    return engine.write_execution_contract(CONFIG, partition, command, environment)


def generic_arguments(partition: Partition) -> dict[str, object]:
    return engine.generic_arguments(CONFIG, partition)


def run_addon_tests(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> tuple[int, list[str]]:
    return engine.run_addon_tests(CONFIG, partition, command, environment)


def stable_record(path: Path, *, maximum_bytes: int) -> dict[str, object]:
    return engine.stable_record(CONFIG, path, maximum_bytes=maximum_bytes)


def result_payload(
    partition: Partition,
) -> tuple[dict[str, object] | None, list[str]]:
    return engine.result_payload(CONFIG, partition)


def result_failures(partition: Partition) -> list[str]:
    return engine.result_failures(CONFIG, partition)


def write_result(partition: Partition) -> list[str]:
    return engine.write_result(CONFIG, partition)


def self_test() -> list[str]:
    return engine.self_test(CONFIG)


def main(argv: Sequence[str] | None = None) -> int:
    return engine.main(CONFIG, argv)


if __name__ == "__main__":
    raise SystemExit(main())
