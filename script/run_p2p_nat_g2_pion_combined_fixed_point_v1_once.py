#!/usr/bin/env python3
"""Run the exact combined fixed-point gate at most once.

Default mode is read-only ``--preflight``.  ``--execute`` consumes the permit;
it is intentionally not invoked by repository verification.  The executor
uses no network, subprocess, source execution, or filesystem extraction.
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


class RunnerError(RuntimeError):
    def __init__(self, code: str, phase: str) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise RunnerError("E_ARGUMENTS", "cli")


def require(condition: bool, code: str, phase: str) -> None:
    if not condition:
        raise RunnerError(code, phase)


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


def strict_json(raw: bytes) -> dict[str, Any]:
    def object_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            require(key not in value, "E_JSON", "validation")
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
        raise RunnerError("E_JSON", "validation") from error
    require(type(value) is dict, "E_JSON", "validation")
    return value


def _json_failure() -> Any:
    raise RunnerError("E_JSON", "validation")


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


def bootstrap_permit_checker(root: Path) -> types.ModuleType:
    relative = PERMIT_CHECKER_PATH
    current = root
    for component in relative.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_TOOL_IDENTITY",
            "preflight",
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
            and before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_TOOL_IDENTITY",
            "preflight",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_TOOL_IDENTITY", "preflight")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_TOOL_IDENTITY", "preflight")
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
            "preflight",
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
        raise RunnerError("E_TOOL_LOAD", "preflight") from error
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
        "publication",
    )
    return value


def path_kind(root: Path, relative: str) -> str:
    try:
        info = os.lstat(root / safe_relative(relative))
    except FileNotFoundError:
        return "absent"
    except OSError as error:
        raise RunnerError("E_NAMESPACE", "preflight") from error
    return "regular" if stat.S_ISREG(info.st_mode) else "other"


def classify_state(
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
    kinds = {key: path_kind(root, path) for key, path in paths.items()}
    if all(value == "absent" for value in kinds.values()):
        return "clean", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["result"] == "regular"
        and kinds["failure"] == "absent"
        and kinds["manifest"] == "regular"
        and all(kinds[key] == "absent" for key in (
            "readbackClaim",
            "readbackReceipt",
            "readbackFailure",
            "readbackManifest",
        ))
    ):
        return "success_pending_readback", kinds
    if (
        kinds["claim"] == "regular"
        and kinds["failure"] == "regular"
        and kinds["result"] == "absent"
        and kinds["manifest"] == "absent"
        and all(kinds[key] == "absent" for key in (
            "readbackClaim",
            "readbackReceipt",
            "readbackFailure",
            "readbackManifest",
        ))
    ):
        return "consumed_failure", kinds
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
        return "readback_complete", kinds
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
    return "blocked", kinds


def require_execution_namespace(
    root: Path,
    permit_checker: types.ModuleType,
    phase: str,
    context: Any | None = None,
) -> None:
    expected_by_phase = {
        "after_claim": {
            "claim": "regular",
            "result": "absent",
            "failure": "absent",
            "manifest": "absent",
            "readbackClaim": "absent",
            "readbackReceipt": "absent",
            "readbackFailure": "absent",
            "readbackManifest": "absent",
        },
        "after_result": {
            "claim": "regular",
            "result": "regular",
            "failure": "absent",
            "manifest": "absent",
            "readbackClaim": "absent",
            "readbackReceipt": "absent",
            "readbackFailure": "absent",
            "readbackManifest": "absent",
        },
        "success": {
            "claim": "regular",
            "result": "regular",
            "failure": "absent",
            "manifest": "regular",
            "readbackClaim": "absent",
            "readbackReceipt": "absent",
            "readbackFailure": "absent",
            "readbackManifest": "absent",
        },
        "failure": {
            "claim": "regular",
            "result": "absent",
            "failure": "regular",
            "manifest": "absent",
            "readbackClaim": "absent",
            "readbackReceipt": "absent",
            "readbackFailure": "absent",
            "readbackManifest": "absent",
        },
    }
    require(phase in expected_by_phase, "E_INTERNAL", "publication")
    _, kinds = classify_state(root, permit_checker)
    require(
        kinds == expected_by_phase[phase],
        "E_NAMESPACE",
        "publication",
    )
    if context is not None:
        try:
            context.namespace_barrier()
        except Exception as error:
            raise RunnerError("E_NAMESPACE", "publication") from error


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
                "publication",
            )
            os.close(current)
            current = child
        return current, parts[-1]
    except BaseException:
        os.close(current)
        raise


def write_exclusive(root: Path, relative: str, raw: bytes) -> str:
    require(
        0 < len(raw) <= MAXIMUM_JSON_BYTES,
        "E_PUBLICATION",
        "publication",
    )
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
            require(written > 0, "E_PUBLICATION", "publication")
            offset += written
        os.fsync(fd)
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_nlink == 1
            and info.st_size == len(raw),
            "E_PUBLICATION",
            "publication",
        )
        os.fsync(parent)
        return sha256(raw)
    except FileExistsError as error:
        raise RunnerError("E_NAMESPACE", "publication") from error
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent)


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


def candidate_projection(candidate: Mapping[str, Any]) -> dict[str, Any]:
    require(
        type(candidate) is dict
        and all(field in candidate for field in PROJECTION_FIELDS),
        "E_CANDIDATE",
        "evaluation",
    )
    return {field: candidate[field] for field in PROJECTION_FIELDS}


def result_document(
    candidate: Mapping[str, Any],
    permit: Mapping[str, Any],
    decision: Mapping[str, Any],
    claim_raw: bytes,
) -> dict[str, Any]:
    projection = candidate_projection(candidate)
    graph = projection["graphDiscovery"]
    require(
        projection["route"] == "next_wave_required"
        and graph["fixedPointReached"] is False
        and graph["newTupleCount"] == 16
        and all(value is False for value in projection["closure"].values()),
        "E_CANDIDATE_ROUTE",
        "evaluation",
    )
    body = {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-evaluation-result"
        ),
        "schemaVersion": "1.0",
        "evaluationId": (
            "g2-pion-ice-v4.3.0-combined-fixed-point-evaluation-v1"
        ),
        "status": (
            "combined_evaluation_complete_not_fixed_point_"
            "new_wave_required"
        ),
        "result": (
            "exact_69_input_combined_graph_recomputed_frontier_16"
        ),
        "decisionBinding": {
            "decisionId": decision["decisionId"],
            "rawSha256": permit["decisionBinding"]["rawSha256"],
            "contentSha256": decision["contentBinding"]["sha256"],
        },
        "permitBinding": {
            "permitId": permit["permitId"],
            "contentSha256": permit["contentBinding"]["sha256"],
        },
        "claimRawSha256": sha256(claim_raw),
        "candidateProviderBinding": permit["candidateProviderBinding"],
        "immutableGraphProviderBinding": (
            permit["immutableGraphProviderBinding"]
        ),
        "candidateContentSha256": candidate["contentBinding"]["sha256"],
        "candidateSourceProjectionSha256": projection["inputSet"][
            "combinedInputSetSha256"
        ],
        "graphSha256": graph["graphSha256"],
        "candidateProjection": projection,
        "fixedPointReached": False,
        "dependencySourceReviewed": False,
        "semanticClosureComplete": False,
        "rungThreeComplete": False,
        "candidateSelected": False,
        "librarySelected": False,
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
            "run_separate_combined_fixed_point_independent_readback"
        ),
    }
    result = dict(body)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "result_without_contentBinding",
        "sha256": sha256(canonical_bytes(body)),
    }
    return result


def claim_document(
    permit: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "claimType": (
            "aetherlink.g2-pion-combined-fixed-point-one-use-claim"
        ),
        "schemaVersion": "1.0",
        "attemptId": secrets.token_hex(16),
        "createdAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "decisionId": decision["decisionId"],
        "decisionContentSha256": decision["contentBinding"]["sha256"],
        "decisionHeldBindingSetSha256": permit["sourceInputSet"][
            "decisionHeldBindingSetSha256"
        ],
        "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode": True,
        "automaticRetryAllowed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def failure_document(
    error: Exception,
    permit: Mapping[str, Any],
    decision: Mapping[str, Any],
    claim_raw: bytes,
) -> dict[str, Any]:
    return content_bound(
        {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "evaluation-failure"
            ),
            "schemaVersion": "1.0",
            "status": "consumed_failure_before_result_publication",
            "failureCode": (
                error.code
                if isinstance(error, RunnerError)
                else "E_INTERNAL"
            ),
            "phase": (
                error.phase
                if isinstance(error, RunnerError)
                else "evaluation"
            ),
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "decisionId": decision["decisionId"],
            "decisionContentSha256": decision["contentBinding"]["sha256"],
            "claimRawSha256": sha256(claim_raw),
            "decisionHeldBindingSetSha256": permit["sourceInputSet"][
                "decisionHeldBindingSetSha256"
            ],
            "automaticRetryAllowed": False,
            "resultBackfillAllowed": False,
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
FAILURE_KEYS = {
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


def validate_failure_bytes(
    claim_raw: bytes,
    failure_raw: bytes,
    permit: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    claim = strict_json(claim_raw)
    failure = strict_json(failure_raw)
    require(
        claim_raw == canonical_bytes(claim)
        and failure_raw == canonical_bytes(failure),
        "E_FAILURE_CANONICAL",
        "validation",
    )
    require(set(claim) == CLAIM_KEYS, "E_FAILURE_CLAIM", "validation")
    require(
        claim["claimType"]
        == "aetherlink.g2-pion-combined-fixed-point-one-use-claim"
        and claim["schemaVersion"] == "1.0"
        and claim["permitId"] == permit["permitId"]
        and claim["permitContentSha256"]
        == permit["contentBinding"]["sha256"]
        and claim["decisionId"] == decision["decisionId"]
        and claim["decisionContentSha256"]
        == decision["contentBinding"]["sha256"]
        and claim["decisionHeldBindingSetSha256"]
        == permit["sourceInputSet"]["decisionHeldBindingSetSha256"]
        and claim[
            "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode"
        ]
        is True
        and all(
            claim[field] is False
            for field in (
                "automaticRetryAllowed",
                "repositoryOwnerIdentityProofRequired",
                "externalAuthenticationRequired",
                "userActionRequired",
            )
        ),
        "E_FAILURE_CLAIM",
        "validation",
    )
    require(set(failure) == FAILURE_KEYS, "E_FAILURE", "validation")
    without = dict(failure)
    binding = without.pop("contentBinding", None)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": "document_without_contentBinding",
            "sha256": sha256(canonical_bytes(without)),
        }
        and failure["documentType"]
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
        and failure["decisionId"] == decision["decisionId"]
        and failure["decisionContentSha256"]
        == decision["contentBinding"]["sha256"]
        and failure["claimRawSha256"] == sha256(claim_raw)
        and failure["decisionHeldBindingSetSha256"]
        == permit["sourceInputSet"]["decisionHeldBindingSetSha256"]
        and all(
            failure[field] is False
            for field in (
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
            )
        ),
        "E_FAILURE",
        "validation",
    )
    return failure


def publish_failure_transaction(
    root: Path,
    permit_checker: types.ModuleType,
    context: Any,
    claim_guard: Any,
    claim_raw: bytes,
    failure: Mapping[str, Any],
    permit: Mapping[str, Any],
    decision: Mapping[str, Any],
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
                        "path": permit_checker.CLAIM_PATH,
                        "rawSha256": sha256(claim_raw),
                        "maximumBytes": MAXIMUM_JSON_BYTES,
                        "ownerOnly": True,
                    }
                ],
            )
            owns_claim_guard = True
        write_exclusive(
            root,
            permit_checker.FAILURE_PATH,
            failure_raw,
        )
        failure_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.FAILURE_PATH,
                    "rawSha256": sha256(failure_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        transaction_claim_guard.final_barrier()
        failure_guard.final_barrier()
        require_execution_namespace(
            root,
            permit_checker,
            "failure",
            context,
        )
        validate_failure_bytes(
            transaction_claim_guard.raw[permit_checker.CLAIM_PATH],
            failure_guard.raw[permit_checker.FAILURE_PATH],
            permit,
            decision,
        )
        context.final_barrier()
        transaction_claim_guard.final_barrier()
        failure_guard.final_barrier()
        require_execution_namespace(
            root,
            permit_checker,
            "failure",
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
        raise RunnerError(
            "E_FAILURE_PUBLICATION_UNCERTAIN",
            "publication",
        ) from error


def validate_terminal_with_readback(
    root: Path,
    permit_checker: types.ModuleType,
) -> None:
    context = permit_checker.open_authority_context(
        root,
        include_permit=True,
        require_clean_namespace=False,
    )
    try:
        raw = context.static.raw[permit_checker.READBACK_CHECKER_PATH]
        module = permit_checker.execute_module(
            "aetherlink_combined_fixed_point_terminal_readback_v1",
            permit_checker.READBACK_CHECKER_PATH,
            raw,
            root,
        )
        output = module.read_only_check(root)
        require(
            output.get("validationPassed") is True
            and output.get("terminalRecognized") is True,
            "E_TERMINAL",
            "preflight",
        )
        context.final_barrier()
    except RunnerError:
        raise
    except Exception as error:
        raise RunnerError("E_TERMINAL", "preflight") from error
    finally:
        context.close()


def preflight(root: Path = ROOT) -> dict[str, Any]:
    require(isolated_interpreter(), "E_INTERPRETER", "preflight")
    permit_checker = bootstrap_permit_checker(root)
    initial, _ = classify_state(root, permit_checker)
    checked = permit_checker.validate_repository(
        root,
        require_clean_namespace=initial == "clean",
    )
    final, _ = classify_state(root, permit_checker)
    require(initial == final, "E_TOCTOU", "preflight")
    require(
        final
        in {
            "clean",
            "success_pending_readback",
            "consumed_failure",
            "readback_complete",
            "readback_failure",
        },
        "E_ONE_USE_STATE",
        "preflight",
    )
    if final != "clean":
        validate_terminal_with_readback(root, permit_checker)
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-runner-preflight"
        ),
        "schemaVersion": "1.0",
        "status": (
            "passed_authorized_not_consumed"
            if final == "clean"
            else f"passed_{final}"
        ),
        "validationPassed": True,
        "permitId": checked["permit"]["permitId"],
        "oneUseState": final,
        "permitConsumptionState": (
            "authorized_not_consumed"
            if final == "clean"
            else "consumed"
        ),
        "heldSourceInputCount": 69,
        "networkOperationCount": 0,
        "sourceExecutionCount": 0,
        "filesystemExtractionCount": 0,
        "subprocessCount": 0,
        "fileWriteCount": 0,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "signatureRequired": False,
        "privateKeyRequired": False,
        "tokenRequired": False,
        "passwordRequired": False,
        "userActionRequired": False,
        "nextAction": (
            permit_checker.EXPECTED_NEXT_ACTION
            if final == "clean"
            else "inspect_consumed_terminal_state_without_retry"
        ),
    }


def execute_once(root: Path = ROOT) -> dict[str, Any]:
    require(isolated_interpreter(), "E_INTERPRETER", "execution")
    permit_checker = bootstrap_permit_checker(root)
    context = permit_checker.open_authority_context(
        root,
        include_permit=True,
        require_clean_namespace=True,
    )
    claim_guard = None
    result_guard = None
    manifest_guard = None
    failure_guard = None
    claim_written = False
    result_attempted = False
    try:
        expected = permit_checker.content_bound(
            permit_checker.expected_payload(context)
        )
        permit = permit_checker.validate_permit_bytes(
            context.static.raw[permit_checker.PERMIT_PATH],
            expected,
        )
        permit_checker.validate_reverse_pins(context)
        decision = context.decision
        context.final_barrier()
        permit_checker.validate_namespace_absent(root)
        claim = claim_document(permit, decision)
        claim_raw = canonical_bytes(claim)
        write_exclusive(root, permit_checker.CLAIM_PATH, claim_raw)
        claim_written = True
        claim_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.CLAIM_PATH,
                    "rawSha256": sha256(claim_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        claim_guard.final_barrier()
        require_execution_namespace(
            root, permit_checker, "after_claim", context
        )
        candidate = context.candidate.generate_candidate(root)
        context.final_barrier()
        claim_guard.final_barrier()
        require_execution_namespace(
            root, permit_checker, "after_claim", context
        )
        result = result_document(candidate, permit, decision, claim_raw)
        result_raw = canonical_bytes(result)
        result_attempted = True
        write_exclusive(root, permit_checker.RESULT_PATH, result_raw)
        result_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.RESULT_PATH,
                    "rawSha256": sha256(result_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        claim_guard.final_barrier()
        result_guard.final_barrier()
        require_execution_namespace(
            root, permit_checker, "after_result", context
        )
        manifest = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "evaluation-manifest"
            ),
            "schemaVersion": "1.0",
            "manifestWrittenLast": True,
            "permitId": permit["permitId"],
            "decisionId": decision["decisionId"],
            "claimRawSha256": sha256(claim_raw),
            "resultPath": permit_checker.RESULT_PATH,
            "resultRawSha256": sha256(result_raw),
            "resultContentSha256": result["contentBinding"]["sha256"],
            "resultStatus": result["status"],
            "decisionHeldBindingSetSha256": permit["sourceInputSet"][
                "decisionHeldBindingSetSha256"
            ],
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
            "userActionRequired": False,
            "nextAction": (
                "run_separate_combined_fixed_point_independent_readback"
            ),
        }
        manifest_raw = canonical_bytes(manifest)
        write_exclusive(
            root,
            permit_checker.MANIFEST_PATH,
            manifest_raw,
        )
        manifest_guard = context.decision_checker.HeldSet(
            root,
            [
                {
                    "path": permit_checker.MANIFEST_PATH,
                    "rawSha256": sha256(manifest_raw),
                    "maximumBytes": MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )
        context.final_barrier()
        claim_guard.final_barrier()
        result_guard.final_barrier()
        manifest_guard.final_barrier()
        require_execution_namespace(
            root, permit_checker, "success", context
        )
        context.namespace_barrier()
        return result
    except Exception as error:
        if claim_written and not result_attempted:
            failure = failure_document(error, permit, decision, claim_raw)
            failure_guard = publish_failure_transaction(
                root,
                permit_checker,
                context,
                claim_guard,
                claim_raw,
                failure,
                permit,
                decision,
            )
        if result_attempted:
            raise RunnerError(
                "E_POST_RESULT_PUBLICATION_UNCERTAIN",
                "publication",
            ) from None
        if isinstance(error, RunnerError):
            raise
        raise RunnerError("E_INTERNAL", "evaluation") from error
    finally:
        for guard in (
            failure_guard,
            manifest_guard,
            result_guard,
            claim_guard,
        ):
            if guard is not None:
                guard.close()
        context.close()


def error_document(failure: RunnerError) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-runner-error"
        ),
        "schemaVersion": "1.0",
        "status": "failed_closed_or_consumed_uncertain",
        "failureCode": failure.code,
        "phase": failure.phase,
        "automaticRetryAllowed": False,
        "networkOperationCount": 0,
        "sourceExecutionCount": 0,
        "filesystemExtractionCount": 0,
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
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        require(isolated_interpreter(), "E_INTERPRETER", "cli")
        args = parse_arguments(argv)
        output = execute_once(ROOT) if args.execute else preflight(ROOT)
    except RunnerError as failure:
        sys.stdout.buffer.write(canonical_bytes(error_document(failure)))
        return 1
    except Exception:
        failure = RunnerError("E_INTERNAL", "runner")
        sys.stdout.buffer.write(canonical_bytes(error_document(failure)))
        return 1
    sys.stdout.buffer.write(canonical_bytes(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
