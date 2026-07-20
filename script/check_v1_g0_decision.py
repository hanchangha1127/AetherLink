#!/usr/bin/env python3
"""Validate the bounded AetherLink V1 G0 decision and its closed authorities."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
import copy
from decimal import Decimal, DecimalException
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

try:
    from script import check_protocol_schema as active_protocol_checker
except ModuleNotFoundError:
    import check_protocol_schema as active_protocol_checker

try:
    from script import check_v1_g0_checkpoint as checkpoint_checker
except ModuleNotFoundError:
    import check_v1_g0_checkpoint as checkpoint_checker


ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "docs/v1/g0/decision-v1.json"
MARKDOWN_PATH = ROOT / "docs/v1/g0/decision-v1.md"
ASSURANCE_PATH = ROOT / "docs/v1/g0/assurance-v1.json"
ASSURANCE_MARKDOWN_PATH = ROOT / "docs/v1/g0/assurance-v1.md"
ASSURANCE_AMENDMENT_PATH = ROOT / "docs/v1/g0/assurance-closure-amendment-v2.json"
ASSURANCE_AMENDMENT_MARKDOWN_PATH = ROOT / "docs/v1/g0/assurance-closure-amendment-v2.md"
ASSURANCE_AMENDMENT_CHECKPOINT_PATH = (
    ROOT / "docs/v1/g0/assurance-closure-amendment-checkpoint-v2.json"
)


class DuplicateJSONKeyError(ValueError):
    pass


class NonFiniteJSONNumberError(ValueError):
    pass


class G0JSONNumberError(ValueError):
    pass


class ReleaseEvidenceNumberError(ValueError):
    pass


MAX_G0_JSON_INTEGER_DIGITS = 128
MAX_G0_ASSURANCE_AMENDMENT_BYTES = 1_048_576
MAX_G0_ASSURANCE_AMENDMENT_CHECKPOINT_BYTES = 1_048_576
G0_SHA256_PATTERN = r"^[0-9a-f]{64}$"
G0_GIT_OBJECT_ID_PATTERN = r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"
G0_AUTHORIZATION_REF_PATTERN = (
    r"^g0-authority-[a-z0-9][a-z0-9_-]{0,95}-v[1-9][0-9]*$"
)
G0_COMMAND_PROFILE_ID_PATTERN = (
    r"^g0-command-profile-[a-z0-9][a-z0-9_-]{0,95}-v[1-9][0-9]*$"
)
G0_CHECKPOINT_PATH_PATTERN = (
    r"^docs/v1/g0/assurance-checkpoint-readback-v[1-9][0-9]*\.json$"
)
MAX_RELEASE_EVIDENCE_BYTES = 4_194_304
MAX_RELEASE_EVIDENCE_SAMPLES = 100_000
MAX_RELEASE_EVIDENCE_INTEGER_DIGITS = 16
MAX_RELEASE_EVIDENCE_FRACTIONAL_DIGITS = 6
EXPECTED_VARIANT_OBSERVATION_FIELDS = [
    "attempt_index",
    "affected_scope",
    "affected_region",
    "direct_outcome",
    "fallback_outcome",
    "outage_connection_outcome",
    "outage_authentication_outcome",
    "outage_route",
    "recovery_route",
    "recovery_connection_outcome",
    "recovery_authentication_outcome",
    "condition_activated_offset_milliseconds",
    "condition_result_offset_milliseconds",
    "service_restored_offset_milliseconds",
    "recovery_authenticated_offset_milliseconds",
    "plaintext_downgrade_event_count",
    "identity_downgrade_event_count",
    "weaker_route_event_count",
    "post_consent_loss_traffic_event_count",
]


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(key)
        result[key] = value
    return result


def reject_non_finite(value: str) -> object:
    raise NonFiniteJSONNumberError(value)


def parse_g0_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise NonFiniteJSONNumberError(value)
    return parsed


def parse_g0_bounded_integer(value: str) -> int:
    digit_count = len(value) - (1 if value.startswith("-") else 0)
    if digit_count > MAX_G0_JSON_INTEGER_DIGITS:
        raise G0JSONNumberError(value)
    return int(value)


def parse_release_evidence_integer(value: str) -> int:
    if re.fullmatch(
        rf"(?:0|[1-9][0-9]{{0,{MAX_RELEASE_EVIDENCE_INTEGER_DIGITS - 1}}})",
        value,
    ) is None:
        raise ReleaseEvidenceNumberError(value)
    return int(value)


def parse_release_evidence_decimal(value: str) -> Decimal:
    if re.fullmatch(
        rf"(?:0|[1-9][0-9]{{0,{MAX_RELEASE_EVIDENCE_INTEGER_DIGITS - 1}}})"
        rf"\.[0-9]{{1,{MAX_RELEASE_EVIDENCE_FRACTIONAL_DIGITS}}}",
        value,
    ) is None:
        raise ReleaseEvidenceNumberError(value)
    return Decimal(value)


def canonical_release_evidence_json(value: object) -> bytes:
    """Encode the closed, cross-implementation release-evidence JSON profile."""

    def encode_decimal_exact(item: Decimal) -> str:
        if (
            not item.is_finite()
            or item < 0
            or (item.is_zero() and item.is_signed())
        ):
            raise ReleaseEvidenceNumberError(str(item))
        if item.is_zero():
            return "0"

        _, raw_digits, exponent = item.as_tuple()
        digits = list(raw_digits)
        original_fractional_digits = max(0, -exponent)
        if original_fractional_digits > MAX_RELEASE_EVIDENCE_FRACTIONAL_DIGITS:
            raise ReleaseEvidenceNumberError(str(item))

        # Remove only fractional trailing zeroes. Decimal.normalize() is not
        # used here because it obeys the process-wide decimal context and can
        # round distinct signed payload values to the same byte sequence.
        while exponent < 0 and digits[-1] == 0:
            digits.pop()
            exponent += 1

        fractional_digits = max(0, -exponent)
        integer_digits = max(1, len(digits) + exponent)
        if (
            fractional_digits > MAX_RELEASE_EVIDENCE_FRACTIONAL_DIGITS
            or integer_digits > MAX_RELEASE_EVIDENCE_INTEGER_DIGITS
        ):
            raise ReleaseEvidenceNumberError(str(item))

        coefficient = "".join(str(digit) for digit in digits)
        if exponent >= 0:
            return coefficient + ("0" * exponent)
        split = len(coefficient) + exponent
        if split > 0:
            return coefficient[:split] + "." + coefficient[split:]
        return "0." + ("0" * -split) + coefficient

    def encode(item: object) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, int):
            if item < 0 or len(str(item)) > MAX_RELEASE_EVIDENCE_INTEGER_DIGITS:
                raise ReleaseEvidenceNumberError(str(item))
            return str(item)
        if isinstance(item, Decimal):
            return encode_decimal_exact(item)
        if isinstance(item, float):
            if (
                not math.isfinite(item)
                or item < 0
                or (item == 0 and math.copysign(1.0, item) < 0)
            ):
                raise ReleaseEvidenceNumberError(repr(item))
            return encode_decimal_exact(Decimal(str(item)))
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise TypeError("release evidence object keys must be strings")
            return "{" + ",".join(
                f"{encode(key)}:{encode(item[key])}" for key in sorted(item)
            ) + "}"
        raise TypeError(f"unsupported release evidence value {type(item).__name__}")

    return encode(value).encode("utf-8")


def canonical_ed25519_signature_is_valid(value: object) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{86}", value) is None:
        return False
    try:
        decoded = base64.b64decode(value + "==", altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        return False
    return (
        len(decoded) == 64
        and base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") == value
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_g0_content_addressed_snapshot(
    root: Path,
    relative_path: str,
    label: str,
    maximum_bytes: int,
) -> tuple[bytes, tuple[int, int, int, int, int, int]]:
    """Read one fixed G0 artifact without following links and retain identity."""

    file_fd = checkpoint_checker.open_repository_file(root, relative_path, label)
    try:
        before = os.fstat(file_fd)
        if before.st_size > maximum_bytes:
            raise checkpoint_checker.CheckpointValidationError(
                f"{label} exceeds {maximum_bytes} bytes"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                raise checkpoint_checker.CheckpointValidationError(
                    f"{label} exceeds {maximum_bytes} bytes"
                )
            chunks.append(chunk)
        after = os.fstat(file_fd)
        checkpoint_checker.require_stable_file(before, after, label)
        return b"".join(chunks), checkpoint_checker.stable_stat_fields(after)
    except OSError as error:
        raise checkpoint_checker.CheckpointValidationError(
            f"cannot read {label}: {error}"
        ) from error
    finally:
        os.close(file_fd)


def collect_g0_final_snapshot_failures(
    root: Path,
    relative_path: str,
    label: str,
    maximum_bytes: int,
    expected_identity: tuple[int, int, int, int, int, int],
    expected_raw_sha256: str,
) -> list[str]:
    """Re-open a validated artifact and reject namespace or byte drift."""

    try:
        current_raw, current_identity = read_g0_content_addressed_snapshot(
            root,
            relative_path,
            label,
            maximum_bytes,
        )
    except checkpoint_checker.CheckpointValidationError as error:
        return [f"{label} final readback failed: {error}"]
    failures: list[str] = []
    if current_identity != expected_identity:
        failures.append(f"{label} repository path identity changed during validation")
    if hashlib.sha256(current_raw).hexdigest() != expected_raw_sha256:
        failures.append(f"{label} bytes changed during validation")
    return failures


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_g0_json_object(
    raw_json: str,
    label: str,
) -> tuple[dict[str, object], list[str]]:
    try:
        value = json.loads(
            raw_json,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite,
            parse_float=parse_g0_finite_float,
            parse_int=parse_g0_bounded_integer,
        )
    except DuplicateJSONKeyError as error:
        return {}, [f"{label} contains duplicate key {error.args[0]!r}"]
    except NonFiniteJSONNumberError as error:
        return {}, [f"{label} contains non-finite number {error.args[0]!r}"]
    except G0JSONNumberError as error:
        return {}, [
            f"{label} contains an integer exceeding "
            f"{MAX_G0_JSON_INTEGER_DIGITS} digits: {error.args[0]!r}"
        ]
    except json.JSONDecodeError as error:
        return {}, [f"{label} is invalid JSON: {error.msg}"]
    if not isinstance(value, dict):
        return {}, [f"{label} must be an object"]
    return value, []


def exact_keys(
    value: object,
    expected: set[str],
    label: str,
    failures: list[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        failures.append(f"{label} must be an object")
        return {}
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        failures.append(
            f"{label} keys drifted; missing={missing!r} unknown={unknown!r}"
        )
    return value


def exactly_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            exactly_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            exactly_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected)
        )
    return actual == expected


def require_equal(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not exactly_equal(actual, expected):
        failures.append(f"{label} must be {expected!r}, got {actual!r}")


def require_string_list(
    value: object,
    label: str,
    failures: list[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        failures.append(f"{label} must be a list")
        return []
    if not allow_empty and not value:
        failures.append(f"{label} must not be empty")
    if not all(isinstance(item, str) and item for item in value):
        failures.append(f"{label} must contain only nonblank strings")
        return []
    return value


def observability_value_is_valid(
    definition: object,
    value: object,
    *,
    registries: dict[str, set[str]] | None = None,
) -> bool:
    if not isinstance(definition, dict):
        return False
    value_type = definition.get("type")
    if value_type == "string":
        if not isinstance(value, str):
            return False
        maximum_bytes = definition.get("maximumBytes")
        if isinstance(maximum_bytes, int):
            try:
                encoded_length = len(value.encode("utf-8"))
            except UnicodeEncodeError:
                return False
            if encoded_length > maximum_bytes:
                return False
    elif value_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return False
    elif value_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        if isinstance(value, float) and (value != value or value in {float("inf"), float("-inf")}):
            return False
    else:
        return False

    if "enum" in definition:
        candidates = definition.get("enum")
        return (
            isinstance(candidates, list)
            and value in candidates
            and any(type(value) is type(candidate) for candidate in candidates)
        )
    if "pattern" in definition:
        pattern = definition.get("pattern")
        return isinstance(pattern, str) and isinstance(value, str) and re.fullmatch(pattern, value) is not None
    if "registry" in definition:
        registry = definition.get("registry")
        return (
            isinstance(registry, str)
            and registries is not None
            and value in registries.get(registry, set())
        )
    if "minimum" in definition and "maximum" in definition:
        minimum = definition.get("minimum")
        maximum = definition.get("maximum")
        return (
            isinstance(minimum, (int, float))
            and not isinstance(minimum, bool)
            and isinstance(maximum, (int, float))
            and not isinstance(maximum, bool)
            and minimum <= value <= maximum
        )
    return False


def release_record_is_valid(
    schema: object,
    record: object,
    *,
    registries: dict[str, set[object]] | None = None,
    evidence_artifacts: dict[str, bytes] | None = None,
    approved_evidence_signers: dict[str, object] | None = None,
    evidence_signature_verifier: Callable[[str, object, bytes, str], bool] | None = None,
) -> bool:
    """Validate one content-free release record against the closed G0 schema."""
    if not isinstance(schema, dict) or not isinstance(record, dict):
        return False
    record_kind = record.get("record_kind")
    classes = schema.get("releaseRecordClasses")
    if not isinstance(classes, list):
        return False
    record_class = next(
        (
            item
            for item in classes
            if isinstance(item, dict) and item.get("recordKind") == record_kind
        ),
        None,
    )
    if not isinstance(record_class, dict):
        return False
    required = record_class.get("requiredFields")
    allowed = record_class.get("allowedFields")
    maximum_fields = record_class.get("maximumFields")
    if (
        not isinstance(required, list)
        or not isinstance(allowed, list)
        or not isinstance(maximum_fields, int)
        or any(not isinstance(field, str) for field in [*required, *allowed])
        or any(field not in record for field in required)
        or any(field not in allowed for field in record)
        or len(record) > maximum_fields
    ):
        return False
    definitions = schema.get("fieldDefinitions")
    if not isinstance(definitions, dict):
        return False
    for field, value in record.items():
        if not observability_value_is_valid(
            definitions.get(field),
            value,
            registries=registries,
        ):
            return False

    evidence_ref = record.get("evidence_ref")
    evidence_digest = record.get("evidence_sha256")
    if (
        not isinstance(evidence_ref, str)
        or not isinstance(evidence_digest, str)
        or evidence_ref != f"sha256:{evidence_digest}"
        or not isinstance(evidence_artifacts, dict)
    ):
        return False
    evidence_bytes = evidence_artifacts.get(evidence_ref)
    if (
        not isinstance(evidence_bytes, bytes)
        or len(evidence_bytes) > MAX_RELEASE_EVIDENCE_BYTES
        or hashlib.sha256(evidence_bytes).hexdigest() != evidence_digest
    ):
        return False
    try:
        envelope = json.loads(
            evidence_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite,
            parse_int=parse_release_evidence_integer,
            parse_float=parse_release_evidence_decimal,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
        NonFiniteJSONNumberError,
        ReleaseEvidenceNumberError,
        RecursionError,
    ):
        return False
    if not isinstance(envelope, dict) or set(envelope) != {
        "payload",
        "signer_id",
        "signature_algorithm",
        "signature",
    }:
        return False
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "evidence_kind",
        "campaign_id",
        "app_build",
        "app_version",
        "record_kind",
        "measurement_contract",
        "metric_name",
        "threshold_operator",
        "threshold_value",
        "platform",
        "device_class",
        "context",
        "samples",
        "variant_observations",
    }:
        return False
    if (
        type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("evidence_kind") != "signed_rc_metric_samples"
    ):
        return False

    def evidence_value_matches_record(field: str, evidence_value: object) -> bool:
        record_value = record.get(field)
        if evidence_value is None or record_value is None:
            return evidence_value is None and record_value is None
        definition = definitions.get(field)
        if isinstance(definition, dict) and definition.get("type") == "number":
            if (
                not isinstance(evidence_value, (int, float, Decimal))
                or isinstance(evidence_value, bool)
                or not isinstance(record_value, (int, float))
                or isinstance(record_value, bool)
            ):
                return False
            return Decimal(str(evidence_value)) == Decimal(str(record_value))
        return (
            evidence_value == record_value
            and type(evidence_value) is type(record_value)
        )

    for field in (
        "campaign_id",
        "app_build",
        "app_version",
        "record_kind",
        "measurement_contract",
        "metric_name",
        "threshold_operator",
        "threshold_value",
        "platform",
        "device_class",
    ):
        if not evidence_value_matches_record(field, payload.get(field)):
            return False
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
    context = payload.get("context")
    if not isinstance(context, dict) or set(context) != set(context_fields):
        return False
    if any(
        not evidence_value_matches_record(field, context.get(field))
        for field in context_fields
    ):
        return False
    samples = payload.get("samples")
    variant_observations = payload.get("variant_observations")

    def sample_value_is_valid(value: object) -> bool:
        if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
            return False
        try:
            finite = math.isfinite(float(value))
        except (OverflowError, TypeError, ValueError):
            return False
        return finite and 0 <= value <= 1000000000000

    if (
        not isinstance(samples, list)
        or len(samples) != record.get("sample_count")
        or len(samples) > MAX_RELEASE_EVIDENCE_SAMPLES
        or any(not sample_value_is_valid(value) for value in samples)
        or not isinstance(variant_observations, list)
        or len(variant_observations) > MAX_RELEASE_EVIDENCE_SAMPLES
    ):
        return False
    signer_id = envelope.get("signer_id")
    algorithm = envelope.get("signature_algorithm")
    signature = envelope.get("signature")
    if (
        not isinstance(signer_id, str)
        or re.fullmatch(r"release-evidence-[a-z0-9_-]{1,64}", signer_id) is None
        or algorithm != "ed25519"
        or not canonical_ed25519_signature_is_valid(signature)
        or not isinstance(approved_evidence_signers, dict)
        or signer_id not in approved_evidence_signers
        or evidence_signature_verifier is None
    ):
        return False
    try:
        canonical_payload = canonical_release_evidence_json(payload)
    except (DecimalException, ReleaseEvidenceNumberError, TypeError, ValueError):
        return False
    if len(canonical_payload) > MAX_RELEASE_EVIDENCE_BYTES:
        return False
    try:
        signature_valid = evidence_signature_verifier(
            algorithm,
            approved_evidence_signers[signer_id],
            canonical_payload,
            signature,
        )
    except Exception:
        return False
    if signature_valid is not True:
        return False

    platform = record.get("platform")
    device_class = record.get("device_class")
    platform_rows = schema.get("supportedPlatformRows")
    if (
        not isinstance(platform, str)
        or not isinstance(device_class, str)
        or not isinstance(platform_rows, dict)
        or device_class not in platform_rows.get(platform, [])
    ):
        return False
    if record.get("measurement_contract") != record_class.get("measurementContract"):
        return False
    metric_name = record.get("metric_name")
    if metric_name not in record_class.get("permittedMetricNames", []):
        return False
    bindings = schema.get("qualityTargetBindings")
    if not isinstance(bindings, list):
        return False
    binding = next(
        (
            item
            for item in bindings
            if isinstance(item, dict) and item.get("metricName") == metric_name
        ),
        None,
    )
    if (
        not isinstance(binding, dict)
        or record.get("measurement_contract") != binding.get("measurementContract")
        or record.get("threshold_operator") != binding.get("thresholdOperator")
        or record.get("threshold_value") != binding.get("thresholdValue")
    ):
        return False
    profiles = schema.get("metricEvidenceProfiles")
    if not isinstance(profiles, list):
        return False
    profile = next(
        (
            item
            for item in profiles
            if isinstance(item, dict) and metric_name in item.get("metricNames", [])
        ),
        None,
    )
    if not isinstance(profile, dict):
        return False
    required_metric_fields = profile.get("requiredFields")
    minimum_sample_count = profile.get("minimumSampleCount")
    applicable_platforms = profile.get("applicablePlatforms")
    sample_count = record.get("sample_count")
    if (
        not isinstance(required_metric_fields, list)
        or any(field not in record for field in required_metric_fields)
        or not isinstance(minimum_sample_count, int)
        or isinstance(minimum_sample_count, bool)
        or not isinstance(sample_count, int)
        or isinstance(sample_count, bool)
        or sample_count < minimum_sample_count
        or not isinstance(applicable_platforms, list)
        or platform not in applicable_platforms
    ):
        return False
    if "provider_adapter" in required_metric_fields and record.get("provider_adapter") not in {
        "ollama",
        "lm_studio",
    }:
        return False
    if "selected_route" in required_metric_fields and record.get("selected_route") == "none":
        return False
    if metric_name == "attempts_per_required_variant" and record.get("network_variant") == "none":
        return False
    network_variant = record.get("network_variant")
    if (
        record_kind == "network_measurement_result"
        and isinstance(network_variant, str)
        and network_variant != "none"
    ):
        if (
            metric_name != "attempts_per_required_variant"
            or len(variant_observations) != sample_count
        ):
            return False
        variant_rules = schema.get("variantOutcomeRules")
        variant_rule = next(
            (
                rule
                for rule in variant_rules
                if isinstance(rule, dict) and rule.get("variantId") == network_variant
            ),
            None,
        ) if isinstance(variant_rules, list) else None
        direct_outcome = record.get("direct_outcome")
        fallback_outcome = record.get("fallback_outcome")
        selected_route = record.get("selected_route")
        if (
            not isinstance(variant_rule, dict)
            or record.get("variant_outcome") != variant_rule.get("requiredOutcome")
            or not all(
                isinstance(value, str)
                for value in (direct_outcome, fallback_outcome, selected_route)
            )
        ):
            return False
        combinations = variant_rule.get("allowedCombinations")
        outage_observation_combinations = variant_rule.get(
            "outageObservationCombinations"
        )
        allowed_recovery_routes = variant_rule.get("allowedRecoveryRoutes")
        aggregate_route_source = variant_rule.get("aggregateRouteSource")
        requires_recovery = variant_rule.get(
            "requiresRestoreAndAuthenticatedRecovery"
        )
        if (
            not isinstance(combinations, list)
            or not isinstance(outage_observation_combinations, list)
            or not isinstance(allowed_recovery_routes, list)
            or aggregate_route_source not in {"outage_route", "recovery_route"}
            or type(requires_recovery) is not bool
        ):
            return False
        if variant_rule.get("regionBinding") == "record_region":
            if not isinstance(record.get("region"), str):
                return False
        elif variant_rule.get("regionBinding") == "not_applicable":
            if record.get("region") is not None:
                return False
        else:
            return False

        for expected_index, observation in enumerate(variant_observations, 1):
            if (
                not isinstance(observation, dict)
                or set(observation) != set(EXPECTED_VARIANT_OBSERVATION_FIELDS)
                or type(observation.get("attempt_index")) is not int
                or observation.get("attempt_index") != expected_index
                or observation.get("affected_scope")
                != variant_rule.get("affectedScope")
                or observation.get("direct_outcome") != direct_outcome
                or observation.get("fallback_outcome") != fallback_outcome
            ):
                return False
            if variant_rule.get("regionBinding") == "record_region":
                if observation.get("affected_region") != record.get("region"):
                    return False
            elif observation.get("affected_region") is not None:
                return False

            outage_connection_outcome = observation.get(
                "outage_connection_outcome"
            )
            outage_authentication_outcome = observation.get(
                "outage_authentication_outcome"
            )
            outage_route = observation.get("outage_route")
            recovery_route = observation.get("recovery_route")
            outage_rule = next(
                (
                    rule
                    for rule in outage_observation_combinations
                    if isinstance(rule, dict)
                    and rule.get("connectionOutcome")
                    == outage_connection_outcome
                    and rule.get("authenticationOutcome")
                    == outage_authentication_outcome
                ),
                None,
            )
            if (
                not isinstance(outage_rule, dict)
                or outage_route not in outage_rule.get("allowedRoutes", [])
                or recovery_route not in allowed_recovery_routes
            ):
                return False
            aggregate_route = observation.get(aggregate_route_source)
            if aggregate_route != selected_route or not any(
                isinstance(combination, dict)
                and combination.get("directOutcome") == direct_outcome
                and combination.get("fallbackOutcome") == fallback_outcome
                and aggregate_route in combination.get("selectedRoutes", [])
                for combination in combinations
            ):
                return False

            activated = observation.get("condition_activated_offset_milliseconds")
            result_offset = observation.get("condition_result_offset_milliseconds")
            if (
                type(activated) is not int
                or type(result_offset) is not int
                or not 0 <= activated < result_offset <= 120000
            ):
                return False
            restored = observation.get("service_restored_offset_milliseconds")
            recovered = observation.get(
                "recovery_authenticated_offset_milliseconds"
            )
            if requires_recovery:
                if (
                    type(restored) is not int
                    or type(recovered) is not int
                    or not result_offset < restored < recovered <= 120000
                    or observation.get("recovery_connection_outcome") != "success"
                    or observation.get("recovery_authentication_outcome") != "success"
                ):
                    return False
            elif (
                restored is not None
                or recovered is not None
                or observation.get("recovery_connection_outcome") != "not_required"
                or observation.get("recovery_authentication_outcome")
                != "not_required"
            ):
                return False
            for zero_field in (
                "plaintext_downgrade_event_count",
                "identity_downgrade_event_count",
                "weaker_route_event_count",
                "post_consent_loss_traffic_event_count",
            ):
                if type(observation.get(zero_field)) is not int or observation.get(
                    zero_field
                ) != 0:
                    return False
    elif variant_observations:
        return False
    if metric_name in {
        "p2p_required_cell_observed_direct_success",
        "p2p_required_cell_wilson95_lower_bound",
    } and record.get("selected_route") != "p2p_direct":
        return False
    if metric_name == "authenticated_handoff_p95_milliseconds" and record.get("network_cell") != (
        "bidirectional_wifi_cellular_authenticated_handoff"
    ):
        return False
    metric_value = record.get("metric_value")
    threshold = binding.get("thresholdValue")
    if (
        not isinstance(metric_value, (int, float))
        or isinstance(metric_value, bool)
        or not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
    ):
        return False
    operator = binding.get("thresholdOperator")
    successful_count = record.get("successful_sample_count")
    if successful_count is not None and (
        not isinstance(successful_count, int)
        or isinstance(successful_count, bool)
        or successful_count > sample_count
    ):
        return False

    def approximately_equal(left: object, right: object) -> bool:
        return (
            isinstance(left, (int, float, Decimal))
            and not isinstance(left, bool)
            and isinstance(right, (int, float, Decimal))
            and not isinstance(right, bool)
            and math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
        )

    count_metrics = {
        "minimum_completed_network_sessions",
        "attempts_per_required_topology_cell",
        "attempts_per_required_variant",
    }
    observed_rate_metrics = {
        "per_cell_observed_authenticated_success",
        "p2p_required_cell_observed_direct_success",
        "closed_beta_crash_free_session_rate",
        "closed_beta_anr_free_session_rate",
        "rollback_success_rate",
    }
    wilson_metrics = {
        "per_cell_wilson95_lower_bound",
        "p2p_required_cell_wilson95_lower_bound",
    }
    latency_metrics = {
        "traversal_setup_p50_milliseconds",
        "traversal_setup_p95_milliseconds",
        "traversal_setup_p99_milliseconds",
        "full_cold_setup_p95_milliseconds",
        "full_cold_setup_p99_milliseconds",
        "authenticated_reconnect_p95_milliseconds",
        "authenticated_handoff_p95_milliseconds",
    }
    binary_metrics = observed_rate_metrics | wilson_metrics | {
        "false_abuse_rejection_rate",
        "rollback_success_rate",
    }
    if record_kind == "security_hard_stop_result":
        binary_metrics.add(metric_name)
    if metric_name in binary_metrics and any(value not in {0, 1, 0.0, 1.0} for value in samples):
        return False

    def nearest_rank_percentile(values: list[object], percentile: float) -> float:
        ordered = sorted(float(value) for value in values)
        return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]

    raw_value: object = metric_value
    capacity_invariants_pass = True
    if metric_name in count_metrics:
        if any(value != 1 for value in samples):
            return False
        raw_value = len(samples)
    elif metric_name in observed_rate_metrics:
        evidence_successes = int(sum(samples))
        if not isinstance(successful_count, int) or successful_count != evidence_successes:
            return False
        raw_value = evidence_successes / sample_count
    elif metric_name in wilson_metrics:
        evidence_successes = int(sum(samples))
        if not isinstance(successful_count, int) or successful_count != evidence_successes:
            return False
        z = 1.959963984540054
        proportion = evidence_successes / sample_count
        denominator = 1 + (z * z / sample_count)
        center = (proportion + (z * z / (2 * sample_count))) / denominator
        margin = (
            z
            * math.sqrt(
                (proportion * (1 - proportion) / sample_count)
                + (z * z / (4 * sample_count * sample_count))
            )
            / denominator
        )
        raw_value = center - margin
    elif metric_name in latency_metrics:
        percentile = 0.5 if "_p50_" in metric_name else 0.95 if "_p95_" in metric_name else 0.99
        raw_value = nearest_rank_percentile(samples, percentile)
        if not approximately_equal(record.get("latency_milliseconds"), raw_value):
            return False
    elif metric_name.startswith("revocation_closure_"):
        percentile = 1.0 if "_absolute_" in metric_name else 0.95 if "_p95_" in metric_name else 0.99
        raw_value = nearest_rank_percentile(samples, percentile)
        if not approximately_equal(record.get("revocation_closure_milliseconds"), raw_value):
            return False
    elif metric_name == "incremental_memory_p95_mib":
        raw_value = nearest_rank_percentile(samples, 0.95)
        if not approximately_equal(record.get("memory_mib"), raw_value):
            return False
    elif metric_name in {
        "android_idle_paired_battery_percent_per_hour",
        "android_active_session_battery_percent_per_hour",
    }:
        raw_value = max(float(value) for value in samples)
        if not approximately_equal(record.get("battery_percent_per_hour"), raw_value):
            return False
    elif metric_name in {
        "closed_beta_crash_free_session_rate",
        "closed_beta_anr_free_session_rate",
        "rollback_success_rate",
    }:
        evidence_successes = int(sum(samples))
        if not isinstance(successful_count, int) or successful_count != evidence_successes:
            return False
        raw_value = evidence_successes / sample_count
    elif metric_name == "rc_soak_hours":
        raw_value = max(float(value) for value in samples)
        if not approximately_equal(record.get("window_hours"), raw_value):
            return False
    elif metric_name == "false_abuse_rejection_rate":
        false_rejections = record.get("false_rejection_count")
        evidence_rejections = int(sum(samples))
        if (
            not isinstance(false_rejections, int)
            or isinstance(false_rejections, bool)
            or false_rejections != evidence_rejections
        ):
            return False
        raw_value = evidence_rejections / sample_count
    elif metric_name in {
        "capacity_load_multiplier",
        "unbounded_growth_events",
        "admission_policy_weakening_events",
    }:
        projected = record.get("projected_peak_units")
        offered = record.get("offered_load_units")
        growth = record.get("unbounded_growth_event_count")
        weakening = record.get("admission_policy_weakening_event_count")
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (projected, offered, growth, weakening)):
            return False
        if not approximately_equal(max(samples), offered):
            return False
        ratio = offered / projected
        raw_value = {
            "capacity_load_multiplier": ratio,
            "unbounded_growth_events": growth,
            "admission_policy_weakening_events": weakening,
        }[metric_name]
        capacity_invariants_pass = ratio >= 2.0 and growth == 0 and weakening == 0
    elif record_kind == "security_hard_stop_result":
        raw_value = int(sum(samples))
    if not approximately_equal(metric_value, raw_value):
        return False
    passes = (
        (operator == "minimum" and metric_value >= threshold)
        or (operator == "maximum" and metric_value <= threshold)
        or (operator == "equal" and metric_value == threshold)
    ) and capacity_invariants_pass
    return record.get("gate_result") == ("passed" if passes else "failed")


def release_campaign_failures(
    schema: object,
    decision: object,
    records: object,
    *,
    registries: dict[str, set[object]] | None = None,
    evidence_artifacts: dict[str, bytes] | None = None,
    approved_evidence_signers: dict[str, object] | None = None,
    evidence_signature_verifier: Callable[[str, object, bytes, str], bool] | None = None,
) -> list[str]:
    """Reject incomplete or internally inconsistent V1 release campaigns."""
    failures: list[str] = []
    if not isinstance(schema, dict) or not isinstance(decision, dict):
        return ["release campaign schema and decision must be objects"]
    if not isinstance(records, list) or not records:
        return ["release campaign must contain records"]
    typed_records: list[dict[str, object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not release_record_is_valid(
            schema,
            record,
            registries=registries,
            evidence_artifacts=evidence_artifacts,
            approved_evidence_signers=approved_evidence_signers,
            evidence_signature_verifier=evidence_signature_verifier,
        ):
            failures.append(f"release campaign record {index} is invalid")
            continue
        typed_records.append(record)
        if record.get("gate_result") != "passed":
            failures.append(f"release campaign record {index} did not pass")
    if not typed_records:
        return failures
    for field in ("campaign_id", "app_build", "app_version"):
        if len({record.get(field) for record in typed_records}) != 1:
            failures.append(f"release campaign {field} is inconsistent")

    expected_metrics = set(
        schema.get("fieldDefinitions", {}).get("metric_name", {}).get("enum", [])
        if isinstance(schema.get("fieldDefinitions"), dict)
        else []
    )
    present_metrics = {
        record.get("metric_name")
        for record in typed_records
        if isinstance(record.get("metric_name"), str)
    }
    for metric in sorted(expected_metrics - present_metrics):
        failures.append(f"release campaign is missing metric {metric}")

    network = decision.get("networkMatrix", {})
    cells = {
        cell.get("id"): cell
        for cell in network.get("requiredCells", [])
        if isinstance(cell, dict) and isinstance(cell.get("id"), str)
    } if isinstance(network, dict) else {}
    variants = {
        variant.get("id"): variant
        for variant in network.get("requiredVariants", [])
        if isinstance(variant, dict) and isinstance(variant.get("id"), str)
    } if isinstance(network, dict) else {}
    providers = ("ollama", "lm_studio")
    platform_rows = schema.get("supportedPlatformRows", {})
    app_rows = [
        row
        for platform in ("android", "macos")
        for row in platform_rows.get(platform, [])
    ] if isinstance(platform_rows, dict) else []
    approved_regions = (
        registries.get("approved_release_region_registry", set())
        if isinstance(registries, dict)
        else set()
    )

    def has_record(metric: str, **dimensions: object) -> bool:
        return any(
            record.get("metric_name") == metric
            and all(record.get(field) == value for field, value in dimensions.items())
            for record in typed_records
        )

    profiles = schema.get("metricEvidenceProfiles", [])
    for profile in profiles if isinstance(profiles, list) else []:
        if not isinstance(profile, dict):
            continue
        coverage = profile.get("campaignCoverage")
        for metric in profile.get("metricNames", []):
            required_dimensions: list[dict[str, object]] = []
            if coverage == "once_per_campaign":
                required_dimensions = [{}]
            elif coverage == "every_network_cell_provider":
                required_dimensions = [
                    {
                        "network_cell": cell,
                        "network_variant": "none",
                        "provider_adapter": provider,
                        "device_class": row,
                    }
                    for cell in cells
                    for provider in providers
                    for row in app_rows
                ]
            elif coverage == "every_required_variant_cell_provider":
                if "regional_relay_outage" in variants and not approved_regions:
                    failures.append(
                        f"release campaign metric {metric} has no approved regional-outage region"
                    )
                required_dimensions = [
                    {
                        "network_variant": variant_id,
                        "network_cell": cell,
                        "provider_adapter": provider,
                        "device_class": row,
                        **({"region": region} if region is not None else {}),
                    }
                    for variant_id, variant in variants.items()
                    for cell in variant.get("appliesToCells", [])
                    for provider in providers
                    for row in app_rows
                    for region in (
                        sorted(approved_regions)
                        if variant_id == "regional_relay_outage"
                        else [None]
                    )
                ]
            elif coverage == "every_p2p_required_cell_provider":
                required_dimensions = [
                    {
                        "network_cell": cell,
                        "network_variant": "none",
                        "provider_adapter": provider,
                        "device_class": row,
                    }
                    for cell in network.get("applicabilityRules", {}).get("p2pRequiredSuccessCells", [])
                    for provider in providers
                    for row in app_rows
                ]
            elif coverage == "every_p2p_attempt_cell_provider":
                required_dimensions = [
                    {
                        "network_cell": cell_id,
                        "network_variant": "none",
                        "provider_adapter": provider,
                        "device_class": row,
                    }
                    for cell_id, cell in cells.items()
                    if cell.get("p2pAttemptRequired") is True
                    for provider in providers
                    for row in app_rows
                ]
            elif coverage == "handoff_cell_provider":
                required_dimensions = [
                    {
                        "network_cell": "bidirectional_wifi_cellular_authenticated_handoff",
                        "network_variant": "none",
                        "provider_adapter": provider,
                        "device_class": row,
                    }
                    for provider in providers
                    for row in app_rows
                ]
            elif coverage == "every_app_platform_row":
                required_dimensions = [{"device_class": row} for row in app_rows]
            elif coverage == "every_android_platform_row":
                required_dimensions = [
                    {"device_class": row}
                    for row in platform_rows.get("android", [])
                ] if isinstance(platform_rows, dict) else []
            elif coverage == "every_service_region":
                if not approved_regions:
                    failures.append(f"release campaign metric {metric} has no approved service region")
                required_dimensions = [{"region": region} for region in sorted(approved_regions)]
            elif coverage == "every_app_and_service_platform":
                required_dimensions = [
                    {"device_class": row}
                    for row in [*app_rows, "service_control_plane"]
                ]
            for dimensions in required_dimensions:
                if not has_record(metric, **dimensions):
                    detail = ",".join(f"{key}={value}" for key, value in dimensions.items())
                    failures.append(f"release campaign metric {metric} is missing coverage {detail}")

    variant_cells = {
        (variant_id, cell)
        for variant_id, variant in variants.items()
        for cell in variant.get("appliesToCells", [])
    }
    for index, record in enumerate(typed_records):
        cell_id = record.get("network_cell")
        variant_id = record.get("network_variant")
        selected_route = record.get("selected_route")
        if isinstance(cell_id, str) and cell_id in cells:
            routes = cells[cell_id].get("authenticatedCompletionRoutes", [])
            if isinstance(selected_route, str) and selected_route != "none" and selected_route not in routes:
                failures.append(f"release campaign record {index} selects a route outside its cell")
        if isinstance(variant_id, str) and variant_id != "none" and (variant_id, cell_id) not in variant_cells:
            failures.append(f"release campaign record {index} uses a variant outside its cell")
        if record.get("metric_name") in {
            "p2p_required_cell_observed_direct_success",
            "p2p_required_cell_wilson95_lower_bound",
        } and selected_route != "p2p_direct":
            failures.append(f"release campaign record {index} does not bind direct P2P evidence")

    route_classes = sorted({
        route
        for cell in cells.values()
        for route in cell.get("authenticatedCompletionRoutes", [])
        if isinstance(route, str)
    })
    for row in app_rows:
        for route in route_classes:
            if not any(
                record.get("record_kind") == "network_measurement_result"
                and record.get("device_class") == row
                and record.get("selected_route") == route
                for record in typed_records
            ):
                failures.append(
                    f"release campaign platform row {row} is missing route class {route}"
                )
    return failures


def release_campaign_is_valid(
    schema: object,
    decision: object,
    records: object,
    *,
    registries: dict[str, set[object]] | None = None,
    evidence_artifacts: dict[str, bytes] | None = None,
    approved_evidence_signers: dict[str, object] | None = None,
    evidence_signature_verifier: Callable[[str, object, bytes, str], bool] | None = None,
) -> bool:
    return not release_campaign_failures(
        schema,
        decision,
        records,
        registries=registries,
        evidence_artifacts=evidence_artifacts,
        approved_evidence_signers=approved_evidence_signers,
        evidence_signature_verifier=evidence_signature_verifier,
    )


EXPECTED_SOURCE_HASHES = {
    "docs/security-hardening/production-p2p-nat-v1/selection-profile.json":
        "8d71bd82dff5f9764a537e9c1cb57fb7a26cd1ea9b78ce9bdac11ddd2cbbb9d7",
    "docs/security-hardening/production-p2p-nat-v1/selection-decision.json":
        "c87551296ca12d4ca8db68e13b45ad7b059ebd8354f8834a512ee218abd75b72",
    "docs/security-hardening/production-p2p-nat-v1/pre-network/decision-v1.json":
        "2962c6f752ebbdfd4432364544b5fa436974701cf54471ed121521f40296108a",
    "docs/security-hardening/production-p2p-nat-v1/pre-network/review-v1.json":
        "d3d7a39774610452babedc964ef57aa08d872c7fa9c8a0b5aaf35ca2b0f99802",
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/decision-v6.json":
        "65095344cbdc13445ef171562b4f60d2b1005d6feaf128d94660f1204c931755",
    "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v9.json":
        "d1e2649504de1661b3184ce21ebfacfd9c38eb590b00e32ff755b77a0d66341d",
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/progress-v8.json":
        "d83f81af28b03493ce47088e81a41a8ac73c722efd18e0f6b333b1b3c20f92a7",
    "docs/security-hardening/production-relay-v1/proposals/authenticated-allocation-control-plane.md":
        "84ac800ae1b64099a84b55e32ec0db8e4356f78780a8ff56392e4e3c390f5743",
    "docs/security-hardening/production-relay-v1/proposals/pair-epoch-recovery.md":
        "183481be411a9eebd03bd86797bcdf91f03ef0780f40fbb048262b9034fdaa69",
}

EXPECTED_BLOCKERS = [
    "g0_assurance_artifacts_and_baseline_gate",
    "roadmap_and_g0_checkpoint_publication",
    "production_application_namespaces",
    "distribution_account_and_key_owners",
    "provider_compatibility_baseline",
    "service_domain_dns_and_webpki_owners",
    "service_root_and_online_signer_owners",
    "privacy_incident_and_retention_owners",
    "quality_measurement_owners",
    "relay_region_capacity_and_cost_budget",
]

EXPECTED_NETWORK_CELL_IDS = [
    "same_lan_ipv4_local_direct",
    "unrelated_native_ipv6_p2p",
    "unrelated_home_nat_ipv4",
    "unrelated_home_nat_to_cgnat",
    "unrelated_cgnat_to_cgnat",
    "unrelated_nat64_to_ipv4",
    "unrelated_udp_blocked_tcp443",
    "forced_turn_relay",
    "forced_sealed_emergency_relay",
    "bidirectional_wifi_cellular_authenticated_handoff",
    "vpn_path_change_authenticated_recovery",
    "suspend_resume_authenticated_reconnect",
]

EXPECTED_NETWORK_VARIANT_IDS = [
    "symmetric_nat_pair",
    "consent_loss_and_recovery",
    "deliberate_p2p_failure",
    "required_turn_outage",
    "required_sealed_relay_outage",
    "regional_relay_outage",
]

EXPECTED_VARIANT_OUTCOME_RULES = [
    {
        "variantId": "symmetric_nat_pair",
        "requiredOutcome": "supported_route_success_and_direct_p2p_result_reported",
        "affectedScope": "symmetric_nat",
        "regionBinding": "not_applicable",
        "requiresRestoreAndAuthenticatedRecovery": False,
        "aggregateRouteSource": "outage_route",
        "allowedCombinations": [
            {
                "directOutcome": "success",
                "fallbackOutcome": "not_attempted",
                "selectedRoutes": ["p2p_direct"],
            },
            {
                "directOutcome": "failure",
                "fallbackOutcome": "success",
                "selectedRoutes": ["turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
            },
        ],
        "outageObservationCombinations": [
            {
                "connectionOutcome": "success",
                "authenticationOutcome": "success",
                "allowedRoutes": ["p2p_direct", "turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
            },
        ],
        "allowedRecoveryRoutes": ["none"],
    },
    {
        "variantId": "consent_loss_and_recovery",
        "requiredOutcome": "stale_path_closed_before_authenticated_recovery",
        "affectedScope": "consent_loss",
        "regionBinding": "not_applicable",
        "requiresRestoreAndAuthenticatedRecovery": True,
        "aggregateRouteSource": "recovery_route",
        "allowedCombinations": [
            {
                "directOutcome": "failure",
                "fallbackOutcome": "success",
                "selectedRoutes": ["p2p_direct", "turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
            },
            {
                "directOutcome": "not_attempted",
                "fallbackOutcome": "success",
                "selectedRoutes": ["p2p_direct", "turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
            },
        ],
        "outageObservationCombinations": [
            {
                "connectionOutcome": "rejected",
                "authenticationOutcome": "not_established",
                "allowedRoutes": ["none"],
            },
        ],
        "allowedRecoveryRoutes": ["p2p_direct", "turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
    },
    {
        "variantId": "deliberate_p2p_failure",
        "requiredOutcome": "authenticated_fallback_without_plaintext_or_identity_downgrade",
        "affectedScope": "p2p_direct",
        "regionBinding": "not_applicable",
        "requiresRestoreAndAuthenticatedRecovery": False,
        "aggregateRouteSource": "outage_route",
        "allowedCombinations": [
            {
                "directOutcome": "failure",
                "fallbackOutcome": "success",
                "selectedRoutes": ["turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
            },
        ],
        "outageObservationCombinations": [
            {
                "connectionOutcome": "success",
                "authenticationOutcome": "success",
                "allowedRoutes": ["turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
            },
        ],
        "allowedRecoveryRoutes": ["none"],
    },
    {
        "variantId": "required_turn_outage",
        "requiredOutcome": "sealed_fallback_or_fail_closed_then_authenticated_recovery",
        "affectedScope": "turn",
        "regionBinding": "not_applicable",
        "requiresRestoreAndAuthenticatedRecovery": True,
        "aggregateRouteSource": "recovery_route",
        "allowedCombinations": [
            {
                "directOutcome": "not_attempted",
                "fallbackOutcome": "success",
                "selectedRoutes": ["turn_relay", "turn_tls_tcp_relay"],
            },
        ],
        "outageObservationCombinations": [
            {
                "connectionOutcome": "success",
                "authenticationOutcome": "success",
                "allowedRoutes": ["sealed_relay"],
            },
            {
                "connectionOutcome": "rejected",
                "authenticationOutcome": "not_established",
                "allowedRoutes": ["none"],
            },
        ],
        "allowedRecoveryRoutes": ["turn_relay", "turn_tls_tcp_relay"],
    },
    {
        "variantId": "required_sealed_relay_outage",
        "requiredOutcome": "fail_closed_without_weaker_route_then_authenticated_recovery",
        "affectedScope": "sealed_relay",
        "regionBinding": "not_applicable",
        "requiresRestoreAndAuthenticatedRecovery": True,
        "aggregateRouteSource": "recovery_route",
        "allowedCombinations": [
            {
                "directOutcome": "not_attempted",
                "fallbackOutcome": "success",
                "selectedRoutes": ["sealed_relay"],
            },
        ],
        "outageObservationCombinations": [
            {
                "connectionOutcome": "rejected",
                "authenticationOutcome": "not_established",
                "allowedRoutes": ["none"],
            },
        ],
        "allowedRecoveryRoutes": ["sealed_relay"],
    },
    {
        "variantId": "regional_relay_outage",
        "requiredOutcome": "single_region_v1_fails_closed_then_recovers_after_service_restore",
        "affectedScope": "region",
        "regionBinding": "record_region",
        "requiresRestoreAndAuthenticatedRecovery": True,
        "aggregateRouteSource": "recovery_route",
        "allowedCombinations": [
            {
                "directOutcome": "not_attempted",
                "fallbackOutcome": "success",
                "selectedRoutes": ["turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
            },
        ],
        "outageObservationCombinations": [
            {
                "connectionOutcome": "rejected",
                "authenticationOutcome": "not_established",
                "allowedRoutes": ["none"],
            },
        ],
        "allowedRecoveryRoutes": ["turn_relay", "turn_tls_tcp_relay", "sealed_relay"],
    },
]

EXPECTED_MEASUREMENT_CONTRACT_IDS = [
    "network_reliability_and_latency",
    "endpoint_resource_and_stability",
    "abuse_and_capacity",
    "security_hard_stops",
]

EXPECTED_MEASUREMENT_TARGET_FIELDS = {
    "network_reliability_and_latency": [
        "minimumCompletedNetworkSessions",
        "minimumAttemptsPerRequiredTopologyCell",
        "minimumAttemptsPerRequiredVariant",
        "perCellObservedAuthenticatedSuccessMinimum",
        "perCellWilson95LowerBoundMinimum",
        "p2pRequiredCellObservedDirectSuccessMinimum",
        "p2pRequiredCellWilson95LowerBoundMinimum",
        "traversalSetupMilliseconds",
        "fullColdSetupMilliseconds",
        "authenticatedReconnectP95Milliseconds",
        "authenticatedHandoffP95Milliseconds",
        "revocationClosureMilliseconds",
    ],
    "endpoint_resource_and_stability": [
        "incrementalMemoryP95MiB",
        "androidBatteryPercentPerHourMaximum",
        "closedBetaCrashFreeSessionMinimum",
        "closedBetaAnrFreeSessionMinimum",
        "rcSoakHoursMinimum",
    ],
    "abuse_and_capacity": [
        "falseAbuseRejectionMaximum",
        "capacityRule",
    ],
    "security_hard_stops": [
        "securityHardStops",
        "rollbackSuccessMinimum",
    ],
}

EXPECTED_SECURITY_HARD_STOPS = {
    "prohibitedDestinationAttempts": 0,
    "plaintextDowngrades": 0,
    "falseIdentityAcceptance": 0,
    "duplicateNonIdempotentRequests": 0,
    "protectedDataLeaks": 0,
    "rollbackFailures": 0,
    "securityStateRollbacks": 0,
    "trafficAfterConsentOrRevocation": 0,
    "unauthorizedServiceAcceptance": 0,
    "unauthorizedReleaseArtifactAcceptance": 0,
    "releaseArtifactProvenanceFailures": 0,
    "routeAuthorizationBypasses": 0,
    "revocationClosureDeadlineMisses": 0,
}

EXPECTED_DECISION_CANONICAL_SHA256 = (
    "b72db086b4ac7bf0e5eff8b71a28917231822cebedf742b85e596eb025e55ae2"
)

EXPECTED_ASSURANCE_CANONICAL_SHA256 = (
    "7642029c307dd658b4e325f409deeef7f0b2addb82105270aa4c83cc588c4a11"
)

EXPECTED_ASSURANCE_BYTE_SHA256 = (
    "64d7d48c1f82b43a33e860b45c769878cb654f0678e94bfd540f12c3d1a9a43d"
)
EXPECTED_ASSURANCE_CHECKPOINT_BYTE_SHA256 = (
    "9b2a108b7a2e8223ec4c50b538277857a2dbc064b9da694fa7c6c200f1081048"
)
EXPECTED_ASSURANCE_CHECKPOINT_CANONICAL_SHA256 = (
    "1e20f60154ea82e3a6a4c16573d7d52b60e362098e7c5a614b6866d303a2b2b5"
)
EXPECTED_ASSURANCE_AMENDMENT_BYTE_SHA256 = (
    "b04204e86c9af4291e8b7112c14e420877a54d2688b5b5d967432949b8f7aea6"
)
EXPECTED_ASSURANCE_AMENDMENT_CANONICAL_SHA256 = (
    "8b843526eef12e147593084d21ea3f40336628c623f732f0fd64d6ad80bbec7b"
)
EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256 = (
    "5777e26d1f2535da58deb74d5f7907617caf8aa99fa20885c771c29ecfb7726a"
)
EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256 = (
    "b12bf8d1f6e782f57b9012728f5b7dada1008d9885f4263782fafa0c256cdc0c"
)
EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_CANONICAL_SHA256 = (
    "4f26d087b0eb0cf312911ddbd1ee25dc8fcfbb0deef6fb8d10009515a16391ca"
)
EXPECTED_G0_EXECUTABLE_CHECK_IDS = [
    "full_no_device_aggregate",
    "android_and_macos_release_compilation",
]
EXPECTED_G0_NON_EXECUTABLE_CHECK_IDS = [
    "g0_assurance_packet",
    "roadmap_and_g0_checkpoint_publication",
    "production_namespaces_distribution_and_key_custody",
    "provider_compatibility_baseline",
    "service_identity_and_signer_custody",
    "privacy_incident_quality_and_operations_ownership",
    "relay_region_capacity_and_cost",
]
EXPECTED_G0_COMMAND_PROFILE_SHA256 = {
    "g0-command-profile-full-no-device-aggregate-v1": (
        "6e60c1f17812a16a6b24bd172ad95e9d3e9b91a793c56ca332467e8961c84f78"
    ),
    "g0-command-profile-android-macos-release-compilation-v1": (
        "3c64524bf371c27412e29fe75f1be52b36d31b2bc25791320e67a12381bacc68"
    ),
}
EXPECTED_G0_PUBLICATION_RECEIPT_PROFILE = {
    "exactFields": [
        "repositoryRef",
        "commitObjectId",
        "parentAssurancePath",
        "parentAssuranceSha256",
        "parentCheckpointPath",
        "parentCheckpointSha256",
        "amendmentPath",
        "amendmentSha256",
        "amendmentCheckpointPath",
        "amendmentCheckpointSha256",
        "effectiveAssuranceCanonicalSha256",
        "remoteReadbackAt",
        "remoteReadbackSha256",
        "result",
    ],
    "repositoryRefPolicy": (
        "nonempty_opaque_non_secret_repository_identity_equal_to_the_expected_publication_target"
    ),
    "commitObjectIdPattern": "^(?:[0-9a-f]{40}|[0-9a-f]{64})$",
    "parentAssurancePathPolicy": "exact_docs_v1_g0_assurance_v1_json",
    "parentCheckpointPathPolicy": (
        "exact_docs_v1_g0_assurance_checkpoint_readback_v1_json"
    ),
    "amendmentPathPolicy": (
        "exact_docs_v1_g0_assurance_closure_amendment_v2_json"
    ),
    "amendmentCheckpointPathPolicy": (
        "exact_docs_v1_g0_assurance_closure_amendment_checkpoint_v2_json"
    ),
    "sha256Pattern": "^[0-9a-f]{64}$",
    "remoteReadbackAtPolicy": "rfc3339_utc",
    "resultDomain": ["verified"],
    "commitContainmentPolicy": (
        "resolved_commit_tree_contains_exact_parent_assurance_parent_checkpoint_"
        "amendment_and_amendment_checkpoint_bytes_at_their_exact_paths_and_hashes"
    ),
    "effectiveReconstructionPolicy": (
        "independently_apply_exact_amendment_to_exact_parent_and_match_effective_"
        "assurance_canonical_sha256"
    ),
    "remoteEqualityPolicy": (
        "remote_readback_sha256_equals_amendment_checkpoint_sha256"
    ),
    "expectedIdentityPolicy": (
        "repository_commit_all_four_paths_all_four_byte_hashes_and_effective_"
        "canonical_sha256_equal_the_explicitly_reviewed_publication_target"
    ),
}
EXPECTED_ASSURANCE_AMENDMENT_OPERATIONS = [
    ("replace", "/schemaVersion"),
    ("replace", "/assuranceId"),
    ("replace", "/g0ClosureContract/schemaVersion"),
    ("add", "/g0ClosureContract/sourceBindings/commandProfiles"),
    ("add", "/g0ClosureContract/executableCheckIds"),
    ("add", "/g0ClosureContract/nonExecutableCheckIds"),
    ("add", "/g0ClosureContract/commandProfileSchema"),
    ("add", "/g0ClosureContract/commandProfiles"),
    ("replace", "/g0ClosureContract/gateReceiptProfile"),
    ("replace", "/g0ClosureContract/publicationReceiptProfile"),
    (
        "replace",
        "/g0ClosureContract/receiptActivationPolicy/successorActivationPrerequisites",
    ),
]

EXPECTED_ASSURANCE_SOURCE_HASHES = {
    "docs/v1/g0/decision-v1.json":
        "44dd88a0de7e02fdb2b7c22e597496ffe4f00f9a67a54af6e9ace8afdcf9308a",
    **EXPECTED_SOURCE_HASHES,
    "docs/architecture.md":
        "cf59f8dd69344d3a3ff742fb229092b9a1197dd0ac052a93eabdbf0540201ac0",
    "docs/protocol.md":
        "aad345519c53e0124e377e0e42a4d5cd14bc33b1cdd573ba38ec35edfa99cfef",
    "docs/connection-overlay.md":
        "845af8d40f0a137682c81bde3261e76d04ce7f84d156a6ad3508bb13986f2f53",
    "docs/security.md":
        "c1ffd4f596c6754dde00916b2735a765b0640cc53b19f62b646922ae148bd7af",
    "docs/security-hardening/production-p2p-nat-v1/threat-model.md":
        "8913b8d32c66399e0426cf08b7a12ee9e6de446644501e842a9c2a0de68259e8",
    "docs/security-hardening/production-p2p-nat-v1/hardening.json":
        "69b3a9080dd3ab1caba2dfd67099643c727be99f5d39000675fe429507df6ceb",
    "docs/security-hardening/production-relay-v1/hardening.json":
        "6635ce4ef9aeb19e389ab8ac72c634389b717ea6aaf9c477230985acfae4d172",
    "packages/protocol-schema/protocol.schema.json":
        "daff66787cade9f4b23c8a7df48a7a1ff850ebb967418939c2ee8d9bc9329e60",
    "packages/protocol-schema/pairing-qr.schema.json":
        "f6ec04a8ca80ee08a26e67bd4ac1695b618d8923fe1dd6ce9a3a35a5206bf3df",
    "apps/macos/Protocol/Sources/ProtocolEnvelope.swift":
        "4ac0a1029b70799cd3814f9457153525745e494961bbcf0cf09b4d122683436b",
    "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/ProtocolModels.kt":
        "40be264c9881d024f168857189595ea9fcc3c1023b05d00a90e924523633b3bd",
    "apps/macos/Pairing/Sources/PairingCoordinator.swift":
        "605e859555f40371d3a656fb5e1aadef823bfaa1b68055efef669b97ec28ecd1",
    "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt":
        "7dfc0cc1fdbb5731d47350ea0c3fa02a70947d363474958e7f3d0d05ccb81957",
    "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt":
        "13632d07054f2dec9c8675fd921a6635910ab8b2f3b5eb152a9933328088aa6e",
    "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift":
        "5adf544488061731cb1610010eef7c8fb005a702cf26ce91fb1135fb53b3f1ad",
    "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt":
        "211f8d5e493ced62cca7771e20e6f409b5ff2a150b187c737557f32d1c7caabf",
    "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeLocalStore.kt":
        "a35faa25c6e6a5a8e0d2b54deb349befe801722df825f0a2bd92bfa7c28537fa",
    "apps/macos/Pairing/Sources/RuntimeIdentityKeyStore.swift":
        "85339f42999b302207c01f4b67771e8c8bd981be166994a4954a94f45cd17a45",
    "apps/macos/CompanionCore/Sources/RuntimeChatEventStore.swift":
        "423429bd8db283494225e61b5d8e88cd86e3faf732e4af949fdab6415ceeb734",
}

EXPECTED_PROTOCOL_UNIT_IDS = [
    "pairing_qr_v1",
    "runtime_envelope_v1",
    "pairing_and_auth",
    "route_refresh_and_relay_allocation",
    "runtime_health_and_models",
    "chat_stream_cancel_history",
    "memory_and_retrieval",
    "error_taxonomy",
    "reserved_namespaces",
]

EXPECTED_DATA_FLOW_IDS = [
    "qr_pairing_to_trusted_state",
    "route_to_authenticated_runtime_session",
    "authenticated_route_refresh",
    "runtime_health_and_provider_access",
    "chat_stream_cancel_and_history",
    "runtime_memory_retrieval_and_research",
    "content_free_assurance_observability",
    "endpoint_to_rendezvous_candidate",
    "endpoint_to_stun",
    "endpoint_to_approved_candidate_target",
    "endpoint_to_turn_or_sealed_relay",
    "endpoint_to_allocation_authority",
    "endpoint_to_pair_state_authority",
    "allocation_authority_to_endpoint_and_relay",
    "android_release_build_to_play_install_update_and_forward_fix",
    "macos_release_build_to_notarized_dmg_install_update_and_rollback",
]

EXPECTED_GUARDED_NAMESPACE_PREFIXES = [
    *active_protocol_checker.RESERVED_PREFIXES,
    "route.",
]

EXPECTED_NAMESPACE_ACTIVE_EXCEPTIONS = {
    "retrieval.": sorted(active_protocol_checker.ALLOWED_RETRIEVAL_TYPES),
    "index.": sorted(active_protocol_checker.ALLOWED_INDEX_TYPES),
    "research.": sorted(active_protocol_checker.ALLOWED_RESEARCH_TYPES),
    "citation.": sorted(active_protocol_checker.ALLOWED_CITATION_TYPES),
    "source_anchor.": sorted(active_protocol_checker.ALLOWED_SOURCE_ANCHOR_TYPES),
    "trusted_source.": sorted(active_protocol_checker.ALLOWED_TRUSTED_SOURCE_TYPES),
    "route.": sorted(active_protocol_checker.ALLOWED_ROUTE_TYPES),
}

EXPECTED_NEW_THREAT_IDS = [f"T{number:03d}" for number in range(17, 27)]

EXPECTED_RISK_IDS = [
    "R001_protocol_schema_code_drift",
    "R002_production_namespace_signing_and_distribution_custody",
    "R003_service_dns_webpki_root_and_signer_compromise",
    "R004_pair_recovery_deny_only_dos",
    "R005_relay_capacity_and_outage",
    "R006_provider_compatibility",
    "R007_privacy_logging_and_retention",
    "R008_local_store_corruption_or_stale_cache",
    "R009_evidence_matrix_gap",
    "R010_rollback_monotonicity",
]

EXPECTED_OBSERVABILITY_EVENT_KINDS = [
    "route_attempt_outcome",
    "authenticated_session_outcome",
    "p2p_direct_outcome",
    "fallback_transition",
    "revocation_closure",
    "service_capacity",
    "security_hard_stop",
    "release_gate_result",
    "incident_state_transition",
]

EXPECTED_RELEASE_RECORD_KINDS = [
    "network_measurement_result",
    "endpoint_resource_and_stability_result",
    "abuse_and_capacity_result",
    "security_hard_stop_result",
    "rollback_drill_result",
]

EXPECTED_RELEASE_RECORD_METRICS = {
    "network_measurement_result": [
        "minimum_completed_network_sessions",
        "attempts_per_required_topology_cell",
        "attempts_per_required_variant",
        "per_cell_observed_authenticated_success",
        "per_cell_wilson95_lower_bound",
        "p2p_required_cell_observed_direct_success",
        "p2p_required_cell_wilson95_lower_bound",
        "traversal_setup_p50_milliseconds",
        "traversal_setup_p95_milliseconds",
        "traversal_setup_p99_milliseconds",
        "full_cold_setup_p95_milliseconds",
        "full_cold_setup_p99_milliseconds",
        "authenticated_reconnect_p95_milliseconds",
        "authenticated_handoff_p95_milliseconds",
        "revocation_closure_p95_milliseconds",
        "revocation_closure_p99_milliseconds",
        "revocation_closure_absolute_milliseconds",
    ],
    "endpoint_resource_and_stability_result": [
        "incremental_memory_p95_mib",
        "android_idle_paired_battery_percent_per_hour",
        "android_active_session_battery_percent_per_hour",
        "closed_beta_crash_free_session_rate",
        "closed_beta_anr_free_session_rate",
        "rc_soak_hours",
    ],
    "abuse_and_capacity_result": [
        "false_abuse_rejection_rate",
        "capacity_load_multiplier",
        "unbounded_growth_events",
        "admission_policy_weakening_events",
    ],
    "security_hard_stop_result": [
        "prohibited_destination_attempts",
        "plaintext_downgrades",
        "false_identity_acceptance",
        "duplicate_non_idempotent_requests",
        "protected_data_leaks",
        "rollback_failures",
        "security_state_rollbacks",
        "traffic_after_consent_or_revocation",
        "unauthorized_service_acceptance",
        "unauthorized_release_artifact_acceptance",
        "release_artifact_provenance_failures",
        "route_authorization_bypasses",
        "revocation_closure_deadline_misses",
    ],
    "rollback_drill_result": ["rollback_success_rate"],
}

EXPECTED_RELEASE_RECORD_CONTRACTS = {
    "network_measurement_result": "network_reliability_and_latency",
    "endpoint_resource_and_stability_result": "endpoint_resource_and_stability",
    "abuse_and_capacity_result": "abuse_and_capacity",
    "security_hard_stop_result": "security_hard_stops",
    "rollback_drill_result": "security_hard_stops",
}

EXPECTED_SERVICE_EVENT_FIELDS = [
    "schema_version",
    "event_kind",
    "reason_code",
    "outcome",
    "route_class",
    "candidate_class",
    "address_family",
    "region",
    "protocol_version",
    "service_config_version",
    "keyset_version",
    "latency_bucket",
    "attempt_count",
    "success_count",
    "rejection_count",
    "byte_count",
    "packet_count",
    "occupancy_count",
]

EXPECTED_RELEASE_RECORD_FIELDS = [
    "record_kind",
    "campaign_id",
    "evidence_sha256",
    "evidence_ref",
    "app_build",
    "app_version",
    "platform",
    "device_class",
    "region",
    "measurement_contract",
    "metric_name",
    "metric_value",
    "threshold_operator",
    "threshold_value",
    "sample_count",
    "successful_sample_count",
    "window_hours",
    "provider_adapter",
    "network_cell",
    "network_variant",
    "selected_route",
    "direct_outcome",
    "fallback_outcome",
    "variant_outcome",
    "latency_milliseconds",
    "memory_mib",
    "battery_percent_per_hour",
    "revocation_closure_milliseconds",
    "peak_forecast_id",
    "projected_peak_units",
    "offered_load_units",
    "unbounded_growth_event_count",
    "admission_policy_weakening_event_count",
    "false_rejection_count",
    "gate_result",
]

EXPECTED_OBSERVABILITY_ENUM_DOMAINS = {
    "schema_version": [1],
    "event_kind": EXPECTED_OBSERVABILITY_EVENT_KINDS,
    "reason_code": [
        "none",
        "policy_rejected",
        "authentication_failed",
        "route_unavailable",
        "timeout",
        "consent_lost",
        "revoked",
        "capacity_rejected",
        "protocol_rejected",
        "security_hard_stop",
        "incident_contained",
        "incident_recovered",
        "gate_failed",
        "gate_passed",
    ],
    "outcome": [
        "success",
        "failure",
        "rejected",
        "timeout",
        "cancelled",
        "unavailable",
        "opened",
        "contained",
        "recovered",
    ],
    "route_class": ["local_direct", "p2p_direct", "turn", "sealed_relay", "none"],
    "candidate_class": ["host", "server_reflexive", "peer_reflexive", "relay", "none"],
    "address_family": ["ipv4", "ipv6", "nat64", "none"],
    "latency_bucket": [
        "lt_100ms",
        "100_to_499ms",
        "500_to_1499ms",
        "1500_to_4999ms",
        "5000_to_9999ms",
        "gte_10000ms",
        "not_applicable",
    ],
    "record_kind": EXPECTED_RELEASE_RECORD_KINDS,
    "platform": ["android", "macos", "service"],
    "device_class": [
        "android_emulator_api26_arm64",
        "android_emulator_api30_arm64",
        "android_emulator_api33_arm64",
        "android_emulator_api36_arm64",
        "android_physical_api26_arm64_phone",
        "android_physical_pixel_current_supported_release",
        "android_physical_galaxy_s_android16_api36",
        "macos14_arm64",
        "macos15_arm64",
        "macos26_arm64",
        "service_control_plane",
    ],
    "measurement_contract": [
        "network_reliability_and_latency",
        "endpoint_resource_and_stability",
        "abuse_and_capacity",
        "security_hard_stops",
    ],
    "metric_name": [
        metric
        for metrics in EXPECTED_RELEASE_RECORD_METRICS.values()
        for metric in metrics
    ],
    "threshold_operator": ["minimum", "maximum", "equal"],
    "provider_adapter": ["ollama", "lm_studio", "not_applicable"],
    "network_cell": EXPECTED_NETWORK_CELL_IDS,
    "network_variant": ["none", *EXPECTED_NETWORK_VARIANT_IDS],
    "selected_route": ["local_direct", "p2p_direct", "turn_relay", "turn_tls_tcp_relay", "sealed_relay", "none"],
    "direct_outcome": ["success", "failure", "not_attempted"],
    "fallback_outcome": ["success", "failure", "not_attempted"],
    "variant_outcome": [
        "not_applicable",
        "supported_route_success_and_direct_p2p_result_reported",
        "stale_path_closed_before_authenticated_recovery",
        "authenticated_fallback_without_plaintext_or_identity_downgrade",
        "sealed_fallback_or_fail_closed_then_authenticated_recovery",
        "fail_closed_without_weaker_route_then_authenticated_recovery",
        "single_region_v1_fails_closed_then_recovers_after_service_restore",
    ],
    "gate_result": ["passed", "failed"],
}

EXPECTED_OBSERVABILITY_RANGES = {
    "protocol_version": ("integer", 1, 2147483647),
    "service_config_version": ("integer", 1, 2147483647),
    "keyset_version": ("integer", 1, 2147483647),
    "attempt_count": ("integer", 0, 2147483647),
    "success_count": ("integer", 0, 2147483647),
    "rejection_count": ("integer", 0, 2147483647),
    "byte_count": ("integer", 0, 9223372036854775807),
    "packet_count": ("integer", 0, 9223372036854775807),
    "occupancy_count": ("integer", 0, 2147483647),
    "app_build": ("integer", 1, 2147483647),
    "metric_value": ("number", 0, 1000000000000),
    "threshold_value": ("number", 0, 1000000000000),
    "sample_count": ("integer", 1, MAX_RELEASE_EVIDENCE_SAMPLES),
    "successful_sample_count": ("integer", 0, 2147483647),
    "window_hours": ("number", 0, 8760),
    "latency_milliseconds": ("integer", 0, 120000),
    "memory_mib": ("number", 0, 65536),
    "battery_percent_per_hour": ("number", 0, 100),
    "revocation_closure_milliseconds": ("integer", 0, 30000),
    "projected_peak_units": ("integer", 1, 9007199254740991),
    "offered_load_units": ("integer", 0, 9007199254740991),
    "unbounded_growth_event_count": ("integer", 0, 2147483647),
    "admission_policy_weakening_event_count": ("integer", 0, 2147483647),
    "false_rejection_count": ("integer", 0, 2147483647),
}

EXPECTED_OBSERVABILITY_PATTERNS = {
    "campaign_id": ("^rc-[0-9]{8}-[a-z0-9]{8}$", 20),
    "evidence_sha256": ("^[0-9a-f]{64}$", 64),
    "evidence_ref": ("^sha256:[0-9a-f]{64}$", 71),
    "app_version": ("^[0-9]+\\.[0-9]+\\.[0-9]+$", 32),
    "peak_forecast_id": ("^peak-[0-9]{8}-[a-z0-9]{8}$", 22),
}

EXPECTED_G0_CHECK_IDS = [
    "g0_assurance_packet",
    "full_no_device_aggregate",
    "android_and_macos_release_compilation",
    "roadmap_and_g0_checkpoint_publication",
    "production_namespaces_distribution_and_key_custody",
    "provider_compatibility_baseline",
    "service_identity_and_signer_custody",
    "privacy_incident_quality_and_operations_ownership",
    "relay_region_capacity_and_cost",
]

EXPECTED_G0_CHECK_EVIDENCE = {
    "g0_assurance_packet": [
        "canonical_assurance_hash",
        "source_hash_readback",
        "owner_acceptance",
    ],
    "full_no_device_aggregate": ["separately_authorized_full_gate_result"],
    "android_and_macos_release_compilation": [
        "android_release_compile_result",
        "macos_release_compile_result",
    ],
    "roadmap_and_g0_checkpoint_publication": [
        "reviewed_commit_scope",
        "published_checkpoint",
    ],
    "production_namespaces_distribution_and_key_custody": [
        "owned_application_ids",
        "distribution_accounts",
        "key_custody_runbook",
    ],
    "provider_compatibility_baseline": [
        "approved_minimum_current_previous_matrix"
    ],
    "service_identity_and_signer_custody": [
        "domain_dns_webpki_owners",
        "root_signer_rotation_and_revocation_owners",
    ],
    "privacy_incident_quality_and_operations_ownership": [
        "privacy_incident_and_retention_owner_approval",
        "quality_measurement_contract_owner_approvals",
    ],
    "relay_region_capacity_and_cost": [
        "approved_region_peak_capacity_and_cost_ceiling"
    ],
}

EXPECTED_FUTURE_CHECK_IDS = [
    "g1_wire_crypto_and_negative_vectors",
    "g2_service_identity_and_control_plane",
    "g3_authenticated_p2p_turn_and_sealed_fallback",
    "g4_monotonic_pair_recovery",
    "g5_signed_artifacts_and_device_provider_matrix",
    "g6_controlled_network_and_resilience_matrix",
    "g6_security_privacy_and_incident_drill",
    "g7_provenance_staged_rollout_and_readback",
]

EXPECTED_INCIDENT_CLASSES = [
    "endpoint_loss_or_key_compromise",
    "dns_webpki_service_root_or_signer_compromise",
    "relay_abuse_capacity_or_regional_outage",
    "protected_data_or_log_leakage",
    "provider_compatibility_regression",
    "bad_android_or_macos_release",
    "pair_epoch_or_revocation_divergence",
]

EXPECTED_APPROVAL_ROLES = [
    "repository_owner",
    "repository_quality_owner",
    "product_and_distribution_owner",
    "product_security_owner",
    "release_owner",
    "release_quality_owner",
    "release_network_qa_owner",
    "release_performance_qa_owner",
    "runtime_provider_compatibility_owner",
    "service_identity_owner",
    "service_security_owner",
    "service_operations_owner",
    "service_operations_and_abuse_owner",
    "privacy_and_incident_owner",
]

EXPECTED_RISK_REQUIRED_EVIDENCE = {
    "R001_protocol_schema_code_drift": [
        {"evidenceKind": "versioned_protocol_parity_gate", "requiredByGate": "g0"},
        {"evidenceKind": "reviewed_checkpoint", "requiredByGate": "g0"},
    ],
    "R002_production_namespace_signing_and_distribution_custody": [
        {"evidenceKind": "namespace_reservation", "requiredByGate": "g0"},
        {"evidenceKind": "custody_runbook", "requiredByGate": "g0"},
        {"evidenceKind": "signed_aab_and_dmg_readback", "requiredByGate": "g5"},
    ],
    "R003_service_dns_webpki_root_and_signer_compromise": [
        {"evidenceKind": "domain_and_dns_ownership", "requiredByGate": "g0"},
        {"evidenceKind": "webpki_runbook", "requiredByGate": "g0"},
        {"evidenceKind": "root_and_signer_custody_drill", "requiredByGate": "g2"},
    ],
    "R004_pair_recovery_deny_only_dos": [
        {"evidenceKind": "concurrent_revoke_rotate_reconcile_vectors", "requiredByGate": "g4"},
        {"evidenceKind": "absolute_30_second_closure_measurement", "requiredByGate": "g4"},
    ],
    "R005_relay_capacity_and_outage": [
        {"evidenceKind": "region_and_cost_approval", "requiredByGate": "g0"},
        {"evidenceKind": "two_times_peak_load_result", "requiredByGate": "g6"},
        {"evidenceKind": "turn_and_sealed_relay_outage_drills", "requiredByGate": "g6"},
    ],
    "R006_provider_compatibility": [
        {"evidenceKind": "approved_provider_matrix", "requiredByGate": "g0"},
        {"evidenceKind": "versioned_health_model_chat_results", "requiredByGate": "g5"},
    ],
    "R007_privacy_logging_and_retention": [
        {"evidenceKind": "privacy_approval", "requiredByGate": "g0"},
        {"evidenceKind": "negative_log_scan", "requiredByGate": "g6"},
        {"evidenceKind": "retention_and_deletion_audit", "requiredByGate": "g6"},
    ],
    "R008_local_store_corruption_or_stale_cache": [
        {"evidenceKind": "corruption_and_stale_cache_regressions", "requiredByGate": "g4"},
        {"evidenceKind": "monotonic_state_persistence_tests", "requiredByGate": "g4"},
    ],
    "R009_evidence_matrix_gap": [
        {"evidenceKind": "full_no_device_gate", "requiredByGate": "g0"},
        {"evidenceKind": "physical_device_matrix", "requiredByGate": "g5"},
        {"evidenceKind": "controlled_network_matrix", "requiredByGate": "g6"},
        {"evidenceKind": "signed_rc_campaign", "requiredByGate": "g6"},
    ],
    "R010_rollback_monotonicity": [
        {"evidenceKind": "100_percent_rollback_drill", "requiredByGate": "g6"},
        {"evidenceKind": "security_state_non_regression_readback", "requiredByGate": "g6"},
    ],
}

EXPECTED_G0_CLOSURE_CONTRACT = {
    "schemaVersion": 1,
    "sourceBindings": {
        "blockers": "docs/v1/g0/decision-v1.json#/blockers",
        "g0ExitChecks": "#/releaseChecklist/g0Exit",
        "approvals": "#/approvals",
        "measurementContracts": (
            "docs/v1/g0/decision-v1.json#/qualityGates/measurementContracts"
        ),
    },
    "approvalReceiptProfile": {
        "exactFields": [
            "role",
            "ownerIdentityRef",
            "status",
            "acceptedRevision",
            "acceptedPublicationCommit",
            "acceptedBlockerIds",
            "acceptedAt",
            "acceptanceEvidenceRefs",
        ],
        "statusDomain": ["blocked_unassigned", "accepted"],
        "ownerIdentityRefPolicy": (
            "nonempty_opaque_non_secret_accountable_identity_reference"
        ),
        "acceptedRevisionPolicy": (
            "lowercase_sha256_of_exact_published_checkpoint_bytes"
        ),
        "acceptedPublicationCommitPolicy": (
            "exact_lowercase_git_commit_object_id_containing_the_accepted_checkpoint"
        ),
        "acceptedBlockerIdsPolicy": (
            "ordered_unique_nonempty_subset_of_blocker_requirements_for_this_role_when_accepted"
        ),
        "acceptedAtPolicy": "rfc3339_utc",
        "acceptanceEvidenceRefsPolicy": (
            "ordered_unique_nonempty_verified_evidence_catalog_ids_when_accepted"
        ),
        "blockedUnassignedStatePolicy": (
            "owner_identity_revision_publication_commit_and_timestamp_null_with_empty_blocker_and_evidence_lists"
        ),
        "acceptedStatePolicy": (
            "owner_identity_revision_publication_commit_timestamp_blocker_ids_and_evidence_refs_all_nonempty"
        ),
        "publicationBindingPolicy": (
            "accepted_revision_equals_verified_publication_checkpoint_sha256_and_accepted_publication_commit_equals_verified_publication_commit_object_id"
        ),
    },
    "evidenceCatalogRecordProfile": {
        "exactFields": [
            "evidenceId",
            "evidenceKind",
            "evidenceClass",
            "subjectImplementationRevision",
            "subjectCheckpointSha256",
            "artifactPath",
            "artifactSha256",
            "verificationMethod",
            "verifiedAt",
            "verificationResult",
        ],
        "evidenceIdPattern": "^g0-evidence-[a-z0-9_-]{1,96}$",
        "sha256Pattern": "^[0-9a-f]{64}$",
        "artifactPathPolicy": (
            "exact_repository_relative_regular_non_symlink_sanitized_receipt"
        ),
        "verifiedAtPolicy": "rfc3339_utc",
        "verificationResultDomain": ["verified"],
        "sensitiveDataPolicy": (
            "no_credentials_keys_tokens_personal_contacts_pairing_material_or_private_account_data"
        ),
    },
    "gateReceiptProfile": {
        "exactFields": [
            "checkId",
            "authorizationRef",
            "sourcePublicationCommit",
            "commandProfileId",
            "startedAt",
            "completedAt",
            "exitCode",
            "result",
            "sanitizedLogSha256",
        ],
        "checkIdPolicy": "exact_g0_exit_check_id",
        "authorizationRefPattern": G0_AUTHORIZATION_REF_PATTERN,
        "authorizationRefPolicy": (
            "nonempty_versioned_authority_reference_authorizing_the_exact_command_profile_and_side_effects"
        ),
        "sourcePublicationCommitPolicy": (
            "exact_verified_publication_commit_object_id"
        ),
        "commandProfileIdPattern": G0_COMMAND_PROFILE_ID_PATTERN,
        "commandProfileIdPolicy": (
            "nonempty_immutable_versioned_command_profile_id"
        ),
        "timestampPolicy": "rfc3339_utc_started_at_not_after_completed_at",
        "exitCodePolicy": "exact_integer_zero",
        "resultDomain": ["passed"],
        "sanitizedLogSha256Policy": (
            "lowercase_sha256_of_exact_sanitized_log_bytes"
        ),
        "sourceTreePolicy": (
            "command_executes_from_the_exact_source_publication_commit"
        ),
    },
    "publicationReceiptProfile": {
        "exactFields": [
            "repositoryRef",
            "commitObjectId",
            "checkpointPath",
            "checkpointSha256",
            "remoteReadbackAt",
            "remoteReadbackSha256",
            "result",
        ],
        "repositoryRefPolicy": (
            "nonempty_opaque_non_secret_repository_identity_equal_to_the_expected_publication_target"
        ),
        "commitObjectIdPattern": G0_GIT_OBJECT_ID_PATTERN,
        "checkpointPathPattern": G0_CHECKPOINT_PATH_PATTERN,
        "sha256Pattern": G0_SHA256_PATTERN,
        "remoteReadbackAtPolicy": "rfc3339_utc",
        "resultDomain": ["verified"],
        "commitContainmentPolicy": (
            "resolved_commit_tree_checkpoint_path_exact_bytes_hash_to_checkpoint_sha256"
        ),
        "remoteEqualityPolicy": (
            "remote_readback_sha256_equals_checkpoint_sha256"
        ),
        "expectedIdentityPolicy": (
            "repository_commit_path_and_checkpoint_sha256_equal_the_explicitly_reviewed_publication_target"
        ),
    },
    "receiptActivationPolicy": {
        "currentCandidateState": (
            "all_receipts_absent_all_approvals_blocked_unassigned_and_no_receipt_validation_api_active"
        ),
        "receiptDerivedTrustAnchorsAllowed": False,
        "successorValidatorRequired": True,
        "validationContextPolicy": (
            "module_owned_factory_only_opaque_deep_immutable_and_built_only_from_canonical_contracts_independent_verifier_outputs_and_exact_artifact_bytes"
        ),
        "successorActivationPrerequisites": [
            "canonical_closure_digest_and_version_with_internally_derived_roles_role_blocker_scopes_blocker_checks_evidence_kinds_and_exact_check_set",
            "one_reviewed_publication_target_with_actual_commit_tree_checkpoint_bytes_and_independently_acquired_remote_checkpoint_bytes_all_hash_equal",
            "verified_evidence_catalog_records_with_authenticated_provenance_subject_revision_checkpoint_binding_safe_paths_actual_artifact_byte_hashes_result_time_and_blocker_relevance",
            "one_nonambiguous_versioned_authority_binding_per_check_with_exact_command_argv_environment_cwd_digest_allowed_side_effects_source_commit_validity_revocation_and_provenance",
            "trusted_runner_attestation_per_gate_binding_source_commit_exact_command_digest_ordered_times_exit_result_and_actual_sanitized_log_bytes_hash",
            "trusted_owner_identity_or_key_and_authenticated_acceptance_covering_every_approval_receipt_field",
            "exact_final_coverage_of_every_required_role_blocker_pair_check_and_evidence_kind_with_duplicate_ambiguity_and_partial_bundle_rejection",
        ],
        "partialBundleAcceptanceAllowed": False,
        "receiptActivationBeforePrerequisitesAllowed": False,
    },
    "derivedEvidenceKinds": {
        "owner_acceptance": (
            "all_required_owner_roles_have_accepted_the_exact_checkpoint_publication_and_scoped_blocker_ids"
        ),
        "quality_measurement_contract_owner_approvals": (
            "release_quality_owner_and_all_four_exact_measurement_contract_owner_roles_have_accepted_quality_measurement_owners"
        ),
    },
    "blockerRequirements": [
        {
            "blockerId": "g0_assurance_artifacts_and_baseline_gate",
            "requiredCheckIds": [
                "g0_assurance_packet",
                "full_no_device_aggregate",
                "android_and_macos_release_compilation",
            ],
            "requiredOwnerRoles": [
                "repository_quality_owner",
                "release_quality_owner",
            ],
            "requiredEvidenceKinds": [
                "canonical_assurance_hash",
                "source_hash_readback",
                "owner_acceptance",
                "separately_authorized_full_gate_result",
                "android_release_compile_result",
                "macos_release_compile_result",
            ],
        },
        {
            "blockerId": "roadmap_and_g0_checkpoint_publication",
            "requiredCheckIds": ["roadmap_and_g0_checkpoint_publication"],
            "requiredOwnerRoles": ["repository_owner"],
            "requiredEvidenceKinds": ["reviewed_commit_scope", "published_checkpoint"],
        },
        {
            "blockerId": "production_application_namespaces",
            "requiredCheckIds": [
                "production_namespaces_distribution_and_key_custody"
            ],
            "requiredOwnerRoles": ["product_and_distribution_owner"],
            "requiredEvidenceKinds": ["owned_application_ids"],
        },
        {
            "blockerId": "distribution_account_and_key_owners",
            "requiredCheckIds": [
                "production_namespaces_distribution_and_key_custody"
            ],
            "requiredOwnerRoles": ["release_owner"],
            "requiredEvidenceKinds": ["distribution_accounts", "key_custody_runbook"],
        },
        {
            "blockerId": "provider_compatibility_baseline",
            "requiredCheckIds": ["provider_compatibility_baseline"],
            "requiredOwnerRoles": ["runtime_provider_compatibility_owner"],
            "requiredEvidenceKinds": ["approved_minimum_current_previous_matrix"],
        },
        {
            "blockerId": "service_domain_dns_and_webpki_owners",
            "requiredCheckIds": ["service_identity_and_signer_custody"],
            "requiredOwnerRoles": ["service_identity_owner"],
            "requiredEvidenceKinds": ["domain_dns_webpki_owners"],
        },
        {
            "blockerId": "service_root_and_online_signer_owners",
            "requiredCheckIds": ["service_identity_and_signer_custody"],
            "requiredOwnerRoles": ["service_security_owner"],
            "requiredEvidenceKinds": [
                "root_signer_rotation_and_revocation_owners"
            ],
        },
        {
            "blockerId": "privacy_incident_and_retention_owners",
            "requiredCheckIds": [
                "privacy_incident_quality_and_operations_ownership"
            ],
            "requiredOwnerRoles": ["privacy_and_incident_owner"],
            "requiredEvidenceKinds": [
                "privacy_incident_and_retention_owner_approval"
            ],
        },
        {
            "blockerId": "quality_measurement_owners",
            "requiredCheckIds": [
                "privacy_incident_quality_and_operations_ownership"
            ],
            "requiredOwnerRoles": [
                "release_quality_owner",
                "release_network_qa_owner",
                "release_performance_qa_owner",
                "service_operations_and_abuse_owner",
                "product_security_owner",
            ],
            "requiredEvidenceKinds": [
                "quality_measurement_contract_owner_approvals"
            ],
        },
        {
            "blockerId": "relay_region_capacity_and_cost_budget",
            "requiredCheckIds": ["relay_region_capacity_and_cost"],
            "requiredOwnerRoles": ["service_operations_owner"],
            "requiredEvidenceKinds": [
                "approved_region_peak_capacity_and_cost_ceiling"
            ],
        },
    ],
    "derivationRules": {
        "blockerClosed": (
            "all_required_evidence_kinds_verified_and_all_required_owner_roles_accepted_exact_revision_publication_and_blocker_scope"
        ),
        "checkPassed": (
            "all_blockers_referencing_check_id_closed_and_all_existing_check_required_evidence_satisfied"
        ),
        "allOwnersNamed": (
            "every_required_owner_role_has_one_nonempty_unique_owner_identity_ref"
        ),
        "allApprovalsAccepted": (
            "every_required_owner_role_has_one_accepted_receipt"
        ),
        "remainingBlockerIds": "decision_blocker_order_filtered_to_not_closed",
        "g0AssuranceBlockerClosed": (
            "g0_assurance_artifacts_and_baseline_gate_is_closed"
        ),
        "g0ExitComplete": (
            "remaining_blocker_ids_empty_and_all_nine_g0_exit_checks_passed"
        ),
        "g1aMayStartNow": (
            "always_false_until_separate_versioned_g1a_authority_record"
        ),
    },
}

EXPECTED_MONOTONIC_STATE = [
    "protocol_floor",
    "service_config_version",
    "keyset_version",
    "pair_epoch",
    "revocation_counter",
    "lease_generation",
]

EXPECTED_CI_TIERS = [
    "pr_fast",
    "merge_full",
    "nightly_product",
    "controlled_network_nightly",
    "weekly_resilience",
    "release_candidate",
]

FALSE_AUTHORITIES = [
    "g1aNoNetworkImplementationAllowed",
    "g1bLoopbackSocketAllowed",
    "p2pSourceAcquisitionAllowed",
    "p2pLibrarySelectionAllowed",
    "p2pCompilerInvocationAllowed",
    "socketCreationAllowed",
    "runtimeNetworkIoAllowed",
    "externalTestNetworkAllowed",
    "productionNetworkIoAllowed",
    "productionKeyGenerationOrInjectionAllowed",
    "signingOrNotarizationAllowed",
    "storeUploadAllowed",
    "productionDeploymentAllowed",
]

_G0_RECEIPT_BUNDLE_ABSENT = object()
G0_RECEIPT_ACTIVATION_DISABLED_MESSAGE = (
    "G0 receipt activation is disabled until a successor canonical contract "
    "and independently anchored validation context satisfy every activation "
    "prerequisite"
)


def collect_failures(
    *,
    raw_json: str | None = None,
    markdown: str | None = None,
    root: Path = ROOT,
    verify_files: bool = True,
    receipt_bundle: object = _G0_RECEIPT_BUNDLE_ABSENT,
) -> list[str]:
    failures: list[str] = []
    if raw_json is None:
        try:
            raw_json = (root / "docs/v1/g0/decision-v1.json").read_text(
                encoding="utf-8"
            )
        except OSError as error:
            return [f"cannot read G0 JSON: {error}"]

    try:
        document = json.loads(
            raw_json,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite,
            parse_float=parse_g0_finite_float,
            parse_int=parse_g0_bounded_integer,
        )
    except DuplicateJSONKeyError as error:
        return [f"G0 JSON contains duplicate key {error.args[0]!r}"]
    except NonFiniteJSONNumberError as error:
        return [f"G0 JSON contains non-finite number {error.args[0]!r}"]
    except G0JSONNumberError as error:
        return [
            "G0 JSON contains an integer exceeding "
            f"{MAX_G0_JSON_INTEGER_DIGITS} digits: {error.args[0]!r}"
        ]
    except json.JSONDecodeError as error:
        return [f"G0 JSON is invalid: {error.msg}"]

    document = exact_keys(
        document,
        {
            "documentType",
            "schemaVersion",
            "decisionId",
            "recordedDate",
            "status",
            "approvalSource",
            "baseline",
            "productScope",
            "networkMatrix",
            "releasePolicy",
            "securitySelections",
            "operationsAndPrivacy",
            "qualityGates",
            "ciTiers",
            "authority",
            "blockers",
            "sourceRecords",
            "supersession",
            "nextGate",
        },
        "G0 decision",
        failures,
    )
    require_equal(document.get("documentType"), "aetherlink.v1-g0-decision", "documentType", failures)
    require_equal(document.get("schemaVersion"), "1.0", "schemaVersion", failures)
    require_equal(document.get("decisionId"), "aetherlink_v1_g0_decision_v1", "decisionId", failures)
    require_equal(document.get("recordedDate"), "2026-07-20", "recordedDate", failures)
    require_equal(document.get("status"), "blocked_before_g1a", "status", failures)
    require_equal(
        document.get("approvalSource"),
        "user_delegated_canonical_v1_roadmap_execution_20260720",
        "approvalSource",
        failures,
    )
    require_equal(
        canonical_json_sha256(document),
        EXPECTED_DECISION_CANONICAL_SHA256,
        "G0 decision canonical sha256",
        failures,
    )

    baseline = exact_keys(
        document.get("baseline"),
        {
            "repository",
            "branch",
            "implementationRevision",
            "originAlignedAtInspection",
            "roadmapPath",
            "roadmapCheckpointState",
            "deviceState",
            "physicalEvidence",
            "productionEvidence",
        },
        "baseline",
        failures,
    )
    require_equal(
        baseline.get("repository"),
        "source_repository_root",
        "baseline.repository",
        failures,
    )
    require_equal(baseline.get("branch"), "main", "baseline.branch", failures)
    require_equal(
        baseline.get("implementationRevision"),
        "d32c1846eead13ab1462619145fc4da1194cce7e",
        "baseline.implementationRevision",
        failures,
    )
    require_equal(baseline.get("originAlignedAtInspection"), True, "baseline.originAlignedAtInspection", failures)
    require_equal(baseline.get("roadmapCheckpointState"), "uncommitted", "baseline.roadmapCheckpointState", failures)
    require_equal(baseline.get("deviceState"), "no_android_device_attached", "baseline.deviceState", failures)
    require_equal(baseline.get("productionEvidence"), "none", "baseline.productionEvidence", failures)

    product = exact_keys(
        document.get("productScope"),
        {"releaseVersion", "p2pIsGaGate", "platforms", "locales", "providers", "requiredUserLoop", "postV1"},
        "productScope",
        failures,
    )
    require_equal(product.get("releaseVersion"), "1.0.0", "productScope.releaseVersion", failures)
    require_equal(product.get("p2pIsGaGate"), True, "productScope.p2pIsGaGate", failures)
    require_equal(product.get("locales"), ["en", "ko", "ja", "zh-Hans", "fr"], "productScope.locales", failures)
    platforms = exact_keys(product.get("platforms"), {"android", "macos"}, "productScope.platforms", failures)
    android = exact_keys(
        platforms.get("android"),
        {"minimumApi", "targetApi", "compileApi", "productionDeviceAbis", "formFactors", "freshPairingRequiresCamera", "emulatorApiMatrix", "physicalMatrix"},
        "productScope.platforms.android",
        failures,
    )
    for field, expected in (("minimumApi", 26), ("targetApi", 36), ("compileApi", 36)):
        require_equal(android.get(field), expected, f"android.{field}", failures)
    require_equal(android.get("productionDeviceAbis"), ["arm64-v8a"], "android.productionDeviceAbis", failures)
    require_equal(android.get("formFactors"), ["phone"], "android.formFactors", failures)
    require_equal(android.get("freshPairingRequiresCamera"), True, "android.freshPairingRequiresCamera", failures)
    require_equal(android.get("emulatorApiMatrix"), [26, 30, 33, 36], "android.emulatorApiMatrix", failures)
    require_equal(
        android.get("physicalMatrix"),
        [
            "api26_arm64_phone",
            "pixel_current_supported_release",
            "galaxy_s_android16_api36",
        ],
        "android.physicalMatrix",
        failures,
    )
    macos = exact_keys(
        platforms.get("macos"),
        {"minimumMajorVersion", "architectures", "releaseTestMajorVersions", "intelDisposition"},
        "productScope.platforms.macos",
        failures,
    )
    require_equal(macos.get("minimumMajorVersion"), 14, "macos.minimumMajorVersion", failures)
    require_equal(macos.get("architectures"), ["arm64"], "macos.architectures", failures)
    require_equal(macos.get("releaseTestMajorVersions"), [14, 15, 26], "macos.releaseTestMajorVersions", failures)
    require_equal(macos.get("intelDisposition"), "post_v1", "macos.intelDisposition", failures)

    providers = product.get("providers")
    if not isinstance(providers, list):
        failures.append("productScope.providers must be a list")
    else:
        provider_ids: list[object] = []
        for index, provider in enumerate(providers):
            item = exact_keys(
                provider,
                {
                    "id",
                    "access",
                    "g0ObservedVersion",
                    "minimumSupportedVersion",
                    "releasePolicy",
                },
                f"productScope.providers[{index}]",
                failures,
            )
            provider_ids.append(item.get("id"))
            require_equal(item.get("access"), "runtime_host_only", f"providers[{index}].access", failures)
            require_equal(item.get("minimumSupportedVersion"), None, f"providers[{index}].minimumSupportedVersion", failures)
            require_equal(
                item.get("releasePolicy"),
                "exact_rc_current_stable_and_previous_verified_versions",
                f"providers[{index}].releasePolicy",
                failures,
            )
        require_equal(provider_ids, ["ollama", "lm_studio"], "provider order", failures)

    network = exact_keys(
        document.get("networkMatrix"),
        {
            "measurementUnit",
            "successGate",
            "directP2pReporting",
            "requiredCells",
            "requiredVariants",
            "applicabilityRules",
        },
        "networkMatrix",
        failures,
    )
    require_equal(
        network.get("measurementUnit"),
        "completed_authenticated_session_attempt",
        "networkMatrix.measurementUnit",
        failures,
    )
    require_equal(
        network.get("successGate"),
        "supported_route_success_per_required_cell",
        "networkMatrix.successGate",
        failures,
    )
    require_equal(
        network.get("directP2pReporting"),
        "release_gate_for_required_success_cells_and_separate_kpi_for_other_attempt_cells",
        "networkMatrix.directP2pReporting",
        failures,
    )
    cells = network.get("requiredCells")
    if not isinstance(cells, list):
        failures.append("networkMatrix.requiredCells must be a list")
    else:
        cell_ids: list[object] = []
        for index, cell in enumerate(cells):
            item = exact_keys(
                cell,
                {
                    "id",
                    "relationship",
                    "networkCondition",
                    "p2pAttemptRequired",
                    "p2pExpectation",
                    "authenticatedCompletionRoutes",
                },
                f"networkMatrix.requiredCells[{index}]",
                failures,
            )
            cell_ids.append(item.get("id"))
            if type(item.get("p2pAttemptRequired")) is not bool:
                failures.append(f"networkMatrix.requiredCells[{index}].p2pAttemptRequired must be a bool")
            if item.get("p2pExpectation") not in {"required_success", "attempt_and_report", "not_applicable"}:
                failures.append(f"networkMatrix.requiredCells[{index}].p2pExpectation is invalid")
            routes = item.get("authenticatedCompletionRoutes")
            if not isinstance(routes, list) or not routes or not all(isinstance(route, str) and route for route in routes):
                failures.append(f"networkMatrix.requiredCells[{index}].authenticatedCompletionRoutes must be nonblank strings")
        require_equal(cell_ids, EXPECTED_NETWORK_CELL_IDS, "network matrix cell order", failures)
    variants = network.get("requiredVariants")
    if not isinstance(variants, list):
        failures.append("networkMatrix.requiredVariants must be a list")
    else:
        variant_ids: list[object] = []
        for index, variant in enumerate(variants):
            item = exact_keys(
                variant,
                {"id", "appliesToCells", "requiredOutcome"},
                f"networkMatrix.requiredVariants[{index}]",
                failures,
            )
            variant_ids.append(item.get("id"))
            applies = item.get("appliesToCells")
            if not isinstance(applies, list) or not applies or not all(cell in EXPECTED_NETWORK_CELL_IDS for cell in applies):
                failures.append(f"networkMatrix.requiredVariants[{index}].appliesToCells must name required cells")
            if not isinstance(item.get("requiredOutcome"), str) or not item.get("requiredOutcome"):
                failures.append(f"networkMatrix.requiredVariants[{index}].requiredOutcome must be nonblank")
        require_equal(variant_ids, EXPECTED_NETWORK_VARIANT_IDS, "network matrix variant order", failures)
    applicability = exact_keys(
        network.get("applicabilityRules"),
        {
            "allRequiredCellsMustRunForGa",
            "allRequiredVariantsMustRunForGa",
            "cellOmissionAllowed",
            "variantOmissionAllowed",
            "routeNotApplicableDoesNotOmitCell",
            "p2pDirectIsSeparateKpiWhereAttemptRequired",
            "p2pRequiredSuccessCells",
            "bothProvidersCoveredInEveryCell",
            "releasePlatformRowsCoveredAcrossEveryRouteClass",
            "excludedAsUnsupported",
        },
        "networkMatrix.applicabilityRules",
        failures,
    )
    for field, expected in (
        ("allRequiredCellsMustRunForGa", True),
        ("allRequiredVariantsMustRunForGa", True),
        ("cellOmissionAllowed", False),
        ("variantOmissionAllowed", False),
        ("routeNotApplicableDoesNotOmitCell", True),
        ("p2pDirectIsSeparateKpiWhereAttemptRequired", True),
        ("bothProvidersCoveredInEveryCell", True),
        ("releasePlatformRowsCoveredAcrossEveryRouteClass", True),
    ):
        require_equal(applicability.get(field), expected, f"networkMatrix.applicabilityRules.{field}", failures)
    require_equal(
        applicability.get("p2pRequiredSuccessCells"),
        ["unrelated_native_ipv6_p2p", "unrelated_home_nat_ipv4"],
        "networkMatrix.applicabilityRules.p2pRequiredSuccessCells",
        failures,
    )

    release = exact_keys(
        document.get("releasePolicy"),
        {"android", "macos", "versioning", "compatibility"},
        "releasePolicy",
        failures,
    )
    android_release = exact_keys(
        release.get("android"),
        {
            "currentApplicationId",
            "productionApplicationId",
            "channel",
            "signing",
            "artifact",
            "currentDebugDataMigration",
            "rollback",
        },
        "releasePolicy.android",
        failures,
    )
    macos_release = exact_keys(
        release.get("macos"),
        {
            "currentBundleId",
            "productionBundleId",
            "channel",
            "signing",
            "artifact",
            "updateModel",
            "rollback",
        },
        "releasePolicy.macos",
        failures,
    )
    versioning = exact_keys(
        release.get("versioning"),
        {
            "marketingVersion",
            "buildNumberRule",
            "androidVersionCodeRule",
            "macosBundleVersionRule",
        },
        "releasePolicy.versioning",
        failures,
    )
    compatibility = exact_keys(
        release.get("compatibility"),
        {"wireAndService", "databaseMigration", "monotonicSecurityState"},
        "releasePolicy.compatibility",
        failures,
    )
    require_equal(android_release.get("currentApplicationId"), "com.localagentbridge.android", "releasePolicy.android.currentApplicationId", failures)
    require_equal(android_release.get("productionApplicationId"), None, "releasePolicy.android.productionApplicationId", failures)
    require_equal(android_release.get("channel"), "google_play_closed_testing_then_staged_production", "releasePolicy.android.channel", failures)
    require_equal(android_release.get("signing"), "play_app_signing_with_separate_upload_key", "releasePolicy.android.signing", failures)
    require_equal(android_release.get("artifact"), "signed_aab", "releasePolicy.android.artifact", failures)
    require_equal(android_release.get("currentDebugDataMigration"), "unsupported_clean_install_and_fresh_pair_required", "releasePolicy.android.currentDebugDataMigration", failures)
    require_equal(macos_release.get("currentBundleId"), "dev.aetherlink.companion", "releasePolicy.macos.currentBundleId", failures)
    require_equal(macos_release.get("productionBundleId"), None, "releasePolicy.macos.productionBundleId", failures)
    require_equal(macos_release.get("channel"), "direct_distribution", "releasePolicy.macos.channel", failures)
    require_equal(macos_release.get("signing"), "developer_id_application_hardened_runtime_notarization", "releasePolicy.macos.signing", failures)
    require_equal(macos_release.get("artifact"), "notarized_stapled_signed_dmg", "releasePolicy.macos.artifact", failures)
    require_equal(macos_release.get("updateModel"), "manual_signed_update_for_v1", "releasePolicy.macos.updateModel", failures)
    require_equal(versioning.get("marketingVersion"), "1.0.0", "releasePolicy.versioning.marketingVersion", failures)
    require_equal(compatibility.get("wireAndService"), "n_and_n_minus_1", "releasePolicy.compatibility.wireAndService", failures)

    security = exact_keys(
        document.get("securitySelections"),
        {"fallbackProfile", "relayControlPlane", "pairRecovery", "g1SuiteInput", "routeAuthorization"},
        "securitySelections",
        failures,
    )
    fallback = exact_keys(
        security.get("fallbackProfile"),
        {"profileId", "disposition", "direct", "ordinaryFallback", "emergencyFallback", "applicationReadiness"},
        "securitySelections.fallbackProfile",
        failures,
    )
    require_equal(fallback.get("profileId"), "production_p2p_nat_v1_recommended", "fallbackProfile.profileId", failures)
    require_equal(fallback.get("disposition"), "retained_without_supersession", "fallbackProfile.disposition", failures)
    require_equal(fallback.get("direct"), "authenticated_encrypted_ice", "fallbackProfile.direct", failures)
    require_equal(fallback.get("ordinaryFallback"), "bounded_turn", "fallbackProfile.ordinaryFallback", failures)
    require_equal(fallback.get("emergencyFallback"), "relay_only_sealed_signaling", "fallbackProfile.emergencyFallback", failures)
    require_equal(fallback.get("applicationReadiness"), "transport_neutral_endpoint_identity_session", "fallbackProfile.applicationReadiness", failures)
    relay = exact_keys(
        security.get("relayControlPlane"),
        {
            "selection",
            "tlsTrust",
            "serviceDomains",
            "configurationTrust",
            "leaseSigner",
            "futureSplitCompatible",
            "relayIsEndpointTrustTerminator",
        },
        "securitySelections.relayControlPlane",
        failures,
    )
    require_equal(relay.get("selection"), "tls_1_3_plus_signed_lease_capabilities", "relayControlPlane.selection", failures)
    require_equal(relay.get("tlsTrust"), "public_webpki_for_public_service_endpoints", "relayControlPlane.tlsTrust", failures)
    require_equal(relay.get("serviceDomains"), None, "relayControlPlane.serviceDomains", failures)
    require_equal(relay.get("configurationTrust"), "app_bundled_offline_aetherlink_root", "relayControlPlane.configurationTrust", failures)
    require_equal(relay.get("leaseSigner"), "offline_root_delegated_non_exportable_online_key", "relayControlPlane.leaseSigner", failures)
    require_equal(relay.get("futureSplitCompatible"), True, "relayControlPlane.futureSplitCompatible", failures)
    require_equal(relay.get("relayIsEndpointTrustTerminator"), False, "relayControlPlane.relayIsEndpointTrustTerminator", failures)
    recovery = exact_keys(
        security.get("pairRecovery"),
        {
            "selection",
            "normalRenewal",
            "emergencyRevocation",
            "denyOnlyDosTradeoffAccepted",
            "keyReplacement",
            "bindingFields",
            "bindingTargets",
            "replacementRotatesEndpointTrafficSecret",
            "replacementRotatesRouteTokenSeed",
            "offlineReactivationRequiresCurrentSignedReceipt",
            "statusReconciliation",
            "silentOneSidedKeyReplacementAllowed",
        },
        "securitySelections.pairRecovery",
        failures,
    )
    require_equal(recovery.get("selection"), "monotonic_pair_epoch_state_machine", "pairRecovery.selection", failures)
    require_equal(recovery.get("normalRenewal"), "runtime_and_client_coauthorized", "pairRecovery.normalRenewal", failures)
    require_equal(recovery.get("emergencyRevocation"), "either_current_endpoint_deny_only", "pairRecovery.emergencyRevocation", failures)
    require_equal(recovery.get("denyOnlyDosTradeoffAccepted"), True, "pairRecovery.denyOnlyDosTradeoffAccepted", failures)
    require_equal(recovery.get("keyReplacement"), "fresh_qr_and_incremented_pair_epoch", "pairRecovery.keyReplacement", failures)
    require_equal(recovery.get("bindingFields"), ["pair_id", "pair_epoch"], "pairRecovery.bindingFields", failures)
    require_equal(
        recovery.get("bindingTargets"),
        ["lease", "registration", "endpoint_transcript", "route_refresh", "application_authentication"],
        "pairRecovery.bindingTargets",
        failures,
    )
    require_equal(recovery.get("replacementRotatesEndpointTrafficSecret"), True, "pairRecovery.replacementRotatesEndpointTrafficSecret", failures)
    require_equal(recovery.get("replacementRotatesRouteTokenSeed"), True, "pairRecovery.replacementRotatesRouteTokenSeed", failures)
    require_equal(recovery.get("offlineReactivationRequiresCurrentSignedReceipt"), True, "pairRecovery.offlineReactivationRequiresCurrentSignedReceipt", failures)
    require_equal(recovery.get("statusReconciliation"), "signed_read_only_pair_status", "pairRecovery.statusReconciliation", failures)
    require_equal(recovery.get("silentOneSidedKeyReplacementAllowed"), False, "pairRecovery.silentOneSidedKeyReplacementAllowed", failures)
    suite = exact_keys(
        security.get("g1SuiteInput"),
        {"status", "profile", "exactTranscriptAndProviderSelectionFrozen"},
        "securitySelections.g1SuiteInput",
        failures,
    )
    require_equal(suite.get("status"), "candidate_requires_g1_ratification", "g1SuiteInput.status", failures)
    require_equal(suite.get("profile"), "platform_native_p256_hkdf_sha256_aes256gcm", "g1SuiteInput.profile", failures)
    require_equal(suite.get("exactTranscriptAndProviderSelectionFrozen"), False, "g1SuiteInput.exactTranscriptAndProviderSelectionFrozen", failures)
    route = exact_keys(
        security.get("routeAuthorization"),
        {
            "commonField",
            "localDirectServiceLeaseRequired",
            "localDirectServiceCapabilityRequired",
            "serviceMediatedP2pCandidatePublishCapabilityRequired",
            "serviceMediatedP2pCandidateFetchCapabilityRequired",
            "capabilityFreeRemoteP2pAllowed",
            "sealedRelaySignedCapabilityRequired",
            "turnSignedCapabilityRequired",
            "crossKindDigestInterpretationAllowed",
        },
        "securitySelections.routeAuthorization",
        failures,
    )
    require_equal(route.get("commonField"), "route_authorization_kind_and_canonical_digest", "routeAuthorization.commonField", failures)
    require_equal(route.get("localDirectServiceLeaseRequired"), False, "routeAuthorization.localDirectServiceLeaseRequired", failures)
    require_equal(route.get("localDirectServiceCapabilityRequired"), False, "routeAuthorization.localDirectServiceCapabilityRequired", failures)
    require_equal(route.get("serviceMediatedP2pCandidatePublishCapabilityRequired"), True, "routeAuthorization.serviceMediatedP2pCandidatePublishCapabilityRequired", failures)
    require_equal(route.get("serviceMediatedP2pCandidateFetchCapabilityRequired"), True, "routeAuthorization.serviceMediatedP2pCandidateFetchCapabilityRequired", failures)
    require_equal(route.get("capabilityFreeRemoteP2pAllowed"), False, "routeAuthorization.capabilityFreeRemoteP2pAllowed", failures)
    require_equal(route.get("sealedRelaySignedCapabilityRequired"), True, "routeAuthorization.sealedRelaySignedCapabilityRequired", failures)
    require_equal(route.get("turnSignedCapabilityRequired"), True, "routeAuthorization.turnSignedCapabilityRequired", failures)
    require_equal(route.get("crossKindDigestInterpretationAllowed"), False, "routeAuthorization.crossKindDigestInterpretationAllowed", failures)

    operations = exact_keys(
        document.get("operationsAndPrivacy"),
        {
            "operatorClass",
            "initialRegionCount",
            "serviceContentPolicy",
            "stablePairIdentifierInLogsAllowed",
            "rawCandidateOrIpInLogsAllowed",
            "aggregateOperationalMetricsRetentionDays",
            "sourceFreeSecurityEventRetentionDays",
            "sanitizedIncidentEvidenceRetentionDays",
            "contentFreeReleaseRecordRetentionDays",
            "capabilityMaximumLifetimeSeconds",
            "maximumClockSkewSeconds",
            "expiredAuthorizationStateDeletionSeconds",
            "offlineRootCustody",
            "onlineSignerCustody",
            "emergencyRevocationSeparatedFromReleaseSigning",
        },
        "operationsAndPrivacy",
        failures,
    )
    require_equal(operations.get("operatorClass"), "first_party", "operationsAndPrivacy.operatorClass", failures)
    require_equal(operations.get("stablePairIdentifierInLogsAllowed"), False, "operationsAndPrivacy.stablePairIdentifierInLogsAllowed", failures)
    require_equal(operations.get("rawCandidateOrIpInLogsAllowed"), False, "operationsAndPrivacy.rawCandidateOrIpInLogsAllowed", failures)
    require_equal(operations.get("capabilityMaximumLifetimeSeconds"), 600, "operationsAndPrivacy.capabilityMaximumLifetimeSeconds", failures)
    require_equal(operations.get("maximumClockSkewSeconds"), 30, "operationsAndPrivacy.maximumClockSkewSeconds", failures)
    require_equal(operations.get("emergencyRevocationSeparatedFromReleaseSigning"), True, "operationsAndPrivacy.emergencyRevocationSeparatedFromReleaseSigning", failures)

    quality = exact_keys(
        document.get("qualityGates"),
        {
            "minimumCompletedNetworkSessions",
            "minimumAttemptsPerRequiredTopologyCell",
            "minimumAttemptsPerRequiredVariant",
            "perCellObservedAuthenticatedSuccessMinimum",
            "perCellWilson95LowerBoundMinimum",
            "p2pRequiredCellObservedDirectSuccessMinimum",
            "p2pRequiredCellWilson95LowerBoundMinimum",
            "traversalSetupMilliseconds",
            "fullColdSetupMilliseconds",
            "authenticatedReconnectP95Milliseconds",
            "authenticatedHandoffP95Milliseconds",
            "revocationClosureMilliseconds",
            "incrementalMemoryP95MiB",
            "androidBatteryPercentPerHourMaximum",
            "closedBetaCrashFreeSessionMinimum",
            "closedBetaAnrFreeSessionMinimum",
            "rcSoakHoursMinimum",
            "falseAbuseRejectionMaximum",
            "rollbackSuccessMinimum",
            "securityHardStops",
            "capacityRule",
            "measurementContracts",
        },
        "qualityGates",
        failures,
    )
    require_equal(quality.get("minimumCompletedNetworkSessions"), 1200, "qualityGates.minimumCompletedNetworkSessions", failures)
    require_equal(quality.get("minimumAttemptsPerRequiredTopologyCell"), 100, "qualityGates.minimumAttemptsPerRequiredTopologyCell", failures)
    require_equal(quality.get("minimumAttemptsPerRequiredVariant"), 30, "qualityGates.minimumAttemptsPerRequiredVariant", failures)
    require_equal(quality.get("perCellObservedAuthenticatedSuccessMinimum"), 0.99, "qualityGates.perCellObservedAuthenticatedSuccessMinimum", failures)
    require_equal(quality.get("perCellWilson95LowerBoundMinimum"), 0.95, "qualityGates.perCellWilson95LowerBoundMinimum", failures)
    require_equal(quality.get("p2pRequiredCellObservedDirectSuccessMinimum"), 0.95, "qualityGates.p2pRequiredCellObservedDirectSuccessMinimum", failures)
    require_equal(quality.get("p2pRequiredCellWilson95LowerBoundMinimum"), 0.9, "qualityGates.p2pRequiredCellWilson95LowerBoundMinimum", failures)
    exact_keys(
        quality.get("traversalSetupMilliseconds"),
        {"p50Maximum", "p95Maximum", "p99Maximum"},
        "qualityGates.traversalSetupMilliseconds",
        failures,
    )
    exact_keys(
        quality.get("fullColdSetupMilliseconds"),
        {"p95Maximum", "p99Maximum"},
        "qualityGates.fullColdSetupMilliseconds",
        failures,
    )
    exact_keys(
        quality.get("revocationClosureMilliseconds"),
        {"p95Maximum", "p99Maximum", "absoluteMaximum"},
        "qualityGates.revocationClosureMilliseconds",
        failures,
    )
    require_equal(
        quality.get("revocationClosureMilliseconds"),
        {"p95Maximum": 10000, "p99Maximum": 30000, "absoluteMaximum": 30000},
        "qualityGates.revocationClosureMilliseconds",
        failures,
    )
    require_equal(
        quality.get("rollbackSuccessMinimum"),
        1.0,
        "qualityGates.rollbackSuccessMinimum",
        failures,
    )
    exact_keys(
        quality.get("incrementalMemoryP95MiB"),
        {"androidMaximum", "macosMaximum"},
        "qualityGates.incrementalMemoryP95MiB",
        failures,
    )
    exact_keys(
        quality.get("androidBatteryPercentPerHourMaximum"),
        {"idlePaired", "activeSession"},
        "qualityGates.androidBatteryPercentPerHourMaximum",
        failures,
    )
    hard_stops = exact_keys(
        quality.get("securityHardStops"),
        set(EXPECTED_SECURITY_HARD_STOPS),
        "qualityGates.securityHardStops",
        failures,
    )
    require_equal(hard_stops, EXPECTED_SECURITY_HARD_STOPS, "qualityGates.securityHardStops", failures)
    capacity_rule = quality.get("capacityRule")
    require_equal(capacity_rule, "pass_at_two_times_the_approved_projected_peak_without_unbounded_growth_or_weaker_admission", "qualityGates.capacityRule", failures)
    contracts = quality.get("measurementContracts")
    if not isinstance(contracts, list):
        failures.append("qualityGates.measurementContracts must be a list")
    else:
        contract_ids: list[object] = []
        for index, contract in enumerate(contracts):
            item = exact_keys(
                contract,
                {
                    "id",
                    "targetFields",
                    "ownerRole",
                    "measurementSource",
                    "sampleWindowRule",
                    "failureAction",
                },
                f"qualityGates.measurementContracts[{index}]",
                failures,
            )
            contract_ids.append(item.get("id"))
            for field in ("ownerRole", "measurementSource", "sampleWindowRule", "failureAction"):
                if not isinstance(item.get(field), str) or not item.get(field):
                    failures.append(f"qualityGates.measurementContracts[{index}].{field} must be nonblank")
            targets = item.get("targetFields")
            if not isinstance(targets, list) or not targets or not all(isinstance(target, str) and target for target in targets):
                failures.append(f"qualityGates.measurementContracts[{index}].targetFields must be nonblank strings")
            contract_id = item.get("id")
            if contract_id in EXPECTED_MEASUREMENT_TARGET_FIELDS:
                require_equal(
                    targets,
                    EXPECTED_MEASUREMENT_TARGET_FIELDS[contract_id],
                    f"qualityGates.measurementContracts[{index}].targetFields",
                    failures,
                )
        require_equal(contract_ids, EXPECTED_MEASUREMENT_CONTRACT_IDS, "measurement contract order", failures)

    require_equal(document.get("ciTiers"), EXPECTED_CI_TIERS, "ciTiers", failures)

    authority = exact_keys(
        document.get("authority"),
        {"g0DocumentationAndStaticValidationAllowed", *FALSE_AUTHORITIES},
        "authority",
        failures,
    )
    require_equal(authority.get("g0DocumentationAndStaticValidationAllowed"), True, "authority.g0DocumentationAndStaticValidationAllowed", failures)
    for field in FALSE_AUTHORITIES:
        require_equal(authority.get(field), False, f"authority.{field}", failures)

    blockers = document.get("blockers")
    if not isinstance(blockers, list):
        failures.append("blockers must be a list")
    else:
        blocker_ids: list[object] = []
        for index, blocker in enumerate(blockers):
            item = exact_keys(blocker, {"id", "ownerRole", "requiredEvidence"}, f"blockers[{index}]", failures)
            blocker_ids.append(item.get("id"))
            if not isinstance(item.get("ownerRole"), str) or not item.get("ownerRole"):
                failures.append(f"blockers[{index}].ownerRole must be nonblank")
            if not isinstance(item.get("requiredEvidence"), str) or not item.get("requiredEvidence"):
                failures.append(f"blockers[{index}].requiredEvidence must be nonblank")
        require_equal(blocker_ids, EXPECTED_BLOCKERS, "blocker order", failures)

    records = document.get("sourceRecords")
    if not isinstance(records, list):
        failures.append("sourceRecords must be a list")
    else:
        observed: dict[str, str] = {}
        for index, record in enumerate(records):
            item = exact_keys(record, {"path", "sha256"}, f"sourceRecords[{index}]", failures)
            path = item.get("path")
            digest = item.get("sha256")
            if not isinstance(path, str) or not isinstance(digest, str):
                failures.append(f"sourceRecords[{index}] path and sha256 must be strings")
                continue
            if path in observed:
                failures.append(f"sourceRecords contains duplicate path {path}")
            observed[path] = digest
        require_equal(observed, EXPECTED_SOURCE_HASHES, "sourceRecords", failures)
        if verify_files:
            for relative, expected_digest in EXPECTED_SOURCE_HASHES.items():
                path = root / relative
                if not path.is_file():
                    failures.append(f"missing G0 source record {relative}")
                elif sha256(path) != expected_digest:
                    failures.append(f"G0 source record digest drifted: {relative}")

    supersession = exact_keys(
        document.get("supersession"),
        {
            "supersedesExistingP2pProfile",
            "supersedesSelectionDecision",
            "supersedesPreNetworkDecisionV1",
            "singlePlaneFallbackRequiresProfileAndSelectionDecisionSupersession",
            "preNetworkDecisionSupersessionRequiredWhenSelectedPolicyChanges",
            "newP2pCandidateRequiresFreshAuthorityChain",
            "amendmentPolicy",
        },
        "supersession",
        failures,
    )
    require_equal(supersession.get("supersedesExistingP2pProfile"), False, "supersession.supersedesExistingP2pProfile", failures)
    require_equal(supersession.get("supersedesSelectionDecision"), False, "supersession.supersedesSelectionDecision", failures)
    require_equal(supersession.get("supersedesPreNetworkDecisionV1"), False, "supersession.supersedesPreNetworkDecisionV1", failures)
    require_equal(
        supersession.get("singlePlaneFallbackRequiresProfileAndSelectionDecisionSupersession"),
        True,
        "supersession.singlePlaneFallbackRequiresProfileAndSelectionDecisionSupersession",
        failures,
    )
    require_equal(
        supersession.get("preNetworkDecisionSupersessionRequiredWhenSelectedPolicyChanges"),
        True,
        "supersession.preNetworkDecisionSupersessionRequiredWhenSelectedPolicyChanges",
        failures,
    )
    require_equal(supersession.get("newP2pCandidateRequiresFreshAuthorityChain"), True, "supersession.newP2pCandidateRequiresFreshAuthorityChain", failures)

    next_gate = exact_keys(
        document.get("nextGate"),
        {"gate", "g1aMayStartNow", "reason"},
        "nextGate",
        failures,
    )
    require_equal(next_gate.get("gate"), "g0_blocker_closure_then_g1a_authority_v1", "nextGate.gate", failures)
    require_equal(next_gate.get("g1aMayStartNow"), False, "nextGate.g1aMayStartNow", failures)

    if verify_files:
        failures.extend(check_repository_baseline(root))

    if markdown is None:
        try:
            markdown = (root / "docs/v1/g0/decision-v1.md").read_text(encoding="utf-8")
        except OSError as error:
            failures.append(f"cannot read G0 markdown: {error}")
            markdown = ""
    required_markdown = (
        "Status: `blocked_before_g1a`",
        "P2P is a GA gate",
        "Google Play closed testing",
        "Developer ID Application signing",
        "twelve non-omittable cells",
        "Six non-omittable orthogonal variants",
        "fallback success cannot",
        "two-plane profile",
        "TLS 1.3 plus canonical signed lease",
        "deny-only emergency revocation",
        "fresh endpoint traffic secret",
        "offline endpoint must obtain a current signed state receipt",
        "`route_authorization_kind`",
        "95% Wilson",
        "quality contracts remain a G0 blocker",
        "G0 assurance artifacts and baseline gate",
        "G1a remains closed",
        "does not authorize G1a implementation",
        "`selection-decision.json`",
        "A new P2P candidate must start a",
    )
    for snippet in required_markdown:
        if snippet not in markdown:
            failures.append(f"G0 markdown is missing {snippet!r}")

    failures.extend(
        collect_assurance_failures(
            decision=document,
            root=root,
            verify_files=verify_files,
        )
    )
    if verify_files:
        failures.extend(
            f"G0 assurance checkpoint: {failure}"
            for failure in checkpoint_checker.collect_failures(root=root)
        )
        failures.extend(
            f"G0 assurance closure amendment: {failure}"
            for failure in collect_assurance_amendment_failures(root=root)
        )
    if failures:
        return failures
    if receipt_bundle is not _G0_RECEIPT_BUNDLE_ABSENT:
        return [G0_RECEIPT_ACTIVATION_DISABLED_MESSAGE]
    return failures


def collect_assurance_failures(
    *,
    decision: dict[str, object],
    root: Path = ROOT,
    verify_files: bool = True,
    raw_json: str | None = None,
    markdown: str | None = None,
) -> list[str]:
    failures: list[str] = []
    if raw_json is None:
        try:
            raw_json = (root / "docs/v1/g0/assurance-v1.json").read_text(
                encoding="utf-8"
            )
        except OSError as error:
            return [f"cannot read G0 assurance JSON: {error}"]

    try:
        assurance = json.loads(
            raw_json,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite,
            parse_float=parse_g0_finite_float,
            parse_int=parse_g0_bounded_integer,
        )
    except DuplicateJSONKeyError as error:
        return [f"G0 assurance JSON contains duplicate key {error.args[0]!r}"]
    except NonFiniteJSONNumberError as error:
        return [f"G0 assurance JSON contains non-finite number {error.args[0]!r}"]
    except G0JSONNumberError as error:
        return [
            "G0 assurance JSON contains an integer exceeding "
            f"{MAX_G0_JSON_INTEGER_DIGITS} digits: {error.args[0]!r}"
        ]
    except json.JSONDecodeError as error:
        return [f"G0 assurance JSON is invalid: {error.msg}"]

    assurance = exact_keys(
        assurance,
        {
            "documentType",
            "schemaVersion",
            "assuranceId",
            "recordedDate",
            "status",
            "baseline",
            "sourceRecords",
            "protocolInventory",
            "dataFlowInventory",
            "threatModelRefresh",
            "riskRegister",
            "g0ClosureContract",
            "observabilitySchema",
            "releaseChecklist",
            "incidentRunbook",
            "rollbackRunbook",
            "approvals",
            "authority",
            "acceptance",
        },
        "G0 assurance",
        failures,
    )
    require_equal(
        assurance.get("documentType"),
        "aetherlink.v1-g0-assurance",
        "assurance.documentType",
        failures,
    )
    require_equal(assurance.get("schemaVersion"), "1.0", "assurance.schemaVersion", failures)
    require_equal(
        assurance.get("assuranceId"),
        "aetherlink_v1_g0_assurance_v1",
        "assurance.assuranceId",
        failures,
    )
    require_equal(assurance.get("recordedDate"), "2026-07-20", "assurance.recordedDate", failures)
    require_equal(assurance.get("status"), "blocked_before_g1a", "assurance.status", failures)
    require_equal(
        canonical_json_sha256(assurance),
        EXPECTED_ASSURANCE_CANONICAL_SHA256,
        "G0 assurance canonical sha256",
        failures,
    )

    baseline = exact_keys(
        assurance.get("baseline"),
        {
            "decisionId",
            "decisionCanonicalSha256",
            "decisionByteSha256",
            "implementationRevision",
            "branch",
            "evidenceBoundary",
        },
        "assurance.baseline",
        failures,
    )
    require_equal(
        baseline.get("decisionId"),
        "aetherlink_v1_g0_decision_v1",
        "assurance.baseline.decisionId",
        failures,
    )
    require_equal(
        baseline.get("decisionCanonicalSha256"),
        canonical_json_sha256(decision),
        "assurance.baseline.decisionCanonicalSha256",
        failures,
    )
    require_equal(
        baseline.get("decisionByteSha256"),
        EXPECTED_ASSURANCE_SOURCE_HASHES["docs/v1/g0/decision-v1.json"],
        "assurance.baseline.decisionByteSha256",
        failures,
    )
    require_equal(
        baseline.get("implementationRevision"),
        "d32c1846eead13ab1462619145fc4da1194cce7e",
        "assurance.baseline.implementationRevision",
        failures,
    )
    require_equal(baseline.get("branch"), "main", "assurance.baseline.branch", failures)
    require_equal(
        baseline.get("evidenceBoundary"),
        "static_inventory_only_no_new_device_network_socket_signing_or_release_execution",
        "assurance.baseline.evidenceBoundary",
        failures,
    )

    records = assurance.get("sourceRecords")
    if not isinstance(records, list):
        failures.append("assurance.sourceRecords must be a list")
    else:
        paths: list[object] = []
        declared_hashes: dict[object, object] = {}
        for index, record in enumerate(records):
            item = exact_keys(
                record,
                {"path", "sha256", "role"},
                f"assurance.sourceRecords[{index}]",
                failures,
            )
            path = item.get("path")
            paths.append(path)
            declared_hashes[path] = item.get("sha256")
            if not isinstance(item.get("role"), str) or not item.get("role"):
                failures.append(f"assurance.sourceRecords[{index}].role must be nonblank")
        require_equal(
            paths,
            list(EXPECTED_ASSURANCE_SOURCE_HASHES),
            "assurance source record order",
            failures,
        )
        require_equal(
            declared_hashes,
            EXPECTED_ASSURANCE_SOURCE_HASHES,
            "assurance source record hashes",
            failures,
        )
        if verify_files:
            for path, expected_hash in EXPECTED_ASSURANCE_SOURCE_HASHES.items():
                source_path = root / path
                try:
                    actual_hash = sha256(source_path)
                except OSError as error:
                    failures.append(f"cannot hash assurance source {path}: {error}")
                    continue
                require_equal(
                    actual_hash,
                    expected_hash,
                    f"assurance source hash {path}",
                    failures,
                )

    referenced_paths: set[str] = set()
    referenced_markdown_anchors: set[tuple[str, str]] = set()

    def collect_referenced_paths(value: object) -> None:
        if isinstance(value, dict):
            for child in value.values():
                collect_referenced_paths(child)
        elif isinstance(value, list):
            for child in value:
                collect_referenced_paths(child)
        elif isinstance(value, str) and value.startswith(("apps/", "docs/", "packages/")):
            path, separator, anchor = value.partition("#")
            referenced_paths.add(path)
            if separator and path.endswith(".md"):
                referenced_markdown_anchors.add((path, anchor))

    collect_referenced_paths(assurance)
    unpinned_paths = sorted(referenced_paths - set(EXPECTED_ASSURANCE_SOURCE_HASHES))
    if unpinned_paths:
        failures.append(f"assurance contains unpinned filesystem references: {unpinned_paths!r}")
    for path, anchor in sorted(referenced_markdown_anchors):
        try:
            document_markdown = (root / path).read_text(encoding="utf-8")
        except OSError as error:
            failures.append(f"cannot read assurance markdown reference {path}: {error}")
            continue
        anchors: set[str] = set()
        for line in document_markdown.splitlines():
            match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
            if match is None:
                continue
            heading = re.sub(r"<[^>]+>", "", match.group(1))
            slug = re.sub(r"[^\w\s-]", "", heading.lower())
            slug = re.sub(r"[\s-]+", "-", slug).strip("-")
            if slug:
                anchors.add(slug)
        if anchor not in anchors:
            failures.append(
                f"assurance markdown reference anchor does not exist: {path}#{anchor}"
            )

    protocol = exact_keys(
        assurance.get("protocolInventory"),
        {
            "activeSchemaId",
            "pairingQrSchemaId",
            "activeMessageTypes",
            "activeErrorCodes",
            "guardedNamespacePrefixes",
            "namespaceActiveExceptions",
            "selectedNotImplemented",
            "cryptoSuiteStatus",
            "routeAuthorization",
            "pairRecoveryContract",
            "units",
        },
        "assurance.protocolInventory",
        failures,
    )
    require_equal(
        protocol.get("activeSchemaId"),
        "https://aetherlink.dev/schema/protocol.v1.json",
        "protocolInventory.activeSchemaId",
        failures,
    )
    require_equal(
        protocol.get("pairingQrSchemaId"),
        "https://aetherlink.dev/schema/pairing-qr.v1.json",
        "protocolInventory.pairingQrSchemaId",
        failures,
    )
    require_equal(
        protocol.get("guardedNamespacePrefixes"),
        EXPECTED_GUARDED_NAMESPACE_PREFIXES,
        "protocolInventory.guardedNamespacePrefixes",
        failures,
    )
    require_equal(
        protocol.get("namespaceActiveExceptions"),
        EXPECTED_NAMESPACE_ACTIVE_EXCEPTIONS,
        "protocolInventory.namespaceActiveExceptions",
        failures,
    )
    require_equal(
        protocol.get("cryptoSuiteStatus"),
        "candidate_requires_g1_ratification",
        "protocolInventory.cryptoSuiteStatus",
        failures,
    )
    selected_not_implemented = require_string_list(
        protocol.get("selectedNotImplemented"),
        "protocolInventory.selectedNotImplemented",
        failures,
    )
    for required_selection in (
        "authenticated_encrypted_ice",
        "bounded_turn",
        "sealed_relay_only_emergency_fallback",
        "transport_neutral_endpoint_identity_session",
        "tls_1_3_signed_lease_capabilities",
        "monotonic_pair_epoch",
        "pair.status",
    ):
        if required_selection not in selected_not_implemented:
            failures.append(
                f"protocolInventory.selectedNotImplemented is missing {required_selection!r}"
            )

    try:
        schema = json.loads(
            (root / "packages/protocol-schema/protocol.schema.json").read_text(
                encoding="utf-8"
            )
        )
        expected_message_types = schema["properties"]["type"]["enum"]
        expected_error_codes = schema["$defs"]["errorPayload"]["properties"]["code"]["enum"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        failures.append(f"cannot inspect active protocol schema for assurance: {error}")
        expected_message_types = []
        expected_error_codes = []
    require_equal(
        protocol.get("activeMessageTypes"),
        expected_message_types,
        "protocolInventory.activeMessageTypes",
        failures,
    )
    require_equal(
        protocol.get("activeErrorCodes"),
        expected_error_codes,
        "protocolInventory.activeErrorCodes",
        failures,
    )
    if isinstance(expected_message_types, list):
        for prefix in EXPECTED_GUARDED_NAMESPACE_PREFIXES:
            active_for_prefix = sorted(
                message_type
                for message_type in expected_message_types
                if isinstance(message_type, str) and message_type.startswith(prefix)
            )
            require_equal(
                active_for_prefix,
                EXPECTED_NAMESPACE_ACTIVE_EXCEPTIONS.get(prefix, []),
                f"protocolInventory namespace policy {prefix}",
                failures,
            )

    route = exact_keys(
        protocol.get("routeAuthorization"),
        {
            "localDirectServiceCapabilityRequired",
            "serviceMediatedP2pCandidatePublishCapabilityRequired",
            "serviceMediatedP2pCandidateFetchCapabilityRequired",
            "turnSignedCapabilityRequired",
            "sealedRelaySignedCapabilityRequired",
            "capabilityFreeRemoteP2pAllowed",
            "crossKindDigestInterpretationAllowed",
        },
        "protocolInventory.routeAuthorization",
        failures,
    )
    expected_route = {
        "localDirectServiceCapabilityRequired": False,
        "serviceMediatedP2pCandidatePublishCapabilityRequired": True,
        "serviceMediatedP2pCandidateFetchCapabilityRequired": True,
        "turnSignedCapabilityRequired": True,
        "sealedRelaySignedCapabilityRequired": True,
        "capabilityFreeRemoteP2pAllowed": False,
        "crossKindDigestInterpretationAllowed": False,
    }
    require_equal(route, expected_route, "protocolInventory.routeAuthorization", failures)
    decision_security = decision.get("securitySelections", {})
    decision_route = (
        decision_security.get("routeAuthorization", {})
        if isinstance(decision_security, dict)
        else {}
    )
    if isinstance(decision_route, dict):
        for field, expected in expected_route.items():
            require_equal(
                route.get(field),
                decision_route.get(field),
                f"assurance route authorization parity {field}",
                failures,
            )

    pair_recovery = exact_keys(
        protocol.get("pairRecoveryContract"),
        {
            "bindingFields",
            "bindingTargets",
            "replacementRequiresFreshQrAndHigherEpoch",
            "replacementRotatesEndpointTrafficSecret",
            "replacementRotatesRouteTokenSeed",
            "offlineReactivationRequiresCurrentSignedReceipt",
            "pairStatusMayMutateState",
        },
        "protocolInventory.pairRecoveryContract",
        failures,
    )
    expected_pair_recovery = {
        "bindingFields": ["pair_id", "pair_epoch"],
        "bindingTargets": [
            "lease",
            "registration",
            "endpoint_transcript",
            "route_refresh",
            "application_authentication",
        ],
        "replacementRequiresFreshQrAndHigherEpoch": True,
        "replacementRotatesEndpointTrafficSecret": True,
        "replacementRotatesRouteTokenSeed": True,
        "offlineReactivationRequiresCurrentSignedReceipt": True,
        "pairStatusMayMutateState": False,
    }
    require_equal(
        pair_recovery,
        expected_pair_recovery,
        "protocolInventory.pairRecoveryContract",
        failures,
    )
    decision_recovery = (
        decision_security.get("pairRecovery", {})
        if isinstance(decision_security, dict)
        else {}
    )
    if isinstance(decision_recovery, dict):
        for field in (
            "bindingFields",
            "bindingTargets",
            "replacementRotatesEndpointTrafficSecret",
            "replacementRotatesRouteTokenSeed",
            "offlineReactivationRequiresCurrentSignedReceipt",
        ):
            require_equal(
                pair_recovery.get(field),
                decision_recovery.get(field),
                f"assurance pair recovery parity {field}",
                failures,
            )

    units = protocol.get("units")
    if not isinstance(units, list):
        failures.append("protocolInventory.units must be a list")
    else:
        unit_ids: list[object] = []
        for index, unit in enumerate(units):
            item = exact_keys(
                unit,
                {
                    "id",
                    "state",
                    "version",
                    "schemaRefs",
                    "swiftRefs",
                    "androidRefs",
                    "documentationRefs",
                    "ownerRole",
                    "acceptanceMethod",
                },
                f"protocolInventory.units[{index}]",
                failures,
            )
            unit_ids.append(item.get("id"))
            if item.get("state") not in {"active_current", "selected_not_implemented"}:
                failures.append(f"protocolInventory.units[{index}].state is invalid")
            for field in ("id", "state", "version", "ownerRole", "acceptanceMethod"):
                if not isinstance(item.get(field), str) or not item.get(field):
                    failures.append(f"protocolInventory.units[{index}].{field} must be nonblank")
            for field in ("schemaRefs", "swiftRefs", "androidRefs", "documentationRefs"):
                require_string_list(
                    item.get(field),
                    f"protocolInventory.units[{index}].{field}",
                    failures,
                    allow_empty=item.get("id") == "reserved_namespaces",
                )
        require_equal(unit_ids, EXPECTED_PROTOCOL_UNIT_IDS, "protocol inventory unit order", failures)
        if units:
            require_equal(
                units[-1].get("state") if isinstance(units[-1], dict) else None,
                "selected_not_implemented",
                "reserved namespace inventory state",
                failures,
            )

    flows = assurance.get("dataFlowInventory")
    required_user_loops = decision.get("productScope", {}).get("requiredUserLoop", [])
    if not isinstance(flows, list):
        failures.append("dataFlowInventory must be a list")
    else:
        flow_ids: list[object] = []
        mapped_user_loops: list[str] = []
        for index, flow in enumerate(flows):
            item = exact_keys(
                flow,
                {
                    "id",
                    "state",
                    "source",
                    "destination",
                    "transport",
                    "dataClasses",
                    "trustBoundaries",
                    "authorizationGate",
                    "persistentStores",
                    "serviceVisibleData",
                    "forbiddenData",
                    "retentionRule",
                    "failureMode",
                    "sourceRefs",
                    "ownerRole",
                    "acceptanceMethod",
                    "userLoopIds",
                },
                f"dataFlowInventory[{index}]",
                failures,
            )
            flow_ids.append(item.get("id"))
            if item.get("state") not in {
                "active_current",
                "active_current_and_selected_not_implemented_paths",
                "selected_not_implemented",
            }:
                failures.append(f"dataFlowInventory[{index}].state is invalid")
            for field in (
                "id",
                "state",
                "source",
                "destination",
                "transport",
                "authorizationGate",
                "retentionRule",
                "failureMode",
                "ownerRole",
                "acceptanceMethod",
            ):
                if not isinstance(item.get(field), str) or not item.get(field):
                    failures.append(f"dataFlowInventory[{index}].{field} must be nonblank")
            for field in (
                "dataClasses",
                "trustBoundaries",
                "persistentStores",
                "serviceVisibleData",
                "forbiddenData",
                "sourceRefs",
                "userLoopIds",
            ):
                values = require_string_list(
                    item.get(field),
                    f"dataFlowInventory[{index}].{field}",
                    failures,
                    allow_empty=field in {"persistentStores", "serviceVisibleData", "userLoopIds"},
                )
                if field == "userLoopIds":
                    mapped_user_loops.extend(values)
                if field == "sourceRefs" and item.get("id") == "authenticated_route_refresh":
                    for required_source in (
                        "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt",
                        "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt",
                    ):
                        if required_source not in values:
                            failures.append(
                                f"authenticated_route_refresh sourceRefs is missing {required_source}"
                            )
        require_equal(flow_ids, EXPECTED_DATA_FLOW_IDS, "data-flow inventory order", failures)
        flows_by_id = {
            flow.get("id"): flow
            for flow in flows
            if isinstance(flow, dict) and isinstance(flow.get("id"), str)
        }
        required_flow_values = {
            "endpoint_to_allocation_authority": {
                "source": ["paired_endpoint_requesting_production_allocation"],
                "destination": ["first_party_allocation_authority"],
                "dataClasses": ["allocation_credential", "route_token", "endpoint_identity_proof"],
                "sourceRefs": ["docs/security-hardening/production-relay-v1/proposals/authenticated-allocation-control-plane.md"],
                "forbiddenData": ["endpoint_traffic_secret", "endpoint_private_key"],
            },
            "endpoint_to_pair_state_authority": {
                "source": ["current_surviving_or_replacement_endpoint"],
                "destination": ["first_party_pair_state_authority"],
                "dataClasses": ["signed_revoke_replace_or_status_request", "fresh_qr_replacement_proof", "transition_id"],
                "sourceRefs": ["docs/security-hardening/production-relay-v1/proposals/pair-epoch-recovery.md"],
                "forbiddenData": ["endpoint_traffic_secret", "route_token_seed", "qr_pairing_secret"],
            },
            "android_release_build_to_play_install_update_and_forward_fix": {
                "dataClasses": ["application_namespace", "artifact_digest", "signing_certificate_identity", "provenance_attestation", "store_readback"],
                "trustBoundaries": ["release_ci_to_play_app_signing", "play_distribution", "android_package_installer_and_update_lineage"],
                "forbiddenData": ["release_private_key", "account_credential"],
                "sourceRefs": ["docs/v1/g0/decision-v1.json"],
            },
            "macos_release_build_to_notarized_dmg_install_update_and_rollback": {
                "dataClasses": ["bundle_identifier", "artifact_digest", "developer_id_identity", "notary_ticket", "staple_readback", "provenance_attestation"],
                "trustBoundaries": ["release_ci_to_developer_id_signing", "apple_notary_service", "gatekeeper_installer_and_update_lineage"],
                "forbiddenData": ["developer_id_private_key", "apple_account_credential"],
                "sourceRefs": ["docs/v1/g0/decision-v1.json"],
            },
        }
        for flow_id, field_requirements in required_flow_values.items():
            flow = flows_by_id.get(flow_id, {})
            for field, required_values in field_requirements.items():
                actual = flow.get(field)
                if field in {"source", "destination"}:
                    if actual != required_values[0]:
                        failures.append(f"{flow_id}.{field} is not the selected V1 authority boundary")
                elif not isinstance(actual, list) or any(value not in actual for value in required_values):
                    failures.append(f"{flow_id}.{field} is missing required V1 assurance values")
        require_equal(
            sorted(set(mapped_user_loops)),
            sorted(required_user_loops) if isinstance(required_user_loops, list) else [],
            "data-flow required user-loop coverage",
            failures,
        )

    threat = exact_keys(
        assurance.get("threatModelRefresh"),
        {
            "sourceThreatModelId",
            "inheritedThreatIds",
            "assets",
            "actors",
            "trustBoundaries",
            "newThreats",
            "failClosedInvariants",
            "residualRiskIds",
        },
        "threatModelRefresh",
        failures,
    )
    require_equal(
        threat.get("sourceThreatModelId"),
        "production_p2p_nat_v1_threat_model",
        "threatModelRefresh.sourceThreatModelId",
        failures,
    )
    require_equal(
        threat.get("inheritedThreatIds"),
        [f"T{number:03d}" for number in range(1, 17)],
        "threatModelRefresh.inheritedThreatIds",
        failures,
    )
    for field in ("assets", "actors", "trustBoundaries", "failClosedInvariants", "residualRiskIds"):
        require_string_list(threat.get(field), f"threatModelRefresh.{field}", failures)
    for field, required_values in {
        "assets": ["application_identity", "release_artifacts", "release_provenance", "distribution_accounts_and_signing_authorities", "update_lineage"],
        "actors": ["release_ci", "google_play_and_play_app_signing", "apple_developer_id_and_notary", "artifact_supply_chain_attacker"],
        "trustBoundaries": ["source_to_release_ci", "release_ci_to_signing_authority", "signed_artifact_to_store_notary_or_direct_distribution", "distribution_to_platform_installer_and_update_lineage"],
    }.items():
        actual = threat.get(field)
        if not isinstance(actual, list) or any(value not in actual for value in required_values):
            failures.append(f"threatModelRefresh.{field} is missing the V1 release supply-chain boundary")
    invariants = threat.get("failClosedInvariants")
    if isinstance(invariants, list):
        for required_invariant in (
            "every_lease_registration_endpoint_transcript_route_refresh_and_application_authentication_binds_pair_id_and_pair_epoch",
            "replacement_requires_fresh_qr_higher_pair_epoch_fresh_endpoint_traffic_secret_and_rotated_route_token_seed",
            "offline_reactivation_requires_a_current_signed_state_receipt",
            "android_install_update_and_forward_fix_accept_only_owned_namespace_play_lineage_and_verified_aab_provenance",
            "macos_install_update_and_rollback_accept_only_owned_bundle_id_developer_id_notarized_stapled_dmg_provenance",
            "release_private_keys_and_distribution_credentials_never_enter_artifacts_logs_or_assurance_records",
        ):
            if required_invariant not in invariants:
                failures.append(
                    f"threatModelRefresh.failClosedInvariants is missing {required_invariant!r}"
                )
    new_threats = threat.get("newThreats")
    if not isinstance(new_threats, list):
        failures.append("threatModelRefresh.newThreats must be a list")
    else:
        threat_ids: list[object] = []
        for index, new_threat in enumerate(new_threats):
            item = exact_keys(
                new_threat,
                {"threatId", "title", "control", "hardStop", "sourceRefs"},
                f"threatModelRefresh.newThreats[{index}]",
                failures,
            )
            threat_ids.append(item.get("threatId"))
            for field in ("threatId", "title", "control", "hardStop"):
                if not isinstance(item.get(field), str) or not item.get(field):
                    failures.append(f"threatModelRefresh.newThreats[{index}].{field} must be nonblank")
            if item.get("hardStop") not in EXPECTED_SECURITY_HARD_STOPS:
                failures.append(f"threatModelRefresh.newThreats[{index}].hardStop is not a closed zero gate")
            require_string_list(
                item.get("sourceRefs"),
                f"threatModelRefresh.newThreats[{index}].sourceRefs",
                failures,
            )
        require_equal(threat_ids, EXPECTED_NEW_THREAT_IDS, "new threat order", failures)

    decision_blockers = [
        item.get("id")
        for item in decision.get("blockers", [])
        if isinstance(item, dict)
    ]
    risks = assurance.get("riskRegister")
    if not isinstance(risks, list):
        failures.append("riskRegister must be a list")
    else:
        risk_ids: list[object] = []
        all_threat_ids = {
            *(f"T{number:03d}" for number in range(1, 27)),
        }
        for index, risk in enumerate(risks):
            item = exact_keys(
                risk,
                {
                    "riskId",
                    "sourceThreatIds",
                    "description",
                    "affectedAssets",
                    "likelihood",
                    "impact",
                    "treatment",
                    "residualRisk",
                    "ownerRole",
                    "acceptanceStatus",
                    "requiredEvidence",
                    "releaseBlocking",
                    "blockerIds",
                },
                f"riskRegister[{index}]",
                failures,
            )
            risk_ids.append(item.get("riskId"))
            for field in (
                "riskId",
                "description",
                "likelihood",
                "impact",
                "treatment",
                "residualRisk",
                "ownerRole",
                "acceptanceStatus",
            ):
                if not isinstance(item.get(field), str) or not item.get(field):
                    failures.append(f"riskRegister[{index}].{field} must be nonblank")
            source_ids = require_string_list(
                item.get("sourceThreatIds"),
                f"riskRegister[{index}].sourceThreatIds",
                failures,
                allow_empty=True,
            )
            if any(source_id not in all_threat_ids for source_id in source_ids):
                failures.append(f"riskRegister[{index}].sourceThreatIds contains an unknown threat")
            require_string_list(item.get("affectedAssets"), f"riskRegister[{index}].affectedAssets", failures)
            risk_id = item.get("riskId")
            if isinstance(risk_id, str):
                require_equal(
                    item.get("requiredEvidence"),
                    EXPECTED_RISK_REQUIRED_EVIDENCE.get(risk_id),
                    f"riskRegister[{index}].requiredEvidence gate mapping",
                    failures,
                )
            blocker_ids = require_string_list(item.get("blockerIds"), f"riskRegister[{index}].blockerIds", failures)
            if any(blocker_id not in decision_blockers for blocker_id in blocker_ids):
                failures.append(f"riskRegister[{index}].blockerIds contains an unknown G0 blocker")
            require_equal(
                item.get("acceptanceStatus"),
                "blocked_unassigned",
                f"riskRegister[{index}].acceptanceStatus",
                failures,
            )
            require_equal(item.get("releaseBlocking"), True, f"riskRegister[{index}].releaseBlocking", failures)
        require_equal(risk_ids, EXPECTED_RISK_IDS, "risk register order", failures)
        risks_by_id = {
            risk.get("riskId"): risk
            for risk in risks
            if isinstance(risk, dict) and isinstance(risk.get("riskId"), str)
        }
        require_equal(
            risks_by_id.get("R002_production_namespace_signing_and_distribution_custody", {}).get("sourceThreatIds"),
            ["T024", "T025", "T026"],
            "R002 release supply-chain threat linkage",
            failures,
        )
        r010_threats = risks_by_id.get("R010_rollback_monotonicity", {}).get("sourceThreatIds")
        if not isinstance(r010_threats, list) or "T026" not in r010_threats:
            failures.append("R010 rollback risk is missing release-provenance threat T026")

    closure = assurance.get("g0ClosureContract")
    require_equal(
        closure,
        EXPECTED_G0_CLOSURE_CONTRACT,
        "g0ClosureContract",
        failures,
    )
    closure_requirements = (
        closure.get("blockerRequirements", [])
        if isinstance(closure, dict)
        else []
    )
    closure_evidence_kinds: set[str] = set()
    if isinstance(closure_requirements, list):
        closure_blocker_ids = [
            item.get("blockerId")
            for item in closure_requirements
            if isinstance(item, dict)
        ]
        closure_check_ids: set[str] = set()
        closure_owner_roles: set[str] = set()
        for index, item in enumerate(closure_requirements):
            if not isinstance(item, dict):
                continue
            closure_check_ids.update(
                require_string_list(
                    item.get("requiredCheckIds"),
                    f"g0ClosureContract.blockerRequirements[{index}].requiredCheckIds",
                    failures,
                )
            )
            closure_owner_roles.update(
                require_string_list(
                    item.get("requiredOwnerRoles"),
                    f"g0ClosureContract.blockerRequirements[{index}].requiredOwnerRoles",
                    failures,
                )
            )
            closure_evidence_kinds.update(
                require_string_list(
                    item.get("requiredEvidenceKinds"),
                    f"g0ClosureContract.blockerRequirements[{index}].requiredEvidenceKinds",
                    failures,
                )
            )
        require_equal(
            closure_blocker_ids,
            decision_blockers,
            "g0ClosureContract blocker coverage",
            failures,
        )
        require_equal(
            closure_check_ids,
            set(EXPECTED_G0_CHECK_IDS),
            "g0ClosureContract check coverage",
            failures,
        )
        require_equal(
            closure_owner_roles,
            set(EXPECTED_APPROVAL_ROLES),
            "g0ClosureContract approval-role coverage",
            failures,
        )
        quality_requirement = next(
            (
                item
                for item in closure_requirements
                if isinstance(item, dict)
                and item.get("blockerId") == "quality_measurement_owners"
            ),
            {},
        )
        quality_gates = decision.get("qualityGates")
        measurement_contracts = (
            quality_gates.get("measurementContracts", [])
            if isinstance(quality_gates, dict)
            else []
        )
        measurement_owner_roles = [
            item.get("ownerRole")
            for item in measurement_contracts
            if isinstance(item, dict)
        ]
        require_equal(
            quality_requirement.get("requiredOwnerRoles")
            if isinstance(quality_requirement, dict)
            else None,
            ["release_quality_owner", *measurement_owner_roles],
            "g0ClosureContract quality owner derivation",
            failures,
        )

    observability = exact_keys(
        assurance.get("observabilitySchema"),
        {
            "unknownFieldPolicy",
            "serviceEventAllowedFields",
            "releaseRecordAllowedFields",
            "fieldDefinitions",
            "supportedPlatformRows",
            "qualityTargetBindings",
            "metricEvidenceProfiles",
            "evidenceEnvelopeSchema",
            "variantOutcomeRules",
            "forbiddenDataClasses",
            "retentionClasses",
            "eventClasses",
            "releaseRecordClasses",
            "acceptanceMethods",
        },
        "observabilitySchema",
        failures,
    )
    require_equal(
        observability.get("unknownFieldPolicy"),
        "reject_event",
        "observabilitySchema.unknownFieldPolicy",
        failures,
    )
    service_fields = require_string_list(
        observability.get("serviceEventAllowedFields"),
        "observabilitySchema.serviceEventAllowedFields",
        failures,
    )
    require_equal(
        service_fields,
        EXPECTED_SERVICE_EVENT_FIELDS,
        "observabilitySchema.serviceEventAllowedFields",
        failures,
    )
    release_fields = require_string_list(
        observability.get("releaseRecordAllowedFields"),
        "observabilitySchema.releaseRecordAllowedFields",
        failures,
    )
    require_equal(
        release_fields,
        EXPECTED_RELEASE_RECORD_FIELDS,
        "observabilitySchema.releaseRecordAllowedFields",
        failures,
    )
    field_definitions = exact_keys(
        observability.get("fieldDefinitions"),
        set(EXPECTED_SERVICE_EVENT_FIELDS) | set(EXPECTED_RELEASE_RECORD_FIELDS),
        "observabilitySchema.fieldDefinitions",
        failures,
    )
    for field, expected_values in EXPECTED_OBSERVABILITY_ENUM_DOMAINS.items():
        expected_type = "integer" if field == "schema_version" else "string"
        definition = exact_keys(
            field_definitions.get(field),
            {"type", "enum"},
            f"observabilitySchema.fieldDefinitions.{field}",
            failures,
        )
        require_equal(definition.get("type"), expected_type, f"field definition type {field}", failures)
        require_equal(definition.get("enum"), expected_values, f"field definition enum {field}", failures)
    for field, (expected_type, minimum, maximum) in EXPECTED_OBSERVABILITY_RANGES.items():
        definition = exact_keys(
            field_definitions.get(field),
            {"type", "minimum", "maximum"},
            f"observabilitySchema.fieldDefinitions.{field}",
            failures,
        )
        require_equal(definition.get("type"), expected_type, f"field definition type {field}", failures)
        require_equal(definition.get("minimum"), minimum, f"field definition minimum {field}", failures)
        require_equal(definition.get("maximum"), maximum, f"field definition maximum {field}", failures)
    for field, (pattern, maximum_bytes) in EXPECTED_OBSERVABILITY_PATTERNS.items():
        definition = exact_keys(
            field_definitions.get(field),
            {"type", "pattern", "maximumBytes"},
            f"observabilitySchema.fieldDefinitions.{field}",
            failures,
        )
        require_equal(definition.get("type"), "string", f"field definition type {field}", failures)
        require_equal(definition.get("pattern"), pattern, f"field definition pattern {field}", failures)
        require_equal(definition.get("maximumBytes"), maximum_bytes, f"field definition maximumBytes {field}", failures)
        try:
            re.compile(pattern)
        except re.error as error:
            failures.append(f"field definition pattern {field} is invalid: {error}")
    region_definition = exact_keys(
        field_definitions.get("region"),
        {"type", "registry", "maximumBytes", "activationGate"},
        "observabilitySchema.fieldDefinitions.region",
        failures,
    )
    require_equal(region_definition.get("type"), "string", "field definition type region", failures)
    require_equal(
        region_definition.get("registry"),
        "approved_release_region_registry",
        "field definition registry region",
        failures,
    )
    require_equal(region_definition.get("maximumBytes"), 32, "field definition maximumBytes region", failures)
    require_equal(
        region_definition.get("activationGate"),
        "relay_region_capacity_and_cost_budget",
        "field definition activationGate region",
        failures,
    )
    expected_platform_rows = {
        "android": [
            *[
                f"android_emulator_api{api}_arm64"
                for api in decision.get("productScope", {}).get("platforms", {}).get("android", {}).get("emulatorApiMatrix", [])
            ],
            *[
                f"android_physical_{row}"
                for row in decision.get("productScope", {}).get("platforms", {}).get("android", {}).get("physicalMatrix", [])
            ],
        ],
        "macos": [
            f"macos{version}_arm64"
            for version in decision.get("productScope", {}).get("platforms", {}).get("macos", {}).get("releaseTestMajorVersions", [])
        ],
        "service": ["service_control_plane"],
    }
    require_equal(
        observability.get("supportedPlatformRows"),
        expected_platform_rows,
        "observabilitySchema.supportedPlatformRows",
        failures,
    )
    require_equal(
        field_definitions.get("device_class", {}).get("enum")
        if isinstance(field_definitions.get("device_class"), dict)
        else None,
        [row for rows in expected_platform_rows.values() for row in rows],
        "device_class enum supported-platform coverage",
        failures,
    )

    quality_bindings = observability.get("qualityTargetBindings")
    expected_metric_order = EXPECTED_OBSERVABILITY_ENUM_DOMAINS["metric_name"]
    if not isinstance(quality_bindings, list):
        failures.append("observabilitySchema.qualityTargetBindings must be a list")
    else:
        binding_metric_names: list[object] = []
        for index, binding in enumerate(quality_bindings):
            item = exact_keys(
                binding,
                {"metricName", "measurementContract", "decisionPath", "thresholdOperator", "thresholdValue"},
                f"observabilitySchema.qualityTargetBindings[{index}]",
                failures,
            )
            metric_name = item.get("metricName")
            binding_metric_names.append(metric_name)
            expected_contract = next(
                (
                    EXPECTED_RELEASE_RECORD_CONTRACTS[record_kind]
                    for record_kind, metrics in EXPECTED_RELEASE_RECORD_METRICS.items()
                    if metric_name in metrics
                ),
                None,
            )
            require_equal(
                item.get("measurementContract"),
                expected_contract,
                f"quality target contract {metric_name}",
                failures,
            )
            decision_path = item.get("decisionPath")
            expected_operator: object = None
            expected_value: object = None
            if decision_path == "qualityGates.incrementalMemoryP95MiB[platform]":
                values = decision.get("qualityGates", {}).get("incrementalMemoryP95MiB", {})
                if isinstance(values, dict) and values.get("androidMaximum") == values.get("macosMaximum"):
                    expected_value = values.get("androidMaximum")
                expected_operator = "maximum"
            elif decision_path == "qualityGates.capacityRule.twoTimesApprovedProjectedPeak":
                expected_value = 2.0
                expected_operator = "minimum"
            elif decision_path in {
                "qualityGates.capacityRule.withoutUnboundedGrowth",
                "qualityGates.capacityRule.withoutWeakerAdmission",
            }:
                expected_value = 0
                expected_operator = "equal"
            elif isinstance(decision_path, str) and decision_path.startswith("qualityGates."):
                current: object = decision
                for component in decision_path.split("."):
                    if isinstance(current, dict):
                        current = current.get(component)
                    else:
                        current = None
                        break
                expected_value = current
                if ".securityHardStops." in decision_path:
                    expected_operator = "equal"
                elif "minimum" in decision_path.lower():
                    expected_operator = "minimum"
                elif "maximum" in decision_path.lower() or metric_name in {
                    "authenticated_reconnect_p95_milliseconds",
                    "authenticated_handoff_p95_milliseconds",
                }:
                    expected_operator = "maximum"
            if not isinstance(expected_value, (int, float)) or isinstance(expected_value, bool):
                failures.append(f"quality target {metric_name} has no numeric decision target")
            require_equal(
                item.get("thresholdOperator"),
                expected_operator,
                f"quality target threshold operator {metric_name}",
                failures,
            )
            require_equal(
                item.get("thresholdValue"),
                expected_value,
                f"quality target threshold value {metric_name}",
                failures,
            )
        require_equal(
            binding_metric_names,
            expected_metric_order,
            "quality target binding metric order",
            failures,
        )
    evidence_profiles = observability.get("metricEvidenceProfiles")
    allowed_coverage_rules = {
        "once_per_campaign",
        "every_network_cell_provider",
        "every_required_variant_cell_provider",
        "every_p2p_required_cell_provider",
        "every_p2p_attempt_cell_provider",
        "handoff_cell_provider",
        "every_app_platform_row",
        "every_android_platform_row",
        "every_service_region",
        "every_app_and_service_platform",
    }
    if not isinstance(evidence_profiles, list):
        failures.append("observabilitySchema.metricEvidenceProfiles must be a list")
    else:
        profiled_metrics: list[str] = []
        profile_ids: list[object] = []
        for index, profile in enumerate(evidence_profiles):
            item = exact_keys(
                profile,
                {
                    "profileId",
                    "metricNames",
                    "requiredFields",
                    "minimumSampleCount",
                    "applicablePlatforms",
                    "campaignCoverage",
                },
                f"observabilitySchema.metricEvidenceProfiles[{index}]",
                failures,
            )
            profile_ids.append(item.get("profileId"))
            metrics = require_string_list(
                item.get("metricNames"),
                f"observabilitySchema.metricEvidenceProfiles[{index}].metricNames",
                failures,
            )
            profiled_metrics.extend(metrics)
            required_fields = require_string_list(
                item.get("requiredFields"),
                f"observabilitySchema.metricEvidenceProfiles[{index}].requiredFields",
                failures,
                allow_empty=True,
            )
            if any(field not in release_fields for field in required_fields):
                failures.append(
                    f"observabilitySchema.metricEvidenceProfiles[{index}] requires a non-release field"
                )
            minimum_sample_count = item.get("minimumSampleCount")
            if (
                not isinstance(minimum_sample_count, int)
                or isinstance(minimum_sample_count, bool)
                or minimum_sample_count < 1
            ):
                failures.append(
                    f"observabilitySchema.metricEvidenceProfiles[{index}].minimumSampleCount must be positive"
                )
            platforms = require_string_list(
                item.get("applicablePlatforms"),
                f"observabilitySchema.metricEvidenceProfiles[{index}].applicablePlatforms",
                failures,
            )
            if any(platform not in expected_platform_rows for platform in platforms):
                failures.append(
                    f"observabilitySchema.metricEvidenceProfiles[{index}] has an unsupported platform"
                )
            if item.get("campaignCoverage") not in allowed_coverage_rules:
                failures.append(
                    f"observabilitySchema.metricEvidenceProfiles[{index}].campaignCoverage is invalid"
                )
        if len(profile_ids) != len(set(profile_ids)):
            failures.append("observabilitySchema.metricEvidenceProfiles has duplicate profileId values")
        require_equal(
            profiled_metrics,
            expected_metric_order,
            "metric evidence profile coverage",
            failures,
        )
    require_equal(
        observability.get("evidenceEnvelopeSchema"),
        {
            "documentType": "aetherlink.v1-release-metric-evidence",
            "schemaVersion": 1,
            "evidenceKind": "signed_rc_metric_samples",
            "signatureAlgorithm": "ed25519",
            "signatureEncoding": "base64url_no_padding_64_bytes",
            "signatureCanonicalityRule": "strict_decode_exactly_64_bytes_reencode_without_padding_must_equal_input",
            "signerIdPattern": "^release-evidence-[a-z0-9_-]{1,64}$",
            "signerIdRegistryRule": "exact_case_sensitive_registry_key_match_after_pattern_validation",
            "signerRegistry": "approved_release_evidence_signer_registry",
            "activationGate": "quality_measurement_owners",
            "signatureCanonicalization": {
                "profile": "aetherlink-release-evidence-canonical-json-v1",
                "characterEncoding": "utf-8",
                "signatureInput": "payload_object_only",
                "objectKeyOrder": "ascending_unicode_scalar_value",
                "whitespace": "none",
                "stringEscaping": "json_minimal_control_escapes_forward_slash_unescaped_non_ascii_utf8",
                "numberGrammar": "nonnegative_base10_no_leading_zero_no_exponent_max_16_integer_digits_max_6_fractional_digits_canonical_trailing_zeros_removed_negative_zero_rejected",
                "literalEncoding": "lowercase_true_false_null",
            },
            "resourceBounds": {
                "maximumEvidenceBytes": MAX_RELEASE_EVIDENCE_BYTES,
                "maximumSampleCount": MAX_RELEASE_EVIDENCE_SAMPLES,
                "maximumIntegerDigits": MAX_RELEASE_EVIDENCE_INTEGER_DIGITS,
                "maximumFractionalDigits": MAX_RELEASE_EVIDENCE_FRACTIONAL_DIGITS,
            },
            "canonicalizationTestVector": {
                "inputJson": '{"z":[2.0,0.001,null,"é"],"a":"line\\nslash/"}',
                "canonicalUtf8": '{"a":"line\\nslash/","z":[2,0.001,null,"é"]}',
                "sha256": "0a5db88c2939cb0b17f82c252171f5793b8d6bf1f08c154e5f28bd8be3a76b79",
            },
            "envelopeExactFields": ["payload", "signer_id", "signature_algorithm", "signature"],
            "payloadExactFields": [
                "schema_version",
                "evidence_kind",
                "campaign_id",
                "app_build",
                "app_version",
                "record_kind",
                "measurement_contract",
                "metric_name",
                "threshold_operator",
                "threshold_value",
                "platform",
                "device_class",
                "context",
                "samples",
                "variant_observations",
            ],
            "contextExactFields": [
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
            ],
            "variantObservationExactFields": EXPECTED_VARIANT_OBSERVATION_FIELDS,
            "variantObservationIndexing": {
                "base": 1,
                "arrayOrder": "attempt_index_strictly_increases_by_one",
                "coverage": "exactly_1_through_sample_count",
            },
            "variantObservationTiming": {
                "type": "json_integer",
                "unit": "milliseconds_from_variant_attempt_start",
                "minimumInclusive": 0,
                "maximumInclusive": 120000,
                "conditionOrder": "condition_activated_before_condition_result",
                "recoveryOrder": "condition_result_before_service_restored_before_authenticated_recovery",
            },
            "variantAggregateRule": "one_homogeneous_outcome_route_cohort_per_record_all_observation_direct_fallback_and_aggregate_route_source_values_equal_record_fields_mixed_valid_combinations_require_separate_records",
            "variantObservationRule": "one_signed_exact_observation_per_sample_one_based_index_and_bounded_ordered_offsets_nullable_nonrecovery_fields_all_downgrade_and_post_consent_counts_zero_homogeneous_record_aggregate",
            "sampleRule": "bounded_finite_nonnegative_canonical_numeric_array_length_equals_sample_count_metric_recomputed_from_samples",
            "unknownFieldPolicy": "reject_envelope",
        },
        "observabilitySchema.evidenceEnvelopeSchema",
        failures,
    )
    require_equal(
        observability.get("variantOutcomeRules"),
        EXPECTED_VARIANT_OUTCOME_RULES,
        "observabilitySchema.variantOutcomeRules",
        failures,
    )
    canonicalization_vector = observability.get("evidenceEnvelopeSchema", {}).get(
        "canonicalizationTestVector"
    ) if isinstance(observability.get("evidenceEnvelopeSchema"), dict) else None
    if isinstance(canonicalization_vector, dict):
        try:
            vector_value = json.loads(
                canonicalization_vector.get("inputJson", ""),
                object_pairs_hook=reject_duplicate_keys,
                parse_constant=reject_non_finite,
                parse_int=parse_release_evidence_integer,
                parse_float=parse_release_evidence_decimal,
            )
            vector_bytes = canonical_release_evidence_json(vector_value)
        except (
            json.JSONDecodeError,
            DuplicateJSONKeyError,
            NonFiniteJSONNumberError,
            ReleaseEvidenceNumberError,
            TypeError,
            ValueError,
        ) as error:
            failures.append(f"release evidence canonicalization vector is invalid: {error}")
        else:
            require_equal(
                vector_bytes.decode("utf-8"),
                canonicalization_vector.get("canonicalUtf8"),
                "release evidence canonicalization vector bytes",
                failures,
            )
            require_equal(
                hashlib.sha256(vector_bytes).hexdigest(),
                canonicalization_vector.get("sha256"),
                "release evidence canonicalization vector sha256",
                failures,
            )
    forbidden_classes = require_string_list(
        observability.get("forbiddenDataClasses"),
        "observabilitySchema.forbiddenDataClasses",
        failures,
    )
    for required_forbidden in (
        "prompt",
        "response",
        "memory",
        "provider_or_backend_credential",
        "raw_candidate_ip_hostname_or_port",
        "stable_pair_session_or_request_identifier",
    ):
        if required_forbidden not in forbidden_classes:
            failures.append(f"observability forbidden data is missing {required_forbidden!r}")
    require_equal(
        observability.get("retentionClasses"),
        {
            "aggregate_operational_metrics": "maximum_30_days",
            "source_free_security_event": "maximum_7_days",
            "sanitized_incident_evidence": "maximum_90_days",
            "content_free_release_record": "maximum_365_days",
            "live_authorization_state": "expiry_plus_30_seconds",
        },
        "observabilitySchema.retentionClasses",
        failures,
    )
    require_string_list(
        observability.get("acceptanceMethods"),
        "observabilitySchema.acceptanceMethods",
        failures,
    )
    events = observability.get("eventClasses")
    if not isinstance(events, list):
        failures.append("observabilitySchema.eventClasses must be a list")
    else:
        event_kinds: list[object] = []
        for index, event in enumerate(events):
            item = exact_keys(
                event,
                {
                    "eventKind",
                    "requiredFields",
                    "allowedFields",
                    "retentionClass",
                    "deletionTrigger",
                    "maximumFields",
                    "maximumStringBytes",
                    "ownerRole",
                },
                f"observabilitySchema.eventClasses[{index}]",
                failures,
            )
            event_kinds.append(item.get("eventKind"))
            required_fields = require_string_list(
                item.get("requiredFields"),
                f"observabilitySchema.eventClasses[{index}].requiredFields",
                failures,
            )
            allowed_fields = require_string_list(
                item.get("allowedFields"),
                f"observabilitySchema.eventClasses[{index}].allowedFields",
                failures,
            )
            if any(field not in service_fields for field in allowed_fields):
                failures.append(f"observabilitySchema.eventClasses[{index}] uses a non-allowlisted field")
            if any(field not in allowed_fields for field in required_fields):
                failures.append(f"observabilitySchema.eventClasses[{index}] requires a non-allowed field")
            for required_base_field in ("schema_version", "event_kind", "reason_code", "outcome"):
                if required_base_field not in required_fields:
                    failures.append(
                        f"observabilitySchema.eventClasses[{index}] is missing required base field {required_base_field}"
                    )
            require_equal(
                item.get("maximumFields"),
                len(allowed_fields),
                f"observabilitySchema.eventClasses[{index}].maximumFields",
                failures,
            )
            require_equal(
                item.get("maximumStringBytes"),
                128,
                f"observabilitySchema.eventClasses[{index}].maximumStringBytes",
                failures,
            )
            if item.get("retentionClass") not in {
                "aggregate_operational_metrics",
                "source_free_security_event",
                "sanitized_incident_evidence",
                "content_free_release_record",
            }:
                failures.append(f"observabilitySchema.eventClasses[{index}].retentionClass is invalid")
        require_equal(event_kinds, EXPECTED_OBSERVABILITY_EVENT_KINDS, "observability event order", failures)

    release_records = observability.get("releaseRecordClasses")
    if not isinstance(release_records, list):
        failures.append("observabilitySchema.releaseRecordClasses must be a list")
    else:
        record_kinds: list[object] = []
        for index, record in enumerate(release_records):
            item = exact_keys(
                record,
                {
                    "recordKind",
                    "measurementContract",
                    "permittedMetricNames",
                    "requiredFields",
                    "allowedFields",
                    "retentionClass",
                    "deletionTrigger",
                    "maximumFields",
                    "ownerRole",
                },
                f"observabilitySchema.releaseRecordClasses[{index}]",
                failures,
            )
            record_kinds.append(item.get("recordKind"))
            record_kind = item.get("recordKind")
            require_equal(
                item.get("measurementContract"),
                EXPECTED_RELEASE_RECORD_CONTRACTS.get(record_kind),
                f"observabilitySchema.releaseRecordClasses[{index}].measurementContract",
                failures,
            )
            permitted_metrics = require_string_list(
                item.get("permittedMetricNames"),
                f"observabilitySchema.releaseRecordClasses[{index}].permittedMetricNames",
                failures,
            )
            require_equal(
                permitted_metrics,
                EXPECTED_RELEASE_RECORD_METRICS.get(record_kind, []),
                f"observabilitySchema.releaseRecordClasses[{index}].permittedMetricNames",
                failures,
            )
            required_fields = require_string_list(
                item.get("requiredFields"),
                f"observabilitySchema.releaseRecordClasses[{index}].requiredFields",
                failures,
            )
            allowed_fields = require_string_list(
                item.get("allowedFields"),
                f"observabilitySchema.releaseRecordClasses[{index}].allowedFields",
                failures,
            )
            if any(field not in release_fields for field in allowed_fields):
                failures.append(
                    f"observabilitySchema.releaseRecordClasses[{index}] uses a non-release-allowlisted field"
                )
            if any(field not in allowed_fields for field in required_fields):
                failures.append(
                    f"observabilitySchema.releaseRecordClasses[{index}] requires a non-allowed field"
                )
            for required_base_field in (
                "record_kind",
                "campaign_id",
                "evidence_sha256",
                "evidence_ref",
                "app_build",
                "app_version",
                "platform",
                "device_class",
                "measurement_contract",
                "metric_name",
                "metric_value",
                "threshold_operator",
                "threshold_value",
                "sample_count",
                "gate_result",
            ):
                if required_base_field not in required_fields:
                    failures.append(
                        f"observabilitySchema.releaseRecordClasses[{index}] is missing required base field {required_base_field}"
                    )
            require_equal(
                item.get("maximumFields"),
                len(allowed_fields),
                f"observabilitySchema.releaseRecordClasses[{index}].maximumFields",
                failures,
            )
            require_equal(
                item.get("retentionClass"),
                "content_free_release_record",
                f"observabilitySchema.releaseRecordClasses[{index}].retentionClass",
                failures,
            )
        require_equal(
            record_kinds,
            EXPECTED_RELEASE_RECORD_KINDS,
            "observability release record order",
            failures,
        )
        flattened_metrics = [
            metric
            for record in release_records
            if isinstance(record, dict)
            for metric in record.get("permittedMetricNames", [])
            if isinstance(metric, str)
        ]
        require_equal(
            flattened_metrics,
            EXPECTED_OBSERVABILITY_ENUM_DOMAINS["metric_name"],
            "release record metric coverage",
            failures,
        )
        profiles_by_metric = {
            metric: profile
            for profile in evidence_profiles
            if isinstance(profile, dict)
            for metric in profile.get("metricNames", [])
            if isinstance(metric, str)
        } if isinstance(evidence_profiles, list) else {}
        for index, record in enumerate(release_records):
            if not isinstance(record, dict):
                continue
            allowed = record.get("allowedFields", [])
            for metric in record.get("permittedMetricNames", []):
                profile = profiles_by_metric.get(metric, {})
                required = profile.get("requiredFields", []) if isinstance(profile, dict) else []
                if not isinstance(allowed, list) or any(field not in allowed for field in required):
                    failures.append(
                        f"observabilitySchema.releaseRecordClasses[{index}] cannot carry required evidence for {metric}"
                    )

    checklist = exact_keys(
        assurance.get("releaseChecklist"),
        {"status", "evidenceClassSeparation", "g0Exit", "futureReleasePromotion"},
        "releaseChecklist",
        failures,
    )
    require_equal(checklist.get("status"), "blocked", "releaseChecklist.status", failures)
    require_equal(
        checklist.get("evidenceClassSeparation"),
        [
            "static_no_device",
            "physical_device",
            "same_wifi_debug",
            "controlled_external_network",
            "signed_release_candidate",
            "production_rollout",
        ],
        "releaseChecklist.evidenceClassSeparation",
        failures,
    )

    def validate_checks(
        value: object,
        expected_ids: list[str],
        label: str,
        expected_statuses: list[str],
        expected_evidence: dict[str, list[str]] | None = None,
    ) -> None:
        if not isinstance(value, list):
            failures.append(f"{label} must be a list")
            return
        ids: list[object] = []
        statuses: list[object] = []
        for index, check in enumerate(value):
            item = exact_keys(
                check,
                {
                    "checkId",
                    "phase",
                    "ownerRole",
                    "status",
                    "requiredEvidence",
                    "evidenceRefs",
                    "blocksPromotion",
                    "waiverRef",
                },
                f"{label}[{index}]",
                failures,
            )
            ids.append(item.get("checkId"))
            statuses.append(item.get("status"))
            required_evidence = require_string_list(
                item.get("requiredEvidence"),
                f"{label}[{index}].requiredEvidence",
                failures,
            )
            check_id = item.get("checkId")
            if expected_evidence is not None and isinstance(check_id, str):
                require_equal(
                    required_evidence,
                    expected_evidence.get(check_id),
                    f"{label}[{index}].requiredEvidence",
                    failures,
                )
            evidence = require_string_list(
                item.get("evidenceRefs"),
                f"{label}[{index}].evidenceRefs",
                failures,
                allow_empty=True,
            )
            status = item.get("status")
            if status not in {"blocked", "not_run", "passed", "waived"}:
                failures.append(f"{label}[{index}].status is invalid")
            if status == "passed" and not evidence:
                failures.append(f"{label}[{index}] passed without immutable evidence")
            if status == "waived" and not item.get("waiverRef"):
                failures.append(f"{label}[{index}] waived without a versioned waiver")
            require_equal(item.get("blocksPromotion"), True, f"{label}[{index}].blocksPromotion", failures)
        require_equal(ids, expected_ids, f"{label} order", failures)
        require_equal(statuses, expected_statuses, f"{label} status", failures)

    validate_checks(
        checklist.get("g0Exit"),
        EXPECTED_G0_CHECK_IDS,
        "releaseChecklist.g0Exit",
        ["blocked", "not_run", "not_run", "blocked", "blocked", "blocked", "blocked", "blocked", "blocked"],
        EXPECTED_G0_CHECK_EVIDENCE,
    )
    validate_checks(
        checklist.get("futureReleasePromotion"),
        EXPECTED_FUTURE_CHECK_IDS,
        "releaseChecklist.futureReleasePromotion",
        ["not_run"] * len(EXPECTED_FUTURE_CHECK_IDS),
    )
    checklist_evidence_kinds = {
        evidence_kind
        for values in EXPECTED_G0_CHECK_EVIDENCE.values()
        for evidence_kind in values
    }
    require_equal(
        closure_evidence_kinds,
        checklist_evidence_kinds,
        "g0ClosureContract evidence-kind coverage",
        failures,
    )

    incidents = assurance.get("incidentRunbook")
    if not isinstance(incidents, list):
        failures.append("incidentRunbook must be a list")
    else:
        incident_ids: list[object] = []
        for index, incident in enumerate(incidents):
            item = exact_keys(
                incident,
                {
                    "incidentClass",
                    "triggers",
                    "severity",
                    "incidentCommanderRole",
                    "containment",
                    "failClosedAction",
                    "credentialOrStateRotation",
                    "evidencePreservation",
                    "recoveryCriteria",
                    "communicationOwnerRole",
                    "drillEvidence",
                },
                f"incidentRunbook[{index}]",
                failures,
            )
            incident_ids.append(item.get("incidentClass"))
            for field in (
                "incidentClass",
                "severity",
                "incidentCommanderRole",
                "failClosedAction",
                "evidencePreservation",
                "communicationOwnerRole",
            ):
                if not isinstance(item.get(field), str) or not item.get(field):
                    failures.append(f"incidentRunbook[{index}].{field} must be nonblank")
            for field in ("triggers", "containment", "credentialOrStateRotation", "recoveryCriteria", "drillEvidence"):
                require_string_list(
                    item.get(field),
                    f"incidentRunbook[{index}].{field}",
                    failures,
                    allow_empty=field in {"credentialOrStateRotation", "drillEvidence"},
                )
            require_equal(item.get("drillEvidence"), [], f"incidentRunbook[{index}].drillEvidence", failures)
        require_equal(incident_ids, EXPECTED_INCIDENT_CLASSES, "incident runbook order", failures)
        incidents_by_class = {
            incident.get("incidentClass"): incident
            for incident in incidents
            if isinstance(incident, dict) and isinstance(incident.get("incidentClass"), str)
        }
        for incident_class, required_rotations in {
            "endpoint_loss_or_key_compromise": [
                "fresh_qr",
                "higher_pair_epoch",
                "fresh_endpoint_traffic_secret",
                "rotated_route_token_seed",
            ],
            "pair_epoch_or_revocation_divergence": [
                "fresh_qr_and_higher_epoch_when_replacement_is_required",
                "fresh_endpoint_traffic_secret",
                "rotated_route_token_seed",
            ],
        }.items():
            rotations = incidents_by_class.get(incident_class, {}).get("credentialOrStateRotation")
            if not isinstance(rotations, list) or any(value not in rotations for value in required_rotations):
                failures.append(
                    f"incidentRunbook {incident_class} is missing mandatory pair-recovery secret rotation"
                )

    rollback = exact_keys(
        assurance.get("rollbackRunbook"),
        {
            "rollbackSuccessMinimum",
            "revocationClosureAbsoluteMaximumMilliseconds",
            "hardStops",
            "monotonicState",
            "universalRules",
            "android",
            "macos",
            "postRecoveryChecks",
        },
        "rollbackRunbook",
        failures,
    )
    require_equal(rollback.get("rollbackSuccessMinimum"), 1.0, "rollbackRunbook.rollbackSuccessMinimum", failures)
    require_equal(
        rollback.get("revocationClosureAbsoluteMaximumMilliseconds"),
        30000,
        "rollbackRunbook.revocationClosureAbsoluteMaximumMilliseconds",
        failures,
    )
    require_equal(rollback.get("hardStops"), EXPECTED_SECURITY_HARD_STOPS, "rollbackRunbook.hardStops", failures)
    require_equal(rollback.get("monotonicState"), EXPECTED_MONOTONIC_STATE, "rollbackRunbook.monotonicState", failures)
    require_string_list(rollback.get("universalRules"), "rollbackRunbook.universalRules", failures)
    require_string_list(rollback.get("postRecoveryChecks"), "rollbackRunbook.postRecoveryChecks", failures)
    android_rollback = exact_keys(
        rollback.get("android"),
        {"strategy", "artifactRule", "forbidden"},
        "rollbackRunbook.android",
        failures,
    )
    macos_rollback = exact_keys(
        rollback.get("macos"),
        {"strategy", "artifactRule", "forbidden"},
        "rollbackRunbook.macos",
        failures,
    )
    require_equal(android_rollback.get("strategy"), "halt_rollout_then_forward_fix", "rollbackRunbook.android.strategy", failures)
    require_equal(macos_rollback.get("strategy"), "restore_previous_approved_signed_artifact_when_compatible", "rollbackRunbook.macos.strategy", failures)

    approvals = assurance.get("approvals")
    if not isinstance(approvals, list):
        failures.append("approvals must be a list")
    else:
        approval_roles: list[object] = []
        for index, approval in enumerate(approvals):
            item = exact_keys(
                approval,
                {
                    "role",
                    "ownerIdentityRef",
                    "status",
                    "acceptedRevision",
                    "acceptedPublicationCommit",
                    "acceptedBlockerIds",
                    "acceptedAt",
                    "acceptanceEvidenceRefs",
                },
                f"approvals[{index}]",
                failures,
            )
            approval_roles.append(item.get("role"))
            require_equal(item.get("ownerIdentityRef"), None, f"approvals[{index}].ownerIdentityRef", failures)
            require_equal(item.get("status"), "blocked_unassigned", f"approvals[{index}].status", failures)
            require_equal(item.get("acceptedRevision"), None, f"approvals[{index}].acceptedRevision", failures)
            require_equal(
                item.get("acceptedPublicationCommit"),
                None,
                f"approvals[{index}].acceptedPublicationCommit",
                failures,
            )
            require_equal(
                item.get("acceptedBlockerIds"),
                [],
                f"approvals[{index}].acceptedBlockerIds",
                failures,
            )
            require_equal(item.get("acceptedAt"), None, f"approvals[{index}].acceptedAt", failures)
            require_equal(item.get("acceptanceEvidenceRefs"), [], f"approvals[{index}].acceptanceEvidenceRefs", failures)
        require_equal(approval_roles, EXPECTED_APPROVAL_ROLES, "approval role order", failures)

    assurance_authority = exact_keys(
        assurance.get("authority"),
        {"g0DocumentationAndStaticValidationAllowed", *FALSE_AUTHORITIES},
        "assurance.authority",
        failures,
    )
    require_equal(assurance_authority, decision.get("authority"), "assurance authority parity", failures)
    require_equal(
        assurance_authority.get("g0DocumentationAndStaticValidationAllowed"),
        True,
        "assurance.authority.g0DocumentationAndStaticValidationAllowed",
        failures,
    )
    for field in FALSE_AUTHORITIES:
        require_equal(assurance_authority.get(field), False, f"assurance.authority.{field}", failures)

    acceptance = exact_keys(
        assurance.get("acceptance"),
        {
            "contradictions",
            "missingHardStops",
            "sourceHashesExpectedToPassStaticChecker",
            "protocolAndDataFlowInventoryCompleteForBaseline",
            "threatRiskObservabilityAndRunbookSectionsCompleteForBaseline",
            "fullNoDeviceAggregate",
            "androidReleaseCompilation",
            "macosReleaseCompilation",
            "allOwnersNamed",
            "allApprovalsAccepted",
            "remainingBlockerIds",
            "g0AssuranceBlockerClosed",
            "g0ExitComplete",
            "g1aMayStartNow",
        },
        "assurance.acceptance",
        failures,
    )
    require_equal(acceptance.get("contradictions"), [], "acceptance.contradictions", failures)
    require_equal(acceptance.get("missingHardStops"), [], "acceptance.missingHardStops", failures)
    require_equal(
        acceptance.get("sourceHashesExpectedToPassStaticChecker"),
        True,
        "acceptance.sourceHashesExpectedToPassStaticChecker",
        failures,
    )
    require_equal(
        acceptance.get("fullNoDeviceAggregate"),
        "not_run_requires_separate_socket_authority",
        "acceptance.fullNoDeviceAggregate",
        failures,
    )
    require_equal(acceptance.get("androidReleaseCompilation"), "not_run", "acceptance.androidReleaseCompilation", failures)
    require_equal(acceptance.get("macosReleaseCompilation"), "not_run", "acceptance.macosReleaseCompilation", failures)
    for field in (
        "allOwnersNamed",
        "allApprovalsAccepted",
        "g0AssuranceBlockerClosed",
        "g0ExitComplete",
        "g1aMayStartNow",
    ):
        require_equal(acceptance.get(field), False, f"acceptance.{field}", failures)
    require_equal(
        acceptance.get("remainingBlockerIds"),
        decision_blockers,
        "acceptance.remainingBlockerIds",
        failures,
    )

    quality = decision.get("qualityGates", {})
    if isinstance(quality, dict):
        require_equal(
            rollback.get("rollbackSuccessMinimum"),
            quality.get("rollbackSuccessMinimum"),
            "assurance rollback success parity",
            failures,
        )
        revocation = quality.get("revocationClosureMilliseconds", {})
        if isinstance(revocation, dict):
            require_equal(
                rollback.get("revocationClosureAbsoluteMaximumMilliseconds"),
                revocation.get("absoluteMaximum"),
                "assurance revocation absolute maximum parity",
                failures,
            )
        require_equal(
            rollback.get("hardStops"),
            quality.get("securityHardStops"),
            "assurance security hard-stop parity",
            failures,
        )

    if markdown is None:
        try:
            markdown = (root / "docs/v1/g0/assurance-v1.md").read_text(
                encoding="utf-8"
            )
        except OSError as error:
            failures.append(f"cannot read G0 assurance markdown: {error}")
            markdown = ""
    required_markdown = (
        "Assurance ID: aetherlink_v1_g0_assurance_v1",
        "Status: blocked_before_g1a",
        "does not authorize G1a implementation",
        "pins all 46 active message types and all 40 active error codes",
        "guards 35 prefixes",
        "Service-mediated P2P candidate publication requires",
        "absolute maximum",
        "30,000 milliseconds",
        "fresh endpoint traffic secret",
        "Sixteen flows cover",
        "Android never calls Ollama or LM Studio directly",
        "T017",
        "T023",
        "T026",
        "Unknown event kinds and unknown fields are rejected",
        "Every allowed field has a machine-enforced type",
        "Five separate release-record classes",
        "exact supported platform row",
        "content-addressed evidence bytes read back",
        "approved signer registry",
        "^release-evidence-[a-z0-9_-]{1,64}$",
        "Ed25519",
        "re-encode to the identical text",
        "nearest-rank p50/p95/p99",
        "self-reported scalar cannot replace",
        "canonicalization test vector",
        "independent of the ambient Decimal",
        "limited to 4 MiB and 100,000",
        "one signed raw observation per sample",
        "exactly one-based `attempt_index` 1 through",
        "0 through 120,000 inclusive",
        "one homogeneous outcome-and-route cohort",
        "bare `variant_outcome` string",
        "cannot satisfy campaign coverage merely by reporting 30 attempts",
        "campaign validator rejects",
        "rotated route-token seed",
        "full no-device aggregate needs separate",
        "rollbackSuccessMinimum is 1.0",
        "All ten G0 blockers remain listed",
        "G1a remains closed",
    )
    for snippet in required_markdown:
        if snippet not in markdown:
            failures.append(f"G0 assurance markdown is missing {snippet!r}")

    return failures


def apply_assurance_amendment_operations(
    parent: dict[str, object],
    operations: object,
    failures: list[str],
) -> dict[str, object]:
    if not isinstance(operations, list):
        failures.append("G0 assurance closure amendment operations must be a list")
        return copy.deepcopy(parent)
    effective = copy.deepcopy(parent)
    observed_operations: list[tuple[object, object]] = []
    for index, raw_operation in enumerate(operations):
        operation = exact_keys(
            raw_operation,
            {"op", "path", "value"},
            f"G0 assurance closure amendment operations[{index}]",
            failures,
        )
        operation_kind = operation.get("op")
        path = operation.get("path")
        observed_operations.append((operation_kind, path))
        if operation_kind not in {"add", "replace"}:
            failures.append(
                f"G0 assurance closure amendment operations[{index}].op is invalid"
            )
            continue
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or path == "/"
            or "~" in path
        ):
            failures.append(
                f"G0 assurance closure amendment operations[{index}].path is invalid"
            )
            continue
        parts = path[1:].split("/")
        if any(not part or part.isdigit() for part in parts):
            failures.append(
                f"G0 assurance closure amendment operations[{index}] cannot address arrays or blank keys"
            )
            continue
        target: object = effective
        valid_target = True
        for part in parts[:-1]:
            if not isinstance(target, dict) or part not in target:
                failures.append(
                    f"G0 assurance closure amendment operations[{index}] parent path is absent"
                )
                valid_target = False
                break
            target = target[part]
        if not valid_target or not isinstance(target, dict):
            continue
        key = parts[-1]
        if operation_kind == "add" and key in target:
            failures.append(
                f"G0 assurance closure amendment operations[{index}] add target already exists"
            )
            continue
        if operation_kind == "replace" and key not in target:
            failures.append(
                f"G0 assurance closure amendment operations[{index}] replace target is absent"
            )
            continue
        target[key] = copy.deepcopy(operation.get("value"))
    require_equal(
        observed_operations,
        EXPECTED_ASSURANCE_AMENDMENT_OPERATIONS,
        "G0 assurance closure amendment operation order",
        failures,
    )
    return effective


def collect_assurance_amendment_failures(
    *,
    root: Path = ROOT,
    raw_json: str | None = None,
    checkpoint_raw_json: str | None = None,
    markdown: str | None = None,
    verify_files: bool = True,
) -> list[str]:
    failures: list[str] = []
    amendment_relative_path = "docs/v1/g0/assurance-closure-amendment-v2.json"
    checkpoint_relative_path = (
        "docs/v1/g0/assurance-closure-amendment-checkpoint-v2.json"
    )
    parent_relative_path = "docs/v1/g0/assurance-v1.json"
    parent_checkpoint_relative_path = (
        "docs/v1/g0/assurance-checkpoint-readback-v1.json"
    )
    artifact_snapshots: list[
        tuple[
            str,
            str,
            int,
            tuple[int, int, int, int, int, int],
            str,
        ]
    ] = []
    try:
        if verify_files:
            amendment_bytes, amendment_identity = read_g0_content_addressed_snapshot(
                root,
                amendment_relative_path,
                "G0 assurance closure amendment",
                MAX_G0_ASSURANCE_AMENDMENT_BYTES,
            )
            parent_bytes, parent_identity = read_g0_content_addressed_snapshot(
                root,
                parent_relative_path,
                "G0 assurance closure amendment parent assurance",
                checkpoint_checker.MAX_ASSURANCE_BYTES,
            )
            (
                parent_checkpoint_bytes,
                parent_checkpoint_identity,
            ) = read_g0_content_addressed_snapshot(
                root,
                parent_checkpoint_relative_path,
                "G0 assurance closure amendment parent checkpoint",
                checkpoint_checker.MAX_CHECKPOINT_BYTES,
            )
            checkpoint_bytes, checkpoint_identity = read_g0_content_addressed_snapshot(
                root,
                checkpoint_relative_path,
                "G0 assurance closure amendment checkpoint",
                MAX_G0_ASSURANCE_AMENDMENT_CHECKPOINT_BYTES,
            )
            artifact_snapshots = [
                (
                    amendment_relative_path,
                    "G0 assurance closure amendment",
                    MAX_G0_ASSURANCE_AMENDMENT_BYTES,
                    amendment_identity,
                    hashlib.sha256(amendment_bytes).hexdigest(),
                ),
                (
                    parent_relative_path,
                    "G0 assurance closure amendment parent assurance",
                    checkpoint_checker.MAX_ASSURANCE_BYTES,
                    parent_identity,
                    hashlib.sha256(parent_bytes).hexdigest(),
                ),
                (
                    parent_checkpoint_relative_path,
                    "G0 assurance closure amendment parent checkpoint",
                    checkpoint_checker.MAX_CHECKPOINT_BYTES,
                    parent_checkpoint_identity,
                    hashlib.sha256(parent_checkpoint_bytes).hexdigest(),
                ),
                (
                    checkpoint_relative_path,
                    "G0 assurance closure amendment checkpoint",
                    MAX_G0_ASSURANCE_AMENDMENT_CHECKPOINT_BYTES,
                    checkpoint_identity,
                    hashlib.sha256(checkpoint_bytes).hexdigest(),
                ),
            ]
        else:
            amendment_bytes = (root / amendment_relative_path).read_bytes()
            parent_bytes = (root / parent_relative_path).read_bytes()
            parent_checkpoint_bytes = (
                root / parent_checkpoint_relative_path
            ).read_bytes()
            checkpoint_bytes = (root / checkpoint_relative_path).read_bytes()
    except (OSError, checkpoint_checker.CheckpointValidationError) as error:
        return [f"cannot securely read G0 assurance closure amendment inputs: {error}"]
    if raw_json is None:
        try:
            raw_json = amendment_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            return [f"G0 assurance closure amendment is not UTF-8: {error}"]
    if verify_files:
        require_equal(
            hashlib.sha256(amendment_bytes).hexdigest(),
            EXPECTED_ASSURANCE_AMENDMENT_BYTE_SHA256,
            "G0 assurance closure amendment raw byte sha256",
            failures,
        )
    amendment, parse_failures = parse_g0_json_object(
        raw_json,
        "G0 assurance closure amendment",
    )
    failures.extend(parse_failures)
    if parse_failures:
        return failures
    require_equal(
        canonical_json_sha256(amendment),
        EXPECTED_ASSURANCE_AMENDMENT_CANONICAL_SHA256,
        "G0 assurance closure amendment canonical sha256",
        failures,
    )
    amendment = exact_keys(
        amendment,
        {
            "documentType",
            "schemaVersion",
            "amendmentId",
            "recordedDate",
            "status",
            "parent",
            "patchProfile",
            "operations",
            "effectiveAssurance",
            "authority",
            "acceptance",
        },
        "G0 assurance closure amendment",
        failures,
    )
    require_equal(
        amendment.get("documentType"),
        "aetherlink.v1-g0-assurance-closure-amendment",
        "G0 assurance closure amendment documentType",
        failures,
    )
    require_equal(
        amendment.get("schemaVersion"),
        "1.0",
        "G0 assurance closure amendment schemaVersion",
        failures,
    )
    require_equal(
        amendment.get("amendmentId"),
        "aetherlink_v1_g0_assurance_closure_amendment_v2",
        "G0 assurance closure amendment amendmentId",
        failures,
    )
    require_equal(
        amendment.get("status"),
        "candidate_not_published_not_authorized",
        "G0 assurance closure amendment status",
        failures,
    )

    parent_raw_sha256 = hashlib.sha256(parent_bytes).hexdigest()
    parent_checkpoint_raw_sha256 = hashlib.sha256(parent_checkpoint_bytes).hexdigest()
    try:
        parent_raw = parent_bytes.decode("utf-8")
        parent_checkpoint_raw = parent_checkpoint_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        failures.append(f"G0 assurance closure amendment parent is not UTF-8: {error}")
        return failures
    parent, parent_parse_failures = parse_g0_json_object(
        parent_raw,
        "G0 assurance closure amendment parent assurance",
    )
    parent_checkpoint, checkpoint_parse_failures = parse_g0_json_object(
        parent_checkpoint_raw,
        "G0 assurance closure amendment parent checkpoint",
    )
    failures.extend(parent_parse_failures)
    failures.extend(checkpoint_parse_failures)
    if parent_parse_failures or checkpoint_parse_failures:
        return failures
    parent_record = exact_keys(
        amendment.get("parent"),
        {
            "assuranceId",
            "assurancePath",
            "assuranceRawByteSha256",
            "assuranceCanonicalSha256",
            "checkpointId",
            "checkpointPath",
            "checkpointRawByteSha256",
            "checkpointCanonicalSha256",
            "observedContainingCommit",
            "publicationObservation",
        },
        "G0 assurance closure amendment parent",
        failures,
    )
    expected_parent = {
        "assuranceId": "aetherlink_v1_g0_assurance_v1",
        "assurancePath": "docs/v1/g0/assurance-v1.json",
        "assuranceRawByteSha256": EXPECTED_ASSURANCE_BYTE_SHA256,
        "assuranceCanonicalSha256": EXPECTED_ASSURANCE_CANONICAL_SHA256,
        "checkpointId": "aetherlink_v1_g0_assurance_checkpoint_readback_v1",
        "checkpointPath": "docs/v1/g0/assurance-checkpoint-readback-v1.json",
        "checkpointRawByteSha256": EXPECTED_ASSURANCE_CHECKPOINT_BYTE_SHA256,
        "checkpointCanonicalSha256": EXPECTED_ASSURANCE_CHECKPOINT_CANONICAL_SHA256,
        "observedContainingCommit": "929fda5f2c01cd7d53325a036071b6a684ecaa1f",
        "publicationObservation": (
            "local_commit_and_remote_tracking_push_reflog_only_not_independent_remote_byte_readback"
        ),
    }
    require_equal(
        parent_record,
        expected_parent,
        "G0 assurance closure amendment exact parent binding",
        failures,
    )
    require_equal(
        parent_raw_sha256,
        EXPECTED_ASSURANCE_BYTE_SHA256,
        "G0 assurance closure amendment parent assurance raw sha256",
        failures,
    )
    require_equal(
        canonical_json_sha256(parent),
        EXPECTED_ASSURANCE_CANONICAL_SHA256,
        "G0 assurance closure amendment parent assurance canonical sha256",
        failures,
    )
    require_equal(
        parent_checkpoint_raw_sha256,
        EXPECTED_ASSURANCE_CHECKPOINT_BYTE_SHA256,
        "G0 assurance closure amendment parent checkpoint raw sha256",
        failures,
    )
    require_equal(
        canonical_json_sha256(parent_checkpoint),
        EXPECTED_ASSURANCE_CHECKPOINT_CANONICAL_SHA256,
        "G0 assurance closure amendment parent checkpoint canonical sha256",
        failures,
    )

    patch_profile = exact_keys(
        amendment.get("patchProfile"),
        {
            "semantics",
            "allowedOperations",
            "unknownOperationOrPathPolicy",
            "arrayIndexOperationPolicy",
            "parentMutationPolicy",
            "effectiveDigestPolicy",
        },
        "G0 assurance closure amendment patchProfile",
        failures,
    )
    require_equal(
        patch_profile.get("semantics"),
        "ordered_json_pointer_add_replace_v1",
        "G0 assurance closure amendment patch semantics",
        failures,
    )
    require_equal(
        patch_profile.get("allowedOperations"),
        [
            {"op": operation, "path": path}
            for operation, path in EXPECTED_ASSURANCE_AMENDMENT_OPERATIONS
        ],
        "G0 assurance closure amendment allowed operation order",
        failures,
    )
    effective = apply_assurance_amendment_operations(
        parent,
        amendment.get("operations"),
        failures,
    )
    effective_record = exact_keys(
        amendment.get("effectiveAssurance"),
        {
            "assuranceId",
            "schemaVersion",
            "canonicalSha256",
            "status",
            "materializationPolicy",
        },
        "G0 assurance closure amendment effectiveAssurance",
        failures,
    )
    require_equal(
        effective_record.get("assuranceId"),
        "aetherlink_v1_g0_assurance_v2",
        "G0 effective assurance ID",
        failures,
    )
    require_equal(
        effective_record.get("schemaVersion"),
        "2.0",
        "G0 effective assurance schemaVersion",
        failures,
    )
    require_equal(
        effective_record.get("status"),
        "blocked_before_g1a",
        "G0 effective assurance status",
        failures,
    )
    require_equal(
        effective.get("assuranceId"),
        effective_record.get("assuranceId"),
        "G0 reconstructed effective assurance ID",
        failures,
    )
    require_equal(
        effective.get("schemaVersion"),
        effective_record.get("schemaVersion"),
        "G0 reconstructed effective assurance schemaVersion",
        failures,
    )
    require_equal(
        canonical_json_sha256(effective),
        EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256,
        "G0 reconstructed effective assurance canonical sha256",
        failures,
    )
    require_equal(
        effective_record.get("canonicalSha256"),
        EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256,
        "G0 recorded effective assurance canonical sha256",
        failures,
    )

    closure = effective.get("g0ClosureContract")
    if not isinstance(closure, dict):
        failures.append("G0 effective assurance closure contract must be an object")
        closure = {}
    require_equal(
        closure.get("schemaVersion"),
        2,
        "G0 effective assurance closure contract schemaVersion",
        failures,
    )
    require_equal(
        closure.get("executableCheckIds"),
        EXPECTED_G0_EXECUTABLE_CHECK_IDS,
        "G0 executable check IDs",
        failures,
    )
    require_equal(
        closure.get("nonExecutableCheckIds"),
        EXPECTED_G0_NON_EXECUTABLE_CHECK_IDS,
        "G0 non-executable check IDs",
        failures,
    )
    require_equal(
        closure.get("publicationReceiptProfile"),
        EXPECTED_G0_PUBLICATION_RECEIPT_PROFILE,
        "G0 effective assurance composite publication receipt profile",
        failures,
    )
    command_profiles = closure.get("commandProfiles")
    if not isinstance(command_profiles, list):
        failures.append("G0 effective assurance commandProfiles must be a list")
        command_profiles = []
    observed_profile_ids: list[object] = []
    observed_profile_checks: list[object] = []
    for index, raw_profile in enumerate(command_profiles):
        profile = exact_keys(
            raw_profile,
            {"commandProfileId", "canonicalProfileSha256", "profileBody"},
            f"G0 effective assurance commandProfiles[{index}]",
            failures,
        )
        profile_id = profile.get("commandProfileId")
        observed_profile_ids.append(profile_id)
        if not isinstance(profile_id, str) or re.fullmatch(
            G0_COMMAND_PROFILE_ID_PATTERN, profile_id
        ) is None:
            failures.append(f"G0 command profile {index} has invalid ID")
        profile_body = profile.get("profileBody")
        if not isinstance(profile_body, dict):
            failures.append(f"G0 command profile {index} body must be an object")
            profile_body = {}
        observed_profile_checks.append(profile_body.get("checkId"))
        require_equal(
            profile.get("canonicalProfileSha256"),
            canonical_json_sha256(profile_body),
            f"G0 command profile {index} self digest",
            failures,
        )
        if isinstance(profile_id, str):
            require_equal(
                profile.get("canonicalProfileSha256"),
                EXPECTED_G0_COMMAND_PROFILE_SHA256.get(profile_id),
                f"G0 command profile {index} pinned digest",
                failures,
            )
        require_equal(
            profile_body.get("currentAuthorizationState"),
            "not_authorized",
            f"G0 command profile {index} authorization state",
            failures,
        )
        require_equal(
            profile_body.get("networkPolicy"),
            "operating_system_egress_denied_gradle_offline_no_adb_no_physical_device",
            f"G0 command profile {index} network policy",
            failures,
        )
    require_equal(
        observed_profile_ids,
        list(EXPECTED_G0_COMMAND_PROFILE_SHA256),
        "G0 command profile order",
        failures,
    )
    require_equal(
        observed_profile_checks,
        EXPECTED_G0_EXECUTABLE_CHECK_IDS,
        "G0 command profile executable-check coverage",
        failures,
    )
    if len(command_profiles) == 2:
        full_steps = command_profiles[0].get("profileBody", {}).get("orderedSteps")
        release_steps = command_profiles[1].get("profileBody", {}).get("orderedSteps")
        require_equal(
            full_steps,
            [{"stepId": "full_no_device_quality", "argv": ["bash", "script/check_no_device_quality.sh"]}],
            "G0 full no-device command argv",
            failures,
        )
        require_equal(
            release_steps,
            [
                {
                    "stepId": "android_release_compilation",
                    "argv": [
                        "./gradlew",
                        "--offline",
                        "--no-daemon",
                        ":app:assembleRelease",
                        "-Pkotlin.incremental=false",
                    ],
                },
                {
                    "stepId": "macos_release_compilation",
                    "argv": ["swift", "build", "-c", "release", "--product", "AetherLink"],
                },
            ],
            "G0 release compilation ordered argv",
            failures,
        )

    expected_authority = {
        "g0DocumentationAndStaticValidationAllowed": True,
        "commandProfileCatalogAuthorizesExecution": False,
        "fullNoDeviceAggregateAllowed": False,
        "androidAndMacosReleaseCompilationAllowed": False,
        "compilerOrLinkerInvocationAllowed": False,
        "buildToolLocalIpcSocketAllowed": False,
        "loopbackTestSocketAllowed": False,
        "externalNetworkIoAllowed": False,
        "adbOrPhysicalDeviceAllowed": False,
        "productionKeySigningUploadOrDeploymentAllowed": False,
        "g1aNoNetworkImplementationAllowed": False,
    }
    require_equal(
        amendment.get("authority"),
        expected_authority,
        "G0 assurance closure amendment authority",
        failures,
    )
    require_equal(
        amendment.get("acceptance"),
        {
            "parentBytesUnchanged": True,
            "amendmentPublicationReceipt": "absent",
            "ownerAcceptance": "absent",
            "gateReceipts": [],
            "effectiveAssuranceActivated": False,
            "g0ExitComplete": False,
            "g1aMayStartNow": False,
        },
        "G0 assurance closure amendment acceptance",
        failures,
    )

    aggregate_script = root / "script/check_no_device_quality.sh"
    try:
        gradle_lines = [
            line.strip()
            for line in aggregate_script.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("run ./gradlew")
        ]
    except OSError as error:
        failures.append(f"cannot read G0 aggregate command source: {error}")
        gradle_lines = []
    require_equal(len(gradle_lines), 5, "G0 aggregate Gradle invocation count", failures)
    if any(not line.startswith("run ./gradlew --offline --no-daemon") for line in gradle_lines):
        failures.append("every G0 aggregate Gradle invocation must be offline")

    if checkpoint_raw_json is None:
        try:
            checkpoint_raw_json = checkpoint_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            failures.append(f"G0 assurance closure amendment checkpoint is not UTF-8: {error}")
            return failures
    if verify_files:
        require_equal(
            hashlib.sha256(checkpoint_bytes).hexdigest(),
            EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256,
            "G0 assurance closure amendment checkpoint raw byte sha256",
            failures,
        )
    checkpoint, checkpoint_failures = parse_g0_json_object(
        checkpoint_raw_json,
        "G0 assurance closure amendment checkpoint",
    )
    failures.extend(checkpoint_failures)
    if not checkpoint_failures:
        require_equal(
            canonical_json_sha256(checkpoint),
            EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_CANONICAL_SHA256,
            "G0 assurance closure amendment checkpoint canonical sha256",
            failures,
        )
        amendment_readback = checkpoint.get("amendmentReadback")
        effective_readback = checkpoint.get("effectiveAssuranceReadback")
        if not isinstance(amendment_readback, dict):
            failures.append("G0 amendment checkpoint amendmentReadback must be an object")
        else:
            require_equal(
                amendment_readback.get("amendmentRawByteSha256"),
                EXPECTED_ASSURANCE_AMENDMENT_BYTE_SHA256,
                "G0 amendment checkpoint amendment raw sha256",
                failures,
            )
            require_equal(
                amendment_readback.get("amendmentCanonicalSha256"),
                EXPECTED_ASSURANCE_AMENDMENT_CANONICAL_SHA256,
                "G0 amendment checkpoint amendment canonical sha256",
                failures,
            )
        if not isinstance(effective_readback, dict):
            failures.append("G0 amendment checkpoint effectiveAssuranceReadback must be an object")
        else:
            require_equal(
                effective_readback.get("canonicalSha256"),
                EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256,
                "G0 amendment checkpoint effective assurance canonical sha256",
                failures,
            )
        require_equal(
            checkpoint.get("status"),
            "candidate_observed_not_immutable",
            "G0 amendment checkpoint status",
            failures,
        )
        checkpoint_authority = checkpoint.get("authority")
        if not isinstance(checkpoint_authority, dict) or any(
            value is not False
            for key, value in checkpoint_authority.items()
            if key != "g0DocumentationAndStaticValidationAllowed"
        ):
            failures.append("G0 amendment checkpoint cannot open execution authority")

    if markdown is None:
        try:
            markdown = (
                root / "docs/v1/g0/assurance-closure-amendment-v2.md"
            ).read_text(encoding="utf-8")
        except OSError as error:
            failures.append(f"cannot read G0 assurance closure amendment markdown: {error}")
            markdown = ""
    for snippet in (
        "candidate_not_published_not_authorized",
        "preserves the exact committed V1 assurance and checkpoint bytes",
        "eleven ordered JSON Pointer operations",
        "composite publication receipt",
        "dormant composite publication candidate validator",
        "Only these two checks use command and gate receipts",
        "Both command profiles are `not_authorized`",
        "`--offline` alone is not zero-egress proof",
        "No receipt validator is activated",
        "G0 remains `blocked_before_g1a`",
    ):
        if snippet not in markdown:
            failures.append(f"G0 assurance closure amendment markdown is missing {snippet!r}")
    for (
        relative_path,
        label,
        maximum_bytes,
        expected_identity,
        expected_raw_sha256,
    ) in artifact_snapshots:
        failures.extend(
            collect_g0_final_snapshot_failures(
                root,
                relative_path,
                label,
                maximum_bytes,
                expected_identity,
                expected_raw_sha256,
            )
        )
    return failures


def check_repository_baseline(root: Path) -> list[str]:
    failures: list[str] = []
    gradle = (root / "apps/android/app/build.gradle.kts").read_text(encoding="utf-8")
    for snippet in (
        'applicationId = "com.localagentbridge.android"',
        "minSdk = 26",
        "targetSdk = 36",
        "compileSdk = 36",
        "versionCode = 1",
        'versionName = "0.1.0"',
    ):
        if snippet not in gradle:
            failures.append(f"Android G0 baseline drifted; missing {snippet!r}")

    package = (root / "Package.swift").read_text(encoding="utf-8")
    if "platforms: [.macOS(.v14)]" not in package:
        failures.append("macOS G0 minimum-version baseline drifted")

    build_script = (root / "script/build_and_run.sh").read_text(encoding="utf-8")
    for snippet in ('BUNDLE_ID="dev.aetherlink.companion"', 'MIN_SYSTEM_VERSION="14.0"', '/usr/bin/codesign --force --deep --sign -'):
        if snippet not in build_script:
            failures.append(f"macOS G0 development bundle baseline drifted; missing {snippet!r}")

    manifest = (root / "apps/android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    for snippet in ('android:allowBackup="false"', 'android:name="android.permission.CAMERA"'):
        if snippet not in manifest:
            failures.append(f"Android G0 manifest baseline drifted; missing {snippet!r}")

    locale_path = root / "apps/android/app/src/main/res/xml/locales_config.xml"
    try:
        locale_root = ET.parse(locale_path).getroot()
        namespace = "{http://schemas.android.com/apk/res/android}name"
        android_locales = [child.attrib.get(namespace) for child in locale_root]
    except (OSError, ET.ParseError) as error:
        failures.append(f"cannot parse Android locale config: {error}")
        android_locales = []
    if android_locales != ["en", "ko", "ja", "zh-CN", "fr"]:
        failures.append(f"Android G0 locale baseline drifted: {android_locales!r}")

    macos_resources = root / "apps/macos/LocalAgentBridgeApp/Sources/Resources"
    macos_locales = sorted(path.name for path in macos_resources.glob("*.lproj"))
    if macos_locales != ["en.lproj", "fr.lproj", "ja.lproj", "ko.lproj", "zh-Hans.lproj"]:
        failures.append(f"macOS G0 locale baseline drifted: {macos_locales!r}")
    return failures


def main() -> int:
    failures = collect_failures()
    if failures:
        for failure in failures:
            print(f"G0 decision/assurance check failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 decision, frozen V1 assurance/readback, and the content-addressed "
        "V2 closure-amendment candidate are internally consistent; owner "
        "acceptance, publication, command execution, full gates, G1a, and all "
        "network, signing, store, key, and deployment authorities remain closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
