#!/usr/bin/env python3
"""Mutation tests for the Phase A libjuice offline-source intake validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from script import check_p2p_nat_libjuice_offline_source as CHECKER
from script import check_p2p_nat_security_design as SECURITY_CHECKER


ROOT = Path(__file__).resolve().parents[1]


def replace_once(raw, old, new):
    before, separator, after = raw.partition(old)
    if not separator:
        raise AssertionError("replacement marker missing")
    return before + new + after


class LibjuiceOfflineSourceIntakeMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = CHECKER.load_json(CHECKER.ARTIFACT_JSON_PATH)

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.OfflineSourceValidationError):
            CHECKER.validate_document(candidate)

    def test_canonical_blocked_absent_state_and_checker_pass(self) -> None:
        CHECKER.validate_expected_intake_ancestors()
        CHECKER.validate_intake_root_absent()
        CHECKER.validate_source_documents()
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_owned_python_ast()
        CHECKER.validate_artifact_hashes()
        self.assertEqual(0, CHECKER.main())

    def test_duplicate_names_nonstandard_numbers_and_invalid_json_fail(self) -> None:
        raw = CHECKER.ARTIFACT_JSON_PATH.read_text(encoding="utf-8")
        duplicate_root = replace_once(
            raw,
            '  "artifactStatus": "blocked_missing_offline_source",',
            '  "artifactStatus": "complete",\n  "artifactStatus": "blocked_missing_offline_source",',
        )
        duplicate_nested = replace_once(
            raw,
            '    "sourceExecutionAllowed": false,',
            '    "sourceExecutionAllowed": true,\n    "sourceExecutionAllowed": false,',
        )
        for candidate in (duplicate_root, duplicate_nested, '{"value": NaN}', "{"):
            with self.subTest(candidate=candidate[:48]):
                with self.assertRaises(CHECKER.OfflineSourceValidationError):
                    CHECKER.parse_json(candidate, "mutation")

    def test_top_level_missing_unknown_and_scalar_drift_fail(self) -> None:
        self.assert_rejected(lambda value: value.pop("authorization"))
        self.assert_rejected(lambda value: value.update({"download": {}}))
        for key, mutation in (
            ("documentType", "other"),
            ("schemaVersion", 1.0),
            ("artifactId", "v2"),
            ("profileId", "other"),
            ("artifactStatus", "source_ready"),
            ("sourcePresence", "present"),
            ("auditStatus", "complete"),
            ("compileStatus", "passed"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation: value.update({key: mutation})
                )

    def test_exact_source_chain_rejects_path_id_and_hash_drift(self) -> None:
        cases = (
            ("sourceReview", "path", "../review-v2.json"),
            ("sourceReview", "reviewId", "other"),
            ("sourceReview", "sha256", "0" * 64),
            ("sourceDecision", "path", "../decision-v2.json"),
            ("sourceDecision", "decisionId", "other"),
            ("sourceDecision", "sha256", "1" * 64),
            ("sourceHandoff", "path", "../../implementation/handoff-v3.json"),
            ("sourceHandoff", "handoffId", "other"),
            ("sourceHandoff", "sha256", "f" * 64),
        )
        for parent, key, mutation in cases:
            with self.subTest(parent=parent, key=key):
                self.assert_rejected(
                    lambda value, parent=parent, key=key, mutation=mutation:
                    value[parent].update({key: mutation})
                )

    def test_candidate_version_tag_commit_and_official_url_policy_are_exact(self) -> None:
        for key, mutation in (
            ("candidateId", "libjuice-main"),
            ("project", "other"),
            ("version", "1.7.3"),
            ("releaseTag", "main"),
            ("commitSha1", "0" * 40),
            ("licenseCandidateSpdx", "UNKNOWN"),
            ("officialUrlUse", "fetch_allowed"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["candidate"].update({key: mutation})
                )
        for key in ("repository", "releaseTag", "archive"):
            with self.subTest(url=key):
                self.assert_rejected(
                    lambda value, key=key:
                    value["candidate"]["officialUrls"].update({key: "https://example.invalid/source"})
                )

    def test_every_authorization_bit_rejects_type_or_value_drift(self) -> None:
        for key, expected in CHECKER.EXPECTED_AUTHORIZATION.items():
            with self.subTest(key=key, case="flip"):
                self.assert_rejected(
                    lambda value, key=key, expected=expected:
                    value["authorization"].update({key: not expected})
                )
            with self.subTest(key=key, case="integer"):
                self.assert_rejected(
                    lambda value, key=key, expected=expected:
                    value["authorization"].update({key: int(expected)})
                )
        self.assert_rejected(lambda value: value["authorization"].pop("urlFetchAllowed"))
        self.assert_rejected(
            lambda value: value["authorization"].update({"dnsResolutionAllowed": False})
        )

    def test_intake_policy_rejects_symlink_glob_consumption_and_schema_drift(self) -> None:
        for key in (
            "absolutePathsAllowed", "parentTraversalAllowed", "backslashPathsAllowed",
            "emptyPathSegmentsAllowed", "symlinksAllowed", "hardlinksAllowed",
            "specialFilesAllowed", "archiveExtractionByCheckerAllowed",
            "generatedManifestByCheckerAllowed",
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key: value["intakePolicy"].update({key: True})
                )
        for key, mutation in (
            ("discoveryMode", "recursive_glob"),
            ("rootPresentDisposition", "inspect_existing_root"),
            ("checkerRootBehavior", "consume_if_present"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["intakePolicy"].update({key: mutation})
                )
        self.assert_rejected(lambda value: value["intakePolicy"].pop("symlinksAllowed"))
        self.assert_rejected(lambda value: value["intakePolicy"].update({"globAllowed": False}))

    def test_path_validator_rejects_absolute_traversal_backslash_and_empty_segments(self) -> None:
        rejected_paths = (
            "/tmp/libjuice",
            "../libjuice",
            "build/../libjuice",
            "build//libjuice",
            "build/./libjuice",
            "build\\offline-source\\libjuice",
            "build/offline-source/",
            "build/\x00/libjuice",
        )
        for path in rejected_paths:
            with self.subTest(path=repr(path)):
                with self.assertRaises(CHECKER.OfflineSourceValidationError):
                    CHECKER.validate_repo_relative_path(path, "mutation.path")
        self.assertEqual(
            CHECKER.EXPECTED_INTAKE_ROOT_RELATIVE,
            CHECKER.validate_repo_relative_path(
                CHECKER.EXPECTED_INTAKE_ROOT_RELATIVE,
                "canonical.path",
            ),
        )

    def test_document_paths_reject_root_and_future_layout_drift(self) -> None:
        for mutation in (
            "/tmp/libjuice-1.7.2",
            "build/offline-source/../libjuice-1.7.2",
            "build/offline-source/libjuice-*",
            "build/offline-source/libjuice-1.7.3",
        ):
            with self.subTest(root=mutation):
                self.assert_rejected(
                    lambda value, mutation=mutation: value.update({"expectedIntakeRoot": mutation})
                )
        for key, mutation in (
            ("originalArchive", "original/*.tar.gz"),
            ("extractedSource", "../source"),
            ("sourceProvenance", "/source-provenance.json"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["requiredFutureLayout"].update({key: mutation})
                )

    def test_root_present_is_fail_closed_without_consumption(self) -> None:
        existing_fixed_path = CHECKER.ARTIFACT_JSON_PATH.parent
        self.assertTrue(existing_fixed_path.exists())
        with self.assertRaises(CHECKER.OfflineSourceValidationError):
            CHECKER.validate_intake_root_absent(existing_fixed_path)
        original_intake_root = CHECKER.EXPECTED_INTAKE_ROOT
        try:
            CHECKER.EXPECTED_INTAKE_ROOT = existing_fixed_path
            self.assertEqual(1, CHECKER.main())
        finally:
            CHECKER.EXPECTED_INTAKE_ROOT = original_intake_root
        CHECKER.validate_intake_root_absent(CHECKER.EXPECTED_INTAKE_ROOT)

    def test_ancestor_type_owner_and_write_permissions_fail_closed(self) -> None:
        expected_uid = Path.home().lstat().st_uid
        CHECKER.validate_intake_ancestor_metadata(CHECKER.ROOT, expected_uid)
        with self.assertRaises(CHECKER.OfflineSourceValidationError):
            CHECKER.validate_intake_ancestor_metadata(CHECKER.ARTIFACT_JSON_PATH, expected_uid)
        for mode, uid in (
            (0o040775, expected_uid),
            (0o040757, expected_uid),
            (0o040755, expected_uid + 1),
            (0o100644, expected_uid),
        ):
            with self.subTest(mode=oct(mode), uid=uid):
                with self.assertRaises(CHECKER.OfflineSourceValidationError):
                    CHECKER.validate_intake_ancestor_values(
                        "mutation ancestor",
                        mode,
                        uid,
                        expected_uid,
                    )

    def test_all_limits_reject_relaxation_bool_float_missing_and_unknown(self) -> None:
        for key, expected in CHECKER.EXPECTED_LIMITS.items():
            with self.subTest(key=key, case="relaxed"):
                self.assert_rejected(
                    lambda value, key=key, expected=expected:
                    value["limits"].update({key: expected + 1})
                )
            with self.subTest(key=key, case="bool"):
                self.assert_rejected(
                    lambda value, key=key: value["limits"].update({key: True})
                )
            with self.subTest(key=key, case="float"):
                self.assert_rejected(
                    lambda value, key=key, expected=expected:
                    value["limits"].update({key: float(expected)})
                )
        self.assert_rejected(lambda value: value["limits"].pop("maximumArchiveBytes"))
        self.assert_rejected(lambda value: value["limits"].update({"maximumSockets": 0}))

    def test_current_evidence_rejects_hashes_results_and_completion_claims(self) -> None:
        hash_fields = (
            "commitSha1", "originalArchiveSha256", "extractedTreeSha256",
            "fileDigestSetSha256", "sourceProvenanceSha256",
        )
        for key in hash_fields:
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key:
                    value["currentEvidence"].update({key: "0" * (40 if key == "commitSha1" else 64)})
                )
        for key in (
            "licenseReviewResult", "generatedFileReviewResult", "dependencyReviewResult",
            "androidBuildFlags", "macosBuildFlags",
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key: value["currentEvidence"].update({key: "complete"})
                )

    def test_future_provenance_schema_rejects_missing_unknown_hash_and_contract_drift(self) -> None:
        self.assert_rejected(
            lambda value: value["requiredFutureProvenanceSchema"].pop("dependencies")
        )
        self.assert_rejected(
            lambda value: value["requiredFutureProvenanceSchema"].update({"fetch": {}})
        )
        mutations = (
            ("commitSha1", "currentValue", "0" * 40),
            ("originalArchive", "sha256", "0" * 64),
            ("extractedSource", "treeSha256", "0" * 64),
            ("fileDigests", "sha256", "0" * 64),
            ("licenseReview", "fileSha256", "0" * 64),
            ("generatedFiles", "sha256", "0" * 64),
            ("dependencies", "sourceSha256", "0" * 64),
            ("buildFlags", "networkTestsEnabled", True),
            ("buildFlags", "sourceExecutionAllowed", 0),
        )
        for parent, key, mutation in mutations:
            with self.subTest(parent=parent, key=key):
                self.assert_rejected(
                    lambda value, parent=parent, key=key, mutation=mutation:
                    value["requiredFutureProvenanceSchema"][parent].update({key: mutation})
                )

    def test_future_schema_requires_exact_archive_tree_file_license_generated_dependency_and_flags(self) -> None:
        cases = (
            ("releaseTag", "value", "main"),
            ("originalArchive", "relativePath", "original/source.zip"),
            ("extractedSource", "relativePath", "src"),
            ("fileDigests", "ordering", "filesystem_order"),
            ("fileDigests", "fileType", "any"),
            ("licenseReview", "requiredStatus", "optional"),
            ("generatedFiles", "requiredStatus", "skipped"),
            ("dependencies", "requiredStatus", "direct_only"),
            ("buildFlags", "requiredStatus", "not_recorded"),
            ("buildFlags", "argumentRule", "shell_command"),
        )
        for parent, key, mutation in cases:
            with self.subTest(parent=parent, key=key):
                self.assert_rejected(
                    lambda value, parent=parent, key=key, mutation=mutation:
                    value["requiredFutureProvenanceSchema"][parent].update({key: mutation})
                )

    def test_failure_and_immutability_policies_reject_completion_or_relaxation(self) -> None:
        for key, mutation in (
            ("onExpectedRootPresent", "consume_existing_root"),
            ("onSchemaOrDigestDrift", "warn"),
            ("onUnsafePathOrFileType", "skip_entry"),
            ("onLimitExceeded", "raise_limit"),
            ("onAuditFailure", "continue"),
            ("completionClaimsAllowed", True),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["failurePolicy"].update({key: mutation})
                )
        self.assert_rejected(
            lambda value: value["immutability"].update({"recordState": "complete"})
        )

    def test_artifact_and_markdown_hashes_reject_byte_or_claim_drift(self) -> None:
        for path, expected in CHECKER.ARTIFACT_SHA256.items():
            raw = path.read_bytes()
            CHECKER.validate_bytes_hash(raw, expected, str(path))
            with self.subTest(path=path.name):
                with self.assertRaises(CHECKER.OfflineSourceValidationError):
                    CHECKER.validate_bytes_hash(raw + b"\n", expected, str(path))
        markdown = CHECKER.ARTIFACT_MARKDOWN_PATH.read_text(encoding="utf-8")
        mutated = replace_once(
            markdown,
            "Source audit: `not_started`",
            "Source audit: `complete`",
        )
        self.assertNotEqual(markdown, mutated)
        with self.assertRaises(CHECKER.OfflineSourceValidationError):
            CHECKER.validate_bytes_hash(
                mutated.encode("utf-8"),
                CHECKER.ARTIFACT_SHA256[CHECKER.ARTIFACT_MARKDOWN_PATH],
                "mutated markdown",
            )

    def test_source_and_semantic_hash_helpers_reject_drift(self) -> None:
        self.assertEqual(
            CHECKER.EXPECTED_SEMANTIC_SHA256,
            CHECKER.semantic_digest(copy.deepcopy(self.canonical)),
        )
        encoded = json.dumps(self.canonical, sort_keys=True).encode("utf-8")
        with self.assertRaises(CHECKER.OfflineSourceValidationError):
            CHECKER.validate_bytes_hash(encoded, "0" * 64, "mutation")

    def test_ast_self_scan_rejects_capability_and_discovery_constructs(self) -> None:
        forbidden_sources = (
            "import socket\nsocket.socket()\n",
            "from urllib import request\nrequest.urlopen('https://example.invalid')\n",
            "import subprocess\nsubprocess.run(['true'])\n",
            "import os\nos.system('true')\n",
            "import importlib\nimportlib.import_module('socket')\n",
            "from importlib import import_module\nimport_module('socket')\n",
            "import builtins\nbuiltins.__import__('socket')\n",
            "__import__('socket')\n",
            "eval('1 + 1')\n",
            "exec('value = 1')\n",
            "compile('value = 1', '<dynamic>', 'exec')\n",
            "getattr(__builtins__, '__import__')('socket')\n",
            "import requests\nrequests.get('https://example.invalid')\n",
            "import _socket\n_socket.socket()\n",
            "import _posixsubprocess\n_posixsubprocess.fork_exec()\n",
            "import shutil\nshutil.unpack_archive('source.tar.gz', 'source')\n",
            "from pathlib import os\nos.execl('/bin/true', 'true')\nos.remove('source')\n",
            "from pathlib import Path\nPath('source').replace('moved')\n",
            "from pathlib import Path\nraw = Path('source')\nraw.replace('moved')\n",
            "from script import unreviewed_helper\n",
            "from pathlib import Path\nPath('x').write_text('payload')\n",
            "from pathlib import Path\nPath('.').glob('*')\n",
            "from pathlib import Path\nPath('.').rglob('*')\n",
            "from pathlib import Path\ndiscover = Path.glob\ndiscover(Path('.'), '*')\n",
            "globals()['__import__']('socket')\n",
            "import sys\nsys.modules['socket'].socket()\n",
        )
        for index, raw in enumerate(forbidden_sources):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.OfflineSourceValidationError):
                    CHECKER.validate_ast_source(raw, f"mutation-{index}.py")
                with self.assertRaises(ValueError):
                    SECURITY_CHECKER.validate_phase_a_static_python_ast(
                        raw,
                        f"trusted-preflight-mutation-{index}.py",
                    )
        CHECKER.validate_ast_source(
            "import ast\nimport hashlib\nimport json\nfrom pathlib import Path\n"
            "value = hashlib.sha256(b'x').hexdigest()\npath = Path('fixed/path')\n",
            "safe.py",
        )


if __name__ == "__main__":
    unittest.main()
