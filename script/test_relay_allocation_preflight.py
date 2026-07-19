#!/usr/bin/env python3
"""Direct mutation tests for the relay allocation preflight response parser."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).resolve().parent / "relay_allocation_preflight.py"
SPEC = importlib.util.spec_from_file_location("relay_allocation_preflight", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load relay allocation preflight")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class RelayAllocationPreflightResponseTests(unittest.TestCase):
    def parse(self, body: str):
        return PREFLIGHT.parse_response(
            "relay.example.test",
            43171,
            PREFLIGHT.RESPONSE_PREFIX + body,
        )

    def assert_invalid_json(self, body: str) -> None:
        with self.assertRaisesRegex(RuntimeError, "returned invalid preflight JSON"):
            self.parse(body)

    def test_canonical_response_passes(self) -> None:
        self.assertEqual(
            self.parse(
                '{"preflight":true,"crypto_version":2,'
                '"allocation_auth":"runtime-p256-v1"}'
            ),
            {
                "preflight": True,
                "crypto_version": 2,
                "allocation_auth": "runtime-p256-v1",
            },
        )

    def test_duplicate_canonical_response_fields_are_rejected(self) -> None:
        mutations = {
            "preflight": (
                '{"preflight":false,"preflight":true,"crypto_version":2,'
                '"allocation_auth":"runtime-p256-v1"}'
            ),
            "crypto_version": (
                '{"preflight":true,"crypto_version":1,"crypto_version":2,'
                '"allocation_auth":"runtime-p256-v1"}'
            ),
            "allocation_auth": (
                '{"preflight":true,"crypto_version":2,'
                '"allocation_auth":"legacy","allocation_auth":"runtime-p256-v1"}'
            ),
        }
        for field, body in mutations.items():
            with self.subTest(field=field):
                self.assert_invalid_json(body)

    def test_nested_duplicate_object_key_is_rejected(self) -> None:
        marker = "leaked-secret-marker"
        body = (
            '{"preflight":true,"crypto_version":2,'
            '"allocation_auth":"runtime-p256-v1",'
            f'"metadata":{{"secret":"{marker}","secret":"second"}}}}'
        )
        with self.assertRaises(RuntimeError) as context:
            self.parse(body)
        self.assertIn("returned invalid preflight JSON", str(context.exception))
        self.assertNotIn(marker, str(context.exception))

    def test_non_finite_values_are_rejected(self) -> None:
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                self.assert_invalid_json(
                    '{"preflight":true,'
                    f'"crypto_version":{token},'
                    '"allocation_auth":"runtime-p256-v1"}'
                )


if __name__ == "__main__":
    unittest.main()
