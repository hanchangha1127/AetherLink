#!/usr/bin/env python3
"""Validate the closed review-only runtime Python sandbox recommendation."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT_RELATIVE = Path("docs/security-hardening/runtime-python-sandbox-v1")
REVIEW_RELATIVE = DESIGN_ROOT_RELATIVE / "review-v1.json"
MANIFEST_RELATIVE = DESIGN_ROOT_RELATIVE / "evidence.sha256"
REVIEW_MARKDOWN_RELATIVE = DESIGN_ROOT_RELATIVE / "review-v1.md"
THREAT_MODEL_RELATIVE = DESIGN_ROOT_RELATIVE / "threat-model.md"
STANDARDS_RELATIVE = DESIGN_ROOT_RELATIVE / "standards.md"

MAXIMUM_REVIEW_BYTES = 128 * 1024
MAXIMUM_MANIFEST_BYTES = 32 * 1024
MAXIMUM_EVIDENCE_BYTES = 8 * 1024 * 1024
MAXIMUM_DOCUMENT_BYTES = 128 * 1024
MAXIMUM_MACOS_SOURCE_FILES = 4_096
MAXIMUM_MACOS_SOURCE_BYTES = 32 * 1024 * 1024
MAXIMUM_MACOS_SOURCE_MODULES = 128

EXPECTED_REVIEW_SHA256 = "c1968e19f546311e35422aaeeb5b5f5cd0ca3cd0e1dde289403da2cef213c571"
EXPECTED_MANIFEST_SHA256 = "d8e5f9de86d68aa17e6a6959d5c2b7d0b7e7e89e5b287c51e9aa49b40a2dc6aa"
EXPECTED_DOCUMENT_SHA256 = {
    REVIEW_MARKDOWN_RELATIVE: "3e2fc5892120a46522096f700ad4ca7cdb0516aa530f7e3a9ea8a8f6b308fc9a",
    THREAT_MODEL_RELATIVE: "24e63f129095b9ee57a4fd8e0a896dabe6b668397383bb274ef4b9f433435ef1",
    STANDARDS_RELATIVE: "3c43ed9fc2aa63e7d4eee8f6a19392c97d1eca3a814a4c79b5fd91e9618cdbdd",
}
EXPECTED_EVIDENCE = (
    ("Package.swift", "70a7f29ad2bf1929f4292b083d15007645be17dcb030f768593142bc51ce8b23"),
    (
        "apps/macos/CompanionCore/Sources/RuntimeHostApprovalCoordinator.swift",
        "50d42d6e38889f6f27ef1c6e2bd9990c0c67588bd3f9883d25f72ea30355825c",
    ),
    (
        "apps/macos/CompanionCore/Sources/RuntimePermissionPolicyRegistry.swift",
        "20534f4731ac9d92dfae270f8ce94a6458c208125622831b3cd092fac7889ef9",
    ),
    (
        "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift",
        "b7cf2a31f9df0ebdcfde1dcf80e51e7095c1b936bd03489cdd420f7be2ae1d9c",
    ),
    (
        "apps/macos/DocumentIngestion/Sources/DocumentTextExtractor.swift",
        "1c531dbf48e759f9c9754c1683d14c161b053a6fd989c1658f29f258c0025a2a",
    ),
    (
        "packages/protocol-schema/protocol.schema.json",
        "156023ebf025e361b6ac402d1d30a6203c054a130d381c9916b95557fd574ad4",
    ),
)

TOP_LEVEL_KEYS = {
    "schema_version", "document_type", "review_id", "status",
    "evidence_status", "execution_status", "source_evidence",
    "approval_required", "current_behavior", "isolation_recommendation",
    "language_profile_recommendation", "resource_recommendation",
    "permission_and_audit_recommendation", "validation_recommendation",
    "current_assessment", "immutability",
}
CURRENT_BEHAVIOR_KEYS = {
    "python_protocol_namespace_active", "python_action_registered",
    "python_runner_target_exists", "bundled_python_runtime_exists",
    "source_acquisition_authorized", "subprocess_execution_authorized",
    "xpc_service_execution_authorized", "filesystem_read_authorized",
    "filesystem_write_authorized", "network_authorized",
    "child_process_authorized", "dynamic_native_extension_authorized",
    "protocol_change_authorized",
}
RESOURCE_VALUES = {
    "maximum_source_utf8_bytes": 16_384,
    "maximum_input_json_bytes": 65_536,
    "maximum_result_json_bytes": 65_536,
    "maximum_stdout_bytes": 65_536,
    "maximum_stderr_bytes": 8_192,
    "wall_timeout_milliseconds": 3_000,
    "termination_cleanup_timeout_milliseconds": 1_000,
    "cpu_time_seconds": 2,
    "maximum_address_space_bytes": 268_435_456,
    "maximum_file_size_bytes": 0,
    "maximum_open_file_descriptors": 32,
    "maximum_child_processes": 0,
    "maximum_concurrent_executions": 1,
    "core_dump_bytes": 0,
    "hard_kill_grace_milliseconds": 250,
}
LIFECYCLE_REQUIREMENTS = (
    "durable_reservation_precedes_worker_start",
    "terminal_audit_precedes_result_publication",
    "restart_never_retries_reserved_or_outcome_unknown_work",
    "cancellation_that_wins_before_spawn_prevents_worker_creation",
    "cancellation_invalidates_xpc_terminates_the_exact_audit_token_bound_worker_instance_and_suppresses_late_results",
    "authority_or_policy_drift_before_reservation_prevents_execution",
    "authority_policy_execution_closure_or_worker_identity_drift_after_reservation_terminates_the_exact_worker_and_suppresses_publication",
    "xpc_audit_token_and_exact_worker_code_identity_are_verified_after_reservation_before_untrusted_request_handoff_and_rechecked_before_result_acceptance",
    "python_uses_a_separate_single_execution_lane_with_bounded_fairness_and_does_not_reuse_the_model_pull_global_slot_implicitly",
    "termination_cleanup_deadline_breach_records_cleanup_failed_blocks_the_python_lane_and_never_publishes",
    "storage_degradation_blocks_new_intake_until_recovery",
)
TERMINAL_EVENTS = [
    "succeeded", "cancelled", "timed_out", "cpu_limit", "memory_limit",
    "output_limit", "sandbox_violation", "worker_crashed", "invalid_result",
    "internal_failure", "cleanup_failed", "result_suppressed",
]
ISOLATION_PROPERTIES = (
    "xpc_service_has_its_own_app_sandbox_and_no_network_entitlements",
    "xpc_service_has_no_app_group_keychain_user_selected_file_or_automation_entitlements",
    "one_shot_xpc_worker_contains_a_pinned_signed_embedded_cpython_artifact_loaded_before_untrusted_source",
    "xpc_worker_accepts_exactly_one_approved_operation_and_exits_without_launching_an_interpreter_process",
    "untrusted_worker_and_python_have_zero_child_process_authority",
    "app_sandbox_is_not_claimed_to_enforce_executable_identity_after_native_compromise",
    "all_inherited_file_descriptors_except_bounded_ipc_are_closed",
    "environment_is_rebuilt_from_an_exact_allowlist",
    "worker_stdin_is_closed_and_request_data_arrives_only_as_bounded_ipc",
    "writable_helper_state_is_untrusted_and_reset_before_each_operation",
    "sandbox_or_reset_verification_failure_blocks_execution",
    "interpreter_starts_with_pinned_equivalent_of_python_I_S_B_before_untrusted_source",
    "python_audit_hooks_are_observability_only_not_the_security_boundary",
)
LANGUAGE_REQUIRED_CONTRACT = (
    "source_is_utf8_nfc_and_bound_to_the_approval_digest",
    "source_rejects_bidi_controls_default_ignorables_and_non_ascii_line_separators_before_digest_and_display",
    "no_import_exec_eval_compile_dunder_or_dynamic_attribute_surface",
    "only_versioned_allowlisted_syntax_builtins_and_value_types",
    "no_clock_random_environment_locale_filesystem_network_process_or_clipboard_input",
    "locale_timezone_and_hash_seed_are_fixed_by_the_versioned_profile",
    "input_and_output_are_closed_versioned_json_values",
    "json_rejects_duplicate_keys_nonfinite_numbers_excess_depth_excess_items_and_bool_number_confusion",
    "all_worker_output_is_untrusted_data_and_never_log_control_text",
    "profile_validation_is_defense_in_depth_inside_the_os_sandbox",
)
RESOURCE_ENFORCEMENT_REQUIREMENTS = (
    "hard_limits_are_installed_before_untrusted_source_is_parsed_or_executed",
    "approval_expiry_execution_deadline_and_cleanup_deadline_are_separate_authorities",
    "one_host_monotonic_execution_deadline_covers_xpc_handoff_startup_execution_and_result_parse_for_normal_completion",
    "a_separate_host_monotonic_termination_cleanup_deadline_covers_grace_hard_kill_pipe_drain_xpc_invalidation_reap_and_scratch_cleanup",
    "stdout_and_stderr_are_drained_under_independent_byte_ceilings",
    "timeout_cancel_output_overflow_or_limit_failure_invalidates_xpc_terminates_the_exact_audit_token_bound_worker_and_suppresses_output",
    "every_terminal_audit_except_cleanup_failed_waits_for_pipe_drain_xpc_invalidation_process_reap_and_scratch_cleanup",
    "unsupported_or_ineffective_platform_limit_blocks_execution",
    "termination_cleanup_deadline_breach_records_cleanup_failed_blocks_the_python_lane_and_never_publishes",
    "resource_measurements_never_authorize_a_larger_limit_automatically",
)
APPROVAL_BINDING_FIELDS = (
    "action_and_policy_revision",
    "authenticated_connection_request_and_generation",
    "trusted_device_key_and_transport_binding",
    "language_profile_revision",
    "execution_closure_digest",
    "xpc_worker_executable_digest",
    "xpc_worker_designated_requirement_digest",
    "xpc_worker_entitlement_digest",
    "interpreter_artifact_digest",
    "exact_source_digest",
    "exact_input_digest",
    "exact_resource_limits",
)
APPROVAL_DISPLAY_REQUIREMENTS = (
    "exact_source_text_is_visible_only_in_the_ephemeral_host_review",
    "input_is_presented_as_a_bounded_safe_summary_with_an_exact_digest",
    "interpreter_worker_identity_profile_and_resource_limits_are_visible_before_confirmation",
    "source_viewer_uses_line_numbers_visible_whitespace_and_token_aware_unicode_escapes_bound_to_the_exact_source_digest",
    "approval_display_content_is_never_written_to_the_durable_audit",
)
DURABLE_AUDIT_FIELDS = (
    "operation_id", "action_id", "policy_revision", "profile_revision",
    "execution_closure_digest", "worker_identity_digest",
    "interpreter_artifact_digest", "source_digest", "input_digest",
    "resource_limit_digest", "result_schema_revision",
    "canonical_result_digest", "publication_envelope_digest", "event_code",
    "occurred_at",
)
DURABLE_AUDIT_FORBIDDEN_FIELDS = (
    "source_text", "input_values", "stdout", "stderr", "result_values",
    "environment_values", "filesystem_paths", "credentials",
)
VALIDATION_PRE_EXECUTION_EVIDENCE = (
    "codesign_and_entitlement_identity_is_exact_for_host_service_and_worker",
    "filesystem_read_write_network_dns_keychain_clipboard_automation_and_process_escape_attempts_fail",
    "environment_file_descriptor_and_writable_state_inheritance_are_absent",
    "cpu_memory_wall_output_file_descriptor_process_and_core_limits_fail_closed",
    "crash_hang_cancel_restart_and_result_race_tests_preserve_exactly_once_audit_semantics",
    "python_lane_fairness_and_model_pull_non_starvation_are_proven_under_long_running_work",
    "interpreter_bundle_sbom_signature_digest_and_update_rollback_policy_are_pinned",
    "embedded_cpython_load_path_and_absence_of_an_interpreter_child_process_are_proven",
    "post_compromise_exec_attempts_retain_sandbox_resource_and_bounded_untrusted_result_channel_authority_without_claiming_exec_allowlisting",
    "xpc_audit_token_exact_code_identity_and_worker_instance_drift_cancel_before_result_acceptance",
    "adversarial_language_profile_mutations_fail_before_worker_start",
    "reserved_python_protocol_messages_remain_rejected_until_a_separate_protocol_decision",
)
APPROVAL_UNRESOLVED_INPUTS = (
    "adversarial_escape_test_harness",
    "approval_execution_lane_and_fairness_contract",
    "approval_preview_and_audit_contract",
    "bundled_cpython_supply_chain",
    "resource_limit_portability",
    "restricted_language_contract",
    "sandbox_entitlement_profile",
    "termination_and_cancellation_contract",
    "xpc_packaging_and_codesigning",
)
APPROVAL_REQUIRED_BEFORE = (
    "acquire_or_bundle_python_artifact",
    "activate_python_protocol_namespace",
    "add_python_permission_action",
    "create_python_runner_target",
    "execute_python_source",
    "grant_child_process_access",
    "grant_file_access",
    "grant_network_access",
    "physical_or_live_validation",
)
ASSESSMENT_REASON_CODES = (
    "explicit_design_selection_missing",
    "execution_lane_and_cancellation_not_frozen",
    "interpreter_supply_chain_unselected",
    "language_profile_not_frozen",
    "sandbox_packaging_not_proven",
    "escape_and_resource_matrix_not_run",
)

PYTHON_IMPLEMENTATION_MARKERS = (
    b"python_deterministic_calculation_v1",
    b"isolated_code_execution",
    b"RuntimePythonSandbox",
    b"PythonSandboxRunner",
    b"Py_Initialize",
    b"PyRun_",
    b"PythonKit",
    b"libpython",
    b"/usr/bin/python",
    b"python3",
)
PYTHON_ARTIFACT_SUFFIXES = {
    ".a", ".dylib", ".py", ".pyc", ".pyo", ".so", ".whl", ".zip",
}
EXECUTABLE_FILE_MAGICS = (
    b"#!",
    b"\x7fELF",
    b"MZ",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
)


class PythonSandboxReviewError(Exception):
    """A validation failure carrying only a stable content-free code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise PythonSandboxReviewError("arguments_invalid")


