#!/usr/bin/env python3
"""Validate the one-use replacement recovery execution permit v3."""

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
    raise RuntimeError("v3 permit checker requires `python3 -I -B -S`")

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v3.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v3.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v3.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v3.py"
)
EXPECTED_DECISION_RAW = (
    "0b650f466e2ef2df2362d11747d15b34db96ef6a63e70556f443137fd43390df"
)
EXPECTED_DECISION_READER_RAW = (
    "f61239840e3adfdfe7e234200be34d79788bf3e642a4bc357b074ea05e740556"
)
EXPECTED_DECISION_CHECKER_RAW = (
    "db6f13b57367758e7ae68ec9a82a2f38df5a61742b66b8531e5d3a2a35c6a053"
)
EXPECTED_DECISION_TESTS_RAW = (
    "761b2bd5d92547855521254f90bbabf12a6a94a72c829d4d8b2fd6eeba6c26a6"
)
EXPECTED_DECISION_CONTENT = (
    "7600954f9887ffdd629a56eca6f3eed20542c0843787a3b8f5cfb240b17781ff"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-execution-permit-v3.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-execution-permit-v3.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v3.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v3.py"
)
RECORDER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "success_v1_recovery_v3.py"
)
RECORDER_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "success_v1_recovery_v3.py"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "b7de3754fdf0522ad7f30c98f9f593619d24fb33b50900df599f1189651dea7a"
)
EXPECTED_RECORDER_TESTS_RAW_SHA256 = (
    "afa7c14b181807155199a8cc609ec1e69e36f98840f12d019b3780161052c520"
)
REVERSE_PIN_NAME = "EXPECTED_PERMIT_CHECKER_RAW_SHA256"
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
V3_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.combined-fixed-point-readback-v3.claim"
V3_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v3.json"
)
V3_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-failure-v3.json"
)
V3_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-manifest-v3.json"
)
V3_PATHS = (V3_CLAIM_PATH, V3_RECEIPT_PATH, V3_FAILURE_PATH, V3_MANIFEST_PATH)
V3_STAGING_PREFIX = ".combined-fixed-point-readback-v3-staging-"
PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-fixed-point-"
    "readback-recovery-execution-permit-v3"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024

READER_BYTES = b"""# Combined fixed-point recovery execution permit v3

This permit authorizes exactly one formal offline replacement recovery
readback. The recorder must durably create and owner-only reopen its v3 claim
before any fresh archive-member open or decode in the formal attempt.

It does not authorize retry, resume, backfill, original evaluation, network
use, source execution, extraction, subprocesses, Git, devices, deployment,
authentication, credentials, signatures, or user action. Receipt publication
attempt begins before its exclusive write; no failure may be backfilled after
that point. The manifest is written last.
"""


class PermitError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(value: bool, code: str) -> None:
    if not value:
        raise PermitError(code)


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
        ).encode()
        + b"\n"
    )


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(PermitError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(PermitError("E_JSON")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def bootstrap_read(path: str, expected: str) -> bytes:
    current = ROOT
    for component in path.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_BOOTSTRAP",
        )
    fd = os.open(
        ROOT / path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
    )
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_BOOTSTRAP",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_BOOTSTRAP")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_BOOTSTRAP")
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
            and sha256(raw) == expected,
            "E_BOOTSTRAP",
        )
        return raw
    finally:
        os.close(fd)


def execute_module(name: str, path: str, raw: bytes) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / path),
            "__loader__": None,
            "__name__": name,
            "__package__": None,
        }
    )
    exec(
        compile(raw, path, "exec", dont_inherit=True, optimize=0),
        module.__dict__,
        module.__dict__,
    )
    return module


DECISION = execute_module(
    "combined_recovery_decision_v3_frozen",
    DECISION_CHECKER_PATH,
    bootstrap_read(DECISION_CHECKER_PATH, EXPECTED_DECISION_CHECKER_RAW),
)


