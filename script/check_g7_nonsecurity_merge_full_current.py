#!/usr/bin/env python3
"""Independently read back the current-checkout G7 non-security Swift run.

This verifier intentionally imports no project module.  It reconstructs the
selected XCTest set from the recorded command and current test-list bytes,
recomputes the source snapshot, and validates every marker, console, binding,
and result byte.  Passing this bounded contract does not complete canonical G7.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-current-run-v1"
EXECUTION_CONTRACT = (
    "aetherlink-g7-nonsecurity-merge-full-current-run-execution-v1"
)
RUN_MARKER_CONTRACT = "swift-focused-xctest-run-source-v1"
BINDING_CONTRACT = "swift-focused-xctest-console-binding-v1"

OUTPUT_ROOT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1"
)
EXECUTION_CONTRACT_RELATIVE_PATH = OUTPUT_ROOT_RELATIVE_PATH / (
    "execution-contract.json"
)
RUN_MARKER_RELATIVE_PATH = OUTPUT_ROOT_RELATIVE_PATH / "run-marker.json"
CONSOLE_RELATIVE_PATH = OUTPUT_ROOT_RELATIVE_PATH / "console.log"
BINDING_RELATIVE_PATH = OUTPUT_ROOT_RELATIVE_PATH / "binding.json"
RESULT_RELATIVE_PATH = OUTPUT_ROOT_RELATIVE_PATH / "result.json"
PARENT_RESULT_RELATIVE_PATH = OUTPUT_ROOT_RELATIVE_PATH / "parent-result.json"
TEST_LIST_RELATIVE_PATH = Path(
    ".build/aetherlink-product-ci-swift-test-list-v1.txt"
)
FOCUSED_RUN_MARKER_RELATIVE_PATH = Path(
    ".build/aetherlink-product-ci-swift-focused-run-marker-v1.json"
)
FOCUSED_CONSOLE_RELATIVE_PATH = Path(
    ".build/aetherlink-product-ci-swift-focused-console-v1.log"
)
FOCUSED_BINDING_RELATIVE_PATH = Path(
    ".build/aetherlink-product-ci-swift-focused-binding-v1.json"
)

RESULT_MAX_BYTES = 2 * 1024 * 1024
EXECUTION_CONTRACT_MAX_BYTES = 160 * 1024
TEST_LIST_MAX_BYTES = 2 * 1024 * 1024
CONSOLE_MAX_BYTES = 16 * 1024 * 1024
SOURCE_FILE_MAX_BYTES = 32 * 1024 * 1024
SOURCE_TOTAL_MAX_BYTES = 256 * 1024 * 1024
FILTER_MAX_BYTES = 64 * 1024
COMMAND_AND_ENVIRONMENT_MAX_BYTES = 96 * 1024
FUTURE_MTIME_TOLERANCE_NS = 5_000_000_000

TEST_LIST_BYTES = 245_185
TEST_LIST_SHA256 = (
    "9daeeca4667c16aa825ba50c17f33c8297511ed9ab3f48c253f389c6f7742b60"
)
DISCOVERED_TEST_COUNT = 2_175
DISCOVERED_TEST_MANIFEST_SHA256 = (
    "a8121a99615da2b2b5b39535f5a8fb0ee03bf48fc2a4773d0aced5bac4a5041a"
)
SELECTED_TEST_COUNT = 1_205
SELECTED_TEST_MANIFEST_SHA256 = (
    "33cf8415b21aa5bf727ac05cdaac6752c8929565fa934e2666128b35330bbd5b"
)
NOT_EXECUTED_TEST_COUNT = 970
NOT_EXECUTED_TEST_MANIFEST_SHA256 = (
    "f335a5eb4c097b59017994bce65520fc1a432fc30e1e7f8ea00baec9065aef10"
)
CURRENT_V2_DELTA_IDENTITIES = (
    "CompanionCoreTests.SQLiteRuntimeChatEventStoreTests/"
    "testSQLiteAppendCacheFlushCheckpointCommitsExactlyOnce",
    "CompanionCoreTests.SQLiteRuntimeChatEventStoreTests/"
    "testSQLiteAppendCacheFlushCheckpointErrorRollsBackAndAllowsExactRetry",
)
V5_IDENTITY_RELATIVE_PATH = Path(
    "script/g7_reviewed_nonsecurity_swift_addon_identities_v5.txt"
)
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
V6_IDENTITY_BYTES = 732
V6_IDENTITY_RAW_SHA256 = (
    "e64e65bbbcdb371b65cf8f290a606de55864c5a48988778a1a85954e05de837c"
)
V6_TEST_COUNT = 7
V6_TEST_MANIFEST_SHA256 = (
    "6b4991164cab03a5575a8c0d4a0526874571994e65e5bde612d8716333482a5d"
)
V7_IDENTITY_RELATIVE_PATH = Path(
    "script/g7_reviewed_nonsecurity_swift_addon_identities_v7.txt"
)
V7_IDENTITY_BYTES = 124
V7_IDENTITY_RAW_SHA256 = (
    "6894d0e26b04a0054f38b733dc553758e9e5b99b9f7b8df85098b6f08cbe4792"
)
V7_TEST_COUNT = 1
V7_TEST_MANIFEST_SHA256 = (
    "2f726fc2fd89ab9a4c7ec464dd94a3aeac0ee9e41811710ddf24baf5bc4ae9aa"
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
FOCUSED_CARRIER_TEST_COUNT = 222
FOCUSED_CARRIER_TEST_MANIFEST_SHA256 = (
    "b481e814d8e0f7a2385e50fb5d0f0f8d1602f08b608eb373bb8960ce53547815"
)
PARENT_REVIEWED_TEST_COUNT = 1_209
PARENT_REVIEWED_TEST_MANIFEST_SHA256 = (
    "26e97b0bf2349883b71677dfb614d15f8a2e920d3fc42036b6e1a08add7cf6a2"
)
PARENT_REMAINING_TEST_COUNT = 966
PARENT_REMAINING_TEST_MANIFEST_SHA256 = (
    "d6da7f2fc7954fa3cf81528028da42bc0b54ddd8320c28ebd07d757b93b2567e"
)
FILTER_COMPONENT_NAMES = (
    "focused",
    "expandedSafe",
    "expandedUi",
    "v2Reviewed",
    "v3Exact",
    "v4Exact",
    "v5Exact",
    "v6Exact",
    "v7Exact",
    "currentV2DeltaExact",
)

EXPECTED_SELECTION_RECORDS = {
    "baseDistinct": (
        393,
        "9d7784e88b7263ca0f3df34b93c59cdcfa0ed76bfe0ee8bc37edabd291966248",
    ),
    "currentV2Delta": (
        2,
        "bf1fb5df5ca49bbd9ab133f6fe42b9c6f887b11dfc70b5d71bf25a3e0dcf4361",
    ),
    "discovered": (
        DISCOVERED_TEST_COUNT,
        DISCOVERED_TEST_MANIFEST_SHA256,
    ),
    "expanded": (
        247,
        "9ad12d0f8b909021046f6b00cdd989dc41010af85d02febd424a4fb6edaf861c",
    ),
    "focused": (
        218,
        "a74d9e570a3e09e243f3f5ee239db4faa555e44cfd0c99790da71ea70b61285c",
    ),
    "historicalDiscovery": (
        2_173,
        "0a550e58480f4733abc264d0ec572e9511492a43dae6ea2dd5459c03548f4e65",
    ),
    "localSocketExcluded": (
        4,
        "f83d04659cc16094468c8966185750a57bd3d702429116d8412b7ab99e4e47fc",
    ),
    "notExecuted": (
        NOT_EXECUTED_TEST_COUNT,
        NOT_EXECUTED_TEST_MANIFEST_SHA256,
    ),
    "selected": (
        SELECTED_TEST_COUNT,
        SELECTED_TEST_MANIFEST_SHA256,
    ),
    "v2CurrentNew": (
        628,
        "dd358dee2279821ed2ec2ec259b4bbd2061346b085d9694902b7857a17eb94fb",
    ),
    "v2HistoricalNew": (
        626,
        "5a1ea997a06466671e6b6eb4095d462cddb185cc54331389173a9cb5b84ee642",
    ),
    "v3New": (
        97,
        "a165a85de87355426d35fdbead9c86b0756ef83fe11cd01a6b7674ef2bf66b50",
    ),
    "v4New": (
        53,
        "0f625c53d1045b750b8a925c969df6d3a902b9d4bd5ed65c3fb283d518f1ca4e",
    ),
    "v5New": (
        V5_TEST_COUNT,
        V5_TEST_MANIFEST_SHA256,
    ),
    "v6New": (
        V6_TEST_COUNT,
        V6_TEST_MANIFEST_SHA256,
    ),
    "v7New": (
        V7_TEST_COUNT,
        V7_TEST_MANIFEST_SHA256,
    ),
}
FOCUSED_EXPANDED_OVERLAP_COUNT = 72

NETWORK_DENY_PROFILE = "(version 1)(allow default)(deny network*)"
COMMAND_PREFIX = (
    "/usr/bin/sandbox-exec",
    "-p",
    NETWORK_DENY_PROFILE,
    "/usr/bin/swift",
    "test",
    "--disable-sandbox",
    "--no-parallel",
    "--filter",
)
ALLOWED_ENVIRONMENT_KEYS = {
    "DEVELOPER_DIR",
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "SDKROOT",
    "TMPDIR",
    "TOOLCHAINS",
}

TRACKED_EXACT_SOURCE_RELATIVE_PATHS = (
    Path(".github/workflows/product-quality.yml"),
    Path("Package.swift"),
    Path(
        "docs/evidence/"
        "g7-reviewed-nonsecurity-swift-addon-identities-v4-proposal.txt"
    ),
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
    V7_IDENTITY_RELATIVE_PATH,
    Path("script/check_g7_nonsecurity_unit_scope_ledger.py"),
    Path("script/g7_nonsecurity_unit_scope_ledger_v1.json"),
    Path("script/test_check_g7_nonsecurity_unit_scope_ledger.py"),
    Path("script/run_g7_nonsecurity_merge_full_current.py"),
    Path("script/run_g7_nonsecurity_merge_full_candidate.py"),
    Path("script/test_check_g7_nonsecurity_merge_full_current.py"),
    Path("script/test_run_g7_nonsecurity_merge_full_current.py"),
)

SOURCE_ROOT_RELATIVE_PATHS = tuple(
    Path(value)
    for value in (
        "apps/macos/P2PNATContracts/Sources",
        "apps/macos/P2PNATConformance/Sources",
        "apps/macos/RelayServerCore/Sources",
        "apps/macos/Protocol/Sources",
        "apps/macos/TrustedDevices/Sources",
        "apps/macos/Pairing/Sources",
        "apps/macos/Transport/Sources",
        "apps/macos/OllamaBackend/Sources",
        "apps/macos/LMStudioBackend/Sources",
        "apps/macos/DocumentIngestion/Sources",
        "apps/macos/CompanionCore/Sources",
        "apps/macos/LocalAgentBridgeApp/Sources",
        "apps/macos/RuntimeDevServer/Sources",
        "apps/macos/AetherLinkRelay/Sources",
        "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources",
        "apps/macos/P2PNATContracts/Tests",
        "apps/macos/P2PNATConformance/Tests",
        "apps/macos/RelayServerCore/Tests",
        "apps/macos/Protocol/Tests",
        "apps/macos/TrustedDevices/Tests",
        "apps/macos/Pairing/Tests",
        "apps/macos/OllamaBackend/Tests",
        "apps/macos/Transport/Tests",
        "apps/macos/LMStudioBackend/Tests",
        "apps/macos/CompanionCore/Tests",
        "apps/macos/LocalAgentBridgeApp/Tests",
        "apps/macos/DocumentIngestion/Tests",
    )
)

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

FOCUSED_EXACT_SOURCE_RELATIVE_PATHS = (
    Path("script/check_product_ci.py"),
    Path(".github/workflows/product-quality.yml"),
    Path("Package.swift"),
)

XCTEST_EVENT_PATTERN = re.compile(
    r"^Test Case '-\[([^\]\s]+) ([^\]\s]+)\]' "
    r"(started|passed|failed|skipped)(?: \([^\r\n]+\))?\.$"
)
XCTEST_SUMMARY_PATTERN = re.compile(
    r"^\s*Executed (\d+) tests?, with (\d+) failures? "
    r"\((\d+) unexpected\) in [0-9.]+ \([0-9.]+\) seconds$"
)


class EvidenceError(ValueError):
    """Raised when evidence bytes do not satisfy the fixed contract."""


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains a duplicate key."""


def reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


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


def require_mapping(
    value: object,
    keys: set[str],
    label: str,
) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise EvidenceError(f"{label} keys differ")
    return value


def require_exact_int(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if type(value) is not int or value < minimum:
        raise EvidenceError(f"{label} must be an exact integer")
    if maximum is not None and value > maximum:
        raise EvidenceError(f"{label} exceeds its bound")
    return value


def require_bool(value: object, expected: bool, label: str) -> None:
    if type(value) is not bool or value is not expected:
        raise EvidenceError(f"{label} must be exactly {expected}")


def require_sha256(value: object, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise EvidenceError(f"{label} must be a lowercase SHA-256")
    return value


def path_label(path: Path, *, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def stable_regular_bytes(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
    require_single_link: bool = True,
) -> tuple[bytes, int, int]:
    try:
        before = path.lstat()
    except OSError as error:
        raise EvidenceError(f"{label} cannot be inspected: {error}") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise EvidenceError(f"{label} must be a physical regular file")
    if require_single_link and before.st_nlink != 1:
        raise EvidenceError(f"{label} must have exactly one hard link")
    if before.st_size > maximum_bytes:
        raise EvidenceError(f"{label} exceeds its byte bound")

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
            stat.S_ISLNK(opened.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise EvidenceError(f"{label} changed during descriptor open")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise EvidenceError(f"{label} exceeds its byte bound")
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
        ) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
            opened.st_nlink,
        ):
            raise EvidenceError(f"{label} changed during descriptor read")
        return b"".join(chunks), stat.S_IMODE(after.st_mode), after.st_mtime_ns
    except OSError as error:
        raise EvidenceError(f"{label} cannot be read: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def load_canonical_json(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
) -> tuple[Mapping[str, object], bytes, int, int]:
    data, mode, mtime_ns = stable_regular_bytes(
        path,
        maximum_bytes=maximum_bytes,
        label=label,
    )
    try:
        document = json.loads(data, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, DuplicateKeyError) as error:
        raise EvidenceError(f"{label} is invalid JSON: {error}") from error
    if type(document) is not dict or canonical_json_bytes(document) != data:
        raise EvidenceError(f"{label} must be canonical ASCII JSON")
    return document, data, mode, mtime_ns


def validate_static_contract() -> None:
    if DISCOVERED_TEST_COUNT != SELECTED_TEST_COUNT + NOT_EXECUTED_TEST_COUNT:
        raise EvidenceError("Swift partition arithmetic differs")
    if (
        393 + 626 + 97 + 53 + V5_TEST_COUNT + V6_TEST_COUNT + V7_TEST_COUNT + 2
        != SELECTED_TEST_COUNT
    ):
        raise EvidenceError("reviewed Swift union arithmetic differs")
    if (
        CURRENT_V2_DELTA_IDENTITIES
        != tuple(sorted(CURRENT_V2_DELTA_IDENTITIES))
        or len(set(CURRENT_V2_DELTA_IDENTITIES)) != 2
        or manifest_sha256(CURRENT_V2_DELTA_IDENTITIES)
        != EXPECTED_SELECTION_RECORDS["currentV2Delta"][1]
    ):
        raise EvidenceError("current V2 delta identity contract differs")
    if (
        LOCAL_SOCKET_EXCLUSION_IDENTITIES
        != tuple(sorted(LOCAL_SOCKET_EXCLUSION_IDENTITIES))
        or len(set(LOCAL_SOCKET_EXCLUSION_IDENTITIES)) != 4
        or manifest_sha256(LOCAL_SOCKET_EXCLUSION_IDENTITIES)
        != EXPECTED_SELECTION_RECORDS["localSocketExcluded"][1]
    ):
        raise EvidenceError("local-socket exclusion identity contract differs")
    if SELECTED_TEST_COUNT + len(LOCAL_SOCKET_EXCLUSION_IDENTITIES) != (
        PARENT_REVIEWED_TEST_COUNT
    ):
        raise EvidenceError("parent reviewed Swift arithmetic differs")
    if DISCOVERED_TEST_COUNT != (
        PARENT_REVIEWED_TEST_COUNT + PARENT_REMAINING_TEST_COUNT
    ):
        raise EvidenceError("parent remaining Swift arithmetic differs")
    for label, value in (
        ("focused carrier", FOCUSED_CARRIER_TEST_MANIFEST_SHA256),
        ("parent reviewed", PARENT_REVIEWED_TEST_MANIFEST_SHA256),
        ("parent remaining", PARENT_REMAINING_TEST_MANIFEST_SHA256),
    ):
        require_sha256(value, f"{label} SHA-256")
    if len(set(TRACKED_EXACT_SOURCE_RELATIVE_PATHS)) != len(
        TRACKED_EXACT_SOURCE_RELATIVE_PATHS
    ):
        raise EvidenceError("exact source paths must be unique")
    if len(set(SOURCE_ROOT_RELATIVE_PATHS)) != len(SOURCE_ROOT_RELATIVE_PATHS):
        raise EvidenceError("source roots must be unique")
    for label, value in (
        ("test-list", TEST_LIST_SHA256),
        ("discovered", DISCOVERED_TEST_MANIFEST_SHA256),
        ("selected", SELECTED_TEST_MANIFEST_SHA256),
        ("not-executed", NOT_EXECUTED_TEST_MANIFEST_SHA256),
    ):
        require_sha256(value, f"{label} SHA-256")
    if set(EXPECTED_SELECTION_RECORDS) != {
        "baseDistinct",
        "currentV2Delta",
        "discovered",
        "expanded",
        "focused",
        "historicalDiscovery",
        "localSocketExcluded",
        "notExecuted",
        "selected",
        "v2CurrentNew",
        "v2HistoricalNew",
        "v3New",
        "v4New",
        "v5New",
        "v6New",
        "v7New",
    }:
        raise EvidenceError("selection record names differ")


def exact_filter(identities: Sequence[str]) -> str:
    return r"^(?:" + "|".join(re.escape(identity) for identity in identities) + r")$"


def read_exact_tests(
    *,
    root: Path,
    label: str,
    relative_path: Path,
    expected_bytes: int,
    expected_raw_sha256: str,
    expected_count: int,
    expected_manifest_sha256: str,
) -> tuple[str, ...]:
    data, mode, _mtime_ns = stable_regular_bytes(
        root / relative_path,
        maximum_bytes=RESULT_MAX_BYTES,
        label=f"{label} identity manifest",
    )
    if mode != 0o644:
        raise EvidenceError(f"{label} identity manifest mode must be 0644")
    if len(data) != expected_bytes or hashlib.sha256(data).hexdigest() != (
        expected_raw_sha256
    ):
        raise EvidenceError(f"{label} identity manifest bytes differ")
    if not data.endswith(b"\n") or b"\r" in data:
        raise EvidenceError(f"{label} identity manifest must use canonical LF lines")
    try:
        identities = tuple(data.decode("ascii").splitlines())
    except UnicodeError as error:
        raise EvidenceError(
            f"{label} identity manifest is not ASCII: {error}"
        ) from error
    if (
        identities != tuple(sorted(identities))
        or len(identities) != expected_count
        or len(set(identities)) != expected_count
        or any(
            identity != identity.strip()
            or re.fullmatch(r"[^\s/]+/[^\s/]+", identity) is None
            for identity in identities
        )
        or manifest_sha256(identities) != expected_manifest_sha256
    ):
        raise EvidenceError(f"{label} identity manifest contract differs")
    return identities


def read_v5_tests(*, root: Path = ROOT) -> tuple[str, ...]:
    return read_exact_tests(
        root=root,
        label="V5",
        relative_path=V5_IDENTITY_RELATIVE_PATH,
        expected_bytes=V5_IDENTITY_BYTES,
        expected_raw_sha256=V5_IDENTITY_RAW_SHA256,
        expected_count=V5_TEST_COUNT,
        expected_manifest_sha256=V5_TEST_MANIFEST_SHA256,
    )


def read_v6_tests(*, root: Path = ROOT) -> tuple[str, ...]:
    return read_exact_tests(
        root=root,
        label="V6",
        relative_path=V6_IDENTITY_RELATIVE_PATH,
        expected_bytes=V6_IDENTITY_BYTES,
        expected_raw_sha256=V6_IDENTITY_RAW_SHA256,
        expected_count=V6_TEST_COUNT,
        expected_manifest_sha256=V6_TEST_MANIFEST_SHA256,
    )


def read_v7_tests(*, root: Path = ROOT) -> tuple[str, ...]:
    return read_exact_tests(
        root=root,
        label="V7",
        relative_path=V7_IDENTITY_RELATIVE_PATH,
        expected_bytes=V7_IDENTITY_BYTES,
        expected_raw_sha256=V7_IDENTITY_RAW_SHA256,
        expected_count=V7_TEST_COUNT,
        expected_manifest_sha256=V7_TEST_MANIFEST_SHA256,
    )


def read_test_list(
    *,
    root: Path = ROOT,
) -> tuple[tuple[str, ...], bytes]:
    path = root / TEST_LIST_RELATIVE_PATH
    data, _mode, _mtime_ns = stable_regular_bytes(
        path,
        maximum_bytes=TEST_LIST_MAX_BYTES,
        label="Swift test list",
    )
    if len(data) != TEST_LIST_BYTES or hashlib.sha256(data).hexdigest() != (
        TEST_LIST_SHA256
    ):
        raise EvidenceError("Swift test-list bytes differ from the reviewed discovery")
    if b"\r" in data or not data.endswith(b"\n"):
        raise EvidenceError("Swift test list must use canonical LF lines")
    try:
        text = data.decode("utf-8")
    except UnicodeError as error:
        raise EvidenceError(f"Swift test list must be UTF-8: {error}") from error
    identities = tuple(text.splitlines())
    if len(identities) != DISCOVERED_TEST_COUNT:
        raise EvidenceError("Swift discovery count differs")
    if len(set(identities)) != len(identities):
        raise EvidenceError("Swift test list contains duplicate identities")
    if any(
        not identity
        or identity != identity.strip()
        or re.fullmatch(r"[^\s/]+/[^\s/]+", identity) is None
        for identity in identities
    ):
        raise EvidenceError("Swift test list contains malformed identities")
    if manifest_sha256(identities) != DISCOVERED_TEST_MANIFEST_SHA256:
        raise EvidenceError("Swift discovery identity manifest differs")
    return identities, data


def validate_partition_record(
    value: object,
    *,
    expected_tests: int,
    expected_sha256: str,
    label: str,
) -> None:
    row = require_mapping(value, {"manifestSha256", "tests"}, label)
    if require_exact_int(row["tests"], f"{label}.tests") != expected_tests:
        raise EvidenceError(f"{label}.tests differs")
    if require_sha256(row["manifestSha256"], f"{label}.manifestSha256") != (
        expected_sha256
    ):
        raise EvidenceError(f"{label}.manifestSha256 differs")


def command_environment_footprint(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> int:
    return sum(len(os.fsencode(value)) + 1 for value in command) + sum(
        len(os.fsencode(key)) + len(os.fsencode(value)) + 2
        for key, value in environment.items()
    )


def validate_execution_contract(
    document: object,
    discovered: tuple[str, ...],
    *,
    root: Path = ROOT,
) -> tuple[tuple[str, ...], tuple[str, ...], str, Mapping[str, str], int]:
    row = require_mapping(
        document,
        {
            "command",
            "commandAndEnvironmentBytes",
            "commandAndEnvironmentMaximumBytes",
            "contract",
            "environment",
            "filterComponents",
            "networkDenyProbePassed",
            "networkDenyProfile",
            "schemaVersion",
            "selection",
            "singleSwiftInvocation",
        },
        "execution contract",
    )
    if row["contract"] != EXECUTION_CONTRACT:
        raise EvidenceError("execution contract identity differs")
    if require_exact_int(row["schemaVersion"], "execution schemaVersion") != 1:
        raise EvidenceError("execution schema version differs")
    require_bool(
        row["networkDenyProbePassed"],
        True,
        "execution networkDenyProbePassed",
    )
    require_bool(
        row["singleSwiftInvocation"],
        True,
        "execution singleSwiftInvocation",
    )
    if row["networkDenyProfile"] != NETWORK_DENY_PROFILE:
        raise EvidenceError("execution network-deny profile differs")

    command_value = row["command"]
    if (
        type(command_value) is not list
        or len(command_value) != len(COMMAND_PREFIX) + 1
        or any(type(value) is not str or not value for value in command_value)
    ):
        raise EvidenceError("execution command shape differs")
    command = tuple(command_value)
    if command[:-1] != COMMAND_PREFIX:
        raise EvidenceError("execution command prefix differs")
    if "--skip" in command:
        raise EvidenceError("execution command must not use a skip filter")
    filter_pattern = command[-1]
    if len(filter_pattern.encode("utf-8")) > FILTER_MAX_BYTES:
        raise EvidenceError("execution filter exceeds its byte bound")
    components_value = row["filterComponents"]
    if type(components_value) is not list or len(components_value) != len(
        FILTER_COMPONENT_NAMES
    ):
        raise EvidenceError("execution filter component shape differs")
    component_patterns: dict[str, str] = {}
    for index, expected_name in enumerate(FILTER_COMPONENT_NAMES):
        component = require_mapping(
            components_value[index],
            {"name", "pattern"},
            f"execution filterComponents[{index}]",
        )
        if component["name"] != expected_name:
            raise EvidenceError("execution filter component order differs")
        pattern = component["pattern"]
        if type(pattern) is not str or not pattern:
            raise EvidenceError("execution filter component must be nonempty")
        component_patterns[expected_name] = pattern
    expected_filter = "(?:" + "|".join(
        component_patterns[name] for name in FILTER_COMPONENT_NAMES
    ) + ")"
    if filter_pattern != expected_filter:
        raise EvidenceError("execution filter differs from its ordered components")

    try:
        selected = tuple(
            sorted(
                identity
                for identity in discovered
                if re.search(filter_pattern, identity)
            )
        )
        matched_components = {
            name: {
                identity
                for identity in discovered
                if re.search(pattern, identity)
            }
            for name, pattern in component_patterns.items()
        }
    except re.error as error:
        raise EvidenceError(f"execution filter is invalid: {error}") from error
    not_executed = tuple(sorted(set(discovered) - set(selected)))
    if (
        len(selected) != SELECTED_TEST_COUNT
        or manifest_sha256(selected) != SELECTED_TEST_MANIFEST_SHA256
    ):
        raise EvidenceError("execution filter selected identity set differs")
    if (
        len(not_executed) != NOT_EXECUTED_TEST_COUNT
        or manifest_sha256(not_executed) != NOT_EXECUTED_TEST_MANIFEST_SHA256
    ):
        raise EvidenceError("execution filter remaining identity set differs")
    if set(selected) & set(not_executed):
        raise EvidenceError("execution selected and remaining sets overlap")
    if set(selected) | set(not_executed) != set(discovered):
        raise EvidenceError("execution filter does not partition discovery")

    focused = matched_components["focused"]
    expanded = (
        matched_components["expandedSafe"]
        | matched_components["expandedUi"]
    )
    base_distinct = focused | expanded
    v2_current_new = matched_components["v2Reviewed"] - base_distinct
    current_delta = matched_components["currentV2DeltaExact"]
    v2_historical_new = v2_current_new - current_delta
    v3_new = matched_components["v3Exact"]
    v4_new = matched_components["v4Exact"]
    v5_new = matched_components["v5Exact"]
    v6_new = matched_components["v6Exact"]
    v7_new = matched_components["v7Exact"]
    v5_manifest = read_v5_tests(root=root)
    if component_patterns["v5Exact"] != exact_filter(v5_manifest):
        raise EvidenceError("execution V5 filter differs from the exact manifest")
    if v5_new != set(v5_manifest):
        raise EvidenceError("execution V5 selected identities differ from the manifest")
    v6_manifest = read_v6_tests(root=root)
    if component_patterns["v6Exact"] != exact_filter(v6_manifest):
        raise EvidenceError("execution V6 filter differs from the exact manifest")
    if v6_new != set(v6_manifest):
        raise EvidenceError("execution V6 selected identities differ from the manifest")
    v7_manifest = read_v7_tests(root=root)
    if component_patterns["v7Exact"] != exact_filter(v7_manifest):
        raise EvidenceError("execution V7 filter differs from the exact manifest")
    if v7_new != set(v7_manifest):
        raise EvidenceError("execution V7 selected identities differ from the manifest")
    historical_discovery = set(discovered) - set(CURRENT_V2_DELTA_IDENTITIES)
    local_socket_excluded = set(LOCAL_SOCKET_EXCLUSION_IDENTITIES)
    derived_sets = {
        "baseDistinct": base_distinct,
        "currentV2Delta": current_delta,
        "discovered": set(discovered),
        "expanded": expanded,
        "focused": focused,
        "historicalDiscovery": historical_discovery,
        "localSocketExcluded": local_socket_excluded,
        "notExecuted": set(not_executed),
        "selected": set(selected),
        "v2CurrentNew": v2_current_new,
        "v2HistoricalNew": v2_historical_new,
        "v3New": v3_new,
        "v4New": v4_new,
        "v5New": v5_new,
        "v6New": v6_new,
        "v7New": v7_new,
    }
    for key, identities in derived_sets.items():
        expected_count, expected_digest = EXPECTED_SELECTION_RECORDS[key]
        if len(identities) != expected_count or manifest_sha256(identities) != (
            expected_digest
        ):
            raise EvidenceError(f"execution derived component differs: {key}")
    if current_delta != set(CURRENT_V2_DELTA_IDENTITIES):
        raise EvidenceError("execution current V2 delta identities differ")
    if not local_socket_excluded <= set(discovered):
        raise EvidenceError("local-socket exclusions are absent from discovery")
    if local_socket_excluded & set(selected):
        raise EvidenceError("local-socket exclusions remain selected")
    if not local_socket_excluded <= set(not_executed):
        raise EvidenceError("local-socket exclusions are absent from remaining")
    if len(focused & expanded) != FOCUSED_EXPANDED_OVERLAP_COUNT:
        raise EvidenceError("execution focused/expanded overlap differs")
    additive_sets = (
        base_distinct,
        v2_current_new,
        v3_new,
        v4_new,
        v5_new,
        v6_new,
        v7_new,
    )
    if any(
        left & right
        for index, left in enumerate(additive_sets)
        for right in additive_sets[index + 1 :]
    ):
        raise EvidenceError("execution additive filter components overlap")
    if set().union(*additive_sets) != set(selected):
        raise EvidenceError("execution additive filter union differs")
    if not current_delta <= v2_current_new:
        raise EvidenceError("execution current V2 delta is outside current V2")

    environment = require_mapping(
        row["environment"],
        set(row["environment"]) if type(row["environment"]) is dict else set(),
        "execution environment",
    )
    if any(
        type(key) is not str
        or type(value) is not str
        or "\x00" in value
        for key, value in environment.items()
    ):
        raise EvidenceError("execution environment must be a string mapping")
    if not set(environment) <= ALLOWED_ENVIRONMENT_KEYS:
        raise EvidenceError("execution environment contains a non-allowlisted key")
    if environment.get("LC_ALL") != "C" or environment.get("LANG") != "C":
        raise EvidenceError("execution locale must be exactly C")
    footprint = command_environment_footprint(command, environment)
    if footprint > COMMAND_AND_ENVIRONMENT_MAX_BYTES:
        raise EvidenceError("execution argv/environment exceeds its byte bound")
    if require_exact_int(
        row["commandAndEnvironmentMaximumBytes"],
        "execution commandAndEnvironmentMaximumBytes",
    ) != COMMAND_AND_ENVIRONMENT_MAX_BYTES:
        raise EvidenceError("execution argv/environment maximum differs")
    if require_exact_int(
        row["commandAndEnvironmentBytes"],
        "execution commandAndEnvironmentBytes",
    ) != footprint:
        raise EvidenceError("execution argv/environment byte count differs")

    selection = require_mapping(
        row["selection"],
        set(EXPECTED_SELECTION_RECORDS) | {"focusedExpandedOverlap"},
        "execution selection",
    )
    for key, (count, digest) in EXPECTED_SELECTION_RECORDS.items():
        validate_partition_record(
            selection[key],
            expected_tests=count,
            expected_sha256=digest,
            label=f"execution selection.{key}",
        )
    if require_exact_int(
        selection["focusedExpandedOverlap"],
        "execution selection.focusedExpandedOverlap",
    ) != FOCUSED_EXPANDED_OVERLAP_COUNT:
        raise EvidenceError("focused/expanded overlap differs")
    return selected, not_executed, filter_pattern, environment, footprint


def parent_partition_from_execution(
    document: object,
    discovered: tuple[str, ...],
    *,
    root: Path = ROOT,
) -> Mapping[str, tuple[str, ...]]:
    selected, _not_executed, _filter, _environment, _footprint = (
        validate_execution_contract(document, discovered, root=root)
    )
    row = require_mapping(
        document,
        {
            "command",
            "commandAndEnvironmentBytes",
            "commandAndEnvironmentMaximumBytes",
            "contract",
            "environment",
            "filterComponents",
            "networkDenyProbePassed",
            "networkDenyProfile",
            "schemaVersion",
            "selection",
            "singleSwiftInvocation",
        },
        "execution contract",
    )
    components = row["filterComponents"]
    if type(components) is not list:
        raise EvidenceError("execution filter components differ")
    focused_component = require_mapping(
        components[0],
        {"name", "pattern"},
        "execution focused component",
    )
    focused_pattern = focused_component["pattern"]
    if focused_component["name"] != "focused" or type(focused_pattern) is not str:
        raise EvidenceError("execution focused component differs")
    focused_without_sockets = tuple(
        sorted(
            identity
            for identity in discovered
            if re.search(focused_pattern, identity)
        )
    )
    if (
        len(focused_without_sockets) != EXPECTED_SELECTION_RECORDS["focused"][0]
        or manifest_sha256(focused_without_sockets)
        != EXPECTED_SELECTION_RECORDS["focused"][1]
    ):
        raise EvidenceError("parent focused no-socket set differs")
    local_socket = tuple(sorted(LOCAL_SOCKET_EXCLUSION_IDENTITIES))
    focused_carrier = tuple(sorted(set(focused_without_sockets) | set(local_socket)))
    reviewed = tuple(sorted(set(selected) | set(local_socket)))
    remaining = tuple(sorted(set(discovered) - set(reviewed)))
    contracts = (
        (
            "focused carrier",
            focused_carrier,
            FOCUSED_CARRIER_TEST_COUNT,
            FOCUSED_CARRIER_TEST_MANIFEST_SHA256,
        ),
        (
            "parent reviewed",
            reviewed,
            PARENT_REVIEWED_TEST_COUNT,
            PARENT_REVIEWED_TEST_MANIFEST_SHA256,
        ),
        (
            "parent remaining",
            remaining,
            PARENT_REMAINING_TEST_COUNT,
            PARENT_REMAINING_TEST_MANIFEST_SHA256,
        ),
    )
    for label, identities, count, digest in contracts:
        if len(identities) != count or manifest_sha256(identities) != digest:
            raise EvidenceError(f"{label} identity contract differs")
    if set(selected) & set(local_socket):
        raise EvidenceError("parent local-socket contribution overlaps no-socket child")
    if set(reviewed) & set(remaining):
        raise EvidenceError("parent reviewed and remaining sets overlap")
    if set(reviewed) | set(remaining) != set(discovered):
        raise EvidenceError("parent partition does not cover discovery")
    return {
        "focusedCarrier": focused_carrier,
        "focusedCarrierOverlap": focused_without_sockets,
        "localSocketExecuted": local_socket,
        "noSocketExecuted": selected,
        "remaining": remaining,
        "reviewedExecuted": reviewed,
    }


def source_snapshot_for_contract(
    *,
    exact_relative_paths: Sequence[Path],
    source_root_relative_paths: Sequence[Path],
    root: Path = ROOT,
) -> Mapping[str, object]:
    paths = [root / relative for relative in exact_relative_paths]
    for relative_root in source_root_relative_paths:
        source_root = root / relative_root
        try:
            root_stat = source_root.lstat()
        except OSError as error:
            raise EvidenceError(
                f"source root {relative_root.as_posix()} cannot be inspected: {error}"
            ) from error
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise EvidenceError(
                f"source root {relative_root.as_posix()} must be a physical directory"
            )
        paths.extend(path for path in source_root.rglob("*") if path.is_file())

    unique_paths = sorted(
        set(paths),
        key=lambda path: path_label(path, root=root),
    )
    entries: list[dict[str, object]] = []
    total = 0
    for path in unique_paths:
        label = f"source input {path_label(path, root=root)}"
        data, mode, _mtime_ns = stable_regular_bytes(
            path,
            maximum_bytes=SOURCE_FILE_MAX_BYTES,
            label=label,
        )
        total += len(data)
        if total > SOURCE_TOTAL_MAX_BYTES:
            raise EvidenceError("source input bytes exceed their aggregate bound")
        entries.append(
            {
                "bytes": len(data),
                "mode": mode,
                "path": path_label(path, root=root),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = canonical_json_bytes(entries)
    return {
        "count": len(entries),
        "sha256": hashlib.sha256(manifest).hexdigest(),
    }


def source_snapshot(*, root: Path = ROOT) -> Mapping[str, object]:
    return source_snapshot_for_contract(
        exact_relative_paths=(
            *TRACKED_EXACT_SOURCE_RELATIVE_PATHS,
            EXECUTION_CONTRACT_RELATIVE_PATH,
        ),
        source_root_relative_paths=SOURCE_ROOT_RELATIVE_PATHS,
        root=root,
    )


def focused_source_snapshot(*, root: Path = ROOT) -> Mapping[str, object]:
    return source_snapshot_for_contract(
        exact_relative_paths=FOCUSED_EXACT_SOURCE_RELATIVE_PATHS,
        source_root_relative_paths=SOURCE_ROOT_RELATIVE_PATHS,
        root=root,
    )


def validate_source_inputs(
    value: object,
    *,
    expected: Mapping[str, object],
    label: str,
) -> None:
    row = require_mapping(value, {"count", "sha256"}, label)
    require_exact_int(row["count"], f"{label}.count", minimum=1)
    require_sha256(row["sha256"], f"{label}.sha256")
    if row != expected:
        raise EvidenceError(f"{label} differs from current source bytes")


def test_list_snapshot(
    identities: tuple[str, ...],
    data: bytes,
) -> Mapping[str, object]:
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "testcaseManifestSha256": manifest_sha256(identities),
        "tests": len(identities),
    }


def console_snapshot(
    data: bytes,
    expected_tests: tuple[str, ...],
) -> Mapping[str, object]:
    if not data.endswith(b"\n"):
        raise EvidenceError("Swift console must end with LF")
    try:
        text = data.decode("utf-8")
    except UnicodeError as error:
        raise EvidenceError(f"Swift console must be UTF-8: {error}") from error
    events: dict[str, list[tuple[int, str]]] = {}
    summaries: list[tuple[int, tuple[int, int, int]]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("Test Case '-["):
            match = XCTEST_EVENT_PATTERN.fullmatch(line)
            if match is None:
                raise EvidenceError(
                    f"Swift console contains malformed XCTest event at line {line_number}"
                )
            identity = f"{match.group(1)}/{match.group(2)}"
            events.setdefault(identity, []).append((line_number, match.group(3)))
        summary = XCTEST_SUMMARY_PATTERN.fullmatch(line)
        if summary is not None:
            summaries.append(
                (line_number, tuple(int(value) for value in summary.groups()))
            )
    expected_set = set(expected_tests)
    if set(events) != expected_set:
        missing = sorted(expected_set - set(events))
        unexpected = sorted(set(events) - expected_set)
        raise EvidenceError(
            "Swift console identities differ; "
            f"missing={missing[:3]!r}; unexpected={unexpected[:3]!r}"
        )
    for identity in sorted(expected_set):
        event_names = tuple(event for _line, event in events[identity])
        if event_names != ("started", "passed"):
            raise EvidenceError(
                f"Swift console events differ for {identity}: {event_names!r}"
            )
    if any(failures or unexpected for _line, (_tests, failures, unexpected) in summaries):
        raise EvidenceError("Swift console contains a failing XCTest summary")
    if not summaries or summaries[-1][1] != (len(expected_tests), 0, 0):
        raise EvidenceError("Swift console final XCTest summary differs")
    last_event_line = max(
        line for identity_events in events.values() for line, _event in identity_events
    )
    if summaries[-1][0] <= last_event_line:
        raise EvidenceError("Swift console final summary must follow all test events")
    return {
        "bytes": len(data),
        "errors": 0,
        "failures": 0,
        "sha256": hashlib.sha256(data).hexdigest(),
        "skipped": 0,
        "testcaseManifestSha256": manifest_sha256(expected_tests),
        "tests": len(expected_tests),
    }


def current_file_record(
    relative: Path,
    *,
    root: Path,
    maximum_bytes: int,
) -> Mapping[str, object]:
    path = root / relative
    data, mode, _mtime_ns = stable_regular_bytes(
        path,
        maximum_bytes=maximum_bytes,
        label=f"artifact {relative.as_posix()}",
    )
    return {
        "bytes": len(data),
        "mode": mode,
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def validate_artifact_record(
    value: object,
    *,
    expected: Mapping[str, object],
    label: str,
) -> None:
    row = require_mapping(value, {"bytes", "mode", "path", "sha256"}, label)
    require_exact_int(row["bytes"], f"{label}.bytes")
    require_exact_int(row["mode"], f"{label}.mode", maximum=0o7777)
    if type(row["path"]) is not str or not row["path"]:
        raise EvidenceError(f"{label}.path must be a nonempty string")
    require_sha256(row["sha256"], f"{label}.sha256")
    if row != expected:
        raise EvidenceError(f"{label} differs from current artifact bytes")


def expected_result_payload(
    *,
    root: Path = ROOT,
) -> Mapping[str, object]:
    output_root = root / OUTPUT_ROOT_RELATIVE_PATH
    try:
        output_stat = output_root.lstat()
    except OSError as error:
        raise EvidenceError(f"current-run output directory is unavailable: {error}") from error
    if (
        stat.S_ISLNK(output_stat.st_mode)
        or not stat.S_ISDIR(output_stat.st_mode)
        or stat.S_IMODE(output_stat.st_mode) != 0o700
    ):
        raise EvidenceError("current-run output directory must be physical mode 0700")

    discovered, test_list_data = read_test_list(root=root)
    execution, _execution_data, execution_mode, execution_mtime = load_canonical_json(
        root / EXECUTION_CONTRACT_RELATIVE_PATH,
        maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
        label="current-run execution contract",
    )
    if execution_mode != 0o600:
        raise EvidenceError("execution contract mode must be 0600")
    selected, _remaining, filter_pattern, _environment, footprint = (
        validate_execution_contract(execution, discovered, root=root)
    )
    current_source = source_snapshot(root=root)
    selected_list_snapshot = test_list_snapshot(selected, test_list_data)

    marker, marker_data, marker_mode, marker_mtime = load_canonical_json(
        root / RUN_MARKER_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
        label="current-run source marker",
    )
    if marker_mode != 0o600:
        raise EvidenceError("run marker mode must be 0600")
    expected_marker = {
        "contract": RUN_MARKER_CONTRACT,
        "sourceInputs": current_source,
        "testList": selected_list_snapshot,
    }
    if marker != expected_marker:
        raise EvidenceError("run marker differs from current source and selection")
    _list_data, _list_mode, list_mtime = stable_regular_bytes(
        root / TEST_LIST_RELATIVE_PATH,
        maximum_bytes=TEST_LIST_MAX_BYTES,
        label="Swift test list timestamp readback",
    )
    if marker_mtime <= list_mtime:
        raise EvidenceError("run marker must postdate the Swift test list")
    if marker_mtime <= execution_mtime:
        raise EvidenceError("run marker must postdate the execution contract")
    if marker_mtime > time.time_ns() + FUTURE_MTIME_TOLERANCE_NS:
        raise EvidenceError("run marker timestamp is implausibly in the future")

    console_data, console_mode, console_mtime = stable_regular_bytes(
        root / CONSOLE_RELATIVE_PATH,
        maximum_bytes=CONSOLE_MAX_BYTES,
        label="current-run Swift console",
    )
    if console_mode != 0o600:
        raise EvidenceError("Swift console mode must be 0600")
    if console_mtime <= marker_mtime:
        raise EvidenceError("Swift console must postdate the run marker")
    observed_console = console_snapshot(console_data, selected)

    binding, _binding_data, binding_mode, binding_mtime = load_canonical_json(
        root / BINDING_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
        label="current-run Swift binding",
    )
    if binding_mode != 0o600:
        raise EvidenceError("Swift binding mode must be 0600")
    if binding_mtime <= console_mtime:
        raise EvidenceError("Swift binding must postdate the console")
    if binding_mtime > time.time_ns() + FUTURE_MTIME_TOLERANCE_NS:
        raise EvidenceError("Swift binding timestamp is implausibly in the future")
    expected_binding = {
        "contract": BINDING_CONTRACT,
        "result": observed_console,
        "runMarker": {
            "bytes": len(marker_data),
            "sha256": hashlib.sha256(marker_data).hexdigest(),
        },
        "sourceInputs": current_source,
        "testList": selected_list_snapshot,
    }
    if binding != expected_binding:
        raise EvidenceError("Swift binding differs from current evidence bytes")

    artifact_contracts = {
        "binding": (BINDING_RELATIVE_PATH, RESULT_MAX_BYTES),
        "console": (CONSOLE_RELATIVE_PATH, CONSOLE_MAX_BYTES),
        "executionContract": (
            EXECUTION_CONTRACT_RELATIVE_PATH,
            EXECUTION_CONTRACT_MAX_BYTES,
        ),
        "runMarker": (RUN_MARKER_RELATIVE_PATH, RESULT_MAX_BYTES),
        "testList": (TEST_LIST_RELATIVE_PATH, TEST_LIST_MAX_BYTES),
    }
    artifacts = {
        key: current_file_record(relative, root=root, maximum_bytes=maximum)
        for key, (relative, maximum) in artifact_contracts.items()
    }
    for key, record in artifacts.items():
        if key != "testList" and record["mode"] != 0o600:
            raise EvidenceError(f"artifact {key} mode must be 0600")

    coverage = {
        key: {"manifestSha256": digest, "tests": count}
        for key, (count, digest) in EXPECTED_SELECTION_RECORDS.items()
    }
    coverage["focusedExpandedOverlap"] = FOCUSED_EXPANDED_OVERLAP_COUNT
    return {
        "artifacts": artifacts,
        "contract": CONTRACT,
        "coverage": coverage,
        "execution": {
            "commandAndEnvironmentBytes": footprint,
            "filterBytes": len(filter_pattern.encode("utf-8")),
            "networkDenyProfile": NETWORK_DENY_PROFILE,
            "singleSwiftInvocation": True,
        },
        "limitations": LIMITATIONS,
        "result": "passed",
        "schemaVersion": SCHEMA_VERSION,
        "sourceInputs": current_source,
    }


def validate_result_document(
    document: object,
    *,
    expected: Mapping[str, object],
) -> None:
    row = require_mapping(
        document,
        {
            "artifacts",
            "contract",
            "coverage",
            "execution",
            "limitations",
            "result",
            "schemaVersion",
            "sourceInputs",
        },
        "current-run result",
    )
    if row["contract"] != CONTRACT or row["result"] != "passed":
        raise EvidenceError("current-run result identity or status differs")
    if require_exact_int(row["schemaVersion"], "result.schemaVersion") != 1:
        raise EvidenceError("current-run schema version differs")

    coverage = require_mapping(
        row["coverage"],
        set(EXPECTED_SELECTION_RECORDS) | {"focusedExpandedOverlap"},
        "result.coverage",
    )
    for key, (count, digest) in EXPECTED_SELECTION_RECORDS.items():
        validate_partition_record(
            coverage[key],
            expected_tests=count,
            expected_sha256=digest,
            label=f"result.coverage.{key}",
        )
    if require_exact_int(
        coverage["focusedExpandedOverlap"],
        "result.coverage.focusedExpandedOverlap",
    ) != FOCUSED_EXPANDED_OVERLAP_COUNT:
        raise EvidenceError("result focused/expanded overlap differs")

    limitations = require_mapping(
        row["limitations"], set(LIMITATIONS), "result.limitations"
    )
    for key, value in LIMITATIONS.items():
        require_bool(limitations[key], value, f"result.limitations.{key}")

    execution = require_mapping(
        row["execution"],
        {
            "commandAndEnvironmentBytes",
            "filterBytes",
            "networkDenyProfile",
            "singleSwiftInvocation",
        },
        "result.execution",
    )
    require_exact_int(
        execution["commandAndEnvironmentBytes"],
        "result.execution.commandAndEnvironmentBytes",
    )
    require_exact_int(execution["filterBytes"], "result.execution.filterBytes")
    require_bool(
        execution["singleSwiftInvocation"],
        True,
        "result.execution.singleSwiftInvocation",
    )
    if execution["networkDenyProfile"] != NETWORK_DENY_PROFILE:
        raise EvidenceError("result network-deny profile differs")
    validate_source_inputs(
        row["sourceInputs"],
        expected=expected["sourceInputs"],
        label="result.sourceInputs",
    )

    artifacts = require_mapping(
        row["artifacts"],
        {"binding", "console", "executionContract", "runMarker", "testList"},
        "result.artifacts",
    )
    expected_artifacts = expected["artifacts"]
    if type(expected_artifacts) is not dict:
        raise EvidenceError("internal expected artifact contract differs")
    for key in artifacts:
        validate_artifact_record(
            artifacts[key],
            expected=expected_artifacts[key],
            label=f"result.artifacts.{key}",
        )
    if row != expected:
        raise EvidenceError("current-run result differs from reconstructed evidence")


def validate_result(
    result_path: Path,
    *,
    root: Path = ROOT,
) -> Mapping[str, object]:
    validate_static_contract()
    document, data, mode, result_mtime_ns = load_canonical_json(
        result_path,
        maximum_bytes=RESULT_MAX_BYTES,
        label="current-run result",
    )
    if result_path == root / RESULT_RELATIVE_PATH:
        if mode != 0o600:
            raise EvidenceError("canonical current-run result mode must be 0600")
        _binding_data, _binding_mode, binding_mtime_ns = stable_regular_bytes(
            root / BINDING_RELATIVE_PATH,
            maximum_bytes=RESULT_MAX_BYTES,
            label="current-run binding chronology",
        )
        if result_mtime_ns <= binding_mtime_ns:
            raise EvidenceError("canonical current-run result must postdate binding")
        if result_mtime_ns > time.time_ns() + FUTURE_MTIME_TOLERANCE_NS:
            raise EvidenceError(
                "canonical current-run result timestamp is implausibly in the future"
            )
    expected = expected_result_payload(root=root)
    validate_result_document(document, expected=expected)
    if data != canonical_json_bytes(expected):
        raise EvidenceError("current-run result bytes differ")
    final_expected = expected_result_payload(root=root)
    if final_expected != expected:
        raise EvidenceError("current evidence changed during complete readback")
    return document


def partition_snapshot(identities: tuple[str, ...]) -> Mapping[str, object]:
    return {
        "manifestSha256": manifest_sha256(identities),
        "tests": len(identities),
    }


def focused_child_evidence(
    *,
    root: Path,
    discovered: tuple[str, ...],
    execution: object,
) -> Mapping[str, object]:
    partition = parent_partition_from_execution(execution, discovered, root=root)
    focused_carrier = partition["focusedCarrier"]
    test_list_data, test_list_mode, test_list_mtime = stable_regular_bytes(
        root / TEST_LIST_RELATIVE_PATH,
        maximum_bytes=TEST_LIST_MAX_BYTES,
        label="shared Swift test list",
    )
    if test_list_mode not in (0o600, 0o644):
        raise EvidenceError("shared Swift test list mode differs")
    focused_source = focused_source_snapshot(root=root)
    focused_list = test_list_snapshot(focused_carrier, test_list_data)

    marker, marker_data, marker_mode, marker_mtime = load_canonical_json(
        root / FOCUSED_RUN_MARKER_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
        label="focused carrier run marker",
    )
    if marker_mode != 0o600:
        raise EvidenceError("focused carrier run marker mode must be 0600")
    expected_marker = {
        "contract": RUN_MARKER_CONTRACT,
        "sourceInputs": focused_source,
        "testList": focused_list,
    }
    if marker != expected_marker:
        raise EvidenceError("focused carrier run marker differs from current source")
    if marker_mtime <= test_list_mtime:
        raise EvidenceError("focused carrier marker must postdate the shared test list")

    console_data, console_mode, console_mtime = stable_regular_bytes(
        root / FOCUSED_CONSOLE_RELATIVE_PATH,
        maximum_bytes=CONSOLE_MAX_BYTES,
        label="focused carrier console",
    )
    if console_mode != 0o600:
        raise EvidenceError("focused carrier console mode must be 0600")
    if console_mtime <= marker_mtime:
        raise EvidenceError("focused carrier console must postdate its marker")
    focused_result = console_snapshot(console_data, focused_carrier)

    binding, _binding_data, binding_mode, binding_mtime = load_canonical_json(
        root / FOCUSED_BINDING_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
        label="focused carrier binding",
    )
    if binding_mode != 0o600:
        raise EvidenceError("focused carrier binding mode must be 0600")
    if binding_mtime <= console_mtime:
        raise EvidenceError("focused carrier binding must postdate its console")
    if binding_mtime > time.time_ns() + FUTURE_MTIME_TOLERANCE_NS:
        raise EvidenceError("focused carrier binding timestamp is implausibly future")
    expected_binding = {
        "contract": BINDING_CONTRACT,
        "result": focused_result,
        "runMarker": {
            "bytes": len(marker_data),
            "sha256": hashlib.sha256(marker_data).hexdigest(),
        },
        "sourceInputs": focused_source,
        "testList": focused_list,
    }
    if binding != expected_binding:
        raise EvidenceError("focused carrier binding differs from current evidence")

    artifact_contracts = {
        "focusedBinding": (FOCUSED_BINDING_RELATIVE_PATH, RESULT_MAX_BYTES),
        "focusedConsole": (FOCUSED_CONSOLE_RELATIVE_PATH, CONSOLE_MAX_BYTES),
        "focusedRunMarker": (FOCUSED_RUN_MARKER_RELATIVE_PATH, RESULT_MAX_BYTES),
        "testList": (TEST_LIST_RELATIVE_PATH, TEST_LIST_MAX_BYTES),
    }
    artifacts = {
        key: current_file_record(relative, root=root, maximum_bytes=maximum)
        for key, (relative, maximum) in artifact_contracts.items()
    }
    return {
        "artifacts": artifacts,
        "binding": binding,
        "partition": partition,
        "sourceInputs": focused_source,
        "testList": focused_list,
    }


def expected_parent_payload(*, root: Path = ROOT) -> Mapping[str, object]:
    current_result = validate_result(root / RESULT_RELATIVE_PATH, root=root)
    discovered, _test_list_data = read_test_list(root=root)
    execution, _data, _mode, _mtime = load_canonical_json(
        root / EXECUTION_CONTRACT_RELATIVE_PATH,
        maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
        label="parent current execution contract",
    )
    focused = focused_child_evidence(
        root=root,
        discovered=discovered,
        execution=execution,
    )
    partition = focused["partition"]
    if type(partition) is not dict:
        raise EvidenceError("parent partition shape differs")
    artifacts_value = focused["artifacts"]
    if type(artifacts_value) is not dict:
        raise EvidenceError("focused artifact shape differs")
    artifacts = dict(artifacts_value)
    artifacts["currentResult"] = current_file_record(
        RESULT_RELATIVE_PATH,
        root=root,
        maximum_bytes=RESULT_MAX_BYTES,
    )

    current_artifacts = current_result["artifacts"]
    if type(current_artifacts) is not dict:
        raise EvidenceError("current child artifact shape differs")
    current_test_list = current_artifacts.get("testList")
    shared_test_list = artifacts["testList"]
    focused_test_list = focused["testList"]
    if (
        type(current_test_list) is not dict
        or type(focused_test_list) is not dict
        or type(shared_test_list) is not dict
    ):
        raise EvidenceError("child test-list record shape differs")
    for key in ("bytes", "sha256"):
        if (
            current_test_list.get(key) != shared_test_list.get(key)
            or focused_test_list.get(key) != shared_test_list.get(key)
        ):
            raise EvidenceError("children do not share exact test-list bytes")

    coverage_names = (
        "focusedCarrier",
        "focusedCarrierOverlap",
        "localSocketExecuted",
        "noSocketExecuted",
        "remaining",
        "reviewedExecuted",
    )
    coverage: dict[str, object] = {
        name: partition_snapshot(partition[name])
        for name in coverage_names
    }
    coverage["discovered"] = partition_snapshot(discovered)
    current_source = current_result["sourceInputs"]
    if type(current_source) is not dict:
        raise EvidenceError("current child source input shape differs")
    return {
        "artifacts": artifacts,
        "contract": PARENT_CONTRACT,
        "coverage": coverage,
        "execution": {
            "childSwiftInvocations": 2,
            "focusedCarrierExternalNetworkDenied": False,
            "focusedCarrierTests": FOCUSED_CARRIER_TEST_COUNT,
            "noSocketNetworkDenyProfile": NETWORK_DENY_PROFILE,
            "sharedTestListBytes": True,
        },
        "limitations": PARENT_LIMITATIONS,
        "result": "passed",
        "schemaVersion": SCHEMA_VERSION,
        "sourceInputs": {
            "focusedCarrier": focused["sourceInputs"],
            "noSocket": current_source,
        },
    }


def validate_parent_document(
    document: object,
    *,
    expected: Mapping[str, object],
) -> None:
    row = require_mapping(
        document,
        {
            "artifacts",
            "contract",
            "coverage",
            "execution",
            "limitations",
            "result",
            "schemaVersion",
            "sourceInputs",
        },
        "current parent result",
    )
    if row["contract"] != PARENT_CONTRACT or row["result"] != "passed":
        raise EvidenceError("current parent identity or result differs")
    if require_exact_int(row["schemaVersion"], "parent schemaVersion") != 1:
        raise EvidenceError("current parent schema version differs")

    expected_coverage = expected["coverage"]
    if type(expected_coverage) is not dict:
        raise EvidenceError("internal parent coverage differs")
    coverage = require_mapping(
        row["coverage"], set(expected_coverage), "parent coverage"
    )
    for key, expected_record in expected_coverage.items():
        if type(expected_record) is not dict:
            raise EvidenceError("internal parent partition record differs")
        validate_partition_record(
            coverage[key],
            expected_tests=expected_record["tests"],
            expected_sha256=expected_record["manifestSha256"],
            label=f"parent coverage.{key}",
        )

    execution = require_mapping(
        row["execution"],
        {
            "childSwiftInvocations",
            "focusedCarrierExternalNetworkDenied",
            "focusedCarrierTests",
            "noSocketNetworkDenyProfile",
            "sharedTestListBytes",
        },
        "parent execution",
    )
    if require_exact_int(
        execution["childSwiftInvocations"], "parent childSwiftInvocations"
    ) != 2:
        raise EvidenceError("parent child invocation count differs")
    if require_exact_int(
        execution["focusedCarrierTests"], "parent focusedCarrierTests"
    ) != FOCUSED_CARRIER_TEST_COUNT:
        raise EvidenceError("parent focused carrier count differs")
    require_bool(
        execution["focusedCarrierExternalNetworkDenied"],
        False,
        "parent focusedCarrierExternalNetworkDenied",
    )
    require_bool(
        execution["sharedTestListBytes"],
        True,
        "parent sharedTestListBytes",
    )
    if execution["noSocketNetworkDenyProfile"] != NETWORK_DENY_PROFILE:
        raise EvidenceError("parent no-socket network profile differs")

    limitations = require_mapping(
        row["limitations"], set(PARENT_LIMITATIONS), "parent limitations"
    )
    for key, value in PARENT_LIMITATIONS.items():
        require_bool(limitations[key], value, f"parent limitations.{key}")

    expected_sources = expected["sourceInputs"]
    if type(expected_sources) is not dict:
        raise EvidenceError("internal parent source inputs differ")
    sources = require_mapping(
        row["sourceInputs"], {"focusedCarrier", "noSocket"}, "parent sources"
    )
    for key in ("focusedCarrier", "noSocket"):
        validate_source_inputs(
            sources[key],
            expected=expected_sources[key],
            label=f"parent sourceInputs.{key}",
        )

    expected_artifacts = expected["artifacts"]
    if type(expected_artifacts) is not dict:
        raise EvidenceError("internal parent artifacts differ")
    artifacts = require_mapping(
        row["artifacts"], set(expected_artifacts), "parent artifacts"
    )
    for key, expected_record in expected_artifacts.items():
        validate_artifact_record(
            artifacts[key],
            expected=expected_record,
            label=f"parent artifacts.{key}",
        )
    if row != expected:
        raise EvidenceError("current parent result differs from reconstructed bytes")


def validate_parent_result(
    result_path: Path,
    *,
    root: Path = ROOT,
) -> Mapping[str, object]:
    validate_static_contract()
    document, data, mode, parent_mtime = load_canonical_json(
        result_path,
        maximum_bytes=RESULT_MAX_BYTES,
        label="current parent result",
    )
    if result_path == root / PARENT_RESULT_RELATIVE_PATH:
        if mode != 0o600:
            raise EvidenceError("canonical parent result mode must be 0600")
        child_mtimes = []
        for relative, maximum in (
            (RESULT_RELATIVE_PATH, RESULT_MAX_BYTES),
            (FOCUSED_BINDING_RELATIVE_PATH, RESULT_MAX_BYTES),
        ):
            _bytes, _mode, mtime = stable_regular_bytes(
                root / relative,
                maximum_bytes=maximum,
                label=f"parent chronology {relative.as_posix()}",
            )
            child_mtimes.append(mtime)
        if parent_mtime <= max(child_mtimes):
            raise EvidenceError("canonical parent must postdate both child results")
        if parent_mtime > time.time_ns() + FUTURE_MTIME_TOLERANCE_NS:
            raise EvidenceError("canonical parent timestamp is implausibly future")
    expected = expected_parent_payload(root=root)
    validate_parent_document(document, expected=expected)
    if data != canonical_json_bytes(expected):
        raise EvidenceError("current parent bytes differ")
    final_expected = expected_parent_payload(root=root)
    if final_expected != expected:
        raise EvidenceError("parent evidence changed during complete readback")
    return document


def self_test() -> None:
    validate_static_contract()
    try:
        require_exact_int(True, "boolean regression")
    except EvidenceError:
        pass
    else:
        raise EvidenceError("exact integer validator accepted Boolean")
    try:
        json.loads(b'{"a":1,"a":2}\n', object_pairs_hook=reject_duplicate_keys)
    except DuplicateKeyError:
        pass
    else:
        raise EvidenceError("duplicate-key validator accepted duplicate JSON")
    identities, _data = read_test_list(root=ROOT)
    if len(identities) != DISCOVERED_TEST_COUNT:
        raise EvidenceError("self-test discovery count differs")
    if len(read_v5_tests(root=ROOT)) != V5_TEST_COUNT:
        raise EvidenceError("self-test V5 identity count differs")
    if len(read_v6_tests(root=ROOT)) != V6_TEST_COUNT:
        raise EvidenceError("self-test V6 identity count differs")
    if len(read_v7_tests(root=ROOT)) != V7_TEST_COUNT:
        raise EvidenceError("self-test V7 identity count differs")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--parent", type=Path)
    parser.add_argument("result", nargs="?", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.self_test:
            if arguments.result is not None or arguments.parent is not None:
                raise EvidenceError("result paths are not valid with --self-test")
            self_test()
            print(
                "G7 current-run independent checker self-test passed: "
                f"{DISCOVERED_TEST_COUNT} discovery identities."
            )
            return 0
        if arguments.parent is not None:
            if arguments.result is not None:
                raise EvidenceError("positional result is not valid with --parent")
            validate_parent_result(arguments.parent)
            print(
                "G7 current parent independent readback passed: "
                f"{PARENT_REVIEWED_TEST_COUNT}/{DISCOVERED_TEST_COUNT} "
                "reviewed current-source tests; canonical G7 remains open."
            )
            return 0
        result_path = (
            arguments.result
            if arguments.result is not None
            else ROOT / RESULT_RELATIVE_PATH
        )
        validate_result(result_path)
    except EvidenceError as error:
        print(f"G7 current-run independent readback failed: {error}", file=sys.stderr)
        return 1
    print(
        "G7 current-run independent readback passed: "
        f"{SELECTED_TEST_COUNT}/{DISCOVERED_TEST_COUNT} current-source tests; "
        "canonical G7 remains open."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
