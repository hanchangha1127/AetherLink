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


class ControlledSpikeReviewMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = json.loads(CHECKER.REVIEW_PATH.read_text(encoding="utf-8"))

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.ReviewValidationError):
            CHECKER.validate_document(candidate)

    def test_canonical_packet_passes(self) -> None:
        CHECKER.validate_source_handoff()
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_markdown(CHECKER.MARKDOWN_PATH.read_bytes())

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
        self.assert_rejected(lambda value: value["securityFloors"].pop())
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


if __name__ == "__main__":
    unittest.main()
