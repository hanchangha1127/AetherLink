#!/usr/bin/env python3
"""Candidate-only independent-input boundary for a dormant V1 G0 V3 bundle.

This module deliberately does not implement owner, authority, runner, registry,
or revocation trust adapters.  It defines the opaque, immutable hand-off shape
that such reviewed adapters would have to populate, and it can cross-bind those
candidate results to one complete receipt-bundle candidate.  A successful
comparison remains non-authorizing and cannot activate a receipt.

The factory-owned identity check is integrity/API hygiene only, not source
authentication or a provenance boundary.  No future active consumer may treat
these generic candidate identities as reviewed trust-adapter outputs.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import weakref

try:
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_receipt_bundle as receipt_bundle
except ModuleNotFoundError:
    import check_v1_g0_decision as decision
    import check_v1_g0_receipt_bundle as receipt_bundle


ROOT = Path(__file__).resolve().parents[1]

MAX_ADAPTER_SUBJECT_BYTES = receipt_bundle.MAX_COMPLETE_BUNDLE_BYTES
MAX_ADAPTER_OBSERVATION_COUNT = 64
MAX_ADAPTER_OBSERVATION_BYTES = receipt_bundle.MAX_REFERENCED_ARTIFACT_BYTES
MAX_ADAPTER_TOTAL_OBSERVATION_BYTES = 100_663_296

INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE = (
    "G0 V3 independent validation context is candidate_only_dormant_non_authorizing; "
    "it cannot activate receipts, close G0, or authorize G1a"
)

class _IndependentAdapterResultError(ValueError):
    """Raised when one candidate adapter result is not safely constructible."""

    def __init__(self, failures: tuple[str, ...]):
        super().__init__("; ".join(failures))
        self.failures = failures


class _IndependentValidationContextError(ValueError):
    """Raised when seven candidate results cannot form one exact context."""

    def __init__(self, failures: tuple[str, ...]):
        super().__init__("; ".join(failures))
        self.failures = failures


class _IndependentAdapterResult:
    """Opaque identity whose immutable payload remains in a module-owned store."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_: object, **__: object) -> _IndependentAdapterResult:
        raise TypeError("independent adapter results are factory-only")

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("independent adapter results are immutable")

    @property
    def _kind(self) -> str:
        return _required_adapter_payload(self)[0]

    @property
    def _target_binding(self) -> tuple[str, str, str, str, str, str]:
        return _required_adapter_payload(self)[1]

    @property
    def _adapter_ref(self) -> str:
        return _required_adapter_payload(self)[2]

    @property
    def _observation_ref(self) -> str:
        return _required_adapter_payload(self)[3]

    @property
    def _observed_at(self) -> str:
        return _required_adapter_payload(self)[4]

    @property
    def _subject_bytes(self) -> bytes:
        return _required_adapter_payload(self)[5]

    @property
    def _observation_blobs(self) -> tuple[tuple[str, bytes], ...]:
        return _required_adapter_payload(self)[6]


