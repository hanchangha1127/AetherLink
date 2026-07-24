#!/usr/bin/env python3
"""Synthetic mutation tests for the G2 source-review wave-one permit."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("tests require unoptimized `python3 -I -B -S`")

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


SOURCE_ROOT = Path(__file__).resolve().parents[1]
CHECKER_FILE = (
    SOURCE_ROOT
    / "script/check_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_execution_permit_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "dependency_source_review_wave1_execution_permit_v1_checker",
    CHECKER_FILE,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load execution-permit checker")
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)

RUNNER_FILE = (
    SOURCE_ROOT
    / "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "dependency_source_review_wave1_runner",
    RUNNER_FILE,
)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("cannot load dependency source-review runner")
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = RUNNER
RUNNER_SPEC.loader.exec_module(RUNNER)


class DependencySourceReviewWaveOnePermitV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.raw: dict[str, bytes] = {}
        self._copy_required_repository_bytes()
        self._write_synthetic_runner_tools()
        self.decision = CHECKER.strict_json(
            self.raw[CHECKER.DECISION_PATH],
            "synthetic decision",
        )
        self.recovery_decision = CHECKER.strict_json(
            self.raw[CHECKER.RECOVERY_DECISION_PATH],
            "synthetic recovery decision",
        )
        self.v1_recovery_decision = CHECKER.strict_json(
            self.raw[CHECKER.V1_RECOVERY_DECISION_PATH],
            "synthetic v1 recovery decision",
        )
        self.receipt = CHECKER.strict_json(
            self.raw[CHECKER.RECEIPT_PATH],
            "synthetic receipt",
        )
        self.resources = CHECKER.resource_bindings_from_receipt(self.receipt)
        self.permit = CHECKER.build_expected_permit(
            self.raw,
            self.decision,
            self.recovery_decision,
            self.receipt,
            self.resources,
        )
        self._write_permit(self.permit)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _copy(self, relative: str, *, owner_only: bool = False) -> bytes:
        source = SOURCE_ROOT / relative
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o600 if owner_only else 0o644)
        raw = destination.read_bytes()
        self.raw[relative] = raw
        return raw

    def _copy_required_repository_bytes(self) -> None:
        self._copy(CHECKER.DECISION_PATH)
        self._copy(CHECKER.V1_RECOVERY_DECISION_PATH)
        self._copy(CHECKER.RECOVERY_DECISION_PATH)
        self._copy(CHECKER.V1_PERMIT_PATH)
        self._copy(CHECKER.V1_CLAIM_PATH, owner_only=True)
        self._copy(CHECKER.V1_FAILURE_PATH, owner_only=True)
        self._copy(CHECKER.V2_PERMIT_PATH)
        self._copy(CHECKER.V2_CLAIM_PATH, owner_only=True)
        self._copy(CHECKER.V2_FAILURE_PATH, owner_only=True)
        self._copy(CHECKER.DECISION_CHECKER_PATH)
        self._copy(CHECKER.DECISION_TEST_PATH)
        self._copy(CHECKER.CHECKER_PATH)
        self._copy(CHECKER.CHECKER_TEST_PATH)
        self._copy(CHECKER.READBACK_RECORDER_PATH)
        self._copy(CHECKER.READBACK_RECORDER_TEST_PATH)
        self._copy(CHECKER.READBACK_CHECKER_PATH)
        self._copy(CHECKER.READBACK_CHECKER_TEST_PATH)
        for item in CHECKER.FIXED_BINDINGS:
            self._copy(item.path, owner_only=item.owner_only)
        self._copy(CHECKER.ROOT_ARCHIVE_PATH, owner_only=True)
        receipt = json.loads(self.raw[CHECKER.RECEIPT_PATH])
        for item in CHECKER.resource_bindings_from_receipt(receipt):
            self._copy(item["path"], owner_only=True)

    def _write_synthetic_runner_tools(self) -> None:
        for path, body in (
            (
                CHECKER.RUNNER_PATH,
                b"#!/usr/bin/env python3\n# synthetic held runner\n",
            ),
            (
                CHECKER.RUNNER_TEST_PATH,
                b"#!/usr/bin/env python3\n# synthetic held runner tests\n",
            ),
        ):
            destination = self.root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
            destination.chmod(0o644)
            self.raw[path] = body

    def _write_permit(self, permit: dict[str, object]) -> None:
        path = self.root / CHECKER.PERMIT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(CHECKER.canonical_json_bytes(permit))
        path.chmod(0o644)

    def _mutate_and_rebind(self, mutation: object) -> None:
        permit = copy.deepcopy(self.permit)
        mutation(permit)
        unsigned = dict(permit)
        unsigned.pop("contentBinding")
        permit["contentBinding"]["sha256"] = CHECKER.sha256_bytes(
            CHECKER.canonical_json_bytes(unsigned)
        )
        self._write_permit(permit)

    def test_01_synthetic_baseline_validates_without_side_effects(self) -> None:
        before = {
            path: hashlib.sha256((self.root / path).read_bytes()).hexdigest()
            for path in (
                CHECKER.PERMIT_PATH,
                CHECKER.DECISION_PATH,
                CHECKER.ROOT_ARCHIVE_PATH,
            )
        }
        result = CHECKER.validate_repository(self.root)
        after = {
            path: hashlib.sha256((self.root / path).read_bytes()).hexdigest()
            for path in before
        }
        self.assertEqual(before, after)
        self.assertTrue(result["reviewExecutionAuthorized"])
        self.assertTrue(result["namespaceInitiallyClean"])
        self.assertEqual(result["heldInputResourceCount"], 38)
        self.assertEqual(result["archiveMemberInspectionCount"], 0)
        self.assertEqual(result["networkOperationCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])

    def test_02_absent_permit_is_not_authorized(self) -> None:
        (self.root / CHECKER.PERMIT_PATH).unlink()
        status, exit_code = CHECKER.preflight_status(self.root)
        self.assertEqual(exit_code, 1)
        self.assertEqual(status["status"], "permit_absent_not_authorized")
        self.assertFalse(status["reviewExecutionAuthorized"])

    def test_03_status_mutation_with_rebound_content_is_rejected(self) -> None:
        self._mutate_and_rebind(
            lambda permit: permit.update({"status": "drift"})
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_04_runner_hash_mutation_with_rebound_content_is_rejected(self) -> None:
        self._mutate_and_rebind(
            lambda permit: permit["toolBindings"][2].update(
                {"rawSha256": "0" * 64}
            )
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_05_authority_overclaim_is_rejected(self) -> None:
        self._mutate_and_rebind(
            lambda permit: permit["authority"].update(
                {"networkAuthorized": True}
            )
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_06_closure_overclaim_is_rejected(self) -> None:
        self._mutate_and_rebind(
            lambda permit: permit["closure"].update(
                {"graphFixedPointReached": True}
            )
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_07_auth_or_user_action_overclaim_is_rejected(self) -> None:
        self._mutate_and_rebind(
            lambda permit: permit["personalProjectBoundary"].update(
                {
                    "externalAuthenticationRequired": True,
                    "userActionRequired": True,
                }
            )
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_08_strict_json_rejects_duplicate_and_ambiguous_numbers(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":1.0}\n',
            b'{"a":NaN}\n',
            b'{"a":Infinity}\n',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.PermitError):
                    CHECKER.strict_json(raw, "mutation")

    def test_09_symlinked_input_is_rejected(self) -> None:
        resource = self.resources[0]["path"]
        path = self.root / resource
        replacement = path.with_name("replacement.mod")
        replacement.write_bytes(path.read_bytes())
        replacement.chmod(0o600)
        path.unlink()
        path.symlink_to(replacement)
        with self.assertRaises(OSError):
            CHECKER.validate_repository(self.root)

    def test_10_hardlinked_input_is_rejected(self) -> None:
        path = self.root / self.resources[0]["path"]
        os.link(path, path.with_name("extra-hard-link"))
        with self.assertRaisesRegex(CHECKER.PermitError, "single-link"):
            CHECKER.validate_repository(self.root)

    def test_11_relaxed_owner_only_input_mode_is_rejected(self) -> None:
        path = self.root / self.resources[0]["path"]
        path.chmod(0o644)
        with self.assertRaisesRegex(CHECKER.PermitError, "owner-only"):
            CHECKER.validate_repository(self.root)

    def test_12_final_name_replacement_is_rejected(self) -> None:
        path = self.root / CHECKER.DECISION_PATH
        original = path.read_bytes()

        def replace_final_name() -> None:
            path.unlink()
            path.write_bytes(original)
            path.chmod(0o644)

        with self.assertRaisesRegex(CHECKER.PermitError, "identity changed"):
            CHECKER.validate_repository(
                self.root,
                before_final_barrier=replace_final_name,
            )

    def test_13_ancestor_replacement_is_rejected(self) -> None:
        accepted = self.root / CHECKER.DEPENDENCY_DIRECTORY
        old_accepted = accepted.with_name("accepted-old")

        def replace_ancestor() -> None:
            accepted.rename(old_accepted)
            accepted.mkdir(mode=0o700)

        with self.assertRaises(CHECKER.PermitError):
            CHECKER.validate_repository(
                self.root,
                before_final_barrier=replace_ancestor,
            )

    def test_14_claim_and_casefold_namespace_collisions_are_rejected(self) -> None:
        claim = self.root / CHECKER.CLAIM_PATH
        claim.write_bytes(b"collision")
        claim.chmod(0o600)
        with self.assertRaisesRegex(CHECKER.PermitError, "namespace collision"):
            CHECKER.validate_repository(self.root)
        claim.unlink()
        claim_collision = claim.with_name(claim.name.upper())
        claim_collision.write_bytes(b"collision")
        claim_collision.chmod(0o600)
        with self.assertRaisesRegex(CHECKER.PermitError, "namespace collision"):
            CHECKER.validate_repository(self.root)
        claim_collision.unlink()
        result_collision = (
            self.root
            / CHECKER.RESULT_PATH.rsplit("/", 1)[0]
            / CHECKER.RESULT_PATH.rsplit("/", 1)[1].upper()
        )
        result_collision.write_bytes(b"collision")
        with self.assertRaisesRegex(CHECKER.PermitError, "namespace collision"):
            CHECKER.validate_repository(self.root)

    def test_15_checker_has_no_execution_network_or_write_surface(self) -> None:
        source = CHECKER_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported_roots.isdisjoint(
                {
                    "asyncio",
                    "ftplib",
                    "http",
                    "socket",
                    "ssl",
                    "subprocess",
                    "urllib",
                    "zipfile",
                }
            )
        )
        self.assertTrue(
            imported_roots
            <= {
                "__future__",
                "argparse",
                "dataclasses",
                "hashlib",
                "json",
                "math",
                "os",
                "pathlib",
                "stat",
                "sys",
                "typing",
                "unicodedata",
            }
        )
        self.assertIn('parser.add_argument("--preflight"', source)
        self.assertNotIn('parser.add_argument("--execute"', source)
        for surface in (
            ".write_bytes(",
            ".write_text(",
            "os.mkdir(",
            "os.makedirs(",
            "os.rename(",
            "os.replace(",
            "os.unlink(",
            "os.write(",
            "os.pwrite(",
        ):
            self.assertNotIn(surface, source)
        forbidden_open_flags = {
            "O_WRONLY",
            "O_RDWR",
            "O_CREAT",
            "O_TRUNC",
            "O_APPEND",
        }
        for call in (
            node for node in ast.walk(tree) if isinstance(node, ast.Call)
        ):
            function = call.func
            if not (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "os"
                and function.attr == "open"
                and len(call.args) >= 2
            ):
                continue
            used_flags = {
                node.attr
                for node in ast.walk(call.args[1])
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            }
            self.assertTrue(used_flags.isdisjoint(forbidden_open_flags))

    def test_16_boolean_integer_contract_mutation_is_rejected(self) -> None:
        self._mutate_and_rebind(
            lambda permit: permit["inputBindings"].update(
                {"resourceCount": True}
            )
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_17_checker_built_permit_composes_with_runner_preflight(self) -> None:
        permit, bindings = RUNNER.load_validated_authority(self.root)
        self.assertEqual(permit, self.permit)
        self.assertEqual(len(bindings), 68)
        preflight = RUNNER.preflight_with_authority(
            self.root,
            permit,
            bindings,
        )
        self.assertTrue(preflight["validationPassed"])
        self.assertEqual(
            preflight["permitConsumptionState"],
            "authorized_not_consumed",
        )
        self.assertEqual(preflight["archiveInspectionCount"], 0)
        self.assertEqual(preflight["networkOperationCount"], 0)
        self.assertEqual(preflight["fileWriteCount"], 0)

    def test_18_each_no_auth_boundary_field_is_independently_bound(self) -> None:
        false_fields = (
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "executionPermitAuthenticationRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "signatureRequired",
            "credentialsAllowed",
            "userActionRequired",
            "productEndpointAuthenticationEvaluatedByThisPermit",
            "productEndpointAuthenticationUserInputRequiredForThisPermit",
        )
        for field in false_fields:
            with self.subTest(field=field):
                self._mutate_and_rebind(
                    lambda permit, field=field: permit[
                        "personalProjectBoundary"
                    ].update({field: True})
                )
                with self.assertRaisesRegex(
                    CHECKER.PermitError,
                    "exact typed",
                ):
                    CHECKER.validate_repository(self.root)
        self._mutate_and_rebind(
            lambda permit: permit["personalProjectBoundary"].update(
                {
                    "productEndpointAuthenticationIsSeparateRuntimeInvariant": (
                        False
                    )
                }
            )
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_19_recovery_decision_is_exactly_raw_and_content_bound(self) -> None:
        raw = self.raw[CHECKER.RECOVERY_DECISION_PATH]
        self.assertEqual(
            CHECKER.sha256_bytes(raw),
            CHECKER.RECOVERY_DECISION_RAW_SHA256,
        )
        self.assertEqual(
            self.recovery_decision["contentBinding"]["sha256"],
            CHECKER.RECOVERY_DECISION_CONTENT_SHA256,
        )
        self.assertEqual(
            self.recovery_decision,
            CHECKER.build_expected_recovery_decision(),
        )
        self.assertEqual(
            CHECKER.sha256_bytes(
                self.raw[CHECKER.V1_RECOVERY_DECISION_PATH]
            ),
            CHECKER.V1_RECOVERY_DECISION_RAW_SHA256,
        )
        self.assertEqual(
            self.v1_recovery_decision,
            CHECKER.build_expected_recovery_decision_v1(),
        )

    def test_20_v1_permit_claim_and_failure_are_exactly_bound(self) -> None:
        permit, claim, failure = CHECKER.validate_failed_attempt(self.raw)
        self.assertEqual(permit["permitId"], CHECKER.V1_PERMIT_ID)
        self.assertEqual(claim["reviewId"], CHECKER.V1_REVIEW_ID)
        self.assertEqual(failure["failureCode"], "E_HELD_SET")
        self.assertEqual(failure["phase"], "held_set")
        self.assertEqual(
            failure["claimRawSha256"],
            CHECKER.V1_CLAIM_RAW_SHA256,
        )

    def test_21_v1_failure_cross_binding_drift_is_rejected(self) -> None:
        failure = copy.deepcopy(
            CHECKER.strict_json(
                self.raw[CHECKER.V1_FAILURE_PATH],
                "synthetic v1 failure",
            )
        )
        failure["claimRawSha256"] = "0" * 64
        unsigned = dict(failure)
        unsigned.pop("contentBinding")
        content_sha256 = CHECKER.sha256_bytes(
            CHECKER.canonical_json_bytes(unsigned)
        )
        failure["contentBinding"]["sha256"] = content_sha256
        failure_raw = CHECKER.canonical_json_bytes(failure)
        raw = dict(self.raw)
        raw[CHECKER.V1_FAILURE_PATH] = failure_raw
        with (
            mock.patch.object(
                CHECKER,
                "V1_FAILURE_RAW_SHA256",
                CHECKER.sha256_bytes(failure_raw),
            ),
            mock.patch.object(
                CHECKER,
                "V1_FAILURE_CONTENT_SHA256",
                content_sha256,
            ),
        ):
            with self.assertRaisesRegex(
                CHECKER.PermitError,
                "v1 failure cross-binding",
            ):
                CHECKER.validate_failed_attempt(raw)

    def test_22_v1_absent_result_contract_is_enforced(self) -> None:
        path = self.root / CHECKER.V1_RESULT_PATH
        path.write_bytes(b"historical backfill forbidden\n")
        path.chmod(0o600)
        with self.assertRaisesRegex(
            CHECKER.PermitError,
            "v1 failed-attempt namespace",
        ):
            CHECKER.validate_repository(self.root)

    def test_23_v1_absent_readback_collision_is_enforced(self) -> None:
        expected = self.root / CHECKER.V1_READBACK_RECEIPT_PATH
        collision = expected.with_name(expected.name.upper())
        collision.write_bytes(b"historical collision forbidden\n")
        collision.chmod(0o600)
        with self.assertRaisesRegex(
            CHECKER.PermitError,
            "v1 failed-attempt namespace",
        ):
            CHECKER.validate_repository(self.root)

    def test_24_v3_readback_namespace_must_be_fresh(self) -> None:
        path = self.root / CHECKER.READBACK_CLAIM_PATH
        path.write_bytes(b"v3 collision\n")
        path.chmod(0o600)
        with self.assertRaisesRegex(
            CHECKER.PermitError,
            "one-use namespace collision",
        ):
            CHECKER.validate_repository(self.root)

    def test_25_apfs_and_v1_no_reuse_contracts_are_exact(self) -> None:
        permit_apfs = self.permit["apfsRecoveryContract"]
        self.assertEqual(
            permit_apfs["directoryIdentityFields"],
            ["st_dev", "st_ino", "st_mode", "st_uid", "st_gid"],
        )
        self.assertTrue(permit_apfs["directoryIdentityExcludesLinkCount"])
        self.assertTrue(permit_apfs["trustedHeldOutputParentRequired"])
        self.assertTrue(
            permit_apfs[
                "claimAndOutputsPublishedDirectlyThroughHeldParentDescriptors"
            ]
        )
        self.assertFalse(
            permit_apfs["descendantRetraversalForPublicationAllowed"]
        )
        self.assertFalse(
            self.permit["v1PreservationContract"]["v1PermitReuseAllowed"]
        )
        self.assertFalse(
            self.permit["v2PreservationContract"]["v2PermitReuseAllowed"]
        )
        self.assertTrue(
            self.permit["selectedV3Correction"][
                "escapeAwareSingleQuotedRuneTokenRequired"
            ]
        )
        self.assertTrue(
            self.permit["selectedV3Correction"][
                "reviewFailureCodePreserved"
            ]
        )
        self.assertFalse(
            self.permit["selectedV3Correction"][
                "runeTokenMaySatisfyImportStringRequirement"
            ]
        )

    def test_26_v3_identifiers_and_all_output_paths_are_bound(self) -> None:
        namespace = self.permit["v3NamespaceContract"]
        self.assertEqual(self.permit["permitId"], CHECKER.PERMIT_ID)
        self.assertEqual(namespace["reviewId"], CHECKER.REVIEW_ID)
        self.assertEqual(namespace["claimPath"], CHECKER.CLAIM_PATH)
        self.assertEqual(namespace["resultPath"], CHECKER.RESULT_PATH)
        self.assertEqual(namespace["failurePath"], CHECKER.FAILURE_PATH)
        self.assertEqual(namespace["manifestPath"], CHECKER.MANIFEST_PATH)
        self.assertEqual(
            namespace["readbackClaimPath"],
            CHECKER.READBACK_CLAIM_PATH,
        )
        self.assertEqual(
            namespace["readbackReceiptPath"],
            CHECKER.READBACK_RECEIPT_PATH,
        )
        self.assertEqual(
            namespace["readbackManifestPath"],
            CHECKER.READBACK_MANIFEST_PATH,
        )

    def test_27_all_ten_tool_hashes_come_from_current_held_bytes(self) -> None:
        bindings = self.permit["toolBindings"]
        self.assertEqual(len(bindings), 10)
        for binding in bindings:
            with self.subTest(role=binding["role"]):
                self.assertEqual(
                    binding["rawSha256"],
                    CHECKER.sha256_bytes(self.raw[binding["path"]]),
                )

    def test_28_recovery_and_permit_require_no_auth_or_user_action(self) -> None:
        self.assertFalse(
            self.recovery_decision["authority"][
                "externalAuthenticationRequired"
            ]
        )
        self.assertFalse(
            self.recovery_decision["authority"]["userActionRequired"]
        )
        self.assertFalse(
            self.permit["authority"]["externalAuthenticationRequired"]
        )
        self.assertFalse(self.permit["authority"]["userActionRequired"])

    def test_29_rebound_recovery_decision_mutation_is_rejected(self) -> None:
        recovery = copy.deepcopy(self.recovery_decision)
        recovery["authority"]["networkAuthorized"] = True
        unsigned = dict(recovery)
        unsigned.pop("contentBinding")
        recovery["contentBinding"]["sha256"] = CHECKER.sha256_bytes(
            CHECKER.canonical_json_bytes(unsigned)
        )
        with self.assertRaisesRegex(
            CHECKER.PermitError,
            "recovery decision exact typed",
        ):
            CHECKER.validate_recovery_decision(recovery)

    def test_30_each_v1_historical_raw_binding_rejects_drift(self) -> None:
        for path, label in (
            (CHECKER.V1_PERMIT_PATH, "v1 permit raw"),
            (CHECKER.V1_CLAIM_PATH, "v1 claim raw"),
            (CHECKER.V1_FAILURE_PATH, "v1 failure raw"),
        ):
            with self.subTest(path=path):
                raw = dict(self.raw)
                raw[path] += b" "
                with self.assertRaisesRegex(CHECKER.PermitError, label):
                    CHECKER.validate_failed_attempt(raw)

    def test_31_execution_holds_recovery_and_failed_attempt_bytes(self) -> None:
        predecessors = self.permit["predecessorBindings"]
        self.assertEqual(len(predecessors), 18)
        self.assertEqual(
            len({binding["path"] for binding in predecessors}),
            18,
        )
        by_path = {binding["path"]: binding for binding in predecessors}
        for path, digest in (
            (
                CHECKER.V1_RECOVERY_DECISION_PATH,
                CHECKER.V1_RECOVERY_DECISION_RAW_SHA256,
            ),
            (
                CHECKER.RECOVERY_DECISION_PATH,
                CHECKER.RECOVERY_DECISION_RAW_SHA256,
            ),
            (CHECKER.V1_PERMIT_PATH, CHECKER.V1_PERMIT_RAW_SHA256),
            (CHECKER.V1_CLAIM_PATH, CHECKER.V1_CLAIM_RAW_SHA256),
            (CHECKER.V1_FAILURE_PATH, CHECKER.V1_FAILURE_RAW_SHA256),
            (CHECKER.V2_PERMIT_PATH, CHECKER.V2_PERMIT_RAW_SHA256),
            (CHECKER.V2_CLAIM_PATH, CHECKER.V2_CLAIM_RAW_SHA256),
            (CHECKER.V2_FAILURE_PATH, CHECKER.V2_FAILURE_RAW_SHA256),
        ):
            with self.subTest(path=path):
                self.assertEqual(by_path[path]["rawSha256"], digest)

    def test_32_v2_permit_claim_and_failure_are_exactly_bound(self) -> None:
        permit, claim, failure = CHECKER.validate_v2_failed_attempt(self.raw)
        self.assertEqual(permit["permitId"], CHECKER.V2_PERMIT_ID)
        self.assertEqual(claim["reviewId"], CHECKER.V2_REVIEW_ID)
        self.assertEqual(
            claim["contentBinding"]["sha256"],
            CHECKER.V2_CLAIM_CONTENT_SHA256,
        )
        self.assertEqual(failure["failureCode"], "E_ARCHIVE_STRUCTURE")
        self.assertEqual(failure["phase"], "archive")
        self.assertEqual(
            failure["failedTupleId"],
            "wave1-010-ec8b158caf64",
        )
        self.assertIsNone(failure["failedTupleOrder"])
        self.assertIsNone(failure["failedResourceKind"])
        self.assertEqual(
            failure["claimRawSha256"],
            CHECKER.V2_CLAIM_RAW_SHA256,
        )

    def test_33_each_v2_historical_raw_binding_rejects_drift(self) -> None:
        for path, label in (
            (CHECKER.V2_PERMIT_PATH, "v2 permit raw"),
            (CHECKER.V2_CLAIM_PATH, "v2 claim raw"),
            (CHECKER.V2_FAILURE_PATH, "v2 failure raw"),
        ):
            with self.subTest(path=path):
                raw = dict(self.raw)
                raw[path] += b" "
                with self.assertRaisesRegex(CHECKER.PermitError, label):
                    CHECKER.validate_v2_failed_attempt(raw)

    def test_34_v2_success_and_readback_absence_is_enforced(self) -> None:
        result = self.root / CHECKER.V2_RESULT_PATH
        result.write_bytes(b"v2 success backfill forbidden\n")
        result.chmod(0o600)
        with self.assertRaisesRegex(
            CHECKER.PermitError,
            "v2 failed-attempt namespace",
        ):
            CHECKER.validate_repository(self.root)
        result.unlink()

        readback = self.root / CHECKER.V2_READBACK_RECEIPT_PATH
        collision = readback.with_name(readback.name.upper())
        collision.write_bytes(b"v2 readback collision forbidden\n")
        collision.chmod(0o600)
        with self.assertRaisesRegex(
            CHECKER.PermitError,
            "v2 failed-attempt namespace",
        ):
            CHECKER.validate_repository(self.root)

    def test_35_selected_v3_correction_is_exactly_bound(self) -> None:
        correction = self.permit["selectedV3Correction"]
        self.assertTrue(correction["reviewFailureCaughtBeforeRuntimeError"])
        for field in (
            "reviewFailureCodePreserved",
            "reviewFailurePhasePreserved",
            "reviewFailureTupleIdPreserved",
            "reviewFailureTupleOrderPreserved",
            "reviewFailureResourceKindPreserved",
        ):
            with self.subTest(field=field):
                self.assertTrue(correction[field])
        self.assertIn(
            "module_prefix_and_safe_normalized_paths",
            correction["zipSafetyChecksUnchanged"],
        )
        self._mutate_and_rebind(
            lambda permit: permit["selectedV3Correction"].update(
                {"reviewFailureCodePreserved": False}
            )
        )
        with self.assertRaisesRegex(CHECKER.PermitError, "exact typed"):
            CHECKER.validate_repository(self.root)

    def test_36_recovery_records_root_cause_without_rewriting_v2(self) -> None:
        root_cause = self.recovery_decision["rootCause"]
        self.assertEqual(root_cause["underlyingFailureCode"], "E_IMPORT_PARSE")
        self.assertEqual(
            root_cause["underlyingFailurePhase"],
            "source_inventory",
        )
        self.assertEqual(root_cause["recordedFailureCode"], "E_ARCHIVE_STRUCTURE")
        self.assertEqual(root_cause["recordedFailurePhase"], "archive")
        self.assertFalse(root_cause["zipStructurePredicateFailureObserved"])
        recorded = self.recovery_decision["failedAttemptBindings"]["v2"]
        self.assertEqual(
            recorded["permit"]["rawSha256"],
            CHECKER.V2_PERMIT_RAW_SHA256,
        )
        self.assertEqual(
            recorded["failure"]["rawSha256"],
            CHECKER.V2_FAILURE_RAW_SHA256,
        )

    def test_37_recovery_v2_is_canonical_single_lf_json(self) -> None:
        raw = self.raw[CHECKER.RECOVERY_DECISION_PATH]
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"))
        self.assertEqual(
            raw,
            CHECKER.canonical_json_bytes(self.recovery_decision),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
