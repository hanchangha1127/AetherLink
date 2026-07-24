#!/usr/bin/env python3
"""Twenty adversarial mutation tests for the G2 Pion rung-two authority."""

from __future__ import annotations

import base64
import copy
import importlib.util
from pathlib import Path
import re
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung2_acquisition_authority.py"
SPEC = importlib.util.spec_from_file_location("g2_pion_rung2_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load G2 Pion rung-two checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class G2PionRungTwoMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provenance = CHECKER.load_json(CHECKER.PROVENANCE_PATH)
        cls.decision = CHECKER.load_json(CHECKER.DECISION_PATH)
        cls.progress = CHECKER.load_json(CHECKER.PROGRESS_PATH)
        cls.manifest = CHECKER.load_json(CHECKER.EVIDENCE_MANIFEST_PATH)
        cls.markdown = CHECKER.DECISION_MARKDOWN_PATH.read_text(encoding="utf-8")

    def assert_provenance_rejected(self, mutation, *, semantic: bool = True) -> None:
        candidate = copy.deepcopy(self.provenance)
        mutation(candidate)
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.validate_provenance_document(candidate, require_semantic=semantic)

    def assert_decision_rejected(self, mutation, *, semantic: bool = True) -> None:
        candidate = copy.deepcopy(self.decision)
        mutation(candidate)
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.validate_decision_document(candidate, require_semantic=semantic)

    def assert_progress_rejected(self, mutation, *, semantic: bool = True) -> None:
        candidate = copy.deepcopy(self.progress)
        mutation(candidate)
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.validate_progress_document(candidate, require_semantic=semantic)

    def assert_manifest_rejected(self, mutation, *, semantic: bool = True) -> None:
        candidate = copy.deepcopy(self.manifest)
        mutation(candidate)
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.validate_evidence_manifest(
                candidate,
                require_semantic=semantic,
                verify_artifact_files=False,
            )

    def test_01_duplicate_root_and_nested_json_names_fail(self) -> None:
        raw = CHECKER.DECISION_PATH.read_text(encoding="utf-8")
        candidates = (
            raw.replace(
                '  "status": "rung2_source_identity_decision_recorded_acquisition_not_executed",',
                '  "status": "executed",\n  "status": "rung2_source_identity_decision_recorded_acquisition_not_executed",',
                1,
            ),
            raw.replace(
                '    "maximumRequestCount": 1,',
                '    "maximumRequestCount": 2,\n    "maximumRequestCount": 1,',
                1,
            ),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate[:80]):
                with self.assertRaises(CHECKER.RungTwoValidationError):
                    CHECKER.parse_json(candidate)

    def test_02_non_finite_json_and_direct_values_fail(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                with self.assertRaises(CHECKER.RungTwoValidationError):
                    CHECKER.parse_json('{"value": ' + constant + "}")
        self.assert_decision_rejected(
            lambda value: value["acquisitionPermit"].update(
                {"maximumResponseBytes": float("nan")}
            )
        )

    def test_03_bool_integer_confusion_fails(self) -> None:
        self.assert_decision_rejected(
            lambda value: value["acquisitionPermit"].update({"maximumRequestCount": True}),
            semantic=False,
        )
        self.assert_progress_rejected(
            lambda value: value["permitState"].update({"requestCount": False}),
            semantic=False,
        )
        self.assert_provenance_rejected(
            lambda value: value["checksumDatabaseObservation"].update(
                {"recordNumber": True}
            ),
            semantic=False,
        )

    def test_04_closed_schema_and_identity_drift_fail(self) -> None:
        for mutation in (
            lambda value: value.pop("rollback"),
            lambda value: value.update({"ownerAuthorization": {}}),
            lambda value: value.update({"schemaVersion": "1.1"}),
            lambda value: value["acquisitionPermit"].update({"unknownPermit": False}),
        ):
            self.assert_decision_rejected(mutation, semantic=False)

    def test_05_parent_lineage_hash_and_state_drift_fail(self) -> None:
        for mutation in (
            lambda value: value["parentRungOne"].update({"profileSha256": "0" * 64}),
            lambda value: value["parentRungOne"].update({"profileSemanticSha256": "0" * 64}),
            lambda value: value["parentRungOne"].update({"evidenceCollectionSha256": "0" * 64}),
            lambda value: value["parentRungOne"].update({"requiredStatus": "candidate_selected"}),
            lambda value: value["parentRungOne"].update({"requiredNextAction": "compile"}),
        ):
            self.assert_decision_rejected(mutation, semantic=False)

    def test_06_source_identity_and_patch_series_drift_fail(self) -> None:
        for key, replacement in (
            ("repositoryUrl", "https://example.invalid/pion/ice"),
            ("modulePath", "github.com/pion/ice/v5"),
            ("version", "v4.3.1"),
            ("tagType", "annotated"),
            ("commit", "0" * 40),
            ("tree", "f" * 40),
            ("patchSeriesImplementationStatus", "implemented"),
        ):
            with self.subTest(key=key):
                self.assert_decision_rejected(
                    lambda value, key=key, replacement=replacement: value["sourceIdentity"].update(
                        {key: replacement}
                    ),
                    semantic=False,
                )

    def test_07_url_host_path_and_encoding_bypasses_fail(self) -> None:
        variants = (
            CHECKER.SOURCE_URL.replace("https://", "http://"),
            CHECKER.SOURCE_URL.replace("proxy.golang.org", "evil.invalid"),
            CHECKER.SOURCE_URL.replace("proxy.golang.org", "user@proxy.golang.org"),
            CHECKER.SOURCE_URL.replace("proxy.golang.org", "proxy.golang.org:444"),
            CHECKER.SOURCE_URL + "?mirror=1",
            CHECKER.SOURCE_URL + "#fragment",
            CHECKER.SOURCE_URL.replace("/@v/", "/%40v/"),
        )
        for candidate in variants:
            with self.subTest(candidate=candidate):
                self.assert_decision_rejected(
                    lambda value, candidate=candidate: value["acquisitionPermit"].update(
                        {"url": candidate}
                    ),
                    semantic=False,
                )

    def test_08_archive_raw_hash_length_and_output_path_drift_fail(self) -> None:
        mutations = (
            lambda value: value["requiredPostAcquisitionChecks"].update({"rawSha256": "0" * 64}),
            lambda value: value["acquisitionPermit"].update({"expectedContentLengthBytes": 293024}),
            lambda value: value["acquisitionPermit"].update({"maximumResponseBytes": 20_000_000}),
            lambda value: value["acquisitionPermit"].update({"outputPath": "../pion.zip"}),
            lambda value: value["acquisitionPermit"].update({"outputPath": "/tmp/pion.zip"}),
            lambda value: value["acquisitionPermit"].update({"outputPath": "build\\pion.zip"}),
        )
        for mutation in mutations:
            self.assert_decision_rejected(mutation, semantic=False)

    def test_09_module_and_go_mod_h1_drift_fail(self) -> None:
        for key in ("moduleH1", "goModH1"):
            self.assert_provenance_rejected(
                lambda value, key=key: value["goChecksumObservation"].update(
                    {key: "h1:" + "A" * 44}
                ),
                semantic=False,
            )
            self.assert_decision_rejected(
                lambda value, key=key: value["requiredPostAcquisitionChecks"].update(
                    {key: "h1:" + "A" * 44}
                ),
                semantic=False,
            )
        self.assert_decision_rejected(
            lambda value: value["requiredPostAcquisitionChecks"].update(
                {"goModH1MatchRequired": False}
            ),
            semantic=False,
        )

    def test_10_github_signature_scope_cannot_be_promoted(self) -> None:
        mutations = (
            lambda value: value["githubCommitSignatureObservation"].update({"status": "locally_verified"}),
            lambda value: value["githubCommitSignatureObservation"].update({"signedObject": "signed_tag"}),
            lambda value: value["githubCommitSignatureObservation"].update({"keyFingerprint": "0" * 40}),
            lambda value: value["githubCommitSignatureObservation"].update({"proxyZipAuthenticatedByThisObservation": True}),
            lambda value: value["githubCommitSignatureObservation"].update({"localReverificationStatus": "verified"}),
        )
        for mutation in mutations:
            self.assert_provenance_rejected(mutation, semantic=False)

    def test_11_sumdb_key_and_signed_tree_mutations_fail_crypto(self) -> None:
        key_match = re.fullmatch(r"([^+]+)\+([0-9a-f]{8})\+(.+)", CHECKER.SUMDB_VERIFIER_KEY)
        self.assertIsNotNone(key_match)
        assert key_match is not None
        key_payload = base64.b64decode(key_match.group(3), validate=True)
        signature = base64.b64decode(CHECKER.SUMDB_SIGNATURE_BASE64, validate=True)[4:]
        CHECKER.verify_ed25519(key_payload[1:], CHECKER.expected_signed_tree_bytes(), signature)
        changed_signature = signature[:-1] + bytes([signature[-1] ^ 1])
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.verify_ed25519(
                key_payload[1:], CHECKER.expected_signed_tree_bytes(), changed_signature
            )
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.verify_ed25519(
                bytes([key_payload[1] ^ 1]) + key_payload[2:],
                CHECKER.expected_signed_tree_bytes(),
                signature,
            )
        noncanonical_s = signature[:32] + CHECKER.ED25519_L.to_bytes(32, "little")
        identity_point = b"\x01" + b"\x00" * 31
        negative_zero = bytearray(identity_point)
        negative_zero[-1] |= 0x80
        noncanonical_y = CHECKER.ED25519_Q.to_bytes(32, "little")
        for public_key, candidate_signature in (
            (key_payload[1:], noncanonical_s),
            (key_payload[1:], identity_point + signature[32:]),
            (key_payload[1:], bytes(negative_zero) + signature[32:]),
            (identity_point, signature),
            (noncanonical_y, signature),
        ):
            with self.subTest(public_key=public_key[:2], signature=candidate_signature[:2]):
                with self.assertRaises(CHECKER.RungTwoValidationError):
                    CHECKER.verify_ed25519(
                        public_key,
                        CHECKER.expected_signed_tree_bytes(),
                        candidate_signature,
                    )

    def test_12_record_hash_and_inclusion_proof_mutations_fail(self) -> None:
        checksum = self.provenance["checksumDatabaseObservation"]
        proof = [
            base64.b64decode(value, validate=True)
            for value in checksum["inclusionProof"]["proofHashesBase64"]
        ]
        root = base64.b64decode(CHECKER.SUMDB_ROOT_HASH_BASE64, validate=True)
        CHECKER.verify_rfc6962_inclusion(
            CHECKER.expected_sumdb_record_bytes(),
            CHECKER.SUMDB_RECORD_NUMBER,
            CHECKER.SUMDB_TREE_SIZE,
            proof,
            root,
        )
        mutated = list(proof)
        mutated[7] = bytes([mutated[7][0] ^ 1]) + mutated[7][1:]
        for candidate in (mutated, proof[:-1], proof + [proof[-1]], list(reversed(proof))):
            with self.subTest(length=len(candidate)):
                with self.assertRaises(CHECKER.RungTwoValidationError):
                    CHECKER.verify_rfc6962_inclusion(
                        CHECKER.expected_sumdb_record_bytes(),
                        CHECKER.SUMDB_RECORD_NUMBER,
                        CHECKER.SUMDB_TREE_SIZE,
                        candidate,
                        root,
                    )
        for leaf_index, tree_size in (
            (CHECKER.SUMDB_RECORD_NUMBER - 1, CHECKER.SUMDB_TREE_SIZE),
            (CHECKER.SUMDB_RECORD_NUMBER + 1, CHECKER.SUMDB_TREE_SIZE),
            (-1, CHECKER.SUMDB_TREE_SIZE),
            (CHECKER.SUMDB_TREE_SIZE, CHECKER.SUMDB_TREE_SIZE),
        ):
            with self.subTest(leaf_index=leaf_index, tree_size=tree_size):
                with self.assertRaises(CHECKER.RungTwoValidationError):
                    CHECKER.verify_rfc6962_inclusion(
                        CHECKER.expected_sumdb_record_bytes(),
                        leaf_index,
                        tree_size,
                        proof,
                        root,
                    )

    def test_13_cross_file_and_manifest_integrity_drift_fail(self) -> None:
        self.assert_decision_rejected(
            lambda value: value["provenanceObservation"].update({"sha256": "0" * 64}),
            semantic=False,
        )
        self.assert_progress_rejected(
            lambda value: value["decisionBinding"].update({"sha256": "0" * 64}),
            semantic=False,
        )
        for mutation in (
            lambda value: value["artifacts"].reverse(),
            lambda value: value["artifacts"][0].update({"path": value["artifacts"][1]["path"]}),
            lambda value: value["artifacts"][0].update({"sha256": "0" * 64}),
            lambda value: value.update({"collectionSha256": "0" * 64}),
        ):
            self.assert_manifest_rejected(mutation, semantic=False)

    def test_14_decision_and_progress_false_completion_claims_fail(self) -> None:
        for mutation in (
            lambda value: value.update({"status": "acquisition_complete"}),
            lambda value: value.update({"result": "source_verified"}),
            lambda value: value.update({"nextAction": "compile_source"}),
            lambda value: value["executionBoundary"].update({"acquisitionExecuted": True}),
            lambda value: value["executionBoundary"].update({"permitConsumed": True}),
        ):
            self.assert_decision_rejected(mutation, semantic=False)
        for mutation in (
            lambda value: value.update({"status": "completed"}),
            lambda value: value.update({"result": "success"}),
            lambda value: value["artifactObservation"].update({"sourceAcquired": True}),
            lambda value: value["verificationObservation"].update({"allRequiredChecksPassed": True}),
        ):
            self.assert_progress_rejected(mutation, semantic=False)

    def test_15_one_use_permit_claim_and_request_count_drift_fail(self) -> None:
        for mutation in (
            lambda value: value["acquisitionPermit"].update({"maximumRequestCount": 2}),
            lambda value: value["acquisitionPermit"].update({"atomicPermitClaimRequired": False}),
            lambda value: value["acquisitionPermit"].update({"existingOutputOrClaimRule": "overwrite"}),
        ):
            self.assert_decision_rejected(mutation, semantic=False)
        for mutation in (
            lambda value: value["permitState"].update({"consumed": True}),
            lambda value: value["permitState"].update({"atomicClaimCreated": True}),
            lambda value: value["permitState"].update({"requestCount": 1}),
            lambda value: value["permitState"].update({"maximumRequestCount": 2}),
        ):
            self.assert_progress_rejected(mutation, semantic=False)

    def test_16_network_and_tool_permission_escalations_fail(self) -> None:
        fields = (
            "ambientProxyAllowed", "redirectsAllowed", "credentialsAllowed",
            "urlQueryAllowed", "urlFragmentAllowed", "packageManagerAllowed",
            "goCommandAllowed", "gitCommandAllowed", "shellAllowed",
            "dependencyFetchAllowed", "archiveExtractionAllowed", "sourceExecutionAllowed",
        )
        for field in fields:
            with self.subTest(field=field):
                self.assert_decision_rejected(
                    lambda value, field=field: value["acquisitionPermit"].update({field: True}),
                    semantic=False,
                )

    def test_17_tls_bounds_and_rollback_weakening_fail(self) -> None:
        for mutation in (
            lambda value: value["acquisitionPermit"].update({"tlsCertificateValidationRequired": False}),
            lambda value: value["acquisitionPermit"].update({"tlsHostnameValidationRequired": False}),
            lambda value: value["acquisitionPermit"].update({"totalDeadlineMilliseconds": 60000}),
            lambda value: value["rollback"].update({"automaticRetryAllowed": True}),
            lambda value: value["rollback"].update({"alternateMirrorAllowed": True}),
            lambda value: value["rollback"].update({"wrapperFallbackAllowed": True}),
            lambda value: value["rollback"].update({"newDecisionRequiredAfterFailure": False}),
        ):
            self.assert_decision_rejected(mutation, semantic=False)

    def test_18_execution_and_user_auth_boundary_escalations_fail(self) -> None:
        false_fields = (
            "acquisitionExecuted", "permitConsumed", "candidateSelected", "librarySelected",
            "dependencyInstallationAllowed", "compilerInvocationAllowed", "codeLoadingAllowed",
            "socketCreationAllowed", "runtimeNetworkIoAllowed", "deviceExecutionAllowed",
            "productionDeploymentAllowed", "gitOperationAllowed", "externalIdentityProofRequired",
            "userActionRequired", "repositoryOwnerAuthenticationRequired",
        )
        for field in false_fields:
            with self.subTest(field=field):
                self.assert_decision_rejected(
                    lambda value, field=field: value["executionBoundary"].update({field: True}),
                    semantic=False,
                )
        self.assert_decision_rejected(
            lambda value: value["executionBoundary"].update(
                {"productEndpointAuthenticationRequired": False}
            ),
            semantic=False,
        )
        for field in ("externalIdentityProofRequired", "userActionRequired"):
            self.assert_provenance_rejected(
                lambda value, field=field: value["executionBoundary"].update({field: True}),
                semantic=False,
            )
            self.assert_progress_rejected(
                lambda value, field=field: value["executionBoundary"].update({field: True}),
                semantic=False,
            )
            self.assert_manifest_rejected(
                lambda value, field=field: value.update({field: True}),
                semantic=False,
            )

    def test_19_zero_request_progress_state_must_remain_coherent(self) -> None:
        mutations = (
            lambda value: value["requestObservation"].update({"started": True}),
            lambda value: value["requestObservation"].update({"requestedUrl": CHECKER.SOURCE_URL}),
            lambda value: value["requestObservation"].update({"httpStatus": 200}),
            lambda value: value["verificationObservation"].update({"rawSha256": CHECKER.RAW_ARCHIVE_SHA256}),
            lambda value: value["verificationObservation"].update({"goModH1Matches": True}),
            lambda value: value["artifactObservation"].update({"outputFileExists": True}),
            lambda value: value["artifactObservation"].update({"outputPath": CHECKER.OUTPUT_PATH}),
            lambda value: value["artifactObservation"].update({"quarantined": True}),
        )
        for mutation in mutations:
            self.assert_progress_rejected(mutation, semantic=False)

    def test_20_baseline_passes_and_fabricated_markdown_claims_fail(self) -> None:
        CHECKER.validate_provenance_document(copy.deepcopy(self.provenance))
        CHECKER.validate_decision_document(copy.deepcopy(self.decision))
        CHECKER.validate_progress_document(copy.deepcopy(self.progress))
        CHECKER.validate_evidence_manifest(
            copy.deepcopy(self.manifest), verify_artifact_files=False
        )
        CHECKER.validate_canonical_document_supersession()
        CHECKER.validate_canonical_document_supersession_v2()
        CHECKER.validate_markdown_text(self.markdown)
        completed = mock.Mock(returncode=0, stdout=b"historical-object", stderr=b"")
        with mock.patch.object(CHECKER.subprocess, "run", return_value=completed) as run:
            self.assertEqual(
                CHECKER.read_exact_git_object(["cat-file", "blob", "deadbeef"], 32),
                b"historical-object",
            )
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")
        historical_action = "prepare_versioned_rung3_offline_source_review_decision"
        historical_checkpoint = "at_that_checkpoint"
        canonical_texts = {
            path: f"{historical_checkpoint} {historical_action}\n"
            for path in CHECKER.CURRENT_CANONICAL_DOCUMENT_PATHS
        }
        canonical_texts["docs/roadmap.md"] = (
            "### G2 - Select A New P2P/NAT Stack Under Fresh Authority\n\n"
            f"{historical_checkpoint} "
            "prepare_versioned_rung2_source_identity_and_acquisition_decision "
            "was the historical preparation action.\n\n"
            f"{historical_action}\n\n"
            "### Immediate Execution Queue\n\n"
            f"{historical_checkpoint} {historical_action}\n"
        )
        CHECKER.validate_current_canonical_document_semantics(canonical_texts)
        stale_texts = copy.deepcopy(canonical_texts)
        stale_texts["docs/progress.md"] += (
            "\nPreparation of a separate rung-two\ntechnical decision\n"
        )
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.validate_current_canonical_document_semantics(stale_texts)
        unscoped_texts = copy.deepcopy(canonical_texts)
        unscoped_texts["docs/roadmap.md"] = unscoped_texts["docs/roadmap.md"].replace(
            f"{historical_checkpoint} "
            "prepare_versioned_rung2_source_identity_and_acquisition_decision",
            "prepare_versioned_rung2_source_identity_and_acquisition_decision",
            1,
        )
        with self.assertRaises(CHECKER.RungTwoValidationError):
            CHECKER.validate_current_canonical_document_semantics(unscoped_texts)
        for claim in (
            "Source acquired successfully.",
            "All required checks passed.",
            "Candidate selected for implementation.",
            "Globally consistent checksum database.",
            "Freshness verified.",
            "GitHub commit cryptographically bound to the proxy ZIP.",
        ):
            with self.subTest(claim=claim):
                with self.assertRaises(CHECKER.RungTwoValidationError):
                    CHECKER.validate_markdown_text(self.markdown + "\n" + claim)


if __name__ == "__main__":
    unittest.main(verbosity=2)
