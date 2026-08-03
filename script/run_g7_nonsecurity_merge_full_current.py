#!/usr/bin/env python3
"""Run the reviewed non-security Swift union once on the current checkout.

Historical V1-V4 candidates remain immutable snapshot evidence.  This runner
reconstructs their reviewed identity union, the two current recovery
regressions, and exact strict non-security V5/V6 manifests.  It removes four
exact local-socket identities from this no-socket lane, then executes all 1,204
remaining identities in one serial
network-denied Swift invocation.
After the separately bound focused 222-test child and this 1,204-test child
both pass on one test list, the optional parent result contributes only the
four exact local-socket identities and records a 1,208-test reviewed union.
It does not claim the complete Swift suite, canonical Merge-full, G7 exit, RC,
GA, or V1 qualification.
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
import time
from typing import Iterable, Sequence

if __package__:
    from script import check_g7_nonsecurity_merge_full_current as independent_checker
    from script import check_g7_reviewed_nonsecurity_swift_addon as addon_v2
    from script import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    from script import check_g7_reviewed_nonsecurity_swift_addon_v4 as addon_v4
    from script import check_product_ci as product_ci
else:
    import check_g7_nonsecurity_merge_full_current as independent_checker
    import check_g7_reviewed_nonsecurity_swift_addon as addon_v2
    import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    import check_g7_reviewed_nonsecurity_swift_addon_v4 as addon_v4
    import check_product_ci as product_ci


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-current-run-v1"
EXECUTION_CONTRACT = (
    "aetherlink-g7-nonsecurity-merge-full-current-run-execution-v1"
)
OUTPUT_ROOT = ROOT / (
    ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1"
)
EXECUTION_CONTRACT_PATH = OUTPUT_ROOT / "execution-contract.json"
RUN_MARKER_PATH = OUTPUT_ROOT / "run-marker.json"
CONSOLE_PATH = OUTPUT_ROOT / "console.log"
BINDING_PATH = OUTPUT_ROOT / "binding.json"
RESULT_PATH = OUTPUT_ROOT / "result.json"
PARENT_RESULT_PATH = OUTPUT_ROOT / "parent-result.json"
TEST_LIST_PATH = product_ci.SWIFT_TEST_LIST_PATH

DISCOVERED_TEST_COUNT = 2_175
DISCOVERED_TEST_MANIFEST_SHA256 = (
    "a8121a99615da2b2b5b39535f5a8fb0ee03bf48fc2a4773d0aced5bac4a5041a"
)
HISTORICAL_DISCOVERED_TEST_COUNT = addon_v4.DISCOVERED_TEST_COUNT
HISTORICAL_DISCOVERED_TEST_MANIFEST_SHA256 = (
    addon_v4.DISCOVERED_TEST_MANIFEST_SHA256
)
CURRENT_ADDITION_IDENTITIES = (
    "CompanionCoreTests.SQLiteRuntimeChatEventStoreTests/"
    "testSQLiteAppendCacheFlushCheckpointCommitsExactlyOnce",
    "CompanionCoreTests.SQLiteRuntimeChatEventStoreTests/"
    "testSQLiteAppendCacheFlushCheckpointErrorRollsBackAndAllowsExactRetry",
)
CURRENT_ADDITION_TEST_COUNT = 2
CURRENT_ADDITION_TEST_MANIFEST_SHA256 = (
    "bf1fb5df5ca49bbd9ab133f6fe42b9c6f887b11dfc70b5d71bf25a3e0dcf4361"
)
CURRENT_V2_NEW_TEST_COUNT = 628
CURRENT_V2_NEW_TEST_MANIFEST_SHA256 = (
    "dd358dee2279821ed2ec2ec259b4bbd2061346b085d9694902b7857a17eb94fb"
)
V5_IDENTITY_RELATIVE_PATH = Path(
    "script/g7_reviewed_nonsecurity_swift_addon_identities_v5.txt"
)
V5_IDENTITY_PATH = ROOT / V5_IDENTITY_RELATIVE_PATH
V5_IDENTITY_BYTES = 2_887
V5_IDENTITY_RAW_SHA256 = (
    "295395947575e19481f62384137a6b1bda23e71d07708b62df67dc1afc8f9b2b"
)
V5_TEST_COUNT = 26
V5_TEST_MANIFEST_SHA256 = (
    "15970c0667b69b337d5fe13bfaffc36fd99e2b1fba52cb4cb99be230a7f04ede"
)
V6_IDENTITY_RELATIVE_PATH = Path(
    "script/g7_reviewed_nonsecurity_swift_addon_identities_v6.txt"
)
V6_IDENTITY_PATH = ROOT / V6_IDENTITY_RELATIVE_PATH
V6_IDENTITY_BYTES = 732
V6_IDENTITY_RAW_SHA256 = (
    "e64e65bbbcdb371b65cf8f290a606de55864c5a48988778a1a85954e05de837c"
)
V6_TEST_COUNT = 7
V6_TEST_MANIFEST_SHA256 = (
    "6b4991164cab03a5575a8c0d4a0526874571994e65e5bde612d8716333482a5d"
)
LOCAL_SOCKET_EXCLUSION_IDENTITIES = (
    "CompanionCoreTests.MacRuntimeConnectionManagerTests/"
    "testConcreteLocalListenerDefersAdvertisementAndRetriesAfterOccupiedPort",
    "TransportTests.LocalPeerServerTests/"
    "testLocalPeerServerOccupiedPortFailsThenSameInstanceRetries",
    "TransportTests.LocalPeerServerTests/"
    "testLocalPeerServerReportsListenerStartAndExplicitStop",
    "TransportTests.LocalPeerServerTests/"
    "testPeerAdmissionCannotCrossListenerStopGenerationBoundary",
)
LOCAL_SOCKET_EXCLUSION_TEST_COUNT = 4
LOCAL_SOCKET_EXCLUSION_TEST_MANIFEST_SHA256 = (
    "f83d04659cc16094468c8966185750a57bd3d702429116d8412b7ab99e4e47fc"
)
CURRENT_FOCUSED_TEST_COUNT = 218
CURRENT_FOCUSED_TEST_MANIFEST_SHA256 = (
    "a74d9e570a3e09e243f3f5ee239db4faa555e44cfd0c99790da71ea70b61285c"
)
SELECTED_TEST_COUNT = 1_204
SELECTED_TEST_MANIFEST_SHA256 = (
    "fbab18434f821237178e87aab1e84ce58bf7e82802978439ae43fc1f95e76fde"
)
NOT_EXECUTED_TEST_COUNT = 971
NOT_EXECUTED_TEST_MANIFEST_SHA256 = (
    "018058edbc3b344da6a7fae3a8b077d9aad6fc3c7fd2929a1130c2cee4152974"
)
FOCUSED_CARRIER_TEST_COUNT = 222
FOCUSED_CARRIER_TEST_MANIFEST_SHA256 = (
    "b481e814d8e0f7a2385e50fb5d0f0f8d1602f08b608eb373bb8960ce53547815"
)
PARENT_REVIEWED_TEST_COUNT = 1_208
PARENT_REVIEWED_TEST_MANIFEST_SHA256 = (
    "ea63ec325a6125f4ae92c49c0ca9d3054e054369335bec6ebeb99c7256468846"
)
PARENT_REMAINING_TEST_COUNT = 967
PARENT_REMAINING_TEST_MANIFEST_SHA256 = (
    "fe4c11470e53a92ff64fe31c143b7d587eacdfcdd68ac8af7c5ba7233d58e9e6"
)
BASE_DISTINCT_TEST_COUNT = 393
BASE_DISTINCT_TEST_MANIFEST_SHA256 = (
    "9d7784e88b7263ca0f3df34b93c59cdcfa0ed76bfe0ee8bc37edabd291966248"
)
FOCUSED_EXPANDED_OVERLAP_COUNT = (
    product_ci.G7_NONSECURITY_SWIFT_FOCUSED_OVERLAP_COUNT
)

RUN_TIMEOUT_SECONDS = 30 * 60
RESULT_MAX_BYTES = 2 * 1024 * 1024
EXECUTION_CONTRACT_MAX_BYTES = 160 * 1024
FILTER_MAX_BYTES = 64 * 1024
COMMAND_AND_ENVIRONMENT_MAX_BYTES = 96 * 1024
FAILURE_CONTEXT_MAX_CHARACTERS = 12_000
FAILURE_CONTEXT_MAX_LINES = 80

TRACKED_EXACT_SOURCE_RELATIVE_PATHS = (
    Path(".github/workflows/product-quality.yml"),
    Path("Package.swift"),
    Path("docs/evidence/g7-reviewed-nonsecurity-swift-addon-identities-v4-proposal.txt"),
    Path("script/check_g7_nonsecurity_merge_full_current.py"),
    Path("script/check_g7_nonsecurity_merge_full_candidate.py"),
    Path("script/check_g7_nonsecurity_merge_full_candidate_v2.py"),
    Path("script/check_g7_nonsecurity_merge_full_candidate_v3.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
    Path("script/check_product_ci.py"),
    Path("script/g7_nonsecurity_swift_successor_engine.py"),
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v2.txt"),
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v3.txt"),
    V5_IDENTITY_RELATIVE_PATH,
    V6_IDENTITY_RELATIVE_PATH,
    Path("script/run_g7_nonsecurity_merge_full_current.py"),
    Path("script/run_g7_nonsecurity_merge_full_candidate.py"),
    Path("script/test_check_g7_nonsecurity_merge_full_current.py"),
    Path("script/test_run_g7_nonsecurity_merge_full_current.py"),
)
EXACT_SOURCE_FILES = tuple(
    ROOT / relative
    for relative in TRACKED_EXACT_SOURCE_RELATIVE_PATHS
) + (EXECUTION_CONTRACT_PATH,)

LIMITATIONS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "deviceOrProductNetworkClaimed": False,
    "hostedCiExecutionClaimed": False,
    "localSocketExecutionClaimed": False,
    "securityAuthenticationOrCryptographyExecuted": False,
    "signedArtifactsClaimed": False,
    "v1Claimed": False,
}

PARENT_CONTRACT = "aetherlink-g7-nonsecurity-merge-full-current-parent-v1"
PARENT_LIMITATIONS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "deviceOrProductNetworkClaimed": False,
    "externalNetworkDeniedClaimed": False,
    "hostedCiExecutionClaimed": False,
    "localSocketExecutionClaimed": True,
    "securityAuthenticationOrCryptographyExecuted": False,
    "signedArtifactsClaimed": False,
    "v1Claimed": False,
}


@dataclass(frozen=True)
class CurrentRunPartition:
    discovered: tuple[str, ...]
    historical_discovered: tuple[str, ...]
    focused: tuple[str, ...]
    expanded: tuple[str, ...]
    base_distinct: tuple[str, ...]
    v2_new: tuple[str, ...]
    v2_current_new: tuple[str, ...]
    v3_new: tuple[str, ...]
    v4_new: tuple[str, ...]
    v5_new: tuple[str, ...]
    v6_new: tuple[str, ...]
    current_additions: tuple[str, ...]
    local_socket_excluded: tuple[str, ...]
    selected: tuple[str, ...]
    not_executed: tuple[str, ...]
    v2_partition: addon_v2.Partition
    v3_partition: addon_v3.Partition
    v4_partition: addon_v4.Partition


def canonical_json_bytes(value: object) -> bytes:
    return product_ci.canonical_json_bytes(value)


def manifest_sha256(identities: Iterable[str]) -> str:
    return product_ci.swift_test_selection_manifest_sha256(tuple(identities))


def exact_set_failures(
    label: str,
    identities: tuple[str, ...],
    expected_count: int,
    expected_manifest_sha256: str,
    *,
    require_sorted: bool = True,
) -> list[str]:
    failures: list[str] = []
    if len(identities) != expected_count:
        failures.append(
            f"{label} must contain {expected_count} identities, found "
            f"{len(identities)}"
        )
    if manifest_sha256(identities) != expected_manifest_sha256:
        failures.append(f"{label} manifest SHA-256 differs")
    if require_sorted and tuple(sorted(identities)) != identities:
        failures.append(f"{label} identities must be sorted")
    if len(set(identities)) != len(identities):
        failures.append(f"{label} identities must be unique")
    return failures


def load_exact_tests(
    *,
    label: str,
    relative_path: Path,
    expected_bytes: int,
    expected_raw_sha256: str,
    expected_count: int,
    expected_manifest_sha256: str,
) -> tuple[tuple[str, ...] | None, list[str]]:
    try:
        data, mode = addon_v4.candidate_base.read_stable_regular_file(
            ROOT,
            relative_path,
            maximum_bytes=RESULT_MAX_BYTES,
        )
    except (ValueError, addon_v4.candidate_base.CandidateError) as error:
        return None, [f"{label} identity manifest cannot be read: {error}"]
    failures: list[str] = []
    if mode != 0o644:
        failures.append(f"{label} identity manifest mode must be 0644")
    if len(data) != expected_bytes:
        failures.append(f"{label} identity manifest byte count differs")
    if hashlib.sha256(data).hexdigest() != expected_raw_sha256:
        failures.append(f"{label} identity manifest raw SHA-256 differs")
    if not data.endswith(b"\n") or b"\r" in data:
        failures.append(f"{label} identity manifest must use canonical LF lines")
    try:
        text = data.decode("ascii")
    except UnicodeError as error:
        return None, failures + [
            f"{label} identity manifest is not ASCII: {error}"
        ]
    identities = tuple(text.splitlines())
    if any(
        identity != identity.strip()
        or re.fullmatch(r"[^\s/]+/[^\s/]+", identity) is None
        for identity in identities
    ):
        failures.append(f"{label} identity manifest identities must be canonical")
    failures.extend(
        exact_set_failures(
            f"{label} reviewed Swift",
            identities,
            expected_count,
            expected_manifest_sha256,
        )
    )
    return (None if failures else identities), failures


def load_v5_tests() -> tuple[tuple[str, ...] | None, list[str]]:
    return load_exact_tests(
        label="V5",
        relative_path=V5_IDENTITY_RELATIVE_PATH,
        expected_bytes=V5_IDENTITY_BYTES,
        expected_raw_sha256=V5_IDENTITY_RAW_SHA256,
        expected_count=V5_TEST_COUNT,
        expected_manifest_sha256=V5_TEST_MANIFEST_SHA256,
    )


def load_v6_tests() -> tuple[tuple[str, ...] | None, list[str]]:
    return load_exact_tests(
        label="V6",
        relative_path=V6_IDENTITY_RELATIVE_PATH,
        expected_bytes=V6_IDENTITY_BYTES,
        expected_raw_sha256=V6_IDENTITY_RAW_SHA256,
        expected_count=V6_TEST_COUNT,
        expected_manifest_sha256=V6_TEST_MANIFEST_SHA256,
    )


def current_focused_filter() -> str:
    """Preserve the reviewed focused selector minus exact socket tests."""
    exclusion = "|".join(
        re.escape(identity) for identity in LOCAL_SOCKET_EXCLUSION_IDENTITIES
    )
    return (
        r"^(?!(?:"
        + exclusion
        + r")$).*?(?:"
        + product_ci.SWIFT_FILTER
        + ")"
    )


def reconstruct_partition() -> tuple[CurrentRunPartition | None, list[str]]:
    try:
        discovered, _test_list_bytes = independent_checker.read_test_list()
    except independent_checker.EvidenceError as error:
        return None, [f"current Swift discovery cannot be read: {error}"]
    failures: list[str] = []
    current_additions = tuple(sorted(CURRENT_ADDITION_IDENTITIES))
    if current_additions != CURRENT_ADDITION_IDENTITIES:
        failures.append("current Swift additions must be sorted")
    if not set(current_additions) <= set(discovered):
        failures.append("current Swift additions are missing from discovery")
    local_socket_excluded = tuple(sorted(LOCAL_SOCKET_EXCLUSION_IDENTITIES))
    if local_socket_excluded != LOCAL_SOCKET_EXCLUSION_IDENTITIES:
        failures.append("local-socket exclusions must be sorted")
    if not set(local_socket_excluded) <= set(discovered):
        failures.append("local-socket exclusions are missing from discovery")
    historical_discovered = tuple(
        identity for identity in discovered if identity not in set(current_additions)
    )
    failures.extend(
        exact_set_failures(
            "historical projected discovery Swift",
            tuple(sorted(historical_discovered)),
            HISTORICAL_DISCOVERED_TEST_COUNT,
            HISTORICAL_DISCOVERED_TEST_MANIFEST_SHA256,
        )
    )
    if failures:
        return None, failures
    v2_partition, v2_failures = addon_v2.partition_shape_failures(
        historical_discovered
    )
    failures.extend(v2_failures)
    if v2_partition is None:
        return None, failures
    v3_partition, v3_failures = addon_v3.partition_shape_failures(
        historical_discovered,
        v2_partition,
    )
    failures.extend(v3_failures)
    if v3_partition is None:
        return None, failures
    v4_partition, v4_failures = addon_v4.partition_shape_failures(
        historical_discovered,
        v3_partition,
    )
    failures.extend(v4_failures)
    if v4_partition is None:
        return None, failures
    v5_new, v5_failures = load_v5_tests()
    failures.extend(v5_failures)
    if v5_new is None:
        return None, failures
    v6_new, v6_failures = load_v6_tests()
    failures.extend(v6_failures)
    if v6_new is None:
        return None, failures

    historical_focused = tuple(
        sorted(
            identity
            for identity in discovered
            if re.search(product_ci.SWIFT_FILTER, identity)
        )
    )
    failures.extend(
        exact_set_failures(
            "reviewed focused Swift",
            historical_focused,
            product_ci.SWIFT_PRODUCT_TEST_COUNT,
            product_ci.SWIFT_PRODUCT_TEST_MANIFEST_SHA256,
        )
    )
    focused = tuple(
        sorted(
            identity
            for identity in discovered
            if re.search(current_focused_filter(), identity)
        )
    )
    if set(historical_focused) - set(focused) != set(local_socket_excluded):
        failures.append("focused Swift differs by more than exact socket exclusions")
    expanded = tuple(
        sorted(
            identity
            for identity in discovered
            if re.search(product_ci.G7_NONSECURITY_SWIFT_FILTER, identity)
            and identity not in product_ci.G7_NONSECURITY_SWIFT_LIVE_TESTS
        )
    )
    base_distinct = tuple(sorted(set(focused) | set(expanded)))
    v2_filter = addon_v2.runner_include_filter(v2_partition)
    v2_current_new = tuple(
        sorted(
            identity
            for identity in discovered
            if re.search(v2_filter, identity) and identity not in set(base_distinct)
        )
    )
    pre_v5_selected = tuple(
        sorted(
            set(base_distinct)
            | set(v2_partition.new)
            | set(v3_partition.selected)
            | set(v4_partition.selected)
            | set(current_additions)
        )
    )
    pre_v5_parent_remaining = (
        set(discovered) - set(pre_v5_selected) - set(local_socket_excluded)
    )
    if not set(v5_new) <= pre_v5_parent_remaining:
        failures.append("V5 reviewed Swift must be inside the prior parent remainder")
    pre_v6_selected = tuple(sorted(set(pre_v5_selected) | set(v5_new)))
    pre_v6_parent_remaining = (
        set(discovered) - set(pre_v6_selected) - set(local_socket_excluded)
    )
    if not set(v6_new) <= pre_v6_parent_remaining:
        failures.append("V6 reviewed Swift must be inside the prior parent remainder")
    selected = tuple(sorted(set(pre_v6_selected) | set(v6_new)))
    not_executed = tuple(sorted(set(discovered) - set(selected)))
    partition = CurrentRunPartition(
        discovered=tuple(discovered),
        historical_discovered=historical_discovered,
        focused=focused,
        expanded=expanded,
        base_distinct=base_distinct,
        v2_new=tuple(v2_partition.new),
        v2_current_new=v2_current_new,
        v3_new=tuple(v3_partition.selected),
        v4_new=tuple(v4_partition.selected),
        v5_new=v5_new,
        v6_new=v6_new,
        current_additions=current_additions,
        local_socket_excluded=local_socket_excluded,
        selected=selected,
        not_executed=not_executed,
        v2_partition=v2_partition,
        v3_partition=v3_partition,
        v4_partition=v4_partition,
    )
    exact_contracts = (
        (
            "discovered Swift",
            partition.discovered,
            DISCOVERED_TEST_COUNT,
            DISCOVERED_TEST_MANIFEST_SHA256,
            False,
        ),
        (
            "historical projected discovery Swift",
            tuple(sorted(partition.historical_discovered)),
            HISTORICAL_DISCOVERED_TEST_COUNT,
            HISTORICAL_DISCOVERED_TEST_MANIFEST_SHA256,
        ),
        (
            "focused Swift",
            partition.focused,
            CURRENT_FOCUSED_TEST_COUNT,
            CURRENT_FOCUSED_TEST_MANIFEST_SHA256,
        ),
        (
            "expanded Swift",
            partition.expanded,
            product_ci.G7_NONSECURITY_SWIFT_TEST_COUNT,
            product_ci.G7_NONSECURITY_SWIFT_TEST_MANIFEST_SHA256,
        ),
        (
            "base distinct Swift",
            partition.base_distinct,
            BASE_DISTINCT_TEST_COUNT,
            BASE_DISTINCT_TEST_MANIFEST_SHA256,
        ),
        (
            "historical V2 new Swift",
            partition.v2_new,
            addon_v2.NEW_TEST_COUNT,
            addon_v2.NEW_TEST_MANIFEST_SHA256,
        ),
        (
            "current V2 new Swift",
            partition.v2_current_new,
            CURRENT_V2_NEW_TEST_COUNT,
            CURRENT_V2_NEW_TEST_MANIFEST_SHA256,
        ),
        (
            "V3 new Swift",
            partition.v3_new,
            addon_v3.NEW_TEST_COUNT,
            addon_v3.NEW_TEST_MANIFEST_SHA256,
        ),
        (
            "V4 new Swift",
            partition.v4_new,
            addon_v4.NEW_TEST_COUNT,
            addon_v4.NEW_TEST_MANIFEST_SHA256,
        ),
        (
            "V5 new Swift",
            partition.v5_new,
            V5_TEST_COUNT,
            V5_TEST_MANIFEST_SHA256,
        ),
        (
            "V6 new Swift",
            partition.v6_new,
            V6_TEST_COUNT,
            V6_TEST_MANIFEST_SHA256,
        ),
        (
            "current additions Swift",
            partition.current_additions,
            CURRENT_ADDITION_TEST_COUNT,
            CURRENT_ADDITION_TEST_MANIFEST_SHA256,
        ),
        (
            "local-socket excluded Swift",
            partition.local_socket_excluded,
            LOCAL_SOCKET_EXCLUSION_TEST_COUNT,
            LOCAL_SOCKET_EXCLUSION_TEST_MANIFEST_SHA256,
        ),
        (
            "current-run selected Swift",
            partition.selected,
            SELECTED_TEST_COUNT,
            SELECTED_TEST_MANIFEST_SHA256,
        ),
        (
            "current-run not-executed Swift",
            partition.not_executed,
            NOT_EXECUTED_TEST_COUNT,
            NOT_EXECUTED_TEST_MANIFEST_SHA256,
        ),
    )
    for contract in exact_contracts:
        label, identities, count, digest, *options = contract
        failures.extend(
            exact_set_failures(
                label,
                identities,
                count,
                digest,
                require_sorted=options[0] if options else True,
            )
        )

    component_sets = (
        set(partition.base_distinct),
        set(partition.v2_new),
        set(partition.v3_new),
        set(partition.v4_new),
        set(partition.v5_new),
        set(partition.v6_new),
        set(partition.current_additions),
    )
    if any(
        left & right
        for index, left in enumerate(component_sets)
        for right in component_sets[index + 1 :]
    ):
        failures.append("current-run additive selection components overlap")
    if set().union(*component_sets) != set(partition.selected):
        failures.append("current-run selection component union differs")
    if set(partition.v2_current_new) != (
        set(partition.v2_new) | set(partition.current_additions)
    ):
        failures.append("current V2 selection is not historical V2 plus exact delta")
    if set(partition.local_socket_excluded) & set(partition.selected):
        failures.append("local-socket exclusions remain selected")
    if not set(partition.local_socket_excluded) <= set(partition.not_executed):
        failures.append("local-socket exclusions are absent from not-executed")
    if len(set(partition.focused) & set(partition.expanded)) != (
        FOCUSED_EXPANDED_OVERLAP_COUNT
    ):
        failures.append("focused/expanded overlap differs")
    if set(partition.selected) & set(partition.not_executed):
        failures.append("selected and not-executed Swift sets overlap")
    if set(partition.selected) | set(partition.not_executed) != set(
        partition.discovered
    ):
        failures.append("current-run Swift partition does not cover discovery")
    return (None if failures else partition), failures


def parent_partition(
    partition: CurrentRunPartition,
) -> tuple[dict[str, tuple[str, ...]] | None, list[str]]:
    focused_carrier = tuple(
        sorted(set(partition.focused) | set(partition.local_socket_excluded))
    )
    reviewed = tuple(
        sorted(set(partition.selected) | set(partition.local_socket_excluded))
    )
    remaining = tuple(sorted(set(partition.discovered) - set(reviewed)))
    values = {
        "discovered": tuple(sorted(partition.discovered)),
        "focusedCarrier": focused_carrier,
        "focusedCarrierOverlap": partition.focused,
        "localSocketExecuted": partition.local_socket_excluded,
        "noSocketExecuted": partition.selected,
        "remaining": remaining,
        "reviewedExecuted": reviewed,
    }
    failures: list[str] = []
    for label, identities, count, digest in (
        (
            "parent focused carrier Swift",
            focused_carrier,
            FOCUSED_CARRIER_TEST_COUNT,
            FOCUSED_CARRIER_TEST_MANIFEST_SHA256,
        ),
        (
            "parent reviewed Swift",
            reviewed,
            PARENT_REVIEWED_TEST_COUNT,
            PARENT_REVIEWED_TEST_MANIFEST_SHA256,
        ),
        (
            "parent remaining Swift",
            remaining,
            PARENT_REMAINING_TEST_COUNT,
            PARENT_REMAINING_TEST_MANIFEST_SHA256,
        ),
    ):
        failures.extend(exact_set_failures(label, identities, count, digest))
    if set(partition.selected) & set(partition.local_socket_excluded):
        failures.append("parent local-socket contribution overlaps no-socket child")
    if set(reviewed) & set(remaining):
        failures.append("parent reviewed and remaining sets overlap")
    if set(reviewed) | set(remaining) != set(partition.discovered):
        failures.append("parent Swift partition does not cover discovery")
    return (None if failures else values), failures


def filter_components(
    partition: CurrentRunPartition,
) -> tuple[tuple[str, str], ...]:
    return (
        ("focused", current_focused_filter()),
        ("expandedSafe", product_ci.G7_NONSECURITY_SWIFT_SAFE_MODULE_FILTER),
        ("expandedUi", product_ci.G7_NONSECURITY_SWIFT_UI_FILTER),
        ("v2Reviewed", addon_v2.runner_include_filter(partition.v2_partition)),
        ("v3Exact", addon_v3.exact_filter(partition.v3_new)),
        ("v4Exact", addon_v4.exact_filter(partition.v4_new)),
        ("v5Exact", addon_v4.exact_filter(partition.v5_new)),
        ("v6Exact", addon_v4.exact_filter(partition.v6_new)),
        ("currentV2DeltaExact", addon_v4.exact_filter(partition.current_additions)),
    )


def combined_filter(partition: CurrentRunPartition) -> str:
    return "(?:" + "|".join(
        pattern for _name, pattern in filter_components(partition)
    ) + ")"


def command_and_filter_failures(
    partition: CurrentRunPartition,
) -> tuple[tuple[str, ...] | None, list[str]]:
    failures: list[str] = []
    filter_pattern = combined_filter(partition)
    if len(filter_pattern.encode("utf-8")) > FILTER_MAX_BYTES:
        failures.append("current-run Swift filter exceeds its byte bound")
    try:
        selected_by_filter = tuple(
            sorted(
                identity
                for identity in partition.discovered
                if re.search(filter_pattern, identity)
            )
        )
    except re.error as error:
        failures.append(f"current-run Swift filter is invalid: {error}")
        selected_by_filter = ()
    if selected_by_filter != partition.selected:
        failures.append("current-run Swift filter differs from the exact reviewed union")
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
    if "--skip" in command:
        failures.append("current-run Swift command must not use a skip filter")
    return (None if failures else command), failures


def command_environment_footprint(
    command: tuple[str, ...],
    environment: dict[str, str],
) -> int:
    return sum(len(os.fsencode(value)) + 1 for value in command) + sum(
        len(os.fsencode(key)) + len(os.fsencode(value)) + 2
        for key, value in environment.items()
    )


def command_environment(
    partition: CurrentRunPartition,
    *,
    run_network_probe: bool,
) -> tuple[tuple[str, ...] | None, dict[str, str] | None, list[str]]:
    command, failures = command_and_filter_failures(partition)
    environment, environment_failures = product_ci.g7_nonsecurity_swift_environment()
    failures.extend(environment_failures)
    if run_network_probe:
        failures.extend(product_ci.g7_nonsecurity_swift_network_sandbox_self_test())
    if command is not None:
        for executable in (Path(command[0]), Path(command[3])):
            try:
                value = executable.lstat()
            except OSError as error:
                failures.append(
                    f"current-run Swift executable cannot be inspected: "
                    f"{executable}: {error}"
                )
                continue
            if (
                stat.S_ISLNK(value.st_mode)
                or not stat.S_ISREG(value.st_mode)
                or not os.access(executable, os.X_OK)
            ):
                failures.append(
                    f"current-run Swift executable must be physical: {executable}"
                )
    if command is not None and environment is not None:
        if command_environment_footprint(command, environment) > (
            COMMAND_AND_ENVIRONMENT_MAX_BYTES
        ):
            failures.append("current-run Swift argv/environment exceeds its bound")
    if failures:
        return None, None, failures
    return command, environment, []


def swift_failure_context(log_path: Path) -> str | None:
    data, failures = product_ci.read_bounded_regular_bytes(
        log_path,
        max_bytes=product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
        label="G7 current-run failure console",
    )
    if data is None:
        return (
            "G7 current-run failure console could not be read: "
            + "; ".join(failures)
        )
    lines = data.decode("utf-8", errors="replace").splitlines()
    interesting_pattern = re.compile(
        r"(?i)(?:\bfailed\b|\berror:|\bfatal\b|xctassert|unexpected)"
    )
    selected_indexes = {
        index
        for index, line in enumerate(lines)
        if interesting_pattern.search(line)
    }
    selected_indexes.update(range(max(0, len(lines) - 20), len(lines)))
    selected_lines = [
        lines[index][:1_000]
        for index in sorted(selected_indexes)[-FAILURE_CONTEXT_MAX_LINES:]
    ]
    if not selected_lines:
        return None
    context = "\n".join(selected_lines)
    if len(context) > FAILURE_CONTEXT_MAX_CHARACTERS:
        context = context[-FAILURE_CONTEXT_MAX_CHARACTERS:]
    return "G7 current-run bounded failure context:\n" + context


def partition_record(identities: tuple[str, ...]) -> dict[str, object]:
    return {
        "manifestSha256": manifest_sha256(identities),
        "tests": len(identities),
    }


def execution_contract_payload(
    partition: CurrentRunPartition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> dict[str, object]:
    return {
        "command": list(command),
        "commandAndEnvironmentBytes": command_environment_footprint(
            command,
            environment,
        ),
        "commandAndEnvironmentMaximumBytes": (
            COMMAND_AND_ENVIRONMENT_MAX_BYTES
        ),
        "contract": EXECUTION_CONTRACT,
        "environment": environment,
        "filterComponents": [
            {"name": name, "pattern": pattern}
            for name, pattern in filter_components(partition)
        ],
        "networkDenyProbePassed": True,
        "networkDenyProfile": product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
        "schemaVersion": SCHEMA_VERSION,
        "selection": {
            "baseDistinct": partition_record(partition.base_distinct),
            "discovered": partition_record(partition.discovered),
            "expanded": partition_record(partition.expanded),
            "focused": partition_record(partition.focused),
            "focusedExpandedOverlap": FOCUSED_EXPANDED_OVERLAP_COUNT,
            "historicalDiscovery": partition_record(
                tuple(sorted(partition.historical_discovered))
            ),
            "localSocketExcluded": partition_record(
                partition.local_socket_excluded
            ),
            "notExecuted": partition_record(partition.not_executed),
            "selected": partition_record(partition.selected),
            "currentV2Delta": partition_record(partition.current_additions),
            "v2CurrentNew": partition_record(partition.v2_current_new),
            "v2HistoricalNew": partition_record(partition.v2_new),
            "v3New": partition_record(partition.v3_new),
            "v4New": partition_record(partition.v4_new),
            "v5New": partition_record(partition.v5_new),
            "v6New": partition_record(partition.v6_new),
        },
        "singleSwiftInvocation": True,
    }


def read_canonical_json(
    path: Path,
    *,
    maximum_bytes: int,
) -> tuple[dict[str, object] | None, bytes | None, list[str]]:
    try:
        value = path.lstat()
        data = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        return None, None, [f"{path.relative_to(ROOT)} cannot be read: {error}"]
    failures: list[str] = []
    if not stat.S_ISREG(value.st_mode) or stat.S_ISLNK(value.st_mode):
        failures.append(f"{path.relative_to(ROOT)} must be a physical file")
    if value.st_nlink != 1:
        failures.append(f"{path.relative_to(ROOT)} must have one link")
    if len(data) > maximum_bytes:
        failures.append(f"{path.relative_to(ROOT)} exceeds its byte bound")
    if (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        failures.append(f"{path.relative_to(ROOT)} changed during read")
    try:
        document = json.loads(
            data,
            object_pairs_hook=addon_v4.candidate_base.reject_duplicate_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        addon_v4.candidate_base.DuplicateKeyError,
    ) as error:
        return None, data, failures + [
            f"{path.relative_to(ROOT)} is invalid JSON: {error}"
        ]
    if type(document) is not dict or canonical_json_bytes(document) != data:
        failures.append(f"{path.relative_to(ROOT)} must be canonical JSON")
    return (document if type(document) is dict else None), data, failures


def execution_contract_failures(
    partition: CurrentRunPartition,
    *,
    expected_environment: dict[str, str] | None = None,
) -> list[str]:
    command, command_failures = command_and_filter_failures(partition)
    if command is None:
        return command_failures
    document, _data, failures = read_canonical_json(
        EXECUTION_CONTRACT_PATH,
        maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
    )
    failures.extend(command_failures)
    if document is None:
        return failures
    environment = document.get("environment")
    if type(environment) is not dict or any(
        type(key) is not str or type(value) is not str
        for key, value in (
            environment.items() if type(environment) is dict else ()
        )
    ):
        failures.append("execution contract environment must be string mapping")
        return failures
    normalized, environment_failures = (
        product_ci.g7_nonsecurity_swift_environment(environment)
    )
    failures.extend(environment_failures)
    if normalized != environment:
        failures.append("execution contract environment is not the exact allowlist")
    if expected_environment is not None and environment != expected_environment:
        failures.append("execution contract environment differs from this run")
    if document != execution_contract_payload(partition, command, environment):
        failures.append("execution contract payload differs")
    return failures


def source_snapshot_parity_failures() -> list[str]:
    if TRACKED_EXACT_SOURCE_RELATIVE_PATHS != (
        independent_checker.TRACKED_EXACT_SOURCE_RELATIVE_PATHS
    ):
        return ["producer/checker exact source path contracts differ"]
    marker, _data, failures = read_canonical_json(
        RUN_MARKER_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if marker is None:
        return failures
    recorded_source = marker.get("sourceInputs")
    try:
        independent_source = independent_checker.source_snapshot(root=ROOT)
    except independent_checker.EvidenceError as error:
        failures.append(f"independent source snapshot failed: {error}")
        return failures
    if recorded_source != independent_source:
        failures.append(
            "producer source snapshot differs from the bounded independent snapshot"
        )
    return failures


def ensure_output_directory(*, create: bool) -> list[str]:
    try:
        value = OUTPUT_ROOT.lstat()
    except FileNotFoundError:
        if not create:
            return ["current-run output directory is missing"]
        try:
            OUTPUT_ROOT.mkdir(mode=0o700)
            value = OUTPUT_ROOT.lstat()
        except OSError as error:
            return [f"current-run output directory cannot be created: {error}"]
    except OSError as error:
        return [f"current-run output directory cannot be inspected: {error}"]
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
        return ["current-run output directory must be physical"]
    if stat.S_IMODE(value.st_mode) != 0o700:
        return ["current-run output directory mode must be 0700"]
    return []


def common_arguments(partition: CurrentRunPartition) -> dict[str, object]:
    return {
        "binding_path": BINDING_PATH,
        "marker_path": RUN_MARKER_PATH,
        "log_path": CONSOLE_PATH,
        "test_list_path": TEST_LIST_PATH,
        "filter_pattern": combined_filter(partition),
        "expected_count": SELECTED_TEST_COUNT,
        "expected_manifest_sha256": SELECTED_TEST_MANIFEST_SHA256,
        "excluded_tests": (),
        "exact_files": EXACT_SOURCE_FILES,
    }


def prepare(partition: CurrentRunPartition) -> list[str]:
    failures = ensure_output_directory(create=True)
    command, environment, contract_failures = command_environment(
        partition,
        run_network_probe=True,
    )
    failures.extend(contract_failures)
    if command is None or environment is None or failures:
        return failures
    failures.extend(
        product_ci.write_canonical_json_payload(
            EXECUTION_CONTRACT_PATH,
            execution_contract_payload(partition, command, environment),
            label="G7 current-run execution contract",
        )
    )
    if not failures:
        failures.extend(
            execution_contract_failures(
                partition,
                expected_environment=environment,
            )
        )
    if not failures:
        marker_arguments = dict(common_arguments(partition))
        marker_arguments.pop("binding_path")
        marker_arguments.pop("log_path")
        failures.extend(
            product_ci.write_swift_focused_test_run_marker(**marker_arguments)
        )
    if not failures:
        failures.extend(source_snapshot_parity_failures())
    return failures


def run(partition: CurrentRunPartition) -> tuple[int, list[str]]:
    failures = ensure_output_directory(create=False)
    command, environment, contract_failures = command_environment(
        partition,
        run_network_probe=True,
    )
    failures.extend(contract_failures)
    if command is None or environment is None:
        return 1, failures
    failures.extend(
        execution_contract_failures(
            partition,
            expected_environment=environment,
        )
    )
    arguments = common_arguments(partition)
    marker_arguments = {
        key: value
        for key, value in arguments.items()
        if key not in ("binding_path",)
    }
    marker_arguments["require_log"] = False
    failures.extend(
        product_ci.swift_focused_test_run_marker_failures(**marker_arguments)
    )
    failures.extend(source_snapshot_parity_failures())
    if failures:
        return 1, failures
    _, expected_tests, selection_failures = (
        product_ci.swift_focused_test_list_snapshot(
            test_list_path=TEST_LIST_PATH,
            filter_pattern=combined_filter(partition),
            expected_count=SELECTED_TEST_COUNT,
            expected_manifest_sha256=SELECTED_TEST_MANIFEST_SHA256,
            excluded_tests=(),
        )
    )
    failures.extend(selection_failures)
    if expected_tests is None or failures:
        return 1, failures

    def validate_log_context(candidate_log_path: Path) -> list[str]:
        return product_ci.swift_focused_test_run_marker_failures(
            marker_path=RUN_MARKER_PATH,
            log_path=candidate_log_path,
            test_list_path=TEST_LIST_PATH,
            filter_pattern=combined_filter(partition),
            expected_count=SELECTED_TEST_COUNT,
            expected_manifest_sha256=SELECTED_TEST_MANIFEST_SHA256,
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
        failure_context=swift_failure_context,
    )


def file_record(path: Path, *, maximum_bytes: int) -> dict[str, object]:
    try:
        value = path.lstat()
        data = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise RuntimeError(f"{path.relative_to(ROOT)} cannot be read: {error}") from error
    if (
        stat.S_ISLNK(value.st_mode)
        or not stat.S_ISREG(value.st_mode)
        or value.st_nlink != 1
        or len(data) > maximum_bytes
        or (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise RuntimeError(f"{path.relative_to(ROOT)} is not a stable single-link file")
    return {
        "bytes": len(data),
        "mode": stat.S_IMODE(value.st_mode),
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def compose_result_payload(
    partition: CurrentRunPartition,
    *,
    artifacts: dict[str, object],
    source_inputs: object,
    execution_document: dict[str, object],
) -> dict[str, object]:
    return {
        "artifacts": artifacts,
        "contract": CONTRACT,
        "coverage": {
            "baseDistinct": partition_record(partition.base_distinct),
            "currentV2Delta": partition_record(partition.current_additions),
            "discovered": partition_record(partition.discovered),
            "expanded": partition_record(partition.expanded),
            "focused": partition_record(partition.focused),
            "focusedExpandedOverlap": FOCUSED_EXPANDED_OVERLAP_COUNT,
            "historicalDiscovery": partition_record(
                tuple(sorted(partition.historical_discovered))
            ),
            "localSocketExcluded": partition_record(
                partition.local_socket_excluded
            ),
            "notExecuted": partition_record(partition.not_executed),
            "selected": partition_record(partition.selected),
            "v2CurrentNew": partition_record(partition.v2_current_new),
            "v2HistoricalNew": partition_record(partition.v2_new),
            "v3New": partition_record(partition.v3_new),
            "v4New": partition_record(partition.v4_new),
            "v5New": partition_record(partition.v5_new),
            "v6New": partition_record(partition.v6_new),
        },
        "execution": {
            "commandAndEnvironmentBytes": execution_document.get(
                "commandAndEnvironmentBytes"
            ),
            "filterBytes": len(combined_filter(partition).encode("utf-8")),
            "networkDenyProfile": product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
            "singleSwiftInvocation": True,
        },
        "limitations": LIMITATIONS,
        "result": "passed",
        "schemaVersion": SCHEMA_VERSION,
        "sourceInputs": source_inputs,
    }


def result_payload(
    partition: CurrentRunPartition,
) -> tuple[dict[str, object] | None, list[str]]:
    binding, _binding_bytes, failures = read_canonical_json(
        BINDING_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if binding is None:
        return None, failures
    source_inputs = binding.get("sourceInputs")
    if (
        type(source_inputs) is not dict
        or set(source_inputs) != {"count", "sha256"}
        or type(source_inputs.get("count")) is not int
        or type(source_inputs.get("sha256")) is not str
    ):
        return None, failures + ["binding sourceInputs shape differs"]
    try:
        artifacts = {
            "binding": file_record(BINDING_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "console": file_record(
                CONSOLE_PATH,
                maximum_bytes=product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
            ),
            "executionContract": file_record(
                EXECUTION_CONTRACT_PATH,
                maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
            ),
            "runMarker": file_record(RUN_MARKER_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "testList": file_record(TEST_LIST_PATH, maximum_bytes=RESULT_MAX_BYTES),
        }
    except RuntimeError as error:
        return None, failures + [str(error)]
    command, command_failures = command_and_filter_failures(partition)
    failures.extend(command_failures)
    if command is None:
        return None, failures
    execution_document, _data, execution_failures = read_canonical_json(
        EXECUTION_CONTRACT_PATH,
        maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
    )
    failures.extend(execution_failures)
    if execution_document is None:
        return None, failures
    return (
        compose_result_payload(
            partition,
            artifacts=artifacts,
            source_inputs=source_inputs,
            execution_document=execution_document,
        ),
        failures,
    )


def result_failures(partition: CurrentRunPartition) -> list[str]:
    failures = ensure_output_directory(create=False)
    failures.extend(execution_contract_failures(partition))
    failures.extend(source_snapshot_parity_failures())
    failures.extend(
        product_ci.swift_focused_test_binding_failures(
            **common_arguments(partition)
        )
    )
    expected, payload_failures = result_payload(partition)
    failures.extend(payload_failures)
    if expected is None:
        return failures
    observed, data, result_read_failures = read_canonical_json(
        RESULT_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    failures.extend(result_read_failures)
    if observed is not None and data != canonical_json_bytes(expected):
        failures.append("current-run result does not exactly bind current evidence")
    try:
        result_mode = stat.S_IMODE(RESULT_PATH.lstat().st_mode)
    except OSError:
        result_mode = -1
    if result_mode != 0o600:
        failures.append("current-run result mode must be 0600")
    return failures


def compose_parent_payload(
    partition: CurrentRunPartition,
    *,
    artifacts: dict[str, object],
    focused_source_inputs: object,
    no_socket_source_inputs: object,
) -> tuple[dict[str, object] | None, list[str]]:
    parent, failures = parent_partition(partition)
    if parent is None:
        return None, failures
    return (
        {
            "artifacts": artifacts,
            "contract": PARENT_CONTRACT,
            "coverage": {
                key: partition_record(value)
                for key, value in parent.items()
            },
            "execution": {
                "childSwiftInvocations": 2,
                "focusedCarrierExternalNetworkDenied": False,
                "focusedCarrierTests": FOCUSED_CARRIER_TEST_COUNT,
                "noSocketNetworkDenyProfile": (
                    product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE
                ),
                "sharedTestListBytes": True,
            },
            "limitations": PARENT_LIMITATIONS,
            "result": "passed",
            "schemaVersion": SCHEMA_VERSION,
            "sourceInputs": {
                "focusedCarrier": focused_source_inputs,
                "noSocket": no_socket_source_inputs,
            },
        },
        failures,
    )


def parent_payload(
    partition: CurrentRunPartition,
) -> tuple[dict[str, object] | None, list[str]]:
    failures = result_failures(partition)
    failures.extend(product_ci.swift_focused_test_binding_failures())
    if (
        product_ci.SWIFT_PRODUCT_TEST_COUNT != FOCUSED_CARRIER_TEST_COUNT
        or product_ci.SWIFT_PRODUCT_TEST_MANIFEST_SHA256
        != FOCUSED_CARRIER_TEST_MANIFEST_SHA256
    ):
        failures.append("focused carrier contract differs from Product CI")
    if (
        PARENT_CONTRACT != independent_checker.PARENT_CONTRACT
        or PARENT_LIMITATIONS != independent_checker.PARENT_LIMITATIONS
    ):
        failures.append("producer/checker parent contract differs")

    focused_binding, _focused_bytes, focused_failures = read_canonical_json(
        product_ci.SWIFT_FOCUSED_TEST_BINDING_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    current_result, _current_bytes, current_failures = read_canonical_json(
        RESULT_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    failures.extend(focused_failures)
    failures.extend(current_failures)
    if focused_binding is None or current_result is None:
        return None, failures

    focused_source_inputs = focused_binding.get("sourceInputs")
    no_socket_source_inputs = current_result.get("sourceInputs")
    focused_test_list = focused_binding.get("testList")
    current_artifacts = current_result.get("artifacts")
    current_test_list = (
        current_artifacts.get("testList")
        if type(current_artifacts) is dict
        else None
    )
    if (
        type(focused_source_inputs) is not dict
        or type(no_socket_source_inputs) is not dict
        or type(focused_test_list) is not dict
        or type(current_test_list) is not dict
    ):
        return None, failures + ["parent child binding shape differs"]

    try:
        artifacts = {
            "currentResult": file_record(
                RESULT_PATH,
                maximum_bytes=RESULT_MAX_BYTES,
            ),
            "focusedBinding": file_record(
                product_ci.SWIFT_FOCUSED_TEST_BINDING_PATH,
                maximum_bytes=RESULT_MAX_BYTES,
            ),
            "focusedConsole": file_record(
                product_ci.SWIFT_FOCUSED_TEST_LOG_PATH,
                maximum_bytes=product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
            ),
            "focusedRunMarker": file_record(
                product_ci.SWIFT_FOCUSED_TEST_RUN_MARKER_PATH,
                maximum_bytes=RESULT_MAX_BYTES,
            ),
            "testList": file_record(
                TEST_LIST_PATH,
                maximum_bytes=RESULT_MAX_BYTES,
            ),
        }
    except RuntimeError as error:
        return None, failures + [str(error)]
    shared_test_list = artifacts["testList"]
    if type(shared_test_list) is not dict:
        return None, failures + ["shared test-list artifact shape differs"]
    for key in ("bytes", "sha256"):
        if (
            focused_test_list.get(key) != shared_test_list.get(key)
            or current_test_list.get(key) != shared_test_list.get(key)
        ):
            failures.append("parent children do not share exact test-list bytes")

    payload, compose_failures = compose_parent_payload(
        partition,
        artifacts=artifacts,
        focused_source_inputs=focused_source_inputs,
        no_socket_source_inputs=no_socket_source_inputs,
    )
    failures.extend(compose_failures)
    return payload, failures


def parent_result_failures(partition: CurrentRunPartition) -> list[str]:
    expected, failures = parent_payload(partition)
    if expected is None:
        return failures
    observed, data, read_failures = read_canonical_json(
        PARENT_RESULT_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    failures.extend(read_failures)
    if observed is not None and data != canonical_json_bytes(expected):
        failures.append("current parent does not exactly bind both child results")
    try:
        parent_stat = PARENT_RESULT_PATH.lstat()
        current_stat = RESULT_PATH.lstat()
        focused_stat = product_ci.SWIFT_FOCUSED_TEST_BINDING_PATH.lstat()
    except OSError as error:
        failures.append(f"current parent chronology cannot be read: {error}")
        return failures
    if stat.S_IMODE(parent_stat.st_mode) != 0o600:
        failures.append("current parent result mode must be 0600")
    if parent_stat.st_mtime_ns <= max(
        current_stat.st_mtime_ns,
        focused_stat.st_mtime_ns,
    ):
        failures.append("current parent must postdate both child results")
    if parent_stat.st_mtime_ns > time.time_ns() + 5_000_000_000:
        failures.append("current parent timestamp is implausibly in the future")
    return failures


def write_parent_result(partition: CurrentRunPartition) -> list[str]:
    payload, failures = parent_payload(partition)
    if payload is not None and not failures:
        failures.extend(
            product_ci.write_canonical_json_payload(
                PARENT_RESULT_PATH,
                payload,
                label="G7 current two-child parent result",
            )
        )
    if not failures:
        failures.extend(parent_result_failures(partition))
    return failures


def write_binding_and_result(partition: CurrentRunPartition) -> list[str]:
    failures = ensure_output_directory(create=False)
    failures.extend(execution_contract_failures(partition))
    failures.extend(source_snapshot_parity_failures())
    if not failures:
        failures.extend(
            product_ci.write_swift_focused_test_binding(
                **common_arguments(partition)
            )
        )
    payload, payload_failures = result_payload(partition)
    failures.extend(payload_failures)
    if payload is not None and not failures:
        failures.extend(
            product_ci.write_canonical_json_payload(
                RESULT_PATH,
                payload,
                label="G7 current-run aggregate result",
            )
        )
    if not failures:
        failures.extend(result_failures(partition))
    return failures


def print_failures(prefix: str, failures: list[str]) -> int:
    for failure in failures:
        print(f"{prefix}: {failure}", file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--write-binding", action="store_true")
    mode.add_argument("--results", action="store_true")
    mode.add_argument("--write-parent", action="store_true")
    mode.add_argument("--parent-results", action="store_true")
    arguments = parser.parse_args(argv)

    partition, failures = reconstruct_partition()
    if partition is None:
        return print_failures("G7 current-run preflight failed", failures)
    if arguments.self_test:
        command, environment, contract_failures = command_environment(
            partition,
            run_network_probe=True,
        )
        failures.extend(contract_failures)
        if command is None or environment is None or failures:
            return print_failures("G7 current-run self-test failed", failures)
        print(
            "G7 current-run contract self-test passed: "
            f"{SELECTED_TEST_COUNT}/{DISCOVERED_TEST_COUNT} selected."
        )
        return 0
    if arguments.prepare:
        failures = prepare(partition)
        if failures:
            return print_failures("G7 current-run preparation failed", failures)
        print(
            "G7 current-run source marker passed: "
            f"{SELECTED_TEST_COUNT} selected, {NOT_EXECUTED_TEST_COUNT} excluded."
        )
        return 0
    if arguments.run:
        status, failures = run(partition)
        if status != 0 or failures:
            return print_failures("G7 current-run execution failed", failures)
        print(
            "G7 current-run Swift execution passed: "
            f"{SELECTED_TEST_COUNT}/{SELECTED_TEST_COUNT}; skipped=0; "
            "failures=0; network denied."
        )
        return 0
    if arguments.write_binding:
        failures = write_binding_and_result(partition)
        if failures:
            return print_failures("G7 current-run binding failed", failures)
        print(
            "G7 current-run result bound: "
            f"{SELECTED_TEST_COUNT}/{DISCOVERED_TEST_COUNT} current-source tests."
        )
        return 0
    if arguments.write_parent:
        failures = write_parent_result(partition)
        if failures:
            return print_failures("G7 current parent binding failed", failures)
        print(
            "G7 current parent result bound: "
            f"{PARENT_REVIEWED_TEST_COUNT}/{DISCOVERED_TEST_COUNT} reviewed "
            "current-source tests."
        )
        return 0
    if arguments.parent_results:
        failures = parent_result_failures(partition)
        if failures:
            return print_failures("G7 current parent readback failed", failures)
        print(
            "G7 current parent producer readback passed: "
            f"{PARENT_REVIEWED_TEST_COUNT}/{PARENT_REVIEWED_TEST_COUNT}; "
            "canonical G7 remains open."
        )
        return 0
    failures = result_failures(partition)
    if failures:
        return print_failures("G7 current-run readback failed", failures)
    print(
        "G7 current-run producer readback passed: "
        f"{SELECTED_TEST_COUNT}/{SELECTED_TEST_COUNT}; canonical G7 remains open."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
