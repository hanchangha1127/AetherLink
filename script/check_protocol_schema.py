#!/usr/bin/env python3
"""Check the protocol JSON schema and v0.1 active message enum."""

from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "packages" / "protocol-schema" / "protocol.schema.json"

RESERVED_PREFIXES = ("memory.", "skills.", "mcp.", "web_search.")
ALLOWED_TOOL_TYPES = frozenset()


def main() -> int:
    failures: list[str] = []

    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{SCHEMA_PATH.relative_to(ROOT)}: invalid JSON: {error}", file=sys.stderr)
        return 1

    message_enum = (
        schema.get("properties", {})
        .get("type", {})
        .get("enum")
    )
    if not isinstance(message_enum, list) or not all(
        isinstance(message_type, str) for message_type in message_enum
    ):
        failures.append("properties.type.enum must be a list of message type strings")
    else:
        duplicates = sorted(
            {
                message_type
                for message_type in message_enum
                if message_enum.count(message_type) > 1
            }
        )
        if duplicates:
            failures.append(f"properties.type.enum has duplicate entries {duplicates}")

        reserved = [
            message_type
            for message_type in message_enum
            if message_type.startswith(RESERVED_PREFIXES)
        ]
        if reserved:
            failures.append(
                "properties.type.enum includes reserved future messages "
                f"{reserved}"
            )

        unsupported_tool_types = [
            message_type
            for message_type in message_enum
            if message_type.startswith("tool.") and message_type not in ALLOWED_TOOL_TYPES
        ]
        if unsupported_tool_types:
            failures.append(
                "properties.type.enum includes future tool messages not documented "
                f"as active v0.1 {unsupported_tool_types}"
            )

    if failures:
        print("Protocol schema check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Protocol schema OK: {SCHEMA_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
