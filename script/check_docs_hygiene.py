#!/usr/bin/env python3
"""Check current docs for stale product-boundary wording."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import errno
import hashlib
import json
import os
import re
import runpy
import stat
import sys

if __package__:
    from script import (
        check_macos_build24_idle_resource_stability_evidence
        as idle_resource_evidence,
    )
    from script import package_release_artifacts
    from script import (
        run_clean_release_reproducibility
        as clean_release_reproducibility,
    )
    from script.check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )
else:
    import check_macos_build24_idle_resource_stability_evidence as idle_resource_evidence
    import package_release_artifacts
    import run_clean_release_reproducibility as clean_release_reproducibility
    from check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
PHYSICAL_QR_OBSERVATION_MANIFEST = (
    ROOT / "docs/evidence/physical-qr-pairing-20260719.json"
)
OLLAMA_MULTILINGUAL_FULL_MATRIX_V3_RESULT = (
    ROOT
    / "docs"
    / "evidence"
    / "ollama-embedding-multilingual-full-matrix-v3.json"
)
LOCAL_RELEASE_MARKETING_VERSION = "1.0.0"
LOCAL_RELEASE_BUILD_NUMBER = 24
CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION = 4
LOCAL_RELEASE_ID = (
    f"aetherlink-{LOCAL_RELEASE_MARKETING_VERSION}"
    f"+{LOCAL_RELEASE_BUILD_NUMBER}-local-v1"
)


@dataclass(frozen=True)
class G6ReproducibilityArchiveContract:
    source_file_count: int
    source_sha256: str
    overlay_sha256: str
    archive_size: int
    archive_sha256: str
    manifest_sha256: str
    checksum_sha256: str
    protected_archive_identity_sha256: str


@dataclass(frozen=True)
class G6ReproducibilityResultContract:
    label: str
    path: Path
    size: int
    sha256: str
    source_root_policy: str
    build_a_root_utf8_length: int
    build_b_root_utf8_length: int
    source_root_lengths_differ: bool


@dataclass(frozen=True)
class G6LifecycleEvidenceFileContract:
    role: str
    path: Path
    size: int
    sha256: str


LOCAL_RELEASE_CURRENT_DOC = (
    ROOT
    / "docs/releases/"
    f"{LOCAL_RELEASE_MARKETING_VERSION}-build-"
    f"{LOCAL_RELEASE_BUILD_NUMBER}-local-v1.md"
)
HISTORICAL_BUILD20_RELEASE_DOC = (
    ROOT / "docs/releases/1.0.0-build-20-local-v1.md"
)
HISTORICAL_BUILD20_RELEASE_DOCUMENT_SHA256 = (
    "fd0082f3bbc6922e25cd490d32c7b0c82e4b7ffd1e622f9951cc63813f8d1615"
)
HISTORICAL_RELEASE_DOCUMENT_SHA256_BY_BUILD = {
    22: "e974eb61b8949d18a894a0f06941480640dca722a12c4d5f70695244beae7724",
    23: "284bfcdfcf60911d1acc0e0835e2d1386d80903d99f7652dceb3936f58423cc6",
}
LATEST_RECORDED_GIT_REFRESH_HEAD = (
    "7d72147528e334edb19b9331ed7933ac71ca424b"
)
LATEST_RECORDED_GIT_REFRESH_LABEL = "2026-07-31 00:03 KST"
LOCAL_RELEASE_FIXTURE_BUILD_NUMBER = 3
LOCAL_RELEASE_FIXTURE_ID = (
    f"aetherlink-{LOCAL_RELEASE_MARKETING_VERSION}"
    f"+{LOCAL_RELEASE_FIXTURE_BUILD_NUMBER}-local-v1"
)
LOCAL_RELEASE_FIXTURE_DOC = (
    ROOT / "docs/releases/1.0.0-build-3-local-v1.md"
)
LOCAL_RELEASE_FIXTURE_READBACK_COMMAND = (
    "python3 script/check_release_artifact_archive.py \\\n"
    "  --archive-dir dist/releases/aetherlink-1.0.0+3-local-v1 \\\n"
    "  --historical"
)
# Backward-compatible fixture handle for the focused fixture-mutation tests.
LOCAL_RELEASE_DOC = LOCAL_RELEASE_FIXTURE_DOC
LOCAL_RELEASE_ARCHIVE_DIR = ROOT / "dist/releases" / LOCAL_RELEASE_ID
LOCAL_RELEASE_REPRODUCIBILITY_RESULT = (
    ROOT
    / "dist/reproducibility/"
    f"{LOCAL_RELEASE_ID}-two-root-v4.json"
)
LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT = (
    ROOT
    / "dist/reproducibility/"
    f"{LOCAL_RELEASE_ID}-two-root-v4-prepublication.json"
)
CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT = (
    ROOT
    / "dist/reproducibility/"
    / (
        f"{LOCAL_RELEASE_ID}-two-root-v4-prepublication-current-source-"
        "g6-macos-unsealed-gate-source-binding-one.json"
    )
)
CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT_SIZE = 19_645
CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT_SHA256 = (
    "b4581b21f5626f111f0d8cd7ef6858899c01ba366de23e1c667912497e93ece3"
)
CURRENT_SOURCE_G6_SOURCE_FILE_COUNT = 266
CURRENT_SOURCE_G6_SOURCE_SHA256 = (
    "63eeefbd7d13bf86452f39fc69337246f8a7ed0b945b5793f7f3ed33f3974c42"
)
CURRENT_SOURCE_G6_OVERLAY_SHA256 = (
    "cf674143e321be2db26d1ea3b70c15dc05c6aed2182acb25e584b8da06256de6"
)
CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SIZE = 167_086_118
CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SHA256 = (
    "cabc9dc622d55d3c3217a4542fd072b5884e49c717621fcfbc96b2f9f5b17037"
)
CURRENT_SOURCE_G6_REPRODUCIBLE_MANIFEST_SHA256 = (
    "96505c31782a5fc4f10544a0e18ca8db8019528f5d78caed9eaf2463725c33a9"
)
CURRENT_SOURCE_G6_REPRODUCIBLE_CHECKSUM_SHA256 = (
    "9e5bf156e16d87f428d3de7484deebc29370e6fc0f920300850b547f4a19b11d"
)
CURRENT_SOURCE_G6_PROTECTED_ARCHIVE_IDENTITY_SHA256 = (
    "df16cc1c38a414fa0c8e09eb3954645c34ba42aba21060ca6ad5710e4b47a4f6"
)
CURRENT_SOURCE_G6_REPRODUCIBILITY_ARCHIVE_CONTRACT = (
    G6ReproducibilityArchiveContract(
        source_file_count=CURRENT_SOURCE_G6_SOURCE_FILE_COUNT,
        source_sha256=CURRENT_SOURCE_G6_SOURCE_SHA256,
        overlay_sha256=CURRENT_SOURCE_G6_OVERLAY_SHA256,
        archive_size=CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SIZE,
        archive_sha256=CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SHA256,
        manifest_sha256=CURRENT_SOURCE_G6_REPRODUCIBLE_MANIFEST_SHA256,
        checksum_sha256=CURRENT_SOURCE_G6_REPRODUCIBLE_CHECKSUM_SHA256,
        protected_archive_identity_sha256=(
            CURRENT_SOURCE_G6_PROTECTED_ARCHIVE_IDENTITY_SHA256
        ),
    )
)
CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT_CONTRACT = (
    G6ReproducibilityResultContract(
        label="recorded lifecycle parent",
        path=CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT,
        size=CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT_SIZE,
        sha256=CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT_SHA256,
        source_root_policy="distinct-unequal-utf8-byte-length-v1",
        build_a_root_utf8_length=101,
        build_b_root_utf8_length=109,
        source_root_lengths_differ=True,
    )
)

CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_ARCHIVE_CONTRACT = (
    G6ReproducibilityArchiveContract(
        source_file_count=266,
        source_sha256=(
            "eefe8cbf522afd152529b3b4b0ee6862616e832e7e4a8f29c268434b783a7ce6"
        ),
        overlay_sha256=(
            "b63123aef04182da7ae7192495d92487a3b5c7957fbbc271dc2e82f63c763651"
        ),
        archive_size=167_086_073,
        archive_sha256=(
            "a4a3615717ac4786086220e5894d2c196d70e31f03892c2fc7e609ede4e50274"
        ),
        manifest_sha256=(
            "22f63e62a39c4f1a2f4ec377dc45703afc37bfb38dcc45b01102af693e6d1f50"
        ),
        checksum_sha256=(
            "1eaf24633eb3e8993768c2d4c5a4c1d234b12a8782008bc7c3a700b9911738ea"
        ),
        protected_archive_identity_sha256=(
            CURRENT_SOURCE_G6_PROTECTED_ARCHIVE_IDENTITY_SHA256
        ),
    )
)
CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS = (
    G6ReproducibilityResultContract(
        label="same-physical-root",
        path=(
            ROOT
            / "dist/reproducibility/"
            / (
                f"{LOCAL_RELEASE_ID}-swift-root-diagnostic-v1-"
                "same-physical-root.json"
            )
        ),
        size=19_648,
        sha256=(
            "c10b20231d7b8cc7a2bf5cfd325c97f831b64e167c0491641be34b20d3746e85"
        ),
        source_root_policy="same-physical-root-sequential-clean-v1",
        build_a_root_utf8_length=104,
        build_b_root_utf8_length=104,
        source_root_lengths_differ=False,
    ),
    G6ReproducibilityResultContract(
        label="distinct-equal-utf8-length",
        path=(
            ROOT
            / "dist/reproducibility/"
            / (
                f"{LOCAL_RELEASE_ID}-swift-root-diagnostic-v1-"
                "distinct-equal-utf8-length.json"
            )
        ),
        size=19_644,
        sha256=(
            "85255949ed10573c550155779c6d47545f68cd2c95cb0380466b8f489ca6c740"
        ),
        source_root_policy="distinct-equal-utf8-byte-length-v1",
        build_a_root_utf8_length=101,
        build_b_root_utf8_length=101,
        source_root_lengths_differ=False,
    ),
    G6ReproducibilityResultContract(
        label="distinct-unequal-utf8-length",
        path=(
            ROOT
            / "dist/reproducibility/"
            / (
                f"{LOCAL_RELEASE_ID}-swift-root-diagnostic-v1-"
                "distinct-unequal-utf8-length.json"
            )
        ),
        size=19_656,
        sha256=(
            "0e7fd34a6e4a4f477a8420c9f536a22008318501245f8b0ac4acd03ee08606b0"
        ),
        source_root_policy=(
            "diagnostic-distinct-unequal-utf8-byte-length-v1"
        ),
        build_a_root_utf8_length=101,
        build_b_root_utf8_length=109,
        source_root_lengths_differ=True,
    ),
    G6ReproducibilityResultContract(
        label="distinct-unequal-utf8-length-repeat-two",
        path=(
            ROOT
            / "dist/reproducibility/"
            / (
                f"{LOCAL_RELEASE_ID}-swift-root-diagnostic-v1-"
                "distinct-unequal-utf8-length-repeat-two.json"
            )
        ),
        size=19_656,
        sha256=(
            "0e7fd34a6e4a4f477a8420c9f536a22008318501245f8b0ac4acd03ee08606b0"
        ),
        source_root_policy=(
            "diagnostic-distinct-unequal-utf8-byte-length-v1"
        ),
        build_a_root_utf8_length=101,
        build_b_root_utf8_length=109,
        source_root_lengths_differ=True,
    ),
)
CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL = (
    "current-source-g6-swift-root-matrix-lifecycle-two"
)
CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT = (
    ROOT
    / "dist/reproducibility/"
    / (
        f"{LOCAL_RELEASE_ID}-two-root-v4-prepublication-"
        f"{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
    )
)
CURRENT_SOURCE_G6_LIFECYCLE_TWO_ARCHIVE_CONTRACT = (
    G6ReproducibilityArchiveContract(
        source_file_count=266,
        source_sha256=(
            "eefe8cbf522afd152529b3b4b0ee6862616e832e7e4a8f29c268434b783a7ce6"
        ),
        overlay_sha256=(
            "ee81fd795de1728dd483f44af5afaa839bc95e61e401b4ba3bbc41925cb0fd06"
        ),
        archive_size=167_086_073,
        archive_sha256=(
            "a4a3615717ac4786086220e5894d2c196d70e31f03892c2fc7e609ede4e50274"
        ),
        manifest_sha256=(
            "22f63e62a39c4f1a2f4ec377dc45703afc37bfb38dcc45b01102af693e6d1f50"
        ),
        checksum_sha256=(
            "1eaf24633eb3e8993768c2d4c5a4c1d234b12a8782008bc7c3a700b9911738ea"
        ),
        protected_archive_identity_sha256=(
            CURRENT_SOURCE_G6_PROTECTED_ARCHIVE_IDENTITY_SHA256
        ),
    )
)
CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT_CONTRACT = (
    G6ReproducibilityResultContract(
        label="current lifecycle-two parent",
        path=CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT,
        size=19_645,
        sha256=(
            "984e8baef1a332a0ee67cb7cabdbf196f875b9c5837ce3444dbfa801a907b43b"
        ),
        source_root_policy="distinct-unequal-utf8-byte-length-v1",
        build_a_root_utf8_length=101,
        build_b_root_utf8_length=109,
        source_root_lengths_differ=True,
    )
)
CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS = (
    clean_release_reproducibility.LaneALocalDMGSuitePaths(
        install=(
            ROOT
            / "dist/lifecycle"
            / (
                f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-"
                f"install-v2-{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
            )
        ),
        uninstall_reinstall=(
            ROOT
            / "dist/lifecycle"
            / (
                f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-"
                "uninstall-reinstall-v1-"
                f"{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
            )
        ),
        state_recovery=(
            ROOT
            / "dist/lifecycle"
            / (
                f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-"
                "uninstall-reinstall-state-recovery-v1-"
                f"{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
            )
        ),
        abrupt_process_state_recovery=(
            ROOT
            / "dist/lifecycle"
            / (
                f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-"
                "uninstall-reinstall-abrupt-process-state-recovery-v1-"
                f"{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
            )
        ),
        abrupt_process_state_recovery_repeatability=(
            ROOT
            / "dist/lifecycle"
            / (
                f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-"
                "uninstall-reinstall-abrupt-process-state-recovery-"
                "repeatability-v1-"
                f"{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
            )
        ),
        idle_resource_stability=(
            ROOT
            / "dist/lifecycle"
            / (
                f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-idle-resource-"
                f"stability-v1-{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
            )
        ),
    )
)
CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS = (
    G6LifecycleEvidenceFileContract(
        role="install",
        path=CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS.install,
        size=3_038,
        sha256=(
            "16d1bde4bb4499303ff2f7b114848c57e1163ef36c8b86ef9d001333e1334cde"
        ),
    ),
    G6LifecycleEvidenceFileContract(
        role="uninstall_reinstall",
        path=CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS.uninstall_reinstall,
        size=3_485,
        sha256=(
            "8fdb6f9dc7f41dda4d0083dea6fb6bb45644dd4560d9a98ecacb75d3836b8136"
        ),
    ),
    G6LifecycleEvidenceFileContract(
        role="state_recovery",
        path=CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS.state_recovery,
        size=4_996,
        sha256=(
            "a4cf9d0fcd0164fb5193f36e084110492488a50643ace63ce7f021a522b89b5a"
        ),
    ),
    G6LifecycleEvidenceFileContract(
        role="abrupt_process",
        path=(
            CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS
            .abrupt_process_state_recovery
        ),
        size=7_200,
        sha256=(
            "a1beb69b55c7c0cc909d72d4e36b8620585ad2e13e60f26c26332529a4abee3f"
        ),
    ),
    G6LifecycleEvidenceFileContract(
        role="abrupt_receipt",
        path=(
            CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS
            .abrupt_process_state_recovery_repeatability
        ),
        size=994,
        sha256=(
            "8f5a97a10e5d1c267fa9fee45cba57237f5ffdb72d8ad834df01fc86ed8e77b2"
        ),
    ),
    G6LifecycleEvidenceFileContract(
        role="idle",
        path=CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS.idle_resource_stability,
        size=22_399,
        sha256=(
            "02141c8e8e734417e359d566c656af87911146d9c0e1b9c01c382dd3fc2b9b66"
        ),
    ),
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT = (
    ROOT
    / "dist/lifecycle/"
    / (
        f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-install-v2-"
        "current-source-g6-macos-unsealed-gate-source-binding-one.json"
    )
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT_SIZE = 3_038
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT_SHA256 = (
    "154e5fb9ae0b0cd9f07b6b34135bc6fab1ea36e61464f967995d58bf57e68e92"
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT = (
    ROOT
    / "dist/lifecycle/"
    / (
        f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-uninstall-"
        "reinstall-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json"
    )
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT_SIZE = 3_485
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT_SHA256 = (
    "4fb0fc1f48df89e600edebde7afaf78a372ffd7e417d31b788cdb6e7ef400306"
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    / (
        f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-uninstall-"
        "reinstall-state-recovery-v1-current-source-g6-macos-unsealed-"
        "gate-source-binding-one.json"
    )
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT_SIZE = 4_996
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT_SHA256 = (
    "9530e99b9597da098b70abed657b923c523cf67552e1f0c203fb3bd16e5e11c6"
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT = (
    ROOT
    / "dist/lifecycle/"
    / (
        f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-uninstall-"
        "reinstall-abrupt-process-state-recovery-v1-current-source-g6-"
        "macos-unsealed-gate-source-binding-one.json"
    )
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SIZE = 7_200
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SHA256 = (
    "fe5d2d843f69e12484bfe905b4789de5d85b5c400d83ab6bedd280f7fd00ed44"
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT = (
    ROOT
    / "dist/lifecycle/"
    / (
        f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-local-dmg-uninstall-"
        "reinstall-abrupt-process-state-recovery-repeatability-v1-"
        "current-source-g6-macos-unsealed-gate-source-binding-one.json"
    )
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT_SIZE = 1_001
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT_SHA256 = (
    "77d0d6477884bc5919ec9ee3babb8182a07bbb892f18a05eb8148b5c0db1f3a5"
)
CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT = (
    ROOT
    / "dist/lifecycle/"
    / (
        f"macos-{LOCAL_RELEASE_ID}-two-root-lane-a-idle-resource-"
        "stability-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json"
    )
)
CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT_SIZE = 22_399
CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT_SHA256 = (
    "fd06f7c618e86b3adfa57aec4966534b25347f9b984b0aef52206052cf1ce570"
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_START = (
    "<!-- aetherlink-current-source-g6-lifecycle-suite-v1:start -->"
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_END = (
    "<!-- aetherlink-current-source-g6-lifecycle-suite-v1:end -->"
)
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_BODY = """\
**Recorded predecessor G6 exact Lane-A DMG and idle-resource lifecycle-suite
handoff.** At its execution snapshot, the comparison-only run bound 266
release inputs at source SHA-256
`63eeefbd7d13bf86452f39fc69337246f8a7ed0b945b5793f7f3ed33f3974c42`
and execution overlay SHA-256
`cf674143e321be2db26d1ea3b70c15dc05c6aed2182acb25e584b8da06256de6`.
Its unequal 101- and 109-byte source roots produced the exact same
167,086,118-byte archive at SHA-256
`cabc9dc622d55d3c3217a4542fd072b5884e49c717621fcfbc96b2f9f5b17037`,
with a 15,200-byte manifest at
`96505c31782a5fc4f10544a0e18ca8db8019528f5d78caed9eaf2463725c33a9`
and a 99-byte checksum sidecar at
`9e5bf156e16d87f428d3de7484deebc29370e6fc0f920300850b547f4a19b11d`.
All archive/member equality flags are true and both difference lists are
empty. The exact 19,645-byte primary result is
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`b4581b21f5626f111f0d8cd7ef6858899c01ba366de23e1c667912497e93ece3`.

Only after exact A/B equality, the runner handed the materialized Lane-A
archive to the complete local-DMG and idle-resource lifecycle suite. The exact
3,038-byte install result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-install-v2-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`154e5fb9ae0b0cd9f07b6b34135bc6fab1ea36e61464f967995d58bf57e68e92`.
The exact 3,485-byte same-DMG uninstall/reinstall result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`4fb0fc1f48df89e600edebde7afaf78a372ffd7e417d31b788cdb6e7ef400306`.
The exact 4,996-byte state-recovery result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-state-recovery-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`9530e99b9597da098b70abed657b923c523cf67552e1f0c203fb3bd16e5e11c6`.
The exact 7,200-byte abrupt-process recovery result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`fe5d2d843f69e12484bfe905b4789de5d85b5c400d83ab6bedd280f7fd00ed44`.
Its exact 1,001-byte two-run repeatability receipt is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-repeatability-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`77d0d6477884bc5919ec9ee3babb8182a07bbb892f18a05eb8148b5c0db1f3a5`.
The exact 22,399-byte current-source idle-resource result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-idle-resource-stability-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`fd06f7c618e86b3adfa57aec4966534b25347f9b984b0aef52206052cf1ce570`.

The suite executed install, same-image removal/reinstall, and fixed-canary
state recovery before two independent abrupt-process cycles. Each abrupt cycle
persisted the fixed Runtime-chat canary, reinstalled from the same image, sent
`SIGKILL(9)` only to the exact owned child after a successful persistence
probe, observed exit code `-9`, reaped the process, found no remaining AppKit
process, and recovered the unchanged canary from a third graceful process.
The two 7,200-byte canonical results were byte-identical.

The final owned, sandboxed app received a 60,000 ms warm-up and 600,000 ms
observation with 120 samples at 5,000 ms intervals; maximum sample lateness was
79 ms. Open file descriptors stayed at baseline/final/maximum 4. Threads stayed
at baseline/final/maximum 3. Resident bytes stayed at
baseline/final/maximum 140,001,280. Every final and peak delta was zero.
The idle result binds the same 266-file source snapshot and the same
ten-file installed app tree of 21,356,326 bytes at SHA-256
`2596df8daa50f962ef776032a2487dd10d431b621f08d496d67b221fac0c9b64`.
It denied network access, confined writes to its temporary root, preserved
pre-existing applications, reaped only its owned child, and removed the
temporary root before publication.

The runner published six child results followed by the parent through one
create-only exclusive-rename transaction with owner-held parent-directory
leases, staging-file fsync, child-directory fsync, parent-last commit-marker
rename, parent-directory fsync, stable readback, and retained-staging
rollback/retry. Each lifecycle field
`archiveReadback.currentSourceCompared=false` means that the child exercise
performed archive-only validation. The documentation guard pins all seven
evidence files together and dynamically cross-binds every child release, ZIP,
manifest, checksum, archive-readback projection, installed tree, source
snapshot, repeatability identity, and recomputed idle summary to the parent
current-source Lane-A result. No lane archive was retained or published,
comparison-only release publication stayed disabled, and the protected Build
23 archive stayed unchanged.

A later full unequal-root lifecycle attempt failed its A/B exact comparator
before the atomic publication step. After the runner and its contracts were
strengthened, four retained comparison-only diagnostic result files recorded
the newer 266-file source snapshot at SHA-256
`eefe8cbf522afd152529b3b4b0ee6862616e832e7e4a8f29c268434b783a7ce6`
and overlay SHA-256
`b63123aef04182da7ae7192495d92487a3b5c7957fbbc271dc2e82f63c763651`.
The four exact JSON files are retained in the `dist/reproducibility/*-swift-root-diagnostic-v1-*.json` namespace.
The same-physical 104/104-byte-root result is 19,648 bytes at SHA-256
`c10b20231d7b8cc7a2bf5cfd325c97f831b64e167c0491641be34b20d3746e85`;
the distinct-equal 101/101-byte-root result is 19,644 bytes at SHA-256
`85255949ed10573c550155779c6d47545f68cd2c95cb0380466b8f489ca6c740`;
and both retained distinct-unequal 101/109-byte-root results are the same
19,656 bytes at SHA-256
`0e7fd34a6e4a4f477a8420c9f536a22008318501245f8b0ac4acd03ee08606b0`.
All eight recorded build entries identify the exact same 167,086,073-byte
archive at SHA-256
`a4a3615717ac4786086220e5894d2c196d70e31f03892c2fc7e609ede4e50274`,
15,200-byte manifest at
`22f63e62a39c4f1a2f4ec377dc45703afc37bfb38dcc45b01102af693e6d1f50`,
and 99-byte checksum sidecar at
`1eaf24633eb3e8993768c2d4c5a4c1d234b12a8782008bc7c3a700b9911738ea`;
their complete archive inventories match, every comparison flag is true, and
both difference lists are empty. The two unequal-root result files are exact
byte copies. Publication remained disabled, no lifecycle child was created,
and the protected Build 23 archive remained unchanged.

The retained current-source lifecycle-two successor then bound the same 266
release inputs at source SHA-256
`eefe8cbf522afd152529b3b4b0ee6862616e832e7e4a8f29c268434b783a7ce6`
and execution overlay SHA-256
`ee81fd795de1728dd483f44af5afaa839bc95e61e401b4ba3bbc41925cb0fd06`.
Both v4 two-root runs used the canonical unequal 101/109-byte geometry and
recorded the same 167,086,073-byte archive, 15,200-byte manifest, 99-byte
checksum, complete member inventory, and empty difference lists as the newer
diagnostic record. Its exact 19,645-byte parent is
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication-current-source-g6-swift-root-matrix-lifecycle-two.json`,
SHA-256
`984e8baef1a332a0ee67cb7cabdbf196f875b9c5837ce3444dbfa801a907b43b`.

Only after that exact A/B comparison, the retained suite recorded these six
create-only lifecycle children:

- 3,038-byte install result, SHA-256
  `16d1bde4bb4499303ff2f7b114848c57e1163ef36c8b86ef9d001333e1334cde`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-install-v2-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 3,485-byte uninstall/reinstall result, SHA-256
  `8fdb6f9dc7f41dda4d0083dea6fb6bb45644dd4560d9a98ecacb75d3836b8136`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 4,996-byte state-recovery result, SHA-256
  `a4cf9d0fcd0164fb5193f36e084110492488a50643ace63ce7f021a522b89b5a`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-state-recovery-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 7,200-byte abrupt-process recovery result, SHA-256
  `a1beb69b55c7c0cc909d72d4e36b8620585ad2e13e60f26c26332529a4abee3f`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 994-byte abrupt-process repeatability receipt, SHA-256
  `8f5a97a10e5d1c267fa9fee45cba57237f5ffdb72d8ad834df01fc86ed8e77b2`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-repeatability-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 22,399-byte idle-resource result, SHA-256
  `02141c8e8e734417e359d566c656af87911146d9c0e1b9c01c382dd3fc2b9b66`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-idle-resource-stability-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`.

The successor children cross-bind the parent archive, manifest, checksum,
source snapshot, and exact ten-file installed tree of 21,356,326 bytes at
SHA-256
`0dd6363420e79b90ffac38fdf9410cc109122800f071ca9e1e66bf579ea21145`.
The owned idle process completed a 60,000 ms warm-up and 600,000 ms observation
with 120 samples at 5,000 ms intervals and maximum lateness 84 ms. File
descriptors stayed at 4, threads at 3, and resident bytes at 140,296,192;
every recomputed final and peak delta was zero. The full documentation checker
reads and validates all six children before treating the parent as the commit
marker. It performs stable no-follow reads, pins all seven identities, reuses
the runner's closed lifecycle validators, and rereads the parent after
cross-binding. It does not invoke archive publication or physical-archive
validation.

The earlier failed lifecycle attempt remains failed and is not relabeled by
the diagnostic or successor records. Together, the retained records prove only
the exact predecessor lifecycle snapshot, the newer same-host four-file,
three-geometry comparison record, and this exact current-source parent+6
successor. They do not prove arbitrary future rerun repeatability or universal
source-root independence.
They also do not prove
in-flight transaction durability, power loss, kernel crash, OS restart,
arbitrary history or long soak, arbitrary cross-host or clean-machine
reproducibility, Finder/quarantine/Gatekeeper behavior, signed/notarized
distribution, automatic data cleanup, N/N-1 upgrade or rollback,
physical-device, provider, network, UI/accessibility, security, deployment, or
production qualification."""
MACOS_CLEAN_HOME_INSTALLED_APP_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-14-clean-home-install-v1.json"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-20-clean-home-install-v1.json"
)
MACOS_CLEAN_HOME_INSTALLED_APP_RUNNER = (
    ROOT / "script/run_macos_clean_home_installed_app_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_APP_TEST = (
    ROOT / "script/test_run_macos_clean_home_installed_app_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-14-clean-home-state-recovery-v1.json"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-clean-home-install-v1.json"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-clean-home-state-recovery-v1.json"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-local-dmg-install-v2.json"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER = (
    ROOT / "script/run_macos_local_dmg_install_smoke_v2.py"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_TEST = (
    ROOT / "script/test_run_macos_local_dmg_install_smoke_v2.py"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-v1.json"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER = (
    ROOT / "script/run_macos_local_dmg_uninstall_reinstall_smoke.py"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_TEST = (
    ROOT / "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
    "state-recovery-v1.json"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RUNNER = (
    ROOT
    / "script/"
    "run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_TEST = (
    ROOT
    / "script/"
    "test_run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
    "abrupt-process-state-recovery-v1.json"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RECEIPT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
    "abrupt-process-state-recovery-repeatability-v1.json"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RUNNER = (
    ROOT
    / "script/"
    "run_macos_local_dmg_uninstall_reinstall_"
    "abrupt_process_state_recovery_smoke.py"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_TEST = (
    ROOT
    / "script/"
    "test_run_macos_local_dmg_uninstall_reinstall_"
    "abrupt_process_state_recovery_smoke.py"
)
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_CHECKER = (
    ROOT / "script/check_macos_build24_lifecycle_evidence.py"
)
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_TEST = (
    ROOT / "script/test_check_macos_build24_lifecycle_evidence.py"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-to-23-to-24-"
    "isolated-reverse-version-readback-v1-current-source-g6-"
    "macos-release-byte-readback-two.json"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_RECEIPT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-to-23-to-24-"
    "isolated-reverse-version-readback-repeatability-v1-current-source-g6-"
    "macos-release-byte-readback-two.json"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER = (
    ROOT / "script/run_macos_isolated_reverse_version_readback_smoke.py"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER_TEST = (
    ROOT / "script/test_run_macos_isolated_reverse_version_readback_smoke.py"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER = (
    ROOT / "script/check_macos_isolated_reverse_version_readback_evidence.py"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER_TEST = (
    ROOT / "script/test_check_macos_isolated_reverse_version_readback_evidence.py"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-24-idle-resource-stability-v1.json"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RUNNER = (
    ROOT / "script/run_macos_build24_idle_resource_stability_smoke.py"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RUNNER_TEST = (
    ROOT / "script/test_run_macos_build24_idle_resource_stability_smoke.py"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_CHECKER = (
    ROOT / "script/check_macos_build24_idle_resource_stability_evidence.py"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_CHECKER_TEST = (
    ROOT
    / "script/test_check_macos_build24_idle_resource_stability_evidence.py"
)
CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER = (
    ROOT / "script/run_macos_isolated_uninstall_reinstall_smoke.py"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-20-local-dmg-install-v1.json"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER = (
    ROOT / "script/run_macos_local_dmg_install_smoke.py"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_TEST = (
    ROOT / "script/test_run_macos_local_dmg_install_smoke.py"
)
CURRENT_MACOS_ISOLATED_UPGRADE_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json"
)
CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-23-to-24-"
    "isolated-upgrade-repeatability-v1.json"
)
CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER = (
    ROOT / "script/run_macos_isolated_upgrade_smoke.py"
)
CURRENT_MACOS_ISOLATED_UPGRADE_TEST = (
    ROOT / "script/test_run_macos_isolated_upgrade_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER = (
    ROOT
    / "script/run_macos_clean_home_installed_state_recovery_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_TEST = (
    ROOT
    / "script/test_run_macos_clean_home_installed_state_recovery_smoke.py"
)
MACOS_PACKAGED_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-13-state-recovery-v1.json"
)
HISTORICAL_BUILD12_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-12-state-recovery-v1.json"
)
MACOS_PACKAGED_STATE_RECOVERY_RUNNER = (
    ROOT / "script/run_macos_packaged_app_state_recovery_smoke.py"
)
MACOS_PACKAGED_STATE_RECOVERY_TEST = (
    ROOT / "script/test_run_macos_packaged_app_state_recovery_smoke.py"
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
LOCAL_RELEASE_EXPECTED_ZIP_SIZE = 166_345_274
LOCAL_RELEASE_EXPECTED_ZIP_SHA256 = (
    "104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c"
)
LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE = 15_200
LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256 = (
    "eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b"
)
LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE = 99
LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256 = (
    "827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882"
)
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE = 20_353
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256 = (
    "08a176bed8abe4f4c62178fa13a939059d127ee3dee4352096bcc593177cea36"
)
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE = 19_645
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256 = (
    "64c21a8c345018e7fca552b1ff706ac5f9c1f19a349afb0090dae22466e9e3db"
)
LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_RELATIVE = (
    "dist/releases/aetherlink-1.0.0+23-local-v1"
)
LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256 = (
    "df16cc1c38a414fa0c8e09eb3954645c34ba42aba21060ca6ad5710e4b47a4f6"
)
HISTORICAL_BUILD18_RELEASE_ID = "aetherlink-1.0.0+18-local-v1"
HISTORICAL_BUILD18_ARCHIVE_SIZE = 165_615_149
HISTORICAL_BUILD18_ARCHIVE_SHA256 = (
    "46e9b4884aa97291832e98aa4116a969ac54a7f217548f84a46c50dfeb4a3872"
)
HISTORICAL_BUILD18_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD18_MANIFEST_SHA256 = (
    "0355cb648dc9e25db37c25aa97c286035baf1234e0353e33960c3ad01f1e2bed"
)
HISTORICAL_BUILD18_CHECKSUM_SIZE = 99
HISTORICAL_BUILD18_CHECKSUM_SHA256 = (
    "7ef07058256bfe453b998ef197c5a953c97b058140e086da6f47f412848460b1"
)
HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SIZE = 19_786
HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SHA256 = (
    "6d0a4921e7f1e750d8e828db4057869511a323871fd1f4b53cb2ec83603ebf1f"
)
HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SIZE = 19_785
HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SHA256 = (
    "abcb3619509acacb48f9102386f1762895fdf51f4b6afdc730e519067b4131d7"
)
HISTORICAL_BUILD18_SOURCE_FILE_COUNT = 243
HISTORICAL_BUILD18_SOURCE_SNAPSHOT_SHA256 = (
    "b894108c8ecfdf1a3a914a3bfa67a2c4cd1cbfa59010b6555d26f0be172863d1"
)
HISTORICAL_BUILD18_SOURCE_OVERLAY_SHA256 = (
    "c979f1353df37d6833caf9aa9f0c28f4bc172624ca017c44f1ba2ca89937ce95"
)
HISTORICAL_BUILD18_SOURCE_INVENTORY_SIZE = 47_275
HISTORICAL_BUILD18_SOURCE_INVENTORY_SHA256 = (
    "6292d43773e6d890e17bc878d2874c5f2808b0593174ae9c5dcac56afc75663a"
)
HISTORICAL_BUILD18_MACOS_UUID = "A16CB949-C7E9-3BD7-A1AB-AC5D0662437F"
HISTORICAL_BUILD18_INSTALLED_APP_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-18-clean-home-install-v1.json"
)
HISTORICAL_BUILD18_INSTALLED_APP_RESULT_SIZE = 2_250
HISTORICAL_BUILD18_INSTALLED_APP_RESULT_SHA256 = (
    "b2b88a6fdf1649eab05b94e73b9d5b7f47baaefc9e352da3de982409ce201f62"
)
HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-18-clean-home-state-recovery-v1.json"
)
HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_SIZE = 3_364
HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_SHA256 = (
    "4f5df0d7bf9b15a042bd4430da83019499d6d8b642c2780bef637f46d3e8ce3d"
)
HISTORICAL_BUILD19_RELEASE_ID = "aetherlink-1.0.0+19-local-v1"
HISTORICAL_BUILD19_ARCHIVE_SIZE = 165_617_111
HISTORICAL_BUILD19_ARCHIVE_SHA256 = (
    "d792b3ab39a32b0076c97e206c773845cb1081a477ae1f309395c91699432ec8"
)
HISTORICAL_BUILD19_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD19_MANIFEST_SHA256 = (
    "7379a910bf055813d02bc0ec9810dfee3443655d6c6e4d0f30e548a0cbe2a99a"
)
HISTORICAL_BUILD19_CHECKSUM_SIZE = 99
HISTORICAL_BUILD19_CHECKSUM_SHA256 = (
    "e4a5e593ecbe73e2db9ae6aa4633415635bcfd0c9a6c9386c69f5155fac76f76"
)
HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SIZE = 19_786
HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SHA256 = (
    "e4d041540c73083970a90f4001ec68362824fcd7012e476f57489f40db195fcc"
)
HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SIZE = 19_785
HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SHA256 = (
    "409272907289385d69509ab8f5f9b90911ab11b78deed405490ec823a5d90dca"
)
HISTORICAL_BUILD19_SOURCE_FILE_COUNT = 245
HISTORICAL_BUILD19_SOURCE_SNAPSHOT_SHA256 = (
    "1f38043525dc622bf839137e5da9bbcd4d3731403b3c32b62508da465655ffc5"
)
HISTORICAL_BUILD19_SOURCE_OVERLAY_SHA256 = (
    "8619f1a4dc6c8bf671e8c574c0ebbe6437fb1bf579b1fd9b3eeb67d838a96749"
)
HISTORICAL_BUILD19_SOURCE_INVENTORY_SIZE = 47_645
HISTORICAL_BUILD19_SOURCE_INVENTORY_SHA256 = (
    "8c9c6f861391f3f6ef47f115e527aab81a22e78c99529113048683d7b4366215"
)
HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SIZE = 2_250
HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SHA256 = (
    "a89291227bde1f9f15caa3743339f569e9f7c79380f8f3a70df0a0fe8388b159"
)
HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SIZE = 3_364
HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SHA256 = (
    "1c72536188ce71388319d068489f4c351521f33d5431af36e7acc5ff76bdb2b7"
)
HISTORICAL_BUILD20_RELEASE_ID = "aetherlink-1.0.0+20-local-v1"
HISTORICAL_BUILD20_ARCHIVE_SIZE = 165_617_269
HISTORICAL_BUILD20_ARCHIVE_SHA256 = (
    "cba5a6531c35725aef7a2a3bf8b25d2155833b31b216906c80f8349249f6edf1"
)
HISTORICAL_BUILD20_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD20_MANIFEST_SHA256 = (
    "c633bf2c2ccc9d007f08e73929eed3d7f6b247d08579fa3695bcbad04348c99d"
)
HISTORICAL_BUILD20_CHECKSUM_SIZE = 99
HISTORICAL_BUILD20_CHECKSUM_SHA256 = (
    "dd803b0bc3313d833b0cdd1b2044c96a0f5873496ecdae94c5a4079bb02feaed"
)
HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SIZE = 20_010
HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SHA256 = (
    "ca71f3ad64ea744275035891c5d41faae9778c6be4f1a6fbadac2c1cf2b59a1c"
)
HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SIZE = 19_571
HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SHA256 = (
    "ad7e9b6e5f52a76d5a65b52bab5138ad86eb019b7b89fa7ee29c51b89c7cef2c"
)
HISTORICAL_BUILD20_MACOS_UUID = "0AD0CBED-7293-3151-84D1-9BAF07654A93"
HISTORICAL_BUILD20_SOURCE_FILE_COUNT = 246
HISTORICAL_BUILD20_SOURCE_SNAPSHOT_SHA256 = (
    "22f14e60d522b2720660e41a645a3e9832dd723b8b93b147c51bbf6c9125998c"
)
HISTORICAL_BUILD20_SOURCE_OVERLAY_SHA256 = (
    "f5d3ef4601129d5cde4595c73157d07fe89a3efd9904b3b9c6002504a4583606"
)
HISTORICAL_BUILD20_PREPUBLICATION_SOURCE_OVERLAY_SHA256 = (
    "0fdd31c2e1fcccb3915335b1cfc87c9a3b18c3c1b200f27463687014efc9ddba"
)
HISTORICAL_BUILD20_SOURCE_INVENTORY_SIZE = 47_803
HISTORICAL_BUILD20_SOURCE_INVENTORY_SHA256 = (
    "cb2a13fbc7e441fbad4b5841ca30545bf38ee52f4d1e9be8dfaadfd5f892a1d4"
)
HISTORICAL_BUILD20_RUNTIME_CHAT_HELPER_IDENTITY = (
    11_570,
    "137bcf0cb948f2d82718ef8c6df52147be5a9f713dd6743bc377a9940bece951",
)
HISTORICAL_BUILD20_RUNTIME_CHAT_RUNNER_IDENTITY = (
    26_948,
    "d5a7b11cbed4a0e04f3617a8cce7f69b09f285c95c5825f7ea7f415a811fde53",
)
HISTORICAL_BUILD20_RUNTIME_CHAT_TEST_IDENTITY = (
    13_950,
    "2a9d1add3ac6343aeeeb0b746f1182dbba148321f214a74211fe59b19e888e61",
)
HISTORICAL_BUILD21_RELEASE_ID = "aetherlink-1.0.0+21-local-v1"
HISTORICAL_BUILD21_ARCHIVE_SIZE = 165_617_441
HISTORICAL_BUILD21_ARCHIVE_SHA256 = (
    "b7acd3eb6c4089306dd8e597eb9b952d8dc993535ec13de63099090f155ca9a6"
)
HISTORICAL_BUILD21_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD21_MANIFEST_SHA256 = (
    "d12ceb13b60cbd165c5007d65dfcb50eb522e6df574b4de777d8a09aed815c5f"
)
HISTORICAL_BUILD21_CHECKSUM_SHA256 = (
    "850145f90cdb3ecd1fac90b8623b42c15b0bc5b357c08f7b47cbdc1086163953"
)
HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SIZE = 20_010
HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SHA256 = (
    "b628ee84164ff7405e67520c2ca33d57aee19caad6875cbe61c361c2f3d7da70"
)
HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SIZE = 19_571
HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SHA256 = (
    "5267f145d8237c11fe5425a7148d62237fae942a6d8413eda7f0e9443a0d1c16"
)
HISTORICAL_BUILD21_SOURCE_FILE_COUNT = 247
HISTORICAL_BUILD21_SOURCE_SNAPSHOT_SHA256 = (
    "d948d5abfed0ccfe72429b46104e30847840dd11a2f7a2380d75a29c3d1763b4"
)
HISTORICAL_BUILD21_SOURCE_INVENTORY_SIZE = 47_975
HISTORICAL_BUILD21_SOURCE_INVENTORY_SHA256 = (
    "620262cae041102653b455ac01bc75ebc42dccaf342e10f59244db842055c57e"
)
HISTORICAL_BUILD21_MACOS_UUID = "0AD0CBED-7293-3151-84D1-9BAF07654A93"
HISTORICAL_BUILD14_MARKETING_VERSION = "1.0.0"
HISTORICAL_BUILD14_RELEASE_ID = "aetherlink-1.0.0+14-local-v1"
HISTORICAL_BUILD14_ARCHIVE_SHA256 = (
    "88769137aa024d193a27483522c1986d2d05acf3f03704e690b19b4c578629f4"
)
HISTORICAL_BUILD14_MANIFEST_SHA256 = (
    "e8f7f0ec0358f63bde6a03ff5d7ae50e08b14e530ebed4c5f962704894f8d914"
)
HISTORICAL_BUILD14_MACOS_UUID = "A16CB949-C7E9-3BD7-A1AB-AC5D0662437F"
HISTORICAL_BUILD16_RELEASE_ID = "aetherlink-1.0.0+16-local-v1"
HISTORICAL_BUILD16_ARCHIVE_SIZE = 165_515_492
HISTORICAL_BUILD16_ARCHIVE_SHA256 = (
    "81f89ba20db75fa542f5b4910c469b82d555be2835c1a6bbb66b8daf71d752e7"
)
HISTORICAL_BUILD16_RESULT_SIZE = 19_745
HISTORICAL_BUILD16_RESULT_SHA256 = (
    "b87208f330701f196b6645fa206e5e80e4d8f7367c81611381ed237fbaf5435d"
)
HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE = 20_976
HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256 = (
    "3e489daf520db42683df2852af3d8df917b8d8dd755e3bcda68d11be7090966b"
)
HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE = 20_976
HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256 = (
    "d86b0bbe803e90b0e844ccbae283e9711e50eb21ac4e8f3e94d485e263c4053e"
)
HISTORICAL_BUILD16_DOC = (
    ROOT / "docs/releases/1.0.0-build-16-local-v1.md"
)
HISTORICAL_BUILD16_RESULT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+16-local-v1-two-root-v2.json"
)
HISTORICAL_BUILD16_FAILED_ATTEMPT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+16-local-v1-two-root-v2-attempt1-failed.json"
)
HISTORICAL_BUILD16_FAILED_CONFIRMATION = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+16-local-v1-two-root-v2-confirmation.json"
)
HISTORICAL_BUILD17_BUILD_NUMBER = 17
HISTORICAL_BUILD17_RELEASE_ID = "aetherlink-1.0.0+17-local-v1"
HISTORICAL_BUILD17_ARCHIVE_SIZE = 165_515_496
HISTORICAL_BUILD17_ARCHIVE_SHA256 = (
    "ff7e68ffa33ce54a312e2874592528cec0227f3200679f9df6531c06ca32c64e"
)
HISTORICAL_BUILD17_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD17_MANIFEST_SHA256 = (
    "5077da6e0d4c806a5df2112f9eb70ff53064fde7e4faf308662df30564a5cc6e"
)
HISTORICAL_BUILD17_SOURCE_FILE_COUNT = 243
HISTORICAL_BUILD17_SOURCE_INVENTORY_SIZE = 47_275
HISTORICAL_BUILD17_SOURCE_INVENTORY_SHA256 = (
    "6c02c68a64639ade37d9102f62d1e277c4efea383bbd04b21d31996ff462580e"
)
HISTORICAL_BUILD17_SOURCE_SNAPSHOT_SHA256 = (
    "0f57cd63e1fe2c27cfc567df742fe47c6bcb79109630e8830d250f0bd94f9187"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_PATH = (
    "dist/reproducibility/"
    "aetherlink-1.0.0+17-local-v1-two-root-v2.json"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SIZE = 19_786
HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SHA256 = (
    "f2582c6b84d305f34fe4d737604717f5ea9721d6ab8b1125354cbc1798464296"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_PATH = (
    "dist/reproducibility/"
    "aetherlink-1.0.0+17-local-v1-two-root-v2-confirmation.json"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SIZE = 19_785
HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SHA256 = (
    "616d70882ec8f09c78f7a57730366924c2cc6de28844b7f2c8763ee125f2867a"
)
HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START = (
    "<!-- aetherlink-historical-build17-lifecycle-v1:start -->"
)
HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_END = (
    "<!-- aetherlink-historical-build17-lifecycle-v1:end -->"
)
HISTORICAL_BUILD17_INSTALLED_APP_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-17-clean-home-install-v1.json"
)
HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SIZE = 2_250
HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SHA256 = (
    "c04b13caf494ce7a07c5726e59208c14221578513a3bd554c786636afeaba355"
)
HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-17-clean-home-state-recovery-v1.json"
)
HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SIZE = 3_364
HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SHA256 = (
    "c81605c27312c3d0d99134f4c178bd884875e183ac62917378ef1e3f9b9cf180"
)
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE = 2_250
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256 = (
    "dba559878af78be5057b50f4fb5a759e0308724f93b6c358ce2c5e6981d7f6c2"
)
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256 = (
    "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29"
)
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256 = (
    "56127b93951ede623f3b30a4149d83305104841717cd84b0541a44b357e6b161"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE = 3_364
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "434cec7c2fd396a56788abdcfa48edd913950331cedf91159a11f8acc02f657d"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "3a77f1773c927c9a1d7714138cb283bb2eaee5c93243dd9f558a3ca39e5245b2"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE = 2_250
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256 = (
    "4ce047a318e47568d647e1167cbaeebc603626073e098451a29c949086aa3d72"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256 = (
    "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256 = (
    "55274ad4abc958d85c4df1193cfe1508d820768fbbe48eae71a4fee8c1c020aa"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE = 3_364
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "d12947e16e7b985515a90a13731947a5991bcd82a06039210e22bba43535bf0b"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "edfd6f89b2cecd6de5cbfcb337ba6f5643a8d74d7caf8735c467578488970664"
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START = (
    "<!-- aetherlink-historical-build20-lifecycle-v1:start -->"
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END = (
    "<!-- aetherlink-historical-build20-lifecycle-v1:end -->"
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_REPEATABILITY_CLAIM = (
    "Both clean-HOME runners were invoked twice and matched their canonical "
    "results."
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_BOUNDARY_CLAIM = (
    "These historical same-host, per-user Build 20 observations do not "
    "qualify a clean "
    "machine/account, signed/notarized distribution, "
    "UI/accessibility, live-provider behavior, a physical device, arbitrary "
    "histories, crash/power-loss, concurrent writers, backup/transfer, "
    "rollback, or production readiness."
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_BOUNDARY_TERMS = (
    "Build 20",
    "clean machine/account",
    "signed/notarized distribution",
    "UI/accessibility",
    "live-provider behavior",
    "arbitrary histories",
    "crash/power-loss",
    "backup/transfer",
    "rollback",
    "production readiness",
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE = 2_250
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256 = (
    "8646ff16bb5a152aab9c874c73a048a684d02e06fb3cbf7ed2f6172de51ff0c1"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256 = (
    "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256 = (
    "55274ad4abc958d85c4df1193cfe1508d820768fbbe48eae71a4fee8c1c020aa"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE = (
    3_364
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "d3205d662967d90d65baac6e5edc57bcc19c5f17c3963a1a3e53c95b07d44588"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "edfd6f89b2cecd6de5cbfcb337ba6f5643a8d74d7caf8735c467578488970664"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-clean-home-lifecycle-v1:start -->"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-clean-home-lifecycle-v1:end -->"
)
CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_BODY = """\
The current G6 non-security Build 24 clean-HOME lifecycle slice executes the
latest immutable archive under a temporary per-user HOME. The installed-app
runner copied the exact ten-file manifest-matched app, completed two distinct
LaunchServices processes, verified all three SQLite files, and kept empty
Runtime chat plus every regular state-file byte and mode stable across
relaunch. The canonical 2,250-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-clean-home-install-v1.json`,
SHA-256
`8646ff16bb5a152aab9c874c73a048a684d02e06fb3cbf7ed2f6172de51ff0c1`.

The state-recovery runner installed the same Build 24 tree, migrated one fixed
legacy Runtime-chat canary, removed the legacy source, and recovered the same
single SQLite row from a distinct SQLite-only relaunch. Both auxiliary
databases passed integrity checks, and the app tree plus remaining state bytes
and modes stayed unchanged. The canonical 3,364-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-clean-home-state-recovery-v1.json`,
SHA-256
`d3205d662967d90d65baac6e5edc57bcc19c5f17c3963a1a3e53c95b07d44588`.
The installed-app runner and test SHA-256 values are
`55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29`
and
`55274ad4abc958d85c4df1193cfe1508d820768fbbe48eae71a4fee8c1c020aa`;
the state-recovery runner and test SHA-256 values are
`9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a`
and
`edfd6f89b2cecd6de5cbfcb337ba6f5643a8d74d7caf8735c467578488970664`.

These result files are post-archive execution evidence and are not Build 24
archive members. They qualify only the recorded same-host, per-user,
temporary-HOME, local ad-hoc Build 24 installation, relaunch, and fixed-canary
state-recovery observations. They do not establish clean-machine/account or
DMG/Finder installation, signing/notarization, rollback, automatic data
cleanup, physical-device behavior, provider, network, UI, accessibility, or
production-release qualification."""
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE = 3_038
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256 = (
    "7d4c6ae7d892bc9d639cc8dfbe5dfb02e09ff7019ee8554f652556ba7b1bb964"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256 = (
    "2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256 = (
    "8b3cd5852c89735f2454cf4ae13d29024901dbbc7d915d37b4b3a58932558c91"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-local-dmg-lifecycle-v2:start -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-local-dmg-lifecycle-v2:end -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_BODY = """\
The current G6 non-security Build 24 local-DMG lifecycle slice copied the
retained ZIP, manifest, and checksum sidecar into one private snapshot.
Archive readback, extraction, DMG creation, and the full exercise used those
same bytes, which were rehashed unchanged afterward. The runner created an
ephemeral HFS+ UDZO image with an Applications alias, mounted it read-only at
one fresh path, copied the exact ten-file manifest tree with `ditto`, detached
it before launch, and verified that no mount remained.

Two distinct LaunchServices processes completed under a temporary per-user
HOME. All three SQLite files passed integrity checks, Runtime chat remained
empty, the runtime identity was present, and every regular app/state byte and
mode stayed stable. The canonical 3,038-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-install-v2.json`,
SHA-256
`7d4c6ae7d892bc9d639cc8dfbe5dfb02e09ff7019ee8554f652556ba7b1bb964`.
The v2 runner and ten-test module SHA-256 values are
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`
and
`8b3cd5852c89735f2454cf4ae13d29024901dbbc7d915d37b4b3a58932558c91`.
Its preserved DMG primitive runner and shared snapshot-helper runner SHA-256
values are
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

This result is post-archive execution evidence and is not a Build 24 archive
member. It qualifies only the recorded same-host, per-user, temporary-HOME,
local ad-hoc mount/copy/relaunch observation. It does not establish Finder
drag-and-drop, downloaded-image quarantine or Gatekeeper behavior, system
`/Applications`, a clean machine/account, TCC or Keychain behavior, signed,
notarized, or stapled distribution, UI/accessibility, provider, network,
physical-device, arbitrary-history, crash/power-loss, concurrent-writer,
backup/restore/transfer, upgrade, rollback, production, or security
qualification."""
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT_SIZE = (
    3_485
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT_SHA256 = (
    "1e0daba4015ae36c8d96f11c424eb08a02855d3caa2e27b7838229cd55af5649"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256 = (
    "300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_TEST_SHA256 = (
    "6e782fc128aad75b20f1b04752e4754ccbf8ceaadc9e2fcabe9cc2e537bfb703"
)
CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256 = (
    "36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-v1:"
    "start -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-v1:"
    "end -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_BODY = """\
The current G6 non-security Build 24 same-DMG uninstall/reinstall slice reused
one private archive snapshot and one ephemeral HFS+ UDZO image. It mounted the
same image bytes read-only at two distinct fresh mountpoints, copied the exact
ten-file manifest tree with `ditto` each time, detached before each launch, and
completed two distinct LaunchServices processes under one temporary per-user
HOME.

After each stopped launch, the runner removed only the exact temporary app
path. Across the first removal, same-image reinstall, second launch, and final
removal, Application Support, all three SQLite files, the runtime identity,
and every regular state-file byte and mode remained unchanged. Two complete
executions matched the same canonical 3,485-byte result at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-v1.json`,
SHA-256
`1e0daba4015ae36c8d96f11c424eb08a02855d3caa2e27b7838229cd55af5649`.
The runner and fifteen-test module SHA-256 values are
`300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae`
and
`6e782fc128aad75b20f1b04752e4754ccbf8ceaadc9e2fcabe9cc2e537bfb703`.
The reused snapshot-bound DMG, preserved DMG primitive, exact-uninstall, and
snapshot-helper runner SHA-256 values are, respectively,
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`,
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`,
`36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa`,
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

This result is post-archive execution evidence and is not a Build 24 archive
member. It qualifies only the recorded same-host, per-user, temporary-HOME,
same-created-image uninstall/reinstall observation. It does not establish
Finder or system `/Applications` installation, downloaded-image quarantine or
Gatekeeper behavior, signing/notarization/stapling, a clean machine/account,
automatic Application Support cleanup, upgrade, rollback, UI/accessibility,
provider, network, physical-device, production, or security qualification."""
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT_SIZE = (
    4_996
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "e3c030df6cb83586f7401de2162ac8aa14cb44fbb7c7ca05b3305d9bb4edf17e"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "31bdae72f08f1f68bc4a07cb59d194c943d56179acf0a7b149ddc2e652c68b4c"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "22ddc7ec39aa8c88c2b69f2dd8a390a287d85eeaff4704109784e221483faee2"
)
CURRENT_SOURCE_G6_LIFECYCLE_SUCCESSOR_SHA256_BY_PATH = {
    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER: (
        "51bf579539e33c516c468c8c1c78d12ffd2b79731a0f2ec3a93db9fd6639dc6c"
    ),
    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_TEST: (
        "291a36b2144c338e303cd98abafe57d466c7983b0b0a689ee75c7cddf444f32c"
    ),
    (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RUNNER
    ): "c73800b11d0409679fa01486e2b758ef2259c622eab315426e65e4566472bdcf",
    (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_TEST
    ): "44edebb6b6253fbc202e091d8546b64df83cf64ffad4a58786666e181205be92",
    (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RUNNER
    ): "e87ba92ef74f13f4c24a16b326fb29dd7055bf9c7abb60e4866c525a0891da9d",
    (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_TEST
    ): "c848d3d8a8ff79450fbaa1e38d422a3cafc947eac597db47c2f1d9239957d06a",
}
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-"
    "state-recovery-v1:start -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-"
    "state-recovery-v1:end -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_BODY = """\
The current G6 non-security Build 24 same-DMG state-recovery slice reused one
private archive snapshot and one ephemeral HFS+ UDZO image. The first
read-only mount installed the exact ten-file manifest tree. A distinct
LaunchServices process migrated the fixed 345-byte legacy Runtime-chat canary
to exactly one SQLite row, and the first exact app removal preserved the full
Application Support tree, including the legacy source, plus the runtime
identity without changing any regular-file byte or mode.

The harness then moved only that fixed legacy source into its temporary
preserved-fixture directory. A second fresh read-only mount of the same image
bytes reinstalled the identical app tree without touching the remaining
state. A distinct SQLite-only LaunchServices process read back the exact
344-byte event once; both auxiliary databases retained `integrity_check=ok`.
The second launch and final exact app removal preserved every remaining state
byte and mode. Two complete executions matched the same canonical 4,996-byte
result at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-state-recovery-v1.json`,
SHA-256
`e3c030df6cb83586f7401de2162ac8aa14cb44fbb7c7ca05b3305d9bb4edf17e`.
The runner and nine-test module SHA-256 values are
`31bdae72f08f1f68bc4a07cb59d194c943d56179acf0a7b149ddc2e652c68b4c`
and
`22ddc7ec39aa8c88c2b69f2dd8a390a287d85eeaff4704109784e221483faee2`.
The reused same-DMG, clean-HOME recovery, packaged-state recovery,
snapshot-bound DMG, DMG primitive, exact-uninstall, and snapshot-helper runner
SHA-256 values are, respectively,
`300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae`,
`9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a`,
`4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca`,
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`,
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`,
`36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa`,
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

The DMG, captured logs, and preserved legacy fixture were temporary and are
not retained evidence. The canonical JSON is post-archive execution evidence,
not a Build 24 archive member. It proves only the fixed non-empty canary under
the recorded same-host, per-user, temporary-HOME, same-created-image flow. It
does not prove automatic legacy or Application Support cleanup, arbitrary
histories, Finder or system `/Applications`, quarantine or Gatekeeper,
signing/notarization/stapling, clean-machine/account, upgrade, rollback,
UI/accessibility, provider, network, physical-device, production, or security
qualification."""
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SIZE = (
    7_200
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "0a7879ecea014123258a14d7f6f3790b7dc5859000941bf8faf76d2b12cb5124"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RECEIPT_SIZE = (
    921
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RECEIPT_SHA256 = (
    "98ec53d1018b0bebf88174a2fad514492b6ca1cff2afa1a6051e7335fabb3a36"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "ddd2c8286d1b78541d4ed18f125b9d1867be718e0276adb9880e60929fc15ec3"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "f06479f5eb4e12d3f0072e8259e9a7b1c28e8797a423ea88b092978a4142b658"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-local-dmg-abrupt-process-"
    "state-recovery-v1:start -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-local-dmg-abrupt-process-"
    "state-recovery-v1:end -->"
)
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_BODY = """\
The current G6 non-security Build 24 persisted-state abrupt-process recovery
slice reused one private archive snapshot and one ephemeral HFS+ UDZO image.
It read the retained Build 24 archive without consulting current source,
mounted the same image bytes read-only at two distinct fresh mountpoints,
copied the exact ten-file manifest tree with `ditto`, and detached before each
launch.

A first distinct LaunchServices process migrated the fixed 345-byte legacy
Runtime-chat canary to exactly one 344-byte SQLite event and exited through
bounded graceful termination. The first exact app removal preserved
Application Support and the runtime identity. The harness then moved only the
fixed legacy source into its temporary preserved-fixture directory, and a
second read-only mount of the same image reinstalled the identical app tree.

The runner launched that exact installed executable as a sandboxed owned child
in SQLite-only readback mode. Only after the exact 71-byte observation and an
independent persistence probe confirmed the committed canary and quiescent
state did it revalidate the executable identity, send `SIGKILL`, observe exit
code `-9`, reap that child, and prove its AppKit identity absent. The canary,
both auxiliary databases, runtime identity, app tree, and every recorded state
byte and mode remained unchanged immediately afterward. A third distinct
LaunchServices process then read back the same event once before final exact
app removal.

Two complete executions matched the same canonical 7,200-byte result at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-v1.json`,
SHA-256
`0a7879ecea014123258a14d7f6f3790b7dc5859000941bf8faf76d2b12cb5124`.
The separate 921-byte repeatability receipt at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-repeatability-v1.json`
has SHA-256
`98ec53d1018b0bebf88174a2fad514492b6ca1cff2afa1a6051e7335fabb3a36`
and binds two passed runs to those exact result bytes. The runner and
nineteen-test module SHA-256 values are
`ddd2c8286d1b78541d4ed18f125b9d1867be718e0276adb9880e60929fc15ec3`
and
`f06479f5eb4e12d3f0072e8259e9a7b1c28e8797a423ea88b092978a4142b658`.
The reused predecessor state-recovery, same-DMG, clean-HOME recovery,
packaged-state recovery, snapshot-bound DMG, DMG primitive, exact-uninstall,
and snapshot-helper runner SHA-256 values are, respectively,
`31bdae72f08f1f68bc4a07cb59d194c943d56179acf0a7b149ddc2e652c68b4c`,
`300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae`,
`9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a`,
`4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca`,
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`,
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`,
`36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa`,
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

The DMG, captured logs, and preserved legacy fixture were temporary and are
not retained evidence. Both JSON files are post-archive execution evidence,
not Build 24 archive members. The signal occurred only after the fixed canary
was committed and independently observed; this is not an in-flight
transaction, hot-journal fault, write-durability, power-loss, kernel-crash,
OS-restart, UI Force Quit, arbitrary-history, or soak result. It does not
qualify automatic state cleanup, Finder or system `/Applications`, quarantine
or Gatekeeper, signing/notarization/stapling, clean-machine/account, upgrade,
rollback, UI/accessibility, provider, network, physical-device, production, or
security behavior. The canonical G6 exit and every G7 exit tier remain
incomplete."""
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_CHECKER_SIZE = 80_890
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_CHECKER_SHA256 = (
    "05a9aea9388ff93cebfde53cf5c5dbd6e0034e01d7d58d28923f60c8f422d18e"
)
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_TEST_SIZE = 38_123
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_TEST_SHA256 = (
    "46b381dda17337709879f361aa9c4957a9b00cc0db69a1ce7cfb8a7ca3bd04fb"
)
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-macos-lifecycle-"
    "aggregate-readback-v1:start -->"
)
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-macos-lifecycle-"
    "aggregate-readback-v1:end -->"
)
CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_BODY = """\
The current Build 24 non-security macOS lifecycle aggregate is the standalone
read-only command
`python3 -I -B -S script/check_macos_build24_lifecycle_evidence.py`.
It opens and retains the repository root, eleven exact directories, and all 40
unique target regular-file descriptors before hashing any target. It then
streams the exact Build 23 and Build 24 archive, manifest, and checksum
sidecars; the terminal version ledger; seven current lifecycle results; two
repeatability receipts; and 25 source files. Final entry and directory-graph
readback must match the held initial identities.

Eight runner/test files that evolved after the evidence run are read from the
non-executable `docs/evidence/macos-build24-lifecycle-source-v1` snapshot. The
checker pins commit `38027523f65f97a81044555c2f42b020eada3436`, the exact
semantic-to-storage map, every byte identity, and the closed fixture directory
inventory, so current source cannot be relabeled as Build 24 evidence.

The checker independently rejects noncanonical or duplicate-key JSON,
non-exact integer, float, and boolean field types, wrong top-level schemas,
release or app-tree drift, reversed Build 23-to-24 direction, weakened
limitations, and receipt/result mismatch. It imports and executes no lifecycle
runner and performs no subprocess, image mount, app launch, file write,
network, device, or Git operation. The 12 exact focused unit modules remain
byte-bound inputs but are deliberately not executed by this static checker.

The standalone readback passed. A separate exact invocation of those 12
non-security unit modules passed 169 tests, and the aggregate checker's own 24
mutation and boundary tests passed. The 80,890-byte checker has SHA-256
`05a9aea9388ff93cebfde53cf5c5dbd6e0034e01d7d58d28923f60c8f422d18e`;
the 38,123-byte test module has SHA-256
`46b381dda17337709879f361aa9c4957a9b00cc0db69a1ce7cfb8a7ca3bd04fb`.

This gate publishes or rewrites no lifecycle result and creates no new install,
launch, DMG, upgrade, recovery, or repeatability observation. Build 23 remains
a retained historical predecessor, not a declared rollback lineage. The pass
is bounded static/no-device consistency evidence and preparation for a future
G7 deterministic check; it is not canonical G7 PR-fast completion and does
not complete the signed, physical-device, network, rollback, production, or
other remaining G6/G7 exit requirements."""
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RESULT_SIZE = 7_859
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RESULT_SHA256 = (
    "dbaa422de18ab37e9f4b92d7e78631fad9719e6c6d41fe30ccb402365267d416"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RECEIPT_SIZE = 1_266
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RECEIPT_SHA256 = (
    "818474ea0469e10f836c237ef3d8cab3ec95ffd5da6299c13ea730982ff08a80"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SIZE = 44_003
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SHA256 = (
    "e22a3e32e0556428f1d0274a75b4bbe93c5f5d28fe1a60607e1537a3db1771b1"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SIZE = 31_118
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SHA256 = (
    "41aadb2c9e2e961b9934ebac284df0a4f9b60f7b6fa4d02992b50775da47647b"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SIZE = 31_402
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SHA256 = (
    "a6ef39ea10c314e756b2f92ad4ec07474da4f92bddb817a867acee2b33808b84"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SIZE = 15_942
CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SHA256 = (
    "019e0ae415b77cbd3458c3bb98a2107f0218b3a76df661f9fadb99843cbacb40"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-reverse-version-readback-v1:start -->"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-reverse-version-readback-v1:end -->"
)
CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_BODY = """\
**Latest current execution-source successor over the preserved
Build 24-to-23-to-24 archives.** Two
independent same-host executions used private snapshots of the exact local
ad-hoc Build 24 and historical Build 23 ZIP, manifest, and checksum sidecars.
Each execution installed Build 24 under one temporary per-user HOME, created
one fixed non-security Runtime-chat canary through the test-only fixture path,
removed the exact app, read the unchanged state with Build 23, removed that
exact app, and read the same state again with Build 24.

Every installed tree matched its archive manifest. The Build 23 tree contained
10 regular files totaling 21,153,014 bytes at SHA-256
`31209251804494f54a699c5c4e8101491f02fca881cf25fba379b88eb493d8a8`;
both Build 24 installations contained 10 regular files totaling 21,151,910
bytes at SHA-256
`0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff`.
No stale bundle file remained after either exact-path replacement. Each run
used three distinct owned LaunchServices processes and confirmed that each was
gone before continuing. The fixed canary remained exactly once, all three
SQLite files passed integrity checks, and every retained state-file byte and
mode remained unchanged through all three installations and removals.

The two executions produced the same canonical 7,859-byte result at
`dist/lifecycle/macos-packaged-app-build-24-to-23-to-24-isolated-reverse-version-readback-v1-current-source-g6-macos-release-byte-readback-two.json`,
SHA-256
`dbaa422de18ab37e9f4b92d7e78631fad9719e6c6d41fe30ccb402365267d416`.
The create-only 1,266-byte repeatability receipt is at
`dist/lifecycle/macos-packaged-app-build-24-to-23-to-24-isolated-reverse-version-readback-repeatability-v1-current-source-g6-macos-release-byte-readback-two.json`,
SHA-256
`818474ea0469e10f836c237ef3d8cab3ec95ffd5da6299c13ea730982ff08a80`.
The result bytes exactly match both the preceding
`android-release-byte-readback-one` successor and the original unsuffixed v1
observation; all three result files and their receipts remain unchanged. After
normalizing only `canonicalResult.fileName`, each adjacent receipt pair is
identical; their different 1,266-, 1,268-, and 1,216-byte identities bind only
the respective create-only canonical result filenames.
Publication records each link intent before linking, fsyncs payloads and the
existing physical parent, rejects symlink ancestors and non-owned or
non-0600 evidence targets, rolls back only exact owned inodes on every
`BaseException`, and performs final stable no-follow byte readback.

The 44,003-byte runner and 31,118-byte 14-test module have SHA-256 values
`e22a3e32e0556428f1d0274a75b4bbe93c5f5d28fe1a60607e1537a3db1771b1`
and
`41aadb2c9e2e961b9934ebac284df0a4f9b60f7b6fa4d02992b50775da47647b`.
The standalone 31,402-byte read-only checker and 15,942-byte 15-test module
have SHA-256 values
`a6ef39ea10c314e756b2f92ad4ec07474da4f92bddb817a867acee2b33808b84`
and
`019e0ae415b77cbd3458c3bb98a2107f0218b3a76df661f9fadb99843cbacb40`.
The checker retains and revalidates all three generations and their six
evidence descriptors, the exact ledger, both three-file archive snapshots,
and the ten-file direct execution-source closure, including the current
247,676-byte release-archive checker at SHA-256
`8405ad0a532b2b88799f370da15b1a13694f1c9d3f79d9b3f0d4be8a5bbe2452`.
It rejects canonical/type/schema, claim-boundary, source-membership,
archive, state, tree, receipt, file-replacement, and symlink-ancestor mutations.

This is a fixed-canary compatibility observation, not an updater, downgrade,
supported migration, declared production predecessor, arbitrary N/N-1
qualification, or product rollback. The result explicitly makes no production
predecessor, N/N-1, rollback, or security qualification claim; it also records
that security state was not inspected and no security evidence was produced.
It does not qualify signed/notarized distribution, DMG/Finder/Gatekeeper,
clean-machine or cross-host behavior, pairing, device, provider, network, UI,
production release, canonical G6 exit, or any G7 exit tier."""
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RESULT_SIZE = 22_534
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RESULT_SHA256 = (
    "07d28a073746731241932681630014647ad452e382afd6728938daacb39e167f"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_SIZE = 45_998
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_SHA256 = (
    "073e58afa67228d6c208186d8ddca790b763a9c0a7acee9d5a681ff1f22801a9"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_TEST_SIZE = (
    32_632
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_TEST_SHA256 = (
    "df8a04a0e46e7ef0cc10a1f5dc29f3f8f9763e960995427304a7ccd93a2e8e4b"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_SIZE = 41_228
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_SHA256 = (
    "487317907ea2b377035a9b84488627bf4ce6887f06142d05245fb0c384a05392"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_TEST_SIZE = (
    43_110
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_TEST_SHA256 = (
    "cdf04f75832b63f8e8279afd6d7f84c6f11011ecc3a6be7e253054f009ed8811"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_START = (
    "<!-- aetherlink-current-build24-macos-idle-resource-stability-v1:"
    "start -->"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_END = (
    "<!-- aetherlink-current-build24-macos-idle-resource-stability-v1:"
    "end -->"
)
CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_BODY = """\
The current Build 24 non-security macOS idle-resource stability observation
used one exact packaged-app child under an isolated temporary HOME. After a
60,000 ms warm-up it retained 120 libproc samples at 5,000 ms targets across
600,000 ms. The maximum observed sample lateness was 79 ms.

The first and final 12-sample upper medians and full-run maxima were 10, 10,
and 10 open file descriptors; 142,344,192, 142,344,192, and 142,393,344
resident bytes; and 3, 3, and 4 threads. Final deltas were 0, 0, and 0;
peak deltas were 0, 49,152, and 1. All stayed within the predeclared local
regression budgets. The exact owned child accepted graceful termination,
exited with status 0, was reaped, and disappeared from AppKit. The preexisting
AetherLink app was preserved, no raw process identifier or temporary path was
retained, and the temporary root was removed before publication.

The canonical 22,534-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-idle-resource-stability-v1.json`,
SHA-256
`07d28a073746731241932681630014647ad452e382afd6728938daacb39e167f`.
The 45,998-byte runner and 32,632-byte 25-test module have SHA-256 values
`073e58afa67228d6c208186d8ddca790b763a9c0a7acee9d5a681ff1f22801a9`
and
`df8a04a0e46e7ef0cc10a1f5dc29f3f8f9763e960995427304a7ccd93a2e8e4b`.

The standalone read-only command
`python3 -I -B -S script/check_macos_build24_idle_resource_stability_evidence.py`
opens 16 fixed archive, ledger, result, runner, test, and transitive-source
files before hashing. It rechecks their held path graph, rejects noncanonical
or duplicate-key JSON and boolean/integer aliasing, and independently
recomputes all 120 targets, maximum lateness, upper medians, deltas, maxima,
limits, and pass flags. The evidence-era local-DMG runner is read from the
closed non-executable Build 24 source snapshot rather than rebound to its live
successor. Its 41,228-byte checker and 43,110-byte 27-test module
have SHA-256 values
`487317907ea2b377035a9b84488627bf4ce6887f06142d05245fb0c384a05392`
and
`cdf04f75832b63f8e8279afd6d7f84c6f11011ecc3a6be7e253054f009ed8811`.

This is one same-host, per-user, network-denied, point-in-time local idle
observation. It is not repeatability, load, performance-SLA, capacity,
long-soak, install, upgrade, recovery, rollback, device, provider, UI,
accessibility, production, or G7 Weekly resilience evidence. No signing or
signature verification was performed."""
CURRENT_BUILD24_MACOS_LIFECYCLE_CHAIN_PREDECESSOR_BY_DOCUMENT = {
    "README.md": (
        "external-network discovery, device, signing, deployment, "
        "security, or release\nevidence.\n\n"
        "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->"
    ),
    "docs/roadmap.md": (
        "Builds 1 through 23 remain separately readable historical "
        "archives.\n\n"
        "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->"
    ),
    "docs/handoff.md": (
        "Builds 1 through 23 are historical; their readback requires "
        "`--historical`.\n"
        "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->"
    ),
    "docs/progress.md": (
        "physical-device behavior, external networking, deployment, "
        "or a production\n  release.\n\n"
        "## 2026-07-31 macOS Build 23 To Build 24 Isolated Upgrade\n\n"
        "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->"
    ),
    "docs/qa-evidence.md": (
        "physical-device behavior, external networking, deployment,\n"
        "  or a production release.\n\n"
        "## 2026-07-31 macOS Build 23 To Build 24 Isolated Upgrade "
        "Checklist\n\n"
        "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->"
    ),
    "docs/releases/1.0.0-build-24-local-v1.md": (
        "fact. None of these historical observations transfers "
        "execution evidence to\nBuild 24.\n\n"
        "## Post-Archive Build 23 To Build 24 Isolated Upgrade "
        "Evidence\n\n"
        "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->"
    ),
}
CURRENT_BUILD24_MACOS_LIFECYCLE_CHAIN_OUTER_SHA256_BY_DOCUMENT = {
    "README.md": (
        "5a4a7e2eca835f484846c98e46c9bd567837e717fd5a28e137537a1eaf080859",
        "24c3ca32967205cd44ec07975147b05a307bdb1cf9a00e10f27b3fd9d5c4cdff",
    ),
    "docs/roadmap.md": (
        "f0f65281e3ae835a0e7b289591d025ad0460deb2bf274bccae4246fadbee2be9",
        "192a521a11e2d05d2e0f36992f7f838faf27e9e9c1036b2dbcfe0e80ad8b30a7",
    ),
    "docs/handoff.md": (
        "fd4f3b5d1cc4ae432072c7101d148220c7842aed87f3f8b0c93cda1c3f9b62d2",
        "45757b5ef397dd7976196ae5b267eee53544fa4b8546464073830acb39d7f858",
    ),
    "docs/progress.md": (
        "1c2d0283383525a70019bde471c6bcfd599c438b547ba15270e286902a979fe4",
        "c2e5ed1ec4d2af10ac3f3f87baeb3b9b29cc35393c1628cc63e147718d1589eb",
    ),
    "docs/qa-evidence.md": (
        "1dfa749f94755e4777bbf9ff18b733ff513293bca0e9a0ecf1738b2a325abfaf",
        "5c92341f48705b39fcd93e03390edba375eb6455bae3a4eb55807f2c6d3c4eff",
    ),
    "docs/releases/1.0.0-build-24-local-v1.md": (
        "815dcc3715bd2082122e016e6479908c4a5fce1d69ad6f9b4af002eef416e047",
        "eb4d9e1354eba5f0375e42b961b3dde775d9b7328f5723d4eca2f8357af0237a",
    ),
}
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE = 2_434
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256 = (
    "e78b605278d5c5b7f5601778c38f35270f1db4a9e95055ff434b71af4c33cf78"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256 = (
    "e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256 = (
    "89e566ff26d22eced043ffa108f8719274f9608685d6ecd18e579291c021cf47"
)
CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SIZE = 6_469
CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SHA256 = (
    "ddec23cf048fa77c559ca7ee4f45354feb558f830ca4b01eccffa5b7786ea09c"
)
CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SIZE = 898
CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SHA256 = (
    "886284149745c6fdd74625fab5d97c21ad35cd9b69cc2ade4353194b4ecd1733"
)
CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256 = (
    "abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095"
)
CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_TEST_SHA256 = (
    "fac7fb5474ae41d00374b577966d75caf3addf45de2243fe64a322cdad80632f"
)
CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START = (
    "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->"
)
CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END = (
    "<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:end -->"
)
CURRENT_MACOS_ISOLATED_UPGRADE_BOUNDARY = (
    "This post-archive runner and result were created after the immutable "
    "Build 24 source snapshot and are not Build 23 or Build 24 archive "
    "members or source inputs. The evidence qualifies only the recorded "
    "same-host, per-user, temporary-HOME, local ad-hoc Build 23-to-24 "
    "transition in which Application Support was retained; it does not "
    "establish automatic data cleanup. It does not qualify rollback, "
    "arbitrary N/N-1 versions, clean-machine or Finder/DMG installation, "
    "signed distribution, physical-device behavior, provider, network, or "
    "UI behavior, or production-release qualification."
)
CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_BLOCK_SHA256 = {
    "README.md": (
        "350abcf391d0fc3db74656914af28073d06e687478b3ce5a1a6f6bb617ea777d"
    ),
    "docs/roadmap.md": (
        "9258b5b3f3737009cf4059f2a631f291c1daefff12f0e2ddc7e3745a287381f0"
    ),
    "docs/handoff.md": (
        "1fb5135bfb920c8a50b8d4e27ffd9c467e13520fa5e074d5aaedafb48637cfc9"
    ),
    "docs/progress.md": (
        "f1ade8eea03355a790c3e31e32d59ae67df90b5bbbf25bfb2024dbd7a11cae35"
    ),
    "docs/qa-evidence.md": (
        "02d8b15c8d45c058afbe565d6c2bf1be661a3f7a281078bcee07f0a522bdc970"
    ),
    "docs/releases/1.0.0-build-24-local-v1.md": (
        "3d3614b5d8469650870550de6ca92755139ca8823fdb0b023cdc2d3fcf28a7bb"
    ),
}
CURRENT_RUNTIME_CHAT_SQLITE_SWIFT_TESTS = (
    (
        "testSQLiteCrossInstanceAppendWaitsForImmediateTransactionAnd"
        "CommitsExactlyOnce"
    ),
    "testSQLiteCrossInstanceBusyTimeoutRollsBackAndLaterReopenSucceeds",
    "testSQLiteBusyTimeoutAtCommitRollsBackEventAndFTSRowsBeforeReopen",
)
CURRENT_RUNTIME_CHAT_SQLITE_STABLE_BUSY_MESSAGE = (
    "Runtime chat history is temporarily busy. Try again."
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE = 2_223
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256 = (
    "db66614d7badd7a0f606c03f91a516dff6d77e539684dcb6daf52709bce0f16f"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START = (
    "<!-- aetherlink-current-build21-abrupt-recovery-v1:start -->"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END = (
    "<!-- aetherlink-current-build21-abrupt-recovery-v1:end -->"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_BLOCK_SHA256 = {
    "README.md": (
        "3fe613780130d575fc083d721d1b45677569661f7fffa8b4163386112c9cb06f"
    ),
    "docs/roadmap.md": (
        "bb63e6f5198d25908ac010ceb3a2b132462602398bf3f621530131bcccf49ceb"
    ),
    "docs/handoff.md": (
        "61af0160afd46516126d7b453edd689e6b091d394de2e2c80fd82e225b098f42"
    ),
    "docs/progress.md": (
        "c5906554dcc3ddec0b3fc8587f05d89639c6d61d4c3ab3670a67a33d58c52748"
    ),
    "docs/qa-evidence.md": (
        "69ce082b9bc2d0ffdfe63138c80012d375c80871fcbd37da3d80d9859e0a3ac7"
    ),
    "docs/releases/1.0.0-build-22-local-v1.md": (
        "d3a5e47b36a8a444f07c4a307e910141be4ae7784e5ea05ab00acad90a8361b2"
    ),
    "docs/releases/1.0.0-build-24-local-v1.md": (
        "d3a5e47b36a8a444f07c4a307e910141be4ae7784e5ea05ab00acad90a8361b2"
    ),
}
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_BODY_SHA256_BY_DOCUMENT = {
    "README.md": (
        "47ae8d160162160bdf50ac1665cf5199a454bbdaab735e24cca807ab48f01778"
    ),
    "docs/roadmap.md": (
        "4f62248831121af2c5cda260db7cf21c0a3559041fea1fd4719153848e591ece"
    ),
    "docs/handoff.md": (
        "4a31420a4e912ffa5201b0cdb1acf2d5ae078b140d819ca918747586645f6835"
    ),
    "docs/progress.md": (
        "9309497777cffde18e01a2dc1f4c96d3a98bd223253d414d02dc45a210ec1c8a"
    ),
    "docs/qa-evidence.md": (
        "3c78bd2b6de1d10550097bb7b3df2ad6ffa79a47efd4ca5a1100b9a4fd00d38b"
    ),
    "docs/releases/1.0.0-build-20-local-v1.md": (
        "a20b68807d4a4a099195c83b801818f76ed750cfcb14c25a609b485a2075ad54"
    ),
    "docs/releases/1.0.0-build-24-local-v1.md": (
        "a20b68807d4a4a099195c83b801818f76ed750cfcb14c25a609b485a2075ad54"
    ),
}
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_OUTER_SHA256_BY_DOCUMENT = {
    "README.md": (
        "3c5c3d864c7b9aa54a45ea0d09c3961346cb5b49fa228c48f11cd79c94cdebd6",
        "71ddae4e8d84a7f78f05459c0a572c74a914dd05fa1abd17eb2c4ee32c16adfd",
    ),
    "docs/roadmap.md": (
        "4ffda7413c3d1c44f6da163bedb27be65c5fba6a34f42598e55231701e666c3f",
        "61ed443d3966c86c1bc8cebdab91e5d84629248a6b881163cf6d90568c427440",
    ),
    "docs/handoff.md": (
        "49d51477a27a1ec6b7d5a6b932c043e376738361c77e089ab1d5706b3b771210",
        "fcd0f93e8d91ade7dc84df0a0cf1ba3d5dfc0d2ff485645b94211dbafd4a63bf",
    ),
    "docs/progress.md": (
        "c5f39633efba296a8e3d0c1600d1d36ad8b4127bec84bfaeac1a07a7879eecbd",
        "75ff47867bb3a85000e23e723f8b9c20e8caf252de95bb19a91732fca40863a6",
    ),
    "docs/qa-evidence.md": (
        "b3242c580f9756fcdc8e09c32726efaae0423d6b84333c20734f558ecd6afd30",
        "89cbf66a09001c07387613ebe728ed79d2ebbe66b943beec8bde498e08aedf85",
    ),
    "docs/releases/1.0.0-build-20-local-v1.md": (
        "fb0c1b58bbd660832b3949162552530870b24872e9034c03c0241bb84d99f366",
        "b2673dc9c562eb6a7f8d209136c138754d58fb9adebfbfabc9b8696c5f3c490c",
    ),
    "docs/releases/1.0.0-build-24-local-v1.md": (
        "155758b4bfd7d8cffed49ee803fb100306b89fea11bb47e258b905184e0a8f3a",
        "ef12bbf9c69c36c9cdfd712abe6185c4e77135ca0ca0c0de8b967afc01420442",
    ),
}
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_NEIGHBORS = {
    "README.md": (
        "Those historical observations are not reinterpreted as Build 21 "
        "evidence.\n\n"
        + CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        + "\n\nBuild 24 preserves compliance profile",
    ),
    "docs/roadmap.md": (
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        + "\n\n"
        + CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        + "\n\nThe separate V3 observation path",
    ),
    "docs/handoff.md": (
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        + "\n\n"
        + CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        + "\n\n- Build 16 preserves",
    ),
    "docs/progress.md": (
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        + "\n\n"
        + CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        + "\n\n- This historical local result",
    ),
    "docs/qa-evidence.md": (
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        + "\n\n"
        + CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        + "\n\n- [ ] This historical local result",
    ),
    "docs/releases/1.0.0-build-20-local-v1.md": (
        "## Historical Build 20 Clean-HOME Installed Lifecycle Evidence\n\n"
        + CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        + "\n\n## Historical Build 20 Local DMG Mount-And-Copy "
        "Lifecycle Evidence",
    ),
    "docs/releases/1.0.0-build-24-local-v1.md": (
        "## Historical Build 20 Clean-HOME Installed Lifecycle Evidence\n\n"
        + CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        + "\n\n## Historical Build 20 Local DMG Evidence",
    ),
}
CURRENT_RUNTIME_CHAT_SQLITE_DOCUMENT_REQUIRED_PATTERNS = (
    (
        "production 5-second busy timeout",
        re.compile(
            r"\bproduction\b.{0,100}\b(?:five-second|5-second)\b"
            r".{0,50}\bbusy timeout\b.{0,80}\bevery\b.{0,40}"
            r"\b(?:connection|database connection)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "three deterministic Swift contention tests",
        re.compile(
            r"\bthree deterministic Swift tests\b.{0,500}\bBEGIN\b"
            r".{0,500}\bCOMMIT\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "two independent 48-event writers",
        re.compile(
            r"\btwo independent\b.{0,80}\b(?:helper processes|writer "
            r"processes|48-event writers)\b.{0,160}\b(?:each writer "
            r"appended 48|48 events each|48-event)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "third-process readback",
        re.compile(
            r"\bthird(?: independent|-process)\b.{0,40}\breadback\b"
            r".{0,60}\bprocess\b",
            re.IGNORECASE,
        ),
    ),
    (
        "96 disjoint exactly-once events",
        re.compile(
            r"\b48\+48=96\b.{0,160}\bdisjoint and exactly once\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "owner and session isolation",
        re.compile(r"\bowner/session isolation\b", re.IGNORECASE),
    ),
    (
        "per-writer append order",
        re.compile(
            r"\bper-writer (?:append )?order(?:ing)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "SQLite integrity",
        re.compile(
            r"\bSQLite integrity\b.{0,80}\bchecks passed\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "owner-only permissions",
        re.compile(
            r"\bpermissions\b.{0,80}`0700`.{0,40}`0600`",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "live evidence is outside the archive",
        re.compile(
            r"\blive\b.{0,100}\bseparate execution evidence\b"
            r".{0,80}\bnot an? (?:retained (?:Build 19 )?)?archive member\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "non-production evidence boundary",
        re.compile(
            r"\bdoes not (?:establish|qualify)\b.{0,320}\bproduction (?:behavior|"
            r"readiness)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)
CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START = (
    "<!-- aetherlink-current-android-drawer-search-ux-v2:start -->"
)
CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_END = (
    "<!-- aetherlink-current-android-drawer-search-ux-v2:end -->"
)
CURRENT_ANDROID_DRAWER_SEARCH_BEHAVIOR_CLAIM = (
    "The current unreleased Android drawer provides an explicit touch Search "
    "action with localized accessibility semantics and the keyboard Search "
    "action through one trimmed-query submission path."
)
CURRENT_ANDROID_DRAWER_SEARCH_ACTION_STATE_CLAIM = (
    "Blank, disconnected, streaming, bulk-mutation, and exact same-query "
    "pending states expose localized action-state descriptions without "
    "dispatching."
)
CURRENT_ANDROID_DRAWER_SEARCH_PENDING_CLAIM = (
    "Only the exact current pending query shows a polite localized progress "
    "live region and suppresses the no-results row; editing or clearing the "
    "query closes that request and invalidates its transient search authority."
)
CURRENT_ANDROID_DRAWER_SEARCH_RESULT_CLAIM = (
    "Only an exact current-query remote response is adopted; stale or absent "
    "response state falls back to immediate local filtering, while current "
    "remote results exclude archived sessions and retain global Runtime rank."
)
CURRENT_ANDROID_DRAWER_SEARCH_EVIDENCE_CLAIM = (
    "The current no-device gate passes 168 AppNavigationTest cases, 22 "
    "navigation-drawer Compose cases, 15 search-related "
    "RuntimeClientViewModelTest cases, and the complete 1,194-test app JVM "
    "suite; release lint reports 0 errors and 2 SDK-version warnings."
)
CURRENT_ANDROID_DRAWER_SEARCH_BOUNDARY_CLAIM = (
    "This source/JVM/Compose evidence is not part of the immutable Build 17 "
    "archive and is first source-bound by the immutable Build 18 archive; it "
    "does not establish physical touch, TalkBack, provider, device, network, "
    "installation, signing, or release behavior."
)
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SIZE = 2_185
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "21f30e0b60e81bcbfb7e8a198c68ef53d6f6c739a63c80a1339278b7565ea769"
)
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca"
)
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "d40d3dac44606f2a1e17a44de5564894f68036a0ba0cf7778fba5574306de5db"
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
LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT = 249
LOCAL_RELEASE_EXPECTED_SOURCE_SHA256 = (
    "a01d37c3be608db3a8fa588b1ec019b673b5c57bc227ffc105047b3e4548f5f2"
)
LOCAL_RELEASE_EXPECTED_SOURCE_OVERLAY_SHA256 = (
    "9d71c5340e1809222542c59d0da96f1ee08f9b619741ae3b0f1cb4fcbc28a3cc"
)
LOCAL_RELEASE_EXPECTED_PREPUBLICATION_SOURCE_OVERLAY_SHA256 = (
    "9d71c5340e1809222542c59d0da96f1ee08f9b619741ae3b0f1cb4fcbc28a3cc"
)
LOCAL_RELEASE_EXPECTED_SOURCE_HEAD = (
    "7d72147528e334edb19b9331ed7933ac71ca424b"
)
LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS = {
    "Package.swift": (
        5_893,
        "446f45034b4093735aeab8bffab87b87642741a379502206307b4419ee2100d8",
    ),
    "apps/macos/CompanionCore/Sources/SQLiteRuntimeChatEventStore.swift": (
        113_478,
        "2365118d7ebb7c808ca42caa69366a2cbf10f631cc088dafe9a3ea618c3346bb",
    ),
    (
        "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
        "RuntimeChatSQLiteCrossProcessQA.swift"
    ): (
        26_025,
        "e4251d009e2ac5775d4ad4beaf8d4528c0812749dae64768760c4ce454c20946",
    ),
    "script/run_macos_runtime_chat_cross_process_smoke.py": (
        52_697,
        "f14021e368372dbf14713974277f62c28aa16bd5160bb9d57b964186e0aa0a78",
    ),
    "script/test_run_macos_runtime_chat_cross_process_smoke.py": (
        25_065,
        "1229600eebdf95317e303f81bc60727fce06b81ee3c8a17be6d0c359bd6a1034",
    ),
}
LOCAL_RELEASE_EXPECTED_MEMBER_COUNT = 29
LOCAL_RELEASE_EXPECTED_MACOS_UUID = "3FDC3DBC-3A74-3A3B-A87D-03CB432B5D46"
LOCAL_RELEASE_EXPECTED_MEMBERS = {
    "android/apk/app-release-unsigned.apk": (
        9_575_138,
        "bd9867b9788cb2e9aa88e7b71259a19dde59b776156f147f9b59162ab0903d74",
    ),
    "android/bundle/app-release.aab": (
        10_677_978,
        "3572b0e696fb714c168de2165f143e966655039eb41ce240d275669791d322fd",
    ),
    "android/mapping/mapping.txt": (
        71_910_079,
        "df11c4119f7ddcab82084d93f377d50cd14a1c33d06eae30192df00a0fcc7514",
    ),
    "android/mapping/resources.txt": (
        134_768,
        "002f51ef322a3849b5c4671db6bb6dd89722dfacd0a3418e465939ac406c005a",
    ),
    "macos/AetherLink.app/Contents/MacOS/AetherLink": (
        18_592_368,
        "5bf283a6dd3504682cb4aefc9cb1536c7e340f776c90de83cea5a473044890e5",
    ),
    "macos/AetherLink.dSYM/Contents/Resources/DWARF/AetherLink": (
        31_607_333,
        "922ad09eccd079e6c128cbb1e85fc311d3fb6ec9315941e1821daac135fc1656",
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
        "a2529e7a0507c5984af849c22aed31cfbde95e5cccb8ecc3ae53190d0b59ee88",
    ),
    "compliance/third-party-license-inventory-v1.json": (
        411_087,
        "1f97b74e794e5e2b3092cc31ce8c67f634a299989658feca597bc301b67dcda5",
    ),
    "source-files.json": (
        48_320,
        "9e72eb51fc21694243680e25b912de78bed4e0d154bdc505646899dd86f80500",
    ),
}
LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK = {
    "member": "android/apk/app-release-unsigned.apk",
    "tool": "aapt2 dump xmltree + resources",
    "verifiedFields": [
        "allowBackup",
        "dataExtractionRules",
        "fullBackupContent",
        "entryPointTopology",
        "applicationShell",
    ],
}
LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK = {
    "member": "android/bundle/app-release.aab",
    "tool": (
        "bundletool dump manifest + resources + config + universal APK "
        "readback"
    ),
    "verifiedFields": [
        "applicationId",
        "minSdk",
        "targetSdk",
        "versionCode",
        "versionName",
        "allowBackup",
        "dataExtractionRules",
        "fullBackupContent",
        "entryPointTopology",
        "applicationShell",
    ],
}
LOCAL_RELEASE_ANDROID_BACKUP_POLICY_REQUIRED_CLAIMS = (
    "`allowBackup=false`",
    "`dataExtractionRules=@xml/data_extraction_rules`",
    "`fullBackupContent=@xml/backup_rules`",
    "`cloud-backup`",
    "`device-transfer`",
    "`root`, `file`, `database`, `sharedpref`, and `external`",
    (
        "`device_root`, `device_file`, `device_database`, and "
        "`device_sharedpref`"
    ),
    '`path="."`',
    "No `<include>` rule is present.",
    "`aapt2 dump xmltree + resources`",
    "`bundletool dump manifest + resources + config + universal APK readback`",
    (
        "Build 15 is the first local release that requires both APK and AAB "
        "backup-policy manifest readback."
    ),
    (
        "Build 17 adds compiled XML body readback for both the APK and an "
        "AAB-derived universal APK."
    ),
)
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
        "marketingVersion": HISTORICAL_BUILD14_MARKETING_VERSION,
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
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT = {
    "app": {
        "buildNumber": 13,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": (
            "e4b91c631e460dc23aba8ac0a6d83107326321341dd9f98042d6c712b85fd514"
        ),
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "uuid": "A16CB949-C7E9-3BD7-A1AB-AC5D0662437F",
    },
    "canary": {
        "eventID": "packaged-state-recovery-canary-event-v1",
        "eventJsonSha256": (
            "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
        ),
        "eventJsonSize": 344,
        "legacyJsonlSha256": (
            "0e51fc924836465c4c0921eb3b3709b387f89787aabf2e100c7cff338f0aea2e"
        ),
        "legacyJsonlSize": 345,
        "model": "qa:packaged-state-recovery-canary-v1",
        "requestID": "packaged-state-recovery-canary-request-v1",
        "sessionID": "packaged-state-recovery-canary-session-v1",
    },
    "isolation": {
        "profile": "allow-default-deny-network-and-non-temp-writes-v1",
        "sandboxed": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "release": {
        "archiveSha256": (
            "d48bf8f837c104624b14b1cdc223d5c62aa2c68d13ff6d830f0a394dcd953191"
        ),
        "manifestSha256": (
            "3f720d7119a9196b9a7db085313ac0c9e796ce903b8738bf04406e3fc87b384b"
        ),
        "releaseId": "aetherlink-1.0.0+13-local-v1",
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
    "stateRecovery": {
        "legacyAbsentBeforeSecondRun": True,
        "legacyFixturePreservedUnchanged": True,
        "migrationObservation": {
            "mode": "migration-read-v1",
            "sha256": (
                "558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9"
            ),
            "size": 70,
            "status": "passed",
        },
        "migrationSQLite": {
            "eventJsonSha256": (
                "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
            ),
            "eventJsonSize": 344,
            "integrityCheck": "ok",
            "totalEventCount": 1,
        },
        "sqliteCanaryUnchangedAcrossRuns": True,
        "sqliteReadbackObservation": {
            "mode": "sqlite-readback-v1",
            "sha256": (
                "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07"
            ),
            "size": 71,
            "status": "passed",
        },
        "sqliteReadbackSQLite": {
            "eventJsonSha256": (
                "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
            ),
            "eventJsonSize": 344,
            "integrityCheck": "ok",
            "totalEventCount": 1,
        },
    },
    "status": "passed",
}
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT = {
    "app": {
        "buildNumber": 14,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": (
            "619d96c01723e512e9cc857540f9ef5db97232237e549a419e65b6a62eead1d2"
        ),
        "marketingVersion": HISTORICAL_BUILD14_MARKETING_VERSION,
        "uuid": HISTORICAL_BUILD14_MACOS_UUID,
    },
    "installation": {
        "codesignVerified": True,
        "copyTool": "ditto",
        "installedRelativePath": "Applications/AetherLink.app",
        "regularFileTreeMatchesReleaseManifest": True,
        "tree": {
            "digestAlgorithm": (
                "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
            ),
            "regularFileCount": 10,
            "sha256": (
                "74be59c1986fe6a703c4648a82b8d1c3264ac8e568df7aace186b655edeacc54"
            ),
            "totalRegularFileBytes": 20_828_180,
        },
    },
    "isolation": {
        "cleanHomeConfigured": True,
        "preexistingBundleApplicationsPreserved": True,
        "runtimeIdentityFileOverrideConfigured": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "launchServices": {
        "commandPolicy": (
            "open-new-fresh-background-exact-app-path-v1"
        ),
        "distinctProcessIdentifiers": True,
        "runs": [
            {
                "activationPolicy": 0,
                "executablePathMatched": True,
                "finishedLaunching": True,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": True,
            }
            for ordinal in (1, 2)
        ],
    },
    "limitations": [
        "same-host-per-user-rehearsal-only",
        "not-a-clean-machine-or-dmg-installation",
        "not-developer-id-notarization-or-signed-distribution",
        "not-physical-device-or-live-provider-evidence",
    ],
    "release": {
        "archiveSha256": HISTORICAL_BUILD14_ARCHIVE_SHA256,
        "manifestSha256": HISTORICAL_BUILD14_MANIFEST_SHA256,
        "releaseId": HISTORICAL_BUILD14_RELEASE_ID,
    },
    "schemaVersion": 1,
    "scope": "same-host-per-user-clean-home-launchservices-rehearsal-v1",
    "state": {
        "expectedSQLiteFiles": [
            "runtime-chat-events.sqlite",
            "runtime-document-index.sqlite",
            "runtime-model-pull-approvals.sqlite",
        ],
        "regularFileBytesAndModesUnchangedAcrossRelaunch": True,
        "runtimeIdentityFilePresent": True,
        "sqlite": [
            {
                "filename": "runtime-chat-events.sqlite",
                "integrityCheck": "ok",
                "totalEventCount": 0,
            },
            {
                "filename": "runtime-document-index.sqlite",
                "integrityCheck": "ok",
            },
            {
                "filename": "runtime-model-pull-approvals.sqlite",
                "integrityCheck": "ok",
            },
        ],
    },
    "status": "passed",
}
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT = {
    "app": MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["app"],
    "canary": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT["canary"],
    "installation": MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT[
        "installation"
    ],
    "isolation": MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["isolation"],
    "launchServices": {
        "commandPolicy": (
            "open-new-fresh-background-exact-app-path-captured-recovery-v1"
        ),
        "distinctProcessIdentifiers": True,
        "runs": [
            {
                "activationPolicy": 0,
                "executablePathMatched": True,
                "finishedLaunching": True,
                "minimumObservationSeconds": 5.0,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": True,
            }
            for ordinal in (1, 2)
        ],
    },
    "limitations": [
        "same-host-per-user-rehearsal-only",
        "not-a-clean-machine-account-or-dmg-installation",
        "not-ui-accessibility-or-live-provider-evidence",
        "not-physical-device-or-signed-distribution-evidence",
    ],
    "release": {
        "archiveSha256": HISTORICAL_BUILD14_ARCHIVE_SHA256,
        "manifestSha256": HISTORICAL_BUILD14_MANIFEST_SHA256,
        "releaseId": HISTORICAL_BUILD14_RELEASE_ID,
    },
    "schemaVersion": 1,
    "scope": (
        "same-host-per-user-clean-home-launchservices-state-recovery-v1"
    ),
    "stateRecovery": {
        "auxiliarySQLite": [
            {
                "filename": "runtime-document-index.sqlite",
                "integrityCheck": "ok",
            },
            {
                "filename": "runtime-model-pull-approvals.sqlite",
                "integrityCheck": "ok",
            },
        ],
        "installedStateBytesAndModesUnchangedAcrossRelaunch": True,
        "legacyAbsentBeforeSecondRun": True,
        "legacyFixturePreservedUnchanged": True,
        "migrationObservation": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT[
            "stateRecovery"
        ]["migrationObservation"],
        "migrationSQLite": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT[
            "stateRecovery"
        ]["migrationSQLite"],
        "runtimeIdentityFilePresent": True,
        "sqliteCanaryUnchangedAcrossRuns": True,
        "sqliteReadbackObservation": (
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT["stateRecovery"][
                "sqliteReadbackObservation"
            ]
        ),
        "sqliteReadbackSQLite": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT[
            "stateRecovery"
        ]["sqliteReadbackSQLite"],
    },
    "status": "passed",
}
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT = {
    **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT,
    "app": {
        "buildNumber": 20,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": (
            "92070b85256532b23b327fec5b6a46df2d98f2de89f85750ea6189c838197fb6"
        ),
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "uuid": HISTORICAL_BUILD20_MACOS_UUID,
    },
    "installation": {
        **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"],
        "tree": {
            **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"][
                "tree"
            ],
            "sha256": (
                "937433afa0f493365bcb823b88f02dbc0eb52294ca15d235a420ed8498572e46"
            ),
            "totalRegularFileBytes": 20_828_260,
        },
    },
    "release": {
        "archiveSha256": HISTORICAL_BUILD20_ARCHIVE_SHA256,
        "manifestSha256": HISTORICAL_BUILD20_MANIFEST_SHA256,
        "releaseId": HISTORICAL_BUILD20_RELEASE_ID,
    },
}
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT = {
    **MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT,
    "app": CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["app"],
    "installation": (
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"]
    ),
    "release": CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["release"],
}
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT = {
    **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT,
    "app": {
        "buildNumber": LOCAL_RELEASE_BUILD_NUMBER,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": (
            "5bf283a6dd3504682cb4aefc9cb1536c7e340f776c90de83cea5a473044890e5"
        ),
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "uuid": LOCAL_RELEASE_EXPECTED_MACOS_UUID,
    },
    "installation": {
        **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"],
        "tree": {
            **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"][
                "tree"
            ],
            "sha256": (
                "0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff"
            ),
            "totalRegularFileBytes": 21_151_910,
        },
    },
    "release": {
        "archiveSha256": LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
        "manifestSha256": LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
        "releaseId": LOCAL_RELEASE_ID,
    },
}
CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT = {
    **MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT,
    "app": CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["app"],
    "installation": (
        CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT[
            "installation"
        ]
    ),
    "release": CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT[
        "release"
    ],
}
CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT = {
    "archiveReadback": {
        "currentSourceCompared": False,
        "mode": "archive-only-no-current-source",
        "readbackAndExerciseSameSnapshot": True,
        "snapshotFiles": {
            f"{LOCAL_RELEASE_ID}.manifest.json": {
                "sha256": LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
                "size": LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE,
            },
            f"{LOCAL_RELEASE_ID}.zip": {
                "sha256": LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
                "size": LOCAL_RELEASE_EXPECTED_ZIP_SIZE,
            },
            f"{LOCAL_RELEASE_ID}.zip.sha256": {
                "sha256": LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256,
                "size": LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE,
            },
        },
        "snapshotFilesUnchangedAfterExercise": True,
        "status": "passed",
    },
    "image": {
        "ephemeral": True,
        "filesystem": "HFS+",
        "format": "UDZO",
        "retained": False,
        "verified": True,
    },
    "installation": {
        "adHocAppSealAndVersionVerified": True,
        "applicationsAliasPresent": True,
        "copyTool": "ditto",
        "exactReleaseTreeCopied": True,
        "tree": {
            "digestAlgorithm": (
                "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
            ),
            "regularFileCount": 10,
            "sha256": (
                "0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff"
            ),
            "totalRegularFileBytes": 21_151_910,
        },
    },
    "isolation": {
        "cleanHomeConfigured": True,
        "preexistingBundleApplicationsPreserved": True,
        "runtimeIdentityFileOverrideConfigured": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "launchServices": {
        "distinctProcessIdentifiers": True,
        "exactInstalledBundlePerCycle": True,
        "runs": [
            {
                "activationPolicy": 0,
                "finishedLaunching": True,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": True,
            }
            for ordinal in (1, 2)
        ],
    },
    "limitations": [
        "not-finder-ui-or-drag-and-drop-evidence",
        "not-general-ui-or-accessibility-evidence",
        "not-developer-id-notarized-or-stapled-distribution",
        "not-gatekeeper-quarantine-or-download-evidence",
        "not-clean-machine-account-or-system-applications",
        "not-tcc-keychain-provider-network-or-device-evidence",
        "not-arbitrary-history-crash-power-loss-or-concurrent-writer-evidence",
        "not-backup-restore-or-device-transfer-evidence",
        "not-upgrade-n-or-n-minus-one-rollback-production-or-security-evidence",
    ],
    "mount": {
        "detachedBeforeLaunch": True,
        "exactFreshMountpoint": True,
        "nobrowse": True,
        "oneMountedEntity": True,
        "readOnly": True,
        "unmountedVerified": True,
    },
    "release": {
        "archiveSha256": LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
        "manifestSha256": LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
        "releaseId": LOCAL_RELEASE_ID,
    },
    "schemaVersion": 2,
    "scope": "same-host-per-user-ephemeral-local-dmg-install-v2",
    "state": {
        "databaseCount": 3,
        "emptyRuntimeChatVerified": True,
        "integrityChecks": "passed",
        "regularFileBytesAndModesUnchangedAcrossRelaunch": True,
        "runtimeIdentityFilePresent": True,
        "sqlite": [
            {
                "filename": "runtime-chat-events.sqlite",
                "integrityCheck": "ok",
                "totalEventCount": 0,
            },
            {
                "filename": "runtime-document-index.sqlite",
                "integrityCheck": "ok",
            },
            {
                "filename": "runtime-model-pull-approvals.sqlite",
                "integrityCheck": "ok",
            },
        ],
        "stableAcrossRelaunch": True,
    },
    "status": "passed",
}
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT = {
    **CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT,
    "archiveReadback": {
        **CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
            "archiveReadback"
        ],
        "snapshotFiles": {
            f"{LOCAL_RELEASE_ID}.manifest.json": {
                "sha256": CURRENT_SOURCE_G6_REPRODUCIBLE_MANIFEST_SHA256,
                "size": 15_200,
            },
            f"{LOCAL_RELEASE_ID}.zip": {
                "sha256": CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SHA256,
                "size": CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SIZE,
            },
            f"{LOCAL_RELEASE_ID}.zip.sha256": {
                "sha256": CURRENT_SOURCE_G6_REPRODUCIBLE_CHECKSUM_SHA256,
                "size": 99,
            },
        },
    },
    "installation": {
        **CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
            "installation"
        ],
        "tree": {
            **CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
                "installation"
            ]["tree"],
            "sha256": (
                "2596df8daa50f962ef776032a2487dd10d431b621f08d496d67b221fac0c9b64"
            ),
            "totalRegularFileBytes": 21_356_326,
        },
    },
    "release": {
        "archiveSha256": CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SHA256,
        "manifestSha256": CURRENT_SOURCE_G6_REPRODUCIBLE_MANIFEST_SHA256,
        "releaseId": LOCAL_RELEASE_ID,
    },
}
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT = {
    "archiveReadback": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
            "archiveReadback"
        ]
    ),
    "image": {
        "ephemeral": True,
        "filesystem": "HFS+",
        "format": "UDZO",
        "retained": False,
        "sameImageBytesUsedForBothInstalls": True,
        "verified": True,
    },
    "installation": {
        "adHocAppSealAndVersionVerified": True,
        "applicationsAliasPresent": True,
        "copyTool": "ditto",
        "exactReleaseTreeCopiedEachInstall": True,
        "installCount": 2,
        "origin": "same-ephemeral-local-dmg",
        "reinstallTreeMatchesInitial": True,
        "tree": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
                "installation"
            ]["tree"]
        ),
    },
    "isolation": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
            "isolation"
        ]
    ),
    "launchServices": {
        "distinctProcessIdentifiers": True,
        "exactInstalledBundlePerCycle": True,
        "noExactTemporaryAppRemaining": True,
        "runs": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
                "launchServices"
            ]["runs"]
        ),
    },
    "limitations": [
        "same-host-per-user-temporary-home-only",
        "same-created-dmg-image-remount-only",
        "application-support-retained-no-automatic-data-cleanup",
        "post-archive-harness-not-build-input-member",
        (
            "not-finder-system-applications-quarantine-or-gatekeeper-"
            "evidence"
        ),
        "not-signed-notarized-stapled-or-distribution-evidence",
        (
            "not-clean-machine-upgrade-rollback-device-provider-network-ui-"
            "accessibility-production-or-security-evidence"
        ),
    ],
    "mount": {
        "cycleCount": 2,
        "detachedBeforeEachLaunch": True,
        "exactFreshMountpointPerInstall": True,
        "nobrowse": True,
        "oneMountedEntityPerInstall": True,
        "readOnly": True,
        "unmountedAfterEachCopy": True,
    },
    "release": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
            "release"
        ]
    ),
    "schemaVersion": 1,
    "scope": (
        "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-v1"
    ),
    "state": {
        "applicationSupportPreservedAcrossRemovalAndReinstall": True,
        "databaseCount": 3,
        "emptyRuntimeChatVerified": True,
        "integrityChecks": "passed",
        "regularFileBytesAndModesUnchanged": True,
        "runtimeIdentityFilePresent": True,
        "sqlite": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
                "state"
            ]["sqlite"]
        ),
        "stableAcrossRemovalAndReinstall": True,
    },
    "status": "passed",
    "uninstall": {
        "appAbsentAfterEachRemoval": True,
        "applicationSupportCleanupPerformed": False,
        "exactTemporaryAppPathOnly": True,
        "exactTemporaryAppStoppedBeforeEachRemoval": True,
        "removalCount": 2,
        "removalMethod": "python-shutil-rmtree",
    },
}
CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT = {
    "archiveReadback": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
            "archiveReadback"
        ]
    ),
    "canary": (
        CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT[
            "canary"
        ]
    ),
    "image": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT[
            "image"
        ]
    ),
    "installation": {
        **CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT[
            "installation"
        ],
        "statePresentBeforeReinstall": True,
    },
    "isolation": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT["isolation"]
    ),
    "launchServices": {
        "commandPolicy": (
            "open-new-fresh-background-exact-app-path-captured-recovery-v1"
        ),
        "distinctProcessIdentifiers": True,
        "exactInstalledBundlePerCycle": True,
        "noExactTemporaryAppRemaining": True,
        "runs": [
            {
                "activationPolicy": 0,
                "executablePathMatched": True,
                "finishedLaunching": True,
                "minimumObservationSeconds": 5.0,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": True,
            }
            for ordinal in (1, 2)
        ],
    },
    "limitations": [
        "same-host-per-user-temporary-home-only",
        "same-created-dmg-image-remount-only",
        "fixed-runtime-chat-legacy-canary-only",
        "legacy-fixture-removed-by-harness-before-reinstall-readback",
        "application-support-retained-no-automatic-data-cleanup",
        "post-archive-harness-not-build-input-member",
        (
            "not-finder-system-applications-quarantine-or-gatekeeper-"
            "evidence"
        ),
        "not-signed-notarized-stapled-or-distribution-evidence",
        (
            "not-clean-machine-upgrade-rollback-device-provider-network-ui-"
            "accessibility-production-or-security-evidence"
        ),
    ],
    "mount": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT[
            "mount"
        ]
    ),
    "release": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT["release"]
    ),
    "schemaVersion": 1,
    "scope": (
        "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
        "state-recovery-v1"
    ),
    "stateRecovery": {
        "applicationSupportPreservedAcrossRemovalAndReinstall": True,
        "auxiliarySQLite": (
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["auxiliarySQLite"]
        ),
        "databaseCount": 3,
        "installedStateBytesAndModesUnchangedAcrossRemovalAndReinstall": True,
        "legacyAbsentBeforeReinstallReadback": True,
        "legacyFixturePreservedUnchanged": True,
        "legacyRemovedByHarnessBeforeReinstall": True,
        "migrationObservation": (
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["migrationObservation"]
        ),
        "migrationSQLite": (
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["migrationSQLite"]
        ),
        "runtimeIdentityFilePresent": True,
        "sqliteCanaryUnchangedAcrossRemovalAndReinstall": True,
        "sqliteReadbackObservation": (
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["sqliteReadbackObservation"]
        ),
        "sqliteReadbackSQLite": (
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["sqliteReadbackSQLite"]
        ),
        "totalEventCount": 1,
    },
    "status": "passed",
    "uninstall": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT[
            "uninstall"
        ]
    ),
}
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT = {
    **CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT,
    "archiveReadback": (
        CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
            "archiveReadback"
        ]
    ),
    "installation": {
        **CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT[
            "installation"
        ],
        "tree": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
            "installation"
        ]["tree"],
    },
    "release": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
        "release"
    ],
}
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_EXPECTED_RESULT = {
    **(
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT
    ),
    "archiveReadback": (
        CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
            "archiveReadback"
        ]
    ),
    "installation": {
        **(
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "installation"
            ]
        ),
        "tree": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
            "installation"
        ]["tree"],
    },
    "release": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
        "release"
    ],
}
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EMPTY_LOG = {
    "sha256": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "size": 0,
}
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT = {
    "abruptTermination": {
        "appKitProcessAbsentAfterReap": True,
        "exactExecutableRevalidatedBeforeSignal": True,
        "exitCode": -9,
        "gracefulTerminationRequested": False,
        "inFlightWriteCheckpointObserved": False,
        "launchMethod": "direct-installed-executable-owned-child",
        "migrationCommittedBeforeAbruptLaunch": True,
        "observationCompletedBeforeSignal": True,
        "persistenceProbePassedBeforeSignal": True,
        "processDisposition": (
            "exact-owned-child-pid-sigkill-reaped-and-appkit-absent"
        ),
        "processReaped": True,
        "signal": "SIGKILL",
        "signalNumber": 9,
    },
    "archiveReadback": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT[
            "archiveReadback"
        ]
    ),
    "canary": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
            "canary"
        ]
    ),
    "image": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
            "image"
        ]
    ),
    "installation": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
            "installation"
        ]
    ),
    "isolation": {
        "preexistingBundleApplicationsPreserved": True,
        "runtimeIdentityFileOverrideConfigured": True,
        "sandboxedOwnedChildConfigured": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "launches": {
        "distinctProcessIdentifiers": True,
        "exactInstalledBundlePerCycle": True,
        "gracefulLaunchServicesCommandPolicy": (
            "open-new-fresh-background-exact-app-path-captured-recovery-v1"
        ),
        "noExactTemporaryAppRemaining": True,
        "runs": [
            {
                "activationPolicy": 0,
                "executablePathMatched": True,
                "finishedLaunching": True,
                "launchMethod": "launchservices-open-exact-installed-app",
                "minimumObservationSeconds": 5.0,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": 1,
                "terminationAccepted": True,
            },
            {
                "activationPolicy": 0,
                "appKitProcessAbsentAfterReap": True,
                "exactExecutableIdentityMatchedImmediatelyBeforeSignal": True,
                "exitCode": -9,
                "finishedLaunching": True,
                "launchMethod": "direct-installed-executable-owned-child",
                "minimumObservationSeconds": 5.0,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": 2,
                "ownedChildProcess": True,
                "persistenceProbePassedBeforeSignal": True,
                "processReaped": True,
                "signalName": "SIGKILL",
                "signalNumber": 9,
            },
            {
                "activationPolicy": 0,
                "executablePathMatched": True,
                "finishedLaunching": True,
                "launchMethod": "launchservices-open-exact-installed-app",
                "minimumObservationSeconds": 5.0,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": 3,
                "terminationAccepted": True,
            },
        ],
        "stderr": {
            "abruptReadback": (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EMPTY_LOG
            ),
            "migration": (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EMPTY_LOG
            ),
            "recoveryReadback": (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EMPTY_LOG
            ),
        },
    },
    "limitations": [
        "same-host-per-user-temporary-home-only",
        "same-created-dmg-image-remount-only",
        "fixed-runtime-chat-legacy-canary-only",
        "post-persisted-sqlite-readback-observation-sigkill-only",
        "legacy-fixture-removed-by-harness-before-reinstall-readback",
        "no-in-flight-write-checkpoint-or-open-transaction-observed",
        (
            "not-write-durability-crash-consistency-power-loss-or-"
            "kernel-crash-evidence"
        ),
        "not-os-restart-ui-force-quit-arbitrary-history-or-soak-evidence",
        "application-support-retained-no-automatic-data-cleanup",
        "post-archive-harness-not-build-input-member",
        (
            "not-finder-system-applications-quarantine-gatekeeper-signing-"
            "notarization-or-stapling-evidence"
        ),
        (
            "not-upgrade-rollback-device-provider-network-ui-accessibility-"
            "production-or-security-evidence"
        ),
    ],
    "mount": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
            "mount"
        ]
    ),
    "release": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
            "release"
        ]
    ),
    "schemaVersion": 1,
    "scope": (
        "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
        "abrupt-process-state-recovery-v1"
    ),
    "stateRecovery": {
        "applicationSupportPreservedAcrossRemovalAndReinstall": True,
        "auxiliarySQLite": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["auxiliarySQLite"]
        ),
        "databaseCount": 3,
        "legacyAbsentBeforeAbruptAndRecoveryReadback": True,
        "legacyFixturePreservedUnchanged": True,
        "legacyRemovedByHarnessBeforeReinstall": True,
        "migrationObservation": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["migrationObservation"]
        ),
        "migrationSQLite": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["migrationSQLite"]
        ),
        "ownedAbruptReadbackObservation": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["sqliteReadbackObservation"]
        ),
        "ownedAbruptReadbackSQLite": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["sqliteReadbackSQLite"]
        ),
        "postAbruptSQLite": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["sqliteReadbackSQLite"]
        ),
        (
            "postAbruptStateBytesAndModesUnchangedAcrossRemovalReinstall"
        ): True,
        "recoveryReadbackObservation": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["sqliteReadbackObservation"]
        ),
        "recoveryReadbackSQLite": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
                "stateRecovery"
            ]["sqliteReadbackSQLite"]
        ),
        "runtimeIdentityFilePresent": True,
        "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination": True,
        "totalEventCount": 1,
    },
    "status": "passed",
    "uninstall": (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT[
            "uninstall"
        ]
    ),
}
CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RECEIPT = {
    "canonicalResult": {
        "fileName": (
            "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
            "abrupt-process-state-recovery-v1.json"
        ),
        "sha256": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        "size": (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SIZE
        ),
    },
    "limitations": [
        "same-host-two-recorded-runs-only",
        "not-arbitrary-repeatability-or-long-soak-evidence",
        (
            "not-in-flight-write-power-loss-kernel-crash-clean-machine-"
            "signed-distribution-device-network-or-production-evidence"
        ),
    ],
    "releaseId": "aetherlink-1.0.0+24-local-v1",
    "resultBytesEqual": True,
    "runCount": 2,
    "runs": [
        {
            "ordinal": ordinal,
            "sha256": (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SHA256
            ),
            "size": (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SIZE
            ),
            "status": "passed",
        }
        for ordinal in (1, 2)
    ],
    "schemaVersion": 1,
    "scope": (
        "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
        "abrupt-process-state-recovery-repeatability-v1"
    ),
    "status": "passed",
}
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_EXPECTED_RESULT = {
    **CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT,
    "archiveReadback": (
        CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
            "archiveReadback"
        ]
    ),
    "installation": {
        **(
            CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT[
                "installation"
            ]
        ),
        "tree": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
            "installation"
        ]["tree"],
    },
    "release": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
        "release"
    ],
}
CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_EXPECTED_RECEIPT = {
    **CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RECEIPT,
    "canonicalResult": {
        "fileName": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT.name,
        "sha256": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SHA256,
        "size": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SIZE,
    },
    "releaseId": LOCAL_RELEASE_ID,
    "runs": [
        {
            "ordinal": ordinal,
            "sha256": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SHA256,
            "size": CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SIZE,
            "status": "passed",
        }
        for ordinal in (1, 2)
    ],
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


def lifecycle_source_sha256_is_bound(
    path: Path,
    actual_sha256: str,
    historical_sha256: str,
) -> bool:
    return actual_sha256 in {
        historical_sha256,
        CURRENT_SOURCE_G6_LIFECYCLE_SUCCESSOR_SHA256_BY_PATH.get(path),
    }


def lifecycle_source_sha256_set_is_bound(
    actual_sha256_by_path: dict[Path, str],
    historical_sha256_by_path: dict[Path, str],
) -> bool:
    successor_paths = set(historical_sha256_by_path) & set(
        CURRENT_SOURCE_G6_LIFECYCLE_SUCCESSOR_SHA256_BY_PATH
    )
    if not successor_paths.issubset(actual_sha256_by_path):
        return False
    actual = {
        path: actual_sha256_by_path[path]
        for path in successor_paths
    }
    historical = {
        path: historical_sha256_by_path[path]
        for path in successor_paths
    }
    successor = {
        path: CURRENT_SOURCE_G6_LIFECYCLE_SUCCESSOR_SHA256_BY_PATH[path]
        for path in successor_paths
    }
    return actual == historical or actual == successor


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
    "docs/releases/1.0.0-build-12-local-v1.md",
    "docs/releases/1.0.0-build-13-local-v1.md",
    "docs/releases/1.0.0-build-14-local-v1.md",
    "docs/releases/1.0.0-build-15-local-v1.md",
    "docs/releases/1.0.0-build-16-local-v1.md",
    "docs/releases/1.0.0-build-17-local-v1.md",
    "docs/releases/1.0.0-build-18-local-v1.md",
    "docs/releases/1.0.0-build-19-local-v1.md",
    "docs/releases/1.0.0-build-20-local-v1.md",
    "docs/releases/1.0.0-build-21-local-v1.md",
    "docs/releases/1.0.0-build-22-local-v1.md",
    "docs/releases/1.0.0-build-23-local-v1.md",
    "docs/releases/1.0.0-build-24-local-v1.md",
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
        "docs/releases/1.0.0-build-24-local-v1.md",
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
                r"\bbounded local Build 23-to-24\b.*\bqualified\b.*"
                r"\barbitrary N/N-1\b.*\bare not\b",
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
                rf"\b{LOCAL_RELEASE_EXPECTED_ZIP_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256}\b"
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
    f"The Build {LOCAL_RELEASE_BUILD_NUMBER} archive is the latest ledger entry"
)
QA_STALE_RELEASE_READBACK_MARKERS = (
    "The Build 23 archive is the latest ledger entry",
    "The Build 22 archive is the latest ledger entry",
    "The Build 21 archive is the latest ledger entry",
    "The Build 20 archive is the latest ledger entry",
    "The Build 19 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 18 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 17 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 16 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 15 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 14 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 13 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 11 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
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
    ROOT / "docs/handoff.md",
    LOCAL_RELEASE_CURRENT_DOC,
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
            "docs/qa-evidence.md: Build "
            f"{LOCAL_RELEASE_BUILD_NUMBER} current-source readback marker "
            "is missing."
        )
    for stale_marker in QA_STALE_RELEASE_READBACK_MARKERS:
        if stale_marker in normalized_text:
            failures.append(
                "docs/qa-evidence.md: stale current-release EOF readback claim "
                "must not remain current."
            )
    return failures


def current_release_summary_document_failures(
    *,
    ledger_bytes: bytes | None = None,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    try:
        entries = parse_release_version_ledger(
            LOCAL_RELEASE_LEDGER.read_bytes()
            if ledger_bytes is None
            else ledger_bytes
        )
    except (OSError, LedgerError) as error:
        return [
            "release/version-ledger.tsv: cannot validate current release "
            f"summary documents: {error}"
        ]
    if len(entries) < 2:
        return [
            "release/version-ledger.tsv: current release summary validation "
            "requires a current and previous entry."
        ]

    current = entries[-1]
    previous = entries[-2]
    current_id = (
        f"aetherlink-{current.marketing_version}"
        f"+{current.build_number}-local-v1"
    )
    previous_id = (
        f"aetherlink-{previous.marketing_version}"
        f"+{previous.build_number}-local-v1"
    )
    result_version = CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION
    required_claims_by_relative = {
        "docs/handoff.md": (
            f"Build {current.build_number} is the latest immutable ledger archive.",
            f"v{result_version} comparison-only prepublication result",
            f"v{result_version} publish-qualified result",
            current_id,
            f"Builds 1 through {previous.build_number} are historical",
        ),
        "docs/progress.md": (
            f"Local V1 Build {current.build_number} Qualification",
            (
                f"Build {current.build_number} is the current local "
                "qualification record; Builds 1 through "
                f"{previous.build_number} are immutable historical records."
            ),
            f"Both v{result_version} two-root runs",
            current_id,
            f"Historical Local V1 Build {previous.build_number} Qualification",
        ),
        "docs/qa-evidence.md": (
            f"Local V1 Build {current.build_number} Qualification Checklist",
            (
                f"The Build {current.build_number} archive is the latest "
                "ledger entry"
            ),
            f"Builds 1 through {previous.build_number} remain immutable historical records.",
            current_id,
            (
                f"Historical Local V1 Build {previous.build_number} "
                "Qualification Checklist"
            ),
        ),
        "docs/roadmap.md": (
            (
                f"Build {current.build_number} is the latest immutable local "
                "G6 package qualification record"
            ),
            f"publish-qualified schema-v{result_version} executions",
            f"latest immutable ledger archive is `{current_id}`",
            (
                f"Builds 1 through {previous.build_number} remain separately "
                "readable historical archives."
            ),
        ),
    }
    forbidden_claims_by_relative = {
        "docs/handoff.md": (
            (
                f"Build {previous.build_number} is the latest immutable "
                "ledger archive."
            ),
            f"The v{result_version - 1} comparison-only prepublication result is",
            f"The v{result_version - 1} publish-qualified result is",
        ),
        "docs/progress.md": (
            (
                f"Build {previous.build_number} is the current local "
                "qualification record"
            ),
        ),
        "docs/qa-evidence.md": (
            (
                f"The Build {previous.build_number} archive is the latest "
                "ledger entry"
            ),
        ),
        "docs/roadmap.md": (
            (
                f"Build {previous.build_number} is the latest immutable local "
                "G6 package qualification record"
            ),
            f"latest immutable ledger archive is `{previous_id}`",
            (
                f"publish-qualified schema-v{result_version - 1} executions "
                "reproduced the same"
            ),
        ),
    }
    summary_line_limits = {
        "docs/handoff.md": 650,
        "docs/progress.md": 550,
        "docs/qa-evidence.md": 550,
        "docs/roadmap.md": 650,
    }

    failures: list[str] = []
    for relative, required_claims in required_claims_by_relative.items():
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else (ROOT / relative).read_text(encoding="utf-8")
            )
        except (KeyError, OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current release summary: {error}"
            )
            continue
        summary_text = "\n".join(
            document_text.splitlines()[: summary_line_limits[relative]]
        )
        normalized_text = " ".join(summary_text.split())
        for claim in required_claims:
            normalized_claim = " ".join(claim.split())
            if normalized_claim not in normalized_text:
                failures.append(
                    f"{relative}: missing ledger-derived current release "
                    f"summary claim {claim!r}."
                )
        for claim in forbidden_claims_by_relative[relative]:
            normalized_claim = " ".join(claim.split())
            if normalized_claim in normalized_text:
                failures.append(
                    f"{relative}: stale previous-release summary claim "
                    f"{claim!r} must not coexist with the current release."
                )
        previous_build_reference = re.compile(
            rf"\bBuild\s+{previous.build_number}\b",
            re.IGNORECASE,
        )
        release_context = re.compile(
            r"\b(?:qualification|ledger|archive|release|package|record|"
            r"entry|evidence|result|prepublication|publication)\b",
            re.IGNORECASE,
        )
        current_or_latest = re.compile(
            r"(?<!then-)\b(?:current|latest)\b",
            re.IGNORECASE,
        )
        state_verb = re.compile(
            r"\b(?:is|remain|remains|continues|serves)\b",
            re.IGNORECASE,
        )
        negated_current = re.compile(
            r"\b(?:not|no longer)\b.{0,24}\b(?:current|latest)\b",
            re.IGNORECASE,
        )
        previous_result_version = result_version - 1
        stale_result_version = re.compile(
            (
                rf"(?:\bschema-v{previous_result_version}\b|"
                rf"\bv{previous_result_version}\b.{{0,80}}"
                r"\b(?:comparison-only|publish-qualified)\b|"
                r"\b(?:comparison-only|publish-qualified)\b.{0,80}"
                rf"\bv{previous_result_version}\b)"
            ),
            re.IGNORECASE,
        )
        for sentence in re.split(r"(?<=[.!?])\s+", normalized_text):
            if (
                previous_build_reference.search(sentence)
                and release_context.search(sentence)
                and current_or_latest.search(sentence)
                and state_verb.search(sentence)
                and "historical" not in sentence.lower()
                and not negated_current.search(sentence)
            ):
                failures.append(
                    f"{relative}: previous Build {previous.build_number} "
                    "must not be semantically re-attributed as the current "
                    "or latest release summary."
                )
                break
        for sentence in re.split(r"(?<=[.!?])\s+", normalized_text):
            if (
                stale_result_version.search(sentence)
                and release_context.search(sentence)
                and current_or_latest.search(sentence)
                and state_verb.search(sentence)
                and "historical" not in sentence.lower()
                and not negated_current.search(sentence)
            ):
                failures.append(
                    f"{relative}: reproducibility result schema v"
                    f"{previous_result_version} must not be semantically "
                    "re-attributed as current release evidence."
                )
                break
    return failures


def release_readback_command_mode_failures(
    document_text_by_path: dict[str, str] | None = None,
) -> list[str]:
    failures: list[str] = []
    try:
        current_build_number = parse_release_version_ledger(
            LOCAL_RELEASE_LEDGER.read_bytes()
        )[-1].build_number
    except (OSError, LedgerError, IndexError) as error:
        return [
            "release/version-ledger.tsv: cannot validate release readback "
            f"command modes: {error}"
        ]
    release_pattern = re.compile(
        r"--archive-dir\s+dist/releases/"
        r"aetherlink-[0-9]+\.[0-9]+\.[0-9]+\+"
        r"(?P<build>[1-9][0-9]*)-local-v1"
    )
    historical_pattern = re.compile(
        r"(?<![\w-])--historical(?![\w-])"
    )
    direct_android_pattern = re.compile(
        r"(?<![\w-])--android-build-outputs(?![\w-])"
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
            direct_android_mode = (
                direct_android_pattern.search(line) is not None
            )
            match = release_pattern.search(line)
            if direct_android_mode:
                if match is not None or historical_pattern.search(line):
                    failures.append(
                        f"{relative}:{line_number}: direct Android build-output "
                        "readback must not name an archive or historical mode."
                    )
                continue
            if match is None:
                failures.append(
                    f"{relative}:{line_number}: release readback command must "
                    "name a canonical versioned archive directory on the same "
                    "line."
                )
                continue

            build_number = int(match.group("build"))
            historical_mode = historical_pattern.search(line) is not None
            if build_number < current_build_number and not historical_mode:
                failures.append(
                    f"{relative}:{line_number}: historical Build "
                    f"{build_number} release readback command requires "
                    "`--historical`."
                )
            elif (
                build_number == current_build_number
                and historical_mode
            ):
                failures.append(
                    f"{relative}:{line_number}: current Build "
                    f"{build_number} release readback command must not use "
                    "`--historical`."
                )
            elif build_number > current_build_number:
                failures.append(
                    f"{relative}:{line_number}: release readback command names "
                    f"future Build {build_number}; current Build is "
                    f"{current_build_number}."
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


def current_release_android_backup_policy_document_failures(
    document_text: str,
    *,
    relative: str = (
        f"docs/releases/{LOCAL_RELEASE_MARKETING_VERSION}-build-"
        f"{LOCAL_RELEASE_BUILD_NUMBER}-local-v1.md"
    ),
) -> list[str]:
    failures: list[str] = []
    normalized_document = re.sub(r"\s+", " ", document_text)
    for index, claim in enumerate(
        LOCAL_RELEASE_ANDROID_BACKUP_POLICY_REQUIRED_CLAIMS,
        1,
    ):
        normalized_claim = re.sub(r"\s+", " ", claim)
        if normalized_claim not in normalized_document:
            failures.append(
                f"{relative}: missing exact Android backup-policy claim "
                f"{index} claim {claim!r}."
            )
    return failures


def current_release_android_manifest_readback_failures(
    manifest: object,
    *,
    relative: str = (
        f"dist/releases/{LOCAL_RELEASE_ID}/"
        f"{LOCAL_RELEASE_ID}.manifest.json"
    ),
) -> list[str]:
    if not isinstance(manifest, dict):
        return [f"{relative}: manifest root must be a JSON object."]

    def read_path(path: tuple[str, ...]) -> object:
        value: object = manifest
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    failures: list[str] = []
    expectations = (
        (
            ("platforms", "android", "apkManifestReadback"),
            LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK,
        ),
        (
            ("platforms", "android", "bundleManifestReadback"),
            LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK,
        ),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )
    return failures


def current_handoff_git_attribution_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/handoff.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate Git-state attribution: {error}"
            ]

    normalized = re.sub(r"\s+", " ", document_text).strip()
    required_bindings = (
        (
            f"Build {LOCAL_RELEASE_BUILD_NUMBER} qualification-time source attribution",
            (
                f"The Build {LOCAL_RELEASE_BUILD_NUMBER} manifest captured "
                "source HEAD and "
                "`origin/main` as "
                f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}` at qualification time."
            ),
        ),
        (
            "timestamped post-qualification Git refresh",
            (
                f"at the {LATEST_RECORDED_GIT_REFRESH_LABEL} refresh, `main` "
                "and `origin/main` both resolved to "
                f"`{LATEST_RECORDED_GIT_REFRESH_HEAD}`."
            ),
        ),
        (
            "live HEAD refresh command",
            "`git rev-parse HEAD`",
        ),
        (
            "live origin/main refresh command",
            "`git rev-parse origin/main`",
        ),
        (
            "archive source identity boundary",
            (
                "The archived source inventory, not either commit alone, "
                f"remains the Build {LOCAL_RELEASE_BUILD_NUMBER} source identity."
            ),
        ),
    )
    failures: list[str] = []
    for label, binding in required_bindings:
        normalized_binding = re.sub(r"\s+", " ", binding).strip()
        if normalized.count(normalized_binding) != 1:
            failures.append(
                f"{relative}: {label} must appear exactly once."
            )

    stale_live_claims = (
        (
            "`main` and `origin/main` both resolve to "
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`"
        ),
        (
            "HEAD and `origin/main` are "
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`"
        ),
    )
    for claim in stale_live_claims:
        if claim in normalized:
            failures.append(
                f"{relative}: qualification-time source HEAD is presented "
                "as a live Git-state claim."
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
            f"`dist/reproducibility/{LOCAL_RELEASE_ID}-two-root-v4.json`",
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
            "reproducibility prepublication path",
            (
                f"`dist/reproducibility/{LOCAL_RELEASE_ID}-two-root-v4-"
                "prepublication.json`"
            ),
        ),
        (
            "reproducibility prepublication size",
            (
                f"{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "reproducibility prepublication SHA-256",
            (
                f"`{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256}`"
            ),
        ),
        (
            "reproducibility comparison-only boundary",
            "`executionMode=comparison-only`",
        ),
        (
            "reproducibility publish-qualified boundary",
            "`executionMode=publish-qualified`",
        ),
        (
            "reproducibility verified publication outcome",
            "`outcome=published-verified`",
        ),
        (
            "reproducibility new publication state",
            "`alreadyMatched=false`",
        ),
        (
            "reproducibility exact prepublication binding",
            "`prepublicationBinding.matched=true`",
        ),
        (
            "protected previous-archive policy",
            "`previous-ledger-entry-archive-v1`",
        ),
        (
            "protected previous-archive identity",
            (
                f"`{LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256}`"
            ),
        ),
        (
            "Swift frontend serialization",
            "`-Xswiftc -num-threads -Xswiftc 1`",
        ),
        (
            "current isolated upgrade result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json`"
            ),
        ),
        (
            "current isolated upgrade result size",
            "6,469-byte canonical result",
        ),
        (
            "current isolated upgrade result SHA-256",
            f"`{CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SHA256}`",
        ),
        (
            "current isolated upgrade repeatability path",
            (
                "`dist/lifecycle/macos-packaged-app-build-23-to-24-"
                "isolated-upgrade-repeatability-v1.json`"
            ),
        ),
        (
            "current isolated upgrade repeatability size",
            (
                f"{CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SIZE}"
                "-byte repeatability receipt"
            ),
        ),
        (
            "current isolated upgrade repeatability SHA-256",
            (
                "`"
                f"{CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SHA256}"
                "`"
            ),
        ),
        (
            "current isolated upgrade runner SHA-256",
            f"`{CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256}`",
        ),
        (
            "current isolated upgrade test SHA-256",
            f"`{CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_TEST_SHA256}`",
        ),
        (
            "current isolated upgrade event JSON identity",
            (
                "`da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef`"
            ),
        ),
        (
            "current isolated upgrade previous app tree identity",
            (
                "`31209251804494f54a699c5c4e8101491f02fca881cf25fba379b88eb493d8a8`"
            ),
        ),
        (
            "current isolated upgrade current app tree identity",
            (
                "`0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff`"
            ),
        ),
        (
            "Build 21 abrupt recovery result path",
            (
                "`dist/lifecycle/"
                "macos-runtime-chat-sqlite-abrupt-process-recovery-"
                "build-21-v1.json`"
            ),
        ),
        (
            "Build 21 abrupt recovery result size",
            f"{CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE:,} bytes",
        ),
        (
            "Build 21 abrupt recovery result SHA-256",
            f"`{CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256}`",
        ),
        (
            "Build 21 abrupt recovery boundary",
            "bounded same-host abrupt child-process `SIGKILL` recovery evidence",
        ),
        (
            "Build 21 production append crash-point exclusion",
            "`not-production-append-crash-point`",
        ),
        (
            "current Build 20 clean-HOME installed-app result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-clean-home-install-v1.json`"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app result size",
            (
                f"{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app result SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app runner SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app test SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "current Build 20 installed state-recovery result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-clean-home-state-recovery-v1.json`"
            ),
        ),
        (
            "current Build 20 installed state-recovery result size",
            (
                f"{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "current Build 20 installed state-recovery result SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "current Build 20 installed state-recovery runner SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "current Build 20 installed state-recovery test SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "current Build 20 lifecycle repeatability",
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_REPEATABILITY_CLAIM,
        ),
        (
            "current Build 20 local DMG result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-local-dmg-install-v1.json`"
            ),
        ),
        (
            "current Build 20 local DMG result size",
            f"{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE:,} bytes",
        ),
        (
            "current Build 20 local DMG result SHA-256",
            f"`{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256}`",
        ),
        (
            "current Build 20 local DMG runner SHA-256",
            f"`{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256}`",
        ),
        (
            "current Build 20 local DMG test SHA-256",
            f"`{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256}`",
        ),
        (
            "historical Build 16 release ID",
            f"`{HISTORICAL_BUILD16_RELEASE_ID}`",
        ),
        (
            "historical Build 16 archive size",
            f"{HISTORICAL_BUILD16_ARCHIVE_SIZE:,} bytes",
        ),
        (
            "historical Build 16 archive SHA-256",
            f"`{HISTORICAL_BUILD16_ARCHIVE_SHA256}`",
        ),
        (
            "historical Build 16 successful result size",
            f"{HISTORICAL_BUILD16_RESULT_SIZE:,} bytes",
        ),
        (
            "historical Build 16 successful result SHA-256",
            f"`{HISTORICAL_BUILD16_RESULT_SHA256}`",
        ),
        (
            "historical Build 16 failed attempt size",
            f"{HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE:,} bytes",
        ),
        (
            "historical Build 16 failed attempt SHA-256",
            f"`{HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256}`",
        ),
        (
            "historical Build 16 failed confirmation size",
            f"{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE:,} bytes",
        ),
        (
            "historical Build 16 failed confirmation SHA-256",
            f"`{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256}`",
        ),
        (
            "historical Build 16 failed publication boundary",
            "`publication=null`",
        ),
        (
            "historical Build 16 non-transfer boundary",
            (
                "Build 17 does not retroactively qualify Build 16."
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-14-clean-home-install-v1.json`"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app result size",
            (
                f"{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app result SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app runner SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app test SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "historical Build 14 clean-HOME distinct relaunch identifiers",
            "`distinctProcessIdentifiers=true`",
        ),
        (
            "historical Build 14 clean-HOME state identity",
            (
                "`regularFileBytesAndModesUnchangedAcrossRelaunch=true`"
            ),
        ),
        (
            "historical Build 14 clean-HOME empty chat state",
            "`totalEventCount=0`",
        ),
        (
            "historical Build 14 installed state-recovery result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-14-clean-home-state-recovery-v1.json`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery result size",
            (
                f"{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "historical Build 14 installed state-recovery result SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery runner SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery test SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery state identity",
            "`installedStateBytesAndModesUnchangedAcrossRelaunch=true`",
        ),
        (
            "historical Build 14 installed state-recovery identity file",
            "`runtimeIdentityFilePresent=true`",
        ),
        (
            "historical Build 14 installed state-recovery separation",
            (
                "Build 14 installed state-recovery evidence remains bound to "
                "Build 14 and is not reinterpreted as Build 17 evidence."
            ),
        ),
        (
            "packaged state-recovery result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-13-state-recovery-v1.json`"
            ),
        ),
        (
            "packaged state-recovery result size",
            f"{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} bytes",
        ),
        (
            "packaged state-recovery result SHA-256",
            f"`{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`",
        ),
        (
            "packaged state-recovery runner SHA-256",
            f"`{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`",
        ),
        (
            "packaged state-recovery test SHA-256",
            f"`{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`",
        ),
        (
            "packaged state-recovery legacy removal",
            "`legacyAbsentBeforeSecondRun=true`",
        ),
        (
            "packaged state-recovery legacy identity",
            "`legacyFixturePreservedUnchanged=true`",
        ),
        (
            "packaged state-recovery SQLite identity",
            "`sqliteCanaryUnchangedAcrossRuns=true`",
        ),
        (
            "packaged state-recovery event JSON identity",
            (
                "`da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef`"
            ),
        ),
        (
            "packaged state-recovery migration observation identity",
            (
                "`558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9`"
            ),
        ),
        (
            "packaged state-recovery readback observation identity",
            (
                "`ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07`"
            ),
        ),
        (
            "Build 12 state-recovery non-transfer boundary",
            (
                "Build 12 state-recovery result was not published, and Build "
                "13 evidence is not reinterpreted as Build 12 evidence."
            ),
        ),
        (
            "Build 13 state-recovery non-transfer boundary",
            (
                "Build 13 state-recovery evidence remains bound to Build 13 "
                "and is not reinterpreted as Build 17 evidence."
            ),
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
                "reinterpreted as Build 17 evidence."
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
        (
            "source overlay SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_OVERLAY_SHA256}`",
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
    historical_claim_prefixes = (
        "historical ",
        "packaged state-recovery ",
        "Build 12 state-recovery ",
        "Build 13 state-recovery ",
        "packaged-app ",
        "Build 10 lifecycle ",
    )
    required_claims = tuple(
        claim
        for claim in required_claims
        if not claim[0].startswith(historical_claim_prefixes)
    )
    for member_path, (size, sha256) in LOCAL_RELEASE_EXPECTED_MEMBERS.items():
        required_claims += (
            (f"{member_path} size", f"{size:,} bytes"),
            (f"{member_path} SHA-256", f"`{sha256}`"),
        )

    normalized_document = re.sub(r"\s+", " ", document_text)
    for label, expected_text in required_claims:
        normalized_expected = re.sub(r"\s+", " ", expected_text)
        if normalized_expected not in normalized_document:
            failures.append(
                f"{relative_doc}: missing exact {label} claim {expected_text!r}."
            )
    failures.extend(
        current_release_android_backup_policy_document_failures(
            document_text,
            relative=str(relative_doc),
        )
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
    failures.extend(
        current_release_android_manifest_readback_failures(
            manifest,
            relative=str(manifest_path.relative_to(ROOT)),
        )
    )

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
        (
            ("platforms", "android", "apkManifestReadback"),
            LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK,
        ),
        (
            ("platforms", "android", "bundleManifestReadback"),
            LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK,
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
        f"dist/reproducibility/{LOCAL_RELEASE_ID}-two-root-v4.json"
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

    missing_result_path = object()

    def read_result_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return missing_result_path
            value = value[key]
        return value

    result_expectations = (
        (("schemaVersion",), 4),
        (("executionMode",), "publish-qualified"),
        (("releaseId",), LOCAL_RELEASE_ID),
        (("status",), "passed"),
        (("failure",), None),
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
        (("prepublicationBinding", "matched"), True),
        (
            ("prepublicationBinding", "path"),
            (
                f"dist/reproducibility/{LOCAL_RELEASE_ID}-two-root-v4-"
                "prepublication.json"
            ),
        ),
        (
            ("prepublicationBinding", "policy"),
            "canonical-comparison-result-exact-source-builds-and-comparison-v1",
        ),
        (
            ("prepublicationBinding", "sha256"),
            LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256,
        ),
        (
            ("prepublicationBinding", "size"),
            LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE,
        ),
        (
            ("protectedArchive", "policy"),
            "previous-ledger-entry-archive-v1",
        ),
        (
            ("protectedArchive", "relativePath"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_RELATIVE,
        ),
        (
            ("protectedArchive", "beforeIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (
            ("protectedArchive", "afterIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (("protectedArchive", "unchanged"), True),
        (
            ("toolchainPolicy", "scope"),
            "same-host-fixed-toolchain-cache-snapshot",
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
        (
            ("publication", "archiveDirectory"),
            f"dist/releases/{LOCAL_RELEASE_ID}",
        ),
        (("publication", "alreadyMatched"), False),
        (("publication", "attempted"), True),
        (("publication", "independentReadback"), True),
        (("publication", "outcome"), "published-verified"),
        (
            ("publication", "policy"),
            "publish-qualified-build-a-after-exact-two-root-match",
        ),
        (("publication", "publishedBytesEqualLaneA"), True),
        (("publication", "qualifiedArchivePublished"), True),
        (("publication", "sourceLane"), "build-a"),
        (("publication", "sourceSnapshotUnchanged"), True),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (
            ("source", "overlaySha256"),
            LOCAL_RELEASE_EXPECTED_SOURCE_OVERLAY_SHA256,
        ),
        (("source", "sha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
    )
    for path, expected in result_expectations:
        actual = read_result_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{result_relative}: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )
    swift_arguments = read_result_path(("toolchainPolicy", "swiftArguments"))
    serialized_frontend = ["-Xswiftc", "-num-threads", "-Xswiftc", "1"]
    if (
        not isinstance(swift_arguments, list)
        or not any(
            swift_arguments[index : index + len(serialized_frontend)]
            == serialized_frontend
            for index in range(
                len(swift_arguments) - len(serialized_frontend) + 1
            )
        )
    ):
        failures.append(
            f"{result_relative}: toolchainPolicy.swiftArguments must include "
            f"the exact contiguous sequence {serialized_frontend!r}."
        )

    failures.extend(
        current_release_reproducibility_build_failures(
            result,
            result_relative,
        )
    )
    failures.extend(current_release_reproducibility_prepublication_failures())
    return failures


def current_release_reproducibility_build_failures(
    result: dict[str, object],
    relative: str,
) -> list[str]:
    failures: list[str] = []
    builds = result.get("builds")
    if not isinstance(builds, list) or len(builds) != 2:
        return [
            f"{relative}: builds must contain exact build-a/build-b results."
        ]
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
            ("size", LOCAL_RELEASE_EXPECTED_ZIP_SIZE),
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
        members = archive.get("members")
        expected_member_count = LOCAL_RELEASE_EXPECTED_MEMBER_COUNT + 1
        if not isinstance(members, list) or len(members) != expected_member_count:
            failures.append(
                f"{relative}: builds[{index}].archive.members must contain "
                f"exactly {expected_member_count} entries."
            )
    return failures


def current_release_reproducibility_prepublication_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    relative = (
        f"dist/reproducibility/{LOCAL_RELEASE_ID}-two-root-v4-"
        "prepublication.json"
    )
    if result_bytes is None:
        if not LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT.is_file():
            return [f"{relative}: missing reproducibility prepublication result."]
        try:
            result_bytes = (
                LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT.read_bytes()
            )
        except OSError as error:
            return [
                f"{relative}: unreadable reproducibility prepublication "
                f"result: {error}"
            ]

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE,
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256,
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
            f"{relative}: invalid reproducibility prepublication JSON: {error}"
        )
        return failures
    if not isinstance(result, dict):
        failures.append(
            f"{relative}: reproducibility prepublication root must be an object."
        )
        return failures

    missing_result_path = object()

    def read_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return missing_result_path
            value = value[key]
        return value

    expectations = (
        (("schemaVersion",), 4),
        (("executionMode",), "comparison-only"),
        (("releaseId",), LOCAL_RELEASE_ID),
        (("status",), "passed"),
        (("failure",), None),
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
        (("prepublicationBinding",), None),
        (
            ("protectedArchive", "policy"),
            "previous-ledger-entry-archive-v1",
        ),
        (
            ("protectedArchive", "relativePath"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_RELATIVE,
        ),
        (
            ("protectedArchive", "beforeIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (
            ("protectedArchive", "afterIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (("protectedArchive", "unchanged"), True),
        (
            ("toolchainPolicy", "scope"),
            "same-host-fixed-toolchain-cache-snapshot",
        ),
        (("publication", "attempted"), False),
        (("publication", "independentReadback"), False),
        (("publication", "outcome"), "disabled-comparison-only"),
        (("publication", "policy"), "comparison-only-no-publication"),
        (("publication", "qualifiedArchivePublished"), False),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (
            ("source", "overlaySha256"),
            LOCAL_RELEASE_EXPECTED_PREPUBLICATION_SOURCE_OVERLAY_SHA256,
        ),
        (("source", "sha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )

    swift_arguments = read_path(("toolchainPolicy", "swiftArguments"))
    serialized_frontend = ["-Xswiftc", "-num-threads", "-Xswiftc", "1"]
    if (
        not isinstance(swift_arguments, list)
        or not any(
            swift_arguments[index : index + len(serialized_frontend)]
            == serialized_frontend
            for index in range(
                len(swift_arguments) - len(serialized_frontend) + 1
            )
        )
    ):
        failures.append(
            f"{relative}: toolchainPolicy.swiftArguments must include the "
            f"exact contiguous sequence {serialized_frontend!r}."
        )

    failures.extend(
        current_release_reproducibility_build_failures(result, relative)
    )
    return failures


CURRENT_SOURCE_G6_EVIDENCE_READ_LIMIT_BYTES = 1024 * 1024


def _stable_current_source_g6_evidence_bytes(
    *,
    path: Path,
    label: str,
) -> tuple[bytes | None, list[str]]:
    try:
        relative = str(path.relative_to(ROOT))
    except ValueError:
        relative = str(path)
    prefix = f"{relative}: current-source {label} result"
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_CLOEXEC"):
        return None, [
            f"{prefix} cannot be read fail-closed because this platform "
            "does not provide O_NOFOLLOW and O_CLOEXEC."
        ]
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None, [f"{relative}: missing current-source {label} result."]
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.EMLINK}:
            return None, [f"{prefix} must not be a symlink."]
        return None, [f"{prefix} is unreadable: {error}"]

    failures: list[str] = []
    chunks: list[bytes] = []
    before: os.stat_result | None = None
    after: os.stat_result | None = None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            failures.append(f"{prefix} must be a regular file.")
        elif before.st_nlink != 1:
            failures.append(
                f"{prefix} must have exactly one final directory link."
            )
        total = 0
        while not failures:
            remaining = (
                CURRENT_SOURCE_G6_EVIDENCE_READ_LIMIT_BYTES + 1 - total
            )
            if remaining <= 0:
                failures.append(
                    f"{prefix} exceeds the bounded "
                    f"{CURRENT_SOURCE_G6_EVIDENCE_READ_LIMIT_BYTES}-byte "
                    "read limit."
                )
                break
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
    except OSError as error:
        failures.append(f"{prefix} failed during stable read: {error}")
    finally:
        os.close(descriptor)

    if before is None or after is None:
        return None, failures

    def descriptor_identity(value: os.stat_result) -> tuple[object, ...]:
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

    if descriptor_identity(before) != descriptor_identity(after):
        failures.append(f"{prefix} changed during stable no-follow read.")
    result_bytes = b"".join(chunks)
    if len(result_bytes) != after.st_size:
        failures.append(
            f"{prefix} stable read size {len(result_bytes)} differs from "
            f"descriptor size {after.st_size}."
        )

    try:
        final_path = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        failures.append(f"{prefix} disappeared after stable read.")
    except OSError as error:
        failures.append(f"{prefix} final path readback failed: {error}")
    else:
        if stat.S_ISLNK(final_path.st_mode):
            failures.append(f"{prefix} must not be a symlink.")
        elif not stat.S_ISREG(final_path.st_mode):
            failures.append(f"{prefix} final path must be a regular file.")
        elif descriptor_identity(final_path) != descriptor_identity(after):
            failures.append(
                f"{prefix} final path identity differs from the read "
                "descriptor."
            )
    if failures:
        return None, failures
    return result_bytes, []


def _g6_reproducibility_result_failures(
    result_bytes: bytes,
    *,
    result_contract: G6ReproducibilityResultContract,
    archive_contract: G6ReproducibilityArchiveContract,
) -> list[str]:
    try:
        relative = str(result_contract.path.relative_to(ROOT))
    except ValueError:
        relative = str(result_contract.path)

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (result_contract.size, result_contract.sha256)
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected identity {expected_identity!r}, "
            f"found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("ascii"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{relative}: invalid current-source G6 JSON: {error}"
        )
        return failures
    if not isinstance(result, dict):
        failures.append(
            f"{relative}: current-source G6 root must be an object."
        )
        return failures

    canonical_bytes = (
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    if result_bytes != canonical_bytes:
        failures.append(
            f"{relative}: result must be canonical sorted compact ASCII JSON "
            "with one trailing LF."
        )

    def require_keys(
        value: object,
        path: str,
        expected: set[str],
    ) -> None:
        if not isinstance(value, dict):
            failures.append(f"{relative}: {path} must be an object.")
            return
        actual = set(value)
        if actual != expected:
            failures.append(
                f"{relative}: {path} keys must be exactly "
                f"{sorted(expected)!r}, found {sorted(actual)!r}."
            )

    root_keys = {
        "builds",
        "comparison",
        "executionMode",
        "failure",
        "gradleCache",
        "prepublicationBinding",
        "protectedArchive",
        "publication",
        "releaseId",
        "schemaVersion",
        "scratch",
        "source",
        "status",
        "toolchainPolicy",
    }
    require_keys(result, "root", root_keys)

    missing = object()

    def read_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return missing
            value = value[key]
        return value

    expectations = (
        (("schemaVersion",), 4),
        (("executionMode",), "comparison-only"),
        (("releaseId",), LOCAL_RELEASE_ID),
        (("status",), "passed"),
        (("failure",), None),
        (("prepublicationBinding",), None),
        (
            ("source", "algorithm"),
            "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        ),
        (("source", "fileCount"), archive_contract.source_file_count),
        (
            ("source", "overlaySha256"),
            archive_contract.overlay_sha256,
        ),
        (("source", "sha256"), archive_contract.source_sha256),
        (
            ("scratch", "fixedSwiftPath"),
            "/private/tmp/aetherlink-g6-swift-scratch-v1",
        ),
        (
            ("scratch", "policy"),
            "fixed-owned-flocked-fresh-per-lane-v1",
        ),
        (
            ("scratch", "sourceRoots", "policy"),
            result_contract.source_root_policy,
        ),
        (
            ("scratch", "sourceRoots", "sourceRootByteLengths"),
            {
                "build-a": result_contract.build_a_root_utf8_length,
                "build-b": result_contract.build_b_root_utf8_length,
            },
        ),
        (
            ("scratch", "sourceRoots", "sourceRootLengthsDiffer"),
            result_contract.source_root_lengths_differ,
        ),
        (
            ("gradleCache", "policy"),
            "paired-clones-from-one-stable-seed-v1",
        ),
        (("gradleCache", "pairInitiallyEqual"), True),
        (
            ("toolchainPolicy", "scope"),
            "same-host-fixed-toolchain-cache-snapshot",
        ),
        (("comparison", "archiveBytesEqual"), True),
        (("comparison", "memberBytesEqual"), True),
        (("comparison", "memberMetadataEqual"), True),
        (("comparison", "memberSetEqual"), True),
        (("comparison", "differences"), []),
        (("comparison", "memberDifferences"), []),
        (
            ("comparison", "normalizations"),
            [
                (
                    "android/mapping/configuration.txt:"
                    "declared-extracted-file-root-markers"
                ),
                (
                    "android/mapping/mapping.prt:"
                    "sorted-members-fixed-metadata-deflate-9"
                ),
                (
                    "android/mapping/resources.txt:"
                    "semantic-reachability-sorted-unique-lines"
                ),
                (
                    "android/mapping/seeds.txt:"
                    "bytewise-sorted-unique-lines"
                ),
            ],
        ),
        (("publication", "attempted"), False),
        (("publication", "independentReadback"), False),
        (
            ("publication", "outcome"),
            "disabled-comparison-only",
        ),
        (
            ("publication", "policy"),
            "comparison-only-no-publication",
        ),
        (("publication", "qualifiedArchivePublished"), False),
        (
            ("protectedArchive", "policy"),
            "previous-ledger-entry-archive-v1",
        ),
        (
            ("protectedArchive", "relativePath"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_RELATIVE,
        ),
        (
            ("protectedArchive", "beforeIdentitySha256"),
            archive_contract.protected_archive_identity_sha256,
        ),
        (
            ("protectedArchive", "afterIdentitySha256"),
            archive_contract.protected_archive_identity_sha256,
        ),
        (("protectedArchive", "unchanged"), True),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if not exact_json_values_equal(actual, expected):
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )

    require_keys(
        result.get("source"),
        "source",
        {"algorithm", "fileCount", "overlaySha256", "sha256"},
    )
    require_keys(
        result.get("scratch"),
        "scratch",
        {"fixedSwiftPath", "policy", "sourceRoots"},
    )
    source_roots = read_path(("scratch", "sourceRoots"))
    require_keys(
        source_roots,
        "scratch.sourceRoots",
        {"policy", "sourceRootByteLengths", "sourceRootLengthsDiffer"},
    )
    require_keys(
        result.get("gradleCache"),
        "gradleCache",
        {
            "fileCount",
            "pairInitiallyEqual",
            "policy",
            "seedSnapshotSha256",
        },
    )
    require_keys(
        result.get("toolchainPolicy"),
        "toolchainPolicy",
        {"scope", "swiftArguments"},
    )
    require_keys(
        result.get("comparison"),
        "comparison",
        {
            "archiveBytesEqual",
            "differences",
            "memberBytesEqual",
            "memberDifferences",
            "memberMetadataEqual",
            "memberSetEqual",
            "normalizations",
        },
    )
    require_keys(
        result.get("publication"),
        "publication",
        {
            "attempted",
            "independentReadback",
            "outcome",
            "policy",
            "qualifiedArchivePublished",
        },
    )
    require_keys(
        result.get("protectedArchive"),
        "protectedArchive",
        {
            "afterIdentitySha256",
            "beforeIdentitySha256",
            "policy",
            "relativePath",
            "unchanged",
        },
    )

    gradle_file_count = read_path(("gradleCache", "fileCount"))
    if type(gradle_file_count) is not int or gradle_file_count <= 0:
        failures.append(
            f"{relative}: gradleCache.fileCount must be an exact positive "
            f"integer, found {gradle_file_count!r}."
        )
    gradle_seed = read_path(("gradleCache", "seedSnapshotSha256"))
    if (
        not isinstance(gradle_seed, str)
        or re.fullmatch(r"[0-9a-f]{64}", gradle_seed) is None
    ):
        failures.append(
            f"{relative}: gradleCache.seedSnapshotSha256 must be a lowercase "
            "SHA-256."
        )

    expected_swift_arguments = [
        "--jobs",
        "1",
        "--scratch-path",
        "/private/tmp/aetherlink-g6-swift-scratch-v1",
        "-Xswiftc",
        "-num-threads",
        "-Xswiftc",
        "1",
        "-Xswiftc",
        "-file-prefix-map",
        "-Xswiftc",
        "<PHYSICAL_SOURCE_ROOT>=/aetherlink/source",
        "-Xswiftc",
        "-file-compilation-dir",
        "-Xswiftc",
        "/aetherlink/source",
        "-Xswiftc",
        "-prefix-serialized-debugging-options",
        "-Xcc",
        "-working-directory",
        "-Xcc",
        "/private/tmp/aetherlink-g6-swift-scratch-v1",
        "-Xcc",
        "-Xclang",
        "-Xcc",
        "-fdebug-compilation-dir=/aetherlink/source",
        "-Xcc",
        "-Xclang",
        "-Xcc",
        "-fdisable-module-hash",
        "-Xcc",
        "-Xclang",
        "-Xcc",
        "-fbuild-session-timestamp=0",
        "-Xcc",
        "-Xclang",
        "-Xcc",
        "-fno-pch-timestamp",
        "-Xlinker",
        "-reproducible",
    ]
    swift_arguments = read_path(("toolchainPolicy", "swiftArguments"))
    if not exact_json_values_equal(swift_arguments, expected_swift_arguments):
        failures.append(
            f"{relative}: toolchainPolicy.swiftArguments must match the "
            "complete fixed reproducibility argument list."
        )

    builds = result.get("builds")
    archives: list[dict[str, object]] = []
    if not isinstance(builds, list) or len(builds) != 2:
        failures.append(
            f"{relative}: builds must contain exactly build-a and build-b."
        )
    else:
        for index, expected_id in enumerate(("build-a", "build-b")):
            build = builds[index]
            build_path = f"builds[{index}]"
            require_keys(
                build,
                build_path,
                {"archive", "commandExitCode", "id", "status"},
            )
            if not isinstance(build, dict):
                continue
            for key, expected in (
                ("id", expected_id),
                ("status", "passed"),
                ("commandExitCode", 0),
            ):
                actual = build.get(key, missing)
                if type(actual) is not type(expected) or actual != expected:
                    failures.append(
                        f"{relative}: expected {build_path}.{key}="
                        f"{expected!r}, found {actual!r}."
                    )

            archive = build.get("archive")
            archive_path = f"{build_path}.archive"
            require_keys(
                archive,
                archive_path,
                {
                    "checksumSha256",
                    "manifestSha256",
                    "members",
                    "payloadMemberCount",
                    "sha256",
                    "size",
                    "sourceSha256",
                    "zipEntryCount",
                },
            )
            if not isinstance(archive, dict):
                continue
            archives.append(archive)
            archive_expectations = (
                (
                    "checksumSha256",
                    archive_contract.checksum_sha256,
                ),
                (
                    "manifestSha256",
                    archive_contract.manifest_sha256,
                ),
                ("payloadMemberCount", 29),
                (
                    "sha256",
                    archive_contract.archive_sha256,
                ),
                ("size", archive_contract.archive_size),
                ("sourceSha256", archive_contract.source_sha256),
                ("zipEntryCount", 30),
            )
            for key, expected in archive_expectations:
                actual = archive.get(key, missing)
                if type(actual) is not type(expected) or actual != expected:
                    failures.append(
                        f"{relative}: expected {archive_path}.{key}="
                        f"{expected!r}, found {actual!r}."
                    )

            members = archive.get("members")
            if not isinstance(members, list) or len(members) != 30:
                failures.append(
                    f"{relative}: {archive_path}.members must contain "
                    "exactly 30 entries."
                )
                continue
            paths: list[str] = []
            for member_index, member in enumerate(members):
                member_path = (
                    f"{archive_path}.members[{member_index}]"
                )
                require_keys(
                    member,
                    member_path,
                    {
                        "compressedSize",
                        "compression",
                        "crc32",
                        "externalAttributes",
                        "path",
                        "sha256",
                        "size",
                        "timestamp",
                    },
                )
                if not isinstance(member, dict):
                    continue
                path_value = member.get("path")
                if (
                    not isinstance(path_value, str)
                    or not path_value
                    or not path_value.isascii()
                    or path_value.startswith("/")
                    or any(
                        part in {"", ".", ".."}
                        for part in path_value.split("/")
                    )
                ):
                    failures.append(
                        f"{relative}: {member_path}.path is not a safe "
                        f"relative ASCII member path: {path_value!r}."
                    )
                else:
                    paths.append(path_value)
                for key in (
                    "compressedSize",
                    "compression",
                    "externalAttributes",
                    "size",
                ):
                    value = member.get(key)
                    if type(value) is not int or value < 0:
                        failures.append(
                            f"{relative}: {member_path}.{key} must be an "
                            f"exact non-negative integer, found {value!r}."
                        )
                if member.get("compression") != 0:
                    failures.append(
                        f"{relative}: {member_path}.compression must be 0."
                    )
                if member.get("compressedSize") != member.get("size"):
                    failures.append(
                        f"{relative}: {member_path} stored sizes differ."
                    )
                crc32 = member.get("crc32")
                if (
                    not isinstance(crc32, str)
                    or re.fullmatch(r"[0-9a-f]{8}", crc32) is None
                ):
                    failures.append(
                        f"{relative}: {member_path}.crc32 must be lowercase "
                        "eight-digit hexadecimal."
                    )
                member_sha256 = member.get("sha256")
                if (
                    not isinstance(member_sha256, str)
                    or re.fullmatch(
                        r"[0-9a-f]{64}",
                        member_sha256,
                    )
                    is None
                ):
                    failures.append(
                        f"{relative}: {member_path}.sha256 must be a "
                        "lowercase SHA-256."
                    )
                if not exact_json_values_equal(
                    member.get("timestamp"),
                    [1980, 1, 1, 0, 0, 0],
                ):
                    failures.append(
                        f"{relative}: {member_path}.timestamp must be the "
                        "fixed ZIP epoch."
                    )
            if len(paths) != len(set(paths)):
                failures.append(
                    f"{relative}: {archive_path}.members paths must be unique."
                )
            first_member = members[0]
            if (
                not isinstance(first_member, dict)
                or first_member.get("path") != "manifest.json"
            ):
                failures.append(
                    f"{relative}: {archive_path}.members must start with "
                    "manifest.json."
                )
            elif paths[1:] != sorted(
                paths[1:],
                key=lambda value: value.encode("ascii"),
            ):
                failures.append(
                    f"{relative}: {archive_path}.members after manifest.json "
                    "must retain bytewise path order."
                )
            elif (
                first_member.get("sha256")
                != archive_contract.manifest_sha256
            ):
                failures.append(
                    f"{relative}: {archive_path} embedded manifest SHA-256 "
                    "does not match manifestSha256."
                )

    if len(archives) == 2 and not exact_json_values_equal(
        archives[0],
        archives[1],
    ):
        failures.append(
            f"{relative}: build-a and build-b archive inventories must match "
            "exactly."
        )
    return failures


def current_source_g6_reproducibility_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    result_contract = replace(
        CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT_CONTRACT,
        path=CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT,
    )
    if result_bytes is None:
        result_bytes, read_failures = (
            _stable_current_source_g6_evidence_bytes(
                path=result_contract.path,
                label="G6 recorded lifecycle-parent reproducibility",
            )
        )
        if result_bytes is None:
            return read_failures
    return _g6_reproducibility_result_failures(
        result_bytes,
        result_contract=result_contract,
        archive_contract=CURRENT_SOURCE_G6_REPRODUCIBILITY_ARCHIVE_CONTRACT,
    )


def current_source_g6_swift_root_diagnostic_failures(
    result_bytes_by_label: dict[str, bytes] | None = None,
) -> list[str]:
    contracts = CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS
    expected_labels = {
        "same-physical-root",
        "distinct-equal-utf8-length",
        "distinct-unequal-utf8-length",
        "distinct-unequal-utf8-length-repeat-two",
    }
    actual_labels = {contract.label for contract in contracts}
    failures: list[str] = []
    if actual_labels != expected_labels or len(actual_labels) != len(contracts):
        failures.append(
            "current-source G6 Swift root diagnostic contract labels must be "
            f"exactly {sorted(expected_labels)!r} and unique."
        )
    canonical_result_root = (ROOT / "dist/reproducibility").resolve()
    actual_paths = [contract.path for contract in contracts]
    if len(set(actual_paths)) != len(actual_paths):
        failures.append(
            "current-source G6 Swift root diagnostic contract paths must be "
            "four distinct files."
        )
    for contract in contracts:
        expected_path = canonical_result_root / (
            f"{LOCAL_RELEASE_ID}-swift-root-diagnostic-v1-"
            f"{contract.label}.json"
        )
        if contract.path != expected_path:
            failures.append(
                "current-source G6 Swift root diagnostic contract "
                f"{contract.label!r} must use canonical path "
                f"{expected_path.relative_to(ROOT)}, found "
                f"{contract.path}."
            )

    if result_bytes_by_label is not None:
        supplied_labels = set(result_bytes_by_label)
        if supplied_labels != expected_labels:
            failures.append(
                "current-source G6 Swift root diagnostic payload labels must "
                f"be exactly {sorted(expected_labels)!r}, found "
                f"{sorted(supplied_labels)!r}."
            )

    payloads: dict[str, bytes] = {}
    parsed_results: dict[str, dict[str, object]] = {}
    for contract in contracts:
        if result_bytes_by_label is None:
            payload, read_failures = _stable_current_source_g6_evidence_bytes(
                path=contract.path,
                label=f"G6 Swift root diagnostic {contract.label}",
            )
            failures.extend(read_failures)
            if payload is None:
                continue
        else:
            payload = result_bytes_by_label.get(contract.label)
            if payload is None:
                failures.append(
                    "current-source G6 Swift root diagnostic payload is "
                    f"missing label {contract.label!r}."
                )
                continue
            if type(payload) is not bytes:
                failures.append(
                    "current-source G6 Swift root diagnostic payload "
                    f"{contract.label!r} must be bytes."
                )
                continue
        payloads[contract.label] = payload
        failures.extend(
            _g6_reproducibility_result_failures(
                payload,
                result_contract=contract,
                archive_contract=(
                    CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_ARCHIVE_CONTRACT
                ),
            )
        )
        try:
            parsed = json.loads(
                payload.decode("ascii"),
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except (
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJSONKeyError,
        ):
            continue
        if isinstance(parsed, dict):
            parsed_results[contract.label] = parsed

    first_unequal = payloads.get("distinct-unequal-utf8-length")
    repeat_unequal = payloads.get(
        "distinct-unequal-utf8-length-repeat-two"
    )
    if (
        first_unequal is not None
        and repeat_unequal is not None
        and first_unequal != repeat_unequal
    ):
        failures.append(
            "current-source G6 unequal-root repeat-two result bytes must "
            "exactly equal the first unequal-root result bytes."
        )

    if len(parsed_results) != len(contracts):
        return failures

    ordered_results = [
        parsed_results[contract.label] for contract in contracts
    ]
    baseline_source = ordered_results[0].get("source")
    for contract, result in zip(contracts[1:], ordered_results[1:]):
        if not exact_json_values_equal(result.get("source"), baseline_source):
            failures.append(
                "current-source G6 Swift root diagnostic source objects must "
                f"match exactly; {contract.label!r} differs."
            )

    baseline_comparison = ordered_results[0].get("comparison")
    for contract, result in zip(contracts[1:], ordered_results[1:]):
        if not exact_json_values_equal(
            result.get("comparison"),
            baseline_comparison,
        ):
            failures.append(
                "current-source G6 Swift root diagnostic comparison objects "
                f"must match exactly; {contract.label!r} differs."
            )

    archives: list[tuple[str, object]] = []
    for contract, result in zip(contracts, ordered_results):
        builds = result.get("builds")
        if not isinstance(builds, list) or len(builds) != 2:
            continue
        for build_index, build in enumerate(builds):
            archive = build.get("archive") if isinstance(build, dict) else None
            archives.append(
                (f"{contract.label}/build-{chr(ord('a') + build_index)}", archive)
            )
    if len(archives) == 2 * len(contracts):
        baseline_archive = archives[0][1]
        for label, archive in archives[1:]:
            if not exact_json_values_equal(archive, baseline_archive):
                failures.append(
                    "current-source G6 Swift root diagnostic archives must "
                    f"match exactly across all eight builds; {label!r} differs."
                )
    return failures


def _project_recorded_g6_lifecycle_archive_evidence(
    parent_result: dict[str, object],
) -> clean_release_reproducibility.ArchiveEvidence:
    builds = parent_result["builds"]
    archive = builds[0]["archive"]
    members = archive["members"]
    manifest_member = members[0]

    def recorded_identity(
        *,
        size: int,
        sha256: str,
    ) -> clean_release_reproducibility.FileIdentity:
        return clean_release_reproducibility.FileIdentity(
            device=0,
            inode=0,
            mode=stat.S_IFREG | 0o600,
            uid=0,
            gid=0,
            size=size,
            mtime_ns=0,
            ctime_ns=0,
            sha256=sha256,
        )

    archive_directory = ROOT / "dist/releases" / LOCAL_RELEASE_ID
    return clean_release_reproducibility.ArchiveEvidence(
        archive_directory=archive_directory,
        archive_path=archive_directory / f"{LOCAL_RELEASE_ID}.zip",
        manifest_path=(
            archive_directory / f"{LOCAL_RELEASE_ID}.manifest.json"
        ),
        checksum_path=(
            archive_directory / f"{LOCAL_RELEASE_ID}.zip.sha256"
        ),
        archive_identity=recorded_identity(
            size=archive["size"],
            sha256=archive["sha256"],
        ),
        manifest_identity=recorded_identity(
            size=manifest_member["size"],
            sha256=archive["manifestSha256"],
        ),
        checksum_identity=recorded_identity(
            size=len(
                (
                    f"{archive['sha256']}  {LOCAL_RELEASE_ID}.zip\n"
                ).encode("ascii")
            ),
            sha256=archive["checksumSha256"],
        ),
        zip_entry_count=archive["zipEntryCount"],
        payload_member_count=archive["payloadMemberCount"],
        normalizations=tuple(
            parent_result["comparison"]["normalizations"]
        ),
        source_sha256=archive["sourceSha256"],
        member_inventory=tuple(dict(member) for member in members),
    )


def current_source_g6_lifecycle_two_evidence_failures(
    result_bytes_by_role: dict[str, bytes] | None = None,
) -> list[str]:
    parent_result_contract = replace(
        CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT_CONTRACT,
        path=CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT,
    )
    parent_file_contract = G6LifecycleEvidenceFileContract(
        role="parent",
        path=parent_result_contract.path,
        size=parent_result_contract.size,
        sha256=parent_result_contract.sha256,
    )
    child_contracts = CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS
    contracts = child_contracts + (parent_file_contract,)
    expected_roles = {
        "install",
        "uninstall_reinstall",
        "state_recovery",
        "abrupt_process",
        "abrupt_receipt",
        "idle",
        "parent",
    }
    failures: list[str] = []
    roles = [contract.role for contract in contracts]
    if set(roles) != expected_roles or len(set(roles)) != len(roles):
        failures.append(
            "current-source G6 lifecycle-two roles must be exactly "
            f"{sorted(expected_roles)!r} and unique."
        )

    canonical_paths = (
        clean_release_reproducibility.lane_a_local_dmg_suite_paths(
            CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL,
            expected_release_id=LOCAL_RELEASE_ID,
        )
    )
    expected_child_paths = {
        "install": canonical_paths.install,
        "uninstall_reinstall": canonical_paths.uninstall_reinstall,
        "state_recovery": canonical_paths.state_recovery,
        "abrupt_process": canonical_paths.abrupt_process_state_recovery,
        "abrupt_receipt": (
            canonical_paths.abrupt_process_state_recovery_repeatability
        ),
        "idle": canonical_paths.idle_resource_stability,
    }
    for contract in child_contracts:
        expected_path = expected_child_paths.get(contract.role)
        if contract.path != expected_path:
            failures.append(
                "current-source G6 lifecycle-two role "
                f"{contract.role!r} must use canonical path "
                f"{expected_path}, found {contract.path}."
            )
    expected_parent_path = (
        ROOT
        / "dist/reproducibility"
        / (
            f"{LOCAL_RELEASE_ID}-two-root-v4-prepublication-"
            f"{CURRENT_SOURCE_G6_LIFECYCLE_TWO_LABEL}.json"
        )
    )
    if parent_result_contract.path != expected_parent_path:
        failures.append(
            "current-source G6 lifecycle-two parent must use canonical "
            f"path {expected_parent_path}, found "
            f"{parent_result_contract.path}."
        )
    contract_paths = [contract.path for contract in contracts]
    if len(set(contract_paths)) != len(contract_paths):
        failures.append(
            "current-source G6 lifecycle-two parent+6 paths must be seven "
            "distinct files."
        )

    if result_bytes_by_role is not None:
        supplied_roles = set(result_bytes_by_role)
        if supplied_roles != expected_roles:
            failures.append(
                "current-source G6 lifecycle-two supplied roles must be "
                f"exactly {sorted(expected_roles)!r}, found "
                f"{sorted(repr(role) for role in supplied_roles)!r}."
            )

    payloads: dict[str, bytes] = {}
    for contract in contracts:
        if result_bytes_by_role is None:
            payload, read_failures = _stable_current_source_g6_evidence_bytes(
                path=contract.path,
                label=f"G6 lifecycle-two {contract.role}",
            )
            failures.extend(read_failures)
            if payload is None:
                continue
        else:
            payload = result_bytes_by_role.get(contract.role)
            if payload is None:
                failures.append(
                    "current-source G6 lifecycle-two payload is missing "
                    f"role {contract.role!r}."
                )
                continue
            if type(payload) is not bytes:
                failures.append(
                    "current-source G6 lifecycle-two payload role "
                    f"{contract.role!r} must be bytes."
                )
                continue
        payloads[contract.role] = payload
        identity = (len(payload), hashlib.sha256(payload).hexdigest())
        expected_identity = (contract.size, contract.sha256)
        if identity != expected_identity:
            try:
                relative = contract.path.relative_to(ROOT)
            except ValueError:
                relative = contract.path
            failures.append(
                f"{relative}: expected lifecycle-two "
                f"{contract.role} identity {expected_identity!r}, found "
                f"{identity!r}."
            )

    def reread_parent_commit_marker() -> None:
        if result_bytes_by_role is not None or "parent" not in payloads:
            return
        reread, read_failures = _stable_current_source_g6_evidence_bytes(
            path=parent_result_contract.path,
            label="G6 lifecycle-two parent commit-marker reread",
        )
        failures.extend(read_failures)
        if reread is not None and reread != payloads["parent"]:
            failures.append(
                "current-source G6 lifecycle-two parent commit marker "
                "changed after parent+6 validation."
            )

    parent_bytes = payloads.get("parent")
    if parent_bytes is None:
        return failures
    parent_failures = _g6_reproducibility_result_failures(
        parent_bytes,
        result_contract=parent_result_contract,
        archive_contract=CURRENT_SOURCE_G6_LIFECYCLE_TWO_ARCHIVE_CONTRACT,
    )
    failures.extend(parent_failures)
    if parent_failures or len(payloads) != len(contracts):
        reread_parent_commit_marker()
        return failures

    try:
        parent_result = (
            clean_release_reproducibility.parse_lane_a_lifecycle_result_bytes(
                parent_bytes,
                label="current-source G6 lifecycle-two parent",
            )
        )
        evidence = _project_recorded_g6_lifecycle_archive_evidence(
            parent_result
        )
        parent_source = parent_result["source"]

        install = (
            clean_release_reproducibility
            .validate_lane_a_local_dmg_result_bytes(
                payloads["install"],
                expected_release_id=LOCAL_RELEASE_ID,
                evidence=evidence,
            )
        )
        expected_tree = install["installation"]["tree"]
        uninstall_reinstall = (
            clean_release_reproducibility
            .validate_lane_a_local_dmg_uninstall_reinstall_result_bytes(
                payloads["uninstall_reinstall"],
                expected_release_id=LOCAL_RELEASE_ID,
                evidence=evidence,
                expected_tree=expected_tree,
            )
        )
        state_recovery = (
            clean_release_reproducibility
            .validate_lane_a_local_dmg_state_recovery_result_bytes(
                payloads["state_recovery"],
                expected_release_id=LOCAL_RELEASE_ID,
                evidence=evidence,
                expected_tree=expected_tree,
            )
        )
        abrupt_process = (
            clean_release_reproducibility
            .validate_lane_a_local_dmg_abrupt_process_state_recovery_result_bytes(
                payloads["abrupt_process"],
                state_recovery=state_recovery,
            )
        )
        abrupt_receipt = (
            clean_release_reproducibility
            .validate_lane_a_local_dmg_abrupt_process_repeatability_receipt_bytes(
                payloads["abrupt_receipt"],
                result_path=canonical_paths.abrupt_process_state_recovery,
                result=abrupt_process,
                expected_release_id=LOCAL_RELEASE_ID,
            )
        )
        expected_source_snapshot = {
            key: parent_source[key]
            for key in ("algorithm", "fileCount", "sha256")
        }
        idle = (
            clean_release_reproducibility
            .validate_lane_a_idle_resource_stability_result_bytes(
                payloads["idle"],
                expected_release_id=LOCAL_RELEASE_ID,
                evidence=evidence,
                expected_source_snapshot=expected_source_snapshot,
                expected_tree=expected_tree,
            )
        )
        suite = clean_release_reproducibility.LaneALocalDMGSuiteEvidence(
            paths=canonical_paths,
            archive=evidence,
            expected_release_id=LOCAL_RELEASE_ID,
            install=install,
            uninstall_reinstall=uninstall_reinstall,
            state_recovery=state_recovery,
            abrupt_process_state_recovery=abrupt_process,
            abrupt_process_state_recovery_repeatability=abrupt_receipt,
            idle_resource_stability=idle,
        )
        clean_release_reproducibility.validate_lane_a_suite_parent_binding(
            parent_result=parent_result,
            suite=suite,
            idle_source_snapshot=idle["sourceSnapshot"],
        )
    except (
        clean_release_reproducibility.ReproducibilityError,
        IndexError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        failures.append(
            "current-source G6 lifecycle-two semantic/cross-binding "
            f"validation failed: {error}"
        )

    reread_parent_commit_marker()
    return failures


def macos_clean_home_installed_app_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_CLEAN_HOME_INSTALLED_APP_RUNNER,
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256,
        ),
        (
            MACOS_CLEAN_HOME_INSTALLED_APP_TEST,
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256,
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(f"{relative}: missing clean-HOME source.")
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(
                f"{relative}: unreadable clean-HOME source: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected SHA-256 {expected_sha256}, "
                f"found {actual_sha256}."
            )
    return failures


def macos_clean_home_installed_state_recovery_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER,
            (
                CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_TEST,
            (
                CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256
            ),
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(
                f"{relative}: missing installed state-recovery source."
            )
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(
                f"{relative}: unreadable installed state-recovery source: "
                f"{error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected SHA-256 {expected_sha256}, "
                f"found {actual_sha256}."
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


def macos_packaged_state_recovery_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_PACKAGED_STATE_RECOVERY_RUNNER,
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256,
        ),
        (
            MACOS_PACKAGED_STATE_RECOVERY_TEST,
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_TEST_SHA256,
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(f"{relative}: missing state-recovery source.")
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(
                f"{relative}: unreadable state-recovery source: {error}"
            )
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

    canonical_result = (
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if result_bytes != canonical_result:
        failures.append(
            f"{relative}: packaged-app lifecycle result is not canonical "
            "JSON."
        )

    if not exact_json_values_equal(
        result,
        expected_result,
    ):
        failures.append(
            f"{relative}: result does not match the exact closed "
            f"{build_label} lifecycle contract."
        )
    return failures


def _pinned_current_source_g6_evidence_bytes(
    *,
    path: Path,
    label: str,
    supplied: bytes | None,
) -> tuple[bytes | None, list[str]]:
    if supplied is not None:
        return supplied, []
    return _stable_current_source_g6_evidence_bytes(
        path=path,
        label=label,
    )


def current_source_g6_lane_a_idle_resource_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    path = CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT
    relative = str(path.relative_to(ROOT))
    payload, failures = _pinned_current_source_g6_evidence_bytes(
        path=path,
        label="lane-A idle-resource stability",
        supplied=result_bytes,
    )
    if payload is None:
        return failures
    identity = (len(payload), hashlib.sha256(payload).hexdigest())
    expected_identity = (
        CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT_SIZE,
        CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT_SHA256,
    )
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected identity {expected_identity!r}, found "
            f"{identity!r}."
        )
    try:
        result = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{relative}: invalid current-source idle-resource JSON: "
            f"{error}"
        )
        return failures
    if type(result) is not dict:
        failures.append(f"{relative}: idle-resource root must be an object.")
        return failures
    canonical = (
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    if payload != canonical:
        failures.append(
            f"{relative}: idle-resource result must be canonical sorted "
            "compact ASCII JSON with one trailing LF."
        )

    expected_root_keys = {
        "archiveReadback",
        "artifact",
        "cleanup",
        "environment",
        "isolation",
        "limitations",
        "measurement",
        "process",
        "release",
        "repeatability",
        "schemaVersion",
        "scope",
        "sourceSnapshot",
        "status",
    }
    if set(result) != expected_root_keys:
        failures.append(
            f"{relative}: idle-resource root keys must be exactly "
            f"{sorted(expected_root_keys)!r}."
        )

    expected_release = {
        "archiveSha256": CURRENT_SOURCE_G6_REPRODUCIBLE_ARCHIVE_SHA256,
        "manifestSha256": CURRENT_SOURCE_G6_REPRODUCIBLE_MANIFEST_SHA256,
        "releaseId": LOCAL_RELEASE_ID,
    }
    expected_source = {
        "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        "fileCount": CURRENT_SOURCE_G6_SOURCE_FILE_COUNT,
        "sha256": CURRENT_SOURCE_G6_SOURCE_SHA256,
    }
    expected_tree = CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
        "installation"
    ]["tree"]
    for label, actual, expected in (
        ("schemaVersion", result.get("schemaVersion"), 1),
        (
            "scope",
            result.get("scope"),
            (
                "same-host-per-user-current-source-lane-a-idle-resource-"
                "stability-v1"
            ),
        ),
        ("status", result.get("status"), "passed"),
        ("release", result.get("release"), expected_release),
        ("sourceSnapshot", result.get("sourceSnapshot"), expected_source),
        (
            "artifact.appTree",
            (
                result.get("artifact", {}).get("appTree")
                if type(result.get("artifact")) is dict
                else None
            ),
            expected_tree,
        ),
        (
            "cleanup",
            result.get("cleanup"),
            {
                "ownedChildOnly": True,
                "preexistingApplicationsPreserved": True,
                "temporaryRootRemovedBeforePublication": True,
            },
        ),
        (
            "repeatability",
            result.get("repeatability"),
            {
                "performed": False,
                "reason": "single-live-resource-observation-v1",
            },
        ),
    ):
        if not exact_json_values_equal(actual, expected):
            failures.append(
                f"{relative}: idle-resource {label} must equal "
                f"{expected!r}, found {actual!r}."
            )

    archive_readback = result.get("archiveReadback")
    expected_snapshot = (
        CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT[
            "archiveReadback"
        ]["snapshotFiles"]
    )
    if type(archive_readback) is not dict:
        failures.append(
            f"{relative}: idle-resource archiveReadback must be an object."
        )
    else:
        for key, expected in (
            ("currentSourceCompared", False),
            ("readbackAndExerciseSameSnapshot", True),
            ("signatureVerificationPerformed", False),
            ("snapshotFiles", expected_snapshot),
            ("snapshotFilesUnchangedAfterExercise", True),
            ("status", "passed"),
        ):
            if not exact_json_values_equal(
                archive_readback.get(key),
                expected,
            ):
                failures.append(
                    f"{relative}: idle-resource archiveReadback.{key} "
                    f"must equal {expected!r}."
                )

    measurement = result.get("measurement")
    if type(measurement) is not dict:
        failures.append(
            f"{relative}: idle-resource measurement must be an object."
        )
        return failures
    measurement_expectations = {
        "api": "macos-libproc-proc-pidinfo-v1",
        "baselineWindowSampleCount": 12,
        "finalWindowSampleCount": 12,
        "intervalMilliseconds": 5_000,
        "observationMilliseconds": 600_000,
        "sampleCount": 120,
        "sampleLatenessLimitMilliseconds": 1_000,
        "status": "passed",
        "warmupMilliseconds": 60_000,
    }
    for key, expected in measurement_expectations.items():
        if not exact_json_values_equal(measurement.get(key), expected):
            failures.append(
                f"{relative}: idle-resource measurement.{key} must equal "
                f"{expected!r}."
            )
    run = measurement.get("run")
    if type(run) is not dict:
        failures.append(
            f"{relative}: idle-resource measurement.run must be an object."
        )
        return failures
    run_expectations = {
        "activationPolicy": 0,
        "appKitProcessAbsentAfterReap": True,
        "exitCode": 0,
        "finishedLaunching": True,
        "gracefulTerminationAccepted": True,
        "ownedChildProcess": True,
        "processIdentifierRetained": False,
        "processReaped": True,
    }
    for key, expected in run_expectations.items():
        if not exact_json_values_equal(run.get(key), expected):
            failures.append(
                f"{relative}: idle-resource run.{key} must equal "
                f"{expected!r}."
            )
    samples = run.get("samples")
    if type(samples) is not list or len(samples) != 120:
        failures.append(
            f"{relative}: idle-resource samples must contain exactly 120 "
            "records."
        )
        return failures
    expected_sample_keys = {
        "observedLatenessMilliseconds",
        "openFileDescriptorCount",
        "ordinal",
        "residentBytes",
        "targetElapsedMilliseconds",
        "threadCount",
    }
    valid_samples = True
    for ordinal, sample in enumerate(samples, start=1):
        if type(sample) is not dict or set(sample) != expected_sample_keys:
            failures.append(
                f"{relative}: idle-resource sample {ordinal} has an "
                "invalid closed schema."
            )
            valid_samples = False
            continue
        if (
            type(sample["ordinal"]) is not int
            or sample["ordinal"] != ordinal
            or type(sample["targetElapsedMilliseconds"]) is not int
            or sample["targetElapsedMilliseconds"] != ordinal * 5_000
            or type(sample["observedLatenessMilliseconds"]) is not int
            or not 0 <= sample["observedLatenessMilliseconds"] <= 1_000
        ):
            failures.append(
                f"{relative}: idle-resource sample {ordinal} schedule is "
                "invalid."
            )
            valid_samples = False
        for key in (
            "openFileDescriptorCount",
            "residentBytes",
            "threadCount",
        ):
            if type(sample[key]) is not int or sample[key] <= 0:
                failures.append(
                    f"{relative}: idle-resource sample {ordinal} {key} "
                    "must be an exact positive integer."
                )
                valid_samples = False
    if not valid_samples:
        return failures

    maximum_lateness = max(
        sample["observedLatenessMilliseconds"] for sample in samples
    )
    if not exact_json_values_equal(
        run.get("maximumObservedLatenessMilliseconds"),
        maximum_lateness,
    ):
        failures.append(
            f"{relative}: idle-resource maximum lateness must be "
            "recomputed from samples."
        )

    def upper_median(values: list[int]) -> int:
        ordered = sorted(values)
        return ordered[len(ordered) // 2]

    def metric(
        key: str,
        final_limit: int,
        peak_limit: int,
    ) -> dict[str, object]:
        values = [sample[key] for sample in samples]
        baseline = upper_median(values[:12])
        final = upper_median(values[-12:])
        maximum = max(values)
        final_delta = final - baseline
        peak_delta = maximum - baseline
        return {
            "baselineUpperMedian": baseline,
            "finalDelta": final_delta,
            "finalDeltaLimit": final_limit,
            "finalUpperMedian": final,
            "maximum": maximum,
            "passed": (
                final_delta <= final_limit and peak_delta <= peak_limit
            ),
            "peakDelta": peak_delta,
            "peakDeltaLimit": peak_limit,
        }

    summary = {
        "openFileDescriptors": metric("openFileDescriptorCount", 2, 8),
        "residentBytes": metric(
            "residentBytes",
            32 * 1024 * 1024,
            128 * 1024 * 1024,
        ),
        "threads": metric("threadCount", 2, 8),
    }
    if not exact_json_values_equal(run.get("summary"), summary):
        failures.append(
            f"{relative}: idle-resource summary must equal the independently "
            "recomputed sample summary."
        )
    if any(value["passed"] is not True for value in summary.values()):
        failures.append(
            f"{relative}: idle-resource recomputed regression budgets must "
            "all pass."
        )
    return failures


def current_source_g6_lane_a_local_dmg_evidence_failures(
    result_bytes: bytes | None = None,
    *,
    primary_result_bytes: bytes | None = None,
    uninstall_reinstall_result_bytes: bytes | None = None,
    state_recovery_result_bytes: bytes | None = None,
    abrupt_process_result_bytes: bytes | None = None,
    abrupt_process_receipt_bytes: bytes | None = None,
    idle_resource_result_bytes: bytes | None = None,
) -> list[str]:
    evidence_specs = (
        (
            "primary",
            CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT,
            "G6 two-root primary",
            primary_result_bytes,
        ),
        (
            "install",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT,
            "lane-A local-DMG install",
            result_bytes,
        ),
        (
            "uninstall_reinstall",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT,
            "lane-A local-DMG uninstall/reinstall",
            uninstall_reinstall_result_bytes,
        ),
        (
            "state_recovery",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT,
            "lane-A local-DMG state recovery",
            state_recovery_result_bytes,
        ),
        (
            "abrupt_process",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT,
            "lane-A local-DMG abrupt-process state recovery",
            abrupt_process_result_bytes,
        ),
        (
            "abrupt_process_receipt",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT,
            "lane-A local-DMG abrupt-process repeatability receipt",
            abrupt_process_receipt_bytes,
        ),
        (
            "idle_resource",
            CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT,
            "lane-A idle-resource stability",
            idle_resource_result_bytes,
        ),
    )
    failures: list[str] = []
    pinned: dict[str, bytes] = {}
    for key, path, label, supplied in evidence_specs:
        payload, read_failures = _pinned_current_source_g6_evidence_bytes(
            path=path,
            label=label,
            supplied=supplied,
        )
        failures.extend(read_failures)
        if payload is not None:
            pinned[key] = payload

    primary_bytes = pinned.get("primary")
    if primary_bytes is not None:
        failures.extend(
            current_source_g6_reproducibility_failures(primary_bytes)
        )

    idle_bytes = pinned.get("idle_resource")
    if idle_bytes is not None:
        failures.extend(
            current_source_g6_lane_a_idle_resource_evidence_failures(
                idle_bytes
            )
        )

    lifecycle_contracts = (
        (
            "install",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT_SIZE,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT_SHA256,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_EXPECTED_RESULT,
            "current-source G6 exact lane-A local-DMG install v2",
        ),
        (
            "uninstall_reinstall",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT_SIZE,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT_SHA256,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT,
            (
                "current-source G6 exact lane-A local-DMG "
                "uninstall/reinstall v1"
            ),
        ),
        (
            "state_recovery",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT_SIZE,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT_SHA256,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_EXPECTED_RESULT,
            (
                "current-source G6 exact lane-A local-DMG state recovery "
                "v1"
            ),
        ),
        (
            "abrupt_process",
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SIZE,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT_SHA256,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_EXPECTED_RESULT,
            (
                "current-source G6 exact lane-A local-DMG abrupt-process "
                "state recovery v1"
            ),
        ),
    )
    parsed_lifecycle: dict[str, dict[str, object]] = {}
    for key, path, size, sha256, expected, label in lifecycle_contracts:
        payload = pinned.get(key)
        if payload is None:
            continue
        relative = str(path.relative_to(ROOT))
        failures.extend(
            packaged_lifecycle_evidence_failures(
                result_path=path,
                relative=relative,
                expected_size=size,
                expected_sha256=sha256,
                expected_result=expected,
                build_label=label,
                result_bytes=payload,
            )
        )
        try:
            parsed = json.loads(
                payload.decode("ascii"),
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except (
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJSONKeyError,
        ):
            continue
        if isinstance(parsed, dict):
            parsed_lifecycle[key] = parsed

    parsed_receipt: dict[str, object] | None = None
    receipt_bytes = pinned.get("abrupt_process_receipt")
    if receipt_bytes is not None:
        receipt_path = (
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT
        )
        failures.extend(
            packaged_lifecycle_evidence_failures(
                result_path=receipt_path,
                relative=str(receipt_path.relative_to(ROOT)),
                expected_size=(
                    CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT_SIZE
                ),
                expected_sha256=(
                    CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT_SHA256
                ),
                expected_result=(
                    CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_EXPECTED_RECEIPT
                ),
                build_label=(
                    "current-source G6 exact lane-A local-DMG "
                    "abrupt-process repeatability v1"
                ),
                result_bytes=receipt_bytes,
            )
        )
        try:
            parsed = json.loads(
                receipt_bytes.decode("ascii"),
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except (
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJSONKeyError,
        ):
            pass
        else:
            if isinstance(parsed, dict):
                parsed_receipt = parsed

    parsed_idle: dict[str, object] | None = None
    if idle_bytes is not None:
        try:
            parsed = json.loads(
                idle_bytes.decode("ascii"),
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except (
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJSONKeyError,
        ):
            pass
        else:
            if isinstance(parsed, dict):
                parsed_idle = parsed

    if (
        primary_bytes is None
        or len(parsed_lifecycle) != 4
        or parsed_receipt is None
        or parsed_idle is None
    ):
        return failures
    try:
        primary_result = json.loads(
            primary_bytes.decode("ascii"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        if type(primary_result) is not dict:
            raise ValueError("primary root is not an object")
        primary_builds = primary_result["builds"]
        if type(primary_builds) is not list or len(primary_builds) != 2:
            raise ValueError("primary builds are not the exact A/B pair")
        build_a = primary_builds[0]
        build_b = primary_builds[1]
        if type(build_a) is not dict or type(build_b) is not dict:
            raise ValueError("primary build record is not an object")
        primary_archive = build_a["archive"]
        build_b_archive = build_b["archive"]
        if (
            type(primary_archive) is not dict
            or type(build_b_archive) is not dict
        ):
            raise ValueError("primary archive projection is not an object")
        if not exact_json_values_equal(primary_archive, build_b_archive):
            raise ValueError("primary A/B archive inventories differ")
        primary_members = primary_archive["members"]
        if type(primary_members) is not list or not primary_members:
            raise ValueError("primary member inventory is invalid")
        primary_manifest_member = primary_members[0]
        if (
            type(primary_manifest_member) is not dict
            or primary_manifest_member.get("path") != "manifest.json"
        ):
            raise ValueError("primary manifest member is invalid")
        archive_sha256 = primary_archive["sha256"]
        archive_size = primary_archive["size"]
        manifest_sha256 = primary_archive["manifestSha256"]
        manifest_size = primary_manifest_member["size"]
        checksum_sha256 = primary_archive["checksumSha256"]
        if (
            type(archive_sha256) is not str
            or type(archive_size) is not int
            or type(manifest_sha256) is not str
            or type(manifest_size) is not int
            or type(checksum_sha256) is not str
        ):
            raise ValueError("primary archive identity types are invalid")
    except (
        UnicodeError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            "current-source G6 lifecycle suite cannot project the pinned "
            f"two-root primary result: {error}"
        )
        return failures

    expected_release = {
        "archiveSha256": archive_sha256,
        "manifestSha256": manifest_sha256,
        "releaseId": LOCAL_RELEASE_ID,
    }
    expected_snapshot_files = {
        f"{LOCAL_RELEASE_ID}.manifest.json": {
            "sha256": manifest_sha256,
            "size": manifest_size,
        },
        f"{LOCAL_RELEASE_ID}.zip": {
            "sha256": archive_sha256,
            "size": archive_size,
        },
        f"{LOCAL_RELEASE_ID}.zip.sha256": {
            "sha256": checksum_sha256,
            "size": len(
                f"{archive_sha256}  {LOCAL_RELEASE_ID}.zip\n".encode(
                    "ascii"
                )
            ),
        },
    }
    for key, path, *_ in lifecycle_contracts:
        result = parsed_lifecycle[key]
        relative = str(path.relative_to(ROOT))
        if not exact_json_values_equal(
            result.get("release"),
            expected_release,
        ):
            failures.append(
                f"{relative}: lane-A lifecycle release identity must "
                "cross-bind the pinned current-source two-root archive and "
                "manifest."
            )
        archive_readback = result.get("archiveReadback")
        if (
            not isinstance(archive_readback, dict)
            or not exact_json_values_equal(
                archive_readback.get("snapshotFiles"),
                expected_snapshot_files,
            )
        ):
            failures.append(
                f"{relative}: lane-A lifecycle snapshot identities must "
                "cross-bind the pinned current-source two-root ZIP, "
                "manifest, and checksum."
            )

    install = parsed_lifecycle["install"]
    uninstall_reinstall = parsed_lifecycle["uninstall_reinstall"]
    state_recovery = parsed_lifecycle["state_recovery"]
    abrupt_process = parsed_lifecycle["abrupt_process"]
    install_readback = install.get("archiveReadback")
    install_tree = (
        install.get("installation", {}).get("tree")
        if isinstance(install.get("installation"), dict)
        else None
    )
    for key, result in (
        ("uninstall/reinstall", uninstall_reinstall),
        ("state recovery", state_recovery),
        ("abrupt-process state recovery", abrupt_process),
    ):
        if not exact_json_values_equal(
            result.get("archiveReadback"),
            install_readback,
        ):
            failures.append(
                "current-source G6 lane-A lifecycle archiveReadback must be "
                f"identical across install and {key}."
            )
        installation = result.get("installation")
        tree = (
            installation.get("tree")
            if isinstance(installation, dict)
            else None
        )
        if not exact_json_values_equal(tree, install_tree):
            failures.append(
                "current-source G6 lane-A installed tree must be identical "
                f"across install and {key}."
            )
    for label, result in (
        ("state recovery", state_recovery),
        ("abrupt-process state recovery", abrupt_process),
    ):
        if not exact_json_values_equal(
            result.get("uninstall"),
            uninstall_reinstall.get("uninstall"),
        ):
            failures.append(
                "current-source G6 lane-A uninstall contract must be "
                "identical across uninstall/reinstall and "
                f"{label}."
            )

    abrupt_bytes = pinned["abrupt_process"]
    abrupt_identity = {
        "fileName": (
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT.name
        ),
        "sha256": hashlib.sha256(abrupt_bytes).hexdigest(),
        "size": len(abrupt_bytes),
    }
    if not exact_json_values_equal(
        parsed_receipt.get("canonicalResult"),
        abrupt_identity,
    ):
        failures.append(
            "current-source G6 lane-A abrupt-process repeatability receipt "
            "must bind the pinned canonical result filename, size, and "
            "SHA-256."
        )
    expected_runs = [
        {
            "ordinal": ordinal,
            "sha256": abrupt_identity["sha256"],
            "size": abrupt_identity["size"],
            "status": "passed",
        }
        for ordinal in (1, 2)
    ]
    if not exact_json_values_equal(
        parsed_receipt.get("runs"),
        expected_runs,
    ):
        failures.append(
            "current-source G6 lane-A abrupt-process repeatability receipt "
            "must bind both independent runs to the pinned canonical result."
        )
    if parsed_receipt.get("releaseId") != LOCAL_RELEASE_ID:
        failures.append(
            "current-source G6 lane-A abrupt-process repeatability receipt "
            "must bind the current release ID."
        )

    idle_relative = str(
        CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT.relative_to(ROOT)
    )
    if not exact_json_values_equal(
        parsed_idle.get("release"),
        expected_release,
    ):
        failures.append(
            f"{idle_relative}: idle-resource release identity must "
            "cross-bind the pinned current-source two-root archive and "
            "manifest."
        )
    idle_readback = parsed_idle.get("archiveReadback")
    if (
        not isinstance(idle_readback, dict)
        or not exact_json_values_equal(
            idle_readback.get("snapshotFiles"),
            expected_snapshot_files,
        )
    ):
        failures.append(
            f"{idle_relative}: idle-resource snapshot identities must "
            "cross-bind the pinned current-source two-root ZIP, manifest, "
            "and checksum."
        )
    idle_artifact = parsed_idle.get("artifact")
    idle_tree = (
        idle_artifact.get("appTree")
        if isinstance(idle_artifact, dict)
        else None
    )
    if not exact_json_values_equal(idle_tree, install_tree):
        failures.append(
            f"{idle_relative}: idle-resource app tree must cross-bind the "
            "pinned lane-A install tree."
        )
    primary_source = primary_result.get("source")
    expected_idle_source = (
        {
            "algorithm": primary_source.get("algorithm"),
            "fileCount": primary_source.get("fileCount"),
            "sha256": primary_source.get("sha256"),
        }
        if isinstance(primary_source, dict)
        else None
    )
    if not exact_json_values_equal(
        parsed_idle.get("sourceSnapshot"),
        expected_idle_source,
    ):
        failures.append(
            f"{idle_relative}: idle-resource source snapshot must "
            "cross-bind the parent current-source identity."
        )
    return failures


def macos_clean_home_installed_app_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_CLEAN_HOME_INSTALLED_APP_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-14-clean-home-install-v1.json"
        ),
        expected_size=(
            MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256
        ),
        expected_result=MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT,
        build_label="historical Build 14 clean-HOME installed-app",
        result_bytes=result_bytes,
    )


def current_macos_clean_home_installed_app_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-install-v1.json"
        ),
        expected_size=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256
        ),
        expected_result=CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT,
        build_label="historical Build 20 clean-HOME installed-app",
        result_bytes=result_bytes,
    )


def macos_clean_home_installed_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-14-clean-home-state-recovery-v1.json"
        ),
        expected_size=(
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
        ),
        build_label="historical Build 14 clean-HOME installed state-recovery",
        result_bytes=result_bytes,
    )


def current_macos_clean_home_installed_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
        ),
        expected_size=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
        ),
        build_label="historical Build 20 clean-HOME installed state-recovery",
        result_bytes=result_bytes,
    )


def current_build24_macos_clean_home_installed_app_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-24-clean-home-install-v1.json"
        ),
        expected_size=(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT
        ),
        build_label="current Build 24 clean-HOME installed-app",
        result_bytes=result_bytes,
    )


def current_build24_macos_clean_home_installed_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT
        ),
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-24-clean-home-state-recovery-v1.json"
        ),
        expected_size=(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
        ),
        build_label="current Build 24 clean-HOME installed state-recovery",
        result_bytes=result_bytes,
    )


def current_macos_local_dmg_install_evidence_failures(
    result_bytes: bytes | None = None,
    source_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    relative = str(CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT.relative_to(ROOT))
    failures: list[str] = []

    for path, expected_sha256 in (
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_TEST,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256,
        ),
    ):
        try:
            payload = (
                source_bytes_by_path[path]
                if source_bytes_by_path is not None
                else path.read_bytes()
            )
        except (KeyError, OSError) as error:
            failures.append(
                f"{path.relative_to(ROOT)}: cannot read local DMG source: "
                f"{error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{path.relative_to(ROOT)}: expected local DMG source "
                f"SHA-256 {expected_sha256}, found {actual_sha256}."
            )

    if result_bytes is None:
        try:
            result_bytes = CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT.read_bytes()
        except OSError as error:
            failures.append(f"{relative}: cannot read local DMG result: {error}")
            return failures

    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE,
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256,
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
        failures.append(f"{relative}: invalid local DMG result JSON: {error}")
        return failures
    if not isinstance(result, dict):
        failures.append(f"{relative}: local DMG result root must be an object.")
        return failures

    def read_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    expectations = (
        (("schemaVersion",), 1),
        (("status",), "passed"),
        (("scope",), "same-host-per-user-ephemeral-local-dmg-install-v1"),
        (("release", "releaseId"), HISTORICAL_BUILD20_RELEASE_ID),
        (
            ("release", "archiveSha256"),
            HISTORICAL_BUILD20_ARCHIVE_SHA256,
        ),
        (
            ("release", "manifestSha256"),
            HISTORICAL_BUILD20_MANIFEST_SHA256,
        ),
        (("image", "filesystem"), "HFS+"),
        (("image", "format"), "UDZO"),
        (("image", "verified"), True),
        (("image", "ephemeral"), True),
        (("image", "retained"), False),
        (("mount", "readOnly"), True),
        (("mount", "exactFreshMountpoint"), True),
        (("mount", "detachedBeforeLaunch"), True),
        (("mount", "unmountedVerified"), True),
        (("installation", "exactReleaseTreeCopied"), True),
        (("launchServices", "distinctProcessIdentifiers"), True),
        (("state", "databaseCount"), 3),
        (("state", "integrityChecks"), "passed"),
        (("state", "stableAcrossRelaunch"), True),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )

    runs = read_path(("launchServices", "runs"))
    if not isinstance(runs, list) or len(runs) != 2:
        failures.append(
            f"{relative}: launchServices.runs must contain two launches."
        )
    limitations = result.get("limitations")
    required_limitations = {
        "not-finder-ui-or-drag-and-drop-evidence",
        "not-developer-id-notarized-or-stapled-distribution",
        "not-gatekeeper-quarantine-or-download-evidence",
        "not-clean-machine-account-or-system-applications",
        "not-upgrade-n-or-n-minus-one-rollback-production-or-security-evidence",
    }
    if not isinstance(limitations, list) or not required_limitations.issubset(
        {item for item in limitations if isinstance(item, str)}
    ):
        failures.append(
            f"{relative}: local DMG result lost required scope limitations."
        )
    return failures


def current_build24_macos_local_dmg_install_evidence_failures(
    result_bytes: bytes | None = None,
    source_bytes_by_path: dict[Path, bytes] | None = None,
    release_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    relative = str(
        CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RESULT.relative_to(ROOT)
    )
    failures: list[str] = []
    expected_sources = (
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_TEST,
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256,
        ),
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
            CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256,
        ),
    )
    for path, expected_sha256 in expected_sources:
        try:
            payload = (
                source_bytes_by_path[path]
                if source_bytes_by_path is not None
                else path.read_bytes()
            )
            actual_sha256 = hashlib.sha256(payload).hexdigest()
        except (KeyError, OSError, TypeError) as error:
            failures.append(
                f"{path.relative_to(ROOT)}: cannot read current Build 24 "
                f"local DMG source: {error}"
            )
            continue
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{path.relative_to(ROOT)}: expected current Build 24 local "
                f"DMG source SHA-256 {expected_sha256}, found "
                f"{actual_sha256}."
            )

    failures.extend(
        packaged_lifecycle_evidence_failures(
            result_path=CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RESULT,
            relative=relative,
            expected_size=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE
            ),
            expected_sha256=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256
            ),
            expected_result=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT
            ),
            build_label="current Build 24 local-DMG v2",
            result_bytes=result_bytes,
        )
    )

    if result_bytes is None:
        try:
            result_bytes = (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RESULT.read_bytes()
            )
        except OSError:
            return failures
    try:
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ):
        return failures
    if not isinstance(result, dict):
        return failures

    archive_path = LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip"
    manifest_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.manifest.json"
    )
    checksum_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip.sha256"
    )
    release_paths = (archive_path, manifest_path, checksum_path)
    if (
        release_bytes_by_path is not None
        and set(release_bytes_by_path) != set(release_paths)
    ):
        failures.append(
            f"{relative}: injected Build 24 release byte map must contain "
            "exactly the ZIP, manifest, and checksum sidecar."
        )
        return failures

    def streamed_identity(path: Path) -> dict[str, object]:
        if release_bytes_by_path is not None:
            payload = release_bytes_by_path[path]
            if type(payload) is not bytes:
                raise TypeError("injected release payload must be bytes")
            return {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while True:
                payload = handle.read(1_024 * 1_024)
                if not payload:
                    break
                digest.update(payload)
                size += len(payload)
        return {"sha256": digest.hexdigest(), "size": size}

    def exact_bytes(path: Path) -> bytes:
        if release_bytes_by_path is not None:
            payload = release_bytes_by_path[path]
            if type(payload) is not bytes:
                raise TypeError("injected release payload must be bytes")
            return payload
        return path.read_bytes()

    try:
        archive_identity = streamed_identity(archive_path)
        manifest_bytes = exact_bytes(manifest_path)
        checksum_bytes = exact_bytes(checksum_path)
        manifest_identity = {
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "size": len(manifest_bytes),
        }
        checksum_identity = {
            "sha256": hashlib.sha256(checksum_bytes).hexdigest(),
            "size": len(checksum_bytes),
        }
        manifest = json.loads(
            manifest_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{relative}: cannot cross-bind retained Build 24 release "
            f"bytes: {error}"
        )
        return failures

    expected_checksum = (
        f"{archive_identity['sha256']}  {archive_path.name}\n"
    ).encode("ascii")
    if checksum_bytes != expected_checksum:
        failures.append(
            f"{relative}: Build 24 checksum sidecar differs from the "
            "retained ZIP identity."
        )

    readback = result.get("archiveReadback")
    release = result.get("release")
    if not isinstance(readback, dict) or not isinstance(release, dict):
        failures.append(
            f"{relative}: local DMG release/readback projection is invalid."
        )
        return failures
    expected_snapshot_files = {
        archive_path.name: archive_identity,
        manifest_path.name: manifest_identity,
        checksum_path.name: checksum_identity,
    }
    if not exact_json_values_equal(
        readback.get("snapshotFiles"),
        expected_snapshot_files,
    ):
        failures.append(
            f"{relative}: snapshot identities do not match the retained "
            "Build 24 release files."
        )
    expected_release = {
        "archiveSha256": archive_identity["sha256"],
        "manifestSha256": manifest_identity["sha256"],
        "releaseId": LOCAL_RELEASE_ID,
    }
    if not exact_json_values_equal(release, expected_release):
        failures.append(
            f"{relative}: release identity does not match the retained "
            "Build 24 archive."
        )

    def manifest_value(path: tuple[str, ...]) -> object:
        value: object = manifest
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    for path, expected in (
        (("release", "releaseId"), LOCAL_RELEASE_ID),
        (("release", "buildNumber"), LOCAL_RELEASE_BUILD_NUMBER),
        (("release", "marketingVersion"), LOCAL_RELEASE_MARKETING_VERSION),
        (("platforms", "macos", "bundleId"), "dev.aetherlink.companion"),
        (
            ("platforms", "macos", "buildNumber"),
            LOCAL_RELEASE_BUILD_NUMBER,
        ),
        (
            ("platforms", "macos", "marketingVersion"),
            LOCAL_RELEASE_MARKETING_VERSION,
        ),
    ):
        actual = manifest_value(path)
        if not exact_json_values_equal(actual, expected):
            failures.append(
                f"{relative}: retained Build 24 manifest "
                f"{'.'.join(path)} differs from the result projection."
            )

    members = manifest_value(("members",))
    app_prefix = "macos/AetherLink.app/"
    app_members = (
        [
            row
            for row in members
            if isinstance(row, dict)
            and isinstance(row.get("path"), str)
            and row["path"].startswith(app_prefix)
        ]
        if isinstance(members, list)
        else []
    )
    tree_digest = hashlib.sha256()
    tree_total = 0
    tree_valid = True
    seen_paths: set[str] = set()
    for row in sorted(app_members, key=lambda item: str(item.get("path"))):
        member_path = row.get("path")
        mode = row.get("mode")
        size = row.get("size")
        sha256 = row.get("sha256")
        if (
            not isinstance(member_path, str)
            or member_path in seen_paths
            or not isinstance(mode, str)
            or re.fullmatch(r"0[0-7]{3}", mode) is None
            or type(size) is not int
            or size < 0
            or not isinstance(sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
        ):
            tree_valid = False
            break
        seen_paths.add(member_path)
        tree_digest.update(member_path.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(mode.encode("ascii"))
        tree_digest.update(b"\0")
        tree_digest.update(str(size).encode("ascii"))
        tree_digest.update(b"\0")
        tree_digest.update(sha256.encode("ascii"))
        tree_digest.update(b"\n")
        tree_total += size
    expected_tree = {
        "digestAlgorithm": (
            "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
        ),
        "regularFileCount": len(app_members),
        "sha256": tree_digest.hexdigest(),
        "totalRegularFileBytes": tree_total,
    }
    installation = result.get("installation")
    actual_tree = (
        installation.get("tree")
        if isinstance(installation, dict)
        else None
    )
    if (
        not tree_valid
        or not app_members
        or not exact_json_values_equal(actual_tree, expected_tree)
    ):
        failures.append(
            f"{relative}: installed app tree does not derive from the "
            "retained Build 24 manifest."
        )
    return failures


def current_build24_macos_local_dmg_uninstall_reinstall_evidence_failures(
    result_bytes: bytes | None = None,
    source_bytes_by_path: dict[Path, bytes] | None = None,
    release_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    relative = str(
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT.relative_to(
            ROOT
        )
    )
    failures: list[str] = []
    expected_sources = (
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_TEST,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_TEST_SHA256
            ),
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER,
            (
                CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
            CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256,
        ),
    )
    expected_sha256_by_path = dict(expected_sources)
    actual_sha256_by_path: dict[Path, str] = {}
    expected_paths = {path for path, _ in expected_sources}
    if (
        source_bytes_by_path is not None
        and set(source_bytes_by_path) != expected_paths
    ):
        failures.append(
            f"{relative}: injected uninstall/reinstall source byte map must "
            "contain exactly the six bound source files."
        )
    for path, expected_sha256 in expected_sources:
        try:
            payload = (
                source_bytes_by_path[path]
                if source_bytes_by_path is not None
                else path.read_bytes()
            )
            if type(payload) is not bytes:
                raise TypeError("injected source payload must be bytes")
        except (KeyError, OSError, TypeError) as error:
            failures.append(
                f"{path.relative_to(ROOT)}: cannot read current Build 24 "
                f"same-DMG uninstall/reinstall source: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        actual_sha256_by_path[path] = actual_sha256
        if not lifecycle_source_sha256_is_bound(
            path,
            actual_sha256,
            expected_sha256,
        ):
            failures.append(
                f"{path.relative_to(ROOT)}: expected current Build 24 "
                "same-DMG uninstall/reinstall source SHA-256 "
                f"{expected_sha256} or its exact current-source G6 "
                f"successor, found {actual_sha256}."
            )
    if not lifecycle_source_sha256_set_is_bound(
        actual_sha256_by_path,
        expected_sha256_by_path,
    ):
        failures.append(
            f"{relative}: bound uninstall/reinstall source SHA-256 values "
            "must match one complete historical or current-source G6 "
            "successor tuple."
        )

    failures.extend(
        packaged_lifecycle_evidence_failures(
            result_path=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT
            ),
            relative=relative,
            expected_size=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT_SIZE
            ),
            expected_sha256=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT_SHA256
            ),
            expected_result=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT
            ),
            build_label=(
                "current Build 24 same-DMG uninstall/reinstall v1"
            ),
            result_bytes=result_bytes,
        )
    )
    failures.extend(
        current_build24_macos_local_dmg_install_evidence_failures(
            release_bytes_by_path=release_bytes_by_path,
        )
    )
    return failures


def current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
    source_bytes_by_path: dict[Path, bytes] | None = None,
    release_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    relative = str(
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RESULT.relative_to(
            ROOT
        )
    )
    failures: list[str] = []
    expected_sources = (
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RUNNER,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_TEST,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_TEST_SHA256
            ),
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER,
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            MACOS_PACKAGED_STATE_RECOVERY_RUNNER,
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER,
            (
                CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
            CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256,
        ),
    )
    expected_sha256_by_path = dict(expected_sources)
    actual_sha256_by_path: dict[Path, str] = {}
    expected_paths = {path for path, _ in expected_sources}
    if (
        source_bytes_by_path is not None
        and set(source_bytes_by_path) != expected_paths
    ):
        failures.append(
            f"{relative}: injected state-recovery source byte map must "
            "contain exactly the nine bound source files."
        )
    for path, expected_sha256 in expected_sources:
        try:
            payload = (
                source_bytes_by_path[path]
                if source_bytes_by_path is not None
                else path.read_bytes()
            )
            if type(payload) is not bytes:
                raise TypeError("injected source payload must be bytes")
        except (KeyError, OSError, TypeError) as error:
            failures.append(
                f"{path.relative_to(ROOT)}: cannot read current Build 24 "
                f"same-DMG state-recovery source: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        actual_sha256_by_path[path] = actual_sha256
        if not lifecycle_source_sha256_is_bound(
            path,
            actual_sha256,
            expected_sha256,
        ):
            failures.append(
                f"{path.relative_to(ROOT)}: expected current Build 24 "
                "same-DMG state-recovery source SHA-256 "
                f"{expected_sha256} or its exact current-source G6 "
                f"successor, found {actual_sha256}."
            )
    if not lifecycle_source_sha256_set_is_bound(
        actual_sha256_by_path,
        expected_sha256_by_path,
    ):
        failures.append(
            f"{relative}: bound state-recovery source SHA-256 values must "
            "match one complete historical or current-source G6 successor "
            "tuple."
        )

    failures.extend(
        packaged_lifecycle_evidence_failures(
            result_path=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RESULT
            ),
            relative=relative,
            expected_size=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT_SIZE
            ),
            expected_sha256=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT_SHA256
            ),
            expected_result=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT
            ),
            build_label=(
                "current Build 24 same-DMG uninstall/reinstall "
                "state-recovery v1"
            ),
            result_bytes=result_bytes,
        )
    )
    failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_evidence_failures(
            release_bytes_by_path=release_bytes_by_path,
        )
    )
    failures.extend(
        current_build24_macos_clean_home_installed_state_recovery_evidence_failures(
            result_bytes=None,
        )
    )
    return failures


def current_build24_macos_local_dmg_abrupt_process_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
    receipt_bytes: bytes | None = None,
    source_bytes_by_path: dict[Path, bytes] | None = None,
    release_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    relative = str(
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RESULT.relative_to(
            ROOT
        )
    )
    receipt_relative = str(
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RECEIPT.relative_to(
            ROOT
        )
    )
    failures: list[str] = []
    expected_sources = (
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RUNNER,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_TEST,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_TEST_SHA256
            ),
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RUNNER,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER,
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            MACOS_PACKAGED_STATE_RECOVERY_RUNNER,
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER,
            (
                CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
            CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256,
        ),
    )
    expected_sha256_by_path = dict(expected_sources)
    actual_sha256_by_path: dict[Path, str] = {}
    expected_paths = {path for path, _ in expected_sources}
    if (
        source_bytes_by_path is not None
        and set(source_bytes_by_path) != expected_paths
    ):
        failures.append(
            f"{relative}: injected abrupt-process source byte map must "
            "contain exactly the ten bound source files."
        )
    for path, expected_sha256 in expected_sources:
        try:
            payload = (
                source_bytes_by_path[path]
                if source_bytes_by_path is not None
                else path.read_bytes()
            )
            if type(payload) is not bytes:
                raise TypeError("injected source payload must be bytes")
        except (KeyError, OSError, TypeError) as error:
            failures.append(
                f"{path.relative_to(ROOT)}: cannot read current Build 24 "
                f"abrupt-process state-recovery source: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        actual_sha256_by_path[path] = actual_sha256
        if not lifecycle_source_sha256_is_bound(
            path,
            actual_sha256,
            expected_sha256,
        ):
            failures.append(
                f"{path.relative_to(ROOT)}: expected current Build 24 "
                "abrupt-process state-recovery source SHA-256 "
                f"{expected_sha256} or its exact current-source G6 "
                f"successor, found {actual_sha256}."
            )
    if not lifecycle_source_sha256_set_is_bound(
        actual_sha256_by_path,
        expected_sha256_by_path,
    ):
        failures.append(
            f"{relative}: bound abrupt-process source SHA-256 values must "
            "match one complete historical or current-source G6 successor "
            "tuple."
        )

    failures.extend(
        packaged_lifecycle_evidence_failures(
            result_path=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RESULT
            ),
            relative=relative,
            expected_size=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SIZE
            ),
            expected_sha256=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT_SHA256
            ),
            expected_result=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RESULT
            ),
            build_label=(
                "current Build 24 same-DMG post-commit abrupt-process "
                "state-recovery v1"
            ),
            result_bytes=result_bytes,
        )
    )
    failures.extend(
        packaged_lifecycle_evidence_failures(
            result_path=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RECEIPT
            ),
            relative=receipt_relative,
            expected_size=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RECEIPT_SIZE
            ),
            expected_sha256=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RECEIPT_SHA256
            ),
            expected_result=(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_EXPECTED_RECEIPT
            ),
            build_label=(
                "current Build 24 abrupt-process state-recovery "
                "repeatability v1"
            ),
            result_bytes=receipt_bytes,
        )
    )
    failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_evidence_failures(
            release_bytes_by_path=release_bytes_by_path,
        )
    )
    return failures


def current_build24_macos_lifecycle_aggregate_evidence_failures(
    *,
    source_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    expected_sources = (
        (
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_CHECKER,
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_CHECKER_SIZE,
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_CHECKER_SHA256,
            "checker",
        ),
        (
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_TEST,
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_TEST_SIZE,
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_TEST_SHA256,
            "test",
        ),
    )
    expected_paths = {path for path, _, _, _ in expected_sources}
    failures: list[str] = []
    if (
        source_bytes_by_path is not None
        and set(source_bytes_by_path) != expected_paths
    ):
        failures.append(
            "script/check_macos_build24_lifecycle_evidence.py: injected "
            "aggregate source byte map must contain exactly the checker "
            "and test files."
        )

    for path, expected_size, expected_sha256, label in expected_sources:
        relative = str(path.relative_to(ROOT))
        try:
            if source_bytes_by_path is None:
                if path.is_symlink() or not path.is_file():
                    raise OSError(
                        "path must be a non-symlink regular file"
                    )
                payload = path.read_bytes()
            else:
                payload = source_bytes_by_path[path]
            if type(payload) is not bytes:
                raise TypeError("injected source payload must be bytes")
        except (KeyError, OSError, TypeError) as error:
            failures.append(
                f"{relative}: cannot read current Build 24 lifecycle "
                f"aggregate {label}: {error}"
            )
            continue

        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if len(payload) != expected_size or actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected current Build 24 lifecycle aggregate "
                f"{label} identity {expected_size} bytes and SHA-256 "
                f"{expected_sha256}; found {len(payload)} bytes and "
                f"{actual_sha256}."
            )
    return failures


def current_build24_reverse_version_readback_source_failures(
    *,
    source_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    expected_sources = (
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_RESULT,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RESULT_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RESULT_SHA256,
            "result",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_RECEIPT,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RECEIPT_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RECEIPT_SHA256,
            "repeatability receipt",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SHA256,
            "runner",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER_TEST,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SHA256,
            "runner test",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SHA256,
            "checker",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER_TEST,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SHA256,
            "checker test",
        ),
    )
    expected_paths = {path for path, _, _, _ in expected_sources}
    failures: list[str] = []
    if (
        source_bytes_by_path is not None
        and set(source_bytes_by_path) != expected_paths
    ):
        failures.append(
            "Build 24-to-23-to-24 reverse-version readback source byte "
            "map must contain exactly the result, repeatability receipt, "
            "runner, runner test, checker, and checker test files."
        )

    for path, expected_size, expected_sha256, label in expected_sources:
        relative = str(path.relative_to(ROOT))
        try:
            if source_bytes_by_path is None:
                if path.is_symlink() or not path.is_file():
                    raise OSError(
                        "path must be a non-symlink regular file"
                    )
                payload = path.read_bytes()
            else:
                payload = source_bytes_by_path[path]
            if type(payload) is not bytes:
                raise TypeError("injected source payload must be bytes")
        except (KeyError, OSError, TypeError) as error:
            failures.append(
                f"{relative}: cannot read current Build 24-to-23-to-24 "
                f"reverse-version readback {label}: {error}"
            )
            continue

        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if len(payload) != expected_size or actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected current Build 24-to-23-to-24 "
                f"reverse-version readback {label} identity "
                f"{expected_size} bytes and SHA-256 {expected_sha256}; "
                f"found {len(payload)} bytes and {actual_sha256}."
            )
    return failures


def current_build24_macos_idle_resource_stability_evidence_failures(
    result_bytes: bytes | None = None,
    *,
    source_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    expected_sources = (
        (
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RUNNER,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_SIZE,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_SHA256,
            "runner",
        ),
        (
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RUNNER_TEST,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_TEST_SIZE,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_TEST_SHA256,
            "runner test",
        ),
        (
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_CHECKER,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_SIZE,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_SHA256,
            "checker",
        ),
        (
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_CHECKER_TEST,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_TEST_SIZE,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_TEST_SHA256,
            "checker test",
        ),
    )
    expected_paths = {path for path, _, _, _ in expected_sources}
    failures: list[str] = []
    if (
        source_bytes_by_path is not None
        and set(source_bytes_by_path) != expected_paths
    ):
        failures.append(
            "script/check_macos_build24_idle_resource_stability_evidence.py: "
            "injected idle-resource source byte map must contain exactly "
            "the runner, runner test, checker, and checker test files."
        )

    for path, expected_size, expected_sha256, label in expected_sources:
        relative = str(path.relative_to(ROOT))
        try:
            if source_bytes_by_path is None:
                if path.is_symlink() or not path.is_file():
                    raise OSError(
                        "path must be a non-symlink regular file"
                    )
                payload = path.read_bytes()
            else:
                payload = source_bytes_by_path[path]
            if type(payload) is not bytes:
                raise TypeError("injected source payload must be bytes")
        except (KeyError, OSError, TypeError) as error:
            failures.append(
                f"{relative}: cannot read current Build 24 idle-resource "
                f"{label}: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if len(payload) != expected_size or actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected current Build 24 idle-resource "
                f"{label} identity {expected_size} bytes and SHA-256 "
                f"{expected_sha256}; found {len(payload)} bytes and "
                f"{actual_sha256}."
            )

    result_path = CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RESULT
    result_relative = str(result_path.relative_to(ROOT))
    try:
        if result_bytes is None:
            if result_path.is_symlink() or not result_path.is_file():
                raise OSError("path must be a non-symlink regular file")
            payload = result_path.read_bytes()
        else:
            payload = result_bytes
        if type(payload) is not bytes:
            raise TypeError("injected result payload must be bytes")
    except (OSError, TypeError) as error:
        failures.append(
            f"{result_relative}: cannot read current Build 24 idle-resource "
            f"result: {error}"
        )
        return failures

    actual_sha256 = hashlib.sha256(payload).hexdigest()
    expected_size = (
        CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RESULT_SIZE
    )
    expected_sha256 = (
        CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RESULT_SHA256
    )
    if len(payload) != expected_size or actual_sha256 != expected_sha256:
        failures.append(
            f"{result_relative}: expected current Build 24 idle-resource "
            f"result identity {expected_size} bytes and SHA-256 "
            f"{expected_sha256}; found {len(payload)} bytes and "
            f"{actual_sha256}."
        )
    try:
        idle_resource_evidence.validate_result_bytes(
            payload,
            enforce_identity=False,
        )
    except idle_resource_evidence.IdleResourceEvidenceError as error:
        failures.append(
            f"{result_relative}: invalid current Build 24 idle-resource "
            f"result contract: {error}"
        )
    return failures


def current_macos_isolated_upgrade_evidence_failures(
    result_bytes: bytes | None = None,
    repeatability_bytes: bytes | None = None,
    source_bytes_by_path: dict[Path, bytes] | None = None,
    release_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    relative = str(
        CURRENT_MACOS_ISOLATED_UPGRADE_RESULT.relative_to(ROOT)
    )
    failures: list[str] = []

    for path, expected_sha256 in (
        (
            CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
            CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_ISOLATED_UPGRADE_TEST,
            CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_TEST_SHA256,
        ),
    ):
        try:
            payload = (
                source_bytes_by_path[path]
                if source_bytes_by_path is not None
                else path.read_bytes()
            )
        except (KeyError, OSError) as error:
            failures.append(
                f"{path.relative_to(ROOT)}: cannot read isolated upgrade "
                f"source: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{path.relative_to(ROOT)}: expected isolated upgrade "
                f"source SHA-256 {expected_sha256}, found {actual_sha256}."
            )

    if result_bytes is None:
        try:
            result_bytes = (
                CURRENT_MACOS_ISOLATED_UPGRADE_RESULT.read_bytes()
            )
        except OSError as error:
            failures.append(
                f"{relative}: cannot read isolated upgrade result: {error}"
            )
            return failures

    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SIZE,
        CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SHA256,
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
            f"{relative}: invalid isolated upgrade result JSON: {error}"
        )
        return failures
    if not isinstance(result, dict):
        failures.append(
            f"{relative}: isolated upgrade result root must be an object."
        )
        return failures

    canonical_result = (
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if result_bytes != canonical_result:
        failures.append(
            f"{relative}: isolated upgrade result is not canonical JSON."
        )

    expected_top_level_keys = {
        "archiveReadback",
        "canary",
        "cleanup",
        "installation",
        "isolation",
        "launchServices",
        "limitations",
        "releases",
        "schemaVersion",
        "scope",
        "stateUpgrade",
        "status",
    }
    if set(result) != expected_top_level_keys:
        failures.append(
            f"{relative}: isolated upgrade top-level keys differ from the "
            "closed contract."
        )

    missing = object()

    def read_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return missing
            value = value[key]
        return value

    expectations = (
        (("schemaVersion",), 2),
        (("status",), "passed"),
        (
            ("scope",),
            "same-host-per-user-isolated-build-to-build-upgrade-v2",
        ),
        (
            ("archiveReadback", "previous", "mode"),
            "historical",
        ),
        (
            ("archiveReadback", "previous", "currentSourceCompared"),
            False,
        ),
        (
            (
                "archiveReadback",
                "previous",
                "readbackAndExerciseSameSnapshot",
            ),
            True,
        ),
        (
            (
                "archiveReadback",
                "previous",
                "snapshotFilesUnchangedAfterExercise",
            ),
            True,
        ),
        (
            ("archiveReadback", "previous", "status"),
            "passed",
        ),
        (
            ("archiveReadback", "current", "mode"),
            "archive-only-no-current-source",
        ),
        (
            ("archiveReadback", "current", "currentSourceCompared"),
            False,
        ),
        (
            (
                "archiveReadback",
                "current",
                "readbackAndExerciseSameSnapshot",
            ),
            True,
        ),
        (
            (
                "archiveReadback",
                "current",
                "snapshotFilesUnchangedAfterExercise",
            ),
            True,
        ),
        (
            ("archiveReadback", "current", "status"),
            "passed",
        ),
        (("cleanup", "appAbsentAfterFinalRemoval"), True),
        (("cleanup", "applicationSupportCleanupPerformed"), False),
        (("cleanup", "exactTemporaryAppPathOnly"), True),
        (("cleanup", "removalCount"), 2),
        (("installation", "copyTool"), "ditto"),
        (
            ("installation", "installedRelativePath"),
            "Applications/AetherLink.app",
        ),
        (
            ("installation", "replacementMethod"),
            "exact-path-remove-then-ditto",
        ),
        (("installation", "stalePreviousBundleFilesAbsent"), True),
        (("installation", "treesDiffer"), True),
        (
            ("installation", "previousTree", "regularFileCount"),
            10,
        ),
        (
            ("installation", "previousTree", "digestAlgorithm"),
            "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1",
        ),
        (
            ("installation", "previousTree", "totalRegularFileBytes"),
            21_153_014,
        ),
        (
            ("installation", "previousTree", "sha256"),
            "31209251804494f54a699c5c4e8101491f02fca881cf25fba379b88eb493d8a8",
        ),
        (
            ("installation", "currentTree", "regularFileCount"),
            10,
        ),
        (
            ("installation", "currentTree", "digestAlgorithm"),
            "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1",
        ),
        (
            ("installation", "currentTree", "totalRegularFileBytes"),
            21_151_910,
        ),
        (
            ("installation", "currentTree", "sha256"),
            "0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff",
        ),
        (
            ("isolation", "preexistingBundleApplicationsPreserved"),
            True,
        ),
        (
            ("isolation", "runtimeIdentityFileOverrideConfigured"),
            True,
        ),
        (("isolation", "temporaryCFUserHomeConfigured"), True),
        (
            ("launchServices", "commandPolicy"),
            "open-new-fresh-background-exact-app-path-captured-recovery-v1",
        ),
        (("launchServices", "distinctProcessIdentifiers"), True),
        (
            ("releases", "from", "releaseId"),
            "aetherlink-1.0.0+23-local-v1",
        ),
        (
            ("releases", "from", "archiveSha256"),
            "b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e",
        ),
        (
            ("releases", "from", "manifestSha256"),
            "a645819bb0dd985b94289a29cc26b6a344361139ab6ca20a2b7aff9af0a8a16d",
        ),
        (("releases", "from", "app", "buildNumber"), 23),
        (
            ("releases", "from", "app", "bundleIdentifier"),
            "dev.aetherlink.companion",
        ),
        (
            ("releases", "from", "app", "executableSha256"),
            "346d0a673ba7710b5692dd2fc2dd8543e937b65deae77ad8c281071e107ab55c",
        ),
        (
            ("releases", "from", "app", "marketingVersion"),
            "1.0.0",
        ),
        (
            ("releases", "from", "app", "uuid"),
            "73F610E8-4BBE-3C8D-B28E-434426EAD95B",
        ),
        (
            ("releases", "to", "releaseId"),
            "aetherlink-1.0.0+24-local-v1",
        ),
        (
            ("releases", "to", "archiveSha256"),
            "104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c",
        ),
        (
            ("releases", "to", "manifestSha256"),
            "eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b",
        ),
        (("releases", "to", "app", "buildNumber"), 24),
        (
            ("releases", "to", "app", "bundleIdentifier"),
            "dev.aetherlink.companion",
        ),
        (
            ("releases", "to", "app", "executableSha256"),
            "5bf283a6dd3504682cb4aefc9cb1536c7e340f776c90de83cea5a473044890e5",
        ),
        (
            ("releases", "to", "app", "marketingVersion"),
            "1.0.0",
        ),
        (
            ("releases", "to", "app", "uuid"),
            "3FDC3DBC-3A74-3A3B-A87D-03CB432B5D46",
        ),
        (
            ("stateUpgrade", "applicationSupportPreservedAcrossUpgrade"),
            True,
        ),
        (
            ("stateUpgrade", "bytesAndModesUnchangedAcrossUpgrade"),
            True,
        ),
        (("stateUpgrade", "currentRelaunchIdempotent"), True),
        (("stateUpgrade", "legacyAbsentAfterUpgrade"), True),
        (
            ("stateUpgrade", "legacyFixturePreservedUnchanged"),
            True,
        ),
        (("stateUpgrade", "runtimeIdentityFilePresent"), True),
        (
            ("stateUpgrade", "migrationObservation", "mode"),
            "migration-read-v1",
        ),
        (
            ("stateUpgrade", "migrationObservation", "sha256"),
            "558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9",
        ),
        (
            ("stateUpgrade", "readbackObservation", "mode"),
            "sqlite-readback-v1",
        ),
        (
            ("stateUpgrade", "readbackObservation", "sha256"),
            "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07",
        ),
        (
            ("stateUpgrade", "relaunchObservation", "mode"),
            "sqlite-readback-v1",
        ),
        (
            ("stateUpgrade", "relaunchObservation", "sha256"),
            "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07",
        ),
        (
            ("stateUpgrade", "migrationSQLite", "totalEventCount"),
            1,
        ),
        (
            ("stateUpgrade", "readbackSQLite", "totalEventCount"),
            1,
        ),
        (
            ("stateUpgrade", "relaunchSQLite", "totalEventCount"),
            1,
        ),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )

    expected_runs = [
        {
            "activationPolicy": 0,
            "executablePathMatched": True,
            "finishedLaunching": True,
            "minimumObservationSeconds": 5.0,
            "newProcessIdentifierDetected": True,
            "observationDeadlineReached": True,
            "ordinal": ordinal,
            "terminationAccepted": True,
        }
        for ordinal in (1, 2, 3)
    ]
    if not exact_json_values_equal(
        read_path(("launchServices", "runs")),
        expected_runs,
    ):
        failures.append(
            f"{relative}: launchServices.runs differs from the exact "
            "three-process contract."
        )

    expected_auxiliary = [
        {
            "filename": "runtime-document-index.sqlite",
            "integrityCheck": "ok",
        },
        {
            "filename": "runtime-model-pull-approvals.sqlite",
            "integrityCheck": "ok",
        },
    ]
    if not exact_json_values_equal(
        read_path(("stateUpgrade", "auxiliarySQLite")),
        expected_auxiliary,
    ):
        failures.append(
            f"{relative}: stateUpgrade.auxiliarySQLite differs from the "
            "exact integrity contract."
        )

    expected_sqlite_files = [
        "runtime-chat-events.sqlite",
        "runtime-document-index.sqlite",
        "runtime-model-pull-approvals.sqlite",
    ]
    if not exact_json_values_equal(
        read_path(("stateUpgrade", "expectedSQLiteFiles")),
        expected_sqlite_files,
    ):
        failures.append(
            f"{relative}: stateUpgrade.expectedSQLiteFiles differs from the "
            "exact three-file contract."
        )

    expected_limitations = [
        "same-host-per-user-temporary-home-only",
        "build-to-build-upgrade-not-rollback",
        "application-support-retained-no-automatic-data-cleanup",
        "post-archive-harness-not-build-input-member",
        "not-clean-machine-device-provider-network-ui-or-distribution-evidence",
        "not-production-release-qualification",
    ]
    if not exact_json_values_equal(
        result.get("limitations"),
        expected_limitations,
    ):
        failures.append(
            f"{relative}: isolated upgrade result lost the exact scope "
            "limitations."
        )

    closed_objects: list[tuple[tuple[str, ...], set[str]]] = [
        (("archiveReadback",), {"current", "previous"}),
        (
            ("canary",),
            {
                "eventID",
                "eventJsonSha256",
                "eventJsonSize",
                "legacyJsonlSha256",
                "legacyJsonlSize",
                "model",
                "requestID",
                "sessionID",
            },
        ),
        (
            ("cleanup",),
            {
                "appAbsentAfterFinalRemoval",
                "applicationSupportCleanupPerformed",
                "exactTemporaryAppPathOnly",
                "removalCount",
            },
        ),
        (
            ("installation",),
            {
                "copyTool",
                "currentTree",
                "installedRelativePath",
                "previousTree",
                "replacementMethod",
                "stalePreviousBundleFilesAbsent",
                "treesDiffer",
            },
        ),
        (
            ("isolation",),
            {
                "preexistingBundleApplicationsPreserved",
                "runtimeIdentityFileOverrideConfigured",
                "temporaryCFUserHomeConfigured",
            },
        ),
        (
            ("launchServices",),
            {"commandPolicy", "distinctProcessIdentifiers", "runs"},
        ),
        (("releases",), {"from", "to"}),
        (
            ("stateUpgrade",),
            {
                "applicationSupportPreservedAcrossUpgrade",
                "auxiliarySQLite",
                "bytesAndModesUnchangedAcrossUpgrade",
                "currentRelaunchIdempotent",
                "expectedSQLiteFiles",
                "legacyAbsentAfterUpgrade",
                "legacyFixturePreservedUnchanged",
                "migrationObservation",
                "migrationSQLite",
                "readbackObservation",
                "readbackSQLite",
                "relaunchObservation",
                "relaunchSQLite",
                "runtimeIdentityFilePresent",
                "stderr",
            },
        ),
        (
            ("stateUpgrade", "stderr"),
            {"migration", "readback", "relaunch"},
        ),
    ]
    for readback_name in ("previous", "current"):
        closed_objects.append(
            (
                ("archiveReadback", readback_name),
                {
                    "currentSourceCompared",
                    "mode",
                    "readbackAndExerciseSameSnapshot",
                    "snapshotFiles",
                    "snapshotFilesUnchangedAfterExercise",
                    "status",
                },
            )
        )
    for tree_name in ("previousTree", "currentTree"):
        closed_objects.append(
            (
                ("installation", tree_name),
                {
                    "digestAlgorithm",
                    "regularFileCount",
                    "sha256",
                    "totalRegularFileBytes",
                },
            )
        )
    for release_name in ("from", "to"):
        closed_objects.extend(
            (
                (
                    ("releases", release_name),
                    {"app", "archiveSha256", "manifestSha256", "releaseId"},
                ),
                (
                    ("releases", release_name, "app"),
                    {
                        "buildNumber",
                        "bundleIdentifier",
                        "executableSha256",
                        "marketingVersion",
                        "uuid",
                    },
                ),
            )
        )
    for observation_name in (
        "migrationObservation",
        "readbackObservation",
        "relaunchObservation",
    ):
        closed_objects.append(
            (
                ("stateUpgrade", observation_name),
                {"mode", "sha256", "size", "status"},
            )
        )
    for sqlite_name in (
        "migrationSQLite",
        "readbackSQLite",
        "relaunchSQLite",
    ):
        closed_objects.append(
            (
                ("stateUpgrade", sqlite_name),
                {
                    "eventJsonSha256",
                    "eventJsonSize",
                    "integrityCheck",
                    "totalEventCount",
                },
            )
        )
    for stderr_name in ("migration", "readback", "relaunch"):
        closed_objects.append(
            (
                ("stateUpgrade", "stderr", stderr_name),
                {"sha256", "size"},
            )
        )
    for path, expected_keys in closed_objects:
        value = read_path(path)
        if not isinstance(value, dict) or set(value) != expected_keys:
            failures.append(
                f"{relative}: {'.'.join(path)} keys differ from the "
                "closed contract."
            )

    for readback_name in ("previous", "current"):
        snapshot_files = read_path(
            ("archiveReadback", readback_name, "snapshotFiles")
        )
        if isinstance(snapshot_files, dict):
            for name, identity_value in snapshot_files.items():
                if (
                    not isinstance(identity_value, dict)
                    or set(identity_value) != {"sha256", "size"}
                ):
                    failures.append(
                        f"{relative}: {readback_name} snapshot {name!r} "
                        "identity keys differ from the closed contract."
                    )
    runs_value = read_path(("launchServices", "runs"))
    run_keys = {
        "activationPolicy",
        "executablePathMatched",
        "finishedLaunching",
        "minimumObservationSeconds",
        "newProcessIdentifierDetected",
        "observationDeadlineReached",
        "ordinal",
        "terminationAccepted",
    }
    if isinstance(runs_value, list):
        for index, run_value in enumerate(runs_value):
            if not isinstance(run_value, dict) or set(run_value) != run_keys:
                failures.append(
                    f"{relative}: launchServices.runs[{index}] keys differ "
                    "from the closed contract."
                )
    auxiliary_value = read_path(("stateUpgrade", "auxiliarySQLite"))
    if isinstance(auxiliary_value, list):
        for index, row in enumerate(auxiliary_value):
            if (
                not isinstance(row, dict)
                or set(row) != {"filename", "integrityCheck"}
            ):
                failures.append(
                    f"{relative}: stateUpgrade.auxiliarySQLite[{index}] "
                    "keys differ from the closed contract."
                )

    expected_canary = {
        "eventID": "packaged-state-recovery-canary-event-v1",
        "eventJsonSha256": (
            "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
        ),
        "eventJsonSize": 344,
        "legacyJsonlSha256": (
            "0e51fc924836465c4c0921eb3b3709b387f89787aabf2e100c7cff338f0aea2e"
        ),
        "legacyJsonlSize": 345,
        "model": "qa:packaged-state-recovery-canary-v1",
        "requestID": "packaged-state-recovery-canary-request-v1",
        "sessionID": "packaged-state-recovery-canary-session-v1",
    }
    if not exact_json_values_equal(result.get("canary"), expected_canary):
        failures.append(
            f"{relative}: canary differs from the exact migration fixture."
        )
    expected_observations = {
        "migrationObservation": {
            "mode": "migration-read-v1",
            "sha256": (
                "558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9"
            ),
            "size": 70,
            "status": "passed",
        },
        "readbackObservation": {
            "mode": "sqlite-readback-v1",
            "sha256": (
                "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07"
            ),
            "size": 71,
            "status": "passed",
        },
        "relaunchObservation": {
            "mode": "sqlite-readback-v1",
            "sha256": (
                "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07"
            ),
            "size": 71,
            "status": "passed",
        },
    }
    expected_sqlite = {
        "eventJsonSha256": expected_canary["eventJsonSha256"],
        "eventJsonSize": 344,
        "integrityCheck": "ok",
        "totalEventCount": 1,
    }
    empty_log = {
        "sha256": (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        "size": 0,
    }
    for name, expected_observation in expected_observations.items():
        if not exact_json_values_equal(
            read_path(("stateUpgrade", name)),
            expected_observation,
        ):
            failures.append(
                f"{relative}: stateUpgrade.{name} differs from the exact "
                "observation contract."
            )
    for name in (
        "migrationSQLite",
        "readbackSQLite",
        "relaunchSQLite",
    ):
        if not exact_json_values_equal(
            read_path(("stateUpgrade", name)),
            expected_sqlite,
        ):
            failures.append(
                f"{relative}: stateUpgrade.{name} differs from the exact "
                "SQLite canary contract."
            )
    if not exact_json_values_equal(
        read_path(("stateUpgrade", "stderr")),
        {
            name: empty_log
            for name in ("migration", "readback", "relaunch")
        },
    ):
        failures.append(
            f"{relative}: stateUpgrade.stderr differs from three empty logs."
        )

    def streamed_file_identity(path: Path) -> dict[str, object]:
        if (
            release_bytes_by_path is not None
            and path in release_bytes_by_path
        ):
            payload = release_bytes_by_path[path]
            return {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while True:
                payload = handle.read(1024 * 1024)
                if not payload:
                    break
                digest.update(payload)
                size += len(payload)
        return {"sha256": digest.hexdigest(), "size": size}

    def manifest_value(
        manifest: object,
        path: tuple[str, ...],
    ) -> object:
        value = manifest
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return missing
            value = value[key]
        return value

    def validate_release_projection(
        *,
        build_number: int,
        release_name: str,
        readback_name: str,
        tree_name: str,
    ) -> None:
        release_id = f"aetherlink-1.0.0+{build_number}-local-v1"
        archive_directory = ROOT / "dist/releases" / release_id
        archive_path = archive_directory / f"{release_id}.zip"
        manifest_path = archive_directory / f"{release_id}.manifest.json"
        checksum_path = archive_directory / f"{release_id}.zip.sha256"
        try:
            archive_identity = streamed_file_identity(archive_path)
            manifest_bytes = (
                release_bytes_by_path[manifest_path]
                if (
                    release_bytes_by_path is not None
                    and manifest_path in release_bytes_by_path
                )
                else manifest_path.read_bytes()
            )
            manifest_identity = {
                "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "size": len(manifest_bytes),
            }
            checksum_bytes = (
                release_bytes_by_path[checksum_path]
                if (
                    release_bytes_by_path is not None
                    and checksum_path in release_bytes_by_path
                )
                else checksum_path.read_bytes()
            )
            checksum_identity = {
                "sha256": hashlib.sha256(checksum_bytes).hexdigest(),
                "size": len(checksum_bytes),
            }
            manifest = json.loads(
                manifest_bytes.decode("utf-8"),
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJSONKeyError,
        ) as error:
            failures.append(
                f"{relative}: cannot cross-bind {release_id}: {error}"
            )
            return

        expected_sidecar = (
            f"{archive_identity['sha256']}  {archive_path.name}\n"
        ).encode("ascii")
        if checksum_bytes != expected_sidecar:
            failures.append(
                f"{relative}: {release_id} checksum sidecar differs from "
                "the actual ZIP identity."
            )

        result_release = read_path(("releases", release_name))
        snapshot_files = read_path(
            ("archiveReadback", readback_name, "snapshotFiles")
        )
        expected_snapshot_files = {
            archive_path.name: archive_identity,
            manifest_path.name: manifest_identity,
            checksum_path.name: checksum_identity,
        }
        if not isinstance(result_release, dict):
            failures.append(
                f"{relative}: releases.{release_name} is not an object."
            )
            return
        if not exact_json_values_equal(
            snapshot_files,
            expected_snapshot_files,
        ):
            failures.append(
                f"{relative}: {release_id} snapshot identities do not "
                "match the retained archive files."
            )
        for field_name, expected_value in (
            ("releaseId", release_id),
            ("archiveSha256", archive_identity["sha256"]),
            ("manifestSha256", manifest_identity["sha256"]),
        ):
            actual_value = result_release.get(field_name)
            if not exact_json_values_equal(actual_value, expected_value):
                failures.append(
                    f"{relative}: releases.{release_name}.{field_name} "
                    f"does not match {release_id}."
                )

        expected_manifest_bindings = (
            (("release", "releaseId"), release_id),
            (("release", "buildNumber"), build_number),
            (("release", "marketingVersion"), "1.0.0"),
            (("platforms", "macos", "bundleId"), "dev.aetherlink.companion"),
            (("platforms", "macos", "buildNumber"), build_number),
            (("platforms", "macos", "marketingVersion"), "1.0.0"),
        )
        for path, expected_value in expected_manifest_bindings:
            actual_value = manifest_value(manifest, path)
            if not exact_json_values_equal(actual_value, expected_value):
                failures.append(
                    f"{relative}: {release_id} manifest "
                    f"{'.'.join(path)} does not match the upgrade result."
                )

        app = result_release.get("app")
        macos = manifest_value(manifest, ("platforms", "macos"))
        if not isinstance(app, dict) or not isinstance(macos, dict):
            failures.append(
                f"{relative}: {release_id} app/manifest macOS projection "
                "is not an object."
            )
            return
        for result_field, manifest_field in (
            ("buildNumber", "buildNumber"),
            ("bundleIdentifier", "bundleId"),
            ("marketingVersion", "marketingVersion"),
            ("uuid", "uuid"),
        ):
            if not exact_json_values_equal(
                app.get(result_field),
                macos.get(manifest_field),
            ):
                failures.append(
                    f"{relative}: {release_id} app {result_field} does "
                    "not match its manifest."
                )
        if not exact_json_values_equal(
            app.get("uuid"),
            manifest_value(manifest, ("platforms", "macos", "dSYM", "uuid")),
        ):
            failures.append(
                f"{relative}: {release_id} app UUID does not match dSYM."
            )

        members = manifest_value(manifest, ("members",))
        app_prefix = "macos/AetherLink.app/"
        executable_path = app_prefix + "Contents/MacOS/AetherLink"
        app_members: list[dict[str, object]] = []
        if isinstance(members, list):
            app_members = [
                row
                for row in members
                if isinstance(row, dict)
                and isinstance(row.get("path"), str)
                and row["path"].startswith(app_prefix)
            ]
        executable_members = [
            row for row in app_members if row.get("path") == executable_path
        ]
        if len(executable_members) != 1 or not exact_json_values_equal(
            app.get("executableSha256"),
            (
                executable_members[0].get("sha256")
                if executable_members
                else missing
            ),
        ):
            failures.append(
                f"{relative}: {release_id} executable identity does not "
                "match its manifest member."
            )

        tree_digest = hashlib.sha256()
        tree_total = 0
        valid_tree = True
        seen_paths: set[str] = set()
        for row in sorted(app_members, key=lambda item: str(item.get("path"))):
            member_path = row.get("path")
            mode = row.get("mode")
            size = row.get("size")
            sha256 = row.get("sha256")
            if (
                not isinstance(member_path, str)
                or member_path in seen_paths
                or not isinstance(mode, str)
                or re.fullmatch(r"0[0-7]{3}", mode) is None
                or type(size) is not int
                or size < 0
                or not isinstance(sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
            ):
                valid_tree = False
                break
            seen_paths.add(member_path)
            tree_digest.update(member_path.encode("utf-8"))
            tree_digest.update(b"\0")
            tree_digest.update(mode.encode("ascii"))
            tree_digest.update(b"\0")
            tree_digest.update(str(size).encode("ascii"))
            tree_digest.update(b"\0")
            tree_digest.update(sha256.encode("ascii"))
            tree_digest.update(b"\n")
            tree_total += size
        expected_tree = {
            "digestAlgorithm": (
                "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
            ),
            "regularFileCount": len(app_members),
            "sha256": tree_digest.hexdigest(),
            "totalRegularFileBytes": tree_total,
        }
        if not valid_tree or not exact_json_values_equal(
            read_path(("installation", tree_name)),
            expected_tree,
        ):
            failures.append(
                f"{relative}: installation.{tree_name} does not derive "
                f"from the {release_id} manifest."
            )

    validate_release_projection(
        build_number=23,
        release_name="from",
        readback_name="previous",
        tree_name="previousTree",
    )
    validate_release_projection(
        build_number=24,
        release_name="to",
        readback_name="current",
        tree_name="currentTree",
    )

    repeatability_relative = str(
        CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_RESULT.relative_to(ROOT)
    )
    if repeatability_bytes is None:
        try:
            repeatability_bytes = (
                CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_RESULT.read_bytes()
            )
        except OSError as error:
            failures.append(
                f"{repeatability_relative}: cannot read repeatability "
                f"receipt: {error}"
            )
            return failures
    repeatability_identity = (
        len(repeatability_bytes),
        hashlib.sha256(repeatability_bytes).hexdigest(),
    )
    expected_repeatability_identity = (
        CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SIZE,
        CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SHA256,
    )
    if repeatability_identity != expected_repeatability_identity:
        failures.append(
            f"{repeatability_relative}: expected identity "
            f"{expected_repeatability_identity!r}, found "
            f"{repeatability_identity!r}."
        )
    try:
        repeatability = json.loads(
            repeatability_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{repeatability_relative}: invalid repeatability receipt "
            f"JSON: {error}"
        )
        return failures
    canonical_repeatability = (
        json.dumps(
            repeatability,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if repeatability_bytes != canonical_repeatability:
        failures.append(
            f"{repeatability_relative}: repeatability receipt is not "
            "canonical JSON."
        )
    canonical_identity = {
        "fileName": CURRENT_MACOS_ISOLATED_UPGRADE_RESULT.name,
        "sha256": CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SHA256,
        "size": CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SIZE,
    }
    expected_repeatability = {
        "canonicalResult": canonical_identity,
        "limitations": [
            "same-host-repeatability-only",
            "two-recorded-runs-not-arbitrary-repeatability",
            "not-cross-host-clean-machine-or-signed-distribution-evidence",
            "not-rollback-device-provider-network-or-production-evidence",
        ],
        "releaseTransition": {
            "from": "aetherlink-1.0.0+23-local-v1",
            "to": "aetherlink-1.0.0+24-local-v1",
        },
        "resultBytesEqual": True,
        "runCount": 2,
        "runs": [
            {
                "ordinal": ordinal,
                "sha256": canonical_identity["sha256"],
                "size": canonical_identity["size"],
                "status": "passed",
            }
            for ordinal in (1, 2)
        ],
        "schemaVersion": 1,
        "scope": (
            "same-host-per-user-isolated-build-to-build-upgrade-"
            "repeatability-v1"
        ),
        "status": "passed",
    }
    if not exact_json_values_equal(
        repeatability,
        expected_repeatability,
    ):
        failures.append(
            f"{repeatability_relative}: receipt differs from the exact "
            "two-run repeatability contract."
        )
    return failures


def marker_is_in_hidden_markdown_context(
    document_text: str,
    marker: str,
) -> bool:
    try:
        marker_index = document_text.index(marker)
    except ValueError:
        return False
    prefix = document_text[:marker_index]

    active_fence: tuple[str, int] | None = None
    outside_fence_lines: list[str] = []
    for line in prefix.splitlines(keepends=True):
        match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})([^\r\n]*)", line)
        if active_fence is None:
            if match is None:
                outside_fence_lines.append(line)
                continue
            token = match.group(1)
            active_fence = (token[0], len(token))
            continue
        if match is None:
            continue
        token = match.group(1)
        trailing = match.group(2)
        if (
            token[0] == active_fence[0]
            and len(token) >= active_fence[1]
            and not trailing.strip()
        ):
            active_fence = None
    if active_fence is not None:
        return True

    html_prefix = "".join(outside_fence_lines)
    comment_depth = 0
    for match in re.finditer(r"<!--|-->", html_prefix):
        if match.group(0) == "<!--":
            comment_depth += 1
        elif comment_depth > 0:
            comment_depth -= 1
    if comment_depth > 0:
        return True

    html_prefix = re.sub(
        r"<!--.*?-->",
        "",
        html_prefix,
        flags=re.DOTALL,
    )
    hidden_container_tags = {"details", "pre", "script", "style", "template"}
    open_containers: list[tuple[str, bool]] = []
    tag_pattern = re.compile(
        r"<\s*(/?)\s*([A-Za-z][A-Za-z0-9:_-]*)([^<>]*)>",
        re.DOTALL,
    )
    for match in tag_pattern.finditer(html_prefix):
        closing = bool(match.group(1))
        tag = match.group(2).lower()
        attributes = match.group(3)
        if closing:
            for index in range(len(open_containers) - 1, -1, -1):
                if open_containers[index][0] == tag:
                    del open_containers[index:]
                    break
            continue
        if attributes.rstrip().endswith("/"):
            continue
        has_hidden_attribute = re.search(
            r"(?:^|\s)hidden"
            r"(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s/]+))?"
            r"(?=\s|/|$)",
            attributes,
            re.IGNORECASE,
        )
        is_hidden = tag in hidden_container_tags or has_hidden_attribute is not None
        open_containers.append((tag, is_hidden))
    return any(is_hidden for _, is_hidden in open_containers)


def current_source_g6_lane_a_local_dmg_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    expected_successors = {
        "README.md": "The current Android QR scanner",
        "docs/roadmap.md": "The current macOS G5/G6 lifecycle slice",
        "docs/handoff.md": "- The current Android release-quality slice",
        "docs/progress.md": (
            "## 2026-07-31 Local V1 Build 24 Qualification"
        ),
        "docs/qa-evidence.md": (
            "## 2026-07-31 Local V1 Build 24 Qualification Checklist"
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            "## Rollback Posture"
        ),
    }
    expected_block = (
        "\n"
        + CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_BODY
        + "\n"
    )
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if document_text_by_relative is not None
                else path.read_text(encoding="utf-8")
            )
        except (KeyError, OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot read current-source G6 Lane-A DMG "
                f"documentation: {error}"
            )
            continue
        start_count = document_text.count(
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_END
        )
        if start_count != 1 or end_count != 1:
            failures.append(
                f"{relative}: current-source G6 Lane-A DMG markers must "
                "each appear exactly once."
            )
            continue
        start_index = document_text.index(
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_START
        )
        body_start = (
            start_index
            + len(CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_START)
        )
        end_index = document_text.index(
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_END
        )
        if start_index >= end_index:
            failures.append(
                f"{relative}: current-source G6 Lane-A DMG markers are "
                "reversed."
            )
            continue
        actual_block = document_text[body_start:end_index]
        if actual_block != expected_block:
            failures.append(
                f"{relative}: current-source G6 Lane-A DMG block must "
                "match the exact canonical body."
            )
        successor = expected_successors[relative]
        expected_after = (
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_END
            + "\n\n"
            + successor
        )
        if expected_after not in document_text:
            failures.append(
                f"{relative}: current-source G6 Lane-A DMG block moved "
                "outside its canonical document location."
            )
        if marker_is_in_hidden_markdown_context(
            document_text,
            CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_START,
        ):
            failures.append(
                f"{relative}: current-source G6 Lane-A DMG block must "
                "remain visible Markdown."
            )
    return failures


def current_macos_isolated_upgrade_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    required_patterns = (
        (
            "build transition",
            re.compile(
                r"\bBuild 23(?:-to-|[\s\S]{0,320}\bBuild 24\b)",
                re.IGNORECASE,
            ),
        ),
        (
            "state canary",
            re.compile(
                r"\b(?:Runtime-chat|Runtime chat)[\s\S]{0,100}canary\b",
                re.IGNORECASE,
            ),
        ),
        (
            "same snapshot bytes",
            re.compile(r"\bsame\s+(?:snapshot\s+)?bytes\b"),
        ),
        (
            "post-use rehash",
            re.compile(
                r"\brehash(?:ed|es|ing)\s+(?:them\s+)?unchanged\b"
            ),
        ),
        (
            "two complete runs",
            re.compile(r"\btwo\s+complete\s+runs\b", re.IGNORECASE),
        ),
        ("canonical result size", re.compile(r"\b6,469-byte\b")),
        (
            "canonical result path",
            re.compile(
                r"macos-packaged-app-build-23-to-24-"
                r"isolated-upgrade-v2\.json"
            ),
        ),
        (
            "canonical result identity",
            re.compile(
                r"\bddec23cf048fa77c559ca7ee4f45354f"
                r"eb558f830ca4b01eccffa5b7786ea09c\b"
            ),
        ),
        ("repeatability receipt size", re.compile(r"\b898-byte\b")),
        (
            "repeatability receipt path",
            re.compile(
                r"macos-packaged-app-build-23-to-24-"
                r"isolated-upgrade-repeatability-v1\.json"
            ),
        ),
        (
            "repeatability receipt identity",
            re.compile(
                r"\b886284149745c6fdd74625fab5d97c21"
                r"ad35cd9b69cc2ade4353194b4ecd1733\b"
            ),
        ),
    )
    contradictory_patterns = (
        re.compile(
            r"(?<!not )\b(?:qualifies?|qualified|proves?|establishes?)\b"
            r"[^.!?]{0,100}\b(?:rollback|arbitrary\s+"
            r"(?:N/N-1|versions?)|cross-host|clean-machine|"
            r"automatic\s+data\s+cleanup|signed\s+distribution|"
            r"physical-device|providers?|networks?|production)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:rollback|arbitrary\s+(?:N/N-1|versions?)|cross-host|"
            r"clean-machine|automatic\s+data\s+cleanup|signed\s+"
            r"distribution|physical-device|providers?|networks?|"
            r"production)\b[^.!?]{0,100}\b(?:is|are|was|were|has\s+been|"
            r"have\s+been)\s+(?:qualified|supported|proven|complete|"
            r"passed)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:production[- ]ready|ready\s+for\s+production|"
            r"works?\s+across\s+hosts?)\b",
            re.IGNORECASE,
        ),
    )
    expected_neighbors = {
        "README.md": (
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
                + "\nThe current non-security G6 lifecycle evidence"
            ),
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/roadmap.md": (
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
                + "\nThe current G6 non-security lifecycle slice"
            ),
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/progress.md": (
            (
                "## 2026-07-31 macOS Build 23 To Build 24 Isolated Upgrade\n\n"
                + CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
            ),
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Clean-HOME "
                "Lifecycle\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/qa-evidence.md": (
            (
                "## 2026-07-31 macOS Build 23 To Build 24 Isolated Upgrade "
                "Checklist\n\n"
                + CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
            ),
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Clean-HOME "
                "Lifecycle Checklist\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/handoff.md": (
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
                + "\n- A post-archive Build 23-to-24 upgrade runner"
            ),
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                "## Post-Archive Build 23 To Build 24 Isolated Upgrade "
                "Evidence\n\n"
                + CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
            ),
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n## Current Build 24 Clean-HOME Lifecycle "
                "Evidence\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if document_text_by_relative is not None
                else path.read_text(encoding="utf-8")
            )
        except (KeyError, OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot read isolated upgrade documentation: "
                f"{error}"
            )
            continue
        if (
            document_text.count(
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
            )
            != 1
            or document_text.count(
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
            )
            != 1
        ):
            failures.append(
                f"{relative}: isolated upgrade v2 markers must each "
                "appear exactly once."
            )
            continue
        start_index = document_text.index(
            CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
        )
        end_index = document_text.index(
            CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
        )
        if start_index >= end_index:
            failures.append(
                f"{relative}: isolated upgrade v2 markers are out of order."
            )
            continue
        expected_before, expected_after = expected_neighbors[relative]
        if (
            expected_before not in document_text
            or expected_after not in document_text
        ):
            failures.append(
                f"{relative}: isolated upgrade v2 block moved outside its "
                "canonical document location."
            )
        block = document_text[
            start_index
            + len(CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START):
            end_index
        ]
        block_sha256 = hashlib.sha256(
            block.encode("utf-8")
        ).hexdigest()
        expected_block_sha256 = (
            CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_BLOCK_SHA256[relative]
        )
        if block_sha256 != expected_block_sha256:
            failures.append(
                f"{relative}: isolated upgrade v2 exact bounded block "
                f"SHA-256 must be {expected_block_sha256}, found "
                f"{block_sha256}."
            )
        normalized_block = re.sub(r"\s+", " ", block).strip()
        normalized_document = re.sub(r"\s+", " ", document_text).strip()
        normalized_boundary = re.sub(
            r"\s+",
            " ",
            CURRENT_MACOS_ISOLATED_UPGRADE_BOUNDARY,
        ).strip()
        if (
            normalized_block.count(normalized_boundary) != 1
            or normalized_document.count(normalized_boundary) != 1
        ):
            failures.append(
                f"{relative}: canonical isolated upgrade boundary must "
                "appear exactly once inside the v2 block."
            )
        for label, pattern in required_patterns:
            if not pattern.search(block):
                failures.append(
                    f"{relative}: missing isolated upgrade {label}."
                )
        if any(
            pattern.search(normalized_block)
            for pattern in contradictory_patterns
        ):
            failures.append(
                f"{relative}: isolated upgrade v2 block contains an "
                "unnegated contradictory qualification claim."
            )
    return failures


def current_runtime_chat_sqlite_abrupt_recovery_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    result_path = (
        "dist/lifecycle/"
        "macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json"
    )
    common_patterns = (
        (
            "bounded recovery claim",
            re.compile(
                r"\bbounded same-host abrupt child-\s*process "
                r"`SIGKILL` recovery evidence\b",
                re.IGNORECASE,
            ),
        ),
        (
            "committed prefix",
            re.compile(
                r"\b(?:24 committed events|(?:committed|commits) 24 events)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "in-flight event and FTS row",
            re.compile(
                r"\b(?:dirty uncommitted|QA-only raw SQLite transaction)"
                r".{0,120}\b25th event and FTS row\b",
                re.IGNORECASE,
            ),
        ),
        (
            "recovery to the committed prefix",
            re.compile(r"\brecover(?:y|ed|s)?\b.{0,100}\b24\b", re.IGNORECASE),
        ),
        (
            "production-store resume",
            re.compile(
                r"\b(?:production-store resume|"
                r"resumes? through the production store)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "final contiguous exactly-once event set",
            re.compile(r"\b48 contiguous exactly-once events\b", re.IGNORECASE),
        ),
        (
            "power-loss and kernel-crash exclusion",
            re.compile(
                r"\bnot power-loss or kernel-crash evidence\b",
                re.IGNORECASE,
            ),
        ),
        (
            "arbitrary-history and long-soak exclusion",
            re.compile(
                r"\bnot arbitrary-history or long-soak evidence\b",
                re.IGNORECASE,
            ),
        ),
        (
            "distribution and device exclusion",
            re.compile(
                r"\bnot clean-machine, signed-distribution, or "
                r"physical-device evidence\b",
                re.IGNORECASE,
            ),
        ),
    )
    forbidden_scope = re.compile(
        r"\b(?:production[- ]append[- ]crash[- ]point|"
        r"power[- ]loss(?: recovery)?|kernel[- ]crash(?: recovery)?|"
        r"clean[- ]machine(?: recovery)?|signed[- ]distribution|"
        r"physical[- ]device(?: behavior)?)\b",
        re.IGNORECASE,
    )
    explicit_scope_boundary = re.compile(
        r"\b(?:not|no|never|cannot|does not|do not|is not|are not|"
        r"unqualified|unproven|unknown|deferred|remains? open|"
        r"requires? future)\b",
        re.IGNORECASE,
    )

    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate Build 21 abrupt recovery "
                f"documentation: {error}"
            )
            continue

        start_count = document_text.count(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: Build 21 abrupt recovery block must contain "
                "exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START
        ) + len(CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START)
        end_index = document_text.index(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        )
        if end_index <= start_index:
            failures.append(
                f"{relative}: Build 21 abrupt recovery markers are reversed "
                "or empty."
            )
            continue

        block = document_text[start_index:end_index]
        block_sha256 = hashlib.sha256(block.encode("utf-8")).hexdigest()
        expected_block_sha256 = (
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_BLOCK_SHA256[relative]
        )
        if block_sha256 != expected_block_sha256:
            failures.append(
                f"{relative}: Build 21 abrupt recovery block must retain "
                "its exact bounded block SHA-256 "
                f"{expected_block_sha256}; found {block_sha256}."
            )
        normalized_block = re.sub(r"\s+", " ", block).strip()
        for binding in (
            result_path,
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256,
            "`not-production-append-crash-point`",
        ):
            count = normalized_block.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: Build 21 abrupt recovery block must contain "
                    f"{binding!r} exactly once; found {count}."
                )
        formatted_size = f"{CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE:,}"
        if not re.search(
            rf"\b{re.escape(formatted_size)}(?:-byte| bytes)\b",
            normalized_block,
        ):
            failures.append(
                f"{relative}: Build 21 abrupt recovery block is missing "
                f"the exact {formatted_size}-byte result size."
            )
        for label, pattern in common_patterns:
            if not pattern.search(normalized_block):
                failures.append(
                    f"{relative}: Build 21 abrupt recovery block is missing "
                    f"its {label}."
                )

        if path == LOCAL_RELEASE_CURRENT_DOC:
            for binding in (
                "`writerProcessReapedBeforeJournalObservation=true`",
                "25 event rows",
                "mutation revision 25",
                "validated revision 24",
            ):
                if normalized_block.count(binding) != 1:
                    failures.append(
                        f"{relative}: detailed abrupt recovery record must "
                        f"contain {binding!r} exactly once."
                    )

        for sentence in re.split(r"(?<=[.!?])\s+", normalized_block):
            plain_sentence = sentence.replace("`", "")
            scope_match = forbidden_scope.search(plain_sentence)
            if scope_match and not explicit_scope_boundary.search(
                plain_sentence
            ):
                failures.append(
                    f"{relative}: Build 21 abrupt recovery block contains "
                    "an unbounded or contradictory forbidden-scope claim."
                )
                break
    return failures


def current_runtime_chat_sqlite_cross_process_document_failures(
    document_text: str | None = None,
    *,
    relative: str = (
        f"docs/releases/{LOCAL_RELEASE_MARKETING_VERSION}-build-"
        f"{LOCAL_RELEASE_BUILD_NUMBER}-local-v1.md"
    ),
) -> list[str]:
    if document_text is None:
        try:
            document_text = LOCAL_RELEASE_CURRENT_DOC.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate current Runtime-chat SQLite "
                f"cross-process evidence: {error}"
            ]

    normalized_text = re.sub(r"\s+", " ", document_text).strip()
    failures: list[str] = []
    for label, pattern in CURRENT_RUNTIME_CHAT_SQLITE_DOCUMENT_REQUIRED_PATTERNS:
        if not pattern.search(normalized_text):
            failures.append(
                f"{relative}: current Build {LOCAL_RELEASE_BUILD_NUMBER} "
                "Runtime-chat SQLite "
                f"cross-process record is missing {label}."
            )

    stable_message_count = normalized_text.count(
        CURRENT_RUNTIME_CHAT_SQLITE_STABLE_BUSY_MESSAGE
    )
    if stable_message_count != 1:
        failures.append(
            f"{relative}: current Build {LOCAL_RELEASE_BUILD_NUMBER} "
            "Runtime-chat SQLite stable busy "
            "message must appear exactly once; found "
            f"{stable_message_count}."
        )

    for source_path in (
        (
            "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
            "RuntimeChatSQLiteCrossProcessQA.swift"
        ),
        "script/run_macos_runtime_chat_cross_process_smoke.py",
        "script/test_run_macos_runtime_chat_cross_process_smoke.py",
    ):
        size, sha256 = (
            LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS[
                source_path
            ]
        )
        required_source_bindings = (
            f"`{source_path}`",
            f"{size:,} bytes",
            f"`{sha256}`",
        )
        for binding in required_source_bindings:
            count = normalized_text.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: Build {LOCAL_RELEASE_BUILD_NUMBER} source "
                    "inventory must bind "
                    f"{source_path!r} with {binding!r} exactly once; found "
                    f"{count}."
                )
    return failures


def current_runtime_chat_sqlite_source_failures(
    source_bytes_by_relative: dict[str, bytes] | None = None,
) -> list[str]:
    failures: list[str] = []
    for relative, expected_identity in (
        LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS.items()
    ):
        try:
            source_bytes = (
                source_bytes_by_relative[relative]
                if source_bytes_by_relative is not None
                else (ROOT / relative).read_bytes()
            )
        except (KeyError, OSError) as error:
            failures.append(
                f"{relative}: cannot validate Build "
                f"{LOCAL_RELEASE_BUILD_NUMBER} Runtime-chat SQLite "
                f"source binding: {error}"
            )
            continue
        identity = (
            len(source_bytes),
            hashlib.sha256(source_bytes).hexdigest(),
        )
        if identity != expected_identity:
            failures.append(
                f"{relative}: expected Build {LOCAL_RELEASE_BUILD_NUMBER} "
                "source inventory identity "
                f"{expected_identity!r}, found {identity!r}."
            )

    test_relative = (
        "apps/macos/CompanionCore/Tests/SQLiteRuntimeChatEventStoreTests.swift"
    )
    try:
        test_source = (
            source_bytes_by_relative[test_relative]
            if source_bytes_by_relative is not None
            else (ROOT / test_relative).read_bytes()
        ).decode("utf-8")
    except (KeyError, OSError, UnicodeError) as error:
        failures.append(
            f"{test_relative}: cannot validate Build "
            f"{LOCAL_RELEASE_BUILD_NUMBER} Runtime-chat SQLite "
            f"Swift regressions: {error}"
        )
        test_source = ""
    for test_name in CURRENT_RUNTIME_CHAT_SQLITE_SWIFT_TESTS:
        declaration = f"func {test_name}() throws"
        count = test_source.count(declaration)
        if count != 1:
            failures.append(
                f"{test_relative}: exact Swift regression {test_name!r} must "
                f"appear once; found {count}."
            )

    store_relative = (
        "apps/macos/CompanionCore/Sources/SQLiteRuntimeChatEventStore.swift"
    )
    try:
        store_source = (
            source_bytes_by_relative[store_relative]
            if source_bytes_by_relative is not None
            else (ROOT / store_relative).read_bytes()
        ).decode("utf-8")
    except (KeyError, OSError, UnicodeError):
        store_source = ""
    for binding in (
        "private static let busyTimeoutMilliseconds: Int32 = 5_000",
        "sqlite3_busy_timeout(openedDatabase, Self.busyTimeoutMilliseconds)",
    ):
        if store_source.count(binding) != 1:
            failures.append(
                f"{store_relative}: exact production busy-timeout binding "
                f"{binding!r} must appear once."
            )
    return failures


def current_runtime_chat_sqlite_abrupt_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    relative = str(
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT.relative_to(ROOT)
    )
    if result_bytes is None:
        try:
            result_bytes = CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT.read_bytes()
        except OSError as error:
            return [f"{relative}: cannot read abrupt recovery result: {error}"]

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE,
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256,
    )
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected abrupt recovery identity "
            f"{expected_identity!r}, found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("ascii"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(f"{relative}: invalid abrupt recovery JSON: {error}")
        return failures

    expected_result = {
        "abruptTermination": {
            "checkpoint": {
                "committedPrefixCount": 24,
                "databaseCacheFlushed": True,
                "inFlightEventID": (
                    "qa-writer-a-inflight-uncommitted-v1"
                ),
                "insideTransactionEventCount": 25,
                "insideTransactionFTSEventCount": 25,
                "insideTransactionMutationRevision": 25,
                "insideTransactionValidatedRevision": 24,
                "journalMode": "delete",
                "schemaVersion": 1,
                "status": "ready-for-abrupt-termination",
                "transactionOpen": True,
                "writer": "writer-a",
            },
            "dirtyDatabaseBeforeRecovery": {
                "appendStateMutationRevision": 25,
                "appendStateValidatedRevision": 24,
                "eventCount": 25,
                "ftsEventCount": 25,
                "immutableReadIgnoredJournal": True,
                "inFlightEventAndFTSPresent": True,
            },
            "journal": {
                "hotJournalHeaderObserved": True,
                "journalMode": "delete",
                "ownerOnlyMode": "0600",
                "pageRecordCountPositive": True,
                "pageSize": 4_096,
                "sectorSize": 512,
            },
            "processGroup": "new-session-exact-child-only",
            "terminationSignal": "SIGKILL",
            "writerProcessReapedBeforeJournalObservation": True,
        },
        "cleanup": "passed",
        "committedPrefixCount": 24,
        "committedPrefixWritePath": (
            "production-SQLiteRuntimeChatEventStore"
        ),
        "final": {
            "appendStateRevision": 48,
            "eventCount": 48,
            "ftsEventCount": 48,
            "hotJournalCleared": True,
            "inFlightEventAndFTSAbsent": True,
            "integrityCheck": "ok",
            "residualJournalHeaderZeroed": False,
            "sequencesContiguous": True,
        },
        "finalReadbackProcess": "independent",
        "inFlightEventID": "qa-writer-a-inflight-uncommitted-v1",
        "inFlightTransactionWritePath": "qa-raw-sql-event-plus-fts-v1",
        "limitations": [
            "same-host-abrupt-child-process-termination-only",
            "not-production-append-crash-point",
            "not-power-loss-or-kernel-crash-evidence",
            "not-arbitrary-history-or-long-soak-evidence",
            "not-clean-machine-signed-distribution-or-device-evidence",
        ],
        "permissions": {
            "checkpointAndSQLiteFiles": "0600",
            "databaseRoot": "0700",
        },
        "recovered": {
            "appendStateRevision": 24,
            "eventCount": 24,
            "ftsEventCount": 24,
            "hotJournalCleared": True,
            "inFlightEventAndFTSAbsent": True,
            "integrityCheck": "ok",
            "residualJournalHeaderZeroed": False,
            "sequencesContiguous": True,
        },
        "recoveryReadbackProcess": "independent",
        "resume": {
            "endExclusive": 48,
            "eventCount": 24,
            "startOrdinal": 24,
            "status": "passed",
            "writer": "writer-a",
        },
        "resumeWritePath": "production-SQLiteRuntimeChatEventStore",
        "schemaVersion": 1,
        "scope": "macos-runtime-chat-sqlite-abrupt-process-recovery-v1",
        "status": "passed",
    }
    if not exact_json_values_equal(result, expected_result):
        failures.append(
            f"{relative}: result does not match the exact closed abrupt "
            "child-process recovery contract."
        )

    canonical = (
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if result_bytes != canonical:
        failures.append(
            f"{relative}: result must be canonical sorted compact ASCII JSON "
            "with one final LF."
        )
    return failures


def current_macos_clean_home_lifecycle_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    required_once = (
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-install-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256,
    )
    required_claims = (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_REPEATABILITY_CLAIM,
    )
    dmg_required_once = (
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-local-dmg-install-v1.json"
        ),
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256,
    )
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        HISTORICAL_BUILD20_RELEASE_DOC,
        LOCAL_RELEASE_CURRENT_DOC,
    )
    release_document_paths = {
        HISTORICAL_BUILD20_RELEASE_DOC,
        LOCAL_RELEASE_CURRENT_DOC,
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 20 lifecycle "
                f"bindings: {error}"
            )
            continue
        start_count = document_text.count(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 20 lifecycle block must contain "
                f"exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        body_start = start_index + len(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        end_index = document_text.index(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 20 lifecycle markers are "
                "reversed or empty."
            )
            continue
        outer_end_index = end_index + len(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        actual_outer_sha256 = (
            hashlib.sha256(
                document_text[:start_index].encode("utf-8")
            ).hexdigest(),
            hashlib.sha256(
                document_text[outer_end_index:].encode("utf-8")
            ).hexdigest(),
        )
        expected_outer_sha256 = (
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_OUTER_SHA256_BY_DOCUMENT[
                relative
            ]
        )
        if actual_outer_sha256 != expected_outer_sha256:
            failures.append(
                f"{relative}: historical Build 20 lifecycle outer document "
                "identity differs from its canonical location."
            )
        block = document_text[body_start:end_index]
        actual_body_sha256 = hashlib.sha256(
            block.encode("utf-8")
        ).hexdigest()
        expected_body_sha256 = (
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_BODY_SHA256_BY_DOCUMENT[
                relative
            ]
        )
        if actual_body_sha256 != expected_body_sha256:
            failures.append(
                f"{relative}: historical Build 20 lifecycle body must "
                f"retain exact SHA-256 {expected_body_sha256}; found "
                f"{actual_body_sha256}."
            )
        if any(
            neighbor not in document_text
            for neighbor in (
                CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_NEIGHBORS[
                    relative
                ]
            )
        ):
            failures.append(
                f"{relative}: historical Build 20 lifecycle block moved "
                "outside its canonical document location."
            )
        if marker_is_in_hidden_markdown_context(
            document_text,
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        ):
            failures.append(
                f"{relative}: historical Build 20 lifecycle block must "
                "remain outside hidden Markdown or HTML contexts."
            )
        normalized_block = re.sub(r"\s+", " ", block).strip()
        if "Build 20" not in normalized_block:
            failures.append(
                f"{relative}: current lifecycle block is not explicitly "
                "bound to Build 20."
            )
        historical_build_mentions = {
            int(value)
            for value in re.findall(
                r"\bBuild\s+([1-9][0-9]*)\b",
                normalized_block,
                re.IGNORECASE,
            )
            if int(value) < 20
        }
        historical_path_mentions = {
            int(value)
            for value in re.findall(
                r"macos-packaged-app-build-([1-9][0-9]*)-",
                normalized_block,
                re.IGNORECASE,
            )
            if int(value) < 20
        }
        historical_contamination = sorted(
            historical_build_mentions | historical_path_mentions
        )
        if historical_contamination:
            failures.append(
                f"{relative}: historical Build "
                f"{historical_contamination!r} content entered the current "
                "Build 20 lifecycle block."
            )
        future_build_mentions = {
            int(value)
            for value in re.findall(
                r"\bBuild\s+([1-9][0-9]*)\b",
                normalized_block,
                re.IGNORECASE,
            )
            if int(value) > 20
        }
        if future_build_mentions:
            failures.append(
                f"{relative}: current Build 20 lifecycle block contains future "
                f"Build {sorted(future_build_mentions)!r} content."
            )
        block_required_once = list(required_once)
        if path in release_document_paths:
            block_required_once.extend(
                (
                    CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256,
                    CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256,
                    (
                        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
                    ),
                    (
                        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256
                    ),
                )
            )
        for binding in block_required_once:
            count = block.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: current Build 20 lifecycle block must "
                    f"contain binding {binding!r} exactly once; found {count}."
                )
        dmg_scope = document_text if path in release_document_paths else block
        for binding in dmg_required_once:
            count = dmg_scope.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: current Build 20 DMG evidence must contain "
                    f"binding {binding!r} exactly once; found {count}."
                )
        size_expectations = (
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE,
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE,
        )
        for expected_size in size_expectations:
            formatted_size = f"{expected_size:,}"
            if not re.search(
                rf"\b{re.escape(formatted_size)}(?:-byte| bytes)\b",
                normalized_block,
            ):
                failures.append(
                    f"{relative}: current Build 20 lifecycle block is "
                    f"missing exact {formatted_size}-byte result size."
                )
        dmg_size_scope = (
            re.sub(r"\s+", " ", document_text).strip()
            if path in release_document_paths
            else normalized_block
        )
        dmg_size = f"{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE:,}"
        if not re.search(
            rf"\b{re.escape(dmg_size)}(?:-byte| bytes)\b",
            dmg_size_scope,
        ):
            failures.append(
                f"{relative}: current Build 20 DMG evidence is missing exact "
                f"{dmg_size}-byte result size."
            )
        for claim in required_claims:
            normalized_claim = re.sub(r"\s+", " ", claim).strip()
            count = normalized_block.count(normalized_claim)
            if count != 1:
                failures.append(
                    f"{relative}: current Build 20 lifecycle block is "
                    f"required to contain exact bounded claim {claim!r} "
                    f"once; found {count}."
                )
        boundary_match = re.search(
            r"\bThese historical same-host, per-user Build 20\b.*?"
            r"\bproduction readiness\.",
            normalized_block,
            re.IGNORECASE,
        )
        if boundary_match is None:
            failures.append(
                f"{relative}: current Build 20 lifecycle block is missing "
                "its bounded non-production sentence."
            )
            block_without_boundary = normalized_block
        else:
            boundary = boundary_match.group(0)
            for term in CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_BOUNDARY_TERMS:
                if term.lower() not in boundary.lower():
                    failures.append(
                        f"{relative}: current Build 20 lifecycle boundary is "
                        f"missing {term!r}."
                    )
            if not re.search(
                r"\bdo not (?:themselves )?qualify\b",
                boundary,
                re.IGNORECASE,
            ):
                failures.append(
                    f"{relative}: current Build 20 lifecycle boundary must "
                    "remain explicitly non-qualifying."
                )
            block_without_boundary = (
                normalized_block[: boundary_match.start()]
                + normalized_block[boundary_match.end() :]
            )
        prohibited_positive_claims = (
            r"\bqualif(?:y|ies|ied|ication)\b",
            r"\bprov(?:e|es|ed|en)\b",
            r"\bcertif(?:y|ies|ied|ication)\b",
            r"\bproduction[- ]ready\b",
            (
                r"\b(?:clean[- ]machine|DMG/Finder|signed/notarized|"
                r"physical[- ]device)\b.{0,100}\b(?:passes?|passed|"
                r"supports?|supported)\b"
            ),
            (
                r"\b(?:passes?|passed|supports?|supported)\b.{0,100}"
                r"\b(?:clean[- ]machine|DMG/Finder|signed/notarized|"
                r"physical[- ]device)\b"
            ),
        )
        for pattern in prohibited_positive_claims:
            if re.search(pattern, block_without_boundary, re.IGNORECASE):
                failures.append(
                    f"{relative}: current Build 20 lifecycle block contains "
                    "a contradictory positive qualification claim."
                )
                break
    return failures


def current_build24_macos_clean_home_lifecycle_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    expected_neighbors = {
        "README.md": (
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/roadmap.md": (
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/handoff.md": (
            (
                CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/progress.md": (
            (
                "## 2026-07-31 macOS Build 24 Clean-HOME Lifecycle\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Lifecycle\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/qa-evidence.md": (
            (
                "## 2026-07-31 macOS Build 24 Clean-HOME Lifecycle "
                "Checklist\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Lifecycle Checklist\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                "## Current Build 24 Clean-HOME Lifecycle Evidence\n\n"
                + CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n## Current Build 24 Local-DMG Lifecycle "
                "Evidence\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24 clean-HOME "
                f"lifecycle block: {error}"
            )
            continue

        start_count = document_text.count(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24 clean-HOME lifecycle block "
                "must contain exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue

        chain_markers = (
            CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START,
            CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END,
            CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
            CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END,
            CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START,
            CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END,
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_END
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_END
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_END
            ),
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START,
            CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_END,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_END,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_START,
            CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_END,
        )
        chain_is_ordered = (
            all(document_text.count(marker) == 1 for marker in chain_markers)
            and sorted(document_text.index(marker) for marker in chain_markers)
            == [document_text.index(marker) for marker in chain_markers]
        )
        if not chain_is_ordered:
            failures.append(
                f"{relative}: current Build 24 lifecycle chain markers "
                "must appear once in isolated, clean-HOME, local-DMG, "
                "uninstall/reinstall, state-recovery, abrupt-process "
                "recovery, aggregate-readback, reverse-version-readback, "
                "idle-resource-stability order."
            )
        else:
            chain_start_index = document_text.index(chain_markers[0])
            chain_end_index = (
                document_text.index(chain_markers[-1])
                + len(chain_markers[-1])
            )
            actual_outer_sha256 = (
                hashlib.sha256(
                    document_text[:chain_start_index].encode("utf-8")
                ).hexdigest(),
                hashlib.sha256(
                    document_text[chain_end_index:].encode("utf-8")
                ).hexdigest(),
            )
            expected_outer_sha256 = (
                CURRENT_BUILD24_MACOS_LIFECYCLE_CHAIN_OUTER_SHA256_BY_DOCUMENT[
                    relative
                ]
            )
            if actual_outer_sha256 != expected_outer_sha256:
                failures.append(
                    f"{relative}: current Build 24 lifecycle chain outer "
                    "document identity differs from its canonical location."
                )
        if (
            CURRENT_BUILD24_MACOS_LIFECYCLE_CHAIN_PREDECESSOR_BY_DOCUMENT[
                relative
            ]
            not in document_text
        ):
            failures.append(
                f"{relative}: current Build 24 lifecycle chain moved away "
                "from its canonical external predecessor."
            )
        if any(
            marker_is_in_hidden_markdown_context(document_text, marker)
            for marker in chain_markers
        ):
            failures.append(
                f"{relative}: current Build 24 lifecycle chain must remain "
                "outside hidden Markdown or HTML contexts."
            )

        start_index = document_text.index(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        body_start = start_index + len(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        end_index = document_text.index(
            CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24 clean-HOME lifecycle markers "
                "are reversed or empty."
            )
            continue

        block = document_text[body_start:end_index].strip()
        if block != CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_BODY:
            expected_sha256 = hashlib.sha256(
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_BODY.encode(
                    "utf-8"
                )
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24 clean-HOME lifecycle block "
                f"must match exact canonical body SHA-256 {expected_sha256}; "
                f"found {actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24 clean-HOME lifecycle block "
                "moved outside its canonical document location."
            )
    return failures


def current_build24_macos_local_dmg_lifecycle_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    expected_neighbors = {
        "README.md": (
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + (
                    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
                )
            ),
        ),
        "docs/roadmap.md": (
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + (
                    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
                )
            ),
        ),
        "docs/handoff.md": (
            (
                CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + (
                    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
                )
            ),
        ),
        "docs/progress.md": (
            (
                "## 2026-07-31 macOS Build 24 Local-DMG Lifecycle\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall Lifecycle\n\n"
                + (
                    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
                )
            ),
        ),
        "docs/qa-evidence.md": (
            (
                "## 2026-07-31 macOS Build 24 Local-DMG Lifecycle "
                "Checklist\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall Lifecycle Checklist\n\n"
                + (
                    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
                )
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                "## Current Build 24 Local-DMG Lifecycle Evidence\n\n"
                + CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
            ),
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n## Current Build 24 Local-DMG "
                "Uninstall/Reinstall Lifecycle Evidence\n\n"
                + (
                    CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
                )
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24 local-DMG "
                f"lifecycle block: {error}"
            )
            continue

        start_count = document_text.count(
            CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24 local-DMG lifecycle block "
                "must contain exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue

        start_index = document_text.index(
            CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
        )
        body_start = start_index + len(
            CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
        )
        end_index = document_text.index(
            CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
        )
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24 local-DMG lifecycle markers "
                "are reversed or empty."
            )
            continue

        block = document_text[body_start:end_index].strip()
        if (
            block
            != CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_BODY
        ):
            expected_sha256 = hashlib.sha256(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_BODY.encode(
                    "utf-8"
                )
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24 local-DMG lifecycle block "
                f"must match exact canonical body SHA-256 {expected_sha256}; "
                f"found {actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24 local-DMG lifecycle block "
                "moved outside its canonical document location."
            )
    return failures


def current_build24_macos_local_dmg_uninstall_reinstall_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    start_marker = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
    )
    end_marker = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_END
    )
    state_start_marker = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_START
    )
    expected_neighbors = {
        "README.md": (
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + start_marker
            ),
            end_marker + "\n\n" + state_start_marker,
        ),
        "docs/roadmap.md": (
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + start_marker
            ),
            end_marker + "\n\n" + state_start_marker,
        ),
        "docs/handoff.md": (
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n"
                + start_marker
            ),
            end_marker + "\n\n" + state_start_marker,
        ),
        "docs/progress.md": (
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall Lifecycle\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall State Recovery\n\n"
                + state_start_marker
            ),
        ),
        "docs/qa-evidence.md": (
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall Lifecycle Checklist\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall State Recovery Checklist\n\n"
                + state_start_marker
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
                + "\n\n## Current Build 24 Local-DMG "
                "Uninstall/Reinstall Lifecycle Evidence\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## Current Build 24 Local-DMG "
                "Uninstall/Reinstall State-Recovery Evidence\n\n"
                + state_start_marker
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24 same-DMG "
                f"uninstall/reinstall lifecycle block: {error}"
            )
            continue

        start_count = document_text.count(start_marker)
        end_count = document_text.count(end_marker)
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24 same-DMG "
                "uninstall/reinstall lifecycle block must contain exactly "
                "one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(start_marker)
        body_start = start_index + len(start_marker)
        end_index = document_text.index(end_marker)
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24 same-DMG "
                "uninstall/reinstall lifecycle markers are reversed or "
                "empty."
            )
            continue
        block = document_text[body_start:end_index].strip()
        if (
            block
            != CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_BODY
        ):
            expected_sha256 = hashlib.sha256(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_BODY.encode(
                    "utf-8"
                )
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24 same-DMG "
                "uninstall/reinstall lifecycle block must match exact "
                f"canonical body SHA-256 {expected_sha256}; found "
                f"{actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24 same-DMG "
                "uninstall/reinstall lifecycle block moved outside its "
                "canonical document location."
            )
        if any(
            marker_is_in_hidden_markdown_context(document_text, marker)
            for marker in (start_marker, end_marker)
        ):
            failures.append(
                f"{relative}: current Build 24 same-DMG "
                "uninstall/reinstall lifecycle block must remain outside "
                "hidden Markdown or HTML contexts."
            )
    return failures


def current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    predecessor = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_END
    )
    start_marker = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_START
    )
    end_marker = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_END
    )
    successor = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_START
    )
    expected_neighbors = {
        "README.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\n" + successor,
        ),
        "docs/roadmap.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\n" + successor,
        ),
        "docs/handoff.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\n" + successor,
        ),
        "docs/progress.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall State Recovery\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Persisted-State Abrupt Process Recovery\n\n"
                + successor
            ),
        ),
        "docs/qa-evidence.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Uninstall/Reinstall State Recovery Checklist\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Persisted-State Abrupt Process Recovery Checklist\n\n"
                + successor
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                predecessor
                + "\n\n## Current Build 24 Local-DMG "
                "Uninstall/Reinstall State-Recovery Evidence\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## Current Build 24 Local-DMG Persisted-State "
                "Abrupt Process Recovery Evidence\n\n"
                + successor
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24 same-DMG "
                f"state-recovery lifecycle block: {error}"
            )
            continue

        start_count = document_text.count(start_marker)
        end_count = document_text.count(end_marker)
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24 same-DMG state-recovery "
                "lifecycle block must contain exactly one start and end "
                f"marker; found {start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(start_marker)
        body_start = start_index + len(start_marker)
        end_index = document_text.index(end_marker)
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24 same-DMG state-recovery "
                "lifecycle markers are reversed or empty."
            )
            continue
        block = document_text[body_start:end_index].strip()
        if (
            block
            != CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_BODY
        ):
            expected_sha256 = hashlib.sha256(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_BODY.encode(
                    "utf-8"
                )
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24 same-DMG state-recovery "
                "lifecycle block must match exact canonical body SHA-256 "
                f"{expected_sha256}; found {actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24 same-DMG state-recovery "
                "lifecycle block moved outside its canonical document "
                "location."
            )
        if any(
            marker_is_in_hidden_markdown_context(document_text, marker)
            for marker in (start_marker, end_marker)
        ):
            failures.append(
                f"{relative}: current Build 24 same-DMG state-recovery "
                "lifecycle block must remain outside hidden Markdown or "
                "HTML contexts."
            )
    return failures


def current_build24_macos_local_dmg_abrupt_process_state_recovery_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    predecessor = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_END
    )
    start_marker = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_START
    )
    end_marker = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_END
    )
    expected_neighbors = {
        "README.md": (
            predecessor + "\n\n" + start_marker,
            (
                end_marker
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
            ),
        ),
        "docs/roadmap.md": (
            predecessor + "\n\n" + start_marker,
            (
                end_marker
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
            ),
        ),
        "docs/handoff.md": (
            predecessor + "\n\n" + start_marker,
            (
                end_marker
                + "\n\n"
                + CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
            ),
        ),
        "docs/progress.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Persisted-State Abrupt Process Recovery\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Lifecycle "
                "Aggregate Readback\n\n"
                + CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
            ),
        ),
        "docs/qa-evidence.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Local-DMG "
                "Persisted-State Abrupt Process Recovery Checklist\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Lifecycle "
                "Aggregate Readback Checklist\n\n"
                + CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                predecessor
                + "\n\n## Current Build 24 Local-DMG Persisted-State "
                "Abrupt Process Recovery Evidence\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## Current Build 24 Lifecycle Aggregate "
                "Readback Evidence\n\n"
                + CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24 "
                f"abrupt-process state-recovery block: {error}"
            )
            continue

        start_count = document_text.count(start_marker)
        end_count = document_text.count(end_marker)
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24 abrupt-process "
                "state-recovery block must contain exactly one start and "
                f"end marker; found {start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(start_marker)
        body_start = start_index + len(start_marker)
        end_index = document_text.index(end_marker)
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24 abrupt-process "
                "state-recovery markers are reversed or empty."
            )
            continue
        block = document_text[body_start:end_index].strip()
        if (
            block
            != CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_BODY
        ):
            expected_sha256 = hashlib.sha256(
                CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_BODY.encode(
                    "utf-8"
                )
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24 abrupt-process "
                "state-recovery block must match exact canonical body "
                f"SHA-256 {expected_sha256}; found {actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24 abrupt-process "
                "state-recovery block moved outside its canonical "
                "document location."
            )
        if any(
            marker_is_in_hidden_markdown_context(document_text, marker)
            for marker in (start_marker, end_marker)
        ):
            failures.append(
                f"{relative}: current Build 24 abrupt-process "
                "state-recovery block must remain outside hidden Markdown "
                "or HTML contexts."
            )
    return failures


def current_build24_macos_lifecycle_aggregate_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    predecessor = (
        CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_END
    )
    start_marker = CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
    end_marker = CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_END
    expected_neighbors = {
        "README.md": (
            predecessor + "\n\n" + start_marker,
            (
                end_marker
                + "\n\n"
                + CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
            ),
        ),
        "docs/roadmap.md": (
            predecessor + "\n\n" + start_marker,
            (
                end_marker
                + "\n\n"
                + CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
            ),
        ),
        "docs/handoff.md": (
            predecessor + "\n\n" + start_marker,
            (
                end_marker
                + "\n\n"
                + CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
            ),
        ),
        "docs/progress.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Lifecycle "
                "Aggregate Readback\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-08-01 macOS Build 24-to-23-to-24 "
                "Bounded Reverse-Version Readback\n\n"
                + CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
            ),
        ),
        "docs/qa-evidence.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Lifecycle "
                "Aggregate Readback Checklist\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-08-01 macOS Build 24-to-23-to-24 "
                "Bounded Reverse-Version Readback Checklist\n\n"
                + CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                predecessor
                + "\n\n## Current Build 24 Lifecycle Aggregate "
                "Readback Evidence\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## Post-Archive Build 24-to-23-to-24 Bounded "
                "Reverse-Version Readback Evidence\n\n"
                + CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24 lifecycle "
                f"aggregate readback block: {error}"
            )
            continue

        start_count = document_text.count(start_marker)
        end_count = document_text.count(end_marker)
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24 lifecycle aggregate "
                "readback block must contain exactly one start and end "
                f"marker; found {start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(start_marker)
        body_start = start_index + len(start_marker)
        end_index = document_text.index(end_marker)
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24 lifecycle aggregate "
                "readback markers are reversed or empty."
            )
            continue

        block = document_text[body_start:end_index].strip()
        if block != CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_BODY:
            expected_sha256 = hashlib.sha256(
                CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_BODY.encode(
                    "utf-8"
                )
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24 lifecycle aggregate "
                "readback block must match exact canonical body SHA-256 "
                f"{expected_sha256}; found {actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24 lifecycle aggregate "
                "readback block moved outside its canonical document "
                "location."
            )
        if any(
            marker_is_in_hidden_markdown_context(document_text, marker)
            for marker in (start_marker, end_marker)
        ):
            failures.append(
                f"{relative}: current Build 24 lifecycle aggregate "
                "readback block must remain outside hidden Markdown or "
                "HTML contexts."
            )
    return failures


def current_build24_reverse_version_readback_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    predecessor = CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_END
    start_marker = CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
    end_marker = CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_END
    successor = CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_START
    expected_neighbors = {
        "README.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\n" + successor,
        ),
        "docs/roadmap.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\n" + successor,
        ),
        "docs/handoff.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\n" + successor,
        ),
        "docs/progress.md": (
            (
                predecessor
                + "\n\n## 2026-08-01 macOS Build 24-to-23-to-24 "
                "Bounded Reverse-Version Readback\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Idle Resource "
                "Stability\n\n"
                + successor
            ),
        ),
        "docs/qa-evidence.md": (
            (
                predecessor
                + "\n\n## 2026-08-01 macOS Build 24-to-23-to-24 "
                "Bounded Reverse-Version Readback Checklist\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 macOS Build 24 Idle Resource "
                "Stability Checklist\n\n"
                + successor
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                predecessor
                + "\n\n## Post-Archive Build 24-to-23-to-24 Bounded "
                "Reverse-Version Readback Evidence\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## Current Build 24 Idle Resource Stability "
                "Evidence\n\n"
                + successor
            ),
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24-to-23-to-24 "
                f"reverse-version readback block: {error}"
            )
            continue

        start_count = document_text.count(start_marker)
        end_count = document_text.count(end_marker)
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24-to-23-to-24 reverse-version "
                "readback block must contain exactly one start and end "
                f"marker; found {start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(start_marker)
        body_start = start_index + len(start_marker)
        end_index = document_text.index(end_marker)
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24-to-23-to-24 reverse-version "
                "readback markers are reversed or empty."
            )
            continue

        block = document_text[body_start:end_index]
        expected_block = (
            "\n"
            + CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_BODY
            + "\n"
        )
        if block != expected_block:
            expected_sha256 = hashlib.sha256(
                expected_block.encode("utf-8")
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24-to-23-to-24 reverse-version "
                "readback block must match exact canonical body SHA-256 "
                f"{expected_sha256}; found {actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24-to-23-to-24 reverse-version "
                "readback block moved outside its canonical document "
                "location."
            )
        if any(
            marker_is_in_hidden_markdown_context(document_text, marker)
            for marker in (start_marker, end_marker)
        ):
            failures.append(
                f"{relative}: current Build 24-to-23-to-24 reverse-version "
                "readback block must remain outside hidden Markdown or "
                "HTML contexts."
            )
    return failures


def current_build24_macos_idle_resource_stability_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    predecessor = CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_END
    start_marker = (
        CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_START
    )
    end_marker = CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_END
    expected_neighbors = {
        "README.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\nThis is a personal, single-owner project.",
        ),
        "docs/roadmap.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\nThe current macOS G5 Runtime slice",
        ),
        "docs/handoff.md": (
            predecessor + "\n\n" + start_marker,
            end_marker + "\n\n- Build 19 remains",
        ),
        "docs/progress.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Idle Resource "
                "Stability\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 Historical Local V1 Build 23 "
                "Qualification"
            ),
        ),
        "docs/qa-evidence.md": (
            (
                predecessor
                + "\n\n## 2026-07-31 macOS Build 24 Idle Resource "
                "Stability Checklist\n\n"
                + start_marker
            ),
            (
                end_marker
                + "\n\n## 2026-07-31 Historical Local V1 Build 23 "
                "Qualification Checklist"
            ),
        ),
        "docs/releases/1.0.0-build-24-local-v1.md": (
            (
                predecessor
                + "\n\n## Current Build 24 Idle Resource Stability "
                "Evidence\n\n"
                + start_marker
            ),
            end_marker + "\n\n## Compatibility And Transition Boundary",
        ),
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 24 "
                f"idle-resource stability block: {error}"
            )
            continue

        start_count = document_text.count(start_marker)
        end_count = document_text.count(end_marker)
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 24 idle-resource stability "
                "block must contain exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(start_marker)
        body_start = start_index + len(start_marker)
        end_index = document_text.index(end_marker)
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 24 idle-resource stability "
                "markers are reversed or empty."
            )
            continue

        block = document_text[body_start:end_index].strip()
        if (
            block
            != CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_BODY
        ):
            expected_sha256 = hashlib.sha256(
                CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_BODY.encode(
                    "utf-8"
                )
            ).hexdigest()
            actual_sha256 = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
            failures.append(
                f"{relative}: current Build 24 idle-resource stability "
                "block must match exact canonical body SHA-256 "
                f"{expected_sha256}; found {actual_sha256}."
            )
        if any(
            binding not in document_text
            for binding in expected_neighbors[relative]
        ):
            failures.append(
                f"{relative}: current Build 24 idle-resource stability "
                "block moved outside its canonical document location."
            )
        if any(
            marker_is_in_hidden_markdown_context(document_text, marker)
            for marker in (start_marker, end_marker)
        ):
            failures.append(
                f"{relative}: current Build 24 idle-resource stability "
                "block must remain outside hidden Markdown or HTML contexts."
            )
    return failures


def top_level_shell_command_definitely_terminates(
    command: str,
    *,
    errexit_enabled: bool,
) -> bool:
    if re.search(
        r"(?:^|;|&&|\|\||[&|])\s*(?:exit|return)(?:\s|$)",
        command,
    ):
        return True
    if re.search(
        r"(?:^|;)\s*exec\s+(?![0-9]*[<>])\S+",
        command,
    ):
        return True
    return (
        errexit_enabled
        and re.fullmatch(
            r"(?:(?:command|builtin|run)\s+)*false(?:\s+[^;&|]*)?",
            command,
        )
        is not None
    )


def shell_prefix_reaches_top_level(prefix: str) -> bool:
    active_heredoc: tuple[str, bool] | None = None
    inside_function = False
    control_stack: list[str] = []
    group_stack: list[str] = []
    quote_state: str | None = None
    pending_command_chain = False
    errexit_enabled = False
    function_start = re.compile(
        r"^(?:function\s+)?[A-Za-z_][A-Za-z0-9_]*"
        r"(?:\s*\(\))?\s*\{\s*$"
    )
    heredoc_start = re.compile(
        r"<<(-?)\s*(?:'([^']+)'|\"([^\"]+)\"|"
        r"([A-Za-z_][A-Za-z0-9_]*))"
    )

    def mask_quoted_shell_text(
        line: str,
        initial_state: str | None,
    ) -> tuple[str, str | None]:
        masked = list(line)
        state = initial_state
        index = 0
        while index < len(line):
            character = line[index]
            if state == "'":
                masked[index] = " "
                if character == "'":
                    state = None
                index += 1
                continue
            if state in {'"', "`"}:
                masked[index] = " "
                if character == "\\" and index + 1 < len(line):
                    masked[index + 1] = " "
                    index += 2
                    continue
                if character == state:
                    state = None
                index += 1
                continue
            if character == "#" and (
                index == 0 or line[index - 1].isspace()
            ):
                masked[index:] = [" "] * (len(line) - index)
                break
            if character == "\\" and index + 1 < len(line):
                masked[index] = " "
                masked[index + 1] = " "
                index += 2
                continue
            if character in {"'", '"', "`"}:
                state = character
                masked[index] = " "
            index += 1
        return "".join(masked), state

    for raw_line in prefix.splitlines():
        if active_heredoc is not None:
            delimiter, strip_tabs = active_heredoc
            candidate = raw_line.lstrip("\t") if strip_tabs else raw_line
            if candidate == delimiter:
                active_heredoc = None
            continue

        heredoc_match = (
            None
            if quote_state is not None
            else heredoc_start.search(raw_line)
        )
        if heredoc_match is not None:
            delimiter = next(
                group
                for group in heredoc_match.groups()[1:]
                if group is not None
            )
            active_heredoc = (delimiter, heredoc_match.group(1) == "-")

        if inside_function:
            if raw_line == "}":
                inside_function = False
            continue

        masked_line, quote_state = mask_quoted_shell_text(
            raw_line,
            quote_state,
        )
        stripped = masked_line.strip()
        if not stripped:
            continue
        if function_start.fullmatch(stripped):
            inside_function = True
            continue
        if heredoc_match is not None:
            continue

        closing_group = re.match(
            r"^([})])(?:\s*(?:;|&&|\|\|))?\s*$",
            stripped,
        )
        if closing_group is not None:
            if group_stack:
                group_stack.pop()
            pending_command_chain = bool(
                re.search(r"(?:&&|\|\|)\s*$", stripped)
            )
            continue
        if re.search(r"(?:^|&&|\|\||[;&|])\s*\{\s*$", stripped):
            group_stack.append("brace")
            pending_command_chain = False
            continue
        if re.search(r"(?:^|&&|\|\||[;&|])\s*\(\s*$", stripped):
            group_stack.append("subshell")
            pending_command_chain = False
            continue

        closing_control = re.match(r"^(fi|done|esac)\b", stripped)
        if closing_control is not None:
            if control_stack:
                control_stack.pop()
            pending_command_chain = False
            continue
        if re.match(r"^if(?:\s|$)", stripped):
            control_stack.append("if")
            pending_command_chain = False
            continue
        if re.match(r"^(?:for|while|until)(?:\s|$)", stripped):
            control_stack.append("loop")
            pending_command_chain = False
            continue
        if re.match(r"^case(?:\s|$)", stripped):
            control_stack.append("case")
            pending_command_chain = False
            continue
        if not control_stack and not group_stack:
            if re.match(r"^set\s+-[A-Za-z]*e[A-Za-z]*(?:\s|$)", stripped):
                errexit_enabled = True
            elif re.match(
                r"^set\s+\+[A-Za-z]*e[A-Za-z]*(?:\s|$)",
                stripped,
            ):
                errexit_enabled = False
            if top_level_shell_command_definitely_terminates(
                stripped,
                errexit_enabled=errexit_enabled,
            ):
                return False
        pending_command_chain = bool(
            re.search(r"(?:&&|\|\||\\)\s*$", stripped)
        )

    return not (
        active_heredoc is not None
        or inside_function
        or control_stack
        or group_stack
        or quote_state is not None
        or pending_command_chain
    )


def reachable_top_level_continued_commands(
    shell_text: str,
    command_start: str,
) -> list[list[str]]:
    pattern = re.compile(
        r"(?m)^" + re.escape(command_start) + r"\s*\\\s*$"
    )
    commands: list[list[str]] = []
    for match in pattern.finditer(shell_text):
        if not shell_prefix_reaches_top_level(shell_text[: match.start()]):
            continue
        command_lines: list[str] = []
        command_is_simple = True
        for raw_line in shell_text[match.start() :].splitlines():
            if "#" in raw_line:
                command_is_simple = False
            without_comment = raw_line.split("#", 1)[0].rstrip()
            continued = without_comment.endswith("\\")
            if continued:
                without_comment = without_comment[:-1].rstrip()
            if not without_comment.strip():
                command_is_simple = False
            command_lines.append(without_comment)
            if not continued:
                break
        tokens = [
            token
            for line in command_lines
            for token in line.strip().split()
            if token
        ]
        if any(
            re.fullmatch(r"[A-Za-z0-9_./:+-]+", token) is None
            for token in tokens
        ):
            command_is_simple = False
        if command_is_simple:
            commands.append(tokens)
    return commands


def current_build24_macos_local_dmg_default_gate_failures(
    *,
    gate_text: str | None = None,
) -> list[str]:
    gate_path = ROOT / "script/check_no_device_quality.sh"
    if gate_text is None:
        try:
            gate_text = gate_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                "script/check_no_device_quality.sh: cannot validate current "
                f"Build 24 local-DMG default-gate selectors: {error}"
            ]

    expected_invocation = """\
run python3 -I -B -S script/check_macos_build24_lifecycle_evidence.py
run python3 -I -B -S script/check_macos_build24_idle_resource_stability_evidence.py
run python3 script/check_docs_hygiene.py
run python3 -B -m unittest \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_clean_home_results_match_closed_contracts \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_clean_home_sources_and_documents_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_clean_home_validators_are_wired_into_main \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_result_and_sources_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_documents_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_validators_are_wired_into_main \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_uninstall_reinstall_result_and_sources_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_uninstall_reinstall_documents_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_uninstall_reinstall_validators_are_wired_into_main \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_uninstall_reinstall_state_recovery_result_and_sources_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_uninstall_reinstall_state_recovery_documents_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_uninstall_reinstall_state_recovery_validators_are_wired_into_main \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_abrupt_process_state_recovery_result_receipt_and_sources_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_abrupt_process_state_recovery_documents_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_local_dmg_abrupt_process_state_recovery_validators_are_wired_into_main \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_macos_lifecycle_aggregate_sources_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_macos_lifecycle_aggregate_documents_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_macos_lifecycle_aggregate_validators_are_wired_into_main \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_macos_idle_resource_stability_result_and_sources_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_macos_idle_resource_stability_documents_are_bound \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_build24_macos_idle_resource_stability_validators_are_wired_into_main
"""
    current_source_g6_invocation = """\
run python3 -B -m unittest \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_reproducibility_matches_closed_contract \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_reproducibility_rejects_semantic_drift \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_reproducibility_rejects_noncanonical_json \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_swift_root_diagnostics_match_closed_contract \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_swift_root_diagnostics_reject_identity_shape_and_noncanonical_json \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_swift_root_diagnostics_reject_root_geometry_and_promotion \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_swift_root_diagnostics_reject_cross_mode_and_repeat_two_drift \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_swift_root_diagnostics_retain_recorded_source \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_swift_root_diagnostics_reject_missing_and_symlink \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lifecycle_two_matches_runner_contract \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lifecycle_two_rejects_parent_and_child_drift \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lifecycle_two_rejects_path_alias_missing_and_symlink \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lifecycle_two_uses_recorded_source_and_avoids_physical_helpers \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lifecycle_two_is_full_mode_only \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_matches_closed_contract \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_idle_resource_matches_closed_contract \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_idle_resource_rejects_drift \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_idle_resource_rejects_crossbinding_drift \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_rejects_drift \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_rejects_shape_and_encoding \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_followups_reject_shape_and_encoding \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_followups_reject_crossbinding_drift \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_rejects_missing_and_symlink \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_followups_reject_missing_and_symlink \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_primary_rejects_missing_and_symlink \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_evidence_rejects_read_time_symlink_swap \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_crossbinds_primary_bytes \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_documents_match \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_documents_reject_mutation \\
  script.test_documentation_handoff_guards.DocumentationHandoffGuardTests.test_current_source_g6_lane_a_local_dmg_documents_reject_move
"""
    aggregate_invocation = (
        "run python3 -I -B -S "
        "script/check_macos_build24_lifecycle_evidence.py"
    )
    aggregate_selectors = (
        (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            "test_current_build24_macos_lifecycle_aggregate_"
            "sources_are_bound"
        ),
        (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            "test_current_build24_macos_lifecycle_aggregate_"
            "documents_are_bound"
        ),
        (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            "test_current_build24_macos_lifecycle_aggregate_"
            "validators_are_wired_into_main"
        ),
    )
    idle_resource_invocation = (
        "run python3 -I -B -S "
        "script/check_macos_build24_idle_resource_stability_evidence.py"
    )
    idle_resource_selectors = (
        (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            "test_current_build24_macos_idle_resource_stability_"
            "result_and_sources_are_bound"
        ),
        (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            "test_current_build24_macos_idle_resource_stability_"
            "documents_are_bound"
        ),
        (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            "test_current_build24_macos_idle_resource_stability_"
            "validators_are_wired_into_main"
        ),
    )
    if (
        gate_text.count(expected_invocation) != 1
        or gate_text.count(current_source_g6_invocation) != 1
        or gate_text.count(aggregate_invocation) != 1
        or gate_text.count(idle_resource_invocation) != 1
        or any(gate_text.count(selector) != 1 for selector in aggregate_selectors)
        or any(
            gate_text.count(selector) != 1
            for selector in idle_resource_selectors
        )
    ):
        return [
            "script/check_no_device_quality.sh: current Build 24 local-DMG "
            "lifecycle aggregate, idle-resource, and current-source G6 "
            "selectors and static checkers must appear exactly once in "
            "reachable active invocations around docs hygiene."
        ]
    syntax_commands = reachable_top_level_continued_commands(
        gate_text,
        "run check_python_syntax",
    )
    if (
        len(syntax_commands) != 1
        or syntax_commands[0][:2] != ["run", "check_python_syntax"]
        or any(
            re.fullmatch(r"script/[A-Za-z0-9_./-]+\.py", token) is None
            for token in syntax_commands[0][2:]
        )
        or any(
            syntax_commands[0].count(path) != 1
            for path in (
                "script/check_macos_build24_lifecycle_evidence.py",
                "script/test_check_macos_build24_lifecycle_evidence.py",
                (
                    "script/check_macos_build24_"
                    "idle_resource_stability_evidence.py"
                ),
                (
                    "script/test_check_macos_build24_"
                    "idle_resource_stability_evidence.py"
                ),
                (
                    "script/run_macos_build24_"
                    "idle_resource_stability_smoke.py"
                ),
                (
                    "script/test_run_macos_build24_"
                    "idle_resource_stability_smoke.py"
                ),
                "script/run_macos_local_dmg_uninstall_reinstall_smoke.py",
                "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py",
                (
                    "script/run_macos_local_dmg_uninstall_reinstall_"
                    "state_recovery_smoke.py"
                ),
                (
                    "script/test_run_macos_local_dmg_uninstall_reinstall_"
                    "state_recovery_smoke.py"
                ),
                (
                    "script/run_macos_local_dmg_uninstall_reinstall_"
                    "abrupt_process_state_recovery_smoke.py"
                ),
                (
                    "script/test_run_macos_local_dmg_uninstall_reinstall_"
                    "abrupt_process_state_recovery_smoke.py"
                ),
            )
        )
    ):
        return [
            "script/check_no_device_quality.sh: current Build 24 lifecycle "
            "aggregate and idle-resource checker/test plus the idle and "
            "same-DMG lifecycle runner/test must each appear exactly once "
            "in the reachable top-level Python syntax inventory."
        ]
    unit_commands = reachable_top_level_continued_commands(
        gate_text,
        "run python3 -m unittest",
    )
    full_unit_commands = [
        command
        for command in unit_commands
        if (
            command[:4] == ["run", "python3", "-m", "unittest"]
            and all(
                re.fullmatch(
                    r"script/[A-Za-z0-9_./-]+\.py",
                    token,
                )
                is not None
                for token in command[4:]
            )
            and "script/test_v1_g0_checkpoint.py" in command
            and "script/test_android_usb_install.py" in command
        )
    ]
    required_unit_paths = (
        "script/test_check_macos_build24_lifecycle_evidence.py",
        (
            "script/test_check_macos_build24_"
            "idle_resource_stability_evidence.py"
        ),
        (
            "script/test_run_macos_build24_"
            "idle_resource_stability_smoke.py"
        ),
        "script/test_release_version_ledger.py",
        "script/test_run_macos_packaged_app_lifecycle_smoke.py",
        "script/test_run_macos_packaged_app_state_recovery_smoke.py",
        "script/test_run_macos_clean_home_installed_app_smoke.py",
        "script/test_run_macos_clean_home_installed_state_recovery_smoke.py",
        "script/test_run_macos_isolated_uninstall_reinstall_smoke.py",
        "script/test_run_macos_isolated_upgrade_smoke.py",
        "script/test_run_macos_local_dmg_install_smoke.py",
        "script/test_run_macos_local_dmg_install_smoke_v2.py",
        "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py",
        (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke.py"
        ),
        (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        ),
    )
    if (
        len(full_unit_commands) != 1
        or any(
            full_unit_commands[0].count(path) != 1
            for path in required_unit_paths
        )
    ):
        return [
            "script/check_no_device_quality.sh: current Build 24 lifecycle "
            "aggregate test, idle-resource checker/runner tests, and all "
            "12 byte-bound focused lifecycle unit modules must each appear "
            "exactly once in the "
            "reachable top-level full Python unittest inventory."
        ]

    if re.search(
        r"(?m)^run\s+python3(?:\s+\S+)*\s+"
        r"script/run_macos_build24_idle_resource_stability_smoke\.py(?:\s|$)",
        gate_text,
    ):
        return [
            "script/check_no_device_quality.sh: the retained ten-minute "
            "idle-resource runner must not execute in the default gate."
        ]

    invocation_index = gate_text.index(expected_invocation)
    current_source_invocation_index = gate_text.index(
        current_source_g6_invocation
    )
    if not (
        shell_prefix_reaches_top_level(gate_text[:invocation_index])
        and shell_prefix_reaches_top_level(
            gate_text[:current_source_invocation_index]
        )
    ):
        return [
            "script/check_no_device_quality.sh: current Build 24 local-DMG "
            "and current-source G6 selector invocations must execute at "
            "reachable top-level shell scope before any definite terminator."
        ]
    return []


def current_android_drawer_search_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        (
            ROOT / "docs/roadmap.md",
            "The current unreleased G5 product-quality slice",
            "The current G5 accessibility slice",
        ),
        (
            ROOT / "docs/handoff.md",
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END,
            "- The multilingual full-matrix V3 path",
        ),
        (
            ROOT / "docs/progress.md",
            "## 2026-07-29 Unreleased Android Drawer Semantic Chat Search UX",
            "## 2026-07-29 Unreleased Multilingual Full-Matrix V3 Preparation",
        ),
        (
            ROOT / "docs/qa-evidence.md",
            "## 2026-07-29 Android Drawer Semantic Chat Search UX Checklist",
            "## 2026-07-29 Multilingual Full-Matrix V3 Preparation Checklist",
        ),
    )
    required_claims = (
        CURRENT_ANDROID_DRAWER_SEARCH_BEHAVIOR_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_ACTION_STATE_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_PENDING_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_RESULT_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_EVIDENCE_CLAIM,
    )
    stale_current_markers = (
        "1,179 tests",
        "1,191-test",
        "1,192-test",
        "167 AppNavigationTest",
        "167-test navigation",
        "167 navigation-policy",
        "12 search-related RuntimeClientViewModelTest",
        "13 search-related RuntimeClientViewModelTest",
        "24 drawer Compose",
        "24-test drawer Compose",
        "24 navigation-drawer",
        "three previously recorded project warnings",
    )
    failures: list[str] = []

    for path, current_section_start, next_section_start in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Android drawer search "
                f"documentation: {error}"
            )
            continue

        start_count = document_text.count(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Android drawer search block must "
                f"contain exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue

        start_index = document_text.index(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START
        )
        body_start = start_index + len(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START
        )
        end_index = document_text.index(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_END
        )
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Android drawer search markers are "
                "reversed or empty."
            )
            continue
        current_section_index = document_text.find(current_section_start)
        next_section_index = document_text.find(
            next_section_start,
            max(current_section_index, 0) + len(current_section_start),
        )
        if not (
            current_section_index >= 0
            and next_section_index >= 0
            and current_section_index < start_index
            and end_index < next_section_index
        ):
            failures.append(
                f"{relative}: current Android drawer search block must remain "
                "inside its canonical current section."
            )

        block = document_text[body_start:end_index]
        normalized_block = re.sub(r"\s+", " ", block).strip()
        closed_block_remainder = normalized_block
        for claim in required_claims:
            normalized_claim = re.sub(r"\s+", " ", claim).strip()
            count = normalized_block.count(normalized_claim)
            if count != 1:
                failures.append(
                    f"{relative}: current Android drawer search block must "
                    f"contain exact claim {claim!r} once; found {count}."
                )
            else:
                closed_block_remainder = closed_block_remainder.replace(
                    normalized_claim,
                    "",
                    1,
                )
        boundary_match = re.search(
            r"This source/JVM/Compose evidence is not part of the immutable "
            r"Build 17 archive and (?:is|was) first source-bound by the "
            r"immutable Build 18 archive; (?:Build 19 retains it\. )?It does "
            r"not establish physical touch, TalkBack, provider, device, "
            r"network, installation, signing, or release behavior\.",
            normalized_block,
            re.IGNORECASE,
        )
        if boundary_match is None:
            failures.append(
                f"{relative}: current Android drawer search block is missing "
                "its Build 17/18/19 archive boundary."
            )
        else:
            closed_block_remainder = closed_block_remainder.replace(
                boundary_match.group(0),
                "",
                1,
            )

        closed_block_remainder = re.sub(
            r"-\s*(?:\[[ xX]\]\s*)?",
            " ",
            closed_block_remainder,
        ).strip()
        if closed_block_remainder:
            failures.append(
                f"{relative}: current Android drawer search block is closed "
                f"to additional claims; found {closed_block_remainder!r}."
            )

        for stale_marker in stale_current_markers:
            if stale_marker in normalized_block:
                failures.append(
                    f"{relative}: current Android drawer search block retains "
                    f"stale evidence marker {stale_marker!r}."
                )

        block_without_boundary = (
            normalized_block[: boundary_match.start()]
            + normalized_block[boundary_match.end() :]
            if boundary_match is not None
            else normalized_block
        )
        prohibited_positive_claims = (
            (
                r"\bphysical touch\b.{0,100}\b"
                r"(?:pass(?:es|ed)?|prov(?:e|es|ed|en)|"
                r"qualif(?:y|ies|ied|ication))\b"
            ),
            (
                r"\bTalkBack\b.{0,100}\b"
                r"(?:pass(?:es|ed)?|prov(?:e|es|ed|en)|"
                r"qualif(?:y|ies|ied|ication))\b"
            ),
            (
                r"\b(?:pass(?:es|ed)?|prov(?:e|es|ed|en)|"
                r"qualif(?:y|ies|ied|ication))\b.{0,100}\bTalkBack\b"
            ),
            r"\bpart of the immutable Build 17 archive\b",
            r"\bproduction[- ]ready\b",
        )
        if any(
            re.search(pattern, block_without_boundary, re.IGNORECASE)
            for pattern in prohibited_positive_claims
        ):
            failures.append(
                f"{relative}: current Android drawer search block contains "
                "a contradictory device, archive, or production claim."
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


def macos_packaged_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_PACKAGED_STATE_RECOVERY_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-13-state-recovery-v1.json"
        ),
        expected_size=MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SIZE,
        expected_sha256=(
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        expected_result=MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT,
        build_label="Build 13 state-recovery",
        result_bytes=result_bytes,
    )


def historical_build12_state_recovery_absence_failures(
    *,
    result_exists: bool | None = None,
) -> list[str]:
    exists = (
        HISTORICAL_BUILD12_STATE_RECOVERY_RESULT.exists()
        if result_exists is None
        else result_exists
    )
    if not exists:
        return []
    return [
        "dist/lifecycle/macos-packaged-app-build-12-state-recovery-v1.json: "
        "Build 12 failed closed and must not have a published state-recovery "
        "result."
    ]


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


def historical_build16_reproducibility_failures(
    *,
    document_text: str | None = None,
    result_bytes_by_path: dict[str, bytes] | None = None,
) -> list[str]:
    relative_doc = HISTORICAL_BUILD16_DOC.relative_to(ROOT)
    if document_text is None:
        if not HISTORICAL_BUILD16_DOC.is_file():
            return [f"{relative_doc}: missing Build 16 historical record."]
        try:
            document_text = HISTORICAL_BUILD16_DOC.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative_doc}: unreadable Build 16 historical record: "
                f"{error}"
            ]

    failures: list[str] = []
    required_document_claims = (
        f"{HISTORICAL_BUILD16_ARCHIVE_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_ARCHIVE_SHA256}`",
        f"{HISTORICAL_BUILD16_RESULT_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_RESULT_SHA256}`",
        f"{HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256}`",
        f"{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256}`",
        "`publication=null`",
        "Build 17 does not retroactively qualify Build 16.",
    )
    for claim in required_document_claims:
        if claim not in document_text:
            failures.append(
                f"{relative_doc}: missing exact Build 16 history claim "
                f"{claim!r}."
            )

    result_specs = (
        (
            HISTORICAL_BUILD16_RESULT,
            HISTORICAL_BUILD16_RESULT_SIZE,
            HISTORICAL_BUILD16_RESULT_SHA256,
            "passed",
        ),
        (
            HISTORICAL_BUILD16_FAILED_ATTEMPT,
            HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE,
            HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256,
            "failed",
        ),
        (
            HISTORICAL_BUILD16_FAILED_CONFIRMATION,
            HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE,
            HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256,
            "failed",
        ),
    )
    expected_failed_member_paths = [
        "macos/AetherLink.app/Contents/MacOS/AetherLink",
        "macos/AetherLink.dSYM/Contents/Resources/DWARF/AetherLink",
        "macos/AetherLink.dSYM/Contents/Resources/Relocations/aarch64/AetherLink.yml",
        "manifest.json",
    ]
    expected_failure_categories = [
        "checksum",
        "manifest",
        "member-bytes",
        "member-metadata",
        "zip",
    ]
    for path, expected_size, expected_sha256, expected_status in result_specs:
        relative = path.relative_to(ROOT)
        if result_bytes_by_path is None:
            if not path.is_file():
                failures.append(
                    f"{relative}: missing Build 16 reproducibility result."
                )
                continue
            try:
                payload = path.read_bytes()
            except OSError as error:
                failures.append(
                    f"{relative}: unreadable Build 16 result: {error}"
                )
                continue
        else:
            payload = result_bytes_by_path.get(str(relative))
            if payload is None:
                failures.append(
                    f"{relative}: missing injected Build 16 result."
                )
                continue
        try:
            result = json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except (
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJSONKeyError,
        ) as error:
            failures.append(f"{relative}: unreadable Build 16 result: {error}")
            continue
        identity = (len(payload), hashlib.sha256(payload).hexdigest())
        expected_identity = (expected_size, expected_sha256)
        if identity != expected_identity:
            failures.append(
                f"{relative}: expected identity {expected_identity!r}, "
                f"found {identity!r}."
            )
        if not isinstance(result, dict):
            failures.append(f"{relative}: result root must be an object.")
            continue
        if result.get("status") != expected_status:
            failures.append(
                f"{relative}: expected status={expected_status!r}, found "
                f"{result.get('status')!r}."
            )
        publication = result.get("publication")
        if expected_status == "passed":
            if (
                not isinstance(publication, dict)
                or publication.get("archiveSha256")
                != HISTORICAL_BUILD16_ARCHIVE_SHA256
            ):
                failures.append(
                    f"{relative}: successful Build 16 result must retain the "
                    "published archive identity."
                )
            continue
        if publication is not None:
            failures.append(
                f"{relative}: failed Build 16 result must retain publication=null."
            )
        comparison = result.get("comparison")
        if not isinstance(comparison, dict):
            failures.append(
                f"{relative}: failed Build 16 result must retain comparison."
            )
            continue
        member_differences = comparison.get("memberDifferences")
        actual_member_paths = (
            [
                item.get("path")
                for item in member_differences
                if isinstance(item, dict)
            ]
            if isinstance(member_differences, list)
            else None
        )
        if actual_member_paths != expected_failed_member_paths:
            failures.append(
                f"{relative}: expected failed member paths "
                f"{expected_failed_member_paths!r}, found "
                f"{actual_member_paths!r}."
            )
        if comparison.get("differences") != expected_failure_categories:
            failures.append(
                f"{relative}: expected failure categories "
                f"{expected_failure_categories!r}, found "
                f"{comparison.get('differences')!r}."
            )
    return failures


def historical_build17_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-17-local-v1.md"
    if document_text is None:
        path = ROOT / relative
        try:
            document_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 17 history: "
                f"{error}"
            ]

    normalized_text = re.sub(r"\s+", " ", document_text).strip()
    required_once = (
        (
            "archive directory",
            f"`dist/releases/{HISTORICAL_BUILD17_RELEASE_ID}/`",
        ),
        (
            "canonical ZIP identity",
            (
                f"| Canonical ZIP | {HISTORICAL_BUILD17_ARCHIVE_SIZE:,} bytes | "
                f"`{HISTORICAL_BUILD17_ARCHIVE_SHA256}` |"
            ),
        ),
        (
            "manifest identity",
            (
                "| External/embedded manifest | "
                f"{HISTORICAL_BUILD17_MANIFEST_SIZE:,} bytes | "
                f"`{HISTORICAL_BUILD17_MANIFEST_SHA256}` |"
            ),
        ),
        (
            "source inventory identity",
            (
                "| Source inventory | "
                f"{HISTORICAL_BUILD17_SOURCE_INVENTORY_SIZE:,} bytes | "
                f"`{HISTORICAL_BUILD17_SOURCE_INVENTORY_SHA256}` |"
            ),
        ),
        (
            "source inventory duplicate identity",
            (
                f"- `source-files.json`: "
                f"{HISTORICAL_BUILD17_SOURCE_INVENTORY_SIZE:,} bytes, "
                f"`{HISTORICAL_BUILD17_SOURCE_INVENTORY_SHA256}`."
            ),
        ),
        (
            "source snapshot identity",
            (
                f"Its {HISTORICAL_BUILD17_SOURCE_FILE_COUNT}-file source "
                "inventory has snapshot digest "
                f"`{HISTORICAL_BUILD17_SOURCE_SNAPSHOT_SHA256}`."
            ),
        ),
        (
            "primary reproducibility identity",
            (
                "The first result is "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_PATH}`. "
                f"It is {HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SIZE:,} "
                "bytes with SHA-256 "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SHA256}`."
            ),
        ),
        (
            "reproducibility confirmation identity",
            (
                "The separate confirmation result is "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_PATH}`. "
                "It is "
                f"{HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SIZE:,} "
                "bytes with SHA-256 "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SHA256}`."
            ),
        ),
    )
    failures: list[str] = []
    for label, claim in required_once:
        normalized_claim = re.sub(r"\s+", " ", claim).strip()
        count = normalized_text.count(normalized_claim)
        if count != 1:
            failures.append(
                f"{relative}: immutable Build 17 {label} must appear exactly "
                f"once; found {count}."
            )

    start_count = document_text.count(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START
    )
    end_count = document_text.count(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_END
    )
    if (start_count, end_count) != (1, 1):
        failures.append(
            f"{relative}: historical Build 17 lifecycle block must contain "
            "exactly one distinct start and end marker; found "
            f"{start_count} and {end_count}."
        )
        return failures

    start_index = document_text.index(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START
    )
    body_start = start_index + len(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START
    )
    end_index = document_text.index(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_END
    )
    if end_index <= body_start:
        failures.append(
            f"{relative}: historical Build 17 lifecycle markers are reversed "
            "or empty."
        )
        return failures

    block = document_text[body_start:end_index]
    normalized_block = re.sub(r"\s+", " ", block).strip()
    lifecycle_claims = (
        (
            "installed-app result identity",
            (
                f"`{HISTORICAL_BUILD17_INSTALLED_APP_RESULT_PATH}`, "
                f"{HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SIZE:,} bytes with "
                "SHA-256 "
                f"`{HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SHA256}`."
            ),
        ),
        (
            "state-recovery result identity",
            (
                f"`{HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_PATH}`, "
                f"{HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SIZE:,} bytes with "
                "SHA-256 "
                f"`{HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SHA256}`."
            ),
        ),
    )
    for label, claim in lifecycle_claims:
        count = normalized_block.count(claim)
        if count != 1:
            failures.append(
                f"{relative}: historical Build 17 lifecycle {label} must "
                f"appear exactly once inside its distinct block; found {count}."
            )
    if (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START in document_text
        or CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END in document_text
    ):
        failures.append(
            f"{relative}: current Build 20 lifecycle markers must not enter "
            "the immutable historical Build 17 record."
        )
    return failures


def historical_build18_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-18-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 18 history: "
                f"{error}"
            ]

    required_bindings = (
        HISTORICAL_BUILD18_RELEASE_ID,
        f"{HISTORICAL_BUILD18_ARCHIVE_SIZE:,} bytes",
        HISTORICAL_BUILD18_ARCHIVE_SHA256,
        f"{HISTORICAL_BUILD18_MANIFEST_SIZE:,} bytes",
        HISTORICAL_BUILD18_MANIFEST_SHA256,
        f"{HISTORICAL_BUILD18_CHECKSUM_SIZE:,} bytes",
        HISTORICAL_BUILD18_CHECKSUM_SHA256,
        f"{HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SHA256,
        (
            f"{HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SIZE:,} "
            "bytes"
        ),
        HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SHA256,
        f"{HISTORICAL_BUILD18_SOURCE_FILE_COUNT}-file source inventory",
        HISTORICAL_BUILD18_SOURCE_SNAPSHOT_SHA256,
        HISTORICAL_BUILD18_SOURCE_OVERLAY_SHA256,
        f"{HISTORICAL_BUILD18_SOURCE_INVENTORY_SIZE:,} bytes",
        HISTORICAL_BUILD18_SOURCE_INVENTORY_SHA256,
        HISTORICAL_BUILD18_MACOS_UUID,
        HISTORICAL_BUILD18_INSTALLED_APP_RESULT_PATH,
        HISTORICAL_BUILD18_INSTALLED_APP_RESULT_SHA256,
        HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_PATH,
        HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_SHA256,
    )
    failures = [
        f"{relative}: immutable Build 18 binding {binding!r} is missing."
        for binding in required_bindings
        if binding not in document_text
    ]
    if (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START in document_text
        or CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END in document_text
    ):
        failures.append(
            f"{relative}: current Build 20 lifecycle markers must not enter "
            "the immutable historical Build 18 record."
        )
    return failures


def historical_build19_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-19-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 19 history: "
                f"{error}"
            ]

    required_bindings = (
        "Build 19 is retained as an immutable historical qualification record.",
        "Run this historical source-bound readback with historical mode:",
        HISTORICAL_BUILD19_RELEASE_ID,
        f"{HISTORICAL_BUILD19_ARCHIVE_SIZE:,} bytes",
        HISTORICAL_BUILD19_ARCHIVE_SHA256,
        f"{HISTORICAL_BUILD19_MANIFEST_SIZE:,} bytes",
        HISTORICAL_BUILD19_MANIFEST_SHA256,
        f"{HISTORICAL_BUILD19_CHECKSUM_SIZE:,} bytes",
        HISTORICAL_BUILD19_CHECKSUM_SHA256,
        f"{HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SHA256,
        (
            f"{HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SIZE:,} "
            "bytes"
        ),
        HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SHA256,
        f"{HISTORICAL_BUILD19_SOURCE_FILE_COUNT}-file source inventory",
        HISTORICAL_BUILD19_SOURCE_SNAPSHOT_SHA256,
        HISTORICAL_BUILD19_SOURCE_OVERLAY_SHA256,
        f"{HISTORICAL_BUILD19_SOURCE_INVENTORY_SIZE:,} bytes",
        HISTORICAL_BUILD19_SOURCE_INVENTORY_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-19-clean-home-install-v1.json"
        ),
        f"{HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-19-clean-home-state-recovery-v1.json"
        ),
        f"{HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SHA256,
    )
    failures = [
        f"{relative}: immutable Build 19 binding {binding!r} is missing."
        for binding in required_bindings
        if binding not in document_text
    ]
    if (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START in document_text
        or CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END in document_text
    ):
        failures.append(
            f"{relative}: current Build 20 lifecycle markers must not enter "
            "the immutable historical Build 19 record."
        )
    for stale_claim in (
        "Run the current source-bound readback without historical mode:",
        "carries current same-host, per-user macOS installed-lifecycle",
    ):
        if stale_claim in document_text:
            failures.append(
                f"{relative}: immutable Build 19 record contains stale "
                f"current-state claim {stale_claim!r}."
            )
    return failures


def historical_build20_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-20-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 20 history: "
                f"{error}"
            ]

    helper_size, helper_sha256 = (
        HISTORICAL_BUILD20_RUNTIME_CHAT_HELPER_IDENTITY
    )
    runner_size, runner_sha256 = (
        HISTORICAL_BUILD20_RUNTIME_CHAT_RUNNER_IDENTITY
    )
    test_size, test_sha256 = HISTORICAL_BUILD20_RUNTIME_CHAT_TEST_IDENTITY
    required_bindings = (
        "Build 20 is retained as an immutable historical qualification record.",
        "Run this historical source-bound readback with historical mode:",
        HISTORICAL_BUILD20_RELEASE_ID,
        f"{HISTORICAL_BUILD20_ARCHIVE_SIZE:,} bytes",
        HISTORICAL_BUILD20_ARCHIVE_SHA256,
        f"{HISTORICAL_BUILD20_MANIFEST_SIZE:,} bytes",
        HISTORICAL_BUILD20_MANIFEST_SHA256,
        f"{HISTORICAL_BUILD20_CHECKSUM_SIZE:,} bytes",
        HISTORICAL_BUILD20_CHECKSUM_SHA256,
        f"{HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SHA256,
        (
            f"{HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SIZE:,} "
            "bytes"
        ),
        HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SHA256,
        f"{HISTORICAL_BUILD20_SOURCE_FILE_COUNT}-file source inventory",
        HISTORICAL_BUILD20_SOURCE_SNAPSHOT_SHA256,
        HISTORICAL_BUILD20_SOURCE_OVERLAY_SHA256,
        HISTORICAL_BUILD20_PREPUBLICATION_SOURCE_OVERLAY_SHA256,
        f"{HISTORICAL_BUILD20_SOURCE_INVENTORY_SIZE:,} bytes",
        HISTORICAL_BUILD20_SOURCE_INVENTORY_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-install-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-local-dmg-install-v1.json"
        ),
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256,
        f"{helper_size:,} bytes",
        helper_sha256,
        f"{runner_size:,} bytes",
        runner_sha256,
        f"{test_size:,}-byte test source",
        test_sha256,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END,
    )
    failures: list[str] = []
    document_sha256 = hashlib.sha256(
        document_text.encode("utf-8")
    ).hexdigest()
    if document_sha256 != HISTORICAL_BUILD20_RELEASE_DOCUMENT_SHA256:
        failures.append(
            f"{relative}: exact immutable document SHA-256 must remain "
            f"{HISTORICAL_BUILD20_RELEASE_DOCUMENT_SHA256}; found "
            f"{document_sha256}."
        )
    failures.extend(
        f"{relative}: immutable Build 20 binding {binding!r} is missing."
        for binding in required_bindings
        if binding not in document_text
    )
    for stale_claim in (
        "Build 20 is the current local qualification record.",
        "Run the current source-bound readback without historical mode:",
        "aetherlink-current-build20-lifecycle-v1",
    ):
        if stale_claim in document_text:
            failures.append(
                f"{relative}: immutable Build 20 record contains stale "
                f"current-state claim {stale_claim!r}."
            )
    build21_evidence_association = re.compile(
        r"\b(?:evidence|observation|lifecycle|DMG|"
        r"belong(?:s|ed)?|inherit(?:s|ed)?|"
        r"transfer(?:s|red|ring)?|relabel(?:s|ed|led)?|"
        r"reinterpret(?:s|ed)?|part of)\b",
        re.IGNORECASE,
    )
    explicit_negation = re.compile(
        r"\b(?:no|not|never|cannot|does not|do not|is not|are not)\b",
        re.IGNORECASE,
    )
    normalized_document = re.sub(r"\s+", " ", document_text).strip()
    for sentence in re.split(r"(?<=[.!?])\s+", normalized_document):
        if (
            re.search(r"\bBuild\s+21\b", sentence, re.IGNORECASE)
            and build21_evidence_association.search(sentence)
            and not explicit_negation.search(sentence)
        ):
            failures.append(
                f"{relative}: immutable Build 20 record contains an "
                "unnegated transfer or relabeling claim into Build 21."
            )
            break
    return failures


def historical_build21_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-21-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 21 history: "
                f"{error}"
            ]

    required_binding_counts = (
        (
            "Build 21 is an immutable historical local qualification record",
            1,
        ),
        (HISTORICAL_BUILD21_RELEASE_ID, 5),
        (f"{HISTORICAL_BUILD21_ARCHIVE_SIZE:,} bytes", 1),
        (f"{HISTORICAL_BUILD21_ARCHIVE_SIZE:,}-byte", 1),
        (HISTORICAL_BUILD21_ARCHIVE_SHA256, 2),
        (f"{HISTORICAL_BUILD21_MANIFEST_SIZE:,} bytes", 1),
        (f"{HISTORICAL_BUILD21_MANIFEST_SIZE:,}-byte", 1),
        (HISTORICAL_BUILD21_MANIFEST_SHA256, 1),
        (HISTORICAL_BUILD21_CHECKSUM_SHA256, 1),
        (
            "dist/reproducibility/"
            "aetherlink-1.0.0+21-local-v1-two-root-v3.json",
            1,
        ),
        (f"{HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SIZE:,} bytes", 1),
        (HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SHA256, 1),
        (
            "dist/reproducibility/"
            "aetherlink-1.0.0+21-local-v1-two-root-v3-prepublication.json",
            1,
        ),
        (
            f"{HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SIZE:,} "
            "bytes",
            1,
        ),
        (HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SHA256, 1),
        (f"{HISTORICAL_BUILD21_SOURCE_FILE_COUNT}-file source inventory", 1),
        (HISTORICAL_BUILD21_SOURCE_SNAPSHOT_SHA256, 2),
        (f"{HISTORICAL_BUILD21_SOURCE_INVENTORY_SIZE:,} bytes", 2),
        (HISTORICAL_BUILD21_SOURCE_INVENTORY_SHA256, 2),
        (HISTORICAL_BUILD21_MACOS_UUID, 1),
        (
            "dist/lifecycle/"
            "macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json",
            1,
        ),
        (CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256, 1),
    )
    failures = [
        (
            f"{relative}: immutable Build 21 binding {binding!r} must appear "
            f"exactly {expected_count} time(s); found "
            f"{document_text.count(binding)}."
        )
        for binding, expected_count in required_binding_counts
        if document_text.count(binding) != expected_count
    ]
    for stale_claim in (
        "Build 21 is the current local qualification record",
        "The Build 21 archive is the latest ledger entry",
        "Build 21 is the latest immutable ledger archive",
        "Run the current source-bound readback without historical mode",
    ):
        if stale_claim in document_text:
            failures.append(
                f"{relative}: immutable Build 21 record contains stale "
                f"current-state claim {stale_claim!r}."
            )
    return failures


def historical_local_release_document_failures(
    *,
    ledger_bytes: bytes | None = None,
    document_text_by_build: dict[int, str] | None = None,
    document_bytes_by_build: dict[int, bytes] | None = None,
) -> list[str]:
    if (
        document_text_by_build is not None
        and document_bytes_by_build is not None
    ):
        return [
            "historical release documents: inject text or bytes, not both."
        ]
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

    failures: list[str] = []
    for entry in entries[:-1]:
        relative = (
            "docs/releases/"
            f"{entry.marketing_version}-build-{entry.build_number}-local-v1.md"
        )
        if (
            document_text_by_build is None
            and document_bytes_by_build is None
        ):
            path = ROOT / relative
            if not path.is_file():
                failures.append(
                    f"{relative}: missing historical local release record."
                )
                continue
            try:
                document_bytes = path.read_bytes()
                document_text = document_bytes.decode("utf-8")
            except (OSError, UnicodeError) as error:
                failures.append(
                    f"{relative}: unreadable historical local release "
                    f"record: {error}"
                )
                continue
        elif document_bytes_by_build is not None:
            document_bytes = document_bytes_by_build.get(
                entry.build_number
            )
            if document_bytes is None:
                failures.append(
                    f"{relative}: missing injected historical release record."
                )
                continue
            try:
                document_text = document_bytes.decode("utf-8")
            except UnicodeError as error:
                failures.append(
                    f"{relative}: unreadable injected historical local "
                    f"release record: {error}"
                )
                continue
        else:
            document_text = document_text_by_build.get(entry.build_number)
            if document_text is None:
                failures.append(
                    f"{relative}: missing injected historical release record."
                )
                continue
            document_bytes = document_text.encode("utf-8")

        release_id = (
            f"aetherlink-{entry.marketing_version}"
            f"+{entry.build_number}-local-v1"
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
            fixture_command_count = document_text.count(
                LOCAL_RELEASE_FIXTURE_READBACK_COMMAND
            )
            if fixture_command_count != 2:
                failures.append(
                    f"{relative}: exact historical Build 3 readback command "
                    "must appear twice; found "
                    f"{fixture_command_count}."
                )
            if readback_targets.count(release_id) != 2:
                failures.append(
                    f"{relative}: historical archive readback target must "
                    f"include exactly two {release_id!r}; found "
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
        expected_document_sha256 = (
            HISTORICAL_RELEASE_DOCUMENT_SHA256_BY_BUILD.get(
                entry.build_number
            )
        )
        if expected_document_sha256 is not None:
            observed_document_sha256 = hashlib.sha256(
                document_bytes
            ).hexdigest()
            if observed_document_sha256 != expected_document_sha256:
                failures.append(
                    f"{relative}: exact immutable document SHA-256 must remain "
                    f"{expected_document_sha256}; found "
                    f"{observed_document_sha256}."
                )
        if entry.build_number == HISTORICAL_BUILD17_BUILD_NUMBER:
            failures.extend(
                historical_build17_release_document_failures(document_text)
            )
        if entry.build_number == 18:
            failures.extend(
                historical_build18_release_document_failures(document_text)
            )
        if entry.build_number == 19:
            failures.extend(
                historical_build19_release_document_failures(document_text)
            )
        if entry.build_number == 20:
            failures.extend(
                historical_build20_release_document_failures(document_text)
            )
        if entry.build_number == 21:
            failures.extend(
                historical_build21_release_document_failures(document_text)
            )

    return failures


def readme_current_local_release_failures(
    *,
    ledger_bytes: bytes | None = None,
    readme_text: str | None = None,
) -> list[str]:
    try:
        entries = parse_release_version_ledger(
            LOCAL_RELEASE_LEDGER.read_bytes()
            if ledger_bytes is None
            else ledger_bytes
        )
    except (OSError, LedgerError) as error:
        return [
            "release/version-ledger.tsv: cannot validate README current "
            f"release lineage: {error}"
        ]
    try:
        document_text = (
            README_PATH.read_text(encoding="utf-8")
            if readme_text is None
            else readme_text
        )
    except (OSError, UnicodeError) as error:
        return [f"README.md: unreadable current release guidance: {error}"]

    current = entries[-1]
    current_release_id = (
        f"aetherlink-{current.marketing_version}"
        f"+{current.build_number}-local-v1"
    )
    current_doc = (
        "docs/releases/"
        f"{current.marketing_version}-build-"
        f"{current.build_number}-local-v1.md"
    )
    failures: list[str] = []

    ledger_claims = re.findall(
        r"`release/version-ledger\.tsv`; its current entry is marketing "
        r"version `([^`]+)`\s+and shared build number `([1-9][0-9]*)`\.",
        document_text,
    )
    expected_ledger_claim = [
        (current.marketing_version, str(current.build_number))
    ]
    if ledger_claims != expected_ledger_claim:
        failures.append(
            "README.md: current ledger claim must appear exactly once as "
            f"{expected_ledger_claim[0]!r}; found {ledger_claims!r}."
        )

    output_claims = re.findall(
        r"The current output is\s+"
        r"`dist/releases/(aetherlink-[^`/]+)/`\.",
        document_text,
    )
    if output_claims != [current_release_id]:
        failures.append(
            "README.md: current output must appear exactly once as "
            f"{current_release_id!r}; found {output_claims!r}."
        )

    qualification_claims = [
        int(value)
        for value in re.findall(
            r"\bThe Build ([1-9][0-9]*) qualification runner created "
            r"two isolated lane worktrees\b",
            document_text,
        )
    ]
    if qualification_claims != [current.build_number]:
        failures.append(
            "README.md: current qualification runner must name build "
            f"{current.build_number} exactly once; found "
            f"{qualification_claims!r}."
        )

    current_record_claims = re.findall(
        r"\[[^\]\n]*build ([1-9][0-9]*) local qualification record\]"
        r"\((docs/releases/[0-9]+\.[0-9]+\.[0-9]+-build-"
        r"[1-9][0-9]*-local-v1\.md)\)\s+defines the current release notes",
        document_text,
    )
    expected_record_claim = [(str(current.build_number), current_doc)]
    if current_record_claims != expected_record_claim:
        failures.append(
            "README.md: current release-record guidance must appear exactly "
            f"once as {expected_record_claim[0]!r}; found "
            f"{current_record_claims!r}."
        )

    historical_range_claims = [
        int(value)
        for value in re.findall(
            r"\bImmutable Builds 1 through ([1-9][0-9]*) remain "
            r"available for historical\s+readback\b",
            document_text,
        )
    ]
    expected_historical_upper = current.build_number - 1
    if historical_range_claims != [expected_historical_upper]:
        failures.append(
            "README.md: historical release range must end at build "
            f"{expected_historical_upper} exactly once; found "
            f"{historical_range_claims!r}."
        )

    current_section_start_markers = [
        match.start()
        for match in re.finditer(
            r"^The current output is$",
            document_text,
            re.MULTILINE,
        )
    ]
    current_section_end_markers = [
        match.start()
        for match in re.finditer(
            r"^Refresh public POM evidence only as an explicit maintenance "
            r"action with$",
            document_text,
            re.MULTILINE,
        )
    ]
    if (
        len(current_section_start_markers) != 1
        or len(current_section_end_markers) != 1
        or current_section_end_markers[0] <= current_section_start_markers[0]
    ):
        failures.append(
            "README.md: current local-release evidence section must have "
            "exactly one ordered output and compliance boundary."
        )
        current_section = ""
    else:
        current_section = document_text[
            current_section_start_markers[0]:
            current_section_end_markers[0]
        ]

    result_claims = re.findall(
        r"`dist/reproducibility/"
        rf"(aetherlink-[^`/]+-two-root-v"
        rf"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}\.json)`",
        current_section,
    )
    expected_result_claim = [
        f"{current_release_id}-two-root-v"
        f"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}.json"
    ]
    if result_claims != expected_result_claim:
        failures.append(
            "README.md: current reproducibility result must appear exactly "
            f"once as {expected_result_claim[0]!r}; found {result_claims!r}."
        )

    prepublication_claims = re.findall(
        r"`dist/reproducibility/"
        rf"(aetherlink-[^`/]+-two-root-v"
        rf"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}"
        r"-prepublication\.json)`",
        current_section,
    )
    expected_prepublication_claim = [
        f"{current_release_id}-two-root-v"
        f"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}-prepublication.json"
    ]
    if prepublication_claims != expected_prepublication_claim:
        failures.append(
            "README.md: current reproducibility prepublication must appear "
            f"exactly once as {expected_prepublication_claim[0]!r}; found "
            f"{prepublication_claims!r}."
        )

    compliance_claims = [
        int(value)
        for value in re.findall(
            r"\bBuild ([1-9][0-9]*) preserves compliance profile\b",
            current_section,
        )
    ]
    if compliance_claims != [current.build_number]:
        failures.append(
            "README.md: current compliance profile must name build "
            f"{current.build_number} exactly once; found "
            f"{compliance_claims!r}."
        )
    return failures


def ollama_multilingual_full_matrix_v3_evidence_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    try:
        if __package__:
            from script import (
                run_ollama_multilingual_semantic_matrix_v3 as runner,
            )
        else:
            import run_ollama_multilingual_semantic_matrix_v3 as runner

        result = runner.recorded_result()
        data = OLLAMA_MULTILINGUAL_FULL_MATRIX_V3_RESULT.read_bytes()
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        return [
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            f"recorded V3 result was invalid: {error}"
        ]

    failures: list[str] = []
    if result.get("qualityGatePassed") is not False:
        failures.append(
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            "the recorded product-quality gate must remain false."
        )
    versions = result["versions"]
    summaries = [
        runner.projection_summary(version["observation"])
        for version in versions
    ]
    ranking_passed_values = {
        summary["rankingComparisonsPassed"]
        for summary in summaries
    }
    repeatability_passed_values = {
        summary["repeatabilityComparisonsPassed"]
        for summary in summaries
    }
    coordinate_sets = {
        tuple(
            (
                row["locale"],
                row["scenarioOrdinalWithinLocale"],
            )
            for row in version["observation"]["rankingFailures"]
        )
        for version in versions
    }
    if (
        len(ranking_passed_values) != 1
        or len(repeatability_passed_values) != 1
        or len(coordinate_sets) != 1
    ):
        failures.append(
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            "exact candidates must share one documentable comparison summary "
            "and ranking-failure coordinate set."
        )
        return failures
    ranking_passed = next(iter(ranking_passed_values))
    repeatability_passed = next(iter(repeatability_passed_values))
    ranking_total = runner.RANKING_COMPARISON_COUNT
    repeatability_total = runner.REPEATABILITY_COMPARISON_COUNT
    failure_coordinates = next(iter(coordinate_sets))
    locale_labels = {
        "en": "English",
        "ko": "Korean",
        "ja": "Japanese",
        "zh-CN": "Simplified Chinese",
        "fr": "French",
    }
    if any(locale not in locale_labels for locale, _ in failure_coordinates):
        failures.append(
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            "ranking-failure locale lacks a documentation label."
        )
        return failures
    recoveries_passed = all(
        version["recoveryPassed"] is True
        for version in versions
    )
    relative = (
        "docs/evidence/"
        "ollama-embedding-multilingual-full-matrix-v3.json"
    )
    raw_sha256 = hashlib.sha256(data).hexdigest()
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
    )
    for path in documentation_targets:
        relative_path = str(path.relative_to(ROOT))
        try:
            text = (
                document_text_by_relative[relative_path]
                if (
                    document_text_by_relative is not None
                    and relative_path in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative_path}: cannot validate V3 evidence "
                f"guidance: {error}"
            )
            continue
        missing = [
            value
            for value in (relative, raw_sha256)
            if value not in text
        ]
        if missing:
            failures.append(
                f"{relative_path}: missing recorded V3 evidence "
                f"binding(s) {missing!r}."
            )
            continue

        anchor = text.index(raw_sha256)
        claim_window = re.sub(
            r"\s+",
            " ",
            text[max(0, anchor - 700):anchor + 700],
        )
        if not re.search(
            rf"\b{ranking_passed}(?:/| of ){ranking_total} "
            r"ranking\b",
            claim_window,
            re.IGNORECASE,
        ):
            failures.append(
                f"{relative_path}: V3 claim must report exactly "
                f"{ranking_passed}/{ranking_total} ranking comparisons."
            )
        if not re.search(
            rf"(?:\b{repeatability_passed}/"
            rf"{repeatability_total}\b|\ball "
            rf"{repeatability_passed}\b) repeatability\b",
            claim_window,
            re.IGNORECASE,
        ):
            failures.append(
                f"{relative_path}: V3 claim must report exactly "
                f"{repeatability_passed}/{repeatability_total} "
                "repeatability comparisons."
            )
        for locale, ordinal in failure_coordinates:
            label = locale_labels[locale]
            optional_shared_locale = (
                r"(?:\s+and\s+French)?"
                if locale == "ko" and ("fr", ordinal) in failure_coordinates
                else ""
            )
            if not re.search(
                rf"\b{re.escape(label)}\b"
                rf"{optional_shared_locale}\s+scenario ordinal {ordinal}\b",
                claim_window,
                re.IGNORECASE,
            ):
                failures.append(
                    f"{relative_path}: V3 claim must report the "
                    f"{label} scenario ordinal {ordinal} ranking failure."
                )
        recovery_pass_pattern = (
            r"(?:\bboth pass fresh-provider recover(?:y|ies)\b|"
            r"\bboth fresh-provider recover(?:y|ies)"
            r"(?: phases)? pass\b)"
        )
        if recoveries_passed and not re.search(
            recovery_pass_pattern,
            claim_window,
            re.IGNORECASE,
        ):
            failures.append(
                f"{relative_path}: V3 claim must report that both "
                "fresh-provider recoveries pass."
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


TRACKED_CONTRACTS_ONLY_ARGUMENT = "--tracked-contracts-only"


def base_document_contract_failures() -> list[str]:
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

    return failures


def current_build24_reverse_version_readback_tracked_source_failures() -> list[str]:
    expected_sources = (
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SHA256,
            "runner",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER_TEST,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SHA256,
            "runner test",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SHA256,
            "checker",
        ),
        (
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER_TEST,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SIZE,
            CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SHA256,
            "checker test",
        ),
    )
    failures: list[str] = []
    for source_path, expected_size, expected_sha256, label in expected_sources:
        relative = str(source_path.relative_to(ROOT))
        try:
            if source_path.is_symlink() or not source_path.is_file():
                raise OSError("path must be a non-symlink regular file")
            payload = source_path.read_bytes()
        except OSError as error:
            failures.append(
                f"{relative}: cannot read tracked reverse-version {label}: "
                f"{error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if len(payload) != expected_size or actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected tracked reverse-version {label} "
                f"identity {expected_size} bytes and SHA-256 "
                f"{expected_sha256}; found {len(payload)} bytes and "
                f"{actual_sha256}."
            )
    return failures


def tracked_document_contract_failures() -> list[str]:
    tracked_failures = base_document_contract_failures()
    tracked_failures.extend(latest_progress_evidence_failures())
    tracked_failures.extend(latest_qa_evidence_failures())
    tracked_failures.extend(current_release_qa_evidence_failures())
    tracked_failures.extend(current_release_summary_document_failures())
    tracked_failures.extend(release_readback_command_mode_failures())
    tracked_failures.extend(syntax_only_no_device_gate_evidence_failures())
    tracked_failures.extend(current_handoff_git_attribution_failures())
    tracked_failures.extend(current_source_g6_lane_a_local_dmg_document_failures())
    tracked_failures.extend(macos_clean_home_installed_app_source_failures())
    tracked_failures.extend(
        macos_clean_home_installed_state_recovery_source_failures()
    )
    tracked_failures.extend(macos_packaged_lifecycle_source_failures())
    tracked_failures.extend(macos_packaged_state_recovery_source_failures())
    tracked_failures.extend(current_macos_isolated_upgrade_document_failures())
    tracked_failures.extend(
        current_runtime_chat_sqlite_cross_process_document_failures()
    )
    tracked_failures.extend(
        current_runtime_chat_sqlite_abrupt_recovery_document_failures()
    )
    tracked_failures.extend(current_runtime_chat_sqlite_source_failures())
    tracked_failures.extend(current_macos_clean_home_lifecycle_document_failures())
    tracked_failures.extend(
        current_build24_macos_clean_home_lifecycle_document_failures()
    )
    tracked_failures.extend(
        current_build24_macos_local_dmg_lifecycle_document_failures()
    )
    tracked_failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_document_failures()
    )
    tracked_failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_document_failures()
    )
    tracked_failures.extend(
        current_build24_macos_local_dmg_abrupt_process_state_recovery_document_failures()
    )
    tracked_failures.extend(
        current_build24_macos_lifecycle_aggregate_document_failures()
    )
    tracked_failures.extend(
        current_build24_reverse_version_readback_tracked_source_failures()
    )
    tracked_failures.extend(
        current_build24_reverse_version_readback_document_failures()
    )
    tracked_failures.extend(
        current_build24_macos_idle_resource_stability_document_failures()
    )
    tracked_failures.extend(
        current_build24_macos_local_dmg_default_gate_failures()
    )
    tracked_failures.extend(current_android_drawer_search_document_failures())
    tracked_failures.extend(historical_local_release_document_failures())
    tracked_failures.extend(readme_current_local_release_failures())
    tracked_failures.extend(ollama_multilingual_full_matrix_v3_evidence_failures())
    tracked_failures.extend(physical_qr_observation_manifest_failures())
    return tracked_failures


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == [TRACKED_CONTRACTS_ONLY_ARGUMENT]:
        tracked_failures = tracked_document_contract_failures()
        if tracked_failures:
            print("Tracked docs contract check failed:", file=sys.stderr)
            for failure in tracked_failures:
                print(f" - {failure}", file=sys.stderr)
            return 1
        print(
            "Tracked docs contracts OK across "
            f"{len(target_files())} current documentation file(s); "
            "ignored dist evidence bytes were not read."
        )
        return 0
    if arguments:
        print(
            "usage: check_docs_hygiene.py [--tracked-contracts-only]",
            file=sys.stderr,
        )
        return 2

    failures = base_document_contract_failures()

    failures.extend(latest_progress_evidence_failures())
    failures.extend(latest_qa_evidence_failures())
    failures.extend(current_release_qa_evidence_failures())
    failures.extend(current_release_summary_document_failures())
    failures.extend(release_readback_command_mode_failures())
    failures.extend(syntax_only_no_device_gate_evidence_failures())
    failures.extend(current_handoff_git_attribution_failures())
    failures.extend(local_release_document_failures())
    failures.extend(current_source_g6_reproducibility_failures())
    failures.extend(current_source_g6_swift_root_diagnostic_failures())
    failures.extend(current_source_g6_lifecycle_two_evidence_failures())
    failures.extend(
        current_source_g6_lane_a_local_dmg_evidence_failures()
    )
    failures.extend(
        current_source_g6_lane_a_local_dmg_document_failures()
    )
    failures.extend(macos_clean_home_installed_app_source_failures())
    failures.extend(
        macos_clean_home_installed_state_recovery_source_failures()
    )
    failures.extend(macos_packaged_lifecycle_source_failures())
    failures.extend(macos_packaged_state_recovery_source_failures())
    failures.extend(
        current_macos_clean_home_installed_app_evidence_failures()
    )
    failures.extend(
        current_macos_clean_home_installed_state_recovery_evidence_failures()
    )
    failures.extend(
        current_build24_macos_clean_home_installed_app_evidence_failures()
    )
    failures.extend(
        current_build24_macos_clean_home_installed_state_recovery_evidence_failures()
    )
    failures.extend(current_macos_local_dmg_install_evidence_failures())
    failures.extend(
        current_build24_macos_local_dmg_install_evidence_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_evidence_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_evidence_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_abrupt_process_state_recovery_evidence_failures()
    )
    failures.extend(
        current_build24_macos_lifecycle_aggregate_evidence_failures()
    )
    failures.extend(
        current_build24_reverse_version_readback_source_failures()
    )
    failures.extend(
        current_build24_macos_idle_resource_stability_evidence_failures()
    )
    failures.extend(current_macos_isolated_upgrade_evidence_failures())
    failures.extend(current_macos_isolated_upgrade_document_failures())
    failures.extend(
        current_runtime_chat_sqlite_cross_process_document_failures()
    )
    failures.extend(
        current_runtime_chat_sqlite_abrupt_recovery_document_failures()
    )
    failures.extend(current_runtime_chat_sqlite_source_failures())
    failures.extend(
        current_runtime_chat_sqlite_abrupt_recovery_evidence_failures()
    )
    failures.extend(current_macos_clean_home_lifecycle_document_failures())
    failures.extend(
        current_build24_macos_clean_home_lifecycle_document_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_lifecycle_document_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_document_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_document_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_abrupt_process_state_recovery_document_failures()
    )
    failures.extend(
        current_build24_macos_lifecycle_aggregate_document_failures()
    )
    failures.extend(
        current_build24_reverse_version_readback_document_failures()
    )
    failures.extend(
        current_build24_macos_idle_resource_stability_document_failures()
    )
    failures.extend(
        current_build24_macos_local_dmg_default_gate_failures()
    )
    failures.extend(current_android_drawer_search_document_failures())
    failures.extend(macos_clean_home_installed_app_evidence_failures())
    failures.extend(
        macos_clean_home_installed_state_recovery_evidence_failures()
    )
    failures.extend(macos_packaged_lifecycle_evidence_failures())
    failures.extend(
        historical_macos_packaged_lifecycle_evidence_failures()
    )
    failures.extend(macos_packaged_state_recovery_evidence_failures())
    failures.extend(
        historical_build12_state_recovery_absence_failures()
    )
    failures.extend(historical_build16_reproducibility_failures())
    failures.extend(historical_local_release_document_failures())
    failures.extend(readme_current_local_release_failures())
    failures.extend(ollama_multilingual_full_matrix_v3_evidence_failures())
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
