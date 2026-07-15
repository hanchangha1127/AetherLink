#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPT_DIR / "check_memory_semantic_calibration_acceptance.py"
SPEC = importlib.util.spec_from_file_location(
    "check_memory_semantic_calibration_acceptance", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
acceptance = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = acceptance
SPEC.loader.exec_module(acceptance)

COPY_HYGIENE_PATH = SCRIPT_DIR / "check_copy_hygiene.py"
COPY_HYGIENE_SPEC = importlib.util.spec_from_file_location(
    "check_copy_hygiene_for_calibration_acceptance", COPY_HYGIENE_PATH
)
assert COPY_HYGIENE_SPEC is not None and COPY_HYGIENE_SPEC.loader is not None
copy_hygiene = importlib.util.module_from_spec(COPY_HYGIENE_SPEC)
sys.modules[COPY_HYGIENE_SPEC.name] = copy_hygiene
COPY_HYGIENE_SPEC.loader.exec_module(copy_hygiene)


def canonical_review() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "document_type": "aetherlink.memory-semantic-duplicate-acceptance-review",
        "review_id": "memory_semantic_duplicate_acceptance_v1_recommended",
        "status": "proposed_not_selected",
        "evidence_status": "blocked_missing_representative_corpus",
        "measurement_status": "not_started",
        "approval_required": {
            "decision_id": None,
            "approval_source": None,
            "selected_recommendation_count": 0,
            "explicit_user_approval_required": True,
            "decision_boundary": "separate_versioned_decision_before_behavior_change",
            "unresolved_inputs": list(acceptance.UNRESOLVED_INPUTS),
            "required_before": list(acceptance.REQUIRED_BEFORE),
        },
        "current_behavior": {
            "review_threshold_basis_points": 9_000,
            "minimum_threshold_basis_points": 8_000,
            "maximum_threshold_basis_points": 10_000,
            "default_threshold_change_authorized": False,
            "threshold_range_change_authorized": False,
            "automatic_memory_mutation_authorized": False,
            "automatic_merge_authorized": False,
            "protocol_change_authorized": False,
            "representative_corpus_intake_authorized": False,
            "additional_live_matrix_execution_authorized": False,
        },
        "representative_corpus_recommendation": {
            "status": "proposed_not_selected",
            "corpus_artifact_path": None,
            "corpus_sha256": None,
            "acceptance_eligible": False,
            "requirements": copy.deepcopy(acceptance.REQUIREMENT_VALUES),
            "current_synthetic_fixture": {
                "path": acceptance.SYNTHETIC_FIXTURE_PATH,
                "sha256": acceptance.SYNTHETIC_FIXTURE_SHA256,
                "classification": "synthetic_evaluator_only",
                "acceptance_eligible": False,
            },
        },
        "target_model_artifact_matrix_recommendation": {
            "status": "proposed_not_selected",
            "required_provider_families": list(acceptance.REQUIRED_PROVIDER_FAMILIES),
            "minimum_required_artifact_count": 2,
            "candidate_artifacts": [copy.deepcopy(acceptance.CANDIDATE_VALUES)],
            "matrix_complete": False,
            "missing_required_artifact_count": 1,
        },
        "acceptance_floor_recommendation": copy.deepcopy(acceptance.FLOOR_VALUES),
        "current_assessment": {
            "representative_corpus_available": False,
            "target_matrix_complete": False,
            "acceptance_floors_approved": False,
            "privacy_review_complete": False,
            "acceptance_decision_eligible": False,
            "selected_threshold_basis_points": None,
            "reason_codes": list(acceptance.REASON_CODES),
        },
        "immutability": copy.deepcopy(acceptance.IMMUTABILITY_VALUES),
    }


class MemorySemanticCalibrationAcceptanceTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        evaluation = self.root / "shared/evaluation"
        evaluation.mkdir(parents=True)
        source_fixture = acceptance.ROOT / acceptance.SYNTHETIC_FIXTURE_PATH
        shutil.copyfile(source_fixture, evaluation / source_fixture.name)
        self.review = canonical_review()
        self.review_path = evaluation / "review.json"
        self.write_review()

    def write_review(self, review: Any | None = None) -> None:
        if review is None:
            review = self.review
        self.review_path.write_bytes(
            json.dumps(review, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )

    def validate(self) -> dict[str, Any]:
        return acceptance.validate_acceptance_review(self.review_path, root=self.root)

    def assert_error(self, code: str, callback: Callable[[], Any]) -> None:
        with self.assertRaises(acceptance.AcceptanceReviewError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def mutate(self, path: tuple[Any, ...], value: Any) -> None:
        target: Any = self.review
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = value
        self.write_review()

    def test_generated_canonical_review_validates_against_injected_root(self) -> None:
        validated = self.validate()
        self.assertEqual(validated, self.review)

    def test_real_repo_packet_validates_when_present(self) -> None:
        if not acceptance.DEFAULT_REVIEW.exists():
            self.skipTest("repository acceptance packet is not present")
        acceptance.validate_acceptance_review(acceptance.DEFAULT_REVIEW, root=acceptance.ROOT)

    def test_duplicate_key_nonfinite_utf8_and_size_are_rejected(self) -> None:
        raw = self.review_path.read_bytes().replace(
            b'"schema_version":1,', b'"schema_version":1,"schema_version":1,', 1
        )
        self.review_path.write_bytes(raw)
        self.assert_error("duplicate_json_key", self.validate)

        self.review_path.write_bytes(b'{"schema_version":NaN}')
        self.assert_error("invalid_json_number", self.validate)
        self.review_path.write_bytes(b'{"schema_version":1e999}')
        self.assert_error("invalid_json_number", self.validate)
        self.review_path.write_bytes(b"\xff")
        self.assert_error("review_json_invalid", self.validate)
        self.review_path.write_bytes(b" " * (acceptance.MAXIMUM_REVIEW_BYTES + 1))
        self.assert_error("review_size_invalid", self.validate)

    def test_review_path_symlink_nonregular_and_empty_fail_closed(self) -> None:
        canonical = self.review_path.read_bytes()
        target = self.review_path.with_name("canonical-review.json")
        target.write_bytes(canonical)

        self.review_path.unlink()
        self.review_path.symlink_to(target)
        self.assert_error("review_type_invalid", self.validate)

        self.review_path.unlink()
        os.mkfifo(self.review_path)
        self.assert_error("review_type_invalid", self.validate)

        self.review_path.unlink()
        self.review_path.write_bytes(b"")
        self.assert_error("review_size_invalid", self.validate)

    def test_copy_hygiene_guard_rejects_symlink_fifo_empty_and_oversize(self) -> None:
        guarded = self.root / "guarded.json"
        guarded.write_bytes(b"{}")
        self.assertEqual(copy_hygiene.read_bounded_regular_file(guarded, 2), b"{}")

        target = self.root / "target.json"
        target.write_bytes(b"{}")
        guarded.unlink()
        guarded.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "not_regular"):
            copy_hygiene.read_bounded_regular_file(guarded, 2)

        guarded.unlink()
        os.mkfifo(guarded)
        with self.assertRaisesRegex(ValueError, "not_regular"):
            copy_hygiene.read_bounded_regular_file(guarded, 2)

        guarded.unlink()
        guarded.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "size_invalid"):
            copy_hygiene.read_bounded_regular_file(guarded, 2)

        guarded.write_bytes(b"xxx")
        with self.assertRaisesRegex(ValueError, "size_invalid"):
            copy_hygiene.read_bounded_regular_file(guarded, 2)

    def test_exact_integer_and_boolean_types_are_required(self) -> None:
        mutations = [
            (("schema_version",), True, "review_identity_invalid"),
            (("schema_version",), 1.0, "review_identity_invalid"),
            (
                ("approval_required", "selected_recommendation_count"),
                False,
                "approval_invalid",
            ),
            (
                ("current_behavior", "review_threshold_basis_points"),
                9_000.0,
                "current_threshold_invalid",
            ),
            (
                ("current_behavior", "automatic_memory_mutation_authorized"),
                0,
                "authorization_invalid",
            ),
            (
                (
                    "representative_corpus_recommendation",
                    "requirements",
                    "minimum_entry_count",
                ),
                200.0,
                "requirements_invalid",
            ),
            (
                ("acceptance_floor_recommendation", "null_precision_fails"),
                1,
                "acceptance_floor_invalid",
            ),
        ]
        for path, value, code in mutations:
            with self.subTest(path=path, value=value):
                self.review = canonical_review()
                self.mutate(path, value)
                self.assert_error(code, self.validate)

    def test_unknown_and_missing_fields_are_rejected_at_each_level(self) -> None:
        containers = [
            ((), "review_keys_invalid"),
            (("approval_required",), "approval_keys_invalid"),
            (("current_behavior",), "current_behavior_keys_invalid"),
            (
                ("representative_corpus_recommendation",),
                "representative_keys_invalid",
            ),
            (
                ("representative_corpus_recommendation", "requirements"),
                "requirements_keys_invalid",
            ),
            (
                (
                    "representative_corpus_recommendation",
                    "current_synthetic_fixture",
                ),
                "synthetic_fixture_keys_invalid",
            ),
            (
                ("target_model_artifact_matrix_recommendation",),
                "target_matrix_keys_invalid",
            ),
            (
                ("target_model_artifact_matrix_recommendation", "candidate_artifacts", 0),
                "candidate_artifact_keys_invalid",
            ),
            (("acceptance_floor_recommendation",), "acceptance_floor_keys_invalid"),
            (("current_assessment",), "assessment_keys_invalid"),
            (("immutability",), "immutability_keys_invalid"),
        ]
        for path, code in containers:
            with self.subTest(path=path, mutation="unknown"):
                self.review = canonical_review()
                target: Any = self.review
                for component in path:
                    target = target[component]
                target["unknown"] = False
                self.write_review()
                self.assert_error(code, self.validate)
            with self.subTest(path=path, mutation="missing"):
                self.review = canonical_review()
                target = self.review
                for component in path:
                    target = target[component]
                del target[next(iter(target))]
                self.write_review()
                self.assert_error(code, self.validate)

    def test_status_approval_and_authorization_gate_drift_are_rejected(self) -> None:
        mutations = [
            (("status",), "approved", "review_identity_invalid"),
            (("evidence_status",), "ready", "review_identity_invalid"),
            (("measurement_status",), "complete", "review_identity_invalid"),
            (("approval_required", "decision_id"), "decision", "approval_invalid"),
            (
                ("approval_required", "explicit_user_approval_required"),
                False,
                "approval_invalid",
            ),
            (
                ("approval_required", "unresolved_inputs"),
                list(reversed(acceptance.UNRESOLVED_INPUTS)),
                "approval_gate_invalid",
            ),
            (
                ("approval_required", "required_before"),
                list(reversed(acceptance.REQUIRED_BEFORE)),
                "approval_gate_invalid",
            ),
            (
                ("representative_corpus_recommendation", "status"),
                "selected",
                "representative_invalid",
            ),
        ]
        for path, value, code in mutations:
            with self.subTest(path=path):
                self.review = canonical_review()
                self.mutate(path, value)
                self.assert_error(code, self.validate)

        for key in acceptance.AUTHORIZATION_KEYS:
            with self.subTest(authorization=key):
                self.review = canonical_review()
                self.mutate(("current_behavior", key), True)
                self.assert_error("authorization_invalid", self.validate)

    def test_actual_synthetic_fixture_hash_drift_is_rejected(self) -> None:
        fixture = self.root / acceptance.SYNTHETIC_FIXTURE_PATH
        fixture.write_bytes(fixture.read_bytes() + b"\n")
        self.assert_error("synthetic_fixture_hash_invalid", self.validate)

    def test_synthetic_fixture_symlink_nonregular_and_size_fail_closed(self) -> None:
        fixture = self.root / acceptance.SYNTHETIC_FIXTURE_PATH
        source_fixture = acceptance.ROOT / acceptance.SYNTHETIC_FIXTURE_PATH

        fixture.unlink()
        fixture.symlink_to(source_fixture)
        self.assert_error("synthetic_fixture_type_invalid", self.validate)

        fixture.unlink()
        os.mkfifo(fixture)
        self.assert_error("synthetic_fixture_type_invalid", self.validate)

        fixture.unlink()
        fixture.write_bytes(b"x" * (acceptance.MAXIMUM_SYNTHETIC_FIXTURE_BYTES + 1))
        self.assert_error("synthetic_fixture_size_invalid", self.validate)

        fixture.write_bytes(b"")
        self.assert_error("synthetic_fixture_size_invalid", self.validate)

    def test_matrix_row_provider_order_and_eligibility_drift_are_rejected(self) -> None:
        matrix_path = ("target_model_artifact_matrix_recommendation",)
        mutations = [
            (
                matrix_path + ("required_provider_families",),
                ["ollama", "lm_studio"],
                "provider_families_invalid",
            ),
            (
                matrix_path + ("candidate_artifacts", 0, "provider_family"),
                "lm_studio",
                "candidate_artifact_invalid",
            ),
            (
                matrix_path + ("candidate_artifacts", 0, "model_id"),
                "ollama:other",
                "candidate_artifact_invalid",
            ),
            (
                matrix_path + ("candidate_artifacts", 0, "acceptance_eligible"),
                True,
                "candidate_artifact_invalid",
            ),
            (matrix_path + ("matrix_complete",), True, "target_matrix_invalid"),
            (matrix_path + ("missing_required_artifact_count",), 0, "target_matrix_invalid"),
        ]
        for path, value, code in mutations:
            with self.subTest(path=path):
                self.review = canonical_review()
                self.mutate(path, value)
                self.assert_error(code, self.validate)

        self.review = canonical_review()
        self.review["target_model_artifact_matrix_recommendation"][
            "candidate_artifacts"
        ].append(copy.deepcopy(acceptance.CANDIDATE_VALUES))
        self.write_review()
        self.assert_error("candidate_artifacts_invalid", self.validate)

    def test_floor_reason_code_and_selected_threshold_drift_are_rejected(self) -> None:
        mutations = [
            (
                ("acceptance_floor_recommendation", "minimum_pair_precision_basis_points"),
                9_499,
                "acceptance_floor_invalid",
            ),
            (
                ("acceptance_floor_recommendation", "single_shared_threshold_required"),
                False,
                "acceptance_floor_invalid",
            ),
            (
                (
                    "acceptance_floor_recommendation",
                    "minimum_language_stratum_precision_basis_points",
                ),
                8_999,
                "acceptance_floor_invalid",
            ),
            (
                (
                    "acceptance_floor_recommendation",
                    "aggregate_averaging_forbidden",
                ),
                False,
                "acceptance_floor_invalid",
            ),
            (
                ("current_assessment", "reason_codes"),
                list(reversed(acceptance.REASON_CODES)),
                "reason_codes_invalid",
            ),
            (
                ("current_assessment", "selected_threshold_basis_points"),
                9_000,
                "assessment_invalid",
            ),
            (
                ("current_assessment", "acceptance_decision_eligible"),
                True,
                "assessment_invalid",
            ),
            (
                ("immutability", "record_state"),
                "open",
                "immutability_invalid",
            ),
        ]
        for path, value, code in mutations:
            with self.subTest(path=path):
                self.review = canonical_review()
                self.mutate(path, value)
                self.assert_error(code, self.validate)

    def test_missing_historical_report_is_allowed_but_present_drift_is_rejected(self) -> None:
        historical = self.root / acceptance.CANDIDATE_VALUES["historical_report_path"]
        self.assertFalse(historical.exists())
        self.validate()

        historical.parent.mkdir(parents=True)
        historical.write_bytes(b"drifted historical observation")
        self.assert_error("historical_report_hash_invalid", self.validate)

        historical.unlink()
        historical.symlink_to(self.review_path)
        self.assert_error("historical_report_type_invalid", self.validate)

    def test_summary_is_deterministic_content_free_and_has_closed_gates(self) -> None:
        summary = acceptance.build_summary(self.validate())
        self.assertEqual(summary["status"], "proposed_not_selected")
        self.assertFalse(summary["acceptance_decision_eligible"])
        self.assertTrue(all(value is False for value in summary["authorization"].values()))
        self.assertEqual(summary["approval_counts"]["selected_recommendation_count"], 0)
        self.assertTrue(summary["acceptance_floors"]["null_precision_fails"])
        self.assertTrue(
            summary["acceptance_floors"]["review_clusters_exact_match_required"]
        )
        self.assertTrue(summary["acceptance_floors"]["all_required_artifacts_must_pass"])
        self.assertTrue(summary["acceptance_floors"]["single_shared_threshold_required"])
        self.assertEqual(
            summary["acceptance_floors"][
                "minimum_language_stratum_predicted_positive_count"
            ],
            20,
        )
        self.assertEqual(
            summary["acceptance_floors"][
                "minimum_language_stratum_actual_positive_count"
            ],
            20,
        )
        self.assertTrue(
            summary["acceptance_floors"]["same_language_stratum_required"]
        )
        self.assertTrue(
            summary["acceptance_floors"]["cross_language_stratum_required"]
        )
        self.assertTrue(
            summary["acceptance_floors"]["hard_negative_stratum_required"]
        )
        self.assertTrue(
            summary["acceptance_floors"]["per_artifact_and_stratum_pass_required"]
        )
        self.assertTrue(
            summary["acceptance_floors"]["aggregate_averaging_forbidden"]
        )
        self.assertEqual(summary["current_review_threshold_basis_points"], 9_000)
        self.assertEqual(summary["target_matrix_counts"]["candidate_artifact_count"], 1)
        serialized = json.dumps(summary, sort_keys=True, separators=(",", ":"))
        for forbidden in (
            "Keep citations with each answer.",
            "offline_embedding",
            "artifact_fingerprint",
            "historical_report_path",
            "endpoint",
            "model_id",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_cli_success_and_failures_are_safe(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with mock.patch.object(acceptance, "ROOT", self.root):
                status = acceptance.main(["--review", str(self.review_path)])
        self.assertEqual(status, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(json.loads(stdout.getvalue()), acceptance.build_summary(self.review))
        self.assertEqual(
            stdout.getvalue(),
            json.dumps(
                acceptance.build_summary(self.review),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )

        secret = "payload-that-must-not-leak"
        malformed = self.root / secret
        malformed.write_bytes(b"{")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = acceptance.main(["--review", str(malformed)])
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "acceptance_review_error:review_json_invalid\n")
        self.assertNotIn(secret, stderr.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = acceptance.main(["--unknown", secret])
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "acceptance_review_error:arguments_invalid\n")
        self.assertNotIn(secret, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
