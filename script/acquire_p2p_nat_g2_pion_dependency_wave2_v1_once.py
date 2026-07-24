#!/usr/bin/env python3
"""Acquire the exact G2 Pion dependency wave-two MOD+ZIP set exactly once.

The default mode is a read-only preflight.  ``--execute`` is accepted only
after the separate wave-two permit checker validates the exact 15 tuples,
30 ordered public Go proxy requests, tool identities, repository root, and a
fresh namespace.  No account login, owner proof, credential, or user action is
part of this personal-project workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
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
THIS_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave2_v1_once.py"
)

EXPECTED_COMMON_RAW_SHA256 = (
    "dc25ddd3a82789bddccbd6ec57a71edc389225e003d7a73e6d371a640937f8c1"
)
EXPECTED_PERMIT_CHECKER_RAW_SHA256 = (
    "608cc5c067f1f48b95cfcfe69a5deb8a0a67c527bbfe8e2b844da47b048df7d4"
)
EXPECTED_PERMIT_STATUS = (
    "wave2_v1_dependency_source_acquisition_authorized_not_consumed"
)
EXPECTED_PERMIT_RESULT = (
    "exact_15_public_proxy_mod_then_zip_pairs_authorized_once_not_executed"
)
EXPECTED_PERMIT_NEXT_ACTION = (
    "execute_bound_dependency_source_wave2_v1_once"
)
EXPECTED_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave2-execution-permit-v1"
)
PER_REQUEST_DEADLINE_MILLISECONDS = 30_000
WHOLE_WAVE_DEADLINE_MILLISECONDS = 600_000
EXPECTED_ACQUISITION_REGULAR_FILE_COUNT = 33
READBACK_RECEIPT_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "result",
    "permitId",
    "decisionId",
    "claimRawSha256",
    "acquisitionReceiptRawSha256",
    "acquisitionManifestRawSha256",
    "orderedSourceSetSha256",
    "aggregateModRawByteSize",
    "aggregateZipRawByteSize",
    "aggregateRawByteSize",
    "aggregateEntryCount",
    "aggregateUncompressedByteCount",
    "resourceCount",
    "tupleCount",
    "resourceIdentitySetSha256",
    "stableReadPassCount",
    "networkUsed",
    "sourceExtractionUsed",
    "sourceExecutionUsed",
    "freshChecksumDatabaseProof",
    "dependencyFixedPointReached",
    "dependencySourceReviewed",
    "candidateSelected",
    "librarySelected",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
    "independentReadbackPassed",
}
READBACK_MANIFEST_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "result",
    "permitId",
    "decisionId",
    "readbackReceiptPath",
    "readbackReceiptRawSha256",
    "acquisitionManifestPath",
    "acquisitionManifestRawSha256",
    "resourceCount",
    "tupleCount",
    "stableReadPassCount",
    "manifestWrittenLast",
    "independentReadbackPassed",
    "networkUsed",
    "sourceExtractionUsed",
    "sourceExecutionUsed",
    "freshChecksumDatabaseProof",
    "dependencyFixedPointReached",
    "dependencySourceReviewed",
    "candidateSelected",
    "librarySelected",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
}


def bootstrap_read(relative: str, expected_sha256: str) -> bytes:
    """Read one bootstrap tool with no-follow and exact byte identity."""
    path = ROOT / relative
    current = ROOT
    for component in relative.split("/")[:-1]:
        current /= component
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
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
        raw = b""
        while len(raw) <= before.st_size:
            chunk = os.read(fd, min(65_536, before.st_size + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        after = os.fstat(fd)
        if (
            len(raw) != before.st_size
            or hashlib.sha256(raw).hexdigest() != expected_sha256
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
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
            "__cached__": None,
            "__file__": str(ROOT / relative),
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
    "g2_wave2_common_trust_root",
    COMMON_PATH,
    bootstrap_read(COMMON_PATH, EXPECTED_COMMON_RAW_SHA256),
)


class AttemptCountingOpener:
    def __init__(self, delegate: Any, counters: dict[str, int]) -> None:
        self.delegate = delegate
        self.counters = counters

    def open(self, request: Any, *, timeout: float) -> Any:
        self.counters["networkRequestAttemptCount"] += 1
        COMMON.validate_counters(self.counters)
        return self.delegate.open(request, timeout=timeout)


def terminal_artifact_bindings(
    terminal_state: str | None,
) -> list[dict[str, Any]]:
    if terminal_state is None or terminal_state == "clean":
        return []
    claim_path = (
        f"{COMMON.DEPENDENCY_PARENT.as_posix()}/{COMMON.CLAIM_NAME}"
    )
    if terminal_state == "failure":
        paths = (claim_path, COMMON.FAILURE_RECEIPT_PATH)
    elif terminal_state == "success":
        paths = (
            claim_path,
            COMMON.SUCCESS_RECEIPT_PATH,
            COMMON.MANIFEST_PATH,
        )
    elif terminal_state == "readback_complete":
        paths = (
            claim_path,
            COMMON.SUCCESS_RECEIPT_PATH,
            COMMON.MANIFEST_PATH,
            COMMON.READBACK_RECEIPT_PATH,
            COMMON.READBACK_MANIFEST_PATH,
        )
    else:
        raise COMMON.Wave2Failure("E_ONE_USE_STATE_PRESENT", "preflight")
    return [
        {
            "path": path,
            "maximumBytes": (
                64 * 1024
                if path == claim_path
                else COMMON.MAXIMUM_JSON_BYTES
            ),
            "ownerOnly": True,
        }
        for path in paths
    ]


def authority_bindings(
    terminal_state: str | None = None,
) -> list[dict[str, Any]]:
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
            "path": THIS_RUNNER_PATH,
            "maximumBytes": COMMON.MAXIMUM_TOOL_BYTES,
        },
        *terminal_artifact_bindings(terminal_state),
    ]


def load_authority(
    *,
    require_clean_namespace: bool,
    terminal_state: str | None = None,
) -> dict[str, Any]:
    if sys.flags.isolated != 1 or not sys.dont_write_bytecode:
        raise COMMON.Wave2Failure("E_INTERPRETER", "preflight")
    try:
        inputs = COMMON.HeldInputSet(
            ROOT,
            authority_bindings(terminal_state),
        )
    except Exception as error:
        if isinstance(error, COMMON.Wave2Failure):
            raise
        raise COMMON.Wave2Failure("E_TOOL_IDENTITY", "preflight") from error
    try:
        checker = COMMON.execute_fixed_module(
            "g2_wave2_permit_checker_trust_root",
            PERMIT_CHECKER_PATH,
            inputs.raw(PERMIT_CHECKER_PATH),
            ROOT,
        )
        try:
            checked = checker.validate_repository(
                ROOT,
                require_clean_namespace=require_clean_namespace,
            )
        except Exception as error:
            raise COMMON.Wave2Failure(
                "E_PERMIT_VALIDATION",
                "preflight",
            ) from error
        permit = checked.get("permit")
        decision = checked.get("decision")
        root_identity = checked.get("repositoryRootIdentity")
        if (
            type(permit) is not dict
            or type(decision) is not dict
            or type(root_identity) is not dict
            or checked.get("executionAuthorized") is not True
            or permit.get("permitId") != EXPECTED_PERMIT_ID
            or permit.get("status") != EXPECTED_PERMIT_STATUS
            or permit.get("result") != EXPECTED_PERMIT_RESULT
            or permit.get("nextAction") != EXPECTED_PERMIT_NEXT_ACTION
            or permit.get("personalProjectBoundary", {}).get(
                "externalAuthenticationRequired"
            )
            is not False
            or permit.get("personalProjectBoundary", {}).get(
                "userActionRequired"
            )
            is not False
        ):
            raise COMMON.Wave2Failure("E_PERMIT_STATE", "preflight")
        permit_raw = inputs.raw(PERMIT_PATH)
        if COMMON.strict_json(permit_raw, PERMIT_PATH) != permit:
            raise COMMON.Wave2Failure("E_PERMIT_STATE", "preflight")
        runner_raw = inputs.raw(THIS_RUNNER_PATH)
        tool_bindings = {
            row.get("role"): row
            for row in permit.get("toolBindings", [])
            if type(row) is dict
        }
        runner_binding = tool_bindings.get("wave2_v1_runner")
        if (
            type(runner_binding) is not dict
            or runner_binding.get("path") != THIS_RUNNER_PATH
            or runner_binding.get("rawSha256")
            != COMMON.sha256_bytes(runner_raw)
        ):
            raise COMMON.Wave2Failure("E_PERMIT_STATE", "preflight")
        items = COMMON.adapt_tuples(decision)
        legacy, core = COMMON.configure_primitives(inputs, ROOT)
        inputs.final_barrier()
        return {
            "inputs": inputs,
            "permit": permit,
            "permitRawSha256": COMMON.sha256_bytes(permit_raw),
            "decision": decision,
            "items": items,
            "legacy": legacy,
            "core": core,
            "repositoryRootIdentity": root_identity,
        }
    except BaseException:
        inputs.close()
        raise


def path_exists(path: Path) -> bool:
    try:
        os.lstat(path)
        return True
    except FileNotFoundError:
        return False
    except OSError as error:
        raise COMMON.Wave2Failure("E_NAMESPACE", "preflight") from error


def staging_names() -> list[str]:
    parent = ROOT / str(COMMON.DEPENDENCY_PARENT)
    try:
        return sorted(
            name
            for name in os.listdir(parent)
            if name.startswith(COMMON.STAGING_PREFIX)
        )
    except OSError as error:
        raise COMMON.Wave2Failure("E_NAMESPACE", "preflight") from error


def classify_state() -> str:
    paths = COMMON.namespace_exact_paths(ROOT)
    present = {name: path_exists(path) for name, path in paths.items()}
    staging = staging_names()
    clean = not any(present.values()) and not staging
    success_base = (
        present["claim"]
        and present["waveParent"]
        and present["final"]
        and present["success"]
        and present["manifest"]
        and not present["failure"]
        and not staging
    )
    success = (
        success_base
        and not present["readback"]
        and not present["readbackManifest"]
    )
    readback_complete = (
        success_base
        and present["readback"]
        and present["readbackManifest"]
    )
    failure = (
        present["claim"]
        and not present["final"]
        and not present["success"]
        and present["failure"]
        and not present["manifest"]
        and not present["readback"]
        and not present["readbackManifest"]
        and not staging
    )
    if clean:
        return "clean"
    if success:
        return "success"
    if readback_complete:
        return "readback_complete"
    if failure:
        return "failure"
    return "blocked"


def read_bound_owner_json(
    authority: Mapping[str, Any],
    relative: str,
) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = authority["inputs"].raw(relative)
        document = COMMON.strict_json(raw, relative)
    except Exception as error:
        raise COMMON.Wave2Failure("E_TERMINAL_STATE", "preflight") from error
    return raw, document


def is_sha256_hex(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_readback_terminal(
    authority: Mapping[str, Any],
    acquisition_receipt_raw: bytes,
    acquisition_receipt: Mapping[str, Any],
    acquisition_manifest_raw: bytes,
    acquisition_manifest: Mapping[str, Any],
    readback_raw: bytes,
    readback: Mapping[str, Any],
    readback_manifest: Mapping[str, Any],
) -> None:
    permit = authority["permit"]
    decision = authority["decision"]
    false_fields = (
        "networkUsed",
        "sourceExtractionUsed",
        "sourceExecutionUsed",
        "freshChecksumDatabaseProof",
        "dependencyFixedPointReached",
        "dependencySourceReviewed",
        "candidateSelected",
        "librarySelected",
        "repositoryOwnerIdentityProofRequired",
        "externalAuthenticationRequired",
        "userActionRequired",
    )
    aggregate_fields = (
        "aggregateModRawByteSize",
        "aggregateZipRawByteSize",
        "aggregateRawByteSize",
        "aggregateEntryCount",
        "aggregateUncompressedByteCount",
    )
    acquisition_manifest_sha256 = COMMON.sha256_bytes(
        acquisition_manifest_raw
    )
    if (
        set(readback) != READBACK_RECEIPT_KEYS
        or set(readback_manifest) != READBACK_MANIFEST_KEYS
        or readback.get("documentType")
        != (
            "aetherlink.g2-pion-dependency-wave2-v1-"
            "independent-readback-receipt"
        )
        or readback.get("schemaVersion") != "1.0"
        or readback.get("status")
        != "wave2_v1_independent_readback_complete"
        or readback.get("result")
        != (
            "exact_30_retained_resources_reopened_three_times_and_h1_"
            "verified"
        )
        or readback.get("permitId") != permit["permitId"]
        or readback.get("decisionId") != decision["decisionId"]
        or readback.get("claimRawSha256")
        != acquisition_receipt.get("claimRawSha256")
        or readback.get("acquisitionReceiptRawSha256")
        != COMMON.sha256_bytes(acquisition_receipt_raw)
        or readback.get("acquisitionManifestRawSha256")
        != acquisition_manifest_sha256
        or readback.get("orderedSourceSetSha256")
        != acquisition_receipt.get("orderedSourceSetSha256")
        or any(
            readback.get(name) != acquisition_receipt.get(name)
            for name in aggregate_fields
        )
        or readback.get("resourceCount") != 30
        or readback.get("tupleCount") != 15
        or not is_sha256_hex(readback.get("resourceIdentitySetSha256"))
        or readback.get("stableReadPassCount") != 3
        or readback.get("independentReadbackPassed") is not True
        or any(readback.get(name) is not False for name in false_fields)
        or readback.get("nextAction")
        != (
            "publish_wave2_v1_readback_manifest_then_rerun_"
            "combined_fixed_point_graph"
        )
        or readback_manifest.get("documentType")
        != (
            "aetherlink.g2-pion-dependency-wave2-v1-"
            "independent-readback-manifest"
        )
        or readback_manifest.get("schemaVersion") != "1.0"
        or readback_manifest.get("status")
        != "wave2_v1_independent_readback_published"
        or readback_manifest.get("result")
        != "readback_receipt_published_then_manifest_written_last"
        or readback_manifest.get("permitId") != permit["permitId"]
        or readback_manifest.get("decisionId") != decision["decisionId"]
        or readback_manifest.get("readbackReceiptPath")
        != COMMON.READBACK_RECEIPT_PATH
        or readback_manifest.get("readbackReceiptRawSha256")
        != COMMON.sha256_bytes(readback_raw)
        or readback_manifest.get("acquisitionManifestPath")
        != COMMON.MANIFEST_PATH
        or readback_manifest.get("acquisitionManifestRawSha256")
        != acquisition_manifest_sha256
        or readback_manifest.get("resourceCount") != 30
        or readback_manifest.get("tupleCount") != 15
        or readback_manifest.get("stableReadPassCount") != 3
        or readback_manifest.get("manifestWrittenLast") is not True
        or readback_manifest.get("independentReadbackPassed") is not True
        or any(
            readback_manifest.get(name) is not False
            for name in false_fields
        )
        or readback_manifest.get("nextAction")
        != "rerun_combined_wave1_wave2_fixed_point_dependency_graph"
        or acquisition_manifest.get("orderedSourceSetSha256")
        != acquisition_receipt.get("orderedSourceSetSha256")
    ):
        raise COMMON.Wave2Failure("E_TERMINAL_STATE", "preflight")


def validate_claim_and_terminal(
    authority: Mapping[str, Any],
    classification: str,
) -> None:
    if classification == "clean":
        return
    if classification not in {"success", "readback_complete", "failure"}:
        raise COMMON.Wave2Failure("E_ONE_USE_STATE_PRESENT", "preflight")
    legacy = authority["legacy"]
    permit = authority["permit"]
    claim_path = (
        f"{COMMON.DEPENDENCY_PARENT.as_posix()}/{COMMON.CLAIM_NAME}"
    )
    claim_raw, claim = read_bound_owner_json(authority, claim_path)
    if (
        claim.get("claimType")
        != "aetherlink.g2-pion-dependency-wave2-v1-one-use-claim"
        or claim.get("schemaVersion") != "1.0"
        or claim.get("permitId") != permit["permitId"]
        or claim.get("permitContentSha256")
        != permit["contentBinding"]["sha256"]
        or claim.get("decisionContentSha256")
        != COMMON.EXPECTED_DECISION_CONTENT_SHA256
        or type(claim.get("attemptId")) is not str
        or len(claim["attemptId"]) != 32
    ):
        raise COMMON.Wave2Failure("E_CLAIM_STATE", "preflight")
    claim_sha256 = COMMON.sha256_bytes(claim_raw)
    artifact_path = (
        COMMON.FAILURE_RECEIPT_PATH
        if classification == "failure"
        else COMMON.SUCCESS_RECEIPT_PATH
    )
    artifact_raw, artifact = read_bound_owner_json(
        authority,
        artifact_path,
    )
    if (
        artifact.get("permitId") != permit["permitId"]
        or artifact.get("permitContentSha256")
        != permit["contentBinding"]["sha256"]
        or artifact.get("claimRawSha256") != claim_sha256
    ):
        raise COMMON.Wave2Failure("E_TERMINAL_STATE", "preflight")
    counters = {
        name: artifact.get(name)
        for name in COMMON.COUNTER_NAMES
    }
    COMMON.validate_counters(counters)
    if classification == "failure":
        wave_parent = ROOT / str(COMMON.DEPENDENCY_PARENT) / COMMON.WAVE_PARENT_NAME
        if path_exists(wave_parent):
            wave_fd = os.open(
                wave_parent,
                legacy.directory_open_flags(),
            )
            try:
                legacy.validate_directory_descriptor(
                    wave_fd,
                    COMMON.WAVE_PARENT_NAME,
                    owner_only=True,
                )
                if legacy.list_names(wave_fd):
                    raise COMMON.Wave2Failure(
                        "E_TERMINAL_STATE",
                        "preflight",
                    )
            finally:
                legacy.close_quietly(wave_fd)
        if (
            artifact.get("status")
            != "wave2_v1_acquisition_failed_permit_consumed"
            or artifact.get("acceptedArtifactCount") != 0
            or artifact.get("acceptedTupleCount") != 0
            or artifact.get("finalSetPublished") is not False
        ):
            raise COMMON.Wave2Failure("E_TERMINAL_STATE", "preflight")
        return
    if (
        artifact.get("status") != "acquired_pending_independent_readback"
        or not COMMON.success_counters(counters)
        or artifact.get("acceptedArtifactCount") != 30
        or artifact.get("acceptedTupleCount") != 15
    ):
        raise COMMON.Wave2Failure("E_TERMINAL_STATE", "preflight")
    manifest_raw, manifest = read_bound_owner_json(
        authority,
        COMMON.MANIFEST_PATH,
    )
    if (
        manifest.get("successReceiptPath") != COMMON.SUCCESS_RECEIPT_PATH
        or manifest.get("successReceiptRawSha256")
        != COMMON.sha256_bytes(artifact_raw)
        or manifest.get("finalDirectoryPath")
        != COMMON.FINAL_DIRECTORY_PATH
        or manifest.get("manifestWrittenLast") is not True
    ):
        raise COMMON.Wave2Failure("E_TERMINAL_STATE", "preflight")
    if classification == "readback_complete":
        readback_raw, readback = read_bound_owner_json(
            authority,
            COMMON.READBACK_RECEIPT_PATH,
        )
        readback_manifest_raw, readback_manifest = read_bound_owner_json(
            authority,
            COMMON.READBACK_MANIFEST_PATH,
        )
        del readback_manifest_raw
        validate_readback_terminal(
            authority,
            artifact_raw,
            artifact,
            manifest_raw,
            manifest,
            readback_raw,
            readback,
            readback_manifest,
        )
    final_fd = os.open(
        ROOT / COMMON.FINAL_DIRECTORY_PATH,
        legacy.directory_open_flags(),
    )
    try:
        wave_parent_fd = os.open(
            ROOT
            / str(COMMON.DEPENDENCY_PARENT)
            / COMMON.WAVE_PARENT_NAME,
            legacy.directory_open_flags(),
        )
        try:
            if legacy.list_names(wave_parent_fd) != [
                COMMON.FINAL_DIRECTORY_NAME
            ]:
                raise COMMON.Wave2Failure(
                    "E_OUTPUT_INVENTORY",
                    "preflight",
                )
        finally:
            legacy.close_quietly(wave_parent_fd)
        legacy.validate_directory_descriptor(
            final_fd,
            COMMON.FINAL_DIRECTORY_NAME,
            owner_only=True,
        )
        if legacy.list_names(final_fd) != COMMON.expected_resource_names(
            authority["items"]
        ):
            raise COMMON.Wave2Failure(
                "E_OUTPUT_INVENTORY",
                "preflight",
            )
    finally:
        os.close(final_fd)


def preflight() -> dict[str, Any]:
    initial = classify_state()
    authority = load_authority(
        require_clean_namespace=initial == "clean",
        terminal_state=initial,
    )
    try:
        classification = classify_state()
        if classification != initial:
            raise COMMON.Wave2Failure("E_TOCTOU", "preflight")
        validate_claim_and_terminal(authority, classification)
        authority["inputs"].final_barrier()
        if classification == "clean":
            status = "passed"
            consumption = "authorized_not_consumed"
            next_action = EXPECTED_PERMIT_NEXT_ACTION
        elif classification == "success":
            status = "consumed_success_pending_independent_readback"
            consumption = "consumed_success"
            next_action = "run_separate_wave2_v1_independent_readback"
        elif classification == "readback_complete":
            status = "consumed_success_independent_readback_complete"
            consumption = "consumed_success"
            next_action = (
                "rerun_combined_wave1_wave2_fixed_point_dependency_graph"
            )
        elif classification == "failure":
            status = "consumed_failure_recovery_required"
            consumption = "consumed_failure"
            next_action = "prepare_new_versioned_wave2_recovery_decision"
        else:
            raise COMMON.Wave2Failure(
                "E_ONE_USE_STATE_PRESENT",
                "preflight",
            )
        return {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-runner-preflight"
            ),
            "schemaVersion": "1.0",
            "status": status,
            "validationPassed": classification
            in {"clean", "success", "readback_complete"},
            "permitId": authority["permit"]["permitId"],
            **COMMON.zero_counters(),
            "fileWriteCount": 0,
            "networkOperationCount": 0,
            "permitConsumptionState": consumption,
            "oneUseState": classification,
            "expectedAcquisitionRegularFileCount": (
                EXPECTED_ACQUISITION_REGULAR_FILE_COUNT
            ),
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": next_action,
        }
    finally:
        authority["inputs"].close()


def create_claim(
    legacy: types.ModuleType,
    parent_fd: int,
    permit: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> tuple[str, str]:
    attempt_id = secrets.token_hex(16)
    payload = COMMON.canonical_json_bytes(
        {
            "claimType": (
                "aetherlink.g2-pion-dependency-wave2-v1-one-use-claim"
            ),
            "schemaVersion": "1.0",
            "attemptId": attempt_id,
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "decisionId": decision["decisionId"],
            "decisionContentSha256": (
                COMMON.EXPECTED_DECISION_CONTENT_SHA256
            ),
            "orderedResourceSetSha256": decision["wave"][
                "orderedResourceSetSha256"
            ],
            "createdAt": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(),
            ),
            "rule": (
                "claim_persists_after_any_network_attempt_and_blocks_retry"
            ),
            "automaticRetryAllowed": False,
            "userActionRequired": False,
        }
    )
    digest = legacy.create_exclusive_file(
        parent_fd,
        COMMON.CLAIM_NAME,
        payload,
        maximum_bytes=64 * 1024,
    )
    return attempt_id, digest


def verify_named_claim(
    legacy: types.ModuleType,
    parent_fd: int,
    expected_sha256: str,
) -> None:
    fd = os.open(
        COMMON.CLAIM_NAME,
        legacy.file_open_flags(),
        dir_fd=parent_fd,
    )
    try:
        legacy.named_entry_matches_open_file(
            parent_fd,
            COMMON.CLAIM_NAME,
            fd,
            expected_link_count=1,
        )
        info = legacy.validate_regular_descriptor(
            fd,
            COMMON.CLAIM_NAME,
            owner_only=True,
        )
        if not 0 < info.st_size <= 64 * 1024:
            raise COMMON.Wave2Failure("E_CLAIM_STATE", "publication")
        os.lseek(fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                raise COMMON.Wave2Failure(
                    "E_CLAIM_STATE",
                    "publication",
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if (
            os.read(fd, 1) != b""
            or COMMON.sha256_bytes(b"".join(chunks)) != expected_sha256
        ):
            raise COMMON.Wave2Failure("E_CLAIM_STATE", "publication")
        legacy.named_entry_matches_open_file(
            parent_fd,
            COMMON.CLAIM_NAME,
            fd,
            expected_link_count=1,
        )
    finally:
        legacy.close_quietly(fd)


def verify_active_namespace(
    legacy: types.ModuleType,
    parent_fd: int,
    wave_parent_fd: int,
    staging_fd: int,
    staging_name: str,
    claim_sha256: str,
) -> None:
    verify_named_claim(legacy, parent_fd, claim_sha256)
    staging_named = os.stat(
        staging_name,
        dir_fd=parent_fd,
        follow_symlinks=False,
    )
    staging_opened = os.fstat(staging_fd)
    wave_named = os.stat(
        COMMON.WAVE_PARENT_NAME,
        dir_fd=parent_fd,
        follow_symlinks=False,
    )
    wave_opened = os.fstat(wave_parent_fd)
    if (
        not stat.S_ISDIR(staging_named.st_mode)
        or staging_named.st_dev != staging_opened.st_dev
        or staging_named.st_ino != staging_opened.st_ino
        or not stat.S_ISDIR(wave_named.st_mode)
        or wave_named.st_dev != wave_opened.st_dev
        or wave_named.st_ino != wave_opened.st_ino
        or legacy.list_names(wave_parent_fd)
        or staging_names() != [staging_name]
        or path_exists(ROOT / COMMON.SUCCESS_RECEIPT_PATH)
        or path_exists(ROOT / COMMON.FAILURE_RECEIPT_PATH)
        or path_exists(ROOT / COMMON.MANIFEST_PATH)
        or path_exists(ROOT / COMMON.READBACK_RECEIPT_PATH)
        or path_exists(ROOT / COMMON.READBACK_MANIFEST_PATH)
        or path_exists(ROOT / COMMON.FINAL_DIRECTORY_PATH)
    ):
        raise COMMON.Wave2Failure("E_NAMESPACE_COLLISION", "publication")


def failure_document(
    authority: Mapping[str, Any],
    failure: Any,
    counters: Mapping[str, int],
    *,
    claim_sha256: str,
) -> dict[str, Any]:
    COMMON.validate_counters(counters)
    allowed_codes = set(authority["core"].ALLOWED_FAILURE_CODES) | {
        "E_CLAIM_STATE",
        "E_COUNTER_INVARIANT",
        "E_INTERNAL",
        "E_NAMESPACE_COLLISION",
        "E_REQUEST_COUNT",
        "E_TOCTOU",
        "E_ZIP_COMPRESSION_RATIO",
    }
    failure_code = (
        failure.code if failure.code in allowed_codes else "E_INTERNAL"
    )
    if counters["networkRequestAttemptCount"] > 0 and (
        type(failure.request_ordinal) is not int
        or not 1 <= failure.request_ordinal <= 30
        or type(failure.tuple_id) is not str
        or not failure.tuple_id
        or type(failure.tuple_order) is not int
        or not 1 <= failure.tuple_order <= 15
        or failure.resource_kind not in {"mod", "zip"}
    ):
        raise COMMON.Wave2Failure("E_FAILURE_STATE", "execution")
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave2-v1-acquisition-failure"
        ),
        "schemaVersion": "1.0",
        "status": "wave2_v1_acquisition_failed_permit_consumed",
        "result": "no_wave2_dependency_source_set_accepted",
        "permitId": authority["permit"]["permitId"],
        "permitContentSha256": authority["permit"]["contentBinding"][
            "sha256"
        ],
        "decisionId": authority["decision"]["decisionId"],
        "decisionContentSha256": COMMON.EXPECTED_DECISION_CONTENT_SHA256,
        "failureCode": failure_code,
        "phase": failure.phase,
        "failedRequestOrdinal": failure.request_ordinal,
        "failedTupleId": failure.tuple_id,
        "failedTupleOrder": failure.tuple_order,
        "failedResourceKind": failure.resource_kind,
        "safeNumericObservations": COMMON.bounded_observations(
            failure.observations
        ),
        **{name: counters[name] for name in COMMON.COUNTER_NAMES},
        "acceptedArtifactCount": 0,
        "acceptedTupleCount": 0,
        "claimRetained": True,
        "claimRawSha256": claim_sha256,
        "finalSetPublished": False,
        "automaticRetryAllowed": False,
        "rawErrorsBodiesHeadersCertificatesPathsOrEntryNamesRecorded": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "prepare_new_versioned_wave2_recovery_decision",
    }


def enforce_file_mode(
    fd: int,
    core: types.ModuleType,
    *,
    tuple_id: str,
    tuple_order: int,
    resource_kind: str,
) -> None:
    try:
        os.fchmod(fd, 0o600)
    except OSError as error:
        raise core.RunnerFailure(
            "E_FILESYSTEM_MODE",
            resource_kind,
            tuple_id=tuple_id,
            tuple_order=tuple_order,
            resource_kind=resource_kind,
        ) from error


def _execute_once_with_umask() -> dict[str, Any]:
    authority = load_authority(require_clean_namespace=True)
    legacy = authority["legacy"]
    core = authority["core"]
    permit = authority["permit"]
    decision = authority["decision"]
    items = authority["items"]
    inputs = authority["inputs"]
    counters = COMMON.zero_counters()
    root_fd = parent_fd = wave_parent_fd = staging_fd = -1
    staging_name: str | None = None
    claim_sha256: str | None = None
    claim_attempted = False
    publication_attempted = False
    held_outputs: list[dict[str, Any]] = []
    active_item: Mapping[str, Any] | None = None
    active_kind: str | None = None
    active_request_ordinal: int | None = None
    try:
        legacy.validate_hard_deadline_environment()
        root_fd = legacy.open_root_directory(
            authority["repositoryRootIdentity"]
        )
        COMMON.require_clean_namespace(ROOT)
        inputs.final_barrier()
        parent_parts = legacy.validate_relative_path(
            str(COMMON.DEPENDENCY_PARENT)
        )
        parent_fd = legacy.open_directory_chain(
            root_fd,
            parent_parts,
            create=False,
        )
        COMMON.require_clean_namespace(ROOT)
        inputs.final_barrier()
        claim_attempted = True
        _, claim_sha256 = create_claim(
            legacy,
            parent_fd,
            permit,
            decision,
        )
        wave_parent_fd = legacy.open_directory_chain(
            parent_fd,
            (COMMON.WAVE_PARENT_NAME,),
            create=True,
            owner_only_from=0,
        )
        staging_name = legacy.create_staging_directory(parent_fd)
        staging_fd = os.open(
            staging_name,
            legacy.directory_open_flags(),
            dir_fd=parent_fd,
        )
        legacy.validate_directory_descriptor(
            staging_fd,
            staging_name,
            owner_only=True,
        )
        verify_active_namespace(
            legacy,
            parent_fd,
            wave_parent_fd,
            staging_fd,
            staging_name,
            str(claim_sha256),
        )
        inputs.final_barrier()
        opener = AttemptCountingOpener(
            legacy.build_exact_opener(),
            counters,
        )
        wave_deadline = (
            time.monotonic()
            + WHOLE_WAVE_DEADLINE_MILLISECONDS / 1000
        )
        per_request_timeout = PER_REQUEST_DEADLINE_MILLISECONDS / 1000
        aggregate_mod_bytes = 0
        aggregate_zip_bytes = 0
        aggregate_entries = 0
        aggregate_uncompressed = 0
        limits = COMMON.archive_limits()
        rows: list[dict[str, Any]] = []

        for item in items:
            active_item = item
            tuple_id = str(item["tupleId"])
            tuple_order = int(item["order"])
            mod_name, zip_name = COMMON.output_names(item)
            active_kind = "mod"
            active_request_ordinal = int(item["modRequestOrdinal"])
            mod_temp = f".{tuple_order:03d}.mod.download"
            mod_fd = os.open(
                mod_temp,
                legacy.create_download_file_flags(),
                0o600,
                dir_fd=staging_fd,
            )
            keep_mod = False
            try:
                enforce_file_mode(
                    mod_fd,
                    core,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="mod",
                )
                mod_download = core.download_resource_once(
                    legacy,
                    opener,
                    item,
                    mod_fd,
                    resource_kind="mod",
                    url=item["modUrl"],
                    maximum_bytes=COMMON.MAXIMUM_MOD_BYTES,
                    aggregate_kind_before=aggregate_mod_bytes,
                    maximum_aggregate_kind_bytes=(
                        COMMON.MAXIMUM_AGGREGATE_RESPONSE_BYTES
                    ),
                    aggregate_total_before=(
                        aggregate_mod_bytes + aggregate_zip_bytes
                    ),
                    per_request_timeout_seconds=per_request_timeout,
                    wave_deadline=wave_deadline,
                )
                counters["responseBodyCompletedCount"] += 1
                COMMON.validate_counters(counters)
                mod_raw = core.read_exact_held_file(
                    legacy,
                    mod_fd,
                    mod_download["rawByteSize"],
                    maximum_bytes=COMMON.MAXIMUM_MOD_BYTES,
                )
                mod_validation = core.validate_mod_bytes(
                    mod_raw,
                    item,
                    legacy,
                )
                legacy.link_temp_to_final(
                    staging_fd,
                    mod_temp,
                    mod_name,
                    mod_fd,
                )
                held_outputs.append(
                    {
                        "fd": mod_fd,
                        "name": mod_name,
                        "resourceKind": "mod",
                        **mod_download,
                    }
                )
                keep_mod = True
                counters["validatedAndStagedResourceCount"] += 1
                counters["validatedModResourceCount"] += 1
                COMMON.validate_counters(counters)
            except Exception as error:
                raise COMMON.map_core_failure(
                    core,
                    error,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    request_ordinal=active_request_ordinal,
                    resource_kind="mod",
                    phase="mod",
                ) from None
            finally:
                if not keep_mod:
                    legacy.close_quietly(mod_fd)

            active_kind = "zip"
            active_request_ordinal = int(item["zipRequestOrdinal"])
            zip_temp = f".{tuple_order:03d}.zip.download"
            zip_fd = os.open(
                zip_temp,
                legacy.create_download_file_flags(),
                0o600,
                dir_fd=staging_fd,
            )
            keep_zip = False
            try:
                enforce_file_mode(
                    zip_fd,
                    core,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    resource_kind="zip",
                )
                zip_download = core.download_resource_once(
                    legacy,
                    opener,
                    item,
                    zip_fd,
                    resource_kind="zip",
                    url=item["url"],
                    maximum_bytes=COMMON.MAXIMUM_ZIP_BYTES,
                    aggregate_kind_before=aggregate_zip_bytes,
                    maximum_aggregate_kind_bytes=(
                        COMMON.MAXIMUM_AGGREGATE_RESPONSE_BYTES
                    ),
                    aggregate_total_before=(
                        aggregate_mod_bytes
                        + aggregate_zip_bytes
                        + mod_download["rawByteSize"]
                    ),
                    per_request_timeout_seconds=per_request_timeout,
                    wave_deadline=wave_deadline,
                )
                counters["responseBodyCompletedCount"] += 1
                COMMON.validate_counters(counters)
                archive = core.inspect_module_zip_v3(
                    legacy,
                    zip_fd,
                    item,
                    limits,
                    aggregate_entries_before=aggregate_entries,
                    aggregate_uncompressed_before=aggregate_uncompressed,
                    external_go_mod=mod_raw,
                )
                legacy.link_temp_to_final(
                    staging_fd,
                    zip_temp,
                    zip_name,
                    zip_fd,
                )
                held_outputs.append(
                    {
                        "fd": zip_fd,
                        "name": zip_name,
                        "resourceKind": "zip",
                        **zip_download,
                    }
                )
                keep_zip = True
                counters["validatedAndStagedResourceCount"] += 1
                counters["validatedZipResourceCount"] += 1
                counters["validatedAndStagedTupleCount"] += 1
                COMMON.validate_counters(counters)
            except Exception as error:
                raise COMMON.map_core_failure(
                    core,
                    error,
                    tuple_id=tuple_id,
                    tuple_order=tuple_order,
                    request_ordinal=active_request_ordinal,
                    resource_kind="zip",
                    phase="zip",
                ) from None
            finally:
                if not keep_zip:
                    legacy.close_quietly(zip_fd)

            aggregate_mod_bytes += mod_download["rawByteSize"]
            aggregate_zip_bytes += zip_download["rawByteSize"]
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
            rows.append(
                {
                    "order": tuple_order,
                    "tupleId": tuple_id,
                    "module": item["module"],
                    "version": item["version"],
                    "selectedByGraphAlgorithm": item[
                        "selectedByGraphAlgorithm"
                    ],
                    "modRequestOrdinal": item["modRequestOrdinal"],
                    "zipRequestOrdinal": item["zipRequestOrdinal"],
                    "modUrl": item["modUrl"],
                    "zipUrl": item["url"],
                    "modOutputFileName": mod_name,
                    "zipOutputFileName": zip_name,
                    "modRawByteSize": mod_download["rawByteSize"],
                    "modRawSha256": mod_download["rawSha256"],
                    "zipRawByteSize": zip_download["rawByteSize"],
                    "zipRawSha256": zip_download["rawSha256"],
                    "goModH1": mod_validation["goModH1"],
                    "moduleZipH1": archive["moduleZipH1"],
                    "entryCount": archive["entryCount"],
                    "uncompressedByteCount": archive[
                        "uncompressedByteCount"
                    ],
                    "modulePrefix": archive["modulePrefix"],
                    "embeddedGoModPresent": archive[
                        "embeddedGoModPresent"
                    ],
                    "embeddedGoModByteParity": archive[
                        "embeddedGoModByteParity"
                    ],
                    "compressionRatioLimitPassed": archive[
                        "compressionTelemetry"
                    ]["ratioLimitPassed"],
                    "modMode": "0600",
                    "modLinkCount": 1,
                    "zipMode": "0600",
                    "zipLinkCount": 1,
                }
            )

        if (
            not COMMON.success_counters(counters)
            or len(rows) != COMMON.EXPECTED_TUPLE_COUNT
            or len(held_outputs) != COMMON.EXPECTED_RESOURCE_COUNT
        ):
            raise COMMON.Wave2Failure("E_REQUEST_COUNT", "execution")
        source_set_sha256 = COMMON.ordered_source_set_sha256(rows)
        core.validate_held_output_inventory_v3(
            legacy,
            staging_fd,
            held_outputs,
            rows,
            items,
            limits,
        )
        os.fsync(staging_fd)
        inputs.final_barrier()
        verify_active_namespace(
            legacy,
            parent_fd,
            wave_parent_fd,
            staging_fd,
            staging_name,
            str(claim_sha256),
        )
        publication_attempted = True
        legacy.exclusive_rename_directory(
            parent_fd,
            staging_name,
            wave_parent_fd,
            COMMON.FINAL_DIRECTORY_NAME,
        )
        published_fd = os.open(
            COMMON.FINAL_DIRECTORY_NAME,
            legacy.directory_open_flags(),
            dir_fd=wave_parent_fd,
        )
        try:
            legacy.validate_directory_descriptor(
                published_fd,
                COMMON.FINAL_DIRECTORY_NAME,
                owner_only=True,
            )
            core.validate_held_output_inventory_v3(
                legacy,
                published_fd,
                held_outputs,
                rows,
                items,
                limits,
            )
        finally:
            legacy.close_quietly(published_fd)
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        held_outputs.clear()
        legacy.close_quietly(staging_fd)
        staging_fd = -1
        os.fsync(parent_fd)
        os.fsync(wave_parent_fd)

        receipt = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-acquisition-receipt"
            ),
            "schemaVersion": "1.0",
            "status": "acquired_pending_independent_readback",
            "result": (
                "fresh_exact_15_dependency_mod_zip_pairs_acquired_and_"
                "held_h1_verified"
            ),
            "permitId": permit["permitId"],
            "permitRawSha256": authority["permitRawSha256"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "decisionId": decision["decisionId"],
            "decisionRawSha256": COMMON.EXPECTED_DECISION_RAW_SHA256,
            "decisionContentSha256": (
                COMMON.EXPECTED_DECISION_CONTENT_SHA256
            ),
            "claimRawSha256": claim_sha256,
            **{name: counters[name] for name in COMMON.COUNTER_NAMES},
            "acceptedArtifactCount": 30,
            "acceptedTupleCount": 15,
            "aggregateModRawByteSize": aggregate_mod_bytes,
            "aggregateZipRawByteSize": aggregate_zip_bytes,
            "aggregateRawByteSize": (
                aggregate_mod_bytes + aggregate_zip_bytes
            ),
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedByteCount": aggregate_uncompressed,
            "orderedSourceSetSha256": source_set_sha256,
            "orderedResourceSetSha256": decision["wave"][
                "orderedResourceSetSha256"
            ],
            "sources": rows,
            "heldGoSumH1Matched": True,
            "freshChecksumDatabaseProof": False,
            "independentReadbackPassed": False,
            "dependencyFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave2_v1_independent_readback",
        }
        receipt_sha256 = legacy.write_repo_relative_artifact(
            root_fd,
            COMMON.SUCCESS_RECEIPT_PATH,
            COMMON.canonical_json_bytes(receipt),
            COMMON.MAXIMUM_JSON_BYTES,
        )
        manifest = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-acquisition-manifest"
            ),
            "schemaVersion": "1.0",
            "status": (
                "wave2_v1_acquisition_publication_complete_pending_"
                "independent_readback"
            ),
            "result": (
                "receipt_and_fresh_exact_15_mod_zip_pairs_published_"
                "manifest_written_last"
            ),
            "permitId": permit["permitId"],
            "permitRawSha256": authority["permitRawSha256"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "decisionRawSha256": COMMON.EXPECTED_DECISION_RAW_SHA256,
            "decisionContentSha256": (
                COMMON.EXPECTED_DECISION_CONTENT_SHA256
            ),
            "successReceiptPath": COMMON.SUCCESS_RECEIPT_PATH,
            "successReceiptRawSha256": receipt_sha256,
            "finalDirectoryPath": COMMON.FINAL_DIRECTORY_PATH,
            **{name: counters[name] for name in COMMON.COUNTER_NAMES},
            "acceptedArtifactCount": 30,
            "acceptedTupleCount": 15,
            "orderedSourceSetSha256": source_set_sha256,
            "manifestWrittenLast": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave2_v1_independent_readback",
        }
        manifest_sha256 = legacy.write_repo_relative_artifact(
            root_fd,
            COMMON.MANIFEST_PATH,
            COMMON.canonical_json_bytes(manifest),
            COMMON.MAXIMUM_JSON_BYTES,
        )
        return {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-runner-result"
            ),
            "schemaVersion": "1.0",
            "status": "acquired_pending_independent_readback",
            **{name: counters[name] for name in COMMON.COUNTER_NAMES},
            "acceptedArtifactCount": 30,
            "acceptedTupleCount": 15,
            "orderedSourceSetSha256": source_set_sha256,
            "successReceiptRawSha256": receipt_sha256,
            "manifestRawSha256": manifest_sha256,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave2_v1_independent_readback",
        }
    except Exception as error:
        item = active_item or {}
        failure = COMMON.map_core_failure(
            core,
            error,
            tuple_id=item.get("tupleId"),
            tuple_order=item.get("order"),
            request_ordinal=active_request_ordinal,
            resource_kind=active_kind,
            phase="execution",
        )
        if publication_attempted:
            failure = COMMON.Wave2Failure(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
                observations=counters,
            )
        if staging_fd >= 0:
            legacy.close_quietly(staging_fd)
            staging_fd = -1
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        held_outputs.clear()
        if (
            staging_name is not None
            and not publication_attempted
            and parent_fd >= 0
        ):
            try:
                legacy.remove_staging(parent_fd, staging_name)
            except Exception:
                pass
        if (
            not publication_attempted
            and claim_sha256 is not None
            and root_fd >= 0
        ):
            try:
                document = failure_document(
                    authority,
                    failure,
                    counters,
                    claim_sha256=claim_sha256,
                )
                legacy.write_repo_relative_artifact(
                    root_fd,
                    COMMON.FAILURE_RECEIPT_PATH,
                    COMMON.canonical_json_bytes(document),
                    COMMON.MAXIMUM_JSON_BYTES,
                )
            except Exception as receipt_error:
                raise COMMON.Wave2Failure(
                    "E_FAILURE_RECEIPT_WRITE",
                    "execution",
                    observations=counters,
                ) from receipt_error
        if claim_attempted and claim_sha256 is None:
            raise COMMON.Wave2Failure(
                "E_CLAIM_STATE_UNCERTAIN",
                "execution",
                observations=counters,
            ) from None
        raise failure from None
    finally:
        for record in held_outputs:
            legacy.close_quietly(record["fd"])
        legacy.close_quietly(staging_fd)
        legacy.close_quietly(wave_parent_fd)
        legacy.close_quietly(parent_fd)
        legacy.close_quietly(root_fd)
        inputs.close()


def execute_once() -> dict[str, Any]:
    previous_umask = os.umask(0o077)
    try:
        return _execute_once_with_umask()
    finally:
        os.umask(previous_umask)


def error_document(failure: Any) -> dict[str, Any]:
    uncertain = failure.code in {
        "E_FAILURE_RECEIPT_WRITE",
        "E_POST_PUBLISH_UNCERTAIN",
        "E_CLAIM_STATE_UNCERTAIN",
    }
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave2-v1-runner-error"
        ),
        "schemaVersion": "1.0",
        "status": (
            "consumed_terminal_state_uncertain"
            if uncertain
            else "failed"
        ),
        "failureCode": failure.code,
        "phase": failure.phase,
        "failedRequestOrdinal": failure.request_ordinal,
        "failedTupleId": failure.tuple_id,
        "failedTupleOrder": failure.tuple_order,
        "failedResourceKind": failure.resource_kind,
        "safeNumericObservations": COMMON.bounded_observations(
            failure.observations
        ),
        "automaticRetryAllowed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": (
            "perform_read_only_terminal_inspection"
            if uncertain
            else "inspect_bound_failure_or_prepare_versioned_recovery"
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--preflight",
        action="store_true",
        help="validate only; this is the default",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="consume the one-use permit and perform the exact acquisition",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = execute_once() if args.execute else preflight()
    except COMMON.Wave2Failure as failure:
        print(json.dumps(error_document(failure), indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
