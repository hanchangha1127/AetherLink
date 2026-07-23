#!/usr/bin/env python3
"""Build and independently validate deterministic G1a-C candidate vectors.

This is intentionally separate from ``check_production_g1a_c_vectors.py`` so
the historical object-10...22 fixture remains a byte-for-byte regression
anchor.  The default mode is read-only; ``--rewrite`` is the only write path.

Only Python's standard library is used.  ALS1, RFC6979 P-256, canonical DER,
and low-S validation reuse the independent standard-library implementation in
the historical oracle rather than any Swift or Kotlin production code.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import check_production_g1a_c_vectors as base


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "shared/protocol/fixtures/production-g1a-c-candidate-v1-vectors.json"
LEGACY_FIXTURE_SHA256 = "c25c0f4d74b0029f060bcedf31b19ef95c57a0a0e6708a741175c8cedeb611f3"

ALS1_MAGIC = b"ALS1"
ALP1_MAGIC = b"ALP1"
VERSION = 1
C1_SUITE = base.C1_SUITE
SECURE_SUITE = base.SECURE_SUITE
PROFILE = base.PROFILE
SIGNATURE_ALGORITHM = base.SIGNATURE_ALGORITHM
P2P_KIND = "verified_p2p_direct_v1"
P2P_TRANSCRIPT_KIND = "p2p_direct"

NOW_MS = 1_000_000
KEYSET_NOT_BEFORE_MS = 999_000
KEYSET_EXPIRES_AT_MS = 1_100_000
BATCH_EXPIRES_AT_MS = 1_030_000
PROOF_ISSUED_AT_MS = 999_800
CAPABILITY_ISSUED_AT_MS = 999_900
OPERATION_NOT_BEFORE_MS = 999_990
OPERATION_EXPIRES_AT_MS = 1_020_000
PATH_VALIDATED_AT_MS = 999_900
PATH_EXPIRES_AT_MS = 1_015_000
PLAN_NOT_BEFORE_MS = 999_990
PLAN_EXPIRES_AT_MS = 1_010_000
ROUTE_CAPABILITY_EXPIRES_AT_MS = 1_012_000
RECEIPT_EXPIRES_AT_MS = 1_010_000

MAXIMUM_CANDIDATE_BYTES = 8_291
MAXIMUM_CAPABILITY_BYTES = 4_096
MAXIMUM_GRANT_EVIDENCE_BYTES = 8_192
MAXIMUM_GRANT_AUTHORIZATION_BYTES = 2_048
MAXIMUM_ENDPOINT_PROOF_BYTES = 2_048
MAXIMUM_OPERATION_RECEIPT_BYTES = 4_096

DESTINATION_POLICY_ID = "public_only_special_use_deny_iana_2025_10_09_v1"
DESTINATION_POLICY_VERSION = 1
OPERATION_ORDER = (
    "client_publish,runtime_fetch_client,runtime_publish,client_fetch_runtime"
)

FIELD_COUNTS = {
    2: 6,
    3: 6,
    4: 8,
    7: 21,
    8: 16,
    10: 11,
    13: 22,
    14: 15,
    15: 11,
    18: 21,
    23: 34,
    24: 34,
    25: 34,
    26: 18,
    27: 24,
    28: 48,
}

MAXIMUM_OBJECT_BYTES = {
    2: 512,
    3: 512,
    4: 512,
    7: 1_024,
    8: 4_096,
    10: 4_096,
    13: 2_048,
    14: 2_048,
    15: 1_024,
    18: 2_048,
    23: MAXIMUM_CAPABILITY_BYTES,
    24: MAXIMUM_CAPABILITY_BYTES,
    25: MAXIMUM_GRANT_EVIDENCE_BYTES,
    26: MAXIMUM_GRANT_AUTHORIZATION_BYTES,
    27: MAXIMUM_ENDPOINT_PROOF_BYTES,
    28: MAXIMUM_OPERATION_RECEIPT_BYTES,
}

KEY_SCALARS = {
    "root": 101,
    "route": 102,
    "candidateCapability": 103,
    "candidateReceipt": 104,
    "clientIdentity": 105,
    "runtimeIdentity": 106,
    "clientEphemeral": 107,
    "runtimeEphemeral": 108,
}

EXPECTED_KEY_IDS = {
    "root": "3575cdea4bc07eb0b02e8775c66ed51ee9ca8ec3bd330f041e7c87c8b8aa3a0f",
    "route": "39ad001c9275120f6ce735f7a2e04d734ca8de2370ac613a3e89bb899ff99dc7",
    "candidateCapability": "2308d684423927e8713e94cf3a548bb04bbeb11e4af74114968cbde3cd51fb73",
    "candidateReceipt": "dbd7185e1cdd938a5798f4f1ff4be526eee4fc4eb85b1ff83eb71ae80be81665",
    "clientIdentity": "a54dbd7cd8848bc7057cfbb1ee4269c41d9a8f64ad996d63b2df1fc28cf5aff3",
    "runtimeIdentity": "3136a7a8e24b00db43b0c3a541ea8acbcc8acd2e93c37afab83d9a774bac6769",
    "clientEphemeral": "9e432f18ddca328f9a380a5b37126fd43cce951e022c36ce23f13eda3386ef77",
    "runtimeEphemeral": "9908d763eb241a6e988261337202f69de4c1ff3684c44688b1ce657a2bcbf881",
}

OPERATION_SPECS = (
    {
        "id": "clientPublish",
        "wireName": "client_publish",
        "operation": "candidate_publish",
        "objectType": 23,
        "authorizationObjectType": 2,
        "authorizationKind": "p2p_publish",
        "requesterRole": "client",
        "candidateOwnerRole": "client",
        "batch": "clientCandidateBatch",
        "identityKey": "clientIdentity",
        "capabilityPurpose": 1 << 2,
        "receiptPurpose": 1 << 4,
    },
    {
        "id": "runtimeFetchClient",
        "wireName": "runtime_fetch_client",
        "operation": "candidate_fetch",
        "objectType": 24,
        "authorizationObjectType": 3,
        "authorizationKind": "p2p_fetch",
        "requesterRole": "runtime",
        "candidateOwnerRole": "client",
        "batch": "clientCandidateBatch",
        "identityKey": "runtimeIdentity",
        "capabilityPurpose": 1 << 3,
        "receiptPurpose": 1 << 5,
    },
    {
        "id": "runtimePublish",
        "wireName": "runtime_publish",
        "operation": "candidate_publish",
        "objectType": 23,
        "authorizationObjectType": 2,
        "authorizationKind": "p2p_publish",
        "requesterRole": "runtime",
        "candidateOwnerRole": "runtime",
        "batch": "runtimeCandidateBatch",
        "identityKey": "runtimeIdentity",
        "capabilityPurpose": 1 << 2,
        "receiptPurpose": 1 << 4,
    },
    {
        "id": "clientFetchRuntime",
        "wireName": "client_fetch_runtime",
        "operation": "candidate_fetch",
        "objectType": 24,
        "authorizationObjectType": 3,
        "authorizationKind": "p2p_fetch",
        "requesterRole": "client",
        "candidateOwnerRole": "runtime",
        "batch": "runtimeCandidateBatch",
        "identityKey": "clientIdentity",
        "capabilityPurpose": 1 << 3,
        "receiptPurpose": 1 << 5,
    },
)


class CandidateVectorError(base.VectorError):
    """The candidate fixture or an independently reconstructed value is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CandidateVectorError(message)


def labeled_digest(label: str) -> str:
    return base.sha256_hex(base.ascii_bytes(label))


def labeled_short_hex(label: str) -> str:
    return labeled_digest(label)[:32]


def domain_digest(domain: str, claims: bytes) -> str:
    return base.sha256_hex(base.signature_transcript(domain, claims))


def alp1_encode(object_type: int, fields: Iterable[bytes]) -> bytes:
    require(type(object_type) is int and 0 < object_type < 256, "invalid ALP1 object type")
    output = bytearray(ALP1_MAGIC + bytes((object_type, VERSION)))
    for tag, field in enumerate(fields, 1):
        require(tag < 256 and isinstance(field, bytes), "invalid ALP1 field")
        output.extend(bytes((tag,)) + base.be32(len(field)) + field)
    return bytes(output)


def alp1_decode(data: bytes, object_type: int, field_count: int) -> list[bytes]:
    require(isinstance(data, bytes) and len(data) >= 6, "truncated ALP1 object")
    require(data[:4] == ALP1_MAGIC, "wrong ALP1 magic")
    require(data[4] == object_type, "wrong ALP1 object type")
    require(data[5] == VERSION, "wrong ALP1 version")
    offset = 6
    fields: list[bytes] = []
    for expected_tag in range(1, field_count + 1):
        require(offset + 5 <= len(data), "truncated ALP1 field header")
        require(data[offset] == expected_tag, "non-sequential ALP1 tag")
        length = int.from_bytes(data[offset + 1 : offset + 5], "big")
        offset += 5
        require(offset + length <= len(data), "truncated ALP1 field")
        fields.append(data[offset : offset + length])
        offset += length
    require(offset == len(data), "trailing ALP1 bytes")
    return fields


def artifact_record(
    object_type: int,
    input_value: dict[str, Any],
    canonical: bytes,
) -> dict[str, Any]:
    return {
        "magic": ALP1_MAGIC.decode("ascii"),
        "objectType": object_type,
        "coverage": "semantic",
        "input": input_value,
        "expectedCanonicalByteCount": len(canonical),
        "expectedCanonicalHex": canonical.hex(),
        "expectedSha256Hex": base.sha256_hex(canonical),
    }


def signature_record(
    signer: str,
    domain: str,
    claims: bytes,
    scalar: int,
    purpose: str,
    purpose_bit: int | None,
) -> tuple[bytes, dict[str, Any]]:
    signature, record = base.signed_signature_record(signer, domain, claims, scalar)
    record["requiredPurpose"] = purpose
    record["requiredPurposeBit"] = purpose_bit
    return signature, record


def candidate_bytes(
    *,
    sequence: int,
    address: bytes,
    port: int = 50_000,
    priority: int = 100,
) -> bytes:
    require(len(address) == 4, "candidate vector must use IPv4")
    require(1 <= sequence <= 255, "invalid candidate sequence")
    return (
        bytes((2, 4, 1))
        + base.be16(port)
        + base.be32(priority)
        + bytes((sequence,)) * 8
        + bytes((len(address),))
        + address
    )


def candidate_batch_bytes(
    *,
    session_id: str,
    generation: int,
    sequence: int,
    expires_at_ms: int,
    role: str,
    candidate: bytes,
) -> bytes:
    blob = base.be16(1) + candidate
    return alp1_encode(
        1,
        [
            base.ascii_bytes(session_id),
            base.be64(generation),
            base.be64(sequence),
            base.be64(expires_at_ms),
            base.ascii_bytes(role),
            blob,
        ],
    )


def path_validation_receipt_bytes(value: dict[str, Any]) -> bytes:
    return alp1_encode(
        5,
        [
            base.ascii_bytes(value["sessionId"]),
            base.be64(value["generation"]),
            base.ascii_bytes(value["candidatePairDigest"]),
            base.ascii_bytes(value["transport"]),
            base.ascii_bytes(value["clientObserved"]),
            base.ascii_bytes(value["runtimeObserved"]),
            base.be64(value["validatedAtMs"]),
            base.be64(value["expiresAtMs"]),
        ],
    )


def selected_candidate_pair_digest(client: bytes, runtime: bytes) -> str:
    claims = b""
    for role, candidate in (("client", client), ("runtime", runtime)):
        role_bytes = base.ascii_bytes(role)
        claims += base.be32(len(role_bytes)) + role_bytes
        claims += base.be32(len(candidate)) + candidate
    return domain_digest("AetherLink G1a-C selected direct candidate-pair v1", claims)


def bilateral_digest(domain: str, client_digest: str, runtime_digest: str) -> str:
    claims = b""
    for role, digest in (("client", client_digest), ("runtime", runtime_digest)):
        role_bytes = base.ascii_bytes(role)
        digest_bytes = base.raw_digest(digest)
        claims += base.be32(len(role_bytes)) + role_bytes
        claims += base.be32(len(digest_bytes)) + digest_bytes
    return domain_digest(domain, claims)


def secure_route_authorization_bytes(
    *,
    object_type: int,
    pair_binding_digest: str,
    pair_epoch: int,
    generation: int,
    candidate_batch_digest: str | None = None,
    capability_digest: str | None = None,
    candidate_pair_digest: str | None = None,
    path_validation_receipt_digest: str | None = None,
    bilateral_publish_digest: str | None = None,
    bilateral_fetch_digest: str | None = None,
) -> bytes:
    common = [
        base.ascii_bytes(SECURE_SUITE),
        base.ascii_bytes(pair_binding_digest),
        base.be64(pair_epoch),
        base.be64(generation),
    ]
    if object_type in (2, 3):
        require(candidate_batch_digest is not None, "missing candidate batch digest")
        require(capability_digest is not None, "missing capability digest")
        fields = common + [
            base.ascii_bytes(candidate_batch_digest),
            base.ascii_bytes(capability_digest),
        ]
    elif object_type == 4:
        values = [
            candidate_pair_digest,
            path_validation_receipt_digest,
            bilateral_publish_digest,
            bilateral_fetch_digest,
        ]
        require(all(value is not None for value in values), "missing final P2P digest")
        fields = common + [base.ascii_bytes(value) for value in values if value is not None]
    else:
        raise CandidateVectorError("unsupported secure route authorization type")
    return base.als1_encode(object_type, fields)


