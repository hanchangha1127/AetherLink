#!/usr/bin/env python3
"""Tests for the read-only Wave3 dependency identity decision."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (sys.flags.isolated and sys.flags.dont_write_bytecode and sys.flags.no_site):
    raise RuntimeError("tests require `python3 -I -B -S`")

import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location("wave3_decision_v1", PATH)
assert SPEC and SPEC.loader
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


class Wave3DecisionV1Tests(unittest.TestCase):
    def expected(self):
        return W.evaluate(False)[0]

    def test_01_live_exact_decision(self) -> None:
        expected, summary = W.evaluate(True)
        self.assertEqual(
            json.loads((W.ROOT / W.DECISION_PATH).read_bytes()),
            expected,
        )
        self.assertTrue(summary["validationPassed"])
        self.assertFalse(summary["acquisitionReady"])
        self.assertFalse(summary["acquisitionAuthorized"])
        self.assertEqual(summary["identityRecordCount"], 31)
        self.assertEqual(summary["heldArchiveOpenCount"], 35)
        self.assertEqual(summary["heldGoSumMemberDecodeCount"], 22)
        self.assertEqual(summary["futureResponseDecodeCount"], 0)

    def test_02_exact_frontier_order_and_digest(self) -> None:
        decision = self.expected()
        wave = decision["wave"]
        self.assertEqual(wave["tupleCount"], 16)
        self.assertEqual(wave["graphSelectedTupleCount"], 4)
        self.assertEqual(wave["versionSpecificNonSelectedTupleCount"], 12)
        self.assertEqual(wave["rejectedTupleCount"], 0)
        self.assertEqual(
            decision["graphBinding"]["exactFrontierCanonicalSha256"],
            W.EXPECTED_FRONTIER_SHA256,
        )
        self.assertEqual(
            [(row["module"], row["version"]) for row in wave["tuples"]],
            [(module, version) for module, version, _ in W.FRONTIER],
        )

    def test_03_identity_counts_and_pty_gap_are_exact(self) -> None:
        wave = self.expected()["wave"]
        self.assertEqual(wave["parentDeclarationCount"], 18)
        self.assertEqual(wave["goModH1Count"], 16)
        self.assertEqual(wave["moduleZipH1Count"], 15)
        self.assertEqual(wave["identityRecordCount"], 31)
        self.assertEqual(wave["requiredIdentityRecordCount"], 32)
        pty = wave["tuples"][0]
        self.assertEqual(pty["module"], "github.com/kr/pty")
        self.assertEqual(
            pty["checksumIdentity"]["goModH1"],
            "h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ=",
        )
        self.assertIsNone(pty["checksumIdentity"]["moduleZipH1"])
        self.assertFalse(pty["acquisitionReady"])

    def test_04_no_tuple_dedup_or_higher_version_replacement(self) -> None:
        tuples = self.expected()["wave"]["tuples"]
        self.assertEqual(sum(row["selectedByGraphAlgorithm"] for row in tuples), 4)
        self.assertEqual(
            sum(not row["selectedByGraphAlgorithm"] for row in tuples),
            12,
        )
        self.assertTrue(all(row["versionSpecificVertexRetained"] for row in tuples))
        self.assertTrue(all(not row["rejected"] for row in tuples))
        self.assertEqual(len({row["tupleId"] for row in tuples}), 16)

    def test_05_parent_declarations_are_bound_to_held_mod_bytes(self) -> None:
        context = W.DecisionContext(W.ROOT, include_decision=True)
        try:
            decision = W.content_bound(W.expected_payload(context))
            raw = context.lineage.authority.sources.raw
            parents = [
                parent
                for row in decision["wave"]["tuples"]
                for parent in row["parentDeclarations"]
            ]
            self.assertEqual(len(parents), 18)
            for parent in parents:
                self.assertEqual(
                    W.sha256(raw[parent["sourcePath"]]),
                    parent["sourceRawSha256"],
                )
                lines = raw[parent["sourcePath"]].decode().splitlines()
                self.assertEqual(
                    lines[parent["line"] - 1].strip(),
                    parent["declaration"],
                )
        finally:
            context.close()

    def test_06_independent_held_go_sum_scan_confirms_31_nonconflicting_h1(self) -> None:
        context = W.DecisionContext(W.ROOT, include_decision=True)
        try:
            decision = W.content_bound(W.expected_payload(context))
            source_rows = decision["predecessorBindings"]["heldSourceInputSet"][
                "files"
            ]
            raw = context.lineage.authority.sources.raw
            result = W.strict_json(
                context.lineage.authority.terminal.raw[W.RESULT_PATH]
            )
            bindings = result["candidateProjection"]["inputSet"][
                "sourceBindings"
            ]
            binding_by_path = {row["path"]: row for row in bindings}
            found = {}
            occurrences = []
            archive_open_count = 0
            member_decode_count = 0
            for source in source_rows:
                path = source["path"]
                if not path.endswith(".zip"):
                    continue
                binding = binding_by_path[path]
                archive_open_count += 1
                with zipfile.ZipFile(io.BytesIO(raw[path])) as archive:
                    for member in archive.namelist():
                        if not member.endswith("/go.sum"):
                            continue
                        member_raw = archive.read(member)
                        member_decode_count += 1
                        for line_number, line in enumerate(
                            member_raw.decode().splitlines(),
                            1,
                        ):
                            parts = line.strip().split()
                            if len(parts) != 3 or not parts[2].startswith("h1:"):
                                continue
                            version = parts[1]
                            kind = "mod" if version.endswith("/go.mod") else "zip"
                            version = version.removesuffix("/go.mod")
                            key = (parts[0], version, kind)
                            found.setdefault(key, set()).add(parts[2])
                            occurrences.append(
                                {
                                    "sourceModule": binding["module"],
                                    "sourceVersion": binding["version"],
                                    "sourceTupleOrder": binding["tupleOrder"],
                                    "sourceArchivePath": path,
                                    "sourceArchiveRawSha256": source[
                                        "rawSha256"
                                    ],
                                    "memberPath": member,
                                    "memberRawSha256": W.sha256(member_raw),
                                    "lineNumber": line_number,
                                    "checksumKind": (
                                        "go_mod_h1"
                                        if kind == "mod"
                                        else "module_zip_h1"
                                    ),
                                    "exactRawLine": line,
                                    "module": parts[0],
                                    "version": version,
                                    "h1": parts[2],
                                }
                            )
            self.assertEqual(archive_open_count, 35)
            self.assertEqual(member_decode_count, 22)
            observed = 0
            for tuple_row in decision["wave"]["tuples"]:
                module = tuple_row["module"]
                version = tuple_row["version"]
                mod_h1, zip_h1 = W.H1[(module, version)]
                self.assertEqual(found[(module, version, "mod")], {mod_h1})
                observed += 1
                if zip_h1 is None:
                    self.assertNotIn((module, version, "zip"), found)
                else:
                    self.assertEqual(found[(module, version, "zip")], {zip_h1})
                    observed += 1
                parent_pairs = {
                    (row["parentModule"], row["parentVersion"])
                    for row in tuple_row["parentDeclarations"]
                }
                for evidence_key, kind, expected_h1 in (
                    ("goModEvidence", "go_mod_h1", mod_h1),
                    ("moduleZipEvidence", "module_zip_h1", zip_h1),
                ):
                    evidence = tuple_row["checksumIdentity"][evidence_key]
                    matching = [
                        row
                        for row in occurrences
                        if row["module"] == module
                        and row["version"] == version
                        and row["checksumKind"] == kind
                    ]
                    if expected_h1 is None:
                        self.assertEqual(matching, [])
                        self.assertIsNone(evidence)
                        continue
                    self.assertEqual({row["h1"] for row in matching}, {expected_h1})
                    selected = sorted(
                        matching,
                        key=lambda row: (
                            0
                            if (
                                row["sourceModule"],
                                row["sourceVersion"],
                            )
                            in parent_pairs
                            else 1,
                            row["sourceTupleOrder"],
                            row["sourceArchivePath"],
                            row["memberPath"],
                            row["lineNumber"],
                        ),
                    )[0]
                    self.assertEqual(evidence, selected)
            self.assertEqual(observed, 31)
            self.assertFalse(
                any(
                    row["module"] == "github.com/kr/pty"
                    and row["version"] == "v1.1.1"
                    and row["checksumKind"] == "module_zip_h1"
                    for row in occurrences
                )
            )
        finally:
            context.close()

    def test_07_h1_parent_and_authority_mutations_do_not_match(self) -> None:
        expected = self.expected()
        for mutation in ("h1", "parent", "authority"):
            changed = copy.deepcopy(expected)
            changed.pop("contentBinding")
            if mutation == "h1":
                changed["wave"]["tuples"][0]["checksumIdentity"][
                    "moduleZipH1"
                ] = "h1:" + "A" * 44
            elif mutation == "parent":
                changed["wave"]["tuples"][8]["parentDeclarations"].pop()
            else:
                changed["authority"]["networkAuthorized"] = True
            self.assertNotEqual(W.content_bound(changed), expected)

    def test_08_held_source_raw_mutation_fails_closed(self) -> None:
        context = W.DecisionContext(W.ROOT, include_decision=True)
        try:
            path = next(iter(context.lineage.authority.sources.raw))
            original = context.lineage.authority.sources.raw[path]
            context.lineage.authority.sources.raw[path] = original + b"x"
            with self.assertRaises(W.DecisionError):
                W.expected_payload(context)
        finally:
            context.close()

    def test_09_terminal_raw_mutation_fails_closed(self) -> None:
        context = W.DecisionContext(W.ROOT, include_decision=True)
        try:
            original = context.outputs.raw[W.V3_RECEIPT_PATH]
            context.outputs.raw[W.V3_RECEIPT_PATH] = original.replace(
                b"formal_replacement_recovery_readback_complete",
                b"formal_replacement_recovery_readback_blocked_",
                1,
            )
            with self.assertRaises(W.DecisionError):
                W.expected_payload(context)
        finally:
            context.close()

    def test_10_held_file_named_fd_swap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            relative = "held/input.mod"
            target = root / relative
            target.parent.mkdir()
            target.write_bytes(b"module example.test/a\n")
            os.chmod(target, 0o600)
            binding = {
                "path": relative,
                "rawSha256": W.sha256(target.read_bytes()),
                "maximumBytes": 1024,
                "ownerOnly": True,
            }
            held = W.PERMIT.DECISION.V2.RECOVERY.TRUST.HeldSet(root, [binding])
            moved = target.with_name("input.held")
            try:
                target.rename(moved)
                target.write_bytes(moved.read_bytes())
                with self.assertRaises(Exception):
                    held.final_barrier()
            finally:
                target.unlink()
                moved.rename(target)
                held.close()

    def test_11_wave3_future_namespace_and_staging_are_absent(self) -> None:
        decision = self.expected()
        self.assertTrue(
            decision["futureNamespaceReservation"]["allCurrentlyAbsent"]
        )
        for path in (
            W.WAVE3_CLAIM_PATH,
            W.WAVE3_FINAL_PATH,
            *W.WAVE3_FUTURE_DOCS,
        ):
            self.assertFalse((W.ROOT / path).exists(), path)
        dependency = W.ROOT / W.DEPENDENCY_ROOT
        self.assertFalse(
            any(path.name.startswith(W.WAVE3_STAGING_PREFIX) for path in dependency.iterdir())
        )

    def test_12_all_execution_and_auth_authorities_are_false(self) -> None:
        authority = self.expected()["authority"]
        for key, value in authority.items():
            if key == "decisionRecorded":
                self.assertTrue(value)
            else:
                self.assertFalse(value, key)

    def test_13_checker_decodes_held_archives_without_extract_write_network(self) -> None:
        source = PATH.read_text(encoding="utf-8")
        self.assertIn("zipfile.ZipFile", source)
        for token in (
            "socket.",
            "urllib.",
            "subprocess.",
            "os.write(",
            "O_CREAT",
            "O_TRUNC",
            ".extract(",
            ".extractall(",
        ):
            self.assertNotIn(token, source)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=W.ROOT,
            capture_output=True,
            check=False,
        )

    def test_14_canonical_cli_default_print_and_invalid(self) -> None:
        default = self.run_cli()
        self.assertEqual(default.returncode, 0)
        self.assertFalse(json.loads(default.stdout)["acquisitionAuthorized"])
        printed = self.run_cli("--print-expected")
        self.assertEqual(printed.returncode, 0)
        self.assertEqual(printed.stdout, (W.ROOT / W.DECISION_PATH).read_bytes())
        invalid = self.run_cli("--secret")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"secret", invalid.stdout)

    def test_15_strict_json_and_content_binding_mutations_fail(self) -> None:
        with self.assertRaises(W.DecisionError):
            W.strict_json(b'{"a":1,"a":2}\n')
        expected = self.expected()
        changed = copy.deepcopy(expected)
        changed["wave"]["identityRecordCount"] = 32
        self.assertNotEqual(changed, expected)

    def test_16_pty_zip_identity_cannot_be_forged_from_constants(self) -> None:
        key = ("github.com/kr/pty", "v1.1.1")
        original = W.H1[key]
        context = W.DecisionContext(W.ROOT, include_decision=True)
        try:
            W.H1[key] = (original[0], "h1:" + "A" * 44)
            with self.assertRaises(W.DecisionError):
                W.expected_payload(context)
        finally:
            W.H1[key] = original
            context.close()

    def test_17_h1_conflict_and_evidence_provenance_drift_fail(self) -> None:
        with self.assertRaises(W.DecisionError):
            W.choose_h1_evidence(
                [{"h1": "h1:a"}, {"h1": "h1:b"}],
                set(),
                "h1:a",
            )
        expected = self.expected()
        evidence = expected["wave"]["tuples"][0]["checksumIdentity"][
            "goModEvidence"
        ]
        mutations = {
            "sourceModule": "example.invalid/source",
            "sourceVersion": "v0.0.0",
            "sourceTupleOrder": 999,
            "sourceArchivePath": "build/invalid.zip",
            "sourceArchiveRawSha256": "0" * 64,
            "memberPath": "invalid/go.sum",
            "memberRawSha256": "1" * 64,
            "lineNumber": evidence["lineNumber"] + 1,
            "exactRawLine": evidence["exactRawLine"] + " ",
        }
        for field, value in mutations.items():
            changed = copy.deepcopy(expected)
            changed.pop("contentBinding")
            changed["wave"]["tuples"][0]["checksumIdentity"][
                "goModEvidence"
            ][field] = value
            self.assertNotEqual(W.content_bound(changed), expected, field)

    def test_18_partial_archive_failure_reports_actual_operations(self) -> None:
        W.reset_operation_counters()
        with self.assertRaises(W.DecisionError):
            W.derive_h1_evidence(
                [
                    {
                        "kind": "zip",
                        "path": "held/bad.zip",
                        "module": "example.invalid/bad",
                        "version": "v0.0.0",
                        "tupleOrder": 1,
                        "rawSha256": W.sha256(b"not-a-zip"),
                    }
                ],
                {"held/bad.zip": b"not-a-zip"},
            )
        self.assertEqual(
            W.operation_counters(),
            {
                "heldArchiveOpenCount": 1,
                "heldGoSumMemberDecodeCount": 0,
                "futureResponseDecodeCount": 0,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
