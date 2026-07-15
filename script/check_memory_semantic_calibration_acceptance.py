#!/usr/bin/env python3
"""Validate the proposed semantic calibration acceptance review packet."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = (
    ROOT / "shared/evaluation/memory-semantic-duplicate-acceptance-review-v1.json"
)
MAXIMUM_REVIEW_BYTES = 1_024 * 1_024
MAXIMUM_SYNTHETIC_FIXTURE_BYTES = 8 * 1_024 * 1_024
MAXIMUM_HISTORICAL_REPORT_BYTES = 32 * 1_024 * 1_024

STATUS = "proposed_not_selected"
SYNTHETIC_FIXTURE_PATH = (
    "shared/evaluation/memory-semantic-duplicate-calibration-v1.json"
)
SYNTHETIC_FIXTURE_SHA256 = (
    "d41a31045a5a4d35ad8ce4ee05af34fc0937326b114a1512fb1160be75b571ff"
)
REQUIRED_BEFORE = [
    "representative_corpus_intake",
    "representative_batch_evaluator",
    "target_matrix_execution",
    "threshold_default_or_range_change",
    "automatic_merge",
    "automatic_memory_mutation",
    "protocol_change",
]
UNRESOLVED_INPUTS = [
    "label_coverage_policy",
    "precommitted_acceptance_floors",
    "privacy_review",
    "representative_batch_evaluator",
    "representative_corpus",
    "target_model_artifact_matrix",
]
REQUIRED_PROVIDER_FAMILIES = ["lm_studio", "ollama"]
REASON_CODES = [
    "acceptance_floors_not_approved",
    "privacy_review_incomplete",
    "representative_batch_evaluator_missing",
    "representative_corpus_missing",
    "target_matrix_incomplete",
]

TOP_LEVEL_KEYS = {
    "schema_version",
    "document_type",
    "review_id",
    "status",
    "evidence_status",
    "measurement_status",
    "approval_required",
    "current_behavior",
    "representative_corpus_recommendation",
    "target_model_artifact_matrix_recommendation",
    "acceptance_floor_recommendation",
    "current_assessment",
    "immutability",
}
APPROVAL_KEYS = {
    "decision_id",
    "approval_source",
    "selected_recommendation_count",
    "explicit_user_approval_required",
    "decision_boundary",
    "unresolved_inputs",
    "required_before",
}
CURRENT_BEHAVIOR_KEYS = {
    "review_threshold_basis_points",
    "minimum_threshold_basis_points",
    "maximum_threshold_basis_points",
    "default_threshold_change_authorized",
    "threshold_range_change_authorized",
    "automatic_memory_mutation_authorized",
    "automatic_merge_authorized",
    "protocol_change_authorized",
    "representative_corpus_intake_authorized",
    "additional_live_matrix_execution_authorized",
}
AUTHORIZATION_KEYS = (
    "default_threshold_change_authorized",
    "threshold_range_change_authorized",
    "automatic_memory_mutation_authorized",
    "automatic_merge_authorized",
    "protocol_change_authorized",
    "representative_corpus_intake_authorized",
    "additional_live_matrix_execution_authorized",
)
REPRESENTATIVE_KEYS = {
    "status",
    "corpus_artifact_path",
    "corpus_sha256",
    "acceptance_eligible",
    "requirements",
    "current_synthetic_fixture",
}
REQUIREMENT_VALUES = {
    "minimum_entry_count": 200,
    "minimum_labeled_pair_count": 500,
    "minimum_positive_label_count": 100,
    "minimum_negative_label_count": 100,
    "minimum_language_count": 5,
    "minimum_entries_per_language": 20,
    "minimum_independent_reviewers_per_pair": 2,
    "adjudication_required": True,
    "declared_label_coverage_policy_required": True,
    "source_group_disjoint_holdout_required": True,
    "locked_holdout_required": True,
    "representative_batch_evaluator_required": True,
    "consented_or_synthetic_provenance_required": True,
    "raw_production_memory_forbidden": True,
    "secrets_forbidden": True,
    "direct_identifiers_forbidden": True,
    "opaque_entry_ids_required": True,
    "privacy_review_required": True,
    "label_guideline_version_required": True,
    "exact_pair_labels_required": True,
    "complete_link_cluster_labels_required": True,
}
SYNTHETIC_FIXTURE_KEYS = {
    "path",
    "sha256",
    "classification",
    "acceptance_eligible",
}
TARGET_MATRIX_KEYS = {
    "status",
    "required_provider_families",
    "minimum_required_artifact_count",
    "candidate_artifacts",
    "matrix_complete",
    "missing_required_artifact_count",
}
CANDIDATE_VALUES = {
    "provider_family": "ollama",
    "model_id": "ollama:embeddinggemma:latest",
    "artifact_fingerprint": (
        "ollama-sha256:85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1"
    ),
    "historical_report_path": (
        "build/qa/memory-semantic-calibration-live-ollama-embeddinggemma-20260714.json"
    ),
    "historical_report_sha256": (
        "c733979b0c721fb32a11bd997c66789ce6a6003669d89be0eb91e155e5475544"
    ),
    "observed_corpus_id": "memory-semantic-duplicate-calibration-v1",
    "observed_corpus_sha256": SYNTHETIC_FIXTURE_SHA256,
    "classification": "observed_synthetic_only",
    "acceptance_eligible": False,
}
FLOOR_VALUES = {
    "status": STATUS,
    "minimum_pair_precision_basis_points": 9_500,
    "minimum_pair_recall_basis_points": 8_000,
    "minimum_pair_f1_basis_points": 8_500,
    "minimum_predicted_positive_count": 100,
    "minimum_actual_positive_count": 100,
    "minimum_language_stratum_precision_basis_points": 9_000,
    "minimum_language_stratum_recall_basis_points": 7_000,
    "minimum_language_stratum_predicted_positive_count": 20,
    "minimum_language_stratum_actual_positive_count": 20,
    "minimum_hard_negative_count": 20,
    "minimum_hard_negative_specificity_basis_points": 9_500,
    "null_precision_fails": True,
    "review_clusters_exact_match_required": True,
    "all_required_artifacts_must_pass": True,
    "single_shared_threshold_required": True,
    "same_language_stratum_required": True,
    "cross_language_stratum_required": True,
    "hard_negative_stratum_required": True,
    "per_artifact_and_stratum_pass_required": True,
    "aggregate_averaging_forbidden": True,
}
ASSESSMENT_KEYS = {
    "representative_corpus_available",
    "target_matrix_complete",
    "acceptance_floors_approved",
    "privacy_review_complete",
    "acceptance_decision_eligible",
    "selected_threshold_basis_points",
    "reason_codes",
}
IMMUTABILITY_VALUES = {
    "record_state": "closed",
    "amendment_policy": "supersede_with_new_versioned_review",
}


class AcceptanceReviewError(Exception):
    """A validation failure carrying only a stable, content-free code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise AcceptanceReviewError("arguments_invalid")


