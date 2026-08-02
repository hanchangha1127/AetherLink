#!/usr/bin/env python3
"""Run and verify the next exact local non-security Swift XCTest add-on.

The passing G7 Merge-full V2 candidate remains an immutable antecedent.  This
contract classifies every one of its 1,150 unexecuted Swift identities and runs
only the 97 identities reviewed as deterministic, local, non-security work.
It deliberately makes no complete-suite, canonical G7, RC, GA, or V1 claim.
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
    from script import check_g7_nonsecurity_merge_full_candidate_v2 as candidate_v2
    from script import check_g7_reviewed_nonsecurity_swift_addon as addon_v2
else:
    import check_g7_nonsecurity_merge_full_candidate_v2 as candidate_v2
    import check_g7_reviewed_nonsecurity_swift_addon as addon_v2


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-g7-reviewed-nonsecurity-swift-addon-v3"
EXECUTION_CONTRACT = "aetherlink-g7-reviewed-nonsecurity-swift-execution-v3"
SCHEMA_VERSION = 1

product_ci = addon_v2.product_ci
candidate_base = candidate_v2.base
source_runner = addon_v2.antecedent_runner

TEST_LIST_PATH = addon_v2.TEST_LIST_PATH
DISCOVERED_TEST_COUNT = 2_173
DISCOVERED_TEST_MANIFEST_SHA256 = (
    "0a550e58480f4733abc264d0ec572e9511492a43dae6ea2dd5459c03548f4e65"
)

ANTECEDENT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v2/candidate.json"
)
ANTECEDENT_PATH = ROOT / ANTECEDENT_RELATIVE_PATH
ANTECEDENT_BYTES = 45_797
ANTECEDENT_SHA256 = (
    "4a05156b1f1d06d613a40d456f34af793c6d7647b6f639937bdf2190aaf24f45"
)
ANTECEDENT_SOURCE = {
    "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
    "fileCount": 1_002,
    "sha256": (
        "19b15cd5549da9eb20bf1f2dcc7d1541fa32f502a331ddc6bac5616f50a019d4"
    ),
    "size": 67_619_351,
}
ANTECEDENT_DISTINCT_TEST_COUNT = 1_023
ANTECEDENT_DISTINCT_TEST_MANIFEST_SHA256 = (
    "589d6a32bbdb7f24511c27d66f362a856ef1977eb524f8c0862d3752598c7282"
)
REVIEWED_INPUT_TEST_COUNT = 1_150
REVIEWED_INPUT_TEST_MANIFEST_SHA256 = (
    "aed047c9af8e4b06aad02064d034ffb70d0ab9dbef131acee6f346909b38ee48"
)

REVIEWED_IDENTITY_RELATIVE_PATH = Path(
    "script/g7_reviewed_nonsecurity_swift_addon_identities_v3.txt"
)
REVIEWED_IDENTITY_PATH = ROOT / REVIEWED_IDENTITY_RELATIVE_PATH
REVIEWED_IDENTITY_BYTES = 10_215
REVIEWED_IDENTITY_RAW_SHA256 = (
    "7bc3c61c9df45a8750d175d725bceabc9d7c34794576038575f821227eecc237"
)
NEW_TEST_COUNT = 97
NEW_TEST_MANIFEST_SHA256 = (
    "a165a85de87355426d35fdbead9c86b0756ef83fe11cd01a6b7674ef2bf66b50"
)
EXCLUDED_BY_SCOPE_TEST_COUNT = 966
EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256 = (
    "7fd64d3a27a1ee79ebb5c18b0a09d5e5bdf9ba57b107e0da8539470d8796c61c"
)
EXCLUDED_EXTERNAL_TEST_COUNT = 87
EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256 = (
    "0a641f6aa0d29985b3ac2f942cd8e78267c95d65c362cf0a03ee3ace1fb1585a"
)
REMAINING_TEST_COUNT = 1_053
REMAINING_TEST_MANIFEST_SHA256 = (
    "bc896a061126bb1958ac7c50ea6558ad174bb82418a7d2687cf99e2489d1e697"
)
DISTINCT_AFTER_ADDON_TEST_COUNT = 1_120
DISTINCT_AFTER_ADDON_TEST_MANIFEST_SHA256 = (
    "aaa5bfb601c28f89e52ab8d1d8da95c81b876eb4d5ea2cc0d1afb8f2ccd2bf18"
)

SELECTED_MODULE_COUNTS = {
    "BridgeProtocolTests.": 12,
    "CompanionCoreTests.": 49,
    "LocalAgentBridgeTests.": 6,
    "P2PNATContractsTests.": 5,
    "RelayServerCoreTests.": 16,
    "TransportTests.": 9,
}

EXTERNAL_COMPANION_TESTS = (
    "CompanionCoreTests.LocalRuntimeMessageRouterTests/"
    "testTCPRelayServiceRouteAllocatorRejectsMismatchedAndExpiredChallenges",
    "CompanionCoreTests.LocalRuntimeMessageRouterTests/"
    "testTCPRelayServiceRouteAllocatorRejectsSecretAndAnyExtraV2ResponseFields",
    "CompanionCoreTests.LocalRuntimeMessageRouterTests/"
    "testTCPRelayServiceRouteAllocatorRequiresClosedV2ResponseShape",
    "CompanionCoreTests.LocalRuntimeMessageRouterTests/"
    "testTCPRelayServiceRouteAllocatorSendsExactV2RequestAndReturnsSecretFreeMetadata",
    "CompanionCoreTests.LocalRuntimeMessageRouterTests/"
    "testTCPRelayServiceRouteAllocatorUsesAbsoluteDeadlineAgainstSlowTrickle",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testClaimSendsExactWireAndVerifiesBothProofs",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testClientAuthorizationTimeoutClosesBoundedSocketTransaction",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testDisconnectAfterChallengeFailsWithoutAllocation",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testRejectsFinalAllocationMutationAfterSendingValidProofs",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testRejectsUnknownChallengeFieldAndStaleChallenge",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testRejectsWrongChallengePrefixWithoutCallingProvider",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testRejectsWrongClientProofBeforeSendingProofLine",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testRenewSendsExactWireAndPreservesNextTicketGeneration",
    "CompanionCoreTests.PairedRelayAllocationClientTests/"
    "testSignerFailureStopsBeforeClientAuthorization",
)
RELAY_PEER_SCOPE_EXCLUSIONS = (
    "TransportTests.RelayPeerClientTests/"
    "testRelayPeerConfigurationPreservesRuntimeIdentityAuthorizationAcrossNonceRefresh",
    "TransportTests.RelayPeerClientTests/"
    "testRelayPeerConnectionCompletionReportsEncryptionFailure",
)

ADDON_RELATIVE_PATHS = (
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
    REVIEWED_IDENTITY_RELATIVE_PATH,
    Path("script/test_check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
)
CANDIDATE_INTEGRATION_RELATIVE_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate_v3.py"),
    Path("script/run_g7_nonsecurity_merge_full_candidate_v3.py"),
    Path("script/test_g7_nonsecurity_merge_full_candidate_v3.py"),
)
ANTECEDENT_PROJECTION_RELATIVE_PATHS = tuple(
    sorted(
        ADDON_RELATIVE_PATHS + CANDIDATE_INTEGRATION_RELATIVE_PATHS,
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

OUTPUT_ROOT = ROOT / ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v3"
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
    antecedent_distinct: tuple[str, ...]
    reviewed_input: tuple[str, ...]
    selected: tuple[str, ...]
    excluded_by_scope: tuple[str, ...]
    excluded_external: tuple[str, ...]
    remaining: tuple[str, ...]
    distinct_after_addon: tuple[str, ...]


def canonical_json_bytes(value: object) -> bytes:
    return addon_v2.canonical_json_bytes(value)


def manifest_sha256(identities: Iterable[str]) -> str:
    return addon_v2.manifest_sha256(identities)


def exact_set_failures(
    label: str,
    identities: tuple[str, ...],
    expected_count: int,
    expected_manifest_sha256: str,
) -> list[str]:
    return addon_v2.exact_set_failures(
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


def external_or_socket_tests(
    reviewed_input: tuple[str, ...],
    selected: tuple[str, ...],
) -> tuple[tuple[str, ...], list[str]]:
    reviewed_set = set(reviewed_input)
    selected_set = set(selected)
    failures: list[str] = []
    companion = set(EXTERNAL_COMPANION_TESTS)
    live = {identity for identity in reviewed_set if "/testLive" in identity}
    relay_socket = {
        identity
        for identity in reviewed_set
        if identity.startswith(
            "RelayServerCoreTests.RelayIdentityBoundSocketTests/"
        )
    } - selected_set
    local_server = {
        identity
        for identity in reviewed_set
        if identity.startswith("TransportTests.LocalPeerServerTests/")
    }
    relay_peer_all = {
        identity
        for identity in reviewed_set
        if identity.startswith("TransportTests.RelayPeerClientTests/")
    }
    relay_peer = relay_peer_all - selected_set - set(RELAY_PEER_SCOPE_EXCLUSIONS)
    expected_group_counts = (
        ("external Companion", companion, 14),
        ("live provider", live, 11),
        ("relay bound socket", relay_socket, 40),
        ("local peer server", local_server, 4),
        ("relay peer client", relay_peer, 18),
    )
    for label, identities, expected in expected_group_counts:
        if len(identities) != expected:
            failures.append(
                f"{label} classification must contain {expected} tests, "
                f"found {len(identities)}"
            )
    if not companion <= reviewed_set:
        failures.append("external Companion classification contains unknown tests")
    if not set(RELAY_PEER_SCOPE_EXCLUSIONS) <= relay_peer_all:
        failures.append("relay peer scope exclusions contain unknown tests")
    external = tuple(
        sorted(companion | live | relay_socket | local_server | relay_peer)
    )
    if set(external) & selected_set:
        failures.append("selected and external/socket test sets must be disjoint")
    failures.extend(
        exact_set_failures(
            "external/socket excluded Swift",
            external,
            EXCLUDED_EXTERNAL_TEST_COUNT,
            EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256,
        )
    )
    return external, failures


def partition_shape_failures(
    discovered: tuple[str, ...],
    antecedent_partition: addon_v2.Partition,
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
    reviewed_input_set = set(antecedent_partition.not_executed)
    selected_set = set(selected)
    external, external_failures = external_or_socket_tests(
        tuple(sorted(reviewed_input_set)),
        tuple(sorted(selected_set)),
    )
    failures.extend(external_failures)
    external_set = set(external)
    scope_set = reviewed_input_set - selected_set - external_set
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
        failures.append("antecedent V2 partition must cover Swift discovery")
    if not selected_set <= reviewed_input_set:
        failures.append("new reviewed tests must come from V2 not-executed tests")
    if selected_set & antecedent_set:
        failures.append("new reviewed tests must be additive to V2")
    if selected_set & scope_set or selected_set & external_set:
        failures.append("new and excluded Swift sets must be disjoint")
    if scope_set & external_set:
        failures.append("scope and external exclusions must be disjoint")
    if selected_set | scope_set | external_set != reviewed_input_set:
        failures.append("reviewed input classification must be complete")
    if remaining_set != reviewed_input_set - selected_set:
        failures.append("remaining Swift set differs from reviewed input minus new")
    if distinct_set | remaining_set != discovered_set:
        failures.append("post-add-on Swift partition must cover discovery")
    if (
        ANTECEDENT_DISTINCT_TEST_COUNT
        + NEW_TEST_COUNT
        + REMAINING_TEST_COUNT
        != DISCOVERED_TEST_COUNT
    ):
        failures.append("post-add-on Swift count arithmetic differs")
    for prefix, expected in SELECTED_MODULE_COUNTS.items():
        if type(expected) is not int or expected < 0:
            failures.append(f"selected module count must be an exact integer: {prefix}")
            continue
        observed = sum(identity.startswith(prefix) for identity in selected_set)
        if observed != expected:
            failures.append(f"selected module count differs: {prefix}")
    if any(
        not any(identity.startswith(prefix) for prefix in SELECTED_MODULE_COUNTS)
        for identity in selected_set
    ):
        failures.append("new reviewed tests must stay in the six reviewed modules")
    return (None if failures else partition), failures


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
        return [f"V2 antecedent candidate cannot be read: {error}"]
    if mode != 0o600:
        failures.append("V2 antecedent candidate mode must be 0600")
    if len(data) != ANTECEDENT_BYTES:
        failures.append("V2 antecedent candidate byte count differs")
    if hashlib.sha256(data).hexdigest() != ANTECEDENT_SHA256:
        failures.append("V2 antecedent candidate SHA-256 differs")
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
        failures.append(f"V2 antecedent candidate JSON cannot be decoded: {error}")
        document = None
    if type(document) is not dict or canonical_json_bytes(document) != data:
        failures.append("V2 antecedent candidate must remain canonical JSON")
    else:
        if document.get("contract") != candidate_v2.CONTRACT:
            failures.append("V2 antecedent candidate contract differs")
        if document.get("schemaVersion") != candidate_v2.SCHEMA_VERSION:
            failures.append("V2 antecedent candidate schema version differs")
        if document.get("result") != "passed":
            failures.append("V2 antecedent candidate result must remain passed")
        if document.get("source") != ANTECEDENT_SOURCE:
            failures.append("V2 antecedent candidate recorded source differs")
        commands = document.get("commands")
        if type(commands) is not list or tuple(
            command.get("id") if type(command) is dict else None
            for command in commands
        ) != candidate_v2.EXPECTED_COMMAND_IDS:
            failures.append("V2 antecedent candidate command sequence differs")
        if type(document.get("artifacts")) is not list or len(
            document["artifacts"]
        ) != 32:
            failures.append("V2 antecedent candidate artifact count differs")
        if type(document.get("implementation")) is not list or len(
            document["implementation"]
        ) != 11:
            failures.append("V2 antecedent candidate implementation count differs")
        coverage = document.get("coverage")
        expected_coverage = {
            "swiftDiscoveredTests": DISCOVERED_TEST_COUNT,
            "swiftDistinctNonsecurityTests": ANTECEDENT_DISTINCT_TEST_COUNT,
            "swiftNotExecutedTests": REVIEWED_INPUT_TEST_COUNT,
            "swiftReviewedAddonTests": 626,
        }
        if type(coverage) is not dict or any(
            type(coverage.get(key)) is not int or coverage.get(key) != expected
            for key, expected in expected_coverage.items()
        ):
            failures.append("V2 antecedent candidate Swift coverage differs")
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
            failures.append("V2 antecedent candidate limitations differ")
        try:
            candidate_v2.validate_static_contract()
            candidate_v2.validate_commands(document.get("commands"))
            candidate_base.validate_file_records(
                document.get("artifacts"),
                expected_paths=candidate_v2.EXPECTED_ARTIFACT_PATHS,
                label="V2 antecedent artifacts",
                root=ROOT,
            )
            candidate_base.validate_file_records(
                document.get("implementation"),
                expected_paths=candidate_v2.EXPECTED_IMPLEMENTATION_PATHS,
                label="V2 antecedent implementation",
                root=ROOT,
            )
        except candidate_base.CandidateError as error:
            failures.append(f"V2 antecedent candidate evidence differs: {error}")

    if len(set(allowed_delta_paths)) != len(allowed_delta_paths):
        failures.append("allowed V3 source delta paths must not contain duplicates")
        return failures
    if any(path.is_absolute() or ".." in path.parts for path in allowed_delta_paths):
        failures.append("allowed V3 source delta paths must be repository-relative")
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
            "allowed V3 source delta paths are missing: "
            + ", ".join(path.as_posix() for path in missing)
        )
        return failures
    for relative in allowed_delta_paths:
        try:
            _data, mode = candidate_base.read_stable_regular_file(
                ROOT,
                relative,
                maximum_bytes=RESULT_MAX_BYTES,
            )
        except candidate_base.CandidateError as error:
            failures.append(f"V3 source delta cannot be inspected: {relative}: {error}")
            continue
        if mode != 0o644:
            failures.append(f"V3 source delta mode must be 0644: {relative}")
    projected_paths = tuple(path for path in current_paths if path not in delta_set)
    try:
        projected = source_runner.source_snapshot(root=ROOT, paths=projected_paths)
    except source_runner.CandidateError as error:
        failures.append(f"V2 antecedent source projection failed: {error}")
    else:
        if projected != ANTECEDENT_SOURCE:
            failures.append(
                "current source minus the exact V3 add-on paths must equal the "
                "V2 antecedent source snapshot"
            )
    return failures


def candidate_antecedent_failures() -> list[str]:
    return _candidate_antecedent_failures_for_delta(
        ANTECEDENT_PROJECTION_RELATIVE_PATHS
    )


def contract_inputs() -> tuple[Partition | None, list[str]]:
    discovered, failures = addon_v2.load_discovered_tests()
    if discovered is None:
        return None, failures
    antecedent_partition, antecedent_partition_failures = (
        addon_v2.partition_shape_failures(discovered)
    )
    failures.extend(antecedent_partition_failures)
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
    return addon_v2.exact_skip_filter(identities)


def command_environment_footprint(
    command: tuple[str, ...],
    environment: dict[str, str],
) -> int:
    return addon_v2.command_environment_footprint(command, environment)


def physical_output_directory_failures(
    directory: Path,
    *,
    create: bool,
) -> list[str]:
    try:
        relative = directory.relative_to(ROOT)
    except ValueError:
        return ["V3 output directory must remain inside the repository"]
    current = ROOT
    for index, component in enumerate(relative.parts):
        current /= component
        try:
            value = current.lstat()
        except FileNotFoundError:
            if create and index == len(relative.parts) - 1:
                try:
                    current.mkdir(mode=0o700)
                    value = current.lstat()
                except OSError as error:
                    return [f"V3 output directory cannot be created: {error}"]
            else:
                return [f"V3 output directory component is missing: {current}"]
        except OSError as error:
            return [f"V3 output directory cannot be inspected: {current}: {error}"]
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            return [f"V3 output directory must be a physical directory: {current}"]
        if (
            index == len(relative.parts) - 1
            and stat.S_IMODE(value.st_mode) != 0o700
        ):
            return [f"V3 output directory mode must be 0700: {current}"]
    return []


def runner_command(
    partition: Partition,
) -> tuple[tuple[str, ...] | None, list[str]]:
    failures: list[str] = []
    filter_pattern = exact_filter(partition.selected)
    command = (
        "/usr/bin/sandbox-exec",
        "-p",
        product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
        "/usr/bin/swift",
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
        filter_pattern,
    )
    try:
        selected_by_command = {
            identity
            for identity in partition.discovered
            if re.search(command[8], identity)
        }
    except re.error as error:
        failures.append(f"runner exact filter regex is invalid: {error}")
        selected_by_command = set()
    if selected_by_command != set(partition.selected):
        failures.append("runner exact filter differs from the 97-test reviewed set")
    if "--skip" in command:
        failures.append("V3 runner must not use a skip filter")
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
    if environment is not None and (
        command_environment_footprint(command, environment)
        > COMMAND_AND_ENVIRONMENT_MAX_BYTES
    ):
        failures.append("runner argv/environment footprint exceeds fixed bound")
    if failures or environment is None:
        return None, None, failures
    return command, environment, []


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
        "contract": EXECUTION_CONTRACT,
        "environment": environment,
        "filterExcluded": 0,
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
            "antecedentDistinctManifestSha256": (
                ANTECEDENT_DISTINCT_TEST_MANIFEST_SHA256
            ),
            "antecedentDistinctTests": ANTECEDENT_DISTINCT_TEST_COUNT,
            "excludedByScopeManifestSha256": (
                EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256
            ),
            "excludedByScopeTests": EXCLUDED_BY_SCOPE_TEST_COUNT,
            "excludedExternalManifestSha256": (
                EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256
            ),
            "excludedExternalTests": EXCLUDED_EXTERNAL_TEST_COUNT,
            "newManifestSha256": NEW_TEST_MANIFEST_SHA256,
            "newTests": NEW_TEST_COUNT,
            "remainingManifestSha256": REMAINING_TEST_MANIFEST_SHA256,
            "remainingTests": REMAINING_TEST_COUNT,
            "reviewedInputManifestSha256": REVIEWED_INPUT_TEST_MANIFEST_SHA256,
            "reviewedInputTests": REVIEWED_INPUT_TEST_COUNT,
        },
        "schemaVersion": SCHEMA_VERSION,
    }


def execution_contract_failures(
    partition: Partition,
    command: tuple[str, ...],
    *,
    expected_environment: dict[str, str] | None = None,
) -> list[str]:
    directory_failures = physical_output_directory_failures(
        EXECUTION_CONTRACT_PATH.parent,
        create=False,
    )
    if directory_failures:
        return directory_failures
    try:
        data, mode = candidate_base.read_stable_regular_file(
            ROOT,
            EXECUTION_CONTRACT_PATH.relative_to(ROOT),
            maximum_bytes=COMMAND_AND_ENVIRONMENT_MAX_BYTES,
        )
    except candidate_base.CandidateError as error:
        return [f"V3 execution contract cannot be read: {error}"]
    failures: list[str] = []
    if mode != 0o600:
        failures.append("V3 execution contract mode must be 0600")
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
        return failures + [f"V3 execution contract JSON cannot be decoded: {error}"]
    if type(document) is not dict or data != canonical_json_bytes(document):
        failures.append("V3 execution contract must be canonical JSON")
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
        failures.append("V3 execution contract environment must be a string mapping")
        recorded_environment = {}
    normalized_environment, environment_failures = (
        product_ci.g7_nonsecurity_swift_environment(recorded_environment)
    )
    failures.extend(
        "V3 execution contract environment: " + failure
        for failure in environment_failures
    )
    if normalized_environment != recorded_environment:
        failures.append("V3 execution contract environment is not the exact allowlist")
    if expected_environment is not None and recorded_environment != expected_environment:
        failures.append("V3 execution contract environment differs from this run")
    expected = execution_contract_payload(partition, command, recorded_environment)
    if data != canonical_json_bytes(expected):
        failures.append("V3 execution contract command/profile/selection differs")
    return failures


def write_execution_contract(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> list[str]:
    failures = physical_output_directory_failures(
        EXECUTION_CONTRACT_PATH.parent,
        create=True,
    )
    if failures:
        return failures
    failures = product_ci.write_canonical_json_payload(
        EXECUTION_CONTRACT_PATH,
        execution_contract_payload(partition, command, environment),
        label="G7 reviewed non-security Swift V3 execution contract",
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


def generic_arguments(partition: Partition) -> dict[str, object]:
    return {
        "binding_path": BINDING_PATH,
        "marker_path": RUN_MARKER_PATH,
        "log_path": CONSOLE_PATH,
        "test_list_path": TEST_LIST_PATH,
        "filter_pattern": exact_filter(partition.selected),
        "expected_count": NEW_TEST_COUNT,
        "expected_manifest_sha256": NEW_TEST_MANIFEST_SHA256,
        "excluded_tests": (),
        "exact_files": EXACT_SOURCE_FILES,
    }


def run_addon_tests(
    partition: Partition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> tuple[int, list[str]]:
    directory_failures = physical_output_directory_failures(
        CONSOLE_PATH.parent,
        create=False,
    )
    if directory_failures:
        return 1, directory_failures
    common = generic_arguments(partition)
    marker_failures = product_ci.swift_focused_test_run_marker_failures(
        **{key: value for key, value in common.items() if key != "binding_path"},
        require_log=False,
    )
    if marker_failures:
        return 1, marker_failures
    _, expected_tests, selection_failures = (
        product_ci.swift_focused_test_list_snapshot(
            test_list_path=TEST_LIST_PATH,
            filter_pattern=exact_filter(partition.selected),
            expected_count=NEW_TEST_COUNT,
            expected_manifest_sha256=NEW_TEST_MANIFEST_SHA256,
            excluded_tests=(),
        )
    )
    if expected_tests is None:
        return 1, selection_failures

    def validate_log_context(candidate_log_path: Path) -> list[str]:
        return product_ci.swift_focused_test_run_marker_failures(
            marker_path=RUN_MARKER_PATH,
            log_path=candidate_log_path,
            test_list_path=TEST_LIST_PATH,
            filter_pattern=exact_filter(partition.selected),
            expected_count=NEW_TEST_COUNT,
            expected_manifest_sha256=NEW_TEST_MANIFEST_SHA256,
            excluded_tests=(),
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
    data, mode = candidate_base.read_stable_regular_file(
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


def partition_record(
    tests: int,
    digest: str,
) -> dict[str, object]:
    return {"manifestSha256": digest, "tests": tests}


def result_payload(partition: Partition) -> tuple[dict[str, object] | None, list[str]]:
    directory_failures = physical_output_directory_failures(
        RESULT_PATH.parent,
        create=False,
    )
    if directory_failures:
        return None, directory_failures
    try:
        artifacts = {
            "antecedentCandidate": stable_record(
                ANTECEDENT_PATH,
                maximum_bytes=RESULT_MAX_BYTES,
            ),
            "binding": stable_record(BINDING_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "console": stable_record(
                CONSOLE_PATH,
                maximum_bytes=product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
            ),
            "executionContract": stable_record(
                EXECUTION_CONTRACT_PATH,
                maximum_bytes=COMMAND_AND_ENVIRONMENT_MAX_BYTES,
            ),
            "reviewedIdentityManifest": stable_record(
                REVIEWED_IDENTITY_PATH,
                maximum_bytes=RESULT_MAX_BYTES,
            ),
            "runMarker": stable_record(RUN_MARKER_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "testList": stable_record(TEST_LIST_PATH, maximum_bytes=RESULT_MAX_BYTES),
        }
    except (ValueError, candidate_base.CandidateError) as error:
        return None, [f"V3 add-on result artifact cannot be read: {error}"]
    expected_modes = {
        "antecedentCandidate": 0o600,
        "binding": 0o600,
        "console": 0o600,
        "executionContract": 0o600,
        "reviewedIdentityManifest": 0o644,
        "runMarker": 0o600,
        "testList": 0o600,
    }
    mode_failures = [
        f"V3 add-on artifact mode differs: {label}"
        for label, expected_mode in expected_modes.items()
        if artifacts[label]["mode"] != expected_mode
    ]
    if mode_failures:
        return None, mode_failures
    return (
        {
            "artifacts": artifacts,
            "contract": CONTRACT,
            "limitations": LIMITATIONS,
            "partition": {
                "antecedentDistinct": partition_record(
                    ANTECEDENT_DISTINCT_TEST_COUNT,
                    ANTECEDENT_DISTINCT_TEST_MANIFEST_SHA256,
                ),
                "discovered": partition_record(
                    DISCOVERED_TEST_COUNT,
                    DISCOVERED_TEST_MANIFEST_SHA256,
                ),
                "distinctAfterAddon": partition_record(
                    DISTINCT_AFTER_ADDON_TEST_COUNT,
                    DISTINCT_AFTER_ADDON_TEST_MANIFEST_SHA256,
                ),
                "excludedByScope": partition_record(
                    EXCLUDED_BY_SCOPE_TEST_COUNT,
                    EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256,
                ),
                "excludedExternal": partition_record(
                    EXCLUDED_EXTERNAL_TEST_COUNT,
                    EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256,
                ),
                "newExecuted": partition_record(
                    NEW_TEST_COUNT,
                    NEW_TEST_MANIFEST_SHA256,
                ),
                "remaining": partition_record(
                    REMAINING_TEST_COUNT,
                    REMAINING_TEST_MANIFEST_SHA256,
                ),
                "reviewedInput": partition_record(
                    REVIEWED_INPUT_TEST_COUNT,
                    REVIEWED_INPUT_TEST_MANIFEST_SHA256,
                ),
            },
            "result": "passed",
            "schemaVersion": SCHEMA_VERSION,
            "scope": {
                "classifiedReviewedInputTests": REVIEWED_INPUT_TEST_COUNT,
                "selectedByModule": SELECTED_MODULE_COUNTS,
                "securityAuthenticationOrSecureChannelSuitesExecuted": False,
                "unclassifiedTests": 0,
            },
        },
        [],
    )


def result_failures(partition: Partition) -> list[str]:
    failures = physical_output_directory_failures(
        RESULT_PATH.parent,
        create=False,
    )
    failures.extend(candidate_antecedent_failures())
    command, command_failures = runner_command(partition)
    failures.extend(command_failures)
    if command is not None:
        failures.extend(execution_contract_failures(partition, command))
    failures.extend(
        product_ci.swift_focused_test_binding_failures(**generic_arguments(partition))
    )
    expected, payload_failures = result_payload(partition)
    failures.extend(payload_failures)
    if expected is None:
        return failures
    try:
        data, mode = candidate_base.read_stable_regular_file(
            ROOT,
            RESULT_PATH.relative_to(ROOT),
            maximum_bytes=RESULT_MAX_BYTES,
        )
    except candidate_base.CandidateError as error:
        failures.append(f"V3 add-on result cannot be read: {error}")
        return failures
    if mode != 0o600:
        failures.append("V3 add-on result mode must be 0600")
    try:
        observed = json.loads(
            data,
            object_pairs_hook=candidate_base.reject_duplicate_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        candidate_base.DuplicateKeyError,
    ) as error:
        failures.append(f"V3 add-on result JSON cannot be decoded: {error}")
        return failures
    if type(observed) is not dict or data != canonical_json_bytes(observed):
        failures.append("V3 add-on result must be canonical JSON")
    if data != canonical_json_bytes(expected):
        failures.append("V3 add-on result must exactly bind current evidence bytes")
    return failures


def write_result(partition: Partition) -> list[str]:
    failures = physical_output_directory_failures(
        RESULT_PATH.parent,
        create=False,
    )
    failures.extend(product_ci.swift_focused_test_binding_failures(
        **generic_arguments(partition)
    ))
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
            label="G7 reviewed non-security Swift V3 add-on result",
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
    if command[:4] != (
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1)(allow default)(deny network*)",
        "/usr/bin/swift",
    ):
        failures.append("V3 runner sandbox prefix differs")
    if command[4:8] != (
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
    ):
        failures.append("V3 runner serial exact-filter contract differs")
    if command[8] != exact_filter(partition.selected) or "--skip" in command:
        failures.append("V3 runner selection contract differs")
    replacement = "CompanionCoreTests.FixtureTests/testSyntheticV3Drift"
    mutated = list(partition.selected)
    mutated[0] = replacement
    observed, mutation_failures = partition_shape_failures(
        partition.discovered,
        addon_v2.Partition(
            discovered=partition.discovered,
            base_reviewed=(),
            method_reviewed=(),
            reviewed=(),
            antecedent=(),
            companion_reviewed=(),
            runner_reviewed=(),
            overlap=(),
            base_new=(),
            new=(),
            distinct_after_addon=partition.antecedent_distinct,
            not_executed=partition.reviewed_input,
        ),
        selected=tuple(sorted(mutated)),
    )
    if observed is not None or not any(
        "manifest SHA-256 differs" in failure for failure in mutation_failures
    ):
        failures.append("same-count V3 identity substitution was not rejected")
    missing_delta_failures = _candidate_antecedent_failures_for_delta(
        ANTECEDENT_PROJECTION_RELATIVE_PATHS[:1]
    )
    if not missing_delta_failures:
        failures.append("incomplete V3 source delta was not rejected")
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
        return print_failures("G7 reviewed Swift V3 add-on preflight failed", failures)

    if args.self_test:
        failures = self_test()
        if failures:
            return print_failures("G7 reviewed Swift V3 self-test failed", failures)
        print("G7 reviewed non-security Swift V3 contract self-test passed.")
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
                    **{
                        key: value
                        for key, value in common.items()
                        if key not in ("binding_path", "log_path")
                    }
                )
            )
        if failures:
            return print_failures("G7 reviewed Swift V3 preparation failed", failures)
        print(f"G7 reviewed Swift V3 marker passed: {NEW_TEST_COUNT} new tests.")
        return 0

    if args.run:
        command, environment, runner_failures = runner_contract(partition)
        failures.extend(runner_failures)
        if command is None or environment is None:
            return print_failures("G7 reviewed Swift V3 runner failed", failures)
        failures.extend(
            execution_contract_failures(
                partition,
                command,
                expected_environment=environment,
            )
        )
        if failures:
            return print_failures("G7 reviewed Swift V3 runner failed", failures)
        status, run_failures = run_addon_tests(partition, command, environment)
        failures.extend(run_failures)
        if status != 0 or failures:
            return print_failures("G7 reviewed Swift V3 runner failed", failures)
        print(
            f"G7 reviewed Swift V3 run passed: {NEW_TEST_COUNT}/{NEW_TEST_COUNT}; "
            "runtimeSkipped=0; failures=0; network-deny profile applied."
        )
        return 0

    if args.write_binding:
        command, command_failures = runner_command(partition)
        failures.extend(command_failures)
        if command is not None:
            failures.extend(execution_contract_failures(partition, command))
        failures.extend(
            physical_output_directory_failures(
                BINDING_PATH.parent,
                create=False,
            )
        )
        if not failures:
            failures.extend(product_ci.write_swift_focused_test_binding(**common))
        if not failures:
            failures.extend(write_result(partition))
        if failures:
            return print_failures("G7 reviewed Swift V3 binding failed", failures)
        print(
            f"G7 reviewed Swift V3 binding passed: {NEW_TEST_COUNT}/"
            f"{NEW_TEST_COUNT}; distinct local Swift evidence "
            f"{DISTINCT_AFTER_ADDON_TEST_COUNT}."
        )
        return 0

    failures.extend(result_failures(partition))
    if failures:
        return print_failures("G7 reviewed Swift V3 readback failed", failures)
    print(
        f"G7 reviewed Swift V3 readback passed: {NEW_TEST_COUNT}/"
        f"{NEW_TEST_COUNT}; distinct local Swift evidence "
        f"{DISTINCT_AFTER_ADDON_TEST_COUNT}; canonical G7 remains unclaimed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
