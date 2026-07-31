#!/usr/bin/env python3
"""Read back the bounded Build 24 idle-resource evidence without executing it."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SHA256_HEX = frozenset("0123456789abcdef")
CHUNK_BYTES = 1024 * 1024
RESULT_RELATIVE_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-24-idle-resource-stability-v1.json"
)
RELEASE_ID = "aetherlink-1.0.0+24-local-v1"
RELEASE_DIRECTORY = f"dist/releases/{RELEASE_ID}"
ARCHIVE_NAME = f"{RELEASE_ID}.zip"
MANIFEST_NAME = f"{RELEASE_ID}.manifest.json"
CHECKSUM_NAME = f"{ARCHIVE_NAME}.sha256"
ARCHIVE_RELATIVE_PATH = f"{RELEASE_DIRECTORY}/{ARCHIVE_NAME}"
MANIFEST_RELATIVE_PATH = f"{RELEASE_DIRECTORY}/{MANIFEST_NAME}"
CHECKSUM_RELATIVE_PATH = f"{RELEASE_DIRECTORY}/{CHECKSUM_NAME}"

RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = "same-host-per-user-build24-idle-resource-stability-v1"
WARMUP_MILLISECONDS = 60_000
OBSERVATION_MILLISECONDS = 600_000
SAMPLE_INTERVAL_MILLISECONDS = 5_000
SAMPLE_COUNT = 120
SAMPLE_LATENESS_LIMIT_MILLISECONDS = 1_000
BASELINE_WINDOW_SAMPLE_COUNT = 12
FINAL_WINDOW_SAMPLE_COUNT = 12

APP_TREE = {
    "digestAlgorithm": (
        "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
    ),
    "regularFileCount": 10,
    "sha256": (
        "0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff"
    ),
    "totalRegularFileBytes": 21_151_910,
}
ARTIFACT = {
    "appTree": APP_TREE,
    "buildNumber": 24,
    "bundleIdentifier": "dev.aetherlink.companion",
    "executableMode": 493,
    "executableSha256": (
        "5bf283a6dd3504682cb4aefc9cb1536c7e340f776c90de83cea5a473044890e5"
    ),
    "executableSize": 18_592_368,
    "marketingVersion": "1.0.0",
    "uuid": "3FDC3DBC-3A74-3A3B-A87D-03CB432B5D46",
}
LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "single-direct-owned-child-idle-observation-only",
    "sixty-second-warmup-and-ten-minute-observation-only",
    "network-denied-and-writes-confined-to-temporary-root",
    "libproc-resource-samples-are-point-in-time-nonatomic-observations",
    "local-regression-budgets-not-performance-sla-or-capacity-evidence",
    "single-recorded-run-not-repeatability-or-long-soak-evidence",
    "no-signing-or-signature-verification-performed",
    (
        "not-install-upgrade-uninstall-reinstall-recovery-crash-or-"
        "rollback-evidence"
    ),
    (
        "not-load-provider-device-ui-accessibility-production-or-"
        "security-evidence"
    ),
)


class IdleResourceEvidenceError(RuntimeError):
    """Raised when the retained evidence fails its closed contract."""


@dataclass(frozen=True)
class ByteIdentity:
    size: int
    sha256: str


@dataclass(frozen=True)
class HeldDirectory:
    file_descriptor: int
    initial_stat: os.stat_result
    relative_parts: tuple[str, ...]


@dataclass(frozen=True)
class HeldFile:
    file_descriptor: int
    initial_stat: os.stat_result
    relative_path: str
    parent_parts: tuple[str, ...]
    name: str


def identity(size: int, sha256: str) -> ByteIdentity:
    if type(size) is not int or size < 0:
        raise ValueError("identity size must be an exact non-negative integer")
    if (
        type(sha256) is not str
        or len(sha256) != 64
        or any(character not in SHA256_HEX for character in sha256)
    ):
        raise ValueError("identity SHA-256 must be lowercase hexadecimal")
    return ByteIdentity(size=size, sha256=sha256)


TARGET_IDENTITIES = {
    ARCHIVE_RELATIVE_PATH: identity(
        166_345_274,
        "104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c",
    ),
    MANIFEST_RELATIVE_PATH: identity(
        15_200,
        "eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b",
    ),
    CHECKSUM_RELATIVE_PATH: identity(
        99,
        "827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882",
    ),
    RESULT_RELATIVE_PATH: identity(
        22_534,
        "07d28a073746731241932681630014647ad452e382afd6728938daacb39e167f",
    ),
    "release/version-ledger.tsv": identity(
        238,
        "dce3c8615a44c11c7b1cdb505bed1d80d6ea7bdb082c9b714bc9c2ff930d19e0",
    ),
    "script/check_release_version_ledger.py": identity(
        13_996,
        "b869bb300161937b66ae775d6e742decf6d208db097408d96ffef3d34a4f78f2",
    ),
    "script/run_macos_packaged_app_lifecycle_smoke.py": identity(
        39_857,
        "3d7ae7ac5b29236babb239769e7e76f6e51b2fc054accb7d53bd88509aa6ee12",
    ),
    "script/run_macos_packaged_app_state_recovery_smoke.py": identity(
        26_782,
        "4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca",
    ),
    "script/run_macos_clean_home_installed_app_smoke.py": identity(
        35_114,
        "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29",
    ),
    "script/run_macos_clean_home_installed_state_recovery_smoke.py": identity(
        26_367,
        "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a",
    ),
    "script/run_macos_isolated_uninstall_reinstall_smoke.py": identity(
        18_890,
        "36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa",
    ),
    "script/run_macos_isolated_upgrade_smoke.py": identity(
        46_668,
        "abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095",
    ),
    "script/run_macos_local_dmg_install_smoke.py": identity(
        32_324,
        "e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb",
    ),
    "script/run_macos_local_dmg_install_smoke_v2.py": identity(
        12_962,
        "515de26546ba97c6879cad1fdf62cda6f3dcbf24a668804955f95e1755d1f374",
    ),
    "script/run_macos_build24_idle_resource_stability_smoke.py": identity(
        45_998,
        "073e58afa67228d6c208186d8ddca790b763a9c0a7acee9d5a681ff1f22801a9",
    ),
    "script/test_run_macos_build24_idle_resource_stability_smoke.py": identity(
        32_632,
        "df8a04a0e46e7ef0cc10a1f5dc29f3f8f9763e960995427304a7ccd93a2e8e4b",
    ),
}
PAYLOAD_PATHS = frozenset(TARGET_IDENTITIES) - {ARCHIVE_RELATIVE_PATH}

SNAPSHOT_FILES = {
    MANIFEST_NAME: {
        "sha256": TARGET_IDENTITIES[MANIFEST_RELATIVE_PATH].sha256,
        "size": TARGET_IDENTITIES[MANIFEST_RELATIVE_PATH].size,
    },
    ARCHIVE_NAME: {
        "sha256": TARGET_IDENTITIES[ARCHIVE_RELATIVE_PATH].sha256,
        "size": TARGET_IDENTITIES[ARCHIVE_RELATIVE_PATH].size,
    },
    CHECKSUM_NAME: {
        "sha256": TARGET_IDENTITIES[CHECKSUM_RELATIVE_PATH].sha256,
        "size": TARGET_IDENTITIES[CHECKSUM_RELATIVE_PATH].size,
    },
}

METRIC_CONTRACTS = {
    "openFileDescriptors": ("openFileDescriptorCount", 2, 8),
    "residentBytes": ("residentBytes", 33_554_432, 134_217_728),
    "threads": ("threadCount", 2, 8),
}
METRIC_SUMMARY_KEYS = {
    "baselineUpperMedian",
    "finalDelta",
    "finalDeltaLimit",
    "finalUpperMedian",
    "maximum",
    "passed",
    "peakDelta",
    "peakDeltaLimit",
}


def stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def normalized_relative_parts(relative_path: str) -> tuple[str, ...]:
    if type(relative_path) is not str or not relative_path:
        raise IdleResourceEvidenceError("target path must be a non-empty string")
    path = PurePosixPath(relative_path)
    parts = path.parts
    if (
        path.is_absolute()
        or not parts
        or any(part in ("", ".", "..") for part in parts)
        or str(path) != relative_path
    ):
        raise IdleResourceEvidenceError(
            f"target path is not a normalized repository path: {relative_path}"
        )
    return parts


class RepositorySnapshot:
    def __init__(
        self,
        root: Path,
        contracts: dict[str, ByteIdentity],
    ) -> None:
        if type(contracts) is not dict or not contracts:
            raise IdleResourceEvidenceError(
                "snapshot contracts must be a non-empty exact dictionary"
            )
        self.root = root
        self.contracts = dict(contracts)
        self.directories: dict[tuple[str, ...], HeldDirectory] = {}
        self.files: dict[str, HeldFile] = {}

    def open_all(self) -> None:
        if self.directories or self.files:
            raise IdleResourceEvidenceError("repository snapshot is already open")
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        root_fd = os.open(str(self.root), flags)
        root_stat = os.fstat(root_fd)
        if not stat.S_ISDIR(root_stat.st_mode):
            os.close(root_fd)
            raise IdleResourceEvidenceError(
                "repository root is not a physical directory"
            )
        self.directories[()] = HeldDirectory(root_fd, root_stat, ())
        try:
            for relative_path in sorted(self.contracts):
                self._open_file(relative_path)
        except BaseException:
            self.close()
            raise

    def _ensure_directory(
        self,
        relative_parts: tuple[str, ...],
    ) -> HeldDirectory:
        existing = self.directories.get(relative_parts)
        if existing is not None:
            return existing
        parent = self._ensure_directory(relative_parts[:-1])
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        file_descriptor = os.open(
            relative_parts[-1],
            flags,
            dir_fd=parent.file_descriptor,
        )
        directory_stat = os.fstat(file_descriptor)
        if not stat.S_ISDIR(directory_stat.st_mode):
            os.close(file_descriptor)
            raise IdleResourceEvidenceError(
                "repository target parent is not a physical directory"
            )
        held = HeldDirectory(
            file_descriptor,
            directory_stat,
            relative_parts,
        )
        self.directories[relative_parts] = held
        return held

    def _open_file(self, relative_path: str) -> None:
        parts = normalized_relative_parts(relative_path)
        parent_parts = parts[:-1]
        parent = self._ensure_directory(parent_parts)
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        file_descriptor = os.open(
            parts[-1],
            flags,
            dir_fd=parent.file_descriptor,
        )
        file_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            os.close(file_descriptor)
            raise IdleResourceEvidenceError(
                f"target is not a physical regular file: {relative_path}"
            )
        self.files[relative_path] = HeldFile(
            file_descriptor,
            file_stat,
            relative_path,
            parent_parts,
            parts[-1],
        )

    def read_all(self) -> dict[str, bytes]:
        if set(self.files) != set(self.contracts):
            raise IdleResourceEvidenceError(
                "held target inventory differs from the fixed contract"
            )
        payloads: dict[str, bytes] = {}
        for relative_path in sorted(self.files):
            held = self.files[relative_path]
            expected = self.contracts[relative_path]
            before = os.fstat(held.file_descriptor)
            if stat_identity(before) != stat_identity(held.initial_stat):
                raise IdleResourceEvidenceError(
                    f"target changed before readback: {relative_path}"
                )
            if before.st_size != expected.size:
                raise IdleResourceEvidenceError(
                    f"target size differs for {relative_path}"
                )
            os.lseek(held.file_descriptor, 0, os.SEEK_SET)
            digest = hashlib.sha256()
            chunks: list[bytes] | None = (
                None if relative_path == ARCHIVE_RELATIVE_PATH else []
            )
            total = 0
            while True:
                chunk = os.read(held.file_descriptor, CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > expected.size:
                    raise IdleResourceEvidenceError(
                        f"target grew during readback: {relative_path}"
                    )
                digest.update(chunk)
                if chunks is not None:
                    chunks.append(chunk)
            after = os.fstat(held.file_descriptor)
            if stat_identity(after) != stat_identity(before):
                raise IdleResourceEvidenceError(
                    f"target changed during readback: {relative_path}"
                )
            actual_sha256 = digest.hexdigest()
            if total != expected.size or actual_sha256 != expected.sha256:
                raise IdleResourceEvidenceError(
                    f"target byte identity differs for {relative_path}: "
                    f"{total} bytes SHA-256 {actual_sha256}"
                )
            if chunks is not None:
                payloads[relative_path] = b"".join(chunks)
        return payloads

    def verify_graph(self) -> None:
        root_path_stat = os.stat(self.root, follow_symlinks=False)
        root_held = self.directories[()]
        if (
            not stat.S_ISDIR(root_path_stat.st_mode)
            or stat_identity(root_path_stat)
            != stat_identity(root_held.initial_stat)
            or stat_identity(os.fstat(root_held.file_descriptor))
            != stat_identity(root_held.initial_stat)
        ):
            raise IdleResourceEvidenceError(
                "repository root identity changed during readback"
            )
        for parts, held in sorted(
            self.directories.items(),
            key=lambda item: (len(item[0]), item[0]),
        ):
            if not parts:
                continue
            parent = self.directories[parts[:-1]]
            entry_stat = os.stat(
                parts[-1],
                dir_fd=parent.file_descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(entry_stat.st_mode)
                or stat_identity(entry_stat)
                != stat_identity(held.initial_stat)
                or stat_identity(os.fstat(held.file_descriptor))
                != stat_identity(held.initial_stat)
            ):
                raise IdleResourceEvidenceError(
                    "repository directory graph changed during readback"
                )
        for relative_path, held in sorted(self.files.items()):
            parent = self.directories[held.parent_parts]
            entry_stat = os.stat(
                held.name,
                dir_fd=parent.file_descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(entry_stat.st_mode)
                or stat_identity(entry_stat)
                != stat_identity(held.initial_stat)
                or stat_identity(os.fstat(held.file_descriptor))
                != stat_identity(held.initial_stat)
            ):
                raise IdleResourceEvidenceError(
                    f"target path changed during readback: {relative_path}"
                )

    def close(self) -> None:
        for held in tuple(self.files.values()):
            try:
                os.close(held.file_descriptor)
            except OSError:
                pass
        self.files.clear()
        for _, held in sorted(
            self.directories.items(),
            key=lambda item: (len(item[0]), item[0]),
            reverse=True,
        ):
            try:
                os.close(held.file_descriptor)
            except OSError:
                pass
        self.directories.clear()


def duplicate_rejecting_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IdleResourceEvidenceError(
                f"JSON contains duplicate object key {key!r}"
            )
        result[key] = value
    return result


def reject_json_float(token: str) -> object:
    raise IdleResourceEvidenceError(
        f"JSON floating-point value is forbidden: {token}"
    )


def reject_json_constant(token: str) -> object:
    raise IdleResourceEvidenceError(
        f"JSON non-finite value is forbidden: {token}"
    )


def canonical_json_bytes(
    value: object,
    *,
    ensure_ascii: bool = False,
) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=ensure_ascii,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as error:
        raise IdleResourceEvidenceError(
            f"value cannot be encoded as canonical JSON: {error}"
        ) from error


def parse_canonical_json(
    payload: bytes,
    label: str,
    *,
    ensure_ascii: bool = False,
) -> object:
    if type(payload) is not bytes:
        raise IdleResourceEvidenceError(f"{label} payload must be exact bytes")
    try:
        text = payload.decode("utf-8")
    except UnicodeError as error:
        raise IdleResourceEvidenceError(
            f"{label} is not valid UTF-8"
        ) from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=duplicate_rejecting_object,
            parse_float=reject_json_float,
            parse_constant=reject_json_constant,
        )
    except IdleResourceEvidenceError:
        raise
    except (TypeError, ValueError) as error:
        raise IdleResourceEvidenceError(
            f"{label} is not valid JSON: {error}"
        ) from error
    if canonical_json_bytes(value, ensure_ascii=ensure_ascii) != payload:
        raise IdleResourceEvidenceError(
            f"{label} is not canonical JSON"
        )
    return value


def exact_json_value_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        left_mapping = left
        right_mapping = right
        if (
            any(type(key) is not str for key in left_mapping)
            or any(type(key) is not str for key in right_mapping)
            or set(left_mapping) != set(right_mapping)
        ):
            return False
        return all(
            exact_json_value_equal(
                left_mapping[key],
                right_mapping[key],
            )
            for key in left_mapping
        )
    if type(left) is list:
        left_items = left
        right_items = right
        return len(left_items) == len(right_items) and all(
            exact_json_value_equal(left_item, right_item)
            for left_item, right_item in zip(left_items, right_items)
        )
    return left == right


def require_closed_dict(
    value: object,
    expected_keys: set[str],
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected_keys:
        raise IdleResourceEvidenceError(
            f"{label} must have the exact closed schema "
            f"{sorted(expected_keys)!r}"
        )
    if any(type(key) is not str for key in value):
        raise IdleResourceEvidenceError(
            f"{label} keys must be exact strings"
        )
    return value


def require_exact(value: object, expected: object, label: str) -> None:
    if not exact_json_value_equal(value, expected):
        raise IdleResourceEvidenceError(f"{label} differs from the contract")


def require_nonempty_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise IdleResourceEvidenceError(
            f"{label} must be a non-empty exact string"
        )
    return value


def require_exact_int(
    value: object,
    label: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        raise IdleResourceEvidenceError(
            f"{label} must be an exact integer"
        )
    if minimum is not None and value < minimum:
        raise IdleResourceEvidenceError(f"{label} is below its minimum")
    if maximum is not None and value > maximum:
        raise IdleResourceEvidenceError(f"{label} exceeds its maximum")
    return value


def upper_median(values: Sequence[int]) -> int:
    if not values or any(type(value) is not int for value in values):
        raise IdleResourceEvidenceError(
            "upper median requires exact integer samples"
        )
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def recompute_metric(
    values: Sequence[int],
    *,
    final_delta_limit: int,
    peak_delta_limit: int,
) -> dict[str, object]:
    if (
        len(values) != SAMPLE_COUNT
        or any(type(value) is not int or value <= 0 for value in values)
    ):
        raise IdleResourceEvidenceError(
            "metric requires exactly 120 positive exact integer samples"
        )
    baseline = upper_median(values[:BASELINE_WINDOW_SAMPLE_COUNT])
    final = upper_median(values[-FINAL_WINDOW_SAMPLE_COUNT:])
    maximum = max(values)
    final_delta = final - baseline
    peak_delta = maximum - baseline
    passed = (
        final_delta <= final_delta_limit
        and peak_delta <= peak_delta_limit
    )
    return {
        "baselineUpperMedian": baseline,
        "finalDelta": final_delta,
        "finalDeltaLimit": final_delta_limit,
        "finalUpperMedian": final,
        "maximum": maximum,
        "passed": passed,
        "peakDelta": peak_delta,
        "peakDeltaLimit": peak_delta_limit,
    }


def validate_samples_and_summary(
    run: dict[str, object],
) -> None:
    samples = run["samples"]
    if type(samples) is not list or len(samples) != SAMPLE_COUNT:
        raise IdleResourceEvidenceError(
            "measurement run must retain exactly 120 samples"
        )
    sample_keys = {
        "observedLatenessMilliseconds",
        "openFileDescriptorCount",
        "ordinal",
        "residentBytes",
        "targetElapsedMilliseconds",
        "threadCount",
    }
    for ordinal, sample_value in enumerate(samples, start=1):
        sample = require_closed_dict(
            sample_value,
            sample_keys,
            f"sample {ordinal}",
        )
        if require_exact_int(sample["ordinal"], "sample ordinal") != ordinal:
            raise IdleResourceEvidenceError("sample ordinal sequence differs")
        target = require_exact_int(
            sample["targetElapsedMilliseconds"],
            "sample target elapsed milliseconds",
        )
        if target != ordinal * SAMPLE_INTERVAL_MILLISECONDS:
            raise IdleResourceEvidenceError("sample target schedule differs")
        require_exact_int(
            sample["observedLatenessMilliseconds"],
            "sample observed lateness",
            minimum=0,
            maximum=SAMPLE_LATENESS_LIMIT_MILLISECONDS,
        )
        for field in (
            "openFileDescriptorCount",
            "residentBytes",
            "threadCount",
        ):
            require_exact_int(
                sample[field],
                f"sample {field}",
                minimum=1,
            )

    observed_lateness = [
        sample["observedLatenessMilliseconds"]  # type: ignore[misc]
        for sample in samples
    ]
    retained_maximum_lateness = require_exact_int(
        run["maximumObservedLatenessMilliseconds"],
        "maximum observed lateness",
        minimum=0,
        maximum=SAMPLE_LATENESS_LIMIT_MILLISECONDS,
    )
    if retained_maximum_lateness != max(observed_lateness):
        raise IdleResourceEvidenceError(
            "maximum observed lateness differs from raw samples"
        )

    summary = require_closed_dict(
        run["summary"],
        set(METRIC_CONTRACTS),
        "measurement summary",
    )
    for metric_name, (
        sample_field,
        final_limit,
        peak_limit,
    ) in METRIC_CONTRACTS.items():
        values = [sample[sample_field] for sample in samples]  # type: ignore[misc]
        recomputed = recompute_metric(
            values,
            final_delta_limit=final_limit,
            peak_delta_limit=peak_limit,
        )
        retained = require_closed_dict(
            summary[metric_name],
            METRIC_SUMMARY_KEYS,
            f"{metric_name} summary",
        )
        if not exact_json_value_equal(recomputed, retained):
            raise IdleResourceEvidenceError(
                f"{metric_name} summary differs from raw samples"
            )
        if retained["passed"] is not True:
            raise IdleResourceEvidenceError(
                f"{metric_name} exceeded its fixed regression budget"
            )


def validate_result_document(value: object) -> dict[str, object]:
    document = require_closed_dict(
        value,
        {
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
            "status",
        },
        "idle resource result",
    )
    require_exact(
        document["schemaVersion"],
        RESULT_SCHEMA_VERSION,
        "result schema version",
    )
    require_exact(document["scope"], RESULT_SCOPE, "result scope")
    require_exact(document["status"], "passed", "result status")
    require_exact(
        document["limitations"],
        list(LIMITATIONS),
        "result limitations",
    )

    archive_readback = require_closed_dict(
        document["archiveReadback"],
        {
            "currentSourceCompared",
            "mode",
            "readbackAndExerciseSameSnapshot",
            "signatureVerificationPerformed",
            "snapshotFiles",
            "snapshotFilesUnchangedAfterExercise",
            "status",
        },
        "archive readback",
    )
    require_exact(
        archive_readback,
        {
            "currentSourceCompared": False,
            "mode": (
                "fixed-identity-snapshot-no-current-source-"
                "no-signature-check"
            ),
            "readbackAndExerciseSameSnapshot": True,
            "signatureVerificationPerformed": False,
            "snapshotFiles": SNAPSHOT_FILES,
            "snapshotFilesUnchangedAfterExercise": True,
            "status": "passed",
        },
        "archive readback",
    )
    require_exact(document["artifact"], ARTIFACT, "artifact")
    require_exact(
        document["cleanup"],
        {
            "ownedChildOnly": True,
            "preexistingApplicationsPreserved": True,
            "temporaryRootRemovedBeforePublication": True,
        },
        "cleanup",
    )

    environment = require_closed_dict(
        document["environment"],
        {
            "architecture",
            "logicalCpuCount",
            "macOSVersion",
            "pageSizeBytes",
        },
        "environment",
    )
    require_nonempty_string(environment["architecture"], "architecture")
    require_nonempty_string(environment["macOSVersion"], "macOS version")
    require_exact_int(
        environment["logicalCpuCount"],
        "logical CPU count",
        minimum=1,
    )
    require_exact_int(
        environment["pageSizeBytes"],
        "page size",
        minimum=1,
    )
    require_exact(
        document["isolation"],
        {
            "afInetBindDeniedByPreflight": True,
            "networkDenied": True,
            "nonTemporaryWriteDeniedByPreflight": True,
            "profile": (
                "allow-default-deny-network-and-non-temp-writes-v1"
            ),
            "sandboxed": True,
            "standardStreams": "devnull",
            "temporaryCFUserHomeConfigured": True,
        },
        "isolation",
    )

    measurement = require_closed_dict(
        document["measurement"],
        {
            "api",
            "baselineWindowSampleCount",
            "finalWindowSampleCount",
            "intervalMilliseconds",
            "observationMilliseconds",
            "run",
            "sampleCount",
            "sampleLatenessLimitMilliseconds",
            "status",
            "warmupMilliseconds",
        },
        "measurement",
    )
    expected_measurement_fields = {
        "api": "macos-libproc-proc-pidinfo-v1",
        "baselineWindowSampleCount": BASELINE_WINDOW_SAMPLE_COUNT,
        "finalWindowSampleCount": FINAL_WINDOW_SAMPLE_COUNT,
        "intervalMilliseconds": SAMPLE_INTERVAL_MILLISECONDS,
        "observationMilliseconds": OBSERVATION_MILLISECONDS,
        "sampleCount": SAMPLE_COUNT,
        "sampleLatenessLimitMilliseconds": (
            SAMPLE_LATENESS_LIMIT_MILLISECONDS
        ),
        "status": "passed",
        "warmupMilliseconds": WARMUP_MILLISECONDS,
    }
    for field, expected in expected_measurement_fields.items():
        require_exact(measurement[field], expected, f"measurement {field}")

    run = require_closed_dict(
        measurement["run"],
        {
            "activationPolicy",
            "appKitProcessAbsentAfterReap",
            "exitCode",
            "finishedLaunching",
            "gracefulTerminationAccepted",
            "maximumObservedLatenessMilliseconds",
            "ownedChildProcess",
            "processIdentifierRetained",
            "processReaped",
            "samples",
            "summary",
        },
        "measurement run",
    )
    for field, expected in {
        "activationPolicy": 0,
        "appKitProcessAbsentAfterReap": True,
        "exitCode": 0,
        "finishedLaunching": True,
        "gracefulTerminationAccepted": True,
        "ownedChildProcess": True,
        "processIdentifierRetained": False,
        "processReaped": True,
    }.items():
        require_exact(run[field], expected, f"measurement run {field}")
    validate_samples_and_summary(run)

    process = require_closed_dict(
        document["process"],
        {
            "launchMethod",
            "preexistingApplicationCount",
            "preexistingApplicationsUsedAsTerminationTargets",
            "rawProcessIdentifierRetained",
        },
        "process",
    )
    require_exact(
        process["launchMethod"],
        "sandbox-exec-direct-owned-child-v1",
        "process launch method",
    )
    require_exact_int(
        process["preexistingApplicationCount"],
        "preexisting application count",
        minimum=0,
    )
    require_exact(
        process["preexistingApplicationsUsedAsTerminationTargets"],
        False,
        "preexisting application termination target flag",
    )
    require_exact(
        process["rawProcessIdentifierRetained"],
        False,
        "raw PID retention flag",
    )
    require_exact(
        document["release"],
        {
            "archiveSha256": TARGET_IDENTITIES[
                ARCHIVE_RELATIVE_PATH
            ].sha256,
            "manifestSha256": TARGET_IDENTITIES[
                MANIFEST_RELATIVE_PATH
            ].sha256,
            "releaseId": RELEASE_ID,
        },
        "release",
    )
    require_exact(
        document["repeatability"],
        {
            "performed": False,
            "reason": "single-live-resource-observation-v1",
        },
        "repeatability",
    )
    return document


def validate_result_bytes(
    payload: bytes,
    *,
    enforce_identity: bool = True,
) -> dict[str, object]:
    if enforce_identity:
        expected = TARGET_IDENTITIES[RESULT_RELATIVE_PATH]
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if len(payload) != expected.size or actual_sha256 != expected.sha256:
            raise IdleResourceEvidenceError(
                "idle resource result byte identity differs"
            )
    value = parse_canonical_json(payload, "idle resource result")
    return validate_result_document(value)


def validate_release_payloads(payloads: dict[str, bytes]) -> None:
    required = {
        MANIFEST_RELATIVE_PATH,
        CHECKSUM_RELATIVE_PATH,
        "release/version-ledger.tsv",
    }
    if not required.issubset(payloads):
        raise IdleResourceEvidenceError(
            "release payload inventory is incomplete"
        )
    expected_ledger = (
        "build_number\tmarketing_version\n"
        + "".join(f"{build}\t1.0.0\n" for build in range(1, 25))
    ).encode("utf-8")
    if payloads["release/version-ledger.tsv"] != expected_ledger:
        raise IdleResourceEvidenceError(
            "terminal release ledger semantics differ"
        )
    expected_checksum = (
        f"{TARGET_IDENTITIES[ARCHIVE_RELATIVE_PATH].sha256}  "
        f"{ARCHIVE_NAME}\n"
    ).encode("utf-8")
    if payloads[CHECKSUM_RELATIVE_PATH] != expected_checksum:
        raise IdleResourceEvidenceError(
            "Build 24 checksum sidecar semantics differ"
        )
    manifest_value = parse_canonical_json(
        payloads[MANIFEST_RELATIVE_PATH],
        "Build 24 manifest",
        ensure_ascii=True,
    )
    manifest = require_closed_dict(
        manifest_value,
        {
            "archive",
            "channel",
            "compliance",
            "dependencyLocking",
            "ledger",
            "members",
            "platforms",
            "product",
            "release",
            "schemaVersion",
            "source",
            "toolchains",
        },
        "Build 24 manifest",
    )
    require_exact(
        manifest["release"],
        {
            "buildNumber": 24,
            "marketingVersion": "1.0.0",
            "releaseId": RELEASE_ID,
        },
        "manifest release",
    )
    ledger_identity = TARGET_IDENTITIES["release/version-ledger.tsv"]
    require_exact(
        manifest["ledger"],
        {
            "path": "release/version-ledger.tsv",
            "sha256": ledger_identity.sha256,
            "size": ledger_identity.size,
        },
        "manifest ledger",
    )


def readback(root: Path = ROOT) -> dict[str, object]:
    snapshot = RepositorySnapshot(root, TARGET_IDENTITIES)
    try:
        snapshot.open_all()
        payloads = snapshot.read_all()
        if set(payloads) != PAYLOAD_PATHS:
            raise IdleResourceEvidenceError(
                "retained payload inventory differs from the fixed contract"
            )
        validate_release_payloads(payloads)
        result = validate_result_bytes(payloads[RESULT_RELATIVE_PATH])
        snapshot.verify_graph()
    finally:
        snapshot.close()
    run = result["measurement"]["run"]  # type: ignore[index]
    return {
        "maximumObservedLatenessMilliseconds": (
            run["maximumObservedLatenessMilliseconds"]  # type: ignore[index]
        ),
        "resultSha256": TARGET_IDENTITIES[RESULT_RELATIVE_PATH].sha256,
        "sampleCount": SAMPLE_COUNT,
        "targetCount": len(TARGET_IDENTITIES),
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        print(
            "usage: check_macos_build24_idle_resource_stability_evidence.py",
            file=sys.stderr,
        )
        return 2
    try:
        report = readback()
    except (IdleResourceEvidenceError, OSError) as error:
        print(
            f"Build 24 idle resource evidence failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "Build 24 idle resource evidence passed: "
        f"{report['targetCount']} fixed files, "
        f"{report['sampleCount']} samples, maximum lateness "
        f"{report['maximumObservedLatenessMilliseconds']} ms, result "
        f"SHA-256 {report['resultSha256']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