class _IndependentValidationContext:
    """Opaque identity whose deep-immutable payload is module-owned."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_: object, **__: object) -> _IndependentValidationContext:
        raise TypeError("independent validation contexts are factory-only")

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("independent validation contexts are immutable")

    @property
    def _lineage_blobs(self) -> tuple[bytes, ...]:
        return _required_context_payload(self)[0]

    @property
    def _adapter_results(self) -> tuple[_IndependentAdapterResult, ...]:
        return _required_context_payload(self)[1]

    @property
    def _trusted_validation_time(self) -> str:
        return _required_context_payload(self)[2]


def _make_factory_store() -> tuple[object, object, object, object]:
    """Keep provenance and payloads outside returned opaque identities."""

    adapter_payloads: weakref.WeakKeyDictionary[
        _IndependentAdapterResult,
        tuple[
            str,
            tuple[str, str, str, str, str, str],
            str,
            str,
            str,
            bytes,
            tuple[tuple[str, bytes], ...],
        ],
    ] = weakref.WeakKeyDictionary()
    context_payloads: weakref.WeakKeyDictionary[
        _IndependentValidationContext,
        tuple[
            tuple[bytes, ...],
            tuple[_IndependentAdapterResult, ...],
            str,
        ],
    ] = weakref.WeakKeyDictionary()

    def new_adapter(
        payload: tuple[
            str,
            tuple[str, str, str, str, str, str],
            str,
            str,
            str,
            bytes,
            tuple[tuple[str, bytes], ...],
        ],
    ) -> _IndependentAdapterResult:
        result = object.__new__(_IndependentAdapterResult)
        adapter_payloads[result] = payload
        return result

    def adapter_payload(value: object) -> object:
        if type(value) is not _IndependentAdapterResult:
            return None
        return adapter_payloads.get(value)

    def new_context(
        payload: tuple[
            tuple[bytes, ...],
            tuple[_IndependentAdapterResult, ...],
            str,
        ],
    ) -> _IndependentValidationContext:
        context = object.__new__(_IndependentValidationContext)
        context_payloads[context] = payload
        return context

    def context_payload(value: object) -> object:
        if type(value) is not _IndependentValidationContext:
            return None
        return context_payloads.get(value)

    return new_adapter, adapter_payload, new_context, context_payload


(
    _new_adapter_identity,
    _adapter_payload,
    _new_context_identity,
    _context_payload,
) = _make_factory_store()
del _make_factory_store


def _required_adapter_payload(
    value: _IndependentAdapterResult,
) -> tuple[
    str,
    tuple[str, str, str, str, str, str],
    str,
    str,
    str,
    bytes,
    tuple[tuple[str, bytes], ...],
]:
    payload = _adapter_payload(value)
    if not isinstance(payload, tuple) or len(payload) != 7:
        raise AttributeError("independent adapter result is not factory-owned")
    return payload


def _required_context_payload(
    value: _IndependentValidationContext,
) -> tuple[
    tuple[bytes, ...],
    tuple[_IndependentAdapterResult, ...],
    str,
]:
    payload = _context_payload(value)
    if not isinstance(payload, tuple) or len(payload) != 3:
        raise AttributeError("independent validation context is not factory-owned")
    return payload


def _canonical_json_bytes(
    value: object,
    label: str,
    maximum_bytes: int,
    failures: list[str],
) -> bytes | None:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (MemoryError, TypeError, ValueError, UnicodeEncodeError, RecursionError):
        failures.append(f"{label} is not canonical JSON data")
        return None
    if not encoded:
        failures.append(f"{label} must not be empty")
        return None
    if len(encoded) > maximum_bytes:
        failures.append(f"{label} exceeds {maximum_bytes} bytes")
        return None
    return encoded


def _bounded_snapshot(
    value: object,
    label: str,
    maximum_bytes: int,
    failures: list[str],
) -> bytes | None:
    """Take one bounded immutable snapshot of an exact byte-buffer input."""

    return receipt_bundle._bounded_snapshot(value, label, maximum_bytes, failures)


def _valid_target_binding(
    *,
    repository_ref: object,
    commit_object_id: object,
    checkpoint_path: object,
    checkpoint_raw_sha256: object,
    effective_assurance_sha256: object,
    effective_closure_sha256: object,
    failures: list[str],
) -> tuple[str, str, str, str, str, str] | None:
    if not receipt_bundle._valid_opaque_text(repository_ref):
        failures.append("adapter target repository reference is invalid")
    if (
        not isinstance(commit_object_id, str)
        or receipt_bundle._GIT_OBJECT_ID_PATTERN.fullmatch(commit_object_id) is None
    ):
        failures.append("adapter target commit object ID is invalid")
    if checkpoint_path != receipt_bundle.V3_CHECKPOINT_PATH:
        failures.append("adapter target checkpoint path is not the exact V3 path")
    if checkpoint_raw_sha256 != receipt_bundle.LINEAGE_RAW_SHA256[-1]:
        failures.append("adapter target checkpoint SHA-256 is not exact")
    if effective_assurance_sha256 != receipt_bundle.EXPECTED_EFFECTIVE_V3_SHA256:
        failures.append("adapter target effective assurance SHA-256 is not exact")
    if effective_closure_sha256 != receipt_bundle.EXPECTED_CLOSURE_V3_SHA256:
        failures.append("adapter target effective closure SHA-256 is not exact")
    if failures:
        return None
    assert isinstance(repository_ref, str)
    assert isinstance(commit_object_id, str)
    assert isinstance(checkpoint_path, str)
    assert isinstance(checkpoint_raw_sha256, str)
    assert isinstance(effective_assurance_sha256, str)
    assert isinstance(effective_closure_sha256, str)
    return (
        repository_ref,
        commit_object_id,
        checkpoint_path,
        checkpoint_raw_sha256,
        effective_assurance_sha256,
        effective_closure_sha256,
    )


def _build_candidate_independent_adapter_result(
    *,
    kind: str,
    repository_ref: str,
    commit_object_id: str,
    checkpoint_path: str,
    checkpoint_raw_sha256: str,
    effective_assurance_sha256: str,
    effective_closure_sha256: str,
    adapter_ref: str,
    observation_ref: str,
    observed_at: str,
    verified_subject: object,
    observation_blobs: tuple[tuple[str, object], ...],
) -> _IndependentAdapterResult:
    """Build one bounded candidate result; this does not authenticate its source."""

    failures: list[str] = []
    target_binding = _valid_target_binding(
        repository_ref=repository_ref,
        commit_object_id=commit_object_id,
        checkpoint_path=checkpoint_path,
        checkpoint_raw_sha256=checkpoint_raw_sha256,
        effective_assurance_sha256=effective_assurance_sha256,
        effective_closure_sha256=effective_closure_sha256,
        failures=failures,
    )
    if not receipt_bundle._valid_opaque_text(kind):
        failures.append("adapter result kind is invalid")
    for label, value in (
        ("adapter reference", adapter_ref),
        ("adapter observation reference", observation_ref),
    ):
        if not receipt_bundle._valid_opaque_text(value):
            failures.append(f"{label} is invalid")
    receipt_bundle._parse_canonical_utc(
        observed_at,
        "adapter observation time",
        failures,
    )
    subject_bytes = _bounded_snapshot(
        verified_subject,
        "adapter verified subject",
        MAX_ADAPTER_SUBJECT_BYTES,
        failures,
    )
    if subject_bytes is not None:
        subject = receipt_bundle._parse_object(
            subject_bytes,
            "adapter verified subject",
            failures,
        )
        if subject is not None:
            receipt_bundle._validate_json_resources(
                subject,
                failures,
                root_label="adapter verified subject",
            )
            canonical_subject = _canonical_json_bytes(
                subject,
                "adapter verified subject",
                MAX_ADAPTER_SUBJECT_BYTES,
                failures,
            )
            if canonical_subject is not None and canonical_subject != subject_bytes:
                failures.append("adapter verified subject bytes are not canonical")

    copied_observations: list[tuple[str, bytes]] = []
    observed_labels: set[str] = set()
    total_observation_bytes = 0
    if (
        not isinstance(observation_blobs, tuple)
        or not observation_blobs
        or len(observation_blobs) > MAX_ADAPTER_OBSERVATION_COUNT
    ):
        failures.append("adapter observations must be a nonempty bounded tuple")
        observation_blobs = ()
    for index, entry in enumerate(observation_blobs):
        if not isinstance(entry, tuple) or len(entry) != 2:
            failures.append(f"adapter observation {index} must be a label/bytes tuple")
            continue
        label, value = entry
        if not receipt_bundle._valid_opaque_text(label):
            failures.append(f"adapter observation {index} label is invalid")
            continue
        if label in observed_labels:
            failures.append(f"adapter observation {index} label is duplicated")
            continue
        observed_labels.add(label)
        snapshot = _bounded_snapshot(
            value,
            f"adapter observation {index}",
            MAX_ADAPTER_OBSERVATION_BYTES,
            failures,
        )
        if snapshot is None:
            continue
        total_observation_bytes += len(snapshot)
        copied_observations.append((label, snapshot))
    if total_observation_bytes > MAX_ADAPTER_TOTAL_OBSERVATION_BYTES:
        failures.append("adapter observations exceed the aggregate byte limit")

    if failures:
        raise _IndependentAdapterResultError(tuple(failures))
    assert target_binding is not None
    assert subject_bytes is not None
    return _new_adapter_identity(
        (
            kind,
            target_binding,
            adapter_ref,
            observation_ref,
            observed_at,
            subject_bytes,
            tuple(copied_observations),
        )
    )


def _effective_independent_trust_inputs(
    lineage_blobs: tuple[bytes, ...],
    failures: list[str],
) -> tuple[str, ...]:
    effective_v3 = receipt_bundle._materialize_effective_v3(lineage_blobs, failures)
    if effective_v3 is None:
        return ()
    closure = effective_v3.get("g0ClosureContract")
    if not isinstance(closure, dict):
        failures.append("effective V3 closure is unavailable")
        return ()
    policy = closure.get("receiptActivationPolicy")
    if not isinstance(policy, dict):
        failures.append("effective V3 receipt activation policy is unavailable")
        return ()
    inputs = policy.get("independentTrustInputs")
    if not isinstance(inputs, list):
        failures.append("effective V3 independent trust inputs must be a list")
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(inputs):
        if not receipt_bundle._valid_opaque_text(value):
            failures.append(f"effective V3 independent trust input {index} is invalid")
            continue
        if value in seen:
            failures.append(f"effective V3 independent trust input {index} is duplicated")
            continue
        seen.add(value)
        result.append(value)
    for field in (
        "receiptDerivedTrustAnchorsAllowed",
        "bundleSuppliedResultOrActivationFieldsAllowed",
        "partialBundleAcceptanceAllowed",
        "candidateValidationMayAuthorize",
        "receiptActivationAllowed",
        "g1aAuthorityDerivationAllowed",
    ):
        if policy.get(field) is not False:
            failures.append(f"effective V3 {field} must remain exact false")
    return tuple(result)


def _factory_owned_adapter_result(value: object) -> bool:
    payload = _adapter_payload(value)
    if not isinstance(payload, tuple) or len(payload) != 7:
        return False
    (
        kind,
        target_binding,
        adapter_ref,
        observation_ref,
        observed_at,
        subject_bytes,
        observation_blobs,
    ) = payload
    if (
        not receipt_bundle._valid_opaque_text(kind)
        or not isinstance(target_binding, tuple)
        or len(target_binding) != 6
        or any(not isinstance(item, str) for item in target_binding)
        or not receipt_bundle._valid_opaque_text(adapter_ref)
        or not receipt_bundle._valid_opaque_text(observation_ref)
        or type(subject_bytes) is not bytes
        or not subject_bytes
        or len(subject_bytes) > MAX_ADAPTER_SUBJECT_BYTES
        or not isinstance(observation_blobs, tuple)
        or not observation_blobs
        or len(observation_blobs) > MAX_ADAPTER_OBSERVATION_COUNT
    ):
        return False
    target_failures: list[str] = []
    if _valid_target_binding(
        repository_ref=target_binding[0],
        commit_object_id=target_binding[1],
        checkpoint_path=target_binding[2],
        checkpoint_raw_sha256=target_binding[3],
        effective_assurance_sha256=target_binding[4],
        effective_closure_sha256=target_binding[5],
        failures=target_failures,
    ) is None:
        return False
    time_failures: list[str] = []
    if receipt_bundle._parse_canonical_utc(
        observed_at,
        "adapter result observedAt",
        time_failures,
    ) is None:
        return False
    seen_labels: set[str] = set()
    total_bytes = 0
    for entry in observation_blobs:
        if not isinstance(entry, tuple) or len(entry) != 2:
            return False
        label, raw = entry
        if (
            not receipt_bundle._valid_opaque_text(label)
            or label in seen_labels
            or type(raw) is not bytes
            or not raw
            or len(raw) > MAX_ADAPTER_OBSERVATION_BYTES
        ):
            return False
        seen_labels.add(label)
        total_bytes += len(raw)
    return total_bytes <= MAX_ADAPTER_TOTAL_OBSERVATION_BYTES


def _build_candidate_independent_validation_context(
    *,
    lineage_blobs: tuple[object, ...],
    adapter_results: tuple[object, ...],
) -> _IndependentValidationContext:
    """Build the exact seven-input context while granting no authority."""

    failures: list[str] = []
    immutable_lineage = receipt_bundle._snapshot_validated_v3_lineage(
        lineage_blobs,
        label="independent validation context lineage",
        failures=failures,
    )
    if immutable_lineage is None:
        raise _IndependentValidationContextError(tuple(failures))
    expected_kinds = _effective_independent_trust_inputs(immutable_lineage, failures)
    if failures:
        raise _IndependentValidationContextError(tuple(failures))

    if (
        not isinstance(adapter_results, tuple)
        or len(adapter_results) != len(expected_kinds)
    ):
        failures.append("validation context must contain exactly seven adapter results")
        adapter_results = ()
    typed_results: list[_IndependentAdapterResult] = []
    for index, result in enumerate(adapter_results):
        if not _factory_owned_adapter_result(result):
            failures.append(f"validation context adapter result {index} is not factory-owned")
            continue
        assert isinstance(result, _IndependentAdapterResult)
        typed_results.append(result)
    if len(typed_results) == len(expected_kinds):
        actual_kinds = tuple(result._kind for result in typed_results)
        if actual_kinds != expected_kinds:
            failures.append("validation context adapter kind coverage or order is not exact")

        first_target = typed_results[0]._target_binding
        if any(result._target_binding != first_target for result in typed_results[1:]):
            failures.append("validation context adapter target bindings are ambiguous")
        adapter_refs = tuple(result._adapter_ref for result in typed_results)
        observation_refs = tuple(result._observation_ref for result in typed_results)
        if len(set(adapter_refs)) != len(adapter_refs):
            failures.append("validation context adapter references are duplicated")
        if len(set(observation_refs)) != len(observation_refs):
            failures.append("validation context observation references are duplicated")

        reviewed_observations = typed_results[0]._observation_blobs
        if tuple(label for label, _ in reviewed_observations) != receipt_bundle.LINEAGE_PATHS:
            failures.append("reviewed target observations do not cover exact lineage paths")
        elif tuple(raw for _, raw in reviewed_observations) != immutable_lineage:
            failures.append("reviewed target observations do not match exact lineage bytes")

        remote_observations = typed_results[1]._observation_blobs
        if remote_observations != (
            (receipt_bundle.V3_CHECKPOINT_PATH, immutable_lineage[-1]),
        ):
            failures.append("independent remote observation does not match V3 checkpoint bytes")

        observed_times: list[datetime] = []
        for index, result in enumerate(typed_results):
            parsed = receipt_bundle._parse_canonical_utc(
                result._observed_at,
                f"validation context adapter result {index} observedAt",
                failures,
            )
            if parsed is not None:
                observed_times.append(parsed)
        trusted_validation_time = typed_results[-1]._observed_at
        trusted_time = receipt_bundle._parse_canonical_utc(
            trusted_validation_time,
            "trusted validation time",
            failures,
        )
        if trusted_time is not None and any(
            observed_time > trusted_time for observed_time in observed_times
        ):
            failures.append("an adapter observation is later than trusted validation time")
    else:
        trusted_validation_time = ""

    if failures:
        raise _IndependentValidationContextError(tuple(failures))
    return _new_context_identity(
        (
            immutable_lineage,
            tuple(typed_results),
            trusted_validation_time,
        )
    )


def _factory_owned_validation_context(value: object) -> bool:
    payload = _context_payload(value)
    if not isinstance(payload, tuple) or len(payload) != 3:
        return False
    lineage_blobs, adapter_results, trusted_validation_time = payload
    if (
        not isinstance(lineage_blobs, tuple)
        or len(lineage_blobs) != len(receipt_bundle.LINEAGE_PATHS)
        or any(type(raw) is not bytes for raw in lineage_blobs)
        or any(
            not raw or len(raw) > maximum
            for raw, maximum in zip(
                lineage_blobs,
                receipt_bundle.LINEAGE_MAXIMUM_BYTES,
            )
        )
        or not isinstance(adapter_results, tuple)
        or len(adapter_results) != 7
        or any(not _factory_owned_adapter_result(result) for result in adapter_results)
        or not isinstance(trusted_validation_time, str)
    ):
        return False
    if adapter_results[-1]._observed_at != trusted_validation_time:
        return False
    time_failures: list[str] = []
    trusted_time = receipt_bundle._parse_canonical_utc(
        trusted_validation_time,
        "trusted validation time",
        time_failures,
    )
    if trusted_time is None:
        return False
    lineage_failures = list(receipt_bundle._collect_v3_lineage_failures(*lineage_blobs))
    expected_kinds = _effective_independent_trust_inputs(
        lineage_blobs,
        lineage_failures,
    )
    if lineage_failures or tuple(result._kind for result in adapter_results) != expected_kinds:
        return False
    first_target = adapter_results[0]._target_binding
    if any(result._target_binding != first_target for result in adapter_results[1:]):
        return False
    if len({result._adapter_ref for result in adapter_results}) != len(adapter_results):
        return False
    if len({result._observation_ref for result in adapter_results}) != len(adapter_results):
        return False
    if adapter_results[0]._observation_blobs != tuple(
        zip(receipt_bundle.LINEAGE_PATHS, lineage_blobs)
    ):
        return False
    if adapter_results[1]._observation_blobs != (
        (receipt_bundle.V3_CHECKPOINT_PATH, lineage_blobs[-1]),
    ):
        return False
    observed_times: list[datetime] = []
    for result in adapter_results:
        parsed = receipt_bundle._parse_canonical_utc(
            result._observed_at,
            "adapter result observedAt",
            time_failures,
        )
        if parsed is None:
            return False
        observed_times.append(parsed)
    return not time_failures and all(value <= trusted_time for value in observed_times)


def _target_binding_object(
    target_binding: tuple[str, str, str, str, str, str],
) -> dict[str, object]:
    return {
        "repositoryRef": target_binding[0],
        "commitObjectId": target_binding[1],
        "checkpointPath": target_binding[2],
        "checkpointRawSha256": target_binding[3],
        "effectiveAssuranceCanonicalSha256": target_binding[4],
        "effectiveClosureCanonicalSha256": target_binding[5],
    }


def _projection_payloads(
    root: dict[str, object],
    *,
    target_binding: tuple[str, str, str, str, str, str],
    trusted_validation_time: str,
) -> dict[str, object]:
    publication = root.get("publicationReceipt")
    if not isinstance(publication, dict):
        publication = {}
    runner_attestations = root.get("runnerAttestations")
    if not isinstance(runner_attestations, list):
        runner_attestations = []
    gate_receipts = root.get("gateReceipts")
    if not isinstance(gate_receipts, list):
        gate_receipts = []
    target = _target_binding_object(target_binding)
    return {
        "reviewed_repository_and_commit_target": {
            "targetBinding": target,
            "publicationReceipt": publication,
        },
        "independent_remote_v3_checkpoint_bytes": {
            "targetBinding": target,
            "remoteCheckpointPath": publication.get("remoteCheckpointPath"),
            "remoteCheckpointRawSha256": publication.get("remoteCheckpointRawSha256"),
            "remoteReadbackAt": publication.get("remoteReadbackAt"),
            "remoteReadbackSha256": publication.get("remoteReadbackSha256"),
        },
        "trusted_owner_identity_registry_and_revocation_snapshot": {
            "targetBinding": target,
            "ownerBindings": root.get("ownerBindings"),
            "approvalReceipts": root.get("approvalReceipts"),
        },
        "trusted_authority_issuer_registry_and_revocation_snapshot": {
            "targetBinding": target,
            "authorityBindings": root.get("authorityBindings"),
        },
        "trusted_runner_registry_and_attestation_verifier_outputs": {
            "targetBinding": target,
            "runnerAttestations": runner_attestations,
            "gateReceipts": gate_receipts,
        },
        "exact_artifact_log_and_runner_manifest_bytes": {
            "targetBinding": target,
            "evidenceCatalog": root.get("evidenceCatalog"),
            "runnerMaterialBindings": [
                {
                    "runnerAttestationRef": runner.get("runnerAttestationRef"),
                    "toolchainManifestSha256": runner.get("toolchainManifestSha256"),
                    "dependencyManifestSha256": runner.get("dependencyManifestSha256"),
                    "observationManifestSha256": runner.get("observationManifestSha256"),
                    "sanitizedLogSha256": runner.get("sanitizedLogSha256"),
                }
                for runner in runner_attestations
                if isinstance(runner, dict)
            ],
            "gateLogBindings": [
                {
                    "runnerAttestationRef": gate.get("runnerAttestationRef"),
                    "sanitizedLogSha256": gate.get("sanitizedLogSha256"),
                }
                for gate in gate_receipts
                if isinstance(gate, dict)
            ],
        },
        "trusted_validation_time": {
            "targetBinding": target,
            "trustedValidationTime": trusted_validation_time,
        },
    }


def _collect_material_observation_failures(
    root: dict[str, object],
    result: _IndependentAdapterResult,
    failures: list[str],
) -> None:
    expected: list[tuple[str, int | None, str | None]] = []
    evidence_catalog = root.get("evidenceCatalog")
    if isinstance(evidence_catalog, list):
        for evidence in evidence_catalog:
            if not isinstance(evidence, dict):
                continue
            path = evidence.get("artifactPath")
            if isinstance(path, str):
                expected.append(
                    (
                        f"artifact:{path}",
                        evidence.get("artifactByteLength")
                        if isinstance(evidence.get("artifactByteLength"), int)
                        else None,
                        evidence.get("artifactSha256")
                        if isinstance(evidence.get("artifactSha256"), str)
                        else None,
                    )
                )
    runner_attestations = root.get("runnerAttestations")
    if isinstance(runner_attestations, list):
        for runner in runner_attestations:
            if not isinstance(runner, dict):
                continue
            runner_ref = runner.get("runnerAttestationRef")
            if not isinstance(runner_ref, str):
                continue
            for label_suffix, field in (
                ("toolchain", "toolchainManifestSha256"),
                ("dependency", "dependencyManifestSha256"),
                ("observation", "observationManifestSha256"),
                ("log", "sanitizedLogSha256"),
            ):
                digest = runner.get(field)
                expected.append(
                    (
                        f"runner:{runner_ref}:{label_suffix}",
                        None,
                        digest if isinstance(digest, str) else None,
                    )
                )

    actual = result._observation_blobs
    expected_labels = tuple(label for label, _, _ in expected)
    actual_labels = tuple(label for label, _ in actual)
    if actual_labels != expected_labels:
        failures.append("artifact, log, and manifest observation coverage is not exact")
        return
    for index, ((_, expected_length, expected_digest), (_, raw)) in enumerate(
        zip(expected, actual)
    ):
        if expected_length is not None and len(raw) != expected_length:
            failures.append(f"material observation {index} byte length does not match")
        if expected_digest is None or hashlib.sha256(raw).hexdigest() != expected_digest:
            failures.append(f"material observation {index} SHA-256 does not match")


def _event_times(
    root: dict[str, object],
    failures: list[str],
) -> dict[str, list[datetime]]:
    result: dict[str, list[datetime]] = {
        "remote": [],
        "authority": [],
        "runner": [],
        "evidence": [],
        "approval": [],
    }
    publication = root.get("publicationReceipt")
    if isinstance(publication, dict):
        parsed = receipt_bundle._parse_canonical_utc(
            publication.get("remoteReadbackAt"),
            "independent context remote readback time",
            failures,
        )
        if parsed is not None:
            result["remote"].append(parsed)
    for entry in root.get("authorityBindings", []) if isinstance(root.get("authorityBindings"), list) else []:
        if not isinstance(entry, dict):
            continue
        parsed = receipt_bundle._parse_canonical_utc(
            entry.get("notBefore"),
            "independent context authority notBefore",
            failures,
        )
        if parsed is not None:
            result["authority"].append(parsed)
    for entry in root.get("runnerAttestations", []) if isinstance(root.get("runnerAttestations"), list) else []:
        if not isinstance(entry, dict):
            continue
        for field in ("startedAt", "completedAt"):
            parsed = receipt_bundle._parse_canonical_utc(
                entry.get(field),
                f"independent context runner {field}",
                failures,
            )
            if parsed is not None:
                result["runner"].append(parsed)
    for entry in root.get("evidenceCatalog", []) if isinstance(root.get("evidenceCatalog"), list) else []:
        if not isinstance(entry, dict):
            continue
        parsed = receipt_bundle._parse_canonical_utc(
            entry.get("verifiedAt"),
            "independent context evidence verifiedAt",
            failures,
        )
        if parsed is not None:
            result["evidence"].append(parsed)
    for entry in root.get("approvalReceipts", []) if isinstance(root.get("approvalReceipts"), list) else []:
        if not isinstance(entry, dict):
            continue
        parsed = receipt_bundle._parse_canonical_utc(
            entry.get("acceptedAt"),
            "independent context approval acceptedAt",
            failures,
        )
        if parsed is not None:
            result["approval"].append(parsed)
    return result


def _collect_context_time_failures(
    root: dict[str, object],
    context: _IndependentValidationContext,
    failures: list[str],
) -> None:
    times = _event_times(root, failures)
    trusted = receipt_bundle._parse_canonical_utc(
        context._trusted_validation_time,
        "independent context trusted validation time",
        failures,
    )
    remote = times["remote"][0] if times["remote"] else None
    if trusted is not None:
        for category in ("remote", "authority", "runner", "evidence", "approval"):
            if any(value > trusted for value in times[category]):
                failures.append(f"{category} event occurs after trusted validation time")
    if remote is not None:
        for category in ("authority", "runner", "evidence", "approval"):
            if any(value < remote for value in times[category]):
                failures.append(f"{category} event predates independent remote readback")

    result_by_kind = {result._kind: result for result in context._adapter_results}
    remote_result = result_by_kind.get("independent_remote_v3_checkpoint_bytes")
    publication = root.get("publicationReceipt")
    if isinstance(publication, dict) and remote_result is not None:
        if publication.get("remoteReadbackAt") != remote_result._observed_at:
            failures.append("bundle remote readback time does not match independent observation")

    snapshot_requirements = (
        (
            "trusted_owner_identity_registry_and_revocation_snapshot",
            times["approval"],
        ),
        (
            "trusted_authority_issuer_registry_and_revocation_snapshot",
            times["runner"],
        ),
        (
            "trusted_runner_registry_and_attestation_verifier_outputs",
            times["runner"],
        ),
        (
            "exact_artifact_log_and_runner_manifest_bytes",
            times["evidence"] + times["runner"],
        ),
    )
    for kind, required_times in snapshot_requirements:
        result = result_by_kind.get(kind)
        if result is None:
            continue
        observed = receipt_bundle._parse_canonical_utc(
            result._observed_at,
            f"{kind} observation time",
            failures,
        )
        if observed is not None and required_times and observed < max(required_times):
            failures.append(f"{kind} observation predates the records it verifies")


def _finish_context_failures(failures: list[str]) -> tuple[str, ...]:
    if INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE not in failures:
        failures.append(INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE)
    return tuple(failures)


def _collect_context_bound_complete_bundle_failures(
    bundle_bytes: object,
    *,
    context: _IndependentValidationContext,
) -> tuple[str, ...]:
    """Cross-bind one candidate bundle; an exact match remains dormant."""

    failures: list[str] = []
    if not _factory_owned_validation_context(context):
        return _finish_context_failures(
            ["independent validation context is not factory-owned"]
        )
    raw = _bounded_snapshot(
        bundle_bytes,
        "context-bound complete receipt bundle candidate",
        receipt_bundle.MAX_COMPLETE_BUNDLE_BYTES,
        failures,
    )
    if raw is None:
        return _finish_context_failures(failures)

    structural_failures = receipt_bundle._collect_complete_bundle_candidate_failures(
        raw,
        lineage_blobs=context._lineage_blobs,
    )
    if structural_failures != (receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,):
        failures.extend(
            failure
            for failure in structural_failures
            if failure != receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE
        )
    root = receipt_bundle._parse_object(
        raw,
        "context-bound complete receipt bundle candidate",
        failures,
    )
    if root is None:
        return _finish_context_failures(failures)

    target_binding = context._adapter_results[0]._target_binding
    projections = _projection_payloads(
        root,
        target_binding=target_binding,
        trusted_validation_time=context._trusted_validation_time,
    )
    for result in context._adapter_results:
        projection = projections.get(result._kind)
        if projection is None:
            failures.append("validation context contains an unknown adapter result")
            continue
        expected_subject = _canonical_json_bytes(
            projection,
            f"{result._kind} bundle projection",
            MAX_ADAPTER_SUBJECT_BYTES,
            failures,
        )
        if expected_subject is not None and result._subject_bytes != expected_subject:
            failures.append(f"{result._kind} subject does not match candidate bundle")

    publication = root.get("publicationReceipt")
    if isinstance(publication, dict):
        expected_repository, expected_commit = target_binding[0], target_binding[1]
        if publication.get("repositoryRef") != expected_repository:
            failures.append("candidate repository does not match independently reviewed target")
        if publication.get("commitObjectId") != expected_commit:
            failures.append("candidate commit does not match independently reviewed target")

    material_result = context._adapter_results[5]
    _collect_material_observation_failures(root, material_result, failures)
    _collect_context_time_failures(root, context, failures)
    return _finish_context_failures(failures)


def _collect_worktree_contract_failures(root: Path = ROOT) -> tuple[str, ...]:
    """Check only the static factory boundary; do not fabricate adapter results."""

    failures: list[str] = []
    snapshots: list[bytes] = []
    for role, path, maximum_bytes, expected_sha256 in zip(
        receipt_bundle.LINEAGE_ROLES,
        receipt_bundle.LINEAGE_PATHS,
        receipt_bundle.LINEAGE_MAXIMUM_BYTES,
        receipt_bundle.LINEAGE_RAW_SHA256,
    ):
        try:
            raw, _ = decision.read_g0_content_addressed_snapshot(
                root,
                path,
                f"independent context lineage {role}",
                maximum_bytes,
            )
        except receipt_bundle.checkpoint.CheckpointValidationError as error:
            failures.append(str(error))
            continue
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            failures.append(f"independent context lineage {role} SHA-256 changed")
        snapshots.append(raw)
    if failures:
        return tuple(failures)
    lineage_failures: list[str] = []
    immutable_lineage = receipt_bundle._snapshot_validated_v3_lineage(
        tuple(snapshots),
        label="independent context worktree lineage",
        failures=lineage_failures,
    )
    if immutable_lineage is None:
        return tuple(lineage_failures)
    inputs = _effective_independent_trust_inputs(immutable_lineage, failures)
    if len(inputs) != 7:
        failures.append("effective V3 must define exactly seven independent trust inputs")
    forbidden_exports = {
        "accept",
        "activate",
        "authorize",
        "close_g0",
        "derive_g1a",
    }
    if forbidden_exports.intersection(__all__):
        failures.append("independent validation module exports an authority operation")
    return tuple(failures)


def main() -> int:
    failures = _collect_worktree_contract_failures()
    if failures:
        for failure in failures:
            print(f"V1 G0 independent validation context check failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 effective V3 defines exactly seven independent trust inputs and the "
        "factory-only immutable candidate context boundary is present. No adapter "
        "result was fabricated, no receipt was activated, and G0/G1a remain closed."
    )
    return 0


__all__: tuple[str, ...] = ()


if __name__ == "__main__":
    raise SystemExit(main())
