#!/usr/bin/env python3
"""Validate the read-only combined fixed-point readback recovery decision v2."""

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
            "combined recovery decision checker requires "
            "unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
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
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "execution-permit-v1.md"
)
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "execution_permit_v1.py"
)
PERMIT_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "execution_permit_v1.py"
)
RUNNER_PATH = "script/run_p2p_nat_g2_pion_combined_fixed_point_v1_once.py"
RUNNER_TESTS_PATH = (
    "script/test_run_p2p_nat_g2_pion_combined_fixed_point_v1_once.py"
)
READBACK_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_success_v1.py"
)
READBACK_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_success_v1.py"
)
CANDIDATE_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
)
CANDIDATE_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_v1.py"
)
GRAPH_RUNNER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)

RECOVERY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v2.json"
)
RECOVERY_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v2.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v2.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v2.py"
)

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
V1_READBACK_PATHS = (
    f"{DEPENDENCY_ROOT}/.combined-fixed-point-readback-v1.claim",
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v1.json",
    (
        f"{BASE}/bounded-dependency-source-combined-fixed-point-"
        "readback-failure-v1.json"
    ),
    (
        f"{BASE}/bounded-dependency-source-combined-fixed-point-"
        "readback-manifest-v1.json"
    ),
)
V2_RECOVERY_PATHS = (
    f"{DEPENDENCY_ROOT}/.combined-fixed-point-readback-v2.claim",
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v2.json",
    (
        f"{BASE}/bounded-dependency-source-combined-fixed-point-"
        "readback-failure-v2.json"
    ),
    (
        f"{BASE}/bounded-dependency-source-combined-fixed-point-"
        "readback-manifest-v2.json"
    ),
)
STAGING_PREFIXES = (
    ".combined-fixed-point-v1-staging-",
    ".combined-fixed-point-readback-v2-staging-",
)

MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-fixed-point-"
    "readback-recovery-decision-v2"
)
NEXT_ACTION = (
    "prepare_separate_v2_recovery_readback_checker_tests_"
    "and_one_use_execution_permit"
)

EXPECTED_RAW: Mapping[str, str] = {
    DECISION_PATH: (
        "b3d89d1b4071c76d1639a05a8bc1112925af65feaf68d71f25f9c1a4b0d8f208"
    ),
    DECISION_READER_PATH: (
        "15119ba0f57c63cf14211d3ece97d29c6b500555aae003a7ccf619c9f8922da4"
    ),
    DECISION_CHECKER_PATH: (
        "186de17e8106228438037be576d367256d8da16af0476f4df9139b8f075e7469"
    ),
    DECISION_TESTS_PATH: (
        "f557b8a9e248ebe27793a9d80e91dc8930d83a1938c827f2b1bdd72a25044ccb"
    ),
    PERMIT_PATH: (
        "8a7bf20b4fcc6390e72002d795a550c1284757ed79dbeafcec4b767a81a29395"
    ),
    PERMIT_READER_PATH: (
        "0d22c23474499a0474075ac6de4c19d78eea67a32123d4528d24978d2c28b3ec"
    ),
    PERMIT_CHECKER_PATH: (
        "dfa5350e68f81c7e288fb281390827567a8b368596d5b8803b7848e81ddbdd25"
    ),
    PERMIT_TESTS_PATH: (
        "a639397f3bd8ca0fe75ca30677b1012612eecb9da65b34bbdba40b693ef0a954"
    ),
    RUNNER_PATH: (
        "228bff341c4923a96674076f99ca7f5168430de49da2708d60242df1580d82f6"
    ),
    RUNNER_TESTS_PATH: (
        "36f47f660323cced2664c7478e3f351024f6908c337b6524e6613f33f985ebf5"
    ),
    READBACK_PATH: (
        "f759f8f41d7dde7a95025e453bce278ba4cccf0dd6cc066c65e14d2be7f38ff1"
    ),
    READBACK_TESTS_PATH: (
        "1e5a6a3243e618b3be30dac632f77fc7375fae625d1931681149e7342ed5e782"
    ),
    CANDIDATE_PATH: (
        "b11047fd74e8ba4b41d66590975270921a5835bf444ad2e942af357d56764f15"
    ),
    CANDIDATE_TESTS_PATH: (
        "ab072a1ea2101f7a24a0d8ea1d6093391ca5ffffe87090f272acacce02340304"
    ),
    GRAPH_RUNNER_PATH: (
        "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
    ),
}

