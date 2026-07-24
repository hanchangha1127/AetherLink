#!/usr/bin/env python3
"""Independently read back and optionally record wave-two acquisition success."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
COMMON_PATH = "script/p2p_nat_g2_pion_dependency_wave2_common_v1.py"
PERMIT_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave2-execution-permit-v1.json"
)
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave2_execution_permit_v1.py"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave2_success_v1.py"
)

EXPECTED_COMMON_RAW_SHA256 = (
    "dc25ddd3a82789bddccbd6ec57a71edc389225e003d7a73e6d371a640937f8c1"
)
EXPECTED_PERMIT_CHECKER_RAW_SHA256 = (
    "608cc5c067f1f48b95cfcfe69a5deb8a0a67c527bbfe8e2b844da47b048df7d4"
)


def bootstrap_read(relative: str, expected_sha256: str) -> bytes:
    path = ROOT / relative
    for parent in path.parents:
        if parent == ROOT.parent:
            break
        if parent == ROOT:
            continue
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid not in {0, os.geteuid()}
            or stat.S_IMODE(before.st_mode) & 0o022
            or before.st_size > 4 * 1024 * 1024
        ):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                raise RuntimeError("E_BOOTSTRAP_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if (
            os.read(fd, 1) != b""
            or hashlib.sha256(raw).hexdigest() != expected_sha256
            or before.st_dev != os.fstat(fd).st_dev
            or before.st_ino != os.fstat(fd).st_ino
            or before.st_size != os.fstat(fd).st_size
        ):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
        return raw
    finally:
        os.close(fd)


def execute_module(
    name: str,
    relative: str,
    raw: bytes,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__file__": str(ROOT / relative),
            "__cached__": None,
            "__loader__": None,
            "__package__": None,
        }
    )
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(
            compile(raw, relative, "exec", dont_inherit=True, optimize=0),
            module.__dict__,
            module.__dict__,
        )
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


COMMON = execute_module(
    "g2_wave2_readback_common_trust_root",
    COMMON_PATH,
    bootstrap_read(COMMON_PATH, EXPECTED_COMMON_RAW_SHA256),
)

CLAIM_KEYS = {
    "claimType",
    "schemaVersion",
    "attemptId",
    "permitId",
    "permitContentSha256",
    "decisionId",
    "decisionContentSha256",
    "orderedResourceSetSha256",
    "createdAt",
    "rule",
    "automaticRetryAllowed",
    "userActionRequired",
}
SOURCE_RECORD_KEYS = {
    "order",
    "tupleId",
    "module",
    "version",
    "selectedByGraphAlgorithm",
    "modRequestOrdinal",
    "zipRequestOrdinal",
    "modUrl",
    "zipUrl",
    "modOutputFileName",
    "zipOutputFileName",
    "modRawByteSize",
    "modRawSha256",
    "zipRawByteSize",
    "zipRawSha256",
    "goModH1",
    "moduleZipH1",
    "entryCount",
    "uncompressedByteCount",
    "modulePrefix",
    "embeddedGoModPresent",
    "embeddedGoModByteParity",
    "compressionRatioLimitPassed",
    "modMode",
    "modLinkCount",
    "zipMode",
    "zipLinkCount",
}
RECEIPT_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "result",
    "permitId",
    "permitRawSha256",
    "permitContentSha256",
    "decisionId",
    "decisionRawSha256",
    "decisionContentSha256",
    "claimRawSha256",
    *COMMON.COUNTER_NAMES,
    "acceptedArtifactCount",
    "acceptedTupleCount",
    "aggregateModRawByteSize",
    "aggregateZipRawByteSize",
    "aggregateRawByteSize",
    "aggregateEntryCount",
    "aggregateUncompressedByteCount",
    "orderedSourceSetSha256",
    "orderedResourceSetSha256",
    "sources",
    "heldGoSumH1Matched",
    "freshChecksumDatabaseProof",
    "independentReadbackPassed",
    "dependencyFixedPointReached",
    "dependencySourceReviewed",
    "dependencyClosureComplete",
    "candidateSelected",
    "librarySelected",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
}
MANIFEST_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "result",
    "permitId",
    "permitRawSha256",
    "permitContentSha256",
    "decisionRawSha256",
    "decisionContentSha256",
    "successReceiptPath",
    "successReceiptRawSha256",
    "finalDirectoryPath",
    *COMMON.COUNTER_NAMES,
    "acceptedArtifactCount",
    "acceptedTupleCount",
    "orderedSourceSetSha256",
    "manifestWrittenLast",
    "independentReadbackPassed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
}


def canonical_utc_timestamp(value: Any) -> bool:
    if type(value) is not str or len(value) != 20:
        return False
    try:
        parsed = time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, ValueError):
        return False
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", parsed) == value


def authority_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": COMMON_PATH,
            "rawSha256": EXPECTED_COMMON_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        *COMMON.decision_bindings(),
        *COMMON.primitive_bindings(),
        {
            "path": PERMIT_CHECKER_PATH,
            "rawSha256": EXPECTED_PERMIT_CHECKER_RAW_SHA256,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": PERMIT_PATH,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
        },
        {
            "path": THIS_CHECKER_PATH,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        {
            "path": (
                f"{COMMON.DEPENDENCY_PARENT.as_posix()}/"
                f"{COMMON.CLAIM_NAME}"
            ),
            "maximumBytes": 64 * 1024,
            "ownerOnly": True,
        },
        {
            "path": COMMON.SUCCESS_RECEIPT_PATH,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": COMMON.MANIFEST_PATH,
            "maximumBytes": COMMON.MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
    ]


def load_authority() -> dict[str, Any]:
    if sys.flags.isolated != 1 or not sys.dont_write_bytecode:
        raise COMMON.Wave2Failure("E_INTERPRETER", "readback")
    try:
        inputs = COMMON.HeldInputSet(ROOT, authority_bindings())
    except Exception as error:
        if isinstance(error, COMMON.Wave2Failure):
            raise
        raise COMMON.Wave2Failure(
            "E_ACQUISITION_NOT_READY",
            "readback",
        ) from error
    try:
        permit_checker = COMMON.execute_fixed_module(
            "g2_wave2_readback_permit_checker_trust_root",
            PERMIT_CHECKER_PATH,
            inputs.raw(PERMIT_CHECKER_PATH),
            ROOT,
        )
        try:
            checked = permit_checker.validate_repository(
                ROOT,
                require_clean_namespace=False,
            )
        except Exception as error:
            raise COMMON.Wave2Failure(
                "E_PERMIT_VALIDATION",
                "readback",
            ) from error
        if (
            checked.get("executionAuthorized") is not True
            or type(checked.get("permit")) is not dict
            or type(checked.get("decision")) is not dict
            or type(checked.get("repositoryRootIdentity")) is not dict
        ):
            raise COMMON.Wave2Failure(
                "E_PERMIT_VALIDATION",
                "readback",
            )
        permit = checked["permit"]
        decision = checked["decision"]
        items = COMMON.adapt_tuples(decision)
        legacy, core = COMMON.configure_primitives(inputs, ROOT)
        claim_raw = inputs.raw(
            f"{COMMON.DEPENDENCY_PARENT.as_posix()}/{COMMON.CLAIM_NAME}"
        )
        receipt_raw = inputs.raw(COMMON.SUCCESS_RECEIPT_PATH)
        manifest_raw = inputs.raw(COMMON.MANIFEST_PATH)
        claim = COMMON.strict_json(claim_raw, "claim")
        receipt = COMMON.strict_json(receipt_raw, "receipt")
        manifest = COMMON.strict_json(manifest_raw, "manifest")
        permit_raw = inputs.raw(PERMIT_PATH)
        if (
            set(claim) != CLAIM_KEYS
            or set(receipt) != RECEIPT_KEYS
            or set(manifest) != MANIFEST_KEYS
            or claim.get("claimType")
            != "aetherlink.g2-pion-dependency-wave2-v1-one-use-claim"
            or claim.get("schemaVersion") != "1.0"
            or type(claim.get("attemptId")) is not str
            or len(claim["attemptId"]) != 32
            or any(
                character not in "0123456789abcdef"
                for character in claim["attemptId"]
            )
            or claim.get("permitId") != permit["permitId"]
            or claim.get("permitContentSha256")
            != permit["contentBinding"]["sha256"]
            or claim.get("decisionId") != decision["decisionId"]
            or claim.get("decisionContentSha256")
            != COMMON.EXPECTED_DECISION_CONTENT_SHA256
            or claim.get("orderedResourceSetSha256")
            != decision["wave"]["orderedResourceSetSha256"]
            or not canonical_utc_timestamp(claim.get("createdAt"))
            or claim.get("rule")
            != "claim_persists_after_any_network_attempt_and_blocks_retry"
            or claim.get("automaticRetryAllowed") is not False
            or claim.get("userActionRequired") is not False
            or receipt.get("documentType")
            != "aetherlink.g2-pion-dependency-wave2-v1-acquisition-receipt"
            or receipt.get("schemaVersion") != "1.0"
            or receipt.get("status") != "acquired_pending_independent_readback"
            or receipt.get("result")
            != (
                "fresh_exact_15_dependency_mod_zip_pairs_acquired_and_"
                "held_h1_verified"
            )
            or receipt.get("permitId") != permit["permitId"]
            or receipt.get("permitRawSha256")
            != COMMON.sha256_bytes(permit_raw)
            or receipt.get("permitContentSha256")
            != permit["contentBinding"]["sha256"]
            or receipt.get("decisionId") != decision["decisionId"]
            or receipt.get("decisionRawSha256")
            != COMMON.EXPECTED_DECISION_RAW_SHA256
            or receipt.get("decisionContentSha256")
            != COMMON.EXPECTED_DECISION_CONTENT_SHA256
            or receipt.get("claimRawSha256")
            != COMMON.sha256_bytes(claim_raw)
            or receipt.get("orderedResourceSetSha256")
            != decision["wave"]["orderedResourceSetSha256"]
            or receipt.get("heldGoSumH1Matched") is not True
            or receipt.get("freshChecksumDatabaseProof") is not False
            or receipt.get("independentReadbackPassed") is not False
            or receipt.get("dependencyFixedPointReached") is not False
            or receipt.get("dependencySourceReviewed") is not False
            or receipt.get("dependencyClosureComplete") is not False
            or receipt.get("candidateSelected") is not False
            or receipt.get("librarySelected") is not False
            or receipt.get("repositoryOwnerIdentityProofRequired") is not False
            or receipt.get("externalAuthenticationRequired") is not False
            or receipt.get("userActionRequired") is not False
            or receipt.get("nextAction")
            != "run_separate_wave2_v1_independent_readback"
            or manifest.get("documentType")
            != "aetherlink.g2-pion-dependency-wave2-v1-acquisition-manifest"
            or manifest.get("schemaVersion") != "1.0"
            or manifest.get("status")
            != (
                "wave2_v1_acquisition_publication_complete_pending_"
                "independent_readback"
            )
            or manifest.get("result")
            != (
                "receipt_and_fresh_exact_15_mod_zip_pairs_published_"
                "manifest_written_last"
            )
            or manifest.get("permitId") != permit["permitId"]
            or manifest.get("permitRawSha256")
            != COMMON.sha256_bytes(permit_raw)
            or manifest.get("permitContentSha256")
            != permit["contentBinding"]["sha256"]
            or manifest.get("decisionRawSha256")
            != COMMON.EXPECTED_DECISION_RAW_SHA256
            or manifest.get("decisionContentSha256")
            != COMMON.EXPECTED_DECISION_CONTENT_SHA256
            or manifest.get("successReceiptPath")
            != COMMON.SUCCESS_RECEIPT_PATH
            or manifest.get("successReceiptRawSha256")
            != COMMON.sha256_bytes(receipt_raw)
            or manifest.get("finalDirectoryPath")
            != COMMON.FINAL_DIRECTORY_PATH
            or manifest.get("manifestWrittenLast") is not True
            or manifest.get("independentReadbackPassed") is not False
            or manifest.get("repositoryOwnerIdentityProofRequired") is not False
            or manifest.get("externalAuthenticationRequired") is not False
            or manifest.get("userActionRequired") is not False
            or manifest.get("nextAction")
            != "run_separate_wave2_v1_independent_readback"
        ):
            raise COMMON.Wave2Failure(
                "E_ACQUISITION_BINDING",
                "readback",
            )
        counters = {
            name: receipt.get(name)
            for name in COMMON.COUNTER_NAMES
        }
        COMMON.validate_counters(counters)
        if (
            not COMMON.success_counters(counters)
            or receipt.get("acceptedArtifactCount") != 30
            or receipt.get("acceptedTupleCount") != 15
            or receipt.get("independentReadbackPassed") is not False
            or receipt.get("freshChecksumDatabaseProof") is not False
            or type(receipt.get("sources")) is not list
            or len(receipt["sources"]) != 15
            or any(
                type(record) is not dict
                or set(record) != SOURCE_RECORD_KEYS
                for record in receipt["sources"]
            )
            or any(
                manifest.get(name) != counters[name]
                for name in COMMON.COUNTER_NAMES
            )
            or manifest.get("acceptedArtifactCount") != 30
            or manifest.get("acceptedTupleCount") != 15
            or manifest.get("orderedSourceSetSha256")
            != receipt.get("orderedSourceSetSha256")
        ):
            raise COMMON.Wave2Failure(
                "E_ACQUISITION_RECEIPT",
                "readback",
            )
        inputs.final_barrier()
        return {
            "inputs": inputs,
            "permit": permit,
            "decision": decision,
            "items": items,
            "legacy": legacy,
            "core": core,
            "claimRaw": claim_raw,
            "receiptRaw": receipt_raw,
            "manifestRaw": manifest_raw,
            "receipt": receipt,
            "manifest": manifest,
            "repositoryRootIdentity": checked["repositoryRootIdentity"],
        }
    except BaseException:
        inputs.close()
        raise


def exact_source_record(
    item: Mapping[str, Any],
    record: Mapping[str, Any],
) -> None:
    if (
        set(record) != SOURCE_RECORD_KEYS
        or record.get("order") != item["order"]
        or record.get("tupleId") != item["tupleId"]
        or record.get("module") != item["module"]
        or record.get("version") != item["version"]
        or record.get("selectedByGraphAlgorithm")
        is not item["selectedByGraphAlgorithm"]
        or record.get("modRequestOrdinal") != item["modRequestOrdinal"]
        or record.get("zipRequestOrdinal") != item["zipRequestOrdinal"]
        or record.get("modUrl") != item["modUrl"]
        or record.get("zipUrl") != item["url"]
        or record.get("modOutputFileName")
        != item["modOutputFileName"]
        or record.get("zipOutputFileName")
        != item["zipOutputFileName"]
        or record.get("goModH1") != item["goModH1"]
        or record.get("moduleZipH1") != item["moduleZipH1"]
        or record.get("modulePrefix")
        != f"{item['module']}@{item['version']}/"
        or record.get("modMode") != "0600"
        or record.get("zipMode") != "0600"
        or record.get("modLinkCount") != 1
        or record.get("zipLinkCount") != 1
        or record.get("compressionRatioLimitPassed") is not True
    ):
        raise COMMON.Wave2Failure("E_SOURCE_RECORD", "readback")


def read_resource_twice(
    legacy: types.ModuleType,
    directory_fd: int,
    name: str,
    expected_size: int,
    maximum_bytes: int,
) -> tuple[int, bytes]:
    fd = os.open(name, legacy.file_open_flags(), dir_fd=directory_fd)
    try:
        legacy.named_entry_matches_open_file(
            directory_fd,
            name,
            fd,
            expected_link_count=1,
        )
        first = legacy.read_stable_regular_file_from_descriptor(
            fd,
            name,
            maximum_bytes,
        ) if hasattr(
            legacy,
            "read_stable_regular_file_from_descriptor",
        ) else None
        if first is None:
            before = legacy.validate_regular_descriptor(
                fd,
                name,
                owner_only=True,
            )
            if before.st_size != expected_size:
                raise COMMON.Wave2Failure(
                    "E_RESOURCE_IDENTITY",
                    "readback",
                )
            def read_pass() -> bytes:
                os.lseek(fd, 0, os.SEEK_SET)
                chunks: list[bytes] = []
                remaining = expected_size
                while remaining:
                    chunk = os.read(fd, min(65_536, remaining))
                    if not chunk:
                        raise COMMON.Wave2Failure(
                            "E_RESOURCE_IDENTITY",
                            "readback",
                        )
                    chunks.append(chunk)
                    remaining -= len(chunk)
                if os.read(fd, 1) != b"":
                    raise COMMON.Wave2Failure(
                        "E_RESOURCE_IDENTITY",
                        "readback",
                    )
                return b"".join(chunks)
            first = read_pass()
            second = read_pass()
            if first != second:
                raise COMMON.Wave2Failure("E_TOCTOU", "readback")
        else:
            second = first
        info = legacy.validate_regular_descriptor(
            fd,
            name,
            owner_only=True,
        )
        legacy.named_entry_matches_open_file(
            directory_fd,
            name,
            fd,
            expected_link_count=1,
        )
        if (
            info.st_size != expected_size
            or len(first) != expected_size
            or first != second
        ):
            raise COMMON.Wave2Failure(
                "E_RESOURCE_IDENTITY",
                "readback",
            )
        return fd, first
    except BaseException:
        os.close(fd)
        raise


def revalidate_retained_resource_pass(guard: Mapping[str, Any]) -> None:
    legacy = guard["legacy"]
    final_fd = guard["finalFd"]
    wave_fd = guard["waveFd"]
    dependency_fd = guard["dependencyFd"]
    identities = guard["identities"]
    for identity, fd in zip(identities, guard["resourceFds"]):
        legacy.validate_regular_descriptor(
            fd,
            "resource",
            owner_only=True,
        )
        legacy.named_entry_matches_open_file(
            final_fd,
            identity["name"],
            fd,
            expected_link_count=1,
        )
        current = os.fstat(fd)
        if (
            current.st_dev != identity["device"]
            or current.st_ino != identity["inode"]
            or stat.S_IMODE(current.st_mode) != identity["mode"]
            or current.st_uid != identity["uid"]
            or current.st_nlink != identity["linkCount"]
            or current.st_size != identity["size"]
            or current.st_mtime_ns != identity["mtimeNs"]
            or current.st_ctime_ns != identity["ctimeNs"]
        ):
            raise COMMON.Wave2Failure("E_TOCTOU", "readback")
    wave_initial = guard["waveIdentity"]
    final_initial = guard["finalIdentity"]
    wave_named = os.stat(
        COMMON.WAVE_PARENT_NAME,
        dir_fd=dependency_fd,
        follow_symlinks=False,
    )
    final_named = os.stat(
        COMMON.FINAL_DIRECTORY_NAME,
        dir_fd=wave_fd,
        follow_symlinks=False,
    )
    if (
        wave_named.st_dev != wave_initial.st_dev
        or wave_named.st_ino != wave_initial.st_ino
        or os.fstat(wave_fd).st_dev != wave_initial.st_dev
        or os.fstat(wave_fd).st_ino != wave_initial.st_ino
        or final_named.st_dev != final_initial.st_dev
        or final_named.st_ino != final_initial.st_ino
        or os.fstat(final_fd).st_dev != final_initial.st_dev
        or os.fstat(final_fd).st_ino != final_initial.st_ino
        or legacy.list_names(wave_fd) != [COMMON.FINAL_DIRECTORY_NAME]
        or legacy.list_names(final_fd) != guard["expectedResourceNames"]
    ):
        raise COMMON.Wave2Failure("E_TOCTOU", "readback")


def close_retained_resource_pass(guard: Mapping[str, Any]) -> None:
    legacy = guard["legacy"]
    for fd in guard["resourceFds"]:
        legacy.close_quietly(fd)
    for key in ("finalFd", "waveFd", "dependencyFd", "rootFd"):
        legacy.close_quietly(guard[key])


def read_exact_published_payload(
    fd: int,
    expected_payload: bytes,
) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = len(expected_payload)
    while remaining:
        chunk = os.read(fd, min(65_536, remaining))
        if not chunk:
            raise COMMON.Wave2Failure("E_TOCTOU", "readback")
        chunks.append(chunk)
        remaining -= len(chunk)
    raw = b"".join(chunks)
    if os.read(fd, 1) != b"" or raw != expected_payload:
        raise COMMON.Wave2Failure("E_TOCTOU", "readback")
    return raw


def open_published_artifact(
    root_fd: int,
    relative_path: str,
    expected_payload: bytes,
    legacy: types.ModuleType,
) -> dict[str, Any]:
    parts = legacy.validate_relative_path(relative_path)
    parent_fd = legacy.open_directory_chain(
        root_fd,
        parts[:-1],
        create=False,
    )
    file_fd = -1
    try:
        file_fd = os.open(
            parts[-1],
            legacy.file_open_flags(),
            dir_fd=parent_fd,
        )
        legacy.named_entry_matches_open_file(
            parent_fd,
            parts[-1],
            file_fd,
            expected_link_count=1,
        )
        info = legacy.validate_regular_descriptor(
            file_fd,
            relative_path,
            owner_only=True,
        )
        if info.st_size != len(expected_payload):
            raise COMMON.Wave2Failure("E_TOCTOU", "readback")
        read_exact_published_payload(file_fd, expected_payload)
        return {
            "legacy": legacy,
            "parentFd": parent_fd,
            "fileFd": file_fd,
            "name": parts[-1],
            "path": relative_path,
            "payload": expected_payload,
            "identity": (
                info.st_dev,
                info.st_ino,
                stat.S_IMODE(info.st_mode),
                info.st_uid,
                info.st_nlink,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            ),
        }
    except BaseException:
        if file_fd >= 0:
            legacy.close_quietly(file_fd)
        legacy.close_quietly(parent_fd)
        raise


def revalidate_published_artifact(guard: Mapping[str, Any]) -> None:
    legacy = guard["legacy"]
    legacy.named_entry_matches_open_file(
        guard["parentFd"],
        guard["name"],
        guard["fileFd"],
        expected_link_count=1,
    )
    info = legacy.validate_regular_descriptor(
        guard["fileFd"],
        guard["path"],
        owner_only=True,
    )
    observed = (
        info.st_dev,
        info.st_ino,
        stat.S_IMODE(info.st_mode),
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )
    if observed != guard["identity"]:
        raise COMMON.Wave2Failure("E_TOCTOU", "readback")
    read_exact_published_payload(
        guard["fileFd"],
        guard["payload"],
    )


def close_published_artifact(guard: Mapping[str, Any]) -> None:
    legacy = guard["legacy"]
    legacy.close_quietly(guard["fileFd"])
    legacy.close_quietly(guard["parentFd"])


def validate_resource_pass(
    authority: Mapping[str, Any],
    *,
    retain_fds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    legacy = authority["legacy"]
    core = authority["core"]
    items = authority["items"]
    records = authority["receipt"]["sources"]
    limits = COMMON.archive_limits()
    root_fd = -1
    dependency_fd = -1
    wave_fd = -1
    final_fd = -1
    opened: list[int] = []
    retained = False
    try:
        root_fd = legacy.open_root_directory(
            authority["repositoryRootIdentity"]
        )
        dependency_fd = legacy.open_directory_chain(
            root_fd,
            legacy.validate_relative_path(str(COMMON.DEPENDENCY_PARENT)),
            create=False,
        )
        wave_fd = os.open(
            COMMON.WAVE_PARENT_NAME,
            legacy.directory_open_flags(),
            dir_fd=dependency_fd,
        )
        final_fd = os.open(
            COMMON.FINAL_DIRECTORY_NAME,
            legacy.directory_open_flags(),
            dir_fd=wave_fd,
        )
        wave_initial = os.fstat(wave_fd)
        final_initial = os.fstat(final_fd)
        if legacy.list_names(wave_fd) != [COMMON.FINAL_DIRECTORY_NAME]:
            raise COMMON.Wave2Failure(
                "E_OUTPUT_INVENTORY",
                "readback",
            )
        legacy.validate_directory_descriptor(
            final_fd,
            COMMON.FINAL_DIRECTORY_NAME,
            owner_only=True,
        )
        if legacy.list_names(final_fd) != COMMON.expected_resource_names(items):
            raise COMMON.Wave2Failure(
                "E_OUTPUT_INVENTORY",
                "readback",
            )
        aggregate_mod = 0
        aggregate_zip = 0
        aggregate_entries = 0
        aggregate_uncompressed = 0
        rows: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        for item, record in zip(items, records):
            exact_source_record(item, record)
            mod_size = record.get("modRawByteSize")
            zip_size = record.get("zipRawByteSize")
            if (
                type(mod_size) is not int
                or not 0 < mod_size <= COMMON.MAXIMUM_MOD_BYTES
                or type(zip_size) is not int
                or not 0 < zip_size <= COMMON.MAXIMUM_ZIP_BYTES
            ):
                raise COMMON.Wave2Failure(
                    "E_RESOURCE_SIZE",
                    "readback",
                )
            mod_fd, mod_raw = read_resource_twice(
                legacy,
                final_fd,
                item["modOutputFileName"],
                mod_size,
                COMMON.MAXIMUM_MOD_BYTES,
            )
            opened.append(mod_fd)
            zip_fd, zip_raw = read_resource_twice(
                legacy,
                final_fd,
                item["zipOutputFileName"],
                zip_size,
                COMMON.MAXIMUM_ZIP_BYTES,
            )
            opened.append(zip_fd)
            for kind, name, fd in (
                ("mod", item["modOutputFileName"], mod_fd),
                ("zip", item["zipOutputFileName"], zip_fd),
            ):
                info = os.fstat(fd)
                identities.append(
                    {
                        "order": item["order"],
                        "kind": kind,
                        "name": name,
                        "device": info.st_dev,
                        "inode": info.st_ino,
                        "mode": stat.S_IMODE(info.st_mode),
                        "uid": info.st_uid,
                        "linkCount": info.st_nlink,
                        "size": info.st_size,
                        "mtimeNs": info.st_mtime_ns,
                        "ctimeNs": info.st_ctime_ns,
                    }
                )
            if (
                COMMON.sha256_bytes(mod_raw) != record.get("modRawSha256")
                or COMMON.sha256_bytes(zip_raw)
                != record.get("zipRawSha256")
            ):
                raise COMMON.Wave2Failure(
                    "E_RESOURCE_SHA256",
                    "readback",
                )
            mod_validation = core.validate_mod_bytes(
                mod_raw,
                item,
                legacy,
            )
            archive = core.inspect_module_zip_v3(
                legacy,
                zip_fd,
                item,
                limits,
                aggregate_entries_before=aggregate_entries,
                aggregate_uncompressed_before=aggregate_uncompressed,
                external_go_mod=mod_raw,
            )
            if (
                mod_validation["goModH1"] != record["goModH1"]
                or archive["moduleZipH1"] != record["moduleZipH1"]
                or archive["entryCount"] != record.get("entryCount")
                or archive["uncompressedByteCount"]
                != record.get("uncompressedByteCount")
                or archive["embeddedGoModPresent"]
                is not record.get("embeddedGoModPresent")
                or archive["embeddedGoModByteParity"] is not True
                or archive["modulePrefix"] != record.get("modulePrefix")
                or archive["compressionTelemetry"]["ratioLimitPassed"]
                is not True
            ):
                raise COMMON.Wave2Failure(
                    "E_RESOURCE_H1",
                    "readback",
                )
            aggregate_mod += mod_size
            aggregate_zip += zip_size
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
            if (
                aggregate_mod + aggregate_zip
                > COMMON.MAXIMUM_AGGREGATE_RESPONSE_BYTES
            ):
                raise COMMON.Wave2Failure(
                    "E_AGGREGATE_RESPONSE_TOO_LARGE",
                    "readback",
                )
            rows.append(dict(record))
        guard = {
            "legacy": legacy,
            "rootFd": root_fd,
            "dependencyFd": dependency_fd,
            "waveFd": wave_fd,
            "finalFd": final_fd,
            "waveIdentity": wave_initial,
            "finalIdentity": final_initial,
            "resourceFds": opened,
            "identities": identities,
            "expectedResourceNames": COMMON.expected_resource_names(items),
        }
        revalidate_retained_resource_pass(guard)
        result = {
            "orderedSourceSetSha256": (
                COMMON.ordered_source_set_sha256(rows)
            ),
            "aggregateModRawByteSize": aggregate_mod,
            "aggregateZipRawByteSize": aggregate_zip,
            "aggregateRawByteSize": aggregate_mod + aggregate_zip,
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedByteCount": aggregate_uncompressed,
            "resourceCount": 30,
            "tupleCount": 15,
            "resourceIdentitySetSha256": COMMON.sha256_bytes(
                COMMON.canonical_json_bytes(identities)
            ),
        }
        if retain_fds is not None:
            if retain_fds:
                raise COMMON.Wave2Failure("E_INTERNAL", "readback")
            retain_fds.update(guard)
            retained = True
        return result
    finally:
        if not retained:
            for fd in opened:
                legacy.close_quietly(fd)
            for fd in (final_fd, wave_fd, dependency_fd, root_fd):
                if fd >= 0:
                    legacy.close_quietly(fd)


def check_loaded(authority: Mapping[str, Any]) -> dict[str, Any]:
    first = validate_resource_pass(authority)
    authority["inputs"].final_barrier()
    second = validate_resource_pass(authority)
    authority["inputs"].final_barrier()
    if first != second:
        raise COMMON.Wave2Failure("E_TOCTOU", "readback")
    receipt = authority["receipt"]
    if (
        first["orderedSourceSetSha256"]
        != receipt.get("orderedSourceSetSha256")
        or first["aggregateModRawByteSize"]
        != receipt.get("aggregateModRawByteSize")
        or first["aggregateZipRawByteSize"]
        != receipt.get("aggregateZipRawByteSize")
        or first["aggregateRawByteSize"]
        != receipt.get("aggregateRawByteSize")
        or first["aggregateEntryCount"]
        != receipt.get("aggregateEntryCount")
        or first["aggregateUncompressedByteCount"]
        != receipt.get("aggregateUncompressedByteCount")
    ):
        raise COMMON.Wave2Failure(
            "E_ACQUISITION_RECEIPT",
            "readback",
        )
    return {
        "status": "wave2_v1_independent_readback_passed_not_recorded",
        "result": "exact_30_retained_resources_reopened_twice_and_h1_verified",
        "permitId": authority["permit"]["permitId"],
        "decisionId": authority["decision"]["decisionId"],
        "claimRawSha256": COMMON.sha256_bytes(
            authority["claimRaw"]
        ),
        "acquisitionReceiptRawSha256": COMMON.sha256_bytes(
            authority["receiptRaw"]
        ),
        "acquisitionManifestRawSha256": COMMON.sha256_bytes(
            authority["manifestRaw"]
        ),
        **first,
        "stableReadPassCount": 2,
        "networkUsed": False,
        "sourceExtractionUsed": False,
        "sourceExecutionUsed": False,
        "freshChecksumDatabaseProof": False,
        "dependencyFixedPointReached": False,
        "dependencySourceReviewed": False,
        "candidateSelected": False,
        "librarySelected": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "record_wave2_v1_readback_receipt_then_manifest",
    }


def check() -> dict[str, Any]:
    authority = load_authority()
    try:
        return check_loaded(authority)
    finally:
        authority["inputs"].close()


def record() -> dict[str, Any]:
    if (
        (ROOT / COMMON.READBACK_RECEIPT_PATH).exists()
        or (ROOT / COMMON.READBACK_RECEIPT_PATH).is_symlink()
        or (ROOT / COMMON.READBACK_MANIFEST_PATH).exists()
        or (ROOT / COMMON.READBACK_MANIFEST_PATH).is_symlink()
    ):
        raise COMMON.Wave2Failure(
            "E_READBACK_NAMESPACE",
            "readback",
        )
    authority = load_authority()
    root_fd = -1
    publication_guard: dict[str, Any] = {}
    published_artifact_guards: list[dict[str, Any]] = []
    try:
        checked = check_loaded(authority)
        final_pass = validate_resource_pass(
            authority,
            retain_fds=publication_guard,
        )
        for key, value in final_pass.items():
            if checked.get(key) != value:
                raise COMMON.Wave2Failure("E_TOCTOU", "readback")
        checked["stableReadPassCount"] = 3
        authority["inputs"].final_barrier()
        revalidate_retained_resource_pass(publication_guard)
        root_fd = authority["legacy"].open_root_directory(
            authority["repositoryRootIdentity"]
        )
        receipt_payload = {
            **checked,
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-"
                "independent-readback-receipt"
            ),
            "schemaVersion": "1.0",
            "status": "wave2_v1_independent_readback_complete",
            "result": (
                "exact_30_retained_resources_reopened_three_times_and_h1_"
                "verified"
            ),
            "independentReadbackPassed": True,
            "nextAction": (
                "publish_wave2_v1_readback_manifest_then_rerun_"
                "combined_fixed_point_graph"
            ),
        }
        receipt_raw = COMMON.canonical_json_bytes(receipt_payload)
        receipt_sha256 = authority["legacy"].write_repo_relative_artifact(
            root_fd,
            COMMON.READBACK_RECEIPT_PATH,
            receipt_raw,
            COMMON.MAXIMUM_JSON_BYTES,
        )
        if receipt_sha256 != COMMON.sha256_bytes(receipt_raw):
            raise COMMON.Wave2Failure("E_TOCTOU", "readback")
        receipt_guard = open_published_artifact(
            root_fd,
            COMMON.READBACK_RECEIPT_PATH,
            receipt_raw,
            authority["legacy"],
        )
        published_artifact_guards.append(receipt_guard)
        authority["inputs"].final_barrier()
        revalidate_retained_resource_pass(publication_guard)
        revalidate_published_artifact(receipt_guard)
        manifest = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-"
                "independent-readback-manifest"
            ),
            "schemaVersion": "1.0",
            "status": "wave2_v1_independent_readback_published",
            "result": "readback_receipt_published_then_manifest_written_last",
            "permitId": authority["permit"]["permitId"],
            "decisionId": authority["decision"]["decisionId"],
            "readbackReceiptPath": COMMON.READBACK_RECEIPT_PATH,
            "readbackReceiptRawSha256": receipt_sha256,
            "acquisitionManifestPath": COMMON.MANIFEST_PATH,
            "acquisitionManifestRawSha256": COMMON.sha256_bytes(
                authority["manifestRaw"]
            ),
            "resourceCount": 30,
            "tupleCount": 15,
            "stableReadPassCount": 3,
            "manifestWrittenLast": True,
            "independentReadbackPassed": True,
            "networkUsed": False,
            "sourceExtractionUsed": False,
            "sourceExecutionUsed": False,
            "freshChecksumDatabaseProof": False,
            "dependencyFixedPointReached": False,
            "dependencySourceReviewed": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "rerun_combined_wave1_wave2_fixed_point_dependency_graph"
            ),
        }
        manifest_raw = COMMON.canonical_json_bytes(manifest)
        manifest_sha256 = authority["legacy"].write_repo_relative_artifact(
            root_fd,
            COMMON.READBACK_MANIFEST_PATH,
            manifest_raw,
            COMMON.MAXIMUM_JSON_BYTES,
        )
        if manifest_sha256 != COMMON.sha256_bytes(manifest_raw):
            raise COMMON.Wave2Failure("E_TOCTOU", "readback")
        manifest_guard = open_published_artifact(
            root_fd,
            COMMON.READBACK_MANIFEST_PATH,
            manifest_raw,
            authority["legacy"],
        )
        published_artifact_guards.append(manifest_guard)
        authority["inputs"].final_barrier()
        revalidate_retained_resource_pass(publication_guard)
        revalidate_published_artifact(receipt_guard)
        revalidate_published_artifact(manifest_guard)
        return {
            "status": "wave2_v1_independent_readback_published",
            "readbackReceiptRawSha256": receipt_sha256,
            "readbackManifestRawSha256": manifest_sha256,
            "resourceCount": 30,
            "tupleCount": 15,
            "networkUsed": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "rerun_combined_wave1_wave2_fixed_point_dependency_graph"
            ),
        }
    finally:
        for artifact_guard in reversed(published_artifact_guards):
            close_published_artifact(artifact_guard)
        if publication_guard:
            close_retained_resource_pass(publication_guard)
        if root_fd >= 0:
            os.close(root_fd)
        authority["inputs"].close()


def error_document(failure: Any) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave2-v1-readback-error"
        ),
        "schemaVersion": "1.0",
        "status": "failed",
        "failureCode": failure.code,
        "phase": failure.phase,
        "networkUsed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="perform the read-only independent readback (default)",
    )
    group.add_argument(
        "--record",
        action="store_true",
        help="write the readback receipt and manifest after a fresh check",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = record() if args.record else check()
    except COMMON.Wave2Failure as failure:
        print(json.dumps(error_document(failure), indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
