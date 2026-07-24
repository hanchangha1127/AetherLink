#!/usr/bin/env python3
"""Offline regressions for the combined Wave1+Wave2 graph checker."""

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
import builtins
import contextlib
import copy
import hashlib
import http.client
import importlib.util
import io
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest import mock
import urllib.request


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "g2_pion_combined_fixed_point_checker_v1",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load combined fixed-point checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

EXPECTED_COMBINED_INPUT_SET_SHA256 = (
    "c744597d53e9bf50611f154421f661aec19f95a767dcbb9a80aa653fe83f2036"
)


@contextlib.contextmanager
def deny_transitive_side_effects() -> object:
    """Make any write, process, socket, or network attempt immediately fatal."""

    real_builtin_open = builtins.open
    real_io_open = io.open
    real_os_open = os.open
    real_path_open = Path.open
    attempts: list[str] = []

    def reject(name: str) -> object:
        def denied(*_: object, **__: object) -> None:
            attempts.append(name)
            raise AssertionError(f"forbidden side effect: {name}")

        return denied

    def reject_write_mode(name: str, mode: object) -> None:
        if type(mode) is not str or any(flag in mode for flag in "wax+"):
            attempts.append(name)
            raise AssertionError(f"forbidden write mode: {name}")

    def guarded_builtin_open(
        file: object,
        mode: str = "r",
        *args: object,
        **kwargs: object,
    ) -> object:
        reject_write_mode("builtins.open", mode)
        return real_builtin_open(file, mode, *args, **kwargs)

    def guarded_io_open(
        file: object,
        mode: str = "r",
        *args: object,
        **kwargs: object,
    ) -> object:
        reject_write_mode("io.open", mode)
        return real_io_open(file, mode, *args, **kwargs)

    def guarded_path_open(
        path: Path,
        mode: str = "r",
        *args: object,
        **kwargs: object,
    ) -> object:
        reject_write_mode("Path.open", mode)
        return real_path_open(path, mode, *args, **kwargs)

    write_flags = (
        os.O_WRONLY
        | os.O_RDWR
        | os.O_CREAT
        | os.O_TRUNC
        | os.O_APPEND
    )

    def guarded_os_open(
        path: object,
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        if flags & write_flags:
            attempts.append("os.open")
            raise AssertionError("forbidden os.open write flags")
        return real_os_open(path, flags, *args, **kwargs)

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(builtins, "open", new=guarded_builtin_open)
        )
        stack.enter_context(mock.patch.object(io, "open", new=guarded_io_open))
        stack.enter_context(
            mock.patch.object(Path, "open", new=guarded_path_open)
        )
        stack.enter_context(mock.patch.object(os, "open", new=guarded_os_open))
        for module, names in (
            (
                os,
                (
                    "write",
                    "rename",
                    "replace",
                    "unlink",
                    "remove",
                    "mkdir",
                    "makedirs",
                    "rmdir",
                    "removedirs",
                    "link",
                    "symlink",
                    "system",
                    "popen",
                ),
            ),
            (
                Path,
                (
                    "write_bytes",
                    "write_text",
                    "touch",
                    "mkdir",
                    "rename",
                    "replace",
                    "unlink",
                    "rmdir",
                    "symlink_to",
                    "hardlink_to",
                ),
            ),
            (
                subprocess,
                (
                    "Popen",
                    "run",
                    "call",
                    "check_call",
                    "check_output",
                ),
            ),
            (socket, ("socket", "create_connection")),
            (urllib.request, ("urlopen", "urlretrieve")),
        ):
            for name in names:
                if not hasattr(module, name):
                    continue
                stack.enter_context(
                    mock.patch.object(
                        module,
                        name,
                        side_effect=reject(f"{module.__name__}.{name}"),
                    )
                )
        for connection in (
            http.client.HTTPConnection,
            http.client.HTTPSConnection,
        ):
            stack.enter_context(
                mock.patch.object(
                    connection,
                    "connect",
                    side_effect=reject(f"{connection.__name__}.connect"),
                )
            )
        yield attempts
    if attempts:
        raise AssertionError(f"forbidden side effects observed: {attempts}")


class CombinedFixedPointCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with checker.PinnedRunnerFile(checker.ROOT) as held_runner:
            cls.runner = checker.load_pinned_runner(held_runner)
            with cls.runner.HeldInputSet(
                checker.ROOT,
                checker.control_bindings(),
            ) as held_controls:
                cls.documents = checker.parse_control_documents(
                    cls.runner,
                    held_controls,
                )
                checker.validate_terminal_documents(
                    cls.runner,
                    cls.documents,
                )

    def test_01_exact_pins_and_terminal_frontier_binding(self) -> None:
        self.assertEqual(
            checker.RUNNER_SHA256,
            hashlib.sha256(
                (checker.ROOT / checker.RUNNER_PATH).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(len(checker.CONTROL_SHA256), 9)
        for path, expected in checker.CONTROL_SHA256.items():
            with self.subTest(path=path):
                self.assertEqual(
                    hashlib.sha256(
                        (checker.ROOT / path).read_bytes()
                    ).hexdigest(),
                    expected,
                )
        wave1 = checker.frontier_projection(
            self.documents[checker.WAVE1_RESULT_PATH]["graphDiscovery"][
                "exactFrontier"
            ]
        )
        wave2 = checker.wave2_projection(
            self.documents[checker.WAVE2_RECEIPT_PATH]["sources"]
        )
        self.assertEqual(wave1, wave2)

    def test_02_exact_69_source_input_closure(self) -> None:
        bindings = checker.source_bindings(self.runner, self.documents)
        self.assertEqual(len(bindings), 69)
        self.assertEqual(
            (1, 34, 34),
            (
                sum(row["kind"] == "root_zip" for row in bindings),
                sum(row["kind"] == "mod" for row in bindings),
                sum(row["kind"] == "zip" for row in bindings),
            ),
        )
        self.assertEqual(len({row["path"] for row in bindings}), 69)
        self.assertEqual(
            len(
                {
                    (row["module"], row["version"])
                    for row in bindings
                    if row["kind"] != "root_zip"
                }
            ),
            34,
        )
        wave2_orders = {
            row["tupleOrder"]
            for row in bindings
            if row["wave"] == "wave2"
        }
        self.assertEqual(wave2_orders, set(range(20, 35)))

    def test_03_frontier_and_lineage_mutations_fail_closed(self) -> None:
        bad_frontier = copy.deepcopy(self.documents)
        bad_frontier[checker.WAVE1_RESULT_PATH]["graphDiscovery"][
            "exactFrontier"
        ][0]["selectedByGraphAlgorithm"] = False
        with self.assertRaises(checker.CombinedCheckFailure) as caught:
            checker.validate_terminal_documents(self.runner, bad_frontier)
        self.assertIn(
            str(caught.exception),
            {"E_CONTENT_BINDING", "E_FRONTIER_BINDING"},
        )

        bad_lineage = copy.deepcopy(self.documents)
        bad_lineage[checker.WAVE2_READBACK_MANIFEST_PATH][
            "readbackReceiptRawSha256"
        ] = "0" * 64
        with self.assertRaises(checker.CombinedCheckFailure) as caught:
            checker.validate_terminal_documents(self.runner, bad_lineage)
        self.assertEqual(str(caught.exception), "E_WAVE2_TERMINAL")

        bad_terminal = copy.deepcopy(self.documents)
        bad_terminal[checker.WAVE2_READBACK_PATH][
            "independentReadbackPassed"
        ] = False
        with self.assertRaises(checker.CombinedCheckFailure) as caught:
            checker.validate_terminal_documents(self.runner, bad_terminal)
        self.assertEqual(str(caught.exception), "E_WAVE2_TERMINAL")

    def test_04_exact_source_schema_mutations_fail_closed(self) -> None:
        bad_wave1 = copy.deepcopy(self.documents)
        bad_wave1[checker.WAVE1_PERMIT_PATH]["inputBindings"]["resources"][
            0
        ]["unexpected"] = False
        with self.assertRaises(checker.CombinedCheckFailure) as caught:
            checker.source_bindings(self.runner, bad_wave1)
        self.assertEqual(str(caught.exception), "E_WAVE1_INPUT")

        bad_wave2 = copy.deepcopy(self.documents)
        del bad_wave2[checker.WAVE2_RECEIPT_PATH]["sources"][0][
            "modulePrefix"
        ]
        with self.assertRaises(checker.CombinedCheckFailure) as caught:
            checker.source_bindings(self.runner, bad_wave2)
        self.assertEqual(str(caught.exception), "E_WAVE2_SOURCE")

        missing_tuple = copy.deepcopy(self.documents)
        missing_tuple[checker.WAVE2_RECEIPT_PATH]["sources"].pop()
        with self.assertRaises(checker.CombinedCheckFailure) as caught:
            checker.source_bindings(self.runner, missing_tuple)
        self.assertEqual(str(caught.exception), "E_WAVE2_SOURCE")

    def test_05_hash_link_and_named_identity_mutations_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            payload = b"module example.com/test\n"
            source = root / "source.mod"
            source.write_bytes(payload)
            os.chmod(source, 0o600)
            binding = {
                "path": "source.mod",
                "rawSha256": "0" * 64,
                "maximumBytes": len(payload),
                "ownerOnly": True,
                "kind": "mod",
            }
            with self.assertRaises(self.runner.ReviewFailure):
                self.runner.HeldInputSet(root, [binding])

            binding["rawSha256"] = hashlib.sha256(payload).hexdigest()
            linked = root / "linked.mod"
            os.link(source, linked)
            with self.assertRaises(self.runner.ReviewFailure):
                self.runner.HeldInputSet(root, [binding])
            linked.unlink()

            held = self.runner.HeldInputSet(root, [binding])
            displaced = root / "source-original.mod"
            source.rename(displaced)
            source.write_bytes(payload)
            os.chmod(source, 0o600)
            try:
                with self.assertRaises(self.runner.ReviewFailure):
                    held.final_barrier()
            finally:
                held.close()

    def test_06_pinned_runner_byte_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            target = root / checker.RUNNER_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            target.write_bytes(
                (checker.ROOT / checker.RUNNER_PATH).read_bytes() + b"\n"
            )
            os.chmod(target, 0o600)
            with self.assertRaises(checker.CombinedCheckFailure) as caught:
                checker.PinnedRunnerFile(root)
            self.assertEqual(str(caught.exception), "E_RUNNER_IDENTITY")

    def test_07_routes_are_mutually_exclusive_and_non_authorizing(self) -> None:
        common = {
            "independentReproductionPassed": True,
            "reconstructionCount": 2,
            "fixedPointReached": False,
            "newTupleCount": 1,
            "unmappedExternalImportCount": 0,
            "unresolvedDeclaredExternalImportCount": 0,
        }
        self.assertEqual(
            checker.route_for_graph(common)["route"],
            "next_wave_required",
        )
        gaps = {
            **common,
            "newTupleCount": 0,
            "unmappedExternalImportCount": 1,
        }
        self.assertEqual(
            checker.route_for_graph(gaps)["route"],
            "external_import_resolution_required",
        )
        fixed = {
            **common,
            "newTupleCount": 0,
            "fixedPointReached": True,
        }
        self.assertEqual(
            checker.route_for_graph(fixed)["route"],
            "fixed_point_candidate",
        )

    def test_08_static_surface_is_read_only_and_offline(self) -> None:
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
            "os.exec",
            "os.mkdir(",
            "os.makedirs(",
            "os.rename(",
            "os.replace(",
            "os.unlink(",
            "os.remove(",
            ".write_bytes(",
            ".write_text(",
            "O_WRONLY",
            "O_RDWR",
            "O_CREAT",
            "O_TRUNC",
            "O_APPEND",
            "eval(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertEqual(source.count("exec(code, module.__dict__"), 1)
        self.assertIn("sys.stdout.buffer.write(", source)
        self.assertNotIn("sys.stderr.buffer.write(", source)
        self.assertNotIn("--output", source)
        self.assertNotIn("--record", source)
        self.assertNotIn("--root", source)
        stderr = io.StringIO()
        with mock.patch("sys.stderr", new=stderr):
            with self.assertRaises(checker.CliUsageFailure):
                checker.parse_arguments(["--output", "forbidden.json"])
        self.assertEqual(stderr.getvalue(), "")

    def test_09_cli_failures_are_canonical_and_content_free(self) -> None:
        expected = checker.error_document_bytes()
        invalid = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(CHECKER_PATH),
                "--output",
                "forbidden.json",
            ],
            check=False,
            capture_output=True,
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, expected)
        self.assertEqual(invalid.stderr, b"")

        bad_isolation = subprocess.run(
            [sys.executable, str(CHECKER_PATH)],
            check=False,
            capture_output=True,
        )
        self.assertEqual(bad_isolation.returncode, 1)
        self.assertEqual(bad_isolation.stdout, expected)
        self.assertEqual(bad_isolation.stderr, b"")

    def test_10_live_combined_reconstruction_is_canonical(self) -> None:
        with deny_transitive_side_effects() as attempts:
            candidate = checker.generate_candidate(checker.ROOT)
        self.assertEqual(attempts, [])
        graph = candidate["graphDiscovery"]
        self.assertEqual(candidate["route"], "next_wave_required")
        self.assertEqual(
            candidate["status"],
            "combined_graph_discovery_complete_next_wave_required",
        )
        self.assertFalse(graph["fixedPointReached"])
        self.assertEqual(graph["newTupleCount"], 16)
        self.assertEqual(graph["unmappedExternalImportCount"], 0)
        self.assertEqual(graph["unresolvedDeclaredExternalImportCount"], 0)
        self.assertEqual(graph["moduleNodeCount"], 51)
        self.assertEqual(graph["moduleEdgeCount"], 132)
        self.assertEqual(
            graph["graphSha256"],
            "541fc40bcfe87640033db54948911972dab9a6cab7e0b26d8021a89660be69d8",
        )
        self.assertEqual(
            candidate["inputSet"]["heldSourceInputCount"],
            69,
        )
        projection = candidate["inputSet"]["sourceBindings"]
        self.assertEqual(len(projection), 69)
        projection_sha256 = hashlib.sha256(
            self.runner.canonical_json_bytes(projection)
        ).hexdigest()
        self.assertEqual(
            projection_sha256,
            EXPECTED_COMBINED_INPUT_SET_SHA256,
        )
        self.assertEqual(
            candidate["inputSet"]["combinedInputSetSha256"],
            EXPECTED_COMBINED_INPUT_SET_SHA256,
        )
        self.assertEqual(
            candidate["checkerVerification"]["fullInputReconstructionCount"],
            2,
        )
        self.assertTrue(
            candidate["checkerVerification"][
                "canonicalGraphEqualityVerified"
            ]
        )
        self.assertTrue(all(value is False for value in candidate["closure"].values()))
        self.assertTrue(all(value is False for value in candidate["authority"].values()))
        counters = candidate["operationCounters"]
        for key in (
            "archiveExtractionCount",
            "sourceExecutionCount",
            "subprocessCount",
            "networkOperationCount",
            "fileWriteCount",
        ):
            self.assertEqual(counters[key], 0)
        binding = candidate["contentBinding"]
        without = dict(candidate)
        without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            hashlib.sha256(
                self.runner.canonical_json_bytes(without)
            ).hexdigest(),
        )

    def test_11_full_reconstruction_mismatches_fail_closed(self) -> None:
        graph = {
            "independentReproductionPassed": True,
            "reconstructionCount": 2,
            "fixedPointReached": False,
            "newTupleCount": 1,
            "unmappedExternalImportCount": 0,
            "unresolvedDeclaredExternalImportCount": 0,
        }
        coverage = {
            "archiveCount": 35,
            "aggregateEntryCount": 1,
            "aggregateUncompressedByteCount": 1,
        }
        graph_mismatch = {**graph, "newTupleCount": 2}
        stdout = io.StringIO()
        with mock.patch.object(
            checker,
            "reconstruct_graph",
            side_effect=[
                (graph, coverage),
                (graph_mismatch, coverage),
            ],
        ):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(
                    checker.CombinedCheckFailure
                ) as caught:
                    checker.generate_candidate(checker.ROOT)
        self.assertEqual(str(caught.exception), "E_REPRODUCTION")
        self.assertEqual(stdout.getvalue(), "")

        coverage_mismatch = {**coverage, "archiveCount": 34}
        stdout = io.StringIO()
        with mock.patch.object(
            checker,
            "reconstruct_graph",
            side_effect=[
                (graph, coverage),
                (graph, coverage_mismatch),
            ],
        ):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(
                    checker.CombinedCheckFailure
                ) as caught:
                    checker.generate_candidate(checker.ROOT)
        self.assertEqual(str(caught.exception), "E_REPRODUCTION")
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
