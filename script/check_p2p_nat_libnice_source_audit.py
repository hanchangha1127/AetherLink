#!/usr/bin/env python3
"""Validate the closed libnice intake, audit rejection, and authority boundary."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PHASE_A_ROOT = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a"
)
SPIKE_ROOT = PHASE_A_ROOT.parent
IMPLEMENTATION_ROOT = SPIKE_ROOT.parent / "implementation"

PATHS = {
    "libnice_manifest": PHASE_A_ROOT / "libnice-source-manifest-v1.json",
    "glib_manifest": PHASE_A_ROOT / "glib-source-manifest-v1.json",
    "audit": PHASE_A_ROOT / "libnice-source-audit-v1.json",
    "audit_md": PHASE_A_ROOT / "libnice-source-audit-v1.md",
    "intake": PHASE_A_ROOT / "offline-source-intake-v4.json",
    "intake_md": PHASE_A_ROOT / "offline-source-intake-v4.md",
    "closure": PHASE_A_ROOT / "libnice-dependency-closure-v3.json",
    "closure_md": PHASE_A_ROOT / "libnice-dependency-closure-v3.md",
    "decision": SPIKE_ROOT / "decision-v6.json",
    "decision_md": SPIKE_ROOT / "decision-v6.md",
    "handoff": IMPLEMENTATION_ROOT / "handoff-v9.json",
    "handoff_md": IMPLEMENTATION_ROOT / "handoff-v9.md",
    "progress": PHASE_A_ROOT / "progress-v8.json",
}

EXPECTED_SHA256 = {
    "libnice_manifest": "bacd979c0c2e60f6f374c7034cddc9377bdcaf038a7a08786d390e9f48201f2f",
    "glib_manifest": "a49ea1128e6644fa29b271be3a70a394e4a8dae554218ef40fe05d13f1756ec7",
    "audit": "2f76f43860e5967403ed2c6bbd7c59aa0b0babc0b5f64b2084b91dc763892ce7",
    "audit_md": "205882e1cc96d8a5057a48b230a27cc59a39725776c216010cf6f7ff1c3e1174",
    "intake": "507b75fc8003f8e73d307e4fb5eded8be5de29215220ce078a38047ea0fc677d",
    "intake_md": "6a2ff284501bcc4cc4c3e5b15f25ca2ec8181266c4762a07c62bad35f2305702",
    "closure": "d3dea4d275a689b98f8b848df1134d2078a3817f755b885225a0bf738c600968",
    "closure_md": "5c81e535acb43c0c853a27b35aaa58508e349de58eb39ef36a29eb1adca2ff1f",
    "decision": "65095344cbdc13445ef171562b4f60d2b1005d6feaf128d94660f1204c931755",
    "decision_md": "dd27231bf77119f47ce1901f4ac2faa6483390f9789a1cb2f1a5852a8d21e6e3",
    "handoff": "d1e2649504de1661b3184ce21ebfacfd9c38eb590b00e32ff755b77a0d66341d",
    "handoff_md": "c7aba9dde3b096238421788691e784f33f2902bdbeeccb6865eab7d53e9b47b8",
    "progress": "d83f81af28b03493ce47088e81a41a8ac73c722efd18e0f6b333b1b3c20f92a7",
}

TOP_LEVEL_KEYS = {
    "libnice_manifest": {
        "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
        "profileId", "candidate", "acquisition", "extraction", "sourceTree",
        "licenseReview", "buildInputReview", "dependencyReview", "authorityBoundary",
    },
    "glib_manifest": {
        "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
        "profileId", "dependency", "acquisition", "extraction", "sourceTree",
        "licenseReview", "generatedAndConfigureInputs", "targetPolicy",
        "transitiveDependencyReview", "authorityBoundary",
    },
    "audit": {
        "documentType", "schemaVersion", "auditId", "profileId", "recordedDate",
        "status", "scope", "sourceEvidence", "approvalChain", "governingContracts",
        "method", "supplyChainResult", "requiredTopicResults", "findings",
        "rejectionDecision", "compileBoundary", "networkBoundary", "evidenceBoundary",
        "immutability",
    },
    "intake": {
        "documentType", "schemaVersion", "artifactId", "profileId", "recordedDate",
        "artifactStatus", "supersedes", "consumedAuthority", "candidate", "intake",
        "reviewedArtifacts", "reviewResults", "auditFailure", "executionRecord",
        "currentAuthorization", "nextStep", "evidenceBoundary", "immutability",
    },
    "closure": {
        "documentType", "schemaVersion", "artifactId", "profileId", "recordedDate",
        "status", "supersedes", "sourceAudit", "completedPins",
        "identifiedButNotAcquired", "platformInputs", "compileOnlyPrerequisitesDisposition",
        "authorization", "nextStep", "evidenceBoundary", "immutability",
    },
    "decision": {
        "documentType", "schemaVersion", "decisionId", "profileId", "recordedDate",
        "status", "supersedes", "decisionBasis", "resolutions", "acquisitionClosure",
        "compileClosure", "authorization", "failurePolicySatisfaction", "nextDecision",
        "evidenceBoundary", "immutability",
    },
    "handoff": {
        "documentType", "schemaVersion", "handoffId", "profileId", "recordedDate",
        "status", "supersedes", "sourceDecision", "evidence",
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
    ("regular_nomination", "mechanism_pass"),
    ("role_handling_and_tie_breaker", "mechanism_pass_entropy_floor_fail"),
    ("rfc7675_consent_freshness", "fail_response_authentication_and_tuple_binding"),
    ("turn_authentication_nonce_and_redirect", "fail_automatic_unapproved_redirect"),
    ("stun_turn_parser_limits", "static_bounds_pass_runtime_not_proven"),
    ("cancellation_shutdown_and_callbacks", "fail"),
    ("content_free_diagnostics", "fail"),
    ("numeric_endpoint_pre_io_policy", "fail"),
    ("c_abi_allocator_callback_and_error_boundary", "fail_requires_new_source_or_private_internal_contract"),
]

FINDINGS = [
    ("LN0123-P1-ENTROPY", "P1"),
    ("LN0123-P1-SECRET-DIAGNOSTICS", "P1"),
    ("LN0123-P1-PRE-IO-REDIRECT", "P1"),
    ("LN0123-P1-CONSENT-BINDING", "P1"),
    ("LN0123-P2-STUN-RESOLVER-LIFETIME", "P2"),
    ("LN0123-P2-GRACEFUL-SHUTDOWN", "P2"),
    ("LN0123-P2-ABI-SURFACE", "P2"),
]

FORBIDDEN_IMPORTS = {
    "asyncio", "ctypes", "http", "importlib", "multiprocessing", "os",
    "requests", "shutil", "socket", "subprocess", "urllib",
}
FORBIDDEN_CALLS = {
    "__import__", "compile", "eval", "exec", "getattr", "open", "popen", "run",
    "system", "urlopen", "write_bytes", "write_text",
}


class LibniceAuditValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise LibniceAuditValidationError(message)


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


def exact_false_map(value: Any, label: str) -> None:
    if type(value) is not dict or not value:
        fail(f"{label}: expected non-empty object")
    for key, item in value.items():
        exact(item, False, f"{label}.{key}")


def validate_hashes() -> None:
    for name, expected in EXPECTED_SHA256.items():
        actual = hashlib.sha256(PATHS[name].read_bytes()).hexdigest()
        exact(actual, expected, f"{name} sha256")


def validate_libnice_manifest(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["libnice_manifest"], "libnice manifest")
    exact(root["manifestId"], "production_p2p_nat_v1_libnice_source_manifest_v1", "libnice manifest id")
    exact(root["candidate"]["releaseVersion"], "0.1.23", "libnice version")
    exact(root["acquisition"]["archive"]["sha256"], "618fc4e8de393b719b1641c1d8eec01826d4d39d15ade92679d221c7f5e4e70d", "libnice archive")
    exact(root["sourceTree"]["sha256"], "e594b0b2435e10a8df970304ba3dec24ea0353820f1eecb820a810ab56cd276a", "libnice tree")
    exact(root["extraction"]["regularFileCount"], 184, "libnice file count")
    exact(root["extraction"]["archiveMatchesExtractedFiles"], True, "libnice archive equivalence")
    exact(root["acquisition"]["detachedSignature"]["cryptographicVerificationStatus"], "not_verified_no_local_openpgp_verifier_or_trusted_signing_key", "libnice signature status")
    for key in ("symlinkCount", "hardlinkCount", "specialFileCount", "pathTraversalCount"):
        exact(root["extraction"][key], 0, f"libnice extraction.{key}")
    performed = {"sourceAcquisitionNetworkIOPerformed", "sourceInspectionPerformed"}
    for key, value in root["authorityBoundary"].items():
        exact(value, key in performed, f"libnice authorityBoundary.{key}")


def validate_glib_manifest(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["glib_manifest"], "glib manifest")
    exact(root["manifestId"], "production_p2p_nat_v1_glib_source_manifest_v1", "glib manifest id")
    exact(root["dependency"]["version"], "2.64.2", "glib version")
    exact(root["acquisition"]["archive"]["sha256"], "9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277", "glib archive")
    exact(root["sourceTree"]["sha256"], "1c36d535b42d89b62c375b60005dd3c073033ba5bb4928c6825c09a4bc61d3ac", "glib tree")
    exact(root["extraction"]["regularFileCount"], 1961, "glib file count")
    exact(root["extraction"]["archiveMatchesExtractedFiles"], True, "glib archive equivalence")
    exact(root["acquisition"]["officialChecksum"]["archiveEntryVerified"], True, "glib official checksum")
    for key in ("symlinkCount", "hardlinkCount", "specialFileCount", "pathTraversalCount"):
        exact(root["extraction"][key], 0, f"glib extraction.{key}")
    performed = {"sourceAcquisitionNetworkIOPerformed", "sourceInspectionPerformed"}
    for key, value in root["authorityBoundary"].items():
        exact(value, key in performed, f"glib authorityBoundary.{key}")


def validate_audit(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["audit"], "audit")
    exact(root["auditId"], "production_p2p_nat_v1_libnice_source_audit_v1", "audit id")
    exact(root["status"], "closed_rejected", "audit status")
    actual_topics = [(item["topic"], item["result"]) for item in root["requiredTopicResults"]]
    exact(actual_topics, AUDIT_TOPIC_RESULTS, "audit topics")
    actual_findings = [(item["findingId"], item["severity"]) for item in root["findings"]]
    exact(actual_findings, FINDINGS, "audit findings")
    exact(sum(1 for _, severity in actual_findings if severity == "P1"), 4, "audit P1 count")
    method = root["method"]
    for key, value in method.items():
        if key in {"reviewMode", "independentReviewModel"}:
            continue
        exact(value, 2 if key == "independentReviewCount" else False, f"audit method.{key}")
    exact(method["independentReviewModel"], "gpt-5.6-sol", "audit review model")
    supply = root["supplyChainResult"]
    exact(supply["minimumDependencySetIdentified"], True, "dependency set identification")
    exact(supply["pendingSourcesAcquired"], False, "pending source acquisition")
    exact(len(supply["pendingSources"]), 4, "pending source count")
    rejection = root["rejectionDecision"]
    exact(rejection["outcome"], "rejected_before_compile", "audit outcome")
    exact(rejection["independentP1BlockerCount"], 4, "rejection P1 count")
    exact(rejection["wrapperOnlyMitigationSufficient"], False, "wrapper sufficiency")
    exact(rejection["sourceForkAuthorized"], False, "source fork authority")
    exact(rejection["compileEligibility"], False, "compile eligibility")
    exact(rejection["pendingDependencyAcquisitionAuthorized"], False, "pending acquisition authority")
    exact(rejection["fallbackSelected"], False, "fallback selection")
    exact(rejection["nextCandidate"], None, "next candidate")
    for key, value in root["compileBoundary"].items():
        if key != "reason":
            exact(value, False, f"audit compileBoundary.{key}")
    exact_false_map(root["networkBoundary"], "audit networkBoundary")


def validate_intake(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["intake"], "intake")
    exact(root["artifactStatus"], "closed_libnice_source_present_audit_rejected", "intake status")
    exact(root["candidate"]["selectionStatus"], "rejected_before_compile", "intake candidate")
    exact(root["consumedAuthority"]["allOneShotAuthorityConsumed"], True, "intake authority consumed")
    exact(root["consumedAuthority"]["additionalAcquisitionAuthorized"], False, "intake extra acquisition")
    failure = root["auditFailure"]
    exact(failure["candidateRejected"], True, "intake rejection")
    exact(failure["independentP1BlockerCount"], 4, "intake P1 count")
    for key in ("compileSkipped", "pendingDependencyAcquisitionSkipped"):
        exact(failure[key], True, f"intake {key}")
    for key in ("sourceForkAuthorized", "fallbackSelected"):
        exact(failure[key], False, f"intake {key}")
    exact_false_map(root["currentAuthorization"], "intake currentAuthorization")
    execution = root["executionRecord"]
    expected_true = {
        "approvedArtifactAcquisitionNetworkIOPerformed",
        "archiveReadAndExtractionPerformed",
        "sourceInspectionPerformed",
    }
    for key, value in execution.items():
        if key == "approvedRequestCount":
            exact(value, 4, "intake request count")
        elif key == "measurements":
            exact(value, [], "intake measurements")
        else:
            exact(value, key in expected_true, f"intake execution.{key}")


def validate_closure(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["closure"], "closure")
    exact(root["status"], "closed_candidate_rejected_no_pending_source_intake", "closure status")
    exact(root["sourceAudit"]["outcome"], "rejected_before_compile", "closure audit outcome")
    exact([(item["name"], item["version"]) for item in root["completedPins"]], [("libnice", "0.1.23"), ("GLib", "2.64.2")], "completed pins")
    pending = [(item["name"], item["proposedVersion"]) for item in root["identifiedButNotAcquired"]]
    exact(pending, [("libffi", "3.7.1"), ("GNU libiconv", "1.19"), ("proxy-libintl", "0.1"), ("OpenSSL", "3.5.7-LTS")], "pending dependency plan")
    for item in root["identifiedButNotAcquired"]:
        if not item["status"].startswith("cancelled_before_"):
            fail("pending dependency status must remain cancelled before acquisition")
    exact_false_map(root["authorization"], "closure authorization")
    for value in root["compileOnlyPrerequisitesDisposition"].values():
        if "candidate_rejected" not in value:
            fail("compile-only prerequisite must remain closed by candidate rejection")


def validate_decision(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["decision"], "decision")
    exact(root["status"], "closed_libnice_rejected_no_networking_candidate", "decision status")
    exact(root["decisionBasis"]["newUserSelectionClaimed"], False, "decision selection claim")
    exact(root["resolutions"][0]["resolution"], "rejected_before_compile", "libnice resolution")
    exact(root["resolutions"][1]["resolution"], "unresolved_no_candidate_selected", "library resolution")
    exact(root["acquisitionClosure"]["pendingFourDependencySourcesAcquired"], False, "decision pending acquisition")
    exact(root["acquisitionClosure"]["additionalSourceAcquisitionAuthorized"], False, "decision acquisition authority")
    exact_false_map(root["compileClosure"], "decision compileClosure")
    for key, value in root["authorization"].items():
        exact(value, key == "handoffV9CreationAuthorized", f"decision authorization.{key}")
    failure = root["failurePolicySatisfaction"]
    exact(failure["failedCandidateRejected"], True, "failure policy rejection")
    for key, value in failure.items():
        if key != "failedCandidateRejected":
            exact(value, False, f"failure policy.{key}")
    next_decision = root["nextDecision"]
    for key in ("required", "requiresNewVersionedLibraryReview", "requiresExplicitUserApproval"):
        exact(next_decision[key], True, f"nextDecision.{key}")
    for key in ("mayReuseRejectedCandidateAuthority", "mayAuthorizeCompilerWithoutNewSourceAudit", "mayAuthorizeSourceExecution", "mayAuthorizeSocketOrRuntimeNetwork", "mayAuthorizePhaseBOrProduction"):
        exact(next_decision[key], False, f"nextDecision.{key}")


def validate_handoff(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["handoff"], "handoff")
    exact(root["status"], "closed_libnice_rejected_no_library_authority", "handoff status")
    disposition = root["networkingLibraryDisposition"]
    exact(disposition["latestRejectedCandidate"], "libnice-0.1.23-glib-c-abi", "handoff candidate")
    exact(disposition["latestRejectionStage"], "source_audit_before_compile", "handoff rejection stage")
    exact(disposition["latestIndependentP1BlockerCount"], 4, "handoff P1 count")
    exact(disposition["selectedCandidate"], None, "handoff selected candidate")
    exact(disposition["nextCandidate"], None, "handoff next candidate")
    exact_false_map(root["authorization"], "handoff authorization")
    expected_true = {"approvedArtifactAcquisitionNetworkIOPerformed", "sourceInspectionPerformed"}
    for key, value in root["executionRecord"].items():
        if key == "measurements":
            exact(value, [], "handoff measurements")
        else:
            exact(value, key in expected_true, f"handoff execution.{key}")
    next_handoff = root["nextHandoff"]
    exact(next_handoff["creationAuthorized"], False, "next handoff authority")
    exact(next_handoff["requiresNewVersionedLibraryReview"], True, "next handoff review")
    exact(next_handoff["requiresExplicitUserDecision"], True, "next handoff decision")
    exact(next_handoff["rejectedAuthorityMayBeReused"], False, "rejected authority reuse")
    exact(next_handoff["compilerSocketRuntimePhaseBOrProductionAuthorityAllowed"], False, "next handoff execution authority")


def validate_progress(root: dict[str, Any]) -> None:
    exact_keys(root, TOP_LEVEL_KEYS["progress"], "progress")
    exact(root["status"], "blocked_no_networking_library_candidate", "progress status")
    summary = root["summary"]
    exact(summary["rejectedNetworkingCandidateCount"], 2, "progress rejected count")
    exact(summary["latestCandidateDisposition"], "rejected_before_compile", "progress latest disposition")
    exact(summary["selectedNetworkingLibrary"], None, "progress selected library")
    statuses = {key: value["status"] for key, value in root["evidenceUnits"].items()}
    exact(statuses, {
        "libnice_supply_chain_dependency_and_source_audit": "complete_rejected",
        "pending_dependency_source_intake": "not_run_candidate_rejected",
        "android_macos_compile_only_integration": "not_run_candidate_rejected_before_compile",
        "cross_platform_session_crypto_vectors": "complete",
        "static_harness_and_egress_policy": "complete_static_only",
    }, "progress evidence statuses")
    exact_false_map(root["authorization"], "progress authorization")
    expected_true = {"approvedArtifactAcquisitionNetworkIOPerformed", "sourceInspectionPerformed"}
    for key, value in root["executionRecord"].items():
        if key == "measurements":
            exact(value, [], "progress measurements")
        else:
            exact(value, key in expected_true, f"progress execution.{key}")
    exact(root["nextStep"]["state"], "waiting_for_new_versioned_networking_library_review", "progress next state")
    for key, value in root["nextStep"].items():
        if key != "state":
            exact(value, False, f"progress nextStep.{key}")


def validate_cross_references(documents: dict[str, dict[str, Any]]) -> None:
    expected = EXPECTED_SHA256
    audit = documents["audit"]
    exact(audit["sourceEvidence"]["libniceManifest"]["sha256"], expected["libnice_manifest"], "audit libnice manifest ref")
    exact(audit["sourceEvidence"]["glibManifest"]["sha256"], expected["glib_manifest"], "audit glib manifest ref")
    exact(documents["intake"]["reviewedArtifacts"]["sourceAudit"]["sha256"], expected["audit"], "intake audit ref")
    exact(documents["closure"]["sourceAudit"]["sha256"], expected["audit"], "closure audit ref")
    exact(documents["decision"]["decisionBasis"]["sourceAudit"]["sha256"], expected["audit"], "decision audit ref")
    exact(documents["decision"]["decisionBasis"]["completedIntake"]["sha256"], expected["intake"], "decision intake ref")
    exact(documents["decision"]["decisionBasis"]["closedDependencyClosure"]["sha256"], expected["closure"], "decision closure ref")
    exact(documents["handoff"]["sourceDecision"]["sha256"], expected["decision"], "handoff decision ref")
    exact(documents["progress"]["currentAuthority"]["decision"]["sha256"], expected["decision"], "progress decision ref")
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
    validate_libnice_manifest(documents["libnice_manifest"])
    validate_glib_manifest(documents["glib_manifest"])
    validate_audit(documents["audit"])
    validate_intake(documents["intake"])
    validate_closure(documents["closure"])
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
    except (OSError, UnicodeError, LibniceAuditValidationError) as error:
        print(f"P2P/NAT libnice source-audit validation failed: {error}", file=sys.stderr)
        return 1
    print("P2P/NAT libnice source-audit rejection validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
