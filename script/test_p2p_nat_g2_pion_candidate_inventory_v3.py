#!/usr/bin/env python3
"""Synthetic-only tests for pure G2 Pion v3 candidate aggregation."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import struct
import tracemalloc
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "script/p2p_nat_g2_pion_candidate_inventory_v3.py"


def load_source_without_importlib(path: Path, *, name: str) -> ModuleType:
    module = ModuleType(name)
    module.__file__ = str(path)
    raw = path.read_bytes()
    exec(
        compile(raw, path.name, "exec", flags=0, dont_inherit=True, optimize=0),
        module.__dict__,
        module.__dict__,
    )
    return module


INVENTORY = load_source_without_importlib(
    MODULE_PATH,
    name="g2_pion_candidate_inventory_v3_test_subject",
)
SOURCE_BODY_SENTINEL = "V3_SOURCE_BODY_MUST_NEVER_APPEAR_IN_OUTPUT_31d0e7"


def units_by_id(result: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["patchUnit"]: row for row in result["patchUnits"]}


def rules_by_id(unit: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["ruleId"]: row for row in unit["rules"]}


def egress_rule(result: dict[str, object]) -> dict[str, object]:
    unit = units_by_id(result)[INVENTORY.PATCH_UNITS[0]]
    return rules_by_id(unit)["egress-dial"]


def lines_with(word: str, count: int) -> bytes:
    return "".join(f"{word} // row-{index}\n" for index in range(count)).encode()


class CandidateInventoryV3Tests(unittest.TestCase):
    def test_rule_definitions_exactly_match_v2_semantics_and_order(self) -> None:
        expected = (
            (
                INVENTORY.PATCH_UNITS[0],
                (
                    ("egress-dial", r"\b(?:Dial|DialContext|DialUDP|WriteTo|WriteToUDP)\b"),
                    ("egress-listen", r"\b(?:Listen|ListenPacket|ListenUDP|PacketConn)\b"),
                    ("candidate-io", r"\b(?:Candidate|UDPMux|UniversalUDPMux|sendBindingRequest)\b"),
                ),
            ),
            (
                INVENTORY.PATCH_UNITS[1],
                (
                    ("diagnostic-call", r"\b(?:Tracef|Debugf|Infof|Warnf|Errorf|Logf|Logger)\b"),
                    ("credential-token", r"(?i)\b(?:credential|password|username|ufrag|pwd|secret)\b"),
                ),
            ),
            (
                INVENTORY.PATCH_UNITS[2],
                (
                    ("callback", r"\bOn(?:ConnectionStateChange|SelectedCandidatePairChange)\b"),
                    ("channel", r"\b(?:chan|close)\b|make\s*\(\s*chan\b"),
                    ("event", r"(?i)\b(?:event|callback|handler)\b"),
                ),
            ),
            (
                INVENTORY.PATCH_UNITS[3],
                (
                    ("deadline", r"\b(?:SetDeadline|SetReadDeadline|SetWriteDeadline|WithTimeout)\b"),
                    ("shutdown", r"\b(?:Close|cancel|WaitGroup|Done)\b"),
                    ("time-bound", r"(?i)\b(?:deadline|timeout|shutdown)\b"),
                ),
            ),
            (
                INVENTORY.PATCH_UNITS[4],
                (
                    ("transport-path", r"(?i)\b(?:tcp|udp|mdns|proxy|relay|host|srflx|upnp)\b"),
                    ("network-type", r"\b(?:NetworkType|CandidateType|TCPType)\b"),
                ),
            ),
            (
                INVENTORY.PATCH_UNITS[5],
                (
                    ("resolver", r"\b(?:Resolver|LookupIP|LookupHost|ResolveIPAddr)\b"),
                    ("turn-tls", r"\b(?:ServerName|InsecureSkipVerify|TLSConfig|tls\.Config|TURN)\b"),
                    ("network-injection", r"\b(?:Net|TransportNet|vnet)\b"),
                ),
            ),
            (
                INVENTORY.PATCH_UNITS[6],
                (
                    ("pre-auth", r"(?i)\b(?:auth|credential|username|password|ufrag|pwd)\b"),
                    ("promotion-state", r"\b(?:ConnectionState|setState|validate|Validate)\b"),
                    ("one-use", r"(?i)\b(?:one.?use|single.?use|nonce|replay)\b"),
                ),
            ),
        )
        self.assertEqual(tuple(INVENTORY.REVIEW_RULES.items()), expected)

    def test_zero_one_eight_nine_512_and_513_hits(self) -> None:
        for count in (0, 1, 8, 9, 512, 513):
            with self.subTest(count=count):
                result = INVENTORY.aggregate_candidate_inventory(
                    (("candidate.go", lines_with("Dial", count)),)
                )
                rule = egress_rule(result)
                recorded = min(count, INVENTORY.REPRESENTATIVE_LIMIT_PER_RULE)
                self.assertEqual(rule["totalHitCount"], count)
                self.assertEqual(rule["recordedRepresentativeCount"], recorded)
                self.assertEqual(rule["omittedHitCount"], count - recorded)
                self.assertIs(rule["truncated"], count > recorded)
                self.assertEqual(len(rule["representatives"]), recorded)
                if count:
                    self.assertGreaterEqual(recorded, 1)

    def test_representatives_are_exact_lowest_ranks_with_tuple_tiebreak(self) -> None:
        count = 50
        result = INVENTORY.aggregate_candidate_inventory(
            (("z.go", lines_with("Dial", count)),)
        )
        representatives = egress_rule(result)["representatives"]
        expected = []
        path_bytes = b"z.go"
        for line in range(1, count + 1):
            expected.append(
                {
                    "path": "z.go",
                    "line": line,
                    "ruleId": "egress-dial",
                    "rankSha256": INVENTORY.representative_rank_sha256(
                        path_bytes, line, "egress-dial"
                    ),
                }
            )
        expected.sort(
            key=lambda row: (
                row["rankSha256"],
                row["path"].encode(),
                row["line"],
                row["ruleId"].encode(),
            )
        )
        self.assertEqual(representatives, expected[:8])

    def test_duplicate_word_is_one_hit_and_multi_rule_line_is_two_hits(self) -> None:
        result = INVENTORY.aggregate_candidate_inventory(
            (("candidate.go", b"Dial Dial Candidate Candidate\n"),)
        )
        unit = units_by_id(result)[INVENTORY.PATCH_UNITS[0]]
        rules = rules_by_id(unit)
        self.assertEqual(rules["egress-dial"]["totalHitCount"], 1)
        self.assertEqual(rules["candidate-io"]["totalHitCount"], 1)
        self.assertEqual(unit["totalHitCount"], 2)

    def test_rare_nonzero_rule_always_retains_a_representative(self) -> None:
        raw = lines_with("Dial", 513) + b"sendBindingRequest\n"
        result = INVENTORY.aggregate_candidate_inventory((("candidate.go", raw),))
        unit = units_by_id(result)[INVENTORY.PATCH_UNITS[0]]
        rules = rules_by_id(unit)
        self.assertEqual(rules["egress-dial"]["totalHitCount"], 513)
        self.assertEqual(rules["egress-dial"]["recordedRepresentativeCount"], 8)
        self.assertEqual(rules["candidate-io"]["totalHitCount"], 1)
        self.assertEqual(rules["candidate-io"]["recordedRepresentativeCount"], 1)

    def test_input_permutations_have_identical_output_and_byte_path_order(self) -> None:
        entries = (
            ("z.go", b"Dial\nDebugf\n"),
            ("\u00e4.go", b"nonce\n"),
            ("a.go", b"Resolver\n"),
        )
        expected = INVENTORY.aggregate_candidate_inventory(entries)
        for permutation in (
            tuple(reversed(entries)),
            (entries[1], entries[0], entries[2]),
            (entries[2], entries[1], entries[0]),
        ):
            self.assertEqual(
                INVENTORY.aggregate_candidate_inventory(permutation),
                expected,
            )

    def test_complete_digest_binds_logical_line_but_rank_does_not(self) -> None:
        first = INVENTORY.aggregate_candidate_inventory(
            (("candidate.go", b"Dial // alpha\r\n"),)
        )
        second = INVENTORY.aggregate_candidate_inventory(
            (("candidate.go", b"Dial // beta\r\n"),)
        )
        first_unit = units_by_id(first)[INVENTORY.PATCH_UNITS[0]]
        second_unit = units_by_id(second)[INVENTORY.PATCH_UNITS[0]]
        self.assertNotEqual(
            first_unit["completeObservationSha256"],
            second_unit["completeObservationSha256"],
        )
        self.assertEqual(
            rules_by_id(first_unit)["egress-dial"]["representatives"],
            rules_by_id(second_unit)["egress-dial"]["representatives"],
        )

    def test_complete_digest_encoding_is_exact_and_excludes_crlf_terminator(self) -> None:
        result = INVENTORY.aggregate_candidate_inventory(
            (("candidate.go", b"Dial // exact\r\n"),)
        )
        unit = units_by_id(result)[INVENTORY.PATCH_UNITS[0]]
        patch_unit_bytes = INVENTORY.PATCH_UNITS[0].encode()
        path = b"candidate.go"
        rule = b"egress-dial"
        expected = hashlib.sha256()
        expected.update(INVENTORY.COMPLETE_OBSERVATION_HASH_DOMAIN)
        expected.update(struct.pack(">H", len(patch_unit_bytes)) + patch_unit_bytes)
        expected.update(struct.pack(">I", len(path)) + path)
        expected.update(struct.pack(">Q", 1))
        expected.update(struct.pack(">H", len(rule)) + rule)
        expected.update(hashlib.sha256(b"Dial // exact").digest())
        self.assertEqual(unit["completeObservationSha256"], expected.hexdigest())

    def test_source_bodies_and_line_digests_are_never_output(self) -> None:
        raw = f"Dial // {SOURCE_BODY_SENTINEL}\n".encode()
        result = INVENTORY.aggregate_candidate_inventory((("candidate.go", raw),))
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn(SOURCE_BODY_SENTINEL, encoded)
        self.assertNotIn(hashlib.sha256(raw.rstrip(b"\n")).hexdigest(), encoded)
        self.assertNotIn("lineSha256", encoded)

    def test_large_inventory_keeps_output_and_representatives_capped(self) -> None:
        raw = lines_with("Dial", 20_000)
        tracemalloc.start()
        result = INVENTORY.aggregate_candidate_inventory((("large.go", raw),))
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rule = egress_rule(result)
        self.assertEqual(rule["totalHitCount"], 20_000)
        self.assertEqual(len(rule["representatives"]), 8)
        self.assertLess(len(json.dumps(result)), 100_000)
        self.assertLess(peak, 16_000_000)

    def test_rejects_bool_as_int_and_limits_above_fixed_ceilings(self) -> None:
        for field in (
            "source_entries",
            "path_bytes",
            "path_components",
            "component_bytes",
            "source_bytes",
            "total_source_bytes",
            "logical_lines_per_source",
            "total_logical_lines",
        ):
            with self.subTest(field=field):
                values = vars(INVENTORY.InventoryLimits()).copy()
                values[field] = True
                with self.assertRaises(INVENTORY.CandidateInventoryError):
                    INVENTORY.aggregate_candidate_inventory(
                        (),
                        limits=INVENTORY.InventoryLimits(**values),
                    )
        too_large = INVENTORY.InventoryLimits(
            source_entries=INVENTORY.MAXIMUM_SOURCE_ENTRIES + 1
        )
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory((), limits=too_large)

    def test_rejects_unsafe_duplicate_and_non_utf8_paths_or_sources(self) -> None:
        bad_paths = (
            "",
            "/absolute.go",
            "a/../b.go",
            "a//b.go",
            "a\\b.go",
            "C:drive.go",
            "line\nbreak.go",
            "trailing/",
            "e\u0301.go",
        )
        for path in bad_paths:
            with self.subTest(path=path):
                with self.assertRaises(INVENTORY.CandidateInventoryError):
                    INVENTORY.aggregate_candidate_inventory(((path, b"Dial\n"),))
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory(
                (("same.go", b"Dial\n"), ("same.go", b"Resolver\n"))
            )
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory((("bad.go", b"\xff"),))
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory((("nul.go", b"Dial\x00"),))

    def test_rejects_entry_byte_and_line_count_bounds_without_large_fixtures(self) -> None:
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory(
                (("a.go", b"x"), ("b.go", b"x")),
                limits=INVENTORY.InventoryLimits(source_entries=1),
            )
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory(
                (("a.go", b"xx"),),
                limits=INVENTORY.InventoryLimits(source_bytes=1),
            )
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory(
                (("a.go", b"x"), ("b.go", b"x")),
                limits=INVENTORY.InventoryLimits(total_source_bytes=1),
            )
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory(
                (("a.go", b"x\ny\n"),),
                limits=INVENTORY.InventoryLimits(logical_lines_per_source=1),
            )
        with self.assertRaises(INVENTORY.CandidateInventoryError):
            INVENTORY.aggregate_candidate_inventory(
                (("a.go", b"x\n"), ("b.go", b"y\n")),
                limits=INVENTORY.InventoryLimits(total_logical_lines=1),
            )

    def test_module_has_no_filesystem_network_process_or_importlib_calls(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        forbidden_import_roots = {
            "asyncio",
            "importlib",
            "os",
            "pathlib",
            "shutil",
            "socket",
            "subprocess",
            "tempfile",
            "urllib",
            "zipfile",
        }
        forbidden_calls = {
            "open",
            "exec",
            "eval",
            "compile",
            "__import__",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(
                    all(alias.name.split(".", 1)[0] not in forbidden_import_roots for alias in node.names)
                )
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".", 1)[0], forbidden_import_roots)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, forbidden_calls)


if __name__ == "__main__":
    unittest.main()
