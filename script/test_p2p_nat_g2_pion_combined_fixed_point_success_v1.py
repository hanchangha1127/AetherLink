#!/usr/bin/env python3
"""Offline tests for combined fixed-point independent readback."""

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
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_combined_fixed_point_success_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "combined_fixed_point_success_v1",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load readback checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


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


def candidate() -> dict:
    return {
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
        "closure": {"dependencyFixedPointReached": False},
        "contentBinding": {"sha256": "3" * 64},
    }


class CombinedFixedPointReadbackTests(unittest.TestCase):
    @staticmethod
    def load_local_module(name: str, filename: str) -> object:
        path = CHECKER_PATH.parent / filename
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {filename}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def actual_readback_failure_transaction(
        self,
        root: Path,
        *,
        mutation: str | None = None,
        semantic_tamper: bool = False,
    ) -> tuple[object, object, object, object, bytes, dict, dict]:
        permit_module = self.load_local_module(
            "permit_for_actual_readback_failure",
            (
                "check_p2p_nat_g2_pion_combined_fixed_point_"
                "execution_permit_v1.py"
            ),
        )
        decision_module = self.load_local_module(
            "decision_for_actual_readback_failure",
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
                "candidateSourceProjectionSha256": "d" * 64,
            },
        }
        result = {
            "contentBinding": {"sha256": "b" * 64},
            "candidateSourceProjectionSha256": "d" * 64,
        }
        result_raw = checker.canonical_bytes(result)
        evaluation_manifest_raw = checker.canonical_bytes(
            {"newTupleCount": 16}
        )
        checker.write_exclusive(
            root,
            permit_module.CLAIM_PATH,
            checker.canonical_bytes({"executionClaim": True}),
        )
        checker.write_exclusive(
            root,
            permit_module.RESULT_PATH,
            result_raw,
        )
        checker.write_exclusive(
            root,
            permit_module.MANIFEST_PATH,
            evaluation_manifest_raw,
        )
        held_outputs = decision_module.HeldSet(
            root,
            checker.output_bindings(permit_module),
        )
        claim = checker.readback_claim(
            permit,
            checker.sha256(result_raw),
        )
        claim_raw = checker.canonical_bytes(claim)
        checker.write_exclusive(
            root,
            permit_module.READBACK_CLAIM_PATH,
            claim_raw,
        )
        claim_guard = decision_module.HeldSet(
            root,
            [
                {
                    "path": permit_module.READBACK_CLAIM_PATH,
                    "rawSha256": checker.sha256(claim_raw),
                    "maximumBytes": checker.MAXIMUM_JSON_BYTES,
                    "ownerOnly": True,
                }
            ],
        )

        def mutate_after_failure_open() -> None:
            dependency = root / permit_module.DEPENDENCY_ROOT
            base = root / permit_module.BASE
            failure_path = root / permit_module.READBACK_FAILURE_PATH
            if mutation == "staging":
                (
                    dependency
                    / f"{permit_module.STAGING_PREFIX}post-readback-failure"
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
                os.link(failure_path, base / "readback-failure-hardlink")
            elif mutation == "claim_mutation":
                claim_path = root / permit_module.READBACK_CLAIM_PATH
                claim_path.write_bytes(b"{}\n")
            elif mutation == "output_mutation_result":
                result_path = root / permit_module.RESULT_PATH
                result_path.write_bytes(b"{}\n")
            elif mutation == "output_mutation_manifest":
                manifest_path = root / permit_module.MANIFEST_PATH
                manifest_path.write_bytes(b"{}\n")
            elif mutation == "terminal_collision_receipt":
                checker.write_exclusive(
                    root,
                    permit_module.READBACK_RECEIPT_PATH,
                    checker.canonical_bytes({"collision": "receipt"}),
                )
            elif mutation == "terminal_collision_manifest":
                checker.write_exclusive(
                    root,
                    permit_module.READBACK_MANIFEST_PATH,
                    checker.canonical_bytes({"collision": "manifest"}),
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
                binding["path"] == permit_module.READBACK_FAILURE_PATH
                for binding in bindings
            )
            if is_failure:
                metrics["failureOwnerOnly"] = all(
                    binding["ownerOnly"] is True
                    for binding in bindings
                )
                if mutation == "preopen_mode":
                    os.chmod(
                        root / permit_module.READBACK_FAILURE_PATH,
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
        failure = checker.readback_failure_document(
            checker.ReadbackError("E_INJECTED", "readback"),
            permit,
            claim_raw,
            result_raw,
            "b" * 64,
            evaluation_manifest_raw,
        )
        if semantic_tamper:
            failure["resultContentSha256"] = "e" * 64
            failure = checker.content_bound(failure)
        return (
            permit_module,
            context,
            held_outputs,
            claim_guard,
            claim_raw,
            failure,
            {
                "permit": permit,
                "result": result,
                "metrics": metrics,
            },
        )

    def record_harness(
        self,
        *,
        graph_error: Exception | None = None,
        guard_error: Exception | None = None,
    ) -> tuple[object, list[tuple[str, bytes]], object]:
        writes: list[tuple[str, bytes]] = []
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
            "sourceInputSet": {
                "decisionHeldBindingSetSha256": "b" * 64,
                "candidateSourceProjectionSha256": "1" * 64,
            },
        }
        result = {
            "contentBinding": {"sha256": "c" * 64},
            "graphSha256": "2" * 64,
            "candidateSourceProjectionSha256": "1" * 64,
        }
        evaluation_manifest = {"newTupleCount": 16}
        result_raw = checker.canonical_bytes(result)
        evaluation_manifest_raw = checker.canonical_bytes(
            evaluation_manifest
        )

        class HeldFactory:
            calls = 0

            def __call__(
                self,
                root: Path,
                bindings: object,
            ) -> FakeGuard:
                del root
                self.calls += 1
                if self.calls == 2 and guard_error is not None:
                    raise guard_error
                if self.calls == 1:
                    return FakeGuard(
                        {
                            FakePermit.RESULT_PATH: result_raw,
                            FakePermit.MANIFEST_PATH: evaluation_manifest_raw,
                            FakePermit.CLAIM_PATH: b"evaluation-claim\n",
                        }
                    )
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
            return candidate()

        context = types.SimpleNamespace(
            static=types.SimpleNamespace(raw={"permit.json": b"permit\n"}),
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
        )

        def write(root: Path, path: str, raw: bytes) -> str:
            del root
            writes.append((path, raw))
            return checker.sha256(raw)

        permit_checker._result = result
        permit_checker._manifest = evaluation_manifest
        return permit_checker, writes, write

    def test_01_live_default_check_is_read_only_not_recordable(self) -> None:
        result = checker.read_only_check(checker.ROOT)
        self.assertTrue(result["validationPassed"])
        self.assertFalse(result["recordable"])
        self.assertEqual(
            result["status"],
            "evaluation_not_executed_readback_not_recordable",
        )
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertFalse(result["networkUsed"])
        self.assertFalse(result["sourceExecutionUsed"])

    def test_02_state_machine_includes_readback_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            out.mkdir()
            self.assertEqual(checker.state(root, FakePermit)[0], "not_executed")
            for name in ("claim.json", "result.json", "manifest.json"):
                (out / name).write_bytes(b"x")
            self.assertEqual(checker.state(root, FakePermit)[0], "recordable")
            (out / "failure.json").write_bytes(b"x")
            self.assertEqual(checker.state(root, FakePermit)[0], "blocked")
            (out / "failure.json").unlink()
            (out / "rb-claim.json").write_bytes(b"x")
            (out / "rb-failure.json").write_bytes(b"x")
            self.assertEqual(
                checker.state(root, FakePermit)[0],
                "readback_failure",
            )

    def test_03_residue_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            out.mkdir()
            (out / "rb-receipt.json").write_bytes(b"x")
            self.assertEqual(checker.state(root, FakePermit)[0], "blocked")

    def test_04_independent_projection_is_exact(self) -> None:
        value = candidate()
        projection = checker.independent_projection(value)
        self.assertEqual(set(projection), set(checker.PROJECTION_FIELDS))
        del value["graphDiscovery"]
        with self.assertRaises(checker.ReadbackError) as caught:
            checker.independent_projection(value)
        self.assertEqual(caught.exception.code, "E_CANDIDATE")

    def test_05_strict_json_rejects_duplicate_and_nonfinite(self) -> None:
        with self.assertRaises(checker.ReadbackError) as caught:
            checker.strict_json(b'{"x":1,"x":2}\n')
        self.assertEqual(caught.exception.code, "E_JSON")
        with self.assertRaises(checker.ReadbackError) as caught:
            checker.strict_json(b'{"x":NaN}\n')
        self.assertEqual(caught.exception.code, "E_JSON")

    def test_06_readback_claim_is_consuming_and_auth_free(self) -> None:
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
            "sourceInputSet": {
                "candidateSourceProjectionSha256": "c" * 64,
            },
        }
        claim = checker.readback_claim(permit, "b" * 64)
        self.assertFalse(claim["automaticRetryAllowed"])
        self.assertFalse(claim["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(claim["externalAuthenticationRequired"])
        self.assertFalse(claim["userActionRequired"])

    def test_07_publication_is_exclusive_and_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            out.mkdir()
            raw = b'{"x":1}\n'
            checker.write_exclusive(root, "out/receipt.json", raw)
            self.assertEqual(
                stat.S_IMODE((out / "receipt.json").stat().st_mode),
                0o600,
            )
            with self.assertRaises(checker.ReadbackError) as caught:
                checker.write_exclusive(root, "out/receipt.json", raw)
            self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_08_record_order_and_uncertainty_are_explicit(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        record_source = source[source.index("def record(") :]
        claim = record_source.index(
            "permit_checker.READBACK_CLAIM_PATH,\n            claim_raw"
        )
        graph = record_source.index("context.candidate.generate_candidate(root)")
        receipt = record_source.index(
            "permit_checker.READBACK_RECEIPT_PATH,\n            receipt_raw"
        )
        manifest = record_source.index(
            "permit_checker.READBACK_MANIFEST_PATH,\n            manifest_raw"
        )
        self.assertLess(claim, graph)
        self.assertLess(graph, receipt)
        self.assertLess(receipt, manifest)
        self.assertIn("receipt_attempted = True", source)
        self.assertIn("E_POST_RECEIPT_PUBLICATION_UNCERTAIN", source)
        self.assertIn("READBACK_FAILURE_PATH", source)

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
                permit_checker, writes, write = self.record_harness(
                    guard_error=guard_error,
                    graph_error=graph_error,
                )
                with (
                    mock.patch.object(
                        checker,
                        "load_permit_checker",
                        return_value=permit_checker,
                    ),
                    mock.patch.object(
                        checker,
                        "state",
                        return_value=("recordable", {}),
                    ),
                    mock.patch.object(
                        checker,
                        "write_exclusive",
                        side_effect=write,
                    ),
                    mock.patch.object(
                        checker,
                        "require_readback_namespace",
                        return_value=None,
                    ),
                    mock.patch.object(
                        checker,
                        "validate_outputs",
                        return_value=(
                            {},
                            permit_checker._result,
                            permit_checker._manifest,
                        ),
                    ),
                ):
                    with self.assertRaises(checker.ReadbackError):
                        checker.record(Path("/unused"))
                self.assertEqual(
                    [path for path, _ in writes],
                    [
                        FakePermit.READBACK_CLAIM_PATH,
                        FakePermit.READBACK_FAILURE_PATH,
                    ],
                )
                failure = json.loads(writes[-1][1])
                self.assertEqual(
                    failure["readbackClaimRawSha256"],
                    checker.sha256(writes[0][1]),
                )
                self.assertFalse(failure["automaticRetryAllowed"])

    def test_08b_receipt_and_manifest_failures_never_backfill(self) -> None:
        for failed_path in (
            FakePermit.READBACK_RECEIPT_PATH,
            FakePermit.READBACK_MANIFEST_PATH,
        ):
            with self.subTest(failed_path=failed_path):
                permit_checker, writes, base_write = (
                    self.record_harness()
                )

                def failing_write(
                    root: Path,
                    path: str,
                    raw: bytes,
                ) -> str:
                    digest = base_write(root, path, raw)
                    if path == failed_path:
                        raise checker.ReadbackError(
                            "E_INJECTED",
                            "record",
                        )
                    return digest

                with (
                    mock.patch.object(
                        checker,
                        "load_permit_checker",
                        return_value=permit_checker,
                    ),
                    mock.patch.object(
                        checker,
                        "state",
                        return_value=("recordable", {}),
                    ),
                    mock.patch.object(
                        checker,
                        "write_exclusive",
                        side_effect=failing_write,
                    ),
                    mock.patch.object(
                        checker,
                        "require_readback_namespace",
                        return_value=None,
                    ),
                    mock.patch.object(
                        checker,
                        "validate_outputs",
                        return_value=(
                            {},
                            permit_checker._result,
                            permit_checker._manifest,
                        ),
                    ),
                ):
                    with self.assertRaises(checker.ReadbackError) as caught:
                        checker.record(Path("/unused"))
                self.assertEqual(
                    caught.exception.code,
                    "E_POST_RECEIPT_PUBLICATION_UNCERTAIN",
                )
                self.assertNotIn(
                    FakePermit.READBACK_FAILURE_PATH,
                    [path for path, _ in writes],
                )

    def test_09_error_document_has_no_retry_or_auth(self) -> None:
        error = checker.error_document(
            checker.ReadbackError("E_TEST", "check")
        )
        self.assertFalse(error["automaticRetryAllowed"])
        for key in (
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ):
            self.assertFalse(error[key])

    def test_10_static_surface_has_no_network_or_source_execution(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
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

    def test_11_outer_hold_and_fresh_recomputation_are_required(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn("permit_checker.open_authority_context(", source)
        self.assertIn("context.final_barrier()", source)
        self.assertIn("held_outputs.final_barrier()", source)
        self.assertIn("context.candidate.generate_candidate(root)", source)
        self.assertIn("freshHeldSourceInputCount", source)
        self.assertIn("sourceGraphAlgorithmsReexecutedByReadback", source)
        self.assertIn("exactResultProjectionMatched", source)

    def test_12_cli_defaults_and_errors_are_canonical(self) -> None:
        args = checker.parse_arguments([])
        self.assertFalse(args.record)
        self.assertFalse(args.check)
        self.assertTrue(checker.parse_arguments(["--record"]).record)
        for argv in (
            ["--execute"],
            ["--root", "/tmp"],
            ["--output", "x"],
            ["--check", "--record"],
        ):
            with self.subTest(argv=argv):
                capture = Capture()
                stderr = io.StringIO()
                with (
                    mock.patch.object(sys, "stdout", capture),
                    mock.patch.object(sys, "stderr", stderr),
                ):
                    self.assertEqual(checker.main(argv), 1)
                expected = checker.canonical_bytes(
                    checker.error_document(
                        checker.ReadbackError("E_ARGUMENTS", "cli")
                    )
                )
                self.assertEqual(capture.buffer.getvalue(), expected)
                self.assertEqual(stderr.getvalue(), "")
        for isolated, side_effect, code, phase in (
            (False, None, "E_INTERPRETER", "cli"),
            (True, RuntimeError("unknown"), "E_INTERNAL", "readback"),
        ):
            capture = Capture()
            stderr = io.StringIO()
            with (
                mock.patch.object(sys, "stdout", capture),
                mock.patch.object(sys, "stderr", stderr),
                mock.patch.object(
                    checker,
                    "isolated_interpreter",
                    return_value=isolated,
                ),
                mock.patch.object(
                    checker,
                    "read_only_check",
                    side_effect=side_effect,
                ),
            ):
                self.assertEqual(checker.main([]), 1)
            expected = checker.canonical_bytes(
                checker.error_document(
                    checker.ReadbackError(code, phase)
                )
            )
            self.assertEqual(capture.buffer.getvalue(), expected)
            self.assertEqual(stderr.getvalue(), "")

    def test_13_phase_specific_namespace_rejects_readback_residue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            out.mkdir()
            for name in (
                "claim.json",
                "result.json",
                "manifest.json",
                "rb-claim.json",
            ):
                (out / name).write_bytes(b"x")
            checker.require_readback_namespace(
                root,
                FakePermit,
                "after_claim",
            )
            (out / "rb-receipt.json").write_bytes(b"x")
            checker.require_readback_namespace(
                root,
                FakePermit,
                "after_receipt",
            )
            (out / "rb-manifest.json").write_bytes(b"x")
            checker.require_readback_namespace(
                root,
                FakePermit,
                "complete",
            )
            (out / "rb-failure.json").write_bytes(b"x")
            with self.assertRaises(checker.ReadbackError) as caught:
                checker.require_readback_namespace(
                    root,
                    FakePermit,
                    "complete",
                )
            self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_14_exact_output_schemas_reject_added_fields(self) -> None:
        for expected, code in (
            (checker.CLAIM_KEYS, "E_CLAIM"),
            (checker.RESULT_KEYS, "E_RESULT"),
            (checker.EVALUATION_MANIFEST_KEYS, "E_MANIFEST"),
            (checker.READBACK_CLAIM_KEYS, "E_READBACK_CLAIM"),
            (checker.READBACK_RECEIPT_KEYS, "E_READBACK_RECEIPT"),
            (checker.READBACK_MANIFEST_KEYS, "E_READBACK_MANIFEST"),
        ):
            with self.subTest(code=code):
                value = {key: None for key in expected}
                checker.exact_keys(value, expected, code)
                value["unrecognizedAuthority"] = True
                with self.assertRaises(checker.ReadbackError) as caught:
                    checker.exact_keys(value, expected, code)
                self.assertEqual(caught.exception.code, code)

    def test_14a_bound_failure_terminals_reject_tamper_and_junk(
        self,
    ) -> None:
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
            "sourceInputSet": {
                "decisionHeldBindingSetSha256": "b" * 64,
                "candidateSourceProjectionSha256": "c" * 64,
            },
        }
        context = types.SimpleNamespace(
            decision={
                "decisionId": "decision",
                "contentBinding": {"sha256": "d" * 64},
            }
        )
        claim = {
            "claimType": (
                "aetherlink.g2-pion-combined-fixed-point-one-use-claim"
            ),
            "schemaVersion": "1.0",
            "attemptId": "1" * 32,
            "createdAt": "2026-07-24T00:00:00Z",
            "permitId": "permit",
            "permitContentSha256": "a" * 64,
            "decisionId": "decision",
            "decisionContentSha256": "d" * 64,
            "decisionHeldBindingSetSha256": "b" * 64,
            "claimCreatedAndFsyncedBeforeArchiveMemberOpenOrDecode": True,
            "automaticRetryAllowed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        claim_raw = checker.canonical_bytes(claim)
        failure = checker.content_bound(
            {
                "documentType": (
                    "aetherlink.g2-pion-combined-fixed-point-"
                    "evaluation-failure"
                ),
                "schemaVersion": "1.0",
                "status": "consumed_failure_before_result_publication",
                "failureCode": "E_INJECTED",
                "phase": "evaluation",
                "permitId": "permit",
                "permitContentSha256": "a" * 64,
                "decisionId": "decision",
                "decisionContentSha256": "d" * 64,
                "claimRawSha256": checker.sha256(claim_raw),
                "decisionHeldBindingSetSha256": "b" * 64,
                "automaticRetryAllowed": False,
                "resultBackfillAllowed": False,
                "networkUsed": False,
                "sourceExecutionUsed": False,
                "filesystemExtractionUsed": False,
                "subprocessUsed": False,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "signatureRequired": False,
                "privateKeyRequired": False,
                "tokenRequired": False,
                "passwordRequired": False,
                "userActionRequired": False,
            }
        )
        held = FakeGuard(
            {
                FakePermit.CLAIM_PATH: claim_raw,
                FakePermit.FAILURE_PATH: checker.canonical_bytes(failure),
            }
        )
        checker.validate_evaluation_failure(
            context,
            held,
            FakePermit,
            permit,
        )
        tampered = dict(failure)
        tampered["networkUsed"] = True
        tampered = checker.content_bound(tampered)
        held.raw[FakePermit.FAILURE_PATH] = checker.canonical_bytes(
            tampered
        )
        with self.assertRaises(checker.ReadbackError) as caught:
            checker.validate_evaluation_failure(
                context,
                held,
                FakePermit,
                permit,
            )
        self.assertEqual(caught.exception.code, "E_FAILURE")
        held.raw[FakePermit.CLAIM_PATH] = b"x"
        with self.assertRaises(checker.ReadbackError):
            checker.validate_evaluation_failure(
                context,
                held,
                FakePermit,
                permit,
            )

    def test_14b_recorded_receipt_self_rebound_tamper_fails(self) -> None:
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
        }
        result_raw = b"result\n"
        evaluation_manifest_raw = b"evaluation-manifest\n"
        result = {
            "contentBinding": {"sha256": "b" * 64},
            "graphSha256": "c" * 64,
            "candidateSourceProjectionSha256": "d" * 64,
        }
        claim = {
            "claimType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "readback-one-use-claim"
            ),
            "schemaVersion": "1.0",
            "attemptId": "2" * 32,
            "createdAt": "2026-07-24T00:00:00Z",
            "permitId": "permit",
            "permitContentSha256": "a" * 64,
            "resultRawSha256": checker.sha256(result_raw),
            "candidateSourceProjectionSha256": "d" * 64,
            "automaticRetryAllowed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        claim_raw = checker.canonical_bytes(claim)
        receipt = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "independent-readback-receipt"
            ),
            "schemaVersion": "1.0",
            "status": "independent_readback_complete_manifest_pending",
            "permitId": "permit",
            "readbackClaimRawSha256": checker.sha256(claim_raw),
            "resultRawSha256": checker.sha256(result_raw),
            "resultContentSha256": "b" * 64,
            "evaluationManifestRawSha256": checker.sha256(
                evaluation_manifest_raw
            ),
            "freshHeldSourceInputCount": 69,
            "freshArchiveOpenCount": 70,
            "freshFullSourceReconstructionCount": 2,
            "sourceGraphAlgorithmsReexecutedByReadback": True,
            "archiveMembersReopened": True,
            "exactResultProjectionMatched": True,
            "graphSha256": "c" * 64,
            "candidateSourceProjectionSha256": "d" * 64,
            "fixedPointReached": False,
            "newTupleCount": 16,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "subprocessUsed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "publish_combined_fixed_point_readback_manifest_last"
            ),
        }
        receipt_raw = checker.canonical_bytes(receipt)
        manifest = {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "independent-readback-manifest"
            ),
            "schemaVersion": "1.0",
            "status": "independent_readback_published_not_fixed_point",
            "manifestWrittenLast": True,
            "permitId": "permit",
            "readbackClaimRawSha256": checker.sha256(claim_raw),
            "readbackReceiptPath": FakePermit.READBACK_RECEIPT_PATH,
            "readbackReceiptRawSha256": checker.sha256(receipt_raw),
            "resultRawSha256": checker.sha256(result_raw),
            "evaluationManifestRawSha256": checker.sha256(
                evaluation_manifest_raw
            ),
            "candidateSourceProjectionSha256": "d" * 64,
            "fixedPointReached": False,
            "newTupleCount": 16,
            "independentReadbackPassed": True,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "filesystemExtractionUsed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "prepare_separate_new_dependency_wave_decision_for_"
                "remaining_16_frontier_tuples"
            ),
        }
        held = FakeGuard(
            {
                FakePermit.RESULT_PATH: result_raw,
                FakePermit.MANIFEST_PATH: evaluation_manifest_raw,
                FakePermit.READBACK_CLAIM_PATH: claim_raw,
                FakePermit.READBACK_RECEIPT_PATH: receipt_raw,
                FakePermit.READBACK_MANIFEST_PATH: checker.canonical_bytes(
                    manifest
                ),
            }
        )
        checker.validate_recorded_readback(
            held,
            FakePermit,
            permit,
            result,
            {"newTupleCount": 16},
        )
        receipt["networkUsed"] = True
        receipt_raw = checker.canonical_bytes(receipt)
        manifest["readbackReceiptRawSha256"] = checker.sha256(receipt_raw)
        held.raw[FakePermit.READBACK_RECEIPT_PATH] = receipt_raw
        held.raw[FakePermit.READBACK_MANIFEST_PATH] = (
            checker.canonical_bytes(manifest)
        )
        with self.assertRaises(checker.ReadbackError) as caught:
            checker.validate_recorded_readback(
                held,
                FakePermit,
                permit,
                result,
                {"newTupleCount": 16},
            )
        self.assertEqual(caught.exception.code, "E_READBACK_RECEIPT")

    def test_14c_readback_failure_reopen_rejects_rebound_auth(
        self,
    ) -> None:
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
            "sourceInputSet": {
                "candidateSourceProjectionSha256": "d" * 64,
            },
        }
        result_raw = b"result\n"
        evaluation_manifest_raw = b"evaluation-manifest\n"
        result = {
            "contentBinding": {"sha256": "b" * 64},
            "candidateSourceProjectionSha256": "d" * 64,
        }
        claim = {
            "claimType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "readback-one-use-claim"
            ),
            "schemaVersion": "1.0",
            "attemptId": "3" * 32,
            "createdAt": "2026-07-24T00:00:00Z",
            "permitId": "permit",
            "permitContentSha256": "a" * 64,
            "resultRawSha256": checker.sha256(result_raw),
            "candidateSourceProjectionSha256": "d" * 64,
            "automaticRetryAllowed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        claim_raw = checker.canonical_bytes(claim)
        failure = checker.readback_failure_document(
            checker.ReadbackError("E_INJECTED", "readback"),
            permit,
            claim_raw,
            result_raw,
            "b" * 64,
            evaluation_manifest_raw,
        )
        held = FakeGuard(
            {
                FakePermit.RESULT_PATH: result_raw,
                FakePermit.MANIFEST_PATH: evaluation_manifest_raw,
                FakePermit.READBACK_CLAIM_PATH: claim_raw,
                FakePermit.READBACK_FAILURE_PATH: checker.canonical_bytes(
                    failure
                ),
            }
        )
        checker.validate_readback_failure(
            held,
            FakePermit,
            permit,
            result,
        )
        failure["externalAuthenticationRequired"] = True
        failure = checker.content_bound(failure)
        held.raw[FakePermit.READBACK_FAILURE_PATH] = (
            checker.canonical_bytes(failure)
        )
        with self.assertRaises(checker.ReadbackError) as caught:
            checker.validate_readback_failure(
                held,
                FakePermit,
                permit,
                result,
            )
        self.assertEqual(caught.exception.code, "E_READBACK_FAILURE")

    def test_15_recorded_state_holds_all_readback_outputs(self) -> None:
        bindings = checker.recorded_output_bindings(FakePermit)
        self.assertEqual(
            [binding["path"] for binding in bindings],
            [
                FakePermit.CLAIM_PATH,
                FakePermit.RESULT_PATH,
                FakePermit.MANIFEST_PATH,
                FakePermit.READBACK_CLAIM_PATH,
                FakePermit.READBACK_RECEIPT_PATH,
                FakePermit.READBACK_MANIFEST_PATH,
            ],
        )
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn("validate_recorded_readback(", source)
        self.assertIn("held_outputs.final_barrier()", source)

    def test_16_claim_guard_failure_still_publishes_failure(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn("claim_written = True", source)
        self.assertIn(
            "if claim_written and not receipt_attempted:",
            source,
        )

    def test_17_actual_readback_failure_reopens_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (
                permit_module,
                context,
                held_outputs,
                claim_guard,
                claim_raw,
                failure,
                bindings,
            ) = self.actual_readback_failure_transaction(root)
            failure_guard = None
            try:
                failure_guard = (
                    checker.publish_readback_failure_transaction(
                        root,
                        permit_module,
                        context,
                        held_outputs,
                        claim_guard,
                        claim_raw,
                        failure,
                        bindings["permit"],
                        bindings["result"],
                    )
                )
                checker.validate_readback_failure_bytes(
                    claim_guard.raw[
                        permit_module.READBACK_CLAIM_PATH
                    ],
                    failure_guard.raw[
                        permit_module.READBACK_FAILURE_PATH
                    ],
                    held_outputs.raw[permit_module.RESULT_PATH],
                    held_outputs.raw[permit_module.MANIFEST_PATH],
                    bindings["permit"],
                    bindings["result"],
                )
                self.assertEqual(
                    checker.state(root, permit_module)[0],
                    "readback_failure",
                )
            finally:
                if failure_guard is not None:
                    failure_guard.close()
                claim_guard.close()
                held_outputs.close()
                context.namespace.close()

    def test_18_actual_readback_failure_rejects_post_publish_changes(
        self,
    ) -> None:
        cases = (
            "staging",
            "parent_swap",
            "preopen_mode",
            "claim_mutation",
            "output_mutation_result",
            "output_mutation_manifest",
            "terminal_collision_receipt",
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
                        held_outputs,
                        claim_guard,
                        claim_raw,
                        failure,
                        bindings,
                    ) = self.actual_readback_failure_transaction(
                        root,
                        mutation=(
                            None
                            if case in {"semantic", "late_staging"}
                            else case
                        ),
                        semantic_tamper=case == "semantic",
                    )
                    real_require = checker.require_readback_namespace
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
                            and phase_calls.count("readback_failure")
                            == 2
                        ):
                            dependency = (
                                root / permit_module.DEPENDENCY_ROOT
                            )
                            (
                                dependency
                                / (
                                    f"{permit_module.STAGING_PREFIX}"
                                    "late-readback-only"
                                )
                            ).mkdir()

                    try:
                        with mock.patch.object(
                            checker,
                            "require_readback_namespace",
                            side_effect=counted_require,
                        ):
                            with self.assertRaises(
                                checker.ReadbackError
                            ) as caught:
                                checker.publish_readback_failure_transaction(
                                    root,
                                    permit_module,
                                    context,
                                    held_outputs,
                                    claim_guard,
                                    claim_raw,
                                    failure,
                                    bindings["permit"],
                                    bindings["result"],
                                )
                        self.assertEqual(
                            caught.exception.code,
                            "E_READBACK_FAILURE_PUBLICATION_UNCERTAIN",
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
                                [
                                    "readback_failure",
                                    "readback_failure",
                                ],
                            )
                            self.assertEqual(namespace_calls, 5)
                        elif case.startswith("terminal_collision"):
                            self.assertEqual(
                                phase_calls,
                                ["readback_failure"],
                            )
                        elif case == "semantic":
                            self.assertEqual(
                                phase_calls,
                                ["readback_failure"],
                            )
                        elif case in {
                            "claim_mutation",
                            "output_mutation_result",
                            "output_mutation_manifest",
                        }:
                            self.assertEqual(phase_calls, [])
                    finally:
                        claim_guard.close()
                        held_outputs.close()
                        context.namespace.close()

    def test_19_mutation_kill_negative_controls_expose_missing_links(
        self,
    ) -> None:
        for case in (
            "terminal_collision_receipt",
            "claim_mutation",
            "output_mutation_result",
            "late_staging",
        ):
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (
                        permit_module,
                        context,
                        held_outputs,
                        claim_guard,
                        claim_raw,
                        failure,
                        bindings,
                    ) = self.actual_readback_failure_transaction(
                        root,
                        mutation=(
                            None if case == "late_staging" else case
                        ),
                    )
                    transaction_claim = claim_guard
                    transaction_outputs = held_outputs
                    phase_count = 0
                    namespace_count = 0
                    real_require = checker.require_readback_namespace
                    real_namespace = context.namespace_barrier

                    class NoBarrierGuard:
                        def __init__(self, guard: object) -> None:
                            self.guard = guard

                        def __getattr__(self, name: str) -> object:
                            return getattr(self.guard, name)

                        def final_barrier(self) -> None:
                            return None

                    if case == "claim_mutation":
                        transaction_claim = NoBarrierGuard(claim_guard)
                    elif case == "output_mutation_result":
                        transaction_outputs = NoBarrierGuard(held_outputs)

                    def negative_require(*args: object) -> None:
                        nonlocal phase_count
                        phase_count += 1
                        if case == "terminal_collision_receipt":
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
                                    "negative-readback-control"
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
                            checker,
                            "require_readback_namespace",
                            side_effect=negative_require,
                        ):
                            failure_guard = (
                                checker.publish_readback_failure_transaction(
                                    root,
                                    permit_module,
                                    context,
                                    transaction_outputs,
                                    transaction_claim,
                                    claim_raw,
                                    failure,
                                    bindings["permit"],
                                    bindings["result"],
                                )
                            )
                        self.assertIsNotNone(failure_guard)
                    finally:
                        if failure_guard is not None:
                            failure_guard.close()
                        claim_guard.close()
                        held_outputs.close()
                        context.namespace.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
