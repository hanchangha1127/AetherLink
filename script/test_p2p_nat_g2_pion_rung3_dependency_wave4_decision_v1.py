#!/usr/bin/env python3
"""Adversarial tests for the offline Wave4 identity decision checker."""

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
    raise RuntimeError("Wave4 decision tests require `python3 -I -B -S`")

import ast
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import types
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_decision_v1.py"
)
READER_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave4-v1.md"
)
DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave4-v1.json"
)
EXPECTED_CHECKER_RAW_SHA256 = (
    "5ef1a37ac6006ab05675a1e3afa44b01f7bb684ce525976bb182c8fcafbd4852"
)
EXPECTED_READER_RAW_SHA256 = (
    "f7176713c9759ec54a21f0cbe77ae2ab5424a8361c256e6af50ad6a43bbba196"
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def preflight() -> tuple[bytes, bytes]:
    checker_raw = (ROOT / CHECKER_PATH).read_bytes()
    reader_raw = (ROOT / READER_PATH).read_bytes()
    if sha256(checker_raw) != EXPECTED_CHECKER_RAW_SHA256:
        raise RuntimeError("checker preflight failed")
    if sha256(reader_raw) != EXPECTED_READER_RAW_SHA256:
        raise RuntimeError("reader preflight failed")
    return checker_raw, reader_raw


def load_checker(raw: bytes) -> types.ModuleType:
    module = types.ModuleType("wave4_decision_checker_test_subject")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / CHECKER_PATH),
            "__loader__": None,
            "__name__": "wave4_decision_checker_test_subject",
            "__package__": None,
        }
    )
    code = compile(
        raw,
        CHECKER_PATH,
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    exec(code, module.__dict__, module.__dict__)
    return module


def load_wave4_candidate_checker() -> types.ModuleType:
    path = CHECKER.WAVE4_CHECKER_PATH
    raw = (ROOT / path).read_bytes()
    if sha256(raw) != CHECKER.WAVE4_CHECKER_RAW_SHA256:
        raise RuntimeError("Wave4 candidate checker preflight failed")
    module = types.ModuleType("wave4_candidate_checker_test_subject")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / path),
            "__loader__": None,
            "__name__": "wave4_candidate_checker_test_subject",
            "__package__": None,
        }
    )
    code = compile(raw, path, "exec", dont_inherit=True, optimize=0)
    exec(code, module.__dict__, module.__dict__)
    return module


CHECKER_RAW, READER_RAW = preflight()
CHECKER = load_checker(CHECKER_RAW)
VALID_H1_A = "h1:" + base64.b64encode(bytes(32)).decode("ascii")
VALID_H1_B = "h1:" + base64.b64encode(bytes([1]) * 32).decode("ascii")


class FakeRunner:
    @staticmethod
    def parse_go_mod(raw: bytes, expected_module: str) -> dict[str, object]:
        text = raw.decode("utf-8")
        if f"module {expected_module}" not in text:
            raise ValueError("module mismatch")
        return {}

    @staticmethod
    def tokenize_mod_line(line: str) -> list[str]:
        before_comment = line.split("//", 1)[0]
        return shlex.split(before_comment, comments=False, posix=True)


def minimal_witness(h1: str) -> dict[str, object]:
    return {
        "archivePath": "held.zip",
        "entryPath": "module@v1.0.0/go.sum",
        "line": 1,
        "text": f"example.test/target v1.0.0 {h1}",
        "h1": h1,
    }


