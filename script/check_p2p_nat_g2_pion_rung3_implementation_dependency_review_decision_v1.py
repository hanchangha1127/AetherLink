#!/usr/bin/env python3
"""Validate the G2 dependency-review lane selection.

This checker reads only fixed local artifacts. A pass proves that one
dependency-review option and one dependency-review treatment unit were selected
for planning while all root implementation units, operational authority,
finding closure, candidate selection, and library selection remain closed. It
does not acquire, extract, compile, load, execute, connect, authenticate, deploy,
or perform a Git write.
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
            "E_RUNTIME: decision checker requires unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
import zipfile


ROOT = Path(os.path.abspath(__file__)).parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG3 = f"{BASE}/rung-three"
DECISION_PATH = f"{RUNG3}/implementation-or-dependency-review-decision-v1.json"
DECISION_DIR = f"{RUNG3}/implementation-or-dependency-review-decision-v1"
PLAN_PATH = (
    f"{DECISION_DIR}/implementation/staged-fixed-point-source-closure.md"
)
PREDECESSOR_PATH = f"{RUNG3}/patch-and-dependency-closure-decision-v1.json"
PREDECESSOR_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_patch_dependency_decision_v1.py"
)
PREDECESSOR_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_patch_dependency_decision_v1.py"
)
PORTFOLIO_DIR = f"{RUNG3}/patch-and-dependency-closure-decision-v1"
ANALYSIS_PATH = f"{PORTFOLIO_DIR}/hardening.json"
PORTFOLIO_MARKDOWN_PATH = f"{PORTFOLIO_DIR}/hardening.md"
CLASSIFICATIONS_PATH = f"{RUNG3}/semantic-source-review-classifications-v1.json"
RESULT_PATH = f"{RUNG3}/semantic-source-review-result-v1.json"
MANIFEST_PATH = f"{RUNG3}/semantic-source-review-manifest-v1.json"
ARCHIVE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
GO_MOD_ENTRY = "github.com/pion/ice/v4@v4.3.0/go.mod"
GO_SUM_ENTRY = "github.com/pion/ice/v4@v4.3.0/go.sum"

EXPECTED_RAW = {
    DECISION_PATH: "6a14603c02c9aa9d9d78377b1c38a9f0d47391c0ac1ff8eea1769198ddc13ff8",
    PLAN_PATH: "22d7cfbc2db9e34fab641167d227e650cb490dcfd9a402a4dff86e1f967234bc",
    PREDECESSOR_PATH: "5ab3bfe60c617c58b88ae0885f2bdb6fba0c315c0478d6eacf526cdd935903ec",
    PREDECESSOR_CHECKER_PATH: "9b8d92ddcfa93e10ab1a67718b709773b21a4ebd6429552a1a85cfee01a9b078",
    PREDECESSOR_TESTS_PATH: "9fee38580b8090f8a9c732203a0ba6a4fbe704385856341d3cfd820916da8f1d",
    ANALYSIS_PATH: "d426e363672e8d36155d37bad754e89ce775d37d16c3cbd0a8de8b6abd393866",
    PORTFOLIO_MARKDOWN_PATH: "1d3dbc89ac20b7fa961e4f986d3a9002de6e51943306d9927fc3220b902bc606",
    CLASSIFICATIONS_PATH: "e76e8c9fa0a78c8c5c4beae1ebfd4c4f8144b411689a3a8bd5f8804ebf61c8c9",
    RESULT_PATH: "a01b3518f1354d438542ae77c06aa92d8f0936d516b4070d19c5bf27791e8a98",
    MANIFEST_PATH: "300da97505b4715576d665846b23dd8363b36d416ed5d24ed4a7d4e77f098e6f",
    ARCHIVE_PATH: "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
}

EXPECTED_PORTFOLIO_FILES = (
    f"{PORTFOLIO_DIR}/context.md",
    f"{PORTFOLIO_DIR}/diagrams/bounded-resource-lifecycle-before.mmd",
    f"{PORTFOLIO_DIR}/diagrams/bounded-resource-lifecycle-independent-local-ceilings-after.mmd",
    f"{PORTFOLIO_DIR}/diagrams/bounded-resource-lifecycle-owned-resource-supervisor-after.mmd",
    f"{PORTFOLIO_DIR}/diagrams/capability-gated-network-boundary-before.mmd",
    f"{PORTFOLIO_DIR}/diagrams/capability-gated-network-boundary-distributed-sink-guards-after.mmd",
    f"{PORTFOLIO_DIR}/diagrams/capability-gated-network-boundary-typed-capability-state-machine-after.mmd",
    f"{PORTFOLIO_DIR}/diagrams/fixed-point-dependency-closure-before.mmd",
    f"{PORTFOLIO_DIR}/diagrams/fixed-point-dependency-closure-single-wave-inventory-review-after.mmd",
    f"{PORTFOLIO_DIR}/diagrams/fixed-point-dependency-closure-staged-fixed-point-source-closure-after.mmd",
    f"{PORTFOLIO_DIR}/diagrams/typed-secret-free-diagnostics-before.mmd",
    f"{PORTFOLIO_DIR}/diagrams/typed-secret-free-diagnostics-delete-current-sensitive-logs-after.mmd",
    f"{PORTFOLIO_DIR}/diagrams/typed-secret-free-diagnostics-typed-diagnostic-sink-after.mmd",
    ANALYSIS_PATH,
    PORTFOLIO_MARKDOWN_PATH,
    f"{PORTFOLIO_DIR}/proposals/bounded-resource-lifecycle.md",
    f"{PORTFOLIO_DIR}/proposals/capability-gated-network-boundary.md",
    f"{PORTFOLIO_DIR}/proposals/fixed-point-dependency-closure.md",
    f"{PORTFOLIO_DIR}/proposals/typed-secret-free-diagnostics.md",
)
EXPECTED_PORTFOLIO_DIRS = (
    PORTFOLIO_DIR,
    f"{PORTFOLIO_DIR}/diagrams",
    f"{PORTFOLIO_DIR}/proposals",
)
EXPECTED_PORTFOLIO_BYTES = 186_716
EXPECTED_PORTFOLIO_BUNDLE = (
    "020fa0b627a85844d557323b5106e4179637fe3f14c578fec50e6a3e34e68f56"
)
EXPECTED_DECISION_FILES = (PLAN_PATH,)
EXPECTED_DECISION_DIRS = (
    DECISION_DIR,
    f"{DECISION_DIR}/implementation",
)
DECISION_SIBLING_PREFIX = "implementation-or-dependency-review-decision-v1"
EXPECTED_DECISION_PREFIX_SIBLINGS = (
    (DECISION_SIBLING_PREFIX, "directory"),
    (f"{DECISION_SIBLING_PREFIX}.json", "file"),
)

EXPECTED_DECISION_KEYS = {
    "documentType",
    "schemaVersion",
    "decisionId",
    "recordedDate",
    "status",
    "predecessorBinding",
    "sourceSnapshot",
    "findingBoundary",
    "selection",
    "portfolioSelections",
    "treatmentUnitSelections",
    "dependencyReviewContract",
    "implementationPlanBinding",
    "sequence",
    "authority",
    "closure",
    "nonClaims",
    "result",
    "nextAction",
    "contentBinding",
}
EXPECTED_CLASSIFICATIONS_KEYS = {
    "archiveSnapshot",
    "candidateClassification",
    "contentBinding",
    "coverageAndLocationBoundsValidatedAgainstSnapshot",
    "decisionBinding",
    "dependencyBoundary",
    "documentType",
    "integrityLimitations",
    "locationValidationBoundary",
    "nonClaims",
    "observationClassification",
    "passCandidateSemanticBindings",
    "passInputBinding",
    "passRecordBindings",
    "passRecordsNonAttesting",
    "personalProjectBoundary",
    "postRunEvidenceBoundary",
    "recordedDate",
    "reviewId",
    "runnerBinding",
    "schemaVersion",
    "semanticJudgmentsIndependentlyReproducedByRunner",
    "status",
}
EXPECTED_RESULT_KEYS = {
    "closure",
    "contentBinding",
    "coverage",
    "coverageAndLocationBoundsValidatedAgainstSnapshot",
    "decisionBinding",
    "documentType",
    "findingAudit",
    "integrityLimitations",
    "locationValidationBoundary",
    "nextAction",
    "passCandidateSemanticBindings",
    "passInputBinding",
    "passRecordBindings",
    "passRecordsNonAttesting",
    "personalProjectBoundary",
    "postRunEvidenceBoundary",
    "recordedDate",
    "result",
    "reviewId",
    "runnerBinding",
    "schemaVersion",
    "semanticJudgmentsIndependentlyReproducedByRunner",
    "status",
}
EXPECTED_MANIFEST_KEYS = {
    "artifacts",
    "contentBinding",
    "coverageAndLocationBoundsValidatedAgainstSnapshot",
    "documentType",
    "integrityLimitations",
    "locationValidationBoundary",
    "nonClaims",
    "passCandidateSemanticBindings",
    "passRecordBindings",
    "passRecordsNonAttesting",
    "personalProjectBoundary",
    "postRunEvidenceBoundary",
    "preCommitOperationCounters",
    "publicationContract",
    "recordedDate",
    "reviewId",
    "runnerBinding",
    "schemaVersion",
    "semanticJudgmentsIndependentlyReproducedByRunner",
    "status",
    "transactionalPublicationBoundary",
}
EXPECTED_PERSONAL_PROJECT_BOUNDARY = {
    "executionPermitAuthenticationRequired": False,
    "executionPermitDocumentRequired": False,
    "externalIdentityProofRequired": False,
    "repositoryOwnerAuthenticationRequired": False,
    "userActionRequired": False,
}
EXPECTED_POST_RUN_BOUNDARY = {
    "finalSuccessEvidenceEstablished": False,
    "independentPostRunCheckerCompleted": False,
    "independentPostRunCheckerRequiredForFinalSuccessEvidence": True,
}
EXPECTED_SEMANTIC_CONTENT_SHA256 = {
    "classifications": (
        "d7feed1bdd5a7a8ee0eead002c598157c01dafe2d429b7c1c012978d39a38886"
    ),
    "result": (
        "9a7eeae26ca7538b33f805f35ade421c528dd52745fd6c737fedb7c70acf6e97"
    ),
    "manifest": (
        "3812c15c57b93b7d35dde44b4cdb3d4abff4f696b517fb6e7e216dab0b45671e"
    ),
}

EXPECTED_PREDECESSOR_BINDING = {
    "decisionPath": PREDECESSOR_PATH,
    "decisionRawSha256": EXPECTED_RAW[PREDECESSOR_PATH],
    "decisionContentSha256": (
        "b0bc1feb01546e3bcd261794f21b51d526de1b3d84fabc36d459699319a773ef"
    ),
    "decisionCheckerPath": PREDECESSOR_CHECKER_PATH,
    "decisionCheckerRawSha256": EXPECTED_RAW[PREDECESSOR_CHECKER_PATH],
    "decisionCheckerTestsPath": PREDECESSOR_TESTS_PATH,
    "decisionCheckerTestsRawSha256": EXPECTED_RAW[PREDECESSOR_TESTS_PATH],
    "analysisPath": ANALYSIS_PATH,
    "analysisRawSha256": EXPECTED_RAW[ANALYSIS_PATH],
    "portfolioPath": PORTFOLIO_DIR,
    "portfolioArtifactCount": 19,
    "portfolioByteSize": EXPECTED_PORTFOLIO_BYTES,
    "portfolioBundleSha256": EXPECTED_PORTFOLIO_BUNDLE,
    "portfolioMarkdownPath": PORTFOLIO_MARKDOWN_PATH,
    "portfolioMarkdownRawSha256": EXPECTED_RAW[PORTFOLIO_MARKDOWN_PATH],
    "classificationPath": CLASSIFICATIONS_PATH,
    "classificationRawSha256": EXPECTED_RAW[CLASSIFICATIONS_PATH],
    "resultPath": RESULT_PATH,
    "resultRawSha256": EXPECTED_RAW[RESULT_PATH],
    "manifestPath": MANIFEST_PATH,
    "manifestRawSha256": EXPECTED_RAW[MANIFEST_PATH],
    "recordedNextAction": (
        "prepare_separate_versioned_implementation_or_dependency_review_decision"
    ),
}

EXPECTED_SOURCE_SNAPSHOT = {
    "module": "github.com/pion/ice/v4",
    "version": "v4.3.0",
    "upstreamCommit": "1e8716372f2bb52e45bf2a7172e4fb1004251c46",
    "archivePath": ARCHIVE_PATH,
    "archiveRawSha256": EXPECTED_RAW[ARCHIVE_PATH],
    "sourceTreeSha256": (
        "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
    ),
    "goModRawSha256": (
        "5044428710b5a718aad517eed5c08e1933378efa3d9b4245853cfb312560aca4"
    ),
    "goSumRawSha256": (
        "b47d7d5f3bb8c8b85b3283585f97ea6bd0a8b97427b49068b9f5685ddd953887"
    ),
    "sourceExtracted": False,
    "sourceModified": False,
    "sourceCompiled": False,
    "sourceLoaded": False,
    "sourceExecuted": False,
}

DEPENDENCY_FINDING_IDS = (
    "G2SR1-F-c9dd2e9b3fa55e3ad43b",
    "G2SR1-F-65bdab86ddd0720af770",
    "G2SR1-F-7e744b8ee19e7de9b7c3",
    "G2SR1-F-7d678ddf77ac89e04ae4",
)

EXPECTED_SELECTION = {
    "decisionLane": "dependency_review_selection",
    "dependencyReviewSelected": True,
    "selectedPortfolioOptionIds": ["staged-fixed-point-source-closure"],
    "selectedTreatmentUnitIds": [
        "dependency_source_license_security_closure_review"
    ],
    "selectedPortfolioOptionCount": 1,
    "selectedTreatmentUnitCount": 1,
    "rootImplementationOptionSetSelected": False,
    "rootPatchImplementationPrepared": False,
    "patchSeriesCreated": False,
    "dependencyReviewPlanCreated": True,
    "dependencyAcquisitionDecisionCreated": False,
}

EXPECTED_PORTFOLIO_SELECTIONS = [
    {
        "opportunityId": "capability-gated-network-boundary",
        "optionId": "distributed-sink-guards",
        "recommended": False,
        "selected": False,
        "status": "deferred_until_dependency_review_outcome",
    },
    {
        "opportunityId": "capability-gated-network-boundary",
        "optionId": "typed-capability-state-machine",
        "recommended": True,
        "selected": False,
        "status": "deferred_until_dependency_review_outcome",
    },
    {
        "opportunityId": "bounded-resource-lifecycle",
        "optionId": "independent-local-ceilings",
        "recommended": False,
        "selected": False,
        "status": "deferred_until_dependency_review_outcome",
    },
    {
        "opportunityId": "bounded-resource-lifecycle",
        "optionId": "owned-resource-supervisor",
        "recommended": True,
        "selected": False,
        "status": "deferred_until_dependency_review_outcome",
    },
    {
        "opportunityId": "typed-secret-free-diagnostics",
        "optionId": "delete-current-sensitive-logs",
        "recommended": False,
        "selected": False,
        "status": "deferred_until_dependency_review_outcome",
    },
    {
        "opportunityId": "typed-secret-free-diagnostics",
        "optionId": "typed-diagnostic-sink",
        "recommended": True,
        "selected": False,
        "status": "deferred_until_dependency_review_outcome",
    },
    {
        "opportunityId": "fixed-point-dependency-closure",
        "optionId": "single-wave-inventory-review",
        "recommended": False,
        "selected": False,
        "status": "deferred_incomplete_graph_evidence",
    },
    {
        "opportunityId": "fixed-point-dependency-closure",
        "optionId": "staged-fixed-point-source-closure",
        "recommended": True,
        "selected": True,
        "status": "selected_for_review_plan_only",
    },
]

ROOT_PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)
DEPENDENCY_UNIT = "dependency_source_license_security_closure_review"
EXPECTED_TREATMENT_SELECTIONS = [
    *[
        {
            "unitId": unit,
            "kind": "root_patch_unit",
            "selected": False,
            "status": "deferred_until_dependency_review_outcome",
        }
        for unit in ROOT_PATCH_UNITS
    ],
    {
        "unitId": DEPENDENCY_UNIT,
        "kind": "dependency_review_unit",
        "selected": True,
        "status": "selected_for_review_plan_only",
    },
]

EXPECTED_DEPENDENCY_CONTRACT = {
    "rootRequirementCount": 19,
    "rootDirectRequirementCount": 10,
    "rootIndirectRequirementCount": 9,
    "goSumRecordCount": 44,
    "goSumModuleVersionTupleCount": 23,
    "goSumSourceHashCount": 21,
    "goSumGoModHashCount": 23,
    "checksumOnlyContextTupleCount": 4,
    "rootMetadataProvesCompleteGraph": False,
    "fixedPointGraphRequired": True,
    "immutableBoundedWavesRequired": True,
    "newSelectedTupleRequiresNewDecisionVersion": True,
    "twoIndependentSemanticPassesRequired": True,
    "licenseClosureRequired": True,
    "spdx23SbomRequired": True,
    "manifestLastIndependentReadbackRequired": True,
    "productionReachabilityProfilesFrozenByThisDecision": False,
    "acquisitionBoundsFrozenByThisDecision": False,
}

EXPECTED_PLAN_BINDING = {
    "path": PLAN_PATH,
    "byteSize": 16_155,
    "rawSha256": EXPECTED_RAW[PLAN_PATH],
    "selectedOptionId": "staged-fixed-point-source-closure",
    "planPrepared": True,
    "planExecuted": False,
}

EXPECTED_SEQUENCE = [
    {
        "order": 1,
        "stepId": "bind_patch_dependency_portfolio",
        "prepared": True,
        "executed": True,
    },
    {
        "order": 2,
        "stepId": "select_dependency_review_lane",
        "prepared": True,
        "executed": True,
    },
    {
        "order": 3,
        "stepId": "prepare_staged_fixed_point_review_plan",
        "prepared": True,
        "executed": True,
    },
    {
        "order": 4,
        "stepId": "prepare_bounded_dependency_source_identity_and_acquisition_decision",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 5,
        "stepId": "acquire_immutable_bounded_waves",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 6,
        "stepId": "expand_exact_graph_to_fixed_point",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 7,
        "stepId": "two_pass_source_license_security_review",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 8,
        "stepId": "publish_sbom_manifest_and_independent_readback",
        "prepared": False,
        "executed": False,
    },
    {
        "order": 9,
        "stepId": "prepare_separate_root_implementation_selection_decision",
        "prepared": False,
        "executed": False,
    },
]

EXPECTED_AUTHORITY = {
    "sourceModificationAuthorized": False,
    "sourceExtractionAuthorized": False,
    "dependencyAcquisitionAuthorized": False,
    "packageManagerAuthorized": False,
    "compilerAuthorized": False,
    "sourceLoadAuthorized": False,
    "sourceExecutionAuthorized": False,
    "socketAuthorized": False,
    "networkAuthorized": False,
    "deviceAuthorized": False,
    "deploymentAuthorized": False,
    "gitWriteAuthorized": False,
    "externalAuthenticationRequired": False,
    "userActionRequired": False,
}
EXPECTED_CLOSURE = {
    "findingsClosedBySelection": 0,
    "rootPatchComplete": False,
    "dependencySourceReviewed": False,
    "dependencyClosureComplete": False,
    "semanticClosureComplete": False,
    "rungThreeComplete": False,
    "candidateSelected": False,
    "librarySelected": False,
}
EXPECTED_NONCLAIMS = {
    "reviewLaneSelectionIsDependencyClosure": False,
    "implementationPlanIsSourceImplementation": False,
    "implementationPlanIsAcquisitionAuthority": False,
    "rootRecommendationsSelected": False,
    "rootMetadataIsCompleteGraphEvidence": False,
    "dependencyReviewSelectsLibrary": False,
    "repositoryIdentityProofRequired": False,
    "productEndpointAuthenticationSatisfied": False,
}

EXPECTED_SUMMARY = {
    "status": "dependency_review_selected_acquisition_not_authorized",
    "result": "staged_fixed_point_dependency_review_selected_all_19_findings_remain_open",
    "decisionLane": "dependency_review_selection",
    "selectedPortfolioOption": "staged-fixed-point-source-closure",
    "selectedTreatmentUnit": DEPENDENCY_UNIT,
    "selectedPortfolioOptionCount": "1",
    "unselectedPortfolioOptionCount": "7",
    "selectedTreatmentUnitCount": "1",
    "unselectedRootPatchUnitCount": "7",
    "findingsClosedBySelection": "0",
    "dependencyAcquisitionAuthorized": "false",
    "sourceModificationAuthorized": "false",
    "networkAuthorized": "false",
    "gitWriteAuthorized": "false",
    "externalAuthenticationRequired": "false",
    "userActionRequired": "false",
    "dependencyClosureComplete": "false",
    "candidateSelected": "false",
    "librarySelected": "false",
    "nextAction": (
        "prepare_separate_versioned_bounded_dependency_source_identity_and_"
        "acquisition_decision"
    ),
}


class CheckError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise CheckError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def strict_equal(actual: Any, expected: Any, code: str, path: str) -> None:
    require(type(actual) is type(expected), code, f"{path}: exact type drift")
    if isinstance(expected, dict):
        require(set(actual) == set(expected), code, f"{path}: exact key set drift")
        for key in expected:
            strict_equal(actual[key], expected[key], code, f"{path}.{key}")
    elif isinstance(expected, list):
        require(len(actual) == len(expected), code, f"{path}: list length drift")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            strict_equal(actual_item, expected_item, code, f"{path}[{index}]")
    else:
        require(actual == expected, code, f"{path}: exact value drift")


def reject_constant(value: str) -> None:
    fail("E_JSON", f"non-finite JSON number is forbidden: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("E_JSON", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
        require(not text.startswith("\ufeff"), "E_JSON", f"{label}: BOM forbidden")
        value = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("E_JSON", f"{label}: invalid strict UTF-8 JSON: {exc}")
    require(type(value) is dict, "E_JSON", f"{label}: top-level object required")
    require(text.endswith("\n"), "E_JSON", f"{label}: final LF required")
    return value


def validate_relative_path(relative: str) -> tuple[str, ...]:
    path = PurePosixPath(relative)
    require(not path.is_absolute(), "E_FILESYSTEM", f"absolute path: {relative}")
    require(
        bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts),
        "E_FILESYSTEM",
        f"unsafe path: {relative}",
    )
    return path.parts


def file_state(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


class DirectoryLink:
    def __init__(
        self,
        parent_fd: int,
        name: str,
        child_fd: int,
        state: tuple[int, int, int, int, int, int, int],
    ) -> None:
        self.parent_fd = parent_fd
        self.name = name
        self.child_fd = child_fd
        self.state = state


class Snapshot:
    def __init__(
        self,
        relative: str,
        root_fd: int,
        root_state: tuple[int, int, int, int, int, int, int],
        directory_links: list[DirectoryLink],
        parent_fd: int,
        filename: str,
        file_fd: int,
        state: tuple[int, int, int, int, int, int, int],
        data: bytes,
    ) -> None:
        self.relative = relative
        self.root_fd = root_fd
        self.root_state = root_state
        self.directory_links = directory_links
        self.parent_fd = parent_fd
        self.filename = filename
        self.file_fd = file_fd
        self.state = state
        self.data = data


def open_flags(*, directory: bool) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if directory and hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    return flags


def secure_read(relative: str, maximum_bytes: int) -> Snapshot:
    parts = validate_relative_path(relative)
    root_info = ROOT.lstat()
    require(
        stat.S_ISDIR(root_info.st_mode) and not stat.S_ISLNK(root_info.st_mode),
        "E_FILESYSTEM",
        "repository root must be a real directory",
    )
    root_fd = os.open(ROOT, open_flags(directory=True))
    directory_links: list[DirectoryLink] = []
    file_fd = -1
    try:
        root_opened = os.fstat(root_fd)
        require(
            file_state(root_opened) == file_state(root_info),
            "E_FILESYSTEM",
            "repository root identity changed",
        )
        current_fd = root_fd
        for part in parts[:-1]:
            before = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            require(
                stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode),
                "E_FILESYSTEM",
                f"real directory ancestor required: {relative}",
            )
            child_fd = os.open(part, open_flags(directory=True), dir_fd=current_fd)
            opened = os.fstat(child_fd)
            require(
                file_state(opened) == file_state(before),
                "E_FILESYSTEM",
                f"directory identity changed: {relative}",
            )
            directory_links.append(
                DirectoryLink(current_fd, part, child_fd, file_state(before))
            )
            current_fd = child_fd

        filename = parts[-1]
        before_file = os.stat(filename, dir_fd=current_fd, follow_symlinks=False)
        require(
            stat.S_ISREG(before_file.st_mode)
            and not stat.S_ISLNK(before_file.st_mode),
            "E_FILESYSTEM",
            f"regular file required: {relative}",
        )
        require(
            before_file.st_nlink == 1,
            "E_FILESYSTEM",
            f"single-link file required: {relative}",
        )
        file_fd = os.open(filename, open_flags(directory=False), dir_fd=current_fd)
        opened_file = os.fstat(file_fd)
        require(
            file_state(opened_file) == file_state(before_file),
            "E_FILESYSTEM",
            f"file identity changed before read: {relative}",
        )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            require(
                total <= maximum_bytes,
                "E_FILESYSTEM",
                f"file exceeds read bound: {relative}",
            )
        require(
            file_state(os.fstat(file_fd)) == file_state(before_file),
            "E_FILESYSTEM",
            f"file changed during read: {relative}",
        )
        return Snapshot(
            relative,
            root_fd,
            file_state(root_info),
            directory_links,
            current_fd,
            filename,
            file_fd,
            file_state(before_file),
            b"".join(chunks),
        )
    except Exception:
        if file_fd >= 0:
            os.close(file_fd)
        for link in reversed(directory_links):
            os.close(link.child_fd)
        os.close(root_fd)
        raise


def verify_snapshot(snapshot: Snapshot) -> None:
    require(
        file_state(ROOT.lstat()) == snapshot.root_state,
        "E_TOCTOU",
        f"repository root changed: {snapshot.relative}",
    )
    require(
        file_state(os.fstat(snapshot.root_fd)) == snapshot.root_state,
        "E_TOCTOU",
        f"opened repository root changed: {snapshot.relative}",
    )
    for link in snapshot.directory_links:
        linked = os.stat(link.name, dir_fd=link.parent_fd, follow_symlinks=False)
        require(
            file_state(linked) == link.state
            and file_state(os.fstat(link.child_fd)) == link.state,
            "E_TOCTOU",
            f"ancestor changed: {snapshot.relative}",
        )
    linked_file = os.stat(
        snapshot.filename,
        dir_fd=snapshot.parent_fd,
        follow_symlinks=False,
    )
    require(
        file_state(linked_file) == snapshot.state
        and file_state(os.fstat(snapshot.file_fd)) == snapshot.state,
        "E_TOCTOU",
        f"file path changed after read: {snapshot.relative}",
    )
    os.lseek(snapshot.file_fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(snapshot.file_fd, 65_536)
        if not chunk:
            break
        chunks.append(chunk)
    require(
        b"".join(chunks) == snapshot.data,
        "E_TOCTOU",
        f"file bytes changed after read: {snapshot.relative}",
    )


def close_snapshots(snapshots: list[Snapshot]) -> None:
    for snapshot in snapshots:
        try:
            os.close(snapshot.file_fd)
        except OSError:
            pass
        for link in reversed(snapshot.directory_links):
            try:
                os.close(link.child_fd)
            except OSError:
                pass
        try:
            os.close(snapshot.root_fd)
        except OSError:
            pass


def inventory_tree(relative: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    base = ROOT.joinpath(*validate_relative_path(relative))
    pending = [base]
    found_dirs: list[str] = []
    found_files: list[str] = []
    while pending:
        current = pending.pop()
        current_info = current.lstat()
        require(
            stat.S_ISDIR(current_info.st_mode)
            and not stat.S_ISLNK(current_info.st_mode),
            "E_INVENTORY",
            f"real directory required: {current.relative_to(ROOT)}",
        )
        found_dirs.append(current.relative_to(ROOT).as_posix())
        with os.scandir(current) as scanner:
            for entry in scanner:
                path = current / entry.name
                info = entry.stat(follow_symlinks=False)
                require(
                    not entry.is_symlink(),
                    "E_INVENTORY",
                    f"symlink forbidden: {path.relative_to(ROOT)}",
                )
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    require(
                        info.st_nlink == 1,
                        "E_INVENTORY",
                        f"single-link file required: {path.relative_to(ROOT)}",
                    )
                    found_files.append(path.relative_to(ROOT).as_posix())
                else:
                    fail(
                        "E_INVENTORY",
                        f"special artifact forbidden: {path.relative_to(ROOT)}",
                    )
    return tuple(sorted(found_dirs)), tuple(sorted(found_files))


def inventory_prefixed_siblings(
    relative: str,
    prefix: str,
) -> tuple[
    tuple[int, int, int, int, int, int, int],
    tuple[tuple[str, str], ...],
]:
    base = ROOT.joinpath(*validate_relative_path(relative))
    before = base.lstat()
    require(
        stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode),
        "E_INVENTORY",
        f"real sibling directory required: {relative}",
    )
    directory_fd = os.open(base, open_flags(directory=True))
    try:
        opened = os.fstat(directory_fd)
        require(
            file_state(opened) == file_state(before),
            "E_INVENTORY",
            f"sibling directory identity changed: {relative}",
        )
        found: list[tuple[str, str]] = []
        with os.scandir(directory_fd) as scanner:
            for entry in scanner:
                if not entry.name.startswith(prefix):
                    continue
                info = entry.stat(follow_symlinks=False)
                require(
                    not entry.is_symlink(),
                    "E_INVENTORY",
                    f"prefixed sibling symlink forbidden: {relative}/{entry.name}",
                )
                if stat.S_ISDIR(info.st_mode):
                    kind = "directory"
                elif stat.S_ISREG(info.st_mode):
                    require(
                        info.st_nlink == 1,
                        "E_INVENTORY",
                        f"single-link prefixed sibling required: {relative}/{entry.name}",
                    )
                    kind = "file"
                else:
                    fail(
                        "E_INVENTORY",
                        f"special prefixed sibling forbidden: {relative}/{entry.name}",
                    )
                found.append((entry.name, kind))
        require(
            file_state(os.fstat(directory_fd)) == file_state(before),
            "E_INVENTORY",
            f"sibling directory changed during inventory: {relative}",
        )
        return file_state(before), tuple(sorted(found))
    finally:
        os.close(directory_fd)


def verify_self_binding(document: dict[str, Any], label: str) -> None:
    binding = document.get("contentBinding")
    require(type(binding) is dict, "E_BINDING", f"{label}: binding missing")
    expected_scopes = {
        DECISION_PATH: "decision_without_contentBinding",
        PREDECESSOR_PATH: "decision_without_contentBinding",
        CLASSIFICATIONS_PATH: "classifications_without_contentBinding",
        RESULT_PATH: "result_without_contentBinding",
        MANIFEST_PATH: "manifest_without_contentBinding",
    }
    require(
        label in expected_scopes,
        "E_BINDING",
        f"{label}: no exact binding scope is registered",
    )
    expected_shape = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": expected_scopes[label],
        "sha256": binding.get("sha256"),
    }
    strict_equal(binding, expected_shape, "E_BINDING", f"{label}.contentBinding")
    require(
        type(binding["sha256"]) is str and len(binding["sha256"]) == 64,
        "E_BINDING",
        f"{label}: invalid binding digest",
    )
    body = dict(document)
    body.pop("contentBinding", None)
    require(
        binding["sha256"] == sha256(canonical_bytes(body)),
        "E_BINDING",
        f"{label}: self-binding drift",
    )


def validate_semantic_predecessor_records(
    classifications: dict[str, Any],
    result: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    require(
        set(classifications) == EXPECTED_CLASSIFICATIONS_KEYS,
        "E_PREDECESSOR_SCHEMA",
        "classifications top-level key set drift",
    )
    require(
        set(result) == EXPECTED_RESULT_KEYS,
        "E_PREDECESSOR_SCHEMA",
        "result top-level key set drift",
    )
    require(
        set(manifest) == EXPECTED_MANIFEST_KEYS,
        "E_PREDECESSOR_SCHEMA",
        "manifest top-level key set drift",
    )
    for document, label, expected_type, expected_status in (
        (
            classifications,
            "classifications",
            "aetherlink.g2-pion-rung3-semantic-source-review-classifications",
            "two_pass_semantic_classification_validated",
        ),
        (
            result,
            "result",
            "aetherlink.g2-pion-rung3-semantic-source-review-result",
            "rung3_semantic_source_review_v1_executed_semantic_closure_blocked",
        ),
        (
            manifest,
            "manifest",
            "aetherlink.g2-pion-rung3-semantic-source-review-manifest",
            "semantic_review_atomic_commit_marker_checker_pending",
        ),
    ):
        strict_equal(
            document["contentBinding"]["sha256"],
            EXPECTED_SEMANTIC_CONTENT_SHA256[label],
            "E_PREDECESSOR",
            f"{label}.contentBinding.sha256",
        )
        strict_equal(
            document.get("documentType"),
            expected_type,
            "E_PREDECESSOR",
            f"{label}.documentType",
        )
        strict_equal(
            document.get("schemaVersion"),
            "1.0",
            "E_PREDECESSOR",
            f"{label}.schemaVersion",
        )
        strict_equal(
            document.get("reviewId"),
            "g2-pion-ice-v4.3.0-rung3-semantic-source-review-v1",
            "E_PREDECESSOR",
            f"{label}.reviewId",
        )
        strict_equal(
            document.get("recordedDate"),
            "2026-07-23",
            "E_PREDECESSOR",
            f"{label}.recordedDate",
        )
        strict_equal(
            document.get("status"),
            expected_status,
            "E_PREDECESSOR",
            f"{label}.status",
        )
        strict_equal(
            document.get("personalProjectBoundary"),
            EXPECTED_PERSONAL_PROJECT_BOUNDARY,
            "E_PREDECESSOR",
            f"{label}.personalProjectBoundary",
        )
        strict_equal(
            document.get("postRunEvidenceBoundary"),
            EXPECTED_POST_RUN_BOUNDARY,
            "E_PREDECESSOR",
            f"{label}.postRunEvidenceBoundary",
        )
        strict_equal(
            document.get("passRecordsNonAttesting"),
            True,
            "E_PREDECESSOR",
            f"{label}.passRecordsNonAttesting",
        )
        strict_equal(
            document.get("coverageAndLocationBoundsValidatedAgainstSnapshot"),
            True,
            "E_PREDECESSOR",
            f"{label}.coverageAndLocationBoundsValidatedAgainstSnapshot",
        )
        strict_equal(
            document.get("semanticJudgmentsIndependentlyReproducedByRunner"),
            False,
            "E_PREDECESSOR",
            f"{label}.semanticJudgmentsIndependentlyReproducedByRunner",
        )

    strict_equal(
        classifications.get("dependencyBoundary"),
        {
            "dependencyClosureComplete": False,
            "dependencySourceReviewed": False,
            "goModRequireCount": 19,
            "goSumRecordCount": 44,
        },
        "E_PREDECESSOR",
        "classifications.dependencyBoundary",
    )
    strict_equal(
        classifications.get("nonClaims"),
        {
            "candidateSelected": False,
            "dependencyClosureComplete": False,
            "librarySelected": False,
            "productionDeploymentAuthorized": False,
            "rungThreeComplete": False,
        },
        "E_PREDECESSOR",
        "classifications.nonClaims",
    )
    strict_equal(
        result.get("closure"),
        {
            "candidateSelected": False,
            "dependencyClosureComplete": False,
            "dependencySourceReviewed": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "semanticClosureComplete": False,
        },
        "E_PREDECESSOR",
        "result.closure",
    )
    strict_equal(
        result.get("result"),
        "two_pass_100_file_4701_observation_review_recorded_findings_and_dependency_gaps_remain",
        "E_PREDECESSOR",
        "result.result",
    )
    strict_equal(
        result.get("nextAction"),
        "prepare_versioned_rung3_patch_and_dependency_closure_decision",
        "E_PREDECESSOR",
        "result.nextAction",
    )
    strict_equal(
        manifest.get("nonClaims"),
        {
            "candidateSelected": False,
            "dependencyClosureComplete": False,
            "finalSuccessEvidenceEstablished": False,
            "independentPostRunCheckerCompleted": False,
            "librarySelected": False,
            "postCommitFullSetReadbackCompletionPersistedByManifest": False,
            "postRunReproductionPerformed": False,
            "rungThreeComplete": False,
        },
        "E_PREDECESSOR",
        "manifest.nonClaims",
    )
    strict_equal(
        manifest.get("publicationContract"),
        {
            "classificationsAndResultFullSetReadbackCompletedBeforeCommitMarker": True,
            "commitMarkerPresenceAloneIsFinalSuccessEvidence": False,
            "failureArtifactMayBePublishedAfterCommitMarker": True,
            "independentPostRunCheckerRequiredForFinalSuccessEvidence": True,
            "manifestRole": "atomic_commit_marker",
            "perArtifactStagingAndFinalReadbackRequired": True,
            "postCommitFullSetReadbackAttemptRequiredBeforeSuccessfulRunnerReturn": True,
            "postCommitFullSetReadbackCompletionPersistedByManifest": False,
        },
        "E_PREDECESSOR",
        "manifest.publicationContract",
    )


def expected_finding_rows(classifications: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        findings = classifications["candidateClassification"]["findings"]
    except (KeyError, TypeError) as exc:
        fail("E_FINDINGS", f"classification finding set missing: {exc}")
    require(type(findings) is list, "E_FINDINGS", "classification findings list")
    rows: list[dict[str, Any]] = []
    for finding in findings:
        require(type(finding) is dict, "E_FINDINGS", "classification finding object")
        rows.append(
            {
                "findingId": finding.get("findingId"),
                "canonicalInvariantId": finding.get("canonicalInvariantId"),
                "finalDisposition": finding.get("finalDisposition"),
                "finalSeverity": finding.get("finalSeverity"),
                "dependencyBlocked": finding.get("dependencyBlocked"),
            }
        )
    require(len(rows) == 19, "E_FINDINGS", "exactly 19 findings required")
    require(
        len({row["findingId"] for row in rows}) == 19,
        "E_FINDINGS",
        "finding IDs must be unique",
    )
    return rows


def validate_predecessor(
    predecessor: dict[str, Any],
    analysis: dict[str, Any],
    classifications: dict[str, Any],
) -> list[dict[str, Any]]:
    verify_self_binding(predecessor, PREDECESSOR_PATH)
    verify_self_binding(classifications, CLASSIFICATIONS_PATH)
    strict_equal(
        predecessor.get("selection"),
        {
            "anyOptionSelected": False,
            "selectedOptionIds": [],
            "implementationPlanCreated": False,
            "patchSeriesCreated": False,
            "dependencyAcquisitionDecisionCreated": False,
        },
        "E_PREDECESSOR",
        "predecessor.selection",
    )
    strict_equal(
        predecessor.get("authority"),
        EXPECTED_AUTHORITY,
        "E_PREDECESSOR",
        "predecessor.authority",
    )
    require(
        predecessor.get("status")
        == "prepared_options_unselected_dependency_closure_blocked",
        "E_PREDECESSOR",
        "predecessor status drift",
    )
    require(
        predecessor.get("nextAction")
        == EXPECTED_PREDECESSOR_BINDING["recordedNextAction"],
        "E_PREDECESSOR",
        "predecessor next action drift",
    )
    rows = expected_finding_rows(classifications)
    strict_equal(
        predecessor.get("findingSet", {}).get("findings"),
        rows,
        "E_FINDINGS",
        "predecessor.findingSet.findings",
    )
    strict_equal(
        analysis.get("selection"),
        {
            "anyOptionSelected": False,
            "selectedOptionIds": [],
            "implementationPlanCreated": False,
        },
        "E_PREDECESSOR",
        "hardening.selection",
    )
    opportunities = analysis.get("opportunities")
    require(
        type(opportunities) is list and len(opportunities) == 4,
        "E_PREDECESSOR",
        "four hardening opportunities required",
    )
    option_rows: list[tuple[str, str, bool]] = []
    for opportunity in opportunities:
        require(type(opportunity) is dict, "E_PREDECESSOR", "opportunity object")
        recommended = opportunity.get("recommendedOptionId")
        options = opportunity.get("options")
        require(
            type(options) is list and len(options) == 2,
            "E_PREDECESSOR",
            "two portfolio options per opportunity required",
        )
        for option in options:
            option_rows.append(
                (
                    opportunity.get("opportunityId"),
                    option.get("optionId"),
                    option.get("optionId") == recommended,
                )
            )
    expected_rows = [
        (
            row["opportunityId"],
            row["optionId"],
            row["recommended"],
        )
        for row in EXPECTED_PORTFOLIO_SELECTIONS
    ]
    strict_equal(
        option_rows,
        expected_rows,
        "E_PREDECESSOR",
        "hardening option identities",
    )
    return rows


def validate_finding_boundary(
    boundary: Any,
    rows: list[dict[str, Any]],
    predecessor: dict[str, Any],
) -> None:
    expected = {
        "canonicalFindingCount": 19,
        "openFindingCount": 19,
        "findingsClosedBySelection": 0,
        "dispositionCounts": {
            "patch_required": 7,
            "unresolved": 12,
        },
        "severityCounts": {
            "P0": 0,
            "P1": 11,
            "P2": 3,
            "P3": 4,
            "none": 1,
        },
        "findings": rows,
        "dependencyReviewFindingIds": list(DEPENDENCY_FINDING_IDS),
        "allFindingsRemainOpen": True,
    }
    strict_equal(boundary, expected, "E_FINDINGS", "decision.findingBoundary")
    mapped: list[str] = []
    for treatment in predecessor.get("treatments", []):
        if DEPENDENCY_UNIT in treatment.get("patchUnitIds", []):
            mapped.append(treatment.get("findingId"))
    strict_equal(
        mapped,
        list(DEPENDENCY_FINDING_IDS),
        "E_FINDINGS",
        "predecessor dependency treatment mapping",
    )


def validate_archive(archive_bytes: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            go_mod = archive.read(GO_MOD_ENTRY)
            go_sum = archive.read(GO_SUM_ENTRY)
    except (zipfile.BadZipFile, KeyError) as exc:
        fail("E_ARCHIVE", f"retained archive invalid: {exc}")
    require(
        sha256(go_mod) == EXPECTED_SOURCE_SNAPSHOT["goModRawSha256"],
        "E_ARCHIVE",
        "go.mod byte digest drift",
    )
    require(
        sha256(go_sum) == EXPECTED_SOURCE_SNAPSHOT["goSumRawSha256"],
        "E_ARCHIVE",
        "go.sum byte digest drift",
    )
    lines = [line.split() for line in go_sum.decode("utf-8").splitlines()]
    require(
        len(lines) == 44 and all(len(line) == 3 for line in lines),
        "E_ARCHIVE",
        "go.sum record structure drift",
    )
    tuples = {(line[0], line[1].removesuffix("/go.mod")) for line in lines}
    require(
        (
            len(tuples),
            sum(not line[1].endswith("/go.mod") for line in lines),
            sum(line[1].endswith("/go.mod") for line in lines),
        )
        == (23, 21, 23),
        "E_ARCHIVE",
        "go.sum tuple count drift",
    )


def portfolio_bundle(raw: dict[str, bytes]) -> tuple[int, str]:
    rows: list[bytes] = []
    total = 0
    for path in sorted(EXPECTED_PORTFOLIO_FILES):
        data = raw[path]
        total += len(data)
        rows.append(
            f"{path}\t{len(data)}\t{sha256(data)}\n".encode("utf-8")
        )
    return total, sha256(b"".join(rows))


def validate_plan(plan_bytes: bytes, decision: dict[str, Any]) -> None:
    try:
        text = plan_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("E_PLAN_SEMANTICS", f"plan is not UTF-8: {exc}")
    start = "<!-- aetherlink-decision-summary:v1\n"
    end = "-->"
    require(
        text.count(start) == 1,
        "E_PLAN_SEMANTICS",
        "exactly one plan summary start required",
    )
    summary_tail = text.split(start, 1)[1]
    require(
        summary_tail.count(end) >= 1,
        "E_PLAN_SEMANTICS",
        "plan summary end missing",
    )
    summary_text = summary_tail.split(end, 1)[0]
    summary: dict[str, str] = {}
    for line in summary_text.splitlines():
        require(
            "=" in line,
            "E_PLAN_SEMANTICS",
            f"malformed plan summary line: {line}",
        )
        key, value = line.split("=", 1)
        require(
            key not in summary,
            "E_PLAN_SEMANTICS",
            f"duplicate plan summary key: {key}",
        )
        summary[key] = value
    strict_equal(summary, EXPECTED_SUMMARY, "E_PLAN_SEMANTICS", "plan.summary")

    headings = [
        "## Selected Design And Constraints",
        "## Source Revision And Drift Check",
        "## Affected Components",
        "## Ordered Work Packages",
        "## Compatibility And Migration",
        "## Tactical Protections During Migration",
        "## Tests And Security Validation",
        "## Performance And Resource Benchmarks",
        "## Rollout And Rollback",
        "## Acceptance Criteria",
        "## Open Decisions",
    ]
    positions: list[int] = []
    for heading in headings:
        require(
            text.count(heading) == 1,
            "E_PLAN_SEMANTICS",
            f"exactly one plan heading required: {heading}",
        )
        positions.append(text.index(heading))
    require(
        positions == sorted(positions),
        "E_PLAN_SEMANTICS",
        "plan heading order drift",
    )
    lower = text.casefold()
    allowed_negative_clauses = (
        "no external authentication or user action is required",
    )
    claim_text = lower
    for clause in allowed_negative_clauses:
        require(
            claim_text.count(clause) == 1,
            "E_PLAN_SEMANTICS",
            f"required negative plan boundary drifted: {clause}",
        )
        claim_text = claim_text.replace(clause, "", 1)
    auth_claim_text = re.sub(r"\s+", " ", lower).strip()
    allowed_auth_contexts = (
        (
            "it requires no repository identity proof, external authentication, "
            "signature, execution permit, or user action."
        ),
        "selection, external-authentication, and user-action mutations;",
        "no external authentication or user action is required.",
        (
            "not requests for owner identity, external authentication, or user input."
        ),
    )
    for clause in allowed_auth_contexts:
        require(
            auth_claim_text.count(clause) == 1,
            "E_PLAN_SEMANTICS",
            f"explicit plan authentication boundary drift: {clause}",
        )
        auth_claim_text = auth_claim_text.replace(clause, "", 1)
    require(
        re.search(
            r"\bexternal(?:-|\s+)authentication\b|\buser(?:-|\s+)action\b",
            auth_claim_text,
        )
        is None,
        "E_PLAN_SEMANTICS",
        "ambiguous plan authentication or user-action mention",
    )
    forbidden_claim_patterns = (
        (
            "dependency acquisition authority",
            r"(?:"
            r"\b(?:dependency acquisition(?: authority)?|acquisition of dependencies)\b"
            r"[^\n.!?]{0,120}\b(?:authorized|allowed|permitted|approved|granted|enabled)\b"
            r"|"
            r"\b(?:authorize|allow|permit|approve|grant|enable|proceed with)\b"
            r"[^\n.!?]{0,80}\bdependency acquisition\b"
            r")",
        ),
        (
            "source modification authority",
            r"(?:"
            r"\bsource (?:modification|extraction)(?: authority)?\b"
            r"[^\n.!?]{0,120}\b(?:authorized|allowed|permitted|approved|granted|enabled)\b"
            r"|"
            r"\b(?:authorize|allow|permit|approve|grant|enable|proceed with)\b"
            r"[^\n.!?]{0,80}\bsource (?:modification|extraction)\b"
            r")",
        ),
        (
            "network authority",
            r"(?:"
            r"\bnetwork (?:access|use|io|i/o|authority)\b"
            r"[^\n.!?]{0,120}\b(?:authorized|allowed|permitted|approved|granted|enabled)\b"
            r"|"
            r"\b(?:authorize|allow|permit|approve|grant|enable|proceed with)\b"
            r"[^\n.!?]{0,80}\bnetwork (?:access|use|io|i/o)\b"
            r")",
        ),
        (
            "Git-write authority",
            r"(?:"
            r"\bgit (?:writes?|write authority)\b"
            r"[^\n.!?]{0,120}\b(?:authorized|allowed|permitted|approved|granted|enabled)\b"
            r"|"
            r"\b(?:authorize|allow|permit|approve|grant|enable|proceed with)\b"
            r"[^\n.!?]{0,80}\bgit writes?\b"
            r")",
        ),
        (
            "finding closure",
            r"(?:"
            r"\b(?:all\s+)?19(?:\s+canonical)? findings\b"
            r"[^\n.!?]{0,120}\b(?:closed|completed|resolved|remediated)\b"
            r"|"
            r"\b(?:close|complete|resolve|remediate)\b"
            r"[^\n.!?]{0,80}\b(?:all\s+)?19(?:\s+canonical)? findings\b"
            r")",
        ),
        (
            "candidate selection",
            r"(?:"
            r"\bcandidate selection\b"
            r"[^\n.!?]{0,80}\b(?:complete|completed|approved|finalized)\b"
            r"|"
            r"\b(?:the\s+)?candidate\b[^\n.!?]{0,80}\bselected\b"
            r"|"
            r"\bselect(?:ed)?\b[^\n.!?]{0,60}\b(?:the\s+)?candidate\b"
            r")",
        ),
        (
            "library selection",
            r"(?:"
            r"\blibrary selection\b"
            r"[^\n.!?]{0,80}\b(?:complete|completed|approved|finalized)\b"
            r"|"
            r"\b(?:the\s+)?library\b[^\n.!?]{0,80}\bselected\b"
            r"|"
            r"\bselect(?:ed)?\b[^\n.!?]{0,60}\b(?:the\s+)?library\b"
            r")",
        ),
        (
            "external-authentication requirement",
            r"(?:"
            r"\bexternal authentication\b"
            r"[^\n.!?]{0,80}\b(?:required|needed|mandatory)\b"
            r"|"
            r"\b(?:require|requires|need|needs)\b"
            r"[^\n.!?]{0,80}\bexternal authentication\b"
            r")",
        ),
        (
            "user-action requirement",
            r"(?:"
            r"\buser action\b[^\n.!?]{0,80}\b(?:required|needed|mandatory)\b"
            r"|"
            r"\b(?:require|requires|need|needs)\b"
            r"[^\n.!?]{0,80}\buser action\b"
            r")",
        ),
    )
    for label, pattern in forbidden_claim_patterns:
        require(
            re.search(pattern, claim_text) is None,
            "E_PLAN_SEMANTICS",
            f"contradictory plan claim: {label}",
        )
    require(
        "/Users/" not in text,
        "E_PLAN_SEMANTICS",
        "distributable plan contains an absolute user path",
    )
    strict_equal(
        decision.get("implementationPlanBinding"),
        EXPECTED_PLAN_BINDING,
        "E_PLAN_BINDING",
        "decision.implementationPlanBinding",
    )
    require(
        len(plan_bytes) == decision["implementationPlanBinding"]["byteSize"]
        and sha256(plan_bytes)
        == decision["implementationPlanBinding"]["rawSha256"],
        "E_PLAN_BINDING",
        "plan bytes drift from decision binding",
    )


def validate_decision(
    decision: dict[str, Any],
    predecessor: dict[str, Any],
    analysis: dict[str, Any],
    classifications: dict[str, Any],
    plan_bytes: bytes,
) -> None:
    require(
        set(decision) == EXPECTED_DECISION_KEYS,
        "E_SCHEMA",
        "decision top-level key set drift",
    )
    verify_self_binding(decision, DECISION_PATH)
    strict_equal(
        decision.get("documentType"),
        "aetherlink.g2-pion-rung3-implementation-or-dependency-review-decision",
        "E_DECISION",
        "decision.documentType",
    )
    strict_equal(
        decision.get("schemaVersion"),
        "1.0",
        "E_DECISION",
        "decision.schemaVersion",
    )
    strict_equal(
        decision.get("decisionId"),
        "g2-pion-ice-v4.3.0-rung3-implementation-or-dependency-review-decision-v1",
        "E_DECISION",
        "decision.decisionId",
    )
    strict_equal(
        decision.get("recordedDate"),
        "2026-07-23",
        "E_DECISION",
        "decision.recordedDate",
    )
    strict_equal(
        decision.get("status"),
        "dependency_review_selected_acquisition_not_authorized",
        "E_DECISION",
        "decision.status",
    )
    strict_equal(
        decision.get("predecessorBinding"),
        EXPECTED_PREDECESSOR_BINDING,
        "E_PREDECESSOR",
        "decision.predecessorBinding",
    )
    strict_equal(
        decision.get("sourceSnapshot"),
        EXPECTED_SOURCE_SNAPSHOT,
        "E_SOURCE",
        "decision.sourceSnapshot",
    )
    rows = validate_predecessor(predecessor, analysis, classifications)
    validate_finding_boundary(decision.get("findingBoundary"), rows, predecessor)
    strict_equal(
        decision.get("selection"),
        EXPECTED_SELECTION,
        "E_SELECTION",
        "decision.selection",
    )
    strict_equal(
        decision.get("portfolioSelections"),
        EXPECTED_PORTFOLIO_SELECTIONS,
        "E_SELECTION",
        "decision.portfolioSelections",
    )
    strict_equal(
        decision.get("treatmentUnitSelections"),
        EXPECTED_TREATMENT_SELECTIONS,
        "E_SELECTION",
        "decision.treatmentUnitSelections",
    )
    require(
        sum(row["selected"] is True for row in decision["portfolioSelections"]) == 1
        and sum(
            row["selected"] is True
            for row in decision["treatmentUnitSelections"]
        )
        == 1,
        "E_SELECTION",
        "exactly one portfolio option and one treatment unit must be selected",
    )
    strict_equal(
        decision.get("dependencyReviewContract"),
        EXPECTED_DEPENDENCY_CONTRACT,
        "E_CONTRACT",
        "decision.dependencyReviewContract",
    )
    strict_equal(
        decision.get("sequence"),
        EXPECTED_SEQUENCE,
        "E_SEQUENCE",
        "decision.sequence",
    )
    strict_equal(
        decision.get("authority"),
        EXPECTED_AUTHORITY,
        "E_AUTHORITY",
        "decision.authority",
    )
    strict_equal(
        decision.get("closure"),
        EXPECTED_CLOSURE,
        "E_CLOSURE",
        "decision.closure",
    )
    strict_equal(
        decision.get("nonClaims"),
        EXPECTED_NONCLAIMS,
        "E_NONCLAIM",
        "decision.nonClaims",
    )
    strict_equal(
        decision.get("result"),
        EXPECTED_SUMMARY["result"],
        "E_DECISION",
        "decision.result",
    )
    strict_equal(
        decision.get("nextAction"),
        EXPECTED_SUMMARY["nextAction"],
        "E_DECISION",
        "decision.nextAction",
    )
    validate_plan(plan_bytes, decision)


def main() -> int:
    snapshots: list[Snapshot] = []
    try:
        sibling_state, prefixed_siblings = inventory_prefixed_siblings(
            RUNG3,
            DECISION_SIBLING_PREFIX,
        )
        strict_equal(
            prefixed_siblings,
            EXPECTED_DECISION_PREFIX_SIBLINGS,
            "E_INVENTORY",
            "decision prefixed siblings",
        )
        portfolio_dirs, portfolio_files = inventory_tree(PORTFOLIO_DIR)
        strict_equal(
            portfolio_dirs,
            tuple(sorted(EXPECTED_PORTFOLIO_DIRS)),
            "E_INVENTORY",
            "portfolio directories",
        )
        strict_equal(
            portfolio_files,
            tuple(sorted(EXPECTED_PORTFOLIO_FILES)),
            "E_INVENTORY",
            "portfolio files",
        )
        decision_dirs, decision_files = inventory_tree(DECISION_DIR)
        strict_equal(
            decision_dirs,
            tuple(sorted(EXPECTED_DECISION_DIRS)),
            "E_INVENTORY",
            "decision directories",
        )
        strict_equal(
            decision_files,
            tuple(sorted(EXPECTED_DECISION_FILES)),
            "E_INVENTORY",
            "decision files",
        )

        limits = {
            DECISION_PATH: 1_000_000,
            PLAN_PATH: 1_000_000,
            PREDECESSOR_PATH: 1_000_000,
            PREDECESSOR_CHECKER_PATH: 2_000_000,
            PREDECESSOR_TESTS_PATH: 2_000_000,
            CLASSIFICATIONS_PATH: 2_000_000,
            RESULT_PATH: 2_000_000,
            MANIFEST_PATH: 2_000_000,
            ARCHIVE_PATH: 1_000_000,
        }
        for path in EXPECTED_PORTFOLIO_FILES:
            limits[path] = 2_000_000
        for path, maximum_bytes in limits.items():
            snapshots.append(secure_read(path, maximum_bytes))
        raw = {snapshot.relative: snapshot.data for snapshot in snapshots}

        for path, expected in EXPECTED_RAW.items():
            require(
                sha256(raw[path]) == expected,
                "E_RAW_DRIFT",
                f"raw byte digest drift: {path}",
            )
        total, bundle = portfolio_bundle(raw)
        require(
            total == EXPECTED_PORTFOLIO_BYTES,
            "E_PORTFOLIO",
            "portfolio byte-size drift",
        )
        require(
            bundle == EXPECTED_PORTFOLIO_BUNDLE,
            "E_PORTFOLIO",
            "portfolio bundle digest drift",
        )

        decision = parse_json(raw[DECISION_PATH], DECISION_PATH)
        predecessor = parse_json(raw[PREDECESSOR_PATH], PREDECESSOR_PATH)
        analysis = parse_json(raw[ANALYSIS_PATH], ANALYSIS_PATH)
        classifications = parse_json(
            raw[CLASSIFICATIONS_PATH], CLASSIFICATIONS_PATH
        )
        result = parse_json(raw[RESULT_PATH], RESULT_PATH)
        manifest = parse_json(raw[MANIFEST_PATH], MANIFEST_PATH)
        verify_self_binding(result, RESULT_PATH)
        verify_self_binding(manifest, MANIFEST_PATH)
        validate_semantic_predecessor_records(
            classifications,
            result,
            manifest,
        )
        validate_decision(
            decision,
            predecessor,
            analysis,
            classifications,
            raw[PLAN_PATH],
        )
        validate_archive(raw[ARCHIVE_PATH])

        for snapshot in snapshots:
            verify_snapshot(snapshot)
        portfolio_dirs_after, portfolio_files_after = inventory_tree(PORTFOLIO_DIR)
        decision_dirs_after, decision_files_after = inventory_tree(DECISION_DIR)
        sibling_state_after, prefixed_siblings_after = inventory_prefixed_siblings(
            RUNG3,
            DECISION_SIBLING_PREFIX,
        )
        strict_equal(
            (sibling_state_after, prefixed_siblings_after),
            (sibling_state, prefixed_siblings),
            "E_INVENTORY",
            "final decision prefixed sibling inventory",
        )
        strict_equal(
            (portfolio_dirs_after, portfolio_files_after),
            (
                tuple(sorted(EXPECTED_PORTFOLIO_DIRS)),
                tuple(sorted(EXPECTED_PORTFOLIO_FILES)),
            ),
            "E_INVENTORY",
            "final portfolio inventory",
        )
        strict_equal(
            (decision_dirs_after, decision_files_after),
            (
                tuple(sorted(EXPECTED_DECISION_DIRS)),
                tuple(sorted(EXPECTED_DECISION_FILES)),
            ),
            "E_INVENTORY",
            "final decision inventory",
        )
        for snapshot in snapshots:
            verify_snapshot(snapshot)

        print(
            "G2 Pion dependency-review selection verified "
            "(1 structural option and 1 dependency-review unit selected; "
            "19 findings open; no acquisition, implementation, closure, "
            "network, Git, external authentication, or user action)."
        )
        return 0
    except CheckError as exc:
        print(
            f"G2 Pion dependency-review selection FAILED "
            f"[{exc.code}]: {exc}",
            file=sys.stderr,
        )
        return 1
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(
            "G2 Pion dependency-review selection FAILED "
            f"[E_INTERNAL]: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        close_snapshots(snapshots)


if __name__ == "__main__":
    raise SystemExit(main())
