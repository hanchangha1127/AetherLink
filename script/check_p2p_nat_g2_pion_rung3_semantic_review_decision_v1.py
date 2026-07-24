#!/usr/bin/env python3
"""Validate the tracked G2 Pion rung-three semantic-review v1 decision.

This checker reads only a fixed allowlist of tracked JSON files. It never reads
``build/`` or the retained archive and performs no writes, process execution,
network, device, or Git operation.
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
        raise RuntimeError("semantic-review decision check requires `python3 -I -B -S`")


require_isolated_interpreter()

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Mapping


ROOT = Path(os.path.abspath(__file__)).parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three"
DECISION_PATH = f"{BASE}/semantic-source-review-decision-v1.json"
RESULT_PATH = f"{BASE}/offline-source-review-result-v3.json"
RUNTIME_MANIFEST_PATH = f"{BASE}/offline-source-review-runtime-manifest-v3.json"
RECEIPT_PATH = f"{BASE}/offline-source-review-execution-receipt-v3.json"
PROGRESS_PATH = f"{BASE}/offline-source-review-progress-v4.json"
SUPERSESSION_PATH = f"{BASE}/canonical-document-supersession-v4.json"
MANIFEST_PATH = f"{BASE}/evidence-manifest-v11.json"

ALLOWED_PATHS = (
    DECISION_PATH,
    RESULT_PATH,
    RUNTIME_MANIFEST_PATH,
    RECEIPT_PATH,
    PROGRESS_PATH,
    SUPERSESSION_PATH,
    MANIFEST_PATH,
)
EXPECTED_RAW_SHA256 = {
    DECISION_PATH: "b65379bf0f97cd0558c93d818e5ecea14242a938ca5922796eb4a28f345e7cfc",
    RESULT_PATH: "ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933",
    RUNTIME_MANIFEST_PATH: "2dace9b59b7374423754f1f9a7345eda76db9130728d1c0579797e5a0c829055",
    RECEIPT_PATH: "dbb46cb6ffacbe14b15118488e07ea71ceb242f652dda17cc42b233f8c966d71",
    PROGRESS_PATH: "08fd7def7fc0c6f9623ffaaf8dbe5157f4128d228e16c55552f1e8a8613f0a10",
    SUPERSESSION_PATH: "5b7735f57a6e97f512d469e683ba6d86a0c195bc16168b56ad1f2ad381120f19",
    MANIFEST_PATH: "24cb2e406f0e8be7664eda6cf677a9034113712734a19c4a27aea94278ee0895",
}
EXPECTED_DECISION_CONTENT_SHA256 = (
    "09ccce7ae9b0893e30d4cbf2533e947623da70f56a499e5bdd2cd3e68bc3ef6b"
)
EXPECTED_ARCHIVE_SHA256 = "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
EXPECTED_SOURCE_TREE_SHA256 = (
    "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
)
EXPECTED_STATUS = "rung3_semantic_source_review_v1_decision_recorded_execution_not_started"
EXPECTED_RESULT = "canonical_v3_evidence_bound_full_semantic_review_execution_contract_recorded"
EXPECTED_NEXT_ACTION = "execute_rung3_semantic_source_review_v1"
PREDECESSOR_STATUS = "rung3_v3_publication_read_back_complete"
PREDECESSOR_NEXT_ACTION = "prepare_separate_versioned_rung3_semantic_source_review_decision"
MAX_TRACKED_FILE_BYTES = 4_194_304

EXPECTED_PATCH_UNITS = (
    (
        "split_egress_capability_and_ingress_admission_boundaries",
        606,
        "587bab19a6de8486e533694a29f4720ad4bea09b648f809d5e2dae8a0996ae4f",
        (("egress-dial", 87, 8, 79), ("egress-listen", 175, 8, 167), ("candidate-io", 344, 8, 336)),
    ),
    (
        "remove_secret_bearing_diagnostics",
        600,
        "7b6a25688527a8cc25d600058499eb65ee2a4ad44550ca3b4aab5a33b32e9b8a",
        (("diagnostic-call", 334, 8, 326), ("credential-token", 266, 8, 258)),
    ),
    (
        "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
        482,
        "fc5279c6e0ff47ffd6c5d285ec89724daef9b67010a1ff0eb34dd2c749e05d05",
        (("callback", 59, 8, 51), ("channel", 394, 8, 386), ("event", 29, 8, 21)),
    ),
    (
        "deadline_bounded_shutdown",
        1056,
        "f8c10189b96a8e335a2612e615567a7a5a17f2e7e9aec136fcabf797f1e851ad",
        (("deadline", 127, 8, 119), ("shutdown", 767, 8, 759), ("time-bound", 162, 8, 154)),
    ),
    (
        "disable_nonprofile_network_paths",
        1356,
        "f1189b22b6752fca8bcca9066d31d917004222cea0bfa5e30b92bdd081d1c299",
        (("transport-path", 839, 8, 831), ("network-type", 517, 8, 509)),
    ),
    (
        "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
        278,
        "ad83ba81c58c26e25f1a44b1da1e0d769a2b05bf790d8e5e5d1429b2be16d108",
        (("resolver", 14, 8, 6), ("turn-tls", 68, 8, 60), ("network-injection", 196, 8, 188)),
    ),
    (
        "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
        323,
        "103ba2454dc4b3156123dbeccdcb897b205d6adff35621d1947695a7f4a7fb39",
        (("pre-auth", 268, 8, 260), ("promotion-state", 55, 8, 47), ("one-use", 0, 0, 0)),
    ),
)
EXPECTED_VERIFICATION_IDS = (
    "g2-r3-egress-path-coverage",
    "g2-r3-ingress-path-coverage",
    "g2-r3-address-and-resolution-adversarial",
    "g2-r3-turn-tls-service-identity",
    "g2-r3-secure-session-promotion",
    "g2-r3-resource-and-event-bounds",
    "g2-r3-secret-free-diagnostics",
    "g2-r3-deadline-shutdown",
)
EXPECTED_PREDECESSORS = tuple(
    {"path": path, "rawSha256": EXPECTED_RAW_SHA256[path], "role": role}
    for path, role in (
        (RESULT_PATH, "canonical_lexical_result"),
        (RUNTIME_MANIFEST_PATH, "canonical_runtime_manifest"),
        (RECEIPT_PATH, "canonical_execution_receipt"),
        (PROGRESS_PATH, "canonical_current_progress"),
        (SUPERSESSION_PATH, "canonical_supersession"),
        (MANIFEST_PATH, "canonical_success_evidence_manifest"),
    )
)


class CheckError(ValueError):
    """The decision or its tracked predecessor evidence failed closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(type(value) is type(expected) and value == expected, f"{label}: mismatch")


