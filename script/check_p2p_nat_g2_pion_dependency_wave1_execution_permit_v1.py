#!/usr/bin/env python3
"""Validate the separate G2 Pion dependency wave-one execution permit."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import types
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave1_decision_v1.py"
)
DECISION_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave1_decision_v1.py"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v1.md"
)
RUNNER_PATH = "script/acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
RUNNER_TEST_PATH = "script/test_acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v1.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_execution_permit_v1.py"
)

EXPECTED_DECISION_RAW_SHA256 = (
    "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
)
EXPECTED_DECISION_CONTENT_SHA256 = (
    "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201"
)
EXPECTED_READER_RAW_SHA256 = (
    "aed39c3614f0237656f43aafabf45f125939cfb888ab9a5b76c4bcb8f26ce850"
)
EXPECTED_DECISION_CHECKER_RAW_SHA256 = (
    "207775b8f0b2c22cf50bb5f62d7e64657cf1ed73cca540b46cac36ea2da5c74b"
)
EXPECTED_DECISION_TEST_RAW_SHA256 = (
    "1fe982561a61d9f73e0d2eb2b3f9d35b07b080ea042835de57e78c2c6ab95249"
)
EXPECTED_SOURCE_ARCHIVE_RAW_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
EXPECTED_DECISION_STATUS = (
    "wave1_source_identity_and_request_contract_prepared_acquisition_not_authorized"
)
EXPECTED_DECISION_RESULT = (
    "exact_19_root_requirement_source_identities_and_bounded_wave1_request_contract_prepared"
)
EXPECTED_DECISION_NEXT_ACTION = (
    "prepare_separate_versioned_wave1_execution_permit_after_checker_runner_and_tests"
)

EXPECTED_DATE = "2026-07-24"
EXPECTED_STATUS = "wave1_dependency_source_acquisition_authorized_not_consumed"
EXPECTED_RESULT = "exact_19_public_proxy_zip_requests_authorized_once_not_executed"
EXPECTED_NEXT_ACTION = "execute_bound_dependency_source_wave1_once"
EXPECTED_SCOPE = "single_exact_19_zip_public_go_proxy_source_intake_only"
EXPECTED_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v1"
)

MAXIMUM_TRACKED_BYTES = 4 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"__PENDING_[A-Z0-9_]+__|^0{64}$")

TOOL_ROWS = (
    (
        "bounded_dependency_wave1_runner",
        RUNNER_PATH,
    ),
    (
        "bounded_dependency_wave1_runner_offline_tests",
        RUNNER_TEST_PATH,
    ),
    (
        "strict_dependency_wave1_execution_permit_checker",
        CHECKER_PATH,
    ),
    (
        "execution_permit_checker_mutation_tests",
        CHECKER_TEST_PATH,
    ),
)

PERMIT_TOP_LEVEL_KEYS = {
    "documentType",
    "schemaVersion",
    "permitId",
    "recordedDate",
    "status",
    "result",
    "nextAction",
    "scope",
    "personalProjectBoundary",
    "decisionBinding",
    "toolBindings",
    "interpreterIsolationContract",
    "oneUseConsumption",
    "requestContract",
    "networkAuthority",
    "archiveValidationContract",
    "filesystemWriteAuthority",
    "resourceLimits",
    "receiptFailureManifestContract",
    "stateMachine",
    "authority",
    "execution",
    "closure",
    "nonClaims",
    "contentBinding",
}

EXPECTED_NONCLAIMS = [
    "permit_is_not_execution_or_success_evidence",
    "wave1_root_requirements_are_not_complete_graph_or_fixed_point_evidence",
    "dependency_direct_sumdb_inclusion_proofs_are_not_verified",
    "root_go_sum_is_not_repository_owner_attestation_or_license_receipt",
    "tls_and_proxy_response_do_not_prove_repository_ownership",
    "module_h1_is_not_raw_zip_sha256",
    "embedded_go_mod_h1_is_not_a_separate_mod_endpoint_observation",
    "acquisition_is_not_source_license_security_or_sbom_review",
    "acquisition_does_not_close_dependency_semantic_or_finding_gaps",
    "runner_self_checks_are_not_independent_readback",
    "later_independent_readback_is_a_point_in_time_observation_not_future_immutability",
    "local_claim_does_not_defeat_hostile_same_uid_filesystem_tampering",
    "nineteen_http_requests_do_not_bound_dns_packets_tcp_connections_or_tls_handshakes",
    "permit_does_not_select_a_candidate_library_or_product_endpoint",
]


class CheckError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise CheckError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def require_isolated_interpreter() -> None:
    require(sys.flags.isolated == 1, "E_RUNTIME", "isolated interpreter required")
    require(sys.dont_write_bytecode, "E_RUNTIME", "bytecode writes must be disabled")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    require(isinstance(value, dict), "E_SCHEMA", f"{label} must be an object")
    actual = set(value)
    require(
        actual == expected,
        "E_SCHEMA",
        f"{label} keys differ: missing={sorted(expected - actual)} "
        f"unexpected={sorted(actual - expected)}",
    )
    return value


def typed_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            typed_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            typed_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def strict_json(raw: bytes, label: str) -> dict[str, Any]:
    require(
        raw.endswith(b"\n") and not raw.endswith(b"\r\n") and b"\r" not in raw,
        "E_JSON",
        f"{label} must use one LF-terminated UTF-8 JSON document",
    )

    def unique(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            require(key not in result, "E_JSON", f"{label} has duplicate key")
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        fail("E_JSON", f"{label} contains a non-finite number")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except CheckError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError("E_JSON", f"{label} is invalid JSON") from error
    require(isinstance(value, dict), "E_SCHEMA", f"{label} root must be an object")
    return value


def validate_relative_path(relative: str) -> tuple[str, ...]:
    require(isinstance(relative, str), "E_FILESYSTEM", "path must be a string")
    path = PurePosixPath(relative)
    require(not path.is_absolute(), "E_FILESYSTEM", "absolute path rejected")
    require("\\" not in relative and "\x00" not in relative, "E_FILESYSTEM", "unsafe path")
    parts = path.parts
    require(bool(parts), "E_FILESYSTEM", "empty path rejected")
    require(
        all(part not in {"", ".", ".."} for part in parts),
        "E_FILESYSTEM",
        "path traversal rejected",
    )
    return parts


def directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def file_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def descriptor_state(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def repository_root_identity(info: os.stat_result) -> dict[str, int]:
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "ownerUid": info.st_uid,
        "mode": stat.S_IMODE(info.st_mode),
    }


class Snapshot:
    def __init__(self, path: str, fd: int, raw: bytes, state: tuple[int, ...]) -> None:
        self.path = path
        self.fd = fd
        self.raw = raw
        self.state = state


class SafeReader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root_fd = os.open(root, directory_flags())
        root_info = os.fstat(self.root_fd)
        require(stat.S_ISDIR(root_info.st_mode), "E_FILESYSTEM", "root is not directory")
        require(root_info.st_uid == os.getuid(), "E_FILESYSTEM", "root owner mismatch")
        require(
            stat.S_IMODE(root_info.st_mode) & 0o022 == 0,
            "E_FILESYSTEM",
            "root is writable by another user",
        )
        self.initial_root_identity = repository_root_identity(root_info)
        self.snapshots: list[Snapshot] = []

    def read(self, relative: str, maximum_bytes: int = MAXIMUM_TRACKED_BYTES) -> bytes:
        parts = validate_relative_path(relative)
        current = os.dup(self.root_fd)
        try:
            for part in parts[:-1]:
                child = os.open(part, directory_flags(), dir_fd=current)
                info = os.fstat(child)
                require(stat.S_ISDIR(info.st_mode), "E_FILESYSTEM", "ancestor type")
                require(info.st_uid == os.getuid(), "E_FILESYSTEM", "ancestor owner")
                require(
                    stat.S_IMODE(info.st_mode) & 0o022 == 0,
                    "E_FILESYSTEM",
                    "ancestor writable by another user",
                )
                os.close(current)
                current = child
            fd = os.open(parts[-1], file_flags(), dir_fd=current)
        except (FileNotFoundError, NotADirectoryError, OSError) as error:
            os.close(current)
            raise CheckError("E_FILESYSTEM", f"cannot securely open {relative}") from error
        os.close(current)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode), "E_FILESYSTEM", f"{relative} type")
            require(before.st_uid == os.getuid(), "E_FILESYSTEM", f"{relative} owner")
            require(before.st_nlink == 1, "E_FILESYSTEM", f"{relative} link count")
            require(
                stat.S_IMODE(before.st_mode) & 0o022 == 0,
                "E_FILESYSTEM",
                f"{relative} writable by another user",
            )
            require(before.st_size <= maximum_bytes, "E_FILESYSTEM", f"{relative} size")
            chunks: list[bytes] = []
            remaining = maximum_bytes + 1
            while remaining > 0:
                chunk = os.read(fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            require(len(raw) <= maximum_bytes, "E_FILESYSTEM", f"{relative} size")
            after = os.fstat(fd)
            require(
                descriptor_state(before) == descriptor_state(after)
                and len(raw) == before.st_size,
                "E_TOCTOU",
                f"{relative} changed during read",
            )
            snapshot = Snapshot(relative, fd, raw, descriptor_state(after))
            self.snapshots.append(snapshot)
            return raw
        except Exception:
            os.close(fd)
            raise

    def verify(self) -> None:
        for snapshot in self.snapshots:
            info = os.fstat(snapshot.fd)
            require(
                descriptor_state(info) == snapshot.state,
                "E_TOCTOU",
                f"{snapshot.path} descriptor changed",
            )
            os.lseek(snapshot.fd, 0, os.SEEK_SET)
            raw = b""
            while len(raw) <= len(snapshot.raw):
                chunk = os.read(
                    snapshot.fd,
                    min(64 * 1024, len(snapshot.raw) + 1 - len(raw)),
                )
                if not chunk:
                    break
                raw += chunk
            require(raw == snapshot.raw, "E_TOCTOU", f"{snapshot.path} bytes changed")
            parts = validate_relative_path(snapshot.path)
            current = os.dup(self.root_fd)
            try:
                for part in parts[:-1]:
                    child = os.open(part, directory_flags(), dir_fd=current)
                    os.close(current)
                    current = child
                named = os.stat(parts[-1], dir_fd=current, follow_symlinks=False)
            finally:
                os.close(current)
            require(
                (named.st_dev, named.st_ino) == (info.st_dev, info.st_ino),
                "E_TOCTOU",
                f"{snapshot.path} name changed",
            )

    def verify_root(self) -> dict[str, int]:
        held = os.fstat(self.root_fd)
        try:
            named = os.stat(self.root, follow_symlinks=False)
        except OSError as error:
            raise CheckError("E_TOCTOU", "repository root name changed") from error
        for info in (held, named):
            require(stat.S_ISDIR(info.st_mode), "E_TOCTOU", "repository root type")
            require(
                info.st_uid == os.getuid(),
                "E_TOCTOU",
                "repository root owner",
            )
            require(
                stat.S_IMODE(info.st_mode) & 0o022 == 0,
                "E_TOCTOU",
                "repository root mode",
            )
        held_identity = repository_root_identity(held)
        require(
            held_identity == repository_root_identity(named)
            and held_identity == self.initial_root_identity,
            "E_TOCTOU",
            "repository root identity changed",
        )
        return held_identity

    def close(self) -> None:
        for snapshot in self.snapshots:
            try:
                os.close(snapshot.fd)
            except OSError:
                pass
        self.snapshots.clear()
        os.close(self.root_fd)


def verify_raw(raw: bytes, expected: str, label: str) -> None:
    require(sha256_bytes(raw) == expected, "E_BINDING", f"{label} raw binding")


def content_binding(document: Mapping[str, Any], label: str) -> str:
    binding = exact_keys(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    require(binding["algorithm"] == "sha256", "E_BINDING", f"{label} algorithm")
    require(
        binding["canonicalization"]
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "E_BINDING",
        f"{label} canonicalization",
    )
    require(
        binding["scope"] == "permit_without_contentBinding",
        "E_BINDING",
        f"{label} scope",
    )
    digest = binding["sha256"]
    require(
        isinstance(digest, str) and HEX_SHA256.fullmatch(digest) is not None,
        "E_BINDING",
        f"{label} digest",
    )
    unsigned = dict(document)
    unsigned.pop("contentBinding", None)
    require(
        sha256_bytes(canonical_json_bytes(unsigned)) == digest,
        "E_BINDING",
        f"{label} content digest",
    )
    return digest


def load_and_run_decision_checker(
    root: Path,
    checker_raw: bytes,
) -> None:
    verify_raw(
        checker_raw,
        EXPECTED_DECISION_CHECKER_RAW_SHA256,
        "decision checker",
    )
    module = types.ModuleType("g2_wave1_decision_checker_for_permit")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(root / DECISION_CHECKER_PATH),
            "__loader__": None,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(
                checker_raw,
                DECISION_CHECKER_PATH,
                "exec",
                flags=0,
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
        module.require_isolated_interpreter()
        module.check(root)
    except CheckError:
        raise
    except Exception as error:
        raise CheckError("E_LINEAGE", "decision checker rejected predecessor") from error


def validate_decision(decision: Mapping[str, Any]) -> None:
    require(decision.get("status") == EXPECTED_DECISION_STATUS, "E_LINEAGE", "decision status")
    require(decision.get("result") == EXPECTED_DECISION_RESULT, "E_LINEAGE", "decision result")
    require(
        decision.get("nextAction") == EXPECTED_DECISION_NEXT_ACTION,
        "E_LINEAGE",
        "decision next action",
    )
    require(
        decision.get("contentBinding", {}).get("sha256")
        == EXPECTED_DECISION_CONTENT_SHA256,
        "E_LINEAGE",
        "decision content binding",
    )
    source = decision.get("sourceSnapshot", {})
    require(
        source.get("archiveRawSha256") == EXPECTED_SOURCE_ARCHIVE_RAW_SHA256,
        "E_LINEAGE",
        "root archive binding",
    )
    require(
        source.get("archiveByteSize") == 293023
        and source.get("archiveEntryCount") == 129,
        "E_LINEAGE",
        "root archive shape",
    )
    require(
        decision.get("wave", {}).get("selectedTupleCount") == 19,
        "E_WAVE",
        "wave tuple count",
    )


def validate_tool_bindings(
    permit: Mapping[str, Any],
    raw_by_path: Mapping[str, bytes],
) -> None:
    bindings = permit.get("toolBindings")
    require(isinstance(bindings, list) and len(bindings) == 4, "E_TOOL_BINDING", "tool count")
    expected_rows = []
    for role, path in TOOL_ROWS:
        raw = raw_by_path[path]
        expected_rows.append(
            {
                "role": role,
                "path": path,
                "rawSha256": sha256_bytes(raw),
            }
        )
    require(bindings == expected_rows, "E_TOOL_BINDING", "tool bytes or order")
    for row in bindings:
        require(
            HEX_SHA256.fullmatch(row["rawSha256"]) is not None
            and PLACEHOLDER.search(row["rawSha256"]) is None,
            "E_TOOL_BINDING",
            "tool binding placeholder",
        )


def validate_runner_source(
    runner_raw: bytes,
    runner_test_raw: bytes,
    checker_raw: bytes,
) -> None:
    try:
        tree = ast.parse(runner_raw, filename=RUNNER_PATH)
        test_tree = ast.parse(runner_test_raw, filename=RUNNER_TEST_PATH)
    except SyntaxError as error:
        raise CheckError("E_TOOL_BINDING", "runner source syntax") from error
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    require(
        {"subprocess", "requests", "httpx", "socket"}.isdisjoint(imports),
        "E_TOOL_BINDING",
        "runner forbidden import",
    )
    require(
        {
            "system",
            "popen",
            "fork",
            "spawnl",
            "spawnv",
            "execl",
            "execv",
        }.isdisjoint(calls),
        "E_TOOL_BINDING",
        "runner process call",
    )
    source = runner_raw.decode("utf-8")
    checker_digest = sha256_bytes(checker_raw)
    require(
        f'EXPECTED_CHECKER_RAW_SHA256 = "{checker_digest}"' in source,
        "E_TOOL_BINDING",
        "runner checker trust root",
    )
    for token in (
        "ProxyHandler({})",
        "RejectRedirects()",
        "ssl.create_default_context()",
        "RENAME_EXCL",
        "renameatx_np",
        '"E_POST_PUBLISH_UNCERTAIN"',
        '"E_REQUEST_DEADLINE"',
        "os.umask(0o077)",
        "def create_download_file_flags() -> int:",
        "os.O_RDWR",
        "create_download_file_flags(),",
        "def set_response_io_timeout(",
        'read_one = getattr(response, "read1", None)',
        "chunk = read_one(",
        "def hard_wall_clock_request_deadline(",
        "def restore_hard_deadline_state(",
        "for _attempt in range(2):",
        "if disarmed:",
        "signal.setitimer(signal.ITIMER_REAL",
        "threading.current_thread() is threading.main_thread()",
        "def validate_local_header(",
        "ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE",
        "def named_entry_matches_open_file(",
        "def validate_held_output_inventory(",
        "validate_held_output_inventory(staging_fd, held_outputs)",
        "validate_held_output_inventory(published_fd, held_outputs)",
        "verified_fd: int",
        "entry.create_system in {0, 3}",
        'authority.get("repositoryRootIdentity")',
        "def inspect_one_use_state(",
        "one_use_artifact_count(inspect_one_use_state(root_fd)) == 0",
        '"blocked_one_use_state_present"',
        'phase="zip"',
        'phase="publication"',
        "def normalize_execution_failure(",
        "os.fsync(parent_fd)",
        '"independentReadbackPassed": False',
    ):
        require(token in source, "E_TOOL_BINDING", f"runner missing {token}")
    for forbidden in (
        "--url",
        "--host",
        "--output",
        "--proxy",
        "--credential",
        "--token",
        "--retry",
        "renamex_np",
        "ROOT / DEPENDENCY_PARENT / staging_name",
        "response.read(",
        '"independentReadbackPassed": True',
    ):
        require(forbidden not in source, "E_TOOL_BINDING", f"runner unsafe {forbidden}")
    test_names = [
        node.name
        for node in ast.walk(test_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    require(
        len(test_names) == 44 and len(set(test_names)) == 44,
        "E_TOOL_BINDING",
        "runner test count",
    )


def validate_permit(
    permit: Mapping[str, Any],
    decision: Mapping[str, Any],
    raw_by_path: Mapping[str, bytes],
) -> None:
    exact_keys(permit, PERMIT_TOP_LEVEL_KEYS, "permit")
    expected_scalars = {
        "documentType": "aetherlink.g2-pion-rung3-dependency-wave1-execution-permit",
        "schemaVersion": "1.0",
        "permitId": EXPECTED_PERMIT_ID,
        "recordedDate": EXPECTED_DATE,
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "scope": EXPECTED_SCOPE,
    }
    for key, expected in expected_scalars.items():
        require(permit.get(key) == expected, "E_PERMIT_STATE", f"permit.{key}")

    personal = exact_keys(
        permit["personalProjectBoundary"],
        {
            "projectOwnership",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
            "privateKeyTokenPasswordOrSignatureRequired",
            "productPairingAuthenticationUnaffected",
        },
        "personalProjectBoundary",
    )
    require(personal["projectOwnership"] == "personal_single_owner", "E_AUTHORITY", "ownership")
    require(
        typed_equal(
            personal,
            {
            "projectOwnership": "personal_single_owner",
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "privateKeyTokenPasswordOrSignatureRequired": False,
            "productPairingAuthenticationUnaffected": True,
            },
        ),
        "E_AUTHORITY",
        "personal project boundary",
    )

    decision_binding = exact_keys(
        permit["decisionBinding"],
        {
            "path",
            "rawSha256",
            "contentSha256",
            "decisionId",
            "requiredStatus",
            "requiredResult",
            "requiredNextAction",
            "sourceArchiveRawSha256",
        },
        "decisionBinding",
    )
    require(
        typed_equal(
            decision_binding,
            {
            "path": DECISION_PATH,
            "rawSha256": EXPECTED_DECISION_RAW_SHA256,
            "contentSha256": EXPECTED_DECISION_CONTENT_SHA256,
            "decisionId": decision["decisionId"],
            "requiredStatus": EXPECTED_DECISION_STATUS,
            "requiredResult": EXPECTED_DECISION_RESULT,
            "requiredNextAction": EXPECTED_DECISION_NEXT_ACTION,
            "sourceArchiveRawSha256": EXPECTED_SOURCE_ARCHIVE_RAW_SHA256,
            },
        ),
        "E_LINEAGE",
        "decision binding",
    )
    validate_tool_bindings(permit, raw_by_path)

    isolation = exact_keys(
        permit["interpreterIsolationContract"],
        {
            "preflightCommand",
            "executeCommand",
            "isolatedInterpreterRequired",
            "sitePackagesAllowed",
            "bytecodeWritesAllowed",
            "pythonPathAllowed",
            "environmentOverridesAllowed",
            "processUmask",
            "cliOverridesAllowed",
        },
        "interpreterIsolationContract",
    )
    base_command = ["python3", "-I", "-B", "-S", RUNNER_PATH]
    require(
        typed_equal(
            isolation,
            {
            "preflightCommand": [*base_command, "--preflight"],
            "executeCommand": [*base_command, "--execute"],
            "isolatedInterpreterRequired": True,
            "sitePackagesAllowed": False,
            "bytecodeWritesAllowed": False,
            "pythonPathAllowed": False,
            "environmentOverridesAllowed": False,
            "processUmask": "077",
            "cliOverridesAllowed": False,
            },
        ),
        "E_RUNTIME",
        "interpreter contract",
    )

    one_use = exact_keys(
        permit["oneUseConsumption"],
        {
            "initialState",
            "claimPath",
            "claimCreate",
            "claimMode",
            "claimPersistsAfterAnyNetworkAttempt",
            "claimUncertaintyConsumesPermit",
            "automaticRetryAllowed",
            "secondExecutionAllowed",
            "preclaimFailureConsumesPermit",
        },
        "oneUseConsumption",
    )
    require(
        typed_equal(
            one_use,
            {
            "initialState": "authorized_not_consumed",
            "claimPath": decision["plannedAcquisitionContract"]["claimPath"],
            "claimCreate": "dirfd_relative_o_excl_no_follow_file_and_parent_fsync",
            "claimMode": "0600",
            "claimPersistsAfterAnyNetworkAttempt": True,
            "claimUncertaintyConsumesPermit": True,
            "automaticRetryAllowed": False,
            "secondExecutionAllowed": False,
            "preclaimFailureConsumesPermit": False,
            },
        ),
        "E_PERMIT_STATE",
        "one-use contract",
    )

    request = exact_keys(
        permit["requestContract"],
        {
            "requestCount",
            "method",
            "scheme",
            "host",
            "port",
            "tupleOrder",
            "pathSource",
            "responseBodyKind",
            "goModByteSource",
            "redirectsAllowed",
            "automaticRetriesAllowed",
            "rangeOrResumeAllowed",
            "alternateMirrorAllowed",
            "queryFragmentOrUserInfoAllowed",
            "authenticationHeadersAllowed",
            "cookiesAllowed",
            "clientCertificatesAllowed",
            "ambientProxyAllowed",
            "contentEncoding",
            "allowedContentTypes",
            "successStatusCode",
        },
        "requestContract",
    )
    require(
        typed_equal(
            request,
            {
            "requestCount": 19,
            "method": "GET",
            "scheme": "https",
            "host": "proxy.golang.org",
            "port": 443,
            "tupleOrder": "exact_decision_wave_order_1_through_19_sequential",
            "pathSource": "exact_decision_tuple_url_path",
            "responseBodyKind": "module_zip_only",
            "goModByteSource": "embedded_zip_entry_only",
            "redirectsAllowed": False,
            "automaticRetriesAllowed": False,
            "rangeOrResumeAllowed": False,
            "alternateMirrorAllowed": False,
            "queryFragmentOrUserInfoAllowed": False,
            "authenticationHeadersAllowed": False,
            "cookiesAllowed": False,
            "clientCertificatesAllowed": False,
            "ambientProxyAllowed": False,
            "contentEncoding": "identity",
            "allowedContentTypes": ["application/zip", "application/octet-stream"],
            "successStatusCode": 200,
            },
        ),
        "E_REQUEST_CONTRACT",
        "request contract",
    )

    network = exact_keys(
        permit["networkAuthority"],
        {
            "boundedSourceIntakeDnsAuthorized",
            "boundedSourceIntakeTcpAuthorized",
            "boundedSourceIntakeTlsAuthorized",
            "boundedSourceIntakeHttpsAuthorized",
            "authorizedHost",
            "authorizedRequestCount",
            "runtimeSocketAuthorized",
            "runtimeNetworkAuthorized",
            "productNetworkAuthorized",
            "relayOrP2PNetworkAuthorized",
        },
        "networkAuthority",
    )
    require(
        typed_equal(
            network,
            {
            "boundedSourceIntakeDnsAuthorized": True,
            "boundedSourceIntakeTcpAuthorized": True,
            "boundedSourceIntakeTlsAuthorized": True,
            "boundedSourceIntakeHttpsAuthorized": True,
            "authorizedHost": "proxy.golang.org",
            "authorizedRequestCount": 19,
            "runtimeSocketAuthorized": False,
            "runtimeNetworkAuthorized": False,
            "productNetworkAuthorized": False,
            "relayOrP2PNetworkAuthorized": False,
            },
        ),
        "E_NETWORK_AUTHORITY",
        "network authority",
    )

    archive = exact_keys(
        permit["archiveValidationContract"],
        {
            "filesystemExtractionAllowed",
            "streamedToOwnerOnlyTemporaryFiles",
            "openedDescriptorValidation",
            "centralAndLocalHeaderConsistencyRequired",
            "crcRequired",
            "exactEofRequired",
            "zip64Allowed",
            "encryptionAllowed",
            "explicitDirectoryEntriesAllowed",
            "symlinkOrSpecialFileAllowed",
            "duplicateOrCasefoldCollisionAllowed",
            "validUtf8AndNfcPathsRequired",
            "allowedCompressionMethods",
            "exactModulePrefixRequired",
            "moduleZipH1Required",
            "embeddedGoModH1Required",
            "orderedSourceSetDigestRequired",
        },
        "archiveValidationContract",
    )
    require(
        typed_equal(
            archive,
            {
            "filesystemExtractionAllowed": False,
            "streamedToOwnerOnlyTemporaryFiles": True,
            "openedDescriptorValidation": True,
            "centralAndLocalHeaderConsistencyRequired": True,
            "crcRequired": True,
            "exactEofRequired": True,
            "zip64Allowed": False,
            "encryptionAllowed": False,
            "explicitDirectoryEntriesAllowed": False,
            "symlinkOrSpecialFileAllowed": False,
            "duplicateOrCasefoldCollisionAllowed": False,
            "validUtf8AndNfcPathsRequired": True,
            "allowedCompressionMethods": ["stored", "deflated"],
            "exactModulePrefixRequired": True,
            "moduleZipH1Required": True,
            "embeddedGoModH1Required": True,
            "orderedSourceSetDigestRequired": True,
            },
        ),
        "E_WAVE",
        "archive validation",
    )

    filesystem = exact_keys(
        permit["filesystemWriteAuthority"],
        {
            "existingAncestorPolicy",
            "newDirectoryMode",
            "newFileMode",
            "claimWriteAuthorized",
            "stagingWriteAuthorized",
            "acceptedZipWriteAuthorized",
            "successReceiptWriteAuthorized",
            "failureReceiptWriteAuthorized",
            "manifestWriteAuthorized",
            "failedStagingCleanupAuthorized",
            "atomicNoReplaceFinalDirectoryPublicationRequired",
            "unexpectedSiblingScope",
            "sourceModificationAuthorized",
            "sourceExtractionAuthorized",
            "otherRepositoryWritesAuthorized",
        },
        "filesystemWriteAuthority",
    )
    require(
        typed_equal(
            filesystem,
            {
            "existingAncestorPolicy": "current_user_owned_and_not_group_or_world_writable",
            "newDirectoryMode": "0700",
            "newFileMode": "0600",
            "claimWriteAuthorized": True,
            "stagingWriteAuthorized": True,
            "acceptedZipWriteAuthorized": True,
            "successReceiptWriteAuthorized": True,
            "failureReceiptWriteAuthorized": True,
            "manifestWriteAuthorized": True,
            "failedStagingCleanupAuthorized": True,
            "atomicNoReplaceFinalDirectoryPublicationRequired": True,
            "unexpectedSiblingScope": "reserved_staging_prefix_and_final_directory_contents_only",
            "sourceModificationAuthorized": False,
            "sourceExtractionAuthorized": False,
            "otherRepositoryWritesAuthorized": False,
            },
        ),
        "E_FILESYSTEM_AUTHORITY",
        "filesystem authority",
    )
    require(
        typed_equal(permit["resourceLimits"], decision["resourceLimits"]),
        "E_BOUNDS",
        "resource limits",
    )

    terminal = exact_keys(
        permit["receiptFailureManifestContract"],
        {
            "successReceiptPath",
            "failureReceiptPath",
            "manifestPath",
            "successState",
            "failureState",
            "postPublishUncertainState",
            "successAndFailureMutuallyExclusive",
            "acceptedArtifactCountOnSuccess",
            "acceptedArtifactCountOnFailure",
            "boundedFailureReasonCodesOnly",
            "rawErrorsBodiesHeadersCertificatesOrAbsolutePathsRecorded",
            "manifestWrittenLast",
            "runnerMayClaimIndependentReadback",
            "postPublishUncertainAutomaticRecoveryAllowed",
            "postPublishUncertainNextAction",
        },
        "receiptFailureManifestContract",
    )
    contract = decision["plannedAcquisitionContract"]
    require(
        typed_equal(
            terminal,
            {
            "successReceiptPath": contract["successReceiptPath"],
            "failureReceiptPath": contract["failureReceiptPath"],
            "manifestPath": contract["manifestPath"],
            "successState": "acquired_pending_independent_readback",
            "failureState": "wave1_acquisition_failed_permit_consumed",
            "postPublishUncertainState": "consumed_terminal_state_uncertain",
            "successAndFailureMutuallyExclusive": True,
            "acceptedArtifactCountOnSuccess": 19,
            "acceptedArtifactCountOnFailure": 0,
            "boundedFailureReasonCodesOnly": True,
            "rawErrorsBodiesHeadersCertificatesOrAbsolutePathsRecorded": False,
            "manifestWrittenLast": True,
            "runnerMayClaimIndependentReadback": False,
            "postPublishUncertainAutomaticRecoveryAllowed": False,
            "postPublishUncertainNextAction": "prepare_new_versioned_wave1_recovery_decision",
            },
        ),
        "E_PERMIT_STATE",
        "terminal contract",
    )

    states = permit["stateMachine"]
    require(
        typed_equal(
            states,
            [
            {"order": 0, "state": "authorized_not_consumed", "terminal": False},
            {"order": 1, "state": "consumed_no_request", "terminal": False},
            {"order": 2, "state": "request_in_progress_1_through_19", "terminal": False},
            {"order": 3, "state": "acquired_staged", "terminal": False},
            {"order": 4, "state": "final_published_pending_receipt", "terminal": False},
            {
                "order": 5,
                "state": "acquired_pending_independent_readback",
                "terminal": True,
            },
            {"order": 6, "state": "consumed_failed", "terminal": True},
            {
                "order": 7,
                "state": "consumed_terminal_state_uncertain",
                "terminal": True,
            },
            ],
        ),
        "E_PERMIT_STATE",
        "state machine",
    )

    authority = exact_keys(
        permit["authority"],
        {
            "permitRecorded",
            "exactWave1AcquisitionAuthorized",
            "boundedSourceIntakeNetworkAuthorized",
            "boundedExecutionArtifactWritesAuthorized",
            "packageManagerAuthorized",
            "goCommandAuthorized",
            "gitCommandAuthorized",
            "shellOrSubprocessAuthorized",
            "compilerAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "runtimeOrProductNetworkAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "gitWriteAuthorized",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
        },
        "authority",
    )
    require(
        typed_equal(
            authority,
            {
            "permitRecorded": True,
            "exactWave1AcquisitionAuthorized": True,
            "boundedSourceIntakeNetworkAuthorized": True,
            "boundedExecutionArtifactWritesAuthorized": True,
            "packageManagerAuthorized": False,
            "goCommandAuthorized": False,
            "gitCommandAuthorized": False,
            "shellOrSubprocessAuthorized": False,
            "compilerAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "runtimeOrProductNetworkAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            },
        ),
        "E_AUTHORITY",
        "authority",
    )

    execution = exact_keys(
        permit["execution"],
        {
            "permitRecorded",
            "permitConsumed",
            "claimCreated",
            "requestCount",
            "acceptedArtifactCount",
            "networkUsed",
            "successReceiptCreated",
            "failureReceiptCreated",
            "manifestCreated",
            "independentReadbackPassed",
            "sourceCompiledLoadedOrExecuted",
            "runtimeNetworkUsed",
            "deviceUsed",
            "deploymentPerformed",
            "gitOperationPerformed",
        },
        "execution",
    )
    require(
        typed_equal(
            execution,
            {
            "permitRecorded": True,
            "permitConsumed": False,
            "claimCreated": False,
            "requestCount": 0,
            "acceptedArtifactCount": 0,
            "networkUsed": False,
            "successReceiptCreated": False,
            "failureReceiptCreated": False,
            "manifestCreated": False,
            "independentReadbackPassed": False,
            "sourceCompiledLoadedOrExecuted": False,
            "runtimeNetworkUsed": False,
            "deviceUsed": False,
            "deploymentPerformed": False,
            "gitOperationPerformed": False,
            },
        ),
        "E_EXECUTION",
        "execution state",
    )
    closure = exact_keys(
        permit["closure"],
        {
            "openFindingCount",
            "findingsClosedByPermit",
            "waveAcquired",
            "graphFixedPointReached",
            "dependencySourceReviewed",
            "dependencyClosureComplete",
            "semanticClosureComplete",
            "rungThreeComplete",
            "candidateSelected",
            "librarySelected",
        },
        "closure",
    )
    require(
        typed_equal(
            closure,
            {
            "openFindingCount": 19,
            "findingsClosedByPermit": 0,
            "waveAcquired": False,
            "graphFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            },
        ),
        "E_CLOSURE",
        "closure",
    )
    require(
        typed_equal(permit["nonClaims"], EXPECTED_NONCLAIMS),
        "E_NONCLAIM",
        "nonclaims",
    )
    content_binding(permit, "permit")


def validate_permit_reader(raw: bytes, permit: Mapping[str, Any]) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CheckError("E_BINDING", "permit reader encoding") from error
    required = (
        EXPECTED_PERMIT_ID,
        EXPECTED_STATUS,
        EXPECTED_RESULT,
        EXPECTED_NEXT_ACTION,
        "19",
        "proxy.golang.org",
        "POST_PUBLISH_UNCERTAIN",
        "consumed_terminal_state_uncertain",
        "사용자 인증",
        "요구하지 않는다",
        "independent readback",
        "source extraction",
        "creator-system",
        "repository-root device",
        "verified descriptor",
        "SIGALRM",
        "one-use state",
        "All 19",
        "pre-publication re-hash/fsync",
        "It does not claim to",
    )
    for token in required:
        require(token in text, "E_BINDING", f"permit reader missing {token}")


def validate_repository(
    root: Path = ROOT,
    before_final_barrier: Callable[[list[Snapshot]], None] | None = None,
) -> dict[str, Any]:
    require_isolated_interpreter()
    reader = SafeReader(root)
    paths = [
        DECISION_PATH,
        READER_PATH,
        DECISION_CHECKER_PATH,
        DECISION_TEST_PATH,
        PERMIT_PATH,
        PERMIT_READER_PATH,
        RUNNER_PATH,
        RUNNER_TEST_PATH,
        CHECKER_PATH,
        CHECKER_TEST_PATH,
    ]
    try:
        raw = {path: reader.read(path) for path in paths}
        verify_raw(raw[DECISION_PATH], EXPECTED_DECISION_RAW_SHA256, "decision")
        verify_raw(raw[READER_PATH], EXPECTED_READER_RAW_SHA256, "decision reader")
        verify_raw(
            raw[DECISION_CHECKER_PATH],
            EXPECTED_DECISION_CHECKER_RAW_SHA256,
            "decision checker",
        )
        verify_raw(
            raw[DECISION_TEST_PATH],
            EXPECTED_DECISION_TEST_RAW_SHA256,
            "decision tests",
        )
        load_and_run_decision_checker(root, raw[DECISION_CHECKER_PATH])
        decision = strict_json(raw[DECISION_PATH], "decision")
        validate_decision(decision)
        permit = strict_json(raw[PERMIT_PATH], "permit")
        raw_by_path = {
            RUNNER_PATH: raw[RUNNER_PATH],
            RUNNER_TEST_PATH: raw[RUNNER_TEST_PATH],
            CHECKER_PATH: raw[CHECKER_PATH],
            CHECKER_TEST_PATH: raw[CHECKER_TEST_PATH],
        }
        validate_runner_source(
            raw[RUNNER_PATH],
            raw[RUNNER_TEST_PATH],
            raw[CHECKER_PATH],
        )
        validate_permit(permit, decision, raw_by_path)
        validate_permit_reader(raw[PERMIT_READER_PATH], permit)
        if before_final_barrier is not None:
            before_final_barrier(reader.snapshots)
        reader.verify()
        reader.verify_root()
        load_and_run_decision_checker(root, raw[DECISION_CHECKER_PATH])
        reader.verify()
        root_identity = reader.verify_root()
        return {
            "permit": permit,
            "decision": decision,
            "repositoryRootIdentity": root_identity,
            "permitRawSha256": sha256_bytes(raw[PERMIT_PATH]),
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "trackedFileReadCount": len(paths),
            "trackedByteCount": sum(len(value) for value in raw.values()),
            "decisionCheckerPassCount": 2,
            "runnerTestCount": 44,
            "executionArtifactReadCount": 0,
            "fileWriteCount": 0,
            "networkOperationCount": 0,
            "permitConsumptionState": "authorized_not_consumed",
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        reader.close()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root used only by mutation tests.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        result = validate_repository(args.root)
    except CheckError as error:
        print(f"[{error.code}] {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("[E_INTERNAL] permit validation failed", file=sys.stderr)
        return 1
    print(
        "G2 Pion dependency wave-one execution permit v1 passed: exact 19 ZIP "
        "requests authorized once, not consumed; no user authentication required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