def _fail(code: str) -> None:
    raise AcceptanceReviewError(code)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> None:
    del value
    _fail("invalid_json_number")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        _fail("invalid_json_number")
    return parsed


def _read_review(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError:
        raise AcceptanceReviewError("review_unreadable") from None
    if not stat.S_ISREG(metadata.st_mode):
        _fail("review_type_invalid")
    if metadata.st_size <= 0 or metadata.st_size > MAXIMUM_REVIEW_BYTES:
        _fail("review_size_invalid")

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            _fail("review_type_invalid")
        raise AcceptanceReviewError("review_unreadable") from None
    try:
        opened_metadata = os.fstat(descriptor)
        if not stat.S_ISREG(opened_metadata.st_mode):
            _fail("review_type_invalid")
        if opened_metadata.st_size <= 0 or opened_metadata.st_size > MAXIMUM_REVIEW_BYTES:
            _fail("review_size_invalid")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                descriptor,
                min(128 * 1_024, MAXIMUM_REVIEW_BYTES + 1 - total),
            )
            if not chunk:
                break
            total += len(chunk)
            if total > MAXIMUM_REVIEW_BYTES:
                _fail("review_size_invalid")
            chunks.append(chunk)
    except OSError:
        raise AcceptanceReviewError("review_unreadable") from None
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if not raw:
        _fail("review_size_invalid")
    return raw


def _strict_json_loads(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise AcceptanceReviewError("review_json_invalid") from None
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
            parse_float=_parse_finite_float,
        )
    except AcceptanceReviewError:
        raise
    except (json.JSONDecodeError, OverflowError, ValueError, RecursionError):
        raise AcceptanceReviewError("review_json_invalid") from None


