#!/usr/bin/env python3
"""Validate the closed libjuice intake, rejection, and fallback boundary."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PHASE_A_ROOT = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a"
)
SPIKE_ROOT = PHASE_A_ROOT.parent
IMPLEMENTATION_ROOT = SPIKE_ROOT.parent / "implementation"

PATHS = {
    "manifest": PHASE_A_ROOT / "libjuice-source-manifest-v1.json",
    "audit": PHASE_A_ROOT / "libjuice-source-audit-v1.json",
    "audit_md": PHASE_A_ROOT / "libjuice-source-audit-v1.md",
    "intake": PHASE_A_ROOT / "offline-source-intake-v2.json",
    "intake_md": PHASE_A_ROOT / "offline-source-intake-v2.md",
    "review": SPIKE_ROOT / "review-v2.json",
    "review_md": SPIKE_ROOT / "review-v2.md",
    "decision": SPIKE_ROOT / "decision-v3.json",
    "decision_md": SPIKE_ROOT / "decision-v3.md",
    "handoff": IMPLEMENTATION_ROOT / "handoff-v6.json",
    "handoff_md": IMPLEMENTATION_ROOT / "handoff-v6.md",
    "progress": PHASE_A_ROOT / "progress-v3.json",
}

EXPECTED_SHA256 = {
    "manifest": "55209e8629c25e0a0158233e47dee8537250a5b44af8a841e0cff07f0af41046",
    "audit": "614adb3ff5d87623b5e9db0f143ce82e3618316b3310ad70750b2806517e8145",
    "audit_md": "b7605889ad0a77d49380776ffc0269567454f9e74e6f0c2f6c82fe74ff522cdc",
    "intake": "1c1b5ebc47ce15456b3855c008db2aaf5289d38635a78a566cfabc25e2cd8fa0",
    "intake_md": "5d5425ca996fc417bbe2821d194171e2829cbef690c1d8a69f7044026139a4eb",
    "review": "d20c9ddcf572edbfeb8df3bf899cb32f0f61c684974ea074f7ed841332c4122b",
    "review_md": "02f2788fe51487b8a02329fd3acc38675093f2c496b26bb18745d32640e9207d",
    "decision": "ae129fc214ac96abb3e1393b895cf03ddf284004ce9a1d3ac2005b4cb5d2022d",
    "decision_md": "bf4e3595e63d6b3060f886d90a30812e7e662eccd63e07119765efe630c90801",
    "handoff": "87af07548bfeb17b54642bb16c00fab2652006ba9401a05ccce8d134bba894e5",
    "handoff_md": "2c3ab05ea7a8fd8872e2051ddc50907505bc9a6a4f10307c59be436f3619e3e5",
    "progress": "22a285b0de28f593f39f6b2a3f43e2966f97e711dd97c6bfc240325c88827db8",
}

TOP_LEVEL_KEYS = {
    "manifest": {
        "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
        "profileId", "candidate", "acquisition", "extraction", "sourceTree",
        "licenseReview", "generatedFileReview", "buildInputReview", "dependencyReview",
        "toolchainReceipt", "authorityBoundary",
    },
    "audit": {
        "documentType", "schemaVersion", "auditId", "profileId", "recordedDate",
        "status", "scope", "sourceManifest", "approvalChain", "governingContracts",
        "method", "requiredTopicResults", "findings", "rejectionDecision",
        "compileBoundary", "networkBoundary", "evidenceBoundary", "immutability",
    },
    "intake": {
        "documentType", "schemaVersion", "artifactId", "profileId", "recordedDate",
        "artifactStatus", "supersedes", "authority", "candidate", "intake",
        "reviewedArtifacts", "reviewResults", "toolchainReceipt", "auditFailure",
        "executionRecord", "currentAuthorization", "nextStep", "immutability",
    },
    "review": {
        "documentType", "schemaVersion", "reviewId", "profileId", "recordedDate",
        "status", "reviewOutcome", "supersedes", "triggerEvidence", "rejectedCandidate",
        "fallbackCandidate", "requiredBeforeSelection", "rejectionConditions",
        "authorization", "measurementStatus", "unchangedApprovedPhaseAUnits",
        "nextDecision", "immutability",
    },
    "decision": {
        "documentType", "schemaVersion", "decisionId", "profileId", "recordedDate",
        "status", "supersedes", "decisionBasis", "resolutions", "acquisitionClosure",
        "compileClosure", "authorization", "failurePolicySatisfaction", "nextDecision",
        "immutability",
    },
    "handoff": {
        "documentType", "schemaVersion", "handoffId", "profileId", "recordedDate",
        "status", "supersedes", "sourceDecision", "evidence", "inheritedEvidence",
        "networkingLibraryDisposition", "phaseAStatus", "acquisitionReceipt",
        "authorization", "executionRecord", "nextHandoff", "evidenceBoundary",
        "immutability",
    },
    "progress": {
        "documentType", "schemaVersion", "artifactId", "profileId", "recordedDate",
        "status", "supersedes", "currentAuthority", "summary", "evidenceUnits",
        "acquisitionAndToolReceipt", "executionRecord", "authorization", "nextStep",
        "evidenceBoundary", "immutability",
    },
}

AUDIT_TOPIC_RESULTS = [
    ("regular_nomination", "mechanism_pass_profile_gate_fail"),
    ("role_handling_and_tie_breaker", "fail"),
    ("rfc7675_consent_freshness", "conditional_mechanism_pass_profile_gate_fail"),
    ("turn_authentication_nonce_and_redirect", "fail"),
    ("stun_turn_parser_limits", "fail_strict_encoding"),
    ("cancellation_shutdown_and_callbacks", "fail"),
    ("content_free_diagnostics", "fail"),
    ("numeric_endpoint_pre_io_policy", "fail"),
]

FINDINGS = [
    ("LJ172-P1-ENTROPY", "P1"),
    ("LJ172-P1-SECRET-LOG", "P1"),
    ("LJ172-P1-UNAUTH-STUN-ERROR", "P1"),
    ("LJ172-P1-TURN-REDIRECT", "P1"),
    ("LJ172-P1-PRE-IO-POLICY", "P1"),
    ("LJ172-P2-ROLE-FIELD", "P2"),
    ("LJ172-P2-TEARDOWN", "P2"),
    ("LJ172-P2-PRE-NOMINATION-PAYLOAD", "P2"),
]

FORBIDDEN_IMPORTS = {
    "asyncio", "ctypes", "http", "importlib", "multiprocessing", "os",
    "requests", "shutil", "socket", "subprocess", "urllib",
}
FORBIDDEN_CALLS = {
    "__import__", "compile", "eval", "exec", "getattr", "open", "popen", "run",
    "system", "urlopen", "write_bytes", "write_text",
}


class SourceAuditValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise SourceAuditValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON name {key!r}")
        result[key] = value
    return result


def reject_nonstandard_number(value: str) -> None:
    fail(f"non-standard JSON number {value!r}")


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
    return parse_json(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))


def exact(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        fail(f"{label}: expected exact {expected!r}, got {actual!r}")


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict:
        fail(f"{label}: expected object")
    if set(value) != expected:
        fail(f"{label}: keys differ")
    return value


def exact_false_map(value: Any, expected_keys: set[str], label: str) -> None:
    value = exact_keys(value, expected_keys, label)
    for key in expected_keys:
        exact(value[key], False, f"{label}.{key}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_hashes() -> None:
    for name, expected in EXPECTED_SHA256.items():
        actual = sha256_bytes(PATHS[name].read_bytes())
        exact(actual, expected, f"{name} sha256")


def validate_manifest(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["manifest"], "manifest")
    exact(root["manifestId"], "production_p2p_nat_v1_libjuice_source_manifest_v1", "manifest id")
    exact(root["status"], "complete_audit_input_rejected_for_compile", "manifest status")
    exact(root["candidate"]["commitSha1"], "3c40a3545b6b1b62c7adee7f8f2bd58aa290afd6", "commit")
    exact(root["acquisition"]["archive"]["sha256"], "75159867c4a5a689a6559e11aa0d30c9eba12ce73a4ae3d898b521467e1f635d", "archive")
    exact(root["extraction"]["regularFileCount"], 81, "file count")
    exact(root["extraction"]["archiveMatchesExtractedFiles"], True, "archive equivalence")
    for key in ("symlinkCount", "hardlinkCount", "specialFileCount", "pathTraversalCount"):
        exact(root["extraction"][key], 0, f"extraction.{key}")

    records = root["sourceTree"]["files"]
    if type(records) is not list or len(records) != 81:
        fail("manifest source records must contain exactly 81 entries")
    paths: list[str] = []
    digest = hashlib.sha256()
    for index, record in enumerate(records):
        exact_keys(record, {"path", "sizeBytes", "sha256"}, f"source record {index}")
        path = record["path"]
        if type(path) is not str or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            fail(f"source record {index} has unsafe path")
        if type(record["sizeBytes"]) is not int or record["sizeBytes"] < 0:
            fail(f"source record {index} has invalid size")
        if type(record["sha256"]) is not str or len(record["sha256"]) != 64:
            fail(f"source record {index} has invalid digest")
        paths.append(path)
        digest.update(path.encode("utf-8") + b"\0")
        digest.update(str(record["sizeBytes"]).encode("ascii") + b"\0")
        digest.update(record["sha256"].encode("ascii") + b"\n")
    exact(paths, sorted(set(paths), key=lambda value: value.encode("utf-8")), "source order")
    tree_digest = digest.hexdigest()
    exact(tree_digest, "c17e0d6d3855e9584718584ab644f030939448d0e8f6a8bf5ca9883da719a330", "tree digest")
    exact(root["sourceTree"]["sha256"], tree_digest, "recorded tree digest")
    exact(root["sourceTree"]["fileDigestSetSha256"], tree_digest, "file set digest")
    exact(root["toolchainReceipt"]["android"]["packageId"], "ndk;28.2.13676358", "NDK package")
    exact(root["toolchainReceipt"]["android"]["archive"]["sha256"], "0d4599e8bbf1a1668a0d51a541729b2246360f350018a2081d0b302dbb594f2a", "NDK archive")
    exact(root["buildInputReview"]["compilerInvocationAllowedByThisManifest"], False, "manifest compiler authority")
    exact(root["buildInputReview"]["archiveInvocationAllowedByThisManifest"], False, "manifest archive authority")
    exact(root["authorityBoundary"]["sourceInspectionPerformed"], True, "manifest inspection")
    for key, value in root["authorityBoundary"].items():
        if key != "sourceInspectionPerformed":
            exact(value, False, f"manifest authorityBoundary.{key}")


def validate_audit(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["audit"], "audit")
    exact(root["status"], "closed_rejected", "audit status")
    actual_topics = [(value["topic"], value["result"]) for value in root["requiredTopicResults"]]
    exact(actual_topics, AUDIT_TOPIC_RESULTS, "audit topics")
    actual_findings = [(value["findingId"], value["severity"]) for value in root["findings"]]
    exact(actual_findings, FINDINGS, "audit findings")
    exact(sum(1 for _, severity in actual_findings if severity == "P1"), 5, "P1 count")
    rejection = root["rejectionDecision"]
    exact(rejection["outcome"], "rejected_before_compile", "audit outcome")
    exact(rejection["wrapperOnlyMitigationSufficient"], False, "wrapper sufficiency")
    exact(rejection["sourceForkRequiredForRemediation"], True, "source fork need")
    exact(rejection["sourceForkAuthorized"], False, "source fork authority")
    exact(rejection["fallbackSelected"], False, "fallback selection")
    exact(rejection["fallbackAcquisitionAuthorized"], False, "fallback acquisition")
    for section in ("compileBoundary", "networkBoundary"):
        for key, value in root[section].items():
            if key == "reason":
                continue
            exact(value, False, f"audit {section}.{key}")
    method_true = {"independentReviewCount": 2}
    for key, value in root["method"].items():
        if key in ("reviewMode", "independentReviewModel"):
            continue
        if key in method_true:
            exact(value, method_true[key], f"audit method.{key}")
        else:
            exact(value, False, f"audit method.{key}")


def validate_intake(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["intake"], "intake")
    exact(root["artifactStatus"], "closed_source_present_audit_rejected", "intake status")
    exact(root["authority"]["authorizationWasExactOneShotAcquisition"], True, "one-shot authority")
    exact(root["authority"]["authorizationConsumed"], True, "authority consumed")
    exact(root["authority"]["additionalAcquisitionAuthorized"], False, "extra acquisition")
    exact(root["auditFailure"]["candidateRejected"], True, "candidate rejection")
    exact(root["auditFailure"]["independentP1BlockerCount"], 5, "intake P1 count")
    exact(root["auditFailure"]["compileSkipped"], True, "compile skipped")
    exact(root["auditFailure"]["fallbackSelected"], False, "fallback selection")
    exact_false_map(root["currentAuthorization"], set(root["currentAuthorization"]), "intake current authorization")
    performed_true = {
        "approvedArtifactAcquisitionNetworkIOPerformed",
        "archiveReadAndExtractionPerformed",
        "sourceInspectionPerformed",
    }
    for key, value in root["executionRecord"].items():
        exact(value, key in performed_true, f"intake execution.{key}")


def validate_review(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["review"], "review")
    exact(root["status"], "proposed_not_selected", "fallback review status")
    exact(root["fallbackCandidate"]["optionId"], "libnice-0.1.23-glib-c-abi", "fallback option")
    for key in ("selection", "acquisition", "implementation"):
        exact(root["fallbackCandidate"][key], None, f"fallback {key}")
    exact_false_map(root["authorization"], set(root["authorization"]), "fallback authorization")
    measurements = root["measurementStatus"]
    for key, value in measurements.items():
        exact(value, [] if key == "measurements" else False, f"measurement.{key}")
    exact(root["nextDecision"]["required"], True, "next decision required")
    exact(root["nextDecision"]["implicitApprovalAllowed"], False, "implicit approval")
    exact(root["nextDecision"]["networkSocketPhaseBOrProductionAuthorityAllowed"], False, "next authority")


def validate_decision(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["decision"], "decision")
    exact(root["status"], "closed_libjuice_rejected_fallback_unselected", "decision status")
    exact(root["decisionBasis"]["newUserSelectionClaimed"], False, "user selection claim")
    exact(root["resolutions"][0]["resolution"], "rejected_before_compile", "libjuice resolution")
    exact(root["resolutions"][1]["resolution"], "proposed_not_selected", "fallback resolution")
    for key, value in root["compileClosure"].items():
        exact(value, False, f"compile closure.{key}")
    authorization = root["authorization"]
    for key, value in authorization.items():
        exact(value, key == "handoffV6CreationAuthorized", f"decision authorization.{key}")
    for key, value in root["failurePolicySatisfaction"].items():
        expected = key in {"failedCandidateRejected", "fallbackReviewOpened"}
        exact(value, expected, f"failure policy.{key}")
    exact(root["nextDecision"]["requiresExplicitUserApproval"], True, "explicit next approval")
    for key in ("mayAuthorizeCompiler", "mayAuthorizeSourceExecution", "mayAuthorizeSocketOrRuntimeNetwork", "mayAuthorizePhaseBOrProduction"):
        exact(root["nextDecision"][key], False, f"next decision.{key}")


def validate_handoff(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["handoff"], "handoff")
    exact(root["status"], "closed_libjuice_rejected_no_fallback_authority", "handoff status")
    exact(root["networkingLibraryDisposition"]["rejectionStage"], "source_audit_before_compile", "rejection stage")
    exact(root["networkingLibraryDisposition"]["fallbackStatus"], "proposed_not_selected", "fallback status")
    exact_false_map(root["authorization"], set(root["authorization"]), "handoff authorization")
    execution = root["executionRecord"]
    for key, value in execution.items():
        expected: Any = True if key == "sourceInspectionPerformed" else ([] if key == "measurements" else False)
        exact(value, expected, f"handoff execution.{key}")
    exact(root["nextHandoff"]["creationAuthorized"], False, "next handoff")
    exact(root["nextHandoff"]["requiresExplicitUserDecision"], True, "next handoff approval")
    exact(root["nextHandoff"]["compilerSocketRuntimePhaseBOrProductionAuthorityAllowed"], False, "next handoff authority")


def validate_progress(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["progress"], "progress")
    exact(root["status"], "blocked_networking_candidate_rejected", "progress status")
    expected_summary = {
        "originalBoundedPhaseAApprovalCount": 4,
        "passedEvidenceUnitCount": 2,
        "rejectedEvidenceUnitCount": 1,
        "notRunEvidenceUnitCount": 1,
        "wholePhaseASecurityReview": "blocked_on_fallback_selection_and_evidence",
        "networkingCandidate": "libjuice-1.7.2-static-c-abi",
        "networkingCandidateDisposition": "rejected_before_compile",
        "fallbackCandidate": "libnice-0.1.23-glib-c-abi",
        "fallbackDisposition": "proposed_not_selected",
    }
    exact(root["summary"], expected_summary, "progress summary")
    statuses = {key: value["status"] for key, value in root["evidenceUnits"].items()}
    exact(
        statuses,
        {
            "libjuice_supply_chain_and_source_audit": "complete_rejected",
            "android_macos_compile_only_integration": "not_run_candidate_rejected_before_compile",
            "cross_platform_session_crypto_vectors": "complete",
            "static_harness_and_egress_policy": "complete_static_only",
        },
        "evidence statuses",
    )
    exact_false_map(root["authorization"], set(root["authorization"]), "progress authorization")
    performed_true = {"approvedArtifactAcquisitionNetworkIOPerformed", "sourceInspectionPerformed"}
    for key, value in root["executionRecord"].items():
        expected: Any = True if key in performed_true else ([] if key == "measurements" else False)
        exact(value, expected, f"progress execution.{key}")
    exact(root["nextStep"]["state"], "waiting_for_explicit_user_decision", "progress next state")
    for key in ("fallbackMayBeImplicitlySelected", "compilerMayBeAuthorizedByThatDecision", "socketRuntimePhaseBOrProductionAuthorityMayBeOpened"):
        exact(root["nextStep"][key], False, f"progress nextStep.{key}")


def validate_cross_references(documents: dict[str, dict[str, Any]]) -> None:
    expected = EXPECTED_SHA256
    exact(documents["audit"]["sourceManifest"]["sha256"], expected["manifest"], "audit manifest ref")
    exact(documents["intake"]["reviewedArtifacts"]["sourceAudit"]["sha256"], expected["audit"], "intake audit ref")
    exact(documents["review"]["triggerEvidence"]["completedIntake"]["sha256"], expected["intake"], "review intake ref")
    exact(documents["decision"]["decisionBasis"]["fallbackReview"]["sha256"], expected["review"], "decision review ref")
    exact(documents["handoff"]["sourceDecision"]["sha256"], expected["decision"], "handoff decision ref")
    exact(documents["progress"]["currentAuthority"]["handoff"]["sha256"], expected["handoff"], "progress handoff ref")


def validate_owned_ast(source: str | None = None) -> None:
    if source is None:
        source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    fail(f"forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in FORBIDDEN_IMPORTS:
                fail(f"forbidden from-import {node.module}")
        elif isinstance(node, ast.Call):
            target = node.func
            name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
            if name in FORBIDDEN_CALLS:
                fail(f"forbidden call {name}")


def load_documents() -> dict[str, dict[str, Any]]:
    return {name: load_json(PATHS[name]) for name in TOP_LEVEL_KEYS}


def validate_documents(documents: dict[str, dict[str, Any]]) -> None:
    exact_keys(documents, set(TOP_LEVEL_KEYS), "document set")
    validate_manifest(documents["manifest"])
    validate_audit(documents["audit"])
    validate_intake(documents["intake"])
    validate_review(documents["review"])
    validate_decision(documents["decision"])
    validate_handoff(documents["handoff"])
    validate_progress(documents["progress"])
    validate_cross_references(documents)


def main() -> int:
    try:
        documents = load_documents()
        validate_documents(documents)
        validate_owned_ast()
        validate_hashes()
    except (OSError, UnicodeError, SourceAuditValidationError) as error:
        print(f"P2P/NAT libjuice source-audit validation failed: {error}", file=sys.stderr)
        return 1
    print("P2P/NAT libjuice source-audit rejection validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
