#!/usr/bin/env python3
"""Mutation tests for the non-authorizing G0 owner trust bootstrap v2."""

from __future__ import annotations

import builtins
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from script import check_v1_g0_owner_trust_bootstrap as bootstrap_v1
from script import check_v1_g0_owner_trust_bootstrap_v2 as bootstrap_v2
from script import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]


class V1G0OwnerTrustBootstrapV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_raw = (ROOT / bootstrap_v2.PROFILE_PATH).read_bytes()
        cls.profile = json.loads(cls.profile_raw)
        cls.predecessor_raw = (ROOT / bootstrap_v1.PROFILE_PATH).read_bytes()
        cls.lineage = tuple((ROOT / path).read_bytes() for path in receipt.LINEAGE_PATHS)
        cls.payload_fixture = cls.make_payload_fixture()

    @staticmethod
    def encoded(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
    def payload_encoded(value: object) -> bytes:
        return bootstrap_v2._canonical_payload_bytes(value)

    @staticmethod
    def ssh_string(value: bytes) -> bytes:
        return len(value).to_bytes(4, "big") + value

    @classmethod
    def sshsig_payload(
        cls,
        public_key_wire: bytes,
        signature: bytes,
        *,
        magic: bytes = b"SSHSIG",
        version: int = 1,
        namespace: bytes = b"aetherlink-owner-bootstrap-v1",
        reserved: bytes = b"",
        hash_algorithm: bytes = b"sha512",
        inner_algorithm: bytes = b"ssh-ed25519",
    ) -> bytes:
        inner = cls.ssh_string(inner_algorithm) + cls.ssh_string(signature)
        return (
            magic
            + version.to_bytes(4, "big")
            + cls.ssh_string(public_key_wire)
            + cls.ssh_string(namespace)
            + cls.ssh_string(reserved)
            + cls.ssh_string(hash_algorithm)
            + cls.ssh_string(inner)
        )

    @staticmethod
    def armor_sshsig(payload: bytes) -> bytes:
        encoded = base64.b64encode(payload)
        lines = [encoded[offset : offset + 70] for offset in range(0, len(encoded), 70)]
        return (
            b"-----BEGIN SSH SIGNATURE-----\n"
            + b"\n".join(lines)
            + b"\n-----END SSH SIGNATURE-----\n"
        )

    @classmethod
    def sshsig_blob(
        cls,
        public_key_wire: bytes,
        signature: bytes,
        **overrides: object,
    ) -> bytes:
        return cls.armor_sshsig(
            cls.sshsig_payload(public_key_wire, signature, **overrides)
        )

    @classmethod
    def make_payload_fixture(cls) -> dict[str, object]:
        roles = bootstrap_v2._EXPECTED_ROLE_ORDER
        public_key = b"\x01" * 32
        wire = (
            (11).to_bytes(4, "big")
            + b"ssh-ed25519"
            + (32).to_bytes(4, "big")
            + public_key
        )
        wire_b64 = base64.b64encode(wire).decode("ascii")
        public_key_sha = hashlib.sha256(wire).hexdigest()
        fingerprint = "SHA256:" + base64.b64encode(
            bytes.fromhex(public_key_sha)
        ).decode("ascii").rstrip("=")
        key_epoch = "1"
        credential_ref = f"g0-owner-credential-{public_key_sha}-e{key_epoch}-v1"
        status_ref = (
            "g0-owner-credential-status-"
            + hashlib.sha256(credential_ref.encode("utf-8")).hexdigest()
            + "-v1"
        )
        registry_id = "g0-owner-registry-v1"
        registry_revision = "1"
        mappings = []
        for role in roles:
            candidate = bootstrap_v2._expected_role_mapping(role)
            mappings.append(
                {
                    "ownerBindingRef": candidate["ownerBindingRefCandidate"],
                    "role": role,
                    "ownerIdentityRef": candidate["ownerIdentityRefCandidate"],
                    "principalRef": bootstrap_v2.EXPECTED_PRINCIPAL["principalRef"],
                    "credentialRef": credential_ref,
                    "identityRegistryRef": registry_id,
                    "identityRegistryRevision": registry_revision,
                    "validFrom": "2026-01-02T00:00:00Z",
                    "validUntil": "2026-12-30T00:00:00Z",
                    "revocationRef": status_ref,
                    "provenanceRef": "github-snapshot-243786110-v1",
                }
            )
        credential = {
            "credentialRef": credential_ref,
            "principalRef": bootstrap_v2.EXPECTED_PRINCIPAL["principalRef"],
            "keyEpoch": key_epoch,
            "keyAlgorithmRef": bootstrap_v2.EXPECTED_SIGNATURE_MECHANISM[
                "mechanismRef"
            ],
            "publicKeyEncodingRef": "openssh_ssh_ed25519_wire_blob_v1",
            "publicKeyWireBlobBase64": wire_b64,
            "publicKeyBlobSha256": public_key_sha,
            "openSshPublicKeyFingerprint": fingerprint,
            "keyUsage": bootstrap_v2.EXPECTED_SIGNATURE_MECHANISM["keyUsage"],
            "allowedRoles": list(roles),
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2027-01-01T00:00:00Z",
            "proofOfControlRef": "g0-owner-proof-of-control-v1",
            "proofOfControlEnvelopeSha256": "1" * 64,
            "proofOfControlVerifiedAt": "2026-01-01T01:00:00Z",
            "revocationRef": status_ref,
            "provenanceRef": "registry-root-attestation-v1",
        }
        registry = {
            "documentType": "aetherlink.v1-g0-owner-identity-registry-snapshot",
            "schemaVersion": 1,
            "registrySnapshotRef": "g0-owner-registry-snapshot-v1",
            "registryId": registry_id,
            "revision": registry_revision,
            "previousRegistrySnapshotSha256": None,
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2027-01-01T00:00:00Z",
            "principalMappings": mappings,
            "credentialRecords": [credential],
        }
        registry_raw = cls.payload_encoded(registry)
        registry_sha = hashlib.sha256(registry_raw).hexdigest()
        revocation = {
            "documentType": "aetherlink.v1-g0-owner-credential-status-snapshot",
            "schemaVersion": 1,
            "revocationSnapshotRef": "g0-owner-revocation-snapshot-v1",
            "registryId": registry_id,
            "registryRevision": registry_revision,
            "registrySnapshotSha256": registry_sha,
            "revision": "1",
            "previousRevocationSnapshotSha256": None,
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2027-01-01T00:00:00Z",
            "credentialStatuses": [
                {
                    "statusRef": status_ref,
                    "credentialRef": credential_ref,
                    "publicKeyBlobSha256": public_key_sha,
                    "keyEpoch": key_epoch,
                    "status": "active",
                    "effectiveAt": None,
                    "compromiseAt": None,
                    "reason": None,
                }
            ],
        }
        revocation_raw = cls.payload_encoded(revocation)
        revocation_sha = hashlib.sha256(revocation_raw).hexdigest()

        def root_statement(kind: str, snapshot_ref: str, digest: str, revision: str) -> dict[str, object]:
            return {
                "documentType": "aetherlink.v1-g0-owner-registry-root-signature-statement",
                "schemaVersion": 1,
                "domain": "aetherlink-owner-registry-root-v1",
                "snapshotKind": kind,
                "snapshotRef": snapshot_ref,
                "snapshotSha256": digest,
                "registryId": registry_id,
                "revision": revision,
                "rootTrustAnchorRef": None,
                "rootKeyRef": None,
                "rootAlgorithmRef": None,
                "rootPublicKeySha256": None,
                "signatureFormatRef": None,
            }

        registry_statement = root_statement(
            "registry", registry["registrySnapshotRef"], registry_sha, registry_revision
        )
        revocation_statement = root_statement(
            "revocation",
            revocation["revocationSnapshotRef"],
            revocation_sha,
            revocation["revision"],
        )
        target_sha = hashlib.sha256(b"target").hexdigest()
        bundle_id = "g0-owner-bundle-v1"
        issuer = "g0-independent-verifier-v1"
        audience = "aetherlink-g0-owner-approval"
        envelopes: list[dict[str, object]] = []
        envelope_blobs: list[bytes] = []
        signature_blobs: list[bytes] = []
        role_records: list[dict[str, object]] = []
        for index, (role, mapping) in enumerate(zip(roles, mappings)):
            candidate = bootstrap_v2._expected_role_mapping(role)
            nonce = base64.urlsafe_b64encode(
                hashlib.sha256(f"nonce:{role}".encode()).digest()
            ).decode("ascii").rstrip("=")
            envelope = {
                "documentType": "aetherlink.v1-g0-owner-role-auth-envelope",
                "schemaVersion": 1,
                "domain": "aetherlink-owner-bootstrap-v1",
                "principalRef": bootstrap_v2.EXPECTED_PRINCIPAL["principalRef"],
                "role": role,
                "ownerBindingRef": mapping["ownerBindingRef"],
                "ownerIdentityRef": mapping["ownerIdentityRef"],
                "credentialRef": credential_ref,
                "publicKeyBlobSha256": public_key_sha,
                "receiptRef": candidate["receiptRefCandidate"],
                "receiptRawSha256": hashlib.sha256(
                    f"raw:{role}".encode()
                ).hexdigest(),
                "receiptCanonicalSha256": hashlib.sha256(
                    f"canonical:{role}".encode()
                ).hexdigest(),
                "targetBindingSha256": target_sha,
                "identityRegistryRevision": registry_revision,
                "registrySnapshotSha256": registry_sha,
                "revocationSnapshotSha256": revocation_sha,
                "keyEpoch": key_epoch,
                "bundleId": bundle_id,
                "challengeIssuerRef": issuer,
                "challengeId": f"g0-owner-challenge-{index + 1}",
                "nonceBase64Url": nonce,
                "audience": audience,
                "issuedAt": "2026-02-01T00:00:00Z",
                "expiresAt": "2026-02-01T00:10:00Z",
            }
            envelope_raw = cls.payload_encoded(envelope)
            signature_raw = cls.sshsig_blob(
                wire,
                hashlib.sha512(f"synthetic-public-signature:{role}".encode()).digest(),
            )
            envelopes.append(envelope)
            envelope_blobs.append(envelope_raw)
            signature_blobs.append(signature_raw)
            role_records.append(
                {
                    "role": role,
                    "ownerBindingRef": mapping["ownerBindingRef"],
                    "ownerIdentityRef": mapping["ownerIdentityRef"],
                    "credentialRef": credential_ref,
                    "keyEpoch": key_epoch,
                    "publicKeyBlobSha256": public_key_sha,
                    "receiptRef": envelope["receiptRef"],
                    "receiptRawSha256": envelope["receiptRawSha256"],
                    "receiptCanonicalSha256": envelope["receiptCanonicalSha256"],
                    "challengeId": envelope["challengeId"],
                    "nonceBase64Url": nonce,
                    "envelopeSha256": hashlib.sha256(envelope_raw).hexdigest(),
                    "signatureSha256": hashlib.sha256(signature_raw).hexdigest(),
                }
            )
        manifest = {
            "documentType": "aetherlink.v1-g0-owner-role-auth-bundle-manifest",
            "schemaVersion": 1,
            "domain": "aetherlink-owner-bootstrap-v1",
            "bundleId": bundle_id,
            "principalRef": bootstrap_v2.EXPECTED_PRINCIPAL["principalRef"],
            "targetBindingSha256": target_sha,
            "identityRegistryRevision": registry_revision,
            "registrySnapshotSha256": registry_sha,
            "revocationSnapshotSha256": revocation_sha,
            "challengeIssuerRef": issuer,
            "audience": audience,
            "orderedRoleEntries": role_records,
        }
        sidecar = {
            "documentType": bootstrap_v2.EXPECTED_ADAPTER[
                "dormantSidecarDocumentType"
            ],
            "schemaVersion": 1,
            "status": bootstrap_v2.EXPECTED_ADAPTER["dormantSidecarStatus"],
            "registrySnapshotSha256": registry_sha,
            "registryRevision": registry_revision,
            "committedRevocationSnapshotSha256": revocation_sha,
            "committedRevocationRevision": revocation["revision"],
            "evaluatedLatestRevocationSnapshotSha256": revocation_sha,
            "evaluatedLatestRevocationRevision": revocation["revision"],
            "orderedRoleResults": [
                {
                    field: record[field]
                    for field in bootstrap_v2.DORMANT_ROLE_RESULT_FIELDS
                }
                for record in role_records
            ],
        }
        return {
            "registry": registry,
            "registry_snapshot_bytes": registry_raw,
            "revocation": revocation,
            "revocation_snapshot_bytes": revocation_raw,
            "registry_statement": registry_statement,
            "registry_root_statement_bytes": cls.payload_encoded(registry_statement),
            "revocation_statement": revocation_statement,
            "revocation_root_statement_bytes": cls.payload_encoded(revocation_statement),
            "envelopes": envelopes,
            "role_envelope_blobs": tuple(envelope_blobs),
            "role_signature_blobs": tuple(signature_blobs),
            "manifest": manifest,
            "manifest_bytes": cls.payload_encoded(manifest),
            "sidecar": sidecar,
            "adapter_sidecar_bytes": cls.payload_encoded(sidecar),
            "public_key_wire": wire,
        }

    def validate_payload(self, **overrides: object) -> tuple[str, ...]:
        values = {
            key: value
            for key, value in self.payload_fixture.items()
            if key.endswith("_bytes") or key.endswith("_blobs")
        }
        values.update(overrides)
        return bootstrap_v2.collect_dormant_owner_trust_payload_failures(
            values["registry_snapshot_bytes"],
            values["revocation_snapshot_bytes"],
            values["registry_root_statement_bytes"],
            values["revocation_root_statement_bytes"],
            role_envelope_blobs=values["role_envelope_blobs"],
            role_signature_blobs=values["role_signature_blobs"],
            manifest_bytes=values["manifest_bytes"],
            adapter_sidecar_bytes=values["adapter_sidecar_bytes"],
        )

    def assert_payload_failure(self, needle: str, **overrides: object) -> None:
        failures = self.validate_payload(**overrides)
        self.assertTrue(any(needle in item for item in failures), failures)
        self.assertIn(bootstrap_v2.PAYLOAD_DORMANT_MESSAGE, failures)

    def validate(
        self,
        profile_raw: object,
        *,
        predecessor: object | None = None,
        lineage: object | None = None,
    ) -> tuple[str, ...]:
        return bootstrap_v2.collect_owner_trust_bootstrap_v2_failures(
            profile_raw,
            predecessor_bytes=(
                self.predecessor_raw if predecessor is None else predecessor
            ),
            lineage_blobs=self.lineage if lineage is None else lineage,
        )

    def assert_semantic_failure(self, profile: object, needle: str) -> None:
        failures = self.validate(self.encoded(profile))
        self.assertTrue(any(needle in item for item in failures), failures)
        self.assertIn(bootstrap_v2.DORMANT_MESSAGE, failures)

    def test_exact_profile_is_only_dormant_and_raw_hash_is_pinned(self) -> None:
        self.assertEqual(self.validate(self.profile_raw), (bootstrap_v2.DORMANT_MESSAGE,))
        self.assertEqual(
            hashlib.sha256(self.profile_raw).hexdigest(),
            "13a3b3a5097b443620f049ad69663c486810945436e1c484f3a79cc8635c53f3",
        )
        self.assertEqual(
            bootstrap_v2.EXPECTED_PROFILE_RAW_SHA256,
            "13a3b3a5097b443620f049ad69663c486810945436e1c484f3a79cc8635c53f3",
        )
        self.assertEqual(self.profile["supersedes"], bootstrap_v2.EXPECTED_SUPERSEDES)
        self.assertEqual(
            self.profile["contractBinding"],
            bootstrap_v1.EXPECTED_CONTRACT_BINDING,
        )

    def test_principal_is_exact_account_control_not_real_world_identity(self) -> None:
        self.assertEqual(
            self.profile["principalCandidate"],
            bootstrap_v2.EXPECTED_PRINCIPAL,
        )
        self.assertEqual(
            self.profile["principalCandidate"]["identitySemantics"],
            "control_of_exact_github_account_not_real_world_identity",
        )
        for field, replacement in (
            ("login", "renamed-owner"),
            ("declaredPrincipal", "github:someone-else"),
            ("immutableUserId", 243786110),
            ("humanPrincipalCount", 2),
            ("status", "authenticated"),
        ):
            changed = copy.deepcopy(self.profile)
            changed["principalCandidate"][field] = replacement
            self.assert_semantic_failure(changed, "profile.principalCandidate")

    def test_fourteen_role_candidates_are_exact_unique_and_v3_ordered(self) -> None:
        mappings = self.profile["roleIdentityCandidates"]
        self.assertEqual(len(mappings), 14)
        expected_roles = tuple(mapping["role"] for mapping in mappings)
        materialization_failures: list[str] = []
        effective_v3 = receipt._materialize_effective_v3(
            self.lineage,
            materialization_failures,
        )
        self.assertEqual(materialization_failures, [])
        derived_roles, _, _, _, _ = receipt._derive_contract_sets(effective_v3, [])
        self.assertEqual(expected_roles, derived_roles)
        self.assertEqual(
            len({mapping["ownerBindingRefCandidate"] for mapping in mappings}),
            14,
        )
        self.assertEqual(
            len({mapping["ownerIdentityRefCandidate"] for mapping in mappings}),
            14,
        )
        self.assertEqual(
            len({mapping["receiptRefCandidate"] for mapping in mappings}),
            14,
        )
        for mapping in mappings:
            self.assertEqual(
                mapping,
                bootstrap_v2._expected_role_mapping(mapping["role"]),
            )
            self.assertEqual(
                mapping["principalRef"],
                self.profile["principalCandidate"]["principalRef"],
            )
            self.assertIsNone(mapping["credentialRefCandidate"])

    def test_role_missing_extra_reorder_duplicate_and_splice_fail_closed(self) -> None:
        mutations: list[tuple[object, str]] = []
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"].pop()
        mutations.append((changed, "count"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"].append(
            copy.deepcopy(changed["roleIdentityCandidates"][0])
        )
        mutations.append((changed, "count"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][0], changed["roleIdentityCandidates"][1] = (
            changed["roleIdentityCandidates"][1],
            changed["roleIdentityCandidates"][0],
        )
        mutations.append((changed, "canonical role order"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][1]["ownerIdentityRefCandidate"] = changed[
            "roleIdentityCandidates"
        ][0]["ownerIdentityRefCandidate"]
        mutations.append((changed, "not unique"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][2]["principalRef"] = "github-user-1-v1"
        mutations.append((changed, "mapping"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][3]["credentialRefCandidate"] = (
            "self-asserted-key"
        )
        mutations.append((changed, "mapping"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][4]["ownerBindingRefCandidate"] = []
        mutations.append((changed, "malformed"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][5]["ownerIdentityRefCandidate"] = {}
        mutations.append((changed, "malformed"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][6]["receiptRefCandidate"] = changed[
            "roleIdentityCandidates"
        ][0]["receiptRefCandidate"]
        mutations.append((changed, "receipt references are not unique"))
        changed = copy.deepcopy(self.profile)
        changed["roleIdentityCandidates"][7]["receiptRefCandidate"] = []
        mutations.append((changed, "receipt reference is malformed"))
        for profile, needle in mutations:
            self.assert_semantic_failure(profile, needle)

    def test_software_sshsig_candidate_is_exact_and_cannot_self_enroll(self) -> None:
        self.assertEqual(
            self.profile["signatureMechanismCandidate"],
            bootstrap_v2.EXPECTED_SIGNATURE_MECHANISM,
        )
        for field, replacement in (
            ("keyAlgorithm", "rsa-sha2-512"),
            ("hardwareBacked", True),
            ("messageHashAlgorithm", "sha256"),
            ("namespace", "file"),
            ("signatureEncoding", "raw"),
            ("automaticCredentialFallbackAllowed", True),
            ("privateKeyPathAccepted", True),
            ("callerSuppliedPrivateKeyMaterialAllowed", True),
            ("sshAgentEnumerationAllowed", True),
            ("sshAgentUseAllowed", True),
            ("environmentCredentialLookupAllowed", True),
            ("keychainCredentialLookupAllowed", True),
            ("projectDrivenSigningInvocationAllowed", True),
            ("releaseEvidenceKeyReuseAllowed", True),
            ("credentialRefCandidate", "credential:self-asserted"),
            ("publicKeyBlobSha256", "0" * 64),
            ("openSshPublicKeyFingerprint", "SHA256:self-asserted"),
            ("trustAnchorRef", "trust:self-asserted"),
            ("proofOfControlStatus", "verified"),
        ):
            changed = copy.deepcopy(self.profile)
            changed["signatureMechanismCandidate"][field] = replacement
            self.assert_semantic_failure(changed, "profile.signatureMechanismCandidate")

    def test_sshsig_wire_manifest_and_transition_contracts_fail_closed(self) -> None:
        mutations = (
            ("sshsigWireContract", "version", 2),
            ("sshsigWireContract", "reservedFieldPolicy", "ignored"),
            ("sshsigWireContract", "outerPublicKeyAlgorithm", "ssh-rsa"),
            ("sshsigWireContract", "embeddedPublicKeyPolicy", "trust_embedded_key"),
            ("sshsigWireContract", "sshCertificatesAllowed", True),
            ("sshsigWireContract", "armorLineLengthCharacters", 64),
            ("sshsigWireContract", "armorNewlinePolicy", "platform_default"),
            ("bundleManifestContract", "roleCardinality", 13),
            ("bundleManifestContract", "canonicalEncoding", "raw_json"),
            (
                "successorTransitionPolicy",
                "currentCandidateMayAuthenticate",
                True,
            ),
            (
                "successorTransitionPolicy",
                "selfAssertedTrustAnchorAllowed",
                True,
            ),
            (
                "successorTransitionPolicy",
                "githubPublishedKeyAsSoleTrustAnchorAllowed",
                True,
            ),
            (
                "successorTransitionPolicy",
                "cachedRegistryOrLocalClockFallbackAllowed",
                True,
            ),
        )
        for section, field, replacement in mutations:
            changed = copy.deepcopy(self.profile)
            changed[section][field] = replacement
            self.assert_semantic_failure(changed, f"profile.{section}")

    def test_envelope_registry_time_and_replay_safety_drift_fail_closed(self) -> None:
        mutations = (
            ("detachedEnvelopeContract", "nonceBytes", 16),
            ("detachedEnvelopeContract", "challengeTtlSeconds", 86_400),
            ("detachedEnvelopeContract", "perRoleSignatureRequired", False),
            ("detachedEnvelopeContract", "receiptMutationAllowed", True),
            (
                "detachedEnvelopeContract",
                "receiptRawBytePolicy",
                "canonical_only",
            ),
            (
                "detachedEnvelopeContract",
                "challengeIssuerPolicy",
                "owner_self_issued",
            ),
            (
                "detachedEnvelopeContract",
                "credentialBindingPolicy",
                "trust_embedded_key",
            ),
            (
                "registryAndRevocationContract",
                "githubAccountSnapshotRole",
                "trust_anchor",
            ),
            (
                "registryAndRevocationContract",
                "availabilityPolicy",
                "use_cached_snapshot",
            ),
            ("trustedTimeContract", "mayProveLatestRegistryRevision", True),
            ("trustedTimeContract", "maySubstituteForReplayLedger", True),
            ("replayContract", "ledgerStatus", "implemented"),
            ("replayContract", "partialConsumptionAllowed", True),
            ("replayContract", "rollbackDetectionRequired", False),
            ("replayContract", "coordinatorStatus", "implemented"),
            ("replayContract", "backupRestorePolicy", "restore_without_pair_check"),
        )
        for section, field, replacement in mutations:
            changed = copy.deepcopy(self.profile)
            changed[section][field] = replacement
            self.assert_semantic_failure(changed, f"profile.{section}")

    def test_selection_state_adapter_and_secret_injection_cannot_advance(self) -> None:
        for field in bootstrap_v1.SELECTION_FIELDS:
            changed = copy.deepcopy(self.profile)
            changed["selection"][field] = "candidate:forbidden"
            self.assert_semantic_failure(changed, "profile.selection")
        for field in bootstrap_v2.STATE_FIELDS:
            changed = copy.deepcopy(self.profile)
            changed["state"][field] = True
            self.assert_semantic_failure(changed, "profile.state")
        for field in (
            "mayCreateDormantSidecar",
            "genericCandidateFactoryMaySubstitute",
            "mayCreateAdapterResult",
        ):
            changed = copy.deepcopy(self.profile)
            changed["adapterProjection"][field] = True
            self.assert_semantic_failure(changed, "profile.adapterProjection")
        for field in ("privateKey", "passphrase", "githubToken", "signatureBytes"):
            changed = copy.deepcopy(self.profile)
            changed[field] = "forbidden"
            self.assert_semantic_failure(changed, "fields or field order")

    def test_predecessor_and_v3_lineage_drift_fail_closed(self) -> None:
        changed_predecessor = self.predecessor_raw.replace(
            b'"humanPrincipalCount": 1',
            b'"humanPrincipalCount": 2',
            1,
        )
        failures = self.validate(self.profile_raw, predecessor=changed_predecessor)
        self.assertTrue(any("predecessor" in item for item in failures), failures)
        self.assertIn(bootstrap_v2.DORMANT_MESSAGE, failures)

        changed_lineage = list(self.lineage)
        changed_lineage[-1] += b" "
        failures = self.validate(self.profile_raw, lineage=tuple(changed_lineage))
        self.assertTrue(any("SHA-256" in item or "exact" in item for item in failures), failures)
        self.assertIn(bootstrap_v2.DORMANT_MESSAGE, failures)

    def test_unknown_missing_reordered_duplicate_nonfinite_and_oversized_fail(self) -> None:
        changed = copy.deepcopy(self.profile)
        del changed["principalCandidate"]["immutableUserId"]
        self.assert_semantic_failure(changed, "profile.principalCandidate fields or field order")

        changed = copy.deepcopy(self.profile)
        changed["state"] = dict(reversed(tuple(changed["state"].items())))
        self.assert_semantic_failure(changed, "profile.state fields or field order")

        changed = copy.deepcopy(self.profile)
        changed["contractBinding"] = dict(
            reversed(tuple(changed["contractBinding"].items()))
        )
        self.assert_semantic_failure(
            changed,
            "profile.contractBinding fields or field order",
        )

        duplicate = self.profile_raw.replace(
            b'"schemaVersion": 2,',
            b'"schemaVersion": 2, "schemaVersion": 2,',
            1,
        )
        failures = self.validate(duplicate)
        self.assertTrue(any("duplicate" in item.lower() for item in failures), failures)

        nonfinite = self.profile_raw.replace(b'"schemaVersion": 2', b'"schemaVersion": NaN', 1)
        failures = self.validate(nonfinite)
        self.assertTrue(any("finite" in item.lower() for item in failures), failures)

        oversized = b"{" + b" " * bootstrap_v2.MAX_PROFILE_BYTES + b"}"
        failures = self.validate(oversized)
        self.assertTrue(any("exceeds" in item for item in failures), failures)

    def test_dormant_payload_exact_pair_is_only_structural(self) -> None:
        self.assertEqual(
            self.validate_payload(),
            (bootstrap_v2.PAYLOAD_DORMANT_MESSAGE,),
        )
        fixture = self.payload_fixture
        registry_sha = hashlib.sha256(fixture["registry_snapshot_bytes"]).hexdigest()
        revocation_sha = hashlib.sha256(
            fixture["revocation_snapshot_bytes"]
        ).hexdigest()
        self.assertEqual(
            fixture["revocation"]["registrySnapshotSha256"], registry_sha
        )
        self.assertEqual(
            fixture["manifest"]["revocationSnapshotSha256"], revocation_sha
        )
        self.assertFalse(
            bootstrap_v2.EXPECTED_ADAPTER["mayCreateDormantSidecar"]
        )

    def test_registry_schema_revision_bounds_and_no_back_reference_fail_closed(self) -> None:
        changed = copy.deepcopy(self.payload_fixture["registry"])
        changed["revocationSnapshotSha256"] = "0" * 64
        self.assert_payload_failure(
            "registry snapshot fields",
            registry_snapshot_bytes=self.payload_encoded(changed),
        )
        for revision in (1, True, -1, "01", "+1", "18446744073709551616"):
            with self.subTest(revision=revision):
                changed = copy.deepcopy(self.payload_fixture["registry"])
                changed["revision"] = revision
                self.assert_payload_failure(
                    "registry.revision",
                    registry_snapshot_bytes=self.payload_encoded(changed),
                )
        oversized = b"{" + b" " * bootstrap_v2.MAX_SNAPSHOT_BYTES + b"}"
        self.assert_payload_failure(
            "exceeds",
            registry_snapshot_bytes=oversized,
        )

    def test_principal_mapping_and_credential_resolution_fail_closed(self) -> None:
        changed = copy.deepcopy(self.payload_fixture["registry"])
        changed["principalMappings"][0]["credentialRef"] = (
            "g0-owner-credential-" + "0" * 64 + "-e1-v1"
        )
        self.assert_payload_failure(
            "dangling",
            registry_snapshot_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["registry"])
        changed["credentialRecords"][0]["allowedRoles"] = list(
            reversed(changed["credentialRecords"][0]["allowedRoles"])
        )
        self.assert_payload_failure(
            "allowedRoles",
            registry_snapshot_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["registry"])
        changed["credentialRecords"].append(
            copy.deepcopy(changed["credentialRecords"][0])
        )
        changed["credentialRecords"][1]["credentialRef"] = (
            "g0-owner-credential-" + "2" * 64 + "-e2-v1"
        )
        self.assert_payload_failure(
            "orphaned",
            registry_snapshot_bytes=self.payload_encoded(changed),
        )

    def test_credential_wire_digest_epoch_and_private_material_fail_closed(self) -> None:
        changed = copy.deepcopy(self.payload_fixture["registry"])
        changed["credentialRecords"][0]["keyEpoch"] = "01"
        self.assert_payload_failure(
            "keyEpoch",
            registry_snapshot_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["registry"])
        changed["credentialRecords"][0]["publicKeyWireBlobBase64"] = base64.b64encode(
            b"ssh-ed25519"
        ).decode("ascii")
        self.assert_payload_failure(
            "51-byte",
            registry_snapshot_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["registry"])
        changed["credentialRecords"][0]["privateKey"] = "forbidden"
        self.assert_payload_failure(
            "fields are not exact",
            registry_snapshot_bytes=self.payload_encoded(changed),
        )

    def test_status_reference_and_active_revoked_conditions_fail_closed(self) -> None:
        changed = copy.deepcopy(self.payload_fixture["revocation"])
        changed["credentialStatuses"][0]["effectiveAt"] = "2026-02-01T00:00:00Z"
        self.assert_payload_failure(
            "active fields",
            revocation_snapshot_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["revocation"])
        changed["credentialStatuses"][0]["status"] = "revoked"
        changed["credentialStatuses"][0]["reason"] = "compromise"
        self.assert_payload_failure(
            "effectiveAt",
            revocation_snapshot_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["revocation"])
        changed["registrySnapshotSha256"] = "0" * 64
        self.assert_payload_failure(
            "registrySnapshotSha256",
            revocation_snapshot_bytes=self.payload_encoded(changed),
        )

        registry = copy.deepcopy(self.payload_fixture["registry"])
        roles = list(bootstrap_v2._EXPECTED_ROLE_ORDER)
        first_credential = registry["credentialRecords"][0]
        second_wire = (
            (11).to_bytes(4, "big")
            + b"ssh-ed25519"
            + (32).to_bytes(4, "big")
            + b"\x02" * 32
        )
        second_digest = hashlib.sha256(second_wire).hexdigest()
        second_ref = f"g0-owner-credential-{second_digest}-e1-v1"
        second_status_ref = (
            "g0-owner-credential-status-"
            + hashlib.sha256(second_ref.encode("utf-8")).hexdigest()
            + "-v1"
        )
        second_credential = copy.deepcopy(first_credential)
        first_credential["allowedRoles"] = roles[:-1]
        second_credential.update(
            {
                "credentialRef": second_ref,
                "publicKeyWireBlobBase64": base64.b64encode(second_wire).decode("ascii"),
                "publicKeyBlobSha256": second_digest,
                "openSshPublicKeyFingerprint": "SHA256:"
                + base64.b64encode(bytes.fromhex(second_digest)).decode("ascii").rstrip("="),
                "allowedRoles": [roles[-1]],
                "proofOfControlRef": "g0-owner-proof-of-control-2-v1",
                "proofOfControlEnvelopeSha256": "2" * 64,
                "revocationRef": second_status_ref,
                "provenanceRef": "registry-root-attestation-2-v1",
            }
        )
        registry["credentialRecords"].append(second_credential)
        registry["principalMappings"][-1]["credentialRef"] = second_ref
        registry["principalMappings"][-1]["revocationRef"] = second_status_ref
        registry_bytes = self.payload_encoded(registry)

        revocation = copy.deepcopy(self.payload_fixture["revocation"])
        revocation["registrySnapshotSha256"] = hashlib.sha256(registry_bytes).hexdigest()
        revocation["credentialStatuses"].append(
            {
                "statusRef": second_status_ref,
                "credentialRef": second_ref,
                "publicKeyBlobSha256": second_digest,
                "keyEpoch": "1",
                "status": "active",
                "effectiveAt": None,
                "compromiseAt": None,
                "reason": None,
            }
        )
        ordered_failures = self.validate_payload(
            registry_snapshot_bytes=registry_bytes,
            revocation_snapshot_bytes=self.payload_encoded(revocation),
        )
        self.assertFalse(
            any("status 0.credentialRef" in item or "status 1.credentialRef" in item for item in ordered_failures),
            ordered_failures,
        )
        revocation["credentialStatuses"].reverse()
        self.assert_payload_failure(
            "status 0.credentialRef",
            registry_snapshot_bytes=registry_bytes,
            revocation_snapshot_bytes=self.payload_encoded(revocation),
        )

    def test_root_statements_are_canonical_null_and_algorithm_neutral(self) -> None:
        changed = copy.deepcopy(self.payload_fixture["registry_statement"])
        changed["rootAlgorithmRef"] = "owner-sshsig-reuse-forbidden"
        self.assert_payload_failure(
            "rootAlgorithmRef must remain null",
            registry_root_statement_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["revocation_statement"])
        changed["snapshotSha256"] = "0" * 64
        self.assert_payload_failure(
            "snapshotSha256",
            revocation_root_statement_bytes=self.payload_encoded(changed),
        )
        noncanonical = json.dumps(
            self.payload_fixture["registry_statement"],
            ensure_ascii=False,
            separators=(", ", ": "),
        ).encode("utf-8")
        self.assert_payload_failure(
            "JCS",
            registry_root_statement_bytes=noncanonical,
        )

    def test_role_epoch_digest_manifest_and_cross_role_swap_fail_closed(self) -> None:
        envelopes = copy.deepcopy(self.payload_fixture["envelopes"])
        envelopes[0]["keyEpoch"] = "2"
        envelope_blobs = tuple(self.payload_encoded(item) for item in envelopes)
        self.assert_payload_failure(
            "keyEpoch",
            role_envelope_blobs=envelope_blobs,
        )
        manifest = copy.deepcopy(self.payload_fixture["manifest"])
        manifest["orderedRoleEntries"][0], manifest["orderedRoleEntries"][1] = (
            manifest["orderedRoleEntries"][1],
            manifest["orderedRoleEntries"][0],
        )
        self.assert_payload_failure(
            "manifest role entry 0",
            manifest_bytes=self.payload_encoded(manifest),
        )
        signatures = list(self.payload_fixture["role_signature_blobs"])
        signatures[0], signatures[1] = signatures[1], signatures[0]
        self.assert_payload_failure(
            "manifest role entry 0",
            role_signature_blobs=tuple(signatures),
        )

    def test_sidecar_exact_pair_and_role_digests_fail_closed(self) -> None:
        changed = copy.deepcopy(self.payload_fixture["sidecar"])
        changed["registrySnapshotSha256"] = "0" * 64
        self.assert_payload_failure(
            "sidecar.registrySnapshotSha256",
            adapter_sidecar_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["sidecar"])
        changed["evaluatedLatestRevocationRevision"] = "0"
        self.assert_payload_failure(
            "evaluatedLatestRevocationRevision",
            adapter_sidecar_bytes=self.payload_encoded(changed),
        )
        changed = copy.deepcopy(self.payload_fixture["sidecar"])
        changed["orderedRoleResults"][0], changed["orderedRoleResults"][1] = (
            changed["orderedRoleResults"][1],
            changed["orderedRoleResults"][0],
        )
        self.assert_payload_failure(
            "sidecar role result 0",
            adapter_sidecar_bytes=self.payload_encoded(changed),
        )

    def test_payload_json_type_confusion_is_dormant_fail_closed(self) -> None:
        json_values: tuple[object, ...] = (None, False, 0, 1.5, "wrong", [], {})
        for field in (
            "ownerBindingRef",
            "ownerIdentityRef",
            "credentialRef",
            "revocationRef",
        ):
            for replacement in json_values:
                with self.subTest(document="registry mapping", field=field, value=replacement):
                    changed = copy.deepcopy(self.payload_fixture["registry"])
                    changed["principalMappings"][0][field] = replacement
                    failures = self.validate_payload(
                        registry_snapshot_bytes=self.payload_encoded(changed)
                    )
                    self.assertIn(bootstrap_v2.PAYLOAD_DORMANT_MESSAGE, failures)
                    self.assertGreater(len(failures), 1, failures)

        for replacement in json_values:
            with self.subTest(document="revocation status", field="reason", value=replacement):
                changed = copy.deepcopy(self.payload_fixture["revocation"])
                changed["credentialStatuses"][0].update(
                    {
                        "status": "revoked",
                        "effectiveAt": "2026-02-01T00:00:00Z",
                        "reason": replacement,
                    }
                )
                failures = self.validate_payload(
                    revocation_snapshot_bytes=self.payload_encoded(changed)
                )
                self.assertIn(bootstrap_v2.PAYLOAD_DORMANT_MESSAGE, failures)
                self.assertGreater(len(failures), 1, failures)

        for replacement in ([], {}):
            with self.subTest(document="credential", field="allowedRoles", value=replacement):
                changed = copy.deepcopy(self.payload_fixture["registry"])
                changed["credentialRecords"][0]["allowedRoles"] = [replacement]
                failures = self.validate_payload(
                    registry_snapshot_bytes=self.payload_encoded(changed)
                )
                self.assertIn(bootstrap_v2.PAYLOAD_DORMANT_MESSAGE, failures)
                self.assertGreater(len(failures), 1, failures)

    def test_sshsig_armor_and_wire_structure_fail_closed(self) -> None:
        wire = self.payload_fixture["public_key_wire"]
        self.assertIsInstance(wire, bytes)
        signature = hashlib.sha512(b"independent-structural-signature").digest()
        valid = self.sshsig_blob(wire, signature)
        valid_payload = self.sshsig_payload(wire, signature)
        altered_key = wire[:-1] + bytes([wire[-1] ^ 1])
        cases: tuple[tuple[str, object, str], ...] = (
            ("type", "not-bytes", "must be bytes"),
            (
                "armor-boundary",
                b"leading-byte" + valid,
                "one canonical OpenSSH SSHSIG block",
            ),
            (
                "armor-line-wrap",
                b"-----BEGIN SSH SIGNATURE-----\n"
                + base64.b64encode(valid_payload)
                + b"\n-----END SSH SIGNATURE-----\n",
                "armor is not canonical",
            ),
            (
                "armor-crlf",
                valid.replace(b"\n", b"\r\n"),
                "one canonical OpenSSH SSHSIG block",
            ),
            (
                "armor-final-lf",
                valid[:-1],
                "one canonical OpenSSH SSHSIG block",
            ),
            (
                "wire-length",
                self.armor_sshsig(b"SSHSIG" + (1).to_bytes(4, "big") + b"\x00\x00\xff\xff"),
                "SSH string length exceeds supplied bytes",
            ),
            (
                "wire-magic",
                self.sshsig_blob(wire, signature, magic=b"BADBAD"),
                "SSHSIG magic is not exact",
            ),
            (
                "wire-version",
                self.sshsig_blob(wire, signature, version=2),
                "SSHSIG version is not 1",
            ),
            (
                "embedded-key",
                self.sshsig_blob(altered_key, signature),
                "does not equal the role credential",
            ),
            (
                "namespace",
                self.sshsig_blob(wire, signature, namespace=b"wrong-namespace"),
                "namespace is not exact",
            ),
            (
                "reserved",
                self.sshsig_blob(wire, signature, reserved=b"not-empty"),
                "reserved field is not empty",
            ),
            (
                "hash",
                self.sshsig_blob(wire, signature, hash_algorithm=b"sha256"),
                "hash algorithm is not sha512",
            ),
            (
                "inner-algorithm",
                self.sshsig_blob(wire, signature, inner_algorithm=b"ssh-rsa"),
                "inner signature algorithm is not ssh-ed25519",
            ),
            (
                "inner-length",
                self.sshsig_blob(wire, signature[:-1]),
                "inner signature length is not 64 bytes",
            ),
            (
                "wire-trailing",
                self.armor_sshsig(valid_payload + b"\x00"),
                "SSHSIG wire has trailing bytes",
            ),
        )
        for name, malformed, needle in cases:
            with self.subTest(name=name):
                signatures = list(self.payload_fixture["role_signature_blobs"])
                signatures[0] = malformed
                self.assert_payload_failure(
                    needle,
                    role_signature_blobs=tuple(signatures),
                )

    def test_mutable_buffers_are_snapshotted_before_validation(self) -> None:
        profile_buffer = bytearray(self.profile_raw)
        predecessor_buffer = bytearray(self.predecessor_raw)
        lineage_buffers = tuple(bytearray(raw) for raw in self.lineage)
        targets = {id(profile_buffer), id(predecessor_buffer), *(id(raw) for raw in lineage_buffers)}
        mutated: set[int] = set()
        real_snapshot = receipt._bounded_snapshot

        def snapshot_then_mutate(
            value: object,
            label: str,
            maximum_bytes: int,
            failures: list[str],
        ) -> bytes | None:
            snapshot = real_snapshot(value, label, maximum_bytes, failures)
            if id(value) in targets and id(value) not in mutated:
                assert isinstance(value, bytearray)
                value[0] ^= 1
                mutated.add(id(value))
            return snapshot

        with mock.patch.object(receipt, "_bounded_snapshot", side_effect=snapshot_then_mutate):
            failures = self.validate(
                profile_buffer,
                predecessor=predecessor_buffer,
                lineage=lineage_buffers,
            )
        self.assertEqual(failures, (bootstrap_v2.DORMANT_MESSAGE,))
        self.assertEqual(mutated, targets)

    def test_pure_validator_performs_no_io_process_network_clock_or_entropy(self) -> None:
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("file I/O")),
            mock.patch.object(os, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network")),
            mock.patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("network"),
            ),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("process")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process")),
            mock.patch.object(time, "time", side_effect=AssertionError("clock")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("clock")),
            mock.patch.object(os, "urandom", side_effect=AssertionError("entropy")),
            mock.patch.object(
                secrets,
                "token_bytes",
                side_effect=AssertionError("entropy"),
            ),
        ):
            self.assertEqual(
                self.validate(self.profile_raw),
                (bootstrap_v2.DORMANT_MESSAGE,),
            )
            self.assertEqual(
                self.validate_payload(),
                (bootstrap_v2.PAYLOAD_DORMANT_MESSAGE,),
            )

    def test_checker_import_surface_has_no_private_key_channels(self) -> None:
        module_values = vars(bootstrap_v2)
        for name in (
            "os",
            "socket",
            "subprocess",
            "secrets",
            "time",
            "keyring",
            "paramiko",
            "cryptography",
        ):
            self.assertNotIn(name, module_values)
        for forbidden in (
            "ssh-keygen",
            "SSH_AUTH_SOCK",
            "security add-generic-password",
            "security find-generic-password",
        ):
            self.assertNotIn(forbidden, Path(bootstrap_v2.__file__).read_text())

    def test_public_api_exposes_no_key_or_adapter_constructor(self) -> None:
        self.assertEqual(
            bootstrap_v2.__all__,
            (
                "DORMANT_MESSAGE",
                "PAYLOAD_DORMANT_MESSAGE",
                "EXPECTED_PROFILE_RAW_SHA256",
                "MAX_PROFILE_BYTES",
                "PROFILE_PATH",
                "collect_dormant_owner_trust_payload_failures",
                "collect_owner_trust_bootstrap_v2_failures",
                "main",
            ),
        )
        public_callables = {
            name
            for name, value in vars(bootstrap_v2).items()
            if not name.startswith("_") and callable(value) and name != "Path"
        }
        self.assertEqual(
            public_callables,
            {
                "collect_dormant_owner_trust_payload_failures",
                "collect_owner_trust_bootstrap_v2_failures",
                "main",
            },
        )

    def test_worktree_reader_rejects_symlink_and_mid_validation_replacement(self) -> None:
        def populate(root: Path) -> None:
            for path, raw in zip(receipt.LINEAGE_PATHS, self.lineage):
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
            predecessor_path = root / bootstrap_v1.PROFILE_PATH
            predecessor_path.parent.mkdir(parents=True, exist_ok=True)
            predecessor_path.write_bytes(self.predecessor_raw)
            profile_path = root / bootstrap_v2.PROFILE_PATH
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_bytes(self.profile_raw)

        targets = (
            (bootstrap_v2.PROFILE_PATH, self.profile_raw),
            (bootstrap_v1.PROFILE_PATH, self.predecessor_raw),
            (receipt.LINEAGE_PATHS[0], self.lineage[0]),
        )
        for index, (target, original) in enumerate(targets):
            with self.subTest(operation="symlink", target=target):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    populate(root)
                    self.assertEqual(bootstrap_v2._collect_worktree_failures(root), ())
                    target_path = root / target
                    external = root / f"outside-{index}.json"
                    external.write_bytes(original)
                    target_path.unlink()
                    target_path.symlink_to(external)
                    failures = bootstrap_v2._collect_worktree_failures(root)
                    self.assertTrue(
                        any("symlink" in item.lower() for item in failures),
                        failures,
                    )

        for target, original in targets:
            with self.subTest(operation="replacement", target=target):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    populate(root)
                    target_path = root / target
                    real_validate = bootstrap_v2.collect_owner_trust_bootstrap_v2_failures

                    def validate_then_replace(
                        *args: object,
                        **kwargs: object,
                    ) -> tuple[str, ...]:
                        result = real_validate(*args, **kwargs)
                        target_path.write_bytes(original + b" ")
                        return result

                    with mock.patch.object(
                        bootstrap_v2,
                        "collect_owner_trust_bootstrap_v2_failures",
                        side_effect=validate_then_replace,
                    ):
                        failures = bootstrap_v2._collect_worktree_failures(root)
                    self.assertTrue(
                        any(
                            "bytes changed" in item or "identity changed" in item
                            for item in failures
                        ),
                        failures,
                    )


if __name__ == "__main__":
    unittest.main()