def request_digest(request_id: str, capability_digest: str, authorization_digest: str) -> str:
    claims = (
        base.raw_digest(request_id)
        + base.raw_digest(capability_digest)
        + base.raw_digest(authorization_digest)
    )
    return domain_digest("AetherLink G1a-C candidate usage request v1", claims)


def usage_result_digest(
    *,
    proof_id: str,
    request_digest_value: str,
    capability_digest: str,
    authorization_digest: str,
    single_use_nonce: str,
    consumed_bytes: int,
    previous_revision: int,
    committed_revision: int,
) -> str:
    claims = b"".join(
        base.raw_digest(value)
        for value in (
            proof_id,
            request_digest_value,
            capability_digest,
            authorization_digest,
            single_use_nonce,
        )
    )
    claims += base.be64(consumed_bytes)
    claims += base.be64(previous_revision)
    claims += base.be64(committed_revision)
    return domain_digest(
        "AetherLink G1a-C readback-confirmed candidate usage receipt v1",
        claims,
    )


def usage_snapshot_digest(state: dict[str, Any]) -> str:
    entries = state["entries"]
    claims = (
        base.be64(state["revision"])
        + base.be64(state["remainingOperations"])
        + base.be64(state["remainingBytes"])
        + base.be32(state["retentionLimit"])
        + base.be32(len(entries))
    )
    for entry in entries:
        for key in (
            "requestId",
            "requestDigest",
            "capabilityDigest",
            "authorizationDigest",
            "singleUseNonce",
            "receiptDigest",
        ):
            claims += base.raw_digest(entry[key])
        claims += base.be64(entry["consumedBytes"])
        claims += base.be64(entry["committedRevision"])
    return domain_digest("AetherLink G1a-C candidate usage ledger snapshot v1", claims)


