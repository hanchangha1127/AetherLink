#!/usr/bin/env python3
"""Mutation tests for the exact GLib acquisition authority."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "script/check_p2p_nat_glib_acquisition_authority.py"
SPEC = importlib.util.spec_from_file_location("glib_authority", PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load GLib authority checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class GlibAuthorityMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision = CHECKER.parse_json(CHECKER.DECISION_PATH)
        cls.handoff = CHECKER.parse_json(CHECKER.HANDOFF_PATH)
        cls.progress = CHECKER.parse_json(CHECKER.PROGRESS_PATH)

    def rejected(self, validator, source, mutation) -> None:
        candidate = copy.deepcopy(source)
        mutation(candidate)
        with self.assertRaises(CHECKER.AuthorityValidationError):
            validator(candidate)

    def test_canonical_chain_passes(self) -> None:
        CHECKER.validate_decision(copy.deepcopy(self.decision))
        CHECKER.validate_handoff(copy.deepcopy(self.handoff))
        CHECKER.validate_progress(copy.deepcopy(self.progress))
        for path, expected in CHECKER.HASHES.items():
            CHECKER.validate_hash(path, expected)

    def test_url_host_hash_and_size_drift_fail(self) -> None:
        self.rejected(CHECKER.validate_decision, self.decision, lambda value: value["acquisitionAuthorization"]["artifacts"][1].update({"url": "https://example.com/glib.tar.xz"}))
        self.rejected(CHECKER.validate_decision, self.decision, lambda value: value["acquisitionAuthorization"]["artifacts"][1].update({"expectedSha256": "0" * 64}))
        self.rejected(CHECKER.validate_decision, self.decision, lambda value: value["acquisitionAuthorization"]["artifacts"][1].update({"maximumBytes": 67_108_865}))

    def test_redirect_proxy_and_package_manager_fail(self) -> None:
        for key in ("redirectFollowingAllowed", "environmentProxyAllowed", "packageManagerAcquisitionAllowed"):
            self.rejected(CHECKER.validate_decision, self.decision, lambda value, key=key: value["acquisitionAuthorization"].update({key: True}))

    def test_openssl_and_other_dependency_escalation_fail(self) -> None:
        self.rejected(CHECKER.validate_decision, self.decision, lambda value: value["furtherDependencyAcquisition"].update({"opensslAcquisitionAuthorized": True}))
        self.rejected(CHECKER.validate_handoff, self.handoff, lambda value: value["authorization"].update({"otherDependencyAcquisitionAuthorized": True}))
        self.rejected(CHECKER.validate_progress, self.progress, lambda value: value["authorization"].update({"opensslAcquisitionNetworkIOAllowed": True}))

    def test_execution_escalation_and_type_confusion_fail(self) -> None:
        for key in CHECKER.FORBIDDEN:
            self.rejected(CHECKER.validate_decision, self.decision, lambda value, key=key: value["executionAuthority"].update({key: True}))
        self.rejected(CHECKER.validate_handoff, self.handoff, lambda value: value["authorization"].update({"compilerInvocationAuthorized": 0}))
        self.rejected(CHECKER.validate_progress, self.progress, lambda value: value["authorization"].update({"phaseBExecutionAuthorized": 0}))

    def test_progress_cannot_claim_acquisition(self) -> None:
        self.rejected(CHECKER.validate_progress, self.progress, lambda value: value["acquisitionState"].update({"completedRequestCount": 1}))
        self.rejected(CHECKER.validate_progress, self.progress, lambda value: value["acquisitionState"].update({"sourceArchivePresent": True}))


if __name__ == "__main__":
    unittest.main()