EXPECTED_DECISION_CONTENT_SHA256 = (
    "5211563f7ad301149a58c2d59fd6c6c3c234054badd075e47f71bc5e96e0549a"
)
EXPECTED_PERMIT_CONTENT_SHA256 = (
    "ce3352982e66d0dd2ef67875331abe12e608d05578bd341e4b664d709abcae14"
)
EXPECTED_CLAIM_RAW_SHA256 = (
    "fe362569ffcd4f4256e88338fd4f2b0d96b35c8cd443af47ac5c92a73d7d0c03"
)
EXPECTED_RESULT_RAW_SHA256 = (
    "6fcf6f231455d4e83d1144215234c056d15a9677fe9956c1ee4f134735c99b36"
)
EXPECTED_RESULT_CONTENT_SHA256 = (
    "3de4a5c0e1024c97c8e2e5f1e89041bc57d66d0a43c0ee7571b34b8185f0face"
)
EXPECTED_MANIFEST_RAW_SHA256 = (
    "d1c45eb7cca1645ba49e3a4974d77074ada7b195aaaeee62f448c9348cff8dd8"
)
EXPECTED_CLAIM_SEMANTIC_SHA256 = (
    "a6bd2d291e94051f2382367e1bab2c36a872db0060731578c0161ca466569e08"
)
EXPECTED_RESULT_SEMANTIC_SHA256 = (
    "2514df70f2821cf48f2bf6677d88cda1d38eb88be4fdbd7a0eb2e436d5fa53d8"
)
EXPECTED_MANIFEST_SEMANTIC_SHA256 = (
    "bd256a6293abd6113fd54cb95821bb8503a5e5c88512c00e53154021053e0a04"
)
EXPECTED_CANDIDATE_CONTENT_SHA256 = (
    "9f6fc09901423727f5aa5af5e0500adcbba4f31ba988c2452adb0e2ec5a0e0f2"
)
EXPECTED_CANDIDATE_PROJECTION_SHA256 = (
    "c744597d53e9bf50611f154421f661aec19f95a767dcbb9a80aa653fe83f2036"
)
EXPECTED_CANDIDATE_RESULT_PROJECTION_SHA256 = (
    "202fac96c9231a3aa6abc01bad8b45771aaeab49270ccbad98027a8e0754c1fc"
)
EXPECTED_HELD_BINDING_SET_SHA256 = (
    "f2a27bb27da1ba86d454625fcfaee64d5d1dbf5e8d38fd5fc0f6bcacbabf362e"
)
EXPECTED_GRAPH_SHA256 = (
    "541fc40bcfe87640033db54948911972dab9a6cab7e0b26d8021a89660be69d8"
)
EXPECTED_EDGE_SET_SHA256 = (
    "25cb01585c5d7fc4ec8840d038a195c513e0383e2a4931947312ea9e47e3db47"
)
EXPECTED_NODE_SET_SHA256 = (
    "970144c5bd6c1a7d8a13a8bdd5c9efc63fc81afab5860ca8fa77fce49871601a"
)
EXPECTED_GRAPH_FRONTIER_SHA256 = (
    "21043c3939299d0dee7676009e178c1938e243114d90a3d0c217a564aed02f1e"
)

