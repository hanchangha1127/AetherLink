#!/usr/bin/env python3
"""Validate the exact one-use combined fixed-point execution permit.

This checker is read-only and must run under ``python3 -I -B -S``.  It loads
the exact decision checker, holds the decision/candidate/tool/evidence/source
closure, derives the expected permit from current pinned executor bytes, and
requires canonical on-disk equality.  It never evaluates source or writes.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "combined fixed-point permit checker requires "
            "unoptimized `python3 -I -B -S`"
        )


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
    f"{BASE}/bounded-dependency-source-combined-fixed-point-decision-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-decision-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_decision_v1.py"
)
# Updated only after the independent decision audit freezes all four bytes.
EXPECTED_DECISION_RAW_SHA256 = (
    "b3d89d1b4071c76d1639a05a8bc1112925af65feaf68d71f25f9c1a4b0d8f208"
)
EXPECTED_DECISION_READER_RAW_SHA256 = (
    "15119ba0f57c63cf14211d3ece97d29c6b500555aae003a7ccf619c9f8922da4"
)
EXPECTED_DECISION_CHECKER_RAW_SHA256 = (
    "186de17e8106228438037be576d367256d8da16af0476f4df9139b8f075e7469"
)
EXPECTED_DECISION_TESTS_RAW_SHA256 = (
    "f557b8a9e248ebe27793a9d80e91dc8930d83a1938c827f2b1bdd72a25044ccb"
)

PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_execution_permit_v1.py"
)
RUNNER_PATH = "script/run_p2p_nat_g2_pion_combined_fixed_point_v1_once.py"
RUNNER_TESTS_PATH = (
    "script/test_run_p2p_nat_g2_pion_combined_fixed_point_v1_once.py"
)
READBACK_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_success_v1.py"
)
READBACK_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_success_v1.py"
)
EXPECTED_RUNNER_NORMALIZED_SHA256 = (
    "846e5edaea0aeaf60a43145040c4fe5a955ee91c737c490f22837f80a3ae2e24"
)
EXPECTED_RUNNER_TESTS_RAW_SHA256 = (
    "36f47f660323cced2664c7478e3f351024f6908c337b6524e6613f33f985ebf5"
)
EXPECTED_READBACK_NORMALIZED_SHA256 = (
    "b44853ac0000af6af54009b182324580b5a1eaad006ae83e8982c7a9e0e50bc1"
)
EXPECTED_READBACK_TESTS_RAW_SHA256 = (
    "1e5a6a3243e618b3be30dac632f77fc7375fae625d1931681149e7342ed5e782"
)
REVERSE_PIN_NAME = "EXPECTED_PERMIT_CHECKER_RAW_SHA256"
NORMALIZED_REVERSE_PIN = "0" * 64

PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-fixed-point-execution-permit-v1"
)
EXPECTED_STATUS = (
    "combined_fixed_point_evaluation_authorized_once_not_consumed"
)
EXPECTED_NEXT_ACTION = "execute_bound_combined_fixed_point_evaluation_once"
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024

DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
CLAIM_PATH = f"{DEPENDENCY_ROOT}/.combined-fixed-point-v1.claim"
RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-result-v1.json"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-manifest-v1.json"
)
READBACK_CLAIM_PATH = (
    f"{DEPENDENCY_ROOT}/.combined-fixed-point-readback-v1.claim"
)
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v1.json"
)
READBACK_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-failure-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-manifest-v1.json"
)
STAGING_PREFIX = ".combined-fixed-point-v1-staging-"
PUBLICATION_PATHS = (
    CLAIM_PATH,
    RESULT_PATH,
    FAILURE_PATH,
    MANIFEST_PATH,
    READBACK_CLAIM_PATH,
    READBACK_RECEIPT_PATH,
    READBACK_FAILURE_PATH,
    READBACK_MANIFEST_PATH,
)

PERMIT_READER_BYTES = b"""# Combined fixed-point one-use execution permit v1

This companion describes the canonical execution permit. The permit authorizes
one offline evaluation of the exact 69 retained inputs. It authorizes no
network, subprocess, dependency source execution, filesystem extraction, Git,
device, deployment, authentication, signature, key, token, password, or user
action.

