#!/usr/bin/env python3
"""Mutation tests for the G2 dependency wave-one execution permit checker."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_RELATIVE_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v1.py"
)
CHECKER_PATH = ROOT / CHECKER_RELATIVE_PATH
CHECKER_BYTES = CHECKER_PATH.read_bytes()
CHECKER = types.ModuleType("g2_dependency_wave1_permit_checker_under_test")
CHECKER.__dict__.update(
    {
        "__cached__": None,
        "__file__": str(CHECKER_PATH),
        "__loader__": None,
        "__package__": None,
    }
)
exec(
    compile(
        CHECKER_BYTES,
        CHECKER_RELATIVE_PATH,
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    ),
    CHECKER.__dict__,
    CHECKER.__dict__,
)


class DependencyWaveOnePermitCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision_raw = (ROOT / CHECKER.DECISION_PATH).read_bytes()
        cls.decision = json.loads(cls.decision_raw)
        cls.permit_raw = (ROOT / CHECKER.PERMIT_PATH).read_bytes()
        cls.permit = json.loads(cls.permit_raw)
        cls.raw_by_path = {
            path: (ROOT / path).read_bytes()
            for _, path in CHECKER.TOOL_ROWS
        }

    def rebound(self, permit: dict) -> dict:
        result = copy.deepcopy(permit)
        result.pop("contentBinding", None)
        result["contentBinding"] = {
            "algorithm": "sha256",
            "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "permit_without_contentBinding",
            "sha256": hashlib.sha256(
                CHECKER.canonical_json_bytes(result)
            ).hexdigest(),
        }
        return result

    def validate_mutation(self, mutate) -> CHECKER.CheckError:
        permit = copy.deepcopy(self.permit)
        mutate(permit)
        permit = self.rebound(permit)
        with self.assertRaises(CHECKER.CheckError) as caught:
            CHECKER.validate_permit(
                permit,
                self.decision,
                self.raw_by_path,
            )
        return caught.exception

    def test_01_repository_baseline_passes_without_execution(self) -> None:
        result = CHECKER.validate_repository(ROOT)
        self.assertEqual(result["permitConsumptionState"], "authorized_not_consumed")
        self.assertEqual(result["runnerTestCount"], 44)
        self.assertEqual(result["decisionCheckerPassCount"], 2)
        self.assertEqual(result["executionArtifactReadCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertEqual(result["networkOperationCount"], 0)
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        root_info = os.stat(ROOT, follow_symlinks=False)
        self.assertEqual(
            result["repositoryRootIdentity"],
            {
                "device": root_info.st_dev,
                "inode": root_info.st_ino,
                "ownerUid": root_info.st_uid,
                "mode": stat.S_IMODE(root_info.st_mode),
            },
        )

    def test_02_strict_json_rejects_duplicate_nonfinite_cr_and_missing_lf(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.CheckError) as caught:
                    CHECKER.strict_json(raw, "fixture")
                self.assertEqual(caught.exception.code, "E_JSON")

    def test_03_relative_path_rejects_escape_absolute_backslash_and_nul(self) -> None:
        for path in ("../escape", "/absolute", "a/../b", "a\\b", "a\x00b"):
            with self.subTest(path=path):
                with self.assertRaises(CHECKER.CheckError) as caught:
                    CHECKER.validate_relative_path(path)
                self.assertEqual(caught.exception.code, "E_FILESYSTEM")

    def test_04_predecessor_raw_and_content_bindings_are_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.decision_raw).hexdigest(),
            CHECKER.EXPECTED_DECISION_RAW_SHA256,
        )
        self.assertEqual(
            self.decision["contentBinding"]["sha256"],
            CHECKER.EXPECTED_DECISION_CONTENT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((ROOT / CHECKER.READER_PATH).read_bytes()).hexdigest(),
            CHECKER.EXPECTED_READER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / CHECKER.DECISION_CHECKER_PATH).read_bytes()
            ).hexdigest(),
            CHECKER.EXPECTED_DECISION_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((ROOT / CHECKER.DECISION_TEST_PATH).read_bytes()).hexdigest(),
            CHECKER.EXPECTED_DECISION_TEST_RAW_SHA256,
        )

    def test_05_permit_content_binding_is_recomputed(self) -> None:
        unsigned = copy.deepcopy(self.permit)
        binding = unsigned.pop("contentBinding")
        self.assertEqual(
            hashlib.sha256(CHECKER.canonical_json_bytes(unsigned)).hexdigest(),
            binding["sha256"],
        )
        self.assertEqual(CHECKER.content_binding(self.permit, "permit"), binding["sha256"])

    def test_06_tool_bindings_match_all_four_current_files(self) -> None:
        CHECKER.validate_tool_bindings(self.permit, self.raw_by_path)
        self.assertEqual(
            [row["path"] for row in self.permit["toolBindings"]],
            [path for _, path in CHECKER.TOOL_ROWS],
        )
        for row in self.permit["toolBindings"]:
            self.assertEqual(
                row["rawSha256"],
                hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest(),
            )

    def test_07_personal_project_authentication_escalation_is_rejected(self) -> None:
        error = self.validate_mutation(
            lambda value: value["personalProjectBoundary"].__setitem__(
                "externalAuthenticationRequired",
                True,
            )
        )
        self.assertEqual(error.code, "E_AUTHORITY")

    def test_08_private_key_or_user_action_requirement_is_rejected(self) -> None:
        for key in (
            "privateKeyTokenPasswordOrSignatureRequired",
            "userActionRequired",
            "repositoryOwnerIdentityProofRequired",
        ):
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key: value[
                        "personalProjectBoundary"
                    ].__setitem__(key, True)
                )
                self.assertEqual(error.code, "E_AUTHORITY")

    def test_09_decision_raw_content_status_result_and_next_drift_are_rejected(self) -> None:
        cases = {
            "rawSha256": "a" * 64,
            "contentSha256": "b" * 64,
            "requiredStatus": "changed",
            "requiredResult": "changed",
            "requiredNextAction": "changed",
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "decisionBinding"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_LINEAGE")

    def test_10_unknown_and_missing_top_level_keys_are_rejected(self) -> None:
        for mutate in (
            lambda value: value.__setitem__("unknown", False),
            lambda value: value.pop("scope"),
        ):
            error = self.validate_mutation(mutate)
            self.assertEqual(error.code, "E_SCHEMA")

    def test_11_status_result_next_action_and_scope_drift_are_rejected(self) -> None:
        for key in ("status", "result", "nextAction", "scope"):
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key: value.__setitem__(key, "changed")
                )
                self.assertEqual(error.code, "E_PERMIT_STATE")

    def test_12_interpreter_isolation_or_cli_override_drift_is_rejected(self) -> None:
        mutations = (
            ("isolatedInterpreterRequired", False),
            ("sitePackagesAllowed", True),
            ("bytecodeWritesAllowed", True),
            ("pythonPathAllowed", True),
            ("environmentOverridesAllowed", True),
            ("cliOverridesAllowed", True),
            ("processUmask", "022"),
        )
        for key, replacement in mutations:
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "interpreterIsolationContract"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_RUNTIME")

    def test_13_command_argument_drift_is_rejected(self) -> None:
        for key in ("preflightCommand", "executeCommand"):
            error = self.validate_mutation(
                lambda value, key=key: value["interpreterIsolationContract"][
                    key
                ].append("--url")
            )
            self.assertEqual(error.code, "E_RUNTIME")

    def test_14_claim_path_retry_second_execution_and_preclaim_drift_are_rejected(self) -> None:
        cases = {
            "claimPath": "build/other.claim",
            "automaticRetryAllowed": True,
            "secondExecutionAllowed": True,
            "preclaimFailureConsumesPermit": True,
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "oneUseConsumption"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_PERMIT_STATE")

    def test_15_request_count_host_method_order_and_mod_endpoint_drift_are_rejected(self) -> None:
        cases = {
            "requestCount": 20,
            "host": "example.com",
            "method": "POST",
            "tupleOrder": "parallel",
            "goModByteSource": "separate_mod_endpoint",
            "responseBodyKind": "zip_and_mod",
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "requestContract"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_REQUEST_CONTRACT")

    def test_16_redirect_retry_range_mirror_auth_cookie_proxy_drift_is_rejected(self) -> None:
        for key in (
            "redirectsAllowed",
            "automaticRetriesAllowed",
            "rangeOrResumeAllowed",
            "alternateMirrorAllowed",
            "queryFragmentOrUserInfoAllowed",
            "authenticationHeadersAllowed",
            "cookiesAllowed",
            "clientCertificatesAllowed",
            "ambientProxyAllowed",
        ):
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key: value["requestContract"].__setitem__(
                        key,
                        True,
                    )
                )
                self.assertEqual(error.code, "E_REQUEST_CONTRACT")

    def test_17_runtime_product_relay_network_authority_is_rejected(self) -> None:
        for key in (
            "runtimeSocketAuthorized",
            "runtimeNetworkAuthorized",
            "productNetworkAuthorized",
            "relayOrP2PNetworkAuthorized",
        ):
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key: value["networkAuthority"].__setitem__(
                        key,
                        True,
                    )
                )
                self.assertEqual(error.code, "E_NETWORK_AUTHORITY")

    def test_18_archive_extraction_zip64_encryption_and_special_file_drift_are_rejected(self) -> None:
        cases = {
            "filesystemExtractionAllowed": True,
            "zip64Allowed": True,
            "encryptionAllowed": True,
            "explicitDirectoryEntriesAllowed": True,
            "symlinkOrSpecialFileAllowed": True,
            "duplicateOrCasefoldCollisionAllowed": True,
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "archiveValidationContract"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_WAVE")

    def test_19_filesystem_modes_scope_and_other_write_drift_are_rejected(self) -> None:
        cases = {
            "existingAncestorPolicy": "owner_only_0700",
            "newDirectoryMode": "0755",
            "newFileMode": "0644",
            "unexpectedSiblingScope": "entire_repository",
            "sourceModificationAuthorized": True,
            "sourceExtractionAuthorized": True,
            "otherRepositoryWritesAuthorized": True,
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "filesystemWriteAuthority"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_FILESYSTEM_AUTHORITY")

    def test_20_any_resource_limit_drift_is_rejected(self) -> None:
        for key in self.permit["resourceLimits"]:
            with self.subTest(key=key):
                original = self.permit["resourceLimits"][key]
                replacement = original + 1 if type(original) is int else "changed"
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "resourceLimits"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_BOUNDS")

    def test_21_receipt_paths_counts_manifest_order_and_readback_drift_are_rejected(self) -> None:
        cases = {
            "successReceiptPath": "changed",
            "failureReceiptPath": "changed",
            "manifestPath": "changed",
            "acceptedArtifactCountOnSuccess": 18,
            "acceptedArtifactCountOnFailure": 1,
            "manifestWrittenLast": False,
            "runnerMayClaimIndependentReadback": True,
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "receiptFailureManifestContract"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_PERMIT_STATE")

    def test_22_post_publish_uncertain_state_and_recovery_boundary_are_required(self) -> None:
        cases = {
            "postPublishUncertainState": "success",
            "postPublishUncertainAutomaticRecoveryAllowed": True,
            "postPublishUncertainNextAction": "retry",
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "receiptFailureManifestContract"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_PERMIT_STATE")

    def test_23_state_machine_reorder_omit_and_terminal_drift_are_rejected(self) -> None:
        mutations = (
            lambda value: value["stateMachine"].reverse(),
            lambda value: value["stateMachine"].pop(),
            lambda value: value["stateMachine"][4].__setitem__("terminal", True),
        )
        for mutate in mutations:
            error = self.validate_mutation(mutate)
            self.assertEqual(error.code, "E_PERMIT_STATE")

    def test_24_package_go_git_shell_compiler_source_runtime_device_deploy_are_closed(self) -> None:
        for key in (
            "packageManagerAuthorized",
            "goCommandAuthorized",
            "gitCommandAuthorized",
            "shellOrSubprocessAuthorized",
            "compilerAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "runtimeOrProductNetworkAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "gitWriteAuthorized",
        ):
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key: value["authority"].__setitem__(key, True)
                )
                self.assertEqual(error.code, "E_AUTHORITY")

    def test_25_authority_bool_to_integer_drift_is_rejected(self) -> None:
        error = self.validate_mutation(
            lambda value: value["authority"].__setitem__(
                "exactWave1AcquisitionAuthorized",
                1,
            )
        )
        self.assertEqual(error.code, "E_AUTHORITY")

    def test_26_execution_claim_network_receipt_manifest_or_readback_overclaim_is_rejected(self) -> None:
        cases = {
            "permitConsumed": True,
            "claimCreated": True,
            "requestCount": 1,
            "acceptedArtifactCount": 1,
            "networkUsed": True,
            "successReceiptCreated": True,
            "failureReceiptCreated": True,
            "manifestCreated": True,
            "independentReadbackPassed": True,
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "execution"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_EXECUTION")

    def test_27_closure_finding_graph_selection_and_library_overclaim_is_rejected(self) -> None:
        cases = {
            "openFindingCount": 18,
            "findingsClosedByPermit": 1,
            "waveAcquired": True,
            "graphFixedPointReached": True,
            "dependencySourceReviewed": True,
            "dependencyClosureComplete": True,
            "semanticClosureComplete": True,
            "rungThreeComplete": True,
            "candidateSelected": True,
            "librarySelected": True,
        }
        for key, replacement in cases.items():
            with self.subTest(key=key):
                error = self.validate_mutation(
                    lambda value, key=key, replacement=replacement: value[
                        "closure"
                    ].__setitem__(key, replacement)
                )
                self.assertEqual(error.code, "E_CLOSURE")

    def test_28_nonclaim_omit_reorder_or_weaken_is_rejected(self) -> None:
        mutations = (
            lambda value: value["nonClaims"].pop(),
            lambda value: value["nonClaims"].reverse(),
            lambda value: value["nonClaims"].__setitem__(0, "permit_is_success"),
        )
        for mutate in mutations:
            error = self.validate_mutation(mutate)
            self.assertEqual(error.code, "E_NONCLAIM")

    def test_29_runner_checker_trust_root_matches_actual_checker_bytes(self) -> None:
        runner = (ROOT / CHECKER.RUNNER_PATH).read_text(encoding="utf-8")
        digest = hashlib.sha256(CHECKER_BYTES).hexdigest()
        self.assertIn(
            f'EXPECTED_CHECKER_RAW_SHA256 = "{digest}"',
            runner,
        )
        self.assertIn("def create_download_file_flags() -> int:", runner)
        self.assertIn("os.O_RDWR", runner)
        self.assertIn("create_download_file_flags(),", runner)
        self.assertIn("renameatx_np", runner)
        self.assertIn("def validate_local_header(", runner)
        self.assertIn("def set_response_io_timeout(", runner)
        self.assertIn('read_one = getattr(response, "read1", None)', runner)
        self.assertIn("chunk = read_one(", runner)
        self.assertIn("def hard_wall_clock_request_deadline(", runner)
        self.assertIn("def restore_hard_deadline_state(", runner)
        self.assertIn("for _attempt in range(2):", runner)
        self.assertIn("if disarmed:", runner)
        self.assertIn("signal.setitimer(signal.ITIMER_REAL", runner)
        self.assertIn(
            "threading.current_thread() is threading.main_thread()",
            runner,
        )
        self.assertIn("def named_entry_matches_open_file(", runner)
        self.assertIn("def validate_held_output_inventory(", runner)
        self.assertIn(
            "validate_held_output_inventory(published_fd, held_outputs)",
            runner,
        )
        self.assertIn("verified_fd: int", runner)
        self.assertIn("entry.create_system in {0, 3}", runner)
        self.assertIn('authority.get("repositoryRootIdentity")', runner)
        self.assertIn("def inspect_one_use_state(", runner)
        self.assertIn(
            "one_use_artifact_count(inspect_one_use_state(root_fd)) == 0",
            runner,
        )
        self.assertIn('"blocked_one_use_state_present"', runner)
        self.assertIn('phase="zip"', runner)
        self.assertIn('phase="publication"', runner)
        self.assertIn("def normalize_execution_failure(", runner)
        CHECKER.validate_runner_source(
            (ROOT / CHECKER.RUNNER_PATH).read_bytes(),
            (ROOT / CHECKER.RUNNER_TEST_PATH).read_bytes(),
            CHECKER_BYTES,
        )
        with self.assertRaises(CHECKER.CheckError) as caught:
            CHECKER.validate_runner_source(
                runner.replace("os.O_RDWR", "os.O_WRONLY", 1).encode("utf-8"),
                (ROOT / CHECKER.RUNNER_TEST_PATH).read_bytes(),
                CHECKER_BYTES,
            )
        self.assertEqual(caught.exception.code, "E_TOOL_BINDING")
        for required in (
            "renameatx_np",
            "def validate_local_header(",
            "def set_response_io_timeout(",
            'read_one = getattr(response, "read1", None)',
            "chunk = read_one(",
            "def hard_wall_clock_request_deadline(",
            "def restore_hard_deadline_state(",
            "for _attempt in range(2):",
            "if disarmed:",
            "signal.setitimer(signal.ITIMER_REAL",
            "threading.current_thread() is threading.main_thread()",
            "def named_entry_matches_open_file(",
            "def validate_held_output_inventory(",
            "validate_held_output_inventory(staging_fd, held_outputs)",
            "validate_held_output_inventory(published_fd, held_outputs)",
            "verified_fd: int",
            "entry.create_system in {0, 3}",
            'authority.get("repositoryRootIdentity")',
            "def inspect_one_use_state(",
            "one_use_artifact_count(inspect_one_use_state(root_fd)) == 0",
            '"blocked_one_use_state_present"',
            'phase="zip"',
            'phase="publication"',
            "def normalize_execution_failure(",
            "os.fsync(parent_fd)",
        ):
            with self.subTest(required=required):
                with self.assertRaises(CHECKER.CheckError) as caught:
                    CHECKER.validate_runner_source(
                        runner.replace(required, "REMOVED").encode("utf-8"),
                        (ROOT / CHECKER.RUNNER_TEST_PATH).read_bytes(),
                        CHECKER_BYTES,
                    )
                self.assertEqual(caught.exception.code, "E_TOOL_BINDING")

    def test_30_runner_ast_has_no_process_or_general_socket_import(self) -> None:
        runner_raw = (ROOT / CHECKER.RUNNER_PATH).read_bytes()
        tree = ast.parse(runner_raw, filename=CHECKER.RUNNER_PATH)
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        self.assertTrue({"subprocess", "socket", "requests"}.isdisjoint(imports))
        self.assertTrue({"system", "popen", "fork", "execv"}.isdisjoint(calls))

    def test_31_runner_test_suite_has_exactly_44_unique_tests(self) -> None:
        tree = ast.parse(
            (ROOT / CHECKER.RUNNER_TEST_PATH).read_bytes(),
            filename=CHECKER.RUNNER_TEST_PATH,
        )
        names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        self.assertEqual(len(names), 44)
        self.assertEqual(len(set(names)), 44)

    def test_32_tool_binding_drift_is_rejected_before_authority_use(self) -> None:
        permit = copy.deepcopy(self.permit)
        permit["toolBindings"][0]["rawSha256"] = "a" * 64
        permit = self.rebound(permit)
        with self.assertRaises(CHECKER.CheckError) as caught:
            CHECKER.validate_permit(permit, self.decision, self.raw_by_path)
        self.assertEqual(caught.exception.code, "E_TOOL_BINDING")

    def test_33_safe_reader_rejects_symlink_hardlink_and_group_write(self) -> None:
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        root.chmod(0o700)
        (root / "real").write_bytes(b"ok\n")
        (root / "real").chmod(0o600)
        os.symlink("real", root / "link")
        os.link(root / "real", root / "hard")
        reader = CHECKER.SafeReader(root)
        try:
            for name in ("link", "hard"):
                with self.subTest(name=name):
                    with self.assertRaises(CHECKER.CheckError):
                        reader.read(name)
            (root / "broad").write_bytes(b"bad\n")
            (root / "broad").chmod(0o620)
            with self.assertRaises(CHECKER.CheckError):
                reader.read("broad")
        finally:
            reader.close()
            directory.cleanup()

    def test_34_safe_reader_detects_replace_after_read(self) -> None:
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        root.chmod(0o700)
        target = root / "target"
        target.write_bytes(b"first\n")
        target.chmod(0o600)
        reader = CHECKER.SafeReader(root)
        try:
            reader.read("target")
            replacement = root / "replacement"
            replacement.write_bytes(b"other\n")
            replacement.chmod(0o600)
            os.replace(replacement, target)
            with self.assertRaises(CHECKER.CheckError) as caught:
                reader.verify()
            self.assertEqual(caught.exception.code, "E_TOCTOU")
        finally:
            reader.close()
            directory.cleanup()

        root_directory = tempfile.TemporaryDirectory()
        parent = Path(root_directory.name)
        root = parent / "root"
        moved = parent / "moved"
        root.mkdir(mode=0o700)
        reader = CHECKER.SafeReader(root)
        try:
            root.rename(moved)
            root.mkdir(mode=0o700)
            with self.assertRaises(CHECKER.CheckError) as caught:
                reader.verify_root()
            self.assertEqual(caught.exception.code, "E_TOCTOU")
        finally:
            reader.close()
            root_directory.cleanup()

    def test_35_permit_reader_states_no_auth_and_uncertain_boundary(self) -> None:
        raw = (ROOT / CHECKER.PERMIT_READER_PATH).read_bytes()
        CHECKER.validate_permit_reader(raw, self.permit)
        text = raw.decode("utf-8")
        self.assertIn("사용자 인증", text)
        self.assertIn("요구하지 않는다", text)
        self.assertIn("POST_PUBLISH_UNCERTAIN", text)
        self.assertIn("creator-system", text)
        self.assertIn("repository-root device", text)
        self.assertIn("verified descriptor", text)
        self.assertIn("SIGALRM", text)
        self.assertIn("one-use state", text)
        self.assertIn("All 19", text)
        self.assertIn("pre-publication re-hash/fsync", text)
        self.assertIn("It does not claim to", text)

    def test_36_permit_has_no_null_placeholder_or_execution_artifact_claim(self) -> None:
        rendered = json.dumps(self.permit, sort_keys=True)
        self.assertNotIn("__PENDING_", rendered)
        self.assertNotIn(": null", rendered)
        self.assertFalse(self.permit["execution"]["permitConsumed"])
        self.assertEqual(self.permit["execution"]["requestCount"], 0)
        self.assertFalse(self.permit["execution"]["networkUsed"])

    def test_37_main_success_output_requires_no_user_authentication(self) -> None:
        with mock.patch("builtins.print") as output:
            self.assertEqual(CHECKER.main([]), 0)
        rendered = output.call_args.args[0]
        self.assertIn("not consumed", rendered)
        self.assertIn("no user authentication required", rendered)

    def test_38_checker_failure_output_does_not_emit_raw_exception_text(self) -> None:
        with (
            mock.patch.object(
                CHECKER,
                "validate_repository",
                side_effect=OSError("/absolute/secret token"),
            ),
            mock.patch("builtins.print") as output,
        ):
            self.assertEqual(CHECKER.main([]), 1)
        rendered = output.call_args.args[0]
        self.assertNotIn("/absolute", rendered)
        self.assertNotIn("token", rendered)
        self.assertIn("E_INTERNAL", rendered)


if __name__ == "__main__":
    unittest.main()
