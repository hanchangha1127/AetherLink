#!/usr/bin/env python3
"""Validate the preparation-only G2 Pion patch/dependency decision.

The checker reads fixed local files, including the retained archive, and writes
nothing.  A pass means the decision faithfully preserves the published 19
findings, eight unselected treatment units, the root dependency seed, and the
all-false authority and closure boundary.  It is not implementation,
dependency acquisition, source review closure, authentication, or user action.
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
        raise RuntimeError("decision checker requires unoptimized `python3 -I -B -S`")


require_isolated_interpreter()

from collections import Counter
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
import zipfile


ROOT = Path(os.path.abspath(__file__)).parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG3 = f"{BASE}/rung-three"
DECISION_PATH = f"{RUNG3}/patch-and-dependency-closure-decision-v1.json"
CLASSIFICATIONS_PATH = f"{RUNG3}/semantic-source-review-classifications-v1.json"
RESULT_PATH = f"{RUNG3}/semantic-source-review-result-v1.json"
MANIFEST_PATH = f"{RUNG3}/semantic-source-review-manifest-v1.json"
ANALYSIS_PATH = f"{RUNG3}/patch-and-dependency-closure-decision-v1/hardening.json"
ANALYSIS_DIR = f"{RUNG3}/patch-and-dependency-closure-decision-v1"
ARCHIVE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
GO_MOD_ENTRY = "github.com/pion/ice/v4@v4.3.0/go.mod"
GO_SUM_ENTRY = "github.com/pion/ice/v4@v4.3.0/go.sum"

EXPECTED_RAW = {
    DECISION_PATH: "5ab3bfe60c617c58b88ae0885f2bdb6fba0c315c0478d6eacf526cdd935903ec",
    CLASSIFICATIONS_PATH: "e76e8c9fa0a78c8c5c4beae1ebfd4c4f8144b411689a3a8bd5f8804ebf61c8c9",
    RESULT_PATH: "a01b3518f1354d438542ae77c06aa92d8f0936d516b4070d19c5bf27791e8a98",
    MANIFEST_PATH: "300da97505b4715576d665846b23dd8363b36d416ed5d24ed4a7d4e77f098e6f",
    ANALYSIS_PATH: "d426e363672e8d36155d37bad754e89ce775d37d16c3cbd0a8de8b6abd393866",
    ARCHIVE_PATH: "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
}
PORTFOLIO_MANIFEST = (
    (f"{ANALYSIS_DIR}/context.md", 2_274,
     "ed943fba58c6a37331c46bf54314d2033b3721980f32b8d772736aa73f60620e"),
    (f"{ANALYSIS_DIR}/diagrams/bounded-resource-lifecycle-before.mmd", 484,
     "4db9f04e83391f33345b2356277960082c55e17c35350be7d84b6075cb8a3c7b"),
    (f"{ANALYSIS_DIR}/diagrams/bounded-resource-lifecycle-independent-local-ceilings-after.mmd", 518,
     "e4d10835feebf4f8070c6b7d7afee058f4565f5b62f043f9f89581f0988eac84"),
    (f"{ANALYSIS_DIR}/diagrams/bounded-resource-lifecycle-owned-resource-supervisor-after.mmd", 586,
     "77035e0d94b48ba064f9e2c50cf2dfbb9111b62c0b7ca9e8b183994e5ed1cdda"),
    (f"{ANALYSIS_DIR}/diagrams/capability-gated-network-boundary-before.mmd", 621,
     "a47de8639e138ea21b77a50f7cba550a3aff81d14b4e3d39e29d7f0ec0358dbe"),
    (f"{ANALYSIS_DIR}/diagrams/capability-gated-network-boundary-distributed-sink-guards-after.mmd", 634,
     "f3ede401ad9c612434e72193bc4d51669dd77667eec0dde99ca914b5c0da0fae"),
    (f"{ANALYSIS_DIR}/diagrams/capability-gated-network-boundary-typed-capability-state-machine-after.mmd", 720,
     "b8c10ece861565e0661f27e6a76cdd557ac67be5916de1d100a7a2787d4ee62d"),
    (f"{ANALYSIS_DIR}/diagrams/fixed-point-dependency-closure-before.mmd", 521,
     "0234eb9e4faaba1d50b1fe52bc2f44714429b7bcaf2f48ed11778c4e15b2f803"),
    (f"{ANALYSIS_DIR}/diagrams/fixed-point-dependency-closure-single-wave-inventory-review-after.mmd", 470,
     "5b68f190f69392c6787015cddf173a835bf5fc08b9f9f499816d3b39e9f6fac6"),
    (f"{ANALYSIS_DIR}/diagrams/fixed-point-dependency-closure-staged-fixed-point-source-closure-after.mmd", 641,
     "59e5456029eecb870abb7b93875e6d8544a5aa3b70fca389daaad2e3205b50bf"),
    (f"{ANALYSIS_DIR}/diagrams/typed-secret-free-diagnostics-before.mmd", 366,
     "71a909fe9fbf8b3a06adc3a3781450a1dca9f791e31498a8cde1b9eb9148c4c7"),
    (f"{ANALYSIS_DIR}/diagrams/typed-secret-free-diagnostics-delete-current-sensitive-logs-after.mmd", 389,
     "9640765e98fea3b39a19e87f0a79f8085e0a19a3dc2d715d39cd0810b13eaa31"),
    (f"{ANALYSIS_DIR}/diagrams/typed-secret-free-diagnostics-typed-diagnostic-sink-after.mmd", 480,
     "dc66afb5aec4b9d78739c2e06471d801b1dd262f6cfeedeef287e984f4aaafe0"),
    (ANALYSIS_PATH, 54_403,
     "d426e363672e8d36155d37bad754e89ce775d37d16c3cbd0a8de8b6abd393866"),
    (f"{ANALYSIS_DIR}/hardening.md", 5_272,
     "1d3dbc89ac20b7fa961e4f986d3a9002de6e51943306d9927fc3220b902bc606"),
    (f"{ANALYSIS_DIR}/proposals/bounded-resource-lifecycle.md", 27_424,
     "becd0b723e3a7c8130596e60b07f780190f0c3b2c978a2e5a120d8191a1c8a1c"),
    (f"{ANALYSIS_DIR}/proposals/capability-gated-network-boundary.md", 32_200,
     "3a3f762a91d76ea378457c16015d732454dcb37cb3b262e0c2b0f5b66a1c987d"),
    (f"{ANALYSIS_DIR}/proposals/fixed-point-dependency-closure.md", 39_684,
     "844c22cfda7917b17078a4ba7b1b2e2fe2fac8bd3c67388619a4b5f04f8f9ec3"),
    (f"{ANALYSIS_DIR}/proposals/typed-secret-free-diagnostics.md", 19_029,
     "7d668be87e03e39593e02dcbe683eef31612e4473caf9a2c85e9984f14015f4c"),
)
EXPECTED_PORTFOLIO_DIRS = (
    ANALYSIS_DIR,
    f"{ANALYSIS_DIR}/diagrams",
    f"{ANALYSIS_DIR}/proposals",
)
EXPECTED_CONTENT = {
    CLASSIFICATIONS_PATH: "d7feed1bdd5a7a8ee0eead002c598157c01dafe2d429b7c1c012978d39a38886",
    RESULT_PATH: "9a7eeae26ca7538b33f805f35ade421c528dd52745fd6c737fedb7c70acf6e97",
    MANIFEST_PATH: "3812c15c57b93b7d35dde44b4cdb3d4abff4f696b517fb6e7e216dab0b45671e",
}
EXPECTED_CONTENT_SCOPE = {
    CLASSIFICATIONS_PATH: "classifications_without_contentBinding",
    RESULT_PATH: "result_without_contentBinding",
    MANIFEST_PATH: "manifest_without_contentBinding",
}
EXPECTED_COLLECTION_SHA256 = (
    "853bec14073a55c21980a306b748bc52aa58ec00d94da11e3a65df2533cb4a1f"
)
EXPECTED_GO_MOD_SHA256 = (
    "5044428710b5a718aad517eed5c08e1933378efa3d9b4245853cfb312560aca4"
)
EXPECTED_GO_SUM_SHA256 = (
    "b47d7d5f3bb8c8b85b3283585f97ea6bd0a8b97427b49068b9f5685ddd953887"
)
EXPECTED_SOURCE_TREE_SHA256 = (
    "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
)
DEPENDENCY_OPTION = "dependency_source_license_security_closure_review"
PATCH_OPTIONS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)
OPTION_IDS = (*PATCH_OPTIONS, DEPENDENCY_OPTION)
DEPENDENCY_FINDINGS = {
    "G2SR1-F-c9dd2e9b3fa55e3ad43b",
    "G2SR1-F-65bdab86ddd0720af770",
    "G2SR1-F-7e744b8ee19e7de9b7c3",
    "G2SR1-F-7d678ddf77ac89e04ae4",
}
PRESERVE_FINDINGS = {
    "G2SR1-F-964c63e397f00eeecc36",
    "G2SR1-F-2eef005a63ea93252f5d",
    "G2SR1-F-bfc6cef606dab975ede3",
}
ASSURANCE_FINDINGS = {
    "G2SR1-F-c9dd2e9b3fa55e3ad43b",
    "G2SR1-F-65bdab86ddd0720af770",
    "G2SR1-F-29bea0297021e485b7b0",
}
EXPECTED_OPPORTUNITIES = (
    "capability-gated-network-boundary",
    "bounded-resource-lifecycle",
    "typed-secret-free-diagnostics",
    "fixed-point-dependency-closure",
)
EXPECTED_TRADEOFF_DIMENSIONS = {
    "security",
    "performance",
    "memory",
    "reliability",
    "operability",
    "migration",
}
EXPECTED_REQUIREMENTS = (
    ("github.com/google/uuid", "v1.6.0", True),
    ("github.com/pion/dtls/v3", "v3.1.5", True),
    ("github.com/pion/logging", "v0.2.4", True),
    ("github.com/pion/mdns/v2", "v2.1.0", True),
    ("github.com/pion/randutil", "v0.1.0", True),
    ("github.com/pion/stun/v3", "v3.1.6", True),
    ("github.com/pion/transport/v4", "v4.0.2", True),
    ("github.com/pion/turn/v5", "v5.0.12", True),
    ("github.com/stretchr/testify", "v1.11.1", True),
    ("golang.org/x/net", "v0.49.0", True),
    ("github.com/davecgh/go-spew", "v1.1.1", False),
    ("github.com/kr/pretty", "v0.1.0", False),
    ("github.com/pmezard/go-difflib", "v1.0.0", False),
    ("github.com/wlynxg/anet", "v0.0.5", False),
    ("golang.org/x/crypto", "v0.48.0", False),
    ("golang.org/x/sys", "v0.41.0", False),
    ("golang.org/x/time", "v0.14.0", False),
    ("gopkg.in/check.v1", "v1.0.0-20190902080502-41f04d3bba15", False),
    ("gopkg.in/yaml.v3", "v3.0.1", False),
)
EXPECTED_CHECKSUM_ONLY = (
    ("github.com/kr/pty", "v1.1.1"),
    ("github.com/kr/text", "v0.1.0"),
    ("github.com/pion/transport/v3", "v3.1.1"),
    ("gopkg.in/check.v1", "v0.0.0-20161208181325-20d25e280405"),
)
EXPECTED_DECISION_KEYS = {
    "documentType", "schemaVersion", "decisionId", "recordedDate", "status",
    "predecessorBindings", "archiveBinding", "analysisBinding", "findingSet",
    "treatments", "options", "dependencySeed", "dependencyClosureSequence",
    "selection", "authority", "closure", "nonClaims", "result", "nextAction",
    "contentBinding",
}
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
    "findingsClosedByPreparation": 0,
    "rootPatchComplete": False,
    "dependencySourceReviewed": False,
    "dependencyClosureComplete": False,
    "semanticClosureComplete": False,
    "rungThreeComplete": False,
    "candidateSelected": False,
    "librarySelected": False,
}
EXPECTED_NONCLAIMS = {
    "recommendationIsSelection": False,
    "preparationIsImplementation": False,
    "goSumIsCompleteGraphEvidence": False,
    "sourceReviewIsRuntimeVerification": False,
    "dependencyClosureAloneClosesRootFindings": False,
    "dependencyClosureSelectsLibrary": False,
    "repositoryIdentityProofRequired": False,
    "productEndpointAuthenticationSatisfied": False,
}
EXPECTED_DEPENDENCY_SEQUENCE = [
    {
        "order": 1,
        "stepId": "normalize_root_seed",
        "prepared": True,
        "executed": False,
        "rule": "Bind exact root metadata and keep checksum-only tuples quarantined.",
    },
    {
        "order": 2,
        "stepId": "prepare_source_identity_and_acquisition_decision",
        "prepared": False,
        "executed": False,
        "rule": "A separate version must predeclare tuples, provenance, hashes, archive limits, no-overwrite, and stop conditions.",
    },
    {
        "order": 3,
        "stepId": "acquire_immutable_bounded_waves",
        "prepared": False,
        "executed": False,
        "rule": "A later technical decision may open a bounded wave; this decision opens no network or package-manager action.",
    },
    {
        "order": 4,
        "stepId": "expand_exact_graph_to_fixed_point",
        "prepared": False,
        "executed": False,
        "rule": "Every new selected tuple requires a new immutable decision version.",
    },
    {
        "order": 5,
        "stepId": "two_pass_source_license_security_review",
        "prepared": False,
        "executed": False,
        "rule": "Review declared build profiles, licenses, network, resolver, TLS, diagnostics, queues, shutdown, native/generated code, and initialization.",
    },
    {
        "order": 6,
        "stepId": "publish_sbom_manifest_and_independent_readback",
        "prepared": False,
        "executed": False,
        "rule": "Closure needs SPDX 2.3, complete source manifest, no unresolved blocker, and manifest-last independent byte readback.",
    },
]


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def strict_equal(actual: Any, expected: Any, path: str) -> None:
    require(type(actual) is type(expected), f"{path}: exact type drift")
    if isinstance(expected, dict):
        require(set(actual) == set(expected), f"{path}: exact key set drift")
        for key in expected:
            strict_equal(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        require(len(actual) == len(expected), f"{path}: list length drift")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            strict_equal(actual_item, expected_item, f"{path}[{index}]")
    else:
        require(actual == expected, f"{path}: exact value drift")


def reject_constant(value: str) -> None:
    raise CheckError(f"non-finite JSON number is forbidden: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"{label}: invalid strict UTF-8 JSON: {exc}") from exc
    require(isinstance(value, dict), f"{label}: top-level JSON must be an object")
    require(text.endswith("\n"), f"{label}: final LF is required")
    return value


def validate_relative_path(relative: str) -> PurePosixPath:
    path = PurePosixPath(relative)
    require(not path.is_absolute(), f"absolute path forbidden: {relative}")
    require(path.parts and all(part not in {"", ".", ".."} for part in path.parts),
            f"unsafe path: {relative}")
    return path


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


class SnapshotEntry:
    """An open, identity-pinned input retained through success emission."""

    def __init__(
        self,
        relative: str,
        target: Path,
        descriptor: int,
        state: tuple[int, int, int, int, int, int, int],
        ancestors: list[tuple[Path, int, int]],
        data: bytes,
    ) -> None:
        self.relative = relative
        self.target = target
        self.descriptor = descriptor
        self.state = state
        self.ancestors = ancestors
        self.data = data


def secure_read(relative: str, maximum_bytes: int) -> SnapshotEntry:
    parts = validate_relative_path(relative).parts
    current = ROOT
    root_info = current.lstat()
    require(stat.S_ISDIR(root_info.st_mode), f"repository root is not a directory: {relative}")
    require(not stat.S_ISLNK(root_info.st_mode), f"repository root symlink forbidden: {relative}")
    identities: list[tuple[Path, int, int]] = [
        (current, root_info.st_dev, root_info.st_ino)
    ]
    for part in parts[:-1]:
        current = current / part
        info = current.lstat()
        require(stat.S_ISDIR(info.st_mode), f"non-directory ancestor: {relative}")
        require(not stat.S_ISLNK(info.st_mode), f"symlink ancestor forbidden: {relative}")
        identities.append((current, info.st_dev, info.st_ino))
    target = ROOT.joinpath(*parts)
    before = target.lstat()
    require(stat.S_ISREG(before.st_mode), f"regular file required: {relative}")
    require(not stat.S_ISLNK(before.st_mode), f"symlink file forbidden: {relative}")
    require(before.st_nlink == 1, f"single-link file required: {relative}")
    before_state = file_state(before)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(target, flags)
    try:
        opened = os.fstat(descriptor)
        require(file_state(opened) == before_state,
                f"file identity changed before read: {relative}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            require(total <= maximum_bytes, f"file exceeds bound: {relative}")
        after = os.fstat(descriptor)
        require(file_state(after) == before_state,
                f"file changed during read: {relative}")
        return SnapshotEntry(
            relative,
            target,
            descriptor,
            before_state,
            identities,
            b"".join(chunks),
        )
    except Exception:
        os.close(descriptor)
        raise


def verify_open_snapshot(entry: SnapshotEntry) -> None:
    opened = os.fstat(entry.descriptor)
    require(file_state(opened) == entry.state,
            f"open file changed after validation: {entry.relative}")
    final = entry.target.lstat()
    require(stat.S_ISREG(final.st_mode),
            f"snapshot path is no longer a regular file: {entry.relative}")
    require(not stat.S_ISLNK(final.st_mode),
            f"snapshot path became a symlink: {entry.relative}")
    require(file_state(final) == entry.state,
            f"snapshot path identity changed after read: {entry.relative}")
    for ancestor, device, inode in entry.ancestors:
        final_ancestor = ancestor.lstat()
        require(stat.S_ISDIR(final_ancestor.st_mode),
                f"snapshot ancestor replaced: {entry.relative}")
        require(not stat.S_ISLNK(final_ancestor.st_mode),
                f"snapshot ancestor became symlink: {entry.relative}")
        require((final_ancestor.st_dev, final_ancestor.st_ino) == (device, inode),
                f"snapshot ancestor identity changed: {entry.relative}")


def close_snapshots(entries: list[SnapshotEntry]) -> None:
    for entry in entries:
        try:
            os.close(entry.descriptor)
        except OSError:
            pass


def validate_portfolio_inventory() -> None:
    base = ROOT.joinpath(*validate_relative_path(ANALYSIS_DIR).parts)
    pending = [base]
    found_dirs: list[str] = []
    found_files: list[str] = []
    while pending:
        current = pending.pop()
        info = current.lstat()
        require(stat.S_ISDIR(info.st_mode),
                f"portfolio directory required: {current.relative_to(ROOT)}")
        require(not stat.S_ISLNK(info.st_mode),
                f"portfolio directory symlink forbidden: {current.relative_to(ROOT)}")
        found_dirs.append(current.relative_to(ROOT).as_posix())
        with os.scandir(current) as scanner:
            for item in scanner:
                path = current / item.name
                item_info = item.stat(follow_symlinks=False)
                relative = path.relative_to(ROOT).as_posix()
                require(not stat.S_ISLNK(item_info.st_mode),
                        f"portfolio symlink forbidden: {relative}")
                if stat.S_ISDIR(item_info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(item_info.st_mode):
                    require(
                        item_info.st_nlink == 1,
                        f"single-link portfolio file required: {relative}",
                    )
                    found_files.append(relative)
                else:
                    raise CheckError(f"unsupported portfolio entry type: {relative}")
    expected_files = tuple(path for path, _, _ in PORTFOLIO_MANIFEST)
    require(tuple(sorted(found_dirs)) == tuple(sorted(EXPECTED_PORTFOLIO_DIRS)),
            "portfolio directory inventory drift")
    require(tuple(sorted(found_files)) == tuple(sorted(expected_files)),
            "portfolio file inventory drift")


def verify_self_binding(document: dict[str, Any], path: str) -> None:
    binding = document.get("contentBinding")
    require(isinstance(binding, dict), f"{path}: contentBinding missing")
    require(binding.get("algorithm") == "sha256", f"{path}: binding algorithm drift")
    require(binding.get("canonicalization") ==
            "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            f"{path}: binding canonicalization drift")
    require(binding.get("scope") == EXPECTED_CONTENT_SCOPE[path],
            f"{path}: binding scope drift")
    body = dict(document)
    body.pop("contentBinding", None)
    digest = sha256(canonical_bytes(body))
    require(digest == EXPECTED_CONTENT[path], f"{path}: recomputed content digest drift")
    require(binding.get("sha256") == digest, f"{path}: embedded content digest drift")


def finding_rows(classifications: dict[str, Any]) -> list[dict[str, Any]]:
    source = classifications.get("candidateClassification", {}).get("findings")
    require(isinstance(source, list) and len(source) == 19,
            "classifications must contain exactly 19 findings")
    rows: list[dict[str, Any]] = []
    for finding in source:
        require(isinstance(finding, dict), "classification finding must be an object")
        rows.append({
            "findingId": finding.get("findingId"),
            "canonicalInvariantId": finding.get("canonicalInvariantId"),
            "finalDisposition": finding.get("finalDisposition"),
            "finalSeverity": finding.get("finalSeverity"),
            "dependencyBlocked": finding.get("dependencyBlocked"),
        })
    require(len({row["findingId"] for row in rows}) == 19, "finding IDs must be unique")
    return rows


def validate_analysis(analysis: dict[str, Any]) -> None:
    require(
        set(analysis)
        == {
            "analysisId",
            "assessment",
            "closure",
            "constraints",
            "documentType",
            "implementationStatus",
            "openQuestions",
            "opportunities",
            "runtimeVerificationStatus",
            "schemaVersion",
            "selection",
            "sourceEvidence",
        },
        "hardening exact top-level schema drift",
    )
    require(analysis.get("documentType") == "codex-security.hardening-analysis",
            "hardening document type drift")
    require(analysis.get("analysisId") ==
            "g2_pion_rung3_patch_dependency_closure_decision_v1",
            "hardening analysis ID drift")
    require(analysis.get("implementationStatus") == "not_implemented",
            "hardening must remain unimplemented")
    require(analysis.get("runtimeVerificationStatus") == "not_executed",
            "hardening must remain unexecuted")
    source = analysis.get("sourceEvidence", {})
    require(
        type(source) is dict
        and set(source)
        == {
            "artifactCount",
            "artifacts",
            "collectionDigestAlgorithm",
            "collectionSha256",
            "kind",
            "label",
            "sourceCompiled",
            "sourceDrift",
            "sourceExecuted",
            "sourceExtracted",
            "sourceLoaded",
            "target",
        },
        "hardening source-evidence schema drift",
    )
    require(source.get("collectionSha256") == EXPECTED_COLLECTION_SHA256,
            "hardening evidence collection drift")
    require(source.get("artifactCount") == 6, "hardening artifact count drift")
    require(source.get("sourceDrift") == "none", "hardening source drift changed")
    for key in (
        "sourceCompiled",
        "sourceExecuted",
        "sourceExtracted",
        "sourceLoaded",
    ):
        strict_equal(source.get(key), False, f"hardening.sourceEvidence.{key}")
    artifacts = source.get("artifacts")
    require(type(artifacts) is list and len(artifacts) == 6,
            "hardening source artifacts drift")
    for index, artifact in enumerate(artifacts):
        require(
            type(artifact) is dict
            and set(artifact) == {"evidenceId", "path", "rawSha256", "role"},
            f"hardening source artifact {index} schema drift",
        )
        require(
            all(type(value) is str for value in artifact.values()),
            f"hardening source artifact {index} type drift",
        )
    assessment = analysis.get("assessment")
    require(
        type(assessment) is dict
        and set(assessment) == {"outcome", "summary"}
        and all(type(value) is str for value in assessment.values()),
        "hardening assessment schema drift",
    )
    constraints = analysis.get("constraints")
    require(
        type(constraints) is dict
        and set(constraints)
        == {"assumptions", "changeHorizons", "nonNegotiables", "profile"},
        "hardening constraints schema drift",
    )
    require(
        type(constraints["profile"]) is str
        and all(
            type(constraints[key]) is list
            for key in ("assumptions", "changeHorizons", "nonNegotiables")
        )
        and all(
            type(item) is str
            for key in ("assumptions", "changeHorizons", "nonNegotiables")
            for item in constraints[key]
        ),
        "hardening constraints type drift",
    )
    require(
        type(analysis.get("openQuestions")) is list
        and all(type(item) is str for item in analysis["openQuestions"]),
        "hardening open-question schema drift",
    )
    opportunities = analysis.get("opportunities")
    require(type(opportunities) is list and
            tuple(item.get("opportunityId") for item in opportunities) ==
            EXPECTED_OPPORTUNITIES,
            "hardening opportunity order or identity drift")
    for opportunity in opportunities:
        require(
            type(opportunity) is dict
            and set(opportunity)
            == {
                "desiredInvariants",
                "diagnosis",
                "evidence",
                "opportunityId",
                "options",
                "proposalPath",
                "recommendation",
                "recommendedOptionId",
                "summary",
                "title",
            },
            "hardening opportunity schema drift",
        )
        require(
            all(
                type(opportunity[key]) is str
                for key in (
                    "diagnosis",
                    "opportunityId",
                    "proposalPath",
                    "recommendation",
                    "recommendedOptionId",
                    "summary",
                    "title",
                )
            ),
            f"{opportunity.get('opportunityId')}: opportunity type drift",
        )
        require(
            type(opportunity["desiredInvariants"]) is list
            and all(
                type(item) is str for item in opportunity["desiredInvariants"]
            ),
            f"{opportunity.get('opportunityId')}: invariant schema drift",
        )
        evidence = opportunity["evidence"]
        evidence_key_sets = {
            frozenset({"claim", "claimType", "path", "sourceKind"}),
            frozenset(
                {"claim", "claimType", "findingId", "path", "sourceKind"}
            ),
            frozenset(
                {"claim", "claimType", "evidenceId", "path", "sourceKind"}
            ),
        }
        require(
            type(evidence) is list
            and all(
                type(item) is dict
                and frozenset(item) in evidence_key_sets
                and all(type(value) is str for value in item.values())
                for item in evidence
            ),
            f"{opportunity.get('opportunityId')}: evidence schema drift",
        )
        options = opportunity.get("options")
        require(type(options) is list and len(options) == 2,
                f"{opportunity.get('opportunityId')}: exactly two options required")
        option_ids = {option.get("optionId") for option in options}
        require(opportunity.get("recommendedOptionId") in option_ids,
                f"{opportunity.get('opportunityId')}: recommendation must name an option")
        for option in options:
            require(
                type(option) is dict
                and set(option)
                == {
                    "diagramPaths",
                    "findingCoverage",
                    "implementationReadiness",
                    "kind",
                    "optionId",
                    "residualRisks",
                    "summary",
                    "title",
                    "tradeoffs",
                },
                f"{opportunity.get('opportunityId')}: option schema drift",
            )
            require(
                all(
                    type(option[key]) is str
                    for key in ("kind", "optionId", "summary", "title")
                ),
                f"{option.get('optionId')}: option type drift",
            )
            diagram_paths = option["diagramPaths"]
            require(
                type(diagram_paths) is dict
                and set(diagram_paths) == {"after", "before"}
                and all(type(value) is str for value in diagram_paths.values()),
                f"{option.get('optionId')}: diagram schema drift",
            )
            tradeoffs = option.get("tradeoffs")
            require(type(tradeoffs) is list, "option tradeoffs missing")
            require({item.get("dimension") for item in tradeoffs} ==
                    EXPECTED_TRADEOFF_DIMENSIONS,
                    f"{option.get('optionId')}: six tradeoff dimensions required")
            require(
                all(
                    type(item) is dict
                    and set(item)
                    == {
                        "assessment",
                        "basis",
                        "confidence",
                        "dimension",
                        "direction",
                        "validationPlan",
                    }
                    and all(type(value) is str for value in item.values())
                    for item in tradeoffs
                ),
                f"{option.get('optionId')}: tradeoff schema drift",
            )
            coverage = option.get("findingCoverage")
            require(type(coverage) is list and coverage,
                    f"{option.get('optionId')}: finding coverage required")
            require(
                all(
                    type(item) is dict
                    and set(item)
                    == {
                        "effect",
                        "findingId",
                        "rationale",
                        "tacticalFixRequired",
                    }
                    and type(item["effect"]) is str
                    and type(item["findingId"]) is str
                    and type(item["rationale"]) is str
                    and type(item["tacticalFixRequired"]) is bool
                    for item in coverage
                ),
                f"{option.get('optionId')}: finding coverage schema drift",
            )
            require(
                type(option["residualRisks"]) is list
                and all(type(item) is str for item in option["residualRisks"]),
                f"{option.get('optionId')}: residual-risk schema drift",
            )
            readiness = option["implementationReadiness"]
            require(
                type(readiness) is dict
                and set(readiness)
                == {
                    "acceptanceCriteria",
                    "affectedComponents",
                    "migrationNotes",
                    "rollback",
                    "workPackages",
                }
                and type(readiness["rollback"]) is str
                and all(
                    type(readiness[key]) is list
                    for key in (
                        "acceptanceCriteria",
                        "affectedComponents",
                        "migrationNotes",
                        "workPackages",
                    )
                )
                and all(
                    type(item) is str
                    for key in (
                        "acceptanceCriteria",
                        "affectedComponents",
                        "migrationNotes",
                        "workPackages",
                    )
                    for item in readiness[key]
                ),
                f"{option.get('optionId')}: implementation-readiness schema drift",
            )
    strict_equal(
        analysis.get("selection"),
        {
            "anyOptionSelected": False,
            "selectedOptionIds": [],
            "implementationPlanCreated": False,
        },
        "hardening.selection",
    )
    strict_equal(
        analysis.get("closure"),
        {
            "findingsClosedByAnalysis": 0,
            "semanticClosureComplete": False,
            "dependencyClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "hardening.closure",
    )
    implementation = ROOT / ANALYSIS_DIR / "implementation"
    require(not implementation.exists(), "implementation directory is forbidden before selection")


def validate_portfolio_semantics(
    raw: dict[str, bytes],
    analysis: dict[str, Any],
) -> None:
    """Bind each reader-facing effect cell to its structured JSON effect."""

    opportunities = analysis["opportunities"]
    for opportunity in opportunities:
        opportunity_id = opportunity["opportunityId"]
        proposal_path = opportunity.get("proposalPath")
        require(isinstance(proposal_path, str),
                f"{opportunity_id}: proposal path missing")
        full_path = f"{ANALYSIS_DIR}/{proposal_path}"
        require(full_path in raw, f"{opportunity_id}: proposal is outside portfolio")
        try:
            proposal = raw[full_path].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CheckError(f"{opportunity_id}: proposal is not UTF-8") from exc
        marker = "## Evidence Coverage And Residual Risk"
        require(proposal.count(marker) == 1,
                f"{opportunity_id}: exactly one coverage section required")
        coverage_section = proposal.split(marker, 1)[1]
        rows: dict[str, tuple[str, str]] = {}
        row_order: list[str] = []
        for line in coverage_section.splitlines():
            if not line.startswith("| `G2SR1-F-"):
                continue
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            require(len(cells) >= 3,
                    f"{opportunity_id}: malformed reader-facing coverage row")
            match = re.match(r"`(G2SR1-F-[0-9a-f]+)`", cells[0])
            require(match is not None,
                    f"{opportunity_id}: malformed coverage finding ID")
            finding_id = match.group(1)
            require(finding_id not in rows,
                    f"{opportunity_id}: duplicate coverage finding {finding_id}")
            rows[finding_id] = (cells[1].casefold(), cells[2].casefold())
            row_order.append(finding_id)

        options = opportunity["options"]
        expected_order = [
            item["findingId"] for item in options[0]["findingCoverage"]
        ]
        require(all(
            [item["findingId"] for item in option["findingCoverage"]]
            == expected_order
            for option in options
        ), f"{opportunity_id}: structured option coverage order drift")
        require(row_order == expected_order,
                f"{opportunity_id}: reader-facing coverage row order drift")
        for option_index, option in enumerate(options):
            for coverage in option["findingCoverage"]:
                finding_id = coverage["findingId"]
                effect = coverage["effect"].casefold()
                require(effect in {"addresses", "mitigates", "unknown"},
                        f"{opportunity_id}: unsupported structured effect {effect}")
                cell = rows[finding_id][option_index]
                leading_effect = re.match(
                    r"(?:\*\*)?(addresses|mitigates|unknown)\b(?:\*\*)?",
                    cell,
                )
                remainder = (
                    cell[leading_effect.end():]
                    if leading_effect is not None
                    else cell
                )
                contradictory_effect = re.search(
                    r"(?:\*\*)?\b(?:addresses|mitigates)\b(?:\*\*)?"
                    r"|\*\*\s*unknown\b\s*\*\*"
                    r"|\b(?:but|yet|although|however)\b"
                    r"[^|]{0,120}\bunknown\b",
                    remainder,
                )
                require(
                    leading_effect is not None
                    and leading_effect.group(1) == effect
                    and contradictory_effect is None,
                        f"{opportunity_id}: {finding_id} option {option_index + 1} "
                        "reader-facing effect drift")


READER_FACING_OVERCLAIM_PATTERNS = (
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
        "Git authority",
        r"(?:"
        r"\bgit (?:writes?|write authority|authority)\b"
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
        "option selection",
        r"\b(?:an|the) option\b[^\n.!?]{0,80}\bselected\b",
    ),
    (
        "implementation plan creation",
        r"\bimplementation plan\b"
        r"[^\n.!?]{0,80}\b(?:created|complete|completed|approved)\b",
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
    (
        "combined Pion/network/Git authority",
        r"\bpion selected;\s*network and git authorized\b",
    ),
)


def validate_reader_facing_nonclaims(normalized_text: str, label: str) -> None:
    flattened = re.sub(r"\s+", " ", normalized_text).strip()
    allowed_auth_mentions = {
        "hardening.md": (
            "external signatures, execution permits, and user action are not prerequisites.",
        ),
        "context.md": (
            "it recommends options but selects none, creates no implementation plan, "
            "and grants no source, dependency, compiler, network, device, git, or "
            "external-authentication authority.",
        ),
    }
    for clause in allowed_auth_mentions[label]:
        require(
            flattened.count(clause) == 1,
            f"{label} explicit non-authentication boundary drift: {clause}",
        )
        flattened = flattened.replace(clause, "", 1)
    require(
        re.search(
            r"\bexternal(?:-|\s+)authentication\b|\buser(?:-|\s+)action\b",
            flattened,
        )
        is None,
        f"{label} ambiguous authentication or user-action mention",
    )
    for claim, pattern in READER_FACING_OVERCLAIM_PATTERNS:
        require(
            re.search(pattern, normalized_text) is None,
            f"{label} contradictory claim: {claim}",
        )


def validate_portfolio_summary(data: bytes) -> None:
    """Reject reader-facing selection, authority, or closure contradictions."""

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError("hardening.md is not UTF-8") from exc
    required = (
        "The evidence contains 19 canonical findings: 7 `patch_required` and 12\n"
        "`unresolved`.",
        "No option is selected, and no `implementation/` directory\nexists.",
        "These are recommendations, not selections.",
        "this review does not.",
    )
    for marker in required:
        require(marker in text, f"hardening.md required boundary drift: {marker}")
    normalized_text = text.casefold()
    validate_reader_facing_nonclaims(normalized_text, "hardening.md")


def validate_context_summary(data: bytes) -> None:
    """Keep the reader-facing evidence context preparation-only."""

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError("context.md is not UTF-8") from exc
    required = (
        "The semantic review contains 19 canonical findings: 7 `patch_required`, 12\n"
        "`unresolved`, and no accepted or false-positive finding.",
        "This analysis closes\nnone of them.",
        "It recommends options but selects none, creates no implementation\n"
        "plan, and grants no source, dependency, compiler, network, device, Git, or\n"
        "external-authentication authority.",
    )
    for marker in required:
        require(marker in text, f"context.md required boundary drift: {marker}")
    normalized_text = text.casefold()
    validate_reader_facing_nonclaims(normalized_text, "context.md")


def validate_archive(decision: dict[str, Any], archive_bytes: bytes) -> None:
    binding = decision.get("archiveBinding", {})
    strict_equal(
        binding,
        {
            "path": ARCHIVE_PATH,
            "rawSha256": EXPECTED_RAW[ARCHIVE_PATH],
            "sourceTreeSha256": EXPECTED_SOURCE_TREE_SHA256,
            "goModRawSha256": EXPECTED_GO_MOD_SHA256,
            "goSumRawSha256": EXPECTED_GO_SUM_SHA256,
            "sourceExtracted": False,
            "sourceCompiled": False,
            "sourceLoaded": False,
            "sourceExecuted": False,
        },
        "decision.archiveBinding",
    )
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
        names = set(archive.namelist())
        require(GO_MOD_ENTRY in names and GO_SUM_ENTRY in names,
                "root module metadata missing from retained archive")
        go_mod = archive.read(GO_MOD_ENTRY)
        go_sum = archive.read(GO_SUM_ENTRY)
    require(sha256(go_mod) == EXPECTED_GO_MOD_SHA256, "go.mod byte digest drift")
    require(sha256(go_sum) == EXPECTED_GO_SUM_SHA256, "go.sum byte digest drift")
    require(binding.get("goModRawSha256") == EXPECTED_GO_MOD_SHA256,
            "go.mod decision binding drift")
    require(binding.get("goSumRawSha256") == EXPECTED_GO_SUM_SHA256,
            "go.sum decision binding drift")

    seed = decision.get("dependencySeed", {})
    strict_equal(
        seed,
        {
            "goVersion": "1.24.0",
            "requirements": [
                {"module": module, "version": version, "direct": direct}
                for module, version, direct in EXPECTED_REQUIREMENTS
            ],
            "requirementCount": 19,
            "directRequirementCount": 10,
            "indirectRequirementCount": 9,
            "goSumRecordCount": 44,
            "goSumModuleVersionTupleCount": 23,
            "goSumSourceHashCount": 21,
            "goSumGoModHashCount": 23,
            "checksumOnlyContextTuples": [
                {"module": module, "version": version, "selected": False}
                for module, version in EXPECTED_CHECKSUM_ONLY
            ],
            "inventoryOnlyNoDependencyAcquisition": True,
            "rootMetadataProvesCompleteGraph": False,
        },
        "decision.dependencySeed",
    )
    rows = seed.get("requirements")
    require(isinstance(rows, list), "dependency requirement seed missing")
    normalized = tuple((row.get("module"), row.get("version"), row.get("direct"))
                       for row in rows)
    require(normalized == EXPECTED_REQUIREMENTS, "exact 19-requirement seed drift")
    require(seed.get("goVersion") == "1.24.0", "Go version seed drift")
    require(seed.get("requirementCount") == 19, "requirement count drift")
    require(seed.get("directRequirementCount") == 10, "direct count drift")
    require(seed.get("indirectRequirementCount") == 9, "indirect count drift")
    lines = [line.split() for line in go_sum.decode("utf-8").splitlines()]
    require(len(lines) == 44 and all(len(line) == 3 for line in lines),
            "go.sum record structure drift")
    tuples = {(line[0], line[1].removesuffix("/go.mod")) for line in lines}
    source_count = sum(not line[1].endswith("/go.mod") for line in lines)
    mod_count = sum(line[1].endswith("/go.mod") for line in lines)
    require((len(tuples), source_count, mod_count) == (23, 21, 23),
            "go.sum tuple/source/go.mod counts drift")
    require((seed.get("goSumRecordCount"), seed.get("goSumModuleVersionTupleCount"),
             seed.get("goSumSourceHashCount"), seed.get("goSumGoModHashCount")) ==
            (44, 23, 21, 23), "decision go.sum counts drift")
    context = seed.get("checksumOnlyContextTuples")
    require(isinstance(context, list), "checksum-only context missing")
    require(tuple((row.get("module"), row.get("version")) for row in context) ==
            EXPECTED_CHECKSUM_ONLY, "checksum-only tuple quarantine drift")
    require(all(row.get("selected") is False for row in context),
            "checksum-only tuple must remain unselected")
    require(seed.get("inventoryOnlyNoDependencyAcquisition") is True,
            "inventory-only boundary drift")
    require(seed.get("rootMetadataProvesCompleteGraph") is False,
            "root metadata must not claim graph closure")


def validate_decision(
    decision: dict[str, Any],
    classifications: dict[str, Any],
    analysis: dict[str, Any],
) -> None:
    require(set(decision) == EXPECTED_DECISION_KEYS,
            "decision top-level key set drift")
    require(decision.get("documentType") ==
            "aetherlink.g2-pion-rung3-patch-and-dependency-closure-decision",
            "decision document type drift")
    require(decision.get("schemaVersion") == "1.0", "decision schema drift")
    require(decision.get("status") ==
            "prepared_options_unselected_dependency_closure_blocked",
            "decision status drift")
    binding = decision.get("contentBinding")
    require(isinstance(binding, dict), "decision content binding missing")
    require(binding.get("algorithm") == "sha256" and
            binding.get("canonicalization") ==
            "utf8_ascii_escaped_sorted_keys_compact_single_lf" and
            binding.get("scope") == "decision_without_contentBinding",
            "decision content-binding contract drift")
    body = dict(decision)
    body.pop("contentBinding", None)
    require(binding.get("sha256") == sha256(canonical_bytes(body)),
            "decision self-binding drift")

    strict_equal(
        decision.get("predecessorBindings"),
        {
            key: {
                "path": path,
                "rawSha256": EXPECTED_RAW[path],
                "contentSha256": EXPECTED_CONTENT[path],
            }
            for key, path in (
                ("classifications", CLASSIFICATIONS_PATH),
                ("result", RESULT_PATH),
                ("manifest", MANIFEST_PATH),
            )
        },
        "decision.predecessorBindings",
    )

    strict_equal(
        decision.get("analysisBinding"),
        {
            "path": ANALYSIS_PATH,
            "rawSha256": EXPECTED_RAW[ANALYSIS_PATH],
            "analysisId": "g2_pion_rung3_patch_dependency_closure_decision_v1",
            "evidenceCollectionSha256": EXPECTED_COLLECTION_SHA256,
            "opportunityIds": list(EXPECTED_OPPORTUNITIES),
            "recommendationsAreSelections": False,
        },
        "decision.analysisBinding",
    )

    expected_findings = finding_rows(classifications)
    strict_equal(
        decision.get("findingSet"),
        {
            "count": 19,
            "findings": expected_findings,
            "dispositionCounts": {"patch_required": 7, "unresolved": 12},
            "severityCounts": {
                "P0": 0,
                "P1": 11,
                "P2": 3,
                "P3": 4,
                "none": 1,
            },
        },
        "decision.findingSet",
    )

    source_findings = classifications["candidateClassification"]["findings"]
    expected_treatments: list[dict[str, Any]] = []
    for finding in source_findings:
        finding_id = finding["findingId"]
        units = list(finding["patchUnits"])
        if finding_id in DEPENDENCY_FINDINGS:
            units.append(DEPENDENCY_OPTION)
        expected_treatments.append({
            "findingId": finding_id,
            "status": "deferred_not_resolved_by_preparation",
            "patchUnitIds": units,
            "preservationRequired": finding_id in PRESERVE_FINDINGS,
            "assuranceBoundary": finding_id in ASSURANCE_FINDINGS,
        })
    strict_equal(
        decision.get("treatments"),
        expected_treatments,
        "decision.treatments",
    )

    options = decision.get("options")
    require(isinstance(options, list) and
            tuple(item.get("optionId") for item in options) == OPTION_IDS,
            "exact eight option identities or order drift")
    reverse: dict[str, list[str]] = {option_id: [] for option_id in OPTION_IDS}
    for treatment in expected_treatments:
        for option_id in treatment["patchUnitIds"]:
            reverse[option_id].append(treatment["findingId"])
    for index, option in enumerate(options):
        option_id = OPTION_IDS[index]
        strict_equal(
            option,
            {
                "optionId": option_id,
                "kind": (
                    "dependency_review_unit"
                    if option_id == DEPENDENCY_OPTION
                    else "root_patch_unit"
                ),
                "selected": False,
                "implementationPrepared": False,
                "findingIds": reverse[option_id],
            },
            f"decision.options[{index}]",
        )

    selection = decision.get("selection", {})
    strict_equal(
        selection,
        {
            "anyOptionSelected": False,
            "selectedOptionIds": [],
            "implementationPlanCreated": False,
            "patchSeriesCreated": False,
            "dependencyAcquisitionDecisionCreated": False,
        },
        "decision.selection",
    )
    strict_equal(decision.get("authority"), EXPECTED_AUTHORITY,
                 "decision.authority")
    strict_equal(decision.get("closure"), EXPECTED_CLOSURE,
                 "decision.closure")
    strict_equal(decision.get("nonClaims"), EXPECTED_NONCLAIMS,
                 "decision.nonClaims")
    sequence = decision.get("dependencyClosureSequence")
    strict_equal(sequence, EXPECTED_DEPENDENCY_SEQUENCE,
                 "decision.dependencyClosureSequence")
    require(decision.get("result") ==
            "four_structural_recommendations_and_eight_unselected_treatment_units_prepared_all_19_findings_remain_open",
            "decision result drift")
    require(decision.get("nextAction") ==
            "prepare_separate_versioned_implementation_or_dependency_review_decision",
            "decision next action drift")
    validate_analysis(analysis)


def main() -> int:
    snapshots: list[SnapshotEntry] = []
    try:
        validate_portfolio_inventory()
        limits = {
            DECISION_PATH: 2_000_000,
            CLASSIFICATIONS_PATH: 2_000_000,
            RESULT_PATH: 2_000_000,
            MANIFEST_PATH: 2_000_000,
            ARCHIVE_PATH: 1_000_000,
        }
        for path, _, _ in PORTFOLIO_MANIFEST:
            limits[path] = 2_000_000
        for path, maximum_bytes in limits.items():
            snapshots.append(secure_read(path, maximum_bytes))
        raw = {entry.relative: entry.data for entry in snapshots}
        archive_bytes = raw[ARCHIVE_PATH]
        for path in (
            DECISION_PATH,
            CLASSIFICATIONS_PATH,
            RESULT_PATH,
            MANIFEST_PATH,
            ANALYSIS_PATH,
        ):
            require(sha256(raw[path]) == EXPECTED_RAW[path],
                    f"raw byte digest drift: {path}")
        require(sha256(archive_bytes) == EXPECTED_RAW[ARCHIVE_PATH],
                "retained archive raw byte digest drift")
        for path, expected_size, expected_digest in PORTFOLIO_MANIFEST:
            require(len(raw[path]) == expected_size,
                    f"portfolio byte-size drift: {path}")
            require(sha256(raw[path]) == expected_digest,
                    f"portfolio raw byte digest drift: {path}")

        decision = parse_json(raw[DECISION_PATH], DECISION_PATH)
        classifications = parse_json(raw[CLASSIFICATIONS_PATH], CLASSIFICATIONS_PATH)
        result = parse_json(raw[RESULT_PATH], RESULT_PATH)
        manifest = parse_json(raw[MANIFEST_PATH], MANIFEST_PATH)
        analysis = parse_json(raw[ANALYSIS_PATH], ANALYSIS_PATH)
        for path, document in (
            (CLASSIFICATIONS_PATH, classifications),
            (RESULT_PATH, result),
            (MANIFEST_PATH, manifest),
        ):
            verify_self_binding(document, path)
        validate_decision(decision, classifications, analysis)
        validate_portfolio_semantics(raw, analysis)
        validate_portfolio_summary(raw[f"{ANALYSIS_DIR}/hardening.md"])
        validate_context_summary(raw[f"{ANALYSIS_DIR}/context.md"])
        validate_archive(decision, archive_bytes)

        # Keep every input descriptor open and prove that both the open object
        # and its repository path still identify the validated bytes.  The
        # inventory barrier also rejects late-added authority/source/staging
        # artifacts.  Repeating identity checks after inventory closes the
        # practical replace-after-read window exercised by the mutation tests.
        for entry in snapshots:
            verify_open_snapshot(entry)
        validate_portfolio_inventory()
        for entry in snapshots:
            verify_open_snapshot(entry)

        print(
            "G2 Pion patch/dependency decision preparation verified "
            "(immutable 19-file portfolio, 19 open findings, 8 unselected units, "
            "19 root requirements; no implementation, acquisition, network, Git, authentication, or user action)."
        )
        return 0
    except (CheckError, OSError, zipfile.BadZipFile, KeyError, TypeError, ValueError) as exc:
        print(f"G2 Pion patch/dependency decision preparation FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        close_snapshots(snapshots)


if __name__ == "__main__":
    raise SystemExit(main())
