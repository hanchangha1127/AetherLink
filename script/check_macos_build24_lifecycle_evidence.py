#!/usr/bin/env python3
"""Read back the bounded non-security macOS Build 24 lifecycle evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
from typing import Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
MAXIMUM_JSON_BYTES = 4 * 1024 * 1024
MAXIMUM_SOURCE_BYTES = 4 * 1024 * 1024
MAXIMUM_ARCHIVE_BYTES = 512 * 1024 * 1024
SHA256_PATTERN_LENGTH = 64


class LifecycleEvidenceError(RuntimeError):
    """Raised when retained lifecycle evidence differs from its contract."""


@dataclass(frozen=True)
class ByteIdentity:
    size: int
    sha256: str


@dataclass(frozen=True)
class ReleaseContract:
    build_number: int
    release_id: str
    ledger: ByteIdentity
    archive: ByteIdentity
    manifest: ByteIdentity
    checksum: ByteIdentity
    executable: ByteIdentity
    executable_uuid: str


@dataclass(frozen=True)
class EvidenceContract:
    relative_path: str
    identity: ByteIdentity
    schema_version: int
    scope: str
    top_level_keys: tuple[str, ...]
    limitations: tuple[str, ...]
    kind: str
    release_build: int | None = None
    canonical_result_path: str | None = None


def identity(size: int, sha256: str) -> ByteIdentity:
    if type(size) is not int or size < 0:
        raise ValueError("byte identity size must be a non-negative exact integer")
    if (
        type(sha256) is not str
        or len(sha256) != SHA256_PATTERN_LENGTH
        or any(character not in "0123456789abcdef" for character in sha256)
    ):
        raise ValueError("byte identity SHA-256 must be lowercase hexadecimal")
    return ByteIdentity(size=size, sha256=sha256)


LEDGER_RELATIVE_PATH = "release/version-ledger.tsv"
LEDGER_IDENTITY = identity(
    238,
    "dce3c8615a44c11c7b1cdb505bed1d80d6ea7bdb082c9b714bc9c2ff930d19e0",
)
MARKETING_VERSION = "1.0.0"
BUNDLE_IDENTIFIER = "dev.aetherlink.companion"
APP_TREE = {
    "digestAlgorithm": "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1",
    "regularFileCount": 10,
    "sha256": "0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff",
    "totalRegularFileBytes": 21_151_910,
}

RELEASES = {
    23: ReleaseContract(
        build_number=23,
        release_id="aetherlink-1.0.0+23-local-v1",
        ledger=identity(
            229,
            "76400cc8b28e34332f5420359d4799ea92fca7c2ca3bc2ce6b110308200ba1b3",
        ),
        archive=identity(
            166_859_521,
            "b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e",
        ),
        manifest=identity(
            15_200,
            "a645819bb0dd985b94289a29cc26b6a344361139ab6ca20a2b7aff9af0a8a16d",
        ),
        checksum=identity(
            99,
            "10048a3199b2420140d72b21145ea5bf41d2b564a39842ee2aef2a8d8b12f3d2",
        ),
        executable=identity(
            18_593_472,
            "346d0a673ba7710b5692dd2fc2dd8543e937b65deae77ad8c281071e107ab55c",
        ),
        executable_uuid="73F610E8-4BBE-3C8D-B28E-434426EAD95B",
    ),
    24: ReleaseContract(
        build_number=24,
        release_id="aetherlink-1.0.0+24-local-v1",
        ledger=LEDGER_IDENTITY,
        archive=identity(
            166_345_274,
            "104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c",
        ),
        manifest=identity(
            15_200,
            "eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b",
        ),
        checksum=identity(
            99,
            "827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882",
        ),
        executable=identity(
            18_592_368,
            "5bf283a6dd3504682cb4aefc9cb1536c7e340f776c90de83cea5a473044890e5",
        ),
        executable_uuid="3FDC3DBC-3A74-3A3B-A87D-03CB432B5D46",
    ),
}

REPOSITORY_SNAPSHOT_DIRECTORIES = (
    "release",
    "script",
    "docs",
    "docs/evidence",
    "docs/evidence/macos-build24-lifecycle-source-v1",
    "docs/evidence/macos-build24-lifecycle-source-v1/script",
    "dist",
    "dist/lifecycle",
    "dist/releases",
    "dist/releases/aetherlink-1.0.0+23-local-v1",
    "dist/releases/aetherlink-1.0.0+24-local-v1",
)

UPGRADE_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json"
)
UPGRADE_RECEIPT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-23-to-24-isolated-upgrade-repeatability-v1.json"
)
ABRUPT_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
    "abrupt-process-state-recovery-v1.json"
)
ABRUPT_RECEIPT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
    "abrupt-process-state-recovery-repeatability-v1.json"
)

EVIDENCE_CONTRACTS = (
    EvidenceContract(
        relative_path=UPGRADE_RESULT_PATH,
        identity=identity(
            6_469,
            "ddec23cf048fa77c559ca7ee4f45354feb558f830ca4b01eccffa5b7786ea09c",
        ),
        schema_version=2,
        scope="same-host-per-user-isolated-build-to-build-upgrade-v2",
        top_level_keys=(
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
        ),
        limitations=(
            "same-host-per-user-temporary-home-only",
            "build-to-build-upgrade-not-rollback",
            "application-support-retained-no-automatic-data-cleanup",
            "post-archive-harness-not-build-input-member",
            "not-clean-machine-device-provider-network-ui-or-distribution-evidence",
            "not-production-release-qualification",
        ),
        kind="upgrade-result",
    ),
    EvidenceContract(
        relative_path=UPGRADE_RECEIPT_PATH,
        identity=identity(
            898,
            "886284149745c6fdd74625fab5d97c21ad35cd9b69cc2ade4353194b4ecd1733",
        ),
        schema_version=1,
        scope=(
            "same-host-per-user-isolated-build-to-build-upgrade-"
            "repeatability-v1"
        ),
        top_level_keys=(
            "canonicalResult",
            "limitations",
            "releaseTransition",
            "resultBytesEqual",
            "runCount",
            "runs",
            "schemaVersion",
            "scope",
            "status",
        ),
        limitations=(
            "same-host-repeatability-only",
            "two-recorded-runs-not-arbitrary-repeatability",
            "not-cross-host-clean-machine-or-signed-distribution-evidence",
            "not-rollback-device-provider-network-or-production-evidence",
        ),
        kind="repeatability-receipt",
        canonical_result_path=UPGRADE_RESULT_PATH,
    ),
    EvidenceContract(
        relative_path=(
            "dist/lifecycle/"
            "macos-packaged-app-build-24-clean-home-install-v1.json"
        ),
        identity=identity(
            2_250,
            "8646ff16bb5a152aab9c874c73a048a684d02e06fb3cbf7ed2f6172de51ff0c1",
        ),
        schema_version=1,
        scope="same-host-per-user-clean-home-launchservices-rehearsal-v1",
        top_level_keys=(
            "app",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "release",
            "schemaVersion",
            "scope",
            "state",
            "status",
        ),
        limitations=(
            "same-host-per-user-rehearsal-only",
            "not-a-clean-machine-or-dmg-installation",
            "not-developer-id-notarization-or-signed-distribution",
            "not-physical-device-or-live-provider-evidence",
        ),
        kind="build-result",
        release_build=24,
    ),
    EvidenceContract(
        relative_path=(
            "dist/lifecycle/"
            "macos-packaged-app-build-24-clean-home-state-recovery-v1.json"
        ),
        identity=identity(
            3_364,
            "d3205d662967d90d65baac6e5edc57bcc19c5f17c3963a1a3e53c95b07d44588",
        ),
        schema_version=1,
        scope=(
            "same-host-per-user-clean-home-launchservices-"
            "state-recovery-v1"
        ),
        top_level_keys=(
            "app",
            "canary",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "release",
            "schemaVersion",
            "scope",
            "stateRecovery",
            "status",
        ),
        limitations=(
            "same-host-per-user-rehearsal-only",
            "not-a-clean-machine-account-or-dmg-installation",
            "not-ui-accessibility-or-live-provider-evidence",
            "not-physical-device-or-signed-distribution-evidence",
        ),
        kind="build-result",
        release_build=24,
    ),
    EvidenceContract(
        relative_path=(
            "dist/lifecycle/"
            "macos-packaged-app-build-24-local-dmg-install-v2.json"
        ),
        identity=identity(
            3_038,
            "7d4c6ae7d892bc9d639cc8dfbe5dfb02e09ff7019ee8554f652556ba7b1bb964",
        ),
        schema_version=2,
        scope="same-host-per-user-ephemeral-local-dmg-install-v2",
        top_level_keys=(
            "archiveReadback",
            "image",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "mount",
            "release",
            "schemaVersion",
            "scope",
            "state",
            "status",
        ),
        limitations=(
            "not-finder-ui-or-drag-and-drop-evidence",
            "not-general-ui-or-accessibility-evidence",
            "not-developer-id-notarized-or-stapled-distribution",
            "not-gatekeeper-quarantine-or-download-evidence",
            "not-clean-machine-account-or-system-applications",
            "not-tcc-keychain-provider-network-or-device-evidence",
            "not-arbitrary-history-crash-power-loss-or-concurrent-writer-evidence",
            "not-backup-restore-or-device-transfer-evidence",
            "not-upgrade-n-or-n-minus-one-rollback-production-or-security-evidence",
        ),
        kind="build-result",
        release_build=24,
    ),
    EvidenceContract(
        relative_path=(
            "dist/lifecycle/"
            "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-v1.json"
        ),
        identity=identity(
            3_485,
            "1e0daba4015ae36c8d96f11c424eb08a02855d3caa2e27b7838229cd55af5649",
        ),
        schema_version=1,
        scope=(
            "same-host-per-user-ephemeral-local-dmg-"
            "uninstall-reinstall-v1"
        ),
        top_level_keys=(
            "archiveReadback",
            "image",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "mount",
            "release",
            "schemaVersion",
            "scope",
            "state",
            "status",
            "uninstall",
        ),
        limitations=(
            "same-host-per-user-temporary-home-only",
            "same-created-dmg-image-remount-only",
            "application-support-retained-no-automatic-data-cleanup",
            "post-archive-harness-not-build-input-member",
            "not-finder-system-applications-quarantine-or-gatekeeper-evidence",
            "not-signed-notarized-stapled-or-distribution-evidence",
            (
                "not-clean-machine-upgrade-rollback-device-provider-network-"
                "ui-accessibility-production-or-security-evidence"
            ),
        ),
        kind="build-result",
        release_build=24,
    ),
    EvidenceContract(
        relative_path=(
            "dist/lifecycle/"
            "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
            "state-recovery-v1.json"
        ),
        identity=identity(
            4_996,
            "e3c030df6cb83586f7401de2162ac8aa14cb44fbb7c7ca05b3305d9bb4edf17e",
        ),
        schema_version=1,
        scope=(
            "same-host-per-user-ephemeral-local-dmg-"
            "uninstall-reinstall-state-recovery-v1"
        ),
        top_level_keys=(
            "archiveReadback",
            "canary",
            "image",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "mount",
            "release",
            "schemaVersion",
            "scope",
            "stateRecovery",
            "status",
            "uninstall",
        ),
        limitations=(
            "same-host-per-user-temporary-home-only",
            "same-created-dmg-image-remount-only",
            "fixed-runtime-chat-legacy-canary-only",
            "legacy-fixture-removed-by-harness-before-reinstall-readback",
            "application-support-retained-no-automatic-data-cleanup",
            "post-archive-harness-not-build-input-member",
            "not-finder-system-applications-quarantine-or-gatekeeper-evidence",
            "not-signed-notarized-stapled-or-distribution-evidence",
            (
                "not-clean-machine-upgrade-rollback-device-provider-network-"
                "ui-accessibility-production-or-security-evidence"
            ),
        ),
        kind="build-result",
        release_build=24,
    ),
    EvidenceContract(
        relative_path=ABRUPT_RESULT_PATH,
        identity=identity(
            7_200,
            "0a7879ecea014123258a14d7f6f3790b7dc5859000941bf8faf76d2b12cb5124",
        ),
        schema_version=1,
        scope=(
            "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
            "abrupt-process-state-recovery-v1"
        ),
        top_level_keys=(
            "abruptTermination",
            "archiveReadback",
            "canary",
            "image",
            "installation",
            "isolation",
            "launches",
            "limitations",
            "mount",
            "release",
            "schemaVersion",
            "scope",
            "stateRecovery",
            "status",
            "uninstall",
        ),
        limitations=(
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
                "not-finder-system-applications-quarantine-gatekeeper-"
                "signing-notarization-or-stapling-evidence"
            ),
            (
                "not-upgrade-rollback-device-provider-network-ui-"
                "accessibility-production-or-security-evidence"
            ),
        ),
        kind="build-result",
        release_build=24,
    ),
    EvidenceContract(
        relative_path=ABRUPT_RECEIPT_PATH,
        identity=identity(
            921,
            "98ec53d1018b0bebf88174a2fad514492b6ca1cff2afa1a6051e7335fabb3a36",
        ),
        schema_version=1,
        scope=(
            "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
            "abrupt-process-state-recovery-repeatability-v1"
        ),
        top_level_keys=(
            "canonicalResult",
            "limitations",
            "releaseId",
            "resultBytesEqual",
            "runCount",
            "runs",
            "schemaVersion",
            "scope",
            "status",
        ),
        limitations=(
            "same-host-two-recorded-runs-only",
            "not-arbitrary-repeatability-or-long-soak-evidence",
            (
                "not-in-flight-write-power-loss-kernel-crash-clean-machine-"
                "signed-distribution-device-network-or-production-evidence"
            ),
        ),
        kind="repeatability-receipt",
        canonical_result_path=ABRUPT_RESULT_PATH,
    ),
)

SOURCE_CONTRACTS = {
    LEDGER_RELATIVE_PATH: LEDGER_IDENTITY,
    "script/check_release_version_ledger.py": identity(
        13_996,
        "b869bb300161937b66ae775d6e742decf6d208db097408d96ffef3d34a4f78f2",
    ),
    "script/test_release_version_ledger.py": identity(
        4_688,
        "1a624072668f94c604a82cd3b0d901b194ac801f019df84ada8324915619dbe5",
    ),
    "script/run_macos_packaged_app_lifecycle_smoke.py": identity(
        39_857,
        "3d7ae7ac5b29236babb239769e7e76f6e51b2fc054accb7d53bd88509aa6ee12",
    ),
    "script/test_run_macos_packaged_app_lifecycle_smoke.py": identity(
        28_454,
        "4b01ac0161969077b027d44aad9f4f838caa1c14d1f807020ef5bca98d9de138",
    ),
    "script/run_macos_packaged_app_state_recovery_smoke.py": identity(
        26_782,
        "4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca",
    ),
    "script/test_run_macos_packaged_app_state_recovery_smoke.py": identity(
        15_881,
        "d40d3dac44606f2a1e17a44de5564894f68036a0ba0cf7778fba5574306de5db",
    ),
    "script/run_macos_clean_home_installed_app_smoke.py": identity(
        35_114,
        "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29",
    ),
    "script/test_run_macos_clean_home_installed_app_smoke.py": identity(
        15_190,
        "55274ad4abc958d85c4df1193cfe1508d820768fbbe48eae71a4fee8c1c020aa",
    ),
    "script/run_macos_clean_home_installed_state_recovery_smoke.py": identity(
        26_367,
        "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a",
    ),
    "script/test_run_macos_clean_home_installed_state_recovery_smoke.py": identity(
        18_304,
        "edfd6f89b2cecd6de5cbfcb337ba6f5643a8d74d7caf8735c467578488970664",
    ),
    "script/run_macos_isolated_uninstall_reinstall_smoke.py": identity(
        18_890,
        "36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa",
    ),
    "script/test_run_macos_isolated_uninstall_reinstall_smoke.py": identity(
        12_718,
        "ad4472a82ad7178e56f3fcb80fce4e80db1015dc845c5469e2b6832432b2b3bf",
    ),
    "script/run_macos_isolated_upgrade_smoke.py": identity(
        46_668,
        "abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095",
    ),
    "script/test_run_macos_isolated_upgrade_smoke.py": identity(
        30_777,
        "fac7fb5474ae41d00374b577966d75caf3addf45de2243fe64a322cdad80632f",
    ),
    "script/run_macos_local_dmg_install_smoke.py": identity(
        32_324,
        "e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb",
    ),
    "script/test_run_macos_local_dmg_install_smoke.py": identity(
        61_144,
        "89e566ff26d22eced043ffa108f8719274f9608685d6ecd18e579291c021cf47",
    ),
    "script/run_macos_local_dmg_install_smoke_v2.py": identity(
        12_962,
        "515de26546ba97c6879cad1fdf62cda6f3dcbf24a668804955f95e1755d1f374",
    ),
    "script/test_run_macos_local_dmg_install_smoke_v2.py": identity(
        20_191,
        "6aa2e9e2354aa36f97ff096787ac05115c95114fcf95869463b47f39dea5006c",
    ),
    "script/run_macos_local_dmg_uninstall_reinstall_smoke.py": identity(
        25_675,
        "300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae",
    ),
    "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py": identity(
        34_767,
        "6e782fc128aad75b20f1b04752e4754ccbf8ceaadc9e2fcabe9cc2e537bfb703",
    ),
    "script/run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py": (
        identity(
            28_693,
            "31bdae72f08f1f68bc4a07cb59d194c943d56179acf0a7b149ddc2e652c68b4c",
        )
    ),
    (
        "script/test_run_macos_local_dmg_uninstall_reinstall_"
        "state_recovery_smoke.py"
    ): identity(
        34_310,
        "22ddc7ec39aa8c88c2b69f2dd8a390a287d85eeaff4704109784e221483faee2",
    ),
    (
        "script/run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ): identity(
        48_788,
        "ddd2c8286d1b78541d4ed18f125b9d1867be718e0276adb9880e60929fc15ec3",
    ),
    (
        "script/test_run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ): identity(
        50_750,
        "f06479f5eb4e12d3f0072e8259e9a7b1c28e8797a423ea88b092978a4142b658",
    ),
}

# Build 24 lifecycle evidence was exercised with the source bytes at this
# commit. The runner and unit-test files that later evolved now retain their
# evidence-era bytes under a versioned, non-executable fixture root instead of
# being falsely rebound to current production source.
HISTORICAL_SOURCE_SNAPSHOT_COMMIT = (
    "38027523f65f97a81044555c2f42b020eada3436"
)
HISTORICAL_SOURCE_SNAPSHOT_ROOT = (
    "docs/evidence/macos-build24-lifecycle-source-v1"
)
HISTORICAL_SOURCE_STORAGE_PATHS = {
    "script/run_macos_local_dmg_install_smoke_v2.py": (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "run_macos_local_dmg_install_smoke_v2.py"
    ),
    "script/test_run_macos_local_dmg_install_smoke_v2.py": (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "test_run_macos_local_dmg_install_smoke_v2.py"
    ),
    "script/run_macos_local_dmg_uninstall_reinstall_smoke.py": (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "run_macos_local_dmg_uninstall_reinstall_smoke.py"
    ),
    "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py": (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "test_run_macos_local_dmg_uninstall_reinstall_smoke.py"
    ),
    (
        "script/run_macos_local_dmg_uninstall_reinstall_"
        "state_recovery_smoke.py"
    ): (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
    ),
    (
        "script/test_run_macos_local_dmg_uninstall_reinstall_"
        "state_recovery_smoke.py"
    ): (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "test_run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
    ),
    (
        "script/run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ): (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ),
    (
        "script/test_run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ): (
        f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script/"
        "test_run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ),
}

HISTORICAL_SOURCE_DIRECTORY_INVENTORIES = {
    HISTORICAL_SOURCE_SNAPSHOT_ROOT: ("script",),
    f"{HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script": tuple(
        sorted(Path(path).name for path in HISTORICAL_SOURCE_STORAGE_PATHS.values())
    ),
}


def source_storage_path(relative_path: str) -> str:
    return HISTORICAL_SOURCE_STORAGE_PATHS.get(relative_path, relative_path)


def validate_historical_source_snapshot_contract(
    snapshot: RepositorySnapshotReader | None = None,
) -> None:
    expected_root = "docs/evidence/macos-build24-lifecycle-source-v1"
    expected_storage_paths = {
        "script/run_macos_local_dmg_install_smoke_v2.py": (
            f"{expected_root}/script/run_macos_local_dmg_install_smoke_v2.py"
        ),
        "script/test_run_macos_local_dmg_install_smoke_v2.py": (
            f"{expected_root}/script/test_run_macos_local_dmg_install_smoke_v2.py"
        ),
        "script/run_macos_local_dmg_uninstall_reinstall_smoke.py": (
            f"{expected_root}/script/"
            "run_macos_local_dmg_uninstall_reinstall_smoke.py"
        ),
        "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py": (
            f"{expected_root}/script/"
            "test_run_macos_local_dmg_uninstall_reinstall_smoke.py"
        ),
        (
            "script/run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke.py"
        ): (
            f"{expected_root}/script/"
            "run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
        ),
        (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke.py"
        ): (
            f"{expected_root}/script/"
            "test_run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
        ),
        (
            "script/run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        ): (
            f"{expected_root}/script/"
            "run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        ),
        (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        ): (
            f"{expected_root}/script/"
            "test_run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        ),
    }
    expected_identities = {
        "script/run_macos_local_dmg_install_smoke_v2.py": identity(
            12_962,
            "515de26546ba97c6879cad1fdf62cda6f3dcbf24a668804955f95e1755d1f374",
        ),
        "script/test_run_macos_local_dmg_install_smoke_v2.py": identity(
            20_191,
            "6aa2e9e2354aa36f97ff096787ac05115c95114fcf95869463b47f39dea5006c",
        ),
        "script/run_macos_local_dmg_uninstall_reinstall_smoke.py": identity(
            25_675,
            "300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae",
        ),
        "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py": identity(
            34_767,
            "6e782fc128aad75b20f1b04752e4754ccbf8ceaadc9e2fcabe9cc2e537bfb703",
        ),
        (
            "script/run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke.py"
        ): identity(
            28_693,
            "31bdae72f08f1f68bc4a07cb59d194c943d56179acf0a7b149ddc2e652c68b4c",
        ),
        (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke.py"
        ): identity(
            34_310,
            "22ddc7ec39aa8c88c2b69f2dd8a390a287d85eeaff4704109784e221483faee2",
        ),
        (
            "script/run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        ): identity(
            48_788,
            "ddd2c8286d1b78541d4ed18f125b9d1867be718e0276adb9880e60929fc15ec3",
        ),
        (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        ): identity(
            50_750,
            "f06479f5eb4e12d3f0072e8259e9a7b1c28e8797a423ea88b092978a4142b658",
        ),
    }
    if (
        HISTORICAL_SOURCE_SNAPSHOT_COMMIT
        != "38027523f65f97a81044555c2f42b020eada3436"
        or HISTORICAL_SOURCE_SNAPSHOT_ROOT != expected_root
        or HISTORICAL_SOURCE_STORAGE_PATHS != expected_storage_paths
        or {
            path: SOURCE_CONTRACTS.get(path)
            for path in expected_storage_paths
        }
        != expected_identities
        or HISTORICAL_SOURCE_DIRECTORY_INVENTORIES
        != {
            expected_root: ("script",),
            f"{expected_root}/script": tuple(
                sorted(Path(path).name for path in expected_storage_paths.values())
            ),
        }
    ):
        raise LifecycleEvidenceError(
            "historical source snapshot contract differs"
        )
    if snapshot is None:
        return
    for relative_directory, expected_entries in (
        HISTORICAL_SOURCE_DIRECTORY_INVENTORIES.items()
    ):
        if tuple(sorted(snapshot.list_directory(relative_directory))) != (
            expected_entries
        ):
            raise LifecycleEvidenceError(
                "historical source snapshot directory inventory differs: "
                f"{relative_directory}"
            )

UNIT_TEST_MODULES = (
    "script.test_release_version_ledger",
    "script.test_run_macos_packaged_app_lifecycle_smoke",
    "script.test_run_macos_packaged_app_state_recovery_smoke",
    "script.test_run_macos_clean_home_installed_app_smoke",
    "script.test_run_macos_clean_home_installed_state_recovery_smoke",
    "script.test_run_macos_isolated_uninstall_reinstall_smoke",
    "script.test_run_macos_isolated_upgrade_smoke",
    "script.test_run_macos_local_dmg_install_smoke",
    "script.test_run_macos_local_dmg_install_smoke_v2",
    "script.test_run_macos_local_dmg_uninstall_reinstall_smoke",
    "script.test_run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke",
    (
        "script.test_run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke"
    ),
)

FORBIDDEN_UNIT_TEST_TOKENS = (
    "security",
    "p2p",
    "relay",
    "network",
    "android",
    "device",
    "provider",
    "signing",
    "notary",
)

EXACT_INTEGER_FIELD_NAMES = frozenset(
    {
        "activationPolicy",
        "buildNumber",
        "configurationCount",
        "cycleCount",
        "databaseCount",
        "emptyConfigurationCount",
        "eventJsonSize",
        "exitCode",
        "fileCount",
        "installCount",
        "legacyJsonlSize",
        "memberCountExcludingManifest",
        "minSdk",
        "moduleCount",
        "ordinal",
        "packageCount",
        "relationshipCount",
        "removalCount",
        "regularFileCount",
        "runCount",
        "schemaVersion",
        "signalNumber",
        "size",
        "targetSdk",
        "totalEventCount",
        "totalRegularFileBytes",
        "versionCode",
    }
)
EXACT_FLOAT_FIELD_NAMES = frozenset({"minimumObservationSeconds"})
EXACT_BOOLEAN_FIELD_NAMES = frozenset(
    {
        "adHocAppSealAndVersionVerified",
        "appAbsentAfterEachRemoval",
        "appAbsentAfterFinalRemoval",
        "appKitProcessAbsentAfterReap",
        "applicationSupportCleanupPerformed",
        "applicationSupportPreservedAcrossRemovalAndReinstall",
        "applicationSupportPreservedAcrossUpgrade",
        "applicationsAliasPresent",
        "artifactFilesAnalyzed",
        "bytesAndModesUnchangedAcrossUpgrade",
        "cleanHomeConfigured",
        "codesignVerified",
        "currentRelaunchIdempotent",
        "currentSourceCompared",
        "detachedBeforeEachLaunch",
        "detachedBeforeLaunch",
        "distinctProcessIdentifiers",
        "emptyRuntimeChatVerified",
        "ephemeral",
        "exactExecutableIdentityMatchedImmediatelyBeforeSignal",
        "exactExecutableRevalidatedBeforeSignal",
        "exactFreshMountpoint",
        "exactFreshMountpointPerInstall",
        "exactInstalledBundlePerCycle",
        "exactReleaseTreeCopied",
        "exactReleaseTreeCopiedEachInstall",
        "exactTemporaryAppPathOnly",
        "exactTemporaryAppStoppedBeforeEachRemoval",
        "executablePathMatched",
        "exported",
        "extendedAttributesIncluded",
        "finishedLaunching",
        "gracefulTerminationRequested",
        "inFlightWriteCheckpointObserved",
        "installedStateBytesAndModesUnchangedAcrossRelaunch",
        "installedStateBytesAndModesUnchangedAcrossRemovalAndReinstall",
        "legacyAbsentAfterUpgrade",
        "legacyAbsentBeforeAbruptAndRecoveryReadback",
        "legacyAbsentBeforeReinstallReadback",
        "legacyAbsentBeforeSecondRun",
        "legacyFixturePreservedUnchanged",
        "legacyRemovedByHarnessBeforeReinstall",
        "licenseCompatibilityConclusionIncluded",
        "mappingEmbeddedByteIdentical",
        "migrationCommittedBeforeAbruptLaunch",
        "networkRequiredForReleaseBuild",
        "newProcessIdentifierDetected",
        "noExactTemporaryAppRemaining",
        "nobrowse",
        "observationCompletedBeforeSignal",
        "observationDeadlineReached",
        "oneMountedEntity",
        "oneMountedEntityPerInstall",
        "ownedChildProcess",
        "persistenceProbePassedBeforeSignal",
        "postAbruptStateBytesAndModesUnchangedAcrossRemovalReinstall",
        "preexistingBundleApplicationsPreserved",
        "processReaped",
        "readOnly",
        "readbackAndExerciseSameSnapshot",
        "regularFileBytesAndModesUnchanged",
        "regularFileBytesAndModesUnchangedAcrossRelaunch",
        "regularFileTreeMatchesReleaseManifest",
        "reinstallTreeMatchesInitial",
        "resultBytesEqual",
        "retained",
        "runtimeIdentityFileOverrideConfigured",
        "runtimeIdentityFilePresent",
        "sameImageBytesUsedForBothInstalls",
        "sandboxedOwnedChildConfigured",
        "snapshotFilesUnchangedAfterExercise",
        "sqliteCanaryUnchangedAcrossRemovalAndReinstall",
        "sqliteCanaryUnchangedAcrossRuns",
        "stableAcrossRelaunch",
        "stableAcrossRemovalAndReinstall",
        "stalePreviousBundleFilesAbsent",
        "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination",
        "statePresentBeforeReinstall",
        "temporaryCFUserHomeConfigured",
        "terminationAccepted",
        "treesDiffer",
        "unmountedAfterEachCopy",
        "unmountedVerified",
        "verified",
    }
)

REPOSITORY_SNAPSHOT_FILE_PATHS = tuple(
    sorted(
        {
            *(source_storage_path(path) for path in SOURCE_CONTRACTS),
            *(
                contract.relative_path
                for contract in EVIDENCE_CONTRACTS
            ),
            *(
                (
                    f"dist/releases/{release.release_id}/"
                    f"{release.release_id}{suffix}"
                )
                for release in RELEASES.values()
                for suffix in (
                    ".zip",
                    ".manifest.json",
                    ".zip.sha256",
                )
            ),
        }
    )
)


def resolve_relative(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if (
        type(relative_path) is not str
        or not relative_path
        or relative_path in (".", "..")
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
    ):
        raise LifecycleEvidenceError(
            f"invalid repository-relative path: {relative_path!r}"
        )
    candidate = root
    for component in path.parts[:-1]:
        candidate /= component
        try:
            status = candidate.lstat()
        except FileNotFoundError:
            break
        except OSError as error:
            raise LifecycleEvidenceError(
                f"cannot inspect path component {candidate}: {error}"
            ) from error
        if stat.S_ISLNK(status.st_mode):
            raise LifecycleEvidenceError(
                f"repository-relative path crosses a symlink: {candidate}"
            )
    return root / path


def stable_file_fields(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def read_open_regular_file(
    descriptor: int,
    *,
    label: str,
    maximum_bytes: int,
    retain_bytes: bool,
    path_status: Callable[[], os.stat_result],
) -> tuple[ByteIdentity, bytes | None]:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size < 0
        or before.st_size > maximum_bytes
    ):
        raise LifecycleEvidenceError(
            f"file has an invalid type or size: {label}"
        )
    digest = hashlib.sha256()
    payload = bytearray() if retain_bytes else None
    total = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > maximum_bytes:
            raise LifecycleEvidenceError(
                f"file exceeded its byte limit while reading: {label}"
            )
        digest.update(chunk)
        if payload is not None:
            payload.extend(chunk)
    after = os.fstat(descriptor)
    if stable_file_fields(before) != stable_file_fields(after) or total != (
        before.st_size
    ):
        raise LifecycleEvidenceError(f"file changed while reading: {label}")
    try:
        path_after = path_status()
    except OSError as error:
        raise LifecycleEvidenceError(
            f"file path changed after reading {label}: {error}"
        ) from error
    if (
        stat.S_ISLNK(path_after.st_mode)
        or path_after.st_nlink != 1
        or stable_file_fields(path_after) != stable_file_fields(after)
    ):
        raise LifecycleEvidenceError(
            f"file path identity changed while reading: {label}"
        )
    return (
        ByteIdentity(size=total, sha256=digest.hexdigest()),
        bytes(payload) if payload is not None else None,
    )


def read_stable_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    retain_bytes: bool,
) -> tuple[ByteIdentity, bytes | None]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise LifecycleEvidenceError(
            f"cannot open regular file {path}: {error}"
        ) from error
    try:
        return read_open_regular_file(
            descriptor,
            label=str(path),
            maximum_bytes=maximum_bytes,
            retain_bytes=retain_bytes,
            path_status=path.lstat,
        )
    finally:
        os.close(descriptor)


def directory_identity(status: os.stat_result) -> tuple[int, int, int]:
    return (status.st_dev, status.st_ino, status.st_mode)


def open_repository_parent_chain(
    root: Path,
    parent_parts: Sequence[str],
) -> tuple[list[int], tuple[tuple[int, int, int], ...]]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_DIRECTORY", 0)
    descriptors: list[int] = []
    identities: list[tuple[int, int, int]] = []
    try:
        root_descriptor = os.open(root, flags)
        descriptors.append(root_descriptor)
        root_status = os.fstat(root_descriptor)
        root_path_status = root.lstat()
        if (
            not stat.S_ISDIR(root_status.st_mode)
            or stat.S_ISLNK(root_path_status.st_mode)
            or directory_identity(root_status)
            != directory_identity(root_path_status)
        ):
            raise LifecycleEvidenceError(
                f"repository root must be one physical directory: {root}"
            )
        identities.append(directory_identity(root_status))
        for component in parent_parts:
            descriptor = os.open(
                component,
                flags,
                dir_fd=descriptors[-1],
            )
            descriptors.append(descriptor)
            status = os.fstat(descriptor)
            if not stat.S_ISDIR(status.st_mode):
                raise LifecycleEvidenceError(
                    "repository path component is not a directory: "
                    f"{component}"
                )
            identities.append(directory_identity(status))
        return descriptors, tuple(identities)
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def verify_repository_parent_chain(
    root: Path,
    parent_parts: Sequence[str],
    expected_identities: tuple[tuple[int, int, int], ...],
) -> None:
    descriptors, actual_identities = open_repository_parent_chain(
        root,
        parent_parts,
    )
    try:
        if actual_identities != expected_identities:
            raise LifecycleEvidenceError(
                "repository parent directory identity changed while reading"
            )
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def read_stable_repository_file(
    root: Path,
    relative_path: str,
    *,
    maximum_bytes: int,
    retain_bytes: bool,
) -> tuple[ByteIdentity, bytes | None]:
    path = Path(relative_path)
    label = str(resolve_relative(root, relative_path))
    descriptors, parent_identities = open_repository_parent_chain(
        root,
        path.parts[:-1],
    )
    file_descriptor: int | None = None
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    file_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        file_descriptor = os.open(
            path.parts[-1],
            file_flags,
            dir_fd=descriptors[-1],
        )
        result = read_open_regular_file(
            file_descriptor,
            label=label,
            maximum_bytes=maximum_bytes,
            retain_bytes=retain_bytes,
            path_status=lambda: os.stat(
                path.parts[-1],
                dir_fd=descriptors[-1],
                follow_symlinks=False,
            ),
        )
        verify_repository_parent_chain(
            root,
            path.parts[:-1],
            parent_identities,
        )
        return result
    except OSError as error:
        raise LifecycleEvidenceError(
            f"cannot read repository file {label}: {error}"
        ) from error
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(descriptors):
            os.close(descriptor)


class RepositorySnapshotReader:
    """Hold one physical repository directory graph for a complete readback."""

    def __init__(
        self,
        root: Path,
        directories: Sequence[str] = REPOSITORY_SNAPSHOT_DIRECTORIES,
        files: Sequence[str] = REPOSITORY_SNAPSHOT_FILE_PATHS,
    ) -> None:
        self.root = root
        self._descriptors: dict[str, int] = {}
        self._identities: dict[str, tuple[int, int, int]] = {}
        self._file_descriptors: dict[str, int] = {}
        self._file_identities: dict[str, tuple[int, ...]] = {}
        self._file_paths = tuple(files)
        self._closed = False
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_DIRECTORY", 0)
        try:
            root_descriptor = os.open(root, flags)
            root_status = os.fstat(root_descriptor)
            root_path_status = root.lstat()
            if (
                not stat.S_ISDIR(root_status.st_mode)
                or stat.S_ISLNK(root_path_status.st_mode)
                or directory_identity(root_status)
                != directory_identity(root_path_status)
            ):
                os.close(root_descriptor)
                raise LifecycleEvidenceError(
                    f"repository root must be one physical directory: {root}"
                )
            self._descriptors[""] = root_descriptor
            self._identities[""] = directory_identity(root_status)

            normalized_directories: list[str] = []
            for relative in directories:
                path = Path(relative)
                if (
                    type(relative) is not str
                    or not relative
                    or relative in (".", "..")
                    or path.is_absolute()
                    or "." in path.parts
                    or ".." in path.parts
                    or path.as_posix() != relative
                ):
                    raise LifecycleEvidenceError(
                        "invalid repository snapshot directory: "
                        f"{relative!r}"
                    )
                normalized_directories.append(relative)
            if len(set(normalized_directories)) != len(
                normalized_directories
            ):
                raise LifecycleEvidenceError(
                    "repository snapshot directories must be unique"
                )
            for relative in sorted(
                normalized_directories,
                key=lambda value: (len(Path(value).parts), value),
            ):
                path = Path(relative)
                parent = (
                    ""
                    if path.parent == Path(".")
                    else path.parent.as_posix()
                )
                if parent not in self._descriptors:
                    raise LifecycleEvidenceError(
                        "repository snapshot directory omits parent: "
                        f"{relative}"
                    )
                descriptor = os.open(
                    path.name,
                    flags,
                    dir_fd=self._descriptors[parent],
                )
                status = os.fstat(descriptor)
                if not stat.S_ISDIR(status.st_mode):
                    os.close(descriptor)
                    raise LifecycleEvidenceError(
                        "repository snapshot path is not a directory: "
                        f"{relative}"
                    )
                self._descriptors[relative] = descriptor
                self._identities[relative] = directory_identity(status)

            if len(set(self._file_paths)) != len(self._file_paths):
                raise LifecycleEvidenceError(
                    "repository snapshot file paths must be unique"
                )
            file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            file_flags |= getattr(os, "O_NOFOLLOW", 0)
            for relative_path in self._file_paths:
                path = Path(relative_path)
                resolve_relative(root, relative_path)
                parent = (
                    ""
                    if path.parent == Path(".")
                    else path.parent.as_posix()
                )
                if parent not in self._descriptors:
                    raise LifecycleEvidenceError(
                        "repository snapshot file parent is not held: "
                        f"{relative_path}"
                    )
                descriptor = os.open(
                    path.name,
                    file_flags,
                    dir_fd=self._descriptors[parent],
                )
                status = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(status.st_mode)
                    or status.st_nlink != 1
                ):
                    os.close(descriptor)
                    raise LifecycleEvidenceError(
                        "repository snapshot file must be one physical "
                        f"regular file: {relative_path}"
                    )
                self._file_descriptors[relative_path] = descriptor
                self._file_identities[relative_path] = stable_file_fields(
                    status
                )
            self.verify_held_file_entries()
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> RepositorySnapshotReader:
        return self

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for descriptor in self._file_descriptors.values():
            os.close(descriptor)
        self._file_descriptors.clear()
        for relative in sorted(
            self._descriptors,
            key=lambda value: len(Path(value).parts),
            reverse=True,
        ):
            os.close(self._descriptors[relative])
        self._descriptors.clear()

    def require_open(self) -> None:
        if self._closed:
            raise LifecycleEvidenceError(
                "repository snapshot reader is already closed"
            )

    def list_directory(self, relative_directory: str) -> tuple[str, ...]:
        self.require_open()
        if relative_directory not in self._descriptors:
            raise LifecycleEvidenceError(
                "directory is outside the held repository snapshot: "
                f"{relative_directory}"
            )
        try:
            return tuple(os.listdir(self._descriptors[relative_directory]))
        except OSError as error:
            raise LifecycleEvidenceError(
                "cannot enumerate held repository directory "
                f"{relative_directory}: {error}"
            ) from error

    def verify_held_file_entries(self) -> None:
        self.require_open()
        for relative_path, expected in self._file_identities.items():
            path = Path(relative_path)
            parent = (
                ""
                if path.parent == Path(".")
                else path.parent.as_posix()
            )
            try:
                current = os.stat(
                    path.name,
                    dir_fd=self._descriptors[parent],
                    follow_symlinks=False,
                )
            except OSError as error:
                raise LifecycleEvidenceError(
                    "repository snapshot file entry changed: "
                    f"{relative_path}: {error}"
                ) from error
            if (
                stat.S_ISLNK(current.st_mode)
                or current.st_nlink != 1
                or stable_file_fields(current) != expected
            ):
                raise LifecycleEvidenceError(
                    "repository snapshot file entry identity changed: "
                    f"{relative_path}"
                )

    def require_identity(
        self,
        relative_path: str,
        expected: ByteIdentity,
        *,
        maximum_bytes: int,
        retain_bytes: bool = False,
    ) -> bytes | None:
        self.require_open()
        path = Path(relative_path)
        resolve_relative(self.root, relative_path)
        parent = (
            ""
            if path.parent == Path(".")
            else path.parent.as_posix()
        )
        if parent not in self._descriptors:
            raise LifecycleEvidenceError(
                "file parent is outside the held repository snapshot: "
                f"{relative_path}"
            )
        if relative_path not in self._file_descriptors:
            raise LifecycleEvidenceError(
                "file is outside the held repository snapshot: "
                f"{relative_path}"
            )
        descriptor = self._file_descriptors[relative_path]
        if stable_file_fields(os.fstat(descriptor)) != (
            self._file_identities[relative_path]
        ):
            raise LifecycleEvidenceError(
                "held repository file changed before readback: "
                f"{relative_path}"
            )
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            actual, payload = read_open_regular_file(
                descriptor,
                label=str(self.root / path),
                maximum_bytes=maximum_bytes,
                retain_bytes=retain_bytes,
                path_status=lambda: os.stat(
                    path.name,
                    dir_fd=self._descriptors[parent],
                    follow_symlinks=False,
                ),
            )
        except OSError as error:
            raise LifecycleEvidenceError(
                f"cannot read held repository file {relative_path}: {error}"
            ) from error
        if actual != expected:
            raise LifecycleEvidenceError(
                f"byte identity differs for {relative_path}: "
                f"expected size={expected.size} sha256={expected.sha256}, "
                f"got size={actual.size} sha256={actual.sha256}"
            )
        return payload

    def verify_unchanged(self) -> None:
        self.require_open()
        self.verify_held_file_entries()
        with RepositorySnapshotReader(
            self.root,
            tuple(
                relative
                for relative in self._descriptors
                if relative
            ),
            self._file_paths,
        ) as current:
            if (
                current._identities != self._identities
                or current._file_identities != self._file_identities
            ):
                raise LifecycleEvidenceError(
                    "repository file or directory graph changed during "
                    "readback"
                )


def require_identity(
    path: Path,
    expected: ByteIdentity,
    *,
    maximum_bytes: int,
    retain_bytes: bool = False,
) -> bytes | None:
    actual, payload = read_stable_regular_file(
        path,
        maximum_bytes=maximum_bytes,
        retain_bytes=retain_bytes,
    )
    if actual != expected:
        raise LifecycleEvidenceError(
            f"byte identity differs for {path}: "
            f"expected size={expected.size} sha256={expected.sha256}, "
            f"got size={actual.size} sha256={actual.sha256}"
        )
    return payload


def require_repository_identity(
    root: Path,
    relative_path: str,
    expected: ByteIdentity,
    *,
    maximum_bytes: int,
    retain_bytes: bool = False,
) -> bytes | None:
    actual, payload = read_stable_repository_file(
        root,
        relative_path,
        maximum_bytes=maximum_bytes,
        retain_bytes=retain_bytes,
    )
    if actual != expected:
        raise LifecycleEvidenceError(
            f"byte identity differs for {relative_path}: "
            f"expected size={expected.size} sha256={expected.sha256}, "
            f"got size={actual.size} sha256={actual.sha256}"
        )
    return payload


def require_bound_identity(
    root: Path,
    relative_path: str,
    expected: ByteIdentity,
    *,
    maximum_bytes: int,
    retain_bytes: bool = False,
    snapshot: RepositorySnapshotReader | None = None,
) -> bytes | None:
    if snapshot is not None:
        return snapshot.require_identity(
            relative_path,
            expected,
            maximum_bytes=maximum_bytes,
            retain_bytes=retain_bytes,
        )
    return require_repository_identity(
        root,
        relative_path,
        expected,
        maximum_bytes=maximum_bytes,
        retain_bytes=retain_bytes,
    )


def reject_duplicate_object_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LifecycleEvidenceError(f"JSON object repeats key {key!r}")
        result[key] = value
    return result


def reject_nonfinite_json(value: str) -> object:
    raise LifecycleEvidenceError(f"JSON contains non-finite number {value!r}")


def parse_canonical_json(payload: bytes, label: str) -> dict[str, object]:
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicate_object_pairs,
            parse_constant=reject_nonfinite_json,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LifecycleEvidenceError(
            f"{label} is not strict UTF-8 JSON: {error}"
        ) from error
    if type(document) is not dict:
        raise LifecycleEvidenceError(f"{label} must contain one JSON object")
    canonical = (
        json.dumps(
            document,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if payload != canonical:
        raise LifecycleEvidenceError(f"{label} is not canonical JSON")
    return document


def require_exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise LifecycleEvidenceError(f"{label} must be an exact integer")
    return value


def require_exact_keys(
    value: object,
    expected: Iterable[str],
    label: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise LifecycleEvidenceError(f"{label} must be an object")
    expected_set = set(expected)
    if set(value) != expected_set:
        raise LifecycleEvidenceError(
            f"{label} keys differ: expected={sorted(expected_set)!r}, "
            f"actual={sorted(value)!r}"
        )
    return value


def validate_scalar_field_types(
    value: object,
    *,
    label: str,
) -> None:
    if type(value) is dict:
        for key, child in value.items():
            child_label = f"{label}.{key}"
            if key in EXACT_INTEGER_FIELD_NAMES and type(child) is not int:
                raise LifecycleEvidenceError(
                    f"{child_label} must be an exact integer"
                )
            if key in EXACT_FLOAT_FIELD_NAMES and (
                type(child) is not float or not math.isfinite(child)
            ):
                raise LifecycleEvidenceError(
                    f"{child_label} must be one finite exact float"
                )
            if key in EXACT_BOOLEAN_FIELD_NAMES and type(child) is not bool:
                raise LifecycleEvidenceError(
                    f"{child_label} must be an exact boolean"
                )
            validate_scalar_field_types(child, label=child_label)
    elif type(value) is list:
        for ordinal, child in enumerate(value):
            validate_scalar_field_types(
                child,
                label=f"{label}[{ordinal}]",
            )


def release_summary(contract: ReleaseContract) -> dict[str, object]:
    return {
        "archiveSha256": contract.archive.sha256,
        "manifestSha256": contract.manifest.sha256,
        "releaseId": contract.release_id,
    }


def app_summary(contract: ReleaseContract) -> dict[str, object]:
    return {
        "buildNumber": contract.build_number,
        "bundleIdentifier": BUNDLE_IDENTIFIER,
        "executableSha256": contract.executable.sha256,
        "marketingVersion": MARKETING_VERSION,
        "uuid": contract.executable_uuid,
    }


def archive_snapshot_files(
    contract: ReleaseContract,
) -> dict[str, dict[str, object]]:
    return {
        f"{contract.release_id}.manifest.json": {
            "sha256": contract.manifest.sha256,
            "size": contract.manifest.size,
        },
        f"{contract.release_id}.zip": {
            "sha256": contract.archive.sha256,
            "size": contract.archive.size,
        },
        f"{contract.release_id}.zip.sha256": {
            "sha256": contract.checksum.sha256,
            "size": contract.checksum.size,
        },
    }


def expected_archive_readback(
    contract: ReleaseContract,
    *,
    mode: str,
) -> dict[str, object]:
    return {
        "currentSourceCompared": False,
        "mode": mode,
        "readbackAndExerciseSameSnapshot": True,
        "snapshotFiles": archive_snapshot_files(contract),
        "snapshotFilesUnchangedAfterExercise": True,
        "status": "passed",
    }


def validate_ledger(
    root: Path,
    *,
    snapshot: RepositorySnapshotReader | None = None,
) -> None:
    payload = require_bound_identity(
        root,
        LEDGER_RELATIVE_PATH,
        LEDGER_IDENTITY,
        maximum_bytes=MAXIMUM_SOURCE_BYTES,
        retain_bytes=True,
        snapshot=snapshot,
    )
    if payload is None:
        raise LifecycleEvidenceError("release ledger bytes were not retained")
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise LifecycleEvidenceError("release ledger must be ASCII") from error
    lines = text.splitlines()
    if not text.endswith("\n") or len(lines) < 3:
        raise LifecycleEvidenceError("release ledger is truncated or noncanonical")
    if lines[0] != "build_number\tmarketing_version":
        raise LifecycleEvidenceError("release ledger header differs")
    entries: list[tuple[int, str]] = []
    for ordinal, line in enumerate(lines[1:], start=1):
        fields = line.split("\t")
        if len(fields) != 2 or not fields[0].isdigit() or not fields[1]:
            raise LifecycleEvidenceError(
                f"release ledger row {ordinal} is malformed"
            )
        build = int(fields[0])
        if entries and build <= entries[-1][0]:
            raise LifecycleEvidenceError(
                "release ledger build numbers must strictly increase"
            )
        entries.append((build, fields[1]))
    if entries[-2:] != [(23, MARKETING_VERSION), (24, MARKETING_VERSION)]:
        raise LifecycleEvidenceError(
            "release ledger terminal pair must remain exactly Build 23 and 24"
        )


def validate_archive_manifest(
    document: dict[str, object],
    contract: ReleaseContract,
) -> None:
    validate_scalar_field_types(document, label="manifest")
    if require_exact_int(document.get("schemaVersion"), "manifest.schemaVersion") != 2:
        raise LifecycleEvidenceError("release manifest schemaVersion differs")
    if document.get("product") != "AetherLink" or document.get("channel") != "local":
        raise LifecycleEvidenceError("release manifest product or channel differs")
    if document.get("release") != {
        "buildNumber": contract.build_number,
        "marketingVersion": MARKETING_VERSION,
        "releaseId": contract.release_id,
    }:
        raise LifecycleEvidenceError("release manifest version identity differs")
    ledger = require_exact_keys(
        document.get("ledger"),
        {"path", "sha256", "size"},
        "manifest.ledger",
    )
    if ledger != {
        "path": LEDGER_RELATIVE_PATH,
        "sha256": contract.ledger.sha256,
        "size": contract.ledger.size,
    }:
        raise LifecycleEvidenceError("release manifest ledger identity differs")
    archive = require_exact_keys(
        document.get("archive"),
        {
            "artifactPathPolicy",
            "compression",
            "entryOrder",
            "entryTimestamp",
            "extendedAttributesIncluded",
            "memberCountExcludingManifest",
            "normalizations",
            "reproducibilityScope",
        },
        "manifest.archive",
    )
    if (
        archive.get("compression") != "stored"
        or archive.get("entryOrder") != "manifest-first-then-ascii-path"
        or require_exact_int(
            archive.get("memberCountExcludingManifest"),
            "manifest.archive.memberCountExcludingManifest",
        )
        != 29
    ):
        raise LifecycleEvidenceError("release manifest archive contract differs")
    platforms = require_exact_keys(
        document.get("platforms"),
        {"android", "macos"},
        "manifest.platforms",
    )
    macos = require_exact_keys(
        platforms.get("macos"),
        {
            "architectures",
            "buildNumber",
            "bundleId",
            "dSYM",
            "locales",
            "marketingVersion",
            "minimumSystemVersion",
            "signatureState",
            "uuid",
        },
        "manifest.platforms.macos",
    )
    if (
        require_exact_int(
            macos.get("buildNumber"),
            "manifest.platforms.macos.buildNumber",
        )
        != contract.build_number
        or macos.get("bundleId") != BUNDLE_IDENTIFIER
        or macos.get("marketingVersion") != MARKETING_VERSION
        or macos.get("uuid") != contract.executable_uuid
    ):
        raise LifecycleEvidenceError("release manifest macOS identity differs")
    members = document.get("members")
    if type(members) is not list:
        raise LifecycleEvidenceError("release manifest members must be a list")
    executable_records = [
        member
        for member in members
        if type(member) is dict
        and member.get("path") == "macos/AetherLink.app/Contents/MacOS/AetherLink"
    ]
    expected_executable = {
        "mode": "0755",
        "path": "macos/AetherLink.app/Contents/MacOS/AetherLink",
        "sha256": contract.executable.sha256,
        "size": contract.executable.size,
    }
    if executable_records != [expected_executable]:
        raise LifecycleEvidenceError(
            "release manifest macOS executable identity differs"
        )


def validate_release_archive(
    root: Path,
    contract: ReleaseContract,
    *,
    snapshot: RepositorySnapshotReader | None = None,
) -> None:
    relative_directory = f"dist/releases/{contract.release_id}"
    directory = resolve_relative(root, relative_directory)
    try:
        directory_status = directory.lstat()
    except OSError as error:
        raise LifecycleEvidenceError(
            f"cannot inspect release directory {directory}: {error}"
        ) from error
    if (
        stat.S_ISLNK(directory_status.st_mode)
        or not stat.S_ISDIR(directory_status.st_mode)
    ):
        raise LifecycleEvidenceError(
            f"release directory must be physical: {directory}"
        )
    expected_files = {
        f"{contract.release_id}.zip": contract.archive,
        f"{contract.release_id}.manifest.json": contract.manifest,
        f"{contract.release_id}.zip.sha256": contract.checksum,
    }
    if snapshot is not None:
        actual_names = set(snapshot.list_directory(relative_directory))
    else:
        try:
            actual_names = {child.name for child in directory.iterdir()}
        except OSError as error:
            raise LifecycleEvidenceError(
                f"cannot enumerate release directory {directory}: {error}"
            ) from error
    if actual_names != set(expected_files):
        raise LifecycleEvidenceError(
            f"release sidecar set differs for {contract.release_id}"
        )

    archive_path = directory / f"{contract.release_id}.zip"
    manifest_path = directory / f"{contract.release_id}.manifest.json"
    checksum_path = directory / f"{contract.release_id}.zip.sha256"
    require_bound_identity(
        root,
        f"{relative_directory}/{archive_path.name}",
        contract.archive,
        maximum_bytes=MAXIMUM_ARCHIVE_BYTES,
        snapshot=snapshot,
    )
    manifest_payload = require_bound_identity(
        root,
        f"{relative_directory}/{manifest_path.name}",
        contract.manifest,
        maximum_bytes=MAXIMUM_JSON_BYTES,
        retain_bytes=True,
        snapshot=snapshot,
    )
    checksum_payload = require_bound_identity(
        root,
        f"{relative_directory}/{checksum_path.name}",
        contract.checksum,
        maximum_bytes=MAXIMUM_JSON_BYTES,
        retain_bytes=True,
        snapshot=snapshot,
    )
    if manifest_payload is None or checksum_payload is None:
        raise LifecycleEvidenceError(
            f"release sidecar bytes were not retained for {contract.release_id}"
        )
    expected_checksum = (
        f"{contract.archive.sha256}  {contract.release_id}.zip\n".encode("ascii")
    )
    if checksum_payload != expected_checksum:
        raise LifecycleEvidenceError(
            f"release checksum sidecar body differs for {contract.release_id}"
        )
    validate_archive_manifest(
        parse_canonical_json(
            manifest_payload,
            f"{contract.release_id} manifest",
        ),
        contract,
    )
    if snapshot is not None:
        final_names = set(snapshot.list_directory(relative_directory))
    else:
        try:
            final_names = {child.name for child in directory.iterdir()}
        except OSError as error:
            raise LifecycleEvidenceError(
                f"cannot re-enumerate release directory {directory}: {error}"
            ) from error
    if final_names != actual_names:
        raise LifecycleEvidenceError(
            f"release sidecar set changed for {contract.release_id}"
        )


def validate_build_result(
    document: dict[str, object],
    contract: EvidenceContract,
) -> None:
    if contract.release_build not in RELEASES:
        raise LifecycleEvidenceError("build result has no release contract")
    release = RELEASES[contract.release_build]
    if document.get("release") != release_summary(release):
        raise LifecycleEvidenceError(
            f"{contract.relative_path} release identity differs"
        )
    if "app" in document and document.get("app") != app_summary(release):
        raise LifecycleEvidenceError(
            f"{contract.relative_path} app identity differs"
        )
    installation = document.get("installation")
    if type(installation) is not dict:
        raise LifecycleEvidenceError(
            f"{contract.relative_path} installation must be an object"
        )
    if installation.get("tree") != APP_TREE:
        raise LifecycleEvidenceError(
            f"{contract.relative_path} app-tree identity differs"
        )
    if "archiveReadback" in document and document.get(
        "archiveReadback"
    ) != expected_archive_readback(
        release,
        mode="archive-only-no-current-source",
    ):
        raise LifecycleEvidenceError(
            f"{contract.relative_path} archive readback differs"
        )


def validate_upgrade_result(
    document: dict[str, object],
    contract: EvidenceContract,
) -> None:
    previous = RELEASES[23]
    current = RELEASES[24]
    releases = require_exact_keys(
        document.get("releases"),
        {"from", "to"},
        f"{contract.relative_path}.releases",
    )
    expected_releases = {
        "from": {
            "app": app_summary(previous),
            **release_summary(previous),
        },
        "to": {
            "app": app_summary(current),
            **release_summary(current),
        },
    }
    if releases != expected_releases:
        raise LifecycleEvidenceError("upgrade release identities differ")
    archive_readback = require_exact_keys(
        document.get("archiveReadback"),
        {"current", "previous"},
        f"{contract.relative_path}.archiveReadback",
    )
    if archive_readback != {
        "current": expected_archive_readback(
            current,
            mode="archive-only-no-current-source",
        ),
        "previous": expected_archive_readback(
            previous,
            mode="historical",
        ),
    }:
        raise LifecycleEvidenceError("upgrade archive readback differs")


def validate_repeatability_receipt(
    document: dict[str, object],
    contract: EvidenceContract,
    contracts_by_path: dict[str, EvidenceContract],
) -> None:
    if contract.canonical_result_path is None:
        raise LifecycleEvidenceError("repeatability receipt has no result path")
    try:
        result_contract = contracts_by_path[contract.canonical_result_path]
    except KeyError as error:
        raise LifecycleEvidenceError(
            "repeatability receipt references an unknown result"
        ) from error
    expected_result = {
        "fileName": Path(result_contract.relative_path).name,
        "sha256": result_contract.identity.sha256,
        "size": result_contract.identity.size,
    }
    if document.get("canonicalResult") != expected_result:
        raise LifecycleEvidenceError(
            f"{contract.relative_path} canonical result binding differs"
        )
    if document.get("resultBytesEqual") is not True:
        raise LifecycleEvidenceError(
            f"{contract.relative_path} must require byte-identical runs"
        )
    if require_exact_int(
        document.get("runCount"),
        f"{contract.relative_path}.runCount",
    ) != 2:
        raise LifecycleEvidenceError(
            f"{contract.relative_path} must record exactly two runs"
        )
    expected_runs = [
        {
            "ordinal": ordinal,
            "sha256": result_contract.identity.sha256,
            "size": result_contract.identity.size,
            "status": "passed",
        }
        for ordinal in (1, 2)
    ]
    if document.get("runs") != expected_runs:
        raise LifecycleEvidenceError(
            f"{contract.relative_path} run bindings differ"
        )
    if contract.relative_path == UPGRADE_RECEIPT_PATH:
        if document.get("releaseTransition") != {
            "from": RELEASES[23].release_id,
            "to": RELEASES[24].release_id,
        }:
            raise LifecycleEvidenceError(
                "upgrade repeatability release transition differs"
            )
    elif contract.relative_path == ABRUPT_RECEIPT_PATH:
        if document.get("releaseId") != RELEASES[24].release_id:
            raise LifecycleEvidenceError(
                "abrupt repeatability release identity differs"
            )
    else:
        raise LifecycleEvidenceError(
            "repeatability receipt path is not in the closed inventory"
        )


def validate_evidence_document(
    document: dict[str, object],
    contract: EvidenceContract,
    contracts_by_path: dict[str, EvidenceContract] | None = None,
) -> None:
    validate_scalar_field_types(document, label=contract.relative_path)
    require_exact_keys(
        document,
        contract.top_level_keys,
        contract.relative_path,
    )
    if require_exact_int(
        document.get("schemaVersion"),
        f"{contract.relative_path}.schemaVersion",
    ) != contract.schema_version:
        raise LifecycleEvidenceError(
            f"{contract.relative_path} schemaVersion differs"
        )
    if document.get("scope") != contract.scope:
        raise LifecycleEvidenceError(f"{contract.relative_path} scope differs")
    if document.get("status") != "passed":
        raise LifecycleEvidenceError(f"{contract.relative_path} did not pass")
    if document.get("limitations") != list(contract.limitations):
        raise LifecycleEvidenceError(
            f"{contract.relative_path} limitations differ"
        )

    if contract.kind == "build-result":
        validate_build_result(document, contract)
    elif contract.kind == "upgrade-result":
        validate_upgrade_result(document, contract)
    elif contract.kind == "repeatability-receipt":
        validate_repeatability_receipt(
            document,
            contract,
            contracts_by_path
            if contracts_by_path is not None
            else {item.relative_path: item for item in EVIDENCE_CONTRACTS},
        )
    else:
        raise LifecycleEvidenceError(
            f"unsupported evidence contract kind: {contract.kind}"
        )


def validate_evidence_files(
    root: Path,
    contracts: Sequence[EvidenceContract] = EVIDENCE_CONTRACTS,
    *,
    snapshot: RepositorySnapshotReader | None = None,
) -> None:
    if len({contract.relative_path for contract in contracts}) != len(contracts):
        raise LifecycleEvidenceError("evidence contract paths must be unique")
    contracts_by_path = {
        contract.relative_path: contract for contract in contracts
    }
    for contract in contracts:
        payload = require_bound_identity(
            root,
            contract.relative_path,
            contract.identity,
            maximum_bytes=MAXIMUM_JSON_BYTES,
            retain_bytes=True,
            snapshot=snapshot,
        )
        if payload is None:
            raise LifecycleEvidenceError(
                f"evidence bytes were not retained: {contract.relative_path}"
            )
        validate_evidence_document(
            parse_canonical_json(payload, contract.relative_path),
            contract,
            contracts_by_path,
        )


def validate_source_files(
    root: Path,
    contracts: dict[str, ByteIdentity] | None = None,
    *,
    snapshot: RepositorySnapshotReader | None = None,
) -> None:
    canonical_contract = contracts is None or contracts is SOURCE_CONTRACTS
    if contracts is None:
        contracts = SOURCE_CONTRACTS
    if not contracts:
        raise LifecycleEvidenceError("source contract inventory must not be empty")
    if canonical_contract:
        validate_historical_source_snapshot_contract(snapshot)
    for relative_path in sorted(contracts):
        require_bound_identity(
            root,
            (
                source_storage_path(relative_path)
                if canonical_contract
                else relative_path
            ),
            contracts[relative_path],
            maximum_bytes=MAXIMUM_SOURCE_BYTES,
            snapshot=snapshot,
        )


def source_path_for_test_module(module: str) -> str:
    return module.replace(".", "/") + ".py"


def validate_unit_test_inventory(
    modules: Sequence[str] = UNIT_TEST_MODULES,
    source_contracts: dict[str, ByteIdentity] = SOURCE_CONTRACTS,
) -> None:
    if tuple(modules) != UNIT_TEST_MODULES:
        raise LifecycleEvidenceError(
            "focused unit-test inventory differs from the canonical tuple"
        )
    if len(set(modules)) != len(modules) or len(modules) != 12:
        raise LifecycleEvidenceError(
            "focused unit-test inventory must contain 12 unique modules"
        )
    for module in modules:
        if not module.startswith("script.test_"):
            raise LifecycleEvidenceError(
                f"focused unit-test module is outside script tests: {module}"
            )
        lowered = module.lower()
        if any(token in lowered for token in FORBIDDEN_UNIT_TEST_TOKENS):
            raise LifecycleEvidenceError(
                f"focused unit-test module crosses excluded scope: {module}"
            )
        source_path = source_path_for_test_module(module)
        if source_path not in source_contracts:
            raise LifecycleEvidenceError(
                f"focused unit-test source is not byte-bound: {source_path}"
            )


def readback_failures(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    try:
        validate_historical_source_snapshot_contract()
    except (LifecycleEvidenceError, OSError, ValueError) as error:
        return [f"historical source snapshot: {error}"]
    try:
        snapshot = RepositorySnapshotReader(root)
    except (LifecycleEvidenceError, OSError, ValueError) as error:
        return [f"repository snapshot: {error}"]
    try:
        checks: tuple[tuple[str, Callable[[], None]], ...] = (
            (
                "release ledger",
                lambda: validate_ledger(root, snapshot=snapshot),
            ),
            (
                "Build 23 release archive",
                lambda: validate_release_archive(
                    root,
                    RELEASES[23],
                    snapshot=snapshot,
                ),
            ),
            (
                "Build 24 release archive",
                lambda: validate_release_archive(
                    root,
                    RELEASES[24],
                    snapshot=snapshot,
                ),
            ),
            (
                "lifecycle evidence",
                lambda: validate_evidence_files(
                    root,
                    snapshot=snapshot,
                ),
            ),
            (
                "lifecycle sources",
                lambda: validate_source_files(
                    root,
                    snapshot=snapshot,
                ),
            ),
            ("focused unit inventory", validate_unit_test_inventory),
        )
        for label, check in checks:
            try:
                check()
            except (LifecycleEvidenceError, OSError, ValueError) as error:
                failures.append(f"{label}: {error}")
        try:
            snapshot.verify_unchanged()
        except (LifecycleEvidenceError, OSError, ValueError) as error:
            failures.append(f"repository snapshot final readback: {error}")
    finally:
        snapshot.close()
    return failures


def main(arguments: Sequence[str] | None = None) -> int:
    supplied = list(sys.argv[1:] if arguments is None else arguments)
    if supplied:
        print(
            "usage: check_macos_build24_lifecycle_evidence.py",
            file=sys.stderr,
        )
        return 2

    failures = readback_failures()
    if failures:
        print(
            "Build 24 macOS lifecycle evidence readback failed:",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Build 24 macOS lifecycle evidence OK: "
        f"{len(RELEASES)} archives, "
        f"{len(EVIDENCE_CONTRACTS)} result/receipt files, "
        f"{len(SOURCE_CONTRACTS)} source files, "
        f"{len(UNIT_TEST_MODULES)} byte-bound focused unit modules "
        "(not executed)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
