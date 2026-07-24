#!/usr/bin/env python3
"""Validate the permanently closed recovery readback v2 authority."""

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
    raise RuntimeError("recovery closure requires `python3 -I -B -S`")

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v2.py"
)
EXPECTED_PERMIT_CHECKER_RAW_SHA256 = (
    "0dbee20b227c685c14d27178173a01eeab365579066ea904c1fea87c3c941fac"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024


class ReadbackError(RuntimeError):
    def __init__(self, code: str, phase: str) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase


def require(value: bool, code: str, phase: str) -> None:
    if not value:
        raise ReadbackError(code, phase)


def load_permit_checker(root: Path) -> types.ModuleType:
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
            os.O_RDONLY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
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
    path = root / PERMIT_CHECKER_PATH
    module = types.ModuleType("combined_recovery_readback_v2_closure_permit")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(path),
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
    namespace = permit_checker.RECOVERY.TRUST.HeldNamespace(root)
    try:
        namespace.final_barrier()
        phase = permit_checker.classify_phase(namespace)
        namespace.final_barrier()
        return phase
    finally:
        namespace.close()


def validate_permit(
    context: Any,
    permit_checker: Any,
) -> dict[str, Any]:
    expected = permit_checker.expected_permit(context)
    raw = context.package.raw[permit_checker.PERMIT_PATH]
    actual = permit_checker.strict_json(raw)
    require(
        raw == permit_checker.canonical_bytes(actual)
        and actual == expected,
        "E_PERMIT",
        "check",
    )
    return actual


def validate_closed_authority(permit: Mapping[str, Any]) -> None:
    authority = permit["authority"]
    require(
        permit["status"]
        == "diagnostic_readback_authority_consumed_or_uncertain"
        and permit["result"] == "v2_recovery_readback_recording_closed"
        and permit["nextAction"]
        == "prepare_separate_v3_recovery_decision_and_one_use_permit"
        and authority["oneOfflineReadbackAuthorized"] is False
        and authority["claimWriteAuthorized"] is False
        and authority["receiptOrFailureWriteAuthorized"] is False
        and authority["manifestOnSuccessWriteAuthorized"] is False
        and permit["oneUseContract"]["formalRecordAttemptAuthorized"] is False
        and permit["priorDraftDiagnosticObservation"][
            "authorityConsumptionState"
        ]
        == "consumed_or_uncertain",
        "E_AUTHORITY",
        "check",
    )


def closure_snapshot(
    root: Path = ROOT,
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    permit_checker = load_permit_checker(root)
    phase = observed_phase(root, permit_checker)
    require(
        phase == "recordable",
        "E_UNAUTHORIZED_POST_CLOSURE_ARTIFACT",
        "check",
    )
    context = permit_checker.ExecutionAuthorityContext(
        root,
        include_permit=True,
        phase="recordable",
    )
    try:
        permit = validate_permit(context, permit_checker)
        validate_closed_authority(permit)
        result = permit_checker.strict_json(
            context.terminal.raw[permit_checker.RECOVERY.RESULT_PATH]
        )
        manifest = permit_checker.strict_json(
            context.terminal.raw[permit_checker.RECOVERY.MANIFEST_PATH]
        )
        require(
            result["graphSha256"]
            == permit_checker.RECOVERY.EXPECTED_GRAPH_SHA256
            and result["contentBinding"]["sha256"]
            == permit_checker.RECOVERY.EXPECTED_RESULT_CONTENT_SHA256
            and manifest["newTupleCount"] == 16
            and result["fixedPointReached"] is False,
            "E_TERMINAL",
            "check",
        )
        context.final_barrier("recordable")
        return permit_checker, permit, result, manifest
    finally:
        context.close()


def check(root: Path = ROOT) -> dict[str, Any]:
    permit_checker, permit, result, manifest = closure_snapshot(root)
    del permit_checker
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-recovery-v2-closure-check"
        ),
        "schemaVersion": "2.0",
        "status": "v2_authority_consumed_or_uncertain_static_closure_validated",
        "validationPassed": True,
        "recordable": False,
        "namespaceRecordableShape": True,
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


def record(root: Path = ROOT) -> dict[str, Any]:
    closure_snapshot(root)
    raise ReadbackError("E_AUTHORITY_CONSUMED", "record")


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise ReadbackError("E_ARGUMENT", "cli")


def error_document(error: ReadbackError) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-recovery-v2-error"
        ),
        "schemaVersion": "2.0",
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
