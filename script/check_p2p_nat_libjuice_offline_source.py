#!/usr/bin/env python3
"""Validate the blocked Phase A libjuice offline-source intake contract."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_JSON_PATH = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/"
    "phase-a/offline-source-intake-v1.json"
)
ARTIFACT_MARKDOWN_PATH = ARTIFACT_JSON_PATH.with_suffix(".md")
SOURCE_REVIEW_PATH = ARTIFACT_JSON_PATH.parents[1] / "review-v1.json"
SOURCE_DECISION_PATH = ARTIFACT_JSON_PATH.parents[1] / "decision-v1.json"
SOURCE_HANDOFF_PATH = ARTIFACT_JSON_PATH.parents[2] / "implementation/handoff-v4.json"
CHECKER_PATH = ROOT / "script/check_p2p_nat_libjuice_offline_source.py"
TEST_PATH = ROOT / "script/test_p2p_nat_libjuice_offline_source.py"
EXPECTED_INTAKE_ROOT_RELATIVE = "build/offline-source/libjuice-1.7.2"
EXPECTED_INTAKE_ROOT = ROOT / EXPECTED_INTAKE_ROOT_RELATIVE

SOURCE_SHA256 = {
    SOURCE_REVIEW_PATH: "744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62",
    SOURCE_DECISION_PATH: "1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228",
    SOURCE_HANDOFF_PATH: "b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd",
}
ARTIFACT_SHA256 = {
    ARTIFACT_JSON_PATH: "3359624f1fa1474b2bfd2acd4e3591fd1e0a8cd5840cda4372327f25dfc68850",
    ARTIFACT_MARKDOWN_PATH: "c186c4bed45a6edd9d270062ac9927839ab1f5c8f5c66eab966dfc9a61c0d2ee",
}
EXPECTED_SEMANTIC_SHA256 = "9788f0a49e27c5074557c42e70075143eb62b07df8f37ea675979467032e7e52"

TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "artifactId", "profileId", "sourceReview",
    "sourceDecision", "sourceHandoff", "artifactStatus", "sourcePresence",
    "auditStatus", "compileStatus", "expectedIntakeRoot", "candidate",
    "authorization", "intakePolicy", "requiredFutureLayout",
    "requiredFutureProvenanceSchema", "currentEvidence", "limits",
    "failurePolicy", "immutability",
}

EXPECTED_AUTHORIZATION = {
    "offlineInspectionAuthorized": True,
    "manualOfflineIntakeAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "urlFetchAllowed": False,
    "redirectFollowingAllowed": False,
    "packageManagerAcquisitionAllowed": False,
    "sourceExecutionAllowed": False,
    "buildExecutionAllowedBeforeReviewedManifest": False,
    "compileExecutionAllowedBeforeReviewedManifest": False,
    "processLaunchAllowed": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIOAllowed": False,
    "dynamicImportAllowed": False,
}

EXPECTED_INTAKE_POLICY = {
    "discoveryMode": "exact_paths_only_no_glob_or_recursive_discovery",
    "rootPresentDisposition": "fail_closed_require_new_reviewed_versioned_manifest",
    "checkerRootBehavior": "reject_without_reading_or_consuming_present_root",
    "absolutePathsAllowed": False,
    "parentTraversalAllowed": False,
    "backslashPathsAllowed": False,
    "emptyPathSegmentsAllowed": False,
    "symlinksAllowed": False,
    "hardlinksAllowed": False,
    "specialFilesAllowed": False,
    "archiveExtractionByCheckerAllowed": False,
    "generatedManifestByCheckerAllowed": False,
}

EXPECTED_LAYOUT = {
    "originalArchive": "original/libjuice-1.7.2.tar.gz",
    "extractedSource": "source",
    "sourceProvenance": "source-provenance.json",
}

EXPECTED_CURRENT_EVIDENCE = {
    "commitSha1": None,
    "originalArchiveSha256": None,
    "extractedTreeSha256": None,
    "fileDigestSetSha256": None,
    "sourceProvenanceSha256": None,
    "licenseReviewResult": None,
    "generatedFileReviewResult": None,
    "dependencyReviewResult": None,
    "androidBuildFlags": None,
    "macosBuildFlags": None,
}

EXPECTED_LIMITS = {
    "maximumArchiveBytes": 16777216,
    "maximumExtractedBytes": 67108864,
    "maximumRegularFiles": 4096,
    "maximumSingleFileBytes": 8388608,
    "maximumRelativePathUtf8Bytes": 240,
    "maximumPathDepth": 16,
    "maximumLicenseFiles": 64,
    "maximumGeneratedFileRecords": 4096,
    "maximumDirectDependencies": 64,
    "maximumTransitiveDependencies": 256,
    "maximumBuildArgumentsPerPlatform": 256,
    "maximumBuildArgumentUtf8Bytes": 1024,
}

REVIEW_AUTHORIZATION = {
    "librarySelectionAuthorized": False,
    "harnessImplementationAuthorized": False,
    "networkIOAllowed": False,
    "socketExecutionAuthorized": False,
    "productionDeploymentAuthorized": False,
    "nextHandoffAuthorized": False,
}

DECISION_AUTHORIZATION = {
    "conditionalLibrarySelectionAuthorized": True,
    "offlineSourceInspectionAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "compileOnlyIntegrationAuthorized": True,
    "phaseAHarnessImplementationAuthorized": True,
    "controlledSpikeNetworkIOAllowed": False,
    "controlledSpikeSocketExecutionAuthorized": False,
    "phaseBExecutionAuthorized": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
    "handoffV4CreationAuthorized": True,
}

HANDOFF_AUTHORIZATION = {
    "implementationAuthorized": True,
    "conditionalLibrarySelectionAuthorized": True,
    "offlineSourceInspectionAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "compileOnlyIntegrationAuthorized": True,
    "phaseAHarnessImplementationAuthorized": True,
    "controlledSpikeNetworkIOAllowed": False,
    "controlledSpikeSocketExecutionAuthorized": False,
    "phaseBExecutionAuthorized": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
}

HANDOFF_PHASE_A = {
    "sourceMaterialMode": "offline_user_provided_or_preexisting_workspace_only",
    "offlineSourceInspectionAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "compileOnlyIntegrationAuthorized": True,
    "sessionCryptoVectorImplementationAuthorized": True,
    "staticHarnessImplementationAuthorized": True,
    "sourceExecutionAllowed": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIOAllowed": False,
    "harnessNetworkIOAllowed": False,
    "outputs": [
        "pinned_source_and_supply_chain_manifest",
        "line_referenced_source_audit",
        "android_macos_compile_only_logs",
        "cross_platform_session_crypto_vectors",
        "static_harness_and_egress_policy_evidence",
    ],
}

ALLOWED_IMPORTS = {"ast", "copy", "hashlib", "json", "stat", "sys", "unittest"}
ALLOWED_FROM_IMPORTS = {
    "__future__": {"annotations"},
    "pathlib": {"Path", "PurePosixPath"},
    "typing": {"Any"},
    "script": {
        "check_p2p_nat_libjuice_offline_source",
        "check_p2p_nat_security_design",
    },
}
FORBIDDEN_DYNAMIC_NAMES = {
    "__builtins__", "__import__", "eval", "exec", "compile", "getattr",
    "globals", "locals", "vars", "setattr", "delattr", "open",
}
FORBIDDEN_CALL_NAMES = {
    "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
    "spawn", "Popen", "run", "call", "check_call", "check_output", "urlopen",
    "urlretrieve", "request", "connect", "connect_ex", "bind", "listen", "accept",
    "send", "sendall", "sendto", "recv", "recvfrom", "create_connection",
    "create_subprocess_exec", "create_subprocess_shell", "import_module", "glob",
    "rglob", "iglob", "unpack_archive", "make_archive", "extract", "extractall",
    "write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "replace",
    "chmod", "symlink_to", "hardlink_to", "link_to", "open", "rmdir",
    "rmtree", "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp",
    "execvpe", "fork_exec",
}
FORBIDDEN_QUALIFIED_REFERENCES = {"sys.modules"}


class OfflineSourceValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise OfflineSourceValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object contains duplicate name {key!r}")
        result[key] = value
    return result


def reject_nonstandard_number(value: str) -> None:
    fail(f"JSON contains non-standard number {value!r}")


def parse_json(raw: str, label: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=reject_duplicate_names,
            parse_constant=reject_nonstandard_number,
        )
    except json.JSONDecodeError as error:
        fail(f"{label}: invalid JSON: {error}")


def load_json(path: Path) -> Any:
    try:
        return parse_json(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
    except (OSError, UnicodeError) as error:
        fail(f"{path.relative_to(ROOT)}: {error}")


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label}: expected object, got {type(value).__name__}")
    actual = set(value)
    if actual != expected:
        fail(
            f"{label}: keys differ; missing={sorted(expected - actual)} "
            f"unknown={sorted(actual - expected)}"
        )
    return value


def recursive_exact(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected):
        fail(f"{label}: expected exact type {type(expected).__name__}, got {type(actual).__name__}")
    if isinstance(expected, dict):
        exact_keys(actual, set(expected), label)
        for key, expected_value in expected.items():
            recursive_exact(actual[key], expected_value, f"{label}.{key}")
        return
    if isinstance(expected, list):
        if len(actual) != len(expected):
            fail(f"{label}: expected exactly {len(expected)} entries, got {len(actual)}")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            recursive_exact(actual_item, expected_item, f"{label}[{index}]")
        return
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_bytes_hash(raw: bytes, expected: str, label: str) -> None:
    actual = hash_bytes(raw)
    if actual != expected:
        fail(f"{label}: SHA-256 drifted; expected {expected}, got {actual}")


def validate_file_hash(path: Path, expected: str) -> None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        fail(f"{path.relative_to(ROOT)}: {error}")
    validate_bytes_hash(raw, expected, str(path.relative_to(ROOT)))


def validate_source_documents() -> None:
    for path, digest in SOURCE_SHA256.items():
        validate_file_hash(path, digest)

    review = load_json(SOURCE_REVIEW_PATH)
    recursive_exact(
        review.get("reviewId"),
        "production_p2p_nat_v1_controlled_network_spike_review_v1",
        "review.reviewId",
    )
    recursive_exact(review.get("authorization"), REVIEW_AUTHORIZATION, "review.authorization")

    decision = load_json(SOURCE_DECISION_PATH)
    recursive_exact(
        decision.get("decisionId"),
        "production_p2p_nat_v1_controlled_network_spike_decision_v1",
        "decision.decisionId",
    )
    recursive_exact(
        decision.get("decisionScope"),
        "bounded_phase_a_evidence_authorization",
        "decision.decisionScope",
    )
    recursive_exact(decision.get("authorization"), DECISION_AUTHORIZATION, "decision.authorization")

    handoff = load_json(SOURCE_HANDOFF_PATH)
    recursive_exact(
        handoff.get("handoffId"),
        "production_p2p_nat_v1_handoff_v4",
        "handoff.handoffId",
    )
    recursive_exact(handoff.get("authorization"), HANDOFF_AUTHORIZATION, "handoff.authorization")
    packages = handoff.get("packages")
    if not isinstance(packages, list):
        fail("handoff.packages: expected list")
    controlled = [
        item for item in packages
        if isinstance(item, dict) and item.get("packageId") == "controlled-network-spike"
    ]
    if len(controlled) != 1:
        fail("handoff.packages: expected exactly one controlled-network-spike package")
    recursive_exact(controlled[0].get("phaseA"), HANDOFF_PHASE_A, "handoff.controlled.phaseA")


def validate_repo_relative_path(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        fail(f"{label}: expected non-empty string")
    if "\\" in value or "\x00" in value:
        fail(f"{label}: backslash or NUL prohibited")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        fail(f"{label}: empty, dot, or parent segment prohibited")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or len(parsed.parts) != len(segments):
        fail(f"{label}: normalized repo-relative POSIX path required")
    if len(value.encode("utf-8")) > EXPECTED_LIMITS["maximumRelativePathUtf8Bytes"]:
        fail(f"{label}: path exceeds fixed UTF-8 byte limit")
    if len(segments) > EXPECTED_LIMITS["maximumPathDepth"]:
        fail(f"{label}: path exceeds fixed depth limit")
    return value


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
        fail(f"artifact: cannot canonicalize strict JSON value: {error}")
    return hash_bytes(canonical)


def validate_document(document: Any) -> None:
    root = exact_keys(document, TOP_LEVEL_KEYS, "artifact")
    actual_semantic_digest = semantic_digest(root)
    if actual_semantic_digest != EXPECTED_SEMANTIC_SHA256:
        fail(
            "artifact: canonical schema or value drifted; "
            f"expected semantic SHA-256 {EXPECTED_SEMANTIC_SHA256}, got {actual_semantic_digest}"
        )
    recursive_exact(
        root["documentType"],
        "aetherlink.p2p-nat-phase-a-offline-source-intake",
        "artifact.documentType",
    )
    recursive_exact(root["schemaVersion"], "1.0", "artifact.schemaVersion")
    recursive_exact(
        root["artifactId"],
        "production_p2p_nat_v1_phase_a_libjuice_offline_source_intake_v1",
        "artifact.artifactId",
    )
    recursive_exact(root["profileId"], "production_p2p_nat_v1_recommended", "artifact.profileId")
    recursive_exact(root["artifactStatus"], "blocked_missing_offline_source", "artifact.artifactStatus")
    recursive_exact(root["sourcePresence"], "absent", "artifact.sourcePresence")
    recursive_exact(root["auditStatus"], "not_started", "artifact.auditStatus")
    recursive_exact(root["compileStatus"], "not_started", "artifact.compileStatus")
    recursive_exact(
        root["expectedIntakeRoot"],
        EXPECTED_INTAKE_ROOT_RELATIVE,
        "artifact.expectedIntakeRoot",
    )
    recursive_exact(root["authorization"], EXPECTED_AUTHORIZATION, "artifact.authorization")
    recursive_exact(root["intakePolicy"], EXPECTED_INTAKE_POLICY, "artifact.intakePolicy")
    recursive_exact(root["requiredFutureLayout"], EXPECTED_LAYOUT, "artifact.requiredFutureLayout")
    recursive_exact(root["currentEvidence"], EXPECTED_CURRENT_EVIDENCE, "artifact.currentEvidence")
    recursive_exact(root["limits"], EXPECTED_LIMITS, "artifact.limits")

    recursive_exact(root["candidate"]["candidateId"], "libjuice-1.7.2-static-c-abi", "artifact.candidate.candidateId")
    recursive_exact(root["candidate"]["version"], "1.7.2", "artifact.candidate.version")
    recursive_exact(root["candidate"]["releaseTag"], "v1.7.2", "artifact.candidate.releaseTag")
    recursive_exact(root["candidate"]["commitSha1"], None, "artifact.candidate.commitSha1")
    recursive_exact(
        root["candidate"]["officialUrlUse"],
        "provenance_metadata_only_no_fetch",
        "artifact.candidate.officialUrlUse",
    )

    validate_repo_relative_path(root["expectedIntakeRoot"], "artifact.expectedIntakeRoot")
    for key, value in root["requiredFutureLayout"].items():
        validate_repo_relative_path(value, f"artifact.requiredFutureLayout.{key}")

    future = root["requiredFutureProvenanceSchema"]
    recursive_exact(future["commitSha1"]["currentValue"], None, "future.commitSha1.currentValue")
    recursive_exact(future["originalArchive"]["sha256"], None, "future.originalArchive.sha256")
    recursive_exact(future["extractedSource"]["treeSha256"], None, "future.extractedSource.treeSha256")
    recursive_exact(future["fileDigests"]["sha256"], None, "future.fileDigests.sha256")
    recursive_exact(future["licenseReview"]["fileSha256"], None, "future.licenseReview.fileSha256")
    recursive_exact(future["generatedFiles"]["sha256"], None, "future.generatedFiles.sha256")
    recursive_exact(future["dependencies"]["sourceSha256"], None, "future.dependencies.sourceSha256")

def validate_intake_root_absent(path: Path = EXPECTED_INTAKE_ROOT) -> None:
    if path.is_symlink() or path.exists():
        fail(
            f"{path}: offline source root is present; refusing to consume it; "
            "a new reviewed versioned manifest is required"
        )


def validate_intake_ancestor_values(
    label: str,
    mode: int,
    uid: int,
    expected_uid: int,
) -> None:
    if not stat.S_ISDIR(mode):
        fail(f"{label}: offline source intake ancestor must be a directory")
    if uid != expected_uid:
        fail(f"{label}: offline source intake ancestor owner drifted")
    if mode & 0o022:
        fail(f"{label}: group/world-writable offline source intake ancestor prohibited")


def validate_intake_ancestor_metadata(path: Path, expected_uid: int) -> None:
    if path.is_symlink():
        fail(f"{path}: symlink ancestor prohibited for offline source intake")
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    validate_intake_ancestor_values(str(path), metadata.st_mode, metadata.st_uid, expected_uid)


def validate_expected_intake_ancestors() -> None:
    expected_uid = Path.home().lstat().st_uid
    validate_intake_ancestor_metadata(ROOT, expected_uid)
    current = ROOT
    for segment in EXPECTED_INTAKE_ROOT_RELATIVE.split("/")[:-1]:
        current = current / segment
        validate_intake_ancestor_metadata(current, expected_uid)


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
            if node.id in FORBIDDEN_DYNAMIC_NAMES:
                fail(f"{label}:{node.lineno}: forbidden dynamic or capability reference {node.id}")
        elif isinstance(node, ast.Attribute):
            name = qualified_name(node)
            final_name = name.rsplit(".", 1)[-1] if name else ""
            if final_name in FORBIDDEN_CALL_NAMES or any(
                name == forbidden or name.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_QUALIFIED_REFERENCES
            ):
                fail(f"{label}:{node.lineno}: forbidden dynamic or capability reference {name}")
        elif isinstance(node, ast.Call):
            name = qualified_name(node.func)
            final_name = name.rsplit(".", 1)[-1] if name else ""
            if final_name in FORBIDDEN_CALL_NAMES:
                fail(f"{label}:{node.lineno}: forbidden network, process, execution, or discovery call {name}")


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
        validate_expected_intake_ancestors()
        validate_intake_root_absent(EXPECTED_INTAKE_ROOT)
        validate_source_documents()
        validate_document(load_json(ARTIFACT_JSON_PATH))
        validate_owned_python_ast()
        validate_artifact_hashes()
        validate_expected_intake_ancestors()
        validate_intake_root_absent(EXPECTED_INTAKE_ROOT)
    except OfflineSourceValidationError as error:
        print(f"P2P/NAT Phase A libjuice offline-source validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "P2P/NAT Phase A libjuice offline-source validation passed "
        "(blocked_missing_offline_source; source absent; audit not started; compile not started)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
