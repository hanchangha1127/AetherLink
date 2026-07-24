#!/usr/bin/env python3
"""Regression tests for the versioned wave-one v3 readback recovery reader."""

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

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_dependency_wave1_success_v3_recovery_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave1_success_v3_recovery_v2_checker",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load recovery checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class DependencyWaveOneV3ReadbackRecoveryV2Tests(unittest.TestCase):
    def fixed_raw(self, relative: str) -> bytes:
        return CHECKER.ROOT.joinpath(relative).read_bytes()

    def test_01_original_checker_and_tests_remain_byte_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(
                self.fixed_raw(CHECKER.ORIGINAL_CHECKER_PATH)
            ).hexdigest(),
            CHECKER.ORIGINAL_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                self.fixed_raw(CHECKER.ORIGINAL_TESTS_PATH)
            ).hexdigest(),
            CHECKER.ORIGINAL_TESTS_RAW_SHA256,
        )

    def test_02_exact_pretty_predecessors_are_the_only_relaxed_bytes(self) -> None:
        for label, binding in CHECKER.PREDECESSOR_BINDINGS.items():
            with self.subTest(label=label):
                raw = self.fixed_raw(binding["path"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), binding["rawSha256"])
                self.assertTrue(raw.endswith(b"\n"))
                self.assertFalse(raw.endswith(b"\n\n"))
                self.assertNotIn(b"\r", raw)
                with self.assertRaises(CHECKER.LEGACY.CheckError):
                    CHECKER.ORIGINAL_STRICT_JSON(raw, label)
                document = CHECKER.corrected_strict_json(raw, label)
                self.assertIs(type(document), dict)
                self.assertEqual(
                    document["contentBinding"]["sha256"],
                    binding["contentSha256"],
                )

    def test_03_raw_drift_duplicate_nonfinite_bom_and_lf_are_rejected(self) -> None:
        label = "source decision"
        binding = CHECKER.PREDECESSOR_BINDINGS[label]
        raw = self.fixed_raw(binding["path"])
        mutations = {
            "raw-drift": raw[:-1] + b" \n",
            "duplicate": b'{"x":1,"x":2}\n',
            "nonfinite": b'{"x":NaN}\n',
            "bom": b"\xef\xbb\xbf" + raw,
            "missing-lf": raw[:-1],
            "double-lf": raw + b"\n",
            "crlf": raw.replace(b"\n", b"\r\n", 1),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                with self.assertRaises(CHECKER.RecoveryError):
                    CHECKER.parse_exact_bound_predecessor(mutation, label)

    def test_04_generated_artifacts_keep_compact_canonical_contract(self) -> None:
        claim_raw = self.fixed_raw(CHECKER.CLAIM_PATH)
        claim = CHECKER.corrected_strict_json(claim_raw, "v3 claim")
        pretty = (
            json.dumps(claim, ensure_ascii=True, indent=2) + "\n"
        ).encode("utf-8")
        with self.assertRaises(CHECKER.LEGACY.CheckError):
            CHECKER.corrected_strict_json(pretty, "v3 claim")

    def test_05_recovery_decision_is_exact_and_needs_no_user_auth(self) -> None:
        decision = CHECKER.validate_recovery_authority(CHECKER.ROOT)
        self.assertEqual(decision["decisionId"], CHECKER.RECOVERY_DECISION_ID)
        authority = decision["authorization"]
        self.assertTrue(authority["recordReadbackAuthorized"])
        self.assertFalse(authority["acquisitionRetryAuthorized"])
        self.assertFalse(authority["externalAuthenticationRequired"])
        self.assertFalse(authority["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(authority["userActionRequired"])

    def test_06_preflight_validates_the_complete_acquisition_read_only(self) -> None:
        output_paths = (
            CHECKER.ROOT / CHECKER.READBACK_RECEIPT_PATH,
            CHECKER.ROOT / CHECKER.READBACK_MANIFEST_PATH,
        )
        before = [
            (path.exists(), path.read_bytes() if path.exists() else None)
            for path in output_paths
        ]
        state = CHECKER.validate_state(CHECKER.ROOT)
        after = [
            (path.exists(), path.read_bytes() if path.exists() else None)
            for path in output_paths
        ]
        self.assertEqual(before, after)
        self.assertIn(
            state["status"],
            {"acquired_pending_independent_readback", "independent_readback_complete"},
        )
        self.assertEqual(state["retainedResourceCount"], 38)
        self.assertEqual(state["networkOperationCount"], 0)
        self.assertEqual(state["fileWriteCount"], 0)
        self.assertFalse(state["externalAuthenticationRequired"])
        self.assertFalse(state["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(state["userActionRequired"])

    def test_07_source_recovery_and_permit_semantics_still_validate(self) -> None:
        state = CHECKER.validate_state(CHECKER.ROOT)
        self.assertEqual(
            state["orderedSourceSetSha256"],
            CHECKER.ORDERED_SOURCE_SET_SHA256,
        )
        self.assertEqual(state["retainedZipCount"], 19)
        self.assertEqual(state["retainedModCount"], 19)

    def test_08_recovery_reader_does_not_expose_network_primitives(self) -> None:
        self.assertFalse(hasattr(CHECKER, "urllib"))
        self.assertFalse(hasattr(CHECKER, "socket"))
        state = CHECKER.validate_state(CHECKER.ROOT)
        self.assertEqual(state["networkOperationCount"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
