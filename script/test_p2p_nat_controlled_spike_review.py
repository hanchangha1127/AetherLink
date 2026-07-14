#!/usr/bin/env python3
"""Mutation tests for the controlled-network-spike review validator."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_controlled_spike_review.py"
SPEC = importlib.util.spec_from_file_location("p2p_nat_controlled_spike_review_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load controlled-spike review checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
SECURITY_CHECKER_PATH = ROOT / "script/check_p2p_nat_security_design.py"
SECURITY_SPEC = importlib.util.spec_from_file_location("p2p_nat_security_design_checker", SECURITY_CHECKER_PATH)
if SECURITY_SPEC is None or SECURITY_SPEC.loader is None:
    raise RuntimeError("unable to load P2P/NAT security design checker")
SECURITY_CHECKER = importlib.util.module_from_spec(SECURITY_SPEC)
SECURITY_SPEC.loader.exec_module(SECURITY_CHECKER)


class ControlledSpikeReviewMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = json.loads(CHECKER.REVIEW_PATH.read_text(encoding="utf-8"))
        cls.decision = json.loads(CHECKER.DECISION_PATH.read_text(encoding="utf-8"))
        cls.handoff_v4 = json.loads(CHECKER.CURRENT_HANDOFF_PATH.read_text(encoding="utf-8"))

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_document(candidate)

    def assert_decision_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.decision)
        mutation(candidate)
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_decision(candidate)

    def assert_handoff_v4_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.handoff_v4)
        mutation(candidate)
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_handoff_v4(candidate)

    def test_canonical_packet_passes(self) -> None:
        CHECKER.validate_source_handoff()
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_markdown(CHECKER.MARKDOWN_PATH.read_bytes())
        CHECKER.validate_decision(copy.deepcopy(self.decision))
        CHECKER.validate_decision_markdown(CHECKER.DECISION_MARKDOWN_PATH.read_bytes())
        CHECKER.validate_handoff_v4(copy.deepcopy(self.handoff_v4))
        CHECKER.validate_handoff_v4_markdown(CHECKER.CURRENT_HANDOFF_MARKDOWN_PATH.read_bytes())
        for path, expected in CHECKER.GENERATED_ARTIFACT_SHA256.items():
            CHECKER.validate_file_hash(path, expected)

    def test_missing_unknown_and_duplicate_names_fail(self) -> None:
        self.assert_rejected(lambda value: value.pop("authorization"))
        self.assert_rejected(lambda value: value.update({"selection": {}}))
        raw = CHECKER.REVIEW_PATH.read_text(encoding="utf-8")
        duplicate = raw.replace(
            '  "status": "proposed_not_selected",',
            '  "status": "selected",\n  "status": "proposed_not_selected",',
            1,
        )
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.parse_json(duplicate, "duplicate status")

    def test_decision_order_and_completeness_fail(self) -> None:
        self.assert_rejected(lambda value: value["decisions"].pop())
        self.assert_rejected(lambda value: value["decisions"].reverse())
        self.assert_rejected(lambda value: value["decisionOrder"].reverse())

    def test_implicit_selection_and_approval_fail(self) -> None:
        self.assert_rejected(
            lambda value: value["decisions"][0].update({
                "status": "selected",
                "resolution": CHECKER.RECOMMENDATIONS[CHECKER.DECISION_ORDER[0]],
                "approvalSource": "implicit",
            })
        )
        for field in self.canonical["authorization"]:
            self.assert_rejected(
                lambda value, field=field: value["authorization"].update({field: True})
            )

    def test_recommendation_and_option_drift_fail(self) -> None:
        self.assert_rejected(
            lambda value: value["decisions"][0].update({
                "recommendedOptionId": "libdatachannel-0.24.3-datachannel-stack"
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][1]["options"][0].update({"disposition": "alternative"})
        )
        self.assert_rejected(lambda value: value["decisions"][2]["options"].pop())

    def test_contract_security_floors_cannot_weaken(self) -> None:
        self.assert_rejected(
            lambda value: value["decisions"][0]["proposedContract"].clear()
        )
        self.assert_rejected(
            lambda value: value["decisions"][0]["proposedContract"].update({
                "sourceAcquisition": "allowed",
                "networkExecutionDuringSelection": True,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][0]["proposedContract"].update({
                "socketExecutionAuthorized": True,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][1]["proposedContract"].update({
                "androidMinimumSdk": 31,
                "downgradeRule": "plaintext_fallback_allowed",
                "networkExecutionDuringSelection": True,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][0]["proposedContract"].update({
                "networkExecutionDuringSelection": 0,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][1]["proposedContract"].update({
                "androidMinimumSdk": 26.0,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][2]["proposedContract"]["phaseA"].update({
                "socketCreationAllowed": True,
                "networkIOAllowed": True,
                "sourceDownloadAllowed": True,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][2]["proposedContract"]["phaseB"].update({
                "wallClockTimeoutSeconds": 3600,
                "maximumResidentMemoryMiBPerProcess": 4096,
                "maximumSocketsPerProcess": 1024,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][2]["proposedContract"]["phaseB"].update({
                "maximumCpuCoresPerProcess": True,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][3]["proposedContract"].update({
                "allowlistMutability": "mutable",
                "endpointSyntax": "hostname_wildcard_or_url",
                "networkExecutionDuringSelection": True,
            })
        )
        self.assert_rejected(
            lambda value: value["decisions"][3]["proposedContract"][
                "prohibitedResolutionAndRouting"
            ].remove("dns")
        )
        self.assert_rejected(lambda value: value["securityFloors"].pop())
        self.assert_rejected(
            lambda value: value["securityFloors"][2].update({
                "contract": "plaintext fallback is allowed",
            })
        )
        self.assert_rejected(
            lambda value: value["securityFloors"][6]["contract"].update({
                "maximumRunSeconds": 3600,
                "maximumResidentMemoryMiBPerProcess": 4096,
                "maximumSocketsPerProcess": 1024,
            })
        )
        self.assert_rejected(
            lambda value: value["securityFloors"][6]["contract"].update({
                "maximumCpuCoresPerProcess": True,
            })
        )
        self.assert_rejected(
            lambda value: value["securityFloors"].append({
                "floorId": "allow_unrestricted_egress",
                "contract": "unsafe",
            })
        )

    def test_official_source_set_and_verification_date_fail(self) -> None:
        self.assert_rejected(lambda value: value["officialSources"]["sources"].pop())
        self.assert_rejected(
            lambda value: value["officialSources"].update({"verifiedAt": "2026-07-11"})
        )
        self.assert_rejected(
            lambda value: value["officialSources"]["sources"][0].update({"url": "https://example.com"})
        )
        self.assert_rejected(
            lambda value: value["officialSources"]["sources"][1].update({
                "sourceId": value["officialSources"]["sources"][0]["sourceId"],
            })
        )

    def test_measurement_and_outcome_claims_fail(self) -> None:
        self.assert_rejected(lambda value: value.update({"measurementStatus": "measured_passed"}))
        self.assert_rejected(
            lambda value: value["reviewOutcome"].update({"selectedDecisionCount": 1})
        )
        self.assert_rejected(
            lambda value: value["reviewOutcome"].update({"handoffCreated": True})
        )

    def test_approval_and_immutability_drift_fail(self) -> None:
        self.assert_rejected(lambda value: value["approvalRequired"]["decisionIds"].pop())
        self.assert_rejected(
            lambda value: value["immutability"].update({"recordState": "open"})
        )

    def test_markdown_claim_and_heading_drift_fail(self) -> None:
        raw = CHECKER.MARKDOWN_PATH.read_bytes()
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_markdown(raw + b"\nnetworkIOAllowed=true\n")
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_markdown(raw.replace(b"## Status", b"## Current Status", 1))

    def test_approval_decision_chain_and_duplicate_names_fail(self) -> None:
        self.assert_decision_rejected(lambda value: value.pop("sourceReviewId"))
        self.assert_decision_rejected(lambda value: value.update({"selection": {}}))
        self.assert_decision_rejected(
            lambda value: value.update({"sourceHandoffPath": "../implementation/handoff-v2.json"})
        )
        raw = CHECKER.DECISION_PATH.read_text(encoding="utf-8")
        duplicate = raw.replace(
            '  "status": "closed",',
            '  "status": "open",\n  "status": "closed",',
            1,
        )
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.parse_json(duplicate, "duplicate approval status")

    def test_approval_decision_order_partial_and_resolution_drift_fail(self) -> None:
        self.assert_decision_rejected(lambda value: value["approvals"].pop())
        self.assert_decision_rejected(lambda value: value["approvals"].reverse())
        self.assert_decision_rejected(lambda value: value["decisionOrder"].reverse())
        self.assert_decision_rejected(
            lambda value: value["approvals"][0].update({
                "resolution": "libnice-0.1.23-glib-c-abi",
            })
        )
        self.assert_decision_rejected(
            lambda value: value["approvals"][1].update({"approvalSource": "implicit"})
        )

    def test_approval_decision_authorization_measurement_and_evidence_drift_fail(self) -> None:
        self.assert_decision_rejected(
            lambda value: value["authorization"].update({"controlledSpikeNetworkIOAllowed": True})
        )
        self.assert_decision_rejected(
            lambda value: value["authorization"].update({"productionDeploymentAuthorized": True})
        )
        self.assert_decision_rejected(
            lambda value: value["authorization"].update({"sourceAcquisitionNetworkIOAllowed": True})
        )
        self.assert_decision_rejected(lambda value: value.update({"measurementStatus": "measured_passed"}))
        self.assert_decision_rejected(lambda value: value["requiredPhaseAEvidence"].pop())
        self.assert_decision_rejected(
            lambda value: value["immutability"].update({"recordState": "open"})
        )

    def test_handoff_v4_chain_preserved_evidence_and_resolution_drift_fail(self) -> None:
        self.assert_handoff_v4_rejected(lambda value: value.update({"supersedesPath": "handoff-v2.json"}))
        self.assert_handoff_v4_rejected(
            lambda value: value.update({"controlledSpikeDecisionPath": "../controlled-network-spike/review-v1.json"})
        )
        self.assert_handoff_v4_rejected(
            lambda value: value["packages"][0]["evidenceSha256"].update({
                next(iter(value["packages"][0]["evidenceSha256"])): "0" * 64,
            })
        )
        self.assert_handoff_v4_rejected(
            lambda value: value["preNetworkDecisions"][0].update({"resolution": "weakened"})
        )
        self.assert_handoff_v4_rejected(lambda value: value["controlledSpikeApprovals"].pop())

    def test_handoff_v4_phase_a_and_closed_network_gates_fail(self) -> None:
        self.assert_handoff_v4_rejected(
            lambda value: value["authorization"].update({"controlledSpikeNetworkIOAllowed": True})
        )
        self.assert_handoff_v4_rejected(
            lambda value: value["packages"][2]["phaseA"].update({"socketCreationAllowed": True})
        )
        self.assert_handoff_v4_rejected(
            lambda value: value["packages"][2]["phaseA"].update({"sourceExecutionAllowed": True})
        )
        self.assert_handoff_v4_rejected(
            lambda value: value["packages"][2]["phaseA"].update({
                "sourceMaterialMode": "network_download_allowed",
                "sourceAcquisitionNetworkIOAllowed": True,
            })
        )
        self.assert_handoff_v4_rejected(
            lambda value: value["packages"][2]["phaseB"].update({
                "executionAuthorized": True,
                "networkIOAllowed": True,
                "socketExecutionAuthorized": True,
            })
        )
        self.assert_handoff_v4_rejected(
            lambda value: value.update({"activeProtocolNamespace": ["route.refresh", "ice.candidate"]})
        )

    def test_approval_markdown_and_handoff_claim_drift_fail(self) -> None:
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_decision_markdown(
                CHECKER.DECISION_MARKDOWN_PATH.read_bytes() + b"\ncontrolledSpikeNetworkIOAllowed=true\n"
            )
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_handoff_v4_markdown(
                CHECKER.CURRENT_HANDOFF_MARKDOWN_PATH.read_bytes().replace(
                    b"## Closed Network Boundary", b"## Open Network Boundary", 1
                )
            )

    def test_security_design_validator_independently_rejects_handoff_v4_authority_drift(self) -> None:
        SECURITY_CHECKER.validate_current_pre_network_handoff()
        SECURITY_CHECKER.validate_current_controlled_spike_handoff(copy.deepcopy(self.handoff_v4))
        mutated = copy.deepcopy(self.handoff_v4)
        mutated["authorization"]["controlledSpikeSocketExecutionAuthorized"] = True
        with self.assertRaises(ValueError):
            SECURITY_CHECKER.validate_current_controlled_spike_handoff(mutated)
        for path, field, replacement in (
            (("authorization",), "controlledSpikeNetworkIOAllowed", 0),
            (("authorization",), "offlineSourceInspectionAuthorized", 1),
            (("packages", 2, "phaseA"), "sourceAcquisitionNetworkIOAllowed", 0),
            (("packages", 2, "phaseB"), "executionAuthorized", 0),
            (("nextDecision",), "networkIOAllowedBeforeDecision", 0),
        ):
            type_confused = copy.deepcopy(self.handoff_v4)
            target = type_confused
            for component in path:
                target = target[component]
            target[field] = replacement
            with self.assertRaises(ValueError):
                SECURITY_CHECKER.validate_current_controlled_spike_handoff(type_confused)
        duplicate = CHECKER.CURRENT_HANDOFF_PATH.read_text(encoding="utf-8").replace(
            '  "status": "closed",',
            '  "status": "open",\n  "status": "closed",',
            1,
        )
        with self.assertRaises(ValueError):
            SECURITY_CHECKER.parse_json(duplicate, "duplicate handoff-v4 status")


if __name__ == "__main__":
    unittest.main()
