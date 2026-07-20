from __future__ import annotations

import base64
import copy
from decimal import Decimal, Inexact, localcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from script import check_v1_g0_decision


ROOT = Path(__file__).resolve().parents[1]
TEST_SIGNER_ID = "release-evidence-test"
TEST_PUBLIC_KEY = b"test-public-key"
TEST_SIGNERS = {TEST_SIGNER_ID: TEST_PUBLIC_KEY}


def deterministic_test_signature(canonical_payload: bytes) -> str:
    digest = hashlib.sha512(TEST_PUBLIC_KEY + b"\0" + canonical_payload).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def verify_test_signature(
    algorithm: str,
    public_key: object,
    canonical_payload: bytes,
    signature: str,
) -> bool:
    return (
        algorithm == "ed25519"
        and public_key == TEST_PUBLIC_KEY
        and signature == deterministic_test_signature(canonical_payload)
    )


def attach_signed_evidence(
    record: dict[str, object],
    samples: list[int | float],
    *,
    variant_observations: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], dict[str, bytes]]:
    context_fields = (
        "network_cell",
        "network_variant",
        "provider_adapter",
        "selected_route",
        "direct_outcome",
        "fallback_outcome",
        "variant_outcome",
        "region",
        "window_hours",
        "peak_forecast_id",
        "projected_peak_units",
        "offered_load_units",
        "unbounded_growth_event_count",
        "admission_policy_weakening_event_count",
        "false_rejection_count",
    )
    payload = {
        "schema_version": 1,
        "evidence_kind": "signed_rc_metric_samples",
        "campaign_id": record["campaign_id"],
        "app_build": record["app_build"],
        "app_version": record["app_version"],
        "record_kind": record["record_kind"],
        "measurement_contract": record["measurement_contract"],
        "metric_name": record["metric_name"],
        "threshold_operator": record["threshold_operator"],
        "threshold_value": record["threshold_value"],
        "platform": record["platform"],
        "device_class": record["device_class"],
        "context": {field: record.get(field) for field in context_fields},
        "samples": samples,
        "variant_observations": (
            [] if variant_observations is None else variant_observations
        ),
    }
    envelope = {
        "payload": payload,
        "signer_id": TEST_SIGNER_ID,
        "signature_algorithm": "ed25519",
        "signature": deterministic_test_signature(
            check_v1_g0_decision.canonical_release_evidence_json(payload)
        ),
    }
    evidence = check_v1_g0_decision.canonical_release_evidence_json(envelope)
    digest = hashlib.sha256(evidence).hexdigest()
    result = copy.deepcopy(record)
    result["evidence_sha256"] = digest
    result["evidence_ref"] = f"sha256:{digest}"
    return result, {f"sha256:{digest}": evidence}


def rewrite_signed_evidence(
    record: dict[str, object],
    artifacts: dict[str, bytes],
    *,
    payload_updates: dict[str, object] | None = None,
    context_updates: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, bytes]]:
    envelope = json.loads(artifacts[record["evidence_ref"]].decode("utf-8"))
    payload = envelope["payload"]
    if payload_updates is not None:
        payload.update(payload_updates)
    if context_updates is not None:
        payload["context"].update(context_updates)
    canonical_payload = check_v1_g0_decision.canonical_release_evidence_json(payload)
    envelope["signature"] = deterministic_test_signature(canonical_payload)
    evidence = check_v1_g0_decision.canonical_release_evidence_json(envelope)
    digest = hashlib.sha256(evidence).hexdigest()
    result = copy.deepcopy(record)
    result["evidence_sha256"] = digest
    result["evidence_ref"] = f"sha256:{digest}"
    return result, {f"sha256:{digest}": evidence}


def make_variant_observations(
    count: int,
    *,
    affected_scope: str,
    direct_outcome: str,
    fallback_outcome: str,
    outage_connection_outcome: str,
    outage_authentication_outcome: str,
    outage_route: str,
    recovery_route: str,
    requires_recovery: bool,
    affected_region: str | None = None,
) -> list[dict[str, object]]:
    return [
        {
            "attempt_index": index,
            "affected_scope": affected_scope,
            "affected_region": affected_region,
            "direct_outcome": direct_outcome,
            "fallback_outcome": fallback_outcome,
            "outage_connection_outcome": outage_connection_outcome,
            "outage_authentication_outcome": outage_authentication_outcome,
            "outage_route": outage_route,
            "recovery_route": recovery_route,
            "recovery_connection_outcome": (
                "success" if requires_recovery else "not_required"
            ),
            "recovery_authentication_outcome": (
                "success" if requires_recovery else "not_required"
            ),
            "condition_activated_offset_milliseconds": 0,
            "condition_result_offset_milliseconds": 1,
            "service_restored_offset_milliseconds": 2 if requires_recovery else None,
            "recovery_authenticated_offset_milliseconds": (
                3 if requires_recovery else None
            ),
            "plaintext_downgrade_event_count": 0,
            "identity_downgrade_event_count": 0,
            "weaker_route_event_count": 0,
            "post_consent_loss_traffic_event_count": 0,
        }
        for index in range(1, count + 1)
    ]


