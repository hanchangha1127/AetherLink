#!/usr/bin/env python3
"""Independently check or record the combined fixed-point evaluation.

``--check`` is the read-only default. ``--record`` consumes a separate
readback claim, freshly recomputes the graph while an outer 69-input hold
remains open, compares the exact result projection, and publishes a receipt
followed by a manifest. Repository verification never invokes ``--record``.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def isolated_interpreter() -> bool:
    return (
        sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_user_site == 1
        and sys.flags.no_site == 1
        and sys.flags.optimize == 0
    )


import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import time
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_execution_permit_v1.py"
)
# Replaced with the final permit-checker SHA before permit publication.
EXPECTED_PERMIT_CHECKER_RAW_SHA256 = (
    "dfa5350e68f81c7e288fb281390827567a8b368596d5b8803b7848e81ddbdd25"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024


class ReadbackError(RuntimeError):
    def __init__(self, code: str, phase: str) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ReadbackError("E_ARGUMENTS", "cli")


def require(condition: bool, code: str, phase: str) -> None:
    if not condition:
        raise ReadbackError(code, phase)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def content_bound(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("contentBinding", None)
    result = dict(body)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "document_without_contentBinding",
        "sha256": sha256(canonical_bytes(body)),
    }
    return result


def load_permit_checker(root: Path) -> types.ModuleType:
    relative = PERMIT_CHECKER_PATH
    current = root
    for component in relative.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_TOOL_IDENTITY",
            "check",
        )
    fd = os.open(
        root / relative,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
    )
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_TOOL_IDENTITY",
            "check",
        )
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_TOOL_IDENTITY", "check")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_TOOL_IDENTITY", "check")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        require(
            sha256(raw) == EXPECTED_PERMIT_CHECKER_RAW_SHA256
            and (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "E_TOOL_IDENTITY",
            "check",
        )
    finally:
        os.close(fd)
    module = types.ModuleType("aetherlink_combined_fixed_point_permit_v1")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(root / relative),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_permit_v1",
            "__package__": None,
        }
    )
    try:
        exec(
            compile(raw, relative, "exec", dont_inherit=True, optimize=0),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise ReadbackError("E_TOOL_LOAD", "check") from error
    return module


def safe_relative(value: str) -> str:
    require(
        type(value) is str
        and value
        and not value.startswith("/")
        and "\\" not in value
        and "\x00" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and PurePosixPath(value).as_posix() == value,
        "E_PATH",
        "readback",
    )
    return value


def path_kind(root: Path, relative: str) -> str:
    try:
        info = os.lstat(root / safe_relative(relative))
    except FileNotFoundError:
        return "absent"
    except OSError as error:
        raise ReadbackError("E_NAMESPACE", "check") from error
    return "regular" if stat.S_ISREG(info.st_mode) else "other"


def state(
    root: Path,
    permit_checker: types.ModuleType,
) -> tuple[str, dict[str, str]]:
    paths = {
        "claim": permit_checker.CLAIM_PATH,
        "result": permit_checker.RESULT_PATH,
        "failure": permit_checker.FAILURE_PATH,
        "manifest": permit_checker.MANIFEST_PATH,
        "readbackClaim": permit_checker.READBACK_CLAIM_PATH,
        "readbackReceipt": permit_checker.READBACK_RECEIPT_PATH,
        "readbackFailure": permit_checker.READBACK_FAILURE_PATH,
        "readbackManifest": permit_checker.READBACK_MANIFEST_PATH,
    }
    kinds = {name: path_kind(root, path) for name, path in paths.items()}
    if all(value == "absent" for value in kinds.values()):
        return "not_executed", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["result"] == "regular"
        and kinds["failure"] == "absent"
        and kinds["manifest"] == "regular"
        and all(kinds[name] == "absent" for name in (
            "readbackClaim",
            "readbackReceipt",
            "readbackFailure",
            "readbackManifest",
        ))
    ):
        return "recordable", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["result"] == "regular"
        and kinds["failure"] == "absent"
        and kinds["manifest"] == "regular"
        and kinds["readbackClaim"] == "regular"
        and kinds["readbackReceipt"] == "regular"
        and kinds["readbackFailure"] == "absent"
        and kinds["readbackManifest"] == "regular"
    ):
        return "recorded", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["result"] == "regular"
        and kinds["failure"] == "absent"
        and kinds["manifest"] == "regular"
        and kinds["readbackClaim"] == "regular"
        and kinds["readbackReceipt"] == "absent"
        and kinds["readbackFailure"] == "regular"
        and kinds["readbackManifest"] == "absent"
    ):
        return "readback_failure", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["failure"] == "regular"
        and kinds["result"] == "absent"
        and kinds["manifest"] == "absent"
        and all(kinds[name] == "absent" for name in (
            "readbackClaim",
            "readbackReceipt",
            "readbackFailure",
            "readbackManifest",
        ))
    ):
        return "evaluation_failure", kinds
    return "blocked", kinds


def require_readback_namespace(
    root: Path,
    permit_checker: types.ModuleType,
    phase: str,
    context: Any | None = None,
) -> None:
    expected_by_phase = {
        "after_claim": {
            "claim": "regular",
            "result": "regular",
            "failure": "absent",
            "manifest": "regular",
            "readbackClaim": "regular",
            "readbackReceipt": "absent",
            "readbackFailure": "absent",
            "readbackManifest": "absent",
        },
        "after_receipt": {
            "claim": "regular",
            "result": "regular",
            "failure": "absent",
            "manifest": "regular",
            "readbackClaim": "regular",
            "readbackReceipt": "regular",
            "readbackFailure": "absent",
            "readbackManifest": "absent",
        },
        "complete": {
            "claim": "regular",
            "result": "regular",
            "failure": "absent",
            "manifest": "regular",
            "readbackClaim": "regular",
            "readbackReceipt": "regular",
            "readbackFailure": "absent",
            "readbackManifest": "regular",
        },
        "readback_failure": {
            "claim": "regular",
            "result": "regular",
            "failure": "absent",
            "manifest": "regular",
            "readbackClaim": "regular",
            "readbackReceipt": "absent",
            "readbackFailure": "regular",
            "readbackManifest": "absent",
        },
    }
    require(phase in expected_by_phase, "E_INTERNAL", "record")
    _, kinds = state(root, permit_checker)
    require(
        kinds == expected_by_phase[phase],
        "E_NAMESPACE",
        "record",
    )
    if context is not None:
        try:
            context.namespace_barrier()
        except Exception as error:
            raise ReadbackError("E_NAMESPACE", "record") from error


def strict_json(raw: bytes) -> dict[str, Any]:
    def object_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            require(key not in value, "E_JSON", "check")
            value[key] = child
        return value

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=object_hook,
            parse_float=lambda _: _json_failure(),
            parse_constant=lambda _: _json_failure(),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReadbackError("E_JSON", "check") from error
    require(type(value) is dict, "E_JSON", "check")
    return value


def _json_failure() -> Any:
    raise ReadbackError("E_JSON", "check")


PROJECTION_FIELDS = (
    "inputSet",
    "terminalEvidenceBindings",
    "coverage",
    "profiles",
    "graphDiscovery",
    "checkerVerification",
    "route",
    "nextAction",
    "operationCounters",
    "closure",
)

CLAIM_KEYS = {
    "claimType",
    "schemaVersion",
    "attemptId",
    "createdAt",
    "permitId",
    "permitContentSha256",
    "decisionId",
    "decisionContentSha256",
    "decisionHeldBindingSetSha256",
    "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode",
    "automaticRetryAllowed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
}
RESULT_KEYS = {
    "documentType",
    "schemaVersion",
    "evaluationId",
    "status",
    "result",
    "decisionBinding",
    "permitBinding",
    "claimRawSha256",
    "candidateProviderBinding",
    "immutableGraphProviderBinding",
    "candidateContentSha256",
    "candidateSourceProjectionSha256",
    "graphSha256",
    "candidateProjection",
    "fixedPointReached",
    "dependencySourceReviewed",
    "semanticClosureComplete",
    "rungThreeComplete",
    "candidateSelected",
    "librarySelected",
    "networkUsed",
    "sourceExecutionUsed",
    "filesystemExtractionUsed",
    "subprocessUsed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "signatureRequired",
    "privateKeyRequired",
    "tokenRequired",
    "passwordRequired",
    "userActionRequired",
    "nextAction",
    "contentBinding",
}
EVALUATION_MANIFEST_KEYS = {
    "documentType",
    "schemaVersion",
    "manifestWrittenLast",
    "permitId",
    "decisionId",
    "claimRawSha256",
    "resultPath",
    "resultRawSha256",
    "resultContentSha256",
    "resultStatus",
    "decisionHeldBindingSetSha256",
    "candidateSourceProjectionSha256",
    "fixedPointReached",
    "newTupleCount",
    "networkUsed",
    "sourceExecutionUsed",
    "filesystemExtractionUsed",
    "subprocessUsed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
}
READBACK_CLAIM_KEYS = {
    "claimType",
    "schemaVersion",
    "attemptId",
    "createdAt",
    "permitId",
    "permitContentSha256",
    "resultRawSha256",
    "candidateSourceProjectionSha256",
    "automaticRetryAllowed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
}
READBACK_RECEIPT_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "permitId",
    "readbackClaimRawSha256",
    "resultRawSha256",
    "resultContentSha256",
    "evaluationManifestRawSha256",
    "freshHeldSourceInputCount",
    "freshArchiveOpenCount",
    "freshFullSourceReconstructionCount",
    "sourceGraphAlgorithmsReexecutedByReadback",
    "archiveMembersReopened",
    "exactResultProjectionMatched",
    "graphSha256",
    "candidateSourceProjectionSha256",
    "fixedPointReached",
    "newTupleCount",
    "networkUsed",
    "sourceExecutionUsed",
    "filesystemExtractionUsed",
    "subprocessUsed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "signatureRequired",
    "privateKeyRequired",
    "tokenRequired",
    "passwordRequired",
    "userActionRequired",
    "nextAction",
}
READBACK_MANIFEST_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "manifestWrittenLast",
    "permitId",
    "readbackClaimRawSha256",
    "readbackReceiptPath",
    "readbackReceiptRawSha256",
    "resultRawSha256",
    "evaluationManifestRawSha256",
    "candidateSourceProjectionSha256",
    "fixedPointReached",
    "newTupleCount",
    "independentReadbackPassed",
    "networkUsed",
    "sourceExecutionUsed",
    "filesystemExtractionUsed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
}
EVALUATION_FAILURE_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "failureCode",
    "phase",
    "permitId",
    "permitContentSha256",
    "decisionId",
    "decisionContentSha256",
    "claimRawSha256",
    "decisionHeldBindingSetSha256",
    "automaticRetryAllowed",
    "resultBackfillAllowed",
    "networkUsed",
    "sourceExecutionUsed",
    "filesystemExtractionUsed",
    "subprocessUsed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "signatureRequired",
    "privateKeyRequired",
    "tokenRequired",
    "passwordRequired",
    "userActionRequired",
    "contentBinding",
}
READBACK_FAILURE_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "failureCode",
    "phase",
    "permitId",
    "permitContentSha256",
    "readbackClaimRawSha256",
    "resultRawSha256",
    "resultContentSha256",
    "evaluationManifestRawSha256",
    "candidateSourceProjectionSha256",
    "automaticRetryAllowed",
    "receiptBackfillAllowed",
    "networkUsed",
    "sourceExecutionUsed",
    "filesystemExtractionUsed",
    "subprocessUsed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "signatureRequired",
    "privateKeyRequired",
    "tokenRequired",
    "passwordRequired",
    "userActionRequired",
    "contentBinding",
}


def exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    code: str,
) -> None:
    require(type(value) is dict and set(value) == expected, code, "check")


def exact_false(
    value: Mapping[str, Any],
    fields: Sequence[str],
    code: str,
) -> None:
    require(all(value.get(field) is False for field in fields), code, "check")


def valid_attempt_fields(value: Mapping[str, Any], code: str) -> None:
    attempt = value.get("attemptId")
    created = value.get("createdAt")
    require(
        type(attempt) is str
        and len(attempt) == 32
        and all(character in "0123456789abcdef" for character in attempt)
        and type(created) is str
        and len(created) == 20,
        code,
        "check",
    )
    try:
        parsed = time.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError) as error:
        raise ReadbackError(code, "check") from error
    require(
        time.strftime("%Y-%m-%dT%H:%M:%SZ", parsed) == created,
        code,
        "check",
    )


def independent_projection(candidate: Mapping[str, Any]) -> dict[str, Any]:
    require(
        type(candidate) is dict
        and set(PROJECTION_FIELDS).issubset(candidate),
        "E_CANDIDATE",
        "check",
    )
    return {field: candidate[field] for field in PROJECTION_FIELDS}


def output_bindings(
    permit_checker: types.ModuleType,
) -> list[dict[str, Any]]:
    return [
        {
            "path": permit_checker.CLAIM_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": permit_checker.RESULT_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": permit_checker.MANIFEST_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
    ]


def recorded_output_bindings(
    permit_checker: types.ModuleType,
) -> list[dict[str, Any]]:
    return output_bindings(permit_checker) + [
        {
            "path": permit_checker.READBACK_CLAIM_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": permit_checker.READBACK_RECEIPT_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": permit_checker.READBACK_MANIFEST_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
    ]


def evaluation_failure_bindings(
    permit_checker: types.ModuleType,
) -> list[dict[str, Any]]:
    return [
        {
            "path": permit_checker.CLAIM_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": permit_checker.FAILURE_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
    ]


def readback_failure_bindings(
    permit_checker: types.ModuleType,
) -> list[dict[str, Any]]:
    return output_bindings(permit_checker) + [
        {
            "path": permit_checker.READBACK_CLAIM_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
        {
            "path": permit_checker.READBACK_FAILURE_PATH,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        },
    ]


def validate_content_binding(
    value: Mapping[str, Any],
    *,
    scope: str,
    code: str,
) -> None:
    without = dict(value)
    binding = without.pop("contentBinding", None)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": scope,
            "sha256": sha256(canonical_bytes(without)),
        },
        code,
        "check",
    )


def validate_execution_claim(
    raw: bytes,
    context: Any,
    permit: Mapping[str, Any],
) -> dict[str, Any]:
    claim = strict_json(raw)
    require(raw == canonical_bytes(claim), "E_CANONICAL_OUTPUT", "check")
    exact_keys(claim, CLAIM_KEYS, "E_CLAIM")
    valid_attempt_fields(claim, "E_CLAIM")
    require(
        claim["claimType"]
        == "aetherlink.g2-pion-combined-fixed-point-one-use-claim"
        and claim["schemaVersion"] == "1.0"
        and claim["permitId"] == permit["permitId"]
        and claim["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and claim["decisionId"] == context.decision["decisionId"]
        and claim["decisionContentSha256"]
        == context.decision["contentBinding"]["sha256"]
        and claim["decisionHeldBindingSetSha256"]
        == permit["sourceInputSet"]["decisionHeldBindingSetSha256"]
        and claim[
            "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode"
        ]
        is True,
        "E_CLAIM",
        "check",
    )
    exact_false(
        claim,
        (
            "automaticRetryAllowed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
        ),
        "E_CLAIM",
    )
    return claim


def validate_outputs(
    context: Any,
    held_outputs: Any,
    candidate: Mapping[str, Any],
    permit_checker: types.ModuleType,
    permit: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    claim_raw = held_outputs.raw[permit_checker.CLAIM_PATH]
    result_raw = held_outputs.raw[permit_checker.RESULT_PATH]
    manifest_raw = held_outputs.raw[permit_checker.MANIFEST_PATH]
    claim = validate_execution_claim(claim_raw, context, permit)
    result = strict_json(result_raw)
    manifest = strict_json(manifest_raw)
    require(
        result_raw == canonical_bytes(result)
        and manifest_raw == canonical_bytes(manifest),
        "E_CANONICAL_OUTPUT",
        "check",
    )
    exact_keys(result, RESULT_KEYS, "E_RESULT")
    require(
        result["documentType"]
        == "aetherlink.g2-pion-combined-fixed-point-evaluation-result"
        and result["schemaVersion"] == "1.0"
        and result["evaluationId"]
        == "g2-pion-ice-v4.3.0-combined-fixed-point-evaluation-v1"
        and result["status"]
        == (
            "combined_evaluation_complete_not_fixed_point_"
            "new_wave_required"
        )
        and result["result"]
        == "exact_69_input_combined_graph_recomputed_frontier_16"
        and result["decisionBinding"]
        == {
            "decisionId": context.decision["decisionId"],
            "rawSha256": permit["decisionBinding"]["rawSha256"],
            "contentSha256": context.decision["contentBinding"]["sha256"],
        }
        and result["permitBinding"]
        == {
            "permitId": permit["permitId"],
            "contentSha256": permit["contentBinding"]["sha256"],
        }
        and result["claimRawSha256"] == sha256(claim_raw)
        and result["candidateProviderBinding"]
        == permit["candidateProviderBinding"]
        and result["immutableGraphProviderBinding"]
        == permit["immutableGraphProviderBinding"]
        and result["fixedPointReached"] is False
        and result["nextAction"]
        == "run_separate_combined_fixed_point_independent_readback",
        "E_RESULT",
        "check",
    )
    exact_false(
        result,
        (
            "fixedPointReached",
            "dependencySourceReviewed",
            "semanticClosureComplete",
            "rungThreeComplete",
            "candidateSelected",
            "librarySelected",
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "subprocessUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ),
        "E_RESULT",
    )
    expected_projection = independent_projection(candidate)
    require(
        result["candidateProjection"] == expected_projection
        and result["candidateContentSha256"]
        == candidate["contentBinding"]["sha256"]
        and result["candidateSourceProjectionSha256"]
        == candidate["inputSet"]["combinedInputSetSha256"]
        and result["candidateSourceProjectionSha256"]
        == permit["sourceInputSet"]["candidateSourceProjectionSha256"]
        and result["graphSha256"]
        == candidate["graphDiscovery"]["graphSha256"],
        "E_RESULT_PROJECTION",
        "check",
    )
    binding = result.get("contentBinding")
    without = dict(result)
    without.pop("contentBinding", None)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": "result_without_contentBinding",
            "sha256": sha256(canonical_bytes(without)),
        },
        "E_RESULT",
        "check",
    )
    exact_keys(manifest, EVALUATION_MANIFEST_KEYS, "E_MANIFEST")
    require(
        manifest["documentType"]
        == "aetherlink.g2-pion-combined-fixed-point-evaluation-manifest"
        and manifest["schemaVersion"] == "1.0"
        and manifest["manifestWrittenLast"] is True
        and manifest["permitId"] == permit["permitId"]
        and manifest["decisionId"] == context.decision["decisionId"]
        and manifest["claimRawSha256"] == sha256(claim_raw)
        and manifest["resultPath"] == permit_checker.RESULT_PATH
        and manifest["resultRawSha256"] == sha256(result_raw)
        and manifest["resultContentSha256"] == binding["sha256"]
        and manifest["resultStatus"] == result["status"]
        and manifest["decisionHeldBindingSetSha256"]
        == permit["sourceInputSet"]["decisionHeldBindingSetSha256"]
        and manifest["candidateSourceProjectionSha256"]
        == result["candidateSourceProjectionSha256"]
        and manifest["fixedPointReached"] is False
        and manifest["newTupleCount"] == 16
        and manifest["nextAction"]
        == "run_separate_combined_fixed_point_independent_readback",
        "E_MANIFEST",
        "check",
    )
    exact_false(
        manifest,
        (
            "fixedPointReached",
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "subprocessUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
        ),
        "E_MANIFEST",
    )
    return claim, result, manifest


def validate_recorded_readback(
    held_outputs: Any,
    permit_checker: types.ModuleType,
    permit: Mapping[str, Any],
    result: Mapping[str, Any],
    evaluation_manifest: Mapping[str, Any],
) -> None:
    claim_raw = held_outputs.raw[permit_checker.READBACK_CLAIM_PATH]
    receipt_raw = held_outputs.raw[permit_checker.READBACK_RECEIPT_PATH]
    manifest_raw = held_outputs.raw[permit_checker.READBACK_MANIFEST_PATH]
    result_raw = held_outputs.raw[permit_checker.RESULT_PATH]
    evaluation_manifest_raw = held_outputs.raw[permit_checker.MANIFEST_PATH]
    claim = strict_json(claim_raw)
    receipt = strict_json(receipt_raw)
    manifest = strict_json(manifest_raw)
    require(
        claim_raw == canonical_bytes(claim)
        and receipt_raw == canonical_bytes(receipt)
        and manifest_raw == canonical_bytes(manifest),
        "E_CANONICAL_READBACK",
        "check",
    )
    exact_keys(claim, READBACK_CLAIM_KEYS, "E_READBACK_CLAIM")
    valid_attempt_fields(claim, "E_READBACK_CLAIM")
    require(
        claim["claimType"]
        == (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-one-use-claim"
        )
        and claim["schemaVersion"] == "1.0"
        and claim["permitId"] == permit["permitId"]
        and claim["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and claim["resultRawSha256"] == sha256(result_raw)
        and claim["candidateSourceProjectionSha256"]
        == result["candidateSourceProjectionSha256"],
        "E_READBACK_CLAIM",
        "check",
    )
    exact_false(
        claim,
        (
            "automaticRetryAllowed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
        ),
        "E_READBACK_CLAIM",
    )
    exact_keys(receipt, READBACK_RECEIPT_KEYS, "E_READBACK_RECEIPT")
    require(
        receipt["documentType"]
        == (
            "aetherlink.g2-pion-combined-fixed-point-"
            "independent-readback-receipt"
        )
        and receipt["schemaVersion"] == "1.0"
        and receipt["status"]
        == "independent_readback_complete_manifest_pending"
        and receipt["permitId"] == permit["permitId"]
        and receipt["readbackClaimRawSha256"] == sha256(claim_raw)
        and receipt["resultRawSha256"] == sha256(result_raw)
        and receipt["resultContentSha256"]
        == result["contentBinding"]["sha256"]
        and receipt["evaluationManifestRawSha256"]
        == sha256(evaluation_manifest_raw)
        and receipt["freshHeldSourceInputCount"] == 69
        and receipt["freshArchiveOpenCount"] == 70
        and receipt["freshFullSourceReconstructionCount"] == 2
        and receipt["sourceGraphAlgorithmsReexecutedByReadback"] is True
        and receipt["archiveMembersReopened"] is True
        and receipt["exactResultProjectionMatched"] is True
        and receipt["graphSha256"] == result["graphSha256"]
        and receipt["candidateSourceProjectionSha256"]
        == result["candidateSourceProjectionSha256"]
        and receipt["fixedPointReached"] is False
        and receipt["newTupleCount"] == 16
        and receipt["nextAction"]
        == "publish_combined_fixed_point_readback_manifest_last",
        "E_READBACK_RECEIPT",
        "check",
    )
    exact_false(
        receipt,
        (
            "fixedPointReached",
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "subprocessUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ),
        "E_READBACK_RECEIPT",
    )
    exact_keys(manifest, READBACK_MANIFEST_KEYS, "E_READBACK_MANIFEST")
    require(
        manifest["documentType"]
        == (
            "aetherlink.g2-pion-combined-fixed-point-"
            "independent-readback-manifest"
        )
        and manifest["schemaVersion"] == "1.0"
        and manifest["status"]
        == "independent_readback_published_not_fixed_point"
        and manifest["manifestWrittenLast"] is True
        and manifest["permitId"] == permit["permitId"]
        and manifest["readbackClaimRawSha256"] == sha256(claim_raw)
        and manifest["readbackReceiptPath"]
        == permit_checker.READBACK_RECEIPT_PATH
        and manifest["readbackReceiptRawSha256"] == sha256(receipt_raw)
        and manifest["resultRawSha256"] == sha256(result_raw)
        and manifest["evaluationManifestRawSha256"]
        == sha256(evaluation_manifest_raw)
        and manifest["candidateSourceProjectionSha256"]
        == result["candidateSourceProjectionSha256"]
        and manifest["fixedPointReached"] is False
        and manifest["newTupleCount"] == 16
        and manifest["independentReadbackPassed"] is True
        and manifest["nextAction"]
        == (
            "prepare_separate_new_dependency_wave_decision_for_"
            "remaining_16_frontier_tuples"
        )
        and sha256(evaluation_manifest_raw)
        == receipt["evaluationManifestRawSha256"]
        and evaluation_manifest["newTupleCount"] == 16,
        "E_READBACK_MANIFEST",
        "check",
    )
    exact_false(
        manifest,
        (
            "fixedPointReached",
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
        ),
        "E_READBACK_MANIFEST",
    )


def validate_evaluation_failure(
    context: Any,
    held_outputs: Any,
    permit_checker: types.ModuleType,
    permit: Mapping[str, Any],
) -> None:
    claim_raw = held_outputs.raw[permit_checker.CLAIM_PATH]
    failure_raw = held_outputs.raw[permit_checker.FAILURE_PATH]
    validate_execution_claim(claim_raw, context, permit)
    failure = strict_json(failure_raw)
    require(
        failure_raw == canonical_bytes(failure),
        "E_CANONICAL_FAILURE",
        "check",
    )
    exact_keys(failure, EVALUATION_FAILURE_KEYS, "E_FAILURE")
    validate_content_binding(
        failure,
        scope="document_without_contentBinding",
        code="E_FAILURE",
    )
    require(
        failure["documentType"]
        == "aetherlink.g2-pion-combined-fixed-point-evaluation-failure"
        and failure["schemaVersion"] == "1.0"
        and failure["status"]
        == "consumed_failure_before_result_publication"
        and type(failure["failureCode"]) is str
        and bool(failure["failureCode"])
        and type(failure["phase"]) is str
        and bool(failure["phase"])
        and failure["permitId"] == permit["permitId"]
        and failure["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and failure["decisionId"] == context.decision["decisionId"]
        and failure["decisionContentSha256"]
        == context.decision["contentBinding"]["sha256"]
        and failure["claimRawSha256"] == sha256(claim_raw)
        and failure["decisionHeldBindingSetSha256"]
        == permit["sourceInputSet"]["decisionHeldBindingSetSha256"],
        "E_FAILURE",
        "check",
    )
    exact_false(
        failure,
        (
            "automaticRetryAllowed",
            "resultBackfillAllowed",
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "subprocessUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ),
        "E_FAILURE",
    )


def validate_readback_failure(
    held_outputs: Any,
    permit_checker: types.ModuleType,
    permit: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    validate_readback_failure_bytes(
        held_outputs.raw[permit_checker.READBACK_CLAIM_PATH],
        held_outputs.raw[permit_checker.READBACK_FAILURE_PATH],
        held_outputs.raw[permit_checker.RESULT_PATH],
        held_outputs.raw[permit_checker.MANIFEST_PATH],
        permit,
        result,
    )


def validate_readback_failure_bytes(
    claim_raw: bytes,
    failure_raw: bytes,
    result_raw: bytes,
    evaluation_manifest_raw: bytes,
    permit: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    claim = strict_json(claim_raw)
    failure = strict_json(failure_raw)
    require(
        claim_raw == canonical_bytes(claim)
        and failure_raw == canonical_bytes(failure),
        "E_CANONICAL_READBACK_FAILURE",
        "check",
    )
    exact_keys(claim, READBACK_CLAIM_KEYS, "E_READBACK_CLAIM")
    valid_attempt_fields(claim, "E_READBACK_CLAIM")
    require(
        claim["claimType"]
        == (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-one-use-claim"
        )
        and claim["schemaVersion"] == "1.0"
        and claim["permitId"] == permit["permitId"]
        and claim["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and claim["resultRawSha256"] == sha256(result_raw)
        and claim["candidateSourceProjectionSha256"]
        == result["candidateSourceProjectionSha256"],
        "E_READBACK_CLAIM",
        "check",
    )
    exact_false(
        claim,
        (
            "automaticRetryAllowed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
        ),
        "E_READBACK_CLAIM",
    )
    exact_keys(failure, READBACK_FAILURE_KEYS, "E_READBACK_FAILURE")
    validate_content_binding(
        failure,
        scope="document_without_contentBinding",
        code="E_READBACK_FAILURE",
    )
    require(
        failure["documentType"]
        == (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-failure"
        )
        and failure["schemaVersion"] == "1.0"
        and failure["status"]
        == "readback_consumed_failure_before_receipt"
        and type(failure["failureCode"]) is str
        and bool(failure["failureCode"])
        and type(failure["phase"]) is str
        and bool(failure["phase"])
        and failure["permitId"] == permit["permitId"]
        and failure["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and failure["readbackClaimRawSha256"] == sha256(claim_raw)
        and failure["resultRawSha256"] == sha256(result_raw)
        and failure["resultContentSha256"]
        == result["contentBinding"]["sha256"]
        and failure["evaluationManifestRawSha256"]
        == sha256(evaluation_manifest_raw)
        and failure["candidateSourceProjectionSha256"]
        == result["candidateSourceProjectionSha256"],
        "E_READBACK_FAILURE",
        "check",
    )
    exact_false(
        failure,
        (
            "automaticRetryAllowed",
            "receiptBackfillAllowed",
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "subprocessUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ),
        "E_READBACK_FAILURE",
    )


def publish_readback_failure_transaction(
    root: Path,
    permit_checker: types.ModuleType,
    context: Any,
    held_outputs: Any,
    claim_guard: Any,
    claim_raw: bytes,
    failure: Mapping[str, Any],
    permit: Mapping[str, Any],
    result: Mapping[str, Any],
) -> Any:
    failure_guard = None
    transaction_claim_guard = claim_guard
    owns_claim_guard = False
    failure_raw = canonical_bytes(failure)
    try:
        if transaction_claim_guard is None:
            transaction_claim_guard = context.decision_checker.HeldSet(
                root,
                [
                    {
                        "path": permit_checker.READBACK_CLAIM_PATH,
                        "rawSha256": sha256(claim_raw),
                        "maximumBytes": MAXIMUM_JSON_BYTES,
                        "ownerOnly": True,
                    }
                ],
            )
            owns_claim_guard = True
        write_exclusive(
            root,
            permit_checker.READBACK_FAILURE_PATH,
            failure_raw,
        )
        failure_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.READBACK_FAILURE_PATH,
                    "rawSha256": sha256(failure_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        held_outputs.final_barrier()
        transaction_claim_guard.final_barrier()
        failure_guard.final_barrier()
        require_readback_namespace(
            root,
            permit_checker,
            "readback_failure",
            context,
        )
        validate_readback_failure_bytes(
            transaction_claim_guard.raw[
                permit_checker.READBACK_CLAIM_PATH
            ],
            failure_guard.raw[permit_checker.READBACK_FAILURE_PATH],
            held_outputs.raw[permit_checker.RESULT_PATH],
            held_outputs.raw[permit_checker.MANIFEST_PATH],
            permit,
            result,
        )
        context.final_barrier()
        held_outputs.final_barrier()
        transaction_claim_guard.final_barrier()
        failure_guard.final_barrier()
        require_readback_namespace(
            root,
            permit_checker,
            "readback_failure",
            context,
        )
        context.namespace_barrier()
        if owns_claim_guard:
            transaction_claim_guard.close()
        return failure_guard
    except Exception as error:
        if owns_claim_guard and transaction_claim_guard is not None:
            transaction_claim_guard.close()
        if failure_guard is not None:
            failure_guard.close()
        raise ReadbackError(
            "E_READBACK_FAILURE_PUBLICATION_UNCERTAIN",
            "record",
        ) from error


def read_only_check(root: Path = ROOT) -> dict[str, Any]:
    require(isolated_interpreter(), "E_INTERPRETER", "check")
    permit_checker = load_permit_checker(root)
    initial, _ = state(root, permit_checker)
    if initial == "not_executed":
        checked = permit_checker.validate_repository(
            root,
            require_clean_namespace=True,
        )
        return {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-readback-check"
            ),
            "schemaVersion": "1.0",
            "status": "evaluation_not_executed_readback_not_recordable",
            "validationPassed": True,
            "terminalRecognized": False,
            "recordable": False,
            "permitId": checked["permit"]["permitId"],
            "heldSourceInputCount": 69,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessCount": 0,
            "fileWriteCount": 0,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        }
    require(
        initial
        in {
            "recordable",
            "recorded",
            "evaluation_failure",
            "readback_failure",
        },
        "E_STATE",
        "check",
    )
    context = permit_checker.open_authority_context(
        root,
        include_permit=True,
        require_clean_namespace=False,
    )
    held_outputs = None
    try:
        expected = permit_checker.content_bound(
            permit_checker.expected_payload(context)
        )
        permit = permit_checker.validate_permit_bytes(
            context.static.raw[permit_checker.PERMIT_PATH],
            expected,
        )
        if initial == "recorded":
            bindings = recorded_output_bindings(permit_checker)
        elif initial == "evaluation_failure":
            bindings = evaluation_failure_bindings(permit_checker)
        elif initial == "readback_failure":
            bindings = readback_failure_bindings(permit_checker)
        else:
            bindings = output_bindings(permit_checker)
        held_outputs = context.decision_checker.HeldSet(root, bindings)
        context.final_barrier()
        held_outputs.final_barrier()
        if initial == "evaluation_failure":
            validate_evaluation_failure(
                context,
                held_outputs,
                permit_checker,
                permit,
            )
            context.final_barrier()
            held_outputs.final_barrier()
            final, _ = state(root, permit_checker)
            require(final == initial, "E_TOCTOU", "check")
            return {
                "documentType": (
                    "aetherlink.g2-pion-combined-fixed-point-"
                    "readback-check"
                ),
                "schemaVersion": "1.0",
                "status": "validated_consumed_evaluation_failure",
                "validationPassed": True,
                "terminalRecognized": True,
                "recordable": False,
                "permitId": permit["permitId"],
                "heldSourceInputCount": 69,
                "networkUsed": False,
                "sourceExecutionUsed": False,
                "filesystemExtractionUsed": False,
                "subprocessCount": 0,
                "fileWriteCount": 0,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "signatureRequired": False,
                "privateKeyRequired": False,
                "tokenRequired": False,
                "passwordRequired": False,
                "userActionRequired": False,
            }
        candidate = context.candidate.generate_candidate(root)
        context.final_barrier()
        held_outputs.final_barrier()
        _, result, _ = validate_outputs(
            context,
            held_outputs,
            candidate,
            permit_checker,
            permit,
        )
        evaluation_manifest = strict_json(
            held_outputs.raw[permit_checker.MANIFEST_PATH]
        )
        if initial == "recorded":
            validate_recorded_readback(
                held_outputs,
                permit_checker,
                permit,
                result,
                evaluation_manifest,
            )
        elif initial == "readback_failure":
            validate_readback_failure(
                held_outputs,
                permit_checker,
                permit,
                result,
            )
        context.final_barrier()
        held_outputs.final_barrier()
        final, _ = state(root, permit_checker)
        require(final == initial, "E_TOCTOU", "check")
        return {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-readback-check"
            ),
            "schemaVersion": "1.0",
            "status": (
                "independent_recomputation_passed_recorded"
                if initial == "recorded"
                else (
                    "validated_consumed_readback_failure"
                    if initial == "readback_failure"
                    else "independent_recomputation_passed_not_recorded"
                )
            ),
            "validationPassed": True,
            "terminalRecognized": True,
            "recordable": initial == "recordable",
            "permitId": permit["permitId"],
            "resultContentSha256": result["contentBinding"]["sha256"],
            "freshHeldSourceInputCount": 69,
            "freshArchiveOpenCount": 70,
            "freshFullSourceReconstructionCount": 2,
            "sourceGraphAlgorithmsReexecutedByReadback": True,
            "archiveMembersReopened": True,
            "exactResultProjectionMatched": True,
            "fixedPointReached": False,
            "newTupleCount": 16,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessCount": 0,
            "fileWriteCount": 0,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        if held_outputs is not None:
            held_outputs.close()
        context.close()


def open_parent(root: Path, relative: str) -> tuple[int, str]:
    parts = safe_relative(relative).split("/")
    current = os.open(
        root,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | os.O_NONBLOCK
        | os.O_CLOEXEC,
    )
    try:
        for component in parts[:-1]:
            child = os.open(
                component,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=current,
            )
            info = os.fstat(child)
            require(
                stat.S_ISDIR(info.st_mode)
                and info.st_uid in {0, os.geteuid()}
                and stat.S_IMODE(info.st_mode) & 0o022 == 0,
                "E_PUBLICATION",
                "record",
            )
            os.close(current)
            current = child
        return current, parts[-1]
    except BaseException:
        os.close(current)
        raise


def write_exclusive(root: Path, relative: str, raw: bytes) -> str:
    parent, name = open_parent(root, relative)
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
            dir_fd=parent,
        )
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            require(written > 0, "E_PUBLICATION", "record")
            offset += written
        os.fsync(fd)
        os.fsync(parent)
        return sha256(raw)
    except FileExistsError as error:
        raise ReadbackError("E_NAMESPACE", "record") from error
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent)


def readback_claim(
    permit: Mapping[str, Any],
    result_raw_sha256: str,
) -> dict[str, Any]:
    return {
        "claimType": (
            "aetherlink.g2-pion-combined-fixed-point-readback-one-use-claim"
        ),
        "schemaVersion": "1.0",
        "attemptId": secrets.token_hex(16),
        "createdAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "resultRawSha256": result_raw_sha256,
        "candidateSourceProjectionSha256": permit["sourceInputSet"][
            "candidateSourceProjectionSha256"
        ],
        "automaticRetryAllowed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def readback_failure_document(
    error: Exception,
    permit: Mapping[str, Any],
    claim_raw: bytes,
    result_raw: bytes,
    result_content_sha256: str,
    evaluation_manifest_raw: bytes,
) -> dict[str, Any]:
    return content_bound(
        {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "readback-failure"
            ),
            "schemaVersion": "1.0",
            "status": "readback_consumed_failure_before_receipt",
            "failureCode": (
                error.code
                if isinstance(error, ReadbackError)
                else "E_INTERNAL"
            ),
            "phase": (
                error.phase
                if isinstance(error, ReadbackError)
                else "readback"
            ),
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "readbackClaimRawSha256": sha256(claim_raw),
            "resultRawSha256": sha256(result_raw),
            "resultContentSha256": result_content_sha256,
            "evaluationManifestRawSha256": sha256(
                evaluation_manifest_raw
            ),
            "candidateSourceProjectionSha256": permit["sourceInputSet"][
                "candidateSourceProjectionSha256"
            ],
            "automaticRetryAllowed": False,
            "receiptBackfillAllowed": False,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessUsed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        }
    )


def record(root: Path = ROOT) -> dict[str, Any]:
    require(isolated_interpreter(), "E_INTERPRETER", "record")
    permit_checker = load_permit_checker(root)
    initial, _ = state(root, permit_checker)
    require(initial == "recordable", "E_STATE", "record")
    context = permit_checker.open_authority_context(
        root,
        include_permit=True,
        require_clean_namespace=False,
    )
    held_outputs = None
    claim_guard = None
    receipt_guard = None
    manifest_guard = None
    failure_guard = None
    claim_written = False
    receipt_attempted = False
    permit = None
    claim_raw = b""
    result_raw = b""
    evaluation_manifest_raw = b""
    result_content_sha256 = ""
    preclaim_result: Mapping[str, Any] = {}
    try:
        expected = permit_checker.content_bound(
            permit_checker.expected_payload(context)
        )
        permit = permit_checker.validate_permit_bytes(
            context.static.raw[permit_checker.PERMIT_PATH],
            expected,
        )
        held_outputs = context.decision_checker.HeldSet(
            root,
            output_bindings(permit_checker),
        )
        result_raw = held_outputs.raw[permit_checker.RESULT_PATH]
        evaluation_manifest_raw = held_outputs.raw[
            permit_checker.MANIFEST_PATH
        ]
        preclaim_result = strict_json(result_raw)
        result_content_sha256 = preclaim_result.get(
            "contentBinding", {}
        ).get("sha256", "")
        claim = readback_claim(permit, sha256(result_raw))
        claim_raw = canonical_bytes(claim)
        write_exclusive(
            root,
            permit_checker.READBACK_CLAIM_PATH,
            claim_raw,
        )
        claim_written = True
        claim_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.READBACK_CLAIM_PATH,
                    "rawSha256": sha256(claim_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        held_outputs.final_barrier()
        claim_guard.final_barrier()
        require_readback_namespace(
            root, permit_checker, "after_claim", context
        )
        candidate = context.candidate.generate_candidate(root)
        context.final_barrier()
        held_outputs.final_barrier()
        claim_guard.final_barrier()
        require_readback_namespace(
            root, permit_checker, "after_claim", context
        )
        _, result, manifest = validate_outputs(
            context,
            held_outputs,
            candidate,
            permit_checker,
            permit,
        )
        receipt = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "independent-readback-receipt"
            ),
            "schemaVersion": "1.0",
            "status": "independent_readback_complete_manifest_pending",
            "permitId": permit["permitId"],
            "readbackClaimRawSha256": sha256(claim_raw),
            "resultRawSha256": sha256(result_raw),
            "resultContentSha256": result["contentBinding"]["sha256"],
            "evaluationManifestRawSha256": sha256(
                held_outputs.raw[permit_checker.MANIFEST_PATH]
            ),
            "freshHeldSourceInputCount": 69,
            "freshArchiveOpenCount": 70,
            "freshFullSourceReconstructionCount": 2,
            "sourceGraphAlgorithmsReexecutedByReadback": True,
            "archiveMembersReopened": True,
            "exactResultProjectionMatched": True,
            "graphSha256": result["graphSha256"],
            "candidateSourceProjectionSha256": result[
                "candidateSourceProjectionSha256"
            ],
            "fixedPointReached": False,
            "newTupleCount": 16,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessUsed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "publish_combined_fixed_point_readback_manifest_last"
            ),
        }
        receipt_raw = canonical_bytes(receipt)
        receipt_attempted = True
        write_exclusive(
            root,
            permit_checker.READBACK_RECEIPT_PATH,
            receipt_raw,
        )
        receipt_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.READBACK_RECEIPT_PATH,
                    "rawSha256": sha256(receipt_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        held_outputs.final_barrier()
        claim_guard.final_barrier()
        receipt_guard.final_barrier()
        require_readback_namespace(
            root, permit_checker, "after_receipt", context
        )
        readback_manifest = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "independent-readback-manifest"
            ),
            "schemaVersion": "1.0",
            "status": "independent_readback_published_not_fixed_point",
            "manifestWrittenLast": True,
            "permitId": permit["permitId"],
            "readbackClaimRawSha256": sha256(claim_raw),
            "readbackReceiptPath": permit_checker.READBACK_RECEIPT_PATH,
            "readbackReceiptRawSha256": sha256(receipt_raw),
            "resultRawSha256": sha256(result_raw),
            "evaluationManifestRawSha256": sha256(
                canonical_bytes(manifest)
            ),
            "candidateSourceProjectionSha256": result[
                "candidateSourceProjectionSha256"
            ],
            "fixedPointReached": False,
            "newTupleCount": 16,
            "independentReadbackPassed": True,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "prepare_separate_new_dependency_wave_decision_for_"
                "remaining_16_frontier_tuples"
            ),
        }
        manifest_raw = canonical_bytes(readback_manifest)
        write_exclusive(
            root,
            permit_checker.READBACK_MANIFEST_PATH,
            manifest_raw,
        )
        manifest_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.READBACK_MANIFEST_PATH,
                    "rawSha256": sha256(manifest_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        held_outputs.final_barrier()
        claim_guard.final_barrier()
        receipt_guard.final_barrier()
        manifest_guard.final_barrier()
        require_readback_namespace(
            root, permit_checker, "complete", context
        )
        context.namespace_barrier()
        return readback_manifest
    except Exception as error:
        if claim_written and not receipt_attempted:
            require(
                permit is not None and held_outputs is not None,
                "E_INTERNAL",
                "record",
            )
            failure = readback_failure_document(
                error,
                permit,
                claim_raw,
                result_raw,
                result_content_sha256,
                evaluation_manifest_raw,
            )
            failure_guard = publish_readback_failure_transaction(
                root,
                permit_checker,
                context,
                held_outputs,
                claim_guard,
                claim_raw,
                failure,
                permit,
                preclaim_result,
            )
        if receipt_attempted:
            raise ReadbackError(
                "E_POST_RECEIPT_PUBLICATION_UNCERTAIN",
                "record",
            ) from None
        if isinstance(error, ReadbackError):
            raise
        raise ReadbackError("E_INTERNAL", "record") from error
    finally:
        for guard in (
            failure_guard,
            manifest_guard,
            receipt_guard,
            claim_guard,
            held_outputs,
        ):
            if guard is not None:
                guard.close()
        context.close()


def error_document(failure: ReadbackError) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-readback-error"
        ),
        "schemaVersion": "1.0",
        "status": "failed_closed_or_consumed_uncertain",
        "failureCode": failure.code,
        "phase": failure.phase,
        "automaticRetryAllowed": False,
        "networkUsed": False,
        "sourceExecutionUsed": False,
        "filesystemExtractionUsed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "signatureRequired": False,
        "privateKeyRequired": False,
        "tokenRequired": False,
        "passwordRequired": False,
        "userActionRequired": False,
    }


def parse_arguments(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--record", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        require(isolated_interpreter(), "E_INTERPRETER", "cli")
        args = parse_arguments(argv)
        output = record(ROOT) if args.record else read_only_check(ROOT)
    except ReadbackError as failure:
        sys.stdout.buffer.write(canonical_bytes(error_document(failure)))
        return 1
    except Exception:
        failure = ReadbackError("E_INTERNAL", "readback")
        sys.stdout.buffer.write(canonical_bytes(error_document(failure)))
        return 1
    sys.stdout.buffer.write(canonical_bytes(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
