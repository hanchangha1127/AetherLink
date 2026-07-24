#!/usr/bin/env python3
"""Mutation tests for the archive-incapable G2 rung-three preparation checker."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung3_review_decision.py"
SPEC = importlib.util.spec_from_file_location("g2_rung3_preparation_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to import G2 rung-three preparation checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


class FixtureRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write_bytes(self, relative: str, data: bytes) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def write_json(self, relative: str, value: object) -> None:
        self.write_bytes(relative, json_bytes(value))

    def read_json(self, relative: str) -> dict[str, object]:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def binding(self, relative: str, *, semantic: bool = True, collection: bool = False) -> dict[str, object]:
        raw = (self.root / relative).read_bytes()
        result: dict[str, object] = {"path": relative, "sha256": CHECKER.sha256_bytes(raw)}
        parsed: object | None = None
        if relative.endswith(".json"):
            parsed = json.loads(raw)
        if semantic:
            result["semanticSha256"] = CHECKER.semantic_sha256(relative, raw, parsed)
        if collection:
            assert isinstance(parsed, dict)
            result["collectionSha256"] = parsed["collectionSha256"]
        return result

    def manifest(self, paths: tuple[str, ...], predecessor: str, start: int) -> dict[str, object]:
        identity = CHECKER.MANIFEST_IDENTITY[start == 8]
        expected = {
            path: (evidence_id, role)
            for evidence_id, path, role in (*CHECKER.V1_ARTIFACTS, *CHECKER.V2_ARTIFACTS)
        }
        artifacts = []
        for offset, relative in enumerate(paths):
            evidence_id, role = expected[relative]
            artifacts.append(
                {
                    "evidenceId": evidence_id,
                    "path": relative,
                    "sha256": CHECKER.sha256_bytes((self.root / relative).read_bytes()),
                    "role": role,
                }
            )
        return {
            "documentType": identity["documentType"],
            "schemaVersion": identity["schemaVersion"],
            "manifestId": identity["manifestId"],
            "recordedDate": identity["recordedDate"],
            "status": CHECKER.EXPECTED_STATUS,
            "result": CHECKER.EXPECTED_RESULT,
            "nextAction": CHECKER.EXPECTED_NEXT,
            "predecessorManifestBinding": self.binding(predecessor, collection=True),
            "artifactScope": identity["artifactScope"],
            "orderingRule": identity["orderingRule"],
            "collectionDigestAlgorithm": identity["collectionDigestAlgorithm"],
            "artifactCount": len(artifacts),
            "artifacts": artifacts,
            "collectionSha256": CHECKER.collection_sha256(artifacts),
            "sourceReviewPerformed": False,
            "reviewExecutionAuthorized": False,
            "evidenceBasis": CHECKER.EVIDENCE_BASIS,
            "archiveRetained": True,
            "archiveReadByRungThree": False,
            "archiveMaterializedByRungThree": False,
            "candidateSelected": False,
            "librarySelected": False,
            "dependencyInstalled": False,
            "compilerInvoked": False,
            "socketCreated": False,
            "networkUsed": False,
            "gitOperationPerformed": False,
            "deviceOperationPerformed": False,
            "externalIdentityProofRequired": False,
            "userActionRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "productEndpointAuthenticationRequired": True,
        }


def make_fixture(root: Path) -> FixtureRepository:
    fixture = FixtureRepository(root)
    current_text = (
        f"current {CHECKER.EXPECTED_STATUS} {CHECKER.EXPECTED_RESULT} "
        f"{CHECKER.EXPECTED_NEXT}. only at_that_checkpoint "
        "recordedNextActionAtThatCheckpoint="
        "prepare_versioned_rung3_offline_source_review_decision.\n"
    ).encode("utf-8")
    for relative in CHECKER.CANONICAL_DOCS:
        fixture.write_bytes(relative, current_text)

    old_documents = [
        {"path": path, "sha256": f"{index + 1:064x}", "role": "old"}
        for index, path in enumerate(CHECKER.CANONICAL_DOCS)
    ]
    fixture.write_json(
        CHECKER.RUNG2_SUPERSESSION_V2,
        {
            "documentType": "aetherlink.g2-canonical-document-supersession",
            "currentDocumentState": {"documents": old_documents},
        },
    )
    fixture.write_json(CHECKER.PROFILE, {"documentType": "fixture-profile", "profile": "restricted"})
    fixture.write_json(CHECKER.RECEIPT, {"documentType": "fixture-receipt", "archive": {"retained": True}})
    fixture.write_json(CHECKER.RUNG2_PROGRESS, {"documentType": "fixture-rung2-progress"})
    fixture.write_json(CHECKER.RUNG2_MANIFEST_V3, {"documentType": "fixture-manifest-v3", "collectionSha256": "3" * 64})
    fixture.write_json(CHECKER.RUNG2_MANIFEST_V5, {"documentType": "fixture-manifest-v5", "collectionSha256": "5" * 64})

    policy = {
        "documentType": "aetherlink.g2-rung3-review-decision-preparation-policy",
        "schemaVersion": "1.0",
        "status": "preparation_only_archive_capability_absent",
        "evidenceBasis": CHECKER.EVIDENCE_BASIS,
        "generatorPolicy": {
            "path": CHECKER.PREPARER,
            "allowedCliModes": ["--check", "--emit-decision"],
            "fileReadAllowlist": [],
            "fileWriteAllowlist": [],
        },
        "checkerPolicy": {
            "path": CHECKER.CHECKER,
            "trackedReadAllowlist": sorted(CHECKER.TRACKED_READ_ALLOWLIST),
            "fileWriteAllowlist": [],
            "archiveReadAllowed": False,
            "sourceTreeReadAllowed": False,
            "buildDirectoryReadAllowed": False,
            "symlinkReadAllowed": False,
            "subprocessAllowed": False,
            "networkAllowed": False,
            "gitAllowed": False,
        },
        "deniedPathRules": {
            "absolutePathInputsAllowed": False,
            "parentTraversalAllowed": False,
            "backslashPathSeparatorsAllowed": False,
            "buildPrefixAllowed": False,
            "archiveSuffixesAllowed": False,
        },
        "zeroOperationCounters": {key: 0 for key in CHECKER.POLICY_ZERO_COUNTERS},
        "executionBoundary": {
            "reviewPlanPreparationAllowed": True,
            "reviewExecutionAuthorized": False,
            "archiveReadAllowed": False,
            "sourceReviewPerformed": False,
            "gitOperationAllowed": False,
            "externalIdentityProofRequired": False,
            "userActionRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "productEndpointAuthenticationRequired": True,
        },
    }
    fixture.write_json(CHECKER.POLICY, policy)
    fixture.write_bytes(
        CHECKER.PREPARER,
        b"import argparse\n"
        b"def main():\n"
        b"    parser = argparse.ArgumentParser()\n"
        b"    parser.add_argument('--check', action='store_true')\n"
        b"    parser.add_argument('--emit-decision', action='store_true')\n"
        b"    return parser\n",
    )
    fixture.write_bytes(CHECKER.PREPARER_TEST, b"# fixture preparer tests\n")
    fixture.write_bytes(CHECKER.CHECKER, b"# fixture checker\n")
    fixture.write_bytes(CHECKER.CHECKER_TEST, b"# fixture checker tests\n")

    parent_paths = (
        CHECKER.PROFILE,
        CHECKER.RECEIPT,
        CHECKER.RUNG2_PROGRESS,
        CHECKER.RUNG2_MANIFEST_V3,
        CHECKER.RUNG2_SUPERSESSION_V2,
        CHECKER.RUNG2_MANIFEST_V5,
        CHECKER.POLICY,
    )
    decision: dict[str, object] = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-decision",
        "schemaVersion": "1.0",
        "decisionId": "g2-pion-ice-v4.3.0-offline-source-review-decision-v1",
        "recordedDate": "2026-07-23",
        "status": CHECKER.EXPECTED_STATUS,
        "result": CHECKER.EXPECTED_RESULT,
        "nextAction": CHECKER.EXPECTED_NEXT,
        "policyBinding": fixture.binding(CHECKER.POLICY),
        "predecessorBindings": [fixture.binding(path) for path in parent_paths],
        "forwardOnlyBindings": {
            "manifest": {"path": CHECKER.MANIFEST_V1, "binding": "forward_identity_only_no_sha256"},
            "progress": {"path": CHECKER.PROGRESS, "binding": "forward_identity_only_no_sha256"},
        },
        "archiveBinding": {
            "receiptPath": CHECKER.RECEIPT,
            "archiveMetadataJsonPointer": "/archive",
            "archiveEvidenceId": "G2R2E009",
            "archivePathCopiedIntoDecision": False,
            "expectedBytes": 293023,
            "entryCount": 129,
            "fileCount": 129,
            "totalUncompressedBytes": 1131286,
            "rawSha256": "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
            "moduleH1": "h1:X8l4s9zV2HeTKX33nulWAFXAEo5KhIVzOsY62/3t/LM=",
            "goModH1": "h1:obAyD+J+Hzs7QA7Y8YXHp5uIn6gb7z87pKedXZkrcFU=",
            "modulePath": "github.com/pion/ice/v4",
            "version": "v4.3.0",
            "tag": "v4.3.0",
            "commitSha1": "1e8716372f2bb52e45bf2a7172e4fb1004251c46",
            "treeSha1": "df59c87a634cfea261582cd9932554663112a975",
            "archiveReadByThisDecision": False,
            "archiveMaterializedByThisDecision": False,
            "sourceReviewedByThisDecision": False,
        },
        "preparationScope": {
            "evidenceBasis": "static_contract_and_mock_isolation_tests_not_os_sandbox_attestation",
            "repositoryFilesRead": 0,
            "repositoryFilesWritten": 0,
            "archiveBytesRead": 0,
        },
        "futureExecutionPermitRequirements": {"separateVersionedPermitRequired": True},
        "futureExecutionProhibitions": {"networkSocketOrDns": True},
        "plannedStaticReview": {
            "patchUnits": list(CHECKER.EXPECTED_PATCH_UNITS),
            "profileVerificationUnits": [
                {"id": item, "status": "planned_not_performed"}
                for item in CHECKER.EXPECTED_VERIFICATION_IDS
            ],
        },
        "personalProjectBoundary": {"noAuthenticationOrUserActionRequested": True},
        "decisionBoundary": {
            "reviewExecutionAuthorized": False,
            "archiveRead": False,
            "archiveMaterialized": False,
            "sourceReviewed": False,
            "compilerInvoked": False,
            "networkUsed": False,
            "gitOperationPerformed": False,
            "repositoryOwnerAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "userActionRequired": False,
        },
    }
    core = dict(decision)
    decision["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": CHECKER.sha256_bytes(CHECKER.canonical_json_bytes(core)),
    }
    fixture.write_json(CHECKER.DECISION, decision)

    fixture.write_json(
        CHECKER.PROGRESS,
        {
            "documentType": "aetherlink.g2-rung3-offline-source-review-progress",
            "schemaVersion": "1.0",
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v1",
            "recordedDate": "2026-07-23",
            "status": CHECKER.EXPECTED_STATUS,
            "result": CHECKER.EXPECTED_RESULT,
            "nextAction": CHECKER.EXPECTED_NEXT,
            "evidenceBasis": {
                "kind": CHECKER.EVIDENCE_BASIS,
                "actualArchiveAccessEvidencePresent": False,
                "operatingSystemSandboxAttestationPresent": False,
            },
            "decisionBinding": fixture.binding(CHECKER.DECISION),
            "policyBinding": fixture.binding(CHECKER.POLICY),
            "preparationToolBinding": {
                "generatorPath": CHECKER.PREPARER,
                "generatorRawSha256": CHECKER.sha256_bytes((root / CHECKER.PREPARER).read_bytes()),
                "testPath": CHECKER.PREPARER_TEST,
                "testRawSha256": CHECKER.sha256_bytes((root / CHECKER.PREPARER_TEST).read_bytes()),
                "offlineTestCount": 15,
                "offlineTestsPassed": True,
            },
            "predecessorBindings": [
                fixture.binding(CHECKER.RUNG2_SUPERSESSION_V2),
                fixture.binding(CHECKER.RUNG2_MANIFEST_V5, collection=True),
            ],
            "archiveState": {
                "receiptPath": CHECKER.RECEIPT,
                "archiveMetadataJsonPointer": "/archive",
                "archiveEvidenceId": "G2R2E009",
                "archivePathCopiedIntoProgress": False,
                "expectedBytes": 293023,
                "rawSha256": "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
                "archiveOpenedByRungThree": False,
                "archiveReadByRungThree": False,
                "archiveMaterializedByRungThree": False,
                "sourceReviewedByRungThree": False,
            },
            "plannedVerification": [
                {"id": item, "status": "planned_not_performed"}
                for item in CHECKER.EXPECTED_VERIFICATION_IDS
            ],
            "zeroOperationCounters": {
                "counterScope": "rung3_review_execution_not_documentation_artifact_creation_or_checker_reads",
                **{key: 0 for key in CHECKER.PROGRESS_ZERO_COUNTERS},
            },
            "executionBoundary": {
                "reviewExecutionAuthorized": False,
                "sourceReviewPerformed": False,
                "archiveReadAllowed": False,
                "repositoryOwnerAuthenticationRequired": False,
                "externalIdentityProofRequired": False,
                "userActionRequired": False,
            },
            "forwardOnlyBindings": {"manifest": {"path": CHECKER.MANIFEST_V1}},
            "personalProjectBoundary": {"noAuthenticationOrUserActionRequested": True},
        },
    )
    fixture.write_json(
        CHECKER.MANIFEST_V1,
        fixture.manifest(CHECKER.V1_ROWS, CHECKER.RUNG2_MANIFEST_V5, 1),
    )

    current_documents = []
    for relative in CHECKER.CANONICAL_DOCS:
        binding = fixture.binding(relative)
        binding["role"] = "current"
        current_documents.append(binding)
    supersession = {
        "documentType": "aetherlink.g2-canonical-document-supersession",
        "schemaVersion": "1.0",
        "supersessionId": "g2-pion-rung3-canonical-document-supersession-v1",
        "recordedDate": "2026-07-23",
        "status": CHECKER.EXPECTED_STATUS,
        "result": CHECKER.EXPECTED_RESULT,
        "nextAction": CHECKER.EXPECTED_NEXT,
        "reason": "fixture",
        "predecessorSupersessionBinding": fixture.binding(CHECKER.RUNG2_SUPERSESSION_V2),
        "predecessorManifestBinding": fixture.binding(CHECKER.RUNG2_MANIFEST_V5, collection=True),
        "preparationDecisionBinding": fixture.binding(CHECKER.DECISION),
        "preparationProgressBinding": fixture.binding(CHECKER.PROGRESS),
        "previousDocumentState": {"documents": old_documents},
        "currentDocumentState": {
            "status": CHECKER.EXPECTED_STATUS,
            "result": CHECKER.EXPECTED_RESULT,
            "nextAction": CHECKER.EXPECTED_NEXT,
            "documents": current_documents,
        },
        "semanticGuard": {
            "scope": list(CHECKER.CANONICAL_DOCS),
            "historicalCheckpointToken": "at_that_checkpoint",
            "requiredCurrentStatus": CHECKER.EXPECTED_STATUS,
            "requiredCurrentResult": CHECKER.EXPECTED_RESULT,
            "requiredCurrentNextAction": CHECKER.EXPECTED_NEXT,
            "historicalNextActionKey": "recordedNextActionAtThatCheckpoint",
            "historicalNextAction": "prepare_versioned_rung3_offline_source_review_decision",
            "historicalNextActionOccurrencePerDocument": 1,
        },
        "executionBoundary": {
            "archiveReadAllowed": False,
            "sourceReviewPerformed": False,
            "reviewExecutionAuthorized": False,
            "repositoryOwnerAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "userActionRequired": False,
            "rungThreeReviewPlanPreparationRecorded": True,
        },
    }
    fixture.write_json(CHECKER.SUPERSESSION, supersession)
    manifest_v2 = fixture.manifest(CHECKER.V2_ROWS, CHECKER.MANIFEST_V1, 8)
    manifest_v2["semanticBindings"] = [
        {"path": path, "semanticSha256": fixture.binding(path)["semanticSha256"]}
        for path in CHECKER.CANONICAL_DOCS
    ]
    manifest_v2["preparationBindings"] = {
        "decision": fixture.binding(CHECKER.DECISION),
        "progress": fixture.binding(CHECKER.PROGRESS),
        "policy": fixture.binding(CHECKER.POLICY),
        "canonicalSupersession": fixture.binding(CHECKER.SUPERSESSION),
    }
    fixture.write_json(CHECKER.MANIFEST_V2, manifest_v2)
    return fixture


class G2PionRungThreePreparationCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = make_fixture(self.root)

    def assert_rejected(self) -> None:
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.check_repository(self.root, enforce_pinned_identity=False)

    def mutate_json(self, relative: str, callback: object) -> None:
        document = self.fixture.read_json(relative)
        callback(document)  # type: ignore[operator]
        self.fixture.write_json(relative, document)

    def test_01_complete_fixture_passes_without_archive_or_build_artifact(self) -> None:
        result = CHECKER.check_repository(self.root, enforce_pinned_identity=False)
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["pinnedIdentityEnforced"])
        self.assertFalse(result["archiveRead"])
        self.assertFalse(result["buildDirectoryRead"])
        self.assertFalse(result["repositoryOwnerAuthenticationRequired"])
        self.assertFalse(result["externalIdentityProofRequired"])
        self.assertTrue(result["productEndpointAuthenticationRequired"])
        self.assertNotIn("authenticationRequired", result)

    def test_02_checker_source_has_no_archive_process_network_or_dynamic_import(self) -> None:
        tree = ast.parse(CHECKER_PATH.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint({"importlib", "socket", "subprocess", "zipfile"}))

    def test_03_reader_rejects_unlisted_traversal_absolute_build_and_archive_paths(self) -> None:
        for path in ("unlisted.txt", "../README.md", "/README.md", "build/x", "x.zip"):
            with self.subTest(path=path), self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeTrackedReader(self.root).read(path)

    def test_04_component_symlink_is_rejected_by_no_follow_open(self) -> None:
        real_docs = self.root / "real-docs"
        real_docs.mkdir()
        (real_docs / "roadmap.md").write_text("safe\n", encoding="utf-8")
        docs = self.root / "docs"
        for child in tuple(docs.iterdir()):
            if child.is_dir():
                continue
        renamed = self.root / "docs-original"
        docs.rename(renamed)
        docs.symlink_to(renamed, target_is_directory=True)
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.SafeTrackedReader(self.root).read("docs/roadmap.md")

    def test_05_duplicate_json_key_is_rejected(self) -> None:
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.strict_json(b'{"a":1,"a":2}\n', "fixture.json")

    def test_06_nonfinite_json_number_is_rejected(self) -> None:
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.strict_json(b'{"a":NaN}\n', "fixture.json")

    def test_07_decision_content_digest_mutation_is_rejected(self) -> None:
        self.mutate_json(CHECKER.DECISION, lambda value: value["contentBinding"].update({"sha256": "0" * 64}))
        self.assert_rejected()

    def test_08_decision_archive_path_copy_is_rejected(self) -> None:
        self.mutate_json(CHECKER.DECISION, lambda value: value.update({"note": "build/archive.zip"}))
        self.assert_rejected()

    def test_09_nonzero_execution_counter_is_rejected(self) -> None:
        self.mutate_json(CHECKER.DECISION, lambda value: value["preparationScope"].update({"archiveBytesRead": 1}))
        self.assert_rejected()

    def test_10_true_review_execution_boundary_is_rejected(self) -> None:
        self.mutate_json(CHECKER.PROGRESS, lambda value: value["executionBoundary"].update({"reviewExecutionAuthorized": True}))
        self.assert_rejected()

    def test_11_generator_forbidden_import_is_rejected(self) -> None:
        path = self.root / CHECKER.PREPARER
        path.write_bytes(b"import socket\n" + path.read_bytes())
        self.assert_rejected()

    def test_12_generator_forbidden_call_is_rejected(self) -> None:
        path = self.root / CHECKER.PREPARER
        path.write_bytes(path.read_bytes() + b"open('x')\n")
        self.assert_rejected()

    def test_13_generator_extra_cli_surface_is_rejected(self) -> None:
        path = self.root / CHECKER.PREPARER
        path.write_bytes(path.read_bytes().replace(b"    return parser\n", b"    parser.add_argument('--archive')\n    return parser\n"))
        self.assert_rejected()

    def test_14_manifest_row_reordering_is_rejected(self) -> None:
        self.mutate_json(CHECKER.MANIFEST_V1, lambda value: value["artifacts"].reverse())
        self.assert_rejected()

    def test_15_manifest_identity_collection_and_nested_authority_mutations_are_rejected(self) -> None:
        mutations = (
            (CHECKER.MANIFEST_V1, "schemaVersion", "2.0"),
            (CHECKER.MANIFEST_V1, "manifestId", "drifted-v1"),
            (CHECKER.MANIFEST_V1, "recordedDate", "2026-07-24"),
            (CHECKER.MANIFEST_V1, "artifactScope", "expanded_scope"),
            (CHECKER.MANIFEST_V2, "orderingRule", "descending_evidence_id"),
            (CHECKER.MANIFEST_V2, "collectionDigestAlgorithm", "sha256_other"),
            (CHECKER.MANIFEST_V2, "collectionSha256", "0" * 64),
        )
        for path, key, replacement in mutations:
            with self.subTest(path=path, key=key):
                original = self.fixture.read_json(path)
                changed = copy.deepcopy(original)
                changed[key] = replacement
                self.fixture.write_json(path, changed)
                self.assert_rejected()
                self.fixture.write_json(path, original)

        manifest_v1 = self.fixture.read_json(CHECKER.MANIFEST_V1)
        manifest_v1["predecessorManifestBinding"][
            "repositoryOwnerAuthenticationRequired"
        ] = True
        self.fixture.write_json(CHECKER.MANIFEST_V1, manifest_v1)
        manifest_v2 = self.fixture.read_json(CHECKER.MANIFEST_V2)
        manifest_v2["predecessorManifestBinding"] = self.fixture.binding(
            CHECKER.MANIFEST_V1, collection=True
        )
        self.fixture.write_json(CHECKER.MANIFEST_V2, manifest_v2)
        self.assert_rejected()

    def test_16_manifest_artifact_raw_hash_mutation_is_rejected(self) -> None:
        self.mutate_json(CHECKER.MANIFEST_V1, lambda value: value["artifacts"][0].update({"sha256": "0" * 64}))
        self.assert_rejected()

    def test_17_progress_decision_semantic_hash_mutation_is_rejected(self) -> None:
        self.mutate_json(CHECKER.PROGRESS, lambda value: value["decisionBinding"].update({"semanticSha256": "0" * 64}))
        self.assert_rejected()

    def test_18_supersession_current_raw_hash_mutation_is_rejected(self) -> None:
        self.mutate_json(CHECKER.SUPERSESSION, lambda value: value["currentDocumentState"]["documents"][0].update({"sha256": "0" * 64}))
        self.assert_rejected()

    def test_19_supersession_current_semantic_hash_mutation_is_rejected(self) -> None:
        self.mutate_json(CHECKER.SUPERSESSION, lambda value: value["currentDocumentState"]["documents"][0].update({"semanticSha256": "0" * 64}))
        self.assert_rejected()

    def test_20_semantic_guard_scope_mutation_is_rejected(self) -> None:
        self.mutate_json(CHECKER.SUPERSESSION, lambda value: value["semanticGuard"]["scope"].pop())
        self.assert_rejected()

    def test_21_missing_current_document_token_is_rejected(self) -> None:
        (self.root / CHECKER.CANONICAL_DOCS[0]).write_text("stale wording only\n", encoding="utf-8")
        self.assert_rejected()

    def test_22_owner_authentication_requirement_is_rejected(self) -> None:
        self.mutate_json(CHECKER.PROGRESS, lambda value: value["executionBoundary"].update({"repositoryOwnerAuthenticationRequired": True}))
        self.assert_rejected()

    def test_23_policy_allowlist_expansion_is_rejected(self) -> None:
        self.mutate_json(CHECKER.POLICY, lambda value: value["checkerPolicy"]["trackedReadAllowlist"].append("build/archive.zip"))
        self.assert_rejected()

    def test_24_policy_file_write_allowlist_is_rejected(self) -> None:
        self.mutate_json(CHECKER.POLICY, lambda value: value["checkerPolicy"].update({"fileWriteAllowlist": ["out.json"]}))
        self.assert_rejected()

    def test_25_boolean_is_not_accepted_as_zero_counter(self) -> None:
        self.mutate_json(CHECKER.PROGRESS, lambda value: value["zeroOperationCounters"].update({"networkOperationCount": False}))
        self.assert_rejected()

    def test_26_current_repository_passes_with_pinned_identity_enforced(self) -> None:
        result = CHECKER.check_repository(ROOT)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["pinnedIdentityEnforced"])

    def test_27_pinned_identity_rejects_coordinated_core_drift(self) -> None:
        reader = CHECKER.SafeTrackedReader(ROOT)
        original = reader.read(CHECKER.DECISION)
        reader._cache[CHECKER.DECISION] = original.replace(
            b'"recordedDate":"2026-07-23"',
            b'"recordedDate":"2026-07-24"',
            1,
        )
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_pinned_identity(reader)

        coordinated = CHECKER.SafeTrackedReader(ROOT)
        removed_test_bytes = b"# coordinated checker-test removal\n"
        coordinated._cache[CHECKER.CHECKER_TEST] = removed_test_bytes
        manifest_v1 = coordinated.json(CHECKER.MANIFEST_V1)
        test_artifact = next(
            artifact
            for artifact in manifest_v1["artifacts"]
            if artifact["path"] == CHECKER.CHECKER_TEST
        )
        test_artifact["sha256"] = CHECKER.sha256_bytes(removed_test_bytes)
        manifest_v1["collectionSha256"] = CHECKER.collection_sha256(
            manifest_v1["artifacts"]
        )
        manifest_v1_bytes = json_bytes(manifest_v1)
        coordinated._cache[CHECKER.MANIFEST_V1] = manifest_v1_bytes
        manifest_v2 = coordinated.json(CHECKER.MANIFEST_V2)
        manifest_v2["predecessorManifestBinding"] = {
            "path": CHECKER.MANIFEST_V1,
            "sha256": CHECKER.sha256_bytes(manifest_v1_bytes),
            "semanticSha256": CHECKER.semantic_sha256(
                CHECKER.MANIFEST_V1,
                manifest_v1_bytes,
                manifest_v1,
            ),
            "collectionSha256": manifest_v1["collectionSha256"],
        }
        coordinated._cache[CHECKER.MANIFEST_V2] = json_bytes(manifest_v2)
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_pinned_identity(coordinated)


if __name__ == "__main__":
    unittest.main()
