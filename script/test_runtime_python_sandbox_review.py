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


SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPT_DIR / "check_runtime_python_sandbox_review.py"
SPEC = importlib.util.spec_from_file_location(
    "check_runtime_python_sandbox_review", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
review_check = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review_check
SPEC.loader.exec_module(review_check)

SOURCE_ROOT = SCRIPT_DIR.parent
COPY_PATHS = [
    review_check.REVIEW_RELATIVE,
    review_check.MANIFEST_RELATIVE,
    review_check.REVIEW_MARKDOWN_RELATIVE,
    review_check.THREAT_MODEL_RELATIVE,
    review_check.STANDARDS_RELATIVE,
    *[Path(path) for path, _ in review_check.EXPECTED_EVIDENCE],
]


class RuntimePythonSandboxReviewTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for relative in COPY_PATHS:
            source = SOURCE_ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        self.review_path = self.root / review_check.REVIEW_RELATIVE
        self.canonical_review = json.loads(
            self.review_path.read_text(encoding="utf-8")
        )

    def review(self) -> dict[str, object]:
        return copy.deepcopy(self.canonical_review)

    def write_review(self, value: dict[str, object]) -> None:
        self.review_path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def assert_rejected(self, code: str) -> None:
        with self.assertRaises(review_check.PythonSandboxReviewError) as context:
            review_check.validate(self.root)
        self.assertEqual(context.exception.code, code)

    def assert_structure_rejected(self, value: dict[str, object], code: str) -> None:
        with self.assertRaises(review_check.PythonSandboxReviewError) as context:
            review_check._validate_review(value)
        self.assertEqual(context.exception.code, code)

    def test_canonical_closed_review_passes(self) -> None:
        review = review_check.validate(self.root)
        self.assertEqual(review["status"], "proposed_not_selected")
        self.assertFalse(review["current_assessment"]["execution_authorized"])
        self.assertFalse(review["current_behavior"]["python_protocol_namespace_active"])

    def test_duplicate_key_nonfinite_and_invalid_utf8_fail_closed(self) -> None:
        canonical = self.review_path.read_bytes()
        self.review_path.write_bytes(
            canonical.replace(
                b'  "schema_version": 1,',
                b'  "schema_version": 1,\n  "schema_version": 1,',
                1,
            )
        )
        self.assert_rejected("duplicate_json_key")

        self.review_path.write_bytes(
            canonical.replace(b'  "schema_version": 1,', b'  "schema_version": NaN,', 1)
        )
        self.assert_rejected("invalid_json_number")

        self.review_path.write_bytes(canonical + b"\xff")
        self.assert_rejected("review_json_invalid")

    def test_unknown_missing_and_reordered_contract_fields_fail(self) -> None:
        value = self.review()
        value["unknown"] = False
        self.write_review(value)
        self.assert_rejected("review_fields_invalid")

        value = self.review()
        del value["execution_status"]
        self.write_review(value)
        self.assert_rejected("review_fields_invalid")

        value = self.review()
        approval = value["approval_required"]
        assert isinstance(approval, dict)
        approval["required_before"] = list(reversed(approval["required_before"]))
        self.write_review(value)
        self.assert_rejected("approval_invalid")

    def test_bool_int_float_type_confusion_fails(self) -> None:
        value = self.review()
        approval = value["approval_required"]
        assert isinstance(approval, dict)
        approval["selected_recommendation_count"] = False
        self.write_review(value)
        self.assert_rejected("approval_invalid")

        value = self.review()
        resources = value["resource_recommendation"]
        assert isinstance(resources, dict)
        resources["cpu_time_seconds"] = 2.0
        self.write_review(value)
        self.assert_rejected("resources_invalid")

        value = self.review()
        source = value["source_evidence"]
        assert isinstance(source, dict)
        source["artifact_count"] = 6.0
        self.write_review(value)
        self.assert_rejected("source_evidence_invalid")

    def test_every_current_authorization_escalation_fails(self) -> None:
        canonical = self.review()
        current = canonical["current_behavior"]
        assert isinstance(current, dict)
        for key in list(current):
            with self.subTest(key=key):
                value = copy.deepcopy(canonical)
                mutated = value["current_behavior"]
                assert isinstance(mutated, dict)
                mutated[key] = True
                self.write_review(value)
                self.assert_rejected("authorization_escalated")

    def test_isolation_recommendation_mutations_fail(self) -> None:
        canonical = self.review()
        for mutate in (
            lambda section: section.__setitem__("status", "selected"),
            lambda section: section.__setitem__(
                "recommended_option_id", "plain_process_system_python"
            ),
            lambda section: section["options"].reverse(),
            lambda section: section["mandatory_properties"].pop(),
        ):
            value = copy.deepcopy(canonical)
            section = value["isolation_recommendation"]
            assert isinstance(section, dict)
            mutate(section)
            self.write_review(value)
            self.assert_rejected("isolation_invalid")

        value = copy.deepcopy(canonical)
        section = value["isolation_recommendation"]
        assert isinstance(section, dict)
        properties = section["mandatory_properties"]
        assert isinstance(properties, list)
        properties[6] = "inherited_file_descriptors_are_allowed"
        self.assert_structure_rejected(value, "isolation_invalid")

    def test_language_profile_and_resource_floor_mutations_fail(self) -> None:
        canonical = self.review()
        value = copy.deepcopy(canonical)
        language = value["language_profile_recommendation"]
        assert isinstance(language, dict)
        language["recommended_option_id"] = "unrestricted_python"
        self.write_review(value)
        self.assert_rejected("language_profile_invalid")

        value = copy.deepcopy(canonical)
        language = value["language_profile_recommendation"]
        assert isinstance(language, dict)
        contract = language["required_contract"]
        assert isinstance(contract, list)
        contract[1] = "unicode_display_controls_are_allowed"
        self.assert_structure_rejected(value, "language_profile_invalid")

        value = copy.deepcopy(canonical)
        resources = value["resource_recommendation"]
        assert isinstance(resources, dict)
        enforcement = resources["enforcement_requirements"]
        assert isinstance(enforcement, list)
        enforcement[2] = "execution_deadline_excludes_startup_and_parse"
        self.assert_structure_rejected(value, "resources_invalid")

        for key, replacement in (
            ("maximum_source_utf8_bytes", 1_000_000),
            ("wall_timeout_milliseconds", 30_000),
            ("maximum_child_processes", 1),
            ("maximum_file_size_bytes", 1),
        ):
            with self.subTest(key=key):
                value = copy.deepcopy(canonical)
                resources = value["resource_recommendation"]
                assert isinstance(resources, dict)
                resources[key] = replacement
                self.write_review(value)
                self.assert_rejected("resources_invalid")

    def test_permission_audit_and_lifecycle_mutations_fail(self) -> None:
        canonical = self.review()
        for key, replacement in (
            ("status", "selected"),
            ("standing_grants_authorized", True),
            ("remote_self_approval_authorized", True),
            ("proposed_decision", "remote_confirmation"),
        ):
            with self.subTest(key=key):
                value = copy.deepcopy(canonical)
                section = value["permission_and_audit_recommendation"]
                assert isinstance(section, dict)
                section[key] = replacement
                self.write_review(value)
                self.assert_rejected("permission_audit_invalid")

        value = copy.deepcopy(canonical)
        section = value["permission_and_audit_recommendation"]
        assert isinstance(section, dict)
        section["durable_audit_fields"].append("source_text")
        self.write_review(value)
        self.assert_rejected("permission_audit_invalid")

        value = copy.deepcopy(canonical)
        section = value["permission_and_audit_recommendation"]
        assert isinstance(section, dict)
        fields = section["durable_audit_fields"]
        assert isinstance(fields, list)
        fields[11] = "unbound_result_digest"
        self.assert_structure_rejected(value, "permission_audit_invalid")

        value = copy.deepcopy(canonical)
        section = value["permission_and_audit_recommendation"]
        assert isinstance(section, dict)
        bindings = section["approval_binding_fields"]
        assert isinstance(bindings, list)
        bindings[4] = "interpreter_only_execution_identity"
        self.assert_structure_rejected(value, "permission_audit_invalid")

        value = copy.deepcopy(canonical)
        section = value["permission_and_audit_recommendation"]
        assert isinstance(section, dict)
        lifecycle = section["lifecycle_requirements"]
        assert isinstance(lifecycle, list)
        lifecycle[7] = (
            "xpc_audit_token_and_exact_worker_code_identity_are_verified_"
            "before_reservation_and_rechecked_before_result_acceptance"
        )
        self.assert_structure_rejected(value, "permission_audit_invalid")

    def test_validation_assessment_and_immutability_mutations_fail(self) -> None:
        canonical = self.review()
        value = copy.deepcopy(canonical)
        validation = value["validation_recommendation"]
        assert isinstance(validation, dict)
        validation["implementation_ready"] = True
        self.write_review(value)
        self.assert_rejected("validation_invalid")

        value = copy.deepcopy(canonical)
        validation = value["validation_recommendation"]
        assert isinstance(validation, dict)
        evidence = validation["required_pre_execution_evidence"]
        assert isinstance(evidence, list)
        evidence[0] = "codesign_evidence_optional"
        self.assert_structure_rejected(value, "validation_invalid")

        value = copy.deepcopy(canonical)
        assessment = value["current_assessment"]
        assert isinstance(assessment, dict)
        assessment["execution_authorized"] = True
        self.write_review(value)
        self.assert_rejected("assessment_invalid")

        value = copy.deepcopy(canonical)
        immutability = value["immutability"]
        assert isinstance(immutability, dict)
        immutability["record_state"] = "mutable"
        self.write_review(value)
        self.assert_rejected("immutability_invalid")

    def test_review_symlink_fifo_empty_and_oversize_are_rejected(self) -> None:
        canonical = self.review_path.read_bytes()
        other = self.review_path.with_name("other.json")
        other.write_bytes(canonical)
        self.review_path.unlink()
        self.review_path.symlink_to(other.name)
        self.assert_rejected("review_type_invalid")

        self.review_path.unlink()
        os.mkfifo(self.review_path)
        self.assert_rejected("review_type_invalid")

        self.review_path.unlink()
        self.review_path.write_bytes(b"")
        self.assert_rejected("review_size_invalid")

        self.review_path.write_bytes(b"{" + b" " * review_check.MAXIMUM_REVIEW_BYTES + b"}")
        self.assert_rejected("review_size_invalid")

    def test_manifest_membership_hash_and_artifact_drift_are_rejected(self) -> None:
        manifest = self.root / review_check.MANIFEST_RELATIVE
        raw = manifest.read_bytes()
        manifest.write_bytes(raw.replace(b"Package.swift", b"README.md", 1))
        self.assert_rejected("manifest_digest_mismatch")

        manifest.write_bytes(raw)
        artifact = self.root / "Package.swift"
        artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assert_rejected("evidence_artifact_digest_mismatch")

    def test_manifest_and_evidence_symlinks_are_rejected(self) -> None:
        manifest = self.root / review_check.MANIFEST_RELATIVE
        copy = manifest.with_name("manifest-copy")
        copy.write_bytes(manifest.read_bytes())
        manifest.unlink()
        manifest.symlink_to(copy.name)
        self.assert_rejected("manifest_type_invalid")

        manifest.unlink()
        shutil.copy2(SOURCE_ROOT / review_check.MANIFEST_RELATIVE, manifest)
        package = self.root / "Package.swift"
        package_copy = self.root / "Package-copy.swift"
        package_copy.write_bytes(package.read_bytes())
        package.unlink()
        package.symlink_to(package_copy.name)
        self.assert_rejected("evidence_artifact_type_invalid")

    def test_human_documents_are_hash_pinned(self) -> None:
        document = self.root / review_check.THREAT_MODEL_RELATIVE
        document.write_text(
            document.read_text(encoding="utf-8") + "\nmutable\n",
            encoding="utf-8",
        )
        self.assert_rejected("design_document_digest_mismatch")

    def test_unreviewed_runner_target_is_rejected_without_source_execution(self) -> None:
        runner = self.root / "apps/macos/RuntimePythonSandbox"
        runner.mkdir(parents=True)
        (runner / "placeholder.txt").write_text("not executable\n", encoding="utf-8")
        self.assert_rejected("python_runner_target_present")

        shutil.rmtree(runner)
        hidden_source = (
            self.root
            / "apps/macos/CompanionCore/Sources/PythonBridge.swift"
        )
        hidden_source.write_text(
            'let bundledInterpreter = "python3"\n',
            encoding="utf-8",
        )
        self.assert_rejected("python_implementation_boundary_open")

        hidden_source.unlink()
        python_resource = (
            self.root
            / "apps/macos/LocalAgentBridgeApp/Sources/Resources/python3"
        )
        python_resource.parent.mkdir(parents=True, exist_ok=True)
        python_resource.write_text("#!/bin/sh\n", encoding="utf-8")
        python_resource.chmod(0o755)
        self.assert_rejected("python_implementation_boundary_open")

        python_resource.unlink()
        resource_target = self.root / "resource-target"
        resource_target.write_text("not executable\n", encoding="utf-8")
        resource_link = python_resource.parent / "worker-data"
        resource_link.symlink_to(resource_target)
        self.assert_rejected("macos_source_boundary_type_invalid")
        resource_link.unlink()

        resource_directory = python_resource.parent / "LinkedResources"
        resource_directory.symlink_to(
            resource_target.parent,
            target_is_directory=True,
        )
        self.assert_rejected("macos_source_boundary_type_invalid")
        resource_directory.unlink()

        companion = self.root / "apps/macos/CompanionCore"
        companion_copy = self.root / "apps/macos/CompanionCore-copy"
        companion.rename(companion_copy)
        companion.symlink_to(companion_copy.name, target_is_directory=True)
        self.assert_rejected("macos_source_boundary_type_invalid")
        companion.unlink()
        companion_copy.rename(companion)

        schema_path = self.root / "packages/protocol-schema/protocol.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["unreviewed-python-message"] = {"enum": ["python.future"]}
        schema_path.write_text(
            json.dumps(schema, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(review_check.PythonSandboxReviewError) as context:
            review_check._validate_source_boundary(self.root)
        self.assertEqual(context.exception.code, "python_protocol_namespace_active")

    def test_cli_failure_is_content_free(self) -> None:
        self.review_path.write_text("{}\n", encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = review_check.main(["--root", str(self.root)])
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "runtime_python_sandbox_review_invalid:review_fields_invalid\n")
        self.assertNotIn(str(self.root), stderr.getvalue())

        loop = self.root / "root-loop"
        loop.symlink_to(loop.name)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = review_check.main(["--root", str(loop)])
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "runtime_python_sandbox_review_invalid:root_invalid\n")
        self.assertNotIn(str(self.root), stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