The execution claim must be created and fsynced before any archive member is
opened or decoded. It binds the decision-held 69-input digest; the result binds
the distinct candidate-source projection digest. A valid evaluation publishes
exactly one canonical, content-bound result or one canonical, content-bound
pre-result failure; the result manifest is written last. A result publication
attempt makes later uncertainty consumed and forbids a failure backfill or
retry. Every failure publication is reopened owner-only, validated against
its claim and authority bindings, and retained through final input, namespace,
and staging barriers.

Independent readback uses a separate one-use claim, reopens all 69 inputs,
recomputes the complete graph, compares the exact result projection, and writes
either a canonical readback receipt or a canonical, content-bound pre-receipt
failure. The readback manifest is last. Executor semantics are independently
frozen by normalized source hashes that erase only the reverse permit-checker
pin literal, while both test files remain exact-raw pinned. The normalized pin
parser permits exactly one module-level simple assignment with an exact
double-quoted lowercase 64-hex literal and rejects every other rebinding. This
permit does not claim that fixed point is reached; the currently frozen route
retains 16 frontier tuples.
"""


class PermitError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise PermitError("E_ARGUMENTS")


def require(condition: bool, code: str) -> None:
    if not condition:
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
        ).encode("utf-8")
        + b"\n"
    )


def bootstrap_read(
    root: Path,
    relative: str,
    expected_sha256: str,
) -> bytes:
    current = root
    for component in relative.split("/")[:-1]:
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
        root / relative,
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
            )
            and sha256(raw) == expected_sha256,
            "E_BOOTSTRAP",
        )
        return raw
    finally:
        os.close(fd)


def execute_module(
    name: str,
    relative: str,
    raw: bytes,
    root: Path,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(root / relative),
            "__loader__": None,
            "__name__": name,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(
                raw,
                relative,
                "exec",
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise PermitError("E_TOOL_LOAD") from error
    return module


def load_decision_checker(root: Path) -> types.ModuleType:
    raw = bootstrap_read(
        root,
        DECISION_CHECKER_PATH,
        EXPECTED_DECISION_CHECKER_RAW_SHA256,
    )
    module = execute_module(
        "aetherlink_combined_fixed_point_decision_v1",
        DECISION_CHECKER_PATH,
        raw,
        root,
    )
    for name in (
        "HeldSet",
        "HeldNamespace",
        "load_candidate_checker",
        "source_hold_bindings",
        "expected_decision",
        "validate_decision_bytes",
        "validate_reader_bytes",
        "validate_namespace_absent",
    ):
        require(callable(getattr(module, name, None)), "E_TOOL_API")
    return module


def static_tool_paths() -> tuple[str, ...]:
    return (
        DECISION_PATH,
        DECISION_READER_PATH,
        DECISION_CHECKER_PATH,
        DECISION_TESTS_PATH,
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py",
        "script/test_p2p_nat_g2_pion_combined_fixed_point_v1.py",
        "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py",
        THIS_CHECKER_PATH,
        THIS_TESTS_PATH,
        RUNNER_PATH,
        RUNNER_TESTS_PATH,
        READBACK_CHECKER_PATH,
        READBACK_TESTS_PATH,
        PERMIT_READER_PATH,
    )


def static_bindings(
    decision_checker: types.ModuleType,
    *,
    include_permit: bool,
) -> list[dict[str, Any]]:
    exact = {
        DECISION_PATH: EXPECTED_DECISION_RAW_SHA256,
        DECISION_READER_PATH: EXPECTED_DECISION_READER_RAW_SHA256,
        DECISION_CHECKER_PATH: EXPECTED_DECISION_CHECKER_RAW_SHA256,
        DECISION_TESTS_PATH: EXPECTED_DECISION_TESTS_RAW_SHA256,
        decision_checker.CANDIDATE_CHECKER_PATH: (
            decision_checker.CANDIDATE_CHECKER_SHA256
        ),
        decision_checker.CANDIDATE_TESTS_PATH: (
            decision_checker.CANDIDATE_TESTS_SHA256
        ),
        decision_checker.WAVE1_RUNNER_PATH: (
            decision_checker.WAVE1_RUNNER_SHA256
        ),
    }
    paths = list(static_tool_paths())
    if include_permit:
        paths.append(PERMIT_PATH)
    return [
        {
            "path": path,
            "rawSha256": exact.get(path),
            "maximumBytes": MAXIMUM_JSON_BYTES
            if path.startswith("docs/")
            else MAXIMUM_TOOL_BYTES,
            "ownerOnly": False,
        }
        for path in paths
    ]


class AuthorityContext:
    def __init__(
        self,
        root: Path,
        *,
        include_permit: bool,
        require_clean_namespace: bool,
    ) -> None:
        self.root = root
        self.decision_checker = load_decision_checker(root)
        self.namespace = None
        self.static = None
        self.runner_held = None
        self.controls = None
        self.sources = None
        try:
            require(
                self.decision_checker.DEPENDENCY_ROOT == DEPENDENCY_ROOT
                and self.decision_checker.BASE == BASE,
                "E_NAMESPACE",
            )
            self.namespace = self.decision_checker.HeldNamespace(root)
            self.static = self.decision_checker.HeldSet(
                root,
                static_bindings(
                    self.decision_checker,
                    include_permit=include_permit,
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
                self.decision_checker.source_hold_bindings(
                    self.source_rows
                ),
            )
            expected_decision = self.decision_checker.expected_decision(root)
            self.decision = self.decision_checker.validate_decision_bytes(
                self.static.raw[DECISION_PATH],
                expected_decision,
            )
            self.decision_checker.validate_reader_bytes(
                self.static.raw[DECISION_READER_PATH]
            )
            require(
                self.decision["status"].endswith(
                    "execution_not_authorized"
                )
                and self.decision["nextAction"]
                == (
                    "prepare_separate_combined_fixed_point_runner_checker_"
                    "tests_and_one_use_execution_permit"
                ),
                "E_DECISION",
            )
            if require_clean_namespace:
                validate_namespace_absent(root)
            self.final_barrier()
            if require_clean_namespace:
                validate_namespace_absent(root)
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        require(
            self.namespace is not None
            and self.static is not None
            and self.runner_held is not None
            and self.controls is not None
            and self.sources is not None,
            "E_CONTEXT",
        )
        self.namespace_barrier()
        self.static.final_barrier()
        self.runner_held.final_barrier()
        self.controls.final_barrier()
        self.sources.final_barrier()
        self.namespace_barrier()

    def namespace_barrier(self) -> None:
        require(self.namespace is not None, "E_CONTEXT")
        self.namespace.final_barrier()
        dependency = [
            parent
            for parent in self.namespace.parents
            if parent.relative == DEPENDENCY_ROOT
        ]
        require(len(dependency) == 1, "E_NAMESPACE")
        try:
            names = os.listdir(dependency[0].fd)
        except OSError as error:
            raise PermitError("E_NAMESPACE") from error
        require(
            not any(name.startswith(STAGING_PREFIX) for name in names),
            "E_NAMESPACE",
        )

    def close(self) -> None:
        for value in (
            self.sources,
            self.controls,
            self.runner_held,
            self.static,
            self.namespace,
        ):
            if value is not None:
                value.close()
        self.sources = None
        self.controls = None
        self.runner_held = None
        self.static = None
        self.namespace = None

    def __enter__(self) -> "AuthorityContext":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def open_authority_context(
    root: Path = ROOT,
    *,
    include_permit: bool = True,
    require_clean_namespace: bool = True,
) -> AuthorityContext:
    return AuthorityContext(
        root,
        include_permit=include_permit,
        require_clean_namespace=require_clean_namespace,
    )


def validate_namespace_absent(root: Path) -> None:
    for relative in PUBLICATION_PATHS:
        try:
            os.lstat(root / relative)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise PermitError("E_NAMESPACE") from error
        raise PermitError("E_NAMESPACE")
    dependency = root / DEPENDENCY_ROOT
    try:
        names = os.listdir(dependency)
    except OSError as error:
        raise PermitError("E_NAMESPACE") from error
    require(
        not any(name.startswith(STAGING_PREFIX) for name in names),
        "E_NAMESPACE",
    )


def file_sha(context: AuthorityContext, path: str) -> str:
    return sha256(context.static.raw[path])


def unique_module_string_assignment(
    source: str,
    name: str,
    *,
    error_code: str,
) -> tuple[str, int, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise PermitError(error_code) from error
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
    require(len(assignments) == 1, error_code)
    assignment = assignments[0]
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
        error_code,
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
        require(name not in bound_names, error_code)
    value = assignment.value.value
    require(
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        error_code,
    )
    segment = ast.get_source_segment(source, assignment.value)
    require(segment == f'"{value}"', error_code)
    raw_lines = source.encode("utf-8").splitlines(keepends=True)
    start = (
        sum(len(line) for line in raw_lines[: assignment.value.lineno - 1])
        + assignment.value.col_offset
    )
    end = (
        sum(
            len(line)
            for line in raw_lines[: assignment.value.end_lineno - 1]
        )
        + assignment.value.end_col_offset
    )
    require(
        source.encode("utf-8")[start:end] == segment.encode("ascii")
        and end - start == 66,
        error_code,
    )
    return value, start + 1, end - 1


def normalized_executor_bytes(raw: bytes) -> bytes:
    try:
        source = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PermitError("E_TOOL_FREEZE") from error
    _, payload_start, payload_end = unique_module_string_assignment(
        source,
        REVERSE_PIN_NAME,
        error_code="E_TOOL_FREEZE",
    )
    require(payload_end - payload_start == 64, "E_TOOL_FREEZE")
    return (
        raw[:payload_start]
        + NORMALIZED_REVERSE_PIN.encode("ascii")
        + raw[payload_end:]
    )


def normalized_executor_sha256(raw: bytes) -> str:
    return sha256(normalized_executor_bytes(raw))


def validate_tool_freeze(context: AuthorityContext) -> None:
    require(
        normalized_executor_sha256(context.static.raw[RUNNER_PATH])
        == EXPECTED_RUNNER_NORMALIZED_SHA256
        and file_sha(context, RUNNER_TESTS_PATH)
        == EXPECTED_RUNNER_TESTS_RAW_SHA256
        and normalized_executor_sha256(
            context.static.raw[READBACK_CHECKER_PATH]
        )
        == EXPECTED_READBACK_NORMALIZED_SHA256
        and file_sha(context, READBACK_TESTS_PATH)
        == EXPECTED_READBACK_TESTS_RAW_SHA256,
        "E_TOOL_FREEZE",
    )


def tool_bindings(context: AuthorityContext) -> list[dict[str, str]]:
    roles = (
        ("permit_checker", THIS_CHECKER_PATH),
        ("permit_checker_tests", THIS_TESTS_PATH),
        ("evaluation_runner", RUNNER_PATH),
        ("evaluation_runner_tests", RUNNER_TESTS_PATH),
        ("readback_checker", READBACK_CHECKER_PATH),
        ("readback_checker_tests", READBACK_TESTS_PATH),
    )
    return [
        {
            "role": role,
            "path": path,
            "rawSha256": file_sha(context, path),
        }
        for role, path in roles
    ]


def expected_payload(context: AuthorityContext) -> dict[str, Any]:
    decision = context.decision
    validate_tool_freeze(context)
    paths = {
        "claimPath": CLAIM_PATH,
        "resultPath": RESULT_PATH,
        "failurePath": FAILURE_PATH,
        "manifestPath": MANIFEST_PATH,
        "readbackClaimPath": READBACK_CLAIM_PATH,
        "readbackReceiptPath": READBACK_RECEIPT_PATH,
        "readbackFailurePath": READBACK_FAILURE_PATH,
        "readbackManifestPath": READBACK_MANIFEST_PATH,
        "stagingDirectoryPrefix": STAGING_PREFIX,
    }
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": PERMIT_ID,
        "recordedDate": "2026-07-24",
        "status": EXPECTED_STATUS,
        "result": (
            "exact_69_input_combined_graph_evaluation_authorized_once_"
            "not_executed"
        ),
        "scope": (
            "single_offline_combined_wave1_wave2_fixed_point_"
            "evaluation_and_independent_readback_only"
        ),
        "nextAction": EXPECTED_NEXT_ACTION,
        "decisionBinding": {
            "path": DECISION_PATH,
            "decisionId": decision["decisionId"],
            "rawSha256": EXPECTED_DECISION_RAW_SHA256,
            "contentSha256": decision["contentBinding"]["sha256"],
            "requiredStatus": decision["status"],
            "requiredNextAction": decision["nextAction"],
        },
        "readerBinding": {
            "path": PERMIT_READER_PATH,
            "rawSha256": file_sha(context, PERMIT_READER_PATH),
        },
        "toolBindings": tool_bindings(context),
        "toolFreeze": {
            "normalization": (
                "replace_only_EXPECTED_PERMIT_CHECKER_RAW_SHA256_"
                "literal_with_64_lowercase_zeroes_then_sha256_raw_utf8"
            ),
            "evaluationRunner": {
                "path": RUNNER_PATH,
                "normalizedSha256": EXPECTED_RUNNER_NORMALIZED_SHA256,
                "testsPath": RUNNER_TESTS_PATH,
                "testsRawSha256": EXPECTED_RUNNER_TESTS_RAW_SHA256,
            },
            "readbackChecker": {
                "path": READBACK_CHECKER_PATH,
                "normalizedSha256": EXPECTED_READBACK_NORMALIZED_SHA256,
                "testsPath": READBACK_TESTS_PATH,
                "testsRawSha256": EXPECTED_READBACK_TESTS_RAW_SHA256,
            },
        },
        "immutableGraphProviderBinding": {
            "path": context.candidate.RUNNER_PATH,
            "rawSha256": context.candidate.RUNNER_SHA256,
        },
        "candidateProviderBinding": {
            "path": context.decision_checker.CANDIDATE_CHECKER_PATH,
            "rawSha256": context.decision_checker.CANDIDATE_CHECKER_SHA256,
            "testsPath": context.decision_checker.CANDIDATE_TESTS_PATH,
            "testsRawSha256": (
                context.decision_checker.CANDIDATE_TESTS_SHA256
            ),
            "candidateOutputIsAuthority": False,
        },
        "terminalEvidenceBinding": {
            "count": len(context.candidate.CONTROL_SHA256),
            "bindings": [
                {"path": path, "rawSha256": digest}
                for path, digest in context.candidate.CONTROL_SHA256.items()
            ],
        },
        "sourceInputSet": {
            "heldInputCount": 69,
            "decisionHeldBindingSetSha256": decision["sourceInputSet"][
                "decisionHeldBindingSetSha256"
            ],
            "candidateSourceProjectionSha256": decision["sourceInputSet"][
                "candidateSourceProjectionSha256"
            ],
            "projectionContract": decision["sourceInputSet"][
                "projectionContract"
            ],
            "bindings": decision["sourceInputSet"]["bindings"],
            "outerHoldRequiredThroughFinalManifestBarrier": True,
        },
        "profiles": decision["profiles"],
        "resourceLimits": decision["resourceLimits"],
        "fixedPointAcceptance": decision["fixedPointAcceptance"],
        "frozenDecisionOneUseContract": decision["futureOneUseContract"],
        "currentExpectedRoute": {
            "route": "next_wave_required",
            "newTupleCount": 16,
            "fixedPointReached": False,
            "evaluationStillRequired": True,
        },
        "oneUseContract": {
            **paths,
            "initialState": "authorized_not_consumed",
            "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode": True,
            "preClaimFailureConsumesPermit": False,
            "claimCreationUncertaintyConsumesPermit": True,
            "claimPersistsAfterAnyEvaluationAttempt": True,
            "resultOrFailureMutuallyExclusive": True,
            "manifestWrittenLast": True,
            "secondExecutionAllowed": False,
            "automaticRetryAllowed": False,
            "postClaimFailureConsumesPermit": True,
            "postClaimUncertaintyConsumesPermit": True,
            "postResultPublicationAttemptUncertainAndConsumed": True,
            "postPublishUncertainState": "consumed_terminal_state_uncertain",
            "failureBackfillAfterResultAttemptAllowed": False,
            "separateReadbackClaimRequired": True,
            "readbackPreClaimFailureConsumesPermit": False,
            "readbackClaimCreationUncertaintyConsumesPermit": True,
            "readbackReceiptOrFailureMutuallyExclusive": True,
            "readbackManifestWrittenLast": True,
            "readbackSecondExecutionAllowed": False,
            "readbackAutomaticRetryAllowed": False,
            "readbackPostClaimFailureConsumesPermit": True,
            "readbackPostClaimUncertaintyConsumesPermit": True,
            "postReceiptPublicationAttemptUncertainAndConsumed": True,
            "readbackPostPublishUncertainState": (
                "consumed_terminal_state_uncertain"
            ),
            "readbackFailureBackfillAfterReceiptAttemptAllowed": False,
        },
        "authority": {
            "permitRecorded": True,
            "singleOfflineEvaluationAuthorized": True,
            "oneUseClaimWriteAuthorized": True,
            "resultOrFailureWriteAuthorized": True,
            "manifestWriteAuthorized": True,
            "independentReadbackAuthorized": True,
            "readbackClaimWriteAuthorized": True,
            "readbackReceiptOrFailureWriteAuthorized": True,
            "readbackManifestWriteAuthorized": True,
            "networkAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "sourceExecutionAuthorized": False,
            "packageManagerAuthorized": False,
            "compilerAuthorized": False,
            "subprocessAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "closure": {
            "dependencyFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "releaseReady": False,
        },
    }


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def expected_permit(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with open_authority_context(
        root,
        include_permit=False,
        require_clean_namespace=True,
    ) as context:
        expected = content_bound(expected_payload(context))
        context.final_barrier()
        validate_namespace_absent(root)
        return expected


def validate_permit_bytes(
    raw: bytes,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        actual = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=lambda pairs: _strict_object(pairs),
            parse_float=lambda _: _json_failure(),
            parse_constant=lambda _: _json_failure(),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError("E_JSON") from error
    require(type(actual) is dict, "E_JSON")
    require(raw == canonical_bytes(actual), "E_CANONICAL_PERMIT")
    require(actual == expected, "E_PERMIT")
    binding = actual.get("contentBinding")
    without = dict(actual)
    without.pop("contentBinding", None)
    require(
        type(binding) is dict
        and set(binding)
        == {
            "algorithm",
            "canonicalization",
            "scope",
            "sha256",
        }
        and binding["algorithm"] == "sha256"
        and binding["scope"] == "permit_without_contentBinding"
        and binding["sha256"] == sha256(canonical_bytes(without)),
        "E_CONTENT_BINDING",
    )
    return actual


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "E_JSON")
        result[key] = value
    return result


def _json_failure() -> Any:
    raise PermitError("E_JSON")


def assigned_string(source: str, name: str) -> str | None:
    try:
        value, _, _ = unique_module_string_assignment(
            source,
            name,
            error_code="E_REVERSE_PIN",
        )
    except PermitError as error:
        raise PermitError("E_REVERSE_PIN") from error
    return value


def validate_reverse_pins(context: AuthorityContext) -> None:
    checker_sha = file_sha(context, THIS_CHECKER_PATH)
    for path in (RUNNER_PATH, READBACK_CHECKER_PATH):
        try:
            source = context.static.raw[path].decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise PermitError("E_REVERSE_PIN") from error
        require(
            assigned_string(
                source,
                "EXPECTED_PERMIT_CHECKER_RAW_SHA256",
            )
            == checker_sha,
            "E_REVERSE_PIN",
        )


def validate_repository(
    root: Path = ROOT,
    *,
    require_clean_namespace: bool = True,
) -> dict[str, Any]:
    require_isolated_interpreter()
    with open_authority_context(
        root,
        include_permit=True,
        require_clean_namespace=require_clean_namespace,
    ) as context:
        expected = content_bound(expected_payload(context))
        permit = validate_permit_bytes(
            context.static.raw[PERMIT_PATH],
            expected,
        )
        validate_reverse_pins(context)
        if require_clean_namespace:
            validate_namespace_absent(root)
        context.final_barrier()
        if require_clean_namespace:
            validate_namespace_absent(root)
        return {
            "permit": permit,
            "decision": context.decision,
            "executionAuthorized": True,
            "namespacePreflightChecked": require_clean_namespace,
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


def parse_arguments(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-expected",
        action="store_true",
        help="print canonical expected permit without writing",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        require_isolated_interpreter()
        args = parse_arguments(argv)
        if args.print_expected:
            output = expected_permit(ROOT)
        else:
            checked = validate_repository(ROOT)
            output = {
                key: checked[key]
                for key in (
                    "executionAuthorized",
                    "namespacePreflightChecked",
                    "heldSourceInputCount",
                    "networkUsed",
                    "sourceExecutionUsed",
                    "filesystemExtractionUsed",
                    "subprocessCount",
                    "fileWriteCount",
                    "repositoryOwnerIdentityProofRequired",
                    "externalAuthenticationRequired",
                    "signatureRequired",
                    "privateKeyRequired",
                    "tokenRequired",
                    "passwordRequired",
                    "userActionRequired",
                )
            }
    except Exception:
        output = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "permit-check-error"
            ),
            "schemaVersion": "1.0",
            "status": "failed_closed",
            "networkOperationCount": 0,
            "sourceExecutionCount": 0,
            "fileWriteCount": 0,
        }
        sys.stdout.buffer.write(canonical_bytes(output))
        return 1
    sys.stdout.buffer.write(canonical_bytes(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
