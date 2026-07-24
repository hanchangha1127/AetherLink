#!/usr/bin/env python3
"""Offline tests for the one-use combined fixed-point runner."""

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
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock


RUNNER_PATH = (
    Path(__file__).resolve().parent
    / "run_p2p_nat_g2_pion_combined_fixed_point_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location(
    "combined_fixed_point_runner_v1",
    RUNNER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load runner")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class FakePermit:
    CLAIM_PATH = "out/claim.json"
    RESULT_PATH = "out/result.json"
    FAILURE_PATH = "out/failure.json"
    MANIFEST_PATH = "out/manifest.json"
    READBACK_CLAIM_PATH = "out/rb-claim.json"
    READBACK_RECEIPT_PATH = "out/rb-receipt.json"
    READBACK_FAILURE_PATH = "out/rb-failure.json"
    READBACK_MANIFEST_PATH = "out/rb-manifest.json"


class Capture:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


class FakeGuard:
    def __init__(self, raw: dict[str, bytes] | None = None) -> None:
        self.raw = raw or {}

    def final_barrier(self) -> None:
        return None

    def close(self) -> None:
        return None


def fake_candidate() -> dict:
    closure = {
        "dependencyFixedPointReached": False,
        "dependencySourceReviewed": False,
        "dependencyClosureComplete": False,
        "semanticClosureComplete": False,
        "licenseCompatibilityReviewed": False,
        "securityReviewComplete": False,
        "rungThreeComplete": False,
        "candidateSelected": False,
        "librarySelected": False,
        "releaseReady": False,
    }
    candidate = {
        "inputSet": {"combinedInputSetSha256": "1" * 64},
        "terminalEvidenceBindings": [],
        "coverage": {},
        "profiles": [],
        "graphDiscovery": {
            "fixedPointReached": False,
            "newTupleCount": 16,
            "graphSha256": "2" * 64,
        },
        "checkerVerification": {},
        "route": "next_wave_required",
        "nextAction": "new_wave",
        "operationCounters": {},
        "closure": closure,
        "contentBinding": {"sha256": "3" * 64},
    }
    return candidate


class CombinedFixedPointRunnerTests(unittest.TestCase):
    @staticmethod
    def load_local_module(name: str, filename: str) -> object:
        path = RUNNER_PATH.parent / filename
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {filename}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def actual_failure_transaction(
        self,
        root: Path,
        *,
        mutation: str | None = None,
        semantic_tamper: bool = False,
    ) -> tuple[object, object, object, bytes, dict, dict]:
        permit_module = self.load_local_module(
            "permit_for_actual_runner_failure",
            (
                "check_p2p_nat_g2_pion_combined_fixed_point_"
                "execution_permit_v1.py"
            ),
        )
        decision_module = self.load_local_module(
            "decision_for_actual_runner_failure",
            "check_p2p_nat_g2_pion_combined_fixed_point_decision_v1.py",
        )
        (root / permit_module.DEPENDENCY_ROOT).mkdir(parents=True)
        (root / permit_module.BASE).mkdir(parents=True)
        os.chmod(root, 0o700)
        namespace = decision_module.HeldNamespace(root)
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
            "sourceInputSet": {
                "decisionHeldBindingSetSha256": "b" * 64,
            },
        }
        decision = {
            "decisionId": "decision",
            "contentBinding": {"sha256": "c" * 64},
        }
        claim = runner.claim_document(permit, decision)
        claim_raw = runner.canonical_bytes(claim)
        runner.write_exclusive(
            root,
            permit_module.CLAIM_PATH,
            claim_raw,
        )
        claim_guard = decision_module.HeldSet(
            root,
            [
                {
                    "path": permit_module.CLAIM_PATH,
                    "rawSha256": runner.sha256(claim_raw),
                    "maximumBytes": runner.MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )

        def mutate_after_failure_open() -> None:
            dependency = root / permit_module.DEPENDENCY_ROOT
            base = root / permit_module.BASE
            failure_path = root / permit_module.FAILURE_PATH
            if mutation == "staging":
                (
                    dependency
                    / f"{permit_module.STAGING_PREFIX}post-failure"
                ).mkdir()
            elif mutation == "parent_swap":
                base.rename(base.with_name("rung-three-old"))
                base.mkdir(parents=True)
            elif mutation == "failure_truncate":
                failure_path.write_bytes(b"{}\n")
            elif mutation == "failure_tamper":
                raw = failure_path.read_bytes()
                failure_path.write_bytes(raw.replace(b"false", b"true ", 1))
            elif mutation == "failure_postopen_mode":
                os.chmod(failure_path, 0o640)
            elif mutation == "failure_nlink":
                os.link(failure_path, base / "failure-hardlink")
            elif mutation == "claim_mutation":
                claim_path = root / permit_module.CLAIM_PATH
                claim_path.write_bytes(b"{}\n")
            elif mutation == "terminal_collision_result":
                runner.write_exclusive(
                    root,
                    permit_module.RESULT_PATH,
                    runner.canonical_bytes({"collision": "result"}),
                )
            elif mutation == "terminal_collision_manifest":
                runner.write_exclusive(
                    root,
                    permit_module.MANIFEST_PATH,
                    runner.canonical_bytes({"collision": "manifest"}),
                )

        real_held_set = decision_module.HeldSet
        metrics = {
            "failureOwnerOnly": None,
            "failureHeldSetOpened": 0,
        }

        def held_set(
            held_root: Path,
            bindings: object,
        ) -> object:
            is_failure = any(
                binding["path"] == permit_module.FAILURE_PATH
                for binding in bindings
            )
            if is_failure:
                metrics["failureOwnerOnly"] = all(
                    binding["ownerOnly"] is True
                    for binding in bindings
                )
                if mutation == "preopen_mode":
                    os.chmod(
                        root / permit_module.FAILURE_PATH,
                        0o640,
                    )
            held = real_held_set(held_root, bindings)
            if is_failure:
                metrics["failureHeldSetOpened"] += 1
                mutate_after_failure_open()
            return held

        context = types.SimpleNamespace(
            namespace=namespace,
            decision_checker=types.SimpleNamespace(HeldSet=held_set),
        )
        context.namespace_barrier = lambda: (
            permit_module.AuthorityContext.namespace_barrier(context)
        )
        context.final_barrier = lambda: context.namespace_barrier()
        failure = runner.failure_document(
            runner.RunnerError("E_INJECTED", "evaluation"),
            permit,
            decision,
            claim_raw,
        )
        if semantic_tamper:
            failure["decisionId"] = "other-decision"
            failure = runner.content_bound(failure)
        return (
            permit_module,
            context,
            claim_guard,
            claim_raw,
            failure,
            {
                "permit": permit,
                "decision": decision,
                "metrics": metrics,
            },
        )

    def execution_harness(
        self,
        *,
        graph_error: Exception | None = None,
        guard_error: Exception | None = None,
    ) -> tuple[object, list[tuple[str, bytes]], object]:
        writes: list[tuple[str, bytes]] = []
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "5" * 64},
            "decisionBinding": {"rawSha256": "4" * 64},
            "candidateProviderBinding": {},
            "immutableGraphProviderBinding": {},
            "sourceInputSet": {
                "decisionHeldBindingSetSha256": "7" * 64,
                "candidateSourceProjectionSha256": "1" * 64,
            },
        }
        decision = {
            "decisionId": "decision",
            "contentBinding": {"sha256": "6" * 64},
        }

        class HeldFactory:
            calls = 0

            def __call__(self, root: Path, bindings: object) -> FakeGuard:
                del root
                self.calls += 1
                if self.calls == 1 and guard_error is not None:
                    raise guard_error
                paths = [binding["path"] for binding in bindings]
                return FakeGuard(
                    {
                        path: next(
                            raw
                            for written_path, raw in reversed(writes)
                            if written_path == path
                        )
                        for path in paths
                    }
                )

        held_factory = HeldFactory()

        def generate(root: Path) -> dict:
            del root
            if graph_error is not None:
                raise graph_error
            return fake_candidate()

        context = types.SimpleNamespace(
            static=types.SimpleNamespace(raw={"permit.json": b"permit\n"}),
            decision=decision,
            decision_checker=types.SimpleNamespace(HeldSet=held_factory),
            candidate=types.SimpleNamespace(generate_candidate=generate),
            final_barrier=lambda: None,
            namespace_barrier=lambda: None,
            close=lambda: None,
        )
        permit_checker = types.SimpleNamespace(
            **{
                name: getattr(FakePermit, name)
                for name in (
                    "CLAIM_PATH",
                    "RESULT_PATH",
                    "FAILURE_PATH",
                    "MANIFEST_PATH",
                    "READBACK_CLAIM_PATH",
                    "READBACK_RECEIPT_PATH",
                    "READBACK_FAILURE_PATH",
                    "READBACK_MANIFEST_PATH",
                )
            },
            PERMIT_PATH="permit.json",
            open_authority_context=lambda *args, **kwargs: context,
            expected_payload=lambda value: {},
            content_bound=lambda value: value,
            validate_permit_bytes=lambda raw, expected: permit,
            validate_reverse_pins=lambda value: None,
            validate_namespace_absent=lambda root: None,
        )

        def write(root: Path, path: str, raw: bytes) -> str:
            del root
            writes.append((path, raw))
            return runner.sha256(raw)

        return permit_checker, writes, write

    def test_01_live_preflight_only(self) -> None:
        result = runner.preflight(runner.ROOT)
        self.assertTrue(result["validationPassed"])
        self.assertEqual(result["oneUseState"], "clean")
        self.assertEqual(result["heldSourceInputCount"], 69)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertEqual(result["networkOperationCount"], 0)

    def test_02_state_machine_classifies_terminal_sets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            out.mkdir()
            self.assertEqual(
                runner.classify_state(root, FakePermit)[0],
                "clean",
            )
            for name in ("claim.json", "result.json", "manifest.json"):
                (out / name).write_bytes(b"x")
            self.assertEqual(
                runner.classify_state(root, FakePermit)[0],
                "success_pending_readback",
            )
            for name in ("rb-claim.json", "rb-receipt.json", "rb-manifest.json"):
                (out / name).write_bytes(b"x")
            self.assertEqual(
                runner.classify_state(root, FakePermit)[0],
                "readback_complete",
            )
            (out / "failure.json").write_bytes(b"x")
            self.assertEqual(
                runner.classify_state(root, FakePermit)[0],
                "blocked",
            )

    def test_03_residue_and_collision_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            out.mkdir()
            (out / "result.json").write_bytes(b"x")
            self.assertEqual(
                runner.classify_state(root, FakePermit)[0],
                "blocked",
            )
            raw = b'{"x":1}\n'
            runner.write_exclusive(root, "out/new.json", raw)
            self.assertEqual(
                stat.S_IMODE((out / "new.json").stat().st_mode),
                0o600,
            )
            with self.assertRaises(runner.RunnerError) as caught:
                runner.write_exclusive(root, "out/new.json", raw)
            self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_04_projection_is_exact_and_missing_fields_fail(self) -> None:
        candidate = fake_candidate()
        projection = runner.candidate_projection(candidate)
        self.assertEqual(set(projection), set(runner.PROJECTION_FIELDS))
        del candidate["coverage"]
        with self.assertRaises(runner.RunnerError) as caught:
            runner.candidate_projection(candidate)
        self.assertEqual(caught.exception.code, "E_CANDIDATE")

    def test_05_result_preserves_frontier_and_all_nonclaims(self) -> None:
        candidate = fake_candidate()
        permit = {
            "decisionBinding": {"rawSha256": "4" * 64},
            "permitId": "permit",
            "contentBinding": {"sha256": "5" * 64},
            "candidateProviderBinding": {},
            "immutableGraphProviderBinding": {},
            "sourceInputSet": {
                "decisionHeldBindingSetSha256": "7" * 64,
                "candidateSourceProjectionSha256": "1" * 64,
            },
        }
        decision = {
            "decisionId": "decision",
            "contentBinding": {"sha256": "6" * 64},
        }
        result = runner.result_document(
            candidate,
            permit,
            decision,
            b"claim\n",
        )
        self.assertFalse(result["fixedPointReached"])
        self.assertEqual(
            result["candidateProjection"]["graphDiscovery"][
                "newTupleCount"
            ],
            16,
        )
        for key in (
            "dependencySourceReviewed",
            "semanticClosureComplete",
            "rungThreeComplete",
            "candidateSelected",
            "librarySelected",
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "subprocessUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ):
            self.assertFalse(result[key])
        without = dict(result)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            hashlib.sha256(runner.canonical_bytes(without)).hexdigest(),
        )

    def test_06_claim_is_consuming_and_authentication_free(self) -> None:
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
            "sourceInputSet": {
                "decisionHeldBindingSetSha256": "b" * 64,
            },
        }
        decision = {
            "decisionId": "decision",
            "contentBinding": {"sha256": "c" * 64},
        }
        claim = runner.claim_document(permit, decision)
        self.assertTrue(
            claim[
                "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode"
            ]
        )
        self.assertFalse(claim["automaticRetryAllowed"])
        self.assertFalse(claim["externalAuthenticationRequired"])
        self.assertFalse(claim["userActionRequired"])

    def test_07_error_document_never_authorizes_retry_or_auth(self) -> None:
        error = runner.error_document(
            runner.RunnerError("E_TEST", "evaluation")
        )
        self.assertFalse(error["automaticRetryAllowed"])
        self.assertFalse(error["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(error["externalAuthenticationRequired"])
        self.assertFalse(error["signatureRequired"])
        self.assertFalse(error["privateKeyRequired"])
        self.assertFalse(error["tokenRequired"])
        self.assertFalse(error["passwordRequired"])
        self.assertFalse(error["userActionRequired"])

    def test_08_claim_precedes_graph_and_manifest_is_last(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        claim_write = source.index(
            "write_exclusive(root, permit_checker.CLAIM_PATH"
        )
        graph = source.index("context.candidate.generate_candidate(root)")
        result = source.index(
            "write_exclusive(root, permit_checker.RESULT_PATH"
        )
        manifest = source.index(
            "permit_checker.MANIFEST_PATH,\n            manifest_raw"
        )
        self.assertLess(claim_write, graph)
        self.assertLess(graph, result)
        self.assertLess(result, manifest)
        self.assertIn("result_attempted = True", source)
        self.assertIn("E_POST_RESULT_PUBLICATION_UNCERTAIN", source)

    def test_08a_claim_guard_and_graph_failures_publish_bound_failure(
        self,
    ) -> None:
        for guard_error, graph_error in (
            (RuntimeError("guard"), None),
            (None, RuntimeError("graph")),
        ):
            with self.subTest(
                guard_error=guard_error is not None,
                graph_error=graph_error is not None,
            ):
                permit_checker, writes, write = self.execution_harness(
                    guard_error=guard_error,
                    graph_error=graph_error,
                )
                with (
                    mock.patch.object(
                        runner,
                        "bootstrap_permit_checker",
                        return_value=permit_checker,
                    ),
                    mock.patch.object(
                        runner,
                        "write_exclusive",
                        side_effect=write,
                    ),
                    mock.patch.object(
                        runner,
                        "require_execution_namespace",
                        return_value=None,
                    ),
                ):
                    with self.assertRaises(runner.RunnerError):
                        runner.execute_once(Path("/unused"))
                self.assertEqual(
                    [path for path, _ in writes],
                    [FakePermit.CLAIM_PATH, FakePermit.FAILURE_PATH],
                )
                failure = runner.json.loads(writes[-1][1])
                self.assertEqual(
                    failure["claimRawSha256"],
                    runner.sha256(writes[0][1]),
                )
                self.assertEqual(failure["permitId"], "permit")
                self.assertFalse(failure["automaticRetryAllowed"])
                rebound = dict(failure)
                binding = rebound.pop("contentBinding")
                self.assertEqual(
                    binding["sha256"],
                    runner.sha256(runner.canonical_bytes(rebound)),
                )

    def test_08b_result_and_manifest_failures_never_backfill(self) -> None:
        for failed_path in (
            FakePermit.RESULT_PATH,
            FakePermit.MANIFEST_PATH,
        ):
            with self.subTest(failed_path=failed_path):
                permit_checker, writes, base_write = (
                    self.execution_harness()
                )

                def failing_write(
                    root: Path,
                    path: str,
                    raw: bytes,
                ) -> str:
                    digest = base_write(root, path, raw)
                    if path == failed_path:
                        raise runner.RunnerError(
                            "E_INJECTED",
                            "publication",
                        )
                    return digest

                with (
                    mock.patch.object(
                        runner,
                        "bootstrap_permit_checker",
                        return_value=permit_checker,
                    ),
                    mock.patch.object(
                        runner,
                        "write_exclusive",
                        side_effect=failing_write,
                    ),
                    mock.patch.object(
                        runner,
                        "require_execution_namespace",
                        return_value=None,
                    ),
                ):
                    with self.assertRaises(runner.RunnerError) as caught:
                        runner.execute_once(Path("/unused"))
                self.assertEqual(
                    caught.exception.code,
                    "E_POST_RESULT_PUBLICATION_UNCERTAIN",
                )
                self.assertNotIn(
                    FakePermit.FAILURE_PATH,
                    [path for path, _ in writes],
                )

    def test_09_static_surface_has_no_network_or_source_execution(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "socket",
                    "subprocess",
                    "urllib",
                    "http",
                    "ftplib",
                    "requests",
                    "ssl",
                    "zipfile",
                }
            )
        )
        for forbidden in (
            ".extract(",
            ".extractall(",
            "os.system(",
            "os.popen(",
            "os.fork(",
            "os.spawn",
            "eval(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(source.count("exec("), 1)

    def test_10_cli_defaults_and_errors_are_canonical(self) -> None:
        args = runner.parse_arguments([])
        self.assertFalse(args.execute)
        self.assertFalse(args.preflight)
        self.assertTrue(runner.parse_arguments(["--execute"]).execute)
        for argv in (
            ["--record"],
            ["--root", "/tmp"],
            ["--output", "x"],
            ["--preflight", "--execute"],
        ):
            with self.subTest(argv=argv):
                capture = Capture()
                stderr = io.StringIO()
                with (
                    mock.patch.object(sys, "stdout", capture),
                    mock.patch.object(sys, "stderr", stderr),
                ):
                    self.assertEqual(runner.main(argv), 1)
                expected = runner.canonical_bytes(
                    runner.error_document(
                        runner.RunnerError("E_ARGUMENTS", "cli")
                    )
                )
                self.assertEqual(capture.buffer.getvalue(), expected)
                self.assertEqual(stderr.getvalue(), "")
        for isolated, side_effect, code, phase in (
            (False, None, "E_INTERPRETER", "cli"),
            (True, RuntimeError("unknown"), "E_INTERNAL", "runner"),
        ):
            capture = Capture()
            stderr = io.StringIO()
            with (
                mock.patch.object(sys, "stdout", capture),
                mock.patch.object(sys, "stderr", stderr),
                mock.patch.object(
                    runner,
                    "isolated_interpreter",
                    return_value=isolated,
                ),
                mock.patch.object(
                    runner,
                    "preflight",
                    side_effect=side_effect,
                ),
            ):
                self.assertEqual(runner.main([]), 1)
            expected = runner.canonical_bytes(
                runner.error_document(runner.RunnerError(code, phase))
            )
            self.assertEqual(capture.buffer.getvalue(), expected)
            self.assertEqual(stderr.getvalue(), "")

    def test_11_phase_specific_namespace_rejects_concurrent_residue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            out.mkdir()
            (out / "claim.json").write_bytes(b"x")
            runner.require_execution_namespace(
                root,
                FakePermit,
                "after_claim",
            )
            (out / "result.json").write_bytes(b"x")
            runner.require_execution_namespace(
                root,
                FakePermit,
                "after_result",
            )
            (out / "manifest.json").write_bytes(b"x")
            runner.require_execution_namespace(
                root,
                FakePermit,
                "success",
            )
            (out / "failure.json").write_bytes(b"x")
            with self.assertRaises(runner.RunnerError) as caught:
                runner.require_execution_namespace(
                    root,
                    FakePermit,
                    "success",
                )
            self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_12_claim_guard_failure_still_publishes_failure(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn("claim_written = True", source)
        self.assertIn(
            "if claim_written and not result_attempted:",
            source,
        )

    def test_13_real_held_output_named_replacement_fails_barrier(
        self,
    ) -> None:
        decision_path = (
            RUNNER_PATH.parent
            / "check_p2p_nat_g2_pion_combined_fixed_point_decision_v1.py"
        )
        spec = importlib.util.spec_from_file_location(
            "combined_decision_for_runner_barrier_test",
            decision_path,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        decision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(decision)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            output = root / "held.json"
            output.write_bytes(b'{"held":true}\n')
            os.chmod(output, 0o600)
            held = decision.HeldSet(
                root,
                [
                    {
                        "path": "held.json",
                        "rawSha256": hashlib.sha256(
                            output.read_bytes()
                        ).hexdigest(),
                        "maximumBytes": 1024,
                        "ownerOnly": True,
                    }
                ],
            )
            try:
                output.rename(root / "held-old.json")
                output.write_bytes(b'{"held":true}\n')
                os.chmod(output, 0o600)
                with self.assertRaises(Exception):
                    held.final_barrier()
            finally:
                held.close()

    def test_14_terminal_shape_requires_semantic_readback_validation(
        self,
    ) -> None:
        context = types.SimpleNamespace(
            static=types.SimpleNamespace(raw={"readback.py": b"tool\n"}),
            final_barrier=lambda: None,
            close=lambda: None,
        )
        output = {
            "validationPassed": False,
            "terminalRecognized": False,
        }
        permit_checker = types.SimpleNamespace(
            READBACK_CHECKER_PATH="readback.py",
            open_authority_context=lambda *args, **kwargs: context,
            execute_module=lambda *args: types.SimpleNamespace(
                read_only_check=lambda root: output
            ),
        )
        with self.assertRaises(runner.RunnerError) as caught:
            runner.validate_terminal_with_readback(
                Path("/unused"),
                permit_checker,
            )
        self.assertEqual(caught.exception.code, "E_TERMINAL")
        output["validationPassed"] = True
        output["terminalRecognized"] = True
        runner.validate_terminal_with_readback(
            Path("/unused"),
            permit_checker,
        )

    def test_15_actual_failure_transaction_reopens_and_validates(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (
                permit_module,
                context,
                claim_guard,
                claim_raw,
                failure,
                bindings,
            ) = self.actual_failure_transaction(root)
            failure_guard = None
            try:
                failure_guard = runner.publish_failure_transaction(
                    root,
                    permit_module,
                    context,
                    claim_guard,
                    claim_raw,
                    failure,
                    bindings["permit"],
                    bindings["decision"],
                )
                actual = runner.validate_failure_bytes(
                    claim_guard.raw[permit_module.CLAIM_PATH],
                    failure_guard.raw[permit_module.FAILURE_PATH],
                    bindings["permit"],
                    bindings["decision"],
                )
                self.assertEqual(actual["failureCode"], "E_INJECTED")
                self.assertEqual(
                    runner.classify_state(root, permit_module)[0],
                    "consumed_failure",
                )
            finally:
                if failure_guard is not None:
                    failure_guard.close()
                claim_guard.close()
                context.namespace.close()

    def test_16_actual_failure_transaction_rejects_post_publish_changes(
        self,
    ) -> None:
        cases = (
            "staging",
            "parent_swap",
            "preopen_mode",
            "claim_mutation",
            "terminal_collision_result",
            "terminal_collision_manifest",
            "failure_truncate",
            "failure_tamper",
            "failure_postopen_mode",
            "failure_nlink",
            "semantic",
            "late_staging",
        )
        for case in cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (
                        permit_module,
                        context,
                        claim_guard,
                        claim_raw,
                        failure,
                        bindings,
                    ) = self.actual_failure_transaction(
                        root,
                        mutation=(
                            None
                            if case in {"semantic", "late_staging"}
                            else case
                        ),
                        semantic_tamper=case == "semantic",
                    )
                    real_require = runner.require_execution_namespace
                    phase_calls: list[str] = []
                    namespace_calls = 0
                    real_namespace_barrier = context.namespace_barrier

                    def counted_namespace_barrier() -> None:
                        nonlocal namespace_calls
                        namespace_calls += 1
                        real_namespace_barrier()

                    context.namespace_barrier = counted_namespace_barrier

                    def counted_require(*args: object) -> None:
                        phase = args[2]
                        phase_calls.append(phase)
                        real_require(*args)
                        if (
                            case == "late_staging"
                            and phase_calls.count("failure") == 2
                        ):
                            dependency = (
                                root / permit_module.DEPENDENCY_ROOT
                            )
                            (
                                dependency
                                / (
                                    f"{permit_module.STAGING_PREFIX}"
                                    "late-only"
                                )
                            ).mkdir()

                    try:
                        with mock.patch.object(
                            runner,
                            "require_execution_namespace",
                            side_effect=counted_require,
                        ):
                            with self.assertRaises(
                                runner.RunnerError
                            ) as caught:
                                runner.publish_failure_transaction(
                                    root,
                                    permit_module,
                                    context,
                                    claim_guard,
                                    claim_raw,
                                    failure,
                                    bindings["permit"],
                                    bindings["decision"],
                                )
                        self.assertEqual(
                            caught.exception.code,
                            "E_FAILURE_PUBLICATION_UNCERTAIN",
                        )
                        self.assertTrue(
                            bindings["metrics"]["failureOwnerOnly"]
                        )
                        if case == "preopen_mode":
                            self.assertEqual(
                                bindings["metrics"][
                                    "failureHeldSetOpened"
                                ],
                                0,
                            )
                        elif case == "late_staging":
                            self.assertEqual(
                                phase_calls,
                                ["failure", "failure"],
                            )
                            self.assertEqual(namespace_calls, 5)
                        elif case.startswith("terminal_collision"):
                            self.assertEqual(phase_calls, ["failure"])
                        elif case == "semantic":
                            self.assertEqual(phase_calls, ["failure"])
                        elif case == "claim_mutation":
                            self.assertEqual(phase_calls, [])
                    finally:
                        claim_guard.close()
                        context.namespace.close()

    def test_17_mutation_kill_negative_controls_expose_missing_links(
        self,
    ) -> None:
        for case in (
            "terminal_collision_result",
            "claim_mutation",
            "late_staging",
        ):
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (
                        permit_module,
                        context,
                        claim_guard,
                        claim_raw,
                        failure,
                        bindings,
                    ) = self.actual_failure_transaction(
                        root,
                        mutation=(
                            None if case == "late_staging" else case
                        ),
                    )
                    transaction_claim = claim_guard
                    phase_count = 0
                    namespace_count = 0
                    real_require = runner.require_execution_namespace
                    real_namespace = context.namespace_barrier

                    if case == "claim_mutation":
                        class NoBarrierGuard:
                            def __getattr__(self, name: str) -> object:
                                return getattr(claim_guard, name)

                            def final_barrier(self) -> None:
                                return None

                        transaction_claim = NoBarrierGuard()

                    def negative_require(*args: object) -> None:
                        nonlocal phase_count
                        phase_count += 1
                        if case == "terminal_collision_result":
                            return
                        real_require(*args)
                        if case == "late_staging" and phase_count == 2:
                            dependency = (
                                root / permit_module.DEPENDENCY_ROOT
                            )
                            (
                                dependency
                                / (
                                    f"{permit_module.STAGING_PREFIX}"
                                    "negative-control"
                                )
                            ).mkdir()

                    def negative_namespace() -> None:
                        nonlocal namespace_count
                        namespace_count += 1
                        if (
                            case == "late_staging"
                            and namespace_count == 5
                        ):
                            return
                        real_namespace()

                    context.namespace_barrier = negative_namespace
                    failure_guard = None
                    try:
                        with mock.patch.object(
                            runner,
                            "require_execution_namespace",
                            side_effect=negative_require,
                        ):
                            failure_guard = (
                                runner.publish_failure_transaction(
                                    root,
                                    permit_module,
                                    context,
                                    transaction_claim,
                                    claim_raw,
                                    failure,
                                    bindings["permit"],
                                    bindings["decision"],
                                )
                            )
                        self.assertIsNotNone(failure_guard)
                    finally:
                        if failure_guard is not None:
                            failure_guard.close()
                        claim_guard.close()
                        context.namespace.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