def _object(value: Any, code: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(code)
    return value


def _array(value: Any, code: str) -> list[Any]:
    if type(value) is not list:
        _fail(code)
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        _fail(code)


def _exact_scalar(value: Any, expected: Any, code: str) -> None:
    if expected is None:
        if value is not None:
            _fail(code)
        return
    if type(value) is not type(expected) or value != expected:
        _fail(code)


def _exact_string_list(value: Any, expected: list[str], code: str) -> None:
    items = _array(value, code)
    if len(items) != len(expected):
        _fail(code)
    for item, expected_item in zip(items, expected):
        _exact_scalar(item, expected_item, code)


def _validate_fixed_object(
    value: Any, expected: dict[str, Any], keys_code: str, value_code: str
) -> dict[str, Any]:
    result = _object(value, keys_code)
    _exact_keys(result, set(expected), keys_code)
    for key, expected_value in expected.items():
        _exact_scalar(result[key], expected_value, value_code)
    return result


def _bounded_regular_file_sha256(
    path: Path,
    *,
    maximum_bytes: int,
    allow_missing: bool,
    error_prefix: str,
) -> str | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return None
        raise AcceptanceReviewError(f"{error_prefix}_unreadable") from None
    except OSError:
        raise AcceptanceReviewError(f"{error_prefix}_unreadable") from None
    if not stat.S_ISREG(metadata.st_mode):
        _fail(f"{error_prefix}_type_invalid")
    if metadata.st_size <= 0 or metadata.st_size > maximum_bytes:
        _fail(f"{error_prefix}_size_invalid")

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    digest = hashlib.sha256()
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ENOENT and allow_missing:
            return None
        if error.errno == errno.ELOOP:
            _fail(f"{error_prefix}_type_invalid")
        raise AcceptanceReviewError(f"{error_prefix}_unreadable") from None
    try:
        opened_metadata = os.fstat(descriptor)
        if not stat.S_ISREG(opened_metadata.st_mode):
            _fail(f"{error_prefix}_type_invalid")
        if opened_metadata.st_size <= 0 or opened_metadata.st_size > maximum_bytes:
            _fail(f"{error_prefix}_size_invalid")
        total = 0
        while True:
            chunk = os.read(descriptor, min(128 * 1_024, maximum_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                _fail(f"{error_prefix}_size_invalid")
            digest.update(chunk)
    except OSError:
        raise AcceptanceReviewError(f"{error_prefix}_unreadable") from None
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _validate_fixture_hash(root: Path) -> None:
    actual = _bounded_regular_file_sha256(
        root / SYNTHETIC_FIXTURE_PATH,
        maximum_bytes=MAXIMUM_SYNTHETIC_FIXTURE_BYTES,
        allow_missing=False,
        error_prefix="synthetic_fixture",
    )
    if actual != SYNTHETIC_FIXTURE_SHA256:
        _fail("synthetic_fixture_hash_invalid")


def _validate_optional_historical_report(root: Path) -> None:
    actual = _bounded_regular_file_sha256(
        root / CANDIDATE_VALUES["historical_report_path"],
        maximum_bytes=MAXIMUM_HISTORICAL_REPORT_BYTES,
        allow_missing=True,
        error_prefix="historical_report",
    )
    if actual is not None and actual != CANDIDATE_VALUES["historical_report_sha256"]:
        _fail("historical_report_hash_invalid")


def validate_review_document(document: Any, *, root: Path = ROOT) -> dict[str, Any]:
    review = _object(document, "review_type_invalid")
    _exact_keys(review, TOP_LEVEL_KEYS, "review_keys_invalid")
    identity = {
        "schema_version": 1,
        "document_type": "aetherlink.memory-semantic-duplicate-acceptance-review",
        "review_id": "memory_semantic_duplicate_acceptance_v1_recommended",
        "status": STATUS,
        "evidence_status": "blocked_missing_representative_corpus",
        "measurement_status": "not_started",
    }
    for key, expected in identity.items():
        _exact_scalar(review[key], expected, "review_identity_invalid")

    approval = _object(review["approval_required"], "approval_type_invalid")
    _exact_keys(approval, APPROVAL_KEYS, "approval_keys_invalid")
    for key, expected in {
        "decision_id": None,
        "approval_source": None,
        "selected_recommendation_count": 0,
        "explicit_user_approval_required": True,
        "decision_boundary": "separate_versioned_decision_before_behavior_change",
    }.items():
        _exact_scalar(approval[key], expected, "approval_invalid")
    _exact_string_list(
        approval["unresolved_inputs"], UNRESOLVED_INPUTS, "approval_gate_invalid"
    )
    _exact_string_list(approval["required_before"], REQUIRED_BEFORE, "approval_gate_invalid")

    behavior = _object(review["current_behavior"], "current_behavior_type_invalid")
    _exact_keys(behavior, CURRENT_BEHAVIOR_KEYS, "current_behavior_keys_invalid")
    for key, expected in {
        "review_threshold_basis_points": 9_000,
        "minimum_threshold_basis_points": 8_000,
        "maximum_threshold_basis_points": 10_000,
    }.items():
        _exact_scalar(behavior[key], expected, "current_threshold_invalid")
    for key in AUTHORIZATION_KEYS:
        _exact_scalar(behavior[key], False, "authorization_invalid")

    representative = _object(
        review["representative_corpus_recommendation"], "representative_type_invalid"
    )
    _exact_keys(representative, REPRESENTATIVE_KEYS, "representative_keys_invalid")
    for key, expected in {
        "status": STATUS,
        "corpus_artifact_path": None,
        "corpus_sha256": None,
        "acceptance_eligible": False,
    }.items():
        _exact_scalar(representative[key], expected, "representative_invalid")
    _validate_fixed_object(
        representative["requirements"],
        REQUIREMENT_VALUES,
        "requirements_keys_invalid",
        "requirements_invalid",
    )
    synthetic = _object(
        representative["current_synthetic_fixture"], "synthetic_fixture_type_invalid"
    )
    _exact_keys(synthetic, SYNTHETIC_FIXTURE_KEYS, "synthetic_fixture_keys_invalid")
    for key, expected in {
        "path": SYNTHETIC_FIXTURE_PATH,
        "sha256": SYNTHETIC_FIXTURE_SHA256,
        "classification": "synthetic_evaluator_only",
        "acceptance_eligible": False,
    }.items():
        _exact_scalar(synthetic[key], expected, "synthetic_fixture_invalid")
    _validate_fixture_hash(root)

    matrix = _object(
        review["target_model_artifact_matrix_recommendation"], "target_matrix_type_invalid"
    )
    _exact_keys(matrix, TARGET_MATRIX_KEYS, "target_matrix_keys_invalid")
    _exact_scalar(matrix["status"], STATUS, "target_matrix_invalid")
    _exact_string_list(
        matrix["required_provider_families"],
        REQUIRED_PROVIDER_FAMILIES,
        "provider_families_invalid",
    )
    for key, expected in {
        "minimum_required_artifact_count": 2,
        "matrix_complete": False,
        "missing_required_artifact_count": 1,
    }.items():
        _exact_scalar(matrix[key], expected, "target_matrix_invalid")
    candidates = _array(matrix["candidate_artifacts"], "candidate_artifacts_invalid")
    if len(candidates) != 1:
        _fail("candidate_artifacts_invalid")
    _validate_fixed_object(
        candidates[0],
        CANDIDATE_VALUES,
        "candidate_artifact_keys_invalid",
        "candidate_artifact_invalid",
    )
    _validate_optional_historical_report(root)

    _validate_fixed_object(
        review["acceptance_floor_recommendation"],
        FLOOR_VALUES,
        "acceptance_floor_keys_invalid",
        "acceptance_floor_invalid",
    )

    assessment = _object(review["current_assessment"], "assessment_type_invalid")
    _exact_keys(assessment, ASSESSMENT_KEYS, "assessment_keys_invalid")
    for key, expected in {
        "representative_corpus_available": False,
        "target_matrix_complete": False,
        "acceptance_floors_approved": False,
        "privacy_review_complete": False,
        "acceptance_decision_eligible": False,
        "selected_threshold_basis_points": None,
    }.items():
        _exact_scalar(assessment[key], expected, "assessment_invalid")
    _exact_string_list(assessment["reason_codes"], REASON_CODES, "reason_codes_invalid")
    _validate_fixed_object(
        review["immutability"],
        IMMUTABILITY_VALUES,
        "immutability_keys_invalid",
        "immutability_invalid",
    )
    return review


def validate_acceptance_review(
    review_path: Path = DEFAULT_REVIEW, *, root: Path = ROOT
) -> dict[str, Any]:
    return validate_review_document(_strict_json_loads(_read_review(review_path)), root=root)


def build_summary(review: dict[str, Any]) -> dict[str, Any]:
    requirements = review["representative_corpus_recommendation"]["requirements"]
    matrix = review["target_model_artifact_matrix_recommendation"]
    floors = review["acceptance_floor_recommendation"]
    behavior = review["current_behavior"]
    return {
        "acceptance_decision_eligible": review["current_assessment"][
            "acceptance_decision_eligible"
        ],
        "acceptance_floors": {
            "all_required_artifacts_must_pass": floors[
                "all_required_artifacts_must_pass"
            ],
            "minimum_pair_f1_basis_points": floors["minimum_pair_f1_basis_points"],
            "minimum_pair_precision_basis_points": floors[
                "minimum_pair_precision_basis_points"
            ],
            "minimum_pair_recall_basis_points": floors[
                "minimum_pair_recall_basis_points"
            ],
            "minimum_predicted_positive_count": floors[
                "minimum_predicted_positive_count"
            ],
            "minimum_actual_positive_count": floors[
                "minimum_actual_positive_count"
            ],
            "minimum_language_stratum_precision_basis_points": floors[
                "minimum_language_stratum_precision_basis_points"
            ],
            "minimum_language_stratum_recall_basis_points": floors[
                "minimum_language_stratum_recall_basis_points"
            ],
            "minimum_hard_negative_count": floors["minimum_hard_negative_count"],
            "minimum_hard_negative_specificity_basis_points": floors[
                "minimum_hard_negative_specificity_basis_points"
            ],
            "minimum_language_stratum_predicted_positive_count": floors[
                "minimum_language_stratum_predicted_positive_count"
            ],
            "minimum_language_stratum_actual_positive_count": floors[
                "minimum_language_stratum_actual_positive_count"
            ],
            "null_precision_fails": floors["null_precision_fails"],
            "review_clusters_exact_match_required": floors[
                "review_clusters_exact_match_required"
            ],
            "single_shared_threshold_required": floors[
                "single_shared_threshold_required"
            ],
            "same_language_stratum_required": floors[
                "same_language_stratum_required"
            ],
            "cross_language_stratum_required": floors[
                "cross_language_stratum_required"
            ],
            "hard_negative_stratum_required": floors[
                "hard_negative_stratum_required"
            ],
            "per_artifact_and_stratum_pass_required": floors[
                "per_artifact_and_stratum_pass_required"
            ],
            "aggregate_averaging_forbidden": floors[
                "aggregate_averaging_forbidden"
            ],
        },
        "approval_counts": {
            "selected_recommendation_count": review["approval_required"][
                "selected_recommendation_count"
            ]
        },
        "authorization": {key: behavior[key] for key in AUTHORIZATION_KEYS},
        "current_review_threshold_basis_points": behavior[
            "review_threshold_basis_points"
        ],
        "representative_corpus_requirement_counts": {
            key: requirements[key]
            for key in (
                "minimum_entry_count",
                "minimum_labeled_pair_count",
                "minimum_positive_label_count",
                "minimum_negative_label_count",
                "minimum_language_count",
                "minimum_entries_per_language",
                "minimum_independent_reviewers_per_pair",
            )
        },
        "status": review["status"],
        "evidence_status": review["evidence_status"],
        "measurement_status": review["measurement_status"],
        "target_matrix_counts": {
            "candidate_artifact_count": len(matrix["candidate_artifacts"]),
            "minimum_required_artifact_count": matrix["minimum_required_artifact_count"],
            "missing_required_artifact_count": matrix["missing_required_artifact_count"],
            "required_provider_family_count": len(matrix["required_provider_families"]),
        },
    }


def _parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        review = validate_acceptance_review(arguments.review, root=ROOT)
        print(
            json.dumps(
                build_summary(review),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except AcceptanceReviewError as error:
        print(f"acceptance_review_error:{error.code}", file=sys.stderr)
        return 2
    except Exception:
        print("acceptance_review_error:internal_error", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
