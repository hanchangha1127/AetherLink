#!/usr/bin/env python3
"""Independently validate the bounded Build 24/23/24 readback evidence."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Iterator, Mapping


ROOT = Path(__file__).resolve().parents[1]
RESULT_RELATIVE = Path(
    "dist/lifecycle/macos-packaged-app-build-24-to-23-to-24-"
    "isolated-reverse-version-readback-v1.json"
)
RECEIPT_RELATIVE = Path(
    "dist/lifecycle/macos-packaged-app-build-24-to-23-to-24-"
    "isolated-reverse-version-readback-repeatability-v1.json"
)
RESULT_SHA256 = "dbaa422de18ab37e9f4b92d7e78631fad9719e6c6d41fe30ccb402365267d416"
RESULT_SIZE = 7_859
RECEIPT_SHA256 = "c332a0512f8ac001fa5b81f29dada9e91d9fd441b43b66c0346105295ac749d8"
RECEIPT_SIZE = 1_216
MAXIMUM_CAPTURE_BYTES = 4 * 1_024 * 1_024
EXECUTION_SOURCE_CLOSURE = (
    Path("script/run_macos_isolated_reverse_version_readback_smoke.py"),
    Path("script/run_macos_isolated_upgrade_smoke.py"),
    Path("script/run_macos_clean_home_installed_app_smoke.py"),
    Path("script/run_macos_clean_home_installed_state_recovery_smoke.py"),
    Path("script/run_macos_isolated_uninstall_reinstall_smoke.py"),
    Path("script/run_macos_packaged_app_state_recovery_smoke.py"),
    Path("script/run_macos_packaged_app_lifecycle_smoke.py"),
    Path("script/check_release_version_ledger.py"),
    Path("script/check_release_artifact_archive.py"),
    Path("script/check_release_compliance.py"),
)


class EvidenceError(RuntimeError):
    pass


class DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class FileSpec:
    size: int
    sha256: str
    mode: int
    capture: bool = False


PINNED_FILES: Mapping[Path, FileSpec] = {
    RESULT_RELATIVE: FileSpec(RESULT_SIZE, RESULT_SHA256, 0o600, True),
    RECEIPT_RELATIVE: FileSpec(RECEIPT_SIZE, RECEIPT_SHA256, 0o600, True),
    Path("script/run_macos_isolated_reverse_version_readback_smoke.py"): FileSpec(
        44_003,
        "e22a3e32e0556428f1d0274a75b4bbe93c5f5d28fe1a60607e1537a3db1771b1",
        0o644,
    ),
    Path("script/test_run_macos_isolated_reverse_version_readback_smoke.py"): FileSpec(
        31_118,
        "41aadb2c9e2e961b9934ebac284df0a4f9b60f7b6fa4d02992b50775da47647b",
        0o644,
    ),
    Path("script/run_macos_isolated_upgrade_smoke.py"): FileSpec(
        46_668,
        "abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095",
        0o644,
    ),
    Path("script/run_macos_clean_home_installed_app_smoke.py"): FileSpec(
        35_114,
        "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29",
        0o644,
    ),
    Path("script/run_macos_clean_home_installed_state_recovery_smoke.py"): FileSpec(
        26_367,
        "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a",
        0o644,
    ),
    Path("script/run_macos_isolated_uninstall_reinstall_smoke.py"): FileSpec(
        18_890,
        "36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa",
        0o644,
    ),
    Path("script/run_macos_packaged_app_state_recovery_smoke.py"): FileSpec(
        26_782,
        "4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca",
        0o644,
    ),
    Path("script/run_macos_packaged_app_lifecycle_smoke.py"): FileSpec(
        39_857,
        "3d7ae7ac5b29236babb239769e7e76f6e51b2fc054accb7d53bd88509aa6ee12",
        0o644,
    ),
    Path("script/check_release_version_ledger.py"): FileSpec(
        13_996,
        "b869bb300161937b66ae775d6e742decf6d208db097408d96ffef3d34a4f78f2",
        0o644,
    ),
    Path("script/check_release_artifact_archive.py"): FileSpec(
        159_513,
        "c9a91a55ffd0ffd36442d4b8bb52583fd61838a073b03feea3b2e73644fb8ece",
        0o755,
    ),
    Path("script/check_release_compliance.py"): FileSpec(
        43_859,
        "a12492e12a0c50bf5b4d52b7cf22733f620ebf34734563cf5702410ec17875ae",
        0o644,
    ),
    Path("release/version-ledger.tsv"): FileSpec(
        238,
        "dce3c8615a44c11c7b1cdb505bed1d80d6ea7bdb082c9b714bc9c2ff930d19e0",
        0o644,
        True,
    ),
    Path(
        "dist/releases/aetherlink-1.0.0+23-local-v1/"
        "aetherlink-1.0.0+23-local-v1.manifest.json"
    ): FileSpec(
        15_200,
        "a645819bb0dd985b94289a29cc26b6a344361139ab6ca20a2b7aff9af0a8a16d",
        0o644,
    ),
    Path(
        "dist/releases/aetherlink-1.0.0+23-local-v1/"
        "aetherlink-1.0.0+23-local-v1.zip"
    ): FileSpec(
        166_859_521,
        "b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e",
        0o644,
    ),
    Path(
        "dist/releases/aetherlink-1.0.0+23-local-v1/"
        "aetherlink-1.0.0+23-local-v1.zip.sha256"
    ): FileSpec(
        99,
        "10048a3199b2420140d72b21145ea5bf41d2b564a39842ee2aef2a8d8b12f3d2",
        0o644,
        True,
    ),
    Path(
        "dist/releases/aetherlink-1.0.0+24-local-v1/"
        "aetherlink-1.0.0+24-local-v1.manifest.json"
    ): FileSpec(
        15_200,
        "eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b",
        0o644,
    ),
    Path(
        "dist/releases/aetherlink-1.0.0+24-local-v1/"
        "aetherlink-1.0.0+24-local-v1.zip"
    ): FileSpec(
        166_345_274,
        "104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c",
        0o644,
    ),
    Path(
        "dist/releases/aetherlink-1.0.0+24-local-v1/"
        "aetherlink-1.0.0+24-local-v1.zip.sha256"
    ): FileSpec(
        99,
        "827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882",
        0o644,
        True,
    ),
}


ARCHIVE_SNAPSHOT_EXPECTED = {
    "historical": {
        "aetherlink-1.0.0+23-local-v1.manifest.json": {
            "sha256": "a645819bb0dd985b94289a29cc26b6a344361139ab6ca20a2b7aff9af0a8a16d",
            "size": 15_200,
        },
        "aetherlink-1.0.0+23-local-v1.zip": {
            "sha256": "b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e",
            "size": 166_859_521,
        },
        "aetherlink-1.0.0+23-local-v1.zip.sha256": {
            "sha256": "10048a3199b2420140d72b21145ea5bf41d2b564a39842ee2aef2a8d8b12f3d2",
            "size": 99,
        },
    },
    "current": {
        "aetherlink-1.0.0+24-local-v1.manifest.json": {
            "sha256": "eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b",
            "size": 15_200,
        },
        "aetherlink-1.0.0+24-local-v1.zip": {
            "sha256": "104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c",
            "size": 166_345_274,
        },
        "aetherlink-1.0.0+24-local-v1.zip.sha256": {
            "sha256": "827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882",
            "size": 99,
        },
    },
}


def exact_equal(first: object, second: object) -> bool:
    if type(first) is not type(second):
        return False
    if isinstance(first, dict):
        return (
            isinstance(second, dict)
            and set(first) == set(second)
            and all(exact_equal(first[key], second[key]) for key in first)
        )
    if isinstance(first, list):
        return (
            isinstance(second, list)
            and len(first) == len(second)
            and all(exact_equal(a, b) for a, b in zip(first, second))
        )
    return first == second


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def reject_nonfinite(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def parse_canonical_json(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        text = payload.decode("ascii")
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as error:
        raise EvidenceError(f"{label} is not strict canonical JSON: {error}") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != payload:
        raise EvidenceError(f"{label} is not canonical object JSON")
    return value


def _identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_uid,
        status.st_nlink,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


@contextmanager
def pinned_file_payloads(
    specs: Mapping[Path, FileSpec] = PINNED_FILES,
    *,
    root: Path = ROOT,
) -> Iterator[dict[Path, bytes]]:
    held: dict[Path, tuple[int, os.stat_result, Path, FileSpec]] = {}
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        for relative, spec in specs.items():
            path = root / relative
            absolute = Path(os.path.abspath(path))
            try:
                resolved = path.resolve(strict=True)
            except OSError as error:
                raise EvidenceError(f"missing pinned file {relative}: {error}") from error
            if resolved != absolute:
                raise EvidenceError(f"pinned file uses a symlink ancestor: {relative}")
            try:
                descriptor = os.open(path, flags)
            except OSError as error:
                raise EvidenceError(f"cannot open pinned file {relative}: {error}") from error
            status = os.fstat(descriptor)
            if (
                not stat.S_ISREG(status.st_mode)
                or status.st_uid != os.getuid()
                or status.st_nlink != 1
                or stat.S_IMODE(status.st_mode) != spec.mode
                or status.st_size != spec.size
            ):
                os.close(descriptor)
                raise EvidenceError(f"pinned file identity differs: {relative}")
            held[relative] = (descriptor, status, path, spec)

        captured: dict[Path, bytes] = {}
        for relative, (descriptor, before, _path, spec) in held.items():
            digest = hashlib.sha256()
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
                if spec.capture:
                    if total > MAXIMUM_CAPTURE_BYTES:
                        raise EvidenceError(f"captured file is too large: {relative}")
                    chunks.append(chunk)
            after = os.fstat(descriptor)
            if (
                total != spec.size
                or digest.hexdigest() != spec.sha256
                or _identity(before) != _identity(after)
            ):
                raise EvidenceError(f"pinned file bytes changed: {relative}")
            if spec.capture:
                captured[relative] = b"".join(chunks)

        yield captured

        for relative, (descriptor, before, path, _spec) in held.items():
            after = os.fstat(descriptor)
            try:
                resolved = path.resolve(strict=True)
                final = path.lstat()
            except OSError as error:
                raise EvidenceError(
                    f"pinned file disappeared after read: {relative}: {error}"
                ) from error
            if (
                resolved != Path(os.path.abspath(path))
                or _identity(before) != _identity(after)
                or _identity(before) != _identity(final)
                or stat.S_ISLNK(final.st_mode)
            ):
                raise EvidenceError(f"pinned file identity changed: {relative}")
    finally:
        for descriptor, _before, _path, _spec in held.values():
            os.close(descriptor)


def validate_ledger(payload: bytes) -> None:
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise EvidenceError(f"release ledger is not ASCII: {error}") from error
    expected = ["build_number\tmarketing_version"] + [
        f"{number}\t1.0.0" for number in range(1, 25)
    ]
    if lines != expected or not payload.endswith(b"\n"):
        raise EvidenceError("release ledger is not the exact Build 1-24 lineage")


def validate_checksum_sidecar(
    payload: bytes,
    *,
    release_id: str,
    archive_sha256: str,
) -> None:
    expected = f"{archive_sha256}  {release_id}.zip\n".encode("ascii")
    if payload != expected:
        raise EvidenceError(f"{release_id} checksum sidecar differs")


def validate_result(value: dict[str, object]) -> None:
    expected_keys = {
        "archiveReadback",
        "canary",
        "cleanup",
        "installation",
        "isolation",
        "launchServices",
        "limitations",
        "qualification",
        "releaseSequence",
        "releases",
        "schemaVersion",
        "scope",
        "stateReadback",
        "status",
    }
    if set(value) != expected_keys:
        raise EvidenceError("result top-level schema differs")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise EvidenceError("result schemaVersion differs")
    if value["scope"] != (
        "same-host-per-user-isolated-current-historical-current-"
        "manual-replacement-readback-v1"
    ) or value["status"] != "passed":
        raise EvidenceError("result scope or status differs")

    qualification = {
        "nMinusOneQualificationClaimed": False,
        "productRollbackQualificationClaimed": False,
        "productionPredecessorClaimed": False,
        "securityEvidenceProduced": False,
        "securityQualificationClaimed": False,
        "securityStateInspected": False,
        "supportedUpgradeOrRollbackClaimed": False,
    }
    limitations = [
        "same-host-per-user-temporary-home-only",
        "local-ad-hoc-manual-exact-path-replacement-only",
        "fixed-runtime-chat-canary-readback-only",
        "fixture-initialization-not-supported-state-migration",
        "historical-build-readback-not-declared-production-predecessor",
        "not-updater-dmg-finder-quarantine-or-gatekeeper-evidence",
        "not-signed-notarized-clean-machine-or-cross-host-evidence",
        "not-pairing-keyset-revocation-or-security-state-evidence",
        "not-arbitrary-n-n-minus-one-upgrade-or-product-rollback",
        "failure-is-bounded-observation-failure-not-product-rollback-failure",
        "not-device-provider-network-ui-or-production-release-qualification",
    ]
    sequence = [
        {
            "ordinal": 1,
            "releaseId": "aetherlink-1.0.0+24-local-v1",
            "role": "current-fixture-initialization",
        },
        {
            "ordinal": 2,
            "releaseId": "aetherlink-1.0.0+23-local-v1",
            "role": "historical-readback",
        },
        {
            "ordinal": 3,
            "releaseId": "aetherlink-1.0.0+24-local-v1",
            "role": "current-readback",
        },
    ]
    if not exact_equal(value["qualification"], qualification):
        raise EvidenceError("result qualification boundary differs")
    if not exact_equal(value["limitations"], limitations):
        raise EvidenceError("result limitations differ")
    if not exact_equal(value["releaseSequence"], sequence):
        raise EvidenceError("result release sequence differs")

    expected_archive_readback = {
        label: {
            "currentSourceCompared": False,
            "mode": "historical" if label == "historical" else "archive-only-no-current-source",
            "readbackAndExerciseSameSnapshot": True,
            "snapshotFiles": ARCHIVE_SNAPSHOT_EXPECTED[label],
            "snapshotFilesUnchangedAfterExercise": True,
            "status": "passed",
        }
        for label in ("current", "historical")
    }
    if not exact_equal(value["archiveReadback"], expected_archive_readback):
        raise EvidenceError("result archive readback projection differs")

    expected_canary = {
        "eventID": "packaged-state-recovery-canary-event-v1",
        "eventJsonSha256": "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef",
        "eventJsonSize": 344,
        "legacyJsonlSha256": "0e51fc924836465c4c0921eb3b3709b387f89787aabf2e100c7cff338f0aea2e",
        "legacyJsonlSize": 345,
        "model": "qa:packaged-state-recovery-canary-v1",
        "requestID": "packaged-state-recovery-canary-request-v1",
        "sessionID": "packaged-state-recovery-canary-session-v1",
    }
    if not exact_equal(value["canary"], expected_canary):
        raise EvidenceError("result canary differs")

    expected_cleanup = {
        "appAbsentAfterFinalRemoval": True,
        "applicationSupportCleanupPerformed": False,
        "exactTemporaryAppPathOnly": True,
        "removalCount": 3,
    }
    expected_isolation = {
        "preexistingBundleApplicationsPreserved": True,
        "runtimeIdentityFileOverrideConfigured": True,
        "temporaryCFUserHomeConfigured": True,
    }
    if not exact_equal(value["cleanup"], expected_cleanup):
        raise EvidenceError("result cleanup differs")
    if not exact_equal(value["isolation"], expected_isolation):
        raise EvidenceError("result isolation differs")

    tree_algorithm = "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
    historical_tree = {
        "digestAlgorithm": tree_algorithm,
        "regularFileCount": 10,
        "sha256": "31209251804494f54a699c5c4e8101491f02fca881cf25fba379b88eb493d8a8",
        "totalRegularFileBytes": 21_153_014,
    }
    current_tree = {
        "digestAlgorithm": tree_algorithm,
        "regularFileCount": 10,
        "sha256": "0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff",
        "totalRegularFileBytes": 21_151_910,
    }
    expected_installation = {
        "copyTool": "ditto",
        "historicalTree": historical_tree,
        "initialCurrentTree": current_tree,
        "installedRelativePath": "Applications/AetherLink.app",
        "replacementCount": 2,
        "replacementMethod": "exact-path-remove-then-ditto",
        "restoredCurrentTree": current_tree,
        "staleBundleFilesAbsentAfterEveryReplacement": True,
        "treesDifferAcrossVersions": True,
    }
    if not exact_equal(value["installation"], expected_installation):
        raise EvidenceError("result installation projection differs")

    expected_run = {
        "activationPolicy": 0,
        "executablePathMatched": True,
        "finishedLaunching": True,
        "minimumObservationSeconds": 5.0,
        "newProcessIdentifierDetected": True,
        "observationDeadlineReached": True,
        "terminationAccepted": True,
    }
    expected_launches = {
        "allOwnedProcessesGoneAfterEachRun": True,
        "commandPolicy": "open-new-fresh-background-exact-app-path-captured-recovery-v1",
        "distinctProcessIdentifiers": True,
        "runs": [{**expected_run, "ordinal": ordinal} for ordinal in (1, 2, 3)],
    }
    if not exact_equal(value["launchServices"], expected_launches):
        raise EvidenceError("result launch evidence differs")

    expected_releases = {
        "current": {
            "app": {
                "buildNumber": 24,
                "bundleIdentifier": "dev.aetherlink.companion",
                "executableSha256": "5bf283a6dd3504682cb4aefc9cb1536c7e340f776c90de83cea5a473044890e5",
                "marketingVersion": "1.0.0",
                "uuid": "3FDC3DBC-3A74-3A3B-A87D-03CB432B5D46",
            },
            "archiveSha256": ARCHIVE_SNAPSHOT_EXPECTED["current"]["aetherlink-1.0.0+24-local-v1.zip"]["sha256"],
            "manifestSha256": ARCHIVE_SNAPSHOT_EXPECTED["current"]["aetherlink-1.0.0+24-local-v1.manifest.json"]["sha256"],
            "releaseId": "aetherlink-1.0.0+24-local-v1",
        },
        "historical": {
            "app": {
                "buildNumber": 23,
                "bundleIdentifier": "dev.aetherlink.companion",
                "executableSha256": "346d0a673ba7710b5692dd2fc2dd8543e937b65deae77ad8c281071e107ab55c",
                "marketingVersion": "1.0.0",
                "uuid": "73F610E8-4BBE-3C8D-B28E-434426EAD95B",
            },
            "archiveSha256": ARCHIVE_SNAPSHOT_EXPECTED["historical"]["aetherlink-1.0.0+23-local-v1.zip"]["sha256"],
            "manifestSha256": ARCHIVE_SNAPSHOT_EXPECTED["historical"]["aetherlink-1.0.0+23-local-v1.manifest.json"]["sha256"],
            "releaseId": "aetherlink-1.0.0+23-local-v1",
        },
    }
    if not exact_equal(value["releases"], expected_releases):
        raise EvidenceError("result release identities differ")

    sqlite_record = {
        "eventJsonSha256": expected_canary["eventJsonSha256"],
        "eventJsonSize": 344,
        "integrityCheck": "ok",
        "totalEventCount": 1,
    }
    empty_log = {
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "size": 0,
    }
    migration_observation = {
        "mode": "migration-read-v1",
        "sha256": "558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9",
        "size": 70,
        "status": "passed",
    }
    readback_observation = {
        "mode": "sqlite-readback-v1",
        "sha256": "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07",
        "size": 71,
        "status": "passed",
    }
    expected_state = {
        "applicationSupportPreservedAcrossManualReplacement": True,
        "auxiliarySQLite": [
            {"filename": "runtime-document-index.sqlite", "integrityCheck": "ok"},
            {"filename": "runtime-model-pull-approvals.sqlite", "integrityCheck": "ok"},
        ],
        "bytesAndModesUnchangedAcrossManualReplacement": True,
        "canaryExactlyOnceAtEveryStage": True,
        "expectedSQLiteFiles": [
            "runtime-chat-events.sqlite",
            "runtime-document-index.sqlite",
            "runtime-model-pull-approvals.sqlite",
        ],
        "fixtureInitializationObservation": migration_observation,
        "fixtureInitializationSQLite": sqlite_record,
        "historicalObservation": readback_observation,
        "historicalSQLite": sqlite_record,
        "legacyAbsentAfterFixtureInitialization": True,
        "legacyFixturePreservedUnchanged": True,
        "restoredCurrentObservation": readback_observation,
        "restoredCurrentSQLite": sqlite_record,
        "runtimeIdentityFilePresent": True,
        "stderr": {
            "fixtureInitialization": empty_log,
            "historicalReadback": empty_log,
            "restoredCurrentReadback": empty_log,
        },
    }
    if not exact_equal(value["stateReadback"], expected_state):
        raise EvidenceError("result state readback differs")


def validate_receipt(value: dict[str, object]) -> None:
    expected = {
        "canonicalResult": {
            "fileName": RESULT_RELATIVE.name,
            "sha256": RESULT_SHA256,
            "size": RESULT_SIZE,
        },
        "limitations": [
            "same-host-two-run-repeatability-only",
            "manual-local-ad-hoc-replacement-not-an-updater",
            "historical-build-is-not-a-declared-production-predecessor",
            "not-arbitrary-n-n-minus-one-or-product-rollback-evidence",
            "not-security-device-network-signed-distribution-or-production-evidence",
        ],
        "qualification": {
            "nMinusOneQualificationClaimed": False,
            "productRollbackQualificationClaimed": False,
            "securityEvidenceProduced": False,
            "securityQualificationClaimed": False,
        },
        "releaseSequence": [
            "aetherlink-1.0.0+24-local-v1",
            "aetherlink-1.0.0+23-local-v1",
            "aetherlink-1.0.0+24-local-v1",
        ],
        "resultBytesEqual": True,
        "runCount": 2,
        "runs": [
            {
                "ordinal": ordinal,
                "sha256": RESULT_SHA256,
                "size": RESULT_SIZE,
                "status": "passed",
            }
            for ordinal in (1, 2)
        ],
        "schemaVersion": 1,
        "scope": (
            "same-host-per-user-isolated-current-historical-current-"
            "manual-replacement-readback-repeatability-v1"
        ),
        "status": "passed",
    }
    if not exact_equal(value, expected):
        raise EvidenceError("repeatability receipt differs")


def validate_evidence_payloads(result_payload: bytes, receipt_payload: bytes) -> None:
    result = parse_canonical_json(result_payload, label="canonical result")
    receipt = parse_canonical_json(receipt_payload, label="repeatability receipt")
    validate_result(result)
    validate_receipt(receipt)
    result_identity = {
        "fileName": RESULT_RELATIVE.name,
        "sha256": hashlib.sha256(result_payload).hexdigest(),
        "size": len(result_payload),
    }
    if not exact_equal(receipt["canonicalResult"], result_identity):
        raise EvidenceError("receipt does not bind the supplied result bytes")


def check() -> None:
    missing_sources = [
        path for path in EXECUTION_SOURCE_CLOSURE if path not in PINNED_FILES
    ]
    if missing_sources:
        raise EvidenceError(
            f"execution source closure is not fully pinned: {missing_sources!r}"
        )
    with pinned_file_payloads() as payloads:
        validate_ledger(payloads[Path("release/version-ledger.tsv")])
        validate_checksum_sidecar(
            payloads[
                Path(
                    "dist/releases/aetherlink-1.0.0+23-local-v1/"
                    "aetherlink-1.0.0+23-local-v1.zip.sha256"
                )
            ],
            release_id="aetherlink-1.0.0+23-local-v1",
            archive_sha256=ARCHIVE_SNAPSHOT_EXPECTED["historical"]["aetherlink-1.0.0+23-local-v1.zip"]["sha256"],
        )
        validate_checksum_sidecar(
            payloads[
                Path(
                    "dist/releases/aetherlink-1.0.0+24-local-v1/"
                    "aetherlink-1.0.0+24-local-v1.zip.sha256"
                )
            ],
            release_id="aetherlink-1.0.0+24-local-v1",
            archive_sha256=ARCHIVE_SNAPSHOT_EXPECTED["current"]["aetherlink-1.0.0+24-local-v1.zip"]["sha256"],
        )
        validate_evidence_payloads(
            payloads[RESULT_RELATIVE],
            payloads[RECEIPT_RELATIVE],
        )


def main() -> int:
    try:
        check()
    except (EvidenceError, OSError) as error:
        print(f"macOS reverse-version evidence check failed: {error}", file=sys.stderr)
        return 1
    print(
        "macOS reverse-version evidence OK: Build 24 -> 23 -> 24; "
        "runs=2; productRollbackQualificationClaimed=false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
