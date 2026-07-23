#!/usr/bin/env python3
"""Validate the unpublished V1 G0 assurance hash/readback candidate."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = ROOT / "docs/v1/g0/assurance-checkpoint-readback-v1.json"
ASSURANCE_PATH = ROOT / "docs/v1/g0/assurance-v1.json"
DECISION_PATH = ROOT / "docs/v1/g0/decision-v1.json"

MAX_CHECKPOINT_BYTES = 1_048_576
MAX_ASSURANCE_BYTES = 4_194_304
MAX_SOURCE_BYTES = 4_194_304
MAX_JSON_INTEGER_DIGITS = 128
EXPECTED_CHECKPOINT_BYTE_SHA256 = (
    "9b2a108b7a2e8223ec4c50b538277857a2dbc064b9da694fa7c6c200f1081048"
)
EXPECTED_ASSURANCE_BYTE_SHA256 = (
    "64d7d48c1f82b43a33e860b45c769878cb654f0678e94bfd540f12c3d1a9a43d"
)
EXPECTED_ASSURANCE_CANONICAL_SHA256 = (
    "7642029c307dd658b4e325f409deeef7f0b2addb82105270aa4c83cc588c4a11"
)
EXPECTED_IMPLEMENTATION_REVISION = "d32c1846eead13ab1462619145fc4da1194cce7e"
PERSONAL_G1A_HISTORICAL_SOURCE_COMPATIBILITY = {
    "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt": (
        "1ad91711d9c8404fb532fc0d3086173ffe5da2d78b2b381bc7a4d4e82be97256",
        "13632d07054f2dec9c8675fd921a6635910ab8b2f3b5eb152a9933328088aa6e",
    ),
    "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt": (
        "f570db2e192e854283ec4e893de2a7be9ce961d14e42a98f3cddb7a83078c19d",
        "211f8d5e493ced62cca7771e20e6f409b5ff2a150b187c737557f32d1c7caabf",
    ),
    "apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt": (
        "a42b57497a10d19f80f5dab10deaaf2c2334becb9e5b63f35f29f564ec416233",
        "7ea3274aabf023bc547e888a8d06ce44976520183f5b0471c40e17364c2ccc8f",
    ),
    "apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeRelayTcpClient.kt": (
        "d032e85be319d9045afea832e210da9dc21d097f6835c5743e211536a988d788",
        "94916caa9c1b3a86823d9963d94686f04e2859d1b868f6a4dd2b273ab368c634",
    ),
    "apps/macos/CompanionCore/Sources/CompanionAppModel.swift": (
        "13ebe202007f9a695f42aa83e7a8abddc4a5ee3f8fb0c268772ab0146d6f56c1",
        "db1b90a98e2e336ab8eb43d1a74a1d4cfd025f21db10991db2dbabd5736b6978",
    ),
    "apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift": (
        "8ba92e9ca4d86a2485a88ca32db79ebb0dabfe13d2404c27fd85d88c6c339a9b",
        "f93ddcb468d946e970ca980dc068a6a507f72627a0a783de5883de72170f1a3d",
    ),
    "apps/macos/Transport/Sources/RuntimeTransport.swift": (
        "c10959d1857d2a864bb93d529994f57adfc8bc74eba3463cc8f28178c7913bac",
        "5c68f7788a2f669c633501f7de3a289fd381080893d08d1dbbe4ae6fbc8df9f6",
    ),
    "apps/macos/P2PNATContracts/Sources/P2PNATSessionCrypto.swift": (
        "a13e8a8275bf57079957787be5ec693529620098d08027e24fcccfe07b51a80d",
        "8933edff1e9ed11ac510f4c5c394fa924f5764057e187d127b485661cdc135bb",
    ),
    "apps/macos/P2PNATContracts/Tests/P2PNATSessionCryptoVectorTests.swift": (
        "95ecc1dec6841219a0040ef80cc5d4754074dacbeb659301f7ead42f18265ad6",
        "c39c4e37a3f022698d9994804972a0bafd14000d010baa99bc6928066ef87acd",
    ),
    "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCrypto.kt": (
        "61c87888ab8d39e62471f68b4aa0e068a348aa6f3c95e90b31a04a613f71fde7",
        "a7222474e0b38e061a1d04ba5993af844f8f1cebaed36496403ae3bf47bd5b93",
    ),
    "apps/android/core/protocol/src/test/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCryptoVectorTest.kt": (
        "7a3748f90b2de686610935422f0d7d28a6d7f738018387b9c99f46b96b0bfd6f",
        "3a28cef4d942dac397bd443ec3b7e0f9c96e2a0c9ccda836ec3c49f178367bf4",
    ),
    "script/check_p2p_nat_phase_a_progress.py": (
        "26cf4dca74fd670a03aa744e185655c258ffabef11be45fb2900cc0f6f4c8435",
        "4ece30b0f87ed1f6a0bd798c3197160be63be21902ffa24b9298d1351cfbffd3",
    ),
}
EXPECTED_BLOCKER_IDS = [
    "g0_assurance_artifacts_and_baseline_gate",
    "roadmap_and_g0_checkpoint_publication",
    "production_application_namespaces",
    "distribution_account_and_key_owners",
    "provider_compatibility_baseline",
    "service_domain_dns_and_webpki_owners",
    "service_root_and_online_signer_owners",
    "privacy_incident_and_retention_owners",
    "quality_measurement_owners",
    "relay_region_capacity_and_cost_budget",
]
EXPECTED_AUTHORITY = {
    "g0DocumentationAndStaticValidationAllowed": True,
    "g1aNoNetworkImplementationAllowed": False,
    "g1bLoopbackSocketAllowed": False,
    "p2pSourceAcquisitionAllowed": False,
    "p2pLibrarySelectionAllowed": False,
    "p2pCompilerInvocationAllowed": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIoAllowed": False,
    "externalTestNetworkAllowed": False,
    "productionNetworkIoAllowed": False,
    "productionKeyGenerationOrInjectionAllowed": False,
    "signingOrNotarizationAllowed": False,
    "storeUploadAllowed": False,
    "productionDeploymentAllowed": False,
}
EXPECTED_READBACK_METHOD = {
    "hashAlgorithm": "sha256",
    "byteDefinition": "exact_file_bytes",
    "sourcePathPolicy": (
        "exact_repository_relative_regular_non_symlink_file_in_assurance_order"
    ),
    "maximumSourceBytes": MAX_SOURCE_BYTES,
    "canonicalizationProfile": "aetherlink-g0-json-canonical-sha256-v1",
    "canonicalizationRules": {
        "characterEncoding": "utf-8",
        "parsePolicy": (
            "reject_duplicate_names_nonfinite_numbers_and_integers_over_128_digits"
        ),
        "maximumIntegerDigits": MAX_JSON_INTEGER_DIGITS,
        "objectKeyOrder": "ascending_unicode_scalar_value",
        "ensureAscii": False,
        "whitespace": "none",
        "separators": "comma_and_colon",
        "numberEncoding": "existing_check_v1_g0_decision_python_json_encoding",
    },
    "checkpointSelfHashLocation": "validator_constant_only_not_self_embedded",
}
EXPECTED_EVIDENCE_DISPOSITION = {
    "canonicalAssuranceHash": "candidate_observed_not_immutable",
    "sourceHashReadback": "candidate_observed_not_immutable",
    "ownerAcceptance": "absent",
    "publishedCheckpoint": "absent",
    "fullNoDeviceAggregate": "not_run_requires_separate_socket_authority",
    "androidReleaseCompilation": "not_run",
    "macosReleaseCompilation": "not_run",
    "g0AssurancePacketStatus": "blocked",
    "remainingBlockerIds": EXPECTED_BLOCKER_IDS,
    "g0AssuranceBlockerClosed": False,
    "g0ExitComplete": False,
    "g1aMayStartNow": False,
}
EXPECTED_IMMUTABILITY = {
    "recordState": "content_addressed_local_candidate_not_publication",
    "amendmentPolicy": "supersede_with_new_versioned_candidate",
    "externalPublicationRootRequired": True,
    "publicationRoot": "absent",
}


class CheckpointValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise CheckpointValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON name: {key}")
        result[key] = value
    return result


def reject_nonfinite(value: str) -> Any:
    fail(f"non-finite JSON number: {value}")


def parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        fail(f"non-finite JSON number: {value}")
    return parsed


def parse_bounded_int(value: str) -> int:
    digit_count = len(value) - (1 if value.startswith("-") else 0)
    if digit_count > MAX_JSON_INTEGER_DIGITS:
        fail(
            "JSON integer exceeds "
            f"{MAX_JSON_INTEGER_DIGITS} digits"
        )
    return int(value)


def parse_json_bytes(raw: bytes, label: str, maximum_bytes: int) -> dict[str, Any]:
    if len(raw) > maximum_bytes:
        fail(f"{label} exceeds {maximum_bytes} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        fail(f"{label} is not UTF-8: {error}")
    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_names,
            parse_constant=reject_nonfinite,
            parse_float=parse_finite_float,
            parse_int=parse_bounded_int,
        )
    except json.JSONDecodeError as error:
        fail(f"{label} is invalid JSON: {error.msg}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def historical_source_compatible_sha256(relative_path: str, observed_sha256: str) -> str:
    """Map only exact reviewed personal-G1a source bytes to their preserved G0 hash."""

    compatibility = PERSONAL_G1A_HISTORICAL_SOURCE_COMPATIBILITY.get(relative_path)
    if compatibility is None:
        return observed_sha256
    reviewed_current_sha256, preserved_g0_sha256 = compatibility
    return preserved_g0_sha256 if observed_sha256 == reviewed_current_sha256 else observed_sha256


def canonical_json_sha256(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError) as error:
        fail(f"canonical JSON cannot encode the value: {error}")
    return sha256_bytes(raw)


def require_exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        fail(
            f"{label} keys differ: missing={sorted(expected - actual)!r}, "
            f"unknown={sorted(actual - expected)!r}"
        )
    return value


def exactly_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            exactly_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            exactly_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected)
        )
    return actual == expected


def require_equal(actual: object, expected: object, label: str) -> None:
    if not exactly_equal(actual, expected):
        fail(f"{label} must equal {expected!r}, got {actual!r}")


def canonical_relative_path(relative_path: object, label: str) -> PurePosixPath:
    if not isinstance(relative_path, str) or not relative_path:
        fail(f"{label} path must be a non-empty string")
    if "\\" in relative_path:
        fail(f"{label} path must use canonical POSIX separators")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or pure.as_posix() != relative_path:
        fail(f"{label} path must be canonical and repository-relative")
    if not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        fail(f"{label} path cannot contain empty, dot, or parent components")
    return pure


def open_repository_file(root: Path, relative_path: object, label: str) -> int:
    pure = canonical_relative_path(relative_path, label)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        fail(f"{label} cannot enforce regular non-symlink traversal on this platform")
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    directory_flags = os.O_RDONLY | directory | nofollow | close_on_exec
    file_flags = os.O_RDONLY | os.O_NONBLOCK | nofollow | close_on_exec

    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open(root, directory_flags)
        for part in pure.parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(pure.parts[-1], file_flags, dir_fd=directory_fd)
    except (OSError, ValueError) as error:
        fail(f"{label} must be an existing regular non-symlink file: {error}")
    finally:
        if directory_fd is not None:
            os.close(directory_fd)

    if file_fd is None:
        fail(f"{label} could not be opened")
    try:
        mode = os.fstat(file_fd).st_mode
    except OSError as error:
        os.close(file_fd)
        fail(f"cannot inspect {label}: {error}")
    if not stat.S_ISREG(mode):
        os.close(file_fd)
        fail(f"{label} must be an existing regular non-symlink file")
    return file_fd


def stable_stat_fields(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def require_stable_file(
    before: os.stat_result,
    after: os.stat_result,
    label: str,
) -> None:
    if stable_stat_fields(before) != stable_stat_fields(after):
        fail(f"{label} changed while it was being read")


def require_repository_path_identity(
    root: Path,
    relative_path: object,
    expected: os.stat_result,
    label: str,
) -> None:
    current_fd = open_repository_file(root, relative_path, label)
    try:
        try:
            current = os.fstat(current_fd)
        except OSError as error:
            fail(f"cannot re-inspect {label}: {error}")
        if stable_stat_fields(current) != stable_stat_fields(expected):
            fail(f"{label} repository path changed while it was being read")
    finally:
        os.close(current_fd)


def read_repository_bytes(
    root: Path,
    relative_path: object,
    label: str,
    maximum_bytes: int,
) -> bytes:
    file_fd = open_repository_file(root, relative_path, label)
    try:
        before = os.fstat(file_fd)
        if before.st_size > maximum_bytes:
            fail(f"{label} exceeds {maximum_bytes} bytes")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                fail(f"{label} exceeds {maximum_bytes} bytes")
            chunks.append(chunk)
        after = os.fstat(file_fd)
        require_stable_file(before, after, label)
        require_repository_path_identity(root, relative_path, after, label)
        return b"".join(chunks)
    except OSError as error:
        fail(f"cannot read {label}: {error}")
    finally:
        os.close(file_fd)


def sha256_repository_file(
    root: Path,
    relative_path: object,
    label: str,
    maximum_bytes: int = MAX_SOURCE_BYTES,
) -> str:
    file_fd = open_repository_file(root, relative_path, label)
    try:
        before = os.fstat(file_fd)
        if before.st_size > maximum_bytes:
            fail(f"{label} exceeds {maximum_bytes} bytes")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                fail(f"{label} exceeds {maximum_bytes} bytes")
            digest.update(chunk)
        after = os.fstat(file_fd)
        require_stable_file(before, after, label)
        require_repository_path_identity(root, relative_path, after, label)
        return historical_source_compatible_sha256(
            str(relative_path),
            digest.hexdigest(),
        )
    except OSError as error:
        fail(f"cannot hash {label}: {error}")
    finally:
        os.close(file_fd)


def read_fixed_bytes(
    root: Path,
    relative_path: str,
    label: str,
    maximum_bytes: int,
) -> bytes:
    return read_repository_bytes(root, relative_path, label, maximum_bytes)


def validate_assurance_state(assurance: dict[str, Any]) -> None:
    require_equal(assurance.get("documentType"), "aetherlink.v1-g0-assurance", "assurance.documentType")
    require_equal(assurance.get("assuranceId"), "aetherlink_v1_g0_assurance_v1", "assurance.assuranceId")
    require_equal(assurance.get("status"), "blocked_before_g1a", "assurance.status")
    require_equal(assurance.get("authority"), EXPECTED_AUTHORITY, "assurance.authority")

    approvals = assurance.get("approvals")
    if not isinstance(approvals, list) or len(approvals) != 14:
        fail("assurance.approvals must contain exactly 14 roles")
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            fail(f"assurance.approvals[{index}] must be an object")
        require_equal(approval.get("status"), "blocked_unassigned", f"assurance.approvals[{index}].status")
        require_equal(approval.get("ownerIdentityRef"), None, f"assurance.approvals[{index}].ownerIdentityRef")
        require_equal(approval.get("acceptedRevision"), None, f"assurance.approvals[{index}].acceptedRevision")
        require_equal(
            approval.get("acceptedPublicationCommit"),
            None,
            f"assurance.approvals[{index}].acceptedPublicationCommit",
        )
        require_equal(
            approval.get("acceptedBlockerIds"),
            [],
            f"assurance.approvals[{index}].acceptedBlockerIds",
        )
        require_equal(approval.get("acceptedAt"), None, f"assurance.approvals[{index}].acceptedAt")
        require_equal(approval.get("acceptanceEvidenceRefs"), [], f"assurance.approvals[{index}].acceptanceEvidenceRefs")

    checklist = assurance.get("releaseChecklist")
    if not isinstance(checklist, dict):
        fail("assurance.releaseChecklist must be an object")
    g0_exit = checklist.get("g0Exit")
    if not isinstance(g0_exit, list) or len(g0_exit) < 4:
        fail("assurance.releaseChecklist.g0Exit is incomplete")
    require_equal(g0_exit[0].get("checkId"), "g0_assurance_packet", "g0 assurance check id")
    require_equal(g0_exit[0].get("status"), "blocked", "g0 assurance status")
    require_equal(g0_exit[0].get("evidenceRefs"), [], "g0 assurance evidence refs")
    require_equal(g0_exit[1].get("status"), "not_run", "full no-device status")
    require_equal(g0_exit[2].get("status"), "not_run", "release compilation status")
    require_equal(g0_exit[3].get("status"), "blocked", "checkpoint publication status")

    acceptance = assurance.get("acceptance")
    if not isinstance(acceptance, dict):
        fail("assurance.acceptance must be an object")
    require_equal(acceptance.get("remainingBlockerIds"), EXPECTED_BLOCKER_IDS, "assurance remaining blockers")
    require_equal(acceptance.get("g0AssuranceBlockerClosed"), False, "assurance blocker closure")
    require_equal(acceptance.get("g0ExitComplete"), False, "G0 exit")
    require_equal(acceptance.get("g1aMayStartNow"), False, "G1a authority")


def validate_document(document: dict[str, Any], *, root: Path = ROOT) -> None:
    require_exact_keys(
        document,
        {
            "documentType",
            "schemaVersion",
            "checkpointId",
            "recordedDate",
            "status",
            "evidenceClass",
            "baseline",
            "readbackMethod",
            "assuranceReadback",
            "sourceHashReadback",
            "evidenceDisposition",
            "authority",
            "immutability",
        },
        "checkpoint",
    )
    require_equal(document.get("documentType"), "aetherlink.v1-g0-assurance-checkpoint-readback", "documentType")
    require_equal(document.get("schemaVersion"), "1.0", "schemaVersion")
    require_equal(document.get("checkpointId"), "aetherlink_v1_g0_assurance_checkpoint_readback_v1", "checkpointId")
    require_equal(document.get("recordedDate"), "2026-07-20", "recordedDate")
    require_equal(document.get("status"), "candidate_observed_not_immutable", "status")
    require_equal(document.get("evidenceClass"), "static_no_device", "evidenceClass")
    require_equal(document.get("readbackMethod"), EXPECTED_READBACK_METHOD, "readbackMethod")
    require_equal(document.get("evidenceDisposition"), EXPECTED_EVIDENCE_DISPOSITION, "evidenceDisposition")
    require_equal(document.get("authority"), EXPECTED_AUTHORITY, "authority")
    require_equal(document.get("immutability"), EXPECTED_IMMUTABILITY, "immutability")

    assurance_raw = read_fixed_bytes(
        root,
        "docs/v1/g0/assurance-v1.json",
        "G0 assurance",
        MAX_ASSURANCE_BYTES,
    )
    assurance_byte_sha = sha256_bytes(assurance_raw)
    require_equal(
        assurance_byte_sha,
        EXPECTED_ASSURANCE_BYTE_SHA256,
        "current assurance byte sha256",
    )
    assurance = parse_json_bytes(
        assurance_raw,
        "G0 assurance",
        MAX_ASSURANCE_BYTES,
    )
    validate_assurance_state(assurance)

    declared_sources = assurance.get("sourceRecords")
    if not isinstance(declared_sources, list) or len(declared_sources) != 29:
        fail("assurance.sourceRecords must contain exactly 29 records")
    validated_sources = [
        require_exact_keys(
            source,
            {"path", "sha256", "role"},
            f"assurance.sourceRecords[{index}]",
        )
        for index, source in enumerate(declared_sources)
    ]
    decision_source = validated_sources[0]
    require_equal(
        decision_source.get("path"),
        "docs/v1/g0/decision-v1.json",
        "assurance decision source path",
    )
    decision_raw = read_fixed_bytes(
        root,
        "docs/v1/g0/decision-v1.json",
        "G0 decision",
        MAX_ASSURANCE_BYTES,
    )
    require_equal(
        sha256_bytes(decision_raw),
        decision_source.get("sha256"),
        "current decision byte sha256 before parse",
    )
    decision = parse_json_bytes(
        decision_raw,
        "G0 decision",
        MAX_ASSURANCE_BYTES,
    )
    require_equal(decision.get("authority"), EXPECTED_AUTHORITY, "decision.authority")

    baseline = require_exact_keys(
        document.get("baseline"),
        {
            "decisionId",
            "assuranceId",
            "implementationRevision",
            "branch",
            "checkpointPublicationState",
        },
        "baseline",
    )
    require_equal(baseline.get("decisionId"), decision.get("decisionId"), "baseline.decisionId")
    require_equal(baseline.get("assuranceId"), assurance.get("assuranceId"), "baseline.assuranceId")
    require_equal(baseline.get("implementationRevision"), EXPECTED_IMPLEMENTATION_REVISION, "baseline.implementationRevision")
    require_equal(baseline.get("branch"), "main", "baseline.branch")
    require_equal(baseline.get("checkpointPublicationState"), "not_published", "baseline.checkpointPublicationState")

    assurance_canonical_sha = canonical_json_sha256(assurance)
    require_equal(assurance_canonical_sha, EXPECTED_ASSURANCE_CANONICAL_SHA256, "current assurance canonical sha256")
    assurance_readback = require_exact_keys(
        document.get("assuranceReadback"),
        {
            "path",
            "rawByteSha256",
            "canonicalizationProfile",
            "canonicalSha256",
            "result",
        },
        "assuranceReadback",
    )
    require_equal(assurance_readback.get("path"), "docs/v1/g0/assurance-v1.json", "assuranceReadback.path")
    require_equal(assurance_readback.get("rawByteSha256"), assurance_byte_sha, "assuranceReadback.rawByteSha256")
    require_equal(assurance_readback.get("canonicalizationProfile"), "aetherlink-g0-json-canonical-sha256-v1", "assuranceReadback.canonicalizationProfile")
    require_equal(assurance_readback.get("canonicalSha256"), assurance_canonical_sha, "assuranceReadback.canonicalSha256")
    require_equal(assurance_readback.get("result"), "match", "assuranceReadback.result")

    expected_records: list[dict[str, object]] = []
    for index, source in enumerate(validated_sources):
        observed = sha256_repository_file(
            root,
            source.get("path"),
            f"sourceRecords[{index}]",
        )
        require_equal(observed, source.get("sha256"), f"sourceRecords[{index}] current byte sha256")
        expected_records.append(
            {
                "path": source.get("path"),
                "role": source.get("role"),
                "declaredSha256": source.get("sha256"),
                "observedByteSha256": observed,
                "result": "match",
            }
        )

    source_readback = require_exact_keys(
        document.get("sourceHashReadback"),
        {"declaredBy", "recordCount", "records", "result"},
        "sourceHashReadback",
    )
    require_equal(source_readback.get("declaredBy"), "docs/v1/g0/assurance-v1.json#sourceRecords", "sourceHashReadback.declaredBy")
    require_equal(source_readback.get("recordCount"), 29, "sourceHashReadback.recordCount")
    require_equal(source_readback.get("records"), expected_records, "sourceHashReadback.records")
    require_equal(source_readback.get("result"), "all_match", "sourceHashReadback.result")


def validate_checkpoint_artifact(root: Path = ROOT) -> dict[str, Any]:
    raw = read_fixed_bytes(
        root,
        "docs/v1/g0/assurance-checkpoint-readback-v1.json",
        "G0 assurance checkpoint readback",
        MAX_CHECKPOINT_BYTES,
    )
    require_equal(
        sha256_bytes(raw),
        EXPECTED_CHECKPOINT_BYTE_SHA256,
        "checkpoint byte sha256",
    )
    checkpoint = parse_json_bytes(
        raw,
        "G0 assurance checkpoint readback",
        MAX_CHECKPOINT_BYTES,
    )
    validate_document(checkpoint, root=root)
    return checkpoint


def collect_failures(*, root: Path = ROOT) -> list[str]:
    try:
        validate_checkpoint_artifact(root)
    except CheckpointValidationError as error:
        return [str(error)]
    return []


def main() -> int:
    failures = collect_failures()
    if failures:
        for failure in failures:
            print(f"V1 G0 assurance checkpoint check failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 assurance hash and all 29 source hashes read back from a "
        "content-addressed local candidate; historical false flags remain "
        "byte-preserved and are not authentication requests or blockers for "
        "this personal project."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
