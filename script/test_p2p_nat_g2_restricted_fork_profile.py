#!/usr/bin/env python3
"""Exactly seventeen adversarial mutation tests for the G2 schema 1.1 profile."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_restricted_fork_profile.py"
SPEC = importlib.util.spec_from_file_location("g2_restricted_fork_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load G2 restricted-fork checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class G2RestrictedForkMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = CHECKER.load_json(CHECKER.PROFILE_PATH)
        cls.hardening = CHECKER.load_json(CHECKER.HARDENING_PATH)
        cls.manifest = CHECKER.load_json(CHECKER.EVIDENCE_MANIFEST_PATH)

    def assert_profile_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.profile)
        mutation(candidate)
        with self.assertRaises(CHECKER.RestrictedForkValidationError):
            CHECKER.validate_profile_document(candidate, require_canonical=False)

    def assert_hardening_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.hardening)
        mutation(candidate)
        with self.assertRaises(CHECKER.RestrictedForkValidationError):
            CHECKER.validate_hardening_document(candidate, require_canonical=False)

    def assert_hardening_enum_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.hardening)
        mutation(candidate)
        with self.assertRaises(CHECKER.RestrictedForkValidationError):
            CHECKER.validate_hardening_enums(candidate)

    def assert_manifest_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.manifest)
        mutation(candidate)
        with self.assertRaises(CHECKER.RestrictedForkValidationError):
            CHECKER.validate_evidence_manifest(candidate, require_complete=False)

    def test_01_duplicate_root_and_nested_json_names_fail(self) -> None:
        raw = CHECKER.PROFILE_PATH.read_text(encoding="utf-8")
        candidates = (
            raw.replace(
                '  "status": "rung1_profile_complete_candidate_not_selected",',
                '  "status": "candidate_selected",\n  "status": "rung1_profile_complete_candidate_not_selected",',
                1,
            ),
            raw.replace(
                '    "sourceAcquisitionAllowed": false,',
                '    "sourceAcquisitionAllowed": true,\n    "sourceAcquisitionAllowed": false,',
                1,
            ),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate[:80]):
                with self.assertRaises(CHECKER.RestrictedForkValidationError):
                    CHECKER.parse_json(candidate)

    def test_02_non_finite_json_and_direct_values_fail(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                with self.assertRaises(CHECKER.RestrictedForkValidationError):
                    CHECKER.parse_json('{"value": ' + constant + "}")
        self.assert_profile_rejected(
            lambda value: value["resourceLimits"].update({"maximumEventBytes": float("nan")})
        )

    def test_03_closed_top_level_schema_and_identity_fail_closed(self) -> None:
        for mutation in (
            lambda value: value.pop("technicalDecision"),
            lambda value: value.update({"authorization": {}}),
            lambda value: value.update({"schemaVersion": "1.0"}),
            lambda value: value.update({"implementationStatus": "implemented"}),
            lambda value: value["resourceLimits"].update({"unknownLimit": 1}),
        ):
            self.assert_profile_rejected(mutation)

    def test_04_source_and_upstream_state_promotion_fails(self) -> None:
        for mutation in (
            lambda value: value["sourceReview"].update({"sourceAcquired": True}),
            lambda value: value["sourceReview"].update({"sourceCompiled": True}),
            lambda value: value["sourceReview"].update({"sourceExecuted": True}),
            lambda value: value["upstreamBaseline"].update({"commit": "0" * 40}),
            lambda value: value["upstreamBaseline"]["observedDirectDependencies"].pop(),
        ):
            self.assert_profile_rejected(mutation)

    def test_05_governance_and_feature_profile_drift_fails(self) -> None:
        for mutation in (
            lambda value: value["forkGovernance"]["minimumPatchOrder"].reverse(),
            lambda value: value["forkGovernance"].update({"upstreamMergePolicy": "automatic"}),
            lambda value: value["featureProfile"]["allowed"].append("active_ice_tcp_candidates"),
            lambda value: value["featureProfile"]["disabled"].remove("mdns"),
        ):
            self.assert_profile_rejected(mutation)

    def test_06_egress_capability_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["networkPolicyBoundary"]["egressCapability"].update({"capabilityReuseAllowed": True}),
            lambda value: value["networkPolicyBoundary"]["egressCapability"].update({"wildcardBindAllowed": True}),
            lambda value: value["networkPolicyBoundary"]["egressCapability"].update({"policyUnavailableRule": "allow"}),
            lambda value: value["networkPolicyBoundary"]["egressCapability"]["allowedOperationOrder"].remove("turn_tls_sni_alpn_handshake"),
        ):
            self.assert_profile_rejected(mutation)

    def test_07_ingress_admission_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["networkPolicyBoundary"]["ingressAdmission"].update({"consumerDeliveryRule": "deliver_before_admission"}),
            lambda value: value["networkPolicyBoundary"]["ingressAdmission"].update({"unknownOrInvalidInputRule": "accept"}),
            lambda value: value["networkPolicyBoundary"]["ingressAdmission"]["preStateMutationChecks"].pop(),
            lambda value: value["networkPolicyBoundary"]["ingressAdmission"]["allowedIngressPathOrder"].remove("turn_tls_authenticated_frame_admission"),
        ):
            self.assert_profile_rejected(mutation)

    def test_08_turn_tls_identity_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["turnTlsServiceIdentity"].update({"tlsMinimumVersion": "1.2"}),
            lambda value: value["turnTlsServiceIdentity"].update({"requiredAlpn": ""}),
            lambda value: value["turnTlsServiceIdentity"].update({"insecureSkipVerifyAllowed": True}),
            lambda value: value["turnTlsServiceIdentity"].update({"ambientProxyAllowed": True}),
            lambda value: value["turnTlsServiceIdentity"].update({"credentialWriteRule": "send_before_identity"}),
        ):
            self.assert_profile_rejected(mutation)

    def test_09_pre_auth_promotion_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["secureSessionPromotion"]["preAuthCapability"].update({"applicationRecordAllowed": True}),
            lambda value: value["secureSessionPromotion"]["preAuthCapability"].update({"maximumLifetimeMilliseconds": 60000}),
            lambda value: value["secureSessionPromotion"].update({"promotionRule": "reuse_pre_auth_capability"}),
            lambda value: value["secureSessionPromotion"]["revocationEvents"].reverse(),
            lambda value: value["secureSessionPromotion"]["revocationEvents"].remove("consent_loss"),
            lambda value: value["secureSessionPromotion"].update({"revocationRule": "defer_revocation"}),
            lambda value: value["secureSessionPromotion"]["postAuthCapability"].update({"plaintextOrLegacyFallbackAllowed": True}),
            lambda value: value["secureSessionPromotion"].update({"pionOrIceMayAuthenticateEndpoint": True}),
        ):
            self.assert_profile_rejected(mutation)

    def test_10_reliable_carrier_blocker_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["secureSessionPromotion"]["carrierBoundary"].update({"reliableCarrierSelected": True}),
            lambda value: value["secureSessionPromotion"]["carrierBoundary"].update({"recordFragmentationFormatDefined": True}),
            lambda value: value["secureSessionPromotion"]["carrierBoundary"].update({"runtimeRequiredInput": "unordered_datagrams"}),
            lambda value: value["secureSessionPromotion"]["carrierBoundary"].update({"rule": "attach_now"}),
        ):
            self.assert_profile_rejected(mutation)

    def test_11_resource_and_sticky_terminal_latch_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["resourceLimits"].update({"maximumPendingEventsPerSession": 65}),
            lambda value: value["resourceLimits"].update({"scopeRule": "per_session_limits_include_current_and_draining_generations"}),
            lambda value: value["resourceLimits"].update({"processAggregateRule": "process_totals_include_all_active_and_draining_sessions_and_must_not_exceed_the_exact_process_ceilings"}),
            lambda value: value["verificationMatrix"][5]["requiredChecks"].__setitem__(1, "two_session_process_aggregate_limits_hold_with_draining_generations"),
            lambda value: value["resourceLimits"].update({"maximumIngressBytesPerSecondPerProcess": 0}),
            lambda value: value["resourceLimits"].update({"stickyTerminalLatchSlotsPerSession": 0}),
            lambda value: value["resourceLimits"].update({"eventOverflowRule": "drop_terminal_event"}),
            lambda value: value["resourceLimits"].update({"maximumTurnServers": True}),
        ):
            self.assert_profile_rejected(mutation)

    def test_12_logging_and_shutdown_state_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["loggingPolicy"].update({"implementationStatus": "implemented"}),
            lambda value: value["loggingPolicy"].update({"remoteIcePasswordLogRemovalRequired": False}),
            lambda value: value["loggingPolicy"]["forbiddenFields"].remove("remote_ice_password"),
            lambda value: value["shutdownPolicy"].update({"totalCloseDeadlineMilliseconds": 5000}),
            lambda value: value["shutdownPolicy"].update({"finalizerRelianceAllowed": True}),
        ):
            self.assert_profile_rejected(mutation)

    def test_13_supply_chain_and_maintenance_mutations_fail(self) -> None:
        for mutation in (
            lambda value: value["buildAndSupplyChain"]["toolchainPins"].update({"xMobileRevision": "unreviewed-main"}),
            lambda value: value["buildAndSupplyChain"]["requiredArtifacts"].pop(),
            lambda value: value["buildAndSupplyChain"]["futureCompileOnlyTargets"].append("macos_x86_64"),
            lambda value: value["maintenancePolicy"].update({"dependencyAdvisoryReviewCadenceDays": 90}),
            lambda value: value["maintenancePolicy"].update({"releaseBlockRule": "best_effort"}),
        ):
            self.assert_profile_rejected(mutation)

    def test_14_verification_and_disposition_promotions_fail(self) -> None:
        for mutation in (
            lambda value: value["verificationMatrix"][0].update({"status": "passed"}),
            lambda value: value["verificationMatrix"].pop(),
            lambda value: value["verificationMatrix"][0]["requiredChecks"].pop(),
            lambda value: value["technicalDecision"].update({"currentResult": "candidate_selected"}),
            lambda value: value["technicalDecision"].update({"recommendedNextAction": "acquire_and_compile"}),
            lambda value: value["disposition"].update({"candidateSelected": True}),
            lambda value: value["disposition"].update({"result": "selected_for_compile"}),
        ):
            self.assert_profile_rejected(mutation)

    def test_15_all_execution_external_identity_and_user_action_flags_stay_false(self) -> None:
        fields = CHECKER.EXECUTION_FALSE_FIELDS + (
            "rung2DecisionRecorded", "externalIdentityProofRequired", "userActionRequired",
        )
        for field in fields:
            with self.subTest(field=field):
                self.assert_profile_rejected(
                    lambda value, field=field: value["technicalDecision"].update({field: True})
                )
                self.assert_hardening_rejected(
                    lambda value, field=field: value["technicalBoundary"].update({field: True})
                )
        for field in (
            "externalIdentityProofRequired", "userActionRequired", "repositoryOwnerAuthenticationRequired",
        ):
            self.assert_hardening_rejected(
                lambda value, field=field: value["governanceBoundary"].update({field: True})
            )
        self.assert_hardening_rejected(
            lambda value: value["governanceBoundary"].update({"productEndpointAuthenticationRequired": False})
        )

    def test_16_hardening_sections_and_diagram_paths_are_exact(self) -> None:
        for mutation in (
            lambda value: value["assessment"].update({"summary": "A different assessment."}),
            lambda value: value["constraints"].update({"profile": "permissive"}),
            lambda value: value["opportunities"][0]["evidence"][0].update({"claim": "A different claim."}),
            lambda value: value["opportunities"][0].update({"result": "candidate_selected"}),
            lambda value: value["opportunities"][0]["options"].reverse(),
            lambda value: value["opportunities"][0]["options"][2]["diagramPaths"].update({"before": "context.md"}),
            lambda value: value["opportunities"][0]["options"][2]["diagramPaths"].update({"after": "context.md"}),
            lambda value: value["openQuestions"].clear(),
        ):
            self.assert_hardening_rejected(mutation)
        for mutation in (
            lambda value: value["opportunities"][0]["evidence"][0].update({"sourceKind": "evidence_synthesis"}),
            lambda value: value["opportunities"][0]["evidence"][0].update({"claimType": "measured"}),
            lambda value: value["opportunities"][0]["options"][2].update({"kind": "recommended"}),
            lambda value: value["opportunities"][0]["options"][2]["evidenceCoverage"][0].update({"effect": "fixed"}),
            lambda value: value["opportunities"][0]["options"][2]["tradeoffs"][0].update({"direction": "better"}),
            lambda value: value["opportunities"][0]["options"][2]["tradeoffs"][0].update({"confidence": "certain"}),
            lambda value: value["opportunities"][0]["options"][2]["tradeoffs"][0].update({"basis": "design-derived"}),
        ):
            self.assert_hardening_enum_rejected(mutation)

    def test_17_recursive_claim_manifest_markdown_and_byte_hash_guards(self) -> None:
        phrases = (
            "The candidate is ready for production.",
            "The candidate is production ready.",
            "Authorization was granted.",
            "All runtime checks passed.",
            "The candidate was selected.",
            "The source was acquired.",
            "The fork compiled successfully.",
            "Production validation passed.",
            "The production release was approved.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assert_hardening_rejected(
                    lambda value, phrase=phrase: value["opportunities"][0]["options"][2]["tradeoffs"][0].update({"assessment": phrase})
                )

        CHECKER.validate_evidence_manifest(copy.deepcopy(self.manifest), require_complete=False)
        self.assert_manifest_rejected(lambda value: value.update({"unknown": True}))
        self.assert_manifest_rejected(
            lambda value: value["artifacts"][0].update({"path": "../outside.md"})
        )
        self.assert_manifest_rejected(
            lambda value: value.update({"externalIdentityProofRequired": True})
        )

        profile_markdown = CHECKER.PROFILE_MARKDOWN_PATH.read_text(encoding="utf-8")
        with self.assertRaises(CHECKER.RestrictedForkValidationError):
            CHECKER.validate_profile_markdown(profile_markdown + "\nAuthorization was granted.\n")

        CHECKER.validate_profile_document(copy.deepcopy(self.profile), require_canonical=True)
        CHECKER.validate_hardening_document(copy.deepcopy(self.hardening), require_canonical=True)
        CHECKER.validate_hardening_enums(copy.deepcopy(self.hardening))
        original = CHECKER.ARTIFACT_SHA256[CHECKER.PROFILE_PATH]
        try:
            CHECKER.ARTIFACT_SHA256[CHECKER.PROFILE_PATH] = "0" * 64
            CHECKER.validate_profile_document(copy.deepcopy(self.profile), require_canonical=False)
            with self.assertRaises(CHECKER.RestrictedForkValidationError):
                CHECKER.validate_artifact_hashes()
        finally:
            CHECKER.ARTIFACT_SHA256[CHECKER.PROFILE_PATH] = original

        placeholders = any(
            isinstance(row.get("sha256"), str) and row["sha256"].startswith("__")
            for row in self.manifest["artifacts"]
        ) or str(self.manifest["collectionSha256"]).startswith("__")
        if placeholders:
            with self.assertRaises(CHECKER.RestrictedForkValidationError):
                CHECKER.validate_evidence_manifest(copy.deepcopy(self.manifest))
        else:
            CHECKER.validate_evidence_manifest(copy.deepcopy(self.manifest))
            CHECKER.validate_profile_manifest_link(self.profile, self.manifest)
            CHECKER.validate_all()


if __name__ == "__main__":
    unittest.main()
