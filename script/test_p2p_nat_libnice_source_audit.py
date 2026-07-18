#!/usr/bin/env python3
"""Mutation tests for the closed libnice source-audit rejection chain."""

from __future__ import annotations

import copy
import unittest

from script import check_p2p_nat_libnice_source_audit as checker


class LibniceSourceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = checker.load_documents()

    def assert_invalid(self, documents: dict[str, dict]) -> None:
        with self.assertRaises(checker.LibniceAuditValidationError):
            checker.validate_documents(documents)

    def test_canonical_documents_ast_and_hashes_pass(self) -> None:
        checker.validate_documents(self.documents)
        checker.validate_owned_ast()
        checker.validate_hashes()

    def test_duplicate_names_and_nonstandard_numbers_fail(self) -> None:
        with self.assertRaises(checker.LibniceAuditValidationError):
            checker.parse_json('{"status":"closed","status":"open"}', "duplicate")
        with self.assertRaises(checker.LibniceAuditValidationError):
            checker.parse_json('{"value":NaN}', "nan")

    def test_audit_findings_topics_and_rejection_cannot_drift(self) -> None:
        for mutation in ("severity", "topic", "outcome", "count", "compile"):
            documents = copy.deepcopy(self.documents)
            if mutation == "severity":
                documents["audit"]["findings"][0]["severity"] = "P2"
            elif mutation == "topic":
                documents["audit"]["requiredTopicResults"][2]["result"] = "mechanism_pass"
            elif mutation == "outcome":
                documents["audit"]["rejectionDecision"]["outcome"] = "compile_eligible"
            elif mutation == "count":
                documents["audit"]["rejectionDecision"]["independentP1BlockerCount"] = 3
            else:
                documents["audit"]["compileBoundary"]["compilerInvocationAuthorized"] = True
            self.assert_invalid(documents)

    def test_pending_dependency_acquisition_and_compile_plan_remain_closed(self) -> None:
        for mutation in ("intake", "closure", "pending_status", "prerequisite"):
            documents = copy.deepcopy(self.documents)
            if mutation == "intake":
                documents["intake"]["currentAuthorization"]["additionalSourceAcquisitionNetworkIOAllowed"] = True
            elif mutation == "closure":
                documents["closure"]["authorization"]["pendingSourceAcquisitionNetworkIOAllowed"] = True
            elif mutation == "pending_status":
                documents["closure"]["identifiedButNotAcquired"][0]["status"] = "acquired"
            else:
                documents["closure"]["compileOnlyPrerequisitesDisposition"]["productCAbiContract"] = "complete"
            self.assert_invalid(documents)

    def test_decision_cannot_select_candidate_or_open_authority(self) -> None:
        for mutation in ("resolution", "acquire", "compile", "runtime", "next"):
            documents = copy.deepcopy(self.documents)
            if mutation == "resolution":
                documents["decision"]["resolutions"][1]["resolution"] = "libnice_selected"
            elif mutation == "acquire":
                documents["decision"]["acquisitionClosure"]["additionalSourceAcquisitionAuthorized"] = True
            elif mutation == "compile":
                documents["decision"]["compileClosure"]["compilerInvocationPerformed"] = True
            elif mutation == "runtime":
                documents["decision"]["authorization"]["runtimeNetworkIOAllowed"] = True
            else:
                documents["decision"]["nextDecision"]["mayReuseRejectedCandidateAuthority"] = True
            self.assert_invalid(documents)

    def test_handoff_and_progress_reject_execution_or_implicit_reuse(self) -> None:
        for target, field in (
            ("handoff", "socketCreationAllowed"),
            ("handoff", "compilerInvocationAuthorized"),
            ("progress", "sourceAcquisitionNetworkIOAllowed"),
            ("progress", "phaseBExecutionAuthorized"),
        ):
            documents = copy.deepcopy(self.documents)
            documents[target]["authorization"][field] = True
            self.assert_invalid(documents)
        documents = copy.deepcopy(self.documents)
        documents["progress"]["nextStep"]["rejectedAuthorityMayBeReused"] = True
        self.assert_invalid(documents)

    def test_cross_reference_hash_drift_fails(self) -> None:
        for target, path in (
            ("intake", ("reviewedArtifacts", "sourceAudit", "sha256")),
            ("decision", ("decisionBasis", "completedIntake", "sha256")),
            ("handoff", ("sourceDecision", "sha256")),
            ("progress", ("currentAuthority", "handoff", "sha256")),
        ):
            documents = copy.deepcopy(self.documents)
            value = documents[target]
            for key in path[:-1]:
                value = value[key]
            value[path[-1]] = "0" * 64
            self.assert_invalid(documents)

    def test_owned_ast_rejects_process_network_dynamic_and_write_capabilities(self) -> None:
        for source in (
            "import socket\n",
            "import subprocess\nsubprocess.run(['true'])\n",
            "from pathlib import Path\nPath('x').write_text('y')\n",
            "eval('1')\n",
        ):
            with self.assertRaises(checker.LibniceAuditValidationError):
                checker.validate_owned_ast(source)


if __name__ == "__main__":
    unittest.main()
