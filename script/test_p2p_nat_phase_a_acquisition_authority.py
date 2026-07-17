#!/usr/bin/env python3
"""Mutation tests for the Phase A artifact-acquisition authority chain."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_phase_a_acquisition_authority.py"
SPEC = importlib.util.spec_from_file_location("p2p_nat_phase_a_acquisition_authority", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load acquisition authority checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class PhaseAAcquisitionAuthorityMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision = json.loads(CHECKER.DECISION_PATH.read_text(encoding="utf-8"))
        cls.handoff = json.loads(CHECKER.HANDOFF_PATH.read_text(encoding="utf-8"))
        cls.progress = json.loads(CHECKER.PROGRESS_PATH.read_text(encoding="utf-8"))

    def assert_decision_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.decision)
        mutation(candidate)
        with self.assertRaises(CHECKER.AuthorityValidationError):
            CHECKER.validate_decision(candidate)

    def assert_handoff_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.handoff)
        mutation(candidate)
        with self.assertRaises(CHECKER.AuthorityValidationError):
            CHECKER.validate_handoff(candidate, copy.deepcopy(self.decision))

    def assert_progress_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.progress)
        mutation(candidate)
        with self.assertRaises(CHECKER.AuthorityValidationError):
            CHECKER.validate_progress(candidate, copy.deepcopy(self.decision))

    def test_canonical_chain_passes(self) -> None:
        CHECKER.validate_decision(copy.deepcopy(self.decision))
        CHECKER.validate_handoff(copy.deepcopy(self.handoff), copy.deepcopy(self.decision))
        CHECKER.validate_progress(copy.deepcopy(self.progress), copy.deepcopy(self.decision))
        for path, expected in CHECKER.PREDECESSOR_HASHES.items():
            CHECKER.validate_file_hash(path, expected)
        for path, expected in CHECKER.CURRENT_HASHES.items():
            CHECKER.validate_file_hash(path, expected)

    def test_missing_unknown_and_duplicate_names_fail(self) -> None:
        self.assert_decision_rejected(lambda value: value.pop("executionAuthority"))
        self.assert_decision_rejected(lambda value: value.update({"networkIOAllowed": True}))
        raw = CHECKER.DECISION_PATH.read_text(encoding="utf-8").replace(
            '  "status": "closed",',
            '  "status": "open",\n  "status": "closed",',
            1,
        )
        with self.assertRaises(CHECKER.AuthorityValidationError):
            CHECKER.parse_json(raw, "duplicate status")

    def test_supersession_and_hash_drift_fail(self) -> None:
        self.assert_decision_rejected(lambda value: value["supersedes"].update({"path": "decision-v0.json"}))
        self.assert_handoff_rejected(lambda value: value.update({"supersedesPath": "handoff-v3.json"}))
        self.assert_progress_rejected(lambda value: value["supersedes"].update({"sha256": "0" * 64}))

    def test_candidate_url_host_and_version_drift_fail(self) -> None:
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["libjuice"].update({"releaseTag": "main"}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["libjuice"].update({"archiveUrl": "https://example.com/libjuice.tar.gz"}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"].update({"allowedHosts": ["github.com", "example.com"]}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["androidNdk"].update({"version": "30.0.0"}))

    def test_archive_paths_and_limits_cannot_expand(self) -> None:
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["libjuice"].update({"archiveRelativePath": "/tmp/libjuice.tar.gz"}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["libjuice"].update({"maximumArchiveBytes": 1_000_000_000}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["androidNdk"].update({"maximumInstalledBytes": 53_687_091_200}))

    def test_proxy_redirect_and_package_manager_fallback_fail(self) -> None:
        for key in ("redirectFollowingAllowed", "environmentProxyAllowed", "packageManagerAcquisitionAllowed"):
            self.assert_decision_rejected(lambda value, key=key: value["acquisitionAuthorization"].update({key: True}))

    def test_compile_source_execution_socket_and_phase_b_escalation_fail(self) -> None:
        for key in (
            "sourceExecutionAllowed", "compilerInvocationAuthorizedBeforeReviewedManifest",
            "archiveInvocationAuthorizedBeforeReviewedManifest", "socketCreationAllowed",
            "runtimeNetworkIOAllowed", "harnessNetworkIOAllowed", "controlledSpikeNetworkIOAllowed",
            "controlledSpikeSocketExecutionAuthorized", "phaseBExecutionAuthorized",
            "productionNetworkIOAllowed", "productionDeploymentAuthorized",
        ):
            self.assert_decision_rejected(lambda value, key=key: value["executionAuthority"].update({key: True}))

    def test_boolean_integer_confusion_fails(self) -> None:
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"].update({"networkIOAllowed": 1}))
        self.assert_handoff_rejected(lambda value: value["authorization"].update({"compilerInvocationAuthorized": 0}))
        self.assert_progress_rejected(lambda value: value["executionAuthority"].update({"phaseBExecutionAuthorized": 0}))

    def test_retained_approvals_and_preserved_evidence_cannot_drift(self) -> None:
        self.assert_decision_rejected(lambda value: value["retainedApprovals"].pop())
        self.assert_decision_rejected(lambda value: value["retainedApprovals"].reverse())
        self.assert_handoff_rejected(lambda value: value["packages"][0]["evidencePaths"].pop())
        self.assert_handoff_rejected(lambda value: value["preNetworkDecisions"].pop())

    def test_progress_and_precompile_gate_escalation_fail(self) -> None:
        self.assert_progress_rejected(lambda value: value["acquisitionState"].update({"status": "completed"}))
        self.assert_progress_rejected(lambda value: value["evidenceStatus"]["libjuice_supply_chain_and_source_audit"].update({"status": "completed"}))
        self.assert_progress_rejected(lambda value: value["executionAuthority"].update({"compilerInvocationAuthorized": True}))
        self.assert_handoff_rejected(lambda value: value["nextDecision"].update({"socketExecutionAuthorizedBeforeSeparateDecision": True}))

    def test_markdown_and_current_hashes_are_pinned(self) -> None:
        CHECKER.validate_markdown(
            CHECKER.DECISION_MARKDOWN_PATH,
            ["Closed Decision", "Exact Acquisition", "Pre-Compile Gate", "Closed Execution Gates", "Next Gate"],
            ("v1.7.2", "28.2.13676358", "controlledSpikeNetworkIOAllowed=false"),
        )
        with self.assertRaises(CHECKER.AuthorityValidationError):
            CHECKER.validate_markdown(
                CHECKER.DECISION_MARKDOWN_PATH,
                ["Wrong"],
                ("v1.7.2",),
            )


if __name__ == "__main__":
    unittest.main()