def exact_object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict and set(value) == keys, f"{label}: exact schema mismatch")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite number")
    elif type(value) is list:
        for index, child in enumerate(value):
            reject_nonfinite(child, f"{label}[{index}]")
    elif type(value) is dict:
        for key, child in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(child, f"{label}.{key}")


def strict_json(data: bytes, label: str) -> Any:
    require(data.endswith(b"\n") and not data.endswith(b"\n\n") and b"\r" not in data, f"{label}: exact LF")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in items:
            require(key not in output, f"{label}: duplicate key")
            output[key] = value
        return output

    try:
        parsed = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CheckError(f"{label}: non-finite {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid JSON") from error
    reject_nonfinite(parsed, label)
    return parsed


def _safe_parts(path: str) -> tuple[str, ...]:
    require(path in ALLOWED_PATHS, f"unlisted tracked read: {path}")
    pure = PurePosixPath(path)
    require(
        not pure.is_absolute()
        and pure.parts
        and all(part not in ("", ".", "..") for part in pure.parts)
        and pure.as_posix() == path,
        f"unsafe tracked path: {path}",
    )
    require("build" not in pure.parts, f"build read forbidden: {path}")
    require(not path.casefold().endswith((".zip", ".tar", ".tgz", ".gz", ".7z")), f"archive read forbidden: {path}")
    require(not path.casefold().endswith((".md", ".markdown")), f"Markdown read forbidden: {path}")
    return pure.parts


def _metadata(value: os.stat_result) -> tuple[int, ...]:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_uid, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


