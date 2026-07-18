#!/usr/bin/env python3
"""Mutation tests for the bounded libnice acquisition authority."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_libnice_acquisition_authority.py"
SPEC = importlib.util.spec_from_file_location("libnice_acquisition_authority", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load libnice acquisition checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class LibniceAcquisitionAuthorityMutationTests(unittest.TestCase):
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
            CHECKER.validate_handoff(candidate)

    def assert_progress_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.progress)
        mutation(candidate)
        with self.assertRaises(CHECKER.AuthorityValidationError):
            CHECKER.validate_progress(candidate)

    def test_canonical_chain_passes(self) -> None:
        CHECKER.validate_decision(copy.deepcopy(self.decision))
        CHECKER.validate_handoff(copy.deepcopy(self.handoff))
        CHECKER.validate_progress(copy.deepcopy(self.progress))
        for path, expected in CHECKER.HASHES.items():
            CHECKER.validate_file_hash(path, expected)

    def test_alternate_url_host_and_redirect_fail(self) -> None:
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["artifacts"][0].update({"url": "https://example.com/libnice.tar.gz"}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"].update({"allowedHosts": ["libnice.freedesktop.org", "example.com"]}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"].update({"redirectFollowingAllowed": True}))

    def test_proxy_package_manager_and_size_expansion_fail(self) -> None:
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"].update({"environmentProxyAllowed": True}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"].update({"packageManagerAcquisitionAllowed": True}))
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"]["artifacts"][0].update({"maximumBytes": 33554433}))

    def test_dependency_authority_cannot_open_early(self) -> None:
        self.assert_decision_rejected(lambda value: value["dependencyAcquisition"].update({"effectiveAuthority": True}))
        self.assert_handoff_rejected(lambda value: value["authorization"].update({"libniceDependencyAcquisitionAuthorized": True}))
        self.assert_progress_rejected(lambda value: value["acquisitionState"].update({"dependencyAcquisitionAuthorized": True}))

    def test_compile_source_socket_and_production_escalation_fail(self) -> None:
        for key in CHECKER.FORBIDDEN_AUTHORITY:
            self.assert_decision_rejected(lambda value, key=key: value["executionAuthority"].update({key: True}))
            self.assert_handoff_rejected(lambda value, key=key: value["authorization"].update({key: True}))
            self.assert_progress_rejected(lambda value, key=key: value["executionAuthority"].update({key: True}))

    def test_boolean_integer_confusion_fails(self) -> None:
        self.assert_decision_rejected(lambda value: value["acquisitionAuthorization"].update({"networkIOAllowed": 1}))
        self.assert_handoff_rejected(lambda value: value["authorization"].update({"compilerInvocationAuthorized": 0}))
        self.assert_progress_rejected(lambda value: value["executionAuthority"].update({"phaseBExecutionAuthorized": 0}))

    def test_progress_cannot_claim_unperformed_work(self) -> None:
        self.assert_progress_rejected(lambda value: value["acquisitionState"].update({"completedRequestCount": 1}))
        self.assert_progress_rejected(lambda value: value["acquisitionState"].update({"sourceArchivePresent": True}))

    def test_duplicate_names_fail(self) -> None:
        raw = CHECKER.DECISION_PATH.read_text(encoding="utf-8").replace(
            '  "status": "closed_libnice_source_acquisition_authorized_dependency_lock_pending",',
            '  "status": "open",\n  "status": "closed_libnice_source_acquisition_authorized_dependency_lock_pending",',
            1,
        )
        with self.assertRaises(CHECKER.AuthorityValidationError):
            CHECKER.parse_json(raw, "duplicate status")


if __name__ == "__main__":
    unittest.main()
