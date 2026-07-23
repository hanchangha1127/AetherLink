#!/usr/bin/env python3
"""Validate the immutable blocked Phase A progress snapshot."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = ROOT / "docs/security-hardening/production-p2p-nat-v1"
PHASE_A_ROOT = DESIGN_ROOT / "controlled-network-spike/phase-a"
PROGRESS_PATH = PHASE_A_ROOT / "progress-v1.json"
DECISION_PATH = DESIGN_ROOT / "controlled-network-spike/decision-v1.json"
HANDOFF_PATH = DESIGN_ROOT / "implementation/handoff-v4.json"
OFFLINE_SOURCE_PATH = PHASE_A_ROOT / "offline-source-intake-v1.json"
COMPILE_ONLY_PATH = PHASE_A_ROOT / "libjuice-compile-only-contract-v1.json"
STATIC_HARNESS_PATH = PHASE_A_ROOT / "static-harness-egress-policy-v1.json"
CHECKER_PATH = ROOT / "script/check_p2p_nat_phase_a_progress.py"
TEST_PATH = ROOT / "script/test_p2p_nat_phase_a_progress.py"

SOURCE_SHA256 = {
    DECISION_PATH: "1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228",
    HANDOFF_PATH: "b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd",
    OFFLINE_SOURCE_PATH: "3359624f1fa1474b2bfd2acd4e3591fd1e0a8cd5840cda4372327f25dfc68850",
    PHASE_A_ROOT / "offline-source-intake-v1.md": "c186c4bed45a6edd9d270062ac9927839ab1f5c8f5c66eab966dfc9a61c0d2ee",
    COMPILE_ONLY_PATH: "2664736c7b783d650eabcd8bc4ad5391babd456d3b7df596dff2171eba7d84b4",
    PHASE_A_ROOT / "libjuice-compile-only-contract-v1.md": "6e181de962f961ccf1b35f020e83e2cceb3829e13bf824c7fa68f17677d09420",
    ROOT / "apps/macos/P2PNATContracts/Sources/P2PNATSessionCrypto.swift": "8933edff1e9ed11ac510f4c5c394fa924f5764057e187d127b485661cdc135bb",
    ROOT / "apps/macos/P2PNATContracts/Tests/P2PNATSessionCryptoVectorTests.swift": "c39c4e37a3f022698d9994804972a0bafd14000d010baa99bc6928066ef87acd",
    ROOT / "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCrypto.kt": "a7222474e0b38e061a1d04ba5993af844f8f1cebaed36496403ae3bf47bd5b93",
    ROOT / "apps/android/core/protocol/src/test/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCryptoVectorTest.kt": "3a28cef4d942dac397bd443ec3b7e0f9c96e2a0c9ccda836ec3c49f178367bf4",
    ROOT / "shared/protocol/fixtures/production-p2p-nat-v1-session-crypto-vectors.json": "4693f71330b5f40f9b99b4445c24fba8fa0939c4ae76f8b9bf3c9644b08f29c9",
    ROOT / "script/check_p2p_nat_session_crypto_vectors.py": "c8f51de5a77599617eb24df3f767569e778e3ac327a8eae7e3fdad6fcad949ee",
    ROOT / "script/test_p2p_nat_session_crypto_vectors.py": "37ba5844a7822d65bca27b312718c7a43c30febc2c0ca83976b91a246e09b526",
    STATIC_HARNESS_PATH: "6934995f310449fa675348c0314ea5bac2991693f1e1d080aa469d7d856ec9f5",
    PHASE_A_ROOT / "static-harness-egress-policy-v1.md": "0578c5f6b89bc3db5cb1ce6ed24f62bad32898b923411759dbf55f946d2fb61b",
}
HISTORICAL_SOURCE_COMPATIBILITY_SHA256 = {
    "apps/macos/P2PNATContracts/Sources/P2PNATSessionCrypto.swift": (
        "a13e8a8275bf57079957787be5ec693529620098d08027e24fcccfe07b51a80d",
        "8933edff1e9ed11ac510f4c5c394fa924f5764057e187d127b485661cdc135bb",
    ),
    "apps/macos/P2PNATContracts/Tests/P2PNATSessionCryptoVectorTests.swift": (
        "95ecc1dec6841219a0040ef80cc5d4754074dacbeb659301f7ead42f18265ad6",
        "c39c4e37a3f022698d9994804972a0bafd14000d010baa99bc6928066ef87acd",
    ),
    "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCrypto.kt": (
        "61c87888ab8d39e62471f68b4aa0e068a348aa6f3c95e90b31a04a613f71fde7",
        "a7222474e0b38e061a1d04ba5993af844f8f1cebaed36496403ae3bf47bd5b93",
    ),
    "apps/android/core/protocol/src/test/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCryptoVectorTest.kt": (
        "7a3748f90b2de686610935422f0d7d28a6d7f738018387b9c99f46b96b0bfd6f",
        "3a28cef4d942dac397bd443ec3b7e0f9c96e2a0c9ccda836ec3c49f178367bf4",
    ),
}
ARTIFACT_SHA256 = {
    PROGRESS_PATH: "3e0d98c2c03e97f7f16e63cca9c545553234ab05ff7d233bae607e09f13738a3",
}
EXPECTED_SEMANTIC_SHA256 = "9cb6c10afed5f12c71c8d7e967700aa7c7773049177a24eb2322e303a2604fd6"

DECISION_ORDER = (
    "networking_library_selection",
    "session_cryptography_library_selection",
    "isolated_harness_design",
    "socket_destination_and_egress_controls",
)
RESOLUTIONS = {
    "networking_library_selection": "libjuice-1.7.2-static-c-abi",
    "session_cryptography_library_selection": "platform-native-p256-hkdf-sha256-aes256gcm",
    "isolated_harness_design": "linux-netns-twin-agent-local-services",
    "socket_destination_and_egress_controls": "numeric-endpoint-allowlist-plus-os-egress-witness",
}
EVIDENCE_ORDER = (
    "libjuice_supply_chain_and_source_audit",
    "android_macos_compile_only_integration",
    "cross_platform_session_crypto_vectors",
    "static_harness_and_egress_policy",
    "phase_a_security_review",
)
EXPECTED_BOUNDED_AUTHORITY = {
    "offlineSourceInspectionAuthorized": True,
    "compileOnlyIntegrationAuthorized": True,
    "sessionCryptoVectorImplementationAuthorized": True,
    "staticHarnessImplementationAuthorized": True,
}
EXPECTED_EXECUTION_AUTHORITY = {
    "sourceAcquisitionNetworkIOAllowed": False,
    "sourceExecutionAllowed": False,
    "compilerInvocationAuthorized": False,
    "archiveInvocationAuthorized": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIOAllowed": False,
    "harnessNetworkIOAllowed": False,
    "controlledSpikeNetworkIOAllowed": False,
    "controlledSpikeSocketExecutionAuthorized": False,
    "phaseBExecutionAuthorized": False,
    "phaseBNetworkIOAllowed": False,
    "phaseBSocketExecutionAuthorized": False,
    "externalEgressAllowed": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
}
EXPECTED_EVIDENCE_STATUS = {
    "libjuice_supply_chain_and_source_audit": {
        "status": "blocked_missing_offline_source",
        "proofScope": "blocked_state_only_no_source_present_or_consumed",
        "artifacts": [
            {
                "path": "offline-source-intake-v1.json",
                "sha256": SOURCE_SHA256[OFFLINE_SOURCE_PATH],
            },
            {
                "path": "offline-source-intake-v1.md",
                "sha256": SOURCE_SHA256[PHASE_A_ROOT / "offline-source-intake-v1.md"],
            },
        ],
    },
    "android_macos_compile_only_integration": {
        "status": "blocked_missing_reviewed_source",
        "proofScope": "blocked_contract_only_no_compiler_archive_or_native_wiring",
        "artifacts": [
            {
                "path": "libjuice-compile-only-contract-v1.json",
                "sha256": SOURCE_SHA256[COMPILE_ONLY_PATH],
            },
            {
                "path": "libjuice-compile-only-contract-v1.md",
                "sha256": SOURCE_SHA256[PHASE_A_ROOT / "libjuice-compile-only-contract-v1.md"],
            },
        ],
    },
    "cross_platform_session_crypto_vectors": {
        "status": "completed_bounded_no_device_vectors",
        "proofScope": "bounded_no_device_fixed_vector_interoperability_only",
        "artifacts": [
            {
                "path": "../../../../../apps/macos/P2PNATContracts/Sources/P2PNATSessionCrypto.swift",
                "sha256": SOURCE_SHA256[ROOT / "apps/macos/P2PNATContracts/Sources/P2PNATSessionCrypto.swift"],
            },
            {
                "path": "../../../../../apps/macos/P2PNATContracts/Tests/P2PNATSessionCryptoVectorTests.swift",
                "sha256": SOURCE_SHA256[ROOT / "apps/macos/P2PNATContracts/Tests/P2PNATSessionCryptoVectorTests.swift"],
            },
            {
                "path": "../../../../../apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCrypto.kt",
                "sha256": SOURCE_SHA256[ROOT / "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCrypto.kt"],
            },
            {
                "path": "../../../../../apps/android/core/protocol/src/test/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCryptoVectorTest.kt",
                "sha256": SOURCE_SHA256[ROOT / "apps/android/core/protocol/src/test/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCryptoVectorTest.kt"],
            },
            {
                "path": "../../../../../shared/protocol/fixtures/production-p2p-nat-v1-session-crypto-vectors.json",
                "sha256": SOURCE_SHA256[ROOT / "shared/protocol/fixtures/production-p2p-nat-v1-session-crypto-vectors.json"],
            },
            {
                "path": "../../../../../script/check_p2p_nat_session_crypto_vectors.py",
                "sha256": SOURCE_SHA256[ROOT / "script/check_p2p_nat_session_crypto_vectors.py"],
            },
            {
                "path": "../../../../../script/test_p2p_nat_session_crypto_vectors.py",
                "sha256": SOURCE_SHA256[ROOT / "script/test_p2p_nat_session_crypto_vectors.py"],
            },
        ],
    },
    "static_harness_and_egress_policy": {
        "status": "static_design_complete",
        "proofScope": "non_executable_static_design_only",
        "artifacts": [
            {
                "path": "static-harness-egress-policy-v1.json",
                "sha256": SOURCE_SHA256[STATIC_HARNESS_PATH],
            },
            {
                "path": "static-harness-egress-policy-v1.md",
                "sha256": SOURCE_SHA256[PHASE_A_ROOT / "static-harness-egress-policy-v1.md"],
            },
        ],
    },
    "phase_a_security_review": {
        "status": "blocked_on_source_and_compile_evidence",
        "proofScope": "whole_phase_a_review_not_started",
        "artifacts": [],
    },
}
EXPECTED_DOCUMENT = {
    "documentType": "aetherlink.p2p-nat-phase-a-progress",
    "schemaVersion": "1.0",
    "artifactId": "production_p2p_nat_v1_controlled_spike_phase_a_progress_v1",
    "profileId": "production_p2p_nat_v1_recommended",
    "recordedAt": "2026-07-17",
    "sourceDecision": {
        "path": "../decision-v1.json",
        "decisionId": "production_p2p_nat_v1_controlled_network_spike_decision_v1",
        "sha256": SOURCE_SHA256[DECISION_PATH],
    },
    "sourceHandoff": {
        "path": "../../implementation/handoff-v4.json",
        "handoffId": "production_p2p_nat_v1_handoff_v4",
        "sha256": SOURCE_SHA256[HANDOFF_PATH],
    },
    "approvalSnapshot": {
        "count": 4,
        "approvalSource": "explicit_user_instruction",
        "decisionOrder": list(DECISION_ORDER),
        "resolutions": RESOLUTIONS,
    },
    "overallStatus": "blocked_incomplete_phase_a",
    "statusSummary": {
        "requiredBoundedEvidenceGroupCount": 4,
        "boundedEvidenceCompletedCount": 2,
        "blockedBoundedEvidenceCount": 2,
        "phaseASecurityReviewStatus": "blocked_on_source_and_compile_evidence",
    },
    "evidenceStatus": EXPECTED_EVIDENCE_STATUS,
    "boundedPhaseAAuthority": EXPECTED_BOUNDED_AUTHORITY,
    "executionAuthority": EXPECTED_EXECUTION_AUTHORITY,
    "phaseBDecisionEligible": False,
    "measurementStatus": "not_started",
    "nextStep": "provide_reviewed_offline_libjuice_source_then_publish_new_versioned_intake_and_compile_contract_before_whole_phase_a_review",
    "immutability": {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_progress",
    },
}

ALLOWED_IMPORTS = {"ast", "copy", "hashlib", "json", "sys", "unittest"}
ALLOWED_FROM_IMPORTS = {
    "__future__": {"annotations"},
    "pathlib": {"Path"},
    "typing": {"Any"},
    "script": {
        "check_p2p_nat_phase_a_progress",
        "check_p2p_nat_security_design",
    },
}
FORBIDDEN_NAMES = {
    "__builtins__", "__import__", "compile", "delattr", "eval", "exec", "getattr",
    "globals", "locals", "open", "setattr", "vars",
}
FORBIDDEN_DYNAMIC_ATTRIBUTE_NAMES = {
    "__class__", "__closure__", "__code__", "__dict__", "__getattribute__",
    "__globals__", "__mro__", "__subclasses__",
}
FORBIDDEN_METHOD_NAMES = {
    "CDLL", "PyDLL", "accept", "bind", "call", "check_call", "check_output", "chmod",
    "connect", "connect_ex", "create_connection", "create_subprocess_exec",
    "create_subprocess_shell", "extract", "extractall", "fork", "fork_exec", "forkpty",
    "glob", "hardlink_to", "iglob", "import_module", "link_to", "listen", "make_archive",
    "mkdir", "open", "popen", "posix_spawn", "posix_spawnp", "recv", "recvfrom",
    "rename", "replace", "request", "rglob", "rmdir", "rmtree", "run", "send",
    "sendall", "sendto", "socket", "spawn", "symlink_to", "system", "touch", "unlink",
    "unpack_archive", "urlopen", "urlretrieve", "write_bytes", "write_text",
}


class PhaseAProgressValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise PhaseAProgressValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON name: {key}")
        result[key] = value
    return result


def reject_nonstandard_number(value: str) -> None:
    fail(f"non-standard JSON number is forbidden: {value}")


def parse_json(raw: str, label: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=reject_duplicate_names,
            parse_constant=reject_nonstandard_number,
        )
    except (json.JSONDecodeError, TypeError) as error:
        fail(f"{label}: invalid JSON: {error}")


def load_json(path: Path) -> Any:
    try:
        return parse_json(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
    except (OSError, UnicodeError) as error:
        fail(f"{path.relative_to(ROOT)}: {error}")


def recursive_exact(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected):
        fail(f"{label}: expected exact type {type(expected).__name__}")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            fail(f"{label}: expected exact keys {sorted(expected)}, got {sorted(actual)}")
        for key, expected_value in expected.items():
            recursive_exact(actual[key], expected_value, f"{label}.{key}")
        return
    if isinstance(expected, list):
        if len(actual) != len(expected):
            fail(f"{label}: expected exactly {len(expected)} entries")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            recursive_exact(actual_item, expected_item, f"{label}[{index}]")
        return
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label}: expected object")
    return value


def hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_file_hash(path: Path, expected: str) -> None:
    try:
        actual = hash_bytes(path.read_bytes())
    except OSError as error:
        fail(f"{path.relative_to(ROOT)}: {error}")
    compatibility = HISTORICAL_SOURCE_COMPATIBILITY_SHA256.get(
        path.relative_to(ROOT).as_posix()
    )
    if compatibility is not None and actual == compatibility[0]:
        actual = compatibility[1]
    if actual != expected:
        fail(f"{path.relative_to(ROOT)}: SHA-256 drifted; expected {expected}, got {actual}")


def semantic_digest(document: Any) -> str:
    try:
        canonical = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        fail(f"progress-v1: cannot canonicalize strict JSON: {error}")
    return hash_bytes(canonical)


def validate_source_documents() -> None:
    for path, digest in SOURCE_SHA256.items():
        validate_file_hash(path, digest)

    decision = require_object(load_json(DECISION_PATH), "decision")
    recursive_exact(
        decision.get("decisionId"),
        "production_p2p_nat_v1_controlled_network_spike_decision_v1",
        "decision.decisionId",
    )
    recursive_exact(decision.get("decisionOrder"), list(DECISION_ORDER), "decision.decisionOrder")
    expected_decision_approvals = [
        {
            "decisionId": decision_id,
            "status": "approved_for_bounded_phase_a_evidence",
            "recommendedOptionId": RESOLUTIONS[decision_id],
            "resolution": RESOLUTIONS[decision_id],
            "approvalSource": "explicit_user_instruction",
        }
        for decision_id in DECISION_ORDER
    ]
    recursive_exact(decision.get("approvals"), expected_decision_approvals, "decision.approvals")

    handoff = require_object(load_json(HANDOFF_PATH), "handoff")
    recursive_exact(
        handoff.get("handoffId"),
        "production_p2p_nat_v1_handoff_v4",
        "handoff.handoffId",
    )
    expected_handoff_approvals = [
        {
            "decisionId": decision_id,
            "status": "approved_for_bounded_phase_a_evidence",
            "resolution": RESOLUTIONS[decision_id],
            "approvalSource": "explicit_user_instruction",
        }
        for decision_id in DECISION_ORDER
    ]
    recursive_exact(
        handoff.get("controlledSpikeApprovals"),
        expected_handoff_approvals,
        "handoff.controlledSpikeApprovals",
    )
    packages = handoff.get("packages")
    if not isinstance(packages, list) or len(packages) != 3:
        fail("handoff.packages: expected exactly three canonical packages")
    controlled = packages[2]
    if not isinstance(controlled, dict) or controlled.get("packageId") != "controlled-network-spike":
        fail("handoff.packages: canonical controlled-network-spike package is missing")
    phase_a = require_object(controlled.get("phaseA"), "handoff.phaseA")
    phase_b = require_object(controlled.get("phaseB"), "handoff.phaseB")
    recursive_exact(
        phase_a.get("sourceExecutionAllowed"),
        False,
        "handoff.phaseA.sourceExecutionAllowed",
    )
    recursive_exact(
        phase_a.get("socketCreationAllowed"),
        False,
        "handoff.phaseA.socketCreationAllowed",
    )
    recursive_exact(
        phase_b.get("executionAuthorized"),
        False,
        "handoff.phaseB.executionAuthorized",
    )

    offline = require_object(load_json(OFFLINE_SOURCE_PATH), "offline")
    for field, expected in {
        "artifactStatus": "blocked_missing_offline_source",
        "sourcePresence": "absent",
        "auditStatus": "not_started",
        "compileStatus": "not_started",
    }.items():
        recursive_exact(offline.get(field), expected, f"offline.{field}")
    failure_policy = require_object(offline.get("failurePolicy"), "offline.failurePolicy")
    recursive_exact(
        failure_policy.get("completionClaimsAllowed"),
        False,
        "offline.failurePolicy.completionClaimsAllowed",
    )

    compile_only = require_object(load_json(COMPILE_ONLY_PATH), "compile")
    compile_status = require_object(compile_only.get("currentStatus"), "compile.currentStatus")
    compile_authority = require_object(
        compile_only.get("authorization"), "compile.authorization"
    )
    recursive_exact(
        compile_status.get("android_macos_compile_only_integration"),
        "blocked_missing_reviewed_source",
        "compile.currentStatus.android_macos_compile_only_integration",
    )
    recursive_exact(
        compile_status.get("executionStatus"),
        "not_executed",
        "compile.currentStatus.executionStatus",
    )
    recursive_exact(
        compile_status.get("compilationEvidence"),
        [],
        "compile.currentStatus.compilationEvidence",
    )
    recursive_exact(
        compile_authority.get("currentCompilerInvocationAuthorized"),
        False,
        "compile.authorization.currentCompilerInvocationAuthorized",
    )
    recursive_exact(
        compile_authority.get("currentArchiveInvocationAuthorized"),
        False,
        "compile.authorization.currentArchiveInvocationAuthorized",
    )

    static_harness = require_object(load_json(STATIC_HARNESS_PATH), "static")
    for field, expected in {
        "artifactStatus": "static_design_complete",
        "executionStatus": "not_executed",
        "measurementStatus": "not_started",
    }.items():
        recursive_exact(static_harness.get(field), expected, f"static.{field}")
    static_authority = require_object(static_harness.get("authorization"), "static.authorization")
    for field in (
        "socketCreationAllowed",
        "runtimeNetworkIOAllowed",
        "harnessNetworkIOAllowed",
        "controlledSpikeNetworkIOAllowed",
        "controlledSpikeSocketExecutionAuthorized",
        "phaseBExecutionAuthorized",
        "phaseBNetworkIOAllowed",
        "phaseBSocketExecutionAuthorized",
        "phaseBExternalEgressAllowed",
        "productionNetworkIOAllowed",
        "productionDeploymentAuthorized",
    ):
        recursive_exact(static_authority.get(field), False, f"static.authorization.{field}")


def validate_document(document: Any) -> None:
    if semantic_digest(document) != EXPECTED_SEMANTIC_SHA256:
        fail("progress-v1: canonical schema or value drifted")
    recursive_exact(document, EXPECTED_DOCUMENT, "progress-v1")
    if list(document["evidenceStatus"]) != list(EVIDENCE_ORDER):
        fail("progress-v1.evidenceStatus: canonical evidence order drifted")
    bounded_statuses = [
        document["evidenceStatus"][evidence_id]["status"]
        for evidence_id in EVIDENCE_ORDER[:-1]
    ]
    completed_count = sum(
        status in {"completed_bounded_no_device_vectors", "static_design_complete"}
        for status in bounded_statuses
    )
    blocked_count = sum(status.startswith("blocked_") for status in bounded_statuses)
    summary = document["statusSummary"]
    if summary["requiredBoundedEvidenceGroupCount"] != len(bounded_statuses):
        fail("progress-v1.statusSummary: bounded evidence requirement count drifted")
    if summary["boundedEvidenceCompletedCount"] != completed_count:
        fail("progress-v1.statusSummary: bounded completion count drifted")
    if summary["blockedBoundedEvidenceCount"] != blocked_count:
        fail("progress-v1.statusSummary: bounded blocker count drifted")


def qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def validate_ast_source(raw: str, label: str) -> None:
    try:
        tree = ast.parse(raw, filename=label)
    except SyntaxError as error:
        fail(f"{label}: invalid Python syntax: {error}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    fail(f"{label}:{node.lineno}: import outside static allowlist {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            allowed_names = ALLOWED_FROM_IMPORTS.get(module, set())
            if not allowed_names or any(
                alias.name == "*" or alias.name not in allowed_names for alias in node.names
            ):
                fail(f"{label}:{node.lineno}: import outside static allowlist {module}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in FORBIDDEN_NAMES:
                fail(f"{label}:{node.lineno}: forbidden dynamic reference {node.id}")
        elif isinstance(node, ast.Attribute):
            name = qualified_name(node)
            final_name = name.rsplit(".", 1)[-1] if name else ""
            if final_name in FORBIDDEN_DYNAMIC_ATTRIBUTE_NAMES:
                fail(f"{label}:{node.lineno}: forbidden dynamic attribute reference {name}")
            if final_name in FORBIDDEN_METHOD_NAMES:
                fail(f"{label}:{node.lineno}: forbidden capability reference {name}")
        elif isinstance(node, ast.Call):
            name = qualified_name(node.func)
            final_name = name.rsplit(".", 1)[-1] if name else ""
            if name is None:
                fail(f"{label}:{node.lineno}: dynamic call target is forbidden")
            if name in FORBIDDEN_NAMES or final_name in FORBIDDEN_METHOD_NAMES:
                fail(f"{label}:{node.lineno}: forbidden capability call {name}")


def validate_owned_python_ast() -> None:
    for path in (CHECKER_PATH, TEST_PATH):
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            fail(f"{path.relative_to(ROOT)}: {error}")
        validate_ast_source(raw, str(path.relative_to(ROOT)))


def validate_artifact_hashes() -> None:
    for path, digest in ARTIFACT_SHA256.items():
        validate_file_hash(path, digest)


def main() -> int:
    try:
        validate_artifact_hashes()
        validate_source_documents()
        validate_document(load_json(PROGRESS_PATH))
        validate_owned_python_ast()
    except PhaseAProgressValidationError as error:
        print(f"P2P/NAT Phase A progress validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "P2P/NAT Phase A progress validation passed "
        "(4 approvals; 2 bounded evidence complete; 2 blocked; whole review blocked; socket gate closed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
