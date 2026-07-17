#!/usr/bin/env python3
"""Mutation tests for the immutable Phase A progress snapshot."""

from __future__ import annotations

import copy
import unittest

from script import check_p2p_nat_phase_a_progress as CHECKER
from script import check_p2p_nat_security_design as SECURITY_CHECKER


class PhaseAProgressMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = CHECKER.load_json(CHECKER.PROGRESS_PATH)

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.PhaseAProgressValidationError):
            CHECKER.validate_document(candidate)

    def test_canonical_progress_sources_ast_hashes_and_independent_validator_pass(self) -> None:
        CHECKER.validate_source_documents()
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_owned_python_ast()
        CHECKER.validate_artifact_hashes()
        self.assertEqual(0, CHECKER.main())
        SECURITY_CHECKER.validate_current_phase_a_progress(copy.deepcopy(self.canonical))
        checker_source = CHECKER.CHECKER_PATH.read_text(encoding="utf-8")
        main_source = checker_source.split("def main() -> int:", 1)[1]
        self.assertLess(
            main_source.index("validate_artifact_hashes()"),
            main_source.index("validate_source_documents()"),
        )
        original_preflight = SECURITY_CHECKER.PHASE_A_STATIC_EVIDENCE_SHA256
        try:
            SECURITY_CHECKER.PHASE_A_STATIC_EVIDENCE_SHA256 = dict(
                list(original_preflight.items())[:-1]
            )
            with self.assertRaises(ValueError):
                SECURITY_CHECKER.validate_phase_a_static_evidence_preflight()
        finally:
            SECURITY_CHECKER.PHASE_A_STATIC_EVIDENCE_SHA256 = original_preflight

    def test_duplicate_missing_unknown_and_nonstandard_json_fail(self) -> None:
        self.assert_rejected(lambda value: value.pop("sourceDecision"))
        self.assert_rejected(lambda value: value.update({"runtimeEvidence": []}))
        with self.assertRaises(CHECKER.PhaseAProgressValidationError):
            CHECKER.parse_json('{"status":"closed","status":"open"}', "duplicate status")
        with self.assertRaises(CHECKER.PhaseAProgressValidationError):
            CHECKER.parse_json('{"count":NaN}', "nonstandard number")
        with self.assertRaises(CHECKER.PhaseAProgressValidationError):
            CHECKER.require_object([], "source")

    def test_source_chain_approval_order_and_status_summary_drift_fail(self) -> None:
        self.assert_rejected(
            lambda value: value["sourceDecision"].update({"sha256": "0" * 64})
        )
        self.assert_rejected(
            lambda value: value["sourceHandoff"].update({"path": "../../implementation/handoff-v3.json"})
        )
        self.assert_rejected(
            lambda value: value["approvalSnapshot"].update({"count": True})
        )
        self.assert_rejected(
            lambda value: value["approvalSnapshot"]["decisionOrder"].reverse()
        )
        self.assert_rejected(
            lambda value: value["approvalSnapshot"]["resolutions"].update({
                "networking_library_selection": "libnice-0.1.23-glib-c-abi",
            })
        )
        self.assert_rejected(
            lambda value: value["statusSummary"].update({"boundedEvidenceCompletedCount": 3})
        )
        self.assert_rejected(
            lambda value: value["statusSummary"].update({"blockedBoundedEvidenceCount": 1})
        )
        self.assert_rejected(
            lambda value: value["statusSummary"].update({"requiredBoundedEvidenceGroupCount": 5})
        )

    def test_evidence_completion_blocker_scope_and_reference_drift_fail(self) -> None:
        self.assert_rejected(
            lambda value: value["evidenceStatus"].pop("phase_a_security_review")
        )
        self.assert_rejected(
            lambda value: value["evidenceStatus"]["libjuice_supply_chain_and_source_audit"].update({
                "status": "completed",
            })
        )
        self.assert_rejected(
            lambda value: value["evidenceStatus"]["android_macos_compile_only_integration"].update({
                "status": "completed",
            })
        )
        self.assert_rejected(
            lambda value: value["evidenceStatus"]["cross_platform_session_crypto_vectors"].update({
                "proofScope": "runtime_network_interoperability_complete",
            })
        )
        self.assert_rejected(
            lambda value: value["evidenceStatus"]["static_harness_and_egress_policy"].update({
                "status": "executed_measured_pass",
            })
        )
        self.assert_rejected(
            lambda value: value["evidenceStatus"]["phase_a_security_review"]["artifacts"].append({
                "path": "fabricated-review.json",
                "sha256": "0" * 64,
            })
        )
        self.assert_rejected(
            lambda value: value["evidenceStatus"]["cross_platform_session_crypto_vectors"]["artifacts"][0].update({
                "sha256": "0" * 64,
            })
        )

    def test_every_execution_gate_phase_b_measurement_and_immutability_drift_fail(self) -> None:
        for field in CHECKER.EXPECTED_EXECUTION_AUTHORITY:
            self.assert_rejected(
                lambda value, field=field: value["executionAuthority"].update({field: True})
            )
            self.assert_rejected(
                lambda value, field=field: value["executionAuthority"].update({field: 0})
            )
        for field in CHECKER.EXPECTED_BOUNDED_AUTHORITY:
            self.assert_rejected(
                lambda value, field=field: value["boundedPhaseAAuthority"].update({field: False})
            )
            self.assert_rejected(
                lambda value, field=field: value["boundedPhaseAAuthority"].update({field: 1})
            )
        self.assert_rejected(lambda value: value.update({"phaseBDecisionEligible": True}))
        self.assert_rejected(lambda value: value.update({"phaseBDecisionEligible": 0}))
        self.assert_rejected(lambda value: value.update({"measurementStatus": "measured_passed"}))
        self.assert_rejected(lambda value: value.update({"overallStatus": "completed_phase_a"}))
        self.assert_rejected(
            lambda value: value["immutability"].update({"recordState": "open"})
        )

    def test_central_validator_independently_rejects_progress_authority_drift(self) -> None:
        SECURITY_CHECKER.validate_current_phase_a_progress(copy.deepcopy(self.canonical))
        for field in CHECKER.EXPECTED_EXECUTION_AUTHORITY:
            candidate = copy.deepcopy(self.canonical)
            candidate["executionAuthority"][field] = True
            with self.assertRaises(ValueError):
                SECURITY_CHECKER.validate_current_phase_a_progress(candidate)
        type_confused = copy.deepcopy(self.canonical)
        type_confused["phaseBDecisionEligible"] = 0
        with self.assertRaises(ValueError):
            SECURITY_CHECKER.validate_current_phase_a_progress(type_confused)

    def test_owned_ast_rejects_process_network_dynamic_and_file_write_capabilities(self) -> None:
        for source in (
            "import socket\n",
            "import subprocess\n",
            "value = eval('1')\n",
            "Path('x').write_text('x')\n",
            "Path('x').rglob('*')\n",
            "Path.__dict__['write_text'](Path('x'), 'x')\n",
            "handlers['run']()\n",
            "sys.__dict__['modules']['os'].__dict__['system']('id')\n",
        ):
            with self.assertRaises(CHECKER.PhaseAProgressValidationError):
                CHECKER.validate_ast_source(source, "unsafe-progress-validator.py")
            with self.assertRaises(ValueError):
                SECURITY_CHECKER.validate_phase_a_static_python_ast(
                    source, "unsafe-progress-validator.py"
                )


if __name__ == "__main__":
    unittest.main()
