#!/usr/bin/env python3
"""Validate the one-use combined fixed-point recovery readback permit v2."""

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
    raise RuntimeError("permit checker requires unoptimized `python3 -I -B -S`")

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
RECOVERY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v2.json"
)
RECOVERY_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v2.md"
)
RECOVERY_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v2.py"
)
RECOVERY_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v2.py"
)
EXPECTED_RECOVERY_RAW = (
    "37660f7b63ddf59b68116bcca708701b1a83bcf0fac2c6f764543f91b315fef8"
)
EXPECTED_RECOVERY_READER_RAW = (
    "978a9c2ba37b68d84475031aee4c5549485b9a54ebe2f4191b0e14308f088ca4"
)
EXPECTED_RECOVERY_CHECKER_RAW = (
    "437e46713715bec57e759ad0c7a6d267a807da06172b1b513e3f7a9f840c5b58"
)
EXPECTED_RECOVERY_TESTS_RAW = (
    "7c973705be07a56fb83f593845cc30cf7ceeb249de465681f9ee08be348b88e0"
)
EXPECTED_RECOVERY_CONTENT = (
    "87c6a90294cab6ee666cde5bda4a41b7bdfcb238b365e7ba3f75f1c03117b058"
)

PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-execution-permit-v2.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-execution-permit-v2.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v2.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v2.py"
)
RECORDER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "success_v1_recovery_v2.py"
)
RECORDER_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "success_v1_recovery_v2.py"
)
EXPECTED_RECORDER_NORMALIZED_SHA256 = (
    "3bf7ff445e9caee7f65c88ca3b78e67622fd8626866aaa09ab48d35ff9bf960e"
)
EXPECTED_RECORDER_TESTS_RAW_SHA256 = (
    "f61d771f39e6c55909a847fff347440c6984c114993c4e4131b5e4fcf86e5467"
)
REVERSE_PIN_NAME = "EXPECTED_PERMIT_CHECKER_RAW_SHA256"

DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
V2_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.combined-fixed-point-readback-v2.claim"
V2_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v2.json"
)
V2_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-failure-v2.json"
)
V2_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-manifest-v2.json"
)
V2_PATHS = (
    V2_CLAIM_PATH,
    V2_RECEIPT_PATH,
    V2_FAILURE_PATH,
    V2_MANIFEST_PATH,
)
V2_STAGING_PREFIX = ".combined-fixed-point-readback-v2-staging-"
PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-fixed-point-"
    "readback-recovery-execution-permit-v2"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024

