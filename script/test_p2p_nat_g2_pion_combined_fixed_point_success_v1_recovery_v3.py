#!/usr/bin/env python3
"""Tests for the one-use replacement recovery recorder v3."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (sys.flags.isolated and sys.flags.dont_write_bytecode and sys.flags.no_site):
    raise RuntimeError("tests require `python3 -I -B -S`")

import copy
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest import mock


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_combined_fixed_point_success_v1_recovery_v3.py"
)
SPEC = importlib.util.spec_from_file_location("recovery_recorder_v3", PATH)
assert SPEC and SPEC.loader
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class RecoveryRecorderV3Tests(unittest.TestCase):
    def exercise_record(self, failure: str | None = None):
        events = []
        writes = {}
        attempts = []
        counts = {
            "fresh": 0,
            "generate": 0,
            "validate_failure": 0,
            "claim_guard_faulted": 0,
            "post_claim_barrier_faulted": 0,
        }

        class Context:
            def __init__(self, *_args, **_kwargs):
                self.phase = "recordable"

            def final_barrier(self, phase):
                events.append(("barrier", phase))
                if (
                    failure == "post_claim_barrier"
                    and phase == "after_claim"
                    and counts["post_claim_barrier_faulted"] == 0
                ):
                    counts["post_claim_barrier_faulted"] += 1
                    raise RuntimeError("post-claim barrier fault")

            def close(self):
                events.append(("context_close", self.phase))

        class Guard:
            def __init__(self, paths):
                self.raw = {path: writes[path] for path in paths}

            def final_barrier(self):
                events.append(("guard_barrier", tuple(self.raw)))

            def close(self):
                events.append(("guard_close", tuple(self.raw)))

        checker = SimpleNamespace(
            PermitContext=Context,
            V3_CLAIM_PATH="claim",
            V3_RECEIPT_PATH="receipt",
            V3_FAILURE_PATH="failure",
            V3_MANIFEST_PATH="manifest",
            canonical_bytes=lambda value: (
                json.dumps(
                    value,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
                + b"\n"
            ),
            sha256=lambda raw: R.hashlib.sha256(raw).hexdigest(),
        )
        permit = {"permitId": "permit-v3"}

        def retained(
            context,
            _checker,
            path,
            raw,
            post_phase,
            durable_callback=None,
        ):
            context.final_barrier(context.phase)
            attempts.append(path)
            events.append(("write", path))
            if failure == "receipt_write" and path == "receipt":
                raise RuntimeError("receipt write fault")
            if failure == "manifest_write" and path == "manifest":
                raise RuntimeError("manifest write fault")
            writes[path] = raw
            if durable_callback is not None:
                durable_callback()
            context.final_barrier(post_phase)
            return checker.sha256(raw)

        def hold(_context, _checker, paths):
            if (
                failure == "claim_guard"
                and tuple(paths) == ("claim",)
                and counts["claim_guard_faulted"] == 0
            ):
                counts["claim_guard_faulted"] += 1
                raise RuntimeError("claim guard fault")
            return Guard(paths)

        def fresh(context, _checker):
            counts["fresh"] += 1
            if failure == "fresh":
                raise RuntimeError("fresh fault")
            counts["generate"] += 1
            events.append(("generate", context.phase))
            return {"graphSha256": "a" * 64}, {"newTupleCount": 16}

        def validate_failure(*_args):
            counts["validate_failure"] += 1

        payload = lambda kind: (lambda *_args: {"kind": kind})
        patches = (
            mock.patch.object(R, "bootstrap_permit_checker", return_value=checker),
            mock.patch.object(R, "observed_phase", return_value="recordable"),
            mock.patch.object(R, "validate_permit", return_value=permit),
            mock.patch.object(R, "claim_payload", payload("claim")),
            mock.patch.object(R, "receipt_payload", payload("receipt")),
            mock.patch.object(R, "manifest_payload", payload("manifest")),
            mock.patch.object(R, "failure_payload", payload("failure")),
            mock.patch.object(
                R,
                "bound_document",
                side_effect=lambda _checker, value, _scope: dict(value),
            ),
            mock.patch.object(R, "retained_write", side_effect=retained),
            mock.patch.object(R, "hold_outputs", side_effect=hold),
            mock.patch.object(R, "fresh_validate", side_effect=fresh),
            mock.patch.object(R, "validate_claim"),
            mock.patch.object(R, "validate_receipt"),
            mock.patch.object(R, "validate_manifest"),
            mock.patch.object(
                R, "validate_failure", side_effect=validate_failure
            ),
            mock.patch.object(R, "completed_documents"),
        )
        result = error = None
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            try:
                result = getattr(R, "record")(Path("."))
            except R.ReadbackError as caught:
                error = caught
        return SimpleNamespace(
            result=result,
            error=error,
            events=events,
            writes=writes,
            attempts=attempts,
            counts=counts,
        )

    def test_01_live_check_is_static_and_read_only(self) -> None:
        with mock.patch.object(
            R, "fresh_validate", side_effect=AssertionError("check recomputed")
        ) as fresh:
            result = R.check()
        fresh.assert_not_called()
        self.assertTrue(result["validationPassed"])
        self.assertTrue(result["recordable"])
        self.assertFalse(result["freshRecomputationPerformed"])
        self.assertEqual(result["archiveMemberDecodeCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)

    def test_02_exact_document_schemas_and_mutation_kills(self) -> None:
        checker = R.bootstrap_permit_checker(R.ROOT)
        context = checker.PermitContext(
            R.ROOT, include_permit=True, phase="recordable"
        )
        try:
            permit = R.validate_permit(context, checker)
            result, manifest = R.frozen_terminal(context, checker)
        finally:
            context.close()
        claim = R.bound_document(
            checker,
            R.claim_payload(permit, checker),
            "claim_without_contentBinding",
        )
        claim_raw = checker.canonical_bytes(claim)
        R.validate_claim(claim_raw, permit, checker)
        receipt = R.bound_document(
            checker,
            R.receipt_payload(
                permit, checker, claim_raw, result, manifest
            ),
            "receipt_without_contentBinding",
        )
        receipt_raw = checker.canonical_bytes(receipt)
        R.validate_receipt(
            receipt_raw, permit, checker, claim_raw, result, manifest
        )
        publication = R.bound_document(
            checker,
            R.manifest_payload(permit, checker, claim_raw, receipt_raw),
            "manifest_without_contentBinding",
        )
        R.validate_manifest(
            checker.canonical_bytes(publication),
            permit,
            checker,
            claim_raw,
            receipt_raw,
        )
        changed = copy.deepcopy(receipt)
        changed["graphSha256"] = "0" * 64
        payload = {key: value for key, value in changed.items() if key != "contentBinding"}
        changed = R.bound_document(checker, payload, "receipt_without_contentBinding")
        with self.assertRaises(R.ReadbackError):
            R.validate_receipt(
                checker.canonical_bytes(changed),
                permit,
                checker,
                claim_raw,
                result,
                manifest,
            )

    def test_03_exact_failure_code_stage_mapping_and_mutations(self) -> None:
        self.assertEqual(
            R.FAILURE_CODE_BY_STAGE,
            {
                "claim_guard": "E_V3_CLAIM_GUARD",
                "claim_validation": "E_V3_CLAIM_VALIDATION",
                "fresh_recompute": "E_V3_FRESH_RECOMPUTE",
                "receipt_materialization": "E_V3_RECEIPT_MATERIALIZATION",
            },
        )
        checker = R.bootstrap_permit_checker(R.ROOT)
        context = checker.PermitContext(
            R.ROOT, include_permit=True, phase="recordable"
        )
        try:
            permit = R.validate_permit(context, checker)
        finally:
            context.close()
        claim = R.bound_document(
            checker,
            R.claim_payload(permit, checker),
            "claim_without_contentBinding",
        )
        claim_raw = checker.canonical_bytes(claim)
        for code, stage in R.FAILURE_STAGE_BY_CODE.items():
            failure = R.bound_document(
                checker,
                R.failure_payload(code, stage, permit, checker, claim_raw),
                "failure_without_contentBinding",
            )
            R.validate_failure(
                claim_raw, checker.canonical_bytes(failure), permit, checker
            )
        with self.assertRaises(R.ReadbackError):
            R.failure_payload(
                "E_UNKNOWN", "fresh_recompute", permit, checker, claim_raw
            )

    def test_04_record_source_orders_claim_fresh_receipt_manifest(self) -> None:
        source = PATH.read_text(encoding="utf-8").split("def record(", 1)[1]
        claim = source.index("V3_CLAIM_PATH")
        fresh = source.index("fresh_validate(")
        receipt_attempted = source.index("receipt_attempted = True")
        receipt = source.index("V3_RECEIPT_PATH", receipt_attempted)
        manifest = source.index("V3_MANIFEST_PATH", receipt)
        self.assertLess(claim, fresh)
        self.assertLess(fresh, receipt_attempted)
        self.assertLess(receipt_attempted, receipt)
        self.assertLess(receipt, manifest)
        self.assertEqual(source.count("fresh_validate("), 1)

    def test_05_check_has_no_fresh_generate_or_write(self) -> None:
        source = PATH.read_text(encoding="utf-8").split("def check(", 1)[1].split(
            "def publish_failure(", 1
        )[0]
        self.assertNotIn("fresh_validate(", source)
        self.assertNotIn("generate_candidate(", source)
        self.assertNotIn("retained_write(", source)

    def test_06_retained_writer_rejects_named_parent_swap(self) -> None:
        checker = R.bootstrap_permit_checker(R.ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            (root / checker.DEPENDENCY_ROOT).mkdir(parents=True)
            (root / checker.BASE).mkdir(parents=True)
            namespace = checker.DECISION.V2.RECOVERY.TRUST.HeldNamespace(root)
            context = SimpleNamespace(
                namespace=namespace,
                phase="recordable",
                final_barrier=lambda phase: namespace.final_barrier(),
            )
            base = root / checker.BASE
            moved = base.with_name("held-base")
            try:
                base.rename(moved)
                base.mkdir()
                with self.assertRaises(Exception):
                    R.retained_write(
                        context,
                        checker,
                        checker.V3_RECEIPT_PATH,
                        b"{}\n",
                        "after_receipt",
                    )
            finally:
                base.rmdir()
                moved.rename(base)
                namespace.final_barrier()
                namespace.close()

    def test_07_no_retry_backfill_network_auth_or_git_surface(self) -> None:
        checker = R.bootstrap_permit_checker(R.ROOT)
        permit, _ = checker.evaluate(True)
        for key in (
            "automaticRetryAllowed",
            "resumeAllowed",
            "claimBackfillAllowed",
            "receiptBackfillAllowed",
            "manifestBackfillAllowed",
            "failureAfterReceiptAttemptAllowed",
        ):
            self.assertFalse(permit["oneUseContract"][key])
        source = PATH.read_text(encoding="utf-8")
        for token in ("urllib.", "socket.", "subprocess.", "os.system("):
            self.assertNotIn(token, source)

    def test_08_phase_shapes_are_mutually_exclusive(self) -> None:
        checker = R.bootstrap_permit_checker(R.ROOT)
        shapes = {
            checker.phase_shape(phase)
            for phase in (
                "recordable",
                "after_claim",
                "failure",
                "after_receipt",
                "complete",
            )
        }
        self.assertEqual(len(shapes), 5)
        for path in checker.V3_PATHS:
            self.assertFalse((R.ROOT / path).exists(), path)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=R.ROOT,
            capture_output=True,
            check=False,
        )

    def test_09_cli_check_and_invalid_are_canonical(self) -> None:
        checked = self.run_cli("--check")
        self.assertEqual(checked.returncode, 0)
        self.assertFalse(json.loads(checked.stdout)["freshRecomputationPerformed"])
        invalid = self.run_cli("--secret")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"secret", invalid.stdout)

    def test_10_no_live_record_is_invoked_by_tests(self) -> None:
        tests = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("--" + "record", tests)
        self.assertNotIn("R." + "record(", tests)

    def test_11_claim_guard_failure_reacquires_and_validates_failure_twice(self) -> None:
        run = self.exercise_record("claim_guard")
        self.assertEqual(tuple(run.writes), ("claim", "failure"))
        self.assertEqual(run.counts["claim_guard_faulted"], 1)
        self.assertEqual(run.counts["validate_failure"], 2)
        self.assertEqual(run.error.code, "E_INTERNAL")

    def test_12_post_claim_barrier_failure_keeps_durable_claim_state(self) -> None:
        run = self.exercise_record("post_claim_barrier")
        self.assertEqual(tuple(run.writes), ("claim", "failure"))
        self.assertEqual(run.counts["post_claim_barrier_faulted"], 1)
        self.assertEqual(run.counts["validate_failure"], 2)
        self.assertEqual(run.error.code, "E_INTERNAL")

    def test_13_fresh_failure_publishes_only_claim_and_failure(self) -> None:
        run = self.exercise_record("fresh")
        self.assertEqual(tuple(run.writes), ("claim", "failure"))
        self.assertEqual(run.counts["fresh"], 1)
        self.assertEqual(run.counts["generate"], 0)
        self.assertEqual(run.counts["validate_failure"], 2)
        self.assertEqual(run.error.code, "E_INTERNAL")

    def test_14_receipt_attempt_failure_forbids_failure_backfill(self) -> None:
        run = self.exercise_record("receipt_write")
        self.assertEqual(tuple(run.writes), ("claim",))
        self.assertEqual(run.attempts, ["claim", "receipt"])
        self.assertNotIn("failure", run.attempts)
        self.assertEqual(
            run.error.code,
            "E_V3_POST_RECEIPT_PUBLICATION_UNCERTAIN",
        )

    def test_15_manifest_failure_is_post_receipt_uncertain(self) -> None:
        run = self.exercise_record("manifest_write")
        self.assertEqual(tuple(run.writes), ("claim", "receipt"))
        self.assertEqual(run.attempts, ["claim", "receipt", "manifest"])
        self.assertNotIn("failure", run.attempts)
        self.assertEqual(
            run.error.code,
            "E_V3_POST_RECEIPT_PUBLICATION_UNCERTAIN",
        )

    def test_16_success_has_exactly_one_fresh_generate_and_ordered_writes(self) -> None:
        run = self.exercise_record()
        self.assertIsNone(run.error)
        self.assertEqual(run.counts["fresh"], 1)
        self.assertEqual(run.counts["generate"], 1)
        self.assertEqual(run.attempts, ["claim", "receipt", "manifest"])
        self.assertEqual(tuple(run.writes), ("claim", "receipt", "manifest"))
        self.assertLess(
            run.events.index(("write", "claim")),
            run.events.index(("generate", "after_claim")),
        )
        self.assertLess(
            run.events.index(("generate", "after_claim")),
            run.events.index(("write", "receipt")),
        )
        self.assertLess(
            run.events.index(("write", "receipt")),
            run.events.index(("write", "manifest")),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