class FixedTrackedReader:
    def __init__(self, root: Path):
        self.root = Path(os.path.abspath(root))
        self.read_count = 0
        self.byte_count = 0

    def read(self, path: str) -> bytes:
        parts = _safe_parts(path)
        flags_dir = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags_file = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        directory_fds: list[int] = []
        try:
            current = os.open(os.fspath(self.root), flags_dir)
            directory_fds.append(current)
            for component in parts[:-1]:
                current = os.open(component, flags_dir, dir_fd=current)
                directory_fds.append(current)
            file_fd = os.open(parts[-1], flags_file, dir_fd=current)
            try:
                before = os.fstat(file_fd)
                require(stat.S_ISREG(before.st_mode), f"{path}: not regular")
                require(before.st_nlink == 1, f"{path}: link count")
                require(0 <= before.st_size <= MAX_TRACKED_FILE_BYTES, f"{path}: size bound")
                chunks: list[bytes] = []
                remaining = before.st_size
                while remaining:
                    chunk = os.read(file_fd, min(65_536, remaining))
                    require(bool(chunk), f"{path}: short read")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(file_fd, 1) == b"", f"{path}: grew during read")
                after = os.fstat(file_fd)
                require(_metadata(before) == _metadata(after), f"{path}: changed during read")
                raw = b"".join(chunks)
                require(len(raw) == before.st_size, f"{path}: size changed")
            finally:
                os.close(file_fd)
        except OSError as error:
            raise CheckError(f"{path}: stable no-follow read failed") from error
        finally:
            for fd in reversed(directory_fds):
                os.close(fd)
        self.read_count += 1
        self.byte_count += len(raw)
        return raw

    def read_all(self) -> dict[str, bytes]:
        return {path: self.read(path) for path in ALLOWED_PATHS}


def _walk_strings(value: Any):
    if type(value) is str:
        yield value
    elif type(value) is list:
        for child in value:
            yield from _walk_strings(child)
    elif type(value) is dict:
        for key, child in value.items():
            yield key
            yield from _walk_strings(child)