READER_BYTES = b"""# Combined fixed-point recovery readback execution permit v2

This document closes the v2 recovery readback authority as consumed or
uncertain. A prior draft checker performed a fresh diagnostic recomputation
before creating the required claim. It observed 16 tuples and no fixed point,
but wrote no v2 output and is not accepted as evidence.

This v2 permit ID no longer authorizes recording, retry, claim creation,
receipt or failure publication, manifest publication, original evaluation,
deletion, modification, v1 backfill, network use, source execution,
extraction, subprocesses, Git, devices, deployment, authentication,
credentials, signatures, or user action. Any formal recovery readback now
requires a separate v3 recovery decision and one-use permit.
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
            parse_float=lambda _: (_ for _ in ()).throw(
                PermitError("E_JSON")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                PermitError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


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
        os.O_RDONLY
        | os.O_NOFOLLOW
        | os.O_NONBLOCK
        | os.O_CLOEXEC,
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
            ),
            "E_BOOTSTRAP",
        )
        require(
            sha256(raw) == expected,
            "E_BOOTSTRAP",
        )
        return raw
    finally:
        os.close(fd)


RECOVERY = execute_module(
    "combined_readback_recovery_decision_v2_frozen",
    RECOVERY_CHECKER_PATH,
    bootstrap_read(RECOVERY_CHECKER_PATH, EXPECTED_RECOVERY_CHECKER_RAW),
)


def unique_module_string_assignment(
    source: str,
    name: str,
) -> tuple[str, int, int]:
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
    ]
    require(len(assignments) == 1, "E_TOOL_FREEZE")
    assignment = assignments[0]
    require(
        isinstance(assignment.value, ast.Constant)
        and type(assignment.value.value) is str,
        "E_TOOL_FREEZE",
    )
    target = assignment.targets[0]
    bound_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, (ast.Store, ast.Del))
        and node.id == name
    ]
    require(
        len(bound_nodes) == 1 and bound_nodes[0] is target,
        "E_TOOL_FREEZE",
    )
    for node in ast.walk(tree):
        bound_names: list[str] = []
        if isinstance(node, ast.alias):
            bound_names.append(node.asname or node.name.split(".", 1)[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound_names.append(node.name)
        elif isinstance(node, ast.arg):
            bound_names.append(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound_names.append(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound_names.extend(node.names)
        elif hasattr(ast, "MatchAs") and isinstance(node, ast.MatchAs):
            if node.name:
                bound_names.append(node.name)
        elif hasattr(ast, "MatchStar") and isinstance(node, ast.MatchStar):
            if node.name:
                bound_names.append(node.name)
        elif hasattr(ast, "MatchMapping") and isinstance(
            node, ast.MatchMapping
        ):
            if node.rest:
                bound_names.append(node.rest)
        require(name not in bound_names, "E_TOOL_FREEZE")
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
    end = start + 64
    require(source.encode()[start:end] == value.encode(), "E_TOOL_FREEZE")
    return value, start, end


def normalized_recorder_sha256(raw: bytes) -> str:
    try:
        source = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PermitError("E_TOOL_FREEZE") from error
    _, start, end = unique_module_string_assignment(
        source,
        REVERSE_PIN_NAME,
    )
    return sha256(raw[:start] + b"0" * 64 + raw[end:])


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


def namespace_kind(namespace: Any, relative: str) -> str:
    parent_fd, name = RECOVERY.namespace_parent(namespace, relative)
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return "absent"
    except OSError as error:
        raise PermitError("E_NAMESPACE") from error
    return "regular" if stat.S_ISREG(info.st_mode) else "other"


def classify_phase(namespace: Any) -> str:
    kinds = tuple(namespace_kind(namespace, path) for path in V2_PATHS)
    for phase in (
        "recordable",
        "after_claim",
        "failure",
        "after_receipt",
        "complete",
    ):
        expected = tuple(
            "regular" if present else "absent"
            for present in phase_shape(phase)
        )
        if kinds == expected:
            return phase
    return "blocked"


def require_phase(context: Any, phase: str) -> None:
    context.namespace.final_barrier()
    context.terminal.final_barrier()
    require(
        classify_phase(context.namespace) == phase,
        "E_NAMESPACE",
    )
    require(
        RECOVERY.absent_from_held_namespace(
            context.namespace,
            RECOVERY.FAILURE_PATH,
        )
        and all(
            RECOVERY.absent_from_held_namespace(context.namespace, path)
            for path in RECOVERY.V1_READBACK_PATHS
        ),
        "E_NAMESPACE",
    )
    names = RECOVERY.held_dependency_names(context.namespace)
    require(
        not any(
            name.startswith(prefix)
            for name in names
            for prefix in (
                *RECOVERY.STAGING_PREFIXES,
                V2_STAGING_PREFIX,
            )
        ),
        "E_NAMESPACE",
    )
    context.terminal.final_barrier()
    context.namespace.final_barrier()


class ExecutionAuthorityContext:
    """Independent direct-payload authority with phase-aware namespace."""

    def __init__(
        self,
        root: Path,
        *,
        include_permit: bool,
        phase: str,
    ) -> None:
        self.root = root
        self.phase = phase
        self.namespace = None
        self.originals = None
        self.static = None
        self.runner_held = None
        self.controls = None
        self.sources = None
        self.terminal = None
        self.recovery = None
        self.package = None
        try:
            original_raw = bootstrap_read(
                RECOVERY.PERMIT_CHECKER_PATH,
                RECOVERY.EXPECTED_RAW[RECOVERY.PERMIT_CHECKER_PATH],
            )
            self.original_permit_checker = execute_module(
                "combined_recovery_v2_original_permit_checker",
                RECOVERY.PERMIT_CHECKER_PATH,
                original_raw,
            )
            self.decision_checker = (
                self.original_permit_checker.load_decision_checker(root)
            )
            self.namespace = self.decision_checker.HeldNamespace(root)
            self.originals = self.decision_checker.HeldSet(
                root,
                RECOVERY.original_binding_rows(),
            )
            self.static = self.decision_checker.HeldSet(
                root,
                self.original_permit_checker.static_bindings(
                    self.decision_checker,
                    include_permit=True,
                ),
            )
            self.candidate = self.decision_checker.load_candidate_checker(
                self.static
            )
            self.runner_held = self.candidate.PinnedRunnerFile(root)
            self.runner = self.candidate.load_pinned_runner(self.runner_held)
            self.controls = self.decision_checker.HeldSet(
                root,
                self.candidate.control_bindings(),
            )
            self.documents = self.candidate.parse_control_documents(
                self.runner,
                self.controls,
            )
            self.candidate.validate_terminal_documents(
                self.runner,
                self.documents,
            )
            self.source_rows = self.candidate.source_bindings(
                self.runner,
                self.documents,
            )
            self.sources = self.decision_checker.HeldSet(
                root,
                self.decision_checker.source_hold_bindings(self.source_rows),
            )
            decision_payload = self.decision_checker.expected_payload(
                self.candidate,
                self.runner,
                self.documents,
                self.source_rows,
            )
            self.decision = self.decision_checker.validate_decision_bytes(
                self.static.raw[RECOVERY.DECISION_PATH],
                self.decision_checker.content_bound(decision_payload),
            )
            self.decision_checker.validate_reader_bytes(
                self.static.raw[RECOVERY.DECISION_READER_PATH]
            )
            original_permit_payload = (
                self.original_permit_checker.expected_payload(self)
            )
            self.original_permit = (
                self.original_permit_checker.validate_permit_bytes(
                    self.static.raw[RECOVERY.PERMIT_PATH],
                    self.original_permit_checker.content_bound(
                        original_permit_payload
                    ),
                )
            )
            self.terminal = self.decision_checker.HeldSet(
                root,
                RECOVERY.terminal_binding_rows(),
            )
            self.recovery = self.decision_checker.HeldSet(
                root,
                [
                    {
                        "path": path,
                        "rawSha256": digest,
                        "maximumBytes": (
                            MAXIMUM_JSON_BYTES
                            if path.startswith("docs/")
                            else MAXIMUM_TOOL_BYTES
                        ),
                        "ownerOnly": False,
                    }
                    for path, digest in (
                        (RECOVERY_DECISION_PATH, EXPECTED_RECOVERY_RAW),
                        (RECOVERY_READER_PATH, EXPECTED_RECOVERY_READER_RAW),
                        (RECOVERY_CHECKER_PATH, EXPECTED_RECOVERY_CHECKER_RAW),
                        (RECOVERY_TESTS_PATH, EXPECTED_RECOVERY_TESTS_RAW),
                    )
                ],
            )
            recovery_document = strict_json(
                self.recovery.raw[RECOVERY_DECISION_PATH]
            )
            require(
                recovery_document["contentBinding"]["sha256"]
                == EXPECTED_RECOVERY_CONTENT
                and recovery_document["status"]
                == "recovery_selected_execution_not_authorized"
                and recovery_document["nextAction"]
                == (
                    "prepare_separate_v2_recovery_readback_checker_tests_"
                    "and_one_use_execution_permit"
                ),
                "E_RECOVERY",
            )
            self.package = self.decision_checker.HeldSet(
                root,
                package_bindings(include_permit),
            )
            require_phase(self, phase)
            self.final_barrier(phase)
        except BaseException:
            self.close()
            raise

    def final_barrier(self, phase: str | None = None) -> None:
        for held in (
            self.originals,
            self.static,
            self.runner_held,
            self.controls,
            self.sources,
            self.terminal,
            self.recovery,
            self.package,
        ):
            require(held is not None, "E_CONTEXT")
            held.final_barrier()
        require_phase(self, phase or self.phase)

    def close(self) -> None:
        for held in (
            self.package,
            self.recovery,
            self.terminal,
            self.sources,
            self.controls,
            self.runner_held,
            self.static,
            self.originals,
            self.namespace,
        ):
            if held is not None:
                held.close()


def expected_permit(context: ExecutionAuthorityContext) -> dict[str, Any]:
    package = context.package.raw
    recorder_raw = package[RECORDER_PATH]
    try:
        recorder_source = recorder_raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PermitError("E_TOOL_FREEZE") from error
    reverse_pin, _, _ = unique_module_string_assignment(
        recorder_source,
        REVERSE_PIN_NAME,
    )
    require(
        package[PERMIT_READER_PATH] == READER_BYTES
        and normalized_recorder_sha256(recorder_raw)
        == EXPECTED_RECORDER_NORMALIZED_SHA256
        and sha256(package[RECORDER_TESTS_PATH])
        == EXPECTED_RECORDER_TESTS_RAW_SHA256
        and reverse_pin == sha256(package[THIS_CHECKER_PATH]),
        "E_TOOL_FREEZE",
    )
    payload = {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-recovery-execution-permit"
        ),
        "schemaVersion": "2.0",
        "permitId": PERMIT_ID,
        "recordedDate": "2026-07-24",
        "status": "diagnostic_readback_authority_consumed_or_uncertain",
        "result": "v2_recovery_readback_recording_closed",
        "recoveryDecisionBinding": {
            "path": RECOVERY_DECISION_PATH,
            "rawSha256": EXPECTED_RECOVERY_RAW,
            "contentSha256": EXPECTED_RECOVERY_CONTENT,
        },
        "toolBindings": {
            "permitReader": {
                "path": PERMIT_READER_PATH,
                "rawSha256": sha256(package[PERMIT_READER_PATH]),
            },
            "permitChecker": {
                "path": THIS_CHECKER_PATH,
                "rawSha256": sha256(package[THIS_CHECKER_PATH]),
            },
            "permitTests": {
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
        "sourceAndTerminalBinding": {
            "heldSourceInputCount": 69,
            "decisionHeldBindingSetSha256": (
                RECOVERY.EXPECTED_HELD_BINDING_SET_SHA256
            ),
            "candidateSourceProjectionSha256": (
                RECOVERY.EXPECTED_CANDIDATE_PROJECTION_SHA256
            ),
            "claimRawSha256": RECOVERY.EXPECTED_CLAIM_RAW_SHA256,
            "resultRawSha256": RECOVERY.EXPECTED_RESULT_RAW_SHA256,
            "resultContentSha256": RECOVERY.EXPECTED_RESULT_CONTENT_SHA256,
            "manifestRawSha256": RECOVERY.EXPECTED_MANIFEST_RAW_SHA256,
            "graphSha256": RECOVERY.EXPECTED_GRAPH_SHA256,
            "newTupleCount": 16,
            "fixedPointReached": False,
        },
        "oneUseContract": {
            "claimPath": V2_CLAIM_PATH,
            "receiptPath": V2_RECEIPT_PATH,
            "failurePath": V2_FAILURE_PATH,
            "manifestPath": V2_MANIFEST_PATH,
            "formalRecordAttemptAuthorized": False,
            "receiptOrFailureMutuallyExclusive": True,
            "manifestWrittenLast": True,
            "automaticRetryAllowed": False,
            "secondInvocationResumeAllowed": False,
            "claimOnlyBackfillAllowed": False,
            "receiptOnlyBackfillAllowed": False,
            "failureAfterReceiptAttemptAllowed": False,
        },
        "priorDraftDiagnosticObservation": {
            "priorPermitRawSha256": (
                "bf14e46c6c43a1e247d702aba742adecd4e1a10b05dc688cd57e5f04e8fdbbda"
            ),
            "priorPermitContentSha256": (
                "6b64282e170973fb86000e56d7a189e9a9b5a26b7fea71bfbb0ee16f00304296"
            ),
            "priorPermitCheckerRawSha256": (
                "c5c3bc2065b4d31a127a138dd30eb458e1a000c57dc6f53d9404636c988983bf"
            ),
            "priorRecorderRawSha256": (
                "bfa2fb3a887a95f7d1c3e8e56287f01b27666f28a34d8a663a5a2e81b462b7fc"
            ),
            "priorRecorderTestsRawSha256": (
                "0d6881a7e1281bffbc91c835f14e97ce257caa96831456eb9b05dcc3615b4cc6"
            ),
            "observedStatus": "recordable_fresh_validation_passed",
            "graphSha256": RECOVERY.EXPECTED_GRAPH_SHA256,
            "newTupleCount": 16,
            "fixedPointReached": False,
            "freshRecomputationOccurred": True,
            "freshRecomputationOccurredBeforeClaim": True,
            "acceptedAsEvidence": False,
            "claimCreated": False,
            "receiptCreated": False,
            "failureCreated": False,
            "manifestCreated": False,
            "fileWriteCount": 0,
            "authorityConsumptionState": "consumed_or_uncertain",
        },
        "authority": {
            "oneOfflineReadbackAuthorized": False,
            "claimWriteAuthorized": False,
            "receiptOrFailureWriteAuthorized": False,
            "manifestOnSuccessWriteAuthorized": False,
            "originalEvaluationAuthorized": False,
            "originalRetryAuthorized": False,
            "originalModifyDeleteAuthorized": False,
            "v1BackfillAuthorized": False,
            "networkAuthorized": False,
            "sourceExecutionAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "subprocessAuthorized": False,
            "gitWriteAuthorized": False,
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
        "nextAction": "prepare_separate_v3_recovery_decision_and_one_use_permit",
    }
    payload["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "permit_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return payload


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    context = ExecutionAuthorityContext(
        ROOT,
        include_permit=verify_disk,
        phase="recordable",
    )
    try:
        expected = expected_permit(context)
        if verify_disk:
            raw = context.package.raw[PERMIT_PATH]
            actual = strict_json(raw)
            require(
                raw == canonical_bytes(actual)
                and actual == expected,
                "E_PERMIT",
            )
        context.final_barrier("recordable")
        return expected, {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "readback-recovery-permit-check"
            ),
            "schemaVersion": "2.0",
            "status": "validated_diagnostic_authority_consumed_or_uncertain",
            "validationPassed": True,
            "recordable": False,
            "namespaceRecordableShape": True,
            "freshRecomputationPerformed": False,
            "archiveMemberDecodeCount": 0,
            "heldSourceInputCount": 69,
            "executionAuthorized": False,
            "readbackRecordingAuthorized": False,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessCount": 0,
            "fileWriteCount": 0,
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
        expected, summary = evaluate(not args.print_expected)
        sys.stdout.buffer.write(
            canonical_bytes(expected if args.print_expected else summary)
        )
        return 0
    except PermitError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.g2-pion-combined-fixed-point-"
                        "readback-recovery-permit-error"
                    ),
                    "schemaVersion": "2.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "validationPassed": False,
                    "executionAuthorized": False,
                    "readbackRecordingAuthorized": False,
                    "networkUsed": False,
                    "fileWriteCount": 0,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        return main_error()


def main_error() -> int:
    sys.stdout.buffer.write(
        canonical_bytes(
            {
                "documentType": (
                    "aetherlink.g2-pion-combined-fixed-point-"
                    "readback-recovery-permit-error"
                ),
                "schemaVersion": "2.0",
                "status": "failed_closed",
                "failureCode": "E_INTERNAL",
                "validationPassed": False,
                "executionAuthorized": False,
                "readbackRecordingAuthorized": False,
                "networkUsed": False,
                "fileWriteCount": 0,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            }
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
