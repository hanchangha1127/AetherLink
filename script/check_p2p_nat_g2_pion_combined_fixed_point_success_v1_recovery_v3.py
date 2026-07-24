#!/usr/bin/env python3
"""Statically check or formally record the one-use recovery readback v3."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("v3 recovery recorder requires `python3 -I -B -S`")

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v3.py"
)
EXPECTED_PERMIT_CHECKER_RAW_SHA256 = (
    "0635504df96981c8e27b0ee3b4b677dd5a1811332b7b67554d90836ac72cc1c6"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024
FAILURE_CODE_BY_STAGE = {
    "claim_guard": "E_V3_CLAIM_GUARD",
    "claim_validation": "E_V3_CLAIM_VALIDATION",
    "fresh_recompute": "E_V3_FRESH_RECOMPUTE",
    "receipt_materialization": "E_V3_RECEIPT_MATERIALIZATION",
}
FAILURE_STAGE_BY_CODE = {
    code: stage for stage, code in FAILURE_CODE_BY_STAGE.items()
}


class ReadbackError(RuntimeError):
    def __init__(self, code: str, phase: str) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase


def require(value: bool, code: str, phase: str) -> None:
    if not value:
        raise ReadbackError(code, phase)


def bootstrap_permit_checker(root: Path) -> types.ModuleType:
    current = root
    for component in PERMIT_CHECKER_PATH.split("/")[:-1]:
        current /= component
        try:
            info = current.lstat()
        except OSError as error:
            raise ReadbackError("E_BOOTSTRAP", "check") from error
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_BOOTSTRAP",
            "check",
        )
    fd = -1
    try:
        fd = os.open(
            root / PERMIT_CHECKER_PATH,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        )
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_BOOTSTRAP",
            "check",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_BOOTSTRAP", "check")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_BOOTSTRAP", "check")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_nlink,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_nlink,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            and hashlib.sha256(raw).hexdigest()
            == EXPECTED_PERMIT_CHECKER_RAW_SHA256,
            "E_BOOTSTRAP",
            "check",
        )
    except OSError as error:
        raise ReadbackError("E_BOOTSTRAP", "check") from error
    finally:
        if fd >= 0:
            os.close(fd)
    module = types.ModuleType("combined_recovery_permit_v3_frozen")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(root / PERMIT_CHECKER_PATH),
            "__loader__": None,
            "__name__": module.__name__,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(
                raw,
                PERMIT_CHECKER_PATH,
                "exec",
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise ReadbackError("E_BOOTSTRAP", "check") from error
    return module


def observed_phase(root: Path, permit_checker: Any) -> str:
    namespace = permit_checker.DECISION.V2.RECOVERY.TRUST.HeldNamespace(root)
    try:
        namespace.final_barrier()
        phase = permit_checker.classify_phase(namespace)
        namespace.final_barrier()
        return phase
    finally:
        namespace.close()


def validate_permit(context: Any, permit_checker: Any) -> dict[str, Any]:
    expected = permit_checker.content_bound(permit_checker.expected_payload(context))
    raw = context.package.raw[permit_checker.PERMIT_PATH]
    actual = permit_checker.strict_json(raw)
    require(
        raw == permit_checker.canonical_bytes(actual) and actual == expected,
        "E_PERMIT",
        "check",
    )
    return actual


def frozen_terminal(
    context: Any, permit_checker: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    authority = context.authority
    result = permit_checker.strict_json(
        authority.terminal.raw[
            permit_checker.DECISION.V2.RECOVERY.RESULT_PATH
        ]
    )
    manifest = permit_checker.strict_json(
        authority.terminal.raw[
            permit_checker.DECISION.V2.RECOVERY.MANIFEST_PATH
        ]
    )
    require(
        result["graphSha256"]
        == permit_checker.DECISION.V2.RECOVERY.EXPECTED_GRAPH_SHA256
        and result["contentBinding"]["sha256"]
        == permit_checker.DECISION.V2.RECOVERY.EXPECTED_RESULT_CONTENT_SHA256
        and manifest["newTupleCount"] == 16
        and result["fixedPointReached"] is False,
        "E_TERMINAL",
        "check",
    )
    return result, manifest


def bound_document(
    permit_checker: Any,
    payload: Mapping[str, Any],
    scope: str,
) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": permit_checker.sha256(permit_checker.canonical_bytes(payload)),
    }
    return result


def read_document(
    raw: bytes, permit_checker: Any, scope: str
) -> dict[str, Any]:
    document = permit_checker.strict_json(raw)
    require(
        raw == permit_checker.canonical_bytes(document),
        "E_CANONICAL",
        "check",
    )
    payload = dict(document)
    binding = payload.pop("contentBinding", None)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": scope,
            "sha256": permit_checker.sha256(
                permit_checker.canonical_bytes(payload)
            ),
        },
        "E_CONTENT",
        "check",
    )
    return document


def claim_payload(permit: Mapping[str, Any], permit_checker: Any) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.recovery-readback-v3-one-use-claim",
        "schemaVersion": "3.0",
        "attemptId": secrets.token_hex(16),
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "decisionContentSha256": permit["decisionBinding"]["contentSha256"],
        "originalResultRawSha256": (
            permit_checker.DECISION.V2.RECOVERY.EXPECTED_RESULT_RAW_SHA256
        ),
        "originalManifestRawSha256": (
            permit_checker.DECISION.V2.RECOVERY.EXPECTED_MANIFEST_RAW_SHA256
        ),
        "automaticRetryAllowed": False,
        "resumeAllowed": False,
        "claimBackfillAllowed": False,
        "receiptBackfillAllowed": False,
        "networkUsed": False,
        "sourceExecutionUsed": False,
        "filesystemExtractionUsed": False,
        "subprocessUsed": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def receipt_payload(
    permit: Mapping[str, Any],
    permit_checker: Any,
    claim_raw: bytes,
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.recovery-readback-v3-receipt",
        "schemaVersion": "3.0",
        "status": "formal_replacement_recovery_readback_complete",
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "decisionContentSha256": permit["decisionBinding"]["contentSha256"],
        "claimRawSha256": permit_checker.sha256(claim_raw),
        "originalResultRawSha256": (
            permit_checker.DECISION.V2.RECOVERY.EXPECTED_RESULT_RAW_SHA256
        ),
        "originalManifestRawSha256": (
            permit_checker.DECISION.V2.RECOVERY.EXPECTED_MANIFEST_RAW_SHA256
        ),
        "resultContentSha256": result["contentBinding"]["sha256"],
        "graphSha256": result["graphSha256"],
        "newTupleCount": manifest["newTupleCount"],
        "fixedPointReached": False,
        "freshHeldSourceInputCount": 69,
        "freshArchiveOpenCount": 70,
        "freshFullSourceReconstructionCount": 2,
        "underlyingIndependentGraphAlgorithmCount": 4,
        "freshRecomputationPerformedAfterDurableClaim": True,
        "receiptBackfillAllowed": False,
        "manifestBackfillAllowed": False,
        "networkUsed": False,
        "sourceExecutionUsed": False,
        "filesystemExtractionUsed": False,
        "subprocessUsed": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def manifest_payload(
    permit: Mapping[str, Any],
    permit_checker: Any,
    claim_raw: bytes,
    receipt_raw: bytes,
) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.recovery-readback-v3-manifest",
        "schemaVersion": "3.0",
        "status": "formal_replacement_recovery_readback_published",
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "decisionContentSha256": permit["decisionBinding"]["contentSha256"],
        "claimRawSha256": permit_checker.sha256(claim_raw),
        "receiptRawSha256": permit_checker.sha256(receipt_raw),
        "originalResultRawSha256": (
            permit_checker.DECISION.V2.RECOVERY.EXPECTED_RESULT_RAW_SHA256
        ),
        "originalManifestRawSha256": (
            permit_checker.DECISION.V2.RECOVERY.EXPECTED_MANIFEST_RAW_SHA256
        ),
        "manifestWrittenLast": True,
        "automaticRetryAllowed": False,
        "claimBackfillAllowed": False,
        "receiptBackfillAllowed": False,
        "manifestBackfillAllowed": False,
        "networkUsed": False,
        "sourceExecutionUsed": False,
        "filesystemExtractionUsed": False,
        "subprocessUsed": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def failure_payload(
    code: str,
    stage: str,
    permit: Mapping[str, Any],
    permit_checker: Any,
    claim_raw: bytes,
) -> dict[str, Any]:
    require(
        FAILURE_STAGE_BY_CODE.get(code) == stage,
        "E_FAILURE",
        "failure_document",
    )
    return {
        "documentType": "aetherlink.recovery-readback-v3-failure",
        "schemaVersion": "3.0",
        "status": "formal_recovery_readback_failed_permit_consumed",
        "failureCode": code,
        "failureStage": stage,
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "decisionContentSha256": permit["decisionBinding"]["contentSha256"],
        "claimRawSha256": permit_checker.sha256(claim_raw),
        "automaticRetryAllowed": False,
        "resumeAllowed": False,
        "receiptBackfillAllowed": False,
        "manifestBackfillAllowed": False,
        "networkUsed": False,
        "sourceExecutionUsed": False,
        "filesystemExtractionUsed": False,
        "subprocessUsed": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def validate_claim(
    raw: bytes, permit: Mapping[str, Any], permit_checker: Any
) -> dict[str, Any]:
    claim = read_document(raw, permit_checker, "claim_without_contentBinding")
    expected = claim_payload(permit, permit_checker)
    attempt = claim.get("attemptId")
    require(
        type(attempt) is str
        and len(attempt) == 32
        and all(character in "0123456789abcdef" for character in attempt),
        "E_CLAIM",
        "check",
    )
    expected["attemptId"] = attempt
    require(
        claim
        == bound_document(
            permit_checker, expected, "claim_without_contentBinding"
        ),
        "E_CLAIM",
        "check",
    )
    return claim


def validate_receipt(
    raw: bytes,
    permit: Mapping[str, Any],
    permit_checker: Any,
    claim_raw: bytes,
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    actual = read_document(raw, permit_checker, "receipt_without_contentBinding")
    expected = bound_document(
        permit_checker,
        receipt_payload(permit, permit_checker, claim_raw, result, manifest),
        "receipt_without_contentBinding",
    )
    require(actual == expected, "E_RECEIPT", "check")
    return actual


def validate_manifest(
    raw: bytes,
    permit: Mapping[str, Any],
    permit_checker: Any,
    claim_raw: bytes,
    receipt_raw: bytes,
) -> dict[str, Any]:
    actual = read_document(raw, permit_checker, "manifest_without_contentBinding")
    expected = bound_document(
        permit_checker,
        manifest_payload(permit, permit_checker, claim_raw, receipt_raw),
        "manifest_without_contentBinding",
    )
    require(actual == expected, "E_MANIFEST", "check")
    return actual


def validate_failure(
    claim_raw: bytes,
    failure_raw: bytes,
    permit: Mapping[str, Any],
    permit_checker: Any,
) -> dict[str, Any]:
    validate_claim(claim_raw, permit, permit_checker)
    actual = read_document(
        failure_raw, permit_checker, "failure_without_contentBinding"
    )
    code = actual.get("failureCode")
    stage = actual.get("failureStage")
    require(
        type(code) is str
        and type(stage) is str
        and FAILURE_STAGE_BY_CODE.get(code) == stage,
        "E_FAILURE",
        "check",
    )
    expected = bound_document(
        permit_checker,
        failure_payload(code, stage, permit, permit_checker, claim_raw),
        "failure_without_contentBinding",
    )
    require(actual == expected, "E_FAILURE", "check")
    return actual


def hold_outputs(context: Any, permit_checker: Any, paths: Sequence[str]) -> Any:
    return context.authority.decision_checker.HeldSet(
        context.root,
        [
            {
                "path": path,
                "maximumBytes": MAXIMUM_JSON_BYTES,
                "ownerOnly": True,
            }
            for path in paths
        ],
    )


def completed_documents(
    context: Any,
    permit_checker: Any,
    permit: Mapping[str, Any],
    result: Mapping[str, Any],
    original_manifest: Mapping[str, Any],
) -> None:
    held = hold_outputs(
        context,
        permit_checker,
        (
            permit_checker.V3_CLAIM_PATH,
            permit_checker.V3_RECEIPT_PATH,
            permit_checker.V3_MANIFEST_PATH,
        ),
    )
    try:
        claim_raw = held.raw[permit_checker.V3_CLAIM_PATH]
        receipt_raw = held.raw[permit_checker.V3_RECEIPT_PATH]
        validate_claim(claim_raw, permit, permit_checker)
        validate_receipt(
            receipt_raw,
            permit,
            permit_checker,
            claim_raw,
            result,
            original_manifest,
        )
        validate_manifest(
            held.raw[permit_checker.V3_MANIFEST_PATH],
            permit,
            permit_checker,
            claim_raw,
            receipt_raw,
        )
        held.final_barrier()
    finally:
        held.close()


def fresh_validate(
    context: Any, permit_checker: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    authority = context.authority
    original = authority.original_permit_checker.execute_module(
        "combined_recovery_v3_original_readback",
        authority.original_permit_checker.READBACK_CHECKER_PATH,
        authority.originals.raw[
            authority.original_permit_checker.READBACK_CHECKER_PATH
        ],
        authority.root,
    )
    held = authority.decision_checker.HeldSet(
        authority.root,
        original.output_bindings(authority.original_permit_checker),
    )
    try:
        context.final_barrier(context.phase)
        held.final_barrier()
        candidate = authority.candidate.generate_candidate(authority.root)
        context.final_barrier(context.phase)
        held.final_barrier()
        _, result, manifest = original.validate_outputs(
            authority,
            held,
            candidate,
            authority.original_permit_checker,
            authority.original_permit,
        )
        context.final_barrier(context.phase)
        held.final_barrier()
        return result, manifest
    finally:
        held.close()


def retained_write(
    context: Any,
    permit_checker: Any,
    relative: str,
    raw: bytes,
    post_phase: str,
    durable_callback: Any = None,
) -> str:
    require(0 < len(raw) <= MAXIMUM_JSON_BYTES, "E_PUBLICATION", "record")
    if relative.startswith(permit_checker.DEPENDENCY_ROOT + "/"):
        parent = context.namespace.parents[0]
        name = relative.removeprefix(permit_checker.DEPENDENCY_ROOT + "/")
    elif relative.startswith(permit_checker.BASE + "/"):
        parent = context.namespace.parents[1]
        name = relative.removeprefix(permit_checker.BASE + "/")
    else:
        raise ReadbackError("E_PUBLICATION", "record")
    require(bool(name) and "/" not in name, "E_PUBLICATION", "record")
    context.final_barrier(context.phase)
    fd = -1
    try:
        fd = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o600,
            dir_fd=parent.fd,
        )
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            require(written > 0, "E_PUBLICATION", "record")
            offset += written
        os.fsync(fd)
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_nlink == 1
            and info.st_size == len(raw),
            "E_PUBLICATION",
            "record",
        )
        os.fsync(parent.fd)
        if durable_callback is not None:
            durable_callback()
        context.final_barrier(post_phase)
        return permit_checker.sha256(raw)
    except FileExistsError as error:
        raise ReadbackError("E_NAMESPACE", "record") from error
    except OSError as error:
        raise ReadbackError("E_PUBLICATION", "record") from error
    finally:
        if fd >= 0:
            os.close(fd)


def check(root: Path = ROOT) -> dict[str, Any]:
    permit_checker = bootstrap_permit_checker(root)
    phase = observed_phase(root, permit_checker)
    require(phase != "blocked", "E_STATE", "check")
    context = permit_checker.PermitContext(
        root, include_permit=True, phase=phase
    )
    try:
        permit = validate_permit(context, permit_checker)
        result, manifest = frozen_terminal(context, permit_checker)
        if phase == "after_claim":
            held = hold_outputs(context, permit_checker, (permit_checker.V3_CLAIM_PATH,))
            try:
                validate_claim(
                    held.raw[permit_checker.V3_CLAIM_PATH], permit, permit_checker
                )
                held.final_barrier()
            finally:
                held.close()
        elif phase == "failure":
            held = hold_outputs(
                context,
                permit_checker,
                (permit_checker.V3_CLAIM_PATH, permit_checker.V3_FAILURE_PATH),
            )
            try:
                validate_failure(
                    held.raw[permit_checker.V3_CLAIM_PATH],
                    held.raw[permit_checker.V3_FAILURE_PATH],
                    permit,
                    permit_checker,
                )
                held.final_barrier()
            finally:
                held.close()
        elif phase == "after_receipt":
            held = hold_outputs(
                context,
                permit_checker,
                (permit_checker.V3_CLAIM_PATH, permit_checker.V3_RECEIPT_PATH),
            )
            try:
                claim_raw = held.raw[permit_checker.V3_CLAIM_PATH]
                validate_claim(claim_raw, permit, permit_checker)
                validate_receipt(
                    held.raw[permit_checker.V3_RECEIPT_PATH],
                    permit,
                    permit_checker,
                    claim_raw,
                    result,
                    manifest,
                )
                held.final_barrier()
            finally:
                held.close()
        elif phase == "complete":
            completed_documents(
                context, permit_checker, permit, result, manifest
            )
        context.final_barrier(phase)
        return {
            "documentType": "aetherlink.recovery-readback-v3-static-check",
            "schemaVersion": "3.0",
            "status": (
                "recordable_static_readiness_passed"
                if phase == "recordable"
                else "consumed_state_static_validation_passed"
            ),
            "phase": phase,
            "validationPassed": True,
            "recordable": phase == "recordable",
            "permitId": permit["permitId"],
            "graphSha256": result["graphSha256"],
            "newTupleCount": manifest["newTupleCount"],
            "fixedPointReached": False,
            "freshRecomputationPerformed": False,
            "archiveMemberDecodeCount": 0,
            "fileWriteCount": 0,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessCount": 0,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        context.close()


def publish_failure(
    context: Any,
    permit_checker: Any,
    permit: Mapping[str, Any],
    claim_raw: bytes,
    code: str,
    stage: str,
    existing_claim_guard: Any,
) -> None:
    claim_guard = existing_claim_guard
    owns_claim_guard = False
    failure_guard = None
    attempted = False
    try:
        if claim_guard is None:
            claim_guard = hold_outputs(
                context, permit_checker, (permit_checker.V3_CLAIM_PATH,)
            )
            owns_claim_guard = True
        require(
            claim_guard.raw[permit_checker.V3_CLAIM_PATH] == claim_raw,
            "E_CLAIM",
            "failure_publication",
        )
        validate_claim(claim_raw, permit, permit_checker)
        context.final_barrier("after_claim")
        claim_guard.final_barrier()
        context.phase = "after_claim"
        failure = bound_document(
            permit_checker,
            failure_payload(code, stage, permit, permit_checker, claim_raw),
            "failure_without_contentBinding",
        )
        failure_raw = permit_checker.canonical_bytes(failure)
        attempted = True
        retained_write(
            context,
            permit_checker,
            permit_checker.V3_FAILURE_PATH,
            failure_raw,
            "failure",
        )
        failure_guard = hold_outputs(
            context, permit_checker, (permit_checker.V3_FAILURE_PATH,)
        )
        for _ in range(2):
            context.final_barrier("failure")
            claim_guard.final_barrier()
            failure_guard.final_barrier()
            validate_failure(
                claim_guard.raw[permit_checker.V3_CLAIM_PATH],
                failure_guard.raw[permit_checker.V3_FAILURE_PATH],
                permit,
                permit_checker,
            )
    except Exception as error:
        code = (
            "E_V3_FAILURE_PUBLICATION_UNCERTAIN"
            if attempted
            else "E_V3_FAILURE_PREPUBLICATION_UNCERTAIN"
        )
        raise ReadbackError(code, "failure_publication") from error
    finally:
        if failure_guard is not None:
            failure_guard.close()
        if owns_claim_guard and claim_guard is not None:
            claim_guard.close()


def record(root: Path = ROOT) -> dict[str, Any]:
    permit_checker = bootstrap_permit_checker(root)
    require(
        observed_phase(root, permit_checker) == "recordable",
        "E_STATE",
        "record",
    )
    context = permit_checker.PermitContext(
        root, include_permit=True, phase="recordable"
    )
    claim_guard = receipt_guard = manifest_guard = None
    claim_written = False
    receipt_attempted = False
    claim_raw = b""
    permit: Mapping[str, Any] = {}
    stage = "claim_guard"
    try:
        permit = validate_permit(context, permit_checker)
        def mark_claim_durable() -> None:
            nonlocal claim_written
            claim_written = True

        claim = bound_document(
            permit_checker,
            claim_payload(permit, permit_checker),
            "claim_without_contentBinding",
        )
        claim_raw = permit_checker.canonical_bytes(claim)
        retained_write(
            context,
            permit_checker,
            permit_checker.V3_CLAIM_PATH,
            claim_raw,
            "after_claim",
            mark_claim_durable,
        )
        stage = "claim_guard"
        claim_guard = hold_outputs(
            context, permit_checker, (permit_checker.V3_CLAIM_PATH,)
        )
        stage = "claim_validation"
        context.final_barrier("after_claim")
        claim_guard.final_barrier()
        validate_claim(
            claim_guard.raw[permit_checker.V3_CLAIM_PATH],
            permit,
            permit_checker,
        )
        context.phase = "after_claim"
        stage = "fresh_recompute"
        result, original_manifest = fresh_validate(context, permit_checker)
        stage = "receipt_materialization"
        receipt = bound_document(
            permit_checker,
            receipt_payload(
                permit,
                permit_checker,
                claim_raw,
                result,
                original_manifest,
            ),
            "receipt_without_contentBinding",
        )
        receipt_raw = permit_checker.canonical_bytes(receipt)
        receipt_attempted = True
        retained_write(
            context,
            permit_checker,
            permit_checker.V3_RECEIPT_PATH,
            receipt_raw,
            "after_receipt",
        )
        receipt_guard = hold_outputs(
            context, permit_checker, (permit_checker.V3_RECEIPT_PATH,)
        )
        context.final_barrier("after_receipt")
        claim_guard.final_barrier()
        receipt_guard.final_barrier()
        validate_receipt(
            receipt_guard.raw[permit_checker.V3_RECEIPT_PATH],
            permit,
            permit_checker,
            claim_raw,
            result,
            original_manifest,
        )
        context.phase = "after_receipt"
        manifest = bound_document(
            permit_checker,
            manifest_payload(
                permit, permit_checker, claim_raw, receipt_raw
            ),
            "manifest_without_contentBinding",
        )
        manifest_raw = permit_checker.canonical_bytes(manifest)
        retained_write(
            context,
            permit_checker,
            permit_checker.V3_MANIFEST_PATH,
            manifest_raw,
            "complete",
        )
        manifest_guard = hold_outputs(
            context, permit_checker, (permit_checker.V3_MANIFEST_PATH,)
        )
        context.final_barrier("complete")
        for guard in (claim_guard, receipt_guard, manifest_guard):
            guard.final_barrier()
        completed_documents(
            context, permit_checker, permit, result, original_manifest
        )
        return {
            "status": "formal_replacement_recovery_readback_published",
            "receiptRawSha256": permit_checker.sha256(receipt_raw),
            "manifestRawSha256": permit_checker.sha256(manifest_raw),
            "networkUsed": False,
            "userActionRequired": False,
        }
    except Exception as error:
        if claim_written and not receipt_attempted:
            publish_failure(
                context,
                permit_checker,
                permit,
                claim_raw,
                FAILURE_CODE_BY_STAGE[stage],
                stage,
                claim_guard,
            )
        if receipt_attempted:
            raise ReadbackError(
                "E_V3_POST_RECEIPT_PUBLICATION_UNCERTAIN", "record"
            ) from None
        if isinstance(error, ReadbackError):
            raise
        raise ReadbackError("E_INTERNAL", "record") from error
    finally:
        for guard in (manifest_guard, receipt_guard, claim_guard):
            if guard is not None:
                guard.close()
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise ReadbackError("E_ARGUMENT", "cli")


def error_document(error: ReadbackError) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.recovery-readback-v3-error",
        "schemaVersion": "3.0",
        "status": "failed_closed_or_consumed_uncertain",
        "failureCode": error.code,
        "phase": error.phase,
        "automaticRetryAllowed": False,
        "networkUsed": False,
        "sourceExecutionUsed": False,
        "filesystemExtractionUsed": False,
        "subprocessCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--check", action="store_true")
        group.add_argument("--record", action="store_true")
        args = parser.parse_args(argv)
        result = record() if args.record else check()
        print(
            json.dumps(
                result,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        return 0
    except ReadbackError as error:
        print(
            json.dumps(
                error_document(error),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                error_document(ReadbackError("E_INTERNAL", "cli")),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