def _derived_patch_units(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    inventory = result.get("patchUnitCandidateInventory")
    require(type(inventory) is dict, "result patch inventory")
    units = inventory.get("patchUnits")
    require(type(units) is list, "result patch units")
    derived: list[dict[str, Any]] = []
    for unit in units:
        require(type(unit) is dict and type(unit.get("rules")) is list, "result patch unit schema")
        derived.append(
            {
                "completeObservationSha256": unit.get("completeObservationSha256"),
                "patchUnit": unit.get("patchUnit"),
                "rules": [
                    {
                        "omittedHitCount": rule.get("omittedHitCount"),
                        "recordedRepresentativeCount": rule.get("recordedRepresentativeCount"),
                        "ruleId": rule.get("ruleId"),
                        "totalHitCount": rule.get("totalHitCount"),
                    }
                    for rule in unit["rules"]
                ],
                "totalHitCount": unit.get("totalHitCount"),
            }
        )
    return derived


def _expected_patch_objects() -> list[dict[str, Any]]:
    return [
        {
            "completeObservationSha256": digest,
            "patchUnit": unit_id,
            "rules": [
                {
                    "omittedHitCount": omitted,
                    "recordedRepresentativeCount": recorded,
                    "ruleId": rule_id,
                    "totalHitCount": total,
                }
                for rule_id, total, recorded, omitted in rules
            ],
            "totalHitCount": unit_total,
        }
        for unit_id, unit_total, digest, rules in EXPECTED_PATCH_UNITS
    ]


def validate_documents(raw: Mapping[str, bytes], *, enforce_pins: bool = True) -> dict[str, Any]:
    require(set(raw) == set(ALLOWED_PATHS), "tracked allowlist mismatch")
    if enforce_pins:
        for path, expected in EXPECTED_RAW_SHA256.items():
            require(sha256_bytes(raw[path]) == expected, f"{path}: raw pin")

    documents = {path: strict_json(raw[path], path) for path in ALLOWED_PATHS}
    decision = documents[DECISION_PATH]
    result = documents[RESULT_PATH]
    require(type(decision) is dict and type(result) is dict, "root documents")
    require(raw[DECISION_PATH] == canonical_json_bytes(decision), "decision is not canonical JSON")
    exact_object(
        decision,
        {
            "archiveIdentity", "contentBinding", "decisionId", "documentType", "nextAction",
            "nonClaims", "operationBoundary", "personalProjectBoundary", "predecessorBindings",
            "publicationContract", "recordedDate", "resourceLimits", "result", "reviewCoverage",
            "schemaVersion", "semanticContract", "status",
        },
        "decision",
    )
    require_exact(decision["documentType"], "aetherlink.g2-pion-rung3-semantic-source-review-decision", "documentType")
    require_exact(decision["schemaVersion"], "1.0", "schemaVersion")
    require_exact(decision["decisionId"], "g2-pion-ice-v4.3.0-rung3-semantic-source-review-decision-v1", "decisionId")
    require_exact(decision["recordedDate"], "2026-07-23", "recordedDate")
    require_exact(decision["status"], EXPECTED_STATUS, "status")
    require_exact(decision["result"], EXPECTED_RESULT, "result")
    require_exact(decision["nextAction"], EXPECTED_NEXT_ACTION, "nextAction")

    binding = exact_object(decision["contentBinding"], {"algorithm", "canonicalization", "scope", "sha256"}, "contentBinding")
    require_exact(binding["algorithm"], "sha256", "contentBinding.algorithm")
    require_exact(binding["canonicalization"], "utf8_ascii_escaped_sorted_keys_compact_single_lf", "contentBinding.canonicalization")
    require_exact(binding["scope"], "decision_without_contentBinding", "contentBinding.scope")
    without_binding = dict(decision)
    without_binding.pop("contentBinding")
    calculated = sha256_bytes(canonical_json_bytes(without_binding))
    require_exact(binding["sha256"], calculated, "contentBinding.sha256")
    if enforce_pins:
        require_exact(calculated, EXPECTED_DECISION_CONTENT_SHA256, "decision content pin")

    require_exact(
        decision["archiveIdentity"],
        {
            "bytes": 293023,
            "entryCount": 129,
            "fileCount": 129,
            "modulePrefix": "github.com/pion/ice/v4@v4.3.0/",
            "rawSha256": EXPECTED_ARCHIVE_SHA256,
            "retainedArchivePath": "build/offline-source/pion-ice-v4.3.0/original/github.com-pion-ice-v4@v4.3.0.zip",
            "sourceTreeSha256": EXPECTED_SOURCE_TREE_SHA256,
        },
        "archiveIdentity",
    )
    require_exact(decision["predecessorBindings"], list(EXPECTED_PREDECESSORS), "predecessorBindings")
    for predecessor in decision["predecessorBindings"]:
        require_exact(
            sha256_bytes(raw[predecessor["path"]]),
            predecessor["rawSha256"],
            f"{predecessor['path']}: bound raw SHA-256",
        )
    require(all(not value.casefold().endswith((".md", ".markdown")) for value in _walk_strings(decision)), "mutable Markdown pin forbidden")

    require_exact(
        decision["personalProjectBoundary"],
        {
            "executionPermitAuthenticationRequired": False,
            "executionPermitDocumentRequired": False,
            "externalIdentityProofRequired": False,
            "productEndpointAuthenticationChangedByThisDecision": False,
            "repositoryOwnerAuthenticationRequired": False,
            "technicalSafetyGatesRemainRequired": True,
            "userActionRequired": False,
        },
        "personalProjectBoundary",
    )
    require_exact(
        decision["operationBoundary"],
        {
            "analysisMayRepeatBeforeExclusivePublication": True,
            "archiveExtractionAllowed": False,
            "archiveReadAllowedOnlyDuringFutureSemanticExecution": True,
            "codeLoadingAllowed": False,
            "compilerInvocationAllowed": False,
            "dependencyInstallationAllowed": False,
            "deviceOperationAllowed": False,
            "dnsAllowed": False,
            "gitOperationAllowed": False,
            "networkAllowed": False,
            "packageManagerAllowed": False,
            "reviewedSourceExecutionAllowed": False,
            "shellAllowed": False,
            "socketCreationAllowed": False,
            "sourceMaterializationAllowed": False,
            "sourcePatchWriteAllowed": False,
            "subprocessAllowed": False,
        },
        "operationBoundary",
    )
    require_exact(
        decision["nonClaims"],
        {
            "candidateSelected": False,
            "dependencyClosureComplete": False,
            "librarySelected": False,
            "productionDeploymentAuthorized": False,
            "rungThreeComplete": False,
            "semanticSourceReviewPerformed": False,
        },
        "nonClaims",
    )
    require_exact(
        decision["publicationContract"],
        {
            "classificationFileName": "semantic-source-review-classifications-v1.json",
            "exclusiveNoReplacePublicationRequired": True,
            "failureFileName": "semantic-source-review-execution-failure-v1.json",
            "manifestFileName": "semantic-source-review-manifest-v1.json",
            "resultFileName": "semantic-source-review-result-v1.json",
            "sourceBodyPublicationAllowed": False,
            "sourceLineDigestPublicationAllowed": False,
        },
        "publicationContract",
    )
    require_exact(
        decision["resourceLimits"],
        {
            "maximumArchiveBytes": 524288,
            "maximumEntries": 4096,
            "maximumGoSourceBytes": 2097152,
            "maximumJsonArtifactBytes": 4194304,
            "maximumPathBytes": 1024,
            "maximumTotalUncompressedBytes": 67108864,
        },
        "resourceLimits",
    )
    require_exact(
        decision["semanticContract"],
        {
            "archiveOpenCountPerAnalysisExecution": 1,
            "dependencyClosureComplete": False,
            "disagreementResolution": "force_unresolved",
            "dispositions": ["false_positive", "acceptable_existing", "patch_required", "unresolved"],
            "eachReviewPassCoversAllGoSourceBodiesAndLexicalObservations": True,
            "oneUseZeroHitHandling": {
                "missingRequiredMechanismGapRequired": True,
                "notAVulnerabilityConclusionByItself": True,
                "ruleId": "one-use",
            },
            "reviewPassesShareOneImmutableInMemorySnapshot": True,
            "sourceBodyReadCountPerGoFilePerAnalysisExecution": 1,
            "sourceClassificationPrecedence": ["example", "test", "production"],
            "sourceClassificationRules": {
                "examplePathPrefix": "examples/",
                "productionOtherwise": True,
                "testPathSuffix": "_test.go",
            },
            "sourceClasses": ["production", "test", "example"],
        },
        "semanticContract",
    )

    coverage = exact_object(
        decision["reviewCoverage"],
        {
            "allGoSourceBodiesRequired", "allLexicalObservationsRequired", "goSourceFileCount",
            "goSourceLogicalLineCount", "goSourceTotalBytes", "lexicalObservationTotals",
            "lexicalRuleCount", "patchUnitCount", "patchUnits", "reviewPassCount",
            "reviewPasses", "sourceClasses", "verificationUnitCount", "verificationUnitIds",
        },
        "reviewCoverage",
    )
    require_exact(coverage["allGoSourceBodiesRequired"], True, "all Go bodies")
    require_exact(coverage["allLexicalObservationsRequired"], True, "all observations")
    require_exact((coverage["goSourceFileCount"], coverage["goSourceTotalBytes"], coverage["goSourceLogicalLineCount"]), (100, 1077591, 39064), "Go inventory")
    require_exact(
        (
            coverage["patchUnitCount"],
            coverage["lexicalRuleCount"],
            coverage["verificationUnitCount"],
            coverage["reviewPassCount"],
        ),
        (7, 19, 8, 2),
        "coverage cardinalities",
    )
    require_exact(coverage["lexicalObservationTotals"], {"omittedHitCount": 4557, "recordedRepresentativeCount": 144, "totalHitCount": 4701}, "observation totals")
    require_exact(coverage["reviewPasses"], ["primary", "independent"], "review passes")
    require_exact(coverage["sourceClasses"], {"example": 4, "production": 52, "test": 44}, "source classes")
    require_exact(coverage["verificationUnitIds"], list(EXPECTED_VERIFICATION_IDS), "verification units")
    require_exact(coverage["patchUnits"], _expected_patch_objects(), "expected patch units")

    result_archive = result.get("archiveEvidence")
    require(type(result_archive) is dict, "result archive evidence")
    for key, expected in (("rawSha256", EXPECTED_ARCHIVE_SHA256), ("bytes", 293023), ("entryCount", 129), ("fileCount", 129)):
        require_exact(result_archive.get(key), expected, f"result archive {key}")
    source_inventory = result.get("sourceInventory")
    require(type(source_inventory) is dict and type(source_inventory.get("entries")) is list, "result source inventory")
    require_exact(source_inventory.get("entryCount"), 129, "result entry count")
    require_exact(source_inventory.get("sourceFilesObserved"), 100, "result source count")
    require_exact(source_inventory.get("treeSha256"), EXPECTED_SOURCE_TREE_SHA256, "result source tree")
    go_entries = [entry for entry in source_inventory["entries"] if type(entry) is dict and entry.get("category") == "go_source"]
    require(len(go_entries) == 100, "result exact Go entries")
    classes = {"production": 0, "test": 0, "example": 0}
    for entry in go_entries:
        path = entry.get("path")
        require(type(path) is str and type(entry.get("bytes")) is int, "Go entry shape")
        if path.startswith("examples/"):
            classes["example"] += 1
        elif path.endswith("_test.go"):
            classes["test"] += 1
        else:
            classes["production"] += 1
    require_exact(classes, {"production": 52, "test": 44, "example": 4}, "derived source classes")
    require_exact(sum(entry["bytes"] for entry in go_entries), 1077591, "derived Go bytes")

    result_candidate = result.get("patchUnitCandidateInventory")
    require(type(result_candidate) is dict, "result candidate inventory")
    require_exact(result_candidate.get("sourceEntryCount"), 100, "candidate source count")
    require_exact(result_candidate.get("sourceTotalBytes"), 1077591, "candidate source bytes")
    require_exact(result_candidate.get("sourceLogicalLineCount"), 39064, "candidate logical lines")
    require_exact(result_candidate.get("totals"), {"hitCount": 4701, "omittedHitCount": 4557, "recordedRepresentativeCount": 144, "truncated": True}, "result totals")
    require_exact(_derived_patch_units(result), coverage["patchUnits"], "decision/result patch derivation")
    result_verification = result.get("profileVerificationUnits")
    require(type(result_verification) is list, "result verification units")
    require_exact([item.get("id") for item in result_verification], list(EXPECTED_VERIFICATION_IDS), "result verification IDs")

    boundary = result.get("executionBoundary")
    require(type(boundary) is dict, "result execution boundary")
    for false_key in (
        "semanticSourceReviewPerformed", "rungThreeComplete", "candidateSelected",
        "librarySelected", "sourceMaterialized", "sourceExecuted", "reviewedSourceCompiled",
        "dependencyInstalled", "networkUsed", "socketCreated", "gitOperationPerformed",
        "deviceExecutionPerformed", "productionDeploymentAuthorized",
        "repositoryOwnerAuthenticationRequired", "externalIdentityProofRequired", "userActionRequired",
    ):
        require_exact(boundary.get(false_key), False, f"result boundary {false_key}")

    expected_predecessor_statuses = {
        RUNTIME_MANIFEST_PATH: (
            "rung3_v3_exact_lexical_candidate_aggregation_committed_"
            "semantic_review_not_performed"
        ),
        RECEIPT_PATH: PREDECESSOR_STATUS,
        PROGRESS_PATH: PREDECESSOR_STATUS,
        SUPERSESSION_PATH: PREDECESSOR_STATUS,
        MANIFEST_PATH: PREDECESSOR_STATUS,
    }
    for path in (RUNTIME_MANIFEST_PATH, RECEIPT_PATH, PROGRESS_PATH, SUPERSESSION_PATH, MANIFEST_PATH):
        document = documents[path]
        require(type(document) is dict, f"{path}: root")
        require_exact(document.get("status"), expected_predecessor_statuses[path], f"{path}: status")
        require_exact(document.get("nextAction"), PREDECESSOR_NEXT_ACTION, f"{path}: nextAction")
    receipt_boundary = documents[RECEIPT_PATH].get("personalProjectBoundary")
    progress_boundary = documents[PROGRESS_PATH].get("personalProjectBoundary")
    for label, personal in (("receipt", receipt_boundary), ("progress", progress_boundary)):
        require(type(personal) is dict, f"{label}: personal boundary")
        for key in ("repositoryOwnerAuthenticationRequired", "externalIdentityProofRequired", "executionPermitAuthenticationRequired", "userActionRequired"):
            require_exact(personal.get(key), False, f"{label}: {key}")
    require_exact(documents[PROGRESS_PATH].get("completionSummary", {}).get("semanticSourceReviewPerformed"), False, "progress semantic review")
    require_exact(documents[SUPERSESSION_PATH].get("executionBoundary", {}).get("dependencyClosureComplete"), False, "supersession dependency closure")

    return {
        "status": "passed",
        "decisionStatus": EXPECTED_STATUS,
        "nextAction": EXPECTED_NEXT_ACTION,
        "trackedFileReadCount": len(ALLOWED_PATHS),
        "goSourceFileCount": 100,
        "lexicalObservationCount": 4701,
        "buildReadCount": 0,
        "archiveReadCount": 0,
        "markdownReadCount": 0,
        "networkOperationCount": 0,
        "deviceOperationCount": 0,
        "gitOperationCount": 0,
        "fileWriteCount": 0,
        "authenticationOrUserActionRequired": False,
    }


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    reader = FixedTrackedReader(root)
    raw = reader.read_all()
    result = validate_documents(raw)
    require(reader.read_count == len(ALLOWED_PATHS), "reader count")
    return result


def main() -> int:
    try:
        result = validate_repository()
    except (CheckError, OSError, RuntimeError) as error:
        print(f"G2 semantic-review decision v1 check failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
