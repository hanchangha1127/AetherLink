#!/usr/bin/env python3
"""Mutation tests for the closed libjuice source-audit boundary."""

from __future__ import annotations

import copy
from pathlib import Path
import unittest

from script import check_p2p_nat_libjuice_source_audit as CHECKER


class LibjuiceSourceAuditMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = CHECKER.load_documents()

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.SourceAuditValidationError):
            CHECKER.validate_documents(candidate)

    def test_canonical_documents_ast_and_hashes_pass(self) -> None:
        CHECKER.validate_documents(copy.deepcopy(self.canonical))
        CHECKER.validate_owned_ast()
        CHECKER.validate_hashes()
        self.assertEqual(0, CHECKER.main())

    def test_duplicate_names_invalid_json_and_nonstandard_number_fail(self) -> None:
        for raw in (
            '{"status":"closed","status":"open"}',
            '{"value":NaN}',
            '{',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.SourceAuditValidationError):
                    CHECKER.parse_json(raw, "mutation")

    def test_document_set_and_top_level_shape_drift_fail(self) -> None:
        self.assert_rejected(lambda value: value.pop("audit"))
        self.assert_rejected(lambda value: value.update({"compile": {}}))
        for name in CHECKER.TOP_LEVEL_KEYS:
            removed_key = sorted(CHECKER.TOP_LEVEL_KEYS[name])[0]
            with self.subTest(name=name, case="missing"):
                self.assert_rejected(
                    lambda value, name=name, removed_key=removed_key:
                    value[name].pop(removed_key)
                )
            with self.subTest(name=name, case="unknown"):
                self.assert_rejected(lambda value, name=name: value[name].update({"runtime": {}}))

    def test_manifest_inventory_digest_toolchain_and_authority_drift_fail(self) -> None:
        mutations = (
            lambda value: value["manifest"]["sourceTree"]["files"].pop(),
            lambda value: value["manifest"]["sourceTree"]["files"].reverse(),
            lambda value: value["manifest"]["sourceTree"]["files"][0].update({"sizeBytes": 0}),
            lambda value: value["manifest"]["sourceTree"].update({"sha256": "0" * 64}),
            lambda value: value["manifest"]["extraction"].update({"symlinkCount": 1}),
            lambda value: value["manifest"]["toolchainReceipt"]["android"].update({"packageId": "ndk;latest"}),
            lambda value: value["manifest"]["buildInputReview"].update({"compilerInvocationAllowedByThisManifest": True}),
            lambda value: value["manifest"]["authorityBoundary"].update({"socketCreationPerformed": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_audit_topics_findings_rejection_and_execution_drift_fail(self) -> None:
        mutations = (
            lambda value: value["audit"]["requiredTopicResults"].reverse(),
            lambda value: value["audit"]["requiredTopicResults"][1].update({"result": "pass"}),
            lambda value: value["audit"]["findings"].pop(0),
            lambda value: value["audit"]["findings"][0].update({"severity": "P3"}),
            lambda value: value["audit"]["rejectionDecision"].update({"outcome": "accepted"}),
            lambda value: value["audit"]["rejectionDecision"].update({"wrapperOnlyMitigationSufficient": True}),
            lambda value: value["audit"]["rejectionDecision"].update({"fallbackSelected": True}),
            lambda value: value["audit"]["compileBoundary"].update({"compilerInvocationPerformed": True}),
            lambda value: value["audit"]["networkBoundary"].update({"runtimeNetworkIOAllowed": True}),
            lambda value: value["audit"]["method"].update({"sourceExecution": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_intake_consumption_execution_and_current_authority_drift_fail(self) -> None:
        mutations = (
            lambda value: value["intake"]["authority"].update({"authorizationConsumed": False}),
            lambda value: value["intake"]["auditFailure"].update({"independentP1BlockerCount": 4}),
            lambda value: value["intake"]["auditFailure"].update({"compileSkipped": False}),
            lambda value: value["intake"]["auditFailure"].update({"fallbackSelected": True}),
            lambda value: value["intake"]["executionRecord"].update({"compilerInvocationPerformed": True}),
            lambda value: value["intake"]["executionRecord"].update({"sourceInspectionPerformed": 1}),
            lambda value: value["intake"]["currentAuthorization"].update({"libniceAcquisitionNetworkIOAllowed": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_fallback_review_rejects_selection_acquisition_measurement_and_implicit_approval(self) -> None:
        mutations = (
            lambda value: value["review"].update({"status": "selected"}),
            lambda value: value["review"]["fallbackCandidate"].update({"selection": "approved"}),
            lambda value: value["review"]["authorization"].update({"libniceSourceAcquisitionAuthorized": True}),
            lambda value: value["review"]["authorization"].update({"compilerInvocationAuthorized": True}),
            lambda value: value["review"]["measurementStatus"].update({"compiled": True}),
            lambda value: value["review"]["measurementStatus"].update({"measurements": [{}]}),
            lambda value: value["review"]["nextDecision"].update({"implicitApprovalAllowed": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_failure_decision_rejects_selection_compile_and_authority_expansion(self) -> None:
        mutations = (
            lambda value: value["decision"]["decisionBasis"].update({"newUserSelectionClaimed": True}),
            lambda value: value["decision"]["resolutions"][0].update({"resolution": "approved"}),
            lambda value: value["decision"]["resolutions"][1].update({"resolution": "selected"}),
            lambda value: value["decision"]["compileClosure"].update({"libjuiceCompilePerformed": True}),
            lambda value: value["decision"]["authorization"].update({"sourceAcquisitionNetworkIOAllowed": True}),
            lambda value: value["decision"]["authorization"].update({"handoffV6CreationAuthorized": 1}),
            lambda value: value["decision"]["failurePolicySatisfaction"].update({"fallbackSilentlySelected": True}),
            lambda value: value["decision"]["nextDecision"].update({"mayAuthorizeCompiler": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_handoff_rejects_any_open_gate_execution_or_next_handoff(self) -> None:
        mutations = (
            lambda value: value["handoff"]["networkingLibraryDisposition"].update({"fallbackStatus": "selected"}),
            lambda value: value["handoff"]["authorization"].update({"implementationAuthorized": True}),
            lambda value: value["handoff"]["authorization"].update({"compilerInvocationAuthorized": True}),
            lambda value: value["handoff"]["authorization"].update({"phaseBExecutionAuthorized": True}),
            lambda value: value["handoff"]["executionRecord"].update({"archiveInvocationPerformed": True}),
            lambda value: value["handoff"]["executionRecord"].update({"measurements": [{}]}),
            lambda value: value["handoff"]["nextHandoff"].update({"creationAuthorized": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_progress_rejects_status_count_evidence_execution_and_next_step_drift(self) -> None:
        mutations = (
            lambda value: value["progress"].update({"status": "complete"}),
            lambda value: value["progress"]["summary"].update({"passedEvidenceUnitCount": 3}),
            lambda value: value["progress"]["summary"].update({"fallbackDisposition": "selected"}),
            lambda value: value["progress"]["evidenceUnits"]["android_macos_compile_only_integration"].update({"status": "complete"}),
            lambda value: value["progress"]["authorization"].update({"compilerInvocationAuthorized": True}),
            lambda value: value["progress"]["executionRecord"].update({"socketCreationPerformed": True}),
            lambda value: value["progress"]["nextStep"].update({"fallbackMayBeImplicitlySelected": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_cross_reference_hash_drift_fails(self) -> None:
        mutations = (
            lambda value: value["audit"]["sourceManifest"].update({"sha256": "0" * 64}),
            lambda value: value["intake"]["reviewedArtifacts"]["sourceAudit"].update({"sha256": "1" * 64}),
            lambda value: value["review"]["triggerEvidence"]["completedIntake"].update({"sha256": "2" * 64}),
            lambda value: value["decision"]["decisionBasis"]["fallbackReview"].update({"sha256": "3" * 64}),
            lambda value: value["handoff"]["sourceDecision"].update({"sha256": "4" * 64}),
            lambda value: value["progress"]["currentAuthority"]["handoff"].update({"sha256": "5" * 64}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_rejected(mutation)

    def test_owned_ast_rejects_process_network_dynamic_and_write_capabilities(self) -> None:
        rejected_sources = (
            "import socket\n",
            "import subprocess\nsubprocess.run(['true'])\n",
            "from urllib import request\n",
            "eval('1')\n",
            "Path('x').write_text('y')\n",
        )
        for source in rejected_sources:
            with self.subTest(source=source):
                with self.assertRaises(CHECKER.SourceAuditValidationError):
                    CHECKER.validate_owned_ast(source)


if __name__ == "__main__":
    unittest.main()