class UnitBoundaryTests(unittest.TestCase):
    def test_checker_has_no_network_or_write_capability_import(self) -> None:
        tree = ast.parse(CHECKER_RAW.decode("utf-8"))
        banned_modules = {
            "asyncio",
            "http",
            "requests",
            "socket",
            "ssl",
            "subprocess",
            "urllib",
        }
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Attribute):
                self.assertNotIn(
                    node.attr,
                    {"O_APPEND", "O_CREAT", "O_RDWR", "O_TRUNC", "O_WRONLY"},
                )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotEqual(node.func.id, "input")
        self.assertTrue(imported.isdisjoint(banned_modules))

    def test_h1_validation_is_exact(self) -> None:
        self.assertTrue(CHECKER.valid_h1(VALID_H1_A))
        self.assertFalse(CHECKER.valid_h1("h1:not-base64"))
        self.assertFalse(
            CHECKER.valid_h1(
                "h1:" + base64.b64encode(bytes(31)).decode("ascii")
            )
        )
        self.assertFalse(CHECKER.valid_h1("sha256:" + "0" * 64))

    def test_declaration_capture_preserves_line_and_parent(self) -> None:
        raw = (
            b"module example.test/parent\n\n"
            b"require (\n"
            b"\texample.test/target v1.0.0 // indirect\n"
            b")\n"
        )
        target = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        result = CHECKER.capture_declarations(
            raw=raw,
            runner=FakeRunner,
            targets=target,
            holder_module="example.test/parent",
            holder_version="v2.0.0",
            holder_wave="synthetic",
            container_kind="external_mod",
            path="parent.mod",
            container_raw_sha256=sha256(raw),
            entry_raw_sha256=None,
        )
        rows = result[("example.test/target", "v1.0.0")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["line"], 4)
        self.assertEqual(
            rows[0]["text"],
            "\texample.test/target v1.0.0 // indirect",
        )
        self.assertEqual(rows[0]["holderModule"], "example.test/parent")

    def test_go_sum_missing_and_conflicting_values_fail_closure(self) -> None:
        wave = [
            {
                "tupleOrder": 1,
                "module": "example.test/target",
                "version": "v1.0.0",
                "selectedByGraphAlgorithm": False,
            }
        ]
        pair = ("example.test/target", "v1.0.0")
        declaration = {
            "path": "parent.mod",
            "line": 1,
            "text": "require example.test/target v1.0.0",
        }
        missing = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations={pair: [declaration]},
            module_zip_h1={pair: []},
            go_mod_h1={pair: [minimal_witness(VALID_H1_A)]},
        )[0]
        self.assertFalse(missing["identityPairComplete"])
        conflict = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations={pair: [declaration]},
            module_zip_h1={
                pair: [
                    minimal_witness(VALID_H1_A),
                    minimal_witness(VALID_H1_B),
                ]
            },
            go_mod_h1={pair: [minimal_witness(VALID_H1_A)]},
        )[0]
        self.assertTrue(conflict["moduleZipH1Conflict"])
        self.assertFalse(conflict["identityPairComplete"])

    def test_go_sum_rejects_bad_shape_and_utf8(self) -> None:
        target = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        common = {
            "targets": target,
            "holder_module": "example.test/parent",
            "holder_version": "v2.0.0",
            "holder_wave": "synthetic",
            "archive_path": "held.zip",
            "archive_raw_sha256": "0" * 64,
            "entry_path": "parent@v2.0.0/go.sum",
        }
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.parse_go_sum_entry(
                raw=b"example.test/target v1.0.0 bad\n",
                **common,
            )
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.parse_go_sum_entry(raw=b"\xff\n", **common)

    def test_zip_inventory_rejects_duplicate_and_unsafe_names(self) -> None:
        duplicate = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("module@v1.0.0/go.sum", b"")
                archive.writestr("module@v1.0.0/go.sum", b"")
        duplicate.seek(0)
        with zipfile.ZipFile(duplicate, "r") as archive:
            with self.assertRaises(CHECKER.DecisionFailure):
                CHECKER.validate_archive_names(archive.infolist())
        unsafe = zipfile.ZipInfo("../go.sum")
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.validate_archive_names([unsafe])

    def test_pinned_file_rejects_hardlink_and_symlink_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir(mode=0o700)
            original = root / "one"
            original.write_bytes(b"x")
            os.link(original, root / "two")
            with self.assertRaises(Exception):
                CHECKER.PinnedFile(root, "one")
            alias = Path(temporary) / "alias"
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(Exception):
                CHECKER.PinnedFile(alias, "one")

    def test_held_namespace_rejects_late_collision_and_root_rebind(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir(mode=0o700)
            dependency = root / CHECKER.DEPENDENCY_ROOT
            dependency.mkdir(parents=True)
            with CHECKER.HeldNamespace(root) as held:
                claim = dependency / Path(CHECKER.WAVE4_CLAIM_PATH).name
                claim.write_bytes(b"late")
                with self.assertRaises(CHECKER.DecisionFailure):
                    held.final_barrier()
                claim.unlink()
                staging = dependency / (
                    CHECKER.WAVE4_STAGING_PREFIX + "late"
                )
                staging.mkdir()
                with self.assertRaises(CHECKER.DecisionFailure):
                    held.final_barrier()
                staging.rmdir()
                final = dependency / CHECKER.WAVE4_FINAL_NAME
                final.mkdir()
                with self.assertRaises(CHECKER.DecisionFailure):
                    held.final_barrier()
                final.rmdir()
                held.final_barrier()

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "root"
            root.mkdir(mode=0o700)
            (root / CHECKER.DEPENDENCY_ROOT).mkdir(parents=True)
            held = CHECKER.HeldNamespace(root)
            displaced = base / "displaced"
            root.rename(displaced)
            root.mkdir(mode=0o700)
            (root / CHECKER.DEPENDENCY_ROOT).mkdir(parents=True)
            try:
                with self.assertRaises(CHECKER.DecisionFailure):
                    held.final_barrier()
            finally:
                held.close()

    def test_wave4_candidate_content_is_reconstructed_not_copied(
        self,
    ) -> None:
        wave4 = load_wave4_candidate_checker()
        rows = wave4.wave4_rows(wave4.expected_frontier_rows())
        combined = {
            "contentBinding": {
                "sha256": CHECKER.COMBINED_V2_CONTENT_SHA256,
            }
        }
        projected = CHECKER.reconstruct_wave4_candidate(
            wave4=wave4,
            combined_candidate=combined,
            wave_rows=rows,
        )
        self.assertEqual(
            projected["contentBinding"]["sha256"],
            CHECKER.WAVE4_CANDIDATE_CONTENT_SHA256,
        )
        original = CHECKER.WAVE4_CANDIDATE_CONTENT_SHA256
        CHECKER.WAVE4_CANDIDATE_CONTENT_SHA256 = "0" * 64
        try:
            with self.assertRaises(CHECKER.DecisionFailure):
                CHECKER.reconstruct_wave4_candidate(
                    wave4=wave4,
                    combined_candidate=combined,
                    wave_rows=rows,
                )
        finally:
            CHECKER.WAVE4_CANDIDATE_CONTENT_SHA256 = original


class LiveRepositoryTests(unittest.TestCase):
    def run_checker(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        preflight()
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(ROOT / CHECKER_PATH),
                *arguments,
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=360,
        )

    def test_expected_bytes_and_materialized_decision(self) -> None:
        generated = self.run_checker("--print-expected")
        self.assertEqual(generated.returncode, 0, generated.stderr.decode())
        decision_raw = (ROOT / DECISION_PATH).read_bytes()
        self.assertEqual(generated.stdout, decision_raw)
        parsed = json.loads(decision_raw)
        self.assertEqual(decision_raw, canonical(parsed))
        self.assertEqual(
            parsed["identityResolution"]["compactIdentitySha256"],
            CHECKER.COMPACT_IDENTITY_SHA256,
        )
        self.assertEqual(
            parsed["identityResolution"]["fullWitnessSha256"],
            CHECKER.FULL_WITNESS_SHA256,
        )
        self.assertTrue(
            parsed["sourceAcquisitionPreparation"]["acquisitionReady"]
        )
        self.assertFalse(
            parsed["sourceAcquisitionPreparation"][
                "acquisitionAuthorizedByThisDecision"
            ]
        )
        self.assertFalse(
            parsed["authority"]["externalAuthenticationRequired"]
        )
        self.assertFalse(parsed["authority"]["userActionRequired"])
        identity_by_order = {
            row["tupleOrder"]: row
            for row in parsed["identityResolution"]["tuples"]
        }
        requests = parsed["sourceAcquisitionPreparation"]["requestSet"]
        self.assertEqual(len(requests), 32)
        self.assertEqual(
            parsed["sourceAcquisitionPreparation"]["requestOrder"],
            "tuple_order_ascending_mod_then_zip",
        )
        self.assertEqual(
            [row["requestOrdinal"] for row in requests],
            list(range(1, 33)),
        )
        self.assertEqual(len({row["url"] for row in requests}), 32)
        self.assertEqual(
            len({row["acceptedFileName"] for row in requests}),
            32,
        )
        expected_keys = {
            "requestOrdinal",
            "tupleOrder",
            "module",
            "version",
            "selectedByGraphAlgorithm",
            "resourceKind",
            "method",
            "host",
            "url",
            "expectedH1",
            "maximumResponseBytes",
            "acceptedFileName",
            "authenticationRequired",
            "networkAuthorized",
            "acquisitionAuthorized",
        }
        for index in range(0, 32, 2):
            expected_order = index // 2 + 1
            mod = requests[index]
            archive = requests[index + 1]
            identity = identity_by_order[mod["tupleOrder"]]
            self.assertEqual(set(mod), expected_keys)
            self.assertEqual(set(archive), expected_keys)
            self.assertEqual(mod["resourceKind"], "mod")
            self.assertEqual(archive["resourceKind"], "zip")
            self.assertEqual(mod["tupleOrder"], expected_order)
            self.assertEqual(mod["tupleOrder"], archive["tupleOrder"])
            self.assertEqual(mod["module"], archive["module"])
            self.assertEqual(mod["version"], archive["version"])
            self.assertEqual(mod["module"], identity["module"])
            self.assertEqual(mod["version"], identity["version"])
            self.assertEqual(
                mod["selectedByGraphAlgorithm"],
                identity["selectedByGraphAlgorithm"],
            )
            self.assertEqual(
                archive["selectedByGraphAlgorithm"],
                identity["selectedByGraphAlgorithm"],
            )
            self.assertEqual(mod["expectedH1"], identity["goModH1"])
            self.assertEqual(
                archive["expectedH1"],
                identity["moduleZipH1"],
            )
            self.assertEqual(mod["maximumResponseBytes"], 1024 * 1024)
            self.assertEqual(
                archive["maximumResponseBytes"],
                16 * 1024 * 1024,
            )
            self.assertEqual(mod["method"], archive["method"])
            self.assertEqual(mod["method"], "GET")
            self.assertEqual(mod["host"], "proxy.golang.org")
            self.assertEqual(archive["host"], "proxy.golang.org")
            self.assertEqual(
                mod["url"],
                (
                    f"https://proxy.golang.org/{identity['module']}/"
                    f"@v/{identity['version']}.mod"
                ),
            )
            self.assertEqual(
                archive["url"],
                (
                    f"https://proxy.golang.org/{identity['module']}/"
                    f"@v/{identity['version']}.zip"
                ),
            )
            tuple_digest = sha256(
                (
                    f"{identity['module']}\n"
                    f"{identity['version']}\n"
                ).encode("utf-8")
            )
            self.assertEqual(
                mod["acceptedFileName"],
                f"{expected_order:03d}-{tuple_digest[:20]}.mod",
            )
            self.assertEqual(
                archive["acceptedFileName"],
                f"{expected_order:03d}-{tuple_digest[:20]}.zip",
            )
            self.assertFalse(mod["authenticationRequired"])
            self.assertFalse(archive["authenticationRequired"])
            self.assertFalse(mod["networkAuthorized"])
            self.assertFalse(archive["networkAuthorized"])
            self.assertFalse(mod["acquisitionAuthorized"])
            self.assertFalse(archive["acquisitionAuthorized"])

    def test_normal_checker_summary(self) -> None:
        completed = self.run_checker()
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stderr, b"")
        summary = json.loads(completed.stdout)
        self.assertEqual(
            summary["status"],
            "validated_16_of_16_acquisition_ready_not_authorized",
        )
        self.assertTrue(summary["validationPassed"])
        self.assertEqual(summary["completeIdentityPairCount"], 16)
        self.assertFalse(summary["acquisitionAuthorized"])
        self.assertFalse(summary["externalAuthenticationRequired"])
        self.assertFalse(summary["userActionRequired"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