def unique_module_string_assignment(source: str, name: str) -> tuple[str, int, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise PermitError("E_TOOL_FREEZE") from error
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
        and isinstance(node.value, ast.Constant)
        and type(node.value.value) is str
    ]
    require(len(assignments) == 1, "E_TOOL_FREEZE")
    assignment = assignments[0]
    target = assignment.targets[0]
    bound_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, (ast.Store, ast.Del))
        and node.id == name
    ]
    require(len(bound_nodes) == 1 and bound_nodes[0] is target, "E_TOOL_FREEZE")
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.alias):
            names.append(node.asname or node.name.split(".", 1)[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.append(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.extend(node.names)
        elif hasattr(ast, "MatchAs") and isinstance(node, ast.MatchAs) and node.name:
            names.append(node.name)
        elif hasattr(ast, "MatchStar") and isinstance(node, ast.MatchStar) and node.name:
            names.append(node.name)
        elif (
            hasattr(ast, "MatchMapping")
            and isinstance(node, ast.MatchMapping)
            and node.rest
        ):
            names.append(node.rest)
        require(name not in names, "E_TOOL_FREEZE")
    value = assignment.value.value
    require(
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        "E_TOOL_FREEZE",
    )
    segment = ast.get_source_segment(source, assignment.value)
    require(segment == f'"{value}"', "E_TOOL_FREEZE")
    lines = source.encode().splitlines(keepends=True)
    start = (
        sum(len(line) for line in lines[: assignment.value.lineno - 1])
        + assignment.value.col_offset
        + 1
    )
    return value, start, start + 64


def normalized_recorder_sha256(raw: bytes) -> str:
    try:
        source = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PermitError("E_TOOL_FREEZE") from error
    _, start, end = unique_module_string_assignment(source, REVERSE_PIN_NAME)
    return sha256(raw[:start] + b"0" * 64 + raw[end:])


def phase_shape(phase: str) -> tuple[bool, bool, bool, bool]:
    shapes = {
        "recordable": (False, False, False, False),
        "after_claim": (True, False, False, False),
        "failure": (True, False, True, False),
        "after_receipt": (True, True, False, False),
        "complete": (True, True, False, True),
    }
    require(phase in shapes, "E_PHASE")
    return shapes[phase]


def classify_phase(namespace: Any) -> str:
    kinds = tuple(
        "absent"
        if DECISION.V2.RECOVERY.absent_from_held_namespace(namespace, path)
        else "regular"
        for path in V3_PATHS
    )
    for phase in ("recordable", "after_claim", "failure", "after_receipt", "complete"):
        expected = tuple(
            "regular" if present else "absent"
            for present in phase_shape(phase)
        )
        if kinds == expected:
            return phase
    return "blocked"


def package_bindings(include_permit: bool) -> list[dict[str, Any]]:
    paths = [
        PERMIT_READER_PATH,
        THIS_CHECKER_PATH,
        THIS_TESTS_PATH,
        RECORDER_PATH,
        RECORDER_TESTS_PATH,
    ]
    if include_permit:
        paths.append(PERMIT_PATH)
    return [
        {
            "path": path,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES if path.startswith("docs/") else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        for path in paths
    ]


def decision_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES if path.startswith("docs/") else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        for path, digest in (
            (DECISION_PATH, EXPECTED_DECISION_RAW),
            (DECISION_READER_PATH, EXPECTED_DECISION_READER_RAW),
            (DECISION_CHECKER_PATH, EXPECTED_DECISION_CHECKER_RAW),
            (DECISION_TESTS_PATH, EXPECTED_DECISION_TESTS_RAW),
        )
    ]


def v2_closure_bindings() -> list[dict[str, Any]]:
    return DECISION.v2_closure_bindings()


class PermitContext:
    def __init__(self, root: Path, *, include_permit: bool, phase: str) -> None:
        self.root = root
        self.phase = phase
        self.authority = None
        self.v2_closure = None
        self.decision_package = None
        self.package = None
        try:
            self.authority = DECISION.V2.ExecutionAuthorityContext(
                root,
                include_permit=True,
                phase="recordable",
            )
            self.v2_closure = self.authority.decision_checker.HeldSet(
                root,
                v2_closure_bindings(),
            )
            self.decision_package = self.authority.decision_checker.HeldSet(
                root,
                decision_bindings(),
            )
            self.package = self.authority.decision_checker.HeldSet(
                root,
                package_bindings(include_permit),
            )
            decision_raw = self.decision_package.raw[DECISION_PATH]
            decision_actual = strict_json(decision_raw)
            require(
                decision_raw == canonical_bytes(decision_actual)
                and decision_actual["contentBinding"]["sha256"]
                == EXPECTED_DECISION_CONTENT,
                "E_DECISION",
            )
            self.decision_document = decision_actual
            self.final_barrier(phase)
        except BaseException:
            self.close()
            raise

    def validate_v2_closure(self) -> None:
        require(
            self.v2_closure is not None and self.decision_package is not None,
            "E_V2_CLOSURE",
        )
        closure_raw = self.v2_closure.raw[DECISION.V2_PERMIT_PATH]
        closure = strict_json(closure_raw)
        expected_binding = {
            "permitContentSha256": DECISION.V2_EXPECTED_CONTENT,
            "status": "diagnostic_readback_authority_consumed_or_uncertain",
            "authorityConsumptionState": "consumed_or_uncertain",
            "files": [
                {
                    "path": path,
                    "rawSha256": DECISION.V2_EXPECTED_RAW[path],
                }
                for path in DECISION.V2_EXPECTED_RAW
            ],
        }
        require(
            closure_raw == canonical_bytes(closure)
            and closure["contentBinding"]["sha256"]
            == DECISION.V2_EXPECTED_CONTENT
            and closure["status"]
            == "diagnostic_readback_authority_consumed_or_uncertain"
            and closure["priorDraftDiagnosticObservation"][
                "authorityConsumptionState"
            ]
            == "consumed_or_uncertain"
            and closure["nextAction"]
            == "prepare_separate_v3_recovery_decision_and_one_use_permit"
            and self.decision_document["v2ClosureBinding"] == expected_binding,
            "E_V2_CLOSURE",
        )

    @property
    def namespace(self) -> Any:
        return self.authority.namespace

    def require_phase(self, phase: str) -> None:
        self.authority.final_barrier("recordable")
        require(classify_phase(self.namespace) == phase, "E_NAMESPACE")
        names = DECISION.V2.RECOVERY.held_dependency_names(self.namespace)
        require(
            not any(name.startswith(V3_STAGING_PREFIX) for name in names),
            "E_NAMESPACE",
        )
        self.authority.final_barrier("recordable")

    def final_barrier(self, phase: str | None = None) -> None:
        require(
            self.authority is not None
            and self.v2_closure is not None
            and self.decision_package is not None
            and self.package is not None,
            "E_CONTEXT",
        )
        self.require_phase(phase or self.phase)
        self.v2_closure.final_barrier()
        self.decision_package.final_barrier()
        self.package.final_barrier()
        self.validate_v2_closure()
        self.authority.final_barrier("recordable")

    def close(self) -> None:
        if self.package is not None:
            self.package.close()
        if self.decision_package is not None:
            self.decision_package.close()
        if self.v2_closure is not None:
            self.v2_closure.close()
        if self.authority is not None:
            self.authority.close()


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def expected_payload(context: PermitContext) -> dict[str, Any]:
    package = context.package.raw
    recorder_raw = package[RECORDER_PATH]
    source = recorder_raw.decode("utf-8", errors="strict")
    reverse_pin, _, _ = unique_module_string_assignment(source, REVERSE_PIN_NAME)
    require(
        package[PERMIT_READER_PATH] == READER_BYTES
        and normalized_recorder_sha256(recorder_raw)
        == EXPECTED_RECORDER_NORMALIZED_SHA256
        and sha256(package[RECORDER_TESTS_PATH])
        == EXPECTED_RECORDER_TESTS_RAW_SHA256
        and reverse_pin == sha256(package[THIS_CHECKER_PATH]),
        "E_TOOL_FREEZE",
    )
    decision = context.decision_document
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-recovery-execution-permit"
        ),
        "schemaVersion": "3.0",
        "permitId": PERMIT_ID,
        "recordedDate": "2026-07-24",
        "status": "replacement_recovery_readback_authorized_once_not_consumed",
        "result": "exact_one_use_replacement_recovery_readback_authorized",
        "decisionBinding": {
            "path": DECISION_PATH,
            "rawSha256": EXPECTED_DECISION_RAW,
            "contentSha256": EXPECTED_DECISION_CONTENT,
            "decisionId": decision["decisionId"],
        },
        "v2ClosureBinding": decision["v2ClosureBinding"],
        "originalEvidenceBinding": {
            "heldSourceInputCount": 69,
            "claimRawSha256": DECISION.V2.RECOVERY.EXPECTED_CLAIM_RAW_SHA256,
            "resultRawSha256": DECISION.V2.RECOVERY.EXPECTED_RESULT_RAW_SHA256,
            "resultContentSha256": (
                DECISION.V2.RECOVERY.EXPECTED_RESULT_CONTENT_SHA256
            ),
            "manifestRawSha256": DECISION.V2.RECOVERY.EXPECTED_MANIFEST_RAW_SHA256,
            "graphSha256": DECISION.V2.RECOVERY.EXPECTED_GRAPH_SHA256,
            "decisionHeldBindingSetSha256": (
                DECISION.V2.RECOVERY.EXPECTED_HELD_BINDING_SET_SHA256
            ),
            "candidateSourceProjectionSha256": (
                DECISION.V2.RECOVERY.EXPECTED_CANDIDATE_PROJECTION_SHA256
            ),
            "newTupleCount": 16,
            "fixedPointReached": False,
        },
        "toolBindings": {
            "reader": {
                "path": PERMIT_READER_PATH,
                "rawSha256": sha256(package[PERMIT_READER_PATH]),
            },
            "checker": {
                "path": THIS_CHECKER_PATH,
                "rawSha256": sha256(package[THIS_CHECKER_PATH]),
            },
            "tests": {
                "path": THIS_TESTS_PATH,
                "rawSha256": sha256(package[THIS_TESTS_PATH]),
            },
            "recorder": {
                "path": RECORDER_PATH,
                "normalizedSha256": EXPECTED_RECORDER_NORMALIZED_SHA256,
            },
            "recorderTests": {
                "path": RECORDER_TESTS_PATH,
                "rawSha256": EXPECTED_RECORDER_TESTS_RAW_SHA256,
            },
        },
        "oneUseContract": {
            "claimPath": V3_CLAIM_PATH,
            "receiptPath": V3_RECEIPT_PATH,
            "failurePath": V3_FAILURE_PATH,
            "manifestPath": V3_MANIFEST_PATH,
            "claimCreatedFsyncedAndReopenedBeforeFreshDecode": True,
            "receiptAttemptBeginsBeforeExclusiveWrite": True,
            "manifestWrittenLast": True,
            "automaticRetryAllowed": False,
            "resumeAllowed": False,
            "claimBackfillAllowed": False,
            "receiptBackfillAllowed": False,
            "manifestBackfillAllowed": False,
            "failureAfterReceiptAttemptAllowed": False,
        },
        "authority": {
            "oneOfflineReadbackAuthorized": True,
            "claimWriteAuthorized": True,
            "receiptOrFailureWriteAuthorized": True,
            "manifestOnSuccessWriteAuthorized": True,
            "originalEvaluationAuthorized": False,
            "networkAuthorized": False,
            "gitWriteAuthorized": False,
            "sourceExecutionAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "subprocessAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "nextAction": "run_formal_v3_recovery_readback_once",
    }


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    context = PermitContext(ROOT, include_permit=verify_disk, phase="recordable")
    try:
        expected = content_bound(expected_payload(context))
        if verify_disk:
            raw = context.package.raw[PERMIT_PATH]
            actual = strict_json(raw)
            require(raw == canonical_bytes(actual) and actual == expected, "E_PERMIT")
        context.final_barrier("recordable")
        return expected, {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "readback-recovery-permit-v3-check"
            ),
            "schemaVersion": "3.0",
            "status": "validated_authorized_once_not_consumed",
            "validationPassed": True,
            "recordable": True,
            "readbackRecordingAuthorized": True,
            "executionAuthorized": False,
            "freshRecomputationPerformed": False,
            "archiveMemberDecodeCount": 0,
            "fileWriteCount": 0,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "subprocessCount": 0,
            "gitWriteAuthorized": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise PermitError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        parser.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        if args.print_expected:
            expected, _ = evaluate(False)
            sys.stdout.buffer.write(canonical_bytes(expected))
        else:
            _, summary = evaluate(True)
            sys.stdout.buffer.write(canonical_bytes(summary))
        return 0
    except PermitError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": "aetherlink.v3-recovery-permit-error",
                    "schemaVersion": "3.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "readbackRecordingAuthorized": False,
                    "executionAuthorized": False,
                    "archiveMemberDecodeCount": 0,
                    "fileWriteCount": 0,
                    "networkUsed": False,
                    "sourceExecutionUsed": False,
                    "subprocessCount": 0,
                    "gitWriteAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": "aetherlink.v3-recovery-permit-error",
                    "schemaVersion": "3.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "readbackRecordingAuthorized": False,
                    "executionAuthorized": False,
                    "archiveMemberDecodeCount": 0,
                    "fileWriteCount": 0,
                    "networkUsed": False,
                    "sourceExecutionUsed": False,
                    "subprocessCount": 0,
                    "gitWriteAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