def endpoint_proof_record(
    *,
    value: dict[str, Any],
    signer: str,
    scalar: int,
) -> tuple[bytes, dict[str, Any]]:
    fields = [
        base.ascii_bytes(C1_SUITE),
        base.be64(1),
        base.ascii_bytes(value["requesterRole"]),
        base.ascii_bytes(value["requesterIdentityFingerprint"]),
        bytes.fromhex(value["requesterPublicKeyX963Hex"]),
        base.ascii_bytes(value["operation"]),
        base.ascii_bytes(value["candidateOwnerRole"]),
        base.ascii_bytes(value["candidateOwnerIdentityFingerprint"]),
        base.ascii_bytes(value["sessionId"]),
        base.ascii_bytes(value["attemptId"]),
        base.ascii_bytes(value["capabilityId"]),
        base.ascii_bytes(value["candidateBatchDigest"]),
        base.be64(value["candidateBatchSequence"]),
        base.ascii_bytes(value["singleUseNonce"]),
        base.ascii_bytes(value["securityContextDigest"]),
        base.be64(value["issuedAtMs"]),
        base.be64(value["notBeforeMs"]),
        base.be64(value["expiresAtMs"]),
        base.ascii_bytes(value["proofId"]),
        base.ascii_bytes(value["pairAuthorityDigest"]),
        base.ascii_bytes(value["serviceAudienceId"]),
        base.ascii_bytes(value["initiatorRole"]),
        base.ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    claims = base.als1_encode(27, fields)
    signature, signature_meta = signature_record(
        signer,
        "AetherLink G1a-C endpoint-authenticated candidate operation v1",
        claims,
        scalar,
        "endpoint_long_term_identity",
        None,
    )
    canonical = base.als1_encode(27, fields + [signature])
    return canonical, base.object_record(
        27,
        "semantic",
        value,
        canonical,
        claims,
        [signature_meta],
    )


def candidate_capability_record(
    *,
    value: dict[str, Any],
    scalar: int,
) -> tuple[bytes, dict[str, Any]]:
    object_type = value["objectType"]
    fields = [
        base.ascii_bytes(C1_SUITE),
        base.ascii_bytes(value["operation"]),
        base.ascii_bytes(value["serviceIdDigest"]),
        base.be64(value["keysetVersion"]),
        base.ascii_bytes(value["signingKeyId"]),
        base.ascii_bytes(value["capabilityId"]),
        base.ascii_bytes(value["pairAuthorityDigest"]),
        base.ascii_bytes(value["pairBindingDigest"]),
        base.be64(value["pairEpoch"]),
        base.be64(value["generation"]),
        base.be64(value["serviceConfigVersion"]),
        base.be64(value["revocationCounter"]),
        base.be32(value["protocolFloor"]),
        base.ascii_bytes(value["clientIdentityFingerprint"]),
        base.ascii_bytes(value["runtimeIdentityFingerprint"]),
        base.ascii_bytes(value["sessionId"]),
        base.ascii_bytes(value["attemptId"]),
        base.ascii_bytes(value["requesterRole"]),
        base.ascii_bytes(value["requesterIdentityFingerprint"]),
        base.ascii_bytes(value["candidateOwnerRole"]),
        base.ascii_bytes(value["candidateOwnerIdentityFingerprint"]),
        base.ascii_bytes(value["candidateBatchDigest"]),
        base.be32(value["candidateBatchByteCount"]),
        base.be64(value["candidateBatchSequence"]),
        base.be64(value["candidateBatchExpiresAtMs"]),
        base.be64(value["maximumCandidateBytes"]),
        base.be32(value["maxOperations"]),
        base.ascii_bytes(value["singleUseNonce"]),
        base.be64(value["issuedAtMs"]),
        base.be64(value["notBeforeMs"]),
        base.be64(value["expiresAtMs"]),
        base.ascii_bytes(value["endpointOperationProofDigest"]),
        base.ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    claims = base.als1_encode(object_type, fields)
    operation_name = value["operation"].replace("_", "-")
    domain = f"AetherLink G1a-C {operation_name} capability service signature v1"
    purpose_bit = 1 << (2 if object_type == 23 else 3)
    signature, signature_meta = signature_record(
        "candidateCapability",
        domain,
        claims,
        scalar,
        value["operation"],
        purpose_bit,
    )
    canonical = base.als1_encode(object_type, fields + [signature])
    return canonical, base.object_record(
        object_type,
        "semantic",
        value,
        canonical,
        claims,
        [signature_meta],
    )


def operation_receipt_record(
    *,
    value: dict[str, Any],
    scalar: int,
) -> tuple[bytes, dict[str, Any]]:
    fields = [
        base.ascii_bytes(C1_SUITE),
        base.be64(1),
        base.ascii_bytes("committed"),
        base.ascii_bytes(value["serviceIdDigest"]),
        base.be64(value["keysetVersion"]),
        base.ascii_bytes(value["signingKeyId"]),
        base.ascii_bytes(value["pairAuthorityDigest"]),
        base.ascii_bytes(value["pairBindingDigest"]),
        base.be64(value["pairEpoch"]),
        base.be64(value["generation"]),
        base.be64(value["serviceConfigVersion"]),
        base.be64(value["revocationCounter"]),
        base.be32(value["protocolFloor"]),
        base.ascii_bytes(value["clientIdentityFingerprint"]),
        base.ascii_bytes(value["runtimeIdentityFingerprint"]),
        base.ascii_bytes(value["sessionId"]),
        base.ascii_bytes(value["attemptId"]),
        base.ascii_bytes(value["ledgerId"]),
        base.ascii_bytes(value["initiatorRole"]),
        base.ascii_bytes(value["operation"]),
        base.ascii_bytes(value["requesterRole"]),
        base.ascii_bytes(value["candidateOwnerRole"]),
        base.ascii_bytes(value["capabilityId"]),
        base.ascii_bytes(value["capabilityDigest"]),
        base.ascii_bytes(value["endpointOperationProofDigest"]),
        base.ascii_bytes(value["proofId"]),
        base.ascii_bytes(value["operationAuthorizationKind"]),
        base.ascii_bytes(value["operationAuthorizationDigest"]),
        base.ascii_bytes(value["requestDigest"]),
        base.ascii_bytes(value["singleUseNonce"]),
        base.ascii_bytes(value["candidateBatchDigest"]),
        base.be32(value["candidateBatchByteCount"]),
        base.be64(value["candidateBatchSequence"]),
        base.be64(value["candidateBatchExpiresAtMs"]),
        base.be32(1),
        base.be64(value["consumedBytes"]),
        base.ascii_bytes(value["resultDigest"]),
        base.be64(value["previousLedgerRevision"]),
        base.be64(value["committedLedgerRevision"]),
        base.ascii_bytes(value["previousLedgerStateCoreDigest"]),
        base.ascii_bytes(value["committedLedgerStateCoreDigest"]),
        base.ascii_bytes(value["commitRecordDigest"]),
        base.be64(value["committedAtMs"]),
        base.be64(value["issuedAtMs"]),
        base.be64(value["notBeforeMs"]),
        base.be64(value["expiresAtMs"]),
        base.ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    claims = base.als1_encode(28, fields)
    operation_name = value["operation"].replace("_", "-")
    domain = f"AetherLink G1a-C {operation_name} operation receipt service signature v1"
    purpose_bit = 1 << (4 if value["operation"] == "candidate_publish" else 5)
    signature, signature_meta = signature_record(
        "candidateReceipt",
        domain,
        claims,
        scalar,
        f"{value['operation']}_receipt",
        purpose_bit,
    )
    canonical = base.als1_encode(28, fields + [signature])
    return canonical, base.object_record(
        28,
        "semantic",
        value,
        canonical,
        claims,
        [signature_meta],
    )


def grant_evidence_bytes(value: dict[str, Any]) -> bytes:
    return base.als1_encode(
        25,
        [
            base.ascii_bytes(C1_SUITE),
            base.be64(1),
            base.ascii_bytes(value["serviceIdDigest"]),
            base.be64(value["keysetVersion"]),
            base.ascii_bytes(value["pairAuthorityDigest"]),
            base.ascii_bytes(value["pairBindingDigest"]),
            base.be64(value["pairEpoch"]),
            base.be64(value["generation"]),
            base.ascii_bytes(value["sessionId"]),
            base.ascii_bytes(value["attemptId"]),
            base.ascii_bytes(value["clientIdentityFingerprint"]),
            base.ascii_bytes(value["runtimeIdentityFingerprint"]),
            base.ascii_bytes(value["clientCandidateBatchDigest"]),
            base.be32(value["clientCandidateBatchByteCount"]),
            base.ascii_bytes(value["runtimeCandidateBatchDigest"]),
            base.be32(value["runtimeCandidateBatchByteCount"]),
            base.ascii_bytes(OPERATION_ORDER),
            b"".join(base.raw_digest(item) for item in value["operationCapabilityDigests"]),
            b"".join(base.raw_digest(item) for item in value["operationAuthorizationDigests"]),
            base.ascii_bytes(value["bilateralPublishDigest"]),
            base.ascii_bytes(value["bilateralFetchDigest"]),
            base.ascii_bytes(value["candidatePairDigest"]),
            base.ascii_bytes(value["pathValidationReceiptDigest"]),
            base.ascii_bytes(value["finalRouteAuthorizationDigest"]),
            base.ascii_bytes(value["c1RoutePlanClaimsDigest"]),
            base.ascii_bytes(value["c1RouteCapabilityDigest"]),
            b"".join(base.raw_digest(item) for item in value["operationReceiptDigests"]),
            base.ascii_bytes(value["initiatorRole"]),
            base.ascii_bytes(value["connectorTargetRole"]),
            base.ascii_bytes(value["destinationPolicyId"]),
            base.be64(value["destinationPolicyVersion"]),
            base.ascii_bytes(value["securityContextDigest"]),
            base.be64(value["effectiveNotBeforeMs"]),
            base.be64(value["expiresAtMs"]),
        ],
    )


def grant_authorization_bytes(value: dict[str, Any]) -> bytes:
    return base.als1_encode(
        26,
        [
            base.ascii_bytes(C1_SUITE),
            base.be64(1),
            base.ascii_bytes(value["grantEvidenceDigest"]),
            base.ascii_bytes(value["pairAuthorityDigest"]),
            base.ascii_bytes(value["pairBindingDigest"]),
            base.be64(value["pairEpoch"]),
            base.be64(value["generation"]),
            base.ascii_bytes(value["clientIdentityFingerprint"]),
            base.ascii_bytes(value["runtimeIdentityFingerprint"]),
            base.ascii_bytes(value["sessionId"]),
            base.ascii_bytes(value["attemptId"]),
            base.ascii_bytes(value["initiatorRole"]),
            base.ascii_bytes(value["connectorTargetRole"]),
            base.ascii_bytes(value["destinationPolicyId"]),
            base.be64(value["destinationPolicyVersion"]),
            base.ascii_bytes(value["securityContextDigest"]),
            base.be64(value["effectiveNotBeforeMs"]),
            base.be64(value["expiresAtMs"]),
        ],
    )


def _object_bytes(fixture: dict[str, Any], name: str) -> bytes:
    return bytes.fromhex(fixture["objects"][name]["expectedCanonicalHex"])


def _artifact_bytes(fixture: dict[str, Any], name: str) -> bytes:
    return bytes.fromhex(fixture["artifacts"][name]["expectedCanonicalHex"])


def _text(value: bytes) -> str:
    try:
        decoded = value.decode("ascii")
    except UnicodeDecodeError as error:
        raise CandidateVectorError("non-ASCII canonical text") from error
    require(decoded.encode("ascii") == value, "non-canonical text")
    return decoded


def _uint(value: bytes, size: int) -> int:
    require(len(value) == size, f"expected {size}-byte integer")
    return int.from_bytes(value, "big")


def _unpack_digests(value: bytes) -> list[str]:
    require(len(value) == 128, "packed digest list must be exactly 128 bytes")
    return [value[index : index + 32].hex() for index in range(0, 128, 32)]


def validate_legacy_fixture_invariant() -> None:
    base.validate_fixture_file(base.FIXTURE)
    actual = base.sha256_hex(base.FIXTURE.read_bytes())
    require(actual == LEGACY_FIXTURE_SHA256, "historical G1a-C fixture hash changed")


def _validate_key_records(fixture: dict[str, Any]) -> None:
    keys = fixture["keys"]
    require(set(keys) == set(KEY_SCALARS), "candidate key set mismatch")
    for name, scalar in KEY_SCALARS.items():
        expected = base.key_record(name, scalar)
        require(keys[name] == expected, f"{name}: deterministic key record mismatch")
        require(expected["keyId"] == EXPECTED_KEY_IDS[name], f"{name}: pinned key ID mismatch")


def _validate_signature_profiles(fixture: dict[str, Any]) -> None:
    unsigned = {
        "authority",
        "preauthorizationSessionContext",
        "p2pConnector",
        "p2pRoutePlan",
        "finalP2PDirectAuthorization",
        "p2pGrantEvidence",
        "p2pGrantAuthorization",
        "candidateSecureSessionTranscript",
    }
    expected: dict[str, list[tuple[str, str, str, int | None]]] = {
        name: [] for name in unsigned
    }
    expected["serviceKeyset"] = [
        (
            "root",
            "AetherLink G1a-C service-keyset root signature v1",
            "service_keyset_root",
            None,
        )
    ]
    expected["p2pRouteCapability"] = [
        (
            "route",
            "AetherLink G1a-C route-capability service signature v1",
            "route_capability",
            0x02,
        )
    ]
    for spec in OPERATION_SPECS:
        suffix = f"{spec['id'][0].upper()}{spec['id'][1:]}"
        expected[f"endpointProof{suffix}"] = [
            (
                spec["identityKey"],
                "AetherLink G1a-C endpoint-authenticated candidate operation v1",
                "endpoint_long_term_identity",
                None,
            )
        ]
        operation_word = "publish" if spec["operation"] == "candidate_publish" else "fetch"
        expected[f"capability{suffix}"] = [
            (
                "candidateCapability",
                f"AetherLink G1a-C candidate-{operation_word} capability service signature v1",
                spec["operation"],
                spec["capabilityPurpose"],
            )
        ]
        expected[f"authorization{suffix}"] = []
        expected[f"receipt{suffix}"] = [
            (
                "candidateReceipt",
                f"AetherLink G1a-C candidate-{operation_word} operation receipt service signature v1",
                f"candidate_{operation_word}_receipt",
                spec["receiptPurpose"],
            )
        ]

    require(set(fixture["objects"]) == set(expected), "object inventory mismatch")
    for name, profiles in expected.items():
        signatures = fixture["objects"][name].get("signatures", [])
        require(len(signatures) == len(profiles), f"{name}: signature count")
        for metadata, profile in zip(signatures, profiles):
            actual = (
                metadata.get("signer"),
                metadata.get("signingDomain"),
                metadata.get("requiredPurpose"),
                metadata.get("requiredPurposeBit"),
            )
            require(actual == profile, f"{name}: signature profile")


def _validate_canonical_records(fixture: dict[str, Any]) -> None:
    keys = fixture["keys"]
    for name, record in fixture["objects"].items():
        canonical = bytes.fromhex(record["expectedCanonicalHex"])
        object_type = record["objectType"]
        require(canonical[:4] == ALS1_MAGIC, f"{name}: wrong magic")
        require(canonical[4] == object_type, f"{name}: wrong object type")
        require(canonical[5] == VERSION, f"{name}: wrong version")
        require(object_type in FIELD_COUNTS, f"{name}: unsupported object type")
        require(len(canonical) <= MAXIMUM_OBJECT_BYTES[object_type], f"{name}: size limit")
        require(record["expectedCanonicalByteCount"] == len(canonical), f"{name}: byte count")
        require(record["expectedSha256Hex"] == base.sha256_hex(canonical), f"{name}: digest")
        fields = base.als1_decode(canonical, object_type, FIELD_COUNTS[object_type])
        signatures = record.get("signatures", [])
        if signatures:
            claims = bytes.fromhex(record["expectedClaimsCanonicalHex"])
            require(
                base.als1_encode(object_type, fields[: -len(signatures)]) == claims,
                f"{name}: signed claims mismatch",
            )
            for metadata, signature in zip(signatures, fields[-len(signatures) :]):
                transcript = base.signature_transcript(metadata["signingDomain"], claims)
                require(metadata["expectedSigningTranscriptHex"] == transcript.hex(), f"{name}: transcript")
                require(
                    metadata["expectedSigningTranscriptSha256Hex"] == base.sha256_hex(transcript),
                    f"{name}: transcript digest",
                )
                require(metadata["fixedLowSDERSignatureHex"] == signature.hex(), f"{name}: signature")
                base.der_decode_signature(signature, require_low_s=True)
                public_key = bytes.fromhex(keys[metadata["signer"]]["publicKeyX963Hex"])
                base.ecdsa_verify(public_key, transcript, signature)

    for name, record in fixture["artifacts"].items():
        canonical = bytes.fromhex(record["expectedCanonicalHex"])
        require(record["magic"] == "ALP1", f"{name}: artifact magic metadata")
        require(record["expectedCanonicalByteCount"] == len(canonical), f"{name}: byte count")
        require(record["expectedSha256Hex"] == base.sha256_hex(canonical), f"{name}: digest")
        field_count = 6 if record["objectType"] == 1 else 8
        alp1_decode(canonical, record["objectType"], field_count)


def _parse_delegated_keyset(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = base.als1_decode(_object_bytes(fixture, "serviceKeyset"), 10, 11)
    require(_text(fields[0]) == C1_SUITE, "keyset suite")
    require(_text(fields[1]) == fixture["identifiers"]["serviceIdDigest"], "keyset service")
    require(_uint(fields[2], 8) == 1, "keyset version")
    require(_text(fields[3]) == "none", "keyset predecessor")
    require(_uint(fields[4], 8) == KEYSET_NOT_BEFORE_MS, "keyset issued")
    require(_uint(fields[5], 8) == KEYSET_EXPIRES_AT_MS, "keyset expiry")
    require(_text(fields[6]) == EXPECTED_KEY_IDS["root"], "keyset root")
    count = _uint(fields[7], 4)
    packed = fields[8]
    record_size = 8 + 32 + 4 + 8 + 8 + 8 + 65
    require(count == 3 and len(packed) == count * record_size, "delegated key count")
    result: dict[str, dict[str, Any]] = {}
    previous_key_id = ""
    for index in range(count):
        cursor = index * record_size
        version = _uint(packed[cursor : cursor + 8], 8)
        cursor += 8
        key_id = packed[cursor : cursor + 32].hex()
        cursor += 32
        purposes = _uint(packed[cursor : cursor + 4], 4)
        cursor += 4
        not_before = _uint(packed[cursor : cursor + 8], 8)
        cursor += 8
        expires = _uint(packed[cursor : cursor + 8], 8)
        cursor += 8
        revoked = _uint(packed[cursor : cursor + 8], 8)
        cursor += 8
        public_x963 = packed[cursor : cursor + 65]
        require(previous_key_id < key_id, "delegated keys not key-ID sorted")
        previous_key_id = key_id
        result[key_id] = {
            "version": version,
            "purposes": purposes,
            "notBeforeMs": not_before,
            "expiresAtMs": expires,
            "revokedAtMs": revoked,
            "publicKeyX963": public_x963,
        }
    expected = {
        EXPECTED_KEY_IDS["route"]: (0x02, "route"),
        EXPECTED_KEY_IDS["candidateCapability"]: (0x0C, "candidateCapability"),
        EXPECTED_KEY_IDS["candidateReceipt"]: (0x30, "candidateReceipt"),
    }
    require(set(result) == set(expected), "delegated key IDs")
    for key_id, (purposes, key_name) in expected.items():
        item = result[key_id]
        require(item["version"] == 1, "delegated version")
        require(item["purposes"] == purposes, "delegated purpose")
        require(item["notBeforeMs"] == KEYSET_NOT_BEFORE_MS, "delegated not-before")
        require(item["expiresAtMs"] == KEYSET_EXPIRES_AT_MS, "delegated expiry")
        require(item["revokedAtMs"] == 0, "delegated revocation")
        require(
            item["publicKeyX963"] == bytes.fromhex(fixture["keys"][key_name]["publicKeyX963Hex"]),
            "delegated public key",
        )
    return result


def _validate_usage_state(state: dict[str, Any]) -> None:
    require(state["revision"] > 0, "usage revision")
    require(state["retentionLimit"] > 0, "usage retention")
    entries = state["entries"]
    require(len(entries) <= state["retentionLimit"], "usage retention exceeded")
    for key in ("requestId", "singleUseNonce", "capabilityDigest", "receiptDigest"):
        require(len({entry[key] for entry in entries}) == len(entries), f"duplicate usage {key}")
    previous_revision = 0
    for entry in entries:
        for key in (
            "requestId",
            "requestDigest",
            "capabilityDigest",
            "authorizationDigest",
            "singleUseNonce",
            "receiptDigest",
        ):
            base.raw_digest(entry[key])
        require(entry["consumedBytes"] > 0, "zero usage bytes")
        require(previous_revision < entry["committedRevision"] <= state["revision"], "usage revision order")
        previous_revision = entry["committedRevision"]
    require(state["snapshotDigestHex"] == usage_snapshot_digest(state), "usage snapshot digest")


def _validate_semantics(fixture: dict[str, Any]) -> None:
    identifiers = fixture["identifiers"]
    keys = fixture["keys"]
    delegated = _parse_delegated_keyset(fixture)

    authority_fields = base.als1_decode(_object_bytes(fixture, "authority"), 8, 16)
    authority_digest = base.sha256_hex(_object_bytes(fixture, "authority"))
    require(_text(authority_fields[0]) == SECURE_SUITE, "authority suite")
    require(_text(authority_fields[1]) == identifiers["pairBindingDigest"], "authority pair")
    require(_uint(authority_fields[2], 8) == 1, "authority epoch")
    require(_text(authority_fields[3]) == EXPECTED_KEY_IDS["clientIdentity"], "authority client")
    require(_text(authority_fields[4]) == EXPECTED_KEY_IDS["runtimeIdentity"], "authority runtime")
    require(_uint(authority_fields[5], 8) == 1, "authority generation")
    require(_uint(authority_fields[6], 8) == 1, "authority service config")
    require(_uint(authority_fields[7], 8) == 1, "authority keyset")
    require(_uint(authority_fields[8], 8) == 0, "authority revocation")
    require(_uint(authority_fields[9], 4) == 1, "authority protocol floor")
    require(_text(authority_fields[11]) == "active", "authority status")
    require(_uint(authority_fields[15], 8) == 1, "authority revision")
    require(authority_digest == fixture["derived"]["pairAuthorityDigest"], "authority digest")

    context_bytes = _object_bytes(fixture, "preauthorizationSessionContext")
    context_fields = base.als1_decode(context_bytes, 18, 21)
    context_digest = base.sha256_hex(context_bytes)
    require(_text(context_fields[0]) == C1_SUITE and _uint(context_fields[1], 8) == 1, "context header")
    require(_text(context_fields[2]) == identifiers["sessionId"], "context session")
    require(_text(context_fields[3]) == identifiers["pairBindingDigest"], "context pair")
    require(_uint(context_fields[4], 8) == 1, "context epoch")
    require(_text(context_fields[5]) == EXPECTED_KEY_IDS["clientIdentity"], "context client")
    require(_text(context_fields[6]) == EXPECTED_KEY_IDS["runtimeIdentity"], "context runtime")
    require(_text(context_fields[7]) == "client" and _text(context_fields[8]) == "runtime", "context roles")
    require(context_fields[9] == bytes.fromhex(keys["clientEphemeral"]["publicKeyX963Hex"]), "context client key")
    require(context_fields[10] == bytes.fromhex(keys["runtimeEphemeral"]["publicKeyX963Hex"]), "context runtime key")
    require(_text(context_fields[11]) == labeled_short_hex("candidate-vector-client-nonce"), "context client nonce")
    require(_text(context_fields[12]) == labeled_short_hex("candidate-vector-runtime-nonce"), "context runtime nonce")
    require(_uint(context_fields[13], 8) == 1, "context generation")
    require(_uint(context_fields[14], 8) == 1 and _uint(context_fields[15], 8) == 1, "context config/keyset")
    require(_uint(context_fields[16], 8) == 0, "context revocation")
    require(_uint(context_fields[17], 4) == 1 and _uint(context_fields[18], 4) == 1, "context protocol")
    require(_text(context_fields[19]) == PROFILE, "context profile")
    require(_text(context_fields[20]) == P2P_KIND, "context route kind")
    require(context_digest == fixture["derived"]["securityContextDigest"], "context digest")

    batch_info: dict[str, dict[str, Any]] = {}
    for name, expected_role, expected_sequence, expected_address, expected_size in (
        ("clientCandidateBatch", "client", 1, bytes((1, 1, 1, 1)), 122),
        ("runtimeCandidateBatch", "runtime", 2, bytes((8, 8, 4, 4)), 123),
    ):
        canonical = _artifact_bytes(fixture, name)
        fields = alp1_decode(canonical, 1, 6)
        require(_text(fields[0]) == identifiers["sessionId"], f"{name}: session")
        require(_uint(fields[1], 8) == 1, f"{name}: generation")
        require(_uint(fields[2], 8) == expected_sequence, f"{name}: sequence")
        require(_uint(fields[3], 8) == BATCH_EXPIRES_AT_MS, f"{name}: expiry")
        require(_text(fields[4]) == expected_role, f"{name}: role")
        require(_uint(fields[5][:2], 2) == 1, f"{name}: candidate count")
        encoded_candidate = fields[5][2:]
        require(encoded_candidate == candidate_bytes(sequence=expected_sequence, address=expected_address), f"{name}: candidate")
        require(len(canonical) == expected_size, f"{name}: canonical size")
        batch_info[name] = {
            "bytes": canonical,
            "digest": base.sha256_hex(canonical),
            "sequence": expected_sequence,
            "role": expected_role,
            "candidate": encoded_candidate,
        }

    operations = fixture["operations"]
    require([item["wireName"] for item in operations] == [item["wireName"] for item in OPERATION_SPECS], "operation order")
    capability_digests: list[str] = []
    authorization_digests: list[str] = []
    proof_ids: list[str] = []
    capability_ids: list[str] = []
    nonces: list[str] = []
    parsed_operations: list[dict[str, Any]] = []
    for spec, operation in zip(OPERATION_SPECS, operations):
        require(operation["wireName"] == spec["wireName"], "operation metadata")
        proof_name = operation["endpointProofObject"]
        capability_name = operation["capabilityObject"]
        authorization_name = operation["authorizationObject"]
        proof_bytes = _object_bytes(fixture, proof_name)
        capability_bytes = _object_bytes(fixture, capability_name)
        authorization_bytes = _object_bytes(fixture, authorization_name)
        proof = base.als1_decode(proof_bytes, 27, 24)
        capability = base.als1_decode(capability_bytes, spec["objectType"], 34)
        authorization = base.als1_decode(
            authorization_bytes,
            spec["authorizationObjectType"],
            6,
        )
        proof_digest = base.sha256_hex(proof_bytes)
        capability_digest = base.sha256_hex(capability_bytes)
        authorization_digest = base.sha256_hex(authorization_bytes)
        batch = batch_info[spec["batch"]]
        requester_identity = EXPECTED_KEY_IDS[spec["identityKey"]]
        owner_identity = EXPECTED_KEY_IDS[f"{spec['candidateOwnerRole']}Identity"]

        require(_text(proof[0]) == C1_SUITE and _uint(proof[1], 8) == 1, f"{proof_name}: header")
        require(_text(proof[2]) == spec["requesterRole"], f"{proof_name}: requester")
        require(_text(proof[3]) == requester_identity, f"{proof_name}: requester identity")
        require(proof[4] == bytes.fromhex(keys[spec["identityKey"]]["publicKeyX963Hex"]), f"{proof_name}: endpoint key")
        _, _, endpoint_key_id = base.public_material(KEY_SCALARS[spec["identityKey"]])
        require(endpoint_key_id == _text(proof[3]), f"{proof_name}: endpoint key ID")
        require(_text(proof[5]) == spec["operation"], f"{proof_name}: operation")
        require(_text(proof[6]) == spec["candidateOwnerRole"], f"{proof_name}: owner")
        require(_text(proof[7]) == owner_identity, f"{proof_name}: owner identity")
        require(_text(proof[8]) == identifiers["sessionId"], f"{proof_name}: session")
        require(_text(proof[9]) == identifiers["attemptId"], f"{proof_name}: attempt")
        require(_text(proof[11]) == batch["digest"], f"{proof_name}: batch digest")
        require(_uint(proof[12], 8) == batch["sequence"], f"{proof_name}: batch sequence")
        require(_text(proof[14]) == context_digest, f"{proof_name}: context")
        require(_uint(proof[15], 8) == PROOF_ISSUED_AT_MS, f"{proof_name}: issued")
        require(_uint(proof[16], 8) == OPERATION_NOT_BEFORE_MS, f"{proof_name}: not-before")
        require(_uint(proof[17], 8) == OPERATION_EXPIRES_AT_MS, f"{proof_name}: expiry")
        require(_text(proof[19]) == authority_digest, f"{proof_name}: authority")
        require(_text(proof[20]) == identifiers["serviceIdDigest"], f"{proof_name}: audience")
        require(_text(proof[21]) == "client", f"{proof_name}: initiator")
        require(_text(proof[22]) == SIGNATURE_ALGORITHM, f"{proof_name}: algorithm")

        require(_text(capability[0]) == C1_SUITE, f"{capability_name}: suite")
        require(_text(capability[1]) == spec["operation"], f"{capability_name}: operation")
        require(_text(capability[2]) == identifiers["serviceIdDigest"], f"{capability_name}: service")
        require(_uint(capability[3], 8) == 1, f"{capability_name}: keyset")
        require(_text(capability[4]) == EXPECTED_KEY_IDS["candidateCapability"], f"{capability_name}: signer")
        require(_text(capability[5]) == _text(proof[10]), f"{capability_name}: capability ID")
        require(_text(capability[6]) == authority_digest, f"{capability_name}: authority")
        require(_text(capability[7]) == identifiers["pairBindingDigest"], f"{capability_name}: pair")
        require(_uint(capability[8], 8) == 1 and _uint(capability[9], 8) == 1, f"{capability_name}: epoch/generation")
        require(_uint(capability[10], 8) == 1 and _uint(capability[11], 8) == 0, f"{capability_name}: config")
        require(_uint(capability[12], 4) == 1, f"{capability_name}: protocol")
        require(_text(capability[13]) == EXPECTED_KEY_IDS["clientIdentity"], f"{capability_name}: client")
        require(_text(capability[14]) == EXPECTED_KEY_IDS["runtimeIdentity"], f"{capability_name}: runtime")
        require(_text(capability[15]) == identifiers["sessionId"], f"{capability_name}: session")
        require(_text(capability[16]) == identifiers["attemptId"], f"{capability_name}: attempt")
        require(_text(capability[17]) == spec["requesterRole"], f"{capability_name}: requester")
        require(_text(capability[18]) == requester_identity, f"{capability_name}: requester identity")
        require(_text(capability[19]) == spec["candidateOwnerRole"], f"{capability_name}: owner")
        require(_text(capability[20]) == owner_identity, f"{capability_name}: owner identity")
        require(_text(capability[21]) == batch["digest"], f"{capability_name}: batch")
        require(_uint(capability[22], 4) == len(batch["bytes"]), f"{capability_name}: batch bytes")
        require(_uint(capability[23], 8) == batch["sequence"], f"{capability_name}: batch sequence")
        require(_uint(capability[24], 8) == BATCH_EXPIRES_AT_MS, f"{capability_name}: batch expiry")
        require(_uint(capability[25], 8) == MAXIMUM_CANDIDATE_BYTES, f"{capability_name}: maximum bytes")
        require(_uint(capability[26], 4) == 1, f"{capability_name}: max operations")
        require(_text(capability[27]) == _text(proof[13]), f"{capability_name}: nonce")
        require(_uint(capability[28], 8) == CAPABILITY_ISSUED_AT_MS, f"{capability_name}: issued")
        require(_uint(capability[29], 8) == OPERATION_NOT_BEFORE_MS, f"{capability_name}: not-before")
        require(_uint(capability[30], 8) == OPERATION_EXPIRES_AT_MS, f"{capability_name}: expiry")
        require(_text(capability[31]) == proof_digest, f"{capability_name}: proof digest")
        require(_text(capability[32]) == SIGNATURE_ALGORITHM, f"{capability_name}: algorithm")
        require(
            delegated[EXPECTED_KEY_IDS["candidateCapability"]]["purposes"] & spec["capabilityPurpose"],
            f"{capability_name}: key purpose",
        )

        require(_text(authorization[0]) == SECURE_SUITE, f"{authorization_name}: suite")
        require(_text(authorization[1]) == identifiers["pairBindingDigest"], f"{authorization_name}: pair")
        require(_uint(authorization[2], 8) == 1 and _uint(authorization[3], 8) == 1, f"{authorization_name}: epoch/generation")
        require(_text(authorization[4]) == batch["digest"], f"{authorization_name}: batch")
        require(_text(authorization[5]) == capability_digest, f"{authorization_name}: capability")

        proof_id = _text(proof[18])
        capability_id = _text(capability[5])
        nonce = _text(capability[27])
        proof_ids.append(proof_id)
        capability_ids.append(capability_id)
        nonces.append(nonce)
        capability_digests.append(capability_digest)
        authorization_digests.append(authorization_digest)
        parsed_operations.append(
            {
                "spec": spec,
                "proof": proof,
                "proofDigest": proof_digest,
                "capability": capability,
                "capabilityDigest": capability_digest,
                "authorization": authorization,
                "authorizationDigest": authorization_digest,
                "batch": batch,
            }
        )

    for name, values in (("proof IDs", proof_ids), ("capability IDs", capability_ids), ("nonces", nonces), ("capability digests", capability_digests), ("authorization digests", authorization_digests)):
        require(len(set(values)) == 4, f"duplicate {name}")

    expected_publish = bilateral_digest(
        "AetherLink G1a-C bilateral candidate-publish set v1",
        capability_digests[0],
        capability_digests[2],
    )
    expected_fetch = bilateral_digest(
        "AetherLink G1a-C bilateral candidate-fetch set v1",
        capability_digests[3],
        capability_digests[1],
    )
    require(expected_publish == fixture["derived"]["bilateralPublishDigest"], "bilateral publish")
    require(expected_fetch == fixture["derived"]["bilateralFetchDigest"], "bilateral fetch order")

    selected_pair = selected_candidate_pair_digest(
        batch_info["clientCandidateBatch"]["candidate"],
        batch_info["runtimeCandidateBatch"]["candidate"],
    )
    require(selected_pair == fixture["derived"]["candidatePairDigest"], "selected candidate pair")
    path_bytes = _artifact_bytes(fixture, "pathValidationReceipt")
    path = alp1_decode(path_bytes, 5, 8)
    path_digest = base.sha256_hex(path_bytes)
    require(_text(path[0]) == identifiers["sessionId"], "path session")
    require(_uint(path[1], 8) == 1, "path generation")
    require(_text(path[2]) == selected_pair, "path candidate pair")
    require(_text(path[3]) == "direct", "path transport")
    require(_uint(path[6], 8) == PATH_VALIDATED_AT_MS, "path validation time")
    require(_uint(path[7], 8) == PATH_EXPIRES_AT_MS, "path expiry")
    require(path_digest == fixture["derived"]["pathValidationReceiptDigest"], "path digest")

    connector_bytes = _object_bytes(fixture, "p2pConnector")
    connector = base.als1_decode(connector_bytes, 15, 11)
    require(_text(connector[0]) == C1_SUITE and _text(connector[1]) == P2P_KIND, "connector kind")
    require(connector[2] == bytes((8, 8, 4, 4)) and _uint(connector[3], 2) == 50_000, "connector destination")
    require(_text(connector[4]) == "none" and _text(connector[5]) == "udp", "connector transport")
    require(_text(connector[8]) == path_digest, "connector path")

    plan_bytes = _object_bytes(fixture, "p2pRoutePlan")
    plan = base.als1_decode(plan_bytes, 14, 15)
    plan_digest = base.sha256_hex(plan_bytes)
    require(_text(plan[0]) == C1_SUITE and _uint(plan[2], 8) == 1, "plan header")
    require(_text(plan[3]) == P2P_KIND, "plan kind")
    require(_text(plan[4]) == authority_digest and _text(plan[5]) == identifiers["pairBindingDigest"], "plan authority")
    require(plan[10] == connector_bytes, "plan connector")
    require(_text(plan[11]) == context_digest and _text(plan[12]) == path_digest, "plan context/path")
    require(_uint(plan[13], 8) == PLAN_NOT_BEFORE_MS and _uint(plan[14], 8) == PLAN_EXPIRES_AT_MS, "plan window")

    route_capability_bytes = _object_bytes(fixture, "p2pRouteCapability")
    route_capability = base.als1_decode(route_capability_bytes, 13, 22)
    route_capability_digest = base.sha256_hex(route_capability_bytes)
    require(_text(route_capability[0]) == C1_SUITE, "route capability suite")
    require(_text(route_capability[1]) == identifiers["serviceIdDigest"], "route capability service")
    require(_text(route_capability[3]) == EXPECTED_KEY_IDS["route"], "route capability signer")
    require(_text(route_capability[8]) == authority_digest, "route capability authority")
    require(_text(route_capability[17]) == P2P_KIND, "route capability kind")
    require(_text(route_capability[18]) == plan_digest, "route capability plan")
    require(_uint(route_capability[19], 4) == 1, "route capability uses")
    require(delegated[EXPECTED_KEY_IDS["route"]]["purposes"] & 0x02, "route key purpose")

    final_authorization_bytes = _object_bytes(fixture, "finalP2PDirectAuthorization")
    final_authorization = base.als1_decode(final_authorization_bytes, 4, 8)
    final_authorization_digest = base.sha256_hex(final_authorization_bytes)
    require(_text(final_authorization[0]) == SECURE_SUITE, "final authorization suite")
    require(_text(final_authorization[4]) == selected_pair, "final candidate pair")
    require(_text(final_authorization[5]) == path_digest, "final path")
    require(_text(final_authorization[6]) == expected_publish, "final publish")
    require(_text(final_authorization[7]) == expected_fetch, "final fetch")

    usage = fixture["usageLedger"]
    states = [usage["initialState"]] + usage["committedStates"]
    require(len(states) == 5, "usage state count")
    for state in states:
        _validate_usage_state(state)
    require(states[0]["revision"] == 1, "initial usage revision")
    require(states[0]["remainingOperations"] == 4, "initial usage operations")
    require(states[0]["remainingBytes"] == 490, "initial usage bytes")
    require(states[0]["retentionLimit"] == 8 and not states[0]["entries"], "initial usage retention")

    receipt_digests: list[str] = []
    ledger_id = usage["ledgerId"]
    for index, parsed in enumerate(parsed_operations):
        operation = operations[index]
        receipt_name = operation["receiptObject"]
        receipt_bytes = _object_bytes(fixture, receipt_name)
        receipt = base.als1_decode(receipt_bytes, 28, 48)
        receipt_digest = base.sha256_hex(receipt_bytes)
        receipt_digests.append(receipt_digest)
        previous_state = states[index]
        committed_state = states[index + 1]
        spec = parsed["spec"]
        proof = parsed["proof"]
        capability = parsed["capability"]
        expected_request = request_digest(
            _text(proof[18]),
            parsed["capabilityDigest"],
            parsed["authorizationDigest"],
        )
        expected_result = usage_result_digest(
            proof_id=_text(proof[18]),
            request_digest_value=expected_request,
            capability_digest=parsed["capabilityDigest"],
            authorization_digest=parsed["authorizationDigest"],
            single_use_nonce=_text(capability[27]),
            consumed_bytes=len(parsed["batch"]["bytes"]),
            previous_revision=previous_state["revision"],
            committed_revision=committed_state["revision"],
        )
        require(_text(receipt[0]) == C1_SUITE and _uint(receipt[1], 8) == 1, f"{receipt_name}: header")
        require(_text(receipt[2]) == "committed", f"{receipt_name}: status")
        require(_text(receipt[3]) == identifiers["serviceIdDigest"], f"{receipt_name}: service")
        require(_uint(receipt[4], 8) == 1, f"{receipt_name}: keyset")
        require(_text(receipt[5]) == EXPECTED_KEY_IDS["candidateReceipt"], f"{receipt_name}: signer")
        require(_text(receipt[6]) == authority_digest and _text(receipt[7]) == identifiers["pairBindingDigest"], f"{receipt_name}: authority")
        require(_uint(receipt[8], 8) == 1 and _uint(receipt[9], 8) == 1, f"{receipt_name}: epoch/generation")
        require(_uint(receipt[10], 8) == 1 and _uint(receipt[11], 8) == 0, f"{receipt_name}: config/revocation")
        require(_uint(receipt[12], 4) == 1, f"{receipt_name}: protocol")
        require(_text(receipt[13]) == EXPECTED_KEY_IDS["clientIdentity"], f"{receipt_name}: client identity")
        require(_text(receipt[14]) == EXPECTED_KEY_IDS["runtimeIdentity"], f"{receipt_name}: runtime identity")
        require(_text(receipt[15]) == identifiers["sessionId"] and _text(receipt[16]) == identifiers["attemptId"], f"{receipt_name}: session")
        require(_text(receipt[17]) == ledger_id, f"{receipt_name}: ledger")
        require(_text(receipt[18]) == "client", f"{receipt_name}: initiator")
        require(_text(receipt[19]) == spec["operation"], f"{receipt_name}: operation")
        require(_text(receipt[20]) == spec["requesterRole"] and _text(receipt[21]) == spec["candidateOwnerRole"], f"{receipt_name}: roles")
        require(_text(receipt[22]) == _text(capability[5]), f"{receipt_name}: capability ID")
        require(_text(receipt[23]) == parsed["capabilityDigest"], f"{receipt_name}: capability digest")
        require(_text(receipt[24]) == parsed["proofDigest"], f"{receipt_name}: proof digest")
        require(_text(receipt[25]) == _text(proof[18]), f"{receipt_name}: proof ID")
        require(_text(receipt[26]) == spec["authorizationKind"], f"{receipt_name}: auth kind")
        require(_text(receipt[27]) == parsed["authorizationDigest"], f"{receipt_name}: auth digest")
        require(_text(receipt[28]) == expected_request, f"{receipt_name}: request digest")
        require(_text(receipt[29]) == _text(capability[27]), f"{receipt_name}: nonce")
        require(_text(receipt[30]) == parsed["batch"]["digest"], f"{receipt_name}: batch digest")
        require(_uint(receipt[31], 4) == len(parsed["batch"]["bytes"]), f"{receipt_name}: batch bytes")
        require(_uint(receipt[32], 8) == parsed["batch"]["sequence"], f"{receipt_name}: batch sequence")
        require(_uint(receipt[33], 8) == BATCH_EXPIRES_AT_MS, f"{receipt_name}: batch expiry")
        require(_uint(receipt[34], 4) == 1, f"{receipt_name}: operations")
        require(_uint(receipt[35], 8) == len(parsed["batch"]["bytes"]), f"{receipt_name}: consumed bytes")
        require(_text(receipt[36]) == expected_result, f"{receipt_name}: result")
        require(_uint(receipt[37], 8) == previous_state["revision"], f"{receipt_name}: previous revision")
        require(_uint(receipt[38], 8) == committed_state["revision"], f"{receipt_name}: committed revision")
        require(_text(receipt[39]) == previous_state["snapshotDigestHex"], f"{receipt_name}: previous state")
        require(_text(receipt[40]) == committed_state["snapshotDigestHex"], f"{receipt_name}: committed state")
        require(_text(receipt[41]) == labeled_digest(f"candidate-commit-{index}"), f"{receipt_name}: commit record")
        require(_uint(receipt[42], 8) == NOW_MS and _uint(receipt[43], 8) == NOW_MS, f"{receipt_name}: commit/issue")
        require(_uint(receipt[44], 8) == NOW_MS and _uint(receipt[45], 8) == RECEIPT_EXPIRES_AT_MS, f"{receipt_name}: window")
        require(_text(receipt[46]) == SIGNATURE_ALGORITHM, f"{receipt_name}: algorithm")
        require(
            delegated[EXPECTED_KEY_IDS["candidateReceipt"]]["purposes"] & spec["receiptPurpose"],
            f"{receipt_name}: key purpose",
        )
        entry = committed_state["entries"][-1]
        require(entry["requestId"] == _text(proof[18]), f"{receipt_name}: ledger request")
        require(entry["receiptDigest"] == expected_result, f"{receipt_name}: ledger result")
        require(committed_state["entries"] == previous_state["entries"] + [entry], f"{receipt_name}: ledger append")
        require(committed_state["remainingOperations"] == previous_state["remainingOperations"] - 1, f"{receipt_name}: operation quota")
        require(committed_state["remainingBytes"] == previous_state["remainingBytes"] - len(parsed["batch"]["bytes"]), f"{receipt_name}: byte quota")

    require(len(set(receipt_digests)) == 4, "duplicate receipt digests")
    require([state["revision"] for state in states] == [1, 2, 3, 4, 5], "usage revision chain")

    grant_bytes = _object_bytes(fixture, "p2pGrantEvidence")
    grant = base.als1_decode(grant_bytes, 25, 34)
    grant_digest = base.sha256_hex(grant_bytes)
    require(_text(grant[0]) == C1_SUITE and _uint(grant[1], 8) == 1, "grant header")
    require(_text(grant[2]) == identifiers["serviceIdDigest"], "grant service")
    require(_uint(grant[3], 8) == 1, "grant keyset")
    require(_text(grant[4]) == authority_digest and _text(grant[5]) == identifiers["pairBindingDigest"], "grant authority")
    require(_uint(grant[6], 8) == 1 and _uint(grant[7], 8) == 1, "grant epoch/generation")
    require(_text(grant[8]) == identifiers["sessionId"] and _text(grant[9]) == identifiers["attemptId"], "grant session")
    require(_text(grant[10]) == EXPECTED_KEY_IDS["clientIdentity"], "grant client identity")
    require(_text(grant[11]) == EXPECTED_KEY_IDS["runtimeIdentity"], "grant runtime identity")
    require(_text(grant[12]) == batch_info["clientCandidateBatch"]["digest"], "grant client batch")
    require(_uint(grant[13], 4) == 122, "grant client bytes")
    require(_text(grant[14]) == batch_info["runtimeCandidateBatch"]["digest"], "grant runtime batch")
    require(_uint(grant[15], 4) == 123, "grant runtime bytes")
    require(_text(grant[16]) == OPERATION_ORDER, "grant operation order")
    require(_unpack_digests(grant[17]) == capability_digests, "grant capability digest order")
    require(_unpack_digests(grant[18]) == authorization_digests, "grant authorization digest order")
    require(_text(grant[19]) == expected_publish and _text(grant[20]) == expected_fetch, "grant bilateral digests")
    require(_text(grant[21]) == selected_pair and _text(grant[22]) == path_digest, "grant path")
    require(_text(grant[23]) == final_authorization_digest, "grant final authorization")
    require(_text(grant[24]) == plan_digest, "grant plan")
    require(_text(grant[25]) == route_capability_digest, "grant route capability")
    require(_unpack_digests(grant[26]) == receipt_digests, "grant receipt digest order")
    require(_text(grant[27]) == "client" and _text(grant[28]) == "runtime", "grant roles")
    require(_text(grant[29]) == DESTINATION_POLICY_ID and _uint(grant[30], 8) == 1, "grant policy")
    require(_text(grant[31]) == context_digest, "grant context")
    require(_uint(grant[32], 8) == NOW_MS and _uint(grant[33], 8) == PLAN_EXPIRES_AT_MS, "grant window")
    require(grant_digest == fixture["derived"]["grantEvidenceDigest"], "grant digest")

    grant_authorization_bytes_value = _object_bytes(fixture, "p2pGrantAuthorization")
    grant_authorization = base.als1_decode(grant_authorization_bytes_value, 26, 18)
    grant_authorization_digest = base.sha256_hex(grant_authorization_bytes_value)
    require(_text(grant_authorization[0]) == C1_SUITE and _uint(grant_authorization[1], 8) == 1, "grant authorization header")
    require(_text(grant_authorization[2]) == grant_digest, "grant authorization evidence")
    require(_text(grant_authorization[3]) == authority_digest and _text(grant_authorization[4]) == identifiers["pairBindingDigest"], "grant authorization authority")
    require(_uint(grant_authorization[5], 8) == 1 and _uint(grant_authorization[6], 8) == 1, "grant authorization epoch/generation")
    require(_text(grant_authorization[7]) == EXPECTED_KEY_IDS["clientIdentity"], "grant authorization client identity")
    require(_text(grant_authorization[8]) == EXPECTED_KEY_IDS["runtimeIdentity"], "grant authorization runtime identity")
    require(_text(grant_authorization[9]) == identifiers["sessionId"] and _text(grant_authorization[10]) == identifiers["attemptId"], "grant authorization session")
    require(_text(grant_authorization[11]) == "client" and _text(grant_authorization[12]) == "runtime", "grant authorization roles")
    require(_text(grant_authorization[13]) == DESTINATION_POLICY_ID and _uint(grant_authorization[14], 8) == 1, "grant authorization policy")
    require(_text(grant_authorization[15]) == context_digest, "grant authorization context")
    require(_uint(grant_authorization[16], 8) == NOW_MS and _uint(grant_authorization[17], 8) == PLAN_EXPIRES_AT_MS, "grant authorization window")
    require(grant_authorization_digest == fixture["derived"]["grantAuthorizationDigest"], "grant authorization digest")

    transcript_bytes = _object_bytes(fixture, "candidateSecureSessionTranscript")
    transcript = base.als1_decode(transcript_bytes, 7, 21)
    require(_text(transcript[0]) == SECURE_SUITE, "transcript suite")
    require(_text(transcript[1]) == identifiers["sessionId"], "transcript session")
    require(_text(transcript[2]) == identifiers["pairBindingDigest"], "transcript pair")
    require(_uint(transcript[3], 8) == 1, "transcript epoch")
    require(_text(transcript[4]) == EXPECTED_KEY_IDS["clientIdentity"], "transcript client identity")
    require(_text(transcript[5]) == EXPECTED_KEY_IDS["runtimeIdentity"], "transcript runtime identity")
    require(_text(transcript[6]) == "client" and _text(transcript[7]) == "runtime", "transcript roles")
    require(transcript[8] == bytes.fromhex(keys["clientEphemeral"]["publicKeyX963Hex"]), "transcript client ephemeral")
    require(transcript[9] == bytes.fromhex(keys["runtimeEphemeral"]["publicKeyX963Hex"]), "transcript runtime ephemeral")
    require(transcript[10] == context_fields[11] and transcript[11] == context_fields[12], "transcript nonces")
    require(_uint(transcript[12], 8) == 1, "transcript generation")
    require(_uint(transcript[13], 8) == 1 and _uint(transcript[14], 8) == 1, "transcript config/keyset")
    require(_uint(transcript[15], 8) == 0, "transcript revocation")
    require(_uint(transcript[16], 4) == 1 and _uint(transcript[17], 4) == 1, "transcript protocol")
    require(_text(transcript[18]) == PROFILE, "transcript profile")
    require(_text(transcript[19]) == P2P_TRANSCRIPT_KIND, "transcript route kind")
    require(_text(transcript[20]) == grant_authorization_digest, "transcript must bind object 26")
    require(base.sha256_hex(transcript_bytes) == fixture["derived"]["secureSessionTranscriptDigest"], "transcript digest")


def validate_built_fixture(fixture: dict[str, Any]) -> None:
    require(fixture["schema"] == "aetherlink-production-g1a-c-candidate-v1-vectors", "schema")
    require(fixture["version"] == 1, "fixture version")
    require(fixture["magic"] == "ALS1" and fixture["artifactMagic"] == "ALP1", "magic")
    require(fixture["suite"] == C1_SUITE, "suite")
    require(fixture["secureSessionSuite"] == SECURE_SUITE, "secure suite")
    require(fixture["signatureAlgorithm"] == SIGNATURE_ALGORITHM, "signature algorithm")
    require(fixture["legacyFixture"]["expectedSha256Hex"] == LEGACY_FIXTURE_SHA256, "legacy hash metadata")
    require(fixture["legacyFixture"]["mustRemainUnchanged"] is True, "legacy immutability metadata")
    require(fixture["reservedObjectTypes"] == [19], "object 19 must remain reserved")
    require(fixture["syntheticMaterials"]["testOnly"] is True, "test-only marker")
    require(fixture["expectedOutcomes"]["productionDurabilityClaim"] is False, "durability claim")
    mutation_ids = [item["id"] for item in fixture["mutations"]]
    require(len(mutation_ids) == len(set(mutation_ids)) >= 24, "mutation inventory")
    _validate_key_records(fixture)
    _validate_signature_profiles(fixture)
    _validate_canonical_records(fixture)
    _validate_semantics(fixture)


def build_fixture() -> dict[str, Any]:
    keys = {name: base.key_record(name, scalar) for name, scalar in KEY_SCALARS.items()}
    for name, expected in EXPECTED_KEY_IDS.items():
        require(keys[name]["keyId"] == expected, f"{name}: unexpected key ID")

    service_id = labeled_digest("candidate-vector-service")
    pair_binding = labeled_digest("candidate-vector-pair")
    session_id = labeled_short_hex("candidate-vector-session")
    attempt_id = labeled_digest("candidate-vector-attempt")
    identifiers = {
        "serviceIdDigest": service_id,
        "pairBindingDigest": pair_binding,
        "sessionId": session_id,
        "attemptId": attempt_id,
    }

    delegated = []
    for key_name, purposes in (
        ("route", 0x02),
        ("candidateCapability", 0x0C),
        ("candidateReceipt", 0x30),
    ):
        delegated.append(
            {
                "keysetVersion": 1,
                "keyId": keys[key_name]["keyId"],
                "purposes": purposes,
                "notBeforeMs": KEYSET_NOT_BEFORE_MS,
                "expiresAtMs": KEYSET_EXPIRES_AT_MS,
                "revokedAtMs": 0,
                "publicKeyX963Hex": keys[key_name]["publicKeyX963Hex"],
            }
        )
    delegated.sort(key=lambda item: item["keyId"])
    packed_delegated = b"".join(
        base.be64(item["keysetVersion"])
        + base.raw_digest(item["keyId"])
        + base.be32(item["purposes"])
        + base.be64(item["notBeforeMs"])
        + base.be64(item["expiresAtMs"])
        + base.be64(item["revokedAtMs"])
        + bytes.fromhex(item["publicKeyX963Hex"])
        for item in delegated
    )
    keyset_input = {
        "serviceIdDigest": service_id,
        "keysetVersion": 1,
        "previousKeysetDigest": "none",
        "issuedAtMs": KEYSET_NOT_BEFORE_MS,
        "expiresAtMs": KEYSET_EXPIRES_AT_MS,
        "rootKeyId": keys["root"]["keyId"],
        "delegatedKeys": delegated,
    }
    keyset_fields = [
        base.ascii_bytes(C1_SUITE),
        base.ascii_bytes(service_id),
        base.be64(1),
        base.ascii_bytes("none"),
        base.be64(KEYSET_NOT_BEFORE_MS),
        base.be64(KEYSET_EXPIRES_AT_MS),
        base.ascii_bytes(keys["root"]["keyId"]),
        base.be32(len(delegated)),
        packed_delegated,
        base.ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    keyset_claims = base.als1_encode(10, keyset_fields)
    keyset_signature, keyset_signature_meta = signature_record(
        "root",
        "AetherLink G1a-C service-keyset root signature v1",
        keyset_claims,
        KEY_SCALARS["root"],
        "service_keyset_root",
        None,
    )
    keyset = base.als1_encode(10, keyset_fields + [keyset_signature])

    authority_input = {
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
        "generation": 1,
        "serviceConfigVersion": 1,
        "keysetVersion": 1,
        "revocationCounter": 0,
        "protocolFloor": 1,
        "status": "active",
        "transitionId": labeled_digest("candidate-vector-transition"),
        "transitionRequestDigest": labeled_digest("candidate-vector-transition-request"),
        "acceptedReceiptDigest": labeled_digest("candidate-vector-accepted-receipt"),
        "authorityRevision": 1,
    }
    authority = base.authority_bytes(authority_input)
    authority_digest = base.sha256_hex(authority)

    context_input = {
        "revision": 1,
        "sessionId": session_id,
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
        "clientRole": "client",
        "runtimeRole": "runtime",
        "clientEphemeralPublicKeyHex": keys["clientEphemeral"]["publicKeyX963Hex"],
        "runtimeEphemeralPublicKeyHex": keys["runtimeEphemeral"]["publicKeyX963Hex"],
        "clientNonce": labeled_short_hex("candidate-vector-client-nonce"),
        "runtimeNonce": labeled_short_hex("candidate-vector-runtime-nonce"),
        "generation": 1,
        "serviceConfigVersion": 1,
        "keysetVersion": 1,
        "revocationCounter": 0,
        "protocolVersion": 1,
        "minimumProtocolVersion": 1,
        "profile": PROFILE,
        "routeKind": P2P_KIND,
    }
    context = base.als1_encode(
        18,
        [
            base.ascii_bytes(C1_SUITE),
            base.be64(1),
            base.ascii_bytes(session_id),
            base.ascii_bytes(pair_binding),
            base.be64(1),
            base.ascii_bytes(keys["clientIdentity"]["keyId"]),
            base.ascii_bytes(keys["runtimeIdentity"]["keyId"]),
            base.ascii_bytes("client"),
            base.ascii_bytes("runtime"),
            bytes.fromhex(keys["clientEphemeral"]["publicKeyX963Hex"]),
            bytes.fromhex(keys["runtimeEphemeral"]["publicKeyX963Hex"]),
            base.ascii_bytes(context_input["clientNonce"]),
            base.ascii_bytes(context_input["runtimeNonce"]),
            base.be64(1),
            base.be64(1),
            base.be64(1),
            base.be64(0),
            base.be32(1),
            base.be32(1),
            base.ascii_bytes(PROFILE),
            base.ascii_bytes(P2P_KIND),
        ],
    )
    context_digest = base.sha256_hex(context)

    client_candidate = candidate_bytes(sequence=1, address=bytes((1, 1, 1, 1)))
    runtime_candidate = candidate_bytes(sequence=2, address=bytes((8, 8, 4, 4)))
    client_batch_input = {
        "sessionId": session_id,
        "generation": 1,
        "sequence": 1,
        "expiresAtMs": BATCH_EXPIRES_AT_MS,
        "role": "client",
        "candidate": {
            "kind": "srflx",
            "family": "ipv4",
            "transport": "udp",
            "port": 50_000,
            "priority": 100,
            "foundationHex": (bytes((1,)) * 8).hex(),
            "addressHex": bytes((1, 1, 1, 1)).hex(),
        },
    }
    runtime_batch_input = copy.deepcopy(client_batch_input)
    runtime_batch_input.update({"sequence": 2, "role": "runtime"})
    runtime_batch_input["candidate"] = {
        **client_batch_input["candidate"],
        "foundationHex": (bytes((2,)) * 8).hex(),
        "addressHex": bytes((8, 8, 4, 4)).hex(),
    }
    client_batch = candidate_batch_bytes(
        session_id=session_id,
        generation=1,
        sequence=1,
        expires_at_ms=BATCH_EXPIRES_AT_MS,
        role="client",
        candidate=client_candidate,
    )
    runtime_batch = candidate_batch_bytes(
        session_id=session_id,
        generation=1,
        sequence=2,
        expires_at_ms=BATCH_EXPIRES_AT_MS,
        role="runtime",
        candidate=runtime_candidate,
    )
    require(len(client_batch) == 122 and len(runtime_batch) == 123, "candidate batch byte counts")
    artifacts: dict[str, dict[str, Any]] = {
        "clientCandidateBatch": artifact_record(1, client_batch_input, client_batch),
        "runtimeCandidateBatch": artifact_record(1, runtime_batch_input, runtime_batch),
    }
    batch_values = {
        "clientCandidateBatch": (client_batch, client_candidate, 1),
        "runtimeCandidateBatch": (runtime_batch, runtime_candidate, 2),
    }

    objects: dict[str, dict[str, Any]] = {
        "serviceKeyset": base.object_record(
            10,
            "semantic",
            keyset_input,
            keyset,
            keyset_claims,
            [keyset_signature_meta],
        ),
        "authority": base.object_record(8, "semantic_input", authority_input, authority),
        "preauthorizationSessionContext": base.object_record(
            18,
            "semantic",
            context_input,
            context,
        ),
    }

    operations: list[dict[str, Any]] = []
    operation_values: list[dict[str, Any]] = []
    for spec in OPERATION_SPECS:
        batch_bytes_value, _, batch_sequence = batch_values[spec["batch"]]
        batch_digest = base.sha256_hex(batch_bytes_value)
        proof_id = labeled_digest(f"candidate-vector-{spec['wireName']}-proof")
        capability_id = labeled_digest(f"candidate-vector-{spec['wireName']}-capability")
        single_use_nonce = labeled_digest(f"candidate-vector-{spec['wireName']}-nonce")
        requester_identity = keys[spec["identityKey"]]["keyId"]
        owner_key_name = f"{spec['candidateOwnerRole']}Identity"
        owner_identity = keys[owner_key_name]["keyId"]
        proof_input = {
            "revision": 1,
            "requesterRole": spec["requesterRole"],
            "requesterIdentityFingerprint": requester_identity,
            "requesterPublicKeyX963Hex": keys[spec["identityKey"]]["publicKeyX963Hex"],
            "operation": spec["operation"],
            "candidateOwnerRole": spec["candidateOwnerRole"],
            "candidateOwnerIdentityFingerprint": owner_identity,
            "sessionId": session_id,
            "attemptId": attempt_id,
            "capabilityId": capability_id,
            "candidateBatchDigest": batch_digest,
            "candidateBatchSequence": batch_sequence,
            "singleUseNonce": single_use_nonce,
            "securityContextDigest": context_digest,
            "issuedAtMs": PROOF_ISSUED_AT_MS,
            "notBeforeMs": OPERATION_NOT_BEFORE_MS,
            "expiresAtMs": OPERATION_EXPIRES_AT_MS,
            "proofId": proof_id,
            "pairAuthorityDigest": authority_digest,
            "serviceAudienceId": service_id,
            "initiatorRole": "client",
        }
        proof, proof_record = endpoint_proof_record(
            value=proof_input,
            signer=spec["identityKey"],
            scalar=KEY_SCALARS[spec["identityKey"]],
        )
        proof_name = f"endpointProof{spec['id'][0].upper()}{spec['id'][1:]}"
        objects[proof_name] = proof_record

        capability_input = {
            "objectType": spec["objectType"],
            "operation": spec["operation"],
            "serviceIdDigest": service_id,
            "keysetVersion": 1,
            "signingKeyId": keys["candidateCapability"]["keyId"],
            "capabilityId": capability_id,
            "pairAuthorityDigest": authority_digest,
            "pairBindingDigest": pair_binding,
            "pairEpoch": 1,
            "generation": 1,
            "serviceConfigVersion": 1,
            "revocationCounter": 0,
            "protocolFloor": 1,
            "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
            "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
            "sessionId": session_id,
            "attemptId": attempt_id,
            "requesterRole": spec["requesterRole"],
            "requesterIdentityFingerprint": requester_identity,
            "candidateOwnerRole": spec["candidateOwnerRole"],
            "candidateOwnerIdentityFingerprint": owner_identity,
            "candidateBatchDigest": batch_digest,
            "candidateBatchByteCount": len(batch_bytes_value),
            "candidateBatchSequence": batch_sequence,
            "candidateBatchExpiresAtMs": BATCH_EXPIRES_AT_MS,
            "maximumCandidateBytes": MAXIMUM_CANDIDATE_BYTES,
            "maxOperations": 1,
            "singleUseNonce": single_use_nonce,
            "issuedAtMs": CAPABILITY_ISSUED_AT_MS,
            "notBeforeMs": OPERATION_NOT_BEFORE_MS,
            "expiresAtMs": OPERATION_EXPIRES_AT_MS,
            "endpointOperationProofDigest": base.sha256_hex(proof),
        }
        capability, capability_record = candidate_capability_record(
            value=capability_input,
            scalar=KEY_SCALARS["candidateCapability"],
        )
        capability_name = f"capability{spec['id'][0].upper()}{spec['id'][1:]}"
        objects[capability_name] = capability_record

        authorization_input = {
            "kind": spec["authorizationKind"],
            "pairBindingDigest": pair_binding,
            "pairEpoch": 1,
            "generation": 1,
            "candidateBatchDigest": batch_digest,
            "capabilityDigest": base.sha256_hex(capability),
        }
        authorization = secure_route_authorization_bytes(
            object_type=spec["authorizationObjectType"],
            pair_binding_digest=pair_binding,
            pair_epoch=1,
            generation=1,
            candidate_batch_digest=batch_digest,
            capability_digest=base.sha256_hex(capability),
        )
        authorization_name = f"authorization{spec['id'][0].upper()}{spec['id'][1:]}"
        objects[authorization_name] = base.object_record(
            spec["authorizationObjectType"],
            "semantic",
            authorization_input,
            authorization,
        )
        receipt_name = f"receipt{spec['id'][0].upper()}{spec['id'][1:]}"
        operations.append(
            {
                "wireName": spec["wireName"],
                "operation": spec["operation"],
                "requesterRole": spec["requesterRole"],
                "candidateOwnerRole": spec["candidateOwnerRole"],
                "candidateBatchArtifact": spec["batch"],
                "endpointProofObject": proof_name,
                "capabilityObject": capability_name,
                "authorizationObject": authorization_name,
                "receiptObject": receipt_name,
            }
        )
        operation_values.append(
            {
                "spec": spec,
                "proofInput": proof_input,
                "proof": proof,
                "proofDigest": base.sha256_hex(proof),
                "capabilityInput": capability_input,
                "capability": capability,
                "capabilityDigest": base.sha256_hex(capability),
                "authorization": authorization,
                "authorizationDigest": base.sha256_hex(authorization),
                "batch": batch_bytes_value,
                "batchDigest": batch_digest,
            }
        )

    capability_digests = [item["capabilityDigest"] for item in operation_values]
    authorization_digests = [item["authorizationDigest"] for item in operation_values]
    bilateral_publish = bilateral_digest(
        "AetherLink G1a-C bilateral candidate-publish set v1",
        capability_digests[0],
        capability_digests[2],
    )
    bilateral_fetch = bilateral_digest(
        "AetherLink G1a-C bilateral candidate-fetch set v1",
        capability_digests[3],
        capability_digests[1],
    )
    candidate_pair = selected_candidate_pair_digest(client_candidate, runtime_candidate)

    path_input = {
        "sessionId": session_id,
        "generation": 1,
        "candidatePairDigest": candidate_pair,
        "transport": "direct",
        "clientObserved": labeled_digest("candidate-vector-client-observed"),
        "runtimeObserved": labeled_digest("candidate-vector-runtime-observed"),
        "validatedAtMs": PATH_VALIDATED_AT_MS,
        "expiresAtMs": PATH_EXPIRES_AT_MS,
    }
    path_receipt = path_validation_receipt_bytes(path_input)
    path_digest = base.sha256_hex(path_receipt)
    artifacts["pathValidationReceipt"] = artifact_record(5, path_input, path_receipt)

    route_handle = "direct-01"
    connector_nonce = "nonce-01"
    connector_secret = bytes.fromhex("5a" * 32)
    connector_input = {
        "objectType": 15,
        "kind": P2P_KIND,
        "addressHex": bytes((8, 8, 4, 4)).hex(),
        "port": 50_000,
        "serverName": "none",
        "transport": "udp",
        "routeHandleDigest": base.route_handle_digest(P2P_KIND, route_handle),
        "credentialCommitmentDigest": base.credential_digest(
            P2P_KIND,
            route_handle,
            connector_nonce,
            connector_secret,
        ),
        "pathReceiptDigest": path_digest,
        "leaseDigest": "none",
        "allocationDigest": "none",
    }
    connector = base.connector_bytes(connector_input)
    objects["p2pConnector"] = base.object_record(15, "semantic", connector_input, connector)

    plan_input = {
        "planId": labeled_digest("candidate-vector-p2p-plan"),
        "revision": 1,
        "kind": P2P_KIND,
        "pairAuthorityDigest": authority_digest,
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "generation": 1,
        "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
        "connector": "p2pConnector",
        "securityContextDigest": context_digest,
        "selectedPathReceiptDigest": path_digest,
        "notBeforeMs": PLAN_NOT_BEFORE_MS,
        "expiresAtMs": PLAN_EXPIRES_AT_MS,
    }
    plan = base.als1_encode(
        14,
        [
            base.ascii_bytes(C1_SUITE),
            base.ascii_bytes(plan_input["planId"]),
            base.be64(1),
            base.ascii_bytes(P2P_KIND),
            base.ascii_bytes(authority_digest),
            base.ascii_bytes(pair_binding),
            base.be64(1),
            base.be64(1),
            base.ascii_bytes(keys["clientIdentity"]["keyId"]),
            base.ascii_bytes(keys["runtimeIdentity"]["keyId"]),
            connector,
            base.ascii_bytes(context_digest),
            base.ascii_bytes(path_digest),
            base.be64(PLAN_NOT_BEFORE_MS),
            base.be64(PLAN_EXPIRES_AT_MS),
        ],
    )
    objects["p2pRoutePlan"] = base.object_record(14, "semantic", plan_input, plan)
    plan_digest = base.sha256_hex(plan)

    route_capability_input = {
        "serviceIdDigest": service_id,
        "keysetVersion": 1,
        "signingKeyId": keys["route"]["keyId"],
        "capabilityId": labeled_digest("candidate-vector-route-capability"),
        "issuedAtMs": CAPABILITY_ISSUED_AT_MS,
        "notBeforeMs": PLAN_NOT_BEFORE_MS,
        "expiresAtMs": ROUTE_CAPABILITY_EXPIRES_AT_MS,
        "pairAuthorityDigest": authority_digest,
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
        "generation": 1,
        "serviceConfigVersion": 1,
        "revocationCounter": 0,
        "protocolFloor": 1,
        "kind": P2P_KIND,
        "routePlanClaimsDigest": plan_digest,
        "maxUses": 1,
    }
    route_capability_fields = [
        base.ascii_bytes(C1_SUITE),
        base.ascii_bytes(service_id),
        base.be64(1),
        base.ascii_bytes(keys["route"]["keyId"]),
        base.ascii_bytes(route_capability_input["capabilityId"]),
        base.be64(CAPABILITY_ISSUED_AT_MS),
        base.be64(PLAN_NOT_BEFORE_MS),
        base.be64(ROUTE_CAPABILITY_EXPIRES_AT_MS),
        base.ascii_bytes(authority_digest),
        base.ascii_bytes(pair_binding),
        base.be64(1),
        base.ascii_bytes(keys["clientIdentity"]["keyId"]),
        base.ascii_bytes(keys["runtimeIdentity"]["keyId"]),
        base.be64(1),
        base.be64(1),
        base.be64(0),
        base.be32(1),
        base.ascii_bytes(P2P_KIND),
        base.ascii_bytes(plan_digest),
        base.be32(1),
        base.ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    route_capability_claims = base.als1_encode(13, route_capability_fields)
    route_capability_signature, route_capability_signature_meta = signature_record(
        "route",
        "AetherLink G1a-C route-capability service signature v1",
        route_capability_claims,
        KEY_SCALARS["route"],
        "route_capability",
        0x02,
    )
    route_capability = base.als1_encode(
        13,
        route_capability_fields + [route_capability_signature],
    )
    objects["p2pRouteCapability"] = base.object_record(
        13,
        "semantic",
        route_capability_input,
        route_capability,
        route_capability_claims,
        [route_capability_signature_meta],
    )

    final_authorization_input = {
        "kind": "p2p_direct",
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "generation": 1,
        "candidatePairDigest": candidate_pair,
        "pathValidationReceiptDigest": path_digest,
        "bilateralPublishDigest": bilateral_publish,
        "bilateralFetchDigest": bilateral_fetch,
    }
    final_authorization = secure_route_authorization_bytes(
        object_type=4,
        pair_binding_digest=pair_binding,
        pair_epoch=1,
        generation=1,
        candidate_pair_digest=candidate_pair,
        path_validation_receipt_digest=path_digest,
        bilateral_publish_digest=bilateral_publish,
        bilateral_fetch_digest=bilateral_fetch,
    )
    objects["finalP2PDirectAuthorization"] = base.object_record(
        4,
        "semantic",
        final_authorization_input,
        final_authorization,
    )

    initial_state = {
        "revision": 1,
        "remainingOperations": 4,
        "remainingBytes": sum(len(item["batch"]) for item in operation_values),
        "retentionLimit": 8,
        "entries": [],
    }
    initial_state["snapshotDigestHex"] = usage_snapshot_digest(initial_state)
    states = [initial_state]
    receipt_digests: list[str] = []
    ledger_id = labeled_digest("candidate-operation-ledger")
    for index, item in enumerate(operation_values):
        previous_state = states[-1]
        proof_id = item["proofInput"]["proofId"]
        request = request_digest(proof_id, item["capabilityDigest"], item["authorizationDigest"])
        committed_revision = previous_state["revision"] + 1
        result = usage_result_digest(
            proof_id=proof_id,
            request_digest_value=request,
            capability_digest=item["capabilityDigest"],
            authorization_digest=item["authorizationDigest"],
            single_use_nonce=item["capabilityInput"]["singleUseNonce"],
            consumed_bytes=len(item["batch"]),
            previous_revision=previous_state["revision"],
            committed_revision=committed_revision,
        )
        entry = {
            "requestId": proof_id,
            "requestDigest": request,
            "capabilityDigest": item["capabilityDigest"],
            "authorizationDigest": item["authorizationDigest"],
            "singleUseNonce": item["capabilityInput"]["singleUseNonce"],
            "consumedBytes": len(item["batch"]),
            "receiptDigest": result,
            "committedRevision": committed_revision,
        }
        committed_state = {
            "revision": committed_revision,
            "remainingOperations": previous_state["remainingOperations"] - 1,
            "remainingBytes": previous_state["remainingBytes"] - len(item["batch"]),
            "retentionLimit": previous_state["retentionLimit"],
            "entries": previous_state["entries"] + [entry],
        }
        committed_state["snapshotDigestHex"] = usage_snapshot_digest(committed_state)
        states.append(committed_state)
        spec = item["spec"]
        receipt_input = {
            "status": "committed",
            "serviceIdDigest": service_id,
            "keysetVersion": 1,
            "signingKeyId": keys["candidateReceipt"]["keyId"],
            "pairAuthorityDigest": authority_digest,
            "pairBindingDigest": pair_binding,
            "pairEpoch": 1,
            "generation": 1,
            "serviceConfigVersion": 1,
            "revocationCounter": 0,
            "protocolFloor": 1,
            "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
            "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
            "sessionId": session_id,
            "attemptId": attempt_id,
            "ledgerId": ledger_id,
            "initiatorRole": "client",
            "operation": spec["operation"],
            "requesterRole": spec["requesterRole"],
            "candidateOwnerRole": spec["candidateOwnerRole"],
            "capabilityId": item["capabilityInput"]["capabilityId"],
            "capabilityDigest": item["capabilityDigest"],
            "endpointOperationProofDigest": item["proofDigest"],
            "proofId": proof_id,
            "operationAuthorizationKind": spec["authorizationKind"],
            "operationAuthorizationDigest": item["authorizationDigest"],
            "requestDigest": request,
            "singleUseNonce": item["capabilityInput"]["singleUseNonce"],
            "candidateBatchDigest": item["batchDigest"],
            "candidateBatchByteCount": len(item["batch"]),
            "candidateBatchSequence": item["capabilityInput"]["candidateBatchSequence"],
            "candidateBatchExpiresAtMs": BATCH_EXPIRES_AT_MS,
            "consumedOperations": 1,
            "consumedBytes": len(item["batch"]),
            "resultDigest": result,
            "previousLedgerRevision": previous_state["revision"],
            "committedLedgerRevision": committed_revision,
            "previousLedgerStateCoreDigest": previous_state["snapshotDigestHex"],
            "committedLedgerStateCoreDigest": committed_state["snapshotDigestHex"],
            "commitRecordDigest": labeled_digest(f"candidate-commit-{index}"),
            "committedAtMs": NOW_MS,
            "issuedAtMs": NOW_MS,
            "notBeforeMs": NOW_MS,
            "expiresAtMs": RECEIPT_EXPIRES_AT_MS,
        }
        receipt, receipt_record = operation_receipt_record(
            value=receipt_input,
            scalar=KEY_SCALARS["candidateReceipt"],
        )
        receipt_name = operations[index]["receiptObject"]
        objects[receipt_name] = receipt_record
        receipt_digests.append(base.sha256_hex(receipt))

    effective_plan_not_before = max(
        PLAN_NOT_BEFORE_MS,
        PATH_VALIDATED_AT_MS,
        *(OPERATION_NOT_BEFORE_MS for _ in operation_values),
    )
    effective_plan_expiry = min(
        PLAN_EXPIRES_AT_MS,
        ROUTE_CAPABILITY_EXPIRES_AT_MS,
        PATH_EXPIRES_AT_MS,
        KEYSET_EXPIRES_AT_MS,
        *(OPERATION_EXPIRES_AT_MS for _ in operation_values),
        BATCH_EXPIRES_AT_MS,
    )
    grant_not_before = max(effective_plan_not_before, NOW_MS)
    grant_expiry = min(effective_plan_expiry, RECEIPT_EXPIRES_AT_MS)
    require(grant_not_before == NOW_MS and grant_expiry == PLAN_EXPIRES_AT_MS, "grant window")
    grant_input = {
        "serviceIdDigest": service_id,
        "keysetVersion": 1,
        "pairAuthorityDigest": authority_digest,
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "generation": 1,
        "sessionId": session_id,
        "attemptId": attempt_id,
        "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
        "clientCandidateBatchDigest": base.sha256_hex(client_batch),
        "clientCandidateBatchByteCount": len(client_batch),
        "runtimeCandidateBatchDigest": base.sha256_hex(runtime_batch),
        "runtimeCandidateBatchByteCount": len(runtime_batch),
        "operationOrder": OPERATION_ORDER,
        "operationCapabilityDigests": capability_digests,
        "operationAuthorizationDigests": authorization_digests,
        "bilateralPublishDigest": bilateral_publish,
        "bilateralFetchDigest": bilateral_fetch,
        "candidatePairDigest": candidate_pair,
        "pathValidationReceiptDigest": path_digest,
        "finalRouteAuthorizationDigest": base.sha256_hex(final_authorization),
        "c1RoutePlanClaimsDigest": plan_digest,
        "c1RouteCapabilityDigest": base.sha256_hex(route_capability),
        "operationReceiptDigests": receipt_digests,
        "initiatorRole": "client",
        "connectorTargetRole": "runtime",
        "destinationPolicyId": DESTINATION_POLICY_ID,
        "destinationPolicyVersion": DESTINATION_POLICY_VERSION,
        "securityContextDigest": context_digest,
        "effectiveNotBeforeMs": grant_not_before,
        "expiresAtMs": grant_expiry,
    }
    grant = grant_evidence_bytes(grant_input)
    objects["p2pGrantEvidence"] = base.object_record(25, "semantic", grant_input, grant)
    grant_digest = base.sha256_hex(grant)

    grant_authorization_input = {
        "grantEvidenceDigest": grant_digest,
        "pairAuthorityDigest": authority_digest,
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "generation": 1,
        "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
        "sessionId": session_id,
        "attemptId": attempt_id,
        "initiatorRole": "client",
        "connectorTargetRole": "runtime",
        "destinationPolicyId": DESTINATION_POLICY_ID,
        "destinationPolicyVersion": DESTINATION_POLICY_VERSION,
        "securityContextDigest": context_digest,
        "effectiveNotBeforeMs": grant_not_before,
        "expiresAtMs": grant_expiry,
    }
    grant_authorization = grant_authorization_bytes(grant_authorization_input)
    objects["p2pGrantAuthorization"] = base.object_record(
        26,
        "semantic",
        grant_authorization_input,
        grant_authorization,
    )
    grant_authorization_digest = base.sha256_hex(grant_authorization)

    transcript_input = {
        "sessionId": session_id,
        "pairBindingDigest": pair_binding,
        "pairEpoch": 1,
        "clientIdentityFingerprint": keys["clientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["runtimeIdentity"]["keyId"],
        "clientRole": "client",
        "runtimeRole": "runtime",
        "clientEphemeralPublicKeyHex": keys["clientEphemeral"]["publicKeyX963Hex"],
        "runtimeEphemeralPublicKeyHex": keys["runtimeEphemeral"]["publicKeyX963Hex"],
        "clientNonce": context_input["clientNonce"],
        "runtimeNonce": context_input["runtimeNonce"],
        "generation": 1,
        "serviceConfigVersion": 1,
        "keysetVersion": 1,
        "revocationCounter": 0,
        "protocolVersion": 1,
        "minimumProtocolVersion": 1,
        "profile": PROFILE,
        "routeKind": P2P_TRANSCRIPT_KIND,
        "routeAuthDigest": grant_authorization_digest,
    }
    transcript = base.als1_encode(
        7,
        [
            base.ascii_bytes(SECURE_SUITE),
            base.ascii_bytes(session_id),
            base.ascii_bytes(pair_binding),
            base.be64(1),
            base.ascii_bytes(keys["clientIdentity"]["keyId"]),
            base.ascii_bytes(keys["runtimeIdentity"]["keyId"]),
            base.ascii_bytes("client"),
            base.ascii_bytes("runtime"),
            bytes.fromhex(keys["clientEphemeral"]["publicKeyX963Hex"]),
            bytes.fromhex(keys["runtimeEphemeral"]["publicKeyX963Hex"]),
            base.ascii_bytes(context_input["clientNonce"]),
            base.ascii_bytes(context_input["runtimeNonce"]),
            base.be64(1),
            base.be64(1),
            base.be64(1),
            base.be64(0),
            base.be32(1),
            base.be32(1),
            base.ascii_bytes(PROFILE),
            base.ascii_bytes(P2P_TRANSCRIPT_KIND),
            base.ascii_bytes(grant_authorization_digest),
        ],
    )
    objects["candidateSecureSessionTranscript"] = base.object_record(
        7,
        "semantic",
        transcript_input,
        transcript,
    )

    mutations = [
        {"id": "proof_reordered_tag", "target": "endpointProofClientPublish", "mutation": "swap_tags_1_2", "expected": "malformedCanonical"},
        {"id": "capability_trailing_byte", "target": "capabilityClientPublish", "mutation": "append_00", "expected": "malformedCanonical"},
        {"id": "receipt_oversized", "target": "receiptClientPublish", "mutation": "append_maximum_bytes", "expected": "limitExceeded"},
        {"id": "proof_high_s", "target": "endpointProofClientPublish", "mutation": "replace_s_with_n_minus_s", "expected": "highS"},
        {"id": "capability_non_minimal_der", "target": "capabilityClientPublish", "mutation": "prepend_redundant_integer_zero", "expected": "nonCanonicalSignature"},
        {"id": "publish_fetch_signature_swap", "target": "capabilityRuntimeFetchClient", "mutation": "use_client_publish_signature", "expected": "invalidSignature"},
        {"id": "proof_wrong_endpoint_key", "target": "endpointProofClientPublish", "mutation": "use_runtime_endpoint_key", "expected": "roleMismatch"},
        {"id": "proof_wrong_context_resigned", "target": "endpointProofClientPublish", "mutation": "security_context_zero_resign", "expected": "roleMismatch"},
        {"id": "capability_type_operation_mismatch", "target": "capabilityClientPublish", "mutation": "object_type_24", "expected": "invalidValue"},
        {"id": "capability_wrong_proof_resigned", "target": "capabilityClientPublish", "mutation": "proof_digest_zero_resign", "expected": "roleMismatch"},
        {"id": "capability_wrong_key_purpose", "target": "serviceKeyset", "mutation": "candidate_publish_purpose_removed", "expected": "keyPurposeMismatch"},
        {"id": "capability_batch_substitution", "target": "capabilityClientPublish", "mutation": "runtime_batch_digest_resign", "expected": "batchMismatch"},
        {"id": "authorization_kind_substitution", "target": "authorizationClientPublish", "mutation": "object_type_3", "expected": "routeMismatch"},
        {"id": "receipt_status_mutation", "target": "receiptClientPublish", "mutation": "status_pending", "expected": "invalidValue"},
        {"id": "receipt_request_digest_mutation", "target": "receiptClientPublish", "mutation": "request_digest_zero", "expected": "requestConflict"},
        {"id": "receipt_revision_gap", "target": "receiptClientPublish", "mutation": "committed_revision_plus_two", "expected": "invalidValue"},
        {"id": "receipt_state_chain_break", "target": "receiptRuntimeFetchClient", "mutation": "previous_state_zero_resign", "expected": "revisionMismatch"},
        {"id": "receipt_wrong_key_purpose", "target": "serviceKeyset", "mutation": "publish_receipt_purpose_removed", "expected": "keyPurposeMismatch"},
        {"id": "receipt_revoked_key", "target": "serviceKeyset", "mutation": "receipt_key_revoked_at_now", "expected": "keyRevoked"},
        {"id": "receipt_expired_use", "target": "receiptClientPublish", "mutation": "now_equals_expires", "expected": "expired"},
        {"id": "receipt_capability_substitution", "target": "receiptClientPublish", "mutation": "verify_against_fetch_capability", "expected": "authorityMismatch"},
        {"id": "receipt_authorization_substitution", "target": "receiptClientPublish", "mutation": "verify_against_fetch_authorization", "expected": "authorityMismatch"},
        {"id": "receipt_idempotent_resign", "target": "receiptClientPublish", "mutation": "sign_after_idempotent_retry", "expected": "replay"},
        {"id": "grant_only_three_receipts", "target": "p2pGrantEvidence", "mutation": "omit_fourth_receipt", "expected": "quotaExceeded"},
        {"id": "grant_receipt_reorder", "target": "p2pGrantEvidence", "mutation": "swap_receipts_1_2", "expected": "authorityMismatch"},
        {"id": "grant_duplicate_receipt", "target": "p2pGrantEvidence", "mutation": "duplicate_first_receipt", "expected": "requestConflict"},
        {"id": "grant_other_ledger_chain", "target": "p2pGrantEvidence", "mutation": "replace_first_receipt_other_ledger", "expected": "revisionMismatch"},
        {"id": "grant_packed_digest_short", "target": "p2pGrantEvidence", "mutation": "truncate_tag_18", "expected": "malformedCanonical"},
        {"id": "grant_operation_order_mutation", "target": "p2pGrantEvidence", "mutation": "swap_operation_names", "expected": "invalidValue"},
        {"id": "grant_authorization_digest_reorder", "target": "p2pGrantEvidence", "mutation": "swap_tag_19_digests", "expected": "routeMismatch"},
        {"id": "grant_authorization_evidence_substitution", "target": "p2pGrantAuthorization", "mutation": "evidence_digest_zero", "expected": "routeMismatch"},
        {"id": "grant_authorization_policy_substitution", "target": "p2pGrantAuthorization", "mutation": "policy_version_2", "expected": "routeMismatch"},
        {"id": "grant_authorization_role_swap", "target": "p2pGrantAuthorization", "mutation": "initiator_runtime_target_client", "expected": "routeMismatch"},
        {"id": "transcript_legacy_final_auth", "target": "candidateSecureSessionTranscript", "mutation": "route_auth_digest_final_type_4", "expected": "routeMismatch"},
    ]

    fixture = {
        "schema": "aetherlink-production-g1a-c-candidate-v1-vectors",
        "version": 1,
        "magic": "ALS1",
        "artifactMagic": "ALP1",
        "suite": C1_SUITE,
        "secureSessionSuite": SECURE_SUITE,
        "signatureAlgorithm": SIGNATURE_ALGORITHM,
        "generationProfile": "python-stdlib-rfc6979-sha256-test-only-v1",
        "legacyFixture": {
            "path": "shared/protocol/fixtures/production-g1a-c-v1-vectors.json",
            "expectedSha256Hex": LEGACY_FIXTURE_SHA256,
            "mustRemainUnchanged": True,
        },
        "constants": {
            "nowMs": NOW_MS,
            "maximumRouteLifetimeMs": 600_000,
            "maximumCandidateBytes": MAXIMUM_CANDIDATE_BYTES,
            "maximumCapabilityBytes": MAXIMUM_CAPABILITY_BYTES,
            "maximumGrantEvidenceBytes": MAXIMUM_GRANT_EVIDENCE_BYTES,
            "maximumGrantAuthorizationBytes": MAXIMUM_GRANT_AUTHORIZATION_BYTES,
            "maximumEndpointOperationProofBytes": MAXIMUM_ENDPOINT_PROOF_BYTES,
            "maximumOperationReceiptBytes": MAXIMUM_OPERATION_RECEIPT_BYTES,
            "protocolVersion": 1,
            "minimumProtocolVersion": 1,
            "profile": PROFILE,
        },
        "syntheticMaterials": {
            "testOnly": True,
            "warning": "Public deterministic test material; never use these scalars or secrets in production.",
            "routeHandle": route_handle,
            "connectorNonce": connector_nonce,
            "connectorSecretHex": connector_secret.hex(),
            "keyConfirmationKeyHex": (bytes((0x77,)) * 32).hex(),
        },
        "identifiers": identifiers,
        "keys": keys,
        "objects": objects,
        "artifacts": artifacts,
        "operations": operations,
        "usageLedger": {
            "ledgerId": ledger_id,
            "initialState": states[0],
            "committedStates": states[1:],
        },
        "derived": {
            "serviceKeysetDigest": base.sha256_hex(keyset),
            "pairAuthorityDigest": authority_digest,
            "securityContextDigest": context_digest,
            "clientCandidateBatchDigest": base.sha256_hex(client_batch),
            "runtimeCandidateBatchDigest": base.sha256_hex(runtime_batch),
            "bilateralPublishDigest": bilateral_publish,
            "bilateralFetchDigest": bilateral_fetch,
            "candidatePairDigest": candidate_pair,
            "pathValidationReceiptDigest": path_digest,
            "p2pRoutePlanClaimsDigest": plan_digest,
            "p2pRouteCapabilityDigest": base.sha256_hex(route_capability),
            "finalP2PDirectAuthorizationDigest": base.sha256_hex(final_authorization),
            "operationReceiptDigests": receipt_digests,
            "grantEvidenceDigest": grant_digest,
            "grantAuthorizationDigest": grant_authorization_digest,
            "secureSessionTranscriptDigest": base.sha256_hex(transcript),
        },
        "expectedOutcomes": {
            "operationOrder": OPERATION_ORDER,
            "usageLedgerRevisions": [1, 2, 3, 4, 5],
            "clientCandidateBatchByteCount": 122,
            "runtimeCandidateBatchByteCount": 123,
            "initialRemainingBytes": 490,
            "grantEvidenceObjectType": 25,
            "grantAuthorizationObjectType": 26,
            "transcriptRouteAuthDigestSource": "p2pGrantAuthorization",
            "effectiveNotBeforeMs": grant_not_before,
            "expiresAtMs": grant_expiry,
            "productionDurabilityClaim": False,
            "durabilityScope": "synthetic_contract_readiness_only",
        },
        "mutations": mutations,
        "reservedObjectTypes": [19],
    }
    return fixture


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_fixture_file(path: Path = FIXTURE) -> None:
    validate_legacy_fixture_invariant()
    expected = build_fixture()
    validate_built_fixture(expected)
    require(path.exists(), f"missing fixture: {path}; run with --rewrite")
    actual_bytes = path.read_bytes()
    actual = json.loads(actual_bytes, object_pairs_hook=_reject_duplicate_keys)
    require(actual_bytes == canonical_json_bytes(expected), f"{path}: bytes differ; inspect drift or run explicit --rewrite")
    require(actual == expected, f"{path}: parsed fixture mismatch")
    validate_built_fixture(actual)
    validate_legacy_fixture_invariant()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--rewrite", action="store_true", help="explicitly regenerate the candidate fixture")
    args = parser.parse_args(argv)
    try:
        validate_legacy_fixture_invariant()
        expected = build_fixture()
        validate_built_fixture(expected)
        if args.rewrite:
            args.fixture.parent.mkdir(parents=True, exist_ok=True)
            args.fixture.write_bytes(canonical_json_bytes(expected))
            print(f"rewrote {args.fixture}")
        else:
            validate_fixture_file(args.fixture)
            print(f"validated {args.fixture}")
        validate_legacy_fixture_invariant()
    except (CandidateVectorError, base.VectorError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"G1a-C candidate vector validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
