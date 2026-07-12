#!/usr/bin/env python3
"""Negative mutation tests for the P2P/NAT pre-network review validator."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_pre_network_review.py"
SPEC = importlib.util.spec_from_file_location("p2p_nat_pre_network_review_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load pre-network review checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
SECURITY_CHECKER_PATH = ROOT / "script/check_p2p_nat_security_design.py"
SECURITY_SPEC = importlib.util.spec_from_file_location(
    "p2p_nat_security_design_checker",
    SECURITY_CHECKER_PATH,
)
if SECURITY_SPEC is None or SECURITY_SPEC.loader is None:
    raise RuntimeError("unable to load P2P/NAT security design checker")
SECURITY_CHECKER = importlib.util.module_from_spec(SECURITY_SPEC)
SECURITY_SPEC.loader.exec_module(SECURITY_CHECKER)


class PreNetworkReviewMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = json.loads(CHECKER.PACKET_PATH.read_text(encoding="utf-8"))
        cls.approval = json.loads(CHECKER.APPROVAL_PATH.read_text(encoding="utf-8"))
        cls.handoff_v3 = json.loads(CHECKER.HANDOFF_V3_PATH.read_text(encoding="utf-8"))

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_document(candidate)

    def assert_approval_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.approval)
        mutation(candidate)
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_approval_document(candidate)

    def assert_handoff_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.handoff_v3)
        mutation(candidate)
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_handoff_v3(candidate)

    def test_canonical_packet_passes(self) -> None:
        CHECKER.validate_references()
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_markdown(CHECKER.MARKDOWN_PATH.read_bytes())
        CHECKER.validate_approval_document(copy.deepcopy(self.approval))
        CHECKER.validate_handoff_v3(copy.deepcopy(self.handoff_v3))
        for path, expected in CHECKER.GENERATED_ARTIFACT_SHA256.items():
            CHECKER.validate_file_hash(path, expected)

    def test_missing_and_unknown_fields_fail(self) -> None:
        self.assert_rejected(lambda value: value.pop("securityFloors"))
        self.assert_rejected(lambda value: value.update({"handoffV3": {}}))
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_markdown(CHECKER.MARKDOWN_PATH.read_bytes() + b"\nApproved for network I/O.\n")
        raw = CHECKER.PACKET_PATH.read_text(encoding="utf-8")
        duplicate_root_status = raw.replace(
            '  "status": "proposed_not_selected",',
            '  "status": "approved",\n  "status": "proposed_not_selected",',
            1,
        )
        duplicate_decision_status = raw.replace(
            '      "status": "proposed_not_selected",',
            '      "status": "approved",\n      "status": "proposed_not_selected",',
            1,
        )
        duplicate_network_authorization = raw.replace(
            '    "networkIOAllowed": false,',
            '    "networkIOAllowed": true,\n    "networkIOAllowed": false,',
            1,
        )
        for candidate in (duplicate_root_status, duplicate_decision_status, duplicate_network_authorization):
            with self.assertRaises(CHECKER.ReviewValidationError):
                CHECKER.parse_json(candidate)

    def test_missing_duplicate_unknown_and_reordered_decisions_fail(self) -> None:
        self.assert_rejected(lambda value: value["decisions"].pop())
        self.assert_rejected(lambda value: value["decisions"].__setitem__(1, copy.deepcopy(value["decisions"][0])))
        self.assert_rejected(lambda value: value["decisions"][0].update({"decisionId": "unknown"}))
        self.assert_rejected(lambda value: value["decisions"].reverse())

    def test_unauthorized_state_transitions_fail(self) -> None:
        self.assert_rejected(lambda value: value.update({"status": "approved"}))
        self.assert_rejected(lambda value: value["authorization"].update({"networkIOAllowed": True}))
        self.assert_rejected(lambda value: value["authorization"].update({"librarySelectionAuthorized": True}))
        self.assert_rejected(lambda value: value["authorization"].update({"productionDeploymentAuthorized": True}))
        self.assert_rejected(lambda value: value["authorization"].update({"nextHandoffAuthorized": True}))

    def test_resolution_or_approval_without_record_fails(self) -> None:
        self.assert_rejected(lambda value: value["decisions"][0].update({"resolution": "approved"}))
        self.assert_rejected(lambda value: value["decisions"][0].update({"approvalSource": "implicit"}))
        self.assert_rejected(lambda value: value["reviewOutcome"].update({"allDecisionsSelected": True}))
        self.assert_rejected(lambda value: value["reviewOutcome"].update({"nextHandoffCreated": True}))
        self.assert_rejected(lambda value: value["reviewOutcome"].update({"requiredAction": "Approved; proceed with network I/O."}))

    def test_weakened_security_floors_fail(self) -> None:
        self.assert_rejected(lambda value: value["securityFloors"].pop())
        self.assert_rejected(lambda value: value["decisions"][0]["proposedContract"].update({"transportTrust": "unauthenticated_plaintext"}))
        self.assert_rejected(lambda value: value["decisions"][1]["proposedContract"].update({"bindingFields": []}))
        self.assert_rejected(lambda value: value["decisions"][1]["proposedContract"].update({"maximumLifetimeSeconds": 3600}))
        self.assert_rejected(lambda value: value["decisions"][2]["proposedContract"].update({"candidateEnvelope": "service_plaintext"}))
        self.assert_rejected(lambda value: value["decisions"][2]["proposedContract"].update({"alwaysProhibited": []}))
        self.assert_rejected(lambda value: value["decisions"][3]["proposedContract"].update({"iceMode": "ice_lite"}))
        self.assert_rejected(lambda value: value["decisions"][3]["proposedContract"].update({"consentExpirySeconds": 60}))
        self.assert_rejected(lambda value: value["decisions"][3]["proposedContract"].update({"consentFailureRule": "continue_application_traffic"}))
        self.assert_rejected(lambda value: value["decisions"][4]["proposedContract"].update({"credentialLifetimeSeconds": 3600}))
        self.assert_rejected(lambda value: value["decisions"][4]["proposedContract"].update({"permissionRule": "unrestricted"}))
        self.assert_rejected(lambda value: value["decisions"][4]["proposedContract"].update({"quotaRule": "disabled"}))
        self.assert_rejected(lambda value: value["decisions"][5]["proposedContract"].update({"inFlightRule": "transparent_replay"}))

    def test_release_results_cannot_be_claimed_before_measurement(self) -> None:
        self.assert_rejected(lambda value: value.update({"measurementStatus": "measured_passed"}))
        self.assert_rejected(lambda value: value["decisions"][6]["proposedContract"].update({"measuredResults": {}}))
        self.assert_rejected(lambda value: value["decisions"][6]["proposedContract"].update({"requiredMatrix": []}))
        self.assert_rejected(lambda value: value["decisions"][6]["proposedContract"]["setupLatencyMilliseconds"].update({"p50": -1}))
        self.assert_rejected(lambda value: value["decisions"][6]["proposedContract"].update({"prohibitedDestinationAttemptsAllowed": 1}))
        self.assert_rejected(lambda value: value["decisions"][6]["proposedContract"].update({"rollbackSuccessMinimum": 0.99}))

    def test_recommendation_and_option_drift_fail(self) -> None:
        self.assert_rejected(lambda value: value["decisions"][0].update({"recommendedOptionId": "contracted-provider-tls13-signed-service-config"}))
        self.assert_rejected(lambda value: value["decisions"][0]["options"][1].update({"disposition": "recommended"}))
        self.assert_rejected(lambda value: value["decisions"][0]["options"].pop())

    def test_approval_missing_unknown_duplicate_and_order_fail(self) -> None:
        self.assert_approval_rejected(lambda value: value.pop("sourceReviewPath"))
        self.assert_approval_rejected(lambda value: value.update({"notes": []}))
        self.assert_approval_rejected(lambda value: value["resolutions"].pop())
        self.assert_approval_rejected(lambda value: value["resolutions"].reverse())
        self.assert_approval_rejected(
            lambda value: value["resolutions"].__setitem__(1, copy.deepcopy(value["resolutions"][0]))
        )
        raw = CHECKER.APPROVAL_PATH.read_text(encoding="utf-8")
        duplicate = raw.replace(
            '  "status": "closed",',
            '  "status": "approved",\n  "status": "closed",',
            1,
        )
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.parse_json(duplicate)

    def test_approval_recommendation_source_and_authorization_fail(self) -> None:
        self.assert_approval_rejected(
            lambda value: value["resolutions"][0].update({"resolution": "contracted-provider-tls13-signed-service-config"})
        )
        self.assert_approval_rejected(
            lambda value: value["resolutions"][0].update({"recommendedOptionId": "contracted-provider-tls13-signed-service-config"})
        )
        self.assert_approval_rejected(
            lambda value: value["resolutions"][0].update({"approvalSource": "implicit"})
        )
        self.assert_approval_rejected(lambda value: value.update({"approvalSource": "implicit"}))
        for field in (
            "networkIOAllowed", "librarySelectionAuthorized", "productionDeploymentAuthorized",
            "controlledNetworkSpikeSocketExecutionAuthorized",
        ):
            self.assert_approval_rejected(
                lambda value, field=field: value["authorization"].update({field: True})
            )

    def test_approval_cannot_fabricate_measurements(self) -> None:
        self.assert_approval_rejected(lambda value: value.update({"measurementStatus": "measured_passed"}))
        self.assert_approval_rejected(lambda value: value.update({"measuredResults": {"success": 1.0}}))

    def test_handoff_missing_unknown_duplicate_and_order_fail(self) -> None:
        self.assert_handoff_rejected(lambda value: value.pop("approvalDecisionPath"))
        self.assert_handoff_rejected(lambda value: value.update({"notes": []}))
        self.assert_handoff_rejected(lambda value: value["preNetworkDecisions"].pop())
        self.assert_handoff_rejected(lambda value: value["preNetworkDecisions"].reverse())
        self.assert_handoff_rejected(lambda value: value["packages"].reverse())
        raw = CHECKER.HANDOFF_V3_PATH.read_text(encoding="utf-8")
        duplicate = raw.replace(
            '  "measurementStatus": "unmeasured_proposal",',
            '  "measurementStatus": "measured_passed",\n  "measurementStatus": "unmeasured_proposal",',
            1,
        )
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.parse_json(duplicate)

    def test_handoff_resolution_and_closed_gates_fail(self) -> None:
        self.assert_handoff_rejected(
            lambda value: value["preNetworkDecisions"][0].update({"status": "open"})
        )
        self.assert_handoff_rejected(
            lambda value: value["preNetworkDecisions"][0].update({"resolution": "contracted-provider-tls13-signed-service-config"})
        )
        for field in (
            "networkIOAllowed", "librarySelectionAuthorized", "productionDeploymentAuthorized",
            "controlledNetworkSpikeSocketExecutionAuthorized",
        ):
            self.assert_handoff_rejected(
                lambda value, field=field: value["authorization"].update({field: True})
            )
        self.assert_handoff_rejected(
            lambda value: value["packages"][2].update({"executionAuthorized": True})
        )
        self.assert_handoff_rejected(
            lambda value: value["packages"][2].update({"networkIOAllowed": True})
        )
        self.assert_handoff_rejected(
            lambda value: value["packages"][2].update({"socketExecutionAuthorized": True})
        )
        self.assert_handoff_rejected(
            lambda value: value["nextReview"].update({"networkIOAllowedDuringReview": True})
        )
        self.assert_handoff_rejected(
            lambda value: value["packages"][2]["blockedOnReviews"].pop()
        )

    def test_handoff_cannot_weaken_floors_or_fabricate_measurements(self) -> None:
        self.assert_handoff_rejected(
            lambda value: value["packages"][0]["evidencePaths"].pop()
        )
        self.assert_handoff_rejected(
            lambda value: value["packages"][0]["evidenceSha256"].pop(
                value["packages"][0]["evidencePaths"][0]
            )
        )
        self.assert_handoff_rejected(
            lambda value: value["packages"][1]["evidenceSha256"].update({
                value["packages"][1]["evidencePaths"][0]: "0" * 64
            })
        )
        self.assert_handoff_rejected(lambda value: value.update({"measurementStatus": "measured_passed"}))
        self.assert_handoff_rejected(lambda value: value.update({"measuredResults": {"sessions": 1000}}))

    def test_security_design_parser_rejects_duplicate_names(self) -> None:
        with self.assertRaises(ValueError):
            SECURITY_CHECKER.parse_json(
                '{"networkIOAllowed":true,"networkIOAllowed":false}',
                "duplicate-authorization",
            )
        mutations = (
            lambda value: value["authorization"].update({"networkIOAllowed": True}),
            lambda value: value.update({"measurementStatus": "measured_passed"}),
            lambda value: value["preNetworkDecisions"][0].update({"status": "open"}),
            lambda value: value["immutability"].update({"recordState": "open"}),
            lambda value: value["packages"][0].update({"executionAuthorized": True}),
            lambda value: value["nextReview"].update({"status": "completed"}),
            lambda value: value["nextReview"].update({"scope": []}),
        )
        for mutation in mutations:
            candidate = copy.deepcopy(self.handoff_v3)
            mutation(candidate)
            with self.assertRaises(ValueError):
                SECURITY_CHECKER.validate_current_pre_network_handoff(candidate)


if __name__ == "__main__":
    unittest.main()