READER_BYTES = b"""# Combined fixed-point readback recovery decision v2

Status: **recovery selected; execution not authorized**.

The consumed evaluation succeeded and its exact claim, result, and manifest
are preserved. The result is not a fixed point: its graph has sixteen new
tuples. The original readback check produced an `E_NAMESPACE` diagnostic
because the original permit context invokes the preparation decision's
clean-future-namespace computation even when terminal-aware checking was
requested. That CLI diagnostic records the observed failure only; it is not
accepted as terminal or semantic evidence.

This decision selects a versioned recovery design. It validates the original
decision and permit through their pure expected-payload paths, binds every
original tool and all 69 held source inputs, and binds the successful terminal
byte-for-byte. It does not modify, delete, retry, resume, backfill, execute, or
record anything.

A separate v2 recovery readback checker, tests, and one-use execution permit
must be prepared and independently reviewed. Until then, readback recording,
network use, source execution, filesystem extraction, subprocesses, Git
writes, authentication, signatures, private keys, tokens, passwords, and user
action remain unauthorized.
"""


class RecoveryError(RuntimeError):
    """A canonical fail-closed recovery decision error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RecoveryError(code)


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
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(type(key) is str and key not in result, "E_JSON")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(
                RecoveryError("E_JSON")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                RecoveryError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecoveryError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_sha256(document: Mapping[str, Any], scope: str) -> str:
    binding = document.get("contentBinding")
    require(
        type(binding) is dict
        and binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": scope,
            "sha256": binding.get("sha256"),
        },
        "E_CONTENT_BINDING",
    )
    payload = dict(document)
    payload.pop("contentBinding")
    actual = sha256(canonical_bytes(payload))
    require(binding["sha256"] == actual, "E_CONTENT_BINDING")
    return actual


def execute_fixed_module(
    name: str,
    path: str,
    raw: bytes,
) -> types.ModuleType:
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
    target = ROOT / path
    fd = os.open(
        target,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_BOOTSTRAP",
        )
        raw = b""
        while len(raw) < before.st_size:
            chunk = os.read(fd, min(65_536, before.st_size - len(raw)))
            require(bool(chunk), "E_BOOTSTRAP")
            raw += chunk
        after = os.fstat(fd)
        require(
            os.read(fd, 1) == b""
            and sha256(raw) == expected
            and (
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
        return raw
    finally:
        os.close(fd)


TRUST = execute_fixed_module(
    "combined_recovery_decision_v2_held_trust_root",
    DECISION_CHECKER_PATH,
    bootstrap_read(DECISION_CHECKER_PATH, EXPECTED_RAW[DECISION_CHECKER_PATH]),
)


def original_binding_rows() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES if path.startswith("docs/") else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        for path, digest in EXPECTED_RAW.items()
    ]


def package_binding_rows(
    *,
    include_decision: bool,
) -> list[dict[str, Any]]:
    paths = [THIS_CHECKER_PATH, THIS_TESTS_PATH, RECOVERY_READER_PATH]
    if include_decision:
        paths.append(RECOVERY_DECISION_PATH)
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


def terminal_binding_rows() -> list[dict[str, Any]]:
    return [
        {
            "path": CLAIM_PATH,
            "rawSha256": EXPECTED_CLAIM_RAW_SHA256,
            "maximumBytes": 818,
            "ownerOnly": True,
        },
        {
            "path": RESULT_PATH,
            "rawSha256": EXPECTED_RESULT_RAW_SHA256,
            "maximumBytes": 301041,
            "ownerOnly": True,
        },
        {
            "path": MANIFEST_PATH,
            "rawSha256": EXPECTED_MANIFEST_RAW_SHA256,
            "maximumBytes": 1320,
            "ownerOnly": True,
        },
    ]


def namespace_parent(namespace: Any, relative: str) -> tuple[int, str]:
    parent_relative, name = relative.rsplit("/", 1)
    matches = [
        parent
        for parent in namespace.parents
        if parent.relative == parent_relative
    ]
    require(len(matches) == 1, "E_NAMESPACE")
    return matches[0].fd, name


def absent_from_held_namespace(namespace: Any, relative: str) -> bool:
    parent_fd, name = namespace_parent(namespace, relative)
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return True
    except OSError as error:
        raise RecoveryError("E_NAMESPACE") from error
    return False


def held_dependency_names(namespace: Any) -> list[str]:
    matches = [
        parent
        for parent in namespace.parents
        if parent.relative == DEPENDENCY_ROOT
    ]
    require(len(matches) == 1, "E_NAMESPACE")
    try:
        return os.listdir(matches[0].fd)
    except OSError as error:
        raise RecoveryError("E_NAMESPACE") from error


def validate_namespace(
    root: Path,
    namespace: Any,
    terminal: Any | None = None,
) -> None:
    namespace.final_barrier()
    if terminal is not None:
        terminal.final_barrier()
    require(
        absent_from_held_namespace(namespace, FAILURE_PATH)
        and all(
            absent_from_held_namespace(namespace, path)
            for path in V1_READBACK_PATHS
        )
        and all(
            absent_from_held_namespace(namespace, path)
            for path in V2_RECOVERY_PATHS
        ),
        "E_NAMESPACE",
    )
    names = held_dependency_names(namespace)
    require(
        not any(
            name.startswith(prefix)
            for name in names
            for prefix in STAGING_PREFIXES
        ),
        "E_NAMESPACE",
    )
    if terminal is not None:
        terminal.final_barrier()
    namespace.final_barrier()


def claim_semantic_projection(claim: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "claimType",
        "schemaVersion",
        "automaticRetryAllowed",
        "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode",
        "decisionId",
        "decisionContentSha256",
        "decisionHeldBindingSetSha256",
        "permitId",
        "permitContentSha256",
        "externalAuthenticationRequired",
        "repositoryOwnerIdentityProofRequired",
        "userActionRequired",
    )
    return {field: claim.get(field) for field in fields}


def result_semantic_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "documentType",
        "schemaVersion",
        "evaluationId",
        "status",
        "result",
        "permitBinding",
        "decisionBinding",
        "claimRawSha256",
        "candidateSourceProjectionSha256",
        "graphSha256",
        "fixedPointReached",
        "nextAction",
        "candidateSelected",
        "dependencySourceReviewed",
        "semanticClosureComplete",
        "librarySelected",
        "rungThreeComplete",
        "networkUsed",
        "sourceExecutionUsed",
        "filesystemExtractionUsed",
        "subprocessUsed",
    )
    return {field: result.get(field) for field in fields}


def manifest_semantic_projection(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    fields = (
        "documentType",
        "schemaVersion",
        "permitId",
        "decisionId",
        "decisionHeldBindingSetSha256",
        "claimRawSha256",
        "resultPath",
        "resultRawSha256",
        "resultContentSha256",
        "resultStatus",
        "candidateSourceProjectionSha256",
        "fixedPointReached",
        "newTupleCount",
        "manifestWrittenLast",
        "nextAction",
        "networkUsed",
        "sourceExecutionUsed",
        "filesystemExtractionUsed",
        "subprocessUsed",
    )
    return {field: manifest.get(field) for field in fields}


class RecoveryContext:
    """Hold the original pure-payload authority without clean-namespace calls."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.decision_checker = None
        self.namespace = None
        self.originals = None
        self.static = None
        self.runner_held = None
        self.controls = None
        self.sources = None
        self.terminal = None
        self.package = None
        try:
            permit_raw = bootstrap_read(
                PERMIT_CHECKER_PATH,
                EXPECTED_RAW[PERMIT_CHECKER_PATH],
            )
            self.permit_checker = execute_fixed_module(
                "combined_recovery_decision_v2_permit_checker",
                PERMIT_CHECKER_PATH,
                permit_raw,
            )
            self.decision_checker = (
                self.permit_checker.load_decision_checker(root)
            )
            self.namespace = self.decision_checker.HeldNamespace(root)
            self.originals = self.decision_checker.HeldSet(
                root,
                original_binding_rows(),
            )
            self.static = self.decision_checker.HeldSet(
                root,
                self.permit_checker.static_bindings(
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
                self.decision_checker.source_hold_bindings(
                    self.source_rows
                ),
            )
            self.decision = validate_original_decision_direct(self)
            self.permit = validate_original_permit_direct(self)
            self.terminal = self.decision_checker.HeldSet(
                root,
                terminal_binding_rows(),
            )
            self.package = self.decision_checker.HeldSet(
                root,
                package_binding_rows(include_decision=False),
            )
            validate_namespace(root, self.namespace, self.terminal)
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        for held in (
            self.static,
            self.originals,
            self.runner_held,
            self.controls,
            self.sources,
            self.terminal,
            self.package,
        ):
            require(held is not None, "E_CONTEXT")
            held.final_barrier()
        validate_namespace(self.root, self.namespace, self.terminal)

    def close(self) -> None:
        for held in (
            self.package,
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
        self.package = None
        self.terminal = None
        self.sources = None
        self.controls = None
        self.runner_held = None
        self.static = None
        self.originals = None
        self.namespace = None


def validate_original_decision_direct(context: Any) -> dict[str, Any]:
    checker = context.decision_checker
    payload = checker.expected_payload(
        context.candidate,
        context.runner,
        context.documents,
        context.source_rows,
    )
    expected = checker.content_bound(payload)
    decision = checker.validate_decision_bytes(
        context.static.raw[DECISION_PATH],
        expected,
    )
    checker.validate_reader_bytes(
        context.static.raw[DECISION_READER_PATH]
    )
    return decision


def validate_original_permit_direct(context: Any) -> dict[str, Any]:
    checker = context.permit_checker
    payload = checker.expected_payload(context)
    expected = checker.content_bound(payload)
    return checker.validate_permit_bytes(
        context.static.raw[PERMIT_PATH],
        expected,
    )


def validate_source_rows(
    context: Any,
    rows: Any,
    decision_rows: Any,
) -> None:
    require(
        type(rows) is list
        and len(rows) == 69
        and rows == decision_rows
        and sha256(canonical_bytes(rows))
        == EXPECTED_HELD_BINDING_SET_SHA256,
        "E_SOURCE_CLOSURE",
    )
    projection_fields = (
        context.decision_checker.CANDIDATE_SOURCE_PROJECTION_FIELDS
    )
    projection = [
        {field: row[field] for field in projection_fields}
        for row in rows
    ]
    require(
        sha256(canonical_bytes(projection))
        == EXPECTED_CANDIDATE_PROJECTION_SHA256,
        "E_SOURCE_CLOSURE",
    )


def validate_terminal_semantics(
    claim: Mapping[str, Any],
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    require(
        sha256(canonical_bytes(claim_semantic_projection(claim)))
        == EXPECTED_CLAIM_SEMANTIC_SHA256
        and sha256(canonical_bytes(result_semantic_projection(result)))
        == EXPECTED_RESULT_SEMANTIC_SHA256
        and sha256(canonical_bytes(manifest_semantic_projection(manifest)))
        == EXPECTED_MANIFEST_SEMANTIC_SHA256,
        "E_TERMINAL_SEMANTICS",
    )
    candidate = result.get("candidateProjection")
    graph = candidate.get("graphDiscovery") if type(candidate) is dict else None
    verification = (
        candidate.get("checkerVerification")
        if type(candidate) is dict
        else None
    )
    require(
        type(candidate) is dict
        and sha256(canonical_bytes(candidate))
        == EXPECTED_CANDIDATE_RESULT_PROJECTION_SHA256
        and result.get("candidateContentSha256")
        == EXPECTED_CANDIDATE_CONTENT_SHA256
        and result.get("graphSha256") == EXPECTED_GRAPH_SHA256
        and result.get("fixedPointReached") is False
        and type(graph) is dict
        and graph.get("graphSha256") == EXPECTED_GRAPH_SHA256
        and graph.get("edgeSetSha256") == EXPECTED_EDGE_SET_SHA256
        and graph.get("nodeSetSha256") == EXPECTED_NODE_SET_SHA256
        and graph.get("moduleGraphAndFrontierSha256")
        == EXPECTED_GRAPH_FRONTIER_SHA256
        and graph.get("newTupleCount") == 16
        and graph.get("fixedPointReached") is False
        and type(verification) is dict
        and verification.get("fullInputReconstructionCount") == 2
        and verification.get("underlyingIndependentGraphAlgorithmCount")
        == 4,
        "E_GRAPH_SEMANTICS",
    )
    require(
        manifest.get("claimRawSha256") == EXPECTED_CLAIM_RAW_SHA256
        and manifest.get("resultRawSha256") == EXPECTED_RESULT_RAW_SHA256
        and manifest.get("resultContentSha256")
        == EXPECTED_RESULT_CONTENT_SHA256
        and manifest.get("newTupleCount") == 16
        and manifest.get("fixedPointReached") is False
        and manifest.get("manifestWrittenLast") is True
        and result.get("claimRawSha256") == EXPECTED_CLAIM_RAW_SHA256
        and result.get("networkUsed") is False
        and result.get("sourceExecutionUsed") is False
        and result.get("filesystemExtractionUsed") is False
        and result.get("subprocessUsed") is False,
        "E_TERMINAL_CROSS_BINDING",
    )


def validate_source_and_terminal(context: RecoveryContext) -> None:
    decision = context.decision
    permit = context.permit
    claim_raw = context.terminal.raw[CLAIM_PATH]
    result_raw = context.terminal.raw[RESULT_PATH]
    manifest_raw = context.terminal.raw[MANIFEST_PATH]
    claim = strict_json(claim_raw)
    result = strict_json(result_raw)
    manifest = strict_json(manifest_raw)
    require(
        claim_raw == canonical_bytes(claim)
        and result_raw == canonical_bytes(result)
        and manifest_raw == canonical_bytes(manifest),
        "E_CANONICAL_TERMINAL",
    )
    require(
        content_sha256(
            decision,
            "decision_without_contentBinding",
        )
        == EXPECTED_DECISION_CONTENT_SHA256
        and content_sha256(
            permit,
            "permit_without_contentBinding",
        )
        == EXPECTED_PERMIT_CONTENT_SHA256
        and content_sha256(
            result,
            "result_without_contentBinding",
        )
        == EXPECTED_RESULT_CONTENT_SHA256,
        "E_CONTENT_BINDING",
    )
    rows = permit["sourceInputSet"]["bindings"]
    decision_rows = decision["sourceInputSet"]["bindings"]
    validate_source_rows(context, rows, decision_rows)
    for row in rows:
        raw = context.sources.raw[row["path"]]
        require(
            len(raw) == row["byteSize"]
            and sha256(raw) == row["rawSha256"]
            and row["mode"] == "0600"
            and row["linkCount"] == 1,
            "E_SOURCE_CLOSURE",
        )
    validate_terminal_semantics(claim, result, manifest)


def expected_recovery_decision(context: RecoveryContext) -> dict[str, Any]:
    package = context.package.raw
    bindings = [
        {
            "role": {
                DECISION_PATH: "original_decision",
                DECISION_READER_PATH: "original_decision_reader",
                DECISION_CHECKER_PATH: "original_decision_checker",
                DECISION_TESTS_PATH: "original_decision_tests",
                PERMIT_PATH: "original_permit",
                PERMIT_READER_PATH: "original_permit_reader",
                PERMIT_CHECKER_PATH: "original_permit_checker",
                PERMIT_TESTS_PATH: "original_permit_tests",
                RUNNER_PATH: "original_evaluation_runner",
                RUNNER_TESTS_PATH: "original_evaluation_runner_tests",
                READBACK_PATH: "failed_original_readback_checker",
                READBACK_TESTS_PATH: "original_readback_checker_tests",
                CANDIDATE_PATH: "candidate_checker",
                CANDIDATE_TESTS_PATH: "candidate_checker_tests",
                GRAPH_RUNNER_PATH: "immutable_wave1_graph_runner",
            }[path],
            "path": path,
            "rawSha256": digest,
        }
        for path, digest in EXPECTED_RAW.items()
    ]
    payload = {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-recovery-decision"
        ),
        "schemaVersion": "2.0",
        "decisionId": DECISION_ID,
        "recordedDate": "2026-07-24",
        "status": "recovery_selected_execution_not_authorized",
        "result": (
            "consumed_success_terminal_preserved_"
            "versioned_readback_recovery_selected"
        ),
        "scope": (
            "read_only_recovery_design_for_exact_consumed_"
            "combined_fixed_point_success_terminal"
        ),
        "incident": {
            "failedCheckPath": READBACK_PATH,
            "failedCheckRawSha256": EXPECTED_RAW[READBACK_PATH],
            "observedFailureCode": "E_NAMESPACE",
            "observedPhase": "check",
            "observationAuthority": "diagnostic_only_not_terminal_evidence",
            "cliErrorOutputAcceptedAsEvidence": False,
            "rootCause": (
                "original_permit_authority_context_calls_original_decision_"
                "expected_decision_clean_namespace_path_even_when_"
                "require_clean_namespace_is_false"
            ),
            "originalExpectedDecisionCallableAllowed": False,
            "directPureExpectedPayloadParityRequired": True,
        },
        "immutableOriginalBindings": bindings,
        "selectedRecoveryPackage": {
            "readerPath": RECOVERY_READER_PATH,
            "readerRawSha256": sha256(package[RECOVERY_READER_PATH]),
            "checkerPath": THIS_CHECKER_PATH,
            "checkerRawSha256": sha256(package[THIS_CHECKER_PATH]),
            "checkerTestsPath": THIS_TESTS_PATH,
            "checkerTestsRawSha256": sha256(package[THIS_TESTS_PATH]),
            "decisionExpectedPayloadDirectlyValidated": True,
            "permitExpectedPayloadDirectlyValidated": True,
            "originalDecisionValidatorReused": True,
            "originalPermitValidatorReused": True,
        },
        "sourceInputBinding": {
            "heldInputCount": 69,
            "decisionHeldBindingSetSha256": (
                EXPECTED_HELD_BINDING_SET_SHA256
            ),
            "candidateSourceProjectionSha256": (
                EXPECTED_CANDIDATE_PROJECTION_SHA256
            ),
            "allRowsHeldOwnerOnly": True,
            "allRowsMode": "0600",
            "allRowsLinkCount": 1,
            "outerHoldRequiredThroughFinalBarrier": True,
        },
        "consumedSuccessTerminal": {
            "claim": {
                "path": CLAIM_PATH,
                "rawSha256": EXPECTED_CLAIM_RAW_SHA256,
                "semanticSha256": EXPECTED_CLAIM_SEMANTIC_SHA256,
                "byteSize": 818,
                "mode": "0600",
                "linkCount": 1,
            },
            "result": {
                "path": RESULT_PATH,
                "rawSha256": EXPECTED_RESULT_RAW_SHA256,
                "contentSha256": EXPECTED_RESULT_CONTENT_SHA256,
                "semanticSha256": EXPECTED_RESULT_SEMANTIC_SHA256,
                "candidateProjectionSha256": (
                    EXPECTED_CANDIDATE_RESULT_PROJECTION_SHA256
                ),
                "byteSize": 301041,
                "mode": "0600",
                "linkCount": 1,
            },
            "manifest": {
                "path": MANIFEST_PATH,
                "rawSha256": EXPECTED_MANIFEST_RAW_SHA256,
                "semanticSha256": EXPECTED_MANIFEST_SEMANTIC_SHA256,
                "byteSize": 1320,
                "mode": "0600",
                "linkCount": 1,
                "manifestWrittenLast": True,
            },
            "graphSha256": EXPECTED_GRAPH_SHA256,
            "edgeSetSha256": EXPECTED_EDGE_SET_SHA256,
            "nodeSetSha256": EXPECTED_NODE_SET_SHA256,
            "graphAndFrontierSha256": EXPECTED_GRAPH_FRONTIER_SHA256,
            "newTupleCount": 16,
            "fixedPointReached": False,
            "fullSourceReconstructionCount": 2,
            "underlyingIndependentGraphAlgorithmCount": 4,
        },
        "namespaceContract": {
            "originalFailurePath": FAILURE_PATH,
            "originalFailureRequiredAbsent": True,
            "originalV1ReadbackPathsRequiredAbsent": list(V1_READBACK_PATHS),
            "v2RecoveryPathsReservedAndRequiredAbsent": list(
                V2_RECOVERY_PATHS
            ),
            "stagingPrefixesRequiredAbsent": list(STAGING_PREFIXES),
            "rootAndAllParentsHeldByFileDescriptor": True,
            "terminalHeldByFileDescriptor": True,
        },
        "preservationAndAuthority": {
            "recoveryDecisionRecorded": True,
            "executionAuthorized": False,
            "readbackRecordingAuthorized": False,
            "oneUseExecutionPermitRecorded": False,
            "originalPermitRetryAllowed": False,
            "originalPermitReuseAllowed": False,
            "originalRunnerExecuteAllowed": False,
            "originalTerminalModifyAllowed": False,
            "originalTerminalDeleteAllowed": False,
            "originalReadbackBackfillAllowed": False,
            "automaticRetryAllowed": False,
            "networkAuthorized": False,
            "sourceExecutionAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "subprocessAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "nextAction": NEXT_ACTION,
    }
    payload["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "decision_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return payload


def validate_recovery_document(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    require(type(actual) is dict and actual == expected, "E_RECOVERY_DECISION")
    require(
        content_sha256(actual, "decision_without_contentBinding")
        == actual["contentBinding"]["sha256"],
        "E_RECOVERY_DECISION",
    )


def evaluate(
    root: Path = ROOT,
    *,
    verify_disk: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context = RecoveryContext(root)
    decision_held = None
    try:
        validate_source_and_terminal(context)
        require(
            context.package.raw[RECOVERY_READER_PATH] == READER_BYTES,
            "E_READER",
        )
        expected = expected_recovery_decision(context)
        if verify_disk:
            decision_held = context.decision_checker.HeldSet(
                root,
                package_binding_rows(include_decision=True)[-1:],
            )
            raw = decision_held.raw[RECOVERY_DECISION_PATH]
            actual = strict_json(raw)
            require(raw == canonical_bytes(actual), "E_CANONICAL_DECISION")
            validate_recovery_document(actual, expected)
            decision_held.final_barrier()
        context.final_barrier()
        if decision_held is not None:
            decision_held.final_barrier()
        validate_namespace(root, context.namespace, context.terminal)
        return expected, {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "readback-recovery-decision-check"
            ),
            "schemaVersion": "2.0",
            "status": "validated_recovery_selected_execution_not_authorized",
            "validationPassed": True,
            "onDiskExactEqualityVerified": verify_disk,
            "heldSourceInputCount": 69,
            "terminalState": "consumed_success",
            "graphSha256": EXPECTED_GRAPH_SHA256,
            "newTupleCount": 16,
            "fixedPointReached": False,
            "executionAuthorized": False,
            "readbackRecordingAuthorized": False,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessCount": 0,
            "fileWriteCount": 0,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
            "nextAction": NEXT_ACTION,
        }
    finally:
        if decision_held is not None:
            decision_held.close()
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise RecoveryError("E_ARGUMENT")


def parse_arguments(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = CanonicalArgumentParser(
        description=__doc__,
        add_help=False,
    )
    parser.add_argument("--print-expected", action="store_true")
    return parser.parse_args(argv)


def error_document(error: RecoveryError) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-recovery-decision-error"
        ),
        "schemaVersion": "2.0",
        "status": "failed_closed",
        "validationPassed": False,
        "failureCode": error.code,
        "executionAuthorized": False,
        "readbackRecordingAuthorized": False,
        "networkUsed": False,
        "sourceExecutionUsed": False,
        "filesystemExtractionUsed": False,
        "subprocessCount": 0,
        "fileWriteCount": 0,
        "gitWriteAuthorized": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_arguments(argv)
        expected, summary = evaluate(
            ROOT,
            verify_disk=not args.print_expected,
        )
        output = expected if args.print_expected else summary
        sys.stdout.buffer.write(canonical_bytes(output))
        return 0
    except RecoveryError as error:
        sys.stdout.buffer.write(canonical_bytes(error_document(error)))
        return 1
    except Exception:
        error = RecoveryError("E_INTERNAL")
        sys.stdout.buffer.write(canonical_bytes(error_document(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