class V1G0DecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = (ROOT / "docs/v1/g0/decision-v1.json").read_text(encoding="utf-8")
        cls.document = json.loads(cls.raw)
        cls.markdown = (ROOT / "docs/v1/g0/decision-v1.md").read_text(encoding="utf-8")
        cls.assurance_raw = (ROOT / "docs/v1/g0/assurance-v1.json").read_text(encoding="utf-8")
        cls.assurance = json.loads(cls.assurance_raw)
        cls.assurance_markdown = (ROOT / "docs/v1/g0/assurance-v1.md").read_text(encoding="utf-8")
        cls.amendment_raw = (
            ROOT / "docs/v1/g0/assurance-closure-amendment-v2.json"
        ).read_text(encoding="utf-8")
        cls.amendment = json.loads(cls.amendment_raw)
        cls.amendment_checkpoint_raw = (
            ROOT / "docs/v1/g0/assurance-closure-amendment-checkpoint-v2.json"
        ).read_text(encoding="utf-8")
        cls.amendment_markdown = (
            ROOT / "docs/v1/g0/assurance-closure-amendment-v2.md"
        ).read_text(encoding="utf-8")

    def failures(
        self,
        document: dict[str, object] | None = None,
        *,
        raw: str | None = None,
        markdown: str | None = None,
    ) -> list[str]:
        if raw is None:
            raw = json.dumps(document if document is not None else self.document)
        return check_v1_g0_decision.collect_failures(
            raw_json=raw,
            markdown=self.markdown if markdown is None else markdown,
            verify_files=False,
        )

    def mutated(self) -> dict[str, object]:
        return copy.deepcopy(self.document)

    def assurance_failures(
        self,
        assurance: dict[str, object] | None = None,
        *,
        raw: str | None = None,
        markdown: str | None = None,
    ) -> list[str]:
        if raw is None:
            raw = json.dumps(assurance if assurance is not None else self.assurance)
        return check_v1_g0_decision.collect_assurance_failures(
            decision=self.document,
            raw_json=raw,
            markdown=self.assurance_markdown if markdown is None else markdown,
            verify_files=False,
        )

    def mutated_assurance(self) -> dict[str, object]:
        return copy.deepcopy(self.assurance)

    def amendment_failures(
        self,
        amendment: dict[str, object] | None = None,
        *,
        raw: str | None = None,
        checkpoint_raw: str | None = None,
    ) -> list[str]:
        if raw is None:
            raw = json.dumps(amendment if amendment is not None else self.amendment)
        return check_v1_g0_decision.collect_assurance_amendment_failures(
            raw_json=raw,
            checkpoint_raw_json=(
                self.amendment_checkpoint_raw
                if checkpoint_raw is None
                else checkpoint_raw
            ),
            markdown=self.amendment_markdown,
            verify_files=False,
        )

    def mutated_amendment(self) -> dict[str, object]:
        return copy.deepcopy(self.amendment)

    def copy_amendment_fixture(self, root: Path) -> None:
        for relative_path in (
            "docs/v1/g0/assurance-v1.json",
            "docs/v1/g0/assurance-checkpoint-readback-v1.json",
            "docs/v1/g0/assurance-closure-amendment-v2.json",
            "docs/v1/g0/assurance-closure-amendment-checkpoint-v2.json",
            "docs/v1/g0/assurance-closure-amendment-v2.md",
            "script/check_no_device_quality.sh",
        ):
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative_path, destination)

    def test_current_decision_and_repository_baseline_pass(self) -> None:
        self.assertEqual(check_v1_g0_decision.collect_failures(), [])
        aggregate = (ROOT / "script/check_no_device_quality.sh").read_text(
            encoding="utf-8"
        )
        for required in (
            "script/check_v1_g0_publication_receipt.py",
            "script/test_v1_g0_publication_receipt.py",
            "script/check_v1_g0_receipt_bundle.py",
            "script/test_v1_g0_receipt_bundle.py",
        ):
            self.assertIn(required, aggregate)

    def test_assurance_closure_amendment_is_exact_fail_closed_and_non_authorizing(self) -> None:
        self.assertEqual(self.amendment_failures(), [])

        mutations: list[dict[str, object]] = []

        parent_drift = self.mutated_amendment()
        parent_drift["parent"]["assuranceRawByteSha256"] = "0" * 64
        mutations.append(parent_drift)

        nested_schema_reused = self.mutated_amendment()
        nested_schema_reused["operations"][2]["value"] = 1
        mutations.append(nested_schema_reused)

        reordered_patch = self.mutated_amendment()
        reordered_patch["operations"][3:5] = reversed(
            reordered_patch["operations"][3:5]
        )
        mutations.append(reordered_patch)

        unknown_path = self.mutated_amendment()
        unknown_path["operations"][3]["path"] = "/g0ClosureContract/implicitAuthority"
        mutations.append(unknown_path)

        profile_digest_forged = self.mutated_amendment()
        profile_digest_forged["operations"][7]["value"][0][
            "canonicalProfileSha256"
        ] = "0" * 64
        mutations.append(profile_digest_forged)

        profile_authorized = self.mutated_amendment()
        profile_authorized["operations"][7]["value"][0]["profileBody"][
            "currentAuthorizationState"
        ] = "authorized"
        mutations.append(profile_authorized)

        offline_removed = self.mutated_amendment()
        offline_removed["operations"][7]["value"][1]["profileBody"][
            "orderedSteps"
        ][0]["argv"].remove("--offline")
        mutations.append(offline_removed)

        executable_scope_expanded = self.mutated_amendment()
        executable_scope_expanded["operations"][4]["value"].append(
            "roadmap_and_g0_checkpoint_publication"
        )
        mutations.append(executable_scope_expanded)

        publication_binding_weakened = self.mutated_amendment()
        publication_binding_weakened["operations"][9]["value"][
            "commitContainmentPolicy"
        ] = "checkpoint_only"
        mutations.append(publication_binding_weakened)

        authority_opened = self.mutated_amendment()
        authority_opened["authority"]["compilerOrLinkerInvocationAllowed"] = True
        mutations.append(authority_opened)

        effective_digest_forged = self.mutated_amendment()
        effective_digest_forged["effectiveAssurance"]["canonicalSha256"] = "0" * 64
        mutations.append(effective_digest_forged)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertTrue(self.amendment_failures(mutation))

        duplicate_raw = self.amendment_raw.replace(
            '  "schemaVersion": "1.0",',
            '  "schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        self.assertTrue(
            any("duplicate key" in failure for failure in self.amendment_failures(raw=duplicate_raw))
        )

        checkpoint = json.loads(self.amendment_checkpoint_raw)
        checkpoint["authority"]["commandProfileExecutionAllowed"] = True
        self.assertTrue(
            self.amendment_failures(
                checkpoint_raw=json.dumps(checkpoint),
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            self.copy_amendment_fixture(fixture_root)
            amendment_path = (
                fixture_root / "docs/v1/g0/assurance-closure-amendment-v2.json"
            )
            matching_target = fixture_root / "matching-amendment.json"
            shutil.copy2(amendment_path, matching_target)
            amendment_path.unlink()
            amendment_path.symlink_to(matching_target)
            symlink_failures = (
                check_v1_g0_decision.collect_assurance_amendment_failures(
                    root=fixture_root,
                )
            )
            self.assertTrue(
                any("regular non-symlink" in failure for failure in symlink_failures)
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            self.copy_amendment_fixture(fixture_root)
            amendment_path = (
                fixture_root / "docs/v1/g0/assurance-closure-amendment-v2.json"
            )
            original_apply = (
                check_v1_g0_decision.apply_assurance_amendment_operations
            )
            replacement_done = False

            def apply_after_identical_replacement(
                parent: dict[str, object],
                operations: object,
                failures: list[str],
            ) -> dict[str, object]:
                nonlocal replacement_done
                if not replacement_done:
                    replacement_path = amendment_path.with_suffix(".replacement")
                    shutil.copy2(amendment_path, replacement_path)
                    os.replace(replacement_path, amendment_path)
                    replacement_done = True
                return original_apply(parent, operations, failures)

            with mock.patch.object(
                check_v1_g0_decision,
                "apply_assurance_amendment_operations",
                side_effect=apply_after_identical_replacement,
            ):
                replacement_failures = (
                    check_v1_g0_decision.collect_assurance_amendment_failures(
                        root=fixture_root,
                    )
                )
            self.assertTrue(
                any(
                    "repository path identity changed during validation" in failure
                    for failure in replacement_failures
                )
            )

    def test_duplicate_key_is_rejected(self) -> None:
        raw = self.raw.replace(
            '  "schemaVersion": "1.0",',
            '  "schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        self.assertTrue(any("duplicate key" in item for item in self.failures(raw=raw)))

    def test_non_finite_number_is_rejected(self) -> None:
        for replacement, expected in (
            ("NaN", "non-finite"),
            ("1e999", "non-finite"),
            ("9" * 129, "exceeding 128 digits"),
        ):
            with self.subTest(replacement=replacement[:16]):
                raw = self.raw.replace(
                    '"closedBetaCrashFreeSessionMinimum": 0.995',
                    f'"closedBetaCrashFreeSessionMinimum": {replacement}',
                    1,
                )
                self.assertTrue(
                    any(expected in item for item in self.failures(raw=raw))
                )

    def test_unknown_top_level_field_is_rejected(self) -> None:
        document = self.mutated()
        document["implicitAuthority"] = True
        self.assertTrue(any("unknown" in item for item in self.failures(document)))

    def test_g1a_cannot_open_while_g0_is_blocked(self) -> None:
        document = self.mutated()
        document["authority"]["g1aNoNetworkImplementationAllowed"] = True
        document["nextGate"]["g1aMayStartNow"] = True
        failures = self.failures(document)
        self.assertTrue(any("g1aNoNetworkImplementationAllowed" in item for item in failures))
        self.assertTrue(any("g1aMayStartNow" in item for item in failures))

    def test_portable_repository_baseline_cannot_leak_a_local_path(self) -> None:
        document = self.mutated()
        document["baseline"]["repository"] = "/Users/example/Desktop/project"
        self.assertTrue(
            any(
                "baseline.repository" in item
                for item in self.failures(document)
            )
        )

    def test_network_and_deployment_authority_cannot_open(self) -> None:
        document = self.mutated()
        document["authority"]["socketCreationAllowed"] = True
        document["authority"]["productionDeploymentAllowed"] = True
        failures = self.failures(document)
        self.assertTrue(any("socketCreationAllowed" in item for item in failures))
        self.assertTrue(any("productionDeploymentAllowed" in item for item in failures))

    def test_two_plane_fallback_cannot_silently_collapse(self) -> None:
        document = self.mutated()
        fallback = document["securitySelections"]["fallbackProfile"]
        fallback["disposition"] = "single_plane"
        fallback["emergencyFallback"] = None
        failures = self.failures(document)
        self.assertTrue(any("fallbackProfile.disposition" in item for item in failures))
        self.assertTrue(any("fallbackProfile.emergencyFallback" in item for item in failures))

    def test_local_direct_cannot_gain_a_service_lease_dependency(self) -> None:
        document = self.mutated()
        route = document["securitySelections"]["routeAuthorization"]
        route["localDirectServiceLeaseRequired"] = True
        self.assertTrue(any("localDirectServiceLeaseRequired" in item for item in self.failures(document)))

    def test_service_mediated_p2p_capabilities_are_mandatory(self) -> None:
        document = self.mutated()
        route = document["securitySelections"]["routeAuthorization"]
        route["serviceMediatedP2pCandidatePublishCapabilityRequired"] = False
        route["serviceMediatedP2pCandidateFetchCapabilityRequired"] = False
        route["capabilityFreeRemoteP2pAllowed"] = True
        failures = self.failures(document)
        self.assertTrue(any("serviceMediatedP2pCandidatePublishCapabilityRequired" in item for item in failures))
        self.assertTrue(any("serviceMediatedP2pCandidateFetchCapabilityRequired" in item for item in failures))
        self.assertTrue(any("capabilityFreeRemoteP2pAllowed" in item for item in failures))

    def test_revocation_retained_state_has_an_absolute_closure_bound(self) -> None:
        document = self.mutated()
        document["qualityGates"]["revocationClosureMilliseconds"]["absoluteMaximum"] = 30001
        self.assertTrue(any("revocationClosureMilliseconds" in item for item in self.failures(document)))

    def test_rollback_success_gate_cannot_drop_below_one(self) -> None:
        document = self.mutated()
        document["qualityGates"]["rollbackSuccessMinimum"] = 0.99
        failures = self.failures(document)
        self.assertTrue(any("rollbackSuccessMinimum" in item for item in failures))

        document = self.mutated()
        document["qualityGates"]["measurementContracts"][-1]["targetFields"].remove(
            "rollbackSuccessMinimum"
        )
        failures = self.failures(document)
        self.assertTrue(any("targetFields" in item for item in failures))

    def test_deny_only_revoke_cannot_become_one_sided_replacement(self) -> None:
        document = self.mutated()
        recovery = document["securitySelections"]["pairRecovery"]
        recovery["silentOneSidedKeyReplacementAllowed"] = True
        self.assertTrue(any("silentOneSidedKeyReplacementAllowed" in item for item in self.failures(document)))

    def test_pair_recovery_rotation_receipt_and_epoch_bindings_are_required(self) -> None:
        document = self.mutated()
        recovery = document["securitySelections"]["pairRecovery"]
        recovery["bindingTargets"].remove("route_refresh")
        recovery["replacementRotatesEndpointTrafficSecret"] = False
        recovery["replacementRotatesRouteTokenSeed"] = False
        recovery["offlineReactivationRequiresCurrentSignedReceipt"] = False
        failures = self.failures(document)
        for field in (
            "bindingTargets",
            "replacementRotatesEndpointTrafficSecret",
            "replacementRotatesRouteTokenSeed",
            "offlineReactivationRequiresCurrentSignedReceipt",
        ):
            self.assertTrue(any(field in item for item in failures), field)

    def test_all_g0_blockers_are_required_and_ordered(self) -> None:
        document = self.mutated()
        document["blockers"].pop()
        self.assertTrue(any("blocker order" in item for item in self.failures(document)))

    def test_unknown_nested_security_field_is_rejected(self) -> None:
        document = self.mutated()
        document["securitySelections"]["fallbackProfile"]["implementationAuthorized"] = True
        self.assertTrue(
            any(
                "securitySelections.fallbackProfile keys drifted" in item
                for item in self.failures(document)
            )
        )

    def test_previously_unchecked_security_downgrades_are_rejected(self) -> None:
        document = self.mutated()
        security = document["securitySelections"]
        security["fallbackProfile"]["direct"] = "plaintext_unauthenticated_ice"
        security["fallbackProfile"]["applicationReadiness"] = "relay_service_identity"
        security["relayControlPlane"]["tlsTrust"] = "opportunistic_tls"
        security["relayControlPlane"]["leaseSigner"] = "unsigned"
        security["pairRecovery"]["keyReplacement"] = "one_sided_silent"
        failures = self.failures(document)
        for field in (
            "fallbackProfile.direct",
            "fallbackProfile.applicationReadiness",
            "relayControlPlane.tlsTrust",
            "relayControlPlane.leaseSigner",
            "pairRecovery.keyReplacement",
        ):
            self.assertTrue(any(field in item for item in failures), field)

    def test_security_hard_stop_names_are_fixed(self) -> None:
        document = self.mutated()
        hard_stops = document["qualityGates"]["securityHardStops"]
        del hard_stops["falseIdentityAcceptance"]
        hard_stops["replacementZeroGate"] = 0
        self.assertTrue(
            any("qualityGates.securityHardStops keys drifted" in item for item in self.failures(document))
        )

    def test_release_artifact_hard_stops_are_zero_and_non_omittable(self) -> None:
        document = self.mutated()
        hard_stops = document["qualityGates"]["securityHardStops"]
        hard_stops["unauthorizedReleaseArtifactAcceptance"] = 1
        del hard_stops["releaseArtifactProvenanceFailures"]
        failures = self.failures(document)
        self.assertTrue(any("qualityGates.securityHardStops" in item for item in failures))

    def test_all_network_matrix_cells_are_required(self) -> None:
        document = self.mutated()
        document["networkMatrix"]["requiredCells"].pop()
        self.assertTrue(any("network matrix cell order" in item for item in self.failures(document)))

    def test_all_network_matrix_variants_are_required(self) -> None:
        document = self.mutated()
        document["networkMatrix"]["requiredVariants"].pop()
        self.assertTrue(any("network matrix variant order" in item for item in self.failures(document)))

    def test_required_p2p_cells_have_a_release_blocking_threshold(self) -> None:
        document = self.mutated()
        document["qualityGates"]["p2pRequiredCellObservedDirectSuccessMinimum"] = 0.0
        self.assertTrue(
            any(
                "p2pRequiredCellObservedDirectSuccessMinimum" in item
                for item in self.failures(document)
            )
        )

    def test_all_quality_measurement_contracts_are_required(self) -> None:
        document = self.mutated()
        document["qualityGates"]["measurementContracts"].pop()
        self.assertTrue(any("measurement contract order" in item for item in self.failures(document)))

    def test_source_record_hash_drift_is_rejected(self) -> None:
        document = self.mutated()
        document["sourceRecords"][0]["sha256"] = "0" * 64
        self.assertTrue(any("sourceRecords" in item for item in self.failures(document)))

    def test_supported_platform_floor_cannot_drift(self) -> None:
        document = self.mutated()
        document["productScope"]["platforms"]["android"]["minimumApi"] = 25
        document["productScope"]["platforms"]["macos"]["architectures"] = ["arm64", "x86_64"]
        failures = self.failures(document)
        self.assertTrue(any("android.minimumApi" in item for item in failures))
        self.assertTrue(any("macos.architectures" in item for item in failures))

    def test_markdown_must_keep_authority_boundary(self) -> None:
        markdown = self.markdown.replace("does not authorize G1a implementation", "allows implementation")
        self.assertTrue(any("does not authorize G1a implementation" in item for item in self.failures(markdown=markdown)))

    def test_assurance_duplicate_key_is_rejected(self) -> None:
        raw = self.assurance_raw.replace(
            '  "schemaVersion": "1.0",',
            '  "schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        self.assertTrue(any("duplicate key" in item for item in self.assurance_failures(raw=raw)))

        for replacement, expected in (
            ("1e999", "non-finite"),
            ("9" * 129, "exceeding 128 digits"),
        ):
            with self.subTest(replacement=replacement[:16]):
                raw = self.assurance_raw.replace(
                    '"schemaVersion": "1.0"',
                    f'"schemaVersion": {replacement}',
                    1,
                )
                self.assertTrue(
                    any(
                        expected in item
                        for item in self.assurance_failures(raw=raw)
                    )
                )

    def test_assurance_unknown_top_level_field_is_rejected(self) -> None:
        assurance = self.mutated_assurance()
        assurance["implementationAuthority"] = True
        self.assertTrue(any("G0 assurance keys drifted" in item for item in self.assurance_failures(assurance)))

    def test_assurance_source_hash_drift_is_rejected(self) -> None:
        assurance = self.mutated_assurance()
        assurance["sourceRecords"][0]["sha256"] = "0" * 64
        self.assertTrue(any("assurance source record hashes" in item for item in self.assurance_failures(assurance)))

    def test_assurance_filesystem_references_must_be_hash_pinned(self) -> None:
        assurance = self.mutated_assurance()
        assurance["protocolInventory"]["units"][0]["documentationRefs"].append(
            "docs/unpinned-assurance-source.md"
        )
        self.assertTrue(
            any(
                "unpinned filesystem references" in item
                for item in self.assurance_failures(assurance)
            )
        )

    def test_assurance_active_protocol_message_cannot_disappear(self) -> None:
        assurance = self.mutated_assurance()
        assurance["protocolInventory"]["activeMessageTypes"].remove("auth.response")
        self.assertTrue(any("protocolInventory.activeMessageTypes" in item for item in self.assurance_failures(assurance)))

    def test_assurance_reserved_namespaces_cannot_be_activated(self) -> None:
        assurance = self.mutated_assurance()
        assurance["protocolInventory"]["units"][-1]["state"] = "active_current"
        self.assertTrue(any("reserved namespace inventory state" in item for item in self.assurance_failures(assurance)))

    def test_assurance_namespace_policy_is_derived_and_non_omittable(self) -> None:
        assurance = self.mutated_assurance()
        protocol = assurance["protocolInventory"]
        protocol["guardedNamespacePrefixes"].remove("bootstrap.")
        protocol["namespaceActiveExceptions"]["route."] = [
            "route.refresh",
            "route.unapproved",
        ]
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("guardedNamespacePrefixes" in item for item in failures))
        self.assertTrue(any("namespaceActiveExceptions" in item for item in failures))

    def test_assurance_pair_recovery_contract_cannot_weaken(self) -> None:
        assurance = self.mutated_assurance()
        recovery = assurance["protocolInventory"]["pairRecoveryContract"]
        recovery["bindingTargets"].remove("application_authentication")
        recovery["replacementRotatesEndpointTrafficSecret"] = False
        recovery["offlineReactivationRequiresCurrentSignedReceipt"] = False
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("pairRecoveryContract" in item for item in failures))

    def test_assurance_markdown_reference_anchors_must_exist(self) -> None:
        assurance = self.mutated_assurance()
        assurance["protocolInventory"]["units"][0]["documentationRefs"] = [
            "docs/protocol.md#missing-assurance-heading"
        ]
        self.assertTrue(
            any(
                "markdown reference anchor does not exist" in item
                for item in self.assurance_failures(assurance)
            )
        )

    def test_assurance_must_cover_every_required_user_loop(self) -> None:
        assurance = self.mutated_assurance()
        memory_flow = assurance["dataFlowInventory"][5]
        memory_flow["userLoopIds"] = []
        self.assertTrue(any("data-flow required user-loop coverage" in item for item in self.assurance_failures(assurance)))

    def test_assurance_selected_control_plane_flows_are_non_omittable(self) -> None:
        assurance = self.mutated_assurance()
        assurance["dataFlowInventory"].pop()
        self.assertTrue(any("data-flow inventory order" in item for item in self.assurance_failures(assurance)))

    def test_assurance_endpoint_authority_request_flows_are_semantically_closed(self) -> None:
        assurance = self.mutated_assurance()
        flows = {flow["id"]: flow for flow in assurance["dataFlowInventory"]}
        flows["endpoint_to_allocation_authority"]["dataClasses"].remove("allocation_credential")
        flows["endpoint_to_pair_state_authority"]["dataClasses"].remove(
            "signed_revoke_replace_or_status_request"
        )
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("endpoint_to_allocation_authority.dataClasses" in item for item in failures))
        self.assertTrue(any("endpoint_to_pair_state_authority.dataClasses" in item for item in failures))

    def test_assurance_release_supply_chain_flows_and_threats_are_non_omittable(self) -> None:
        assurance = self.mutated_assurance()
        flows = {flow["id"]: flow for flow in assurance["dataFlowInventory"]}
        flows["android_release_build_to_play_install_update_and_forward_fix"]["dataClasses"].remove(
            "provenance_attestation"
        )
        flows["macos_release_build_to_notarized_dmg_install_update_and_rollback"]["trustBoundaries"].remove(
            "apple_notary_service"
        )
        assurance["threatModelRefresh"]["assets"].remove("release_provenance")
        assurance["riskRegister"][1]["sourceThreatIds"].remove("T026")
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("android_release_build_to_play" in item for item in failures))
        self.assertTrue(any("macos_release_build_to_notarized" in item for item in failures))
        self.assertTrue(any("release supply-chain boundary" in item for item in failures))
        self.assertTrue(any("R002 release supply-chain threat linkage" in item for item in failures))

    def test_assurance_risk_evidence_gate_mapping_cannot_drift(self) -> None:
        mutations: list[dict[str, object]] = []

        future_evidence_promoted_to_g0 = self.mutated_assurance()
        future_evidence_promoted_to_g0["riskRegister"][1]["requiredEvidence"][2][
            "requiredByGate"
        ] = "g0"
        mutations.append(future_evidence_promoted_to_g0)

        missing_gate = self.mutated_assurance()
        missing_gate["riskRegister"][8]["requiredEvidence"][1].pop(
            "requiredByGate"
        )
        mutations.append(missing_gate)

        reordered = self.mutated_assurance()
        reordered["riskRegister"][4]["requiredEvidence"][0:2] = reversed(
            reordered["riskRegister"][4]["requiredEvidence"][0:2]
        )
        mutations.append(reordered)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertTrue(
                    any(
                        "requiredEvidence gate mapping" in item
                        for item in self.assurance_failures(mutation)
                    )
                )

    def test_assurance_g0_closure_contract_cannot_drift_or_promote(self) -> None:
        mutations: list[dict[str, object]] = []

        missing_blocker = self.mutated_assurance()
        missing_blocker["g0ClosureContract"]["blockerRequirements"].pop()
        mutations.append(missing_blocker)

        missing_quality_owner = self.mutated_assurance()
        missing_quality_owner["g0ClosureContract"]["blockerRequirements"][8][
            "requiredOwnerRoles"
        ].remove("service_operations_and_abuse_owner")
        mutations.append(missing_quality_owner)

        wrong_check = self.mutated_assurance()
        wrong_check["g0ClosureContract"]["blockerRequirements"][0][
            "requiredCheckIds"
        ][0] = "future_release_check"
        mutations.append(wrong_check)

        weakened_derivation = self.mutated_assurance()
        weakened_derivation["g0ClosureContract"]["derivationRules"][
            "g0ExitComplete"
        ] = "all_owners_named"
        mutations.append(weakened_derivation)

        type_confused = self.mutated_assurance()
        type_confused["g0ClosureContract"]["schemaVersion"] = True
        mutations.append(type_confused)

        check_ids_type_confused = self.mutated_assurance()
        check_ids_type_confused["g0ClosureContract"]["blockerRequirements"][0][
            "requiredCheckIds"
        ] = True
        mutations.append(check_ids_type_confused)

        owner_roles_type_confused = self.mutated_assurance()
        owner_roles_type_confused["g0ClosureContract"]["blockerRequirements"][0][
            "requiredOwnerRoles"
        ] = 1
        mutations.append(owner_roles_type_confused)

        evidence_kinds_type_confused = self.mutated_assurance()
        evidence_kinds_type_confused["g0ClosureContract"]["blockerRequirements"][0][
            "requiredEvidenceKinds"
        ] = None
        mutations.append(evidence_kinds_type_confused)

        receipt_anchor_weakened = self.mutated_assurance()
        receipt_anchor_weakened["g0ClosureContract"]["receiptActivationPolicy"][
            "receiptDerivedTrustAnchorsAllowed"
        ] = True
        mutations.append(receipt_anchor_weakened)

        receipt_prerequisite_removed = self.mutated_assurance()
        receipt_prerequisite_removed["g0ClosureContract"]["receiptActivationPolicy"][
            "successorActivationPrerequisites"
        ].pop()
        mutations.append(receipt_prerequisite_removed)

        incomplete_check_evidence = self.mutated_assurance()
        incomplete_check_evidence["releaseChecklist"]["g0Exit"][7][
            "requiredEvidence"
        ].pop()
        mutations.append(incomplete_check_evidence)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                failures = self.assurance_failures(mutation)
                self.assertTrue(
                    any(
                        "g0ClosureContract" in item
                        or "releaseChecklist.g0Exit[7].requiredEvidence" in item
                        for item in failures
                    )
                )

    def test_assurance_route_refresh_flow_pins_actual_pairing_store(self) -> None:
        assurance = self.mutated_assurance()
        flow = assurance["dataFlowInventory"][2]
        flow["sourceRefs"].remove(
            "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt"
        )
        self.assertTrue(
            any(
                "authenticated_route_refresh sourceRefs is missing" in item
                for item in self.assurance_failures(assurance)
            )
        )

    def test_assurance_new_threat_set_is_non_omittable(self) -> None:
        assurance = self.mutated_assurance()
        assurance["threatModelRefresh"]["newThreats"].pop()
        self.assertTrue(any("new threat order" in item for item in self.assurance_failures(assurance)))

    def test_assurance_observability_rejects_non_allowlisted_fields(self) -> None:
        assurance = self.mutated_assurance()
        event = assurance["observabilitySchema"]["eventClasses"][0]
        event["allowedFields"].append("prompt")
        event["maximumFields"] += 1
        self.assertTrue(any("non-allowlisted field" in item for item in self.assurance_failures(assurance)))

    def test_assurance_observability_value_domains_reject_sensitive_values(self) -> None:
        definitions = self.assurance["observabilitySchema"]["fieldDefinitions"]
        validate = check_v1_g0_decision.observability_value_is_valid
        self.assertTrue(validate(definitions["outcome"], "success"))
        self.assertFalse(validate(definitions["reason_code"], "raw_prompt_contents"))
        self.assertFalse(validate(definitions["region"], "192.168.0.1"))
        self.assertTrue(
            validate(
                definitions["region"],
                "kr-seoul",
                registries={"approved_release_region_registry": {"kr-seoul"}},
            )
        )
        self.assertFalse(validate(definitions["revocation_closure_milliseconds"], 30001))
        self.assertFalse(validate(definitions["schema_version"], True))
        self.assertFalse(validate(definitions["app_version"], "1.0"))

    def test_assurance_observability_field_domains_are_closed(self) -> None:
        assurance = self.mutated_assurance()
        definitions = assurance["observabilitySchema"]["fieldDefinitions"]
        definitions["reason_code"]["enum"].append("raw_prompt_contents")
        definitions["revocation_closure_milliseconds"]["maximum"] = 30001
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("field definition enum reason_code" in item for item in failures))
        self.assertTrue(any("field definition maximum revocation_closure_milliseconds" in item for item in failures))

    def test_assurance_event_required_fields_are_non_omittable(self) -> None:
        assurance = self.mutated_assurance()
        assurance["observabilitySchema"]["eventClasses"][0]["requiredFields"].remove(
            "outcome"
        )
        self.assertTrue(
            any(
                "missing required base field outcome" in item
                for item in self.assurance_failures(assurance)
            )
        )

    def test_assurance_release_records_use_the_separate_allowlist(self) -> None:
        assurance = self.mutated_assurance()
        record = assurance["observabilitySchema"]["releaseRecordClasses"][0]
        record["allowedFields"].append("reason_code")
        record["maximumFields"] += 1
        self.assertTrue(
            any(
                "non-release-allowlisted field" in item
                for item in self.assurance_failures(assurance)
            )
        )

    def test_assurance_release_measurements_cover_every_gate_and_platform_row(self) -> None:
        assurance = self.mutated_assurance()
        schema = assurance["observabilitySchema"]
        schema["fieldDefinitions"]["device_class"]["enum"].remove("macos15_arm64")
        schema["supportedPlatformRows"]["macos"].remove("macos15_arm64")
        schema["qualityTargetBindings"][0]["thresholdValue"] = 1199
        schema["releaseRecordClasses"][0]["permittedMetricNames"].remove(
            "authenticated_handoff_p95_milliseconds"
        )
        schema["releaseRecordClasses"][0]["requiredFields"].remove("evidence_sha256")
        schema["releaseRecordClasses"][0]["allowedFields"].remove("successful_sample_count")
        schema["releaseRecordClasses"][0]["maximumFields"] -= 1
        capacity_profile = next(
            profile
            for profile in schema["metricEvidenceProfiles"]
            if profile["profileId"] == "capacity_integrity"
        )
        capacity_profile["minimumSampleCount"] = 0
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("field definition enum device_class" in item for item in failures))
        self.assertTrue(any("supportedPlatformRows" in item for item in failures))
        self.assertTrue(any("quality target threshold value" in item for item in failures))
        self.assertTrue(any("permittedMetricNames" in item for item in failures))
        self.assertTrue(any("required base field evidence_sha256" in item for item in failures))
        self.assertTrue(any("cannot carry required evidence" in item for item in failures))
        self.assertTrue(any("minimumSampleCount must be positive" in item for item in failures))

    def test_release_record_validation_binds_metric_threshold_platform_and_result(self) -> None:
        schema = self.assurance["observabilitySchema"]
        unsigned_record = {
            "record_kind": "network_measurement_result",
            "campaign_id": "rc-20260720-abcdef12",
            "app_build": 1,
            "app_version": "1.0.0",
            "platform": "service",
            "device_class": "service_control_plane",
            "measurement_contract": "network_reliability_and_latency",
            "metric_name": "minimum_completed_network_sessions",
            "metric_value": 1200,
            "threshold_operator": "minimum",
            "threshold_value": 1200,
            "sample_count": 1200,
            "gate_result": "passed",
        }
        record, artifacts = attach_signed_evidence(unsigned_record, [1] * 1200)
        validate = check_v1_g0_decision.release_record_is_valid
        validation_context = {
            "evidence_artifacts": artifacts,
            "approved_evidence_signers": TEST_SIGNERS,
            "evidence_signature_verifier": verify_test_signature,
        }
        self.assertTrue(validate(schema, record, **validation_context))

        wrong_threshold = copy.deepcopy(record)
        wrong_threshold["threshold_value"] = 1199
        self.assertFalse(validate(schema, wrong_threshold, **validation_context))

        false_pass = copy.deepcopy(record)
        false_pass["metric_value"] = 1199
        self.assertFalse(validate(schema, false_pass, **validation_context))

        wrong_platform_row = copy.deepcopy(record)
        wrong_platform_row["device_class"] = "macos14_arm64"
        self.assertFalse(validate(schema, wrong_platform_row, **validation_context))

        unknown_field = copy.deepcopy(record)
        unknown_field["prompt"] = "forbidden"
        self.assertFalse(validate(schema, unknown_field, **validation_context))

        self.assertFalse(validate(schema, record))
        self.assertFalse(
            validate(
                schema,
                record,
                evidence_artifacts=artifacts,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        boolean_schema_record, boolean_schema_artifacts = rewrite_signed_evidence(
            record,
            artifacts,
            payload_updates={"schema_version": True},
        )
        self.assertFalse(
            validate(
                schema,
                boolean_schema_record,
                evidence_artifacts=boolean_schema_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )
        self.assertFalse(
            validate(
                schema,
                record,
                evidence_artifacts=artifacts,
                approved_evidence_signers=TEST_SIGNERS,
            )
        )
        evidence_ref = record["evidence_ref"]
        corrupted_artifacts = {evidence_ref: b"different bytes"}
        self.assertFalse(
            validate(
                schema,
                record,
                evidence_artifacts=corrupted_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        arbitrary_evidence = b"not a signed release metric envelope"
        arbitrary_digest = hashlib.sha256(arbitrary_evidence).hexdigest()
        arbitrary_record = copy.deepcopy(record)
        arbitrary_record["evidence_sha256"] = arbitrary_digest
        arbitrary_record["evidence_ref"] = f"sha256:{arbitrary_digest}"
        self.assertFalse(
            validate(
                schema,
                arbitrary_record,
                evidence_artifacts={arbitrary_record["evidence_ref"]: arbitrary_evidence},
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

    def test_release_record_rejects_zero_sample_missing_context_and_false_capacity(self) -> None:
        schema = self.assurance["observabilitySchema"]
        base = {
            "campaign_id": "rc-20260720-1234abcd",
            "app_build": 1,
            "app_version": "1.0.0",
            "threshold_operator": "equal",
            "threshold_value": 0,
            "sample_count": 1,
            "gate_result": "passed",
        }
        security = {
            **base,
            "record_kind": "security_hard_stop_result",
            "platform": "service",
            "device_class": "service_control_plane",
            "measurement_contract": "security_hard_stops",
            "metric_name": "unauthorized_release_artifact_acceptance",
            "metric_value": 0,
        }
        security, security_artifacts = attach_signed_evidence(security, [0])
        validation_context = {
            "approved_evidence_signers": TEST_SIGNERS,
            "evidence_signature_verifier": verify_test_signature,
        }
        self.assertTrue(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                security,
                evidence_artifacts=security_artifacts,
                **validation_context,
            )
        )
        noncanonical_evidence = security_artifacts[security["evidence_ref"]].replace(
            b'"samples":[0]',
            b'"samples":[1e999]',
        )
        noncanonical_digest = hashlib.sha256(noncanonical_evidence).hexdigest()
        oversized_sample = copy.deepcopy(security)
        oversized_sample["evidence_sha256"] = noncanonical_digest
        oversized_sample["evidence_ref"] = f"sha256:{noncanonical_digest}"
        oversized_sample_artifacts = {
            oversized_sample["evidence_ref"]: noncanonical_evidence
        }
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                oversized_sample,
                evidence_artifacts=oversized_sample_artifacts,
                **validation_context,
            )
        )
        zero_sample = copy.deepcopy(security)
        zero_sample["sample_count"] = 0
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                zero_sample,
                evidence_artifacts=security_artifacts,
                **validation_context,
            )
        )

        valid_capacity = {
            **base,
            "record_kind": "abuse_and_capacity_result",
            "platform": "service",
            "device_class": "service_control_plane",
            "region": "kr-seoul",
            "measurement_contract": "abuse_and_capacity",
            "metric_name": "capacity_load_multiplier",
            "metric_value": 2.0,
            "threshold_operator": "minimum",
            "threshold_value": 2.0,
            "peak_forecast_id": "peak-20260720-aabbccdd",
            "projected_peak_units": 1,
            "offered_load_units": 2,
            "unbounded_growth_event_count": 0,
            "admission_policy_weakening_event_count": 0,
        }
        valid_capacity, valid_capacity_artifacts = attach_signed_evidence(
            valid_capacity,
            [2],
        )
        self.assertTrue(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                valid_capacity,
                registries={"approved_release_region_registry": {"kr-seoul"}},
                evidence_artifacts=valid_capacity_artifacts,
                **validation_context,
            )
        )
        boolean_context, boolean_context_artifacts = rewrite_signed_evidence(
            valid_capacity,
            valid_capacity_artifacts,
            context_updates={"projected_peak_units": True},
        )
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                boolean_context,
                registries={"approved_release_region_registry": {"kr-seoul"}},
                evidence_artifacts=boolean_context_artifacts,
                **validation_context,
            )
        )

        p2p = {
            **base,
            "record_kind": "network_measurement_result",
            "platform": "android",
            "device_class": "android_emulator_api26_arm64",
            "measurement_contract": "network_reliability_and_latency",
            "metric_name": "p2p_required_cell_observed_direct_success",
            "metric_value": 1.0,
            "threshold_operator": "minimum",
            "threshold_value": 0.95,
            "sample_count": 100,
            "successful_sample_count": 100,
        }
        p2p, p2p_artifacts = attach_signed_evidence(p2p, [1] * 100)
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                p2p,
                evidence_artifacts=p2p_artifacts,
                **validation_context,
            )
        )

        capacity = {
            **base,
            "record_kind": "abuse_and_capacity_result",
            "platform": "service",
            "device_class": "service_control_plane",
            "region": "kr-seoul",
            "measurement_contract": "abuse_and_capacity",
            "metric_name": "capacity_load_multiplier",
            "metric_value": 2.0,
            "threshold_operator": "minimum",
            "threshold_value": 2.0,
            "peak_forecast_id": "peak-20260720-1234abcd",
            "projected_peak_units": 1000,
            "offered_load_units": 1,
            "unbounded_growth_event_count": 999,
            "admission_policy_weakening_event_count": 999,
        }
        capacity, capacity_artifacts = attach_signed_evidence(capacity, [1])
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                capacity,
                registries={"approved_release_region_registry": {"kr-seoul"}},
                evidence_artifacts=capacity_artifacts,
                **validation_context,
            )
        )

    def test_release_record_derives_percentiles_from_signed_samples(self) -> None:
        schema = self.assurance["observabilitySchema"]
        forged_scalar = {
            "record_kind": "network_measurement_result",
            "campaign_id": "rc-20260720-c0ffee12",
            "app_build": 1,
            "app_version": "1.0.0",
            "platform": "android",
            "device_class": "android_emulator_api26_arm64",
            "measurement_contract": "network_reliability_and_latency",
            "metric_name": "traversal_setup_p95_milliseconds",
            "metric_value": 1,
            "threshold_operator": "maximum",
            "threshold_value": 5000,
            "sample_count": 100,
            "network_cell": "same_lan_ipv4_local_direct",
            "network_variant": "none",
            "provider_adapter": "ollama",
            "selected_route": "p2p_direct",
            "latency_milliseconds": 1,
            "gate_result": "passed",
        }
        record, artifacts = attach_signed_evidence(
            forged_scalar,
            [1] * 94 + [10000] * 6,
        )
        validate = check_v1_g0_decision.release_record_is_valid
        validation_context = {
            "evidence_artifacts": artifacts,
            "approved_evidence_signers": TEST_SIGNERS,
            "evidence_signature_verifier": verify_test_signature,
        }
        self.assertFalse(validate(schema, record, **validation_context))

        accurate_failure = copy.deepcopy(record)
        accurate_failure["metric_value"] = 10000
        accurate_failure["latency_milliseconds"] = 10000
        accurate_failure["gate_result"] = "failed"
        self.assertTrue(validate(schema, accurate_failure, **validation_context))

    def test_release_required_variants_bind_signed_outcome_and_route_combinations(self) -> None:
        schema = self.assurance["observabilitySchema"]
        bypass_record = {
            "record_kind": "network_measurement_result",
            "campaign_id": "rc-20260720-deadbeef",
            "app_build": 1,
            "app_version": "1.0.0",
            "platform": "android",
            "device_class": "android_emulator_api26_arm64",
            "measurement_contract": "network_reliability_and_latency",
            "metric_name": "attempts_per_required_variant",
            "metric_value": 30,
            "threshold_operator": "minimum",
            "threshold_value": 30,
            "sample_count": 30,
            "network_cell": "unrelated_home_nat_ipv4",
            "network_variant": "deliberate_p2p_failure",
            "provider_adapter": "ollama",
            "selected_route": "p2p_direct",
            "gate_result": "passed",
        }
        bypass_record, bypass_artifacts = attach_signed_evidence(
            bypass_record,
            [1] * 30,
        )
        validate = check_v1_g0_decision.release_record_is_valid
        self.assertFalse(
            validate(
                schema,
                bypass_record,
                evidence_artifacts=bypass_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        valid_record = copy.deepcopy(bypass_record)
        valid_record.update(
            {
                "selected_route": "turn_relay",
                "direct_outcome": "failure",
                "fallback_outcome": "success",
                "variant_outcome": (
                    "authenticated_fallback_without_plaintext_or_identity_downgrade"
                ),
            }
        )
        valid_observations = make_variant_observations(
            30,
            affected_scope="p2p_direct",
            direct_outcome="failure",
            fallback_outcome="success",
            outage_connection_outcome="success",
            outage_authentication_outcome="success",
            outage_route="turn_relay",
            recovery_route="none",
            requires_recovery=False,
        )
        valid_record, valid_artifacts = attach_signed_evidence(
            valid_record,
            [1] * 30,
            variant_observations=valid_observations,
        )
        validation_context = {
            "evidence_artifacts": valid_artifacts,
            "approved_evidence_signers": TEST_SIGNERS,
            "evidence_signature_verifier": verify_test_signature,
        }
        self.assertTrue(validate(schema, valid_record, **validation_context))

        zero_based_observations = copy.deepcopy(valid_observations)
        for index, observation in enumerate(zero_based_observations):
            observation["attempt_index"] = index
        zero_based_record, zero_based_artifacts = attach_signed_evidence(
            valid_record,
            [1] * 30,
            variant_observations=zero_based_observations,
        )
        self.assertFalse(
            validate(
                schema,
                zero_based_record,
                evidence_artifacts=zero_based_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        over_deadline_observations = copy.deepcopy(valid_observations)
        over_deadline_observations[-1][
            "condition_result_offset_milliseconds"
        ] = 120001
        over_deadline_record, over_deadline_artifacts = attach_signed_evidence(
            valid_record,
            [1] * 30,
            variant_observations=over_deadline_observations,
        )
        self.assertFalse(
            validate(
                schema,
                over_deadline_record,
                evidence_artifacts=over_deadline_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        mixed_route_observations = copy.deepcopy(valid_observations)
        mixed_route_observations[-1]["outage_route"] = "sealed_relay"
        mixed_route_record, mixed_route_artifacts = attach_signed_evidence(
            valid_record,
            [1] * 30,
            variant_observations=mixed_route_observations,
        )
        self.assertFalse(
            validate(
                schema,
                mixed_route_record,
                evidence_artifacts=mixed_route_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        wrong_route = copy.deepcopy(valid_record)
        wrong_route["selected_route"] = "p2p_direct"
        wrong_route, wrong_route_artifacts = attach_signed_evidence(
            wrong_route,
            [1] * 30,
            variant_observations=valid_observations,
        )
        self.assertFalse(
            validate(
                schema,
                wrong_route,
                evidence_artifacts=wrong_route_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        wrong_outcome = copy.deepcopy(valid_record)
        wrong_outcome["variant_outcome"] = (
            "supported_route_success_and_direct_p2p_result_reported"
        )
        wrong_outcome, wrong_outcome_artifacts = attach_signed_evidence(
            wrong_outcome,
            [1] * 30,
            variant_observations=valid_observations,
        )
        self.assertFalse(
            validate(
                schema,
                wrong_outcome,
                evidence_artifacts=wrong_outcome_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        turn_recovery = copy.deepcopy(valid_record)
        turn_recovery.update(
            {
                "network_cell": "forced_turn_relay",
                "network_variant": "required_turn_outage",
                "selected_route": "turn_relay",
                "direct_outcome": "not_attempted",
                "fallback_outcome": "success",
                "variant_outcome": (
                    "sealed_fallback_or_fail_closed_then_authenticated_recovery"
                ),
            }
        )
        turn_observations = make_variant_observations(
            30,
            affected_scope="turn",
            direct_outcome="not_attempted",
            fallback_outcome="success",
            outage_connection_outcome="rejected",
            outage_authentication_outcome="not_established",
            outage_route="none",
            recovery_route="turn_relay",
            requires_recovery=True,
        )
        turn_declaration, turn_declaration_artifacts = attach_signed_evidence(
            turn_recovery,
            [1] * 30,
        )
        self.assertFalse(
            validate(
                schema,
                turn_declaration,
                evidence_artifacts=turn_declaration_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )
        turn_recovery, turn_artifacts = attach_signed_evidence(
            turn_recovery,
            [1] * 30,
            variant_observations=turn_observations,
        )
        self.assertTrue(
            validate(
                schema,
                turn_recovery,
                evidence_artifacts=turn_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        same_failed_route = copy.deepcopy(turn_observations)
        for observation in same_failed_route:
            observation["outage_route"] = "turn_relay"
        bad_turn, bad_turn_artifacts = attach_signed_evidence(
            turn_recovery,
            [1] * 30,
            variant_observations=same_failed_route,
        )
        self.assertFalse(
            validate(
                schema,
                bad_turn,
                evidence_artifacts=bad_turn_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        sealed_declaration = copy.deepcopy(turn_recovery)
        sealed_declaration.update(
            {
                "network_cell": "forced_sealed_emergency_relay",
                "network_variant": "required_sealed_relay_outage",
                "selected_route": "sealed_relay",
                "variant_outcome": (
                    "fail_closed_without_weaker_route_then_authenticated_recovery"
                ),
            }
        )
        sealed_declaration, sealed_declaration_artifacts = attach_signed_evidence(
            sealed_declaration,
            [1] * 30,
        )
        self.assertFalse(
            validate(
                schema,
                sealed_declaration,
                evidence_artifacts=sealed_declaration_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        missing_region = copy.deepcopy(turn_recovery)
        missing_region.update(
            {
                "network_cell": "forced_turn_relay",
                "network_variant": "regional_relay_outage",
                "variant_outcome": (
                    "single_region_v1_fails_closed_then_recovers_after_service_restore"
                ),
            }
        )
        missing_region_observations = make_variant_observations(
            30,
            affected_scope="region",
            direct_outcome="not_attempted",
            fallback_outcome="success",
            outage_connection_outcome="rejected",
            outage_authentication_outcome="not_established",
            outage_route="none",
            recovery_route="turn_relay",
            requires_recovery=True,
        )
        missing_region, missing_region_artifacts = attach_signed_evidence(
            missing_region,
            [1] * 30,
            variant_observations=missing_region_observations,
        )
        self.assertFalse(
            validate(
                schema,
                missing_region,
                evidence_artifacts=missing_region_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

        regional_record = copy.deepcopy(missing_region)
        regional_record["region"] = "kr-seoul"
        regional_observations = make_variant_observations(
            30,
            affected_scope="region",
            affected_region="kr-seoul",
            direct_outcome="not_attempted",
            fallback_outcome="success",
            outage_connection_outcome="rejected",
            outage_authentication_outcome="not_established",
            outage_route="none",
            recovery_route="turn_relay",
            requires_recovery=True,
        )
        regional_record, regional_artifacts = attach_signed_evidence(
            regional_record,
            [1] * 30,
            variant_observations=regional_observations,
        )
        self.assertTrue(
            validate(
                schema,
                regional_record,
                registries={
                    "approved_release_region_registry": {"kr-seoul", "us-east"}
                },
                evidence_artifacts=regional_artifacts,
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )
        regional_failures = check_v1_g0_decision.release_campaign_failures(
            schema,
            self.document,
            [regional_record],
            registries={
                "approved_release_region_registry": {"kr-seoul", "us-east"}
            },
            evidence_artifacts=regional_artifacts,
            approved_evidence_signers=TEST_SIGNERS,
            evidence_signature_verifier=verify_test_signature,
        )
        self.assertTrue(any("region=us-east" in item for item in regional_failures))

        failures = check_v1_g0_decision.release_campaign_failures(
            schema,
            self.document,
            [valid_record],
            registries={"approved_release_region_registry": {"kr-seoul"}},
            evidence_artifacts=valid_artifacts,
            approved_evidence_signers=TEST_SIGNERS,
            evidence_signature_verifier=verify_test_signature,
        )
        self.assertTrue(any("network_variant=none" in failure for failure in failures))

    def test_release_evidence_is_bounded_and_has_fixed_canonicalization(self) -> None:
        schema = self.assurance["observabilitySchema"]
        envelope_schema = schema["evidenceEnvelopeSchema"]
        vector = envelope_schema["canonicalizationTestVector"]
        vector_value = json.loads(
            vector["inputJson"],
            object_pairs_hook=check_v1_g0_decision.reject_duplicate_keys,
            parse_constant=check_v1_g0_decision.reject_non_finite,
            parse_int=check_v1_g0_decision.parse_release_evidence_integer,
            parse_float=check_v1_g0_decision.parse_release_evidence_decimal,
        )
        canonical = check_v1_g0_decision.canonical_release_evidence_json(
            vector_value
        )
        self.assertEqual(canonical.decode("utf-8"), vector["canonicalUtf8"])
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), vector["sha256"])
        precision_value = json.loads(
            '{"n":1234567890.123456}',
            parse_int=check_v1_g0_decision.parse_release_evidence_integer,
            parse_float=check_v1_g0_decision.parse_release_evidence_decimal,
        )
        self.assertEqual(
            check_v1_g0_decision.canonical_release_evidence_json(precision_value),
            b'{"n":1234567890.123456}',
        )
        with localcontext() as context:
            context.prec = 6
            context.traps[Inexact] = True
            exact_a = check_v1_g0_decision.canonical_release_evidence_json(
                {"n": Decimal("1234567890123456.123456")}
            )
            exact_b = check_v1_g0_decision.canonical_release_evidence_json(
                {"n": Decimal("1234567890123456.123455")}
            )
        self.assertEqual(exact_a, b'{"n":1234567890123456.123456}')
        self.assertEqual(exact_b, b'{"n":1234567890123456.123455}')
        self.assertNotEqual(exact_a, exact_b)

        unsigned_record = {
            "record_kind": "security_hard_stop_result",
            "campaign_id": "rc-20260720-b00b1e55",
            "app_build": 1,
            "app_version": "1.0.0",
            "platform": "service",
            "device_class": "service_control_plane",
            "measurement_contract": "security_hard_stops",
            "metric_name": "unauthorized_release_artifact_acceptance",
            "metric_value": 0,
            "threshold_operator": "equal",
            "threshold_value": 0,
            "sample_count": 1,
            "gate_result": "passed",
        }
        record, artifacts = attach_signed_evidence(unsigned_record, [0])
        verifier_called = False

        def unexpected_verifier(
            _algorithm: str,
            _public_key: object,
            _payload: bytes,
            _signature: str,
        ) -> bool:
            nonlocal verifier_called
            verifier_called = True
            return True

        oversized = b" " * (check_v1_g0_decision.MAX_RELEASE_EVIDENCE_BYTES + 1)
        oversized_digest = hashlib.sha256(oversized).hexdigest()
        oversized_record = copy.deepcopy(record)
        oversized_record["evidence_sha256"] = oversized_digest
        oversized_record["evidence_ref"] = f"sha256:{oversized_digest}"
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                oversized_record,
                evidence_artifacts={oversized_record["evidence_ref"]: oversized},
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=unexpected_verifier,
            )
        )
        self.assertFalse(verifier_called)

        envelope = json.loads(artifacts[record["evidence_ref"]].decode("utf-8"))
        canonical_signature = envelope["signature"]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        terminal_index = alphabet.index(canonical_signature[-1])
        self.assertEqual(terminal_index % 16, 0)
        for alias_index in range(terminal_index, terminal_index + 16):
            candidate = canonical_signature[:-1] + alphabet[alias_index]
            self.assertEqual(
                check_v1_g0_decision.canonical_ed25519_signature_is_valid(candidate),
                alias_index == terminal_index,
            )
        self.assertFalse(
            check_v1_g0_decision.canonical_ed25519_signature_is_valid(
                canonical_signature[:-1]
            )
        )
        self.assertFalse(
            check_v1_g0_decision.canonical_ed25519_signature_is_valid(
                canonical_signature + "A"
            )
        )

        envelope["signature"] = canonical_signature[:-1] + alphabet[terminal_index + 1]
        aliased_evidence = check_v1_g0_decision.canonical_release_evidence_json(envelope)
        aliased_digest = hashlib.sha256(aliased_evidence).hexdigest()
        aliased_record = copy.deepcopy(record)
        aliased_record["evidence_sha256"] = aliased_digest
        aliased_record["evidence_ref"] = f"sha256:{aliased_digest}"
        verifier_called = False
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                aliased_record,
                evidence_artifacts={aliased_record["evidence_ref"]: aliased_evidence},
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=unexpected_verifier,
            )
        )
        self.assertFalse(verifier_called)

        signer_envelope = json.loads(artifacts[record["evidence_ref"]].decode("utf-8"))
        signer_envelope["signer_id"] = "prod-key-1"
        signer_evidence = check_v1_g0_decision.canonical_release_evidence_json(
            signer_envelope
        )
        signer_digest = hashlib.sha256(signer_evidence).hexdigest()
        signer_record = copy.deepcopy(record)
        signer_record["evidence_sha256"] = signer_digest
        signer_record["evidence_ref"] = f"sha256:{signer_digest}"
        verifier_called = False
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                signer_record,
                evidence_artifacts={signer_record["evidence_ref"]: signer_evidence},
                approved_evidence_signers={"prod-key-1": TEST_PUBLIC_KEY},
                evidence_signature_verifier=unexpected_verifier,
            )
        )
        self.assertFalse(verifier_called)

        exponent_evidence = artifacts[record["evidence_ref"]].replace(
            b'"samples":[0]',
            b'"samples":[0e0]',
        )
        exponent_digest = hashlib.sha256(exponent_evidence).hexdigest()
        exponent_record = copy.deepcopy(record)
        exponent_record["evidence_sha256"] = exponent_digest
        exponent_record["evidence_ref"] = f"sha256:{exponent_digest}"
        self.assertFalse(
            check_v1_g0_decision.release_record_is_valid(
                schema,
                exponent_record,
                evidence_artifacts={exponent_record["evidence_ref"]: exponent_evidence},
                approved_evidence_signers=TEST_SIGNERS,
                evidence_signature_verifier=verify_test_signature,
            )
        )

    def test_release_campaign_rejects_missing_metric_and_matrix_coverage(self) -> None:
        schema = self.assurance["observabilitySchema"]
        unsigned_record = {
            "record_kind": "network_measurement_result",
            "campaign_id": "rc-20260720-feedface",
            "app_build": 1,
            "app_version": "1.0.0",
            "platform": "service",
            "device_class": "service_control_plane",
            "measurement_contract": "network_reliability_and_latency",
            "metric_name": "minimum_completed_network_sessions",
            "metric_value": 1200,
            "threshold_operator": "minimum",
            "threshold_value": 1200,
            "sample_count": 1200,
            "gate_result": "passed",
        }
        record, artifacts = attach_signed_evidence(unsigned_record, [1] * 1200)
        failures = check_v1_g0_decision.release_campaign_failures(
            schema,
            self.document,
            [record],
            registries={"approved_release_region_registry": {"kr-seoul"}},
            evidence_artifacts=artifacts,
            approved_evidence_signers=TEST_SIGNERS,
            evidence_signature_verifier=verify_test_signature,
        )
        self.assertTrue(any("missing metric" in failure for failure in failures))
        self.assertTrue(any("missing route class" in failure for failure in failures))

    def test_assurance_incident_pair_recovery_rotations_are_mandatory(self) -> None:
        assurance = self.mutated_assurance()
        assurance["incidentRunbook"][0]["credentialOrStateRotation"].remove(
            "fresh_endpoint_traffic_secret"
        )
        assurance["incidentRunbook"][-1]["credentialOrStateRotation"].remove(
            "rotated_route_token_seed"
        )
        failures = self.assurance_failures(assurance)
        self.assertGreaterEqual(
            sum("mandatory pair-recovery secret rotation" in item for item in failures),
            2,
        )

    def test_assurance_all_security_hard_stops_are_required(self) -> None:
        assurance = self.mutated_assurance()
        del assurance["rollbackRunbook"]["hardStops"]["routeAuthorizationBypasses"]
        self.assertTrue(any("rollbackRunbook.hardStops" in item for item in self.assurance_failures(assurance)))

    def test_assurance_check_cannot_pass_without_immutable_evidence(self) -> None:
        assurance = self.mutated_assurance()
        assurance["releaseChecklist"]["g0Exit"][0]["status"] = "passed"
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("passed without immutable evidence" in item for item in failures))

    def test_assurance_receipts_cannot_be_invented_or_misbound(self) -> None:
        assurance = self.mutated_assurance()
        approval = assurance["approvals"][0]
        approval["ownerIdentityRef"] = "invented-owner"
        approval["status"] = "accepted"
        approval["acceptedPublicationCommit"] = "a" * 40
        approval["acceptedBlockerIds"] = [
            "roadmap_and_g0_checkpoint_publication"
        ]
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("ownerIdentityRef" in item for item in failures))
        self.assertTrue(any("approvals[0].status" in item for item in failures))
        self.assertTrue(
            any("acceptedPublicationCommit" in item for item in failures)
        )
        self.assertTrue(any("acceptedBlockerIds" in item for item in failures))

    def test_assurance_cannot_open_socket_or_g1_authority(self) -> None:
        assurance = self.mutated_assurance()
        assurance["authority"]["g1aNoNetworkImplementationAllowed"] = True
        assurance["authority"]["socketCreationAllowed"] = True
        failures = self.assurance_failures(assurance)
        self.assertTrue(any("g1aNoNetworkImplementationAllowed" in item for item in failures))
        self.assertTrue(any("socketCreationAllowed" in item for item in failures))

    def test_assurance_contradiction_cannot_be_hidden(self) -> None:
        assurance = self.mutated_assurance()
        assurance["acceptance"]["contradictions"] = ["hidden_conflict"]
        self.assertTrue(any("acceptance.contradictions" in item for item in self.assurance_failures(assurance)))

    def test_assurance_markdown_must_keep_g1a_boundary(self) -> None:
        markdown = self.assurance_markdown.replace("G1a remains closed", "G1a may begin")
        self.assertTrue(any("G1a remains closed" in item for item in self.assurance_failures(markdown=markdown)))


if __name__ == "__main__":
    unittest.main()