def _fail(code: str) -> None:
    raise PythonSandboxReviewError(code)


def _read_regular(path: Path, maximum_bytes: int, code: str) -> bytes:
    try:
        metadata = path.lstat()
    except OSError:
        raise PythonSandboxReviewError(code + "_unreadable") from None
    if not stat.S_ISREG(metadata.st_mode):
        _fail(code + "_type_invalid")
    if metadata.st_size <= 0 or metadata.st_size > maximum_bytes:
        _fail(code + "_size_invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            _fail(code + "_type_invalid")
        raise PythonSandboxReviewError(code + "_unreadable") from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            _fail(code + "_type_invalid")
        if (metadata.st_dev, metadata.st_ino) != (opened.st_dev, opened.st_ino):
            _fail(code + "_changed_during_read")
        if (
            metadata.st_size != opened.st_size
            or metadata.st_mtime_ns != opened.st_mtime_ns
            or metadata.st_ctime_ns != opened.st_ctime_ns
        ):
            _fail(code + "_changed_during_read")
        if opened.st_size <= 0 or opened.st_size > maximum_bytes:
            _fail(code + "_size_invalid")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(128 * 1024, maximum_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                _fail(code + "_size_invalid")
            chunks.append(chunk)
        finished = os.fstat(descriptor)
        if (
            (opened.st_dev, opened.st_ino) != (finished.st_dev, finished.st_ino)
            or opened.st_size != finished.st_size
            or opened.st_mtime_ns != finished.st_mtime_ns
            or opened.st_ctime_ns != finished.st_ctime_ns
            or total != finished.st_size
        ):
            _fail(code + "_changed_during_read")
    except OSError:
        raise PythonSandboxReviewError(code + "_unreadable") from None
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if not raw:
        _fail(code + "_size_invalid")
    return raw


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    del value
    _fail("invalid_json_number")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        _fail("invalid_json_number")
    return parsed


def _strict_json(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise PythonSandboxReviewError("review_json_invalid") from None
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
            parse_float=_finite_float,
        )
    except PythonSandboxReviewError:
        raise
    except (json.JSONDecodeError, OverflowError, RecursionError, ValueError):
        raise PythonSandboxReviewError("review_json_invalid") from None


def _object(value: Any, code: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(code)
    return value


def _exact(value: Any, expected: Any, code: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _fail(code)


def _keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        _fail(code)


def _string_list(value: Any, code: str) -> list[str]:
    if type(value) is not list or not value or any(type(item) is not str or not item for item in value):
        _fail(code)
    if len(set(value)) != len(value):
        _fail(code)
    return value


def _validate_review(review: Any) -> dict[str, Any]:
    review = _object(review, "review_type_invalid")
    _keys(review, TOP_LEVEL_KEYS, "review_fields_invalid")
    identities = {
        "schema_version": 1,
        "document_type": "aetherlink.runtime-python-sandbox-review",
        "review_id": "runtime_python_sandbox_v1_recommended",
        "status": "proposed_not_selected",
        "evidence_status": "static_review_complete",
        "execution_status": "not_started",
    }
    for key, expected in identities.items():
        _exact(review[key], expected, "review_identity_invalid")

    source = _object(review["source_evidence"], "source_evidence_invalid")
    expected_source = {
        "manifest_path": MANIFEST_RELATIVE.as_posix(),
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "artifact_count": 6,
        "source_drift": "absent",
    }
    if source != expected_source or any(type(source[k]) is not type(v) for k, v in expected_source.items()):
        _fail("source_evidence_invalid")

    approval = _object(review["approval_required"], "approval_invalid")
    _keys(approval, {
        "decision_id", "approval_source", "selected_recommendation_count",
        "explicit_user_approval_required", "decision_boundary",
        "unresolved_inputs", "required_before",
    }, "approval_invalid")
    for key, expected in {
        "decision_id": None,
        "approval_source": None,
        "selected_recommendation_count": 0,
        "explicit_user_approval_required": True,
        "decision_boundary": "separate_versioned_decision_before_any_executable_or_protocol_change",
    }.items():
        _exact(approval[key], expected, "approval_invalid")
    unresolved = _string_list(approval["unresolved_inputs"], "approval_invalid")
    required_before = _string_list(approval["required_before"], "approval_invalid")
    if unresolved != list(APPROVAL_UNRESOLVED_INPUTS) or required_before != list(APPROVAL_REQUIRED_BEFORE):
        _fail("approval_invalid")

    current = _object(review["current_behavior"], "current_behavior_invalid")
    _keys(current, CURRENT_BEHAVIOR_KEYS, "current_behavior_invalid")
    for value in current.values():
        _exact(value, False, "authorization_escalated")

    isolation = _object(review["isolation_recommendation"], "isolation_invalid")
    _keys(isolation, {"status", "recommended_option_id", "options", "mandatory_properties"}, "isolation_invalid")
    _exact(isolation["status"], "proposed_not_selected", "isolation_invalid")
    _exact(isolation["recommended_option_id"], "app_sandbox_xpc_bundled_python", "isolation_invalid")
    options = isolation["options"]
    _exact(options, [
        {
            "option_id": "in_process_subinterpreter",
            "disposition": "rejected",
            "reason_codes": [
                "shared_process_memory_and_file_descriptors",
                "interpreter_failure_can_terminate_runtime_host",
                "no_os_privilege_separation",
            ],
        },
        {
            "option_id": "plain_process_system_python",
            "disposition": "rejected",
            "reason_codes": [
                "host_interpreter_identity_not_pinned",
                "process_boundary_does_not_create_app_sandbox",
                "ambient_environment_and_filesystem_authority",
            ],
        },
        {
            "option_id": "app_sandbox_xpc_bundled_python",
            "disposition": "recommended",
            "reason_codes": [
                "independent_minimum_privilege_sandbox",
                "pinned_signed_interpreter_artifact",
                "one_shot_failure_and_state_isolation",
            ],
        },
    ], "isolation_invalid")
    properties = _string_list(isolation["mandatory_properties"], "isolation_invalid")
    if properties != list(ISOLATION_PROPERTIES):
        _fail("isolation_invalid")

    language = _object(review["language_profile_recommendation"], "language_profile_invalid")
    _keys(language, {"status", "profile_id", "recommended_option_id", "options", "required_contract"}, "language_profile_invalid")
    for key, expected in {
        "status": "proposed_not_selected",
        "profile_id": "deterministic_calculation_v1",
        "recommended_option_id": "restricted_profile_inside_os_sandbox",
    }.items():
        _exact(language[key], expected, "language_profile_invalid")
    _exact(language["options"], [
        {"option_id": "unrestricted_python", "disposition": "rejected"},
        {"option_id": "static_ast_only_without_os_sandbox", "disposition": "rejected"},
        {"option_id": "restricted_profile_inside_os_sandbox", "disposition": "recommended"},
    ], "language_profile_invalid")
    contract = _string_list(language["required_contract"], "language_profile_invalid")
    if contract != list(LANGUAGE_REQUIRED_CONTRACT):
        _fail("language_profile_invalid")

    resources = _object(review["resource_recommendation"], "resources_invalid")
    expected_resource_keys = {"status", "enforcement_requirements", *RESOURCE_VALUES.keys()}
    _keys(resources, expected_resource_keys, "resources_invalid")
    _exact(resources["status"], "proposed_not_selected", "resources_invalid")
    for key, expected in RESOURCE_VALUES.items():
        _exact(resources[key], expected, "resources_invalid")
    enforcement = _string_list(resources["enforcement_requirements"], "resources_invalid")
    if enforcement != list(RESOURCE_ENFORCEMENT_REQUIREMENTS):
        _fail("resources_invalid")

    permission = _object(review["permission_and_audit_recommendation"], "permission_audit_invalid")
    expected_permission_keys = {
        "status", "proposed_action_id", "proposed_protocol_message_id",
        "proposed_effect", "proposed_decision", "proposed_audit",
        "standing_grants_authorized", "remote_self_approval_authorized",
        "approval_binding_fields", "approval_display_requirements",
        "durable_audit_fields", "durable_audit_forbidden_fields",
        "terminal_event_codes", "lifecycle_requirements",
    }
    _keys(permission, expected_permission_keys, "permission_audit_invalid")
    for key, expected in {
        "status": "proposed_not_selected",
        "proposed_action_id": "python_deterministic_calculation_v1",
        "proposed_protocol_message_id": "python.run",
        "proposed_effect": "isolated_code_execution",
        "proposed_decision": "host_explicit_approval_each_run",
        "proposed_audit": "durable_redacted_required",
        "standing_grants_authorized": False,
        "remote_self_approval_authorized": False,
    }.items():
        _exact(permission[key], expected, "permission_audit_invalid")
    exact_permission_lists = {
        "approval_binding_fields": APPROVAL_BINDING_FIELDS,
        "approval_display_requirements": APPROVAL_DISPLAY_REQUIREMENTS,
        "durable_audit_fields": DURABLE_AUDIT_FIELDS,
        "durable_audit_forbidden_fields": DURABLE_AUDIT_FORBIDDEN_FIELDS,
        "lifecycle_requirements": LIFECYCLE_REQUIREMENTS,
    }
    for key, expected in exact_permission_lists.items():
        values = _string_list(permission[key], "permission_audit_invalid")
        if values != list(expected):
            _fail("permission_audit_invalid")
    if set(permission["durable_audit_fields"]).intersection(permission["durable_audit_forbidden_fields"]):
        _fail("permission_audit_invalid")
    if permission["terminal_event_codes"] != TERMINAL_EVENTS:
        _fail("permission_audit_invalid")

    validation = _object(review["validation_recommendation"], "validation_invalid")
    _keys(validation, {
        "status", "required_pre_execution_evidence",
        "no_device_static_review_is_execution_proof",
        "live_sandbox_escape_matrix_complete", "implementation_ready",
    }, "validation_invalid")
    _exact(validation["status"], "proposed_not_selected", "validation_invalid")
    evidence = _string_list(validation["required_pre_execution_evidence"], "validation_invalid")
    if evidence != list(VALIDATION_PRE_EXECUTION_EVIDENCE):
        _fail("validation_invalid")
    for key in ("no_device_static_review_is_execution_proof", "live_sandbox_escape_matrix_complete", "implementation_ready"):
        _exact(validation[key], False, "validation_invalid")

    assessment = _object(review["current_assessment"], "assessment_invalid")
    _keys(assessment, {
        "recommended_design_available", "design_selection_eligible",
        "implementation_authorized", "execution_authorized",
        "protocol_activation_authorized", "reason_codes",
    }, "assessment_invalid")
    _exact(assessment["recommended_design_available"], True, "assessment_invalid")
    _exact(assessment["design_selection_eligible"], True, "assessment_invalid")
    for key in ("implementation_authorized", "execution_authorized", "protocol_activation_authorized"):
        _exact(assessment[key], False, "assessment_invalid")
    reasons = _string_list(assessment["reason_codes"], "assessment_invalid")
    if reasons != list(ASSESSMENT_REASON_CODES):
        _fail("assessment_invalid")
    immutability = _object(review["immutability"], "immutability_invalid")
    if immutability != {"record_state": "closed", "amendment_policy": "supersede_with_new_versioned_review"}:
        _fail("immutability_invalid")
    return review


def _validate_manifest(root: Path) -> None:
    raw = _read_regular(root / MANIFEST_RELATIVE, MAXIMUM_MANIFEST_BYTES, "manifest")
    if hashlib.sha256(raw).hexdigest() != EXPECTED_MANIFEST_SHA256:
        _fail("manifest_digest_mismatch")
    if not raw.endswith(b"\n"):
        _fail("manifest_format_invalid")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError:
        raise PythonSandboxReviewError("manifest_format_invalid") from None
    pattern = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9._/-]+)$")
    entries = []
    seen = set()
    for line in lines:
        match = pattern.fullmatch(line)
        if match is None:
            _fail("manifest_format_invalid")
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative in seen:
            _fail("manifest_path_invalid")
        seen.add(relative)
        entries.append((relative, digest))
    if entries != list(EXPECTED_EVIDENCE):
        _fail("manifest_membership_invalid")
    for relative, expected_digest in EXPECTED_EVIDENCE:
        raw_artifact = _read_regular(root / relative, MAXIMUM_EVIDENCE_BYTES, "evidence_artifact")
        if hashlib.sha256(raw_artifact).hexdigest() != expected_digest:
            _fail("evidence_artifact_digest_mismatch")


def _validate_documents(root: Path) -> None:
    snippets = {
        REVIEW_MARKDOWN_RELATIVE: (
            "`runtime_python_sandbox_v1_recommended` is `proposed_not_selected`",
            "separately signed, minimum-privilege, one-shot XPC worker",
            "App Sandbox is not an executable-identity allowlist",
            "select the review requirements only",
            "active `python.*` protocol message",
        ),
        THREAT_MODEL_RELATIVE: (
            "No untrusted Python executes in the runtime host process.",
            "App Sandbox and code-signing identity form the primary containment boundary",
            "audit-token-bound worker instance",
            "Static no-device review does not demonstrate",
        ),
        STANDARDS_RELATIVE: (
            "https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox",
            "https://developer.apple.com/documentation/xpc",
            "https://docs.python.org/3/using/cmdline.html",
            "https://docs.python.org/3/library/sys.html#sys.addaudithook",
            "https://pubs.opengroup.org/onlinepubs/7908799/xsh/getrlimit.html",
            "https://www.unicode.org/reports/tr9/",
        ),
    }
    for relative, expected_digest in EXPECTED_DOCUMENT_SHA256.items():
        raw = _read_regular(root / relative, MAXIMUM_DOCUMENT_BYTES, "design_document")
        if hashlib.sha256(raw).hexdigest() != expected_digest:
            _fail("design_document_digest_mismatch")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise PythonSandboxReviewError("design_document_utf8_invalid") from None
        if any(snippet not in text for snippet in snippets[relative]):
            _fail("design_document_contract_missing")


def _validate_source_boundary(root: Path) -> None:
    source_paths = (
        "Package.swift",
        "apps/macos/CompanionCore/Sources/RuntimePermissionPolicyRegistry.swift",
        "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift",
        "packages/protocol-schema/protocol.schema.json",
    )
    for relative in source_paths:
        raw = _read_regular(root / relative, MAXIMUM_EVIDENCE_BYTES, "source_boundary")
        if any(marker in raw for marker in PYTHON_IMPLEMENTATION_MARKERS):
            _fail("python_implementation_boundary_open")

    macos_root = root / "apps/macos"
    try:
        with os.scandir(macos_root) as entries:
            modules = sorted(entries, key=lambda entry: entry.name)
    except OSError:
        raise PythonSandboxReviewError("macos_source_boundary_unreadable") from None
    if len(modules) > MAXIMUM_MACOS_SOURCE_MODULES:
        _fail("macos_source_boundary_limit_exceeded")
    source_file_count = 0
    source_byte_count = 0
    for module in modules:
        if module.is_symlink():
            _fail("macos_source_boundary_type_invalid")
        if not module.is_dir(follow_symlinks=False):
            continue
        sources = Path(module.path) / "Sources"
        try:
            source_metadata = sources.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise PythonSandboxReviewError("macos_source_boundary_unreadable") from None
        if not stat.S_ISDIR(source_metadata.st_mode):
            _fail("macos_source_boundary_type_invalid")
        def reject_walk_error(error: OSError) -> None:
            del error
            raise PythonSandboxReviewError("macos_source_boundary_unreadable")

        for directory, directory_names, file_names in os.walk(
            sources,
            followlinks=False,
            onerror=reject_walk_error,
        ):
            safe_directories = []
            for name in sorted(directory_names):
                candidate = Path(directory) / name
                try:
                    candidate_metadata = candidate.lstat()
                except OSError:
                    raise PythonSandboxReviewError("macos_source_boundary_unreadable") from None
                if stat.S_ISLNK(candidate_metadata.st_mode):
                    _fail("macos_source_boundary_type_invalid")
                if stat.S_ISDIR(candidate_metadata.st_mode):
                    if "python" in name.lower():
                        _fail("python_implementation_boundary_open")
                    safe_directories.append(name)
            directory_names[:] = safe_directories
            for name in sorted(file_names):
                source_file_count += 1
                if source_file_count > MAXIMUM_MACOS_SOURCE_FILES:
                    _fail("macos_source_boundary_limit_exceeded")
                artifact = Path(directory) / name
                try:
                    artifact_metadata = artifact.lstat()
                except OSError:
                    raise PythonSandboxReviewError("macos_source_boundary_unreadable") from None
                if not stat.S_ISREG(artifact_metadata.st_mode):
                    _fail("macos_source_boundary_type_invalid")
                raw = _read_regular(
                    artifact,
                    MAXIMUM_EVIDENCE_BYTES,
                    "macos_source_artifact",
                )
                source_byte_count += len(raw)
                if source_byte_count > MAXIMUM_MACOS_SOURCE_BYTES:
                    _fail("macos_source_boundary_limit_exceeded")
                lower_name = name.lower()
                if (
                    "python" in lower_name
                    or artifact.suffix.lower() in PYTHON_ARTIFACT_SUFFIXES
                    or artifact_metadata.st_mode & 0o111
                    or any(raw.startswith(magic) for magic in EXECUTABLE_FILE_MAGICS)
                ):
                    _fail("python_implementation_boundary_open")
                if any(marker in raw for marker in PYTHON_IMPLEMENTATION_MARKERS):
                    _fail("python_implementation_boundary_open")

    schema = _read_regular(root / "packages/protocol-schema/protocol.schema.json", MAXIMUM_EVIDENCE_BYTES, "schema")
    schema_document = _strict_json(schema)
    pending = [schema_document]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
        elif type(value) is str and value.startswith("python."):
            _fail("python_protocol_namespace_active")
    if re.search(br'"python\.[^"\\]*"', schema):
        _fail("python_protocol_namespace_active")
    for relative in ("apps/macos/RuntimePythonSandbox", "apps/macos/PythonSandboxRunner"):
        if (root / relative).exists():
            _fail("python_runner_target_present")


def validate(root: Path = ROOT, review_path: Optional[Path] = None) -> dict[str, Any]:
    try:
        root = root.resolve()
    except (OSError, RuntimeError):
        raise PythonSandboxReviewError("root_invalid") from None
    path = review_path if review_path is not None else root / REVIEW_RELATIVE
    raw = _read_regular(path, MAXIMUM_REVIEW_BYTES, "review")
    review = _validate_review(_strict_json(raw))
    if hashlib.sha256(raw).hexdigest() != EXPECTED_REVIEW_SHA256:
        _fail("review_digest_mismatch")
    _validate_manifest(root)
    _validate_documents(root)
    _validate_source_boundary(root)
    return review


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--review", type=Path)
    try:
        arguments = parser.parse_args(argv)
        review_path = arguments.review
        if review_path is not None and not review_path.is_absolute():
            review_path = arguments.root / review_path
        review = validate(arguments.root, review_path)
    except PythonSandboxReviewError as error:
        print("runtime_python_sandbox_review_invalid:" + error.code, file=sys.stderr)
        return 1
    print(
        "Runtime Python sandbox review valid: " + review["status"]
        + "; recommended=app_sandbox_xpc_bundled_python; "
        + "execution_authorized=false; protocol_active=false; artifacts=6"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
