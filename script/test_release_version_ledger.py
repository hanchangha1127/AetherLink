#!/usr/bin/env python3
"""Regression tests for the shared release version ledger."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from script.check_release_version_ledger import (
    LedgerError,
    load_release_version_ledger,
    parse_release_version_ledger,
    source_contract_failures,
)


class ReleaseVersionLedgerTests(unittest.TestCase):
    def test_repository_ledger_and_consumers_pass(self) -> None:
        entries = load_release_version_ledger()

        self.assertEqual(len(entries), 9)
        self.assertEqual(entries[-1].build_number, 9)
        self.assertEqual(entries[-1].marketing_version, "1.0.0")
        self.assertEqual(source_contract_failures(entries[-1]), [])

    def test_increasing_builds_allow_same_or_newer_marketing_version(self) -> None:
        entries = parse_release_version_ledger(
            b"build_number\tmarketing_version\n"
            b"1\t1.0.0\n"
            b"2\t1.0.0\n"
            b"9\t1.1.0\n"
        )

        self.assertEqual(
            [(entry.build_number, entry.marketing_version) for entry in entries],
            [(1, "1.0.0"), (2, "1.0.0"), (9, "1.1.0")],
        )

    def test_invalid_closed_format_is_rejected(self) -> None:
        invalid_ledgers = {
            "bom": b"\xef\xbb\xbfbuild_number\tmarketing_version\n1\t1.0.0\n",
            "crlf": b"build_number\tmarketing_version\r\n1\t1.0.0\r\n",
            "missing_final_lf": b"build_number\tmarketing_version\n1\t1.0.0",
            "wrong_header": b"marketing_version\tbuild_number\n1.0.0\t1\n",
            "no_entry": b"build_number\tmarketing_version\n",
            "blank_line": b"build_number\tmarketing_version\n1\t1.0.0\n\n",
            "extra_field": b"build_number\tmarketing_version\n1\t1.0.0\textra\n",
            "zero_build": b"build_number\tmarketing_version\n0\t1.0.0\n",
            "leading_zero_build": b"build_number\tmarketing_version\n01\t1.0.0\n",
            "overflow_build": b"build_number\tmarketing_version\n2100000001\t1.0.0\n",
            "version_suffix": b"build_number\tmarketing_version\n1\t1.0.0-rc1\n",
            "leading_zero_version": b"build_number\tmarketing_version\n1\t01.0.0\n",
            "oversized_version": (
                b"build_number\tmarketing_version\n1\t2147483648.0.0\n"
            ),
            "nul": b"build_number\tmarketing_version\n1\t1.0.0\x00\n",
            "vertical_tab_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x0b2\t1.0.1\n"
            ),
            "form_feed_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x0c2\t1.0.1\n"
            ),
            "file_separator_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x1c2\t1.0.1\n"
            ),
            "group_separator_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x1d2\t1.0.1\n"
            ),
            "record_separator_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x1e2\t1.0.1\n"
            ),
            "delete_control": b"build_number\tmarketing_version\n1\t1.0.0\x7f\n",
            "non_ascii": b"build_number\tmarketing_version\n1\t1.0.0\xc2\xa0\n",
        }

        for label, raw in invalid_ledgers.items():
            with self.subTest(label=label):
                with self.assertRaises(LedgerError):
                    parse_release_version_ledger(raw)

    def test_duplicate_or_regressive_entries_are_rejected(self) -> None:
        invalid_ledgers = {
            "duplicate_build": (
                b"build_number\tmarketing_version\n1\t1.0.0\n1\t1.0.1\n"
            ),
            "lower_build": (
                b"build_number\tmarketing_version\n2\t1.0.0\n1\t1.0.1\n"
            ),
            "lower_version": (
                b"build_number\tmarketing_version\n1\t1.1.0\n2\t1.0.9\n"
            ),
        }

        for label, raw in invalid_ledgers.items():
            with self.subTest(label=label):
                with self.assertRaises(LedgerError):
                    parse_release_version_ledger(raw)

    def test_loader_reports_missing_file_as_ledger_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.tsv"

            with self.assertRaises(LedgerError):
                load_release_version_ledger(missing)


if __name__ == "__main__":
    unittest.main()
