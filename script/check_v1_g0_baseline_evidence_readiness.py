#!/usr/bin/env python3
"""Validate the dormant G0 baseline-evidence readiness contract.

The pure entry points in this module consume supplied bytes only.  They do not
execute a command, inspect an artifact path, authenticate a principal, or turn
a candidate observation into catalog or receipt authority.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

try:
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_receipt_bundle as receipt
except ModuleNotFoundError:
    import check_v1_g0_decision as decision
    import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = "docs/v1/g0/baseline-gate-evidence-readiness-profile-v1.json"
EXPECTED_PROFILE_RAW_SHA256 = (
    "a0c8f45167e9a8f3a4fccbba65afbb928b29b88df2ea2090cc96043ba960af17"
)
MAX_PROFILE_BYTES = 262_144
MAX_CANDIDATE_BYTES = 262_144
MAX_JSON_DEPTH = 16
MAX_JSON_ITEMS = 256
MAX_STRING_BYTES = 4_096
MAX_MANIFEST_ENTRIES = 64
MAX_MANIFEST_BLOB_BYTES = 4_194_304
MAX_TOTAL_MANIFEST_BYTES = 62_914_560
NO_DEVICE_SUCCESS_MARKER = b"No-device quality checks passed."

DORMANT_MESSAGE = (
    "G0 baseline evidence readiness candidate is dormant_non_authorizing; "
    "supplied-byte validation cannot authorize execution, authenticate "
    "provenance, create catalog records, close G0, or authorize G1a"
)

PROFILE_FIELDS = (
    "documentType",
    "schemaVersion",
    "profileId",
    "status",
    "contractBinding",
    "artifactPaths",
    "commandProfileBindings",
    "evidencePlans",
    "commonEnvelopeProfile",
    "manifestProfile",
    "resultProfiles",
    "resourceBounds",
    "sensitiveDataPolicy",
    "authorizationBoundary",
    "supersessionPolicy",
)
CONTRACT_FIELDS = (
    "repositoryRef",
    "blockerId",
    "publicationCommitObjectId",
    "publicationCheckpointPath",
    "publicationCheckpointRawSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
    "requiredCheckIds",
    "requiredOwnerRoles",
    "requiredEvidenceKinds",
)
ARTIFACT_PATH_FIELDS = ("evidenceKind", "candidateVersion", "path")
COMMAND_BINDING_FIELDS = (
    "checkId",
    "commandProfileId",
    "canonicalProfileSha256",
    "currentAuthorizationState",
    "orderedStepsCanonicalSha256",
    "environmentRequirementsCanonicalSha256",
    "toolchainRequirementsCanonicalSha256",
    "allowedSideEffectsCanonicalSha256",
    "forbiddenSideEffectsCanonicalSha256",
    "requiredPreconditionsCanonicalSha256",
    "orderedSteps",
    "requiredEvidenceKinds",
)
COMMAND_STEP_FIELDS = (
    "stepIndex",
    "stepId",
    "argvCanonicalSha256",
)
EVIDENCE_PLAN_FIELDS = (
    "evidenceKind",
    "validationClass",
    "checkId",
    "commandProfileId",
    "commandProfileSha256",
    "commandArgvSha256",
    "allowedSideEffectsSha256",
    "commandStepIndex",
    "commandStepId",
    "commandStepArgvSha256",
    "requiredManifestRoles",
)
CANDIDATE_PLAN_FIELDS = (
    "checkId",
    "validationClass",
    "commandProfileId",
    "commandProfileSha256",
    "commandArgvSha256",
    "allowedSideEffectsSha256",
    "commandStepIndex",
    "commandStepId",
    "commandStepArgvSha256",
    "requiredManifestRoles",
)
CANDIDATE_FIELDS = (
    "documentType",
    "schemaVersion",
    "artifactId",
    "evidenceKind",
    "status",
    "profileRef",
    "contractBinding",
    "plan",
    "manifest",
    "result",
    "trustBoundary",
    "state",
)
PROFILE_REF_FIELDS = ("path", "profileId", "rawSha256")
MANIFEST_FIELDS = ("serialization", "entries", "entriesCanonicalSha256")
MANIFEST_ENTRY_FIELDS = (
    "inputRole",
    "sourceRef",
    "contentType",
    "byteLength",
    "rawSha256",
    "canonicalSha256",
)
RESULT_FIELDS = (
    "resultClass",
    "manifestCanonicalSha256",
    "startedAt",
    "completedAt",
    "exitCode",
    "payload",
)
TRUST_BOUNDARY_FIELDS = (
    "observationClass",
    "independentInputsPresent",
    "requiredIndependentInputsAbsent",
    "catalogRecordDerivable",
    "authorityDerivable",
    "runnerAttestationDerivable",
    "gateReceiptDerivable",
)
STATE_FIELDS = (
    "executionAuthorized",
    "evidenceVerified",
    "ownerAcceptanceDerived",
    "blockerClosureDerived",
    "receiptActivationAllowed",
    "g0ExitComplete",
    "g1aMayStartNow",
)
REQUIRED_INDEPENDENT_INPUTS_ABSENT = (
    "authenticated_provenance",
    "trusted_authority_and_runner_attestation",
    "independent_artifact_byte_verification",
)
EXECUTION_PAYLOAD_FIELDS = (
    "executionSessionRefCandidate",
    "authorizationRefCandidate",
    "sourcePublicationCommit",
    "commandProfileId",
    "commandProfileSha256",
    "commandArgvSha256",
    "workingDirectorySha256",
    "environmentSha256",
    "allowedSideEffectsSha256",
    "stepIndex",
    "stepId",
    "stepArgvSha256",
    "toolchainManifestSha256",
    "dependencyManifestSha256",
    "observationManifestSha256",
    "sanitizedLogSha256",
    "outputManifestSha256",
)
STATIC_ASSURANCE_PAYLOAD_FIELDS = (
    "lineageRawSha256",
    "lineageCanonicalSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
)
STATIC_SOURCE_PAYLOAD_FIELDS = (
    "sourceRecordCount",
    "sourceRecordsCanonicalSha256",
    "mismatchCount",
)
RUN_PLAN_FIELDS = (
    "documentType",
    "schemaVersion",
    "planId",
    "status",
    "profileRef",
    "contractBinding",
    "commands",
    "candidateArtifactReservations",
    "state",
)
RUN_PLAN_COMMAND_FIELDS = (
    "checkId",
    "commandProfileId",
    "commandProfileSha256",
    "commandArgvSha256",
    "allowedSideEffectsSha256",
    "currentAuthorizationState",
    "authorizationRefCandidate",
    "runnerAttestationRefCandidate",
    "executionAllowed",
)
RUN_PLAN_RESERVATION_FIELDS = (
    "evidenceKind",
    "path",
    "artifactPresent",
    "acquisitionAuthorized",
)

EVIDENCE_KINDS = (
    "canonical_assurance_hash",
    "source_hash_readback",
    "separately_authorized_full_gate_result",
    "android_release_compile_result",
    "macos_release_compile_result",
)
DERIVED_EVIDENCE_KINDS = (
    "owner_acceptance",
    "quality_measurement_contract_owner_approvals",
)
EXECUTION_EVIDENCE_KINDS = EVIDENCE_KINDS[2:]
STATIC_EVIDENCE_KINDS = EVIDENCE_KINDS[:2]
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SESSION_REF_PATTERN = re.compile(
    r"^execution-session-candidate:[a-z0-9][a-z0-9-]{0,95}:v[1-9][0-9]{0,8}$"
)
AUTHORITY_REF_PATTERN = re.compile(
    r"^authority-candidate:[a-z0-9][a-z0-9-]{0,95}:v[1-9][0-9]{0,8}$"
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_bytes(value: object, label: str, failures: list[str]) -> bytes | None:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (MemoryError, RecursionError, TypeError, UnicodeEncodeError, ValueError) as error:
        failures.append(f"{label} cannot be canonically encoded: {error}")
        return None


def _ordered_bytes(value: object, label: str, failures: list[str]) -> bytes | None:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (MemoryError, RecursionError, TypeError, UnicodeEncodeError, ValueError) as error:
        failures.append(f"{label} cannot be encoded: {error}")
        return None


def _canonical_sha256(value: object, label: str, failures: list[str]) -> str | None:
    encoded = _canonical_bytes(value, label, failures)
    return None if encoded is None else _sha256(encoded)


def _exact_object(
    value: object,
    fields: tuple[str, ...],
    label: str,
    failures: list[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        failures.append(f"{label} must be an object")
        return {}
    if tuple(value) != fields:
        failures.append(f"{label} fields or field order are not exact")
    return value


def _require_equal(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not decision.exactly_equal(actual, expected):
        failures.append(f"{label} is not exact")


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _exact_nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _exact_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _artifact_id(evidence_kind: str) -> str:
    return f"g0-{evidence_kind.replace('_', '-')}-candidate-v1"


def _artifact_path(evidence_kind: str) -> str:
    return f"docs/evidence/{_artifact_id(evidence_kind)}.json"


def _finish_candidate_failures(failures: list[str]) -> tuple[str, ...]:
    failures[:] = [failure for failure in failures if failure != DORMANT_MESSAGE]
    failures.append(DORMANT_MESSAGE)
    return tuple(failures)


def _snapshot_context(
    profile_bytes: object,
    lineage_blobs: object,
    failures: list[str],
) -> tuple[bytes, tuple[bytes, ...], dict[str, object], dict[str, object]] | None:
    profile_raw = receipt._bounded_snapshot(
        profile_bytes,
        "G0 baseline evidence readiness profile",
        MAX_PROFILE_BYTES,
        failures,
    )
    immutable_lineage = receipt._snapshot_validated_v3_lineage(
        lineage_blobs,
        label="G0 baseline evidence readiness lineage",
        failures=failures,
    )
    if profile_raw is None or immutable_lineage is None:
        return None
    profile = receipt._parse_object(
        profile_raw,
        "G0 baseline evidence readiness profile",
        failures,
    )
    effective_v3 = receipt._materialize_effective_v3(immutable_lineage, failures)
    if profile is None or effective_v3 is None:
        return None
    receipt._validate_json_resources(
        profile,
        failures,
        root_label="G0 baseline evidence readiness profile",
        maximum_depth=MAX_JSON_DEPTH,
        maximum_items=MAX_JSON_ITEMS,
        maximum_string_bytes=MAX_STRING_BYTES,
    )
    return profile_raw, immutable_lineage, profile, effective_v3


def _expected_contract_binding(
    effective_v3: dict[str, object],
    failures: list[str],
) -> dict[str, object]:
    closure = effective_v3.get("g0ClosureContract")
    blockers = closure.get("blockerRequirements") if isinstance(closure, dict) else None
    target = None
    if isinstance(blockers, list):
        target = next(
            (
                blocker
                for blocker in blockers
                if isinstance(blocker, dict)
                and blocker.get("blockerId")
                == "g0_assurance_artifacts_and_baseline_gate"
            ),
            None,
        )
    if not isinstance(target, dict):
        failures.append("effective V3 baseline blocker is missing or ambiguous")
        return {}
    required_evidence = target.get("requiredEvidenceKinds")
    if not isinstance(required_evidence, list):
        failures.append("effective V3 baseline evidence kinds must be a list")
        return {}
    non_derived = [kind for kind in required_evidence if kind not in DERIVED_EVIDENCE_KINDS]
    return {
        "repositoryRef": "github:hanchangha1127/AetherLink",
        "blockerId": "g0_assurance_artifacts_and_baseline_gate",
        "publicationCommitObjectId": receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
        "publicationCheckpointPath": receipt.V3_CHECKPOINT_PATH,
        "publicationCheckpointRawSha256": receipt.LINEAGE_RAW_SHA256[-1],
        "effectiveAssuranceCanonicalSha256": receipt.EXPECTED_EFFECTIVE_V3_SHA256,
        "effectiveClosureCanonicalSha256": receipt.EXPECTED_CLOSURE_V3_SHA256,
        "requiredCheckIds": target.get("requiredCheckIds"),
        "requiredOwnerRoles": target.get("requiredOwnerRoles"),
        "requiredEvidenceKinds": non_derived,
    }


def _expected_command_bindings(
    effective_v3: dict[str, object],
    failures: list[str],
) -> list[dict[str, object]]:
    closure = effective_v3.get("g0ClosureContract")
    profiles = closure.get("commandProfiles") if isinstance(closure, dict) else None
    if not isinstance(profiles, list) or len(profiles) != 2:
        failures.append("effective V3 must contain the exact two command profiles")
        return []
    expected: list[dict[str, object]] = []
    for profile_index, raw_profile in enumerate(profiles):
        if not isinstance(raw_profile, dict):
            failures.append(f"effective V3 commandProfiles[{profile_index}] must be an object")
            continue
        body = raw_profile.get("profileBody")
        if not isinstance(body, dict):
            failures.append(
                f"effective V3 commandProfiles[{profile_index}].profileBody must be an object"
            )
            continue
        steps = body.get("orderedSteps")
        if not isinstance(steps, list):
            failures.append(
                f"effective V3 commandProfiles[{profile_index}].orderedSteps must be a list"
            )
            continue
        compiled_steps: list[dict[str, object]] = []
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict):
                failures.append(
                    f"effective V3 commandProfiles[{profile_index}].orderedSteps[{step_index}] must be an object"
                )
                continue
            compiled_steps.append(
                {
                    "stepIndex": step_index,
                    "stepId": step.get("stepId"),
                    "argvCanonicalSha256": _canonical_sha256(
                        step.get("argv"),
                        f"effective command profile {profile_index} step {step_index} argv",
                        failures,
                    ),
                }
            )
        body_sha = _canonical_sha256(
            body,
            f"effective command profile {profile_index} body",
            failures,
        )
        expected.append(
            {
                "checkId": body.get("checkId"),
                "commandProfileId": raw_profile.get("commandProfileId"),
                "canonicalProfileSha256": body_sha,
                "currentAuthorizationState": body.get("currentAuthorizationState"),
                "orderedStepsCanonicalSha256": _canonical_sha256(
                    steps,
                    f"effective command profile {profile_index} ordered steps",
                    failures,
                ),
                "environmentRequirementsCanonicalSha256": _canonical_sha256(
                    body.get("environmentRequirements"),
                    f"effective command profile {profile_index} environment",
                    failures,
                ),
                "toolchainRequirementsCanonicalSha256": _canonical_sha256(
                    body.get("toolchainRequirements"),
                    f"effective command profile {profile_index} toolchains",
                    failures,
                ),
                "allowedSideEffectsCanonicalSha256": _canonical_sha256(
                    body.get("allowedSideEffects"),
                    f"effective command profile {profile_index} allowed side effects",
                    failures,
                ),
                "forbiddenSideEffectsCanonicalSha256": _canonical_sha256(
                    body.get("forbiddenSideEffects"),
                    f"effective command profile {profile_index} forbidden side effects",
                    failures,
                ),
                "requiredPreconditionsCanonicalSha256": _canonical_sha256(
                    body.get("requiredPreconditions"),
                    f"effective command profile {profile_index} preconditions",
                    failures,
                ),
                "orderedSteps": compiled_steps,
                "requiredEvidenceKinds": body.get("requiredEvidenceKinds"),
            }
        )
        _require_equal(
            raw_profile.get("canonicalProfileSha256"),
            body_sha,
            f"effective command profile {profile_index} canonical digest",
            failures,
        )
        _require_equal(
            body.get("currentAuthorizationState"),
            "not_authorized",
            f"effective command profile {profile_index} authorization state",
            failures,
        )
    return expected


def _expected_evidence_plans(
    command_bindings: list[dict[str, object]],
) -> list[dict[str, object]]:
    if len(command_bindings) != 2:
        return []
    full, release = command_bindings
    full_steps = full.get("orderedSteps")
    release_steps = release.get("orderedSteps")
    if not isinstance(full_steps, list) or len(full_steps) != 1:
        return []
    if not isinstance(release_steps, list) or len(release_steps) != 2:
        return []

    def execution_plan(
        kind: str,
        binding: dict[str, object],
        step_index: int,
        roles: list[str],
    ) -> dict[str, object]:
        steps = binding["orderedSteps"]
        step = steps[step_index]
        return {
            "evidenceKind": kind,
            "validationClass": "execution_result_observation",
            "checkId": binding["checkId"],
            "commandProfileId": binding["commandProfileId"],
            "commandProfileSha256": binding["canonicalProfileSha256"],
            "commandArgvSha256": binding["orderedStepsCanonicalSha256"],
            "allowedSideEffectsSha256": binding[
                "allowedSideEffectsCanonicalSha256"
            ],
            "commandStepIndex": step_index,
            "commandStepId": step["stepId"],
            "commandStepArgvSha256": step["argvCanonicalSha256"],
            "requiredManifestRoles": roles,
        }

    common_roles = [
        "sanitized_ordered_stdout_stderr",
        "working_directory",
        "environment",
        "toolchain",
        "dependencies",
        "egress_process_observation_manifest",
    ]
    return [
        {
            "evidenceKind": "canonical_assurance_hash",
            "validationClass": "static_lineage_observation",
            "checkId": "g0_assurance_packet",
            "commandProfileId": None,
            "commandProfileSha256": None,
            "commandArgvSha256": None,
            "allowedSideEffectsSha256": None,
            "commandStepIndex": None,
            "commandStepId": None,
            "commandStepArgvSha256": None,
            "requiredManifestRoles": list(receipt.LINEAGE_ROLES),
        },
        {
            "evidenceKind": "source_hash_readback",
            "validationClass": "static_source_observation",
            "checkId": "g0_assurance_packet",
            "commandProfileId": None,
            "commandProfileSha256": None,
            "commandArgvSha256": None,
            "allowedSideEffectsSha256": None,
            "commandStepIndex": None,
            "commandStepId": None,
            "commandStepArgvSha256": None,
            "requiredManifestRoles": ["effective_v3_source_records_in_exact_order"],
        },
        execution_plan(
            "separately_authorized_full_gate_result",
            full,
            0,
            [*common_roles, "output_manifest"],
        ),
        execution_plan(
            "android_release_compile_result",
            release,
            0,
            [*common_roles, "unsigned_android_release_output_manifest"],
        ),
        execution_plan(
            "macos_release_compile_result",
            release,
            1,
            [*common_roles, "unsigned_macos_release_output_manifest"],
        ),
    ]


def _collect_profile_document_failures(
    profile_raw: bytes,
    profile: dict[str, object],
    effective_v3: dict[str, object],
) -> tuple[str, ...]:
    failures: list[str] = []
    _require_equal(
        _sha256(profile_raw),
        EXPECTED_PROFILE_RAW_SHA256,
        "baseline evidence readiness profile raw SHA-256",
        failures,
    )
    profile = _exact_object(profile, PROFILE_FIELDS, "readiness profile", failures)
    for field, expected in (
        ("documentType", "aetherlink.v1-g0-baseline-gate-evidence-readiness-profile"),
        ("schemaVersion", 1),
        ("profileId", "aetherlink_v1_g0_baseline_gate_evidence_readiness_profile_v1"),
        ("status", "draft_prepared_unverified_non_authorizing"),
    ):
        _require_equal(profile.get(field), expected, f"readiness profile {field}", failures)

    contract = _exact_object(
        profile.get("contractBinding"), CONTRACT_FIELDS, "contractBinding", failures
    )
    expected_contract = _expected_contract_binding(effective_v3, failures)
    _require_equal(contract, expected_contract, "contractBinding", failures)

    expected_paths = [
        {
            "evidenceKind": kind,
            "candidateVersion": 1,
            "path": _artifact_path(kind),
        }
        for kind in EVIDENCE_KINDS
    ]
    paths = profile.get("artifactPaths")
    if isinstance(paths, list):
        for index, item in enumerate(paths):
            _exact_object(item, ARTIFACT_PATH_FIELDS, f"artifactPaths[{index}]", failures)
            if isinstance(item, dict) and not receipt._safe_artifact_path(item.get("path")):
                failures.append(f"artifactPaths[{index}].path is unsafe")
    _require_equal(paths, expected_paths, "artifactPaths", failures)

    expected_commands = _expected_command_bindings(effective_v3, failures)
    commands = profile.get("commandProfileBindings")
    if isinstance(commands, list):
        for index, command in enumerate(commands):
            command = _exact_object(
                command,
                COMMAND_BINDING_FIELDS,
                f"commandProfileBindings[{index}]",
                failures,
            )
            steps = command.get("orderedSteps")
            if isinstance(steps, list):
                for step_index, step in enumerate(steps):
                    _exact_object(
                        step,
                        COMMAND_STEP_FIELDS,
                        f"commandProfileBindings[{index}].orderedSteps[{step_index}]",
                        failures,
                    )
    _require_equal(commands, expected_commands, "commandProfileBindings", failures)

    expected_plans = _expected_evidence_plans(expected_commands)
    plans = profile.get("evidencePlans")
    if isinstance(plans, list):
        for index, plan in enumerate(plans):
            _exact_object(plan, EVIDENCE_PLAN_FIELDS, f"evidencePlans[{index}]", failures)
    _require_equal(plans, expected_plans, "evidencePlans", failures)

    common = profile.get("commonEnvelopeProfile")
    if not isinstance(common, dict):
        failures.append("commonEnvelopeProfile must be an object")
    else:
        _require_equal(common.get("exactFields"), list(CANDIDATE_FIELDS), "candidate fields", failures)
        _require_equal(common.get("planExactFields"), list(CANDIDATE_PLAN_FIELDS), "candidate plan fields", failures)
        _require_equal(
            common.get("trustBoundaryExactFields"),
            list(TRUST_BOUNDARY_FIELDS),
            "candidate trust-boundary fields",
            failures,
        )
        _require_equal(
            common.get("stateExactFields"),
            list(STATE_FIELDS),
            "candidate state fields",
            failures,
        )
        fixed = common.get("fixedValues")
        _require_equal(
            fixed,
            {
                "documentType": "aetherlink.v1-g0-baseline-evidence-candidate",
                "schemaVersion": 1,
                "status": "prepared_unverified_non_authorizing",
            },
            "candidate fixed values",
            failures,
        )
        _require_equal(
            common.get("trustBoundaryFixedValues"),
            {
                "observationClass": "synthetic_fixture_or_unverified_session_observation_only",
                "independentInputsPresent": [],
                "requiredIndependentInputsAbsent": list(
                    REQUIRED_INDEPENDENT_INPUTS_ABSENT
                ),
                "catalogRecordDerivable": False,
                "authorityDerivable": False,
                "runnerAttestationDerivable": False,
                "gateReceiptDerivable": False,
            },
            "candidate trust-boundary fixed values",
            failures,
        )
        _require_equal(
            common.get("stateFixedValues"),
            {field: False for field in STATE_FIELDS},
            "candidate state fixed values",
            failures,
        )
    manifest_profile = profile.get("manifestProfile")
    if not isinstance(manifest_profile, dict):
        failures.append("manifestProfile must be an object")
    else:
        _require_equal(manifest_profile.get("exactFields"), list(MANIFEST_FIELDS), "manifest fields", failures)
        _require_equal(manifest_profile.get("entryExactFields"), list(MANIFEST_ENTRY_FIELDS), "manifest entry fields", failures)

    result_profiles = profile.get("resultProfiles")
    if not isinstance(result_profiles, list):
        failures.append("resultProfiles must be a list")
    else:
        _require_equal(
            [item.get("evidenceKind") for item in result_profiles if isinstance(item, dict)],
            list(EVIDENCE_KINDS),
            "result profile evidence-kind order",
            failures,
        )
        expected_payload_fields = (
            STATIC_ASSURANCE_PAYLOAD_FIELDS,
            STATIC_SOURCE_PAYLOAD_FIELDS,
            EXECUTION_PAYLOAD_FIELDS,
            EXECUTION_PAYLOAD_FIELDS,
            EXECUTION_PAYLOAD_FIELDS,
        )
        for index, expected_fields in enumerate(expected_payload_fields):
            item = result_profiles[index] if index < len(result_profiles) else None
            if not isinstance(item, dict):
                failures.append(f"resultProfiles[{index}] must be an object")
                continue
            _require_equal(
                item.get("exactPayloadFields"),
                list(expected_fields),
                f"resultProfiles[{index}] payload fields",
                failures,
            )

    bounds = profile.get("resourceBounds")
    if not isinstance(bounds, dict):
        failures.append("resourceBounds must be an object")
    else:
        for field, expected in (
            ("profileMaximumBytes", MAX_PROFILE_BYTES),
            ("candidateMaximumBytes", MAX_CANDIDATE_BYTES),
            ("jsonMaximumDepth", MAX_JSON_DEPTH),
            ("arrayMaximumItems", MAX_JSON_ITEMS),
            ("manifestMaximumEntries", MAX_MANIFEST_ENTRIES),
            ("manifestBlobMaximumBytes", MAX_MANIFEST_BLOB_BYTES),
            ("manifestTotalMaximumBytes", MAX_TOTAL_MANIFEST_BYTES),
            ("stringMaximumUtf8Bytes", MAX_STRING_BYTES),
            ("integerMaximumDigits", 128),
        ):
            _require_equal(bounds.get(field), expected, f"resourceBounds.{field}", failures)

    boundary = profile.get("authorizationBoundary")
    if not isinstance(boundary, dict):
        failures.append("authorizationBoundary must be an object")
    else:
        for field in (
            "commandProfilesRemainNotAuthorized",
            "candidateValidationMayExecuteCommands",
            "candidateValidationMayReadFiles",
            "candidateValidationMayAuthenticateAuthority",
            "candidateValidationMayAuthenticateRunner",
            "candidateValidationMayCreateCatalogRecords",
            "candidateValidationMayCreateReceipts",
            "candidateValidationMayCloseBlocker",
            "candidateValidationMayActivateReceipts",
            "candidateValidationMayCompleteG0",
            "candidateValidationMayAuthorizeG1a",
        ):
            expected = field == "commandProfilesRemainNotAuthorized"
            _require_equal(boundary.get(field), expected, f"authorizationBoundary.{field}", failures)
        _require_equal(
            boundary.get("derivedEvidenceKindsForbidden"),
            list(DERIVED_EVIDENCE_KINDS),
            "authorizationBoundary derived evidence kinds",
            failures,
        )
    return tuple(failures)


def _validated_context(
    profile_bytes: object,
    lineage_blobs: object,
    failures: list[str],
) -> tuple[bytes, tuple[bytes, ...], dict[str, object], dict[str, object]] | None:
    context = _snapshot_context(profile_bytes, lineage_blobs, failures)
    if context is None:
        return None
    profile_raw, immutable_lineage, profile, effective_v3 = context
    failures.extend(
        _collect_profile_document_failures(profile_raw, profile, effective_v3)
    )
    return None if failures else context


def collect_baseline_evidence_readiness_profile_failures(
    profile_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
) -> tuple[str, ...]:
    """Validate the profile using immutable snapshots of six supplied lineage blobs."""

    failures: list[str] = []
    _validated_context(profile_bytes, lineage_blobs, failures)
    return tuple(failures)


def _build_run_plan(
    profile_raw: bytes,
    profile: dict[str, object],
) -> dict[str, object]:
    commands: list[dict[str, object]] = []
    for binding in profile["commandProfileBindings"]:
        commands.append(
            {
                "checkId": binding["checkId"],
                "commandProfileId": binding["commandProfileId"],
                "commandProfileSha256": binding["canonicalProfileSha256"],
                "commandArgvSha256": binding["orderedStepsCanonicalSha256"],
                "allowedSideEffectsSha256": binding[
                    "allowedSideEffectsCanonicalSha256"
                ],
                "currentAuthorizationState": "not_authorized",
                "authorizationRefCandidate": None,
                "runnerAttestationRefCandidate": None,
                "executionAllowed": False,
            }
        )
    reservations = [
        {
            "evidenceKind": entry["evidenceKind"],
            "path": entry["path"],
            "artifactPresent": False,
            "acquisitionAuthorized": False,
        }
        for entry in profile["artifactPaths"]
    ]
    return {
        "documentType": "aetherlink.v1-g0-baseline-evidence-readiness-plan",
        "schemaVersion": 1,
        "planId": "aetherlink_v1_g0_baseline_evidence_readiness_plan_v1",
        "status": "prepared_unverified_non_authorizing",
        "profileRef": {
            "path": PROFILE_PATH,
            "profileId": profile["profileId"],
            "rawSha256": _sha256(profile_raw),
        },
        "contractBinding": profile["contractBinding"],
        "commands": commands,
        "candidateArtifactReservations": reservations,
        "state": {
            "commandExecutionAuthorized": False,
            "artifactAcquisitionAuthorized": False,
            "evidenceVerified": False,
            "catalogRecordsCreated": False,
            "receiptsCreated": False,
            "blockerClosureDerived": False,
            "receiptActivationAllowed": False,
            "g0ExitComplete": False,
            "g1aMayStartNow": False,
        },
    }


def _collect_run_plan_failures(
    plan: object,
    *,
    profile_raw: bytes,
    profile: dict[str, object],
) -> tuple[str, ...]:
    failures: list[str] = []
    plan = _exact_object(plan, RUN_PLAN_FIELDS, "readiness run plan", failures)
    expected = _build_run_plan(profile_raw, profile)
    _require_equal(plan, expected, "readiness run plan", failures)
    commands = plan.get("commands")
    if isinstance(commands, list):
        for index, command in enumerate(commands):
            command = _exact_object(
                command,
                RUN_PLAN_COMMAND_FIELDS,
                f"readiness run plan commands[{index}]",
                failures,
            )
            _require_equal(
                command.get("currentAuthorizationState"),
                "not_authorized",
                f"readiness run plan commands[{index}] authorization state",
                failures,
            )
            for field in ("authorizationRefCandidate", "runnerAttestationRefCandidate"):
                _require_equal(
                    command.get(field),
                    None,
                    f"readiness run plan commands[{index}].{field}",
                    failures,
                )
            _require_equal(
                command.get("executionAllowed"),
                False,
                f"readiness run plan commands[{index}].executionAllowed",
                failures,
            )
    reservations = plan.get("candidateArtifactReservations")
    if isinstance(reservations, list):
        for index, reservation in enumerate(reservations):
            reservation = _exact_object(
                reservation,
                RUN_PLAN_RESERVATION_FIELDS,
                f"readiness run plan reservations[{index}]",
                failures,
            )
            _require_equal(
                reservation.get("artifactPresent"),
                False,
                f"readiness run plan reservations[{index}].artifactPresent",
                failures,
            )
            _require_equal(
                reservation.get("acquisitionAuthorized"),
                False,
                f"readiness run plan reservations[{index}].acquisitionAuthorized",
                failures,
            )
    state = plan.get("state")
    if not isinstance(state, dict) or not state or any(value is not False for value in state.values()):
        failures.append("readiness run plan state must contain only exact false values")
    return tuple(failures)


def compile_dormant_baseline_evidence_readiness_plan(
    profile_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
) -> tuple[bytes, str]:
    """Compile a deterministic non-executable plan from supplied bytes only."""

    failures: list[str] = []
    context = _validated_context(profile_bytes, lineage_blobs, failures)
    if context is None:
        raise ValueError("baseline evidence readiness profile is invalid: " + "; ".join(failures))
    profile_raw, _, profile, _ = context
    plan = _build_run_plan(profile_raw, profile)
    plan_raw = _ordered_bytes(plan, "baseline evidence readiness plan", failures)
    if plan_raw is None:
        raise ValueError("baseline evidence readiness plan is invalid: " + "; ".join(failures))
    parsed = receipt._parse_object(plan_raw, "baseline evidence readiness plan", failures)
    if parsed is not None:
        failures.extend(
            _collect_run_plan_failures(parsed, profile_raw=profile_raw, profile=profile)
        )
    if failures or parsed is None:
        raise ValueError("baseline evidence readiness plan is invalid: " + "; ".join(failures))
    return plan_raw, _sha256(plan_raw)


def _snapshot_ordered_blobs(
    value: object,
    *,
    expected_count: int,
    label: str,
    failures: list[str],
) -> tuple[bytes, ...] | None:
    if not isinstance(value, tuple) or len(value) != expected_count:
        failures.append(f"{label} must be an exact {expected_count}-blob tuple")
        return None
    snapshots: list[bytes] = []
    total_bytes = 0
    for index, blob in enumerate(value):
        snapshot = receipt._bounded_snapshot(
            blob,
            f"{label}[{index}]",
            MAX_MANIFEST_BLOB_BYTES,
            failures,
        )
        if snapshot is None:
            continue
        total_bytes += len(snapshot)
        if total_bytes > MAX_TOTAL_MANIFEST_BYTES:
            failures.append(
                f"{label} exceeds {MAX_TOTAL_MANIFEST_BYTES} total bytes"
            )
            return None
        snapshots.append(snapshot)
    if len(snapshots) != expected_count:
        return None
    return tuple(snapshots)


def _forbid_extra_blob_tuple(
    value: object,
    *,
    label: str,
    failures: list[str],
) -> None:
    if value is not None and value != ():
        failures.append(f"{label} must be absent for this evidence kind")


def _validate_manifest(
    manifest: object,
    *,
    evidence_kind: str,
    plan: dict[str, object],
    effective_v3: dict[str, object],
    lineage_blobs: tuple[bytes, ...],
    source_blobs: object,
    manifest_blobs: object,
    failures: list[str],
) -> tuple[dict[str, object], str | None, dict[str, bytes]]:
    manifest = _exact_object(manifest, MANIFEST_FIELDS, "candidate manifest", failures)
    _require_equal(
        manifest.get("serialization"),
        "utf8_compact_json_manifest_entry_field_order_v1",
        "candidate manifest serialization",
        failures,
    )
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        failures.append("candidate manifest entries must be a list")
        return manifest, None, {}
    if not 0 < len(entries) <= MAX_MANIFEST_ENTRIES:
        failures.append("candidate manifest entry count is outside the profile bound")
    seen_roles: set[str] = set()
    claimed_total_bytes = 0
    for index, raw_entry in enumerate(entries):
        entry = _exact_object(
            raw_entry, MANIFEST_ENTRY_FIELDS, f"candidate manifest entries[{index}]", failures
        )
        role = entry.get("inputRole")
        if not isinstance(role, str) or not role or role in seen_roles:
            failures.append(f"candidate manifest entries[{index}].inputRole is invalid or duplicated")
        else:
            seen_roles.add(role)
        source_ref = entry.get("sourceRef")
        if not isinstance(source_ref, str) or not source_ref or source_ref != source_ref.strip():
            failures.append(f"candidate manifest entries[{index}].sourceRef is invalid")
        elif source_ref.startswith("/") or ".." in source_ref.split("/"):
            failures.append(f"candidate manifest entries[{index}].sourceRef is unsafe")
        if entry.get("contentType") not in (
            "application/json",
            "application/octet-stream",
            "text/plain",
        ):
            failures.append(f"candidate manifest entries[{index}].contentType is invalid")
        byte_length = entry.get("byteLength")
        if (
            not _exact_positive_integer(byte_length)
            or byte_length > MAX_MANIFEST_BLOB_BYTES
        ):
            failures.append(f"candidate manifest entries[{index}].byteLength is invalid")
        else:
            claimed_total_bytes += byte_length
        if not _valid_sha256(entry.get("rawSha256")):
            failures.append(f"candidate manifest entries[{index}].rawSha256 is invalid")
        canonical = entry.get("canonicalSha256")
        if canonical is not None and not _valid_sha256(canonical):
            failures.append(f"candidate manifest entries[{index}].canonicalSha256 is invalid")
    if claimed_total_bytes > MAX_TOTAL_MANIFEST_BYTES:
        failures.append("candidate manifest claimed byte total exceeds the profile bound")

    observed_blobs: tuple[bytes, ...] | None = None

    if evidence_kind == "canonical_assurance_hash":
        _forbid_extra_blob_tuple(
            source_blobs, label="source blobs", failures=failures
        )
        _forbid_extra_blob_tuple(
            manifest_blobs, label="manifest blobs", failures=failures
        )
        expected = [
            {
                "inputRole": role,
                "sourceRef": path,
                "contentType": "application/json",
                "byteLength": len(raw),
                "rawSha256": raw_sha,
                "canonicalSha256": canonical_sha,
            }
            for role, path, raw, raw_sha, canonical_sha in zip(
                receipt.LINEAGE_ROLES,
                receipt.LINEAGE_PATHS,
                lineage_blobs,
                receipt.LINEAGE_RAW_SHA256,
                receipt.LINEAGE_CANONICAL_SHA256,
            )
        ]
        if len(entries) != len(expected):
            failures.append("canonical assurance manifest must contain six entries")
        for index, (entry, expected_entry) in enumerate(zip(entries, expected)):
            for field in MANIFEST_ENTRY_FIELDS:
                _require_equal(
                    entry.get(field) if isinstance(entry, dict) else None,
                    expected_entry[field],
                    f"canonical assurance manifest entries[{index}].{field}",
                    failures,
                )
    elif evidence_kind == "source_hash_readback":
        _forbid_extra_blob_tuple(
            manifest_blobs, label="manifest blobs", failures=failures
        )
        source_records = effective_v3.get("sourceRecords")
        if not isinstance(source_records, list) or len(source_records) != 29:
            failures.append("effective V3 must contain exactly 29 source records")
        else:
            if len(entries) != len(source_records):
                failures.append("source readback manifest must contain exactly 29 entries")
            for index, (entry, source) in enumerate(zip(entries, source_records)):
                if not isinstance(entry, dict) or not isinstance(source, dict):
                    failures.append(f"source readback manifest entries[{index}] is invalid")
                    continue
                for field, expected in (
                    ("inputRole", source.get("role")),
                    ("sourceRef", source.get("path")),
                    (
                        "contentType",
                        "application/json"
                        if isinstance(source.get("path"), str)
                        and source["path"].endswith(".json")
                        else "text/plain",
                    ),
                    ("rawSha256", source.get("sha256")),
                    ("canonicalSha256", None),
                ):
                    _require_equal(
                        entry.get(field),
                        expected,
                        f"source readback manifest entries[{index}].{field}",
                        failures,
                    )
            observed_blobs = _snapshot_ordered_blobs(
                source_blobs,
                expected_count=len(source_records),
                label="source readback blobs",
                failures=failures,
            )
    else:
        _forbid_extra_blob_tuple(
            source_blobs, label="source blobs", failures=failures
        )
        expected_roles = plan.get("requiredManifestRoles")
        actual_roles = [entry.get("inputRole") for entry in entries if isinstance(entry, dict)]
        _require_equal(actual_roles, expected_roles, "execution manifest role order", failures)
        if isinstance(expected_roles, list):
            for index, role in enumerate(expected_roles):
                entry = entries[index] if index < len(entries) else None
                expected_source_ref = f"observation/{role.replace('_', '-')}"
                _require_equal(
                    entry.get("sourceRef") if isinstance(entry, dict) else None,
                    expected_source_ref,
                    f"execution manifest entries[{index}].sourceRef",
                    failures,
                )
                _require_equal(
                    entry.get("canonicalSha256") if isinstance(entry, dict) else None,
                    None,
                    f"execution manifest entries[{index}].canonicalSha256",
                    failures,
                )
            observed_blobs = _snapshot_ordered_blobs(
                manifest_blobs,
                expected_count=len(expected_roles),
                label="execution manifest blobs",
                failures=failures,
            )

    observed_by_role: dict[str, bytes] = {}
    if observed_blobs is not None:
        for index, (entry, raw) in enumerate(zip(entries, observed_blobs)):
            if not isinstance(entry, dict):
                continue
            _require_equal(
                entry.get("byteLength"),
                len(raw),
                f"candidate manifest entries[{index}] observed byteLength",
                failures,
            )
            _require_equal(
                entry.get("rawSha256"),
                _sha256(raw),
                f"candidate manifest entries[{index}] observed raw SHA-256",
                failures,
            )
            role = entry.get("inputRole")
            if isinstance(role, str):
                observed_by_role[role] = raw

    encoded_entries = _ordered_bytes(entries, "candidate manifest entries", failures)
    digest = None if encoded_entries is None else _sha256(encoded_entries)
    _require_equal(
        manifest.get("entriesCanonicalSha256"),
        digest,
        "candidate manifest entries digest",
        failures,
    )
    return manifest, digest, observed_by_role


def _validate_static_payload(
    payload: object,
    *,
    evidence_kind: str,
    effective_v3: dict[str, object],
    failures: list[str],
) -> None:
    if evidence_kind == "canonical_assurance_hash":
        payload = _exact_object(
            payload, STATIC_ASSURANCE_PAYLOAD_FIELDS, "static assurance payload", failures
        )
        expected = {
            "lineageRawSha256": list(receipt.LINEAGE_RAW_SHA256),
            "lineageCanonicalSha256": list(receipt.LINEAGE_CANONICAL_SHA256),
            "effectiveAssuranceCanonicalSha256": receipt.EXPECTED_EFFECTIVE_V3_SHA256,
            "effectiveClosureCanonicalSha256": receipt.EXPECTED_CLOSURE_V3_SHA256,
        }
    else:
        payload = _exact_object(
            payload, STATIC_SOURCE_PAYLOAD_FIELDS, "static source payload", failures
        )
        source_records = effective_v3.get("sourceRecords")
        source_digest = _canonical_sha256(
            source_records, "effective V3 source records", failures
        )
        expected = {
            "sourceRecordCount": 29,
            "sourceRecordsCanonicalSha256": source_digest,
            "mismatchCount": 0,
        }
    _require_equal(payload, expected, f"{evidence_kind} payload", failures)


def _validate_execution_payload(
    payload: object,
    *,
    plan: dict[str, object],
    contract: dict[str, object],
    manifest_blobs_by_role: dict[str, bytes],
    failures: list[str],
) -> None:
    payload = _exact_object(payload, EXECUTION_PAYLOAD_FIELDS, "execution payload", failures)
    session_ref = payload.get("executionSessionRefCandidate")
    if not isinstance(session_ref, str) or SESSION_REF_PATTERN.fullmatch(session_ref) is None:
        failures.append("execution payload session candidate reference is invalid")
    authority_ref = payload.get("authorizationRefCandidate")
    if not isinstance(authority_ref, str) or AUTHORITY_REF_PATTERN.fullmatch(authority_ref) is None:
        failures.append("execution payload authority candidate reference is invalid")
    for field, expected in (
        ("sourcePublicationCommit", contract.get("publicationCommitObjectId")),
        ("commandProfileId", plan.get("commandProfileId")),
        ("commandProfileSha256", plan.get("commandProfileSha256")),
        ("commandArgvSha256", plan.get("commandArgvSha256")),
        ("allowedSideEffectsSha256", plan.get("allowedSideEffectsSha256")),
        ("stepIndex", plan.get("commandStepIndex")),
        ("stepId", plan.get("commandStepId")),
        ("stepArgvSha256", plan.get("commandStepArgvSha256")),
    ):
        _require_equal(payload.get(field), expected, f"execution payload {field}", failures)
    for field in (
        "workingDirectorySha256",
        "environmentSha256",
        "toolchainManifestSha256",
        "dependencyManifestSha256",
        "observationManifestSha256",
        "sanitizedLogSha256",
        "outputManifestSha256",
    ):
        if not _valid_sha256(payload.get(field)):
            failures.append(f"execution payload {field} is invalid")
    output_role = {
        "full_no_device_aggregate": "output_manifest",
        "android_and_macos_release_compilation": (
            "unsigned_android_release_output_manifest"
            if plan.get("commandStepIndex") == 0
            else "unsigned_macos_release_output_manifest"
        ),
    }.get(plan.get("checkId"))
    role_to_payload_field = {
        "sanitized_ordered_stdout_stderr": "sanitizedLogSha256",
        "working_directory": "workingDirectorySha256",
        "environment": "environmentSha256",
        "toolchain": "toolchainManifestSha256",
        "dependencies": "dependencyManifestSha256",
        "egress_process_observation_manifest": "observationManifestSha256",
    }
    if isinstance(output_role, str):
        role_to_payload_field[output_role] = "outputManifestSha256"
    for role, field in role_to_payload_field.items():
        raw = manifest_blobs_by_role.get(role)
        if raw is None:
            failures.append(f"execution manifest blob role {role} is missing")
            continue
        _require_equal(
            payload.get(field),
            _sha256(raw),
            f"execution payload {field} manifest binding",
            failures,
        )
    if plan.get("checkId") == "full_no_device_aggregate":
        log_bytes = manifest_blobs_by_role.get("sanitized_ordered_stdout_stderr")
        marker_count = (
            sum(line == NO_DEVICE_SUCCESS_MARKER for line in log_bytes.splitlines())
            if isinstance(log_bytes, bytes)
            else 0
        )
        if marker_count != 1:
            failures.append(
                "full no-device sanitized log must contain the exact success marker once"
            )


def _collect_candidate_snapshot_failures(
    candidate_raw: bytes,
    *,
    profile_raw: bytes,
    immutable_lineage: tuple[bytes, ...],
    profile: dict[str, object],
    effective_v3: dict[str, object],
    source_blobs: object,
    manifest_blobs: object,
) -> tuple[tuple[str, ...], dict[str, object] | None]:
    failures: list[str] = []
    candidate = receipt._parse_object(
        candidate_raw, "G0 baseline evidence candidate", failures
    )
    if candidate is None:
        return tuple(failures), None
    receipt._validate_json_resources(
        candidate,
        failures,
        root_label="G0 baseline evidence candidate",
        maximum_depth=MAX_JSON_DEPTH,
        maximum_items=MAX_JSON_ITEMS,
        maximum_string_bytes=MAX_STRING_BYTES,
    )
    canonical_candidate_raw = _ordered_bytes(
        candidate, "G0 baseline evidence candidate", failures
    )
    _require_equal(
        candidate_raw,
        canonical_candidate_raw,
        "candidate compact canonical bytes",
        failures,
    )
    candidate = _exact_object(candidate, CANDIDATE_FIELDS, "baseline evidence candidate", failures)
    _require_equal(
        candidate.get("documentType"),
        "aetherlink.v1-g0-baseline-evidence-candidate",
        "candidate documentType",
        failures,
    )
    _require_equal(candidate.get("schemaVersion"), 1, "candidate schemaVersion", failures)
    _require_equal(
        candidate.get("status"),
        "prepared_unverified_non_authorizing",
        "candidate status",
        failures,
    )
    evidence_kind = candidate.get("evidenceKind")
    if not isinstance(evidence_kind, str) or evidence_kind not in EVIDENCE_KINDS:
        failures.append("candidate evidenceKind is unknown, derived, or forbidden")
        return tuple(failures), candidate
    _require_equal(
        candidate.get("artifactId"),
        _artifact_id(evidence_kind),
        "candidate artifactId",
        failures,
    )
    profile_ref = _exact_object(
        candidate.get("profileRef"), PROFILE_REF_FIELDS, "candidate profileRef", failures
    )
    _require_equal(
        profile_ref,
        {
            "path": PROFILE_PATH,
            "profileId": profile.get("profileId"),
            "rawSha256": _sha256(profile_raw),
        },
        "candidate profileRef",
        failures,
    )
    contract = _exact_object(
        candidate.get("contractBinding"), CONTRACT_FIELDS, "candidate contractBinding", failures
    )
    _require_equal(contract, profile.get("contractBinding"), "candidate contractBinding", failures)
    plan_index = EVIDENCE_KINDS.index(evidence_kind)
    source_plan = profile["evidencePlans"][plan_index]
    expected_plan = {field: source_plan[field] for field in CANDIDATE_PLAN_FIELDS}
    plan = _exact_object(
        candidate.get("plan"), CANDIDATE_PLAN_FIELDS, "candidate plan", failures
    )
    _require_equal(plan, expected_plan, "candidate plan", failures)
    _, manifest_digest, observed_blobs_by_role = _validate_manifest(
        candidate.get("manifest"),
        evidence_kind=evidence_kind,
        plan=plan,
        effective_v3=effective_v3,
        lineage_blobs=immutable_lineage,
        source_blobs=source_blobs,
        manifest_blobs=manifest_blobs,
        failures=failures,
    )
    result = _exact_object(candidate.get("result"), RESULT_FIELDS, "candidate result", failures)
    expected_result_profile = profile["resultProfiles"][plan_index]
    _require_equal(
        result.get("resultClass"),
        expected_result_profile.get("resultClass"),
        "candidate result class",
        failures,
    )
    _require_equal(
        result.get("manifestCanonicalSha256"),
        manifest_digest,
        "candidate result manifest digest",
        failures,
    )
    if evidence_kind in EXECUTION_EVIDENCE_KINDS:
        started = receipt._parse_canonical_utc(
            result.get("startedAt"), "candidate result startedAt", failures
        )
        completed = receipt._parse_canonical_utc(
            result.get("completedAt"), "candidate result completedAt", failures
        )
        if isinstance(started, datetime) and isinstance(completed, datetime) and started > completed:
            failures.append("candidate result timestamps are reversed")
        if not receipt._exact_zero(result.get("exitCode")):
            failures.append("candidate result exitCode must be exact integer zero")
        _validate_execution_payload(
            result.get("payload"),
            plan=plan,
            contract=contract,
            manifest_blobs_by_role=observed_blobs_by_role,
            failures=failures,
        )
    else:
        for field in ("startedAt", "completedAt", "exitCode"):
            _require_equal(result.get(field), None, f"static result {field}", failures)
        _validate_static_payload(
            result.get("payload"),
            evidence_kind=evidence_kind,
            effective_v3=effective_v3,
            failures=failures,
        )
    trust = _exact_object(
        candidate.get("trustBoundary"),
        TRUST_BOUNDARY_FIELDS,
        "candidate trustBoundary",
        failures,
    )
    _require_equal(
        trust.get("observationClass"),
        "synthetic_fixture_or_unverified_session_observation_only",
        "candidate trustBoundary observationClass",
        failures,
    )
    _require_equal(
        trust.get("independentInputsPresent"),
        [],
        "candidate trustBoundary independentInputsPresent",
        failures,
    )
    _require_equal(
        trust.get("requiredIndependentInputsAbsent"),
        list(REQUIRED_INDEPENDENT_INPUTS_ABSENT),
        "candidate trustBoundary requiredIndependentInputsAbsent",
        failures,
    )
    for field in (
        "catalogRecordDerivable",
        "authorityDerivable",
        "runnerAttestationDerivable",
        "gateReceiptDerivable",
    ):
        _require_equal(trust.get(field), False, f"candidate trustBoundary {field}", failures)
    state = _exact_object(candidate.get("state"), STATE_FIELDS, "candidate state", failures)
    if any(value is not False for value in state.values()) or len(state) != len(STATE_FIELDS):
        failures.append("candidate state must contain only the exact seven false values")
    return tuple(failures), candidate


def collect_baseline_evidence_candidate_failures(
    candidate_bytes: object,
    *,
    profile_bytes: object,
    lineage_blobs: tuple[object, ...],
    source_blobs: tuple[object, ...] | None = None,
    manifest_blobs: tuple[object, ...] | None = None,
) -> tuple[str, ...]:
    """Validate supplied candidate and observation bytes, always staying dormant."""

    failures: list[str] = []
    candidate_raw = receipt._bounded_snapshot(
        candidate_bytes,
        "G0 baseline evidence candidate",
        MAX_CANDIDATE_BYTES,
        failures,
    )
    context = _validated_context(profile_bytes, lineage_blobs, failures)
    if candidate_raw is None or context is None:
        return _finish_candidate_failures(failures)
    profile_raw, immutable_lineage, profile, effective_v3 = context
    candidate_failures, _ = _collect_candidate_snapshot_failures(
        candidate_raw,
        profile_raw=profile_raw,
        immutable_lineage=immutable_lineage,
        profile=profile,
        effective_v3=effective_v3,
        source_blobs=source_blobs,
        manifest_blobs=manifest_blobs,
    )
    failures.extend(candidate_failures)
    return _finish_candidate_failures(failures)


def _build_static_candidate(
    evidence_kind: str,
    *,
    profile_raw: bytes,
    immutable_lineage: tuple[bytes, ...],
    source_snapshots: tuple[bytes, ...],
    profile: dict[str, object],
    effective_v3: dict[str, object],
    failures: list[str],
) -> dict[str, object] | None:
    if evidence_kind not in STATIC_EVIDENCE_KINDS:
        failures.append("static candidate compiler received a non-static evidence kind")
        return None
    plan_index = EVIDENCE_KINDS.index(evidence_kind)
    source_plan = profile["evidencePlans"][plan_index]
    plan = {field: source_plan[field] for field in CANDIDATE_PLAN_FIELDS}
    if evidence_kind == "canonical_assurance_hash":
        entries = [
            {
                "inputRole": role,
                "sourceRef": path,
                "contentType": "application/json",
                "byteLength": len(raw),
                "rawSha256": raw_sha,
                "canonicalSha256": canonical_sha,
            }
            for role, path, raw, raw_sha, canonical_sha in zip(
                receipt.LINEAGE_ROLES,
                receipt.LINEAGE_PATHS,
                immutable_lineage,
                receipt.LINEAGE_RAW_SHA256,
                receipt.LINEAGE_CANONICAL_SHA256,
            )
        ]
        payload: dict[str, object] = {
            "lineageRawSha256": list(receipt.LINEAGE_RAW_SHA256),
            "lineageCanonicalSha256": list(receipt.LINEAGE_CANONICAL_SHA256),
            "effectiveAssuranceCanonicalSha256": receipt.EXPECTED_EFFECTIVE_V3_SHA256,
            "effectiveClosureCanonicalSha256": receipt.EXPECTED_CLOSURE_V3_SHA256,
        }
    else:
        source_records = effective_v3.get("sourceRecords")
        if not isinstance(source_records, list) or len(source_records) != 29:
            failures.append("static candidate compiler requires exactly 29 source records")
            return None
        if len(source_snapshots) != len(source_records):
            failures.append("static candidate compiler requires exactly 29 source blobs")
            return None
        entries = []
        for index, (source, raw) in enumerate(zip(source_records, source_snapshots)):
            if not isinstance(source, dict):
                failures.append(f"static candidate source record {index} is invalid")
                return None
            path = source.get("path")
            entries.append(
                {
                    "inputRole": source.get("role"),
                    "sourceRef": path,
                    "contentType": (
                        "application/json"
                        if isinstance(path, str) and path.endswith(".json")
                        else "text/plain"
                    ),
                    "byteLength": len(raw),
                    "rawSha256": source.get("sha256"),
                    "canonicalSha256": None,
                }
            )
        source_records_digest = _canonical_sha256(
            source_records, "effective V3 source records", failures
        )
        if source_records_digest is None:
            return None
        payload = {
            "sourceRecordCount": len(source_records),
            "sourceRecordsCanonicalSha256": source_records_digest,
            "mismatchCount": 0,
        }
    encoded_entries = _ordered_bytes(entries, "compiled static manifest entries", failures)
    if encoded_entries is None:
        return None
    manifest_digest = _sha256(encoded_entries)
    result_profile = profile["resultProfiles"][plan_index]
    return {
        "documentType": "aetherlink.v1-g0-baseline-evidence-candidate",
        "schemaVersion": 1,
        "artifactId": _artifact_id(evidence_kind),
        "evidenceKind": evidence_kind,
        "status": "prepared_unverified_non_authorizing",
        "profileRef": {
            "path": PROFILE_PATH,
            "profileId": profile["profileId"],
            "rawSha256": _sha256(profile_raw),
        },
        "contractBinding": profile["contractBinding"],
        "plan": plan,
        "manifest": {
            "serialization": "utf8_compact_json_manifest_entry_field_order_v1",
            "entries": entries,
            "entriesCanonicalSha256": manifest_digest,
        },
        "result": {
            "resultClass": result_profile["resultClass"],
            "manifestCanonicalSha256": manifest_digest,
            "startedAt": None,
            "completedAt": None,
            "exitCode": None,
            "payload": payload,
        },
        "trustBoundary": {
            "observationClass": "synthetic_fixture_or_unverified_session_observation_only",
            "independentInputsPresent": [],
            "requiredIndependentInputsAbsent": list(REQUIRED_INDEPENDENT_INPUTS_ABSENT),
            "catalogRecordDerivable": False,
            "authorityDerivable": False,
            "runnerAttestationDerivable": False,
            "gateReceiptDerivable": False,
        },
        "state": {field: False for field in STATE_FIELDS},
    }


def compile_dormant_static_baseline_evidence_pair(
    profile_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
    source_blobs: tuple[object, ...],
) -> tuple[tuple[bytes, str], tuple[bytes, str]]:
    """Compile the two static candidates in fixed order without I/O or authority."""

    failures: list[str] = []
    context = _validated_context(profile_bytes, lineage_blobs, failures)
    if context is None:
        raise ValueError(
            "static baseline evidence context is invalid: " + "; ".join(failures)
        )
    profile_raw, immutable_lineage, profile, effective_v3 = context
    source_snapshots = _snapshot_ordered_blobs(
        source_blobs,
        expected_count=29,
        label="static compiler source blobs",
        failures=failures,
    )
    if source_snapshots is None:
        raise ValueError(
            "static baseline evidence inputs are invalid: " + "; ".join(failures)
        )
    compiled: list[tuple[bytes, str]] = []
    for evidence_kind in STATIC_EVIDENCE_KINDS:
        candidate = _build_static_candidate(
            evidence_kind,
            profile_raw=profile_raw,
            immutable_lineage=immutable_lineage,
            source_snapshots=source_snapshots,
            profile=profile,
            effective_v3=effective_v3,
            failures=failures,
        )
        if candidate is None:
            break
        candidate_raw = _ordered_bytes(
            candidate, f"compiled {evidence_kind} candidate", failures
        )
        if candidate_raw is None:
            break
        if len(candidate_raw) > MAX_CANDIDATE_BYTES:
            failures.append(f"compiled {evidence_kind} candidate exceeds the byte bound")
            break
        candidate_failures, _ = _collect_candidate_snapshot_failures(
            candidate_raw,
            profile_raw=profile_raw,
            immutable_lineage=immutable_lineage,
            profile=profile,
            effective_v3=effective_v3,
            source_blobs=(
                source_snapshots if evidence_kind == "source_hash_readback" else None
            ),
            manifest_blobs=None,
        )
        if candidate_failures:
            failures.extend(
                f"compiled {evidence_kind}: {failure}"
                for failure in candidate_failures
            )
            break
        compiled.append((candidate_raw, _sha256(candidate_raw)))
    if failures or len(compiled) != len(STATIC_EVIDENCE_KINDS):
        raise ValueError(
            "static baseline evidence compilation failed: " + "; ".join(failures)
        )
    return compiled[0], compiled[1]


def collect_static_candidate_pair_failures(
    assurance_candidate_bytes: object,
    source_candidate_bytes: object,
    *,
    profile_bytes: object,
    lineage_blobs: tuple[object, ...],
    source_blobs: tuple[object, ...],
) -> tuple[str, ...]:
    """Cross-bind the two supplied static candidates while remaining dormant."""

    failures: list[str] = []
    assurance_raw = receipt._bounded_snapshot(
        assurance_candidate_bytes,
        "canonical assurance static candidate",
        MAX_CANDIDATE_BYTES,
        failures,
    )
    source_raw = receipt._bounded_snapshot(
        source_candidate_bytes,
        "source readback static candidate",
        MAX_CANDIDATE_BYTES,
        failures,
    )
    context = _validated_context(profile_bytes, lineage_blobs, failures)
    source_snapshots = _snapshot_ordered_blobs(
        source_blobs,
        expected_count=29,
        label="static pair source blobs",
        failures=failures,
    )
    if (
        assurance_raw is None
        or source_raw is None
        or context is None
        or source_snapshots is None
    ):
        return _finish_candidate_failures(failures)
    profile_raw, immutable_lineage, profile, effective_v3 = context
    assurance_failures, assurance = _collect_candidate_snapshot_failures(
        assurance_raw,
        profile_raw=profile_raw,
        immutable_lineage=immutable_lineage,
        profile=profile,
        effective_v3=effective_v3,
        source_blobs=None,
        manifest_blobs=None,
    )
    source_failures, source = _collect_candidate_snapshot_failures(
        source_raw,
        profile_raw=profile_raw,
        immutable_lineage=immutable_lineage,
        profile=profile,
        effective_v3=effective_v3,
        source_blobs=source_snapshots,
        manifest_blobs=None,
    )
    failures.extend(assurance_failures)
    failures.extend(source_failures)
    if isinstance(assurance, dict) and isinstance(source, dict):
        _require_equal(
            assurance.get("evidenceKind"),
            "canonical_assurance_hash",
            "static pair assurance evidence kind",
            failures,
        )
        _require_equal(
            source.get("evidenceKind"),
            "source_hash_readback",
            "static pair source evidence kind",
            failures,
        )
        for field in ("profileRef", "contractBinding", "trustBoundary", "state"):
            _require_equal(
                source.get(field),
                assurance.get(field),
                f"static pair shared {field}",
                failures,
            )
        assurance_plan = assurance.get("plan")
        source_plan = source.get("plan")
        if isinstance(assurance_plan, dict) and isinstance(source_plan, dict):
            _require_equal(
                source_plan.get("checkId"),
                assurance_plan.get("checkId"),
                "static pair shared checkId",
                failures,
            )
    return _finish_candidate_failures(failures)


def collect_release_candidate_pair_failures(
    android_candidate_bytes: object,
    macos_candidate_bytes: object,
    *,
    profile_bytes: object,
    lineage_blobs: tuple[object, ...],
    android_manifest_blobs: tuple[object, ...],
    macos_manifest_blobs: tuple[object, ...],
) -> tuple[str, ...]:
    """Cross-bind two structurally valid unverified release observations."""

    failures: list[str] = []
    android_raw = receipt._bounded_snapshot(
        android_candidate_bytes,
        "Android release candidate",
        MAX_CANDIDATE_BYTES,
        failures,
    )
    macos_raw = receipt._bounded_snapshot(
        macos_candidate_bytes,
        "macOS release candidate",
        MAX_CANDIDATE_BYTES,
        failures,
    )
    context = _validated_context(profile_bytes, lineage_blobs, failures)
    if android_raw is None or macos_raw is None or context is None:
        return _finish_candidate_failures(failures)
    profile_raw, immutable_lineage, profile, effective_v3 = context
    android_failures, android = _collect_candidate_snapshot_failures(
        android_raw,
        profile_raw=profile_raw,
        immutable_lineage=immutable_lineage,
        profile=profile,
        effective_v3=effective_v3,
        source_blobs=None,
        manifest_blobs=android_manifest_blobs,
    )
    macos_failures, macos = _collect_candidate_snapshot_failures(
        macos_raw,
        profile_raw=profile_raw,
        immutable_lineage=immutable_lineage,
        profile=profile,
        effective_v3=effective_v3,
        source_blobs=None,
        manifest_blobs=macos_manifest_blobs,
    )
    failures.extend(android_failures)
    failures.extend(macos_failures)
    if isinstance(android, dict) and isinstance(macos, dict):
        _require_equal(
            android.get("evidenceKind"),
            "android_release_compile_result",
            "release pair Android evidence kind",
            failures,
        )
        _require_equal(
            macos.get("evidenceKind"),
            "macos_release_compile_result",
            "release pair macOS evidence kind",
            failures,
        )
        android_result = android.get("result")
        macos_result = macos.get("result")
        if isinstance(android_result, dict) and isinstance(macos_result, dict):
            android_payload = android_result.get("payload")
            macos_payload = macos_result.get("payload")
            if isinstance(android_payload, dict) and isinstance(macos_payload, dict):
                for field in (
                    "executionSessionRefCandidate",
                    "authorizationRefCandidate",
                    "sourcePublicationCommit",
                    "commandProfileId",
                    "commandProfileSha256",
                    "commandArgvSha256",
                    "workingDirectorySha256",
                    "environmentSha256",
                    "allowedSideEffectsSha256",
                    "toolchainManifestSha256",
                    "dependencyManifestSha256",
                    "observationManifestSha256",
                    "sanitizedLogSha256",
                ):
                    _require_equal(
                        macos_payload.get(field),
                        android_payload.get(field),
                        f"release pair shared {field}",
                        failures,
                    )
            android_manifest = android.get("manifest")
            macos_manifest = macos.get("manifest")
            if isinstance(android_manifest, dict) and isinstance(macos_manifest, dict):
                android_entries = android_manifest.get("entries")
                macos_entries = macos_manifest.get("entries")
                common_roles = profile["evidencePlans"][3][
                    "requiredManifestRoles"
                ][:-1]
                if isinstance(android_entries, list) and isinstance(macos_entries, list):
                    android_by_role = {
                        entry.get("inputRole"): entry
                        for entry in android_entries
                        if isinstance(entry, dict)
                    }
                    macos_by_role = {
                        entry.get("inputRole"): entry
                        for entry in macos_entries
                        if isinstance(entry, dict)
                    }
                    for role in common_roles:
                        _require_equal(
                            macos_by_role.get(role),
                            android_by_role.get(role),
                            f"release pair shared manifest role {role}",
                            failures,
                        )
            android_completed = receipt._parse_canonical_utc(
                android_result.get("completedAt"), "Android release completedAt", failures
            )
            macos_started = receipt._parse_canonical_utc(
                macos_result.get("startedAt"), "macOS release startedAt", failures
            )
            if (
                isinstance(android_completed, datetime)
                and isinstance(macos_started, datetime)
                and android_completed > macos_started
            ):
                failures.append("release pair step time order is reversed")
    return _finish_candidate_failures(failures)


def _collect_absent_candidate_failures(root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    for kind in EVIDENCE_KINDS:
        path = _artifact_path(kind)
        try:
            (root / path).lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            failures.append(f"could not confirm absent readiness artifact {path}: {error}")
        else:
            failures.append(f"readiness artifact {path} must remain absent")
    return tuple(failures)


def _collect_worktree_failures(root: Path = ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    lineage: list[bytes] = []
    lineage_identities: list[tuple[int, int, int, int, int, int]] = []
    for role, path, maximum_bytes in zip(
        receipt.LINEAGE_ROLES,
        receipt.LINEAGE_PATHS,
        receipt.LINEAGE_MAXIMUM_BYTES,
    ):
        try:
            raw, identity = decision.read_g0_content_addressed_snapshot(
                root, path, f"G0 readiness lineage {role}", maximum_bytes
            )
        except receipt.checkpoint.CheckpointValidationError as error:
            failures.append(str(error))
            continue
        lineage.append(raw)
        lineage_identities.append(identity)
    try:
        profile_raw, profile_identity = decision.read_g0_content_addressed_snapshot(
            root, PROFILE_PATH, "G0 baseline evidence readiness profile", MAX_PROFILE_BYTES
        )
    except receipt.checkpoint.CheckpointValidationError as error:
        failures.append(str(error))
        return tuple(failures)
    if len(lineage) != len(receipt.LINEAGE_PATHS):
        return tuple(failures)
    failures.extend(
        collect_baseline_evidence_readiness_profile_failures(
            profile_raw, lineage_blobs=tuple(lineage)
        )
    )
    try:
        plan_raw, _ = compile_dormant_baseline_evidence_readiness_plan(
            profile_raw, lineage_blobs=tuple(lineage)
        )
        plan = receipt._parse_object(plan_raw, "compiled readiness plan", failures)
        profile = receipt._parse_object(profile_raw, "readiness profile", failures)
        if isinstance(plan, dict) and isinstance(profile, dict):
            failures.extend(
                _collect_run_plan_failures(
                    plan, profile_raw=profile_raw, profile=profile
                )
            )
    except ValueError as error:
        failures.append(str(error))
    failures.extend(_collect_absent_candidate_failures(root))
    for role, path, maximum_bytes, identity, expected_sha in zip(
        receipt.LINEAGE_ROLES,
        receipt.LINEAGE_PATHS,
        receipt.LINEAGE_MAXIMUM_BYTES,
        lineage_identities,
        receipt.LINEAGE_RAW_SHA256,
    ):
        failures.extend(
            decision.collect_g0_final_snapshot_failures(
                root, path, f"G0 readiness lineage {role}", maximum_bytes, identity, expected_sha
            )
        )
    failures.extend(
        decision.collect_g0_final_snapshot_failures(
            root,
            PROFILE_PATH,
            "G0 baseline evidence readiness profile",
            MAX_PROFILE_BYTES,
            profile_identity,
            EXPECTED_PROFILE_RAW_SHA256,
        )
    )
    failures.extend(_collect_absent_candidate_failures(root))
    return tuple(failures)


def main() -> int:
    failures = _collect_worktree_failures()
    if failures:
        for failure in failures:
            print(f"V1 G0 baseline evidence readiness validation failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 baseline evidence readiness profile and deterministic dormant plan "
        "match the exact effective V3 blocker, five non-derived evidence kinds, "
        "and two not-authorized command profiles; all five candidate artifacts "
        "remain absent, and no execution, verification, receipt, G0-exit, or G1a "
        "authority was created."
    )
    return 0


__all__ = [
    "collect_baseline_evidence_candidate_failures",
    "collect_baseline_evidence_readiness_profile_failures",
    "collect_release_candidate_pair_failures",
    "collect_static_candidate_pair_failures",
    "compile_dormant_baseline_evidence_readiness_plan",
    "compile_dormant_static_baseline_evidence_pair",
]


if __name__ == "__main__":
    raise SystemExit(main())
