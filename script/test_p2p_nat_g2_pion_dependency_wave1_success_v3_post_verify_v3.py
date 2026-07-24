#!/usr/bin/env python3
"""Regression tests for the fixed-hash v3 readback post-verifier."""

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

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_dependency_wave1_success_v3_post_verify_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave1_success_v3_post_verify_v3_checker",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load post-verifier")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class DependencyWaveOneV3PostVerificationV3Tests(unittest.TestCase):
    def fixed_raw(self, relative: str) -> bytes:
        return CHECKER.ROOT.joinpath(relative).read_bytes()

    def test_01_v2_recovery_chain_remains_byte_exact(self) -> None:
        for relative, expected in (
            (CHECKER.V2_CHECKER_PATH, CHECKER.V2_CHECKER_RAW_SHA256),
            (CHECKER.V2_TESTS_PATH, CHECKER.V2_TESTS_RAW_SHA256),
            (CHECKER.V2_DECISION_PATH, CHECKER.V2_DECISION_RAW_SHA256),
        ):
            with self.subTest(relative=relative):
                self.assertEqual(
                    hashlib.sha256(self.fixed_raw(relative)).hexdigest(),
                    expected,
                )

    def test_02_exact_pretty_predecessors_pass_fixed_parser(self) -> None:
        for label, binding in CHECKER.RELAXED_PREDECESSOR_BINDINGS.items():
            with self.subTest(label=label):
                raw = self.fixed_raw(binding["path"])
                parsed = CHECKER.hardened_strict_json(raw, label)
                self.assertIs(type(parsed), dict)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), binding["rawSha256"])

    def test_03_canonicalized_predecessor_bypass_is_rejected(self) -> None:
        for label, binding in CHECKER.RELAXED_PREDECESSOR_BINDINGS.items():
            with self.subTest(label=label):
                raw = self.fixed_raw(binding["path"])
                canonical = CHECKER.LEGACY.canonical_json_bytes(json.loads(raw))
                self.assertNotEqual(hashlib.sha256(canonical).hexdigest(), binding["rawSha256"])
                with self.assertRaises(CHECKER.V2.RecoveryError):
                    CHECKER.hardened_strict_json(canonical, label)

    def test_04_generated_json_requires_fixed_sha_and_canonical_bytes(self) -> None:
        for label, binding in CHECKER.CANONICAL_ARTIFACT_BINDINGS.items():
            with self.subTest(label=label):
                raw = self.fixed_raw(binding["path"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), binding["rawSha256"])
                self.assertIs(type(CHECKER.hardened_strict_json(raw, label)), dict)
                with self.assertRaises(CHECKER.PostVerificationError):
                    CHECKER.hardened_strict_json(raw[:-1] + b" \n", label)

    def test_05_unbound_parser_labels_fail_closed(self) -> None:
        with self.assertRaises(CHECKER.PostVerificationError):
            CHECKER.hardened_strict_json(b"{}\n", "unexpected label")

    def test_06_decision_validation_rejects_boolean_integer_confusion(self) -> None:
        checker_sha = hashlib.sha256(CHECKER_PATH.read_bytes()).hexdigest()
        tests_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        expected = CHECKER.expected_post_verification_decision(
            checker_sha,
            tests_sha,
        )
        decision = copy.deepcopy(expected)
        decision["contentBinding"] = {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": "decision_without_contentBinding",
            "sha256": CHECKER.sha256_bytes(
                CHECKER.LEGACY.canonical_json_bytes(expected)
            ),
        }
        decision["authorization"]["postVerificationAuthorized"] = 1
        self.assertEqual(
            decision["authorization"]["postVerificationAuthorized"],
            expected["authorization"]["postVerificationAuthorized"],
        )
        with self.assertRaises(CHECKER.PostVerificationError):
            CHECKER.validate_decision_document(decision, expected)
        rebound = copy.deepcopy(decision)
        without_binding = dict(rebound)
        without_binding.pop("contentBinding")
        rebound["contentBinding"]["sha256"] = CHECKER.sha256_bytes(
            CHECKER.LEGACY.canonical_json_bytes(without_binding)
        )
        with self.assertRaises(CHECKER.PostVerificationError):
            CHECKER.validate_decision_document(rebound, expected)

    def test_07_post_verification_decision_is_exact_and_no_auth(self) -> None:
        decision = CHECKER.validate_post_verification_authority(CHECKER.ROOT)
        self.assertEqual(
            decision["decisionId"],
            CHECKER.POST_VERIFICATION_DECISION_ID,
        )
        authority = decision["authorization"]
        self.assertTrue(authority["postVerificationAuthorized"])
        self.assertFalse(authority["readbackRecordAuthorized"])
        self.assertFalse(authority["acquisitionRetryAuthorized"])
        self.assertFalse(authority["externalAuthenticationRequired"])
        self.assertFalse(authority["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(authority["userActionRequired"])

    def test_08_complete_readback_is_verified_without_writes(self) -> None:
        output_paths = (
            CHECKER.ROOT / CHECKER.V2.READBACK_RECEIPT_PATH,
            CHECKER.ROOT / CHECKER.V2.READBACK_MANIFEST_PATH,
        )
        before = [path.read_bytes() for path in output_paths]
        state = CHECKER.validate_state(CHECKER.ROOT)
        after = [path.read_bytes() for path in output_paths]
        self.assertEqual(before, after)
        self.assertEqual(state["status"], "independent_readback_complete")
        self.assertEqual(state["observedRegularFileCount"], 43)
        self.assertEqual(state["retainedResourceCount"], 38)
        self.assertEqual(state["retainedZipCount"], 19)
        self.assertEqual(state["retainedModCount"], 19)
        self.assertEqual(state["networkOperationCount"], 0)
        self.assertEqual(state["fileWriteCount"], 0)
        self.assertTrue(state["verificationOnly"])
        self.assertFalse(state["recordModeExposed"])
        self.assertFalse(state["externalAuthenticationRequired"])
        self.assertFalse(state["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(state["userActionRequired"])

    def test_09_post_verifier_has_no_record_surface_or_network_import(self) -> None:
        self.assertFalse(hasattr(CHECKER, "record_readback"))
        self.assertFalse(hasattr(CHECKER, "urllib"))
        self.assertFalse(hasattr(CHECKER, "socket"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
